"""
SWE-bench 인스턴스를 7가지 제어 흐름 패턴 유형으로 분류하고 각 개수를 출력합니다.

유형:
  1. 비동기 처리
  2. 동시성 제어
  3. 동적 디스패치
  4. 고차 함수
  5. 예외 처리
  6. 동적 코드 생성
  7. 이벤트/FSM
"""

import json
import re
from collections import defaultdict
from pathlib import Path

DATASET_PATH = Path(__file__).parent.parent / "dataset_cache" / "SWE-bench" / "test" / "instances.jsonl"

# 각 유형별 키워드 패턴 (patch diff 와 problem_statement 를 모두 검색)
PATTERNS = {
    1: {
        "name": "비동기 처리",
        "patch_keywords": [
            r"\basync\b", r"\bawait\b", r"\basyncio\b", r"\bcoroutine\b",
            r"\bFuture\b", r"\bTask\b", r"\bevent.?loop\b", r"\baiohttp\b",
            r"\btornado\b", r"\btwisted\b", r"\bnon.?blocking\b", r"\bcallback\b",
            r"\bcelery\b", r"\bdeferred\b", r"async_to_sync", r"sync_to_async",
            r"\bPromise\b", r"\bScheduler\b",
        ],
        "problem_keywords": [
            r"\basync\b", r"\basyncio\b", r"\bcoroutine\b", r"\bevent.?loop\b",
            r"\baiohttp\b", r"\bnon.?blocking\b", r"\bdeferred\b",
        ],
    },
    2: {
        "name": "동시성 제어",
        "patch_keywords": [
            r"\bthreading\b", r"\bThread\b", r"\bLock\b", r"\bRLock\b",
            r"\bSemaphore\b", r"\bEvent\b", r"\bCondition\b", r"\bBarrier\b",
            r"\bmultiprocessing\b", r"\bconcurrent\b", r"\bthreadpool\b",
            r"\bThreadPool\b", r"\bracecondition\b", r"\bdeadlock\b",
            r"\batomic\b", r"\bsynchronize\b", r"queue\.Queue", r"\bGIL\b",
            r"thread.?safe",
        ],
        "problem_keywords": [
            r"\bthread\b", r"\bconcurrent\b", r"\bmultiprocessing\b",
            r"\brace.?condition\b", r"\bdeadlock\b", r"\bsynchroniz", r"thread.?safe",
        ],
    },
    3: {
        "name": "동적 디스패치",
        "patch_keywords": [
            r"\b__getattr__\b", r"\b__setattr__\b", r"\b__getattribute__\b",
            r"\bgetattr\b", r"\bhasattr\b", r"\bsetattr\b", r"\bdelattr\b",
            r"\bisinstance\b", r"\btype\(\b", r"\b__class__\b", r"\bMRO\b",
            r"\bdispatch\b", r"\bsingletons?\b", r"\boverload\b",
            r"\bvirtual\b", r"method.?resolution", r"\b__subclasshook__\b",
            r"register\(", r"\bfunctools\.singledispatch\b",
        ],
        "problem_keywords": [
            r"\bdispatch\b", r"\bpolymorphi", r"\bMRO\b", r"\boverload\b",
            r"method.?resolution", r"\b__getattr__\b",
        ],
    },
    4: {
        "name": "고차 함수",
        "patch_keywords": [
            r"\blambda\b", r"\bfunctools\b", r"\bpartial\b", r"\bwraps\b",
            r"\bdecorator\b", r"\b@\w+\n", r"\bclosure\b", r"\bmap\(",
            r"\bfilter\(", r"\breduce\(", r"\bapply\b", r"\bgenerator\b",
            r"\byield\b", r"\byield from\b", r"higher.?order",
            r"\bcallable\b", r"\b__call__\b", r"\bfn\b.*lambda",
        ],
        "problem_keywords": [
            r"\bdecorator\b", r"\bclosure\b", r"\blambda\b", r"\bgenerator\b",
            r"\byield\b", r"higher.?order", r"\bfunctools\b",
        ],
    },
    5: {
        "name": "예외 처리",
        "patch_keywords": [
            r"\btry:\b", r"\bexcept\b", r"\braise\b", r"\bfinally:\b",
            r"\bException\b", r"\bBaseException\b", r"\bRuntimeError\b",
            r"\bValueError\b", r"\bTypeError\b", r"\bKeyError\b",
            r"\bAttributeError\b", r"\bImportError\b", r"\bOSError\b",
            r"\bIOError\b", r"\bStopIteration\b", r"\bGeneratorExit\b",
            r"\bwarnings\.warn\b", r"\bsuppressed?\b", r"\bexception.?handling\b",
            r"\bexc_info\b", r"\btraceback\b",
        ],
        "problem_keywords": [
            r"\bexception\b", r"\berror.?handling\b", r"\btraceback\b",
            r"\braise\b", r"\bcrash\b", r"\bfail\b.*except",
        ],
    },
    6: {
        "name": "동적 코드 생성",
        "patch_keywords": [
            r"\bexec\(", r"\beval\(", r"\bcompile\(", r"\bast\b",
            r"\bmetaclass\b", r"\b__new__\b", r"\btype\(\w+,",
            r"\binspect\b", r"\breflect", r"\bdynamic\b.*class",
            r"code.?generat", r"\b__code__\b", r"\bco_code\b",
            r"\bgenerate.*code\b", r"\bdynamic.*import\b",
            r"importlib", r"\b__import__\b", r"\bpickle\b",
            r"\bshelve\b", r"\bmarshal\b",
        ],
        "problem_keywords": [
            r"\bexec\b", r"\beval\b", r"\bmetaclass\b", r"\bdynamic.*class\b",
            r"code.?generat", r"\binspect\b", r"\breflect",
        ],
    },
    7: {
        "name": "이벤트/FSM",
        "patch_keywords": [
            r"\bsignal\b", r"\bemit\b", r"\bListener\b", r"\bObserver\b",
            r"\bon_enter\b", r"\bon_exit\b", r"\btransition\b",
            r"\bstate.?machine\b", r"\bFSM\b", r"\bpublish\b", r"\bsubscribe\b",
            r"\bdispatchEvent\b", r"\bEventHandler\b", r"\bEventEmitter\b",
            r"\bhook\b", r"\bnotif", r"event.?driven", r"\bcallback.*event\b",
        ],
        "problem_keywords": [
            r"\bsignal\b", r"\bevent.?driven\b", r"\bstate.?machine\b",
            r"\bFSM\b", r"\bobserver\b", r"\bpublish.*subscribe\b",
        ],
    },
}


def text_matches(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    for kw in keywords:
        if re.search(kw, text, re.IGNORECASE):
            return True
    return False


def classify_instance(instance: dict) -> list[int]:
    patch = instance.get("patch", "")
    test_patch = instance.get("test_patch", "")
    problem = instance.get("problem_statement", "")

    matched = []
    for type_id, cfg in PATTERNS.items():
        patch_hit = text_matches(patch + "\n" + test_patch, cfg["patch_keywords"])
        problem_hit = text_matches(problem, cfg["problem_keywords"])
        if patch_hit or problem_hit:
            matched.append(type_id)
    return matched


def main():
    counts = defaultdict(int)
    instance_ids_by_type = defaultdict(list)
    total = 0

    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            instance = json.loads(line)
            total += 1
            matched_types = classify_instance(instance)
            for t in matched_types:
                counts[t] += 1
                instance_ids_by_type[t].append(instance["instance_id"])

    TYPE_NAMES_EN = {
        1: "Async Processing",
        2: "Concurrency Control",
        3: "Dynamic Dispatch",
        4: "Higher-Order Functions",
        5: "Exception Handling",
        6: "Dynamic Code Generation",
        7: "Event / FSM",
    }

    print(f"Total instances: {total}\n")
    print(f"{'#':>3}  {'Type':<24}  {'Count':>6}  {'Ratio':>6}")
    print("-" * 50)
    for type_id in sorted(PATTERNS.keys()):
        name = TYPE_NAMES_EN[type_id]
        count = counts[type_id]
        ratio = count / total * 100 if total else 0
        print(f"  {type_id:>1}  {name:<24}  {count:>6}  {ratio:>5.1f}%")

    all_matched_ids = set()
    for ids in instance_ids_by_type.values():
        all_matched_ids.update(ids)
    print(f"\nInstances matching >= 1 type : {len(all_matched_ids)} ({len(all_matched_ids)/total*100:.1f}%)")
    print(f"Instances matching no type   : {total - len(all_matched_ids)} ({(total - len(all_matched_ids))/total*100:.1f}%)")


if __name__ == "__main__":
    main()
