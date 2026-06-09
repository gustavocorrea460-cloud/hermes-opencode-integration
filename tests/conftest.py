"""Fixtures compartilhadas para testes de hermes-proxy.py."""

import importlib.util
import sys
from pathlib import Path

# Carrega hermes-proxy.py como módulo (nome com hífen)
HERMES_PROXY_PATH = Path.home() / ".hermes" / "hermes-proxy.py"
assert HERMES_PROXY_PATH.exists(), f"{HERMES_PROXY_PATH} not found"

spec = importlib.util.spec_from_file_location("hermes_proxy_mod", HERMES_PROXY_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["hermes_proxy_mod"] = mod
spec.loader.exec_module(mod)

# Exporta os símbolos que os testes usam
_conv_key = mod._conv_key
_msg_hash = mod._msg_hash
_is_free = mod._is_free
_has_images = mod._has_images
_messages_to_text = mod._messages_to_text
_messages_to_oc_parts = mod._messages_to_oc_parts
_extract_images_from_content = mod._extract_images_from_content
_parse_tool_calls = mod._parse_tool_calls
_strip_tool_tags = mod._strip_tool_tags
_convert_tools_to_text = mod._convert_tools_to_text
_resolve_model = mod._resolve_model
_build_full_prompt = mod._build_full_prompt
_build_incremental_prompt = mod._build_incremental_prompt
TOOL_CALL_FORMAT = mod.TOOL_CALL_FORMAT
CONTEXT_LENGTH = mod.CONTEXT_LENGTH
MAX_REQUEST_BODY = mod.MAX_REQUEST_BODY
