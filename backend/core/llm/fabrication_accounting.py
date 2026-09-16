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

    def as_dict(self) -> Dict[str, Any]:
        return {
            "generations": self.generations,
            "fabricated": self.fabricated,
            "grounded_ok": self.grounded_ok,
            "clean": self.grounded_ok,  # deprecated alias
            "unevaluated": self.unevaluated,
            "unknown": self.unknown,
            "availability": self.availability,
            "rows": self.rows,
            "duplicate_rows": self.duplicate_rows,
            "malformed_rows": self.malformed_rows,
            "rate": self.rate,
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
