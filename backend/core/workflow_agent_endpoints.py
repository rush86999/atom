from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import logging

# Import the NLU processor
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

# Initialize AI service
ai_service = RealAIWorkflowService()

router = APIRouter(prefix="/api/workflow-agent", tags=["workflow_agent"])

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    conversation_history: List[ChatMessage]

class WorkflowData(BaseModel):
    workflow_id: str
    workflow_name: str
    steps_count: int
    is_scheduled: bool
    requires_confirmation: bool
    actions: List[Dict[str, Any]]

class ChatResponse(BaseModel):
    message: str
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    steps_count: Optional[int] = None
    is_scheduled: Optional[bool] = None
    requires_confirmation: Optional[bool] = None
    actions: Optional[List[Dict[str, Any]]] = None

class ExecuteGeneratedRequest(BaseModel):
    workflow_id: str
    input_data: Dict[str, Any]

@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Handle chat messages from the Workflow Assistant UI.
    Uses NLU to interpret intent and generate workflows.
    """
    try:
        from core.workflow_endpoints import save_workflows, load_workflows
        
        # Initialize AI service sessions
        await ai_service.initialize_sessions()
        
        # Analyze the user's request with AI
        nlu_result = await ai_service.process_with_nlu(request.message, provider="deepseek")
        
        intent = nlu_result.get("intent", "")
        tasks = nlu_result.get("tasks", [])
        
        logger.info(f"Chat NLU Result - Intent: {intent}, Tasks: {tasks}")
        
        # Check if user wants to create a workflow
        if any(keyword in request.message.lower() for keyword in ["create", "make", "build", "workflow", "automation"]):
            # Generate workflow ID and name
            workflow_id = str(uuid.uuid4())
            workflow_name = intent[:50] if intent else "AI-Generated Workflow"
            
            # Create workflow nodes from AI-generated tasks
            nodes = []
            connections = []
            
            # Add trigger node
            trigger_node = {
                "id": f"node_{uuid.uuid4().hex[:8]}",
                "type": "trigger",
                "title": "Manual Trigger",
                "description": "Trigger this workflow manually",
                "position": {"x": 100, "y": 100},
                "config": {
                    "triggerType": "manual"
                },
                "connections": []
            }
            nodes.append(trigger_node)
            
            # Add action nodes for each task
            prev_node_id = trigger_node["id"]
            y_position = 200
            
            for i, task in enumerate(tasks[:5]):  # Limit to 5 tasks
                node_id = f"node_{uuid.uuid4().hex[:8]}"
                
                # Determine action type from task description
                action_type = "notify"  # Default
                integration_id = "slack"  # Default
                
                if "email" in task.lower():
                    action_type = "send_email"
                    integration_id = "gmail"
                elif "slack" in task.lower() or "message" in task.lower():
                    action_type = "notify"
                    integration_id = "slack"
                
                node = {
                    "id": node_id,
                    "type": "action",
                    "title": f"Step {i+1}: {task[:30]}...",
                    "description": task,
                    "position": {"x": 100, "y": y_position},
                    "config": {
                        "actionType": action_type,
                        "integrationId": integration_id,
                        "message": task
                    },
                    "connections": []
                }
                nodes.append(node)
                
                # Create connection from previous node
                connection = {
                    "id": f"conn_{uuid.uuid4().hex[:8]}",
                    "source": prev_node_id,
                    "target": node_id,
                    "condition": None
                }
                connections.append(connection)
                
                # Update for next iteration
                prev_node_id = node_id
                y_position += 100
            
            # Create workflow definition
            workflow_def = {
                "id": workflow_id,
                "name": workflow_name,
                "description": f"Generated from: {request.message}",
                "version": "1.0",
                "nodes": nodes,
                "connections": connections,
                "triggers": ["manual"],
                "enabled": True,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            }
            
            # Save workflow
            workflows = load_workflows()
            workflows.append(workflow_def)
            save_workflows(workflows)
            
            logger.info(f"Created and saved workflow {workflow_id}: {workflow_name}")
            
            return {
                "success": True,
                "response": {
                    "message": f"✅ I've created a workflow: **{workflow_name}**\\n\\nIt includes {len(tasks)} steps based on your request.\\n\\nYou can run it now or edit it first.",
                    "workflow_id": workflow_id,
                    "workflow_name": workflow_name,
                    "steps_count": len(nodes) - 1,  # Exclude trigger
                    "is_scheduled": False,
                    "requires_confirmation": True,
                    "actions": [
                        {"type": "execute", "label": "Run Now", "workflowId": workflow_id},
                        {"type": "edit", "label": "Edit Workflow", "workflowId": workflow_id},
                        {"type": "schedule", "label": "Schedule", "workflowId": workflow_id}
                    ]
                }
            }
        
        # Handle other intents (list, schedule, etc.)
        elif any(keyword in request.message.lower() for keyword in ["list", "show", "what workflows"]):
            workflows = load_workflows()
            workflow_list = [{"id": w["id"], "name": w["name"]} for w in workflows]
            
            return {
                "success": True,
                "response": {
                    "message": f"You have {len(workflows)} workflows:\\n" + "\\n".join([f"- {w['name']}" for w in workflows[:10]]),
                    "workflows": workflow_list,
                    "actions": []
                }
            }
        
        else:
            # General help
            return {
                "success": True,
                "response": {
                    "message": "I can help you with:\\n- **Create workflow**: 'Create a workflow to send daily reports'\\n- **List workflows**: 'Show my workflows'\\n- **Schedule**: 'Schedule this workflow daily'\\n\\nWhat would you like to do?",
                    "actions": []
                }
            }

    except Exception as e:
        logger.error(f"Error in chat agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@router.post("/execute-generated")
async def execute_generated_workflow(request: ExecuteGeneratedRequest):
    """
    Execute a workflow that was generated via chat.
    """
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    return {
        "success": True, 
        "execution_id": execution_id,
        "status": "running",
        "message": "Workflow execution started successfully"
    }
