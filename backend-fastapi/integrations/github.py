from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import os

class GitHubIntegration:
    """GitHub API integration for ATOM platform"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.token = os.getenv("GITHUB_TOKEN", "mock_github_token")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    async def search_repositories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search repositories"""
        try:
            url = f"{self.base_url}/search/repositories"
            params = {"q": query, "per_page": limit}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": item["id"],
                        "type": "github",
                        "title": item["name"],
                        "description": item["description"] or "",
                        "url": item["html_url"],
                        "service": "github",
                        "created_at": item["created_at"],
                        "metadata": {
                            "language": item["language"],
                            "stars": item["stargazers_count"],
                            "forks": item["forks_count"],
                            "updated_at": item["updated_at"],
                            "owner": item["owner"]["login"]
                        }
                    }
                    for item in data.get("items", [])
                ]
        except Exception as e:
            print(f"GitHub search error: {e}")
        
        # Return mock data for demo
        return [
            {
                "id": "github-repo-1",
                "type": "github",
                "title": "atom-automation",
                "description": "Enterprise automation platform",
                "url": "https://github.com/atom/automation",
                "service": "github",
                "created_at": "2024-01-01T00:00:00Z",
                "metadata": {
                    "language": "Python",
                    "stars": 150,
                    "forks": 30
                }
            }
        ]
    
    async def get_issues(self, repository: str) -> List[Dict[str, Any]]:
        """Get repository issues"""
        # Mock implementation
        return [
            {
                "id": "issue-1",
                "title": "Implement OAuth integration",
                "state": "open",
                "created_at": "2024-01-10T00:00:00Z"
            }
        ]
