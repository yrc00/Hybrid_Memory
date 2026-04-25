
export OPENAI_API_KEY="dummy"
export OPENAI_API_BASE="http://localhost:8000/v1"

export PYTHONPATH=$PYTHONPATH:$(pwd)

# Lite
export GRAPH_INDEX_DIR='./index_data/SWE-bench_Lite/graph_index_v2.3'
export BM25_INDEX_DIR='./index_data/SWE-bench_Lite/BM25_index'
result_path='./results/qwen32b_swe-bench/SWE-bench_Lite'

echo $result_path
mkdir -p $result_path

python auto_search_main.py \
    --dataset 'SWE-bench/SWE-bench_Lite' \
    --split 'test' \
    --model 'openai/Qwen/Qwen2.5-Coder-32B-Instruct' \
    --merge \
    --output_folder $result_path/location \
    --eval_n_limit 300 \
    --num_processes 25 \
    --use_function_calling \
    --simple_desc \
    --output_file 'loc_outputs_reparsed.jsonl' \
    --merge_file 'merged_loc_outputs_reparsed.jsonl'\
    --ranking_method majority