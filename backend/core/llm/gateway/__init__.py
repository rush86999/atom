"""LLM Gateway: inbound OpenAI/Anthropic-compatible surface over BYOK routing.

Exposes Atom's existing routing/fallback/self-healing layer as an OpenAI- and
Anthropic-compatible gateway so external AI tools (Claude Code, Hermes, any
OpenAI-SDK app) can plug in with a base URL + ``atom_sk_*`` key.

See docs/architecture/LLM_GATEWAY.md.
"""
from typing import Any, Dict

from fastapi import HTTPException

from core.llm.byok_handler import (
    AllProvidersFailedError,
    GatewayBlockedError,
    NoProvidersConfiguredError,
)
from core.llm.gateway.auth import GatewayIdentity, get_gateway_identity
from core.llm.gateway.gateway_service import (
    GATEWAY_ENABLED,
    GatewayService,
    get_gateway_enabled,
    require_gateway_enabled,
)
from core.llm.gateway.wire_formats import openai_error_to_anthropic


def map_gateway_error(exc: Exception, anthropic: bool = False) -> Dict[str, Any]:
    """Central gateway error table -> JSON body (no str(e) leaks).

    Standalone so both route modules and unit tests can map errors without
    constructing a GatewayService.
    """
    if isinstance(exc, NoProvidersConfiguredError):
        status, message, code = 503, "No LLM providers configured for this account.", "no_llm_provider"
        extra = {"recovery_url": getattr(exc, "recovery_url", "/settings/ai")}
    elif isinstance(exc, GatewayBlockedError):
        status, message, code = 429, exc.message, exc.reason
        extra = {}
    elif isinstance(exc, AllProvidersFailedError):
        status, message, code = 502, "All LLM providers failed. Please try again.", "all_providers_failed"
        extra = {}
    elif isinstance(exc, HTTPException):
        status, message, code = exc.status_code, str(exc.detail), "gateway_error"
        extra = {}
    elif isinstance(exc, ValueError):
        status, message, code = 400, "Invalid request.", "invalid_request"
        extra = {}
    else:
        status, message, code = 500, "Internal server error.", "internal_error"
        extra = {}

    if anthropic:
        body: Dict[str, Any] = openai_error_to_anthropic(status, code, message)
    else:
        error: Dict[str, Any] = {
            "message": message,
            "type": "server_error" if status >= 500 else "invalid_request_error",
            "param": None,
            "code": code,
        }
        error.update(extra)
        body = {"error": error}
    body["_status"] = status
    return body


__all__ = [
    "GATEWAY_ENABLED",
    "GatewayService",
    "GatewayIdentity",
    "get_gateway_identity",
    "get_gateway_enabled",
    "require_gateway_enabled",
    "map_gateway_error",
]
