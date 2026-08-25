"""Gateway request/response logging (Phase B4).

Persists a ``GatewayRequestLog`` row per gateway call. Metadata is always
recorded; bodies are only persisted when ``ATOM_GATEWAY_LOG_BODIES=true`` and
are PII-redacted, auth-header-stripped, and truncated to 64 KB. Retention sweep
helper deletes rows older than ``ATOM_GATEWAY_LOG_RETENTION_DAYS``.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.models import GatewayRequestLog

logger = logging.getLogger(__name__)

def log_bodies() -> bool:
    """Env wins > runtime_settings DB row (UI admin) > default."""
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_GATEWAY_LOG_BODIES", False)


def log_retention_days() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_GATEWAY_LOG_RETENTION_DAYS", 30)
MAX_LOG_BODY_CHARS = 64 * 1024  # 64 KB truncation

# Headers that must never be persisted (secrets / session material).
AUTH_HEADER_KEYS = {"authorization", "x-api-key", "cookie", "proxy-authorization"}


def _drop_auth_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(headers, dict):
        return {}
    return {k: v for k, v in headers.items() if str(k).lower() not in AUTH_HEADER_KEYS}


def _redact_text(text: str) -> str:
    """Redact PII from text, FAILING CLOSED when the redactor is unavailable.

    When bodies are explicitly logged (``ATOM_GATEWAY_LOG_BODIES=true``) but
    the PII redactor import fails or raises, returning the raw text would
    persist prompts (which often contain PII) verbatim. Instead return a
    placeholder so a redactor failure never leaks raw content.
    """
    if not text:
        return text
    try:
        from core.pii_redactor import redact_pii

        return redact_pii(text)
    except Exception:
        return "[redaction unavailable — body omitted]"


def _truncate(text: str) -> str:
    if text and len(text) > MAX_LOG_BODY_CHARS:
        return text[:MAX_LOG_BODY_CHARS]
    return text


def _sanitize_body(body: Any, include_body: bool) -> Optional[str]:
    """Serialize + redact + truncate a body; None when bodies are disabled."""
    if not include_body or body is None:
        return None
    try:
        raw = json.dumps(body, default=str)
    except Exception:
        raw = str(body)
    return _redact_text(_truncate(raw))


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Best-effort cost estimate for a gateway call (never raises)."""
    try:
        from core.cost_config import get_llm_cost
        from core.dynamic_pricing_fetcher import get_pricing_fetcher

        cost = get_pricing_fetcher().estimate_cost(model, prompt_tokens or 0, completion_tokens or 0)
        if cost is None:
            cost = get_llm_cost(model, prompt_tokens or 0, completion_tokens or 0)
        return cost if cost and cost > 0 else None
    except Exception:
        return None


def log_gateway_request(
    db,
    identity,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    stream: bool = False,
    status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    request_body: Any = None,
    response_body: Any = None,
) -> Optional[str]:
    """Persist a gateway request log row; returns row id or None (best-effort)."""
    try:
        row = GatewayRequestLog(
            id=str(uuid.uuid4()),
            tenant_id=getattr(identity, "tenant_id", None),
            workspace_id=getattr(identity, "workspace_id", None),
            user_id=getattr(identity, "user_id", None),
            api_key_id=getattr(identity, "api_key_id", None),
            provider=provider,
            model=model,
            stream=stream,
            status_code=status_code,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            request_json=_sanitize_body(request_body, log_bodies()),
            response_json=_sanitize_body(response_body, log_bodies()),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)
    except Exception as exc:
        logger.debug(f"Gateway request log skipped: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def sweep_gateway_logs(db) -> int:
    """Delete log rows older than the retention window; returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=log_retention_days())
    try:
        deleted = db.query(GatewayRequestLog).filter(GatewayRequestLog.created_at < cutoff).delete()
        db.commit()
        return int(deleted or 0)
    except Exception as exc:
        logger.debug(f"Gateway log sweep skipped: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0
