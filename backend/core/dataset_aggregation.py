"""Deterministic row-selection/aggregation over materialized sheet datasets.

The existing sheet-dataset service already materializes each workbook sheet
into a Parquet frame and has an NL→SQL planner. This module adds the missing
*operation* layer for selection/aggregation requests:

1. bind the requested sheet explicitly (or report ambiguity);
2. ask the existing NL→SQL planner for a **detail-row** SELECT (never an
   aggregate);
3. validate the SQL with the existing read-only validator;
4. aggregate the full eligible row set in Python/Decimal, preserving negative
   quantities and separate currencies;
5. validate required inputs per row and name gaps instead of letting SQL null
   handling turn a blank into zero or a complete total.

It deliberately does not add another SQL engine or formula evaluator.
"""
from __future__ import annotations

import json
import logging
import math
import numbers
import os
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from core.data.dataset_manager import _validate_dataset_sql
from core.formula_engine import col_letter
from core.pending_file_task import is_aggregate_request
from core.sheet_dataset_service import SHEET_ROW_COL, _schema_block

logger = logging.getLogger(__name__)

_MAX_AGGREGATE_ROWS = 50000
_MAX_DISPLAY_ROWS = 50

#: Sentinel strings that materialization can preserve for an absent cell.
#: They are MISSING INPUTS, never numeric zeros (2026-10-25 review).
_MISSING_SENTINELS = {
    "", "nan", "+nan", "-nan", "inf", "+inf", "-inf",
    "infinity", "+infinity", "-infinity", "null", "none", "n/a", "na",
    "<na>", "<nat>", "(blank)", "blank",
}

_SHEET_STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "in", "on", "at",
    "for", "from", "of", "to", "with", "by", "rows", "row", "records",
    "record", "approved", "cancelled", "canceled", "open", "closed",
    "active", "inactive", "eligible", "matching", "first", "second",
    "third", "fourth", "fifth", "next", "last", "same", "other",
    "uploaded", "workbook", "file", "spreadsheet", "whole", "entire",
    "each", "every", "all", "both", "any", "some", "look", "read", "open",
    "give", "show", "tell", "find", "get", "calculate", "select", "filter",
}
_GENERIC_SHEET_WORDS = {
    "sheet", "data", "table", "tab", "details", "detail", "totals",
    "summary", "report", "records", "rows",
}
_FILE_TOKEN_RE = re.compile(
    r"(?<![\w./\\-])[^\s/\\]+\.(?:xlsx|xlsm|xlsb|xls|csv|tsv|parquet|pdf|docx?)"
    r"(?![\w])",
    re.IGNORECASE,
)


def looks_like_aggregate_request(query: str) -> bool:
    """Delegate to the shared accepted-operation classifier."""
    return is_aggregate_request(query)


def _norm_sheet(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _strip_file_names(text: str, entries: List[Dict[str, Any]]) -> str:
    """The workbook NAME is not a sheet scope.

    Remove explicit filenames (with extension) before sheet matching.
    Bare stems are NOT removed: a user who says "Adjustments sheet" may
    mean the sheet even when a workbook stem happens to match. The
    space-containing filename bug (2026-10-25 second review) came from
    stripping only its last whitespace-delimited token, leaving "PO" to
    bind an unrelated sheet.
    """
    cleaned = str(text or "")
    names = set()
    for entry in entries:
        base = os.path.basename(str(entry.get("file_name") or "").strip())
        if base:
            names.add(base)
    # Exact filenames first (longest first) so a name containing spaces
    # is removed whole, not token-by-token.
    for name in sorted(names, key=len, reverse=True):
        if not name:
            continue
        cleaned = re.sub(
            r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])",
            " ", cleaned, flags=re.IGNORECASE)
    # Any remaining extension-bearing token (a name not in this
    # workbook's catalog, or a differently-cased copy).
    cleaned = _FILE_TOKEN_RE.sub(" ", cleaned)
    return " ".join(cleaned.split())


def _is_generic_sheet_name(name: str) -> bool:
    """A sheet literally named Summary/Totals/Data/Approved must not bind
    just because the request uses that ordinary word."""
    words = re.findall(r"[a-z0-9]+", _norm_sheet(name))
    return bool(words) and all(
        word in _GENERIC_SHEET_WORDS or word in _SHEET_STOPWORDS
        for word in words
    )


def _sheet_name_is_cued(name: str, text: str) -> bool:
    """An explicit scope cue for a generic sheet name."""
    escaped = re.escape(name)
    return bool(
        re.search(rf"['\"]{escaped}['\"]", text, re.IGNORECASE)
        or re.search(
            rf"(?<![a-z0-9]){escaped}\s+(?:sheet|tab)\b",
            text, re.IGNORECASE)
        or re.search(
            rf"\b(?:sheet|tab)\s+(?:named\s+|called\s+)?{escaped}"
            rf"(?![a-z0-9])",
            text, re.IGNORECASE)
    )


def _catalog_sheet_match(
    entries: List[Dict[str, Any]], text: str
) -> Tuple[Optional[str], Optional[str]]:
    """Whole-token catalog match, longest first.

    Nested names (PO / PO Register) resolve to the longer name instead of
    a false ambiguity. Generic tab words require a "NAME sheet" / quoted
    cue so "summary of the rows" does not bind a Summary tab (second
    review, 2026-10-25).
    """
    matched: List[str] = []
    lowered = _norm_sheet(text)
    for entry in entries:
        name = _norm_sheet(entry.get("entity_name"))
        if not name:
            continue
        if not re.search(
                r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])",
                lowered):
            continue
        if _is_generic_sheet_name(name) and not _sheet_name_is_cued(
                name, text):
            continue
        matched.append(name)
    matched = sorted(set(matched), key=len, reverse=True)
    if not matched:
        return None, None
    longest = matched[0]
    for other in matched[1:]:
        if not re.search(
                r"(?<![a-z0-9])" + re.escape(other) + r"(?![a-z0-9])",
                longest):
            return None, "multiple explicit sheet names: " + ", ".join(
                sorted(matched))
    return longest, None


def _trailing_sheet_phrase(text: str) -> Optional[str]:
    """A short proper-noun phrase immediately before the word "sheet".

    Deliberately conservative: never fabricate a name out of prose such
    as "the sheet" or "approved rows in the sheet". A phrase containing a
    scope/grammar stopword is not a sheet name.
    """
    match = re.search(r"\bsheet\b", text, re.IGNORECASE)
    if not match:
        return None
    before = text[:match.start()].rstrip()
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9&'._-]*", before)
    words: List[str] = []
    for token in reversed(tokens):
        if token.lower() in _SHEET_STOPWORDS:
            break
        words.append(token)
        if len(words) == 4:
            break
    if not words:
        return None
    phrase = " ".join(reversed(words))
    if all(word.lower() in _GENERIC_SHEET_WORDS for word in words):
        return None
    return phrase


def _bind_sheet(
    entries: List[Dict[str, Any]], query: str
) -> Tuple[Optional[str], Optional[str]]:
    """Bind an explicitly named sheet; never guess among several.

    - explicit catalog names match on whole tokens, longest name wins;
    - workbook filenames/stems are removed first (a file name is not a
      sheet scope);
    - a conservative "NAME sheet" phrase can name a sheet missing from
      the catalog — it is reported, never substituted;
    - no explicit name with more than one sheet is an ambiguity, not a
      planner fallback (2026-10-25 work order).
    """
    text = _strip_file_names(query, entries)
    lowered = _norm_sheet(text)
    name, err = _catalog_sheet_match(entries, text)
    if err:
        return None, err
    if name:
        return name, None

    phrase = _trailing_sheet_phrase(text)
    if phrase:
        return phrase.lower(), None

    # "the sheet" / "the second sheet" names no sheet. With more than one
    # cataloged sheet that is ambiguous scope, not permission to choose.
    if re.search(
            r"\b(?:the|this|that|first|second|third|fourth|fifth|next|last|"
            r"same|other)\s+sheet\b",
            lowered):
        if len(entries) > 1:
            return None, (
                "the request refers to a sheet without naming it, and this "
                "workbook has several sheets")
        return _norm_sheet(entries[0].get("entity_name")), None

    if len(entries) > 1:
        return None, (
            "no sheet was named and this workbook has several sheets; "
            "name the sheet explicitly")
    if entries:
        return _norm_sheet(entries[0].get("entity_name")), None
    return None, None


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return str(value).strip().lower() in _MISSING_SENTINELS


def _dec(value: Any) -> Optional[Decimal]:
    if _blank(value):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _cell_for(columns: List[str], column: str, row: int) -> str:
    try:
        idx = columns.index(column)
    except ValueError:
        return ""
    return f"{col_letter(idx)}{row}"


def _error_block(title: str, detail: str) -> Dict[str, Any]:
    block = (
        "LIVE TOOL RESULTS (datasets.aggregate — deterministic; the "
        "model did not compute this):\n"
        f"{title}\n{detail}\n"
        "No total was computed."
    )
    return {
        "status": "error",
        "complete": False,
        "block": block,
        "answer": block.split("\n", 1)[1],
        "gaps": [],
        "subtotals": {},
    }


def _render(result: Dict[str, Any]) -> str:
    file_name = result.get("file_name") or ""
    sheet = result.get("sheet") or ""
    lines = [
        "LIVE TOOL RESULTS (datasets.aggregate — deterministic; the model did not compute this):",
        f"Workbook: `{file_name}`; Sheet: `{sheet}`; Version: `{str(result.get('version') or '')[:12]}`",
        f"Selected rows: {result.get('selected_count', 0)}; "
        f"computable: {result.get('known_count', 0)}; "
        f"gaps: {len(result.get('gaps') or [])}",
    ]
    source_count = result.get("source_row_count")
    if source_count is not None:
        lines.append(
            f"Sheet rows: {source_count}; selected by the predicate: "
            f"{result.get('selected_count', 0)}; not selected: "
            f"{result.get('not_selected_count', 0)}")
    source_statuses = result.get("source_status_counts") or {}
    if source_statuses:
        lines.append(
            "Sheet status counts: " + ", ".join(
                f"{k}={v}" for k, v in sorted(source_statuses.items())))
    selected_statuses = result.get("selected_status_counts") or {}
    if selected_statuses:
        lines.append(
            "Selected status counts: " + ", ".join(
                f"{k}={v}" for k, v in sorted(selected_statuses.items())))
    coverage = result.get("coverage") or {}
    if coverage.get("truncated"):
        lines.append(
            "Coverage: MATERIALIZED SHEET IS TRUNCATED at "
            f"{coverage.get('materialized_row_count')} of "
            f"{coverage.get('source_row_count')} rows — no complete total "
            "can be certified from this copy.")
    subtotals = result.get("subtotals") or {}
    if subtotals:
        lines.append("| Currency | Rows | Quantity | Value |")
        lines.append("|---|---:|---:|---:|")
        for currency in sorted(subtotals):
            row = subtotals[currency]
            lines.append(
                f"| {currency} | {row['rows']} | {row['quantity']} | "
                f"{row['value']} |"
            )
    gaps = result.get("gaps") or []
    if gaps:
        lines.append("Gaps:")
        for gap in gaps:
            lines.append(
                f"- {sheet} row {gap.get('row')} ({gap.get('identity')}): "
                f"missing {gap.get('missing')}"
                + (f" at {gap.get('cell')}" if gap.get("cell") else "")
            )
    if result.get("complete"):
        lines.append("Completeness: complete. All selected rows had required inputs.")
    else:
        if subtotals:
            lines.append(
                "Known subtotal (complete rows only): "
                + "; ".join(
                    f"{v['value']} {cur}" for cur, v in sorted(subtotals.items())
                )
            )
        lines.append(
            "Completeness: INCOMPLETE. Complete/grand total withheld: "
            + (f"{len(gaps)} required-input gap(s)." if gaps
               else "the selected scope is empty or truncated.")
        )
    # Contributing rows come AFTER completeness so a history/display cap
    # can never truncate the gap and completeness statement away.
    if result.get("rows"):
        shown = result["rows"][:_MAX_DISPLAY_ROWS]
        lines.append("Contributing rows:")
        for row in shown:
            lines.append(
                f"- row {row['row']} ({row['identity']}): "
                f"{row['quantity']} x {row['price']} = {row['value']} "
                f"{row['currency']} [{row['quantity_cell']}, "
                f"{row['price_cell']}]"
            )
        remaining = len(result["rows"]) - len(shown)
        if remaining > 0:
            lines.append(
                f"- … {remaining} more contributing row(s) not displayed; "
                "the totals above include the full selected scope."
            )
    return "\n".join(lines)


def aggregate_selected_rows(
    records: List[Dict[str, Any]],
    columns: List[str],
    roles: Dict[str, str],
    *,
    sheet: str,
    file_name: str,
    version: str,
    source_row_count: Optional[int] = None,
    coverage: Optional[Dict[str, Any]] = None,
    source_status_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Deterministic aggregation over already-selected detail rows.

    This is the local arithmetic control: callers can feed a validated
    SELECT's rows directly, with no model involved, then the same function
    serves the natural-language path.

    Provenance is REQUIRED: every row must carry its original sheet row
    (``__sheet_row``). A positional fallback (``idx + 2``) is forbidden —
    it cites the wrong cell whenever the SQL filtered or reordered rows.
    """
    invalid: List[int] = []
    sheet_rows: List[int] = []
    for idx, rec in enumerate(records):
        raw = rec.get(SHEET_ROW_COL)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            invalid.append(idx)
            continue
        if parsed < 2:
            invalid.append(idx)
            continue
        sheet_rows.append(parsed)
    if invalid:
        return _error_block(
            "ROW PROVENANCE MISSING",
            f"{len(invalid)} selected row(s) did not carry a usable "
            f"{SHEET_ROW_COL}; no total was computed.",
        )
    duplicates = sorted({
        row for row, count in Counter(sheet_rows).items() if count > 1
    })
    if duplicates:
        return _error_block(
            "DUPLICATE ROWS",
            "The selection returned the same sheet row more than once "
            f"({', '.join(str(r) for r in duplicates[:8])}); a total over "
            "duplicated rows is wrong, so none was computed.",
        )

    subtotals: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    selected_status_counts: Dict[str, int] = {}
    status_column = roles.get("status_column") or ""
    for idx, rec in enumerate(records):
        sheet_row = sheet_rows[idx]
        if status_column:
            status_value = rec.get(status_column)
            status_key = ("(blank)" if _blank(status_value)
                          else str(status_value).strip())
            selected_status_counts[status_key] = (
                selected_status_counts.get(status_key, 0) + 1)
        identity = rec.get(roles["identity_column"]) if roles["identity_column"] else None
        if not _blank(identity):
            identity = str(identity).strip()
            identity_source = "identity_column"
        else:
            identity = f"row {sheet_row}"
            identity_source = "sheet_row"
        qty = _dec(rec.get(roles["quantity_column"]))
        price = _dec(rec.get(roles["price_column"]))
        currency = rec.get(roles["currency_column"])
        currency = str(currency).strip().upper() if not _blank(currency) else ""
        missing = []
        if qty is None:
            missing.append(("quantity", roles["quantity_column"]))
        if price is None:
            missing.append(("price", roles["price_column"]))
        if not currency:
            missing.append(("currency", roles["currency_column"]))
        if missing:
            for label, col in missing:
                gaps.append({
                    "identity": identity,
                    "row": sheet_row,
                    "missing": label,
                    "cell": _cell_for(columns, col, sheet_row),
                })
            continue
        value = qty * price
        bucket = subtotals.setdefault(currency, {
            "rows": 0, "quantity": Decimal(0), "value": Decimal(0)
        })
        bucket["rows"] += 1
        bucket["quantity"] += qty
        bucket["value"] += value
        rows.append({
            "identity": identity,
            "identity_source": identity_source,
            "row": sheet_row,
            "quantity": str(qty),
            "price": str(price),
            "value": str(value.quantize(Decimal("0.01"))),
            "currency": currency,
            "quantity_cell": _cell_for(columns, roles["quantity_column"], sheet_row),
            "price_cell": _cell_for(columns, roles["price_column"], sheet_row),
        })

    rendered_subtotals = {
        cur: {
            "rows": v["rows"],
            "quantity": str(v["quantity"]),
            "value": str(v["value"].quantize(Decimal("0.01"))),
        }
        for cur, v in subtotals.items()
    }
    complete = not gaps
    not_selected = (
        max(int(source_row_count) - len(records), 0)
        if source_row_count is not None else None
    )
    result = {
        "status": "complete" if complete else "partial",
        "complete": complete,
        "file_name": file_name,
        "sheet": sheet,
        "version": version,
        "source_row_count": source_row_count,
        "selected_count": len(records),
        "not_selected_count": not_selected,
        "source_status_counts": source_status_counts or {},
        "selected_status_counts": selected_status_counts,
        "known_count": len(rows),
        "gaps": gaps,
        "subtotals": rendered_subtotals,
        "rows": rows,
        "coverage": coverage or {},
    }
    result["block"] = _render(result)
    result["answer"] = result["block"].split("\n", 1)[1]
    return result


def _duckdb_ast(sql: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Parse SQL with DuckDB's own parser (no execution)."""
    import duckdb

    con = duckdb.connect()
    try:
        raw = con.execute(
            "SELECT json_serialize_sql(?)", [sql]).fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        return None, f"SQL could not be parsed ({type(exc).__name__})."
    finally:
        con.close()
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None, "SQL parser returned an unreadable structure."
    if parsed.get("error"):
        return None, (
            "SQL could not be parsed: "
            + str(parsed.get("error_message") or "syntax error")[:200]
        )
    statements = parsed.get("statements") or []
    if len(statements) != 1:
        return None, "Only one SELECT statement is allowed."
    node = (statements[0] or {}).get("node") or {}
    if node.get("type") != "SELECT_NODE":
        return None, "Only a SELECT statement is allowed."
    return node, ""


def _ast_plain_projected_columns(node: Dict[str, Any]) -> List[str]:
    """Plain column references in the outer projection (no expressions)."""
    out: List[str] = []
    for item in node.get("select_list") or []:
        if str(item.get("class") or "").upper() != "COLUMN_REF":
            continue
        if str(item.get("alias") or "").strip():
            continue
        names = item.get("column_names") or []
        if names and str(names[-1]):
            out.append(str(names[-1]))
    return out


def _ast_column_refs(value: Any) -> set:
    """All COLUMN_REF last names in an AST subtree (case-preserved)."""
    out = set()
    if isinstance(value, dict):
        if str(value.get("class") or "").upper() == "COLUMN_REF":
            names = value.get("column_names") or []
            if names:
                out.add(str(names[-1]))
        for child in value.values():
            out.update(_ast_column_refs(child))
    elif isinstance(value, list):
        for child in value:
            out.update(_ast_column_refs(child))
    return out


def _ast_predicate_paths(node: Dict[str, Any]) -> List[List[str]]:
    """Column-reference paths used in WHERE/HAVING/QUALIFY/GROUP."""
    out: List[List[str]] = []

    def _paths(value: Any) -> None:
        if isinstance(value, dict):
            if str(value.get("class") or "").upper() == "COLUMN_REF":
                names = [str(n) for n in (value.get("column_names") or [])]
                if names:
                    out.append(names)
            for child in value.values():
                _paths(child)
        elif isinstance(value, list):
            for child in value:
                _paths(child)

    def _visit(value: Any) -> None:
        if isinstance(value, dict):
            if str(value.get("type") or "").upper() == "SELECT_NODE":
                for key in ("where_clause", "having", "qualify",
                            "group_expressions", "group_sets"):
                    _paths(value.get(key))
            for child in value.values():
                _visit(child)
        elif isinstance(value, list):
            for child in value:
                _visit(child)

    _visit(node)
    return out


def _ast_predicate_columns(node: Dict[str, Any]) -> set:
    """Last names of predicate column refs (see predicate_paths)."""
    return {path[-1] for path in _ast_predicate_paths(node) if path}


def _ast_contains_sample(value: Any) -> bool:
    """Any SELECT/table node in the tree may carry a sample."""
    if isinstance(value, dict):
        if value.get("sample") is not None:
            return True
        return any(_ast_contains_sample(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_contains_sample(v) for v in value)
    return False


def _ast_has_nonbase_from(value: Any) -> bool:
    """Any nested FROM that is not the registered base table/empty."""
    if isinstance(value, dict):
        from_table = value.get("from_table")
        if isinstance(from_table, dict):
            kind = str(from_table.get("type") or "").upper()
            if kind and kind not in ("BASE_TABLE", "EMPTY"):
                return True
        return any(_ast_has_nonbase_from(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_has_nonbase_from(v) for v in value)
    return False


def _ast_has_extract_or_random(value: Any) -> bool:
    """Struct/array field access and random() can hide a required input."""
    extract_types = {"STRUCT_EXTRACT", "ARRAY_EXTRACT", "LIST_EXTRACT",
                     "MAP_EXTRACT"}
    extract_funcs = {
        "struct_extract", "array_extract", "list_extract", "map_extract",
        "json_extract", "json_extract_string", "json_value",
        "json_extract_path", "json_extract_path_text", "json_type",
        "json_each", "json_tree", "to_json", "json_serialize_sql",
        "json_deserialize_sql", "json_execute_serialized_sql",
        "struct_values", "struct_keys", "struct_pack", "struct_insert",
        "map_keys", "map_values", "row",
        "->", "->>", "query", "query_table",
        "random", "setseed", "uuid", "gen_random_uuid", "uuidv4", "uuidv7",
    }
    if isinstance(value, dict):
        kind = str(value.get("type") or "").upper()
        cls = str(value.get("class") or "").upper()
        func = str(value.get("function_name") or "").lower()
        if kind in extract_types or cls in extract_types:
            return True
        if func in extract_funcs:
            return True
        return any(_ast_has_extract_or_random(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_has_extract_or_random(v) for v in value)
    return False


def _ast_has_column_alias_list(value: Any) -> bool:
    """FROM (...) AS t(a,b) can rename a required input."""
    if isinstance(value, dict):
        if value.get("column_name_alias"):
            return True
        return any(_ast_has_column_alias_list(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_has_column_alias_list(v) for v in value)
    return False


def _ast_has_select_alias(value: Any) -> bool:
    """Any SELECT projection alias, including nested SELECT nodes."""
    if isinstance(value, dict):
        if str(value.get("type") or "").upper() == "SELECT_NODE":
            for item in value.get("select_list") or []:
                if str(item.get("alias") or "").strip():
                    return True
        return any(_ast_has_select_alias(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_has_select_alias(v) for v in value)
    return False


def _ast_has_unsafe_reference(value: Any) -> bool:
    """STAR/COLUMNS and positional refs can hide a physical column."""
    if isinstance(value, dict):
        cls = str(value.get("class") or "").upper()
        if cls in ("STAR", "POSITIONAL_REFERENCE"):
            return True
        return any(_ast_has_unsafe_reference(v) for v in value.values())
    if isinstance(value, list):
        return any(_ast_has_unsafe_reference(v) for v in value)
    return False


def _ast_select_node_count(value: Any) -> int:
    if isinstance(value, dict):
        count = 1 if str(value.get("type") or "").upper() == "SELECT_NODE" else 0
        return count + sum(_ast_select_node_count(v) for v in value.values())
    if isinstance(value, list):
        return sum(_ast_select_node_count(v) for v in value)
    return 0


def _ast_identity_violation(
    node: Dict[str, Any], allowed_tables: List[str]
) -> Optional[str]:
    """Structural membership binding via DuckDB's parsed AST.

    The outer query must read the registered BASE_TABLE directly; the
    outer projection must contain exactly one plain __sheet_row column
    reference and no computed/aliased replacement. Comments, dollar
    quotes, CTEs, derived tables, joins and samples cannot hide that
    shape from the parser.
    """
    if (node.get("cte_map") or {}).get("map"):
        return (
            "The selection query must be a single SELECT reading the "
            "registered dataset directly; WITH/CTE forms are not allowed."
        )
    if _ast_select_node_count(node) > 1:
        return (
            "The selection query must be one flat SELECT; nested SELECTs/"
            "subqueries are not allowed."
        )
    if _ast_contains_sample(node):
        return (
            "The selection query may not sample rows (outer or nested); the "
            "full eligible selection is required."
        )
    if _ast_has_nonbase_from(node):
        return (
            "The selection query may not use nested derived tables, joins "
            "or table functions; only the registered base table is readable."
        )
    if _ast_has_extract_or_random(node):
        return (
            "The selection query may not use struct/array field extraction "
            "or random()/setseed() in a predicate; name physical frame "
            "columns directly and keep the selection deterministic."
        )
    if _ast_has_column_alias_list(node):
        return (
            "The selection query may not rename columns in FROM; physical "
            "frame column names are required."
        )
    if _ast_has_unsafe_reference(node):
        return (
            "The selection query may not use STAR/COLUMNS expansion or "
            "positional column references; name physical frame columns "
            "explicitly."
        )
    if _ast_has_select_alias(node):
        return (
            "Projected columns must not be aliased (including nested "
            "SELECTs); name the physical frame columns directly."
        )
    from_table = node.get("from_table") or {}
    if str(from_table.get("type") or "").upper() != "BASE_TABLE":
        return (
            "The selection query must read the registered dataset directly; "
            "derived tables, joins and table functions are not allowed."
        )
    table = str(from_table.get("table_name") or "").lower()
    allowed = {str(name).lower() for name in allowed_tables if name}
    if table not in allowed:
        return (
            f"The selection query reads '{table}', but only the registered "
            "dataset may supply row identities."
        )
    schema = str(from_table.get("schema_name") or "").lower()
    if schema not in ("", "main"):
        return "The selection query may read only the registered dataset."
    if from_table.get("at_clause"):
        return "Time-travel/AT clauses are not allowed on the dataset."
    if from_table.get("column_name_alias"):
        return "Renaming columns in FROM is not allowed for this selection."
    for modifier in node.get("modifiers") or []:
        kind = str(modifier.get("type") or "").upper()
        if kind == "ORDER_MODIFIER":
            continue
        return (
            "The selection query must return the full unordered detail row "
            f"set; {kind or 'this modifier'} is not allowed."
        )
    if (node.get("group_expressions") or node.get("group_sets")
            or node.get("having") or node.get("qualify")):
        return (
            "The selection query must return detail rows only; grouping/"
            "HAVING/QUALIFY are not allowed."
        )
    select_list = node.get("select_list") or []
    sheet_refs = []
    for item in select_list:
        cls = str(item.get("class") or "").upper()
        if cls == "STAR":
            return (
                "Project __sheet_row explicitly as a plain column; SELECT * "
                "is not allowed."
            )
        if cls not in ("COLUMN_REF", "CONSTANT", "VALUE_CONSTANT"):
            return (
                "The projection may contain only plain frame columns and "
                "constants; functions, CASE, unnest, casts and subqueries "
                "are not allowed."
            )
        names = item.get("column_names") or []
        last = str(names[-1]) if names else ""
        if last == "__sheet_row":
            sheet_refs.append(item)
    if len(sheet_refs) != 1:
        return (
            "The selection query must project exactly one plain "
            "__sheet_row column reference."
        )
    item = sheet_refs[0]
    if str(item.get("class") or "").upper() != "COLUMN_REF":
        return (
            "The selection query must project __sheet_row as a plain "
            "column reference (never an expression, CASE, cast or alias); "
            "the authoritative frame supplies all calculation inputs."
        )
    if str(item.get("alias") or "").strip():
        return (
            "The selection query must project __sheet_row without an alias; "
            "the authoritative frame supplies all calculation inputs."
        )
    return None


_ROLE_HINTS: Dict[str, Tuple[str, ...]] = {
    "identity_column": (
        "po id", "po number", "order id", "order number", "item id",
        "item number", "reference", "ref", "sku", "code", "id",
        "line no", "line number", "row no", "row number",
    ),
    "quantity_column": (
        "qty", "quantity", "units", "unit quantity",
    ),
    "price_column": (
        "unit price", "price", "unit cost", "amount", "total", "value",
        "cost",
    ),
    "currency_column": (
        "currency", "ccy", "curr",
    ),
    "status_column": (
        "status", "state",
    ),
}


def _norm_role_name(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _role_hint_matches(column: str, hints: Tuple[str, ...]) -> bool:
    tokens = set(_norm_role_name(column).split())
    return any(
        all(token in tokens for token in hint.split())
        for hint in hints
    )


def _infer_roles(
    roles: Dict[str, str], columns: List[str]
) -> Dict[str, str]:
    """Fill a missing role from an exact generic column-name match.

    The planner sometimes omits or aliases role fields while the frame
    carries the real names. This is a deterministic frame lookup, not a
    second model call; ambiguous matches stay missing and fail closed.
    """
    normalized: Dict[str, List[str]] = {}
    for col in columns:
        normalized.setdefault(_norm_role_name(col), []).append(col)
    for role, hints in _ROLE_HINTS.items():
        current = str(roles.get(role) or "")
        if current and current in columns and current != SHEET_ROW_COL:
            continue
        matches = {
            col for hint in hints for col in normalized.get(hint, [])
        }
        if len(matches) == 1:
            roles[role] = next(iter(matches))
    return roles


def _resolve_roles(
    roles: Dict[str, str], columns: List[str]
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Bind required/status roles to the frame's own matching columns.

    A model-provided role never outranks a single physical column that
    matches that role's generic name. Multiple matches are ambiguous and
    fail closed; no matches leave the planner's value in place.
    """
    ambiguous: Dict[str, List[str]] = {}
    for role in ("quantity_column", "price_column",
                 "currency_column", "status_column"):
        hints = _ROLE_HINTS.get(role, ())
        matches = [
            col for col in columns if _role_hint_matches(col, hints)
        ]
        if len(matches) == 1:
            roles[role] = matches[0]
        elif len(matches) > 1:
            ambiguous[role] = matches
    return roles, ambiguous


def _strip_sql_noise(sql: str) -> str:
    """Literals and quoted identifiers are not SQL keywords/paths."""
    text = re.sub(r"'(?:[^'\\]|\\.)*'", " ", sql)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', " ", text)
    text = re.sub(r"--[^\n]*", " ", text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return text


def _selection_sql_violation(sql: str) -> Optional[str]:
    """Fail-closed detail-row shape.

    The aggregate is computed in Python over the returned rows; a query
    that can aggregate, de-duplicate, join, limit, read a path, replace a
    required input, or filter required inputs out is not a detail
    selection and cannot be certified (2026-10-25 reviews).
    """
    stripped = _strip_sql_noise(sql)
    if re.search(
            r"\b(?:union|intersect|except|join|group\s+by|having|"
            r"qualify|limit|offset)\b",
            stripped, re.IGNORECASE):
        return (
            "The selection query must return detail rows only: UNION/"
            "INTERSECT/EXCEPT, JOIN, GROUP BY, and LIMIT/OFFSET are not "
            "allowed."
        )
    if re.search(r"\bselect\s+distinct\b", stripped, re.IGNORECASE):
        return (
            "The selection query must return detail rows only: DISTINCT is "
            "not allowed."
        )
    if re.search(r"\bover\s*\(", stripped, re.IGNORECASE):
        return (
            "The selection query must return detail rows only: window "
            "functions are not allowed."
        )
    if re.search(
            r"\b(?:sum|count|avg|min|max|median|stddev|variance|"
            r"string_agg|array_agg|list|first|last|any_value|arg_min|"
            r"arg_max|min_by|max_by|mode|quantile_cont|quantile_disc|"
            r"approx_quantile|approx_count_distinct|count_if|bool_and|"
            r"bool_or|bit_and|bit_or|product|fsum|sumkahan|entropy|"
            r"approx_\w+|percentile\w*)\s*\(",
            stripped, re.IGNORECASE):
        return (
            "The selection query must return detail rows only: aggregate "
            "functions are not allowed (the harness computes totals)."
        )
    if re.search(
            r"\b(?:coalesce|ifnull|nullif|nvl)\s*\(",
            stripped, re.IGNORECASE):
        return (
            "The selection query may not replace a required input with a "
            "default: a blank/NaN input must remain a named gap, never zero."
        )
    if re.search(r"\bis\s+(?:not\s+)?null\b", stripped, re.IGNORECASE):
        return (
            "The selection query may not filter rows by NULL presence: a "
            "row with a missing required input must remain visible as a gap."
        )
    if re.search(r"(?is)\b(?:from|join)\s*'", sql):
        return (
            "The selection query may read only the registered dataset; a "
            "file path/table function is not allowed."
        )
    if re.search(
            r"(?is)['\"][^'\"]*(?:/|\\\\|\.parquet|\.csv|\.json|\.xlsx)"
            r"['\"]", sql):
        return (
            "The selection query may not name a filesystem path; only the "
            "registered dataset frame is readable."
        )
    return None


async def _execute_selection_plan(
    entries: List[Dict[str, Any]],
    plan: Any,
    query: str,
    *,
    file_name: Optional[str],
    sheet_name: Optional[str],
    max_rows: int,
) -> Dict[str, Any]:
    dataset_name = str(getattr(plan, "dataset_name", "") or "").strip()
    sql = str(getattr(plan, "sql", "") or "").strip().rstrip(";").strip()
    chosen = next(
        (e for e in entries if str(e.get("dataset_name")) == dataset_name), None
    )
    if sheet_name is not None and chosen is None:
        return _error_block(
            "SHEET BINDING VIOLATED",
            f"The plan targets '{dataset_name}', but the request explicitly "
            f"named sheet '{sheet_name}'. No fallback was allowed.",
        )
    if chosen is None or not sql:
        return _error_block(
            "AGGREGATION NOT PLANNED",
            "The planner did not return a usable dataset/query; no total was computed.",
        )
    if sheet_name is not None and _norm_sheet(chosen.get("entity_name")) != sheet_name:
        return _error_block(
            "SHEET BINDING VIOLATED",
            f"The planner chose '{chosen.get('entity_name')}' but the request "
            f"explicitly named '{sheet_name}'. No fallback was allowed.",
        )
    coverage = dict(chosen.get("coverage") or {})
    if coverage.get("truncated"):
        return _error_block(
            "MATERIALIZED COVERAGE TRUNCATED",
            f"'{chosen.get('entity_name')}' is materialized only up to "
            f"{coverage.get('materialized_row_count')} of "
            f"{coverage.get('source_row_count')} source rows. A total over "
            "a truncated copy would be wrong; no total was computed.",
        )
    roles = {
        "identity_column": str(getattr(plan, "identity_column", "") or ""),
        "quantity_column": str(getattr(plan, "quantity_column", "") or ""),
        "price_column": str(getattr(plan, "price_column", "") or ""),
        "currency_column": str(getattr(plan, "currency_column", "") or ""),
        "status_column": str(getattr(plan, "status_column", "") or ""),
    }
    alias = re.sub(
        r"[^a-z0-9_]+", "_", str(chosen.get("entity_name")).lower())
    ast_node, ast_error = _duckdb_ast(sql)
    if ast_error or ast_node is None:
        return _error_block("SQL REJECTED", ast_error)
    try:
        import pandas as pd

        df = pd.read_parquet(chosen["parquet_path"])
        columns = [str(c) for c in df.columns]
    except Exception as exc:  # noqa: BLE001
        return _error_block(
            "AGGREGATION EXECUTION FAILED",
            f"The materialized sheet could not be read "
            f"({type(exc).__name__}); no total was computed.",
        )
    # Role inference precedes the required-column SQL guard: a planner
    # that omits quantity_column must not thereby disable the guard.
    roles = _infer_roles(roles, columns)
    roles, _ambiguous_roles = _resolve_roles(roles, columns)
    if _ambiguous_roles:
        return _error_block(
            "AMBIGUOUS ROLE COLUMN",
            "More than one frame column matches "
            + ", ".join(sorted(_ambiguous_roles))
            + "; no role was chosen by name or planner order.",
        )
    if roles["identity_column"] in ("", SHEET_ROW_COL):
        # The planner sometimes returns __sheet_row as the identity
        # role even when it projected a real business key. Values
        # still come from the frame; only the ROLE is corrected.
        _role_cols = {
            roles["quantity_column"], roles["price_column"],
            roles["currency_column"], roles["status_column"],
            SHEET_ROW_COL,
        }
        _candidate = next(
            (
                name for name in _ast_plain_projected_columns(ast_node)
                if name in columns and name not in _role_cols
            ),
            None,
        )
        if _candidate:
            roles["identity_column"] = _candidate
    for role in ("quantity_column", "price_column",
                 "currency_column", "status_column"):
        if roles[role] == SHEET_ROW_COL:
            roles[role] = ""
    _seen_roles: Dict[str, str] = {}
    _normalized_frame: Dict[str, List[str]] = {}
    for column in columns:
        _normalized_frame.setdefault(_norm_role_name(column), []).append(
            column)
    for role in ("identity_column", "quantity_column", "price_column",
                 "currency_column", "status_column"):
        column = roles[role]
        if not column:
            continue
        norm = _norm_role_name(column)
        if len(_normalized_frame.get(norm, [])) > 1:
            return _error_block(
                "AMBIGUOUS COLUMN NAME",
                f"{role}='{column}' is ambiguous with another frame column "
                "after case/punctuation normalization; no similar column "
                "was chosen.",
            )
        if norm in _seen_roles:
            return _error_block(
                "ROLE CONFLICT",
                f"{role} and {_seen_roles[norm]} both map to '{column}'; "
                "each calculation role must be a distinct frame column.",
            )
        _seen_roles[norm] = role
        own_hints = _ROLE_HINTS.get(role, ())
        own_match = _role_hint_matches(column, own_hints)
        for other_role, hints in _ROLE_HINTS.items():
            if other_role == role:
                continue
            other_match = _role_hint_matches(column, hints)
            if other_match and not own_match:
                return _error_block(
                    "ROLE CONFLICT",
                    f"{role} is mapped to '{column}', which matches the "
                    f"{other_role} role; no silent role substitution is "
                    "allowed.",
                )
    for role, col in roles.items():
        if col and col not in columns:
            return _error_block(
                "COLUMN NOT FOUND",
                f"The planner named {role}='{col}', which is not a column "
                "of the materialized sheet. No similar column was substituted.",
            )
    for required in ("identity_column", "quantity_column",
                     "price_column", "currency_column"):
        if not roles[required]:
            return _error_block(
                "REQUIRED COLUMN NOT IDENTIFIED",
                f"The planner did not identify the {required.replace('_column', '')} "
                "column; a complete total was withheld.",
            )
    predicate_paths = _ast_predicate_paths(ast_node)
    _from_table = ast_node.get("from_table") or {}
    relation_names = {
        "df",
        str(chosen.get("dataset_name") or "").lower(),
        str(chosen.get("entity_name") or "").lower(),
        alias,
        str(_from_table.get("alias") or "").lower(),
    }
    for path in predicate_paths:
        if path and path[-1].lower() in relation_names:
            return _error_block(
                "SQL REJECTED",
                "The selection query references a whole-row/relation name "
                f"'{'.'.join(path)}' in a predicate; name physical frame "
                "columns directly.",
            )
    predicate_columns = {
        path[-1].lower() for path in predicate_paths if path
    }
    frame_columns = {name.lower() for name in columns}
    unexpected = sorted(
        name for name in predicate_columns if name not in frame_columns)
    if unexpected:
        return _error_block(
            "SQL REJECTED",
            "The selection query references names that are not physical "
            "frame columns ("
            + ", ".join(unexpected[:8])
            + "); predicates must name physical columns directly.",
        )
    required_like_columns = set()
    for required in ("quantity_column", "price_column", "currency_column"):
        column = roles[required]
        if column:
            required_like_columns.add(column.lower())
        hints = _ROLE_HINTS.get(required, ())
        required_like_columns.update(
            col.lower() for col in columns
            if _role_hint_matches(col, hints)
        )
    for required in ("quantity_column", "price_column", "currency_column"):
        column = roles[required]
        if column and column.lower() in predicate_columns:
            return _error_block(
                "SQL REJECTED",
                f"The selection query may not filter on the required input "
                f"column '{column}'; missing inputs must remain visible as "
                "gaps.",
            )
    filtered_required = sorted(
        predicate_columns & required_like_columns)
    if filtered_required:
        return _error_block(
            "SQL REJECTED",
            "The selection query may not filter on required-input/like "
            "columns ("
            + ", ".join(filtered_required[:8])
            + "); missing inputs must remain visible as gaps.",
        )
    violation = (
        _validate_dataset_sql(sql)
        or _selection_sql_violation(sql)
        or _ast_identity_violation(
            ast_node,
            ["df", str(chosen.get("dataset_name") or ""), alias],
        )
    )
    if violation:
        return _error_block("SQL REJECTED", violation)
    if not re.match(r"(?is)^\s*select\b", sql) or ";" in sql:
        return _error_block("SQL REJECTED", "Only one SELECT statement is allowed.")

    logger.debug(
        "[datasets.aggregate] plan dataset=%s sql=%r roles=%s",
        dataset_name, sql[:800], roles)
    try:
        import duckdb

        source_status_counts: Dict[str, int] = {}
        if roles["status_column"] and roles["status_column"] in columns:
            status_series = (
                df[roles["status_column"]]
                .astype(object)
                .where(df[roles["status_column"]].notna(), "(blank)")
                .astype(str).str.strip()
            )
            status_series = status_series.where(
                status_series != "", "(blank)")
            source_status_counts = {
                str(k): int(v)
                for k, v in status_series.value_counts().head(12).items()
            }
        con = duckdb.connect()
        try:
            con.register("df", df)
            con.register(chosen["dataset_name"], df)
            con.register(alias, df)
            # The registered frame is the ONLY readable source. This
            # closes path/URL reads even if a validator token is missed.
            con.execute("SET enable_external_access=false")
            wrapped = f"SELECT * FROM ({sql}) AS _agg_rows LIMIT {max_rows + 1}"
            out = con.execute(wrapped).df()
        finally:
            con.close()
        out = out.astype(object).where(out.notna(), None)
    except Exception as exc:  # noqa: BLE001
        return _error_block(
            "AGGREGATION EXECUTION FAILED",
            f"The selection query failed ({type(exc).__name__}); no total was computed.",
        )

    if len(out) > max_rows:
        return _error_block(
            "PROCESSING LIMIT EXCEEDED",
            f"The selection returned more than {max_rows} rows. A partial "
            "total would be wrong; no total was computed. Narrow the request.",
        )
    if not len(out):
        _no_rows_block = _render({
            "file_name": file_name or chosen.get("file_name"),
            "sheet": chosen.get("entity_name"),
            "version": chosen.get("content_hash"),
            "source_row_count": coverage.get("source_row_count")
            or chosen.get("row_count"),
            "selected_count": 0,
            "not_selected_count": coverage.get("source_row_count")
            or chosen.get("row_count") or 0,
            "known_count": 0,
            "gaps": [],
            "subtotals": {},
            "rows": [],
            "coverage": coverage,
            "source_status_counts": source_status_counts,
            "selected_status_counts": {},
        }) + "\nNo rows matched the selection; no total was computed."
        return {
            "status": "no_rows",
            "complete": False,
            "block": _no_rows_block,
            "answer": _no_rows_block.split("\n", 1)[1],
            "gaps": [],
            "subtotals": {},
        }

    out_sheet_col = (
        SHEET_ROW_COL if SHEET_ROW_COL in out.columns else None)
    if out_sheet_col is None:
        return _error_block(
            "ROW PROVENANCE MISSING",
            f"The selection query did not project {SHEET_ROW_COL}; sheet row "
            "identity is required, so no total was computed.",
        )

    # EVIDENCE BINDING (2026-10-25 final correction): SQL selects ROW
    # IDENTITIES only. Every calculation input is read back from the
    # authoritative materialized frame — a projection alias, constant,
    # CASE, cast or expression can never supply quantity/price/currency/
    # status/identity.
    selected_ids: List[int] = []
    seen_ids = set()
    for value in out[out_sheet_col].tolist():
        if isinstance(value, bool) or value is None:
            return _error_block(
                "ROW IDENTITY INVALID",
                f"A selected {SHEET_ROW_COL} was not an exact integer; no "
                "total was computed.",
            )
        if isinstance(value, numbers.Integral):
            row_id = int(value)
        elif isinstance(value, str) and re.fullmatch(
                r"[0-9]+", value.strip()):
            row_id = int(value.strip())
        else:
            return _error_block(
                "ROW IDENTITY INVALID",
                f"A selected {SHEET_ROW_COL} was not an exact integer "
                f"({value!r}); no total was computed.",
            )
        if row_id < 2 or row_id in seen_ids:
            return _error_block(
                "ROW IDENTITY INVALID",
                f"A selected {SHEET_ROW_COL} was out of range or duplicated "
                f"({row_id}); no total was computed.",
            )
        seen_ids.add(row_id)
        selected_ids.append(row_id)

    authoritative_by_row: Dict[int, Dict[str, Any]] = {}
    for record in df.to_dict(orient="records"):
        raw_row = record.get(SHEET_ROW_COL)
        try:
            row_id = int(raw_row)
        except (TypeError, ValueError):
            continue
        authoritative_by_row[row_id] = record
    missing_ids = [
        row_id for row_id in selected_ids
        if row_id not in authoritative_by_row
    ]
    if missing_ids:
        return _error_block(
            "ROW IDENTITY NOT FOUND",
            "The selection returned row reference(s) that do not exist in "
            "the bound sheet/version ("
            + ", ".join(str(r) for r in missing_ids[:8])
            + "); no total was computed.",
        )
    selected_records = [
        authoritative_by_row[row_id] for row_id in selected_ids
    ]

    return aggregate_selected_rows(
        selected_records,
        columns,
        roles,
        sheet=str(chosen.get("entity_name") or ""),
        file_name=str(file_name or chosen.get("file_name") or ""),
        version=str(chosen.get("content_hash") or ""),
        source_row_count=(
            coverage.get("source_row_count")
            if coverage.get("source_row_count") is not None
            else chosen.get("row_count")
        ),
        coverage=coverage,
        source_status_counts=source_status_counts,
    )


async def execute_validated_aggregate_plan(
    entries: List[Dict[str, Any]],
    plan: Dict[str, Any],
    query: str = "",
    *,
    file_name: Optional[str] = None,
    max_rows: int = _MAX_AGGREGATE_ROWS,
) -> Dict[str, Any]:
    """Execute a controlled, already-validated selection plan.

    No model is involved. This is the local arithmetic/provenance control
    before natural-language planning; it uses the same read-only executor
    and deterministic Decimal aggregation as the production path.
    """
    if not entries:
        return _error_block("WORKBOOK NOT FOUND", "No dataset entries were supplied.")
    sheet_name, sheet_err = _bind_sheet(entries, query)
    if sheet_err:
        return _error_block("SHEET AMBIGUOUS", sheet_err)
    if sheet_name is not None:
        bound = [
            e for e in entries
            if _norm_sheet(e.get("entity_name")) == sheet_name
        ]
        if not bound:
            return _error_block(
                "SHEET NOT FOUND",
                f"Explicit sheet '{sheet_name}' is not cataloged for this "
                "workbook. No fallback to another sheet was attempted.",
            )
        entries = bound
    hashes = {
        str(entry.get("content_hash") or "") for entry in entries
        if str(entry.get("content_hash") or "")
    }
    if len(hashes) > 1:
        return _error_block(
            "WORKBOOK VERSION AMBIGUOUS",
            "Several active versions of the workbook/sheet are cataloged. "
            "No version was chosen by name or query order.",
        )
    import types as _types

    return await _execute_selection_plan(
        entries, _types.SimpleNamespace(**plan), query,
        file_name=file_name, sheet_name=sheet_name, max_rows=max_rows,
    )


async def aggregate_named_dataset(
    entries: List[Dict[str, Any]],
    query: str,
    llm_service: Any,
    *,
    file_name: Optional[str] = None,
    max_rows: int = _MAX_AGGREGATE_ROWS,
) -> Dict[str, Any]:
    """Run one selection/aggregation request over the named workbook sheets.

    ``entries`` must already be the catalog rows for ONE workbook (the caller
    resolves the file identity). Returns a result envelope with a rendered
    deterministic ``block``.
    """
    if not entries:
        return _error_block("WORKBOOK NOT FOUND", "No dataset entries were supplied.")
    if llm_service is None:
        return _error_block(
            "AGGREGATION PLANNER UNAVAILABLE",
            "The sheet-dataset SQL planner is unavailable; no total was computed.",
        )

    sheet_name, sheet_err = _bind_sheet(entries, query)
    if sheet_err:
        return _error_block("SHEET AMBIGUOUS", sheet_err)
    if sheet_name is not None:
        bound = [e for e in entries if _norm_sheet(e.get("entity_name")) == sheet_name]
        if not bound:
            return _error_block(
                "SHEET NOT FOUND",
                f"Explicit sheet '{sheet_name}' is not cataloged for this workbook. "
                "No fallback to another sheet was attempted.",
            )
        entries = bound
    hashes = {
        str(e.get("content_hash") or "") for e in entries
        if str(e.get("content_hash") or "")
    }
    if len(hashes) > 1:
        return _error_block(
            "WORKBOOK VERSION AMBIGUOUS",
            "Several active versions of the workbook/sheet are cataloged. "
            "No version was chosen by name or query order.",
        )

    from pydantic import BaseModel

    class _SheetSelectionPlan(BaseModel):
        dataset_name: str
        sql: str
        identity_column: str = ""
        quantity_column: str = ""
        price_column: str = ""
        currency_column: str = ""
        status_column: str = ""
        note: str = ""

    prompt = (
        "You write ONE DuckDB SELECT statement that returns the eligible DATA "
        "ROWS from the chosen sheet. Do NOT aggregate in SQL.\n\n"
        "Datasets available (each loaded as \"df\"):\n"
        f"{_schema_block(entries)}\n\n"
        f"Question: {query}\n\n"
        "Rules:\n"
        "- Pick the single dataset_name from the list; the sheet is already "
        "bound when the question names one.\n"
        "- SQL must be ONE SELECT reading ONLY \"df\" directly (no WITH/CTE, "
        "derived table or join). No "
        "INSERT/UPDATE/DELETE/DDL, no semicolon, no LIMIT.\n"
        "- Return the eligible rows only: encode the user's selection/filter "
        "in WHERE using the actual columns and values. Do not return unrelated "
        "rows (e.g. cancelled rows when the request selects approved rows).\n"
        "- NEVER replace a required input with COALESCE/IFNULL/NULLIF or a "
        "default, and never filter rows out because quantity, unit price, or "
        "currency is missing. Return those rows unchanged so the harness can "
        "name the gap instead of zeroing or dropping it.\n"
        "- Do NOT use SUM, COUNT, AVG, MIN, MAX, GROUP BY, or any aggregate. "
        "The harness computes totals deterministically over the returned rows.\n"
        "- SELECT ROW IDENTITIES: project __sheet_row as a plain column "
        "reference (never an expression, CASE, cast, or alias). The harness "
        "reads quantity, unit price, currency, status and identity from the "
        "authoritative frame for those rows, so projections of those fields "
        "are ignored. Other projection items may be plain frame columns or "
        "constants only — no functions/unnest/CASE/casts/subqueries.\n"
        "- Do NOT alias any projected column. Predicates must name physical "
        "frame columns directly; never use COLUMNS(...) expansion or #n "
        "positional references.\n"
        "- Set the role fields to the exact FRAME column names (listed "
        "above), not SQL aliases. identity_column is the sheet's business "
        "identifier column (never __sheet_row); use an empty string if the "
        "sheet has no business identifier and for any other role the sheet "
        "does not have.\n"
        "- If no dataset plausibly matches, set dataset_name and sql to empty.\n\n"
        "Return JSON: dataset_name, sql, identity_column, quantity_column, "
        "price_column, currency_column, status_column, note"
    )
    try:
        from core.llm.pinned_planning import (
            pinned_structured_call,
            resolve_pinned_provider_model,
        )

        llm_kwargs = resolve_pinned_provider_model(
            llm_service, "ATOM_SHEET_SQL_MODEL", "", provider="openrouter"
        )
        plan = await pinned_structured_call(
            llm_service,
            prompt=prompt,
            response_model=_SheetSelectionPlan,
            system_instruction=(
                "You convert a spreadsheet selection request into one safe "
                "DuckDB row-selection query. Output JSON only."
            ),
            call_kwargs=llm_kwargs,
            log_label="sheet dataset aggregate selection",
            task_type="nl2sql",
        )
    except Exception as exc:  # noqa: BLE001
        return _error_block(
            "AGGREGATION PLANNER FAILED",
            f"The sheet-dataset planner failed ({type(exc).__name__}); "
            "no total was computed.",
        )

    return await _execute_selection_plan(
        entries, plan, query,
        file_name=file_name, sheet_name=sheet_name, max_rows=max_rows,
    )
