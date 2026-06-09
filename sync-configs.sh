#!/usr/bin/env bash
# sync-configs.sh — Sincroniza MCP servers entre Hermes config.yaml e OpenCode opencode.json
# Uso: bash sync-configs.sh [--dry-run] [--sync]

set -euo pipefail

HERMES_CONFIG="$HOME/.hermes/config.yaml"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
CAUTION="⚠️  ATENÇÃO: Este script é informativo. A sincronização automática ainda requer revisão manual."

echo "═══════════════════════════════════════════════════════════"
echo "  Config Sync — Hermes ↔ OpenCode"
echo "═══════════════════════════════════════════════════════════"

# ── Detect MCP servers in Hermes config ──
echo ""
echo "📋 MCP servers em config.yaml:"
if [[ -f "$HERMES_CONFIG" ]]; then
    grep -A2 "mcp_servers:" "$HERMES_CONFIG" 2>/dev/null | head -5 || echo "  (nenhum ou não encontrado)"
    grep -E "^\s+- " "$HERMES_CONFIG" 2>/dev/null | head -10 || echo "  (nenhum listado)"
else
    echo "  ❌ Arquivo não encontrado"
fi

# ── Detect MCP servers in OpenCode config ──
echo ""
echo "📋 MCP servers em opencode.json:"
if [[ -f "$OPENCODE_CONFIG" ]]; then
    python3 -c "
import json, sys
with open('$OPENCODE_CONFIG') as f:
    cfg = json.load(f)
mcps = cfg.get('mcp', {})
if mcps:
    for name, conf in sorted(mcps.items()):
        enabled = conf.get('enabled', True)
        status = '✅' if enabled else '⏸️'
        print(f'  {status} {name}')
else:
    print('  (nenhum MCP configurado)')
"
else
    echo "  ❌ Arquivo não encontrado"
fi

# ── Comparar ──
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🔍 Diferenças detectadas"
echo "═══════════════════════════════════════════════════════════"

python3 << 'PYEOF'
import os, json, re

hermes_path = os.path.expanduser("~/.hermes/config.yaml")
opencode_path = os.path.expanduser("~/.config/opencode/opencode.json")

# Parse MCP servers from config.yaml (simple grep approach)
hermes_servers = set()
if os.path.exists(hermes_path):
    content = open(hermes_path).read()
    # Find lines under mcp_servers: that start with - name:
    in_mcp = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("mcp_servers:"):
            in_mcp = True
            continue
        if in_mcp and stripped.startswith("- ") and ":" in stripped:
            name = stripped.split(":")[0].lstrip("- ").strip()
            hermes_servers.add(name)
        elif in_mcp and not stripped.startswith("  ") and not stripped.startswith("- "):
            in_mcp = False

# Parse MCP servers from opencode.json
opencode_servers = set()
if os.path.exists(opencode_path):
    cfg = json.load(open(opencode_path))
    mcps = cfg.get("mcp", {})
    opencode_servers = set(mcps.keys())

if not hermes_servers and not opencode_servers:
    print("  ✅ Nenhum MCP server configurado em ambos — nada a sincronizar.")
else:
    only_hermes = hermes_servers - opencode_servers
    only_opencode = opencode_servers - hermes_servers
    common = hermes_servers & opencode_servers

    if common:
        print(f"  ✅ Em ambos ({len(common)}): {', '.join(sorted(common))}")
    if only_hermes:
        print(f"  🔶 Só no config.yaml ({len(only_hermes)}): {', '.join(sorted(only_hermes))}")
        print("     → Adicione ao opencode.json manualmente")
    if only_opencode:
        print(f"  🔶 Só no opencode.json ({len(only_opencode)}): {', '.join(sorted(only_opencode))}")
        print("     → Adicione ao config.yaml se quiser que o Hermes use")

print()
print("  ⚠️  ATENÇÃO: Este script é informativo. A sincronização automática ainda requer revisão manual.")
PYEOF

# ── Dry-run / Sync modes ──
MODE="${1:---dry-run}"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  📌 Uso"
echo "═══════════════════════════════════════════════════════════"
echo "  bash sync-configs.sh --dry-run   (mostrar diferenças, padrão)"
echo "  bash sync-configs.sh --sync      (sincronizar automaticamente)"
echo ""
echo "  Após sincronizar, reinicie o proxy:"
echo "    ~/.hermes/restart.sh"
