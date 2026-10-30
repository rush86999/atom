"""Server-side resource and output resolution for assignments.

A public proposal names catalog references, not filesystem paths. The server
resolves the reference inside the authenticated workspace, checks the active
grant, source version and materialization coverage, and returns a TYPED
binding plus the authoritative local path for the read adapter.

The binding is carried through the plan without the path. A path resolved at
start is not continuing access: every read re-resolves the binding, so a
revoked grant or a superseded source version stops the read.

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
from typing import Any, Dict, List, Optional, Tuple

from core.assignment_plan import canonical_sha256


class AssignmentResourceError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 400,
                 candidates: Optional[List[Dict[str, Any]]] = None):
        self.code = code
        self.status = status
        self.candidates = list(candidates or [])
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


def _effective_workspace(user: Any) -> str:
    return str(getattr(user, "workspace_id", "") or "default").strip()


def _effective_tenant(user: Any) -> str:
    return str(getattr(user, "tenant_id", "") or "default").strip()


def _access_scope(user: Any) -> Dict[str, Any]:
    return {
        "user_id": str(getattr(user, "id", "") or ""),
        "workspace_id": _effective_workspace(user),
        "tenant_id": _effective_tenant(user),
    }


def _parquet_schema(path: Path) -> Tuple[List[str], List[str]]:
    """Physical columns and actual numeric columns, without reading rows.

    The materialized frame decides what a measure is. Header vocabulary is
    never used to invent one.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = pq.ParquetFile(str(path)).schema_arrow
        columns = [str(field.name) for field in schema]
        numeric = [
            str(field.name) for field in schema
            if str(field.name) != "__sheet_row"
            and (pa.types.is_integer(field.type)
                 or pa.types.is_floating(field.type)
                 or pa.types.is_decimal(field.type))
        ]
        return columns, numeric
    except Exception:  # noqa: BLE001 — corrupt copy is a read-time refusal
        return [], []


def _internal_source(reference: Dict[str, Any], user: Any) -> Dict[str, Any]:
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
    suffix = path.suffix.lower()
    kind = str(reference.get("kind") or "").lower()
    if not kind:
        kind = "workbook" if suffix in (".xlsx", ".xls") else "document"
    representation = "xlsx" if suffix in (".xlsx", ".xls", ".xlsm") else "file"
    return {
        "kind": kind,
        "representation": representation,
        "path": str(path),
        "resource_id": f"fixture:{path.name}",
        "source_version": _sha256_file(path),
        "dataset_name": None,
        "original_file_name": path.name,
        "columns": [],
        "numeric_columns": [],
        "row_count": None,
        "sheet": reference.get("sheet"),
        "coverage": {"known": True, "truncated": False,
                     "controlled_fixture": True},
        "access_scope": _access_scope(user),
        "workspace_id": _effective_workspace(user),
        "tenant_id": _effective_tenant(user),
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
        return _internal_source(reference, user)

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
    workspace_id = _effective_workspace(user)
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
            "resource and version.", status=409,
            candidates=list(resolution.get("candidates") or [])[:10])
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
    source_name = str(entry.get("source") or "").strip().lower()
    if source_name == "upload":
        # A local upload is authorized by its workspace/creator binding, not
        # by an OAuth token family. The catalog lookup above already enforced
        # the workspace scope; this extra check keeps a shared workspace from
        # binding another user's private upload.
        created_by = str(entry.get("created_by") or "")
        user_id = str(getattr(user, "id", "") or "")
        if created_by and created_by != user_id:
            raise AssignmentResourceError(
                "resource_workspace_mismatch",
                "That uploaded source belongs to a different user.",
                status=403,
            )
        coverage = _validate_connected_coverage(entry)
    else:
        try:
            _assert_connected_source_access(db, entry.get("source"), user)
            coverage = _validate_connected_coverage(entry)
        except CapabilityError as exc:
            raise AssignmentResourceError(
                exc.code, str(exc), status=exc.status_code)
    actual_version = str(entry.get("content_hash") or "")
    if expected_version and actual_version != expected_version:
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
    columns, numeric_columns = _parquet_schema(parquet_path)
    if not columns:
        raise AssignmentResourceError(
            "materialization_incomplete",
            "The materialized copy has no readable schema.", status=409)

    kind = str(reference.get("kind") or "").lower()
    if not kind:
        file_name = str(entry.get("file_name") or entry.get("dataset_name") or "")
        kind = "workbook" if file_name.lower().endswith(
            (".xlsx", ".xls", ".csv")) else "document"
    return {
        "kind": kind,
        "representation": "parquet_frame",
        "path": str(parquet_path),
        "resource_id": str(entry.get("id") or entry.get("dataset_name") or ""),
        "dataset_name": entry.get("dataset_name"),
        "external_id": entry.get("external_id"),
        "source": entry.get("source"),
        "source_kind": entry.get("source_kind"),
        "original_file_name": entry.get("file_name"),
        "columns": columns,
        "numeric_columns": numeric_columns,
        "row_count": int(entry.get("row_count") or 0),
        "sheet": entry.get("entity_name"),
        "source_version": actual_version,
        "coverage": coverage,
        "access_scope": _access_scope(user),
        "workspace_id": workspace_id,
        "tenant_id": _effective_tenant(user),
        "internal_fixture": False,
    }


_EXTENSIONS = {
    "document": ".docx",
    "spreadsheet": ".xlsx",
    "presentation": ".pptx",
    "email_draft": ".json",
}


def resource_binding(source: Dict[str, Any]) -> Dict[str, Any]:
    """The typed, path-free binding persisted with the plan."""
    return {
        "resource_id": source.get("resource_id"),
        "dataset_name": source.get("dataset_name"),
        "source": source.get("source"),
        "source_kind": source.get("source_kind"),
        "external_id": source.get("external_id"),
        "original_file_name": source.get("original_file_name"),
        "representation": source.get("representation"),
        "source_version": source.get("source_version"),
        "sheet": source.get("sheet"),
        "columns": list(source.get("columns") or [])[:200],
        "numeric_columns": list(source.get("numeric_columns") or [])[:100],
        "row_count": source.get("row_count"),
        "coverage": dict(source.get("coverage") or {}),
        "access_scope": dict(source.get("access_scope") or {}),
        "workspace_id": source.get("workspace_id"),
        "tenant_id": source.get("tenant_id"),
        "internal_fixture": bool(source.get("internal_fixture")),
    }


def recheck_resource_access(
    db,
    user: Any,
    binding: Dict[str, Any],
) -> Dict[str, Any]:
    """Re-resolve a binding immediately before a read or a resumed read.

    A path resolved earlier is never treated as a continuing grant. The
    catalog is asked again for the active version, the token store is asked
    again for the grant, and the access scope must still match this user.
    """
    binding = dict(binding or {})
    scope = dict(binding.get("access_scope") or {})
    user_id = str(getattr(user, "id", "") or "")
    if scope.get("user_id") and str(scope["user_id"]) != user_id:
        raise AssignmentResourceError(
            "resource_workspace_mismatch",
            "This resource binding belongs to a different authenticated "
            "principal.", status=403)
    for key in ("workspace_id", "tenant_id"):
        expected = str(scope.get(key) or binding.get(key) or "")
        actual = (
            _effective_workspace(user) if key == "workspace_id"
            else _effective_tenant(user)
        )
        if expected and expected != actual:
            raise AssignmentResourceError(
                "resource_workspace_mismatch",
                "This resource binding is outside the authenticated scope.",
                status=403)
    if binding.get("internal_fixture"):
        if os.getenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS") != "1":
            raise AssignmentResourceError(
                "filesystem_path_not_allowed",
                "The controlled fixture path is no longer enabled.", status=403)
        return dict(binding)
    reference = {
        "dataset_name": binding.get("dataset_name"),
        "source": binding.get("source"),
        "external_id": binding.get("external_id"),
        "sheet": binding.get("sheet"),
        "source_version": binding.get("source_version"),
        "kind": "workbook",
    }
    resolved = resolve_assignment_source(
        db, user, reference, allow_internal=False)
    if str(resolved.get("resource_id") or "") != str(
            binding.get("resource_id") or ""):
        raise AssignmentResourceError(
            "stale_source_version",
            "The active catalog entry changed since the plan was accepted.",
            status=409)
    if str(resolved.get("source_version") or "") != str(
            binding.get("source_version") or ""):
        raise AssignmentResourceError(
            "stale_source_version",
            "The active source version changed since the plan was accepted.",
            status=409)
    if str(resolved.get("sheet") or "") != str(binding.get("sheet") or ""):
        raise AssignmentResourceError(
            "stale_source_version",
            "The bound sheet is no longer the active catalog entry.",
            status=409)
    return resolved


def _normalize_name(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def select_resource_candidates(
    entries,
    *,
    objective: str = "",
    scope_query: str = "",
    explicit_sheet: Optional[str] = None,
    required_count: int = 1,
) -> List[Dict[str, Any]]:
    """Choose candidate catalog entries without adopting the first result.

    Order never establishes identity. A candidate must be active, and the
    choice uses the accepted objective/scope tokens, the actual schema and
    materialization coverage. Multiple equally plausible candidates are a
    clarification, not a pick; no justified candidate is explicit pending
    work, not the first row.
    """
    required_count = max(1, int(required_count or 1))
    rows = [dict(entry) for entry in (entries or [])
            if str(entry.get("status") or "active") == "active"]
    if explicit_sheet:
        wanted = _normalize_name(explicit_sheet)
        rows = [row for row in rows
                if _normalize_name(row.get("entity_name")) == wanted]
    if not rows:
        return []
    ignored = {
        "the", "and", "for", "with", "from", "this", "that", "prepare",
        "create", "using", "based", "into", "over", "under", "please",
        "make", "give", "show", "need", "want", "work", "report",
    }
    tokens = {
        token for token in re.findall(
            r"[a-z0-9]{3,}",
            (str(objective or "") + " " + str(scope_query or "")).lower())
        if token not in ignored
    }

    def haystack(entry: Dict[str, Any]) -> str:
        columns = entry.get("columns") or []
        return " ".join([
            str(entry.get("dataset_name") or ""),
            str(entry.get("file_name") or ""),
            str(entry.get("entity_name") or ""),
            str(entry.get("source") or ""),
            " ".join(str(column) for column in columns[:200]),
        ]).lower()

    def score(entry: Dict[str, Any]) -> int:
        hay = haystack(entry)
        value = sum(1 for token in tokens if token in hay)
        coverage = dict(entry.get("coverage") or {})
        if coverage.get("known") and coverage.get("truncated"):
            value -= 5
        return value

    for entry in rows:
        entry["_score"] = score(entry)
    rows.sort(key=lambda item: (-item["_score"],
                                str(item.get("dataset_name") or ""),
                                str(item.get("entity_name") or "")))
    best = int(rows[0]["_score"])
    if best <= 0:
        # Nothing in the objective/scope justifies this resource. Do not
        # adopt the first catalog row merely because it exists.
        return []

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in rows:
        identity = str(entry.get("file_name") or entry.get("dataset_name")
                       or entry.get("id") or "")
        grouped.setdefault(identity, []).append(entry)

    def group_top(group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        top_score = int(group[0]["_score"])
        return [item for item in group if int(item["_score"]) == top_score]

    if required_count == 1:
        top = [entry for entry in rows if int(entry["_score"]) == best]
        if len(top) == 1:
            return [{key: value for key, value in top[0].items()
                     if key != "_score"}]
        raise AssignmentResourceError(
            "ambiguous_resource",
            "Several authorized resources match the requested scope; name "
            "the exact resource or sheet.",
            status=409,
            candidates=[{key: value for key, value in entry.items()
                         if key != "_score"} for entry in top[:10]])

    selected: List[Dict[str, Any]] = []
    for identity in sorted(
            grouped,
            key=lambda key: -int(grouped[key][0]["_score"])):
        if len(selected) >= required_count:
            break
        group = grouped[identity]
        if int(group[0]["_score"]) <= 0:
            continue
        top = group_top(group)
        sheets = {_normalize_name(item.get("entity_name")) for item in top}
        if len(top) > 1 and len(sheets) > 1:
            raise AssignmentResourceError(
                "ambiguous_resource",
                f"Resource '{identity}' has several plausible sheets; name "
                "the exact sheet.",
                status=409,
                candidates=[{key: value for key, value in entry.items()
                             if key != "_score"} for entry in top[:10]])
        selected.append({key: value for key, value in top[0].items()
                         if key != "_score"})
    if len(selected) < required_count:
        raise AssignmentResourceError(
            "insufficient_resources",
            f"The request requires {required_count} authorized resources; "
            f"only {len(selected)} distinct resource(s) matched.",
            status=409)
    return selected


def derive_aggregate_spec(
    objective: str,
    sources: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Derive a deterministic aggregate from the objective and actual schema.

    This is not a model call and it never invents a measure. ``count`` is
    unambiguous. ``sum`` requires one named numeric column, or exactly one
    numeric column in the bound frame. Anything else is a clarification.
    """
    text = _normalize_name(objective)
    if not text:
        return None
    if re.search(r"\b(count|how many|number of)\b", text):
        return {"aggregate": {"operation": "count"}}
    if not re.search(r"\b(sum|total|add up|combined|aggregate)\b", text):
        return None
    if len(sources) != 1:
        raise AssignmentResourceError(
            "calculation_ambiguous",
            "A sum over several sources needs an explicit calculation.",
            status=409)
    numeric = [str(column) for column in
               (sources[0].get("numeric_columns") or [])]
    if not numeric:
        raise AssignmentResourceError(
            "calculation_ambiguous",
            "The bound source has no numeric column to sum.",
            status=409)
    objective_tokens = set(text.split())
    scored = []
    for column in numeric:
        normalized = _normalize_name(column)
        column_tokens = set(normalized.split())
        overlap = len(column_tokens & objective_tokens)
        if overlap:
            exact = 2 if normalized and normalized in text else 0
            scored.append((exact + overlap, exact, column))
    scored.sort(reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return {"aggregate": {"operation": "sum",
                              "value_column": scored[0][2]}}
    if len(numeric) == 1:
        return {"aggregate": {"operation": "sum",
                              "value_column": numeric[0]}}
    raise AssignmentResourceError(
        "calculation_ambiguous",
        "Several numeric columns could be summed; name the measure column.",
        status=409,
        candidates=[{"column": column} for column in numeric[:20]])


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
                or (Path(__file__).resolve().parents[1]
                    / "data" / "office" / "assignments")).resolve()
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
        resource_binding(item) for item in (sources or [])
    ])[:24]
