# SETUP — Instalação da Integração do Zero

> **Instruções para configurar Hermes + OpenCode em uma máquina nova.**
> Este guia assume que você está em um Linux (Ubuntu/Debian) com acesso a sudo.

---

## 1. Pré-requisitos

```bash
# Python 3.11+
python3 --version  # precisa ser >= 3.11

# Node.js 20+
node --version     # precisa ser >= 20

# npm
npm --version

# Git
git --version

# uv (gerenciador de Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Instalar Hermes Agent

```bash
# Clonar repositório
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent

# Criar virtualenv e instalar dependências
uv venv
source .venv/bin/activate
uv sync

# Setup inicial (escolha um provider, ex: Groq)
# Você precisará de uma API key
hermes setup
```

**⚠️ Configure uma API key funcional no setup inicial** (ex: Groq em https://console.groq.com).  
Isso será usado como **fallback** quando o OpenCode não estiver disponível.

## 3. Instalar OpenCode

```bash
# Opção A: npm (recomendado)
npm install -g @opencode-ai/sdk

# Opção B: binário pré-compilado
# Baixar de https://github.com/anomalyco/opencode/releases
# mkdir -p ~/.opencode/bin
# mv opencode ~/.opencode/bin/
# export PATH="$HOME/.opencode/bin:$PATH"
```

Verificar:

```bash
opencode --version  # deve mostrar 1.15.11 ou maior
```

## 4. Copiar Arquivos da Integração

```bash
# Os arquivos de integração estão em ~/.hermes/integration/
# Copie-os para os locais corretos:

INTEGRATION_DIR="$HOME/.hermes/integration"

# Binários (proxy, bridge, scripts)
cp "$INTEGRATION_DIR/bin/hermes-proxy.py" ~/.hermes/
cp "$INTEGRATION_DIR/bin/hermes-mcp-bridge.py" ~/.hermes/
cp "$INTEGRATION_DIR/bin/start.sh" ~/.hermes/
cp "$INTEGRATION_DIR/bin/stop.sh" ~/.hermes/
cp "$INTEGRATION_DIR/bin/status.sh" ~/.hermes/

chmod +x ~/.hermes/*.sh

echo "Arquivos copiados para ~/.hermes/"
```

## 5. Configurar Hermes

Edite `~/.hermes/config.yaml`:

```yaml
# ═══════════════════════════════════════════════════════════════
#  ATENÇÃO: Adapte para sua máquina
#  - Substitua ${GROQ_API_KEY} pela sua chave real
#  - Confirme que a porta 4101 não está em uso
# ═══════════════════════════════════════════════════════════════

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
    model: llama-3.3-70b-versatile
    base_url: https://api.groq.com/openai/v1
    api_key: "${GROQ_API_KEY}"

# ── MCP Servers (OpenCode ecosystem) ──────────────────────────
mcp_servers:
  threejs-devtools:
    command: threejs-devtools-mcp
    enabled: true
  gsap-master:
    command: npx
    args: ["-y", "bruzethegreat-gsap-master-mcp-server@latest"]
    enabled: true
  figma:
    command: npx
    args: ["-y", "figma-developer-mcp", "--figma-api-key=${FIGMA_API_KEY}", "--stdio"]
    enabled: true
  mcp-three:
    command: mcp-three
    enabled: true
  sketchfab:
    command: sketchfab-mcp
    args: ["--api-key", "${SKETCHFAB_API_KEY}"]
    enabled: true
  context7:
    url: https://mcp.context7.com/mcp
    type: remote
    enabled: true
```

## 6. Configurar OpenCode

Edite `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "opencode": {
      "models": {
        "deepseek-v4-flash-free": {
          "limit": { "context": 1000000, "output": 65536 },
          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "attachment": true,
          "tool_call": true
        }
      }
    }
  },
  "mcp": {
    "hermes-bridge": {
      "type": "local",
      "command": [
        "python3",
        "/home/SEU_USUARIO/.hermes/hermes-mcp-bridge.py"
      ],
      "enabled": true
    },
    "threejs-devtools": { "type": "local", "command": ["threejs-devtools-mcp"], "enabled": true },
    "gsap-master": { "type": "local", "command": ["npx", "-y", "bruzethegreat-gsap-master-mcp-server@latest"], "enabled": true },
    "figma": { "type": "local", "command": ["npx", "-y", "figma-developer-mcp", "--figma-api-key=SUA_CHAVE", "--stdio"], "enabled": true },
    "mcp-three": { "type": "local", "command": ["mcp-three"], "enabled": true },
    "sketchfab": { "type": "local", "command": ["sketchfab-mcp", "--api-key", "SUA_CHAVE"], "enabled": true },
    "context7": { "type": "remote", "url": "https://mcp.context7.com/mcp", "enabled": true }
  },
  "compaction": { "reserved": 200000 }
}

**⚠️ Substitua:**
- `/home/SEU_USUARIO/` → seu home directory real
- `SUA_CHAVE` → suas API keys reais
- O path do python3 deve apontar para a venv do Hermes

### ⚠️ CRÍTICO: Entenda as Modalidades

Cada campo no `opencode.json` controla se o OpenCode PERMITE ou BLOQUEIA
certo tipo de conteúdo. Sem eles, o OpenCode substitui o conteúdo por
"ERROR: model does not support X input":

| Config | Obrigatório? | Efeito se ausente |
|---|---|---|
| `modalities.input: ["text","image"]` | ✅ **SIM** | Imagens viram erro "model does not support image input" |
| `attachment: true` | ✅ **SIM** | Botão de upload de arquivo some da UI |
| `tool_call: true` | ✅ **SIM** | Modelo não pode chamar ferramentas |
| `limit.context: 1000000` | ✅ **SIM** | Contexto limitado ao padrão (128K-200K) |
| `modalities.input: ["video"]` | ❌ Opcional | Para enviar vídeos |
| `modalities.input: ["pdf"]` | ❌ Opcional | Para enviar PDFs |

> ⚠️ **Nota:** Mesmo com a config correta, o proxy (`hermes-proxy.py`)
> atualmente NÃO envia imagens — ele ignora `image_url` parts.
> A config do OpenCode é NECESSÁRIA mas não SUFICIENTE para imagens.
> Veja [P0-3] no ROADMAP.md para o trabalho pendente.

## 7. Iniciar Tudo

```bash
~/.hermes/start.sh
```

Isso inicia:
1. `opencode serve` na porta 8800
2. `hermes-proxy.py` na porta 4101

## 8. Verificar

```bash
# Status
~/.hermes/status.sh
# Saída esperada:
# OpenCode serve (porta 8800): ✅ RUNNING
# Hermes Proxy (porta 4101): ✅ RUNNING

# Health check
curl -s http://127.0.0.1:4101/health
# Saída esperada:
# {"status":"ok","serve_ready":true,"uptime":...,"active_sessions":0}
```

## 9. Testar

```bash
# Teste básico
curl -s http://127.0.0.1:4101/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash-free","messages":[{"role":"user","content":"Say hi in 2 words."}],"stream":false}'

# Saída esperada (algo como):
# {"id":"msg_...","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":"Hi there"},"finish_reason":"stop"}],"usage":{...}}

# Teste com Hermes
hermes -p "Say hello"
```

## 10. Verificar Session Reuse (Context Synergy)

Faça duas chamadas seguidas e veja os logs:

```bash
# Turno 1
curl -s ... -d '{"messages":[{"role":"user","content":"primeira"}]}' > /dev/null
# Turno 2 (reusa sessão)
curl -s ... -d '{"messages":[{"role":"user","content":"primeira"},{"role":"assistant","content":"ok"},{"role":"user","content":"segunda"}]}' > /dev/null

# Ver logs
tail -5 ~/.hermes/logs/hermes-proxy.log
# Deve mostrar: "Reusing OC session ses_xxx for key yyy — sending 2/3 new messages"
```

## 11. Usar Hermes Normalmente

```bash
hermes
# Agora o Hermes usa OpenCode como motor de inferência.
# Tudo funciona: CLI, TUI, Telegram, Discord, Slack, ACP...
```

## Rollback (Voltar ao Hermes Puro)

Se algo der errado e você quiser voltar ao Hermes sem OpenCode:

```bash
# 1. Parar a integração
~/.hermes/stop.sh

# 2. Restaurar config.yaml original
# (se tiver backup, ou apenas mude:)
# provider: custom
# base_url: https://api.groq.com/openai/v1

# 3. Remover MCP bridge do OpenCode
# Editar ~/.config/opencode/opencode.json
# Remover "hermes-bridge" do bloco "mcp"

# 4. Pronto — Hermes volta a usar Groq diretamente
hermes
```

---

## Solução de Problemas

| Problema | Causa | Solução |
|---|---|---|
| `opencode: command not found` | OpenCode não instalado | `npm install -g @opencode-ai/sdk` |
| `Address already in use` (porta 4101) | Outro processo na porta | `fuser -k 4101/tcp` |
| `Address already in use` (porta 8800) | Outro processo na porta | `fuser -k 8800/tcp` |
| Proxy não detecta OpenCode serve | Serve demorou a iniciar | `~/.hermes/restart.sh` ou esperar |
| Session sempre reseta (nunca reuse) | System prompt mudou entre chamadas | Normal se for conversa diferente |
| Hermes cai no fallback (Groq) | Proxy retornou erro | Ver `tail -f ~/.hermes/logs/hermes-proxy.log` |
| MCP bridge não aparece no OpenCode | Path do python3 errado | Corrigir `command` no `opencode.json` |

---

*Para continuidade do desenvolvimento, veja `ROADMAP.md`.*
