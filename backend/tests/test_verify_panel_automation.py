"""
Verification-panel automation tests: ATOM_VERIFY_PANEL resolution through
runtime settings (env kill-switch wins), fire-and-forget run persistence
(the evidence base), stats, and the opt-in shadow→enforce latch gates.
"""

import os
os.environ.setdefault("TESTING", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.exchange_memory_maintenance as xm
import core.verify_panel as vp
from core.hallucination_config import get_verify_panel_mode
from core.verify_panel import VerifyVerdict, get_panel_run_stats


# ---------------------------------------------------------------------------
# Flag resolution (runtime settings: explicit env > db row > "auto")
# ---------------------------------------------------------------------------

def test_panel_default_setting_is_auto_effective_shadow(monkeypatch):
    monkeypatch.delenv("ATOM_VERIFY_PANEL", raising=False)
    with patch("core.runtime_settings._db_snapshot", return_value={}):
        assert get_verify_panel_mode() == "shadow"  # auto behaves as shadow
    from core.settings_catalog import find_spec

    assert find_spec("ATOM_VERIFY_PANEL").default == "auto"


def test_panel_env_wins_over_persisted_row(monkeypatch):
    monkeypatch.setenv("ATOM_VERIFY_PANEL", "off")
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_VERIFY_PANEL": "enforce"}):
        assert get_verify_panel_mode() == "off"


def test_panel_persisted_row_flips_mode(monkeypatch):
    monkeypatch.delenv("ATOM_VERIFY_PANEL", raising=False)
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_VERIFY_PANEL": "enforce"}):
        assert get_verify_panel_mode() == "enforce"


def test_panel_persisted_auto_is_effective_shadow(monkeypatch):
    monkeypatch.delenv("ATOM_VERIFY_PANEL", raising=False)
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_VERIFY_PANEL": "auto"}):
        assert get_verify_panel_mode() == "shadow"


def test_panel_garbage_mode_falls_back_to_off(monkeypatch):
    monkeypatch.delenv("ATOM_VERIFY_PANEL", raising=False)
    with patch("core.runtime_settings._db_snapshot",
               return_value={"ATOM_VERIFY_PANEL": "whenever"}):
        assert get_verify_panel_mode() == "off"


# ---------------------------------------------------------------------------
# Run persistence (the evidence base)
# ---------------------------------------------------------------------------

def _mock_db():
    return MagicMock()


@pytest.mark.asyncio
async def test_verify_reply_records_successful_run():
    vote = SimpleNamespace(
        winner=VerifyVerdict(grounded=False, unsupported_claims=["x"]),
        agreement_ratio=0.9, level="high", valid_count=3, fanout_targets=[],
    )
    voter = MagicMock()
    voter.vote_with_consensus = AsyncMock(return_value=vote)
    db = _mock_db()
    with patch("core.verify_panel.SelfConsistencyVoter", return_value=voter), \
         patch("core.database.SessionLocal", return_value=db):
        result = await vp.verify_reply("answer", "evidence", handler=MagicMock())
        import asyncio as _asyncio
        await _asyncio.sleep(0.1)  # let the fire-and-forget record land

    assert result["ran"] is True and result["grounded"] is False
    row = db.add.call_args[0][0]
    assert row.ran is True
    assert row.grounded is False
    assert row.agreement == 0.9
    assert row.samples == 3


@pytest.mark.asyncio
async def test_verify_reply_records_empty_input_failure():
    db = _mock_db()
    with patch("core.database.SessionLocal", return_value=db):
        result = await vp.verify_reply("", "", handler=MagicMock())
        import asyncio as _asyncio
        await _asyncio.sleep(0.1)
    assert result["ran"] is False
    row = db.add.call_args[0][0]
    assert row.ran is False
    assert "empty" in (row.error or "")


@pytest.mark.asyncio
async def test_persistence_failure_never_breaks_the_reply():
    vote = SimpleNamespace(
        winner=VerifyVerdict(grounded=True), agreement_ratio=1.0,
        level="high", valid_count=3, fanout_targets=[],
    )
    voter = MagicMock()
    voter.vote_with_consensus = AsyncMock(return_value=vote)
    broken = MagicMock()
    broken.commit.side_effect = RuntimeError("db down")
    with patch("core.verify_panel.SelfConsistencyVoter", return_value=voter), \
         patch("core.database.SessionLocal", return_value=broken):
        result = await vp.verify_reply("answer", "evidence", handler=MagicMock())
        import asyncio as _asyncio
        await _asyncio.sleep(0.1)
    assert result["ran"] is True  # reply path untouched


def test_get_panel_run_stats():
    rows = [
        SimpleNamespace(ran=True, agreement=0.9),
        SimpleNamespace(ran=True, agreement=0.7),
        SimpleNamespace(ran=False, agreement=None),
    ]
    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = rows
    stats = get_panel_run_stats(db)
    assert stats == {"total": 3, "ran": 2, "ran_rate": 0.667, "mean_agreement": 0.8}


# ---------------------------------------------------------------------------
# Opt-in shadow→enforce latch
# ---------------------------------------------------------------------------

def _healthy_stats():
    return {"total": 25, "ran": 24, "ran_rate": 0.96, "mean_agreement": 0.85}


def _resolved(value="auto", source="db"):
    """Stand-in for runtime_settings.resolve_setting's result."""
    return SimpleNamespace(value=value, source=source)


def _latch_db():
    """DB mock whose RuntimeSetting lookup finds no existing row, so the
    latch takes the create path (db.add)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_panel_promote_only_in_auto_mode():
    db = _mock_db()
    with patch("core.runtime_settings.resolve_setting", return_value=_resolved("shadow")):
        result = xm._maybe_auto_promote_panel(db)
    assert result == {"promoted": False, "reason": "mode_pinned_shadow"}


@pytest.mark.asyncio
async def test_panel_env_sourced_auto_is_never_latched(monkeypatch):
    monkeypatch.setenv("ATOM_VERIFY_PANEL", "auto")  # operator-pinned via env
    db = _mock_db()
    with patch("core.runtime_settings.resolve_setting", return_value=_resolved("auto", "env")):
        result = xm._maybe_auto_promote_panel(db)
    assert result["reason"] == "explicit_env_kill_switch"
    assert not db.add.called


@pytest.mark.asyncio
async def test_panel_promote_latches_on_healthy_record():
    db = _latch_db()
    invalidate = MagicMock()
    with patch("core.runtime_settings.resolve_setting", return_value=_resolved("auto")), \
         patch("core.verify_panel.get_panel_run_stats",
               return_value=_healthy_stats()), \
         patch("core.runtime_settings.invalidate_settings_cache", invalidate):
        result = xm._maybe_auto_promote_panel(db)

    assert result["promoted"] is True
    row = db.add.call_args[0][0]
    assert row.key == "ATOM_VERIFY_PANEL"
    assert row.value_json == "enforce"
    assert db.commit.called and invalidate.called


@pytest.mark.asyncio
async def test_panel_promote_gates_on_evidence():
    db = _mock_db()
    cases = [
        ({"total": 5, "ran": 5, "ran_rate": 1.0, "mean_agreement": 0.9},
         "not_enough_runs"),
        ({"total": 30, "ran": 12, "ran_rate": 0.4, "mean_agreement": 0.9},
         "panel_flaky"),
        ({"total": 30, "ran": 29, "ran_rate": 0.97, "mean_agreement": 0.2},
         "votes_not_meaningful"),
    ]
    with patch("core.runtime_settings.resolve_setting", return_value=_resolved("auto")):
        for stats, expected in cases:
            with patch("core.verify_panel.get_panel_run_stats", return_value=stats):
                result = xm._maybe_auto_promote_panel(db)
            assert result["reason"] == expected, stats
            assert result["promoted"] is False
    assert not db.add.called


@pytest.mark.asyncio
async def test_panel_pinned_enforce_never_moves():
    db = _mock_db()
    with patch("core.runtime_settings.resolve_setting", return_value=_resolved("enforce")):
        result = xm._maybe_auto_promote_panel(db)
    assert result["reason"] == "mode_pinned_enforce"
    assert not db.add.called


@pytest.mark.asyncio
async def test_cycle_includes_panel_step_and_isolates_failures():
    db = _mock_db()
    with patch.object(xm, "_backfill_vectors", side_effect=RuntimeError("x")), \
         patch("core.exchange_example_service.exchange_memory_setting",
               return_value=("off", "db")), \
         patch("core.runtime_settings.resolve_setting", return_value=_resolved("auto")), \
         patch("core.verify_panel.get_panel_run_stats",
               return_value=_healthy_stats()), \
         patch("core.runtime_settings.invalidate_settings_cache", MagicMock()), \
         patch("core.student_learning_service.auto_observe", AsyncMock()):
        summary = await xm.run_maintenance_cycle(db)
    assert summary["backfilled"] == 0
    assert summary["promoted_panel"]["promoted"] is True
    assert summary["promoted"]["reason"] == "mode_pinned_off"
    assert "distilled" in summary
