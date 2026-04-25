"""
Re-parse existing raw_output_loc from loc_outputs.jsonl without calling the API.
Only re-processes entries where found_files == [[],[]] (empty results).

Modes:
  - full (default): uses graph index pkl files to resolve modules/entities
  - lite (--lite):  graph-free, extracts only file paths from raw output

Usage:
    # full mode (requires GRAPH_INDEX_DIR with .pkl files)
    export GRAPH_INDEX_DIR="./index_data/SWE-bench-Live/graph_index_v2.3"
    python reparse_outputs.py --input_file <path/to/loc_outputs.jsonl>

    # lite mode (no graph needed, file paths only)
    python reparse_outputs.py --input_file <path/to/loc_outputs.jsonl> --lite

    # overwrite in-place (.bak backup is created automatically)
    python reparse_outputs.py --input_file <path/to/loc_outputs.jsonl> [--lite] --inplace
"""

import argparse
import json
import os
import re
import shutil
from tqdm import tqdm


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_jsonl(path):
    with open(path, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(records, path):
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def is_empty(loc):
    ff = loc.get("found_files", [[]])
    return all(len(x) == 0 for x in ff)


# ---------------------------------------------------------------------------
# lite parsing (no graph index required)
# ---------------------------------------------------------------------------

def _extract_text_to_parse(raw_output: str) -> str:
    """Extract content from triple-backtick blocks; fall back to full text."""
    code_blocks = re.findall(r'```[^\n]*\n(.*?)```', raw_output, re.DOTALL)
    if code_blocks:
        return '\n'.join(code_blocks)
    return raw_output.strip('` \n')


def _extract_locs(text: str) -> tuple:
    """Extract file paths, modules, and entities from structured text.

    Handles lines like:
        some/path/file.py
        function: my_func
        class: MyClass
        method: MyClass.my_method
        function: MyClass.my_method   (dot notation)

    line: is skipped — cannot resolve to a function name without the graph.

    Returns:
        files    : list of file paths
        modules  : list of "file:ClassName" or "file:func_name"
        entities : list of "file:ClassName.method" or "file:func_name"
    """
    files, modules, entities = [], [], []
    current_file = None
    current_class = None

    for line in text.splitlines():
        line = line.strip().strip(':').strip()
        if not line:
            continue

        # ── file path ──────────────────────────────────────────────────
        if line.endswith('.py'):
            match = re.search(r'[\w\./-]+\.py', line)
            if match:
                fp = match.group(0)
                if fp not in files:
                    files.append(fp)
                current_file = fp
                current_class = None
            continue

        if current_file is None:
            continue

        # ── class ──────────────────────────────────────────────────────
        if line.startswith('class:'):
            name = line[len('class:'):].strip().split()[0]
            if name and name != 'N/A':
                current_class = name
                mid = f'{current_file}:{name}'
                if mid not in modules:
                    modules.append(mid)
            continue

        # ── function / method ──────────────────────────────────────────
        if line.startswith(('function:', 'method:')):
            name = line.split(':', 1)[1].strip().split()[0].strip('()')
            if not name or name == 'N/A':
                continue

            if '.' in name:
                # e.g. "MyClass.my_method"
                class_part, method_part = name.split('.', 1)
                eid = f'{current_file}:{class_part}.{method_part}'
                mid = f'{current_file}:{class_part}'
                current_class = class_part
            elif current_class:
                # bare method name after a class: line
                eid = f'{current_file}:{current_class}.{name}'
                mid = f'{current_file}:{current_class}'
            else:
                eid = f'{current_file}:{name}'
                mid = f'{current_file}:{name}'

            if mid not in modules:
                modules.append(mid)
            if eid not in entities:
                entities.append(eid)

    return files, modules, entities


def lite_parse(raw_outputs: list) -> tuple:
    """Return (all_found_files, all_found_modules, all_found_entities) without graph."""
    all_found_files, all_found_modules, all_found_entities = [], [], []
    for raw in raw_outputs:
        text = _extract_text_to_parse(raw)
        files, modules, entities = _extract_locs(text)
        all_found_files.append(files)
        all_found_modules.append(modules)
        all_found_entities.append(entities)
    return all_found_files, all_found_modules, all_found_entities


# ---------------------------------------------------------------------------
# full parsing (requires graph index)
# ---------------------------------------------------------------------------

def full_parse(instance_id: str, raw_outputs: list) -> tuple:
    from util.process_output import get_loc_results_from_raw_outputs
    return get_loc_results_from_raw_outputs(instance_id, raw_outputs)


def debug_one(input_file: str, instance_id: str = None):
    """Trace exactly why full mode fails for a given instance."""
    import pickle
    import re
    graph_dir = os.environ.get("GRAPH_INDEX_DIR", "index_data/graph_index")

    records = load_jsonl(input_file)
    target = None
    for rec in records:
        if not is_empty(rec):
            continue
        if instance_id is None or rec["instance_id"] == instance_id:
            target = rec
            break

    if target is None:
        print("No matching empty record found.")
        return

    iid = target["instance_id"]
    print(f"=== instance: {iid}")

    pkl_path = f"{graph_dir}/{iid}.pkl"
    if not os.path.exists(pkl_path):
        print(f"[ERROR] graph pkl not found: {pkl_path}")
        return

    G = pickle.load(open(pkl_path, "rb"))
    from dependency_graph import RepoEntitySearcher
    from dependency_graph.build_graph import NODE_TYPE_FILE
    searcher = RepoEntitySearcher(G)
    all_files = searcher.get_all_nodes_by_type(NODE_TYPE_FILE)
    valid_files = [f['name'] for f in all_files]

    print(f"valid_files sample (first 10): {valid_files[:10]}")
    valid_top_folders = list({fn.split('/')[0] for fn in valid_files})
    print(f"valid_top_folders: {valid_top_folders}")

    for si, raw in enumerate(target["raw_output_loc"]):
        print(f"\n--- sample {si} ---")
        code_blocks = re.findall(r'```[^\n]*\n(.*?)```', raw, re.DOTALL)
        if code_blocks:
            text = '\n'.join(code_blocks)
            print(f"backtick blocks found: {len(code_blocks)}")
        else:
            text = raw.strip('` \n')
            print("no backtick blocks, using raw text")

        for line in text.splitlines():
            line = line.strip().strip(':').strip()
            if not line.endswith('.py'):
                continue
            pattern = r'[\w\./-]+\.py'
            m = re.search(pattern, line)
            if not m:
                print(f"  [no regex match] {line!r}")
                continue
            matched_fp = m.group(0)
            # check if any valid_top_folder matches
            hit_folder = None
            for folder in valid_top_folders:
                if f'{folder}/' in matched_fp:
                    hit_folder = folder
                    break
            if hit_folder is None:
                print(f"  [no folder match] {matched_fp!r}  (valid: {valid_top_folders})")
            else:
                start = matched_fp.index(f'{hit_folder}/')
                extracted = matched_fp[start:]
                in_valid = extracted in valid_files
                print(f"  [extracted] {extracted!r}  in_valid_files={in_valid}")


# ---------------------------------------------------------------------------
# main reparse logic
# ---------------------------------------------------------------------------

def reparse(input_file, inplace=False, lite=False):
    records = load_jsonl(input_file)

    empty_ids = [r["instance_id"] for r in records if is_empty(r)]
    mode_label = "lite (file-path only, no graph)" if lite else "full (with graph index)"
    print(f"Mode           : {mode_label}")
    print(f"Total records  : {len(records)}")
    print(f"Empty results  : {len(empty_ids)}")
    print(f"Already filled : {len(records) - len(empty_ids)}")

    if not empty_ids:
        print("Nothing to re-parse.")
        return

    recovered = 0
    still_empty = 0

    for rec in tqdm(records, desc="Re-parsing"):
        if not is_empty(rec):
            continue

        instance_id = rec["instance_id"]
        raw_outputs = rec.get("raw_output_loc", [])
        if not raw_outputs:
            still_empty += 1
            continue

        try:
            if lite:
                all_found_files, all_found_modules, all_found_entities = lite_parse(raw_outputs)
            else:
                all_found_files, all_found_modules, all_found_entities = full_parse(instance_id, raw_outputs)
        except Exception as e:
            tqdm.write(f"[WARN] {instance_id}: {e}")
            still_empty += 1
            continue

        rec["found_files"] = all_found_files
        rec["found_modules"] = all_found_modules
        rec["found_entities"] = all_found_entities

        if not all(len(x) == 0 for x in all_found_files):
            recovered += 1
        else:
            still_empty += 1

    print(f"\nRecovered      : {recovered}")
    print(f"Still empty    : {still_empty}")

    if inplace:
        backup = input_file + ".bak"
        shutil.copy2(input_file, backup)
        print(f"Backup saved to {backup}")
        write_jsonl(records, input_file)
        print(f"Updated in-place: {input_file}")
    else:
        output_file = input_file.replace(".jsonl", "_reparsed.jsonl")
        write_jsonl(records, output_file)
        print(f"Saved to {output_file}")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", type=str, required=True,
                        help="Path to loc_outputs.jsonl")
    parser.add_argument("--lite", action="store_true",
                        help="Graph-free mode: extract file paths only (no module/entity resolution)")
    parser.add_argument("--inplace", action="store_true",
                        help="Overwrite the input file (a .bak backup is created automatically)")
    parser.add_argument("--debug", action="store_true",
                        help="Trace why full mode fails for the first empty instance")
    parser.add_argument("--debug_id", type=str, default=None,
                        help="Specific instance_id to debug (used with --debug)")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"File not found: {args.input_file}")
        return

    if args.debug:
        debug_one(args.input_file, args.debug_id)
        return

    reparse(args.input_file, inplace=args.inplace, lite=args.lite)


if __name__ == "__main__":
    main()
