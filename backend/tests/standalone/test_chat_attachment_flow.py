
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock dependencies to avoid full environment setup
sys.modules['core.database'] = MagicMock()
sys.modules['core.chat_session_manager'] = MagicMock()
sys.modules['api.agent_routes'] = MagicMock()
sys.modules['core.unified_search_endpoints'] = MagicMock()
sys.modules['core.automation_settings'] = MagicMock()
sys.modules['core.unified_task_endpoints'] = MagicMock()
sys.modules['api.document_routes'] = MagicMock()

# Mock Async Websockets
mock_ws_manager = MagicMock()
async def async_magic(): pass
mock_ws_manager.broadcast_event = MagicMock(side_effect=lambda *args, **kwargs: async_magic())
sys.modules['core.websockets'] = MagicMock()
sys.modules['core.websockets'].get_connection_manager.return_value = mock_ws_manager

# Mock Document Store for context injection
mock_doc_store = {
    "doc_123": {
        "title": "test_document.txt",
        "content": "This is a secret document about Project X."
    }
}
sys.modules['api.document_routes']._document_store = mock_doc_store

from integrations.chat_orchestrator import ChatOrchestrator, ChatIntent

async def test_attachment_flow():
    print("Initializing Chat Orchestrator (Mocked)...")
    
    # Mock the internal components of Orchestrator
    with patch('integrations.chat_orchestrator.get_chat_session_manager') as mock_get_manager:
        orchestrator = ChatOrchestrator()
        
        # Mock Session Manager methods
        orchestrator.session_manager.get_session.return_value = None
        orchestrator.session_manager.create_session.return_value = {"id": "test_session"}
        
        # Mock NLP Engine to avoid real API calls but verify call arguments
        mock_nlp = MagicMock()
        mock_nlp.parse_command.return_value = MagicMock(
            confidence=0.9, 
            command_type="analyze",
            primary_intent=ChatIntent.AI_ANALYTICS,
            entities=[],
            platforms=[]
        )
        mock_nlp.query_llm.return_value = "I analyzed the document. It is about Project X."
        
        orchestrator.ai_engines["nlp"] = mock_nlp
        
        print("\n--- Test Case: Chat with Attachment ---")
        user_message = "What is this file about?"
        context = {
            "attachments": [{"id": "doc_123", "name": "test_document.txt"}]
        }
        
        response = await orchestrator.process_chat_message(
            user_id="user_test",
            message=user_message,
            session_id="test_session",
            context=context
        )
        
        print(f"Response Success: {response.get('success')}")
        print(f"Response Message: {response.get('data', {}).get('message')}")
        
        # Verification
        # 1. Verify text injection
        # The Orchestrator calls _analyze_intent (or internally modifies message)
        # We can't easily see the internal variable 'message', but we can check what query_llm received.
        
        last_call_args = mock_nlp.query_llm.call_args
        if last_call_args:
            args, kwargs = last_call_args
            messages = args[0]
            last_message = messages[-1]['content']
            
            if "[USER ATTACHED FILES:]" in last_message:
                print("[PASS]: Attachment content was injected.")
            else:
                print("[FAIL]: Attachment content NOT found in LLM prompt.")
                print(f"Sent prompt: {last_message}")
                
            if "This is a secret document about Project X" in last_message:
                print("[PASS]: Document content present.")
            else:
                print("[FAIL]: Document content text missing.")
        else:
            print("[FAIL]: query_llm was never called.")

if __name__ == "__main__":
    asyncio.run(test_attachment_flow())
