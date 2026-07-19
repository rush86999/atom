import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from core.agent_graduation_service import AgentGraduationService
from core.agent_graphrag_service import AgentGraphRAGService
from core.models import AgentRegistry, AgentStatus, GraphNode, GraphEdge
from core.memory.pomdp_memory_framework import MemoryManager, MemoryEntry, MemoryType

@pytest.mark.asyncio
async def test_graduation_triggered_consolidation():
    db = MagicMock()
    # Mock SQL agent registry query
    agent = AgentRegistry(
        id="agent1",
        name="Intern Agent",
        status=AgentStatus.INTERN,
        configuration={}
    )
    db.query().filter().first.return_value = agent
    
    # Mock MemoryManager & MemoryConsolidation
    mock_manager = MagicMock()
    mock_consolidator = MagicMock()
    mock_consolidator.consolidate_memories = AsyncMock(return_value=5)
    
    with patch("core.agent_graduation_service.get_memory_manager", return_value=mock_manager), \
         patch("core.memory.pomdp_memory_framework.MemoryConsolidation", return_value=mock_consolidator):
        
        service = AgentGraduationService(db=db)
        success = await service.promote_agent(
            agent_id="agent1",
            new_maturity="supervised",
            validated_by="user1"
        )
        
        assert success is True
        assert agent.status == AgentStatus.SUPERVISED
        mock_consolidator.consolidate_memories.assert_called_once_with("agent1")


@pytest.mark.asyncio
async def test_hybrid_graphrag_episodic_context():
    db = MagicMock()
    # Setup AgentGraphRAGService
    service = AgentGraphRAGService(db=db, workspace_id="ws1", agent_id="agent1")
    
    # Mock GraphRAG Engine query response
    service.graphrag.query = MagicMock(return_value={
        "mode": "global",
        "answer": "Leiden Community Summary on Sorting Algorithms."
    })
    
    # Mock MemoryManager and recall_hypothesis_trajectory
    mock_manager = MagicMock()
    mock_manager.recall_hypothesis_trajectory.return_value = {
        "winning_trajectory": [{"step": 1, "action": "quicksort"}],
        "pruned_failure_branches": ["bubblesort"]
    }
    
    with patch("core.memory.pomdp_memory_framework.get_memory_manager", return_value=mock_manager):
        res = await service.get_hybrid_context(query="optimize sort")
        
        assert res["has_results"] is True
        assert "Leiden Community Summary" in res["context"]
        assert "quicksort" in res["context"]
        assert "bubblesort" in res["context"]
        assert res["recalled_trajectory"] is not None
