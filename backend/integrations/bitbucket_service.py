"""
Bitbucket Integration Service

This service provides integration with Bitbucket API for:
- Repository and branch management
- Pull requests and code review
- Pipelines and deployments
- Team and workspace collaboration
"""

import base64
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

class BitbucketService:
    """Bitbucket API service implementation"""

    def __init__(self):
        """Initialize Bitbucket service"""
        self.base_url = "https://api.bitbucket.org/2.0"
        self.client_id = os.getenv("BITBUCKET_CLIENT_ID")
        self.client_secret = os.getenv("BITBUCKET_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "BITBUCKET_REDIRECT_URI",
            "http://localhost:3000/api/integrations/bitbucket/callback",
        )

    def get_authorization_url(self, state: str = None) -> str:
        """Generate Bitbucket OAuth 2.0 authorization URL"""
        auth_url = "https://bitbucket.org/site/oauth2/authorize"
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "repository team account",
            "state": state or "default",
        }
        return f"{auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        token_url = "https://bitbucket.org/site/oauth2/access_token"

        # Bitbucket uses Basic Auth for token exchange
        auth_string = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        try:
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()

            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope"),
            }
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        token_url = "https://bitbucket.org/site/oauth2/access_token"

        auth_string = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        try:
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    def _make_request(
        self, access_token: str, endpoint: str, method: str = "GET", data: Dict = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Bitbucket API"""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.RequestException as e:
            logger.error(f"Bitbucket API request failed: {e}")
            raise

    def get_workspaces(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all workspaces for the authenticated user"""
        try:
            result = self._make_request(access_token, "workspaces")
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch workspaces: {e}")
            return []

    def get_repositories(
        self, access_token: str, workspace: str = None
    ) -> List[Dict[str, Any]]:
        """Get repositories from workspace or user"""
        try:
            if workspace:
                endpoint = f"repositories/{workspace}"
            else:
                endpoint = "repositories"

            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch repositories: {e}")
            return []

    def get_repository(
        self, access_token: str, workspace: str, repo_slug: str
    ) -> Dict[str, Any]:
        """Get specific repository details"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}"
            return self._make_request(access_token, endpoint)
        except Exception as e:
            logger.error(f"Failed to fetch repository: {e}")
            return {}

    def get_branches(
        self, access_token: str, workspace: str, repo_slug: str
    ) -> List[Dict[str, Any]]:
        """Get branches for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/refs/branches"
            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch branches: {e}")
            return []

    def get_pull_requests(
        self, access_token: str, workspace: str, repo_slug: str, state: str = "OPEN"
    ) -> List[Dict[str, Any]]:
        """Get pull requests for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/pullrequests"
            params = f"?state={state}"
            result = self._make_request(access_token, endpoint + params)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch pull requests: {e}")
            return []

    def get_pull_request(
        self, access_token: str, workspace: str, repo_slug: str, pr_id: str
    ) -> Dict[str, Any]:
        """Get specific pull request details"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
            return self._make_request(access_token, endpoint)
        except Exception as e:
            logger.error(f"Failed to fetch pull request: {e}")
            return {}

    def create_pull_request(
        self,
        access_token: str,
        workspace: str,
        repo_slug: str,
        title: str,
        source_branch: str,
        destination_branch: str = "main",
        description: str = "",
        reviewers: List[str] = None,
    ) -> Dict[str, Any]:
        """Create a new pull request"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/pullrequests"

            data = {
                "title": title,
                "source": {"branch": {"name": source_branch}},
                "destination": {"branch": {"name": destination_branch}},
                "description": description,
            }

            if reviewers:
                data["reviewers"] = [{"uuid": reviewer} for reviewer in reviewers]

            return self._make_request(access_token, endpoint, "POST", data)
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return {}

    def get_commits(
        self, access_token: str, workspace: str, repo_slug: str, branch: str = None
    ) -> List[Dict[str, Any]]:
        """Get commits for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/commits"
            if branch:
                endpoint += f"?include={branch}"

            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch commits: {e}")
            return []

    def get_pipelines(
        self, access_token: str, workspace: str, repo_slug: str
    ) -> List[Dict[str, Any]]:
        """Get pipelines for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/pipelines/"
            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch pipelines: {e}")
            return []

    def trigger_pipeline(
        self,
        access_token: str,
        workspace: str,
        repo_slug: str,
        branch: str = "main",
        variables: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Trigger a pipeline for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/pipelines/"

            data = {
                "target": {
                    "ref_type": "branch",
                    "type": "pipeline_ref_target",
                    "ref_name": branch,
                }
            }

            if variables:
                data["variables"] = [
                    {"key": k, "value": v} for k, v in variables.items()
                ]

            return self._make_request(access_token, endpoint, "POST", data)
        except Exception as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            return {}

    def get_issues(
        self, access_token: str, workspace: str, repo_slug: str
    ) -> List[Dict[str, Any]]:
        """Get issues for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/issues"
            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch issues: {e}")
            return []

    def create_issue(
        self,
        access_token: str,
        workspace: str,
        repo_slug: str,
        title: str,
        content: str = "",
        kind: str = "bug",
        priority: str = "major",
    ) -> Dict[str, Any]:
        """Create a new issue"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/issues"

            data = {
                "title": title,
                "content": {"raw": content},
                "kind": kind,
                "priority": priority,
            }

            return self._make_request(access_token, endpoint, "POST", data)
        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            return {}

    def get_webhooks(
        self, access_token: str, workspace: str, repo_slug: str
    ) -> List[Dict[str, Any]]:
        """Get webhooks for a repository"""
        try:
            endpoint = f"repositories/{workspace}/{repo_slug}/hooks"
            result = self._make_request(access_token, endpoint)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to fetch webhooks: {e}")
            return []

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get current user information"""
        try:
            return self._make_request(access_token, "user")
        except Exception as e:
            logger.error(f"Failed to fetch user info: {e}")
            return {}

    def search_code(
        self, access_token: str, query: str, workspace: str = None
    ) -> List[Dict[str, Any]]:
        """Search code across repositories"""
        try:
            endpoint = "search/code"
            params = f"?search_query={query}"
            if workspace:
                params += f"&workspace={workspace}"

            result = self._make_request(access_token, endpoint + params)
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to search code: {e}")
            return []

    def get_health_status(self, access_token: str) -> Dict[str, Any]:
        """Check Bitbucket service health"""
        try:
            # Simple request to test connectivity
            user_info = self.get_user_info(access_token)

            return {
                "status": "healthy" if user_info else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "user": user_info.get("display_name") if user_info else None,
            }
        except Exception as e:
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "error": str(e)
            }
