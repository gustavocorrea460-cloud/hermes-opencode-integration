#!/usr/bin/env bash
# Start OpenCode serve + Hermes Fusion Proxy
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

cleanup() {
    echo "Stopping services..."
    pkill -f "opencode serve" 2>/dev/null || true
    pkill -f "hermes-proxy.py" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start opencode serve
echo "Starting OpenCode serve..."
opencode serve --port 8800 --hostname 127.0.0.1 > "$LOG_DIR/opencode-serve.log" 2>&1 &
SERVE_PID=$!
echo "  PID: $SERVE_PID"

# Wait for it to be ready
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8800/api/model > /dev/null 2>&1; then
        echo "  OpenCode serve ready! ($i seconds)"
        break
    fi
    sleep 1
done

# Source Hermes venv and start proxy
echo "Starting Hermes Fusion Proxy..."
source "$SCRIPT_DIR/hermes-agent/venv/bin/activate"
python3 "$SCRIPT_DIR/hermes-proxy.py" > "$LOG_DIR/hermes-proxy.log" 2>&1 &
PROXY_PID=$!
echo "  PID: $PROXY_PID"

sleep 2
if curl -s http://127.0.0.1:4101/health > /dev/null 2>&1; then
    echo "✅ Hermes Fusion Proxy ready on port 4101"
    echo ""
    echo "Hermes is now using OpenCode for LLM inference."
    echo "Model: deepseek-v4-flash-free (fallback: OpenRouter)"
    echo "Models: $(curl -s http://127.0.0.1:4101/v1/models 2>/dev/null | python3 -c \"import sys,json; print(f'{len(json.load(sys.stdin)[\"data\"])} free models')\" 2>/dev/null || echo \"146 free models\")"
else
    echo "❌ Proxy failed to start" >&2
    exit 1
fi

wait
