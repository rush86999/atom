import asyncio
import os
import sys
import json
from datetime import datetime

# Add the backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from dotenv import load_dotenv
load_dotenv()

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStep, WorkflowStepType, WorkflowDefinition

async def verify_followup_automation():
    print("Starting Workflow Automation Verification...")
    
    # 1. Initialize Orchestrator
    orchestrator = AdvancedWorkflowOrchestrator()
    
    # Set Notion token if not in env
    notion_token = os.getenv('NOTION_TOKEN')
    if notion_token:
        os.environ['NOTION_ACCESS_TOKEN'] = notion_token
        print(f"  [INFO] Using Notion token: {notion_token[:10]}...")

    # 2. Gmail Fetch Configuration
    # Real Gmail is now authenticated!
    print("  [INFO] Using REAL Gmail integration.")
    
    # searching for a database or page to use
    from integrations.notion_service import NotionService
    notion = NotionService()
    
    # Try searching for anything accessible
    print("  [INFO] Searching for 'Atom Tasks' in Notion...")
    search_payload = {
        "query": "Atom Tasks",
        "filter": {"value": "database", "property": "object"}
    }
    search_response = notion.session.post(f"{notion.base_url}/search", json=search_payload)
    
    if search_response.status_code != 200:
        print(f"  [ERROR] Notion Search Failed: {search_response.status_code} - {search_response.text}")
        search_results = {}
    else:
        search_results = search_response.json()
        print(f"  [DEBUG] Found {len(search_results.get('results', []))} databases named 'Atom Tasks'.")
    
    database_id = None
    page_id = None
    
    if search_results.get('results'):
        for item in search_results['results']:
            if item['object'] == 'database':
                database_id = item['id']
                title_list = item.get('title', [])
                title = title_list[0]['plain_text'] if title_list else 'Untitled Database'
                print(f"  [INFO] Found Notion database: {title} ({database_id})")
                break
    
    if not database_id:
        print("  [WARN] 'Atom Tasks' database NOT found in search results.")
        # Try one last thing: search for ANY database if specific search failed
        print("  [INFO] Searching for ANY accessible database...")
        search_payload = {"filter": {"value": "database", "property": "object"}}
        search_results = notion.session.post(f"{notion.base_url}/search", json=search_payload).json()
        if search_results.get('results'):
             database_id = search_results['results'][0]['id']
             print(f"  [INFO] Using fallback database: {database_id}")

    # 2. Define a Test Workflow
    test_workflow = WorkflowDefinition(
        workflow_id="test_followup_verification",
        name="Test Follow-up Verification",
        description="Verify Gmail fetch (real), NLU analysis (real), and Notion creation (real)",
        steps=[
            WorkflowStep(
                step_id="fetch_emails",
                step_type=WorkflowStepType.GMAIL_FETCH,
                description="Fetch unread follow-up emails",
                parameters={"query": "label:inbox", "max_results": 5}, 
                next_steps=["analyze_content"]
            ),
            WorkflowStep(
                step_id="analyze_content",
                step_type=WorkflowStepType.NLU_ANALYSIS,
                description="Extract tasks from emails using AI",
                parameters={
                    "complexity": 3,
                    "text_input": "Analyze these emails for follow-up tasks: {{fetch_emails.messages}}"
                },
                next_steps=["filter_relevance"]
            ),
            WorkflowStep(
                step_id="filter_relevance",
                step_type=WorkflowStepType.CONDITIONAL_LOGIC,
                description="Filter out marketing/spam emails",
                parameters={
                    "conditions": [
                        {
                            "if": "relevance == 'relevant'",
                            "then": ["create_notion_task"]
                        }
                    ]
                }
            ),
            WorkflowStep(
                step_id="create_notion_task",
                step_type=WorkflowStepType.NOTION_INTEGRATION,
                description="Create task in Notion",
                parameters={
                    "action": "create_page",
                    "database_id": database_id,
                    "title": "Tasks: {{analyze_content.intent}}",
                    "content": "{{analyze_content.tasks}}"
                },
                next_steps=["create_notion_notes"]
            ),
            WorkflowStep(
                step_id="create_notion_notes",
                step_type=WorkflowStepType.NOTION_INTEGRATION,
                description="Create note in Notion",
                parameters={
                    "action": "create_page",
                    "database_id": database_id,
                    "title": "Meeting Notes: Deepgram Webinar",
                    "content": "Attendee list: ['Rish', 'Antigravity']\nSummary: The webinar discussed multi-agent voice AI architecture."
                },
                next_steps=[]
            )
        ],
        start_step="fetch_emails"
    )
    
    orchestrator.workflows[test_workflow.workflow_id] = test_workflow
    
    print(f"Executing workflow: {test_workflow.name}")
    
    # 3. Input Data
    input_data = {
        "text": "Identify and extract follow-up tasks from my latest emails."
    }
    
    # 4. Execute Workflow
    try:
        context = await orchestrator.execute_workflow(test_workflow.workflow_id, input_data)
        
        print(f"\nWorkflow Status: {context.status.value}")
        print(f"Steps Executed: {len(context.execution_history)}")
        
        for entry in context.execution_history:
            step_id = entry.get('step_id')
            res = entry.get('result', {})
            status = res.get('status', 'unknown')
            print(f"  - Step {step_id}: {status}")
            
            if status == "failed":
                print(f"    Error: {res.get('error')}")
            else:
                # Print output snippet
                if step_id == "analyze_content":
                    print(f"    Intent: {res.get('intent')}")
                    tasks = res.get('tasks', [])
                    print(f"    Tasks Found: {len(tasks)}")
                    for i, task in enumerate(tasks):
                        print(f"      {i+1}. {task}")
                elif step_id == "create_notion_task":
                    nr = res.get('notion_result')
                    if nr:
                         print(f"    Notion Page ID: {nr.get('id')}")
                    else:
                         print(f"    No Notion result returned")
        
        if context.status.value == "completed":
            print("\nVerification SUCCESSFUL!")
        else:
            print("\nVerification FAILED!")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nVerification ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(verify_followup_automation())
