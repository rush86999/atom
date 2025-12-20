import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Mock basic dependencies to avoid import errors in restricted environment
import unittest.mock as mock

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStep, WorkflowStepType, WorkflowContext

async def verify_memory_integration():
    print("🚀 Starting AI Memory Integration Verification...")
    
    # 1. Mock Knowledge Manager
    async def mock_answer_query(self, query):
        # Return facts for Project Phoenix, but nothing for unknown stakeholders
        if "Project Phoenix" in query:
            return {
                "answer": "Project Phoenix is a top-secret initiative lead by Maya Manager.",
                "relevant_facts": ["Project Phoenix is a top-secret initiative.", "Maya Manager is the project lead."]
            }
        elif "Unknown Stakeholder" in query:
             return {
                "answer": "I don't have information about Unknown Stakeholder.",
                "relevant_facts": []
            }
        return {"answer": "No information found.", "relevant_facts": []}

    # Setup the mock
    import core.knowledge_query_endpoints
    core.knowledge_query_endpoints.get_knowledge_query_manager = lambda: type('MockKM', (), {'answer_query': mock_answer_query})()

    # 2. Setup Orchestrator
    orchestrator = AdvancedWorkflowOrchestrator()
    
    # 3. Verifying Context Injection
    print("\n2. Verifying Context Injection...")
    step = WorkflowStep(
        step_id="test_ai_step",
        step_type=WorkflowStepType.NLU_ANALYSIS,
        description="Verify context injection",
        parameters={"include_kg_context": True, "text_input": "Identify the project lead for Project Phoenix."}
    )
    
    context = WorkflowContext(
        workflow_id="test_wf",
        input_data={"text": "Identify the project lead for Project Phoenix."}
    )
    
    # Mock NLU processing
    captured_system_prompt = None
    async def mock_process(text, provider, system_prompt):
        nonlocal captured_system_prompt
        captured_system_prompt = system_prompt
        return {
            "intent": "identify project lead",
            "entities": ["Project Phoenix", "Maya Manager"],
            "confidence": 0.9,
            "tasks": [],
            "priority": "medium",
            "category": "general"
        }
    
    orchestrator.ai_service.process_with_nlu = mock_process
    
    result = await orchestrator._execute_nlu_analysis(step, context)
    
    print(f"Result Status: {result.get('status')}")
    if captured_system_prompt and "**Knowledge Context from ATOM KG:**" in captured_system_prompt:
        print("✅ Context injection verified in system prompt!")
        print(f"Captured Snapshot: {captured_system_prompt[:100]}...")
    else:
        print("❌ Knowledge context not found in prompt")

    # 4. Verify Missing Stakeholder Fallback
    print("\n3. Verifying Missing Stakeholder Fallback...")
    
    async def mock_process_missing(text, provider, system_prompt):
        return {
            "intent": "assign task",
            "entities": ["Unknown Stakeholder Manager", "Project Alpha"],
            "confidence": 0.8,
            "tasks": [],
            "priority": "high",
            "category": "urgent"
        }
    
    orchestrator.ai_service.process_with_nlu = mock_process_missing
    
    # Execute NLU analysis with a missing stakeholder
    result_missing = await orchestrator._execute_nlu_analysis(step, context)
    
    print(f"Result Status: {result_missing.get('status')}")
    if result_missing.get("status") == "waiting_approval":
        print(f"✅ Correct'ly paused for missing stakeholder: {result_missing.get('missing_entities')}")
        print(f"Message: {result_missing.get('message')}")
    else:
        print(f"❌ Failed to pause for missing stakeholder. Result: {result_missing}")

    print("\n🎉 AI Memory Integration Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_memory_integration())
