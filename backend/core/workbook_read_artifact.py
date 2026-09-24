"""Structured workbook read artifacts and target coverage."""
from __future__ import annotations

import hashlib
import io
import re
from typing import Any, Dict, List, Optional, Sequence

_TARGET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]{1,10}(?:-[A-Za-z0-9]+)*[0-9][A-Za-z0-9-]*|[0-9]{2,6})(?![A-Za-z0-9])"
)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_PRICE_HEADER_RE = re.compile(
    r"price|cost|amount|rate|value|msrp|list|wholesale|dealer|currency",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(
    r"\b(?:CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\b|"
    r"\[[$€£¥₹₩₽₺-][^\]]*\]",
    re.IGNORECASE,
)


def _canonical(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _is_year(value: str) -> bool:
    return bool(_YEAR_RE.fullmatch(str(value or "").strip()))


def extract_targets(
    query: str = "", context_texts: Optional[Sequence[str]] = None,
    explicit: Optional[Sequence[str]] = None,
) -> List[str]:
    """Extract likely item/model identifiers without treating years as targets."""
    values: List[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or _is_year(text):
            return
        canonical = _canonical(text)
        if len(canonical) < 2 or canonical in seen:
            return
        seen.add(canonical)
        values.append(text)

    for value in explicit or []:
        add(value)
    if values:
        return values[:64]
    for text in [query or "", *(context_texts or [])]:
        for match in _TARGET_RE.finditer(str(text or "")):
            add(match.group(0))
    return values[:64]


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _matches_target(target: str, value: Any) -> bool:
    text = _cell_text(value)
    if not text:
        return False
    canonical = _canonical(target)
    if not canonical:
        return False
    value_canonical = _canonical(text)
    if canonical in value_canonical:
        if canonical.isdigit():
            return re.search(
                rf"(?<!\d){re.escape(canonical)}(?!\d)", str(text)
            ) is not None
        return True
    return False


def _currency_for(
    value: Any, number_format: str, header: str
) -> Dict[str, str]:
    header_text = str(header or "")
    format_text = str(number_format or "")
    explicit = _CURRENCY_RE.search(f"{header_text} {format_text}")
    if explicit:
        token = explicit.group(0).upper()
        for code in ("CAD", "USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "INR", "MXN", "BRL", "ZAR"):
            if code in token:
                return {"currency": code, "currency_hint": token}
    if "$" in format_text or "$" in header_text:
        return {"currency": "unspecified", "currency_hint": "$"}
    if "€" in format_text or "€" in header_text:
        return {"currency": "unspecified", "currency_hint": "€"}
    if "£" in format_text or "£" in header_text:
        return {"currency": "unspecified", "currency_hint": "£"}
    return {"currency": "unspecified", "currency_hint": ""}


def _fallback_artifact(
    content: bytes,
    file_name: str,
    targets: Sequence[str],
    provider: Optional[str],
    resource_id: Optional[str],
    source_metadata: Optional[Dict[str, Any]],
    error: str,
) -> Dict[str, Any]:
    return {
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_length": len(content),
        "sheets": [],
        "sheet_count": 0,
        "all_sheets_searched": False,
        "truncated": True,
        "formula_status": "unavailable",
        "coverage": {
            "requested": list(targets),
            "outcomes": [
                {
                    "target": target,
                    "status": "incomplete",
                    "reason": error,
                    "evidence": [],
                }
                for target in targets
            ],
            "complete": False,
        },
        "source_metadata": dict(source_metadata or {}),
    }


def inspect_workbook_bytes(
    content: bytes,
    file_name: str,
    *,
    query: str = "",
    context_texts: Optional[Sequence[str]] = None,
    targets: Optional[Sequence[str]] = None,
    provider: Optional[str] = None,
    resource_id: Optional[str] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read every worksheet once and return one outcome per requested target."""
    requested = extract_targets(query, context_texts, targets)
    try:
        import openpyxl
    except Exception as exc:
        return _fallback_artifact(
            content, file_name, requested, provider, resource_id,
            source_metadata, f"openpyxl unavailable: {exc}",
        )

    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(content), data_only=False, read_only=False,
            keep_links=False,
        )
        values_workbook = openpyxl.load_workbook(
            io.BytesIO(content), data_only=True, read_only=False,
            keep_links=False,
        )
    except Exception as exc:
        return _fallback_artifact(
            content, file_name, requested, provider, resource_id,
            source_metadata, f"workbook parse failed: {exc}",
        )

    evidence: Dict[str, List[Dict[str, Any]]] = {
        target: [] for target in requested
    }
    sheets: List[Dict[str, Any]] = []
    formula_states: List[str] = []

    for worksheet in workbook.worksheets:
        value_sheet = values_workbook[worksheet.title]
        rows = list(worksheet.iter_rows())
        header_map: Dict[int, str] = {}
        header_rows: List[int] = []
        for row_index, row in enumerate(rows[:12], start=1):
            values = [cell for cell in row if _cell_text(cell.value)]
            if len(values) >= 2 and len(header_rows) < 3:
                header_rows.append(row_index)
                for cell in values:
                    if cell.column not in header_map:
                        header_map[cell.column] = _cell_text(cell.value)
        for row in rows:
            row_number = row[0].row if row else 0
            row_values = [
                {"cell": cell.coordinate, "value": _cell_text(cell.value)}
                for cell in row if _cell_text(cell.value)
            ]
            for cell in row:
                value = cell.value
                text = _cell_text(value)
                if not text:
                    continue
                is_formula = isinstance(value, str) and value.startswith("=")
                if is_formula:
                    cached = value_sheet[cell.coordinate].value
                    formula_state = "cached" if cached is not None else "unavailable"
                    formula_states.append(formula_state)
                else:
                    formula_state = "literal"
                for target in requested:
                    if not _matches_target(target, text):
                        continue
                    price_columns = [
                        (column, name) for column, name in header_map.items()
                        if _PRICE_HEADER_RE.search(str(name))
                    ]
                    prices: List[Dict[str, Any]] = []
                    for column, name in price_columns:
                        source_cell = worksheet.cell(row=row_number, column=column)
                        source_value = source_cell.value
                        cached_value = value_sheet.cell(
                            row=row_number, column=column
                        ).value
                        display_value = (
                            cached_value if isinstance(source_value, str)
                            and source_value.startswith("=") else source_value
                        )
                        price_currency = _currency_for(
                            display_value, source_cell.number_format, name
                        )
                        prices.append({
                            "cell": source_cell.coordinate,
                            "value": _cell_text(display_value),
                            "column": name,
                            "price_basis": _cell_text(name),
                            **price_currency,
                            "formula_state": (
                                "cached" if isinstance(source_value, str)
                                and source_value.startswith("=")
                                and cached_value is not None else "literal"
                            ),
                        })
                    if len(evidence[target]) < 32:
                        evidence[target].append({
                            "sheet": worksheet.title,
                            "row": row_number,
                            "cell": cell.coordinate,
                            "value": text,
                            "formula": value if is_formula else None,
                            "formula_state": formula_state,
                            "row_context": row_values[:40],
                            "prices": prices,
                        })
        sheets.append({
            "name": worksheet.title,
            "max_row": int(worksheet.max_row or 0),
            "max_column": int(worksheet.max_column or 0),
            "header_rows": header_rows,
            "headers": {str(column): name for column, name in header_map.items()},
            "merged_ranges": [str(item) for item in list(worksheet.merged_cells.ranges)[:200]],
            "searched": True,
        })

    outcomes: List[Dict[str, Any]] = []
    for target in requested:
        found = evidence[target]
        if not found:
            outcomes.append({
                "target": target,
                "status": "absent",
                "evidence": [],
            })
            continue
        status = "found" if len(found) == 1 else "ambiguous"
        outcomes.append({
            "target": target,
            "status": status,
            "evidence": found if status == "ambiguous" else found[:1],
        })

    return {
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_length": len(content),
        "sheets": sheets,
        "sheet_count": len(sheets),
        "all_sheets_searched": True,
        "truncated": False,
        "formula_status": (
            "cached" if formula_states and all(s == "cached" for s in formula_states)
            else "mixed" if formula_states else "not_present"
        ),
        "coverage": {
            "requested": requested,
            "outcomes": outcomes,
            "complete": all(
                outcome["status"] in ("found", "ambiguous", "absent")
                for outcome in outcomes
            ),
        },
        "source_metadata": dict(source_metadata or {}),
    }


def _column_letter(index: int) -> str:
    result = ""
    value = int(index)
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def inspect_dataset_entries(
    entries: Sequence[Dict[str, Any]],
    file_name: str,
    *,
    query: str = "",
    context_texts: Optional[Sequence[str]] = None,
    targets: Optional[Sequence[str]] = None,
    provider: Optional[str] = None,
    resource_id: Optional[str] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the same artifact from materialized sheet Parquet entries."""
    requested = extract_targets(query, context_texts, targets)
    evidence: Dict[str, List[Dict[str, Any]]] = {target: [] for target in requested}
    sheets: List[Dict[str, Any]] = []
    complete = True
    formula_states: List[str] = []
    try:
        import pandas as pd
    except Exception as exc:
        return _fallback_artifact(
            b"", file_name, requested, provider, resource_id,
            source_metadata, f"pandas unavailable: {exc}",
        )

    for entry in entries:
        path = str(entry.get("parquet_path") or "")
        sheet_name = str(entry.get("entity_name") or entry.get("sheet_name") or "")
        if not path or not sheet_name:
            complete = False
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            complete = False
            continue
        columns = [str(column) for column in frame.columns]
        row_column = "__sheet_row" if "__sheet_row" in frame.columns else None
        formula_map: Dict[str, Any] = {}
        try:
            from core.sheet_dataset_service import load_formulas_for_parquet

            formula_map = load_formulas_for_parquet(path) or {}
        except Exception:
            formula_map = {}

        for row_index, row in frame.iterrows():
            row_number = row.get(row_column) if row_column else row_index + 1
            row_context = [
                {"cell": f"{_column_letter(column_index + 1)}{row_number}",
                 "value": _cell_text(value)}
                for column_index, value in enumerate(row.tolist())
                if _cell_text(value)
            ][:40]
            for column_index, (column, value) in enumerate(zip(columns, row.tolist()), start=1):
                text = _cell_text(value)
                if not text:
                    continue
                cell_ref = f"{_column_letter(column_index)}{row_number}"
                formula_states.append("cached" if cell_ref in formula_map else "literal")
                for target in requested:
                    if not _matches_target(target, text):
                        continue
                    prices = []
                    for price_index, price_column in enumerate(columns, start=1):
                        if not _PRICE_HEADER_RE.search(price_column):
                            continue
                        price_value = row.iloc[price_index - 1]
                        prices.append({
                            "cell": f"{_column_letter(price_index)}{row_number}",
                            "value": _cell_text(price_value),
                            "column": price_column,
                            "price_basis": price_column,
                            **_currency_for(price_value, "", price_column),
                            "formula_state": "literal",
                        })
                    if len(evidence[target]) < 32:
                        evidence[target].append({
                            "sheet": sheet_name,
                            "row": int(row_number) if str(row_number).isdigit() else row_number,
                            "cell": cell_ref,
                            "value": text,
                            "formula": formula_map.get(cell_ref),
                            "formula_state": "cached" if cell_ref in formula_map else "literal",
                            "row_context": row_context,
                            "prices": prices,
                        })
        sheets.append({
            "name": sheet_name,
            "max_row": int(frame.shape[0]),
            "max_column": int(frame.shape[1]),
            "headers": {str(i + 1): column for i, column in enumerate(columns)},
            "header_rows": [],
            "merged_ranges": [],
            "searched": True,
        })

    outcomes = []
    for target in requested:
        found = evidence[target]
        status = "found" if len(found) == 1 else "ambiguous" if found else "absent"
        outcomes.append({
            "target": target,
            "status": status,
            "evidence": found if status == "ambiguous" else found[:1],
        })
    return {
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "sha256": sha256,
        "byte_length": None,
        "sheets": sheets,
        "sheet_count": len(sheets),
        "all_sheets_searched": complete,
        "truncated": not complete,
        "formula_status": "cached" if formula_states and all(s == "cached" for s in formula_states) else "mixed" if formula_states else "not_present",
        "coverage": {
            "requested": requested,
            "outcomes": outcomes,
            "complete": complete and all(
                outcome["status"] in ("found", "ambiguous", "absent")
                for outcome in outcomes
            ),
        },
        "source_metadata": dict(source_metadata or {}),
    }


def render_workbook_artifact(artifact: Dict[str, Any]) -> str:
    """Render compact, citable coverage for the model evidence block."""
    if not artifact:
        return ""
    lines = [
        "WORKBOOK READ ARTIFACT: "
        f"{artifact.get('file_name') or 'unnamed file'} "
        f"(resource_id={artifact.get('resource_id')}, "
        f"sha256={artifact.get('sha256')}, sheets={artifact.get('sheet_count')}, "
        f"all_sheets_searched={artifact.get('all_sheets_searched')}, "
        f"truncated={artifact.get('truncated')}, "
        f"formula_status={artifact.get('formula_status')})"
    ]
    coverage = artifact.get("coverage") or {}
    for outcome in coverage.get("outcomes") or []:
        target = outcome.get("target")
        status = outcome.get("status")
        refs = []
        for item in outcome.get("evidence") or []:
            ref = f"{item.get('sheet')}!{item.get('cell')}"
            value = item.get("value")
            if value:
                ref += f"={value}"
            refs.append(ref)
        lines.append(
            f"TARGET {target}: {status.upper()}"
            + (f" | {'; '.join(refs[:8])}" if refs else "")
        )
        for item in (outcome.get("evidence") or [])[:2]:
            for price in item.get("prices") or []:
                lines.append(
                    f"  PRICE {target} | {price.get('cell')} | "
                    f"{price.get('value')} | basis={price.get('price_basis')} | "
                    f"currency={price.get('currency')} | "
                    f"formula_state={price.get('formula_state')}"
                )
    if not coverage.get("complete", False):
        lines.append("WORKBOOK COVERAGE: INCOMPLETE")
    return "\n".join(lines)
