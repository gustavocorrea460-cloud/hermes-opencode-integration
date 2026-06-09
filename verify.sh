#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  verify.sh — Verifica se a integração Hermes + OpenCode está correta
#  Uso: bash verify.sh
#  Saída: ✅/❌/⚠️  para cada componente
# ═══════════════════════════════════════════════════════════════════════
set -e
FAIL=0
WARN=0

red='\033[0;31m'; green='\033[0;32m'; yellow='\033[1;33m'; blue='\033[0;34m'; nc='\033[0m'
ok="${green}✅${nc}"; fail="${red}❌${nc}"; warn="${yellow}⚠️${nc}"; info="${blue}ℹ️${nc}"

echo ""
echo -e "${blue}══════════════════════════════════════════════════════════${nc}"
echo -e "${blue}  Verificação da Integração Hermes + OpenCode${nc}"
echo -e "${blue}══════════════════════════════════════════════════════════${nc}"
echo ""

# ── 1. Pré-requisitos ──────────────────────────────────────────────────
echo -e "${blue}[1/11] Pré-requisitos${nc}"

PY_VER=$(python3 --version 2>/dev/null || true)
if [[ "$PY_VER" =~ Python\ 3\.(1[1-9]|[2-9][0-9])|Python\ 4 ]]; then
    echo -e "  $ok Python: $PY_VER"
else
    echo -e "  $fail Python 3.11+ necessário (found: ${PY_VER:-none})"
    FAIL=1
fi

NODE_VER=$(node --version 2>/dev/null || true)
if [[ "$NODE_VER" =~ v(2[0-9]|[3-9][0-9])\. ]]; then
    echo -e "  $ok Node.js: $NODE_VER"
else
    echo -e "  $fail Node.js 20+ necessário (found: ${NODE_VER:-none})"
    FAIL=1
fi

# ── 2. OpenCode ────────────────────────────────────────────────────────
echo ""
echo -e "${blue}[2/11] OpenCode${nc}"

OPENCODE_BIN=$(command -v opencode 2>/dev/null || true)
if [ -n "$OPENCODE_BIN" ]; then
    OC_VER=$($OPENCODE_BIN --version 2>/dev/null || echo "unknown")
    echo -e "  $ok opencode: $OC_VER ($OPENCODE_BIN)"
else
    echo -e "  $fail opencode não encontrado no PATH"
    echo -e "  $info Instale com: npm install -g @opencode-ai/sdk"
    FAIL=1
fi

# ── 3. Hermes Agent ────────────────────────────────────────────────────
echo ""
echo -e "${blue}[3/11] Hermes Agent${nc}"

HERMES_DIR="$HOME/.hermes/hermes-agent"
if [ -d "$HERMES_DIR" ]; then
    echo -e "  $ok Diretório: $HERMES_DIR"
    VENV_PATH=""
    if [ -f "$HERMES_DIR/venv/bin/python3" ]; then
        VENV_PATH="$HERMES_DIR/venv/bin/python3"
        echo -e "  $ok Virtualenv: venv/"
    elif [ -f "$HERMES_DIR/.venv/bin/python3" ]; then
        VENV_PATH="$HERMES_DIR/.venv/bin/python3"
        echo -e "  $ok Virtualenv: .venv/"
    else
        echo -e "  $fail Virtualenv não encontrada (venv/ ou .venv/)"
        FAIL=1
    fi
else
    echo -e "  $fail Diretório $HERMES_DIR não existe"
    FAIL=1
fi

# ── 4. Integration Files ───────────────────────────────────────────────
echo ""
echo -e "${blue}[4/11] Arquivos da Integração${nc}"

INTEGRATION_FILES=("hermes-proxy.py" "hermes-mcp-bridge.py" "start.sh" "stop.sh" "status.sh")
for f in "${INTEGRATION_FILES[@]}"; do
    if [ -f "$HOME/.hermes/$f" ]; then
        echo -e "  $ok ~/.hermes/$f"
    else
        echo -e "  $fail ~/.hermes/$f ausente"
        echo -e "  $info Copie de integration/bin/ ou rode install.sh"
        FAIL=1
    fi
done

# ── 5. Config Hermes ───────────────────────────────────────────────────
echo ""
echo -e "${blue}[5/11] Config Hermes${nc}"

HCONFIG="$HOME/.hermes/config.yaml"
if [ -f "$HCONFIG" ]; then
    echo -e "  $ok ~/.hermes/config.yaml"

    # Provider
    if grep -q "opencode-proxy" "$HCONFIG"; then
        echo -e "  $ok Provider: opencode-proxy"
    else
        echo -e "  $fail Provider não configurado como opencode-proxy"
        FAIL=1
    fi

    # Context length
    if grep -q "context_length: 1000000" "$HCONFIG"; then
        echo -e "  $ok Context length: 1.000.000"
    else
        echo -e "  $warn context_length não configurado como 1M"
        WARN=1
    fi

    # MCP servers
    if grep -q "mcp_servers:" "$HCONFIG"; then
        echo -e "  $ok Seção mcp_servers: presente"
        for mcp in threejs-devtools gsap-master figma mcp-three sketchfab context7; do
            if grep -q "$mcp" "$HCONFIG"; then
                echo -e "  $ok MCP server: $mcp"
            else
                echo -e "  $warn MCP server $mcp não encontrado no config.yaml"
                WARN=1
            fi
        done
    else
        echo -e "  $warn Nenhum MCP server configurado no Hermes"
        WARN=1
    fi

    # YAML syntax validation
    if python3 -c "import yaml; yaml.safe_load(open('$HCONFIG'))" 2>/dev/null; then
        echo -e "  $ok YAML syntax: válido"
    else
        echo -e "  $fail YAML syntax: INVÁLIDO!"
        echo -e "  $info Rode: python3 -c \"import yaml; yaml.safe_load(open('$HCONFIG'))\""
        FAIL=1
    fi
else
    echo -e "  $fail ~/.hermes/config.yaml ausente"
    FAIL=1
fi

# ── 6. Config OpenCode ─────────────────────────────────────────────────
echo ""
echo -e "${blue}[6/11] Config OpenCode${nc}"

OC_CONFIG="$HOME/.config/opencode/opencode.json"
if [ -f "$OC_CONFIG" ]; then
    echo -e "  $ok $OC_CONFIG"

    # hermes-bridge MCP
    if grep -q "hermes-bridge" "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok MCP hermes-bridge registrado"

        # Verificar path do python3 no bridge
        BRIDGE_CMD=$(python3 -c "
import json
with open('$OC_CONFIG') as f:
    d = json.load(f)
cmd = d.get('mcp',{}).get('hermes-bridge',{}).get('command',[])
print(' '.join(cmd) if cmd else '')
" 2>/dev/null)
        if echo "$BRIDGE_CMD" | grep -q "python3" && echo "$BRIDGE_CMD" | grep -q "hermes-mcp-bridge"; then
            BRIDGE_PATH=$(echo "$BRIDGE_CMD" | grep -o '/[^ ]*hermes-mcp-bridge[^ ]*' || true)
            if [ -f "$BRIDGE_PATH" ]; then
                echo -e "  $ok Bridge path: $BRIDGE_PATH"
            else
                echo -e "  $fail Bridge path NÃO encontrado: $BRIDGE_PATH"
                echo -e "  $info Corrija o path em $OC_CONFIG"
                FAIL=1
            fi
        else
            echo -e "  $fail Comando do hermes-bridge parece incorreto: $BRIDGE_CMD"
            FAIL=1
        fi
    else
        echo -e "  $fail hermes-bridge MCP não encontrado"
        FAIL=1
    fi

    # Modalities
    if grep -q '"image"' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok Modalities: image habilitado"
    else
        echo -e "  $fail Modalities: image NÃO configurado — imagens serão BLOQUEADAS pelo runtime!"
        echo -e "  $info Adicione \"image\" em modalities.input"
        FAIL=1
    fi
    if grep -q '"video"' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok Modalities: video habilitado"
    else
        echo -e "  $info Modalities: video não configurado (opcional)"
    fi
    if grep -q '"pdf"' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok Modalities: pdf habilitado"
    fi

    # attachment, tool_call, context
    if grep -q '"attachment": true' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok attachment: true"
    else
        echo -e "  $warn attachment não configurado — upload pode falhar"
        WARN=1
    fi
    if grep -q '"tool_call": true' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok tool_call: true"
    else
        echo -e "  $warn tool_call não configurado — tools podem não funcionar"
        WARN=1
    fi
    if grep -q '"context": 1000000' "$OC_CONFIG" 2>/dev/null; then
        echo -e "  $ok limit.context: 1.000.000"
    else
        echo -e "  $warn limit.context não configurado como 1M — contexto limitado"
        WARN=1
    fi

    # JSON syntax validation
    if python3 -c "import json; json.load(open('$OC_CONFIG'))" 2>/dev/null; then
        echo -e "  $ok JSON syntax: válido"
    else
        echo -e "  $fail JSON syntax: INVÁLIDO!"
        echo -e "  $info Rode: python3 -c \"import json; json.load(open('$OC_CONFIG'))\""
        FAIL=1
    fi
else
    echo -e "  $fail $OC_CONFIG ausente"
    FAIL=1
fi

# ── 7. Environment ─────────────────────────────────────────────────────
echo ""
echo -e "${blue}[7/11] Environment${nc}"

if [ -f "$HOME/.hermes/.env" ]; then
    echo -e "  $ok ~/.hermes/.env presente"
    # Check for critical keys (without exposing them)
    for key in GROQ_API_KEY FIGMA_API_KEY SKETCHFAB_API_KEY; do
        if grep -q "${key}=" "$HOME/.hermes/.env" 2>/dev/null; then
            VAL=$(grep "${key}=" "$HOME/.hermes/.env" | cut -d= -f2)
            if [ -n "$VAL" ] && [ "$VAL" != "\"\"" ]; then
                echo -e "  $ok $key configurada"
            else
                echo -e "  $warn $key está vazia"
                WARN=1
            fi
        else
            echo -e "  $warn $key não encontrada no .env"
            WARN=1
        fi
    done
else
    echo -e "  $warn ~/.hermes/.env ausente (algumas keys podem estar no config.yaml)"
    echo -e "  $info Crie a partir de: cp integration/config/.env.example ~/.hermes/.env"
    WARN=1
fi

# ── 8. MCP Bridge Test ─────────────────────────────────────────────────
echo ""
echo -e "${blue}[8/11] MCP Bridge${nc}"

# Find the MCP bridge python command from opencode.json
MCP_PYTHON=$(python3 -c "
import json
with open('$OC_CONFIG') as f:
    d = json.load(f)
cmd = d.get('mcp',{}).get('hermes-bridge',{}).get('command',[])
print(cmd[0] if len(cmd) > 0 else '')
" 2>/dev/null)
MCP_SCRIPT=$(python3 -c "
import json
with open('$OC_CONFIG') as f:
    d = json.load(f)
cmd = d.get('mcp',{}).get('hermes-bridge',{}).get('command',[])
print(cmd[1] if len(cmd) > 1 else '')
" 2>/dev/null)

if [ -n "$MCP_PYTHON" ] && [ -n "$MCP_SCRIPT" ] && [ -f "$MCP_SCRIPT" ]; then
    # Test tools/list via MCP protocol
    MCP_TEST=$(echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
        timeout 8 "$MCP_PYTHON" "$MCP_SCRIPT" 2>/dev/null || true)
    if echo "$MCP_TEST" | grep -q "hermes_"; then
        TOOL_COUNT=$(echo "$MCP_TEST" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if 'result' in d and 'tools' in d['result']:
            print(len(d['result']['tools']))
            break
    except: pass
" 2>/dev/null || echo "?")
        echo -e "  $ok MCP bridge responde tools/list ($TOOL_COUNT ferramentas)"
    else
        echo -e "  $warn MCP bridge não respondeu tools/list"
        echo -e "  $info Teste manual: echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' | timeout 5 $MCP_PYTHON $MCP_SCRIPT"
        WARN=1
    fi
else
    echo -e "  $warn MCP bridge não pôde ser testado (path inválido)"
    WARN=1
fi

# ── 9. MCP Server Binaries ─────────────────────────────────────────────
echo ""
echo -e "${blue}[9/11] MCP Server Binaries${nc}"

for bin in threejs-devtools-mcp mcp-three; do
    if command -v "$bin" &>/dev/null; then
        echo -e "  $ok $bin: $(which $bin)"
    else
        echo -e "  $warn $bin não encontrado no PATH — MCP server não disponível"
        WARN=1
    fi
done

# ── 10. Services Running ───────────────────────────────────────────────
echo ""
echo -e "${blue}[10/11] Services Rodando${nc}"

# Check port conflicts
for port in 4101 8800; do
    if ss -tlnp "sport = :$port" 2>/dev/null | grep -q "$port"; then
        : # port in use, which is expected
    fi
done

OC_SERVE=$(curl -s --max-time 3 http://127.0.0.1:8800/api/model 2>/dev/null || true)
if [ -n "$OC_SERVE" ] && echo "$OC_SERVE" | grep -q "model"; then
    echo -e "  $ok OpenCode serve (porta 8800)"
else
    echo -e "  $warn OpenCode serve não respondeu na 8800"
    echo -e "  $info Inicie com: ~/.hermes/start.sh"
    WARN=1
fi

PROXY_HEALTH=$(curl -s --max-time 3 http://127.0.0.1:4101/health 2>/dev/null || true)
if [ -n "$PROXY_HEALTH" ]; then
    echo -e "  $ok Fusion Proxy (porta 4101)"
    if echo "$PROXY_HEALTH" | grep -q '"serve_ready":true'; then
        echo -e "  $ok Proxy conectado ao OpenCode serve"
    else
        echo -e "  $warn Proxy não detectou OpenCode serve (serve_ready=false)"
        WARN=1
    fi
    SESSIONS=$(echo "$PROXY_HEALTH" | python3 -c "import sys,json;print(json.load(sys.stdin).get('active_sessions',0))" 2>/dev/null)
    echo -e "  $info Sessions ativas: $SESSIONS"
else
    echo -e "  $warn Fusion Proxy não respondeu na 4101"
    WARN=1
fi

# ── 11. End-to-End Test ────────────────────────────────────────────────
echo ""
echo -e "${blue}[11/11] Teste End-to-End${nc}"

if [ -n "$PROXY_HEALTH" ]; then
    CHAT_TEST=$(curl -s --max-time 120 http://127.0.0.1:4101/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"deepseek-v4-flash-free","messages":[{"role":"user","content":"Say hi in 2 words."}],"stream":false}' 2>/dev/null || true)
    if echo "$CHAT_TEST" | grep -q "choices"; then
        echo -e "  $ok Chat completions funcionando"
        CONTENT=$(echo "$CHAT_TEST" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    c = d.get('choices',[{}])[0].get('message',{}).get('content','')[:100]
    print(c)
except: print('?')
" 2>/dev/null || echo "?")
        echo -e "  $info Resposta: $CONTENT"
    else
        echo -e "  $warn Chat completions falhou"
        echo -e "  $info Verifique ~/.hermes/logs/hermes-proxy.log"
        WARN=1
    fi
else
    echo -e "  $warn Proxy offline — pulando teste"
    WARN=1
fi

# ── Resultado ──────────────────────────────────────────────────────────
echo ""
echo -e "${blue}══════════════════════════════════════════════════════════${nc}"
echo -e "${blue}  Resumo${nc}"
echo -e "${blue}══════════════════════════════════════════════════════════${nc}"
if [ $FAIL -gt 0 ]; then
    echo -e "  ${red}❌ $FAIL falha(s) crítica(s) — corrija antes de usar${nc}"
    echo -e "  $info Veja SETUP.md para instruções de instalação"
    echo -e "  $info Veja docs/TROUBLESHOOTING.md para soluções"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo -e "  ${yellow}⚠️  $WARN aviso(s) — funciona mas pode melhorar${nc}"
    echo -e "  $info Veja ROADMAP.md para próximos passos"
    exit 0
else
    echo -e "  ${green}✅ Tudo funcionando! Hermes está usando OpenCode como motor.${nc}"
    exit 0
fi
