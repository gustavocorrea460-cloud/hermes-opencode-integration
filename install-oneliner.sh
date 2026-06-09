#!/usr/bin/env bash
# install-oneliner.sh — Instalação em 1 comando da integração Hermes + OpenCode
# Uso: curl -fsSL https://raw.githubusercontent.com/.../install-oneliner.sh | bash

set -euo pipefail

REPO_URL="https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main"

echo "⚡ Instalando Hermes + OpenCode Integration..."
echo ""

# Pré-requisitos
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 é necessário"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js é necessário"; exit 1; }

# OpenCode
command -v opencode >/dev/null 2>&1 || npm install -g @opencode/cli

# Hermes
[ -d "$HOME/.hermes/hermes-agent" ] || curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Baixar integração
mkdir -p "$HOME/.hermes/integration"
curl -fsSL "$REPO_URL/hermes-proxy.py" -o "$HOME/.hermes/hermes-proxy.py"
curl -fsSL "$REPO_URL/hermes-mcp-bridge.py" -o "$HOME/.hermes/hermes-mcp-bridge.py"
curl -fsSL "$REPO_URL/start.sh" -o "$HOME/.hermes/start.sh"
curl -fsSL "$REPO_URL/stop.sh" -o "$HOME/.hermes/stop.sh"
curl -fsSL "$REPO_URL/status.sh" -o "$HOME/.hermes/status.sh"
chmod +x "$HOME/.hermes/start.sh" "$HOME/.hermes/stop.sh" "$HOME/.hermes/status.sh"

# Iniciar
"$HOME/.hermes/start.sh"

echo ""
echo "✅ Instalação concluída! Use: hermes"
