export PYTHONPATH=$PYTHONPATH:$(pwd)

<<<<<<< HEAD
# NOTE: The BM25 index is shared between base mode and Hybrid Memory
# (--use_dataflow) mode.  Run this script once; no separate index is needed
# for the _df graph.
=======
# python build_bm25_index.py \
#         --dataset 'czlll/SWE-bench_Lite' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 32 \
#         --download_repo
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e

python build_bm25_index.py \
        --dataset 'SWE-bench/SWE-bench_Lite' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo

<<<<<<< HEAD
# # SWE-bench_Verified
=======
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
# python build_bm25_index.py \
#         --dataset 'SWE-bench/SWE-bench_Verified' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

<<<<<<< HEAD
# # SWE-bench-Live
# python build_bm25_index.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'lite' \
=======
# python build_bm25_index.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'test' \
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo