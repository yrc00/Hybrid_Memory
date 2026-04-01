export PYTHONPATH=$PYTHONPATH:$(pwd)

# python build_bm25_index.py \
#         --dataset 'czlll/SWE-bench_Lite' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 32 \
#         --download_repo

python build_bm25_index.py \
        --dataset 'SWE-bench/SWE-bench_Lite' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo

# python build_bm25_index.py \
#         --dataset 'SWE-bench/SWE-bench_Verified' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

# python build_bm25_index.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo