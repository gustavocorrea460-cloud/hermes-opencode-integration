# CHECKLIST — Verificação Rápida

> Para humanos e agentes: confira cada item antes de concluir que a integração está OK.

## ☐ 1. Pré-requisitos
- ☐ Python 3.11+ instalado
- ☐ Node.js 20+ instalado
- ☐ `opencode` no PATH

## ☐ 2. Hermes Instalado
- ☐ `~/.hermes/hermes-agent/` existe
- ☐ `~/.hermes/hermes-agent/venv/bin/python3` ou `.venv/bin/python3` existe
- ☐ `hermes --version` funciona

## ☐ 3. OpenCode Instalado
- ☐ `opencode --version` ≥ 1.15
- ☐ `~/.opencode/bin/opencode` ou global

## ☐ 4. Arquivos da Integração
- ☐ `~/.hermes/hermes-proxy.py` existe
- ☐ `~/.hermes/hermes-mcp-bridge.py` existe
- ☐ `~/.hermes/start.sh` existe e é executável
- ☐ `~/.hermes/stop.sh` existe e é executável
- ☐ `~/.hermes/status.sh` existe e é executável

## ☐ 5. Config Hermes
- ☐ `~/.hermes/config.yaml` tem `provider: opencode-proxy`
- ☐ `~/.hermes/config.yaml` tem `base_url: http://127.0.0.1:4101/v1`
- ☐ `~/.hermes/config.yaml` tem `context_length: 1000000`
- ☐ API key do fallback (Groq) configurada
- ☐ MCP servers (threejs, gsap, figma, etc.) configurados

## ☐ 6. Config OpenCode — Modalidades (CRÍTICO)
- ☐ `modalities.input` tem `"image"` — sem isso, imagens são BLOQUEADAS pelo runtime
- ☐ `modalities.input` tem `"video"`? (opcional, se precisar de vídeo)
- ☐ `modalities.input` tem `"pdf"`? (opcional, se precisar de PDF)
- ☐ `attachment: true` — libera upload de arquivos na UI
- ☐ `tool_call: true` — libera chamada de ferramentas
- ☐ `limit.context: 1000000` — 1 milhão de tokens de contexto
- ☐ `limit.output: 65536` — 64K tokens de saída
- ☐ JSON syntax: válido (`python3 -c "import json; json.load(open('...'))"`)

## ☐ 7. Config OpenCode — MCP Bridge
- ☐ `~/.config/opencode/opencode.json` tem `hermes-bridge` MCP
- ☐ Path do python3 no `hermes-bridge.command` está correto
- ☐ Path do `hermes-mcp-bridge.py` no command existe
- ☐ MCP bridge responde `tools/list` com ferramentas prefixadas `hermes_`
- ☐ Pelo menos 10 ferramentas Hermes aparecem na lista

## ☐ 8. Config Hermes — MCP Servers
- ☐ `config.yaml` tem seção `mcp_servers:`
- ☐ MCP servers listados: threejs-devtools, gsap-master, figma, mcp-three, sketchfab, context7
- ☐ YAML syntax: válido (`python3 -c "import yaml; yaml.safe_load(open('...'))"`)

## ☐ 9. Environment
- ☐ `~/.hermes/.env` existe
- ☐ `GROQ_API_KEY` configurada (fallback)
- ☐ `FIGMA_API_KEY` configurada
- ☐ `SKETCHFAB_API_KEY` configurada

## ☐ 10. Services Rodando
- ☐ `~/.hermes/status.sh` mostra ambos ✅ RUNNING
- ☐ `curl -s http://127.0.0.1:8800/api/model` responde
- ☐ `curl -s http://127.0.0.1:4101/health` responde com `serve_ready: true`

## ☐ 11. Chat Funciona
- ☐ `curl` de teste retorna 200 com choices
- ☐ Log mostra "Reusing OC session" na segunda chamada

## ☐ 12. MCP Bridge (Runtime)
- ☐ `tools/list` via MCP protocol retorna ferramentas com prefixo `hermes_`
- ☐ Pelo menos 1 ferramenta Hermes executável via MCP

## ☐ 13. Fallback
- ☐ Se `~/.hermes/stop.sh` → Hermes cai no fallback Groq
- ☐ Se `~/.hermes/start.sh` → Hermes volta a usar OpenCode

## ☐ 14. Systemd (Opcional)
- ☐ `systemd/opencode-serve.service` instalado (auto-start no boot)
- ☐ `systemd/hermes-proxy.service` instalado (auto-start no boot)

---

## Resumo

| Status | Significado |
|---|---|
| ☑ Todos ✅ | Integração completa e funcional |
| ⚠️ Alguns avisos | Funciona, mas veja ROADMAP.md |
| ❌ Falhas críticas | Corrigir antes de usar — veja SETUP.md |
