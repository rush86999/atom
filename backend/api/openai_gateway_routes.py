"""LLM Gateway routes: OpenAI- and Anthropic-compatible inbound surface.

Exposes Atom's BYOK routing layer as ``/v1/chat/completions`` (OpenAI),
``/v1/messages`` (Anthropic), and ``/v1/models``. All routing, fallback,
self-healing, and cost tracking reuse the existing ``BYOKHandler``; only the
wire protocol + identity model are new here.

See docs/architecture/LLM_GATEWAY.md.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.llm.byok_handler import AllProvidersFailedError, GatewayBlockedError, NoProvidersConfiguredError
from core.llm.gateway import (
    GATEWAY_ENABLED,
    GatewayService,
    get_gateway_identity,
    map_gateway_error,
    require_gateway_enabled,
)
from core.llm.gateway.auth import GatewayIdentity
from core.llm.gateway.budget_alerts import record_gateway_spend
from core.llm.gateway.gateway_service import default_max_tokens
from core.llm.gateway.request_logger import estimate_cost_usd, log_gateway_request
from core.llm.gateway.wire_formats import (
    anthropic_request_to_openai,
    map_stop_reason,
    openai_response_to_anthropic,
    prompt_from_messages,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["LLM Gateway"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

MAX_GATEWAY_BODY_BYTES = 64 * 1024 * 1024  # 64 MiB (R55 parity)


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class OpenAIChatRequest(BaseModel):
    model: Optional[str] = "auto"
    messages: List[Dict[str, Any]] = Field(..., min_length=1)
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    top_p: Optional[float] = None
    user: Optional[str] = None
    n: Optional[int] = None
    model_config = {"extra": "ignore"}  # SDK forward-compat


class AnthropicMessagesRequest(BaseModel):
    model: Optional[str] = "auto"
    messages: List[Dict[str, Any]] = Field(..., min_length=1)
    system: Optional[Union[str, List[Dict[str, Any]]]] = None
    max_tokens: int = Field(default_factory=default_max_tokens)
    temperature: float = 0.7
    stop_sequences: Optional[List[str]] = None
    top_p: Optional[float] = None
    stream: bool = False
    model_config = {"extra": "ignore"}


# --------------------------------------------------------------------------- #
# SSE helpers
# --------------------------------------------------------------------------- #
def _openai_sse(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _error_response(exc: Exception, anthropic: bool = False) -> JSONResponse:
    body = map_gateway_error(exc, anthropic=anthropic)
    status = body.pop("_status", 500)
    return JSONResponse(status_code=status, content=body)


async def _log_and_alert(
    identity: GatewayIdentity,
    db: Session,
    *,
    model: str,
    provider: str,
    stream: bool,
    status_code: int,
    latency_ms: Optional[int],
    usage: Optional[Dict[str, Any]] = None,
    request_body: Any = None,
    response_body: Any = None,
) -> None:
    """Persist a GatewayRequestLog row + feed gateway spend alerts (B3/B4)."""
    prompt_tokens = (usage or {}).get("prompt_tokens")
    completion_tokens = (usage or {}).get("completion_tokens")
    cost = estimate_cost_usd(model, prompt_tokens or 0, completion_tokens or 0)
    log_gateway_request(
        db,
        identity,
        provider=provider,
        model=model,
        stream=stream,
        status_code=status_code,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost,
        request_body=request_body,
        response_body=response_body,
    )
    await record_gateway_spend(identity.workspace_id, cost, user_id=identity.user_id)
    # Observability seam (W?): one span per gateway request, emitted from this
    # single choke point so all surfaces/paths are covered uniformly.
    try:
        from core.llm.gateway.gateway_service import record_gateway_span

        record_gateway_span(model, provider, status_code, latency_ms, usage=usage)
    except Exception as exc:  # never break the gateway for observability
        logger.debug(f"gateway span emission skipped: {exc}")


# --------------------------------------------------------------------------- #
# OpenAI: POST /v1/chat/completions
# --------------------------------------------------------------------------- #
@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    body: OpenAIChatRequest,
    identity: GatewayIdentity = Depends(get_gateway_identity),
    db: Session = Depends(get_db),
):
    require_gateway_enabled()
    service = GatewayService(identity, db)
    max_tokens = body.max_tokens or default_max_tokens()
    try:
        provider, model = await service._resolve_route(
            body.messages, body.model, dict(request.headers)
        )
    except (NoProvidersConfiguredError, ValueError) as exc:
        await _log_and_alert(
            identity, db, model=body.model or "auto", provider="unresolved", stream=False,
            status_code=map_gateway_error(exc).get("_status", 500),
            latency_ms=0,
            request_body=body.model_dump(),
        )
        return _error_response(exc)
    extra_kwargs: Dict[str, Any] = {}
    if body.stop is not None:
        extra_kwargs["stop"] = body.stop
    if body.top_p is not None:
        extra_kwargs["top_p"] = body.top_p
    if body.user:
        extra_kwargs["user"] = body.user

    if body.stream:
        return StreamingResponse(
            _openai_stream(service, body.messages, model, provider, body.temperature, max_tokens, extra_kwargs, identity, db),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    start = time.time()
    try:
        result = await service.handler.chat_completion(
            body.messages, model, provider,
            temperature=body.temperature, max_tokens=max_tokens,
            task_type="chat", extra_kwargs=extra_kwargs,
        )
    except (NoProvidersConfiguredError, GatewayBlockedError, AllProvidersFailedError, ValueError) as exc:
        await _log_and_alert(
            identity, db, model=model, provider=provider, stream=False,
            status_code=map_gateway_error(exc).get("_status", 500),
            latency_ms=int((time.time() - start) * 1000),
            request_body=body.model_dump(),
        )
        return _error_response(exc)
    await _log_and_alert(
        identity, db, model=model, provider=provider, stream=False, status_code=200,
        latency_ms=int((time.time() - start) * 1000),
        usage=result.get("usage"), request_body=body.model_dump(), response_body=result,
    )
    return JSONResponse(status_code=200, content=result)


async def _openai_stream(
    service: GatewayService,
    messages: List[Dict[str, Any]],
    model: str,
    provider: str,
    temperature: float,
    max_tokens: int,
    extra_kwargs: Dict[str, Any],
    identity: GatewayIdentity,
    db: Session,
):
    acc = ""
    chunk_id = f"chatcmpl_atom_{uuid.uuid4().hex}"
    created = int(time.time())
    stream_status = 200
    try:
        yield _openai_sse({
            "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        })
        async for delta in service.handler.stream_completion(
            messages, model, provider, temperature=temperature, max_tokens=max_tokens,
            task_type="chat", extra_kwargs=extra_kwargs or None,
        ):
            if delta.startswith("\n\n[Error:"):
                stream_status = 502
                yield _openai_sse({
                    "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "stop"}],
                })
                yield "data: [DONE]\n\n"
                return
            acc += delta
            yield _openai_sse({
                "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
            })
        # finish + usage chunks.
        # NOTE: this is a rough chars/4 estimate because stream_completion
        # yields only text deltas, not provider usage. Real usage would require
        # stream_options.include_usage upstream; for now we estimate so spend
        # tracking is approximately right rather than fabricated from a
        # timestamp (the prior bug).
        est = max(1, len(acc) // 4)
        yield _openai_sse({
            "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        })
        yield _openai_sse({
            "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            "usage": {"prompt_tokens": est, "completion_tokens": est, "total_tokens": 2 * est},
        })
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"OpenAI gateway stream failed: {e}")
        stream_status = 500
        yield _openai_sse({
            "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "stop"}],
        })
        yield "data: [DONE]\n\n"
    finally:
        # Record spend + log for BOTH clean completion and client disconnect.
        # Previously this sat only on the success path, so a mid-stream
        # disconnect consumed provider tokens (billed to the owner) with no
        # spend record — undercounting budget and leaving the audit log
        # incomplete. The estimate is best-effort from accumulated text.
        est = max(1, len(acc) // 4)
        await _log_and_alert(
            identity, db, model=model, provider=provider, stream=True,
            status_code=stream_status,
            latency_ms=int((time.time() - created) * 1000),
            usage={"prompt_tokens": est, "completion_tokens": est},
            response_body={"choices": [{"message": {"content": acc}}]},
        )


# --------------------------------------------------------------------------- #
# Anthropic: POST /v1/messages
# --------------------------------------------------------------------------- #
@router.post("/messages")
async def anthropic_messages(
    request: Request,
    body: AnthropicMessagesRequest,
    identity: GatewayIdentity = Depends(get_gateway_identity),
    db: Session = Depends(get_db),
):
    require_gateway_enabled()
    service = GatewayService(identity, db)
    openai_payload = anthropic_request_to_openai(body.model_dump(exclude_unset=True))
    messages: List[Dict[str, Any]] = openai_payload["messages"]
    model = body.model if body.model not in ("auto", None) else None
    try:
        provider, model = await service._resolve_route(messages, model, dict(request.headers))
    except (NoProvidersConfiguredError, ValueError) as exc:
        await _log_and_alert(
            identity, db, model=body.model or "auto", provider="unresolved", stream=False,
            status_code=map_gateway_error(exc, anthropic=True).get("_status", 500),
            latency_ms=0,
            request_body=body.model_dump(),
        )
        return _error_response(exc, anthropic=True)
    extra_kwargs: Dict[str, Any] = {}
    if openai_payload.get("stop"):
        extra_kwargs["stop"] = openai_payload["stop"]
    if body.top_p is not None:
        extra_kwargs["top_p"] = body.top_p

    if body.stream:
        return StreamingResponse(
            _anthropic_stream(service, messages, model, provider, body.temperature, body.max_tokens, extra_kwargs, identity, db),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    start = time.time()
    try:
        result = await service.handler.chat_completion(
            messages, model, provider,
            temperature=body.temperature, max_tokens=body.max_tokens,
            task_type="chat", extra_kwargs=extra_kwargs,
        )
    except (NoProvidersConfiguredError, GatewayBlockedError, AllProvidersFailedError, ValueError) as exc:
        await _log_and_alert(
            identity, db, model=model, provider=provider, stream=False,
            status_code=map_gateway_error(exc, anthropic=True).get("_status", 500),
            latency_ms=int((time.time() - start) * 1000),
            request_body=body.model_dump(),
        )
        return _error_response(exc, anthropic=True)
    await _log_and_alert(
        identity, db, model=model, provider=provider, stream=False, status_code=200,
        latency_ms=int((time.time() - start) * 1000),
        usage=result.get("usage"), request_body=body.model_dump(), response_body=result,
    )
    return JSONResponse(status_code=200, content=openai_response_to_anthropic(result))


async def _anthropic_stream(
    service: GatewayService,
    messages: List[Dict[str, Any]],
    model: str,
    provider: str,
    temperature: float,
    max_tokens: int,
    extra_kwargs: Dict[str, Any],
    identity: GatewayIdentity,
    db: Session,
):
    msg_id = f"msg_atom_{uuid.uuid4().hex}"
    created = int(time.time())
    acc = ""
    stream_status = 200
    try:
        yield _format_sse("message_start", {
            "type": "message_start", "message": {
                "id": msg_id, "type": "message", "role": "assistant",
                "content": [], "model": model, "stop_reason": None,
                "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        })
        yield _format_sse("content_block_start", {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        async for delta in service.handler.stream_completion(
            messages, model, provider, temperature=temperature, max_tokens=max_tokens,
            task_type="chat", extra_kwargs=extra_kwargs or None,
        ):
            if delta.startswith("\n\n[Error:"):
                yield _format_sse("content_block_delta", {
                    "type": "content_block_delta", "index": 0,
                    "delta": {"type": "text_delta", "text": ""},
                })
                yield _format_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                yield _format_sse("message_delta", {
                    "type": "message_delta", "delta": {"stop_reason": "error", "stop_sequence": None},
                    "usage": {"output_tokens": 0},
                })
                yield _format_sse("message_stop", {"type": "message_stop"})
                yield _format_sse("error", {"type": "error", "error": {"type": "api_error", "message": "Stream failed"}})
                return
            acc += delta
            yield _format_sse("content_block_delta", {
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": delta},
            })
        yield _format_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        # Estimate output tokens from accumulated streamed text. The prior
        # code used ``max(1, created // 1) % 10000`` where ``created`` was the
        # Unix timestamp — a nonsensical token count that polluted cost
        # tracking and budget alerts. stream_completion yields only text
        # deltas (no provider usage), so a chars/4 estimate is the best we
        # can do without upstream stream_options.
        est_output = max(1, len(acc) // 4)
        yield _format_sse("message_delta", {
            "type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": est_output},
        })
        yield _format_sse("message_stop", {"type": "message_stop"})
    except Exception as e:
        logger.error(f"Anthropic gateway stream failed: {e}")
        stream_status = 500
        yield _format_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        yield _format_sse("message_stop", {"type": "message_stop"})
        yield _format_sse("error", {"type": "error", "error": {"type": "api_error", "message": "Stream failed"}})
    finally:
        # Record spend + log for both clean completion and client disconnect.
        est_output = max(1, len(acc) // 4)
        await _log_and_alert(
            identity, db, model=model, provider=provider, stream=True,
            status_code=stream_status,
            latency_ms=int((time.time() - created) * 1000),
            usage={"prompt_tokens": est_output, "completion_tokens": est_output},
        )


# --------------------------------------------------------------------------- #
# OpenAI: GET /v1/models
# --------------------------------------------------------------------------- #
@router.get("/models")
async def list_models(
    identity: GatewayIdentity = Depends(get_gateway_identity),
    db: Session = Depends(get_db),
):
    require_gateway_enabled()
    service = GatewayService(identity, db)
    return JSONResponse(status_code=200, content=service.list_models())
