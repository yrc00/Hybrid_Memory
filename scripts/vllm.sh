<<<<<<< HEAD
# ss -tulpn | 8000
# CUDA_VISIBLE_DEVICES=2 bash scripts/vllm.sh
# tmux new-session -d -s vllm && \
# tmux send-keys -t vllm "conda activate hybridmem && CUDA_VISIBLE_DEVICES=2 bash scripts/vllm.sh" Enter
# tmux kill-session -t vllm

# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-7B-CL \
#   --served-model-name Qwen/Qwen2.5-Coder-7B-CL \
=======
# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-7B \
#   --served-model-name Qwen/Qwen2.5-Coder-7B-Instruct \
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
#   --host 0.0.0.0 \
#   --port 8000 \
#   --tensor-parallel-size 1 \
#   --max-model-len 131072

# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-7B \
#   --served-model-name Qwen/Qwen2.5-Coder-7B-Instruct \
#   --host 0.0.0.0 \
#   --port 8000 \
#   --tensor-parallel-size 1 \
#   --max-model-len 32768

# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-7B \
#   --served-model-name Qwen/Qwen2.5-Coder-7B-Instruct \
#   --host 0.0.0.0 \
#   --port 8000 \
#   --tensor-parallel-size 1 \
#   --max-model-len 131072 \
#   --hf-overrides '{"max_position_embeddings": 131072, "rope_scaling": {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}}'

# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-32B \
#   --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct \
#   --host 0.0.0.0 \
#   --port 8000 \
#   --tensor-parallel-size 2 \
#   --max-model-len 32768 \
#   --max-num-seqs 64 \            # 기본값 256 → 워밍업 메모리 압력 감소
#   --gpu-memory-utilization 0.85  # 기본값 0.90

<<<<<<< HEAD
# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen3-Coder-30B \
#   --served-model-name Qwen/Qwen3-Coder-30B-A3B-Instruct \
#   --host 0.0.0.0 \
#   --port 8000 \
#   --tensor-parallel-size 2 \
#   --max-model-len 32768 \
#   --max-num-seqs 32 \
#   --gpu-memory-utilization 0.88

python -m vllm.entrypoints.openai.api_server \
  --model ./models/baseline/GLM-Z1-9B \
  --served-model-name zai-org/GLM-Z1-9B-0414 \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1 \
  --max-model-len 32768
=======
python -m vllm.entrypoints.openai.api_server \
  --model ./models/baseline/Qwen3-Coder-30B \
  --served-model-name Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.88
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
