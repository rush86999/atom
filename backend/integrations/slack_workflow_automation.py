"""
ATOM Workflow Automation - Slack Integration
Complete Slack integration with workflow automation capabilities
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Import ATOM components
try:
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from workflow_engine import WorkflowEngine
    from communication_service import CommunicationService
except ImportError:
    # Mock components for development
    AtomMemoryService = None
    AtomSearchService = None
    WorkflowEngine = None
    CommunicationService = None

logger = logging.getLogger(__name__)

class WorkflowTriggerType(Enum):
    MESSAGE = "message"
    FILE_UPLOAD = "file_upload"
    CHANNEL_CREATED = "channel_created"
    USER_JOIN = "user_join"
    MENTION = "mention"
    REACTION = "reaction"
    SCHEDULED = "scheduled"

class WorkflowActionType(Enum):
    SEND_MESSAGE = "send_message"
    CREATE_CHANNEL = "create_channel"
    INVITE_USER = "invite_user"
    UPLOAD_FILE = "upload_file"
    UPDATE_STATUS = "update_status"
    CREATE_TASK = "create_task"
    SEND_EMAIL = "send_email"
    API_CALL = "api_call"

@dataclass
class SlackWorkflowTrigger:
    """Workflow trigger configuration for Slack events"""
    id: str
    type: WorkflowTriggerType
    conditions: Dict[str, Any]
    workspace_id: str
    channel_ids: List[str]
    user_ids: List[str]
    keywords: List[str]
    active: bool = True

@dataclass
class SlackWorkflowAction:
    """Workflow action configuration for Slack operations"""
    id: str
    type: WorkflowActionType
    parameters: Dict[str, Any]
    delay_seconds: int = 0
    retry_count: int = 0
    success_message: Optional[str] = None

@dataclass
class SlackWorkflow:
    """Complete workflow definition for Slack automation"""
    id: str
    name: str
    description: str
    triggers: List[SlackWorkflowTrigger]
    actions: List[SlackWorkflowAction]
    created_by: str
    created_at: datetime
    active: bool = True
    execution_count: int = 0
    last_executed: Optional[datetime] = None

@dataclass
class WorkflowExecution:
    """Workflow execution record"""
    id: str
    workflow_id: str
    trigger_data: Dict[str, Any]
    status: str  # 'running', 'completed', 'failed'
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    action_results: List[Dict[str, Any]] = None

class SlackWorkflowAutomation:
    """Slack workflow automation system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_service = AtomMemoryService() if AtomMemoryService else None
        self.search_service = AtomSearchService() if AtomSearchService else None
        self.workflow_engine = WorkflowEngine() if WorkflowEngine else None
        self.communication_service = CommunicationService() if CommunicationService else None
        
        # Storage for workflows and executions
        self.workflows: Dict[str, SlackWorkflow] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        
        # Slack client for actions
        self.slack_clients: Dict[str, WebClient] = {}
        
        # Event handlers
        self.event_handlers: Dict[WorkflowTriggerType, List[Callable]] = {
            trigger_type: [] for trigger_type in WorkflowTriggerType
        }
        
        logger.info("Slack Workflow Automation initialized")
    
    def register_workflow(self, workflow: SlackWorkflow) -> bool:
        """Register a new workflow"""
        try:
            self.workflows[workflow.id] = workflow
            
            # Store in ATOM memory
            if self.memory_service:
                memory_data = {
                    'type': 'slack_workflow',
                    'workflow_id': workflow.id,
                    'data': asdict(workflow),
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.memory_service.store(memory_data)
            
            logger.info(f"Registered workflow: {workflow.name} ({workflow.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register workflow {workflow.id}: {e}")
            return False
    
    def unregister_workflow(self, workflow_id: str) -> bool:
        """Unregister a workflow"""
        try:
            if workflow_id in self.workflows:
                del self.workflows[workflow_id]
                
                # Remove from ATOM memory
                if self.memory_service:
                    self.memory_service.delete(f'slack_workflow:{workflow_id}')
                
                logger.info(f"Unregistered workflow: {workflow_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to unregister workflow {workflow_id}: {e}")
            return False
    
    def get_workflow(self, workflow_id: str) -> Optional[SlackWorkflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self, workspace_id: Optional[str] = None, active_only: bool = True) -> List[SlackWorkflow]:
        """List workflows with optional filtering"""
        workflows = list(self.workflows.values())
        
        if workspace_id:
            workflows = [w for w in workflows if any(t.workspace_id == workspace_id for t in w.triggers)]
        
        if active_only:
            workflows = [w for w in workflows if w.active]
        
        return sorted(workflows, key=lambda w: w.created_at, reverse=True)
    
    async def execute_workflow(self, workflow_id: str, trigger_data: Dict[str, Any]) -> WorkflowExecution:
        """Execute a workflow with given trigger data"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        execution_id = f"exec_{workflow_id}_{int(datetime.utcnow().timestamp())}"
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            trigger_data=trigger_data,
            status='running',
            started_at=datetime.utcnow(),
            action_results=[]
        )
        
        self.executions[execution_id] = execution
        
        try:
            # Update workflow execution count
            workflow.execution_count += 1
            workflow.last_executed = datetime.utcnow()
            
            # Execute actions
            for action in workflow.actions:
                if action.delay_seconds > 0:
                    await asyncio.sleep(action.delay_seconds)
                
                result = await self.execute_action(action, trigger_data)
                execution.action_results.append(result)
            
            # Mark execution as completed
            execution.status = 'completed'
            execution.completed_at = datetime.utcnow()
            
            # Store execution in ATOM memory
            if self.memory_service:
                memory_data = {
                    'type': 'workflow_execution',
                    'execution_id': execution_id,
                    'workflow_id': workflow_id,
                    'data': asdict(execution),
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.memory_service.store(memory_data)
            
            logger.info(f"Workflow execution completed: {execution_id}")
            
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            
            logger.error(f"Workflow execution failed: {execution_id} - {e}")
            
            # Retry logic
            if workflow.triggers and workflow.triggers[0].retry_count > 0:
                workflow.triggers[0].retry_count -= 1
                await asyncio.sleep(5)  # Wait before retry
                return await self.execute_workflow(workflow_id, trigger_data)
        
        return execution
    
    async def execute_action(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow action"""
        try:
            result = {
                'action_id': action.id,
                'type': action.type.value,
                'status': 'success',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if action.type == WorkflowActionType.SEND_MESSAGE:
                result.update(await self._send_message(action, trigger_data))
            
            elif action.type == WorkflowActionType.CREATE_CHANNEL:
                result.update(await self._create_channel(action, trigger_data))
            
            elif action.type == WorkflowActionType.INVITE_USER:
                result.update(await self._invite_user(action, trigger_data))
            
            elif action.type == WorkflowActionType.UPLOAD_FILE:
                result.update(await self._upload_file(action, trigger_data))
            
            elif action.type == WorkflowActionType.UPDATE_STATUS:
                result.update(await self._update_status(action, trigger_data))
            
            elif action.type == WorkflowActionType.CREATE_TASK:
                result.update(await self._create_task(action, trigger_data))
            
            elif action.type == WorkflowActionType.SEND_EMAIL:
                result.update(await self._send_email(action, trigger_data))
            
            elif action.type == WorkflowActionType.API_CALL:
                result.update(await self._make_api_call(action, trigger_data))
            
            else:
                result['status'] = 'failed'
                result['error'] = f"Unknown action type: {action.type}"
            
            # Log action completion
            if self.communication_service:
                self.communication_service.log_event({
                    'type': 'workflow_action',
                    'action_type': action.type.value,
                    'status': result['status'],
                    'workflow_id': trigger_data.get('workflow_id'),
                    'timestamp': result['timestamp']
                })
            
            return result
            
        except Exception as e:
            return {
                'action_id': action.id,
                'type': action.type.value,
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _send_message(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to Slack channel"""
        workspace_id = trigger_data.get('workspace_id')
        channel_id = self._resolve_parameter(action.parameters.get('channel'), trigger_data)
        message = self._resolve_parameter(action.parameters.get('message'), trigger_data)
        
        client = self._get_slack_client(workspace_id)
        if not client:
            raise ValueError(f"Slack client not available for workspace: {workspace_id}")
        
        # Send message
        response = await asyncio.to_thread(
            client.chat_postMessage,
            channel=channel_id,
            text=message,
            blocks=action.parameters.get('blocks')
        )
        
        return {
            'channel_id': channel_id,
            'message_id': response['ts'],
            'message': message
        }
    
    async def _create_channel(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Slack channel"""
        workspace_id = trigger_data.get('workspace_id')
        channel_name = self._resolve_parameter(action.parameters.get('name'), trigger_data)
        is_private = action.parameters.get('is_private', False)
        
        client = self._get_slack_client(workspace_id)
        if not client:
            raise ValueError(f"Slack client not available for workspace: {workspace_id}")
        
        response = await asyncio.to_thread(
            client.conversations_create,
            name=channel_name,
            is_private=is_private
        )
        
        return {
            'channel_id': response['channel']['id'],
            'channel_name': channel_name,
            'is_private': is_private
        }
    
    async def _invite_user(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invite user to channel"""
        workspace_id = trigger_data.get('workspace_id')
        channel_id = self._resolve_parameter(action.parameters.get('channel'), trigger_data)
        user_id = self._resolve_parameter(action.parameters.get('user'), trigger_data)
        
        client = self._get_slack_client(workspace_id)
        if not client:
            raise ValueError(f"Slack client not available for workspace: {workspace_id}")
        
        response = await asyncio.to_thread(
            client.conversations_invite,
            channel=channel_id,
            users=user_id
        )
        
        return {
            'channel_id': channel_id,
            'user_id': user_id,
            'invited': True
        }
    
    async def _upload_file(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to Slack"""
        workspace_id = trigger_data.get('workspace_id')
        channel_id = self._resolve_parameter(action.parameters.get('channel'), trigger_data)
        file_path = self._resolve_parameter(action.parameters.get('file_path'), trigger_data)
        
        client = self._get_slack_client(workspace_id)
        if not client:
            raise ValueError(f"Slack client not available for workspace: {workspace_id}")
        
        response = await asyncio.to_thread(
            client.files_upload_v2,
            channel=channel_id,
            file=file_path,
            initial_comment=action.parameters.get('comment')
        )
        
        return {
            'file_id': response['file']['id'],
            'file_name': response['file']['name'],
            'channel_id': channel_id
        }
    
    async def _update_status(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update Slack status"""
        workspace_id = trigger_data.get('workspace_id')
        status_text = self._resolve_parameter(action.parameters.get('status'), trigger_data)
        emoji = action.parameters.get('emoji')
        
        client = self._get_slack_client(workspace_id)
        if not client:
            raise ValueError(f"Slack client not available for workspace: {workspace_id}")
        
        response = await asyncio.to_thread(
            client.users_profile_set,
            profile={
                'status_text': status_text,
                'status_emoji': emoji
            }
        )
        
        return {
            'status_text': status_text,
            'emoji': emoji,
            'updated': True
        }
    
    async def _create_task(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create task in external system"""
        task_title = self._resolve_parameter(action.parameters.get('title'), trigger_data)
        task_description = self._resolve_parameter(action.parameters.get('description'), trigger_data)
        
        # This would integrate with your task management system
        # For now, simulate task creation
        task_id = f"task_{int(datetime.utcnow().timestamp())}"
        
        return {
            'task_id': task_id,
            'title': task_title,
            'description': task_description,
            'created': True
        }
    
    async def _send_email(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send email notification"""
        to_email = self._resolve_parameter(action.parameters.get('to'), trigger_data)
        subject = self._resolve_parameter(action.parameters.get('subject'), trigger_data)
        body = self._resolve_parameter(action.parameters.get('body'), trigger_data)
        
        # This would integrate with your email service
        # For now, simulate email sending
        email_id = f"email_{int(datetime.utcnow().timestamp())}"
        
        return {
            'email_id': email_id,
            'to': to_email,
            'subject': subject,
            'sent': True
        }
    
    async def _make_api_call(self, action: SlackWorkflowAction, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make external API call"""
        url = self._resolve_parameter(action.parameters.get('url'), trigger_data)
        method = action.parameters.get('method', 'POST')
        headers = action.parameters.get('headers', {})
        data = self._resolve_parameter(action.parameters.get('data'), trigger_data)
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data
            )
        
        return {
            'url': url,
            'method': method,
            'status_code': response.status_code,
            'response': response.json() if response.content_type == 'application/json' else response.text
        }
    
    def _resolve_parameter(self, param: Any, trigger_data: Dict[str, Any]) -> Any:
        """Resolve parameter with template substitution"""
        if isinstance(param, str) and '{' in param:
            # Simple template substitution
            result = param
            for key, value in trigger_data.items():
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    if isinstance(value, (dict, list)):
                        result = result.replace(placeholder, json.dumps(value))
                    else:
                        result = result.replace(placeholder, str(value))
            return result
        return param
    
    def _get_slack_client(self, workspace_id: str) -> Optional[WebClient]:
        """Get or create Slack client for workspace"""
        if workspace_id not in self.slack_clients:
            # Get access token for workspace
            token = self._get_workspace_token(workspace_id)
            if not token:
                logger.error(f"No access token available for workspace: {workspace_id}")
                return None
            
            self.slack_clients[workspace_id] = WebClient(token=token)
        
        return self.slack_clients[workspace_id]
    
    def _get_workspace_token(self, workspace_id: str) -> Optional[str]:
        """Get access token for workspace"""
        # This would retrieve from your token storage
        # For now, use environment variable
        return os.getenv(f'SLACK_TOKEN_{workspace_id}')
    
    async def handle_slack_event(self, event_data: Dict[str, Any]) -> List[WorkflowExecution]:
        """Handle incoming Slack event and trigger workflows"""
        executions = []
        
        try:
            event_type = event_data.get('type')
            workspace_id = event_data.get('team_id')
            channel_id = event_data.get('channel')
            user_id = event_data.get('user')
            
            # Find matching triggers
            matching_triggers = []
            for workflow in self.workflows.values():
                if not workflow.active:
                    continue
                
                for trigger in workflow.triggers:
                    if await self._evaluate_trigger(trigger, event_data):
                        matching_triggers.append((workflow, trigger, event_data))
            
            # Execute workflows for matching triggers
            for workflow, trigger, event in matching_triggers:
                execution = await self.execute_workflow(
                    workflow.id,
                    {
                        'event': event,
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': user_id,
                        'trigger_type': trigger.type.value,
                        'trigger_id': trigger.id
                    }
                )
                executions.append(execution)
            
            # Index event data for search
            if self.search_service and event_type in ['message', 'file_shared']:
                await self._index_slack_content(event_data)
            
            return executions
            
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
            return executions
    
    async def _evaluate_trigger(self, trigger: SlackWorkflowTrigger, event_data: Dict[str, Any]) -> bool:
        """Evaluate if trigger matches event data"""
        try:
            event_type = event_data.get('type')
            workspace_id = event_data.get('team_id')
            channel_id = event_data.get('channel')
            user_id = event_data.get('user')
            
            # Check trigger type
            if trigger.type == WorkflowTriggerType.MESSAGE and event_type != 'message':
                return False
            elif trigger.type == WorkflowTriggerType.FILE_UPLOAD and event_type != 'file_shared':
                return False
            elif trigger.type == WorkflowTriggerType.CHANNEL_CREATED and event_type != 'channel_created':
                return False
            elif trigger.type == WorkflowTriggerType.USER_JOIN and event_type != 'team_join':
                return False
            elif trigger.type == WorkflowTriggerType.MENTION and 'text' not in event_data:
                return False
            
            # Check workspace
            if trigger.workspace_id and trigger.workspace_id != workspace_id:
                return False
            
            # Check channels
            if trigger.channel_ids and channel_id not in trigger.channel_ids:
                return False
            
            # Check users
            if trigger.user_ids and user_id not in trigger.user_ids:
                return False
            
            # Check keywords
            if trigger.keywords:
                text = event_data.get('text', '').lower()
                if not any(keyword.lower() in text for keyword in trigger.keywords):
                    return False
            
            # Check additional conditions
            for condition_key, condition_value in trigger.conditions.items():
                if condition_key == 'time_range':
                    current_time = datetime.utcnow().hour
                    start_hour = condition_value.get('start', 0)
                    end_hour = condition_value.get('end', 23)
                    if not (start_hour <= current_time <= end_hour):
                        return False
                elif condition_key == 'user_role':
                    # Check user role in workspace
                    pass  # Would require API call
                elif condition_key in event_data:
                    if event_data[condition_key] != condition_value:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating trigger: {e}")
            return False
    
    async def _index_slack_content(self, event_data: Dict[str, Any]):
        """Index Slack content for search"""
        if not self.search_service:
            return
        
        try:
            # Prepare content for indexing
            content_data = {
                'source': 'slack',
                'type': event_data.get('type'),
                'id': event_data.get('event_ts') or event_data.get('ts'),
                'workspace_id': event_data.get('team_id'),
                'channel_id': event_data.get('channel'),
                'user_id': event_data.get('user'),
                'text': event_data.get('text', ''),
                'timestamp': event_data.get('event_ts') or event_data.get('ts'),
                'metadata': {
                    'file_details': event_data.get('file'),
                    'reactions': event_data.get('reactions', []),
                    'thread_ts': event_data.get('thread_ts')
                }
            }
            
            # Index in search service
            await self.search_service.index(content_data)
            
        except Exception as e:
            logger.error(f"Error indexing Slack content: {e}")
    
    def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID"""
        return self.executions.get(execution_id)
    
    def list_workflow_executions(self, workflow_id: Optional[str] = None, 
                               limit: int = 50) -> List[WorkflowExecution]:
        """List workflow executions with optional filtering"""
        executions = list(self.executions.values())
        
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        
        return sorted(executions, key=lambda e: e.started_at, reverse=True)[:limit]
    
    def get_workflow_stats(self, workflow_id: str) -> Dict[str, Any]:
        """Get execution statistics for workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {}
        
        executions = self.list_workflow_executions(workflow_id)
        successful_executions = [e for e in executions if e.status == 'completed']
        failed_executions = [e for e in executions if e.status == 'failed']
        
        return {
            'workflow_id': workflow_id,
            'workflow_name': workflow.name,
            'total_executions': len(executions),
            'successful_executions': len(successful_executions),
            'failed_executions': len(failed_executions),
            'success_rate': (len(successful_executions) / len(executions) * 100) if executions else 0,
            'last_execution': executions[0].started_at.isoformat() if executions else None,
            'average_duration': sum(
                (e.completed_at - e.started_at).total_seconds() 
                for e in successful_executions if e.completed_at
            ) / len(successful_executions) if successful_executions else 0
        }

# Global workflow automation instance
slack_workflow_automation = SlackWorkflowAutomation({
    'max_concurrent_executions': 10,
    'default_retry_count': 3,
    'execution_timeout_seconds': 300
})