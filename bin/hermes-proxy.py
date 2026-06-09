#!/usr/bin/env python3
"""Hermes Fusion Proxy v3 — Context-Synced OpenAI-compatible HTTP server.

Routes LLM inference to OpenCode serve with FULL context synergy:
  - Session reuse: 1 Hermes conversation ↔ 1 OpenCode session (KV cache!)
  - Incremental sends: only new messages per turn, not full history
  - Compression detection: auto-resets OpenCode session when Hermes compacts
  - Context length awareness: reports correct 1M window to Hermes
  - Stale session cleanup: prevents orphaned OpenCode sessions

Architecture:
  Hermes AIAgent ──OpenAI──→ hermes-proxy.py ──HTTP──→ opencode serve
      │           (streaming)       │         (session reuse) │
      └── tool loop, skills etc.    └── tracks sent_msgs hash └── KV cached!
"""

import base64
import concurrent.futures
import hashlib
import http.server
import itertools
import json
import logging
import os
import re
import signal
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

class _RedactFilter(logging.Filter):
    """Redact common secrets from log messages."""
    _PATTERNS = [
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+'), r'\1***'),
        (re.compile(r'(sk-or-v1-)[a-zA-Z0-9]{20,}'), r'\1***'),
        (re.compile(r'(nvapi-)[a-zA-Z0-9_-]{20,}'), r'\1***'),
        (re.compile(r'(\bsecret["\']?\s*[:=]\s*["\'])[^"\']+'), r'\1***'),
        (re.compile(r'(\btoken["\']?\s*[:=]\s*["\'])[^"\']+'), r'\1***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self._PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hermes-proxy")
logger.addFilter(_RedactFilter())

PROXY_PORT = 4101
PROXY_HOST = "127.0.0.1"
SERVE_PORT = 8800
SERVE_HOST = "127.0.0.1"
CONTEXT_LENGTH = 1_000_000
SESSION_TTL = 3600
CLEANUP_INTERVAL = 300
MAX_REQUEST_BODY = 10 * 1024 * 1024  # 10 MB
SESSION_MAP_PATH = Path.home() / ".hermes" / "session_map.json"
PROXY_VERSION = "0.4.0"

MODEL_MAP: dict[str, dict[str, str]] = {}
MODEL_MAP_LOCK = threading.Lock()
MODEL_SYNC_INTERVAL = 300


def _fetch_model_catalog() -> list[dict]:
    """Fetch the full model catalog from OpenCode serve."""
    try:
        req = urllib.request.Request(
            f"http://{SERVE_HOST}:{SERVE_PORT}/api/model", method="GET"
        )
        req.timeout = 10
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("models", "data", "catalog", "result"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
            return []
    except Exception:
        return []


def _is_free(model: dict) -> bool:
    """Check if model is free (input cost == 0)."""
    costs = model.get("cost", [])
    if costs and isinstance(costs, list):
        return costs[0].get("input", 1) == 0
    if isinstance(costs, dict):
        return costs.get("input", 1) == 0
    return False


def _sync_models() -> None:
    """Sync MODEL_MAP from OpenCode serve catalog, keeping only free models."""
    global MODEL_MAP
    try:
        catalog = _fetch_model_catalog()
        if not catalog:
            logger.warning("Model catalog empty — keeping existing MODEL_MAP")
            return

        new_map: dict[str, dict[str, Any]] = {}
        count_free = 0
        count_tools = 0
        count_vision = 0

        for m in catalog:
            mid = m.get("id", "")
            pid = m.get("providerID", "opencode")
            if not mid or not m.get("enabled", True):
                continue
            if not _is_free(m):
                continue
            # Skip paid OpenCode Zen models
            if pid == "opencode-zen":
                continue

            count_free += 1
            caps: dict = m.get("capabilities", {})
            inputs: list = (
                caps.get("input", []) if isinstance(caps.get("input"), list) else []
            )
            has_tools = caps.get("tools") is True
            has_vision = "image" in inputs
            has_video = "video" in inputs

            new_map[mid] = {
                "modelID": mid,
                "providerID": pid,
                "tools": has_tools,
                "vision": has_vision,
                "video": has_video,
            }

            if has_tools:
                count_tools += 1
            if has_vision:
                count_vision += 1

        # Always include known free aliases with capability info
        extras = {
            "deepseek-v4-flash-free": {
                "modelID": "deepseek-v4-flash-free",
                "providerID": "opencode",
                "tools": True,
                "vision": True,
                "video": False,
            },
        }
        for k, v in extras.items():
            if k not in new_map:
                new_map[k] = v

        # Sort: models with tools first, then vision, then alphabetically
        def _sort_key(item: tuple[str, dict]) -> tuple[int, str]:
            info = item[1]
            has_tools = info.get("tools", False)
            has_vision = info.get("vision", False)
            priority = 0 if has_tools else (1 if has_vision else 2)
            return (priority, item[0])

        with MODEL_MAP_LOCK:
            MODEL_MAP = dict(sorted(new_map.items(), key=_sort_key))

        logger.info(
            "Synced %d free models from OpenCode (%d tools, %d vision)",
            count_free,
            count_tools,
            count_vision,
        )
    except Exception as e:
        logger.error("Model sync failed: %s", e)


def _model_sync_timer() -> None:
    """Periodically refresh the model catalog."""
    while True:
        time.sleep(MODEL_SYNC_INTERVAL)
        try:
            _sync_models()
        except Exception:
            pass


TOOL_CALL_FORMAT = (
    "Tool Calling Format: Use <tool_use><name>tool_name</name>"
    "<arguments>{json}</arguments></tool_use> for each tool call. "
    "One block per call. Valid JSON in arguments. Stop after tool call and wait for result."
)

serve_process: subprocess.Popen | None = None
serve_ready_event = threading.Event()
serve_lock = threading.Lock()

# ── Context-Synced Session State ──────────────────────────────────────
# Maps conversation_key → SessionState
# A session is "alive" as long as messages grow monotonically.
# When Hermes compresses (messages shrink or change), the session resets.
_session_map: dict[str, dict] = {}
_session_lock = threading.RLock()

start_time = time.time()
request_counter = itertools.count(1)
_request_count_cache = 0  # last known value for health endpoint


def _conv_key(
    system_prompt: str,
    model: str,
    messages: list | None = None,
    session_id: str | None = None,
) -> str:
    """Stable identity for a Hermes conversation = fingerprint of system + model + first user msg.
    This survives across turns because Hermes keeps the same system prompt.
    The first user message fingerprint prevents cross-conversation collisions.
    If session_id is provided (e.g. from Hermes gateway), it's included for isolation."""
    raw = system_prompt + "|||" + model
    if session_id:
        raw += "|||session:" + session_id
    elif messages:
        for m in messages:
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content if isinstance(c, dict)
                    )
                raw += "|||" + str(content)[:200]
                break
    return hashlib.md5(raw.encode()).hexdigest()


def _msg_hash(messages: list[dict]) -> str:
    """Fingerprint of the sent messages for compression detection.
    Ignores tool_call_id (which is ephemeral and changes between turns)."""
    cleaned = []
    for m in messages:
        c = {}
        for k, v in m.items():
            if k == "tool_call_id":
                continue
            if k == "tool_calls" and isinstance(v, list):
                c[k] = [{kk: vv for kk, vv in tc.items() if kk != "id"} for tc in v]
            else:
                c[k] = v
        cleaned.append(c)
    return hashlib.md5(
        json.dumps(cleaned, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def _find_session(key: str, messages: list[dict]) -> tuple[str | None, bool]:
    """Find reusable session or signal compression reset.

    Continuation detection:
      - sent_count stores how many Hermes messages were sent to OC
      - sent_hash stores hash of messages[0:sent_count] (the prefix)
      - On new call: compute hash of messages[0:sent_count] and compare
      - If prefix matches AND len(messages) > sent_count: continuation!
      - If prefix changed or len(shrank): compression happened, reset

    Returns (oc_session_id or None, is_compressed).
    """
    with _session_lock:
        state = _session_map.get(key)
        if state is None:
            return None, False

        oc_id = state["oc_session_id"]
        sent_count = state["sent_count"]
        old_prefix_hash = state["sent_hash"]
        new_count = len(messages)

        # Compute hash of the first `sent_count` messages (the prefix)
        new_prefix = messages[:sent_count]
        new_prefix_hash = _msg_hash(new_prefix) if new_prefix else old_prefix_hash

        # Continuation: prefix matches AND messages grew
        if new_count > sent_count and new_prefix_hash == old_prefix_hash:
            state["last_access"] = time.time()
            return oc_id, False

        # Compression or new conversation: invalidate old session
        logger.info(
            "Session reset for %s: old=%d prefix=%s new=%d",
            key[:12],
            sent_count,
            old_prefix_hash[:8],
            new_count,
        )
        _session_map.pop(key, None)
        return None, True


def _save_session(key: str, oc_session_id: str, messages: list[dict]) -> None:
    """Record a session for future incremental reuse."""
    with _session_lock:
        _session_map[key] = {
            "oc_session_id": oc_session_id,
            "sent_count": len(messages),
            "sent_hash": _msg_hash(messages),
            "created_at": time.time(),
            "last_access": time.time(),
        }
    _persist_session_map()


def _persist_session_map() -> None:
    """Save session_map to disk for ACP restore."""
    try:
        with _session_lock:
            data = {}
            for k, v in _session_map.items():
                data[k] = {
                    "oc_session_id": v["oc_session_id"],
                    "sent_count": v["sent_count"],
                    "sent_hash": v["sent_hash"],
                    "created_at": v["created_at"],
                    "last_access": v["last_access"],
                }
        SESSION_MAP_PATH.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning("Failed to persist session map: %s", e)


def _load_session_map() -> None:
    """Load session_map from disk (ACP restart recovery)."""
    try:
        if not SESSION_MAP_PATH.exists():
            return
        data = json.loads(SESSION_MAP_PATH.read_text())
        with _session_lock:
            restored = 0
            for k, v in data.items():
                if k not in _session_map:
                    _session_map[k] = v
                    restored += 1
            if restored:
                logger.info("Restored %d sessions from disk", restored)
    except Exception as e:
        logger.warning("Failed to load session map: %s", e)


def _cleanup_stale_sessions() -> None:
    """Background task: delete orphaned OpenCode sessions."""
    now = time.time()
    with _session_lock:
        stale = [
            k for k, v in _session_map.items() if now - v["last_access"] > SESSION_TTL
        ]
        for key in stale:
            oc_id = _session_map[key]["oc_session_id"]
            logger.info("Cleaning stale session %s (%s)", oc_id, key[:12])
            _delete_session(oc_id)
            del _session_map[key]


def _cleanup_timer() -> None:
    """Run cleanup periodically in a daemon thread."""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        try:
            _cleanup_stale_sessions()
        except Exception:
            pass


# ── OpenCode serve lifecycle ──────────────────────────────────────────


def _check_serve() -> bool:
    try:
        req = urllib.request.Request(
            f"http://{SERVE_HOST}:{SERVE_PORT}/api/model", method="GET"
        )
        req.timeout = 3
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except Exception:
        return False


def _start_serve() -> None:
    global serve_process
    with serve_lock:
        if serve_ready_event.is_set():
            return
        if _check_serve():
            serve_ready_event.set()
            logger.info("opencode serve already running")
            return

        logger.info("Starting opencode serve on port %s", SERVE_PORT)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        out_log = os.path.join(log_dir, "opencode-serve.log")
        err_log = os.path.join(log_dir, "opencode-serve.err.log")

        opencode_bin = "opencode"
        import shutil

        if not shutil.which(opencode_bin):
            for candidate in [
                Path.home() / ".opencode" / "bin" / "opencode",
                Path.home() / ".local" / "bin" / "opencode",
                Path("/usr/local/bin/opencode"),
            ]:
                if candidate.exists():
                    opencode_bin = str(candidate)
                    logger.info("Found opencode at %s", opencode_bin)
                    break
            else:
                logger.error("opencode binary not found on PATH or common locations")
                return

        try:
            serve_process = subprocess.Popen(
                [
                    opencode_bin,
                    "serve",
                    "--port",
                    str(SERVE_PORT),
                    "--hostname",
                    SERVE_HOST,
                ],
                stdout=open(out_log, "a"),
                stderr=open(err_log, "a"),
            )
        except FileNotFoundError:
            logger.error("opencode binary not found at %s", opencode_bin)
            return

        for _ in range(30):
            if _check_serve():
                serve_ready_event.set()
                logger.info("opencode serve ready")
                return
            time.sleep(1)

        logger.warning("opencode serve did not become ready in 30s")


def _stop_serve() -> None:
    global serve_process
    if serve_process:
        logger.info("Stopping opencode serve")
        serve_process.terminate()
        try:
            serve_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            serve_process.kill()
        serve_process = None
    serve_ready_event.clear()


# ── OpenCode HTTP client ──────────────────────────────────────────────


def _opencode_request(
    method: str, path: str, body: dict | None = None, timeout: int | None = None
) -> tuple[int, Any]:
    url = f"http://{SERVE_HOST}:{SERVE_PORT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.timeout = timeout if timeout is not None else 180
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": str(e)}
    except urllib.error.URLError as e:
        return 503, {"error": f"opencode serve unreachable: {e.reason}"}


def _create_session() -> str:
    status, body = _opencode_request("POST", "/session", {})
    if status != 200 or not isinstance(body, dict) or "id" not in body:
        raise RuntimeError(f"Failed to create OpenCode session: {body}")
    return body["id"]


def _delete_session(session_id: str) -> None:
    try:
        _opencode_request("DELETE", f"/session/{session_id}")
    except Exception:
        pass


# ── Message conversion ────────────────────────────────────────────────


def _extract_system_prompt(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content)
            if content:
                parts.append(content)
    return "\n\n".join(parts)


def _convert_tools_to_text(tools: list[dict] | None) -> str:
    if not tools:
        return ""
    lines = ["## Available Tools", ""]
    for tool in tools:
        fn = tool.get("function", {})
        if not fn:
            continue
        lines.append(f"### {fn['name']}")
        if fn.get("description"):
            lines.append(fn["description"])
        params = fn.get("parameters", {})
        if params.get("properties"):
            lines.append("")
            lines.append("Parameters:")
            required = params.get("required", [])
            for pname, pschema in params["properties"].items():
                req_str = " (required)" if pname in required else ""
                type_str = pschema.get("type", "string")
                desc = pschema.get("description", "")
                lines.append(f"- {pname}: {type_str}{req_str} - {desc}")
        lines.append("")
    return "\n".join(lines)


def _download_image_to_data_url(url: str) -> str | None:
    """Download an image from HTTP(S) URL and return as data URL."""
    if url.startswith("data:"):
        return url
    try:
        req = urllib.request.Request(url, method="GET")
        req.timeout = 30
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "image/png")
            b64 = base64.b64encode(data).decode()
            return f"data:{ctype};base64,{b64}"
    except Exception:
        logger.warning("Failed to download image from %s", url[:80])
        return None


def _extract_images_from_content(content: Any) -> list[dict]:
    """Extract image file parts from OpenAI content array."""
    images = []
    if not isinstance(content, list):
        return images
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "image_url":
            iu = item.get("image_url", {})
            url = iu.get("url", "") if isinstance(iu, dict) else ""
            if url:
                data_url = (
                    url if url.startswith("data:") else _download_image_to_data_url(url)
                )
                if data_url:
                    images.append(
                        {
                            "type": "file",
                            "url": data_url,
                            "mime": data_url.split(";")[0].replace("data:", "")
                            if ";" in data_url
                            else "image/png",
                        }
                    )
    return images


def _messages_to_text(messages: list[dict]) -> str:
    """Convert a list of OpenAI-format messages to flat text for OpenCode."""
    parts = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        if not content:
            content = ""

        if role == "system":
            continue  # system is sent separately
        elif role == "tool":
            name = m.get("name", "unknown")
            parts.append(f'[Tool result for "{name}"]:\n{content}')
        elif role == "assistant":
            tc = m.get("tool_calls")
            if tc:
                tc_text = "\n".join(
                    f"  → Called {t['function']['name']}({t['function']['arguments']})"
                    for t in tc
                    if isinstance(t, dict) and "function" in t
                )
                if content:
                    parts.append(f"Assistant: {content}\n{tc_text}")
                else:
                    parts.append(tc_text)
            elif content:
                parts.append(f"Assistant: {content}")
        else:
            if content:
                parts.append(f"User: {content}")
    return "\n\n".join(parts)


def _messages_to_oc_parts(messages: list[dict]) -> list[dict]:
    """Convert messages to OpenCode parts array (text + images).

    Returns a list of parts suitable for OpenCode session/message API:
    [{"type": "text", "text": "..."}, {"type": "file", "url": "data:...", "mime": "..."}]
    """
    oc_parts: list[dict] = []
    for m in messages:
        role = m.get("role", "")
        if role == "system":
            continue
        content = m.get("content", "")

        if isinstance(content, list):
            # Extract text
            text_items = [
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            text = " ".join(text_items)
            # Extract images
            images = _extract_images_from_content(content)

            if role in ("user", "tool") and text:
                oc_parts.append(
                    {
                        "type": "text",
                        "text": f"{'User' if role == 'user' else 'Tool'}: {text}",
                    }
                )
            elif role == "assistant":
                if text:
                    oc_parts.append({"type": "text", "text": f"Assistant: {text}"})
            elif text:
                oc_parts.append({"type": "text", "text": text})

            oc_parts.extend(images)

        else:
            text = content or ""
            if role == "tool":
                name = m.get("name", "unknown")
                oc_parts.append(
                    {"type": "text", "text": f'[Tool result for "{name}"]:\n{text}'}
                )
            elif role == "assistant":
                tc = m.get("tool_calls")
                if tc:
                    tc_text = "\n".join(
                        f"  → Called {t['function']['name']}({t['function']['arguments']})"
                        for t in tc
                        if isinstance(t, dict) and "function" in t
                    )
                    if text:
                        oc_parts.append(
                            {"type": "text", "text": f"Assistant: {text}\n{tc_text}"}
                        )
                    else:
                        oc_parts.append({"type": "text", "text": tc_text})
                elif text:
                    oc_parts.append({"type": "text", "text": f"Assistant: {text}"})
            elif text:
                oc_parts.append({"type": "text", "text": f"User: {text}"})

    return oc_parts


def _has_images(messages: list[dict]) -> bool:
    """Check if any message contains image_url parts."""
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    return True
    return False


def _build_full_prompt(
    messages: list[dict], tools: list[dict] | None, system_prompt: str
) -> tuple[str, str]:
    """Build system prompt + user text from ALL messages (for new session)."""
    tool_text = _convert_tools_to_text(tools)
    if tool_text:
        if system_prompt:
            system_prompt = (
                system_prompt + "\n\n" + tool_text + "\n\n" + TOOL_CALL_FORMAT
            )
        else:
            system_prompt = tool_text + "\n\n" + TOOL_CALL_FORMAT
    elif not system_prompt:
        system_prompt = "You are a helpful AI assistant."

    user_prompt = _messages_to_text(messages)
    return system_prompt, user_prompt


def _build_incremental_prompt(new_messages: list[dict]) -> str:
    """Convert ONLY the new messages (since last turn) to text.
    Uses same format as _messages_to_text but adds context prefix."""
    if not new_messages:
        return ""
    text = _messages_to_text(new_messages)
    return text


def _parse_tool_calls(text: str) -> list[dict]:
    pattern = r"<tool_use>\s*<name>([^<]+)</name>\s*<arguments>([\s\S]*?)</arguments>\s*</tool_use>"
    tool_calls = []
    for i, match in enumerate(re.finditer(pattern, text)):
        name = match.group(1).strip()
        args_str = match.group(2).strip()
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {"raw": args_str}
        tool_calls.append(
            {
                "id": f"call_{int(time.time() * 1000)}_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        )
    return tool_calls


def _strip_tool_tags(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<tool_use>[\s\S]*?</tool_use>", "", text).strip()


def _resolve_model(openai_model: str) -> dict[str, str]:
    with MODEL_MAP_LOCK:
        if openai_model in MODEL_MAP:
            return dict(MODEL_MAP[openai_model])
    if openai_model.startswith("opencode/"):
        return {"modelID": openai_model[9:], "providerID": "opencode"}
    if openai_model.startswith("opencode-zen/"):
        return {"modelID": openai_model[13:], "providerID": "opencode-zen"}
    return {"modelID": openai_model, "providerID": "opencode"}


def _oc_send_prompt(
    oc_session_id: str,
    system: str,
    text: str,
    model_info: dict,
    oc_parts: list[dict] | None = None,
) -> tuple[int, Any]:
    """Send a prompt to an existing OpenCode session.

    Args:
        oc_parts: Optional pre-built parts array (supports text + file parts for images).
                  If None, creates a single text part from `text`.
    """
    body = {
        "modelID": model_info["modelID"],
        "providerID": model_info["providerID"],
        "system": system or None,
        "tools": {},
        "parts": oc_parts if oc_parts else [{"type": "text", "text": text}],
    }
    timeout = model_info.get("_timeout")
    return _opencode_request(
        "POST",
        f"/session/{oc_session_id}/message",
        body,
        timeout=timeout if timeout is not None else 180,
    )


# ── Core handler ──────────────────────────────────────────────────────


def handle_chat_completion(body: dict) -> dict | None:
    global _request_count_cache
    request_num = next(request_counter)
    _request_count_cache = request_num

    model = body.get("model", "opencode")
    messages = body.get("messages", [])
    tools = body.get("tools", [])
    stream = body.get("stream", False)
    response_format = body.get("response_format")
    model_info = _resolve_model(model)

    # Dynamic timeout: body override > tools+images > default
    req_timeout = body.get("timeout")
    if req_timeout is None:
        has_tools = bool(tools)
        has_images = _has_images(messages)
        is_reasoning = (
            "deepseek" in model_info["modelID"] or "r1" in model_info["modelID"].lower()
        )
        if is_reasoning:
            req_timeout = 300  # reasoning models need more time
        elif has_tools and has_images:
            req_timeout = 180
        elif has_images:
            req_timeout = 120
        elif has_tools:
            req_timeout = 60
        else:
            req_timeout = 60  # simple text
    model_info["_timeout"] = req_timeout

    _start_serve()
    if not serve_ready_event.is_set():
        return {
            "error": {
                "message": "opencode serve not available",
                "type": "server_error",
            },
            "status": 503,
        }

    system_prompt = _extract_system_prompt(messages)
    # Inject JSON format instructions when response_format is requested
    if response_format:
        rf_type = response_format.get("type", "")
        if rf_type == "json_object":
            system_prompt += "\n\nYou MUST respond with valid JSON only. No other text, no markdown, no thinking tags."
        elif rf_type == "json_schema":
            schema = response_format.get("schema", {})
            system_prompt += f"\n\nYou MUST respond with valid JSON matching this schema: {json.dumps(schema)}. No other text."
    session_id = body.get("session_id") or body.get("user") or None
    key = _conv_key(system_prompt, model, messages, session_id)
    logger.info(
        "Request #%s: model=%s msgs=%s tools=%s stream=%s key=%s",
        request_num,
        model_info["modelID"],
        len(messages),
        len(tools),
        stream,
        key[:12],
    )

    # ── Check for reusable session (atomic with _session_lock) ──
    with _session_lock:
        oc_session_id, needs_reset = _find_session(key, messages)

        if needs_reset:
            # Compression detected: old session is invalid
            _delete_session(oc_session_id)
            oc_session_id = None

        if oc_session_id is None:
            # Before creating, delete any stale entry for this key
            old_state = _session_map.pop(key, None)
            if old_state:
                _delete_session(old_state["oc_session_id"])

    if oc_session_id is None:
        system_prompt_full, user_prompt = _build_full_prompt(
            messages,
            tools,
            system_prompt,
        )
        has_images = _has_images(messages)

        if has_images:
            oc_parts = _messages_to_oc_parts(messages)
            if not user_prompt.strip() and not any(
                p.get("type") == "file" for p in oc_parts
            ):
                return {
                    "error": {
                        "message": "empty user prompt",
                        "type": "invalid_request",
                    },
                    "status": 400,
                }
            oc_session_id = _create_session()
            logger.info(
                "New OC session %s for key %s (%d msgs, with images)",
                oc_session_id,
                key[:12],
                len(messages),
            )
            try:
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    system_prompt_full,
                    user_prompt,
                    model_info,
                    oc_parts=oc_parts,
                )
            except Exception:
                _delete_session(oc_session_id)
                raise
        else:
            if not user_prompt.strip():
                return {
                    "error": {
                        "message": "empty user prompt",
                        "type": "invalid_request",
                    },
                    "status": 400,
                }
            oc_session_id = _create_session()
            logger.info(
                "New OC session %s for key %s (%d msgs)",
                oc_session_id,
                key[:12],
                len(messages),
            )
            try:
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    system_prompt_full,
                    user_prompt,
                    model_info,
                )
            except Exception:
                _delete_session(oc_session_id)
                raise

        if status == 200:
            _save_session(key, oc_session_id, messages)
        else:
            _delete_session(oc_session_id)
            err = resp if isinstance(resp, str) else json.dumps(resp)
            logger.error("OpenCode error (status %s): %s", status, err[:500])
            return {
                "error": {
                    "message": f"opencode error: {err[:500]}",
                    "type": "upstream_error",
                },
                "status": 502,
            }
    else:
        # ── Continuation: send only new messages ──
        with _session_lock:
            state = _session_map.get(key, {})
            sent_count = state.get("sent_count", 0)

        new_messages = messages[sent_count:]
        logger.info(
            "Reusing OC session %s for key %s — sending %d/%d new messages",
            oc_session_id,
            key[:12],
            len(new_messages),
            len(messages),
        )

        if not new_messages:
            logger.warning("No new messages to send — reusing full prompt")
            _, user_prompt = _build_full_prompt(messages, tools, "")
            if _has_images(messages):
                oc_parts = _messages_to_oc_parts(messages)
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    None,
                    user_prompt,
                    model_info,
                    oc_parts=oc_parts,
                )
            else:
                status, resp = _oc_send_prompt(
                    oc_session_id, None, user_prompt, model_info
                )
        else:
            if _has_images(new_messages):
                oc_parts = _messages_to_oc_parts(new_messages)
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    None,
                    "",
                    model_info,
                    oc_parts=oc_parts,
                )
            else:
                incremental_text = _build_incremental_prompt(new_messages)
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    None,
                    incremental_text,
                    model_info,
                )

        if status == 200:
            _save_session(key, oc_session_id, messages)
        else:
            logger.error(
                "Continuation failed (status %s), falling back to new session", status
            )
            _delete_session(oc_session_id)
            with _session_lock:
                _session_map.pop(key, None)
            system_prompt_full, user_prompt = _build_full_prompt(
                messages, tools, system_prompt
            )
            if not user_prompt.strip() and not _has_images(messages):
                return {
                    "error": {
                        "message": "empty user prompt",
                        "type": "invalid_request",
                    },
                    "status": 400,
                }
            oc_session_id = _create_session()
            if _has_images(messages):
                oc_parts = _messages_to_oc_parts(messages)
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    system_prompt_full,
                    user_prompt,
                    model_info,
                    oc_parts=oc_parts,
                )
            else:
                status, resp = _oc_send_prompt(
                    oc_session_id,
                    system_prompt_full,
                    user_prompt,
                    model_info,
                )
            if status != 200:
                _delete_session(oc_session_id)
                return {
                    "error": {
                        "message": "opencode error after fallback",
                        "type": "upstream_error",
                    },
                    "status": 502,
                }
            _save_session(key, oc_session_id, messages)

    # ── Parse response ──
    if not isinstance(resp, dict) or "info" not in resp:
        return {
            "error": {
                "message": "unexpected opencode response format",
                "type": "upstream_error",
            },
            "status": 502,
        }

    info = resp["info"]
    parts = resp.get("parts", [])

    raw_text = "\n".join(p.get("text", "") for p in parts if p.get("type") in ("text",))
    reasoning = "\n".join(
        p.get("text", "") for p in parts if p.get("type") == "reasoning"
    )
    tool_calls = _parse_tool_calls(raw_text)
    clean_text = _strip_tool_tags(raw_text)

    if reasoning and clean_text:
        response_text = f"<thinking>\n{reasoning}\n</thinking>\n\n{clean_text}"
    elif reasoning:
        response_text = f"<thinking>\n{reasoning}\n</thinking>"
    else:
        response_text = clean_text

    finish = info.get("finish", "stop")
    ts = info.get("tokens", {})

    # Real token usage from OpenCode — Hermes uses this for context tracking
    prompt_tokens = ts.get("input", 0)
    completion_tokens = ts.get("output", 0)
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }

    msg_id = info.get("id", f"msg_{int(time.time() * 1000)}")
    created = int(time.time())

    if tool_calls:
        return {
            "id": msg_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": clean_text or None,
                        "tool_calls": tool_calls,
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": usage,
            "_stream": stream,
        }
    else:
        return {
            "id": msg_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": finish if finish in ("stop", "length") else "stop",
                }
            ],
            "usage": usage,
            "_stream": stream,
        }


# ── HTTP Server ───────────────────────────────────────────────────────


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.client_address[0], format % args)

    def _send_json(self, status: int, data: Any) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin", "")
        if origin in ("http://localhost:4101", "http://127.0.0.1:4101", ""):
            self.send_header("Access-Control-Allow-Origin", origin or "*")
        else:
            self.send_header("Access-Control-Allow-Origin", "http://localhost:4101")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_sse(self, data: Any) -> None:
        self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())

    def do_GET(self) -> None:
        if self.path == "/health":
            with _session_lock:
                active = len(_session_map)
            self._send_json(
                200,
                {
                    "version": PROXY_VERSION,
                    "status": "ok",
                    "serve_ready": serve_ready_event.is_set(),
                    "uptime": round(time.time() - start_time),
                    "requests": _request_count_cache,
                    "active_sessions": active,
                },
            )
        elif self.path == "/v1/models":
            with MODEL_MAP_LOCK:
                model_items = list(MODEL_MAP.items())
            models = []
            for k, v in model_items:
                entry: dict[str, Any] = {
                    "id": k,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "opencode",
                }
                # Declare capabilities for Hermes to discover
                caps: dict[str, Any] = {
                    "tools": v.get("tools", False),
                }
                modalities: list[str] = ["text"]
                if v.get("vision"):
                    modalities.append("image")
                if v.get("video"):
                    modalities.append("video")
                caps["input"] = modalities
                entry["capabilities"] = caps
                models.append(entry)
            self._send_json(200, {"object": "list", "data": models})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_REQUEST_BODY:
            self._send_json(413, {"error": "request too large"})
            return
        raw = self.rfile.read(content_length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        try:
            result = handle_chat_completion(body)
        except Exception as e:
            logger.exception("Unhandled error processing request")
            self._send_json(
                500, {"error": {"message": str(e), "type": "internal_error"}}
            )
            return

        if result is None:
            self._send_json(
                500, {"error": {"message": "no response", "type": "internal_error"}}
            )
            return

        if "status" in result and result["status"] >= 400:
            status = result.pop("status", 502)
            self._send_json(status, {"error": result.get("error", result)})
            return

        stream = result.pop("_stream", False)
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            origin = self.headers.get("Origin", "")
            if origin in ("http://localhost:4101", "http://127.0.0.1:4101", ""):
                self.send_header("Access-Control-Allow-Origin", origin or "*")
            else:
                self.send_header("Access-Control-Allow-Origin", "http://localhost:4101")
            self.end_headers()

            choice = result["choices"][0]
            msg = choice["message"]

            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    delta = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": tc["id"],
                                "type": "function",
                                "function": tc["function"],
                            }
                        ],
                    }
                    self._send_sse(
                        {
                            "id": result["id"],
                            "object": "chat.completion.chunk",
                            "created": result["created"],
                            "model": result["model"],
                            "choices": [
                                {"index": 0, "delta": delta, "finish_reason": None}
                            ],
                        }
                    )
                self._send_sse(
                    {
                        "id": result["id"],
                        "object": "chat.completion.chunk",
                        "created": result["created"],
                        "model": result["model"],
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": "tool_calls"}
                        ],
                    }
                )
            else:
                content = msg.get("content", "")
                if content:
                    delta = {"role": "assistant", "content": content}
                    self._send_sse(
                        {
                            "id": result["id"],
                            "object": "chat.completion.chunk",
                            "created": result["created"],
                            "model": result["model"],
                            "choices": [
                                {"index": 0, "delta": delta, "finish_reason": None}
                            ],
                        }
                    )
                self._send_sse(
                    {
                        "id": result["id"],
                        "object": "chat.completion.chunk",
                        "created": result["created"],
                        "model": result["model"],
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                )

            self._send_sse(
                {
                    "id": result["id"],
                    "object": "chat.completion.chunk",
                    "created": result["created"],
                    "model": result["model"],
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": result.get("usage", {}),
                }
            )
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            result.pop("_stream", None)
            self._send_json(200, result)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        if origin in ("http://localhost:4101", "http://127.0.0.1:4101", ""):
            self.send_header("Access-Control-Allow-Origin", origin or "*")
        else:
            self.send_header("Access-Control-Allow-Origin", "http://localhost:4101")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


MAX_WORKERS = 10


class ThreadPoolHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS, thread_name_prefix="proxy"
        )

    def process_request(self, request: Any, client_address: tuple[str, int]) -> None:
        self.pool.submit(self.process_request_thread, request, client_address)

    def server_close(self) -> None:
        self.pool.shutdown(wait=False)
        super().server_close()


MIN_OPENCODE_VERSION = "1.15.0"
MIN_HERMES_VERSION = "0.14.0"


def _check_compatibility() -> bool:
    """Check Hermes and OpenCode version compatibility on startup."""
    ok = True

    # Check OpenCode serve endpoint
    try:
        req = urllib.request.Request(f"http://{SERVE_HOST}:{SERVE_PORT}/", method="GET")
        req.timeout = 5
        with urllib.request.urlopen(req) as resp:
            logger.info("OpenCode serve reachable (HTTP %s)", resp.status)
    except Exception as e:
        logger.warning("OpenCode serve not reachable: %s", e)
        ok = False

    # Check Hermes config has expected provider
    hermes_config = Path.home() / ".hermes" / "config.yaml"
    if hermes_config.exists():
        content = hermes_config.read_text()
        if "opencode-proxy" not in content:
            logger.warning(
                "Hermes config may not use opencode-proxy provider — "
                "check ~/.hermes/config.yaml"
            )
            ok = False
        else:
            logger.info("Hermes config uses opencode-proxy provider ✓")
    else:
        logger.warning("Hermes config not found at %s", hermes_config)
        ok = False

    # Check opencode.json MCP bridge config
    opencode_config = Path.home() / ".config" / "opencode" / "opencode.json"
    if opencode_config.exists():
        content = opencode_config.read_text()
        if "hermes-bridge" in content:
            logger.info("OpenCode config has hermes-bridge MCP ✓")
        else:
            logger.warning("OpenCode config missing hermes-bridge MCP entry")
            ok = False
    else:
        logger.warning("OpenCode config not found")
        ok = False

    if not ok:
        logger.warning(
            "Compatibility issues detected. Run ~/.hermes/integration/verify.sh"
            " for details."
        )
    return ok


def _load_env() -> None:
    """Load ~/.hermes/.env into os.environ if it exists."""
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception as e:
        logger.warning("Failed to load .env: %s", e)


def main() -> None:
    logger.info(
        "Hermes Fusion Proxy v%s starting on %s:%s",
        PROXY_VERSION,
        PROXY_HOST,
        PROXY_PORT,
    )

    _load_env()
    _load_session_map()
    _start_serve()

    _check_compatibility()
    _sync_models()

    cleanup_thread = threading.Thread(target=_cleanup_timer, daemon=True)
    cleanup_thread.start()
    logger.info("Session cleanup thread started (interval=%ss)", CLEANUP_INTERVAL)

    model_sync_thread = threading.Thread(target=_model_sync_timer, daemon=True)
    model_sync_thread.start()
    logger.info("Model sync thread started (interval=%ss)", MODEL_SYNC_INTERVAL)

    server = ThreadPoolHTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)

    def shutdown(sig: int, frame: Any = None) -> None:
        logger.info("Shutting down, cleaning up %d sessions...", len(_session_map))
        for key, state in list(_session_map.items()):
            _delete_session(state["oc_session_id"])
        _session_map.clear()
        server.shutdown()
        _stop_serve()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Proxy ready at http://%s:%s (context=%s, sessions=%s TTL)",
        PROXY_HOST,
        PROXY_PORT,
        CONTEXT_LENGTH,
        SESSION_TTL,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown(0)


if __name__ == "__main__":
    main()
