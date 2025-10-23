#!/bin/bash
"""
Setup AppenCorrect as a systemd service for journal logging
"""

echo "🔧 Setting up AppenCorrect systemd service..."

# Stop current process if running
CURRENT_PID=$(ps aux | grep "app:app" | grep -v grep | awk '{print $2}' | head -1)
if [ ! -z "$CURRENT_PID" ]; then
    echo "Stopping current process (PID: $CURRENT_PID)..."
    kill $CURRENT_PID
    sleep 3
fi

# Copy service file to systemd
echo "Installing service file..."
sudo cp appencorrect.service /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable service
echo "Enabling service..."
sudo systemctl enable appencorrect

# Start service
echo "Starting AppenCorrect service..."
sudo systemctl start appencorrect

# Check status
echo "Service status:"
sudo systemctl status appencorrect

echo ""
echo "🎉 AppenCorrect is now running as a systemd service!"
echo ""
echo "📊 Monitoring commands:"
echo "   sudo systemctl status appencorrect     # Service status"
echo "   journalctl -u appencorrect -f         # Live logs"
echo "   journalctl -u appencorrect --since today  # Today's logs"
echo "   journalctl -u appencorrect -n 100     # Last 100 lines"
echo ""
