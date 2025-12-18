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

    async def generate_dynamic_workflow(self, user_query: str) -> WorkflowDefinition:
        """
        Dynamically generate a workflow from a user query using high-reasoning AI.
        Breaks down the task into steps and assigns appropriate models based on complexity.
        """
        if not self.ai_service:
            raise ValueError("AI service not initialized")

        # 1. Get a high-reasoning provider for the planning phase
        byok_manager = get_byok_manager()
        try:
            # Try to get a level 4 (reasoning) provider, fallback to level 3 (high)
            planner_provider_id = byok_manager.get_optimal_provider("reasoning", min_reasoning_level=4)
            if not planner_provider_id:
                planner_provider_id = byok_manager.get_optimal_provider("analysis", min_reasoning_level=3)
            
            # If still no provider, use default
            if not planner_provider_id:
                planner_provider_id = "openai" # Default fallback
                
            planner_provider = byok_manager.providers.get(planner_provider_id)
            logger.info(f"Using {planner_provider.name if planner_provider else planner_provider_id} for task planning")
            
        except Exception as e:
            logger.warning(f"Failed to select optimal planner: {e}")
            planner_provider_id = "openai"

        # 2. Break down the task
        steps_data = await self.ai_service.break_down_task(user_query, provider=planner_provider_id)
        
        # 3. Convert to WorkflowDefinition
        workflow_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        workflow_steps = []
        
        for i, step_data in enumerate(steps_data):
            step_id = step_data.get("step_id", f"step_{i+1}")
            complexity = step_data.get("complexity", 2)
            description = step_data.get("description", "Process step")
            
            # Map step type to WorkflowStepType (simplified)
            step_type_str = step_data.get("step_type", "general").lower()
            if "email" in step_type_str:
                wf_step_type = WorkflowStepType.EMAIL_SEND
            elif "slack" in step_type_str:
                wf_step_type = WorkflowStepType.SLACK_NOTIFICATION
            elif "api" in step_type_str:
                wf_step_type = WorkflowStepType.API_CALL
            else:
                wf_step_type = WorkflowStepType.NLU_ANALYSIS
            
            # Determine next steps
            next_steps = []
            if i < len(steps_data) - 1:
                next_steps = [steps_data[i+1].get("step_id", f"step_{i+2}")]
                
            workflow_steps.append(WorkflowStep(
                step_id=step_id,
                step_type=wf_step_type,
                description=description,
                parameters={
                    "complexity": complexity, # Store complexity for execution
                    "original_instruction": description
                },
                next_steps=next_steps
            ))
            
        workflow = WorkflowDefinition(
            workflow_id=workflow_id,
            name=f"Dynamic Workflow: {user_query[:30]}...",
            description=f"Generated from query: {user_query}",
            steps=workflow_steps,
            start_step=workflow_steps[0].step_id if workflow_steps else "end"
        )
        
        # Cache the workflow
        self.workflows[workflow_id] = workflow
        
        return workflow

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
        step_result = await self._execute_step_by_type(step, context)

        # Store step result
        context.results[step_id] = step_result
        context.execution_history.append({
            "step_id": step_id,
            "step_type": step.step_type.value,
            "timestamp": datetime.datetime.now().isoformat(),
            "result": step_result,
            "execution_time_ms": step_result.get("execution_time_ms", 0)
        })

        # Determine next steps
        if step.parallel_steps:
            # Execute parallel steps concurrently
            parallel_tasks = [
                self._execute_workflow_step(workflow, next_step, context)
                for next_step in step.parallel_steps
            ]
            await asyncio.gather(*parallel_tasks, return_exceptions=True)

            # After parallel execution, continue to sequential next steps
            for next_step in step.next_steps:
                await self._execute_workflow_step(workflow, next_step, context)
        else:
            # Sequential execution
            for next_step in step.next_steps:
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
        """Evaluate a single condition"""
        # Simple string-based evaluation (can be enhanced with proper expression parser)
        try:
            # Replace variables in condition
            for key, value in context.variables.items():
                condition = condition.replace(key, str(value))

            # Add some basic evaluations
            if "priority == 'urgent'" in condition:
                return context.variables.get("priority") == "urgent"
            elif "score >= 80" in condition:
                return context.variables.get("score", 0) >= 80
            elif "category == 'technical'" in condition:
                return context.variables.get("category") == "technical"

            return True
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
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

    async def _execute_step_by_type(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute a step based on its type"""
        start_time = time.time()
        
        # Resolve variables in parameters before execution
        step.parameters = self._resolve_variables(step.parameters, context)

        try:
            if step.step_type == WorkflowStepType.NLU_ANALYSIS:
                result = await self._execute_nlu_analysis(step, context)
            elif step.step_type == WorkflowStepType.CONDITIONAL_LOGIC:
                result = await self._execute_conditional_logic(step, context)
            elif step.step_type == WorkflowStepType.EMAIL_SEND:
                result = await self._execute_email_send(step, context)
            elif step.step_type == WorkflowStepType.SLACK_NOTIFICATION:
                result = await self._execute_slack_notification(step, context)
            elif step.step_type == WorkflowStepType.ASANA_INTEGRATION:
                result = await self._execute_asana_integration(step, context)
            elif step.step_type == WorkflowStepType.PARALLEL_EXECUTION:
                result = await self._execute_parallel_execution(step, context)
            elif step.step_type == WorkflowStepType.DELAY:
                result = await self._execute_delay(step, context)
            elif step.step_type == WorkflowStepType.API_CALL:
                result = await self._execute_api_call(step, context)
            elif step.step_type == WorkflowStepType.NOTION_INTEGRATION:
                result = await self._execute_notion_integration(step, context)
            elif step.step_type == WorkflowStepType.GMAIL_FETCH:
                result = await self._execute_gmail_fetch(step, context)
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
                "tasks": nlu_result.get("tasks", [])
            })

            return {
                "status": "completed",
                "nlu_result": nlu_result,
                "provider_used": provider_id,
                "complexity_level": complexity,
                "intent": nlu_result.get("intent"),
                "entities": nlu_result.get("entities", []),
                "confidence": nlu_result.get("confidence", 0.8),
                "tasks": nlu_result.get("tasks", [])
            }

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _execute_conditional_logic(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute conditional logic step"""
        conditions = step.parameters.get("conditions", [])

        for condition in conditions:
            if_condition = condition.get("if")
            then_steps = condition.get("then", [])

            if await self._evaluate_condition(if_condition, context):
                # Set next steps based on condition
                context.variables["conditional_next_steps"] = then_steps
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

        # Simulate email sending (in real implementation, integrate with email service)
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "status": "completed",
            "template": template,
            "recipient": recipient,
            "sent_at": datetime.datetime.now().isoformat()
        }

    async def _execute_slack_notification(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Slack notification step"""
        channel = step.parameters.get("channel", "#general")
        message = step.parameters.get("message", context.input_data.get("text", ""))

        # Simulate Slack notification (in real implementation, integrate with Slack API)
        await asyncio.sleep(0.1)  # Simulate API call

        return {
            "status": "completed",
            "channel": channel,
            "message": message,
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
        delay_hours = step.parameters.get("delay_hours", 0)
        delay_seconds = step.parameters.get("delay_seconds", delay_hours * 3600)

        if delay_seconds > 0:
            await asyncio.sleep(min(delay_seconds, 5))  # Cap delay for demo purposes

        return {
            "status": "completed",
            "delayed_seconds": delay_seconds,
            "actual_delay": min(delay_seconds, 5)
        }

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
                    properties = {
                        "Name": {"title": [{"text": {"content": title}}]}
                    }
                    
                    # Format content as blocks if it looks like a list
                    content_blocks = []
                    
                    # Parse list-like string back to list if needed
                    tasks_to_format = []
                    if isinstance(content, list):
                        tasks_to_format = content
                    elif isinstance(content, str):
                        if content.strip().startswith('[') and content.strip().endswith(']'):
                            try:
                                import ast
                                tasks_to_format = ast.literal_eval(content.strip())
                            except:
                                tasks_to_format = [content]
                        else:
                            tasks_to_format = [l.strip() for l in content.split('\n') if l.strip()]

                    if tasks_to_format and isinstance(tasks_to_format, list):
                        content_blocks.append(notion.create_heading_block("Action Items", level=2))
                        for item in tasks_to_format:
                            # Remove "Task X: " prefix if present
                            clean_item = str(item)
                            import re
                            clean_item = re.sub(r'^Task\s+\d+:\s*', '', clean_item)
                            content_blocks.append(notion.create_todo_block(clean_item))
                    else:
                        content_blocks.append(notion.create_text_block(str(content)))
                    
                    result = notion.create_page_in_database(
                        database_id=database_id,
                        properties=properties,
                        content_blocks=content_blocks
                    )
                else:
                    parent = step.parameters.get("parent")
                    properties = {
                        "title": [{"text": {"content": title}}]
                    }
                    result = notion.create_page(parent, properties)
                
                if result and content:
                    # Add content as block children
                    page_id = result.get("id")
                    if page_id:
                        blocks = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": content}}]}}]
                        notion.append_block_children(page_id, blocks)
                
                return {
                    "status": "completed",
                    "notion_result": result,
                    "action": action
                }
            else:
                return {"status": "failed", "error": f"Unsupported Notion action: {action}"}
        except Exception as e:
            logger.error(f"Notion integration error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_gmail_fetch(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """Execute Gmail fetch step"""
        try:
            from integrations.gmail_service import GmailService
            gmail = GmailService()
            
            query = step.parameters.get("query", "is:unread")
            max_results = step.parameters.get("max_results", 5)
            
            # get_messages already returns parsed messages
            parsed_messages = gmail.get_messages(query=query, max_results=max_results)
            
            # get_messages already returns parsed messages
            parsed_messages = gmail.get_messages(query=query, max_results=max_results)
            
            return {
                "status": "completed",
                "messages": parsed_messages,
                "count": len(parsed_messages)
            }
        except Exception as e:
            logger.error(f"Gmail fetch error: {e}")
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

# Global orchestrator instance
orchestrator = AdvancedWorkflowOrchestrator()