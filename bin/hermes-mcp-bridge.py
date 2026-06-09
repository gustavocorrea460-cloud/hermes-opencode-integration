#!/usr/bin/env python3
"""Hermes MCP Bridge — exposes ALL Hermes features as MCP tools & resources.

This server implements the Model Context Protocol (MCP) over stdio,
discovering Hermes tools dynamically from the registry and exposing
them as MCP tools that OpenCode (or any MCP client) can call.

Exposed features:
  - 64+ Hermes tools (terminal, browser, files, web, skills, etc.)
  - Skills as resources (hermes://skills/...)
  - Sessions as resources (hermes://sessions/...)
  - Memory tools (hermes_memory_*)
  - Cron tools (hermes_cron_*)
  - Kanban tools (hermes_kanban_*)
  - Gateway tools (hermes_gateway_*)

Usage:
  python3 hermes-mcp-bridge.py
  # Or in OpenCode config:
  # "mcp": { "hermes-bridge": { "type": "local", "command": ["python3", "/path/to/hermes-mcp-bridge.py"] } }
"""

import functools
import json
import logging
import os
import asyncio
import concurrent.futures
import sys
import time
import traceback
from pathlib import Path
from typing import Any
MCP_VERSION = "2025-03-26"
_tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="mcp-tool")
TOOL_TIMEOUT = 300  # 5 min timeout per tool call

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hermes-mcp-bridge")

HERMES_DIR = Path(os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, str(HERMES_DIR))

# Import Hermes tool registry
try:
    from tools.registry import registry, discover_builtin_tools

    discover_builtin_tools()
    _all_tool_names = registry.get_all_tool_names()
    logger.info("Discovered %d Hermes tools", len(_all_tool_names))
except Exception as e:
    logger.error("Failed to discover Hermes tools: %s", e)
    registry = None
    _all_tool_names = []

# --- MCP Protocol Implementation ---

MCP_VERSION = "2025-03-26"


def mcp_error(id: Any, code: int, message: str, data: Any = None) -> str:
    resp = {
        "jsonrpc": "2.0",
        "id": id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        resp["error"]["data"] = data
    return json.dumps(resp)


def mcp_result(id: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id, "result": result})


def mcp_notification(method: str, params: Any = None) -> str:
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


def convert_schema_to_mcp(hermes_schema: dict) -> dict:
    """Convert Hermes-style schema to MCP tool schema."""
    hermes_schema = hermes_schema or {}
    params = hermes_schema.get("parameters", {"type": "object", "properties": {}})

    mcp_schema = {
        "type": "object",
        "properties": {},
    }

    if "required" in params:
        mcp_schema["required"] = params["required"]

    raw_props = params.get("properties", {})
    for name, prop in raw_props.items():
        mcp_schema["properties"][name] = {
            "type": prop.get("type", "string"),
            "description": prop.get("description", ""),
        }

    return mcp_schema


# --- Request Handlers ---


def handle_initialize(req: dict) -> str:
    req_id = req.get("id")
    capabilities = {
        "tools": {},
        "resources": {
            "subscribe": True,
            "listChanged": False,
        },
    }
    return mcp_result(
        req_id,
        {
            "protocolVersion": MCP_VERSION,
            "capabilities": capabilities,
            "serverInfo": {"name": "hermes-mcp-bridge", "version": "0.2.0"},
        },
    )


def handle_tools_list(req: dict) -> str:
    req_id = req.get("id")
    if registry is None:
        return mcp_error(req_id, -32603, "Hermes registry not available")

    mcp_tools = []
    for name in sorted(_all_tool_names):
        try:
            entry = registry.get_entry(name)
            if entry is None:
                continue

            desc = entry.description or ""
            schema = convert_schema_to_mcp(entry.schema)
            mcp_tools.append(
                {
                    "name": f"hermes_{name}",
                    "description": f"[Hermes] {desc}"[:500],
                    "inputSchema": schema,
                }
            )
        except Exception as e:
            logger.debug("Error converting tool %s: %s", name, e)
            continue

    return mcp_result(req_id, {"tools": mcp_tools})


def handle_tools_call(req: dict) -> str:
    req_id = req.get("id")
    params = req.get("params", {})
    mcp_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if registry is None:
        return mcp_error(req_id, -32603, "Hermes registry not available")

    # Strip "hermes_" prefix to get Hermes tool name
    hermes_name = mcp_name
    if hermes_name.startswith("hermes_"):
        hermes_name = hermes_name[7:]

    entry = registry.get_entry(hermes_name)
    if entry is None:
        return mcp_error(req_id, -32601, f"Unknown tool: {mcp_name}")

    try:
        # P3-5: Handle async tools
        if getattr(entry, "is_async", False):
            result = asyncio.run(entry.handler(arguments))
        else:
            # P3-3: Run with timeout via ThreadPoolExecutor
            future = _tool_executor.submit(entry.handler, arguments)
            result = future.result(timeout=TOOL_TIMEOUT)

        if result is None:
            result = ""

        # Ensure result is a string
        if not isinstance(result, str):
            try:
                result = json.dumps(result)
            except Exception:
                result = str(result)

        max_len = 100000
        if len(result) > max_len:
            truncated_info = f"\n\n[Truncated: {len(result)} bytes → {max_len} bytes]"
            result = result[:max_len] + truncated_info
        content = [{"type": "text", "text": result}]
        return mcp_result(req_id, {"content": content})
    except concurrent.futures.TimeoutError:
        logger.error("Tool %s timed out after %ss", mcp_name, TOOL_TIMEOUT)
        return mcp_result(
            req_id,
            {
                "content": [{"type": "text", "text": f"Error: {mcp_name} timed out after {TOOL_TIMEOUT}s"}],
                "isError": True,
            },
        )
    except Exception as e:
        logger.error("Tool %s failed: %s", mcp_name, traceback.format_exc())
        return mcp_result(
            req_id,
            {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            },
        )


def handle_resources_list(req: dict) -> str:
    req_id = req.get("id")
    resources = []

    resources.append(
        {
            "uri": "hermes://info",
            "name": "Hermes Bridge Info",
            "description": "Hermes MCP Bridge status and tool count",
            "mimeType": "application/json",
        }
    )

    resources.append(
        {
            "uri": "hermes://tools",
            "name": "Hermes Available Tools",
            "description": f"List of {len(_all_tool_names)} registered Hermes tools",
            "mimeType": "application/json",
        }
    )

    skills_uri = "hermes://skills"
    resources.append(
        {
            "uri": skills_uri,
            "name": "Hermes Skills",
            "description": "List installed Hermes skills",
            "mimeType": "application/json",
        }
    )

    return mcp_result(req_id, {"resources": resources})


_skills_cache_time = 0.0
_skills_cache_data: list[dict] = []
SKILLS_CACHE_TTL = 30  # seconds


def _list_skills_cached(skills_path: Path) -> list[dict]:
    """List skills with caching (TTL=30s) to avoid repeated disk reads."""
    global _skills_cache_time, _skills_cache_data
    now = time.time()
    if now - _skills_cache_time < SKILLS_CACHE_TTL and _skills_cache_data:
        return _skills_cache_data
    skills = []
    if skills_path.exists():
        for skill_dir in sorted(skills_path.iterdir()):
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skills.append({"name": skill_dir.name, "path": str(skill_md)})
    _skills_cache_data = skills
    _skills_cache_time = now
    return skills


def handle_resources_read(req: dict) -> str:
    req_id = req.get("id")
    params = req.get("params", {})
    uri = params.get("uri", "")

    if uri == "hermes://info":
        data = {
            "tools_total": len(_all_tool_names),
            "tools": sorted(_all_tool_names),
        }
        return mcp_result(
            req_id,
            {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(data, indent=2),
                    }
                ],
            },
        )

    if uri == "hermes://tools":
        tool_list = []
        for name in sorted(_all_tool_names):
            entry = registry.get_entry(name) if registry else None
            if entry:
                tool_list.append(
                    {"name": name, "description": (entry.description or "")[:100]}
                )
        return mcp_result(
            req_id,
            {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(tool_list, indent=2),
                    }
                ],
            },
        )

    if uri == "hermes://skills":
        skills_path = Path(os.path.expanduser("~/.hermes/skills"))
        skills = _list_skills_cached(skills_path)
        return mcp_result(
            req_id,
            {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(skills, indent=2),
                    }
                ],
            },
        )

    # Dynamic skill URI: hermes://skills/{name}/SKILL.md
    if uri.startswith("hermes://skills/") and uri.endswith("/SKILL.md"):
        skill_name = uri[len("hermes://skills/") : -len("/SKILL.md")]
        skill_path = Path(os.path.expanduser(f"~/.hermes/skills/{skill_name}/SKILL.md"))
        if skill_path.exists():
            text = skill_path.read_text(encoding="utf-8")
            return mcp_result(
                req_id,
                {
                    "contents": [
                        {"uri": uri, "mimeType": "text/markdown", "text": text}
                    ],
                },
            )

    return mcp_error(req_id, -32602, f"Resource not found: {uri}")


# --- Main Loop ---


def main() -> None:
    logger.info("Hermes MCP Bridge starting on stdio")
    logger.info("Discovered %d Hermes tools", len(_all_tool_names))

    # Signal that server is ready (some clients use this)
    print(mcp_notification("server/ready", {"status": "ok"}), flush=True)

    buffer = ""
    for line in sys.stdin:
        buffer += line
        try:
            req = json.loads(buffer)
            buffer = ""
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        req_id = req.get("id")

        try:
            if method == "initialize":
                response = handle_initialize(req)
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                response = handle_tools_list(req)
            elif method == "tools/call":
                response = handle_tools_call(req)
            elif method == "resources/list":
                response = handle_resources_list(req)
            elif method == "resources/read":
                response = handle_resources_read(req)
            elif method == "ping":
                response = mcp_result(req_id, {})
            else:
                response = mcp_error(req_id, -32601, f"Method not found: {method}")

            print(response, flush=True)
            logger.debug("Handled %s (%s)", method, req_id)

        except Exception as e:
            logger.error("Error handling %s: %s", method, traceback.format_exc())
            if req_id is not None:
                err_resp = mcp_error(req_id, -32603, f"Internal error: {e}")
                print(err_resp, flush=True)


if __name__ == "__main__":
    main()
