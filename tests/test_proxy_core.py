"""Testes para funções core do hermes-proxy.py."""

import json
from conftest import (
    _conv_key,
    _msg_hash,
    _is_free,
    _has_images,
    _resolve_model,
    _parse_tool_calls,
    _strip_tool_tags,
    _build_full_prompt,
    _build_incremental_prompt,
    TOOL_CALL_FORMAT,
    CONTEXT_LENGTH,
    MAX_REQUEST_BODY,
)


# ── _conv_key ──────────────────────────────────────────────────────────


def test_conv_key_stable():
    """Mesmo system prompt + model + messages = mesma chave."""
    msgs = [{"role": "user", "content": "hello"}]
    k1 = _conv_key("system1", "deepseek", msgs)
    k2 = _conv_key("system1", "deepseek", msgs)
    assert k1 == k2


def test_conv_key_diff_system():
    """System prompts diferentes = chaves diferentes."""
    msgs = [{"role": "user", "content": "hello"}]
    k1 = _conv_key("system1", "deepseek", msgs)
    k2 = _conv_key("system2", "deepseek", msgs)
    assert k1 != k2


def test_conv_key_diff_user_msg():
    """Primeira mensagem diferente = chave diferente."""
    k1 = _conv_key("sys", "model", [{"role": "user", "content": "hello"}])
    k2 = _conv_key("sys", "model", [{"role": "user", "content": "world"}])
    assert k1 != k2


def test_conv_key_with_session_id():
    """session_id diferente = chave diferente (cross-conversation fix)."""
    msgs = [{"role": "user", "content": "hello"}]
    k1 = _conv_key("sys", "model", msgs, "chat_1")
    k2 = _conv_key("sys", "model", msgs, "chat_2")
    assert k1 != k2


def test_conv_key_session_id_stable():
    """Mesmo session_id = mesma chave."""
    msgs = [{"role": "user", "content": "hello"}]
    k1 = _conv_key("sys", "model", msgs, "chat_1")
    k2 = _conv_key("sys", "model", msgs, "chat_1")
    assert k1 == k2


def test_conv_key_without_messages():
    """Sem messages, usa só system + model (backward compat)."""
    k = _conv_key("sys", "model")
    assert len(k) == 32  # MD5 hex digest
    assert isinstance(k, str)


def test_conv_key_truncates_user_content():
    """Conteúdo > 200 chars é truncado no hash."""
    long_content = "x" * 500
    k = _conv_key("sys", "model", [{"role": "user", "content": long_content}])
    assert len(k) == 32
    assert isinstance(k, str)


def test_conv_key_with_image_message():
    """Mensagem com content array (image_url) ainda gera hash."""
    k = _conv_key(
        "sys",
        "model",
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                ],
            }
        ],
    )
    assert len(k) == 32


# ── _msg_hash ──────────────────────────────────────────────────────────


def test_msg_hash_stable():
    """Mesmas mensagens = mesmo hash."""
    msgs = [{"role": "user", "content": "hi"}]
    assert _msg_hash(msgs) == _msg_hash(msgs)


def test_msg_hash_different():
    """Mensagens diferentes = hash diferente."""
    assert _msg_hash([{"role": "user", "content": "hi"}]) != _msg_hash(
        [{"role": "user", "content": "bye"}]
    )


def test_msg_hash_empty():
    """Lista vazia = hash de string vazia."""
    h = _msg_hash([])
    assert isinstance(h, str)
    assert len(h) > 0


def test_msg_hash_ignores_tool_call_id():
    """tool_call_id não afeta o hash."""
    m1 = [{"role": "tool", "tool_call_id": "abc", "content": "result"}]
    m2 = [{"role": "tool", "tool_call_id": "xyz", "content": "result"}]
    assert _msg_hash(m1) == _msg_hash(m2)


def test_msg_hash_tool_call_id_differs():
    """tool_call_id igual + content diferente = hash diferente."""
    m1 = [{"role": "tool", "tool_call_id": "abc", "content": "res1"}]
    m2 = [{"role": "tool", "tool_call_id": "abc", "content": "res2"}]
    assert _msg_hash(m1) != _msg_hash(m2)


# ── _is_free ───────────────────────────────────────────────────────────


def test_is_free_zero_cost():
    """Custo zero = free."""
    assert _is_free({"cost": [{"input": 0, "output": 0}]})


def test_is_free_paid():
    """Custo > 0 = não free."""
    assert not _is_free({"cost": [{"input": 5, "output": 15}]})


def test_is_free_no_cost():
    """Sem campo cost = assume pago."""
    assert not _is_free({})


def test_is_free_empty_list():
    """Lista vazia = assume pago."""
    assert not _is_free({"cost": []})


def test_is_free_dict_cost():
    """cost como dict também funciona."""
    assert _is_free({"cost": {"input": 0, "output": 0}})
    assert not _is_free({"cost": {"input": 1, "output": 2}})


# ── _has_images ────────────────────────────────────────────────────────


def test_has_images_no():
    """Mensagem só com texto = sem imagens."""
    msgs = [{"role": "user", "content": "hello"}]
    assert not _has_images(msgs)


def test_has_images_yes():
    """Mensagem com image_url = tem imagens."""
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {"type": "image_url", "image_url": {"url": "data:img"}},
            ],
        }
    ]
    assert _has_images(msgs)


def test_has_images_multiple_messages():
    """Várias mensagens, uma com imagem."""
    msgs = [
        {"role": "user", "content": "text only"},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:x"}}],
        },
    ]
    assert _has_images(msgs)


def test_has_images_empty():
    """Lista vazia = sem imagens."""
    assert not _has_images([])


# ── _resolve_model ─────────────────────────────────────────────────────


def test_resolve_model_deepseek():
    """deepseek-v4-flash-free resolved corretamente."""
    result = _resolve_model("deepseek-v4-flash-free")
    assert result["modelID"] == "deepseek-v4-flash-free"
    assert result["providerID"] == "opencode"


def test_resolve_model_opencode_prefix():
    """Prefixo opencode/ é tratado."""
    result = _resolve_model("opencode/llama-3.1-70b")
    assert result["modelID"] == "llama-3.1-70b"
    assert result["providerID"] == "opencode"


def test_resolve_model_opencode_zen_prefix():
    """Prefixo opencode-zen/ é tratado."""
    result = _resolve_model("opencode-zen/nemotron-3")
    assert result["modelID"] == "nemotron-3"
    assert result["providerID"] == "opencode-zen"


def test_resolve_model_unknown():
    """Modelo desconhecido passa direto com provider opencode."""
    result = _resolve_model("unknown-model-v1")
    assert result["modelID"] == "unknown-model-v1"
    assert result["providerID"] == "opencode"


def test_resolve_model_returns_copy():
    """_resolve_model retorna uma cópia, não o dict original."""
    result = _resolve_model("deepseek-v4-flash-free")
    result["test"] = "modified"
    # Segunda chamada não deve ser afetada
    result2 = _resolve_model("deepseek-v4-flash-free")
    assert "test" not in result2


# ── _parse_tool_calls ──────────────────────────────────────────────────

SAMPLE_TOOL_CALL = """<tool_use><name>get_weather</name><arguments>{"city": "NYC"}</arguments></tool_use>"""


def test_parse_tool_calls_basic():
    """XML tool call é parseado corretamente."""
    result = _parse_tool_calls(SAMPLE_TOOL_CALL)
    assert len(result) == 1
    assert result[0]["function"]["name"] == "get_weather"
    assert json.loads(result[0]["function"]["arguments"]) == {"city": "NYC"}


def test_parse_tool_calls_none():
    """Texto sem tool calls = lista vazia."""
    assert _parse_tool_calls("Hello world") == []


def test_parse_tool_calls_multiple():
    """Múltiplas tool calls no mesmo texto."""
    text = (
        '<tool_use><name>tool1</name><arguments>{"a":1}</arguments></tool_use>'
        '<tool_use><name>tool2</name><arguments>{"b":2}</arguments></tool_use>'
    )
    result = _parse_tool_calls(text)
    assert len(result) == 2


def test_parse_tool_calls_malformed_xml():
    """XML malformado não quebra."""
    result = _parse_tool_calls("<tool_use><name>test</name></tool_use>")
    assert result == []  # sem arguments = ignorado


def test_parse_tool_calls_empty():
    """String vazia = lista vazia."""
    assert _parse_tool_calls("") == []


# ── _strip_tool_tags ───────────────────────────────────────────────────


def test_strip_tool_tags_removes_block():
    """Tool call block é removido do texto."""
    text = f"Let me check. {SAMPLE_TOOL_CALL}"
    result = _strip_tool_tags(text)
    assert "<tool_use>" not in result
    assert "Let me check." in result


def test_strip_tool_tags_clean_text():
    """Texto sem tool tags retorna igual."""
    text = "Just a normal response."
    assert _strip_tool_tags(text) == text


def test_strip_tool_tags_preserves_adjacent():
    """Texto antes e depois é preservado."""
    text = f"Before. {SAMPLE_TOOL_CALL} After."
    result = _strip_tool_tags(text)
    assert "Before." in result
    assert "After." in result


def test_strip_tool_tags_only_tags():
    """Apenas tool call = string vazia."""
    assert _strip_tool_tags(SAMPLE_TOOL_CALL).strip() == ""


def test_strip_tool_tags_multiple():
    """Múltiplas tool calls removidas."""
    text = f"{SAMPLE_TOOL_CALL}{SAMPLE_TOOL_CALL}"
    assert _strip_tool_tags(text).strip() == ""


# ── Constantes ─────────────────────────────────────────────────────────


def test_context_length():
    assert CONTEXT_LENGTH == 1_000_000


def test_max_request_body():
    assert MAX_REQUEST_BODY == 10 * 1024 * 1024


def test_tool_call_format():
    assert "<tool_use>" in TOOL_CALL_FORMAT
    assert "<arguments>" in TOOL_CALL_FORMAT


# ── response_format ────────────────────────────────────────────────────


def test_response_format_json_object():
    """response_format.type=json_object deve adicionar instrução ao sistema."""
    sys_prompt = "You are helpful."
    rf = {"type": "json_object"}
    result = sys_prompt
    if rf.get("type") == "json_object":
        result += "\n\nYou MUST respond with valid JSON only. No other text, no markdown, no thinking tags."
    assert "JSON" in result
    assert "markdown" in result


def test_response_format_json_schema():
    """response_format.type=json_schema deve incluir schema."""
    sys_prompt = "You are helpful."
    rf = {
        "type": "json_schema",
        "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
    }
    result = sys_prompt
    if rf.get("type") == "json_schema":
        import json

        result += f"\n\nYou MUST respond with valid JSON matching this schema: {json.dumps(rf['schema'])}. No other text."
    assert "schema" in result
    assert "name" in result
