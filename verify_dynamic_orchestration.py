
import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backend.core.byok_endpoints import BYOKManager, AIProviderConfig, APIKey
from backend.advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from backend.enhanced_ai_workflow_endpoints import RealAIWorkflowService

# Mocking
class MockAIService(RealAIWorkflowService):
    async def break_down_task(self, user_query, provider="moonshot"):
        print(f"Mock: Breaking down task '{user_query}' using {provider}")
        return [
            {
                "step_id": "step_1",
                "description": "Analyze the financial report",
                "complexity": 3,
                "step_type": "analysis"
            },
            {
                "step_id": "step_2",
                "description": "Summarize key findings",
                "complexity": 2,
                "step_type": "generation"
            },
            {
                "step_id": "step_3",
                "description": "Email summary to team",
                "complexity": 1,
                "step_type": "email_send"
            }
        ]

    async def process_with_nlu(self, text, provider="openai", system_prompt=None):
        print(f"Mock: Processing NLU with {provider}")
        return {
            "intent": "processed",
            "confidence": 0.9,
            "entities": []
        }

async def verify_dynamic_orchestration():
    print("--- Verifying Dynamic Orchestration ---")
    
    # 1. Setup BYOK Manager
    byok_manager = BYOKManager()
    # Ensure we have providers with reasoning levels
    byok_manager.providers["high_reasoning"] = AIProviderConfig(
        id="high_reasoning",
        name="High Reasoning Model",
        description="Test High Reasoning",
        api_key_env_var="TEST_KEY",
        supported_tasks=["reasoning", "analysis"],
        reasoning_level=4,
        cost_per_token=0.01
    )
    byok_manager.providers["medium_reasoning"] = AIProviderConfig(
        id="medium_reasoning",
        name="Medium Reasoning Model",
        description="Test Medium Reasoning",
        api_key_env_var="TEST_KEY",
        supported_tasks=["analysis", "general"],
        reasoning_level=2,
        cost_per_token=0.005
    )
    
    # Mock API keys
    byok_manager.api_keys["high_reasoning_default_production"] = APIKey(
        provider_id="high_reasoning",
        key_name="default",
        encrypted_key="mock_encrypted",
        key_hash="mock_hash",
        created_at=datetime.now(),
        environment="production"
    )
    byok_manager.api_keys["medium_reasoning_default_production"] = APIKey(
        provider_id="medium_reasoning",
        key_name="default",
        encrypted_key="mock_encrypted",
        key_hash="mock_hash",
        created_at=datetime.now(),
        environment="production"
    )
    
    # Mock decrypt to return something
    byok_manager.decrypt_api_key = lambda x: "mock_decrypted_key"
    
    # 2. Setup Orchestrator with Mock AI Service
    orchestrator = AdvancedWorkflowOrchestrator()
    orchestrator.ai_service = MockAIService()
    
    # 3. Generate Dynamic Workflow
    print("\n1. Generating Dynamic Workflow...")
    workflow = await orchestrator.generate_dynamic_workflow("Analyze Q3 financial report and email summary")
    
    print(f"Workflow Generated: {workflow.name}")
    print(f"Steps: {len(workflow.steps)}")
    for step in workflow.steps:
        print(f"  - Step: {step.step_id}, Type: {step.step_type}, Complexity: {step.parameters.get('complexity')}")
        
    # 4. Execute Workflow
    print("\n2. Executing Workflow...")
    # We need to mock get_byok_manager to return our instance
    import backend.advanced_workflow_orchestrator
    backend.advanced_workflow_orchestrator.get_byok_manager = lambda: byok_manager
    
    context = await orchestrator.execute_workflow(workflow.workflow_id, {"text": "Q3 Report Data"})
    
    print(f"\nExecution Status: {context.status}")
    print("Execution History:")
    for entry in context.execution_history:
        print(f"  - Step {entry['step_id']}: {entry['result'].get('status')}")
        if 'provider_used' in entry['result']:
            print(f"    Provider Used: {entry['result']['provider_used']}")
            
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_dynamic_orchestration())
