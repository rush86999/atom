import pytest
from sqlalchemy.orm import Session
from core.memory_consolidation import MemoryConsolidationService
from core.models import AgentMemory, AgentRegistry
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_memory_consolidation_tenant_isolation(db_session: Session):
    # 1. Setup agents and memories for two tenants
    agent1 = AgentRegistry(
        id="agent-1", name="Agent 1", workspace_id="ws-1", tenant_id="tenant-1",
        category="Test", module_path="test", class_name="Test"
    )
    agent2 = AgentRegistry(
        id="agent-2", name="Agent 2", workspace_id="ws-2", tenant_id="tenant-2",
        category="Test", module_path="test", class_name="Test"
    )
    db_session.add(agent1)
    db_session.add(agent2)
    db_session.commit()

    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    
    mem1 = AgentMemory(
        agent_id="agent-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        content="Tenant 1 memory",
        importance_score=0.8,
        created_at=cutoff
    )
    mem2 = AgentMemory(
        agent_id="agent-2",
        workspace_id="ws-2",
        tenant_id="tenant-2",
        content="Tenant 2 memory",
        importance_score=0.8,
        created_at=cutoff
    )
    db_session.add(mem1)
    db_session.add(mem2)
    db_session.commit()

    # 2. Consolidate tenant 1 only
    service = MemoryConsolidationService(workspace_id="ws-1", tenant_id="tenant-1")
    
    # Mock LanceDB to avoid real IO
    with patch("core.memory_consolidation.get_lancedb_handler") as mock_lancedb:
        mock_handler = MagicMock()
        mock_handler.add_document.return_value = True
        mock_lancedb.return_value = mock_handler
        
        # We need to ensure MemoryConsolidationService uses our test DB session
        # The current implementation uses SessionLocal() internally. 
        # For testing, we might need to patch SessionLocal.
        with patch("core.memory_consolidation.SessionLocal", return_value=db_session):
            stats = await service.consolidate_all_memories()
            
            assert stats["memories_archived"] == 1
            
            # Verify tenant 1 memory is archived
            db_session.refresh(mem1)
            assert mem1.metadata_json.get("_archived") == "true"
            
            # Verify tenant 2 memory is NOT archived
            db_session.refresh(mem2)
            assert mem2.metadata_json is None or "_archived" not in mem2.metadata_json
