#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded provider-reliability replay + fallback-independence probe.

Replays a SMALL, representative workload through whatever routes are
currently configured, and records — per attempt — a *contract-checked*
outcome, real streamed first-visible latency, per-attempt telemetry, and
the routing topology the fallbacks live in.

What changed relative to the first version of this harness (external review
items 4 and 5):

1. **An answer contract per probe.**  A non-empty string is no longer
   "success".  Each probe declares a checkable contract (sentinel token,
   expected number, ...) and the reply is verified against it.  Transport
   success and contract satisfaction are recorded separately, so a refusal,
   an apology, a truncated fragment or a wrong answer is a *contract
   violation*, not an `ok`.

2. **First-visible latency comes from real streamed output.**  In
   ``--mode stream`` (the default) the probe is issued through
   ``BYOKHandler.stream_completion`` — which sets ``stream=True`` on the
   OpenAI-compatible client and iterates chunks — and the first-visible
   stamp is taken on the first chunk carrying non-empty content (role-only,
   empty and whitespace-only deltas do not stamp it).  The previous version
   stamped first-visible *after* a non-streaming call returned, which just
   approximated completion latency.  In ``--mode completion`` first-visible
   is reported as ``None`` with ``first_visible_measurable: false``.

3. **Fixture limits are stated, and unsupported expectations are excluded.**
   The medium fixture's rows bind values to ``machine <i>`` and never carry
   or link the identifier ``F-5216``, so a price expectation for that
   identifier is *unsupported by the fixture*; it is marked
   ``unsupported_by_fixture`` and excluded from the contract pass rate
   rather than counted either way.  The large fixture's row ``R235`` does
   state ``LIST Price=7519.0``, so the list-price expectation is checkable,
   but its formula string (``G235==F235*0.9 | I235==H235+700``) never
   defines ``F235``/``H235`` and ``5350*0.9 = 4815 != 7519``, so "the
   formula chain derives it" is likewise `unsupported_by_fixture`.  Both
   limitations are printed in the report (``## Fixture limitations``).

4. **Per-attempt telemetry + real caps.**  Every attempt records the
   requested and the actually-used ``(provider, model)`` pair, whether it
   was a retry and its retry index, a structured error (type/message/
   status), token usage (prompt/completion/total) with an explicit
   ``usage_estimated`` flag, the cost when the provider reports one and an
   explicit ``cost_unknown`` flag when it does not.  An explicit
   ``--retry-cap`` and ``--spend-cap-usd`` are enforced *inside* the loop
   and the effective caps are printed with the run.

5. **Honest denominators.**  Every rate carries its numerator and
   denominator (attempts, distinct generations, ``(provider, model)``
   pairs) and a rate with a zero denominator is reported as ``null`` /
   ``n/a``, never as ``0%``.

Item 5 — fallback independence at the REQUEST boundary
------------------------------------------------------

A restored credential does not prove that a provider authenticates,
supports the required request, enters the ranking, or succeeds as a
fallback.  ``--fallback-independence`` therefore checks, against the LIVE
configuration:

1. for every configured provider: that a key resolves, that a minimal real
   request authenticates and returns a *contract-satisfying* answer, and
   that the provider appears in the routing ladder for a representative
   request;
2. then a CONTROLLED PRIMARY FAILURE (an intentionally invalid primary
   model on a real provider) is exercised and the full attempt sequence is
   recorded to see whether a fallback actually answers.

``(provider, model)`` pairs are preserved throughout: the ladder is read as
``List[Tuple[str, str]]`` and every record keeps both fields.  Model names
alone lose provider identity when one model is served through several
gateways.  **The production code this harness calls does contain
name-keyed lookups** (reported, not fixed — out of this harness's file
scope):

* ``BYOKHandler.get_fallback_models()`` returns ``List[str]`` — model names
  only, provider identity dropped;
* ``BYOKHandler.stream_completion(fallback_models=[name, ...])`` recurses
  with the ORIGINAL ``provider_id`` for a model name that came from a
  different ``(provider, model)`` ladder pair;
* ``DynamicPricingFetcher.get_model_price(model_name)`` /
  ``LLMService.estimate_cost(..., model)`` resolve price by model name
  alone, so a cost estimate carries no provider dimension.

Topology states
---------------

``topology_state`` replaces the old boolean with four named states —
``some_shared_fallbacks`` (at least one fallback shares the primary's
upstream provider, but not all), ``all_shared_fallbacks``, ``no_fallback``
and ``unknown_topology`` (could not be determined) — plus
``no_shared_fallbacks`` for "fallbacks exist and none shares the primary's
provider", which the boolean also could not express.  The legacy
``fallbacks_share_primary_upstream`` boolean is still emitted for anything
that parses it.

Shared OpenRouter routing is a **common gateway dependency**: observing a
429 through that gateway does NOT prove every downstream route was
affected.  A fallback sharing a gateway is not independent capacity, and a
429 observed on one route through that gateway is not evidence about the
other routes behind it.

Read-only?
----------

**This harness is NOT read-only, and the first version's "nothing here
writes to the database" claim was wrong.**  Grepping the call graph of what
it calls:

* ``generate_response`` -> ``_record_outcome_feedback``
  (``core/llm/byok_handler.py:3538``) -> ``LearningBasedRouter.record_feedback``
  (``core/learning_llm_router.py:1515``) -> ``_persist_feedback``
  (``core/learning_llm_router.py:1642``) -> ``INSERT INTO
  llm_routing_feedback``.  This is **production learning history**, and
  observation is explicitly **not** gated: ``get_learning_router_instance(
  observe_only=True)`` bypasses the ``ATOM_LEARNING_ROUTER`` flag, so rows
  accrue even with the flag off.  ``stream_completion`` has the same hook
  (``byok_handler.py:5742`` success / ``5811`` failure).
* ``_record_outcome_feedback`` -> ``record_stage_outcome`` writes
  ``llm_stage_router_audit`` when a stage-decision carrier is active (this
  harness never sets one).
* ``_track_rate_usage`` -> ``RateUsagePersistence.record`` inserts
  ``rate_usage_records`` rows for providers with custom RPM/TPM limits.
* ``_track_llm_call`` -> in-process ring buffer + Prometheus counters only.
* ``agent_executions`` is written only when the caller passes ``db=`` and
  ``agent_id`` with governance enabled; this harness passes neither.

To keep benchmark traffic out of those stores the harness installs no-op
shims over ``BYOKHandler._record_outcome_feedback`` **and**
``rate_tracker.record_usage`` on its own handler instance for live runs
(``--allow-learning-writes`` disables them), and counts
``llm_routing_feedback`` / ``rate_usage_records`` /
``llm_stage_router_audit`` rows before and after when ``--db`` is given —
so the claim is CHECKED rather than asserted.  The in-process
``llm_call_tracker`` is deliberately left on: the harness reads it back to
learn which ``(provider, model)`` pair actually served each attempt.

Usage::

    ./venv/bin/python scripts/provider_reliability_replay.py --topology-only
    ./venv/bin/python scripts/provider_reliability_replay.py --budget-calls 3
    ./venv/bin/python scripts/provider_reliability_replay.py --fallback-independence
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===========================================================================
# 1. Answer contracts
# ===========================================================================

STATUS_SATISFIED = "satisfied"
STATUS_VIOLATED = "violated"
STATUS_UNSUPPORTED = "unsupported_by_fixture"

NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_MISSING_PROVIDER = {"", "?", "unknown", "unresolved", "none", "null"}


@dataclass(frozen=True)
class ContractResult:
    """Outcome of checking one reply against one contract."""

    status: str
    detail: str
    supported: bool

    @property
    def satisfied(self) -> Optional[bool]:
        """True/False when checkable, None when the fixture cannot support it."""
        if self.status == STATUS_UNSUPPORTED:
            return None
        return self.status == STATUS_SATISFIED


@dataclass(frozen=True)
class AnswerContract:
    """A checkable expectation about a reply.

    ``kind`` is one of ``sentinel_token`` (the reply must contain the token
    as a word), ``number`` (the reply must contain the expected numeric
    value, optionally alongside a row token), or ``unsupported_by_fixture``
    (the harness states that the fixture cannot justify any expectation, so
    the probe is excluded from the contract pass rate).
    """

    kind: str
    token: Optional[str] = None
    number: Optional[float] = None
    row_token: Optional[str] = None
    single_word: bool = False
    unsupported_reason: Optional[str] = None

    def describe(self) -> str:
        if self.kind == "sentinel_token":
            extra = " (must be the only content)" if self.single_word else ""
            return f"reply contains the sentinel token {self.token!r}{extra}"
        if self.kind == "number":
            expect = f"reply states the value {self.number:g}"
            if self.row_token:
                expect += f" and cites {self.row_token}"
            return expect
        if self.kind == "unsupported_by_fixture":
            return f"unsupported_by_fixture: {self.unsupported_reason}"
        return f"unknown contract kind {self.kind!r}"

    def check(self, reply: Optional[str]) -> ContractResult:
        if self.kind == "unsupported_by_fixture":
            return ContractResult(
                STATUS_UNSUPPORTED,
                self.unsupported_reason or "fixture cannot support this expectation",
                supported=False,
            )
        text = (reply or "").strip()
        if not text:
            return ContractResult(STATUS_VIOLATED, "empty reply", supported=True)
        if self.kind == "sentinel_token":
            found = re.search(rf"\b{re.escape(str(self.token))}\b", text, re.IGNORECASE)
            if not found:
                return ContractResult(
                    STATUS_VIOLATED,
                    f"sentinel token {self.token!r} absent from reply",
                    supported=True,
                )
            if self.single_word and _words(text) != [str(self.token).lower()]:
                return ContractResult(
                    STATUS_SATISFIED,
                    f"sentinel {self.token!r} present but reply was not the sole content",
                    supported=True,
                )
            return ContractResult(
                STATUS_SATISFIED, f"sentinel token {self.token!r} present", supported=True
            )
        if self.kind == "number":
            observed = parse_numbers(text)
            if not any(abs(v - float(self.number)) <= 0.01 for v in observed):
                return ContractResult(
                    STATUS_VIOLATED,
                    f"expected {self.number:g}; observed numbers "
                    f"{observed[:6] if observed else 'none'}",
                    supported=True,
                )
            if self.row_token and not re.search(
                rf"\b{re.escape(self.row_token)}\b", text, re.IGNORECASE
            ):
                return ContractResult(
                    STATUS_VIOLATED,
                    f"value {self.number:g} present but row token "
                    f"{self.row_token!r} is not cited",
                    supported=True,
                )
            return ContractResult(
                STATUS_SATISFIED, f"value {self.number:g} present", supported=True
            )
        return ContractResult(
            STATUS_VIOLATED, f"unknown contract kind {self.kind!r}", supported=True
        )


def _words(text: str) -> List[str]:
    return [w for w in re.split(r"[^0-9A-Za-z_]+", text.lower()) if w]


def parse_numbers(text: str) -> List[float]:
    """Numbers appearing in ``text``, tolerant of thousands separators."""
    out: List[float] = []
    for raw in NUMBER_RE.findall(text or ""):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:  # pragma: no cover - regex guarantees numeric
            continue
    return out


# ===========================================================================
# 2. Workload + fixtures
# ===========================================================================

_SMALL = "Reply with the single word: ok"

_MEDIUM = (
    "From the evidence below, state the list price of the F-5216 in one "
    "sentence and cite the row.\n\nEVIDENCE:\n"
    + "\n".join(
        f"- [ingested mailbox] msg-{i}: quote line for machine {i} "
        f"| list={5000 + i} | full: knowledge/conversations/m{i}"
        for i in range(40))
)

_LARGE_EVIDENCE = (
    "From the evidence below, state the list price of the F-5216 and the "
    "formula chain that derives it, in under 40 words.\n\nEVIDENCE:\n"
    + "\n".join(
        f"- [ingested mailbox] msg-{i}: forwarded price list {i} "
        + "x" * 260 + f" | full: knowledge/conversations/m{i}"
        for i in range(60))
    + "\nR235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
      "Factory Price=5350 | $7,519.00\n"
      "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | I235==H235+700"
)

MEDIUM_FIXTURE_LIMITATION = (
    "medium fixture: its 40 rows bind every value to 'machine <i>' "
    "(e.g. 'quote line for machine 7 | list=5007'); no row carries or links "
    "the identifier 'F-5216' (fixture-wide regex hits for F-5216: 0). An "
    "expected list price for the F-5216 is therefore NOT justified by this "
    "fixture — the probe's contract is unsupported_by_fixture and it is "
    "excluded from the contract pass rate (it still counts in the transport "
    "denominators)."
)

LARGE_FIXTURE_LIMITATION = (
    "large fixture: row R235 does state 'LIST Price=7519.0' (and "
    "'$7,519.00'), so the list-price expectation IS checkable and is checked. "
    "Its formula string 'G235==F235*0.9 | I235==H235+700' is NOT checkable: "
    "the fixture never defines F235 or H235, and 5350*0.9=4815 != 7519, so "
    "'the formula chain that derives it' is unsupported_by_fixture and is "
    "excluded from the contract pass rate rather than counted either way."
)


@dataclass(frozen=True)
class Probe:
    """One workload probe: prompt + the contract its answer must satisfy."""

    name: str
    kind: str
    prompt: str
    contract: AnswerContract
    unsupported_expectations: Tuple[str, ...] = ()
    limitation: Optional[str] = None


def build_workload() -> List[Probe]:
    """The representative workload, with explicit answer contracts."""
    return [
        Probe(
            name="planning_short",
            kind="planning",
            prompt=_SMALL,
            contract=AnswerContract(kind="sentinel_token", token="ok", single_word=True),
        ),
        Probe(
            name="grounded_medium",
            kind="grounded",
            prompt=_MEDIUM,
            contract=AnswerContract(
                kind="unsupported_by_fixture",
                unsupported_reason=(
                    "the medium fixture never links its rows to the identifier "
                    "F-5216, so no list price for it can be verified"
                ),
            ),
            unsupported_expectations=("list_price_of_F-5216",),
            limitation=MEDIUM_FIXTURE_LIMITATION,
        ),
        Probe(
            name="derivation_large",
            kind="grounded",
            prompt=_LARGE_EVIDENCE,
            contract=AnswerContract(kind="number", number=7519.0, row_token="R235"),
            unsupported_expectations=("formula_chain_derives_7519",),
            limitation=LARGE_FIXTURE_LIMITATION,
        ),
    ]


WORKLOAD: List[Tuple[str, str, str]] = [(p.name, p.kind, p.prompt) for p in build_workload()]


# ===========================================================================
# 3. Transport classification
# ===========================================================================

_RATE_LIMIT_RE = re.compile(
    r"(429|rate.?limit|too many requests|quota|insufficient balance|"
    r"credits?|capacity)", re.IGNORECASE)
_BUDGET_RE = re.compile(
    r"(budget|turn.?budget|deadline|cancell?ed)", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"(timeout|timed out|deadline exceeded)", re.IGNORECASE)

#: Phrases that make a reply an obvious non-answer. Contract checks already
#: catch these for checkable probes; the label is kept for reporting.
_NON_ANSWER_RE = re.compile(
    r"(i'?m sorry|i am sorry|i can'?t|i cannot|unable to|as an ai|"
    r"please check your api key|an error occurred while generating)",
    re.IGNORECASE)


def classify(error: Optional[Dict[str, Any]], content: Optional[str]) -> str:
    """One TRANSPORT outcome per attempt (contract satisfaction is separate)."""
    if error:
        blob = f"{error.get('type', '')} {error.get('message', '')} {error.get('status', '')}"
        if _RATE_LIMIT_RE.search(blob):
            return "rate_limited"
        if _BUDGET_RE.search(blob):
            return "budget_exceeded"
        if _TIMEOUT_RE.search(blob):
            return "timeout"
        return "provider_error"
    if not (content or "").strip():
        return "zero_output"
    return "ok"


def error_info(exc: BaseException) -> Dict[str, Any]:
    """Structured error: type, message and HTTP status when the SDK exposes it."""
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    return {
        "type": type(exc).__name__,
        "message": str(exc)[:400],
        "status": status,
    }


def looks_like_non_answer(reply: Optional[str]) -> bool:
    return bool(_NON_ANSWER_RE.search(reply or ""))


def transport_outcome(
    error: Optional[Dict[str, Any]],
    content: Optional[str],
    observed_attempts: Sequence[Dict[str, Any]],
) -> Tuple[str, bool]:
    """(outcome, every_observed_attempt_failed).

    ``stream_completion`` and ``generate_response`` yield user-facing text
    ("I'm sorry, ...") even when every provider attempt failed, so non-empty
    output alone is not transport success.  When the production call tracker
    shows that every observed provider attempt failed, the attempt is a
    ``provider_error`` whatever text came back.
    """
    all_failed = bool(observed_attempts) and not any(
        rec.get("success") for rec in observed_attempts
    )
    if error:
        return classify(error, content), all_failed
    if all_failed:
        return "provider_error", True
    return classify(None, content), False


# ===========================================================================
# 4. Topology (four required states + the fully-independent case)
# ===========================================================================

STATE_SOME_SHARED = "some_shared_fallbacks"
STATE_ALL_SHARED = "all_shared_fallbacks"
STATE_NO_SHARED = "no_shared_fallbacks"
STATE_NO_FALLBACK = "no_fallback"
STATE_UNKNOWN = "unknown_topology"

#: The four states the review requires, plus ``no_shared_fallbacks`` for the
#: "fallbacks exist and none shares the primary's provider" case — which the
#: old boolean also could not express.
TOPOLOGY_STATES = (
    STATE_SOME_SHARED,
    STATE_ALL_SHARED,
    STATE_NO_SHARED,
    STATE_NO_FALLBACK,
    STATE_UNKNOWN,
)

TOPOLOGY_STATE_MEANING = {
    STATE_SOME_SHARED: (
        "at least one fallback shares the primary's upstream provider, but "
        "not all of them"
    ),
    STATE_ALL_SHARED: (
        "every fallback shares the primary's upstream provider — the ladder "
        "adds no provider diversity for the top candidate"
    ),
    STATE_NO_SHARED: (
        "fallbacks exist and none shares the primary's upstream provider"
    ),
    STATE_NO_FALLBACK: "no fallback is configured below the primary",
    STATE_UNKNOWN: (
        "the primary or at least one fallback has no resolvable provider, so "
        "shared-upstream ownership could not be determined"
    ),
}


def classify_fallback_topology(
    primary: Optional[Tuple[Optional[str], Optional[str]]],
    fallback_pairs: Sequence[Tuple[Optional[str], Optional[str]]],
) -> Dict[str, Any]:
    """Classify the ladder's provider-sharing topology.

    Preserves ``(provider, model)`` pairs: a fallback that resolves to an
    unknown provider makes the whole classification ``unknown_topology``
    rather than being silently treated as independent.
    """
    fb = [tuple(p) for p in (fallback_pairs or [])]
    primary_provider = primary[0] if primary else None
    unresolved = sorted(
        {str(p) for p, _m in fb if not p or str(p).lower() in _MISSING_PROVIDER}
    )
    if not primary_provider or str(primary_provider).lower() in _MISSING_PROVIDER:
        state = STATE_UNKNOWN
    elif not fb:
        state = STATE_NO_FALLBACK
    elif unresolved:
        state = STATE_UNKNOWN
    else:
        shared = [p for p, _m in fb if p == primary_provider]
        if len(shared) == len(fb):
            state = STATE_ALL_SHARED
        elif shared:
            state = STATE_SOME_SHARED
        else:
            state = STATE_NO_SHARED
    shared_providers = sorted(
        {str(p) for p, _m in fb if p and p == primary_provider}
    )
    return {
        "state": state,
        "state_meaning": TOPOLOGY_STATE_MEANING[state],
        "primary": {"provider": primary_provider, "model": primary[1] if primary else None},
        "fallback_count": len(fb),
        "fallback_pairs": [{"provider": p, "model": m} for p, m in fb],
        "shared_providers": shared_providers,
        "unresolved_fallback_providers": unresolved,
        # Legacy key kept for anything that already parses it.
        "fallbacks_sharing_primary_upstream": shared_providers,
        "fallbacks_share_primary_upstream": bool(shared_providers),
    }


def resolve_fallback_pairs(
    fallback_names: Sequence[str],
    ranked_pairs: Sequence[Tuple[str, str]],
) -> Tuple[List[Tuple[str, str]], List[str], Dict[str, List[str]]]:
    """Re-attach a provider to fallback model NAMES taken from the ladder.

    ``get_fallback_models`` drops the provider.  Resolving each name against
    the ranked ``(provider, model)`` list restores it; a name served by more
    than one gateway is reported as AMBIGUOUS (and treated as an unknown
    provider rather than guessed at), and a name with no ladder entry becomes
    ``unknown`` so the topology is classified ``unknown_topology`` instead of
    being silently assumed independent.
    """
    providers_by_model: Dict[str, List[str]] = defaultdict(list)
    for provider, model in ranked_pairs:
        providers_by_model[model].append(provider)
    pairs: List[Tuple[str, str]] = []
    unresolved: List[str] = []
    ambiguous: Dict[str, List[str]] = {}
    for name in fallback_names:
        providers = sorted(set(providers_by_model.get(name) or []))
        if not providers:
            unresolved.append(name)
            pairs.append(("unknown", name))
        elif len(providers) > 1:
            ambiguous[name] = providers
            pairs.append(("unknown", name))
        else:
            pairs.append((providers[0], name))
    return pairs, unresolved, ambiguous


async def topology(
    complexity_name: str = "SIMPLE", fallback_limit: int = 3
) -> Dict[str, Any]:
    """Live candidate ladder + fallback list, read-only (no generation)."""
    from core.llm.byok_handler import BYOKHandler, QueryComplexity

    h = BYOKHandler(tenant_id="default")
    complexity = getattr(QueryComplexity, complexity_name)
    ranked = [(p, m) for (p, m) in (h.get_ranked_providers(complexity) or [])]

    primary = ranked[0] if ranked else (None, None)
    fallback_names = (
        h.get_fallback_models(complexity, primary[1], limit=fallback_limit)
        if ranked else []
    )
    fb_pairs, unresolved_fallback_models, ambiguous_fallback_models = (
        resolve_fallback_pairs(fallback_names, ranked)
    )

    topo = classify_fallback_topology(primary, fb_pairs)
    topo.update({
        "ranked_candidates": [{"provider": p, "model": m} for p, m in ranked],
        "ranked_count": len(ranked),
        "providers_in_ladder": dict(Counter(p for p, _m in ranked)),
        "primary": {"provider": primary[0], "model": primary[1]},
        "complexity": complexity_name,
        # ``get_fallback_models`` is a NAME-keyed production API: it returns
        # model names and drops the provider.  The names are re-resolved
        # against the ranked (provider, model) list here, and any ambiguity
        # is reported instead of hidden.
        "fallback_models": list(fallback_names),
        "fallback_pair_source": (
            "get_fallback_models() returns model NAMES only; each name was "
            "re-resolved against the ranked (provider, model) ladder"
        ),
        "unresolved_fallback_models": unresolved_fallback_models,
        "ambiguous_fallback_models": ambiguous_fallback_models,
        "name_keyed_lookups_in_production": [
            "BYOKHandler.get_fallback_models -> List[str] (provider dropped)",
            "BYOKHandler.stream_completion(fallback_models=[name, ...]) recurses "
            "with the caller's provider_id for a name from another ladder pair",
            "DynamicPricingFetcher.get_model_price(model_name) / "
            "LLMService.estimate_cost(..., model) key price on model name alone",
        ],
    })
    return topo


# ===========================================================================
# 5. Caps
# ===========================================================================


@dataclass
class SpendLedger:
    """Retry and spend caps enforced inside the loop.

    ``spend_cap_usd`` is charged with the provider-reported cost when there
    is one and with the harness estimate otherwise; how much of the charged
    total came from estimates is reported so the cap's strength is visible.
    """

    retry_cap: int = 1
    spend_cap_usd: float = 0.05
    attempts: int = 0
    retries_used: int = 0
    cost_reported_total: float = 0.0
    cost_estimated_total: float = 0.0
    charged_total: float = 0.0
    charged_from_estimate: float = 0.0
    cost_unknown_attempts: int = 0
    blocked_by_retry_cap: int = 0
    blocked_by_spend_cap: int = 0

    def note_attempt(
        self,
        cost: Optional[float],
        cost_estimate: Optional[float],
        is_retry: bool,
    ) -> None:
        self.attempts += 1
        if is_retry:
            self.retries_used += 1
        if cost is not None:
            self.cost_reported_total += float(cost)
            self.charged_total += float(cost)
        else:
            self.cost_unknown_attempts += 1
            if cost_estimate is not None:
                self.cost_estimated_total += float(cost_estimate)
                self.charged_total += float(cost_estimate)
                self.charged_from_estimate += float(cost_estimate)

    def blocked_reason(
        self, *, retry: bool, retries_this_generation: int = 0
    ) -> Optional[str]:
        """Why the next attempt must not run, or None when it may.

        ``--retry-cap`` is per generation (per probe): a retry is refused once
        ``retries_this_generation`` reaches it.  ``retries_used`` stays a
        run-wide counter for reporting.
        """
        if retry and retries_this_generation >= self.retry_cap:
            self.blocked_by_retry_cap += 1
            return "retry_cap"
        if self.charged_total >= self.spend_cap_usd:
            self.blocked_by_spend_cap += 1
            return "spend_cap"
        return None

    def to_dict(self, budget_calls: int) -> Dict[str, Any]:
        return {
            "effective_caps": {
                "budget_calls": budget_calls,
                "retry_cap": self.retry_cap,
                "spend_cap_usd": self.spend_cap_usd,
            },
            "attempts": self.attempts,
            "retries_used": self.retries_used,
            "cost_reported_total": round(self.cost_reported_total, 8),
            "cost_estimated_total": round(self.cost_estimated_total, 8),
            "charged_total": round(self.charged_total, 8),
            "charged_from_estimate": round(self.charged_from_estimate, 8),
            "cost_unknown_attempts": self.cost_unknown_attempts,
            "blocked_by_retry_cap": self.blocked_by_retry_cap,
            "blocked_by_spend_cap": self.blocked_by_spend_cap,
            "retry_cap_scope": "per generation (probe), checked when a retry "
                               "would otherwise be scheduled",
            "spend_cap_basis": (
                "provider-reported cost when present, else the harness "
                "estimate; an attempt with neither cannot be charged"
            ),
        }


# ===========================================================================
# 6. Stream helpers
# ===========================================================================


def delta_text(chunk: Any) -> str:
    """Visible content carried by one streamed chunk ("" when there is none).

    Accepts the handler's raw string tokens and OpenAI-style chunk dicts or
    objects (``choices[0].delta.content``).  Role-only deltas, empty strings
    and whitespace-only deltas yield "" so they never stamp first-visible.
    """
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
    else:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return ""
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return ""
        content = getattr(delta, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
            else:
                parts.append(str(getattr(part, "text", "") or ""))
        return "".join(parts)
    return str(content)


def first_visible_index(deltas: Sequence[Any]) -> Optional[int]:
    """Index of the first chunk carrying non-empty content, or None."""
    for i, chunk in enumerate(deltas):
        if delta_text(chunk).strip():
            return i
    return None


def streamed_text(deltas: Iterable[Any]) -> str:
    return "".join(delta_text(c) for c in deltas)


def rate(numerator: int, denominator: int) -> Dict[str, Any]:
    """A rate that always carries its denominator; None when it has none."""
    if denominator and denominator > 0:
        return {
            "pct": round(100.0 * numerator / denominator, 1),
            "numerator": numerator,
            "denominator": denominator,
        }
    return {"pct": None, "numerator": numerator, "denominator": denominator,
            "note": "undefined: zero denominator"}


def _fmt_rate(r: Optional[Dict[str, Any]]) -> str:
    if not r or not r.get("denominator"):
        return "n/a (no denominator)"
    if r.get("pct") is None:  # pragma: no cover - defensive
        return "n/a"
    return f"{r['pct']}% ({r['numerator']}/{r['denominator']})"


# ===========================================================================
# 7. Live plumbing
# ===========================================================================


def tracker_len() -> int:
    try:
        from core.llm_call_tracker import get_llm_call_tracker

        return len(get_llm_call_tracker())
    except Exception:
        return 0


def tracker_since(before: int) -> List[Dict[str, Any]]:
    """Per-attempt records the production call tracker added since ``before``."""
    try:
        from core.llm_call_tracker import get_llm_call_tracker

        tracker = get_llm_call_tracker()
        total = len(tracker)
        new_count = max(0, total - before)
        if not new_count:
            return []
        recent = tracker.get_recent_calls(limit=max(1, new_count))  # newest first
        ordered = list(reversed(recent))[:new_count]
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "success": bool(r.success),
                "latency_ms": round(float(r.latency_ms or 0.0), 1),
                "output_chunks": int(r.output_tokens or 0),
                "input_tokens": int(r.input_tokens or 0),
                "fallback": bool(r.fallback),
                "fallback_provider": r.fallback_provider,
                "error": r.error,
            }
            for r in ordered
        ]
    except Exception:
        return []


def install_read_only_guard(handler: Any) -> Dict[str, Any]:
    """Keep this harness's own traffic out of the app's persisted stores.

    Two indirect writes are reachable from a generation and both are shimmed
    **on this process's handler instance only** (the generation path itself is
    untouched):

    * ``_record_outcome_feedback`` -> ``LearningBasedRouter.record_feedback``
      -> ``_persist_feedback`` -> ``INSERT INTO llm_routing_feedback``.
      Observation is NOT gated by ``ATOM_LEARNING_ROUTER``
      (``get_learning_router_instance(observe_only=True)`` bypasses the gate),
      so benchmark traffic would otherwise land in production learning
      history.
    * ``rate_tracker.record_usage`` -> ``RateUsagePersistence.record`` ->
      ``INSERT INTO rate_usage_records`` for providers with custom RPM/TPM
      limits.  Those rows feed the monthly-allowance routing headroom, so
      synthetic usage is not harmless either.

    Everything else the generation path records (the in-process
    ``llm_call_tracker`` ring buffer and Prometheus counters) is memory-only
    and is deliberately LEFT ON: the harness reads it back to learn which
    ``(provider, model)`` pair actually served each attempt.
    """
    state: Dict[str, Any] = {
        "installed": False,
        "error": None,
        "learning_feedback_calls_suppressed": 0,
        "rate_usage_calls_suppressed": 0,
    }
    try:
        original = handler._record_outcome_feedback  # type: ignore[attr-defined]

        async def _noop(*args: Any, **kwargs: Any) -> None:
            state["learning_feedback_calls_suppressed"] += 1
            return None

        handler._record_outcome_feedback = _noop  # type: ignore[assignment]
        state["original_learning_hook"] = getattr(
            original, "__qualname__", str(original)
        )
        state["installed"] = True
    except Exception as exc:  # pragma: no cover - defensive
        state["error"] = error_info(exc)

    try:
        tracker = getattr(handler, "rate_tracker", None)
        if tracker is not None:
            original_usage = tracker.record_usage

            def _noop_usage(*args: Any, **kwargs: Any) -> None:
                state["rate_usage_calls_suppressed"] += 1
                return None

            tracker.record_usage = _noop_usage  # type: ignore[assignment]
            state["rate_usage_guard_installed"] = True
            state["original_rate_usage_hook"] = getattr(
                original_usage, "__qualname__", str(original_usage)
            )
        else:
            state["rate_usage_guard_installed"] = False
    except Exception as exc:  # pragma: no cover - defensive
        state["rate_usage_guard_error"] = error_info(exc)
        state["rate_usage_guard_installed"] = False

    return state


# Backwards-compatible alias (the guard now covers more than learning writes).
suppress_learning_writes = install_read_only_guard


def count_table_rows(db_path: str, table: str) -> Optional[int]:
    """Row count for a SQLite table, read-only; None when unavailable."""
    if not db_path or not os.path.exists(db_path):
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if cur.fetchone() is None:
                return None
            return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            con.close()
    except Exception:
        return None


def learning_history_snapshot(db_path: str) -> Dict[str, Any]:
    return {
        "db": db_path,
        "llm_routing_feedback_rows": count_table_rows(db_path, "llm_routing_feedback"),
        "rate_usage_records_rows": count_table_rows(db_path, "rate_usage_records"),
        "llm_stage_router_audit_rows": count_table_rows(db_path, "llm_stage_router_audit"),
    }


_ESTIMATION_SERVICE: Any = None


def _estimation_service() -> Any:
    """Cached LLMService used only for token/cost estimation."""
    global _ESTIMATION_SERVICE
    if _ESTIMATION_SERVICE is None:
        from core.llm_service import LLMService

        _ESTIMATION_SERVICE = LLMService()
    return _ESTIMATION_SERVICE


def _estimate_tokens(text: str, model: str) -> Tuple[int, bool]:
    """(token_count, estimated). Always an estimate on this path."""
    try:
        return int(_estimation_service().estimate_tokens(text or "", model)), True
    except Exception:
        return max(1, len(text or "") // 4), True


def _estimate_cost(prompt: str, completion: str, model: str) -> Optional[float]:
    """Harness cost estimate — NAME-keyed, hence provider-blind by nature."""
    try:
        svc = _estimation_service()
        p_tokens, _ = _estimate_tokens(prompt, model)
        c_tokens, _ = _estimate_tokens(completion, model)
        return float(svc.estimate_cost(p_tokens, c_tokens, model))
    except Exception:
        return None


def _usage_block(
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    source: str,
) -> Dict[str, Any]:
    total = None
    if prompt_tokens is not None and completion_tokens is not None:
        total = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "source": source,
        "estimated": source != "provider_reported",
    }


# ===========================================================================
# 8. Probes
# ===========================================================================


async def stream_probe(
    handler: Any,
    probe: Probe,
    pair: Tuple[str, str],
    timeout_s: float,
    max_tokens: int,
    fallback_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """One streamed attempt pinned to an explicit ``(provider, model)`` pair."""
    provider, model = pair
    t0 = time.monotonic()
    deltas: List[Any] = []
    first_visible_ms: Optional[float] = None
    error: Optional[Dict[str, Any]] = None
    before = tracker_len()
    agen = None
    try:
        agen = handler.stream_completion(
            messages=[{"role": "user", "content": probe.prompt}],
            model=model,
            provider_id=provider,
            temperature=0.0,
            max_tokens=max_tokens,
            task_type=probe.kind,
            **({"fallback_models": list(fallback_models)} if fallback_models else {}),
        )
        while True:
            try:
                chunk = await asyncio.wait_for(agen.__anext__(), timeout=timeout_s)
            except StopAsyncIteration:
                break
            text = delta_text(chunk)
            if text.strip() and first_visible_ms is None:
                first_visible_ms = round((time.monotonic() - t0) * 1000, 1)
            if text:
                deltas.append(chunk)
    except asyncio.TimeoutError:
        error = {
            "type": "TimeoutError",
            "message": f"no streamed chunk within {timeout_s}s",
            "status": None,
        }
    except Exception as exc:  # noqa: BLE001 - any provider failure is data
        error = error_info(exc)
    finally:
        if agen is not None:
            try:
                await agen.aclose()
            except Exception:
                pass

    total_ms = round((time.monotonic() - t0) * 1000, 1)
    text = streamed_text(deltas)
    observed = tracker_since(before)
    used = None
    for rec in reversed(observed):
        if rec["success"]:
            used = {"provider": rec["provider"], "model": rec["model"]}
            break
    return {
        "mode": "stream",
        "requested": {"provider": provider, "model": model},
        "used": used,
        "observed_attempts": observed,
        "transport_error": error,
        "content": text,
        "first_visible_ms": first_visible_ms,
        "first_visible_measurable": True,
        "completion_ms": total_ms,
        "usage": _usage_block(
            _estimate_tokens(probe.prompt, model)[0],
            _estimate_tokens(text, model)[0] if text else 0,
            "estimated",
        ),
        "output_chars": len(text.strip()),
        "output_chunks": len(deltas),
    }


async def completion_probe(
    svc: Any,
    probe: Probe,
    timeout_s: float,
    max_tokens: int,
) -> Dict[str, Any]:
    """One non-streaming attempt (legacy path).

    First-visible latency is NOT measurable here and is reported as such
    instead of being approximated by completion latency.
    """
    t0 = time.monotonic()
    error: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    used: Optional[Dict[str, Any]] = None
    usage: Dict[str, Any] = _usage_block(None, None, "unavailable")
    cost: Optional[float] = None
    try:
        res = await asyncio.wait_for(
            svc.generate_completion(
                messages=[{"role": "user", "content": probe.prompt}],
                model="auto",
                max_tokens=max_tokens,
                task_type=probe.kind,
            ),
            timeout=timeout_s,
        )
        res = res or {}
        content = res.get("content") or res.get("response")
        used = {"provider": res.get("provider"), "model": res.get("model")}
        raw_usage = res.get("usage") or {}
        if raw_usage:
            usage = _usage_block(
                raw_usage.get("prompt_tokens"),
                raw_usage.get("completion_tokens"),
                "provider_reported",
            )
        cost = res.get("cost")
    except asyncio.TimeoutError:
        error = {
            "type": "TimeoutError",
            "message": f"no completion within {timeout_s}s",
            "status": None,
        }
    except Exception as exc:  # noqa: BLE001
        error = error_info(exc)
    total_ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "mode": "completion",
        "requested": {"provider": "auto", "model": "auto"},
        "used": used,
        "observed_attempts": [],
        "transport_error": error,
        "content": content or "",
        "first_visible_ms": None,
        "first_visible_measurable": False,
        "completion_ms": total_ms,
        "usage": usage,
        "output_chars": len((content or "").strip()),
        "output_chunks": None,
        "reported_cost": cost,
    }


# ===========================================================================
# 9. Replay
# ===========================================================================


async def replay(args: Any) -> Dict[str, Any]:
    """Bounded replay with per-attempt telemetry, contracts and caps."""
    from core.llm.byok_handler import BYOKHandler, QueryComplexity

    handler = BYOKHandler(tenant_id="default")
    ledger = SpendLedger(retry_cap=args.retry_cap, spend_cap_usd=args.spend_cap_usd)
    guard = (
        {"installed": False, "suppressed_calls": 0}
        if args.allow_learning_writes
        else install_read_only_guard(handler)
    )
    svc = None
    if args.mode == "completion":
        from core.llm_service import LLMService

        svc = LLMService()

    probes = build_workload()
    attempts: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    generation_index = 0
    budget_exhausted = False

    for rep in range(max(1, args.repeats)):
        if budget_exhausted:
            break
        for probe in probes:
            if budget_exhausted:
                break
            generation_index += 1
            complexity = handler.analyze_query_complexity(probe.prompt, probe.kind)
            ranked = [(p, m) for (p, m) in (handler.get_ranked_providers(complexity) or [])]
            if not ranked:
                attempts.append({
                    "workload": probe.name,
                    "kind": probe.kind,
                    "generation": generation_index,
                    "repeat": rep,
                    "attempt_index": 0,
                    "retry": False,
                    "retry_index": 0,
                    "requested": {"provider": None, "model": None},
                    "used": None,
                    "outcome": "no_candidate",
                    "transport_ok": False,
                    "error": {"type": "NoCandidate", "message": "empty routing ladder",
                              "status": None},
                    "contract": _contract_record(probe, None),
                    "prompt_chars": len(probe.prompt),
                })
                continue

            retry_index = 0
            while True:
                if ledger.attempts >= args.budget_calls:
                    blocked.append({"workload": probe.name, "reason": "budget_calls"})
                    budget_exhausted = True
                    break
                reason = ledger.blocked_reason(
                    retry=False, retries_this_generation=retry_index
                )
                if reason:
                    blocked.append({"workload": probe.name, "reason": reason,
                                    "retry_index": retry_index})
                    break
                pair = ranked[min(retry_index, len(ranked) - 1)]
                if args.mode == "completion":
                    run = await completion_probe(svc, probe, args.timeout_s, args.max_tokens)
                else:
                    run = await stream_probe(
                        handler, probe, pair, args.timeout_s, args.max_tokens
                    )
                content = run.get("content") or ""
                observed = run.get("observed_attempts") or []
                outcome, all_attempts_failed = transport_outcome(
                    run.get("transport_error"), content, observed
                )
                contract = _contract_record(probe, content)
                used = run.get("used")
                reported_cost = run.get("reported_cost")
                cost_estimate = (
                    None if reported_cost is not None
                    else _estimate_cost(probe.prompt, content, (used or {}).get("model") or pair[1])
                )
                ledger.note_attempt(
                    cost=reported_cost,
                    cost_estimate=cost_estimate,
                    is_retry=retry_index > 0,
                )
                attempts.append({
                    "workload": probe.name,
                    "kind": probe.kind,
                    "generation": generation_index,
                    "repeat": rep,
                    "attempt_index": retry_index,
                    "retry": retry_index > 0,
                    "retry_index": retry_index,
                    "mode": run.get("mode"),
                    "prompt_chars": len(probe.prompt),
                    "requested": run.get("requested"),
                    "used": used,
                    "provider_identity_known": bool(used and used.get("provider")),
                    "observed_attempts": run.get("observed_attempts") or [],
                    "all_provider_attempts_failed": all_attempts_failed,
                    "outcome": outcome,
                    "transport_ok": outcome == "ok",
                    "looks_like_non_answer": looks_like_non_answer(content),
                    "reply_excerpt": (content or "")[:200],
                    "error": run.get("transport_error"),
                    "contract": contract,
                    "first_visible_ms": run.get("first_visible_ms"),
                    "first_visible_measurable": run.get("first_visible_measurable", False),
                    "completion_ms": run.get("completion_ms"),
                    "usage": run.get("usage"),
                    "cost": reported_cost,
                    "cost_unknown": reported_cost is None,
                    "cost_estimate": (
                        round(cost_estimate, 8) if cost_estimate is not None else None
                    ),
                    "cost_estimate_source": (
                        None if cost_estimate is None else
                        "harness estimate (name-keyed pricing; provider-blind)"
                    ),
                    "output_chars": run.get("output_chars"),
                    "output_chunks": run.get("output_chunks"),
                    "blocked_by": None,
                })
                # Retry only when a CHECKABLE contract was violated, or
                # transport failed outright.  An unsupported_by_fixture probe
                # is excluded from the contract rate and must not drive retries.
                needs_retry = outcome != "ok" or contract["satisfied"] is False
                if not needs_retry:
                    break
                retry_index += 1
                # The ledger is the single source of truth for both caps;
                # the retry cap is per generation.
                retry_block = ledger.blocked_reason(
                    retry=True, retries_this_generation=retry_index - 1
                )
                if retry_block:
                    blocked.append({"workload": probe.name, "reason": retry_block,
                                    "retry_index": retry_index})
                    break
    return {
        "attempts": attempts,
        "blocked": blocked,
        "ledger": ledger,
        "read_only_guard": guard,
    }


def _contract_record(probe: Probe, reply: Optional[str]) -> Dict[str, Any]:
    result = probe.contract.check(reply)
    return {
        "status": result.status,
        "satisfied": result.satisfied,
        "supported": result.supported,
        "expectation": probe.contract.describe(),
        "detail": result.detail,
        "unsupported_expectations": list(probe.unsupported_expectations),
    }


# ===========================================================================
# 10. Fallback independence (live)
# ===========================================================================


async def fallback_independence(args: Any) -> Dict[str, Any]:
    """Measure fallback independence at the REQUEST boundary.

    A restored credential proves none of: authentication, request support,
    ladder membership, or that a fallback actually answers.  Every step here
    is recorded as observed, not assumed.
    """
    from core.llm.byok_handler import BYOKHandler, QueryComplexity

    handler = BYOKHandler(tenant_id="default")
    guard = (
        {"installed": False, "suppressed_calls": 0}
        if args.allow_learning_writes
        else install_read_only_guard(handler)
    )
    probe = Probe(
        name="auth_canary",
        kind="planning",
        prompt=_SMALL,
        contract=AnswerContract(kind="sentinel_token", token="ok", single_word=True),
    )

    configured = sorted(handler.get_available_providers() or [])
    ranked = [(p, m) for (p, m) in (handler.get_ranked_providers(QueryComplexity.SIMPLE) or [])]
    first_pair_for: Dict[str, Tuple[str, str]] = {}
    rank_of: Dict[str, int] = {}
    for i, (p, m) in enumerate(ranked):
        first_pair_for.setdefault(p, (p, m))
        rank_of.setdefault(p, i)

    providers: List[Dict[str, Any]] = []
    for provider in configured:
        record: Dict[str, Any] = {
            "provider": provider,
            "key_resolvable": False,
            "key_source": "unresolved",
            "in_routing_ladder": provider in first_pair_for,
            "ladder_rank": rank_of.get(provider),
            "representative_pair": (
                {"provider": first_pair_for[provider][0], "model": first_pair_for[provider][1]}
                if provider in first_pair_for else None
            ),
            "authenticated": None,
            "contract": None,
            "note": None,
        }
        try:
            key = handler.byok_manager.get_api_key(provider)
        except Exception as exc:  # noqa: BLE001
            key = None
            record["note"] = f"key lookup raised {type(exc).__name__}"
        if key:
            record["key_resolvable"] = True
            record["key_source"] = "byok_store_or_env"
        elif provider in configured:
            # A client only exists when a credential resolved at init time.
            record["key_resolvable"] = True
            record["key_source"] = "client_initialized"
        if not record["in_routing_ladder"]:
            record["note"] = (
                "no ladder candidate serves this provider for a SIMPLE request "
                "— it cannot win or be fallen back to, whatever its credential"
            )
        else:
            pair = first_pair_for[provider]
            run = await stream_probe(handler, probe, pair, args.timeout_s, 16)
            contract = _contract_record(probe, run.get("content"))
            record["authenticated"] = bool(contract["satisfied"])
            record["contract"] = contract
            record["used"] = run.get("used")
            record["transport_error"] = run.get("transport_error")
            record["first_visible_ms"] = run.get("first_visible_ms")
        providers.append(record)

    # ---- controlled primary failure -------------------------------------
    primary = ranked[0] if ranked else (None, None)
    forced_provider = args.force_primary_provider or primary[0]
    forced_model = args.force_primary_model or "__atom_reliability_invalid_model__"
    fallback_names: List[str] = []
    for _p, _m in ranked[1:]:
        if _m and _m != forced_model and _m not in fallback_names:
            fallback_names.append(_m)
        if len(fallback_names) >= max(0, args.fallback_limit):
            break
    failure_probe = Probe(
        name="forced_primary_failure",
        kind="planning",
        prompt=_SMALL,
        contract=AnswerContract(kind="sentinel_token", token="ok", single_word=True),
    )
    exercise: Dict[str, Any] = {
        "forced_primary": {"provider": forced_provider, "model": forced_model},
        "fallback_models_requested": fallback_names,
        "fallback_pair_source": (
            "stream_completion(fallback_models=[...]) is NAME-keyed: the "
            "production fallback recursion keeps the caller's provider_id for "
            "a name taken from another ranked (provider, model) pair"
        ),
        "primary_failure_observed": False,
        "fallback_answered": False,
        "answered_by": None,
        "contract": None,
        "attempt_sequence": [],
        "error": None,
        "skipped": None,
    }
    if not forced_provider:
        exercise["skipped"] = "no ladder primary to force a failure against"
    else:
        run = await stream_probe(
            handler,
            failure_probe,
            (forced_provider, forced_model),
            args.timeout_s,
            16,
            fallback_models=fallback_names,
        )
        sequence = run.get("observed_attempts") or []
        exercise["attempt_sequence"] = sequence
        exercise["primary_failure_observed"] = any(
            (not rec["success"]) and rec["model"] == forced_model for rec in sequence
        )
        content = run.get("content") or ""
        contract = _contract_record(failure_probe, content)
        exercise["contract"] = contract
        exercise["transport_error"] = run.get("transport_error")
        answered = [
            rec for rec in sequence
            if rec["success"] and rec["model"] != forced_model
        ]
        exercise["fallback_answered"] = bool(answered and contract["satisfied"])
        if answered:
            last = answered[-1]
            exercise["answered_by"] = {
                "provider": last["provider"],
                "model": last["model"],
                "fallback": last["fallback"],
                "fallback_provider": last["fallback_provider"],
            }
        exercise["note"] = (
            "a 429 or error observed through a shared gateway dependency "
            "(e.g. OpenRouter) does NOT prove every downstream route behind "
            "that gateway was affected"
        )

    return {
        "configured_providers": configured,
        "providers_in_ladder": sorted(first_pair_for),
        "ladder_size": len(ranked),
        "primary": {"provider": primary[0], "model": primary[1]},
        "provider_checks": providers,
        "controlled_primary_failure": exercise,
        "read_only_guard": guard,
    }


# ===========================================================================
# 11. Summary
# ===========================================================================


def summarize(
    attempts: List[Dict[str, Any]],
    ledger: SpendLedger,
    budget_calls: int,
    blocked: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    by_outcome: Counter = Counter()
    by_size: Dict[str, Counter] = defaultdict(Counter)
    by_pair: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"attempts": 0, "transport_ok": 0, "contract_checked": 0,
                 "contract_satisfied": 0, "cost_reported": 0.0, "cost_unknown": 0,
                 "first_visible_ms": [], "completion_ms": []})

    generations: set = set()
    pairs_seen: set = set()
    contract_checked = 0
    contract_satisfied = 0
    unsupported = 0
    non_answer = 0
    all_attempts_failed = 0
    cost_estimate_missing = 0
    first_visible_values: List[float] = []
    first_visible_from_failed = 0
    completion_values: List[float] = []
    prompt_tokens = completion_tokens = 0
    prompt_tokens_known = completion_tokens_known = 0
    reported_cost_total = 0.0
    estimated_cost_total = 0.0
    cost_unknown_attempts = 0

    for a in attempts:
        outcome = a.get("outcome", "unknown")
        by_outcome[outcome] += 1
        size = ("small" if a.get("prompt_chars", 0) < 1000
                else "medium" if a.get("prompt_chars", 0) < 12000 else "large")
        by_size[size][outcome] += 1
        used = a.get("used") or {}
        key = f"{used.get('provider') or 'unknown'}/{used.get('model') or 'unknown'}"
        bucket = by_pair[key]
        bucket["attempts"] += 1
        if outcome == "ok":
            bucket["transport_ok"] += 1
        if a.get("looks_like_non_answer"):
            non_answer += 1
        if a.get("all_provider_attempts_failed"):
            all_attempts_failed += 1
        contract = a.get("contract") or {}
        if contract.get("status") == STATUS_UNSUPPORTED:
            unsupported += 1
        elif contract.get("satisfied") is not None:
            contract_checked += 1
            bucket["contract_checked"] += 1
            if contract.get("satisfied"):
                contract_satisfied += 1
                bucket["contract_satisfied"] += 1
        if a.get("first_visible_ms") is not None:
            first_visible_values.append(float(a["first_visible_ms"]))
            bucket["first_visible_ms"].append(float(a["first_visible_ms"]))
            if a.get("all_provider_attempts_failed"):
                # The handler yields user-facing error text, which stamps a
                # first-visible time even though no provider produced output.
                first_visible_from_failed += 1
        if a.get("completion_ms") is not None:
            completion_values.append(float(a["completion_ms"]))
            bucket["completion_ms"].append(float(a["completion_ms"]))
        usage = a.get("usage") or {}
        if usage.get("prompt_tokens") is not None:
            prompt_tokens += int(usage["prompt_tokens"])
            prompt_tokens_known += 1
        if usage.get("completion_tokens") is not None:
            completion_tokens += int(usage["completion_tokens"])
            completion_tokens_known += 1
        if a.get("cost") is not None:
            bucket["cost_reported"] += float(a["cost"])
            reported_cost_total += float(a["cost"])
        else:
            cost_unknown_attempts += 1
            bucket["cost_unknown"] += 1
            if a.get("cost_estimate") is not None:
                estimated_cost_total += float(a["cost_estimate"])
            if not a.get("cost_estimate"):
                # No reported cost AND no usable estimate: the spend cap
                # cannot see this attempt at all.
                cost_estimate_missing += 1
        if used.get("provider") and used.get("model"):
            pairs_seen.add((used["provider"], used["model"]))
        if a.get("generation") is not None:
            generations.add((a.get("workload"), a.get("repeat")))

    for bucket in by_pair.values():
        fv = bucket.pop("first_visible_ms")
        cm = bucket.pop("completion_ms")
        bucket["mean_first_visible_ms"] = round(sum(fv) / len(fv), 1) if fv else None
        bucket["mean_completion_ms"] = round(sum(cm) / len(cm), 1) if cm else None
        bucket["contract_pass_rate"] = rate(bucket["contract_satisfied"],
                                            bucket["contract_checked"])

    total = len(attempts)
    return {
        "denominators": {
            "attempts": total,
            "distinct_generations": len(generations),
            "provider_model_pairs": len(pairs_seen),
            "contract_checked_attempts": contract_checked,
            "unsupported_by_fixture_attempts": unsupported,
        },
        "outcomes": dict(by_outcome),
        "by_prompt_size": {k: dict(v) for k, v in by_size.items()},
        "by_provider_model": dict(by_pair),
        "rates": {
            "transport_success": rate(by_outcome.get("ok", 0), total),
            "zero_output": rate(by_outcome.get("zero_output", 0), total),
            "rate_limited": rate(by_outcome.get("rate_limited", 0), total),
            "contract_pass": rate(contract_satisfied, contract_checked),
            "non_answer_looking_replies": rate(non_answer, total),
            "all_provider_attempts_failed": rate(all_attempts_failed, total),
        },
        # Kept for backward compatibility; None (not 0) when undefined.
        "answer_success_rate_pct": rate(by_outcome.get("ok", 0), total)["pct"],
        "zero_output_rate_pct": rate(by_outcome.get("zero_output", 0), total)["pct"],
        "contract_pass_rate_pct": rate(contract_satisfied, contract_checked)["pct"],
        "latency": {
            "first_visible_ms": {
                "mean": round(sum(first_visible_values) / len(first_visible_values), 1)
                if first_visible_values else None,
                "min": min(first_visible_values) if first_visible_values else None,
                "max": max(first_visible_values) if first_visible_values else None,
                "denominator": len(first_visible_values),
                "from_attempts_where_every_provider_failed": first_visible_from_failed,
                "note": (
                    "stamped on the first streamed chunk with non-empty content; "
                    f"{first_visible_from_failed} of these stamp(s) come from "
                    "attempts where every observed provider attempt failed and "
                    "the text was the handler's own error message, so read the "
                    "distribution together with the transport outcomes"
                    if first_visible_values else
                    "not measured in this mode (no streamed output observed)"
                ),
            },
            "completion_ms": {
                "mean": round(sum(completion_values) / len(completion_values), 1)
                if completion_values else None,
                "max": max(completion_values) if completion_values else None,
                "denominator": len(completion_values),
            },
        },
        "usage": {
            "prompt_tokens_total": prompt_tokens,
            "completion_tokens_total": completion_tokens,
            "prompt_tokens_known_attempts": prompt_tokens_known,
            "completion_tokens_known_attempts": completion_tokens_known,
            "note": (
                "streamed attempts report no provider usage; their token "
                "counts are estimates and are flagged per attempt"
            ),
        },
        "cost": {
            "reported_total": round(reported_cost_total, 8),
            "estimated_total": round(estimated_cost_total, 8),
            "cost_unknown_attempts": cost_unknown_attempts,
            "cost_estimate_missing_attempts": cost_estimate_missing,
            "cost_per_successful_answer": (
                round(reported_cost_total / contract_satisfied, 8)
                if contract_satisfied and reported_cost_total else None
            ),
            "cost_per_successful_answer_denominator": contract_satisfied,
            "note": (
                "no provider-reported cost on this path: every attempt is "
                "flagged cost_unknown and the estimated total is a harness "
                "estimate from name-keyed pricing (provider-blind)"
            ),
        },
        "caps": ledger.to_dict(budget_calls),
        "blocked": blocked or [],
    }


def fixture_limitations() -> List[str]:
    return [p.limitation for p in build_workload() if p.limitation]


# ===========================================================================
# 12. Rendering
# ===========================================================================


def render_markdown(rep: Dict[str, Any]) -> str:
    s = rep.get("summary") or {}
    topo = rep.get("topology") or {}
    rates = s.get("rates") or {}
    lines = [
        "# Provider reliability — bounded replay",
        "",
        f"_Generated {rep['generated_at']} · mode `{rep.get('mode')}` · "
        f"budget {rep['budget_calls']} calls · executed {rep['executed_calls']}._",
        "",
        "## 1. What this run measured",
        "",
        f"- Attempts: **{s.get('denominators', {}).get('attempts', 0)}** · "
        f"distinct generations: **{s.get('denominators', {}).get('distinct_generations', 0)}** · "
        f"distinct `(provider, model)` pairs: "
        f"**{s.get('denominators', {}).get('provider_model_pairs', 0)}**",
        f"- Effective caps: `{s.get('caps', {}).get('effective_caps')}` "
        f"(retries used: {s.get('caps', {}).get('retries_used')}, "
        f"blocked: {s.get('caps', {}).get('blocked_by_retry_cap')} by retry cap, "
        f"{s.get('caps', {}).get('blocked_by_spend_cap')} by spend cap)",
        f"- Transport success: **{_fmt_rate(rates.get('transport_success'))}** · "
        f"contract pass: **{_fmt_rate(rates.get('contract_pass'))}** "
        f"(denominator excludes `unsupported_by_fixture` attempts)",
        f"- Zero output: {_fmt_rate(rates.get('zero_output'))} · "
        f"rate limited: {_fmt_rate(rates.get('rate_limited'))} · "
        f"every provider attempt failed: "
        f"{_fmt_rate(rates.get('all_provider_attempts_failed'))}",
        f"- Non-answer-looking replies (apology/refusal phrases): "
        f"{_fmt_rate(rates.get('non_answer_looking_replies'))}",
        "",
        "## 2. Answer contracts (per probe)",
        "",
        "| probe | contract | supported by fixture | unsupported expectations |",
        "|---|---|---|---|",
    ]
    for p in build_workload():
        lines.append(
            f"| `{p.name}` | {p.contract.describe()} | "
            f"{'no' if p.contract.kind == STATUS_UNSUPPORTED else 'yes'} | "
            f"{', '.join(p.unsupported_expectations) or '—'} |"
        )
    lines += ["", "## 3. Fixture limitations", ""]
    for lim in fixture_limitations():
        lines.append(f"- {lim}")
    lines += [
        "",
        "## 4. Observed outcomes by transport",
        "",
        "| outcome | attempts |",
        "|---|---|",
    ]
    for k, v in sorted((s.get("outcomes") or {}).items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "### By prompt size", "", "| tier | outcomes |", "|---|---|"]
    for tier, outcomes in sorted((s.get("by_prompt_size") or {}).items()):
        lines.append(f"| {tier} | {outcomes} |")
    lines += [
        "",
        "## 5. Contract results and per-pair telemetry",
        "",
        "| provider/model | attempts | transport ok | contract pass | "
        "mean first-visible ms | mean completion ms | cost unknown |",
        "|---|---|---|---|---|---|---|",
    ]
    for pair, a in sorted((s.get("by_provider_model") or {}).items(),
                          key=lambda kv: -kv[1]["attempts"]):
        lines.append(
            f"| `{pair}` | {a['attempts']} | {a['transport_ok']} | "
            f"{_fmt_rate(a.get('contract_pass_rate'))} | "
            f"{a.get('mean_first_visible_ms')} | {a.get('mean_completion_ms')} | "
            f"{a.get('cost_unknown')} |"
        )
    lat = s.get("latency") or {}
    fv = lat.get("first_visible_ms") or {}
    cm = lat.get("completion_ms") or {}
    lines += [
        "",
        "## 6. Latency",
        "",
        f"- First visible (streamed): mean {fv.get('mean')} ms / "
        f"min {fv.get('min')} / max {fv.get('max')} over "
        f"**{fv.get('denominator', 0)}** attempts "
        f"(of which {fv.get('from_attempts_where_every_provider_failed', 0)} came "
        f"from an all-providers-failed attempt) — {fv.get('note')}",
        f"- Completion: mean {cm.get('mean')} ms / max {cm.get('max')} over "
        f"**{cm.get('denominator', 0)}** attempts",
        "",
        "## 7. Cost",
        "",
        f"- Provider-reported total: **{s.get('cost', {}).get('reported_total')}** · "
        f"harness-estimated total: **{s.get('cost', {}).get('estimated_total')}** · "
        f"attempts with no reported cost: "
        f"**{s.get('cost', {}).get('cost_unknown_attempts')}** "
        f"(of which no usable estimate: "
        f"{s.get('cost', {}).get('cost_estimate_missing_attempts')} — the spend "
        f"cap cannot see those)",
        f"- Cost per contract-satisfying answer: "
        f"**{s.get('cost', {}).get('cost_per_successful_answer')}** "
        f"(denominator {s.get('cost', {}).get('cost_per_successful_answer_denominator')})",
        f"- {s.get('cost', {}).get('note')}",
        f"- Spend cap basis: {s.get('caps', {}).get('spend_cap_basis')}",
        "",
        "## 8. Fallback topology",
        "",
        f"- Primary: `{topo.get('primary', {}).get('provider')}/"
        f"{topo.get('primary', {}).get('model')}`",
        f"- Ranked candidates: {topo.get('ranked_count')} · providers: "
        f"`{topo.get('providers_in_ladder')}`",
        f"- Fallback models (production API returns NAMES only): "
        f"`{topo.get('fallback_models')}`",
        f"- Fallback `(provider, model)` pairs: `{topo.get('fallback_pairs')}`",
        f"- **Topology state: `{topo.get('state')}`** → "
        f"{topo.get('state_meaning')}",
        f"- Legacy boolean `fallbacks_share_primary_upstream="
        f"{topo.get('fallbacks_share_primary_upstream')}` "
        f"(shared providers: `{topo.get('shared_providers')}`)",
    ]
    if topo.get("unresolved_fallback_models"):
        lines.append(
            f"- ⚠ fallback names with no resolvable provider: "
            f"`{topo.get('unresolved_fallback_models')}`"
        )
    lines += [
        "",
        "> A fallback sharing a gateway (e.g. OpenRouter) is a **common gateway "
        "dependency**, not independent capacity. Observing a 429 through that "
        "gateway does **not** prove every downstream route behind it was "
        "affected — and it does not prove they were healthy either.",
        "",
    ]
    if rep.get("fallback_independence"):
        fi = rep["fallback_independence"]
        lines += [
            "## 9. Fallback independence (request boundary)",
            "",
            "| provider | key resolvable | in ladder (rank) | authenticated "
            "(contract) | representative pair |",
            "|---|---|---|---|---|",
        ]
        for rec in fi.get("provider_checks", []):
            pair = rec.get("representative_pair") or {}
            lines.append(
                f"| `{rec['provider']}` | {rec['key_resolvable']} "
                f"({rec['key_source']}) | {rec['in_routing_ladder']} "
                f"({rec.get('ladder_rank')}) | {rec.get('authenticated')} | "
                f"`{pair.get('provider')}/{pair.get('model')}` |"
            )
        ex = fi.get("controlled_primary_failure", {})
        lines += [
            "",
            f"- Forced primary failure: `{ex.get('forced_primary', {}).get('provider')}/"
            f"{ex.get('forced_primary', {}).get('model')}` · "
            f"primary failure observed: **{ex.get('primary_failure_observed')}**",
            f"- Fallback answered a contract-satisfying reply: "
            f"**{ex.get('fallback_answered')}**"
            + (f" via `{ex.get('answered_by')}`" if ex.get("answered_by") else ""),
            f"- Attempt sequence: `{ex.get('attempt_sequence')}`",
        ]
        if ex.get("skipped"):
            lines.append(f"- Skipped: {ex['skipped']}")
        lines.append("")
    else:
        lines += [
            "## 9. Fallback independence (request boundary)",
            "",
            "_Not run._ Pass `--fallback-independence` to check, against the "
            "live configuration, that each configured provider's key resolves, "
            "that a minimal request authenticates and satisfies a contract, "
            "that the provider is in the routing ladder, and to exercise a "
            "controlled primary failure and observe whether a fallback answers.",
            "",
        ]
    lines += [
        "## 10. What this does and does not establish",
        "",
        "- Establishes: the observed outcome mix and contract results for the "
        "routes configured at replay time, with first-visible latency measured "
        "from real streamed output, per-attempt telemetry, and the ladder's "
        "provider-sharing topology.",
        "- Does NOT establish: a provider-wide failure rate. The sample is "
        "bounded by the caps above and by the account's own quota.",
        "- Does NOT establish: that a fallback is independent capacity. The "
        "topology state above is a statement about the configured ladder (and "
        "about shared gateway dependencies), not about behaviour under load.",
    ]
    return "\n".join(lines) + "\n"


# ===========================================================================
# 13. Entry point
# ===========================================================================


def _database_url_from_env_files(backend_root: str) -> Optional[str]:
    """Best-effort DATABASE_URL read without importing the app."""
    for candidate in (os.path.join(backend_root, ".env"),
                      os.path.join(os.path.dirname(backend_root), ".env")):
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def _default_db_path() -> str:
    """The SQLite file whose learning-history rows are counted before/after.

    Resolution order: ``ATOM_RELIABILITY_DB`` env, ``DATABASE_URL`` env,
    ``DATABASE_URL`` in ``backend/.env`` or the repo ``.env``, then
    ``backend/data/atom.db`` / ``backend/atom_dev.db`` when they exist.
    """
    env = os.environ.get("ATOM_RELIABILITY_DB")
    if env:
        return env
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url = os.environ.get("DATABASE_URL") or _database_url_from_env_files(backend_root)
    if url and url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            return path if os.path.isabs(path) else os.path.join(backend_root, path)
    for fallback in (os.path.join(backend_root, "data", "atom.db"),
                     os.path.join(backend_root, "atom_dev.db")):
        if os.path.exists(fallback):
            return fallback
    return os.path.join(backend_root, "data", "atom.db")


async def main_async(args: Any) -> int:
    topo = await topology(fallback_limit=args.fallback_limit)
    if args.topology_only:
        print(json.dumps(topo, indent=2, default=str))
        return 0

    before = learning_history_snapshot(args.db)
    run = await replay(args)
    after = learning_history_snapshot(args.db)
    fallback_report = None
    if args.fallback_independence:
        fallback_report = await fallback_independence(args)

    summary = summarize(run["attempts"], run["ledger"], args.budget_calls, run["blocked"])
    rep = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "budget_calls": args.budget_calls,
        "executed_calls": summary["denominators"]["attempts"],
        "topology": topo,
        "summary": summary,
        "attempts": run["attempts"],
        "fixture_limitations": fixture_limitations(),
        "fallback_independence": fallback_report,
        "read_only_check": {
            "before": before,
            "after": after,
            "read_only_guard": run.get("read_only_guard"),
            "llm_routing_feedback_rows_added": _delta(
                before.get("llm_routing_feedback_rows"),
                after.get("llm_routing_feedback_rows"),
            ),
            "rate_usage_records_rows_added": _delta(
                before.get("rate_usage_records_rows"),
                after.get("rate_usage_records_rows"),
            ),
            "llm_stage_router_audit_rows_added": _delta(
                before.get("llm_stage_router_audit_rows"),
                after.get("llm_stage_router_audit_rows"),
            ),
        },
    }
    md = render_markdown(rep)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(md)
    return 0


def _delta(before: Optional[int], after: Optional[int]) -> Optional[int]:
    if before is None or after is None:
        return None
    return after - before


def build_parser() -> argparse.ArgumentParser:
    """The CLI. Existing flags keep their names and semantics."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-calls", type=int, default=6,
                    help="hard cap on generation attempts, retries included "
                         "(default 6)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--timeout-s", type=float, default=90.0,
                    help="per-chunk (stream) / per-call (completion) timeout")
    ap.add_argument("--mode", choices=("stream", "completion"), default="stream",
                    help="stream = real streamed output, first-visible measured "
                         "(default); completion = legacy non-streaming path")
    ap.add_argument("--retry-cap", type=int, default=1,
                    help="max retries per probe (default 1)")
    ap.add_argument("--spend-cap-usd", type=float, default=0.05,
                    help="charged-cost ceiling for the run (default 0.05)")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--fallback-limit", type=int, default=3,
                    help="fallbacks to resolve in the ladder report (default 3)")
    ap.add_argument("--fallback-independence", action="store_true",
                    help="live request-boundary checks: key, authentication, "
                         "ladder membership, and a controlled primary failure")
    ap.add_argument("--force-primary-provider", default=None,
                    help="provider to force a failure on (default: ladder primary)")
    ap.add_argument("--force-primary-model", default=None,
                    help="model to force a failure with (default: a deliberately "
                         "invalid model id)")
    ap.add_argument("--db", default=None,
                    help="SQLite path used to count learning/usage rows before "
                         "and after the run (default: backend/atom_dev.db)")
    ap.add_argument("--allow-learning-writes", action="store_true",
                    help="do NOT suppress the production learning-feedback write "
                         "(benchmark traffic then enters llm_routing_feedback)")
    ap.add_argument("--topology-only", action="store_true",
                    help="print the routing topology without generating")
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.db:
        args.db = _default_db_path()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
