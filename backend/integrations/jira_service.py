"""
Jira Service for ATOM Platform
Provides comprehensive Jira integration functionality
"""

import json
import logging
import os
import base64
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
import requests
from urllib.parse import urljoin, urlencode

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class JiraService(IntegrationService):
    """Jira API integration service"""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Jira service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with base_url, username, api_token
        """
        super().__init__(tenant_id=tenant_id, config=config)

        self.access_token = config.get("access_token")
        self.cloud_id = config.get("cloud_id") or config.get("instance_url")
        
        if self.access_token and self.cloud_id:
            # Construct Jira OAuth base URL using cloud_id
            self.base_url = f"https://api.atlassian.com/ex/jira/{self.cloud_id}"
            logger.info(f"JiraService using OAuth cloud_id: {self.cloud_id[:8]}...")
        else:
            self.base_url = config.get("base_url") or os.getenv('JIRA_BASE_URL')

        self.username = config.get("username") or os.getenv('JIRA_USERNAME')
        self.api_token = config.get("api_token") or os.getenv('JIRA_API_TOKEN')

        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'ATOM-Platform/1.0'
        })

        # Setup authentication
        if self.access_token:
            # OAuth token
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            logger.info(f"JiraService initialized for tenant {tenant_id[:8]}... with OAuth token")
        elif all([self.base_url, self.username, self.api_token]):
            # Basic auth
            self.base_url = self.base_url.rstrip('/')
            credentials = f"{self.username}:{self.api_token}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.session.headers.update({
                'Authorization': f'Basic {encoded_credentials}'
            })
            logger.info(f"JiraService initialized for tenant {tenant_id[:8]}... with basic auth")
        else:
            logger.warning(f"JiraService initialized for tenant {tenant_id[:8]}... without credentials")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make request with optional dynamic token"""
        token = kwargs.pop('token', None)
        headers = self.session.headers.copy()
        
        if token:
            headers['Authorization'] = f"Bearer {token}"
            
        return self.session.request(
            method=method,
            url=urljoin(self.base_url, endpoint),
            headers=headers,
            **kwargs
        )

    def test_connection(self) -> Dict[str, Any]:
        """Test Jira API connection"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/3/myself")
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "success",
                    "message": "Jira connection successful",
                    "user": user_data['displayName'],
                    "email": user_data.get('emailAddress', ''),
                    "authenticated": True
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_projects(self, start_at: int = 0, max_results: int = 50, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get Jira projects"""
        try:
            params = {
                'startAt': start_at,
                'maxResults': max_results
            }
            response = self._make_request("GET", "/rest/api/3/project", params=params, token=token)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return []
    
    def get_project(self, project_key: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get specific project details"""
        try:
            response = self._make_request("GET", f"/rest/api/3/project/{project_key}", token=token)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get project {project_key}: {e}")
            return None
    
    def search_issues(self, jql: str, start_at: int = 0, max_results: int = 50,
                   fields: List[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Search issues using JQL"""
        try:
            if fields is None:
                fields = ['summary', 'status', 'assignee', 'reporter', 'priority', 
                         'created', 'updated', 'issuetype', 'project']
            
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': max_results,
                'fields': ','.join(fields)
            }
            
            response = self._make_request("GET", "/rest/api/3/search", params=params, token=token)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to search issues: {e}")
            return {"issues": [], "total": 0, "startAt": 0, "maxResults": 0}
    
    def get_issue(self, issue_key: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get specific issue details"""
        try:
            response = self._make_request("GET", f"/rest/api/3/issue/{issue_key}", token=token)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get issue {issue_key}: {e}")
            return None
    
    def create_issue(self, project_key: str, summary: str, issue_type: str,
                   description: str = "", priority: str = None,
                   assignee: str = None, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new issue"""
        try:
            data = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{
                                "type": "text",
                                "text": description
                            }]
                        }]
                    },
                    "issuetype": {"name": issue_type}
                }
            }
            
            if priority:
                data["fields"]["priority"] = {"name": priority}
            
            if assignee:
                data["fields"]["assignee"] = {"name": assignee}
            
            response = self._make_request("POST", "/rest/api/3/issue", json=data, token=token)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            return None
    
    def update_issue(self, issue_key: str, update_data: Dict[str, Any], token: Optional[str] = None) -> bool:
        """Update an issue"""
        try:
            response = self._make_request(
                "PUT",
                f"/rest/api/3/issue/{issue_key}",
                json=update_data,
                token=token
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update issue {issue_key}: {e}")
            return False
    
    def add_comment(self, issue_key: str, body: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Add comment to issue"""
        try:
            data = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": body
                        }]
                    }]
                }
            }
            
            response = self._make_request("POST", f"/rest/api/3/issue/{issue_key}/comment", json=data, token=token)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to add comment to {issue_key}: {e}")
            return None
    
    def get_comments(self, issue_key: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get comments for an issue"""
        try:
            response = self._make_request("GET", f"/rest/api/3/issue/{issue_key}/comment", token=token)
            response.raise_for_status()
            return response.json().get('comments', [])
        except Exception as e:
            logger.error(f"Failed to get comments for {issue_key}: {e}")
            return []
    
    def transition_issue(self, issue_key: str, transition_name: str,
                      comment: str = None, token: Optional[str] = None) -> bool:
        """Transition issue to new status"""
        try:
            # Get available transitions
            transitions_response = self._make_request(
                "GET",
                f"/rest/api/3/issue/{issue_key}/transitions",
                token=token
            )
            transitions_response.raise_for_status()
            transitions = transitions_response.json().get('transitions', [])
            
            # Find the transition
            target_transition = None
            for transition in transitions:
                if transition['name'].lower() == transition_name.lower():
                    target_transition = transition
                    break
            
            if not target_transition:
                logger.error(f"Transition '{transition_name}' not found for issue {issue_key}")
                return False
            
            # Perform transition
            data = {"transition": {"id": target_transition['id']}}
            
            if comment:
                data["update"] = {
                    "comment": [{
                        "add": {
                            "body": {
                                "type": "doc",
                                "version": 1,
                                "content": [{
                                    "type": "paragraph",
                                    "content": [{
                                        "type": "text",
                                        "text": comment
                                    }]
                                }]
                            }
                        }
                    }]
                }
            
            response = self._make_request(
                "POST",
                f"/rest/api/3/issue/{issue_key}/transitions",
                json=data,
                token=token
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to transition issue {issue_key}: {e}")
            return False
    
    def assign_issue(self, issue_key: str, assignee: str, token: Optional[str] = None) -> bool:
        """Assign issue to user"""
        try:
            data = {
                "fields": {
                    "assignee": {"name": assignee}
                }
            }
            
            response = self._make_request(
                "PUT",
                f"/rest/api/3/issue/{issue_key}",
                json=data,
                token=token
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign issue {issue_key} to {assignee}: {e}")
            return False
    
    def get_users(self, project_key: str = None, start_at: int = 0, max_results: int = 50, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get users"""
        try:
            params = {
                'startAt': start_at,
                'maxResults': max_results
            }
            
            endpoint = "/rest/api/3/users/search"
            if project_key:
                params['project'] = project_key
            
            response = self._make_request("GET", endpoint, params=params, token=token)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []
    
    def get_statuses(self, project_key: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get statuses for project"""
        try:
            response = self._make_request("GET", f"/rest/api/3/project/{project_key}/statuses", token=token)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get statuses for project {project_key}: {e}")
            return []
    
    def get_issue_types(self, project_key: str = None, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get issue types"""
        try:
            if project_key:
                response = self._make_request("GET", f"/rest/api/3/project/{project_key}/issuetypes", token=token)
            else:
                response = self._make_request("GET", "/rest/api/3/issuetype", token=token)
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get issue types: {e}")
            return []
    
    def get_worklogs(self, issue_key: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get work logs for an issue"""
        try:
            response = self._make_request("GET", f"/rest/api/3/issue/{issue_key}/worklog", token=token)
            response.raise_for_status()
            return response.json().get('worklogs', [])
        except Exception as e:
            logger.error(f"Failed to get worklogs for {issue_key}: {e}")
            return []
    
    def add_worklog(self, issue_key: str, time_spent: str, comment: str = "",
                   started: str = None, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Add work log to issue"""
        try:
            data = {
                "timeSpent": time_spent,
                "comment": comment
            }
            
            if started:
                data["started"] = started
            
            response = self._make_request(
                "POST",
                f"/rest/api/3/issue/{issue_key}/worklog",
                json=data,
                token=token
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to add worklog to {issue_key}: {e}")
            return None
    
    def get_project_components(self, project_key: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get project components"""
        try:
            response = self._make_request("GET", f"/rest/api/3/project/{project_key}/component", token=token)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get components for project {project_key}: {e}")
            return []

    async def sync_to_postgres_cache(self, project_key: str) -> Dict[str, Any]:
        """Sync Jira analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Fetch issue counts for metrics
            all_issues = self.search_issues(f"project = {project_key}", max_results=0)
            total_issues = all_issues.get('total', 0)
            
            open_issues_data = self.search_issues(f"project = {project_key} AND statusCategory != Done", max_results=0)
            open_issues = open_issues_data.get('total', 0)
            
            completed_issues_data = self.search_issues(f"project = {project_key} AND statusCategory = Done", max_results=0)
            completed_issues = completed_issues_data.get('total', 0)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("jira_total_issues", total_issues, "count"),
                    ("jira_open_issues", open_issues, "count"),
                    ("jira_completed_issues", completed_issues, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=project_key,
                        integration_type="jira",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=project_key,
                            integration_type="jira",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Jira metrics to PostgreSQL cache for project {project_key}")
            except Exception as e:
                logger.error(f"Error saving Jira metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Jira PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, project_key: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Jira"""
        # Pipeline 1: Atom Memory
        # Triggered via jira_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(project_key)
        
        return {
            "success": True,
            "project_key": project_key,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Jira integration capabilities"""
        return {
            "operations": [
                {"id": "create_issue", "name": "Create Issue", "description": "Create a new Jira issue"},
                {"id": "search_issues", "name": "Search Issues", "description": "Search issues using JQL"},
                {"id": "update_issue", "name": "Update Issue", "description": "Update existing issue"},
                {"id": "get_projects", "name": "Get Projects", "description": "List Jira projects"},
                {"id": "add_comment", "name": "Add Comment", "description": "Add comment to issue"},
            ],
            "required_params": ["base_url"],
            "optional_params": ["username", "api_token", "access_token"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check Jira API connectivity"""
        try:
            if not self.base_url:
                return {
                    "healthy": False,
                    "message": "No base URL configured",
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }

            response = self.session.get(f"{self.base_url}/rest/api/3/myself")
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "healthy": True,
                    "message": "Jira API is connected",
                    "service": "jira",
                    "user": user_data.get('displayName'),
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "healthy": False,
                    "message": f"Authentication failed: {response.status_code}",
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.error(f"Jira health check failed: {e}")
            return {
                "healthy": False,
                "message": str(e),
                "last_check": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_entity_operation(
        self,
        operation: str,
        entity_type: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Standardized CRUD interface for Knowledge Graph entities (Jira).
        """
        if entity_type != "issue":
             return {
                 "success": False,
                 "error": f"Jira integration does not yet support the '{entity_type}' entity via dynamic tools.",
             }

        try:
            if operation == "create":
                # Map parameters for create_issue
                result = self.create_issue(
                    project_key=parameters.get("project_key") or parameters.get("project"),
                    summary=parameters.get("summary"),
                    issue_type=parameters.get("issue_type") or parameters.get("issuetype") or "Task",
                    description=parameters.get("description", ""),
                    priority=parameters.get("priority"),
                    assignee=parameters.get("assignee"),
                    token=parameters.get("token")
                )
                return {"success": True, "result": result, "entity_type": entity_type, "operation": operation}

            elif operation == "get":
                # Map parameters for get_issue
                issue_key = parameters.get("issue_key") or parameters.get("id") or parameters.get("key")
                if not issue_key:
                    raise ValueError("issue_key, id, or key is required for 'get' operation")
                
                result = self.get_issue(issue_key, token=parameters.get("token"))
                return {"success": True, "result": result, "entity_type": entity_type, "operation": operation}

            elif operation == "list":
                # Map parameters for search_issues
                jql = parameters.get("jql")
                if not jql:
                    project = parameters.get("project_key") or parameters.get("project")
                    if project:
                        jql = f"project = {project}"
                    else:
                        jql = "order by created DESC"
                
                result = self.search_issues(
                    jql=jql,
                    start_at=parameters.get("start_at", 0),
                    max_results=parameters.get("max_results", 50),
                    token=parameters.get("token")
                )
                return {"success": True, "result": result, "entity_type": entity_type, "operation": operation}

            else:
                return {
                    "success": False,
                    "error": f"Operation '{operation}' not supported for entity type '{entity_type}'",
                }

        except Exception as e:
            logger.error(f"Jira entity operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation,
                "entity_type": entity_type
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Jira operation with tenant context.

        Args:
            operation: Operation name (e.g., "create_issue", "search_issues")
            parameters: Operation parameters with variable substitution applied
            context: Tenant context dict with tenant_id, agent_id, workspace_id, connector_id

        Returns:
            Dict with success status and result

        CRITICAL: All operations validate tenant_id from context to prevent cross-tenant access.
        """
        # Validate tenant context
        if context and 'tenant_id' in context:
            tenant_id = context.get('tenant_id')
            if tenant_id != self.tenant_id:
                logger.error(f"Tenant ID mismatch: expected {self.tenant_id}, got {tenant_id}")
                return {
                    "success": False,
                    "error": "Tenant ID mismatch",
                    "operation": operation,
                }

        # Map operation names to methods
        operation_map = {
            "create_issue": self._op_create_issue,
            "search_issues": self._op_search_issues,
            "update_issue": self._op_update_issue,
            "get_projects": self._op_get_projects,
            "add_comment": self._op_add_comment,
        }

        if operation not in operation_map:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "operation": operation,
            }

        try:
            result = operation_map[operation](parameters, context)
            if asyncio.iscoroutine(result):
                result = await result
            return {
                "success": True,
                "result": result,
                "operation": operation,
                "details": {"tenant_id": self.tenant_id},
            }
        except Exception as e:
            logger.error(f"Failed to execute Jira operation {operation}: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation,
            }

    # Operation implementations
    def _op_create_issue(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create issue operation"""
        result = self.create_issue(
            project_key=parameters.get("project_key"),
            summary=parameters.get("summary"),
            issue_type=parameters.get("issue_type", "Task"),
            description=parameters.get("description", ""),
            priority=parameters.get("priority"),
            assignee=parameters.get("assignee"),
            token=parameters.get("token")
        )
        if not result:
            raise Exception("Failed to create issue")
        return result

    def _op_search_issues(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Search issues operation"""
        result = self.search_issues(
            jql=parameters.get("jql", ""),
            start_at=parameters.get("start_at", 0),
            max_results=parameters.get("max_results", 50),
            fields=parameters.get("fields"),
            token=parameters.get("token")
        )
        return result

    def _op_update_issue(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Update issue operation"""
        issue_key = parameters.get("issue_key")
        update_data = parameters.get("update_data", {})
        success = self.update_issue(issue_key, update_data, token=parameters.get("token"))
        if not success:
            raise Exception(f"Failed to update issue {issue_key}")
        return {"issue_key": issue_key, "updated": True}

    def _op_get_projects(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get projects operation"""
        projects = self.get_projects(
            start_at=parameters.get("start_at", 0),
            max_results=parameters.get("max_results", 50),
            token=parameters.get("token")
        )
        return projects

    def _op_add_comment(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Add comment operation"""
        result = self.add_comment(
            issue_key=parameters.get("issue_key"),
            body=parameters.get("body"),
            token=parameters.get("token")
        )
        if not result:
            raise Exception("Failed to add comment")
        return result
