# SNAPSHOT — Estado Atual da Integração

> **Data:** 2026-06-08  
> **Hermes Agent:** v0.14.0+  
> **OpenCode:** v1.16.2  
> **Fusion Proxy:** v0.4.0  
> **MCP Bridge:** v0.2.0  
> **Testes:** 73/73 pytest

---

## ✅ Funcionando

### Proxy (hermes-proxy.py v0.4.0)
| Funcionalidade | Status | Detalhes |
|---|---|---|
| Chat completions (OpenAI format) | ✅ | `POST /v1/chat/completions` |
| Streaming SSE | ✅ | Chunks com content + tool_calls + usage |
| Tool calls via XML tags | ✅ | `<tool_use><name>...` parseado |
| Session reuse (1:1 com Hermes) | ✅ | Mesma sessão OC reutilizada |
| Envio incremental | ✅ | Só mensagens novas enviadas |
| Detecção de compressão | ✅ | Hash do prefixo → se mudou, reseta |
| Fallback automático | ✅ | OpenRouter via OPENROUTER_API_KEY |
| Model list dinâmica (146 modelos) | ✅ | Sync automático a cada 5 min |
| Capacidades por modelo | ✅ | tools, vision, video declarados |
| Imagens (image_url → file parts) | ✅ | Convertido para formato OpenCode |
| JSON mode / response_format | ✅ | Injeção de schema no system prompt |
| CORS restrito a localhost | ✅ | Valida Origin header |
| Timeout dinâmico | ✅ | 60s texto · 120s imagens · 300s reasoning |
| Session persistida em disco | ✅ | `session_map.json` para restart |
| Version check no startup | ✅ | Verifica Hermes + OpenCode config |
| opencode PATH fallback | ✅ | Busca em `~/.opencode/bin/` etc. |

### MCP Bridge (hermes-mcp-bridge.py)
| Funcionalidade | Status | Detalhes |
|---|---|---|
| Protocolo MCP sobre stdio | ✅ | JSON-RPC 2.0 |
| Lista de tools (64 ferramentas) | ✅ | Hermes terminal, browser, web, etc. |
| Cron job via MCP | ✅ | `hermes_cronjob` |
| Kanban (9 tools) | ✅ | `hermes_kanban_*` |
| Skills como resources | ✅ | `hermes://skills/` com cache 30s |
| Tool result truncation | ✅ | `[Truncated: N bytes → 100KB]` |
| Hermes info resource | ✅ | `hermes://info` |

### Systemd (Auto-Start)
| Funcionalidade | Status |
|---|---|
| `opencode-serve.service` | ✅ Instalado (user service) |
| `hermes-proxy.service` | ✅ Instalado (BindsTo opencode-serve) |

### Testes
| Suite | Status |
|---|---|
| `test_proxy_core.py` (38 tests) | ✅ |
| `test_proxy_messages.py` (31 tests) | ✅ |
| `test_proxy_security.py` (4 tests) | ✅ |

---

## ❌ Não Funciona / Não Implementado

| Funcionalidade | Impacto | Solução |
|---|---|---|
| **Imagens em modelos free OpenCode** | 🟡 OpenCode serve roteia file parts via DeepSeek/Zen que rejeita | Usar providers externos (NVIDIA) direto |
| **Systemd auto-start ativo** | 🟢 Precisa de `systemctl --user enable` manual | `start.sh` já cobre init |
| **Config sync script** | 🟢 MCP servers em 2 arquivos | Script `sync-configs.sh` |

---

## 🔑 Configs Atuais

### `~/.hermes/config.yaml`
```yaml
model:
  default: deepseek-v4-flash-free
  provider: opencode-proxy
  base_url: http://127.0.0.1:4101/v1
  context_length: 1000000
providers:
  opencode-proxy:
    base_url: http://127.0.0.1:4101/v1
fallback_providers:
  - provider: custom
    model: anthropic/claude-sonnet-4
    base_url: https://openrouter.ai/api/v1
    api_key: "${OPENROUTER_API_KEY}"
mcp_servers:
  - threejs-devtools, gsap-master, figma, mcp-three, sketchfab, context7
```

### `~/.config/opencode/opencode.json`
```json
{
  "mcp": {
    "hermes-bridge": {"command": ["python3", "~/.hermes/hermes-mcp-bridge.py"]},
    "threejs-devtools": {},
    "gsap-master": {},
    "figma": {},
    "mcp-three": {},
    "sketchfab": {},
    "context7": {}
  },
  "provider.opencode.models.deepseek-v4-flash-free": {
    "limit.context": 1000000,
    "modalities.input": ["text", "image", "video"]
  }
}
```

---

## 📊 Métricas

| Métrica | Valor |
|---|---|
| Modelos gratuitos sincronizados | 146 |
| Tools Hermes via MCP | 64 |
| Testes | 73 (0.08s) |
| Context window | 1.000.000 tokens |
| Session TTL | 3.600s (1h) |
| Proxy versão | 0.4.0 |

---

## 📦 Scripts

| Script | Função |
|---|---|
| `start.sh` | Inicia opencode serve + proxy |
| `stop.sh` | Para tudo |
| `restart.sh` | Reinício atômico |
| `status.sh` | Status rápido |
| `verify.sh` | Validação completa (11 passos) |
| `tests/test_*.py` | 73 testes pytest |

*Atualizado em 2026-06-08 — v0.4.0*
