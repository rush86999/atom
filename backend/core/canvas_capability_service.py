"""Versioned canvas capability manifests and adapters.

A canvas TYPE is presentation. This module answers a different question:
which operations is THIS canvas actually allowed and able to perform right
now? The answer is the intersection of:

  declared operations (manifest)
  ∩ installed adapter capabilities (table adapter here)
  ∩ authenticated user/owner permission
  ∩ current resource support (bound dataset / teaching / artifact writer)

The adapters call the existing deterministic selection, aggregation and
structured-review implementations. They do not introduce a second review
engine, a second calculation engine, or client-supplied permissions.

Manifest storage: ``Canvas.content["capability_manifest"]`` (versioned by a
stable hash). Bound dataset: ``Canvas.content["dataset"]`` with a source hash
and monotonic revision. These are the canvas's existing authoritative row,
not CanvasContext.
"""
from __future__ import annotations

import csv
import copy
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import func, update

from core.models import Canvas, CanvasAudit

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
TABLE_OPERATIONS = {
    "read", "select", "calculate", "assess", "edit", "export", "bind",
}
_SUPPORTED_OPERATIONS = TABLE_OPERATIONS
_SUPPORTED_BASE_COMPONENTS = {"table"}
_MAX_BIND_BYTES = int(os.getenv("ATOM_CANVAS_BIND_MAX_BYTES", str(20 * 1024 * 1024)))
_MAX_ASSESS_SUBJECTS = int(os.getenv("ATOM_ASSESS_MAX_SUBJECTS", "50") or 50)

#: Server-controlled review policy for assessments.
#:
#: ``always`` (default) requires human review for EVERY assessment, whatever
#: the model reports about its own uncertainty. That is the correct default for
#: an unqualified configuration: a confident, wrong APPROVE reports no
#: uncertainty, and certification only proves the contract was satisfied, not
#: that the decision is correct.
#:
#: ``model_reported`` is an explicit opt-out for a configuration that has been
#: independently qualified; it restores the old behaviour (review only when
#: uncertified or the model reports unresolved requirements).
_REVIEW_POLICY_ALWAYS = "always"
#: ``scoped`` grants autonomy only to a configuration that is BOTH qualified in
#: the server-controlled registry AND allowed by the owner's autonomy policy
#: (mode x maturity x trust) for the ``canvas_assessment`` topic.
_REVIEW_POLICY_SCOPED = "scoped"
_REVIEW_POLICIES = {_REVIEW_POLICY_ALWAYS, _REVIEW_POLICY_SCOPED}
_ASSESSMENT_CAPABILITY = "canvas_assessment.model_judgment"
_ASSESSMENT_TOPIC = "canvas_assessment"

_QUALIFICATION_CACHE: Dict[str, Any] = {"signature": None, "registry": None}


def current_assessment_revision(canvas: Canvas) -> int:
    """Monotonic token for assessment-state writes (assess + approval)."""
    record = _canvas_content(canvas).get("assessment_review") or {}
    try:
        return int(record.get("assessment_revision") or 0)
    except (TypeError, ValueError):
        return 0


def _qualification_registry_path() -> Path:
    configured = os.getenv("ATOM_ASSESSMENT_QUALIFICATION_FILE")
    if configured:
        return Path(configured)
    return (Path(__file__).resolve().parents[1] / "config"
            / "assessment_qualification.json")


def load_assessment_qualification_registry() -> Dict[str, Any]:
    """Read the server-controlled registry, reloading when the file changes."""
    path = _qualification_registry_path()
    try:
        stat = path.stat()
    except OSError:
        return {"schema": None, "configurations": [], "path": str(path)}
    signature = (str(path), stat.st_mtime_ns, stat.st_size)
    if _QUALIFICATION_CACHE.get("signature") == signature:
        return _QUALIFICATION_CACHE["registry"]
    try:
        registry = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001 — fail closed on an unreadable file
        logger.warning("assessment qualification registry unreadable: %s", exc)
        registry = {"schema": None, "configurations": [], "error": str(exc)}
    registry.setdefault("configurations", [])
    registry["path"] = str(path)
    _QUALIFICATION_CACHE["signature"] = signature
    _QUALIFICATION_CACHE["registry"] = registry
    return registry


def assessment_serving_configuration(provider: Any) -> Dict[str, Any]:
    """The serving configuration an assessment actually ran against.

    Qualification is not a property of a model name: the same weights behind a
    different endpoint or budget are a different configuration.
    """
    if str(provider or "") == "ollama":
        base_url = (os.getenv("OLLAMA_BASE_URL")
                    or "http://localhost:11434/v1").rstrip("/")
        try:
            timeout = int(float(os.getenv("OLLAMA_REQUEST_TIMEOUT") or 600))
        except ValueError:
            timeout = 600
        return {"base_url": base_url, "request_timeout": str(timeout)}
    return {}


def assessment_qualification(
    provider: Any, model: Any, *,
    policy_text: Any = None,
    decision_options: Any = None,
    subject_field: Any = None,
    contract_version: Any = None,
    serving: Any = None,
) -> Dict[str, Any]:
    """Qualification state for one exact configuration and task scope.

    A qualified entry applies only to the contract version, serving
    configuration, policy text, decision vocabulary and subject field it was
    qualified against. A model name alone authorizes nothing.
    """
    registry = load_assessment_qualification_registry()
    wanted = (str(provider or ""), str(model or ""))
    for entry in registry.get("configurations") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("capability") != _ASSESSMENT_CAPABILITY:
            continue
        if (str(entry.get("provider") or ""),
                str(entry.get("model") or "")) != wanted:
            continue
        revoked = bool(entry.get("revoked"))
        base = {
            "status": entry.get("status"),
            "revoked": revoked,
            "configuration_id": entry.get("id"),
            "contract_version": entry.get("contract_version"),
            "evidence": entry.get("evidence"),
            "limitations": entry.get("limitations"),
            "registry": registry.get("path"),
        }
        if entry.get("status") != "qualified" or revoked:
            return {**base, "qualified": False, "scope_reasons": ["not_qualified"]}

        reasons: List[str] = []
        if str(entry.get("contract_version") or "") != str(contract_version or ""):
            reasons.append("contract_version_mismatch")
        scope = entry.get("scope") or {}
        if str(scope.get("task_policy") or "") != str(policy_text or ""):
            reasons.append("policy_out_of_scope")
        if [str(x) for x in scope.get("decision_options") or []] != [
                str(x) for x in (decision_options or [])]:
            reasons.append("decision_vocabulary_out_of_scope")
        if str(scope.get("subject_field") or "") != str(subject_field or ""):
            reasons.append("subject_field_out_of_scope")
        declared_serving = entry.get("serving")
        if not isinstance(declared_serving, dict) or not declared_serving:
            reasons.append("serving_configuration_undeclared")
        elif declared_serving != (serving or {}):
            reasons.append("serving_configuration_mismatch")
        return {
            **base,
            "qualified": not reasons,
            "scope_reasons": reasons,
            "scope": scope,
            "serving": declared_serving,
        }
    return {
        "qualified": False,
        "status": "unregistered",
        "revoked": False,
        "scope_reasons": ["unregistered"],
        "registry": registry.get("path"),
    }


def assessment_review_policy() -> str:
    raw = (os.getenv("ATOM_ASSESSMENT_REVIEW_POLICY") or _REVIEW_POLICY_ALWAYS)
    value = raw.strip().lower()
    return value if value in _REVIEW_POLICIES else _REVIEW_POLICY_ALWAYS

# A connected catalog row names a provider. These are the token families the
# existing journey services already resolve; adding a provider here does not
# grant access, it only lets the binding ask the existing token store whether
# the authenticated user still has an active grant.
from core.integrations.token_store import SOURCE_PROVIDER_ALIASES as _CONNECTED_PROVIDER_ALIASES


class CapabilityError(Exception):
    """Typed operation refusal; the API maps this to a 4xx with a receipt."""

    def __init__(self, code: str, message: str, status_code: int = 400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def manifest_revision(manifest: Dict[str, Any]) -> str:
    return _sha256_json(manifest)[:16]


def policy_revision(manifest: Dict[str, Any]) -> str:
    policy = {
        "task_policy": manifest.get("task_policy") or "",
        "decision_options": manifest.get("decision_options") or [],
        # Applicability metadata changes what the policy governs, so it is
        # part of the effective revision. Existing manifests without it keep
        # their old hash.
        "teaching_context": manifest.get("teaching_context") or {},
    }
    return _sha256_json(policy)[:16]


def default_manifest() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "base_component": "table",
        "operations": ["read", "select", "calculate", "edit", "export", "bind"],
        "data_binding": {"subject_field": "", "resource_id": "", "source_version": ""},
        "editable_fields": [],
        "teaching_binding": {"agent_id": "", "scope_id": ""},
        "decision_options": [],
        "task_policy": "",
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def validate_manifest(manifest: Any) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise CapabilityError("invalid_manifest", "Manifest must be an object.")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CapabilityError(
            "unsupported_manifest_version",
            f"Manifest schema_version must be {SCHEMA_VERSION}.",
        )
    base = str(manifest.get("base_component") or "").strip().lower()
    if base not in _SUPPORTED_BASE_COMPONENTS:
        raise CapabilityError(
            "unsupported_adapter",
            f"No installed adapter for base_component '{base or 'missing'}'. "
            "This canvas cannot acquire read/write operations from its label.",
        )
    operations = manifest.get("operations")
    if not isinstance(operations, list) or not all(
        isinstance(item, str) for item in operations
    ):
        raise CapabilityError("invalid_manifest", "operations must be a string list.")
    unknown = sorted({op for op in operations if op not in _SUPPORTED_OPERATIONS})
    if unknown:
        raise CapabilityError(
            "unsupported_operation",
            f"Unsupported operation(s): {', '.join(unknown)}. Nothing was enabled.",
        )
    binding = manifest.get("data_binding") or {}
    if not isinstance(binding, dict):
        raise CapabilityError("invalid_manifest", "data_binding must be an object.")
    editable = manifest.get("editable_fields") or []
    if not isinstance(editable, list) or not all(isinstance(x, str) for x in editable):
        raise CapabilityError("invalid_manifest", "editable_fields must be a string list.")
    decisions = manifest.get("decision_options") or []
    if decisions and (
        not isinstance(decisions, list)
        or not all(isinstance(x, str) and x.strip() for x in decisions)
    ):
        raise CapabilityError("invalid_manifest", "decision_options must be non-empty strings.")
    outputs = manifest.get("outputs") or []
    if outputs and (not isinstance(outputs, list) or any(
        str(item).lower() not in {"xlsx", "csv"} for item in outputs
    )):
        raise CapabilityError("invalid_manifest", "outputs supports xlsx/csv.")
    required = manifest.get("required_approvals") or []
    if not isinstance(required, list):
        raise CapabilityError("invalid_manifest", "required_approvals must be a list.")
    clean = dict(manifest)
    clean.pop("manifest_revision", None)
    clean["base_component"] = base
    clean["operations"] = list(dict.fromkeys(operations))
    clean["data_binding"] = dict(binding)
    clean["editable_fields"] = list(dict.fromkeys(editable))
    clean["decision_options"] = [str(x).strip() for x in decisions]
    clean["task_policy"] = str(manifest.get("task_policy") or "").strip()
    clean["outputs"] = [str(x).lower() for x in outputs]
    clean["required_approvals"] = list(required)
    clean["manifest_revision"] = manifest_revision(clean)
    return clean


def sanitize_capability_copy(content: Any, new_canvas_id: str) -> Any:
    """Copy-on-fork: keep shape/operations, drop private teaching and bindings.

    A fork is an independent instance. It may carry the data shape the user
    deliberately copied, but not the source canvas's private teaching policy,
    employee binding, approval requirements or resource identity.
    """
    if not isinstance(content, dict) or not isinstance(
            content.get("capability_manifest"), dict):
        return content
    copied = dict(content)
    manifest = dict(copied["capability_manifest"])
    manifest["teaching_binding"] = {"agent_id": "", "scope_id": ""}
    manifest["task_policy"] = ""
    manifest["decision_options"] = []
    manifest["required_approvals"] = []
    manifest["data_binding"] = {
        "subject_field": (manifest.get("data_binding") or {}).get("subject_field", ""),
        "measure_field": (manifest.get("data_binding") or {}).get("measure_field", ""),
        "status_field": (manifest.get("data_binding") or {}).get("status_field", ""),
        "resource_id": f"canvas:{new_canvas_id}",
        "source_version": "",
    }
    manifest.pop("manifest_revision", None)
    manifest["manifest_revision"] = manifest_revision(manifest)
    copied["capability_manifest"] = manifest
    dataset = copied.get("dataset")
    if isinstance(dataset, dict):
        dataset = dict(dataset)
        source = dict(dataset.get("source") or {})
        dataset["source"] = {
            "resource_id": f"canvas:{new_canvas_id}",
            "file_name": "copied dataset",
            "source_version": hashlib.sha256(
                json.dumps(
                    [dataset.get("columns"), dataset.get("rows")],
                    default=str).encode()
            ).hexdigest()[:16],
        }
        copied["dataset"] = dataset
    copied.pop("capability_revision", None)
    return copied


def _canvas_content(canvas: Canvas) -> Dict[str, Any]:
    return dict(canvas.content or {}) if isinstance(canvas.content, dict) else {}


def get_manifest(canvas: Canvas) -> Dict[str, Any]:
    raw = _canvas_content(canvas).get("capability_manifest")
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def get_dataset(canvas: Canvas) -> Dict[str, Any]:
    raw = _canvas_content(canvas).get("dataset")
    return dict(raw) if isinstance(raw, dict) else {}


def current_revision(canvas: Canvas) -> int:
    try:
        return int(_canvas_content(canvas).get("capability_revision") or 0)
    except (TypeError, ValueError):
        return 0


def authorize_canvas(db, canvas: Canvas, user: Any) -> None:
    """Owner/author check plus workspace isolation (server-side, never a body
    field). Wrong workspace cannot read or mutate another workspace's canvas."""
    user_id = str(getattr(user, "id", "") or "")
    if not user_id:
        raise CapabilityError("unauthenticated", "Authentication required.", 401)
    from tools.canvas_crud_tool import _verify_canvas_owner

    if not _verify_canvas_owner(db, canvas.id, user_id):
        raise CapabilityError("forbidden", "Not the canvas owner.", 403)
    canvas_ws = str(getattr(canvas, "workspace_id", "") or "")
    user_ws = str(getattr(user, "workspace_id", "") or "")
    if canvas_ws and user_ws and canvas_ws != user_ws and str(canvas.created_by or "") != user_id:
        raise CapabilityError(
            "workspace_mismatch",
            "This canvas belongs to a different workspace.",
            403,
        )


def effective_operations(canvas: Canvas, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest = manifest if isinstance(manifest, dict) else get_manifest(canvas)
    declared = set(manifest.get("operations") or [])
    adapter = set(TABLE_OPERATIONS) if manifest.get("base_component") == "table" else set()
    dataset = get_dataset(canvas)
    columns = [str(c) for c in (dataset.get("columns") or [])]
    resource = {"read", "bind"}
    if columns and dataset.get("rows") is not None:
        resource |= {"select", "calculate"}
        editable = [c for c in (manifest.get("editable_fields") or []) if c in columns]
        if editable:
            resource.add("edit")
        if "xlsx" in (manifest.get("outputs") or []):
            resource.add("export")
    subject_field = str((manifest.get("data_binding") or {}).get("subject_field") or "")
    if (
        columns
        and subject_field in columns
        and manifest.get("decision_options")
        and str(manifest.get("task_policy") or "").strip()
    ):
        resource.add("assess")
    effective = declared & adapter & resource
    return {
        "declared": sorted(declared),
        "adapter": sorted(adapter),
        "resource": sorted(resource),
        "effective": sorted(effective),
        "manifest_revision": manifest.get("manifest_revision") or manifest_revision(manifest or {}),
    }


def _require_approval(canvas: Canvas, manifest: Dict[str, Any], operation: str, user: Any) -> None:
    required = {str(item) for item in (manifest.get("required_approvals") or [])}
    if operation in required:
        role = str(getattr(user, "role", "") or "").lower()
        if role not in {"workspace_admin", "admin", "owner", "super_admin"}:
            raise CapabilityError(
                "approval_required",
                f"Operation '{operation}' requires an approved supervisor.",
                403,
            )


def _require_effective(canvas: Canvas, operation: str) -> Dict[str, Any]:
    manifest = get_manifest(canvas)
    if not manifest:
        raise CapabilityError(
            "not_capability_canvas",
            "This canvas has no capability manifest.",
        )
    check = effective_operations(canvas, manifest)
    if operation not in check["effective"]:
        raise CapabilityError(
            "unsupported_operation",
            f"Operation '{operation}' is not available on this canvas. "
            f"Declared={check['declared']}, effective={check['effective']}.",
            supported=check["effective"],
        )
    return manifest


def _frame(canvas: Canvas) -> pd.DataFrame:
    dataset = get_dataset(canvas)
    columns = [str(c) for c in (dataset.get("columns") or [])]
    rows = dataset.get("rows") or []
    sheet_rows = dataset.get("sheet_rows") or []
    if not columns:
        raise CapabilityError("dataset_not_bound", "No dataset is bound to this canvas.")
    records = []
    for idx, row in enumerate(rows):
        if not isinstance(row, (list, tuple)):
            raise CapabilityError("dataset_corrupt", "Dataset rows must be arrays.")
        try:
            row_ref = int(sheet_rows[idx]) if idx < len(sheet_rows) else idx + 2
        except (TypeError, ValueError):
            raise CapabilityError(
                "dataset_corrupt", "Dataset source row references are invalid."
            )
        records.append({
            **{columns[i]: (row[i] if i < len(row) else None) for i in range(len(columns))},
            "__sheet_row": row_ref,
        })
    return pd.DataFrame(records, columns=columns + ["__sheet_row"])


def _subject_values(columns: Sequence[str], row: Dict[str, Any], subject_field: str) -> str:
    value = row.get(subject_field)
    if value is None or str(value).strip() == "":
        raise CapabilityError(
            "ambiguous_subject_mapping",
            f"Row {row.get('__sheet_row')} has no value in subject field "
            f"'{subject_field}'. Bind a populated subject field before assessing.",
        )
    return str(value).strip()


def _dataset_source(canvas: Canvas) -> Dict[str, Any]:
    dataset = get_dataset(canvas)
    source = dataset.get("source") or {}
    result = {
        "resource_id": str(source.get("resource_id") or canvas.id),
        "file_name": str(source.get("file_name") or ""),
        "source_version": str(source.get("source_version") or dataset.get("source_version") or ""),
        "sha256": str(source.get("sha256") or ""),
    }
    # Connected bindings carry two identities: the local canvas snapshot and
    # the upstream provider/file/sheet/version. A local edit updates the
    # snapshot revision but never the upstream version.
    if isinstance(source.get("snapshot"), dict):
        result["snapshot"] = dict(source["snapshot"])
    if isinstance(source.get("upstream"), dict):
        result["upstream"] = dict(source["upstream"])
    result["writeback"] = dict(
        source.get("writeback")
        or {"supported": False, "upstream_mutated": False, "performed": False}
    )
    return result


def _audit(
    db, canvas: Canvas, user: Any, action: str, details: Dict[str, Any],
    agent_id: Optional[str] = None,
) -> None:
    payload = dict(details or {})
    # The audit trail is the canvas read source. Capability manifests/bindings
    # must ride the audit row or /api/canvas/{id} keeps serving the blank
    # creation snapshot from an older row.
    payload.setdefault("content", dict(canvas.content or {}))
    db.add(CanvasAudit(
        id=str(uuid.uuid4()),
        created_at=_now(),
        tenant_id=canvas.tenant_id or "default",
        agent_id=agent_id,
        user_id=str(getattr(user, "id", "") or "") or None,
        canvas_id=canvas.id,
        action_type=action,
        canvas_type=canvas.canvas_type,
        details_json=payload,
    ))


def _init_capability(
    canvas: Canvas, manifest: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    content = dict(content) if isinstance(content, dict) else _canvas_content(canvas)
    content["capability_manifest"] = manifest
    if "capability_revision" not in content:
        content["capability_revision"] = 0
    canvas.content = content
    return content


def set_manifest(db, canvas: Canvas, user: Any, manifest: Dict[str, Any]) -> Dict[str, Any]:
    clean = validate_manifest(manifest)
    content = _init_capability(canvas, clean)
    canvas.last_edited_by = str(getattr(user, "id", "") or "") or None
    canvas.last_edited_at = _now()
    # A changed teaching policy invalidates reusable assessments: there is no
    # stored assessment cache, so the new revision simply cannot be reused
    # under the old policy hash. Record both for the receipt.
    _audit(db, canvas, user, "capability_manifest", {
        "manifest_revision": clean["manifest_revision"],
        "policy_revision": policy_revision(clean),
        "operations": clean["operations"],
    })
    db.commit()
    return {
        "success": True,
        "manifest": clean,
        "operations": effective_operations(canvas, clean),
        "policy_revision": policy_revision(clean),
        "revision": current_revision(canvas),
    }


def _json_cell(value: Any) -> Any:
    """Convert one materialized cell to a JSON-safe scalar without inventing
    values. NaN/NaT are blanks, not zeroes or strings."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _snapshot_digest(
    columns: Sequence[str], rows: Sequence[Sequence[Any]],
    sheet_rows: Optional[Sequence[int]] = None,
) -> str:
    payload = [list(columns), [list(row) for row in rows], list(sheet_rows or [])]
    return hashlib.sha256(
        json.dumps(payload, default=str).encode()
    ).hexdigest()


def _persist_dataset(
    db, canvas: Canvas, user: Any, columns: Sequence[str],
    rows: Sequence[Sequence[Any]], *,
    source: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    verified_file_sha256: Optional[str] = None,
    sheet_rows: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Store one authoritative dataset snapshot on the canvas.

    Both the upload path and the connected-catalog path land here so identity
    handling, revision bumps and audit receipts stay identical. The canvas
    snapshot is always the local resource; connected callers add a separate
    ``upstream`` block that this function never rewrites.
    """
    clean_columns = [str(c).strip() for c in columns]
    if not clean_columns or any(not c for c in clean_columns):
        raise CapabilityError("invalid_dataset", "Columns must be non-empty strings.")
    if len(set(clean_columns)) != len(clean_columns):
        raise CapabilityError("invalid_dataset", "Column names must be unique.")
    clean_rows = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            raise CapabilityError("invalid_dataset", "Rows must be arrays.")
        clean_rows.append(list(row[: len(clean_columns)]))
    if not clean_rows:
        raise CapabilityError("invalid_dataset", "Dataset has no data rows.")

    clean_sheet_rows: Optional[List[int]] = None
    if sheet_rows is not None:
        if len(sheet_rows) != len(clean_rows):
            raise CapabilityError(
                "invalid_dataset",
                "sheet_rows must name exactly one source row per data row.",
            )
        try:
            clean_sheet_rows = [int(value) for value in sheet_rows]
        except (TypeError, ValueError):
            raise CapabilityError(
                "invalid_dataset", "sheet_rows must contain worksheet row numbers."
            )
        if any(value < 2 for value in clean_sheet_rows):
            raise CapabilityError(
                "invalid_dataset", "sheet_rows must be >= 2 (row 1 is the header)."
            )

    source = dict(source or {})
    # Resource identity is the canvas, never a client-supplied id.
    source["resource_id"] = f"canvas:{canvas.id}"
    source.setdefault("file_name", title or "canvas dataset")
    dataset_hash = _snapshot_digest(clean_columns, clean_rows, clean_sheet_rows)
    source["source_version"] = dataset_hash[:16]
    # A client-supplied sha is not authority. Preserve a verified file hash
    # only when the file-upload path supplied one explicitly.
    # The verified file hash is a server-side parameter, never a source-dict
    # key a JSON client could supply.
    source["sha256"] = str(verified_file_sha256 or dataset_hash)
    snapshot = dict(source.get("snapshot") or {})
    snapshot.update({
        "kind": snapshot.get("kind") or "canvas_dataset_snapshot",
        "resource_id": f"canvas:{canvas.id}",
        "version": source["source_version"],
        "sha256": source["sha256"],
        "rows": len(clean_rows),
        "columns": len(clean_columns),
    })
    source["snapshot"] = snapshot
    source.setdefault(
        "writeback",
        {"supported": False, "upstream_mutated": False, "performed": False},
    )

    content = _canvas_content(canvas)
    manifest = get_manifest(canvas) or default_manifest()
    dataset = {
        "columns": clean_columns,
        "rows": clean_rows,
        "source": source,
        "bound_at": _now().isoformat(),
    }
    if clean_sheet_rows is not None:
        dataset["sheet_rows"] = clean_sheet_rows
    content["dataset"] = dataset
    content["capability_revision"] = current_revision(canvas) + 1
    manifest.setdefault("data_binding", {})
    manifest["data_binding"]["resource_id"] = source["resource_id"]
    manifest["data_binding"]["source_version"] = source["source_version"]
    if title:
        canvas.name = title
    canvas.content = _init_capability(canvas, validate_manifest(manifest), content)
    canvas.last_edited_by = str(getattr(user, "id", "") or "") or None
    canvas.last_edited_at = _now()
    _audit(db, canvas, user, "capability_bind", {
        "columns": clean_columns,
        "row_count": len(clean_rows),
        "source": source,
        "revision": content["capability_revision"],
    })
    db.commit()
    return {
        "success": True,
        "columns": clean_columns,
        "row_count": len(clean_rows),
        "source": source,
        "revision": content["capability_revision"],
        "manifest": manifest,
        "operations": effective_operations(canvas, manifest),
    }


def bind_dataset(
    db, canvas: Canvas, user: Any, columns: Sequence[str], rows: Sequence[Sequence[Any]],
    source: Optional[Dict[str, Any]] = None, title: Optional[str] = None,
    verified_file_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    return _persist_dataset(
        db, canvas, user, columns, rows,
        source=source, title=title,
        verified_file_sha256=verified_file_sha256,
    )


def _assert_connected_source_access(
    db, provider: str, user: Any,
) -> Dict[str, Any]:
    """Ask the existing token store whether this user still has a grant.

    A missing grant and a revoked grant are different states. The binding
    never treats cached rows as proof that upstream access still exists.
    """
    from core.models import IntegrationToken

    source = str(provider or "").strip().lower()
    aliases = _CONNECTED_PROVIDER_ALIASES.get(source)
    if not aliases:
        raise CapabilityError(
            "source_access_unverified",
            f"Source '{source or 'unknown'}' has no connected token family; "
            "a cached catalog row alone is not source access.",
            409,
        )
    user_id = str(getattr(user, "id", "") or "")
    if not user_id:
        raise CapabilityError("unauthenticated", "Authentication required.", 401)
    rows = (
        db.query(IntegrationToken)
        .filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.provider.in_(list(aliases)),
        )
        .order_by(IntegrationToken.updated_at.desc())
        .all()
    )
    active = []
    expired = []
    now = _now()
    for row in rows:
        if str(row.status or "").lower() != "active" or not row.access_token:
            continue
        expires = getattr(row, "expires_at", None)
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                expired.append(row)
                continue
        active.append(row)
    if active:
        return {
            "status": "active",
            "provider": source,
            "token_provider": active[0].provider,
            "checked_at": now.isoformat(),
        }
    if expired:
        raise CapabilityError(
            "source_access_expired",
            "The connected source access token is expired. Refresh or "
            "reconnect the source; the cached snapshot is not treated as "
            "current access.",
            409,
        )
    if rows:
        raise CapabilityError(
            "source_permission_revoked",
            "The connected source grant is revoked or inactive. Reconnect the "
            "source; the cached snapshot is not treated as authorised.",
            403,
        )
    raise CapabilityError(
        "source_disconnected",
        "No connected grant exists for this source and user. Reconnect before "
        "binding; no cached rows were used.",
        409,
    )


def _assert_bound_source_access(db, canvas: Canvas, user: Any) -> None:
    source = get_dataset(canvas).get("source") or {}
    upstream = source.get("upstream") if isinstance(source, dict) else None
    if not isinstance(upstream, dict):
        return
    _assert_connected_source_access(
        db, str(upstream.get("provider") or ""), user,
    )


def _validate_connected_coverage(entry: Dict[str, Any]) -> Dict[str, Any]:
    coverage = dict(entry.get("coverage") or {})
    if not coverage.get("known"):
        raise CapabilityError(
            "materialization_incomplete",
            "The catalog entry does not have known materialization coverage; "
            "binding it could certify a partial sheet.",
            409,
        )
    if coverage.get("truncated"):
        raise CapabilityError(
            "materialization_incomplete",
            "The materialized sheet is truncated; a complete result cannot be "
            "certified from this copy.",
            409,
        )
    source_rows = coverage.get("source_row_count")
    materialized = coverage.get("materialized_row_count")
    if source_rows is None or materialized is None:
        raise CapabilityError(
            "materialization_incomplete",
            "The catalog entry is missing source/materialized row counts.",
            409,
        )
    if int(source_rows) != int(materialized):
        raise CapabilityError(
            "materialization_incomplete",
            f"Only {materialized} of {source_rows} source rows were "
            "materialized; no connected snapshot was bound.",
            409,
        )
    if int(entry.get("row_count") or 0) != int(materialized):
        raise CapabilityError(
            "materialization_incomplete",
            "The catalog row count disagrees with its coverage record.",
            409,
        )
    return coverage


def bind_connected_dataset(
    db, canvas: Canvas, user: Any, *,
    dataset_name: Optional[str] = None,
    source: Optional[str] = None,
    external_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    expected_version: Optional[str] = None,
    subject_field: Optional[str] = None,
    measure_field: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Bind a server-resolved connected catalog sheet to this canvas.

    The request names a catalog reference only. The server authorizes the
    canvas, resolves the entry inside the authenticated workspace, verifies
    the source grant and exact version, reads the authoritative Parquet
    frame, and stores a labelled local snapshot with both identities.
    No body field can supply rows, a path or a hash.
    """
    from core.sheet_dataset_service import (
        DatasetScopeError,
        connected_parquet_path,
        resolve_dataset_entry_scoped_sync,
    )

    authorize_canvas(db, canvas, user)
    manifest = _require_effective(canvas, "bind")
    workspace_id = str(getattr(canvas, "workspace_id", "") or "").strip()
    try:
        resolution = resolve_dataset_entry_scoped_sync(
            dataset_name,
            workspace_id=workspace_id,
            source=source,
            external_id=external_id,
            sheet_name=sheet_name,
        )
    except DatasetScopeError as exc:
        raise CapabilityError("workspace_scope_required", str(exc), 400)

    state = resolution.get("state")
    if state == "workspace_mismatch":
        raise CapabilityError(
            "workspace_mismatch",
            "That dataset belongs to a different workspace.",
            403,
        )
    if state == "inactive":
        raise CapabilityError(
            "source_inactive",
            "The source version is superseded or inactive; it cannot be "
            "bound as the authoritative frame.",
            409,
        )
    if state == "ambiguous":
        raise CapabilityError(
            "ambiguous_source",
            "More than one active catalog version matches this reference; "
            "name the exact dataset and version before binding.",
            409,
            candidates=resolution.get("candidates") or [],
        )
    if state != "active" or not resolution.get("entry"):
        raise CapabilityError(
            "source_not_found",
            "No active dataset matches that catalog reference in this "
            "workspace. A guessed name or a deleted source cannot be bound.",
            404,
        )

    entry = resolution["entry"]
    if str(entry.get("source_kind") or "") != "file":
        raise CapabilityError(
            "unsupported_source_kind",
            "Connected binding requires a file-backed dataset entry.",
            409,
        )
    # Catalog rows are workspace-scoped derived data; the authenticated
    # grant check below is per user. ``created_by`` is not an ACL: ingestion
    # workers stamp a workspace/service identity on some rows, so treating it
    # as a user id would reject legitimate connected copies. Multi-user file
    # ACLs remain explicitly unsupported (single-user restrictions stay).
    access = _assert_connected_source_access(
        db, str(entry.get("source") or ""), user,
    )

    actual_version = str(entry.get("content_hash") or "")
    requested_version = str(expected_version or "").strip()
    if requested_version:
        if len(requested_version) < 6 or not (
            actual_version == requested_version
            or actual_version.startswith(requested_version)
        ):
            raise CapabilityError(
                "stale_source_version",
                f"Requested source version '{requested_version}' is not the "
                f"active version '{actual_version[:12]}'. Refresh or bind the "
                "active version explicitly.",
                409,
                active_version=actual_version,
            )

    coverage = _validate_connected_coverage(entry)
    parquet_path = connected_parquet_path(entry)
    if parquet_path is None or not parquet_path.exists():
        raise CapabilityError(
            "materialization_incomplete",
            "The catalog entry points outside the dataset store or its "
            "Parquet copy is missing; no snapshot was bound.",
            409,
        )
    try:
        frame = pd.read_parquet(parquet_path)
    except Exception as exc:  # noqa: BLE001 — corrupt copy is a refusal
        raise CapabilityError(
            "materialization_incomplete",
            f"The materialized copy could not be read ({type(exc).__name__}).",
            409,
        )
    if len(frame) != int(coverage.get("materialized_row_count") or 0):
        raise CapabilityError(
            "materialization_incomplete",
            "The Parquet row count disagrees with the catalog coverage record.",
            409,
        )

    physical_columns = [str(c) for c in frame.columns if str(c) != "__sheet_row"]
    if not physical_columns:
        raise CapabilityError(
            "materialization_incomplete",
            "The materialized sheet has no data columns.",
            409,
        )
    raw_rows = frame[physical_columns].to_dict(orient="records")
    rows = [
        [_json_cell(record.get(column)) for column in physical_columns]
        for record in raw_rows
    ]
    if "__sheet_row" in frame.columns:
        try:
            sheet_rows = [int(value) for value in frame["__sheet_row"].tolist()]
        except (TypeError, ValueError):
            raise CapabilityError(
                "materialization_incomplete",
                "The materialized sheet lost its source row references.",
                409,
            )
    else:
        sheet_rows = list(range(2, len(rows) + 2))

    binding = dict(manifest.get("data_binding") or {})
    configured_subject = str(binding.get("subject_field") or "").strip()
    requested_subject = str(subject_field or "").strip()
    if requested_subject and configured_subject and requested_subject != configured_subject:
        raise CapabilityError(
            "subject_mapping_conflict",
            f"Manifest subject '{configured_subject}' differs from requested "
            f"subject '{requested_subject}'. Change the manifest explicitly.",
            409,
        )
    resolved_subject = requested_subject or configured_subject
    if not resolved_subject:
        raise CapabilityError(
            "subject_field_required",
            "Name the subject field (or set data_binding.subject_field) before "
            "binding connected rows; no column was guessed.",
            400,
            columns=physical_columns,
        )
    if resolved_subject not in physical_columns:
        raise CapabilityError(
            "ambiguous_subject_mapping",
            f"Subject field '{resolved_subject}' is not a column of "
            f"'{entry.get('entity_name')}'.",
            409,
            columns=physical_columns,
        )

    configured_measure = str(binding.get("measure_field") or "").strip()
    requested_measure = str(measure_field or "").strip()
    if requested_measure and configured_measure and requested_measure != configured_measure:
        raise CapabilityError(
            "measure_mapping_conflict",
            f"Manifest measure '{configured_measure}' differs from requested "
            f"measure '{requested_measure}'. Change the manifest explicitly.",
            409,
        )
    resolved_measure = requested_measure or configured_measure
    if resolved_measure and resolved_measure not in physical_columns:
        raise CapabilityError(
            "unknown_measure_field",
            f"Measure field '{resolved_measure}' is not a column of "
            f"'{entry.get('entity_name')}'.",
            409,
            columns=physical_columns,
        )

    upstream = {
        "provider": str(entry.get("source") or ""),
        "dataset_name": str(entry.get("dataset_name") or ""),
        "file_name": str(entry.get("file_name") or ""),
        "external_id": str(entry.get("external_id") or ""),
        "sheet_name": str(entry.get("entity_name") or ""),
        "content_hash": actual_version,
        "version": actual_version,
        "source_modified_at": entry.get("source_modified_at"),
        "ingested_at": entry.get("ingested_at"),
        "workspace_id": workspace_id,
        "coverage": coverage,
    }
    snapshot_label = (
        title
        or f"{entry.get('file_name') or 'connected workbook'} — "
           f"{entry.get('entity_name') or 'sheet'}"
    )
    prior_dataset = get_dataset(canvas)
    prior_source = prior_dataset.get("source") or {}
    prior_upstream = (
        prior_source.get("upstream")
        if isinstance(prior_source.get("upstream"), dict) else None
    )
    previous_bindings = list(prior_source.get("previous_bindings") or [])
    if prior_dataset:
        previous_bindings.append({
            "snapshot": prior_source.get("snapshot"),
            "upstream": prior_upstream,
            "replaced_at": _now().isoformat(),
        })
    refresh = {
        "replaced": bool(prior_dataset),
        "prior_snapshot_version": (
            (prior_source.get("snapshot") or {}).get("version")
            if isinstance(prior_source.get("snapshot"), dict) else None
        ),
        "prior_upstream_version": (
            prior_upstream.get("content_hash") if prior_upstream else None
        ),
        "assessment_reuse_invalidated": bool(prior_dataset),
        "new_upstream_version": actual_version,
    }
    source_meta = {
        "file_name": str(entry.get("file_name") or ""),
        "snapshot": {
            "kind": "canvas_dataset_snapshot",
            "label": snapshot_label,
            "note": "Local snapshot. Edits do not write back to the connected source.",
        },
        "upstream": upstream,
        "writeback": {
            "supported": False,
            "upstream_mutated": False,
            "performed": False,
        },
        "source_access": access,
        "previous_bindings": previous_bindings[-5:],
        "refresh": refresh,
    }
    manifest = dict(manifest)
    binding.update({
        "resource_id": f"canvas:{canvas.id}",
        "subject_field": resolved_subject,
        "measure_field": resolved_measure,
        "source_version": actual_version,
    })
    manifest["data_binding"] = binding
    content = _canvas_content(canvas)
    content["capability_manifest"] = validate_manifest(manifest)
    canvas.content = content

    result = _persist_dataset(
        db, canvas, user, physical_columns, rows,
        source=source_meta, title=snapshot_label, sheet_rows=sheet_rows,
    )
    result["upstream"] = upstream
    result["snapshot"] = result["source"].get("snapshot") or {}
    result["coverage"] = coverage
    result["source_access"] = access
    result["requested_version"] = requested_version or None
    result["refresh"] = refresh
    return result


def parse_tabular_upload(filename: str, content: bytes) -> Tuple[List[str], List[List[Any]]]:
    """Parse CSV/XLSX bytes into header + typed data rows. No display paging:
    the bound dataset is the complete file (the certified total is computed
    over it, never over a truncated view)."""
    if len(content) > _MAX_BIND_BYTES:
        raise CapabilityError("file_too_large", "Dataset exceeds the bind size cap.")
    ext = Path(filename or "").suffix.lower()
    if ext == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        parsed = [row for row in reader]
    elif ext in (".xlsx", ".xlsm"):
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        ws = wb.active
        parsed = [list(row) for row in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raise CapabilityError("unsupported_dataset_type", "Bind a CSV or XLSX dataset.")
    # Preserve interior blank rows: they are real source rows and their
    # positions are part of edit/evidence identity. Only trim trailing blanks.
    while parsed and not any(cell not in (None, "") for cell in parsed[-1]):
        parsed.pop()
    if len(parsed) < 2:
        raise CapabilityError("invalid_dataset", "Dataset needs a header and at least one row.")
    header = [str(cell).strip() if cell is not None else "" for cell in parsed[0]]
    if not all(header):
        raise CapabilityError("invalid_dataset", "Every dataset column needs a header.")
    rows = [list(row) for row in parsed[1:]]
    return header, rows


def _select(
    df: pd.DataFrame, columns: List[str], ask: str,
    max_rows: Optional[int] = None,
    required_columns: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from core.table_selection import resolve_selection, select_rows

    physical = [c for c in columns if c != "__sheet_row"]
    resolved = resolve_selection(physical, ask, df)
    if not resolved.get("ok"):
        raise CapabilityError(
            "ambiguous_selection",
            f"Selection needs clarification: {resolved.get('reason')}.",
            candidates=resolved.get("candidates") or [],
        )
    chosen = [c for c in resolved.get("columns") or physical if c in physical]
    if required_columns:
        # Assessment evidence needs the subject/measure/status columns even
        # when the ask only named the predicate column. Selection semantics
        # stay unchanged for the other operations.
        required = [c for c in physical if c in set(required_columns)]
        chosen = [c for c in physical if c in set(chosen) | set(required)]
    predicate = resolved.get("predicate")
    result = select_rows(
        df, chosen, predicate,
        **({"max_rows": max(1, max_rows)} if max_rows is not None else {}),
    )
    if result.get("status") not in ("complete", "no_rows"):
        raise CapabilityError(
            "selection_failed",
            f"Selection failed: {result.get('reason')}.",
            detail=result.get("detail"),
        )
    return result, resolved


def select_operation(db, canvas: Canvas, user: Any, ask: str) -> Dict[str, Any]:
    manifest = _require_effective(canvas, "select")
    _assert_bound_source_access(db, canvas, user)
    dataset = get_dataset(canvas)
    columns = list(dataset.get("columns") or [])
    df = _frame(canvas)
    result, resolved = _select(df, columns, ask)
    source = _dataset_source(canvas)
    return {
        "success": True,
        "operation": "select",
        "canvas_id": canvas.id,
        "source": source,
        "source_revision": get_dataset(canvas).get("source", {}).get("source_version"),
        "manifest_revision": manifest.get("manifest_revision"),
        "revision": current_revision(canvas),
        "columns": result.get("columns"),
        "predicate": result.get("predicate"),
        "rows": result.get("rows") or [],
        "selected_count": result.get("selected_count") or 0,
        "source_row_count": result.get("source_row_count"),
        "not_selected_count": result.get("not_selected_count"),
        "status": result.get("status"),
        "sql": result.get("sql"),
        "coverage": {
            "complete_dataset": True,
            "displayed_rows": len(result.get("rows") or []),
            "source_rows": result.get("source_row_count"),
        },
    }


def _resolve_measure(columns: Sequence[str], ask: str, manifest: Dict[str, Any]) -> Optional[str]:
    from core.table_selection import _mentioned_columns, normalize

    mentioned = _mentioned_columns(list(columns), ask)
    for candidate in mentioned:
        return candidate
    configured = str((manifest.get("data_binding") or {}).get("measure_field") or "").strip()
    if configured and configured in columns:
        return configured
    return None


def calculate_operation(db, canvas: Canvas, user: Any, ask: str) -> Dict[str, Any]:
    from core.dataset_aggregation import (
        aggregate_selected_rows,
        looks_like_aggregate_request,
    )

    manifest = _require_effective(canvas, "calculate")
    _assert_bound_source_access(db, canvas, user)
    dataset = get_dataset(canvas)
    columns = list(dataset.get("columns") or [])
    df = _frame(canvas)
    ask_text = str(ask or "").strip()
    if "=" in ask_text or "formula" in ask_text.lower():
        raise CapabilityError(
            "unsupported_formula",
            "Formula evaluation is not part of the table adapter. Use the "
            "Excel-like canvas for formulas; no total was computed here.",
        )
    is_count = bool(
        any(term in ask_text.lower() for term in ("count", "how many", "number of rows"))
    )
    if not is_count and not looks_like_aggregate_request(ask_text):
        raise CapabilityError(
            "unsupported_operation",
            "No supported calculation was requested. The table adapter supports "
            "sum of one explicitly named numeric measure and count.",
        )
    # Calculation is over the COMPLETE eligible dataset, never the displayed
    # page. The display cap remains for selection rendering only.
    selected, _resolved = _select(df, columns, ask_text, max_rows=len(df))
    physical = [c for c in columns if c != "__sheet_row"]
    measure = "" if is_count else _resolve_measure(physical, ask_text, manifest)
    if not is_count and not measure:
        raise CapabilityError(
            "ambiguous_measure",
            "Name the numeric measure to sum explicitly; no column was guessed.",
            columns=physical,
        )
    records = [
        {"__sheet_row": row.get("row"), **(row.get("cells") or {})}
        for row in (selected.get("rows") or [])
    ]
    binding = manifest.get("data_binding") or {}
    roles = {
        "identity_column": str(binding.get("subject_field") or ""),
        "status_column": str(binding.get("status_field") or ""),
        "currency_column": str(binding.get("currency_field") or ""),
    }
    source = _dataset_source(canvas)
    upstream = source.get("upstream") or {}
    # The authoritative workbook version is the upstream content hash. The
    # derived canvas snapshot revision is reported separately; it is never
    # presented as the workbook's version.
    version = str(
        upstream.get("content_hash")
        or source.get("source_version")
        or ""
    )
    coverage = {
        "complete_dataset": True,
        "selected_count": selected.get("selected_count"),
        "source_row_count": selected.get("source_row_count"),
    }
    if source.get("snapshot"):
        coverage["snapshot_version"] = source["snapshot"].get("version")
    if upstream:
        coverage["upstream_version"] = upstream.get("content_hash")
        coverage["upstream_provider"] = upstream.get("provider")
        coverage["upstream_external_id"] = upstream.get("external_id")
    result = aggregate_selected_rows(
        records,
        physical,
        roles,
        sheet=str(source.get("file_name") or "canvas"),
        file_name=str(source.get("file_name") or "canvas dataset"),
        version=version,
        source_row_count=selected.get("source_row_count"),
        coverage=coverage,
        operation="count" if is_count else "sum",
        value_column="" if is_count else str(measure),
    )
    if source.get("snapshot") and upstream:
        note = (
            f"Canvas snapshot: `{str(source['snapshot'].get('version') or '')[:12]}` "
            "(local; edits do not write back). "
            f"Upstream: `{upstream.get('provider')}` "
            f"`{upstream.get('external_id')}` "
            f"version `{str(upstream.get('content_hash') or '')[:12]}`."
        )
        result["block"] = note + "\n" + str(result.get("block") or "")
        if result.get("answer"):
            result["answer"] = note + "\n" + str(result["answer"])
    total_values = {
        key: bucket.get("value")
        for key, bucket in (result.get("subtotals") or {}).items()
    }
    return {
        "success": result.get("status") == "complete",
        "operation": "count" if is_count else "sum",
        "canvas_id": canvas.id,
        "ask": ask_text,
        "source": source,
        "manifest_revision": manifest.get("manifest_revision"),
        "revision": current_revision(canvas),
        "measure": measure or "row count",
        "selected_count": selected.get("selected_count"),
        "source_row_count": selected.get("source_row_count"),
        "not_selected_count": selected.get("not_selected_count"),
        "subtotals": result.get("subtotals") or {},
        "total_values": total_values,
        "gaps": result.get("gaps") or [],
        "rows": result.get("rows") or [],
        "coverage": result.get("coverage") or {},
        "block": result.get("block"),
        "answer": result.get("answer"),
        "status": result.get("status"),
    }


def _evidence_index(
    rows: Sequence[Dict[str, Any]], subject_field: str, source: Dict[str, Any],
    execution_id: str, columns: Sequence[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    entries: List[Dict[str, Any]] = []
    subjects: List[str] = []
    seen_subjects = set()
    for row in rows:
        cells = row.get("cells") or {}
        subject = _subject_values(columns, cells, subject_field)
        if subject in seen_subjects:
            raise CapabilityError(
                "duplicate_subject_mapping",
                f"Subject '{subject}' appears on more than one selected row; "
                "bind a unique subject field before assessing.",
            )
        seen_subjects.add(subject)
        subjects.append(subject)
        row_ref = row.get("row")
        entries.append({
            "evidence_id": f"ev:{subject}:{row_ref}",
            "subject_id": subject,
            "source_identity": {
                "resource_id": source.get("resource_id"),
                "file_name": source.get("file_name"),
                "source_version": source.get("source_version"),
                "sha256": source.get("sha256"),
                "snapshot_version": (
                    source.get("snapshot") or {}).get("version"),
                "upstream_provider": (
                    source.get("upstream") or {}).get("provider"),
                "upstream_external_id": (
                    source.get("upstream") or {}).get("external_id"),
                "upstream_version": (
                    source.get("upstream") or {}).get("content_hash"),
            },
            "retrieval_operation": "canvas_table_read",
            "retrieval_execution_id": execution_id,
            "row_ref": f"row {row_ref}" if row_ref else None,
            "values": [
                f"{column}={cells.get(column)!r}" for column in columns
            ],
        })
    return entries, subjects


async def assess_operation(
    db, canvas: Canvas, user: Any, ask: str,
    llm_service: Any = None,
    max_subjects: Optional[int] = None,
) -> Dict[str, Any]:
    from core.review_result import (
        LAST_STRUCTURED_REVIEW,
        build_policy_index,
        build_review_result,
        generate_structured_review,
        render_review_result,
        review_output_instruction,
    )

    manifest = _require_effective(canvas, "assess")
    _require_approval(canvas, manifest, "assess", user)
    _assert_bound_source_access(db, canvas, user)
    columns = list(get_dataset(canvas).get("columns") or [])
    subject_field = str((manifest.get("data_binding") or {}).get("subject_field") or "")
    if subject_field not in columns:
        raise CapabilityError(
            "ambiguous_subject_mapping",
            f"Subject field '{subject_field}' is not a bound column.",
        )
    df = _frame(canvas)
    physical = [c for c in columns if c != "__sheet_row"]
    selected, _resolved = _select(
        df, columns, ask or "all rows", max_rows=len(df),
        required_columns=physical,
    )
    rows = selected.get("rows") or []
    if not rows:
        raise CapabilityError("no_rows", "The assessment selection returned no rows.")
    execution_id = f"canvas-{canvas.id}-{uuid.uuid4().hex[:12]}"
    source = _dataset_source(canvas)

    # Bounded assessment: the deterministic selection may name thousands of
    # subjects. Never dispatch them all. Subjects beyond the cap are named in
    # the receipt rather than silently dropped.
    all_subjects: List[str] = []
    seen_subjects = set()
    for row in rows:
        subject = _subject_values(physical, row.get("cells") or {}, subject_field)
        if subject in seen_subjects:
            raise CapabilityError(
                "duplicate_subject_mapping",
                f"Subject '{subject}' appears on more than one selected row; "
                "bind a unique subject field before assessing.",
            )
        seen_subjects.add(subject)
        all_subjects.append(subject)
    cap = int(max_subjects if max_subjects is not None else _MAX_ASSESS_SUBJECTS)
    if cap < 1:
        raise CapabilityError(
            "invalid_assessment_scope", "max_subjects must be at least 1."
        )
    assessed_rows = rows[:cap]
    subjects = all_subjects[:cap]
    unassessed_subjects = all_subjects[cap:]
    evidence, _ = _evidence_index(
        assessed_rows, subject_field, source, execution_id, physical,
    )
    coverage = {
        "selected_count": len(rows),
        "assessed_count": len(subjects),
        "unassessed_count": len(unassessed_subjects),
        "assessment_truncated": bool(unassessed_subjects),
        "max_subjects": cap,
        "limit_source": "request" if max_subjects is not None else "default",
        "assessed_subjects": subjects,
        "unassessed_subjects": unassessed_subjects,
        "selection_source_row_count": selected.get("source_row_count"),
    }
    decisions = list(manifest.get("decision_options") or [])
    policy_text = str(manifest.get("task_policy") or "").strip()
    policy_id = f"policy:{policy_revision(manifest)}"
    lessons = [{
        "id": policy_id,
        "topic": "task policy",
        "lesson": policy_text,
        "decision_options": decisions,
    }]
    policies = build_policy_index(lessons, decisions)
    if not policies:
        raise CapabilityError(
            "policy_unavailable",
            "The task policy/decision vocabulary did not produce a selectable "
            "policy entry; no assessment was dispatched.",
        )
    contract = {
        "subjects": subjects,
        "allowed_decisions": decisions,
        "required_actions": [],
    }
    source_rows = "\n".join(
        f"- subject={entry['subject_id']} | {entry['row_ref']} | "
        + " | ".join(entry["values"])
        for entry in evidence
    )
    upstream = source.get("upstream") or {}
    snapshot = source.get("snapshot") or {}
    if upstream:
        identity_text = (
            "Local canvas snapshot: "
            f"version {snapshot.get('version') or source.get('source_version')} "
            "(edits are local; no source writeback).\n"
            f"Upstream: provider {upstream.get('provider')}; "
            f"item {upstream.get('external_id')}; "
            f"file {upstream.get('file_name')}; "
            f"sheet {upstream.get('sheet_name')}; "
            f"version {upstream.get('content_hash')}.\n"
        )
    else:
        identity_text = (
            f"Local canvas dataset: {source.get('file_name')}; "
            f"version {source.get('source_version')}.\n"
        )
    coverage_text = (
        f"Assessment coverage: {len(subjects)} assessed, "
        f"{len(unassessed_subjects)} selected but unassessed "
        f"(cap {cap}, {coverage['limit_source']})."
    )
    system = (
        "You assess authoritative canvas rows under the task policy below. "
        "Use only the supplied rows and policy. Do not invent rows, columns, "
        "sources or decisions.\n\n"
        + review_output_instruction(contract, evidence, policies)
        + "\n\nSOURCE IDENTITY\n" + identity_text
        + "\n" + coverage_text
        + "\n\nSOURCE ROWS\n" + source_rows
        + "\n\nPOLICY TEXT\n" + policy_text
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": str(ask or "Assess every selected row.")},
    ]
    review_model = str(os.getenv("ATOM_REVIEW_MODEL", "") or "").strip()
    if not review_model:
        raise CapabilityError(
            "review_model_unconfigured",
            "ATOM_REVIEW_MODEL is not configured; refusing an unpinned review dispatch.",
        )
    if llm_service is None:
        from core.llm_service import get_llm_service

        llm_service = get_llm_service(
            workspace_id=canvas.workspace_id,
            tenant_id=canvas.tenant_id,
        )
    answer = await generate_structured_review(
        llm_service,
        messages=messages,
        model=review_model,
        llm_scope={
            "workspace_id": canvas.workspace_id,
            "tenant_id": canvas.tenant_id,
            "agent_id": (manifest.get("teaching_binding") or {}).get("agent_id"),
        },
    )
    route = dict(LAST_STRUCTURED_REVIEW)
    if not answer:
        return {
            "success": False,
            "operation": "assess",
            "canvas_id": canvas.id,
            "status": "failed_closed",
            "certified": False,
            "errors": [{
                "code": route.get("failure_kind") or "structured_review_failed",
                "stage": route.get("failure_stage"),
                "detail": route.get("failure_detail"),
            }],
            "route": route,
            "source": source,
            "coverage": coverage,
            "subjects": subjects,
            "unassessed_subjects": unassessed_subjects,
            "manifest_revision": manifest.get("manifest_revision"),
            "policy_revision": policy_revision(manifest),
        }
    review = build_review_result(
        execution_id=execution_id,
        requested_records=subjects,
        answer=answer,
        allowed_decisions=decisions,
        evidence_index=evidence,
        policy_index=policies,
    )
    certified = bool(review.get("ok")) and review.get("completion") == "completed"
    unresolved_subjects = [
        str(item.get("subject_id"))
        for item in (review.get("assessments") or [])
        if isinstance(item, dict) and (item.get("unresolved_requirements") or [])
    ]
    review_policy = assessment_review_policy()
    review_reasons: List[str] = []
    if not certified:
        review_reasons.append("assessment_uncertified")
    if unresolved_subjects:
        review_reasons.append("unresolved_requirements")
    serving = assessment_serving_configuration(route.get("served_provider"))
    qualification = assessment_qualification(
        route.get("served_provider"), route.get("served_model"),
        policy_text=manifest.get("task_policy") or "",
        decision_options=manifest.get("decision_options") or [],
        subject_field=(manifest.get("data_binding") or {}).get("subject_field"),
        contract_version=review.get("schema_version"),
        serving=serving,
    )
    if review_policy == _REVIEW_POLICY_ALWAYS:
        review_reasons.append("review_policy_always")
    else:
        # SCOPED: autonomy needs BOTH a qualified configuration AND the
        # owner's policy for this topic. One cannot override the other.
        if not qualification.get("qualified"):
            review_reasons.append("qualification_required")
        try:
            from core.autonomy_policy import OUTCOME_EXECUTE, gate_for_topic

            gate = gate_for_topic(
                db, str(getattr(user, "id", "") or "") or None,
                _ASSESSMENT_TOPIC,
                agent_id=str(
                    (manifest.get("teaching_binding") or {}).get("agent_id")
                    or "") or None,
            )
        except Exception as exc:  # noqa: BLE001 — fail closed
            gate = {"outcome": "propose", "error": str(exc)[:200]}
        if gate.get("outcome") != OUTCOME_EXECUTE:
            review_reasons.append("autonomy_policy_denied")
    review_required = bool(review_reasons)

    execution_fingerprint = _sha256_json({
        "policy_revision": policy_revision(manifest),
        "teaching_context": manifest.get("teaching_context") or {},
        "source_version": source.get("source_version"),
        "upstream_version": (source.get("upstream") or {}).get("content_hash"),
        "ask": str(ask or ""),
        "max_subjects": cap,
        "assessed_subjects": subjects,
        "decisions": decisions,
    })[:24]
    # Deep copy: SQLAlchemy's JSON column compares old and new values, so an
    # in-place mutation of a nested record would be seen as "no change" and
    # silently skip the UPDATE.
    content = copy.deepcopy(_canvas_content(canvas))
    assessment_artifact = _canonical_assessment_artifact(
        review.get("assessments") or [])
    previous_assessment_revision = current_assessment_revision(canvas)
    content["assessment_review"] = {
        "execution_id": execution_id,
        "execution_fingerprint": execution_fingerprint,
        "source_revision": source.get("source_version"),
        "policy_revision": policy_revision(manifest),
        "manifest_revision": manifest.get("manifest_revision"),
        "canvas_revision": current_revision(canvas),
        # Every writer of assessment state increments this token; approval is
        # a compare-and-swap on it, so two writers cannot both win.
        "assessment_revision": previous_assessment_revision + 1,
        "certified": certified,
        "review_required": review_required,
        "review_reasons": review_reasons,
        "review_policy": review_policy,
        "qualification": qualification,
        "served_provider": route.get("served_provider"),
        "served_model": route.get("served_model"),
        "contract_version": review.get("schema_version"),
        "serving": serving,
        "authority": {
            "owner_id": str(getattr(user, "id", "") or ""),
            "agent_id": str(
                (manifest.get("teaching_binding") or {}).get("agent_id") or ""),
            "workspace_id": str(canvas.workspace_id or ""),
            "tenant_id": str(canvas.tenant_id or ""),
            "capability": _ASSESSMENT_CAPABILITY,
            "topic": _ASSESSMENT_TOPIC,
        },
        # The single reviewed artifact and its digest. No separate decision
        # map: what is approved is exactly what is returned downstream.
        "assessments": assessment_artifact,
        "assessment_content_sha256": _assessment_digest(assessment_artifact),
        "unresolved_subjects": [
            item["subject_id"] for item in assessment_artifact
            if item["unresolved_requirements"]
        ],
        "assessed_at": _now().isoformat(),
        # A new assessment invalidates any earlier human approval: the
        # authorization below is cleared here and must be granted again for
        # THIS execution, source/policy revision and assessment content.
        "authorization": None,
    }
    canvas.content = content
    db.commit()

    return {
        "success": certified,
        "operation": "assess",
        "canvas_id": canvas.id,
        "execution_id": execution_id,
        "execution_fingerprint": execution_fingerprint,
        "status": review.get("completion"),
        "certified": certified,
        "review_required": review_required,
        "review_reasons": review_reasons,
        "qualification": qualification,
        "unresolved_subjects": unresolved_subjects,
        "authorization": assessment_authorization(canvas, db=db),
        "assessments": review.get("assessments") or [],
        "errors": review.get("errors") or [],
        "review": review,
        # `rendered` is the human-readable decision artifact. Until the
        # assessment is authorized (and under the default policy that means a
        # human approved it), the existing consumer must not receive it as an
        # actionable decision set.
        "rendered": (
            render_review_result(review)
            if certified and assessment_authorization(canvas, db=db).get("state")
            == "authorized" else ""),
        "rendered_suppressed": bool(
            certified and assessment_authorization(canvas, db=db).get("state")
            != "authorized"),
        "authorized": assessment_authorization(canvas, db=db).get("state") == "authorized",
        "route": route,
        "source": source,
        "source_revision": source.get("source_version"),
        "upstream_revision": (source.get("upstream") or {}).get("content_hash"),
        "manifest_revision": manifest.get("manifest_revision"),
        "policy_revision": policy_revision(manifest),
        "teaching_snapshot": {
            "policy_revision": policy_revision(manifest),
            "task_policy": str(manifest.get("task_policy") or ""),
            "decision_options": list(manifest.get("decision_options") or []),
            "teaching_context": dict(manifest.get("teaching_context") or {}),
            "source_snapshot_version": source.get("source_version"),
            "source_upstream_version": (
                source.get("upstream") or {}).get("content_hash"),
            "execution_id": execution_id,
        },
        "subjects": subjects,
        "unassessed_subjects": unassessed_subjects,
        "coverage": coverage,
        "evidence_count": len(evidence),
    }


def edit_operation(
    db, canvas: Canvas, user: Any, edits: Sequence[Dict[str, Any]],
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    manifest = _require_effective(canvas, "edit")
    _require_approval(canvas, manifest, "edit", user)
    _assert_bound_source_access(db, canvas, user)
    content = _canvas_content(canvas)
    dataset = get_dataset(canvas)
    columns = list(dataset.get("columns") or [])
    rows = [list(row) for row in (dataset.get("rows") or [])]
    sheet_rows = dataset.get("sheet_rows") or []
    editable = set(manifest.get("editable_fields") or [])
    if not editable:
        raise CapabilityError(
            "edit_not_allowed",
            "No editable fields are declared; this canvas is read-only.",
        )
    if expected_revision is None:
        raise CapabilityError(
            "revision_required",
            "expected_revision is required for an edit; refusing an unchecked write.",
        )
    if int(expected_revision) != current_revision(canvas):
        raise CapabilityError(
            "stale_revision",
            f"Expected revision {expected_revision} but canvas is at "
            f"{current_revision(canvas)}. Nothing was changed.",
        )
    readback = []
    changed = 0
    for edit in edits or []:
        if not isinstance(edit, dict):
            raise CapabilityError("invalid_edit", "Each edit must be an object.")
        try:
            row_number = int(edit.get("row"))
        except (TypeError, ValueError):
            raise CapabilityError("invalid_edit", "edit.row must be the sheet row (2 = first data row).")
        column = str(edit.get("column") or "")
        if column not in columns:
            raise CapabilityError("unknown_column", f"Column '{column}' is not bound.")
        if column not in editable:
            raise CapabilityError(
                "edit_not_allowed",
                f"Column '{column}' is not declared editable.",
            )
        if sheet_rows:
            try:
                idx = sheet_rows.index(row_number)
            except ValueError:
                raise CapabilityError(
                    "row_not_found",
                    f"Row {row_number} is not a source row in this snapshot.",
                )
        else:
            idx = row_number - 2
        if idx < 0 or idx >= len(rows):
            raise CapabilityError("row_not_found", f"Row {row_number} is outside the dataset.")
        before = rows[idx][columns.index(column)] if columns.index(column) < len(rows[idx]) else None
        after = edit.get("value")
        if before == after:
            readback.append({
                "row": row_number, "column": column, "before": before,
                "after": before, "changed": False, "already_satisfied": True,
            })
            continue
        while len(rows[idx]) < len(columns):
            rows[idx].append(None)
        rows[idx][columns.index(column)] = after
        changed += 1
        readback.append({
            "row": row_number, "column": column, "before": before,
            "after": after, "changed": True, "already_satisfied": False,
        })
    dataset["rows"] = rows
    source = dict(dataset.get("source") or {})
    snapshot_hash = _snapshot_digest(columns, rows, sheet_rows)
    source["source_version"] = snapshot_hash[:16]
    source["sha256"] = snapshot_hash
    snapshot = dict(source.get("snapshot") or {})
    if snapshot:
        snapshot["version"] = source["source_version"]
        snapshot["sha256"] = snapshot_hash
        snapshot["rows"] = len(rows)
        source["snapshot"] = snapshot
    source["writeback"] = {
        "supported": False,
        "upstream_mutated": False,
        "performed": False,
    }
    dataset["source"] = source
    content["dataset"] = dataset
    content["capability_revision"] = current_revision(canvas) + (1 if changed else 0)
    canvas.content = content
    canvas.last_edited_by = str(getattr(user, "id", "") or "") or None
    canvas.last_edited_at = _now()
    if changed:
        _audit(db, canvas, user, "capability_edit", {
            "edits": readback,
            "revision": content["capability_revision"],
            "source_version": dataset["source"]["source_version"],
        })
    db.commit()
    # Read back from the authoritative row, not the in-memory request.
    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).first() or canvas
    fresh_dataset = get_dataset(fresh)
    fresh_rows = fresh_dataset.get("rows") or []
    fresh_sheet_rows = fresh_dataset.get("sheet_rows") or []
    for item in readback:
        if fresh_sheet_rows:
            try:
                idx = fresh_sheet_rows.index(int(item["row"]))
            except ValueError:
                idx = -1
        else:
            idx = int(item["row"]) - 2
        col = columns.index(item["column"])
        observed = fresh_rows[idx][col] if 0 <= idx < len(fresh_rows) and col < len(fresh_rows[idx]) else None
        item["readback"] = observed
        item["readback_matches"] = observed == item["after"]
    fresh_source = _dataset_source(fresh)
    return {
        "success": all(item["readback_matches"] for item in readback),
        "operation": "edit",
        "canvas_id": canvas.id,
        "changed_count": changed,
        "edits": readback,
        "revision": current_revision(fresh),
        "source_version": fresh_source.get("source_version"),
        "upstream_revision": (fresh_source.get("upstream") or {}).get("content_hash"),
        "source": fresh_source,
        "writeback": fresh_source.get("writeback"),
        "manifest_revision": manifest.get("manifest_revision"),
    }


_APPROVER_ROLES = {"workspace_admin", "admin", "owner", "super_admin"}


def _canonical_assessment_artifact(
    assessments: Any,
) -> List[Dict[str, Any]]:
    """The ONE reviewed artifact: decisions, basis, evidence, policy, gaps.

    Canonical form (subjects sorted, nested lists sorted, fixed keys) so the
    digest is a function of the reviewed content and nothing else. Downstream
    decisions are derived from THIS artifact — there is no separately mutable
    decision map that could disagree with what was approved.
    """
    normalized: List[Dict[str, Any]] = []
    for item in sorted(
        (a for a in (assessments or []) if isinstance(a, dict)),
        key=lambda a: str(a.get("subject_id")),
    ):
        evidence = sorted(
            (
                {
                    "evidence_id": entry.get("evidence_id"),
                    "row_ref": entry.get("row_ref"),
                    "values": list(entry.get("values") or []),
                }
                for entry in (
                    item.get("evidence_refs") or item.get("evidence") or [])
                if isinstance(entry, dict)
            ),
            key=lambda e: str(e.get("evidence_id")),
        )
        policies = sorted(
            (
                {
                    "policy_id": entry.get("policy_id"),
                    "lesson": entry.get("lesson"),
                }
                for entry in (
                    item.get("policy_refs") or item.get("policies") or [])
                if isinstance(entry, dict)
            ),
            key=lambda e: str(e.get("policy_id")),
        )
        normalized.append({
            "subject_id": str(item.get("subject_id")),
            "decision": str(item.get("decision")),
            "basis": [str(entry) for entry in (item.get("basis") or [])],
            "evidence": evidence,
            "policies": policies,
            "unresolved_requirements": [
                str(entry)
                for entry in (item.get("unresolved_requirements") or [])
            ],
        })
    return normalized


def _assessment_digest(assessments: Any) -> str:
    """Digest computed from the artifact itself, never from a stored hash."""
    return _sha256_json(_canonical_assessment_artifact(assessments))


def _assessment_binding(
    record: Dict[str, Any], digest: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "execution_id": record.get("execution_id"),
        "execution_fingerprint": record.get("execution_fingerprint"),
        "source_revision": record.get("source_revision"),
        "policy_revision": record.get("policy_revision"),
        "manifest_revision": record.get("manifest_revision"),
        "canvas_revision": record.get("canvas_revision"),
        "assessment_content_sha256": (
            digest if digest is not None
            else _assessment_digest(record.get("assessments") or [])),
    }


def _reload_canvas(db, canvas: Canvas) -> Canvas:
    """Authoritative read that bypasses the session's identity-map copy.

    A stale ORM object is exactly how a lost update happens: validation sees
    revision N while the database is already at N+1.
    """
    if db is None:
        return canvas
    fresh = (
        db.query(Canvas)
        .populate_existing()
        .filter(Canvas.id == canvas.id)
        .one_or_none()
    )
    return fresh or canvas


def _assessment_cas_predicates(
    dialect: str, revision: Any, execution_id: str,
    assessment_revision: Any = None,
):
    """WHERE-clause predicates for an atomic assessment write.

    The revision is the capability revision stored in the canvas content; the
    execution id pins the exact assessment. Both are evaluated BY THE DATABASE,
    so a write that lands between our read and our update makes the update
    match zero rows instead of overwriting it.
    """
    if dialect == "sqlite":
        return (
            func.json_extract(Canvas.content, "$.capability_revision")
            == revision,
            func.json_extract(
                Canvas.content, "$.assessment_review.execution_id")
            == execution_id,
            func.json_extract(
                Canvas.content, "$.assessment_review.assessment_revision")
            == assessment_revision,
        )
    if dialect == "postgresql":
        return (
            Canvas.content["capability_revision"].astext == str(revision),
            Canvas.content["assessment_review"]["execution_id"].astext
            == execution_id,
            Canvas.content["assessment_review"]["assessment_revision"].astext
            == str(assessment_revision),
        )
    return None


def _cas_update_assessment_content(
    db, canvas: Canvas, *, observed_revision: Any, execution_id: str,
    new_content: Dict[str, Any], observed_assessment_revision: Any,
) -> bool:
    """Database-enforced compare-and-swap for an assessment write.

    Returns True only when EXACTLY one row matched (id, capability revision,
    assessment execution id). Zero rows means another writer changed the canvas
    after our read; the caller must refuse and leave their work in place.
    """
    dialect = db.get_bind().dialect.name
    predicates = _assessment_cas_predicates(
        dialect, observed_revision, execution_id, observed_assessment_revision)
    if predicates is None:
        return False
    result = db.execute(
        update(Canvas)
        .where(Canvas.id == canvas.id)
        .where(*predicates)
        .values(content=new_content, updated_at=_now())
    )
    return result.rowcount == 1


def assessment_authorization(
    canvas: Canvas, db=None,
) -> Dict[str, Any]:
    """Authorization state of the CURRENT assessment on this canvas.

    The canvas is reloaded from the database when a session is supplied, and
    the digest is RECOMPUTED from the persisted artifact on every call. A
    stored hash is not evidence, and a session's cached copy is not the truth.
    """
    fresh = _reload_canvas(db, canvas) if db is not None else canvas
    content = _canvas_content(fresh)
    record = content.get("assessment_review")
    if not isinstance(record, dict) or not record:
        return {"state": "no_assessment"}

    artifact = record.get("assessments")
    if not isinstance(artifact, list) or not artifact:
        return {
            "state": "content_drift",
            "reason": "assessment artifact is missing or unreadable",
        }
    digest = _assessment_digest(artifact)
    if digest != record.get("assessment_content_sha256"):
        return {
            "state": "content_drift",
            "reason": "assessment content changed since it was recorded",
            "recomputed_sha256": digest,
            "recorded_sha256": record.get("assessment_content_sha256"),
        }
    if record.get("canvas_revision") != current_revision(fresh):
        return {
            "state": "stale_assessment",
            "reason": "canvas data changed since this assessment",
            "binding": _assessment_binding(record, digest),
        }

    manifest = get_manifest(fresh) or {}
    source = _dataset_source(fresh)
    current_policy = policy_revision(manifest) if manifest else None
    current_source = source.get("source_version")
    if (
        record.get("policy_revision") != current_policy
        or record.get("source_revision") != current_source
    ):
        return {
            "state": "stale_assessment",
            "reason": "policy or source changed since this assessment",
            "binding": _assessment_binding(record, digest),
        }

    binding = _assessment_binding(record, digest)
    # Current authority is re-evaluated from live state, never from the
    # assessment's stored review_required flag. Qualification, task scope AND
    # the owner's present autonomy gate must all still permit this operation.
    if record.get("review_policy") == _REVIEW_POLICY_SCOPED:
        current_qualification = assessment_qualification(
            record.get("served_provider"), record.get("served_model"),
            policy_text=manifest.get("task_policy") or "",
            decision_options=manifest.get("decision_options") or [],
            subject_field=(
                manifest.get("data_binding") or {}).get("subject_field"),
            contract_version=record.get("contract_version"),
            serving=assessment_serving_configuration(
                record.get("served_provider")),
        )
        if not current_qualification.get("qualified"):
            return {
                "state": (
                    "revoked" if current_qualification.get("revoked")
                    else "qualification_out_of_scope"),
                "reason": (
                    "qualification_revoked"
                    if current_qualification.get("revoked")
                    else "qualification_out_of_scope"),
                "qualification": current_qualification,
                "binding": binding,
            }
        authority = record.get("authority") or {}
        if db is None:
            return {
                "state": "authority_unverified",
                "reason": "no session to re-evaluate owner authority",
                "authority": authority,
                "binding": binding,
            }
        try:
            from core.autonomy_policy import OUTCOME_EXECUTE, gate_for_topic

            gate = gate_for_topic(
                db,
                str(authority.get("owner_id") or "") or None,
                str(authority.get("topic") or _ASSESSMENT_TOPIC),
                agent_id=str(authority.get("agent_id") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001 — fail closed
            gate = {"outcome": "propose", "error": str(exc)[:200]}
        if gate.get("outcome") != OUTCOME_EXECUTE:
            return {
                "state": "authority_withdrawn",
                "reason": "owner autonomy gate no longer allows execution",
                "authority": authority,
                "gate": gate,
                "binding": binding,
            }
    if not record.get("review_required"):
        # Only reachable under the explicit ``model_reported`` opt-out.
        return {
            "state": "authorized",
            "approval": None,
            "binding": binding,
            "reason": "review_policy_model_reported",
        }
    approval = record.get("authorization") or {}
    if approval and all(
        approval.get(key) == value for key, value in binding.items()
    ):
        return {"state": "authorized", "approval": approval, "binding": binding}
    return {
        "state": "review_required",
        "review_reasons": list(record.get("review_reasons") or []),
        "unresolved_subjects": [
            item["subject_id"] for item in artifact
            if item.get("unresolved_requirements")
        ],
        "binding": binding,
    }


def approve_assessment(db, canvas: Canvas, user: Any, execution_id: str) -> Dict[str, Any]:
    """Record a human approval with a database-enforced compare-and-swap.

    Every validation runs against a freshly reloaded row, and the write is a
    conditional UPDATE on (capability revision, assessment execution id).
    Exactly one row must change; zero means another writer got there first, so
    the approval is refused and the newer content is left untouched.
    """
    if db is None:
        raise CapabilityError(
            "unsupported_database",
            "Assessment approval requires a database session.",
            409,
        )
    fresh = _reload_canvas(db, canvas)
    content = copy.deepcopy(_canvas_content(fresh))
    record = content.get("assessment_review")
    if not isinstance(record, dict) or not record:
        raise CapabilityError(
            "no_assessment", "There is no assessment on this canvas to approve.", 409)
    if str(record.get("execution_id")) != str(execution_id):
        raise CapabilityError(
            "stale_assessment",
            "The named assessment is not the current one; re-read and approve "
            "the current execution.",
            409,
            current_execution_id=record.get("execution_id"),
        )
    role = str(getattr(user, "role", "") or "").lower()
    if role not in _APPROVER_ROLES:
        raise CapabilityError(
            "approval_forbidden",
            "Only a workspace admin or owner can approve an assessment.",
            403,
        )

    state = assessment_authorization(fresh, db=db)
    if state.get("state") == "content_drift":
        raise CapabilityError(
            "assessment_content_changed",
            "The assessment content changed after it was recorded; run a fresh "
            "assessment before approving.",
            409,
        )
    if state.get("state") == "stale_assessment":
        raise CapabilityError(
            "stale_assessment",
            "The canvas, source or policy changed since this assessment; run a "
            "fresh assessment before approving.",
            409,
        )
    if state.get("state") == "no_assessment":
        raise CapabilityError(
            "no_assessment", "There is no assessment on this canvas to approve.", 409)

    artifact = record.get("assessments") or []
    digest = _assessment_digest(artifact)
    if state.get("state") == "authorized" and state.get("approval"):
        # Already approved for this exact binding: do NOT create a second
        # transition. Two simultaneous approvals converge on one record.
        return {
            "success": True,
            "canvas_id": fresh.id,
            "authorization": state,
            "idempotent": True,
        }
    if not record.get("review_required"):
        return {
            "success": True,
            "canvas_id": fresh.id,
            "authorization": assessment_authorization(fresh, db=db),
        }
    observed_revision = record.get("canvas_revision")
    observed_assessment_revision = record.get("assessment_revision")
    approval = {
        **_assessment_binding(record, digest),
        "approved_by": str(getattr(user, "id", "") or ""),
        "approved_role": role,
        "approved_at": _now().isoformat(),
    }
    record["authorization"] = approval
    # The approval itself is a relevant write: advance the concurrency token.
    record["assessment_revision"] = int(observed_assessment_revision or 0) + 1
    content["assessment_review"] = record
    audit_payload = {
        **{key: approval.get(key) for key in (
            "execution_id", "execution_fingerprint", "source_revision",
            "policy_revision", "manifest_revision", "canvas_revision",
            "assessment_content_sha256")},
        "unresolved_subjects": [
            item["subject_id"] for item in artifact
            if item.get("unresolved_requirements")
        ],
        "content": content,
    }
    _audit(db, fresh, user, "capability_assessment_approved", audit_payload)

    written = _cas_update_assessment_content(
        db, fresh,
        observed_revision=observed_revision,
        execution_id=str(record.get("execution_id")),
        observed_assessment_revision=observed_assessment_revision,
        new_content=content,
    )
    if not written:
        # Another writer changed the canvas (or the assessment) after our
        # validation. Keep their work: roll back and refuse.
        db.rollback()
        raise CapabilityError(
            "assessment_conflict",
            "The canvas changed while the approval was being recorded; reload "
            "and review the current assessment before approving.",
            409,
        )
    db.commit()
    db.expire(fresh)
    return {
        "success": True,
        "canvas_id": fresh.id,
        "authorization": assessment_authorization(fresh, db=db),
    }


def decisions_operation(canvas: Canvas, db=None, user: Any = None) -> Dict[str, Any]:
    """Downstream consumer: decisions derived from the authorized artifact.

    Re-reads the authoritative row and revalidates the recomputed digest, the
    revision and the policy/source binding before returning anything. There is
    no separate decision map: the decisions ARE the reviewed artifact.
    """
    fresh = _reload_canvas(db, canvas) if db is not None else canvas
    record = _canvas_content(fresh).get("assessment_review")
    if not isinstance(record, dict) or not record:
        raise CapabilityError(
            "no_assessment", "There is no assessment on this canvas.", 409)
    authority = (record.get("authority") or {})
    if user is not None:
        caller = str(getattr(user, "id", "") or "")
        owner = str(authority.get("owner_id") or "")
        if owner and caller != owner:
            raise CapabilityError(
                "authority_mismatch",
                "This assessment belongs to a different owner.",
                403,
                owner_id=owner,
            )
    authorization = assessment_authorization(fresh, db=db)
    if authorization.get("state") != "authorized":
        raise CapabilityError(
            "review_required",
            "This assessment has not been authorized for downstream use.",
            409,
            authorization=authorization,
        )
    artifact = _canonical_assessment_artifact(record.get("assessments") or [])
    return {
        "success": True,
        "operation": "decisions",
        "canvas_id": fresh.id,
        "execution_id": record.get("execution_id"),
        "execution_fingerprint": record.get("execution_fingerprint"),
        "source_revision": record.get("source_revision"),
        "policy_revision": record.get("policy_revision"),
        "manifest_revision": record.get("manifest_revision"),
        "canvas_revision": record.get("canvas_revision"),
        "assessment_content_sha256": authorization.get("binding", {}).get(
            "assessment_content_sha256"),
        "decisions": {
            item["subject_id"]: item["decision"] for item in artifact
        },
        "assessments": artifact,
        "authorization": authorization,
    }


def export_operation(db, canvas: Canvas, user: Any) -> Dict[str, Any]:
    import openpyxl
    from core.office_service import _validate_office_path

    manifest = _require_effective(canvas, "export")
    _require_approval(canvas, manifest, "export", user)
    _assert_bound_source_access(db, canvas, user)
    outputs = manifest.get("outputs") or ["xlsx"]
    if "xlsx" not in outputs:
        raise CapabilityError("unsupported_output", "Only xlsx export is declared.")
    dataset = get_dataset(canvas)
    columns = list(dataset.get("columns") or [])
    rows = dataset.get("rows") or []
    source = _dataset_source(canvas)
    binding = manifest.get("teaching_binding") or {}
    teaching = {}
    if binding.get("agent_id"):
        from core.artifact_teaching import resolve_artifact_teaching

        teaching = resolve_artifact_teaching(
            db, str(binding.get("agent_id")), "spreadsheet",
            goal_id=str(binding.get("goal_id") or "") or None,
            task_context=dict(manifest.get("teaching_context") or {}),
            workspace_id=str(canvas.workspace_id or "") or None,
        )
        if teaching.get("status") in {"needs_context", "conflict"}:
            raise CapabilityError(
                "teaching_context_unresolved",
                teaching.get("explanation")
                or "Spreadsheet teaching context needs confirmation.",
                409,
                teaching=teaching,
            )
        spec = teaching.get("spec") or {}
        wanted = [str(item) for item in (spec.get("table_columns") or [])]
        if wanted:
            normalized = {
                " ".join(str(column).lower().split()): column
                for column in columns
            }
            missing = [item for item in wanted
                       if " ".join(item.lower().split()) not in normalized]
            if missing:
                raise CapabilityError(
                    "unsupported_formatting",
                    f"Required spreadsheet columns are missing: {', '.join(missing)}",
                    409,
                    teaching=teaching,
                )
            ordered = [normalized[" ".join(item.lower().split())] for item in wanted]
            ordered += [column for column in columns if column not in ordered]
            indexes = [columns.index(column) for column in ordered]
            columns = ordered
            rows = [
                [row[index] if index < len(row) else None for index in indexes]
                for row in rows
            ]
    office_dir = Path(os.getenv("ATOM_OFFICE_DIR", os.path.join("data", "office"))).resolve()
    office_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in canvas.name)[:50] or "canvas"
    target = _validate_office_path(str(office_dir / f"{safe}-{canvas.id[:8]}.xlsx"))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(columns)
    measure_field = str((manifest.get("data_binding") or {}).get("measure_field") or "")
    numeric_fields = {measure_field} if measure_field else set()
    import re as _re
    for row in rows:
        ws.append(list(row))
        excel_row = ws.max_row
        for idx, column in enumerate(columns, start=1):
            cell = ws.cell(row=excel_row, column=idx)
            value = cell.value
            if isinstance(value, str) and value.startswith("="):
                # Data is data: never let a bound cell become a live formula.
                cell.value = value
                cell.data_type = "s"
                continue
            if column in numeric_fields and isinstance(value, str):
                text = value.strip().replace(",", "")
                if _re.fullmatch(r"-?\d+", text):
                    cell.value = int(text)
                elif _re.fullmatch(r"-?\d*\.\d+", text):
                    cell.value = float(text)
    spreadsheet_spec = (teaching or {}).get("spec") or {}
    if spreadsheet_spec:
        from openpyxl.styles import Font

        font_name = str(spreadsheet_spec.get("font_name") or "")
        font_size = spreadsheet_spec.get("font_size")
        header_bold = bool(spreadsheet_spec.get("header_bold", True))
        for row_cells in ws.iter_rows():
            for cell in row_cells:
                if font_name or font_size or (
                        header_bold and cell.row == 1):
                    cell.font = Font(
                        name=font_name or cell.font.name,
                        size=float(font_size or cell.font.sz or 11),
                        bold=header_bold if cell.row == 1 else cell.font.bold,
                    )
        if spreadsheet_spec.get("freeze_header"):
            ws.freeze_panes = "A2"
    meta = wb.create_sheet("Provenance")
    meta.append(["canvas_id", canvas.id])
    meta.append(["source_resource_id", source.get("resource_id")])
    meta.append(["source_file", source.get("file_name")])
    meta.append(["source_version", source.get("source_version")])
    meta.append(["manifest_revision", manifest.get("manifest_revision")])
    meta.append(["policy_revision", policy_revision(manifest)])
    meta.append(["exported_at", _now().isoformat()])
    wb.save(target)
    content = _canvas_content(canvas)
    exports = [str(p) for p in (content.get("capability_exports") or [])]
    if str(target) not in exports:
        exports.append(str(target))
    content["capability_exports"] = exports[-10:]
    canvas.content = content
    _audit(db, canvas, user, "capability_export", {
        "artifact": target,
        "source_version": source.get("source_version"),
        "rows": len(rows),
        "teaching": teaching,
    })
    db.commit()
    return {
        "success": True,
        "operation": "export",
        "canvas_id": canvas.id,
        "artifact": {
            "file_path": target,
            "file_name": Path(target).name,
            "format": "xlsx",
            "rows": len(rows),
            "columns": columns,
            "sha256": hashlib.sha256(Path(target).read_bytes()).hexdigest(),
        },
        "source": source,
        "manifest_revision": manifest.get("manifest_revision"),
        "teaching": teaching,
        "download_url": f"/api/v1/office/download?file_path={target}&canvas_id={canvas.id}",
    }
