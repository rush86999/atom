import asyncio
import os
import sys
import json

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.business_health_service import business_health_service
# Import these to ensure SQLAlchemy models are registered
from core.models import Workspace, AgentJob, BusinessRule
from sales.models import Lead, Deal
from ecommerce.models import EcommerceOrder, Subscription
from saas.models import SaaSTier  # Critical fix for SaaSTier error
from unittest.mock import patch, MagicMock
from integrations.ai_enhanced_service import AIResponse, AITaskType, AIModelType, AIServiceType

async def verify_business_health():
    print("🚀 Verifying Business Health Intelligence (Phase 8)...")
    
    # Mock the AI service
    from integrations.ai_enhanced_service import ai_enhanced_service
    
    original_process = ai_enhanced_service.process_ai_request
    
    async def mock_call(request):
        if "prioritize" in request.request_id:
            return AIResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                model_type=request.model_type,
                service_type=request.service_type,
                output_data={"rationale": "Focus on high-intent lead follow-ups to maximize immediate revenue."},
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
                output_data={"roi": "150%", "breakeven": "4 months", "prediction": "Hiring will increase capacity by 20% and stabilize cash flow."},
                confidence=0.9,
                processing_time=0.1,
                token_usage={},
                metadata={}
            )
            
    ai_enhanced_service.process_ai_request = mock_call
    
    try:
        workspace_id = "default-workspace"
        
        # 1. Test Daily Priorities
        print("\n--- 1. Testing Daily Priorities ---")
        priorities_result = await business_health_service.get_daily_priorities(workspace_id)
        print(f"Advice: {priorities_result.get('owner_advice')}")
        print(f"Num Priorities: {len(priorities_result.get('priorities', []))}")
        for p in priorities_result.get('priorities', []):
            print(f"  [{p['priority']}] {p['type']}: {p['title']}")

        # 2. Test Strategic Simulation
        print("\n--- 2. Testing Strategic Simulation (Hiring) ---")
        sim_data = {"role": "HVAC Technician", "salary": 65000}
        sim_result = await business_health_service.simulate_decision(workspace_id, "HIRING", sim_data)
        
        if isinstance(sim_result, dict) and "error" in sim_result:
            print(f"Simulation Error: {sim_result['error']}")
        elif isinstance(sim_result, dict):
            print(f"Sim Prediction: {sim_result.get('prediction', 'No prediction summary available')}")
            print(f"ROI: {sim_result.get('roi', 'N/A')}")
            print(f"Breakeven: {sim_result.get('breakeven', 'N/A')}")
        else:
            print(f"Unexpected sim_result type: {type(sim_result)} - {sim_result}")

        print("\n✅ Business Health Verification Complete!")
    finally:
        ai_enhanced_service.process_ai_request = original_process

    print("\n✅ Business Health Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_business_health())
