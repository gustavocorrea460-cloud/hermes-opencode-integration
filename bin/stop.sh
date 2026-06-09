#!/usr/bin/env bash
# Stop OpenCode serve + Hermes Fusion Proxy
set -e

echo "Stopping Hermes Fusion Proxy..."
pkill -f "hermes-proxy.py" 2>/dev/null && echo "  Proxy stopped" || echo "  Proxy not running"

echo "Stopping OpenCode serve..."
pkill -f "opencode serve" 2>/dev/null && echo "  OpenCode stopped" || echo "  OpenCode not running"

echo "All services stopped."
