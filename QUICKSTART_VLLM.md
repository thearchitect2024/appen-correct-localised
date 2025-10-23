# AppenCorrect vLLM Quick Start

## TL;DR - Get Running in 15 Minutes

### SageMaker Notebook (ml.g5.xlarge)

```bash
# 1. Run setup (5 min)
cd /home/ec2-user/SageMaker
wget https://raw.githubusercontent.com/thearchitect2024/appen-correct-localised/vllm/setup_sagemaker_vllm.sh
chmod +x setup_sagemaker_vllm.sh
./setup_sagemaker_vllm.sh

# 2. Start vLLM (downloads model first time: ~10 min)
cd appen-correct-localised
./start_vllm_server.sh

# Wait for: "Application startup complete."

# 3. Start Flask (new terminal)
python3 app.py

# 4. Test
curl -X POST http://localhost:5006/demo/check \
  -H "Content-Type: application/json" \
  -d '{"text": "I has a eror"}'
```

Done! ✅

---

## Key Confirmations

### ✅ Concurrency is Enabled

vLLM's continuous batching processes **multiple requests simultaneously**:

```bash
# Configuration in start_vllm_server.sh:
--max-num-seqs 64              # 64 concurrent requests
--max-num-batched-tokens 8192  # Batch tokens together
```

**GPU stays busy, not idle!** 🚀

### ✅ Model is Cached

Models download once, then cached:

```bash
# Cache location:
export HF_HOME=/home/ec2-user/SageMaker/.huggingface
export TRANSFORMERS_CACHE=$HF_HOME/hub

# First run: Downloads ~14GB (5-10 min)
# Next run: Loads from cache (30-60 sec) ✅
```

**No re-downloading!** 💾

---

## Performance Expected

| Metric | Value |
|--------|-------|
| **Latency** | 1-3 seconds |
| **Throughput (1 GPU)** | 15-20 req/sec |
| **Throughput (6 GPUs)** | 90-120 req/sec |
| **Concurrent users (1 GPU)** | 100-150 |
| **Concurrent users (6 GPUs)** | 500-600 ✅ |
| **GPU Utilization** | 80-90% |

---

## Test Concurrency

```bash
# Run test suite
python3 test_vllm_concurrency.py
```

**What it tests:**
- ✓ 20 simultaneous requests
- ✓ Response format validation
- ✓ Throughput measurement
- ✓ GPU batching verification

**Expected output:**
```
✓ Concurrency is working!
  Sequential avg latency: 2.3s
  Concurrent avg latency: 2.5s
  Throughput: 8.0 req/sec
  
✓ GPU is processing multiple requests simultaneously!
  vLLM's continuous batching is active
```

---

## Public Access (ngrok)

```bash
# Install
pip install pyngrok

# Get token from: https://dashboard.ngrok.com

# Start tunnel
python -c "
from pyngrok import ngrok
ngrok.set_auth_token('YOUR_TOKEN')
url = ngrok.connect(5006)
print(f'\n🌐 Public URL: {url}\n')
print(f'Demo: {url}/')
print(f'API: {url}/demo/check')
"
```

Share the URL! Anyone can test your grammar checker.

---

## Monitor GPU

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Check utilization (should be 70-90%)
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv

# Check vLLM process
ps aux | grep vllm
```

---

## Common Issues

### "Model downloading..."
**Wait 5-10 min on first run.** Subsequent runs load from cache.

### "Flash Attention error"
```bash
pip install flash-attn --no-build-isolation --force-reinstall
```

### "Connection refused" (vLLM)
```bash
# Check if running:
curl http://localhost:8000/health

# If not, check logs:
./start_vllm_server.sh
```

### "Slow responses"
First request is slow (model loading). After that: 1-3 sec.

---

## Files Reference

| File | Purpose |
|------|---------|
| `start_vllm_server.sh` | Start vLLM with optimal settings |
| `setup_sagemaker_vllm.sh` | One-click SageMaker setup |
| `test_vllm_concurrency.py` | Test concurrency & throughput |
| `VLLM_DEPLOYMENT.md` | Full deployment guide |
| `vllm_client.py` | vLLM client library |
| `.env` | Configuration (USE_VLLM=true) |

---

## Production Deployment

### EKS with KEDA + Karpenter

**Cost: $250-450/month** (vs $3,000-5,000 for Gemini API)

See `VLLM_DEPLOYMENT.md` for full guide.

**Key components:**
- Flask pods (CPU): Auto-scale 5-20
- vLLM pods (GPU): Auto-scale 1-6
- Spot instances: 44% cost savings
- Scale-to-zero: Off-hours cost = $0

---

## Need Help?

1. **Check logs**: vLLM startup messages show errors
2. **Test vLLM directly**: `curl http://localhost:8000/v1/models`
3. **Verify GPU**: `nvidia-smi` should show process
4. **Read full guide**: `VLLM_DEPLOYMENT.md`

---

## Architecture Diagram

```
┌──────────┐
│  Users   │ (500-600 concurrent)
└────┬─────┘
     ↓
┌────────────┐
│ Flask Pods │ (10-15 pods, CPU)
└────┬───────┘
     ↓ (internal network, <5ms)
┌─────────────────────────┐
│ vLLM Pods (6× g6.xlarge)│
│ GPU inference with:     │
│ ✓ Continuous batching   │ ← Multiple requests at once
│ ✓ Flash Attention 2     │ ← 2-3x faster
│ ✓ PagedAttention        │ ← Efficient memory
│ ✓ Model caching         │ ← No re-download
└─────────────────────────┘
```

**GPU stays busy processing multiple corrections simultaneously!** 🚀

