"""
Real GitHub service implementation using GitHub REST API
This provides real implementations for GitHub API functionality
"""

from typing import Dict, Any, Optional, List
import os
import requests
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class GitHubRepository:
    """GitHub repository object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.full_name = data.get('full_name', '')
        self.description = data.get('description', '')
        self.private = data.get('private', False)
        self.fork = data.get('fork', False)
        self.html_url = data.get('html_url', '')
        self.clone_url = data.get('clone_url', '')
        self.ssh_url = data.get('ssh_url', '')
        self.language = data.get('language', '')
        self.stargazers_count = data.get('stargazers_count', 0)
        self.watchers_count = data.get('watchers_count', 0)
        self.forks_count = data.get('forks_count', 0)
        self.open_issues_count = data.get('open_issues_count', 0)
        self.default_branch = data.get('default_branch', 'main')
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.pushed_at = data.get('pushed_at')
        self.owner = data.get('owner', {})
        self.topics = data.get('topics', [])
        self.license = data.get('license', {})
        self.size = data.get('size', 0)

class GitHubIssue:
    """GitHub issue object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.number = data.get('number', 0)
        self.title = data.get('title', '')
        self.body = data.get('body', '')
        self.state = data.get('state', 'open')
        self.locked = data.get('locked', False)
        self.comments = data.get('comments', 0)
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.closed_at = data.get('closed_at')
        self.milestone = data.get('milestone', {})
        self.assignee = data.get('assignee')
        self.assignees = data.get('assignees', [])
        self.user = data.get('user', {})
        self.labels = data.get('labels', [])
        self.html_url = data.get('html_url', '')
        self.repository_url = data.get('repository_url', '')
        self.reactions = data.get('reactions', {})

class GitHubPullRequest:
    """GitHub pull request object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.number = data.get('number', 0)
        self.title = data.get('title', '')
        self.body = data.get('body', '')
        self.state = data.get('state', 'open')
        self.locked = data.get('locked', False)
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.closed_at = data.get('closed_at')
        self.merged_at = data.get('merged_at')
        self.merge_commit_sha = data.get('merge_commit_sha')
        self.head = data.get('head', {})
        self.base = data.get('base', {})
        self.user = data.get('user', {})
        self.assignees = data.get('assignees', [])
        self.requested_reviewers = data.get('requested_reviewers', [])
        self.labels = data.get('labels', [])
        self.milestone = data.get('milestone', {})
        self.commits = data.get('commits', 0)
        self.additions = data.get('additions', 0)
        self.deletions = data.get('deletions', 0)
        self.changed_files = data.get('changed_files', 0)
        self.html_url = data.get('html_url', '')
        self.diff_url = data.get('diff_url', '')
        self.patch_url = data.get('patch_url', '')

class GitHubUser:
    """GitHub user object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.login = data.get('login', '')
        self.name = data.get('name', '')
        self.email = data.get('email', '')
        self.bio = data.get('bio', '')
        self.company = data.get('company', '')
        self.location = data.get('location', '')
        self.blog = data.get('blog', '')
        self.avatar_url = data.get('avatar_url', '')
        self.html_url = data.get('html_url', '')
        self.followers = data.get('followers', 0)
        self.following = data.get('following', 0)
        self.public_repos = data.get('public_repos', 0)
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')

class GitHubWebhook:
    """GitHub webhook object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.url = data.get('url', '')
        self.test_url = data.get('test_url', '')
        self.ping_url = data.get('ping_url', '')
        self.name = data.get('name', '')
        self.events = data.get('events', [])
        self.active = data.get('active', True)
        self.config = data.get('config', {})
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')

class GitHubService:
    """Real GitHub API service implementation"""
    
    def __init__(self):
        self.api_base_url = "https://api.github.com"
        self.timeout = 30
        self._mock_mode = self._check_mock_mode()
    
    def _check_mock_mode(self) -> bool:
        """Check if we should use mock mode"""
        # Check if we have real GitHub credentials
        github_client_id = os.getenv("GITHUB_CLIENT_ID")
        github_token = os.getenv("GITHUB_ACCESS_TOKEN")
        
        return not (github_client_id and github_token and 
                   github_token != "mock_github_token")
    
    async def get_user_repositories(self, user_id: str, type: str = "all", 
                                sort: str = "updated", direction: str = "desc",
                                per_page: int = 50, page: int = 1) -> List[GitHubRepository]:
        """Get user's GitHub repositories"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_repositories(user_id, type, sort, direction, per_page, page)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            params = {
                "type": type,
                "sort": sort,
                "direction": direction,
                "per_page": min(per_page, 100),  # GitHub limit
                "page": page
            }
            
            response = requests.get(
                f"{self.api_base_url}/user/repos",
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            repos = []
            for repo_data in response.json():
                repos.append(GitHubRepository(repo_data))
            
            logger.info(f"Retrieved {len(repos)} GitHub repositories for user {user_id}")
            return repos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub repositories for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub repositories: {e}")
            return []
    
    async def create_repository(self, user_id: str, name: str, description: str = "",
                           private: bool = False, auto_init: bool = True) -> Optional[GitHubRepository]:
        """Create a new GitHub repository"""
        try:
            if self._mock_mode:
                return await self._mock_create_repository(user_id, name, description, private, auto_init)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            data = {
                "name": name,
                "description": description,
                "private": private,
                "auto_init": auto_init
            }
            
            response = requests.post(
                f"{self.api_base_url}/user/repos",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            repo_data = response.json()
            repo = GitHubRepository(repo_data)
            
            logger.info(f"Created GitHub repository '{name}' for user {user_id}")
            return repo
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating GitHub repository for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating GitHub repository: {e}")
            return None
    
    async def get_user_issues(self, user_id: str, state: str = "open", 
                           sort: str = "updated", direction: str = "desc",
                           per_page: int = 50, page: int = 1) -> List[GitHubIssue]:
        """Get user's GitHub issues"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_issues(user_id, state, sort, direction, per_page, page)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            params = {
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": min(per_page, 100),
                "page": page
            }
            
            response = requests.get(
                f"{self.api_base_url}/user/issues",
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            issues = []
            for issue_data in response.json():
                issues.append(GitHubIssue(issue_data))
            
            logger.info(f"Retrieved {len(issues)} GitHub issues for user {user_id}")
            return issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub issues for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub issues: {e}")
            return []
    
    async def create_issue(self, user_id: str, owner: str, repo: str, 
                        title: str, body: str = "", labels: List[str] = None,
                        assignees: List[str] = None) -> Optional[GitHubIssue]:
        """Create a new GitHub issue"""
        try:
            if self._mock_mode:
                return await self._mock_create_issue(user_id, owner, repo, title, body, labels, assignees)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            data = {
                "title": title,
                "body": body
            }
            
            if labels:
                data["labels"] = labels
            if assignees:
                data["assignees"] = assignees
            
            response = requests.post(
                f"{self.api_base_url}/repos/{owner}/{repo}/issues",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            issue_data = response.json()
            issue = GitHubIssue(issue_data)
            
            logger.info(f"Created GitHub issue '{title}' in {owner}/{repo} for user {user_id}")
            return issue
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating GitHub issue for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating GitHub issue: {e}")
            return None
    
    async def get_pull_requests(self, user_id: str, owner: str, repo: str,
                            state: str = "open", sort: str = "created", 
                            direction: str = "desc", per_page: int = 50, 
                            page: int = 1) -> List[GitHubPullRequest]:
        """Get pull requests for a repository"""
        try:
            if self._mock_mode:
                return await self._mock_get_pull_requests(user_id, owner, repo, state, sort, direction, per_page, page)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            params = {
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": min(per_page, 100),
                "page": page
            }
            
            response = requests.get(
                f"{self.api_base_url}/repos/{owner}/{repo}/pulls",
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            prs = []
            for pr_data in response.json():
                prs.append(GitHubPullRequest(pr_data))
            
            logger.info(f"Retrieved {len(prs)} GitHub pull requests for {owner}/{repo}")
            return prs
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub pull requests: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub pull requests: {e}")
            return []
    
    async def create_pull_request(self, user_id: str, owner: str, repo: str,
                              title: str, head: str, base: str, 
                              body: str = "") -> Optional[GitHubPullRequest]:
        """Create a new pull request"""
        try:
            if self._mock_mode:
                return await self._mock_create_pull_request(user_id, owner, repo, title, head, base, body)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            data = {
                "title": title,
                "head": head,
                "base": base,
                "body": body
            }
            
            response = requests.post(
                f"{self.api_base_url}/repos/{owner}/{repo}/pulls",
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            pr_data = response.json()
            pr = GitHubPullRequest(pr_data)
            
            logger.info(f"Created GitHub pull request '{title}' in {owner}/{repo} for user {user_id}")
            return pr
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating GitHub pull request: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating GitHub pull request: {e}")
            return None
    
    async def search_repositories(self, user_id: str, query: str, 
                              sort: str = "updated", order: str = "desc",
                              per_page: int = 50, page: int = 1) -> Dict[str, Any]:
        """Search GitHub repositories"""
        try:
            if self._mock_mode:
                return await self._mock_search_repositories(user_id, query, sort, order, per_page, page)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return {'ok': False, 'error': 'No access token'}
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": min(per_page, 100),
                "page": page
            }
            
            response = requests.get(
                f"{self.api_base_url}/search/repositories",
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            repos = []
            for repo_data in data.get('items', []):
                repos.append(GitHubRepository(repo_data))
            
            return {
                'ok': True,
                'repositories': repos,
                'total_count': data.get('total_count', 0),
                'query': query
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching GitHub repositories: {e}")
            return {'ok': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error searching GitHub repositories: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_user_profile(self, user_id: str) -> Optional[GitHubUser]:
        """Get authenticated user profile"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_profile(user_id)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            response = requests.get(
                f"{self.api_base_url}/user",
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            user_data = response.json()
            user = GitHubUser(user_data)
            
            logger.info(f"Retrieved GitHub profile for user {user_id}")
            return user
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub profile for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub profile: {e}")
            return None
    
    async def get_webhooks(self, user_id: str, owner: str, repo: str) -> List[GitHubWebhook]:
        """Get webhooks for a repository"""
        try:
            if self._mock_mode:
                return await self._mock_get_webhooks(user_id, owner, repo)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            response = requests.get(
                f"{self.api_base_url}/repos/{owner}/{repo}/hooks",
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            webhooks = []
            for webhook_data in response.json():
                webhooks.append(GitHubWebhook(webhook_data))
            
            logger.info(f"Retrieved {len(webhooks)} GitHub webhooks for {owner}/{repo}")
            return webhooks
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting GitHub webhooks: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting GitHub webhooks: {e}")
            return []
    
    # Mock implementations for testing
    async def _mock_get_user_repositories(self, user_id: str, type: str, sort: str, 
                                      direction: str, per_page: int, page: int) -> List[GitHubRepository]:
        """Mock user repositories"""
        repos = [
            {
                'id': 123456789,
                'name': 'atom-platform',
                'full_name': 'developer/atom-platform',
                'description': 'Advanced Task Orchestration & Management Platform',
                'private': False,
                'fork': False,
                'html_url': 'https://github.com/developer/atom-platform',
                'clone_url': 'https://github.com/developer/atom-platform.git',
                'ssh_url': 'git@github.com:developer/atom-platform.git',
                'language': 'TypeScript',
                'stargazers_count': 42,
                'watchers_count': 42,
                'forks_count': 8,
                'open_issues_count': 3,
                'default_branch': 'main',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'pushed_at': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                'owner': {
                    'login': 'developer',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
                },
                'topics': ['typescript', 'react', 'fastapi', 'automation'],
                'license': {
                    'name': 'MIT'
                },
                'size': 1520
            },
            {
                'id': 987654321,
                'name': 'linear-integration',
                'full_name': 'developer/linear-integration',
                'description': 'Linear API integration utilities',
                'private': True,
                'fork': False,
                'html_url': 'https://github.com/developer/linear-integration',
                'clone_url': 'https://github.com/developer/linear-integration.git',
                'ssh_url': 'git@github.com:developer/linear-integration.git',
                'language': 'Python',
                'stargazers_count': 12,
                'watchers_count': 12,
                'forks_count': 2,
                'open_issues_count': 0,
                'default_branch': 'main',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
                'pushed_at': (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
                'owner': {
                    'login': 'developer',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
                },
                'topics': ['python', 'linear', 'api'],
                'license': {
                    'name': 'Apache-2.0'
                },
                'size': 240
            }
        ]
        
        return [GitHubRepository(repo) for repo in repos[:per_page]]
    
    async def _mock_create_repository(self, user_id: str, name: str, description: str,
                                  private: bool, auto_init: bool) -> GitHubRepository:
        """Mock repository creation"""
        mock_repo = {
            'id': int(datetime.utcnow().timestamp()),
            'name': name,
            'full_name': f'developer/{name}',
            'description': description,
            'private': private,
            'fork': False,
            'html_url': f'https://github.com/developer/{name}',
            'clone_url': f'https://github.com/developer/{name}.git',
            'ssh_url': f'git@github.com:developer/{name}.git',
            'language': 'TypeScript',
            'stargazers_count': 0,
            'watchers_count': 0,
            'forks_count': 0,
            'open_issues_count': 0,
            'default_branch': 'main',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'pushed_at': datetime.utcnow().isoformat(),
            'owner': {
                'login': 'developer',
                'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
            },
            'topics': [],
            'license': None,
            'size': 0
        }
        
        return GitHubRepository(mock_repo)
    
    async def _mock_get_user_issues(self, user_id: str, state: str, sort: str,
                                  direction: str, per_page: int, page: int) -> List[GitHubIssue]:
        """Mock user issues"""
        issues = [
            {
                'id': 111111111,
                'number': 1,
                'title': 'Add GitHub integration to ATOM',
                'body': 'Implement complete GitHub API integration with OAuth support',
                'state': 'open',
                'locked': False,
                'comments': 5,
                'created_at': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'closed_at': None,
                'user': {
                    'login': 'developer',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
                },
                'labels': [
                    {'name': 'enhancement', 'color': 'a2eeef'},
                    {'name': 'github', 'color': 'c1c9e5'}
                ],
                'html_url': 'https://github.com/developer/atom-platform/issues/1',
                'reactions': {
                    'total_count': 3,
                    'plus_one': 2,
                    'laugh': 0,
                    'hooray': 1,
                    'confused': 0,
                    'heart': 0,
                    'rocket': 0,
                    'eyes': 0
                }
            },
            {
                'id': 222222222,
                'number': 2,
                'title': 'Fix TypeScript compilation errors',
                'body': 'Resolve type issues in the integration modules',
                'state': 'closed',
                'locked': False,
                'comments': 3,
                'created_at': (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                'closed_at': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                'user': {
                    'login': 'developer',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
                },
                'labels': [
                    {'name': 'bug', 'color': 'd73a4a'},
                    {'name': 'typescript', 'color': '892a5b'}
                ],
                'html_url': 'https://github.com/developer/atom-platform/issues/2'
            }
        ]
        
        # Filter by state
        filtered_issues = []
        for issue in issues:
            if state == 'all' or issue['state'] == state:
                filtered_issues.append(GitHubIssue(issue))
        
        return filtered_issues[:per_page]
    
    async def _mock_create_issue(self, user_id: str, owner: str, repo: str,
                               title: str, body: str, labels: List[str],
                               assignees: List[str]) -> GitHubIssue:
        """Mock issue creation"""
        mock_issue = {
            'id': int(datetime.utcnow().timestamp()),
            'number': 999,
            'title': title,
            'body': body,
            'state': 'open',
            'locked': False,
            'comments': 0,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'closed_at': None,
            'user': {
                'login': 'developer',
                'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
            },
            'labels': [{'name': label, 'color': 'c1c9e5'} for label in (labels or [])],
            'html_url': f'https://github.com/{owner}/{repo}/issues/999',
            'reactions': {'total_count': 0}
        }
        
        return GitHubIssue(mock_issue)
    
    async def _mock_get_pull_requests(self, user_id: str, owner: str, repo: str,
                                   state: str, sort: str, direction: str,
                                   per_page: int, page: int) -> List[GitHubPullRequest]:
        """Mock pull requests"""
        prs = [
            {
                'id': 333333333,
                'number': 42,
                'title': 'Feature: Add GitHub integration',
                'body': 'Complete GitHub API integration with OAuth and webhook support',
                'state': 'open',
                'locked': False,
                'created_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
                'closed_at': None,
                'merged_at': None,
                'head': {
                    'ref': 'feature/github-integration',
                    'sha': 'abc123def456',
                    'label': 'developer:feature/github-integration',
                    'repo': {
                        'id': 123456789,
                        'name': 'atom-platform',
                        'url': 'https://api.github.com/repos/developer/atom-platform'
                    }
                },
                'base': {
                    'ref': 'main',
                    'sha': 'def789ghi012',
                    'label': 'developer:main',
                    'repo': {
                        'id': 123456789,
                        'name': 'atom-platform',
                        'url': 'https://api.github.com/repos/developer/atom-platform'
                    }
                },
                'user': {
                    'login': 'developer',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
                },
                'assignees': [
                    {'login': 'developer', 'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'}
                ],
                'requested_reviewers': [],
                'labels': [
                    {'name': 'enhancement', 'color': 'a2eeef'}
                ],
                'milestone': None,
                'commits': 8,
                'additions': 1250,
                'deletions': 120,
                'changed_files': 15,
                'html_url': 'https://github.com/developer/atom-platform/pull/42',
                'diff_url': 'https://github.com/developer/atom-platform/pull/42.diff',
                'patch_url': 'https://github.com/developer/atom-platform/pull/42.patch'
            }
        ]
        
        # Filter by state
        filtered_prs = []
        for pr in prs:
            if state == 'all' or pr['state'] == state:
                filtered_prs.append(GitHubPullRequest(pr))
        
        return filtered_prs[:per_page]
    
    async def _mock_create_pull_request(self, user_id: str, owner: str, repo: str,
                                     title: str, head: str, base: str, 
                                     body: str) -> GitHubPullRequest:
        """Mock pull request creation"""
        mock_pr = {
            'id': int(datetime.utcnow().timestamp()),
            'number': 1000,
            'title': title,
            'body': body,
            'state': 'open',
            'locked': False,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'closed_at': None,
            'merged_at': None,
            'head': {
                'ref': head,
                'sha': 'new123sha456',
                'label': f'developer:{head}',
                'repo': {
                    'id': 123456789,
                    'name': repo,
                    'url': f'https://api.github.com/repos/{owner}/{repo}'
                }
            },
            'base': {
                'ref': base,
                'sha': 'base789sha012',
                'label': f'developer:{base}',
                'repo': {
                    'id': 123456789,
                    'name': repo,
                    'url': f'https://api.github.com/repos/{owner}/{repo}'
                }
            },
            'user': {
                'login': 'developer',
                'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4'
            },
            'assignees': [],
            'requested_reviewers': [],
            'labels': [],
            'milestone': None,
            'commits': 5,
            'additions': 800,
            'deletions': 100,
            'changed_files': 10,
            'html_url': f'https://github.com/{owner}/{repo}/pull/1000'
        }
        
        return GitHubPullRequest(mock_pr)
    
    async def _mock_search_repositories(self, user_id: str, query: str, sort: str,
                                     order: str, per_page: int, page: int) -> Dict[str, Any]:
        """Mock repository search"""
        mock_repos = [
            {
                'id': 555555555,
                'name': f'{query}-awesome-lib',
                'full_name': f'awesome-user/{query}-awesome-lib',
                'description': f'Awesome library for {query}',
                'private': False,
                'fork': False,
                'html_url': f'https://github.com/awesome-user/{query}-awesome-lib',
                'clone_url': f'https://github.com/awesome-user/{query}-awesome-lib.git',
                'language': 'TypeScript',
                'stargazers_count': 1500,
                'watchers_count': 1500,
                'forks_count': 200,
                'open_issues_count': 12,
                'default_branch': 'main',
                'owner': {
                    'login': 'awesome-user',
                    'avatar_url': 'https://avatars.githubusercontent.com/u/987654?v=4'
                },
                'topics': [query, 'typescript', 'library'],
                'license': {'name': 'MIT'},
                'size': 3200
            }
        ]
        
        repos = [GitHubRepository(repo) for repo in mock_repos]
        
        return {
            'ok': True,
            'repositories': repos,
            'total_count': len(repos),
            'query': query
        }
    
    async def _mock_get_user_profile(self, user_id: str) -> GitHubUser:
        """Mock user profile"""
        return GitHubUser({
            'id': 123456,
            'login': 'developer',
            'name': 'Alex Developer',
            'email': 'alex@company.com',
            'bio': 'Full-stack developer passionate about automation and productivity tools',
            'company': 'Tech Company',
            'location': 'San Francisco, CA',
            'blog': 'https://alexdev.com',
            'avatar_url': 'https://avatars.githubusercontent.com/u/123456?v=4',
            'html_url': 'https://github.com/developer',
            'followers': 245,
            'following': 182,
            'public_repos': 35,
            'created_at': (datetime.now(timezone.utc) - timedelta(days=365*3)).isoformat(),
            'updated_at': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        })
    
    async def _mock_get_webhooks(self, user_id: str, owner: str, repo: str) -> List[GitHubWebhook]:
        """Mock webhooks"""
        mock_webhooks = [
            {
                'id': 777777777,
                'url': f'https://api.atom.com/webhooks/github/{owner}/{repo}',
                'test_url': f'https://api.github.com/repos/{owner}/{repo}/hooks/777777777/test',
                'ping_url': f'https://api.github.com/repos/{owner}/{repo}/hooks/777777777/pings',
                'name': 'web',
                'events': ['push', 'pull_request', 'issues'],
                'active': True,
                'config': {
                    'content_type': 'json',
                    'insecure_ssl': '0',
                    'url': f'https://api.atom.com/webhooks/github/{owner}/{repo}'
                },
                'created_at': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                'updated_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            }
        ]
        
        return [GitHubWebhook(webhook) for webhook in mock_webhooks]
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user (placeholder for real implementation)"""
        # In real implementation, this would fetch from database
        if self._mock_mode:
            return os.getenv('GITHUB_ACCESS_TOKEN', 'mock_github_token')
        
        # Would implement actual token retrieval from database
        return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'GitHub Service',
            'version': '1.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'Get user repositories',
                'Create repository',
                'Get user issues',
                'Create issue',
                'Get pull requests',
                'Create pull request',
                'Search repositories',
                'Get user profile',
                'Manage webhooks'
            ]
        }

# Create singleton instance
github_service = GitHubService()