#!/bin/bash
# Dynamic service startup script that uses WORKERS from .env

# Load environment variables
if [ -f /home/ec2-user/apps/AppenCorrect/.env ]; then
    source /home/ec2-user/apps/AppenCorrect/.env
fi

# Set defaults
WORKERS=${WORKERS:-12}
HOST=${FLASK_HOST:-0.0.0.0}
PORT=${FLASK_PORT:-5006}

# Calculate connection limit based on workers
CONNECTION_LIMIT=$((WORKERS * 4))

echo "Starting AppenCorrect with $WORKERS threads..."

# Start waitress with dynamic configuration
exec /home/ec2-user/autocase_env/bin/waitress-serve \
    --host=$HOST \
    --port=$PORT \
    --threads=$WORKERS \
    --connection-limit=$CONNECTION_LIMIT \
    --cleanup-interval=30 \
    --channel-timeout=120 \
    --send-bytes=18000 \
    app:app
