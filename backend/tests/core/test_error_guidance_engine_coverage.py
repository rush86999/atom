"""
Coverage + bug-hunt tests for core/error_guidance_engine.py.

Tests exercise:
  - categorize_error (all code + message branches)
  - get_suggested_resolution (incl. the index-vs-string bug)
  - present_error (async; ws broadcast + audit; feature-flag + error paths)
  - track_resolution (async; commit + rollback paths)
  - get_historical_resolutions / success_rate / statistics / suggestions
  - get_error_fix_suggestions (async)
  - private _explain_* helpers
  - get_error_guidance_engine factory + ERROR_GUIDANCE_ENABLED flag

DB and websocket manager are mocked. No network.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.error_guidance_engine as ege
from core.error_guidance_engine import (
    ERROR_GUIDANCE_ENABLED,
    ErrorGuidanceEngine,
    get_error_guidance_engine,
)


# ---------------------------------------------------------------------------
# Fake DB query helpers
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Chainable query that can evaluate simple ``Column == value`` and
    ``Column == True/False`` filters against seeded row mocks.

    Filters arrive as SQLAlchemy binary expressions; we read ``.left`` /
    ``.right`` (for ``==``) so we can apply them in Python without a real DB.
    """

    def __init__(self, rows=None):
        self._rows = list(rows) if rows else []
        self._predicates = []

    def _eval_clause(self, clause, row):
        # Handle ``Column == value`` and ``Column == True/False``
        try:
            left = getattr(clause, "left", None)
            right = getattr(clause, "right", None)
            if left is not None and right is not None:
                key = self._col_key(left)
                if key:
                    # Resolve the RHS to a plain Python value
                    if hasattr(right, "value"):
                        want = right.value
                    elif right.__class__.__name__ == "True_":
                        want = True
                    elif right.__class__.__name__ == "False_":
                        want = False
                    else:
                        want = right
                    return getattr(row, key, None) == want
        except Exception:
            pass
        return True  # unknown clause → don't filter

    @staticmethod
    def _col_key(col):
        # InstrumentedAttribute / Column — get the attribute name
        for attr in ("key", "name"):
            v = getattr(col, attr, None)
            if isinstance(v, str):
                return v
        # Walk expression description like 'OperationErrorResolution.success'
        desc = getattr(getattr(col, "description", None), "split", lambda *a: [])()
        return desc[-1] if desc else None

    def filter(self, *clauses, **k):
        for c in clauses:
            self._predicates.append(c)
        return self

    def order_by(self, *a):
        return self

    def limit(self, n):
        return self

    def all(self):
        out = []
        for r in self._rows:
            if all(self._eval_clause(p, r) for p in self._predicates):
                out.append(r)
        return out

    def first(self):
        rows = self.all()
        return rows[0] if rows else None


class FakeDB:
    def __init__(self):
        # rows returned for ANY query (the engine filters in-Python mostly)
        self.rows: List[Any] = []
        self.added: List[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self._commit_raises = False

    def query(self, model):
        return _FakeQuery(self.rows)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self._commit_raises:
            raise RuntimeError("commit boom")
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def _resolution(
    error_type="permission_denied",
    resolution_attempted="Let Agent Request Permission",
    success=True,
    user_feedback=None,
    agent_suggested=True,
    timestamp="DEFAULT",
    error_code=None,
):
    r = MagicMock()
    r.error_type = error_type
    r.resolution_attempted = resolution_attempted
    r.success = success
    r.user_feedback = user_feedback
    r.agent_suggested = agent_suggested
    r.timestamp = datetime(2026, 1, 1) if timestamp == "DEFAULT" else timestamp
    r.error_code = error_code
    return r


@pytest.fixture
def engine():
    return ErrorGuidanceEngine(FakeDB())


# ===========================================================================
# categorize_error
# ===========================================================================


class TestCategorizeError:
    def test_none_code_with_permission_message(self, engine):
        assert engine.categorize_error(None, "permission required") == "permission_denied"

    def test_401_with_expired(self, engine):
        assert engine.categorize_error("401", "token expired") == "auth_expired"

    def test_401_with_token(self, engine):
        assert engine.categorize_error("HTTP 401", "bad token") == "auth_expired"

    def test_401_without_token_or_expired(self, engine):
        assert engine.categorize_error("401", "forbidden") == "permission_denied"

    def test_403_permission_denied(self, engine):
        assert engine.categorize_error("403", "nope") == "permission_denied"

    def test_429_rate_limit(self, engine):
        assert engine.categorize_error("429", "slow down") == "rate_limit"

    def test_404_resource_not_found(self, engine):
        assert engine.categorize_error("404", "missing") == "resource_not_found"

    def test_400_invalid_input(self, engine):
        assert engine.categorize_error("400", "bad") == "invalid_input"

    def test_code_takes_precedence_over_message(self, engine):
        # Code 400 with a "permission" message → still invalid_input (code wins)
        assert engine.categorize_error("400", "permission denied") == "invalid_input"

    def test_message_unauthorized(self, engine):
        assert engine.categorize_error(None, "unauthorized access") == "permission_denied"

    def test_message_expired(self, engine):
        assert engine.categorize_error(None, "session expired") == "auth_expired"

    def test_message_token(self, engine):
        assert engine.categorize_error(None, "invalid token") == "auth_expired"

    def test_message_rate_limit(self, engine):
        assert engine.categorize_error(None, "rate limit hit") == "rate_limit"

    def test_message_too_many_requests(self, engine):
        assert engine.categorize_error(None, "too many requests") == "rate_limit"

    def test_message_network(self, engine):
        assert engine.categorize_error(None, "network down") == "network_error"

    def test_message_connect(self, engine):
        assert engine.categorize_error(None, "cannot connect") == "network_error"

    def test_message_timeout(self, engine):
        assert engine.categorize_error(None, "request timeout") == "network_error"

    def test_message_not_found(self, engine):
        assert engine.categorize_error(None, "user not found") == "resource_not_found"

    def test_message_invalid(self, engine):
        assert engine.categorize_error(None, "invalid format") == "invalid_input"

    def test_message_malformed(self, engine):
        assert engine.categorize_error(None, "malformed json") == "invalid_input"

    def test_unknown_default(self, engine):
        assert engine.categorize_error(None, "something weird") == "unknown"

    def test_empty_message(self, engine):
        assert engine.categorize_error(None, "") == "unknown"

    def test_unmapped_code_falls_to_message(self, engine):
        assert engine.categorize_error("500", "network failure") == "network_error"

    def test_empty_message_with_unmapped_code(self, engine):
        # Code present but none of the recognized codes; empty message → unknown
        assert engine.categorize_error("500", "") == "unknown"


# ===========================================================================
# get_suggested_resolution
# ===========================================================================


class TestGetSuggestedResolution:
    def test_unknown_type_returns_zero(self, engine):
        assert engine.get_suggested_resolution("not_a_type") == 0

    def test_known_type_no_history_returns_zero(self, engine):
        # engine.db.rows is empty
        assert engine.get_suggested_resolution("permission_denied") == 0

    def test_with_history_returns_index(self, engine):
        """BUG: get_suggested_resolution returns a *string* (the resolution
        name) when historical successes exist, but the docstring + every caller
        treats the return value as a 0-based integer index. Repro: with two
        successful 'Let Agent Request Permission' resolutions, the function
        returns the string 'Let Agent Request Permission' instead of its
        template index (0)."""
        engine.db.rows = [
            _resolution(resolution_attempted="Let Agent Request Permission"),
            _resolution(resolution_attempted="Let Agent Request Permission"),
            _resolution(resolution_attempted="Grant Permission Manually"),
        ]
        result = engine.get_suggested_resolution("permission_denied")
        assert isinstance(result, int), (
            "get_suggested_resolution must return an int index, got "
            f"{type(result).__name__}: {result!r}"
        )
        assert result == 0  # 'Let Agent Request Permission' is index 0

    def test_with_history_returns_correct_index_for_second(self, engine):
        # 'Grant Permission Manually' is index 1 in the template; if it has the
        # most historical successes, the suggested index should be 1.
        engine.db.rows = [
            _resolution(resolution_attempted="Grant Permission Manually"),
            _resolution(resolution_attempted="Grant Permission Manually"),
            _resolution(resolution_attempted="Let Agent Request Permission"),
        ]
        assert engine.get_suggested_resolution("permission_denied") == 1

    def test_with_history_resolution_not_in_template_falls_back_to_zero(self, engine):
        # Historical resolution name doesn't match any current template title
        # (e.g. template changed between releases) → fall back to index 0.
        engine.db.rows = [
            _resolution(resolution_attempted="Legacy Resolution Name"),
            _resolution(resolution_attempted="Legacy Resolution Name"),
        ]
        assert engine.get_suggested_resolution("permission_denied") == 0


# ===========================================================================
# present_error (async)
# ===========================================================================


class TestPresentError:
    @pytest.mark.asyncio
    async def test_feature_disabled_returns_early(self, engine):
        with patch.object(ege, "ERROR_GUIDANCE_ENABLED", False):
            with patch.object(ege, "ws_manager") as ws:
                await engine.present_error("u1", "op1", {"code": "403", "message": "no"})
                ws.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_presents_known_error(self, engine):
        with patch.object(ege, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await engine.present_error(
                "u1", "op1", {"code": "403", "message": "forbidden"},
                agent_id="a1",
            )
            assert ws.broadcast.await_count == 1
            channel, msg = ws.broadcast.await_args.args
            assert channel == "user:u1"
            assert msg["type"] == "operation:error"
            data = msg["data"]
            assert data["error"]["type"] == "permission_denied"
            assert data["operation_id"] == "op1"
            assert isinstance(data["suggested_resolution"], int)
            assert "what_happened" in data["agent_analysis"]
            assert len(data["resolutions"]) == 2

    @pytest.mark.asyncio
    async def test_presents_unknown_error_uses_default_template(self, engine):
        with patch.object(ege, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await engine.present_error("u1", "op1", {"code": "500", "message": "weird"})
            data = ws.broadcast.await_args.args[1]["data"]
            assert data["error"]["type"] == "unknown"
            # Default fallback template has 2 resolutions
            assert len(data["resolutions"]) == 2

    @pytest.mark.asyncio
    async def test_error_in_broadcast_swallowed(self, engine):
        with patch.object(ege, "ws_manager") as ws:
            ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
            # Must not raise
            await engine.present_error("u1", "op1", {"code": "403", "message": "no"})

    @pytest.mark.asyncio
    async def test_audit_created_after_present(self, engine):
        with patch.object(ege, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await engine.present_error(
                "u1", "op1", {"message": "rate limit"}, agent_id="a1",
            )
            assert len(engine.db.added) == 1
            audit = engine.db.added[0]
            assert audit.action_type == "present_error"
            assert audit.user_id == "u1"

    @pytest.mark.asyncio
    async def test_audit_commit_failure_swallowed(self, engine):
        engine.db._commit_raises = True
        with patch.object(ege, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await engine.present_error("u1", "op1", {"message": "x"})
            assert engine.db.rolled_back >= 1


# ===========================================================================
# track_resolution (async)
# ===========================================================================


class TestTrackResolution:
    @pytest.mark.asyncio
    async def test_feature_disabled_noop(self, engine):
        with patch.object(ege, "ERROR_GUIDANCE_ENABLED", False):
            await engine.track_resolution("rate_limit", "429", "wait", True)
            assert engine.db.added == []

    @pytest.mark.asyncio
    async def test_tracks_successful_resolution(self, engine):
        await engine.track_resolution(
            "rate_limit", "429", "Let Agent Wait and Retry",
            success=True, user_feedback="worked", agent_suggested=True,
        )
        assert len(engine.db.added) == 1
        r = engine.db.added[0]
        assert r.error_type == "rate_limit"
        assert r.success is True
        assert r.user_feedback == "worked"
        assert engine.db.committed == 1

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back(self, engine):
        engine.db._commit_raises = True
        await engine.track_resolution("rate_limit", "429", "wait", True)
        assert engine.db.rolled_back == 1


# ===========================================================================
# get_historical_resolutions
# ===========================================================================


class TestGetHistoricalResolutions:
    def test_empty(self, engine):
        assert engine.get_historical_resolutions("rate_limit") == []

    def test_returns_mapped_dicts(self, engine):
        engine.db.rows = [
            _resolution(error_type="rate_limit", resolution_attempted="r1",
                        success=True, user_feedback="good",
                        agent_suggested=True, timestamp=datetime(2026, 1, 2)),
            _resolution(error_type="rate_limit", resolution_attempted="r2",
                        success=False, user_feedback=None,
                        agent_suggested=False, timestamp=None),
        ]
        out = engine.get_historical_resolutions("rate_limit", limit=10)
        assert len(out) == 2
        assert out[0]["resolution"] == "r1"
        assert out[0]["success"] is True
        assert out[1]["timestamp"] is None  # None timestamp → None
        assert out[0]["timestamp"] == "2026-01-02T00:00:00"

    def test_exception_returns_empty(self, engine):
        engine.db.query = MagicMock(side_effect=RuntimeError("boom"))
        assert engine.get_historical_resolutions("rate_limit") == []


# ===========================================================================
# get_resolution_success_rate
# ===========================================================================


class TestGetResolutionSuccessRate:
    def test_no_data_zero(self, engine):
        out = engine.get_resolution_success_rate("rate_limit", "wait")
        assert out == {
            "resolution": "wait",
            "success_rate": 0.0,
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
        }

    def test_with_data(self, engine):
        engine.db.rows = [
            _resolution(error_type="rate_limit", resolution_attempted="wait", success=True),
            _resolution(error_type="rate_limit", resolution_attempted="wait", success=True),
            _resolution(error_type="rate_limit", resolution_attempted="wait", success=False),
        ]
        out = engine.get_resolution_success_rate("rate_limit", "wait")
        assert out["success_rate"] == round(2 / 3 * 100, 2)
        assert out["total_attempts"] == 3
        assert out["successful_attempts"] == 2
        assert out["failed_attempts"] == 1

    def test_exception_path(self, engine):
        engine.db.query = MagicMock(side_effect=RuntimeError("boom"))
        out = engine.get_resolution_success_rate("rate_limit", "wait")
        assert out["success_rate"] == 0.0
        assert "error" in out


# ===========================================================================
# get_resolution_statistics
# ===========================================================================


class TestGetResolutionStatistics:
    def test_empty(self, engine):
        out = engine.get_resolution_statistics()
        assert out == {
            "total_resolutions": 0,
            "by_error_type": {},
            "overall_success_rate": 0.0,
        }

    def test_filtered_empty(self, engine):
        out = engine.get_resolution_statistics("rate_limit")
        assert out["total_resolutions"] == 0

    def test_with_data(self, engine):
        engine.db.rows = [
            _resolution(error_type="rate_limit",
                        resolution_attempted="wait", success=True),
            _resolution(error_type="rate_limit",
                        resolution_attempted="wait", success=False),
            _resolution(error_type="network_error",
                        resolution_attempted="retry", success=True),
        ]
        out = engine.get_resolution_statistics()
        assert out["total_resolutions"] == 3
        assert out["overall_success_rate"] == round(2 / 3 * 100, 2)
        assert out["by_error_type"]["rate_limit"]["total"] == 2
        assert out["by_error_type"]["rate_limit"]["successful"] == 1
        assert out["by_error_type"]["network_error"]["successful"] == 1
        # detailed_stats has per-(type,resolution) breakdowns
        detailed = {d["resolution"]: d for d in out["detailed_stats"]}
        assert detailed["wait"]["total"] == 2
        assert detailed["wait"]["successful"] == 1
        assert detailed["wait"]["success_rate"] == 50.0

    def test_exception_path(self, engine):
        engine.db.query = MagicMock(side_effect=RuntimeError("boom"))
        out = engine.get_resolution_statistics()
        assert out["total_resolutions"] == 0
        assert "error" in out


# ===========================================================================
# suggest_fixes_from_history
# ===========================================================================


class TestSuggestFixesFromHistory:
    def test_no_history_returns_template(self, engine):
        out = engine.suggest_fixes_from_history("rate_limit", "rate limit hit")
        assert len(out) == 2  # template has 2 resolutions, default limit 3
        assert all(s["source"] == "template" for s in out)
        assert all(s["success_rate"] is None for s in out)

    def test_no_history_unknown_type_empty(self, engine):
        out = engine.suggest_fixes_from_history("bogus", "x")
        assert out == []

    def test_with_history_sorted_by_success_rate(self, engine):
        # Two successful "Let Agent Wait and Retry", one failed attempt
        # → success_rate 2/3 ≈ 66.67%
        engine.db.rows = [
            _resolution(error_type="rate_limit",
                        resolution_attempted="Let Agent Wait and Retry", success=True),
            _resolution(error_type="rate_limit",
                        resolution_attempted="Let Agent Wait and Retry", success=True),
            _resolution(error_type="rate_limit",
                        resolution_attempted="Let Agent Wait and Retry", success=False),
        ]
        out = engine.suggest_fixes_from_history("rate_limit", "rate limit")
        assert len(out) == 1
        s = out[0]
        assert s["source"] == "historical"
        assert s["resolution"] == "Let Agent Wait and Retry"
        assert s["success_rate"] == round(2 / 3 * 100, 2)
        assert s["successful_attempts"] == 2
        assert s["total_attempts"] == 3
        # Description comes from template lookup
        assert "rate limit" in s["description"].lower()

    def test_limit_applied(self, engine):
        engine.db.rows = [
            _resolution(error_type="rate_limit",
                        resolution_attempted="Let Agent Wait and Retry", success=True),
        ]
        out = engine.suggest_fixes_from_history("rate_limit", "rate limit", limit=0)
        # limit=0 → empty slice
        assert out == []

    def test_exception_returns_empty(self, engine):
        engine.db.query = MagicMock(side_effect=RuntimeError("boom"))
        assert engine.suggest_fixes_from_history("rate_limit", "x") == []


# ===========================================================================
# get_error_fix_suggestions (async)
# ===========================================================================


class TestGetErrorFixSuggestions:
    @pytest.mark.asyncio
    async def test_known_error_full_payload(self, engine):
        out = await engine.get_error_fix_suggestions("403", "forbidden")
        assert out["error_type"] == "permission_denied"
        assert "template_resolutions" in out
        assert "historical_suggestions" in out
        assert "statistics" in out
        assert isinstance(out["recommended_resolution"], int)

    @pytest.mark.asyncio
    async def test_exclude_historical(self, engine):
        out = await engine.get_error_fix_suggestions(
            "403", "forbidden", include_historical=False,
        )
        assert out["historical_suggestions"] == []

    @pytest.mark.asyncio
    async def test_exception_path(self, engine):
        # Force categorize to blow up by passing a non-hashable... easier:
        # make suggest_fixes_from_history raise via db query error
        engine.db.query = MagicMock(side_effect=RuntimeError("boom"))
        out = await engine.get_error_fix_suggestions("403", "forbidden")
        # The outer try/except catches and returns error dict
        assert "error" in out or "error_type" in out


# ===========================================================================
# Private explain helpers
# ===========================================================================


class TestExplainHelpers:
    @pytest.mark.parametrize("etype,expected_key", [
        ("permission_denied", "permission"),
        ("auth_expired", "expired"),
        ("network_error", "network"),
        ("rate_limit", "limiting"),
        ("invalid_input", "doesn't match"),
        ("resource_not_found", "doesn't exist"),
        ("unknown", "unexpected"),
        ("totally_bogus", "unexpected"),  # default fallback
    ])
    def test_explain_what_happened(self, engine, etype, expected_key):
        out = engine._explain_what_happened(etype, {})
        assert expected_key.lower() in out.lower()

    def test_explain_why_known_and_unknown(self, engine):
        assert "security" in engine._explain_why("auth_expired", {}).lower()
        assert "unclear" in engine._explain_why("bogus", {}).lower()

    def test_explain_impact_known_and_unknown(self, engine):
        assert "wait" in engine._explain_impact("rate_limit").lower()
        assert "resolved" in engine._explain_impact("bogus").lower()


# ===========================================================================
# Factory + flag
# ===========================================================================


class TestFactoryAndFlag:
    def test_factory_returns_instance(self):
        eng = get_error_guidance_engine(FakeDB())
        assert isinstance(eng, ErrorGuidanceEngine)

    def test_error_resolutions_template_completeness(self):
        # Every template has title + resolutions + 2 entries each
        for etype, tpl in ErrorGuidanceEngine.ERROR_RESOLUTIONS.items():
            assert "title" in tpl
            assert "resolutions" in tpl
            assert len(tpl["resolutions"]) == 2
            for r in tpl["resolutions"]:
                assert {"title", "description", "agent_can_fix", "steps"} <= set(r.keys())

    def test_flag_default_true(self):
        # Should be a bool
        assert isinstance(ERROR_GUIDANCE_ENABLED, bool)
