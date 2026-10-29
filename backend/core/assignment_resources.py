"""Server-side resource and output resolution for assignments.

A public proposal names catalog references, not filesystem paths. The server
resolves the reference inside the authenticated workspace, checks the active
grant, source version and materialization coverage, and returns the
authoritative local path for the read adapter.

An internal fixture path is available ONLY when
``ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=1`` and the path is under the configured
fixture root. It exists for controlled tests and is never accepted by an
unrestricted public proposal.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from core.assignment_plan import canonical_sha256


class AssignmentResourceError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 400):
        self.code = code
        self.status = status
        super().__init__(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_root() -> Path:
    return Path(os.getenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT")
                or tempfile.gettempdir()).resolve()


def _internal_source(reference: Dict[str, Any]) -> Dict[str, Any]:
    raw = str(reference.get("path") or reference.get("locator") or "").strip()
    if not raw:
        raise AssignmentResourceError(
            "resource_reference_required",
            "A source must name a catalog reference or an allowed fixture.")
    if os.getenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS") != "1":
        raise AssignmentResourceError(
            "filesystem_path_not_allowed",
            "Public proposals cannot supply filesystem paths; use an "
            "authorized catalog/resource reference.",
            status=422,
        )
    path = Path(raw).expanduser().resolve()
    root = _fixture_root()
    if path != root and root not in path.parents:
        raise AssignmentResourceError(
            "fixture_path_outside_scope",
            "The fixture path is outside the configured controlled root.",
            status=403,
        )
    if not path.is_file():
        raise AssignmentResourceError(
            "resource_not_found", "The fixture file does not exist.", status=404)
    kind = str(reference.get("kind") or "").lower()
    if not kind:
        kind = "workbook" if path.suffix.lower() in (".xlsx", ".xls") \
            else "document"
    return {
        "kind": kind,
        "path": str(path),
        "resource_id": f"fixture:{path.name}",
        "source_version": _sha256_file(path),
        "dataset_name": None,
        "sheet": reference.get("sheet"),
        "coverage": {"known": True, "truncated": False,
                     "controlled_fixture": True},
        "internal_fixture": True,
    }


def resolve_assignment_source(
    db,
    user: Any,
    reference: Dict[str, Any],
    *,
    allow_internal: bool = False,
) -> Dict[str, Any]:
    """Resolve one source reference through the existing connected binding."""
    reference = dict(reference or {})
    if reference.get("path") or reference.get("locator"):
        if not allow_internal:
            raise AssignmentResourceError(
                "filesystem_path_not_allowed",
                "Public proposals cannot supply filesystem paths; use an "
                "authorized catalog/resource reference.",
                status=422,
            )
        return _internal_source(reference)

    dataset_name = str(reference.get("dataset_name")
                       or reference.get("catalog_ref") or "").strip()
    source = str(reference.get("source") or "").strip()
    external_id = str(reference.get("external_id") or "").strip()
    sheet_name = str(reference.get("sheet") or "").strip()
    expected_version = str(reference.get("source_version") or "").strip()
    if not dataset_name and not (source and external_id):
        raise AssignmentResourceError(
            "resource_reference_required",
            "A source must name a dataset_name or (source, external_id).",
            status=422,
        )
    workspace_id = str(getattr(user, "workspace_id", "") or "").strip()
    if not workspace_id:
        raise AssignmentResourceError(
            "workspace_scope_required",
            "The authenticated principal has no workspace scope.", status=403)

    from core.sheet_dataset_service import (
        DatasetScopeError,
        connected_parquet_path,
        resolve_dataset_entry_scoped_sync,
    )
    from core.canvas_capability_service import (
        CapabilityError,
        _assert_connected_source_access,
        _validate_connected_coverage,
    )

    try:
        resolution = resolve_dataset_entry_scoped_sync(
            dataset_name or None,
            workspace_id=workspace_id,
            source=source or None,
            external_id=external_id or None,
            sheet_name=sheet_name or None,
        )
    except DatasetScopeError as exc:
        raise AssignmentResourceError(
            "workspace_scope_required", str(exc), status=403)
    state = resolution.get("state")
    if state == "workspace_mismatch":
        raise AssignmentResourceError(
            "resource_workspace_mismatch",
            "That resource belongs to a different workspace.", status=403)
    if state == "inactive":
        raise AssignmentResourceError(
            "stale_source_version",
            "The catalog entry is superseded or inactive.", status=409)
    if state == "ambiguous":
        raise AssignmentResourceError(
            "ambiguous_resource",
            "More than one active catalog version matches; name the exact "
            "resource and version.", status=409)
    if state != "active" or not resolution.get("entry"):
        raise AssignmentResourceError(
            "resource_not_found",
            "No active catalog entry matches that reference in this "
            "workspace.", status=404)

    entry = resolution["entry"]
    if str(entry.get("source_kind") or "") != "file":
        raise AssignmentResourceError(
            "unsupported_resource_kind",
            "Assignment sources require a file-backed catalog entry.",
            status=409)
    try:
        _assert_connected_source_access(db, entry.get("source"), user)
        coverage = _validate_connected_coverage(entry)
    except CapabilityError as exc:
        raise AssignmentResourceError(
            exc.code, str(exc), status=exc.status_code)
    actual_version = str(entry.get("content_hash") or "")
    if expected_version and not (
        actual_version == expected_version
        or actual_version.startswith(expected_version)
    ):
        raise AssignmentResourceError(
            "stale_source_version",
            f"Requested version '{expected_version}' is not the active "
            f"version '{actual_version[:12]}'.", status=409)
    parquet_path = connected_parquet_path(entry)
    if parquet_path is None or not parquet_path.exists():
        raise AssignmentResourceError(
            "materialization_incomplete",
            "The catalog entry points outside the dataset store or its "
            "materialized copy is missing.", status=409)

    kind = str(reference.get("kind") or "").lower()
    if not kind:
        file_name = str(entry.get("file_name") or entry.get("dataset_name") or "")
        kind = "workbook" if file_name.lower().endswith(
            (".xlsx", ".xls", ".csv")) else "document"
    return {
        "kind": kind,
        "path": str(parquet_path),
        "resource_id": str(entry.get("id") or entry.get("dataset_name") or ""),
        "dataset_name": entry.get("dataset_name"),
        "external_id": entry.get("external_id"),
        "source": entry.get("source"),
        "sheet": entry.get("entity_name"),
        "source_version": actual_version,
        "coverage": coverage,
        "internal_fixture": False,
    }


_EXTENSIONS = {
    "document": ".docx",
    "spreadsheet": ".xlsx",
    "presentation": ".pptx",
    "email_draft": ".json",
}


def allocate_output_path(
    user: Any,
    *,
    kind: str,
    title: str,
    assignment_id: str,
) -> str:
    """Allocate an owned output path; the client never names a path."""
    root = Path(os.getenv("ATOM_ASSIGNMENT_OUTPUT_DIR")
                or os.getenv("ATOM_OFFICE_DIR")
                or (Path(tempfile.gettempdir()) / "atom-assignment-outputs"))
    workspace = re.sub(r"[^A-Za-z0-9_.-]+", "_",
                       str(getattr(user, "workspace_id", "") or "default"))[:60]
    user_id = re.sub(r"[^A-Za-z0-9_.-]+", "_",
                     str(getattr(user, "id", "") or "user"))[:60]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(title or kind).lower()).strip("-")
    slug = (slug or kind)[:60]
    extension = _EXTENSIONS.get(str(kind).lower(), ".bin")
    directory = (root / workspace / user_id / assignment_id).resolve()
    root_resolved = root.resolve()
    if directory != root_resolved and root_resolved not in directory.parents:
        raise AssignmentResourceError(
            "output_scope_violation",
            "Allocated output escaped the artifact store.", status=500)
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f"{slug}-{uuid.uuid4().hex[:8]}{extension}")


def source_fingerprint(sources) -> str:
    return canonical_sha256([
        {
            "resource_id": item.get("resource_id"),
            "source_version": item.get("source_version"),
            "dataset_name": item.get("dataset_name"),
        }
        for item in sources or []
    ])[:24]
