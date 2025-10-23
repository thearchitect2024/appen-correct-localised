# AppenCorrect with TGI - Quick Start

## What is TGI?

**Text-Generation-Inference (TGI)** is Hugging Face's production-grade LLM inference server. It's written in Rust for performance and provides:

- ✅ **No pyairports issues** (unlike vLLM 0.5.5+)
- ✅ **Continuous batching** (like vLLM)
- ✅ **Flash Attention 2** support
- ✅ **Production stability**
- ✅ **Simple Docker deployment**

## Quick Start (Local Testing)

### 1. Install Docker

```bash
# Check Docker is installed
docker --version
```

### 2. Start TGI Server

```bash
# Create cache directory
mkdir -p ~/.huggingface

# Start TGI with Qwen 2.5 7B
docker run -d \
  --name tgi-server \
  --gpus all \
  -p 8080:80 \
  -v ~/.huggingface:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --max-concurrent-requests 8 \
  --max-input-length 512 \
  --max-total-tokens 1536 \
  --dtype auto
```

**First run:** Downloads 14GB model (5-10 min)  
**Subsequent runs:** Starts in 30-60 sec (cached)

### 3. Check TGI is Running

```bash
# Check health
curl http://localhost:8080/health

# Test inference
curl http://localhost:8080/generate \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"inputs": "Fix: I has a eror", "parameters": {"max_new_tokens": 100}}'
```

### 4. Install AppenCorrect Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set TGI URL

```bash
export TGI_URL="http://localhost:8080"
```

### 6. Start Flask API

```bash
python3 app.py
```

Flask will start on `http://localhost:5006`

### 7. Test the System

Open browser: `http://localhost:5006/`

Or use curl:
```bash
curl -X POST http://localhost:5006/demo/check \
  -H 'Content-Type: application/json' \
  -d '{"text": "I has a eror in grammer"}'
```

## SageMaker Testing

Use the included notebook: `sagemaker_tgi_test.ipynb`

1. Launch SageMaker notebook instance (g6.xlarge or ml.g5.xlarge)
2. Clone repo: `git clone https://github.com/thearchitect2024/appen-correct-localised.git`
3. Checkout tgi branch: `git checkout tgi`
4. Open `sagemaker_tgi_test.ipynb`
5. Run cells in order
6. Get ngrok URL for public testing

## Production (EKS)

Coming soon: TGI Helm chart for Kubernetes deployment

## Troubleshooting

### TGI not starting

Check logs:
```bash
docker logs tgi-server
```

### Out of memory

Reduce concurrent requests:
```bash
docker stop tgi-server
docker rm tgi-server

# Restart with lower concurrency
docker run -d \
  --name tgi-server \
  --gpus all \
  -p 8080:80 \
  -v ~/.huggingface:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --max-concurrent-requests 4 \
  --max-input-length 256 \
  --max-total-tokens 768
```

### Flask can't connect to TGI

Check TGI is listening:
```bash
curl http://localhost:8080/health
```

If not, check `docker ps` to see if container is running.

## Stopping Services

```bash
# Stop Flask
pkill -f app.py

# Stop TGI
docker stop tgi-server
docker rm tgi-server
```

## Cost Comparison

| Setup | Monthly Cost | Latency | Rate Limits |
|-------|-------------|---------|-------------|
| **Gemini API (main)** | $3,000-5,000 | 200-500ms | 500 QPM |
| **TGI Local (tgi)** | $300-400 (GPU only) | <50ms | Unlimited |

**Savings: 90%+ cost reduction** 💰

