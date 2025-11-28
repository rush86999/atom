from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
import logging
import json

# Import workflow management components
from core.workflow_endpoints import load_workflows, save_workflows
from ai.automation_engine import AutomationEngine
from ai.workflow_scheduler import workflow_scheduler

# Import Calendar and Email services
from integrations.google_calendar_service import GoogleCalendarService
from integrations.gmail_service import GmailService

# Import Task and Finance services
from core.unified_task_endpoints import get_tasks, create_task, CreateTaskRequest
from integrations.quickbooks_routes import list_quickbooks_items

# Import System and Search services
from core.system_status import SystemStatus
from core.unified_search_endpoints import hybrid_search as unified_hybrid_search
from core.unified_search_endpoints import SearchRequest

# Import AI service for intent classification
from enhanced_ai_workflow_endpoints import RealAIWorkflowService
from advanced_workflow_orchestrator import orchestrator
from dataclasses import asdict

# Import chat history management
from core.lancedb_handler import get_chat_history_manager
from core.chat_session_manager import get_chat_session_manager
from core.chat_context_manager import get_chat_context_manager

# Initialize AI service
ai_service = RealAIWorkflowService()

# Initialize chat history components
chat_history = get_chat_history_manager()
session_manager = get_chat_session_manager()
context_manager = get_chat_context_manager()

router = APIRouter(prefix="/api/atom-agent", tags=["atom_agent"])

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None  # Now optional, will create if not provided
    conversation_history: List[ChatMessage] = []  # Deprecated, loaded from storage

class ExecuteGeneratedRequest(BaseModel):
    workflow_id: str
    input_data: Dict[str, Any]

def save_chat_interaction(
    session_id: str,
    user_id: str,
    user_message: str,
    assistant_message: str,
    intent: str = None,
    entities: Dict[str, Any] = None,
    result_data: Dict[str, Any] = None
):
    """Helper to save both user and assistant messages"""
    logger.info(f"save_chat_interaction called: session_id={session_id}, intent={intent}")
    try:
        # Save user message
        chat_history.save_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=user_message,
            metadata={"intent": intent, "entities": entities} if intent else {}
        )
        
        # Extract output entities from result_data
        output_metadata = {"intent": intent}
        if result_data and "response" in result_data:
            response_data = result_data["response"]
            # Extract common IDs if present
            if "workflow_id" in response_data:
                output_metadata["workflow_id"] = response_data["workflow_id"]
                output_metadata["workflow_name"] = response_data.get("workflow_name")
            if "task_id" in response_data:
                output_metadata["task_id"] = response_data["task_id"]
            if "schedule_id" in response_data:
                output_metadata["schedule_id"] = response_data["schedule_id"]
        
        # Save assistant response
        chat_history.save_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=assistant_message,
            metadata=output_metadata
        )
        
        # Update session activity
        session_manager.update_session_activity(session_id)
    except Exception as e:
        logger.error(f"Failed to save chat interaction: {e}")

@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Handle chat messages from the Universal ATOM Assistant.
    Uses LLM to interpret intent and interact with platform features.
    """
    try:
        # Session management: create or load session
        if not request.session_id:
            # Create new session
            session_id = session_manager.create_session(request.user_id)
        else:
            session_id = request.session_id
            # Verify session exists
            session = session_manager.get_session(session_id)
            if not session:
               # Session doesn't exist, create new one
                session_id = session_manager.create_session(request.user_id)
        
        # Load conversation history from LanceDB (replaces passed history)
        stored_history = chat_history.get_session_history(session_id, limit=20)
        conversation_history = [
            ChatMessage(role=msg["role"], content=msg["text"])
            for msg in stored_history
        ]
        
        # Initialize AI sessions if needed
        await ai_service.initialize_sessions()
        
        # Use LLM to classify intent
        intent_response = await classify_intent_with_llm(
            request.message, 
            conversation_history
        )
        
        intent = intent_response.get("intent")
        entities = intent_response.get("entities", {})
        
        # Context Resolution: Check for references if entities are missing or contain pronouns
        # We check if the message contains common reference words
        lower_msg = request.message.lower()
        has_reference = any(word in lower_msg for word in ["that", "this", "it", "the workflow", "the task"])
        
        if has_reference:
            # Try to resolve workflow reference
            if intent in ["SCHEDULE_WORKFLOW", "RUN_WORKFLOW", "CANCEL_SCHEDULE"] or (intent == "UNKNOWN" and "workflow" in lower_msg):
                # Check if we have a specific name/ID, or if the extracted ref is just a placeholder
                current_ref = entities.get("workflow_ref") or entities.get("workflow_name")
                is_placeholder = not current_ref or any(w in str(current_ref).lower() for w in ["that", "this", "it", "the workflow"])
                
                logger.info(f"Context check: ref='{current_ref}', is_placeholder={is_placeholder}")
                
                if is_placeholder:
                    logger.info("Attempting to resolve reference...")
                    resolved = await context_manager.resolve_reference(request.message, session_id, "workflow")
                    if resolved:
                        logger.info(f"Resolved workflow reference: {resolved}")
                        # If we found a workflow ID, inject it
                        if resolved.get("id"):
                            entities["workflow_id"] = resolved["id"]
                            # Also set name if available to help handlers that look for name
                            if resolved.get("name"):
                                entities["workflow_name"] = resolved["name"]
                                # CRITICAL: Update workflow_ref so handlers use the resolved name/ID
                                entities["workflow_ref"] = resolved["id"]
                                
            # Try to resolve task reference
            elif intent in ["COMPLETE_TASK", "DELETE_TASK"]:
                current_ref = entities.get("task_id") or entities.get("task_ref")
                is_placeholder = not current_ref or any(w in str(current_ref).lower() for w in ["that", "this", "it", "the task"])
                
                if is_placeholder:
                    resolved = await context_manager.resolve_reference(request.message, session_id, "task")
                    if resolved and resolved.get("id"):
                         entities["task_id"] = resolved["id"]
        
        logger.info(f"Classified intent: {intent}, entities: {entities}")
        
        # Route to appropriate handler based on intent
        if intent == "LIST_WORKFLOWS":
            result = await handle_list_workflows(request)
        elif intent == "RUN_WORKFLOW":
            result = await handle_run_workflow(request, entities)
        elif intent == "SCHEDULE_WORKFLOW":
            result = await handle_schedule_workflow(request, entities)
        elif intent == "GET_HISTORY":
            result = await handle_get_history(request, entities)
        elif intent == "CANCEL_SCHEDULE":
            result = await handle_cancel_schedule(request, entities)
        elif intent == "GET_STATUS":
            result = await handle_get_status(request, entities)
            
        # Calendar Intents
        elif intent == "CREATE_EVENT":
            result = await handle_create_event(request, entities)
        elif intent == "LIST_EVENTS":
            result = await handle_list_events(request, entities)
            
        # Email Intents
        elif intent == "SEND_EMAIL":
            result = await handle_send_email(request, entities)
        elif intent == "SEARCH_EMAILS":
            result = await handle_search_emails(request, entities)
            
        # Task Intents
        elif intent in ["CREATE_TASK", "LIST_TASKS"]:
            result = await handle_task_intent(intent, entities, request)
            
        # Finance Intents
        elif intent in ["GET_TRANSACTIONS", "CHECK_BALANCE", "INVOICE_STATUS"]:
            result = await handle_finance_intent(intent, entities, request)
            
            
        # System Intents (Phase 25C)
        elif intent == "GET_SYSTEM_STATUS":
            result = await handle_system_status(request)
            
        # Search Intents (Phase 25C)
        elif intent == "SEARCH_PLATFORM":
            result = await handle_platform_search(request, entities)
            
        # Workflow Creation (Phase 26)
        elif intent == "CREATE_WORKFLOW":
            result = await handle_create_workflow(request, entities)

            
        elif intent == "HELP":
            result = handle_help_request()
        
        else:
            # Default: Offer suggestions
            result = {
                "success": True,
                "response": {
                    "message": "I can help you with Workflows, Calendar, Email, Tasks, and Finance. Try asking me something!",
                    "actions": []
                }
            }
        
        # Save chat interaction
        if result and result.get("success"):
            assistant_msg = result.get("response", {}).get("message", "")
            save_chat_interaction(
                session_id=session_id,
                user_id=request.user_id,
                user_message=request.message,
                assistant_message=assistant_msg,
                intent=intent,
                entities=entities,
                result_data=result
            )
        
        # Add session_id to response
        if result:
            result["session_id"] = session_id
        
        return result

    except Exception as e:
        logger.error(f"Error in chat agent: {str(e)}")
        return {"success": False, "error": str(e)}

async def classify_intent_with_llm(message: str, history: List[ChatMessage]) -> Dict[str, Any]:
    """Use LLM to classify user intent via BYOK system"""
    
    system_prompt = """You are ATOM, an intelligent personal assistant for task orchestration and management.
    Classify the user's intent into one of these categories:
    
    **Workflows:**
    - CREATE_WORKFLOW: User wants to create a new workflow
    - LIST_WORKFLOWS: User wants to see existing workflows
    - RUN_WORKFLOW: User wants to execute a workflow now
    - SCHEDULE_WORKFLOW: User wants to schedule when a workflow runs
    - GET_HISTORY: User wants to see workflow execution history
    - CANCEL_SCHEDULE: User wants to stop a scheduled workflow
    
    **Calendar:** CREATE_EVENT, LIST_EVENTS
    **Email:** SEND_EMAIL, SEARCH_EMAILS
    **Tasks:** CREATE_TASK, LIST_TASKS
   **Finance:** GET_TRANSACTIONS, CHECK_BALANCE, INVOICE_STATUS
    **System:** GET_SYSTEM_STATUS
    **Search:** SEARCH_PLATFORM
    **General:** HELP, UNKNOWN
    
    **For SCHEDULE_WORKFLOW, extract:**
    - workflow_ref: Name or ID of workflow to schedule (e.g., "daily report", "backup workflow")
    - time_expression: The natural language schedule (e.g., "every weekday at 9am", "daily at 5pm", "every Monday")
    
    **Scheduling Patterns Recognition:**
    - Time-based: "daily", "every day", "at 9am", "5pm"
    - Day-based: "Monday", "weekday", "weekend", "every Tuesday"
    - Interval: "every 2 hours", "every 30 minutes"
    - Complex: "every weekday at 9am", "first Monday of month"
    
    **Examples:**
    Input: "Schedule the daily report to run every weekday at 9am"
    Output: {"intent": "SCHEDULE_WORKFLOW", "entities": {"workflow_ref": "daily report", "time_expression": "every weekday at 9am"}}
    
    Input: "Run backup workflow every 2 hours"
    Output: {"intent": "SCHEDULE_WORKFLOW", "entities": {"workflow_ref": "backup workflow", "time_expression": "every 2 hours"}}
    
    **CRITICAL:** If the user says "Schedule..." or "Set a schedule for...", the intent is ALWAYS SCHEDULE_WORKFLOW, never CREATE_WORKFLOW.
    
    Respond ONLY with valid JSON: {"intent": "INTENT_NAME", "entities": {...}}
    """
    
    try:
        # Use BYOK system to get optimal provider for chat tasks
        from core.byok_endpoints import get_byok_manager
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
    if "schedule" in msg and ("workflow" in msg or "run" in msg):
        # Try to extract time expression using patterns
        try:
            from core.time_expression_parser import parse_with_patterns
            time_info = parse_with_patterns(msg)
            
            workflow_ref = msg.replace("schedule", "").replace("workflow", "").strip()
            time_expression = msg
            
            if time_info and "matched_text" in time_info:
                # Remove the time expression from the message to get the workflow ref
                workflow_ref = msg.replace(time_info["matched_text"], "")
                workflow_ref = workflow_ref.replace("schedule", "").replace("to run", "")
                # Remove leading "the" and "workflow" if it appears as a standalone word at start
                import re
                workflow_ref = re.sub(r'^\s*the\s+', '', workflow_ref.strip())
                workflow_ref = re.sub(r'^\s*workflow\s+', '', workflow_ref)
                
                # Clean up multiple spaces
                workflow_ref = " ".join(workflow_ref.split())
                time_expression = time_info["matched_text"]
        except ImportError:
            workflow_ref = msg.replace("schedule", "").replace("workflow", "").strip()
            time_expression = msg
            
        return {"intent": "SCHEDULE_WORKFLOW", "entities": {"workflow_ref": workflow_ref, "time_expression": time_expression}}
    elif "create" in msg and "workflow" in msg:
        return {"intent": "CREATE_WORKFLOW", "entities": {"description": msg}}
    elif "list" in msg and "workflow" in msg:
        return {"intent": "LIST_WORKFLOWS", "entities": {}}
    elif "run" in msg and "workflow" in msg:
        return {"intent": "RUN_WORKFLOW", "entities": {"workflow_ref": msg.replace("run workflow", "").strip()}}
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
        
    # System Intents
    elif "system" in msg and ("status" in msg or "health" in msg or "performance" in msg):
        return {"intent": "GET_SYSTEM_STATUS", "entities": {}}
        
    # Search Intents
    elif "search" in msg or "find" in msg:
        # Extract search query
        query = msg.replace("search", "").replace("find", "").strip()
        return {"intent": "SEARCH_PLATFORM", "entities": {"query": query}}
        
    # Default to unknown
    return {"intent": "UNKNOWN", "entities": {}}


# --- Workflow Handlers ---

async def handle_create_workflow(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new workflow from natural language description"""
    description = entities.get("description", request.message)
    
    try:
        # Use the orchestrator to generate the workflow definition
        workflow_obj = await orchestrator.generate_dynamic_workflow(description)
        
        if not workflow_obj:
            return {
                "success": False, 
                "response": {
                    "message": "I couldn't understand how to create that workflow. Could you be more specific?", 
                    "actions": []
                }
            }
            
        # Convert dataclass to dict for storage (handle enums)
        from enum import Enum
        workflow_def = asdict(workflow_obj, dict_factory=lambda x: {
            k: v.value if isinstance(v, Enum) else v for k, v in x
        })
        
        # Save the generated workflow
        workflows = load_workflows()
        workflows.append(workflow_def)
        save_workflows(workflows)
        
        return {
            "success": True,
            "response": {
                "message": f"✅ I've created a workflow: **{workflow_def['name']}**\n\nIt includes {len(workflow_def.get('steps', []))} steps to achieve your goal.",
                "workflow_id": workflow_def['workflow_id'],
                "workflow_name": workflow_def['name'],
                "steps_count": len(workflow_def.get('steps', [])),
                "actions": [
                    {"type": "execute", "label": "Run Now", "workflowId": workflow_def['workflow_id']},
                    {"type": "edit", "label": "Edit Workflow", "workflowId": workflow_def['workflow_id']},
                    {"type": "schedule", "label": "Schedule", "workflowId": workflow_def['workflow_id']}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Workflow creation failed: {e}")
        return {
            "success": False, 
            "response": {
                "message": f"Failed to create workflow: {str(e)}", 
                "actions": []
            }
        }

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
            "actions": [{"type": "run", "label": f"Run {wf['name']}", "workflowId": wf['workflow_id']} for wf in workflows[:3]]
        }
    }

async def handle_run_workflow(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a specified workflow"""
    workflow_ref = entities.get("workflow_ref", "")
    if not workflow_ref:
        return {"success": False, "response": {"message": "Please specify which workflow to run.", "actions": []}}
    
    workflows = load_workflows()
    workflow = next((w for w in workflows if workflow_ref.lower() in w['name'].lower() or workflow_ref in w['workflow_id']), None)
    
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
    """Schedule a workflow using natural language time expression"""
    workflow_ref = entities.get("workflow_ref") or entities.get("workflow_name")
    time_expression = entities.get("time_expression") or entities.get("schedule")
    
    if not workflow_ref or not time_expression:
        return {
            "success": False,
            "response": {
                "message": "Please specify which workflow to schedule and when (e.g., 'Schedule daily report every weekday at 9am')",
                "actions": []
            }
        }
    
    # Find the workflow
    workflows = load_workflows()
    workflow = next((w for w in workflows if workflow_ref.lower() in w['name'].lower() or workflow_ref in w['workflow_id']), None)
    
    if not workflow:
        return {
            "success": False,
            "response": {
                "message": f"Workflow '{workflow_ref}' not found.",
                "actions": []
            }
        }
    
    # Parse the time expression
    from core.time_expression_parser import parse_time_expression
    schedule_info = await parse_time_expression(time_expression, ai_service)
    
    if not schedule_info:
        return {
            "success": False,
            "response": {
                "message": f"I couldn't understand the schedule '{time_expression}'. Try phrases like 'daily at 9am' or 'every Monday'.",
                "actions": []
            }
        }
    
    # Register with scheduler
    job_id = f"{workflow['workflow_id']}_{uuid.uuid4().hex[:8]}"
    
    try:
        if schedule_info["schedule_type"] == "cron":
            workflow_scheduler.schedule_workflow_cron(
                job_id=job_id,
                workflow_id=workflow['workflow_id'],
                cron_expression=schedule_info["cron_expression"]
            )
        elif schedule_info["schedule_type"] == "interval":
            workflow_scheduler.schedule_workflow_interval(
                job_id=job_id,
                workflow_id=workflow['workflow_id'],
                interval_minutes=schedule_info["interval_minutes"]
            )
        elif schedule_info["schedule_type"] == "date":
            workflow_scheduler.schedule_workflow_once(
                job_id=job_id,
                workflow_id=workflow['workflow_id'],
                run_date=schedule_info["run_date"]
            )
            
        return {
            "success": True,
            "response": {
                "message": f"✅ Scheduled '{workflow['name']}' to run {schedule_info['human_readable']}",
                "schedule_id": job_id,
                "workflow_id": workflow['workflow_id'],
                "schedule": schedule_info['human_readable'],
                "actions": [
                    {"type": "view_schedules", "label": "View All Schedules"},
                    {"type": "cancel_schedule", "label": "Cancel This Schedule", "scheduleId": job_id}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        return {
            "success": False,
            "response": {
                "message": f"Failed to schedule workflow: {str(e)}",
                "actions": []
            }
        }

async def handle_get_history(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    workflow_ref = entities.get("workflow_ref", "")
    if not workflow_ref:
        return {"success": False, "response": {"message": "Please specify the workflow.", "actions": []}}
    return {"success": True, "response": {"message": f"History for {workflow_ref} is available in the Editor.", "actions": []}}

async def handle_cancel_schedule(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel a scheduled workflow"""
    schedule_id = entities.get("schedule_id")
    workflow_ref = entities.get("workflow_ref")
    
    if schedule_id:
        success = workflow_scheduler.remove_job(schedule_id)
        if success:
            return {"success": True, "response": {"message": f"✅ Schedule {schedule_id} cancelled.", "actions": []}}
        else:
            return {"success": False, "response": {"message": f"Could not find schedule {schedule_id}.", "actions": []}}
            
    if workflow_ref:
        # This is harder because we need to find jobs for the workflow
        # For now, simpler to ask user to check the list
        return {"success": True, "response": {"message": "Please go to the Schedule tab to manage specific schedules.", "actions": []}}
        
    return {"success": False, "response": {"message": "Please specify which schedule to cancel.", "actions": []}}

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
                "**System**: 'Show system status'\\n"
                "**Search**: 'Search for project documents'\\n"
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

# --- System & Search Handlers (Phase 25C) ---

async def handle_system_status(request: ChatRequest) -> Dict[str, Any]:
    """Handle system status request"""
    try:
        # Get comprehensive system status
        overall_status = SystemStatus.get_overall_status()
        system_info = SystemStatus.get_system_info()
        resource_usage = SystemStatus.get_resource_usage()
        service_status = SystemStatus.get_service_status()
        
        # Count healthy services
        healthy_services = sum(1 for s in service_status.values() if s.get("status") in ["healthy", "operational"])
        total_services = len(service_status)
        
        message = f"**System Status: {overall_status.upper()}**\n\n"
        message += f"Services: {healthy_services}/{total_services} healthy\n"
        message += f"CPU: {resource_usage.get('cpu', {}).get('percent', 0):.1f}%\n"
        message += f"Memory: {resource_usage.get('memory', {}).get('percent', 0):.1f}%\n"
        message += f"Platform: {system_info.get('platform', {}).get('system', 'Unknown')}"
        
        return {
            "success": True,
            "response": {
                "message": message,
                "data": {
                    "overall_status": overall_status,
                    "services": service_status,
                    "resources": resource_usage
                },
                "actions": []
            }
        }
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        return {
            "success": False,
            "response": {
                "message": f"Failed to get system status: {str(e)}",
                "actions": []
            }
        }

async def handle_platform_search(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle platform-wide search request"""
    try:
        query = entities.get("query", request.message)
        
        # Create search request
        search_req = SearchRequest(
            query=query,
            user_id=request.user_id,
            limit=10,
            search_type="hybrid"
        )
        
        # Perform search
        search_response = await unified_hybrid_search(search_req)
        
        if search_response.success and search_response.results:
            message = f"Found {len(search_response.results)} results for '{query}':\n\n"
            for i, result in enumerate(search_response.results[:5], 1):
                doc_type = result.metadata.get("type", "document") if result.metadata else "document"
                snippet = result.text[:100] + "..." if len(result.text) > 100 else result.text
                message += f"{i}. [{doc_type.title()}] {snippet}\n"
            
            if len(search_response.results) > 5:
                message += f"\n...and {len(search_response.results) - 5} more results."
            
            return {
                "success": True,
                "response": {
                    "message": message,
                    "data": {
                        "results": [r.dict() for r in search_response.results],
                        "total_count": search_response.total_count
                    },
                    "actions": []
                }
            }
        else:
            return {
                "success": True,
                "response": {
                    "message": f"No results found for '{query}'.",
                    "actions": []
                }
            }
            
    except Exception as e:
        logger.error(f"Platform search failed: {e}")
        return {
            "success": False,
            "response": {
                "message": f"Search failed: {str(e)}",
                "actions": []
            }
        }
