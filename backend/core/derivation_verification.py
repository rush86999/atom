# -*- coding: utf-8 -*-
"""Verify DERIVED figures against the workbook evidence, instead of trusting a citation.

Why this module exists (audit directive 3, 2026-09-16). The orchestrator used to
skip figure-grounding entirely when the evidence block carried a formula marker
AND the reply contained any row citation::

    _figures_derivable = bool(tool_block and "FORMULAS FOR THE MATCHED ROW" in tool_block)
    _derivation_reply  = _figures_derivable and _ROW_CITE_RE.search(content)

So an INVENTED chain evaded verification by writing "row 235" anywhere in the
reply. The motivation behind the bypass was legitimate — a correctly COMPUTED
value is absent from the evidence text by construction, so a text-presence check
cannot call it fabricated — but a citation is not evidence of arithmetic.
Mentioning a row proves nothing about the numbers derived from it.

The contract implemented here:

* ``STORED``        the figure appears as a value in the evidence (a cell value),
* ``COMPUTED``      the figure is reproducible by evaluating the referenced
                    formulas against the referenced cells (dependencies resolved),
* ``UNRESOLVED``    a dependency is missing (a referenced cell is outside the
                    delivered window), so the figure can be neither confirmed nor
                    denied — reported as UNVERIFIED, never as clean,
* ``CONTRADICTED``  the figure is claimed as a derivation step but the formula
                    that would produce it yields a different number.

Only ``CONTRADICTED`` is a failure verdict. ``UNRESOLVED`` is deliberately NOT
clean — "we could not check" must never read as "we checked and it was fine".

Evaluation is bounded and safe: formulas are parsed as Python expressions,
whitelisted to literals, cell references, arithmetic and a few spreadsheet
functions. No attribute access, calls to arbitrary names, or ``eval`` of raw
text.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── outcomes ────────────────────────────────────────────────────────────────
VERIFIED_STORED = "stored"
VERIFIED_COMPUTED = "computed"
UNRESOLVED = "unresolved"
CONTRADICTED = "contradicted"

#: Spreadsheet functions we can evaluate. Anything else makes the claim
#: UNRESOLVED rather than wrong — an unknown function is a gap in the checker,
#: not evidence against the answer.
_SUPPORTED_FUNCS = {
    "ROUNDUP": lambda x, d=0: _roundup(x, d),
    "ROUND": lambda x, d=0: round(x, int(d)),
    "ROUNDDOWN": lambda x, d=0: _rounddown(x, d),
    "INT": lambda x: int(x),
    "ABS": lambda x: abs(x),
    "SUM": lambda *a: sum(a),
    "MIN": lambda *a: min(a),
    "MAX": lambda *a: max(a),
}

_CELL_RE = re.compile(r"^([A-Za-z]{1,3})(\d{1,7})$")
#: A number in prose: 7,519.00 / 5350 / 7519.0 / 1 893.70
_NUMBER_RE = re.compile(r"\d[\d,\s]*(?:\.\d+)?")


def _roundup(value: float, digits: int = 0) -> float:
    """Excel ROUNDUP: away from zero, at ``digits`` decimal places."""
    import math

    factor = 10 ** int(digits)
    scaled = value * factor
    return (math.ceil(scaled) if scaled >= 0 else math.floor(scaled)) / factor


def _rounddown(value: float, digits: int = 0) -> float:
    import math

    factor = 10 ** int(digits)
    scaled = value * factor
    return (math.floor(scaled) if scaled >= 0 else math.ceil(scaled)) / factor


def _to_number(text: Any) -> Optional[float]:
    s = str(text or "").strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_evidence(block: str) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, Dict[str, float]]]:
    """Pull (cell values, cell formulas, per-row column values) out of a block.

    Understands the two shapes ``render_dataset_answer`` emits::

        R235 | Product Name=F-52"x16G | LIST Price=7519.0 | Factory Price=5350 | …
        FORMULAS FOR THE MATCHED ROW(S) — …: D235==P235 | G235==F235*0.9 | …

    Column LABELS are registered as cell references too (``F235`` → the value in
    the column whose letter is F) so a formula naming F235 can resolve against
    the row's data. Fault-isolated: a malformed block yields empty maps.
    """
    values: Dict[str, float] = {}
    formulas: Dict[str, str] = {}
    rows: Dict[str, Dict[str, float]] = {}
    column_letters: Dict[str, str] = {}
    try:
        for raw in (block or "").splitlines():
            line = raw.strip()
            if line.startswith("R") and "|" in line:
                head, _, rest = line.partition("|")
                row_id = head.strip().lstrip("R").strip()
                if not row_id.isdigit():
                    continue
                cells: Dict[str, float] = {}
                for part in rest.split("|"):
                    if "=" not in part:
                        continue
                    label, _, val = part.partition("=")
                    num = _to_number(val)
                    if num is not None:
                        cells[label.strip()] = num
                rows[row_id] = cells
            elif line.startswith("COLUMNS:") and "=" in line:
                _, _, body = line.partition(":")
                for part in body.split("|"):
                    if "=" not in part:
                        continue
                    name, _, letter = part.partition("=")
                    name, letter = name.strip(), letter.strip().upper()
                    if name and re.fullmatch(r"[A-Z]{1,3}", letter):
                        column_letters[name] = letter
            elif line.startswith("FORMULAS FOR") and ":" in line:
                _, _, body = line.partition(":")
                for part in body.split("|"):
                    if "=" not in part:
                        continue
                    cell, _, formula = part.partition("=")
                    cell = cell.strip().lstrip("=").strip()
                    formula = formula.strip().lstrip("=").strip()
                    if _CELL_RE.match(cell) and formula.startswith("=") or formula:
                        formulas[cell] = formula
    except Exception:  # noqa: BLE001 — a malformed block must not raise
        return {}, {}, {}
    # Column-label → cell letters, per row: "Factory Price" is column F here.
    # The letters come from the block's own COLUMNS line when present (authoritative
    # — the extractor knows its own layout), else from a bare-letter label.
    for row_id, cells in rows.items():
        for label, num in cells.items():
            letter = column_letters.get(label) or _column_letter(label)
            if letter:
                values.setdefault(f"{letter}{row_id}", num)
    return values, formulas, rows


def _column_letter(label: str) -> Optional[str]:
    """The spreadsheet column a dataset column label corresponds to.

    ``render_dataset_answer`` renders named columns, not letters, so the letters
    are recovered positionally from the KNOWN order of the workbook's columns —
    a mapping supplied by the caller when available. Absent that, the label
    itself is used when it is already a bare letter.
    """
    lab = (label or "").strip()
    if re.fullmatch(r"[A-Za-z]{1,3}", lab):
        return lab.upper()
    return None


class _Evaluator:
    """Whitelisted arithmetic over cell references. Never executes arbitrary code."""

    def __init__(self, cell_values: Dict[str, float], formulas: Dict[str, str]) -> None:
        self.cell_values = cell_values
        self.formulas = formulas
        self._stack: List[str] = []

    def value_of(self, cell: str) -> Optional[float]:
        cell = cell.upper()
        if cell in self.cell_values:
            return self.cell_values[cell]
        formula = self.formulas.get(cell)
        if formula is None:
            return None
        if cell in self._stack:  # circular reference
            return None
        self._stack.append(cell)
        try:
            return self.eval_formula(formula)
        finally:
            self._stack.pop()

    def eval_formula(self, formula: str) -> Optional[float]:
        expr = (formula or "").strip().lstrip("=").strip()
        if not expr:
            return None
        try:
            node = ast.parse(expr, mode="eval")
        except SyntaxError:
            return None
        try:
            return self._eval(node.body)
        except Exception:  # noqa: BLE001 — any failure = unresolved, not wrong
            return None

    def _eval(self, node: ast.AST) -> Optional[float]:
        if isinstance(node, ast.Constant):
            return float(node.value) if isinstance(node.value, (int, float)) else None
        if isinstance(node, ast.Name):
            return self.value_of(node.id)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            if operand is None:
                return None
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            return None
        if isinstance(node, ast.BinOp):
            left, right = self._eval(node.left), self._eval(node.right)
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right if right else None
            if isinstance(node.op, ast.Pow):
                return left ** right
            return None
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                return None
            fn = _SUPPORTED_FUNCS.get(node.func.id.upper())
            if fn is None:
                return None
            args = [self._eval(a) for a in node.args]
            if any(a is None for a in args):
                return None
            return fn(*args)
        return None


@dataclass
class FigureVerdict:
    """One figure from the reply, and what the evidence says about it."""

    figure: float
    status: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"figure": self.figure, "status": self.status, "detail": self.detail}


@dataclass
class DerivationVerification:
    """Outcome of checking a derivation reply against its evidence block."""

    verdicts: List[FigureVerdict] = field(default_factory=list)
    unresolved_cells: List[str] = field(default_factory=list)

    @property
    def contradicted(self) -> List[FigureVerdict]:
        return [v for v in self.verdicts if v.status == CONTRADICTED]

    @property
    def verified(self) -> List[FigureVerdict]:
        return [
            v for v in self.verdicts
            if v.status in (VERIFIED_STORED, VERIFIED_COMPUTED)
        ]

    @property
    def claims(self) -> int:
        return len(self.verdicts)

    @property
    def is_clean(self) -> bool:
        """Clean ONLY when something was actually CHECKED and passed.

        Two distinct ways to be not-clean, and the caller must treat both as
        "unverified" rather than "grounded":

        * a claim was contradicted by the workbook's own formulas,
        * a claim could not be resolved because its dependencies are outside the
          delivered window.

        ``checked`` guards the empty case: a reply with no cell-anchored claim
        has had NOTHING verified, and reporting that as clean would hand out a
        grounding verdict for work never checked (the same "silence reads as
        approval" failure this contract exists to remove).
        """
        return self.checked > 0 and not self.contradicted and not self.unresolved_cells

    @property
    def checked(self) -> int:
        """Claims that were positively checked (stored or reproduced)."""
        return len(self.verified)

    def summary(self) -> str:
        if not self.claims:
            return "unverified — the reply made no cell-anchored claim to check"
        if self.contradicted:
            first = self.contradicted[0]
            return (
                f"{len(self.contradicted)} figure(s) contradicted by the "
                f"workbook formulas (e.g. {first.figure:g}: {first.detail})"
            )
        if self.unresolved_cells:
            return (
                "unverified — dependencies outside the delivered window: "
                + ", ".join(sorted(set(self.unresolved_cells))[:6])
            )
        return f"{len(self.verified)} figure(s) verified against the evidence"


#: A claim attributes a figure to a CELL. Two ways replies do that:
#:   letter form  — "G235 = 4815", "G235 -> 4815", "G235 yields 4815"
#:   label form   — "the List Price on row 235 is 7519", "row 235's Factory Price: 5350"
#: Both are checkable statements. Anchoring on the cell is what makes the check
#: meaningful: without it a row number (235) or an input constant (700) reads as
#: a "derivation step" and gets contradicted by an unrelated formula (caught in
#: testing before this shipped).
_LETTER_CLAIM_RE = re.compile(
    r"\b([A-Za-z]{1,3})(\d{1,7})\b\s*(?:=|==|->|→|:|yields|gives|becomes|is)\s*"
    r"\$?\s*([\d][\d,\s]*(?:\.\d+)?)",
    re.IGNORECASE,
)
#: "… <label> … row 235 … is <number>" — the label names the column, the row
#: number names the row. Tolerant of the connector words people actually write.
_LABEL_CLAIM_RE = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 /()\-]{2,40}?)\s*(?:on|in|at|for)?\s*"
    r"(?:row|r)\s*[:#]?\s*(?P<row>\d{1,7})\s*(?:'s)?\s*"
    r"(?:is|=|:|of|yields|gives|→|->)\s*\$?\s*(?P<value>[\d][\d,\s]*(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass
class Claim:
    """A figure the reply attributes to a specific cell."""

    cell: str
    claimed: float
    raw: str = ""


def _resolve_label(label: str, row: str, column_letters: Dict[str, str]) -> Optional[str]:
    """'List Price' + '235' -> 'D235' using the delivered COLUMNS bridge."""
    want = " ".join(str(label or "").split()).strip(" :,-").lower()
    if not want:
        return None
    for name, letter in column_letters.items():
        if " ".join(str(name).split()).lower() == want:
            return f"{letter}{row}"
    # Longest delivered label contained in the phrase ("the LIST Price" etc.)
    best = ""
    for name, letter in column_letters.items():
        n = " ".join(str(name).split()).lower()
        if n and n in want and len(n) > len(best):
            best = n
            best_letter = letter
    return f"{best_letter}{row}" if best else None


def extract_claims(reply: str, column_letters: Optional[Dict[str, str]] = None) -> List[Claim]:
    """Cell-anchored figures from a derivation reply (letter or label form)."""
    out: List[Claim] = []
    seen: set = set()
    text = reply or ""
    letters = column_letters or {}
    for m in _LETTER_CLAIM_RE.finditer(text):
        # Reject the label-form's "row 235 is 7519" — "row" is not a column.
        if m.group(1).upper() == "ROW":
            continue
        value = _to_number(m.group(3))
        cell = f"{m.group(1).upper()}{m.group(2)}"
        if value is None or (cell, value) in seen:
            continue
        seen.add((cell, value))
        out.append(Claim(cell=cell, claimed=value, raw=m.group(0)[:60]))
    for m in _LABEL_CLAIM_RE.finditer(text):
        cell = _resolve_label(m.group("label"), m.group("row"), letters)
        value = _to_number(m.group("value"))
        if not cell or value is None or (cell, value) in seen:
            continue
        seen.add((cell, value))
        out.append(Claim(cell=cell, claimed=value, raw=m.group(0)[:60]))
    return out


def verify_derivation_claims(
    reply: str,
    tool_block: str,
    *,
    tol: float = 0.01,
) -> DerivationVerification:
    """Check the reply's CELL-ANCHORED figures against the evidence.

    Contract (audit directive 3):

    * a figure matching a delivered cell value is STORED;
    * a claim about a cell whose formula reproduces the figure is COMPUTED —
      arithmetic is checked by EVALUATION, not by the figure appearing as text,
      because a correctly computed value is absent from the source by
      construction;
    * a claim about a cell whose formula evaluates to something materially
      different is CONTRADICTED;
    * a claim whose dependencies are outside the delivered window is UNRESOLVED
      (unverifiable), which is NOT clean;
    * a figure the reply never anchors to a cell is simply not a claim — it is
      prose (a row number, a quantity, "10% off"), and asserting nothing about it
      is the honest outcome. Verification must not manufacture contradictions.

    A citation alone proves nothing: anchoring to cell A1 says nothing about the
    number the reply derived, which is exactly the hole this replaces.
    """
    result = DerivationVerification()
    values, formulas, _rows = parse_evidence(tool_block or "")
    if not formulas and not values:
        return result
    ev = _Evaluator(values, formulas)

    def _close(a: float, b: float) -> bool:
        return abs(a - b) <= max(tol, abs(b) * 1e-6)

    _letters: Dict[str, str] = {}
    for _line in (tool_block or "").splitlines():
        if _line.strip().startswith("COLUMNS:") and "=" in _line:
            _, _, _body = _line.partition(":")
            for _part in _body.split("|"):
                if "=" in _part:
                    _n, _, _l = _part.partition("=")
                    _letters[_n.strip()] = _l.strip().upper()
    for claim in extract_claims(reply, _letters):
        cell, figure = claim.cell, claim.claimed
        stored_here = values.get(cell)
        if stored_here is not None and _close(figure, stored_here):
            result.verdicts.append(FigureVerdict(figure, VERIFIED_STORED, cell))
            continue
        if cell in formulas:
            produced = ev.eval_formula(formulas[cell])
            if produced is None:
                result.unresolved_cells.append(cell)
                result.verdicts.append(
                    FigureVerdict(figure, UNRESOLVED, f"{cell}: dependencies unavailable")
                )
                continue
            if _close(figure, produced):
                result.verdicts.append(
                    FigureVerdict(figure, VERIFIED_COMPUTED, f"{cell} = {produced:g}")
                )
            else:
                result.verdicts.append(
                    FigureVerdict(
                        figure, CONTRADICTED,
                        f"{cell} evaluates to {produced:g}, not {figure:g}",
                    )
                )
            continue
        if stored_here is not None:
            result.verdicts.append(
                FigureVerdict(
                    figure, CONTRADICTED,
                    f"{cell} is {stored_here:g} in the evidence, not {figure:g}",
                )
            )
            continue
        # The cell is not in the delivered window at all: we cannot check it.
        result.unresolved_cells.append(cell)
        result.verdicts.append(
            FigureVerdict(figure, UNRESOLVED, f"{cell} not in the delivered evidence")
        )
    return result
