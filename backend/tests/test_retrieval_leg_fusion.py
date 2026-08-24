"""R83 #4 — multi-leg rank fusion A/B arm (off | rrf | linear).

The arm ships OFF by default: the only in-repo benchmark data on rank
fusion (HERMES_COMPARISON.md, Hermes LongMemEval-S subset) disfavors RRF
(0.61 acc vs 0.66 pure vector), so promotion out of ``off`` requires
clearing the P2.3 memory_eval recall@k gate per arm. These tests lock the
combiner math, the fail-closed default, and off-mode byte parity with the
legacy union.
"""
from __future__ import annotations

import pytest

from core.hybrid_search.leg_fusion import (
    MODE_LINEAR,
    MODE_OFF,
    MODE_RRF,
    RRF_K,
    fuse_legs,
    get_fusion_mode,
    get_linear_weights,
)


LEGS = {"vector": ["a", "b", "c"], "keyword": ["b", "d"]}


@pytest.mark.unit
def test_default_mode_is_off():
    """Snapshot: the A/B arm must not leave `off` without the eval gate."""
    import os

    saved = os.environ.pop("ATOM_RETRIEVAL_FUSION", None)
    try:
        assert get_fusion_mode() == MODE_OFF
    finally:
        if saved is not None:
            os.environ["ATOM_RETRIEVAL_FUSION"] = saved


@pytest.mark.unit
def test_invalid_mode_fails_closed_to_off(monkeypatch):
    monkeypatch.setenv("ATOM_RETRIEVAL_FUSION", "bogus")
    assert get_fusion_mode() == MODE_OFF
    # An invalid live value must not reorder anything either.
    ranked, scores = fuse_legs(LEGS)
    assert ranked == ["a", "b", "c", "d"]
    assert scores == {}


@pytest.mark.unit
def test_off_is_legacy_union_parity():
    """off == the pre-R83 vector-then-keyword union, byte for byte."""
    ranked, scores = fuse_legs(LEGS, MODE_OFF)
    assert ranked == ["a", "b", "c", "d"]
    assert scores == {}


@pytest.mark.unit
def test_rrf_known_values():
    ranked, scores = fuse_legs(LEGS, MODE_RRF)
    # b appears in both legs: rank 2 vector + rank 1 keyword.
    assert scores["b"] == pytest.approx(1.0 / (RRF_K + 2) + 1.0 / (RRF_K + 1))
    assert scores["a"] == pytest.approx(1.0 / (RRF_K + 1))
    # b (two legs) first; d (keyword rank 2, 1/62) beats c (vector rank 3, 1/63).
    assert ranked == ["b", "a", "d", "c"]


@pytest.mark.unit
def test_linear_equal_weights_known_values():
    ranked, scores = fuse_legs(LEGS, MODE_LINEAR)
    # vector norms: a=1.0, b=0.5, c=0.0; keyword norms (n=2): b=1.0, d=0.0.
    assert scores["a"] == pytest.approx(0.5)
    assert scores["b"] == pytest.approx(0.25 + 0.5)
    assert scores["c"] == pytest.approx(0.0)
    assert scores["d"] == pytest.approx(0.0)
    # c and d tie at 0 — c wins by first-seen (vector leg, earlier rank).
    assert ranked == ["b", "a", "c", "d"]


@pytest.mark.unit
def test_linear_weights_env_and_override(monkeypatch):
    monkeypatch.setenv("ATOM_RETRIEVAL_LINEAR_WEIGHTS", "1.0,0.0")
    assert get_linear_weights() == (1.0, 0.0)
    # Keyword leg fully de-weighted → pure vector order.
    ranked, _ = fuse_legs(LEGS, MODE_LINEAR)
    assert ranked == ["a", "b", "c", "d"]


@pytest.mark.unit
def test_linear_invalid_weights_fall_back_to_equal(monkeypatch):
    monkeypatch.setenv("ATOM_RETRIEVAL_LINEAR_WEIGHTS", "nope")
    assert get_linear_weights() == (0.5, 0.5)
    monkeypatch.setenv("ATOM_RETRIEVAL_LINEAR_WEIGHTS", "0.5")
    assert get_linear_weights() == (0.5, 0.5)  # wrong arity → equal


@pytest.mark.unit
def test_single_hit_leg_scores_one():
    ranked, scores = fuse_legs({"vector": ["x"], "keyword": []}, MODE_LINEAR)
    assert scores["x"] == pytest.approx(0.5)  # weight 0.5 × norm 1.0
    assert ranked == ["x"]


@pytest.mark.unit
def test_empty_legs_return_empty():
    for mode in (MODE_OFF, MODE_RRF, MODE_LINEAR):
        ranked, scores = fuse_legs({"vector": [], "keyword": []}, mode)
        assert ranked == []
        assert scores in ({}, {"": 0.0}) or all(v == 0 for v in scores.values()) or scores == {}


@pytest.mark.unit
def test_graphrag_local_search_wired_to_fusion_seam():
    """The fusion arm must actually be reachable from the memory legs."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "graphrag_engine.py"
    ).read_text(encoding="utf-8")
    assert "from core.hybrid_search.leg_fusion import" in src
    assert "get_fusion_mode" in src
