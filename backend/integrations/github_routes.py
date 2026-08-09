"""
GitHub Integration Routes for FastAPI
Provides REST API endpoints for GitHub integration

Feature Flags:
- OAUTH_STRICT_MODE: Enable strict database-only token validation (default: true)
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from .github_service import GitHubService

    GITHUB_AVAILABLE = True
    github_service = GitHubService()
except ImportError as e:
    logger.warning(f"GitHub service not available: {e}")
    GITHUB_AVAILABLE = False
    github_service = None

# GitHub endpoints act on behalf of a user's stored OAuth token. They MUST be
# authenticated, and the effective user_id must come from the authenticated
# session — NOT the request body (otherwise any caller could pass another
# user's id and act under their GitHub identity: an IDOR). Router-level auth
# closes the unauthenticated-access hole; per-handler overrides pin user_id to
# the authenticated user (see e.g. list_repositories).
from core.auth import get_current_user, User
router = APIRouter(prefix="/api/github", tags=["github"], dependencies=[Depends(get_current_user)])

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
    1. Database token (IntegrationToken, provider="github") - if OAUTH_STRICT_MODE is true
    2. Environment variable fallback - if OAUTH_STRICT_MODE is false (for testing)

    Args:
        user_id: User ID to get tokens for
        db: Optional database session (will create one if not provided)

    Returns:
        Dictionary with access_token and user_info, or None if not found

    Raises:
        HTTPException: If OAUTH_STRICT_MODE is true and no token found
    """
    owns_db = False
    try:
        if db is None:
            db_gen = get_db_session()
            db = next(db_gen)
            owns_db = True
        try:
            from core.models import IntegrationToken
            from core.privsec.token_encryption import decrypt_token

            token_record = db.query(IntegrationToken).filter(
                IntegrationToken.user_id == user_id,
                IntegrationToken.provider == "github",
                IntegrationToken.status == "active"
            ).first()

            if token_record:
                if token_record.expires_at and token_record.expires_at < datetime.now(timezone.utc):
                    logger.warning(f"GitHub token for user {user_id} is expired")
                    if OAUTH_STRICT_MODE:
                        raise HTTPException(
                            status_code=401,
                            detail={
                                "ok": False,
                                "error": "GitHub token expired",
                                "error_code": "OAUTH_TOKEN_EXPIRED",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        )
                    return None

                logger.info(f"Using GitHub token from database for user {user_id}")
                return {
                    'access_token': decrypt_token(token_record.access_token, allow_plaintext=True),
                    'token_type': token_record.token_type or 'bearer',
                    'scope': token_record.scope or 'repo,user:email,read:org',
                    'user_info': getattr(token_record, 'user_info', None) or {},
                    'source': 'database'
                }

        except HTTPException:
            raise
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
                    "timestamp": datetime.now(timezone.utc).isoformat()
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
                detail="Failed to retrieve GitHub token"
            )
        return None
    finally:
        if owns_db:
            db.close()

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
    name: Optional[str] = None
    description: Optional[str] = ""
    private: bool = False
    auto_init: bool = True

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
    title: Optional[str] = None
    body: Optional[str] = ""
    labels: Optional[List[str]] = []
    assignees: Optional[List[str]] = []

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
    title: Optional[str] = None
    head: Optional[str] = None
    base: str = "main"
    body: Optional[str] = ""

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


@router.get("/health")
async def health_check():
    """GitHub service health check"""
    try:
        if not GITHUB_AVAILABLE:
            return {
                "ok": False,
                "status": "unhealthy",
                "error": "GitHub services not available",
                "timestamp": datetime.now(timezone.utc).isoformat()
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
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "degraded",
                "error": "GitHub service error",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    except Exception as e:
        return {
            "ok": False,
            "status": "unhealthy",
            "error": "GitHub health check failed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.post("/repositories")
async def list_repositories(request: RepoRequest, current_user: User = Depends(get_current_user)):
    """List user GitHub repositories"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            if not request.name:
                raise HTTPException(status_code=422, detail="name is required for repository creation")
            return await create_repository(CreateRepoRequest(**request.dict()), current_user)
        
        # Get repositories using GitHub service
        # Note: github_service methods are synchronous and don't take user_id
        repos = github_service.get_user_repositories(
            request.repo_type
        )
        
        repos_data = [{
            'repo_id': repo.get('id'),
            'name': repo.get('name'),
            'full_name': repo.get('full_name'),
            'description': repo.get('description'),
            'private': repo.get('private'),
            'fork': repo.get('fork'),
            'html_url': repo.get('html_url'),
            'clone_url': repo.get('clone_url'),
            'ssh_url': repo.get('ssh_url'),
            'language': repo.get('language'),
            'stargazers_count': repo.get('stargazers_count'),
            'watchers_count': repo.get('watchers_count'),
            'forks_count': repo.get('forks_count'),
            'open_issues_count': repo.get('open_issues_count'),
            'default_branch': repo.get('default_branch'),
            'created_at': repo.get('created_at'),
            'updated_at': repo.get('updated_at'),
            'pushed_at': repo.get('pushed_at'),
            'size': repo.get('size'),
            'owner': {
                'login': (repo.get('owner') or {}).get('login'),
                'avatar_url': (repo.get('owner') or {}).get('avatar_url')
            },
            'topics': repo.get('topics'),
            'license': repo.get('license'),
            'visibility': 'private' if repo.get('private') else 'public'
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error listing repositories")

def _create_github_repository(
    name: str, description: str, private: bool, auto_init: bool
) -> Dict[str, Any]:
    """Create a GitHub repository via the service's authenticated session."""
    response = github_service.session.post(
        f"{github_service.base_url}/user/repos",
        json={
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        },
    )
    response.raise_for_status()
    return response.json()


@router.post("/repositories/create")
async def create_repository(request: CreateRepoRequest, current_user: User = Depends(get_current_user)):
    """Create a new GitHub repository"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create repository using GitHub service
        result = _create_github_repository(
            request.name,
            request.description or '',
            request.private,
            request.auto_init
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create repository")
        
        repo_data = {
            'repo_id': result.get('id'),
            'name': result.get('name'),
            'full_name': result.get('full_name'),
            'description': result.get('description'),
            'private': result.get('private'),
            'fork': result.get('fork'),
            'html_url': result.get('html_url'),
            'clone_url': result.get('clone_url'),
            'ssh_url': result.get('ssh_url'),
            'language': result.get('language'),
            'stargazers_count': result.get('stargazers_count'),
            'watchers_count': result.get('watchers_count'),
            'forks_count': result.get('forks_count'),
            'open_issues_count': result.get('open_issues_count'),
            'default_branch': result.get('default_branch'),
            'created_at': result.get('created_at'),
            'updated_at': result.get('updated_at'),
            'pushed_at': result.get('pushed_at'),
            'size': result.get('size'),
            'owner': {
                'login': (result.get('owner') or {}).get('login'),
                'avatar_url': (result.get('owner') or {}).get('avatar_url')
            },
            'topics': result.get('topics'),
            'license': result.get('license'),
            'visibility': 'private' if result.get('private') else 'public'
        }
        
        return {
            'ok': True,
            'data': {
                'repository': repo_data,
                'url': result.get('html_url'),
                'clone_url': result.get('clone_url'),
                'ssh_url': result.get('ssh_url'),
                'message': 'Repository created successfully'
            },
            'endpoint': 'create_repository',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error creating repository")

@router.post("/issues")
async def list_issues(request: IssueRequest, current_user: User = Depends(get_current_user)):
    """List user GitHub issues"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            if not request.title:
                raise HTTPException(status_code=422, detail="title is required for issue creation")
            return await create_issue(CreateIssueRequest(**request.dict()), current_user)
        
        # Get issues using GitHub service
        issues = github_service.get_repository_issues(
            request.owner,
            request.repo,
            request.state
        )
        
        issues_data = [{
            'issue_id': issue.get('id'),
            'number': issue.get('number'),
            'title': issue.get('title'),
            'body': issue.get('body'),
            'state': issue.get('state'),
            'locked': issue.get('locked'),
            'comments': issue.get('comments'),
            'created_at': issue.get('created_at'),
            'updated_at': issue.get('updated_at'),
            'closed_at': issue.get('closed_at'),
            'user': {
                'login': (issue.get('user') or {}).get('login'),
                'avatar_url': (issue.get('user') or {}).get('avatar_url')
            },
            'assignee': {
                'login': (issue.get('assignee') or {}).get('login'),
                'avatar_url': (issue.get('assignee') or {}).get('avatar_url')
            } if issue.get('assignee') else None,
            'assignees': [{
                'login': (assignee or {}).get('login'),
                'avatar_url': (assignee or {}).get('avatar_url')
            } for assignee in (issue.get('assignees') or [])],
            'labels': issue.get('labels'),
            'milestone': issue.get('milestone'),
            'html_url': issue.get('html_url'),
            'reactions': issue.get('reactions'),
            'repository_url': issue.get('repository_url')
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error listing issues")

@router.post("/issues/create")
async def create_issue(request: CreateIssueRequest, current_user: User = Depends(get_current_user)):
    """Create a new GitHub issue"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create issue using GitHub service
        result = github_service.create_issue(
            request.owner,
            request.repo,
            request.title,
            request.body or '',
            request.labels or []
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create issue")
        
        issue_data = {
            'issue_id': result.get('id'),
            'number': result.get('number'),
            'title': result.get('title'),
            'body': result.get('body'),
            'state': result.get('state'),
            'locked': result.get('locked'),
            'comments': result.get('comments'),
            'created_at': result.get('created_at'),
            'updated_at': result.get('updated_at'),
            'closed_at': result.get('closed_at'),
            'user': result.get('user'),
            'assignee': result.get('assignee'),
            'assignees': result.get('assignees'),
            'labels': result.get('labels'),
            'milestone': result.get('milestone'),
            'html_url': result.get('html_url'),
            'reactions': result.get('reactions'),
            'repository_url': result.get('repository_url')
        }
        
        return {
            'ok': True,
            'data': {
                'issue': issue_data,
                'url': result.get('html_url'),
                'message': 'Issue created successfully'
            },
            'endpoint': 'create_issue',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error creating issue")

@router.post("/pulls")
async def list_pull_requests(request: PullRequestRequest, current_user: User = Depends(get_current_user)):
    """List pull requests for a repository"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        if request.operation == "create":
            if not request.title or not request.head:
                raise HTTPException(status_code=422, detail="title and head are required for pull request creation")
            return await create_pull_request(CreatePullRequestRequest(**request.dict()), current_user)
        
        # Get pull requests using GitHub service
        prs = github_service.get_repository_pulls(
            request.owner,
            request.repo,
            request.state
        )
        
        prs_data = [{
            'pr_id': pr.get('id'),
            'number': pr.get('number'),
            'title': pr.get('title'),
            'body': pr.get('body'),
            'state': pr.get('state'),
            'locked': pr.get('locked'),
            'created_at': pr.get('created_at'),
            'updated_at': pr.get('updated_at'),
            'closed_at': pr.get('closed_at'),
            'merged_at': pr.get('merged_at'),
            'merge_commit_sha': pr.get('merge_commit_sha'),
            'head': pr.get('head'),
            'base': pr.get('base'),
            'user': pr.get('user'),
            'assignees': pr.get('assignees'),
            'requested_reviewers': pr.get('requested_reviewers'),
            'labels': pr.get('labels'),
            'milestone': pr.get('milestone'),
            'commits': pr.get('commits'),
            'additions': pr.get('additions'),
            'deletions': pr.get('deletions'),
            'changed_files': pr.get('changed_files'),
            'html_url': pr.get('html_url'),
            'diff_url': pr.get('diff_url'),
            'patch_url': pr.get('patch_url')
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error listing pull requests")

@router.post("/pulls/create")
async def create_pull_request(request: CreatePullRequestRequest, current_user: User = Depends(get_current_user)):
    """Create a new pull request"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Create pull request using GitHub service
        result = github_service.create_pull_request(
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
            'pr_id': result.get('id'),
            'number': result.get('number'),
            'title': result.get('title'),
            'body': result.get('body'),
            'state': result.get('state'),
            'locked': result.get('locked'),
            'created_at': result.get('created_at'),
            'updated_at': result.get('updated_at'),
            'closed_at': result.get('closed_at'),
            'merged_at': result.get('merged_at'),
            'merge_commit_sha': result.get('merge_commit_sha'),
            'head': result.get('head'),
            'base': result.get('base'),
            'user': result.get('user'),
            'assignees': result.get('assignees'),
            'requested_reviewers': result.get('requested_reviewers'),
            'labels': result.get('labels'),
            'milestone': result.get('milestone'),
            'commits': result.get('commits'),
            'additions': result.get('additions'),
            'deletions': result.get('deletions'),
            'changed_files': result.get('changed_files'),
            'html_url': result.get('html_url'),
            'diff_url': result.get('diff_url'),
            'patch_url': result.get('patch_url')
        }
        
        return {
            'ok': True,
            'data': {
                'pull_request': pr_data,
                'url': result.get('html_url'),
                'diff_url': result.get('diff_url'),
                'message': 'Pull request created successfully'
            },
            'endpoint': 'create_pull_request',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error creating pull request")

@router.post("/search")
async def search_github(request: SearchRequest, current_user: User = Depends(get_current_user)):
    """Search GitHub repositories"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
        if not GITHUB_AVAILABLE:
            raise HTTPException(status_code=503, detail="GitHub service not available")
        
        tokens = get_github_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="GitHub tokens not found")
        
        # Search repositories using GitHub service
        result = github_service.search_repositories(
            request.query,
            request.sort,
            request.order
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error searching GitHub")

@router.post("/user/profile")
async def get_user_profile(request: UserRequest, current_user: User = Depends(get_current_user)):
    """Get authenticated user profile"""
    try:
        request.user_id = current_user.id  # IDOR: pin to authenticated user
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'github_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error getting user profile")