# Mock Jira service for development
# This provides mock implementations for Jira API functionality

from typing import Dict, Any, Optional, List
import os
import uuid
from datetime import datetime, timedelta

from mcp_base import MCPBase

class MockJIRA:
    """Mock JIRA client for development"""

    def __init__(self, server: str, basic_auth: tuple = None, token_auth: str = None):
        self.server = server
        self.basic_auth = basic_auth
        self.token_auth = token_auth
        self.issues = self._create_mock_issues()

    def _create_mock_issues(self) -> List[Dict]:
        """Create mock Jira issues for development"""
        return [
            {
                "id": "10001",
                "key": "PROJ-1",
                "fields": {
                    "summary": "Fix login page styling",
                    "description": "The login page needs CSS fixes for mobile responsiveness",
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "John Developer"},
                    "reporter": {"displayName": "Product Manager"},
                    "created": "2024-01-15T10:00:00.000+0000",
                    "updated": "2024-01-16T14:30:00.000+0000",
                    "priority": {"name": "High"},
                    "issuetype": {"name": "Bug"}
                }
            },
            {
                "id": "10002",
                "key": "PROJ-2",
                "fields": {
                    "summary": "Add user profile page",
                    "description": "Create a new user profile page with editable settings",
                    "status": {"name": "To Do"},
                    "assignee": {"displayName": "Jane Developer"},
                    "reporter": {"displayName": "Product Manager"},
                    "created": "2024-01-14T09:00:00.000+0000",
                    "updated": "2024-01-14T09:00:00.000+0000",
                    "priority": {"name": "Medium"},
                    "issuetype": {"name": "Story"}
                }
            },
            {
                "id": "10003",
                "key": "PROJ-3",
                "fields": {
                    "summary": "Database migration script",
                    "description": "Create migration script for new user schema",
                    "status": {"name": "Done"},
                    "assignee": {"displayName": "DevOps Engineer"},
                    "reporter": {"displayName": "Tech Lead"},
                    "created": "2024-01-10T08:00:00.000+0000",
                    "updated": "2024-01-12T16:45:00.000+0000",
                    "priority": {"name": "Critical"},
                    "issuetype": {"name": "Task"}
                }
            }
        ]

    def search_issues(self, jql: str, startAt: int = 0, maxResults: int = 50) -> List[Dict]:
        """Mock search_issues method"""
        # Simple mock implementation - filter by text search in real implementation
        if "text" in jql.lower():
            # Extract search query from JQL
            import re
            match = re.search(r'text ~ "([^"]+)"', jql, re.IGNORECASE)
            if match:
                query = match.group(1).lower()
                filtered_issues = [
                    issue for issue in self.issues
                    if query in issue["fields"]["summary"].lower() or
                       query in issue["fields"]["description"].lower()
                ]
                return filtered_issues[startAt:startAt + maxResults]

        # Return all issues for non-search queries
        return self.issues[startAt:startAt + maxResults]

    def issue(self, issue_id: str) -> Dict:
        """Mock issue method to get specific issue"""
        for issue in self.issues:
            if issue["id"] == issue_id or issue["key"] == issue_id:
                return issue
        raise Exception(f"Issue {issue_id} not found")

class JiraService(MCPBase):
    def __init__(self, client: MockJIRA):
        self.client = client

    def list_files(
        self,
        project_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            # Build mock JQL query
            jql = f'project = "{project_id}"'
            if query:
                jql += f' AND text ~ "{query}"'

            start_at = int(page_token) if page_token else 0
            issues = self.client.search_issues(jql, startAt=start_at, maxResults=page_size)

            next_page_token = str(start_at + len(issues)) if len(issues) == page_size else None

            return {
                "status": "success",
                "data": {
                    "files": issues,
                    "nextPageToken": next_page_token
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            issue = self.client.issue(file_id)
            return {"status": "success", "data": issue}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "message": "Download not directly supported for Jira issues."
        }

# Mock function to get Jira client
def get_jira_client(server: str, username: str = None, password: str = None, token: str = None) -> MockJIRA:
    """Mock function to get Jira client"""
    return MockJIRA(server, basic_auth=(username, password), token_auth=token)

# For compatibility with existing imports
JIRA = MockJIRA
