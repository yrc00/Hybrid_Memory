"""
SWE-bench Lite에서 '비동기 처리' 유형 인스턴스를 추출하고,
qwen7b-cl의 file-level Acc@k 정확도를 계산합니다.

정확도 기준:
  - Acc@k: 예측한 상위 k개 파일 안에 ground-truth 파일이 하나라도 포함되면 correct
  - instance-level 정확도 = correct / total_async_instances
"""

import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent

LITE_DATASET  = BASE / "dataset_cache" / "SWE-bench_Lite" / "test" / "instances.jsonl"
RESULTS_FILE  = BASE / "results" / "qwen7b-cl_swe-bench" / "SWE-bench_Lite" / "location" / "merged_loc_outputs.jsonl"

# 비동기 처리 패턴 (classify_swe_bench.py 의 유형 1과 동일)
ASYNC_PATCH_KWS = [
    r"\basync\b", r"\bawait\b", r"\basyncio\b", r"\bcoroutine\b",
    r"\bFuture\b", r"\bTask\b", r"\bevent.?loop\b", r"\baiohttp\b",
    r"\btornado\b", r"\btwisted\b", r"\bnon.?blocking\b", r"\bcallback\b",
    r"\bcelery\b", r"\bdeferred\b", r"async_to_sync", r"sync_to_async",
    r"\bPromise\b", r"\bScheduler\b",
]
ASYNC_PROBLEM_KWS = [
    r"\basync\b", r"\basyncio\b", r"\bcoroutine\b", r"\bevent.?loop\b",
    r"\baiohttp\b", r"\bnon.?blocking\b", r"\bdeferred\b",
]

K_VALUES = [1, 3, 5, 10, 15]


def matches_any(text: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def is_async(instance: dict) -> bool:
    patch   = instance.get("patch", "")
    test_p  = instance.get("test_patch", "")
    problem = instance.get("problem_statement", "")
    return (
        matches_any(patch + "\n" + test_p, ASYNC_PATCH_KWS)
        or matches_any(problem, ASYNC_PROBLEM_KWS)
    )


def gt_files_from_patch(patch: str) -> set[str]:
    return set(re.findall(r"^--- a/(.+)$", patch, re.MULTILINE))


def main():
    # SWE-bench Lite 전체 인스턴스 로드
    lite_instances: dict[str, dict] = {}
    with open(LITE_DATASET, encoding="utf-8") as f:
        for line in f:
            inst = json.loads(line)
            lite_instances[inst["instance_id"]] = inst

    # 비동기 처리 인스턴스 필터링
    async_ids = {iid for iid, inst in lite_instances.items() if is_async(inst)}
    print(f"Total SWE-bench Lite instances : {len(lite_instances)}")
    print(f"Async Processing instances     : {len(async_ids)}")
    print()

    # qwen7b-cl 결과 로드 (merged = majority vote)
    results: dict[str, dict] = {}
    with open(RESULTS_FILE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            results[r["instance_id"]] = r

    # Acc@k 계산
    correct_at = defaultdict(int)
    missing = []

    for iid in async_ids:
        if iid not in results:
            missing.append(iid)
            continue

        inst   = lite_instances[iid]
        result = results[iid]

        gt     = gt_files_from_patch(inst.get("patch", ""))
        preds  = result.get("found_files", [])  # list of files in ranked order

        for k in K_VALUES:
            top_k = set(preds[:k])
            if gt & top_k:
                correct_at[k] += 1

    evaluated = len(async_ids) - len(missing)
    print(f"Evaluated : {evaluated}  (missing results: {len(missing)})")
    print()
    print(f"{'Metric':<14}  {'Correct':>7}  {'Total':>7}  {'Acc':>7}")
    print("-" * 40)
    for k in K_VALUES:
        c = correct_at[k]
        acc = c / evaluated * 100 if evaluated else 0
        print(f"file/Acc@{k:<4}  {c:>7}  {evaluated:>7}  {acc:>6.1f}%")

    # 대표 async 인스턴스 목록 출력
    print(f"\n--- Async instance IDs ({len(async_ids)}) ---")
    for iid in sorted(async_ids):
        inst   = lite_instances[iid]
        result = results.get(iid, {})
        gt     = gt_files_from_patch(inst.get("patch", ""))
        preds  = result.get("found_files", [])
        hit1   = "O" if (gt & set(preds[:1])) else "X"
        hit5   = "O" if (gt & set(preds[:5])) else "X"
        print(f"  {hit1}/{hit5}  {iid}")

    if missing:
        print(f"\nMissing result for: {missing}")


if __name__ == "__main__":
    main()
