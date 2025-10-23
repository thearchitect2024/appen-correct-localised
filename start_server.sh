#!/bin/bash
"""
AppenCorrect Production Server Startup Script

This script starts the AppenCorrect server with configurable workers/threads
using the WORKERS environment variable from .env file.

Usage:
    ./start_server.sh                    # Use environment WORKERS value
    WORKERS=25 ./start_server.sh         # Override WORKERS value
    ./start_server.sh --help            # Show help
"""

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

# Set default values
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="5006"
DEFAULT_WORKERS="50"
DEFAULT_TIMEOUT="30"
DEFAULT_MAX_REQUESTS="1000"

# Get configuration from environment variables or use defaults
HOST=${FLASK_HOST:-$DEFAULT_HOST}
PORT=${FLASK_PORT:-$DEFAULT_PORT}
WORKERS=${WORKERS:-$DEFAULT_WORKERS}
TIMEOUT=${TIMEOUT:-$DEFAULT_TIMEOUT}
MAX_REQUESTS=${MAX_REQUESTS:-$DEFAULT_MAX_REQUESTS}
MAX_REQUESTS_JITTER=${MAX_REQUESTS_JITTER:-50}

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "AppenCorrect Production Server Startup"
    echo ""
    echo "Environment Variables:"
    echo "  WORKERS              Number of worker threads (default: $DEFAULT_WORKERS)"
    echo "  FLASK_HOST           Host to bind to (default: $DEFAULT_HOST)"
    echo "  FLASK_PORT           Port to bind to (default: $DEFAULT_PORT)"
    echo "  TIMEOUT              Request timeout in seconds (default: $DEFAULT_TIMEOUT)"
    echo "  MAX_REQUESTS         Max requests per worker (default: $DEFAULT_MAX_REQUESTS)"
    echo "  MAX_REQUESTS_JITTER  Random jitter for max requests (default: 50)"
    echo ""
    echo "Usage:"
    echo "  ./start_server.sh                    # Use environment values"
    echo "  WORKERS=25 ./start_server.sh         # Override WORKERS"
    echo ""
    echo "Current Configuration:"
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Workers: $WORKERS"
    echo "  Timeout: $TIMEOUT"
    echo "  Max Requests: $MAX_REQUESTS"
    exit 0
fi

echo "=========================================="
echo "       AppenCorrect Production Server     "
echo "=========================================="
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS threads"
echo "Timeout: ${TIMEOUT}s"
echo "Max Requests per Worker: $MAX_REQUESTS"
echo "Max Requests Jitter: $MAX_REQUESTS_JITTER"
echo "=========================================="
echo ""

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found in current directory"
    echo "Please run this script from the AppenCorrect root directory"
    exit 1
fi

# Check if required Python packages are installed
echo "Checking dependencies..."
python3 -c "import waitress" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: waitress not installed. Please install it with:"
    echo "pip install waitress"
    exit 1
fi

python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: flask not installed. Please install dependencies with:"
    echo "pip install -r requirements.txt"
    exit 1
fi

echo "✓ Dependencies verified"

# Test cache connection
echo "Testing cache connection..."
python3 -c "
try:
    from cache_client import get_cache
    cache = get_cache()
    if cache.is_available():
        print('✓ Cache connected successfully')
    else:
        print('⚠️ Cache not available - using fallback mode')
except ImportError:
    print('ℹ️ Cache dependencies not installed - using in-memory cache only')
except Exception as e:
    print(f'⚠️ Cache connection failed: {e} - using fallback mode')
"
echo ""

# Start the server with Waitress
echo "Starting AppenCorrect server..."
echo "Press Ctrl+C to stop the server"
echo ""

# Waitress command with configurable workers (threads)
# Note: Waitress uses threads, not processes like Gunicorn
exec waitress-serve \
    --host="$HOST" \
    --port="$PORT" \
    --threads="$WORKERS" \
    --connection-limit="$((WORKERS * 4))" \
    --cleanup-interval="30" \
    --channel-timeout="$TIMEOUT" \
    --log-untrusted-proxy-headers \
    --trusted-proxy="*" \
    app:app
