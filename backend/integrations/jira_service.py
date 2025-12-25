"""
Jira Service for ATOM Platform
Provides comprehensive Jira integration functionality
"""

import json
import logging
import os
import base64
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import requests
from urllib.parse import urljoin, urlencode

logger = logging.getLogger(__name__)

class JiraService:
    """Jira API integration service"""
    
    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, 
                 api_token: Optional[str] = None):
        self.base_url = base_url or os.getenv('JIRA_BASE_URL')
        self.username = username or os.getenv('JIRA_USERNAME')
        self.api_token = api_token or os.getenv('JIRA_API_TOKEN')
        
        if not all([self.base_url, self.username, self.api_token]):
            raise ValueError("Jira base_url, username, and api_token are required")
        
        # Ensure base_url doesn't have trailing slash
        self.base_url = self.base_url.rstrip('/')
        
        # Setup authentication
        credentials = f"{self.username}:{self.api_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Basic {encoded_credentials}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'ATOM-Platform/1.0'
        })
    
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

# Singleton instance for global access
jira_service = JiraService()

def get_jira_service() -> JiraService:
    """Get Jira service instance"""
    return jira_service