export PYTHONPATH=$PYTHONPATH:$(pwd)

# NOTE: The BM25 index is shared between base mode and Hybrid Memory
# (--use_dataflow) mode.  Run this script once; no separate index is needed
# for the _df graph.

python build_bm25_index.py \
        --dataset 'SWE-bench/SWE-bench_Lite' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo

# # SWE-bench_Verified
# python build_bm25_index.py \
#         --dataset 'SWE-bench/SWE-bench_Verified' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

# # SWE-bench-Live
# python build_bm25_index.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'lite' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo