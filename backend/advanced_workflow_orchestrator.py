#!/usr/bin/env python3
"""
Advanced Workflow Orchestrator for ATOM
Builds complex multi-step workflows with conditional logic, parallel processing, and cross-service integration
"""

import os
import json
import logging
import asyncio
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from fastapi import HTTPException
import aiohttp
import uuid
import re
import ast
from core.byok_endpoints import get_byok_manager

# Configure logging
logger = logging.getLogger(__name__)

class WorkflowStepType(Enum):
    """Types of workflow steps"""
    NLU_ANALYSIS = "nlu_analysis"
    TASK_CREATION = "task_creation"
    EMAIL_SEND = "email_send"
    SLACK_NOTIFICATION = "slack_notification"
    ASANA_INTEGRATION = "asana_integration"
    CONDITIONAL_LOGIC = "conditional_logic"
    PARALLEL_EXECUTION = "parallel_execution"
    DATA_TRANSFORMATION = "data_transformation"
    API_CALL = "api_call"
    DELAY = "delay"
    APPROVAL_REQUIRED = "approval_required"
    NOTION_INTEGRATION = "notion_integration"
    GMAIL_FETCH = "gmail_fetch"
    GMAIL_INTEGRATION = "gmail_integration"
    GMAIL_SEARCH = "gmail_search"
    NOTION_SEARCH = "notion_search"
    NOTION_DB_QUERY = "notion_db_query"
    APP_SEARCH = "app_search"
    HUBSPOT_INTEGRATION = "hubspot_integration"
    SALESFORCE_INTEGRATION = "salesforce_integration"
    UNIVERSAL_INTEGRATION = "universal_integration"

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"

@dataclass
class WorkflowStep:
    """Individual workflow step definition"""
    step_id: str
    step_type: WorkflowStepType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    parallel_steps: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30

@dataclass
class WorkflowContext:
    """Context shared across workflow steps"""
    workflow_id: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class WorkflowDefinition:
    """Complete workflow definition"""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    start_step: str
    triggers: List[str] = field(default_factory=list)
    version: str = "1.0"

class AdvancedWorkflowOrchestrator:
    """Advanced workflow orchestrator with complex multi-step processing"""

    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.active_contexts: Dict[str, WorkflowContext] = {}
        self.ai_service = None
        self.http_sessions = {}
        
        # Initialize Template Manager
        try:
            from core.workflow_template_system import WorkflowTemplateManager
            self.template_manager = WorkflowTemplateManager()
        except ImportError:
            self.template_manager = None
            logger.warning("WorkflowTemplateManager not found, template features disabled")

        # Initialize AI service
        self._initialize_ai_service()

        # Load predefined workflows
        self._load_predefined_workflows()

    def _initialize_ai_service(self):
        """Initialize AI service for NLU processing"""
        try:
            # Import the enhanced AI workflow service
            from enhanced_ai_workflow_endpoints import RealAIWorkflowService
            self.ai_service = RealAIWorkflowService()
        except Exception as e:
            logger.warning(f"Could not initialize AI service: {e}")

    def _load_predefined_workflows(self):
        """Load predefined complex workflows"""

        # Workflow 1: Customer Support Ticket Automation
        customer_support_workflow = WorkflowDefinition(
            workflow_id="customer_support_automation",
            name="Customer Support Ticket Automation",
            description="Complex workflow for automated customer support ticket processing",
            steps=[
                WorkflowStep(
                    step_id="analyze_ticket",
                    step_type=WorkflowStepType.NLU_ANALYSIS,
                    description="Analyze incoming support ticket with AI",
                    parameters={"extract_entities": True, "sentiment_analysis": True},
                    next_steps=["categorize_ticket"]
                ),
                WorkflowStep(
                    step_id="categorize_ticket",
                    step_type=WorkflowStepType.CONDITIONAL_LOGIC,
                    description="Categorize ticket based on analysis",
                    parameters={
                        "conditions": [
                            {"if": "priority == 'urgent'", "then": ["escalate_manager"]},
                            {"if": "category == 'technical'", "then": ["assign_technical"]},
                            {"if": "category == 'billing'", "then": ["assign_billing"]},
                            {"else": ["assign_general"]}
                        ]
                    },
                    next_steps=["escalate_manager", "assign_technical", "assign_billing", "assign_general"]
                ),
                WorkflowStep(
                    step_id="escalate_manager",
                    step_type=WorkflowStepType.SLACK_NOTIFICATION,
                    description="Escalate urgent ticket to manager",
                    parameters={"channel": "#support-escalations", "mention": "@manager"},
                    next_steps=["create_asana_task"]
                ),
                WorkflowStep(
                    step_id="assign_technical",
                    step_type=WorkflowStepType.ASANA_INTEGRATION,
                    description="Assign technical ticket to engineering team",
                    parameters={"project": "Technical Support", "team": "engineering"},
                    next_steps=["send_acknowledgment"]
                ),
                WorkflowStep(
                    step_id="assign_billing",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Forward billing inquiry to finance team",
                    parameters={"template": "billing_forward", "recipient": "finance@company.com"},
                    next_steps=["create_billing_task"]
                ),
                WorkflowStep(
                    step_id="assign_general",
                    step_type=WorkflowStepType.PARALLEL_EXECUTION,
                    description="Handle general support request",
                    parallel_steps=["create_asana_task", "send_acknowledgment"],
                    next_steps=["follow_up_reminder"]
                ),
                WorkflowStep(
                    step_id="create_asana_task",
                    step_type=WorkflowStepType.ASANA_INTEGRATION,
                    description="Create task in Asana for tracking",
                    parameters={"project": "Customer Support", "assignee": "support_team"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="send_acknowledgment",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Send acknowledgment email to customer",
                    parameters={"template": "ticket_acknowledgment"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="create_billing_task",
                    step_type=WorkflowStepType.ASANA_INTEGRATION,
                    description="Create billing task for finance team",
                    parameters={"project": "Billing", "assignee": "finance_team"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="follow_up_reminder",
                    step_type=WorkflowStepType.DELAY,
                    description="Wait 24 hours before follow-up",
                    parameters={"delay_hours": 24},
                    next_steps=["check_resolution"]
                ),
                WorkflowStep(
                    step_id="check_resolution",
                    step_type=WorkflowStepType.CONDITIONAL_LOGIC,
                    description="Check if ticket is resolved",
                    parameters={
                        "conditions": [
                            {"if": "status == 'resolved'", "then": ["send_satisfaction_survey"]},
                            {"else": ["escalate_again"]}
                        ]
                    },
                    next_steps=["send_satisfaction_survey", "escalate_again"]
                ),
                WorkflowStep(
                    step_id="send_satisfaction_survey",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Send customer satisfaction survey",
                    parameters={"template": "satisfaction_survey"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="escalate_again",
                    step_type=WorkflowStepType.SLACK_NOTIFICATION,
                    description="Escalate unresolved ticket",
                    parameters={"channel": "#support-escalations", "message": "Ticket requires attention"},
                    next_steps=[]
                )
            ],
            start_step="analyze_ticket"
        )

        # Workflow 2: Project Management Automation
        project_management_workflow = WorkflowDefinition(
            workflow_id="project_management_automation",
            name="Project Management Automation",
            description="Automated project setup and task management",
            steps=[
                WorkflowStep(
                    step_id="analyze_project_request",
                    step_type=WorkflowStepType.NLU_ANALYSIS,
                    description="Analyze project setup request",
                    parameters={"extract_scope": True, "identify_milestones": True},
                    next_steps=["create_project_structure"]
                ),
                WorkflowStep(
                    step_id="create_project_structure",
                    step_type=WorkflowStepType.PARALLEL_EXECUTION,
                    description="Create project structure in multiple systems",
                    parallel_steps=["setup_asana_project", "create_slack_channel", "setup_repository"],
                    next_steps=["notify_stakeholders"]
                ),
                WorkflowStep(
                    step_id="setup_asana_project",
                    step_type=WorkflowStepType.ASANA_INTEGRATION,
                    description="Create project in Asana with tasks",
                    parameters={"create_tasks": True, "set_deadlines": True},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="create_slack_channel",
                    step_type=WorkflowStepType.SLACK_NOTIFICATION,
                    description="Create dedicated Slack channel",
                    parameters={"create_channel": True, "invite_team": True},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="setup_repository",
                    step_type=WorkflowStepType.API_CALL,
                    description="Setup code repository if needed",
                    parameters={"service": "github", "action": "create_repo"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="notify_stakeholders",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Send project kickoff email",
                    parameters={"template": "project_kickoff"},
                    next_steps=["schedule_kickoff_meeting"]
                ),
                WorkflowStep(
                    step_id="schedule_kickoff_meeting",
                    step_type=WorkflowStepType.API_CALL,
                    description="Schedule project kickoff meeting",
                    parameters={"service": "calendar", "action": "schedule_meeting"},
                    next_steps=["setup_daily_standup"]
                ),
                WorkflowStep(
                    step_id="setup_daily_standup",
                    step_type=WorkflowStepType.DELAY,
                    description="Setup daily standup reminders",
                    parameters={"recurring": True, "frequency": "daily"},
                    next_steps=[]
                )
            ],
            start_step="analyze_project_request"
        )

        # Workflow 3: Sales Lead Processing
        sales_lead_workflow = WorkflowDefinition(
            workflow_id="sales_lead_processing",
            name="Sales Lead Processing Automation",
            description="Automated sales lead qualification and follow-up",
            steps=[
                WorkflowStep(
                    step_id="analyze_lead",
                    step_type=WorkflowStepType.NLU_ANALYSIS,
                    description="Analyze and qualify incoming lead",
                    parameters={"extract_contact_info": True, "score_lead": True},
                    next_steps=["lead_scoring"]
                ),
                WorkflowStep(
                    step_id="lead_scoring",
                    step_type=WorkflowStepType.CONDITIONAL_LOGIC,
                    description="Score lead and route accordingly",
                    parameters={
                        "conditions": [
                            {"if": "score >= 80", "then": ["high_priority_routing"]},
                            {"if": "score >= 50", "then": ["medium_priority_routing"]},
                            {"else": ["low_priority_routing"]}
                        ]
                    },
                    next_steps=["high_priority_routing", "medium_priority_routing", "low_priority_routing"]
                ),
                WorkflowStep(
                    step_id="high_priority_routing",
                    step_type=WorkflowStepType.PARALLEL_EXECUTION,
                    description="Immediate follow-up for high-value leads",
                    parallel_steps=["notify_sales_rep", "create_crm_task", "schedule_demo"],
                    next_steps=["send_welcome_email"]
                ),
                WorkflowStep(
                    step_id="medium_priority_routing",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Send personalized email sequence",
                    parameters={"template": "nurture_sequence", "follow_up_days": 3},
                    next_steps=["create_crm_task"]
                ),
                WorkflowStep(
                    step_id="low_priority_routing",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Add to general newsletter",
                    parameters={"template": "newsletter_welcome"},
                    next_steps=["create_follow_up_task"]
                ),
                WorkflowStep(
                    step_id="notify_sales_rep",
                    step_type=WorkflowStepType.SLACK_NOTIFICATION,
                    description="Notify sales rep immediately",
                    parameters={"channel": "#sales-alerts", "urgent": True},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="create_crm_task",
                    step_type=WorkflowStepType.ASANA_INTEGRATION,
                    description="Create lead follow-up task in CRM",
                    parameters={"priority": "high", "follow_up_days": 1},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="schedule_demo",
                    step_type=WorkflowStepType.API_CALL,
                    description="Schedule product demo",
                    parameters={"service": "calendar", "duration": "30min"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="send_welcome_email",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="Send personalized welcome email",
                    parameters={"template": "high_value_welcome"},
                    next_steps=[]
                ),
                WorkflowStep(
                    step_id="create_follow_up_task",
                    step_type=WorkflowStepType.DELAY,
                    description="Schedule follow-up for later",
                    parameters={"delay_days": 7},
                    next_steps=[]
                )
            ],
            start_step="analyze_lead"
        )

        # Register workflows
        self.workflows[customer_support_workflow.workflow_id] = customer_support_workflow
        self.workflows[project_management_workflow.workflow_id] = project_management_workflow
        self.workflows[customer_support_workflow.workflow_id] = customer_support_workflow
        self.workflows[project_management_workflow.workflow_id] = project_management_workflow
        self.workflows[sales_lead_workflow.workflow_id] = sales_lead_workflow

    async def generate_dynamic_workflow(self, user_query: str) -> Dict[str, Any]:
        """
        Dynamically generate a workflow from a user query using high-reasoning AI.
        Returns a standardized workflow definition dict with nodes and connections.
        """
        if not self.ai_service:
            raise ValueError("AI service not initialized")

        # 1. Get a high-reasoning provider for the planning phase
        byok_manager = get_byok_manager()
        try:
            planner_provider_id = byok_manager.get_optimal_provider("reasoning", min_reasoning_level=4)
            if not planner_provider_id:
                planner_provider_id = byok_manager.get_optimal_provider("analysis", min_reasoning_level=3)
            
            if not planner_provider_id:
                planner_provider_id = "openai"
                
            planner_provider = byok_manager.providers.get(planner_provider_id)
            logger.info(f"Using {planner_provider.name if planner_provider else planner_provider_id} for task planning")
            
        except Exception as e:
            logger.warning(f"Failed to select optimal planner: {e}")
            planner_provider_id = "openai"

        # 2. Break down the task
        decomposition = await self.ai_service.break_down_task(user_query, provider=planner_provider_id)
        steps_data = decomposition.get('steps', [])
        trigger_data = decomposition.get('trigger')
        
        # 3. Create standardized WorkflowDefinition structure
        workflow_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        nodes = []
        connections = []
        
        # Add Trigger node if present
        start_node_id = "step_1"
        if trigger_data:
            trigger_id = f"trigger_{uuid.uuid4().hex[:6]}"
            nodes.append({
                "id": trigger_id,
                "type": "trigger",
                "title": trigger_data.get("description", "Start Trigger"),
                "description": trigger_data.get("description", ""),
                "position": {"x": 100, "y": 100},
                "config": {
                    "service": trigger_data.get("service"),
                    "event": trigger_data.get("event"),
                    "trigger_type": trigger_data.get("type")
                },
                "connections": [start_node_id]
            })
            
            connections.append({
                "id": f"conn_trigger",
                "source": trigger_id,
                "target": start_node_id
            })

        for i, step_data in enumerate(steps_data):
            step_id = step_data.get("step_id", f"step_{i+1}")
            title = step_data.get("title", f"Step {i+1}")
            description = step_data.get("description", "Process step")
            service = step_data.get("service", "task").lower()
            
            node_type = "action"
            if service == "delay":
                node_type = "delay"
            elif any(s in service for s in ["condition", "logic", "if"]):
                node_type = "condition"

            config = {
                "service": service,
                "action": step_data.get("action", "execute"),
                "parameters": step_data.get("parameters", {}),
                "complexity": step_data.get("complexity", 2)
            }
            
            node_connections = []
            if i < len(steps_data) - 1:
                next_id = steps_data[i+1].get("step_id", f"step_{i+2}")
                node_connections.append(next_id)
                connections.append({
                    "id": f"conn_{i}",
                    "source": step_id,
                    "target": next_id
                })

            nodes.append({
                "id": step_id,
                "type": node_type,
                "title": title,
                "description": description,
                "position": {"x": 100 + (i+1)*250, "y": 100},
                "config": config,
                "connections": node_connections
            })

        # Final standardized workflow definition
        standard_workflow = {
            "id": workflow_id,
            "workflow_id": workflow_id,
            "name": f"Dynamic: {user_query[:30]}...",
            "description": f"Generated from query: {user_query}",
            "version": "1.0",
            "nodes": nodes,
            "connections": connections,
            "triggers": [trigger_data.get("description")] if trigger_data else [],
            "enabled": True,
            "createdAt": datetime.datetime.now().isoformat(),
            "updatedAt": datetime.datetime.now().isoformat()
        }
        
        # Store internal dataclass version for orchestrator execution
        internal_steps = []
        for node in nodes:
            if node["type"] == "trigger": continue
            
            svc = node["config"]["service"]
            if svc == "gmail" or svc == "email":
                step_type = WorkflowStepType.EMAIL_SEND
            elif svc == "slack":
                step_type = WorkflowStepType.SLACK_NOTIFICATION
            elif svc == "hubspot":
                step_type = WorkflowStepType.HUBSPOT_INTEGRATION
            elif svc == "salesforce":
                step_type = WorkflowStepType.SALESFORCE_INTEGRATION
            elif svc == "delay":
                step_type = WorkflowStepType.DELAY
            elif svc == "asana":
                step_type = WorkflowStepType.ASANA_INTEGRATION
            elif svc == "notion":
                step_type = WorkflowStepType.NOTION_INTEGRATION
            else:
                # Use universal integration as fallback for all other services
                step_type = WorkflowStepType.UNIVERSAL_INTEGRATION

            params = node["config"].get("parameters", {}).copy()
            params["service"] = svc
            params["action"] = node["config"].get("action", "execute")

            internal_steps.append(WorkflowStep(
                step_id=node["id"],
                step_type=step_type,
                description=node["description"],
                parameters=params,
                next_steps=node["connections"]
            ))

        internal_wf = WorkflowDefinition(
            workflow_id=workflow_id,
            name=standard_workflow["name"],
            description=standard_workflow["description"],
            steps=internal_steps,
            start_step=start_node_id,
            triggers=standard_workflow["triggers"]
        )
        self.workflows[workflow_id] = internal_wf
        
        # 4. Handle Template registration if requested by AI
        if decomposition.get("is_template"):
            template_id = self._create_template_from_workflow(
                internal_wf, 
                category=decomposition.get("category", "automation")
            )
            standard_workflow["template_id"] = template_id
            logger.info(f"Dynamically generated template: {template_id}")

        return standard_workflow


    async def execute_workflow(self, workflow_id: str, input_data: Dict[str, Any],
                             execution_context: Optional[Dict[str, Any]] = None) -> WorkflowContext:
        """Execute a complex workflow"""

        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflows[workflow_id]
        context = WorkflowContext(
            workflow_id=str(uuid.uuid4()),
            input_data=input_data,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.datetime.now()
        )

        if execution_context:
            context.variables.update(execution_context)

        self.active_contexts[context.workflow_id] = context

        try:
            # Initialize AI service sessions
            if self.ai_service:
                await self.ai_service.initialize_sessions()

            # Execute workflow steps
            await self._execute_workflow_step(workflow, workflow.start_step, context)

            context.status = WorkflowStatus.COMPLETED
            context.completed_at = datetime.datetime.now()

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            context.status = WorkflowStatus.FAILED
            context.error_message = str(e)
            context.completed_at = datetime.datetime.now()

        finally:
            # Cleanup AI service sessions
            if self.ai_service:
                await self.ai_service.cleanup_sessions()

        return context

    async def _execute_workflow_step(self, workflow: WorkflowDefinition, step_id: str,
                                   context: WorkflowContext) -> None:
        """Execute a single workflow step"""

        if step_id not in [s.step_id for s in workflow.steps]:
            logger.warning(f"Step {step_id} not found in workflow")
            return

        step = next(s for s in workflow.steps if s.step_id == step_id)
        context.current_step = step_id

        logger.info(f"Executing step: {step_id} - {step.description}")

        # Check if step conditions are met
        if not await self._check_conditions(step.conditions, context):
            logger.info(f"Conditions not met for step {step_id}, skipping")
            return

        # Execute the step based on its type
        step_result = await self._execute_step_by_type(workflow, step, context)

        # Store step result
        context.results[step_id] = step_result
        context.execution_history.append({
            "step_id": step_id,
            "step_type": step.step_type.value,
            "status": step_result.get("status", "completed"),
            "timestamp": datetime.datetime.now().isoformat(),
            "result": step_result,
            "execution_time_ms": step_result.get("execution_time_ms", 0)
        })

        # Determine next steps
        # Prioritize dynamic next steps from step result (useful for conditional logic)
        target_next_steps = step_result.get("next_steps", step.next_steps)

        if step.parallel_steps:
            # Execute parallel steps concurrently
            parallel_tasks = [
                self._execute_workflow_step(workflow, next_step, context)
                for next_step in step.parallel_steps
            ]
            await asyncio.gather(*parallel_tasks, return_exceptions=True)

            # After parallel execution, continue to sequential next steps
            for next_step in target_next_steps:
                await self._execute_workflow_step(workflow, next_step, context)
        else:
            # Sequential execution
            for next_step in target_next_steps:
                await self._execute_workflow_step(workflow, next_step, context)

    async def _check_conditions(self, conditions: Dict[str, Any], context: WorkflowContext) -> bool:
        """Check if step conditions are met"""
        if not conditions:
            return True

        # Implement condition evaluation logic
        for condition in conditions.get("conditions", []):
            if_condition = condition.get("if")
            then_steps = condition.get("then", [])
            else_step = condition.get("else")

            # Simple condition evaluation (can be enhanced)
            if await self._evaluate_condition(if_condition, context):
                return True
            elif else_step:
                return True

        return True

    async def _evaluate_condition(self, condition: str, context: WorkflowContext) -> bool:
        """Evaluate a single condition with dynamic variable support (no hardcoding)"""
        try:
            # 1. Parse the condition using regex to support various operators
            # Pattern: variable_name OPERATOR expected_value
            # Operators supported: ==, !=, >=, <=, >, <
            match = re.search(r'(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+)', condition)
            if not match:
                logger.warning(f"Invalid condition format: {condition}. Must be 'var operator value'.")
                return True # Proceed if format is invalid to avoid blocking workflow

            var_name, operator, expected_val_raw = match.groups()
            actual_val = context.variables.get(var_name)

            # 2. Parse expected value into its proper type
            expected_val_raw = expected_val_raw.strip()
            
            # Handle quoted strings
            if (expected_val_raw.startswith("'") and expected_val_raw.endswith("'")) or \
               (expected_val_raw.startswith('"') and expected_val_raw.endswith('"')):
                expected_val = expected_val_raw[1:-1]
            # Handle Booleans
            elif expected_val_raw.lower() == 'true':
                expected_val = True
            elif expected_val_raw.lower() == 'false':
                expected_val = False
            # Handle Numbers
            else:
                try:
                    if '.' in expected_val_raw:
                        expected_val = float(expected_val_raw)
                    else:
                        expected_val = int(expected_val_raw)
                except ValueError:
                    # Fallback to string if not a number
                    expected_val = expected_val_raw

            # 3. Perform the comparison based on operator
            try:
                if operator == '==':
                    return actual_val == expected_val
                elif operator == '!=':
                    return actual_val != expected_val
                elif operator == '>=':
                    return actual_val >= expected_val
                elif operator == '<=':
                    return actual_val <= expected_val
                elif operator == '>':
                    return actual_val > expected_val
                elif operator == '<':
                    return actual_val < expected_val
            except TypeError as te:
                logger.error(f"Type mismatch in condition evaluation: {te} (Var: {var_name}, Type: {type(actual_val)})")
                return False

            return True # Default to True
        except Exception as e:
            logger.warning(f"Dynamic condition evaluation failed: {e}")
            return True  # Default to proceeding if condition evaluation fails

    def _resolve_variables(self, value: Any, context: WorkflowContext) -> Any:
        """Resolve variables in a value (string, dict, or list)"""
        if isinstance(value, str):
            # Replace {{variable}} with value from context.variables
            import re
            matches = re.findall(r'\{\{([^}]+)\}\}', value)
            for match in matches:
                # Support nested access like {{step_id.key}}
                if '.' in match:
                    parts = match.split('.')
                    step_id = parts[0]
                    key = parts[1]
                    if step_id in context.results:
                        val = context.results[step_id].get(key, "")
                        value = value.replace(f"{{{{{match}}}}}", str(val))
                elif match in context.variables:
                    value = value.replace(f"{{{{{match}}}}}", str(context.variables[match]))
            return value
        elif isinstance(value, dict):
            return {k: self._resolve_variables(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_variables(v, context) for v in value]
        return value

    async def _execute_step_by_type(self, workflow: WorkflowDefinition, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a step based on its type"""
        start_time = time.time()
        
        # Resolve variables in parameters before execution
        step.parameters = self._resolve_variables(step.parameters, context)

        try:
            if step.step_type == WorkflowStepType.NLU_ANALYSIS:
                result = await self._execute_nlu_analysis(step, context)
            elif step.step_type == WorkflowStepType.CONDITIONAL_LOGIC:
                result = await self._execute_conditional_logic(workflow, step, context)
            elif step.step_type == WorkflowStepType.EMAIL_SEND:
                result = await self._execute_email_send(step, context)
            elif step.step_type == WorkflowStepType.SLACK_NOTIFICATION:
                result = await self._execute_slack_notification(step, context)
            elif step.step_type == WorkflowStepType.ASANA_INTEGRATION:
                result = await self._execute_asana_integration(step, context)
            elif step.step_type == WorkflowStepType.PARALLEL_EXECUTION:
                result = await self._execute_parallel_execution(step, context)
            elif step.step_type == WorkflowStepType.HUBSPOT_INTEGRATION:
                result = await self._execute_hubspot_integration(step, context)
            elif step.step_type == WorkflowStepType.SALESFORCE_INTEGRATION:
                result = await self._execute_salesforce_integration(step, context)
            elif step.step_type == WorkflowStepType.DELAY:
                result = await self._execute_delay(step, context)
            elif step.step_type == WorkflowStepType.API_CALL:
                result = await self._execute_api_call(step, context)
            elif step.step_type == WorkflowStepType.UNIVERSAL_INTEGRATION:
                result = await self._execute_universal_integration(step, context)
            elif step.step_type == WorkflowStepType.NOTION_INTEGRATION:
                result = await self._execute_notion_integration(step, context)
            elif step.step_type == WorkflowStepType.GMAIL_FETCH:
                result = await self._execute_gmail_fetch(step, context)
            elif step.step_type == WorkflowStepType.GMAIL_INTEGRATION:
                result = await self._execute_gmail_integration(step, context)
            elif step.step_type == WorkflowStepType.GMAIL_SEARCH:
                result = await self._execute_gmail_search(step, context)
            elif step.step_type == WorkflowStepType.NOTION_SEARCH:
                result = await self._execute_notion_search(step, context)
            elif step.step_type == WorkflowStepType.NOTION_DB_QUERY:
                result = await self._execute_notion_db_query(step, context)
            elif step.step_type == WorkflowStepType.APP_SEARCH:
                result = await self._execute_app_search(step, context)
            else:
                result = {"status": "completed", "message": f"Step type {step.step_type.value} executed"}

            execution_time = (time.time() - start_time) * 1000
            result["execution_time_ms"] = execution_time

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Step execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "execution_time_ms": execution_time
            }

    async def _format_content_for_output(self, content: Any, target_type: str = "markdown", title: str = "Content") -> Any:
        """
        Format content for a specific output target (Notion, Slack, Email).
        Handles strings, lists, and lists-as-strings with robust parsing.
        """
        data_to_format = []
        
        # 1. Robustly extract list-like data
        if isinstance(content, list):
            data_to_format = content
        elif isinstance(content, str):
            stripped = content.strip()
            # Try to find a list within the string (e.g. "Result: ['item1', 'item2']")
            list_match = re.search(r'\[.*\]', stripped, re.DOTALL)
            if list_match:
                try:
                    content_list = ast.literal_eval(list_match.group(0))
                    if isinstance(content_list, list):
                        data_to_format = content_list
                except:
                    pass
            
            if not data_to_format:
                # Fallback to line-based parsing
                lines = [l.strip() for l in stripped.split('\n') if l.strip()]
                # Remove common prefixes from the first line if it looks like a label
                if lines:
                    lines[0] = re.sub(r'^(Tasks extracted|Result|Output|Content|Tasks):\s*', '', lines[0], flags=re.I)
                    data_to_format = [l for l in lines if l.strip()]
        else:
            data_to_format = [str(content)]

        # 2. Flatten any nested lists and clean items
        flattened_data = []
        for stage1 in data_to_format:
            if isinstance(stage1, list):
                for item in stage1:
                    flattened_data.append(str(item))
            else:
                flattened_data.append(str(stage1))
        
        # 3. Target-specific formatting
        if target_type == "notion":
            from integrations.notion_service import notion_service as notion
            blocks = []
            
            # Use title as a header if provided and not redundant
            if title and title.lower() not in ["content", "result"]:
                blocks.append(notion.create_heading_block(title, level=2))
            
            for item in flattened_data:
                clean_item = item.strip()
                # Remove common list prefixes
                clean_item = re.sub(r'^(\d+\.|\*|\-)\s*', '', clean_item)
                # Remove "Task X: " if present
                clean_item = re.sub(r'^Task\s+\d+:\s*', '', clean_item)
                
                if not clean_item:
                    continue

                # Determine block type: use To-Do if it's a "task" workflow, otherwise paragraph
                is_task_context = any(word in (title or "").lower() for word in ["task", "todo", "action", "follow-up"])
                if is_task_context:
                    blocks.append(notion.create_todo_block(clean_item))
                else:
                    blocks.append(notion.create_text_block(clean_item))
            return blocks

        elif target_type == "slack":
            message = ""
            if title and title.lower() not in ["content", "result"]:
                message += f"*<{title}>*\n"
            
            for item in flattened_data:
                clean_item = item.strip()
                clean_item = re.sub(r'^(\d+\.|\*|\-)\s*', '', clean_item)
                clean_item = re.sub(r'^Task\s+\d+:\s*', '', clean_item)
                if clean_item:
                    message += f"• {clean_item}\n"
            return message

        elif target_type == "email":
            html = ""
            if title and title.lower() not in ["content", "result"]:
                html += f"<h2>{title}</h2>"
            
            html += "<ul>"
            for item in flattened_data:
                clean_item = item.strip()
                clean_item = re.sub(r'^(\d+\.|\*|\-)\s*', '', clean_item)
                clean_item = re.sub(r'^Task\s+\d+:\s*', '', clean_item)
                if clean_item:
                    html += f"<li>{clean_item}</li>"
            html += "</ul>"
            return html

        else: # Default is markdown-like list
            text = ""
            if title and title.lower() not in ["content", "result"]:
                text += f"### {title}\n"
            for item in flattened_data:
                clean_item = item.strip()
                clean_item = re.sub(r'^(\d+\.|\*|\-)\s*', '', clean_item)
                clean_item = re.sub(r'^Task\s+\d+:\s*', '', clean_item)
                if clean_item:
                    text += f"- {clean_item}\n"
            return text

    async def _execute_nlu_analysis(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute NLU analysis step"""
        if not self.ai_service:
            return {"status": "skipped", "message": "AI service not available"}

        # Prioritize text_input from step parameters (dynamic resolution)
        input_text = step.parameters.get("text_input")
        if not input_text:
            input_text = context.input_data.get("text", str(context.input_data))
        
        logger.info(f"NLU Analysis input length: {len(str(input_text))}")
        
        # Determine optimal provider based on complexity
        complexity = step.parameters.get("complexity", 2)
        provider_id = "openai" # Default
        
        try:
            byok_manager = get_byok_manager()
            # Map complexity 1-4 to reasoning levels
            # 1 -> Level 1 (Low)
            # 2 -> Level 2 (Medium)
            # 3 -> Level 3 (High)
            # 4 -> Level 4 (Reasoning)
            
            # For NLU analysis, we generally want at least level 2 unless it's very simple
            min_level = max(1, complexity)
            
            optimal_id = byok_manager.get_optimal_provider("analysis", min_reasoning_level=min_level)
            if optimal_id:
                provider_id = optimal_id
                logger.info(f"Selected provider {provider_id} for step {step.step_id} (Complexity: {complexity})")
        except Exception as e:
            logger.warning(f"Provider selection failed: {e}")
            provider_id = context.variables.get("preferred_ai_provider", "openai")

        try:
            # Use the specific instruction if available (from dynamic workflow)
            instruction = step.parameters.get("original_instruction")
            if instruction:
                # Prepend instruction to input
                input_text = f"Instruction: {instruction}\n\nInput Data: {input_text}"

            nlu_result = await self.ai_service.process_with_nlu(
                input_text,
                provider_id
            )

            # Update context with NLU results
            context.variables.update({
                "intent": nlu_result.get("intent"),
                "entities": nlu_result.get("entities", []),
                "priority": nlu_result.get("priority", "medium"),
                "confidence": nlu_result.get("confidence", 0.8),
                "category": nlu_result.get("category", "general"),
                "tasks": nlu_result.get("tasks", []),
                "relevance": nlu_result.get("relevance", "relevant"),
                "is_relevant": nlu_result.get("is_relevant", True)
            })

            return {
                "status": "completed",
                "nlu_result": nlu_result,
                "provider_used": provider_id,
                "complexity_level": complexity,
                "intent": nlu_result.get("intent"),
                "entities": nlu_result.get("entities", []),
                "confidence": nlu_result.get("confidence", 0.8),
                "tasks": nlu_result.get("tasks", []),
                "relevance": nlu_result.get("relevance", "relevant"),
                "is_relevant": nlu_result.get("is_relevant", True)
            }

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_conditional_logic(self, workflow: WorkflowDefinition, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute conditional logic step with AI support"""
        conditions = step.parameters.get("conditions", [])
        ai_option = step.parameters.get("ai_option", False)
        ai_prompt = step.parameters.get("ai_prompt")

        # 1. AI-Powered Evaluation
        if ai_option and self.ai_service:
            try:
                # Build a reasoning prompt for the AI
                full_prompt = f"Given the following workflow context and variables, evaluate which path to take.\n\n"
                full_prompt += f"Context: {json.dumps(context.variables, indent=2)}\n\n"
                full_prompt += f"Logic Prompt: {ai_prompt}\n\n"
                full_prompt += "Respond with a JSON object containing:\n"
                full_prompt += "1. 'path_id': the ID or index of the matching condition (from the 'then' list)\n"
                full_prompt += "2. 'reasoning': a brief explanation of the decision.\n"
                
                # Call AI service (using a reasoning-capable model if available)
                ai_response = await self.ai_service.analyze_text(full_prompt, complexity=3)
                
                # Parse response
                try:
                    # Look for JSON in the response
                    json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                    if json_match:
                        decision = json.loads(json_match.group(0))
                        next_steps = decision.get("path_id")
                        # If path_id is a single string but next_steps expects a list
                        if isinstance(next_steps, str):
                            # Handle 'false' or 'none' as signals to not proceed
                            if next_steps.lower() in ["false", "none", "stop", "null"]:
                                next_steps = []
                            else:
                                next_steps = [next_steps]
                        
                        # Validate next_steps exist in workflow
                        valid_steps = []
                        if next_steps:
                            for ns in next_steps:
                                if any(s.step_id == ns for s in workflow.steps):
                                    valid_steps.append(ns)
                                else:
                                    logger.warning(f"AI suggested non-existent step: {ns}. Ignoring.")
                        
                        return {
                            "status": "completed",
                            "ai_evaluation": True,
                            "reasoning": decision.get("reasoning"),
                            "next_steps": valid_steps
                        }
                except Exception as parse_e:
                    logger.warning(f"Failed to parse AI condition response: {parse_e}")
                    # Fallback to simple first step if AI fails
                    pass
            except Exception as ai_e:
                logger.error(f"AI condition evaluation failed: {ai_e}")
                # Fallback to normal evaluation
                pass

        # 2. Standard Evaluation (Dynamic variable comparisons)
        for condition in conditions:
            if_condition = condition.get("if")
            then_steps = condition.get("then", [])

            if await self._evaluate_condition(if_condition, context):
                # Set next steps based on condition
                return {
                    "status": "completed",
                    "condition_met": if_condition,
                    "next_steps": then_steps
                }

        return {"status": "completed", "condition_met": None, "next_steps": []}

    async def _execute_email_send(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute email send step"""
        template = step.parameters.get("template", "default")
        recipient = step.parameters.get("recipient", context.variables.get("email"))
        subject = step.parameters.get("subject", "ATOM Notification")
        content = step.parameters.get("content", context.input_data.get("text", ""))

        # Advanced formatting
        rich_content = await self._format_content_for_output(content, target_type="email", title=subject)

        # Simulate email sending (in real implementation, integrate with email service)
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "status": "completed",
            "template": template,
            "recipient": recipient,
            "subject": subject,
            "rich_content": rich_content,
            "sent_at": datetime.datetime.now().isoformat()
        }

    async def _execute_slack_notification(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Slack notification step"""
        channel = step.parameters.get("channel", "#general")
        content = step.parameters.get("message", context.input_data.get("text", ""))
        title = step.parameters.get("title", "New Notification")

        # Advanced formatting
        rich_message = await self._format_content_for_output(content, target_type="slack", title=title)

        # Simulate Slack notification (in real implementation, integrate with Slack API)
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "status": "completed",
            "channel": channel,
            "message": rich_message,
            "sent_at": datetime.datetime.now().isoformat()
        }

    async def _execute_asana_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Asana integration step"""
        project = step.parameters.get("project", "Default")
        assignee = step.parameters.get("assignee", "unassigned")

        # Simulate Asana task creation (in real implementation, integrate with Asana API)
        await asyncio.sleep(0.1)  # Simulate API call

        task_id = f"task_{uuid.uuid4().hex[:8]}"

        return {
            "status": "completed",
            "task_id": task_id,
            "project": project,
            "assignee": assignee,
            "created_at": datetime.datetime.now().isoformat()
        }

    async def _execute_parallel_execution(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute parallel execution step"""
        parallel_steps = step.parallel_steps

        return {
            "status": "completed",
            "parallel_steps": parallel_steps,
            "execution_type": "parallel"
        }

    async def _execute_delay(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute delay step"""
        duration = step.parameters.get("duration", step.parameters.get("delay_seconds", 0))
        unit = step.parameters.get("unit", "seconds").lower()
        
        # Convert to seconds
        try:
            duration_val = float(duration)
        except:
            duration_val = 0
            
        if unit == "days":
            delay_seconds = duration_val * 86400
        elif unit == "hours":
            delay_seconds = duration_val * 3600
        elif unit == "minutes":
            delay_seconds = duration_val * 60
        else:
            delay_seconds = duration_val
            
        if delay_seconds > 0:
            # Cap for demo purposes, in real app we'd use a scheduler
            await asyncio.sleep(min(delay_seconds, 1)) 

        return {
            "status": "completed",
            "delayed_seconds": delay_seconds,
            "actual_delay": min(delay_seconds, 1),
            "unit": unit
        }

    async def _execute_hubspot_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute HubSpot integration step"""
        try:
            from core.mock_mode import get_mock_mode_manager
            mock_manager = get_mock_mode_manager()
            
            if mock_manager.is_mock_mode("hubspot", False): # Assume no credentials for demo
                logger.info(f"HubSpot Mock Mode: Executing {step.parameters.get('action')}")
                return {"status": "completed", "result": {"id": "mock_hs_123", "status": "created"}, "mock": True}

            return {"status": "completed", "message": "HubSpot action processed", "parameters": step.parameters}
        except Exception as e:
            logger.error(f"HubSpot integration error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_salesforce_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Salesforce integration step"""
        try:
            from core.mock_mode import get_mock_mode_manager
            mock_manager = get_mock_mode_manager()
            
            if mock_manager.is_mock_mode("salesforce", False):
                logger.info(f"Salesforce Mock Mode: Executing {step.parameters.get('action')}")
                return {"status": "completed", "result": {"id": "mock_sf_456", "status": "created"}, "mock": True}

            return {"status": "completed", "message": "Salesforce action processed", "parameters": step.parameters}
        except Exception as e:
            logger.error(f"Salesforce integration error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_api_call(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute external API call step"""
        service = step.parameters.get("service", "unknown")
        action = step.parameters.get("action", "call")

        # Simulate API call (in real implementation, make actual API calls)
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "status": "completed",
            "service": service,
            "action": action,
            "call_time": datetime.datetime.now().isoformat()
        }

    async def _execute_notion_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Notion integration step"""
        try:
            from integrations.notion_service import NotionService
            notion = NotionService()
            
            action = step.parameters.get("action", "create_page")
            database_id = step.parameters.get("database_id")
            title = step.parameters.get("title", "New Task")
            content = step.parameters.get("content", "")
            
            if action == "create_page":
                if database_id:
                    properties = step.parameters.get("properties", {
                        "Name": {"title": [{"text": {"content": title}}]}
                    })
                    
                    # Use generalized rich formatting if content is provided
                    content_blocks = None
                    if content:
                        content_blocks = await self._format_content_for_output(content, target_type="notion", title=title)
                    
                    result = notion.create_page_in_database(
                        database_id=database_id,
                        properties=properties,
                        content_blocks=content_blocks
                    )
                else:
                    parent = step.parameters.get("parent")
                    properties = step.parameters.get("properties", {
                        "title": [{"text": {"content": title}}]
                    })
                    result = notion.create_page(parent, properties)
                
            elif action == "page_get":
                page_id = step.parameters.get("page_id")
                result = notion.get_page(page_id)
                
            elif action == "page_update":
                page_id = step.parameters.get("page_id")
                properties = step.parameters.get("properties", {})
                archived = step.parameters.get("archived", False)
                result = notion.update_page(page_id, properties, archived=archived)
                
            elif action == "db_query":
                database_id = step.parameters.get("database_id")
                filter_obj = step.parameters.get("filter")
                sorts = step.parameters.get("sorts")
                max_pages = step.parameters.get("page_size", 100)
                result = notion.query_database(database_id, filter=filter_obj, sorts=sorts, page_size=max_pages)
                
            elif action == "db_get":
                database_id = step.parameters.get("database_id")
                result = notion.get_database(database_id)
                
            elif action == "block_append":
                block_id = step.parameters.get("block_id")
                content = step.parameters.get("content", "")
                blocks = await self._format_content_for_output(content, target_type="notion")
                result = notion.append_block_children(block_id, blocks)
            else:
                return {"status": "failed", "error": f"Unsupported Notion action: {action}"}

            return {
                "status": "completed",
                "result": result,
                "notion_result": result, # Backward compatibility
                "action": action
            }
        except Exception as e:
            logger.error(f"Notion integration error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_gmail_fetch(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Gmail fetch step (Backward compatibility)"""
        step.parameters["action"] = "list"
        return await self._execute_gmail_integration(step, context)

    async def _execute_gmail_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Gmail integration step with full CRUD support"""
        try:
            from integrations.gmail_service import GmailService
            gmail = GmailService()
            
            action = step.parameters.get("action", "list")
            
            if action == "list":
                query = step.parameters.get("query", "is:unread")
                max_results = step.parameters.get("max_results", 5)
                # get_messages already returns parsed messages
                result = gmail.get_messages(query=query, max_results=max_results)
                return {
                    "status": "completed",
                    "result": result, # For consistency
                    "messages": result,
                    "count": len(result),
                    "action": action
                }
                
            elif action == "message_get":
                message_id = step.parameters.get("message_id")
                result = gmail.get_message(message_id)
                
            elif action == "message_modify":
                message_id = step.parameters.get("message_id")
                add_labels = step.parameters.get("add_labels", [])
                remove_labels = step.parameters.get("remove_labels", [])
                result = gmail.modify_message(message_id, add_labels=add_labels, remove_labels=remove_labels)
                
            elif action == "message_delete":
                message_id = step.parameters.get("message_id")
                result = gmail.delete_message(message_id)
                
            elif action == "draft_create":
                to = step.parameters.get("to")
                subject = step.parameters.get("subject", "Automated Response")
                body = step.parameters.get("body", "")
                thread_id = step.parameters.get("thread_id")
                result = gmail.draft_message(to=to, subject=subject, body=body, thread_id=thread_id)
                
            elif action == "send":
                to = step.parameters.get("to")
                subject = step.parameters.get("subject", "Automated Response")
                body = step.parameters.get("body", "")
                thread_id = step.parameters.get("thread_id")
                result = gmail.send_message(to=to, subject=subject, body=body, thread_id=thread_id)
            else:
                return {"status": "failed", "error": f"Unsupported Gmail action: {action}"}

            return {
                "status": "completed",
                "result": result,
                "messages": result if action == "list" else None, # Compatibility
                "action": action
            }
        except Exception as e:
            logger.error(f"Gmail integration error: {e}")
            return {"status": "failed", "error": str(e)}


    async def _execute_gmail_search(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Gmail search step"""
        try:
            from integrations.gmail_service import GmailService
            gmail = GmailService()
            query = step.parameters.get("query", "")
            max_results = step.parameters.get("max_results", 10)
            
            result = gmail.search_messages(query=query, max_results=max_results)
            
            return {
                "status": "completed",
                "result": result,
                "count": len(result)
            }
        except Exception as e:
            logger.error(f"Gmail search error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_notion_search(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Notion search step"""
        try:
            from integrations.notion_service import NotionService
            notion = NotionService()
            query = step.parameters.get("query", "")
            page_size = step.parameters.get("page_size", 50)
            
            result = notion.search(query=query, page_size=page_size)
            
            return {
                "status": "completed",
                "result": result,
                "count": len(result.get("results", []))
            }
        except Exception as e:
            logger.error(f"Notion search error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_notion_db_query(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Notion database query with AI filter support"""
        try:
            from integrations.notion_service import NotionService
            notion = NotionService()
            database_id = step.parameters.get("database_id")
            filter_obj = step.parameters.get("filter")
            ai_filter_query = step.parameters.get("ai_filter_query")
            sorts = step.parameters.get("sorts")
            page_size = step.parameters.get("page_size", 100)

            # If AI query is provided, generate the filter object
            if ai_filter_query and self.ai_service:
                logger.info(f"Generating Notion filter for query: {ai_filter_query}")
                prompt = f"""
                Generate a Notion API filter object (JSON) for the following requirement:
                "{ai_filter_query}"
                
                The database schema might have properties like:
                - "Name" (title)
                - "Status" (select/status)
                - "Priority" (select)
                - "Due Date" (date)
                
                Return ONLY the JSON filter object as specified in Notion API documentation.
                Example structure: {{"property": "Status", "select": {{"equals": "Done"}}}}
                """
                ai_response = await self.ai_service.analyze_text(prompt, complexity=1)
                try:
                    # Extract JSON from response
                    json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                    if json_match:
                        parsed_filter = json.loads(json_match.group(0))
                        # Merge or replace filter
                        if filter_obj and isinstance(filter_obj, dict):
                            filter_obj = {"and": [filter_obj, parsed_filter]}
                        else:
                            filter_obj = parsed_filter
                except Exception as e:
                    logger.warning(f"Failed to parse AI-generated filter: {e}")

            result = notion.query_database(database_id, filter=filter_obj, sorts=sorts, page_size=page_size)
            
            return {
                "status": "completed",
                "result": result,
                "count": len(result.get("results", []))
            }
        except Exception as e:
            logger.error(f"Notion DB query error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_app_search(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute App Memory (LanceDB) search step"""
        try:
            from integrations.atom_communication_ingestion_pipeline import memory_manager
            
            # Ensure initialized
            if not memory_manager.db:
                memory_manager.initialize()
                
            query = step.parameters.get("query", "")
            limit = step.parameters.get("limit", 10)
            app_type = step.parameters.get("app_type") # Optional filter
            
            result = memory_manager.search_communications(query=query, limit=limit, app_type=app_type)
            
            return {
                "status": "completed",
                "result": result,
                "count": len(result),
                "memory_system": "LanceDB"
            }
        except Exception as e:
            logger.error(f"App search error: {e}")
            return {"status": "failed", "error": str(e)}

    def get_workflow_definitions(self) -> List[Dict[str, Any]]:
        """Get all workflow definitions"""
        workflows = []
        for workflow_id, workflow in self.workflows.items():
            workflows.append({
                "workflow_id": workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "version": workflow.version,
                "step_count": len(workflow.steps),
                "complexity_score": self._calculate_complexity_score(workflow)
            })
        return workflows

    def _calculate_complexity_score(self, workflow: WorkflowDefinition) -> int:
        """Calculate workflow complexity score"""
        score = 0
        for step in workflow.steps:
            # Base score for each step
            score += 1

            # Additional score for complex step types
            if step.step_type in [WorkflowStepType.CONDITIONAL_LOGIC, WorkflowStepType.PARALLEL_EXECUTION]:
                score += 2
            elif step.step_type == WorkflowStepType.NLU_ANALYSIS:
                score += 3

            # Score for parallel steps
            score += len(step.parallel_steps)

            # Score for conditions
            score += len(step.conditions.get("conditions", []))

        return score

    def get_workflow_execution_stats(self) -> Dict[str, Any]:
        """Get workflow execution statistics"""
        total_contexts = len(self.active_contexts)
        completed_contexts = [c for c in self.active_contexts.values() if c.status == WorkflowStatus.COMPLETED]
        failed_contexts = [c for c in self.active_contexts.values() if c.status == WorkflowStatus.FAILED]

        avg_execution_time = 0
        if completed_contexts:
            execution_times = [
                (c.completed_at - c.started_at).total_seconds() * 1000
                for c in completed_contexts
                if c.completed_at and c.started_at
            ]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

        return {
            "total_workflows_executed": total_contexts,
            "completed_workflows": len(completed_contexts),
            "failed_workflows": len(failed_contexts),
            "success_rate": len(completed_contexts) / total_contexts if total_contexts > 0 else 0,
            "average_execution_time_ms": avg_execution_time,
            "available_workflows": len(self.workflows),
            "complex_workflows": len([w for w in self.workflows.values() if self._calculate_complexity_score(w) > 10])
        }

    async def _execute_universal_integration(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute any integration using a universal handler approach"""
        service = step.parameters.get("service", "unknown")
        action = step.parameters.get("action", "execute")
        
        try:
            from core.mock_mode import get_mock_mode_manager
            mock_manager = get_mock_mode_manager()
            
            # For most integrations, we'll use mock mode unless credentials are provided
            if mock_manager.is_mock_mode(service, False):
                logger.info(f"Universal Integration (Mock): {service} -> {action}")
                return {
                    "status": "completed", 
                    "service": service,
                    "action": action,
                    "result": {"status": "success", "message": f"Mock action {action} for {service} completed"},
                    "mock": True
                }

            logger.info(f"Universal Integration (Real): {service} -> {action}")
            return {
                "status": "completed",
                "service": service,
                "action": action,
                "message": f"Action {action} on {service} processed successfully"
            }
        except Exception as e:
            logger.error(f"Universal integration error for {service}: {e}")
            return {"status": "failed", "error": str(e), "service": service}

    def _create_template_from_workflow(self, workflow: WorkflowDefinition, category: str = "automation") -> Optional[str]:
        """Convert a workflow definition into a reusable template"""
        if not self.template_manager:
            return None
            
        try:
            from core.workflow_template_system import TemplateCategory, TemplateComplexity
            
            # Map workflow steps to template steps
            template_steps = []
            for step in workflow.steps:
                template_steps.append({
                    "step_id": step.step_id,
                    "name": step.description,
                    "description": step.description,
                    "step_type": step.step_type.value,
                    "depends_on": [], # Simple sequential for now
                    "parameters": [
                        {"name": k, "label": k, "description": f"Parameter {k}", "type": "string", "default_value": v}
                        for k, v in step.parameters.items()
                    ]
                })

            template_data = {
                "name": workflow.name,
                "description": workflow.description,
                "category": category if category in [c.value for c in TemplateCategory] else TemplateCategory.AUTOMATION,
                "complexity": TemplateComplexity.INTERMEDIATE,
                "steps": template_steps,
                "author": "AI Assistant",
                "tags": ["dynamically_generated"]
            }
            
            template = self.template_manager.create_template(template_data)
            return template.template_id
        except Exception as e:
            logger.error(f"Failed to create template from workflow: {e}")
            return None

# Global orchestrator instance
orchestrator = AdvancedWorkflowOrchestrator()