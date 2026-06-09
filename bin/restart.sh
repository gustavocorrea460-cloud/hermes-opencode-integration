#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  restart.sh — Reinício atômico de todos os serviços da integração
#  Uso: bash restart.sh
# ═══════════════════════════════════════════════════════════════════════
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔄 Reiniciando serviços da integração Hermes + OpenCode..."
"$SCRIPT_DIR/stop.sh"
sleep 2
"$SCRIPT_DIR/start.sh"
