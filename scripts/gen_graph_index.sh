export PYTHONPATH=$PYTHONPATH:$(pwd)

# # generate graph index for SWE-bench_Lite
# python dependency_graph/batch_build_graph.py \
#         --dataset 'czlll/SWE-bench_Lite' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 32 \
#         --download_repo

# generate graph index for SWE-bench_Lite
python dependency_graph/batch_build_graph.py \
        --dataset 'SWE-bench/SWE-bench_Lite' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo


# # generate graph index SWE-bench_Verified
# python dependency_graph/batch_build_graph.py \
#         --dataset 'SWE-bench/SWE-bench_Verified' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

# # generate graph index for SWE-bench_Verified
# python dependency_graph/batch_build_graph.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'lite' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo