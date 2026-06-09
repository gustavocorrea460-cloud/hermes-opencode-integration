"""Testes para funções de processamento de mensagens do hermes-proxy.py."""

import json
from conftest import (
    _messages_to_text,
    _messages_to_oc_parts,
    _extract_images_from_content,
    _build_full_prompt,
    _build_incremental_prompt,
    _convert_tools_to_text,
    TOOL_CALL_FORMAT,
)


# ── _messages_to_text ──────────────────────────────────────────────────


def test_simple_user():
    """Mensagem simples do usuário."""
    text = _messages_to_text([{"role": "user", "content": "hello"}])
    assert "User: hello" in text


def test_simple_assistant():
    """Mensagem simples do assistant."""
    text = _messages_to_text([{"role": "assistant", "content": "hi there"}])
    assert "Assistant: hi there" in text


def test_system_is_skipped():
    """System prompt não aparece no texto do usuário."""
    text = _messages_to_text(
        [
            {"role": "system", "content": "you are a bot"},
            {"role": "user", "content": "hello"},
        ]
    )
    assert "System" not in text
    assert "User: hello" in text


def test_tool_message():
    """Mensagem de tool inclui resultado."""
    text = _messages_to_text([{"role": "tool", "name": "search", "content": "results"}])
    assert 'Tool result for "search"' in text
    assert "results" in text


def test_assistant_tool_calls():
    """Tool calls do assistant são convertidas para texto."""
    text = _messages_to_text(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city":"NYC"}',
                        },
                    }
                ],
            }
        ]
    )
    assert "get_weather" in text
    assert "NYC" in text


def test_assistant_with_both():
    """Assistant com texto + tool calls."""
    text = _messages_to_text(
        [
            {
                "role": "assistant",
                "content": "Let me check",
                "tool_calls": [
                    {
                        "function": {"name": "get_weather", "arguments": "{}"},
                    }
                ],
            }
        ]
    )
    assert "Let me check" in text
    assert "get_weather" in text


def test_empty_content():
    """Conteúdo vazio não gera linha."""
    text = _messages_to_text([{"role": "user", "content": ""}])
    assert text.strip() == ""


def test_empty_messages():
    """Lista vazia retorna string vazia."""
    assert _messages_to_text([]) == ""


def test_image_url_stripped():
    """image_url é ignorado (a imagem vai via oc_parts)."""
    text = _messages_to_text(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "data:img"}},
                ],
            }
        ]
    )
    assert "describe" in text
    assert "data:img" not in text


# ── _messages_to_oc_parts ──────────────────────────────────────────────


def test_oc_parts_text_only():
    """Apenas texto = um único text part."""
    parts = _messages_to_oc_parts([{"role": "user", "content": "hello"}])
    assert len(parts) == 1
    assert parts[0]["type"] == "text"
    assert "User: hello" in parts[0]["text"]


def test_oc_parts_assistant():
    """Assistant message vira text part."""
    parts = _messages_to_oc_parts([{"role": "assistant", "content": "hi"}])
    assert parts[0]["type"] == "text"
    assert "Assistant: hi" in parts[0]["text"]


def test_oc_parts_tool():
    """Tool message vira text part com prefixo."""
    parts = _messages_to_oc_parts(
        [{"role": "tool", "name": "search", "content": "res"}]
    )
    assert "Tool" in parts[0]["text"]
    assert "search" in parts[0]["text"]


def test_oc_parts_with_image():
    """Mensagem com imagem = text + file parts."""
    parts = _messages_to_oc_parts(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,abc"},
                    },
                ],
            }
        ]
    )
    types = [p["type"] for p in parts]
    assert "text" in types
    assert "file" in types
    # file part tem url e mime
    file_part = [p for p in parts if p["type"] == "file"][0]
    assert file_part["url"].startswith("data:")
    assert file_part["mime"] == "image/png"


def test_oc_parts_multiple_images():
    """Múltiplas imagens = múltiplos file parts."""
    parts = _messages_to_oc_parts(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,a"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,b"},
                    },
                ],
            }
        ]
    )
    file_parts = [p for p in parts if p["type"] == "file"]
    assert len(file_parts) == 2
    assert file_parts[0]["mime"] == "image/png"
    assert file_parts[1]["mime"] == "image/jpeg"


def test_oc_parts_system_skipped():
    """System prompt não vira part."""
    parts = _messages_to_oc_parts(
        [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert len(parts) == 1


# ── _extract_images_from_content ───────────────────────────────────────


def test_extract_no_images():
    """Content sem image_url = lista vazia."""
    assert _extract_images_from_content([{"type": "text", "text": "hello"}]) == []


def test_extract_data_url():
    """Data URL é extraída corretamente."""
    url = "data:image/png;base64,abcd"
    images = _extract_images_from_content(
        [
            {"type": "image_url", "image_url": {"url": url}},
        ]
    )
    assert len(images) == 1
    assert images[0]["url"] == url
    assert images[0]["mime"] == "image/png"


def test_extract_jpeg():
    """JPEG tem mime correto."""
    images = _extract_images_from_content(
        [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,x"}},
        ]
    )
    assert images[0]["mime"] == "image/jpeg"


def test_extract_not_a_list():
    """String não quebra."""
    assert _extract_images_from_content("plain string") == []


def test_extract_empty():
    """Lista vazia = sem imagens."""
    assert _extract_images_from_content([]) == []


def test_extract_invalid_image_url():
    """image_url sem url válida é ignorado."""
    images = _extract_images_from_content(
        [
            {"type": "image_url", "image_url": "not a dict"},
        ]
    )
    assert images == []


# ── _convert_tools_to_text ─────────────────────────────────────────────


def test_convert_tools_basic():
    """Ferramentas são convertidas para texto."""
    tools = [
        {
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            }
        }
    ]
    text = _convert_tools_to_text(tools)
    assert "get_weather" in text
    assert "Tool" in text or "get_weather" in text


def test_convert_tools_empty():
    """Lista vazia = string vazia."""
    assert _convert_tools_to_text([]) == ""


def test_convert_tools_none():
    """None = string vazia."""
    assert _convert_tools_to_text(None) == ""


# ── _build_full_prompt ─────────────────────────────────────────────────


def test_build_full_prompt_basic():
    """Full prompt tem system + user."""
    sys_p, user_p = _build_full_prompt(
        [{"role": "user", "content": "hello"}],
        None,
        "You are a bot",
    )
    assert "You are a bot" in sys_p
    assert "User: hello" in user_p


def test_build_full_prompt_with_tools():
    """Tools são incluídas no system prompt."""
    tools = [{"function": {"name": "test_tool", "description": "", "parameters": {}}}]
    sys_p, user_p = _build_full_prompt(
        [{"role": "user", "content": "hi"}],
        tools,
        "",
    )
    assert "test_tool" in sys_p


def test_build_full_prompt_no_system():
    """Sem system prompt, usa default."""
    sys_p, user_p = _build_full_prompt(
        [{"role": "user", "content": "hi"}],
        None,
        "",
    )
    assert "helpful" in sys_p


def test_build_full_prompt_multiple_messages():
    """Várias mensagens são concatenadas."""
    msgs = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]
    sys_p, user_p = _build_full_prompt(msgs, None, "system")
    assert "User: first" in user_p
    assert "Assistant: second" in user_p


# ── _build_incremental_prompt ──────────────────────────────────────────


def test_build_incremental_single():
    """Nova mensagem única."""
    text = _build_incremental_prompt([{"role": "user", "content": "new"}])
    assert "User: new" in text


def test_build_incremental_skips_system():
    """System prompt em new_messages é ignorado."""
    text = _build_incremental_prompt(
        [
            {"role": "system", "content": "new rule"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert "System" not in text
    assert "User: hi" in text


def test_build_incremental_empty():
    """Lista vazia."""
    assert _build_incremental_prompt([]) == ""
