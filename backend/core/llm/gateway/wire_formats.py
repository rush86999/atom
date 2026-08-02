"""Pure wire-format translators for the LLM gateway.

These functions perform no I/O and are fully unit-testable. They translate
between the Anthropic Messages API and the OpenAI Chat Completions API so a
single BYOKHandler call path can serve both protocols.

See docs/architecture/LLM_GATEWAY.md for the mapping tables.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


def prompt_from_messages(messages: List[Dict[str, Any]], default: str = "") -> str:
    """Extract the last user message (flattened) for intent/complexity scoring.

    Handles both ``str`` content and OpenAI multimodal content lists
    (concatenating text parts) so intent detection sees real user text rather
    than an empty string.
    """
    if not messages:
        return default
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and part.get("text"):
                        parts.append(str(part["text"]))
                    elif part.get("text"):
                        parts.append(str(part["text"]))
                elif isinstance(part, str):
                    parts.append(part)
            return " ".join(parts)
        return str(content)
    return default


def _content_block_to_openai(block: Dict[str, Any], msg: Dict[str, Any]) -> None:
    """Mutate ``msg`` (a single OpenAI message) with the mapped content part."""
    block_type = block.get("type")
    if block_type == "text":
        text = block.get("text", "")
        if isinstance(msg["content"], str):
            msg["content"] = text
        else:
            msg["content"].append({"type": "text", "text": text})
    elif block_type == "image":
        source = block.get("source") or {}
        if source.get("type") == "url":
            url = source.get("url", "")
            msg["content"].append({"type": "image_url", "image_url": {"url": url}})
        else:
            # base64 source
            media_type = source.get("media_type", "image/png")
            data = source.get("data", "")
            data_url = f"data:{media_type};base64,{data}"
            msg["content"].append({"type": "image_url", "image_url": {"url": data_url}})
    elif block_type in ("tool_use", "tool_result", "thinking", "redacted_thinking"):
        # Best-effort: preserve unknown blocks as text for upstream providers
        # that accept them, otherwise drop.
        text = str(block.get("text") or block.get("content") or "")
        if text and isinstance(msg["content"], list):
            msg["content"].append({"type": "text", "text": text})


def anthropic_request_to_openai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate an Anthropic Messages request into an OpenAI Chat request.

    Handles top-level ``system`` (str or content list -> system message),
    content blocks (image -> ``image_url`` data URL, tool blocks best-effort),
    and ``stop_sequences`` -> ``stop``.
    """
    messages: List[Dict[str, Any]] = []
    system = payload.get("system")
    if system:
        system_text = ""
        if isinstance(system, str):
            system_text = system
        elif isinstance(system, list):
            parts = []
            for part in system:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif isinstance(part, str):
                    parts.append(part)
            system_text = " ".join(parts)
        messages.append({"role": "system", "content": system_text})

    for raw in payload.get("messages", []):
        role = raw.get("role")
        if role == "assistant":
            msg: Dict[str, Any] = {"role": "assistant", "content": []}
        elif role == "user":
            msg = {"role": "user", "content": []}
        else:
            msg = {"role": role, "content": raw.get("content", "")}

        content = raw.get("content")
        if isinstance(content, str):
            msg["content"] = content
        elif isinstance(content, list):
            if not isinstance(msg["content"], list):
                msg["content"] = []
            for block in content:
                if isinstance(block, dict):
                    _content_block_to_openai(block, msg)
                else:
                    msg["content"].append({"type": "text", "text": str(block)})
            if not msg["content"]:
                msg["content"] = ""
        else:
            msg["content"] = ""

        messages.append(msg)

    out: Dict[str, Any] = {
        "messages": messages,
        "temperature": payload.get("temperature", 0.7),
        "max_tokens": payload.get("max_tokens", 1000),
    }
    model = payload.get("model")
    if model:
        out["model"] = model
    stop_sequences = payload.get("stop_sequences")
    if stop_sequences:
        out["stop"] = stop_sequences
    if "top_p" in payload and payload.get("top_p") is not None:
        out["top_p"] = payload["top_p"]
    return out


_STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "max_tokens",
    None: "end_turn",
}


def map_stop_reason(openai_stop_reason: Optional[str]) -> str:
    """Map an OpenAI finish_reason to an Anthropic stop_reason."""
    return _STOP_REASON_MAP.get(openai_stop_reason, openai_stop_reason or "end_turn")


def openai_response_to_anthropic(
    resp: Dict[str, Any], stop_reason: Optional[str] = None
) -> Dict[str, Any]:
    """Translate an OpenAI completion dict into an Anthropic message dict."""
    choices = resp.get("choices") or []
    content_text = ""
    if choices:
        message = choices[0].get("message") or {}
        content_text = message.get("content") or ""
    usage = resp.get("usage") or {}
    return {
        "id": f"msg_atom_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content_text}],
        "model": resp.get("model", ""),
        "stop_reason": stop_reason or map_stop_reason(
            (choices[0].get("finish_reason") if choices else None)
        ),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "created": resp.get("created") or int(time.time()),
    }


_STATUS_TO_ERROR_TYPE = {
    400: "invalid_request_error",
    401: "authentication_error",
    403: "permission_error",
    404: "not_found_error",
    422: "invalid_request_error",
    429: "rate_limit_error",
    500: "api_error",
    502: "api_error",
    503: "overloaded_error",
    504: "api_error",
}


def map_error_type(status: int) -> str:
    """Map an HTTP status to an Anthropic error type."""
    return _STATUS_TO_ERROR_TYPE.get(status, "api_error")


def openai_error_to_anthropic(
    status: int, code: Optional[str], message: str
) -> Dict[str, Any]:
    """Build an Anthropic-shaped error body from an OpenAI-style error."""
    return {
        "type": "error",
        "error": {
            "type": map_error_type(status),
            "message": message,
            "code": code,
        },
    }
