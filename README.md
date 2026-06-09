# Hermes + OpenCode Integration

Motor de inferência LLM **gratuito** para o **Hermes Agent** usando **OpenCode** como backend, com proxy de sessão, MCP bridge, e 146 modelos gratuitos sincronizados dinamicamente.

## Instalação (1 comando)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main/install-oneliner.sh)
```

Ou manualmente:

```bash
git clone https://github.com/gustavocorrea460-cloud/hermes-opencode-integration.git
cd hermes-opencode-integration
bash install.sh
```

## Arquitetura

```
Hermes Agent ──OpenAI──→ hermes-proxy.py ──HTTP──→ opencode serve
    │         (streaming)    v0.4.0         (session reuse)  │
    └── 64 tools via MCP ─→ hermes-mcp-bridge.py             │
                            (stdio JSON-RPC 2.0)              │
                                                        146 free models
```

## Componentes

| Componente | Versão | Função |
|---|---|---|
| **Hermes Agent** | 0.14.x | Framework multi-plataforma de agentes |
| **OpenCode** | 1.16.x | Motor de inferência local (CLI + serve) |
| **Fusion Proxy** | **0.4.0** | Ponte OpenAI → OpenCode com session reuse |
| **MCP Bridge** | 0.2.0 | Expõe 64 ferramentas Hermes via MCP |

## Status

- **Proxy:** ✅ Chat, streaming, tools, session reuse, 146 modelos
- **Imagens:** ✅ `image_url` → `file` parts (limitado pelo backend)
- **Session:** ✅ Persistida em disco, isolamento por `session_id`
- **Segurança:** ✅ CORS restrito, body limit 10MB, .env isolado
- **Testes:** ✅ 73 pytest, verify.sh (11 passos)
- **Auto-start:** ✅ Systemd user services instalados

## Guia de Uso

### 1. Verificar se está tudo funcionando
```bash
bash ~/.hermes/integration/verify.sh
```
Testa 11 pontos: processos, portas, chat, session reuse, MCP bridge. Leva ~15s.

### 2. Rodar os testes automatizados
```bash
cd ~/.hermes/integration
python3 -m pytest tests/ -v            # modo detalhado (73 testes)
python3 -m pytest tests/ -q            # modo resumido
```

### 3. Iniciar / Parar / Status
```bash
# Início manual (abre opencode serve + proxy)
~/.hermes/start.sh

# Parar tudo
~/.hermes/stop.sh

# Ver status (processos, portas, logs)
~/.hermes/status.sh

# Logs do proxy
tail -f ~/.hermes/logs/hermes-proxy.log

# Logs do OpenCode serve
tail -f ~/.hermes/logs/opencode-serve.log
```

### 4. Auto-start com systemd (iniciar no boot)

Os serviços já estão instalados, só precisa ativar:

```bash
# Ativar para iniciar automaticamente no login
systemctl --user enable opencode-serve.service
systemctl --user enable hermes-proxy.service

# Iniciar agora (sem reboot)
systemctl --user start opencode-serve.service
systemctl --user start hermes-proxy.service

# Verificar se estão rodando
systemctl --user status opencode-serve.service
systemctl --user status hermes-proxy.service

# Ver logs do serviço
journalctl --user -u opencode-serve.service -n 50 --no-pager
journalctl --user -u hermes-proxy.service -n 50 --no-pager

# Parar serviços
systemctl --user stop opencode-serve.service
systemctl --user stop hermes-proxy.service

# Desativar auto-start
systemctl --user disable opencode-serve.service
systemctl --user disable hermes-proxy.service
```

> **Nota:** Se você não usa systemd (ex: WSL sem systemd), use `~/.hermes/start.sh` manualmente.

### 5. Gerenciar modelos

```bash
# Listar todos os 146 modelos gratuitos disponíveis
curl http://127.0.0.1:4101/v1/models | python3 -m json.tool

# Ver só modelos com visão
curl -s http://127.0.0.1:4101/v1/models | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d['data']:
    c = m.get('capabilities', {})
    if 'image' in c.get('input', []):
        print(f\"{m['id']:40s} tools={c.get('tools', False)}\")"

# Trocar o modelo padrão no Hermes
hermes config set model.default deepseek-v4-flash-free    # 1M contexto (padrão)
hermes config set model.default meta/llama-3.1-70b-instruct  # 128K, NVIDIA free
hermes config set model.default kimi-k2.5-free                # vision + video

# Testar um modelo específico via API
curl -s http://127.0.0.1:4101/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta/llama-3.1-70b-instruct","messages":[{"role":"user","content":"hi"}],"stream":false}'
```

### 6. Health check do proxy

```bash
curl http://127.0.0.1:4101/health | python3 -m json.tool
# Retorna: version, status, serve_ready, uptime, requests, active_sessions
```

### 7. Resumo visual do estado

```
⚡ Hermes Agent ─opencode-proxy→ hermes-proxy.py ─HTTP→ opencode serve
   │                              v0.4.0                │ 146 free models
   └── 64 tools via MCP bridge ─────────────────────────┘ session reuse
```

## Documentação

| Arquivo | Conteúdo |
|---|---|
| `SETUP.md` | Instalação do zero |
| `CHECKLIST.md` | Checklist de verificação |
| `SNAPSHOT.md` | Estado atual detalhado |
| `ROADMAP.md` | 51 itens de melhoria (33/51 resolvidos) |
| `verify.sh` | Script de validação (11 passos) |
| `tests/` | 73 testes pytest |

## Modelos Gratuitos

146 modelos sincronizados do OpenCode serve. Filtrados por `cost=0` e excluindo `opencode-zen` (pago). Destaques:

| Modelo | Provider | Tools | Visão | Contexto |
|---|---|---|---|---|
| `deepseek-v4-flash-free` | opencode | ✅ | ✅ | 1M |
| `meta/llama-3.1-70b-instruct` | nvidia | ✅ | ❌ | 128K |
| `kimi-k2.5-free` | opencode | ✅ | ✅+📹 | 128K |
| `minimax-m3-free` | opencode | ✅ | ✅+📹 | 128K |
| `google/gemma-3-27b-it` | nvidia | ✅ | ✅ | 128K |
