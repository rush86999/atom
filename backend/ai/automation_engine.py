import asyncio
import json
import logging
import uuid
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from integrations.gmail_service import get_gmail_service
from integrations.slack_enhanced_service import SlackEnhancedService
from services.agent_service import agent_service
from core.oauth_handler import SLACK_OAUTH_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of automation triggers"""

    SCHEDULED = "scheduled"
    EVENT_BASED = "event_based"
    MANUAL = "manual"
    API_CALL = "api_call"


class ActionType(Enum):
    """Types of automation actions"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NOTIFY = "notify"
    SEARCH = "search"
    SYNC = "sync"
    TRANSFORM = "transform"


class PlatformType(Enum):
    """Supported platform types for automation"""

    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    GMAIL = "gmail"
    GOOGLE_CHAT = "google_chat"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    ZOOM = "zoom"
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    BOX = "box"
    ONEDRIVE = "onedrive"
    GITHUB = "github"
    ASANA = "asana"
    NOTION = "notion"
    LINEAR = "linear"
    MONDAY = "monday"
    TRELLO = "trello"
    JIRA = "jira"
    GITLAB = "gitlab"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    INTERCOM = "intercom"
    FRESHDESK = "freshdesk"
    ZENDESK = "zendesk"
    STRIPE = "stripe"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    MAILCHIMP = "mailchimp"
    HUBSPOT_MARKETING = "hubspot_marketing"
    TABLEAU = "tableau"
    GOOGLE_ANALYTICS = "google_analytics"
    FIGMA = "figma"
    SHOPIFY = "shopify"


@dataclass
class AutomationTrigger:
    """Definition of an automation trigger"""

    trigger_id: str
    trigger_type: TriggerType
    platform: PlatformType
    event_name: str
    conditions: Dict[str, Any]
    description: str
    is_active: bool = True


@dataclass
class AutomationAction:
    """Definition of an automation action"""

    action_id: str
    action_type: ActionType
    platform: PlatformType
    target_entity: str
    parameters: Dict[str, Any]
    description: str


@dataclass
class AutomationWorkflow:
    """Complete automation workflow definition"""

    workflow_id: str
    name: str
    description: str
    trigger: AutomationTrigger
    actions: List[AutomationAction]
    conditions: List[Dict[str, Any]]
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class WorkflowExecution:
    """Record of workflow execution"""

    execution_id: str
    workflow_id: str
    trigger_data: Dict[str, Any]
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    actions_executed: List[str] = None
    errors: List[str] = None
    results: Dict[str, Any] = None
    duration_ms: float = 0.0

    def __post_init__(self):
        if self.actions_executed is None:
            self.actions_executed = []
        if self.errors is None:
            self.errors = []
        if self.results is None:
            self.results = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "trigger_data": self.trigger_data,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "actions_executed": self.actions_executed,
            "errors": self.errors,
            "results": self.results,
            "duration_ms": self.duration_ms
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowExecution':
        """Create from dictionary"""
        execution = cls(
            execution_id=data["execution_id"],
            workflow_id=data["workflow_id"],
            trigger_data=data.get("trigger_data", {}),
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else datetime.now(),
            status=data.get("status", "unknown")
        )
        execution.end_time = datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None
        execution.actions_executed = data.get("actions_executed", [])
        execution.errors = data.get("errors", [])
        execution.results = data.get("results", {})
        execution.duration_ms = data.get("duration_ms", 0.0)
        return execution


class AutomationEngine:
    """Cross-Platform Automation Engine for ATOM Platform"""

    def __init__(self):
        self.workflows: Dict[str, AutomationWorkflow] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.executions_file = "executions.json"
        self._load_executions()
        
        self.slack_service = SlackEnhancedService({
            "client_id": SLACK_OAUTH_CONFIG.client_id,
            "client_secret": SLACK_OAUTH_CONFIG.client_secret,
            "signing_secret": "dummy", # Not needed for sending messages
            "redirect_uri": SLACK_OAUTH_CONFIG.redirect_uri
        })
        self.platform_connectors = self._initialize_platform_connectors()
        self.action_handlers = self._initialize_action_handlers()

    def _load_executions(self):
        """Load executions from file"""
        try:
            if os.path.exists(self.executions_file):
                with open(self.executions_file, 'r') as f:
                    data = json.load(f)
                    for exec_data in data:
                        execution = WorkflowExecution.from_dict(exec_data)
                        self.executions[execution.execution_id] = execution
                logger.info(f"Loaded {len(self.executions)} executions from {self.executions_file}")
        except Exception as e:
            logger.error(f"Error loading executions: {e}")

    def _save_execution(self, execution: WorkflowExecution):
        """Save execution to file"""
        try:
            self.executions[execution.execution_id] = execution
            
            # Convert all executions to dict list
            data = [e.to_dict() for e in self.executions.values()]
            
            with open(self.executions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving execution: {e}")

    def _initialize_platform_connectors(self) -> Dict[PlatformType, callable]:
        """Initialize platform action connectors"""
        # In production, these would be actual API connectors
        connectors = {platform: self._mock_platform_connector for platform in PlatformType}
        
        # Override with real connectors where available
        connectors[PlatformType.SLACK] = self._slack_connector
        # Gmail is not in PlatformType enum explicitly but might be mapped from GOOGLE_DRIVE or added
        # Assuming we use a generic google connector or add GMAIL to enum if needed.
        # For now, let's add a specific check in the mock connector or just use _gmail_connector if we add GMAIL type.
        # But wait, PlatformType doesn't have GMAIL. It has GOOGLE_CHAT, GOOGLE_DRIVE.
        # I should probably add GMAIL to PlatformType or just map it.
        # Let's assume we can use a custom string or just add it.
        # For this task, I'll add GMAIL to PlatformType enum first.
        
        # Override with real connectors where available
        connectors[PlatformType.SLACK] = self._slack_connector
        connectors[PlatformType.GMAIL] = self._gmail_connector
        
        return connectors

    def _initialize_action_handlers(self) -> Dict[ActionType, callable]:
        """Initialize action handler functions"""
        return {
            ActionType.CREATE: self._handle_create_action,
            ActionType.UPDATE: self._handle_update_action,
            ActionType.DELETE: self._handle_delete_action,
            ActionType.NOTIFY: self._handle_notify_action,
            ActionType.SEARCH: self._handle_search_action,
            ActionType.SYNC: self._handle_sync_action,
            ActionType.TRANSFORM: self._handle_transform_action,
        }

    def create_workflow(self, workflow_data: Dict[str, Any]) -> AutomationWorkflow:
        """Create a new automation workflow"""
        workflow_id = str(uuid.uuid4())

        # Create trigger
        trigger = AutomationTrigger(
            trigger_id=str(uuid.uuid4()),
            trigger_type=TriggerType(workflow_data["trigger"]["type"]),
            platform=PlatformType(workflow_data["trigger"]["platform"]),
            event_name=workflow_data["trigger"]["event_name"],
            conditions=workflow_data["trigger"].get("conditions", {}),
            description=workflow_data["trigger"]["description"],
        )

        # Create actions
        actions = []
        for action_data in workflow_data["actions"]:
            action = AutomationAction(
                action_id=str(uuid.uuid4()),
                action_type=ActionType(action_data["type"]),
                platform=PlatformType(action_data["platform"]),
                target_entity=action_data["target_entity"],
                parameters=action_data.get("parameters", {}),
                description=action_data["description"],
            )
            actions.append(action)

        # Create workflow
        workflow = AutomationWorkflow(
            workflow_id=workflow_id,
            name=workflow_data["name"],
            description=workflow_data["description"],
            trigger=trigger,
            actions=actions,
            conditions=workflow_data.get("conditions", []),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.workflows[workflow_id] = workflow
        logger.info(f"Created workflow: {workflow.name} (ID: {workflow_id})")
        return workflow

    async def execute_workflow(
        self, workflow_id: str, trigger_data: Dict[str, Any]
    ) -> WorkflowExecution:
        """Execute an automation workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        if not workflow.is_active:
            raise ValueError(f"Workflow {workflow_id} is not active")

        # Create execution record
        execution = WorkflowExecution(
            execution_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            trigger_data=trigger_data,
            start_time=datetime.now(),
        )
        self.executions[execution.execution_id] = execution

        logger.info(f"Starting workflow execution: {workflow.name}")

        try:
            # Check conditions
            if not await self._check_conditions(workflow.conditions, trigger_data):
                execution.status = "skipped"
                execution.end_time = datetime.now()
                execution.errors.append("Conditions not met")
                return execution

            # Execute actions in sequence
            for action in workflow.actions:
                try:
                    result = await self._execute_action(action, trigger_data)
                    execution.actions_executed.append(action.action_id)
                    execution.results[action.action_id] = result
                    logger.info(f"Executed action: {action.description}")
                except Exception as e:
                    error_msg = f"Action {action.action_id} failed: {str(e)}"
                    execution.errors.append(error_msg)
                    logger.error(f"Error executing {action.action_type.value} action on {action.platform.value}: {str(e)}")
                    execution.errors.append(f"{action.action_id}: {str(e)}")
                    # Continue with next action (configurable behavior)

            execution.status = "completed"
            execution.end_time = datetime.now()
            logger.info(f"Workflow {workflow.workflow_id} completed with status: {execution.status}")

        except Exception as e:
            execution.status = "failed"
            execution.end_time = datetime.now()
            execution.errors.append(f"Workflow execution failed: {str(e)}")
            logger.error(f"Workflow execution failed: {str(e)}")

        # Calculate duration
        if execution.end_time and execution.start_time:
            execution.duration_ms = (execution.end_time - execution.start_time).total_seconds() * 1000

        self._save_execution(execution)
        return execution

    async def _check_conditions(
        self, conditions: List[Dict[str, Any]], trigger_data: Dict[str, Any]
    ) -> bool:
        """Check if all conditions are met"""
        for condition in conditions:
            condition_type = condition.get("type")
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            # Get field value from trigger data
            field_value = trigger_data.get(field)

            if not self._evaluate_condition(field_value, operator, value):
                return False

        return True

    def _evaluate_condition(
        self, field_value: Any, operator: str, expected_value: Any
    ) -> bool:
        """Evaluate a single condition"""
        if operator == "equals":
            return field_value == expected_value
        elif operator == "not_equals":
            return field_value != expected_value
        elif operator == "contains":
            return expected_value in str(field_value)
        elif operator == "greater_than":
            return float(field_value) > float(expected_value)
        elif operator == "less_than":
            return float(field_value) < float(expected_value)
        elif operator == "exists":
            return field_value is not None
        elif operator == "not_exists":
            return field_value is None
        else:
            logger.warning(f"Unknown operator: {operator}")
            return True  # Default to true for unknown operators

    async def _execute_action(
        self, action: AutomationAction, trigger_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single automation action"""
        handler = self.action_handlers.get(action.action_type)
        if not handler:
            raise ValueError(f"No handler for action type: {action.action_type}")

        # Merge trigger data with action parameters
        execution_data = {**trigger_data, **action.parameters}

        result = await handler(action, execution_data)
        return result

    async def _handle_create_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle create actions"""
        platform_connector = self.platform_connectors.get(action.platform)
        if not platform_connector:
            raise ValueError(f"No connector for platform: {action.platform}")

        # Mock implementation - in production, this would call actual APIs
        result = await platform_connector("create", action.target_entity, data)
        return {"success": True, "created_id": str(uuid.uuid4()), "data": result}

    async def _handle_update_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle update actions"""
        platform_connector = self.platform_connectors.get(action.platform)
        if not platform_connector:
            raise ValueError(f"No connector for platform: {action.platform}")

        # Mock implementation
        result = await platform_connector("update", action.target_entity, data)
        return {"success": True, "updated_id": data.get("id"), "data": result}

    async def _handle_delete_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle delete actions"""
        platform_connector = self.platform_connectors.get(action.platform)
        if not platform_connector:
            raise ValueError(f"No connector for platform: {action.platform}")

        # Mock implementation
        result = await platform_connector("delete", action.target_entity, data)
        return {"success": True, "deleted_id": data.get("id"), "data": result}

    async def _handle_notify_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle notification actions"""
        platform_connector = self.platform_connectors.get(action.platform)
        if not platform_connector:
            raise ValueError(f"No connector for platform: {action.platform}")

        # Mock implementation
        result = await platform_connector("notify", action.target_entity, data)
        return {"success": True, "notification_sent": True, "data": result}

    async def _handle_search_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle search actions"""
        platform_connector = self.platform_connectors.get(action.platform)
        if not platform_connector:
            raise ValueError(f"No connector for platform: {action.platform}")

        # Mock implementation
        result = await platform_connector("search", action.target_entity, data)
        return {"success": True, "results": result, "count": len(result)}

    async def _handle_sync_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle sync actions between platforms"""
        # This would synchronize data between different platforms
        source_platform = data.get("source_platform")
        target_platform = action.platform

        # Mock implementation
        return {
            "success": True,
            "synced_items": 5,
            "input_data": data,
            "output_data": {"transformed": True, **data},
        }

    async def _handle_transform_action(
        self, action: AutomationAction, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle data transformation actions"""
        # This would transform data from one format to another
        transformation_type = data.get("transformation_type", "default")

        # Mock implementation
        return {
            "success": True,
            "transformation_type": transformation_type,
            "input_data": data,
            "output_data": {"transformed": True, **data},
        }

    async def _mock_platform_connector(
        self, operation: str, entity: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock connector for platforms without real implementation"""
        logger.info(
            f"Mock execution for platform: {operation} on {entity}"
        )
        return {
            "operation": operation,
            "entity": entity,
            "platform": "mock",
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

    async def _slack_connector(
        self, operation: str, entity: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Real Slack connector"""
        if operation == "notify":
            channel = data.get("channel")
            message = data.get("message")
            # We need a workspace_id. For MVP, we might need to look it up or pass it in data.
            # If not provided, we might default to the first available workspace in token storage?
            # Or just fail if not provided.
            # Let's try to get it from data or token storage.
            workspace_id = data.get("workspace_id")
            
            # If no workspace_id, try to find one from token storage (hack for MVP)
            if not workspace_id:
                from core.token_storage import token_storage
                token = token_storage.get_token("slack")
                if token:
                    workspace_id = token.get("team", {}).get("id")
            
            if workspace_id and channel and message:
                result = await self.slack_service.send_message(workspace_id, channel, message)
                return {"success": result.get("ok", False), "data": result}
            else:
                raise ValueError("Missing workspace_id, channel, or message for Slack notification")
        
        return await self._mock_platform_connector(operation, entity, data)

    async def _gmail_connector(
        self, operation: str, entity: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Real Gmail connector"""
        service = get_gmail_service()
        
        if operation == "notify" or operation == "create":
            to = data.get("to")
            subject = data.get("subject")
            body = data.get("body") or data.get("message")
            
            if to and subject and body:
                result = service.send_message(to, subject, body)
                return {"success": bool(result), "data": result}
            else:
                raise ValueError("Missing to, subject, or body for Gmail message")
                
        elif operation == "search":
            query = data.get("query", "")
            messages = service.search_messages(query)
            return {"success": True, "data": messages, "count": len(messages)}
            
        return await self._mock_platform_connector(operation, entity, data)

    def get_workflow(self, workflow_id: str) -> Optional[AutomationWorkflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)

    def list_workflows(self, active_only: bool = True) -> List[AutomationWorkflow]:
        """List all workflows"""
        workflows = list(self.workflows.values())
        if active_only:
            workflows = [w for w in workflows if w.is_active]
        return workflows

    def update_workflow(
        self, workflow_id: str, updates: Dict[str, Any]
    ) -> AutomationWorkflow:
        """Update an existing workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Update fields
        if "name" in updates:
            workflow.name = updates["name"]
        if "description" in updates:
            workflow.description = updates["description"]
        if "is_active" in updates:
            workflow.is_active = updates["is_active"]
        if "conditions" in updates:
            workflow.conditions = updates["conditions"]

        workflow.updated_at = datetime.now()
        logger.info(f"Updated workflow: {workflow.name}")
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            logger.info(f"Deleted workflow: {workflow_id}")
            return True
        return False

    async def execute_workflow_definition(self, workflow_def: Dict[str, Any], input_data: Dict[str, Any] = None, execution_id: str = None) -> Dict[str, Any]:
        """
        Execute a workflow from its definition (as stored in workflows.json)
        
        Args:
            workflow_def: Workflow definition with nodes and connections
            input_data: Optional input data for the workflow
            execution_id: Optional ID for this execution
            
        Returns:
            Execution results and metadata
        """
        results = []
        input_data = input_data or {}
        execution_id = execution_id or str(uuid.uuid4())
        
        logger.info(f"Executing workflow: {workflow_def.get('name')} (ID: {execution_id})")
        
        # Create execution record
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_def.get('id'),
            trigger_data=input_data,
            start_time=datetime.now(),
            status="running"
        )
        self.executions[execution_id] = execution
        
        # Execute each node in order
        for node in workflow_def.get('nodes', []):
            node_result = {
                "node_id": node['id'],
                "node_type": node['type'],
                "node_title": node['title'],
                "status": "pending",
                "output": None,
                "error": None
            }
            
            try:
                if node['type'] == 'action':
                    # Get node configuration
                    config = node.get('config', {})
                    action_type = config.get('actionType')
                    integration_id = config.get('integrationId')
                    
                    logger.info(f"Executing action node: {node['title']} (action: {action_type}, integration: {integration_id})")
                    
                    # Execute based on action type and integration
                    if action_type == 'send_email' and integration_id == 'gmail':
                        # Execute Gmail send email
                        gmail_service = get_gmail_service()
                        result = gmail_service.send_message(
                            to=config.get('to', ''),
                            subject=config.get('subject', 'No Subject'),
                            body=config.get('body', '')
                        )
                        node_result['output'] = result
                        node_result['status'] = "success"
                        
                    elif action_type == 'notify' and integration_id == 'slack':
                        # Execute Slack notification
                        result = await self.slack_service.send_message(
                            channel=config.get('channel', '#general'),
                            message=config.get('message', '')
                        )
                        node_result['output'] = result
                        node_result['status'] = "success"
                        

                    elif action_type == 'run_agent_task':
                        # Execute Computer Use Agent Task
                        goal = config.get('goal', '')
                        mode = config.get('mode', 'thinker')
                        
                        logger.info(f"Starting agent task: {goal} ({mode})")
                        
                        # Start agent task
                        param_result = await agent_service.execute_task(goal, mode)
                        
                        node_result['output'] = param_result
                        node_result['status'] = "success"

                    else:
                        # Unsupported action type
                        node_result['status'] = "skipped"
                        node_result['output'] = f"Action type '{action_type}' with integration '{integration_id}' not yet implemented"
                        
                elif node['type'] == 'trigger':
                    # Trigger nodes don't execute, they just define when the workflow runs
                    node_result['status'] = "success"
                    node_result['output'] = "Trigger node (manual execution)"
                    
                else:
                    # Other node types (condition, delay, etc.)
                    node_result['status'] = "skipped"
                    node_result['output'] = f"Node type '{node['type']}' not yet implemented"
                    
            except Exception as e:
                logger.error(f"Error executing node {node['id']}: {e}")
                node_result['status'] = "failed"
                node_result['error'] = str(e)
                execution.errors.append(f"Node {node['id']}: {str(e)}")
            
            results.append(node_result)
            execution.actions_executed.append(node['id'])
            execution.results[node['id']] = node_result
            
            # If any node fails, mark execution as failed (or continue based on policy)
            if node_result['status'] == 'failed':
                execution.status = "failed"
        
        # Finalize execution record
        if execution.status == "running":
            execution.status = "completed"
            
        execution.end_time = datetime.now()
        if execution.start_time:
            execution.duration_ms = (execution.end_time - execution.start_time).total_seconds() * 1000
            
        self._save_execution(execution)
        
        logger.info(f"Workflow execution complete with {len(results)} nodes processed")
        return results

    def get_execution_history(
        self, workflow_id: str, limit: int = 10
    ) -> List[WorkflowExecution]:
        """Get execution history for a workflow"""
        executions = [
            e for e in self.executions.values() if e.workflow_id == workflow_id
        ]
        executions.sort(key=lambda x: x.start_time, reverse=True)
        return executions[:limit]





# Example usage and testing
async def main():
    """Test the automation engine"""
    engine = AutomationEngine()

    # Create a sample workflow
    workflow_data = {
        "name": "Daily Team Update",
        "description": "Send daily team updates and create follow-up tasks",
        "trigger": {
            "type": "scheduled",
            "platform": "slack",
            "event_name": "daily_reminder",
            "conditions": {"time": "09:00", "weekday": "mon-fri"},
            "description": "Triggered every weekday at 9 AM",
        },
        "actions": [
            {
                "type": "search",
                "platform": "asana",
                "target_entity": "tasks",
                "parameters": {"status": "today", "assignee": "team"},
                "description": "Find today's tasks for the team",
            },
            {
                "type": "notify",
                "platform": "slack",
                "target_entity": "channel",
                "parameters": {
                    "channel": "#team-updates",
                    "message": "Daily update ready",
                },
                "description": "Send notification to Slack channel",
            },
            {
                "type": "create",
                "platform": "asana",
                "target_entity": "task",
                "parameters": {
                    "name": "Follow up on daily update",
                    "assignee": "manager",
                },
                "description": "Create follow-up task",
            },
        ],
        "conditions": [
            {
                "type": "business_hours",
                "field": "time",
                "operator": "greater_than",
                "value": "08:00",
            }
        ],
    }

    # Create the workflow
    workflow = engine.create_workflow(workflow_data)
    print(f"Created workflow: {workflow.name}")

    # Execute the workflow
    trigger_data = {"time": "09:00", "weekday": "monday", "team": "engineering"}

    execution = await engine.execute_workflow(workflow.workflow_id, trigger_data)
    print(f"Execution completed with status: {execution.status}")
    print


if __name__ == "__main__":
    asyncio.run(main())
