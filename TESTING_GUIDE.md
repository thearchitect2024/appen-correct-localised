# Testing Guide - vLLM Branch

## ✅ All Changes Committed!

Branch: `vllm`  
Latest Commits:
- `55486aa` - Documentation confirming vLLM-only implementation
- `dc3f49c` - Remove all Gemini and OpenAI API code - vLLM only
- `c1ea334` - Add vLLM local inference support with concurrency and model caching

---

## Quick Test Options

### Option 1: Local Testing (Requires GPU)

**Prerequisites:**
- NVIDIA GPU with 16GB+ VRAM (L4, A10G, T4, A100, etc.)
- CUDA drivers installed
- Python 3.8+

**Steps:**

```bash
# 1. Navigate to the repo
cd /Users/kkularatna/Downloads/AppenCorrect-main

# 2. Switch to vllm branch (if not already)
git checkout vllm

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Flash Attention 2 (optional but recommended)
pip install flash-attn --no-build-isolation

# 5. Start vLLM server (Terminal 1)
# This will download Qwen 2.5 7B (~14GB) on first run
./start_vllm_server.sh

# Wait for: "Application startup complete."
# Takes 5-10 min first time (model download)
# Subsequent runs: 30-60 seconds (loads from cache)

# 6. Start Flask API (Terminal 2 - new terminal)
export VLLM_URL=http://localhost:8000
export VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
python3 app.py

# 7. Test with curl
curl -X POST http://localhost:5006/demo/check \
  -H "Content-Type: application/json" \
  -d '{"text": "I has a eror in grammer"}'

# 8. Open web interface
open http://localhost:5006
```

---

### Option 2: SageMaker Testing (Recommended for First Test)

**Prerequisites:**
- AWS Account
- SageMaker notebook instance: `ml.g5.xlarge` or `ml.g5.2xlarge`

**Steps:**

```bash
# 1. SSH into SageMaker notebook instance
ssh ec2-user@your-sagemaker-instance

# 2. Run one-click setup script
cd /home/ec2-user/SageMaker
wget https://raw.githubusercontent.com/thearchitect2024/appen-correct-localised/vllm/setup_sagemaker_vllm.sh
chmod +x setup_sagemaker_vllm.sh
./setup_sagemaker_vllm.sh

# 3. Start vLLM (Terminal 1)
cd /home/ec2-user/SageMaker/appen-correct-localised
./start_vllm_server.sh

# 4. Start Flask (Terminal 2)
python3 app.py

# 5. Create ngrok tunnel for public access (optional)
pip install pyngrok
python -c "from pyngrok import ngrok; ngrok.set_auth_token('YOUR_TOKEN'); print(ngrok.connect(5006))"
```

**Get ngrok token:** https://dashboard.ngrok.com/get-started/your-authtoken

---

### Option 3: Docker Testing (CPU only - slow, not recommended)

```bash
# Build Docker image
docker build -t appencorrect-vllm .

# Note: vLLM requires GPU, won't work well in CPU-only Docker
# This is just for testing the Flask API structure
```

---

## What to Test

### 1. **Health Check**
```bash
curl http://localhost:5006/health
```
Expected: `{"status": "healthy", "api_available": true, "api_type": "vllm"}`

### 2. **Simple Grammar Check**
```bash
curl -X POST http://localhost:5006/demo/check \
  -H "Content-Type: application/json" \
  -d '{"text": "I has a eror"}'
```
Expected: JSON with corrections

### 3. **Concurrency Test**
```bash
python3 test_vllm_concurrency.py
```
Expected: 
- ✓ 20 concurrent requests processed
- ✓ GPU batching verified
- ✓ Response format validated

### 4. **Web Interface**
Open browser: `http://localhost:5006`
- Type text with errors
- Click "Check Grammar"
- Verify corrections appear

---

## Expected Performance

### First Run:
- **Model Download**: 5-10 minutes (~14GB)
- **Model Load**: 30-60 seconds
- **First Request**: 3-5 seconds

### Subsequent Runs:
- **Model Load**: 30-60 seconds (from cache)
- **Request Latency**: 1-3 seconds
- **Throughput**: 15-20 requests/sec per GPU

---

## Troubleshooting

### "vLLM server connection failed"
```bash
# Check if vLLM is running
curl http://localhost:8000/health

# Check GPU
nvidia-smi

# Check vLLM logs
# Look for "Application startup complete."
```

### "Model download timeout"
```bash
# Download manually first
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct')"
```

### "Flash Attention error"
```bash
# Reinstall with --no-build-isolation
pip uninstall flash-attn -y
pip install flash-attn --no-build-isolation
```

### "Out of memory"
```bash
# Check GPU memory
nvidia-smi

# Need at least 16GB VRAM
# Qwen 2.5 7B requires ~14GB
```

---

## Files Changed in vllm Branch

### New Files:
- `vllm_client.py` - vLLM inference client
- `start_vllm_server.sh` - Server startup script
- `setup_sagemaker_vllm.sh` - SageMaker setup
- `test_vllm_concurrency.py` - Concurrency tests
- `VLLM_DEPLOYMENT.md` - Full deployment guide
- `QUICKSTART_VLLM.md` - Quick start guide
- `VLLM_ONLY_CHANGES.md` - Summary of changes
- `TESTING_GUIDE.md` - This file

### Modified Files:
- `core.py` - Removed Gemini/OpenAI, added vLLM
- `requirements.txt` - Added vLLM dependencies
- `.gitignore` - Ignored .env and logs

### Removed:
- All Gemini API code (113 references)
- All OpenAI API code
- `google-genai` from requirements

---

## Quick Verification Commands

```bash
# Check branch
git branch --show-current
# Expected: vllm

# Check commits
git log --oneline -3
# Should see vLLM-related commits

# Check for Gemini/OpenAI (should be empty)
grep -r "gemini\|openai" core.py
# Expected: No matches

# Check vLLM files exist
ls -lh vllm_client.py start_vllm_server.sh
# Should exist

# Check requirements
grep vllm requirements.txt
# Should show: vllm==0.6.3
```

---

## Push to GitHub (if needed)

```bash
# Push vllm branch to remote
git push origin vllm

# Or push and set upstream
git push -u origin vllm
```

---

## Next Steps After Testing

1. ✅ Test locally or on SageMaker
2. ✅ Verify concurrency works
3. ✅ Check response format matches expectations
4. 🚀 Deploy to EKS with KEDA
5. 📊 Set up monitoring (Prometheus/Grafana)
6. 💰 Configure Karpenter for cost optimization

---

## Support

- **Full Guide**: `VLLM_DEPLOYMENT.md`
- **Quick Start**: `QUICKSTART_VLLM.md`
- **Changes**: `VLLM_ONLY_CHANGES.md`
- **Issues**: https://github.com/thearchitect2024/appen-correct-localised/issues

---

## Summary

✅ **All changes committed to `vllm` branch**  
✅ **100% vLLM, 0% Gemini/OpenAI**  
✅ **Model caching enabled**  
✅ **Concurrency configured (64 requests/GPU)**  
✅ **Ready to test!**

**Recommended:** Start with SageMaker testing for quickest setup.

