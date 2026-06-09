#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  Hermes + OpenCode Integration — Desinstalador v0.4.0
# ═══════════════════════════════════════════════════════════════════════
#  Uso: bash uninstall.sh [--remove-all] [--help]
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Cores ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS="${GREEN}✓${NC}"; FAIL="${RED}✗${NC}"; WARN="${YELLOW}⚠${NC}"; INFO="${CYAN}→${NC}"

HERMES_DIR="$HOME/.hermes"
SYSTEMD_DIR="$HOME/.config/systemd/user"
BACKUP_DIR="$HERMES_DIR/backup-$(date +%Y%m%d-%H%M%S)"
REMOVE_ALL=false
for arg in "$@"; do [ "$arg" = "--remove-all" ] && REMOVE_ALL=true; done

echo ""
echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║${NC}  Hermes + OpenCode Integration — Desinstalação              ${RED}║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Checklist ──
echo -e "${YELLOW}Este desinstalador vai REMOVER:${NC}"
echo ""
if [ "$REMOVE_ALL" = true ]; then
    echo "  [🔴] Fusion Proxy (hermes-proxy.py)"
    echo "  [🔴] MCP Bridge (hermes-mcp-bridge.py)"
    echo "  [🔴] Scripts (start.sh, stop.sh, status.sh, restart.sh)"
    echo "  [🔴] Systemd services (opencode-serve, hermes-proxy)"
    echo "  [🔴] Integração completa (~/.hermes/integration/)"
    echo "  [🔴] Config integration da opencode.json"
    echo "  [🔴] Modelo deepseek-v4-flash-free do opencode.json"
    echo ""
    echo -e "${RED}⚠️  Modo --remove-all: também vai restaurar config.yaml + opencode.json originais${NC}"
else
    echo "  [ ] Fusion Proxy (hermes-proxy.py)"
    echo "  [ ] MCP Bridge (hermes-mcp-bridge.py)"
    echo "  [ ] Scripts (start.sh, stop.sh, status.sh, restart.sh)"
    echo "  [ ] Systemd services"
    echo "  [ ] Integração (~/.hermes/integration/)"
    echo ""
    echo -e "${YELLOW}⚠️  Use --remove-all para restaurar configs originais também${NC}"
fi
echo ""
echo -e "${CYAN}NÃO serão removidos:${NC}"
echo "  [✅] Hermes Agent (~/.hermes/hermes-agent/)"
echo "  [✅] OpenCode (~/.opencode/ ou npm global)"
echo "  [✅] .env (API keys)"
echo "  [✅] config.yaml (será restaurado com backup)"
echo ""

if [ -t 0 ]; then
    read -p "$(echo -e "${RED}Pressione Enter para desinstalar ou Ctrl+C para cancelar...${NC}")"
fi

# ── 1. Backup ──
echo ""
echo -e "${BLUE}[1/5]${NC} Backup"
mkdir -p "$BACKUP_DIR"
for f in config.yaml opencode.json; do
    case "$f" in
        config.yaml) src="$HERMES_DIR/$f" ;;
        opencode.json) src="$HOME/.config/opencode/$f" ;;
    esac
    if [ -f "$src" ]; then
        cp "$src" "$BACKUP_DIR/$f"
        echo -e "  ${PASS} Backup: $f → $BACKUP_DIR/"
    fi
done

# ── 2. Parar Serviços ──
echo ""
echo -e "${BLUE}[2/5]${NC} Parando Serviços"

# Systemd
for svc in opencode-serve.service hermes-proxy.service; do
    if systemctl --user is-active "$svc" &>/dev/null; then
        systemctl --user stop "$svc" 2>/dev/null || true
        echo -e "  ${PASS} Parou: $svc"
    fi
done
# Desabilitar
for svc in opencode-serve.service hermes-proxy.service; do
    if systemctl --user is-enabled "$svc" &>/dev/null 2>&1; then
        systemctl --user disable "$svc" 2>/dev/null || true
        echo -e "  ${PASS} Desabilitou: $svc"
    fi
done

# Processos diretos
if fuser 4101/tcp 2>/dev/null; then
    fuser -k 4101/tcp 2>/dev/null || true
    echo -e "  ${PASS} Proxy parado (porta 4101)"
fi
if fuser 8800/tcp 2>/dev/null; then
    fuser -k 8800/tcp 2>/dev/null || true
    echo -e "  ${PASS} OpenCode serve parado (porta 8800)"
fi

sleep 2

# ── 3. Remover Systemd ──
echo ""
echo -e "${BLUE}[3/5]${NC} Removendo Systemd"
for svc in opencode-serve.service hermes-proxy.service; do
    if [ -f "$SYSTEMD_DIR/$svc" ]; then
        rm -f "$SYSTEMD_DIR/$svc"
        echo -e "  ${PASS} Removeu: $SYSTEMD_DIR/$svc"
    fi
done
systemctl --user daemon-reload 2>/dev/null || true

# ── 4. Remover Arquivos da Integração ──
echo ""
echo -e "${BLUE}[4/5]${NC} Removendo Arquivos"

# Arquivos principais
for f in hermes-proxy.py hermes-mcp-bridge.py start.sh stop.sh status.sh restart.sh; do
    if [ -f "$HERMES_DIR/$f" ]; then
        rm -f "$HERMES_DIR/$f"
        echo -e "  ${PASS} Removeu: $HERMES_DIR/$f"
    fi
done

# Diretório de integração
if [ -d "$HERMES_DIR/integration" ]; then
    rm -rf "$HERMES_DIR/integration"
    echo -e "  ${PASS} Removeu: $HERMES_DIR/integration/"
fi

# Session map (cache)
if [ -f "$HERMES_DIR/session_map.json" ]; then
    rm -f "$HERMES_DIR/session_map.json"
    echo -e "  ${PASS} Removeu: session_map.json"
fi

# Logs
if [ -d "$HERMES_DIR/logs" ]; then
    rm -rf "$HERMES_DIR/logs"
    echo -e "  ${PASS} Removeu: logs/"
fi

# ── 5. Restaurar Configs (se --remove-all) ──
echo ""
echo -e "${BLUE}[5/5]${NC} Configs"

if [ "$REMOVE_ALL" = true ]; then
    # Restaurar config.yaml (remover seção opencode-proxy)
    if [ -f "$BACKUP_DIR/config.yaml" ]; then
        # Remove ou comenta o provider opencode-proxy
        cp "$BACKUP_DIR/config.yaml" "$HERMES_DIR/config.yaml"
        echo -e "  ${PASS} config.yaml restaurado do backup"
    fi

    # Restaurar opencode.json (remover hermes-bridge mcp)
    if [ -f "$BACKUP_DIR/opencode.json" ]; then
        OAUTH="$HOME/.config/opencode/opencode.json"
        python3 -c "
import json
with open('$BACKUP_DIR/opencode.json') as f:
    cfg = json.load(f)
# Remove hermes-bridge MCP
cfg.get('mcp', {}).pop('hermes-bridge', None)
# Remove deepseek-v4-flash-free model
cfg.get('provider', {}).get('opencode', {}).get('models', {}).pop('deepseek-v4-flash-free', None)
with open('$OAUTH', 'w') as f:
    json.dump(cfg, f, indent=2)
print('  opencode.json limpo')
" 2>/dev/null || cp "$BACKUP_DIR/opencode.json" "$OAUTH"
        echo -e "  ${PASS} opencode.json restaurado"
    fi

    # Limpar hermes config fallback
    if grep -q "opencode-proxy" "$HERMES_DIR/config.yaml" 2>/dev/null; then
        echo -e "  ${WARN} Ainda há referência a opencode-proxy no config.yaml"
        echo -e "  ${INFO} Edite manualmente: nano $HERMES_DIR/config.yaml"
    fi
else
    echo -e "  ${INFO} Para restaurar configs originais: bash uninstall.sh --remove-all"
fi

# ── Resumo ──
echo ""
echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║${NC}  ❌ Desinstalação concluída.                                 ${RED}║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Backup salvo em: ${CYAN}$BACKUP_DIR/${NC}"
echo ""

if [ "$REMOVE_ALL" = false ]; then
    echo -e "  ${YELLOW}Para remover também as alterações nas configs:${NC}"
    echo "    bash uninstall.sh --remove-all"
    echo ""
fi
echo -e "  ${GREEN}Hermes Agent e OpenCode NÃO foram removidos.${NC}"
echo -e "  ${GREEN}Seu .env e API keys estão preservados.${NC}"
echo ""
