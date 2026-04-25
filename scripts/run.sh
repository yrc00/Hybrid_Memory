# tmux new-session -d -s hybridmem && \
# tmux send-keys -t hybridmem 'bash scripts/run.sh && echo "완료 $(date)" > status.log || echo "실패 $(date)" > status.log; exit' Enter


export OPENAI_API_KEY="dummy"
export OPENAI_API_BASE="http://localhost:8000/v1"
export PYTHONPATH=$PYTHONPATH:$(pwd)

declare -A BENCHMARKS=(
    ["SWE-bench_Lite"]="SWE-bench/SWE-bench_Lite"
    ["SWE-bench_Verified"]="SWE-bench/SWE-bench_Verified"
    ["SWE-bench-Live"]="SWE-bench-Live/SWE-bench-Live"
)

declare -A SPLITS=(
    ["SWE-bench_Lite"]="test"
    ["SWE-bench_Verified"]="test"
    ["SWE-bench-Live"]="lite"
)

# =============================================================================
# Base mode  (contains / invokes / imports / inherits edges)
# Requires: index_data/<bench>/graph_index_v3.0/<instance_id>.pkl
# =============================================================================

for BENCH_NAME in "SWE-bench_Lite" "SWE-bench_Verified" "SWE-bench-Live"; do
    DATASET="${BENCHMARKS[$BENCH_NAME]}"
    SPLIT="${SPLITS[$BENCH_NAME]}"
    export GRAPH_INDEX_DIR="./index_data/${BENCH_NAME}/graph_index_v3.0"
    export BM25_INDEX_DIR="./index_data/${BENCH_NAME}/BM25_index"
    result_path="./results/GLM-Z1-9B_swe-bench-analysis/${BENCH_NAME}"

    echo "========================================="
    echo "Running benchmark: $BENCH_NAME"
    echo "Dataset: $DATASET"
    echo "Split: $SPLIT"
    echo "Result path: $result_path"
    echo "========================================="

    mkdir -p $result_path

    python auto_search_main.py \
        --dataset "$DATASET" \
        --split "$SPLIT" \
        --model 'openai/zai-org/GLM-Z1-9B-0414' \
        --localize \
        --merge \
        --analyze \
        --output_folder "$result_path/location" \
        --num_processes 15 \
        --use_function_calling \
        --simple_desc \
        --ranking_method majority

    if [ $? -ne 0 ]; then
        echo "ERROR: $BENCH_NAME failed. Continuing to next benchmark..."
    else
        echo "SUCCESS: $BENCH_NAME completed."
    fi
done

echo "All benchmarks finished."


# =============================================================================
# Hybrid Memory mode  (--use_dataflow)
# Adds exception_boundary / value_transform edges and enriched
# inherits / invokes meta to the graph.
#
# Requires:
#   - index_data/<bench>/graph_index_v3.0/<instance_id>_df.pkl
#     → build with: bash scripts/gen_graph_index.sh  (--use_dataflow section)
#   - vLLM server running (for edge descriptions during inference, optional)
#     → bash scripts/vllm.sh
#
# Additional env vars for edge-description generation (used at graph-build time,
# not inference time — set them before gen_graph_index.sh if you want descriptions):
#   export VLLM_BASE_URL="http://localhost:8000/v1"   # default
#   export VLLM_MODEL="zai-org/GLM-Z1-9B-0414"       # auto-detected if unset
# =============================================================================

# for BENCH_NAME in "SWE-bench_Lite" "SWE-bench_Verified" "SWE-bench-Live"; do
#     DATASET="${BENCHMARKS[$BENCH_NAME]}"
#     SPLIT="${SPLITS[$BENCH_NAME]}"
#     export GRAPH_INDEX_DIR="./index_data/${BENCH_NAME}/graph_index_v3.0"
#     export BM25_INDEX_DIR="./index_data/${BENCH_NAME}/BM25_index"
#     result_path="./results/GLM-Z1-9B_hybrid-memory/${BENCH_NAME}"
#
#     echo "========================================="
#     echo "Running Hybrid Memory: $BENCH_NAME"
#     echo "Dataset: $DATASET | Split: $SPLIT"
#     echo "Result path: $result_path"
#     echo "========================================="
#
#     mkdir -p $result_path
#
#     python auto_search_main.py \
#         --dataset "$DATASET" \
#         --split "$SPLIT" \
#         --model 'openai/zai-org/GLM-Z1-9B-0414' \
#         --localize \
#         --merge \
#         --analyze \
#         --output_folder "$result_path/location" \
#         --num_processes 15 \
#         --use_function_calling \
#         --simple_desc \
#         --ranking_method majority \
#         --use_dataflow
#
#     if [ $? -ne 0 ]; then
#         echo "ERROR: $BENCH_NAME failed. Continuing to next benchmark..."
#     else
#         echo "SUCCESS: $BENCH_NAME completed."
#     fi
# done
#
# echo "All Hybrid Memory benchmarks finished."


# export OPENAI_API_KEY="dummy"
# export OPENAI_API_BASE="http://localhost:8000/v1"

# export PYTHONPATH=$PYTHONPATH:$(pwd)

# # Lite
# # export GRAPH_INDEX_DIR='./index_data/SWE-bench-Live/graph_index_v2.3'
# # export BM25_INDEX_DIR='./index_data/SWE-bench-Live/BM25_index'
# # result_path='./results/qwen7b-cl_swe-bench/SWE-bench-Live'

# # Verified
# export GRAPH_INDEX_DIR='./index_data/SWE-bench_Verified/graph_index_v2.3'
# export BM25_INDEX_DIR='./index_data/SWE-bench_Verified/BM25_index'
# result_path='./results/qwen7b_ext_swe-bench/SWE-bench_Verified'

# # # Live
# # export GRAPH_INDEX_DIR='./index_data/SWE-bench-Live/graph_index_v2.3'
# # export BM25_INDEX_DIR='./index_data/SWE-bench-Live/BM25_index'
# # result_path='./results/qwen7b-cl_swe-bench/SWE-bench-Live'


# echo $result_path
# mkdir -p $result_path

# # python auto_search_main.py \
# #     --dataset 'SWE-bench/SWE-bench_Verified' \
# #     --split 'test' \
# #     --model 'openai/Qwen/Qwen2.5-Coder-7B-Instruct' \
# #     --localize \
# #     --merge \
# #     --output_folder $result_path/location \
# #     --num_processes 25 \
# #     --use_function_calling \
# #     --simple_desc \
# #     --ranking_method majority

# python auto_search_main.py \
#     --dataset 'SWE-bench/SWE-bench_Verified' \
#     --split 'test' \
#     --model 'openai/Qwen/Qwen2.5-Coder-7B-Instruct' \
#     --merge \
#     --output_folder $result_path/location \
#     --num_processes 25 \
#     --use_function_calling \
#     --simple_desc \