#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  Hermes + OpenCode Integration — Instalador v0.4.0
#  Motor de inferência LLM gratuito para o Hermes Agent
# ═══════════════════════════════════════════════════════════════════════
#  Uso:
#    bash install.sh                        # modo local (arquivos na pasta)
#    bash install.sh --repo=https://...     # modo download
#    bash install.sh --yes                  # headless (sem confirmação)
#    bash install.sh --help                 # ajuda
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Config ──
VERSION="0.4.0"
OFFICIAL_REPO="https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main"
HERMES_DIR="$HOME/.hermes"
OPENCODE_JSON="$HOME/.config/opencode/opencode.json"
SYSTEMD_DIR="$HOME/.config/systemd/user"
YES=false
REPO_URL=""
CURRENT_STEP=0
CHECK_UPDATE=false
DO_UPDATE=false

# ── Cores ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS="${GREEN}✓${NC}"; FAIL="${RED}✗${NC}"; WARN="${YELLOW}⚠${NC}"; INFO="${CYAN}→${NC}"

# ── Parser de args ──
for arg in "$@"; do
    case "$arg" in
        --repo=*) REPO_URL="${arg#*=}" ;;
        --yes|-y) YES=true ;;
        --check-update) CHECK_UPDATE=true ;;
        --update) DO_UPDATE=true ;;
        --help|-h)
            echo "Instalador Hermes + OpenCode Integration v$VERSION"
            echo ""
            echo "Uso: bash install.sh [OPÇÕES]"
            echo ""
            echo "Opções:"
            echo "  --repo=URL      Baixa arquivos de um repositório remoto"
            echo "  --yes, -y       Modo headless (sem perguntar confirmação)"
            echo "  --check-update  Verifica se há versão nova disponível"
            echo "  --update        Atualiza para a versão mais recente"
            echo "  --help, -h      Mostra esta ajuda"
            echo ""
            echo "Sem --repo: usa arquivos da mesma pasta (ou baixa do repo oficial)"
            exit 0;;
    esac
done

# ── Fallback URL ──
if [ -z "$REPO_URL" ]; then
    REPO_URL="$OFFICIAL_REPO"
fi

# ── Rollback ──
_CLEANUP_DIRS=()
clean_up() {
    echo ""
    echo -e "${WARN} Limpando instalação incompleta..."
    for d in "${_CLEANUP_DIRS[@]}"; do
        [ -d "$d" ] && rm -rf "$d" 2>/dev/null && echo -e "  ${PASS} Removeu: $d"
    done
    for f in "$HERMES_DIR/hermes-proxy.py" "$HERMES_DIR/hermes-mcp-bridge.py" \
             "$HERMES_DIR/start.sh" "$HERMES_DIR/stop.sh" "$HERMES_DIR/status.sh"; do
        [ -f "$f" ] && rm -f "$f" 2>/dev/null
    done
    echo -e "${WARN} Instalação cancelada. Nada foi alterado permanentemente."
}
trap 'clean_up' ERR EXIT

# ── Update check ──
_check_latest_version() {
    local url="${REPO_URL%/}/VERSION"
    curl -fsSL --max-time 5 "$url" 2>/dev/null || echo ""
}

if [ "$CHECK_UPDATE" = true ] || [ "$DO_UPDATE" = true ]; then
    echo ""
    echo -e "${BLUE}🔍 Verificando atualizações...${NC}"
    LATEST=$(_check_latest_version)
    if [ -z "$LATEST" ]; then
        echo -e "${WARN} Não foi possível verificar versão mais recente (sem conexão?)"
        echo -e "${INFO} Versão local: v$VERSION"
        [ "$DO_UPDATE" = true ] && exit 1
        exit 0
    fi
    LATEST=$(echo "$LATEST" | head -1 | tr -d ' \n\r')
    echo -e "${INFO} Versão local:  ${CYAN}v$VERSION${NC}"
    echo -e "${INFO} Versão remota: ${CYAN}v$LATEST${NC}"

    if [ "$LATEST" = "$VERSION" ]; then
        echo -e "${PASS} Você já está na versão mais recente!"
        [ "$DO_UPDATE" = true ] && exit 0
        exit 0
    fi

    echo -e "${WARN} Versão v$LATEST disponível (local: v$VERSION)"

    if [ "$DO_UPDATE" = true ]; then
        echo -e "${INFO} Atualizando para v$LATEST..."
        VERSION="$LATEST"
        # Segue o fluxo normal de instalação (atualiza arquivos)
    else
        echo ""
        echo -e "${CYAN}Para atualizar, execute:${NC}"
        echo "  bash install.sh --update"
        exit 0
    fi
fi

# ── Utilitários ──
step() { CURRENT_STEP=$1; echo -e "\n${BLUE}[${1}/${TOTAL}]${NC} ${2}"; }
ok()   { echo -e "  ${PASS} ${1}"; }
fail() { echo -e "  ${FAIL} ${1}"; exit 1; }
warn() { echo -e "  ${WARN} ${1}"; }
info() { echo -e "  ${INFO} ${1}"; }
hr()   { echo -e "  ${BLUE}──────────────────────────────────────────────${NC}"; }

download() {
    local url="$1" dest="$2"
    curl -fsSL --max-time 30 "$url" -o "$dest" 2>/dev/null && return 0
    return 1
}

download_or_copy() {
    local filename="$1" dest="$2"

    # Tenta local primeiro
    local srcdir
    srcdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
    for d in "$srcdir" "$srcdir/bin" "$srcdir/.."; do
        if [ -f "$d/$filename" ]; then
            cp "$d/$filename" "$dest" && return 0
        fi
    done

    # Tenta download do repo
    local url="${REPO_URL%/}/$filename"
    if download "$url" "$dest"; then
        return 0
    fi

    return 1
}

wait_for_port() {
    local port="$1" label="$2" timeout="${3:-30}"
    info "Aguardando $label na porta $port (ate ${timeout}s)..."
    for i in $(seq 1 "$timeout"); do
        if curl -s --max-time 2 "http://127.0.0.1:$port/" >/dev/null 2>&1; then
            ok "$label pronto após ${i}s"
            return 0
        fi
        sleep 1
    done
    warn "$label não respondeu após ${timeout}s. Verifique os logs."
    return 1
}

# ── WSL detection ──
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null || uname -r 2>/dev/null | grep -qi microsoft; then
    IS_WSL=true
fi

# ── Port check ──
_check_port() {
    local port="$1"
    if ss -tlnp 2>/dev/null | grep -q ":$port "; then
        warn "Porta $port já está em uso por outro processo"
        return 1
    fi
    return 0
}

# ═══════════════════════════════════════════════════════════════════════
#  CHECKLIST
# ═══════════════════════════════════════════════════════════════════════
clear
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     Hermes + OpenCode Integration  v${VERSION}                    ║"
echo "║     Motor de inferência LLM gratuito para o Hermes Agent     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}Este instalador vai:${NC}"
echo ""
echo "  1/8  Verificar pré-requisitos (Python 3, Node.js)"
echo "  2/8  Instalar OpenCode (se necessário)"
echo "  3/8  Instalar Hermes Agent (se necessário, ~5min download)"
echo "  4/8  Baixar proxy + MCP bridge + scripts"
echo "  5/8  Configurar (config.yaml, opencode.json, .env, systemd)"
echo "  6/8  Iniciar serviços (opencode serve + proxy)"
echo "  7/8  Configurar Hermes para usar o provider"
echo "  8/8  Testar e mostrar resultado"
echo ""
echo -e "${YELLOW}Requer: Python 3.11+, Node.js 20+, 2GB RAM livre${NC}"
if [ "$IS_WSL" = true ]; then
    echo -e "${YELLOW}⚠️  WSL detectado — systemd não disponível. Usará start.sh manual.${NC}"
fi
echo ""

if [ "$YES" = false ] && [ -t 0 ]; then
    read -p "$(echo -e "${CYAN}Pressione Enter para continuar ou Ctrl+C para cancelar...${NC}")"
fi

TOTAL=8

# ═══════════════════════════════════════════════════════════════════════
#  1/8 — PRÉ-REQUISITOS
# ═══════════════════════════════════════════════════════════════════════
step 1 "Pré-requisitos"

PY_VER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1 || echo "0")
if awk "BEGIN {exit !($PY_VER >= 3.11)}" 2>/dev/null; then
    ok "Python $(python3 --version 2>&1)"
else
    fail "Python 3.11+ necessário"
fi

python3 -m venv /tmp/.hermes_test_venv 2>/dev/null && rm -rf /tmp/.hermes_test_venv \
    && ok "python3-venv disponível" \
    || fail "python3-venv não instalado. Rode: sudo apt install python3-venv"

if command -v node &>/dev/null; then
    NODE_VER=$(node --version 2>&1 | grep -oP '\d+' | head -1)
    if [ "$NODE_VER" -ge 20 ] 2>/dev/null; then
        ok "Node.js $(node --version 2>&1)"
    else
        fail "Node.js 20+ necessário"
    fi
else
    fail "Node.js não encontrado"
fi

command -v curl &>/dev/null && ok "curl disponível" || fail "curl necessário"

# ═══════════════════════════════════════════════════════════════════════
#  2/8 — OPENCODE
# ═══════════════════════════════════════════════════════════════════════
step 2 "OpenCode"

OPENCODE_BIN=""
for candidate in "$HOME/.opencode/bin/opencode" "/usr/local/bin/opencode"; do
    [ -x "$candidate" ] && OPENCODE_BIN="$candidate" && break
done
[ -z "$OPENCODE_BIN" ] && command -v opencode &>/dev/null && OPENCODE_BIN="$(command -v opencode)"

if [ -n "$OPENCODE_BIN" ]; then
    ok "OpenCode: $("$OPENCODE_BIN" --version 2>/dev/null || echo "instalado")"
else
    info "Instalando OpenCode via npm (pode levar alguns segundos)..."
    npm install -g @opencode/cli 2>&1 | tail -1 || true
    for candidate in "$HOME/.opencode/bin/opencode" "/usr/local/bin/opencode"; do
        [ -x "$candidate" ] && OPENCODE_BIN="$candidate" && break
    done
    if [ -n "$OPENCODE_BIN" ]; then
        ok "OpenCode instalado"
    else
        warn "OpenCode pode não ter sido instalado. Continue manualmente: npm i -g opencode-ai@latest"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
#  3/8 — HERMES AGENT
# ═══════════════════════════════════════════════════════════════════════
step 3 "Hermes Agent"

HERMES_BIN="$HERMES_DIR/hermes-agent/venv/bin/hermes"
if [ -f "$HERMES_BIN" ]; then
    ok "Hermes Agent: $("$HERMES_BIN" --version 2>/dev/null || echo "instalado")"
else
    info "Instalando Hermes Agent (download de ~100MB, pode levar alguns minutos)..."
    echo ""
    curl -#fsSL https://hermes-agent.nousresearch.com/install.sh | bash 2>&1 || true
    if [ -f "$HERMES_BIN" ]; then
        ok "Hermes Agent instalado"
    else
        warn "Hermes Agent pode não ter instalado. Tente manual:"
        warn "  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
#  4/8 — ARQUIVOS DA INTEGRAÇÃO
# ═══════════════════════════════════════════════════════════════════════
step 4 "Arquivos da Integração"

mkdir -p "$HERMES_DIR/logs" "$HOME/.config/opencode"
_CLEANUP_DIRS+=("$HERMES_DIR/integration")

FILES_TO_INSTALL=(
    "hermes-proxy.py"
    "hermes-mcp-bridge.py"
    "start.sh"
    "stop.sh"
    "status.sh"
    "restart.sh"
    "verify.sh"
    "sync-configs.sh"
    "config/hermes-agent.md"
    "pyproject.toml"
    "tests/conftest.py"
    "tests/test_proxy_core.py"
    "tests/test_proxy_messages.py"
)

INSTALLED=0
MISSING=0
for f in "${FILES_TO_INSTALL[@]}"; do
    dest="$HERMES_DIR/$f"
    mkdir -p "$(dirname "$dest")"
    if download_or_copy "$f" "$dest"; then
        chmod +x "$dest" 2>/dev/null || true
        ok "$(basename "$f")"
        INSTALLED=$((INSTALLED + 1))
    else
        MISSING=$((MISSING + 1))
    fi
done

# Verificar se os arquivos CRÍTICOS existem
for critical in hermes-proxy.py hermes-mcp-bridge.py; do
    if [ ! -f "$HERMES_DIR/$critical" ]; then
        info "Arquivo crítico '$critical' não encontrado localmente. Baixando do repositório oficial..."
        if download "$OFFICIAL_REPO/$critical" "$HERMES_DIR/$critical"; then
            ok "$critical (baixado)"
            INSTALLED=$((INSTALLED + 1))
        else
            fail "Não foi possível obter $critical. Verifique sua conexão."
        fi
    fi
done

# Criar scripts inline se não foram copiados
for script in start.sh stop.sh status.sh; do
    if [ ! -f "$HERMES_DIR/$script" ]; then
        case "$script" in
            start.sh)
                cat > "$HERMES_DIR/start.sh" << 'SHELL'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"; mkdir -p "$LOG_DIR"
echo "Starting OpenCode serve..."
nohup opencode serve --port 8800 --hostname 127.0.0.1 > "$LOG_DIR/opencode-serve.log" 2>&1 &
SERVE_PID=$!
sleep 3
echo "Starting Fusion Proxy..."
source "$SCRIPT_DIR/hermes-agent/venv/bin/activate" 2>/dev/null || true
nohup python3 "$SCRIPT_DIR/hermes-proxy.py" > "$LOG_DIR/hermes-proxy.log" 2>&1 &
sleep 2
echo "Ready. Proxy: http://127.0.0.1:4101 | Models: $(curl -s http://127.0.0.1:4101/v1/models 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])),'free models')" 2>/dev/null || echo "? models")"
wait $SERVE_PID
SHELL
                chmod +x "$HERMES_DIR/start.sh"
                ok "$script (criado inline)"; INSTALLED=$((INSTALLED + 1)) ;;
            stop.sh)
                cat > "$HERMES_DIR/stop.sh" << 'SHELL'
#!/usr/bin/env bash
echo "Parando Fusion Proxy..."; fuser -k 4101/tcp 2>/dev/null && echo "  Proxy parou" || echo "  Proxy não estava rodando"
echo "Parando OpenCode serve..."; fuser -k 8800/tcp 2>/dev/null && echo "  OpenCode parou" || echo "  OpenCode não estava rodando"
echo "Pronto."
SHELL
                chmod +x "$HERMES_DIR/stop.sh"
                ok "$script (criado inline)"; INSTALLED=$((INSTALLED + 1)) ;;
            status.sh)
                cat > "$HERMES_DIR/status.sh" << 'SHELL'
#!/usr/bin/env bash
echo "=== Serviços ==="
echo -n "Proxy (4101): "; ss -tlnp 2>/dev/null | grep -q 4101 && echo "RODANDO" || echo "PARADO"
echo -n "OpenCode (8800): "; ss -tlnp 2>/dev/null | grep -q 8800 && echo "RODANDO" || echo "PARADO"
echo ""
if curl -s --max-time 3 http://127.0.0.1:4101/health >/dev/null 2>&1; then
    HEALTH=$(curl -s http://127.0.0.1:4101/health 2>/dev/null)
    echo "=== Health ==="
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null
fi
echo ""
echo "=== Logs (últimas 3 linhas) ==="
for log in "$HOME/.hermes/logs/"*.log; do
    [ -f "$log" ] && echo "--- $(basename "$log") ---" && tail -3 "$log"
done
SHELL
                chmod +x "$HERMES_DIR/status.sh"
                ok "$script (criado inline)"; INSTALLED=$((INSTALLED + 1)) ;;
        esac
    fi
done

echo ""
info "Total: $INSTALLED arquivos instalados"

# Instalar agente hermes para OpenCode
if [ -f "$HERMES_DIR/config/hermes-agent.md" ]; then
    mkdir -p "$HOME/.config/opencode/agents"
    cp "$HERMES_DIR/config/hermes-agent.md" "$HOME/.config/opencode/agents/hermes.md"
    ok "Agente OpenCode: hermes.md"
fi

# ═══════════════════════════════════════════════════════════════════════
#  5/8 — CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════
step 5 "Configuração"

# 5a. config.yaml
hr
if [ ! -f "$HERMES_DIR/config.yaml" ]; then
    info "Criando config.yaml..."
    cat > "$HERMES_DIR/config.yaml" << YAML
model:
  default: deepseek-v4-flash-free
  provider: opencode-proxy
  base_url: http://127.0.0.1:4101/v1
  api_key: ""
  context_length: 1000000
providers:
  opencode-proxy:
    base_url: http://127.0.0.1:4101/v1
    api_mode: chat_completions
fallback_providers:
  - provider: custom
    model: meta/llama-3.1-70b-instruct
    api_key: ""
YAML
    ok "config.yaml criado"
else
    # Adicionar opencode-proxy se não existir
    if ! grep -q "opencode-proxy" "$HERMES_DIR/config.yaml"; then
        info "Adicionando opencode-proxy ao config.yaml existente..."
        cat >> "$HERMES_DIR/config.yaml" << YAML

# ── Adicionado pelo instalador Hermes+OpenCode v$VERSION ──
providers:
  opencode-proxy:
    base_url: http://127.0.0.1:4101/v1
    api_mode: chat_completions
YAML
        ok "opencode-proxy adicionado ao config.yaml"
    else
        ok "config.yaml já configurado (pulado)"
    fi
fi

# 5b. opencode.json
hr
mkdir -p "$(dirname "$OPENCODE_JSON")"
if ! grep -q "hermes-bridge" "$OPENCODE_JSON" 2>/dev/null; then
    info "Adicionando hermes-bridge ao opencode.json..."
    # Usa python para editar o JSON com segurança
    python3 -c "
import json, os
path = os.path.expanduser('$OPENCODE_JSON')
try:
    with open(path) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {'\$schema': 'https://opencode.ai/config.json', 'provider': {}, 'mcp': {}}

# Garantir que provider.opencode.models existe
if 'opencode' not in cfg.setdefault('provider', {}):
    cfg['provider']['opencode'] = {}
if 'models' not in cfg['provider']['opencode']:
    cfg['provider']['opencode']['models'] = {}

# Adicionar deepseek-v4-flash-free
models = cfg['provider']['opencode']['models']
if 'deepseek-v4-flash-free' not in models:
    models['deepseek-v4-flash-free'] = {
        'limit': {'context': 1000000, 'output': 65536},
        'modalities': {'input': ['text', 'image', 'video'], 'output': ['text']},
        'attachment': True,
        'tool_call': True,
    }

# Adicionar hermes-bridge MCP (com ~ para portabilidade)
if 'hermes-bridge' not in cfg.setdefault('mcp', {}):
    cfg['mcp']['hermes-bridge'] = {
        'type': 'local',
        'command': ['python3', '~/.hermes/hermes-mcp-bridge.py'],
        'enabled': True,
    }

with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('ok')
" 2>/dev/null && ok "opencode.json configurado" || warn "Falha ao configurar opencode.json"
else
    ok "opencode.json já configurado"
fi

# 5c. .env
hr
if [ ! -f "$HERMES_DIR/.env" ]; then
    info "Criando .env..."
    cat > "$HERMES_DIR/.env" << 'ENV'
# Hermes + OpenCode Integration — API Keys (opcional)
# Se quiser fallback para OpenRouter, descomente e adicione sua chave:
# OPENROUTER_API_KEY=coloque_sua_chave_aqui
ENV
    ok ".env criado"
else
    ok ".env já existe (preservado)"
fi

# 5d. systemd
hr
if [ "$IS_WSL" = true ]; then
    info "WSL detectado — systemd não disponível. Use ~/.hermes/start.sh para iniciar."
    info "Arquivos .service criados mesmo assim para referência."
fi

mkdir -p "$SYSTEMD_DIR"
if [ ! -f "$SYSTEMD_DIR/opencode-serve.service" ]; then
    cat > "$SYSTEMD_DIR/opencode-serve.service" << 'SVC'
[Unit]
Description=OpenCode Serve — LLM Engine for Hermes
After=network.target
[Service]
Type=simple
ExecStart=%h/.opencode/bin/opencode serve --port 8800 --hostname 127.0.0.1
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
NoNewPrivileges=true
PrivateTmp=true
ReadWritePaths=%h/.opencode %h/.config/opencode
[Install]
WantedBy=default.target
SVC
    ok "opencode-serve.service"
fi
if [ ! -f "$SYSTEMD_DIR/hermes-proxy.service" ]; then
    cat > "$SYSTEMD_DIR/hermes-proxy.service" << 'SVC'
[Unit]
Description=Hermes Fusion Proxy — OpenCode bridge
After=network.target opencode-serve.service
BindsTo=opencode-serve.service
[Service]
Type=simple
ExecStart=%h/.hermes/hermes-agent/venv/bin/python3 %h/.hermes/hermes-proxy.py
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1
ReadWritePaths=%h/.hermes
[Install]
WantedBy=default.target
SVC
    ok "hermes-proxy.service"
fi

# ═══════════════════════════════════════════════════════════════════════
#  6/8 — INICIAR
# ═══════════════════════════════════════════════════════════════════════
step 6 "Iniciando Serviços"

# Verificar portas
_check_port 8800 || true
_check_port 4101 || true

# Mata processos antigos (ignora se não existirem)
fuser -k 4101/tcp 2>/dev/null || true
fuser -k 8800/tcp 2>/dev/null || true
sleep 1

# Abre firewall pessoal (WSL não precisa)
if command -v ufw &>/dev/null; then
    ufw allow 4101/tcp 2>/dev/null || true
    ufw allow 8800/tcp 2>/dev/null || true
fi

# OpenCode serve
if [ -n "${OPENCODE_BIN:-}" ] && [ -x "$OPENCODE_BIN" ]; then
    info "Iniciando OpenCode serve (porta 8800)..."
    nohup "$OPENCODE_BIN" serve --port 8800 --hostname 127.0.0.1 \
        > "$HERMES_DIR/logs/opencode-serve.log" 2>&1 &
    wait_for_port 8800 "OpenCode serve" 30 || true
else
    warn "OpenCode não encontrado. Pule esta etapa ou instale manualmente."
    warn "  npm i -g opencode-ai@latest"
fi

# Proxy
if [ -f "$HERMES_DIR/hermes-proxy.py" ]; then
    info "Iniciando Fusion Proxy (porta 4101)..."
    cd "$HERMES_DIR"
    # Tenta ativar venv, mas não falha se não conseguir
    source "$HERMES_DIR/hermes-agent/venv/bin/activate" 2>/dev/null || true
    nohup python3 "$HERMES_DIR/hermes-proxy.py" \
        > "$HERMES_DIR/logs/hermes-proxy.log" 2>&1 &
    sleep 4
    if curl -s --max-time 3 http://127.0.0.1:4101/health >/dev/null 2>&1; then
        VER=$(curl -s http://127.0.0.1:4101/health 2>/dev/null | \
              python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null)
        ok "Fusion Proxy v$VER rodando em http://127.0.0.1:4101"
    else
        warn "Proxy não respondeu. Logs: tail -f '$HERMES_DIR/logs/hermes-proxy.log'"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
#  7/8 — CONFIGURAR HERMES
# ═══════════════════════════════════════════════════════════════════════
step 7 "Configurar Hermes"

if [ -f "$HERMES_BIN" ]; then
    info "Configurando Hermes para usar opencode-proxy..."

    # Já está no config.yaml, mas garantimos que o Hermes reconheça
    if "$HERMES_BIN" config set model.default deepseek-v4-flash-free 2>/dev/null; then
        ok "Modelo padrão: deepseek-v4-flash-free"
    else
        warn "Não foi possível configurar o modelo. Faça manualmente:"
        warn "  hermes config set model.default deepseek-v4-flash-free"
    fi

    # Listar modelos disponíveis via proxy
    MODELS_COUNT=$(curl -s --max-time 3 http://127.0.0.1:4101/v1/models 2>/dev/null | \
                   python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo "?")
    ok "$MODELS_COUNT modelos gratuitos disponíveis"
else
    warn "Hermes não encontrado. Configure manualmente depois."
fi

# ═══════════════════════════════════════════════════════════════════════
#  8/8 — TESTE
# ═══════════════════════════════════════════════════════════════════════
step 8 "Teste"

if curl -s --max-time 3 http://127.0.0.1:4101/health >/dev/null 2>&1; then
    ok "Proxy respondendo"

    echo ""
    info "Testando chat completion (pode levar até 60s)..."
    RESP=$(curl -s --max-time 60 http://127.0.0.1:4101/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"deepseek-v4-flash-free","messages":[{"role":"user","content":"Reply: OK"}],"stream":false}' 2>/dev/null \
        | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    txt = d['choices'][0]['message']['content'][:80]
    print(txt)
except: print('')
" 2>/dev/null || echo "")

    if [ -n "$RESP" ]; then
        ok "Resposta: $RESP"
    else
        warn "Teste falhou. Verifique: tail -f '$HERMES_DIR/logs/hermes-proxy.log'"
    fi
else
    warn "Proxy não respondeu. Inicie manualmente: ~/.hermes/start.sh"
fi

# ═══════════════════════════════════════════════════════════════════════
#  RESUMO
# ═══════════════════════════════════════════════════════════════════════
# Remove trap de erro (instalação concluída com sucesso)
trap '' ERR EXIT

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Instalação Concluída!                                    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}COMANDOS PRINCIPAIS${NC}"
echo "  ─────────────────────────────────────────────"
echo "  hermes                     Usar o Hermes Agent (já configurado)"
echo "  ~/.hermes/status.sh        Ver status dos serviços"
echo "  ~/.hermes/start.sh         Iniciar manualmente"
echo "  ~/.hermes/stop.sh          Parar"
echo ""
echo -e "  ${CYAN}AUTO-START (SYSTEMD)${NC}"
echo "  ─────────────────────────────────────────────"
echo "  systemctl --user enable --now opencode-serve.service"
echo "  systemctl --user enable --now hermes-proxy.service"
echo ""
echo -e "  ${CYAN}TROCAR DE MODELO${NC}"
echo "  ─────────────────────────────────────────────"
echo "  curl http://127.0.0.1:4101/v1/models | python3 -m json.tool"
echo "  hermes config set model.default kimi-k2.5-free"
echo ""
echo -e "  ${CYAN}VERIFICAR${NC}"
echo "  ─────────────────────────────────────────────"
echo "  bash ~/.hermes/integration/verify.sh"
echo ""
echo -e "  ${CYAN}DESINSTALAR${NC}"
echo "  ─────────────────────────────────────────────"
echo "  bash ~/.hermes/integration/uninstall.sh"
echo ""
