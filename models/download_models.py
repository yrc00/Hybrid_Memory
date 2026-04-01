from huggingface_hub import snapshot_download

# # finetuned Qwen2.5 7B
# snapshot_download(
#     repo_id="czlll/Qwen2.5-Coder-7B-CL",
#     local_dir="./models/baseline/Qwen2.5-Coder-7B-CL"
# )

# # finetuned Qwen2.5 32B
# snapshot_download(
#     repo_id="czlll/Qwen2.5-Coder-7B-CL",
#     local_dir="./models/baseline/Qwen2.5-Coder-32B-CL"
# )

# # Qwen2.5 7B
# snapshot_download(
#     repo_id="Qwen/Qwen2.5-Coder-7B-Instruct",
#     local_dir="./models/baseline/Qwen2.5-Coder-7B"
# )

# Qwen2.5 32B
snapshot_download(
    repo_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    local_dir="./models/baseline/Qwen2.5-Coder-32B"
)

# # Qwen3 30B
# snapshot_download(
#     repo_id="Qwen/Qwen3-Coder-30B-A3B-Instruct",
#     local_dir="./models/baseline/Qwen3-Coder-30B"
# )
