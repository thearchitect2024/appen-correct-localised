#!/bin/bash
"""
Final Pre-Restart Safety Check for AppenCorrect
Quick verification before restarting with 50 workers + Redis cache
"""

echo "🚀 Final AppenCorrect Restart Safety Check"
echo "=========================================="

# Activate virtual environment
source /home/ec2-user/autocase_env/bin/activate

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Not in AppenCorrect directory"
    exit 1
fi

echo "✅ Virtual environment activated"
echo "✅ In AppenCorrect directory"

# Check .env file
if [ ! -f ".env" ]; then
    echo "❌ .env file missing"
    exit 1
fi

echo "✅ .env file exists"

# Check key environment variables
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ GEMINI_API_KEY not configured"
    exit 1
fi

echo "✅ GEMINI_API_KEY configured"

# Check if current app is running
CURRENT_PID=$(ps aux | grep "app:app" | grep -v grep | awk '{print $2}' | head -1)
if [ ! -z "$CURRENT_PID" ]; then
    echo "⚠️ Current app running (PID: $CURRENT_PID)"
    echo "   To stop: kill $CURRENT_PID"
else
    echo "✅ No conflicting processes"
fi

# Check Redis packages
python3 -c "import redis; import valkey; print('✅ Redis/Valkey packages installed')" 2>/dev/null || {
    echo "❌ Redis/Valkey packages missing"
    echo "   Run: pip install redis valkey"
    exit 1
}

# Check cache connection (with timeout)
echo "🔌 Testing cache connection..."
CACHE_TEST=$(timeout 5 python3 -c "
import redis
try:
    r = redis.Redis(host='$VALKEY_HOST', port=$VALKEY_PORT, db=$VALKEY_DB, socket_timeout=3)
    r.ping()
    print('CONNECTED')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null)

if [[ "$CACHE_TEST" == "CONNECTED" ]]; then
    echo "✅ Cache connection successful"
    CACHE_MODE="with Redis cache"
elif [[ "$VALKEY_ENABLED" == "true" ]]; then
    echo "⚠️ Cache enabled but not connecting - will use fallback"
    CACHE_MODE="with fallback cache"
else
    echo "ℹ️ Cache disabled - using in-memory cache"
    CACHE_MODE="with in-memory cache"
fi

# Show final configuration
echo ""
echo "📋 FINAL CONFIGURATION:"
echo "   Workers: ${WORKERS:-50}"
echo "   Cache: $CACHE_MODE"
echo "   Port: 5006"
echo ""

# Generate restart commands
echo "🎯 RESTART COMMANDS:"
echo ""

if [ ! -z "$CURRENT_PID" ]; then
    echo "1. Stop current app:"
    echo "   kill $CURRENT_PID"
    echo "   sleep 3"
    echo ""
fi

echo "2. Start with optimized settings:"
echo "   # Recommended for m5.large (2 vCPUs):"
echo "   WORKERS=20 ./start_server.sh"
echo ""
echo "   # Or with your configured setting:"
echo "   ./start_server.sh"
echo ""
echo "   # Or manual:"
echo "   waitress-serve --host=0.0.0.0 --port=5006 --threads=20 app:app"
echo ""

echo "3. Verify startup:"
echo "   curl http://localhost:5006/health"
echo ""

echo "🎉 READY TO RESTART!"
echo "The app will work $CACHE_MODE"
if [[ "$CACHE_TEST" != "CONNECTED" ]] && [[ "$VALKEY_ENABLED" == "true" ]]; then
    echo ""
    echo "💡 Cache note: Even if Redis isn't connecting, the app will"
    echo "   work fine with in-memory cache fallback."
fi
