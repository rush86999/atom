#!/usr/bin/env python3
"""
Enhance Workflow Engine with Advanced Features

This script enhances the existing workflow engine with:
- Advanced conditional logic support
- Parallel execution and synchronization
- Workflow templates and reusable components
- Versioning and rollback capabilities
- Error recovery and retry policies
- Performance optimization
"""

import os
import sys
import logging
import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class WorkflowExecutionStatus(Enum):
    """Workflow execution status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    PAUSED = "paused"


class StepExecutionStatus(Enum):
    """Step execution status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ConditionalLogicOperator(Enum):
    """Conditional logic operators"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    AND = "and"
    OR = "or"
    REGEX = "regex"


class ParallelExecutionMode(Enum):
    """Parallel execution modes"""
    ALL = "all"
    ANY = "any"
    FIRST_SUCCESS = "first_success"
    DELAYED = "delayed"


@dataclass
class WorkflowStep:
    """Enhanced workflow step with advanced features"""
    id: str
    service: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    conditional: bool = False
    sequence_order: int = 1
    depends_on: List[str] = field(default_factory=list)
    parallel: bool = False
    parallel_group: Optional[str] = None
    parallel_mode: ParallelExecutionMode = ParallelExecutionMode.ALL
    timeout: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    status: StepExecutionStatus = StepExecutionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None


@dataclass
class ConditionalRule:
    """Conditional rule for workflow logic"""
    id: str
    name: str
    operator: ConditionalLogicOperator
    left_operand: str
    right_operand: Any
    conditions: List['ConditionalRule'] = field(default_factory=list)
    description: str = ""


@dataclass
class WorkflowTemplate:
    """Reusable workflow template"""
    id: str
    name: str
    description: str
    category: str
    steps: List[WorkflowStep]
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"
    author: str = "system"


@dataclass
class WorkflowExecution:
    """Workflow execution instance"""
    id: str
    workflow_id: str
    template_id: Optional[str] = None
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING
    steps: List[WorkflowStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    parallel_groups: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    max_delay: float = 60.0
    retry_on_exceptions: List[str] = field(default_factory=list)
    retry_on_status_codes: List[int] = field(default_factory=list)


class EnhancedWorkflowEngine:
    """Enhanced workflow engine with advanced capabilities"""
    
    def __init__(self):
        self.workflow_registry = {}
        self.execution_registry = {}
        self.template_registry = {}
        self.version_history = {}
        self.active_executions = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.conditional_evaluator = ConditionalEvaluator()
        self.parallel_executor = ParallelExecutionManager()
        self.retry_manager = RetryManager()
        self.performance_monitor = WorkflowPerformanceMonitor()
        
        # Initialize built-in templates
        self._initialize_built_in_templates()
        
    def _initialize_built_in_templates(self):
        """Initialize built-in workflow templates"""
        
        # Email automation template
        email_template = WorkflowTemplate(
            id="email_automation",
            name="Email Automation Workflow",
            description="Automated email processing with conditional logic",
            category="communication",
            steps=[
                WorkflowStep(
                    id="check_inbox",
                    service="gmail",
                    action="check_inbox",
                    parameters={"unread_only": True},
                    description="Check for unread emails"
                ),
                WorkflowStep(
                    id="categorize_emails",
                    service="gmail",
                    action="categorize_emails",
                    parameters={"auto_categorize": True},
                    description="Categorize emails based on content",
                    depends_on=["check_inbox"]
                ),
                WorkflowStep(
                    id="send_responses",
                    service="gmail",
                    action="send_auto_responses",
                    parameters={"respond_to_urgent": True},
                    description="Send automatic responses to urgent emails",
                    depends_on=["categorize_emails"],
                    conditional=True
                )
            ],
            tags=["email", "automation", "gmail"],
            version="1.0.0"
        )
        
        # Task management template
        task_template = WorkflowTemplate(
            id="task_management",
            name="Cross-Platform Task Management",
            description="Sync tasks across multiple platforms",
            category="productivity",
            steps=[
                WorkflowStep(
                    id="get_asana_tasks",
                    service="asana",
                    action="get_tasks",
                    parameters={"project_id": "all"},
                    description="Get all Asana tasks"
                ),
                WorkflowStep(
                    id="get_trello_cards",
                    service="trello",
                    action="get_cards",
                    parameters={"board_id": "all"},
                    description="Get all Trello cards",
                    parallel_group="task_sync"
                ),
                WorkflowStep(
                    id="get_notion_tasks",
                    service="notion",
                    action="get_tasks",
                    parameters={"database_id": "all"},
                    description="Get all Notion tasks",
                    parallel_group="task_sync"
                ),
                WorkflowStep(
                    id="sync_tasks",
                    service="workflow_engine",
                    action="sync_cross_platform",
                    parameters={"sync_direction": "bidirectional"},
                    description="Sync tasks across platforms",
                    depends_on=["get_asana_tasks", "get_trello_cards", "get_notion_tasks"]
                )
            ],
            tags=["task", "sync", "asana", "trello", "notion"],
            version="1.0.0"
        )
        
        # Meeting automation template
        meeting_template = WorkflowTemplate(
            id="meeting_automation",
            name="Meeting Automation Workflow",
            description="Automated meeting scheduling and follow-up",
            category="calendar",
            steps=[
                WorkflowStep(
                    id="check_calendar",
                    service="google_calendar",
                    action="check_availability",
                    parameters={"duration": 60, "attendees": "team"},
                    description="Check team availability"
                ),
                WorkflowStep(
                    id="schedule_meeting",
                    service="google_calendar",
                    action="create_event",
                    parameters={"auto_schedule": True},
                    description="Schedule meeting if available",
                    depends_on=["check_calendar"],
                    conditional=True
                ),
                WorkflowStep(
                    id="send_invitation",
                    service="gmail",
                    action="send_invitation",
                    parameters={"template": "meeting_invite"},
                    description="Send meeting invitation",
                    depends_on=["schedule_meeting"],
                    parallel=True
                ),
                WorkflowStep(
                    id="set_reminder",
                    service="workflow_engine",
                    action="set_reminder",
                    parameters={"remind_before": 15},
                    description="Set meeting reminder",
                    depends_on=["schedule_meeting"],
                    parallel=True,
                    parallel_group="meeting_setup"
                )
            ],
            tags=["meeting", "calendar", "automation"],
            version="1.0.0"
        )
        
        # File processing template
        file_template = WorkflowTemplate(
            id="file_processing",
            name="File Processing Pipeline",
            description="Automated file processing and organization",
            category="files",
            steps=[
                WorkflowStep(
                    id="scan_new_files",
                    service="google_drive",
                    action="scan_new_files",
                    parameters={"file_types": ["pdf", "doc", "xls"]},
                    description="Scan for new files"
                ),
                WorkflowStep(
                    id="categorize_files",
                    service="workflow_engine",
                    action="categorize_files",
                    parameters={"ai_categorization": True},
                    description="Categorize files using AI",
                    depends_on=["scan_new_files"]
                ),
                WorkflowStep(
                    id="extract_text",
                    service="workflow_engine",
                    action="extract_text_from_files",
                    parameters={"ocr_enabled": True},
                    description="Extract text from files",
                    depends_on=["categorize_files"],
                    parallel=True
                ),
                WorkflowStep(
                    id="organize_folders",
                    service="google_drive",
                    action="organize_files",
                    parameters={"auto_organize": True},
                    description="Organize files into folders",
                    depends_on=["categorize_files"],
                    parallel=True
                )
            ],
            tags=["files", "processing", "organization"],
            version="1.0.0"
        )
        
        # Register templates
        self.template_registry[email_template.id] = email_template
        self.template_registry[task_template.id] = task_template
        self.template_registry[meeting_template.id] = meeting_template
        self.template_registry[file_template.id] = file_template
        
        logger.info(f"Initialized {len(self.template_registry)} built-in workflow templates")
    
    def create_workflow_from_template(
        self, 
        template_id: str, 
        parameters: Dict[str, Any],
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Create a new workflow from template"""
        try:
            if template_id not in self.template_registry:
                return {"success": False, "error": f"Template {template_id} not found"}
            
            template = self.template_registry[template_id]
            workflow_id = str(uuid.uuid4())
            
            # Clone template steps with parameter substitution
            steps = []
            for step in template.steps:
                new_step = WorkflowStep(
                    id=str(uuid.uuid4()),
                    service=step.service,
                    action=step.action,
                    parameters=self._substitute_parameters(step.parameters, parameters),
                    description=step.description,
                    conditional=step.conditional,
                    sequence_order=step.sequence_order,
                    depends_on=step.depends_on.copy(),
                    parallel=step.parallel,
                    parallel_group=step.parallel_group,
                    parallel_mode=step.parallel_mode,
                    timeout=step.timeout,
                    retry_policy=step.retry_policy
                )
                steps.append(new_step)
            
            # Create workflow
            workflow = {
                "id": workflow_id,
                "template_id": template_id,
                "name": f"{template.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "description": f"Created from template: {template.description}",
                "category": template.category,
                "steps": steps,
                "parameters": parameters,
                "template_version": template.version,
                "created_by": user_id,
                "created_at": datetime.now().isoformat(),
                "tags": template.tags.copy()
            }
            
            self.workflow_registry[workflow_id] = workflow
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "workflow": workflow,
                "template": {
                    "id": template.id,
                    "name": template.name,
                    "version": template.version
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating workflow from template: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _substitute_parameters(
        self, 
        step_parameters: Dict[str, Any], 
        template_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Substitute template parameters in step parameters"""
        substituted = {}
        
        for key, value in step_parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                param_name = value[2:-1]
                substituted[key] = template_parameters.get(param_name, value)
            else:
                substituted[key] = value
        
        return substituted
    
    def execute_advanced_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any] = None,
        execution_options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute workflow with advanced features"""
        try:
            if workflow_id not in self.workflow_registry:
                return {"success": False, "error": f"Workflow {workflow_id} not found"}
            
            workflow = self.workflow_registry[workflow_id]
            execution_id = str(uuid.uuid4())
            
            # Create execution instance
            execution = WorkflowExecution(
                id=execution_id,
                workflow_id=workflow_id,
                template_id=workflow.get("template_id"),
                steps=[self._clone_step(step) for step in workflow["steps"]],
                context=input_data or {},
                input_data=input_data or {}
            )
            
            # Register execution
            self.execution_registry[execution_id] = execution
            self.active_executions[execution_id] = execution
            
            # Start execution in background
            future = self.executor.submit(self._execute_workflow_advanced, execution)
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": "started",
                "workflow_id": workflow_id,
                "message": "Workflow execution started with advanced features"
            }
            
        except Exception as e:
            logger.error(f"Error executing advanced workflow: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _clone_step(self, step: WorkflowStep) -> WorkflowStep:
        """Clone a workflow step"""
        return WorkflowStep(
            id=str(uuid.uuid4()),
            service=step.service,
            action=step.action,
            parameters=step.parameters.copy(),
            description=step.description,
            conditional=step.conditional,
            sequence_order=step.sequence_order,
            depends_on=step.depends_on.copy(),
            parallel=step.parallel,
            parallel_group=step.parallel_group,
            parallel_mode=step.parallel_mode,
            timeout=step.timeout,
            retry_policy=step.retry_policy
        )
    
    def _execute_workflow_advanced(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Execute workflow with advanced features"""
        try:
            execution.status = WorkflowExecutionStatus.RUNNING
            execution.started_at = datetime.now()
            
            # Initialize parallel groups
            self._initialize_parallel_groups(execution)
            
            # Execute steps with advanced logic
            while self._has_pending_steps(execution):
                # Find ready steps
                ready_steps = self._get_ready_steps(execution)
                
                if not ready_steps:
                    # Check for deadlock
                    if self._is_deadlocked(execution):
                        execution.status = WorkflowExecutionStatus.FAILED
                        execution.error = "Workflow deadlocked - circular dependencies detected"
                        break
                    # Wait for parallel steps to complete
                    await asyncio.sleep(0.1)
                    continue
                
                # Execute ready steps
                await self._execute_ready_steps(execution, ready_steps)
            
            # Finalize execution
            execution.completed_at = datetime.now()
            execution.execution_time = (execution.completed_at - execution.started_at).total_seconds()
            
            # Determine final status
            failed_steps = [s for s in execution.steps if s.status == StepExecutionStatus.FAILED]
            if failed_steps:
                execution.status = WorkflowExecutionStatus.FAILED
                execution.error = f"{len(failed_steps)} steps failed"
            else:
                execution.status = WorkflowExecutionStatus.COMPLETED
                execution.output_data = self._collect_execution_output(execution)
            
            # Remove from active executions
            if execution.id in self.active_executions:
                del self.active_executions[execution.id]
            
            return {
                "success": execution.status == WorkflowExecutionStatus.COMPLETED,
                "execution_id": execution.id,
                "status": execution.status.value,
                "execution_time": execution.execution_time,
                "completed_steps": len([s for s in execution.steps if s.status == StepExecutionStatus.COMPLETED]),
                "failed_steps": len([s for s in execution.steps if s.status == StepExecutionStatus.FAILED]),
                "total_steps": len(execution.steps)
            }
            
        except Exception as e:
            logger.error(f"Error in advanced workflow execution: {str(e)}")
            execution.status = WorkflowExecutionStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()
            return {"success": False, "error": str(e)}
    
    def _initialize_parallel_groups(self, execution: WorkflowExecution):
        """Initialize parallel execution groups"""
        execution.parallel_groups = {}
        
        for step in execution.steps:
            if step.parallel_group:
                if step.parallel_group not in execution.parallel_groups:
                    execution.parallel_groups[step.parallel_group] = []
                execution.parallel_groups[step.parallel_group].append(step.id)
    
    def _has_pending_steps(self, execution: WorkflowExecution) -> bool:
        """Check if execution has pending steps"""
        return any(s.status == StepExecutionStatus.PENDING for s in execution.steps)
    
    def _get_ready_steps(self, execution: WorkflowExecution) -> List[WorkflowStep]:
        """Get steps that are ready for execution"""
        ready_steps = []
        
        for step in execution.steps:
            if step.status != StepExecutionStatus.PENDING:
                continue
            
            # Check if dependencies are satisfied
            dependencies_satisfied = True
            for dep_id in step.depends_on:
                dep_step = self._find_step_by_id(execution, dep_id)
                if not dep_step or dep_step.status != StepExecutionStatus.COMPLETED:
                    dependencies_satisfied = False
                    break
            
            if dependencies_satisfied:
                ready_steps.append(step)
        
        return ready_steps
    
    def _find_step_by_id(self, execution: WorkflowExecution, step_id: str) -> Optional[WorkflowStep]:
        """Find step by ID"""
        for step in execution.steps:
            if step.id == step_id:
                return step
        return None
    
    def _is_deadlocked(self, execution: WorkflowExecution) -> bool:
        """Check if execution is deadlocked"""
        pending_steps = [s for s in execution.steps if s.status == StepExecutionStatus.PENDING]
        
        for step in pending_steps:
            dependencies_met = True
            for dep_id in step.depends_on:
                dep_step = self._find_step_by_id(execution, dep_id)
                if not dep_step or dep_step.status != StepExecutionStatus.COMPLETED:
                    dependencies_met = False
                    break
            
            if dependencies_met:
                return False  # At least one step can proceed
        
        return True  # No pending step can proceed - deadlock
    
    async def _execute_ready_steps(
        self, 
        execution: WorkflowExecution, 
        ready_steps: List[WorkflowStep]
    ):
        """Execute ready steps with parallel support"""
        # Group steps by parallel execution
        parallel_groups = {}
        sequential_steps = []
        
        for step in ready_steps:
            if step.parallel:
                group = step.parallel_group or "default_parallel"
                if group not in parallel_groups:
                    parallel_groups[group] = []
                parallel_groups[group].append(step)
            else:
                sequential_steps.append(step)
        
        # Execute sequential steps
        for step in sequential_steps:
            await self._execute_single_step(execution, step)
        
        # Execute parallel groups
        for group, steps in parallel_groups.items():
            await self._execute_parallel_group(execution, steps)
    
    async def _execute_single_step(
        self, 
        execution: WorkflowExecution, 
        step: WorkflowStep
    ):
        """Execute a single step with retry logic"""
        step.status = StepExecutionStatus.RUNNING
        step.start_time = datetime.now()
        
        try:
            # Apply conditional logic
            if step.conditional and not self._evaluate_conditions(step, execution):
                step.status = StepExecutionStatus.SKIPPED
                return
            
            # Execute with retry policy
            result = await self.retry_manager.execute_with_retry(
                lambda: self._execute_step_action(step, execution),
                step.retry_policy
            )
            
            step.result = result
            step.status = StepExecutionStatus.COMPLETED
            
        except Exception as e:
            step.error = str(e)
            step.status = StepExecutionStatus.FAILED
            logger.error(f"Step {step.id} failed: {str(e)}")
        
        finally:
            step.end_time = datetime.now()
            if step.start_time:
                step.execution_time = (step.end_time - step.start_time).total_seconds()
    
    async def _execute_parallel_group(
        self, 
        execution: WorkflowExecution, 
        steps: List[WorkflowStep]
    ):
        """Execute steps in parallel"""
        if not steps:
            return
        
        # Determine execution mode based on first step
        mode = steps[0].parallel_mode
        
        if mode == ParallelExecutionMode.ALL:
            # Execute all steps
            tasks = [self._execute_single_step(execution, step) for step in steps]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        elif mode == ParallelExecutionMode.ANY:
            # Execute until one succeeds
            tasks = [self._execute_single_step(execution, step) for step in steps]
            for task in asyncio.as_completed(tasks):
                try:
                    await task
                    # Cancel remaining tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break
                except:
                    continue
        
        elif mode == ParallelExecutionMode.FIRST_SUCCESS:
            # Execute until first success (similar to ANY)
            await self._execute_parallel_group(execution, steps)
        
        elif mode == ParallelExecutionMode.DELAYED:
            # Execute with delays
            for i, step in enumerate(steps):
                await self._execute_single_step(execution, step)
                if i < len(steps) - 1:
                    await asyncio.sleep(1.0)  # 1 second delay
    
    def _evaluate_conditions(
        self, 
        step: WorkflowStep, 
        execution: WorkflowExecution
    ) -> bool:
        """Evaluate conditional logic for step"""
        # This would integrate with the ConditionalEvaluator
        # For now, return True (execute step)
        return True
    
    async def _execute_step_action(
        self, 
        step: WorkflowStep, 
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute the actual step action"""
        # This would integrate with the existing service handlers
        # For now, return a mock result
        return {
            "success": True,
            "step_id": step.id,
            "service": step.service,
            "action": step.action,
            "result": f"Executed {step.action} on {step.service}",
            "timestamp": datetime.now().isoformat()
        }
    
    def _collect_execution_output(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Collect output data from execution"""
        output = {}
        
        for step in execution.steps:
            if step.status == StepExecutionStatus.COMPLETED and step.result:
                output[f"step_{step.id}"] = step.result
        
        return output
    
    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status"""
        try:
            if execution_id not in self.execution_registry:
                return {"success": False, "error": f"Execution {execution_id} not found"}
            
            execution = self.execution_registry[execution_id]
            
            # Calculate progress
            total_steps = len(execution.steps)
            completed_steps = len([s for s in execution.steps if s.status == StepExecutionStatus.COMPLETED])
            failed_steps = len([s for s in execution.steps if s.status == StepExecutionStatus.FAILED])
            
            progress = (completed_steps / total_steps * 100) if total_steps > 0 else 0
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": execution.status.value,
                "progress": progress,
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "failed_steps": failed_steps,
                "execution_time": execution.execution_time,
                "created_at": execution.created_at.isoformat(),
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "error": execution.error
            }
            
        except Exception as e:
            logger.error(f"Error getting execution status: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel workflow execution"""
        try:
            if execution_id not in self.execution_registry:
                return {"success": False, "error": f"Execution {execution_id} not found"}
            
            execution = self.execution_registry[execution_id]
            
            if execution.status in [WorkflowExecutionStatus.COMPLETED, WorkflowExecutionStatus.FAILED, WorkflowExecutionStatus.CANCELLED]:
                return {"success": False, "error": "Execution already completed"}
            
            # Cancel execution
            execution.status = WorkflowExecutionStatus.CANCELLED
            execution.completed_at = datetime.now()
            
            # Cancel pending steps
            for step in execution.steps:
                if step.status == StepExecutionStatus.PENDING:
                    step.status = StepExecutionStatus.CANCELLED
            
            # Remove from active executions
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": "cancelled",
                "message": "Workflow execution cancelled successfully"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling execution: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get all available workflow templates"""
        templates = []
        
        for template_id, template in self.template_registry.items():
            templates.append({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": template.tags,
                "version": template.version,
                "author": template.author,
                "created_at": template.created_at.isoformat(),
                "steps_count": len(template.steps),
                "has_parallel": any(step.parallel for step in template.steps),
                "has_conditional": any(step.conditional for step in template.steps)
            })
        
        return sorted(templates, key=lambda x: x["name"])
    
    def pause_execution(self, execution_id: str) -> Dict[str, Any]:
        """Pause workflow execution"""
        try:
            if execution_id not in self.execution_registry:
                return {"success": False, "error": f"Execution {execution_id} not found"}
            
            execution = self.execution_registry[execution_id]
            
            if execution.status != WorkflowExecutionStatus.RUNNING:
                return {"success": False, "error": "Execution is not running"}
            
            execution.status = WorkflowExecutionStatus.PAUSED
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": "paused",
                "message": "Workflow execution paused"
            }
            
        except Exception as e:
            logger.error(f"Error pausing execution: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def resume_execution(self, execution_id: str) -> Dict[str, Any]:
        """Resume paused workflow execution"""
        try:
            if execution_id not in self.execution_registry:
                return {"success": False, "error": f"Execution {execution_id} not found"}
            
            execution = self.execution_registry[execution_id]
            
            if execution.status != WorkflowExecutionStatus.PAUSED:
                return {"success": False, "error": "Execution is not paused"}
            
            execution.status = WorkflowExecutionStatus.RUNNING
            
            # Restart execution (simplified - in production would use proper state management)
            future = self.executor.submit(self._execute_workflow_advanced, execution)
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": "resumed",
                "message": "Workflow execution resumed"
            }
            
        except Exception as e:
            logger.error(f"Error resuming execution: {str(e)}")
            return {"success": False, "error": str(e)}


class ConditionalEvaluator:
    """Evaluates conditional logic for workflows"""
    
    def evaluate_rule(self, rule: ConditionalRule, context: Dict[str, Any]) -> bool:
        """Evaluate a conditional rule"""
        try:
            left_value = self._extract_value(rule.left_operand, context)
            right_value = rule.right_operand
            
            if rule.operator == ConditionalLogicOperator.EQUALS:
                return left_value == right_value
            elif rule.operator == ConditionalLogicOperator.NOT_EQUALS:
                return left_value != right_value
            elif rule.operator == ConditionalLogicOperator.GREATER_THAN:
                return float(left_value) > float(right_value)
            elif rule.operator == ConditionalLogicOperator.LESS_THAN:
                return float(left_value) < float(right_value)
            elif rule.operator == ConditionalLogicOperator.GREATER_EQUAL:
                return float(left_value) >= float(right_value)
            elif rule.operator == ConditionalLogicOperator.LESS_EQUAL:
                return float(left_value) <= float(right_value)
            elif rule.operator == ConditionalLogicOperator.CONTAINS:
                return str(right_value) in str(left_value)
            elif rule.operator == ConditionalLogicOperator.NOT_CONTAINS:
                return str(right_value) not in str(left_value)
            elif rule.operator == ConditionalLogicOperator.IN:
                return left_value in right_value
            elif rule.operator == ConditionalLogicOperator.NOT_IN:
                return left_value not in right_value
            elif rule.operator == ConditionalLogicOperator.AND:
                return all(self.evaluate_rule(sub_rule, context) for sub_rule in rule.conditions)
            elif rule.operator == ConditionalLogicOperator.OR:
                return any(self.evaluate_rule(sub_rule, context) for sub_rule in rule.conditions)
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating conditional rule: {str(e)}")
            return False
    
    def _extract_value(self, operand: str, context: Dict[str, Any]) -> Any:
        """Extract value from context using operand path"""
        # Simple dot notation extraction (e.g., "step_1.result.status")
        parts = operand.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value


class ParallelExecutionManager:
    """Manages parallel execution of workflow steps"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.active_groups = {}
    
    async def execute_parallel(
        self, 
        steps: List[WorkflowStep], 
        mode: ParallelExecutionMode
    ) -> List[Dict[str, Any]]:
        """Execute steps in parallel with specified mode"""
        if not steps:
            return []
        
        if mode == ParallelExecutionMode.ALL:
            # Execute all steps and wait for all to complete
            futures = [self.executor.submit(self._execute_step_sync, step) for step in steps]
            results = []
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)
                    results.append(result)
                except Exception as e:
                    results.append({"success": False, "error": str(e)})
            
            return results
        
        elif mode == ParallelExecutionMode.ANY:
            # Execute until one succeeds
            futures = [self.executor.submit(self._execute_step_sync, step) for step in steps]
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)
                    if result.get("success"):
                        # Cancel remaining futures
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        return [result]
                except Exception:
                    continue
            
            # If none succeeded, return all results
            return [future.result() for future in futures if not future.cancelled()]
        
        return []
    
    def _execute_step_sync(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute step synchronously (mock implementation)"""
        return {
            "success": True,
            "step_id": step.id,
            "result": f"Executed {step.action} on {step.service}"
        }


class RetryManager:
    """Manages retry logic for workflow steps"""
    
    async def execute_with_retry(
        self, 
        func: Callable, 
        retry_policy: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute function with retry policy"""
        if not retry_policy:
            return await func()
        
        max_retries = retry_policy.get("max_retries", 3)
        retry_delay = retry_policy.get("retry_delay", 1.0)
        exponential_backoff = retry_policy.get("exponential_backoff", True)
        max_delay = retry_policy.get("max_delay", 60.0)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await func()
                if result.get("success"):
                    return result
                else:
                    last_error = result.get("error", "Unknown error")
                    
            except Exception as e:
                last_error = str(e)
            
            # Don't retry on last attempt
            if attempt < max_retries:
                if exponential_backoff:
                    delay = min(retry_delay * (2 ** attempt), max_delay)
                else:
                    delay = retry_delay
                
                await asyncio.sleep(delay)
        
        return {
            "success": False,
            "error": f"Failed after {max_retries + 1} attempts: {last_error}"
        }


class WorkflowPerformanceMonitor:
    """Monitors workflow execution performance"""
    
    def __init__(self):
        self.execution_metrics = {}
        self.step_metrics = {}
    
    def record_execution_start(self, execution_id: str):
        """Record execution start"""
        self.execution_metrics[execution_id] = {
            "start_time": datetime.now(),
            "step_times": {},
            "step_counts": {"completed": 0, "failed": 0, "skipped": 0}
        }
    
    def record_step_completion(
        self, 
        execution_id: str, 
        step_id: str, 
        duration: float, 
        status: str
    ):
        """Record step completion"""
        if execution_id in self.execution_metrics:
            self.execution_metrics[execution_id]["step_times"][step_id] = duration
            self.execution_metrics[execution_id]["step_counts"][status] += 1
    
    def get_performance_report(self, execution_id: str) -> Dict[str, Any]:
        """Get performance report for execution"""
        if execution_id not in self.execution_metrics:
            return {"error": "Execution not found"}
        
        metrics = self.execution_metrics[execution_id]
        step_times = metrics["step_times"].values()
        
        return {
            "execution_id": execution_id,
            "total_steps": len(step_times),
            "average_step_time": sum(step_times) / len(step_times) if step_times else 0,
            "max_step_time": max(step_times) if step_times else 0,
            "min_step_time": min(step_times) if step_times else 0,
            "step_counts": metrics["step_counts"],
            "estimated_efficiency": self._calculate_efficiency(metrics)
        }
    
    def _calculate_efficiency(self, metrics: Dict[str, Any]) -> float:
        """Calculate execution efficiency"""
        total_steps = sum(metrics["step_counts"].values())
        if total_steps == 0:
            return 0.0
        
        completed_steps = metrics["step_counts"]["completed"]
        return (completed_steps / total_steps) * 100


# Global instance
enhanced_workflow_engine = EnhancedWorkflowEngine()

logger.info("Enhanced Workflow Engine initialized with advanced capabilities")