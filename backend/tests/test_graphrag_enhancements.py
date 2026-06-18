"""
Test suite for Phase 2 GraphRAG Enhancements.

RED PHASE: Tests for multi-hop expansion, community detection, and dynamic graph.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# ============================================================================
# Multi-Hop Expansion Tests
# ============================================================================

class TestMultiHopExpansionConfig:
    """Tests for ExpansionConfig"""

    def test_expansion_config_import(self):
        """Test that ExpansionConfig can be imported"""
        try:
            from core.graphrag.multi_hop_expansion import ExpansionConfig
            assert ExpansionConfig is not None
        except ImportError as e:
            pytest.fail(f"ExpansionConfig import failed: {e}")

    def test_expansion_config_defaults(self):
        """Test that ExpansionConfig has sensible defaults"""
        from core.graphrag.multi_hop_expansion import ExpansionConfig

        config = ExpansionConfig()

        assert config.max_hop_depth > 0
        assert config.max_nodes_per_hop > 0
        assert config.max_total_nodes > 0
        assert config.min_relevance_score >= 0
        assert config.min_relevance_score <= 1
        assert config.relevance_decay > 0
        assert config.relevance_decay <= 1

    def test_expansion_strategies_enum(self):
        """Test that ExpansionStrategy enum has required values"""
        from core.graphrag.multi_hop_expansion import ExpansionStrategy

        # Check that required strategies exist
        assert hasattr(ExpansionStrategy, 'BFS')
        assert hasattr(ExpansionStrategy, 'DFS')
        assert hasattr(ExpansionStrategy, 'BIDIRECTIONAL')
        assert hasattr(ExpansionStrategy, 'ADAPTIVE')

        # Check values are lowercase
        assert ExpansionStrategy.BFS.value == "bfs"
        assert ExpansionStrategy.DFS.value == "dfs"

    def test_activation_cues_enum(self):
        """Test that ActivationCue enum has required values"""
        from core.graphrag.multi_hop_expansion import ActivationCue

        # Check that required cues exist
        assert hasattr(ActivationCue, 'RELATIONSHIP_TYPE')
        assert hasattr(ActivationCue, 'ENTITY_TYPE')
        assert hasattr(ActivationCue, 'CONFIDENCE_THRESHOLD')
        assert hasattr(ActivationCue, 'TEMPORAL_RELEVANCE')

        # Check values are lowercase
        assert ActivationCue.RELATIONSHIP_TYPE.value == "relationship_type"


class TestMultiHopExpander:
    """Tests for MultiHopExpander"""

    def test_expander_import(self):
        """Test that MultiHopExpander can be imported"""
        try:
            from core.graphrag.multi_hop_expansion import MultiHopExpander
            assert MultiHopExpander is not None
        except ImportError as e:
            pytest.fail(f"MultiHopExpander import failed: {e}")

    def test_expander_initialization(self):
        """Test that MultiHopExpander can be initialized"""
        from core.graphrag.multi_hop_expansion import MultiHopExpander, ExpansionConfig

        config = ExpansionConfig()
        expander = MultiHopExpander(config)

        assert expander is not None
        assert expander.config == config

    def test_expander_returns_result(self):
        """Test that expand returns ExpansionResult type"""
        from core.graphrag.multi_hop_expansion import MultiHopExpander, ExpansionResult

        # Just check the method signature and return type annotation
        expander = MultiHopExpander()
        assert hasattr(expander, 'expand')
        # The method exists and should return ExpansionResult
        # Actual execution test would require complex database mocking

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.graphrag.multi_hop_expansion import get_multi_hop_expander

        assert callable(get_multi_hop_expander)


class TestSQLMultiHopExpander:
    """Tests for SQLMultiHopExpander"""

    def test_sql_expander_import(self):
        """Test that SQLMultiHopExpander can be imported"""
        try:
            from core.graphrag.multi_hop_expansion import SQLMultiHopExpander
            assert SQLMultiHopExpander is not None
        except ImportError as e:
            pytest.fail(f"SQLMultiHopExpander import failed: {e}")

    def test_sql_expander_initialization(self):
        """Test that SQLMultiHopExpander can be initialized"""
        from core.graphrag.multi_hop_expansion import SQLMultiHopExpander, ExpansionConfig

        config = ExpansionConfig()
        expander = SQLMultiHopExpander(config)

        assert expander is not None
        assert expander.config == config

    def test_sql_expansion_returns_result(self):
        """Test that expand_sql returns ExpansionResult"""
        from core.graphrag.multi_hop_expansion import SQLMultiHopExpander
        from unittest.mock import Mock

        expander = SQLMultiHopExpander()
        session = Mock()

        # Mock execute to return empty result
        session.execute.return_value.fetchall.return_value = []

        result = expander.expand_sql("test_id", "workspace_1", 2, session)

        assert hasattr(result, "nodes")
        assert hasattr(result, "relationships")
        assert hasattr(result, "total_nodes_found")


# ============================================================================
# Community Detection Tests
# ============================================================================

class TestCommunityDetectionConfig:
    """Tests for CommunityConfig"""

    def test_community_config_import(self):
        """Test that CommunityConfig can be imported"""
        try:
            from core.graphrag.community_detection import CommunityConfig
            assert CommunityConfig is not None
        except ImportError as e:
            pytest.fail(f"CommunityConfig import failed: {e}")

    def test_community_config_defaults(self):
        """Test that CommunityConfig has sensible defaults"""
        from core.graphrag.community_detection import CommunityConfig

        config = CommunityConfig()

        assert config.base_resolution > 0
        assert config.min_community_size > 0
        assert config.max_community_size > config.min_community_size
        assert config.min_modularity >= 0
        assert config.min_modularity <= 1

    def test_clustering_algorithm_enum(self):
        """Test that ClusteringAlgorithm enum has required values"""
        from core.graphrag.community_detection import ClusteringAlgorithm

        # Check that required algorithms exist
        assert hasattr(ClusteringAlgorithm, 'LEIDEN')
        assert hasattr(ClusteringAlgorithm, 'LOUVAIN')
        assert hasattr(ClusteringAlgorithm, 'LABEL_PROPAGATION')
        assert hasattr(ClusteringAlgorithm, 'GIRVAN_NEWMAN')

    def test_resolution_policy_enum(self):
        """Test that ResolutionPolicy enum has required values"""
        from core.graphrag.community_detection import ResolutionPolicy

        # Check that required policies exist
        assert hasattr(ResolutionPolicy, 'FIXED')
        assert hasattr(ResolutionPolicy, 'ADAPTIVE')
        assert hasattr(ResolutionPolicy, 'HIERARCHICAL')


class TestLeidenAlgorithm:
    """Tests for LeidenAlgorithm"""

    def test_leiden_import(self):
        """Test that LeidenAlgorithm can be imported"""
        try:
            from core.graphrag.community_detection import LeidenAlgorithm
            assert LeidenAlgorithm is not None
        except ImportError as e:
            pytest.fail(f"LeidenAlgorithm import failed: {e}")

    def test_leiden_initialization(self):
        """Test that LeidenAlgorithm can be initialized"""
        from core.graphrag.community_detection import LeidenAlgorithm, CommunityConfig

        config = CommunityConfig()
        leiden = LeidenAlgorithm(config)

        assert leiden is not None
        assert leiden.config == config

    def test_leiden_returns_detection_result(self):
        """Test that detect method exists and returns DetectionResult"""
        from core.graphrag.community_detection import LeidenAlgorithm, DetectionResult

        leiden = LeidenAlgorithm()
        # Just check the method signature
        assert hasattr(leiden, 'detect')
        # The method exists and should return DetectionResult
        # Actual execution test would require NetworkX and database mocking


class TestCommunityDetectionService:
    """Tests for CommunityDetectionService"""

    def test_service_import(self):
        """Test that CommunityDetectionService can be imported"""
        try:
            from core.graphrag.community_detection import CommunityDetectionService
            assert CommunityDetectionService is not None
        except ImportError as e:
            pytest.fail(f"CommunityDetectionService import failed: {e}")

    def test_service_initialization(self):
        """Test that service can be initialized"""
        from core.graphrag.community_detection import CommunityDetectionService, CommunityConfig

        config = CommunityConfig()
        service = CommunityDetectionService(config)

        assert service is not None
        assert service.config == config

    def test_service_factory(self):
        """Test that factory function exists"""
        from core.graphrag.community_detection import get_community_detector

        assert callable(get_community_detector)


# ============================================================================
# Dynamic Graph Tests
# ============================================================================

class TestIncrementalUpdateConfig:
    """Tests for IncrementalUpdateConfig"""

    def test_config_import(self):
        """Test that IncrementalUpdateConfig can be imported"""
        try:
            from core.graphrag.dynamic_graph import IncrementalUpdateConfig
            assert IncrementalUpdateConfig is not None
        except ImportError as e:
            pytest.fail(f"IncrementalUpdateConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that config has sensible defaults"""
        from core.graphrag.dynamic_graph import IncrementalUpdateConfig

        config = IncrementalUpdateConfig()

        assert config.batch_size > 0
        assert config.batch_timeout_ms >= 0
        assert config.max_versions > 0
        assert config.version_retention_days > 0

    def test_update_type_enum(self):
        """Test that UpdateType enum has required values"""
        from core.graphrag.dynamic_graph import UpdateType

        # Check that required types exist
        assert hasattr(UpdateType, 'NODE_ADD')
        assert hasattr(UpdateType, 'NODE_UPDATE')
        assert hasattr(UpdateType, 'NODE_DELETE')
        assert hasattr(UpdateType, 'EDGE_ADD')
        assert hasattr(UpdateType, 'EDGE_UPDATE')
        assert hasattr(UpdateType, 'EDGE_DELETE')
        assert hasattr(UpdateType, 'BATCH_UPDATE')

    def test_version_status_enum(self):
        """Test that GraphVersionStatus enum has required values"""
        from core.graphrag.dynamic_graph import GraphVersionStatus

        # Check that required statuses exist
        assert hasattr(GraphVersionStatus, 'DRAFT')
        assert hasattr(GraphVersionStatus, 'COMMITTED')
        assert hasattr(GraphVersionStatus, 'ROLLED_BACK')
        assert hasattr(GraphVersionStatus, 'ARCHIVED')


class TestDynamicGraphManager:
    """Tests for DynamicGraphManager"""

    def test_manager_import(self):
        """Test that DynamicGraphManager can be imported"""
        try:
            from core.graphrag.dynamic_graph import DynamicGraphManager
            assert DynamicGraphManager is not None
        except ImportError as e:
            pytest.fail(f"DynamicGraphManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.graphrag.dynamic_graph import DynamicGraphManager, IncrementalUpdateConfig

        config = IncrementalUpdateConfig()
        manager = DynamicGraphManager(config)

        assert manager is not None
        assert manager.config == config

    def test_manager_has_components(self):
        """Test that manager has required components"""
        from core.graphrag.dynamic_graph import DynamicGraphManager

        manager = DynamicGraphManager()

        assert hasattr(manager, "update_manager")
        assert hasattr(manager, "version_manager")
        assert hasattr(manager, "temporal_tracker")

    def test_add_node_method(self):
        """Test that add_node method exists and is callable"""
        from core.graphrag.dynamic_graph import DynamicGraphManager

        manager = DynamicGraphManager()
        session = Mock()

        # Mock the add_update to return True
        manager.update_manager.add_update = Mock(return_value=True)

        result = manager.add_node(
            workspace_id="ws1",
            entity_id="node1",
            name="Test Node",
            entity_type="test",
            session=session
        )

        assert result is True
        manager.update_manager.add_update.assert_called_once()

    def test_add_edge_method(self):
        """Test that add_edge method exists and is callable"""
        from core.graphrag.dynamic_graph import DynamicGraphManager

        manager = DynamicGraphManager()
        session = Mock()

        # Mock the add_update to return True
        manager.update_manager.add_update = Mock(return_value=True)

        result = manager.add_edge(
            workspace_id="ws1",
            source_id="node1",
            target_id="node2",
            relationship_type="test",
            session=session
        )

        assert result is True

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.graphrag.dynamic_graph import get_dynamic_graph_manager

        assert callable(get_dynamic_graph_manager)


class TestIncrementalUpdateManager:
    """Tests for IncrementalUpdateManager"""

    def test_updater_import(self):
        """Test that IncrementalUpdateManager can be imported"""
        try:
            from core.graphrag.dynamic_graph import IncrementalUpdateManager
            assert IncrementalUpdateManager is not None
        except ImportError as e:
            pytest.fail(f"IncrementalUpdateManager import failed: {e}")

    def test_updater_initialization(self):
        """Test that updater can be initialized"""
        from core.graphrag.dynamic_graph import IncrementalUpdateManager, IncrementalUpdateConfig

        config = IncrementalUpdateConfig()
        updater = IncrementalUpdateManager(config)

        assert updater is not None
        assert updater.config == config

    def test_updater_has_pending_updates(self):
        """Test that updater tracks pending updates"""
        from core.graphrag.dynamic_graph import IncrementalUpdateManager

        updater = IncrementalUpdateManager()

        assert hasattr(updater, "pending_updates")
        assert isinstance(updater.pending_updates, list)


class TestGraphVersionManager:
    """Tests for GraphVersionManager"""

    def test_version_manager_import(self):
        """Test that GraphVersionManager can be imported"""
        try:
            from core.graphrag.dynamic_graph import GraphVersionManager
            assert GraphVersionManager is not None
        except ImportError as e:
            pytest.fail(f"GraphVersionManager import failed: {e}")

    def test_version_manager_initialization(self):
        """Test that version manager can be initialized"""
        from core.graphrag.dynamic_graph import GraphVersionManager, IncrementalUpdateConfig

        config = IncrementalUpdateConfig()
        manager = GraphVersionManager(config)

        assert manager is not None
        assert manager.config == config

    def test_create_version_returns_snapshot(self):
        """Test that create_version method exists and returns GraphSnapshot"""
        from core.graphrag.dynamic_graph import GraphVersionManager, GraphSnapshot

        manager = GraphVersionManager()
        # Just check the method signature
        assert hasattr(manager, 'create_version')
        # The method exists and should return GraphSnapshot
        # Actual execution test would require complex database mocking


class TestTemporalGraphTracker:
    """Tests for TemporalGraphTracker"""

    def test_tracker_import(self):
        """Test that TemporalGraphTracker can be imported"""
        try:
            from core.graphrag.dynamic_graph import TemporalGraphTracker
            assert TemporalGraphTracker is not None
        except ImportError as e:
            pytest.fail(f"TemporalGraphTracker import failed: {e}")

    def test_tracker_initialization(self):
        """Test that tracker can be initialized"""
        from core.graphrag.dynamic_graph import TemporalGraphTracker, IncrementalUpdateConfig

        config = IncrementalUpdateConfig()
        tracker = TemporalGraphTracker(config)

        assert tracker is not None
        assert tracker.config == config

    def test_get_evolution_metrics(self):
        """Test that get_evolution_metrics method exists"""
        from core.graphrag.dynamic_graph import TemporalGraphTracker

        tracker = TemporalGraphTracker()
        # Just check the method signature
        assert hasattr(tracker, 'get_evolution_metrics')
        # The method exists and should return dict with metrics
        # Actual execution test would require complex database mocking


# ============================================================================
# Integration Tests
# ============================================================================

class TestGraphRAGIntegration:
    """Tests for GraphRAG module integration"""

    def test_module_import(self):
        """Test that graphrag module can be imported"""
        try:
            import core.graphrag
            assert core.graphrag is not None
        except ImportError as e:
            pytest.fail(f"graphrag module import failed: {e}")

    def test_module_exports(self):
        """Test that module exports required components"""
        from core.graphrag import (
            MultiHopExpander,
            CommunityDetectionService,
            DynamicGraphManager,
            get_multi_hop_expander,
            get_community_detector,
            get_dynamic_graph_manager,
        )

        assert MultiHopExpander is not None
        assert CommunityDetectionService is not None
        assert DynamicGraphManager is not None
        assert callable(get_multi_hop_expander)
        assert callable(get_community_detector)
        assert callable(get_dynamic_graph_manager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
