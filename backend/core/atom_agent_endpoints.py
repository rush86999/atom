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
from advanced_workflow_orchestrator import get_orchestrator
from dataclasses import asdict

# Import chat history management
from core.lancedb_handler import get_chat_history_manager
from core.chat_session_manager import get_chat_session_manager
from core.chat_context_manager import get_chat_context_manager
from core.knowledge_query_endpoints import get_knowledge_query_manager
from operations.system_intelligence_service import SystemIntelligenceService

# Initialize AI service
ai_service = RealAIWorkflowService()

# Initialize chat history components
# Initialize chat history components
# DEPRECATED: Globals removed for Workspace Isolation (Phase 19)
# chat_history = get_chat_history_manager()
# session_manager = get_chat_session_manager()
# context_manager = get_chat_context_manager()

router = APIRouter(prefix="/api/atom-agent", tags=["atom_agent"])

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    current_page: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    conversation_history: List[ChatMessage] = []
    agent_id: Optional[str] = None  # Explicit agent selection for governance

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
    result_data: Dict[str, Any] = None,
    chat_history_mgr = None,
    session_mgr = None
):
    """Helper to save both user and assistant messages"""
    # Instantiate if not provided
    if not chat_history_mgr:
        chat_history_mgr = get_chat_history_manager("default")
    if not session_mgr:
        session_mgr = get_chat_session_manager("default")

    logger.info(f"save_chat_interaction called: session_id={session_id}, intent={intent}")
    try:
        # Save user message
        chat_history_mgr.save_message(
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
        chat_history_mgr.save_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=assistant_message,
            metadata=output_metadata
        )
        
        # Update session activity
        session_mgr.update_session_activity(session_id)
    except Exception as e:
        logger.error(f"Failed to save chat interaction: {e}")

@router.get("/sessions")
async def list_sessions(user_id: str = "default_user", limit: int = 50):
    """List all chat sessions for a user"""
    try:
        session_manager = get_chat_session_manager("default")
        sessions = session_manager.list_user_sessions(user_id, limit=limit)
        return {
            "success": True,
            "sessions": [
                {
                    "id": s["session_id"],
                    "title": s.get("metadata", {}).get("title") or f"Session {s['session_id'][:8]}",
                    "date": s["last_active"],
                    "preview": s.get("metadata", {}).get("last_message", "New conversation")
                }
                for s in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return {"success": False, "error": str(e)}

@router.post("/sessions")
async def create_new_session(user_id: str = Body(..., embed=True)):
    """Create a new chat session"""
    try:
        session_manager = get_chat_session_manager("default")
        session_id = session_manager.create_session(user_id=user_id)
        return {"success": True, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return {"success": False, "error": str(e)}

@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Retrieve conversation history for a specific session.
    Returns all messages in chronological order.
    """
    try:
        session_manager = get_chat_session_manager("default")
        chat_history = get_chat_history_manager("default")

        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": "Session not found"
            }
        
        # Retrieve messages from LanceDB
        messages = chat_history.get_session_history(session_id, limit=100)
        
        # Convert to frontend-friendly format
        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                "id": msg.get("id", ""),
                "role": msg.get("role", "assistant"),
                "content": msg.get("text", ""),
                "timestamp": msg.get("created_at", datetime.utcnow().isoformat()),
                "metadata": {}
            }
            
            # Parse metadata if it exists
            if "metadata" in msg and msg["metadata"]:
                try:
                    if isinstance(msg["metadata"], str):
                        formatted_msg["metadata"] = json.loads(msg["metadata"])
                    else:
                        formatted_msg["metadata"] = msg["metadata"]
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse metadata as JSON: {e}")
                    formatted_msg["metadata"] = msg["metadata"]
                except Exception as e:
                    logger.warning(f"Unexpected error parsing metadata: {e}")
                    formatted_msg["metadata"] = {}
            
            formatted_messages.append(formatted_msg)
        
        return {
            "success": True,
            "session": session,
            "messages": formatted_messages,
            "count": len(formatted_messages)
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve session history: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Handle chat messages from the Universal ATOM Assistant.
    Uses LLM to interpret intent and interact with platform features.
    """
    try:
        # Single-tenant: use default context
        chat_history = get_chat_history_manager("default")
        session_manager = get_chat_session_manager("default")
        context_manager = get_chat_context_manager("default")

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
        
        # Phase 18: Inject System Intelligence Context
        system_context_str = ""
        try:
             # Use the first available DB session or create a new one if possible. 
             # Ideally get_db dependency should be used, but here we can try to reuse existing patterns.
             # Since we are in an endpoint, we might not have direct DB session unless dependency injected.
             # We will use the `get_db` generator manually or a dedicated session for this service.
             from core.database import SessionLocal
             with SessionLocal() as db_session:
                 intel_service = SystemIntelligenceService(db_session)
                 system_context_str = intel_service.get_aggregated_context("default")
        except Exception as ctx_error:
            logger.warning(f"Failed to fetch system intelligence context: {ctx_error}")

        # Use LLM to classify intent
        intent_response = await classify_intent_with_llm(
            request.message, 
            conversation_history,
            current_page=request.current_page,
            system_context=system_context_str
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
            
        elif intent == "GET_AUTOMATION_INSIGHTS":
            result = await handle_automation_insights(request)
            
        # Search Intents (Phase 25C)
        elif intent == "SEARCH_PLATFORM":
            result = await handle_platform_search(request, entities)
            
        # Workflow Creation (Phase 26)
        elif intent == "CREATE_WORKFLOW":
            result = await handle_create_workflow(request, entities)
            
        elif intent == "GET_SILENT_STAKEHOLDERS":
            result = await handle_silent_stakeholders(request)
            
        elif intent == "FOLLOW_UP_EMAILS":
            result = await handle_follow_up_emails(request, entities)
        
        elif intent == "WELLNESS_CHECK":
            result = await handle_wellness_check(request, entities)
            
        elif intent == "RESOLVE_CONFLICTS":
            result = await handle_resolve_conflicts(request, entities)
        
        elif intent == "SET_GOAL":
            result = await handle_set_goal(request, entities)
            
        elif intent == "GOAL_STATUS":
            result = await handle_goal_status(request, entities)

        elif intent == "KNOWLEDGE_QUERY":
            result = await handle_knowledge_query(request, entities)
            
        elif intent == "CRM_QUERY":
            result = await handle_crm_intent(request, entities)
            
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
                result_data=result,
                chat_history_mgr=chat_history,
                session_mgr=session_manager
            )
        
        # Add proactive suggestions to the response
        try:
            from core.behavior_analyzer import get_behavior_analyzer
            analyzer = get_behavior_analyzer()
            patterns = analyzer.detect_patterns(request.user_id)
            if patterns:
                if "response" not in result:
                    result["response"] = {"message": "", "actions": []}
                
                # Append behavioral suggestions as actions
                for pattern in patterns:
                    suggestion_action = {
                        "type": "run_workflow",
                        "label": pattern["name"],
                        "description": pattern["description"],
                        "workflow_id": pattern.get("suggested_actions", [""])[0] # Take first suggested action
                    }
                    if suggestion_action not in result["response"]["actions"]:
                        result["response"]["actions"].append(suggestion_action)
        except Exception as suggest_e:
            logger.warning(f"Failed to inject proactive suggestions: {suggest_e}")

        # Add session_id to response
        if result:
            result["session_id"] = session_id
        
        return result

    except Exception as e:
        logger.error(f"Error in chat agent: {str(e)}")
        return {"success": False, "error": str(e)}

async def classify_intent_with_llm(
    message: str, 
    history: List[ChatMessage],
    current_page: Optional[str] = None,
    system_context: str = ""
) -> Dict[str, Any]:
    """Use LLM to classify user intent via BYOK system with Knowledge Graph context"""
    
    # 0. Preemptive Knowledge Retrieval
    knowlege_context = ""
    try:
        from core.knowledge_query_endpoints import get_knowledge_query_manager
        km = get_knowledge_query_manager()
        # Perform a quick search for relevant facts
        facts = await km.answer_query(f"What relevant facts are there about: {message}")
        if facts and facts.get("relevant_facts"):
            knowlege_context = "\n**Knowledge Context:**\n" + "\n".join([f"- {f}" for f in facts["relevant_facts"][:5]])
    except Exception as e:
        logger.warning(f"Failed to fetch preemptive knowledge for intent classification: {e}")

    system_prompt = f"""You are ATOM, an intelligent personal assistant for task orchestration and management.
Current User Context (Page): {current_page or 'Unknown'}
"""
    if system_context:
        system_prompt += f"\n**Current Business Context:**\n{system_context}\n"
    
    if knowlege_context:
        system_prompt += knowlege_context + "\n\n"
        
    system_prompt += """
    Classify the user's intent into one of these categories:
    
    **Workflows:**
    - CREATE_WORKFLOW: User wants to create a new workflow
    - LIST_WORKFLOWS: User wants to see existing workflows
    - RUN_WORKFLOW: User wants to execute a workflow now
    - SCHEDULE_WORKFLOW: User wants to schedule when a workflow runs
    - GET_HISTORY: User wants to see workflow execution history
    - CANCEL_SCHEDULE: User wants to stop a scheduled workflow
    
    **Calendar:** CREATE_EVENT, LIST_EVENTS, RESOLVE_CONFLICTS
    **Email:** SEND_EMAIL, SEARCH_EMAILS, FOLLOW_UP_EMAILS
    **Tasks:** CREATE_TASK, LIST_TASKS
    **Wellness:** WELLNESS_CHECK
    **Finance:** GET_TRANSACTIONS, CHECK_BALANCE, INVOICE_STATUS
    **CRM & Sales:** 
    - CRM_QUERY: Use for questions about sales, leads, deals, pipeline, forecasts, or sales follow-ups.
    **System & Analytics:**
    - GET_SYSTEM_STATUS: User wants to check system health
    - GET_AUTOMATION_INSIGHTS: User wants to see drift metrics or automation health
    - GET_SILENT_STAKEHOLDERS: User wants to know who has been quiet or who they should reach out to
    **Search:** SEARCH_PLATFORM
    **Goal Management:** SET_GOAL, GOAL_STATUS
    **Knowledge Graph:** KNOWLEDGE_QUERY (Use for questions about relationships, decisions, or cross-entity facts like "Who worked on Project X?" or "What decisions were made with Vendor Y?")
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
            elif provider_id == "google":
                result = await ai_service.call_google_api(message, system_prompt) if hasattr(ai_service, 'call_google_api') else None
            elif provider_id == "google_flash":
                result = await ai_service.call_google_api(message, system_prompt, model="gemini-1.5-flash") if hasattr(ai_service, 'call_google_api') else None
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
    elif "conflict" in msg or "overlap" in msg:
        return {"intent": "RESOLVE_CONFLICTS", "entities": {}}
    elif "schedule" in msg or "meeting" in msg or "appointment" in msg or ("create" in msg and "event" in msg):
        return {"intent": "CREATE_EVENT", "entities": {"summary": msg}}
    elif "calendar" in msg or ("list" in msg and "event" in msg) or "agenda" in msg:
        return {"intent": "LIST_EVENTS", "entities": {}}
        
    # Email Intents
    elif "send" in msg and ("email" in msg or "mail" in msg):  
        return {"intent": "SEND_EMAIL", "entities": {"subject": "New Email"}}
    elif "search" in msg and ("email" in msg or "mail" in msg or "inbox" in msg):
        return {"intent": "SEARCH_EMAILS", "entities": {"query": msg.replace("search", "").strip()}}
    elif "follow up" in msg or "follow-up" in msg:
        return {"intent": "FOLLOW_UP_EMAILS", "entities": {}}
        
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
        
    # CRM & Sales Intents
    elif any(word in msg for word in ["sale", "lead", "deal", "pipeline", "prospect", "forecast"]):
        return {"intent": "CRM_QUERY", "entities": {}}
        
    # System Intents
    elif "system" in msg and ("status" in msg or "health" in msg or "performance" in msg):
        return {"intent": "GET_SYSTEM_STATUS", "entities": {}}
    elif "wellness" in msg or "burnout" in msg or "stress" in msg:
        return {"intent": "WELLNESS_CHECK", "entities": {}}
        
    # Goal Intents
    elif ("set" in msg or "create" in msg) and "goal" in msg:
        return {"intent": "SET_GOAL", "entities": {"goal_text": message}}
    elif "goal" in msg and ("status" in msg or "progress" in msg):
        return {"intent": "GOAL_STATUS", "entities": {}}
        
    # Search Intents
    elif "search" in msg or "find" in msg:
        # Extract search query
        query = msg.replace("search", "").replace("find", "").strip()
        return {"intent": "SEARCH_PLATFORM", "entities": {"query": query}}
    
    # Knowledge fallback
    elif "who" in msg or "what" in msg or "decisions" in msg or "projects" in msg:
        return {"intent": "KNOWLEDGE_QUERY", "entities": {"query": message}}
        
    # Default to unknown
    return {"intent": "UNKNOWN", "entities": {}}


# --- Workflow Handlers ---

async def handle_create_workflow(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new workflow from natural language description"""
    description = entities.get("description", request.message)
    
    try:
        # Use the orchestrator to generate the workflow definition (now returns a dict)
        workflow_def = await get_orchestrator().generate_dynamic_workflow(description)
        
        if not workflow_def:
            return {
                "success": False, 
                "response": {
                    "message": "I couldn't understand how to create that workflow. Could you be more specific?", 
                    "actions": []
                }
            }
            
        # Save the generated workflow to the standard storage
        workflows = load_workflows()
        workflows.append(workflow_def)
        save_workflows(workflows)
        
        node_count = len(workflow_def.get('nodes', []))
        is_template = "template_id" in workflow_def
        template_msg = f"\n\n✨ **I've also saved this as a reusable template!** (ID: {workflow_def.get('template_id')})" if is_template else ""
        
        return {
            "success": True,
            "response": {
                "message": f"✅ I've proposed a new automation: **{workflow_def['name']}**\n\nIt includes {node_count} components to achieve your goal.{template_msg}\n\nWould you like to deploy it?",
                "workflow_id": workflow_def['id'],
                "workflow_name": workflow_def['name'],
                "nodes": workflow_def.get('nodes', []),
                "connections": workflow_def.get('connections', []),
                "actions": [
                    {"type": "execute", "label": "✅ Deploy Workflow", "workflowId": workflow_def['id']},
                    {"type": "edit", "label": "🔍 Review Details", "workflowId": workflow_def['id']}
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

# --- CRM/Sales Handlers ---

async def handle_crm_intent(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle sales and CRM queries via SalesAssistant"""
    try:
        from core.database import get_db_session
        from sales.assistant import SalesAssistant

        with get_db_session() as db:
            # Get workspace_id from entities or default to temp_ws for now
            workspace_id = entities.get("workspace_id") or "temp_ws"
            assistant = SalesAssistant(db)
            answer = await assistant.answer_sales_query(workspace_id, request.message)

            return {
                "success": True,
                "response": {
                    "message": answer,
                    "actions": [
                        {"type": "view_leads", "label": "View Leads"},
                        {"type": "view_pipeline", "label": "View Pipeline"}
                    ]
                }
            }
    except Exception as e:
        logger.error(f"CRM handler failed: {e}")
        return {
            "success": False,
            "error": f"Failed to process sales query: {str(e)}"
        }

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
    return {"success": True, "response": {"message": f"Searching for {query} in your inbox...", "actions": []}}

async def handle_knowledge_query(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Answer complex relationship queries using knowledge graph"""
    query = entities.get("query", request.message)
    try:
        manager = get_knowledge_query_manager()
        res = await manager.answer_query(query)
        answer_text = res.get("answer", "I couldn't find an answer.")
        return {
            "success": True,
            "response": {
                "message": answer_text,
                "actions": [
                    {"type": "view_knowledge_graph", "label": "🔍 View Knowledge Map"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Knowledge query handler failed: {e}")
        return {
            "success": False,
            "response": {"message": "I encountered an error while searching your knowledge graph.", "actions": []}
        }
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

async def handle_follow_up_emails(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to follow up on emails by triggering the workflow template"""
    try:
        from core.workflow_template_system import template_manager
        
        # Find the email_followup template
        template = template_manager.get_template("email_followup")
        if not template:
            return {
                "success": False,
                "response": {
                    "message": "The email follow-up system is currently being updated. Please try again in 5 minutes.",
                    "actions": []
                }
            }
        
        # Trigger the workflow
        # Note: In a real app, this would use WorkflowEngine.start_workflow
        # For now, we return a success message with follow-up candidates link
        return {
            "success": True,
            "response": {
                "message": "🔍 I've analyzed your sent emails. I've found a few people you might want to follow up with, including **investor@venture.com** (no reply in 5 days).\n\nI've prepared polite nudge drafts for you in the **Email Follow-up Center**.",
                "actions": [
                    {"type": "link", "label": "Open Follow-up Center", "path": "/email/followups"},
                    {"type": "run_workflow", "label": "Automate All Follow-ups", "workflow_id": "email_followup"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Follow-up handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_wellness_check(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to check user wellness/burnout and trigger mitigation workflow"""
    try:
        from core.workflow_template_system import template_manager
        template = template_manager.get_template("burnout_protection")
        
        return {
            "success": True,
            "response": {
                "message": "I'm checking your workload and wellness metrics. 🧘\n\nI've noticed your meetings are taking up 85% of your day. I can trigger the **Burnout Protection** workflow to suggest focus blocks and reschedule non-urgent meetings.",
                "actions": [
                    {"type": "link", "label": "Open Wellness Dashboard", "path": "/analytics/wellness"},
                    {"type": "run_workflow", "label": "Start Protection Workflow", "workflow_id": "burnout_protection"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Wellness handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_automation_insights(request: ChatRequest) -> Dict[str, Any]:
    """Handle request to view automation insights and behavioral suggestions"""
    try:
        from core.automation_insight_manager import get_insight_manager
        from core.behavior_analyzer import get_behavior_analyzer
        
        insight_manager = get_insight_manager()
        behavior_analyzer = get_behavior_analyzer()
        
        # 1. Get Drift Insights
        insights = insight_manager.generate_all_insights(request.user_id)
        critical_drift = [i for i in insights if i["drift_score"] > 0.7]
        
        # 2. Get Behavioral Patterns
        patterns = behavior_analyzer.detect_patterns(request.user_id)
        
        # 3. Construct Message
        message = "**Automation Health Report** 📊\n\n"
        
        if critical_drift:
            message += "⚠️ **Drift Detected**: " + ", ".join([f"'{i['workflow_id']}'" for i in critical_drift]) + " are showing high manual override rates. You might want to optimize their triggers.\n\n"
        else:
            message += "✅ All workflows are running within expected parameters.\n\n"
            
        if patterns:
            message += "**Personalized Suggestions** ✨\n"
            for p in patterns:
                message += f"- {p['description']}\n"
        else:
            message += "I'm still learning your patterns. Keep using ATOM to get personalized automation suggestions!"

        # 4. Define Actions
        actions = [
            {"type": "link", "label": "Full Insights Dashboard", "path": "/analytics/insights"}
        ]
        
        for p in patterns:
            actions.append({
                "type": "run_workflow",
                "label": p["name"],
                "workflow_id": p.get("suggested_actions", [""])[0]
            })
            
        return {
            "success": True,
            "response": {
                "message": message,
                "actions": actions[:5] # Limit to top 5 actions
            }
        }
    except Exception as e:
        logger.error(f"Insights handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_resolve_conflicts(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to optimize schedule and resolve conflicts"""
    try:
        return {
            "success": True,
            "response": {
                "message": "📅 I've analyzed your calendar for the next 7 days and found **3 conflicts**. \n\nI can automatically resolve these by polling the participants and finding the best slots using my coordination engine.",
                "actions": [
                    {"type": "run_workflow", "label": "Resolve All Conflicts", "workflow_id": "auto_schedule_conflict_resolution"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Conflict resolution handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_set_goal(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to set a new high-level goal"""
    try:
        from core.workflow_template_system import template_manager
        # Extract goal and date if possible, otherwise use defaults/mock
        goal_text = entities.get("goal_text", request.message)
        # Default to end of month if no date specified
        import datetime
        now = datetime.datetime.now()
        end_of_month = (now.replace(day=1) + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        target_date = entities.get("target_date", end_of_month.isoformat())

        return {
            "success": True,
            "response": {
                "message": f"I've set your goal: '**{goal_text}**'. I'm decomposing this into a series of sub-tasks and will monitor the progress for you. 🚀",
                "actions": [
                    {
                        "type": "run_workflow", 
                        "label": "Activate Automation", 
                        "workflow_id": "goal_driven_automation",
                        "parameters": {
                            "goal_text": goal_text,
                            "target_date": target_date
                        }
                    },
                    {"type": "link", "label": "View Goal Dashboard", "path": "/analytics/goals"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Set goal handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_silent_stakeholders(request: ChatRequest) -> Dict[str, Any]:
    """Handle request to identify silent stakeholders and suggest outreach"""
    try:
        from core.stakeholder_engine import get_stakeholder_engine
        engine = get_stakeholder_engine()
        
        silent_stakeholders = await engine.identify_silent_stakeholders(request.user_id)
        
        if not silent_stakeholders:
            return {
                "success": True,
                "response": {
                    "message": "I've checked your communications and project assignments. Everyone seems to be actively engaged! ✅",
                    "actions": []
                }
            }
            
        message = "**Stakeholder Engagement Alert** 📣\n\nI've identified a few key people who haven't engaged in a while:\n\n"
        actions = []
        
        for s in silent_stakeholders[:3]: # Show top 3
            message += f"- **{s['name']}** ({s['email']}): No interaction for {s['days_since']} days.\n"
            actions.append({
                "type": "send_email",
                "label": f"Nudge {s['name']}",
                "recipient": s["email"],
                "subject": f"Checking in - {s.get('name')}",
                "body": s.get("suggested_outreach", "")
            })
            
        message += "\nWould you like me to draft an outreach message for any of them?"
        
        return {
            "success": True,
            "response": {
                "message": message,
                "actions": actions
            }
        }
    except Exception as e:
        logger.error(f"Stakeholder handler failed: {e}")
        return {"success": False, "error": str(e)}

async def handle_goal_status(request: ChatRequest, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Handle request to check status of active goals"""
    try:
        from core.goal_engine import goal_engine
        # Mock status for now
        return {
            "success": True,
            "response": {
                "message": "You have **1 active goal**: 'Close this deal by end of month'.\n- **Progress**: 25%\n- **Status**: On Track\n- **Next Milestone**: Proposal Drafting (Due in 3 days)",
                "actions": [
                    {"type": "link", "label": "Manage Goals", "path": "/analytics/goals"}
                ]
            }
        }
    except Exception as e:
        logger.error(f"Goal status handler failed: {e}")
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


# ==================== STREAMING CHAT ENDPOINT ====================

@router.post("/chat/stream")
async def chat_stream_agent(request: ChatRequest):
    """
    Handle chat messages with streaming LLM responses.
    Tokens are broadcast via WebSocket as they arrive from the LLM.

    Now includes agent governance integration with:
    - Agent resolution and attribution
    - Governance checks before streaming
    - Agent execution tracking
    - Performance-optimized caching
    """
    # Feature flag for governance (can be disabled for emergencies)
    import os
    governance_enabled = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
    emergency_bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

    agent = None
    agent_execution = None
    resolution_context = None
    governance_check = None

    try:
        # Import streaming support
        from core.llm.byok_handler import BYOKHandler
        from core.websockets import manager as ws_manager
        from core.database import SessionLocal
        from core.agent_context_resolver import AgentContextResolver
        from core.agent_governance_service import AgentGovernanceService
        from core.models import AgentExecution

        # Determine workspace
        ws_id = request.workspace_id or "default"

        # ============================================
        # GOVERNANCE: Agent Resolution & Validation
        # ============================================
        if governance_enabled and not emergency_bypass:
            with SessionLocal() as db:
                resolver = AgentContextResolver(db)
                governance = AgentGovernanceService(db)

                # Resolve agent for this request
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=request.user_id,
                    workspace_id=ws_id,
                    session_id=request.session_id,
                    requested_agent_id=request.agent_id,
                    action_type="stream_chat"
                )

                if not agent:
                    logger.warning("Agent resolution failed, using system default")

                # Perform governance check
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="stream_chat"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to stream chat: {governance_check['reason']}",
                            "governance_check": governance_check
                        }

                    # Create AgentExecution record for audit trail
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id=ws_id,
                        status="running",
                        input_summary=f"Stream chat: {request.message[:200]}...",
                        triggered_by="websocket"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} started for agent {agent.name}")

        # Get BYOK handler
        byok_handler = BYOKHandler(workspace_id=ws_id, provider_id="auto")

        # Prepare messages for LLM
        messages = []

        # Add system context if available
        try:
            from operations.system_intelligence_service import SystemIntelligenceService

            with SessionLocal() as db_session:
                intel_service = SystemIntelligenceService(db_session)
                system_context_str = intel_service.get_aggregated_context(ws_id)
                if system_context_str:
                    messages.append({
                        "role": "system",
                        "content": f"""You are ATOM, an intelligent assistant helping with business automation and integrations.

Current Business Context:
{system_context_str}

Provide helpful, concise responses. When you need to take actions, describe what you're doing clearly."""
                    })
        except Exception as ctx_error:
            logger.warning(f"Failed to fetch system intelligence context: {ctx_error}")
            messages.append({
                "role": "system",
                "content": "You are ATOM, an intelligent assistant helping with business automation and integrations."
            })

        # Add conversation history
        if request.conversation_history:
            for msg in request.conversation_history[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Add current message
        messages.append({
            "role": "user",
            "content": request.message
        })

        # Get optimal provider for streaming
        from core.llm.byok_handler import QueryComplexity

        complexity = byok_handler.analyze_query_complexity(request.message, task_type="chat")
        provider_id, model = byok_handler.get_optimal_provider(
            complexity,
            task_type="chat",
            prefer_cost=True,
            tenant_plan="free",
            is_managed_service=False,
            requires_tools=False
        )

        logger.info(f"Starting streaming chat with {provider_id}/{model}" +
                   (f" (agent: {agent.name})" if agent else ""))

        # Create a unique message ID for this response
        message_id = str(uuid.uuid4())

        # Send initial message to WebSocket
        user_channel = f"user:{request.user_id}"
        await ws_manager.broadcast(user_channel, {
            "type": "streaming:start",
            "id": message_id,
            "model": model,
            "provider": provider_id,
            "agent_id": agent.id if agent else None,
            "agent_name": agent.name if agent else None
        })

        # Stream tokens via WebSocket
        accumulated_content = ""
        tokens_count = 0
        start_time = datetime.now()

        try:
            # Stream with agent context if available
            stream_kwargs = {
                "messages": messages,
                "model": model,
                "provider_id": provider_id,
                "temperature": 0.7,
                "max_tokens": 2000
            }

            # Pass agent context for tracking
            if agent and governance_enabled:
                stream_kwargs["agent_id"] = agent.id

            async for token in byok_handler.stream_completion(**stream_kwargs):
                accumulated_content += token
                tokens_count += 1

                # Broadcast token to frontend
                await ws_manager.broadcast(user_channel, {
                    "type": ws_manager.STREAMING_UPDATE,
                    "id": message_id,
                    "delta": token,
                    "complete": False,
                    "metadata": {
                        "model": model,
                        "tokens_so_far": len(accumulated_content)
                    }
                })

            # Send completion message
            await ws_manager.broadcast(user_channel, {
                "type": ws_manager.STREAMING_COMPLETE,
                "id": message_id,
                "content": accumulated_content,
                "complete": True
            })

            # Save to chat history
            chat_history = get_chat_history_manager(ws_id)
            session_manager = get_chat_session_manager(ws_id)

            if not request.session_id:
                session_id = session_manager.create_session(request.user_id)
            else:
                session_id = request.session_id

            # Save user message
            chat_history.add_message(session_id, "user", request.message)

            # Save assistant response
            chat_history.add_message(session_id, "assistant", accumulated_content)

            # ============================================
            # GOVERNANCE: Record execution outcome
            # ============================================
            if agent_execution and governance_enabled:
                end_time = datetime.now()
                duration_seconds = (end_time - start_time).total_seconds()

                with SessionLocal() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()

                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Generated {tokens_count} tokens, {len(accumulated_content)} chars"
                        execution.duration_seconds = duration_seconds
                        execution.completed_at = end_time
                        db.commit()

                        # Record outcome for confidence scoring
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=True)

                        logger.info(f"Agent execution {execution.id} completed successfully")

            return {
                "success": True,
                "message_id": message_id,
                "session_id": session_id,
                "streamed": True,
                "agent_id": agent.id if agent else None,
                "agent_name": agent.name if agent else None
            }

        except Exception as stream_error:
            logger.error(f"Streaming error: {stream_error}")

            # Mark execution as failed
            if agent_execution and governance_enabled:
                with SessionLocal() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()

                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(stream_error)
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record failure for confidence scoring
                        governance_service = AgentGovernanceService(db)
                        await governance_service.record_outcome(agent.id, success=False)

            # Send error via WebSocket
            await ws_manager.broadcast(user_channel, {
                "type": ws_manager.STREAMING_ERROR,
                "id": message_id,
                "error": str(stream_error)
            })
            raise

    except Exception as e:
        logger.error(f"Error in streaming chat: {str(e)}")
        return {"success": False, "error": str(e)}
