"""Verified deletion of a Skill Builder package directory.

``POST /api/admin/skills/`` writes a tenant package directory. Before WA-069
there was no way to delete it: ``DELETE /api/skills/{skill_id}`` only deletes
``SkillExecution`` rows whose ``skill_source`` is ``community``, so an
editor-created package was unreachable and stayed consumable by
``agent_evolution_loop`` / ``evolution_engine`` forever.

This service adds the lifecycle's missing half with the repo's durable
operation pattern (one ``AuditLog`` receipt keyed by ``operation_id``, exact
request/target digests, replay) plus filesystem-specific coherence:

* **Quarantine before purge.** The package is renamed with one atomic
  ``os.replace`` to ``{tenant}/.skill-trash/{name}`` — outside ``skills/`` —
  before any recursive delete. A crash mid-``rmtree`` therefore cannot leave a
  half-deleted package that consumers still load, and the finished rename is
  observable by a retry.
* **Two-phase receipt.** The ``AuditLog`` row is committed as ``pending``
  *before* the filesystem effect and finalized after it. A retry with the same
  ``operation_id`` resumes an interrupted operation instead of reporting a
  false ``404`` (effect applied, receipt lost) or repeating a completed one.
* **No atomicity claim across stores.** A ``pending`` receipt with a completed
  effect is finalized on replay; a known partial (source retired, trash purge
  refused) is reported as ``committed_unverified`` with
  ``replay=do_not_repeat``. Nothing here pretends the directory and the row
  share a transaction.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import (
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import role_level
from core.skill_builder_service import (
    SkillBuilderService,
    SkillPathError,
    normalize_skill_name,
)

logger = logging.getLogger(__name__)

SKILL_PACKAGE_DELETE_SCHEMA = "atom-skill-package-delete-1"
_OPERATION_PREFIX = "skill-package"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION = "skill_package_deleted"
_RESOURCE_PREFIX = "skill-package:"
_MIN_ROLE = UserRole.WORKSPACE_ADMIN
_RESUMABLE_OUTCOMES = ("pending", "not_applied")


# ---------------------------------------------------------------------------
# Safe envelopes (mirrors core.document_delete_service)
# ---------------------------------------------------------------------------

def _fingerprint(*parts: Any) -> str:
    message = "|".join(
        str(part if part is not None else "") for part in parts)
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    prefix = f"{_OPERATION_PREFIX}:delete:"
    candidate = supplied or f"{prefix}{uuid.uuid4().hex}"
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


def _not_applied(message: str) -> Dict[str, Any]:
    return {
        "status": "not_applied",
        "error": message,
        "error_code": "SKILL_PACKAGE_DELETE_NOT_APPLIED",
        "http_status": 409,
        "verification": {
            "status": "refused",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
    }


def _conflict(
    message: str, *, code: str = "OPERATION_CONFLICT",
) -> Dict[str, Any]:
    return {
        "status": "conflict",
        "error": message,
        "error_code": code,
        "http_status": 409,
        "verification": {"status": "refuted", "effect": "none"},
    }


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
    effect: str, data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    verification_status: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": data,
        "message": message or (
            "The skill package deletion committed but its complete effect "
            "could not be verified. Reconcile the original operation; do not "
            "repeat it."),
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_id": target_id,
        "verification": {
            "status": (
                verification_status
                or audit_state.get("status", "unavailable")),
            "audit_status": audit_state.get("status", "unavailable"),
            "effect": effect,
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _effect_unknown(
    operation_id: str, target_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": data,
        "message": (
            "The skill package deletion may have committed, but confirmation "
            "was lost. Reconcile the original operation; do not repeat it "
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


def _no_change(
    operation_id: str, *, target_id: str, data: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    return {
        "status": "no_change",
        "data": data,
        "message": message,
        "operation_id": operation_id,
        "audit_id": None,
        "target_id": target_id,
        "verification": {"status": "no_change", "effect": "none"},
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


# ---------------------------------------------------------------------------
# Sessions / identity
# ---------------------------------------------------------------------------

def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message")
            or "workspace_admin authority is required"),
        http_status=int(actor.get("http_status") or 403),
        error_code=str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
    )


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    """Resolve the authoritative User row before any effect.

    The request-entry ``User`` is a snapshot. A concurrent deactivation,
    demotion or tenant reassignment must not let a package be deleted under
    stale authority, and the tenant the deletion is scoped to must come from
    the stored row — never from the request body or path.
    """
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
            if role_level(row.role) < role_level(_MIN_ROLE):
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "AUTHORITY_REQUIRED",
                    "message": (
                        "workspace_admin+ authority is required to delete a "
                        "skill package"),
                }
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "is_active": bool(row.is_active),
                "tenant_id": str(resolve_tenant_id(row)),
                "workspace_id": str(resolve_workspace_id(row)),
                "raw_tenant_id": row.tenant_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "skill-package authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _exact(column, value: Any):
    if value is None:
        return column.is_(None)
    return column == value


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    """Bind the frozen principal in the intent transaction."""
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


def _expected(
    *, operation_id: str, actor: Dict[str, Any], package: str,
) -> Dict[str, Any]:
    tenant_id = actor["tenant_id"]
    workspace_id = actor["workspace_id"]
    return {
        "operation_id": operation_id,
        "schema": SKILL_PACKAGE_DELETE_SCHEMA,
        "action": _ACTION,
        "event_type": AuditEventType.DELETE.value,
        "actor_id": actor["id"],
        "actor_email": actor["email"],
        "actor_role": actor["role"],
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "package": package,
        "target_digest": _fingerprint(
            "skill-package-target", tenant_id, package),
        "request_digest": _fingerprint(
            "skill-package-delete-request", tenant_id, package),
        "resource": f"{_RESOURCE_PREFIX}{tenant_id}:{package}",
    }


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------

def _data(
    *, package: str, outcome: str, pre_files: int,
    package_effect: str, trash_effect: str,
) -> Dict[str, Any]:
    return {
        "skill_id": package,
        "name": package,
        "deleted": package_effect in ("retired", "absent"),
        "outcome": outcome,
        "effects": {
            "package": package_effect,
            "quarantine": trash_effect,
            "pre_files": int(pre_files),
        },
    }


def _audit_metadata(
    expected: Dict[str, Any], *, outcome: str, pre_files: int,
    package_effect: str, trash_effect: str,
) -> Dict[str, Any]:
    return {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "actor_id": expected["actor_id"],
        "actor_email": expected["actor_email"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
        "workspace_id": expected["workspace_id"],
        "package": expected["package"],
        "target_digest": expected["target_digest"],
        "request_digest": expected["request_digest"],
        "outcome": outcome,
        "pre_files": int(pre_files),
        "package_effect": package_effect,
        "quarantine_effect": trash_effect,
    }


def _apply_receipt(
    row: AuditLog, expected: Dict[str, Any], *, outcome: str,
    pre_files: int, package_effect: str, trash_effect: str,
) -> None:
    row.event_type = expected["event_type"]
    row.security_level = SecurityLevel.HIGH.value
    row.threat_level = "none"
    row.user_id = expected["actor_id"] or None
    row.user_email = expected["actor_email"] or None
    row.tenant_id = expected["tenant_id"] or None
    row.workspace_id = expected["workspace_id"] or None
    row.resource = expected["resource"]
    row.action = expected["action"]
    row.description = f"Skill package deletion ({outcome})"
    row.metadata_json = json.dumps(
        _audit_metadata(
            expected, outcome=outcome, pre_files=pre_files,
            package_effect=package_effect, trash_effect=trash_effect),
        sort_keys=True)
    row.success = outcome == "verified"
    row.error_message = None if row.success else f"outcome={outcome}"


def _verify_audit(
    db: Session, expected: Dict[str, Any], outcome: str,
) -> Dict[str, Any]:
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
            if str(row.workspace_id or "") != expected["workspace_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.resource or "") != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            if bool(row.success) != (outcome == "verified"):
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.security_level or "") != SecurityLevel.HIGH.value:
                return {"status": "refuted", "audit_id": audit_id}
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}
            for key in (
                "schema", "operation_id", "action", "event_type",
                "actor_id", "tenant_id", "workspace_id", "package",
                "target_digest", "request_digest",
            ):
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if metadata.get("outcome") != outcome:
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(metadata.get("pre_files"), int):
                return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "skill-package receipt read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _prior_receipt(db: Session, expected: Dict[str, Any]) -> bool:
    """A verified earlier receipt for the same tenant package, if any."""
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.action == _ACTION,
                AuditLog.resource == expected["resource"],
            ).first()
            if row is None:
                return False
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return False
            return (
                isinstance(metadata, dict)
                and metadata.get("outcome") == "verified"
                and bool(row.success)
            )
    except Exception as exc:  # noqa: BLE001 — absence of proof means 404
        logger.warning(
            "skill-package prior receipt lookup failed: error_class=%s",
            type(exc).__name__)
        return False


# ---------------------------------------------------------------------------
# Filesystem effect
# ---------------------------------------------------------------------------

def _retire(source: Any, trash: Any) -> str:
    """Atomically move the package out of the consumable tree."""
    try:
        trash.parent.mkdir(parents=True, exist_ok=True)
        if not trash.resolve().is_relative_to(trash.parent.resolve()):
            return "unsafe"
        os.replace(source, trash)
        return "retired"
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        logger.warning(
            "skill-package quarantine rename failed: error_class=%s",
            type(exc).__name__)
        return "failed"


def _purge(trash: Any) -> str:
    try:
        if trash.is_symlink():
            return "unsafe"
        if not trash.exists():
            return "absent"
        shutil.rmtree(trash)
        return "deleted"
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        logger.warning(
            "skill-package quarantine purge failed: error_class=%s",
            type(exc).__name__)
        return "delete_failed"


def _inspect(builder: SkillBuilderService, expected: Dict[str, Any]) -> Dict[str, Any]:
    return builder.skill_package_state(
        expected["tenant_id"], expected["package"])


# ---------------------------------------------------------------------------
# Replay / finalize
# ---------------------------------------------------------------------------

def _replay(
    db: Session, expected: Dict[str, Any], builder: SkillBuilderService,
) -> Optional[Dict[str, Any]]:
    """Reconcile an existing receipt for this ``operation_id``.

    Returns a terminal envelope, a resumable marker (``_resume``) or ``None``
    when the operation id is unused.
    """
    operation_id = expected["operation_id"]
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == operation_id).first()
            if row is None:
                return None
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                metadata = None
            if not isinstance(metadata, dict):
                return _committed_unverified(
                    operation_id,
                    {"status": "unavailable", "audit_id": None},
                    target_id=expected["target_digest"], effect="unknown")
            for key in (
                "schema", "action", "event_type", "tenant_id",
                "workspace_id", "package", "target_digest",
                "request_digest", "actor_id",
            ):
                if metadata.get(key) != expected[key]:
                    return _conflict(
                        "operation_id is bound to a different skill-package "
                        "deletion request")
            outcome = str(metadata.get("outcome") or "")
            package_effect = str(metadata.get("package_effect") or "")
            trash_effect = str(metadata.get("quarantine_effect") or "")
            pre_files = int(metadata.get("pre_files") or 0)
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "skill-package replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable", "audit_id": None},
            target_id=expected["target_digest"], effect="unknown")

    try:
        state = _inspect(builder, expected)
    except SkillPathError:
        return _committed_unverified(
            operation_id, {"status": "unavailable", "audit_id": None},
            target_id=expected["target_digest"], effect="unknown")

    if outcome in _RESUMABLE_OUTCOMES:
        return {
            "_resume": True,
            "_row": row,
            "_pre_files": pre_files,
            "_package_effect": package_effect,
            "_trash_effect": trash_effect,
            "_state": state,
        }

    audit_state = _verify_audit(db, expected, outcome)
    source_absent = state["package_state"] == "absent"
    trash_absent = state["trash_state"] == "absent"
    if outcome == "verified" and audit_state["status"] == "verified":
        if source_absent and trash_absent:
            return {
                "status": "already_applied",
                "data": _with_receipt(
                    _data(
                        package=expected["package"], outcome="verified",
                        pre_files=pre_files,
                        package_effect=package_effect or "retired",
                        trash_effect=trash_effect or "deleted"),
                    operation_id=operation_id,
                    audit_id=operation_id,
                    verification_status="already_applied",
                    replay="do_not_repeat"),
                "message": (
                    "This skill package deletion was already applied; the "
                    "original receipt was returned without another deletion."),
                "operation_id": operation_id,
                "audit_id": operation_id,
                "target_id": expected["target_digest"],
            }
        portal = "package" if not source_absent else "quarantine"
        return _committed_unverified(
            operation_id, audit_state,
            target_id=expected["target_digest"],
            effect="partial" if source_absent else "unknown",
            data=_data(
                package=expected["package"], outcome="committed_unverified",
                pre_files=pre_files, package_effect=package_effect,
                trash_effect=trash_effect),
            message=(
                f"The receipt is verified but the {portal} still exists "
                "on disk; reconcile without repeating the deletion."))

    # Anything else already carried a do_not_repeat instruction.
    effect = (
        "committed" if source_absent and trash_absent
        else "partial" if source_absent else "unknown")
    return _committed_unverified(
        operation_id, audit_state,
        target_id=expected["target_digest"], effect=effect,
        data=_data(
            package=expected["package"], outcome=outcome or "unknown",
            pre_files=pre_files, package_effect=package_effect,
            trash_effect=trash_effect),
        verification_status=(
            "committed_unverified" if effect == "partial"
            else audit_state.get("status", "unavailable")))


def _finalize(
    db: Session, expected: Dict[str, Any], row: AuditLog, *,
    outcome: str, pre_files: int, package_effect: str, trash_effect: str,
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    try:
        # ``row`` may be *detached*: a resumed operation loads the pending
        # receipt through a short-lived session, while this session still
        # holds the instance committed by the interrupted attempt. Re-attach
        # by primary key so the receipt is updated in place instead of
        # raising "another instance with key ... is already present".
        target = db.get(AuditLog, row.id) if row.id else None
        if target is None:
            target = row
        _apply_receipt(
            target, expected, outcome=outcome, pre_files=pre_files,
            package_effect=package_effect, trash_effect=trash_effect)
        db.add(target)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "skill-package receipt finalize failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _effect_unknown(
            operation_id, expected["target_digest"],
            data=_data(
                package=expected["package"], outcome="effect_unknown",
                pre_files=pre_files, package_effect=package_effect,
                trash_effect=trash_effect))

    audit_state = _verify_audit(db, expected, outcome)
    data = _data(
        package=expected["package"], outcome=outcome,
        pre_files=pre_files, package_effect=package_effect,
        trash_effect=trash_effect)
    if outcome == "verified" and audit_state["status"] == "verified":
        return {
            "status": "verified",
            "data": _with_receipt(
                data, operation_id=operation_id, audit_id=operation_id),
            "message": (
                f"Skill package '{expected['package']}' deletion verified: "
                "the published directory and its quarantine are gone."),
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": expected["target_digest"],
        }
    if outcome == "not_applied":
        return {
            "status": "not_applied",
            "data": data,
            "error": (
                "The skill package could not be moved out of the skills "
                "directory; no deletion was applied"),
            "error_code": "SKILL_PACKAGE_DELETE_NOT_APPLIED",
            "http_status": 409,
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": expected["target_digest"],
            "verification": {
                "status": "refused",
                "effect": "none",
                "replay": "safe_same_operation",
                "audit_status": audit_state["status"],
                "audit_id": operation_id,
            },
        }
    return _committed_unverified(
        operation_id, audit_state,
        target_id=expected["target_digest"],
        effect="partial" if package_effect in ("retired", "absent")
        else "unknown",
        data=data,
        verification_status="committed_unverified",
        message=(
            "The skill package is no longer consumable, but its quarantine "
            "could not be removed. Reconcile without repeating the deletion; "
            "a later delete of the same package name finishes the cleanup."))


# ---------------------------------------------------------------------------
# Public operation
# ---------------------------------------------------------------------------

def delete_skill_package_verified(
    db: Session, *, actor: Any, name: str,
    operation_id: Optional[str] = None,
    builder: Optional[SkillBuilderService] = None,
) -> Dict[str, Any]:
    """Delete one tenant package from the skills root with a receipt.

    Outcomes: ``verified``, ``already_applied`` (same-operation replay),
    ``no_change`` (absent, covered by an earlier verified receipt),
    ``committed_unverified`` (known partial), ``effect_unknown``
    (confirmation lost), ``not_applied`` (rename refused), ``conflict``
    (operation id reused for different material) and ``refused``
    (unknown/foreign/unsafe/malformed).
    """
    raw_name = str(name or "").strip()
    if not raw_name:
        return _refused("skill name must be non-empty", field="skill_id")
    package = normalize_skill_name(raw_name)
    if not package:
        return _refused(
            "skill name has no addressable characters", field="skill_id")

    snapshot = _resolve_actor(db, actor)
    if not snapshot.get("ok"):
        return _actor_refusal(snapshot)
    try:
        operation_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    builder = builder or SkillBuilderService()
    expected = _expected(
        operation_id=operation_id, actor=snapshot, package=package)

    replay = _replay(db, expected, builder)
    if replay is not None and not replay.get("_resume"):
        return replay
    intent_row: Optional[AuditLog] = replay.get("_row") if replay else None
    pre_files = int(replay.get("_pre_files") or 0) if replay else 0

    try:
        state = _inspect(builder, expected)
    except SkillPathError as exc:
        return _refused(
            f"Refusing unsafe skill package path: {exc}",
            http_status=400, error_code="UNSAFE_SKILL_PATH")
    if state["package_state"] == "unsafe" or state["trash_state"] == "unsafe":
        return _refused(
            "Refusing to delete a skill path that is a symlink or a "
            "non-directory file",
            http_status=409, error_code="UNSAFE_SKILL_PATH")
    if state["package_state"] == "present" and state["trash_state"] == "absent":
        pre_files = state["file_count"]

    # Nothing published and nothing quarantined.
    if state["package_state"] == "absent" and state["trash_state"] == "absent":
        if intent_row is not None:
            # Interrupted between the filesystem effect and the finalize.
            return _finalize(
                db, expected, intent_row, outcome="verified",
                pre_files=pre_files,
                package_effect="retired", trash_effect="deleted")
        if _prior_receipt(db, expected):
            return _no_change(
                operation_id, target_id=expected["target_digest"],
                data=_data(
                    package=package, outcome="no_change",
                    pre_files=0, package_effect="absent",
                    trash_effect="absent"),
                message=(
                    f"Skill package '{package}' is already absent; an earlier "
                    "deletion receipt was found and no new receipt was "
                    "created."))
        return _refused(
            f"Skill package not found: {package}",
            http_status=404, error_code="NOT_FOUND")

    # From here the operation intends an effect. Commit the intent first so an
    # interrupt is recoverable by the same operation id.
    if intent_row is None:
        row = AuditLog(
            id=operation_id,
            event_type=expected["event_type"],
            security_level=SecurityLevel.HIGH.value,
            threat_level="none",
            user_id=expected["actor_id"] or None,
            user_email=expected["actor_email"] or None,
            tenant_id=expected["tenant_id"] or None,
            workspace_id=expected["workspace_id"] or None,
            resource=expected["resource"],
            action=expected["action"],
            description="Skill package deletion (pending)",
            metadata_json=json.dumps(
                _audit_metadata(
                    expected, outcome="pending", pre_files=pre_files,
                    package_effect="pending", trash_effect="pending"),
                sort_keys=True),
            success=False,
            error_message="outcome=pending",
        )
        try:
            if not _claim_actor(db, snapshot):
                db.rollback()
                return _conflict(
                    "deleting authority changed; refresh and retry",
                    code="AUTHORITY_CHANGED")
            db.add(row)
            db.commit()
        except IntegrityError:
            db.rollback()
            replay = _replay(db, expected, builder)
            if replay is not None and not replay.get("_resume"):
                return replay
            return _conflict(
                "operation_id was claimed concurrently; refresh and retry")
        except Exception as exc:  # noqa: BLE001 — no effect has happened yet
            db.rollback()
            logger.error(
                "skill-package intent commit failed: operation_id=%s "
                "error_class=%s", operation_id, type(exc).__name__)
            return _not_applied(
                "The skill package deletion could not be recorded; nothing "
                "was deleted")
        intent_row = row

    trash_effect = "absent"
    if state["trash_state"] == "present":
        # A stale quarantine is already logically deleted; clearing it before
        # the rename keeps the package name reusable.
        trash_effect = _purge(state["trash"])
        if trash_effect not in ("deleted", "absent"):
            return _finalize(
                db, expected, intent_row, outcome="not_applied",
                pre_files=pre_files, package_effect="present",
                trash_effect=trash_effect)

    package_effect = "absent"
    if state["package_state"] == "present":
        package_effect = _retire(state["package"], state["trash"])
        if package_effect not in ("retired", "absent"):
            return _finalize(
                db, expected, intent_row, outcome="not_applied",
                pre_files=pre_files, package_effect="present",
                trash_effect=trash_effect)
        if package_effect == "retired":
            trash_effect = _purge(state["trash"])

    try:
        after = _inspect(builder, expected)
        source_absent = after["package_state"] == "absent"
        trash_absent = after["trash_state"] == "absent"
    except SkillPathError:
        source_absent = False
        trash_absent = False

    if source_absent and trash_absent:
        outcome = "verified"
    elif source_absent:
        outcome = "committed_unverified"
    else:
        outcome = "not_applied"

    return _finalize(
        db, expected, intent_row, outcome=outcome, pre_files=pre_files,
        package_effect=package_effect, trash_effect=trash_effect)
