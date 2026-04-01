export PYTHONPATH=$PYTHONPATH:$(pwd)

# Lite
python util/benchmark/gen_oracle_locations.py \
    --dataset SWE-bench/SWE-bench_Lite \
    --split test \
    --output_dir evaluation/gt_location \
    --repo_base_dir playground/repo_base

# Verified
python util/benchmark/gen_oracle_locations.py \
    --dataset SWE-bench/SWE-bench_Verified \
    --split test \
    --output_dir evaluation/gt_location \
    --repo_base_dir playground/repo_base
