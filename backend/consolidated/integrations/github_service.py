from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import os
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

class GitHubServiceType(Enum):
    """GitHub service types"""

    REPOSITORY = "repository"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    CODE_REVIEW = "code_review"
    WORKFLOW = "workflow"
    TEAM = "team"
    PROJECT = "project"
    WEBHOOK = "webhook"


class GitHubService:
    """Enhanced GitHub API integration service with comprehensive features"""

    def __init__(self):
        self.api_base_url = "https://api.github.com"
        self.timeout = 30
        self.max_retries = 3

        # Load configuration from environment
        self.client_id = os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "GITHUB_REDIRECT_URI",
            "http://localhost:3000/api/integrations/github/callback",
        )

        # Rate limiting tracking
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Optional[Dict]:
        """Make HTTP request to GitHub API with error handling and retry logic"""
        try:
            url = f"{self.api_base_url}{endpoint}"
            request_headers = self._get_headers()
            if headers:
                request_headers.update(headers)

            logger.info(f"Making GitHub API request: {method} {endpoint}")

            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=request_headers,
                timeout=self.timeout,
            )

            # Update rate limit info
            if "X-RateLimit-Remaining" in response.headers:
                self.rate_limit_remaining = int(
                    response.headers["X-RateLimit-Remaining"]
                )
            if "X-RateLimit-Reset" in response.headers:
                self.rate_limit_reset = int(response.headers["X-RateLimit-Reset"])

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 201:
                return response.json()
            elif response.status_code == 204:
                return {
                    "status": "success",
                    "message": "Operation completed successfully",
                }
            elif response.status_code == 429 and retry_count < self.max_retries:
                # Rate limited, wait and retry
                reset_time = self.rate_limit_reset
                wait_time = max(reset_time - datetime.now().timestamp(), 1)
                logger.warning(
                    f"Rate limited, waiting {wait_time} seconds before retry"
                )
                import time

                time.sleep(wait_time)
                return self._make_request(
                    method, endpoint, data, headers, retry_count + 1
                )
            else:
                logger.error(
                    f"GitHub API error {response.status_code}: {response.text}"
                )
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            if retry_count < self.max_retries:
                logger.info(f"Retrying request (attempt {retry_count + 1})")
                return self._make_request(
                    method, endpoint, data, headers, retry_count + 1
                )
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for GitHub API requests"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
        if hasattr(self, "access_token") and self.access_token:
            headers["Authorization"] = f"token {self.access_token}"
        return headers

    def set_access_token(self, access_token: str):
        """Set GitHub access token for authenticated requests"""
        self.access_token = access_token

    async def get_user_profile(self) -> Optional[Dict]:
        """Get authenticated user profile"""
        return self._make_request("GET", "/user")

    async def get_organizations(self) -> List[Dict]:
        """Get user's organizations"""
        result = self._make_request("GET", "/user/orgs")
        return result if result else []

    async def get_repositories(
        self, org: Optional[str] = None, visibility: str = "all"
    ) -> List[Dict]:
        """Get repositories for user or organization"""
        if org:
            endpoint = f"/orgs/{org}/repos"
        else:
            endpoint = "/user/repos"

        params = {"visibility": visibility, "per_page": 100}
        result = self._make_request("GET", endpoint)
        return result if result else []

    async def get_repository(self, owner: str, repo: str) -> Optional[Dict]:
        """Get specific repository details"""
        return self._make_request("GET", f"/repos/{owner}/{repo}")

    async def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = False,
    ) -> Optional[Dict]:
        """Create a new repository"""
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        return self._make_request("POST", "/user/repos", data)

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get issues for a repository"""
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = {"state": state}
        if labels:
            params["labels"] = ",".join(labels)

        result = self._make_request("GET", endpoint)
        return result if result else []

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """Create a new issue"""
        data = {
            "title": title,
            "body": body,
            "labels": labels or [],
            "assignees": assignees or [],
        }
        return self._make_request("POST", f"/repos/{owner}/{repo}/issues", data)

    async def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """Update an existing issue"""
        data = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if state is not None:
            data["state"] = state
        if labels is not None:
            data["labels"] = labels

        return self._make_request(
            "PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", data
        )

    async def get_pull_requests(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[Dict]:
        """Get pull requests for a repository"""
        endpoint = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state}

        result = self._make_request("GET", endpoint)
        return result if result else []

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> Optional[Dict]:
        """Create a new pull request"""
        data = {"title": title, "head": head, "base": base, "body": body}
        return self._make_request("POST", f"/repos/{owner}/{repo}/pulls", data)

    async def get_pull_request_reviews(
        self, owner: str, repo: str, pull_number: int
    ) -> List[Dict]:
        """Get reviews for a pull request"""
        result = self._make_request(
            "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        )
        return result if result else []

    async def create_pull_request_review(
        self, owner: str, repo: str, pull_number: int, body: str, event: str = "COMMENT"
    ) -> Optional[Dict]:
        """Create a review for a pull request"""
        data = {
            "body": body,
            "event": event,  # APPROVE, REQUEST_CHANGES, COMMENT
        }
        return self._make_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", data
        )

    async def get_workflow_runs(
        self, owner: str, repo: str, branch: Optional[str] = None
    ) -> List[Dict]:
        """Get workflow runs for a repository"""
        endpoint = f"/repos/{owner}/{repo}/actions/runs"
        params = {}
        if branch:
            params["branch"] = branch

        result = self._make_request("GET", endpoint)
        if result and "workflow_runs" in result:
            return result["workflow_runs"]
        return []

    async def trigger_workflow(
        self, owner: str, repo: str, workflow_id: str, ref: str = "main"
    ) -> Optional[Dict]:
        """Trigger a workflow dispatch"""
        data = {"ref": ref}
        return self._make_request(
            "POST",
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            data,
        )

    async def get_teams(self, org: str) -> List[Dict]:
        """Get teams for an organization"""
        result = self._make_request("GET", f"/orgs/{org}/teams")
        return result if result else []

    async def get_team_members(self, org: str, team_slug: str) -> List[Dict]:
        """Get members of a team"""
        result = self._make_request("GET", f"/orgs/{org}/teams/{team_slug}/members")
        return result if result else []

    async def get_projects(self, owner: str, repo: str) -> List[Dict]:
        """Get projects for a repository"""
        result = self._make_request("GET", f"/repos/{owner}/{repo}/projects")
        return result if result else []

    async def create_webhook(
        self,
        owner: str,
        repo: str,
        url: str,
        events: List[str] = ["push", "pull_request"],
    ) -> Optional[Dict]:
        """Create a webhook for a repository"""
        data = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {"url": url, "content_type": "json"},
        }
        return self._make_request("POST", f"/repos/{owner}/{repo}/hooks", data)

    async def search_code(self, query: str, org: Optional[str] = None) -> List[Dict]:
        """Search code across repositories"""
        if org:
            query = f"org:{org} {query}"

        result = self._make_request("GET", f"/search/code?q={query}")
        if result and "items" in result:
            return result["items"]
        return []

    async def search_issues(self, query: str, org: Optional[str] = None) -> List[Dict]:
        """Search issues and pull requests"""
        if org:
            query = f"org:{org} {query}"

        result = self._make_request("GET", f"/search/issues?q={query}")
        if result and "items" in result:
            return result["items"]
        return []

    async def get_branches(self, owner: str, repo: str) -> List[Dict]:
        """Get branches for a repository"""
        result = self._make_request("GET", f"/repos/{owner}/{repo}/branches")
        return result if result else []

    async def create_branch(
        self, owner: str, repo: str, branch_name: str, from_branch: str = "main"
    ) -> Optional[Dict]:
        """Create a new branch"""
        # First get the SHA of the base branch
        ref_result = self._make_request(
            "GET", f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        )
        if not ref_result:
            return None

        sha = ref_result["object"]["sha"]
        data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        return self._make_request("POST", f"/repos/{owner}/{repo}/git/refs", data)

    async def get_commits(
        self, owner: str, repo: str, branch: str = "main", since: Optional[str] = None
    ) -> List[Dict]:
        """Get commits for a repository"""
        endpoint = f"/repos/{owner}/{repo}/commits"
        params = {"sha": branch}
        if since:
            params["since"] = since

        result = self._make_request("GET", endpoint)
        return result if result else []

    async def get_rate_limit(self) -> Optional[Dict]:
        """Get current rate limit status"""
        return self._make_request("GET", "/rate_limit")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of GitHub integration"""
        try:
            # Test basic API connectivity
            user_profile = await self.get_user_profile()
            rate_limit = await self.get_rate_limit()

            if user_profile and rate_limit:
                return {
                    "status": "healthy",
                    "service": "github",
                    "user": user_profile.get("login"),
                    "rate_limit_remaining": self.rate_limit_remaining,
                    "rate_limit_reset": self.rate_limit_reset,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "unhealthy",
                    "service": "github",
                    "error": "Unable to fetch user profile or rate limit",
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "github",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

            }

# Global service instance
github_service = GitHubService()
