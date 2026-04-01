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
