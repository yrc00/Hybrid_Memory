# lite 모드 (graph 없음, 파일 경로만 추출) — 현재 환경에서 사용 가능
python reparse_outputs.py \
    --input_file ./results/qwen7b_ext_swe-bench/SWE-bench_Verified/location/loc_outputs.jsonl \
    --lite

# # full 모드 (graph index 있을 때, module/entity까지 복구)
# export GRAPH_INDEX_DIR="./index_data/SWE-bench_Lite/graph_index_v2.3"
# python reparse_outputs.py \
#     --input_file ./results/qwen7b_ext_swe-bench/SWE-bench_Lite/location/loc_outputs.jsonl

# # 원본 덮어쓰기 (두 모드 모두 --inplace 가능)
# python reparse_outputs.py ... --lite --inplace