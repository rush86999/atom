"""
GitHub Service for ATOM Platform
Provides comprehensive GitHub integration functionality
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import requests

logger = logging.getLogger(__name__)

class GitHubService:
    """GitHub API integration service"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('GITHUB_ACCESS_TOKEN')
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        if self.access_token:
            self.session.headers.update({
                'Authorization': f'token {self.access_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'ATOM-Platform/1.0'
            })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test GitHub API connection"""
        try:
            response = self.session.get(f"{self.base_url}/user")
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "success",
                    "message": "GitHub connection successful",
                    "user": user_data['login'],
                    "authenticated": True
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_user_repositories(self, type: str = "all") -> List[Dict[str, Any]]:
        """Get user repositories"""
        try:
            params = {"type": type, "sort": "updated", "per_page": 100}
            response = self.session.get(f"{self.base_url}/user/repos", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get repositories: {e}")
            return []
    
    def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Get repository details"""
        try:
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get repository {owner}/{repo}: {e}")
            return None
    
    def get_repository_issues(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """Get repository issues"""
        try:
            params = {"state": state, "sort": "updated", "per_page": 50}
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/issues", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get issues for {owner}/{repo}: {e}")
            return []
    
    def get_repository_pulls(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """Get repository pull requests"""
        try:
            params = {"state": state, "sort": "updated", "per_page": 50}
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/pulls", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get pull requests for {owner}/{repo}: {e}")
            return []
    
    def create_issue(self, owner: str, repo: str, title: str, body: str, labels: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new issue"""
        try:
            data = {
                "title": title,
                "body": body,
                "labels": labels or []
            }
            response = self.session.post(f"{self.base_url}/repos/{owner}/{repo}/issues", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create issue in {owner}/{repo}: {e}")
            return None
    
    def create_pull_request(self, owner: str, repo: str, title: str, head: str, base: str, body: str = "") -> Optional[Dict[str, Any]]:
        """Create a pull request"""
        try:
            data = {
                "title": title,
                "head": head,
                "base": base,
                "body": body
            }
            response = self.session.post(f"{self.base_url}/repos/{owner}/{repo}/pulls", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create pull request in {owner}/{repo}: {e}")
            return None
    
    def get_user_commits(self, owner: str, repo: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get commits for a repository"""
        try:
            params = {"per_page": 100}
            if since:
                params["since"] = since.isoformat()
            
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/commits", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get commits for {owner}/{repo}: {e}")
            return []
    
    def get_workflow_runs(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get GitHub Actions workflow runs"""
        try:
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/actions/runs")
            response.raise_for_status()
            return response.json().get('workflow_runs', [])
        except Exception as e:
            logger.error(f"Failed to get workflow runs for {owner}/{repo}: {e}")
            return []
    
    def get_repository_stats(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository statistics"""
        try:
            # Get basic repo info
            repo_data = self.get_repository(owner, repo)
            if not repo_data:
                return {}
            
            # Get issues count
            issues = self.get_repository_issues(owner, repo, "all")
            # Get PRs count
            pulls = self.get_repository_pulls(owner, repo, "all")
            
            return {
                "name": repo_data["full_name"],
                "stars": repo_data["stargazers_count"],
                "forks": repo_data["forks_count"],
                "open_issues": repo_data["open_issues_count"],
                "total_issues": len(issues),
                "total_prs": len(pulls),
                "language": repo_data.get("language"),
                "updated_at": repo_data["updated_at"],
                "created_at": repo_data["created_at"]
            }
        except Exception as e:
            logger.error(f"Failed to get repository stats for {owner}/{repo}: {e}")
            return {}
    
    def search_repositories(self, query: str, sort: str = "updated", order: str = "desc") -> List[Dict[str, Any]]:
        """Search repositories"""
        try:
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": 50
            }
            response = self.session.get(f"{self.base_url}/search/repositories", params=params)
            response.raise_for_status()
            return response.json().get('items', [])
        except Exception as e:
            logger.error(f"Failed to search repositories: {e}")
            return []
    
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get current user profile"""
        try:
            response = self.session.get(f"{self.base_url}/user")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None

# Singleton instance for global access
github_service = GitHubService()

def get_github_service() -> GitHubService:
    """Get GitHub service instance"""
    return github_service