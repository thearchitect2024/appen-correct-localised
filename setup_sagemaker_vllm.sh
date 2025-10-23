#!/bin/bash
#
# Complete SageMaker Setup Script for AppenCorrect with vLLM
# Run this on a SageMaker notebook instance (ml.g5.xlarge or ml.g5.2xlarge)
#

set -e

echo "=========================================="
echo "  AppenCorrect + vLLM SageMaker Setup"
echo "=========================================="
echo ""

# Configuration
REPO_URL="https://github.com/thearchitect2024/appen-correct-localised.git"
REPO_BRANCH="vllm"
WORK_DIR="/home/ec2-user/SageMaker/appen-correct-localised"
MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"

# Model cache directory (persistent across notebook restarts)
export HF_HOME="/home/ec2-user/SageMaker/.huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/hub"
mkdir -p "$HF_HOME/hub"

echo "Step 1: Checking GPU..."
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
echo ""

echo "Step 2: Installing system dependencies..."
pip install --upgrade pip setuptools wheel
echo ""

echo "Step 3: Installing Flash Attention 2 (may take 5-10 min)..."
pip install flash-attn==2.6.3 --no-build-isolation
python -c "import flash_attn; print(f'✓ Flash Attention {flash_attn.__version__} installed')"
echo ""

echo "Step 4: Installing vLLM and dependencies..."
pip install vllm==0.6.3
pip install transformers>=4.45.0 torch>=2.1.0
pip install requests flask flask-cors python-dotenv jsonschema pyngrok
pip install langdetect lingua-language-detector redis valkey
echo ""

echo "Step 5: Cloning/updating repository..."
if [ -d "$WORK_DIR" ]; then
    echo "Repository exists, pulling latest..."
    cd "$WORK_DIR"
    git fetch origin
    git checkout "$REPO_BRANCH"
    git pull origin "$REPO_BRANCH"
else
    echo "Cloning repository..."
    cd /home/ec2-user/SageMaker
    git clone "$REPO_URL"
    cd appen-correct-localised
    git checkout "$REPO_BRANCH"
fi
echo ""

echo "Step 6: Configuring environment..."
cd "$WORK_DIR"
cat > .env << 'EOF'
# vLLM Configuration
USE_VLLM=true
VLLM_URL=http://localhost:8000
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct

# HuggingFace cache (persistent model storage)
HF_HOME=/home/ec2-user/SageMaker/.huggingface
TRANSFORMERS_CACHE=/home/ec2-user/SageMaker/.huggingface/hub

# Flask Configuration
FLASK_PORT=5006
FLASK_DEBUG=false

# GPU Configuration
GPU_MEMORY_UTILIZATION=0.85
VLLM_MAX_NUM_SEQS=64
VLLM_MAX_NUM_BATCHED_TOKENS=8192
EOF

echo "✓ Environment configured"
cat .env
echo ""

echo "Step 7: Making scripts executable..."
chmod +x start_vllm_server.sh
echo ""

echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start vLLM server (in one terminal):"
echo "   cd $WORK_DIR"
echo "   ./start_vllm_server.sh"
echo ""
echo "2. Start Flask API (in another terminal):"
echo "   cd $WORK_DIR"
echo "   python3 app.py"
echo ""
echo "3. Create ngrok tunnel (optional, for public access):"
echo "   ngrok http 5006"
echo ""
echo "4. Test the system:"
echo "   curl -X POST http://localhost:5006/demo/check \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"text\": \"I has a eror in grammer\"}'"
echo ""
echo "Model will be cached in: $HF_HOME/hub"
echo "First run downloads ~14GB (5-10 min), subsequent runs are instant!"
echo ""

