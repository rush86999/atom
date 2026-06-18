"""
Test suite for Memory Consolidation Service.

RED PHASE: These tests verify the memory consolidation service integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestConsolidationConfig:
    """Tests for ConsolidationConfig"""

    def test_consolidation_config_exists(self):
        """Test that ConsolidationConfig is defined"""
        try:
            from core.memory.memory_consolidation_service import ConsolidationConfig
            assert ConsolidationConfig is not None
        except ImportError as e:
            pytest.fail(f"ConsolidationConfig import failed: {e}")

    def test_consolidation_config_has_attributes(self):
        """Test that ConsolidationConfig has required attributes"""
        from core.memory.memory_consolidation_service import ConsolidationConfig

        required_attrs = [
            "CONSOLIDATION_INTERVAL_HOURS",
            "MIN_MEMORIES_FOR_CONSOLIDATION",
            "MIN_QUALITY_SCORE",
            "HIGH_QUALITY_THRESHOLD",
            "CONSOLIDATION_ACCESS_THRESHOLD",
            "REPLAY_THRESHOLD",
            "FORGETTING_DAYS",
            "FORGETTING_DECAY_RATE",
            "MIN_PATTERN_SIZE",
            "PATTERN_SIMILARITY_THRESHOLD",
        ]

        for attr in required_attrs:
            assert hasattr(ConsolidationConfig, attr), \
                f"ConsolidationConfig missing attribute: {attr}"

    def test_consolidation_config_values(self):
        """Test that ConsolidationConfig has sensible values"""
        from core.memory.memory_consolidation_service import ConsolidationConfig

        # Check reasonable values
        assert ConsolidationConfig.CONSOLIDATION_INTERVAL_HOURS > 0
        assert ConsolidationConfig.MIN_MEMORIES_FOR_CONSOLIDATION > 0
        assert 0 <= ConsolidationConfig.MIN_QUALITY_SCORE <= 1
        assert 0 <= ConsolidationConfig.HIGH_QUALITY_THRESHOLD <= 1
        assert ConsolidationConfig.FORGETTING_DAYS > 0
        assert 0 < ConsolidationConfig.FORGETTING_DECAY_RATE <= 1


class TestConsolidationServiceInit:
    """Tests for MemoryConsolidationService initialization"""

    def test_service_import(self):
        """Test that MemoryConsolidationService can be imported"""
        try:
            from core.memory.memory_consolidation_service import MemoryConsolidationService
            assert MemoryConsolidationService is not None
        except ImportError as e:
            pytest.fail(f"MemoryConsolidationService import failed: {e}")

    def test_service_initialization(self):
        """Test that service can be initialized with database"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert service is not None
        assert service.db == db
        assert hasattr(service, 'episode_lifecycle')

    def test_factory_function(self):
        """Test that factory function exists"""
        try:
            from core.memory.memory_consolidation_service import get_consolidation_service
            assert callable(get_consolidation_service)
        except ImportError as e:
            pytest.fail(f"get_consolidation_service import failed: {e}")


class TestEpisodeToMemorySync:
    """Tests for episode to POMDP memory synchronization"""

    def test_sync_method_exists(self):
        """Test that sync_episodes_to_memory method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'sync_episodes_to_memory'), \
            "Service should have sync_episodes_to_memory method"

    def test_sync_method_is_async(self):
        """Test that sync_episodes_to_memory is async"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService
        import inspect

        method = MemoryConsolidationService.sync_episodes_to_memory
        assert inspect.iscoroutinefunction(method), \
            "sync_episodes_to_memory should be async"

    def test_sync_returns_required_fields(self):
        """Test that sync_episodes_to_memory returns required fields"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        # Mock query to return no episodes
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        import asyncio
        result = asyncio.run(service.sync_episodes_to_memory("test_agent"))

        # Required fields
        required_fields = ["synced", "skipped", "errors"]
        for field in required_fields:
            assert field in result, f"Result missing required field: {field}"


class TestConsolidationCycle:
    """Tests for consolidation cycle execution"""

    def test_consolidation_cycle_method_exists(self):
        """Test that run_consolidation_cycle method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'run_consolidation_cycle'), \
            "Service should have run_consolidation_cycle method"

    def test_consolidation_cycle_returns_required_fields(self):
        """Test that run_consolidation_cycle returns required fields"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        import asyncio
        result = asyncio.run(service.run_consolidation_cycle())

        # Required fields
        required_fields = ["consolidated", "duration_seconds"]
        for field in required_fields:
            assert field in result, f"Result missing required field: {field}"

    def test_consolidation_prevents_concurrent_execution(self):
        """Test that consolidation prevents concurrent execution"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        # Set in progress flag
        service._consolidation_in_progress = True

        import asyncio
        result = asyncio.run(service.run_consolidation_cycle())

        assert result.get("status") == "already_running"


class TestForgettingCurve:
    """Tests for forgetting curve implementation"""

    def test_forgetting_curve_method_exists(self):
        """Test that apply_forgetting_curve method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'apply_forgetting_curve'), \
            "Service should have apply_forgetting_curve method"

    def test_forgetting_curve_returns_required_fields(self):
        """Test that apply_forgetting_curve returns required fields"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        import asyncio
        result = asyncio.run(service.apply_forgetting_curve("test_agent"))

        # Required fields
        required_fields = ["affected", "expired"]
        for field in required_fields:
            assert field in result, f"Result missing required field: {field}"


class TestMemoryReplay:
    """Tests for memory replay functionality"""

    def test_replay_method_exists(self):
        """Test that replay_critical_memories method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'replay_critical_memories'), \
            "Service should have replay_critical_memories method"

    def test_replay_returns_list(self):
        """Test that replay_critical_memories returns list"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        import asyncio
        result = asyncio.run(service.replay_critical_memories("test_agent"))

        assert isinstance(result, list), "Result should be a list"


class TestPatternExtraction:
    """Tests for pattern extraction"""

    def test_pattern_extraction_method_exists(self):
        """Test that extract_patterns method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'extract_patterns'), \
            "Service should have extract_patterns method"

    def test_pattern_extraction_returns_list(self):
        """Test that extract_patterns returns list"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        import asyncio
        result = asyncio.run(service.extract_patterns("test_agent"))

        assert isinstance(result, list), "Result should be a list"


class TestConsolidationStatus:
    """Tests for consolidation status reporting"""

    def test_status_method_exists(self):
        """Test that get_consolidation_status method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, 'get_consolidation_status'), \
            "Service should have get_consolidation_status method"

    def test_status_returns_required_fields(self):
        """Test that get_consolidation_status returns required fields"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        result = service.get_consolidation_status()

        # Required fields
        required_fields = ["last_consolidation", "in_progress", "pomdp_available"]
        for field in required_fields:
            assert field in result, f"Result missing required field: {field}"


class TestEpisodeConversion:
    """Tests for episode to ObservationSpace conversion"""

    def test_episode_to_observation_method_exists(self):
        """Test that _episode_to_observation method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, '_episode_to_observation'), \
            "Service should have _episode_to_observation method"

    def test_infer_task_complexity_method_exists(self):
        """Test that _infer_task_complexity method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, '_infer_task_complexity'), \
            "Service should have _infer_task_complexity method"

    def test_infer_autonomy_level_method_exists(self):
        """Test that _infer_autonomy_level method exists"""
        from core.memory.memory_consolidation_service import MemoryConsolidationService

        db = Mock()
        service = MemoryConsolidationService(db)

        assert hasattr(service, '_infer_autonomy_level'), \
            "Service should have _infer_autonomy_level method"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
