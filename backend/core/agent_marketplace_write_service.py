"""Verified agent-marketplace seller publication.

The publish route previously called ``AgentMarketplaceService.
package_agent_for_sale``, which loaded the source agent, inserted an
``AgentTemplate`` and committed with no exact source-agent binding, audit
receipt or replay protection. This module keeps the existing packaging and
redaction rules but makes the decision explicit:

- the current User row is re-read and its active status/role/raw tenant are
  claimed in the publication transaction;
- the exact source ``AgentRegistry`` material is claimed in the same
  transaction;
- the listing insert is flushed, one safe ``AuditLog`` receipt is added, and
  both commit or roll back together;
- same-operation replay is idempotent and changed material conflicts.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import (
    AgentRegistry,
    AgentTemplate,
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-agent-marketplace-publish-1"
_OPERATION_PREFIX = "agent-marketplace"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_PUBLISH = "agent_listing_published"


def _fingerprint(*parts: Any) -> str:
    message = "|".join(
        str(part if part is not None else "") for part in parts)
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str)


def _operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{_OPERATION_PREFIX}:publish:{uuid.uuid4().hex}"
    prefix = f"{_OPERATION_PREFIX}:publish:"
    if not candidate.startswith(prefix):
        candidate = f"{prefix}{candidate}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise ValueError("operation_id is malformed")
    return candidate


def _refused(
    message: str, *, http_status: int = 403,
    error_code: str = "AUTHORITY_REQUIRED", field: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "refused",
        "error": message,
        "error_code": error_code,
        "field": field,
        "http_status": int(http_status),
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _conflict(message: str, *, code: str = "STALE_TARGET") -> Dict[str, Any]:
    return {
        "status": "conflict",
        "error": message,
        "error_code": code,
        "http_status": 409,
        "verification": {"status": "refuted", "effect": "none"},
    }


def _not_applied(message: str) -> Dict[str, Any]:
    return {
        "status": "not_applied",
        "error": message,
        "error_code": "AGENT_MARKETPLACE_TRANSACTION_ROLLED_BACK",
        "http_status": 409,
        "verification": {
            "status": "refused",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
    }


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": None,
        "message": (
            "The agent listing committed but its audit/target readback did "
            "not verify. Reconcile the original operation."),
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_id": target_id,
        "verification": {
            "status": audit_state.get("status", "unavailable"),
            "effect": "committed",
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _effect_unknown(operation_id: str, target_id: str) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": None,
        "message": (
            "The agent listing may have committed, but confirmation was "
            "lost. Reconcile the original operation; do not repeat it "
            "blindly."),
        "operation_id": operation_id,
        "audit_id": None,
        "target_id": target_id,
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
            "error": "COMMIT_OUTCOME_UNKNOWN",
        },
    }


def _with_receipt(
    data: Dict[str, Any], *, operation_id: str, audit_id: Optional[str],
    verification_status: str = "verified",
    effect: str = "committed",
    replay: Optional[str] = None,
) -> Dict[str, Any]:
    result = dict(data)
    verification = {
        "status": verification_status,
        "effect": effect,
        "audit_id": audit_id,
    }
    if replay:
        verification["replay"] = replay
    result["verification"] = verification
    result["operation_id"] = operation_id
    result["audit_id"] = audit_id
    return result


def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "Owner or admin authority is required"),
        http_status=int(actor.get("http_status") or 403),
        error_code=str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
    )


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    actor_id = str(getattr(actor, "id", "") or "")
    if not actor_id:
        return {
            "ok": False, "http_status": 401,
            "error_code": "UNAUTHENTICATED",
            "message": "Authentication required",
        }
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(User).filter(User.id == actor_id).first()
            if row is None:
                return {
                    "ok": False, "http_status": 401,
                    "error_code": "UNAUTHENTICATED",
                    "message": "Authentication required",
                }
            if not bool(row.is_active) or str(row.status or "") != "active":
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": (
                        "This account is not active; refresh and sign in "
                        "again"),
                }
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "is_active": bool(row.is_active),
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_tenant_id": row.tenant_id,
                "workspace_id": str(resolve_workspace_id(row)),
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "agent-marketplace authority read failed: actor=%s "
            "error_class=%s", actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == value


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    result = db.execute(
        update(User)
        .where(
            User.id == actor["id"],
            User.is_active.is_(True),
            User.status == actor["status"],
            User.role == actor["role"],
            _exact(User.tenant_id, actor["raw_tenant_id"]),
        )
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


def _load_agent(db: Session, agent_id: str) -> Optional[AgentRegistry]:
    with _fresh_session(db) as fresh:
        return fresh.query(AgentRegistry).filter(
            AgentRegistry.id == str(agent_id)).populate_existing().first()


def _agent_state(agent: AgentRegistry) -> Dict[str, Any]:
    return {
        "id": str(agent.id),
        "tenant_id": None if agent.tenant_id is None else str(agent.tenant_id),
        "user_id": None if agent.user_id is None else str(agent.user_id),
        "workspace_id": (
            None if agent.workspace_id is None
            else str(agent.workspace_id)),
        "name": str(agent.name or ""),
        "description": (
            None if agent.description is None else str(agent.description)),
        "category": str(agent.category or ""),
        "specialty": (
            None if agent.specialty is None else str(agent.specialty)),
        "status": str(agent.status or ""),
        "configuration": dict(agent.configuration or {}),
    }


def _agent_digest(agent: AgentRegistry) -> str:
    return _fingerprint("agent-source", _canonical(_agent_state(agent)))


def _agent_predicates(agent: AgentRegistry):
    return [
        AgentRegistry.id == str(agent.id),
        _exact(AgentRegistry.tenant_id, agent.tenant_id),
        _exact(AgentRegistry.user_id, agent.user_id),
        _exact(AgentRegistry.workspace_id, agent.workspace_id),
        AgentRegistry.name == str(agent.name or ""),
        _exact(AgentRegistry.description, agent.description),
        AgentRegistry.category == str(agent.category or ""),
        _exact(AgentRegistry.specialty, agent.specialty),
        AgentRegistry.status == str(agent.status or ""),
        AgentRegistry.configuration == dict(agent.configuration or {}),
    ]


def _claim_agent(db: Session, agent: AgentRegistry) -> bool:
    result = db.execute(
        update(AgentRegistry)
        .where(*_agent_predicates(agent))
        .values(updated_at=AgentRegistry.updated_at)
    )
    return result.rowcount == 1


def _template_state(template: AgentTemplate) -> Dict[str, Any]:
    return {
        "id": str(template.id),
        "tenant_id": (
            None if template.tenant_id is None else str(template.tenant_id)),
        "author_id": (
            None if template.author_id is None else str(template.author_id)),
        "name": str(template.name or ""),
        "description": (
            None if template.description is None
            else str(template.description)),
        "category": (
            None if template.category is None else str(template.category)),
        "version": str(template.version or ""),
        "price": float(template.price or 0.0),
        "configuration": dict(template.configuration or {}),
        "capabilities": list(template.capabilities or []),
        "canvas_ui_schemas": list(template.canvas_ui_schemas or []),
        "anonymized_memory_bundle": dict(
            template.anonymized_memory_bundle or {}),
        "tunable_keys": list(template.tunable_keys or []),
        "permission_profile": dict(template.permission_profile or {}),
        "verified_record": dict(template.verified_record or {}),
        "is_public": bool(template.is_public),
        "is_approved": bool(template.is_approved),
        "is_active": bool(template.is_active),
    }


def _template_digest(template: AgentTemplate) -> str:
    return _fingerprint("agent-listing", _canonical(_template_state(template)))


def _load_template(
    db: Session, template_id: str,
) -> Optional[AgentTemplate]:
    with _fresh_session(db) as fresh:
        return fresh.query(AgentTemplate).filter(
            AgentTemplate.id == str(template_id)).populate_existing().first()


def _template_in_session(
    db: Session, template_id: str,
) -> Optional[AgentTemplate]:
    """Read the flushed listing from the writer's own transaction."""
    return db.query(AgentTemplate).filter(
        AgentTemplate.id == str(template_id)).populate_existing().first()


def _request_digest(
    agent_id: str, price: float, description: Optional[str],
) -> str:
    return _fingerprint(
        "agent-marketplace-request", str(agent_id), float(price or 0.0),
        str(description or ""))


def _audit_expected(
    *, operation_id: str, source_agent_id: str, template_id: str,
    prior_digest: str, result_digest: str, request_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_PUBLISH,
        "event_type": AuditEventType.CREATE.value,
        "target_id": str(template_id),
        "source_agent_id": str(source_agent_id),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "request_digest": str(request_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"agent_template:{template_id}",
    }


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any],
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "target_id": expected["target_id"],
        "source_agent_id": expected["source_agent_id"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "request_digest": expected["request_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=actor["workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description="Agent marketplace publication recorded",
        metadata_json=json.dumps(metadata, sort_keys=True),
        success=True,
    )


def _verify_audit(db: Session, expected: Dict[str, Any]) -> Dict[str, Any]:
    audit_id = expected["operation_id"]
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == audit_id).first()
            if row is None:
                return {"status": "unavailable", "audit_id": audit_id}
            if str(row.event_type or "") != expected["event_type"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.action or "") != expected["action"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.user_id or "") != expected["actor_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.tenant_id or "") != expected["tenant_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.resource or "") != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            if row.success is not True:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.security_level or "") != SecurityLevel.HIGH.value:
                return {"status": "refuted", "audit_id": audit_id}
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}
            string_fields = (
                "schema", "operation_id", "action", "event_type",
                "target_id", "source_agent_id", "prior_digest",
                "result_digest", "request_digest", "actor_id",
                "actor_role", "tenant_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "agent-marketplace audit read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _expected_from_metadata(
    metadata: Dict[str, Any], *, operation_id: str,
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": metadata.get("schema"),
        "action": metadata.get("action"),
        "event_type": metadata.get("event_type"),
        "target_id": metadata.get("target_id"),
        "source_agent_id": metadata.get("source_agent_id"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "request_digest": metadata.get("request_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"agent_template:{metadata.get('target_id')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, authority: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == str(operation_id)).first()
            if row is None:
                return None
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                metadata = None
            if not isinstance(metadata, dict):
                return _committed_unverified(
                    operation_id, {"status": "unavailable"},
                    target_id=str(expected.get("target_id") or ""))
            if (
                metadata.get("schema") != expected["schema"]
                or metadata.get("action") != expected["action"]
                or metadata.get("event_type") != expected["event_type"]
                or metadata.get("source_agent_id")
                != expected["source_agent_id"]
                or metadata.get("request_digest")
                != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
                or metadata.get("actor_role") != authority["role"]
                or metadata.get("tenant_id") != authority["tenant_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different decision or "
                    "changed authority",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            template = _load_template(db, audit_expected["target_id"])
            target_ok = (
                template is not None
                and _template_digest(template)
                == audit_expected["result_digest"]
            )
            data = {
                "success": True,
                "template_id": audit_expected["target_id"],
                "verified_record": (
                    dict(template.verified_record or {})
                    if template is not None else {}),
            }
            if audit_state["status"] == "verified" and not target_ok:
                audit_state = {
                    "status": "refuted",
                    "audit_id": audit_expected["operation_id"],
                }
            if audit_state["status"] == "verified" and target_ok:
                return {
                    "status": "already_applied",
                    "data": _with_receipt(
                        data, operation_id=operation_id,
                        audit_id=audit_expected["operation_id"],
                        verification_status="already_applied",
                        replay="do_not_repeat"),
                    "message": "This agent listing was already published.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "agent-marketplace replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool], success_data: Dict[str, Any],
    authority: Dict[str, Any],
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected, authority=authority)
        if replay is not None:
            return replay
        return _not_applied(
            "The agent listing was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "agent-marketplace decision outcome unknown: operation_id=%s "
            "target=%s error_class=%s", operation_id, target_id,
            type(exc).__name__)
        return _effect_unknown(operation_id, target_id)

    audit_state = _verify_audit(db, expected)
    try:
        target_ok = bool(target_check())
    except Exception:  # noqa: BLE001 — unreadable is not verified
        target_ok = False
    if audit_state["status"] == "verified" and not target_ok:
        audit_state = {"status": "refuted", "audit_id": operation_id}
    if audit_state["status"] == "verified" and target_ok:
        return {
            "status": "verified",
            "data": _with_receipt(
                success_data, operation_id=operation_id,
                audit_id=operation_id),
            "message": "Agent listing committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


def publish_agent_listing(
    db: Session, *, actor: Any, agent_id: str, price: float = 0.0,
    description: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    try:
        operation_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    agent = _load_agent(db, agent_id)
    if agent is None:
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    is_admin = role_level(authority["role"]) >= role_level(UserRole.ADMIN)
    if not is_admin and str(agent.user_id or "") != authority["id"]:
        return _refused(
            "Only the agent's owner (or an admin) can publish it for sale",
            http_status=403, error_code="AUTHORITY_REQUIRED")

    request_digest = _request_digest(agent_id, price, description)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_PUBLISH,
        "event_type": AuditEventType.CREATE.value,
        "source_agent_id": str(agent.id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(db, operation_id, expected_base, authority=authority)
    if replay is not None:
        return replay

    prior_digest = _agent_digest(agent)
    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "publisher authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    if not _claim_agent(db, agent):
        db.rollback()
        return _conflict(
            "source agent changed; refresh and retry", code="STALE_SOURCE")

    from core.agent_marketplace_service import AgentMarketplaceService

    service = AgentMarketplaceService(db)
    packaged = service.package_agent_for_sale(
        agent_id,
        price=price,
        description=description,
        author_id=authority["id"],
        commit=False,
        agent=agent,
    )
    if not packaged.get("success"):
        db.rollback()
        message = str(packaged.get("error") or "publication refused")
        if "not found" in message.lower():
            return _refused(message, http_status=404, error_code="NOT_FOUND")
        return _conflict(message, code="PACKAGE_REFUSED")

    template_id = str(packaged.get("template_id") or "")
    template = _template_in_session(db, template_id)
    if template is None:
        db.rollback()
        return _not_applied(
            "The agent listing could not be read after packaging; no effect "
            "was committed")
    result_digest = _template_digest(template)
    expected = _audit_expected(
        operation_id=operation_id, source_agent_id=str(agent.id),
        template_id=template_id, prior_digest=prior_digest,
        result_digest=result_digest, request_digest=request_digest,
        actor=authority)

    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_template(db, template_id)) is not None
            and _template_digest(now) == result_digest),
        success_data={
            "success": True,
            "template_id": template_id,
            "verified_record": dict(template.verified_record or {}),
        },
        authority=authority)
