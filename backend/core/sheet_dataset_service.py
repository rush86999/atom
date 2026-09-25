"""Materialize ingested spreadsheets into SQL-queryable datasets.

Why: exact-value questions over workbooks ("price of WG-350DSAV in the
consolidated price list") were answered from query-anchored TEXT excerpts of
the parsed file — and the excerpt window was the recurring failure mode
(commits c0e54c075, 8c665d7ef exist solely because the answer row sat just
outside it). In-context table reading measurably degrades with size
(NeedleInATable, arXiv 2504.06560: GPT-4o 50%→17% from 8×8→32×32 tables) and
full-context injection fails past ~50K cells (arXiv 2603.06503: 55–68% vs
97–99% for structured access). Production conversational-analytics harnesses
(Genie, Fabric data agents, Cortex Analyst) route value questions to SQL over
curated tables for the same reason.

What this service does: for every spreadsheet already being content-ingested
(when it flows through process_file_bytes), extract each sheet as a typed
DataFrame, write one Parquet file per sheet under
backend/data/sheet_datasets/{workspace}/, and register it in the
`dataset_entries` catalog (core/models.py DatasetEntry). Agents then query it
through the EXISTING data tools: find_datasets → load_registered_dataset →
query_data (DuckDB SQL over the DataFrame). No new query mechanism.

Freshness contract: rows are keyed on the source byte hash. Same hash → the
materialized copy is reused (zero re-parse); a changed source becomes a NEW
version (old row marked superseded, Parquet GC'd to the last 2 versions), so
a stale copy can never masquerade as current. The cloud file stays the
durable store of record (AGENTS.md: stale caches shadowing durable state).

Conventions deliberately shared with the existing text extractor
(auto_document_ingestion._parse_xlsx): first row is the header, and pandas
row 0 == sheet row 2 — the `__sheet_row` column carries that number so a
dataset answer cites the same R# an excerpt would.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Column carrying the original sheet row number (pandas index 0 == sheet
# row 2 — same R# convention as the text extractor, so citations agree).
SHEET_ROW_COL = "__sheet_row"

# Cost guards. Materialization only runs where content is already being
# ingested, so these bound pathological files, not normal traffic.
_MAX_ROWS_PER_SHEET = int(os.getenv("ATOM_SHEET_DATASET_MAX_ROWS", "500000"))
# Secrets: the whole frame is scanned serialized (char-capped like the text
# extraction budget). A flagged sheet is either per-cell redacted (small) or
# skipped entirely (huge) — secrets never reach the Parquet store unredacted.
_REDACT_SCAN_MAX_CHARS = 4_000_000
_REDACT_CELL_CAP = 200_000
# Superseded versions kept on disk per source file before GC (safety net for
# "the user reverted the file" moments).
_VERSIONS_TO_KEEP = 2

# Module-level so no f-string expression contains a backslash: Python ≤3.11
# (the server runtime) rejects that at compile time, which made this whole
# module silently unimportable on the server while tests (3.14) stayed green.
_PARQUET_NAME_SAFE_RE = re.compile(r"[^A-Za-z0-9_\-]")

# Strict numeric-string pattern used ONLY by the raw-XML grid path: plain
# decimals without leading zeros ("14145.00" yes, "02139" no — part codes and
# ZIPs must stay strings).
_PLAIN_DECIMAL_RE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?")


def _promote_numeric_strings(series):
    """Raw-XML cells arrive as strings. Promote a column to numbers when
    EVERY non-empty value is a plain decimal — keeps SQL comparisons numeric
    without ever stripping a leading zero from a code."""
    import pandas as pd

    if series.dtype != object:
        return series
    non_empty = [str(v).strip() for v in series if str(v).strip()]
    if not non_empty:
        return series
    if all(_PLAIN_DECIMAL_RE.fullmatch(v) for v in non_empty):
        return pd.to_numeric(series, errors="coerce")
    return series

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

_SHEET_EXTENSIONS = {"xlsx", "xls", "xlsm", "csv"}


def sheet_datasets_enabled() -> bool:
    """Kill switch: ATOM_SHEET_DATASETS=0 disables materialization and the
    dataset tools degrade to 'no datasets registered'."""
    return os.getenv("ATOM_SHEET_DATASETS", "1") != "0"


def datasets_root() -> Path:
    """Anchor under backend/data regardless of CWD (root-vs-backend launches
    forked LanceDB stores and DB URLs before — AGENTS.md path anchoring)."""
    env_dir = os.getenv("ATOM_DATA_DIR", "")
    base = Path(env_dir) if env_dir and Path(env_dir).is_absolute() else _BACKEND_ROOT / "data"
    return base / "sheet_datasets"


@contextmanager
def _catalog_session():
    """Session over the catalog. Imported lazily so the module loads in
    processes that never touch the DB (tests patch core.database.engine)."""
    from core.database import get_db_session

    with get_db_session() as db:
        yield db


# ─────────────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_columns(raw_cols: List[Any]) -> List[str]:
    """Header normalization shared by every sheet: collapse whitespace, clip,
    fill blank/Unnamed columns with positional c1..cn, dedupe. Avoids
    colliding with the __sheet_row meta column."""
    seen: Dict[str, bool] = {}
    out: List[str] = []
    for i, col in enumerate(raw_cols):
        name = " ".join(str(col).split()) if col is not None else ""
        if not name or name.lower() == "nan" or name.lower().startswith("unnamed"):
            name = f"c{i + 1}"
        name = name[:64]
        if name == SHEET_ROW_COL:
            name = f"{SHEET_ROW_COL}_src"
        base, n = name, 2
        while name in seen:
            name = f"{base}_{n}"
            n += 1
        seen[name] = True
        out.append(name)
    return out


def _stabilize_column(series):
    """Make a column Parquet-safe without destroying queryability. Excel
    columns routinely mix types (a totals row's label under a numeric
    column). Prefer numeric when coercion is lossless — keeps SQL comparisons
    numeric; otherwise fall back to strings."""
    import pandas as pd

    if series.dtype != object:
        return series
    non_null = series.dropna()
    if non_null.map(type).nunique() <= 1:
        return series
    as_num = pd.to_numeric(series, errors="coerce")
    if as_num.notna().sum() == series.notna().sum():
        return as_num
    return series.map(
        lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v)
    )


def _col_index(letters: str) -> int:
    """'C' -> 2, 'AA' -> 26 — zero-based column index from cell-ref letters."""
    idx = 0
    for ch in (letters or ""):
        if ch.isalpha():
            idx = idx * 26 + (ord(ch.upper()) - 64)
    return max(0, idx - 1)


def _xlsx_raw_grid_frames(content: bytes) -> List[tuple]:
    """Raw-XML fallback for Zoho Sheet exports that pandas/openpyxl reject
    ('could not read strings from None' — unusual sharedStrings content).
    The file is well-formed XML, so walk it directly.

    Mirrors the XML walking of DocumentParser._parse_xlsx_raw
    (auto_document_ingestion.py) — deliberately a separate implementation:
    that parser is the production TEXT path of last resort and stays
    untouched. Header convention is the same (first row with >=2 non-blank
    cells), and __sheet_row carries the ACTUAL worksheet row numbers, so
    dataset answers cite the same R# the text excerpts do.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    import pandas as pd

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def _cell_value(c) -> str:
        ctype = c.get("t")
        if ctype == "inlineStr":
            return "".join(t.text or "" for t in c.iter() if _local(t.tag) == "t")
        v = next((ch for ch in c if _local(ch.tag) == "v"), None)
        if v is None:
            return ""
        if ctype == "s":
            try:
                return shared[int(v.text)]
            except (ValueError, IndexError):
                return v.text or ""
        return v.text or ""

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root:
                if _local(si.tag) == "si":
                    shared.append(
                        "".join(t.text or "" for t in si.iter() if _local(t.tag) == "t")
                    )

        names: Dict[str, str] = {}
        try:
            wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
            rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_to_target = {
                rel.get("Id"): rel.get("Target", "")
                for rel in rels_root
                if _local(rel.tag) == "Relationship"
            }
            for sheet in wb_root.iter():
                if _local(sheet.tag) != "sheet":
                    continue
                rid = sheet.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                target = (rid_to_target.get(rid, "") or "").lstrip("/")
                if target and not target.startswith("xl/"):
                    target = f"xl/{target}"
                if target:
                    names[target] = sheet.get("name") or target
        except Exception as name_err:  # noqa: BLE001 — names best-effort
            logger.debug(f"workbook sheet-name read failed: {name_err}")

        out: List[tuple] = []
        sheets = sorted(
            n for n in zf.namelist()
            if n.startswith("xl/worksheets/") and n.endswith(".xml")
        )
        for sheet_path in sheets:
            sheet_name = names.get(sheet_path, sheet_path.rsplit("/", 1)[-1])
            root = ET.fromstring(zf.read(sheet_path))
            grid: Dict[int, Dict[int, str]] = {}
            rownum_fallback = 0
            for row in root.iter():
                if _local(row.tag) != "row":
                    continue
                try:
                    row_num = int(row.get("r"))
                except (TypeError, ValueError):
                    rownum_fallback += 1
                    row_num = rownum_fallback
                cells: Dict[int, str] = {}
                for c in row:
                    if _local(c.tag) != "c":
                        continue
                    val = _cell_value(c)
                    if val and str(val).strip():
                        cells[_col_index("".join(ch for ch in (c.get("r") or "") if ch.isalpha()))] = str(val)
                if cells:
                    grid[row_num] = cells

            # Header detection, generic for exported business sheets. A
            # header row is TEXT-HEAVY (labels: 'Part Number', 'List Price',
            # ...); a wide NUMERIC row is data masquerading as a header (the
            # LINMAC sheet's first item row has 14 numeric cells and
            # out-spreads the real header — the densest-row heuristic picked
            # it and left every column labeled with that row's values).
            # Preference: first text-heavy row with ≥3 cells in the top band
            # → first text-heavy row with ≥2 → densest row (a numeric-heavy
            # sheet with no text header at all → positional columns, all rows
            # are data). Repeated section headers (same cells as the chosen
            # header, repeated per product block) are excluded from data.
            numeric_re = re.compile(r"-?\d+(?:\.\d+)?")

            def _header_like(rn: int) -> bool:
                vals = [str(v).strip() for v in grid[rn].values() if str(v).strip()]
                if not vals:
                    return False
                non_numeric = sum(1 for v in vals if not numeric_re.fullmatch(v))
                return non_numeric >= max(2, int(0.6 * len(vals)))

            header_row_num = None
            for rn in sorted(grid)[:10]:
                if len(grid[rn]) >= 2 and _header_like(rn):
                    header_row_num = rn
                    break
            header_rows: List[int] = []
            if header_row_num is not None:
                header_rows.append(header_row_num)
                for rn in sorted(grid):
                    if rn <= header_row_num:
                        continue
                    if len(header_rows) >= 3:
                        break
                    if len(grid[rn]) < 2 or not _header_like(rn):
                        break
                    vals = [str(v).strip() for v in grid[rn].values() if str(v).strip()]
                    has_label = any(
                        re.search(
                            r"id|name|code|sku|item|model|part|product|description|"
                            r"date|time|status|version|quantity|qty|stock|weight|"
                            r"price|cost|amount|value|rate|lead|expiry|expiration|"
                            r"certification|organization|company|minimum|required",
                            value,
                            re.IGNORECASE,
                        )
                        for value in vals
                    )
                    if not has_label:
                        break
                    header_rows.append(rn)
            headerless = not header_rows
            n_cols = (max((max(r) for r in grid.values()), default=0)) + 1
            if headerless:
                columns = _normalize_columns([f"c{i + 1}" for i in range(n_cols)])
                data_start = 0
            else:
                combined: Dict[int, List[str]] = {}
                for header_rn in header_rows:
                    for column_index, value in grid[header_rn].items():
                        text = str(value).strip()
                        if text and text not in combined.setdefault(column_index, []):
                            combined[column_index].append(text)
                columns = _normalize_columns([
                    " ".join(combined.get(i, [])) for i in range(n_cols)
                ])
                data_start = max(header_rows)
            data: List[List[str]] = []
            row_numbers: List[int] = []
            header_vals = {
                str(value).strip()
                for header_rn in header_rows
                for value in grid[header_rn].values()
            }
            for rn in sorted(grid):
                if not headerless and rn < data_start:
                    continue
                row_cells = grid[rn]
                values = [row_cells.get(i, "") for i in range(n_cols)]
                if not any(str(v).strip() for v in values):
                    continue
                if not headerless and set(row_cells.values()) <= header_vals:
                    continue
                data.append(values)
                row_numbers.append(rn)
            if not data:
                continue
            source_row_count = len(data)
            data = data[:_MAX_ROWS_PER_SHEET]
            row_numbers = row_numbers[: len(data)]
            df = pd.DataFrame(data, columns=columns)
            df[SHEET_ROW_COL] = row_numbers
            for col in df.columns:
                if col != SHEET_ROW_COL:
                    df[col] = _promote_numeric_strings(df[col])
            df.attrs["_atom_source_row_count"] = source_row_count
            df.attrs["_atom_truncated"] = source_row_count > len(data)
            out.append((str(sheet_name), df))
        return out


def _extract_sheet_frames(content: bytes, file_ext: str, file_name: str) -> List[tuple]:
    """(sheet_name, DataFrame) for every sheet. First row is the header —
    the same convention (and the same pandas call) as the text extractor, so
    __sheet_row and excerpt R# citations always refer to the same row."""

    import pandas as pd

    ext = (file_ext or "").lower().lstrip(".")
    if ext == "csv":
        df = pd.read_csv(io.BytesIO(content))
        return [(_sheet_stem(file_name), _frame_with_sheet_rows(df))]
    if ext not in _SHEET_EXTENSIONS:
        return []
    try:
        # sheet_name=None → ALL sheets (the text extractor dropped a real
        # pricing sheet when a 5-sheet cap existed; caps here bound rows,
        # never sheets).
        frames = pd.read_excel(
            io.BytesIO(content), sheet_name=None, header=None
        )
    except Exception as pd_err:
        # Zoho Sheet exports trip openpyxl's sharedStrings reader — the same
        # quirk the text path's raw-XML fallback exists for (live 2026-09-07:
        # the flagship Consolidated Price List 2019.xlsx). The workbook is
        # still well-formed XML: build the frames straight from it.
        logger.info(
            f"sheet datasets: pandas failed on {file_name} "
            f"({type(pd_err).__name__}); trying raw-XML grid"
        )
        raw = _xlsx_raw_grid_frames(content)
        if raw:
            return raw
        raise
    out: List[tuple] = []
    for sheet_name, df in frames.items():
        out.append((str(sheet_name), _frame_with_inferred_headers(df)))
    return out


def _frame_with_sheet_rows(df):
    source_row_count = len(df.index)
    df = df.iloc[:_MAX_ROWS_PER_SHEET].copy()
    df.columns = _normalize_columns(list(df.columns))
    # R# convention: pandas index 0 == sheet row 2 (row 1 is the header).
    df[SHEET_ROW_COL] = df.index + 2
    for col in df.columns:
        if col != SHEET_ROW_COL:
            df[col] = _stabilize_column(df[col])
    df.attrs["_atom_source_row_count"] = source_row_count
    df.attrs["_atom_truncated"] = source_row_count > len(df.index)
    return df


def _frame_coverage(df) -> Dict[str, Any]:
    source_rows = df.attrs.get("_atom_source_row_count")
    return {
        "known": source_rows is not None,
        "source_row_count": int(source_rows) if source_rows is not None else None,
        "materialized_row_count": int(len(df.index)),
        "truncated": bool(df.attrs.get("_atom_truncated", False)),
        "row_cap": _MAX_ROWS_PER_SHEET,
    }


def _frame_with_inferred_headers(df):
    import pandas as pd

    raw = df.copy()
    values = raw.to_numpy(dtype=object)
    primary = None
    for index, row in enumerate(values[:12]):
        nonempty = [str(value).strip() for value in row if str(value).strip()]
        if len(nonempty) < 2:
            continue
        numeric = sum(
            bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value))
            for value in nonempty
        )
        if numeric <= max(1, int(len(nonempty) * 0.4)):
            primary = index
            break
    if primary is None:
        primary = 0
        header_indices = []
    else:
        header_indices = [primary]
        for index in range(primary + 1, min(len(values), primary + 4)):
            row = values[index]
            nonempty = [str(value).strip() for value in row if str(value).strip()]
            if len(nonempty) < 2:
                break
            numeric = sum(
                bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value))
                for value in nonempty
            )
            has_label = any(
                re.search(
                    r"id|name|code|sku|item|model|part|product|description|"
                    r"date|time|status|version|quantity|qty|stock|weight|"
                    r"price|cost|amount|value|rate|lead|expiry|expiration|"
                    r"certification|organization|company|minimum|required",
                    value,
                    re.IGNORECASE,
                )
                for value in nonempty
            )
            if numeric > max(1, int(len(nonempty) * 0.4)) or not has_label:
                break
            header_indices.append(index)
    width = max((len(row) for row in values), default=0)
    labels: List[List[str]] = [[] for _ in range(width)]
    for index in header_indices:
        for column_index, value in enumerate(values[index]):
            try:
                missing = bool(pd.isna(value))
            except (TypeError, ValueError):
                missing = False
            text = "" if value is None or missing else str(value).strip()
            if text and text not in labels[column_index]:
                labels[column_index].append(text)
    if not any(labels):
        labels = [[f"c{index + 1}"] for index in range(width)]
    data_start = (header_indices[-1] + 1) if header_indices else 0
    source_data = raw.iloc[data_start:]
    source_row_count = len(source_data.index)
    data = source_data.iloc[:_MAX_ROWS_PER_SHEET].copy().reset_index(drop=True)
    data.columns = _normalize_columns([" ".join(items) for items in labels])
    source_rows = [
        int(index) + 1 if str(index).isdigit() else index + 1
        for index in source_data.index[:_MAX_ROWS_PER_SHEET]
    ]
    data[SHEET_ROW_COL] = source_rows
    for col in data.columns:
        if col != SHEET_ROW_COL:
            data[col] = _stabilize_column(data[col])
    data.attrs["_atom_source_row_count"] = source_row_count
    data.attrs["_atom_truncated"] = source_row_count > len(data.index)
    data.attrs["_atom_header_rows"] = [index + 1 for index in header_indices]
    return data


def _column_schema_json(df, coverage: Optional[Dict[str, Any]] = None) -> str:
    """Per-column name + up to 3 sample values — the semantic layer of this
    catalog. Sample values are what let the NL→SQL step pick types and the
    right sheet without reading the Parquet files first (the Genie/Fabric
    lesson: agent accuracy tracks schema description quality)."""
    import json as _json

    schema = []
    for col in df.columns:
        samples: List[str] = []
        if col != SHEET_ROW_COL:
            for v in df[col].dropna().head(8):
                s = str(v).strip()
                if s and s not in samples:
                    samples.append(s[:24])
                if len(samples) >= 3:
                    break
        schema.append({"name": col, "samples": samples})
    if coverage is not None:
        return _json.dumps({"columns": schema, "coverage": coverage})
    return _json.dumps(schema)


def _sheet_stem(file_name: str) -> str:
    stem = Path(file_name or "csv").stem.strip() or "csv"
    return stem[:64]


def _redact_frames_if_needed(frames: List[tuple], file_name: str) -> List[tuple]:
    """Fail-closed secrets pass: a sheet whose serialized text trips the
    redactor either gets every string cell redacted (small sheets) or is
    skipped (huge ones). Never writes flagged-but-unredacted cells."""
    try:
        from core.secrets_redactor import get_secrets_redactor

        redactor = get_secrets_redactor()
    except Exception as red_err:  # noqa: BLE001 — no redactor: skip, don't leak
        logger.warning(f"sheet datasets: redactor unavailable ({red_err}); skipping {file_name}")
        return []

    kept: List[tuple] = []
    for sheet_name, df in frames:
        try:
            serialized = df.head(_MAX_ROWS_PER_SHEET).to_csv(index=False)[:_REDACT_SCAN_MAX_CHARS]
            if not redactor.redact(serialized).has_secrets:
                kept.append((sheet_name, df))
                continue
            cell_count = df.size
            if cell_count > _REDACT_CELL_CAP:
                logger.warning(
                    f"sheet datasets: '{sheet_name}' of {file_name} flagged for secrets "
                    f"but too large to per-cell redact ({cell_count} cells); skipping sheet"
                )
                continue
            def _redact_cell(v):
                if not isinstance(v, str) or not v:
                    return v
                return redactor.redact(v).redacted_text
            for col in df.columns:
                if col != SHEET_ROW_COL and df[col].dtype == object:
                    df[col] = df[col].map(_redact_cell)
            kept.append((sheet_name, df))
            logger.info(f"sheet datasets: redacted cells in '{sheet_name}' of {file_name}")
        except Exception as sheet_err:  # noqa: BLE001 — one bad sheet never blocks the file
            logger.warning(f"sheet datasets: secrets pass failed for '{sheet_name}': {sheet_err}")
    return kept


# ─────────────────────────────────────────────────────────────────────────────
# Naming + storage
# ─────────────────────────────────────────────────────────────────────────────


def _dataset_name(source: str, file_name: str, sheet_name: str, taken: set) -> str:
    raw = f"{source}_{_sheet_stem(file_name)}__{sheet_name}".lower()
    name = re.sub(r"[^a-z0-9_]+", "_", raw)[:80].strip("_") or "dataset"
    base, n = name, 2
    while name in taken:
        name = f"{base}_{n}"
        n += 1
    taken.add(name)
    return name


def _version_dir(workspace_id: str, content_hash: str) -> Path:
    safe_ws = re.sub(r"[^A-Za-z0-9_\-]", "_", workspace_id or "default")[:64] or "default"
    path = datasets_root() / safe_ws / content_hash[:12]
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_parquet_atomic(df, target: Path) -> None:
    # Unique tmp name: concurrent materializations of the same file (read-leg
    # task + ingestion funnel) share the target path — a shared .tmp name made
    # the loser's os.replace fail with ENOENT (live 2026-09-07).
    tmp = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, target)


# ─────────────────────────────────────────────────────────────────────────────
# Per-cell formula sidecar — pandas/Parquet carry only computed values, so a
# dataset answer could show WHAT a cell equals but never WHY (live 2026-09-09:
# the Trumatic-L3030S quote conversation had to reverse-engineer '=I11/0.95'
# from the numbers and missed three formula columns entirely). The ORIGINAL
# bytes are in hand at materialization time — the only moment they exist,
# because received mailbox attachments are never persisted — so the formula
# map is extracted then and stored as a sibling JSON beside each Parquet.
# ─────────────────────────────────────────────────────────────────────────────

_FORMULA_SIDECAR_SUFFIX = ".formulas.json"
# Noise bound for pathological workbooks (a full-column-fill price book can
# carry tens of thousands of shared-formula cells).
_MAX_FORMULA_CELLS = 5000


def _formula_sidecar_path(parquet_path) -> Path:
    p = Path(parquet_path)
    return p.with_name(p.name + _FORMULA_SIDECAR_SUFFIX)


def _write_formula_sidecar(target: Path, sheet_name: str, formulas: Dict[str, str]) -> None:
    sidecar = _formula_sidecar_path(target)
    try:
        tmp = sidecar.with_name(f"{sidecar.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(
            json.dumps({"sheet": sheet_name, "formulas": formulas}, ensure_ascii=False)
        )
        os.replace(tmp, sidecar)
    except OSError as err:
        logger.debug(f"formula sidecar write failed for {target.name}: {err}")


def load_formulas_for_parquet(parquet_path: str, max_cells: int = 5000) -> Dict[str, str]:
    """cell -> formula for one dataset Parquet's sheet ([] when no sidecar).

    ``max_cells`` used to default to 60, which made the sidecar effectively
    useless for any real sheet: the dict is in A1 order, so 60 cells covered
    roughly the first five rows. A derivation ask about a row further down (the
    F-5216 workbook's row 235 — the whole point of keeping formulas) rendered the
    formulas of UNRELATED rows and none of the ones being asked about (live
    2026-09-16). The sidecar is a few thousand short strings, so the full sheet is
    cheap to hold; the RENDERER is what keeps the prompt bounded, by emitting
    only the formulas for the rows that matched.
    """
    try:
        sidecar = _formula_sidecar_path(parquet_path)
        if not sidecar.exists():
            return {}
        data = json.loads(sidecar.read_text())
        formulas = data.get("formulas") or {}
        return dict(list(formulas.items())[:max_cells])
    except Exception as err:  # noqa: BLE001 — sidecar is additive, never fatal
        logger.debug(f"formula sidecar read failed for {parquet_path}: {err}")
        return {}


def _extract_formula_map(content: bytes, file_ext: str) -> Dict[str, Dict[str, str]]:
    """sheet -> {cell_ref: '=formula'} straight from the original workbook.

    xlsx/xlsm only (xls has no XML package; csv cannot carry formulas).
    openpyxl first, then the same raw-XML fallback the text extractor uses
    for openpyxl-hostile workbooks (Zoho Sheet exports)."""
    ext = (file_ext or "").lower().lstrip(".")
    if ext not in ("xlsx", "xlsm"):
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        try:
            for sheet_name in wb.sheetnames:
                cells: Dict[str, str] = {}
                for row in wb[sheet_name].iter_rows():
                    for cell in row:
                        v = cell.value
                        if isinstance(v, str) and v.startswith("="):
                            cells[cell.coordinate] = v
                            if len(cells) >= _MAX_FORMULA_CELLS:
                                break
                    if len(cells) >= _MAX_FORMULA_CELLS:
                        break
                if cells:
                    out[str(sheet_name)] = cells
        finally:
            wb.close()
        if out:
            return out
    except Exception as exc:  # noqa: BLE001 — fall through to raw XML
        logger.debug(
            f"formula map: openpyxl scan failed ({type(exc).__name__}); raw-XML fallback"
        )
    return _formula_map_raw_xml(content)


def _formula_map_raw_xml(content: bytes) -> Dict[str, Dict[str, str]]:
    """Stdlib-XML formula scan (namespace-agnostic) for openpyxl-hostile
    workbooks. Shared-formula DEPENDENT cells carry no <f> body in the
    package — the master cell's formula is captured; expanding shared ranges
    per dependent is deliberately skipped (the master is what an agent cites)."""
    import xml.etree.ElementTree as ET
    import zipfile

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    out: Dict[str, Dict[str, str]] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            sheet_display: Dict[str, str] = {}
            try:
                wb = ET.fromstring(zf.read("xl/workbook.xml"))
                rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
                rid_target = {
                    rel.get("Id"): rel.get("Target", "")
                    for rel in rels
                    if _local(rel.tag) == "Relationship"
                }
                for sh in wb.iter():
                    if _local(sh.tag) != "sheet":
                        continue
                    rid = sh.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )
                    target = (rid_target.get(rid) or "").lstrip("/")
                    if target and not target.startswith("xl/"):
                        target = f"xl/{target}"
                    if target:
                        sheet_display[target] = sh.get("name") or target
            except Exception:
                pass  # part filenames still work as sheet keys

            total = 0
            for sheet_path in sorted(
                n for n in zf.namelist()
                if n.startswith("xl/worksheets/") and n.endswith(".xml")
            ):
                sheet_name = sheet_display.get(
                    sheet_path, sheet_path.rsplit("/", 1)[-1]
                )
                cells: Dict[str, str] = {}
                root = ET.fromstring(zf.read(sheet_path))
                for row in root.iter():
                    if _local(row.tag) != "row":
                        continue
                    for c in row:
                        if _local(c.tag) != "c":
                            continue
                        f_el = next(
                            (ch for ch in c if _local(ch.tag) == "f"), None
                        )
                        ftext = (f_el.text or "").strip() if f_el is not None else ""
                        if not ftext:
                            continue
                        cells[c.get("r") or ""] = (
                            ftext if ftext.startswith("=") else f"={ftext}"
                        )
                        total += 1
                        if total >= _MAX_FORMULA_CELLS:
                            break
                    if total >= _MAX_FORMULA_CELLS:
                        break
                if cells:
                    out[sheet_name] = cells
                if total >= _MAX_FORMULA_CELLS:
                    break
    except Exception as err:  # noqa: BLE001 — best-effort by contract
        logger.debug(f"formula map: raw-XML scan failed: {err}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Catalog operations (sync; async wrappers below)
# ─────────────────────────────────────────────────────────────────────────────


def _column_letters(names: List[str]) -> Dict[str, str]:
    """Column NAME -> spreadsheet LETTER, by position.

    ``render_dataset_answer`` renders named columns, but the workbook's formulas
    address cells by letter (``F235``). The extractor writes headers positionally
    (its own fallback is literally ``c<i+1>``), so position IS the letter.
    Without this mapping a verifier cannot connect "Factory Price=5350" to the
    ``=F235*0.9`` that consumes it, and every dependency reads as unresolved
    (found while implementing the derivation verification contract, 2026-09-16).
    """
    out: Dict[str, str] = {}
    for i, name in enumerate(names or []):
        letter = ""
        n = i
        while True:
            letter = chr(ord("A") + (n % 26)) + letter
            n = n // 26 - 1
            if n < 0:
                break
        out[str(name)] = letter
    return out


def _entry_to_dict(row) -> Dict[str, Any]:
    import json as _json

    raw_schema = row.columns_json
    if isinstance(raw_schema, str):
        try:
            schema = _json.loads(raw_schema or "[]")
        except (TypeError, ValueError):
            schema = []
    elif isinstance(raw_schema, (list, dict)):
        schema = raw_schema
    else:
        schema = []
    coverage = {"known": False}
    if isinstance(schema, dict):
        coverage = schema.get("coverage") or {"known": False}
        schema = schema.get("columns") or []
    if not coverage.get("known") and row.row_count is not None:
        materialized_rows = int(row.row_count)
        coverage = {
            "known": materialized_rows < _MAX_ROWS_PER_SHEET,
            "source_row_count": materialized_rows,
            "materialized_row_count": materialized_rows,
            "truncated": materialized_rows >= _MAX_ROWS_PER_SHEET,
            "row_cap": _MAX_ROWS_PER_SHEET,
            "backfilled_from_catalog": True,
        }
    columns = [c["name"] if isinstance(c, dict) else str(c) for c in schema][:40]
    samples = {
        c["name"]: c.get("samples", [])
        for c in schema[:40] if isinstance(c, dict)
    }
    return {
        "id": row.id,
        "dataset_name": row.dataset_name,
        "entity_name": row.entity_name,
        "file_name": row.file_name,
        "source": row.source,
        "source_kind": row.source_kind,
        "external_id": row.external_id,
        "content_hash": row.content_hash,
        "content_hash_algorithm": "sha1",
        "source_metadata": getattr(row, "source_metadata", None) or {},
        "row_count": row.row_count or 0,
        "column_count": row.column_count or 0,
        "columns": columns,
        "column_samples": samples,
        "coverage": coverage,
        "source_modified_at": row.source_modified_at.isoformat() if row.source_modified_at else None,
        "ingested_at": row.ingested_at.isoformat() if row.ingested_at else None,
        "parquet_path": row.parquet_path,
    }


def materialize_sheet_bytes_sync(
    content: bytes,
    file_name: str,
    source: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    external_id: Optional[str] = None,
    source_modified_at=None,
) -> Dict[str, Any]:
    """Extract sheets → Parquet + catalog rows, idempotent per byte hash.

    Called from process_file_bytes (async wrapper below) — only for files
    whose content is already being ingested, so there is no extra download
    and no extra parse in the fresh-file case (hash check first).
    """
    if not sheet_datasets_enabled():
        return {"status": "disabled"}
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in _SHEET_EXTENSIONS:
        return {"status": "skipped", "reason": "not_a_sheet"}

    content_hash = hashlib.sha1(content or b"").hexdigest()
    # Canonical identity = the SOURCE-NATIVE id. Two call sites used two
    # conventions for the same file — the read leg passes the bare id while
    # the periodic-sync funnel passes "zoho_workdrive:{id}" — and a dataset
    # materialized by one was invisible to the other. Strip the source
    # prefix so both collapse to one key; content-address when absent.
    _raw_ext = str(external_id or "").strip()
    _prefix = f"{source}:"
    if _raw_ext.startswith(_prefix):
        _raw_ext = _raw_ext[len(_prefix):]
    file_key = _raw_ext or f"sha1:{content_hash}"
    ws_id = workspace_id or "default"

    from core.models import DatasetEntry

    with _catalog_session() as db:
        existing = (
            db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "file",
                DatasetEntry.source == source,
                DatasetEntry.external_id == file_key,
                DatasetEntry.status == "active",
                DatasetEntry.content_hash == content_hash,
            )
            .all()
        )
        if existing:
            # The bytes just hashed to this copy's own content_hash — the
            # source is PROVEN unchanged. Re-stamp ingested_at so the
            # freshness TTL reflects THIS verification. Without this, a copy
            # that went stale-by-TTL (reverify re-downloads identical bytes
            # → status 'current') stayed stale forever and every read kept
            # paying the live download instead of ever trusting the copy.
            now = datetime.now(timezone.utc)
            # Same proof backfills formula sidecars for datasets materialized
            # before they existed — the bytes are in hand right here, so the
            # natural re-download cycle (reverify / JIT pull / re-ingest)
            # heals pre-fix datasets one touch at a time. The existence check
            # makes this free after the first heal.
            missing_sidecar = [
                r
                for r in existing
                if not _formula_sidecar_path(r.parquet_path).exists()
            ]
            if missing_sidecar:
                try:
                    heal_map = _extract_formula_map(content, ext)
                except Exception as heal_err:  # noqa: BLE001 — sidecar is additive
                    logger.debug(f"formula sidecar backfill failed for {file_name}: {heal_err}")
                    heal_map = {}
                for row in missing_sidecar:
                    _write_formula_sidecar(
                        Path(row.parquet_path),
                        row.entity_name,
                        heal_map.get(row.entity_name, {}),
                    )
                logger.info(
                    f"sheet datasets: backfilled {len(missing_sidecar)} formula "
                    f"sidecar(s) for {file_name}"
                )
            for row in existing:
                row.ingested_at = now
            db.commit()
            return {
                "status": "current",
                "content_hash": content_hash,
                "datasets": [_entry_to_dict(r) for r in existing],
            }

    try:
        frames = _extract_sheet_frames(content, ext, file_name)
    except Exception as parse_err:  # noqa: BLE001 — graceful skip (e.g. Zoho
        # exports that pandas rejects; the text path has its own fallback)
        logger.info(f"sheet datasets: pandas could not parse {file_name} ({parse_err}); no dataset")
        return {"status": "skipped", "reason": f"parse_failed: {type(parse_err).__name__}"}
    frames = [(s, df) for s, df in frames if df is not None and len(df.columns) > 1]
    frames = [f for f in frames if len(f[1]) > 0]
    if not frames:
        return {"status": "skipped", "reason": "no_tabular_content"}
    frames = _redact_frames_if_needed(frames, file_name)
    if not frames:
        return {"status": "skipped", "reason": "secrets_unredactable"}

    # One formula-map extraction per file (the original bytes leave scope
    # after this call — attachments are never persisted).
    try:
        formula_map = _extract_formula_map(content, ext)
    except Exception as fm_err:  # noqa: BLE001 — sidecar is additive
        logger.debug(f"formula map extraction failed for {file_name}: {fm_err}")
        formula_map = {}

    taken_names: set = set()
    version_dir = _version_dir(ws_id, content_hash)
    registered: List[Dict[str, Any]] = []

    # Mtime-chain preservation: a re-materialization whose caller had no
    # connector mtime (e.g. the background re-verify after serving) must not
    # blank the freshness stamp — inherit the previous version's so hint-
    # equality checks keep working across re-verifies.
    effective_mtime = source_modified_at
    if effective_mtime is None:
        with _catalog_session() as db:
            from core.models import DatasetEntry as _DS

            prev = (
                db.query(_DS)
                .filter(
                    _DS.source_kind == "file",
                    _DS.source == source,
                    _DS.external_id == file_key,
                    _DS.status == "active",
                )
                .order_by(_DS.ingested_at.desc())
                .first()
            )
            effective_mtime = prev.source_modified_at if prev else None

    from core.models import DatasetEntry

    with _catalog_session() as db:
        for sheet_name, df in frames:
            # Per-sheet idempotency: a previous run may have crashed midway
            # through a multi-sheet file.
            already = (
                db.query(DatasetEntry)
                .filter(
                    DatasetEntry.source_kind == "file",
                    DatasetEntry.source == source,
                    DatasetEntry.external_id == file_key,
                    DatasetEntry.content_hash == content_hash,
                    DatasetEntry.entity_name == sheet_name,
                )
                .first()
            )
            if already:
                coverage = _frame_coverage(df)
                if not (_entry_to_dict(already).get("coverage") or {}).get("known"):
                    already.columns_json = _column_schema_json(df, coverage)
                    db.flush()
                registered.append(_entry_to_dict(already))
                if not _formula_sidecar_path(already.parquet_path).exists():
                    _write_formula_sidecar(
                        Path(already.parquet_path),
                        sheet_name,
                        formula_map.get(sheet_name, {}),
                    )
                continue
            ds_name = _dataset_name(source, file_name, sheet_name, taken_names)
            target = version_dir / f"{_PARQUET_NAME_SAFE_RE.sub('_', ds_name)}.parquet"
            try:
                _write_parquet_atomic(df, target)
            except Exception as write_err:  # noqa: BLE001 — Arrow can reject exotic frames
                logger.warning(f"sheet datasets: parquet write failed for '{sheet_name}': {write_err}")
                continue
            # Always written (empty when the sheet has no formulas) so the
            # sidecar's existence means "formulas extracted at this version".
            _write_formula_sidecar(
                target, sheet_name, formula_map.get(sheet_name, {})
            )
            coverage = _frame_coverage(df)
            row = DatasetEntry(
                workspace_id=ws_id,
                created_by=user_id,
                source_kind="file",
                source=source,
                external_id=file_key,
                file_name=file_name,
                content_hash=content_hash,
                entity_name=sheet_name,
                dataset_name=ds_name,
                parquet_path=str(target),
                row_count=int(len(df)),
                column_count=int(len(df.columns)),
                columns_json=_column_schema_json(df, coverage),
                source_modified_at=effective_mtime,
                status="active",
            )
            db.add(row)
            db.flush()
            registered.append(_entry_to_dict(row))

        if not registered:
            return {"status": "skipped", "reason": "parquet_write_failed"}

        # Supersede every other active version of this file, then GC disk.
        older = (
            db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "file",
                DatasetEntry.source == source,
                DatasetEntry.external_id == file_key,
                DatasetEntry.status == "active",
                DatasetEntry.content_hash != content_hash,
            )
            .all()
        )
        new_ids = {r["id"] for r in registered}
        stale_paths: List[str] = []
        for old in older:
            old.status = "superseded"
            old.superseded_by = next(iter(new_ids))
        db.commit()

        stale_paths = [
            r.parquet_path
            for r in db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "file",
                DatasetEntry.source == source,
                DatasetEntry.external_id == file_key,
                DatasetEntry.status == "superseded",
            )
            .order_by(DatasetEntry.ingested_at.desc())
            .offset(_VERSIONS_TO_KEEP)
            .all()
        ]
        if stale_paths:
            (
                db.query(DatasetEntry)
                .filter(DatasetEntry.parquet_path.in_(stale_paths))
                .delete(synchronize_session=False)
            )
            db.commit()

    for path in stale_paths:
        try:
            os.unlink(path)
        except OSError:
            pass
        try:
            os.unlink(str(_formula_sidecar_path(path)))
        except OSError:
            pass

    logger.info(
        f"sheet datasets: materialized {len(registered)} sheet(s) of {file_name} "
        f"(hash {content_hash[:12]})"
    )
    return {"status": "materialized", "content_hash": content_hash, "datasets": registered}


def find_entries_sync(query: str = "", user_id: Optional[str] = None,
                      workspace_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Catalog search for agents: token match over dataset/file/sheet names,
    active rows only, freshest first. Scoped by workspace when known; the
    catalog is a per-deployment derived cache, so NO user filter when only
    user_id is available — app-record datasets have no creator, and hiding
    them from the probe would defeat the whole point."""
    from core.models import DatasetEntry

    tokens = [t for t in re.split(r"[^a-z0-9]+", (query or "").lower()) if len(t) > 1]
    with _catalog_session() as db:
        q = db.query(DatasetEntry).filter(DatasetEntry.status == "active")
        if workspace_id:
            q = q.filter(DatasetEntry.workspace_id == workspace_id)
        rows = q.order_by(DatasetEntry.ingested_at.desc()).limit(500).all()
        if not tokens:
            return [_entry_to_dict(r) for r in rows[:limit]]
        scored = []
        for r in rows:
            hay = " ".join(
                filter(None, [r.dataset_name, r.file_name, r.entity_name, r.source])
            ).lower()
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda pair: (-pair[0],), )
        return [_entry_to_dict(r) for _, r in scored[:limit]]


def get_entry_by_name_sync(dataset_name: str) -> Optional[Dict[str, Any]]:
    from core.models import DatasetEntry

    with _catalog_session() as db:
        row = (
            db.query(DatasetEntry)
            .filter(DatasetEntry.dataset_name == dataset_name, DatasetEntry.status == "active")
            .first()
        )
        return _entry_to_dict(row) if row else None


def entries_for_file_sync(source: str, external_id: str) -> List[Dict[str, Any]]:
    """Active datasets for one source file — the read-path routing hint."""
    from core.models import DatasetEntry

    with _catalog_session() as db:
        rows = (
            db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "file",
                DatasetEntry.source == source,
                DatasetEntry.external_id == str(external_id or ""),
                DatasetEntry.status == "active",
            )
            .order_by(DatasetEntry.entity_name.asc())
            .limit(500)
            .all()
        )
        return [_entry_to_dict(r) for r in rows]


def catalog_has_entries_sync() -> bool:
    """Cheap availability gate for the planner service (cached upstream)."""
    from core.models import DatasetEntry

    with _catalog_session() as db:
        return db.query(DatasetEntry.id).filter(DatasetEntry.status == "active").first() is not None


def search_all_datasets_sync(
    query: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 5,
    max_files: int = 200,
    context_texts: Optional[List[str]] = None,
    name_context_texts: Optional[List[str]] = None,
    deadline: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Cross-file content probe: which ingested spreadsheet contains the
    question's identifying code?

    Candidate tokens come from the query and its surrounding context texts
    (history turns); each is scanned across the most recent files until one
    hits. Returns None when the query has no identifying token — callers
    fall back to memory. App-record datasets (source_kind='app_records') are
    scanned too, so this one probe covers files AND synced app entities.

    ``context_texts`` supplements the CANDIDATE (figure/code) tokens from earlier
    turns. ``name_context_texts`` supplements the NAME tokens and defaults to the
    query alone — see the note at its use for why history must not name files.
    """
    # `context_texts` may legitimately carry FIGURES from earlier turns (a "try
    # again" turn inherits the amount). It must NOT carry NAMES: an incidental
    # history word that happens to appear in one catalogued file name ("the vendor
    # quote" -> "vendor") becomes a spurious named file and hijacks the probe.
    # Callers that want name matching pass `name_context_texts` explicitly.
    _name_sources = list(name_context_texts) if name_context_texts is not None else [query]
    _name_tokens = set(distinctive_name_tokens(_name_sources))
    # Code/figure candidates may draw on history; the NAME decision does not, so
    # suppress this helper's own name fallback (see the note above).
    candidates = candidate_probe_tokens(
        [query] + list(context_texts or []), allow_name_fallback=False
    )
    if not candidates and not _name_tokens:
        return None
    entries = find_entries_sync("", user_id, workspace_id, 500)
    files: Dict[tuple, List[Dict[str, Any]]] = {}
    order: List[tuple] = []
    for e in entries:
        key = (e["source"], e["external_id"])
        if key not in files:
            files[key] = []
            order.append(key)
        files[key].append(e)
    order = order[:max_files]
    # A query that NAMES a file must reach that file. Token content-matching alone
    # does not do it: "vipul" occurs inside an unrelated vendor form and an
    # invoice export, and those matched before the workbook whose NAME contains
    # the word — the dataset lane then ran SQL against the wrong spreadsheet
    # (live 2026-09-16). Name matches are therefore ordered ahead of content-only
    # matches within each token's hits; both still require the token to be present
    # somewhere, so this reorders evidence rather than inventing it.
    # A word can name a file WITHOUT occurring in its content — "vipul" exists only
    # in "PRICE VIPUL (6).xlsx", so every content probe for it returns None and the
    # file the user named is unreachable (measured live 2026-09-16). When the query
    # names a catalogued file, probe THAT file using the query's numeric tokens
    # (the codes/amounts a derivation ask is about), and lead with the result.
    def _out_of_time() -> bool:
        """True once the caller's budget is spent.

        A scan that runs long must DEGRADE, not vanish: the caller wraps this in
        `asyncio.wait_for` and a timeout discards the whole result — so a slow
        catalog used to turn a partially-answered derivation into no evidence at
        all, which the reply then reported as "the lookup did not complete"
        (live 2026-09-16). Returning what was found, marked `incomplete`, keeps
        the answer as good as the work already done.
        """
        return deadline is not None and time.monotonic() > deadline

    if _name_tokens:
        # Numeric tokens the query already yielded (codes/amounts) are the ones
        # worth probing INSIDE the named file; fall back to the candidate itself.
        base_nums = [t for t in candidates if t.isdigit()]
        named: List[Dict[str, Any]] = []
        for key in order:
            if _out_of_time():
                break
            fname = str((files[key][0] or {}).get("file_name") or "").lower()
            if not any(t in fname for t in _name_tokens):
                continue
            # Probe with the query's numbers if it has any; otherwise take the
            # named file itself, because a word that names a file need not appear
            # in its contents ("vipul"), and "open the PRICE VIPUL workbook" is
            # exactly that request.
            rec = None
            if base_nums:
                for tok in base_nums:
                    rec = _probe_cached(files[key], tok, 20)
                    if rec is not None:
                        break
            if rec is None:
                rec = _probe_cached(files[key], sorted(_name_tokens)[0], 20)
            if rec is None and files[key]:
                # Return the file by NAME even when no token matched inside it:
                # the user named it and it exists, which is itself the answer.
                rec = _probe_named_file(files[key], 20)
            if rec is not None:
                named.append(rec)
        if named:
            return {
                "token": ",".join(sorted(_name_tokens)),
                "tokens_tried": candidates,
                "files_searched": len(order),
                "hits": named[:limit],
                "incomplete": _out_of_time(),
            }
    for token in candidates or [None]:
        if token is None:
            break  # name-only query: the named-file block below handles it
        if _out_of_time():
            break
        hits: List[Dict[str, Any]] = []
        for key in order:
            if _out_of_time():
                break
            best = _probe_cached(files[key], token, 10)
            if best is not None:
                hits.append(best)
        if hits:
            def _name_rank(rec: Dict[str, Any]) -> int:
                fname = str(rec.get("file_name") or "").lower()
                return 0 if any(t in fname for t in _name_tokens) else 1

            hits.sort(key=lambda r: (_name_rank(r), -r["row_count"]))
            return {
                "token": token,
                "tokens_tried": candidates,
                "files_searched": len(order),
                "hits": hits[:limit],
                "incomplete": _out_of_time(),
            }
    return {
        "token": candidates[0] if candidates else ",".join(sorted(_name_tokens)),
        "tokens_tried": candidates,
        "files_searched": len(order),
        "hits": [],
        # "nothing matched" and "time ran out" are different answers, and the
        # caller must be able to tell them apart — otherwise a truncated scan
        # reads as a definitive empty catalog.
        "incomplete": bool(_out_of_time()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FIND ALL (Excel-style): every cell containing a value, with addresses
# ─────────────────────────────────────────────────────────────────────────────


def _find_all_value_variants(value: str) -> List[str]:
    """Search variants of a Find-All value: the raw text plus the
    comma-stripped form, so '5,350' also hits cells stored as 5350.
    Case is handled by ILIKE / lower()."""
    raw = " ".join(str(value or "").split())
    if not raw:
        return []
    out = [raw]
    stripped = raw.replace(",", "")
    if stripped and stripped != raw:
        out.append(stripped)
    return out


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        # cells render 5350.0 as '5350' — the workbook shows no decimal
        return str(int(v))
    return str(v)


def find_all_occurrences_sync(
    value: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    *,
    file_name: Optional[str] = None,
    max_matches: int = 50,
    max_files: int = 200,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """Excel-style Find All across the ingested-spreadsheet catalog.

    Every CELL containing ``value`` (contains-match, case-insensitive —
    Excel's Find All defaults), with file, sheet, cell ADDRESS (letter +
    workbook row), the cell's rendered value and its formula when the
    sidecar has one. Counts are EXACT (a COUNT scan per sheet), so a
    zero-match result licenses a scoped absence claim over the whole
    catalog; the rendered match list is capped with a truncation flag.

    ``file_name`` scopes the scan to catalogued files whose name contains
    it (Excel's 'Within: Workbook' equivalent). ``deadline`` (monotonic)
    marks the result ``incomplete`` instead of silently vanishing — the
    same degradation contract as :func:`search_all_datasets_sync`.
    """
    variants = _find_all_value_variants(value)
    result: Dict[str, Any] = {
        "value": str(value or ""),
        "variants": variants,
        "file_filter": file_name or None,
        "files_scanned": 0,
        "sheets_scanned": 0,
        "total_matches": 0,
        "per_file": {},
        "matches": [],
        "truncated": False,
        "incomplete": False,
        "error": "",
    }
    if not variants:
        result["error"] = "no searchable value"
        return result

    def _out_of_time() -> bool:
        return deadline is not None and time.monotonic() > deadline

    entries = find_entries_sync("", user_id, workspace_id, 500)
    files: Dict[tuple, List[Dict[str, Any]]] = {}
    order: List[tuple] = []
    for e in entries:
        key = (e["source"], e["external_id"])
        if key not in files:
            files[key] = []
            order.append(key)
        files[key].append(e)
    if file_name:
        needle = str(file_name).lower()
        order = [k for k in order
                 if needle in str((files[k][0] or {}).get("file_name")
                                  or "").lower()]
    order = order[:max_files]

    try:
        import duckdb as _duckdb
    except ImportError:  # noqa: F401 — pandas fallback below
        _duckdb = None
    con = None
    if _duckdb is not None:
        try:
            con = _duckdb.connect()
        except Exception:  # noqa: BLE001
            con = None

    lowered = [v.lower() for v in variants]
    matches: List[Dict[str, Any]] = []
    total = 0
    per_file: Dict[str, int] = {}
    try:
        for key in order:
            if _out_of_time():
                result["incomplete"] = True
                break
            sheet_entries = files[key]
            fname = str((sheet_entries[0] or {}).get("file_name") or "")
            file_hit = 0
            for e in sheet_entries:
                if _out_of_time():
                    result["incomplete"] = True
                    break
                result["sheets_scanned"] += 1
                sheet_rows = _find_all_rows(
                    con, e, lowered,
                    row_limit=max_matches - len(matches))
                if not sheet_rows:
                    continue
                n_rows, rows = sheet_rows
                total += n_rows
                file_hit += n_rows
                if len(matches) < max_matches and rows is not None:
                    _append_cells(matches, e, rows, lowered,
                                  max_matches - len(matches))
            result["files_scanned"] += 1
            if file_hit:
                per_file[fname] = per_file.get(fname, 0) + file_hit
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass
    result["total_matches"] = total
    result["per_file"] = per_file
    result["matches"] = matches
    result["truncated"] = total > len(matches)
    return result


def _find_all_rows(con, entry: Dict[str, Any],
                   lowered_variants: List[str],
                   row_limit: int = 0) -> Optional[tuple]:
    """(exact_match_count, rows_or_None) for one sheet. ``rows`` is fetched
    only while ``row_limit`` (the caller's remaining display budget) is
    positive — counting is exact via COUNT(*), so truncation never lies."""
    columns = [str(c) for c in (entry.get("columns") or [])]
    columns = [c for c in columns if c != SHEET_ROW_COL]
    if not columns:
        return None
    path = str(entry.get("parquet_path", "")).replace("'", "''")
    cols_sql = ", ".join(
        f'CAST("{c.replace(chr(34), chr(34) * 2)}" AS VARCHAR)' for c in columns
    )
    predicate = " OR ".join(
        f"concat_ws('|', {cols_sql}) ILIKE ?" for _ in lowered_variants)
    params = [f"%{v}%" for v in lowered_variants]
    if con is not None:
        try:
            n = con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path}') "
                f"WHERE {predicate}", params).fetchone()[0]
            if not n:
                return None
            if row_limit <= 0:
                return int(n), None
            rows = con.execute(
                f"SELECT * FROM read_parquet('{path}') "
                f"WHERE {predicate} LIMIT {int(row_limit)}",
                params).df()
            return int(n), rows
        except Exception:  # noqa: BLE001 — pandas fallback below
            pass
    # pandas path (or DuckDB row fetch): count + rows together
    import pandas as pd

    try:
        df = pd.read_parquet(entry["parquet_path"])
    except Exception:  # noqa: BLE001
        return None
    data_cols = [c for c in df.columns if c != SHEET_ROW_COL]
    if not data_cols:
        return None
    strs = df[data_cols].astype(str)
    mask = strs.apply(
        lambda col: col.str.lower().apply(
            lambda s: any(v in s for v in lowered_variants)))
    hit_mask = mask.any(axis=1)
    n = int(hit_mask.sum())
    if not n:
        return None
    return n, df[hit_mask]


def _append_cells(matches: List[Dict[str, Any]], entry: Dict[str, Any],
                  rows, lowered_variants: List[str], budget: int) -> None:
    """Flatten matched ROWS into per-CELL matches (Excel lists each cell),
    with letter+row addresses and sidecar formulas."""
    from pandas import DataFrame

    if not isinstance(rows, DataFrame):
        return
    letters = _column_letters([c for c in rows.columns if c != SHEET_ROW_COL])
    formulas: Dict[str, str] = {}
    try:
        formulas = load_formulas_for_parquet(
            str(entry.get("parquet_path") or ""), max_cells=20000) or {}
    except Exception:  # noqa: BLE001 — formulas are decoration, not the answer
        formulas = {}
    for _, row in rows.iterrows():
        sheet_row = row.get(SHEET_ROW_COL)
        row_ref = str(int(sheet_row)) if str(sheet_row).isdigit() else ""
        for col in rows.columns:
            if col == SHEET_ROW_COL:
                continue
            cell_text = _cell_str(row.get(col)).lower()
            if not any(v in cell_text for v in lowered_variants):
                continue
            addr = f"{letters.get(str(col), '?')}{row_ref}"
            matches.append({
                "file": entry.get("file_name") or "",
                "sheet": entry.get("entity_name") or "",
                "cell": addr,
                "column": str(col),
                "value": _cell_str(row.get(col)),
                "formula": formulas.get(addr, ""),
            })
            budget -= 1
            if budget <= 0:
                return


def render_find_all_result(result: Dict[str, Any]) -> str:
    """Evidence block for a Find-All scan. Zero-match phrasing is deliberately
    scoped-absence ('no cell of any ingested spreadsheet'), and an incomplete
    scan says so — the absence guard reads both."""
    value = result.get("value") or ""
    head = f"FIND ALL RESULTS (datasets.find_all, value='{value}'"
    if result.get("file_filter"):
        head += f", within files matching '{result['file_filter']}'"
    head += "):"
    lines = [head]
    if result.get("error"):
        lines.append(f"  {result['error']}")
        return "\n".join(lines)
    scope = (f"complete scan: {result.get('files_scanned', 0)} file(s), "
             f"{result.get('sheets_scanned', 0)} sheet(s)")
    if result.get("incomplete"):
        scope = ("INCOMPLETE scan (time budget hit): "
                 f"{result.get('files_scanned', 0)} file(s), "
                 f"{result.get('sheets_scanned', 0)} sheet(s) of the catalog "
                 "— absence cannot be concluded from this")
    lines.append(f"  {scope}")
    total = result.get("total_matches", 0)
    if not total:
        lines.append(
            "  0 cell matches — the value appears in no cell of the "
            "spreadsheet(s) scanned above."
        )
        return "\n".join(lines)
    per_file = result.get("per_file") or {}
    files_summary = ", ".join(f"'{f}': {n}" for f, n in
                              sorted(per_file.items(), key=lambda kv: -kv[1]))
    lines.append(f"  {total} cell match(es). Per file: {files_summary}")
    current_fs = None
    for m in result.get("matches") or []:
        fs = f"{m['file']} / {m['sheet']}"
        if fs != current_fs:
            lines.append(f"{fs}:")
            current_fs = fs
        cell = f"{m['cell']} = {m['value']}"
        if m.get("formula"):
            cell += f"  (formula {m['formula']})"
        lines.append(f"  {cell}")
    if result.get("truncated"):
        lines.append(
            f"  … showing first {len(result.get('matches') or [])} of "
            f"{total} matches (exact count above; narrow with a file name "
            "for the rest)")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Freshness gate
# ─────────────────────────────────────────────────────────────────────────────


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_DATASET_TTL = timedelta(
    hours=max(1, int(os.getenv("ATOM_SHEET_DATASET_TTL_HOURS", "6") or 6))
)


# IMMUTABLE dataset sources: email-attachment workbooks. A live-synced
# file (storage/drive) can change upstream, so answering from the copy
# needs freshness proof; an attachment CANNOT change — a different
# version arrives as a new message, hence a new external_id. The TTL
# gate (built for the sync case) rejected these hours after ingest and
# silently disabled the NL-to-SQL path on the files least likely to be
# stale (live 2026-09-15: an email-attachment workbook, gate False at
# T+5h with no re-download path to fall back to).
_IMMUTABLE_DATASET_SOURCES = frozenset({
    "outlook", "gmail", "attachment",
})


def _copy_is_fresh(entries: List[Dict[str, Any]], source_modified_hint: Any = None) -> bool:
    """May agents answer from the materialized copy?

    Proof order: (1) the source's own modified-at, when the caller captured
    it from the connector's search record, must equal the copy's stamp —
    same signal the repo's hybrid-sync update probes rely on; (2) otherwise
    a recency TTL on the materialization itself. Anything unparsable is NOT
    treated as fresh: fall through to the download path, which re-verifies.
    """
    if not entries:
        return False
    newest = max(entries, key=lambda r: (r.get("ingested_at") or ""))
    ingested_dt = _parse_dt(newest.get("ingested_at"))
    if str(newest.get("source") or "").lower() in _IMMUTABLE_DATASET_SOURCES:
        # immutable attachment: a parsable ingest stamp is sufficient
        return bool(ingested_dt)
    hint_dt = _parse_dt(source_modified_hint)
    entry_dt = _parse_dt(newest.get("source_modified_at"))
    if hint_dt and entry_dt:
        return hint_dt == entry_dt
    ingested_dt = _parse_dt(newest.get("ingested_at"))
    if not ingested_dt:
        return False
    return (datetime.now(timezone.utc) - ingested_dt) <= _DATASET_TTL


# ─────────────────────────────────────────────────────────────────────────────
# NL → SQL answering (the harness-side routing: chat executes ONE planned leg
# per turn and the reply model never calls tools, so the dataset query must
# happen inside this service, invoked from the read leg)
# ─────────────────────────────────────────────────────────────────────────────


_MAX_SCHEMA_DATASETS = 64
_MAX_SCHEMA_COLUMNS = 15


def _schema_block(entries: List[Dict[str, Any]]) -> str:
    lines = []
    for e in entries[:_MAX_SCHEMA_DATASETS]:
        cols = ", ".join(
            f'"{c}"' + (f" (e.g. {'; '.join(e.get('column_samples', {}).get(c, [])[:3])})" if e.get("column_samples", {}).get(c) else "")
            for c in e.get("columns", [])[:_MAX_SCHEMA_COLUMNS]
        )
        lines.append(
            f'- dataset_name="{e["dataset_name"]}" | sheet \'{e["entity_name"]}\' of '
            f'file \'{e.get("file_name")}\' | {e.get("row_count")} rows | columns: {cols}'
        )
    return "\n".join(lines)


def _duckdb_probe_entry(con, entry: Dict[str, Any], token: str, limit: int):
    """One DuckDB scan of one dataset: (hit_count, hit_df) or (None, None)
    when the dataset can't be probed this way. Projected, streamed — cost is
    O(matched rows), not O(table)."""
    columns = [str(c) for c in (entry.get("columns") or [])]
    if not columns:
        return None, None
    # NEVER SCAN THE INTERNAL ROW-NUMBER COLUMN. `__sheet_row` is bookkeeping the
    # extractor adds so answers can cite 'R<n>'; it is not workbook data, yet it
    # rode into the concatenated probe text — so a query for 5350 matched every
    # file that merely HAS a row 5350, and a row-7519 query matched a sheet with
    # 7,519 rows. That is how an amount probe resolved to a 2019 price list
    # instead of the workbook holding the value (measured live 2026-09-16).
    columns = [c for c in columns if c != SHEET_ROW_COL]
    if not columns:
        return None, None
    path = str(entry.get("parquet_path", "")).replace("'", "''")
    cols_sql = ", ".join(
        f'CAST("{c.replace(chr(34), chr(34) * 2)}" AS VARCHAR)' for c in columns
    )
    sql = (
        f"SELECT * FROM read_parquet('{path}') "
        f"WHERE concat_ws('|', {cols_sql}) ILIKE ? "
        f"LIMIT {int(limit)}"
    )
    try:
        out = con.execute(sql, [f"%{token}%"]).df()
    except Exception:  # noqa: BLE001 — caller falls back to pandas
        return None, None
    if out.empty:
        return 0, out
    return len(out), out


def _pandas_probe_entry(entry: Dict[str, Any], token: str):
    """Pandas fallback probe (no DuckDB on the interpreter)."""
    import pandas as pd

    try:
        df = pd.read_parquet(entry["parquet_path"])
    except Exception:  # noqa: BLE001
        return None, None
    if df.empty:
        return None, None
    strs = df.astype(str)
    # same exclusion as the DuckDB path — see the note there
    strs = strs.drop(columns=[C for C in (SHEET_ROW_COL,) if C in strs.columns])
    mask = strs.apply(lambda col: col.str.contains(token, case=False, regex=False, na=False))
    hit = df[mask.any(axis=1)]
    if hit.empty:
        return None, None
    return len(hit), hit


# PROBE CACHE: search_all_datasets_sync scans EVERY dataset's parquet per
# token — 200+ files, and the derivation lane probes up to 4 tokens per
# turn. Repeated tokens ('5216', '7519') re-scanned every turn made the
# catalog's answers intermittent under load (live 2026-09-16: PRICE VIPUL
# present in one probe, absent the next). Keyed by (content_hash, token,
# max_rows) so a re-materialized file (new hash) invalidates naturally;
# TTL bounds staleness for same-hash updates. Env kill switch + TTL:
# ATOM_SHEET_PROBE_CACHE_TTL_SECONDS (default 300, 0 = off).
_PROBE_CACHE: Dict[tuple, tuple] = {}
# Guards the cache dict only — never held across a probe (probing can take
# seconds and must not serialize the evidence legs).
_PROBE_CACHE_LOCK = threading.Lock()
_PROBE_CACHE_TTL_S = float(
    os.getenv("ATOM_SHEET_PROBE_CACHE_TTL_SECONDS", "300") or 300
)


def _probe_cached(entries: List[Dict[str, Any]], token: str, max_rows: int):
    """_probe_sheet_hits with a per-(file-version, token) cache.

    The cached object is never handed out: callers receive a deep copy, so a
    consumer that edits the result it got cannot corrupt what the next caller
    reads. ("Callers must not mutate it" was a documented request, not an
    enforced invariant — verified failing 2026-09-16.)

    Cacheability requires an identity. A row with neither content_hash,
    external_id, parquet_path nor file_name cannot be told apart from any
    other such row, so an anonymous entry is probed directly rather than
    cached under a key that would serve one file's result for another.
    """
    if _PROBE_CACHE_TTL_S <= 0:
        return _probe_sheet_hits(entries, token, max_rows)
    import time as _t

    now = _t.monotonic()
    e0 = entries[0] if entries else {}
    # identity: content_hash gives content-version invalidation; the rest keep
    # two catalog rows apart when they share bytes (the same attachment on two
    # messages) or carry no hash at all.
    identity = (
        str(e0.get("content_hash") or ""),
        str(e0.get("external_id") or ""),
        str(e0.get("parquet_path") or ""),
        str(e0.get("file_name") or ""),
    )
    if not any(identity):
        return _probe_sheet_hits(entries, token, max_rows)
    key = (identity, token, max_rows)
    with _PROBE_CACHE_LOCK:
        hit = _PROBE_CACHE.get(key)
        if hit and now - hit[0] < _PROBE_CACHE_TTL_S:
            return copy.deepcopy(hit[1])
    result = _probe_sheet_hits(entries, token, max_rows)
    with _PROBE_CACHE_LOCK:
        # bound the cache: drop expired entries first (the common case), and
        # only clear wholesale when everything in it is still live.
        if len(_PROBE_CACHE) > 512:
            expired = [k for k, (ts, _v) in _PROBE_CACHE.items()
                       if now - ts >= _PROBE_CACHE_TTL_S]
            for k in expired:
                _PROBE_CACHE.pop(k, None)
            if len(_PROBE_CACHE) > 512:
                _PROBE_CACHE.clear()
        _PROBE_CACHE[key] = (now, copy.deepcopy(result))
    return result


def _read_sheet_rows(parquet_path: str, max_rows: int) -> List[Dict[str, Any]]:
    """Read up to max_rows from the parquet as dicts, skipping pure-index
    and all-empty rows. Used by the named-file probe to carry real row
    content so the model can show the derivation, not just the headers."""
    try:
        import pandas as pd

        df = pd.read_parquet(parquet_path)
        df = df.astype(object).where(df.notna(), None)
        return df.head(max_rows).to_dict(orient="records")
    except Exception:  # noqa: BLE001 — best-effort row content
        return []


def _probe_named_file(entries: List[Dict[str, Any]], max_rows: int) -> Optional[Dict[str, Any]]:
    """A result for a file the USER NAMED, without requiring a content match.

    Content probing answers "which file contains this value". A naming ask is the
    other direction — "open the file called X" — and X need not contain any token
    from the question (the F-5216 workbook's contents never name the code the user
    knows it by). Returning the catalog entry with its sheet index and formulas
    gives the reply model the file the user means, instead of the nearest
    unrelated file whose contents happened to match a word.
    """
    if not entries:
        return None
    e = entries[0]
    try:
        formulas = load_formulas_for_parquet(str(e.get("parquet_path") or ""))
    except Exception:  # noqa: BLE001 — formulas are additive
        formulas = {}
    # Attach the actual rows so the derivation evidence carries real data, not
    # just the file/sheet index (live 2026-09-16: the model named the file
    # correctly but could not show the derivation because the rows list was
    # empty). Probe with a wildcard match to pull the sheet's business rows,
    # capped by max_rows.
    #
    # `rows_out` WAS NEVER ASSIGNED: this literal referenced an undefined name,
    # so every "open the file named X" ask raised NameError inside the tool
    # (`tool execution failed for zoho_workdrive.read: name 'rows_out' is not
    # defined`, repeated twice per turn — canvas-edit leg and canvas-action leg)
    # and the turn then told the model the live lookup had failed. The
    # content-probe path was unaffected, which is why the same ask sometimes
    # worked: whichever lane matched first decided the outcome.
    _rows = _read_sheet_rows(str(e.get("parquet_path") or ""), max_rows)
    return {
        "file_name": e.get("file_name"),
        "entity_name": e.get("entity_name") or e.get("sheet_name"),
        "source_modified_at": e.get("source_modified_at"),
        "sql": "(selected by file name — no content probe needed)",
        "columns": [],
        "rows": _rows,
        "row_count": len(_rows),
        "formulas": formulas,
        "selected_by_name": True,
    }


def _probe_sheet_hits(entries: List[Dict[str, Any]], token: str, max_rows: int) -> Optional[Dict[str, Any]]:
    """Deterministic content probe for identifier lookups (SKUs, model codes).

    Scans every sheet of the copy for `token` (case-insensitive substring —
    '350dsav' matches 'WG-350DSAV' and 'WG350DSAV' alike) and returns an
    answer built from the sheet with the most hits. Returns None when NO
    sheet contains the token — which is itself knowledge: the value is not
    in this copy, and the caller should fall back to the live file instead
    of letting a wrong-sheet LLM guess stand.

    Engine: DuckDB scan over the Parquet files (projected, streamed — cost is
    O(matched rows), so probe latency stays flat as datasets grow), with the
    original pandas scan as fallback.
    """
    try:
        import duckdb as _duckdb
    except ImportError:  # noqa: F401 — pandas fallback below
        _duckdb = None

    con = None
    if _duckdb is not None:
        try:
            con = _duckdb.connect()
        except Exception:  # noqa: BLE001
            con = None

    best = None  # (hit_count, entry, hit_df)
    try:
        for e in entries:
            hit_count, hit = None, None
            if con is not None:
                hit_count, hit = _duckdb_probe_entry(con, e, token, max_rows + 1)
            if hit_count is None:
                hit_count, hit = _pandas_probe_entry(e, token)
            if hit_count and (best is None or hit_count > best[0]):
                best = (hit_count, e, hit)
    finally:
        if con is not None:
            con.close()
    if best is None:
        return None
    count, e, hit = best
    head = hit.head(max_rows)
    # Column NAME -> LETTER travels with the rows: the workbook's formulas
    # address cells by letter, so without it a verifier cannot connect a value
    # to the formula that produces it (see _column_letters).
    # DIGIT-BOUNDARY CHECK for pure-number tokens. The scan above is a substring
    # match, which is right for codes ('350dsav' must match 'WG-350DSAV') and
    # wrong for amounts/model numbers: EVERY hit for the code "5216" against the
    # live catalog was a substring of the artifact float tail "15.521625000000002",
    # so the derivation ask resolved to unrelated price lists while the workbook
    # that actually answers it was never probed (measured 2026-09-16). A token
    # that is ALL digits must therefore appear as a whole number, not inside one;
    # tokens containing letters keep substring semantics.
    if token.isdigit() and count:
        for _line in render_dataset_answer({
            "file_name": e.get("file_name"), "entity_name": e.get("entity_name"),
            "sql": "", "columns": head.columns.tolist(), "rows": head.to_dict("records"),
            "row_count": count, "formulas": {},
        }).splitlines():
            if _line.startswith("SQL RESULT") or _line.startswith("... "):
                continue
            # A NUMERIC CELL renders as '7519.0' when the source stores it as a
            # float, so a trailing decimal is the same number, not a longer one.
            # A trailing DIGIT is not ('75190'), and a digit before a dot is not
            # ('15.5216' is a fragment, while a leading '0' as in a zero-padded
            # part number is an identifier and passes).
            if re.search(
                rf"(?<![0-9.]){re.escape(token)}(?![0-9])", _line
            ):
                return {
                    "file_name": e.get("file_name"),
                    "entity_name": e.get("entity_name"),
                    "external_id": e.get("external_id"),
                    "source_modified_at": e.get("source_modified_at"),
                    "sql": f"-- content probe: scanned for '{token}' (whole-number match)",
                    "columns": head.columns.tolist(),
                    "column_letters": _column_letters(head.columns.tolist()),
                    "rows": head.to_dict("records"),
                    "row_count": count,
                    "formulas": load_formulas_for_parquet(str(e.get("parquet_path") or "")),
                }
        return None  # only float-tail/substring matches — not this number
    rows = head.astype(object).where(head.notna(), None).to_dict(orient="records")
    return {
        "dataset_name": e["dataset_name"],
        "entity_name": e["entity_name"],
        "file_name": e.get("file_name"),
        "source_kind": e.get("source_kind"),
        "external_id": e.get("external_id"),
        "content_hash": e.get("content_hash"),
        "source_modified_at": e.get("source_modified_at"),
        "ingested_at": e.get("ingested_at"),
        "sql": f"-- content probe: every sheet scanned for '{token}'",
        "row_count": int(count),
        "columns": [str(c) for c in head.columns],
        "column_letters": _column_letters([str(c) for c in head.columns]),
        "rows": rows,
        # FORMULAS on the deterministic path too (gap fix 2026-09-16): the
        # sidecar exists at materialization time; only the LLM-SQL path
        # attached it before, so a Stage-0 answer rendered values without
        # the cell formulas — exactly the derivation asks' evidence.
        "formulas": load_formulas_for_parquet(str(e.get("parquet_path") or "")),
        "note": "",
    }


def _select_probe_token(query: str) -> Optional[str]:
    """The identifying token of a value-lookup question: the LONGEST
    digit-bearing token ('350dsav' from 'WG-350DSAV'). Long digit-bearing
    codes are the rarest, most precise anchor a workbook has.

    Bare years ('2019') are REJECTED: they appear in titles across sheets,
    and probing one returns noisy wrong-sheet hits (live 2026-09-07: a read
    for 'consolidated price list 2019' answered from a title row instead of
    the model's row). Word tokens ('price', 'consolidated') are equally
    unprobesable."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) >= 4]
    digit_tokens = [
        t for t in tokens
        if any(ch.isdigit() for ch in t) and not re.fullmatch(r"(19|20)\d{2}", t)
    ]
    if not digit_tokens:
        return None
    return sorted(digit_tokens, key=len, reverse=True)[0]


#: token -> number of catalogued FILE NAMES containing it, plus the file count.
#: Derived from this install's own corpus, so "distinctive" means distinctive
#: HERE ("price" is in 128 files, "vipul" in 1) with no domain vocabulary baked
#: into the code.
_NAME_TOKEN_INDEX: Dict[str, Any] = {}
_NAME_TOKEN_INDEX_TTL_S = 300.0


def _name_token_index() -> tuple:
    """``(doc_freq, file_count)`` over catalogued file names, TTL-cached."""
    import time as _time

    hit = _NAME_TOKEN_INDEX.get("t")
    now = _time.monotonic()
    if hit and now - hit[0] < _NAME_TOKEN_INDEX_TTL_S:
        return hit[1], hit[2]
    doc_freq: Dict[str, int] = {}
    total = 0
    try:
        entries = find_entries_sync("", None, None, 500)
        names = {str(e.get("file_name") or "") for e in entries}
        names.discard("")
        total = len(names)
        for name in names:
            for tok in set(re.split(r"[^a-z0-9]+", name.lower())):
                if len(tok) >= 4 and not tok.isdigit():
                    doc_freq[tok] = doc_freq.get(tok, 0) + 1
    except Exception as err:  # noqa: BLE001 — the index is an optimisation
        logger.debug(f"name-token index unavailable: {err}")
    _NAME_TOKEN_INDEX["t"] = (now, doc_freq, total)
    return doc_freq, total


def distinctive_name_tokens(texts: List[str], max_tokens: int = 2) -> List[str]:
    """Query words that identify a FILE by name, ranked by rarity in the corpus.

    The digit-only rule above cannot see a file named in words: "PRICE VIPUL
    (6).xlsx" carries no code, so a query naming it produced NO candidate tokens,
    the catalog was never probed, and the dataset lane ran its SQL against
    whatever other spreadsheet the query's incidental digits matched (live
    2026-09-16: Consolidated Price List answered a question about the VIPUL
    workbook).

    Rarity is measured against this install's catalogued file names, so nothing
    domain-specific is hard-coded: "price" appears in 6 of 65 file names here and
    is rejected as non-identifying, while "vipul" appears in 1 and is accepted.
    Two uncommon words are decisive together; a LONE rare word needs the query to
    carry a digit/code as corroboration, which keeps prose questions ("which
    vendors sent a price list") from probing the catalog on ordinary vocabulary
    while still resolving a file named in words.
    """
    doc_freq, total = _name_token_index()
    if not total or not doc_freq:
        return []
    # A word is "identifying" only if it is rare in THIS catalog. Measured on the
    # live corpus: "price" is in 6 of 65 file names and "list" in 6, while the
    # token that names the F-5216 workbook ("vipul") is in exactly 1 — so rarity
    # is derived from the install's own catalog instead of any vocabulary list.
    #
    # At this catalog size frequency alone cannot decide: "lead" is also in 1
    # file name and appears in countless questions. Word LENGTH cannot decide
    # either — "vipul" is 5 characters, so a 6-character floor dropped the very
    # token this exists to catch while admitting "harsle". The safety therefore
    # comes from AGREEMENT: a lone rare word is only trusted when the query also
    # carries a code/blob/amount, because a file-naming question nearly always
    # does ("PRICE VIPUL (6).xlsx", "the F-5216 workbook"). "what is the lead
    # time" carries neither and stays out of the catalog probe.
    # ANY digit run counts as corroboration — a version marker like "(6)" in
    # "PRICE VIPUL (6).xlsx" is exactly the signal, and a \d{2,} floor missed it
    # (single digits fell through, so a file-naming query still produced no
    # tokens). One digit anywhere in the ask plus one rare name word is a far
    # tighter test than either alone.
    corroborated = bool(
        re.search(r"(?:[a-z]{1,4}-\d|\d)", " ".join(texts or []).lower())
    )
    common_cutoff = max(2, int(total * 0.03))
    rare_cutoff = 1
    scored: List[tuple] = []
    seen: set = set()
    for text in texts or []:
        for tok in re.split(r"[^a-z0-9]+", (text or "").lower()):
            if len(tok) < 4 or tok in seen or tok.isdigit():
                continue
            seen.add(tok)
            freq = doc_freq.get(tok)
            if freq is None or freq > common_cutoff:
                continue  # not a catalog word, or too common to identify one file
            scored.append((freq, tok))
    scored.sort(key=lambda t: (t[0], -len(t[1])))
    if not scored:
        return []
    if len(scored) >= 2:
        return [tok for _f, tok in scored[:max_tokens]]
    if scored[0][0] <= rare_cutoff and corroborated:
        return [scored[0][1]][:max_tokens]
    # A LONE rare word with no digit anywhere ("open the PRICE VIPUL workbook"):
    # the corroboration rule above rejected it and the file the user named became
    # unreachable again. At this catalog size (65 names, typically one or two
    # distinctive words per question) requiring corroboration costs a real answer
    # to avoid a speculative probe, and the two outcomes are not symmetric: being
    # wrong means the catalog rows for a file whose name matched are shown, while
    # being silent means the agent tells the user its own workbook is unavailable.
    # The probe is a local SQLite+parquet read on a name the user typed, so it is
    # taken.
    if scored[0][0] <= rare_cutoff:
        return [scored[0][1]][:max_tokens]
    return []
def candidate_probe_tokens(
    texts: List[str], max_tokens: int = 3, allow_name_fallback: bool = True
) -> List[str]:
    """Ranked candidate identifier tokens from the query AND its context
    (history turns, canvas).

    The planner's query for a 'try again' turn may carry no code at all while
    the conversation does ('WG-350DSAV' sat in earlier turns), and the
    identifier net can append a company slug ('brennanmachineryinc1') whose
    single trailing digit made it look code-like. So: collect digit-bearing
    tokens from ALL supplied texts, drop bare years, rank by digit-density
    then length (codes beat names), and return the top few for the probe to
    try in order.
    """
    tokens: List[str] = []
    seen: set = set()
    for text in texts:
        for t in re.split(r"[^a-z0-9]+", (text or "").lower()):
            if len(t) < 4 or t in seen:
                continue
            if not any(ch.isdigit() for ch in t):
                continue
            if re.fullmatch(r"(19|20)\d{2}", t):
                continue
            seen.add(t)
            tokens.append(t)
    tokens.sort(
        key=lambda t: (sum(ch.isdigit() for ch in t), len(t)),
        reverse=True,
    )
    if tokens:
        return tokens[:max_tokens]
    if not allow_name_fallback:
        # The caller is running its OWN, narrower name matching (see the
        # `name_context_texts` note in search_all_datasets_sync). Falling back
        # here would re-read the full context — history included — and quietly
        # reintroduce the hijack this flag exists to prevent.
        return []
    # No code in the query: it may still be naming a FILE in words. Appended
    # (not replacing) so a code always leads, and so the caller's "no candidate"
    # branch still means "nothing identifying was said".
    return distinctive_name_tokens(texts, max_tokens=min(max_tokens, 2))


async def answer_from_datasets(
    source: str,
    external_id: str,
    query: str,
    *,
    llm_service: Any = None,
    source_modified_hint: Any = None,
    context_texts: Optional[List[str]] = None,
    max_rows: int = 50,
) -> Optional[Dict[str, Any]]:
    """Answer a natural-language value question from the materialized copy.

    Returns None whenever the answer should come from the live file instead:
    no registered copy, copy not freshness-verified, no LLM available, or
    the generated SQL produced nothing. The caller (read leg) falls through
    to download+excerpt in every one of those cases, so this can never make
    an answer WORSE — only skip a download.
    """
    import asyncio

    if not query or llm_service is None:
        return None

    entries = entries_for_file_sync(source, external_id)
    if not entries or not _copy_is_fresh(entries, source_modified_hint):
        return None

    # ── Stage 0: deterministic content probe (no LLM) ────────────────────
    # Candidate identifiers come from the query AND the surrounding context —
    # a 'try again' turn's planner query may drop the code entirely while the
    # conversation holds it (live 2026-09-07: the identifier net appended the
    # company slug and the SKU never reached the probe). Every candidate is
    # probed; any hit is the answer. A total miss is proof the value is not
    # in this copy → the caller falls back to the live file.
    candidates = candidate_probe_tokens([query] + list(context_texts or []))
    if candidates:
        for probe_token in candidates:
            probe = await asyncio.to_thread(
                _probe_sheet_hits, entries, probe_token, max_rows
            )
            if probe is not None:
                logger.info(
                    f"sheet datasets: content probe answered '{query[:60]}' from "
                    f"{probe['dataset_name']} ({probe['row_count']} hits for "
                    f"'{probe_token}')"
                )
                return probe
        logger.info(
            f"sheet datasets: no candidate token {candidates} appears in any "
            f"sheet of this copy of {entries[0].get('file_name')} — falling "
            f"back to the live file"
        )
        return None

    # No identifier in the query: NL→SQL over the schema (LLM), as before.
    if llm_service is None:
        return None

    from pydantic import BaseModel as _BaseModel

    class _SheetSQLPlan(_BaseModel):
        dataset_name: str
        sql: str
        note: str = ""

    by_name = {e["dataset_name"]: e for e in entries}

    from core.data.dataset_manager import _validate_dataset_sql

    # NL→SQL planning is a small structured call, so it is SHAPED cheaply
    # (``disable_reasoning`` via the shared helper) and ROUTED by BPC — no
    # hardcoded model. The old pin existed because unpinned routing could pick
    # an unreachable client and burn the read leg's 45s budget on connection
    # retries (live 2026-09-07); BPC now excludes connection-dead providers
    # (`_filter_by_health` + provider circuit breaker), which is the same
    # fix that let the canvas editor and tool planner drop their pins. A pin
    # additionally collapses the candidate list to one tuple, removing every
    # provider fallback — a transient 429 then became fatal (2026-09-10).
    #
    # ``ATOM_SHEET_SQL_MODEL`` remains an OPTIONAL operator override.
    from core.llm.pinned_planning import resolve_pinned_provider_model

    llm_kwargs: Dict[str, Any] = resolve_pinned_provider_model(
        llm_service, "ATOM_SHEET_SQL_MODEL", "", provider="openrouter"
    )

    import time as _time

    _t0 = _time.monotonic()

    def _prompt(shown: List[Dict[str, Any]], tried_set: set) -> str:
        tried_note = (
            ("\nThese datasets already returned nothing for this question — "
             f"pick a DIFFERENT one: {sorted(tried_set)}\n")
            if tried_set
            else ""
        )
        return (
            "You write ONE DuckDB SELECT statement. The chosen dataset is loaded "
            "as a pandas DataFrame exposed under the table name \"df\".\n\n"
            "Datasets available (each would be loaded as \"df\"):\n"
            f"{_schema_block(shown)}\n\n"
            f"Question: {query}\n\n"
            f"{tried_note}"
            "Rules:\n"
            "- Pick the single most likely dataset_name from the list.\n"
            "- The SQL must be ONE statement, SELECT or WITH, reading ONLY \"df\". "
            "No INSERT/UPDATE/DELETE/DDL, no semicolon.\n"
            "- Quote column names in double quotes exactly as listed. Non-listed "
            "columns do not exist.\n"
            "- Every dataset has a \"__sheet_row\" column: the row's number in the "
            "original spreadsheet (header = row 1). Include it in the projection so "
            "the answer can cite where the value lives.\n"
            "- Prefer exact matching on identifier-like columns using the sample "
            "values; use ILIKE for partial text.\n"
            "- If no dataset plausibly contains the answer, set dataset_name to "
            "\"\" and sql to \"\".\n\n"
            "Return JSON: dataset_name, sql, note"
        )

    # Up to two attempts: workbooks hold dozens of sheets and the first pick
    # can miss (live 2026-09-07: the model picked the alphabetically-first
    # 'Cedarberg' sheet). The exclusion retry is the single iteration that
    # bought the 25-point gain in the agentic-retrieval benchmarks.
    # Cheap lexical pre-ranking (BRTR's retrieval-fusion, lite): datasets
    # whose sheet/columns/SAMPLE VALUES contain the query's tokens come first.
    _q_tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2]

    def _score(e: Dict[str, Any]) -> int:
        hay = " ".join(
            [e.get("entity_name", ""), e.get("file_name") or ""]
            + list(e.get("columns") or [])
            + [s for ss in (e.get("column_samples") or {}).values() for s in ss]
        ).lower()
        return sum(1 for t in _q_tokens if t in hay)

    ranked = sorted(entries, key=_score, reverse=True)
    tried: set = set()
    for attempt in (1, 2):
        shown = [e for e in ranked if e["dataset_name"] not in tried]
        if not shown:
            break
        _a0 = _time.monotonic()
        try:
            from core.llm.pinned_planning import pinned_structured_call

            plan = await pinned_structured_call(
                llm_service,
                prompt=_prompt(shown, tried),
                response_model=_SheetSQLPlan,
                system_instruction=(
                    "You convert natural-language questions about spreadsheet "
                    "contents into one safe DuckDB SELECT statement. Output JSON only."
                ),
                call_kwargs=llm_kwargs,
                log_label="sheet dataset NL→SQL",
                task_type="nl2sql",
            )
        except Exception as llm_err:  # noqa: BLE001 — fall through to the live path
            logger.info(
                f"sheet datasets: NL→SQL generation failed for '{query[:60]}' "
                f"in {_time.monotonic() - _a0:.1f}s: {type(llm_err).__name__}"
            )
            return None

        entry = by_name.get((getattr(plan, "dataset_name", "") or "").strip())
        sql = (getattr(plan, "sql", "") or "").strip().rstrip(";").strip()
        if entry is None or not sql:
            return None

        # Server-generated but still untrusted input: same filesystem/URL
        # function block the agent SQL tool applies, plus read-only shape.
        violation = _validate_dataset_sql(sql)
        if violation:
            logger.info(f"sheet datasets: SQL rejected ({violation})")
            return None
        if not re.match(r"(?is)^\s*(select|with)\b", sql) or ";" in sql:
            return None
        if not re.search(r"\blimit\b", sql, re.IGNORECASE):
            sql = f"SELECT * FROM ({sql}) AS _capped LIMIT {max_rows}"

        chosen_entry = entry
        chosen_sql = sql

        def _run() -> Dict[str, Any]:
            import duckdb
            import pandas as pd

            df = pd.read_parquet(chosen_entry["parquet_path"])
            con = duckdb.connect()
            try:
                con.register("df", df)
                # The model addresses the table variously as "df", the dataset
                # name, or the sheet name — register all three aliases
                # ([a-z0-9_] safe) so a schema mismatch never wastes the try.
                con.register(chosen_entry["dataset_name"], df)
                sheet_alias = re.sub(r"[^a-z0-9_]+", "_", chosen_entry["entity_name"].lower())
                con.register(sheet_alias, df)
                out = con.execute(chosen_sql).df()
            finally:
                con.close()
            out = out.astype(object).where(out.notna(), None)
            rows = out.to_dict(orient="records")
            return {
                "dataset_name": chosen_entry["dataset_name"],
                "entity_name": chosen_entry["entity_name"],
                "file_name": chosen_entry.get("file_name"),
                "source": chosen_entry.get("source"),
                "source_kind": chosen_entry.get("source_kind"),
                "external_id": chosen_entry.get("external_id"),
                "content_hash": chosen_entry.get("content_hash"),
                "source_modified_at": chosen_entry.get("source_modified_at"),
                "ingested_at": chosen_entry.get("ingested_at"),
                "sql": chosen_sql,
                "row_count": len(rows),
                "columns": [str(c) for c in out.columns],
                "rows": rows[:max_rows],
                # Cell->formula from the original workbook (sidecar written at
                # materialization). Rendered as a FORMULAS footer so a "how is
                # this computed?" turn cites real cells instead of guessing.
                "formulas": load_formulas_for_parquet(chosen_entry["parquet_path"]),
                "note": getattr(plan, "note", "") or "",
            }

        try:
            result = await asyncio.to_thread(_run)
        except Exception as exec_err:  # noqa: BLE001 — schema errors are retryable
            tried.add(chosen_entry["dataset_name"])
            remaining = [e for e in ranked if e["dataset_name"] not in tried]
            logger.info(
                f"sheet datasets: SQL execution failed after "
                f"{_time.monotonic() - _t0:.1f}s "
                f"({type(exec_err).__name__} from {chosen_entry['dataset_name']})"
                + (" — retrying another sheet" if remaining else " — no sheets left")
            )
            if not remaining:
                return None
            continue
        if result.get("rows"):
            logger.info(
                f"sheet datasets: answered '{query[:60]}' from "
                f"{result.get('dataset_name')} ({result.get('row_count')} rows; "
                f"attempt {attempt}, total {_time.monotonic() - _t0:.1f}s)"
            )
            return result
        tried.add(chosen_entry["dataset_name"])
        logger.info(
            f"sheet datasets: NL→SQL returned 0 rows from {chosen_entry['dataset_name']} "
            f"(attempt {attempt}; total {_time.monotonic() - _t0:.1f}s)"
            + (" — no untried sheets left" if not [e for e in ranked if e["dataset_name"] not in tried] else " — retrying another sheet")
        )
    return None


def render_dataset_answer(result: Dict[str, Any]) -> str:
    """Render SQL rows in the SAME R# | col=value convention as the text
    extractor, so the reply model cites dataset answers exactly like excerpt
    answers (its grounding contract needs nothing new)."""
    def _fmt(v: Any) -> str:
        s = " ".join(str(v).split())
        return s[:48]

    lines = [
        f"SQL RESULT from '{result.get('file_name')}' sheet '{result.get('entity_name')}' "
        f"(materialized copy, source modified {result.get('source_modified_at') or 'unknown'}, "
        f"ingested {result.get('ingested_at') or 'unknown'}, "
        f"content hash {str(result.get('content_hash') or 'unknown')[:20]}); "
        f"executed: {' '.join(str(result.get('sql', '')) .split())[:160]}"
    ]
    cols = [c for c in result.get("columns", [])][:12]
    for row in result.get("rows", []):
        cells = [f"{c}={_fmt(row.get(c))}" for c in cols if row.get(c) is not None]
        rnum = row.get(SHEET_ROW_COL)
        prefix = f"R{rnum}" if rnum is not None else "R?"
        lines.append(f"{prefix} | " + " | ".join(cells))
    shown = len(result.get("rows", []))
    if result.get("row_count", 0) > shown:
        lines.append(f"... {result['row_count'] - shown} more rows matched")
    # COLUMN LETTERS: the workbook's formulas address cells by letter (F235),
    # while the rows above are rendered by name (Factory Price=5350). A verifier
    # cannot check arithmetic without the bridge, so it travels in the block.
    letters = result.get("column_letters") or {}
    if letters:
        lines.append(
            "COLUMNS: "
            + " | ".join(f"{name}={letter}" for name, letter in list(letters.items())[:40])
        )
    formulas = result.get("formulas") or {}
    if formulas:
        # MATCHED ROWS FIRST. Emitting the sheet's first N cells (what this did)
        # shows the derivation of some arbitrary early row — useless for "how was
        # THIS price derived", and actively misleading because it looks like the
        # answer. Map every cell to its row and keep the rows in the result.
        import re as _re

        wanted_rows = {
            str(row.get(SHEET_ROW_COL))
            for row in result.get("rows", [])
            if row.get(SHEET_ROW_COL) is not None
        }

        def _row_of(cell: str) -> str:
            m = _re.match(r"^[A-Za-z]+(\d+)$", str(cell))
            return m.group(1) if m else ""


        matched = [
            (cell, f) for cell, f in formulas.items() if _row_of(cell) in wanted_rows
        ]
        rest = [
            (cell, f) for cell, f in formulas.items() if _row_of(cell) not in wanted_rows
        ]
        shown = matched[:40]
        if shown:
            lines.append(
                "FORMULAS (original workbook): FORMULAS FOR THE MATCHED ROW(S) "
                "— the derivation the original workbook computes (cell=formula): "
                + " | ".join(f"{cell}={_fmt(f)}" for cell, f in shown)
            )
        elif formulas:
            # NO ROW MATCHED — because the file was selected BY NAME ("open the
            # PRICE VIPUL workbook"), which is the very request that wants the
            # derivation. Without this the agent got the file and its sheet index
            # but no chain, and answered "the calculation file is unavailable"
            # while the chain sat in the sidecar.
            #
            # Rather than dump the sheet's first cells (the old bug), pick the rows
            # that actually COMPUTE something: a derivation row carries several
            # formulas, while footer/label rows carry one or none. Distinct rows
            # are then deduplicated by their formula PATTERN, because a price list
            # repeats one pattern down hundreds of rows and 200 identical rows
            # would bury the answer.
            by_row: Dict[str, List[tuple]] = {}
            for cell, f in formulas.items():
                r = _row_of(cell)
                if r:
                    by_row.setdefault(r, []).append((cell, f))
            patterns: List[str] = []
            for row_num in sorted(by_row, key=lambda x: int(x) if x.isdigit() else 0):
                cells_in_row = sorted(by_row[row_num])
                if len(cells_in_row) < 2:
                    continue  # a single formula is usually a bare reference
                signature = "|".join(_re.sub(r"\d+", "#", f) for _c, f in cells_in_row)
                if signature in patterns:
                    continue  # same computation as a row already shown
                patterns.append(signature)
                lines.append(
                    f"FORMULAS FOR ROW {row_num} (a computing row of this sheet; "
                    "no single row matched the question, so these show how the "
                    "sheet derives its values): "
                    + " | ".join(f"{c}={_fmt(f)}" for c, f in cells_in_row[:12])
                )
                if len(patterns) >= 3:
                    break
        if rest and shown:
            # A little context from other rows helps the model read the pattern.
            extra = rest[: max(0, 40 - len(shown))]
            if extra:
                lines.append(
                    "OTHER ROWS' FORMULAS (pattern context, not this row): "
                    + " | ".join(f"{cell}={_fmt(f)}" for cell, f in extra)
                )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Async wrappers (callers live on the event loop; pandas/sqlite are blocking)
# ─────────────────────────────────────────────────────────────────────────────





async def ensure_sheet_dataset(content: bytes, *, file_name: str, source: str,
                               user_id: Optional[str] = None, workspace_id: Optional[str] = None,
                               external_id: Optional[str] = None, source_modified_at=None) -> Dict[str, Any]:
    import asyncio

    try:
        result = await asyncio.to_thread(
            materialize_sheet_bytes_sync,
            content, file_name, source,
            user_id=user_id, workspace_id=workspace_id, external_id=external_id,
            source_modified_at=source_modified_at,
        )
        # INFO on EVERY outcome: a silent skip here is how the 2026-09-07
        # "two reads, zero datasets" failure stayed invisible for a day.
        logger.info(
            f"sheet datasets: {result.get('status')} for {file_name}"
            + (f" ({result.get('reason')})" if result.get("reason") else "")
            + (f" [{len(result.get('datasets') or [])} sheets]" if result.get("datasets") else "")
        )
        if result.get("status") == "materialized":
            # Hourly-gated storage quota check — piggybacks on materialization
            # instead of running its own loop.
            await _maybe_gc_workspace(workspace_id or "default")
        return result
    except Exception as err:  # noqa: BLE001 — best-effort by contract; never break ingestion
        logger.warning(f"sheet datasets: materialization skipped for {file_name}: {err}")
        return {"status": "error", "reason": str(err)[:200]}


# Strong refs so fire-and-forget tasks can't be garbage-collected mid-run
# (asyncio only keeps weak refs); atomic Parquet writes make a shutdown
# mid-task harmless.
# ─────────────────────────────────────────────────────────────────────────────
# Storage GC — per-workspace quota (bounded disk, bounded evictions)
# ─────────────────────────────────────────────────────────────────────────────


def _max_store_bytes() -> float:
    try:
        return float(os.getenv("ATOM_SHEET_DATASET_MAX_STORE_MB", "2048")) * 1024 * 1024
    except ValueError:
        return 2048.0 * 1024 * 1024


_GC_INTERVAL_S = max(60, int(os.getenv("ATOM_SHEET_DATASET_GC_INTERVAL_S", "3600") or 3600))
_GC_GRACE_S = max(0, int(os.getenv("ATOM_SHEET_DATASET_GC_GRACE_S", "600") or 600))
_LAST_GC_MONO = 0.0


def _cleanup_tmp_files() -> int:
    """Delete orphaned .tmp write artifacts older than a day (atomic-write
    leftovers from crashed runs)."""
    import time as _time

    removed = 0
    root = datasets_root()
    if not root.exists():
        return 0
    cutoff = _time.time() - 86400
    for p in root.rglob("*.tmp"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def gc_workspace_datasets_sync(workspace_id: str, max_store_bytes: Optional[float] = None) -> Dict[str, Any]:
    """Evict dataset Parquet files until the workspace store is under quota.

    Eviction order: superseded versions (oldest first — the version GC's
    keep-2 already bounds these), then oldest active datasets. Rows younger
    than the grace window are never evicted, protecting just-served answers.
    Every eviction deletes the catalog row WITH its Parquet file so disk and
    catalog can't diverge.
    """
    from core.models import DatasetEntry

    if max_store_bytes is None:
        max_store_bytes = _max_store_bytes()
    now = datetime.now(timezone.utc)
    evicted = 0
    with _catalog_session() as db:
        rows = (
            db.query(DatasetEntry)
            .filter(DatasetEntry.workspace_id == (workspace_id or "default"))
            .all()
        )

        def _size(r) -> int:
            try:
                return os.path.getsize(r.parquet_path)
            except OSError:
                return 0

        def _evictable(r) -> bool:
            ing = _parse_dt(r.ingested_at)
            return ing is None or (now - ing).total_seconds() >= _GC_GRACE_S

        total = sum(_size(r) for r in rows)

        def _evict(r) -> None:
            nonlocal total, evicted
            total -= _size(r)
            try:
                os.unlink(r.parquet_path)
            except OSError:
                pass
            try:
                os.unlink(str(_formula_sidecar_path(r.parquet_path)))
            except OSError:
                pass
            db.delete(r)
            evicted += 1

        if total > max_store_bytes:
            superseded = sorted(
                (r for r in rows if r.status == "superseded" and _evictable(r)),
                key=lambda r: (r.ingested_at or datetime.min.replace(tzinfo=timezone.utc)),
            )
            for r in superseded:
                if total <= max_store_bytes:
                    break
                _evict(r)
        if total > max_store_bytes:
            active = sorted(
                (r for r in rows if r.status == "active" and _evictable(r)),
                key=lambda r: (r.ingested_at or datetime.min.replace(tzinfo=timezone.utc)),
            )
            for r in active:
                if total <= max_store_bytes:
                    break
                _evict(r)
        db.commit()

    orphans = _cleanup_tmp_files()
    if evicted or orphans:
        logger.info(
            f"sheet datasets: GC evicted {evicted} dataset(s) "
            f"(+{orphans} tmp artifacts) in {workspace_id or 'default'}"
        )
    return {"status": "ok", "evicted": evicted, "total_bytes": int(total)}


async def _maybe_gc_workspace(workspace_id: Optional[str]) -> None:
    """Hourly-gated quota check (runs in the materialize background lane)."""
    global _LAST_GC_MONO
    import asyncio
    import time as _time

    now = _time.monotonic()
    if now - _LAST_GC_MONO < _GC_INTERVAL_S:
        return
    _LAST_GC_MONO = now
    try:
        await asyncio.to_thread(gc_workspace_datasets_sync, workspace_id or "default", None)
    except Exception as gc_err:  # noqa: BLE001 — GC never breaks serving
        logger.debug(f"sheet datasets: GC skipped: {gc_err}")


def spawn_background(coro, label: str = "dataset background task") -> bool:
    """Schedule a fire-and-forget task with a strong ref (asyncio keeps only
    weak refs). False when there is no running loop."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug(f"{label}: no running loop; not scheduled")
        return False
    task = loop.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


_BACKGROUND_TASKS: set = set()


def ensure_sheet_dataset_background(content: bytes, *, file_name: str, source: str,
                                    user_id: Optional[str] = None, workspace_id: Optional[str] = None,
                                    external_id: Optional[str] = None,
                                    source_modified_hint: Any = None) -> None:
    """Schedule materialization without blocking the read leg.

    The first materialization of a large workbook costs a full pandas parse
    (~10s on the 13MB price list) — spending that inside the read's 45s tool
    budget risks timing out the very turn that arms the fast path. The task
    logs its outcome at INFO when it lands; the NEXT question about this file
    takes the dataset fast path.
    """

    async def _task() -> None:
        modified_at = _parse_dt(source_modified_hint)
        await ensure_sheet_dataset(
            content,
            file_name=file_name,
            source=source,
            user_id=user_id,
            workspace_id=workspace_id,
            external_id=external_id,
            source_modified_at=modified_at,
        )

    spawn_background(
        _task(),
        f"dataset materialization {file_name}",
    )


async def datasets_for_file(source: str, external_id: str) -> List[Dict[str, Any]]:
    import asyncio

    try:
        return await asyncio.to_thread(entries_for_file_sync, source, external_id)
    except Exception as err:  # noqa: BLE001
        logger.debug(f"sheet datasets: lookup failed for {external_id}: {err}")
        return []
