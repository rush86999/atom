import asyncio
import os
import sys
import json

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

import sys
from unittest.mock import MagicMock

# Mock problematic dependencies before they are imported
sys.modules["dateparser"] = MagicMock()
sys.modules["atom_memory_service"] = MagicMock()
sys.modules["atom_search_service"] = MagicMock()
sys.modules["atom_workflow_service"] = MagicMock()
sys.modules["atom_ingestion_pipeline"] = MagicMock()
sys.modules["atom_slack_integration"] = MagicMock()
sys.modules["atom_teams_integration"] = MagicMock()
sys.modules["atom_google_chat_integration"] = MagicMock()
sys.modules["atom_discord_integration"] = MagicMock()

from integrations.chat_orchestrator import ChatOrchestrator
# Import models to register with SQLAlchemy
from core.models import Workspace, AgentJob, BusinessRule
from sales.models import Lead, Deal
from ecommerce.models import EcommerceOrder, Subscription
from saas.models import SaaSTier

async def verify_chat_health_integration():
    print("🚀 Verifying Atom Chat Agent Health Integration...")
    
    orchestrator = ChatOrchestrator()
    user_id = "test-user-123"
    workspace_id = "default-workspace"
    
    # Test Cases
    test_messages = [
        "What are my priorities today?",
        "What should I do today?",
        "Simulate hiring a new developer for $80k",
        "What is the impact of spending $10k on marketing?"
    ]
    
    # Mock AI Service to avoid network/key issues
    from integrations.ai_enhanced_service import ai_enhanced_service, AIResponse
    
    async def mock_call(request):
        if "priorities" in request.input_data.lower() or "do today" in request.input_data.lower():
            return AIResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                model_type=request.model_type,
                service_type=request.service_type,
                output_data={"rationale": "Your sales pipeline is strong. Focus on closing the top 3 high-intent leads."},
                confidence=0.95,
                processing_time=0.1,
                token_usage={},
                metadata={}
            )
        else:
            return AIResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                model_type=request.model_type,
                service_type=request.service_type,
                output_data={"roi": "180%", "breakeven": "5 months", "prediction": "This investment will likely pay off within 6 months given current growth."},
                confidence=0.9,
                processing_time=0.1,
                token_usage={},
                metadata={}
            )
            
    ai_enhanced_service.process_ai_request = mock_call
    
    for msg in test_messages:
        print(f"\n💬 Message: {msg}")
        response = await orchestrator.process_chat_message(
            user_id=user_id,
            message=msg,
            context={"workspace_id": workspace_id}
        )
        
        print(f"🎯 Intent: {response.get('intent')}")
        print(f"🤖 Atom Response:\n{response.get('message')}")
        print(f"💡 Suggested Actions: {response.get('suggested_actions')}")

    print("\n✅ Chat Health Integration Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_chat_health_integration())
