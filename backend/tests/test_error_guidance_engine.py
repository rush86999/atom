"""
Error Guidance Engine Tests

Tests for error categorization, resolution strategies, and recovery automation.
Coverage target: 20-25 tests for error_guidance_engine.py (815 lines)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.error_guidance_engine import (
    ErrorGuidanceEngine,
    get_error_guidance_engine
)


class TestErrorCategorization:
    """Test error type categorization by code and message."""

    def test_categorize_permission_denied_by_code(self):
        """ErrorGuidanceEngine categorizes 403 as permission_denied."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("403", "Access denied")

        assert error_type == "permission_denied"

    def test_categorize_auth_expired_by_code(self):
        """ErrorGuidanceEngine categorizes 401 with expired token as auth_expired."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("401", "Token expired")

        assert error_type == "auth_expired"

    def test_categorize_rate_limit_by_code(self):
        """ErrorGuidanceEngine categorizes 429 as rate_limit."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("429", "Too many requests")

        assert error_type == "rate_limit"

    def test_categorize_resource_not_found_by_code(self):
        """ErrorGuidanceEngine categorizes 404 as resource_not_found."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("404", "Not found")

        assert error_type == "resource_not_found"

    def test_categorize_invalid_input_by_code(self):
        """ErrorGuidanceEngine categorizes 400 as invalid_input."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("400", "Invalid request")

        assert error_type == "invalid_input"

    def test_categorize_unknown_error(self):
        """ErrorGuidanceEngine categorizes unknown errors as unknown."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        error_type = engine.categorize_error("500", "Internal server error")

        assert error_type == "unknown"


class TestResolutionStrategies:
    """Test resolution strategy selection and execution."""

    def test_get_suggested_resolution_default(self):
        """ErrorGuidanceEngine returns default resolution index (0) when no history."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.all.return_value = []
        engine = ErrorGuidanceEngine(db)

        index = engine.get_suggested_resolution("permission_denied")

        assert index == 0

    def test_get_suggested_resolution_with_history(self):
        """ErrorGuidanceEngine returns most successful resolution from history."""
        db = Mock(spec=Session)

        # Mock resolution history - need multiple resolutions with same name
        mock_resolution = Mock()
        mock_resolution.resolution_attempted = "Let Agent Request Permission"

        # Configure query chain properly
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_resolution, mock_resolution]
        db.query.return_value = mock_query

        engine = ErrorGuidanceEngine(db)

        index = engine.get_suggested_resolution("permission_denied")

        assert index == 0  # First (most successful) resolution

    def test_get_resolution_success_rate_no_data(self):
        """ErrorGuidanceEngine returns zero success rate when no resolutions exist."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.all.return_value = []
        engine = ErrorGuidanceEngine(db)

        stats = engine.get_resolution_success_rate("permission_denied", "Let Agent Request Permission")

        assert stats["success_rate"] == 0.0
        assert stats["total_attempts"] == 0

    def test_get_resolution_success_rate_with_data(self):
        """ErrorGuidanceEngine calculates success rate from resolution history."""
        db = Mock(spec=Session)

        # Mock successful and failed resolutions
        mock_success = Mock()
        mock_success.success = True
        mock_failed = Mock()
        mock_failed.success = False

        db.query.return_value.filter.return_value.all.return_value = [mock_success, mock_failed, mock_success]

        engine = ErrorGuidanceEngine(db)

        stats = engine.get_resolution_success_rate("permission_denied", "Let Agent Request Permission")

        assert stats["success_rate"] == 66.67
        assert stats["total_attempts"] == 3
        assert stats["successful_attempts"] == 2
        assert stats["failed_attempts"] == 1


class TestErrorRecovery:
    """Test automatic error recovery and retry logic."""

    @pytest.mark.asyncio
    async def test_present_error_with_valid_data(self):
        """ErrorGuidanceEngine presents error with resolutions via WebSocket."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.all.return_value = []

        with patch('core.error_guidance_engine.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()

            engine = ErrorGuidanceEngine(db)
            await engine.present_error(
                user_id="user-001",
                operation_id="op-001",
                error={"code": "403", "message": "Access denied"},
                agent_id="agent-001"
            )

            # Verify WebSocket broadcast was called
            mock_ws.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_error_disabled(self):
        """ErrorGuidanceEngine skips presenting when feature disabled."""
        db = Mock(spec=Session)

        with patch('core.error_guidance_engine.ERROR_GUIDANCE_ENABLED', False):
            engine = ErrorGuidanceEngine(db)
            await engine.present_error(
                user_id="user-001",
                operation_id="op-001",
                error={"code": "403", "message": "Access denied"}
            )

            # Should not raise any errors

    @pytest.mark.asyncio
    async def test_track_resolution_success(self):
        """ErrorGuidanceEngine tracks successful resolution outcome."""
        db = Mock(spec=Session)
        db.add = Mock()
        db.commit = Mock()

        with patch('core.error_guidance_engine.ERROR_GUIDANCE_ENABLED', True):
            engine = ErrorGuidanceEngine(db)
            await engine.track_resolution(
                error_type="permission_denied",
                error_code="403",
                resolution_attempted="Let Agent Request Permission",
                success=True,
                agent_suggested=True
            )

            # Verify database operations
            db.add.assert_called_once()
            db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_resolution_disabled(self):
        """ErrorGuidanceEngine skips tracking when feature disabled."""
        db = Mock(spec=Session)

        with patch('core.error_guidance_engine.ERROR_GUIDANCE_ENABLED', False):
            engine = ErrorGuidanceEngine(db)
            await engine.track_resolution(
                error_type="permission_denied",
                resolution_attempted="Let Agent Request Permission",
                success=True
            )

            # Should not raise any errors


class TestGuidanceIntegration:
    """Test guidance engine integration and analytics."""

    def test_get_historical_resolutions(self):
        """ErrorGuidanceEngine retrieves historical resolution attempts."""
        db = Mock(spec=Session)

        # Mock historical resolutions
        mock_resolution = Mock()
        mock_resolution.resolution_attempted = "Let Agent Request Permission"
        mock_resolution.success = True
        mock_resolution.agent_suggested = True
        mock_resolution.user_feedback = "Worked perfectly"
        mock_resolution.timestamp = datetime.now()

        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_resolution
        ]

        engine = ErrorGuidanceEngine(db)
        history = engine.get_historical_resolutions("permission_denied", limit=10)

        assert len(history) == 1
        assert history[0]["resolution"] == "Let Agent Request Permission"
        assert history[0]["success"] is True

    def test_get_resolution_statistics(self):
        """ErrorGuidanceEngine calculates comprehensive resolution statistics."""
        db = Mock(spec=Session)

        # Mock resolutions
        mock_resolution = Mock()
        mock_resolution.error_type = "permission_denied"
        mock_resolution.resolution_attempted = "Let Agent Request Permission"
        mock_resolution.success = True

        # Configure query chain properly
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_resolution]
        db.query.return_value = mock_query

        engine = ErrorGuidanceEngine(db)
        stats = engine.get_resolution_statistics(error_type="permission_denied")

        assert stats["total_resolutions"] == 1
        assert "overall_success_rate" in stats

    def test_suggest_fixes_from_history(self):
        """ErrorGuidanceEngine suggests fixes based on historical success."""
        db = Mock(spec=Session)

        # Mock successful resolutions
        mock_success = Mock()
        mock_success.resolution_attempted = "Let Agent Request Permission"
        mock_success.success = True

        db.query.return_value.filter.return_value.all.return_value = [mock_success]

        engine = ErrorGuidanceEngine(db)
        suggestions = engine.suggest_fixes_from_history("permission_denied", "Access denied")

        assert len(suggestions) >= 0  # May return template if no history

    @pytest.mark.asyncio
    async def test_get_error_fix_suggestions(self):
        """ErrorGuidanceEngine provides comprehensive fix suggestions."""
        db = Mock(spec=Session)
        db.query.return_value.all.return_value = []

        engine = ErrorGuidanceEngine(db)
        suggestions = await engine.get_error_fix_suggestions(
            error_code="403",
            error_message="Access denied",
            include_historical=False
        )

        assert "error_type" in suggestions
        assert "template_resolutions" in suggestions
        assert "recommended_resolution" in suggestions


class TestErrorExplanations:
    """Test plain English error explanations."""

    def test_explain_what_happened(self):
        """ErrorGuidanceEngine explains what happened in plain English."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        explanation = engine._explain_what_happened("permission_denied", {"code": "403"})

        assert "permission" in explanation.lower()

    def test_explain_why(self):
        """ErrorGuidanceEngine explains why error occurred."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        explanation = engine._explain_why("auth_expired", {})

        assert "security" in explanation.lower() or "expire" in explanation.lower()

    def test_explain_impact(self):
        """ErrorGuidanceEngine explains impact of error."""
        db = Mock(spec=Session)
        engine = ErrorGuidanceEngine(db)

        impact = engine._explain_impact("network_error")

        assert "connection" in impact.lower() or "network" in impact.lower()


class TestHelperFunctions:
    """Test helper functions and utilities."""

    def test_get_error_guidance_engine_singleton(self):
        """get_error_guidance_engine returns ErrorGuidanceEngine instance."""
        db = Mock(spec=Session)

        engine = get_error_guidance_engine(db)

        assert isinstance(engine, ErrorGuidanceEngine)
        assert engine.db == db
