# Configs da Integração

Arquivos de configuração de referência para a integração Hermes + OpenCode.

## Arquivos

| Arquivo | Sistema | Descrição |
|---|---|---|
| `hermes-config.yaml` | Hermes Agent | Provider `opencode-proxy` + fallback |
| `opencode-config.json` | OpenCode | Modelo `deepseek-v4-flash-free` + MCP `hermes-bridge` |
| `.env.example` | Shell | Template para API keys |

## Como usar

1. Copie os arquivos para os locais corretos:
   ```bash
   cp hermes-config.yaml ~/.hermes/config.yaml
   cp opencode-config.json ~/.config/opencode/opencode.json
   cp .env.example ~/.hermes/.env
   ```

2. Edite `~/.hermes/.env` com suas API keys (opcional)

3. Reinicie o proxy:
   ```bash
   ~/.hermes/restart.sh
   ```
