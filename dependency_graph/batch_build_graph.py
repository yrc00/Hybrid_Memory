import argparse
import json
import os
import pickle
import time
from pathlib import Path
import subprocess
import torch.multiprocessing as mp
import os.path as osp
from datasets import load_dataset
from dependency_graph.build_graph import build_graph, VERSION
from util.benchmark.setup_repo import setup_repo


def list_folders(path):
    return [p.name for p in Path(path).iterdir() if p.is_dir()]


def run(rank, repo_queue, repo_path, out_path,
<<<<<<< HEAD
        download_repo=False, instance_data=None, use_dataflow=False):
=======
        download_repo=False, instance_data=None):
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
    while True:
        try:
            repo_name = repo_queue.get_nowait()
        except Exception:
            # Queue is empty
            break

        output_file = f'{osp.join(out_path, repo_name)}.pkl'
<<<<<<< HEAD
        output_file_df = f'{osp.join(out_path, repo_name)}_df.pkl'

        base_exists = osp.exists(output_file)
        df_exists = osp.exists(output_file_df)

        if base_exists and (not use_dataflow or df_exists):
=======
        if osp.exists(output_file):
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
            print(f'[{rank}] {repo_name} already processed, skipping.')
            continue

        if download_repo:
            # get process specific base dir
            repo_base_dir = str(osp.join(repo_path, str(rank)))
            os.makedirs(repo_base_dir, exist_ok=True)
            # clone and check actual repo
            try:
<<<<<<< HEAD
                repo_dir = setup_repo(instance_data=instance_data[repo_name],
                                      repo_base_dir=repo_base_dir,
=======
                repo_dir = setup_repo(instance_data=instance_data[repo_name], 
                                      repo_base_dir=repo_base_dir, 
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
                                      dataset=None)
            except subprocess.CalledProcessError as e:
                print(f'[{rank}] Error checkout commit {repo_name}: {e}')
                continue
        else:
            repo_dir = osp.join(repo_path, repo_name)

        print(f'[{rank}] Start process {repo_name}')
        try:
<<<<<<< HEAD
            if not base_exists:
                G = build_graph(repo_dir, global_import=True)
                with open(output_file, 'wb') as f:
                    pickle.dump(G, f)
                print(f'[{rank}] Processed {repo_name}')

            if use_dataflow and not df_exists:
                G_df = build_graph(repo_dir, global_import=True, use_dataflow=True)
                with open(output_file_df, 'wb') as f:
                    pickle.dump(G_df, f)
                print(f'[{rank}] Processed {repo_name} (hybrid memory)')
=======
            G = build_graph(repo_dir, global_import=True)
            with open(output_file, 'wb') as f:
                pickle.dump(G, f)
            print(f'[{rank}] Processed {repo_name}')
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
        except Exception as e:
            print(f'[{rank}] Error processing {repo_name}: {e}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="czlll/SWE-bench_Lite")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument('--num_processes', type=int, default=30)
    parser.add_argument('--download_repo', action='store_true', 
                        help='Whether to download the codebase to `repo_path` before indexing.')
    parser.add_argument('--repo_path', type=str, default='playground/build_graph', 
                        help='The directory where you plan to pull or have already pulled the codebase.')
    parser.add_argument('--index_dir', type=str, default='index_data', 
                        help='The base directory where the generated graph index will be saved.')
<<<<<<< HEAD
    parser.add_argument('--instance_id_path', type=str, default='',
                        help='Path to a file containing a list of selected instance IDs.')
    parser.add_argument('--use_dataflow', action='store_true',
                        help='Also generate _df.pkl with hybrid memory edges (exception_boundary, value_transform, enriched inherit/invoke).')
=======
    parser.add_argument('--instance_id_path', type=str, default='', 
                        help='Path to a file containing a list of selected instance IDs.')
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
    args = parser.parse_args()

    
    dataset_name = args.dataset.split('/')[-1]
    args.index_dir = f'{args.index_dir}/{dataset_name}/graph_index_{VERSION}/'
    os.makedirs(args.index_dir, exist_ok=True)
        
    # load selected repo instance id and instance_data
    if args.download_repo:
        selected_instance_data = {}
        bench_data = load_dataset(args.dataset, split=args.split)
        if args.instance_id_path and osp.exists(args.instance_id_path):
            with open(args.instance_id_path, 'r') as f:
                repo_folders = json.loads(f.read())
            for instance in bench_data:
                if instance['instance_id'] in repo_folders:
                    selected_instance_data[instance['instance_id']] = instance
        else:
            repo_folders = []
            for instance in bench_data:
                repo_folders.append(instance['instance_id'])
                selected_instance_data[instance['instance_id']] = instance
    else:
        if args.instance_id_path and osp.exists(args.instance_id_path):
            with open(args.instance_id_path, 'r') as f:
                repo_folders = json.loads(f.read())
        else:
            repo_folders = list_folders(args.repo_path)
        selected_instance_data = None

    os.makedirs(args.repo_path, exist_ok=True)

    # Create a shared queue and add repositories to it
    manager = mp.Manager()
    queue = manager.Queue()
    for repo in repo_folders:
        queue.put(repo)

    start_time = time.time()

    # Start multiprocessing with a global queue
    mp.spawn(
        run,
        nprocs=args.num_processes,
        args=(queue, args.repo_path, args.index_dir,
<<<<<<< HEAD
              args.download_repo, selected_instance_data, args.use_dataflow),
=======
              args.download_repo, selected_instance_data),
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
        join=True
    )

    end_time = time.time()
    print(f'Total Execution time = {end_time - start_time:.3f}s')
