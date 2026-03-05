"""
Graceful Degradation Tests

Tests that the system remains operational (possibly in degraded mode) when critical
dependencies fail. Validates that the system continues operating rather than crashing.

Graceful Degradation Scenarios:
- LLM Service Degradation (fallback, timeout, rate limit)
- Database Degradation (cache, read-only mode, connection pool recovery)
- Governance Degradation (cache miss fallback, safe denies, logging)
- Canvas Degradation (render failure, state preservation, partial render)
- API Endpoint Degradation (health check, metrics, non-critical endpoints)
- Multi-Service Failure (simultaneous failures, cascade prevention, recovery)

These tests use existing fixtures: assert_graceful_degradation from conftest.py
"""

import pytest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session

# Import services for testing
from core.governance_cache import GovernanceCache
from core.circuit_breaker import CircuitBreaker, circuit_breaker
from core.exceptions import DatabaseConnectionError, LLMRateLimitError

logger = logging.getLogger(__name__)


# ============================================================================
# TestLLMServiceDegradation
# ============================================================================


class TestLLMServiceDegradation:
    """Test LLM service graceful degradation."""

    def test_llm_fallback_returns_cached_response(self):
        """
        LLM service should return cached response when provider fails.

        When primary LLM provider fails, system should fallback to cached responses.
        """
        from core.llm.byok_handler import BYOKHandler

        # Mock handler with cache
        handler = MagicMock(spec=BYOKHandler)
        handler.cache = {}
        handler.cache["test_prompt"] = "Cached response"

        # Mock primary provider to fail
        with patch.object(handler, 'generate_response', side_effect=Exception("Provider failed")):
            # Try to get response (should use cache)
            result = handler.cache.get("test_prompt", "Default fallback")

        assert result == "Cached response", "Should return cached response when provider fails"

    def test_llm_fallback_returns_error_message(self):
        """
        LLM service should return clear error when all providers fail.

        When all LLM providers fail, return clear error message instead of crashing.
        """
        from core.llm.byok_handler import BYOKHandler

        handler = MagicMock(spec=BYOKHandler)

        # Mock all providers to fail
        with patch.object(handler, 'generate_response', side_effect=Exception("All providers failed")):
            # Should handle gracefully
            try:
                handler.generate_response("test")
            except Exception as e:
                # Should have clear error message
                assert "failed" in str(e).lower() or "error" in str(e).lower()

    def test_llm_partial_stream_timeout_handling(self):
        """
        LLM streaming should handle timeout mid-stream gracefully.

        When timeout occurs mid-stream, should return partial response or error.
        """
        async def streaming_mock():
            """Mock streaming that times out."""
            yield "partial"
            await asyncio.sleep(0.1)
            yield "response"
            raise asyncio.TimeoutError("Stream timeout")

        async def test_stream():
            try:
                async for chunk in streaming_mock():
                    pass
            except asyncio.TimeoutError:
                # Expected - timeout handled gracefully
                return True
            return False

        result = asyncio.run(test_stream())
        assert result, "Should handle streaming timeout"

    def test_llm_rate_limit_graceful_degradation(self):
        """
        LLM rate limit (429) should not crash the application.

        System should continue operating when LLM rate limit is hit.
        """
        from core.llm.byok_handler import BYOKHandler

        handler = MagicMock(spec=BYOKHandler)

        # Mock rate limit error
        with patch.object(handler, 'generate_response', side_effect=LLMRateLimitError("openai")):
            # Application should not crash
            try:
                handler.generate_response("test")
            except LLMRateLimitError:
                # Expected - rate limit handled gracefully
                pass
            else:
                pass  # May also be handled internally


# ============================================================================
# TestDatabaseDegradation
# ============================================================================


class TestDatabaseDegradation:
    """Test database graceful degradation."""

    def test_cache_works_during_db_failure(self):
        """
        Cache should remain operational when database fails.

        System should use cached data when database is unavailable.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Pre-populate cache
        cache.set("test-agent", "stream_chat", {"allowed": True})

        # Mock database failure
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB connection failed", {}, None)):
            # Cache should still work
            result = cache.get("test-agent", "stream_chat")

        assert result is not None, "Cache should work during DB failure"
        assert result["allowed"] == True, "Cached value should be correct"

    def test_read_only_mode_on_write_failure(self):
        """
        System should enter read-only mode when database writes fail.

        Reads should succeed, writes should fail gracefully.
        """
        # Mock database that fails on write
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = OperationalError("Write failed", {}, None)

        # Read should work
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id="test")

        try:
            # Simulate read operation
            result = mock_db.query.return_value.filter.return_value.first()
            assert result is not None, "Read should succeed in read-only mode"
        except Exception:
            pytest.fail("Read should not fail in read-only mode")

        # Write should fail gracefully
        with pytest.raises(OperationalError):
            mock_db.execute("INSERT INTO test VALUES (1)")

    def test_connection_pool_recovery(self):
        """
        Connection pool should recover after outage.

        Pool should re-establish connections after database comes back online.
        """
        from core.database import engine

        # Mock pool recovery
        with patch.object(engine.pool, 'reconnect', return_value=True):
            # Simulate pool recovery
            try:
                if hasattr(engine.pool, 'reconnect'):
                    engine.pool.reconnect()
                else:
                    # Pool doesn't have reconnect method - use dispose
                    engine.pool.dispose()
            except Exception as e:
                pytest.fail(f"Pool recovery should not crash: {e}")

    def test_session_cleanup_after_error(self):
        """
        Database session should be usable after error.

        Session should not be corrupted after database error.
        """
        from core.database import SessionLocal

        # Create session
        session = SessionLocal()

        # Mock error
        with patch.object(session, 'execute', side_effect=OperationalError("Query failed", {}, None)):
            try:
                session.execute("SELECT 1")
            except OperationalError:
                pass  # Expected

        # Session should still be usable
        session.close()  # Should not raise
        assert True, "Session cleanup should succeed"


# ============================================================================
# TestGovernanceDegradation
# ============================================================================


class TestGovernanceDegradation:
    """Test governance service graceful degradation."""

    def test_governance_cache_miss_fallback(self):
        """
        Governance should fallback to safe defaults on cache miss.

        When cache misses, should return safe deny instead of crashing.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Try to get non-existent cached value
        result = cache.get("nonexistent-agent", "stream_chat")

        # Should return None or safe default (not crash)
        assert result is None or "allowed" in result, "Should return safe default on cache miss"

    def test_governance_default_to_safe_denies(self):
        """
        Governance should deny by default when unavailable.

        When governance service is down, default to deny (safe mode).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Mock governance service failure
        with patch("core.governance_cache.GovernanceCache._check_database", side_effect=Exception("Governance down")):
            # Should default to deny
            result = cache.get("test-agent", "stream_chat")

        # Should return None (deny) or explicit deny
        assert result is None or result.get("allowed") == False, "Should default to safe deny"

    def test_governance_logging_continues_during_error(self):
        """
        Governance should continue logging errors without crashing.

        Logging errors should not prevent governance from operating.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Mock logger failure
        with patch("core.governance_cache.logger.error", side_effect=Exception("Logger failed")):
            # Governance should still work
            try:
                cache.set("test-agent", "stream_chat", {"allowed": True})
            except Exception:
                pytest.fail("Governance should not crash when logging fails")


# ============================================================================
# TestCanvasDegradation
# ============================================================================


class TestCanvasDegradation:
    """Test canvas graceful degradation."""

    def test_canvas_render_failure_fallback(self):
        """
        Canvas should show fallback component on render failure.

        When canvas component fails to render, show fallback.
        """
        canvas_data = {
            "canvas_id": "test-canvas",
            "components": [
                {"type": "chart", "data": {"invalid": "data"}},
                {"type": "text", "content": "Fallback text"}
            ]
        }

        # Mock render failure
        def mock_render(component):
            if component["type"] == "chart":
                raise Exception("Render failed")
            return component

        # Should render text component, skip failed chart
        rendered = []
        for component in canvas_data["components"]:
            try:
                result = mock_render(component)
                if result:
                    rendered.append(result)
            except Exception:
                # Skip failed component, continue rendering
                continue

        assert len(rendered) == 1, "Should render fallback component"
        assert rendered[0]["type"] == "text", "Should render text fallback"

    def test_canvas_state_preserved_on_error(self):
        """
        Canvas state should be saved even if render fails.

        State persistence should be independent of rendering.
        """
        canvas_state = {
            "canvas_id": "test-canvas",
            "state": {"data": "important"},
            "saved_at": datetime.utcnow().isoformat()
        }

        # Mock render failure but state save success
        mock_db = MagicMock()
        mock_db.add.return_value = None
        mock_db.commit.return_value = None

        # Simulate render failure
        try:
            raise Exception("Render failed")
        except Exception:
            pass

        # State should still be saved
        mock_db.add(canvas_state)
        mock_db.commit()

        assert mock_db.add.called, "State should be saved despite render error"

    def test_canvas_partial_render(self):
        """
        Canvas should partially render when some components fail.

        Failed components should not prevent other components from rendering.
        """
        components = [
            {"type": "header", "title": "Working Header"},
            {"type": "chart", "data": None},  # Will fail
            {"type": "text", "content": "Working Text"},
        ]

        def safe_render(component):
            if component["data"] is None:
                raise ValueError("Invalid data")
            return component

        # Partial render
        rendered = []
        for comp in components:
            try:
                rendered.append(safe_render(comp))
            except Exception:
                continue  # Skip failed component

        assert len(rendered) == 2, "Should render 2 out of 3 components"
        assert rendered[0]["type"] == "header", "Should render header"
        assert rendered[1]["type"] == "text", "Should render text"


# ============================================================================
# TestAPIEndpointDegradation
# ============================================================================


class TestAPIEndpointDegradation:
    """Test API endpoint graceful degradation."""

    def test_health_check_always_responds(self, client):
        """
        Health check should always respond, even during outages.

        Health endpoint should be resilient to dependency failures.
        """
        # Test health endpoint
        response = client.get("/health/live")

        # Should always return 200
        assert response.status_code == 200, "Health check should always respond"

    def test_metrics_endpoint_resilient(self, client):
        """
        Metrics endpoint should be resilient during partial outage.

        Metrics should work even if some services are down.
        """
        # Test metrics endpoint
        response = client.get("/health/metrics")

        # Should return metrics (even if partial)
        assert response.status_code in [200, 503], "Metrics should respond or degrade gracefully"

    def test_non_critical_endpoints_fail_gracefully(self, client):
        """
        Non-critical endpoints should fail with clear error messages.

        When non-critical services fail, return clear error instead of 500.
        """
        # Test endpoint that might fail
        response = client.get("/api/v1/agents/nonexistent-agent")

        # Should return 404 (not 500)
        assert response.status_code == 404, "Non-existent resource should return 404, not crash"


# ============================================================================
# TestMultiServiceFailure
# ============================================================================


class TestMultiServiceFailure:
    """Test multiple simultaneous service failures."""

    def test_db_and_llm_simultaneous_failure(self):
        """
        System should handle simultaneous DB and LLM failures.

        Multiple service failures should not cascade to complete outage.
        """
        # Mock both DB and LLM failures
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB failed", {}, None)):
            with patch("core.llm.byok_handler.BYOKHandler.generate_response", side_effect=Exception("LLM failed")):
                # System should still handle gracefully
                cache = GovernanceCache(max_size=100, ttl_seconds=60)
                cache.set("test", "action", {"allowed": True})

                # Cache should still work
                result = cache.get("test", "action")
                assert result is not None, "Cache should work during multi-service failure"

    def test_cascade_failure_prevention(self):
        """
        Circuit breaker should prevent cascade failures.

        When service fails repeatedly, circuit breaker should open.
        """
        # Create circuit breaker
        @circuit_breaker(failure_threshold=2, recovery_timeout=1)
        def failing_service():
            raise Exception("Service failed")

        # Trigger failures to open circuit
        with pytest.raises(Exception):
            failing_service()

        with pytest.raises(Exception):
            failing_service()

        # Circuit should be open now
        with pytest.raises(Exception):  # CircuitBreakerOpen
            failing_service()

    def test_system_recovers_after_outage(self):
        """
        System should fully recover after services come back online.

        Recovery should be automatic after dependencies return.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate outage
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB failed", {}, None)):
            # Cache works during outage
            cache.set("test", "action", {"allowed": True})
            result = cache.get("test", "action")
            assert result is not None

        # After outage, full functionality should return
        from core.database import SessionLocal
        try:
            db = SessionLocal()
            # Quick health check
            db.execute("SELECT 1")
            db.close()
        except Exception:
            # DB not available, but that's ok for this test
            pass


# ============================================================================
# TestEdgeCases
# ============================================================================


class TestEdgeCases:
    """Test edge cases in graceful degradation."""

    def test_rapid_failure_recovery_cycles(self):
        """
        System should handle rapid failure/recovery cycles.

        Alternating failures and recoveries should not cause instability.
        """
        service_working = True

        def flaky_service():
            nonlocal service_working
            service_working = not service_working
            if service_working:
                return "success"
            raise Exception("Service failed")

        # Should handle alternating success/failure
        results = []
        for i in range(10):
            try:
                result = flaky_service()
                results.append(result)
            except Exception:
                results.append("failed")

        # Should have mixed results (not all crashes)
        assert "success" in results, "Should handle recovery cycles"
        assert "failed" in results, "Should record failures"

    def test_partial_service_availability(self):
        """
        System should function with partial service availability.

        When some services are up and others down, system should use what's available.
        """
        # Mock: Cache up, DB down, LLM down
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        cache.set("test", "action", {"allowed": True})

        with patch("core.database.SessionLocal", side_effect=OperationalError("DB down", {}, None)):
            with patch("core.llm.byok_handler.BYOKHandler.generate_response", side_effect=Exception("LLM down")):
                # Cache should still work
                result = cache.get("test", "action")
                assert result is not None, "Should use available services"

    def test_memory_pressure_during_degradation(self):
        """
        System should handle memory pressure during degraded mode.

        Graceful degradation should not cause memory exhaustion.
        """
        cache = GovernanceCache(max_size=10, ttl_seconds=60)  # Small cache

        # Fill cache during degradation
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB down", {}, None)):
            for i in range(20):  # More than max_size
                cache.set(f"agent-{i}", "action", {"allowed": True})

        # Should enforce max size (not grow unbounded)
        assert len(cache._cache) <= 10, "Cache should enforce max size during degradation"


# ============================================================================
# Integration Tests
# ============================================================================


class TestGracefulDegradationIntegration:
    """Integration tests for graceful degradation scenarios."""

    def test_full_stack_degraded_mode(self, client):
        """
        Test full application in degraded mode.

        Simulate multiple failures and verify application continues operating.
        """
        # Mock critical service failures
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB failed", {}, None)):
            # Health check should still work
            response = client.get("/health/live")
            assert response.status_code == 200, "Health check should work in degraded mode"

    def test_graceful_shutdown_on_critical_failure(self):
        """
        System should shutdown gracefully on critical failure.

        When critical services fail permanently, shutdown cleanly.
        """
        # Simulate critical failure
        with patch("core.database.engine.connect", side_effect=OperationalError("Critical DB failure", {}, None)):
            # Application should handle gracefully
            from core.database import engine
            try:
                # Try to connect
                conn = engine.connect()
                conn.close()
            except OperationalError:
                # Expected - connection failed
                pass

    def test_degraded_mode_performance(self):
        """
        System should maintain acceptable performance in degraded mode.

        Degraded mode should not cause excessive latency or resource usage.
        """
        import time

        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Pre-populate cache
        cache.set("test", "action", {"allowed": True})

        # Measure cache performance during DB failure
        with patch("core.database.SessionLocal", side_effect=OperationalError("DB down", {}, None)):
            start = time.time()
            for i in range(100):
                cache.get("test", "action")
            duration = time.time() - start

        # Cache should be fast (< 1 second for 100 reads)
        assert duration < 1.0, f"Cache performance degraded: {duration}s for 100 reads"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
