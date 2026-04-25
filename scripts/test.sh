export OPENAI_API_KEY="dummy"
export OPENAI_API_BASE="http://localhost:8000/v1"
export PYTHONPATH=$PYTHONPATH:$(pwd)

# =============================================================================
# Quick single-benchmark test — Hybrid Memory (--use_dataflow)
# Requires _df.pkl graph index; see gen_graph_index.sh (--use_dataflow section).
# =============================================================================

# export GRAPH_INDEX_DIR='./index_data/SWE-bench_Lite/graph_index_v3.0'
# export BM25_INDEX_DIR='./index_data/SWE-bench_Lite/BM25_index'
# result_path='./results/test_hybrid_memory/SWE-bench_Lite'
# mkdir -p $result_path
#
# python auto_search_main.py \
#     --dataset 'SWE-bench/SWE-bench_Lite' \
#     --split 'test' \
#     --model 'openai/zai-org/GLM-Z1-9B-0414' \
#     --localize \
#     --merge \
#     --output_folder $result_path/location \
#     --eval_n_limit 50 \
#     --num_processes 8 \
#     --use_function_calling \
#     --simple_desc \
#     --use_dataflow

# export GRAPH_INDEX_DIR='./index_data/SWE-bench_Lite/graph_index_v2.3'
# export BM25_INDEX_DIR='./index_data/SWE-bench_Lite/BM25_index'

# result_path='./results/qwen7b_swe-bench/SWE-bench_Lite'
# echo $result_path
# mkdir -p $result_path

# python auto_search_main.py \
#     --dataset 'SWE-bench/SWE-bench_Lite' \
#     --split 'lite' \
#     --model 'openai/Qwen/Qwen2.5-Coder-7B-Instruct' \
#     --localize \
#     --merge \
#     --output_folder $result_path/location \
#     --eval_n_limit 300 \
#     --num_processes 25 \
#     --use_function_calling \
#     --simple_desc

# declare -A BENCHMARKS=(
#     ["SWE-bench_Lite"]="SWE-bench/SWE-bench_Lite"
#     ["SWE-bench_Verified"]="SWE-bench/SWE-bench_Verified"
#     ["SWE-bench-Live"]="SWE-bench-Live/SWE-bench-Live"
# )

# declare -A SPLITS=(
#     ["SWE-bench_Lite"]="test"
#     ["SWE-bench_Verified"]="test"
#     ["SWE-bench-Live"]="lite"
# )

# for BENCH_NAME in "SWE-bench_Lite" "SWE-bench_Verified" "SWE-bench-Live"; do
#     DATASET="${BENCHMARKS[$BENCH_NAME]}"
#     SPLIT="${SPLITS[$BENCH_NAME]}"
#     export GRAPH_INDEX_DIR="./index_data/${BENCH_NAME}/graph_index_v2.3"
#     export BM25_INDEX_DIR="./index_data/${BENCH_NAME}/BM25_index"
#     result_path="./results/qwen7b_swe-bench/${BENCH_NAME}"

#     echo "========================================="
#     echo "Running benchmark: $BENCH_NAME"
#     echo "Dataset: $DATASET"
#     echo "Split: $SPLIT"
#     echo "Result path: $result_path"
#     echo "========================================="

#     mkdir -p $result_path

#     python auto_search_main.py \
#         --dataset "$DATASET" \
#         --split "$SPLIT" \
#         --model 'openai/Qwen/Qwen3-Coder-30B-A3B-Instruct' \
#         --localize \
#         --merge \
#         --output_folder "$result_path/location" \
#         --eval_n_limit 300 \
#         --num_processes 25 \
#         --use_function_calling \
#         --simple_desc \
#         # --ranking_method majority

#     if [ $? -ne 0 ]; then
#         echo "ERROR: $BENCH_NAME failed. Continuing to next benchmark..."
#     else
#         echo "SUCCESS: $BENCH_NAME completed."
#     fi
# done

# echo "All benchmarks finished."