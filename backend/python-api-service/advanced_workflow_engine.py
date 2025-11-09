"""
Advanced Workflow Engine with Conditional Logic and Templates

This module provides advanced workflow automation capabilities including:
- Complex multi-service workflows with conditional logic
- Workflow templates for common business processes
- Workflow versioning and rollback capabilities
- Workflow debugging and troubleshooting tools
- Integration with memory system for context-aware workflows
"""

import asyncio
import copy
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """Workflow node types"""

    TRIGGER = "trigger"
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    DELAY = "delay"
    PARALLEL = "parallel"
    MERGE = "merge"
    ERROR_HANDLER = "error_handler"


@dataclass
class WorkflowNode:
    """Base workflow node definition"""

    id: str
    type: NodeType
    name: str
    service: str
    action: str
    parameters: Dict[str, Any]
    conditions: Optional[List[Dict[str, Any]]] = None
    error_handling: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class WorkflowConnection:
    """Connection between workflow nodes"""

    source_node_id: str
    target_node_id: str
    condition: Optional[str] = None


class AdvancedWorkflowEngine:
    """
    Advanced workflow engine supporting conditional logic, templates,
    versioning, and debugging capabilities.
    """

    def __init__(self, memory_service=None, integration_service=None):
        self.memory_service = memory_service
        self.integration_service = integration_service
        self.workflow_templates = {}
        self.workflow_versions = {}
        self.execution_history = {}
        self.condition_evaluators = {}

        # Initialize built-in condition evaluators
        self._initialize_condition_evaluators()
        self._initialize_workflow_templates()

        logger.info("Advanced Workflow Engine initialized")

    def _initialize_condition_evaluators(self):
        """Initialize built-in condition evaluators"""
        self.condition_evaluators = {
            "equals": lambda a, b: a == b,
            "not_equals": lambda a, b: a != b,
            "greater_than": lambda a, b: a > b,
            "less_than": lambda a, b: a < b,
            "contains": lambda a, b: b in a if isinstance(a, (str, list)) else False,
            "starts_with": lambda a, b: a.startswith(b)
            if isinstance(a, str)
            else False,
            "ends_with": lambda a, b: a.endswith(b) if isinstance(a, str) else False,
            "is_empty": lambda a: not a
            if isinstance(a, (str, list, dict))
            else a is None,
            "is_not_empty": lambda a: bool(a)
            if isinstance(a, (str, list, dict))
            else a is not None,
            "in_list": lambda a, b: a in b if isinstance(b, (list, tuple)) else False,
            "not_in_list": lambda a, b: a not in b
            if isinstance(b, (list, tuple))
            else False,
        }

    def _initialize_workflow_templates(self):
        """Initialize common workflow templates"""
        # Email Processing Template
        self.workflow_templates["email_processing"] = {
            "name": "Email Processing Workflow",
            "description": "Automatically process incoming emails and create tasks",
            "nodes": [
                {
                    "id": "trigger_email",
                    "type": "trigger",
                    "name": "Monitor Inbox",
                    "service": "gmail",
                    "action": "monitor_inbox",
                    "parameters": {
                        "label": "INBOX",
                        "keywords": ["urgent", "action required", "follow up"],
                    },
                },
                {
                    "id": "classify_email",
                    "type": "condition",
                    "name": "Classify Email",
                    "service": "ai",
                    "action": "classify_content",
                    "parameters": {"categories": ["urgent", "important", "routine"]},
                },
                {
                    "id": "create_task_urgent",
                    "type": "action",
                    "name": "Create Urgent Task",
                    "service": "asana",
                    "action": "create_task",
                    "parameters": {"priority": "high", "due_date": "today"},
                    "conditions": [
                        {
                            "field": "classification",
                            "operator": "equals",
                            "value": "urgent",
                        }
                    ],
                },
                {
                    "id": "create_task_important",
                    "type": "action",
                    "name": "Create Important Task",
                    "service": "asana",
                    "action": "create_task",
                    "parameters": {"priority": "medium", "due_date": "tomorrow"},
                    "conditions": [
                        {
                            "field": "classification",
                            "operator": "equals",
                            "value": "important",
                        }
                    ],
                },
                {
                    "id": "schedule_followup",
                    "type": "action",
                    "name": "Schedule Follow-up",
                    "service": "google_calendar",
                    "action": "create_event",
                    "parameters": {"reminder": True},
                    "conditions": [
                        {
                            "field": "classification",
                            "operator": "equals",
                            "value": "routine",
                        }
                    ],
                },
            ],
            "connections": [
                {"source_node_id": "trigger_email", "target_node_id": "classify_email"},
                {
                    "source_node_id": "classify_email",
                    "target_node_id": "create_task_urgent",
                    "condition": "urgent",
                },
                {
                    "source_node_id": "classify_email",
                    "target_node_id": "create_task_important",
                    "condition": "important",
                },
                {
                    "source_node_id": "classify_email",
                    "target_node_id": "schedule_followup",
                    "condition": "routine",
                },
            ],
        }

        # Meeting Follow-up Template
        self.workflow_templates["meeting_followup"] = {
            "name": "Meeting Follow-up Workflow",
            "description": "Automatically process meeting transcripts and create follow-up tasks",
            "nodes": [
                {
                    "id": "trigger_meeting",
                    "type": "trigger",
                    "name": "Meeting Completed",
                    "service": "zoom",
                    "action": "meeting_ended",
                    "parameters": {},
                },
                {
                    "id": "transcribe_meeting",
                    "type": "action",
                    "name": "Transcribe Meeting",
                    "service": "deepgram",
                    "action": "transcribe_audio",
                    "parameters": {},
                },
                {
                    "id": "extract_action_items",
                    "type": "action",
                    "name": "Extract Action Items",
                    "service": "ai",
                    "action": "extract_action_items",
                    "parameters": {},
                },
                {
                    "id": "create_tasks",
                    "type": "action",
                    "name": "Create Tasks",
                    "service": "asana",
                    "action": "create_tasks",
                    "parameters": {},
                    "conditions": [
                        {
                            "field": "action_items_count",
                            "operator": "greater_than",
                            "value": 0,
                        }
                    ],
                },
                {
                    "id": "send_summary",
                    "type": "action",
                    "name": "Send Summary Email",
                    "service": "gmail",
                    "action": "send_email",
                    "parameters": {"template": "meeting_summary"},
                },
            ],
            "connections": [
                {
                    "source_node_id": "trigger_meeting",
                    "target_node_id": "transcribe_meeting",
                },
                {
                    "source_node_id": "transcribe_meeting",
                    "target_node_id": "extract_action_items",
                },
                {
                    "source_node_id": "extract_action_items",
                    "target_node_id": "create_tasks",
                },
                {
                    "source_node_id": "extract_action_items",
                    "target_node_id": "send_summary",
                },
            ],
        }

    async def create_workflow_from_template(
        self, template_name: str, customizations: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a workflow from a template with optional customizations"""
        if template_name not in self.workflow_templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = copy.deepcopy(self.workflow_templates[template_name])
        workflow_id = str(uuid.uuid4())

        # Apply customizations
        if customizations:
            template = self._apply_template_customizations(template, customizations)

        # Create workflow definition
        workflow = {
            "id": workflow_id,
            "name": template["name"],
            "description": template["description"],
            "template": template_name,
            "nodes": template["nodes"],
            "connections": template["connections"],
            "status": WorkflowStatus.DRAFT.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0.0",
        }

        # Store workflow version
        self.workflow_versions[workflow_id] = {"1.0.0": copy.deepcopy(workflow)}

        logger.info(f"Created workflow {workflow_id} from template {template_name}")
        return workflow

    def _apply_template_customizations(
        self, template: Dict[str, Any], customizations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply customizations to a workflow template"""
        # Update workflow metadata
        if "name" in customizations:
            template["name"] = customizations["name"]
        if "description" in customizations:
            template["description"] = customizations["description"]

        # Update node parameters
        if "node_updates" in customizations:
            for node_update in customizations["node_updates"]:
                node_id = node_update.get("node_id")
                parameters = node_update.get("parameters", {})

                for node in template["nodes"]:
                    if node["id"] == node_id:
                        node["parameters"].update(parameters)
                        break

        # Add new nodes
        if "new_nodes" in customizations:
            template["nodes"].extend(customizations["new_nodes"])

        # Add new connections
        if "new_connections" in customizations:
            template["connections"].extend(customizations["new_connections"])

        return template

    async def execute_workflow(
        self, workflow_id: str, trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a workflow with conditional logic"""
        if workflow_id not in self.workflow_versions:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Get latest version
        latest_version = self._get_latest_version(workflow_id)
        workflow = self.workflow_versions[workflow_id][latest_version]

        execution_id = str(uuid.uuid4())
        execution_context = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "start_time": datetime.now().isoformat(),
            "trigger_data": trigger_data or {},
            "node_results": {},
            "variables": {},
            "status": "running",
        }

        self.execution_history[execution_id] = execution_context

        try:
            # Find starting nodes (triggers)
            start_nodes = [
                node for node in workflow["nodes"] if node["type"] == "trigger"
            ]

            if not start_nodes:
                raise ValueError("No trigger nodes found in workflow")

            # Execute workflow
            await self._execute_nodes(workflow, start_nodes, execution_context)

            execution_context["status"] = "completed"
            execution_context["end_time"] = datetime.now().isoformat()

            logger.info(
                f"Workflow {workflow_id} execution {execution_id} completed successfully"
            )

        except Exception as e:
            execution_context["status"] = "failed"
            execution_context["error"] = str(e)
            execution_context["end_time"] = datetime.now().isoformat()
            logger.error(
                f"Workflow {workflow_id} execution {execution_id} failed: {str(e)}"
            )

        return execution_context

    async def _execute_nodes(
        self,
        workflow: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        context: Dict[str, Any],
    ):
        """Execute a list of workflow nodes"""
        for node in nodes:
            if context["status"] == "failed":
                break

            try:
                # Execute node
                result = await self._execute_single_node(node, context)
                context["node_results"][node["id"]] = result

                # Update context variables
                if result.get("output_variables"):
                    context["variables"].update(result["output_variables"])

                # Get next nodes based on conditions
                next_nodes = self._get_next_nodes(workflow, node, result, context)

                if next_nodes:
                    await self._execute_nodes(workflow, next_nodes, context)

            except Exception as e:
                logger.error(f"Error executing node {node['id']}: {str(e)}")
                # Handle node execution error
                error_handler_nodes = self._get_error_handler_nodes(workflow, node)
                if error_handler_nodes:
                    context["current_error"] = str(e)
                    await self._execute_nodes(workflow, error_handler_nodes, context)
                else:
                    raise e

    async def _execute_single_node(
        self, node: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single workflow node"""
        logger.info(f"Executing node: {node['id']} - {node['name']}")

        start_time = datetime.now()

        try:
            # Check conditions before execution
            if node.get("conditions"):
                conditions_met = await self._evaluate_conditions(
                    node["conditions"], context
                )
                if not conditions_met:
                    return {
                        "status": "skipped",
                        "reason": "conditions_not_met",
                        "execution_time": 0,
                    }

            # Execute node action
            if self.integration_service:
                result = await self.integration_service.execute_service_action(
                    node["service"],
                    node["action"],
                    {**node["parameters"], **context["variables"]},
                )
            else:
                # Mock execution for testing
                result = {
                    "success": True,
                    "data": f"Mock execution of {node['service']}.{node['action']}",
                    "output_variables": {},
                }

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "status": "completed",
                "result": result,
                "execution_time": execution_time,
                "output_variables": result.get("output_variables", {}),
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Node {node['id']} execution failed: {str(e)}")

            # Handle retries
            if node.get("retry_count", 0) < node.get("max_retries", 3):
                node["retry_count"] = node.get("retry_count", 0) + 1
                logger.info(
                    f"Retrying node {node['id']} (attempt {node['retry_count']})"
                )
                return await self._execute_single_node(node, context)
            else:
                raise e

    async def _evaluate_conditions(
        self, conditions: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> bool:
        """Evaluate conditions for node execution"""
        for condition in conditions:
            field = condition["field"]
            operator = condition["operator"]
            value = condition["value"]

            # Get field value from context
            field_value = context["variables"].get(field)
            if field_value is None:
                field_value = context["trigger_data"].get(field)

            # Evaluate condition
            evaluator = self.condition_evaluators.get(operator)
            if not evaluator:
                logger.warning(f"Unknown condition operator: {operator}")
                return False

            try:
                if not evaluator(field_value, value):
                    return False
            except Exception as e:
                logger.error(
                    f"Error evaluating condition {field} {operator} {value}: {str(e)}"
                )
                return False

        return True

    def _get_next_nodes(
        self,
        workflow: Dict[str, Any],
        current_node: Dict[str, Any],
        result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get next nodes to execute based on connections and conditions"""
        next_nodes = []

        # Find connections from current node
        connections = [
            conn
            for conn in workflow["connections"]
            if conn["source_node_id"] == current_node["id"]
        ]

        for connection in connections:
            # Check connection condition
            if connection.get("condition"):
                condition_met = self._evaluate_connection_condition(
                    connection["condition"], result, context
                )
                if not condition_met:
                    continue

            # Find target node
            target_node = next(
                (
                    node
                    for node in workflow["nodes"]
                    if node["id"] == connection["target_node_id"]
                ),
                None,
            )

            if target_node:
                next_nodes.append(target_node)

        return next_nodes

    def _evaluate_connection_condition(
        self, condition: str, result: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """Evaluate connection condition"""
        # Simple condition evaluation - can be extended for complex expressions
        if condition in context["variables"]:
            return bool(context["variables"][condition])
        elif condition in result.get("output_variables", {}):
            return bool(result["output_variables"][condition])
        else:
            # Default to True if condition can't be evaluated
            return True

    def _get_error_handler_nodes(
        self, workflow: Dict[str, Any], failed_node: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get error handler nodes for a failed node"""
        error_handler_nodes = []

        # Find error handler connections from the failed node
        error_connections = [
            conn
            for conn in workflow["connections"]
            if conn["source_node_id"] == failed_node["id"]
            and conn.get("condition") == "error"
        ]

        for connection in error_connections:
            # Find target error handler node
            error_node = next(
                (
                    node
                    for node in workflow["nodes"]
                    if node["id"] == connection["target_node_id"]
                    and node["type"] == "error_handler"
                ),
                None,
            )

            if error_node:
                error_handler_nodes.append(error_node)

        return error_handler_nodes

    def _get_latest_version(self, workflow_id: str) -> str:
        """Get the latest version of a workflow"""
        if workflow_id in self.workflow_versions:
            versions = list(self.workflow_versions[workflow_id].keys())
            versions.sort(reverse=True)
            return versions[0]
        return "1.0.0"

    async def get_workflow_execution_history(
        self, workflow_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get execution history for a workflow"""
        executions = []

        for execution_id, execution_context in self.execution_history.items():
            if execution_context.get("workflow_id") == workflow_id:
                executions.append(execution_context)

        # Sort by start time (most recent first)
        executions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        return executions[:limit]

    def create_workflow_version(
        self, workflow_id: str, new_version: str, changes: Dict[str, Any]
    ) -> bool:
        """Create a new version of a workflow"""
        if workflow_id not in self.workflow_versions:
            return False

        # Get latest version
        latest_version = self._get_latest_version(workflow_id)
        latest_workflow = self.workflow_versions[workflow_id][latest_version]

        # Create new version with changes
        new_workflow = copy.deepcopy(latest_workflow)
        new_workflow["version"] = new_version
        new_workflow["updated_at"] = datetime.now().isoformat()

        # Apply changes
        if "nodes" in changes:
            new_workflow["nodes"] = changes["nodes"]
        if "connections" in changes:
            new_workflow["connections"] = changes["connections"]
        if "name" in changes:
            new_workflow["name"] = changes["name"]
        if "description" in changes:
            new_workflow["description"] = changes["description"]

        # Store new version
        self.workflow_versions[workflow_id][new_version] = new_workflow

        logger.info(f"Created version {new_version} for workflow {workflow_id}")
        return True

    def rollback_workflow_version(self, workflow_id: str, target_version: str) -> bool:
        """Rollback workflow to a previous version"""
        if workflow_id not in self.workflow_versions:
            return False

        if target_version not in self.workflow_versions[workflow_id]:
            return False

        # Get current latest version
        latest_version = self._get_latest_version(workflow_id)

        # Create rollback version
        rollback_version = f"rollback-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        rollback_workflow = copy.deepcopy(
            self.workflow_versions[workflow_id][target_version]
        )
        rollback_workflow["version"] = rollback_version
        rollback_workflow["updated_at"] = datetime.now().isoformat()

        # Store rollback version
        self.workflow_versions[workflow_id][rollback_version] = rollback_workflow

        logger.info(
            f"Rolled back workflow {workflow_id} from {latest_version} to {target_version}"
        )
        return True
