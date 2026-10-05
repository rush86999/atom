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

import copy
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

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
    """A typed calculation recipe with provenance and version."""
    policy_id: str
    name: str
    steps: List[PolicyStep]
    provenance: str = ""       # 'lesson:4b6a11cc' / 'config:xyz'
    version: str = "1"
    freshness_window_days: Optional[int] = None
    conditions: List[str] = field(default_factory=list)  # applicability


@dataclass
class CalculationResult:
    """The full, replayable outcome. `status` in
    {'succeeded','unresolved','rejected'} — unresolved keeps the missing
    input named; succeeded-with-stale-source carries the limitation."""
    status: str
    proposed: Optional[Money] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_reason: str = ""
    rejection_reason: str = ""
    freshness: str = "unknown"   # 'current' | 'stale' | 'unknown'
    policy_id: str = ""
    policy_version: str = ""
    inputs_snapshot: Dict[str, Any] = field(default_factory=dict)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_record(self) -> Dict[str, Any]:
        return {
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
    if result.steps:
        chain = " → ".join(
            f"{s.get('output_amount', s.get('status'))}"
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
    it serves."""
    ops = "-".join(s.op for s in steps)
    return f"taught-{ops}"



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
        # Unresolved inputs become durable next-work: a research action
        # or a precise owner question — never a silent choice.
        if result.status == "unresolved":
            from core.task_lifecycle import add_unresolved_questions

            add_unresolved_questions(lifecycle, run_id, [{
                "item": item_label,
                "kind": "verification",
                "question": (
                    f"the price calculation for {item_label} cannot "
                    f"complete: {result.unresolved_reason}"),
                "evidence": (
                    f"policy {result.policy_id} v{result.policy_version}; "
                    "no value invented"),
                "next_action": (
                    f"provide or research the missing input "
                    f"({result.unresolved_reason})"),
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
