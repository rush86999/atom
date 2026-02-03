"""
Linear Service for ATOM Platform
Provides comprehensive Linear project management integration functionality
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class LinearService:
    def __init__(self):
        self.client_id = os.getenv("LINEAR_CLIENT_ID")
        self.client_secret = os.getenv("LINEAR_CLIENT_SECRET")
        self.base_url = "https://api.linear.app"
        self.graphql_url = "https://api.linear.app/graphql"
        self.auth_url = "https://linear.app/oauth/authorize"
        self.token_url = "https://api.linear.app/oauth/token"
        self.access_token = os.getenv("LINEAR_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": access_token,
            "Content-Type": "application/json"
        }

    def get_authorization_url(self, redirect_uri: str, state: str = None, scope: str = "read,write") -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Linear token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def _graphql_query(self, query: str, variables: Dict = None, access_token: str = None) -> Dict[str, Any]:
        """Execute a GraphQL query"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = await self.client.post(
                self.graphql_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"GraphQL query failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"GraphQL query failed: {str(e)}"
            )

    async def get_viewer(self, access_token: str = None) -> Dict[str, Any]:
        """Get current user information"""
        query = """
            query {
                viewer {
                    id
                    name
                    email
                    admin
                    createdAt
                }
            }
        """
        
        result = await self._graphql_query(query, access_token=access_token)
        return result.get("data", {}).get("viewer", {})

    async def get_issues(
        self,
        access_token: str = None,
        first: int = 50,
        team_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get issues"""
        variables = {"first": first}
        
        filter_clause = ""
        if team_id:
            filter_clause = f'filter: {{ team: {{ id: {{ eq: "{team_id}" }} }} }}'
            
        query = f"""
            query($first: Int!) {{
                issues({filter_clause} first: $first) {{
                    nodes {{
                        id
                        title
                        description
                        priority
                        state {{
                            name
                        }}
                        assignee {{
                            name
                        }}
                        createdAt
                        updatedAt
                    }}
                }}
            }}
        """
        
        result = await self._graphql_query(query, variables, access_token)
        return result.get("data", {}).get("issues", {}).get("nodes", [])

    async def get_teams(self, access_token: str = None, first: int = 50) -> List[Dict[str, Any]]:
        """Get teams"""
        query = f"""
            query {{
                teams(first: {first}) {{
                    nodes {{
                        id
                        name
                        key
                        description
                    }}
                }}
            }}
        """
        
        result = await self._graphql_query(query, access_token=access_token)
        return result.get("data", {}).get("teams", {}).get("nodes", [])

    async def get_projects(self, access_token: str = None, first: int = 50) -> List[Dict[str, Any]]:
        """Get projects"""
        query = f"""
            query {{
                projects(first: {first}) {{
                    nodes {{
                        id
                        name
                        description
                        state
                        progress
                        startedAt
                        targetDate
                    }}
                }}
            }}
        """
        
        result = await self._graphql_query(query, access_token=access_token)
        return result.get("data", {}).get("projects", {}).get("nodes", [])

    async def create_issue(
        self,
        title: str,
        team_id: str,
        access_token: str = None,
        description: str = None,
        priority: int = None,
        assignee_id: str = None
    ) -> Dict[str, Any]:
        """Create a new issue"""
        variables = {
            "title": title,
            "teamId": team_id
        }
        
        if description:
            variables["description"] = description
        if priority:
            variables["priority"] = priority
        if assignee_id:
            variables["assigneeId"] = assignee_id
        
        query = """
            mutation($title: String!, $teamId: String!, $description: String, $priority: Int, $assigneeId: String) {
                issueCreate(input: {
                    title: $title
                    teamId: $teamId
                    description: $description
                    priority: $priority
                    assigneeId: $assigneeId
                }) {
                    success
                    issue {
                        id
                        title
                        url
                    }
                }
            }
        """
        
        result = await self._graphql_query(query, variables, access_token)
        return result.get("data", {}).get("issueCreate", {})

    async def create_project(
        self,
        name: str,
        team_ids: List[str],
        access_token: str = None,
        description: str = None,
        state: str = "planned"
    ) -> Dict[str, Any]:
        """Create a new project in Linear"""
        variables = {
            "name": name,
            "teamIds": team_ids,
            "state": state
        }
        if description:
            variables["description"] = description
            
        query = """
            mutation($name: String!, $teamIds: [String!]!, $description: String, $state: String) {
                projectCreate(input: {
                    name: $name
                    teamIds: $teamIds
                    description: $description
                    state: $state
                }) {
                    success
                    project {
                        id
                        name
                        url
                    }
                }
            }
        """
        result = await self._graphql_query(query, variables, access_token)
        return result.get("data", {}).get("projectCreate", {})

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Linear service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "linear",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "linear",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
linear_service = LinearService()

def get_linear_service() -> LinearService:
    """Get Linear service instance"""
    return linear_service
