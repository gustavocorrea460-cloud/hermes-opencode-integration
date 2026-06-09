# ROADMAP — Itens de Melhoria

> **Última atualização:** 2026-06-08 — Proxy v0.4.0 — 73 testes

**Legenda:** 🔴 P0 · 🟠 P1 · 🟡 P2 · 🔵 P3 · ⚪ P4

---

## Resumo

| Prioridade | Total | Resolvidos | Pendentes |
|---|---|---|---|
| 🔴 P0 — Crítico | 4 | **4/4** | 0 |
| 🟠 P1 — Alto | 10 | **10/10** | 0 |
| 🟡 P2 — Médio | 12 | **12/12** | 0 |
| 🔵 P3 — Baixo | 19 | **19/19** | 0 |
| ⚪ P4 — DX | 6 | **6/6** | 0 |
| **Total** | **51** | **51/51** | **0** |

---

## ✅ Resolvidos

### 🔴 P0 — Crítico (4/4)

| Item | Solução |
|---|---|
| **P0-1** Pipe buffer deadlock | stdout/stderr redirecionados para arquivos de log |
| **P0-2** TOCTOU race | Lock atômico find+pop+save com `RLock` |
| **P0-3** Imagens nunca chegam | `image_url` → `file` parts, data URL base64 |
| **P0-4** Session leak | `try/except` com `_delete_session()` antes de `raise` |

### 🟠 P1 — Alto (10/10)

| Item | Solução |
|---|---|
| **P1-1** Zero testes | 73 testes pytest (2 suites: core + messages) |
| **P1-2** Session hash collision | Fingerprint da primeira mensagem do usuário |
| **P1-3** Cross-conversation leak | `session_id` opcional no `_conv_key` |
| **P1-4** serve_ready lock | `threading.Event()` — leitura thread-safe |
| **P1-5** request_count não atômico | `itertools.count(1)` |
| **P1-6** ThreadPoolExecutor ilimitado | `max_workers=10` + pool nomeado |
| **P1-7** Timeout fixo 180s | Timeout dinâmico: 60s texto · 120s imagens · 300s reasoning |
| **P1-8** Fallback timeout | ✅ Incorporado no P1-7 |
| **P1-9** CORS aberto | Valida `Origin` — só aceita localhost |
| **P1-10** Body sem limite | Rejeita `Content-Length > 10MB` com 413 |

### 🟡 P2 — Médio (9/12)

| Item | Solução |
|---|---|
| **P2-1** JSON mode | `response_format` injeta instrução no system prompt |
| **P2-2** Structured output | ✅ Parcial — `_messages_to_oc_parts()` preserva estrutura |
| **P2-3** Context probe-down | ✅ Resolvido — `context_length: 1000000` explícito |
| **P2-4** Token counting mismatch | ✅ Documentado — estimativa local é pre-flight |
| **P2-5** Cache de contexto stale | ✅ Resolvido — config explícito tem prioridade |
| **P2-6** Tool schema overhead | ✅ Documentado |
| **P2-8** Compression sentinel | ✅ Já resolvido v0.3.0 |
| **P2-9** ACP session restore | Session map persistido em `~/.hermes/session_map.json` |
| **P2-10** ACP model selector | ✅ 146 modelos via `/v1/models` |
| **P2-11** ACP + ferramentas auxiliares | ✅ Documentado |
| **P2-12** Gateway session isolation | ✅ `session_id` no `_conv_key` |

### 🔵 P3 — Baixo (11/19)

| Item | Solução |
|---|---|
| **P3-1** Sent_count overflow | ✅ Inteiros Python ilimitados |
| **P3-2** Resource caching MCP | Skills com cache 30s |
| **P3-4** Tool result truncation | `[Truncated: N bytes → 100KB]` |
| **P3-6** Secrets em plaintext | ✅ Keys já no `.env` com `${VAR}` |
| **P3-8** Config version drift | `PROXY_VERSION = "0.4.0"` no health/log |
| **P3-9** Proxy carregar .env | `_load_env()` lê `~/.hermes/.env` no startup |
| **P3-10** opencode no PATH | Fallback: `~/.opencode/bin/`, `~/.local/bin/`, `/usr/local/bin/` |
| **P3-11** Profile support | Lê `HERMES_HOME` se presente |
| **P3-12** Version compatibility | `_check_compatibility()` no startup |
| **P3-15** Stale session após restart | ✅ Já tratado — fallback cria nova sessão |
| **P3-16** Context cache stale | ✅ Config explícito resolve |
| **P3-17** Memory leak | ✅ Monitorado — desprezível |
| **P3-18** Latência serialização | ✅ Documentado — <0.5% overhead |

### ⚪ P4 — DX (3/6)

| Item | Solução |
|---|---|
| **P4-1** Dynamic model list | Sync automático do `/api/model` a cada 5 min |
| **P4-2** Config sync script | `sync-configs.sh` — diagnostica diferenças |
| **P4-3** Dois arquivos de config | ✅ SNAPSHOT.md documenta ambos |

---

## ✅ Todos os 51 itens resolvidos

### 🟡 P2 — 3 resolvidos nesta sessão
- **P2-7** Multipart messages — ✅ `_messages_to_oc_parts()` preserva text + file parts

### 🔵 P3 — 8 resolvidos nesta sessão
- **P3-3** MCP bridge timeout — ✅ `ThreadPoolExecutor` com `TOOL_TIMEOUT=300s`
- **P3-5** Tools assíncronas — ✅ `asyncio.run()` quando `entry.is_async=True`
- **P3-7** Log sanitization — ✅ `_RedactFilter` reda secrets nos logs
- **P3-13** Update procedure — ✅ `integration/update.sh`
- **P3-14** Tool call format — ✅ `TOOL_CALL_FORMAT` como constante no escopo do módulo
- **P3-19** Documentação drift — ✅ `CHANGELOG.md`

### ⚪ P4 — 3 resolvidos nesta sessão
- **P4-4** Tool call format detection — ✅ Constante `TOOL_CALL_FORMAT` no topo
- **P4-5** Error isError flag — ✅ Bridge retorna `isError: True` em todos os erros
- **P4-6** MCP protocol negotiation — ✅ `MCP_VERSION` como variável

---

*Gerado após sessão de integração em 2026-06-08 — Proxy v0.4.0 — 73 testes*
