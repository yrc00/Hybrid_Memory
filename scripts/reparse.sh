# 결과를 새 파일(_reparsed.jsonl)로 저장 (안전)
export GRAPH_INDEX_DIR="./index_data/SWE-bench-Live/graph_index_v2.3"
python reparse_outputs.py \
    --input_file ./results/qwen7b_ext_swe-bench/SWE-bench-Live/location/loc_outputs.jsonl

# # 원본 파일을 덮어쓰기 (.bak 백업 자동 생성)
# python reparse_outputs.py \
#     --input_file ./results/qwen7b_ext_swe-bench/SWE-bench-Live/location/loc_outputs.jsonl \
#     --inplace
