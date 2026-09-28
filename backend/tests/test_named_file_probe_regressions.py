"""Named-file probe regressions — the short form and the cached-miss defect.

Two things are pinned here, both from live observation on 2026-09-27:

1. The SHORT form ("what is the list price for U-22 and SLE24-16?") must resolve
   the same rows the eight-item form does. It is the simpler request, so a
   failure here is not a scale problem.

2. A probe MISS must not be frozen. `_probe_cached` used to cache `None` for the
   full positive TTL, so one transient read failure published "no matching row
   in the indexed content searched" for five minutes — for rows that were
   present, and that the very next probe resolves. A false absence claim, built
   by a cache, from data that was never actually read.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

import pytest


# --------------------------------------------------------------------------- #
# The miss must not be frozen
# --------------------------------------------------------------------------- #

def _entries(tmp_path: Path) -> List[Dict[str, Any]]:
    parquet = tmp_path / "linmac.parquet"
    pd = pytest.importorskip("pandas")
    pd.DataFrame({
        "Part Number": ["U-22", "SLE24-16", "GSL48-16"],
        "List Price": [1777.0, 8880.0, 640.0],
    }).to_parquet(parquet)
    return [{
        "file_name": "Consolidated Price List 2019.xlsx",
        "dataset_name": "linmac",
        "entity_name": "linmac",
        "parquet_path": str(parquet),
        "content_hash": "abc123",
        "external_id": "ext-1",
    }]


def test_a_transient_probe_failure_does_not_become_a_five_minute_absence(
    tmp_path, monkeypatch
):
    """The regression, exactly as observed.

    A probe that fails once (here: the parquet read raises, standing in for the
    data directory being rebuilt mid-turn) used to be cached as a miss for the
    full positive TTL. Every later turn then reported the row as absent while a
    fresh probe resolved it immediately.
    """
    from core import sheet_dataset_service as svc

    entries = _entries(tmp_path)
    monkeypatch.setattr(svc, "_PROBE_CACHE", {})
    monkeypatch.setattr(svc, "_PROBE_CACHE_TTL_S", 300.0)
    real = svc._probe_sheet_hits
    state = {"fail": True}

    def _flaky(entries_, token, max_rows):
        if state["fail"]:
            return None          # stands in for a transient read failure
        return real(entries_, token, max_rows)

    monkeypatch.setattr(svc, "_probe_sheet_hits", _flaky)

    # Turn 1: the probe fails.
    assert svc._probe_cached(entries, "U-22", 8) is None

    # The data recovers immediately (the rebuild finishes).
    state["fail"] = False

    # Turn 2, still inside the 300s POSITIVE ttl: the miss must NOT be served.
    # Before the fix this returned the cached None and the turn reported
    # "no matching row in the indexed content searched".
    hit = svc._probe_cached(entries, "U-22", 8)
    assert hit, (
        "a cached MISS was served for a row that is present — this is the "
        "false-absence defect"
    )


def test_a_miss_costs_a_re_read_and_that_is_the_deliberate_trade(
    tmp_path, monkeypatch
):
    """State the cost honestly instead of pretending it away.

    Not caching a miss means a genuinely-absent identifier re-reads the parquet
    on each probe. That is a real cost and it is bounded by the per-turn budget
    (probes run per requested item per turn). It is paid deliberately: the
    alternative was a cache that reported rows as absent without having read
    them. The knob exists for anyone who would rather buy the read back.
    """
    from core import sheet_dataset_service as svc

    entries = _entries(tmp_path)
    monkeypatch.setattr(svc, "_PROBE_CACHE", {})

    calls = {"n": 0}
    real = svc._probe_sheet_hits

    def _counting(entries_, token, max_rows):
        calls["n"] += 1
        return real(entries_, token, max_rows)

    monkeypatch.setattr(svc, "_probe_sheet_hits", _counting)

    assert svc._PROBE_NEGATIVE_CACHE_TTL_S == 0.0, (
        "negative caching is off by default; a miss must never be frozen")
    assert svc._probe_cached(entries, "NOT-A-REAL-CODE", 8) is None
    n = calls["n"]
    assert svc._probe_cached(entries, "NOT-A-REAL-CODE", 8) is None
    assert calls["n"] == n + 1, "a repeated miss re-reads, by design"

    # The knob still works for an operator who wants the read back.
    monkeypatch.setattr(svc, "_PROBE_NEGATIVE_CACHE_TTL_S", 30.0)
    svc._probe_cached(entries, "NOT-A-REAL-CODE", 8)
    n2 = calls["n"]
    svc._probe_cached(entries, "NOT-A-REAL-CODE", 8)
    assert calls["n"] == n2, "an explicitly re-enabled negative TTL must cache"


def test_positive_cache_still_serves_hits_for_the_full_ttl(tmp_path, monkeypatch):
    """The fix must not cost the read we were actually paying to avoid."""
    from core import sheet_dataset_service as svc

    entries = _entries(tmp_path)
    monkeypatch.setattr(svc, "_PROBE_CACHE", {})
    monkeypatch.setattr(svc, "_PROBE_CACHE_TTL_S", 300.0)

    calls = {"n": 0}
    real = svc._probe_sheet_hits

    def _counting(entries_, token, max_rows):
        calls["n"] += 1
        return real(entries_, token, max_rows)

    monkeypatch.setattr(svc, "_probe_sheet_hits", _counting)

    first = svc._probe_cached(entries, "U-22", 8)
    assert first
    n = calls["n"]
    assert svc._probe_cached(entries, "U-22", 8)
    assert calls["n"] == n, "a hit must stay cached for the full positive TTL"


def test_cache_entries_carry_the_negative_marker(tmp_path, monkeypatch):
    """The stored tuple gained a third element; a stale 2-tuple left anywhere
    would raise on unpack, so the shape is pinned — and so is WHICH results are
    stored at all."""
    from core import sheet_dataset_service as svc

    entries = _entries(tmp_path)
    monkeypatch.setattr(svc, "_PROBE_CACHE", {})

    svc._probe_cached(entries, "U-22", 8)
    svc._probe_cached(entries, "NOPE-1", 8)

    # Default: a hit is cached and flagged; a miss is not stored at all.
    assert [v[2] for v in svc._PROBE_CACHE.values()] == [False]
    assert len(svc._PROBE_CACHE) == 1, svc._PROBE_CACHE

    # With the knob enabled, both are stored and flagged distinctly.
    svc._PROBE_CACHE.clear()
    monkeypatch.setattr(svc, "_PROBE_NEGATIVE_CACHE_TTL_S", 30.0)
    svc._probe_cached(entries, "U-22", 8)
    svc._probe_cached(entries, "NOPE-1", 8)
    assert sorted(v[2] for v in svc._PROBE_CACHE.values()) == [False, True]


# --------------------------------------------------------------------------- #
# The short form resolves what the long form resolves
# --------------------------------------------------------------------------- #

def test_short_form_yields_the_same_items_as_the_eight_item_form():
    """Both forms must name the same requested set.

    The short form is the SIMPLER request, so if it diverges from the long one
    the divergence is in interpretation or source selection, not in scale.
    """
    from core.chat_tool_planner import _resolve_active_items
    from core.sheet_dataset_service import candidate_probe_tokens

    short = ("In Consolidated Price List 2019.xlsx, what is the list price "
             "for U-22 and SLE24-16?")
    eight = ("find 8 machine prices in Consolidated Price List 2019.xlsx: 381, "
             "U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, "
             "TK Multi Wheel Gang Slitter, GSL48-16")

    short_items = _resolve_active_items(short, {}, candidate_probe_tokens)
    eight_items = _resolve_active_items(eight, {}, candidate_probe_tokens)

    assert "U-22" in short_items, short_items
    assert "SLE24-16" in short_items, short_items
    for item in short_items:
        assert item in eight_items, (
            f"{item!r} resolved from the short form but not the long one — the "
            "two forms must agree on the requested set")


def test_short_form_preserves_identifier_order():
    from core.chat_tool_planner import _resolve_active_items
    from core.sheet_dataset_service import candidate_probe_tokens

    short = ("In Consolidated Price List 2019.xlsx, what is the list price "
             "for U-22 and SLE24-16?")
    items = _resolve_active_items(short, {}, candidate_probe_tokens)
    assert items.index("U-22") < items.index("SLE24-16"), items
