#!/usr/bin/env python3
"""
🔄 Cross-Integration Workflow Engine
Enables workflows that span multiple integrations
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class WorkflowStep:
    """Individual workflow step"""
    id: str
    name: str
    integration: str
    action: str
    parameters: Dict[str, Any]
    depends_on: Optional[List[str]] = None
    condition: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class WorkflowExecution:
    """Workflow execution context"""
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[WorkflowStep] = None
    results: Dict[str, Any] = None
    error: Optional[str] = None

class IntegrationConnector:
    """Connector for different integration APIs"""
    
    def __init__(self):
        self.connections: Dict[str, Any] = {}
    
    async def get_connection(self, integration: str, user_id: str):
        """Get connection for an integration"""
        # In production, this would retrieve from secure database
        connection_key = f"{integration}_{user_id}"
        
        if connection_key not in self.connections:
            # Mock connection - in production would use real OAuth tokens
            self.connections[connection_key] = {
                'integration': integration,
                'user_id': user_id,
                'access_token': 'mock_token_' + integration,
                'connected_at': datetime.now(timezone.utc)
            }
        
        return self.connections[connection_key]
    
    async def execute_action(self, integration: str, action: str, parameters: Dict[str, Any], user_id: str):
        """Execute action on an integration"""
        try:
            connection = await self.get_connection(integration, user_id)
            
            if not connection:
                raise Exception(f"No connection found for {integration}")
            
            # Route to appropriate integration connector
            if integration == 'github':
                return await self._execute_github_action(action, parameters, connection)
            elif integration == 'notion':
                return await self._execute_notion_action(action, parameters, connection)
            elif integration == 'slack':
                return await self._execute_slack_action(action, parameters, connection)
            elif integration == 'linear':
                return await self._execute_linear_action(action, parameters, connection)
            elif integration == 'jira':
                return await self._execute_jira_action(action, parameters, connection)
            else:
                raise Exception(f"Integration {integration} not supported")
        
        except Exception as e:
            logger.error(f"Failed to execute {integration}.{action}: {e}")
            raise
    
    async def _execute_github_action(self, action: str, parameters: Dict[str, Any], connection: Dict[str, Any]):
        """Execute GitHub action"""
        if action == 'create_issue':
            return {
                'success': True,
                'data': {
                    'issue_id': f'GH-{int(datetime.now().timestamp())}',
                    'title': parameters.get('title'),
                    'body': parameters.get('body'),
                    'repository': parameters.get('repository'),
                    'url': f"https://github.com/{parameters.get('repository')}/issues/{int(datetime.now().timestamp())}"
                },
                'integration': 'github'
            }
        elif action == 'get_repositories':
            return {
                'success': True,
                'data': [
                    {'name': 'atom-project', 'url': 'https://github.com/user/atom-project'},
                    {'name': 'example-repo', 'url': 'https://github.com/user/example-repo'}
                ],
                'integration': 'github'
            }
        else:
            raise Exception(f"GitHub action {action} not implemented")
    
    async def _execute_notion_action(self, action: str, parameters: Dict[str, Any], connection: Dict[str, Any]):
        """Execute Notion action"""
        if action == 'create_page':
            return {
                'success': True,
                'data': {
                    'page_id': f'NOTION-{int(datetime.now().timestamp())}',
                    'title': parameters.get('title'),
                    'url': f"https://notion.so/page-{int(datetime.now().timestamp())}"
                },
                'integration': 'notion'
            }
        elif action == 'get_pages':
            return {
                'success': True,
                'data': [
                    {'title': 'Project Notes', 'id': 'page-1'},
                    {'title': 'Meeting Notes', 'id': 'page-2'}
                ],
                'integration': 'notion'
            }
        else:
            raise Exception(f"Notion action {action} not implemented")
    
    async def _execute_slack_action(self, action: str, parameters: Dict[str, Any], connection: Dict[str, Any]):
        """Execute Slack action"""
        if action == 'send_message':
            return {
                'success': True,
                'data': {
                    'message_id': f'SLACK-{int(datetime.now().timestamp())}',
                    'channel': parameters.get('channel'),
                    'text': parameters.get('text'),
                    'ts': datetime.now().timestamp()
                },
                'integration': 'slack'
            }
        elif action == 'get_channels':
            return {
                'success': True,
                'data': [
                    {'name': 'general', 'id': 'C123456'},
                    {'name': 'dev-team', 'id': 'C789012'}
                ],
                'integration': 'slack'
            }
        else:
            raise Exception(f"Slack action {action} not implemented")
    
    async def _execute_linear_action(self, action: str, parameters: Dict[str, Any], connection: Dict[str, Any]):
        """Execute Linear action"""
        if action == 'create_issue':
            return {
                'success': True,
                'data': {
                    'issue_id': f'LIN-{int(datetime.now().timestamp())}',
                    'title': parameters.get('title'),
                    'description': parameters.get('description'),
                    'team_id': parameters.get('team_id'),
                    'url': f"https://linear.app/issue/{int(datetime.now().timestamp())}"
                },
                'integration': 'linear'
            }
        else:
            raise Exception(f"Linear action {action} not implemented")
    
    async def _execute_jira_action(self, action: str, parameters: Dict[str, Any], connection: Dict[str, Any]):
        """Execute Jira action"""
        if action == 'create_issue':
            return {
                'success': True,
                'data': {
                    'issue_key': f'JIRA-{int(datetime.now().timestamp())}',
                    'summary': parameters.get('summary'),
                    'description': parameters.get('description'),
                    'project_key': parameters.get('project_key'),
                    'url': f"https://your-domain.atlassian.net/browse/JIRA-{int(datetime.now().timestamp())}"
                },
                'integration': 'jira'
            }
        else:
            raise Exception(f"Jira action {action} not implemented")

class WorkflowEngine:
    """Main workflow orchestration engine"""
    
    def __init__(self):
        self.connector = IntegrationConnector()
        self.active_workflows: Dict[str, WorkflowExecution] = {}
        self.workflow_templates: Dict[str, List[WorkflowStep]] = {}
        
        # Initialize built-in workflow templates
        self._initialize_workflow_templates()
    
    def _initialize_workflow_templates(self):
        """Initialize built-in workflow templates"""
        
        # GitHub → Linear Issue Sync
        self.workflow_templates['github_linear_sync'] = [
            WorkflowStep(
                id='step1',
                name='Get GitHub Issues',
                integration='github',
                action='get_repositories',
                parameters={},
                depends_on=None
            ),
            WorkflowStep(
                id='step2',
                name='Create Linear Issues',
                integration='linear',
                action='create_issue',
                parameters={
                    'title': '{{step1.data[0].name}} Repository Issue',
                    'description': 'Auto-synced from GitHub',
                    'team_id': 'team-1'
                },
                depends_on=['step1']
            )
        ]
        
        # Notion → Slack Notification
        self.workflow_templates['notion_slack_notify'] = [
            WorkflowStep(
                id='step1',
                name='Get Notion Pages',
                integration='notion',
                action='get_pages',
                parameters={},
                depends_on=None
            ),
            WorkflowStep(
                id='step2',
                name='Send Slack Notification',
                integration='slack',
                action='send_message',
                parameters={
                    'channel': 'general',
                    'text': 'New Notion page created: {{step1.data[0].title}}'
                },
                depends_on=['step1']
            )
        ]
        
        # Jira → Slack Update
        self.workflow_templates['jira_slack_update'] = [
            WorkflowStep(
                id='step1',
                name='Create Jira Issue',
                integration='jira',
                action='create_issue',
                parameters={
                    'summary': 'Auto-generated issue',
                    'description': 'Created from workflow',
                    'project_key': 'PROJ'
                },
                depends_on=None
            ),
            WorkflowStep(
                id='step2',
                name='Notify Slack',
                integration='slack',
                action='send_message',
                parameters={
                    'channel': 'dev-team',
                    'text': 'New Jira issue created: {{step1.data.issue_key}} - {{step1.data.summary}}'
                },
                depends_on=['step1']
            )
        ]
    
    async def start_workflow(self, workflow_id: str, workflow_name: str, user_id: str, template_name: Optional[str] = None, custom_steps: Optional[List[WorkflowStep]] = None) -> WorkflowExecution:
        """Start a new workflow execution"""
        
        # Get workflow steps
        if template_name and template_name in self.workflow_templates:
            steps = self.workflow_templates[template_name]
        elif custom_steps:
            steps = custom_steps
        else:
            raise Exception("Either template_name or custom_steps must be provided")
        
        # Create workflow execution
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            steps=steps,
            results={}
        )
        
        self.active_workflows[workflow_id] = execution
        
        try:
            # Execute workflow
            await self._execute_workflow(execution, user_id)
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            logger.error(f"Workflow {workflow_id} failed: {e}")
        
        return execution
    
    async def _execute_workflow(self, execution: WorkflowExecution, user_id: str):
        """Execute workflow steps"""
        
        # Topological sort of steps based on dependencies
        sorted_steps = self._sort_steps(execution.steps)
        
        for step in sorted_steps:
            # Check if dependencies are completed
            if step.depends_on:
                for dep_id in step.depends_on:
                    if dep_id not in execution.results or not execution.results[dep_id].get('success'):
                        raise Exception(f"Dependency {dep_id} not completed for step {step.id}")
            
            # Check condition if specified
            if step.condition and not self._evaluate_condition(step.condition, execution.results):
                logger.info(f"Skipping step {step.id} due to condition: {step.condition}")
                execution.results[step.id] = {'success': True, 'skipped': True}
                continue
            
            # Execute step with retry logic
            for attempt in range(step.max_retries + 1):
                try:
                    # Parameter substitution
                    resolved_parameters = self._substitute_parameters(step.parameters, execution.results)
                    
                    # Execute the step
                    result = await self.connector.execute_action(
                        step.integration,
                        step.action,
                        resolved_parameters,
                        user_id
                    )
                    
                    execution.results[step.id] = result
                    logger.info(f"Step {step.id} completed successfully")
                    break
                    
                except Exception as e:
                    step.retry_count = attempt
                    if attempt < step.max_retries:
                        logger.warning(f"Step {step.id} failed, retrying ({attempt + 1}/{step.max_retries}): {e}")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(f"Step {step.id} failed after {step.max_retries} retries: {e}")
                        execution.results[step.id] = {'success': False, 'error': str(e)}
                        raise
    
    def _sort_steps(self, steps: List[WorkflowStep]) -> List[WorkflowStep]:
        """Sort workflow steps based on dependencies"""
        # Simple topological sort
        sorted_steps = []
        remaining_steps = steps.copy()
        
        while remaining_steps:
            # Find steps with no remaining dependencies
            ready_steps = [step for step in remaining_steps if not step.depends_on or 
                          all(dep in [s.id for s in sorted_steps] for dep in step.depends_on)]
            
            if not ready_steps:
                raise Exception("Circular dependency detected in workflow steps")
            
            for step in ready_steps:
                sorted_steps.append(step)
                remaining_steps.remove(step)
        
        return sorted_steps
    
    def _substitute_parameters(self, parameters: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute template parameters with actual values"""
        import re
        
        def substitute_value(value):
            if isinstance(value, str):
                # Replace {{step_id.field}} with actual values
                pattern = r'\{\{(\w+)\.(\w+)\}\}'
                def replace(match):
                    step_id = match.group(1)
                    field = match.group(2)
                    
                    if step_id in results and results[step_id].get('success'):
                        data = results[step_id].get('data', {})
                        return str(self._get_nested_value(data, field, match.group(0)))
                    return match.group(0)
                
                return re.sub(pattern, replace, value)
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            return value
        
        return substitute_value(parameters)
    
    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get nested value from data using dot notation"""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                index = int(key)
                current = current[index] if index < len(current) else default
            else:
                return default
        
        return current if current is not None else default
    
    def _evaluate_condition(self, condition: str, results: Dict[str, Any]) -> bool:
        """Evaluate workflow condition"""
        # Simple condition evaluation
        # In production, this would use a proper expression parser
        try:
            # Replace step references with actual values
            for step_id, result in results.items():
                if result.get('success'):
                    condition = condition.replace(f'step_{step_id}', 'True')
            
            # Evaluate as Python expression
            return eval(condition, {'__builtins__': {}}, {'True': True, 'False': False})
        except:
            return False
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowExecution]:
        """Get status of a workflow"""
        return self.active_workflows.get(workflow_id)
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow"""
        if workflow_id in self.active_workflows:
            execution = self.active_workflows[workflow_id]
            if execution.status in [WorkflowStatus.RUNNING, WorkflowStatus.PENDING]:
                execution.status = WorkflowStatus.CANCELLED
                execution.completed_at = datetime.now(timezone.utc)
                return True
        return False
    
    def list_workflow_templates(self) -> Dict[str, Dict[str, Any]]:
        """List available workflow templates"""
        return {
            'github_linear_sync': {
                'name': 'GitHub → Linear Issue Sync',
                'description': 'Automatically create Linear issues from GitHub repositories',
                'steps': len(self.workflow_templates['github_linear_sync']),
                'integrations': ['github', 'linear']
            },
            'notion_slack_notify': {
                'name': 'Notion → Slack Notification',
                'description': 'Send Slack notifications for new Notion pages',
                'steps': len(self.workflow_templates['notion_slack_notify']),
                'integrations': ['notion', 'slack']
            },
            'jira_slack_update': {
                'name': 'Jira → Slack Update',
                'description': 'Create Jira issues and notify in Slack',
                'steps': len(self.workflow_templates['jira_slack_update']),
                'integrations': ['jira', 'slack']
            }
        }

# Global workflow engine instance
workflow_engine = WorkflowEngine()

# Export for use in routes
__all__ = [
    'WorkflowEngine',
    'workflow_engine',
    'WorkflowStep',
    'WorkflowExecution',
    'WorkflowStatus',
    'IntegrationConnector'
]