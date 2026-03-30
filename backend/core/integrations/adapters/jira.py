"""
Jira Integration Adapter

Provides OAuth-based integration with Jira for issue and project tracking.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class JiraAdapter:
    """
    Adapter for Jira OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Issue creation and management
    - Project and board access
    - Sprint and epic tracking
    """

    def __init__(self, db, workspace_id: str, site_url: Optional[str] = None):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "jira"
        self.site_url = site_url or os.getenv("JIRA_SITE_URL")
        self.base_url = f"{self.site_url}/rest/api/3" if self.site_url else None

        # OAuth credentials from environment
        self.client_id = os.getenv("JIRA_CLIENT_ID")
        self.client_secret = os.getenv("JIRA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("JIRA_REDIRECT_URI")

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _load_token(self):
        """Load OAuth tokens from database for the current workspace"""
        if not self.db:
            return
            
        from core.models import IntegrationToken
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.workspace_id == self.workspace_id,
            IntegrationToken.provider == self.service_name
        ).first()
        
        if token:
            self._access_token = token.access_token
            # Jira tokens also are store here
            self._refresh_token = token.refresh_token
            self._token_expires_at = token.expires_at
            
            # Dynamically set site_url from token if not explicitly provided
            if not self.site_url and token.instance_url:
                self.site_url = token.instance_url
                self.base_url = f"{self.site_url}/rest/api/3"
                logger.info(f"Loaded Jira site URL from token: {self.site_url}")

    async def refresh_token(self) -> bool:
        """Refresh Jira access token using refresh token"""
        if not self._refresh_token:
            return False
            
        token_url = "https://auth.atlassian.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, json=data)
                response.raise_for_status()
                
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                self._refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update DB
                if self.db:
                    from core.models import IntegrationToken
                    token = self.db.query(IntegrationToken).filter(
                        IntegrationToken.workspace_id == self.workspace_id,
                        IntegrationToken.provider == self.service_name
                    ).first()
                    if token:
                        token.access_token = self._access_token
                        token.refresh_token = self._refresh_token
                        token.expires_at = self._token_expires_at
                        self.db.commit()
                
                return True
        except Exception as e:
            logger.error(f"Jira token refresh failed: {e}")
            return False

    async def ensure_token(self):
        """Ensure we have a valid access token"""
        if not self._access_token:
            await self._load_token()
            
        if not self._access_token or (self._token_expires_at and self._token_expires_at < datetime.now()):
            if self._refresh_token:
                await self.refresh_token()

    async def get_oauth_url(self) -> str:
        """
        Generate Jira OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Jira OAuth consent screen
        """
        if not self.site_url or not self.client_id:
            raise ValueError("Jira site URL and client ID must be configured")

        # Jira OAuth endpoint
        auth_url = f"{self.site_url}/rest/oauth2/latest/authorization"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "read:jira-work read:jira-user read:jira-project",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Jira OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, scope, etc.
        """
        if not self.site_url or not self.client_id or not self.client_secret:
            raise ValueError("Jira OAuth credentials not configured")

        token_url = f"{self.site_url}/rest/oauth2/latest/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Jira access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Jira token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Jira API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.base_url or not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current user info
                response = await client.get(
                    f"{self.base_url}/myself",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Jira connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return False

    async def search_issues(self, jql: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search Jira issues using JQL (Jira Query Language).

        Args:
            jql: JQL query string
            limit: Maximum number of results

        Returns:
            List of issue objects
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "jql": jql,
                        "maxResults": limit,
                        "fields": ["summary", "status", "assignee", "priority", "issuetype", "created"]
                    }
                )
                response.raise_for_status()

                data = response.json()
                issues = data.get("issues", [])

                logger.info(f"Jira search returned {len(issues)} issues for workspace {self.workspace_id}")
                return issues

        except Exception as e:
            logger.error(f"Jira search failed: {e}")
            raise

    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Retrieve a specific Jira issue by key.

        Args:
            issue_key: Jira issue key (e.g., "PROJ-123")

        Returns:
            Issue details with all fields
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/issue/{issue_key}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Retrieved Jira issue {issue_key} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to retrieve Jira issue {issue_key}: {e}")
            raise

    async def create_issue(self, project_key: str, summary: str, description: str,
                         issue_type: str = "Task", priority: str = "Medium") -> Dict[str, Any]:
        """
        Create a new Jira issue.

        Args:
            project_key: Project key (e.g., "PROJ")
            summary: Issue summary
            description: Issue description
            issue_type: Type of issue (Task, Bug, Story, Epic)
            priority: Priority (Low, Medium, High)

        Returns:
            Created issue object with key and ID
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/issue",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "fields": {
                            "project": {"key": project_key},
                            "summary": summary,
                            "description": {
                                "content": description
                            },
                            "issuetype": {"name": issue_type},
                            "priority": {"name": priority}
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Created Jira issue {data.get('key')} for workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to create Jira issue: {e}")
            raise

    async def update_issue(self, issue_key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Jira issue.

        Args:
            issue_key: Issue key
            updates: Dictionary of fields to update

        Returns:
            Updated issue object
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/issue/{issue_key}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json=updates
                )
                response.raise_for_status()

                data = response.json()

                logger.info(f"Updated Jira issue {issue_key} in workspace {self.workspace_id}")
                return data

        except Exception as e:
            logger.error(f"Failed to update Jira issue {issue_key}: {e}")
            raise

    async def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        """
        Add a comment to a Jira issue.

        Args:
            issue_key: Issue key
            comment: Comment text

        Returns:
            Created comment object
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/issue/{issue_key}/comment",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "body": {
                            "content": {
                                "type": "text",
                                "text": comment
                            }
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()

        except Exception as e:
            logger.error(f"Failed to add comment to Jira issue {issue_key}: {e}")
            raise

    async def get_available_schemas(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available projects and their associated issue types.
        In Jira, the schema is effectively (Project x IssueType).

        Returns:
            List of project/issue-type schema objects.
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            async with httpx.AsyncClient() as client:
                # Fetch projects with their issue types expanded
                response = await client.get(
                    f"{self.base_url}/project",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    params={"expand": "issueTypes"}
                )
                response.raise_for_status()
                projects = response.json()
                
                schemas = []
                for project in projects:
                    project_key = project.get("key")
                    project_name = project.get("name")
                    issue_types = project.get("issueTypes", [])
                    
                    for itype in issue_types:
                        # Create a composite schema object
                        schemas.append({
                            "project_key": project_key,
                            "project_name": project_name,
                            "issue_type": itype.get("name"),
                            "issue_type_id": itype.get("id"),
                            "description": itype.get("description")
                        })
                
                logger.info(f"Discovered {len(schemas)} project/issue-type combinations in Jira")
                return schemas
        except Exception as e:
            logger.error(f"Failed to discover Jira schemas: {e}")
            return []

    async def fetch_records(self, entity_type: str, limit: int = 50, after: Optional[str] = None) -> Dict[str, Any]:
        """
        Unified method to fetch Jira issues using JQL based on project and issue type.
        
        Args:
            entity_type: Composite ID in format 'project_key:issue_type_name'
            limit: Maximum issues to fetch.
            after: startAt (integer offset) for Jira pagination.
            
        Returns:
            Dictionary with 'results' (list) and 'paging' (dict).
        """
        if not self.base_url or not self._access_token:
            raise ValueError("Jira API not configured")

        try:
            if ":" not in entity_type:
                logger.error(f"Invalid Jira entity_type format: {entity_type}. Expected 'project_key:issue_type_name'")
                return {"results": [], "paging": {}}
                
            project_key, issue_type = entity_type.split(":", 1)
            jql = f"project = '{project_key}' AND issuetype = '{issue_type}' ORDER BY created DESC"
            
            start_at = int(after) if after and after.isdigit() else 0
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "jql": jql,
                        "maxResults": limit,
                        "startAt": start_at,
                        "fields": ["*all"] # Fetch all fields for discovery
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                issues = data.get("issues", [])
                total = data.get("total", 0)
                next_startat = start_at + len(issues)
                
                return {
                    "results": issues,
                    "paging": {"after": str(next_startat)} if next_startat < total else {}
                }
        except Exception as e:
            logger.error(f"Failed to fetch records from Jira {entity_type}: {e}")
            return {"results": [], "paging": {}}
