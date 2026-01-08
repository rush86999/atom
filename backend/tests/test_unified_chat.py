
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from integrations.chat_orchestrator import ChatOrchestrator, ChatIntent, FeatureType, PlatformType
from core.auto_document_ingestion import AutoDocumentIngestionService, IngestionSettings
from datetime import datetime

@pytest.fixture
def mock_chat_orchestrator():
    orchestrator = ChatOrchestrator()
    orchestrator._initialize_ai_engines = MagicMock() # Mock out AI engines
    orchestrator.ai_engines = {}
    return orchestrator

@pytest.mark.asyncio
async def test_chat_triggers_automation_agent(mock_chat_orchestrator):
    """Test that automation requests trigger execute_agent_task"""
    
    # Mock dependency
    with patch("integrations.chat_orchestrator.execute_agent_task", new_callable=AsyncMock) as mock_execute:
        
        # Test input
        message = "Check competitor prices"
        session = {"id": "test_session", "user_id": "user1"}
        intent_analysis = {
            "primary_intent": ChatIntent.AUTOMATION_TRIGGER,
            "confidence": 0.9,
            "platforms": []
        }
        
        # Call handler directly
        response = await mock_chat_orchestrator._handle_automation_request(
            message, intent_analysis, session, {}
        )
        
        # Verify
        assert response["success"] is True
        assert response["data"]["agent_id"] == "competitive_intel"
        
        # Verify execute_agent_task call
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[0][0] == "competitive_intel"
        assert call_args[0][1]["request"] == message
        assert call_args[0][1]["session_id"] == "test_session"

@pytest.mark.asyncio
async def test_chat_routes_to_meta_agent(mock_chat_orchestrator):
    """Test that agent requests route to AtomMetaAgent"""
    
    # Mock Atom
    with patch("core.atom_meta_agent.get_atom_agent") as mock_get_atom:
        mock_atom = MagicMock()
        mock_atom.execute = AsyncMock(return_value={
            "final_output": "I have spawned a sales agent.",
            "actions_executed": [],
            "spawned_agent": "sales_assistant"
        })
        mock_get_atom.return_value = mock_atom
        
        # Test input
        message = "Help me analyze my sales pipeline"
        session = {"id": "test_session", "user_id": "user1"}
        intent_analysis = {
            "primary_intent": ChatIntent.AGENT_REQUEST,
            "confidence": 0.9
        }
        
        # Call handler
        response = await mock_chat_orchestrator._handle_agent_request(
            message, intent_analysis, session, {}
        )
        
        # Verify
        assert response["status"] == "success"
        assert response["agent_response"] == "I have spawned a sales agent."
        
        # Verify Atom execute call
        mock_atom.execute.assert_called_once()
        call_kwargs = mock_atom.execute.call_args[1]
        assert call_kwargs["request"] == message
        assert call_kwargs["context"]["session_id"] == "test_session"


@pytest.mark.asyncio
async def test_ingestion_triggers_atom():
    """Test that document ingestion triggers AtomMetaAgent"""
    
    workspace_id = "test_ws"
    service = AutoDocumentIngestionService(workspace_id)
    
    # Mock internal methods
    service._list_files = AsyncMock(return_value=[
        {"id": "file1", "name": "financials.pdf", "size": 1000, "modified_at": datetime.now()}
    ])
    service._download_file = AsyncMock(return_value=b"Updated content")
    service.parser.parse_document = AsyncMock(return_value="Valid text content")
    service.memory_handler = MagicMock()
    service.memory_handler.add_document.return_value = True
    
    # Mock Atom Trigger
    with patch("core.atom_meta_agent.handle_data_event_trigger", new_callable=AsyncMock) as mock_trigger:
        
        # Execute sync (force=True to bypass disabled check logic if we mock settings, but let's just mock settings)
        service.get_settings = MagicMock(return_value=IngestionSettings(
            integration_id="google_drive", 
            workspace_id=workspace_id, 
            enabled=True,
            file_types=["pdf"]
        ))
        
        result = await service.sync_integration("google_drive", force=True)
        
        # Verify success
        assert result["success"] is True
        assert result["files_ingested"] == 1
        
        # Verify Trigger
        mock_trigger.assert_called_once()
        call_kwargs = mock_trigger.call_args[1]
        assert call_kwargs["event_type"] == "document_ingestion"
        assert call_kwargs["data"]["count"] == 1
        assert "financials.pdf" in call_kwargs["data"]["files"][0]
