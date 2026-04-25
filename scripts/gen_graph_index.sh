export PYTHONPATH=$PYTHONPATH:$(pwd)

<<<<<<< HEAD
# =============================================================================
# Base graph index (contains / invokes / imports / inherits edges only)
# Graph files: index_data/<bench>/graph_index_v3.0/<instance_id>.pkl
# =============================================================================

# # generate base graph index for SWE-bench_Lite
# python dependency_graph/batch_build_graph.py \
#         --dataset 'SWE-bench/SWE-bench_Lite' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

# # generate base graph index for SWE-bench_Verified
=======
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
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
# python dependency_graph/batch_build_graph.py \
#         --dataset 'SWE-bench/SWE-bench_Verified' \
#         --split 'test' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
#         --download_repo

<<<<<<< HEAD
# # generate base graph index for SWE-bench-Live
=======
# # generate graph index for SWE-bench_Verified
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
# python dependency_graph/batch_build_graph.py \
#         --dataset 'SWE-bench-Live/SWE-bench-Live' \
#         --split 'lite' \
#         --repo_path playground/build_graph \
#         --num_processes 30 \
<<<<<<< HEAD
#         --download_repo


# =============================================================================
# Hybrid Memory graph index (--use_dataflow)
# Adds exception_boundary / value_transform edges and enriches
# inherits / invokes edges with meta information.
# Graph files: index_data/<bench>/graph_index_v3.0/<instance_id>_df.pkl
#
# Optional: start vLLM *before* running these commands so that edge
# descriptions are generated automatically.  If vLLM is not reachable,
# descriptions are simply omitted and the build continues normally.
#
#   export VLLM_BASE_URL="http://localhost:8000/v1"   # default
#   export VLLM_MODEL="zai-org/GLM-Z1-9B-0414"       # auto-detected if unset
#   bash scripts/vllm.sh &   # or start in a separate tmux pane
# =============================================================================

# generate Hybrid Memory graph index for SWE-bench_Lite
python dependency_graph/batch_build_graph.py \
        --dataset 'SWE-bench/SWE-bench_Lite' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo \
        --use_dataflow

# generate Hybrid Memory graph index for SWE-bench_Verified
python dependency_graph/batch_build_graph.py \
        --dataset 'SWE-bench/SWE-bench_Verified' \
        --split 'test' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo \
        --use_dataflow

# generate Hybrid Memory graph index for SWE-bench-Live
python dependency_graph/batch_build_graph.py \
        --dataset 'SWE-bench-Live/SWE-bench-Live' \
        --split 'lite' \
        --repo_path playground/build_graph \
        --num_processes 30 \
        --download_repo \
        --use_dataflow
=======
#         --download_repo
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
