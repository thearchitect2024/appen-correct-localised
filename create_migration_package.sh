#!/bin/bash
"""
Create Migration Package for AppenCorrect
Packages everything needed to deploy on a new instance
"""

echo "📦 Creating AppenCorrect Migration Package"
echo "=========================================="

# Create migration directory
MIGRATION_DIR="/tmp/appencorrect_migration_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$MIGRATION_DIR"

echo "✓ Created migration directory: $MIGRATION_DIR"

# Copy application files
echo "📁 Copying application files..."
cp -r /home/ec2-user/apps/AppenCorrect/* "$MIGRATION_DIR/"

# Copy virtual environment requirements
echo "📦 Creating requirements snapshot..."
source /home/ec2-user/autocase_env/bin/activate
pip freeze > "$MIGRATION_DIR/requirements_snapshot.txt"

# Create deployment script for new instance
cat > "$MIGRATION_DIR/deploy_on_new_instance.sh" << 'EOF'
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

EOF

chmod +x "$MIGRATION_DIR/deploy_on_new_instance.sh"

# Create transfer instructions
cat > "$MIGRATION_DIR/MIGRATION_INSTRUCTIONS.md" << 'EOF'
# AppenCorrect Migration Instructions

## Quick Transfer Methods

### Method 1: Direct Copy (Same VPC)
```bash
# On new instance:
rsync -avz ec2-user@OLD-INSTANCE-IP:/tmp/appencorrect_migration_* /tmp/
cd /tmp/appencorrect_migration_*
./deploy_on_new_instance.sh m5.xlarge
```

### Method 2: S3 Transfer
```bash
# On old instance:
tar -czf appencorrect_migration.tar.gz -C /tmp appencorrect_migration_*
aws s3 cp appencorrect_migration.tar.gz s3://your-bucket/

# On new instance:
aws s3 cp s3://your-bucket/appencorrect_migration.tar.gz .
tar -xzf appencorrect_migration.tar.gz
cd appencorrect_migration_*
./deploy_on_new_instance.sh m5.xlarge
```

### Method 3: SCP Transfer
```bash
# From your local machine:
scp -r ec2-user@OLD-IP:/tmp/appencorrect_migration_* .
scp -r appencorrect_migration_* ec2-user@NEW-IP:/tmp/
# Then SSH to new instance and run deploy script
```

## Configuration Optimization

The deploy script automatically optimizes for:
- **2 cores**: 50 workers
- **4 cores**: 80 workers  
- **8 cores**: 150 workers
- **16+ cores**: 20 workers per core

## Verification Steps

After migration:
1. Test API: `curl http://localhost:5006/health`
2. Monitor logs: `journalctl -u appencorrect -f`
3. Run load test: `python3 detailed_stats_test.py`
4. Check cache: `python3 test_cache.py`
EOF

# Copy current database files
echo "💾 Copying database files..."
cp *.db "$MIGRATION_DIR/" 2>/dev/null || echo "   No .db files found"

# Create package
echo "📦 Creating migration package..."
cd /tmp
tar -czf "appencorrect_migration_$(date +%Y%m%d_%H%M%S).tar.gz" appencorrect_migration_*

echo ""
echo "✅ Migration package created!"
echo "📍 Location: /tmp/appencorrect_migration_$(date +%Y%m%d_%H%M%S).tar.gz"
echo "📁 Directory: $MIGRATION_DIR"
echo ""
echo "🎯 Next steps:"
echo "1. Launch new instance (m5.xlarge or m5.2xlarge)"
echo "2. Transfer files using one of the methods in MIGRATION_INSTRUCTIONS.md"
echo "3. Run deploy_on_new_instance.sh on the new instance"
echo ""
echo "💡 The new instance will be automatically optimized for its CPU count!"
