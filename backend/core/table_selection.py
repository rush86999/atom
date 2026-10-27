"""General table selection over a bound, materialized dataset.

This is the operation boundary the core workspace needs: "list these columns
for rows matching this condition" is a SELECTION, not an item lookup and not
an aggregate. Nothing here knows a business domain:

* which columns to return comes from the sheet's own headers named in the ask;
* the predicate comes from a header/value comparison or a recorded cell value;
* identifiers, row references and cells are read from the authoritative frame
  after the SQL has selected row identities only.

The SQL is validated with the same read-only rules as the aggregate lane.
The rendered table is built from the validated rows, so a model-written table
can never become the delivered factual result.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SHEET_ROW_COL = "__sheet_row"
MAX_SELECT_ROWS = 200

_SELECTION_VERB_RE = re.compile(
    r"\b(?:list|show|display|return|select|extract|give\s+me|pull|filter)\b",
    re.IGNORECASE,
)
_ROW_WORD_RE = re.compile(r"\b(?:rows?|records?|entries?|lines?)\b", re.IGNORECASE)
_FILTER_WORD_RE = re.compile(r"\b(?:for|where|with|whose)\b", re.IGNORECASE)
_COLUMN_WORD_RE = re.compile(r"\bcolumns?\b", re.IGNORECASE)
_CALC_WORD_RE = re.compile(
    r"\b(?:total|totals|subtotal|subtotals|sum|sums|count|counts|"
    r"how\s+many|aggregate|aggregates|calculate|calculation|average|mean|"
    r"median|min|max|minimum|maximum)\b",
    re.IGNORECASE,
)

_COMPARISON_OPS = [
    (">=", ">="), ("<=", "<="), ("!=", "!="), ("<>", "!="),
    ("=", "="), (">", ">"), ("<", "<"),
]
_COMPARISON_WORDS = [
    (r"\bat\s+least\b|\bgreater\s+than\s+or\s+equal\b|\bno\s+less\s+than\b", ">="),
    (r"\bat\s+most\b|\bless\s+than\s+or\s+equal\b|\bno\s+more\s+than\b", "<="),
    (r"\bgreater\s+than\b|\bmore\s+than\b|\bover\b|\babove\b|\bexceeds?\b", ">"),
    (r"\bless\s+than\b|\bunder\b|\bbelow\b", "<"),
    (r"\bnot\s+equal\s+to\b|\bother\s+than\b", "!="),
    (r"\bequals?\b|\bis\b|\bare\b", "="),
]


def normalize(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _column_aliases(column: str) -> List[str]:
    base = normalize(column)
    aliases = [base]
    if base.endswith("s") and len(base) > 3:
        aliases.append(base[:-1])
    return [a for i, a in enumerate(aliases) if a and a not in aliases[:i]]


def _mentioned_columns(columns: Sequence[str], message: str) -> List[str]:
    """Columns in the order the ask names them (not sheet or name length)."""
    normalized = normalize(message)
    found: List[Tuple[int, int, str]] = []
    for column in columns:
        best: Optional[Tuple[int, int]] = None
        for alias in _column_aliases(column):
            index = normalized.find(f" {alias} ")
            if index >= 0:
                candidate = (index, -len(alias))
                if best is None or candidate < best:
                    best = candidate
        if best is not None:
            found.append((best[0], best[1], column))
    found.sort(key=lambda item: (item[0], item[1]))
    out: List[str] = []
    for _, _, column in found:
        if column not in out:
            out.append(column)
    return out


def is_table_selection_request(message: str) -> bool:
    """A list/show of columns or rows, with an optional row condition.

    Deliberately generic: no field names, values or business vocabulary.
    Aggregates ("total", "count") are handled by their own operation first.
    """
    text = " ".join(str(message or "").split())
    if not text or not _SELECTION_VERB_RE.search(text):
        return False
    # A calculation ask owns the turn; selection is the non-calculating
    # list/show of columns or rows.
    if _CALC_WORD_RE.search(text):
        return False
    # "list the prices for U-22" is an item lookup, not a table selection:
    # a row/record word or an explicit "columns" is required.
    # A row/record/column word is what distinguishes "list the approved
    # rows" from an item lookup ("show ticket HD-88") or a price ask.
    return bool(_ROW_WORD_RE.search(text) or _COLUMN_WORD_RE.search(text))


def _cell_value_candidates(
    df: Any, columns: Sequence[str], message: str,
) -> List[Tuple[str, str]]:
    """Recorded values that appear in the ask, with their header.

    A predicate value is evidence from the bound frame, not a vocabulary:
    "Submitted" is found because the Stage column actually contains it.
    """
    normalized = normalize(message)
    out: List[Tuple[str, str]] = []
    for column in columns:
        if column not in df.columns:
            continue
        try:
            values = df[column].dropna().astype(object).unique().tolist()
        except Exception:  # noqa: BLE001 — best effort
            continue
        for value in values[:200]:
            text = str(value).strip()
            if len(text) < 2 or text.lower() in {"none", "null", "nan"}:
                continue
            if _contains_phrase(normalized, normalize(text)):
                out.append((column, text))
    return out


def _preferred_candidates(
    candidates: List[Tuple[str, str]], message: str,
) -> List[Tuple[str, str]]:
    """Prefer a value that follows for/where/with; keep the rest as fallback."""
    normalized = normalize(message)
    preferred: List[Tuple[str, str]] = []
    for column, value in candidates:
        val = normalize(value)
        match = re.search(
            rf"\b(?:for|where|with|whose)\b(?:\s+\w+){{0,4}}\s+{re.escape(val)}\b",
            normalized,
        )
        if match:
            preferred.append((column, value))
    return preferred or candidates


def _comparison_predicate(
    columns: Sequence[str], message: str,
) -> Optional[Dict[str, Any]]:
    text = str(message or "")
    for column in sorted(columns, key=len, reverse=True):
        quoted = re.escape(column)
        # "Amount >= 10000", "Amount at least 10000", "Amount is 12000"
        for pattern, op in _COMPARISON_OPS:
            m = re.search(
                rf"(?<![A-Za-z0-9]){quoted}\s*{re.escape(pattern)}\s*"
                rf"(['\"]?)([^'\"\s,;]+)\1",
                text, re.IGNORECASE,
            )
            if m:
                return {"column": column, "operator": op,
                        "value": _coerce_value(m.group(2))}
        for word_re, op in _COMPARISON_WORDS:
            m = re.search(
                rf"(?<![A-Za-z0-9]){quoted}\s+(?:{word_re})\s+"
                rf"(['\"]?)([^'\"\s,;]+)\1",
                text, re.IGNORECASE,
            )
            if m:
                return {"column": column, "operator": op,
                        "value": _coerce_value(m.group(2))}
    return None


def _coerce_value(raw: str) -> Any:
    text = str(raw).strip()
    cleaned = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        if re.fullmatch(r"-?\d+", cleaned):
            return int(cleaned)
        if re.fullmatch(r"-?\d*\.\d+", cleaned):
            return float(cleaned)
    except Exception:  # noqa: BLE001
        pass
    return text


def resolve_selection(
    columns: Sequence[str], message: str, df: Any = None,
) -> Dict[str, Any]:
    """Resolve requested columns and an optional predicate from the ask.

    Returns ``{ok, columns, predicate, reason, candidates}``. Ambiguity is a
    clarification, never a silent choice.
    """
    physical = [c for c in columns if c != SHEET_ROW_COL]
    chosen = _mentioned_columns(physical, message)
    predicate = _comparison_predicate(physical, message)
    if predicate is not None and predicate["column"] not in chosen:
        # A comparison names its column explicitly; keep it out of the
        # output only when the user did not ask for it.
        pass
    if predicate is None and df is not None:
        candidates = _cell_value_candidates(df, physical, message)
        preferred = _preferred_candidates(candidates, message)
        # Drop candidates whose value is just a column name in the ask.
        named = {normalize(c) for c in chosen}
        preferred = [
            (c, v) for c, v in preferred
            if normalize(v) not in named and normalize(c) not in
            {normalize(v)}
        ]
        if preferred:
            by_column: Dict[str, List[str]] = {}
            for column, value in preferred:
                by_column.setdefault(column, []).append(value)
            if len(by_column) > 1:
                return {
                    "ok": False,
                    "reason": "ambiguous_predicate",
                    "columns": chosen,
                    "candidates": [
                        {"column": c, "value": v}
                        for c, v in preferred
                    ],
                }
            column, values = next(iter(by_column.items()))
            unique = list(dict.fromkeys(values))
            if len(unique) > 1:
                return {
                    "ok": False,
                    "reason": "ambiguous_value",
                    "columns": chosen,
                    "candidates": [
                        {"column": column, "value": v} for v in unique
                    ],
                }
            predicate = {"column": column, "operator": "=",
                         "value": unique[0]}
    if not chosen:
        # "list the rows where ..." — every physical column is the result.
        chosen = physical
    if not chosen:
        return {"ok": False, "reason": "no_columns", "columns": [],
                "candidates": []}
    return {"ok": True, "columns": chosen, "predicate": predicate,
            "reason": "", "candidates": []}


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _sql_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _select_sql(
    columns: Sequence[str], predicate: Optional[Dict[str, Any]],
) -> str:
    projected = ", ".join(_quote_ident(c) for c in columns)
    sql = f'SELECT {_quote_ident(SHEET_ROW_COL)}, {projected} FROM df'
    if predicate:
        sql += (
            f' WHERE {_quote_ident(predicate["column"])} '
            f'{predicate["operator"]} {_sql_literal(predicate["value"])}'
        )
    return sql


def select_rows(
    df: Any, columns: Sequence[str], predicate: Optional[Dict[str, Any]],
    *, max_rows: int = MAX_SELECT_ROWS,
) -> Dict[str, Any]:
    """Execute a read-only selection and read values from the bound frame."""
    import duckdb

    unknown = [c for c in columns if c not in df.columns]
    if unknown:
        return {"status": "error", "reason": "unknown_columns",
                "detail": unknown}
    if predicate and predicate["column"] not in df.columns:
        return {"status": "error", "reason": "unknown_predicate_column",
                "detail": predicate["column"]}
    sql = _select_sql(columns, predicate)
    # Reuse the aggregate lane's read-only SQL validation.
    try:
        from core.dataset_aggregation import (
            _validate_dataset_sql, _selection_sql_violation,
        )

        violation = (_validate_dataset_sql(sql)
                     or _selection_sql_violation(sql))
        if violation:
            return {"status": "error", "reason": "sql_rejected",
                    "detail": violation}
    except Exception as exc:  # noqa: BLE001 — validator is shared, not optional
        return {"status": "error", "reason": "sql_validation_unavailable",
                "detail": str(exc)}

    con = duckdb.connect()
    try:
        con.register("df", df)
        con.execute("SET enable_external_access=false")
        out = con.execute(
            f"SELECT * FROM ({sql}) AS _sel_rows LIMIT {max_rows + 1}"
        ).df()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "selection_failed",
                "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        con.close()

    if len(out) > max_rows:
        return {"status": "error", "reason": "processing_limit",
                "detail": f"more than {max_rows} rows"}

    authoritative = {}
    for record in df.to_dict(orient="records"):
        try:
            row_id = int(record.get(SHEET_ROW_COL))
        except (TypeError, ValueError):
            continue
        authoritative[row_id] = record

    rows: List[Dict[str, Any]] = []
    for raw in out.to_dict(orient="records"):
        try:
            row_id = int(raw.get(SHEET_ROW_COL))
        except (TypeError, ValueError):
            return {"status": "error", "reason": "row_provenance",
                    "detail": "selected row had no integer sheet row"}
        if row_id not in authoritative:
            return {"status": "error", "reason": "row_not_found",
                    "detail": f"row {row_id} not in bound frame"}
        cells = {}
        for column in columns:
            value = authoritative[row_id].get(column)
            if value is None or (isinstance(value, float) and value != value):
                value = None
            cells[column] = value
        rows.append({"row": row_id, "cells": cells})

    return {
        "status": "complete" if rows else "no_rows",
        "operation": "table_select",
        "columns": list(columns),
        "predicate": predicate,
        "rows": rows,
        "selected_count": len(rows),
        "source_row_count": len(df),
        "not_selected_count": max(len(df) - len(rows), 0),
        "sql": sql,
    }


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def render_selection(result: Dict[str, Any], source: Dict[str, Any]) -> str:
    """Render the validated rows. This is the delivered factual table."""
    columns = result.get("columns") or []
    rows = result.get("rows") or []
    sheet = source.get("sheet") or ""
    file_name = source.get("file_name") or ""
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(
        "---:" if any(
            isinstance(r["cells"].get(c), (int, float)) for r in rows
        ) else "---" for c in columns
    ) + " |"
    body = [
        "| " + " | ".join(_display(r["cells"].get(c)) for c in columns) + " |"
        for r in rows
    ]
    lines = [
        f"Selection: `{sheet}` in `{file_name}`",
        f"Rows: {result.get('selected_count', 0)} selected"
        + (f"; {result.get('not_selected_count', 0)} outside the filter"
           if result.get("predicate") else ""),
        "",
        header,
        divider,
        *body,
    ]
    if result.get("predicate"):
        p = result["predicate"]
        lines.append("")
        lines.append(
            f"Filter: {p['column']} {p['operator']} {_display(p['value'])}"
        )
    return "\n".join(lines)


def render_selection_block(result: Dict[str, Any], source: Dict[str, Any]) -> str:
    header = (
        "LIVE TOOL RESULTS (datasets.select — deterministic; the model did "
        "not choose these rows):"
    )
    return header + "\n" + render_selection(result, source)


def selection_receipt(
    result: Dict[str, Any], source: Dict[str, Any], *,
    delivered: bool,
) -> Dict[str, Any]:
    """The completion contract for a table selection.

    A valid receipt requires all five: bound source identity, resolved
    columns, the predicate (or an explicit no-predicate selection), row
    references from the authoritative frame, and delivery.
    """
    checks = {
        "source_bound": bool(
            source.get("file_name") and source.get("content_hash")),
        "columns_resolved": bool(result.get("columns")),
        "predicate_resolved": (
            result.get("predicate") is None
            or bool(result.get("predicate", {}).get("column"))
        ),
        "row_references": bool(
            isinstance(result.get("rows"), list)
            and all(isinstance(r.get("row"), int) for r in result["rows"])),
        "delivered": bool(delivered),
    }
    return {
        "operation": "table_select",
        "status": result.get("status"),
        "checks": checks,
        "ok": all(checks.values()) and result.get("status") == "complete",
        "selected_count": result.get("selected_count", 0),
        "columns": result.get("columns") or [],
        "predicate": result.get("predicate"),
        "row_references": [r.get("row") for r in result.get("rows") or []],
    }


def deliver_selection(
    result: Dict[str, Any], source: Dict[str, Any],
    model_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Deliver only the deterministic table.

    Model narration is kept in private diagnostics. It never becomes the
    user-facing factual result, even when it contradicts the validated rows.
    """
    receipt = selection_receipt(result, source, delivered=True)
    message = render_selection(result, source)
    rejected = None
    if model_text and str(model_text).strip():
        rejected = str(model_text)[:8000]
    return {
        "message": message,
        "block": render_selection_block(result, source),
        "receipt": receipt,
        "diagnostics": {"rejected_model_table": rejected},
        "ok": receipt["ok"],
    }


def selection_response_ok(message: str, data: Any) -> bool:
    """True when the response carries a valid selection for a selection ask.

    Non-selection turns are not governed by this contract. A lookup receipt,
    a model-written table, or a selection with no rows/pre-dicate does not
    satisfy it.
    """
    try:
        if not is_table_selection_request(message):
            return True
    except Exception:  # noqa: BLE001 — never block a non-selection turn
        return True
    record = data.get("table_selection") if isinstance(data, dict) else None
    if not isinstance(record, dict):
        return False
    return bool(
        record.get("status") == "complete"
        and record.get("columns")
        and isinstance(record.get("rows"), list)
        and record.get("rows")
        and isinstance(record.get("source"), dict)
        and record["source"].get("file_name")
        and record["source"].get("content_hash")
    )


def _choose_entry(
    entries: Sequence[Dict[str, Any]], query: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    import pandas as pd

    scored: List[Tuple[int, Dict[str, Any], Any]] = []
    for entry in entries:
        path = entry.get("parquet_path")
        if not path:
            continue
        try:
            df = pd.read_parquet(path)
        except Exception:  # noqa: BLE001
            continue
        columns = [str(c) for c in df.columns if str(c) != SHEET_ROW_COL]
        mentioned = _mentioned_columns(columns, query)
        score = len(mentioned)
        # A predicate value that exists in this entry adds confidence.
        candidates = _preferred_candidates(
            _cell_value_candidates(df, columns, query), query)
        if candidates:
            score += 1
        scored.append((score, entry, df))
    if not scored:
        return None, "no readable dataset entries"
    scored.sort(key=lambda item: -item[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, "several sheets could satisfy this selection"
    return scored[0][1], None


def select_named_dataset(
    entries: Sequence[Dict[str, Any]], query: str,
    *, file_name: Optional[str] = None, max_rows: int = MAX_SELECT_ROWS,
) -> Dict[str, Any]:
    """Resolve one bound sheet, select its rows, and render the table."""
    entry, error = _choose_entry(entries, query)
    if error or entry is None:
        return {"status": "clarification_required", "reason": error,
                "block": f"SELECTION NEEDS A BOUND SHEET\n{error}"}
    import pandas as pd

    df = pd.read_parquet(entry["parquet_path"])
    columns = [str(c) for c in df.columns if str(c) != SHEET_ROW_COL]
    resolved = resolve_selection(columns, query, df=df)
    if not resolved.get("ok"):
        candidates = resolved.get("candidates") or []
        lines = ["SELECTION NEEDS A CLARIFICATION",
                 f"Reason: {resolved.get('reason')}"]
        for candidate in candidates:
            lines.append(
                f"- {candidate.get('column')}: {candidate.get('value')}")
        return {
            "status": "clarification_required",
            "reason": resolved.get("reason"),
            "clarification": candidates,
            "block": "\n".join(lines),
        }
    result = select_rows(
        df, resolved["columns"], resolved["predicate"], max_rows=max_rows)
    source = {
        "file_name": entry.get("file_name") or file_name,
        "sheet": entry.get("entity_name"),
        "content_hash": entry.get("content_hash"),
        "resource_id": entry.get("content_hash"),
        "source_row_count": len(df),
        "ingested_at": entry.get("ingested_at"),
        "source_modified_at": entry.get("source_modified_at"),
        "source": entry.get("source"),
    }
    if result.get("status") in {"error", "no_rows"}:
        block = (
            "LIVE TOOL RESULTS (datasets.select — deterministic):\n"
            + str(result.get("reason") or result.get("status"))
        )
        return {"status": result.get("status"), "reason": result.get("reason"),
                "detail": result.get("detail"), "block": block,
                "source": source, "result": result}
    result["source"] = source
    result["block"] = render_selection_block(result, source)
    result["answer"] = render_selection(result, source)
    return result
