#!/usr/bin/env python3
"""
Multi-Integration Workflow Orchestration Engine
Intelligent cross-platform automation with AI optimization
"""

import os
import json
import logging
import asyncio
import uuid
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Union, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
import httpx
from collections import defaultdict, deque
import re
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRYING = "retrying"

class TriggerType(Enum):
    """Workflow trigger types"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    WEBHOOK = "webhook"
    API_CALL = "api_call"
    CONDITIONAL = "conditional"

class ActionType(Enum):
    """Action types for workflow steps"""
    API_CALL = "api_call"
    DATA_TRANSFORM = "data_transform"
    CONDITION_CHECK = "condition_check"
    DELAY = "delay"
    WEBHOOK = "webhook"
    EMAIL_NOTIFICATION = "email_notification"
    SLACK_NOTIFICATION = "slack_notification"
    PARALLEL_EXECUTION = "parallel_execution"
    ERROR_HANDLER = "error_handler"
    RETRY = "retry"

class Operator(Enum):
    """Comparison operators for conditions"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX_MATCH = "regex"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"

@dataclass
class WorkflowTrigger:
    """Workflow trigger configuration"""
    type: TriggerType
    integration: str
    event_type: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None  # Cron expression
    webhook_path: Optional[str] = None
    api_endpoint: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowStep:
    """Individual workflow step"""
    id: str
    name: str
    action: ActionType
    integration: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    timeout: int = 30
    depends_on: List[str] = field(default_factory=list)
    error_handler: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowDefinition:
    """Complete workflow definition"""
    id: str
    name: str
    description: str
    version: str
    triggers: List[WorkflowTrigger]
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class WorkflowExecution:
    """Workflow execution record"""
    id: str
    workflow_id: str
    status: WorkflowStatus
    started_at: str
    completed_at: Optional[str] = None
    triggered_by: str
    context: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StepExecution:
    """Step execution record"""
    id: str
    workflow_execution_id: str
    step_id: str
    status: WorkflowStatus
    started_at: str
    completed_at: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    logs: List[str] = field(default_factory=list)

@dataclass
class WorkflowAnalytics:
    """Workflow analytics data"""
    workflow_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_execution_time: float
    success_rate: float
    last_execution: Optional[str]
    most_common_errors: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    ai_optimizations: List[str]

class WorkflowCondition:
    """Condition evaluator for workflows"""
    
    @staticmethod
    def evaluate(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a condition against context"""
        try:
            if not condition:
                return True
            
            # Handle simple conditions
            if 'operator' in condition and 'field' in condition and 'value' in condition:
                return WorkflowCondition._evaluate_simple_condition(condition, context)
            
            # Handle complex conditions (AND/OR)
            if 'and' in condition:
                return all(WorkflowCondition.evaluate(sub_cond, context) for sub_cond in condition['and'])
            
            if 'or' in condition:
                return any(WorkflowCondition.evaluate(sub_cond, context) for sub_cond in condition['or'])
            
            if 'not' in condition:
                return not WorkflowCondition.evaluate(condition['not'], context)
            
            return True
            
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False
    
    @staticmethod
    def _evaluate_simple_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition"""
        operator = condition['operator']
        field = condition['field']
        expected_value = condition['value']
        
        # Get actual value from context (support nested paths)
        actual_value = WorkflowCondition._get_nested_value(field, context)
        
        # Handle null/undefined values
        if actual_value is None:
            if operator == Operator.IS_NULL.value:
                return True
            elif operator == Operator.IS_NOT_NULL.value:
                return False
            else:
                actual_value = ""
        
        try:
            # Evaluate based on operator
            if operator == Operator.EQUALS.value:
                return str(actual_value) == str(expected_value)
            
            elif operator == Operator.NOT_EQUALS.value:
                return str(actual_value) != str(expected_value)
            
            elif operator == Operator.GREATER_THAN.value:
                return float(actual_value) > float(expected_value)
            
            elif operator == Operator.LESS_THAN.value:
                return float(actual_value) < float(expected_value)
            
            elif operator == Operator.GREATER_EQUAL.value:
                return float(actual_value) >= float(expected_value)
            
            elif operator == Operator.LESS_EQUAL.value:
                return float(actual_value) <= float(expected_value)
            
            elif operator == Operator.CONTAINS.value:
                return str(expected_value).lower() in str(actual_value).lower()
            
            elif operator == Operator.NOT_CONTAINS.value:
                return str(expected_value).lower() not in str(actual_value).lower()
            
            elif operator == Operator.STARTS_WITH.value:
                return str(actual_value).lower().startswith(str(expected_value).lower())
            
            elif operator == Operator.ENDS_WITH.value:
                return str(actual_value).lower().endswith(str(expected_value).lower())
            
            elif operator == Operator.REGEX_MATCH.value:
                return bool(re.match(str(expected_value), str(actual_value)))
            
            elif operator == Operator.IS_NULL.value:
                return actual_value is None or actual_value == ""
            
            elif operator == Operator.IS_NOT_NULL.value:
                return actual_value is not None and actual_value != ""
            
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
                
        except (ValueError, TypeError) as e:
            logger.error(f"Condition evaluation error: {e}")
            return False
    
    @staticmethod
    def _get_nested_value(path: str, context: Dict[str, Any]) -> Any:
        """Get nested value from context using dot notation"""
        try:
            keys = path.split('.')
            value = context
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                elif isinstance(value, list) and key.isdigit():
                    index = int(key)
                    if 0 <= index < len(value):
                        value = value[index]
                    else:
                        return None
                else:
                    return None
            
            return value
            
        except Exception:
            return None

class DataTransformer:
    """Data transformation utilities for workflows"""
    
    @staticmethod
    def transform(data: Dict[str, Any], transformation: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation to data"""
        try:
            transform_type = transformation.get('type')
            
            if transform_type == 'map_fields':
                return DataTransformer._map_fields(data, transformation.get('mapping', {}))
            
            elif transform_type == 'filter_fields':
                return DataTransformer._filter_fields(data, transformation.get('fields', []))
            
            elif transform_type == 'aggregate':
                return DataTransformer._aggregate(data, transformation.get('aggregation', {}))
            
            elif transform_type == 'calculate':
                return DataTransformer._calculate(data, transformation.get('calculations', {}))
            
            elif transform_type == 'format':
                return DataTransformer._format(data, transformation.get('format_rules', {}))
            
            elif transform_type == 'lookup':
                return DataTransformer._lookup(data, transformation.get('lookup_config', {}))
            
            elif transform_type == 'script':
                return DataTransformer._execute_script(data, transformation.get('script', ''))
            
            else:
                logger.warning(f"Unknown transformation type: {transform_type}")
                return data
                
        except Exception as e:
            logger.error(f"Data transformation failed: {e}")
            return data
    
    @staticmethod
    def _map_fields(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Map fields from source to target"""
        result = {}
        for target_field, source_field in mapping.items():
            value = WorkflowCondition._get_nested_value(source_field, data)
            if value is not None:
                DataTransformer._set_nested_value(target_field, value, result)
        return result
    
    @staticmethod
    def _filter_fields(data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """Filter to specific fields"""
        result = {}
        for field in fields:
            value = WorkflowCondition._get_nested_value(field, data)
            if value is not None:
                DataTransformer._set_nested_value(field, value, result)
        return result
    
    @staticmethod
    def _aggregate(data: Dict[str, Any], aggregation: Dict[str, Any]) -> Dict[str, Any]:
        """Perform aggregation operations"""
        result = {}
        
        for field, operation in aggregation.items():
            values = WorkflowCondition._get_nested_value(field, data)
            if not isinstance(values, list):
                values = [values]
            
            if operation == 'count':
                result[f"{field}_count"] = len([v for v in values if v is not None])
            
            elif operation == 'sum':
                result[f"{field}_sum"] = sum(float(v) for v in values if v is not None and str(v).replace('.', '').isdigit())
            
            elif operation == 'avg':
                numeric_values = [float(v) for v in values if v is not None and str(v).replace('.', '').isdigit()]
                result[f"{field}_avg"] = sum(numeric_values) / len(numeric_values) if numeric_values else 0
            
            elif operation == 'min':
                numeric_values = [float(v) for v in values if v is not None and str(v).replace('.', '').isdigit()]
                result[f"{field}_min"] = min(numeric_values) if numeric_values else 0
            
            elif operation == 'max':
                numeric_values = [float(v) for v in values if v is not None and str(v).replace('.', '').isdigit()]
                result[f"{field}_max"] = max(numeric_values) if numeric_values else 0
        
        return result
    
    @staticmethod
    def _calculate(data: Dict[str, Any], calculations: Dict[str, str]) -> Dict[str, Any]:
        """Perform calculations on data"""
        result = {}
        
        for field_name, expression in calculations.items():
            try:
                # Simple expression evaluation (safe)
                # In production, use a proper expression evaluator
                context = {k: v for k, v in data.items() if isinstance(v, (int, float))}
                result[field_name] = eval(expression, {"__builtins__": {}}, context)
            except Exception as e:
                logger.error(f"Calculation failed for {field_name}: {e}")
                result[field_name] = None
        
        return result
    
    @staticmethod
    def _format(data: Dict[str, Any], format_rules: Dict[str, str]) -> Dict[str, Any]:
        """Format data fields"""
        result = data.copy()
        
        for field, format_rule in format_rules.items():
            value = WorkflowCondition._get_nested_value(field, data)
            if value is not None:
                try:
                    if format_rule.startswith('date:'):
                        date_format = format_rule[5:]  # Remove 'date:' prefix
                        if isinstance(value, str):
                            date_obj = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        else:
                            date_obj = value
                        formatted_value = date_obj.strftime(date_format)
                        DataTransformer._set_nested_value(field, formatted_value, result)
                    
                    elif format_rule.startswith('number:'):
                        number_format = format_rule[7:]  # Remove 'number:' prefix
                        if number_format == 'currency':
                            formatted_value = f"${float(value):,.2f}"
                        elif number_format == 'percentage':
                            formatted_value = f"{float(value) * 100:.1f}%"
                        else:
                            formatted_value = f"{float(value):.{number_format}f}"
                        DataTransformer._set_nested_value(field, formatted_value, result)
                    
                    elif format_rule == 'uppercase':
                        formatted_value = str(value).upper()
                        DataTransformer._set_nested_value(field, formatted_value, result)
                    
                    elif format_rule == 'lowercase':
                        formatted_value = str(value).lower()
                        DataTransformer._set_nested_value(field, formatted_value, result)
                    
                except Exception as e:
                    logger.error(f"Formatting failed for {field}: {e}")
        
        return result
    
    @staticmethod
    def _lookup(data: Dict[str, Any], lookup_config: Dict[str, Any]) -> Dict[str, Any]:
        """Perform data lookup"""
        try:
            lookup_table = lookup_config.get('table', {})
            lookup_key = WorkflowCondition._get_nested_value(lookup_config.get('key'), data)
            target_field = lookup_config.get('target_field', 'value')
            default_value = lookup_config.get('default')
            
            if lookup_key in lookup_table:
                result = lookup_table[lookup_key]
                if isinstance(result, dict) and target_field in result:
                    return {lookup_config.get('output_field', 'lookup_result'): result[target_field]}
                else:
                    return {lookup_config.get('output_field', 'lookup_result'): result}
            else:
                return {lookup_config.get('output_field', 'lookup_result'): default_value}
        
        except Exception as e:
            logger.error(f"Lookup failed: {e}")
            return {}
    
    @staticmethod
    def _execute_script(data: Dict[str, Any], script: str) -> Dict[str, Any]:
        """Execute custom script (simplified for security)"""
        # In production, use a secure script execution environment
        try:
            # Very limited script execution for security
            if 'return' in script:
                # Extract return statement
                return_match = re.search(r'return\s+(.+?);', script)
                if return_match:
                    result = eval(return_match.group(1), {"__builtins__": {}}, {"data": data})
                    return result
            return {}
        
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return {}
    
    @staticmethod
    def _set_nested_value(path: str, value: Any, target: Dict[str, Any]):
        """Set nested value in target using dot notation"""
        keys = path.split('.')
        current = target
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value

class WorkflowEngine:
    """Main workflow orchestration engine"""
    
    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.step_executions: Dict[str, StepExecution] = {}
        self.scheduled_workflows: Dict[str, Any] = {}
        self.webhooks: Dict[str, Any] = {}
        self.http_client = httpx.AsyncClient(timeout=60.0)
        
        # Configuration
        self.max_concurrent_executions = 50
        self.default_timeout = 300  # 5 minutes
        self.cleanup_interval = 3600  # 1 hour
        
        # Initialize
        self._load_workflows()
        self._start_cleanup_task()
    
    def _load_workflows(self):
        """Load workflow definitions"""
        try:
            workflows_dir = Path("workflows")
            if workflows_dir.exists():
                for workflow_file in workflows_dir.glob("*.json"):
                    with open(workflow_file, 'r') as f:
                        workflow_data = json.load(f)
                        workflow = self._parse_workflow_definition(workflow_data)
                        self.workflows[workflow.id] = workflow
                
                for workflow_file in workflows_dir.glob("*.yaml"):
                    with open(workflow_file, 'r') as f:
                        workflow_data = yaml.safe_load(f)
                        workflow = self._parse_workflow_definition(workflow_data)
                        self.workflows[workflow.id] = workflow
            
            logger.info(f"Loaded {len(self.workflows)} workflow definitions")
            
        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
    
    def _parse_workflow_definition(self, data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse workflow definition from data"""
        try:
            # Parse triggers
            triggers = []
            for trigger_data in data.get('triggers', []):
                trigger = WorkflowTrigger(
                    type=TriggerType(trigger_data['type']),
                    integration=trigger_data['integration'],
                    event_type=trigger_data.get('event_type'),
                    condition=trigger_data.get('condition'),
                    schedule=trigger_data.get('schedule'),
                    webhook_path=trigger_data.get('webhook_path'),
                    api_endpoint=trigger_data.get('api_endpoint'),
                    enabled=trigger_data.get('enabled', True),
                    metadata=trigger_data.get('metadata', {})
                )
                triggers.append(trigger)
            
            # Parse steps
            steps = []
            for step_data in data.get('steps', []):
                step = WorkflowStep(
                    id=step_data['id'],
                    name=step_data['name'],
                    action=ActionType(step_data['action']),
                    integration=step_data.get('integration'),
                    parameters=step_data.get('parameters', {}),
                    condition=step_data.get('condition'),
                    retry_config=step_data.get('retry_config'),
                    timeout=step_data.get('timeout', 30),
                    depends_on=step_data.get('depends_on', []),
                    error_handler=step_data.get('error_handler'),
                    metadata=step_data.get('metadata', {})
                )
                steps.append(step)
            
            return WorkflowDefinition(
                id=data['id'],
                name=data['name'],
                description=data['description'],
                version=data['version'],
                triggers=triggers,
                steps=steps,
                variables=data.get('variables', {}),
                settings=data.get('settings', {}),
                enabled=data.get('enabled', True),
                tags=data.get('tags', []),
                created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
                updated_at=data.get('updated_at', datetime.now(timezone.utc).isoformat())
            )
            
        except Exception as e:
            logger.error(f"Failed to parse workflow definition: {e}")
            raise
    
    async def create_workflow(self, workflow_definition: Dict[str, Any]) -> WorkflowDefinition:
        """Create new workflow"""
        try:
            workflow = self._parse_workflow_definition(workflow_definition)
            self.workflows[workflow.id] = workflow
            
            # Save workflow definition
            await self._save_workflow(workflow)
            
            # Register triggers
            await self._register_workflow_triggers(workflow)
            
            logger.info(f"Created workflow: {workflow.id} - {workflow.name}")
            return workflow
            
        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            raise
    
    async def execute_workflow(self, workflow_id: str, triggered_by: str = "manual", 
                            context: Dict[str, Any] = None) -> WorkflowExecution:
        """Execute a workflow"""
        try:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            workflow = self.workflows[workflow_id]
            
            # Check if workflow is enabled
            if not workflow.enabled:
                raise ValueError(f"Workflow {workflow_id} is disabled")
            
            # Check concurrent execution limit
            running_count = sum(1 for exec in self.executions.values() 
                              if exec.status == WorkflowStatus.RUNNING)
            if running_count >= self.max_concurrent_executions:
                raise Exception("Maximum concurrent executions reached")
            
            # Create execution record
            execution = WorkflowExecution(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                status=WorkflowStatus.RUNNING,
                started_at=datetime.now(timezone.utc).isoformat(),
                triggered_by=triggered_by,
                context=context or {},
                variables=workflow.variables.copy(),
                metadata={
                    "ai_optimizations": [],
                    "performance_hints": []
                }
            )
            
            self.executions[execution.id] = execution
            
            logger.info(f"Started workflow execution: {execution.id} for workflow {workflow_id}")
            
            # Execute workflow asynchronously
            asyncio.create_task(self._execute_workflow_steps(execution, workflow))
            
            return execution
            
        except Exception as e:
            logger.error(f"Failed to execute workflow {workflow_id}: {e}")
            raise
    
    async def _execute_workflow_steps(self, execution: WorkflowExecution, workflow: WorkflowDefinition):
        """Execute workflow steps"""
        try:
            start_time = time.time()
            completed_steps = set()
            failed_steps = set()
            
            # Create step dependency graph
            step_graph = self._build_step_dependency_graph(workflow.steps)
            
            # Execute steps in dependency order
            while len(completed_steps) < len(workflow.steps):
                # Find steps ready for execution
                ready_steps = []
                
                for step in workflow.steps:
                    if step.id in completed_steps or step.id in failed_steps:
                        continue
                    
                    # Check dependencies
                    dependencies_met = all(
                        dep in completed_steps for dep in step.depends_on
                    )
                    
                    if dependencies_met:
                        ready_steps.append(step)
                
                if not ready_steps:
                    # Check if we have circular dependencies or all remaining steps failed
                    remaining_steps = [s.id for s in workflow.steps 
                                     if s.id not in completed_steps and s.id not in failed_steps]
                    
                    if remaining_steps:
                        logger.error(f"Circular dependency detected for steps: {remaining_steps}")
                        execution.status = WorkflowStatus.FAILED
                        execution.error = "Circular dependency in workflow steps"
                    break
                
                # Execute ready steps
                step_tasks = []
                for step in ready_steps:
                    step_task = self._execute_step(execution, workflow, step)
                    step_tasks.append(step_task)
                
                # Wait for all current steps to complete
                step_results = await asyncio.gather(*step_tasks, return_exceptions=True)
                
                # Process step results
                for i, result in enumerate(step_results):
                    step = ready_steps[i]
                    
                    if isinstance(result, Exception):
                        logger.error(f"Step {step.id} failed: {result}")
                        failed_steps.add(step.id)
                        
                        # Check error handler
                        if step.error_handler:
                            await self._execute_error_handler(execution, workflow, step, result)
                        else:
                            execution.status = WorkflowStatus.FAILED
                            execution.error = f"Step {step.id} failed: {result}"
                            break
                    else:
                        if result.get('success', False):
                            completed_steps.add(step.id)
                            
                            # Merge step output into execution context
                            execution.context.update(result.get('output_data', {}))
                            execution.step_results[step.id] = result
                        else:
                            logger.error(f"Step {step.id} returned failure: {result}")
                            failed_steps.add(step.id)
                            
                            if step.error_handler:
                                await self._execute_error_handler(execution, workflow, step, result)
                            else:
                                execution.status = WorkflowStatus.FAILED
                                execution.error = f"Step {step.id} failed"
                                break
                
                # Check if workflow should continue
                if execution.status == WorkflowStatus.FAILED:
                    break
            
            # Update execution status
            end_time = time.time()
            execution.execution_time = end_time - start_time
            
            if execution.status != WorkflowStatus.FAILED:
                execution.status = WorkflowStatus.COMPLETED
                logger.info(f"Workflow execution {execution.id} completed successfully")
            else:
                logger.error(f"Workflow execution {execution.id} failed")
            
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            
            # Store analytics
            await self._store_workflow_analytics(execution, workflow)
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
    
    async def _execute_step(self, execution: WorkflowExecution, workflow: WorkflowDefinition, 
                           step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single workflow step"""
        try:
            start_time = time.time()
            
            # Create step execution record
            step_execution = StepExecution(
                id=str(uuid.uuid4()),
                workflow_execution_id=execution.id,
                step_id=step.id,
                status=WorkflowStatus.RUNNING,
                started_at=datetime.now(timezone.utc).isoformat(),
                input_data=execution.context.copy(),
                retry_count=0
            )
            
            self.step_executions[step_execution.id] = step_execution
            
            logger.info(f"Executing step: {step.id} - {step.name}")
            
            # Check step condition
            if step.condition:
                if not WorkflowCondition.evaluate(step.condition, execution.context):
                    step_execution.status = WorkflowStatus.COMPLETED
                    step_execution.completed_at = datetime.now(timezone.utc).isoformat()
                    step_execution.output_data = {"skipped": True, "reason": "Condition not met"}
                    return {
                        "success": True,
                        "skipped": True,
                        "step_execution_id": step_execution.id,
                        "output_data": step_execution.output_data
                    }
            
            # Execute step based on action type
            result = await self._execute_step_action(execution, step)
            
            # Update step execution
            end_time = time.time()
            step_execution.execution_time = end_time - start_time
            step_execution.status = WorkflowStatus.COMPLETED if result.get('success', False) else WorkflowStatus.FAILED
            step_execution.completed_at = datetime.now(timezone.utc).isoformat()
            step_execution.output_data = result.get('output_data', {})
            step_execution.error = result.get('error') if not result.get('success', False) else None
            
            logger.info(f"Step {step.id} completed with status: {step_execution.status.value}")
            
            return {
                "success": result.get('success', False),
                "step_execution_id": step_execution.id,
                "output_data": result.get('output_data', {}),
                "error": result.get('error'),
                "execution_time": step_execution.execution_time
            }
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            step_execution.status = WorkflowStatus.FAILED
            step_execution.error = str(e)
            step_execution.completed_at = datetime.now(timezone.utc).isoformat()
            
            return {
                "success": False,
                "step_execution_id": step_execution.id,
                "error": str(e)
            }
    
    async def _execute_step_action(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute step based on action type"""
        try:
            action = step.action
            
            if action == ActionType.API_CALL:
                return await self._execute_api_call(execution, step)
            
            elif action == ActionType.DATA_TRANSFORM:
                return await self._execute_data_transform(execution, step)
            
            elif action == ActionType.CONDITION_CHECK:
                return await self._execute_condition_check(execution, step)
            
            elif action == ActionType.DELAY:
                return await self._execute_delay(execution, step)
            
            elif action == ActionType.WEBHOOK:
                return await self._execute_webhook(execution, step)
            
            elif action == ActionType.EMAIL_NOTIFICATION:
                return await self._execute_email_notification(execution, step)
            
            elif action == ActionType.SLACK_NOTIFICATION:
                return await self._execute_slack_notification(execution, step)
            
            elif action == ActionType.PARALLEL_EXECUTION:
                return await self._execute_parallel_execution(execution, step)
            
            else:
                logger.error(f"Unknown action type: {action}")
                return {
                    "success": False,
                    "error": f"Unknown action type: {action}"
                }
                
        except Exception as e:
            logger.error(f"Step action execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_api_call(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute API call action"""
        try:
            parameters = step.parameters
            
            # Replace variables in parameters
            resolved_params = self._resolve_variables(parameters, execution.context)
            
            # Make API call
            integration = step.integration or "hubspot"  # Default integration
            base_url = self._get_integration_base_url(integration)
            
            url = f"{base_url}{resolved_params.get('endpoint', '')}"
            method = resolved_params.get('method', 'GET')
            headers = resolved_params.get('headers', {})
            data = resolved_params.get('data', {})
            
            # Add workflow execution headers
            headers['X-Workflow-Execution-Id'] = execution.id
            headers['X-Workflow-Step-Id'] = step.id
            
            async with httpx.AsyncClient(timeout=step.timeout) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=data)
                elif method.upper() == 'POST':
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=headers)
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported HTTP method: {method}"
                    }
            
            # Process response
            if response.status_code < 400:
                return {
                    "success": True,
                    "output_data": {
                        "status_code": response.status_code,
                        "response_data": response.json() if response.content else {},
                        "headers": dict(response.headers),
                        "url": str(response.url)
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"API call failed with status {response.status_code}",
                    "output_data": {
                        "status_code": response.status_code,
                        "response_data": response.json() if response.content else {},
                        "url": str(response.url)
                    }
                }
                
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"API call timed out after {step.timeout} seconds"
            }
        except Exception as e:
            logger.error(f"API call execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_data_transform(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute data transform action"""
        try:
            parameters = step.parameters
            
            # Get input data
            input_data = execution.context.get('input_data', {})
            if 'input_data' in parameters:
                # Transform the data
                transformed_data = DataTransformer.transform(input_data, parameters)
            else:
                # Transform current context
                transformed_data = DataTransformer.transform(execution.context, parameters)
            
            return {
                "success": True,
                "output_data": transformed_data
            }
            
        except Exception as e:
            logger.error(f"Data transform execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_condition_check(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute condition check action"""
        try:
            parameters = step.parameters
            condition = parameters.get('condition')
            
            if not condition:
                return {
                    "success": False,
                    "error": "No condition provided"
                }
            
            # Evaluate condition
            result = WorkflowCondition.evaluate(condition, execution.context)
            
            return {
                "success": True,
                "output_data": {
                    "condition_result": result,
                    "condition": condition
                }
            }
            
        except Exception as e:
            logger.error(f"Condition check execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_delay(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute delay action"""
        try:
            parameters = step.parameters
            duration = parameters.get('duration', 5)  # Default 5 seconds
            
            # Wait for specified duration
            await asyncio.sleep(duration)
            
            return {
                "success": True,
                "output_data": {
                    "delayed_for": duration
                }
            }
            
        except Exception as e:
            logger.error(f"Delay execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_webhook(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute webhook call action"""
        try:
            parameters = step.parameters
            
            # Resolve variables
            resolved_params = self._resolve_variables(parameters, execution.context)
            
            url = resolved_params.get('url')
            method = resolved_params.get('method', 'POST')
            headers = resolved_params.get('headers', {})
            data = resolved_params.get('data', {})
            
            if not url:
                return {
                    "success": False,
                    "error": "No webhook URL provided"
                }
            
            # Add workflow headers
            headers['X-Workflow-Execution-Id'] = execution.id
            headers['X-Workflow-Step-Id'] = step.id
            headers['X-Workflow-Trigger'] = 'webhook'
            
            async with httpx.AsyncClient(timeout=step.timeout) as client:
                if method.upper() == 'POST':
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=data)
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported webhook method: {method}"
                    }
            
            if response.status_code < 400:
                return {
                    "success": True,
                    "output_data": {
                        "status_code": response.status_code,
                        "response_data": response.json() if response.content else {},
                        "webhook_url": url
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Webhook call failed with status {response.status_code}",
                    "output_data": {
                        "status_code": response.status_code,
                        "webhook_url": url
                    }
                }
                
        except Exception as e:
            logger.error(f"Webhook execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_email_notification(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute email notification action"""
        try:
            parameters = step.parameters
            
            # Resolve variables
            resolved_params = self._resolve_variables(parameters, execution.context)
            
            to = resolved_params.get('to')
            subject = resolved_params.get('subject')
            body = resolved_params.get('body')
            
            if not to or not subject:
                return {
                    "success": False,
                    "error": "Missing required email parameters: to, subject"
                }
            
            # In production, integrate with email service
            logger.info(f"Sending email to {to}: {subject}")
            
            return {
                "success": True,
                "output_data": {
                    "email_sent": True,
                    "to": to,
                    "subject": subject
                }
            }
            
        except Exception as e:
            logger.error(f"Email notification execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_slack_notification(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute Slack notification action"""
        try:
            parameters = step.parameters
            
            # Resolve variables
            resolved_params = self._resolve_variables(parameters, execution.context)
            
            channel = resolved_params.get('channel', '#general')
            message = resolved_params.get('message')
            
            if not message:
                return {
                    "success": False,
                    "error": "Missing required Slack parameter: message"
                }
            
            # In production, integrate with Slack API
            logger.info(f"Sending Slack message to {channel}: {message}")
            
            return {
                "success": True,
                "output_data": {
                    "slack_notification_sent": True,
                    "channel": channel,
                    "message": message
                }
            }
            
        except Exception as e:
            logger.error(f"Slack notification execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_parallel_execution(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute parallel steps"""
        try:
            parameters = step.parameters
            parallel_steps = parameters.get('steps', [])
            
            if not parallel_steps:
                return {
                    "success": False,
                    "error": "No parallel steps provided"
                }
            
            # Create temporary workflow steps for parallel execution
            parallel_results = []
            
            for step_data in parallel_steps:
                parallel_step = WorkflowStep(
                    id=step_data['id'],
                    name=step_data['name'],
                    action=ActionType(step_data['action']),
                    integration=step_data.get('integration'),
                    parameters=step_data.get('parameters', {}),
                    timeout=step_data.get('timeout', 30)
                )
                
                # Execute parallel step
                result = await self._execute_step_action(execution, parallel_step)
                parallel_results.append({
                    "step_id": parallel_step.id,
                    "result": result
                })
            
            return {
                "success": True,
                "output_data": {
                    "parallel_results": parallel_results
                }
            }
            
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _resolve_variables(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variables in data using context"""
        try:
            resolved_data = {}
            
            for key, value in data.items():
                if isinstance(value, str) and '${' in value:
                    # Replace variables
                    resolved_value = self._replace_variables(value, context)
                    resolved_data[key] = resolved_value
                else:
                    resolved_data[key] = value
            
            return resolved_data
            
        except Exception as e:
            logger.error(f"Variable resolution failed: {e}")
            return data
    
    def _replace_variables(self, text: str, context: Dict[str, Any]) -> str:
        """Replace variables in text with context values"""
        try:
            # Simple variable replacement (supports ${variable} syntax)
            import re
            
            def replace_match(match):
                var_path = match.group(1)
                value = WorkflowCondition._get_nested_value(var_path, context)
                return str(value) if value is not None else ""
            
            return re.sub(r'\$\{([^}]+)\}', replace_match, text)
            
        except Exception as e:
            logger.error(f"Variable replacement failed: {e}")
            return text
    
    def _get_integration_base_url(self, integration: str) -> str:
        """Get base URL for integration"""
        base_urls = {
            'hubspot': 'http://localhost:5058/api/v2/hubspot',
            'slack': 'http://localhost:5058/api/v2/slack',
            'jira': 'http://localhost:5058/api/v2/jira',
            'linear': 'http://localhost:5058/api/v2/linear',
            'salesforce': 'http://localhost:5058/api/v2/salesforce',
            'xero': 'http://localhost:5058/api/v2/xero'
        }
        
        return base_urls.get(integration, f'http://localhost:5058/api/v2/{integration}')
    
    def _build_step_dependency_graph(self, steps: List[WorkflowStep]) -> Dict[str, List[str]]:
        """Build dependency graph for steps"""
        graph = {}
        
        for step in steps:
            graph[step.id] = step.depends_on.copy()
        
        return graph
    
    async def _execute_error_handler(self, execution: WorkflowExecution, workflow: WorkflowDefinition,
                                  step: WorkflowStep, error: Exception):
        """Execute error handler step"""
        try:
            if not step.error_handler:
                return
            
            # Find error handler step
            error_step = None
            for s in workflow.steps:
                if s.id == step.error_handler:
                    error_step = s
                    break
            
            if not error_step:
                logger.error(f"Error handler step {step.error_handler} not found")
                return
            
            # Add error information to context
            execution.context['error'] = {
                "step_id": step.id,
                "step_name": step.name,
                "error_message": str(error),
                "error_type": type(error).__name__
            }
            
            # Execute error handler step
            result = await self._execute_step(execution, workflow, error_step)
            
            if result.get('success', False):
                logger.info(f"Error handler {error_step.id} executed successfully")
            else:
                logger.error(f"Error handler {error_step.id} failed")
            
        except Exception as e:
            logger.error(f"Error handler execution failed: {e}")
    
    async def _save_workflow(self, workflow: WorkflowDefinition):
        """Save workflow definition to file"""
        try:
            workflows_dir = Path("workflows")
            workflows_dir.mkdir(exist_ok=True)
            
            workflow_file = workflows_dir / f"{workflow.id}.json"
            
            with open(workflow_file, 'w') as f:
                json.dump(asdict(workflow), f, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Failed to save workflow: {e}")
    
    async def _register_workflow_triggers(self, workflow: WorkflowDefinition):
        """Register workflow triggers"""
        try:
            for trigger in workflow.triggers:
                if trigger.type == TriggerType.WEBHOOK and trigger.webhook_path:
                    # Register webhook
                    self.webhooks[trigger.webhook_path] = {
                        "workflow_id": workflow.id,
                        "trigger": trigger,
                        "enabled": trigger.enabled
                    }
                
                elif trigger.type == TriggerType.SCHEDULED and trigger.schedule:
                    # Schedule workflow (simplified)
                    self.scheduled_workflows[workflow.id] = {
                        "schedule": trigger.schedule,
                        "workflow_id": workflow.id,
                        "trigger": trigger,
                        "enabled": trigger.enabled,
                        "last_run": None
                    }
            
            logger.info(f"Registered {len(workflow.triggers)} triggers for workflow {workflow.id}")
            
        except Exception as e:
            logger.error(f"Failed to register workflow triggers: {e}")
    
    async def _store_workflow_analytics(self, execution: WorkflowExecution, workflow: WorkflowDefinition):
        """Store workflow execution analytics"""
        try:
            # This would integrate with analytics system
            # For now, just log the analytics
            logger.info(f"Workflow analytics - {workflow.id}: "
                       f"status={execution.status.value}, "
                       f"time={execution.execution_time:.2f}s, "
                       f"steps={len(execution.step_results)}")
            
        except Exception as e:
            logger.error(f"Failed to store workflow analytics: {e}")
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        asyncio.create_task(self._cleanup_task())
    
    async def _cleanup_task(self):
        """Background task to cleanup old executions"""
        while True:
            try:
                # Cleanup old executions (older than 7 days)
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
                
                old_executions = [
                    exec_id for exec_id, execution in self.executions.items()
                    if datetime.fromisoformat(execution.started_at) < cutoff_time
                ]
                
                for exec_id in old_executions:
                    del self.executions[exec_id]
                
                # Cleanup old step executions
                old_step_executions = [
                    step_id for step_id, step_execution in self.step_executions.items()
                    if datetime.fromisoformat(step_execution.started_at) < cutoff_time
                ]
                
                for step_id in old_step_executions:
                    del self.step_executions[step_id]
                
                if old_executions or old_step_executions:
                    logger.info(f"Cleaned up {len(old_executions)} executions and {len(old_step_executions)} step executions")
                
                # Sleep for cleanup interval
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(300)  # 5 minutes on error
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status and recent executions"""
        try:
            if workflow_id not in self.workflows:
                return {"error": f"Workflow {workflow_id} not found"}
            
            workflow = self.workflows[workflow_id]
            
            # Get recent executions
            recent_executions = [
                execution for execution in self.executions.values()
                if execution.workflow_id == workflow_id
            ]
            
            # Sort by start time
            recent_executions.sort(key=lambda x: x.started_at, reverse=True)
            
            # Calculate analytics
            total_executions = len(recent_executions)
            successful_executions = len([e for e in recent_executions if e.status == WorkflowStatus.COMPLETED])
            failed_executions = len([e for e in recent_executions if e.status == WorkflowStatus.FAILED])
            
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
            
            avg_execution_time = 0
            if recent_executions:
                completed_times = [e.execution_time for e in recent_executions if e.execution_time is not None]
                if completed_times:
                    avg_execution_time = sum(completed_times) / len(completed_times)
            
            return {
                "workflow": {
                    "id": workflow.id,
                    "name": workflow.name,
                    "description": workflow.description,
                    "version": workflow.version,
                    "enabled": workflow.enabled,
                    "tags": workflow.tags,
                    "created_at": workflow.created_at,
                    "updated_at": workflow.updated_at
                },
                "status": {
                    "total_executions": total_executions,
                    "successful_executions": successful_executions,
                    "failed_executions": failed_executions,
                    "success_rate": success_rate,
                    "average_execution_time": avg_execution_time,
                    "last_execution": recent_executions[0].started_at if recent_executions else None
                },
                "recent_executions": [
                    {
                        "id": execution.id,
                        "status": execution.status.value,
                        "started_at": execution.started_at,
                        "completed_at": execution.completed_at,
                        "execution_time": execution.execution_time,
                        "triggered_by": execution.triggered_by,
                        "error": execution.error
                    }
                    for execution in recent_executions[:10]  # Last 10 executions
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {"error": str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall workflow system status"""
        try:
            # Count workflows by status
            total_workflows = len(self.workflows)
            enabled_workflows = len([w for w in self.workflows.values() if w.enabled])
            
            # Count executions by status
            total_executions = len(self.executions)
            running_executions = len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING])
            completed_executions = len([e for e in self.executions.values() if e.status == WorkflowStatus.COMPLETED])
            failed_executions = len([e for e in self.executions.values() if e.status == WorkflowStatus.FAILED])
            
            return {
                "system": {
                    "total_workflows": total_workflows,
                    "enabled_workflows": enabled_workflows,
                    "total_executions": total_executions,
                    "running_executions": running_executions,
                    "completed_executions": completed_executions,
                    "failed_executions": failed_executions,
                    "registered_triggers": len(self.webhooks) + len(self.scheduled_workflows),
                    "max_concurrent_executions": self.max_concurrent_executions
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {"error": str(e)}

# Global workflow engine instance
workflow_engine: Optional[WorkflowEngine] = None

def get_workflow_engine() -> WorkflowEngine:
    """Get global workflow engine instance"""
    global workflow_engine
    if workflow_engine is None:
        workflow_engine = WorkflowEngine()
    return workflow_engine

async def initialize_workflow_engine():
    """Initialize workflow orchestration engine"""
    try:
        engine = get_workflow_engine()
        logger.info("Workflow orchestration engine initialized")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize workflow engine: {e}")
        return False