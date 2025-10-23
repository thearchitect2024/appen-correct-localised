#!/bin/bash
"""
Deploy AppenCorrect on New Instance
Run this script on the target instance after copying files
"""

NEW_INSTANCE_TYPE=${1:-"m5.xlarge"}

echo "🚀 Deploying AppenCorrect on $NEW_INSTANCE_TYPE"
echo "================================================"

# Detect CPU cores
CPU_CORES=$(nproc)
echo "✓ Detected $CPU_CORES CPU cores"

# Calculate optimal workers based on instance type
if [ "$CPU_CORES" -eq 4 ]; then
    # 4 cores - use 80-100 workers
    OPTIMAL_WORKERS=80
    CONNECTION_LIMIT=320
elif [ "$CPU_CORES" -eq 8 ]; then
    # 8 cores - use 150-200 workers  
    OPTIMAL_WORKERS=150
    CONNECTION_LIMIT=600
elif [ "$CPU_CORES" -eq 2 ]; then
    # 2 cores - current setup
    OPTIMAL_WORKERS=50
    CONNECTION_LIMIT=200
else
    # Auto-calculate: ~20 workers per core
    OPTIMAL_WORKERS=$((CPU_CORES * 20))
    CONNECTION_LIMIT=$((OPTIMAL_WORKERS * 4))
fi

echo "✓ Optimal configuration for $CPU_CORES cores:"
echo "   Workers: $OPTIMAL_WORKERS"
echo "   Connection limit: $CONNECTION_LIMIT"

# Setup directories
echo "📁 Setting up directories..."
mkdir -p /home/ec2-user/apps
cp -r . /home/ec2-user/apps/AppenCorrect/
cd /home/ec2-user/apps/AppenCorrect

# Create virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv /home/ec2-user/autocase_env
source /home/ec2-user/autocase_env/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements_snapshot.txt

# Update .env for new hardware
echo "⚙️ Optimizing configuration for $CPU_CORES cores..."
sed -i "s/WORKERS=.*/WORKERS=$OPTIMAL_WORKERS/" .env

# Create optimized systemd service
cat > appencorrect_optimized.service << EOFSERVICE
[Unit]
Description=AppenCorrect (Optimized for $CPU_CORES cores)
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/apps/AppenCorrect
EnvironmentFile=/home/ec2-user/apps/AppenCorrect/.env
ExecStart=/home/ec2-user/autocase_env/bin/waitress-serve --host=0.0.0.0 --port=5006 --threads=$OPTIMAL_WORKERS --connection-limit=$CONNECTION_LIMIT --cleanup-interval=30 --channel-timeout=120 --send-bytes=18000 app:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOFSERVICE

# Install service
echo "🔧 Installing systemd service..."
sudo cp appencorrect_optimized.service /etc/systemd/system/appencorrect.service
sudo systemctl daemon-reload
sudo systemctl enable appencorrect

# Test cache connection
echo "🔌 Testing cache connection..."
python3 -c "
from cache_client import get_cache
cache = get_cache()
if cache.is_available():
    print('✅ Cache connected successfully')
    cache.set('test', 'migration_test', 'working')
    result = cache.get('test', 'migration_test') 
    print(f'✅ Cache test: {result}')
else:
    print('⚠️ Cache not connected - will use fallback')
"

# Start service
echo "🚀 Starting AppenCorrect service..."
sudo systemctl start appencorrect

# Wait and test
sleep 5
echo "🧪 Testing API..."
curl -s -X POST "http://localhost:5006/check" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: appencorrect_6cc586912e264062afdc0810f22d075a" \
  -d '{"text": "Migration test sentance.", "language": "english"}' \
  | jq .statistics.processing_time

echo ""
echo "✅ Migration completed!"
echo "📊 Final configuration:"
echo "   Workers: $OPTIMAL_WORKERS threads"
echo "   CPU cores: $CPU_CORES"
echo "   Connection limit: $CONNECTION_LIMIT"
echo "   Port: 5006"
echo ""
echo "🔍 Monitor with:"
echo "   journalctl -u appencorrect -f"
echo "   sudo systemctl status appencorrect"

