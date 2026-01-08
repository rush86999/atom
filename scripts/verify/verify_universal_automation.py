import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def verify_universal_automation():
    print("🚀 Starting Universal Automation & Template Verification...\n")
    
    from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStepType, WorkflowStatus
    orchestrator = AdvancedWorkflowOrchestrator()
    
    # 1. Mock AI Service to avoid actual API calls
    mock_ai_service = MagicMock()
    mock_ai_service.cleanup_sessions = AsyncMock()
    mock_ai_service.initialize_sessions = AsyncMock()
    mock_ai_service.analyze_message = AsyncMock(return_value={"intent": "none", "confidence": 0.9})
    mock_ai_service.process_with_nlu = AsyncMock(return_value={"intent": "none", "entities": [], "confidence": 0.9})
    mock_ai_service.analyze_text = AsyncMock(return_value="Action completed successfully")
    
    # Inject mock AI service
    orchestrator.ai_service = mock_ai_service
    
    # 2. Test Case: GitHub + Stripe + Template
    query = "Set up a reusable template to notify Discord and create a Stripe invoice whenever a GitHub issue is opened."
    print(f"📝 Testing query: \"{query}\"")
    
    # Mock decomposition with Universal Integration and Template flag
    mock_decomposition = {
        "is_template": True,
        "category": "integration",
        "trigger": {
            "type": "event",
            "service": "github",
            "event": "issue_opened",
            "description": "Whenever a GitHub issue is opened"
        },
        "steps": [
            {
                "step_id": "step_1",
                "title": "Notify Discord",
                "description": "Send alert to Discord",
                "service": "discord",
                "action": "notify_channel",
                "parameters": {"channel": "#github-alerts"}
            },
            {
                "step_id": "step_2",
                "title": "Create Stripe Invoice",
                "description": "Create a new invoice in Stripe",
                "service": "stripe",
                "action": "create_invoice",
                "parameters": {"amount": "0", "customer": "pending"}
            }
        ]
    }
    
    mock_ai_service.break_down_task = AsyncMock(return_value=mock_decomposition)
    
    # Generate Workflow
    workflow_def = await orchestrator.generate_dynamic_workflow(query)
    
    print("\n✅ Generation Point:")
    print(f"  - Workflow ID: {workflow_def['id']}")
    print(f"  - Nodes Count: {len(workflow_def['nodes'])} (Expected 3)")
    assert len(workflow_def['nodes']) == 3
    
    # Check for template registration
    print(f"  - Template ID: {workflow_def.get('template_id')}")
    assert workflow_def.get("template_id") is not None
    
    # Verify Universal Integration Mapping
    internal_wf = orchestrator.workflows[workflow_def['id']]
    discord_step = next(s for s in internal_wf.steps if "discord" in s.description.lower())
    stripe_step = next(s for s in internal_wf.steps if "stripe" in s.description.lower())
    
    print(f"  - Discord Step Type: {discord_step.step_type.value} (Expected universal_integration)")
    print(f"  - Stripe Step Type: {stripe_step.step_type.value} (Expected universal_integration)")
    
    assert discord_step.step_type == WorkflowStepType.UNIVERSAL_INTEGRATION
    assert stripe_step.step_type == WorkflowStepType.UNIVERSAL_INTEGRATION
    
    # 3. Test Execution Simulation
    print("\n⚡ Testing Execution Simulation (Universal Dispatch)...")
    
    mock_manager = MagicMock()
    mock_manager.is_mock_mode.return_value = True
    
    with patch("core.mock_mode.get_mock_mode_manager", return_value=mock_manager):
        context = await orchestrator.execute_workflow(workflow_def["id"], {"user": "test_user"})
        
        print(f"  - Execution Status: {context.status}")
        assert context.status.value == "completed"
        
        # Verify Universal History
        for h in context.execution_history:
            if h['step_type'] == "universal_integration":
                print(f"    - Step {h['step_id']} ({h['result']['service']}): {h['status']}")
                assert h['status'] == "completed"
                assert h['result']['mock'] is True

    print("\n✨ ALL UNIVERSAL & TEMPLATE TESTS PASSED! ✨")

if __name__ == "__main__":
    asyncio.run(verify_universal_automation())
