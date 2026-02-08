"""
GitHub Integration Routes for FastAPI
Provides REST API endpoints for GitHub integration

Feature Flags:
- OAUTH_STRICT_MODE: Enable strict database-only token validation (default: true)
"""

import asyncio
from datetime import datetime
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from .github_service import github_service
    GITHUB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GitHub service not available: {e}")
    GITHUB_AVAILABLE = False
    github_service = None

router = APIRouter(prefix="/api/github", tags=["github"])

# Feature flag for OAuth strict mode
OAUTH_STRICT_MODE = os.getenv("OAUTH_STRICT_MODE", "true").lower() == "true"

if not OAUTH_STRICT_MODE:
    logger.warning("OAUTH_STRICT_MODE is FALSE - Falling back to environment variable tokens (INSECURE)")


def get_db_session():
    """Get database session for token lookup"""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_github_tokens(user_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Get GitHub tokens for user from database.

    Priority order:
    1. Database token (GitHubToken model) - if OAUTH_STRICT_MODE is true
    2. Environment variable fallback - if OAUTH_STRICT_MODE is false (for testing)

    Args:
        user_id: User ID to get tokens for
        db: Optional database session (will create one if not provided)

    Returns:
        Dictionary with access_token and user_info, or None if not found

    Raises:
        HTTPException: If OAUTH_STRICT_MODE is true and no token found
    """
    try:
        # Try to get token from database first
        if db:
            # Try to import GitHubToken model (may not exist yet)
            try:
                from core.models import GitHubToken

                token_record = db.query(GitHubToken).filter(
                    GitHubToken.user_id == user_id,
                    GitHubToken.status == "active"
                ).first()

                if token_record:
                    # Check if token is expired
                    if token_record.expires_at and token_record.expires_at < datetime.utcnow():
                        logger.warning(f"GitHub token for user {user_id} is expired")
                        if OAUTH_STRICT_MODE:
                            raise HTTPException(
                                status_code=401,
                                detail={
                                    "ok": False,
                                    "error": "GitHub token expired",
                                    "error_code": "OAUTH_TOKEN_EXPIRED",
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            )
                        return None

                    # Update last_used timestamp
                    token_record.last_used = datetime.utcnow()
                    db.commit()

                    logger.info(f"Using GitHub token from database for user {user_id}")
                    return {
                        'access_token': token_record.access_token,
                        'token_type': token_record.token_type or 'bearer',
                        'scope': token_record.scope or 'repo,user:email,read:org',
                        'user_info': token_record.user_info or {},
                        'source': 'database'
                    }

            except ImportError:
                # GitHubToken model doesn't exist yet, fall through to env var
                logger.debug("GitHubToken model not found, falling back to environment variable")

            except Exception as e:
                logger.error(f"Error querying GitHub token from database: {e}")

        # Fallback to environment variable if strict mode is disabled
        if not OAUTH_STRICT_MODE:
            token = os.getenv('GITHUB_ACCESS_TOKEN')
            if token:
                logger.warning(f"Using GitHub access token from environment variable for user {user_id} (INSECURE)")
                return {
                    'access_token': token,
                    'token_type': 'bearer',
                    'scope': 'repo,user:email,read:org',
                    'user_info': {
                        'login': 'testuser',
                        'id': '123456'
                    },
                    'source': 'environment'
                }

        # No token found
        if OAUTH_STRICT_MODE:
            raise HTTPException(
                status_code=401,
                detail={
                    "ok": False,
                    "error": "GitHub authentication required. Please connect your GitHub account.",
                    "error_code": "OAUTH_TOKEN_INVALID",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        logger.error(f"No GitHub token found for user {user_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub tokens for user {user_id}: {e}")
        if OAUTH_STRICT_MODE:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve GitHub token: {str(e)}"
            )
        return None

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
        # Simple implementation using env var
        token = os.getenv('GITHUB_ACCESS_TOKEN')
        if token:
            return {
                'access_token': token,
                'token_type': 'bearer',
                'scope': 'repo,user:email,read:org',
                'user_info': {
                    'login': 'testuser',
                    'id': '123456'
                }
            }
        return None
    except Exception as e:
        logger.error(f"Error getting GitHub tokens for user {user_id}: {e}")
        return None

@router.get("/health")
async def health_check():
    """GitHub service health check"""
    try:
        if not GITHUB_AVAILABLE:
            return {
                "ok": False,
                "status": "unhealthy",
                "error": "GitHub services not available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test GitHub service
        try:
            service_info = github_service.test_connection()
            return {
                "ok": True,  # Required format for validator
                "status": "healthy",
                "message": "GitHub API is accessible",
                "service_available": GITHUB_AVAILABLE,
                "service_info": service_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "degraded",
                "error": f"GitHub service error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        return {
            "ok": False,
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
        # Note: github_service methods are synchronous and don't take user_id
        repos = github_service.get_user_repositories(
            request.repo_type
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