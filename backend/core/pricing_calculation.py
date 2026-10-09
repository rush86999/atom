# -*- coding: utf-8 -*-
"""Taught pricing calculations — deterministic arithmetic over typed,
evidence-backed inputs (round 66).

Separation of concerns (the milestone's core rule): the MODEL may
identify which taught policy applies and propose the calculation; THIS
MODULE validates the inputs and executes the arithmetic in Decimal.
An LLM-generated number is never a calculation result.

Business-neutral by construction: a "policy" is a typed recipe (markup,
margin, depreciation ladder, hourly-rate fee…) with named steps and
parameter bindings — nothing here knows machinery, Brennan, or any
vendor. Policies arrive from teaching/configuration; each carries
provenance (lesson id / config id) and a version string so a result can
name exactly what produced it.

Non-negotiable semantics:
- Missing required parameters (e.g. an exchange rate) leave the result
  UNRESOLVED — never invented, never defaulted.
- Manual overrides are inputs the owner set; they pass through
  unchanged unless the instruction explicitly supersedes them.
- Freshness is a separate dimension: a correct calculation on a stale
  source is correct-but-freshness-limited, not an error.
- Every step is recorded with its exact inputs so the result replays.
"""
from __future__ import annotations

import ast
import copy
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, InvalidOperation, localcontext
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

#: Rounding modes a policy step may name (deterministic by name).
ROUNDING_MODES = {
    "up": ROUND_CEILING,          # ROUNDUP: the taught ladder's rule
    "half_up": ROUND_HALF_UP,     # conventional money rounding
}

#: Currencies the mechanism understands structurally. Adding one is a
#: data change, not a code change; conversion BETWEEN them always
#: requires an explicit, sourced rate.
KNOWN_CURRENCIES = {"CAD", "USD", "EUR", "GBP", "AUD", "INR"}

#: Maximum age (days) of a source value before a result is labeled
#: freshness-limited. OVERRIDABLE per policy (a business may teach a
#: tighter or looser window); this default keeps the dimension honest
#: when no window was taught.
DEFAULT_FRESHNESS_WINDOW_DAYS = 180


class PricingInputError(ValueError):
    """A typed input failed validation — invalid margin, incompatible
    currencies without a rate, unsupported units, malformed amounts.
    The calculation must not proceed on such inputs."""


@dataclass
class Money:
    """A typed monetary amount: Decimal + currency + unit basis."""
    amount: Decimal
    currency: str
    unit: str = "each"  # 'each', 'hour', 'kg', 'lot' … the basis the
                         # price is quoted in — incompatible units are
                         # rejected rather than silently converted.

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            try:
                self.amount = Decimal(str(self.amount))
            except (InvalidOperation, ValueError) as exc:
                raise PricingInputError(
                    f"amount is not numeric: {self.amount!r}") from exc
        self.currency = str(self.currency or "").strip().upper()
        if not self.currency:
            raise PricingInputError("currency is required")
        if self.currency not in KNOWN_CURRENCIES:
            # Not rejected outright: a business may trade in others —
            # but conversion and formatting treat it as opaque.
            pass
        self.unit = str(self.unit or "each").strip().lower() or "each"


@dataclass
class SourceRef:
    """Where an input came from — the result names it, so a reader can
    check the evidence and its age."""
    kind: str            # 'workbook_cell' | 'email' | 'lesson' | 'manual_override' | …
    reference: str       # 'Consolidated Price List 2019.xlsx!Tennsmith!E106'
    observed_at: Optional[str] = None  # ISO date the source was seen
    content_hash: str = ""


@dataclass
class PolicyStep:
    """One typed arithmetic step. `op` names the operation; `params`
    binds its parameters; both are validated at execution."""
    op: str
    params: Dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass
class TaughtPolicy:
    """A typed calculation recipe with provenance and version.

    ``scope`` (round 68) binds applicability: a lesson-derived policy
    may be global, but a WORKBOOK-derived policy is scoped to its
    sheet — 'every sheet has its own formula' is the workbook's own
    structure (live evidence: BurrKing's ladder multiplies by $AB$1 /
    $AB$8 / $AB$11 parameter cells; TennSmith's row uses c24/c26
    factors; the F5216 lesson example was ONE ROW's chain, not the
    business rule). Scope is data (file/sheet), never business
    vocabulary."""
    policy_id: str
    name: str
    steps: List[PolicyStep]
    provenance: str = ""       # 'lesson:...' / 'workbook:FILE!SHEET'
    version: str = "1"
    freshness_window_days: Optional[int] = None
    conditions: List[str] = field(default_factory=list)  # applicability
    scope: Dict[str, str] = field(default_factory=dict)  # file/sheet


@dataclass
class CalculationResult:
    """The full, replayable outcome. `status` in
    {'succeeded','computed_substituted','stored_value','unresolved',
    'rejected','incomplete'} — COMPUTED_SUBSTITUTED (round 72) means
    the output formula was evaluated but intermediate formulas were
    unavailable (stored values stand in): the value is proposed WITH
    that qualification and a fully-reconstructed obligation stays
    open;
    unresolved keeps the missing input named; succeeded-with-stale-source
    carries the limitation; INCOMPLETE (round 69) means the WORKBOOK
    calculation itself could not be reconstructed completely (an
    unsupported operation or an unresolvable dependency cell): the exact
    gap is named in `missing_dependency` and NO partial value is
    published; STORED_VALUE (round 71) means the output cell is an
    established typed literal — the value is an OBSERVATION
    (`verification['stored_value']`), no price is proposed, and it
    cannot satisfy a calculation obligation."""
    status: str
    proposed: Optional[Money] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_reason: str = ""
    rejection_reason: str = ""
    missing_dependency: str = ""
    freshness: str = "unknown"   # 'current' | 'stale' | 'unknown'
    policy_id: str = ""
    policy_version: str = ""
    inputs_snapshot: Dict[str, Any] = field(default_factory=dict)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    #: Workbook-grounded results (round 69): the output's identity and
    #: the version hash of the workbook bytes it was reconstructed from.
    workbook: Dict[str, Any] = field(default_factory=dict)
    #: Every cell the reconstruction touched, role-tagged and ordered —
    #: literal inputs, parameter cells (incl. cross-sheet), intermediates.
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    #: Independent comparisons of the computed value (the workbook's own
    #: cached output, an engine evaluation when bytes were available).
    verification: Dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> Dict[str, Any]:
        rec = {
            "result_id": self.result_id,
            "status": self.status,
            "proposed": (None if self.proposed is None else {
                "amount": str(self.proposed.amount),
                "currency": self.proposed.currency,
                "unit": self.proposed.unit}),
            "steps": self.steps,
            "unresolved_reason": self.unresolved_reason,
            "rejection_reason": self.rejection_reason,
            "freshness": self.freshness,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "inputs": self.inputs_snapshot,
            "computed_at": self.computed_at,
        }
        if self.missing_dependency:
            rec["missing_dependency"] = self.missing_dependency
        if self.workbook:
            rec["workbook"] = self.workbook
        if self.dependencies:
            rec["dependencies"] = self.dependencies
        if self.verification:
            rec["verification"] = self.verification
        return rec


# ---------------------------------------------------------------------------
# Input container + validation
# ---------------------------------------------------------------------------

@dataclass
class PricingInputs:
    """Everything a calculation may consume. Unknown keys are ignored
    (they ride inputs_snapshot for audit), but every key a step READS
    must be present and valid at execution time."""
    base: Money                          # the source value being priced from
    source: SourceRef                    # its provenance
    manual_override: Optional[Money] = None  # owner-set price (protected)
    exchange_rate: Optional[Dict[str, Any]] = None  # {'from','to','rate','source'}
    params: Dict[str, Any] = field(default_factory=dict)  # margin, years, hours, …

    def validate(self) -> None:
        if self.manual_override is not None:
            # An override must be a plausible money value; it does NOT
            # need to relate to the base (the owner may price freely).
            Money(self.manual_override.amount,
                  self.manual_override.currency,
                  self.manual_override.unit)
        if self.exchange_rate is not None:
            rate = self.exchange_rate.get("rate")
            try:
                rate_dec = Decimal(str(rate))
            except (InvalidOperation, TypeError) as exc:
                raise PricingInputError(
                    f"exchange rate is not numeric: {rate!r}") from exc
            if rate_dec <= 0:
                raise PricingInputError(
                    f"exchange rate must be positive: {rate_dec}")
            for key in ("from", "to"):
                if not str(self.exchange_rate.get(key) or "").strip():
                    raise PricingInputError(
                        f"exchange rate missing '{key}' currency")


# ---------------------------------------------------------------------------
# Step executors — pure Decimal arithmetic, each validating its params
# ---------------------------------------------------------------------------

def _d(value: Any, name: str) -> Decimal:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PricingInputError(
            f"parameter '{name}' is not numeric: {value!r}") from exc
    if not dec.is_finite():
        raise PricingInputError(f"parameter '{name}' is not finite")
    return dec


def _resolve_placeholders(params: Dict[str, Any],
                          ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """'{name}' placeholder params resolve from the inputs' bindings
    (ctx). A placeholder with no binding is UNRESOLVED — the caller
    names the missing input; the literal placeholder never executes."""
    resolved: Dict[str, Any] = {}
    missing: List[str] = []
    for k, v in (params or {}).items():
        if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
            key = v[1:-1]
            if key not in ctx or ctx[key] is None:
                missing.append(key)
                continue
            resolved[k] = ctx[key]
        else:
            resolved[k] = v
    if missing:
        # Expose the missing names so the unresolved reason names the
        # actual gap (not the first placeholder alphabetically).
        _resolve_placeholders.last_missing = missing
        return None
    _resolve_placeholders.last_missing = []
    return resolved


def _exec_step(executor, current: Money, params: Dict[str, Any],
                ctx: Dict[str, Any]):
    """Run one executor with placeholder resolution. Returns
    (next_money, unresolved_name_or_None)."""
    bound = _resolve_placeholders(params, ctx)
    if bound is None:
        miss = getattr(_resolve_placeholders, "last_missing", None) or []
        return None, (miss[0] if miss else "input")
    return executor(current, bound, ctx), None


def _op_apply_markup(current: Money, params: Dict[str, Any],
                      ctx: Dict[str, Any]) -> Money:
    """markup: price = base × (1 + pct/100). Applies to the CURRENT
    value so ladders compose."""
    pct = _d(params.get("percent"), "percent")
    if pct < -100:
        raise PricingInputError(f"markup percent below -100: {pct}")
    return Money(current.amount * (Decimal(1) + pct / Decimal(100)),
                 current.currency, current.unit)


def _op_apply_margin(current: Money, params: Dict[str, Any],
                      ctx: Dict[str, Any]) -> Money:
    """gross margin: price = cost / (1 - pct/100) — margin is a share
    OF the price, not an addition to cost."""
    pct = _d(params.get("percent"), "percent")
    if not (Decimal(0) <= pct < Decimal(100)):
        raise PricingInputError(
            f"margin percent must be in [0, 100): {pct}")
    divisor = Decimal(1) - pct / Decimal(100)
    if divisor <= 0:
        raise PricingInputError(f"margin divisor is not positive: {divisor}")
    return Money(current.amount / divisor, current.currency, current.unit)


def _op_convert_currency(current: Money, params: Dict[str, Any],
                         ctx: Dict[str, Any]) -> Money:
    """Explicit, sourced conversion only. The rate comes from the
    inputs' exchange_rate binding (ctx); a missing rate is UNRESOLVED,
    never invented."""
    target = str(params.get("to") or "").strip().upper()
    if not target:
        raise PricingInputError("conversion target currency missing")
    rate_info = ctx.get("exchange_rate")
    if not isinstance(rate_info, dict):
        return None  # unresolved signal — see run_policy
    frm = str(rate_info.get("from") or "").upper()
    to = str(rate_info.get("to") or "").upper()
    if frm != current.currency or to != target:
        return None  # the sourced rate does not cover this leg
    rate = Decimal(str(rate_info.get("rate")))
    return Money(current.amount * rate, target, current.unit)


def _op_add_freight(current: Money, params: Dict[str, Any],
                     ctx: Dict[str, Any]) -> Money:
    """Add a freight amount (same currency). The amount may be a param
    or an evidence-backed binding; never a guess."""
    amt = params.get("amount", ctx.get("freight_amount"))
    if amt is None:
        return None  # unresolved: freight unknown
    return Money(current.amount + _d(amt, "freight"),
                 current.currency, current.unit)


def _op_depreciate(current: Money, params: Dict[str, Any],
                   ctx: Dict[str, Any]) -> Money:
    """Straight-percentage-per-year depreciation of a NEW price to the
    machine's current age (the taught PRIMARY method's arithmetic)."""
    rate = _d(params.get("annual_percent"), "annual_percent")
    years = _d(params.get("years"), "years")
    if not (Decimal(0) <= rate <= Decimal(100)):
        raise PricingInputError(
            f"depreciation percent must be in [0, 100]: {rate}")
    if years < 0:
        raise PricingInputError(f"negative years: {years}")
    factor = (Decimal(1) - rate / Decimal(100)) ** years
    return Money(current.amount * factor, current.currency, current.unit)


def _op_multiply(current: Money, params: Dict[str, Any],
                 ctx: Dict[str, Any]) -> Money:
    """Generic multiply (hourly fee: base=rate per hour × hours; ladder
    multipliers). Param may be a literal or an inputs binding."""
    raw = params.get("factor", ctx.get(params.get("factor_from", "")))
    if raw is None:
        return None  # unresolved
    factor = _d(raw, "factor")
    return Money(current.amount * factor, current.currency, current.unit)


def _op_divide(current: Money, params: Dict[str, Any],
                ctx: Dict[str, Any]) -> Money:
    """An explicitly taught division (e.g. the ladder's '/0.87'):
    exact Decimal division by the taught factor — no margin semantics
    derived, no percent conversion."""
    divisor = _d(params.get("divisor"), "divisor")
    if divisor == 0:
        raise PricingInputError("taught division by zero")
    return Money(current.amount / divisor, current.currency, current.unit)


def _op_round(current: Money, params: Dict[str, Any],
              ctx: Dict[str, Any]) -> Money:
    """Deterministic rounding. mode 'up' = ROUNDUP (the taught ladder),
    'half_up' conventional. places: decimal places (0 = whole dollars)."""
    mode = str(params.get("mode") or "half_up")
    if mode not in ROUNDING_MODES:
        raise PricingInputError(f"unknown rounding mode: {mode!r}")
    places = int(params.get("places", 0))
    if places < 0 or places > 6:
        raise PricingInputError(f"rounding places out of range: {places}")
    quantum = Decimal(1).scaleb(-places)
    return Money(current.amount.quantize(quantum, rounding=ROUNDING_MODES[mode]),
                 current.currency, current.unit)


_STEP_EXECUTORS = {
    "apply_markup": _op_apply_markup,
    "apply_margin": _op_apply_margin,
    "convert_currency": _op_convert_currency,
    "add_freight": _op_add_freight,
    "depreciate": _op_depreciate,
    "multiply": _op_multiply,
    "divide": _op_divide,
    "round": _op_round,
}


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def _freshness_of(source: SourceRef,
                  window_days: Optional[int]) -> str:
    """'current' | 'stale' | 'unknown' — from the source's observed
    date against the policy's (or the default) window. A missing
    observed date is UNKNOWN (the honest label), never fresh."""
    if not source.observed_at:
        return "unknown"
    try:
        seen = date.fromisoformat(str(source.observed_at)[:10])
    except ValueError:
        return "unknown"
    window = int(window_days or DEFAULT_FRESHNESS_WINDOW_DAYS)
    age = (date.today() - seen).days
    return "current" if age <= window else "stale"


def run_policy(policy: TaughtPolicy, inputs: PricingInputs,
               item_label: str = "") -> CalculationResult:
    """Execute a taught policy over typed inputs. Returns the full
    result record — succeeded / unresolved / rejected, with every step
    replayable and freshness judged independently of arithmetic."""
    result = CalculationResult(
        status="succeeded",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        freshness=_freshness_of(inputs.source,
                                policy.freshness_window_days),
        inputs_snapshot={
            "item": item_label,
            "base": {"amount": str(inputs.base.amount),
                      "currency": inputs.base.currency,
                      "unit": inputs.base.unit},
            "source": {"kind": inputs.source.kind,
                       "reference": inputs.source.reference,
                       "observed_at": inputs.source.observed_at,
                       "content_hash": inputs.source.content_hash},
            "manual_override": (None if inputs.manual_override is None else {
                "amount": str(inputs.manual_override.amount),
                "currency": inputs.manual_override.currency,
                "unit": inputs.manual_override.unit}),
            "params": {k: str(v) for k, v in inputs.params.items()},
        },
    )
    # Manual overrides are PROTECTED: they pass through unchanged. The
    # policy still executes (its steps are recorded for comparison),
    # but the PROPOSED value is the override — an override is never
    # recomputed away.
    try:
        inputs.validate()
    except PricingInputError as exc:
        result.status = "rejected"
        result.rejection_reason = str(exc)
        return result

    ctx: Dict[str, Any] = dict(inputs.params or {})
    ctx["exchange_rate"] = inputs.exchange_rate
    current = copy.copy(inputs.base)
    for i, step in enumerate(policy.steps):
        executor = _STEP_EXECUTORS.get(step.op)
        if executor is None:
            result.status = "rejected"
            result.rejection_reason = f"unknown step op: {step.op!r}"
            return result
        before = copy.copy(current)
        missing: Optional[str] = None
        try:
            nxt, missing = _exec_step(executor, current,
                                       step.params, ctx)
        except PricingInputError as exc:
            result.status = "rejected"
            result.rejection_reason = f"step {i + 1} ({step.op}): {exc}"
            return result
        if nxt is None:
            # UNRESOLVED: a required input is missing. Name it; never
            # invent. The executed prefix is preserved for audit.
            result.status = "unresolved"
            result.unresolved_reason = (
                f"step {i + 1} ({step.op}) requires "
                f"'{missing or 'an input'}' which was not provided")
            result.steps.append({
                "step": i + 1, "op": step.op,
                "input_amount": str(before.amount),
                "input_currency": before.currency,
                "status": "unresolved", "note": step.note,
                "missing": missing})
            return result
        current = nxt
        result.steps.append({
            "step": i + 1, "op": step.op,
            "params": {k: str(v) for k, v in step.params.items()},
            "input_amount": str(before.amount),
            "output_amount": str(current.amount),
            "currency": current.currency,
            "status": "ok", "note": step.note})

    if inputs.manual_override is not None:
        result.proposed = copy.copy(inputs.manual_override)
        result.steps.append({
            "step": len(policy.steps) + 1, "op": "manual_override_passthrough",
            "computed_amount": str(current.amount),
            "proposed_amount": str(result.proposed.amount),
            "note": ("owner's manual price preserved; the computed value "
                      "is recorded for comparison only")})
    else:
        result.proposed = current
    return result


# ---------------------------------------------------------------------------
# Comparison rendering (business language, reviewable)
# ---------------------------------------------------------------------------

def render_comparison(item_label: str, draft_price: Optional[Money],
                      result: CalculationResult) -> str:
    """A plain-language, reviewable comparison block: existing price,
    proposal, source and basis, policy and steps, currency/rounding,
    freshness, approval need. Internal diagnostics stay out; the
    qualifications that prevent unsupported commitments stay in."""
    lines: List[str] = [f"**{item_label or 'Item'} — price check**"]
    if draft_price is not None:
        lines.append(f"- Draft price: {draft_price.currency} "
                     f"{draft_price.amount}")
    if result.status == "succeeded" and result.proposed is not None:
        lines.append(f"- Proposed price (computed): "
                     f"{result.proposed.currency} {result.proposed.amount} "
                     f"per {result.proposed.unit}")
    elif result.status == "computed_substituted" \
            and result.proposed is not None:
        lines.append(
            f"- Proposed price (computed WITH SUBSTITUTED OPERANDS — "
            f"NOT fully reconstructed): "
            f"{result.proposed.currency} {result.proposed.amount} "
            f"per {result.proposed.unit}")
    elif result.status == "stored_value":
        wb0 = result.workbook or {}
        lines.append(
            f"- STORED VALUE — NOT COMPUTED: "
            f"{result.verification.get('stored_value')} observed at "
            f"{wb0.get('sheet', '')}!{wb0.get('output_cell', '')} in "
            f"{wb0.get('file', '')} (typed literal; no formula was "
            f"evaluated — this cannot satisfy a calculation "
            f"obligation)")
    elif result.status == "incomplete":
        lines.append(f"- Proposed price: NOT COMPUTED — the workbook "
                     f"calculation is incomplete: "
                     f"{result.missing_dependency or 'a dependency could not be reconstructed'}")
        lines.append("  (No partial result was published; the exact "
                     "dependency is named above.)")
    elif result.status == "unresolved":
        lines.append(f"- Proposed price: NOT COMPUTED — "
                     f"{result.unresolved_reason}")
        lines.append("  (No value was invented for the missing input.)")
    else:
        lines.append(f"- Proposed price: REJECTED — "
                     f"{result.rejection_reason}")
    snap = result.inputs_snapshot
    src = snap.get("source") or {}
    if src.get("reference"):
        seen = (f", seen {src.get('observed_at')}"
                if src.get("observed_at") else ", date unknown")
        lines.append(f"- Source: {src.get('kind')} — "
                     f"{src.get('reference')}{seen}")
    if result.policy_id:
        lines.append(f"- Policy applied: {result.policy_id} "
                     f"(v{result.policy_version})")
    if result.workbook:
        wb = result.workbook
        lines.append(f"- Calculation defined by: {wb.get('file')} — "
                     f"{wb.get('sheet')} row {wb.get('row')}, output cell "
                     f"{wb.get('output_cell')}; workbook version "
                     f"{str(wb.get('version') or 'unknown')[:12]}")
        ab = wb.get("authorized_by") or {}
        if ab.get("lesson_id"):
            lines.append(f"- Applicability: authorized by teaching "
                         f"(lesson {ab.get('lesson_id')}, "
                         f"v{ab.get('version')}) — the workbook defines "
                         f"the calculation; the teaching authorizes its "
                         f"use here")
        if result.dependencies:
            lines.append(f"- Dependencies reconstructed: "
                         f"{len(result.dependencies)} cell(s) — literal "
                         f"inputs, parameters and intermediates are "
                         f"recorded with the result")
    v = result.verification or {}
    cs = v.get("cache_substituted_cells") or []
    if cs:
        lines.append(
            "- Limitation: part of the chain was taken from the "
            "workbook's STORED values, not reconstructed arithmetic ("
            + ", ".join(cs[:6]) + ") — a stored value can be stale; a "
            "live read of the workbook can replace it with the real "
            "formula")
    if v.get("cached_output") is not None:
        if v.get("matches_cached"):
            lines.append(f"- Cross-check: matches the workbook's own "
                         f"cached output ({v.get('cached_output')})")
        else:
            lines.append(f"- **Your decision needed**: the computed value "
                         f"differs from the workbook's cached output "
                         f"({v.get('cached_output')}) — a cached value can "
                         f"be stale, so nothing is adopted until you choose")
    if v.get("engine") and v.get("engine_value") is not None:
        if v.get("matches_engine"):
            lines.append(f"- Cross-check: independently re-evaluated with "
                         f"the {v.get('engine')} formula engine "
                         f"({v.get('engine_value')}) — same value")
        else:
            lines.append(f"- **Fidelity failure**: the {v.get('engine')} "
                         f"formula engine evaluates this output to "
                         f"{v.get('engine_value')}, not "
                         f"{v.get('computed')} — the reconstruction is "
                         f"wrong and must not be used")
    if result.steps:
        chain = " → ".join(
            f"{s.get('output_amount', s.get('output', s.get('status')))}"
            for s in result.steps if s.get("op") != "manual_override_passthrough")
        if chain:
            lines.append(f"- Calculation steps: {chain}")
    if snap.get("manual_override"):
        lines.append("- Manual price: PRESERVED (owner-set; unchanged)")
    if result.freshness == "stale":
        lines.append("- Limitation: the source value is dated — treat the "
                     "proposal as freshness-limited, not a current-market "
                     "price.")
    elif result.freshness == "unknown":
        lines.append("- Limitation: the source value's date is unknown — "
                     "freshness could not be established.")
    if (result.status == "succeeded" and draft_price is not None
            and result.proposed is not None
            and result.proposed.amount != draft_price.amount):
        lines.append("- **Your decision needed**: the computed price "
                     "differs from the draft price — nothing changes "
                     "until you choose.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Teaching → typed policies (structural grammar; no business nouns here)
# ---------------------------------------------------------------------------

import re as _re


def parse_taught_policies(lessons: List[Dict[str, Any]],
                          ) -> List[TaughtPolicy]:
    """Derive typed policies from natural-language teaching.

    INTEGRITY RULES (round 67, reviewer corrections 2 and 3):
    - EXPLICIT TAUGHT RULES ONLY. A recipe step exists because the
      lesson states it — a number with its operation and, where the
      operation needs one, its rounding. Mentions do not become
      recipes: a lesson that says "depreciate the new price" without a
      percent, method or rounding yields an UNRESOLVED applicability
      note (conditions with no steps), never an invented ladder.
    - DECIMAL LITERALS throughout: taught numbers become Decimal by
      string, never float; a taught division stays a division factor
      (multiply by its exact Decimal), with no margin-percent
      conversion and no rounding of derived values.
    - STRUCTURAL grammar only: percent-with-operation sentences and
      ordered ladder cues — no business nouns, no per-business
      policies baked in.
    """
    out: List[TaughtPolicy] = []
    for idx, lesson in enumerate(lessons or []):
        text = " ".join(str(lesson.get("lesson")
                             or lesson.get("summary") or "").split())
        if not text:
            continue
        lid = str(lesson.get("id") or lesson.get("lesson_id") or
                  f"idx-{idx}")
        import hashlib as _hl

        _canon = f"{lid}\x1f{text}"
        version = _hl.sha256(_canon.encode("utf-8")).hexdigest()[:12]
        steps, conditions = _taught_steps_from_text(text)
        if not steps:
            continue
        # A recipe with an explicit ROUNDUP/rounding cue in the SAME
        # lesson gets the rounding step; without it, none is added.
        out.append(TaughtPolicy(
            policy_id=_derived_policy_id(steps, text),
            name=f"Taught recipe ({len(steps)} step(s))",
            steps=steps,
            provenance=f"lesson:{lid}",
            version=version,
            conditions=conditions))
    return out


# A taught number: digits with optional decimal part (never parsed via
# float — captured as a string and handed to Decimal directly).
_NUM = r"([0-9]+(?:\.[0-9]+)?)"


def _dec(s: str) -> Decimal:
    return Decimal(s)


def _taught_steps_from_text(
        text: str) -> "tuple[List[PolicyStep], List[str]]":
    """Explicit steps + unresolved conditions from ONE lesson's text."""
    steps: List[PolicyStep] = []
    conditions: List[str] = []
    low = text

    # "markup of 20%" / "20 percent markup" — explicit markup.
    for m in _re.finditer(
            rf"markup[^.{{}}]{{0,30}}?{_NUM}\s*(?:%|percent)",
            low, _re.IGNORECASE):
        steps.append(PolicyStep(
            "apply_markup", {"percent": m.group(1)},
            note="taught markup"))
    if not steps:
        for m in _re.finditer(
                rf"{_NUM}\s*(?:%|percent)\s+markup",
                low, _re.IGNORECASE):
            steps.append(PolicyStep(
                "apply_markup", {"percent": m.group(1)},
                note="taught markup"))

    # "gross margin of 20%" / "20% gross margin" — explicit margin.
    for m in _re.finditer(
            rf"(?:gross\s+)?margin[^.{{}}]{{0,30}}?{_NUM}\s*(?:%|percent)",
            low, _re.IGNORECASE):
        steps.append(PolicyStep(
            "apply_margin", {"percent": m.group(1)},
            note="taught gross margin"))
    if not any(s.op == "apply_margin" for s in steps):
        for m in _re.finditer(
                rf"{_NUM}\s*(?:%|percent)\s+(?:gross\s+)?margin",
                low, _re.IGNORECASE):
            steps.append(PolicyStep(
                "apply_margin", {"percent": m.group(1)},
                note="taught gross margin"))

    # Ordered ladder cues: "(F235*0.9)" multiply, "(H235+700)" add,
    # "(K235/0.87)" divide — EXACT operations with EXACT numbers, in
    # text order. A division stays a division (multiply by the exact
    # Decimal reciprocal is avoided; we keep the literal factor as a
    # multiply-by-Decimal only when the cue is a multiplication —
    # divisions become a dedicated step kind below).
    # The cue shapes are 'CELL*NUM', 'CELL+NUM' (usually parenthesized)
    # and 'CELL/NUM' (often NOT parenthesized — '(K235/0.87 and
    # L235/0.86)' closes only after the second). Match the bare
    # CELL-op-NUM core; the surrounding prose is not the contract.
    for m in _re.finditer(
            rf"[A-Z]\d{{1,4}}\s*([*/+])\s*{_NUM}\b",
            low):
        op_ch, num = m.group(1), m.group(2)
        if op_ch == "*":
            steps.append(PolicyStep(
                "multiply", {"factor": num},
                note=f"taught multiply ({m.group(0)})"))
        elif op_ch == "+":
            steps.append(PolicyStep(
                "add_freight", {"amount": num},
                note=f"taught add ({m.group(0)})"))
        elif op_ch == "/":
            steps.append(PolicyStep(
                "divide", {"divisor": num},
                note=f"taught divide ({m.group(0)})"))

    # Rounding: ONLY an explicit ROUNDUP / "round ... to N places" in
    # the lesson — and it executes LAST (rounding terminates the
    # recipe regardless of where the word sits in the sentence).
    if _re.search(r"\bROUNDUP\b", text):
        round_step = PolicyStep(
            "round", {"mode": "up", "places": 0},
            note="taught ROUNDUP")
    else:
        m = _re.search(
            rf"round[^.{{}}]{{0,30}}?to\s+({ _NUM })\s+decimal\s+places",
            text, _re.IGNORECASE)
        if m:
            steps.append(PolicyStep(
                "round", {"mode": "half_up", "places": int(m.group(1))},
                note="taught rounding"))

    # Depreciation WITHOUT taught numbers: an unresolved applicability
    # condition, never an invented recipe.
    if _re.search(r"depreciat", low, _re.IGNORECASE) and not any(
            s.op == "depreciate" for s in steps):
        pct = _re.search(
            rf"depreciat[^.{{}}]{{0,60}}?{_NUM}\s*(?:%|percent)",
            low, _re.IGNORECASE)
        if pct:
            steps.append(PolicyStep(
                "depreciate", {"annual_percent": pct.group(1),
                               "years": "{years}"},
                note="taught percent per year (years bound per item)"))
        else:
            conditions.append(
                "depreciation is taught as the method but no annual "
                "percent is stated — the rate is an unresolved input")
    # Rounding terminates the recipe (appended after all value steps).
    try:
        steps.append(round_step)
    except NameError:
        pass
    return steps, conditions


def _derived_policy_id(steps: List[PolicyStep], text: str) -> str:
    """A stable id from what the recipe IS (its ops), not the business
    it serves. Includes each op's TAUGHT PARAMETER so two recipes with
    the same op names but different factors (live round 67: a
    margin-preamble variant and the bare ladder collided under one id)
    cannot share an identity."""
    parts = []
    for s in steps:
        sig = s.op
        for k in sorted(s.params):
            sig += f".{k}{s.params[k]}"
        parts.append(sig)
    return "taught-" + "-".join(parts)



def record_calculation(
        lifecycle: Any,
        run_id: str,
        item_label: str,
        result: CalculationResult,
        draft_price: Optional[Money] = None,
        *,
        execution_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Persist a calculation as a job operation with its full typed
    record (round 66 §4). The operation's `extra` carries the result
    record (inputs snapshot, steps, policy id + version, freshness) so
    retries and restarts can replay it; the STATUS encodes the
    milestone's distinction — succeeded→applied only means the
    arithmetic ran; unresolved/missing inputs keep the operation
    open and add the specific next action or owner question."""
    if lifecycle is None or not run_id:
        return None
    try:
        # ONE CALCULATION OPERATION PER REQUEST (release case 3, final
        # owner correction 2026-10-06): the lifecycle's own Stripe-style
        # idempotency, keyed on the REQUEST/EXECUTION identity PLUS the
        # calculation's identity — policy, version, status, item, input
        # values, computed value; never the snapshot's prose. The same
        # request dispatched by two arms (different query texts) or
        # retried within the request replays to the SAME operation; a
        # NEW request — even with identical inputs and result — records
        # its OWN separately attributed operation (a content-only key
        # silently reattributed later legitimate requests to an earlier
        # op). Callers without a request identity (tests, legacy paths)
        # fall back to the content-only key.
        import hashlib as _calc_hash
        import json as _calc_json

        _snap = result.inputs_snapshot or {}
        _key_inputs = {str(k): str(v) for k, v in
                       (_snap.get("inputs") or {}).items()}
        # The computed VALUE is part of the identity: policy paths that
        # carry no inputs snapshot still differ by their result (8h×150
        # vs 12h×150 must never collapse into one operation).
        _prop = result.proposed
        _key_value = ("" if _prop is None else
                      f"{_prop.amount}|{_prop.currency}|{_prop.unit}")
        _idem = "calc:" + _calc_hash.sha256("|".join((
            f"exec={execution_id or ''}",
            str(result.policy_id), str(result.policy_version),
            str(result.status), str(_snap.get("item") or item_label),
            _key_value,
            _calc_json.dumps(_key_inputs, sort_keys=True,
                             default=str))).encode()).hexdigest()[:40]
        op = lifecycle.create_operation(
            run_id, op_type="calculate",
            requested_change=(
                f"calculate proposed price for {item_label or 'item'} "
                f"under policy {result.policy_id} "
                f"(v{result.policy_version})"),
            idempotency_key=_idem)
        status_map = {
            "succeeded": "applied",
            # COMPUTED WITH SUBSTITUTIONS (round 72): the arithmetic ran
            # and a value exists, but one or more intermediate formulas
            # were unavailable — the calculation is NOT fully
            # reconstructed and cannot satisfy a fully-reconstructed
            # obligation; the op records as applied WITH the gap kept
            # open as durable next-work below.
            "computed_substituted": "applied",
            "unresolved": "waiting",
            "rejected": "failed",
            # INCOMPLETE (round 69): the workbook calculation itself is
            # missing a dependency or hits an unsupported operation —
            # the operation stays open exactly like an unresolved input,
            # and no partial value was ever proposed.
            "incomplete": "waiting",
            # STORED VALUE (round 71): the output is an observed typed
            # literal, not a computed formula — it CANNOT satisfy the
            # calculation obligation, so the operation stays open with
            # the distinction stated as durable next-work.
            "stored_value": "waiting",
        }
        _final_status = status_map.get(result.status, "failed")
        if (op.get("status") == _final_status
                and op.get("calculation") is not None):
            # A replayed COMPLETED operation is not re-transitioned —
            # the record already stands; the duplicate dispatch replays
            # to this same operation instead of writing a second one.
            return op
        lifecycle.transition_operation(
            run_id, op["operation_id"], "running",
            execution_id=execution_id)
        lifecycle.transition_operation(
            run_id, op["operation_id"], _final_status,
            execution_id=execution_id)
        lifecycle.attach_operation_field(
            run_id, op["operation_id"], "calculation",
            result.to_record())
        if draft_price is not None:
            lifecycle.attach_operation_field(
                run_id, op["operation_id"], "draft_price",
                {"amount": str(draft_price.amount),
                 "currency": draft_price.currency,
                 "unit": draft_price.unit})
        # Unresolved inputs, incomplete reconstructions AND stored-
        # value observations become durable next-work: a research
        # action or a precise owner question — never a silent choice,
        # never a partial published price, and never a stored value
        # mistaken for a satisfied calculation.
        if result.status == "computed_substituted":
            from core.task_lifecycle import add_unresolved_questions

            _sub_cells = ", ".join(
                result.verification.get("cache_substituted_cells", []) or [])
            add_unresolved_questions(lifecycle, run_id, [{
                "item": item_label,
                "kind": "verification",
                "question": (
                    f"the calculation for {item_label} is computed but "
                    f"NOT fully reconstructed: intermediate formula(s) "
                    f"{_sub_cells} were "
                    f"unavailable and their stored values stand in"),
                "evidence": (
                    f"policy {result.policy_id} v{result.policy_version}; "
                    "computed_substituted — a fully-reconstructed "
                    "obligation is not satisfied"),
                "next_action": (
                    "a live read of the workbook can restore the "
                    "missing formulas and complete the reconstruction"),
            }], source_operation=op["operation_id"])
        if result.status == "stored_value":
            from core.task_lifecycle import add_unresolved_questions

            add_unresolved_questions(lifecycle, run_id, [{
                "item": item_label,
                "kind": "verification",
                "question": (
                    f"the requested calculation for {item_label} cannot "
                    f"be satisfied: the output cell holds a STORED "
                    f"VALUE ({result.verification.get('stored_value')}), "
                    f"not a computed formula"),
                "evidence": (
                    f"policy {result.policy_id} v{result.policy_version}; "
                    "stored value observed, not computed"),
                "next_action": (
                    "provide a formula-bearing output cell, or "
                    "explicitly authorize the stored value as the "
                    "price"),
            }], source_operation=op["operation_id"])
        if result.status in ("unresolved", "incomplete"):
            from core.task_lifecycle import add_unresolved_questions

            gap = (result.missing_dependency or result.unresolved_reason)
            add_unresolved_questions(lifecycle, run_id, [{
                "item": item_label,
                "kind": "verification",
                "question": (
                    f"the price calculation for {item_label} cannot "
                    f"complete: {gap}"),
                "evidence": (
                    f"policy {result.policy_id} v{result.policy_version}; "
                    "no value invented, no partial price published"),
                "next_action": (
                    f"provide or research the missing dependency "
                    f"({gap})"),
            }], source_operation=op["operation_id"])
        # A computed price differing from the draft is a business
        # decision, created only when the arithmetic succeeded.
        if (result.status == "succeeded" and draft_price is not None
                and result.proposed is not None
                and result.proposed.amount != draft_price.amount):
            from core.task_lifecycle import add_unresolved_questions

            _src_ref = (result.inputs_snapshot.get("source", {}) or {}).get(
                "reference", "")
            add_unresolved_questions(lifecycle, run_id, [{
                "item": item_label,
                "kind": "business_decision",
                "question": (
                    f"computed price {result.proposed.currency} "
                    f"{result.proposed.amount} differs from the draft's "
                    f"{draft_price.currency} {draft_price.amount} for "
                    f"{item_label}"),
                "evidence": (
                    f"policy {result.policy_id} v{result.policy_version}; "
                    f"source {_src_ref}"),
                "next_action": (
                    "owner chooses: keep the draft price or adopt the "
                    "computed one"),
            }], source_operation=op["operation_id"])
        return op
    except Exception as exc:  # noqa: BLE001 — recording is best-effort
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "calculation recording skipped: %r", exc)
        return None


# ---------------------------------------------------------------------------
# The agent-facing entry: a typed query string -> grounded result block
# ---------------------------------------------------------------------------

_QUERY_PATTERNS = [
    # calculate <policy> from <amount> <currency> [k=v ...]
    # The amount accepts thousands separators ("7,627") — stripped
    # before Decimal (live price4: the model's comma-formatted number
    # failed the pattern and the honest "no returned result" followed).
    _re.compile(
        r"calculate\s+(?P<policy>[a-z0-9_-]+)\s+from\s+"
        r"(?P<amount>[0-9][0-9,]*(?:\.[0-9]+)?)\s+"
        r"(?P<currency>[A-Za-z]{3})"
        r"(?P<rest>.*)$", _re.IGNORECASE),
]


async def calculate_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str]) -> Optional[str]:
    """The planner lane's entry (round 67): parse the typed query,
    load the taught policies for the workspace's agents, select the
    named one, run it, and return a grounded LIVE TOOL RESULTS block
    with the full comparison. Unknown policy / missing bindings are
    honest outcomes, never fabricated values."""
    q = " ".join(str(query or "").split())
    if not q:
        return None
    m = None
    for pat in _QUERY_PATTERNS:
        m = pat.match(q)
        if m:
            break
    if m is None:
        return None
    from core.database import get_db_session
    from core.student_learning_service import _permanent_lessons
    from core.models import AgentRegistry

    # Load every workspace agent's taught policies (sibling-sharing is
    # the established design), then select by the queried id.
    policies = []
    with get_db_session() as db:
        ids = [str(r.id) for r in db.query(AgentRegistry.id)
               .filter(AgentRegistry.status != "retired").limit(10)]
        for aid in ids:
            for lesson in _permanent_lessons(db, aid):
                lesson.setdefault("id", aid)
                policies.extend(parse_taught_policies([lesson]))
    wanted = m.group("policy").strip().lower()
    selected = next(
        (p for p in policies
         if p.policy_id.lower() == wanted), None)
    if selected is None:
        return (
            "LIVE TOOL RESULTS (datasets.calculate) — UNKNOWN POLICY "
            f"'{m.group('policy')}': no taught recipe with that id "
            f"(available: {', '.join(sorted({p.policy_id for p in policies})) or 'none'}). "
            "Do not compute a price by hand; state which policy should "
            "apply and ask for the teaching if it is missing.")

    # params from the rest: k=v tokens; source=/override= named.
    params: Dict[str, str] = {}
    source_ref = None
    override = None
    for tok in (m.group("rest") or "").split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        k = k.strip().lower()
        if k == "source":
            source_ref = SourceRef(kind="named", reference=v)
        elif k == "override":
            override = Money(Decimal(v), m.group("currency").upper())
        else:
            params[k] = v
    inputs = PricingInputs(
        base=Money(Decimal(m.group("amount").replace(",", "")),
                   m.group("currency").upper()),
        source=source_ref or SourceRef(
            kind="query", reference="agent-provided"),
        manual_override=override,
        params=params)
    result = run_policy(selected, inputs)
    body = render_comparison("Requested calculation", None, result)
    return _grounded(body)


#: Structured calculation registry (round 76): result_id -> envelope.
#: The registry is LOOKUP ONLY — it is never narration authority on its
#: own. Narration authority comes ONLY from the current request's
#: evidence: the result_id(s) embedded in THIS turn's tool block (or an
#: explicit records list passed by the caller). Cross-conversation or
#: cross-operation reuse by recency is refused.
_LAST_CALC_RECORDS: Dict[str, Dict[str, Any]] = {}

#: Machine-readable result marker embedded in every grounded calculate
#: block so validation can bind to THIS operation's record(s).
_CALC_RESULT_ID_RE = _re.compile(
    r"\[calc:result_id=([0-9a-fA-F-]{8,36})\]")


def _calc_operation_key(
        user_id: Optional[str],
        conversation_id: Optional[str],
        canvas_id: Optional[str],
        query: Optional[str]) -> str:
    """Stable operation identity for dedup + evidence binding.

    Uses sha256 (never Python hash(): salted per process) over validated
    context + normalized query. Different users/conversations/canvases
    never share; a changed ask is a different key."""
    import hashlib as _hl

    def _clean(v: Optional[str]) -> str:
        return " ".join(str(v or "").strip().split())[:200].lower()

    q = " ".join(str(query or "").strip().split())[:400].lower()
    raw = "|".join([
        _clean(user_id), _clean(conversation_id),
        _clean(canvas_id), q])
    return _hl.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _publish_calc_record(
        result: "CalculationResult",
        *,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        query: Optional[str] = None,
        operation_key: Optional[str] = None,
        persisted: Optional[bool] = None) -> str:
    """Register the structured record with its request identity.

    ``persisted`` carries the DURABLE outcome of the same request's
    ``_record_on_job`` call (None = recording not attempted, e.g. a
    no-input turn). It rides the record env so narration validation can
    refuse "saved/recorded" claims when the job write failed — release
    case 3: a persistence failure must never read as durable completion.

    Returns the operation key. Bounded (newest 64); publishing never
    raises and never confers authority — authority requires the caller
    to reference these result_id(s) from the current tool block."""
    try:
        op = (operation_key or _calc_operation_key(
            user_id, conversation_id, canvas_id, query))
        _LAST_CALC_RECORDS[result.result_id] = {
            "record": result.to_record(),
            "user_id": str(user_id or "").strip(),
            "conversation_id": str(conversation_id or "").strip(),
            "canvas_id": str(canvas_id or "").strip(),
            "query": str(query or "")[:400],
            "operation_key": op,
            "persisted": persisted,
        }
        while len(_LAST_CALC_RECORDS) > 64:
            _LAST_CALC_RECORDS.pop(next(iter(_LAST_CALC_RECORDS)))
        return op
    except Exception:  # noqa: BLE001 — publishing is additive
        return operation_key or ""


def _calc_records_for_tool_block(
        tool_block: Optional[str],
        *,
        expected_conversation_id: Optional[str] = None,
        expected_user_id: Optional[str] = None) -> Tuple[
            List[Dict[str, Any]], Optional[bool]]:
    """The CURRENT request's records: only result_id(s) referenced by
    THIS tool block. Identity-filtered when the caller supplies the
    expected conversation/user — a record from another context never
    qualifies, even if its id was copied across.

    Also returns the records' durable `persisted` outcome (False when
    ANY of this request's records failed its job write; None when
    recording was not attempted or the env predates the field)."""
    if not tool_block:
        return [], None
    try:
        ids = _CALC_RESULT_ID_RE.findall(str(tool_block))
    except Exception:  # noqa: BLE001
        return [], None
    out: List[Dict[str, Any]] = []
    persisted: Optional[bool] = None
    seen = set()
    for rid in ids:
        if rid in seen:
            continue
        seen.add(rid)
        env = _LAST_CALC_RECORDS.get(rid)
        if not isinstance(env, dict):
            continue
        rec = env.get("record")
        if not isinstance(rec, dict):
            # Back-compat: very old entries stored the record directly.
            rec = env if "proposed" in env else None
            if rec is None:
                continue
            env = {"record": rec}
        if expected_conversation_id:
            exp_c = str(expected_conversation_id).strip()
            got_c = str((env.get("conversation_id") or "")).strip()
            if got_c and got_c != exp_c:
                continue
        if expected_user_id:
            exp_u = str(expected_user_id).strip()
            got_u = str((env.get("user_id") or "")).strip()
            if got_u and got_u != exp_u:
                continue
        if env.get("persisted") is False:
            persisted = False
        out.append(rec)
    return out, persisted


def _calc_narration_allowance(
        tool_block: Optional[str] = None,
        records: Optional[List[Dict[str, Any]]] = None,
        *,
        expected_conversation_id: Optional[str] = None,
        expected_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Structured authority for the CURRENT narration.

    Built ONLY from the current request's records (explicit list, or
    result_id(s) parsed from the current tool block). No-arg / empty
    calls return {} — process-global recency is never authority, so a
    later reply cannot inherit unrelated evidence.
    """
    import itertools  # noqa: F401 — kept for call-site compat

    recs: List[Dict[str, Any]] = []
    persisted: Optional[bool] = None
    if records is not None:
        recs = [r for r in records if isinstance(r, dict)]
    elif tool_block:
        recs, persisted = _calc_records_for_tool_block(
            tool_block,
            expected_conversation_id=expected_conversation_id,
            expected_user_id=expected_user_id)
    else:
        return {}
    if not recs:
        return {}

    def _norm_num(s: Any) -> str:
        t = str(s).replace(",", "")
        if "." in t:
            t = t.rstrip("0").rstrip(".")
            if t in ("", "-"):
                t = "0"
        return t

    outputs: List[Dict[str, str]] = []
    input_norms: List[str] = []
    step_norms: List[str] = []
    allowed: List[str] = []
    currency: Optional[str] = None
    unit: Optional[str] = None
    status: Optional[str] = None
    for rec in recs:
        proposed = rec.get("proposed") or {}
        if proposed.get("amount") is not None:
            amt = str(proposed["amount"])
            allowed.append(amt)
            outputs.append({
                "amount": amt,
                "amount_norm": _norm_num(amt),
                "currency": str(proposed.get("currency") or ""),
                "unit": str(proposed.get("unit") or ""),
            })
            currency = proposed.get("currency") or currency
            unit = proposed.get("unit") or unit
        status = rec.get("status") or status
        for dep in rec.get("dependencies") or []:
            if isinstance(dep, dict) and dep.get("value") is not None:
                v = str(dep["value"])
                allowed.append(v)
                input_norms.append(_norm_num(v))
        inp = rec.get("inputs") or {}
        if isinstance(inp, dict):
            for v in inp.get("inputs", {}).values() if isinstance(
                    inp.get("inputs"), dict) else []:
                try:
                    _norm_num(v)
                    allowed.append(str(v))
                    input_norms.append(_norm_num(v))
                except Exception:  # noqa: BLE001
                    pass
        for step in rec.get("steps") or []:
            if not isinstance(step, dict):
                continue
            out = step.get("output_amount", step.get("output"))
            if out is not None:
                allowed.append(str(out))
                step_norms.append(_norm_num(out))
    limitations: List[str] = []
    for rec in recs:
        v = rec.get("verification") or {}
        if v.get("matches_cached") is False:
            limitations.append(
                "the computed value differs from the workbook's own "
                f"cached output ({v.get('cached_output')})")
        if rec.get("freshness") in ("stale", "unknown"):
            limitations.append(
                "the source date is unknown — freshness could not be "
                "established")
    if persisted is False:
        limitations.append(
            "the job-ledger write FAILED — this result is computed but "
            "NOT recorded; never present it as saved, logged, or durable")
    return {"allowed_figures": allowed, "currency": currency,
            "unit": unit, "status": status, "records": recs,
            "limitations": limitations,
            "persisted": persisted,
            "outputs": outputs,
            "input_amounts_norm": sorted(set(input_norms)),
            "step_outputs_norm": sorted(set(step_norms))}


def _persistence_note(recorded: Optional[bool]) -> str:
    """The durable-recording honesty line for a calculate block.

    Empty when the job write succeeded (or was not attempted — a
    no-input turn publishes nothing to persist). When it FAILED, the
    block must say so in the same breath as the result: the narration
    reads this block, so a silent failure would let the reply present a
    computed figure as recorded/saved (release case 3: "persistence
    failure cannot be presented as durable completion")."""
    if recorded is not False:
        return ""
    return ("- RECORDING FAILED: this result could NOT be persisted to "
            "the job ledger. State the computed value, but NEVER call it "
            "recorded, saved, logged, or durable — say the recording "
            "failed instead.")


def _grounded(body: str, result_id: Optional[str] = None) -> str:
    try:
        from core.chat_tool_planner import _with_grounding

        block = ("LIVE TOOL RESULTS (datasets.calculate — deterministic "
                 "Decimal arithmetic; the model did not compute this):\n"
                 + body)
        if result_id:
            block += f"\n[calc:result_id={result_id}]"
        return _with_grounding(block)
    except Exception:  # noqa: BLE001 — grounding is additive
        block = ("LIVE TOOL RESULTS (datasets.calculate):\n" + body)
        if result_id:
            block += f"\n[calc:result_id={result_id}]"
        return block


# ---------------------------------------------------------------------------
# Workbook-grounded pricing (rounds 69-70): the APPLICATION layer over
# the general formula engine
# ---------------------------------------------------------------------------
#
# core.formula_engine parses, validates and evaluates the supported
# formula language — references, named inputs, functions, Decimal
# precision, rounding — with NO business concepts. THIS module is the
# pricing application on top of it:
#   * TEACHING authorizes WHEN a workbook calculation applies (a
#     formula's existence never makes it the approved pricing policy);
#   * the result carries money, freshness and full provenance
#     (workbook version, sheet, row, output cell, every dependency);
#   * the lane wires the agent's request to the engine, completes
#     unresolvable references with ONE bounded live read when the
#     source is downloadable, and cross-checks the value against the
#     workbook's stored output and the independent `formulas` engine;
#   * INCOMPLETE calculations name the exact missing dependency and
#     publish NO price — a partial answer is never presented as
#     complete.


def workbook_calculation_result(
        calc: "FormulaResult",
        *,
        currency: str = "CAD",
        observed_at: Optional[str] = None,
        item_label: str = "",
        authorized_by: Optional[Dict[str, str]] = None,
        freshness_window_days: Optional[int] = None,
        live_read_cells: Optional[List[str]] = None) -> CalculationResult:
    """Adapt an engine FormulaResult into the pricing record. INCOMPLETE
    calculations carry NO proposed value — the blocking rule — and name
    the exact missing dependency."""
    from core.formula_engine import FormulaResult  # noqa: F401 — type

    origin = calc.origin or {}
    wb_meta = {
        "file": origin.get("file", ""),
        "sheet": origin.get("sheet", ""),
        "row": origin.get("row"),
        "output_cell": origin.get("output_cell", ""),
        "version": origin.get("version", ""),
        "authorized_by": authorized_by,
        "live_read_cells": live_read_cells or [],
    }
    result = CalculationResult(
        status={"computed": "succeeded",
                "computed_substituted": "computed_substituted",
                "stored_value": "stored_value",
                "incomplete": "incomplete"}.get(calc.status, "incomplete"),
        policy_id=f"workbook:{origin.get('sheet', '').strip()}!" \
                  f"{origin.get('output_cell', '')}",
        policy_version=(origin.get("version", "")[:12] or "unknown"),
        freshness=_freshness_of(
            SourceRef(kind="workbook_cell",
                      reference=(f"{origin.get('file', '')}!"
                                 f"{origin.get('sheet', '').strip()}!"
                                 f"{origin.get('output_cell', '')}"),
                      observed_at=observed_at),
            freshness_window_days),
        workbook=wb_meta,
        dependencies=[d.to_dict() for d in calc.dependencies],
        inputs_snapshot={
            "item": item_label,
            "basis": ("the source's own formula chain, evaluated by the "
                      "general formula engine (core.formula_engine); "
                      "constants preserved as decimals"),
            "currency": currency,
        })
    if calc.status == "stored_value":
        # A STORED VALUE IS AN OBSERVATION, NOT A CALCULATION: no
        # proposed price is published, and the stored value is never
        # cross-checked against itself as if that were verification.
        result.verification["stored_value"] = str(calc.value)
        result.verification["stored_value_note"] = (
            "typed literal — stored value, observed, NOT computed; "
            "it cannot satisfy a calculation obligation")
        return result
    if calc.status not in ("computed", "computed_substituted"):
        result.missing_dependency = (
            calc.missing or calc.unsupported or
            "the calculation could not be evaluated completely")
        return result
    result.proposed = Money(calc.value, currency)
    result.steps = list(calc.steps)
    if calc.cache_substituted:
        result.verification["cache_substituted_cells"] = \
            list(calc.cache_substituted)
    if calc.cached_value is not None:
        try:
            cached_dec = Decimal(
                str(calc.cached_value).replace(",", ""))
            matches = abs(cached_dec - calc.value) <= Decimal("0.01")
            result.verification["cached_output"] = str(calc.cached_value)
            result.verification["matches_cached"] = bool(matches)
            # VERIFICATION INDEPENDENCE (round 71): a cross-check
            # against the workbook's own stored output is independent
            # only when no operand was itself substituted from a
            # stored value.
            result.verification["fully_independent"] = \
                not calc.cache_substituted
        except (InvalidOperation, ValueError):
            result.verification["cached_output"] = str(calc.cached_value)
            result.verification["matches_cached"] = None
    return result


# ---------------------------------------------------------------------------
# Teaching authorizes WHEN a workbook calculation applies
# ---------------------------------------------------------------------------

def _norm_token_text(s: Any) -> str:
    return " ".join(_re.split(r"[\s_\-]+", str(s or "").lower())).strip()


def authorized_workbook_basis(
        lessons: List[Dict[str, Any]],
        file_name: str,
        sheet_name: str) -> Optional[Dict[str, str]]:
    """The governance gate (round 69): the workbook DEFINES a
    calculation; TEACHING authorizes when that calculation applies. A
    formula's existence never makes it the approved pricing policy.

    A lesson authorizes FILE!SHEET when its text names the workbook
    (basename with or without extension, whitespace/underscore-
    insensitive) AND the sheet name as its own token. Structural
    matching only — no business vocabulary here. Returns the
    authorizing lesson {'lesson_id','version'} or None."""
    import os as _os

    base = _os.path.basename(str(file_name or "").strip())
    stem = _norm_token_text(_os.path.splitext(base)[0])
    sheet_tok = _norm_token_text(sheet_name)
    if not stem or not sheet_tok:
        return None
    for idx, lesson in enumerate(lessons or []):
        text = _norm_token_text(
            " ".join(str(lesson.get("lesson") or lesson.get("summary")
                         or "").split()))
        if not text:
            continue
        if stem not in text:
            continue
        if not _re.search(
                rf"(?<![a-z0-9]){_re.escape(sheet_tok)}(?![a-z0-9])",
                text):
            continue
        lid = str(lesson.get("id") or lesson.get("lesson_id")
                  or f"idx-{idx}")
        import hashlib as _hl

        digest = _hl.sha256(
            f"{lid}\x1f{text}".encode("utf-8")).hexdigest()[:12]
        return {"lesson_id": lid, "version": digest}
    return None


# ---------------------------------------------------------------------------
# The agent-facing workbook lane (rounds 69-70)
# ---------------------------------------------------------------------------

_WB_QUERY_RE = _re.compile(
    r"calculate\s+(?:price\s+(?:for|of)\s+)?"
    r"(?P<file>.+?\.xlsx)\s+"
    r"(?P<sheet>.+?)\s+row\s+(?P<row>\d+)\s+cell\s+"
    r"(?P<cell>[A-Za-z]{1,3}\d+)"
    r"(?P<rest>.*)$", _re.IGNORECASE)


def _workspace_lessons(user_id: Optional[str],
                       workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """Every workspace agent's permanent lessons (sibling-sharing is
    the established design) — the teaching layer the lane reads."""
    from core.database import get_db_session
    from core.student_learning_service import _permanent_lessons
    from core.models import AgentRegistry

    lessons: List[Dict[str, Any]] = []
    with get_db_session() as db:
        ids = [str(r.id) for r in db.query(AgentRegistry.id)
               .filter(AgentRegistry.status != "retired").limit(10)]
        for aid in ids:
            for lesson in _permanent_lessons(db, aid):
                lesson.setdefault("id", aid)
                lessons.append(lesson)
    return lessons


class _FileSheetBooks:
    """Lazy per-sheet reference sources for one cataloged file,
    preferring the SAME workbook version (content hash) as the target
    sheet — cross-sheet references resolve within one workbook, never
    across versions."""

    def __init__(self, file_name: str, workspace_id: Optional[str],
                 prefer_hash: str):
        self.file_name = file_name
        self.workspace_id = workspace_id
        self.prefer_hash = prefer_hash
        self._books: Dict[str, "CellBook"] = {}
        self._entries: Optional[List[Dict[str, Any]]] = None
        self.resolution_problems: Dict[str, str] = {}
        #: True when the live download's hash DIVERGED from the
        # cataloged version: every book then comes from the LIVE grid
        # alone (round 72 — one coherent version or an explicit
        # conflict, never frame/live mixing).
        self.live_only = False
        #: Sheets a DIVERGENT live version no longer carries — the lane
        # turns these into an explicit VERSION CONFLICT.
        self.live_missing_sheets: set = set()
        #: A live workbook grid (workbook_grid_from_bytes) applied to
        #: every book AS IT IS BUILT — order-independent, so a sibling
        #: sheet first touched DURING a re-evaluation still receives the
        #: live values (its frame cannot supply cells above the header
        #: region).
        self.live_grid: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None

    def _load_entries(self) -> List[Dict[str, Any]]:
        if self._entries is not None:
            return self._entries
        from core.database import get_db_session
        from core.models import DatasetEntry

        # VERSION PINNING (round 71, the owner's contract): every
        # sheet of one workbook must resolve to the SAME identified
        # workbook version. Ambiguous resolution (several active
        # versions of one sheet, none matching the pinned version) is
        # REJECTED and reported — never chosen by name or query order.
        by_sheet: Dict[str, List[Dict[str, Any]]] = {}
        with get_db_session() as db:
            q = db.query(DatasetEntry).filter(
                DatasetEntry.file_name == self.file_name,
                DatasetEntry.status == "active")
            if self.workspace_id:
                q = q.filter(DatasetEntry.workspace_id == self.workspace_id)
            for e in q.all():
                key = " ".join(str(e.entity_name or "").lower().split())
                by_sheet.setdefault(key, []).append({
                    "entity_name": str(e.entity_name or ""),
                    "parquet_path": str(e.parquet_path or ""),
                    "content_hash": str(e.content_hash or ""),
                    "source": str(e.source or ""),
                    "external_id": str(e.external_id or ""),
                    "source_modified_at": (
                        e.source_modified_at.isoformat()
                        if e.source_modified_at else None),
                })
        self.resolution_problems: Dict[str, str] = {}
        best: Dict[str, Dict[str, Any]] = {}
        for key, recs in by_sheet.items():
            hashes = sorted({r["content_hash"] for r in recs})
            if len(hashes) > 1:
                if self.prefer_hash and self.prefer_hash in hashes:
                    best[key] = next(
                        r for r in recs
                        if r["content_hash"] == self.prefer_hash)
                else:
                    self.resolution_problems[key] = (
                        f"multiple active workbook versions for sheet "
                        f"'{recs[0]['entity_name']}' "
                        f"({', '.join(h[:12] for h in hashes)}) — "
                        f"refusing to choose by name or query order")
                continue
            best[key] = recs[0]
        self._entries = list(best.values())
        return self._entries

    def entry_for(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        want = " ".join(str(sheet_name or "").lower().split())
        for e in self._load_entries():
            if " ".join(str(e["entity_name"]).lower().split()) == want:
                return e
        return None

    def problem_for(self, sheet_name: str) -> Optional[str]:
        """The ambiguity reason when entry_for returned None for a
        sheet that IS cataloged under several active versions."""
        self._load_entries()
        return self.resolution_problems.get(
            " ".join(str(sheet_name or "").lower().split()))

    def provider(self, sheet_name: str) -> Optional["CellBook"]:
        from core.formula_engine import (CellBook,
                                         sheet_grid_from_parquet)

        key = " ".join(str(sheet_name or "").lower().split())
        if key in self._books:
            return self._books[key]
        entry = self.entry_for(sheet_name)
        if entry is None or not entry.get("parquet_path"):
            return None
        # SAME VERSION ONLY: a cross-sheet reference resolves within
        # the identified workbook version, never across versions.
        if (self.prefer_hash
                and entry.get("content_hash")
                and entry["content_hash"] != self.prefer_hash):
            return None
        if self.live_grid is not None and self.live_only:
            # DIVERGENT LIVE VERSION: siblings come from the LIVE grid
            # alone. A sheet the live workbook no longer carries is
            # recorded for the explicit VERSION CONFLICT the lane
            # reports — the cataloged version must not fill in.
            live = self.live_grid.get(key)
            if not live:
                self.live_missing_sheets.add(
                    str(entry.get("entity_name") or sheet_name))
                return None
            from core.formula_engine import CellBook

            book = CellBook(
                entry["entity_name"], live["formulas"],
                live["values"], source="live_read",
                formula_cells=live.get("formula_cells"))
            self._books[key] = book
            return book
        from core.sheet_dataset_service import load_formulas_for_parquet

        try:
            formulas = load_formulas_for_parquet(entry["parquet_path"])
            values, empty = sheet_grid_from_parquet(entry["parquet_path"])
        except Exception:  # noqa: BLE001 — a broken sibling sheet is a
            # named gap, not a crash
            return None
        book = CellBook(entry["entity_name"], formulas, values, empty)
        if self.live_grid:
            live = self.live_grid.get(key)
            if live:
                book.overlay(
                    live["values"], "live_read",
                    formulas=live["formulas"],
                    formula_cells=live.get("formula_cells"))
        self._books[key] = book
        return book


async def calculate_workbook_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        execution_id: Optional[str] = None) -> Optional[str]:
    """The planner lane's WORKBOOK entry (rounds 69-70):

        calculate price for FILE.xlsx SHEET row N cell XN [currency=CAD] [item=..]

    The agent supplies the output cell (from its dataset search
    result); THIS code authorizes applicability against the workspace
    teaching, evaluates the output through the general formula engine
    (core.formula_engine), completes unresolvable references with ONE
    live read of the source workbook when it is downloadable,
    cross-checks against the workbook's stored output (and, when bytes
    were fetched, against the independent `formulas` engine), and
    returns a grounded block. Incomplete evaluations name the exact
    missing dependency and publish NO price."""
    from core.formula_engine import evaluate_reference

    q = " ".join(str(query or "").split())
    # search, not match: the planner may embed the grammar mid-query
    m = _WB_QUERY_RE.search(q)
    if m is None:
        return None
    file_name = m.group("file").strip()
    sheet_name = m.group("sheet").strip()
    row_number = int(m.group("row"))
    cell = m.group("cell").upper()
    currency = "CAD"
    item_label = ""
    for tok in (m.group("rest") or "").split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if k.strip().lower() in ("currency", "cur"):
            currency = v.strip().upper()[:3] or "CAD"
        elif k.strip().lower() == "item":
            item_label = v.strip()

    books = _FileSheetBooks(file_name, workspace_id, prefer_hash="")
    entry = books.entry_for(sheet_name)
    if entry is None:
        problem = books.problem_for(sheet_name)
        if problem:
            # AMBIGUOUS VERSION (round 71): several active workbook
            # versions — refused, never chosen by name/query order.
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — workbook) — "
                f"AMBIGUOUS WORKBOOK VERSION: {problem}. Name the exact "
                "workbook version (or wait for the catalog to "
                "supersede the older one); no calculation was run.")
        available = [
            str(e["entity_name"]).strip()
            for e in books._load_entries()][:20]  # noqa: SLF001
        return _grounded(
            "LIVE TOOL RESULTS (datasets.calculate — workbook) — SHEET "
            f"NOT FOUND: '{sheet_name}' is not a cataloged sheet of "
            f"{file_name} (cataloged: {', '.join(available) or 'none'}). "
            "Name the sheet exactly as the search result reported it.")
    books.prefer_hash = entry.get("content_hash") or ""

    # GOVERNANCE GATE: teaching authorizes when the workbook's
    # calculation applies — never the formula's mere existence.
    lessons = _workspace_lessons(user_id, workspace_id)
    authorized = authorized_workbook_basis(lessons, file_name, sheet_name)
    if authorized is None:
        return _grounded(
            "LIVE TOOL RESULTS (datasets.calculate — workbook) — NOT "
            f"AUTHORIZED: no permanent teaching authorizes pricing from "
            f"{file_name} ({sheet_name} sheet). The workbook defines a "
            "calculation; teaching authorizes when that calculation "
            "applies — a formula's existence does not make it the "
            "approved pricing policy. State the intended basis and ask "
            "for the teaching if it is missing; do not compute a price "
            "another way.")

    from core.formula_engine import sheet_grid_from_parquet
    from core.sheet_dataset_service import load_formulas_for_parquet

    try:
        formulas = load_formulas_for_parquet(entry["parquet_path"])
        values, empty = sheet_grid_from_parquet(entry["parquet_path"])
    except Exception as exc:  # noqa: BLE001 — named, never silent
        return _grounded(
            "LIVE TOOL RESULTS (datasets.calculate — workbook) — SOURCE "
            f"UNREADABLE: the materialized sheet for {file_name} "
            f"{sheet_name} could not be read ({type(exc).__name__}).")

    from core.formula_engine import CellBook

    target_book = CellBook(entry["entity_name"], formulas, values, empty)

    def _origin() -> Dict[str, str]:
        return {"file": file_name, "sheet": entry["entity_name"],
                "row": str(row_number), "output_cell": cell,
                "version": entry.get("content_hash") or ""}

    calc = evaluate_reference(
        entry["entity_name"], cell, target_book,
        books.provider, row_of_interest=row_number,
        cached_value=values.get(cell), origin=_origin())

    # LIVE-READ COMPLETION (bounded): references above the materialized
    # frame (parameter blocks) AND cells whose formulas the sidecar lost
    # (shared-formula dependents, visible as cache substitutions) are
    # filled with ONE download of the source workbook when it is
    # downloadable.
    live_cells: List[str] = []
    if ((calc.missing_references or calc.cache_substituted)
            and str(entry.get("source") or "") == "zoho_workdrive"):
        ext_id = str(entry.get("external_id") or "")
        if ext_id and not ext_id.startswith("sha1:"):
            content = await _download_workbook_bytes(
                user_id, ext_id, workspace_id)
            if content:
                from core.formula_engine import (CellBook,
                                                 workbook_grid_from_bytes)

                live = workbook_grid_from_bytes(content)
                import hashlib as _hl

                live_hash = _hl.sha1(content).hexdigest()
                catalog_hash = entry.get("content_hash") or ""
                same_version = (not catalog_hash
                                or live_hash == catalog_hash)
                # ORDER-INDEPENDENT SAME-VERSION MERGE: the grid rides
                # the books object and every book built from here on
                # (target re-evaluation AND sibling sheets first touched
                # mid-walk) receives it. The TARGET book itself must
                # join the cache first — it was built locally from the
                # frame and is the one book the overlay loop would
                # otherwise miss (live 2026-10-05).
                books.live_grid = live
                target_key = " ".join(sheet_name.lower().split())
                if same_version:
                    books.live_only = False
                    books._books.setdefault(  # noqa: SLF001
                        target_key, target_book)
                    for key, book in list(  # noqa: SLF001
                            books._books.items()):
                        if key in live:
                            book.overlay(
                                live[key]["values"], "live_read",
                                formulas=live[key]["formulas"],
                                formula_cells=live[key].get(
                                    "formula_cells"))
                else:
                    # ONE COHERENT VERSION OR AN EXPLICIT CONFLICT
                    # (round 72): the live bytes are a DIFFERENT
                    # workbook version — the cataloged frame/sidecar
                    # must contribute NOTHING. The entire dependency
                    # graph is rebuilt from the live grid alone; a
                    # sheet the live version no longer carries is a
                    # version conflict, refused, never filled from the
                    # older cataloged version.
                    books.live_only = True
                    live_target = live.get(target_key)
                    if not live_target:
                        return _grounded(
                            "LIVE TOOL RESULTS (datasets.calculate — "
                            "workbook) — VERSION CONFLICT: the live "
                            f"workbook (version {live_hash[:12]}) "
                            "differs from the cataloged version "
                            f"({catalog_hash[:12]}) and does not carry "
                            f"sheet '{sheet_name}' — mixing versions is "
                            "refused; no calculation was run. Re-ingest "
                            "the workbook to catalog the live version.")
                    target_book = CellBook(
                        entry["entity_name"],
                        live_target["formulas"],
                        live_target["values"], source="live_read",
                        formula_cells=live_target.get("formula_cells"))
                    books._books = {target_key: target_book}
                    _live_version_divergence = live_hash
                calc = evaluate_reference(
                    entry["entity_name"], cell, target_book,
                    books.provider, row_of_interest=row_number,
                    cached_value=values.get(cell), origin=_origin())
                if books.live_only and books.live_missing_sheets:
                    # EXPLICIT VERSION CONFLICT (round 72): the live
                    # version lacks a sheet the calculation needs —
                    # refuse rather than mix versions.
                    return _grounded(
                        "LIVE TOOL RESULTS (datasets.calculate — "
                        "workbook) — VERSION CONFLICT: the live "
                        f"workbook (version {live_hash[:12]}) differs "
                        f"from the cataloged version "
                        f"({catalog_hash[:12]}) and does not carry "
                        "sheet(s) "
                        + ", ".join(sorted(books.live_missing_sheets))
                        + " that the calculation depends on — mixing "
                        "versions is refused; no calculation was run. "
                        "Re-ingest the workbook to catalog the live "
                        "version.")
                live_cells = sorted({
                    f"{d.sheet}!{d.cell}"
                    for d in calc.dependencies
                    if d.source == "live_read"})
                # INDEPENDENT ENGINE CHECK while the bytes are in hand
                if calc.status == "complete":
                    import asyncio

                    from core.formula_engine import (
                        verify_with_formulas_engine,
                    )

                    engine_val = await asyncio.wait_for(
                        asyncio.to_thread(
                            verify_with_formulas_engine,
                            content, entry["entity_name"], cell),
                        timeout=90.0)
                    if engine_val is not None:
                        try:
                            ev = Decimal(engine_val.replace(",", ""))
                            matches = abs(
                                ev - (calc.value or Decimal(0))) \
                                <= Decimal("0.01")
                        except (InvalidOperation, ValueError):
                            matches = None
                        if not matches and calc.value is not None:
                            # FIDELITY FAILURE: the reconstruction is
                            # wrong — block the price, name it.
                            from core.formula_engine import FormulaResult

                            calc = FormulaResult(
                                reference=calc.reference,
                                status="incomplete",
                                missing=(
                                    f"fidelity check failed: the "
                                    f"independent formulas engine "
                                    f"evaluates {sheet_name}!{cell} to "
                                    f"{engine_val}, but the "
                                    f"reconstruction produced "
                                    f"{calc.value} — no price is "
                                    f"published from a wrong "
                                    f"reconstruction"),
                                dependencies=calc.dependencies,
                                steps=calc.steps,
                                cached_value=values.get(cell),
                                origin=_origin())
                        else:
                            calc._engine_check = {  # noqa: SLF001
                                "engine": "formulas",
                                "engine_value": engine_val,
                                "matches_engine": bool(matches)}

    if locals().get("_live_version_divergence"):
        result_notes = {
            "live_read_version": _live_version_divergence,
            "cataloged_version": entry.get("content_hash"),
            "note": ("the live workbook bytes differ from the "
                     "cataloged snapshot — the calculation ran on the "
                     "LIVE version; the cataloged one is stale"),
        }
    else:
        result_notes = None
    result = workbook_calculation_result(
        calc, currency=currency,
        observed_at=(datetime.now(timezone.utc).isoformat()
                     if locals().get("_live_version_divergence")
                     else entry.get("source_modified_at")),
        item_label=item_label or f"{sheet_name} row {row_number}",
        authorized_by=authorized,
        live_read_cells=live_cells)
    eng = getattr(calc, "_engine_check", None)  # noqa: SLF001
    if isinstance(eng, dict):
        result.verification.update(eng)
    if result_notes:
        result.verification.update(result_notes)
        result.workbook["live_read_version"] = \
            result_notes["live_read_version"]
    # JOB INTEGRATION (round 71): calculation identity, inputs,
    # dependencies, result type and provenance persist on the
    # conversation's ACTUAL job run — this was required work, not an
    # optional follow-up. Evidence is request-bound: the record is
    # registered with this turn's identity and referenced by result_id
    # in the returned block. The DURABLE outcome rides both the record
    # env and the block: a failed job write can never read as durable
    # completion (release case 3).
    _recorded = _record_on_job(conversation_id, workspace_id,
                               item_label or f"{sheet_name} row {row_number}",
                               result, canvas_id=canvas_id, user_id=user_id,
                               execution_id=execution_id)
    _publish_calc_record(
        result, user_id=user_id,
        conversation_id=conversation_id, canvas_id=canvas_id,
        query=query, persisted=_recorded)
    body = render_comparison(
        item_label or f"{sheet_name} row {row_number}", None, result)
    body += _persistence_note(_recorded)
    label = ("workbook"
             if result.status != "stored_value"
             else "workbook — STORED VALUE, NOT COMPUTED")
    nl = chr(10)
    return _grounded(
        f"LIVE TOOL RESULTS (datasets.calculate — {label}):{nl}" + body,
        result_id=result.result_id)


def _conversation_job(
        conversation_id: Optional[str],
        workspace_id: Optional[str],
        canvas_id: Optional[str] = None,
        item_label: str = "item") -> Tuple[Any, Optional[str]]:
    """Find or create the conversation's ACTIVE job task — the one
    job-identity helper for every durable calculation write (the
    recorded operation AND the pending-input question). Returns
    (lifecycle, run_id) or (None, None); never raises."""
    if not conversation_id and not canvas_id:
        return None, None
    try:
        from integrations.chat_orchestrator import _task_lifecycle_for

        lifecycle = _task_lifecycle_for(None, workspace_id)
        if lifecycle is None:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "calculation job recording failed: no lifecycle "
                "(conversation=%s)", conversation_id)
            return None, None
        task = (lifecycle.find_active_task(conversation_id)
                if conversation_id else None)
        if task is None and canvas_id:
            task = lifecycle.find_active_task_for_canvas(canvas_id)
        if task is None and conversation_id:
            # Fresh canvas-free turn: attach the job now so reload
            # recovers it. create_task binds conversation_id; canvas
            # rides provenance when the turn carries one.
            try:
                created = lifecycle.create_task(
                    conversation_id,
                    f"calculation for {item_label or 'item'}",
                    provenance=(
                        {"canvas_id": str(canvas_id)}
                        if canvas_id else {}),
                )
            except Exception as _create_exc:  # noqa: BLE001
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "calculation job creation failed (conversation=%s): %r",
                    conversation_id, _create_exc)
                return None, None
            return lifecycle, created.get("run_id")
        if not task:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "calculation job recording failed: no task "
                "(conversation=%s canvas=%s)", conversation_id, canvas_id)
            return None, None
        return lifecycle, task["run_id"]
    except Exception as exc:  # noqa: BLE001 — recording is best-effort
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "calculation job lookup failed (conversation=%s): %r",
            conversation_id, exc)
        return None, None


def _record_on_job(
        conversation_id: Optional[str],
        workspace_id: Optional[str],
        item_label: str,
        result: CalculationResult,
        canvas_id: Optional[str] = None,
        user_id: Optional[str] = None,
        execution_id: Optional[str] = None) -> bool:
    """Persist a calculation onto the conversation's job run.

    Canvas-free requests create their job on first calculation (via
    lifecycle.create_task) so a fresh conversation survives reload —
    finding-only would silently drop the work. Failures are observable
    (warning with result_id + conversation) and return False; callers
    never raise. The operation keeps its qualified status throughout
    (stored/substituted stay open, never satisfied)."""
    lifecycle, run_id = _conversation_job(
        conversation_id, workspace_id, canvas_id=canvas_id,
        item_label=item_label)
    if lifecycle is None or not run_id:
        return False
    try:
        # ATTRIBUTION: EXACT-OR-FAIL (owner qualification 2026-10-07):
        # a running operation on the same task does NOT prove this
        # turn's identity when turns overlap. The caller's
        # request/execution identity is the ONLY source; when absent,
        # the attribution check fails explicitly (warning + unattributed
        # record) — never another turn's identity, never inference.
        if not execution_id and conversation_id:
            import logging as _lg
            import traceback as _tb

            import traceback as _tb

            _lg.getLogger(__name__).warning(
                "calculation recorded without exact turn attribution "
                "(conversation=%s result_id=%s) — caller carried no "
                "request/execution identity\n%s",
                conversation_id, getattr(result, "result_id", "?"),
                "".join(_tb.format_stack()[-12:-1]))
            # MISSING IDENTITY RECORDS UNATTRIBUTED with the stack
            # capture above naming the caller (owner correction
            # 2026-10-07: the temporary content-matching guard is
            # REMOVED — request identity comes from the caller, and the
            # caller is now fixed at both completion seams).
        record_calculation(lifecycle, run_id, item_label, result,
                           execution_id=execution_id)
        return True
    except Exception as exc:  # noqa: BLE001 — recording is best-effort
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "calculation job recording failed "
            "(result_id=%s conversation=%s): %r",
            getattr(result, "result_id", "?"), conversation_id, exc)
        return False


# ---------------------------------------------------------------------------
# Conversation-state follow-up (release case 3): the estimate flow asks
# ONE precise question; the owner's bare ANSWER turn ("17.5 hours, no
# materials.") and bare RECALCULATE turn ("Recalculate — 12 hours.")
# must reach the SAME lane deterministically — never depend on the
# planner happening to route them. The pending question is durable job
# state (an unresolved VERIFICATION question carrying the structured
# inputs), so the answer binds even after a restart; the completed
# calculation is the record the recalculate turn rebinds. No wider
# regex, no second recording seam.
# ---------------------------------------------------------------------------

#: Marker carried in a verification question's structured `inputs` that
#: identifies it as THIS lane's pending-input question (distinguishes it
#: from every other verification question on the job).
_PENDING_CALC_MARKER = "pending_calc_inputs"


def _record_pending_calc_inputs(
        conversation_id: Optional[str],
        workspace_id: Optional[str],
        item: str,
        missing: List[str],
        bound: Dict[str, str],
        expr: str,
        policy_version: str,
        canvas_id: Optional[str] = None,
        user_bound: Optional[Dict[str, str]] = None) -> bool:
    """Record the missing-input question as DURABLE job state (no
    calculate operation — the driver contract for the asking turn).

    ``user_bound`` names the inputs the REQUEST itself stated; the rest
    of ``bound`` are taught defaults at ask time. The distinction is
    load-bearing on resume: user-stated values persist, taught defaults
    re-derive from the CURRENT lesson — a changed teaching never
    silently completes a stale calculation.

    Fault-isolated: a question that cannot be recorded degrades the
    follow-up to planner-dependent routing (the pre-fix behavior), it
    never breaks the asking turn itself."""
    lifecycle, run_id = _conversation_job(
        conversation_id, workspace_id, canvas_id=canvas_id,
        item_label=item)
    if lifecycle is None or not run_id:
        return False
    try:
        from core.task_lifecycle import add_unresolved_questions

        add_unresolved_questions(lifecycle, run_id, [{
            "item": item,
            "kind": "verification",
            "question": (
                f"the calculation for {item} is waiting on inputs: "
                f"{', '.join(missing)} (taught formula: {expr})"),
            "evidence": (
                f"policy taught-expression:{item} v{policy_version}; "
                + (", ".join(f"{k}={v}" for k, v in sorted(bound.items()))
                   or "no inputs bound yet")),
            "next_action": (
                "reply with the missing inputs — the calculate lane "
                "completes and records the calculation"),
            "inputs": {
                _PENDING_CALC_MARKER: True,
                "missing": list(missing),
                "bound": dict(bound),
                "user_bound": dict(user_bound or {}),
                "expr": expr,
                "policy_version": policy_version,
            },
        }])
        return True
    except Exception as exc:  # noqa: BLE001 — pending state is additive
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "pending calculation-input question not recorded "
            "(conversation=%s): %r", conversation_id, exc)
        return False


def _open_pending_questions(
        conversation_id: Optional[str],
        workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """The conversation's open pending-input questions, oldest first."""
    if not conversation_id:
        return []
    try:
        from integrations.chat_orchestrator import _task_lifecycle_for

        lifecycle = _task_lifecycle_for(None, workspace_id)
        if lifecycle is None:
            return []
        task = lifecycle.find_active_task(conversation_id)
        if task is None:
            return []
        questions = ((task.get("task_revision") or {}).get("unresolved")
                     or [])
        return [q for q in questions
                if str(q.get("status") or "") == "open"
                and isinstance(q.get("inputs"), dict)
                and q["inputs"].get(_PENDING_CALC_MARKER)
                and q.get("kind") == "verification"]
    except Exception:  # noqa: BLE001 — pending state is additive
        return []


def _pending_calc_question(
        conversation_id: Optional[str],
        workspace_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The conversation's NEWEST open pending-input question, or None."""
    open_qs = _open_pending_questions(conversation_id, workspace_id)
    return open_qs[-1] if open_qs else None


def _last_taught_calc(
        conversation_id: Optional[str],
        workspace_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The conversation's latest APPLIED taught-expression calculation
    record (the state a recalculate turn rebinds), or None."""
    if not conversation_id:
        return None
    try:
        from integrations.chat_orchestrator import _task_lifecycle_for

        lifecycle = _task_lifecycle_for(None, workspace_id)
        if lifecycle is None:
            return None
        task = lifecycle.find_active_task(conversation_id)
        if task is None:
            return None
        for op in reversed(task.get("operations") or []):
            if op.get("operation_type") != "calculate":
                continue
            rec = op.get("calculation") or {}
            if not str(rec.get("policy_id") or "").startswith(
                    "taught-expression:"):
                continue
            if op.get("status") != "applied":
                continue
            return rec
        return None
    except Exception:  # noqa: BLE001 — pending state is additive
        return None


def _calc_followup_dispatch(
        message: str,
        conversation_id: Optional[str],
        workspace_id: Optional[str]) -> bool:
    """Whether THIS turn deterministically belongs to the calculate
    lane as a follow-up of the conversation's OWN recorded calculation
    state (release case 3). Two triggers, both checked against durable
    job state — the resolver re-validates everything:

    * PENDING ANSWER — an open pending-input question exists and the
      message binds at least one of its missing inputs;
    * RECALCULATE — a bare recalculate imperative while the job carries
      an APPLIED taught-expression calculation to rebind over (the
      mechanism's second arm; same imperative shape
      message_requires_calculation already matches — no new shapes).

    SAME-CONVERSATION AMBIGUITY (owner assignment 4): with more than one
    open pending-input question a bare answer cannot be attributed to
    one of them deterministically — do NOT route; the ordinary flow asks
    which calculation the owner is answering."""
    try:
        text = str(message or "")
        if not text:
            return False
        if len(_open_pending_questions(conversation_id, workspace_id)) > 1:
            return False
        question = _pending_calc_question(conversation_id, workspace_id)
        if question is not None:
            inputs = question.get("inputs") or {}
            missing = [str(m) for m in (inputs.get("missing") or [])]
            if missing and _bind_mentioned_inputs(text, missing):
                return True
        if _RECALC_IMPERATIVE_RE.search(text):
            return _last_taught_calc(
                conversation_id, workspace_id) is not None
        return False
    except Exception:  # noqa: BLE001 — additive guard
        return False


async def calculate_followup_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        execution_id: Optional[str] = None) -> Optional[str]:
    """Complete or rebind the conversation's OWN calculation.

    Two triggers, both deterministic on durable state:

    * PENDING ANSWER — an open pending-input question exists and the
      message binds >=1 of its missing inputs: bind over the question's
      bound inputs; complete the calculation (own recorded operation)
      or ask again for exactly what is still missing (no new record).
    * RECALCULATE — a bare recalculate imperative plus an applied
      taught-expression record on the job: bind the message's values
      over the record's inputs; a changed value produces its OWN
      operation (content-derived policy version; nothing changed →
      nothing recomputed).

    Returns None whenever neither trigger holds — explicit estimate
    asks never reach here (earlier lanes answer them)."""
    q = " ".join(str(query or "").split())
    if not q or not conversation_id:
        return None
    lessons = _workspace_lessons(user_id, workspace_id)
    exprs = {e["name"]: e for e in parse_taught_expressions(lessons)}

    # --- trigger A: the answer to a pending-input question ------------
    # SAME-CONVERSATION AMBIGUITY: with several open pendings a bare
    # answer is not attributable — leave it to the ordinary flow.
    if len(_open_pending_questions(conversation_id, workspace_id)) <= 1:
        question = _pending_calc_question(conversation_id, workspace_id)
        if question is not None:
            inputs = question.get("inputs") or {}
            missing = [str(m) for m in (inputs.get("missing") or [])]
            item = str(question.get("item") or "")
            e = exprs.get(item)
            if e is not None and missing:
                answered = _bind_mentioned_inputs(q, missing)
                if answered:
                    # CHANGED TEACHING (owner counterexample): user-stated
                    # values persist across the answer turn, but taught
                    # DEFAULTS re-derive from the CURRENT lesson — resuming
                    # with the ask-time defaults would silently complete a
                    # calculation under teaching that no longer exists (and
                    # would mislabel it with the fresh policy version).
                    user_bound = {k: str(v) for k, v in
                                  (inputs.get("user_bound") or {}).items()}
                    bound = dict(e["defaults"])
                    bound.update(user_bound)
                    bound.update(answered)
                    still_missing = [i for i in e["idents"]
                                     if i not in bound]
                    if still_missing:
                        return _grounded(
                            "LIVE TOOL RESULTS (datasets.calculate — "
                            "natural) — INPUT NEEDED to use the taught "
                            f"formula \"{e['name']}: {e['expr']}\" (lesson "
                            f"{e['lesson_id'][:8]}): "
                            + ", ".join(still_missing)
                            + ". Ask the user for exactly these; do not "
                              "guess.")
                    # DISCLOSURE (owner assignment 5): when a taught
                    # DEFAULT changed between the ask and the answer and
                    # the owner did not state that input, the completion
                    # says so — one identifiable current version, user
                    # inputs preserved, the changed default named.
                    ask_bound = {k: str(v) for k, v in
                                 (inputs.get("bound") or {}).items()}
                    disclosures = [
                        f"taught {k} changed since the estimate was "
                        f"requested: {ask_bound.get(k)} → {v} per hour"
                        if k == "rate" else
                        f"taught {k} changed since the estimate was "
                        f"requested: {ask_bound.get(k)} → {v}"
                        for k, v in sorted(e["defaults"].items())
                        if k not in user_bound and k not in answered
                        and str(ask_bound.get(k)) != str(v)]
                    return _complete_taught_calculation(
                        e, bound, newly_bound=sorted(answered),
                        user_id=user_id, workspace_id=workspace_id,
                        conversation_id=conversation_id, canvas_id=canvas_id,
                        basis="taught expression (lesson "
                              f"{e['lesson_id']}) evaluated by the general "
                              "formula engine; missing inputs answered by "
                              "the owner's reply",
                        disclosures=disclosures,
                        execution_id=execution_id)

    # --- trigger B: a bare recalculate over the last computation ------
    if _RECALC_IMPERATIVE_RE.search(q):
        rec = _last_taught_calc(conversation_id, workspace_id)
        if rec is not None:
            item = str(rec.get("policy_id") or "").split(":", 1)[-1]
            e = exprs.get(item)
            prior = {str(k): str(v) for k, v in
                     ((rec.get("inputs") or {}).get("inputs") or {}).items()}
            if e is not None:
                rebound = _bind_mentioned_inputs(q, e["idents"])
                changed = {k: v for k, v in rebound.items()
                           if prior.get(k) != v}
                if changed:
                    bound = dict(prior)
                    bound.update(rebound)
                    return _complete_taught_calculation(
                        e, bound, newly_bound=sorted(changed),
                        user_id=user_id, workspace_id=workspace_id,
                        conversation_id=conversation_id,
                        canvas_id=canvas_id,
                        basis="taught expression (lesson "
                              f"{e['lesson_id']}) evaluated by the general "
                              "formula engine; recalculated with the "
                              "owner's changed inputs",
                        execution_id=execution_id)
    return None


def _complete_taught_calculation(
        e: Dict[str, Any],
        inputs: Dict[str, str],
        *,
        newly_bound: List[str],
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str],
        canvas_id: Optional[str],
        basis: str,
        disclosures: Optional[List[str]] = None,
        execution_id: Optional[str] = None) -> str:
    """Evaluate the taught expression over the FINAL inputs, record the
    result as its own operation, resolve the pending question, and
    return the grounded block. Shared by both follow-up triggers."""
    from core.formula_engine import evaluate_expression
    from core.task_lifecycle import resolve_unresolved_questions

    calc = evaluate_expression(e["expr"], inputs)
    result = CalculationResult(
        status=("succeeded" if calc.status == "computed"
                else calc.status),
        policy_id=f"taught-expression:{e['name']}",
        policy_version=e.get("version", e["lesson_id"][:12]),
        proposed=(Money(calc.value, "XXX", unit=(calc.unit or "value"))
                  if calc.value is not None else None),
        steps=list(calc.steps),
        missing_dependency=(calc.missing or calc.unsupported or "")
        if calc.status == "incomplete" else "",
        dependencies=[d.to_dict() for d in calc.dependencies],
        inputs_snapshot={
            "item": e["name"],
            "basis": basis,
            "inputs": dict(inputs),
            "request_supplied": sorted(newly_bound),
            "taught_defaults": sorted(
                k for k in e["defaults"] if k in inputs
                and k not in newly_bound),
        })
    _recorded = _record_on_job(conversation_id, workspace_id,
                               e["name"], result,
                               canvas_id=canvas_id, user_id=user_id,
                               execution_id=execution_id)
    _publish_calc_record(
        result, user_id=user_id,
        conversation_id=conversation_id, canvas_id=canvas_id,
        query=" ".join(newly_bound), persisted=_recorded)
    # The pending question this turn answered must not stay open.
    try:
        lifecycle, run_id = _conversation_job(
            conversation_id, workspace_id, canvas_id=canvas_id,
            item_label=e["name"])
        if lifecycle is not None and run_id:
            resolve_unresolved_questions(
                lifecycle, run_id, kinds=("verification",),
                items=(e["name"],),
                resolution=("the owner supplied the missing inputs; "
                            f"the calculation completed ({calc.value}) "
                            "and was recorded as its own operation"))
    except Exception:  # noqa: BLE001 — resolution is additive
        pass
    lines = [f"**{e['name']} — taught formula, engine-computed**",
             f"- Formula (taught): {e['expr']}"]
    if calc.status == "computed":
        lines.append(f"- Value (computed): {calc.value}")
    else:
        lines.append(f"- NOT COMPUTED — "
                     f"{calc.missing or calc.unsupported}")
    lines.append("- Inputs: " + ", ".join(
        f"{k}={v}" + (" [from this reply]" if k in newly_bound
                      else " [previously bound]")
        for k, v in inputs.items()))
    for note in (disclosures or []):
        lines.append(f"- Note: {note} — the calculation uses the "
                      "current teaching")
    if calc.steps:
        lines.append("- Steps: " + " → ".join(
            str(s.get("output")) for s in calc.steps))
    lines.extend(_persistence_note(_recorded).splitlines())
    return _grounded(
        "LIVE TOOL RESULTS (datasets.calculate — natural language; "
        "the model did not compute this):\n" + "\n".join(lines),
        result_id=result.result_id)


async def _download_workbook_bytes(
        user_id: Optional[str], external_id: str,
        workspace_id: Optional[str]) -> Optional[bytes]:
    """One bounded download of the source workbook (the same
    integration the app already reads from). Never fatal."""
    import asyncio

    try:
        from integrations.zoho_workdrive_service import (
            zoho_workdrive_service,
        )

        return await asyncio.wait_for(
            zoho_workdrive_service.download_file(
                user_id, external_id, workspace_id=workspace_id),
            timeout=75.0)
    except Exception:  # noqa: BLE001 — download is best-effort
        return None


# ---------------------------------------------------------------------------
# The named-input entry (round 71): an explicitly provided expression
# evaluated by the SAME engine — no workbook, no money, no business
# vocabulary. The agent supplies the expression (selected from teaching
# or the ask) and the named inputs it gathered; the engine computes or
# names the exact gap.
# ---------------------------------------------------------------------------

_EXPR_QUERY_RE = _re.compile(
    r"calculate\s+expression\s+(?P<expr>.+?)(?:\s+with\s+(?P<rest>.+))?$",
    _re.IGNORECASE)


async def calculate_expression_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        execution_id: Optional[str] = None) -> Optional[str]:
    """The planner lane's NAMED-INPUT entry:

        calculate expression EXPR [with name=value name=value ...]

    Runs core.formula_engine.evaluate_expression — the same engine the
    workbook path uses — and returns a grounded block. Missing inputs
    and unsupported constructs are named precisely; nothing is
    invented."""
    from core.formula_engine import evaluate_expression

    q = " ".join(str(query or "").split())
    m = _EXPR_QUERY_RE.match(q)
    if m is None:
        return None
    expr = (m.group("expr") or "").strip()
    inputs: Dict[str, str] = {}
    units: Dict[str, str] = {}
    for tok in (m.group("rest") or "").split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        k = k.strip()
        if k.endswith("_unit"):
            units[k[:-5]] = v.strip()
        else:
            inputs[k] = v.strip()
    calc = evaluate_expression(expr, inputs, units=units)
    lines = [f"**{expr} — formula engine result**"]
    if calc.status == "computed":
        lines.append(f"- Value (computed): {calc.value}")
    elif calc.status == "incomplete":
        lines.append(f"- NOT COMPUTED — {calc.missing or calc.unsupported}")
        lines.append("  (No partial value was produced.)")
    if calc.unit:
        lines.append(f"- Unit: {calc.unit} (recorded, not interpreted)")
    named = [d for d in calc.dependencies if d.role == "input"]
    if named:
        lines.append("- Inputs: " + ", ".join(
            f"{d.cell}={d.value}" + (f" [{d.unit}]" if d.unit else "")
            for d in named))
    if calc.steps:
        chain = " → ".join(str(s.get("output")) for s in calc.steps)
        lines.append(f"- Steps: {chain}")
    if calc.status == "computed" and not named:
        lines.append("- Note: every operand is a literal — no named "
                     "inputs were bound")
    # JOB INTEGRATION: same durable recording as the workbook path.
    # Unknown currency stays XXX in the record (never invented here);
    # narration must not render $, CAD or USD for it. The durable
    # outcome rides the record env and the block (release case 3).
    result = CalculationResult(
        status=("succeeded" if calc.status == "computed"
                else "incomplete"),
        policy_id=f"expression:{expr[:60]}",
        policy_version="engine-1",
        proposed=(Money(calc.value, "XXX", unit=(calc.unit or "value"))
                  if calc.status == "computed" and calc.value is not None
                  else None),
        steps=list(calc.steps),
        missing_dependency=(calc.missing or calc.unsupported or "")
        if calc.status == "incomplete" else "",
        dependencies=[d.to_dict() for d in calc.dependencies],
        inputs_snapshot={
            "item": expr[:80],
            "basis": "explicitly provided expression, evaluated by the "
                     "general formula engine (core.formula_engine)",
            "inputs": {d.cell: d.value for d in named},
        })
    _recorded = _record_on_job(conversation_id, workspace_id, expr[:60],
                               result, canvas_id=canvas_id,
                               user_id=user_id,
                               execution_id=execution_id)
    _publish_calc_record(
        result, user_id=user_id,
        conversation_id=conversation_id, canvas_id=canvas_id,
        query=query, persisted=_recorded)
    lines.extend(_persistence_note(_recorded).splitlines())
    return _grounded(
        "LIVE TOOL RESULTS (datasets.calculate — formula engine, "
        "named inputs; the model did not compute this):\n"
        + "\n".join(lines),
        result_id=result.result_id)


# ---------------------------------------------------------------------------
# Natural-language use by the trained employee (round 73) — the owner's
# next milestone: ordinary business requests, NO calculator syntax.
# The AGENT selects the applicable formula; the LANE resolves, validates
# and invokes deterministically, and asks ONLY necessary questions.
# ---------------------------------------------------------------------------

#: An estimate/service-job ask (the non-pricing family). A
#: RECALCULATE-that-estimate ask belongs here too — "recalculate"
#: alone is matched by message_requires_calculation, but the family
#: resolver must also recognize it or the ask falls through every
#: lane and the reply narrates memory (live round 74).
_NAT_ESTIMATE_RE = _re.compile(
    r"\b(?:estimate|quote)\b.*\b(?:job|service|work)\b"
    r"|\bservice\s+(?:job\s+)?estimate\b"
    r"|\bjob\s+(?:estimate|cost)\b"
    r"|\brecalculate\b[^.?!\n]*\bestimate\b",
    _re.IGNORECASE | _re.DOTALL)

#: A selling-price ask (the workbook family).
_NAT_PRICE_RE = _re.compile(
    r"\b(?:calculate|compute|work\s+out|figure)\b[^.!?\n]{0,120}"
    r"\b(?:selling\s+)?price\b",
    _re.IGNORECASE)

#: Two taught-expression shapes: a LABELLED formula ("Service
#: estimate: estimate = ROUNDUP(hours*rate + materials, 0)") or a
#: bare assignment ("estimate = ..."). Both require a real
#: assignment '=' — prose colons never match on their own.
_TAUGHT_EXPR_LABEL_RE = _re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 _%&/-]{2,40}?)\s*:\s*"
    r"(?P<name2>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<expr2>[A-Za-z0-9_ +\-*/^().,$]{3,200})")
_TAUGHT_EXPR_BARE_RE = _re.compile(
    r"(?:^|[.!?:]\s|\s)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<expr>[A-Za-z0-9_ +\-*/^().,$]{3,200})")

_PRICE_HEADER_RE = _re.compile(
    r"list\s*price|cdn\s*list|selling\s*price|^price$|price", _re.IGNORECASE)


def parse_taught_expressions(
        lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """TAUGHT EXPRESSIONS (round 73): a lesson may carry an explicit
    formula in the supported language — ``Name: name1 OP name2 ...`` —
    together with taught default inputs (``rate is 150``). This is the
    teaching layer supplying the FORMULA and its standard parameters;
    the engine still does all arithmetic. Structural parsing only: the
    expression must contain a real identifier (>=3 chars) and an
    operator or supported function — prose lessons never produce one.
    """
    from core.formula_engine import evaluate_expression

    out: List[Dict[str, Any]] = []
    for idx, lesson in enumerate(lessons or []):
        text = " ".join(str(lesson.get("lesson")
                             or lesson.get("summary") or "").split())
        if not text or "=" not in text and ":" not in text:
            continue
        lid = str(lesson.get("id") or lesson.get("lesson_id")
                  or f"idx-{idx}")
        found = []  # (display_name, raw_expr)
        label_matches = list(_TAUGHT_EXPR_LABEL_RE.finditer(text))
        for m in label_matches:
            found.append((m.group("label"), m.group("expr2")))
        labelled = [(m.start(), m.end()) for m in label_matches]
        for m in _TAUGHT_EXPR_BARE_RE.finditer(text):
            if any(a <= m.start("name") < b for a, b in labelled):
                continue  # already captured with its label
            found.append((m.group("name"), m.group("expr")))
        for disp, raw in found:
            # cut the captured text at the sentence boundary — the
            # character class admits '.' for decimals, so prose after
            # the formula must not ride along ('... 0). Our service
            # rate is 150...' stops at '0)').
            expr = " ".join(_re.split(r"\.\s", raw or "")[0].split())
            expr = _re.sub(r"\.(?!\d).*$", "", expr).strip()
            if not expr or "," not in expr and not _re.search(
                    r"[+\-*/^]", expr):
                continue
            # identifiers come from the EXPRESSION TEXT (missing
            # inputs never appear in dependencies — they are the
            # precise question, not a resolution)
            from core.formula_engine import SUPPORTED_FUNCTIONS

            idents = sorted({
                t for t in _re.findall(
                    r"\b[A-Za-z_][A-Za-z0-9_]*\b", expr)
                if t.upper() not in SUPPORTED_FUNCTIONS
                and not _re.fullmatch(r"[A-Za-z]{1,3}\d+", t)
                and len(t) >= 2})
            if not any(len(i) >= 3 for i in idents):
                continue
            probe = evaluate_expression(expr, {})
            if probe.unsupported:
                continue
            defaults: Dict[str, str] = {}
            for ident in idents:
                dm = _re.search(
                    rf"\b{_re.escape(ident)}s?\s+(?:is|of|at|=|:)\s*"
                    rf"\$?([0-9][0-9,]*(?:\.[0-9]+)?)", text,
                    _re.IGNORECASE)
                if dm:
                    defaults[ident] = dm.group(1)
            import hashlib as _hl

            # CONTENT-derived version: a changed rate or formula is a
            # different teaching even under the same lesson id — the
            # recorded policy version must move with it (round 74).
            version = _hl.sha256(
                f"{lid}\x1f{expr}\x1f{sorted(defaults.items())}"
                .encode("utf-8")).hexdigest()[:12]
            out.append({
                "name": " ".join(str(disp or "").strip().split()),
                "expr": expr, "idents": idents, "defaults": defaults,
                "lesson_id": lid, "version": version, "text": text})
    return out


def _bind_mentioned_inputs(text: str, idents: List[str]
                           ) -> Dict[str, str]:
    """Bind named inputs the REQUEST itself states: '17.5 hours',
    'rate of 200', 'no materials' (an explicit zero). Only user-stated
    values bind here — nothing is inferred."""
    bound: Dict[str, str] = {}
    for ident in idents:
        m = (
            # EXPLICIT KEY=VALUE FIRST: the tool planner folds
            # conversation inputs into its query as compact
            # `hours=17.5 materials=0` pairs (release case 3, trial 1).
            # kv-first is not just about the '=' — without it, the
            # word-order pattern below would steal "17.5 materials"
            # adjacency and bind materials to the HOURS value.
            _re.search(
                rf"\b{ _re.escape(ident)}s?\s*=\s*"
                rf"\$?([0-9][0-9,]*(?:\.[0-9]+)?)", text,
                _re.IGNORECASE)
            or _re.search(
                rf"\$?([0-9][0-9,]*(?:\.[0-9]+)?)\s*"
                rf"(?:{ _re.escape(ident)}s?)\b", text, _re.IGNORECASE)
            or _re.search(
                rf"\b{ _re.escape(ident)}s?\s+(?:is|of|at|=)\s*"
                rf"\$?([0-9][0-9,]*(?:\.[0-9]+)?)", text,
                _re.IGNORECASE))
        if m:
            bound[ident] = m.group(1).replace(",", "")
            continue
        if _re.search(rf"\bno\s+{ _re.escape(ident)}s?\b", text,
                      _re.IGNORECASE):
            bound[ident] = "0"
    return bound


def _find_item_rows(item: str, user_id: Optional[str],
                    workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """The catalog's Find-All over the item code — the deterministic
    item→row resolution (file, sheet, cell address) the NL path uses."""
    from core.sheet_dataset_service import find_all_occurrences_sync

    try:
        out = find_all_occurrences_sync(
            item, user_id, workspace_id, max_matches=40)
        return list((out or {}).get("matches") or [])
    except Exception:  # noqa: BLE001 — resolution is best-effort
        return []


def _price_cell_for_row(file_name: str, sheet_name: str,
                        row: int) -> Optional[Dict[str, Any]]:
    """The row's PRICE cell: the header whose name matches the price
    vocabulary, mapped to its column letter by frame order. Exactly one
    candidate or None — ambiguity is the caller's question to ask."""
    from core.sheet_dataset_service import read_sheet_row_sync

    res = read_sheet_row_sync(file_name, sheet_name, row)
    if not res or "headers" not in res:
        return None
    ci = 0
    for h in res["headers"]:
        if str(h) == "__sheet_row":
            continue
        if _PRICE_HEADER_RE.search(str(h)):
            letter = _col_letter_fn(ci)
            value = res["row"].get(h)
            if value is None or str(value).strip() == "":
                return None  # the price cell is blank on this row
            return {"cell": f"{letter}{row}", "header": str(h),
                    "value": value}
        ci += 1
    return None


def _col_letter_fn(idx: int) -> str:
    from core.formula_engine import col_letter

    return col_letter(idx)


def _identity_tokens(text: str) -> List[str]:
    """Identity-shaped item tokens in the request (the shared
    keep-rule — '90703', 'GSL48-16' — never prose or bare specs)."""
    from core.workbook_read_artifact import identity_shaped_item

    out: List[str] = []
    for tok in _re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", text or ""):
        # Digit-bearing codes only for price asks: capitalized prose
        # words ('Calculate', 'BurrKing') are not item codes.
        if not _re.search(r"\d", tok):
            continue
        if identity_shaped_item(tok) and tok.upper() not in out:
            out.append(tok.upper())
    return out[:4]


def _authorized_workbook_pairs(
        lessons: List[Dict[str, Any]],
        workspace_id: Optional[str]) -> set:
    """Every cataloged (file, sheet) pair a permanent teaching
    authorizes pricing from — teaching-as-scope for natural price
    asks."""
    from core.models import DatasetEntry
    from core.database import get_db_session

    pairs = set()
    with get_db_session() as db:
        rows = db.query(DatasetEntry).filter(
            DatasetEntry.status == "active").all()
        seen = set()
        for r in rows:
            key = (str(r.file_name or ""), str(r.entity_name or ""))
            if key in seen:
                continue
            seen.add(key)
            if authorized_workbook_basis(lessons, key[0], key[1]):
                pairs.add(key)
    return pairs


async def calculate_natural_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        execution_id: Optional[str] = None) -> Optional[str]:
    """The natural-language entry: the trained employee's ORDINARY
    request, no calculator syntax. Two families:

    * estimate/service-job asks resolve to a TAUGHT EXPRESSION (the
      lesson supplies the formula and standard inputs; the request
      supplies the rest; what is still missing becomes one precise
      question);
    * selling-price asks resolve the ITEM to its row (catalog Find-All),
      scope to the AUTHORIZED workbook basis (teaching-as-scope), pick
      the row's price cell, and run the existing workbook path — which
      preserves every result-type distinction (a stored value stays an
      observation; a substituted computation stays qualified).
    """
    q = str(query or "").strip()
    if not q:
        return None
    lessons = _workspace_lessons(user_id, workspace_id)

    # --- the estimate family (taught expressions) ---------------------
    if _NAT_ESTIMATE_RE.search(q) or "taught rate" in q.lower():
        exprs = parse_taught_expressions(lessons)
        if not exprs:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — NO "
                "TAUGHT FORMULA: no permanent teaching carries a "
                "formula for this kind of request. Do not compute an "
                "estimate by hand; state what the estimate should "
                "include and ask for the teaching.")
        if len(exprs) > 1:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — "
                "SEVERAL TAUGHT FORMULAS apply here: "
                + "; ".join(f"{e['name']} ({e['expr']}) [lesson "
                            f"{e['lesson_id'][:8]}]"
                            for e in exprs[:5])
                + ". Ask which one applies; do not guess.")
        e = exprs[0]
        mentioned = _bind_mentioned_inputs(q, e["idents"])
        inputs = dict(e["defaults"])
        inputs.update(mentioned)
        missing = [i for i in e["idents"] if i not in inputs]
        if missing:
            # DURABLE PENDING STATE (release case 3): the question rides
            # the job as a verification question carrying the structured
            # inputs — the owner's bare ANSWER turn binds from it
            # deterministically (and after a restart), instead of the
            # routing depending on the planner. NO calculate operation
            # is recorded for the asking turn.
            _record_pending_calc_inputs(
                conversation_id, workspace_id, e["name"], missing,
                inputs, e["expr"],
                e.get("version", e["lesson_id"][:12]),
                canvas_id=canvas_id, user_bound=dict(mentioned))
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — "
                f"INPUT NEEDED to use the taught formula "
                f"\"{e['name']}: {e['expr']}\" (lesson "
                f"{e['lesson_id'][:8]}): "
                + ", ".join(missing)
                + ". Bound so far: "
                + (", ".join(f"{k}={v}"
                             + (" (taught default)" if k in e["defaults"]
                                and k not in mentioned else "")
                             for k, v in inputs.items()) or "none")
                + ". Ask the user for exactly these; do not guess.")
        from core.formula_engine import evaluate_expression

        calc = evaluate_expression(e["expr"], inputs)
        result = CalculationResult(
            status=("succeeded" if calc.status == "computed"
                    else calc.status),
            policy_id=f"taught-expression:{e['name']}",
            policy_version=e.get("version", e["lesson_id"][:12]),
            proposed=(Money(calc.value, "XXX",
                            unit=(calc.unit or "value"))
                      if calc.value is not None else None),
            steps=list(calc.steps),
            missing_dependency=(calc.missing or calc.unsupported or "")
            if calc.status == "incomplete" else "",
            dependencies=[d.to_dict() for d in calc.dependencies],
            inputs_snapshot={
                "item": e["name"],
                "basis": (f"taught expression (lesson {e['lesson_id']})"
                          f" evaluated by the general formula engine"),
                "inputs": dict(inputs),
                "request_supplied": sorted(mentioned),
                "taught_defaults": sorted(e["defaults"]),
            })
        # DURABLE OUTCOME (release case 3): record first, then publish
        # with the outcome and carry it on the block — a failed job
        # write is stated in the same block as the result, and the
        # narration guard refuses "saved/recorded" claims for it.
        _recorded = _record_on_job(conversation_id, workspace_id,
                                   e["name"], result,
                                   canvas_id=canvas_id, user_id=user_id,
                                   execution_id=execution_id)
        _publish_calc_record(
            result, user_id=user_id,
            conversation_id=conversation_id, canvas_id=canvas_id,
            query=query, persisted=_recorded)
        lines = [f"**{e['name']} — taught formula, engine-computed**",
                 f"- Formula (taught): {e['expr']}"]
        if calc.status == "computed":
            lines.append(f"- Value (computed): {calc.value}")
        else:
            lines.append(f"- NOT COMPUTED — "
                         f"{calc.missing or calc.unsupported}")
        lines.append("- Inputs: " + ", ".join(
            f"{k}={v}" + (" [taught default]" if k in e["defaults"]
                          and k not in mentioned else " [from request]")
            for k, v in inputs.items()))
        if calc.steps:
            lines.append("- Steps: " + " → ".join(
                str(s.get("output")) for s in calc.steps))
        lines.extend(_persistence_note(_recorded).splitlines())
        return _grounded(
            "LIVE TOOL RESULTS (datasets.calculate — natural language; "
            "the model did not compute this):\n" + "\n".join(lines),
            result_id=result.result_id)

    # --- the selling-price family (authorized workbook basis) ---------
    if _NAT_PRICE_RE.search(q):
        tokens = _identity_tokens(q)
        if not tokens:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — "
                "WHICH ITEM? the request names no item code; ask for "
                "the item to price. Do not guess an item.")
        # teach-as-scope: only file/sheet pairs the teaching authorizes
        authorized_pairs = _authorized_workbook_pairs(lessons,
                                                      workspace_id)
        import asyncio

        candidates: List[Dict[str, Any]] = []
        for item in tokens:
            matches = await asyncio.to_thread(
                _find_item_rows, item, user_id, workspace_id)
            for mmatch in matches:
                key = (str(mmatch.get("file")), str(mmatch.get("sheet")))
                if key not in authorized_pairs:
                    continue
                row = int("".join(
                    c for c in str(mmatch.get("cell") or "") if c.isdigit())
                          or 0)
                if not row:
                    continue
                candidates.append({"item": item, "file": key[0],
                                   "sheet": key[1], "row": row})
        if not candidates:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — NO "
                "AUTHORIZED BASIS FOR THIS ITEM: the item was "
                + (f"found in the catalog but no teaching authorizes "
                   "pricing from the file/sheet it lives in"
                   if tokens else "not found")
                + ". A formula's existence does not make it the "
                "approved pricing policy; ask for the intended basis.")
        resolved: List[Dict[str, Any]] = []
        for cand in candidates:
            pc = _price_cell_for_row(cand["file"], cand["sheet"],
                                     cand["row"])
            if pc:
                resolved.append({**cand, **pc})
        if not resolved:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — NO "
                "PRICE CELL: the item's row carries no price column "
                "value in the authorized workbook. Ask which price "
                "basis applies; do not guess a cell.")
        if len({(c["file"], c["sheet"], c["row"]) for c in resolved}) > 1:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — natural) — "
                "SEVERAL authorized candidates: "
                + "; ".join(f"{c['item']} → {c['file']} {c['sheet']} "
                            f"row {c['row']} cell {c['cell']}"
                            for c in resolved[:5])
                + ". Ask which one applies; do not guess.")
        c0 = resolved[0]
        return await calculate_workbook_from_query(
            f"calculate price for {c0['file']} {c0['sheet']} "
            f"row {c0['row']} cell {c0['cell']} item={c0['item']}",
            user_id, workspace_id, conversation_id=conversation_id)

    return None


#: A bare imperative to recalculate/recompute — regardless of family.
#: Named so the conversation-state follow-up resolver (release case 3)
#: and the explicit-ask classifier share ONE definition of the shape.
_RECALC_IMPERATIVE_RE = _re.compile(
    r"\b(?:re-?calculate|recompute|run\s+the?"
    r"\s+calculation)\b", _re.IGNORECASE)


def calc_pending_question_reply(
        message: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str]) -> Optional[str]:
    """The user-facing rendering of the conversation's OPEN pending
    calculation question, re-derived from durable state — the honest
    reply when the narration leg collapsed (template delivery). No
    figure, no authority claim: the question and the taught formula
    only."""
    try:
        if not conversation_id:
            return None
        q = _pending_calc_question(conversation_id, workspace_id)
        if q is None:
            return None
        inputs = q.get("inputs") or {}
        missing = [str(m) for m in (inputs.get("missing") or [])]
        if not missing:
            return None
        return (
            "To run your taught-formula calculation I still need: "
            + ", ".join(missing)
            + ".\n\n(Taught formula: " + str(inputs.get("expr") or "")
            + ". The calculation did not run yet — reply with the "
            "values and I'll compute it.)")
    except Exception:  # noqa: BLE001 — delivery is additive
        return None


def record_pending_for_failed_calc_ask(
        message: str,
        user_id: Optional[str],
        workspace_id: Optional[str],
        conversation_id: Optional[str],
        canvas_id: Optional[str] = None) -> bool:
    """TIMEOUT-TO-FOLLOW-UP BOUNDARY (owner directive 2026-10-07): a
    calculation-shaped ask whose turn FAILED before the calculate lane
    ran (provider distress, budget exhaustion, timeout) must still
    leave the durable pending-calculation context — policy/version,
    known inputs, unresolved fields — so the owner's NEXT message
    ("17.5 hours, no materials.") binds to unfinished calculation work
    and the engine executes. Without this, the failed ask left no
    pending state and the follow-up's teaching-based arithmetic was
    narrated without an engine result (the established defect).

    Deterministic — no LLM: parse the taught expressions, bind what the
    ask stated, record the missing-input question for the single
    applicable expression. Skips when a pending question already exists
    (the lane ran), when no teaching applies, or when the ask carried
    every input (nothing to ask; an explicit retry re-asks). Fault-
    isolated: a recording failure never breaks the failing turn."""
    try:
        q = str(message or "").strip()
        if not q or not conversation_id:
            return False
        if not (_NAT_ESTIMATE_RE.search(q) or "taught rate" in q.lower()):
            return False
        if _pending_calc_question(conversation_id, workspace_id) is not None:
            return False  # the lane already asked; its question stands
        lessons = _workspace_lessons(user_id, workspace_id)
        exprs = parse_taught_expressions(lessons)
        if len(exprs) != 1:
            return False  # ambiguity is the lane's question to ask, in turn
        e = exprs[0]
        mentioned = _bind_mentioned_inputs(q, e["idents"])
        inputs = dict(e["defaults"])
        inputs.update(mentioned)
        missing = [i for i in e["idents"] if i not in inputs]
        if not missing:
            return False
        return _record_pending_calc_inputs(
            conversation_id, workspace_id, e["name"], missing,
            inputs, e["expr"],
            e.get("version", e["lesson_id"][:12]),
            canvas_id=canvas_id, user_bound=dict(mentioned))
    except Exception:  # noqa: BLE001 — boundary is additive
        return False


def message_requires_calculation(message: str) -> bool:
    """Whether the message is an EXPLICIT calculation ask — the shapes
    that must dispatch the engine (or its validated reuse) rather than
    be answered from conversation memory. Bounded to the three forms
    the calculate lane understands; a mention of prices in an ordinary
    search ask does NOT match."""
    m = str(message or "").strip()
    if not m:
        return False
    if _WB_QUERY_RE.search(m) or _EXPR_QUERY_RE.match(m):
        return True
    if _NAT_ESTIMATE_RE.search(m):
        return True
    if _NAT_PRICE_RE.search(m):
        return True
    # a bare imperative to recalculate/recompute — regardless of family
    if _RECALC_IMPERATIVE_RE.search(m):
        return True
    return False
