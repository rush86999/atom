"""
Exchange memory maintenance tests — the automation half of the rated-
exchange learning loop: vector backfill, distillation of recurring
rejections into pattern lessons, and the opt-in shadow→enforce latch
(env kill-switch always wins; promotion is one-way).
"""

import os
os.environ.setdefault("TESTING", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.exchange_memory_maintenance as xm
from core.exchange_example_service import exchange_memory_mode


# ---------------------------------------------------------------------------
# Flag resolution now goes through runtime settings (env > db row > default)
# ---------------------------------------------------------------------------

def test_mode_defaults_to_shadow_without_env_or_row(monkeypatch):
    monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
    with patch("core.runtime_settings._db_snapshot", return_value={}):
        assert exchange_memory_mode() == "shadow"


def test_env_var_still_wins_as_kill_switch(monkeypatch):
    monkeypatch.setenv("ATOM_EXCHANGE_MEMORY", "off")
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_EXCHANGE_MEMORY": "enforce"}):
        assert exchange_memory_mode() == "off"


def test_persisted_row_flips_mode_when_env_unset(monkeypatch):
    monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_EXCHANGE_MEMORY": "enforce"}):
        assert exchange_memory_mode() == "enforce"


# ---------------------------------------------------------------------------
# Mock DB helper — supports the few query shapes the maintenance uses
# ---------------------------------------------------------------------------

class _Chain:
    """query(...) -> filter* -> (order_by)* -> limit* -> all/first."""

    def __init__(self, rows=None, first=None):
        self._rows = rows if rows is not None else []
        self._first = first

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._first


def _mock_db(label_rows=None, runtime_row=None):
    db = MagicMock()

    def query(*a, **k):
        # query() targets are model classes OR model attributes
        # (e.g. ExchangeExample.label is a Column) — resolve both.
        target = a[0] if a else None
        name = getattr(target, "__name__", None) or getattr(
            getattr(target, "table", None), "name", ""
        )
        if name in ("ExchangeExample", "exchange_examples"):
            return _Chain(rows=label_rows if label_rows is not None else [])
        if name in ("RuntimeSetting", "runtime_settings"):
            return _Chain(first=runtime_row)
        return _Chain()

    db.query.side_effect = query
    return db


def _example(label="negative", comment="wrong customer", query="email the customer",
             workspace="ws-1", embedded=True, consolidated=False):
    return SimpleNamespace(
        id=f"ex-{label}-{comment}-{query}", label=label, comment=comment,
        user_query=query, workspace_id=workspace,
        embedded=embedded, consolidated=consolidated,
    )


# ---------------------------------------------------------------------------
# Step 1: backfill
# ---------------------------------------------------------------------------

def test_backfill_reembeds_and_flags_rows():
    pending = [_example(embedded=False), _example(embedded=False)]
    db = _mock_db(label_rows=pending)
    with patch("core.exchange_example_service._write_vector", side_effect=[True, False]):
        fixed = xm._backfill_vectors(db)
    assert fixed == 1
    assert pending[0].embedded is True   # vector written → flag flipped
    assert pending[1].embedded is False  # write failed → retried next cycle
    assert db.commit.called


def test_backfill_noop_when_all_embedded():
    db = _mock_db(label_rows=[])
    with patch("core.exchange_example_service._write_vector") as wv:
        assert xm._backfill_vectors(db) == 0
    wv.assert_not_called()
    assert not db.commit.called


# ---------------------------------------------------------------------------
# Step 2: distill recurring comment-bearing rejections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recurring_rejections_distilled_into_one_pattern_lesson():
    community = [
        _example(query="email the customer", comment="wrong customer"),
        _example(query="email a customer", comment="forgot the signature"),
        _example(query="customer email please", comment="used the wrong customer"),
    ]
    db = _mock_db(label_rows=community)
    observe = AsyncMock()
    with patch.object(xm, "_distill_min", return_value=3), \
         patch("core.student_learning_service.auto_observe", observe):
        result = await xm._consolidate_recurring_negatives(db)

    assert result["lessons"] == 1
    assert result["rows_marked"] == 3
    assert observe.await_count == 1
    kwargs = observe.await_args.kwargs
    assert kwargs["observation_type"] == "human_correction"
    assert kwargs["details"]["distilled"] is True
    # The lesson quotes representative reasons — never a bare "avoid that".
    assert "wrong customer" in kwargs["summary"]
    assert "forgot the signature" in kwargs["summary"]
    assert all(r.consolidated for r in community)
    assert db.commit.called


@pytest.mark.asyncio
async def test_below_threshold_is_not_distilled():
    community = [
        _example(query="email the customer", comment="wrong customer"),
        _example(query="email a customer", comment="forgot signature"),
    ]
    db = _mock_db(label_rows=community)
    observe = AsyncMock()
    with patch.object(xm, "_distill_min", return_value=3), \
         patch("core.student_learning_service.auto_observe", observe):
        result = await xm._consolidate_recurring_negatives(db)
    assert result["lessons"] == 0
    assert observe.await_count == 0
    assert all(not r.consolidated for r in community)
    assert not db.commit.called


@pytest.mark.asyncio
async def test_already_consolidated_rows_are_not_distilled_again():
    db = _mock_db(label_rows=[])  # the query filters consolidated rows out
    observe = AsyncMock()
    with patch("core.student_learning_service.auto_observe", observe):
        result = await xm._consolidate_recurring_negatives(db)
    assert result["lessons"] == 0
    assert observe.await_count == 0


@pytest.mark.asyncio
async def test_regenerate_only_bucket_yields_no_reasons_but_still_distills():
    community = [
        _example(query="draft the report", comment="regenerated"),
        _example(query="draft a report", comment="regenerated"),
        _example(query="report draft please", comment="too vague"),
    ]
    db = _mock_db(label_rows=community)
    observe = AsyncMock()
    with patch.object(xm, "_distill_min", return_value=3), \
         patch("core.student_learning_service.auto_observe", observe):
        await xm._consolidate_recurring_negatives(db)
    summary = observe.await_args.kwargs["summary"]
    assert "too vague" in summary
    assert "no reason recorded" not in summary


# ---------------------------------------------------------------------------
# Step 3: opt-in auto-promotion
# ---------------------------------------------------------------------------

def _healthy_counts():
    return [("positive",)] * 12 + [("negative",)] * 10


@pytest.mark.asyncio
async def test_auto_promote_disabled_by_default(monkeypatch):
    with patch.object(xm, "_auto_promote_exchange", return_value=False):
        result = xm._maybe_auto_promote(_mock_db())
    assert result == {"promoted": False, "reason": "auto_promote_disabled"}


@pytest.mark.asyncio
async def test_explicit_env_is_a_kill_switch_automation_never_fights(monkeypatch):
    monkeypatch.setenv("ATOM_EXCHANGE_MEMORY", "shadow")  # operator-pinned
    db = _mock_db(label_rows=_healthy_counts())
    with patch.object(xm, "_auto_promote_exchange", return_value=True), \
         patch("core.exchange_example_service.exchange_memory_mode",
               return_value="shadow"):
        result = xm._maybe_auto_promote(db)
    assert result == {"promoted": False, "reason": "explicit_env_kill_switch"}
    assert not db.add.called


@pytest.mark.asyncio
async def test_auto_promote_latches_shadow_to_enforce(monkeypatch):
    monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
    db = _mock_db(label_rows=_healthy_counts())
    invalidate = MagicMock()
    with patch.object(xm, "_auto_promote_exchange", return_value=True), \
         patch("core.exchange_example_service.exchange_memory_mode",
               return_value="shadow"), \
         patch("core.runtime_settings.invalidate_settings_cache", invalidate):
        result = xm._maybe_auto_promote(db)

    assert result["promoted"] is True
    row = db.add.call_args[0][0]
    assert row.key == "ATOM_EXCHANGE_MEMORY"
    assert row.value_json == "enforce"
    assert row.updated_by == "exchange_maintenance"
    assert db.commit.called
    assert invalidate.called


@pytest.mark.asyncio
async def test_auto_promote_skips_small_corpus(monkeypatch):
    monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
    db = _mock_db(label_rows=[("positive",)] * 5 + [("negative",)] * 2)
    with patch.object(xm, "_auto_promote_exchange", return_value=True), \
         patch("core.exchange_example_service.exchange_memory_mode",
               return_value="shadow"):
        result = xm._maybe_auto_promote(db)
    assert result["promoted"] is False
    assert result["reason"] == "corpus_too_small"
    assert not db.add.called


@pytest.mark.asyncio
async def test_auto_promote_never_demotes_enforce(monkeypatch):
    monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
    db = _mock_db(label_rows=_healthy_counts())
    with patch.object(xm, "_auto_promote_exchange", return_value=True), \
         patch("core.exchange_example_service.exchange_memory_mode",
               return_value="enforce"):
        result = xm._maybe_auto_promote(db)
    assert result["reason"] == "mode_is_enforce"
    assert not db.add.called


# ---------------------------------------------------------------------------
# Cycle: steps are fault-isolated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cycle_survives_a_failing_step(monkeypatch):
    db = _mock_db(label_rows=_healthy_counts())
    with patch.object(xm, "_backfill_vectors", side_effect=RuntimeError("lance down")), \
         patch.object(xm, "_auto_promote_exchange", return_value=False), \
         patch.object(xm, "_auto_promote_panel", return_value=False), \
         patch("core.student_learning_service.auto_observe", AsyncMock()):
        summary = await xm.run_maintenance_cycle(db)
    assert summary["backfilled"] == 0
    assert summary["promoted"]["reason"] == "auto_promote_disabled"
    assert summary["promoted_panel"]["reason"] == "auto_promote_disabled"
    assert "distilled" in summary
