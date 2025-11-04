"""
GitHub Integration Routes for FastAPI
Provides REST API endpoints for GitHub integration
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import os
import sys
from datetime import datetime

# Add Python API service path for imports
sys.path.append('/Users/rushiparikh/projects/atom/atom/backend/python-api-service')

try:
    from github_enhanced_api import github_enhanced_bp
    from github_service_real import github_service
    from auth_handler_github_complete import github_auth_manager
    from db_oauth_github_complete import get_tokens, save_tokens, delete_tokens
    GITHUB_AVAILABLE = True
except ImportError as e:
    print(f"GitHub service not available: {e}")
    GITHUB_AVAILABLE = False
    github_service = None

router = APIRouter(prefix="/api/github", tags=["github"])

# Request/Response Models
class UserRequest(BaseModel):
    user_id: str

class RepoRequest(UserRequest):
    repo_type: str = "all"
    sort: str = "updated"
    direction: str = "desc"
    limit: int = 50
    page: int = 1
    operation: str = "list"

class CreateRepoRequest(UserRequest):
    name: str
    description: Optional[str] = ""
    private: bool = False
    auto_init: bool = True

class IssueRequest(UserRequest):
    owner: Optional[str] = "developer"
    repo: Optional[str] = "atom-platform"
    state: str = "open"
    sort: str = "updated"
    direction: str = "desc"
    limit: int = 50
    page: int = 1
    operation: str = "list"

class CreateIssueRequest(UserRequest):
    owner: str = "developer"
    repo: str = "atom-platform"
    title: str
    body: Optional[str] = ""
    labels: Optional[List[str]] = []
    assignees: Optional[List[str]] = []

class PullRequestRequest(UserRequest):
    owner: str = "developer"
    repo: str = "atom-platform"
    state: str = "open"
    sort: str = "created"
    direction: str = "desc"
    limit: int = 50
    page: int = 1
    operation: str = "list"

class CreatePullRequestRequest(UserRequest):
    owner: str = "developer"
    repo: str = "atom-platform"
    title: str
    head: str
    base: str = "main"
    body: Optional[str] = ""

class SearchRequest(UserRequest):
    query: str
    search_type: str = "repositories"
    sort: str = "updated"
    order: str = "desc"
    limit: int = 50
    page: int = 1

def get_github_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub tokens for user"""
    try:
        if GITHUB_AVAILABLE:
            return asyncio.run(get_tokens(None, user_id))
        else:
            # Mock implementation for development
            return {
                'access_token': os.getenv('GITHUB_ACCESS_TOKEN', 'mock_github_token'),
                'token_type': 'bearer',
                'scope': 'repo,user:email,read:org',
                'expires_at': (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                'user_info': {
                    'login': os.getenv('GITHUB_USER_LOGIN', 'testuser'),
                    'id': os.getenv('GITHUB_USER_ID', '123456'),
                    'name': os.getenv('GITHUB_USER_NAME', 'Test User'),
                    'email': os.getenv('GITHUB_USER_EMAIL', 'test@example.com'),
                    'avatar_url': os.getenv('GITHUB_USER_AVATAR', 'https://avatars.githubusercontent.com/u/123456?v=4'),
                    'html_url': f"https://github.com/{os.getenv('GITHUB_USER_LOGIN', 'testuser')}",
                    'company': os.getenv('GITHUB_USER_COMPANY', 'Test Company'),
                    'location': os.getenv('GITHUB_USER_LOCATION', 'San Francisco, CA'),
                    'public_repos': 25,
                    'followers': 150,
                    'following': 80,
                    'created_at': (datetime.utcnow() - timedelta(days=365)).isoformat()
                }
            }
    except Exception as e:
        print(f"Error getting GitHub tokens for user {user_id}: {e}")
        return None

@router.get("/health")
async def health_check():
    """GitHub service health check"""
    try:
        if not GITHUB_AVAILABLE:
            return {
                "status": "unhealthy",
                "error": "GitHub services not available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test GitHub service
        try:
            service_info = github_service.get_service_info()
            return {
                "status": "healthy",
                "message": "GitHub API is accessible",
                "service_available": GITHUB_AVAILABLE,
                "service_info": service_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "degraded",
                "error": f"GitHub service error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/repositories")
async def list_repositories(request: RepoRequest):
    """List user GitHub repositories"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            return await create_repository(CreateRepoRequest(**request.dict()))
        
        # Get repositories using GitHub service
        repos = await github_service.get_user_repositories(
            request.user_id,
            request.repo_type,
            request.sort,
            request.direction,
            request.limit,
            request.page
        )
        
        repos_data = [{
            'repo_id': repo.id,
            'name': repo.name,
            'full_name': repo.full_name,
            'description': repo.description,
            'private': repo.private,
            'fork': repo.fork,
            'html_url': repo.html_url,
            'clone_url': repo.clone_url,
            'ssh_url': repo.ssh_url,
            'language': repo.language,
            'stargazers_count': repo.stargazers_count,
            'watchers_count': repo.watchers_count,
            'forks_count': repo.forks_count,
            'open_issues_count': repo.open_issues_count,
            'default_branch': repo.default_branch,
            'created_at': repo.created_at,
            'updated_at': repo.updated_at,
            'pushed_at': repo.pushed_at,
            'size': repo.size,
            'owner': {
                'login': repo.owner.get('login') if repo.owner else None,
                'avatar_url': repo.owner.get('avatar_url') if repo.owner else None
            },
            'topics': repo.topics,
            'license': repo.license,
            'visibility': 'private' if repo.private else 'public'
        } for repo in repos]
        
        return {
            'ok': True,
            'data': {
                'repositories': repos_data,
                'total_count': len(repos_data),
                'pagination': {
                    'page': request.page,
                    'limit': request.limit,
                    'has_more': len(repos_data) == request.limit
                }
            },
            'endpoint': 'list_repositories',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing repositories: {str(e)}")

@router.post("/repositories/create")
async def create_repository(request: CreateRepoRequest):
    """Create a new GitHub repository"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create repository using GitHub service
        result = await github_service.create_repository(
            request.user_id,
            request.name,
            request.description or '',
            request.private,
            request.auto_init
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create repository")
        
        repo_data = {
            'repo_id': result.id,
            'name': result.name,
            'full_name': result.full_name,
            'description': result.description,
            'private': result.private,
            'fork': result.fork,
            'html_url': result.html_url,
            'clone_url': result.clone_url,
            'ssh_url': result.ssh_url,
            'language': result.language,
            'stargazers_count': result.stargazers_count,
            'watchers_count': result.watchers_count,
            'forks_count': result.forks_count,
            'open_issues_count': result.open_issues_count,
            'default_branch': result.default_branch,
            'created_at': result.created_at,
            'updated_at': result.updated_at,
            'pushed_at': result.pushed_at,
            'size': result.size,
            'owner': {
                'login': result.owner.get('login') if result.owner else None,
                'avatar_url': result.owner.get('avatar_url') if result.owner else None
            },
            'topics': result.topics,
            'license': result.license,
            'visibility': 'private' if result.private else 'public'
        }
        
        return {
            'ok': True,
            'data': {
                'repository': repo_data,
                'url': result.html_url,
                'clone_url': result.clone_url,
                'ssh_url': result.ssh_url,
                'message': 'Repository created successfully'
            },
            'endpoint': 'create_repository',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating repository: {str(e)}")

@router.post("/issues")
async def list_issues(request: IssueRequest):
    """List user GitHub issues"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            return await create_issue(CreateIssueRequest(**request.dict()))
        
        # Get issues using GitHub service
        issues = await github_service.get_user_issues(
            request.user_id,
            request.state,
            request.sort,
            request.direction,
            request.limit,
            request.page
        )
        
        issues_data = [{
            'issue_id': issue.id,
            'number': issue.number,
            'title': issue.title,
            'body': issue.body,
            'state': issue.state,
            'locked': issue.locked,
            'comments': issue.comments,
            'created_at': issue.created_at,
            'updated_at': issue.updated_at,
            'closed_at': issue.closed_at,
            'user': {
                'login': issue.user.get('login') if issue.user else None,
                'avatar_url': issue.user.get('avatar_url') if issue.user else None
            },
            'assignee': {
                'login': issue.assignee.get('login') if issue.assignee else None,
                'avatar_url': issue.assignee.get('avatar_url') if issue.assignee else None
            } if issue.assignee else None,
            'assignees': [{
                'login': assignee.get('login') if assignee else None,
                'avatar_url': assignee.get('avatar_url') if assignee else None
            } for assignee in (issue.assignees or [])],
            'labels': issue.labels,
            'milestone': issue.milestone,
            'html_url': issue.html_url,
            'reactions': issue.reactions,
            'repository_url': issue.repository_url
        } for issue in issues]
        
        return {
            'ok': True,
            'data': {
                'issues': issues_data,
                'total_count': len(issues_data),
                'pagination': {
                    'page': request.page,
                    'limit': request.limit,
                    'has_more': len(issues_data) == request.limit
                }
            },
            'endpoint': 'list_issues',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing issues: {str(e)}")

@router.post("/issues/create")
async def create_issue(request: CreateIssueRequest):
    """Create a new GitHub issue"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create issue using GitHub service
        result = await github_service.create_issue(
            request.user_id,
            request.owner,
            request.repo,
            request.title,
            request.body or '',
            request.labels or [],
            request.assignees or []
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create issue")
        
        issue_data = {
            'issue_id': result.id,
            'number': result.number,
            'title': result.title,
            'body': result.body,
            'state': result.state,
            'locked': result.locked,
            'comments': result.comments,
            'created_at': result.created_at,
            'updated_at': result.updated_at,
            'closed_at': result.closed_at,
            'user': result.user,
            'assignee': result.assignee,
            'assignees': result.assignees,
            'labels': result.labels,
            'milestone': result.milestone,
            'html_url': result.html_url,
            'reactions': result.reactions,
            'repository_url': result.repository_url
        }
        
        return {
            'ok': True,
            'data': {
                'issue': issue_data,
                'url': result.html_url,
                'message': 'Issue created successfully'
            },
            'endpoint': 'create_issue',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating issue: {str(e)}")

@router.post("/pulls")
async def list_pull_requests(request: PullRequestRequest):
    """List pull requests for a repository"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            return await create_pull_request(CreatePullRequestRequest(**request.dict()))
        
        # Get pull requests using GitHub service
        prs = await github_service.get_pull_requests(
            request.user_id,
            request.owner,
            request.repo,
            request.state,
            request.sort,
            request.direction,
            request.limit,
            request.page
        )
        
        prs_data = [{
            'pr_id': pr.id,
            'number': pr.number,
            'title': pr.title,
            'body': pr.body,
            'state': pr.state,
            'locked': pr.locked,
            'created_at': pr.created_at,
            'updated_at': pr.updated_at,
            'closed_at': pr.closed_at,
            'merged_at': pr.merged_at,
            'merge_commit_sha': pr.merge_commit_sha,
            'head': pr.head,
            'base': pr.base,
            'user': pr.user,
            'assignees': pr.assignees,
            'requested_reviewers': pr.requested_reviewers,
            'labels': pr.labels,
            'milestone': pr.milestone,
            'commits': pr.commits,
            'additions': pr.additions,
            'deletions': pr.deletions,
            'changed_files': pr.changed_files,
            'html_url': pr.html_url,
            'diff_url': pr.diff_url,
            'patch_url': pr.patch_url
        } for pr in prs]
        
        return {
            'ok': True,
            'data': {
                'pull_requests': prs_data,
                'total_count': len(prs_data),
                'repository': f'{request.owner}/{request.repo}',
                'pagination': {
                    'page': request.page,
                    'limit': request.limit,
                    'has_more': len(prs_data) == request.limit
                }
            },
            'endpoint': 'list_pull_requests',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing pull requests: {str(e)}")

@router.post("/pulls/create")
async def create_pull_request(request: CreatePullRequestRequest):
    """Create a new pull request"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create pull request using GitHub service
        result = await github_service.create_pull_request(
            request.user_id,
            request.owner,
            request.repo,
            request.title,
            request.head,
            request.base,
            request.body or ''
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create pull request")
        
        pr_data = {
            'pr_id': result.id,
            'number': result.number,
            'title': result.title,
            'body': result.body,
            'state': result.state,
            'locked': result.locked,
            'created_at': result.created_at,
            'updated_at': result.updated_at,
            'closed_at': result.closed_at,
            'merged_at': result.merged_at,
            'merge_commit_sha': result.merge_commit_sha,
            'head': result.head,
            'base': result.base,
            'user': result.user,
            'assignees': result.assignees,
            'requested_reviewers': result.requested_reviewers,
            'labels': result.labels,
            'milestone': result.milestone,
            'commits': result.commits,
            'additions': result.additions,
            'deletions': result.deletions,
            'changed_files': result.changed_files,
            'html_url': result.html_url,
            'diff_url': result.diff_url,
            'patch_url': result.patch_url
        }
        
        return {
            'ok': True,
            'data': {
                'pull_request': pr_data,
                'url': result.html_url,
                'diff_url': result.diff_url,
                'message': 'Pull request created successfully'
            },
            'endpoint': 'create_pull_request',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating pull request: {str(e)}")

@router.post("/search")
async def search_github(request: SearchRequest):
    """Search GitHub repositories"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Search repositories using GitHub service
        result = await github_service.search_repositories(
            request.user_id,
            request.query,
            request.sort,
            request.order,
            request.limit,
            request.page
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching GitHub: {str(e)}")

@router.post("/user/profile")
async def get_user_profile(request: UserRequest):
    """Get authenticated user profile"""
    try:
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        return {
            'ok': True,
            'data': {
                'user': tokens['user_info']
            },
            'endpoint': 'get_user_profile',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user profile: {str(e)}")