"""
Linear Integration Adapter

Provides OAuth-based integration with Linear for issue tracking and project management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class LinearAdapter:
    """
    Adapter for Linear OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Issue and project management
    - Team and workflow access
    - Sprint and cycle tracking
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "linear"
        self.base_url = "https://api.linear.app"

        # OAuth credentials from environment
        self.client_id = os.getenv("LINEAR_CLIENT_ID")
        self.client_secret = os.getenv("LINEAR_CLIENT_SECRET")
        self.redirect_uri = os.getenv("LINEAR_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Linear OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Linear OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("LINEAR_CLIENT_ID not configured")

        # Linear OAuth endpoint
        auth_url = "https://linear.app/oauth/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "read write issues:read issues:write projects:read projects:write teams:read",
            "response_type": "code",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Linear OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Linear OAuth credentials not configured")

        token_url = f"{self.base_url}/oauth/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, json=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration (Linear tokens don't expire by default)
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Linear access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Linear token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Linear API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current user info
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": """
                            query {
                                viewer {
                                    id
                                    name
                                    email
                                }
                            }
                        """
                    }
                )
                response.raise_for_status()

                logger.info(f"Linear connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Linear connection test failed: {e}")
            return False

    async def search_issues(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Linear issues by title or description.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of issue objects
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            async with httpx.AsyncClient() as client:
                # Linear uses GraphQL
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": """
                            query($filter: IssueFilter, $first: Int) {
                                issues(filter: $filter, first: $first) {
                                    nodes {
                                        id
                                        title
                                        description
                                        state {
                                            name
                                        }
                                        priority
                                        assignee {
                                            name
                                            email
                                        }
                                        labels {
                                            nodes {
                                                name
                                            }
                                        }
                                    }
                                }
                            }
                        """,
                        "variables": {
                            "filter": {
                                "query": query
                            },
                            "first": limit
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()
                issues = data.get("data", {}).get("issues", {}).get("nodes", [])

                logger.info(f"Linear search returned {len(issues)} issues for workspace {self.workspace_id}")
                return issues

        except Exception as e:
            logger.error(f"Linear issue search failed: {e}")
            raise

    async def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Linear issue by ID.

        Args:
            issue_id: Linear issue ID

        Returns:
            Issue details with all fields
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": """
                            query($id: String!) {
                                issue(id: $id) {
                                    id
                                    title
                                    description
                                    state {
                                        id
                                        name
                                    }
                                    priority
                                    assignee {
                                        id
                                        name
                                        email
                                    }
                                    team {
                                        id
                                        name
                                    }
                                    labels {
                                        nodes {
                                            id
                                            name
                                        }
                                    }
                                    project {
                                        id
                                        name
                                    }
                                    createdAt
                                    updatedAt
                                }
                            }
                        """,
                        "variables": {
                            "id": issue_id
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()
                issue = data.get("data", {}).get("issue")

                logger.info(f"Retrieved Linear issue {issue_id} for workspace {self.workspace_id}")
                return issue

        except Exception as e:
            logger.error(f"Failed to retrieve Linear issue {issue_id}: {e}")
            raise

    async def create_issue(self, team_id: str, title: str, description: str = None,
                          priority: int = 0, assignee_id: str = None) -> Dict[str, Any]:
        """
        Create a new Linear issue.

        Args:
            team_id: Team ID to create issue in
            title: Issue title
            description: Issue description
            priority: Priority level (0=Urgent, 1=High, 2=Medium, 3=Low, 4=No priority)
            assignee_id: User ID to assign issue to

        Returns:
            Created issue object with ID
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            # Build mutation
            mutation = """
                mutation($input: IssueCreateInput!) {
                    issueCreate(input: $input) {
                        success
                        issue {
                            id
                            title
                            description
                            state {
                                id
                                name
                            }
                            priority
                            assignee {
                                id
                                name
                            }
                        }
                    }
                }
            """

            variables = {
                "input": {
                    "teamId": team_id,
                    "title": title,
                    "description": description,
                    "priority": priority
                }
            }

            if assignee_id:
                variables["input"]["assigneeId"] = assignee_id

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                issue_data = data.get("data", {}).get("issueCreate", {})

                if issue_data.get("success"):
                    issue = issue_data.get("issue")
                    logger.info(f"Created Linear issue {issue.get('id')} for workspace {self.workspace_id}")
                    return issue
                else:
                    raise Exception("Failed to create Linear issue")

        except Exception as e:
            logger.error(f"Failed to create Linear issue: {e}")
            raise

    async def update_issue(self, issue_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Linear issue.

        Args:
            issue_id: Issue ID to update
            updates: Dictionary of fields to update (title, description, stateId, priority, etc.)

        Returns:
            Updated issue object
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            mutation = """
                mutation($input: IssueUpdateInput!) {
                    issueUpdate(input: $input) {
                        success
                        issue {
                            id
                            title
                            description
                            state {
                                id
                                name
                            }
                            priority
                        }
                    }
                }
            """

            variables = {
                "input": {
                    "id": issue_id,
                    **updates
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                issue_data = data.get("data", {}).get("issueUpdate", {})

                if issue_data.get("success"):
                    issue = issue_data.get("issue")
                    logger.info(f"Updated Linear issue {issue_id} in workspace {self.workspace_id}")
                    return issue
                else:
                    raise Exception("Failed to update Linear issue")

        except Exception as e:
            logger.error(f"Failed to update Linear issue {issue_id}: {e}")
            raise

    async def get_teams(self) -> List[Dict[str, Any]]:
        """
        Retrieve all Linear teams.

        Returns:
            List of team objects
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": """
                            query {
                                teams {
                                    nodes {
                                        id
                                        name
                                        description
                                        key
                                    }
                                }
                            }
                        """
                    }
                )
                response.raise_for_status()

                data = response.json()
                teams = data.get("data", {}).get("teams", {}).get("nodes", [])

                logger.info(f"Retrieved {len(teams)} Linear teams for workspace {self.workspace_id}")
                return teams

        except Exception as e:
            logger.error(f"Failed to retrieve Linear teams: {e}")
            raise

    async def add_comment(self, issue_id: str, body: str) -> Dict[str, Any]:
        """
        Add a comment to a Linear issue.

        Args:
            issue_id: Issue ID
            body: Comment content (supports Markdown)

        Returns:
            Created comment object
        """
        if not self._access_token:
            raise ValueError("Linear access token not available")

        try:
            mutation = """
                mutation($input: CommentCreateInput!) {
                    commentCreate(input: $input) {
                        success
                        comment {
                            id
                            body
                            user {
                                name
                            }
                            createdAt
                        }
                    }
                }
            """

            variables = {
                "input": {
                    "issueId": issue_id,
                    "body": body
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers={
                        "Authorization": f"{self._access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": mutation,
                        "variables": variables
                    }
                )
                response.raise_for_status()

                data = response.json()
                comment_data = data.get("data", {}).get("commentCreate", {})

                if comment_data.get("success"):
                    comment = comment_data.get("comment")
                    logger.info(f"Added comment to Linear issue {issue_id} in workspace {self.workspace_id}")
                    return comment
                else:
                    raise Exception("Failed to add comment to Linear issue")

        except Exception as e:
            logger.error(f"Failed to add comment to Linear issue {issue_id}: {e}")
            raise
