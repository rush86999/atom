# -*- coding: utf-8 -*-
"""Generation-level accounting for routing feedback evidence.

WHY THIS EXISTS
===============

``llm_routing_feedback`` rows are NOT one-per-generation. One observed model
output can produce several rows:

* the **outcome** row written when the generation path returns
  (``_record_outcome_feedback``), and
* a **corrective verdict** row written later, when a guard catches an invented
  figure or an unsupported claim (``record_fabrication_signal``) — the guard
  runs on the *assembled reply*, after the outcome row already exists.

Dividing ``fabrication rows / all rows`` therefore mixes two units and lets a
correction inflate the denominator: one fabricated generation among four
evaluated generations reads as ``1/5``, which can fall below the bench
threshold and leave a fabricating model in the candidate list. Measured on the
live table 2026-09-16: 170 rows over 168 generations, two of them written
twice.

IDENTITIES
==========

``turn``
    One routing decision — identified by ``routing_result_id``. A turn that
    falls back to a second model produces two attempts within ONE turn.

``attempt``
    ``(turn, model_id)``. A primary attempt and a fallback attempt are both
    real attempts and each contributes its own generation; neither may be
    dropped or merged.

``generation``
    The model output produced by one attempt. **This is the unit of the
    fabrication rate** — the denominator is the number of EVALUATED
    generations, never the number of rows.

``verdict``
    The corrective stamp attached to a generation
    (``prompt_features["verdict"]``). At most one effective verdict per
    generation: repeating a correction for the same generation is idempotent
    (see ``LearningBasedRouter._persist_feedback``), and this module collapses
    any residual duplicates when counting.

CLASSIFICATION
==============

A generation is classified from all rows that carry its identity:

``fabricated``
    some row carries a fabrication verdict (``unsupported_figures`` /
    ``ungrounded_claims``) — counts in numerator AND denominator.
``grounded_ok``
    some row carries a POSITIVE grounding marker (``grounding_ok``): the check
    ran on this generation and found nothing unsupported. Counts in the
    denominator only. This — not a high score — is what qualifies a generation
    as evaluated for honesty.
``availability``
    only availability verdicts (timeout / provider error / empty response).
    An outage is not evidence about honesty, so it is excluded from BOTH
    terms and reported separately.
``evidence_ignored``
    the reply was handed evidence that CONTAINED the answer and did not use it
    (the deterministic derivation check). A judgement on a real output, so it
    is counted — but in its OWN class and against its OWN denominator, never
    the fabrication one: a compliance failure must not dilute the honesty rate
    and an invention must not dilute the compliance rate. Keeping it out of
    ``generations`` is deliberate — that denominator decides the fabrication
    bench, and letting a different defect class enlarge it would rebuild the
    exact dilution this module exists to prevent.
``unevaluated``
    a real quality measurement above the fabrication band with NO grounding
    provenance. ``user_satisfaction`` comes from the heuristic assessment
    (truncation / refusal / schema / empty) and says nothing about grounding:
    the incident's confidently wrong replies scored well. "No fabrication
    detected" is not "grounding evaluated successfully", so these generations
    are excluded from the denominator and reported — never called clean.
``unknown``
    a low/absent score with no verdict provenance. **Historical rows with no
    provenance stay explicitly UNKNOWN** — absence of provenance cannot
    establish absence of fabrication. Reported separately so the shortfall is
    visible.

FAILURE ISOLATION
=================

Malformed metadata is a per-ROW property, never a property of the pass: a
``prompt_features`` payload of JSON ``null``, a JSON array, a bare string or
truncated JSON marks that row unknown and is counted in ``malformed_rows``.
It must never abort the accounting and must never make the caller's check
fail open ("no fabrication found" for a model that has one).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Tuple

#: Verdicts that mean "this generation's content was judged fabricated".
FABRICATION_VERDICTS = frozenset({"unsupported_figures", "ungrounded_claims"})

#: Verdicts that mean "the grounding check RAN on this generation and found
#: nothing unsupported". This is the ONLY positive evidence that a generation
#: was evaluated for honesty — without it, a high heuristic score is just
#: "nothing structural was wrong", which is what the incident's confidently
#: wrong replies scored.
GROUNDING_EVALUATED_VERDICTS = frozenset({"grounding_ok", "grounding_passed"})

#: Verdicts that mean "this generation was handed evidence containing the
#: answer and did not use it". A real defect, judged deterministically on the
#: output, but NOT dishonesty: no figure was invented. It therefore gets its
#: own class so neither rate can mask the other.
EVIDENCE_VERDICTS = frozenset({"evidence_ignored"})

#: WHICH RULE produced a verdict — the version stamp that makes a verdict
#: usable as EXCLUSION evidence.
#:
#: Why this exists (measured 2026-09-16): the deterministic figure check reports
#: "figures in the reply appear in NO retrieved evidence". For a derivation turn
#: the delivered evidence carries the matched row's FORMULAS, so every correctly
#: COMPUTED value is by construction absent from the evidence text. The rule
#: therefore recorded fabrications against models that had answered correctly —
#: the live log shows the verdicts naming the derivation chain itself
#: ("5,625.30, 7,518, 1,893.70" on a reply that walked the stored formulas).
#: A verdict is only as good as the rule that produced it, so verdict rows now
#: carry the rule's identity, and a consumer that EXCLUDES a route on verdict
#: evidence (the fabrication bench) counts only verdicts written by a rule that
#: can tell "computed" from "invented". Legacy rows carry no stamp: their
#: context is UNKNOWN, and unknown provenance may not exclude a route — the same
#: principle that keeps unprovenanced history out of the honest count, applied
#: in the direction that protects a model from being condemned by a rule we have
#: since found unsound.
#: Figure verdict recorded because the WORKBOOK CONTRADICTED the reply's
#: arithmetic — the derivation verifier evaluated the delivered formulas and the
#: reply's own cell-anchored claims disagreed with them. This is proof, not a
#: heuristic, so it may exclude a route.
FIGURE_VERDICT_RULE = "figures_v2"
#: Figure verdict recorded by the EVIDENCE-ABSENCE heuristic WITHOUT a
#: derivation cross-check (no cell-anchored claim to verify, or the verifier
#: unavailable). The heuristic cannot tell a value COMPUTED from the delivered
#: formulas from an invented one — live 2026-09-16 it flagged `$4,815.00`, a
#: stored row value, on a reply it could not cross-check. Recorded (the ledger
#: keeps what the guard said) but NEVER exclusion evidence: a route may not be
#: removed on a verdict no independent check confirms.
FIGURE_HEURISTIC_RULE = "figures_heuristic"
PANEL_VERDICT_RULE = "panel_v1"          # verification judge panel

#: Rules whose verdicts are acceptable as EXCLUSION evidence today.
CURRENT_VERDICT_RULES = frozenset({FIGURE_VERDICT_RULE, PANEL_VERDICT_RULE})

#: Which verdict wins when two judgements land on the SAME generation (one
#: verdict slot per row). Higher wins; equal is idempotent. Ordering is by
#: severity of the claim about the output: an invention outranks a refusal to
#: use the evidence, which outranks the positive marker that the grounding
#: check merely ran. Availability verdicts are absent on purpose — they judge
#: an attempt that produced no output and never annotate another attempt's row.
VERDICT_PRECEDENCE = {
    "unsupported_figures": 4,
    "ungrounded_claims": 4,
    "evidence_ignored": 3,
    "grounding_ok": 2,
    "grounding_passed": 2,
}

#: Verdicts that are a JUDGEMENT ON THE OUTPUT (as opposed to a statement
#: about the check that ran). Only these may rewrite a row's quality fields.
JUDGEMENT_VERDICTS = FABRICATION_VERDICTS | EVIDENCE_VERDICTS


def verdict_rank(verdict: Any) -> int:
    """Severity rank of a stored verdict; ``0`` for absent/unrecognised.

    Unrecognised provenance ranks 0: it cannot outrank a real judgement, and a
    real judgement may replace it (an unknown marker carries no information to
    preserve).
    """
    if not isinstance(verdict, str):
        return 0
    return VERDICT_PRECEDENCE.get(verdict.strip(), 0)


#: Verdicts that mean "no usable output" — an availability failure, which is
#: evidence about uptime, not about honesty.
AVAILABILITY_VERDICTS = frozenset({
    "timeout",
    "provider_error",
    "empty_response",
    "empty_truncation",
    "cancelled",
})

#: At/below this satisfaction score the row is in the fabrication band. A
#: score in this band WITHOUT a verdict is not proof of fabrication (it is
#: also where provider exceptions and empty completions land), so it stays
#: unknown rather than counting as clean or as fabricated.
FABRICATION_SCORE_CEILING = 0.15

_MISSING = object()


def coerce_features(raw: Any) -> Tuple[Dict[str, Any], bool]:
    """Return ``(features, malformed)`` for a stored ``prompt_features`` value.

    ``None``/empty is simply ABSENT (never malformed). A JSON object is
    returned as-is. Anything else — JSON ``null``, an array, a bare scalar,
    truncated JSON, a Python list — is malformed: the caller gets ``{}`` plus
    ``malformed=True`` and decides the row's fate; it never raises.
    """
    if raw is None:
        return {}, False
    if isinstance(raw, dict):
        return raw, False
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:  # noqa: BLE001 — undecodable bytes are malformed
            return {}, True
    if isinstance(raw, str):
        if not raw.strip():
            return {}, False
        try:
            parsed = json.loads(raw)
        except Exception:  # noqa: BLE001 — truncated/garbage JSON
            return {}, True
        if parsed is None:
            # JSON ``null`` is how a JSON column stores "no features" — the
            # live table holds 67 such rows. Absent, not corrupt.
            return {}, False
        if isinstance(parsed, dict):
            return parsed, False
        return {}, True
    # A list/int/bool handed straight from a JSON column: not a feature map.
    return {}, True


def verdict_of(raw: Any) -> Tuple[Optional[str], bool]:
    """Return ``(verdict, malformed)`` for a stored ``prompt_features`` value.

    The verdict must be a non-empty string; a list/dict/number in the
    ``verdict`` slot is treated as absent provenance rather than coerced into
    a match.
    """
    features, malformed = coerce_features(raw)
    value = features.get("verdict")
    if value is None:
        return None, malformed
    if not isinstance(value, str):
        return None, True
    value = value.strip()
    return (value or None), malformed


def verdict_rule_of(raw: Any) -> Optional[str]:
    """Return the RULE that produced a row's verdict, or ``None``.

    ``None`` means the row predates rule stamping (or carries no verdict):
    its context is unknown, which consumers must read as "not usable as
    exclusion evidence" rather than as a clean bill of health. Never raises —
    an unreadable payload simply has no rule.
    """
    try:
        features, _malformed = coerce_features(raw)
    except Exception:  # noqa: BLE001 — unreadable provenance has no rule
        return None
    value = features.get("verdict_rule")
    if not isinstance(value, str):
        return None
    return value.strip() or None



def _field(row: Any, name: str, index: int) -> Any:
    """Read a field from an ORM row, a namespace, a mapping or a tuple."""
    if isinstance(row, dict):
        return row.get(name, None)
    if isinstance(row, (tuple, list)):
        return row[index] if index < len(row) else None
    value = getattr(row, name, _MISSING)
    return None if value is _MISSING else value


def generation_key(row: Any) -> Tuple[str, str]:
    """Identity of the generation a row describes: ``(turn, model)``.

    ``turn`` is the routing decision id. Rows that predate id capture (or that
    were written by a caller that could not supply one) fall back to their own
    row id, so they are counted as their own generation instead of being
    silently merged into somebody else's.
    """
    turn = _field(row, "routing_result_id", 1)
    turn = str(turn).strip() if turn is not None else ""
    if not turn:
        row_id = _field(row, "id", 0)
        turn = f"row:{row_id}" if row_id is not None else "row:?"
    model = _field(row, "model_id", 2)
    return turn, str(model) if model is not None else ""


@dataclass
class GenerationAccounting:
    """Counts over EVALUATED GENERATIONS (not rows, not raw scores)."""

    generations: int = 0        # denominator: generations with a GROUNDING verdict
    fabricated: int = 0         # numerator
    #: Generations whose grounding check RAN and passed (an explicit positive
    #: marker). Deliberately not called "clean": a high heuristic score with no
    #: grounding marker means "nothing was checked", which is reported as
    #: ``unevaluated`` instead (review item 3).
    grounded_ok: int = 0
    #: Generations judged to have IGNORED evidence they were handed. Counted in
    #: its own class: not in ``fabricated`` (no invention), and NOT in
    #: ``generations`` (that denominator decides the fabrication bench, and a
    #: different defect class must not enlarge it — see the module docstring).
    evidence_ignored: int = 0
    #: A real quality measurement with NO grounding provenance: the ordinary
    #: heuristic assessment (truncation / refusal / schema / empty). It cannot
    #: be counted as evaluated for honesty, and it must not be counted as
    #: clean either — "no fabrication detected" is not "grounding evaluated
    #: successfully".
    unevaluated: int = 0
    unknown: int = 0            # low score, no provenance — excluded, reported
    availability: int = 0       # outage — excluded, reported
    rows: int = 0               # raw rows seen
    duplicate_rows: int = 0     # rows collapsed into an already-seen generation
    malformed_rows: int = 0     # rows whose metadata could not be read
    verdict_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def clean(self) -> int:
        """Deprecated alias for ``grounded_ok`` — kept so older callers and
        reports do not silently read 0. New code must use ``grounded_ok``."""
        return self.grounded_ok

    @property
    def rate(self) -> Optional[float]:
        """Fabricated share of EVALUATED generations, or ``None`` when there
        are none (an undefined rate must not read as 0.0)."""
        if self.generations <= 0:
            return None
        return self.fabricated / self.generations

    @property
    def judged_outputs(self) -> int:
        """Generations carrying an OUTPUT JUDGEMENT (honesty or compliance)."""
        return self.fabricated + self.grounded_ok + self.evidence_ignored

    @property
    def evidence_ignored_rate(self) -> Optional[float]:
        """Ignored-evidence share of judged outputs, or ``None`` when there are
        none. Its own denominator: the compliance signal must stay readable
        even while the honesty denominator is empty, and vice versa."""
        if self.judged_outputs <= 0:
            return None
        return self.evidence_ignored / self.judged_outputs

    def as_dict(self) -> Dict[str, Any]:
        return {
            "generations": self.generations,
            "fabricated": self.fabricated,
            "grounded_ok": self.grounded_ok,
            "clean": self.grounded_ok,  # deprecated alias
            "evidence_ignored": self.evidence_ignored,
            "judged_outputs": self.judged_outputs,
            "unevaluated": self.unevaluated,
            "unknown": self.unknown,
            "availability": self.availability,
            "rows": self.rows,
            "duplicate_rows": self.duplicate_rows,
            "malformed_rows": self.malformed_rows,
            "rate": self.rate,
            "evidence_ignored_rate": self.evidence_ignored_rate,
            "verdict_counts": dict(self.verdict_counts),
        }



def account_generations(rows: Iterable[Any]) -> GenerationAccounting:
    """Collapse feedback rows into per-generation fabrication accounting.

    Never raises: a row whose fields are missing or malformed is counted and
    skipped, so one bad row cannot decide the fate of a model's whole check.
    """
    acc = GenerationAccounting()
    states: Dict[Tuple[str, str], Dict[str, bool]] = {}

    for row in rows:
        acc.rows += 1
        try:
            key = generation_key(row)
            verdict, malformed = verdict_of(_field(row, "prompt_features", 4))
        except Exception:  # noqa: BLE001 — one unreadable row is not a pass
            acc.malformed_rows += 1
            acc.unknown += 1
            continue

        if malformed:
            acc.malformed_rows += 1
        if verdict:
            acc.verdict_counts[verdict] = acc.verdict_counts.get(verdict, 0) + 1

        state = states.get(key)
        if state is None:
            state = {"fabricated": False, "grounded_ok": False,
                     "evidence_ignored": False,
                     "unevaluated": False, "availability": False,
                     "unknown": False}
            states[key] = state
        else:
            acc.duplicate_rows += 1

        if malformed:
            # The metadata that would carry a verdict could not be read — most
            # likely truncated mid-write. Such a row can neither accuse nor
            # exonerate: UNKNOWN, whatever the score says.
            state["unknown"] = True
            continue
        if verdict in FABRICATION_VERDICTS:
            state["fabricated"] = True
            continue
        if verdict in EVIDENCE_VERDICTS:
            # A real judgement on a real output — counted in its own class.
            # Deliberately does NOT set ``grounded_ok`` (the honesty check may
            # never have run) and does NOT enter ``generations``. Checked
            # BEFORE the grounding marker so a generation carrying both is
            # classified by the stronger claim, matching ``VERDICT_PRECEDENCE``
            # (the single verdict slot resolves the same way at write time).
            state["evidence_ignored"] = True
            continue
        if verdict in GROUNDING_EVALUATED_VERDICTS:
            # The grounding check RAN on this generation and found nothing
            # unsupported. That is the only way a generation earns a place in
            # the denominator without a fabrication verdict.
            state["grounded_ok"] = True
            continue

        if verdict in AVAILABILITY_VERDICTS:
            state["availability"] = True
            continue
        if verdict:
            # An UNRECOGNISED verdict is not a clean bill of health.
            state["unknown"] = True
            continue

        score = _field(row, "user_satisfaction", 3)
        if score is None:
            state["unknown"] = True
            continue
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            state["unknown"] = True
            continue
        # A real score with NO grounding verdict means the grounding check never
        # ran on this generation, so it does not belong in the denominator —
        # whatever the score says (review item 3). The two bands are reported
        # separately because they carry different risk:
        #   * ABOVE the band -> the ordinary heuristic assessment (truncation /
        #     refusal / schema / empty); merely not grounded. UNEVALUATED.
        #   * INSIDE the band -> exactly where provider exceptions, empty
        #     completions AND fabrications all land; without provenance we
        #     cannot tell which. UNKNOWN, never "clean".
        if score_value > FABRICATION_SCORE_CEILING:
            state["unevaluated"] = True
        else:
            state["unknown"] = True

    for state in states.values():
        if state["fabricated"]:
            acc.fabricated += 1
            acc.generations += 1
        elif state["evidence_ignored"]:
            # Same order as the per-row classification: the stronger claim
            # decides the generation, so it cannot also be counted as an
            # honestly-evaluated one.
            acc.evidence_ignored += 1
        elif state["grounded_ok"]:
            acc.grounded_ok += 1
            acc.generations += 1
        elif state["availability"]:
            acc.availability += 1
        elif state["unevaluated"]:
            acc.unevaluated += 1
        else:
            acc.unknown += 1



    return acc
