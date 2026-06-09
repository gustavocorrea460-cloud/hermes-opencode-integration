# Changelog

## v0.4.0 (2026-06-08)

### 🔴 P0 — Crítico
- **P0-1**: Pipe buffer deadlock — stdout/stderr redirecionados para arquivos de log
- **P0-2**: TOCTOU race — Lock atômico find+pop+save com `RLock`
- **P0-3**: Imagens — `image_url` → `file` parts com data URL base64
- **P0-4**: Session leak — `try/except` com cleanup garantido

### 🟠 P1 — Alto
- **P1-1**: 73 testes pytest (2 suites)
- **P1-2**: Session hash collision — fingerprint da primeira mensagem
- **P1-3**: Cross-conversation leak — `session_id` opcional no hash
- **P1-4**: `serve_ready` com `threading.Event()`
- **P1-5**: `request_count` atômico com `itertools.count()`
- **P1-6**: ThreadPoolExecutor com `max_workers=10`
- **P1-7/8**: Timeout dinâmico (60s-300s)
- **P1-9**: CORS restrito a localhost
- **P1-10**: Body limit 10MB com HTTP 413

### 🟡 P2 — Médio
- **P2-1**: JSON mode `response_format`
- **P2-2**: Structured output via `_messages_to_oc_parts()`
- **P2-3**: Context probe — config explícito `1M`
- **P2-9**: Session persistida em disco
- **P2-10**: 146 modelos via `/v1/models`
- **P2-12**: Gateway session isolation

### 🔵 P3 — Baixo
- **P3-2**: Skills cache 30s no MCP bridge
- **P3-4**: Tool result truncation com aviso `[Truncated]`
- **P3-8**: `PROXY_VERSION = "0.4.0"`
- **P3-9**: `_load_env()` no startup
- **P3-10**: opencode PATH fallback
- **P3-12**: `_check_compatibility()` no startup

### 🟡 P2
- **P2-7**: Multipart messages — `_messages_to_oc_parts()` preserva texto + imagens

### 🔵 P3
- **P3-3**: MCP bridge timeout — `ThreadPoolExecutor` com `TOOL_TIMEOUT=300s`
- **P3-5**: Tools assíncronas — `asyncio.run()` quando `entry.is_async=True`
- **P3-7**: Log sanitization — `_RedactFilter` reda secrets (api_key, token, secret)
- **P3-13**: `update.sh` — script de atualização
- **P3-14**: Tool call format — `TOOL_CALL_FORMAT` como constante no módulo
- **P3-19**: `CHANGELOG.md` adicionado

### ⚪ P4 — DX
- **P4-1**: Dynamic model list (sync a cada 5min)
- **P4-2**: `sync-configs.sh`
- **P4-4**: Tool call format detection — constante no topo do módulo
- **P4-5**: Error isError flag — bridge retorna `isError: True` em erros
- **P4-6**: MCP protocol negotiation — `MCP_VERSION` como variável

## v0.3.0 (anterior)
- Primeira versão funcional da integração
- Session reuse, streaming, tool calling
- MCP bridge com 64 ferramentas Hermes
