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
    {'succeeded','unresolved','rejected','incomplete'} — unresolved keeps
    the missing input named; succeeded-with-stale-source carries the
    limitation; INCOMPLETE (round 69) means the WORKBOOK calculation
    itself could not be reconstructed completely (an unsupported
    operation or an unresolvable dependency cell): the exact gap is
    named in `missing_dependency` and NO partial value is published."""
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
        op = lifecycle.create_operation(
            run_id, op_type="calculate",
            requested_change=(
                f"calculate proposed price for {item_label or 'item'} "
                f"under policy {result.policy_id} "
                f"(v{result.policy_version})"))
        status_map = {
            "succeeded": "applied",
            "unresolved": "waiting",
            "rejected": "failed",
            # INCOMPLETE (round 69): the workbook calculation itself is
            # missing a dependency or hits an unsupported operation —
            # the operation stays open exactly like an unresolved input,
            # and no partial value was ever proposed.
            "incomplete": "waiting",
        }
        lifecycle.transition_operation(
            run_id, op["operation_id"], "running",
            execution_id=execution_id)
        lifecycle.transition_operation(
            run_id, op["operation_id"],
            status_map.get(result.status, "failed"),
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
        # Unresolved inputs AND incomplete reconstructions become durable
        # next-work: a research action or a precise owner question —
        # never a silent choice, and never a partial published price.
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
                    f"source {result.inputs_snapshot.get('source', {})
                               .get('reference')}"),
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


def _grounded(body: str) -> str:
    try:
        from core.chat_tool_planner import _with_grounding

        return _with_grounding(
            "LIVE TOOL RESULTS (datasets.calculate — deterministic "
            "Decimal arithmetic; the model did not compute this):\n"
            + body)
    except Exception:  # noqa: BLE001 — grounding is additive
        return ("LIVE TOOL RESULTS (datasets.calculate):\n" + body)


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
        status="succeeded" if calc.status == "complete" else "incomplete",
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
    if calc.status != "complete":
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

        best: Dict[str, Dict[str, Any]] = {}
        with get_db_session() as db:
            q = db.query(DatasetEntry).filter(
                DatasetEntry.file_name == self.file_name,
                DatasetEntry.status == "active")
            if self.workspace_id:
                q = q.filter(DatasetEntry.workspace_id == self.workspace_id)
            for e in q.all():
                key = " ".join(str(e.entity_name or "").lower().split())
                rec = {
                    "entity_name": str(e.entity_name or ""),
                    "parquet_path": str(e.parquet_path or ""),
                    "content_hash": str(e.content_hash or ""),
                    "source": str(e.source or ""),
                    "external_id": str(e.external_id or ""),
                    "source_modified_at": (
                        e.source_modified_at.isoformat()
                        if e.source_modified_at else None),
                }
                if key not in best:
                    best[key] = rec
                elif (self.prefer_hash and
                        rec["content_hash"] == self.prefer_hash):
                    best[key] = rec
        self._entries = list(best.values())
        return self._entries

    def entry_for(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        want = " ".join(str(sheet_name or "").lower().split())
        for e in self._load_entries():
            if " ".join(str(e["entity_name"]).lower().split()) == want:
                return e
        return None

    def provider(self, sheet_name: str) -> Optional["CellBook"]:
        from core.formula_engine import (CellBook,
                                         sheet_grid_from_parquet)

        key = " ".join(str(sheet_name or "").lower().split())
        if key in self._books:
            return self._books[key]
        entry = self.entry_for(sheet_name)
        if entry is None or not entry.get("parquet_path"):
            return None
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
                book.overlay(live["values"], "live_read",
                             formulas=live["formulas"])
        self._books[key] = book
        return book


async def calculate_workbook_from_query(
        query: str,
        user_id: Optional[str],
        workspace_id: Optional[str]) -> Optional[str]:
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

    # LITERAL-SHEET OBSERVATION (owner's rule): a sheet whose values are
    # typed literals has no calculation to run — the stored value is
    # reported as an observation with its source, never a derived price.
    if calc.status == "incomplete" and "has no formula" in calc.missing:
        if values.get(cell) is not None:
            return _grounded(
                "LIVE TOOL RESULTS (datasets.calculate — workbook) — "
                f"SOURCED VALUE (no calculation): {sheet_name}!{cell} = "
                f"{values.get(cell)}, stored in {file_name} (workbook "
                f"version {(entry.get('content_hash') or '')[:12]}). "
                "This sheet's values are typed literals, not formulas: "
                "there is no workbook calculation to reconstruct; the "
                "stored value is an observation from its source, not a "
                "computed price.")
        return _grounded(
            "LIVE TOOL RESULTS (datasets.calculate — workbook) — NO "
            f"CALCULATION AND NO STORED VALUE at {sheet_name}!{cell}: "
            "the sheet has no formula there and no stored value either.")

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
                from core.formula_engine import workbook_grid_from_bytes

                live = workbook_grid_from_bytes(content)
                # Order-independent: the grid rides the books object and
                # every book built from here on (target re-evaluation AND
                # sibling sheets first touched mid-walk) receives it.
                # The TARGET book itself must join the cache first — it
                # was built locally from the frame and is the one book
                # the overlay loop would otherwise miss (live 2026-10-05:
                # turn ran 'no formula, stored value only' exactly here).
                books.live_grid = live
                books._books.setdefault(  # noqa: SLF001
                    " ".join(sheet_name.lower().split()), target_book)
                for key, book in list(  # noqa: SLF001
                        books._books.items()):
                    if key in live:
                        book.overlay(live[key]["values"], "live_read",
                                     formulas=live[key]["formulas"])
                # VERSION DIVERGENCE HONESTY: the live bytes are their
                # own workbook version — when they differ from the
                # cataloged snapshot, the record says so (the cataloged
                # version is the stale one; the calculation ran on the
                # live bytes).
                import hashlib as _hl

                live_hash = _hl.sha1(content).hexdigest()
                if entry.get("content_hash") and \
                        live_hash != entry.get("content_hash"):
                    _live_version_divergence = live_hash
                calc = evaluate_reference(
                    entry["entity_name"], cell, target_book,
                    books.provider, row_of_interest=row_number,
                    cached_value=values.get(cell), origin=_origin())
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
    body = render_comparison(
        item_label or f"{sheet_name} row {row_number}", None, result)
    return _grounded(body)


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
