#!/usr/bin/env bash
# update.sh — Atualiza a integração Hermes + OpenCode
# Uso: bash update.sh
#       bash update.sh --repo=https://...

set -euo pipefail

REPO_URL="https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main"
HERMES_DIR="$HOME/.hermes"
VERSION_FILE="$HERMES_DIR/integration/VERSION"

# Cores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS="${GREEN}✓${NC}"; FAIL="${RED}✗${NC}"; WARN="${YELLOW}⚠${NC}"; INFO="${CYAN}→${NC}"

# Detectar versão atual
CURRENT="0.4.0"
if [ -f "$VERSION_FILE" ]; then
    CURRENT=$(head -1 "$VERSION_FILE" | tr -d ' \n\r')
fi

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  Atualizando Integração Hermes + OpenCode                    ${BLUE}║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${INFO} Versão local:  ${CYAN}v$CURRENT${NC}"

# Buscar versão remota
LATEST=$(curl -fsSL --max-time 5 "${REPO_URL%/}/VERSION" 2>/dev/null | head -1 | tr -d ' \n\r' || echo "")
if [ -z "$LATEST" ]; then
    echo -e "${WARN} Não foi possível verificar versão remota."
    exit 1
fi
echo -e "${INFO} Versão remota: ${CYAN}v$LATEST${NC}"
echo ""

if [ "$LATEST" = "$CURRENT" ]; then
    echo -e "${PASS} Você já está na versão mais recente! (v$CURRENT)"
    exit 0
fi

echo -e "${WARN} Nova versão disponível: v$CURRENT → v$LATEST"
echo ""

# Baixar arquivos atualizados
echo -e "${BLUE}Baixando atualização...${NC}"
UPDATED=0
MISSING=0
FILES=(
    "hermes-proxy.py:hermes-proxy.py"
    "hermes-mcp-bridge.py:hermes-mcp-bridge.py"
    "VERSION:integration/VERSION"
)

for entry in "${FILES[@]}"; do
    src="${entry%%:*}"
    dst="${entry##*:}"
    dest_path="$HERMES_DIR/$dst"
    mkdir -p "$(dirname "$dest_path")"
    if curl -fsSL --max-time 30 "${REPO_URL%/}/$src" -o "$dest_path"; then
        chmod +x "$dest_path" 2>/dev/null || true
        echo -e "  ${PASS} $(basename "$src")"
        UPDATED=$((UPDATED + 1))
    else
        echo -e "  ${WARN} $(basename "$src") — falha no download"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
echo -e "${PASS} Atualização concluída: $UPDATED arquivos atualizados"

# Restart se estiver rodando
if curl -s --max-time 2 http://127.0.0.1:4101/health >/dev/null 2>&1; then
    echo ""
    echo -e "${INFO} Proxy está rodando. Reiniciando..."
    fuser -k 4101/tcp 2>/dev/null || true
    sleep 1
    source "$HERMES_DIR/hermes-agent/venv/bin/activate" 2>/dev/null || true
    nohup python3 "$HERMES_DIR/hermes-proxy.py" > "$HERMES_DIR/logs/hermes-proxy.log" 2>&1 &
    sleep 2
    if curl -s --max-time 2 http://127.0.0.1:4101/health >/dev/null 2>&1; then
        echo -e "${PASS} Proxy reiniciado com sucesso"
    fi
fi

echo ""
echo -e "${PASS} Atualizado para v$LATEST"
echo -e "${INFO} Rode ~/.hermes/integration/verify.sh para confirmar"
