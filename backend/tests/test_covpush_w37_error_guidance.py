"""Coverage wave 37 — core/error_guidance_engine (no existing suite → 85%+).

- categorize_error: code-first (401 expired/token, 401/403, 429, 404, 400),
  message-based (permission/expired/rate/network/not-found/invalid), default
- get_suggested_resolution: unknown type, no resolutions, most-successful
  mapped to template index, template-mismatch fallback
- track_resolution: disabled flag, success, exception rollback
- get_historical_resolutions: rows + exception
- get_resolution_success_rate: none, mixed, exception
- get_resolution_statistics: empty, grouped, filtered, exception
- suggest_fixes_from_history: template fallback, historical, exception
- get_error_fix_suggestions: full + exception
- _explain_* helpers
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.error_guidance_engine import ErrorGuidanceEngine
from core.models import OperationErrorResolution


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


@pytest.fixture
def engine(fresh_db):
    return ErrorGuidanceEngine(fresh_db)


def _resolution(db, error_type="auth_expired", attempted="Reconnect", success=True, agent_suggested=True):
    r = OperationErrorResolution(
        id=str(uuid.uuid4()),
        tenant_id="default",
        error_type=error_type,
        error_code="401",
        resolution_attempted=attempted,
        success=success,
        user_feedback="fb",
        agent_suggested=agent_suggested,
    )
    db.add(r)
    db.commit()
    return r


class TestCategorize:
    @pytest.mark.parametrize("code,msg,expected", [
        ("401", "token expired", "auth_expired"),
        ("401", "unauthorized", "permission_denied"),
        ("403", "forbidden", "permission_denied"),
        ("429", "too many", "rate_limit"),
        ("404", "missing", "resource_not_found"),
        ("400", "bad request", "invalid_input"),
    ])
    def test_code_first(self, engine, code, msg, expected):
        assert engine.categorize_error(code, msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("permission denied", "permission_denied"),
        ("token has expired", "auth_expired"),
        ("rate limit exceeded", "rate_limit"),
        ("network unreachable", "network_error"),
        ("resource not found", "resource_not_found"),
        ("invalid input", "invalid_input"),
        ("something else entirely", "unknown"),
    ])
    def test_message_based(self, engine, msg, expected):
        assert engine.categorize_error(None, msg) == expected


class TestSuggestedResolution:
    def test_unknown_type(self, engine):
        assert engine.get_suggested_resolution("nonsense") == 0

    def test_no_resolutions(self, engine, fresh_db):
        assert engine.get_suggested_resolution("auth_expired") == 0

    def test_most_successful_mapped(self, engine, fresh_db):
        _resolution(fresh_db, attempted="Let Agent Reconnect", success=True)
        _resolution(fresh_db, attempted="Let Agent Reconnect", success=True)
        _resolution(fresh_db, attempted="Manual Fix", success=False)
        idx = engine.get_suggested_resolution("auth_expired")
        template = engine.ERROR_RESOLUTIONS["auth_expired"]["resolutions"]
        assert template[idx]["title"] == "Let Agent Reconnect"

    def test_template_mismatch_fallback(self, engine, fresh_db):
        _resolution(fresh_db, attempted="Ghost Resolution", success=True)
        assert engine.get_suggested_resolution("auth_expired") == 0


class TestTrackResolution:
    async def test_disabled_flag(self, engine, fresh_db):
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", False):
            await engine.track_resolution("auth_expired", "401", "Reconnect", True)
        assert fresh_db.query(OperationErrorResolution).count() == 0

    async def test_success(self, engine, fresh_db):
        await engine.track_resolution("auth_expired", "401", "Reconnect", True, user_feedback="worked")
        rows = fresh_db.query(OperationErrorResolution).all()
        assert len(rows) == 1
        assert rows[0].success is True

    async def test_exception_rollback(self, engine, fresh_db):
        engine.db = MagicMock()
        engine.db.add.side_effect = RuntimeError("boom")
        await engine.track_resolution("auth_expired", "401", "Reconnect", True)
        assert engine.db.rollback.called


class TestHistorical:
    def test_get_historical(self, engine, fresh_db):
        _resolution(fresh_db)
        _resolution(fresh_db, error_type="rate_limit", attempted="Wait")
        rows = engine.get_historical_resolutions("auth_expired")
        assert len(rows) == 1
        assert rows[0]["resolution"] == "Reconnect"
        assert rows[0]["user_feedback"] == "fb"

    def test_get_historical_exception(self, engine):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        engine.db = db
        assert engine.get_historical_resolutions("auth_expired") == []


class TestSuccessRate:
    def test_no_resolutions(self, engine, fresh_db):
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats["total_attempts"] == 0
        assert stats["success_rate"] == 0.0

    def test_mixed(self, engine, fresh_db):
        _resolution(fresh_db, attempted="Reconnect", success=True)
        _resolution(fresh_db, attempted="Reconnect", success=False)
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats["total_attempts"] == 2
        assert stats["successful_attempts"] == 1
        assert stats["success_rate"] == 50.0

    def test_exception(self, engine):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        engine.db = db
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats["success_rate"] == 0.0
        assert "error" in stats


class TestStatistics:
    def test_empty(self, engine, fresh_db):
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 0

    def test_grouped(self, engine, fresh_db):
        _resolution(fresh_db, error_type="auth_expired", attempted="Reconnect", success=True)
        _resolution(fresh_db, error_type="auth_expired", attempted="Reconnect", success=False)
        _resolution(fresh_db, error_type="rate_limit", attempted="Wait", success=True)
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 3
        assert stats["overall_success_rate"] == round(2 / 3 * 100, 2)
        assert len(stats["detailed_stats"]) == 2
        filtered = engine.get_resolution_statistics(error_type="auth_expired")
        assert filtered["total_resolutions"] == 2

    def test_exception(self, engine):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        engine.db = db
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 0
        assert "error" in stats


class TestSuggestFixes:
    def test_template_fallback(self, engine, fresh_db):
        suggestions = engine.suggest_fixes_from_history("auth_expired", "token expired")
        assert suggestions
        assert suggestions[0]["source"] == "template"
        assert suggestions[0]["agent_can_fix"] is True

    def test_unknown_type_template_empty(self, engine, fresh_db):
        assert engine.suggest_fixes_from_history("nonsense", "x") == []

    def test_historical(self, engine, fresh_db):
        _resolution(fresh_db, attempted="Reconnect", success=True)
        _resolution(fresh_db, attempted="Reconnect", success=True)
        _resolution(fresh_db, attempted="Reconnect", success=False)
        suggestions = engine.suggest_fixes_from_history("auth_expired", "token expired")
        assert suggestions
        assert suggestions[0]["source"] == "historical"
        assert suggestions[0]["success_rate"] == round(2 / 3 * 100, 2)

    def test_exception(self, engine):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        engine.db = db
        assert engine.suggest_fixes_from_history("auth_expired", "x") == []


class TestFixSuggestions:
    async def test_full(self, engine, fresh_db):
        result = await engine.get_error_fix_suggestions("401", "token expired")
        assert result["error_type"] == "auth_expired"
        assert result["template_resolutions"]
        assert result["statistics"]["total_resolutions"] == 0

    async def test_include_historical_false(self, engine, fresh_db):
        result = await engine.get_error_fix_suggestions(
            "429", "rate limit", include_historical=False
        )
        assert result["error_type"] == "rate_limit"
        assert result["historical_suggestions"] == []

    async def test_exception(self, engine):
        with patch.object(engine, "categorize_error", side_effect=RuntimeError("boom")):
            result = await engine.get_error_fix_suggestions("401", "x")
        assert result["error_type"] == "unknown"
        assert "error" in result


class TestExplainers:
    def test_explain_what_happened(self, engine):
        for t in ["permission_denied", "auth_expired", "network_error", "rate_limit",
                  "invalid_input", "resource_not_found", "unknown"]:
            assert engine._explain_what_happened(t, {})
        assert engine._explain_what_happened("weird", {}) == engine._explain_what_happened("unknown", {})

    def test_explain_why_and_impact(self, engine):
        for t in ["permission_denied", "auth_expired", "network_error", "rate_limit",
                  "invalid_input", "resource_not_found", "unknown"]:
            assert engine._explain_why(t, {})
            assert engine._explain_impact(t)


class TestPresentError:
    async def test_present_broadcasts(self, engine, fresh_db):
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", True), \
             patch("core.error_guidance_engine.ws_manager") as ws, \
             patch.object(engine, "_create_audit", new=AsyncMock()) as audit:
            ws.broadcast = AsyncMock()
            await engine.present_error(
                "u1", "op-1", {"code": "401", "message": "token expired"},
                agent_id="a1",
            )
        ws.broadcast.assert_called_once()
        payload = ws.broadcast.call_args.args[1]["data"]
        assert payload["error"]["type"] == "auth_expired"
        assert payload["operation_id"] == "op-1"
        assert payload["agent_analysis"]["impact"]
        audit.assert_awaited_once()

    async def test_present_disabled(self, engine, fresh_db):
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", False), \
             patch("core.error_guidance_engine.ws_manager") as ws:
            await engine.present_error("u1", "op-1", {"code": "401", "message": "x"})
        ws.broadcast.assert_not_called()

    async def test_present_exception_swallowed(self, engine):
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", True), \
             patch.object(engine, "categorize_error", side_effect=RuntimeError("boom")):
            await engine.present_error("u1", "op-1", {"code": "401", "message": "x"})
        # no raise
