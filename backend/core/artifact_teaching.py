"""Artifact-specific teaching derived from the existing lesson journal.

Formatting is not a second training system: lessons still live in
``AgentRegistry.configuration.learning.log`` with the same ids, revision and
global/goal scope. This module adds optional ``applies_to``, ``format_spec``
and ``conditions`` fields to those entries and resolves them for an output
type. The renderers apply the resolved spec deterministically and report
unsupported or missing requirements instead of silently approximating them.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

OUTPUT_TYPES = {"email", "document", "presentation", "spreadsheet"}

# Context keys are intentionally open-ended: these are examples the task may
# declare, not a fixed business taxonomy. The evaluator compares whatever the
# lesson requires against whatever the task supplies.
_CONTEXT_RESERVED = {
    "exceptions", "effective_from", "effective_to", "replaces",
    "field_mappings",
}

_FORMAT_SCHEMA: Dict[str, Dict[str, Any]] = {
    "document": {
        "font_name": "str",
        "font_size": "int:8:32",
        "line_spacing": "float:1.0:2.5",
        "heading_order": "list",
        "table_columns": "list",
        "prohibited_terms": "list",
    },
    "email": {
        "greeting": "str",
        "signature": "str",
        "subject_prefix": "str",
        "prohibited_terms": "list",
    },
    "presentation": {
        "font_name": "str",
        "font_size": "int:8:32",
        "slide_order": "list",
        "table_columns": "list",
        "prohibited_terms": "list",
    },
    "spreadsheet": {
        "font_name": "str",
        "font_size": "int:8:32",
        "header_bold": "bool",
        "freeze_header": "bool",
        "table_columns": "list",
    },
}


def _clean_list(value: Any, limit: int = 20) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: List[str] = []
    for item in value:
        text = " ".join(str(item or "").split())
        if text and text not in out:
            out.append(text[:120])
    return out[:limit]


def _clean_conditions(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for key in ("recipient", "task_scope"):
        value = " ".join(str(raw.get(key) or "").split())
        if value:
            out[key] = value[:200]
    return out


def normalize_artifact_teaching(
    applies_to: Optional[Sequence[str]],
    format_spec: Any,
    conditions: Any = None,
) -> Dict[str, Any]:
    """Validate one lesson's artifact fields. Never invents a value."""
    outputs = [str(item).strip().lower() for item in (applies_to or [])
               if str(item or "").strip()]
    outputs = [item for item in dict.fromkeys(outputs) if item in OUTPUT_TYPES]
    if not isinstance(format_spec, dict) or not format_spec:
        return {
            "applies_to": outputs,
            "format_spec": {},
            "conditions": _clean_conditions(conditions),
            "unsupported": [],
            "errors": ["format_spec is required"],
        }
    if len(outputs) != 1:
        return {
            "applies_to": outputs,
            "format_spec": {},
            "conditions": _clean_conditions(conditions),
            "unsupported": [],
            "errors": ["format_spec requires exactly one applies_to output"],
        }
    output_type = outputs[0]
    schema = _FORMAT_SCHEMA[output_type]
    clean: Dict[str, Any] = {}
    unsupported: List[str] = []
    errors: List[str] = []
    for key, value in format_spec.items():
        spec = schema.get(str(key))
        if spec is None:
            unsupported.append(str(key))
            continue
        try:
            if spec == "str":
                text = " ".join(str(value or "").split())
                if not text:
                    errors.append(f"{key} must be non-empty")
                else:
                    clean[key] = text[:2000]
            elif spec == "bool":
                clean[key] = bool(value)
            elif spec == "list":
                clean[key] = _clean_list(value)
            elif spec.startswith("int:") or spec.startswith("float:"):
                kind, low, high = spec.split(":")
                number = int(value) if kind == "int" else float(value)
                if number < float(low) or number > float(high):
                    errors.append(f"{key} out of range {low}..{high}")
                else:
                    clean[key] = number
        except (TypeError, ValueError):
            errors.append(f"{key} has the wrong type")
    return {
        "applies_to": outputs,
        "format_spec": clean,
        "conditions": _clean_conditions(conditions),
        "unsupported": unsupported,
        "errors": errors,
    }


def _condition_matches(
    conditions: Dict[str, str], *, recipient: Optional[str],
    task_scope: Optional[str],
) -> bool:
    if not conditions:
        return True
    if conditions.get("recipient"):
        want = conditions["recipient"].strip().lower()
        have = str(recipient or "").strip().lower()
        if not have:
            return False
        if want.startswith("@"):
            if not have.endswith(want):
                return False
        elif have != want:
            return False
    if conditions.get("task_scope"):
        if str(task_scope or "").strip() != conditions["task_scope"]:
            return False
    return True


def normalize_lesson_context(raw: Any) -> Dict[str, Any]:
    """Validate a generic context map without inventing business dimensions."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in list(raw.items())[:24]:
        name = str(key or "").strip()[:80]
        if not name:
            continue
        if name == "exceptions":
            if isinstance(value, dict):
                out[name] = {
                    str(k).strip()[:80]: _context_scalar(v)
                    for k, v in list(value.items())[:12]
                    if str(k or "").strip()
                }
            continue
        if name in {"effective_from", "effective_to"}:
            text = str(value or "").strip()
            if text:
                out[name] = text[:40]
            continue
        if name == "replaces":
            out[name] = _clean_list(value)
            continue
        if name == "field_mappings":
            rows = []
            for item in (value or [])[:24]:
                if not isinstance(item, dict):
                    continue
                concept = str(item.get("concept") or "").strip()[:80]
                column = str(item.get("column") or "").strip()[:120]
                if not concept or not column:
                    continue
                row = {
                    "concept": concept,
                    "sheet": str(item.get("sheet") or "").strip()[:120],
                    "column": column,
                    "unit": str(item.get("unit") or "").strip()[:40],
                    "source_version": str(
                        item.get("source_version") or "").strip()[:80],
                    "revision": int(item.get("revision") or 1),
                }
                unit_authority = str(
                    item.get("unit_authority") or "").strip()[:40]
                if unit_authority:
                    row["unit_authority"] = unit_authority
                for field, limit in (
                    ("required_unit", 40),
                    ("source_unit", 40),
                    ("source_unit_column", 120),
                ):
                    value_text = str(item.get(field) or "").strip()[:limit]
                    if value_text:
                        row[field] = value_text
                rows.append(row)
            if rows:
                out[name] = rows
            continue
        if isinstance(value, (list, tuple)):
            cleaned = [_context_scalar(item) for item in value[:12]]
            out[name] = [item for item in cleaned if item]
        else:
            scalar = _context_scalar(value)
            if scalar:
                out[name] = scalar
    return out


def _context_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return " ".join(str(value).split())[:200]


def _context_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        actual_values = actual if isinstance(actual, list) else [actual]
        return any(
            _context_matches(item, candidate)
            for item in expected for candidate in actual_values
        )
    if isinstance(actual, list):
        return any(_context_matches(expected, candidate) for candidate in actual)
    return _context_scalar(expected).lower() == _context_scalar(actual).lower()


def evaluate_lesson_context(
    lesson_context: Any,
    task_context: Any,
    *,
    workspace_id: Optional[str] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate applicability against declared task context.

    Similarity is the caller's retrieval step; this function is the authority
    check. Missing required context is a clarification, a conflicting value is
    not applicable, and a matching exception excludes the general lesson.
    """
    lesson = normalize_lesson_context(lesson_context)
    task = normalize_lesson_context(task_context)
    # The authenticated workspace is established context, not a missing
    # qualification. Add it to the task facts before comparing.
    if workspace_id and "workspace_id" not in task:
        task["workspace_id"] = _context_scalar(workspace_id)
    matched: Dict[str, str] = {}
    missing: List[str] = []
    conflicts: List[Dict[str, str]] = []
    excluded_by: List[str] = []
    if workspace_id:
        task_workspace = _context_scalar(workspace_id)
        required_workspace = lesson.get("workspace_id")
        if required_workspace and not _context_matches(
                required_workspace, task_workspace):
            return {
                "status": "not_applicable",
                "specificity": 0,
                "matched": {},
                "missing": [],
                "conflicts": [{
                    "key": "workspace_id",
                    "required": str(required_workspace),
                    "actual": task_workspace,
                }],
                "excluded_by": [],
                "reason": "workspace_boundary",
            }
    exceptions = lesson.get("exceptions") or {}
    for key, value in exceptions.items():
        if key in task and _context_matches(value, task[key]):
            excluded_by.append(key)
    if excluded_by:
        return {
            "status": "not_applicable",
            "specificity": 0,
            "matched": {},
            "missing": [],
            "conflicts": [],
            "excluded_by": excluded_by,
            "reason": "explicit_exception",
        }
    now_text = str(now or "")[:40]
    if now_text:
        effective_from = lesson.get("effective_from")
        effective_to = lesson.get("effective_to")
        if effective_from and now_text < effective_from:
            return {
                "status": "not_applicable", "specificity": 0,
                "matched": {}, "missing": [], "conflicts": [],
                "excluded_by": [], "reason": "not_yet_effective",
            }
        if effective_to and now_text > effective_to:
            return {
                "status": "not_applicable", "specificity": 0,
                "matched": {}, "missing": [], "conflicts": [],
                "excluded_by": [], "reason": "expired",
            }
    for key, expected in lesson.items():
        if key in _CONTEXT_RESERVED:
            continue
        if key == "workspace_id" and workspace_id:
            continue
        if key not in task:
            missing.append(key)
            continue
        if not _context_matches(expected, task[key]):
            conflicts.append({
                "key": key,
                "required": _context_scalar(expected),
                "actual": _context_scalar(task[key]),
            })
            continue
        matched[key] = _context_scalar(task[key])
    if conflicts:
        # A lesson whose required context has a DIFFERENT established value
        # does not govern this task. Save `conflict` for equally applicable
        # instructions that disagree with each other.
        return {
            "status": "not_applicable",
            "specificity": len(matched),
            "matched": matched,
            "missing": missing,
            "conflicts": conflicts,
            "excluded_by": [],
            "reason": "context_mismatch",
        }
    if missing:
        return {
            "status": "needs_context",
            "specificity": len(matched),
            "matched": matched,
            "missing": missing,
            "conflicts": [],
            "excluded_by": [],
            "reason": "missing_required_context",
        }
    return {
        "status": "applicable",
        "specificity": len(matched),
        "matched": matched,
        "missing": [],
        "conflicts": [],
        "excluded_by": [],
        "reason": "context_matched" if matched else "global_scope",
    }


def resolve_field_mapping(
    mappings: Sequence[Dict[str, Any]],
    schema: Sequence[Dict[str, Any]],
    *,
    source_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve confirmed concept→field mappings against the CURRENT schema.

    Exact sheet/column identity only. A mapping confirmed for one workbook or
    source version is not globally reusable; a missing/ambiguous/unit-changed
    mapping is needs_context, never a guessed first column.
    """
    columns = []
    for item in schema or []:
        if not isinstance(item, dict):
            continue
        column = str(item.get("column") or "").strip()
        if not column:
            continue
        columns.append({
            "sheet": str(item.get("sheet") or "").strip(),
            "column": column,
            "unit": str(item.get("unit") or "").strip(),
            "source_version": str(item.get("source_version") or "").strip(),
        })
    resolved: List[Dict[str, Any]] = []
    for mapping in mappings or []:
        if not isinstance(mapping, dict):
            continue
        concept = str(mapping.get("concept") or "").strip()
        column = str(mapping.get("column") or "").strip()
        sheet = str(mapping.get("sheet") or "").strip()
        unit = str(mapping.get("unit") or "").strip()
        mapped_version = str(mapping.get("source_version") or "").strip()
        record = {
            "concept": concept,
            "sheet": sheet,
            "column": column,
            "unit": unit,
            "revision": int(mapping.get("revision") or 1),
            "status": "needs_context",
            "reason": "",
            "matched": None,
        }
        if not concept or not column:
            record["reason"] = "mapping_incomplete"
            resolved.append(record)
            continue
        if (
            source_version and mapped_version
            and str(source_version) != mapped_version
        ):
            record["status"] = "not_applicable"
            record["reason"] = "stale_source_version"
            resolved.append(record)
            continue
        candidates = [
            item for item in columns
            if item["column"] == column
            and (not sheet or item["sheet"] == sheet)
        ]
        if not candidates:
            record["reason"] = "column_not_found"
            resolved.append(record)
            continue
        if len(candidates) > 1:
            record["status"] = "conflict"
            record["reason"] = "same_column_on_multiple_sheets"
            record["candidates"] = candidates[:10]
            resolved.append(record)
            continue
        match = candidates[0]
        if unit and match["unit"] and unit.lower() != match["unit"].lower():
            record["reason"] = "unit_changed"
            record["matched"] = match
            resolved.append(record)
            continue
        if unit and not match["unit"]:
            record["reason"] = "unit_unknown"
            record["matched"] = match
            resolved.append(record)
            continue
        record["status"] = "applicable"
        record["reason"] = "exact_schema_match"
        record["matched"] = match
        resolved.append(record)
    statuses = {item["status"] for item in resolved}
    if "conflict" in statuses:
        status = "conflict"
    elif "needs_context" in statuses:
        status = "needs_context"
    elif "not_applicable" in statuses and "applicable" not in statuses:
        status = "not_applicable"
    elif resolved:
        status = "applicable"
    else:
        status = "not_applicable"
    return {
        "status": status,
        "mappings": resolved,
        "source_version": source_version,
        "explanation": (
            "Concept mappings were resolved against the current schema."
            if status == "applicable"
            else "One or more concept mappings need confirmation or do not apply."
        ),
    }


def resolve_artifact_teaching(
    db: Any,
    agent_id: Optional[str],
    output_type: str,
    *,
    goal_id: Optional[str] = None,
    recipient: Optional[str] = None,
    task_scope: Optional[str] = None,
    task_context: Optional[Dict[str, Any]] = None,
    workspace_id: Optional[str] = None,
    now: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Merge applicable format lessons, newest first, for one output type."""
    output_type = str(output_type or "").strip().lower()
    if not agent_id or output_type not in OUTPUT_TYPES:
        return {"spec": {}, "sources": [], "revision": "", "unsupported": [],
                "errors": [], "output_type": output_type}
    from core.student_learning_service import get_agent_lessons

    lessons = get_agent_lessons(
        db, str(agent_id), query=None, limit=limit, goal_id=goal_id,
        include_workspace=False,
    )
    task = normalize_lesson_context(task_context or {})
    applicability: List[Dict[str, Any]] = []
    applicable: List[Tuple[int, Dict[str, Any], Dict[str, Any], List[str]]] = []
    clarifications: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    unsupported: List[str] = []
    errors: List[str] = []
    for entry in lessons:
        raw_spec = entry.get("format_spec")
        mappings_for_entry = (
            (entry.get("context") or {}).get("field_mappings") or []
        )
        if (not isinstance(raw_spec, dict) or not raw_spec) and not mappings_for_entry:
            continue
        raw_spec = raw_spec if isinstance(raw_spec, dict) else {}
        applies = [str(item).lower() for item in (entry.get("applies_to") or [])]
        if applies and output_type not in applies:
            continue
        if not _condition_matches(
            entry.get("conditions") or {}, recipient=recipient,
            task_scope=task_scope,
        ):
            continue
        lesson_context = dict(entry.get("context") or {})
        if entry.get("workspace_id") and "workspace_id" not in lesson_context:
            lesson_context["workspace_id"] = entry["workspace_id"]
        context_eval = evaluate_lesson_context(
            lesson_context, task,
            workspace_id=workspace_id, now=now,
        )
        record = {
            "lesson_id": entry.get("id"),
            "revision": entry.get("revision") or 1,
            "topic": entry.get("topic"),
            **context_eval,
        }
        applicability.append(record)
        if context_eval["status"] == "applicable":
            applicable.append((
                int(context_eval.get("specificity") or 0),
                entry, raw_spec, applies,
            ))
        elif context_eval["status"] == "needs_context" and context_eval.get("specificity"):
            clarifications.append(record)
        elif context_eval["status"] == "conflict":
            conflicts.append(record)

    # Explicit replacement relationships remove the replaced lesson before
    # specificity merging. Newest-wins is NOT used as a replacement rule.
    replaced_ids = set()
    for _specificity, entry, _raw_spec, _applies in applicable:
        replaced_ids.update(
            str(item) for item in
            ((entry.get("context") or {}).get("replaces") or [])
            if str(item)
        )
    if replaced_ids:
        applicable = [
            item for item in applicable if str(item[1].get("id")) not in replaced_ids
        ]
        for record in applicability:
            if str(record.get("lesson_id")) in replaced_ids:
                record["status"] = "not_applicable"
                record["reason"] = "explicitly_replaced"
                record["replaced_by"] = sorted(replaced_ids)

    # Higher-specificity scoped guidance overrides a general rule. At the SAME
    # specificity, differing values are a real conflict; recency is not used
    # to silently choose one.
    spec: Dict[str, Any] = {}
    selected: List[Dict[str, Any]] = []
    field_mappings: List[Dict[str, Any]] = []
    by_key: Dict[str, List[Tuple[int, Any, Dict[str, Any]]]] = {}
    for specificity, entry, raw_spec, applies in applicable:
        for key, value in raw_spec.items():
            by_key.setdefault(key, []).append((specificity, value, entry))
        selected.append({
            "id": entry.get("id"),
            "revision": entry.get("revision") or 1,
            "topic": entry.get("topic"),
            "applies_to": applies,
            "conditions": entry.get("conditions") or {},
            "context": dict(entry.get("context") or {}),
            "specificity": specificity,
        })
        for mapping in ((entry.get("context") or {}).get("field_mappings") or []):
            if not isinstance(mapping, dict):
                continue
            field_mappings.append({
                **dict(mapping),
                "lesson_id": entry.get("id"),
                "lesson_revision": entry.get("revision") or 1,
            })
        unsupported.extend(entry.get("unsupported_format_keys") or [])
        errors.extend(entry.get("format_errors") or [])
    for key, candidates in by_key.items():
        top = max(candidate[0] for candidate in candidates)
        top_values = [candidate for candidate in candidates if candidate[0] == top]
        distinct = {
            json.dumps(value, sort_keys=True, default=str)
            for _specificity, value, _entry in top_values
        }
        if len(distinct) > 1:
            conflicts.append({
                "lesson_id": None,
                "topic": None,
                "status": "conflict",
                "specificity": top,
                "matched": {},
                "missing": [],
                "conflicts": [{
                    "key": key,
                    "required": sorted(distinct)[0][:120],
                    "actual": sorted(distinct)[1][:120],
                }],
                "excluded_by": [],
                "reason": "equally_applicable_conflict",
            })
            continue
        spec[key] = top_values[0][1]
    if conflicts:
        status = "conflict"
    elif clarifications:
        status = "needs_context"
    elif spec or field_mappings:
        status = "applicable"
    else:
        status = "not_applicable"
    revision_payload = {
        "spec": spec,
        "sources": [
            [item.get("id"), item.get("revision"), item.get("context")]
            for item in selected
        ],
        "field_mappings": field_mappings,
        "matched_context": [
            item.get("matched") for item in applicability
            if item.get("status") == "applicable"
        ],
        "status": status,
    }
    revision = hashlib.sha256(
        json.dumps(revision_payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16] if (spec or field_mappings) else ""
    if status == "applicable":
        matched = sorted({
            f"{key}={value}"
            for item in selected for key, value in (item.get("context") or {}).items()
            if key not in _CONTEXT_RESERVED
        })
        explanation = (
            "Applied this instruction because these conditions match: "
            + (", ".join(matched) if matched else "the lesson is global scope")
            + "."
        )
    elif status == "needs_context":
        missing = sorted({
            key for item in clarifications for key in (item.get("missing") or [])
        })
        explanation = (
            "I need confirmation before applying this instruction: "
            + ", ".join(missing)
            + "."
        )
    elif status == "conflict":
        explanation = (
            "Applicable teachings conflict; I did not choose by recency. "
            "Confirm which scope governs."
        )
    else:
        explanation = "No applicable teaching was established for this context."
    return {
        "spec": spec,
        "sources": selected,
        "field_mappings": field_mappings,
        "revision": revision,
        "unsupported": sorted(set(unsupported)),
        "errors": sorted(set(errors)),
        "output_type": output_type,
        "status": status,
        "applicability": applicability,
        "clarifications": clarifications,
        "conflicts": conflicts,
        "explanation": explanation,
    }


def apply_email_teaching(
    content: Dict[str, Any], spec: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """Apply deterministic email protocol fields. Never sends."""
    out = dict(content or {})
    findings: List[Dict[str, str]] = []
    subject = str(out.get("subject") or "")
    prefix = str(spec.get("subject_prefix") or "").strip()
    if prefix and not subject.startswith(prefix):
        out["subject"] = f"{prefix} {subject}".strip()
    body = str(out.get("body") or "")
    # Preserve the body's format: HTML bodies get paragraph tags, plain-text
    # bodies (including the controlled outbox) stay readable text.
    is_html = bool(re.search(r"<[a-zA-Z][^>]*>", body))
    greeting = str(spec.get("greeting") or "").strip()
    if greeting and not body.lstrip().lower().startswith(greeting.lower()):
        body = (f"<p>{greeting}</p>" if is_html else f"{greeting}\n\n") + body
    signature = str(spec.get("signature") or "").strip()
    if signature and signature not in body:
        body = body.rstrip() + (
            f"<p>{signature}</p>" if is_html else f"\n\n{signature}")
    out["body"] = body
    out["draft_only"] = True
    out["send_performed"] = False
    out["teaching_revision"] = spec.get("_revision") or ""
    prohibited = [str(term) for term in (spec.get("prohibited_terms") or [])]
    for term in prohibited:
        if term and term.lower() in (subject + " " + body).lower():
            findings.append({
                "code": "prohibited_internal_information",
                "detail": term,
            })
    return out, findings


def _sections(markdown: str) -> Tuple[str, List[Tuple[str, List[str]]]]:
    lines = str(markdown or "").splitlines()
    preamble: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    current_title: Optional[str] = None
    current: List[str] = []
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and len(match.group(1)) >= 2:
            if current_title is not None:
                sections.append((current_title, current))
            else:
                preamble = current
            current_title = match.group(2).strip()
            current = [line]
        else:
            current.append(line)
    if current_title is not None:
        sections.append((current_title, current))
    else:
        preamble = lines
    return "\n".join(preamble).strip(), sections


def _normalize_heading(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def reorder_markdown_sections(
    markdown: str, heading_order: Sequence[str],
) -> Tuple[str, List[Dict[str, str]]]:
    wanted = [_normalize_heading(item) for item in (heading_order or []) if str(item).strip()]
    if not wanted:
        return str(markdown or ""), []
    preamble, sections = _sections(markdown)
    by_key = {_normalize_heading(title): (title, body) for title, body in sections}
    findings: List[Dict[str, str]] = []
    ordered: List[str] = []
    if preamble:
        ordered.append(preamble)
    used = set()
    for key in wanted:
        found = by_key.get(key)
        if found is None:
            findings.append({"code": "missing_required_section", "detail": key})
            continue
        used.add(key)
        ordered.append("\n".join(found[1]).strip())
    for key, (_title, body) in by_key.items():
        if key not in used:
            ordered.append("\n".join(body).strip())
    return "\n\n".join(item for item in ordered if item), findings


def _reorder_table_columns(
    markdown: str, columns: Sequence[str],
) -> Tuple[str, List[Dict[str, str]]]:
    wanted = [str(item).strip() for item in (columns or []) if str(item).strip()]
    if not wanted:
        return markdown, []
    lines = str(markdown or "").splitlines()
    findings: List[Dict[str, str]] = []
    out: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("|") and index + 1 < len(lines) and re.match(
            r"^\s*\|?\s*:?-{3,}", lines[index + 1]
        ):
            block = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index])
                index += 1
            header = [cell.strip() for cell in block[0].strip().strip("|").split("|")]
            normalized = {_normalize_heading(cell): i for i, cell in enumerate(header)}
            missing = [column for column in wanted
                       if _normalize_heading(column) not in normalized]
            if missing:
                findings.append({
                    "code": "missing_table_columns",
                    "detail": ", ".join(missing),
                })
                out.extend(block)
                continue
            order = [normalized[_normalize_heading(column)] for column in wanted]
            for row_line in block:
                cells = [cell.strip() for cell in row_line.strip().strip("|").split("|")]
                if len(cells) < len(header):
                    cells.extend([""] * (len(header) - len(cells)))
                out.append("| " + " | ".join(cells[i] for i in order) + " |")
            continue
        out.append(line)
        index += 1
    return "\n".join(out), findings


def apply_document_teaching(
    markdown: str, spec: Dict[str, Any],
) -> Tuple[str, List[Dict[str, str]]]:
    text, findings = reorder_markdown_sections(
        markdown, spec.get("heading_order") or [])
    text, table_findings = _reorder_table_columns(
        text, spec.get("table_columns") or [])
    findings.extend(table_findings)
    for term in spec.get("prohibited_terms") or []:
        if str(term).lower() in text.lower():
            findings.append({
                "code": "prohibited_internal_information",
                "detail": str(term),
            })
    return text, findings


def apply_presentation_teaching(
    markdown: str, spec: Dict[str, Any],
) -> Tuple[str, List[Dict[str, str]]]:
    order = [str(item).strip() for item in (spec.get("slide_order") or []) if str(item).strip()]
    text, findings = _reorder_table_columns(
        markdown, spec.get("table_columns") or [])
    if not order:
        return text, findings
    blocks = re.split(r"(?=^Slide\s+\d+\s*:)", text, flags=re.MULTILINE)
    preamble = ""
    slides = []
    for block in blocks:
        if not block.strip():
            continue
        match = re.match(r"^Slide\s+\d+\s*:\s*(.+)", block, re.MULTILINE)
        if match:
            slides.append((match.group(1).strip(), block.strip()))
        else:
            preamble = block.strip()
    by_title = {_normalize_heading(title): (title, block) for title, block in slides}
    ordered = []
    used = set()
    for title in order:
        key = _normalize_heading(title)
        found = by_title.get(key)
        if found is None:
            findings.append({"code": "missing_required_slide", "detail": title})
            continue
        used.add(key)
        ordered.append(found[1])
    for key, (_title, block) in by_title.items():
        if key not in used:
            ordered.append(block)
    renumbered = []
    for index, block in enumerate(ordered, start=1):
        renumbered.append(re.sub(
            r"^Slide\s+\d+\s*:", f"Slide {index}:", block,
            count=1, flags=re.MULTILINE,
        ))
    body = "\n\n".join(renumbered)
    return (preamble + "\n\n" + body).strip() if preamble else body, findings


def format_spec_summary(spec: Dict[str, Any]) -> str:
    parts = []
    for key in sorted(spec):
        value = spec[key]
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        parts.append(f"{key}={value}")
    return "; ".join(parts)
