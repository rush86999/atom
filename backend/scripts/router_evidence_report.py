#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Router-evidence reconciliation report — what the learning-router history
actually contains, and what it does NOT license.

Written for audit item 3 ("establish trustworthy router evidence before
choosing a trust horizon"). The audit's claim of "~90 verdict rows" for
auto-activation is not reproducible as a *representative* sample: accrual was
dead from 9a4a2a774 (a latent TypeError in the ``assess_response_quality``
call) until 76cc51bcd repaired it, so every row in the table postdates
2026-09-15 22:24 and comes from the incident's own traffic. This script makes
that auditable instead of asserted, and reports the numbers the activation
threshold is computed from.

WHAT CHANGED IN THIS REVISION (external review, item 3)
=======================================================

1. **The order comparison is a real A/B of the two rankers.** Earlier
   revisions labelled two *descriptive statistics* (aggregate satisfaction per
   model; total historical spend per model) "the learned order" and "the
   static BPC order". Neither is the router. This revision instead invokes the
   real implementations — ``BYOKHandler.get_ranked_providers`` (BPC) and
   ``BYOKHandler._rerank_with_learning`` (the learned re-ranker) — over an
   IDENTICAL candidate set and identical request features, exactly as the
   production call path does (``byok_handler.generate_response``). The
   descriptive statistics are kept but RENAMED to what they are
   (``observed_satisfaction_ranking`` / ``historical_spend_ranking``).
2. **Cost is reported per ANSWER, with its denominator.** Total spend depends
   on how many calls a model received, so ranking by total spend is not a
   cost-efficiency ranking. Every per-answer figure is printed next to the
   number of answered generations it divides by.
3. **No total is compared across different answer counts.** All savings are
   computed from cost per answer, and each figure carries its denominator.
4. **Four-state truthfulness is preserved.** An observational holdout cannot
   establish that one model is SUPERIOR — only that it was executed and
   observed. Absence of ``prompt_features.verdict`` provenance cannot
   establish absence of fabrication, so unprovenanced generations stay
   explicitly UNKNOWN, never "clean".
5. **Fabrication/quality accounting is per GENERATION**, delegated to
   ``core.llm.fabrication_accounting.account_generations`` (one generation can
   produce an outcome row *and* a corrective-verdict row; dividing rows
   inflates the denominator). That logic is NOT re-implemented here.

Read-only. Never writes to the database.

Usage::

    ./venv/bin/python scripts/router_evidence_report.py
    ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db --json out.json
    ./venv/bin/python scripts/router_evidence_report.py --holdout-frac 0.3
    ./venv/bin/python scripts/router_evidence_report.py --no-live-rankers
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

# The script lives in backend/scripts; application modules are imported
# lazily (see ``_accounting_module`` / ``_load_ranker_modules``) so that
# ``--db`` can pin DATABASE_URL BEFORE core.database builds its engine.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

#: Per-model orderings are only reported for models with at least this many
#: observations in the train slice — a 2-row model that happens to score 100%
#: is a small-sample artifact, not evidence.
MIN_OBS = 8

#: A cost-per-answer comparison needs a real denominator on BOTH sides. Models
#: with fewer answered generations are listed as excluded (with their n),
#: never silently compared.
MIN_COMPARABLE_ANSWERS = 5

#: Complexity is NOT persisted per feedback row, so the ranker A/B is swept
#: over the whole ladder and the sweep is declared as such.
COMPLEXITY_LADDER = ("SIMPLE", "MODERATE", "COMPLEX", "ADVANCED")

#: A turn whose rows span more than this many distinct models, with EVERY row
#: unsuccessful and NO recorded cost, is not a set of executed generations: one
#: turn does not execute 100+ models for free. Such a turn is a candidate
#: enumeration written into the outcome table, and counting it as executed
#: attempts inflates the failure count, the model count and the fabrication
#: band. It is reported as its own data-quality finding, never silently dropped.
SWEEP_MIN_MODELS = 5

_ACCOUNTING = None
_RANKERS: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Lazy application imports
# ---------------------------------------------------------------------------

def _accounting_module():
    """``core.llm.fabrication_accounting`` — the single fabrication ledger.

    Imported lazily, not re-implemented: one generation can be written as
    several rows (outcome row + corrective-verdict row), so anything that
    divides rows mixes units. See the module docstring for the identities.
    """
    global _ACCOUNTING
    if _ACCOUNTING is None:
        _ACCOUNTING = importlib.import_module("core.llm.fabrication_accounting")
    return _ACCOUNTING


def _load_ranker_modules() -> Dict[str, Any]:
    """Import the REAL router implementation (BPC + learned re-ranker)."""
    global _RANKERS
    if _RANKERS is None:
        byok = importlib.import_module("core.llm.byok_handler")
        registry = importlib.import_module("core.llm.learning_router_registry")
        settings = importlib.import_module("core.runtime_settings")
        _RANKERS = {
            "BYOKHandler": byok.BYOKHandler,
            "QueryComplexity": byok.QueryComplexity,
            "get_learning_router_instance": registry.get_learning_router_instance,
            "readiness_report": registry.readiness_report,
            "learning_router_mode": registry.learning_router_mode,
            "resolve_setting": settings.resolve_setting,
        }
    return _RANKERS


def _db_path_from_env(default: str = "data/atom.db") -> str:
    url = os.getenv("DATABASE_URL", "") or ""
    m = re.sub(r"^sqlite:///", "", url)
    return m or default


def load_rows(db_path: str) -> List[Dict[str, Any]]:
    """Read the feedback rows. Opens the SQLite file read-only (``mode=ro``)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            "SELECT id, routing_result_id, tenant_id, task_type, model_id, "
            "success, quality_satisfied, user_satisfaction, actual_cost, "
            "actual_latency_ms, prompt_features, created_at "
            "FROM llm_routing_feedback ORDER BY created_at"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    """SQLite stores booleans as 0/1; ORM/test fixtures use bools."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _features(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The row's feature dict, or ``None`` when it carries no real features.

    SQLite stores a JSON ``null`` as the TEXT ``'null'``, which is truthy —
    the first cut of this report counted 67 null-feature rows as populated.
    """
    raw = row.get("prompt_features")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) and parsed else None


def _verdict(row: Dict[str, Any]) -> Optional[str]:
    """Explicit provenance (``prompt_features.verdict``), if the row carries it."""
    verdict, _malformed = _accounting_module().verdict_of(row.get("prompt_features"))
    return verdict


def _features_present(row: Dict[str, Any]) -> bool:
    return _features(row) is not None


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def _p95(values: Sequence[Optional[float]]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    idx = min(len(vals) - 1, int(round(0.95 * (len(vals) - 1))))
    return round(vals[idx], 1)


def generation_key(row: Dict[str, Any]) -> Tuple[str, str]:
    """``(turn, model)`` identity of the generation a row describes.

    Delegated to ``core.llm.fabrication_accounting.generation_key`` so the
    report and the router agree on what one generation is.
    """
    return _accounting_module().generation_key(row)


# ---------------------------------------------------------------------------
# Generation records — the unit every per-answer figure is computed over
# ---------------------------------------------------------------------------

def build_generations(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse feedback ROWS into GENERATION records.

    One generation = one ``(routing_result_id, model_id)`` attempt. A turn that
    falls back to a second model produced two generations; a generation written
    twice (outcome row + corrective row, or a pure duplicate) is ONE generation.

    ``answered`` is the per-answer denominator: a generation counts as answered
    when at least one of its rows reports ``success`` — i.e. the call returned
    and an answer exists. A generation whose every row reports failure produced
    no answer and is excluded from every per-answer figure (its cost, if
    recorded, still sits in the model's total spend — stated explicitly in the
    report).
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    order: List[Tuple[str, str]] = []
    for row in rows:
        key = generation_key(row)
        if key not in grouped:
            order.append(key)
        grouped[key].append(row)

    out: List[Dict[str, Any]] = []
    for key in order:
        grs = grouped[key]
        turn, model = key
        costs = [_num(r.get("actual_cost")) for r in grs]
        lat = [_num(r.get("actual_latency_ms")) for r in grs]
        sat = [_num(r.get("user_satisfaction")) for r in grs]
        answered = any(_truthy(r.get("success")) for r in grs)
        out.append({
            "turn": turn,
            "model": model,
            "rows": len(grs),
            "task_type": str(grs[0].get("task_type")),
            "tenant_id": str(grs[0].get("tenant_id")),
            "answered": answered,
            "quality_satisfied": any(_truthy(r.get("quality_satisfied")) for r in grs),
            # Total recorded spend for the attempt (a failed attempt is still
            # billed). Rows with no recorded cost are excluded and counted.
            "cost": round(sum(c for c in costs if c is not None), 6),
            "rows_without_cost": sum(1 for c in costs if c is None),
            "latency_ms": _mean(lat),
            "satisfaction": _mean(sat),
            "created_at": _parse_ts(grs[0].get("created_at")),
        })
    return out


def detect_candidate_sweeps(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turns that look like a per-candidate write, not executed attempts.

    Shape: one ``routing_result_id`` carrying one row per CANDIDATE model, every
    row unsuccessful, no cost recorded, all written inside one short window. A
    real turn executes one model (plus fallbacks); it cannot execute a hundred
    of them for free. These rows are counted separately so they cannot be read
    as a fleet-wide outage, and so the models they name are not mistaken for
    models that were actually run.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("routing_result_id"))].append(row)
    sweeps = []
    sweep_rows = 0
    sweep_models: set = set()
    for turn, trs in grouped.items():
        models = {str(r.get("model_id")) for r in trs}
        if len(models) <= SWEEP_MIN_MODELS:
            continue
        all_failed = all(not _truthy(r.get("success")) for r in trs)
        no_cost = all(_num(r.get("actual_cost")) is None for r in trs)
        if not (all_failed and no_cost):
            continue
        sweeps.append({
            "routing_result_id": turn,
            "rows": len(trs),
            "models": len(models),
            "task_types": sorted({str(r.get("task_type")) for r in trs}),
            "created_at_first": str(trs[0].get("created_at")),
            "created_at_last": str(trs[-1].get("created_at")),
        })
        sweep_rows += len(trs)
        sweep_models |= models
    return {
        "threshold_distinct_models": SWEEP_MIN_MODELS,
        "rule": ("one turn with more than "
                 f"{SWEEP_MIN_MODELS} distinct model ids, every row "
                 "success=false, and no recorded cost"),
        "turns": sorted(sweeps, key=lambda d: -d["rows"]),
        "turn_count": len(sweeps),
        "rows": sweep_rows,
        "distinct_models": sorted(sweep_models),
        "model_count": len(sweep_models),
        "warning": (
            "These rows cannot be outcomes of executed generations. They are "
            "reported separately and are NOT treated as observed attempts, "
            "answers or evidence about any model."
        ),
    }


def _aggregate(gens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-model facts, with the denominator of every per-answer figure."""
    answered = [g for g in gens if g["answered"]]
    failed = [g for g in gens if not g["answered"]]
    total_cost = round(sum(g["cost"] for g in gens), 6)
    answered_cost = round(sum(g["cost"] for g in answered), 6)
    n_ans = len(answered)
    return {
        "rows": sum(g["rows"] for g in gens),
        "generations": len(gens),
        "answered_generations": n_ans,
        "failed_generations": len(failed),
        "quality_satisfied_generations": sum(1 for g in answered if g["quality_satisfied"]),
        "quality_satisfied_pct_of_answers": _pct(
            sum(1 for g in answered if g["quality_satisfied"]), n_ans),
        "mean_satisfaction_per_answer": _mean([g["satisfaction"] for g in answered]),
        "mean_latency_ms_per_answer": _mean([g["latency_ms"] for g in answered]),
        "p95_latency_ms_per_answer": _p95([g["latency_ms"] for g in answered]),
        "answers_without_latency": sum(1 for g in answered if g["latency_ms"] is None),
        # Numerator = ALL recorded spend for the model (including failed
        # attempts, which are billed). Denominator = answers, printed beside
        # every per-answer figure.
        "total_recorded_cost": total_cost,
        "total_recorded_cost_of_answers": answered_cost,
        "rows_without_cost": sum(g["rows_without_cost"] for g in gens),
        "cost_per_answer": cost_per_answer(total_cost, n_ans),
        "cost_per_answer_basis": (
            f"{total_cost} / {n_ans} answered generation(s)"
            if n_ans else "undefined — no answered generation"
        ),
    }


def cost_per_answer(total_cost: Optional[float], answered_generations: int) -> Optional[float]:
    """Total recorded spend / answered generations. ``None`` when undefined.

    An undefined rate must not read as ``0.0`` (which would look free).
    """
    if not answered_generations or answered_generations <= 0:
        return None
    if total_cost is None:
        return None
    return round(float(total_cost) / answered_generations, 6)


def per_answer_savings(
    by_model: Dict[str, Dict[str, Any]],
    min_answers: int = MIN_COMPARABLE_ANSWERS,
) -> Dict[str, Any]:
    """Cheapest/priciest model by COST PER ANSWER, with both denominators.

    Totals are deliberately NOT compared: models answered different numbers of
    generations, so a total-spend difference is a workload difference as much
    as a price difference.
    """
    eligible = [
        (m, a) for m, a in by_model.items()
        if a.get("cost_per_answer") is not None
        and a.get("answered_generations", 0) >= min_answers
    ]
    excluded = [
        {"model": m, "answered_generations": a.get("answered_generations", 0),
         "reason": f"fewer than {min_answers} answered generation(s)"}
        for m, a in by_model.items()
        if a.get("cost_per_answer") is not None
        and a.get("answered_generations", 0) < min_answers
    ]
    undefined = sorted(
        m for m, a in by_model.items() if a.get("cost_per_answer") is None)
    base = {
        "basis": "cost per ANSWERED generation (total recorded spend / answers)",
        "min_answered_generations": min_answers,
        "excluded_small_denominator": sorted(excluded, key=lambda d: d["model"]),
        "undefined_no_answers": undefined,
    }
    if len(eligible) < 2:
        base.update({
            "status": "insufficient_denominators",
            "note": ("fewer than two models have >= "
                     f"{min_answers} answered generations — no per-answer "
                     "saving is computed"),
        })
        return base

    cheapest = min(eligible, key=lambda kv: kv[1]["cost_per_answer"])
    priciest = max(eligible, key=lambda kv: kv[1]["cost_per_answer"])
    c_cpa = cheapest[1]["cost_per_answer"]
    p_cpa = priciest[1]["cost_per_answer"]
    base.update({
        "status": "ok",
        "cheapest": {
            "model": cheapest[0],
            "cost_per_answer": c_cpa,
            "answered_generations": cheapest[1]["answered_generations"],
            "total_recorded_cost": cheapest[1]["total_recorded_cost"],
        },
        "priciest": {
            "model": priciest[0],
            "cost_per_answer": p_cpa,
            "answered_generations": priciest[1]["answered_generations"],
            "total_recorded_cost": priciest[1]["total_recorded_cost"],
        },
        "difference_per_answer": round(p_cpa - c_cpa, 6),
        "cheaper_by_pct_of_priciest": (
            round(100.0 * (p_cpa - c_cpa) / p_cpa, 1) if p_cpa else None
        ),
        "totals_are_not_comparable": (
            "the two models answered different numbers of generations "
            f"({cheapest[1]['answered_generations']} vs "
            f"{priciest[1]['answered_generations']}); their raw totals differ "
            "by workload as much as by price, so only the per-answer figures "
            "are compared"
        ),
    })
    return base


# ---------------------------------------------------------------------------
# Fabrication / quality accounting (per generation, via the shared module)
# ---------------------------------------------------------------------------

def accounting_block(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """``account_generations`` for the whole table and per model."""
    acc = _accounting_module().account_generations(rows)
    by_model: Dict[str, Dict[str, Any]] = {}
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("model_id"))].append(row)
    for model, mrs in grouped.items():
        by_model[model] = _accounting_module().account_generations(mrs).as_dict()
    return {"overall": acc.as_dict(), "by_model": by_model}


def band_audit(rows: List[Dict[str, Any]], sweep_turns: Optional[set] = None) -> Dict[str, Any]:
    """Audit the bench's score rule AT GENERATION LEVEL.

    Rule: ``user_satisfaction <= 0.15``. A row in that band proves nothing on
    its own — provider exceptions and empty completions land in the same band
    as fabrications — so every generation selected by the score is classified
    by PROVENANCE ONLY:

    * ``fabrication_verdict`` — an explicit fabrication verdict exists;
    * ``availability_verdict`` — an explicit availability verdict exists;
    * ``unknown`` — no verdict: NOT clean, and never counted as fabricated.

    Generations whose rows all report ``success=false`` are surfaced as
    ``availability_shaped_by_success_flag`` — an observable that is reported
    BESIDE the provenance classes, not as a substitute for one, because the
    success flag is not a fabrication verdict.
    """
    fa = _accounting_module()
    ceiling = fa.FABRICATION_SCORE_CEILING
    sweep_turns = sweep_turns or set()
    gen_rows: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    order: List[Tuple[str, str]] = []
    unscored_rows = 0
    for row in rows:
        score = _num(row.get("user_satisfaction"))
        if score is None:
            unscored_rows += 1
        key = generation_key(row)
        if key not in gen_rows:
            order.append(key)
        gen_rows[key].append(row)

    band: List[Dict[str, Any]] = []
    for key in order:
        grs = gen_rows[key]
        scores = [_num(r.get("user_satisfaction")) for r in grs]
        known = [s for s in scores if s is not None]
        if not known or min(known) > ceiling:
            continue
        verdicts = {v for v in (_verdict(r) for r in grs) if v}
        fab = sorted(verdicts & set(fa.FABRICATION_VERDICTS))
        avail = sorted(verdicts & set(fa.AVAILABILITY_VERDICTS))
        if fab:
            cls = "fabrication_verdict"
        elif avail:
            cls = "availability_verdict"
        else:
            cls = "unknown"
        band.append({
            "generation": f"{key[0]}/{key[1]}",
            "routing_result_id": key[0],
            "model": key[1],
            "rows": len(grs),
            "min_satisfaction": min(known),
            "success_flag_all_false": not any(_truthy(r.get("success")) for r in grs),
            "suspected_candidate_sweep": key[0] in sweep_turns,
            "classification": cls,
            "verdicts": sorted(verdicts),
        })

    by_class: Dict[str, int] = defaultdict(int)
    for item in band:
        by_class[item["classification"]] += 1
    rows_in_band = sum(
        1 for r in rows
        if (_num(r.get("user_satisfaction")) is not None
            and float(_num(r.get("user_satisfaction"))) <= ceiling))
    return {
        "rule": f"user_satisfaction <= {ceiling}",
        "rows_in_band": rows_in_band,
        "rows_without_a_score": unscored_rows,
        "generations_in_band": len(band),
        "generations_by_classification": dict(sorted(by_class.items())),
        "generations_with_fabrication_verdict": by_class.get("fabrication_verdict", 0),
        "generations_unprovenanced": by_class.get("unknown", 0),
        "generations_availability_verdict": by_class.get("availability_verdict", 0),
        "generations_availability_shaped_by_success_flag": sum(
            1 for item in band if item["success_flag_all_false"]),
        "generations_availability_shaped_from_suspected_sweeps": sum(
            1 for item in band
            if item["success_flag_all_false"] and item["suspected_candidate_sweep"]),
        "generations_availability_shaped_not_from_sweeps": sum(
            1 for item in band
            if item["success_flag_all_false"] and not item["suspected_candidate_sweep"]),
        "unprovenanced_are_unknown_not_clean": True,
        "detail": sorted(band, key=lambda d: (d["classification"], d["model"])),
    }


# ---------------------------------------------------------------------------
# Live A/B of the two REAL rankers
# ---------------------------------------------------------------------------

def _tokens_from_features(feats: Dict[str, Any]) -> Optional[int]:
    """Invert ``log_tokens = log2(tokens + 1)`` (see ``_extract_request_features``)."""
    raw = _num(feats.get("log_tokens"))
    if raw is None:
        return None
    try:
        tokens = int(round(2 ** raw - 1))
    except (OverflowError, ValueError):
        return None
    return max(1, tokens)


def request_profiles(
    rows: List[Dict[str, Any]],
    max_profiles: int = 6,
    exclude_turns: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Request profiles reconstructed from the PERSISTED request features.

    Rows with no stashed features are excluded here on purpose: their training
    input is the task-default vector, not a real request, and the A/B must run
    on real request features. (Their share is reported in the totals.) Rows from
    a suspected candidate sweep are excluded too — they are not requests.
    """
    exclude_turns = (exclude_turns if exclude_turns is not None else {
        s["routing_result_id"] for s in detect_candidate_sweeps(rows)["turns"]})
    groups: Dict[Tuple[str, Any], List[int]] = defaultdict(list)
    for row in rows:
        if str(row.get("routing_result_id")) in exclude_turns:
            continue
        feats = _features(row)
        if not feats:
            continue
        tokens = _tokens_from_features(feats)
        if tokens is None:
            continue
        groups[(str(row.get("task_type")), feats.get("token_bucket"))].append(tokens)

    profiles: List[Dict[str, Any]] = []
    for (task, bucket), toks in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        toks_sorted = sorted(toks)
        profiles.append({
            "task_type": task,
            "token_bucket": bucket,
            "estimated_tokens": toks_sorted[len(toks_sorted) // 2],
            "tokens_min": toks_sorted[0],
            "tokens_max": toks_sorted[-1],
            "rows_with_these_features": len(toks),
        })
    return profiles[:max_profiles]


def _ranks(order: Sequence[str], models: Sequence[str]) -> Dict[str, Optional[int]]:
    return {m: (order.index(m) if m in order else None) for m in models}


def live_ranker_ab(
    rows: List[Dict[str, Any]],
    max_profiles: int = 6,
    complexities: Sequence[str] = COMPLEXITY_LADDER,
    workspace_id: str = "default",
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run BPC and the learned re-ranker over ONE identical candidate set.

    This is the production path in miniature (``byok_handler.generate_response``):
    ``get_ranked_providers(...)`` produces the BPC order, then
    ``_rerank_with_learning(...)`` re-orders THAT SAME LIST. The learned
    re-ranker can only permute — it never adds or removes candidates — so the
    candidate set is identical for both rankers by construction, and the run
    records the size to prove it.

    Fail-soft: on any error the block reports ``status: "unavailable"`` with the
    reason, and every descriptive section of the report still renders.
    """
    out: Dict[str, Any] = {
        "status": "unavailable",
        "method": (
            "real implementations: BYOKHandler.get_ranked_providers (BPC) vs "
            "BYOKHandler._rerank_with_learning (learned re-ranking) over the "
            "same candidate list"
        ),
        "inputs": {
            "task_type": "from each profile",
            "estimated_tokens": "median of the persisted prompt features per profile",
            "turn_index": 0,
            "prefer_cost": True,
            "tenant_plan": "free",
            "is_managed_service": True,
            "requires_tools": False,
            "requires_structured": False,
            "cognitive_tier": None,
            "max_quality": None,
            "required_capability": None,
            "complexity": "NOT persisted per row — swept over the full ladder",
            "prompt": "synthetic, length 4 x estimated_tokens (the re-ranker "
                      "derives estimated_tokens = len(prompt) // 4)",
        },
        "runs": [],
    }
    try:
        mods = _load_ranker_modules()
        BYOKHandler = mods["BYOKHandler"]
        QueryComplexity = mods["QueryComplexity"]
    except Exception as exc:  # noqa: BLE001 — the report must still render
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    profiles = request_profiles(rows, max_profiles=max_profiles)
    # "Observed" = the model produced at least one ANSWER. Models named only by
    # candidate-sweep rows never ran and must not appear as if they had.
    observed_models = sorted({
        g["model"] for g in build_generations(rows) if g["answered"]})
    tenants = sorted({str(r.get("tenant_id")) for r in rows if r.get("tenant_id")})
    tenant = tenant_id or (tenants[0] if len(tenants) == 1 else "default")

    out["inputs"]["tenant_id"] = tenant
    out["inputs"]["workspace_id"] = workspace_id
    out["inputs"]["observed_models"] = observed_models
    out["inputs"]["profiles"] = profiles
    if not profiles:
        out["status"] = "no_request_features"
        out["error"] = (
            "no row carries a real prompt_features dict, so no request profile "
            "can be reconstructed for the A/B")
        return out

    cwd = os.getcwd()
    handler = None
    loop = None
    try:
        # Application code resolves data/ paths against the CWD; run from the
        # backend root so nothing is created elsewhere.
        os.chdir(_BACKEND_ROOT)
        handler = BYOKHandler(tenant_id=tenant, workspace_id=workspace_id)

        lr = mods["get_learning_router_instance"]()
        learned_signal = {
            "singleton_present": lr is not None,
            "predictor_buckets": sorted(getattr(lr, "_per_model_routers", {}).keys()) if lr else [],
            "ema_keys": sorted(getattr(lr, "_ema_scores", {}).keys()) if lr else [],
            "ema_score_weight": getattr(lr, "_EMA_SCORE_WEIGHT", None) if lr else None,
            "settings": {},
        }
        for key in ("ATOM_LEARNING_ROUTER", "ATOM_EMA_ROUTER_ENABLED",
                    "ATOM_FABRICATION_BENCH"):
            try:
                resolved = mods["resolve_setting"](key)
                learned_signal["settings"][key] = {
                    "value": resolved.value, "source": resolved.source}
            except Exception:  # noqa: BLE001 — provenance is best-effort
                learned_signal["settings"][key] = {"value": None, "source": "error"}
        try:
            learned_signal["mode"] = mods["learning_router_mode"]()
        except Exception:  # noqa: BLE001
            learned_signal["mode"] = None
        out["learned_signal"] = learned_signal

        try:
            out["activation"] = mods["readiness_report"]()
        except Exception as exc:  # noqa: BLE001
            out["activation"] = {"error": f"{type(exc).__name__}: {exc}"}

        loop = asyncio.new_event_loop()
        for profile in profiles:
            task = profile["task_type"]
            tokens = int(profile["estimated_tokens"])
            prompt = "x" * (4 * tokens)
            for cx_name in complexities:
                cx = getattr(QueryComplexity, cx_name)
                bpc_options = handler.get_ranked_providers(
                    cx, task_type=task, estimated_tokens=tokens, turn_index=0)
                bpc_order = [m for _p, m in bpc_options]
                learned_options = loop.run_until_complete(
                    handler._rerank_with_learning(list(bpc_options), prompt, task))
                learned_order = [m for _p, m in learned_options]
                run = {
                    "task_type": task,
                    "token_bucket": profile["token_bucket"],
                    "estimated_tokens": tokens,
                    "complexity": cx_name,
                    "candidates": len(bpc_order),
                    "same_candidate_set": sorted(bpc_order) == sorted(learned_order),
                    "orders_identical": bpc_order == learned_order,
                    "bpc_top": bpc_order[0] if bpc_order else None,
                    "learned_top": learned_order[0] if learned_order else None,
                    "top_changed": bool(bpc_order and learned_order
                                        and bpc_order[0] != learned_order[0]),
                    "bpc_rank_of_observed": _ranks(bpc_order, observed_models),
                    "learned_rank_of_observed": _ranks(learned_order, observed_models),
                }
                out["runs"].append(run)

        # The predictor bucket is created lazily by retraining, so report the
        # state that was actually SERVED rather than assuming one.
        if lr is not None:
            served: Dict[str, Any] = {}
            for task in sorted({p["task_type"] for p in profiles}):
                bucket = f"{tenant}:{task}"
                pmr = getattr(lr, "_per_model_routers", {}).get(bucket)
                ema_all = sorted(
                    k.split(":", 2)[2] for k in getattr(lr, "_ema_scores", {})
                    if k.startswith(bucket + ":"))
                served[bucket] = {
                    "predictor_models": sorted(getattr(pmr, "predictors", {}).keys()) if pmr else [],
                    "ema_models": ema_all,
                    "ema_models_with_observed_answers": sorted(
                        set(ema_all) & set(observed_models)),
                }
            out["learned_signal"]["served_by_tenant_task"] = served

        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 — a diagnostic report must render
        out["status"] = "error"
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            if loop is not None:
                loop.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if handler is not None and getattr(handler, "db_session", None) is not None:
                handler.db_session.close()
        except Exception:  # noqa: BLE001
            pass
        os.chdir(cwd)
    return out


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_report(
    rows: List[Dict[str, Any]],
    holdout_frac: float = 0.3,
    ranker_ab: Optional[Dict[str, Any]] = None,
    source: Optional[Dict[str, Any]] = None,
    min_model_rows: int = 2,
) -> Dict[str, Any]:
    """Assemble the whole report. Pure when ``ranker_ab`` is supplied."""
    total = len(rows)
    generations = build_generations(rows)
    gen_counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        gen_counts[str(row.get("routing_result_id"))] += 1
    dup_generations = {k: v for k, v in gen_counts.items() if v > 1}

    sweeps = detect_candidate_sweeps(rows)
    sweep_turns = {s["routing_result_id"] for s in sweeps["turns"]}
    sweep_models = set(sweeps["distinct_models"])

    ts = [t for t in (_parse_ts(r.get("created_at")) for r in rows) if t]
    first, last = (min(ts), max(ts)) if ts else (None, None)
    span_h = round((last - first).total_seconds() / 3600.0, 2) if ts else None

    no_features = sum(1 for r in rows if not _features_present(r))
    no_score = sum(1 for r in rows if _num(r.get("user_satisfaction")) is None)

    # ---- per model: cost per answer with its denominator -------------------
    gens_by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for gen in generations:
        gens_by_model[gen["model"]].append(gen)
    by_model = {
        model: {
            "rows": sum(g["rows"] for g in gens),
            **_aggregate(gens),
        }
        for model, gens in gens_by_model.items()
    }

    # ---- per task ----------------------------------------------------------
    gens_by_task: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for gen in generations:
        gens_by_task[gen["task_type"]].append(gen)
    by_task = {
        task: {
            "rows": sum(g["rows"] for g in gens),
            "generations": len(gens),
            "answered_generations": sum(1 for g in gens if g["answered"]),
            "models": sorted({g["model"] for g in gens}),
            "models_with_answers": sorted({g["model"] for g in gens if g["answered"]}),
            "quality_satisfied_pct_of_answers": _pct(
                sum(1 for g in gens if g["answered"] and g["quality_satisfied"]),
                sum(1 for g in gens if g["answered"])),
        }
        for task, gens in gens_by_task.items()
    }

    # ---- duplicate-generation classification -------------------------------
    dup_detail = []
    for gid, count in sorted(dup_generations.items(), key=lambda kv: -kv[1])[:10]:
        grs = [r for r in rows if str(r.get("routing_result_id")) == gid]
        models = sorted({str(r.get("model_id")) for r in grs})
        if gid in sweep_turns:
            kind = "candidate_sweep_shaped"
        elif len(models) > 1:
            kind = "multi_model_turn (primary + fallback attempts)"
        else:
            kind = "pure_duplicate (same generation written twice)"
        dup_detail.append({
            "routing_result_id": gid,
            "kind": kind,
            "rows": count,
            "models": models,
            "satisfactions": [r.get("user_satisfaction") for r in grs],
        })

    target = None
    if source:
        target = source.get("db")

    sweep_gen_count = sum(
        1 for g in generations if g["turn"] in sweep_turns)
    answered_from_sweeps = sum(
        1 for g in generations if g["turn"] in sweep_turns and g["answered"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": dict(source or {}),
        "display": {"min_model_rows": min_model_rows},
        "method": {
            "learned_order": (
                "REAL learned re-ranker: BYOKHandler._rerank_with_learning over "
                "the candidate list BPC returned (see ranker_ab)"
            ) if (ranker_ab or {}).get("status") in {"ok", "error", "no_request_features"} else (
                "NOT COLLECTED (--no-live-rankers): no claim about the learned "
                "router's order appears in this report"
            ),
            "static_order": (
                "REAL BPC: BYOKHandler.get_ranked_providers (see ranker_ab)"
            ) if (ranker_ab or {}).get("status") in {"ok", "error", "no_request_features"} else (
                "NOT COLLECTED (--no-live-rankers)"
            ),
            "descriptive_statistics": (
                "observed_satisfaction_ranking / historical_spend_ranking are "
                "DESCRIPTIVE statistics over observed rows. They are NOT the "
                "learned router and NOT BPC and are labelled as such."
            ),
            "cost_basis": (
                "cost per ANSWERED generation (total recorded spend / answers); "
                "every per-answer figure is printed with its denominator"
            ),
            "fabrication_basis": (
                "core.llm.fabrication_accounting.account_generations — per "
                "GENERATION, not per row"
            ),
            "option_implemented": (
                "preferred option: evaluate the ACTUAL implementations over an "
                "identical candidate set and identical request features"
            ),
        },
        "totals": {
            "rows": total,
            "distinct_generations": len(generations),
            "answered_generations": sum(1 for g in generations if g["answered"]),
            "failed_generations": sum(1 for g in generations if not g["answered"]),
            "failed_generations_from_suspected_candidate_sweeps": sum(
                1 for g in generations
                if not g["answered"] and g["turn"] in sweep_turns),
            "distinct_turns": len({g["turn"] for g in generations}),
            "duplicate_generations": len(dup_generations),
            "duplicate_row_excess": sum(v - 1 for v in dup_generations.values()),
            "models": len(gens_by_model),
            "first_row_utc": first.isoformat() if first else None,
            "last_row_utc": last.isoformat() if last else None,
            "span_hours": span_h,
            "rows_per_hour": round(total / span_h, 2) if span_h else None,
            "rows_without_prompt_features": no_features,
            "rows_without_prompt_features_pct": _pct(no_features, total),
            "rows_without_a_satisfaction_score": no_score,
            "rows_from_suspected_candidate_sweeps": sweeps["rows"],
            "generations_from_suspected_candidate_sweeps": sweep_gen_count,
            "answered_generations_from_suspected_candidate_sweeps": answered_from_sweeps,
            "models_named_only_by_suspected_candidate_sweeps": sorted(
                sweep_models - {g["model"] for g in generations if g["answered"]}),
        },
        "data_quality": {
            "suspected_candidate_sweeps": sweeps,
            "model_count_excluding_sweep_only_models": len({
                g["model"] for g in generations
                if g["model"] not in sweep_models or g["answered"]}),
        },
        "accounting": accounting_block(rows),
        "fabrication_band": band_audit(rows, sweep_turns),
        "duplicate_generation_detail": dup_detail,
        "by_model": by_model,
        "by_task": by_task,
        "ranker_ab": ranker_ab or {"status": "not_collected"},
        "activation": (ranker_ab or {}).get("activation"),
        "savings": per_answer_savings(by_model),
        "holdout": holdout_eval(rows, holdout_frac),
        "limitations": [
            "Rows are outcomes of the model BPC already chose (observational, "
            "not randomised): an unexecuted alternative has no known outcome "
            "and is reported as unobserved, never as a win or a loss.",
            "An observational holdout can establish that a model was EXECUTED "
            "and OBSERVED; it cannot establish that one model is SUPERIOR.",
            "Accrual began only after the assess_response_quality TypeError was "
            "repaired, so the window is one incident's traffic, not a "
            "representative workload.",
            "prompt_features are NULL for rows written without a stashed "
            "decision id, so those rows train on task-default features "
            "(train/serve skew); see totals.rows_without_prompt_features.",
            "No decision log persists the candidate ordering per decision, so "
            "retrospective routing disagreements cannot be reconstructed; the "
            "A/B in section 4 evaluates the rankers LIVE over reconstructed "
            "request profiles instead.",
            "per-decision complexity is NOT persisted, so the ranker A/B is "
            "swept over the whole complexity ladder rather than reproducing "
            "the complexity each historical decision actually used.",
            "Cost per answer divides ALL recorded spend (failed attempts "
            "included, since they are billed) by the number of answered "
            "generations; rows with no recorded cost are excluded from the "
            "numerator and counted in rows_without_cost.",
        ],
        "changelog": changelog(),
        "target_db": target,
    }


def _descriptive_orders(
    train_agg: Dict[str, Dict[str, Any]], eligible: List[str]
) -> Tuple[List[str], List[str]]:
    """The two DESCRIPTIVE orderings, named for what they measure.

    * ``observed_satisfaction_ranking`` — train-slice quality-satisfied rate
      desc, mean latency asc. This is an aggregate of OBSERVED outcomes; it is
      not the learned router (which re-ranks candidates per request from a
      per-model predictor / EMA signal — see the A/B in section 4).
    * ``historical_spend_ranking`` — train-slice total recorded spend asc.
      This is not BPC: BPC ranks a candidate pool by value score (quality^2 /
      effective cost, with quality floors, capability and rate-headroom
      filters) per request, not by what a model has cost historically.
    """
    observed_satisfaction_ranking = sorted(
        eligible,
        key=lambda m: (-(train_agg[m]["quality_satisfied_pct_of_answers"] or 0),
                       train_agg[m]["mean_latency_ms_per_answer"] or 0))
    historical_spend_ranking = sorted(
        eligible, key=lambda m: (train_agg[m]["total_recorded_cost"], m))
    return observed_satisfaction_ranking, historical_spend_ranking


def holdout_eval(rows: List[Dict[str, Any]], frac: float) -> Dict[str, Any]:
    """Time-ordered split; report per-model measured outcomes on the holdout.

    Deliberately does NOT declare a winner: with one model per decision and no
    randomisation, the holdout can measure each model's observed quality,
    latency and cost per answer, but cannot answer "what would the other model
    have done". The two orderings it reports are DESCRIPTIVE statistics, and
    the ordering comparison against BPC is the live A/B (section 4), not this.
    """
    ts_rows = [(t, r) for t, r in ((_parse_ts(r.get("created_at")), r) for r in rows) if t]
    ts_rows.sort(key=lambda p: p[0])
    if len(ts_rows) < 10:
        return {"status": "insufficient_rows", "rows": len(ts_rows)}
    cut = max(1, int(len(ts_rows) * (1.0 - frac)))
    train = [r for _t, r in ts_rows[:cut]]
    holdout = [r for _t, r in ts_rows[cut:]]

    def _agg(rs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        gens: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for gen in build_generations(rs):
            gens[gen["model"]].append(gen)
        for model, mgens in gens.items():
            out[model] = _aggregate(mgens)
            out[model]["accounting"] = _accounting_module().account_generations(
                [r for r in rs if str(r.get("model_id")) == model]).as_dict()
        return out

    train_agg, holdout_agg = _agg(train), _agg(holdout)
    eligible = [m for m, a in train_agg.items()
                if a["answered_generations"] >= MIN_OBS]
    excluded_small = sorted(m for m in train_agg if m not in eligible)
    observed_satisfaction_ranking, historical_spend_ranking = _descriptive_orders(
        train_agg, eligible)

    descriptive_disagreements = []
    if (observed_satisfaction_ranking and historical_spend_ranking
            and observed_satisfaction_ranking[0] != historical_spend_ranking[0]):
        descriptive_disagreements.append({
            "train_top_observed_satisfaction": observed_satisfaction_ranking[0],
            "train_top_historical_spend": historical_spend_ranking[0],
            "note": ("both are descriptive statistics over the same observed "
                     "rows; neither is a router output"),
        })
    return {
        "status": "ok",
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_by_model": train_agg,
        "holdout_by_model": holdout_agg,
        "observed_satisfaction_ranking": observed_satisfaction_ranking,
        "historical_spend_ranking": historical_spend_ranking,
        "ordering_min_answered_generations": MIN_OBS,
        "models_excluded_small_sample": excluded_small,
        "descriptive_order_disagreements": descriptive_disagreements,
        "holdout_savings": per_answer_savings(holdout_agg),
        "verdict": (
            "Held-out comparison is INCONCLUSIVE by construction: the holdout "
            "contains only outcomes of the model that was actually executed. "
            "It can show that a model was EXECUTED and OBSERVED; it cannot "
            "establish that one model is SUPERIOR. Certifying superiority over "
            "static BPC requires an executed split (ATOM_TRAFFIC_SPLIT-style) "
            "or a persisted candidate-order log with counterfactual sampling."
        ),
    }


def changelog() -> List[Dict[str, str]]:
    """Claims this revision REMOVED or RENAMED, and why."""
    return [
        {
            "claim": "\"learned_order_from_train\" presented a train-slice "
                     "aggregate satisfaction ranking as the learned router's order",
            "action": "REMOVED as a claim; RENAMED to "
                      "`observed_satisfaction_ranking`",
            "why": "the learned router is a per-request candidate re-ranker "
                   "(per-model predictor + EMA telemetry), not an aggregate "
                   "satisfaction table; the real re-ranker is now invoked in "
                   "the A/B (section 4)",
        },
        {
            "claim": "\"static_cost_priority_order\" presented total historical "
                     "spend per model as the static BPC order",
            "action": "REMOVED as a claim; RENAMED to "
                      "`historical_spend_ranking`",
            "why": "BPC ranks a per-request candidate pool by value score, and "
                   "total spend measures workload volume, not routing order",
        },
        {
            "claim": "\"cost/success\" divided total spend by ROWS with "
                     "success=true",
            "action": "REPLACED by `cost_per_answer` with an explicit "
                      "`answered_generations` denominator",
            "why": "one generation can be written as several rows, and total "
                   "spend depends on how many calls a model received",
        },
        {
            "claim": "savings quoted from totals across models with different "
                     "answer counts (e.g. a total for 11 answers vs a total for "
                     "25 answers)",
            "action": "REMOVED; every saving is recomputed from cost per "
                      "answer with both denominators printed",
            "why": "totals across different answer counts are not comparable",
        },
        {
            "claim": "the fabrication band's row counts (rows_in_band / "
                     "misclassified / unprovenanced) as if one row were one "
                     "evaluated output",
            "action": "REPLACED by generation-level accounting via "
                      "`core.llm.fabrication_accounting.account_generations`",
            "why": "one generation can produce an outcome row AND a corrective "
                   "verdict row; dividing rows inflates the denominator",
        },
        {
            "claim": "a low score with no verdict counted as a "
                     "misclassification/fabrication signal",
            "action": "KEPT as a selection band, but every unprovenanced "
                      "generation is reported as UNKNOWN (never clean, never "
                      "fabricated)",
            "why": "absence of provenance cannot establish absence of "
                   "fabrication — nor its presence",
        },
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_models(models: Sequence[str], cap: int = 12) -> str:
    """Model-id list for prose, capped with an explicit remainder marker.

    A table is not the place for 125 ids; the full list is in the JSON report.
    """
    shown = ", ".join(f"`{m}`" for m in list(models)[:cap])
    if len(models) > cap:
        shown += f" … (+{len(models) - cap} more, full list in the JSON report)"
    return shown or "—"


def render_markdown(rep: Dict[str, Any]) -> str:
    t = rep["totals"]
    m = rep["method"]
    lines = [
        "# Router evidence — reconciliation",
        "",
        f"_Generated {rep['generated_at']} by `backend/scripts/router_evidence_report.py`._",
        "",
        f"- Target database: `{rep.get('target_db')}`",
        f"- Learned order: {m['learned_order']}",
        f"- Static order: {m['static_order']}",
        f"- Cost basis: {m['cost_basis']}",
        f"- Fabrication basis: {m['fabrication_basis']}",
        "",
        "## 1. What the table actually holds",
        "",
        f"- **{t['rows']} outcome rows** across **{t['distinct_generations']} distinct "
        f"generations / {t['distinct_turns']} turns** ({t['models']} models).",
        f"- Answered generations: **{t['answered_generations']}**; generations with "
        f"no successful attempt: **{t['failed_generations']}**.",
        f"- Window: `{t['first_row_utc']}` → `{t['last_row_utc']}` "
        f"(**{t['span_hours']} h**, ~{t['rows_per_hour']} rows/h).",
        f"- Duplicate generations: **{t['duplicate_generations']}** "
        f"({t['duplicate_row_excess']} excess row(s)) — one generation written "
        "more than once.",
        f"- Rows with **no stashed prompt features**: "
        f"**{t['rows_without_prompt_features']}** "
        f"({t['rows_without_prompt_features_pct']}%) → these train on "
        "task-default features.",
        f"- Rows with **no satisfaction score**: "
        f"**{t['rows_without_a_satisfaction_score']}** (excluded from every "
        "score-based band, not read as 0.0).",
        f"- Rows belonging to a **suspected candidate sweep**: "
        f"**{t['rows_from_suspected_candidate_sweeps']}** over "
        f"**{len(rep['data_quality']['suspected_candidate_sweeps']['turns'])}** "
        f"turn(s), naming "
        f"**{rep['data_quality']['suspected_candidate_sweeps']['model_count']}** "
        f"model id(s) — see §1.3; these are NOT executed attempts and "
        f"**{t['failed_generations_from_suspected_candidate_sweeps']}** of the "
        "failed-generation count comes from them.",
        "",
        "### 1.1 Fabrication / quality accounting — per GENERATION",
        "",
        "`core.llm.fabrication_accounting.account_generations`. The denominator is "
        "EVALUATED GENERATIONS, never rows. `unknown` is the unprovenanced "
        "residue: it is excluded from both terms and is **not** counted as clean.",
        "",
    ]
    ov = rep["accounting"]["overall"]
    lines += [
        f"- Evaluated generations (denominator): **{ov['generations']}** "
        f"(fabricated {ov['fabricated']} + clean {ov['clean']}).",
        f"- Fabricated generations (numerator): **{ov['fabricated']}** → rate "
        f"**{ov['rate'] if ov['rate'] is not None else 'undefined'}**.",
        f"- Unprovenanced generations (UNKNOWN, excluded): **{ov['unknown']}**.",
        f"- Availability-classified generations (excluded): **{ov['availability']}**.",
        f"- Rows collapsed into an already-seen generation: "
        f"**{ov['duplicate_rows']}**; malformed metadata rows: "
        f"**{ov['malformed_rows']}**.",
        "",
        f"_Selection rule `{rep['fabrication_band']['rule']}` (a score band, not "
        "a verdict):_",
        "",
        f"- Rows in band: **{rep['fabrication_band']['rows_in_band']}** "
        f"({rep['fabrication_band']['rows_without_a_score']} row(s) carry no "
        "score at all).",
        f"- **Generations** in band: **{rep['fabrication_band']['generations_in_band']}** "
        f"— by provenance: {rep['fabrication_band']['generations_by_classification']}.",
        f"- Carrying an explicit fabrication verdict: "
        f"**{rep['fabrication_band']['generations_with_fabrication_verdict']}**.",
        f"- Unprovenanced (**UNKNOWN**, not clean): "
        f"**{rep['fabrication_band']['generations_unprovenanced']}**.",
        f"- Availability-shaped by the `success` flag (reported beside, not "
        f"instead of, provenance): "
        f"**{rep['fabrication_band']['generations_availability_shaped_by_success_flag']}** "
        f"= {rep['fabrication_band']['generations_availability_shaped_from_suspected_sweeps']} "
        "from suspected candidate sweeps + "
        f"{rep['fabrication_band']['generations_availability_shaped_not_from_sweeps']} "
        "otherwise.",
        "",
        "### 1.2 Accounting by model (generations)",
        "",
    ]
    display_floor = (rep.get("display") or {}).get("min_model_rows", 2)
    acct_models = sorted(rep["accounting"]["by_model"].items(),
                         key=lambda kv: -kv[1]["rows"])
    shown = [(mm, aa) for mm, aa in acct_models if aa["rows"] >= display_floor]
    hidden = [(mm, aa) for mm, aa in acct_models if aa["rows"] < display_floor]
    lines += [
        f"_Models with fewer than {display_floor} row(s) are summarised below "
        "the table, not listed (they are present in the JSON report)._",
        "",
        "| model | rows | generations | fabricated | clean | unknown | availability | rate | malformed rows |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for model, a in shown:
        lines.append(
            f"| `{model}` | {a['rows']} | {a['generations']} | {a['fabricated']} | "
            f"{a['clean']} | {a['unknown']} | {a['availability']} | "
            f"{a['rate'] if a['rate'] is not None else 'undefined'} | "
            f"{a['malformed_rows']} |")
    if hidden:
        lines.append(
            f"| _(omitted: {len(hidden)} model(s) with < {display_floor} row(s) — "
            f"{sum(a['rows'] for _m, a in hidden)} row(s) total, all in the "
            "UNKNOWN column)_ | "
            f"{sum(a['rows'] for _m, a in hidden)} | 0 | 0 | 0 | "
            f"{sum(a['unknown'] for _m, a in hidden)} | 0 | — | 0 |")
        lines += ["", "_Omitted model ids: "
                  + _fmt_models([mm for mm, _a in hidden]) + "._"]

    lines += ["", "### 1.3 Suspected candidate sweeps (data quality)", ""]
    sw = rep["data_quality"]["suspected_candidate_sweeps"]
    lines += [
        f"- Rule: {sw['rule']}.",
        f"- Turns: **{sw['turn_count']}**; rows: **{sw['rows']}**; distinct model "
        f"ids named: **{sw['model_count']}**.",
        f"- **{sw['warning']}**",
    ]
    if sw["turns"]:
        lines += ["", "| routing_result_id | rows | models | task types | first row | last row |",
                  "|---|---|---|---|---|---|"]
        for item in sw["turns"]:
            lines.append(
                f"| `{item['routing_result_id']}` | {item['rows']} | "
                f"{item['models']} | {', '.join(item['task_types'])} | "
                f"{item['created_at_first']} | {item['created_at_last']} |")


    if rep.get("duplicate_generation_detail"):
        lines += ["", "### Generations written more than once", "",
                  "| routing_result_id | kind | rows | models | satisfactions |",
                  "|---|---|---|---|---|"]
        for d in rep["duplicate_generation_detail"]:
            models_txt = ", ".join(d["models"][:4])
            if len(d["models"]) > 4:
                models_txt += f" (+{len(d['models']) - 4} more)"
            sats_txt = str(d["satisfactions"][:4])
            if len(d["satisfactions"]) > 4:
                sats_txt += " …"
            lines.append(
                f"| `{d['routing_result_id']}` | {d['kind']} | {d['rows']} | "
                f"{models_txt} | {sats_txt} |")
        lines += ["", "A duplicated row inflates any row-based denominator — one "
                      "generation must not be counted twice.", ""]

    lines += [
        "## 2. Cost per answer (the only basis for a cost comparison)",
        "",
        "Total spend depends on how many calls a model received, so it is NOT a "
        "cost-efficiency measure. `cost_per_answer` = **total recorded spend / "
        "answered generations**; the denominator is printed beside every figure. "
        "The numerator includes failed attempts (they are billed).",
        "",
        "| model | answered generations (denominator) | failed generations | total recorded cost | cost per answer | mean ms/answer | p95 ms/answer | quality-satisfied % of answers | mean sat/answer | rows w/o cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    cost_models = sorted(rep["by_model"].items(),
                         key=lambda kv: -kv[1]["answered_generations"])
    cost_shown = [(mm, aa) for mm, aa in cost_models
                  if aa["answered_generations"] > 0]
    for model, a in cost_shown:
        lines.append(
            f"| `{model}` | {a['answered_generations']} | {a['failed_generations']} | "
            f"{a['total_recorded_cost']} | {a['cost_per_answer']} | "
            f"{a['mean_latency_ms_per_answer']} | {a['p95_latency_ms_per_answer']} | "
            f"{a['quality_satisfied_pct_of_answers']} | "
            f"{a['mean_satisfaction_per_answer']} | {a['rows_without_cost']} |")
    no_answer_models = [mm for mm, aa in cost_models if aa["answered_generations"] == 0]
    if no_answer_models:
        lines += ["", f"_{len(no_answer_models)} model id(s) have no answered "
                      "generation, so no per-answer figure can exist for them "
                      "(they appear only in suspected candidate sweeps or "
                      "failed attempts): " + _fmt_models(no_answer_models) + "._"]

    sv = rep["savings"]
    lines += ["", "### Per-answer cost comparison", "",
              f"_Basis: {sv['basis']}; floor {sv['min_answered_generations']} "
              "answered generations per side._", ""]
    if sv.get("status") == "ok":
        c, p = sv["cheapest"], sv["priciest"]
        lines += [
            f"- Cheapest per answer: `{c['model']}` — **{c['cost_per_answer']}** "
            f"per answer over **{c['answered_generations']}** answered "
            f"generation(s) (total recorded cost {c['total_recorded_cost']}).",
            f"- Priciest per answer: `{p['model']}` — **{p['cost_per_answer']}** "
            f"per answer over **{p['answered_generations']}** answered "
            f"generation(s) (total recorded cost {p['total_recorded_cost']}).",
            f"- Difference per answer: **{sv['difference_per_answer']}** → "
            f"`{c['model']}` is **{sv['cheaper_by_pct_of_priciest']}%** cheaper "
            "per answer than "
            f"`{p['model']}`.",
            f"- Totals are not compared: {sv['totals_are_not_comparable']}.",
        ]
    else:
        lines.append(f"- **{sv['status']}** — {sv.get('note', '')}")
    if sv.get("excluded_small_denominator"):
        lines.append(
            "- Excluded for a denominator below the floor: "
            + ", ".join(f"`{d['model']}` ({d['answered_generations']})"
                        for d in sv["excluded_small_denominator"]) + ".")
    if sv.get("undefined_no_answers"):
        lines.append("- No per-answer figure (no answered generation): "
                     + _fmt_models(sv["undefined_no_answers"]) + ".")

    lines += [
        "",
        "## 3. Observed outcomes by task",
        "",
        "| task | rows | generations | answered generations | models (with an answer) | quality-satisfied % of answers |",
        "|---|---|---|---|---|---|",
    ]
    for task, a in sorted(rep["by_task"].items(),
                          key=lambda kv: -kv[1]["answered_generations"]):
        answered_models = a.get("models_with_answers", [])
        lines.append(f"| `{task}` | {a['rows']} | {a['generations']} | "
                     f"{a['answered_generations']} | {len(answered_models)} "
                     f"(of {len(a['models'])} ids present) | "
                     f"{a['quality_satisfied_pct_of_answers']} |")

    # ---- section 4: the real A/B ------------------------------------------
    ab = rep["ranker_ab"]
    lines += ["", "## 4. A/B of the ACTUAL rankers (BPC vs learned re-ranking)", "",
              f"_Status: **{ab.get('status')}**._", ""]
    if ab.get("status") == "ok":
        lines += [
            f"- Method: {ab['method']}.",
            "- The learned re-ranker can only PERMUTE the list BPC returned, so "
            "both rankers see an identical candidate set; "
            "`same_candidate_set` is asserted per run below.",
            f"- Learned-signal provenance: mode `{(ab.get('learned_signal') or {}).get('mode')}`, "
            f"settings `{(ab.get('learned_signal') or {}).get('settings')}`, "
            f"per-model predictor buckets "
            f"`{(ab.get('learned_signal') or {}).get('predictor_buckets')}`.",
            f"- Observed models (the {len(ab['inputs'].get('observed_models', []))} "
            "with at least one ANSWERED generation) — only these are ranked in "
            "the table below: "
            + ", ".join(f"`{mm}`" for mm in ab["inputs"].get("observed_models", [])) + ".",
            "- `per_model` bucket predictions are only present after an "
            "in-process retrain; when the bucket is empty the served learned "
            "signal is the EMA telemetry term keyed `tenant:task:model` (the "
            "documented cold-start handoff in `_rerank_with_learning`).",
            f"- Inputs: `{json.dumps(ab['inputs'], sort_keys=True)}`",
            "",
            "| task | est. tokens | complexity | candidates | same set | orders identical | BPC top | learned top | top changed | BPC rank → learned rank (observed models) |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for run in ab["runs"]:
            rank_pairs = ", ".join(
                f"`{mm}`={'-' if run['bpc_rank_of_observed'].get(mm) is None else run['bpc_rank_of_observed'][mm]}"
                f"→{'-' if run['learned_rank_of_observed'].get(mm) is None else run['learned_rank_of_observed'][mm]}"
                for mm in sorted(run["bpc_rank_of_observed"]))
            lines.append(
                f"| `{run['task_type']}` | {run['estimated_tokens']} | "
                f"{run['complexity']} | {run['candidates']} | "
                f"{run['same_candidate_set']} | {run['orders_identical']} | "
                f"`{run['bpc_top']}` | `{run['learned_top']}` | "
                f"{run['top_changed']} | {rank_pairs} |")
        n_runs = len(ab["runs"])
        n_diff = sum(1 for r in ab["runs"] if not r["orders_identical"])
        n_top = sum(1 for r in ab["runs"] if r["top_changed"])
        lines += [
            "",
            f"- Runs where the two rankers produced different orders: **{n_diff}/{n_runs}**; "
            f"runs where the TOP candidate changed: **{n_top}/{n_runs}**.",
            "",
            "**This is an ORDERING A/B, not an outcome A/B.** It shows what each "
            "ranker does with the same candidates and the same request features. "
            "It cannot show which order produces better answers: the alternative "
            "that was never executed still has no observed outcome. Certifying "
            "superiority requires an executed split "
            "(`ATOM_TRAFFIC_SPLIT`-style) or a persisted candidate-order log "
            "with counterfactual sampling.",
        ]
        served = (ab.get("learned_signal") or {}).get("served_by_tenant_task")
        if served:
            lines += ["", "| tenant:task bucket | per-model predictors served | EMA models served (with an observed answer) | EMA models total |",
                      "|---|---|---|---|"]
            for bucket, info in sorted(served.items()):
                observed_ema = info.get("ema_models_with_observed_answers", [])
                lines.append(
                    f"| `{bucket}` | {info['predictor_models'] or '*(none — cold predictor bucket)*'} | "
                    f"{observed_ema or '*(none)*'} | {len(info['ema_models'])} |")
    else:
        lines += [
            f"- Reason: {ab.get('error', 'live rankers not collected')}",
            "- **No claim about the learned router's order or BPC's order is "
            "made in this report.** The descriptive orderings in section 5 are "
            "explicitly NOT router outputs.",
        ]

    # ---- section 5: activation --------------------------------------------
    act = rep.get("activation")
    lines += ["", "## 5. Automatic activation: readiness, not superiority", ""]
    if act and not act.get("error"):
        lines += [
            f"- Mode `{act.get('mode')}` → re-ranking enabled: **{act.get('enabled')}**; "
            f"readiness check: **{act.get('ready')}**.",
            f"- Observations in the {act.get('thresholds', {}).get('window_days')}-day "
            f"window: **{act.get('rows_in_window')}**; models with >= "
            f"{act.get('thresholds', {}).get('min_observations_per_model')} "
            f"observations: **{act.get('models_with_enough_observations')}** "
            f"(thresholds: >={act.get('thresholds', {}).get('min_rows')} rows, "
            f">={act.get('thresholds', {}).get('min_models')} models).",
            f"- Reported reason: _{act.get('reason')}_",
            "",
            "_The readiness numbers come from a live re-query through the "
            "application engine at A/B time, so they can differ from the "
            "snapshot row count in §1 when the table is being written "
            "concurrently._",
            "",
            "**Effective behaviour: readiness threshold met; no executed "
            "comparison.** The threshold is a statement about statistical "
            "SUPPLY. It does not establish that re-ranking beats static BPC, "
            "and it cannot: the rows are outcomes of the model BPC already "
            "chose, so there is no counterfactual. The activation claim stands; "
            "what it is evidence OF is supply, not superiority.",
        ]
    else:
        lines.append("- Not collected "
                     f"({(act or {}).get('error', '--no-live-rankers')}).")

    # ---- section 6: holdout ------------------------------------------------
    h = rep["holdout"]
    lines += ["", "## 6. Held-out evaluation (observational)", ""]
    if h.get("status") != "ok":
        lines.append(f"- **{h.get('status')}** ({h.get('rows')} rows).")
    else:
        lines += [
            f"- Train {h['train_rows']} rows / holdout {h['holdout_rows']} rows "
            "(time-ordered split).",
            f"- `observed_satisfaction_ranking` (DESCRIPTIVE: train-slice "
            f"quality-satisfied rate desc — NOT the learned router): "
            f"`{h['observed_satisfaction_ranking']}`",
            f"- `historical_spend_ranking` (DESCRIPTIVE: train-slice total spend "
            f"asc — NOT BPC): `{h['historical_spend_ranking']}`",
            f"- Orderings require >= {h['ordering_min_answered_generations']} "
            f"answered generations; excluded: "
            f"{_fmt_models(h['models_excluded_small_sample'])}.",
            "",
            "| model | answered generations (denominator) | quality-satisfied % of answers | mean ms/answer | total recorded cost | cost per answer |",
            "|---|---|---|---|---|---|",
        ]
        for model, a in sorted(
                (kv for kv in h["holdout_by_model"].items()
                 if kv[1]["answered_generations"] > 0)):
            lines.append(
                f"| `{model}` | {a['answered_generations']} | "
                f"{a['quality_satisfied_pct_of_answers']} | "
                f"{a['mean_latency_ms_per_answer']} | {a['total_recorded_cost']} | "
                f"{a['cost_per_answer']} |")
        no_answer_holdout = sorted(
            mm for mm, a in h["holdout_by_model"].items()
            if a["answered_generations"] == 0)
        if no_answer_holdout:
            lines += ["", f"_{len(no_answer_holdout)} model id(s) in the holdout "
                          "slice have no answered generation and therefore no "
                          "per-answer figure: " + _fmt_models(no_answer_holdout) + "._"]
        hs = h.get("holdout_savings") or {}
        if hs.get("status") == "ok":
            c, p = hs["cheapest"], hs["priciest"]
            lines += [
                "",
                f"- Holdout cost per answer: `{c['model']}` **{c['cost_per_answer']}** "
                f"over **{c['answered_generations']}** answer(s) vs "
                f"`{p['model']}` **{p['cost_per_answer']}** over "
                f"**{p['answered_generations']}** answer(s) → difference "
                f"**{hs['difference_per_answer']}** per answer "
                f"({hs['cheaper_by_pct_of_priciest']}% of the higher per-answer "
                "cost).",
                f"- Totals are not compared: {hs['totals_are_not_comparable']}.",
            ]
        elif hs:
            lines += ["", f"- Holdout per-answer comparison: **{hs.get('status')}** "
                          f"— {hs.get('note', '')}"]
        lines += ["", f"**{h['verdict']}**"]

    lines += ["", "## 7. Limitations (read before trusting a horizon)", ""]
    lines += [f"- {x}" for x in rep["limitations"]]

    lines += ["", "## 8. Changelog — claims removed or renamed", "",
              "| claim | action | why |", "|---|---|---|"]
    for item in rep["changelog"]:
        lines.append(f"| {item['claim']} | {item['action']} | {item['why']} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="SQLite path (default: DATABASE_URL)")
    ap.add_argument("--json", default=None, help="also write the raw report as JSON")
    ap.add_argument("--markdown", default=None, help="write the rendered markdown here")
    ap.add_argument("--holdout-frac", type=float, default=0.3)
    ap.add_argument("--no-live-rankers", action="store_true",
                    help="skip the live BPC/learned A/B (descriptive sections only)")
    ap.add_argument("--ab-max-profiles", type=int, default=6,
                    help="maximum number of reconstructed request profiles to A/B")
    ap.add_argument("--min-model-rows", type=int, default=2,
                    help="hide models with fewer rows from the printed per-model "
                         "tables (they remain in --json); 1 prints everything")
    args = ap.parse_args(argv)

    db = os.path.abspath(args.db or _db_path_from_env())
    if not os.path.exists(db):
        print(f"database not found: {db}", file=sys.stderr)
        return 2

    # The application-side reads the A/B performs (learning-router hydration,
    # the fabrication bench, the readiness check) must hit the SAME database the
    # rows came from. Set before any application module is imported.
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"

    rows = load_rows(db)
    ranker_ab = None
    if not args.no_live_rankers:
        ranker_ab = live_ranker_ab(rows, max_profiles=args.ab_max_profiles)

    rep = build_report(rows, holdout_frac=args.holdout_frac, ranker_ab=ranker_ab,
                       source={"db": db, "rows_loaded": len(rows)},
                       min_model_rows=max(1, args.min_model_rows))
    md = render_markdown(rep)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
