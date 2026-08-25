#!/bin/bash
# Start the Python trading engine service
cd /home/z/my-project/mini-services/trading-engine

# Kill only MY instances (not /app/ ones)
for pid in $(pgrep -f "mini-services/trading-engine/main.py"); do
    kill -9 $pid 2>/dev/null
done
sleep 1

# Start with nohup, fully detached
nohup python3 main.py > /tmp/trading-engine.log 2>&1 &
ENGINE_PID=$!
echo $ENGINE_PID > /tmp/trading-engine.pid

# Wait for startup
sleep 4

# Verify
if kill -0 $ENGINE_PID 2>/dev/null; then
    echo "OK: Trading engine started. PID: $ENGINE_PID"
    curl -s http://localhost:3030/health
    echo ""
else
    echo "FAILED: Trading engine did not start"
    tail -30 /tmp/trading-engine.log
fi
