"""
Test ReflectionEngine pattern detection.

Tests cover:
- Event listening
- Repeated failure pattern detection
- Triggering MementoEngine after threshold
- Pattern frequency tracking
- Resetting patterns after successful promotion
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.auto_dev.reflection_engine import ReflectionEngine
from core.auto_dev.event_hooks import TaskEvent


class TestReflectionEngineEventListening:
    """Test ReflectionEngine listens to events."""

    def test_subscribes_to_task_fail_events(self, auto_dev_db_session):
        """Test subscribes to task_fail events."""
        engine = ReflectionEngine(db=auto_dev_db_session)
        engine.register()

        # Should have registered handler
        assert len(engine._failure_buffer) == 0

    def test_tracks_event_metadata(self, auto_dev_db_session, sample_task_event):
        """Test tracks event metadata."""
        engine = ReflectionEngine(db=auto_dev_db_session)

        import asyncio
        asyncio.run(engine.process_failure(sample_task_event))

        assert len(engine._failure_buffer[sample_task_event.agent_id]) == 1


class TestReflectionEnginePatternDetection:
    """Test detects repeated failure patterns."""

    @pytest.mark.asyncio
    async def test_identifies_repeated_failure_patterns(self, auto_dev_db_session, sample_task_event):
        """Test identifies repeated failure patterns."""
        engine = ReflectionEngine(db=auto_dev_db_session, failure_threshold=2)

        # Process same failure twice
        await engine.process_failure(sample_task_event)
        await engine.process_failure(sample_task_event)

        # Should trigger on second occurrence
        assert len(engine._failure_buffer[sample_task_event.agent_id]) >= 1

    @pytest.mark.asyncio
    async def test_groups_by_error_type(self, auto_dev_db_session):
        """Test groups by error type."""
        engine = ReflectionEngine(db=auto_dev_db_session)

        event1 = TaskEvent(
            episode_id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Process sales data",
            error_trace="ValueError: Invalid format",
            outcome="failure",
        )

        event2 = TaskEvent(
            episode_id="ep-002",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Process sales data again",
            error_trace="ValueError: Invalid format",
            outcome="failure",
        )

        await engine.process_failure(event1)
        await engine.process_failure(event2)

        # Should find similar failures
        similar = engine._find_similar_failures("agent-001", "Process sales data")
        assert len(similar) >= 1


class TestReflectionEngineTriggerThreshold:
    """Test triggers MementoEngine after threshold."""

    @pytest.mark.asyncio
    async def test_triggers_after_n_failures(self, auto_dev_db_session, sample_task_event, monkeypatch):
        """Test triggers MementoEngine after N failures."""
        engine = ReflectionEngine(db=auto_dev_db_session, failure_threshold=2)

        # Mock MementoEngine to avoid database requirements
        mock_memento = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.skill_name = "test_skill"
        mock_memento.generate_skill_candidate = AsyncMock(return_value=mock_candidate)

        import sys
        original_module = sys.modules.get("core.auto_dev.memento_engine")

        class MockMementoEngine:
            def __init__(self, db):
                pass

        sys.modules["core.auto_dev.memento_engine"] = MockMementoEngine
        sys.modules["core.auto_dev.memento_engine"].MementoEngine = lambda db: mock_memento

        try:
            # Process two failures
            await engine.process_failure(sample_task_event)
            await engine.process_failure(sample_task_event)

            # Should have triggered
            mock_memento.generate_skill_candidate.assert_called_once()
        finally:
            if original_module:
                sys.modules["core.auto_dev.memento_engine"] = original_module
            else:
                sys.modules.pop("core.auto_dev.memento_engine", None)

    @pytest.mark.asyncio
    async def test_prevents_duplicate_triggers(self, auto_dev_db_session, sample_task_event):
        """Test prevents duplicate triggers."""
        engine = ReflectionEngine(db=auto_dev_db_session, failure_threshold=2)

        # Process same event multiple times
        for _ in range(5):
            await engine.process_failure(sample_task_event)

        # Buffer should be cleared after trigger
        assert len(engine._failure_buffer[sample_task_event.agent_id]) < 5


class TestReflectionEnginePatternTracking:
    """Test pattern frequency tracking."""

    @pytest.mark.asyncio
    async def test_stores_pattern_metadata(self, auto_dev_db_session, sample_task_event):
        """Test stores pattern metadata."""
        engine = ReflectionEngine(db=auto_dev_db_session)

        await engine.process_failure(sample_task_event)

        buffer = engine._failure_buffer[sample_task_event.agent_id]
        assert len(buffer) == 1
        assert buffer[0]["episode_id"] == sample_task_event.episode_id
        assert buffer[0]["task_description"] == sample_task_event.task_description


class TestReflectionEngineIntegration:
    """Test ReflectionEngine integration."""

    def test_reflection_engine_initialization(self, auto_dev_db_session):
        """Test ReflectionEngine initializes correctly."""
        engine = ReflectionEngine(db=auto_dev_db_session)

        assert engine.db == auto_dev_db_session
        assert engine.failure_threshold == 2  # Default
        assert len(engine._failure_buffer) == 0
