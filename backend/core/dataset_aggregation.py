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

import math
import os
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from core.data.dataset_manager import _validate_dataset_sql
from core.formula_engine import col_letter
from core.pending_file_task import is_aggregate_request
from core.sheet_dataset_service import SHEET_ROW_COL, _schema_block

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


def _strip_sql_noise(sql: str) -> str:
    """Literals and quoted identifiers are not SQL keywords/paths."""
    text = re.sub(r"'(?:[^'\\]|\\.)*'", " ", sql)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', " ", text)
    text = re.sub(r"--[^\n]*", " ", text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return text


def _selection_sql_violation(
    sql: str, required_columns: Optional[List[str]] = None
) -> Optional[str]:
    """Fail-closed detail-row shape.

    The aggregate is computed in Python over the returned rows; a query
    that can aggregate, de-duplicate, join, limit, read a path, replace a
    required input, or filter required inputs out is not a detail
    selection and cannot be certified (2026-10-25 reviews).
    """
    stripped = _strip_sql_noise(sql)
    if re.search(
            r"\b(?:union|intersect|except|distinct|join|group\s+by|having|"
            r"qualify|limit|offset)\b",
            stripped, re.IGNORECASE):
        return (
            "The selection query must return detail rows only: DISTINCT, "
            "UNION/INTERSECT/EXCEPT, JOIN, GROUP BY, and LIMIT/OFFSET are "
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
            r"arg_max|approx_\w+|percentile\w*)\s*\(",
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
    where = re.search(
        r"(?is)\bwhere\b(.*?)(?:\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)",
        sql)
    if where:
        for column in required_columns or []:
            if column and re.search(
                    r"(?<![A-Za-z0-9_])" + re.escape(column)
                    + r"(?![A-Za-z0-9_])",
                    where.group(1), re.IGNORECASE):
                return (
                    f"The selection query may not filter on the required "
                    f"input column '{column}'; missing inputs must remain "
                    "visible as gaps."
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
    violation = _validate_dataset_sql(sql) or _selection_sql_violation(
        sql,
        required_columns=[
            roles["quantity_column"],
            roles["price_column"],
            roles["currency_column"],
        ],
    )
    if violation:
        return _error_block("SQL REJECTED", violation)
    if not re.match(r"(?is)^\s*(select|with)\b", sql) or ";" in sql:
        return _error_block("SQL REJECTED", "Only one SELECT statement is allowed.")

    try:
        import duckdb
        import pandas as pd

        df = pd.read_parquet(chosen["parquet_path"])
        columns = [str(c) for c in df.columns]
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
            alias = re.sub(r"[^a-z0-9_]+", "_", str(chosen["entity_name"]).lower())
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

    out_columns = [str(c) for c in out.columns]
    if SHEET_ROW_COL not in out_columns:
        return _error_block(
            "ROW PROVENANCE MISSING",
            f"The selection query did not project {SHEET_ROW_COL}; sheet row "
            "identity is required, so no total was computed.",
        )
    if roles["identity_column"] not in out_columns:
        return _error_block(
            "ROW IDENTITY MISSING",
            f"The selection query did not project the identity column "
            f"'{roles['identity_column']}'; no total was computed.",
        )
    if out[SHEET_ROW_COL].isna().any():
        return _error_block(
            "ROW PROVENANCE MISSING",
            f"One or more selected rows have no {SHEET_ROW_COL} value; no "
            "total was computed.",
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
        }) + "\nNo rows matched the selection; no total was computed."
        return {
            "status": "no_rows",
            "complete": False,
            "block": _no_rows_block,
            "answer": _no_rows_block.split("\n", 1)[1],
            "gaps": [],
            "subtotals": {},
        }

    return aggregate_selected_rows(
        out.to_dict(orient="records"),
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
        "- SQL must be ONE SELECT (or WITH) reading ONLY \"df\". No "
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
        "- Project __sheet_row plus the exact identity, quantity, unit-price, "
        "currency and status/grouping columns. Quote column names exactly as "
        "listed.\n"
        "- Set the role fields to the exact column names used in the SQL. Use "
        "an empty string for a role the sheet does not have.\n"
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
