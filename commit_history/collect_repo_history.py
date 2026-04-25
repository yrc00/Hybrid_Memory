"""
GitHub 레포지토리 전체 issue + patch(merged PR diff)를 수집하고
시간 순서 인덱스(timeline)를 생성하는 스크립트.

■ 저장 구조
    commit_history/
      repos/
        {owner}__{repo}/
          issues/
            {iso_created_at}__{number}.md       ← issue 본문
          patches/
            {iso_created_at}__{number}.diff     ← linked PR diff
          timeline.jsonl                        ← 시간 순 인덱스 (1줄=1항목)
          metadata.json                         ← 수집 요약

■ timeline.jsonl 한 행의 스키마
    {
      "number":      123,
      "type":        "issue" | "pr",
      "title":       "...",
      "created_at":  "2021-03-15T10:23:00Z",   ← ISO 8601 UTC
      "closed_at":   "2021-03-20T08:11:00Z",
      "issue_file":  "repos/owner__repo/issues/2021-03-15T102300__123.md",
      "patch_file":  "repos/owner__repo/patches/2021-03-15T102300__123.diff",  # 없으면 null
      "pr_number":   456,           # issue와 연결된 PR 번호 (없으면 null)
      "pr_merged_at":"2021-03-20T...",
      "labels":      ["bug", "..."]
    }

■ 시간 기반 필터 예시 (평가 시 활용)
    from collect_repo_history import load_timeline_before

    entries = load_timeline_before(
        repo="django/django",
        cutoff_dt="2021-06-01T00:00:00Z",   # 이 시각 이전 항목만
        base_dir="commit_history",
    )

■ 필요 환경변수
    GITHUB_TOKEN=xxxx   (없으면 rate-limit 60 req/h 적용)
		
Usage:
    # 벤치마크에 포함된 레포 자동 추출 후 수집
    python collect_repo_history.py --benchmark lite

    # 특정 레포만 수집
    python collect_repo_history.py --repo django/django --repo astropy/astropy

    # 벤치마크 + 추가 레포
    python collect_repo_history.py --benchmark verified --repo pallets/flask

    # 최근 N개 issue만 (테스트용)
    python collect_repo_history.py --repo django/django --max_issues 200
    
    GITHUB_TOKEN=ghp_xxxx python commit_history/collect_repo_history.py --benchmark lite

    tmux new-session -d -s collect_job && \
    tmux send-keys -t collect_job "GITHUB_TOKEN=ghp_xxxx python commit_history/collect_repo_history.py --benchmark lite > commit_history/run_$(date +%Y%m%d_%H%M%S).log 2>&1" Enter
"""

from __future__ import annotations

import os
import re
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from tqdm import tqdm

# ──────────────────────────────────────────────────────────────────────────────
# 로깅
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 벤치마크 정의 (collect_issues_patches.py 와 동일)
# ──────────────────────────────────────────────────────────────────────────────
DATASETS: dict[str, dict] = {
    "SWE-bench_Lite":     {"hf_name": "SWE-bench/SWE-bench_Lite",      "split": "test"},
    "SWE-bench_Verified": {"hf_name": "SWE-bench/SWE-bench_Verified",   "split": "test"},
    "SWE-bench-Live":     {"hf_name": "SWE-bench-Live/SWE-bench-Live",  "split": "lite"},
    "Loc-Bench_V1":       {"hf_name": "czlll/Loc-Bench_V1",             "split": "test"},
}
ALIASES: dict[str, str] = {
    "lite":     "SWE-bench_Lite",
    "verified": "SWE-bench_Verified",
    "live":     "SWE-bench-Live",
    "loc":      "Loc-Bench_V1",
}

# ──────────────────────────────────────────────────────────────────────────────
# GitHub API 클라이언트
# ──────────────────────────────────────────────────────────────────────────────
_GITHUB_API = "https://api.github.com"
_CLOSE_PATTERN = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#(\d+)",
    re.IGNORECASE,
)


class GitHubClient:
    """최소한의 GitHub REST API 래퍼 (rate-limit 자동 대기)."""

    def __init__(self, token: str | None = None) -> None:
        self.session = requests.Session()
        headers = {"Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    # ── 내부 GET ──────────────────────────────────────────────────────────────
    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        while True:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - int(time.time()), 1) + 2
                logger.warning(f"Rate limit 초과 — {wait}초 대기 중...")
                time.sleep(wait)
                continue
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"429 Too Many Requests — {wait}초 대기 중...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp

    # ── 페이지네이션 ───────────────────────────────────────────────────────────
    def paginate(self, url: str, params: dict | None = None) -> Iterator[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        while True:
            params["page"] = page
            resp = self._get(url, params)
            items = resp.json()
            if not items:
                break
            yield from items
            # Link 헤더에 next가 없으면 종료
            if 'rel="next"' not in resp.headers.get("Link", ""):
                break
            page += 1

    # ── 단건 조회 ─────────────────────────────────────────────────────────────
    def get_json(self, url: str, params: dict | None = None) -> dict:
        return self._get(url, params).json()

    # ── PR diff ───────────────────────────────────────────────────────────────
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        old_accept = self.session.headers["Accept"]
        self.session.headers["Accept"] = "application/vnd.github.v3.diff"
        try:
            resp = self._get(url)
            return resp.text
        except Exception:
            return ""
        finally:
            self.session.headers["Accept"] = old_accept


# ──────────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────────

def _dt_to_tag(iso: str) -> str:
    """'2021-03-15T10:23:00Z' → '2021-03-15T102300' (파일명용)."""
    return iso[:19].replace(":", "").replace("-", "").replace("T", "T")


def _parse_iso(iso: str | None) -> datetime | None:
    if not iso:
        return None
    iso = iso.rstrip("Z")
    try:
        return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _closed_issue_numbers(text: str) -> list[int]:
    """PR body에서 'Closes #N' 패턴으로 연결 issue 번호 추출."""
    return [int(m) for m in _CLOSE_PATTERN.findall(text or "")]


# ──────────────────────────────────────────────────────────────────────────────
# 레포 수집 핵심 로직
# ──────────────────────────────────────────────────────────────────────────────

def collect_repo(
    client: GitHubClient,
    repo_full: str,
    output_root: Path,
    max_issues: int | None = None,
    skip_done: bool = False,
) -> None:
    """레포 하나의 closed issue + merged PR diff를 수집."""
    owner, repo_name = repo_full.split("/", 1)
    repo_slug = f"{owner}__{repo_name}"
    repo_dir   = output_root / "repos" / repo_slug
    issues_dir = repo_dir / "issues"
    patches_dir = repo_dir / "patches"

    if skip_done and (repo_dir / "metadata.json").exists():
        logger.info(f"[{repo_full}] metadata.json 존재 — 건너뜀 (--skip_done)")
        return

    issues_dir.mkdir(parents=True, exist_ok=True)
    patches_dir.mkdir(parents=True, exist_ok=True)

    # ── 이전 수집 재개: 기존 timeline.jsonl 로드 ─────────────────────────────
    timeline_path = repo_dir / "timeline.jsonl"
    existing_entries: dict[int, dict] = {}
    if timeline_path.exists():
        with open(timeline_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line:
                    continue
                _entry = json.loads(_line)
                existing_entries[_entry["number"]] = _entry
        if existing_entries:
            logger.info(
                f"[{repo_full}] 기존 timeline {len(existing_entries)}건 발견 — "
                "이미 수집된 항목은 건너뜁니다."
            )

    # ── Step 1: merged PR 목록 → {이슈번호: PR 정보} 매핑 구축 ─────────────
    logger.info(f"[{repo_full}] merged PR 수집 중...")
    pr_url = f"{_GITHUB_API}/repos/{owner}/{repo_name}/pulls"
    issue_to_pr: dict[int, dict] = {}   # issue_number → pr_data
    pr_list: list[dict] = []

    for pr in tqdm(
        client.paginate(pr_url, {"state": "closed"}),
        desc=f"  PR 페이지",
        unit="pr",
        leave=False,
    ):
        if not pr.get("merged_at"):
            continue  # merged된 것만
        pr_list.append(pr)
        # body에서 closes #N 추출
        for num in _closed_issue_numbers(pr.get("body") or ""):
            issue_to_pr[num] = pr

    logger.info(f"[{repo_full}] merged PR {len(pr_list)}개, issue 연결 {len(issue_to_pr)}건")

    # ── Step 2: closed issue 수집 ─────────────────────────────────────────────
    logger.info(f"[{repo_full}] closed issue 수집 중...")
    iss_url = f"{_GITHUB_API}/repos/{owner}/{repo_name}/issues"
    timeline_entries: list[dict] = list(existing_entries.values())  # 기존 항목 포함
    fetched = 0

    issue_iter = client.paginate(iss_url, {"state": "closed", "sort": "created", "direction": "asc"})

    # 새로 수집된 항목을 즉시 append — 중단되더라도 다음 실행에서 재개 가능
    with open(timeline_path, "a", encoding="utf-8") as _tl_file:
        for issue in tqdm(issue_iter, desc=f"  Issue", unit="iss", leave=False):
            # PR은 issues API에도 등장하므로 제외
            if "pull_request" in issue:
                continue

            fetched += 1
            if max_issues and fetched > max_issues:
                break

            number: int    = issue["number"]

            # ── 이미 수집된 항목은 건너뜀 ────────────────────────────────────
            if number in existing_entries:
                continue

            created_at: str = issue.get("created_at") or ""
            closed_at: str  = issue.get("closed_at") or ""
            title: str      = issue.get("title") or ""
            body: str       = issue.get("body") or ""
            labels: list    = [lb["name"] for lb in issue.get("labels") or []]
            tag = _dt_to_tag(created_at) if created_at else f"nodate__{number}"

            # ── issue 파일 저장 ───────────────────────────────────────────────
            issue_filename = f"{tag}__{number}.md"
            issue_path = issues_dir / issue_filename
            if not issue_path.exists():
                issue_content = _render_issue_md(
                    number=number, title=title, body=body,
                    created_at=created_at, closed_at=closed_at,
                    labels=labels, repo=repo_full,
                )
                issue_path.write_text(issue_content, encoding="utf-8")

            issue_rel = str(issue_path.relative_to(output_root))

            # ── 연결 PR이 있으면 diff 저장 ────────────────────────────────────
            pr = issue_to_pr.get(number)
            patch_rel: str | None = None
            pr_number: int | None = None
            pr_merged_at: str | None = None

            if pr:
                pr_number   = pr["number"]
                pr_merged_at = pr.get("merged_at")
                patch_filename = f"{tag}__{number}.diff"
                patch_path = patches_dir / patch_filename

                if not patch_path.exists():
                    diff_text = client.get_pr_diff(owner, repo_name, pr_number)
                    patch_path.write_text(diff_text, encoding="utf-8")

                patch_rel = str(patch_path.relative_to(output_root))

            # ── timeline 항목 즉시 기록 ───────────────────────────────────────
            entry = {
                "number":      number,
                "type":        "issue",
                "title":       title,
                "created_at":  created_at,
                "closed_at":   closed_at,
                "issue_file":  issue_rel,
                "patch_file":  patch_rel,       # None이면 연결 PR 없음
                "pr_number":   pr_number,
                "pr_merged_at": pr_merged_at,
                "labels":      labels,
            }
            _tl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            _tl_file.flush()
            timeline_entries.append(entry)

    # ── Step 3: PR 자체도 timeline에 추가 (issue 없이 직접 수정된 경우) ───────
    issue_linked_prs = {v["number"] for v in issue_to_pr.values()}

    with open(timeline_path, "a", encoding="utf-8") as _tl_file:
        for pr in tqdm(pr_list, desc=f"  독립 PR", unit="pr", leave=False):
            if pr["number"] in issue_linked_prs:
                continue  # 이미 issue와 연결된 PR은 중복 제외

            number     = pr["number"]

            # ── 이미 수집된 항목은 건너뜀 ────────────────────────────────────
            if number in existing_entries:
                continue

            created_at = pr.get("created_at") or ""
            merged_at  = pr.get("merged_at") or ""
            title      = pr.get("title") or ""
            labels     = [lb["name"] for lb in pr.get("labels") or []]
            tag = _dt_to_tag(created_at) if created_at else f"nodate__{number}"

            # issue 파일 (PR 설명을 issue처럼 저장)
            issue_filename = f"{tag}__{number}.md"
            issue_path = issues_dir / issue_filename
            if not issue_path.exists():
                issue_content = _render_pr_md(
                    number=number, title=title, body=pr.get("body") or "",
                    created_at=created_at, merged_at=merged_at,
                    labels=labels, repo=repo_full,
                )
                issue_path.write_text(issue_content, encoding="utf-8")

            issue_rel = str(issue_path.relative_to(output_root))

            # patch diff 저장
            patch_filename = f"{tag}__{number}.diff"
            patch_path = patches_dir / patch_filename
            if not patch_path.exists():
                diff_text = client.get_pr_diff(owner, repo_name, number)
                patch_path.write_text(diff_text, encoding="utf-8")

            patch_rel = str(patch_path.relative_to(output_root))

            entry = {
                "number":      number,
                "type":        "pr",
                "title":       title,
                "created_at":  created_at,
                "closed_at":   merged_at,
                "issue_file":  issue_rel,
                "patch_file":  patch_rel,
                "pr_number":   number,
                "pr_merged_at": merged_at,
                "labels":      labels,
            }
            _tl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            _tl_file.flush()
            timeline_entries.append(entry)

    # ── Step 4: 시간 순 정렬 후 timeline.jsonl 재작성 ────────────────────────
    timeline_entries.sort(key=lambda e: e.get("created_at") or "")

    with open(timeline_path, "w", encoding="utf-8") as f:
        for entry in timeline_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── Step 5: metadata.json 저장 ───────────────────────────────────────────
    meta = {
        "repo":         repo_full,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_issues": sum(1 for e in timeline_entries if e["type"] == "issue"),
        "total_prs":    sum(1 for e in timeline_entries if e["type"] == "pr"),
        "with_patch":   sum(1 for e in timeline_entries if e["patch_file"]),
        "earliest":     timeline_entries[0]["created_at"] if timeline_entries else None,
        "latest":       timeline_entries[-1]["created_at"] if timeline_entries else None,
    }
    (repo_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        f"[{repo_full}] 완료 — "
        f"issue {meta['total_issues']}개 / PR {meta['total_prs']}개 / "
        f"patch 포함 {meta['with_patch']}개\n"
        f"  저장: {repo_dir.resolve()}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 파일 렌더러
# ──────────────────────────────────────────────────────────────────────────────

def _render_issue_md(*, number, title, body, created_at, closed_at, labels, repo) -> str:
    lines = [
        f"# Issue #{number}: {title}",
        f"",
        f"**Repository**: `{repo}`",
        f"**Created**: {created_at}",
        f"**Closed**: {closed_at}",
    ]
    if labels:
        lines.append(f"**Labels**: {', '.join(labels)}")
    lines += ["", "## Description", "", body or "(no description)"]
    return "\n".join(lines)


def _render_pr_md(*, number, title, body, created_at, merged_at, labels, repo) -> str:
    lines = [
        f"# PR #{number}: {title}",
        f"",
        f"**Repository**: `{repo}`",
        f"**Created**: {created_at}",
        f"**Merged**: {merged_at}",
    ]
    if labels:
        lines.append(f"**Labels**: {', '.join(labels)}")
    lines += ["", "## Description", "", body or "(no description)"]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# 평가 시 사용하는 temporal 필터 유틸 (외부에서 import 가능)
# ──────────────────────────────────────────────────────────────────────────────

def load_timeline_before(
    repo: str,
    cutoff_dt: str,
    base_dir: str | Path = "commit_history",
    require_patch: bool = False,
) -> list[dict]:
    """
    cutoff_dt(ISO 8601) 이전에 생성된 timeline 항목만 반환.

    Parameters
    ----------
    repo         : "owner/repo" 형식
    cutoff_dt    : 이 시각 이전 항목만 반환 (예: "2021-06-01T00:00:00Z")
    base_dir     : commit_history 루트 경로
    require_patch: True면 patch_file이 있는 항목만 반환

    Returns
    -------
    list of timeline entry dicts (시간 오름차순)
    """
    owner, repo_name = repo.split("/", 1)
    repo_slug = f"{owner}__{repo_name}"
    timeline_path = Path(base_dir) / "repos" / repo_slug / "timeline.jsonl"

    if not timeline_path.exists():
        logger.warning(f"timeline.jsonl 없음: {timeline_path}")
        return []

    cutoff = _parse_iso(cutoff_dt)
    results: list[dict] = []

    with open(timeline_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entry_dt = _parse_iso(entry.get("created_at"))
            if entry_dt is None or entry_dt >= cutoff:
                continue
            if require_patch and not entry.get("patch_file"):
                continue
            results.append(entry)

    return results  # 이미 시간 순 정렬됨


def get_issue_content(entry: dict, base_dir: str | Path = "commit_history") -> str:
    """timeline entry로부터 issue 파일 내용을 반환."""
    p = Path(base_dir) / entry["issue_file"]
    return p.read_text(encoding="utf-8") if p.exists() else ""


def get_patch_content(entry: dict, base_dir: str | Path = "commit_history") -> str:
    """timeline entry로부터 patch diff 내용을 반환."""
    if not entry.get("patch_file"):
        return ""
    p = Path(base_dir) / entry["patch_file"]
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ──────────────────────────────────────────────────────────────────────────────
# 벤치마크에서 레포 목록 추출
# ──────────────────────────────────────────────────────────────────────────────

def repos_from_benchmark(benchmark_name: str, dataset_cache_dir: Path) -> list[str]:
    """벤치마크 instances.jsonl 에서 unique repo 목록을 추출."""
    cfg = DATASETS[benchmark_name]
    local_path = dataset_cache_dir / benchmark_name / cfg["split"] / "instances.jsonl"

    repos: set[str] = set()

    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                inst = json.loads(line)
                if inst.get("repo"):
                    repos.add(inst["repo"])
    else:
        logger.info(f"로컬 캐시 없음 → HuggingFace에서 {benchmark_name} 로드...")
        from datasets import load_dataset
        data = load_dataset(cfg["hf_name"], split=cfg["split"])
        repos = {d["repo"] for d in data if d.get("repo")}

    logger.info(f"[{benchmark_name}] 고유 레포 {len(repos)}개: {sorted(repos)[:5]} ...")
    return sorted(repos)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHub 레포 전체 issue & patch 수집기 (시간 순 인덱스 포함)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--benchmark", "-b",
        type=str,
        default=None,
        metavar="BENCHMARK",
        help="벤치마크 이름 (lite/verified/live/loc/SWE-bench_Lite/…)\n"
             "포함된 레포를 자동으로 추출",
    )
    parser.add_argument(
        "--repo", "-r",
        type=str,
        action="append",
        default=[],
        metavar="OWNER/REPO",
        help="직접 레포 지정 (여러 번 사용 가능)\n예: --repo django/django",
    )
    parser.add_argument(
        "--output_dir", "-o",
        type=str,
        default="commit_history",
        help="저장 루트 (기본: commit_history/)",
    )
    parser.add_argument(
        "--dataset_cache_dir",
        type=str,
        default="dataset_cache",
        help="로컬 dataset 캐시 경로 (기본: dataset_cache/)",
    )
    parser.add_argument(
        "--max_issues",
        type=int,
        default=None,
        metavar="N",
        help="레포당 최대 수집 issue 수 (테스트용)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub Personal Access Token\n"
             "(기본: GITHUB_TOKEN 환경변수 사용)",
    )
    parser.add_argument(
        "--skip_done",
        action="store_true",
        default=False,
        help="metadata.json이 이미 존재하는 레포는 건너뜀 (재시작/이어받기용)",
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning(
            "GITHUB_TOKEN이 설정되지 않았습니다. "
            "Rate limit이 시간당 60 req로 제한됩니다."
        )

    client = GitHubClient(token=token)
    output_root      = Path(args.output_dir)
    dataset_cache_dir = Path(args.dataset_cache_dir)

    # 수집 대상 레포 목록 구성
    repos: list[str] = list(args.repo)  # 직접 지정 레포

    if args.benchmark:
        bm = ALIASES.get(args.benchmark, args.benchmark)
        if bm not in DATASETS:
            parser.error(f"알 수 없는 벤치마크: '{args.benchmark}'")
        bm_repos = repos_from_benchmark(bm, dataset_cache_dir)
        for r in bm_repos:
            if r not in repos:
                repos.append(r)

    if not repos:
        parser.error("--benchmark 또는 --repo 중 하나 이상 지정해야 합니다.")

    logger.info(f"수집 대상 레포 {len(repos)}개: {repos}")

    for repo in repos:
        try:
            collect_repo(
                client=client,
                repo_full=repo,
                output_root=output_root,
                max_issues=args.max_issues,
                skip_done=args.skip_done,
            )
        except Exception as e:
            logger.error(f"[{repo}] 수집 실패: {e}", exc_info=True)

    logger.info("모든 수집 완료.")


if __name__ == "__main__":
    main()
