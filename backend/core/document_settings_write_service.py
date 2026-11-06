"""Verified workspace-scoped document-ingestion settings writes.

The route previously updated an in-memory settings object and made a best-effort
database persist with no exact CAS, audit receipt or replay protection. This
module binds the current principal and the exact prior `ingestion_settings` row
in guarded DML in the same transaction as one safe `AuditLog` receipt.

The existing `AutoDocumentIngestionService` cache is cleared/reloaded by the
route after a committed change; the database row is the authority.
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
    AuditEventType,
    AuditLog,
    IngestionSettings,
    SecurityLevel,
    User,
)
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-document-settings-decision-1"
_OPERATION_PREFIX = "document-settings"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_UPDATE = "document_settings_updated"

SETTINGS_FIELDS = (
    "enabled",
    "auto_sync_new_files",
    "file_types",
    "sync_folders",
    "exclude_folders",
    "max_file_size_mb",
    "sync_frequency_minutes",
)
DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "auto_sync_new_files": True,
    "file_types": ["pdf", "docx", "txt", "md"],
    "sync_folders": [],
    "exclude_folders": [],
    "max_file_size_mb": 50,
    "sync_frequency_minutes": 60,
}


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
    candidate = supplied or f"{_OPERATION_PREFIX}:{uuid.uuid4().hex}"
    prefix = f"{_OPERATION_PREFIX}:"
    if not candidate.startswith(prefix):
        candidate = f"{prefix}{candidate}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise ValueError("operation_id is malformed")
    return candidate


def _refused(
    message: str, *, http_status: int = 422,
    error_code: str = "VALIDATION_ERROR", field: Optional[str] = None,
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
        "error_code": "DOCUMENT_SETTINGS_TRANSACTION_ROLLED_BACK",
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
            "The ingestion-settings update committed but its audit/target "
            "readback did not verify. Reconcile the original operation."),
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
            "The ingestion-settings update may have committed, but "
            "confirmation was lost. Reconcile the original operation; do not "
            "repeat it blindly."),
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


def _no_change(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    result = dict(data)
    result["verification"] = {"status": "no_change", "effect": "none"}
    return {"status": "no_change", "data": result, "message": message}


def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "Authentication required"),
        http_status=int(actor.get("http_status") or 401),
        error_code=str(actor.get("error_code") or "UNAUTHENTICATED"),
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
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_tenant_id": row.tenant_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "document-settings authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
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
            _exact(User.tenant_id, actor["raw_tenant_id"]),
        )
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


def _load_settings(
    db: Session, workspace_id: str, integration_id: str,
) -> Optional[IngestionSettings]:
    with _fresh_session(db) as fresh:
        return fresh.query(IngestionSettings).filter(
            IngestionSettings.workspace_id == str(workspace_id),
            IngestionSettings.integration_id == str(integration_id),
        ).populate_existing().first()


def _normalize_changes(changes: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key in SETTINGS_FIELDS:
        value = changes.get(key)
        if value is None:
            continue
        if key in ("enabled", "auto_sync_new_files"):
            normalized[key] = bool(value)
        elif key in ("file_types", "sync_folders", "exclude_folders"):
            normalized[key] = list(value or [])
        else:
            normalized[key] = int(value)
    return normalized


def _settings_state(
    row: Optional[IngestionSettings], *, changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if row is None:
        state = {
            key: (list(value) if isinstance(value, list) else value)
            for key, value in DEFAULTS.items()
        }
    else:
        state = {
            key: (
                list(getattr(row, key) or [])
                if key in ("file_types", "sync_folders", "exclude_folders")
                else getattr(row, key)
            )
            for key in SETTINGS_FIELDS
        }
    if changes:
        state.update(changes)
    return state


def _state_digest(state: Dict[str, Any]) -> str:
    return _fingerprint("document-settings-state", _canonical(state))


def _request_digest(
    workspace_id: str, integration_id: str, changes: Dict[str, Any],
) -> str:
    return _fingerprint(
        "document-settings-request", str(workspace_id),
        str(integration_id), _canonical(changes))


def _audit_expected(
    *, operation_id: str, workspace_id: str, integration_id: str,
    prior_digest: str, result_digest: str, request_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_UPDATE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(integration_id),
        "target_workspace_id": str(workspace_id),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "request_digest": str(request_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"ingestion_settings:{workspace_id}:{integration_id}",
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
        "target_workspace_id": expected["target_workspace_id"],
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
        workspace_id=expected["target_workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description="Document-ingestion settings updated",
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
            if str(row.workspace_id or "") != expected["target_workspace_id"]:
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
                "target_id", "target_workspace_id", "prior_digest",
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
            "document-settings audit read-back failed: operation_id=%s "
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
        "target_workspace_id": metadata.get("target_workspace_id"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "request_digest": metadata.get("request_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": (
            f"ingestion_settings:{metadata.get('target_workspace_id')}:"
            f"{metadata.get('target_id')}"),
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
                or metadata.get("target_id") != expected["target_id"]
                or metadata.get("target_workspace_id")
                != expected["target_workspace_id"]
                or metadata.get("request_digest")
                != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
                or metadata.get("actor_role") != authority["role"]
                or metadata.get("tenant_id") != authority["tenant_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different settings request",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            current = _load_settings(
                db, str(metadata.get("target_workspace_id") or ""),
                str(metadata.get("target_id") or ""))
            target_ok = (
                current is not None
                and _state_digest(_settings_state(current))
                == audit_expected["result_digest"]
            )
            data = (
                _settings_state(current) if current is not None
                else {"integration_id": audit_expected["target_id"]}
            )
            data["integration_id"] = audit_expected["target_id"]
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
                    "message": "These ingestion settings were already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "document-settings replay read failed: operation_id=%s "
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
        replay = _replay(
            db, operation_id, expected, authority=authority)
        if replay is not None:
            return replay
        return _not_applied(
            "The ingestion-settings update was rolled back; no effect was "
            "applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "document-settings update outcome unknown: operation_id=%s "
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
            "message": "Ingestion settings updated",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


def update_ingestion_settings(
    db: Session, *, actor: Any, workspace_id: str, integration_id: str,
    changes: Dict[str, Any], operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    integration_id = str(integration_id or "").strip()
    if not integration_id:
        return _refused(
            "integration_id must be non-empty", field="integration_id")
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    try:
        operation_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    normalized = _normalize_changes(changes or {})
    request_digest = _request_digest(
        workspace_id, integration_id, normalized)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_UPDATE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": integration_id,
        "target_workspace_id": str(workspace_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(db, operation_id, expected_base, authority=authority)
    if replay is not None:
        return replay

    current = _load_settings(db, workspace_id, integration_id)
    current_state = _settings_state(current)
    if not normalized:
        data = dict(current_state)
        data["integration_id"] = integration_id
        return _no_change(data, "No ingestion-settings changes requested")
    result_state = _settings_state(current, changes=normalized)
    if result_state == current_state:
        data = dict(result_state)
        data["integration_id"] = integration_id
        return _no_change(data, "Ingestion settings already match the request")

    prior_digest = _state_digest(current_state)
    result_digest = _state_digest(result_state)
    expected = dict(expected_base)
    expected["prior_digest"] = prior_digest
    expected["result_digest"] = result_digest
    expected["actor_role"] = authority["role"]
    expected["tenant_id"] = authority["tenant_id"]
    expected["resource"] = (
        f"ingestion_settings:{workspace_id}:{integration_id}")

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        if current is None:
            row_id = "ingestion:" + _fingerprint(
                "document-settings-row", workspace_id, integration_id)
            db.add(IngestionSettings(
                id=row_id,
                tenant_id=authority["tenant_id"],
                workspace_id=str(workspace_id),
                integration_id=integration_id,
                **result_state,
            ))
            db.flush()
        else:
            predicates = [
                IngestionSettings.id == str(current.id),
                IngestionSettings.workspace_id == str(workspace_id),
                IngestionSettings.integration_id == integration_id,
            ]
            for key in SETTINGS_FIELDS:
                predicates.append(_exact(getattr(IngestionSettings, key),
                                         current_state[key]))
            updated = db.execute(
                update(IngestionSettings).where(*predicates).values(
                    **normalized))
            if updated.rowcount != 1:
                db.rollback()
                return _conflict(
                    "ingestion settings changed; refresh and retry",
                    code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected, authority=authority)
        return replay or _conflict(
            "ingestion settings changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "document-settings update failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, integration_id,
            type(exc).__name__)
        return _not_applied(
            "The ingestion settings could not be updated; no effect was "
            "committed")

    data = dict(result_state)
    data["integration_id"] = integration_id
    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_settings(db, workspace_id, integration_id))
            is not None
            and _state_digest(_settings_state(now)) == result_digest),
        success_data=data,
        authority=authority)
