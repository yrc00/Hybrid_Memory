export PYTHONPATH=$PYTHONPATH:$(pwd)

# Lite
python util/benchmark/gen_oracle_locations.py \
    --dataset SWE-bench/SWE-bench_Lite \
    --split test \
    --output_dir evaluation/gt_location \
    --repo_base_dir playground/repo_base \
    --max_edit_file_num 5

# Verified
python util/benchmark/gen_oracle_locations.py \
    --dataset SWE-bench/SWE-bench_Verified \
    --split test \
    --output_dir evaluation/gt_location \
    --repo_base_dir playground/repo_base \
    --max_edit_file_num 5

# SWE-bench-Live (lite)
python util/benchmark/gen_oracle_locations.py \
    --dataset SWE-bench-Live \
    --split lite \
    --local_data_file dataset_cache/SWE-bench-Live/lite/instances.jsonl \
    --output_dir evaluation/gt_location \
    --repo_base_dir playground/repo_base \
    --max_edit_file_num 5
