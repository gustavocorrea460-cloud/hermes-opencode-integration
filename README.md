<div align="center">

# Hermes + OpenCode Integration

[![Zero Cost Inference](https://img.shields.io/badge/💰_Zero_Cost_Inference-brightgreen?style=for-the-badge)](https://github.com/gustavocorrea460-cloud/hermes-opencode-integration)
[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](https://github.com/gustavocorrea460-cloud/hermes-opencode-integration)
[![Tests](https://img.shields.io/badge/tests-73%20passed-green.svg)](https://github.com/gustavocorrea460-cloud/hermes-opencode-integration)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**🔥 Stop paying for LLM inference. Run Hermes Agent with 110 free models — zero API costs.**

</div>

---

## 🚀 Why This?

| Problem | Solution |
|---|---|
| Hermes needs an LLM → costs $5-50/month with APIs | **$0.00** — 110 free models via OpenCode |
| Complex setup with multiple providers | **One command** — install and done |
| Session context lost between turns | **KV cache reuse** — 1:1 session mapping |
| Tools not available to OpenCode models | **64 MCP tools** — terminal, browser, cron, kanban, memory |

---

## ✨ Features at a Glance

| Feature | What it means |
|---|---|
| 🎯 **Zero-cost inference** | 110 free models with generous limits — NVIDIA (90) + OpenCode (20) |
| ⏱️ **Session reuse** | 1:1 Hermes ↔ OpenCode session = KV cache preserved |
| 🔧 **MCP Bridge** | 64 Hermes tools via MCP (terminal, browser, web, cron, kanban, memory) |
| 📸 **Image support** | OpenAI `image_url` → OpenCode `file` parts automatically |
| 💾 **Session persistence** | Survives proxy restarts via `session_map.json` |
| 🛡️ **Security** | CORS localhost-only, 10MB limit, log redaction, .env isolation |
| 🧪 **Tested** | 73 pytest tests + `verify.sh` (11-step validation) |
| ⚡ **Auto-start** | Systemd user services included

---

## Quick Start

**One command installation:**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main/install-oneliner.sh)
```

**Or clone and install:**

```bash
git clone https://github.com/gustavocorrea460-cloud/hermes-opencode-integration.git
cd hermes-opencode-integration
bash install.sh
```

After installation, just run:

```bash
hermes
```

---

## Architecture

```
┌─────────────┐     OpenAI API      ┌───────────────┐     HTTP     ┌───────────────┐
│  Hermes     │ ──(streaming)──→   │ Fusion Proxy  │ ──────────→ │ OpenCode Serve │
│  Agent      │ ←───────────────── │   v0.4.0      │ ←────────── │  (port 8800)   │
│             │   64 tools via MCP │  (port 4101)  │ session     │  110 free      │
│             │ ←──────────────── │               │ reuse       │  models        │
└─────────────┘                   └───────┬───────┘             └───────────────┘
                                         │
                                  ┌──────┴──────┐
                                  │ MCP Bridge  │
                                  │ 64 Hermes   │
                                  │ tools       │
                                  └─────────────┘
```

**Data flow:**

1. Hermes sends an OpenAI-compatible request to the Fusion Proxy (port 4101)
2. Proxy resolves the model, creates/reuses an OpenCode session
3. Request is forwarded to OpenCode Serve (port 8800) with the free model
4. Response streams back through the proxy to Hermes
5. The MCP Bridge exposes 64 Hermes tools (terminal, browser, cron, etc.) via stdio JSON-RPC

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| OpenCode | 1.15+ | `opencode --version` |
| Hermes Agent | 0.14+ | `hermes --version` |
| RAM | 2GB+ | — |

---

## Usage

### Verify installation

```bash
~/.hermes/integration/verify.sh
```

### Manual start/stop

```bash
~/.hermes/start.sh      # Start services
~/.hermes/stop.sh       # Stop services
~/.hermes/status.sh     # Check status
```

### Run tests

```bash
cd ~/.hermes/integration
python3 -m pytest tests/ -v
```

### Systemd (auto-start on boot)

> **⚠️ WSL (Windows):** Systemd is not available on WSL by default. Use `~/.hermes/start.sh` instead.  
> To enable systemd on WSL: https://aka.ms/wsl-systemd

```bash
systemctl --user enable --now opencode-serve.service
systemctl --user enable --now hermes-proxy.service
```

### List available free models

```bash
curl http://127.0.0.1:4101/v1/models | python3 -m json.tool
```

### Switch model

```bash
hermes config set model.default deepseek-v4-flash-free    # 1M context (default)
hermes config set model.default kimi-k2.5-free            # vision + video
```

---

## Available Free Models

110 free models with generous rate limits, synced automatically from OpenCode serve.

| Source | Count | Example models |
|---|---|---|
| **NVIDIA** | **90** | Llama 3.1 70B, Gemma 3 27B, Mixtral 8x22B |
| **OpenCode** | **20** | DeepSeek V4 Flash (1M ctx), Kimi K2.5, Minimax M3 |

**Free model highlights:**

| Model | Provider | Tools | Vision | Context |
|---|---|---|---|---|
| `deepseek-v4-flash-free` | opencode | ✅ | ✅ | **1M** |
| `meta/llama-3.1-70b-instruct` | nvidia | ✅ | ❌ | 128K |
| `kimi-k2.5-free` | opencode | ✅ | ✅+📹 | 128K |
| `google/gemma-3-27b-it` | nvidia | ✅ | ✅ | 128K |
| `abacusai/dracarys-llama-3_1-70b-instruct` | nvidia | ✅ | ❌ | 128K |

---

## Configuration

| File | Purpose |
|---|---|
| `~/.hermes/config.yaml` | Hermes provider config (opencode-proxy) |
| `~/.config/opencode/opencode.json` | OpenCode model + MCP config |
| `~/.hermes/.env` | Environment variables (optional) |
| `~/.hermes/integration/` | All integration files, tests, docs |

---

## Tests

73 pytest tests across 2 suites:

| Suite | File | Tests |
|---|---|---|
| Core | `tests/test_proxy_core.py` | 38 |
| Messages | `tests/test_proxy_messages.py` | 31 |
| Security | `test_proxy_security.py` | 4 |

Coverage: `_conv_key`, `_msg_hash`, `_is_free`, `_has_images`, `_resolve_model`, `_parse_tool_calls`, `_messages_to_text`, `_messages_to_oc_parts`, `_extract_images_from_content`, `_build_full_prompt`, `_build_incremental_prompt`, `_convert_tools_to_text`.

---

## Security

- **CORS**: Restricted to `localhost:4101` and `127.0.0.1:4101`
- **Body limit**: 10MB maximum request size (HTTP 413)
- **Log redaction**: API keys and tokens redacted from logs via `_RedactFilter`
- **Session isolation**: Optional `session_id` in `_conv_key` prevents cross-conversation leaks
- **No secrets in repo**: All API keys isolated to `~/.hermes/.env`
- **No personal data**: Zero usernames or absolute paths in the repository

---

## Troubleshooting

### Proxy won't start

```bash
tail -f ~/.hermes/logs/hermes-proxy.log
# Check for port conflicts or Python errors
```

### OpenCode serve not responding

```bash
tail -f ~/.hermes/logs/opencode-serve.log
# Check if opencode is installed: opencode --version
```

### "No free models available"

```bash
# Wait for initial model sync (up to 30s)
# Or check proxy health:
curl http://127.0.0.1:4101/health
```

### Chat completions return empty

Some free models (like `deepseek-v4-flash-free`) return empty responses for image inputs. For vision, switch to `kimi-k2.5-free` or `google/gemma-3-27b-it`.

---

## Project Structure

```
📦 hermes-opencode-integration/
├── 📜 hermes-proxy.py           # Fusion Proxy (OpenAI → OpenCode bridge)
├── 📜 hermes-mcp-bridge.py      # MCP Bridge (64 Hermes tools)
├── 📜 VERSION                   # Version tracking
├── 📜 install.sh                # Installer
├── 📜 uninstall.sh              # Uninstaller
├── 📜 update.sh                 # Updater
├── 📜 verify.sh                 # Validation (11 steps)
├── 📜 README.md                 # This file
├── 📜 CHANGELOG.md              # Version history
├── 📜 LICENSE                   # MIT License
├── 📜 CONTRIBUTING.md           # Contributing guide
├── 📋 config/                   # Reference configs
├── ⚙️ systemd/                  # Auto-start services
├── 🧪 tests/                    # Pytest test suite (73 tests)
└── 📁 bin/                      # Scripts
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) © 2026 gustavocorrea460-cloud

---

## 🇧🇷 Português

### Integração Hermes + OpenCode

Motor de inferência LLM **gratuito** para o **Hermes Agent** usando **OpenCode** como backend. Substitui chamadas pagas (OpenAI, Anthropic) por 110 modelos gratuitos, com reuso de sessão e 64 ferramentas via MCP.

**Instalação:**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gustavocorrea460-cloud/hermes-opencode-integration/main/install-oneliner.sh)
```

**Uso:** Apenas `hermes` no terminal — o Hermes usa automaticamente os modelos gratuitos do OpenCode via proxy local.

**Documentação completa** em `SNAPSHOT.md`, `ROADMAP.md`, `CHANGELOG.md` e `SETUP.md`.

---

*Built with ❤️ for the Hermes Agent community*
