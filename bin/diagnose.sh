#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  diagnose.sh — Relatório completo de diagnóstico
#  Uso: bash diagnose.sh > relatorio.txt
#  Coleta: versões, configs, logs, portas, serviços, testes
# ═══════════════════════════════════════════════════════════════════════
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Diagnóstico Hermes + OpenCode                             ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Sistema ────────────────────────────────────────────────────────
echo "═══ 1. Sistema ═══"
echo "Host: $(uname -a)"
echo "Uptime: $(uptime -p)"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h ~ | tail -1 | awk '{print $3 "/" $2}')"
echo ""

# ── 2. Versões ────────────────────────────────────────────────────────
echo "═══ 2. Versões ═══"
echo "Python: $(python3 --version 2>/dev/null || echo 'N/A')"
echo "Node:    $(node --version 2>/dev/null || echo 'N/A')"
echo "OpenCode: $(opencode --version 2>/dev/null || echo 'N/A')"
echo "Hermes:  $(hermes --version 2>/dev/null || hermes-agent --version 2>/dev/null || echo 'N/A')"
echo "Proxy:   $(python3 -c "import hermes_proxy; print(getattr(hermes_proxy, '__version__', '0.3.0'))" 2>/dev/null || echo '0.3.0')"
echo "Bridge:  $(python3 -c "import hermes_mcp_bridge; print('0.2.0')" 2>/dev/null || echo '0.2.0')"
echo ""

# ── 3. Processos ──────────────────────────────────────────────────────
echo "═══ 3. Processos ═══"
echo "--- opencode serve ---"
ps aux | grep "[o]pencode serve" || echo "  não rodando"
echo "--- hermes-proxy ---"
ps aux | grep "[h]ermes-proxy" || echo "  não rodando"
echo "--- hermes-mcp-bridge ---"
ps aux | grep "[h]ermes-mcp-bridge" || echo "  não rodando"
echo ""

# ── 4. Portas ─────────────────────────────────────────────────────────
echo "═══ 4. Portas ═══"
echo "Porta 4101 (proxy):"
ss -tlnp | grep 4101 || echo "  livre/não escutando"
echo "Porta 8800 (opencode serve):"
ss -tlnp | grep 8800 || echo "  livre/não escutando"
echo ""

# ── 5. Configs ────────────────────────────────────────────────────────
echo "═══ 5. Config Hermes ═══"
if [ -f ~/.hermes/config.yaml ]; then
    echo "--- Fingerprint ---"
    grep -E "^(model:|  default:|  provider:|  base_url:|  context_length:|mcp_servers:)" ~/.hermes/config.yaml
    echo "--- MCP Servers ---"
    grep -E "^  [a-z]" ~/.hermes/config.yaml | grep -E "(command:|enabled:)" | head -20
else
    echo "  ARQUIVO AUSENTE"
fi
echo ""

echo "═══ 6. Config OpenCode ═══"
if [ -f ~/.config/opencode/opencode.json ]; then
    python3 -c "
import json
with open('$HOME/.config/opencode/opencode.json') as f:
    d = json.load(f)
oc = d.get('provider',{}).get('opencode',{}).get('models',{})
k = list(oc.keys())[0] if oc else '?'
print(f'Model ativo: {k}')
m = oc.get(k,{})
print(f'  modalities: {m.get(\"modalities\",{})}')
print(f'  attachment: {m.get(\"attachment\")}')
print(f'  tool_call: {m.get(\"tool_call\")}')
print(f'  limit: {m.get(\"limit\",{})}')
mcps = list(d.get('mcp',{}).keys())
print(f'MCP servers ({len(mcps)}): {mcps}')
" 2>/dev/null || echo "  erro ao ler"
else
    echo "  ARQUIVO AUSENTE"
fi
echo ""

# ── 7. Services Health ────────────────────────────────────────────────
echo "═══ 7. Health Checks ═══"
echo "--- OpenCode serve (porta 8800) ---"
curl -s --max-time 5 http://127.0.0.1:8800/api/model 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Modelos: {len(d)} disponíveis')
    for m in d[:3]:
        print(f'    - {m.get(\"id\",\"?\")}')
except: print('  não respondeu')
" 2>/dev/null || echo "  não respondeu"

echo "--- Proxy (porta 4101) ---"
curl -s --max-time 5 http://127.0.0.1:4101/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  não respondeu"
echo ""

# ── 8. Session Map ────────────────────────────────────────────────────
echo "═══ 8. Sessions Ativas ═══"
curl -s --max-time 5 http://127.0.0.1:4101/health 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Active sessions: {d.get(\"active_sessions\",\"?\")}')
    print(f'  Requests: {d.get(\"requests\",\"?\")}')
    print(f'  Uptime: {d.get(\"uptime\",\"?\")}s')
except: print('  proxy offline')
" 2>/dev/null || echo "  proxy offline"
echo ""

# ── 9. Logs Recentes ──────────────────────────────────────────────────
echo "═══ 9. Últimas 10 linhas dos Logs ═══"
echo "--- ~/.hermes/logs/hermes-proxy.log ---"
tail -10 ~/.hermes/logs/hermes-proxy.log 2>/dev/null || echo "  (vazio/inexistente)"
echo ""
echo "--- /tmp/osc*.log ---"
ls -1t /tmp/osc*.log 2>/dev/null | head -3 | while read f; do
    echo "LOG: $f"
    tail -5 "$f" 2>/dev/null
done
echo ""

# ── 10. Testes ────────────────────────────────────────────────────────
echo "═══ 10. Testes ═══"
echo "--- Chat rápido ---"
curl -s --max-time 60 http://127.0.0.1:4101/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-v4-flash-free","messages":[{"role":"user","content":"Say hi"}],"stream":false}' \
    2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    c = d.get('choices',[{}])[0].get('message',{}).get('content','')[:100]
    u = d.get('usage',{})
    print(f'  Content: {c}')
    print(f'  Usage: {u}')
except: print('  Falhou')
" 2>/dev/null || echo "  Falhou"

echo ""
echo "═══ Fim do Diagnóstico ═══"
