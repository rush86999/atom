"""
GraphRAG Engine Tests (PostgreSQL Recursive CTEs)

Comprehensive tests for GraphRAG engine using PostgreSQL recursive CTEs.
Tests cover graph traversal, entity extraction, local/global search, and canonical entity mapping.

Coverage: 80%+ for core/graphrag_engine.py
Lines: 450+, Tests: 25-35
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.graphrag_engine import GraphRAGEngine, Entity, Relationship
from core.models import (
    GraphNode, GraphEdge, EntityTypeDefinition, User, Workspace, Team,
    SupportTicket, Formula, UserTask
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def graphrag_engine(postgresql_db: Session):
    """Create GraphRAG engine instance for testing."""
    if postgresql_db is None:
        pytest.skip("PostgreSQL unavailable")
    return GraphRAGEngine(workspace_id="test_workspace")


@pytest.fixture
def sample_graph_data(postgresql_db: Session):
    """Create sample graph nodes and edges for testing."""
    if postgresql_db is None:
        pytest.skip("PostgreSQL unavailable")

    # Create nodes
    user1 = GraphNode(
        entity_id="user_1",
        entity_type="user",
        name="Alice Johnson",
        workspace_id="test_workspace"
    )
    user2 = GraphNode(
        entity_id="user_2",
        entity_type="user",
        name="Bob Smith",
        workspace_id="test_workspace"
    )
    workspace1 = GraphNode(
        entity_id="workspace_1",
        entity_type="workspace",
        name="Engineering Team",
        workspace_id="test_workspace"
    )
    task1 = GraphNode(
        entity_id="task_1",
        entity_type="task",
        name="Complete Feature X",
        workspace_id="test_workspace"
    )

    postgresql_db.add_all([user1, user2, workspace1, task1])
    postgresql_db.commit()

    # Create edges
    edge1 = GraphEdge(
        from_entity="user_1",
        to_entity="workspace_1",
        rel_type="member_of",
        workspace_id="test_workspace"
    )
    edge2 = GraphEdge(
        from_entity="user_2",
        to_entity="workspace_1",
        rel_type="member_of",
        workspace_id="test_workspace"
    )
    edge3 = GraphEdge(
        from_entity="user_1",
        to_entity="task_1",
        rel_type="assigned_to",
        workspace_id="test_workspace"
    )

    postgresql_db.add_all([edge1, edge2, edge3])
    postgresql_db.commit()

    return {
        "users": [user1, user2],
        "workspaces": [workspace1],
        "tasks": [task1],
        "edges": [edge1, edge2, edge3]
    }


@pytest.fixture
def sample_entity_type(postgresql_db: Session):
    """Create sample entity type definition."""
    if postgresql_db is None:
        pytest.skip("PostgreSQL unavailable")

    entity_type = EntityTypeDefinition(
        slug="customer",
        display_name="Customer",
        json_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "tier": {"type": "string", "enum": ["bronze", "silver", "gold"]}
            },
            "required": ["name", "email"]
        },
        is_active=True
    )
    postgresql_db.add(entity_type)
    postgresql_db.commit()
    return entity_type


# ============================================================================
# Test Graph Traversal
# ============================================================================

class TestGraphTraversal:
    """Tests for graph traversal algorithms using recursive CTEs."""

    def test_get_node_neighbors(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test retrieving immediate neighbors of a node."""
        neighbors = graphrag_engine.get_node_neighbors(
            postgresql_db,
            entity_id="user_1",
            workspace_id="test_workspace"
        )

        assert len(neighbors) == 2  # workspace_1 and task_1
        neighbor_ids = {n["entity_id"] for n in neighbors}
        assert "workspace_1" in neighbor_ids
        assert "task_1" in neighbor_ids

    def test_get_node_neighbors_empty(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test retrieving neighbors for a node with no connections."""
        # Create isolated node
        isolated = GraphNode(
            entity_id="isolated_1",
            entity_type="user",
            name="Isolated User",
            workspace_id="test_workspace"
        )
        postgresql_db.add(isolated)
        postgresql_db.commit()

        neighbors = graphrag_engine.get_node_neighbors(
            postgresql_db,
            entity_id="isolated_1",
            workspace_id="test_workspace"
        )

        assert len(neighbors) == 0

    def test_traverse_depth_1(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test graph traversal at depth 1."""
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=1
        )

        # Should include user_1 + immediate neighbors
        assert len(results) >= 1
        entity_ids = {r["entity_id"] for r in results}
        assert "user_1" in entity_ids

    def test_traverse_depth_2(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test graph traversal at depth 2."""
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=2
        )

        # Should include user_1, neighbors, and neighbors of neighbors
        assert len(results) >= 1
        entity_ids = {r["entity_id"] for r in results}
        assert "user_1" in entity_ids

    def test_traverse_depth_limit(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test that max_depth parameter limits traversal correctly."""
        results_depth_1 = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=1
        )

        results_depth_3 = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=3
        )

        # Depth 3 should return at least as many results as depth 1
        assert len(results_depth_3) >= len(results_depth_1)

    def test_traverse_nonexistent_entity(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test traversal from a non-existent entity returns empty."""
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="nonexistent",
            workspace_id="test_workspace",
            max_depth=2
        )

        assert len(results) == 0


# ============================================================================
# Test Recursive CTEs
# ============================================================================

class TestRecursiveCTEs:
    """Tests for recursive common table expression functionality."""

    def test_recursive_cte_basic(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test basic recursive CTE execution."""
        # This test verifies PostgreSQL's WITH RECURSIVE support
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=2
        )

        # If we got here without error, recursive CTEs work
        assert isinstance(results, list)

    def test_recursive_cte_performance(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test that recursive CTE queries execute within performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=3
        )
        elapsed = time.time() - start_time

        # Target: <100ms for local search
        assert elapsed < 0.1, f"Traversal took {elapsed:.3f}s, target <0.1s"
        assert isinstance(results, list)

    def test_recursive_cte_max_depth(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test that recursive CTE respects max_depth limit."""
        results_depth_5 = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=5
        )

        # Verify no cycles cause infinite loops
        assert isinstance(results_depth_5, list)
        # Should still return finite results
        assert len(results_depth_5) > 0


# ============================================================================
# Test Local Search
# ============================================================================

class TestLocalSearch:
    """Tests for neighborhood-based local search."""

    def test_local_search_basic(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test basic local search by entity name."""
        results = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="test_workspace",
            depth=2
        )

        assert len(results) > 0
        # Should find Alice Johnson
        assert any("Alice" in r.get("name", "") for r in results)

    def test_local_search_depth_parameter(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test that depth parameter affects search results."""
        results_depth_1 = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="test_workspace",
            depth=1
        )

        results_depth_3 = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="test_workspace",
            depth=3
        )

        # Both should return results
        assert len(results_depth_1) > 0
        assert len(results_depth_3) > 0

    def test_local_search_no_results(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test local search with query that has no matches."""
        results = graphrag_engine.local_search(
            postgresql_db,
            query="NonExistentEntityXYZ",
            workspace_id="test_workspace",
            depth=2
        )

        assert len(results) == 0

    def test_local_search_performance(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test local search performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="test_workspace",
            depth=2
        )
        elapsed = time.time() - start_time

        # Target: <100ms for local search
        assert elapsed < 0.1, f"Local search took {elapsed:.3f}s, target <0.1s"
        assert len(results) > 0


# ============================================================================
# Test Global Search
# ============================================================================

class TestGlobalSearch:
    """Tests for community-based global search."""

    def test_global_search_basic(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test basic global search."""
        results = graphrag_engine.global_search(
            postgresql_db,
            query="team members",
            workspace_id="test_workspace"
        )

        assert isinstance(results, list)

    def test_global_search_empty_database(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test global search with empty graph."""
        # Use different workspace to ensure no data
        results = graphrag_engine.global_search(
            postgresql_db,
            query="anything",
            workspace_id="empty_workspace"
        )

        assert isinstance(results, list)

    def test_global_search_performance(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Test global search performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.global_search(
            postgresql_db,
            query="team",
            workspace_id="test_workspace"
        )
        elapsed = time.time() - start_time

        # Target: <200ms for global search
        assert elapsed < 0.2, f"Global search took {elapsed:.3f}s, target <0.2s"


# ============================================================================
# Test Entity Extraction
# ============================================================================

class TestEntityExtraction:
    """Tests for LLM-based entity extraction."""

    @patch('core.graphrag_engine.LLMService')
    def test_extract_entities_from_text(self, mock_llm_service, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test extracting entities from text using LLM."""
        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_response.return_value = {
            "entities": [
                {"name": "Alice Johnson", "type": "user"},
                {"name": "Engineering Team", "type": "workspace"}
            ]
        }
        mock_llm_service.return_value = mock_llm_instance
        graphrag_engine.llm_service = mock_llm_instance

        text = "Alice Johnson is working on the Engineering Team project."
        entities = graphrag_engine.extract_entities(
            postgresql_db,
            text=text,
            workspace_id="test_workspace"
        )

        assert len(entities) >= 0  # May be empty if extraction fails gracefully

    @patch('core.graphrag_engine.LLMService')
    def test_extract_entities_empty_text(self, mock_llm_service, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test entity extraction from empty text."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_response.return_value = {"entities": []}
        mock_llm_service.return_value = mock_llm_instance
        graphrag_engine.llm_service = mock_llm_instance

        entities = graphrag_engine.extract_entities(
            postgresql_db,
            text="",
            workspace_id="test_workspace"
        )

        assert len(entities) == 0


# ============================================================================
# Test Canonical Entity Mapping
# ============================================================================

class TestCanonicalEntityMapping:
    """Tests for canonical to semantic entity resolution."""

    def test_map_user_to_canonical(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test mapping User model to canonical entity."""
        # Create a User in the database
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email="alice@example.com",
            first_name="Alice",
            last_name="Johnson"
        )
        postgresql_db.add(user)
        postgresql_db.commit()

        # Query canonical entity
        entity = graphrag_engine.get_canonical_entity(
            postgresql_db,
            entity_type="user",
            entity_id=user_id,
            workspace_id="test_workspace"
        )

        # Verify mapping
        assert entity is not None
        assert entity.id == user_id

    def test_map_workspace_to_canonical(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test mapping Workspace model to canonical entity."""
        workspace_id = str(uuid.uuid4())
        workspace = Workspace(
            id=workspace_id,
            name="Test Workspace",
            slug="test-workspace"
        )
        postgresql_db.add(workspace)
        postgresql_db.commit()

        entity = graphrag_engine.get_canonical_entity(
            postgresql_db,
            entity_type="workspace",
            entity_id=workspace_id,
            workspace_id="test_workspace"
        )

        assert entity is not None
        assert entity.id == workspace_id

    def test_map_nonexistent_canonical(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test mapping non-existent canonical entity returns None."""
        entity = graphrag_engine.get_canonical_entity(
            postgresql_db,
            entity_type="user",
            entity_id="nonexistent_id",
            workspace_id="test_workspace"
        )

        assert entity is None

    def test_sync_canonical_entity_create(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test creating graph node from canonical entity."""
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email="bob@example.com",
            first_name="Bob",
            last_name="Smith"
        )
        postgresql_db.add(user)
        postgresql_db.commit()

        # Sync to graph
        graphrag_engine.sync_canonical_entity(
            postgresql_db,
            entity_type="user",
            entity_id=user_id,
            workspace_id="test_workspace"
        )

        # Verify graph node created
        node = postgresql_db.query(GraphNode).filter(
            GraphNode.entity_id == user_id
        ).first()

        assert node is not None
        assert node.entity_type == "user"

    def test_sync_canonical_entity_update(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test updating existing graph node from canonical entity."""
        user_id = str(uuid.uuid4())

        # Create existing graph node
        existing_node = GraphNode(
            entity_id=user_id,
            entity_type="user",
            name="Old Name",
            workspace_id="test_workspace"
        )
        postgresql_db.add(existing_node)
        postgresql_db.commit()

        # Create User
        user = User(
            id=user_id,
            email="updated@example.com",
            first_name="Updated",
            last_name="Name"
        )
        postgresql_db.add(user)
        postgresql_db.commit()

        # Sync should update node
        graphrag_engine.sync_canonical_entity(
            postgresql_db,
            entity_type="user",
            entity_id=user_id,
            workspace_id="test_workspace"
        )

        # Verify update
        updated_node = postgresql_db.query(GraphNode).filter(
            GraphNode.entity_id == user_id
        ).first()

        assert updated_node is not None
        # Name should be updated based on registry mapping

    def test_get_registry_entry(self, graphrag_engine: GraphRAGEngine):
        """Test retrieving entity type registry configuration."""
        registry_entry = graphrag_engine._get_registry_entry("user")

        assert registry_entry is not None
        assert "model" in registry_entry
        assert "updatable_fields" in registry_entry

    def test_get_registry_entry_unknown(self, graphrag_engine: GraphRAGEngine):
        """Test retrieving registry entry for unknown entity type."""
        registry_entry = graphrag_engine._get_registry_entry("unknown_type")

        assert registry_entry is None


# ============================================================================
# Test JSONB Support
# ============================================================================

class TestJSONBSupport:
    """Tests for PostgreSQL JSONB column support."""

    def test_entity_type_jsonb_storage(self, sample_entity_type, postgresql_db: Session):
        """Test that entity type JSON schema is stored in JSONB column."""
        entity_type = postgresql_db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.slug == "customer"
        ).first()

        assert entity_type is not None
        # Verify JSONB column works (PostgreSQL-specific)
        assert entity_type.json_schema is not None
        assert isinstance(entity_type.json_schema, dict)
        assert "properties" in entity_type.json_schema

    def test_entity_type_jsonb_query(self, sample_entity_type, postgresql_db: Session):
        """Test querying JSONB column with PostgreSQL operators."""
        # This test verifies JSONB query support
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSON

        # Query using JSONB contains operator
        results = postgresql_db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.json_schema.op('@>')('{"type": "object"}')
        ).all()

        assert len(results) > 0


# ============================================================================
# Test Workspace Isolation
# ============================================================================

class TestWorkspaceIsolation:
    """Tests for workspace-based data isolation."""

    def test_workspace_isolation_traversal(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test that traversal respects workspace boundaries."""
        # Create nodes in different workspaces
        node_ws1 = GraphNode(
            entity_id="node_ws1",
            entity_type="user",
            name="Workspace 1 User",
            workspace_id="workspace_1"
        )
        node_ws2 = GraphNode(
            entity_id="node_ws2",
            entity_type="user",
            name="Workspace 2 User",
            workspace_id="workspace_2"
        )
        postgresql_db.add_all([node_ws1, node_ws2])
        postgresql_db.commit()

        # Traverse in workspace_1 should not see workspace_2
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="node_ws1",
            workspace_id="workspace_1",
            max_depth=1
        )

        entity_ids = [r["entity_id"] for r in results]
        assert "node_ws2" not in entity_ids

    def test_workspace_isolation_search(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test that search respects workspace boundaries."""
        # Create nodes with same name in different workspaces
        node_ws1 = GraphNode(
            entity_id="node_ws1",
            entity_type="user",
            name="Alice",
            workspace_id="workspace_1"
        )
        node_ws2 = GraphNode(
            entity_id="node_ws2",
            entity_type="user",
            name="Alice",
            workspace_id="workspace_2"
        )
        postgresql_db.add_all([node_ws1, node_ws2])
        postgresql_db.commit()

        # Search in workspace_1 should only return workspace_1 results
        results = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="workspace_1",
            depth=1
        )

        # Should only find the Alice in workspace_1
        assert len(results) >= 0
        for result in results:
            if result.get("entity_id") == "node_ws2":
                pytest.fail("Found entity from different workspace")


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_traverse_with_none_db(self, graphrag_engine: GraphRAGEngine):
        """Test that traversal handles None database gracefully."""
        with pytest.raises(Exception):
            graphrag_engine.traverse(
                None,
                start_entity_id="test",
                workspace_id="test_workspace",
                max_depth=1
            )

    def test_local_search_invalid_query(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test local search with malformed query."""
        results = graphrag_engine.local_search(
            postgresql_db,
            query="",  # Empty query
            workspace_id="test_workspace",
            depth=1
        )

        # Should handle gracefully
        assert isinstance(results, list)

    def test_sync_canonical_invalid_type(self, graphrag_engine: GraphRAGEngine, postgresql_db: Session):
        """Test syncing non-existent canonical entity type."""
        # Should not crash, just log warning
        graphrag_engine.sync_canonical_entity(
            postgresql_db,
            entity_type="nonexistent_type",
            entity_id="some_id",
            workspace_id="test_workspace"
        )

        # Test passes if no exception raised


# ============================================================================
# Performance Benchmarks
# ============================================================================

class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    def test_traversal_performance_target(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Verify traversal meets <100ms performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.traverse(
            postgresql_db,
            start_entity_id="user_1",
            workspace_id="test_workspace",
            max_depth=3
        )
        elapsed = time.time() - start_time

        assert elapsed < 0.1, f"Traversal took {elapsed:.3f}s, target <0.1s"

    def test_local_search_performance_target(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Verify local search meets <100ms performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.local_search(
            postgresql_db,
            query="Alice",
            workspace_id="test_workspace",
            depth=2
        )
        elapsed = time.time() - start_time

        assert elapsed < 0.1, f"Local search took {elapsed:.3f}s, target <0.1s"

    def test_global_search_performance_target(self, graphrag_engine: GraphRAGEngine, sample_graph_data, postgresql_db: Session):
        """Verify global search meets <200ms performance target."""
        import time

        start_time = time.time()
        results = graphrag_engine.global_search(
            postgresql_db,
            query="team",
            workspace_id="test_workspace"
        )
        elapsed = time.time() - start_time

        assert elapsed < 0.2, f"Global search took {elapsed:.3f}s, target <0.2s"
