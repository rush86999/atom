import asyncio
import os
import json
import logging
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowDefinition, WorkflowStep, WorkflowStepType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_search_nodes():
    print("Starting Search Nodes Verification...")
    orchestrator = AdvancedWorkflowOrchestrator()
    
    # Workflow: Search Across Everything
    search_workflow = WorkflowDefinition(
        workflow_id="search_verification",
        name="Search Verification Workflow",
        description="Verifies all new search node types",
        steps=[
            WorkflowStep(
                step_id="gmail_search",
                step_type=WorkflowStepType.GMAIL_SEARCH,
                description="Search Gmail for recent atom messages",
                parameters={"query": "atom", "max_results": 2},
                next_steps=["notion_search"]
            ),
            WorkflowStep(
                step_id="notion_search",
                step_type=WorkflowStepType.NOTION_SEARCH,
                description="Search Notion for atom pages",
                parameters={"query": "atom", "page_size": 2},
                next_steps=["notion_db_query"]
            ),
            WorkflowStep(
                step_id="notion_db_query",
                step_type=WorkflowStepType.NOTION_DB_QUERY,
                description="Search Notion DB with AI filter",
                parameters={
                    "database_id": "2cd94123-8441-800a-98c3-ecb8484770f5", # Standard Atom Tasks DB
                    "ai_filter_query": "high priority tasks that are not done",
                    "page_size": 5
                },
                next_steps=["app_memory_search"]
            ),
            WorkflowStep(
                step_id="app_memory_search",
                step_type=WorkflowStepType.APP_SEARCH,
                description="Search App Memory (LanceDB) for atom communications",
                parameters={"query": "atom", "limit": 5}
            )
        ],
        start_step="gmail_search"
    )
    
    print(f"Executing workflow: {search_workflow.name}")
    context = await orchestrator.execute_workflow(search_workflow)
    
    print("\n--- Verification Results ---")
    for step_id, result in context.results.items():
        status = result.get("status", "unknown")
        count = result.get("count", 0)
        print(f"Step {step_id}: {status} (Count: {count})")
        if status == "failed":
            print(f"  Error: {result.get('error')}")
            
    if all(r.get("status") == "completed" for r in context.results.values()):
        print("\nAll Search Nodes Verified Successfully!")
    else:
        print("\nSome Search Nodes Failed Verification.")

if __name__ == "__main__":
    asyncio.run(verify_search_nodes())
