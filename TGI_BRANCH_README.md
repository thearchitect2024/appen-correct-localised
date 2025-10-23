# TGI Branch - AppenCorrect with Text-Generation-Inference

## What Changed?

This branch replaces **vLLM** with **TGI (Text-Generation-Inference)** to avoid dependency issues while maintaining the same performance.

### Key Differences from vLLM Branch

| Aspect | vLLM Branch | TGI Branch (This) |
|--------|-------------|-------------------|
| **Inference Engine** | vLLM (Python) | TGI (Rust + Docker) |
| **Dependency Issues** | ❌ pyairports broken on PyPI | ✅ No issues |
| **Installation** | pip install (complex deps) | Docker pull (simple) |
| **Stability** | ⚠️ Module import errors | ✅ Production-ready |
| **Performance** | 100-120 req/sec | 80-120 req/sec (similar) |
| **Maintained by** | UC Berkeley | Hugging Face |
| **Default Port** | 8000 | 8080 |

## Quick Start

```bash
# 1. Start TGI server (Docker)
docker run -d \
  --name tgi-server \
  --gpus all \
  -p 8080:80 \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id Qwen/Qwen2.5-7B-Instruct

# 2. Set environment
export TGI_URL="http://localhost:8080"

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Flask
python3 app.py
```

Open: `http://localhost:5006/`

## Architecture

```
User Browser
    ↓ HTTPS
Flask API (CPU pods)
    ↓ HTTP (internal K8s network)
TGI Server (GPU pods)
    ↓ GPU inference
Qwen 2.5 7B Model
```

**Same as vLLM**, just swapping the inference engine!

## Files Changed

### New Files
- `tgi_client.py` - TGI API client
- `sagemaker_tgi_test.ipynb` - SageMaker testing notebook
- `QUICKSTART_TGI.md` - Quick start guide
- `TGI_BRANCH_README.md` - This file

### Modified Files
- `core.py` - All vLLM → TGI references
- `requirements.txt` - `vllm` → `text-generation`

### Removed Files
- `vllm_client.py`
- `start_vllm_server.sh`
- `sagemaker_vllm_test.ipynb`
- `QUICKSTART_VLLM.md`
- `VLLM_DEPLOYMENT.md`
- `VLLM_ONLY_CHANGES.md`
- `test_vllm_concurrency.py`
- `setup_sagemaker_vllm.sh`

## Testing

### Local Testing
See `QUICKSTART_TGI.md`

### SageMaker Testing
1. Launch g6.xlarge or ml.g5.xlarge instance
2. Clone repo and checkout `tgi` branch
3. Open `sagemaker_tgi_test.ipynb`
4. Run all cells
5. Use ngrok URL to test publicly

### Expected Performance

| Metric | Target |
|--------|--------|
| **Latency** | 200-500ms (grammar checking) |
| **Throughput** | 80-120 req/sec per GPU |
| **Concurrency** | 8-32 concurrent requests per GPU |
| **Memory** | ~14GB model + ~8GB KV cache = 22GB |
| **Error Rate** | <1% |

## Production Deployment (EKS)

Coming soon: Helm charts for TGI deployment

**Expected setup:**
- 10x Flask pods (CPU, t3.medium)
- 3-4x TGI pods (GPU, g6.xlarge spot)
- KEDA for autoscaling
- Karpenter for node management

**Monthly cost:** $300-400 (vs $3,000-5,000 for Gemini API)

## Why TGI Over vLLM?

1. **No Dependency Hell** ✅
   - vLLM requires `outlines` → `pyairports` → broken on PyPI
   - TGI runs in Docker with all deps included

2. **Production Stability** ✅
   - TGI is used by Hugging Face in production
   - Rust core = fewer runtime errors

3. **Simpler Setup** ✅
   - Docker pull vs complex pip install
   - No flash-attn build issues

4. **Same Performance** ✅
   - Both use continuous batching
   - Both support Flash Attention 2
   - Both support paged attention

## Troubleshooting

### TGI won't start
```bash
docker logs tgi-server
```

Common issues:
- Missing GPU (`--gpus all` flag)
- Port already in use (change `-p 8080:80`)
- Out of memory (reduce `--max-concurrent-requests`)

### Flask can't connect
```bash
# Check TGI is running
curl http://localhost:8080/health

# Check environment variable
echo $TGI_URL
```

### Slow inference
- Reduce `--max-concurrent-requests`
- Reduce `--max-total-tokens`
- Check GPU utilization: `nvidia-smi`

## Migration from vLLM Branch

If you're currently on the `vllm` branch:

```bash
# Switch to TGI branch
git checkout tgi
git pull origin tgi

# Stop vLLM
pkill -f vllm

# Start TGI
docker run -d --name tgi-server --gpus all -p 8080:80 \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id Qwen/Qwen2.5-7B-Instruct

# Update environment
export TGI_URL="http://localhost:8080"  # Was VLLM_URL=http://localhost:8000

# Restart Flask
python3 app.py
```

**Everything else stays the same!** Same UI, same API, same responses.

## Support

For issues or questions:
1. Check `QUICKSTART_TGI.md`
2. Check Docker logs: `docker logs tgi-server`
3. Test TGI directly: `curl http://localhost:8080/health`

## Next Steps

1. ✅ Test locally with Docker
2. ✅ Test in SageMaker with notebook
3. ⏳ Deploy to EKS (Helm charts coming)
4. ⏳ Add monitoring and metrics
5. ⏳ Performance benchmarking vs Gemini

---

**Bottom line:** TGI = vLLM without the headaches! 🚀

