"""Gateway service: resolves routing and executes completions through BYOK.

Builds a per-request :class:`BYOKHandler` so gateway calls always carry the
caller's workspace/tenant/user identity (passing ``db`` also closes the
``__init__`` session-leak path, and passing ``user_id`` activates the
``LLMCredentialService`` — required for subscription-credential reuse, Phase D).

See docs/architecture/LLM_GATEWAY.md.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    GatewayBlockedError,
    NoProvidersConfiguredError,
)
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.gateway.auth import GatewayIdentity
from core.llm.intent_detector import IntentDetector
from core.llm.routing_overrides import parse_routing_overrides
from core.models import User

logger = logging.getLogger(__name__)

def gateway_enabled() -> bool:
    """Env wins > runtime_settings DB row (UI admin) > default."""
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_GATEWAY_ENABLED", True)


def prefer_cost() -> bool:
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_GATEWAY_PREFER_COST", True)


def default_max_tokens() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_GATEWAY_DEFAULT_MAX_TOKENS", 1000)

GATEWAY_ENABLED = gateway_enabled()
PREFER_COST = prefer_cost()
DEFAULT_MAX_TOKENS = default_max_tokens()

_KNOWN_TIER_VALUES = {t.value for t in CognitiveTier}


class GatewayService:
    """Thin orchestrator wrapping a per-request BYOKHandler."""

    def __init__(self, identity: GatewayIdentity, db: Session):
        self.identity = identity
        self.db = db
        self.handler = BYOKHandler(
            workspace_id=identity.workspace_id,
            tenant_id=identity.tenant_id,
            db_session=db,
            user_id=identity.user_id,
        )

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #
    async def _resolve_route(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str],
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """Return ``(provider_id, model)`` for this request honoring headers.

        Header overrides (in precedence order, see docs/reference/ROUTING_HEADERS.md):
        ``x-atom-model`` forces the model; ``x-atom-tier`` forces the cognitive
        tier; ``x-atom-intent`` forces intent. Otherwise cost-aware BPC routing.

        The intent override (when present) is threaded through the same
        learning-router re-rank ``generate_response`` uses — previously the
        parsed value was discarded here, so ``x-atom-intent`` was a documented
        no-op on the gateway surface.
        """
        from core.llm.gateway.wire_formats import prompt_from_messages

        overrides = parse_routing_overrides(headers or {})
        prompt = prompt_from_messages(messages)

        forced_model = overrides.get("model") or (
            model if model and model not in ("auto", "") else None
        )
        forced_tier = overrides.get("tier")
        forced_intent = overrides.get("intent")

        complexity = self.handler.analyze_query_complexity(prompt, "chat")
        prefer_cost = prefer_cost()

        if forced_tier:
            tier = _parse_tier(forced_tier)
            if tier is not None:
                options = self.handler.get_ranked_providers(
                    complexity,
                    "chat",
                    prefer_cost=prefer_cost,
                    cognitive_tier=tier,
                )
            else:
                options = []
        else:
            try:
                options = self.handler.get_ranked_providers(
                    complexity,
                    "chat",
                    prefer_cost=prefer_cost,
                )
            except NoProvidersConfiguredError:
                raise
            except Exception as e:
                logger.warning(f"Gateway routing fallback to first client: {e}")
                options = []

        if options:
            if forced_intent:
                options = await self.handler._rerank_with_learning(
                    options, prompt, "chat", intent=forced_intent
                )
            routed_provider, routed_model = options[0]
        else:
            routed_provider, routed_model = self._absolute_fallback()

        if forced_model:
            return self._resolve_provider_for_model(routed_provider, forced_model)
        return routed_provider, routed_model

    def _optimal(self) -> Tuple[str, str]:
        try:
            return self.handler.get_optimal_provider(
                self.handler.analyze_query_complexity("", "chat"),
                "chat",
                prefer_cost=prefer_cost(),
            )
        except NoProvidersConfiguredError:
            raise
        except Exception as e:
            logger.warning(f"Gateway routing fallback to first client: {e}")
            return self._absolute_fallback()

    def _absolute_fallback(self) -> Tuple[str, str]:
        """First configured client + its configured default model.

        The model comes from the provider's own config (``AIProviderConfig.
        model``) so an Anthropic-only deployment falls back to a model
        Anthropic actually serves — the previous hardcoded ``"gpt-4o-mini"``
        guaranteed a provider-level failure for every non-OpenAI client.
        """
        clients = self.handler.async_clients or self.handler.clients
        if clients:
            provider_id = list(clients.keys())[0]
            default_model = None
            try:
                cfg = (self.handler.byok_manager.providers or {}).get(provider_id)
                if cfg is not None and isinstance(getattr(cfg, "model", None), str):
                    default_model = cfg.model
            except Exception:
                default_model = None
            return provider_id, default_model or "gpt-4o-mini"
        raise NoProvidersConfiguredError()

    def _resolve_provider_for_model(self, routed_provider: str, model: str) -> Tuple[str, str]:
        """Find the first configured client serving ``model``; else routed provider."""
        for pid in (self.handler.async_clients.keys() | self.handler.clients.keys()):
            if pid == routed_provider:
                continue
            if self.handler._provider_serves_model(pid, model):
                return pid, model
        return routed_provider, model

    # ------------------------------------------------------------------ #
    # Models
    # ------------------------------------------------------------------ #
    def list_models(self) -> Dict[str, Any]:
        """OpenAI model-list shape from configured clients + registry."""
        client_ids = list(self.handler.async_clients.keys()) or list(self.handler.clients.keys())
        data: List[Dict[str, Any]] = []
        seen: set = set()
        for pid in client_ids:
            models = self._models_for_provider(pid)
            for mid in models:
                if mid in seen:
                    continue
                seen.add(mid)
                data.append({"id": mid, "object": "model", "owned_by": "atom"})
        # If no concrete models could be derived, surface provider ids as models.
        if not data:
            for pid in client_ids:
                data.append({"id": pid, "object": "model", "owned_by": "atom"})
        return {"object": "list", "data": data}

    def _models_for_provider(self, provider_id: str) -> List[str]:
        """Registry models for a provider; falls back to the configured model.

        Previously imported a nonexistent ``get_models_for_provider`` from
        ``core.llm.registry.queries`` — the ImportError was swallowed, so the
        model registry was NEVER consulted and only the config fallback was
        ever surfaced (``GET /v1/models`` returned a stub). The query now
        exists (``core/llm/registry/queries.py``) and is invoked with the
        caller's tenant scope.
        """
        try:
            from core.llm.registry.queries import get_models_for_provider

            return get_models_for_provider(self.db, provider_id)
        except Exception:
            pass
        cfg = self.handler.byok_manager.providers.get(provider_id)
        if cfg and cfg.model:
            return [cfg.model]
        return []

    # ------------------------------------------------------------------ #
    # Errors
    # ------------------------------------------------------------------ #
    def map_gateway_error(self, exc: Exception, anthropic: bool = False) -> Dict[str, Any]:
        """Central gateway error table -> JSON body (no str(e) leaks)."""
        from core.llm.gateway.wire_formats import openai_error_to_anthropic

        if isinstance(exc, NoProvidersConfiguredError):
            return self._error_body(
                status=503,
                message="No LLM providers configured for this account.",
                code="no_llm_provider",
                anthropic=anthropic,
                recovery_url=getattr(exc, "recovery_url", "/settings/ai"),
            )
        if isinstance(exc, GatewayBlockedError):
            return self._error_body(
                status=429,
                message=exc.message,
                code=exc.reason,
                anthropic=anthropic,
            )
        if isinstance(exc, AllProvidersFailedError):
            return self._error_body(
                status=502,
                message="All LLM providers failed. Please try again.",
                code="all_providers_failed",
                anthropic=anthropic,
            )
        if isinstance(exc, HTTPException):
            detail = exc.detail
            return self._error_body(
                status=exc.status_code,
                message=str(detail),
                code="gateway_error",
                anthropic=anthropic,
            )
        if isinstance(exc, ValueError):
            return self._error_body(
                status=400,
                message="Invalid request.",
                code="invalid_request",
                anthropic=anthropic,
            )
        logger.error(f"Gateway error: {exc}")
        return self._error_body(
            status=500,
            message="Internal server error.",
            code="internal_error",
            anthropic=anthropic,
        )

    def _error_body(
        self,
        status: int,
        message: str,
        code: str,
        anthropic: bool = False,
        recovery_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        from core.llm.gateway.wire_formats import openai_error_to_anthropic

        if anthropic:
            body = openai_error_to_anthropic(status, code, message)
        else:
            error: Dict[str, Any] = {
                "message": message,
                "type": "server_error" if status >= 500 else "invalid_request_error",
                "param": None,
                "code": code,
            }
            if recovery_url:
                error["recovery_url"] = recovery_url
            body = {"error": error}
        body["_status"] = status
        return body


def record_gateway_span(
    model: Optional[str],
    provider: Optional[str],
    status_code: Optional[int],
    latency_ms: Optional[int],
    usage: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an observability span for one gateway request (fire-and-forget).

    Called from the gateway routes' single logging choke point
    (``_log_and_alert`` in ``api/openai_gateway_routes.py``) so both the
    OpenAI- and Anthropic-compatible surfaces — success, error, and stream
    paths — emit exactly one ``llm.gateway.request`` span each. Token usage
    is read defensively: only fields actually present on the caller-supplied
    usage dict are recorded.
    """
    import time as _time
    import uuid as _uuid

    from core.observability.tracing import record_span

    usage = usage or {}
    ended = _time.time()
    attributes: Dict[str, Any] = {
        "model": model,
        "provider": provider,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if "prompt_tokens" in usage:
        attributes["prompt_tokens"] = usage.get("prompt_tokens")
    if "completion_tokens" in usage:
        attributes["completion_tokens"] = usage.get("completion_tokens")
    try:
        record_span(
            trace_id=str(_uuid.uuid4()),
            name="llm.gateway.request",
            kind="llm.gateway",
            attributes=attributes,
            started_at=ended - max(0.0, (latency_ms or 0) / 1000.0),
            ended_at=ended,
            status="ok" if (status_code or 500) < 400 else "error",
        )
    except Exception as exc:  # observability must never break the gateway
        logger.debug(f"gateway span recording skipped: {exc}")


def _parse_tier(value: str) -> Optional[CognitiveTier]:
    """Parse an x-atom-tier override into a CognitiveTier, or None."""
    try:
        return CognitiveTier(value.lower())
    except ValueError:
        logger.warning(f"Unknown cognitive tier override: {value}")
        return None


def get_gateway_enabled() -> bool:
    """Central master-switch check for the gateway surface."""
    return gateway_enabled()


def require_gateway_enabled() -> None:
    """Raise 404 when the gateway master switch is off."""
    if not gateway_enabled():
        raise HTTPException(status_code=404, detail="Gateway disabled")


def get_user_or_none(identity: GatewayIdentity) -> Optional[User]:
    return identity.user
