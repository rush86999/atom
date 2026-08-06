"""
Coverage-push tests for core.agent_graphrag_service (AgentGraphRAGService).

Mocks GraphRAGEngine and the POMDP memory manager. Targets >=70% coverage.
"""

from unittest.mock import Mock, AsyncMock, patch

import pytest

from core.agent_graphrag_service import AgentGraphRAGService


def make_service():
    engine = Mock()
    service = AgentGraphRAGService.__new__(AgentGraphRAGService)
    service.db = Mock()
    service.workspace_id = "ws-1"
    service.agent_id = "agent-1"
    service.graphrag = engine
    return service, engine


def local_result():
    return {
        "mode": "local",
        "entities": [
            {"id": "e1", "name": "Alpha", "type": "org", "description": "d1"},
            {"id": "e2", "name": "Beta", "type": "person", "description": "d2"},
        ],
        "relationships": [
            {"from": "e1", "to": "e2", "type": "works_at", "description": "x"},
            {"from": "e2", "to": "e1", "type": "manages"},
        ],
    }


class TestGetAgentContext:
    def test_init(self):
        with patch("core.agent_graphrag_service.GraphRAGEngine") as engine_cls:
            service = AgentGraphRAGService(Mock(), "ws-1", "agent-1")
        assert service.workspace_id == "ws-1"
        assert service.agent_id == "agent-1"
        engine_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_local_mode(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value=local_result())
        result = await service.get_agent_context("who is alpha", max_entities=1, max_relationships=1)
        assert result["agent_id"] == "agent-1"
        assert result["has_results"] is True
        assert len(result["entities"]) == 1
        assert len(result["relationships"]) == 1
        assert "Found 1 relevant entities" in result["context"]

    @pytest.mark.asyncio
    async def test_local_mode_empty_raises(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "local", "entities": [], "relationships": []})
        with pytest.raises(ValueError, match="No entities found"):
            await service.get_agent_context("query")

    @pytest.mark.asyncio
    async def test_global_mode(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "global", "answer": "Community summary"})
        result = await service.get_agent_context("overview", mode="global")
        assert result["has_results"] is True
        assert result["context"] == "Global Context: Community summary"

    @pytest.mark.asyncio
    async def test_global_mode_empty_answer_raises(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "global", "answer": "   "})
        with pytest.raises(ValueError, match="global search failed"):
            await service.get_agent_context("overview", mode="global")

    def test_format_context_local(self):
        service, _ = make_service()
        ctx = service._format_context(local_result())
        assert "- Alpha (org): d1" in ctx
        assert "Alpha -> Beta (works_at)" in ctx

    def test_format_context_global(self):
        service, _ = make_service()
        ctx = service._format_context({"mode": "global", "answer": "summary"})
        assert ctx == "Global Context: summary"

    def test_format_context_fallback_ids(self):
        service, _ = make_service()
        result = local_result()
        result["relationships"] = [{"from": "unknown-id", "to": "e2", "type": "t"}]
        ctx = service._format_context(result)
        assert "unknown-id -> Beta" in ctx


class TestValidateEntityRelationship:
    def _db_nodes(self, node_a, node_b, edge):
        from core.models import GraphNode, GraphEdge
        db = Mock()
        node_query = Mock()
        node_query.filter.return_value = node_query
        node_query.first.side_effect = [node_a, node_b]
        edge_query = Mock()
        edge_query.filter.return_value = edge_query
        edge_query.first.return_value = edge
        db.query = Mock(side_effect=lambda model: node_query if model is GraphNode else edge_query)
        return db

    @pytest.mark.asyncio
    async def test_relationship_found(self):
        service, _ = make_service()
        node_a = Mock(id="n1")
        node_b = Mock(id="n2")
        edge = Mock(relationship_type="works_at", weight=1.5, properties={"description": "desc"})
        service.db = self._db_nodes(node_a, node_b, edge)
        result = await service.validate_entity_relationship("Alpha", "Beta")
        assert result["exists"] is True
        assert result["relationship_type"] == "works_at"
        assert result["weight"] == 1.5

    @pytest.mark.asyncio
    async def test_relationship_with_type(self):
        service, _ = make_service()
        node_a = Mock(id="n1")
        node_b = Mock(id="n2")
        edge = Mock(relationship_type="works_at", weight=1.0, properties={})
        service.db = self._db_nodes(node_a, node_b, edge)
        result = await service.validate_entity_relationship("Alpha", "Beta", "works_at")
        assert result["description"] == "Alpha -> Beta"

    @pytest.mark.asyncio
    async def test_missing_node_raises(self):
        service, _ = make_service()
        service.db = self._db_nodes(None, Mock(id="n2"), None)
        with pytest.raises(ValueError, match="Entities not found"):
            await service.validate_entity_relationship("Alpha", "Beta")

    @pytest.mark.asyncio
    async def test_missing_edge_raises(self):
        from core.models import GraphNode, GraphEdge
        service, _ = make_service()
        node_a = Mock(id="n1")
        node_b = Mock(id="n2")
        node_query = Mock()
        node_query.filter.return_value = node_query
        node_query.first.side_effect = [node_a, node_b]
        edge_query = Mock()
        edge_query.filter.return_value = edge_query
        edge_query.first.return_value = None
        db = Mock()
        db.query = Mock(side_effect=lambda model: node_query if model is GraphNode else edge_query)
        service.db = db
        with pytest.raises(ValueError, match="No relationship found"):
            await service.validate_entity_relationship("Alpha", "Beta")


class TestGetHybridContext:
    @pytest.mark.asyncio
    async def test_with_trajectory(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "global", "answer": "ans"})
        manager = Mock()
        manager.recall_hypothesis_trajectory = Mock(return_value={
            "winning_trajectory": [{"a": 1}],
            "pruned_failure_branches": [{"b": 2}],
        })
        with patch("core.memory.pomdp_memory_framework.get_memory_manager", return_value=manager):
            result = await service.get_hybrid_context("query")
        assert "Recalled Experiential Context" in result["context"]
        assert result["recalled_trajectory"] is not None

    @pytest.mark.asyncio
    async def test_no_trajectory(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "global", "answer": "ans"})
        manager = Mock()
        manager.recall_hypothesis_trajectory = Mock(return_value=None)
        with patch("core.memory.pomdp_memory_framework.get_memory_manager", return_value=manager):
            result = await service.get_hybrid_context("query")
        assert result["recalled_trajectory"] is None

    @pytest.mark.asyncio
    async def test_memory_failure(self):
        service, engine = make_service()
        engine.query = AsyncMock(return_value={"mode": "global", "answer": "ans"})
        with patch("core.memory.pomdp_memory_framework.get_memory_manager", side_effect=RuntimeError("mem down")):
            result = await service.get_hybrid_context("query")
        assert result["recalled_trajectory"] is None
