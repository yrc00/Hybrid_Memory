<<<<<<< HEAD

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
=======
#!/bin/bash
# Merge reparsed loc_outputs into merged_loc_outputs_reparsed_mrr.jsonl
#
# Usage:
#   bash scripts/merge_reparsed.sh <output_folder> [ranking_method]
#
# Examples:
#   bash scripts/merge_reparsed.sh ./results/qwen7b_ext_swe-bench/SWE-bench-Live/location
#   bash scripts/merge_reparsed.sh ./results/qwen7b_ext_swe-bench/SWE-bench-Live/location majority

export PYTHONPATH=$PYTHONPATH:$(pwd)

OUTPUT_FOLDER=${1:?"Usage: $0 <output_folder> [ranking_method]"}
RANKING_METHOD=${2:-"mrr"}

INPUT_FILE="$OUTPUT_FOLDER/loc_outputs_reparsed.jsonl"

if [ ! -f "$INPUT_FILE" ]; then
    echo "ERROR: $INPUT_FILE not found."
    echo "Run reparse_outputs.py --lite first to generate it."
    exit 1
fi

echo "Output folder  : $OUTPUT_FOLDER"
echo "Input file     : $INPUT_FILE"
echo "Ranking method : $RANKING_METHOD"

python auto_search_main.py \
    --merge \
    --output_folder "$OUTPUT_FOLDER" \
    --output_file "$INPUT_FILE" \
    --ranking_method "$RANKING_METHOD"
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
