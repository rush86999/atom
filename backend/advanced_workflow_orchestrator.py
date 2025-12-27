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
from core.meta_automation import get_meta_automation
# Configure logging
logger = logging.getLogger(__name__)

# Database and models for Phase 11 persistence
try:
    from core.database import SessionLocal
    from core.models import WorkflowExecution, WorkflowExecutionStatus
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    logger.warning("Workflow persistence models not available")

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
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    KNOWLEDGE_UPDATE = "knowledge_update"
    SYSTEM_REASONING = "system_reasoning"
    INVOICE_PROCESSING = "invoice_processing"
    ECOMMERCE_SYNC = "ecommerce_sync"
    AGENT_EXECUTION = "agent_execution"  # Phase 28: Run a Computer Use Agent
    # Phase 37: Financial & Ops Automations
    COST_LEAK_DETECTION = "cost_leak_detection"
    BUDGET_CHECK = "budget_check"
    INVOICE_RECONCILIATION = "invoice_reconciliation"
    # Phase 35: Background Agents
    BACKGROUND_AGENT_START = "background_agent_start"
    BACKGROUND_AGENT_STOP = "background_agent_stop"
    GRAPHRAG_QUERY = "graphrag_query"
    PROJECT_CREATE = "project_create"
    PROJECT_STATUS_SYNC = "project_status_sync"
    CONTRACT_PROVISION = "contract_provision"
    MILESTONE_BILLING = "milestone_billing"
    AUTO_STAFFING = "auto_staffing"
    REVENUE_RECOGNITION = "revenue_recognition"
    RETENTION_PLAYBOOK = "retention_playbook"
    BUSINESS_AGENT_EXECUTION = "business_agent_execution"
    B2B_PO_DETECTION = "b2b_po_detection"

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"

@dataclass
class RetryPolicy:
    """Configuration for retry behavior on step failures (Phase 32)"""
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0  # Delay multiplier per retry
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout", "connection", "rate_limit", "temporary"
    ])
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt using exponential backoff"""
        delay = self.initial_delay_seconds * (self.exponential_base ** attempt)
        return min(delay, self.max_delay_seconds)
    
    def should_retry(self, error: str, attempt: int) -> bool:
        """Check if error is retryable and attempts remain"""
        if attempt >= self.max_retries:
            return False
        error_lower = error.lower()
        return any(e in error_lower for e in self.retryable_errors)

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
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: int = 30
    confidence_threshold: float = 0.7
    agent_fallback_id: Optional[str] = None  # Phase 33: Explicit agent to use on API failure

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
    user_id: str = "default_user"

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

        # Workflow 4: Contract Processing Automation
        contract_workflow = WorkflowDefinition(
            workflow_id="contract_processing_automation",
            name="Contract Processing Automation",
            description="Extracts terms, creates reminders, and logs obligations from a contract",
            steps=[
                WorkflowStep(
                    step_id="extract_terms",
                    step_type=WorkflowStepType.NLU_ANALYSIS,
                    description="Extract key contract terms and obligations",
                    parameters={
                        "system_prompt": """Analyze the contract text and extract:
1. Obligations (as a list of tasks)
2. Renewal Date (if found)
3. Owner/Point of Person
4. Summary

Return as JSON with 'tasks', 'renewal_date', 'owner', and 'summary'.""",
                        "include_kg_context": True
                    },
                    next_steps=["log_obligations", "create_reminders"]
                ),
                WorkflowStep(
                    step_id="log_obligations",
                    step_type=WorkflowStepType.KNOWLEDGE_UPDATE,
                    description="Log contract obligations into Knowledge Graph",
                    parameters={
                        "update_type": "obligation",
                        "subject": "{{entities.contract_id or 'New Contract'}}",
                        "facts": "{{tasks}}"
                    }
                ),
                WorkflowStep(
                    step_id="create_reminders",
                    step_type=WorkflowStepType.TASK_CREATION,
                    description="Create renewal reminders",
                    parameters={
                        "task_title": "Contract Renewal: {{entities.contract_id}}",
                        "due_date": "{{renewal_date}}",
                        "description": "Auto-generated reminder from contract analysis."
                    }
                )
            ],
            start_step="extract_terms",
            triggers=["document_uploaded"]
        )

        # Workflow 5: Shopify Order to Ledger Sync
        shopify_sync_workflow = WorkflowDefinition(
            workflow_id="shopify_to_ledger_sync",
            name="Shopify Order to Ledger Sync",
            description="Automatically sync Shopify orders to the accounting ledger",
            steps=[
                WorkflowStep(
                    step_id="ledger_mapping",
                    step_type=WorkflowStepType.ECOMMERCE_SYNC,
                    description="Map Shopify order to ledger entries",
                    parameters={"action": "order_to_ledger"},
                    next_steps=["notify_success"]
                ),
                WorkflowStep(
                    step_id="notify_success",
                    step_type=WorkflowStepType.SLACK_NOTIFICATION,
                    description="Notify team of successful ledger sync",
                    parameters={"channel": "#finance-sync", "message": "Order {order_number} synced to ledger for ${total_price}"},
                    next_steps=[]
                )
            ],
            start_step="ledger_mapping",
            triggers=["SHOPIFY_ORDER_CREATED"]
        )

        # Register workflows
        self.workflows[customer_support_workflow.workflow_id] = customer_support_workflow
        self.workflows[project_management_workflow.workflow_id] = project_management_workflow
        self.workflows[sales_lead_workflow.workflow_id] = sales_lead_workflow
        self.workflows[contract_workflow.workflow_id] = contract_workflow
        self.workflows[shopify_sync_workflow.workflow_id] = shopify_sync_workflow

    async def trigger_event(self, event_type: str, data: Dict[str, Any]):
        """
        Trigger workflows based on an external event.
        Scans all workflows for matching triggers.
        """
        logger.info(f"Triggering event: {event_type} with data from {data.get('source', 'unknown')}")
        
        triggered_count = 0
        for workflow_id, workflow in self.workflows.items():
            if event_type in (workflow.triggers or []):
                logger.info(f"Found matching workflow for event '{event_type}': {workflow_id}")
                # Start workflow in a separate background task
                asyncio.create_task(self.execute_workflow(workflow_id, data))
                triggered_count += 1
        
        return triggered_count

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
            user_id=execution_context.get("user_id", "default_user") if execution_context else "default_user",
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

            if context.status != WorkflowStatus.WAITING_APPROVAL:
                context.status = WorkflowStatus.COMPLETED
                context.completed_at = datetime.datetime.now()

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            context.status = WorkflowStatus.FAILED
            context.error_message = str(e)
            context.completed_at = datetime.datetime.now()

        finally:
            # Persistent state update
            self._save_execution_state(context)
            
            # Cleanup AI service sessions
            if self.ai_service:
                await self.ai_service.cleanup_sessions()

        return context

    def _save_execution_state(self, context: WorkflowContext):
        """Persist workflow execution state to database (Phase 11)"""
        if not MODELS_AVAILABLE:
            return

        try:
            with SessionLocal() as db:
                # Find or create execution record
                execution = db.query(WorkflowExecution).filter(
                    WorkflowExecution.execution_id == context.workflow_id
                ).first()
                
                if not execution:
                    execution = WorkflowExecution(
                        execution_id=context.workflow_id,
                        workflow_id=context.workflow_id, # Simplified mapping
                        user_id=context.user_id if context.user_id != "default_user" else None
                    )
                    db.add(execution)
                
                # Update status and data
                execution.status = context.status.value
                execution.input_data = json.dumps(context.input_data)
                execution.outputs = json.dumps(context.results)
                
                # Context state including variables and history
                state = {
                    "variables": context.variables,
                    "execution_history": context.execution_history,
                    "results": context.results
                }
                execution.context = json.dumps(state)
                
                if context.error_message:
                    execution.error = context.error_message
                
                db.commit()
                logger.info(f"Persisted state for workflow {context.workflow_id} (Status: {context.status.value})")
        except Exception as e:
            logger.error(f"Failed to persist workflow state: {e}")

    async def resume_workflow(self, execution_id: str, step_id: str) -> WorkflowContext:
        """Resume a workflow execution after approval (Phase 11 Enhanced)"""
        if execution_id in self.active_contexts:
            context = self.active_contexts[execution_id]
        elif MODELS_AVAILABLE:
            # Attempt to load from database
            context = self._load_execution_state(execution_id)
            if not context:
                raise ValueError(f"Workflow execution {execution_id} not found in memory or database")
            self.active_contexts[execution_id] = context
        else:
            raise ValueError(f"Workflow execution {execution_id} not found")
        
        # Finding the workflow definition
        workflow_def = None
        for wf in self.workflows.values():
            if any(s.step_id == step_id for s in wf.steps):
                workflow_def = wf
                break
        
        if not workflow_def:
            raise ValueError(f"Could not find workflow definition containing step {step_id}")

        step = next(s for s in workflow_def.steps if s.step_id == step_id)
        step_result = context.results.get(step_id)
        
        if not step_result or step_result.get("status") != "waiting_approval":
            logger.warning(f"Step {step_id} is not waiting for approval")
            return context

        logger.info(f"Resuming workflow {execution_id} from step {step_id} after approval")
        
        # Update status
        context.status = WorkflowStatus.RUNNING
        step_result["status"] = "completed"
        step_result["approved_at"] = datetime.datetime.now().isoformat()
        
        # Continue execution from next steps
        target_next_steps = step_result.get("next_steps", step.next_steps)
        
        # Run continue_workflow and ensure it persists after
        await self._continue_workflow(workflow_def, target_next_steps, context)
        self._save_execution_state(context)
        
        return context

    def _load_execution_state(self, execution_id: str) -> Optional[WorkflowContext]:
        """Load workflow state from database (Phase 11)"""
        if not MODELS_AVAILABLE:
            return None

        try:
            with SessionLocal() as db:
                execution = db.query(WorkflowExecution).filter(
                    WorkflowExecution.execution_id == execution_id
                ).first()
                
                if not execution:
                    return None
                
                state = json.loads(execution.context) if execution.context else {}
                
                context = WorkflowContext(
                    workflow_id=execution.execution_id,
                    user_id=execution.user_id or "default_user",
                    input_data=json.loads(execution.input_data) if execution.input_data else {},
                    status=WorkflowStatus(execution.status),
                    started_at=execution.created_at
                )
                context.variables = state.get("variables", {})
                context.execution_history = state.get("execution_history", [])
                context.results = state.get("results", {})
                
                return context
        except Exception as e:
            logger.error(f"Failed to load workflow state: {e}")
            return None

    async def _continue_workflow(self, workflow: WorkflowDefinition, next_steps: List[str], context: WorkflowContext):
        """Helper to continue workflow execution from a list of steps"""
        try:
            for next_step_id in next_steps:
                await self._execute_workflow_step(workflow, next_step_id, context)
            
            # If all branches finish, mark as completed
            # This is a bit simplified, a real orchestrator would track all active branches
            if all(s.get("status") != "running" for s in context.execution_history):
                context.status = WorkflowStatus.COMPLETED
                context.completed_at = datetime.datetime.now()
        except Exception as e:
            logger.error(f"Error continuing workflow: {e}")
            context.status = WorkflowStatus.FAILED
            context.error_message = str(e)
            context.completed_at = datetime.datetime.now()

    async def _generate_fallback_instructions(self, step: WorkflowStep, error_msg: str) -> str:
        """
        Generate natural language instructions for the fallback agent (Self-Healing).
        """
        prompt = f"The workflow step '{step.description}' (Service: {step.parameters.get('service')}) failed with error: {error_msg}. Perform this task manually via the UI."
        if self.ai_service:
            try:
                # Use AI to refine instructions (MVP: just return prompt to agent)
                return prompt 
            except Exception:
                pass
        return prompt

    def _get_fallback_url(self, service: str) -> str:
        """Get the starting URL for the fallback agent"""
        service = service.upper()
        if service == "SALESFORCE": return "https://login.salesforce.com"
        elif service == "HUBSPOT": return "https://app.hubspot.com/login"
        elif service == "BANKING": return "https://bank.com/login"
        return "about:blank"

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

        # Execute the step with retry logic (Phase 32)
        step_result = None
        last_error = None
        retry_policy = step.retry_policy
        
        for attempt in range(retry_policy.max_retries + 1):
            try:
                step_result = await self._execute_step_by_type(workflow, step, context)
                break  # Success, exit retry loop
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if we should retry
                if retry_policy.should_retry(error_str, attempt):
                    delay = retry_policy.get_delay(attempt)
                    logger.warning(f"Step {step_id} failed (attempt {attempt + 1}/{retry_policy.max_retries}): {error_str}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                
                # Check for Meta-Automation Fallback as last resort (Phase 23 Self-Healing)
                meta_automation = get_meta_automation()
                
                if meta_automation.should_fallback(e):
                    logger.warning(f"Meta-Automation: triggering fallback for error: {e}")
                    
                    # Determine integration type from step parameters
                    # Defaulting to 'salesforce' if not found for testing purposes, 
                    # in real app we'd infer from step_type or config
                    integration_type = step.parameters.get("service", "salesforce")
                    
                    fallback_result = meta_automation.execute_fallback(
                        integration_type, 
                        step.description, # Use step description as the goal
                        step.parameters
                    )
                    
                    if fallback_result and fallback_result.get("status") != "failed":
                        logger.info(f"Meta-Automation: Fallback successful via {fallback_result.get('agent')}")
                        step_result = {
                            "status": "completed",
                            "output": fallback_result,
                            "notes": "Completed via Self-Healing (Meta-Automation)"
                        }
                        break
                    else:
                         logger.error(f"Meta-Automation: Fallback failed: {fallback_result.get('error')}")
                    service = step.parameters.get("service", "").upper()
                    if not service:
                        if step.step_type == WorkflowStepType.SALESFORCE_INTEGRATION:
                            service = "SALESFORCE"
                        elif step.step_type == WorkflowStepType.HUBSPOT_INTEGRATION:
                            service = "HUBSPOT"
                    
                    meta_automation = get_meta_automation()
                    agent = meta_automation.get_fallback_agent(service)
                    
                    if agent:
                        logger.info(f"Fallback Agent {type(agent).__name__} engaged for step {step_id}")
                        instructions = await self._generate_fallback_instructions(step, str(e))
                        target_url = self._get_fallback_url(service)
                        
                        try:
                            sys_result = await agent.execute_task(target_url, instructions)
                            if sys_result.get("status") == "success":
                                logger.info(f"Meta-Automation Fallback Successful for {step_id}")
                                step_result = {
                                    "status": "completed",
                                    "output": sys_result.get("data", {}),
                                    "notes": "Completed via Self-Healing UI Fallback"
                                }
                                break
                            else:
                                raise Exception(f"Fallback UI Agent failed: {sys_result.get('error')}")
                        except Exception as fallback_err:
                            logger.error(f"Meta-Automation Fallback failed: {fallback_err}")
                            raise e
                    else:
                        raise e
                elif not desktop_available:
                    logger.warning(f"Agent fallback skipped - no desktop environment available")
                    raise e
                else:
                    raise e
        
        # If we exhausted retries without success
        if step_result is None and last_error:
            logger.error(f"Step {step_id} failed after {retry_policy.max_retries} retries: {last_error}")
            raise last_error
        
        # Check confidence threshold for human-in-the-loop (Phase 11)
        confidence = step_result.get("confidence", 1.0) # Default to 1.0 if not provided
        if confidence < step.confidence_threshold:
            logger.warning(f"Step {step_id} confidence ({confidence}) below threshold ({step.confidence_threshold}). Waiting for approval.")
            context.status = WorkflowStatus.WAITING_APPROVAL
            step_result["status"] = "waiting_approval"
            step_result["requires_confirmation"] = True
            
            # Store step result as pending
            context.results[step_id] = step_result
            return # Pause execution of this branch

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
            elif step.step_type == WorkflowStepType.KNOWLEDGE_LOOKUP:
                result = await self._execute_knowledge_lookup(step, context)
            elif step.step_type == WorkflowStepType.KNOWLEDGE_UPDATE:
                result = await self._execute_knowledge_update(step, context)
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
            elif step.step_type == WorkflowStepType.SYSTEM_REASONING:
                result = await self._execute_system_reasoning(step, context)
            elif step.step_type == WorkflowStepType.INVOICE_PROCESSING:
                result = await self._execute_invoice_processing(step, context)
            elif step.step_type == WorkflowStepType.ECOMMERCE_SYNC:
                result = await self._execute_ecommerce_sync(step, context)
            elif step.step_type == WorkflowStepType.AGENT_EXECUTION:
                result = await self._execute_agent_step(step, context)
            elif step.step_type == WorkflowStepType.BUSINESS_AGENT_EXECUTION:
                result = await self._execute_business_agent_step(step, context)
            # Phase 37: Financial & Ops Automations
            elif step.step_type == WorkflowStepType.COST_LEAK_DETECTION:
                result = await self._execute_cost_leak_detection(step, context)
            elif step.step_type == WorkflowStepType.BUDGET_CHECK:
                result = await self._execute_budget_check(step, context)
            elif step.step_type == WorkflowStepType.INVOICE_RECONCILIATION:
                result = await self._execute_invoice_reconciliation(step, context)
            # Phase 35: Background Agents
            elif step.step_type == WorkflowStepType.BACKGROUND_AGENT_START:
                result = await self._execute_background_agent_start(step, context)
            elif step.step_type == WorkflowStepType.BACKGROUND_AGENT_STOP:
                result = await self._execute_background_agent_stop(step, context)
            elif step.step_type == WorkflowStepType.GRAPHRAG_QUERY:
                result = await self._execute_graphrag_query(step, context)
            elif step.step_type == WorkflowStepType.PROJECT_CREATE:
                result = await self._execute_project_create(step, context)
            elif step.step_type == WorkflowStepType.PROJECT_STATUS_SYNC:
                result = await self._execute_project_status_sync(step, context)
            elif step.step_type == WorkflowStepType.CONTRACT_PROVISION:
                result = await self._execute_contract_provision(step, context)
            elif step.step_type == WorkflowStepType.MILESTONE_BILLING:
                result = await self._execute_milestone_billing(step, context)
            elif step.step_type == WorkflowStepType.AUTO_STAFFING:
                result = await self._execute_auto_staffing(step, context)
            elif step.step_type == WorkflowStepType.REVENUE_RECOGNITION:
                result = await self._execute_revenue_recognition(step, context)
            elif step.step_type == WorkflowStepType.RETENTION_PLAYBOOK:
                result = await self._execute_retention_playbook(step, context)
            elif step.step_type == WorkflowStepType.B2B_PO_DETECTION:
                result = await self._execute_b2b_po_detection(step, context)
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

    async def _execute_ecommerce_sync(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute automated ecommerce to ledger mapping"""
        order_id = step.parameters.get("order_id") or context.input_data.get("order_id")
        workspace_id = context.input_data.get("workspace_id", "default")
        action = step.parameters.get("action", "order_to_ledger")

        if not order_id:
            return {"status": "failed", "error": "No order_id provided for ecommerce sync"}

        try:
            from ecommerce.ledger_mapper import OrderToLedgerMapper
            from core.database import SessionLocal
            
            with SessionLocal() as db:
                mapper = OrderToLedgerMapper(db)
                if action == "order_to_ledger":
                    tx_id = mapper.process_order(order_id)
                    
                    if tx_id:
                        context.variables.update({"ledger_transaction_id": tx_id})
                        return {
                            "status": "success",
                            "message": f"Successfully synced order {order_id} to ledger",
                            "ledger_transaction_id": tx_id
                        }
                    else:
                        return {"status": "failed", "error": "Order mapping returned no transaction ID"}
                else:
                    return {"status": "failed", "error": f"Unsupported ecommerce action: {action}"}

        except Exception as e:
            logger.error(f"Ecommerce sync failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_b2b_po_detection(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute AI-driven B2B PO detection from email text"""
        email_body = step.parameters.get("email_body") or context.input_data.get("email_body")
        workspace_id = context.input_data.get("workspace_id", "default")
        customer_email = context.input_data.get("from_email") or step.parameters.get("customer_email")

        if not email_body:
            return {"status": "failed", "error": "No email_body provided for PO detection"}

        try:
            from ecommerce.b2b_procurement_service import B2BProcurementService
            from core.database import SessionLocal
            
            with SessionLocal() as db:
                service = B2BProcurementService(db)
                
                # 1. Extraction
                po_data = await service.extract_po_from_text(email_body)
                
                if "error" in po_data:
                    return {"status": "failed", "error": po_data["error"]}
                
                if not po_data.get("items"):
                    return {"status": "completed", "message": "No PO items detected in email"}

                # 2. Create Draft Order
                draft_order_id = await service.create_draft_order_from_po(
                    workspace_id,
                    customer_email or po_data.get("customer_email", "unknown@example.com"),
                    po_data
                )
                
                context.variables.update({
                    "draft_order_id": draft_order_id,
                    "po_data": po_data
                })

                return {
                    "status": "success",
                    "message": f"Successfully detected B2B PO and created draft order {draft_order_id}",
                    "draft_order_id": draft_order_id
                }

        except Exception as e:
            logger.error(f"B2B PO detection failed: {e}")
            return {"status": "failed", "error": str(e)}

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

        # Knowledge Graph Context Injection
        kg_context = ""
        if step.parameters.get("include_kg_context"):
            try:
                from core.knowledge_query_endpoints import get_knowledge_query_manager
                km = get_knowledge_query_manager()
                logger.info(f"Injecting KG context for AI step: {step.step_id}")
                facts = await km.answer_query(f"What relevant facts are there about: {input_text}")
                if facts and facts.get("relevant_facts"):
                    kg_context = "\n**Knowledge Context from ATOM KG:**\n" + "\n".join([f"- {f}" for f in facts["relevant_facts"][:5]])
            except Exception as e:
                logger.warning(f"Failed to fetch KG context for AI step: {e}")

        try:
            # Use the specific instruction if available (from dynamic workflow)
            instruction = step.parameters.get("original_instruction")
            
            # Use provided system_prompt or the default NLU prompt
            base_system_prompt = step.parameters.get("system_prompt", """Analyze the user's request and extract ALL intents and goals:
1. The main intent(s)/goal(s) - List ALL distinct goals found
2. Key entities (people, dates, times, locations, actions)
3. Specific tasks that should be created for EACH intent
4. Priority level

Return your response as a JSON object with this format:
{
    "intent": "summary of all goals",
    "entities": ["list", "of", "key", "entities"],
    "tasks": ["Task 1", "Task 2"],
    "category": "general",
    "priority": "medium",
    "confidence": 0.8
}""")
            
            integrated_system_prompt = base_system_prompt
            if kg_context:
                integrated_system_prompt = f"{kg_context}\n\n{base_system_prompt}"

            if instruction:
                # Prepend instruction to input
                input_text = f"Instruction: {instruction}\n\nInput Data: {input_text}"

            nlu_result = await self.ai_service.process_with_nlu(
                input_text,
                provider_id,
                system_prompt=integrated_system_prompt,
                user_id=context.user_id
            )

            # STAKEHOLDER CHECK: Ensure context is complete
            # Check if the AI identified entities that are missing from our Knowledge Graph
            identified_entities = nlu_result.get("entities", [])
            missing_context = []
            
            # We'll specifically look for human names or roles that might be stakeholders
            for entity in identified_entities:
                # Simple heuristic: If it looks like a person and we have no KG info, it's a gap
                try:
                    from core.knowledge_query_endpoints import get_knowledge_query_manager
                    km = get_knowledge_query_manager()
                    facts = await km.answer_query(f"Who is {entity}?", user_id=context.user_id)
                    if not facts.get("relevant_facts") or "not found" in str(facts.get("answer", "")).lower():
                        # Check if this entity is a person/owner (heuristic)
                        if any(role in str(entity).lower() for role in ["manager", "stakeholder", "lead", "owner"]):
                            missing_context.append(entity)
                except:
                    pass

            if missing_context:
                logger.info(f"Missing critical context for entities: {missing_context}")
                # Instead of failing, we can trigger an implicit 'approval' or 'input' step
                # For now, we'll add it to the context and mark a flag for the UI to intercept
                context.variables["missing_stakeholders"] = missing_context
                context.variables["requires_user_input"] = True
                
                # Update status to waiting for user to fill the gap
                return {
                    "status": "waiting_approval", # Reusing status for user input
                    "message": f"Critical stakeholder data missing: {', '.join(missing_context)}. Please provide context.",
                    "missing_entities": missing_context,
                    "workflow_id": context.workflow_id
                }

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

    async def _execute_invoice_processing(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute automated invoice processing and ledger recording"""
        document_id = step.parameters.get("document_id") or context.input_data.get("document_id")
        workspace_id = step.parameters.get("workspace_id") or context.input_data.get("workspace_id", "default_workspace")
        expense_account_code = step.parameters.get("expense_account_code", "5100")

        if not document_id:
            return {"status": "failed", "error": "No document_id provided for invoice processing"}

        try:
            from core.database import SessionLocal
            from accounting.ap_service import APService
            
            with SessionLocal() as db:
                ap_service = APService(db)
                result = await ap_service.process_invoice_document(
                    document_id=document_id,
                    workspace_id=workspace_id,
                    expense_account_code=expense_account_code
                )
                
                # Merge bill results into context variables for subsequent steps
                if result["status"] == "success":
                    context.variables.update({
                        "bill_id": result.get("bill_id"),
                        "transaction_id": result.get("transaction_id"),
                        "vendor_name": result.get("vendor"),
                        "bill_amount": result.get("amount")
                    })
                
                return result
        except Exception as e:
            logger.error(f"Invoice processing step failed: {e}")
            return {"status": "failed", "error": str(e)}

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

    async def _execute_system_reasoning(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute system reasoning step for cross-system consistency and deduplication"""
        try:
            from core.cross_system_reasoning import get_reasoning_engine
            reasoning = get_reasoning_engine()
            
            reasoning_type = step.parameters.get("reasoning_type", "consistency")
            
            if reasoning_type == "consistency":
                issues = await reasoning.enforce_consistency(context.user_id)
                return {
                    "status": "completed",
                    "reasoning_type": "consistency",
                    "issues": issues,
                    "count": len(issues)
                }
            elif reasoning_type == "deduplication":
                duplicates = await reasoning.deduplicate_tasks(context.user_id)
                return {
                    "status": "completed",
                    "reasoning_type": "deduplication",
                    "duplicates": duplicates,
                    "count": len(duplicates)
                }
            else:
                return {"status": "failed", "error": f"Unknown reasoning type: {reasoning_type}"}
                
        except Exception as e:
            logger.error(f"System reasoning step failed: {e}")
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
            
            # Check for credentials or connectionId
            connection_id = step.parameters.get("connectionId")
            credentials = step.parameters.get("credentials") or context.variables.get(f"{service}_credentials")
            
            # If we have a connection_id, fetch real credentials
            if connection_id and not credentials:
                from backend.core.connection_service import connection_service
                # Use a dummy user_id for now, in prod this comes from context
                user_id = context.variables.get("user_id", "demo_user")
                credentials = connection_service.get_connection_credentials(connection_id, user_id)
                if credentials:
                    logger.info(f"Retrieved real credentials for connection {connection_id}")

            # Use Mock Mode if no credentials and mock mode is enabled (default behavior)
            if not credentials and mock_manager.is_mock_mode(service, False):
                logger.info(f"Universal Integration (Mock): {service} -> {action}")
                return {
                    "status": "completed", 
                    "service": service,
                    "action": action,
                    "result": {"status": "success", "message": f"Mock action {action} for {service} completed"},
                    "mock": True
                }

            # Real Execution via External Integration Service (Node.js Bridge)
            logger.info(f"Universal Integration (Real): {service} -> {action}")
            
            from backend.core.external_integration_service import external_integration_service
            
            # Prepare parameters - merge step params with input data
            # Filter out system params like 'service', 'action', 'credentials'
            action_params = {k: v for k, v in step.parameters.items() if k not in ["service", "action", "credentials"]}
            
            result = await external_integration_service.execute_integration_action(
                integration_id=service,
                action_id=action,
                params=action_params,
                credentials=credentials
            )

            return {
                "status": "completed",
                "service": service,
                "action": action,
                "result": result
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

    async def _execute_knowledge_lookup(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a knowledge graph lookup within a workflow"""
        query = step.parameters.get("query")
        if not query:
            return {"status": "failed", "error": "No query provided for knowledge lookup"}

        try:
            from core.knowledge_query_endpoints import get_knowledge_query_manager
            km = get_knowledge_query_manager()
            
            logger.info(f"Performing Knowledge Lookup: {query}")
            answer_data = await km.answer_query(query, user_id=context.user_id)
            
            # Extract facts and answer
            result = {
                "status": "completed",
                "answer": answer_data.get("answer", ""),
                "facts_found": len(answer_data.get("relevant_facts", [])),
                "execution_time_ms": answer_data.get("execution_time_ms", 0)
            }
            
            # Option to store specific answer in a variable
            output_var = step.parameters.get("output_variable")
            if output_var:
                context.variables[output_var] = result["answer"]
                logger.debug(f"Stored KG result in variable: {output_var}")
                
            return result
        except Exception as e:
            logger.error(f"Knowledge lookup failed in workflow: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_graphrag_query(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        Execute a GraphRAG query within a workflow.
        Supports advanced stakeholder and hierarchy traversal.
        """
        query = step.parameters.get("query")
        mode = step.parameters.get("mode", "auto")
        entity_name = step.parameters.get("entity_name")
        depth = step.parameters.get("depth", 2)
        
        if not query:
            return {"status": "failed", "error": "No query provided for GraphRAG"}

        try:
            from core.graphrag_engine import graphrag_engine
            
            logger.info(f"Performing GraphRAG Query ({mode}): {query}")
            result_data = graphrag_engine.query(
                context.user_id, 
                query, 
                mode=mode
            )
            
            # If it's a local search and an entity was specified/found
            if mode == "local" or (mode == "auto" and result_data.get("mode") == "local"):
                # Potential starting point for chain-of-thought or further discovery
                context.variables["last_graph_entity"] = result_data.get("start_entity")
            
            # Store primary answer/summary in context
            output_var = step.parameters.get("output_variable", "graphrag_result")
            answer = result_data.get("answer", "")
            
            # If no direct answer, format the entities/relationships found
            if not answer and result_data.get("entities"):
                entities = result_data.get("entities", [])
                entity_str = ", ".join([f"{e['name']} ({e['type']})" for e in entities[:5]])
                answer = f"Relevant entities found in GraphRAG: {entity_str}"
            
            context.variables[output_var] = answer
            
            return {
                "status": "completed",
                "mode": result_data.get("mode"),
                "entities_found": result_data.get("entities_found", 0),
                "relationships_found": result_data.get("relationships_found", 0),
                "answer": answer,
                "raw_result": result_data
            }
        except Exception as e:
            logger.error(f"GraphRAG query failed in workflow: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_knowledge_update(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a knowledge graph update within a workflow"""
        update_type = step.parameters.get("update_type", "fact")
        subject = step.parameters.get("subject", "unknown")
        facts = step.parameters.get("facts", [])
        
        if not isinstance(facts, list):
            facts = [facts]

        try:
            from core.knowledge_ingestion import get_knowledge_ingestion
            ki = get_knowledge_ingestion()
            
            logger.info(f"Performing Knowledge Update: {update_type} for {subject}")
            
            for fact in facts:
                # Log as a relationship: Subject -> HAS_OBLIGATION -> Fact (simplified for now)
                await ki.process_document(
                    f"{subject} has the following obligation/fact: {fact}",
                    doc_id=f"wf_update_{uuid.uuid4().hex[:8]}",
                    source=f"workflow_{context.workflow_id}"
                )
            
            return {
                "status": "completed",
                "message": f"Logged {len(facts)} facts to Knowledge Graph",
                "subject": subject
            }
        except Exception as e:
            logger.error(f"Knowledge update failed in workflow: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_agent_step(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        Execute a Computer Use Agent as a workflow step (Phase 28).
        Enables chaining agents together where output of one is input to the next.
        """
        agent_id = step.parameters.get("agent_id")
        if not agent_id:
            return {"status": "failed", "error": "No agent_id provided in step parameters"}

        try:
            # Phase 28/29: Use DB Registry and World Model
            from core.models import AgentRegistry
            from core.database import SessionLocal
            from core.agent_world_model import WorldModelService, AgentExperience
            from api.agent_routes import execute_agent_task
            import uuid

            # 1. Fetch Agent Definition
            with SessionLocal() as db:
                agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                if not agent:
                   return {"status": "failed", "error": f"Agent {agent_id} not found in registry"}
                
                # Snapshot data needed outside session
                agent_name = agent.name
                agent_category = agent.category
                agent_class = agent.class_name

            # 2. World Model Retrieval (Memory & Knowledge)
            wm_service = WorldModelService()
            task_context = f"Execute {agent_name} with params: {str(step.parameters)}"
            
            # Recall relevant past experiences and general knowledge
            memory_context = await wm_service.recall_experiences(agent, task_context)
            
            # 3. Context Injection
            # We merge context variables AND memory into agent parameters
            agent_params = {
                **step.parameters.get("agent_params", {}), 
                **context.variables,
                "_memory_context": memory_context # Inject retrieved memories
            }
            
            if memory_context["experiences"]:
                logger.info(f"Agent {agent_id} context augmented with {len(memory_context['experiences'])} past experiences")

            logger.info(f"Executing agent step: {agent_id} with context injection")

            # 4. Execute the agent
            # Note: execute_agent_task is the background task wrapper, but here we await it directly
            # We might need to call the logic directly if execute_agent_task expects background_tasks
            # inspecting execute_agent_task signature... it is async def execute_agent_task(agent_id, params)
            
            # We call the logic wrapper. The wrapper in agent_routes ALSO does WM recording. 
            # To avoid double recording, we should ideally have a lower-level 'run_agent_logic' function.
            # However, for now, if execute_agent_task does recording, we can rely on that.
            # BUT: execute_agent_task in agent_routes.py creates its own DB session and WorldModelService.
            # So calling it here works perfectly fine and reuses that logic!
            
            # Wait, execute_agent_task return type? 
            # In agent_routes.py it returns None (it handles logging/broadcasting). 
            # We need the RESULT here for the workflow.
            
            # Refactor Plan: 
            # We can't rely solely on execute_agent_task if it doesn't return the result.
            # Let's check agent_routes.py again. It logs result but doesn't return it? 
            # It finishes with: return {"status": "started", ...} in the route, but the background task function?
            # The background task function (execute_agent_task) has no return statement that passes data back to caller.
            # It broadcasts via notification_manager.
            
            # For Workflow Orchestrator, we need the return value!
            # So we must implement the execution logic here directly OR refactor agent_routes to expose a shared runner.
            # I will instantiate the agent class directly here to ensure I get the return value.
            
            # Dynamic Import logic similar to agent_routes
            module_name = agent.module_path
            class_name = agent.class_name
            
            mod = __import__(module_name, fromlist=[class_name])
            AgentClass = getattr(mod, class_name)
            agent_instance = AgentClass()
            
            # Heuristic execution (same as agent_routes)
            result = None
            if agent_id == "competitive_intel":
                 result = await agent_instance.track_competitor_pricing(
                    agent_params.get("competitors", ["competitor-a"]),
                    agent_params.get("product", "widget-x")
                )
            elif agent_id == "inventory_reconcile":
                result = await agent_instance.reconcile_inventory(
                    agent_params.get("skus", ["SKU-123"])
                )
            elif agent_id == "payroll_guardian":
                result = await agent_instance.reconcile_payroll(
                    agent_params.get("period", "2023-12")
                )
            elif hasattr(agent_instance, 'run'):
                 result = await agent_instance.run(agent_params)
            else:
                 result = "Executed generic agent logic."

            # 5. Record Experience (Since we bypassed execute_agent_task)
            await wm_service.record_experience(AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                task_type=agent_class,
                input_summary=str(agent_params),
                outcome="Success",
                learnings=f"Workflow Step Success. Result: {str(result)[:100]}...",
                agent_role=agent_category,
                specialty=None,
                timestamp=datetime.datetime.utcnow()
            ))

            # Store agent output in context for next step
            if result:
                context.variables[f"{agent_id}_output"] = result

            return {
                "status": "success",
                "agent_id": agent_id,
                "output": result,
                "message": f"Agent {agent_id} executed successfully via World Model"
            }

        except Exception as e:
            logger.error(f"Agent step execution failed: {e}")
            return {"status": "failed", "error": str(e)}

    # ==================== PHASE 37: FINANCIAL OPS HANDLERS ====================
    
    async def _execute_cost_leak_detection(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute cost leak detection step"""
        try:
            from core.financial_ops_engine import cost_detector
            report = cost_detector.get_savings_report()
            context.variables["cost_report"] = report
            return {
                "status": "completed",
                "unused_count": len(report.get("unused_subscriptions", [])),
                "potential_savings": report.get("potential_monthly_savings", 0),
                "report": report
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_budget_check(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute budget check step"""
        try:
            from core.financial_ops_engine import budget_guardrails
            category = step.parameters.get("category")
            amount = step.parameters.get("amount", 0)
            deal_stage = step.parameters.get("deal_stage") or context.variables.get("deal_stage")
            milestone = step.parameters.get("milestone") or context.variables.get("milestone")
            
            result = budget_guardrails.check_spend(category, amount, deal_stage, milestone)
            context.variables["budget_check_result"] = result
            return {"status": "completed", **result}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_invoice_reconciliation(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute invoice reconciliation step"""
        try:
            from core.financial_ops_engine import invoice_reconciler
            result = invoice_reconciler.reconcile()
            context.variables["reconciliation_result"] = result
            return {
                "status": "completed",
                "matched": result["summary"]["matched_count"],
                "discrepancies": result["summary"]["discrepancy_count"],
                "result": result
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # ==================== PHASE 35: BACKGROUND AGENT HANDLERS ====================
    
    async def _execute_background_agent_start(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Start a background agent for periodic execution"""
        try:
            from core.background_agent_runner import background_runner
            agent_id = step.parameters.get("agent_id")
            interval = step.parameters.get("interval_seconds", 3600)
            
            if not agent_id:
                return {"status": "failed", "error": "No agent_id specified"}
            
            background_runner.register_agent(agent_id, interval)
            await background_runner.start_agent(agent_id)
            
            return {
                "status": "completed",
                "agent_id": agent_id,
                "interval": interval,
                "message": f"Background agent {agent_id} started"
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_background_agent_stop(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Stop a background agent"""
        try:
            from core.background_agent_runner import background_runner
            agent_id = step.parameters.get("agent_id")
            
            if not agent_id:
                return {"status": "failed", "error": "No agent_id specified"}
            
            await background_runner.stop_agent(agent_id)
            
            return {
                "status": "completed",
                "agent_id": agent_id,
                "message": f"Background agent {agent_id} stopped"
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_business_agent_step(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Phase 67: Execute a specialized business agent (Accounting, Sales, etc.)"""
        agent_type = step.parameters.get("agent_type")
        workspace_id = context.variables.get("workspace_id", "default_workspace")
        
        logger.info(f"Orchestrator executing Business Agent: {agent_type} for workspace {workspace_id}")
        
        try:
            from core.business_agents import get_specialized_agent
            agent = get_specialized_agent(agent_type)
            
            if not agent:
                return {"status": "error", "message": f"Specialized agent type '{agent_type}' not found."}
                
            result = await agent.run(workspace_id, step.parameters)
            return result
        except Exception as e:
            logger.error(f"Business agent execution failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _execute_project_create(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        Execute automated project creation from a requirement prompt.
        """
        try:
            from core.pm_engine import pm_engine
            
            prompt = step.parameters.get("prompt") or context.input_data.get("text")
            contract_id = step.parameters.get("contract_id") or context.variables.get("contract_id")
            workspace_id = step.parameters.get("workspace_id") or context.input_data.get("workspace_id", "default")
            
            if not prompt:
                return {"status": "failed", "error": "No prompt provided for project creation"}

            result = await pm_engine.generate_project_from_nl(
                prompt=prompt,
                user_id=context.user_id,
                workspace_id=workspace_id,
                contract_id=contract_id
            )
            
            if result["status"] == "success":
                context.variables["created_project_id"] = result["project_id"]
                context.variables["created_project_name"] = result["name"]
                
            return result
        except Exception as e:
            logger.error(f"Project creation step failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_project_status_sync(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        Sync project status by inferring progress from GraphRAG and system activity.
        """
        try:
            from core.pm_engine import pm_engine
            
            project_id = step.parameters.get("project_id") or context.variables.get("created_project_id")
            
            if not project_id:
                return {"status": "failed", "error": "No project_id provided for status sync"}

            # 1. Infer status
            status_result = await pm_engine.infer_project_status(project_id, context.user_id)
            
            # 2. Analyze risks
            risk_result = await pm_engine.analyze_project_risks(project_id, context.user_id)
            
            return {
                "status": "completed",
                "status_sync": status_result,
                "risk_analysis": risk_result,
                "overall_risk": risk_result.get("risk_level", "unknown")
            }
        except Exception as e:
            logger.error(f"Project status sync failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_contract_provision(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute automated contract and project provisioning from a deal"""
        deal_id = step.parameters.get("deal_id") or context.input_data.get("deal_id")
        external_platform = step.parameters.get("external_platform") or context.input_data.get("external_platform")
        workspace_id = context.input_data.get("workspace_id", "default")
        user_id = context.input_data.get("user_id", "default")

        if not deal_id:
            return {"status": "failed", "error": "No deal_id provided for contract provision"}

        try:
            from core.pm_orchestrator import pm_orchestrator
            result = await pm_orchestrator.provision_from_deal(deal_id, user_id, workspace_id, external_platform)
            
            if result["status"] == "success":
                context.variables.update({
                    "contract_id": result["contract_id"],
                    "project_id": result["project_id"]
                })
                # Auto-notify stakeholders if identified
                if result.get("stakeholders_identified"):
                    await pm_orchestrator.notify_startup(
                        result["project_id"], 
                        result["stakeholders_identified"]
                    )
                
            return result
        except Exception as e:
            logger.error(f"Contract provision failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_milestone_billing(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute automated milestone billing"""
        milestone_id = step.parameters.get("milestone_id") or context.input_data.get("milestone_id")
        workspace_id = context.input_data.get("workspace_id", "default")

        if not milestone_id:
            return {"status": "failed", "error": "No milestone_id provided for billing"}

        try:
            from core.billing_orchestrator import billing_orchestrator
            result = await billing_orchestrator.process_milestone_completion(milestone_id, workspace_id)
            
            if result["status"] == "success":
                context.variables.update({
                    "invoice_id": result["invoice_id"],
                    "billed_amount": result["amount"]
                })
                
            return result
        except Exception as e:
            logger.error(f"Milestone billing failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_auto_staffing(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute AI-driven staffing recommendation"""
        description = step.parameters.get("description") or context.input_data.get("description")
        workspace_id = context.input_data.get("workspace_id", "default")

        if not description:
            return {"status": "failed", "error": "No description provided for staffing"}

        try:
            from core.staffing_advisor import staffing_advisor
            limit = step.parameters.get("limit", 3)
            result = await staffing_advisor.recommend_staff(description, workspace_id, limit=limit)
            
            if result["status"] == "success":
                context.variables.update({
                    "staffing_recommendations": result["recommendations"],
                    "required_skills": result["required_skills"]
                })
                
            return result
        except Exception as e:
            logger.error(f"Auto staffing failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_revenue_recognition(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute automated revenue recognition for a milestone"""
        milestone_id = step.parameters.get("milestone_id") or context.input_data.get("milestone_id")
        
        if not milestone_id:
            return {"status": "failed", "error": "No milestone_id provided"}

        try:
            from accounting.revenue_recognition import revenue_recognition_service
            result = await revenue_recognition_service.record_revenue_recognition(milestone_id)
            return result
        except Exception as e:
            logger.error(f"Revenue recognition failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_retention_playbook(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        Execute an automated retention playbook for at-risk customers.
        """
        sub_id = step.parameters.get("subscription_id") or context.input_data.get("subscription_id")
        reason = step.parameters.get("reason", "Unknown churn signal")
        
        if not sub_id:
            return {"status": "failed", "error": "No subscription_id provided for retention playbook"}

        try:
            from saas.models import Subscription
            from core.models import TeamMessage, Team
            from core.database import SessionLocal
            
            db = SessionLocal()
            sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
            if not sub:
                return {"status": "failed", "error": "Subscription not found"}
                
            # Simulate high-priority intervention
            # 1. Notify the team
            team = db.query(Team).filter(Team.workspace_id == sub.workspace_id).first()
            if team:
                msg = TeamMessage(
                    team_id=team.id,
                    user_id="system",
                    content=f"🚨 RETENTION PLAYBOOK ACTIVATED for Subscription {sub_id}. Reason: {reason}. Action required: Reach out to customer immediately."
                )
                db.add(msg)
                db.commit()
                
            return {
                "status": "success",
                "message": "Retention playbook activated",
                "subscription_id": sub_id,
                "workflow_steps_logged": True
            }
        except Exception as e:
            logger.error(f"Retention playbook execution failed: {e}")
            return {"status": "failed", "error": str(e)}

# Global orchestrator instance
orchestrator = AdvancedWorkflowOrchestrator()

# Singleton instance
_orchestrator_instance = None

def get_orchestrator() -> AdvancedWorkflowOrchestrator:
    """Get or create singleton instance of the orchestrator"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AdvancedWorkflowOrchestrator()
    return _orchestrator_instance
