#!/usr/bin/env bash
# Check status of all services
echo "=== Service Status ==="

echo -n "OpenCode serve (port 8800): "
if curl -s http://127.0.0.1:8800/api/model > /dev/null 2>&1; then
    echo "✅ RUNNING"
else
    echo "❌ DOWN"
fi

echo -n "Hermes Proxy (port 4101): "
HEALTH=$(curl -s http://127.0.0.1:4101/health 2>/dev/null)
if [ -n "$HEALTH" ]; then
    echo "✅ RUNNING"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo "❌ DOWN"
fi
