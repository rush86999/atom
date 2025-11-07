"""
GitLab Enhanced Service
Provides comprehensive GitLab API integration with caching and error handling
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GitLabProject:
    """GitLab project data model"""

    id: int
    name: str
    path: str
    path_with_namespace: str
    description: Optional[str]
    web_url: str
    namespace: Dict[str, Any]
    visibility: str
    star_count: int
    forks_count: int
    open_issues_count: int
    last_activity_at: str
    created_at: str
    updated_at: str
    default_branch: str
    owner: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class GitLabIssue:
    """GitLab issue data model"""

    id: int
    iid: int
    project_id: int
    title: str
    description: Optional[str]
    state: str
    labels: List[str]
    author: Dict[str, Any]
    assignee: Optional[Dict[str, Any]]
    milestone: Optional[Dict[str, Any]]
    web_url: str
    created_at: str
    updated_at: str
    closed_at: Optional[str]
    due_date: Optional[str]
    weight: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class GitLabMergeRequest:
    """GitLab merge request data model"""

    id: int
    iid: int
    project_id: int
    title: str
    description: Optional[str]
    state: str
    source_branch: str
    target_branch: str
    author: Dict[str, Any]
    assignee: Optional[Dict[str, Any]]
    reviewers: List[Dict[str, Any]]
    web_url: str
    created_at: str
    updated_at: str
    merged_at: Optional[str]
    closed_at: Optional[str]
    sha: str
    merge_status: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class GitLabPipeline:
    """GitLab pipeline data model"""

    id: int
    project_id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: str
    updated_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    duration: Optional[int]
    coverage: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class GitLabBranch:
    """GitLab branch data model"""

    name: str
    commit: Dict[str, Any]
    merged: bool
    protected: bool
    default: bool
    developers_can_push: bool
    developers_can_merge: bool
    can_push: bool
    web_url: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class GitLabCommit:
    """GitLab commit data model"""

    id: str
    short_id: str
    title: str
    message: str
    author_name: str
    author_email: str
    authored_date: str
    committed_date: str
    committer_name: str
    committer_email: str
    web_url: str
    stats: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class GitLabEnhancedService:
    """
    Enhanced GitLab service with comprehensive API operations
    """

    def __init__(self, base_url: str = None, access_token: str = None):
        """
        Initialize GitLab service

        Args:
            base_url: GitLab instance base URL (defaults to gitlab.com)
            access_token: GitLab access token
        """
        self.base_url = base_url or os.getenv("GITLAB_BASE_URL", "https://gitlab.com")
        self.api_base_url = f"{self.base_url}/api/v4"
        self.access_token = access_token or os.getenv("GITLAB_ACCESS_TOKEN")
        self.session = None
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache TTL

        # Configure headers
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _ensure_session(self):
        """Ensure aiohttp session is available"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to GitLab API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Response data as dictionary
        """
        await self._ensure_session()

        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "data": data,
                        "status_code": response.status,
                    }
                elif response.status == 201:
                    data = await response.json()
                    return {
                        "success": True,
                        "data": data,
                        "status_code": response.status,
                    }
                elif response.status == 204:
                    return {
                        "success": True,
                        "data": None,
                        "status_code": response.status,
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"GitLab API error: {response.status}",
                        "details": error_text,
                        "status_code": response.status,
                    }
        except aiohttp.ClientError as e:
            return {"success": False, "error": f"GitLab API connection error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for operation"""
        key_parts = [operation]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return ":".join(key_parts)

    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if valid"""
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                return cached_data
            else:
                del self.cache[cache_key]
        return None

    def _set_cached_data(self, cache_key: str, data: Any):
        """Set data in cache"""
        self.cache[cache_key] = (data, datetime.now())

    async def get_projects(
        self, user_id: str = None, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get user's GitLab projects

        Args:
            user_id: User ID for filtering
            filters: Additional filters (membership, owned, starred, etc.)

        Returns:
            Dictionary with projects data
        """
        cache_key = self._generate_cache_key(
            "get_projects", user_id=user_id, filters=json.dumps(filters or {})
        )
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        params = {"per_page": 100}
        if filters:
            params.update(filters)

        result = await self._make_request("GET", "/projects", params=params)

        if result["success"] and result["data"]:
            projects = []
            for project_data in result["data"]:
                try:
                    project = GitLabProject(
                        id=project_data["id"],
                        name=project_data["name"],
                        path=project_data["path"],
                        path_with_namespace=project_data["path_with_namespace"],
                        description=project_data.get("description"),
                        web_url=project_data["web_url"],
                        namespace=project_data["namespace"],
                        visibility=project_data["visibility"],
                        star_count=project_data.get("star_count", 0),
                        forks_count=project_data.get("forks_count", 0),
                        open_issues_count=project_data.get("open_issues_count", 0),
                        last_activity_at=project_data["last_activity_at"],
                        created_at=project_data["created_at"],
                        updated_at=project_data.get(
                            "updated_at", project_data["created_at"]
                        ),
                        default_branch=project_data["default_branch"],
                        owner=project_data.get("owner"),
                    )
                    projects.append(project.to_dict())
                except KeyError as e:
                    logger.warning(f"Missing key in project data: {e}")
                    continue

            response_data = {
                "success": True,
                "projects": projects,
                "total": len(projects),
                "service": "gitlab",
            }
            self._set_cached_data(cache_key, response_data)
            return response_data
        else:
            return result

    async def get_project(self, project_id: int) -> Dict[str, Any]:
        """
        Get specific project details

        Args:
            project_id: GitLab project ID

        Returns:
            Dictionary with project details
        """
        cache_key = self._generate_cache_key("get_project", project_id=project_id)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        result = await self._make_request("GET", f"/projects/{project_id}")

        if result["success"] and result["data"]:
            project_data = result["data"]
            project = GitLabProject(
                id=project_data["id"],
                name=project_data["name"],
                path=project_data["path"],
                path_with_namespace=project_data["path_with_namespace"],
                description=project_data.get("description"),
                web_url=project_data["web_url"],
                namespace=project_data["namespace"],
                visibility=project_data["visibility"],
                star_count=project_data.get("star_count", 0),
                forks_count=project_data.get("forks_count", 0),
                open_issues_count=project_data.get("open_issues_count", 0),
                last_activity_at=project_data["last_activity_at"],
                created_at=project_data["created_at"],
                updated_at=project_data.get("updated_at", project_data["created_at"]),
                default_branch=project_data["default_branch"],
                owner=project_data.get("owner"),
            )

            response_data = {
                "success": True,
                "project": project.to_dict(),
                "service": "gitlab",
            }
            self._set_cached_data(cache_key, response_data)
            return response_data
        else:
            return result

    async def get_issues(
        self, project_id: int, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get issues for a project

        Args:
            project_id: GitLab project ID
            filters: Issue filters (state, labels, assignee, etc.)

        Returns:
            Dictionary with issues data
        """
        cache_key = self._generate_cache_key(
            "get_issues", project_id=project_id, filters=json.dumps(filters or {})
        )
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        params = {"per_page": 50}
        if filters:
            params.update(filters)

        result = await self._make_request(
            "GET", f"/projects/{project_id}/issues", params=params
        )

        if result["success"] and result["data"]:
            issues = []
            for issue_data in result["data"]:
                try:
                    issue = GitLabIssue(
                        id=issue_data["id"],
                        iid=issue_data["iid"],
                        project_id=issue_data["project_id"],
                        title=issue_data["title"],
                        description=issue_data.get("description"),
                        state=issue_data["state"],
                        labels=issue_data.get("labels", []),
                        author=issue_data["author"],
                        assignee=issue_data.get("assignee"),
                        milestone=issue_data.get("milestone"),
                        web_url=issue_data["web_url"],
                        created_at=issue_data["created_at"],
                        updated_at=issue_data["updated_at"],
                        closed_at=issue_data.get("closed_at"),
                        due_date=issue_data.get("due_date"),
                        weight=issue_data.get("weight"),
                    )
                    issues.append(issue.to_dict())
                except KeyError as e:
                    logger.warning(f"Missing key in issue data: {e}")
                    continue

            response_data = {
                "success": True,
                "issues": issues,
                "total": len(issues),
                "service": "gitlab",
            }
            self._set_cached_data(cache_key, response_data)
            return response_data
        else:
            return result

    async def get_merge_requests(
        self, project_id: int, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get merge requests for a project

        Args:
            project_id: GitLab project ID
            filters: Merge request filters (state, source_branch, etc.)

        Returns:
            Dictionary with merge requests data
        """
        cache_key = self._generate_cache_key(
            "get_merge_requests",
            project_id=project_id,
            filters=json.dumps(filters or {}),
        )
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        params = {"per_page": 50}
        if filters:
            params.update(filters)

        result = await self._make_request(
            "GET", f"/projects/{project_id}/merge_requests", params=params
        )

        if result["success"] and result["data"]:
            merge_requests = []
            for mr_data in result["data"]:
                try:
                    mr = GitLabMergeRequest(
                        id=mr_data["id"],
                        iid=mr_data["iid"],
                        project_id=mr_data["project_id"],
                        title=mr_data["title"],
                        description=mr_data.get("description"),
                        state=mr_data["state"],
                        source_branch=mr_data["source_branch"],
                        target_branch=mr_data["target_branch"],
                        author=mr_data["author"],
                        assignee=mr_data.get("assignee"),
                        reviewers=mr_data.get("reviewers", []),
                        web_url=mr_data["web_url"],
                        created_at=mr_data["created_at"],
                        updated_at=mr_data["updated_at"],
                        merged_at=mr_data.get("merged_at"),
                        closed_at=mr_data.get("closed_at"),
                        sha=mr_data["sha"],
                        merge_status=mr_data["merge_status"],
                    )
                    merge_requests.append(mr.to_dict())
                except KeyError as e:
                    logger.warning(f"Missing key in merge request data: {e}")
                    continue

            response_data = {
                "success": True,
                "merge_requests": merge_requests,
                "total": len(merge_requests),
                "service": "gitlab",
            }
            self._set_cached_data(cache_key, response_data)
            return response_data
        else:
            return result

    async def get_pipelines(
        self, project_id: int, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get CI/CD pipelines for a project

        Args:
            project_id: GitLab project ID
            filters: Pipeline filters (status, ref, etc.)

        Returns:
            Dictionary with pipelines data
        """
        cache_key = self._generate_cache_key(
            "get_pipelines", project_id=project_id, filters=json.dumps(filters or {})
        )
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        params = {"per_page": 20}
        if filters:
            params.update(filters)

        result = await self._make_request(
            "GET", f"/projects/{project_id}/pipelines", params=params
        )

        if result["success"] and result["data"]:
            pipelines = []
            for pipeline_data in result["data"]:
                try:
                    pipeline = GitLabPipeline(
                        id=pipeline_data["id"],
                        project_id=pipeline_data["project_id"],
                        status=pipeline_data["status"],
                        ref=pipeline_data["ref"],
                        sha=pipeline_data["sha"],
                        web_url=pipeline_data["web_url"],
                        created_at=pipeline_data["created_at"],
                        updated_at=pipeline_data["updated_at"],
                        started_at=pipeline_data.get("started_at"),
                        finished_at=pipeline_data.get("finished_at"),
                        duration=pipeline_data.get("duration"),
                        coverage=pipeline_data.get("coverage"),
                    )
                    pipelines.append(pipeline.to_dict())
                except KeyError as e:
                    logger.warning(f"Missing key in pipeline data: {e}")
                    continue

            response_data = {
                "success": True,
                "pipelines": pipelines,
                "total": len(pipelines),
                "service": "gitlab",
            }
            self._set_cached_data(cache_key, response_data)
            return response_data
        else:
            return result

    async def get_branches(self, project_id: int) -> Dict[str, Any]:
        """
        Get branches for a project

        Args:
            project_id: GitLab project ID

        Returns:
            Dictionary with branches data
        """
        cache_key = self._generate_cache_key("get_branches", project_id=project_id)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        result = await self._make_request(
            "GET", f"/projects/{project_id}/repository/branches"
        )
