#!/bin/bash
#
# vLLM Server Startup Script for AppenCorrect
# Optimized for g6.xlarge (NVIDIA L4, 24GB VRAM)
# Features: Continuous batching, model caching, Flash Attention 2
#

set -e

echo "=========================================="
echo "  AppenCorrect vLLM Server Startup"
echo "=========================================="
echo ""

# Configuration
MODEL_NAME="${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
HOST="${VLLM_HOST:-0.0.0.0}"
PORT="${VLLM_PORT:-8000}"
GPU_MEMORY_UTIL="${GPU_MEMORY_UTILIZATION:-0.85}"

# Model caching directory (reuses downloaded models)
export HF_HOME="${HF_HOME:-/data/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
export HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-$HF_HOME/datasets}"

# Create cache directories if they don't exist
mkdir -p "$HF_HOME/hub"
mkdir -p "$HF_HOME/datasets"

echo "Configuration:"
echo "  Model: $MODEL_NAME"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  GPU Memory Utilization: ${GPU_MEMORY_UTIL}%"
echo "  Model Cache: $HF_HOME"
echo ""

# Check GPU availability
echo "Checking GPU..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found. GPU required for vLLM."
    exit 1
fi

nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

# Check if model is already cached
if [ -d "$TRANSFORMERS_CACHE/models--${MODEL_NAME//\/--}" ]; then
    echo "✓ Model found in cache (no download needed)"
else
    echo "⚠ Model not cached - will download on first run (~14GB, 5-10 min)"
fi
echo ""

# Start vLLM server with concurrency optimization
echo "Starting vLLM server..."
echo "Features enabled:"
echo "  ✓ Continuous batching (handles multiple requests simultaneously)"
echo "  ✓ PagedAttention (memory-efficient KV cache)"
echo "  ✓ Flash Attention 2 (2-3x faster)"
echo "  ✓ Model caching (reuse across restarts)"
echo ""

exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_NAME" \
    --host "$HOST" \
    --port "$PORT" \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --max-num-batched-tokens 8192 \
    --max-num-seqs 64 \
    --disable-log-requests \
    --trust-remote-code \
    --enable-prefix-caching

# Concurrency Configuration Explained:
#
# --max-num-seqs 64
#   Maximum number of concurrent sequences (requests) to process
#   With g6.xlarge (24GB): 52-64 concurrent requests
#   Adjust based on GPU memory and average request size
#
# --max-num-batched-tokens 8192
#   Maximum tokens to batch together for inference
#   Higher = better throughput, but more memory
#   For grammar checking (avg 600 tokens/req): 8192 / 600 = ~13 parallel
#
# --gpu-memory-utilization 0.85
#   Use 85% of GPU memory (leaves 15% buffer)
#   24GB * 0.85 = 20.4GB for model + KV cache
#   Model: ~14GB, KV cache: ~6GB (for 52+ concurrent requests)
#
# --enable-prefix-caching
#   Cache common prompt prefixes (system messages)
#   Speeds up repeated queries with same instructions
#
# Result: GPU processes requests as they arrive, batching them dynamically
#         No idle time between requests - GPU stays busy!

