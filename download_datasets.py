"""
HuggingFace 벤치마크 데이터셋을 로드하여 로컬에 저장하는 스크립트.

저장 경로: dataset_cache/{DATASET_NAME}/{split}/
포맷: JSONL (각 줄이 하나의 instance)

Usage:
    python download_datasets.py                  # 전체 다운로드
    python download_datasets.py --dataset lite   # 특정 dataset만
"""

import os
import json
import argparse
from datetime import date, datetime
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm


class _JSONEncoder(json.JSONEncoder):
    """datetime / date 타입을 ISO 8601 문자열로 직렬화."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


DATASETS = {
    "SWE-bench_Lite": {
        "hf_name": "SWE-bench/SWE-bench_Lite",
        "split": "test",
    },
    "SWE-bench_Verified": {
        "hf_name": "SWE-bench/SWE-bench_Verified",
        "split": "test",
    },
    "SWE-bench-Live": {
        "hf_name": "SWE-bench-Live/SWE-bench-Live",
        "split": "lite",
    },
    "Loc-Bench_V1": {
        "hf_name": "czlll/Loc-Bench_V1",
        "split": "test",
    },
}

# CLI alias → key 매핑
ALIASES = {
    "lite":     "SWE-bench_Lite",
    "verified": "SWE-bench_Verified",
    "live":     "SWE-bench-Live",
    "loc":      "Loc-Bench_V1",
}


def download_and_save(name: str, hf_name: str, split: str, output_dir: Path) -> None:
    save_path = output_dir / name / split
    save_path.mkdir(parents=True, exist_ok=True)
    jsonl_path = save_path / "instances.jsonl"

    print(f"\n[{name}] Loading from HuggingFace: {hf_name} (split={split})")
    data = load_dataset(hf_name, split=split)

    print(f"[{name}] {len(data)} instances → {jsonl_path}")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for instance in tqdm(data, desc=f"  Saving {name}", unit="inst"):
            f.write(json.dumps(instance, ensure_ascii=False, cls=_JSONEncoder) + "\n")

    # instance_id 목록도 함께 저장 (빠른 필터링용)
    ids_path = save_path / "instance_ids.txt"
    with open(ids_path, "w", encoding="utf-8") as f:
        for instance in data:
            f.write(instance["instance_id"] + "\n")

    print(f"[{name}] Done. ({len(data)} instances)")


def main():
    parser = argparse.ArgumentParser(description="Download SWE-bench / Loc-Bench datasets from HuggingFace")
    parser.add_argument(
        "--dataset",
        type=str,
        default="all",
        choices=["all"] + list(ALIASES.keys()),
        help="다운로드할 dataset (기본값: all)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="dataset_cache",
        help="저장 경로 (기본값: dataset_cache)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    targets = DATASETS if args.dataset == "all" else {ALIASES[args.dataset]: DATASETS[ALIASES[args.dataset]]}

    for name, cfg in targets.items():
        download_and_save(
            name=name,
            hf_name=cfg["hf_name"],
            split=cfg["split"],
            output_dir=output_dir,
        )

    print("\nAll done.")
    print(f"Saved to: {output_dir.resolve()}/")


if __name__ == "__main__":
    main()
