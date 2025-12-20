
import asyncio
import os
import sys
from datetime import datetime
import uuid

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from advanced_workflow_orchestrator import (
    AdvancedWorkflowOrchestrator, 
    WorkflowDefinition, 
    WorkflowStep, 
    WorkflowStepType,
    WorkflowStatus
)

class MockAIService:
    async def initialize_sessions(self): pass
    async def cleanup_sessions(self): pass

async def verify_confidence_gates():
    print("🚀 Starting Human-in-the-Loop Verification...")
    
    orchestrator = AdvancedWorkflowOrchestrator()
    orchestrator.ai_service = MockAIService()
    
    # 1. Define a workflow with a low-confidence step
    # We'll use a step type that we can easily mock the result for
    workflow = WorkflowDefinition(
        workflow_id="hitl_wf",
        name="HITL Workflow",
        description="Verify confidence gating",
        steps=[
            WorkflowStep(
                step_id="uncertain_step",
                step_type=WorkflowStepType.DATA_TRANSFORMATION, # Use a simple type
                description="A step that might be uncertain",
                confidence_threshold=0.8,
                next_steps=["follow_up"]
            ),
            WorkflowStep(
                step_id="follow_up",
                step_type=WorkflowStepType.SLACK_NOTIFICATION,
                description="Step after approval",
                parameters={"channel": "#general", "message": "Resumed successfully"},
                next_steps=[]
            )
        ],
        start_step="uncertain_step"
    )
    orchestrator.workflows["hitl_wf"] = workflow
    
    # Monkey patch _execute_step_by_type to return low confidence for this test
    original_execute = orchestrator._execute_step_by_type
    
    async def mock_execute(wf, step, context):
        if step.step_id == "uncertain_step":
            return {"status": "completed", "confidence": 0.5, "transformed_data": "foo"}
        return await original_execute(wf, step, context)
        
    orchestrator._execute_step_by_type = mock_execute
    
    print("🔍 Executing workflow with low confidence (0.5 < 0.8)...")
    context = await orchestrator.execute_workflow("hitl_wf", {}, {"user_id": "user_1"})
    
    assert context.status == WorkflowStatus.WAITING_APPROVAL, f"Workflow should be waiting approval, but is {context.status}"
    assert "uncertain_step" in context.results
    assert context.results["uncertain_step"]["status"] == "waiting_approval"
    print("   ✅ Workflow successfully paused for approval.")
    
    # 2. Test Resumption
    print("🔍 Approving and resuming workflow...")
    execution_id = context.workflow_id
    
    # Mock resume - wait for _continue_workflow to finish
    resumed_context = await orchestrator.resume_workflow(execution_id, "uncertain_step")
    
    # Since _continue_workflow runs in a task, we need to wait a bit
    await asyncio.sleep(0.5)
    
    assert resumed_context.status == WorkflowStatus.COMPLETED, f"Workflow should be completed after resume, but is {resumed_context.status}"
    assert "follow_up" in resumed_context.results
    assert resumed_context.results["follow_up"]["status"] == "completed"
    print("   ✅ Workflow successfully resumed and completed.")
    
    print("✅ VERIFICATION SUCCESSFUL: Human-in-the-Loop confidence gates are working!")

if __name__ == "__main__":
    asyncio.run(verify_confidence_gates())
