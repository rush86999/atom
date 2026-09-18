# -*- coding: utf-8 -*-
"""Tests for ``scripts/router_evidence_report.py`` (audit item 3).

These cover the PURE computation only — synthetic rows, no live database, no
router imports. The properties under test are the ones the external review
called out:

* cost is per ANSWER with its denominator (never a raw total);
* a saving is never computed across different answer counts;
* the two orderings are named after what they MEASURE, and the router's own
  order is only ever produced by the real rankers (section 4 / ``ranker_ab``);
* fabrication/quality accounting is per GENERATION through
  ``core.llm.fabrication_accounting`` — unprovenanced generations stay
  UNKNOWN, never clean;
* candidate-sweep rows are not treated as executed attempts.
"""
from __future__ import annotations

import json

import pytest

from scripts.router_evidence_report import (
    MIN_COMPARABLE_ANSWERS,
    SWEEP_MIN_MODELS,
    _aggregate,
    _tokens_from_features,
    band_audit,
    build_generations,
    build_report,
    cost_per_answer,
    detect_candidate_sweeps,
    holdout_eval,
    per_answer_savings,
    render_markdown,
    request_profiles,
)


# ---------------------------------------------------------------------------
# Fixtures — rows shaped exactly like ``load_rows`` output
# ---------------------------------------------------------------------------

def _features(log_tokens: float = 8.0, bucket: float = 2.0, **kw) -> str:
    base = {
        "log_tokens": log_tokens,
        "token_bucket": bucket,
        "task_code": 0.0,
        "task_analysis": 0.0,
        "task_reasoning": 0.0,
        "task_chat": 0.0,
        "task_general": 1.0,
        "has_code": 0.0,
        "has_numbers": 0.0,
        "avg_word_length": 5.0,
        "intent_coding": 0.0,
        "intent_data_analysis": 0.0,
        "intent_web_browsing": 0.0,
        "intent_creative_writing": 0.0,
        "intent_reasoning": 0.0,
        "intent_conversation": 0.0,
    }
    base.update(kw)
    return json.dumps(base)


def _verdict_features(verdict: str, score: float = 0.9) -> str:
    feats = json.loads(_features())
    feats["verdict"] = verdict
    return json.dumps(feats)


_ROWS = 0


def _row(
    turn: str,
    model: str,
    *,
    success: bool = True,
    quality_satisfied: bool = True,
    satisfaction: float = 0.9,
    cost: float | None = 0.001,
    latency: float | None = 1000.0,
    task: str = "general",
    features: str | None = None,
    created_at: str = "2026-09-16 10:00:00",
    tenant: str = "default",
) -> dict:
    global _ROWS
    _ROWS += 1
    return {
        "id": f"row-{_ROWS}",
        "routing_result_id": turn,
        "tenant_id": tenant,
        "task_type": task,
        "model_id": model,
        "success": success,
        "quality_satisfied": quality_satisfied,
        "user_satisfaction": satisfaction,
        "actual_cost": cost,
        "actual_latency_ms": latency,
        "prompt_features": features if features is not None else _features(),
        "created_at": created_at,
    }


def _timed(n: int, model: str = "m-a", **kw) -> list:
    """``n`` rows on a rising clock, one generation each."""
    return [
        _row(f"t{i}", model, created_at=f"2026-09-16 10:{i:02d}:00", **kw)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Cost per answer
# ---------------------------------------------------------------------------

class TestCostPerAnswer:
    def test_divides_total_cost_by_answered_generations(self):
        rows = [
            _row("t1", "m-a", cost=0.20, satisfaction=0.9),
            _row("t2", "m-a", cost=0.10, satisfaction=0.9),
        ]
        agg = _aggregate(build_generations(rows))
        assert agg["answered_generations"] == 2  # the denominator
        assert agg["total_recorded_cost"] == 0.30
        assert agg["cost_per_answer"] == 0.15
        assert "2 answered generation" in agg["cost_per_answer_basis"]

    def test_undefined_without_an_answer_is_none_not_zero(self):
        # A rate with no denominator must not read as "free".
        assert cost_per_answer(0.5, 0) is None
        assert cost_per_answer(None, 3) is None
        assert cost_per_answer(0.5, 0) != 0.0

    def test_failed_attempt_cost_stays_in_the_numerator(self):
        rows = [
            _row("t1", "m-a", success=False, quality_satisfied=False,
                 satisfaction=0.0, cost=0.10),
            _row("t2", "m-a", cost=0.20),
        ]
        agg = _aggregate(build_generations(rows))
        assert agg["answered_generations"] == 1
        assert agg["failed_generations"] == 1
        # billed failure stays in the numerator; only the denominator moves
        assert agg["total_recorded_cost"] == 0.30
        assert agg["cost_per_answer"] == 0.30

    def test_duplicate_rows_do_not_inflate_the_answer_denominator(self):
        # One generation, written twice (outcome row + corrective row).
        rows = [
            _row("t1", "m-a", cost=0.10, satisfaction=0.9),
            _row("t1", "m-a", cost=0.10, satisfaction=0.9),
        ]
        gens = build_generations(rows)
        assert len(gens) == 1
        agg = _aggregate(gens)
        assert agg["rows"] == 2
        assert agg["generations"] == 1
        assert agg["answered_generations"] == 1
        assert agg["cost_per_answer"] == 0.20

    def test_telemetry_denominators_are_per_answer(self):
        rows = [
            _row("t1", "m-a", latency=1000.0, satisfaction=0.8),
            _row("t2", "m-a", latency=3000.0, satisfaction=0.6),
            _row("t3", "m-a", success=False, latency=None, satisfaction=0.0,
                 quality_satisfied=False),
        ]
        agg = _aggregate(build_generations(rows))
        assert agg["answered_generations"] == 2
        assert agg["mean_latency_ms_per_answer"] == 2000.0
        assert agg["mean_satisfaction_per_answer"] == 0.7
        assert agg["quality_satisfied_pct_of_answers"] == 100.0

    def test_rows_without_cost_are_counted(self):
        rows = [
            _row("t1", "m-a", cost=None),
            _row("t2", "m-a", cost=0.10),
        ]
        agg = _aggregate(build_generations(rows))
        assert agg["rows_without_cost"] == 1
        assert agg["total_recorded_cost"] == 0.10


# ---------------------------------------------------------------------------
# Savings — per answer, with both denominators, never from totals
# ---------------------------------------------------------------------------

class TestPerAnswerSavings:
    def _by_model(self):
        return {
            "cheap": _aggregate(build_generations(
                [_row(f"c{i}", "cheap", cost=0.01) for i in range(10)])),
            "pricey": _aggregate(build_generations(
                [_row(f"p{i}", "pricey", cost=0.03) for i in range(30)])),
        }

    def test_saving_is_computed_from_cost_per_answer(self):
        sv = per_answer_savings(self._by_model())
        assert sv["status"] == "ok"
        assert sv["cheapest"]["model"] == "cheap"
        assert sv["cheapest"]["answered_generations"] == 10
        assert sv["cheapest"]["cost_per_answer"] == 0.01
        assert sv["priciest"]["model"] == "pricey"
        assert sv["priciest"]["answered_generations"] == 30
        assert sv["priciest"]["cost_per_answer"] == 0.03
        assert sv["difference_per_answer"] == 0.02
        assert "10 vs 30" in sv["totals_are_not_comparable"]

    def test_refuses_to_compare_a_thin_denominator(self):
        by_model = {
            "thin": _aggregate(build_generations(
                [_row("x1", "thin", cost=0.10), _row("x2", "thin", cost=0.10)])),
            "fat": _aggregate(build_generations(
                [_row(f"y{i}", "fat", cost=0.50)
                 for i in range(MIN_COMPARABLE_ANSWERS)])),
        }
        sv = per_answer_savings(by_model)
        assert sv["status"] == "insufficient_denominators"
        assert "difference_per_answer" not in sv
        assert sv["excluded_small_denominator"][0]["model"] == "thin"
        assert sv["excluded_small_denominator"][0]["answered_generations"] == 2

    def test_models_with_no_answer_are_reported_undefined(self):
        by_model = {
            "no-answer": _aggregate(build_generations(
                [_row("z1", "no-answer", success=False, satisfaction=0.0,
                      quality_satisfied=False, cost=None)])),
        }
        sv = per_answer_savings(by_model)
        assert sv["status"] == "insufficient_denominators"
        assert sv["undefined_no_answers"] == ["no-answer"]


# ---------------------------------------------------------------------------
# Fabrication / quality accounting — generation level, provenance only
# ---------------------------------------------------------------------------

class TestFabricationAccounting:
    def test_low_score_without_verdict_is_unknown_not_clean(self):
        rows = [_row("t1", "m-a", satisfaction=0.0, quality_satisfied=False,
                     features="null")]
        band = band_audit(rows)
        assert band["rows_in_band"] == 1
        assert band["generations_in_band"] == 1
        assert band["generations_with_fabrication_verdict"] == 0
        assert band["generations_unprovenanced"] == 1
        assert band["generations_by_classification"] == {"unknown": 1}
        assert band["unprovenanced_are_unknown_not_clean"] is True

        rep = build_report(rows, ranker_ab={"status": "not_collected"})
        overall = rep["accounting"]["overall"]
        assert overall["unknown"] == 1
        assert overall["clean"] == 0        # never exonerated by absence
        assert overall["fabricated"] == 0
        assert overall["generations"] == 0  # not in the evaluated denominator
        assert overall["rate"] is None      # undefined, not 0.0

    def test_fabrication_verdict_is_counted_once_per_generation(self):
        # An outcome row AND a corrective-verdict row for ONE generation.
        rows = [
            _row("t1", "m-a", satisfaction=0.0, quality_satisfied=False),
            _row("t1", "m-a", satisfaction=0.0, quality_satisfied=False,
                 features=_verdict_features("unsupported_figures")),
        ]
        rep = build_report(rows, ranker_ab={"status": "not_collected"})
        overall = rep["accounting"]["overall"]
        assert overall["rows"] == 2
        assert overall["fabricated"] == 1   # not 2
        assert overall["generations"] == 1
        assert overall["rate"] == 1.0
        assert overall["duplicate_rows"] == 1

        band = rep["fabrication_band"]
        assert band["generations_with_fabrication_verdict"] == 1
        assert band["generations_unprovenanced"] == 0

    def test_unrecognised_verdict_stays_unknown(self):
        rows = [_row("t1", "m-a", satisfaction=0.02, quality_satisfied=False,
                     features=_verdict_features("something_new"))]
        overall = build_report(rows, ranker_ab={"status": "not_collected"})[
            "accounting"]["overall"]
        assert overall["unknown"] == 1
        assert overall["clean"] == 0
        assert overall["fabricated"] == 0

    def test_missing_score_is_not_read_as_zero(self):
        rows = [_row("t1", "m-a", satisfaction=None)]
        band = band_audit(rows)
        assert band["rows_in_band"] == 0
        assert band["rows_without_a_score"] == 1

    def test_availability_flag_is_reported_beside_provenance(self):
        rows = [_row("t1", "m-a", success=False, satisfaction=0.0,
                     quality_satisfied=False)]
        band = band_audit(rows)
        assert band["generations_availability_shaped_by_success_flag"] == 1
        # ...but it is NOT reclassified as availability by provenance
        assert band["generations_by_classification"] == {"unknown": 1}


# ---------------------------------------------------------------------------
# Descriptive orderings — renamed, and never called the router
# ---------------------------------------------------------------------------

class TestDescriptiveOrderings:
    def _rows(self):
        rows = []
        for i in range(10):
            rows.append(_row(f"a{i}", "model-a", quality_satisfied=True,
                             satisfaction=0.9, cost=0.01,
                             created_at=f"2026-09-16 10:{i:02d}:00"))
        for i in range(10):
            rows.append(_row(f"b{i}", "model-b", quality_satisfied=False,
                             satisfaction=0.1, cost=0.001,
                             created_at=f"2026-09-16 11:{i:02d}:00"))
        return rows

    def test_orders_are_named_for_what_they_measure(self):
        h = holdout_eval(self._rows(), 0.3)
        assert h["status"] == "ok"
        assert "observed_satisfaction_ranking" in h
        assert "historical_spend_ranking" in h
        # The legacy names asserted a router identity the statistics never had.
        assert "learned_order_from_train" not in h
        assert "static_cost_priority_order" not in h
        assert h["observed_satisfaction_ranking"][0] == "model-a"

    def test_holdout_never_declares_superiority(self):
        h = holdout_eval(self._rows(), 0.3)
        assert "INCONCLUSIVE" in h["verdict"]
        assert "SUPERIOR" in h["verdict"]

    def test_holdout_savings_are_per_answer_with_denominators(self):
        h = holdout_eval(self._rows(), 0.3)
        sv = h["holdout_savings"]
        assert sv["basis"].startswith("cost per ANSWERED generation")
        if sv["status"] == "ok":
            assert sv["cheapest"]["answered_generations"] > 0
            assert sv["priciest"]["answered_generations"] > 0

    def test_ordering_needs_a_real_denominator(self):
        rows = []
        for i in range(10):
            rows.append(_row(f"a{i}", "model-a",
                             created_at=f"2026-09-16 10:{i:02d}:00"))
            rows.append(_row(f"b{i}", "model-b",
                             created_at=f"2026-09-16 10:{i:02d}:30"))
        h = holdout_eval(rows, 0.5)
        assert h["observed_satisfaction_ranking"] == []
        assert h["historical_spend_ranking"] == []
        assert sorted(h["models_excluded_small_sample"]) == ["model-a", "model-b"]


# ---------------------------------------------------------------------------
# Candidate sweeps are not executed attempts
# ---------------------------------------------------------------------------

class TestCandidateSweeps:
    def _sweep_rows(self, models: int = SWEEP_MIN_MODELS + 1):
        return [
            _row("sweep-turn", f"cand-{i}", success=False, quality_satisfied=False,
                 satisfaction=0.0, cost=None, features=_features(log_tokens=1.0))
            for i in range(models)
        ]

    def test_detected_by_shape(self):
        sweep = detect_candidate_sweeps(self._sweep_rows())
        assert sweep["turn_count"] == 1
        assert sweep["rows"] == SWEEP_MIN_MODELS + 1
        assert sweep["model_count"] == SWEEP_MIN_MODELS + 1

    def test_a_multi_model_turn_with_costs_is_not_a_sweep(self):
        rows = [
            _row("fallback-turn", "m-a", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
            _row("fallback-turn", "m-b", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
            _row("fallback-turn", "m-c", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
            _row("fallback-turn", "m-d", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
            _row("fallback-turn", "m-e", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
            _row("fallback-turn", "m-f", success=False, satisfaction=0.0,
                 quality_satisfied=False, cost=0.001),
        ]
        assert detect_candidate_sweeps(rows)["turn_count"] == 0

    def test_sweep_is_reported_and_not_counted_as_answers(self):
        rows = self._sweep_rows() + [_row("real", "m-a", cost=0.02)]
        rep = build_report(rows, ranker_ab={"status": "not_collected"})
        t = rep["totals"]
        assert t["answered_generations"] == 1
        assert t["rows_from_suspected_candidate_sweeps"] == SWEEP_MIN_MODELS + 1
        assert t["failed_generations_from_suspected_candidate_sweeps"] == (
            SWEEP_MIN_MODELS + 1)
        assert rep["by_model"]["m-a"]["cost_per_answer"] == 0.02
        # the sweep-only models have no per-answer figure at all
        assert rep["by_model"]["cand-0"]["cost_per_answer"] is None

    def test_sweep_rows_do_not_create_request_profiles(self):
        rows = self._sweep_rows(8)
        assert request_profiles(rows) == []
        assert len(request_profiles(rows, exclude_turns=set())) == 1

    def test_band_audit_splits_sweep_shaped_generations(self):
        rows = self._sweep_rows() + [
            _row("real-low", "m-a", success=False, satisfaction=0.0,
                 quality_satisfied=False)]
        sweep_turns = {"sweep-turn"}
        band = band_audit(rows, sweep_turns)
        assert band["generations_availability_shaped_by_success_flag"] == (
            SWEEP_MIN_MODELS + 2)
        assert band["generations_availability_shaped_from_suspected_sweeps"] == (
            SWEEP_MIN_MODELS + 1)
        assert band["generations_availability_shaped_not_from_sweeps"] == 1


# ---------------------------------------------------------------------------
# Report assembly / rendering contracts
# ---------------------------------------------------------------------------

class TestReportAssembly:
    def _rows(self):
        return [_row(f"t{i}", "m-a", cost=0.01,
                     created_at=f"2026-09-16 10:{i:02d}:00") for i in range(12)]

    def test_option_implemented_is_the_preferred_one(self):
        rep = build_report(self._rows(), ranker_ab={"status": "ok", "runs": [],
                                                    "inputs": {}, "method": "x"})
        assert "preferred option" in rep["method"]["option_implemented"]
        assert "identical candidate set" in rep["method"]["option_implemented"]
        assert "REAL BPC" in rep["method"]["static_order"]
        assert "REAL learned re-ranker" in rep["method"]["learned_order"]

    def test_without_the_live_ab_no_router_claim_is_made(self):
        rep = build_report(self._rows(), ranker_ab=None)
        assert rep["ranker_ab"] == {"status": "not_collected"}
        assert "NOT COLLECTED" in rep["method"]["learned_order"]
        assert "NOT COLLECTED" in rep["method"]["static_order"]
        md = render_markdown(rep)
        assert "no executed comparison" in md or "No claim about the learned" in md

    def test_ranker_ab_block_is_echoed_verbatim(self):
        block = {
            "status": "ok",
            "method": "real implementations",
            "inputs": {"observed_models": ["m-a"]},
            "learned_signal": {"mode": "auto", "settings": {}, "predictor_buckets": []},
            "activation": {"mode": "auto", "enabled": True, "ready": True,
                           "rows_in_window": 12, "models_with_enough_observations": 2,
                           "thresholds": {"min_rows": 30, "min_models": 2,
                                          "min_observations_per_model": 8,
                                          "window_days": 7},
                           "reason": "active"},
            "runs": [{
                "task_type": "general", "token_bucket": 2.0, "estimated_tokens": 256,
                "complexity": "MODERATE", "candidates": 3, "same_candidate_set": True,
                "orders_identical": False, "bpc_top": "z", "learned_top": "m-a",
                "top_changed": True,
                "bpc_rank_of_observed": {"m-a": 2}, "learned_rank_of_observed": {"m-a": 0},
            }],
        }
        rep = build_report(self._rows(), ranker_ab=block)
        md = render_markdown(rep)
        assert "ORDERING A/B, not an outcome A/B" in md
        assert "readiness threshold met; no executed comparison" in md
        assert "1/1" in md

    def test_changelog_lists_the_removed_and_renamed_claims(self):
        rep = build_report(self._rows(), ranker_ab=None)
        md = render_markdown(rep)
        assert "## 8. Changelog" in md
        claims = " ".join(item["claim"] for item in rep["changelog"])
        assert "learned_order_from_train" in claims
        assert "static_cost_priority_order" in claims
        assert "cost/success" in claims
        # the renamed names are present, the old ones only as REMOVED claims
        assert "observed_satisfaction_ranking" in md
        assert "historical_spend_ranking" in md

    def test_generation_key_falls_back_to_the_row_id(self):
        rows = [_row(None, "m-a"), _row(None, "m-a")]
        gens = build_generations(rows)
        assert len(gens) == 2  # not silently merged into one generation

    def test_tokens_from_features_inverts_the_log2_encoding(self):
        assert _tokens_from_features({"log_tokens": 10.0}) == 1023
        assert _tokens_from_features({"log_tokens": 0.0}) == 1
        assert _tokens_from_features({}) is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
