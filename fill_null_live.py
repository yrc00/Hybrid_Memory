"""Fill null file_changes entries in SWE-bench-Live gt_location.jsonl."""
import os, sys, json, re, subprocess, shutil
from collections import defaultdict

sys.path.insert(0, 'c:/Users/cyeli/workspace/HYBRID_MEMORY')
from util.benchmark.gen_oracle_locations import extract_module_from_patch

PLAYGROUND = 'c:/Users/cyeli/workspace/HYBRID_MEMORY/playground/live'
JSONL_PATH = 'c:/Users/cyeli/workspace/HYBRID_MEMORY/evaluation/gt_location/SWE-bench-Live/lite/gt_location.jsonl'
os.makedirs(PLAYGROUND, exist_ok=True)


def git(args, cwd=None, check=True):
    result = subprocess.run(
        ['git'] + args, cwd=cwd, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, args, result.stderr)
    return result


def get_repo_dir(repo):
    return os.path.join(PLAYGROUND, repo.replace('/', '__'))


def clone_repo(repo):
    repo_dir = get_repo_dir(repo)
    if os.path.exists(os.path.join(repo_dir, '.git')):
        print(f"  [cached] {repo}")
        return repo_dir
    print(f"  [clone]  {repo}")
    url = f"https://github.com/{repo}.git"
    git(['clone', '--filter=blob:none', '--no-single-branch', url, repo_dir])
    return repo_dir


def ensure_commit(repo_dir, commit):
    """Fetch and checkout commit if not already available."""
    r = git(['cat-file', '-t', commit], cwd=repo_dir, check=False)
    if r.returncode != 0:
        git(['fetch', '--depth=1', 'origin', commit], cwd=repo_dir)


def get_worktree_path(repo_dir, commit):
    return os.path.join(repo_dir + '_wt', commit[:12])


def setup_worktree(repo_dir, commit):
    wt_path = get_worktree_path(repo_dir, commit)
    if os.path.exists(os.path.join(wt_path, '.git')):
        return wt_path
    ensure_commit(repo_dir, commit)
    os.makedirs(os.path.dirname(wt_path), exist_ok=True)
    git(['worktree', 'add', '--detach', wt_path, commit], cwd=repo_dir)
    return wt_path


def cleanup_worktree(repo_dir, commit):
    wt_path = get_worktree_path(repo_dir, commit)
    if os.path.exists(wt_path):
        shutil.rmtree(wt_path)
        git(['worktree', 'prune'], cwd=repo_dir, check=False)


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f]


def save_jsonl(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        for d in lines:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')


def main():
    lines = load_jsonl(JSONL_PATH)
    nulls = [d for d in lines if d['file_changes'] is None]

    # Filter to only extractable (has .py files)
    extractable = []
    for d in nulls:
        files = re.findall(r'diff --git a/(.+) b/', d.get('patch', ''))
        if any(f.endswith('.py') for f in files):
            extractable.append(d)

    print(f"Extractable null instances: {len(extractable)}")

    # Group by repo
    by_repo = defaultdict(list)
    for d in extractable:
        by_repo[d['repo']].append(d)

    results = {}
    errors = {}

    for repo, instances in sorted(by_repo.items()):
        print(f"\n[{repo}] {len(instances)} instances")
        try:
            repo_dir = clone_repo(repo)
        except Exception as e:
            print(f"  CLONE FAILED: {e}")
            for inst in instances:
                errors[inst['instance_id']] = str(e)
            continue

        # Group by commit
        by_commit = defaultdict(list)
        for inst in instances:
            by_commit[inst['base_commit']].append(inst)

        for commit, commit_instances in by_commit.items():
            print(f"  commit={commit[:10]}, instances={[d['instance_id'].split('__')[-1] for d in commit_instances]}")
            wt_path = None
            try:
                wt_path = setup_worktree(repo_dir, commit)
                for inst in commit_instances:
                    try:
                        fc = extract_module_from_patch(inst, wt_path, max_edit_file_num=100)
                        if fc:
                            results[inst['instance_id']] = fc
                            print(f"    OK  {inst['instance_id']}: {len(fc)} files")
                        else:
                            print(f"    EMPTY {inst['instance_id']}: no extractable modules")
                    except Exception as e:
                        errors[inst['instance_id']] = str(e)
                        print(f"    ERR {inst['instance_id']}: {e}")
            except Exception as e:
                print(f"  WORKTREE FAILED ({commit[:10]}): {e}")
                for inst in commit_instances:
                    errors[inst['instance_id']] = str(e)
            finally:
                if wt_path:
                    try:
                        cleanup_worktree(repo_dir, commit)
                    except Exception:
                        pass

    # Update JSONL
    updated = 0
    for d in lines:
        if d['instance_id'] in results:
            d['file_changes'] = results[d['instance_id']]
            updated += 1

    save_jsonl(JSONL_PATH, lines)

    remaining_null = sum(1 for d in lines if d['file_changes'] is None)
    print(f"\n=== Done ===")
    print(f"Updated: {updated}, Errors: {len(errors)}, Remaining null: {remaining_null}")
    if errors:
        print("Errors:")
        for iid, err in errors.items():
            print(f"  {iid}: {err[:100]}")


if __name__ == '__main__':
    main()
