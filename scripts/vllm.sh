# python -m vllm.entrypoints.openai.api_server \
#   --model ./models/baseline/Qwen2.5-Coder-7B \
#   --served-model-name Qwen/Qwen2.5-Coder-7B-Instruct \
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

python -m vllm.entrypoints.openai.api_server \
  --model ./models/baseline/Qwen3-Coder-30B \
  --served-model-name Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.88