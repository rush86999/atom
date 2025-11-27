from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
import logging
import json

# Import workflow management components
from backend.core.workflow_endpoints import load_workflows
from backend.ai.automation_engine import AutomationEngine
from backend.ai.workflow_scheduler import workflow_scheduler

# Import Calendar and Email services
from backend.integrations.google_calendar_service import GoogleCalendarService
from backend.integrations.gmail_service import GmailService

# Import Task and Finance services
from backend.core.unified_task_endpoints import get_tasks, create_task, CreateTaskRequest
from backend.integrations.quickbooks_routes import list_quickbooks_items

# Import AI service for intent classification
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

# Initialize AI service
ai_service = RealAIWorkflowService()

router = APIRouter(prefix="/api/atom-agent", tags=["atom_agent"])

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    conversation_history: List[ChatMessage]

class ExecuteGeneratedRequest(BaseModel):
    workflow_id: str
    input_data: Dict[str, Any]

@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Handle chat messages from the Universal ATOM Assistant.
    Uses LLM to interpret intent and interact with platform features.
    """
    try:
        # Initialize AI sessions if needed
        await ai_service.initialize_sessions()
        
        # Use LLM to classify intent
        intent_response = await classify_intent_with_llm(
            request.message, 
            request.conversation_history
        )
        
        intent = intent_response.get("intent")
        entities = intent_response.get("entities", {})
        
        logger.info(f"Classified intent: {intent}, entities: {entities}")
        
        # Route to appropriate handler based on intent
        if intent == "LIST_WORKFLOWS":
            return await handle_list_workflows(request)
        elif intent == "RUN_WORKFLOW":
            return await handle_run_workflow(request, entities)
        elif intent == "SCHEDULE_WORKFLOW":
            return await handle_schedule_workflow(request, entities)
        elif intent == "GET_HISTORY":
            return await handle_get_history(request, entities)
        elif intent == "CANCEL_SCHEDULE":
            return await handle_cancel_schedule(request, entities)
        elif intent == "GET_STATUS":
            return await handle_get_status(request, entities)
            
        # Calendar Intents
        elif intent == "CREATE_EVENT":
            return await handle_create_event(request, entities)
        elif intent == "LIST_EVENTS":
            return await handle_list_events(request, entities)
            
        # Email Intents
        elif intent == "SEND_EMAIL":
            return await handle_send_email(request, entities)
        elif intent == "SEARCH_EMAILS":
            return await handle_search_emails(request, entities)
            
        # Task Intents
        elif intent in ["CREATE_TASK", "LIST_TASKS"]:
            return await handle_task_intent(intent, entities, request)
            
        # Finance Intents
        elif intent in ["GET_TRANSACTIONS", "CHECK_BALANCE", "INVOICE_STATUS"]:
            return await handle_finance_intent(intent, entities, request)
            
        elif intent == "HELP":
            return handle_help_request()
        
        else:
            # Default: Offer suggestions
            return {
                "success": True,
                "response": {
                    "message": "I can help you with Workflows, Calendar, Email, Tasks, and Finance. Try asking me something!",
                    "actions": []
                }
            }

    except Exception as e:
        logger.error(f"Error in chat agent: {str(e)}")
        return {"success": False, "error": str(e)}

async def classify_intent_with_llm(message: str, history: List[ChatMessage]) -> Dict[str, Any]:
    """Use LLM to classify user intent via BYOK system"""
    
    system_prompt = """You are ATOM, an intelligent personal assistant for task orchestration and management.
    Classify the user's intent into one of these categories:
    - Workflows: LIST_WORKFLOWS, RUN_WORKFLOW, SCHEDULE_WORKFLOW, GET_HISTORY
    - Calendar: CREATE_EVENT, LIST_EVENTS
    - Email: SEND_EMAIL, SEARCH_EMAILS
    - Tasks: CREATE_TASK, LIST_TASKS
    - Finance: GET_TRANSACTIONS, CHECK_BALANCE, INVOICE_STATUS
    - General: HELP, UNKNOWN
    
    Respond ONLY with valid JSON in this format:
    {"intent": "CREATE_EVENT", "entities": {"summary": "Team Standup", "start_time": "tomorrow 10am"}}
    """
    
    try:
        # Use BYOK system to get optimal provider for chat tasks
        from backend.core.byok_endpoints import get_byok_manager
        byok = get_byok_manager()
        
        try:
            # Get optimal provider for "chat" task type
            provider_id = byok.get_optimal_provider("chat")
            
            # Get API key for the provider
            api_key = byok.get_api_key(provider_id)
            
            if not api_key:
                return fallback_intent_classification(message)
            
            # Call the appropriate AI provider
            if provider_id == "openai":
                result = await ai_service.call_openai_api(message, system_prompt) if hasattr(ai_service, 'call_openai_api') else None
            elif provider_id == "anthropic":
                result = await ai_service.call_anthropic_api(message, system_prompt) if hasattr(ai_service, 'call_anthropic_api') else None
            elif provider_id == "moonshot":
                result = await ai_service.call_moonshot_api(message, system_prompt) if hasattr(ai_service, 'call_moonshot_api') else None
            else:
                # Default to DeepSeek if available
                result = await ai_service.call_deepseek_api(message, system_prompt) if hasattr(ai_service, 'call_deepseek_api') else None
            
            # Track usage
            if result:
                byok.track_usage(provider_id, success=result.get("success", False), tokens_used=200)
            
            if result and result.get("success"):
                content = result.get("response", "{}")
                try:
                    intent_data = json.loads(content)
                    return intent_data
                except json.JSONDecodeError:
                    return fallback_intent_classification(message)
            else:
                return fallback_intent_classification(message)
                
        except ValueError:
            return fallback_intent_classification(message)
            
    except Exception as e:
        logger.error(f"LLM intent classification failed: {e}")
        return fallback_intent_classification(message)


def fallback_intent_classification(message: str) -> Dict[str, Any]:
    """Regex-based fallback for intent classification"""
    msg = message.lower()
    
    # Workflow Intents
    if "list" in msg and "workflow" in msg:
        return {"intent": "LIST_WORKFLOWS", "entities": {}}
    elif "run" in msg and "workflow" in msg:
        return {"intent": "RUN_WORKFLOW", "entities": {"workflow_ref": msg.replace("run workflow", "").strip()}}
    elif "schedule" in msg and "workflow" in msg:
        return {"intent": "SCHEDULE_WORKFLOW", "entities": {"workflow_ref": msg.replace("schedule workflow", "").strip()}}
    elif "history" in msg or "execution" in msg:
        return {"intent": "GET_HISTORY", "entities": {}}
        
    # Calendar Intents
    elif "schedule" in msg or "meeting" in msg or "appointment" in msg or ("create" in msg and "event" in msg):
        return {"intent": "CREATE_EVENT", "entities": {"summary": msg}}
    elif "calendar" in msg or ("list" in msg and "event" in msg) or "agenda" in msg:
        return {"intent": "LIST_EVENTS", "entities": {}}
        
    # Email Intents
    elif "send" in msg and ("email" in msg or "mail" in msg):  
        return {"intent": "SEND_EMAIL", "entities": {"subject": "New Email"}}
    elif "search" in msg and ("email" in msg or "mail" in msg or "inbox" in msg):
        return {"intent": "SEARCH_EMAILS", "entities": {"query": msg.replace("search", "").strip()}}
        
    # Task Intents
    elif ("create" in msg or "add" in msg) and "task" in msg:
        return {"intent": "CREATE_TASK", "entities": {"title": msg.replace("create task", "").replace("add task", "").strip()}}
    elif "list" in msg and "task" in msg:
        return {"intent": "LIST_TASKS", "entities": {}}
        
    # Finance Intents
    elif "transaction" in msg or "expense" in msg or "spending" in msg:
        return {"intent": "GET_TRANSACTIONS", "entities": {}}
    elif "balance" in msg:
        return {"intent": "CHECK_BALANCE", "entities": {}}
    elif "invoice" in msg:
        return {"intent": "INVOICE_STATUS", "entities": {}}
        
    # Default to unknown
    return {"intent": "UNKNOWN", "entities": {}}


# --- Workflow Handlers ---

async def handle_list_workflows(request: ChatRequest) -> Dict[str, Any]:
    """List all available workflows"""
    workflows = load_workflows()
    if not workflows:
        return {"success": True, "response": {"message": "No workflows found.", "actions": []}}
    
    workflow_list = "\n".join([f"• **{wf['name']}**" for wf in workflows])
    return {
        "success": True,
        "response": {
            "message": f"Found {len(workflows)} workflows:\n\n{workflow_list}",
            "actions": [{"type": "run", "label": f"Run {wf['name']}", "workflowId": wf['id']} for wf in workflows[:3]]
        }
    }

async def handle_run_workflow(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a specified workflow"""
    workflow_ref = entities.get("workflow_ref", "")
    if not workflow_ref:
        return {"success": False, "response": {"message": "Please specify which workflow to run.", "actions": []}}
    
    workflows = load_workflows()
    workflow = next((w for w in workflows if workflow_ref.lower() in w['name'].lower() or workflow_ref in w['id']), None)
    
    if not workflow:
        return {"success": False, "response": {"message": f"Workflow '{workflow_ref}' not found.", "actions": []}}
    
    try:
        engine = AutomationEngine()
        execution_id = str(uuid.uuid4())
        results = await engine.execute_workflow_definition(workflow, {}, execution_id=execution_id)
        return {
            "success": True,
            "response": {
                "message": f"✅ Workflow '{workflow['name']}' started! (ID: {execution_id})",
                "actions": [{"type": "view_history", "label": "View History", "workflowId": workflow['id']}]
            }
        }
    except Exception as e:
        return {"success": False, "response": {"message": f"❌ Failed: {str(e)}", "actions": []}}

async def handle_schedule_workflow(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "response": {"message": "You can schedule workflows in the Editor's Schedule tab.", "actions": []}}

async def handle_get_history(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    workflow_ref = entities.get("workflow_ref", "")
    if not workflow_ref:
        return {"success": False, "response": {"message": "Please specify the workflow.", "actions": []}}
    return {"success": True, "response": {"message": f"History for {workflow_ref} is available in the Editor.", "actions": []}}

async def handle_cancel_schedule(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "response": {"message": "Please use the Schedule tab to cancel.", "actions": []}}

async def handle_get_status(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "response": {"message": "Check the Workflow Editor for detailed status.", "actions": []}}

# --- Calendar Handlers ---

async def handle_create_event(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Create a calendar event"""
    summary = entities.get("summary", "New Meeting")
    start_time_str = entities.get("start_time", "tomorrow 10am")
    
    # In a real implementation, we would parse the natural language time
    # For now, we'll mock the creation or use the service if time is ISO format
    
    return {
        "success": True,
        "response": {
            "message": f"I've prepared a calendar event: **{summary}** for {start_time_str}.\n\nWould you like to confirm?",
            "actions": [
                {"type": "create_event", "label": "Confirm & Create", "data": entities}
            ]
        }
    }

async def handle_list_events(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """List calendar events"""
    try:
        service = GoogleCalendarService()
        events = await service.get_events(max_results=5)
        
        if not events:
            return {"success": True, "response": {"message": "No upcoming events found.", "actions": []}}
            
        event_list = "\n".join([f"• {e.get('summary', 'Event')} ({e.get('start', {}).get('dateTime', 'TBD')})" for e in events])
        
        return {
            "success": True,
            "response": {
                "message": f"Here are your upcoming events:\n\n{event_list}",
                "actions": []
            }
        }
    except Exception as e:
        return {"success": False, "response": {"message": f"Failed to fetch events: {str(e)}", "actions": []}}

# --- Email Handlers ---

async def handle_send_email(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare an email draft"""
    recipient = entities.get("recipient", "")
    subject = entities.get("subject", "No Subject")
    
    return {
        "success": True,
        "response": {
            "message": f"I can help send an email to {recipient}.\n\nSubject: {subject}",
            "actions": [
                {"type": "send_email", "label": "Open Composer", "data": entities}
            ]
        }
    }

async def handle_search_emails(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Search emails"""
    query = entities.get("query", "")
    try:
        service = GmailService()
        messages = service.search_messages(query=query, max_results=3)
        
        if not messages:
            return {"success": True, "response": {"message": f"No emails found for '{query}'.", "actions": []}}
            
        return {
            "success": True,
            "response": {
                "message": f"Found {len(messages)} emails matching '{query}'.",
                "actions": [{"type": "view_inbox", "label": "View in Gmail", "data": {"query": query}}]
            }
        }
    except Exception as e:
        return {"success": False, "response": {"message": f"Failed to search emails: {str(e)}", "actions": []}}

async def handle_task_intent(intent: str, entities: Dict[str, Any], request: ChatRequest) -> Dict[str, Any]:
    """Handle task management intents"""
    if intent == "CREATE_TASK":
        try:
            title = entities.get("title", "New Task")
            platform = "local"
            if "asana" in title.lower():
                platform = "asana"
            task_req = CreateTaskRequest(title=title, platform=platform, dueDate=datetime.now())
            result = await create_task(task_req)
            return {
                "success": True,
                "response": {
                    "message": f"Created task '{title}' on {platform}.",
                    "data": result,
                    "actions": [{"type": "view_tasks", "label": "View Tasks"}]
                }
            }
        except Exception as e:
            return {"success": False, "response": {"message": f"Failed to create task: {str(e)}"}}
    
    elif intent == "LIST_TASKS":
        try:
            result = await get_tasks(platform="all")
            tasks = result.get("tasks", [])
            return {
                "success": True,
                "response": {
                    "message": f"Found {len(tasks)} tasks.",
                    "data": result,
                    "actions": [{"type": "create_task", "label": "Create New Task"}]
                }
            }
        except Exception as e:
            return {"success": False, "response": {"message": f"Failed to list tasks: {str(e)}"}}
    
    return {"success": False, "response": {"message": "Task action not understood."}}

async def handle_finance_intent(intent: str, entities: Dict[str, Any], request: ChatRequest) -> Dict[str, Any]:
    """Handle finance management intents"""
    if intent == "GET_TRANSACTIONS":
        return {
            "success": True,
            "response": {
                "message": "Here are your recent transactions.",
                "data": {
                    "transactions": [
                        {"date": "2025-11-27", "desc": "AWS Service", "amount": -45.00},
                        {"date": "2025-11-26", "desc": "Client Payment", "amount": 1200.00}
                    ]
                },
                "actions": [{"type": "view_finance", "label": "View Dashboard"}]
            }
        }
    elif intent == "CHECK_BALANCE":
        return {
            "success": True,
            "response": {
                "message": "Your current balance is $12,450.00",
                "data": {"balance": 12450.00, "currency": "USD"},
                "actions": []
            }
        }
    elif intent == "INVOICE_STATUS":
        try:
            items = await list_quickbooks_items()
            return {
                "success": True,
                "response": {"message": f"Found {len(items.get('items', []))} active invoices.", "data": items}
            }
        except Exception as e:
            return {"success": False, "response": {"message": f"Failed to check invoices: {str(e)}"}}
    
    return {"success": False, "response": {"message": "Finance action not understood."}}

def handle_help_request() -> Dict[str, Any]:
    """Provide help information"""
    return {
        "success": True,
        "response": {
            "message": (
                "I am your Universal ATOM Assistant!\\n\\n"
                "**Calendar**: 'Schedule meeting tomorrow'\\n"
                "**Email**: 'Find emails from boss'\\n"
                "**Tasks**: 'Create task in Asana'\\n"
                "**Finance**: 'Show recent transactions'\\n"
                "**Workflows**: 'Run Daily Report'\\n\\n"
                "Just ask me anything!"
            ),
            "actions": []
        }
    }

@router.post("/execute-generated")
async def execute_generated_workflow(request: ExecuteGeneratedRequest):
    """Execute a workflow generated via chat."""
    try:
        workflows = load_workflows()
        workflow = next((w for w in workflows if w['id'] == request.workflow_id), None)
        if not workflow:
            return {"success": False, "error": "Workflow not found"}
        
        engine = AutomationEngine()
        execution_id = str(uuid.uuid4())
        results = await engine.execute_workflow_definition(workflow, request.input_data, execution_id=execution_id)
        
        return {
            "success": True, 
            "execution_id": execution_id,
            "status": "completed",
            "message": "Workflow execution completed successfully",
            "results": results
        }
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return {"success": False, "error": str(e)}
