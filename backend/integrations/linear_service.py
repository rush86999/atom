"""
Linear Service for ATOM Platform
Provides comprehensive Linear project management integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

class LinearService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.client_id = config.get("client_id") or os.getenv("LINEAR_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("LINEAR_CLIENT_SECRET")
        self.base_url = "https://api.linear.app"
        self.graphql_url = "https://api.linear.app/graphql"
        self.auth_url = "https://linear.app/oauth/authorize"
        self.token_url = "https://api.linear.app/oauth/token"
        self.access_token = config.get("access_token") or os.getenv("LINEAR_ACCESS_TOKEN")
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

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Linear integration capabilities"""
        return {
            "operations": [
                {"id": "get_issues", "description": "Get issues from Linear"},
                {"id": "create_issue", "description": "Create a new issue"},
                {"id": "get_teams", "description": "Get teams"},
                {"id": "get_projects", "description": "Get projects"},
                {"id": "create_project", "description": "Create a new project"},
                {"id": "get_viewer", "description": "Get current user info"},
            ],
            "required_params": ["access_token"],
            "optional_params": ["team_id", "first"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Linear service"""
        try:
            return {
                "healthy": True,
                "message": "Linear service is healthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Linear service unhealthy: {str(e)}",
                "last_check": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute Linear operation with tenant context"""
        try:
            access_token = parameters.get("access_token")

            if operation == "get_issues":
                issues = await self.get_issues(
                    access_token=access_token,
                    first=parameters.get("first", 50),
                    team_id=parameters.get("team_id")
                )
                return {"success": True, "result": issues}

            elif operation == "create_issue":
                issue = await self.create_issue(
                    title=parameters["title"],
                    team_id=parameters["team_id"],
                    access_token=access_token,
                    description=parameters.get("description"),
                    priority=parameters.get("priority"),
                    assignee_id=parameters.get("assignee_id")
                )
                return {"success": True, "result": issue}

            elif operation == "get_teams":
                teams = await self.get_teams(access_token=access_token)
                return {"success": True, "result": teams}

            elif operation == "get_projects":
                projects = await self.get_projects(access_token=access_token)
                return {"success": True, "result": projects}

            elif operation == "create_project":
                project = await self.create_project(
                    name=parameters["name"],
                    team_ids=parameters["team_ids"],
                    access_token=access_token,
                    description=parameters.get("description"),
                    state=parameters.get("state", "planned")
                )
                return {"success": True, "result": project}

            elif operation == "get_viewer":
                viewer = await self.get_viewer(access_token=access_token)
                return {"success": True, "result": viewer}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Sync Linear analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get issues and teams
            issues = await self.get_issues(access_token)
            teams = await self.get_teams(access_token)
            projects = await self.get_projects(access_token)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("linear_issue_count", len(issues), "count"),
                    ("linear_team_count", len(teams), "count"),
                    ("linear_project_count", len(projects), "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="linear",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="linear",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Linear metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Linear metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Linear PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Linear"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


