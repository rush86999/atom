# -*- coding: utf-8 -*-
"""The general formula engine — parse, validate and evaluate a
supported formula language deterministically (round 70, owner
redesign: "the reusable capability should be a formula engine;
pricing is one application of it").

LAYER CONTRACT (the owner's separation, enforced by construction):

* BUSINESS TEACHING decides WHEN a calculation applies and which
  sources are authoritative — outside this module entirely.
* THE AGENT identifies the requested output, selects an applicable
  formula and obtains missing inputs — outside this module.
* THIS ENGINE parses, validates and evaluates supported expressions
  deterministically, recording every dependency and step.
* EVIDENCE AND PERMISSIONS (provenance, applicability, freshness,
  authorization) are attached by the calling application from the
  engine's neutral records.

The engine has NO built-in concepts of vendor, retail price, freight
or machinery. Cell addresses, function names and named inputs are
references; business meaning arrives with the calling workflow.

Inspection that preceded this evaluator (AGENTS.md §3):
* core.formula_extractor — extracts formulas into semantic memory;
  no evaluation.
* core.derivation_verification._Evaluator — whitelisted-AST float
  evaluation scoped to verifying reply claims against an evidence
  block; its fail-closed discipline is followed here.
* core.workbook_runtime + the declared `formulas` dependency
  (requirements-py314, formulas==1.3.4) — whole-workbook float
  evaluation and cached-value injection; used HERE as the independent
  verification oracle, not as the execution path.
None provides typed-Decimal, dependency-complete, replayable,
fail-closed evaluation with per-reference provenance — which is what
applications need to publish a reviewable result.

THE SUPPORTED FORMULA LANGUAGE (explicit; expands by adding functions
or reference sources, never by adding a business):

  literals        integer and decimal numbers — Decimal by string,
                  never float
  references      A1, $A$1, Sheet!A1, 'Sheet Name'!A1, resolved
                  through cell books (the workbook input format)
  named inputs    identifiers bound by the caller (the explicit-input
                  format: taught expressions, job parameters) — an
                  explicit input shadows a same-shaped cell reference
  operators       + - * / and ^ with a non-negative integer exponent;
                  unary +/-
  functions       ROUNDUP, ROUND, ROUNDDOWN, INT, ABS, MIN, MAX, SUM
  precision       Decimal arithmetic at 34 significant digits
  rounding        Excel semantics — ROUNDUP away from zero, ROUNDDOWN
                  toward zero, ROUND half-away-from-zero
  units           optional per-input annotations, recorded verbatim
                  and propagated to the result; never interpreted

Anything outside the language returns a precise UNSUPPORTED result
naming the construct; a missing reference or input returns a precise
MISSING result naming the exact cell or name. A partial answer is
never presented as complete.
"""
from __future__ import annotations

import ast
import os
import re
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING, \
    ROUND_FLOOR, ROUND_HALF_UP, localcontext
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

#: Spreadsheet functions the engine understands. Anything else is
#: UNSUPPORTED — named in the result, never approximated.
SUPPORTED_FUNCTIONS = {
    "ROUNDUP", "ROUND", "ROUNDDOWN", "INT", "ABS", "MIN", "MAX", "SUM",
}

_CELL_RE = re.compile(r"^([A-Z]{1,3})(\d+)$", re.IGNORECASE)

#: A sheet-qualified reference: 'Exchange-Index'!H4 / BurrKing!AB1.
_SHEET_QUALIFIED_RE = re.compile(
    r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_ .&\-]*?))!"
    r"\$?([A-Za-z]{1,3})\$?(\d+)")

_MAX_CHAIN_DEPTH = 32  # dependency chains deeper than this are refused

_ENGINE_PRECISION = 34


class FormulaInputError(ValueError):
    """A provided input failed validation (non-numeric, non-finite).
    Distinct from missing/unsupported: the input was present but
    unusable."""


# ---------------------------------------------------------------------------
# Reference sources — the workbook input format
# ---------------------------------------------------------------------------

def col_letter(idx: int) -> str:
    n, s = idx, ""
    while n >= 0:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
    return s


class CellBook:
    """One sheet's formulas plus resolvable values, with per-cell
    provenance. ``empty`` is the set of cells KNOWN blank — Excel's
    blank-operand rule applies there, while a cell with no value, no
    formula and no blank record is MISSING (named, never zero)."""

    def __init__(self, name: str, formulas: Dict[str, str],
                 values: Dict[str, str], empty: Optional[Set[str]] = None,
                 source: str = "frame",
                 formula_cells: Optional[Set[str]] = None):
        self.name = name
        self.formulas = {k.upper(): v for k, v in (formulas or {}).items()}
        # Normalize: an empty-string value IS a blank (frames and raw
        # grids both materialize blanks that way) — it belongs in the
        # known-blank set, never in values where it would fail as a
        # non-numeric operand.
        vals: Dict[str, str] = {}
        blanks = {c.upper() for c in (empty or set())}
        for k, v in (values or {}).items():
            if v is None or str(v).strip() == "":
                blanks.add(k.upper())
            else:
                vals[k.upper()] = str(v)
        self.values = vals
        self.empty = blanks
        #: WORKBOOK METADATA (round 71): the set of cells this cell
        # carries a formula in (an <f> element in the package, body or
        # bodyless-shared). This is what separates "typed literal ->
        # stored-value observation" from "formula cell whose body is
        # unavailable -> incomplete" — column heuristics prove nothing
        # about ONE cell. None when the source carries no such
        # metadata (sidecar-only durable state).
        self.formula_cells = (
            None if formula_cells is None
            else {c.upper() for c in formula_cells})
        self.source = source
        self._overlay_sources: Dict[str, str] = {}

    def overlay(self, values: Dict[str, str], source: str,
                formulas: Optional[Dict[str, str]] = None,
                formula_cells: Optional[Set[str]] = None) -> None:
        """Merge caller-supplied cells (e.g. from a live source read)
        over the durable state — per-cell sources are retained so the
        record can say which dependencies were read live. ``formulas``
        overlays too: package formats that share formula bodies across
        cells leave dependents without one, so a live read is also the
        completion path for MISSING formulas, never an inference from
        neighboring cells. ``formula_cells`` merges the WORKBOOK
        METADATA (which cells carry formulas at all) — once any
        metadata arrives, the book can distinguish typed literals from
        formula cells whose bodies are missing."""
        for k, v in (values or {}).items():
            if v is None or str(v) == "":
                continue
            key = k.upper()
            self.values[key] = str(v)
            self._overlay_sources[key] = source
        for k, fml in (formulas or {}).items():
            if fml and str(fml).strip():
                self.formulas[k.upper()] = str(fml).strip()
                self._overlay_sources[k.upper()] = source
        if formula_cells is not None:
            if self.formula_cells is None:
                self.formula_cells = set()
            self.formula_cells.update(
                c.upper() for c in formula_cells)

    def cell_source(self, cell: str) -> str:
        return self._overlay_sources.get(cell.upper(), self.source)


def sheet_grid_from_parquet(parquet_path: str
                            ) -> Tuple[Dict[str, str], Set[str]]:
    """A materialized sheet frame -> (values by Excel address, known
    blanks). Columns map to letters by ORDER (frames preserve sheet
    column order; headers are text, not letters) and rows by
    __sheet_row when present (the true row), else by position+2."""
    import pandas as _pd

    df = _pd.read_parquet(parquet_path)
    has_sr = "__sheet_row" in df.columns
    vals: Dict[str, str] = {}
    empty: Set[str] = set()
    for ci, col in enumerate(df.columns):
        if str(col) == "__sheet_row":
            continue
        letter = col_letter(ci)
        sr = df["__sheet_row"] if has_sr else None
        for i, v in enumerate(df[col]):
            row_no = int(sr.iloc[i]) if has_sr else i + 2
            addr = f"{letter}{row_no}"
            # Blanks materialize as None, NaN AND empty strings — all
            # three are the known-blank set; anything else is a value.
            if v is None or str(v).strip() == "" or (
                    hasattr(v, "item") and _pd.isna(v)):
                empty.add(addr)
                continue
            s = str(v)
            if s:
                vals.setdefault(addr, s)
    return vals, empty


def _translate_shared_formula(master_ref: str, text: str,
                              cell_ref: str) -> str:
    """Translate a shared-formula MASTER body to a dependent cell.

    The package DECLARES that a dependent cell (<f t="shared" si=N/>
    with no body) evaluates the master's formula shifted by the cell
    offset — Excel's own format semantics, not an inference. Relative
    components shift; $-absolute components stay."""
    def _parse(ref: str) -> Tuple[int, int]:
        m = re.match(r"\$?([A-Z]{1,3})\$?(\d+)$", ref or "",
                     re.IGNORECASE)
        if not m:
            return (0, 0)
        col = 0
        for ch in m.group(1).upper():
            col = col * 26 + (ord(ch) - 64)
        return (col, int(m.group(2)))

    mc, mr = _parse(master_ref)
    cc, cr = _parse(cell_ref)
    dc, dr = cc - mc, cr - mr

    def _shift(m: "re.Match[str]") -> str:
        col_abs, col_letters, row_abs, row_num = m.groups()
        col = 0
        for ch in col_letters.upper():
            col = col * 26 + (ord(ch) - 64)
        if not col_abs:
            col += dc
        row = int(row_num)
        if not row_abs:
            row += dr
        if col < 1 or row < 1:
            return m.group(0)  # off-sheet: leave the token untouched
        letters = ""
        c = col
        while c > 0:
            c, r = divmod(c - 1, 26)
            letters = chr(65 + r) + letters
        return f"{col_abs}{letters}{row_abs}{row}"

    return re.sub(
        r"(\$?)([A-Za-z]{1,3})(\$?)(\d+)", _shift, text)


def _raw_xml_grid(content: bytes
                   ) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Per-sheet {'values', 'formulas'} straight from the xlsx package
    (stdlib XML). Fallback for workbooks openpyxl's strict reader
    rejects — the same Zoho-Sheet-XML situation core.formula_extractor
    and core.sheet_dataset_service handle with raw-XML scans. Shared-
    formula DEPENDENTS carry no <f> body, but the package names their
    master: the master's formula is translated to each dependent by
    its cell offset (Excel's own semantics), which is what recovers a
    price column's per-row formulas from packages the strict reader
    cannot open."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in names:
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst:
                if _local(si.tag) != "si":
                    continue
                parts: List[str] = []
                for child in si:
                    if _local(child.tag) == "t":
                        parts.append(child.text or "")
                    elif _local(child.tag) == "r":
                        parts.extend(sub.text or "" for sub in child
                                     if _local(sub.tag) == "t")
                shared_strings.append("".join(parts))
        sheet_display: Dict[str, str] = {}
        try:
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_target = {
                rel.get("Id"): rel.get("Target", "")
                for rel in rels
                if _local(rel.tag) == "Relationship"}
            for sh in wb.iter():
                if _local(sh.tag) != "sheet":
                    continue
                rid = sh.get(
                    "{http://schemas.openxmlformats.org/officeDocument"
                    "/2006/relationships}id")
                target = (rid_target.get(rid) or "").lstrip("/")
                if target and not target.startswith("xl/"):
                    target = f"xl/{target}"
                if target:
                    sheet_display[target] = sh.get("name") or target
        except Exception:  # noqa: BLE001 — names best-effort
            pass
        for sheet_path in sorted(
                n for n in names
                if n.startswith("xl/worksheets/") and n.endswith(".xml")):
            sheet_name = sheet_display.get(
                sheet_path, sheet_path.rsplit("/", 1)[-1])
            key = " ".join(str(sheet_name).lower().split())
            slot = out.setdefault(
                key, {"values": {}, "formulas": {}, "formula_cells": set()})
            root = ET.fromstring(zf.read(sheet_path))
            cells = [c for c in root.iter() if _local(c.tag) == "c"]
            # Pass 1: shared-formula masters (the si group's body owner).
            masters: Dict[str, Tuple[str, str]] = {}
            for c in cells:
                f = next((ch for ch in c if _local(ch.tag) == "f"), None)
                if (f is not None and f.get("t") == "shared"
                        and (f.text or "").strip()):
                    masters[f.get("si")] = (c.get("r") or "", f.text)
            # Pass 2: values + formulas, translating shared dependents.
            # EVERY cell carrying an <f> element (body or bodyless) is
            # recorded in formula_cells — the metadata that separates a
            # typed literal from a formula cell whose body is missing.
            for c in cells:
                ref = (c.get("r") or "").upper()
                if not ref:
                    continue
                v = next((ch for ch in c if _local(ch.tag) == "v"), None)
                f = next((ch for ch in c if _local(ch.tag) == "f"), None)
                if f is not None:
                    slot["formula_cells"].add(ref)
                ftext = (f.text or "").strip() if f is not None else ""
                if f is not None and not ftext \
                        and f.get("t") == "shared":
                    master = masters.get(f.get("si"))
                    if master:
                        ftext = _translate_shared_formula(
                            master[0], master[1], ref)
                if ftext:
                    slot["formulas"][ref] = (
                        ftext if ftext.startswith("=") else f"={ftext}")
                if v is None or v.text is None:
                    continue
                if c.get("t") == "s":
                    try:
                        slot["values"][ref] = shared_strings[int(v.text)]
                    except (ValueError, IndexError):
                        slot["values"][ref] = v.text
                else:
                    slot["values"][ref] = v.text
    return out


def workbook_grid_from_bytes(content: bytes
                             ) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Workbook bytes -> per-sheet {'values', 'formulas'}. openpyxl's
    normal reader translates shared formulas into per-cell strings —
    the completion path for dependent cells a sidecar never captured —
    and data_only=True yields the workbook's own stored values. When
    the strict reader rejects the package (Zoho-Sheet XML), the raw-XML
    scan provides the same shape (formulas best-effort)."""
    import io

    from openpyxl import load_workbook

    try:
        return _openpyxl_grid(content)
    except Exception:  # noqa: BLE001 — the raw scan is the fallback
        return _raw_xml_grid(content)


def _openpyxl_grid(content: bytes
                   ) -> Dict[str, Dict[str, Dict[str, str]]]:
    import io

    from openpyxl import load_workbook

    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    wbf = load_workbook(io.BytesIO(content), data_only=False)
    try:
        for ws in wbf.worksheets:
            key = " ".join(str(ws.title).lower().split())
            slot = out.setdefault(
                key, {"values": {}, "formulas": {}, "formula_cells": set()})
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("="):
                        ref = str(c.coordinate).upper()
                        slot["formulas"][ref] = c.value
                        slot["formula_cells"].add(ref)
    finally:
        wbf.close()
    wbv = load_workbook(io.BytesIO(content), read_only=True,
                        data_only=True)
    try:
        for ws in wbv.worksheets:
            key = " ".join(str(ws.title).lower().split())
            slot = out.setdefault(
                key, {"values": {}, "formulas": {}, "formula_cells": set()})
            for row in ws.iter_rows():
                for c in row:
                    if c.value is None or str(c.value) == "":
                        continue
                    slot["values"][
                        str(c.coordinate).upper()] = str(c.value)
    finally:
        wbv.close()
    return out


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class _Incomplete(Exception):
    """Evaluation cannot proceed — the exact gap travels with it."""

    def __init__(self, missing: str = "", unsupported: str = "",
                 references: Optional[List[Tuple[str, str]]] = None):
        super().__init__(missing or unsupported)
        self.missing = missing
        self.unsupported = unsupported
        #: (sheet, cell) references that, if provided, may complete the
        #: evaluation — what a live read should fetch.
        self.references = references or []


@dataclass
class ReferenceDependency:
    """One reference the evaluation touched, with its role and value.

    Roles are neutral: 'input' (a value consumed as given — the row's
    own literals in a workbook, a caller's named input), 'reference'
    (a looked-up cell: parameter blocks, cross-sheet sources) and
    'intermediate' (a cell computed by formula during the walk)."""
    sheet: str
    cell: str            # or the named input, sheet=''
    role: str
    value: Optional[str] = None   # Decimal-string when resolved
    formula: str = ""
    note: str = ""
    source: str = "frame"  # 'frame' | 'frame_cache' | 'live_read' | 'computed' | 'input'
    unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"sheet": self.sheet, "cell": self.cell, "role": self.role,
                "value": self.value, "formula": self.formula or None,
                "note": self.note or None, "source": self.source,
                "unit": self.unit or None}


@dataclass
class FormulaResult:
    """One output's evaluation, with STRUCTURALLY SEPARATE result
    types (round 71 — the owner's contract: a cached output must never
    be reported as a completed calculation):

    ``status``:
      'computed'      the formula was evaluated — ``value`` is the
                      Decimal the supported language produced and
                      ``steps`` replays every operation;
      'stored_value'  the cell is established (by workbook metadata)
                      as a TYPED LITERAL — ``value`` is the stored
                      number, observed, NOT computed; no steps exist;
      'incomplete'    ``missing``/``unsupported`` names the exact gap
                      and ``missing_references`` lists what a live
                      read could fill.

    A missing output formula NEVER yields 'computed' or a completed
    calculation; a stored value is an observation, and comparing it
    with itself is not verification."""
    reference: str               # 'BurrKing!E25' or the expression text
    status: str = "incomplete"
    value: Optional[Decimal] = None
    missing: str = ""
    unsupported: str = ""
    missing_references: List[Tuple[str, str]] = field(default_factory=list)
    expression: str = ""          # normalized, dependency-annotated
    dependencies: List[ReferenceDependency] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    #: References resolved from stored values where no formula was
    #: known — flagged, never presented as reconstructed arithmetic.
    cache_substituted: List[str] = field(default_factory=list)
    #: The source's own stored output for this reference, when the
    #: caller has one (a comparison, never a foundation).
    cached_value: Optional[str] = None
    #: Optional unit annotation, recorded verbatim.
    unit: str = ""
    #: Origin identity the calling application supplied (file name,
    #: content version, teaching id…). The engine records; it does not
    #: interpret.
    origin: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class FormulaEngine:
    """Evaluates one output through the supported language, recording
    every dependency and step. Two input formats share this execution
    path: REFERENCES (cell books, with an optional provider for
    cross-sheet resolution) and EXPLICIT INPUTS (named bindings — the
    taught-expression format).

    Parsing is STRUCTURAL — Python `ast` over the normalized formula,
    the discipline core.derivation_verification established — not
    regex case collection: every node must be a supported literal,
    reference, named input, operator or function, or the evaluation
    stops INCOMPLETE with the exact construct named."""

    def __init__(self, book: Optional[CellBook] = None,
                 provider: Optional[Callable[[str], Optional[CellBook]]]
                 = None,
                 inputs: Optional[Dict[str, Any]] = None,
                 units: Optional[Dict[str, str]] = None,
                 row_of_interest: Optional[int] = None):
        self.book = book
        self.provider = provider
        self.inputs = {str(k): v for k, v in (inputs or {}).items()}
        self.units = dict(units or {})
        self.row = int(row_of_interest) if row_of_interest else None
        self.dependencies: List[ReferenceDependency] = []
        self.steps: List[Dict[str, Any]] = []
        self._seen: Set[Tuple[str, str]] = set()
        self._stack: Set[Tuple[str, str]] = set()
        self._depth = 0

    # -- book resolution ----------------------------------------------

    def _book_for(self, sheet: str) -> CellBook:
        if self.book is not None and sheet.strip().lower() \
                == self.book.name.strip().lower():
            return self.book
        other = self.provider(sheet) if self.provider else None
        if other is None:
            raise _Incomplete(
                missing=f"cross-sheet reference to '{sheet}' cannot be "
                f"resolved: no source is available for it")
        return other

    @staticmethod
    def _formula_columns(book: CellBook) -> Set[str]:
        """Column letters that carry at least one formula in this
        source — the evidence that separates a genuine literal column
        from a lost shared formula."""
        cols = set()
        for key in book.formulas:
            m = _CELL_RE.match(key)
            if m:
                cols.add(m.group(1).upper())
        return cols

    # -- reference resolution ------------------------------------------

    def _record(self, dep: ReferenceDependency) -> None:
        key = (dep.sheet.strip().lower(), dep.cell.upper())
        if key not in self._seen:
            self._seen.add(key)
            self.dependencies.append(dep)

    def _role_for(self, sheet: str, cell: str, has_formula: bool) -> str:
        m = _CELL_RE.match(cell)
        same_sheet = (self.book is not None and sheet.strip().lower()
                      == self.book.name.strip().lower())
        if same_sheet and self.row is not None and m \
                and int(m.group(2)) == self.row:
            # A row-of-interest cell is an INPUT only when literal; a
            # same-row FORMULA cell is an intermediate of the chain.
            return "intermediate" if has_formula else "input"
        return "reference"

    @staticmethod
    def _decimal(raw: Any, sheet: str, cell: str) -> Decimal:
        try:
            dec = Decimal(str(raw).replace(",", ""))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise FormulaInputError(
                f"{sheet}!{cell} holds a non-numeric value "
                f"({raw!r})") from exc
        if not dec.is_finite():
            raise FormulaInputError(
                f"{sheet}!{cell} holds a non-finite value")
        return dec

    def value_of(self, sheet: str, cell: str) -> Decimal:
        """Resolve ONE reference: its formula first (the source's own
        arithmetic — a stored value is never substituted for a formula
        operand), then its stored value, then the blank rule, then
        INCOMPLETE naming the reference."""
        book = self._book_for(sheet)
        key = cell.upper()
        formula = book.formulas.get(key)
        dep = ReferenceDependency(
            sheet=book.name, cell=key,
            role=self._role_for(sheet, key, bool(formula)),
            formula=formula or "",
            source=book.cell_source(key))
        if formula:
            if (book.name.strip().lower(), key) in self._stack:
                raise _Incomplete(
                    unsupported=f"circular reference at "
                                f"{book.name}!{key}")
            if self._depth >= _MAX_CHAIN_DEPTH:
                raise _Incomplete(
                    unsupported=f"dependency chain deeper than "
                                f"{_MAX_CHAIN_DEPTH} at {book.name}!"
                                f"{key}")
            self._stack.add((book.name.strip().lower(), key))
            self._depth += 1
            try:
                val = self.eval_formula(formula, book, key)
            finally:
                self._depth -= 1
                self._stack.discard((book.name.strip().lower(), key))
            dep.value = str(val)
            dep.source = "computed"
            self._record(dep)
            return val
        if key in book.values:
            # OPERAND STORED-VALUE HONESTY: a reference with a stored
            # value but no formula may be a literal OR a lost shared
            # formula. METADATA decides when the source carries it:
            # a formula cell without a body is flagged (arithmetic we
            # do not have); an established literal is a clean input.
            # Without metadata, the row-of-interest column heuristic
            # still flags the demonstrated loss pattern (documented
            # heuristic — it cannot prove anything about one cell).
            val = self._decimal(book.values[key], book.name, key)
            dep.value = str(val)
            m = _CELL_RE.match(key)
            same_row = bool(
                m and self.row is not None
                and int(m.group(2)) == self.row
                and book.name.strip().lower()
                == (self.book.name.strip().lower()
                    if self.book else book.name.strip().lower()))
            known_formula_cell = (
                book.formula_cells is not None
                and key in book.formula_cells)
            if dep.source == "frame":
                if known_formula_cell:
                    dep.source = "frame_cache"
                    dep.note = ("this cell is a formula cell (workbook "
                                "metadata) whose body is unavailable — "
                                "its stored value stands in for "
                                "arithmetic we do not have; a live read "
                                "can restore the formula")
                elif book.formula_cells is None and same_row and m \
                        and m.group(1).upper() \
                        in self._formula_columns(book):
                    dep.source = "frame_cache"
                    dep.note = ("no formula in the durable source for a "
                                "row cell in a column that carries "
                                "formulas elsewhere — the stored value "
                                "was used; a live read can replace it "
                                "with the real formula")
            self._record(dep)
            return val
        if key in book.empty:
            dep.value = "0"
            dep.note = ("blank cell — spreadsheet arithmetic treats a "
                        "blank operand as 0")
            self._record(dep)
            return Decimal(0)
        self._record(dep)
        raise _Incomplete(
            missing=f"{book.name}!{key} has no stored value and no "
            f"formula — the reference cannot be resolved from the "
            f"available sources",
            references=[(book.name, key)])

    # -- named inputs (the explicit-input format) -----------------------

    def input_value(self, name: str) -> Decimal:
        """Resolve a named input. Explicit inputs shadow same-shaped
        cell references (the caller named them deliberately)."""
        if name in self.inputs and self.inputs[name] is not None:
            raw = self.inputs[name]
            try:
                dec = Decimal(str(raw).replace(",", ""))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise FormulaInputError(
                    f"input '{name}' is not numeric: {raw!r}") from exc
            if not dec.is_finite():
                raise FormulaInputError(
                    f"input '{name}' is not finite")
            self._record(ReferenceDependency(
                sheet="", cell=name, role="input", value=str(dec),
                source="input", unit=self.units.get(name, "")))
            return dec
        raise _Incomplete(
            missing=f"the input '{name}' was not provided and no "
            f"reference resolves it",
            references=[])

    # -- formula normalization + AST evaluation -------------------------

    def _normalize(self, formula: str
                   ) -> Tuple[str, Dict[str, Tuple[str, str]]]:
        expr = (formula or "").strip()
        if expr.startswith("="):
            expr = expr[1:]
        tokens: Dict[str, Tuple[str, str]] = {}

        def _sub(m: "re.Match[str]") -> str:
            sheet = (m.group(1) or m.group(2) or "").strip()
            cell = f"{m.group(3)}{m.group(4)}".upper()
            tok = f"__XS{len(tokens)}__"
            tokens[tok] = (sheet, cell)
            return tok

        expr = _SHEET_QUALIFIED_RE.sub(_sub, expr)
        expr = expr.replace("$", "").replace("^", "**")
        return expr, tokens

    def eval_formula(self, formula: str, book: Optional[CellBook],
                     cell: str) -> Decimal:
        expr, tokens = self._normalize(formula)
        try:
            node = ast.parse(expr, mode="eval").body
        except SyntaxError as exc:
            raise _Incomplete(
                unsupported=f"the formula ={formula} at "
                            f"{(book.name + '!') if book else ''}{cell} "
                            f"uses syntax outside the supported "
                            f"language ({exc.msg})") from exc
        with localcontext() as ctx:
            ctx.prec = _ENGINE_PRECISION
            return self._eval(node, book, cell, tokens)

    def _eval(self, node: ast.AST, book: Optional[CellBook], cell: str,
              tokens: Dict[str, Tuple[str, str]]) -> Decimal:
        where = f"{book.name}!{cell}" if book else cell
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(
                    node.value, (int, float)):
                raise _Incomplete(
                    unsupported=f"non-numeric literal {node.value!r} in "
                                f"{where}")
            return Decimal(str(node.value))
        if isinstance(node, ast.Name):
            tok = node.id
            if tok in tokens:
                sheet, tcell = tokens[tok]
                return self.value_of(sheet, tcell)
            if _CELL_RE.match(tok):
                # Explicit inputs shadow same-shaped references.
                if tok in self.inputs:
                    return self.input_value(tok)
                if book is not None:
                    return self.value_of(book.name, tok.upper())
                raise _Incomplete(missing=(
                    f"the reference {tok} cannot be resolved: no cell "
                    f"source is attached to this evaluation"))
            return self.input_value(tok)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand, book, cell, tokens)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            raise _Incomplete(unsupported=f"unary operator in {where}")
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, book, cell, tokens)
            right = self._eval(node.right, book, cell, tokens)
            op_name = {ast.Add: "add", ast.Sub: "subtract",
                       ast.Mult: "multiply", ast.Div: "divide",
                       ast.Pow: "power"}.get(type(node.op))
            if op_name is None:
                raise _Incomplete(
                    unsupported=f"an arithmetic operator in {where} is "
                                f"outside the supported set (+ - * /)")
            try:
                if op_name == "add":
                    out = left + right
                elif op_name == "subtract":
                    out = left - right
                elif op_name == "multiply":
                    out = left * right
                elif op_name == "divide":
                    if right == 0:
                        raise FormulaInputError(
                            f"{where} divides by zero")
                    out = left / right
                else:  # power
                    if right != right.to_integral_value() or right < 0 \
                            or right > 99:
                        raise _Incomplete(
                            unsupported=f"exponent {right} in {where} is "
                                        f"outside the supported integer "
                                        f"range")
                    out = left ** int(right)
            except FormulaInputError:
                raise
            except (InvalidOperation, OverflowError) as exc:
                raise _Incomplete(
                    unsupported=f"arithmetic failed in {where}: "
                                f"{exc}") from exc
            self.steps.append({
                "cell": cell if book is not None else where,
                "op": op_name,
                "operands": [{"value": str(left)}, {"value": str(right)}],
                "output": str(out)})
            return out
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise _Incomplete(
                    unsupported=f"an unsupported call shape in {where}")
            fname = node.func.id.upper()
            if fname not in SUPPORTED_FUNCTIONS:
                raise _Incomplete(
                    unsupported=f"the function {fname}() in {where} is "
                                f"not in the supported function set — "
                                f"the result is incomplete rather than "
                                f"approximated")
            args = [self._eval(a, book, cell, tokens) for a in node.args]
            if not args:
                raise _Incomplete(
                    unsupported=f"{fname}() with no operands in {where}")
            if fname == "SUM":
                out = args[0]
                for a in args[1:]:
                    out += a
                    self.steps.append({
                        "cell": cell if book is not None else where,
                        "op": "add",
                        "operands": [{"value": str(out - a)},
                                     {"value": str(a)}],
                        "output": str(out)})
                return out
            if fname == "MIN":
                return min(args)
            if fname == "MAX":
                return max(args)
            if fname == "ABS":
                return abs(args[0])
            if fname == "INT":
                return args[0].to_integral_value(rounding=ROUND_FLOOR)
            # ROUND family: value[, digits]
            digits = int(args[1]) if len(args) > 1 else 0
            if len(args) > 2:
                raise _Incomplete(
                    unsupported=f"{fname}() with extra operands in {where}")
            out = excel_round(args[0], digits,
                              {"ROUNDUP": "up", "ROUNDDOWN": "down",
                               "ROUND": "half"}[fname])
            self.steps.append({
                "cell": cell if book is not None else where,
                "op": {"ROUNDUP": "round_up", "ROUNDDOWN": "round_down",
                       "ROUND": "round_half"}[fname],
                "operands": [{"value": str(args[0])}],
                "places": digits, "output": str(out)})
            return out
        raise _Incomplete(
            unsupported=f"formula construct {type(node).__name__} in "
                        f"{where} is outside the supported language")


def excel_round(value: Decimal, digits: int, mode: str) -> Decimal:
    """Spreadsheet rounding on Decimal. ROUNDUP is away from zero,
    ROUNDDOWN toward zero, ROUND half-away-from-zero — the sign is
    reapplied after rounding the magnitude so negatives behave like
    the spreadsheet's."""
    quantum = Decimal(1).scaleb(-int(digits))
    if value == 0:
        return value.quantize(quantum)
    sign = Decimal(-1) if value < 0 else Decimal(1)
    mag = abs(value)
    if mode == "up":
        q = mag.quantize(quantum, rounding=ROUND_CEILING)
    elif mode == "down":
        q = mag.quantize(quantum, rounding=ROUND_FLOOR)
    else:
        q = mag.quantize(quantum, rounding=ROUND_HALF_UP)
    return (q * sign).quantize(quantum)


# ---------------------------------------------------------------------------
# The two entry points — one execution path
# ---------------------------------------------------------------------------

def evaluate_reference(
        sheet_name: str,
        cell: str,
        book: CellBook,
        provider: Optional[Callable[[str], Optional[CellBook]]] = None,
        *,
        row_of_interest: Optional[int] = None,
        cached_value: Optional[str] = None,
        origin: Optional[Dict[str, str]] = None) -> FormulaResult:
    """Evaluate ONE output reference from a reference source (the
    workbook input format). Fail-closed: 'complete' only when the
    ENTIRE dependency tree resolved through the supported language."""
    oc = str(cell).upper()
    result = FormulaResult(
        reference=f"{sheet_name}!{oc}",
        cached_value=cached_value,
        origin=dict(origin or {}))
    formula = book.formulas.get(oc)
    engine = FormulaEngine(book, provider, row_of_interest=row_of_interest)
    if not formula:
        # METADATA-DRIVEN (round 71): whether this cell is a formula
        # cell is established by the workbook's own cell/formula
        # metadata (an <f> element in the package), never by what
        # OTHER cells in the column happen to carry.
        if book.formula_cells is not None and oc in book.formula_cells:
            # A formula cell whose body the current sources lack: the
            # calculation is INCOMPLETE — the stored value must NOT be
            # reported as a completed calculation.
            result.missing = (
                f"{sheet_name}!{oc} is a formula cell (workbook "
                f"metadata) but its formula body is unavailable from "
                f"the current sources — a live read of the workbook "
                f"can supply it; the stored value is not reported as "
                f"a computed result")
            result.missing_references = [(sheet_name, oc)]
            return result
        if book.formula_cells is not None and oc in book.values:
            # Established literal: a stored-value OBSERVATION.
            try:
                val = Decimal(
                    str(book.values[oc]).replace(",", ""))
            except (InvalidOperation, ValueError):
                val = None
            if val is not None and val.is_finite():
                result.status = "stored_value"
                result.value = val
                result.dependencies = [ReferenceDependency(
                    sheet=sheet_name, cell=oc, role="input",
                    value=str(val), source=book.cell_source(oc),
                    note=("typed literal (workbook metadata carries no "
                          "formula for this cell) — stored value, "
                          "observed, not computed"))]
                return result
            result.missing = (
                f"{sheet_name}!{oc} holds a non-numeric stored value")
            return result
        if book.formula_cells is None and oc in book.values:
            # Durable-only state: a stored value exists but NOTHING
            # establishes whether the cell is a formula cell — the
            # honest outcome is INCOMPLETE (a live read decides), not
            # a completed calculation from the cache.
            result.missing = (
                f"{sheet_name}!{oc} has no formula in the durable "
                f"sources and no metadata to establish whether it is "
                f"a formula cell — a live read of the workbook "
                f"decides; its stored value is not reported as a "
                f"computed result")
            result.missing_references = [(sheet_name, oc)]
            return result
        result.missing = (
            f"{sheet_name}!{oc} has no formula, no stored value and "
            f"no metadata — the reference cannot be resolved")
        result.missing_references = [(sheet_name, oc)]
        return result
    try:
        val = engine.value_of(sheet_name, oc)
    except _Incomplete as inc:
        result.missing = inc.missing
        result.unsupported = inc.unsupported
        result.missing_references = inc.references
        result.dependencies = list(engine.dependencies)
        result.steps = list(engine.steps)
        return result
    except FormulaInputError as exc:
        result.unsupported = f"the source's own arithmetic is invalid: {exc}"
        result.dependencies = list(engine.dependencies)
        result.steps = list(engine.steps)
        return result
    result.status = "computed"
    result.value = val
    result.dependencies = list(engine.dependencies)
    result.steps = list(engine.steps)
    result.cache_substituted = sorted({
        f"{d.sheet}!{d.cell}" for d in result.dependencies
        if d.source == "frame_cache"})
    result.expression = _render_expression(formula, engine)
    return result


def evaluate_expression(
        expression: str,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        units: Optional[Dict[str, str]] = None,
        output_unit: str = "",
        origin: Optional[Dict[str, str]] = None) -> FormulaResult:
    """Evaluate an EXPLICITLY PROVIDED expression (the taught-
    expression input format): the same supported language, with
    identifiers resolved from ``inputs`` (named bindings — hours,
    rate, demand… whatever the calling workflow teaches; the engine
    gives them no business meaning). Missing inputs are named
    precisely; nothing is invented."""
    expr = str(expression or "").strip()
    result = FormulaResult(
        reference=expr[:120],
        unit=str(output_unit or ""),
        origin=dict(origin or {}))
    if not expr:
        result.missing = "an empty expression cannot be evaluated"
        return result
    engine = FormulaEngine(inputs=inputs, units=units)
    try:
        val = engine.eval_formula(expr, None, "expression")
    except _Incomplete as inc:
        result.missing = inc.missing
        result.unsupported = inc.unsupported
        result.dependencies = list(engine.dependencies)
        result.steps = list(engine.steps)
        return result
    except FormulaInputError as exc:
        result.unsupported = str(exc)
        result.dependencies = list(engine.dependencies)
        return result
    result.status = "computed"
    result.value = val
    result.dependencies = list(engine.dependencies)
    result.steps = list(engine.steps)
    result.expression = _render_expression(expr, engine)
    return result


def _render_expression(formula: str, engine: FormulaEngine) -> str:
    """The normalized formula with each resolved reference annotated —
    a reviewer reads WHAT was evaluated."""
    try:
        expr, _ = engine._normalize(formula)  # noqa: SLF001 — internal
    except Exception:  # noqa: BLE001 — rendering is best-effort
        return formula
    notes = []
    for dep in engine.dependencies:
        if dep.role == "reference":
            notes.append(f"{dep.sheet}!{dep.cell}={dep.value}")
        elif dep.role == "input":
            notes.append(f"{dep.cell}={dep.value}")
    if notes:
        return f"{expr}   [{'; '.join(notes)}]"
    return expr


# ---------------------------------------------------------------------------
# Independent verification oracle — the repo's declared Excel engine
# ---------------------------------------------------------------------------

def verify_with_formulas_engine(
        content: bytes,
        sheet_name: str,
        cell: str) -> Optional[str]:
    """Re-evaluate one cell with the ESTABLISHED engine the repo
    already declares and runs (formulas==1.3.4, the engine behind
    core.workbook_runtime) — an evaluation path independent of this
    module. Returns the engine's value as a string, or None when the
    engine cannot evaluate it (never raises into the caller; an
    unevaluable check is reported as absent, not clean)."""
    try:
        import formulas as _formulas
    except ImportError:
        return None
    path = ""
    try:
        with tempfile.NamedTemporaryFile(
                suffix=".xlsx", delete=False) as tf:
            tf.write(content)
            path = tf.name
        model = _formulas.ExcelModel().loads(path).finish()
        solution = model.calculate()
        key = (f"'[{os.path.basename(path)}]"
               f"{str(sheet_name).strip()}'!{cell}").upper()
        by_ref = {str(k).upper(): v for k, v in solution.items()}
        val = by_ref.get(key)
        if val is None:
            return None
        if hasattr(val, "value") and not isinstance(
                val, (int, float, bool, str)):
            val = val.value  # Ranges -> scalar
        while isinstance(val, (list, tuple)) and len(val) == 1:
            val = val[0]
        if hasattr(val, "item") and not isinstance(
                val, (int, float, bool, str)):
            try:
                val = val.item()
            except (ValueError, TypeError):
                return None
        return None if val is None else str(val)
    except Exception:  # noqa: BLE001 — verification is additive
        return None
    finally:
        try:
            if path:
                os.unlink(path)
        except OSError:
            pass
