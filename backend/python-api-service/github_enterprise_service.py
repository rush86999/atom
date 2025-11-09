#!/usr/bin/env python3
"""
GitHub Enterprise Service
Enterprise-grade service for GitHub integration
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from asyncpg import Pool

logger = logging.getLogger(__name__)

class GitHubEnterpriseService:
    """Enterprise GitHub service with comprehensive features"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self.cache = {}
        self._initialized = False
        self.rate_limit = {
            "requests": 0,
            "window_start": datetime.now(timezone.utc),
            "limit": 5000,  # GitHub rate limit for authenticated requests
            "window_minutes": 60
        }
    
    async def initialize(self, db_pool: Pool):
        """Initialize service with database pool and tokens"""
        try:
            from db_oauth_github import get_github_tokens
            
            self.db_pool = db_pool
            tokens = await get_github_tokens(db_pool, self.user_id)
            
            if tokens and not tokens.get("expired", True):
                self.access_token = tokens.get("access_token")
                self._initialized = True
                logger.info(f"Enterprise GitHub service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No valid GitHub tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize enterprise GitHub service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("GitHub enterprise service not initialized. Call initialize() first.")
    
    async def _check_rate_limit(self) -> bool:
        """Check and enforce rate limiting"""
        now = datetime.now(timezone.utc)
        window_elapsed = (now - self.rate_limit["window_start"]).seconds
        
        # Reset window if elapsed
        if window_elapsed >= self.rate_limit["window_minutes"] * 60:
            self.rate_limit["requests"] = 0
            self.rate_limit["window_start"] = now
            return True
        
        # Check limit
        if self.rate_limit["requests"] >= self.rate_limit["limit"]:
            logger.warning("GitHub API rate limit exceeded")
            return False
        
        self.rate_limit["requests"] += 1
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization"""
        return {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "ATOM-Enterprise-GitHub/1.0"
        }
    
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get comprehensive GitHub user profile"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            # Check cache first
            cache_key = f"user_profile_{self.user_id}"
            if cache_key in self.cache:
                cache_time = self.cache[cache_key]["timestamp"]
                if datetime.now(timezone.utc) - cache_time < timedelta(minutes=5):
                    return self.cache[cache_key]["data"]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                user_info = {
                    "id": data.get("id"),
                    "login": data.get("login"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "avatar_url": data.get("avatar_url"),
                    "bio": data.get("bio"),
                    "location": data.get("location"),
                    "company": data.get("company"),
                    "website": data.get("blog"),
                    "public_repos": data.get("public_repos"),
                    "private_repos": data.get("total_private_repos", 0),
                    "followers": data.get("followers"),
                    "following": data.get("following"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "hireable": data.get("hireable"),
                    "two_factor_authentication": data.get("two_factor_authentication"),
                    "last_login": datetime.now(timezone.utc).isoformat()
                }
                
                # Cache result
                self.cache[cache_key] = {
                    "data": {"success": True, "data": user_info},
                    "timestamp": datetime.now(timezone.utc)
                }
                
                return {"success": True, "data": user_info}
                
        except Exception as e:
            logger.error(f"Failed to get GitHub user profile: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_repositories(self, type: str = "all", sort: str = "updated", per_page: int = 100) -> Dict[str, Any]:
        """List GitHub repositories"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            params = {
                "type": type,  # all, owner, member
                "sort": sort,  # created, updated, pushed, full_name
                "per_page": per_page
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/user/repos",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                repositories = []
                
                for repo in data:
                    repo_info = {
                        "id": repo.get("id"),
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "description": repo.get("description"),
                        "private": repo.get("private"),
                        "fork": repo.get("fork"),
                        "html_url": repo.get("html_url"),
                        "clone_url": repo.get("clone_url"),
                        "ssh_url": repo.get("ssh_url"),
                        "language": repo.get("language"),
                        "languages": {},  # Will be populated separately
                        "size": repo.get("size"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "watchers_count": repo.get("watchers_count"),
                        "forks_count": repo.get("forks_count"),
                        "open_issues_count": repo.get("open_issues_count"),
                        "topics": repo.get("topics", []),
                        "archived": repo.get("archived"),
                        "disabled": repo.get("disabled"),
                        "default_branch": repo.get("default_branch"),
                        "created_at": repo.get("created_at"),
                        "updated_at": repo.get("updated_at"),
                        "pushed_at": repo.get("pushed_at"),
                        "permissions": repo.get("permissions", {}),
                        "owner": {
                            "login": repo["owner"]["login"],
                            "avatar_url": repo["owner"]["avatar_url"]
                        }
                    }
                    repositories.append(repo_info)
                
                return {
                    "success": True,
                    "data": repositories,
                    "total": len(repositories),
                    "type": type,
                    "sort": sort
                }
                
        except Exception as e:
            logger.error(f"Failed to list GitHub repositories: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_repository_details(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get detailed repository information"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            async with httpx.AsyncClient() as client:
                # Get repo details
                repo_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}",
                    headers=self._get_headers()
                )
                repo_response.raise_for_status()
                repo_data = repo_response.json()
                
                # Get languages
                lang_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/languages",
                    headers=self._get_headers()
                )
                lang_response.raise_for_status()
                languages = lang_response.json()
                
                # Get contributors (simplified)
                contrib_response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contributors",
                    headers=self._get_headers(),
                    params={"per_page": 10}
                )
                contrib_response.raise_for_status()
                contributors = contrib_response.json()
                
                repo_details = {
                    "id": repo_data.get("id"),
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "description": repo_data.get("description"),
                    "private": repo_data.get("private"),
                    "fork": repo_data.get("fork"),
                    "html_url": repo_data.get("html_url"),
                    "clone_url": repo_data.get("clone_url"),
                    "ssh_url": repo_data.get("ssh_url"),
                    "language": repo_data.get("language"),
                    "languages": languages,
                    "size": repo_data.get("size"),
                    "stargazers_count": repo_data.get("stargazers_count"),
                    "watchers_count": repo_data.get("watchers_count"),
                    "forks_count": repo_data.get("forks_count"),
                    "open_issues_count": repo_data.get("open_issues_count"),
                    "topics": repo_data.get("topics", []),
                    "archived": repo_data.get("archived"),
                    "disabled": repo_data.get("disabled"),
                    "default_branch": repo_data.get("default_branch"),
                    "license": repo_data.get("license"),
                    "readme": None,  # Could fetch README separately
                    "created_at": repo_data.get("created_at"),
                    "updated_at": repo_data.get("updated_at"),
                    "pushed_at": repo_data.get("pushed_at"),
                    "contributors_count": len(contributors),
                    "top_contributors": [
                        {
                            "login": contrib["login"],
                            "avatar_url": contrib["avatar_url"],
                            "contributions": contrib["contributions"]
                        }
                        for contrib in contributors[:5]
                    ],
                    "permissions": repo_data.get("permissions", {}),
                    "owner": {
                        "login": repo_data["owner"]["login"],
                        "avatar_url": repo_data["owner"]["avatar_url"]
                    }
                }
                
                return {
                    "success": True,
                    "data": repo_details
                }
                
        except Exception as e:
            logger.error(f"Failed to get GitHub repository details: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_pull_requests(self, owner: str, repo: str, state: str = "open", per_page: int = 100) -> Dict[str, Any]:
        """List pull requests for a repository"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            params = {
                "state": state,  # open, closed, all
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                pull_requests = []
                
                for pr in data:
                    pr_info = {
                        "id": pr.get("id"),
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "body": pr.get("body"),
                        "state": pr.get("state"),
                        "draft": pr.get("draft"),
                        "user": {
                            "login": pr["user"]["login"],
                            "avatar_url": pr["user"]["avatar_url"]
                        },
                        "created_at": pr.get("created_at"),
                        "updated_at": pr.get("updated_at"),
                        "head": {
                            "ref": pr["head"]["ref"],
                            "sha": pr["head"]["sha"],
                            "repo": pr["head"]["repo"]["full_name"] if pr["head"]["repo"] else None
                        },
                        "base": {
                            "ref": pr["base"]["ref"],
                            "sha": pr["base"]["sha"],
                            "repo": pr["base"]["repo"]["full_name"]
                        },
                        "mergeable": None,  # Would need separate API call
                        "merged": pr.get("merged"),
                        "mergeable_state": pr.get("mergeable_state"),
                        "comments": pr.get("comments"),
                        "review_comments": pr.get("review_comments"),
                        "commits": pr.get("commits"),
                        "additions": pr.get("additions"),
                        "deletions": pr.get("deletions"),
                        "changed_files": pr.get("changed_files"),
                        "url": pr.get("html_url"),
                        "diff_url": pr.get("diff_url"),
                        "patch_url": pr.get("patch_url")
                    }
                    pull_requests.append(pr_info)
                
                return {
                    "success": True,
                    "data": pull_requests,
                    "total": len(pull_requests),
                    "state": state
                }
                
        except Exception as e:
            logger.error(f"Failed to list GitHub pull requests: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_issues(self, owner: str, repo: str, state: str = "open", per_page: int = 100) -> Dict[str, Any]:
        """List issues for a repository"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            params = {
                "state": state,  # open, closed, all
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                issues = []
                
                # Filter out pull requests (they're returned as issues too)
                for issue in data:
                    if "pull_request" not in issue:
                        issue_info = {
                            "id": issue.get("id"),
                            "number": issue.get("number"),
                            "title": issue.get("title"),
                            "body": issue.get("body"),
                            "state": issue.get("state"),
                            "user": {
                                "login": issue["user"]["login"],
                                "avatar_url": issue["user"]["avatar_url"]
                            },
                            "assignees": [
                                {
                                    "login": assignee["login"],
                                    "avatar_url": assignee["avatar_url"]
                                }
                                for assignee in issue.get("assignees", [])
                            ],
                            "labels": [
                                {
                                    "name": label["name"],
                                    "color": label["color"]
                                }
                                for label in issue.get("labels", [])
                            ],
                            "milestone": issue.get("milestone"),
                            "comments": issue.get("comments"),
                            "reactions": issue.get("reactions", {}),
                            "created_at": issue.get("created_at"),
                            "updated_at": issue.get("updated_at"),
                            "closed_at": issue.get("closed_at"),
                            "url": issue.get("html_url")
                        }
                        issues.append(issue_info)
                
                return {
                    "success": True,
                    "data": issues,
                    "total": len(issues),
                    "state": state
                }
                
        except Exception as e:
            logger.error(f"Failed to list GitHub issues: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_webhook(self, owner: str, repo: str, webhook_url: str, events: List[str], secret: Optional[str] = None) -> Dict[str, Any]:
        """Create webhook for a repository"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            webhook_config = {
                "name": "web",
                "active": True,
                "events": events,
                "config": {
                    "url": webhook_url,
                    "content_type": "json"
                }
            }
            
            if secret:
                webhook_config["config"]["secret"] = secret
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo}/hooks",
                    headers=self._get_headers(),
                    json=webhook_config
                )
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "active": data.get("active"),
                        "events": data.get("events"),
                        "config": data.get("config"),
                        "url": data.get("config", {}).get("url"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create GitHub webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_repository_analytics(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository analytics"""
        try:
            await self._ensure_initialized()
            
            # Get repository details
            repo_result = await self.get_repository_details(owner, repo)
            if not repo_result.get("success"):
                return repo_result
            
            repo_data = repo_result["data"]
            
            # Get traffic data (simplified)
            analytics = {
                "overview": {
                    "stars": repo_data["stargazers_count"],
                    "forks": repo_data["forks_count"],
                    "watchers": repo_data["watchers_count"],
                    "open_issues": repo_data["open_issues_count"],
                    "size": repo_data["size"],
                    "created_at": repo_data["created_at"],
                    "last_updated": repo_data["pushed_at"]
                },
                "languages": repo_data["languages"],
                "top_contributors": repo_data["top_contributors"],
                "topics": repo_data["topics"],
                "is_popular": repo_data["stargazers_count"] > 100,
                "is_active": repo_data["pushed_at"] and (
                    datetime.now(timezone.utc) - datetime.fromisoformat(
                        repo_data["pushed_at"].replace("Z", "+00:00")
                    ).replace(tzinfo=timezone.utc)
                ).days < 30
            }
            
            return {
                "success": True,
                "data": analytics
            }
            
        except Exception as e:
            logger.error(f"Failed to get GitHub repository analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def clear_cache(self):
        """Clear service cache"""
        self.cache.clear()
        logger.info("Cache cleared for GitHub enterprise service")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        return {
            "service": "GitHub Enterprise",
            "initialized": self._initialized,
            "user_id": self.user_id,
            "cache_size": len(self.cache),
            "rate_limit": {
                "requests": self.rate_limit["requests"],
                "limit": self.rate_limit["limit"],
                "window_minutes": self.rate_limit["window_minutes"],
                "reset_time": (self.rate_limit["window_start"] + timedelta(minutes=self.rate_limit["window_minutes"])).isoformat()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Factory function
def create_github_enterprise_service(user_id: str) -> GitHubEnterpriseService:
    """Create enterprise GitHub service instance"""
    return GitHubEnterpriseService(user_id)

# Export service class
__all__ = [
    'GitHubEnterpriseService',
    'create_github_enterprise_service'
]
