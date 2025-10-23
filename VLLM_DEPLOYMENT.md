# vLLM Deployment Guide for AppenCorrect

This guide covers deploying AppenCorrect with local vLLM inference instead of the external Gemini API.

## Overview

**Before (Gemini API):**
```
User → Flask → Internet → Google Gemini API → Response
Cost: $3,000-5,000/month
Latency: 500-1000ms
Rate limits: Yes
```

**After (vLLM Local):**
```
User → Flask → Internal K8s → vLLM (GPU) → Response
Cost: $250-450/month
Latency: 1-3 seconds
Rate limits: None
Concurrency: 300+ users on 6 GPUs
```

---

## Key Features

### 1. **Continuous Batching** 
vLLM processes multiple requests simultaneously on the GPU, not one at a time:

```
Traditional:  Request1 → GPU → Done → Request2 → GPU → Done
              GPU Utilization: 30-40%

vLLM:         Request1 ─┐
              Request2 ─┤→ GPU (all together)
              Request3 ─┘
              GPU Utilization: 80-90%
```

### 2. **Model Caching**
Models are downloaded once and cached locally:
- First run: Downloads ~14GB (5-10 minutes)
- Subsequent runs: Loads from cache (30-60 seconds)
- Cache location: `$HF_HOME/hub` or `/data/huggingface/hub`

### 3. **Flash Attention 2**
Optimized attention mechanism:
- 2-3x faster inference
- 50% less memory usage
- Enables more concurrent requests

### 4. **PagedAttention**
Efficient KV cache management:
- Dynamic memory allocation
- Reduces memory fragmentation
- Handles variable-length sequences efficiently

---

## Architecture

### Production (EKS)

```
┌────────────────────────────────────────────┐
│  AWS Load Balancer                         │
└───────────────┬────────────────────────────┘
                ↓
┌────────────────────────────────────────────┐
│  Flask API Pods (CPU)                      │
│  ┌─────┬─────┬─────┬─────┐                │
│  │Pod 1│Pod 2│...  │Pod10│                │
│  └─────┴─────┴─────┴─────┘                │
│  KEDA Autoscaling: 5-20 pods              │
└───────────────┬────────────────────────────┘
                ↓ (internal ClusterIP)
┌────────────────────────────────────────────┐
│  vLLM Service                              │
└───────────────┬────────────────────────────┘
                ↓
┌────────────────────────────────────────────┐
│  vLLM Pods (GPU)                           │
│  ┌─────────┬─────────┬─────────┬─────────┐│
│  │GPU Pod 1│GPU Pod 2│GPU Pod 3│GPU Pod N││
│  │g6.xlarge│g6.xlarge│g6.xlarge│g6.xlarge││
│  │L4 24GB  │L4 24GB  │L4 24GB  │L4 24GB  ││
│  └─────────┴─────────┴─────────┴─────────┘│
│  KEDA Autoscaling: 1-6 pods               │
│  Karpenter: Spot instances, scale-to-zero │
└────────────────────────────────────────────┘
```

### Testing (SageMaker)

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       ↓ (internet)
┌──────────────┐
│    ngrok     │  Public tunnel
└──────┬───────┘
       ↓ (localhost)
┌───────────────────────────────────┐
│  SageMaker Notebook Instance      │
│  ml.g5.xlarge (A10G GPU, 24GB)    │
│                                   │
│  ┌─────────────┐  ┌─────────────┐│
│  │  Flask API  │→ │ vLLM Server ││
│  │  Port 5006  │  │  Port 8000  ││
│  └─────────────┘  └──────┬──────┘│
│                           ↓       │
│                      ┌────────┐  │
│                      │  GPU   │  │
│                      │  Qwen  │  │
│                      │  2.5-7B│  │
│                      └────────┘  │
└───────────────────────────────────┘
```

---

## Quickstart: SageMaker Testing

### Prerequisites
- SageMaker notebook instance: `ml.g5.xlarge` or `ml.g5.2xlarge`
- GPU with 24GB VRAM (A10G or L4)
- ngrok account (for public URL, optional)

### Step 1: Setup
```bash
# SSH into SageMaker notebook or use terminal
cd /home/ec2-user/SageMaker

# Download and run setup script
wget https://raw.githubusercontent.com/thearchitect2024/appen-correct-localised/vllm/setup_sagemaker_vllm.sh
chmod +x setup_sagemaker_vllm.sh
./setup_sagemaker_vllm.sh
```

This will:
- ✓ Install Flash Attention 2
- ✓ Install vLLM 0.6.3
- ✓ Clone repository (vllm branch)
- ✓ Configure model caching
- ✓ Setup environment

### Step 2: Start vLLM Server
```bash
cd /home/ec2-user/SageMaker/appen-correct-localised

# Set cache directory (persistent across restarts)
export HF_HOME=/home/ec2-user/SageMaker/.huggingface

# Start vLLM (first run downloads model, ~10 min)
./start_vllm_server.sh
```

**Expected output:**
```
Model: Qwen/Qwen2.5-7B-Instruct
Model Cache: /home/ec2-user/SageMaker/.huggingface/hub
⚠ Model not cached - will download on first run (~14GB, 5-10 min)
Starting vLLM server...
  ✓ Continuous batching (handles multiple requests simultaneously)
  ✓ PagedAttention (memory-efficient KV cache)
  ✓ Flash Attention 2 (2-3x faster)
  ✓ Model caching (reuse across restarts)
```

Wait for: `Application startup complete.` (takes 5-10 min first time)

### Step 3: Start Flask API (new terminal)
```bash
cd /home/ec2-user/SageMaker/appen-correct-localised
python3 app.py
```

**Expected output:**
```
✓ vLLM client initialized - URL: http://localhost:8000
✓ vLLM server connection successful
AppenCorrect Core initialized - API: vllm, Model: Qwen/Qwen2.5-7B-Instruct
Running on http://127.0.0.1:5006
```

### Step 4: Test Locally
```bash
# Health check
curl http://localhost:5006/health

# Test correction
curl -X POST http://localhost:5006/demo/check \
  -H "Content-Type: application/json" \
  -d '{"text": "I has a eror in grammer"}'
```

### Step 5: Create Public URL with ngrok (optional)
```bash
# Install ngrok
pip install pyngrok

# Get auth token from https://dashboard.ngrok.com
python -c "from pyngrok import ngrok; ngrok.set_auth_token('YOUR_TOKEN_HERE'); print(ngrok.connect(5006))"
```

Share the ngrok URL to test from anywhere!

### Step 6: Test Concurrency
```bash
# Run concurrency test
python3 test_vllm_concurrency.py
```

This will test:
- ✓ Multiple simultaneous requests
- ✓ GPU batching efficiency
- ✓ Response format validation
- ✓ Throughput measurement

---

## Configuration Parameters

### vLLM Server Settings

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `--max-num-seqs` | 64 | Max concurrent requests |
| `--max-num-batched-tokens` | 8192 | Max tokens per batch |
| `--gpu-memory-utilization` | 0.85 | Use 85% of GPU memory |
| `--enable-prefix-caching` | true | Cache common prompts |
| `--max-model-len` | 4096 | Max sequence length |

### Capacity Planning

**Single g6.xlarge (L4 24GB VRAM):**
- Model size: ~14GB
- KV cache: ~9.5GB
- **Concurrent requests: 52-64**
- **Throughput: 15-20 req/sec**
- **Users supported: ~100-150** (normal usage)

**6 g6.xlarge GPUs:**
- **Concurrent requests: 312-384**
- **Throughput: 90-120 req/sec**
- **Users supported: 500-600** ✅

### Cost Optimization

**Spot Instances:**
- On-demand: $0.805/hour
- Spot: $0.452/hour
- **Savings: 44%**

**KEDA Autoscaling:**
```yaml
minReplicaCount: 1   # Off-hours: 1 GPU
maxReplicaCount: 6   # Peak: 6 GPUs
```

**Monthly Cost Breakdown:**
- Off-hours (400hrs): 1 GPU × $0.452 = $181
- Business (200hrs): 2 GPUs × $0.452 = $181
- Peak (130hrs): 6 GPUs × $0.452 = $354
- **Total: ~$437/month** vs. $3,000-5,000 for Gemini API

---

## Troubleshooting

### Model Download Issues
```bash
# Check cache directory
ls -lh $HF_HOME/hub/

# Clear cache and re-download
rm -rf $HF_HOME/hub/models--Qwen*
./start_vllm_server.sh
```

### Flash Attention Errors
```bash
# Reinstall with --no-build-isolation
pip uninstall flash-attn -y
pip install flash-attn==2.6.3 --no-build-isolation
```

### vLLM Won't Start
```bash
# Check GPU availability
nvidia-smi

# Check memory
nvidia-smi --query-gpu=memory.free --format=csv

# Need at least 16GB free
```

### Low Throughput
```bash
# Check GPU utilization (should be 70-90%)
nvidia-smi dmon -s u

# If low (<50%), increase max-num-seqs
# Edit start_vllm_server.sh:
--max-num-seqs 96  # Increase from 64
```

### Flask Can't Connect to vLLM
```bash
# Test vLLM directly
curl http://localhost:8000/health

# Check environment
cat .env | grep VLLM_URL
# Should be: VLLM_URL=http://localhost:8000
```

---

## Performance Benchmarks

### Expected Latency (per request)
- **Cold start** (first request): 3-5 seconds
- **Warm** (subsequent): 1-3 seconds
- **P95**: <4 seconds
- **P99**: <6 seconds

### Expected Throughput
- **1 GPU**: 15-20 req/sec
- **6 GPUs**: 90-120 req/sec

### GPU Utilization
- **Sequential**: 30-40% (wasteful)
- **With vLLM batching**: 80-90% (optimal) ✅

---

## Next Steps

1. **Test in SageMaker** (current step)
2. **Build Docker image** with vLLM
3. **Deploy to EKS** with KEDA
4. **Configure Karpenter** for spot instances
5. **Set up monitoring** (Prometheus/Grafana)
6. **Load test** with 500 concurrent users

---

## FAQ

**Q: Why not use INT8 quantization?**
A: Grammar/spelling requires high accuracy. FP16 maintains quality while INT8 can introduce errors.

**Q: Can I use a smaller GPU?**
A: Minimum 16GB VRAM (T4). Qwen 2.5 7B needs ~14GB + 2GB for KV cache.

**Q: What about other models?**
A: Llama 3.1 8B, Mistral 7B, or Phi-3 also work. Qwen has best multilingual support.

**Q: How do I update the model?**
A: Change `VLLM_MODEL` in `.env` and restart vLLM server.

**Q: Can I run this on CPU?**
A: vLLM requires GPU. For CPU, use transformers library (much slower).

---

## Support

- **Issues**: https://github.com/thearchitect2024/appen-correct-localised/issues
- **vLLM Docs**: https://docs.vllm.ai
- **Model**: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct

