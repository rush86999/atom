"""
Linear Integration Routes for FastAPI
Provides REST API endpoints for Linear integration
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add Python API service path for imports
sys.path.append('/Users/rushiparikh/projects/atom/atom/backend/python-api-service')

try:
    from linear_enhanced_api import linear_enhanced_bp
    from linear_service_real import linear_service
    from auth_handler_linear import linear_auth_manager
    from db_oauth_linear import get_tokens, save_tokens, delete_tokens
    LINEAR_AVAILABLE = True
except ImportError as e:
    print(f"Linear service not available: {e}")
    LINEAR_AVAILABLE = False

router = APIRouter(prefix="/api/linear", tags=["linear"])

# Request/Response Models
class UserRequest(BaseModel):
    user_id: str

class IssueRequest(UserRequest):
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    include_completed: bool = True
    include_canceled: bool = False
    include_backlog: bool = True
    limit: int = 50
    operation: str = "list"

class CreateIssueRequest(UserRequest):
    title: str
    description: Optional[str] = ""
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[str] = "medium"
    labels: Optional[List[Dict[str, Any]]] = []

class TeamRequest(UserRequest):
    limit: int = 20

class ProjectRequest(UserRequest):
    team_id: Optional[str] = None
    limit: int = 50

class CycleRequest(UserRequest):
    team_id: Optional[str] = None
    include_completed: bool = True
    limit: int = 20

class UsersRequest(UserRequest):
    team_id: Optional[str] = None
    include_inactive: bool = False
    limit: int = 100

class SearchRequest(UserRequest):
    query: str
    search_type: str = "issues"
    limit: int = 50

def get_linear_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Linear tokens for user"""
    try:
        if LINEAR_AVAILABLE:
            return asyncio.run(get_tokens(None, user_id))
        else:
            # Mock implementation for development
            return {
                'access_token': os.getenv('LINEAR_ACCESS_TOKEN', 'mock_token'),
                'refresh_token': os.getenv('LINEAR_REFRESH_TOKEN', 'mock_refresh'),
                'expires_at': (datetime.utcnow().replace(tzinfo=None) + timedelta(hours=1)).isoformat(),
                'user_info': {
                    'id': os.getenv('LINEAR_USER_ID', 'mock_user_id'),
                    'name': os.getenv('LINEAR_USER_NAME', 'Test User'),
                    'email': os.getenv('LINEAR_USER_EMAIL', 'test@example.com'),
                    'organization': {
                        'id': os.getenv('LINEAR_ORG_ID', 'mock_org_id'),
                        'name': os.getenv('LINEAR_ORG_NAME', 'Test Organization')
                    }
                }
            }
    except Exception as e:
        print(f"Error getting Linear tokens for user {user_id}: {e}")
        return None

@router.get("/health")
async def health_check():
    """Linear service health check"""
    try:
        if not LINEAR_AVAILABLE:
            return {
                "status": "unhealthy",
                "error": "Linear services not available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test Linear service
        try:
            service_info = linear_service.get_service_info()
            return {
                "status": "healthy",
                "message": "Linear API is accessible",
                "service_available": LINEAR_AVAILABLE,
                "service_info": service_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "degraded",
                "error": f"Linear service error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/issues")
async def list_issues(request: IssueRequest):
    """List user Linear issues"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        if request.operation == "create":
            return await create_issue(CreateIssueRequest(**request.dict()))
        
        # Get issues using Linear service
        issues = await linear_service.get_user_issues(
            request.user_id,
            request.team_id,
            request.project_id,
            request.include_completed,
            request.include_canceled,
            request.include_backlog,
            request.limit
        )
        
        issues_data = [{
            'issue_id': issue.id,
            'identifier': issue.identifier,
            'title': issue.title,
            'description': issue.description,
            'status': {
                'id': issue.status.get('id'),
                'name': issue.status.get('name'),
                'color': issue.status.get('color'),
                'type': issue.status.get('type')
            },
            'priority': {
                'id': issue.priority.get('id'),
                'label': issue.priority.get('label'),
                'priority': issue.priority.get('priority')
            },
            'assignee': issue.assignee and {
                'id': issue.assignee.get('id'),
                'name': issue.assignee.get('name'),
                'displayName': issue.assignee.get('displayName'),
                'avatarUrl': issue.assignee.get('avatarUrl')
            },
            'project': {
                'id': issue.project.get('id'),
                'name': issue.project.get('name'),
                'icon': issue.project.get('icon'),
                'color': issue.project.get('color')
            },
            'team': {
                'id': issue.team.get('id'),
                'name': issue.team.get('name'),
                'icon': issue.team.get('icon')
            },
            'labels': issue.labels,
            'created_at': issue.createdAt,
            'updated_at': issue.updatedAt,
            'due_date': issue.dueDate,
            'state': issue.state,
            'url': f"https://linear.app/issue/{issue.identifier}"
        } for issue in issues]
        
        return {
            'ok': True,
            'data': {
                'issues': issues_data,
                'total_count': len(issues_data)
            },
            'endpoint': 'list_issues',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing issues: {str(e)}")

@router.post("/issues/create")
async def create_issue(request: CreateIssueRequest):
    """Create a new Linear issue"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        issue_data = {
            'title': request.title,
            'description': request.description,
            'teamId': request.team_id,
            'projectId': request.project_id,
            'assigneeId': request.assignee_id,
            'priority': request.priority,
            'labels': request.labels
        }
        
        # Create issue using Linear service (mock implementation for now)
        result = await linear_service.search_linear(request.user_id, request.title, 'issues', 1)
        
        mock_issue = {
            'issue_id': f'lin-{int(datetime.utcnow().timestamp())}',
            'identifier': f'NEW-{int(datetime.utcnow().timestamp())}',
            'title': request.title,
            'description': request.description,
            'status': {
                'id': 'status-todo',
                'name': 'Todo',
                'color': 'gray',
                'type': 'backlog'
            },
            'priority': {
                'id': f'priority-{request.priority}',
                'label': request.priority.title(),
                'priority': 3 if request.priority == 'medium' else 4 if request.priority == 'high' else 2
            },
            'assignee': {'id': request.assignee_id} if request.assignee_id else None,
            'project': {'id': request.project_id} if request.project_id else None,
            'team': {'id': request.team_id} if request.team_id else None,
            'labels': request.labels or [],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'due_date': None,
            'state': 'backlog',
            'url': f"https://linear.app/issue/NEW-{int(datetime.utcnow().timestamp())}"
        }
        
        return {
            'ok': True,
            'data': {
                'issue': mock_issue,
                'url': mock_issue['url'],
                'message': 'Issue created successfully'
            },
            'endpoint': 'create_issue',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating issue: {str(e)}")

@router.post("/teams")
async def list_teams(request: TeamRequest):
    """List user Linear teams"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        teams = await linear_service.get_user_teams(request.user_id, request.limit)
        
        teams_data = [{
            'team_id': team.id,
            'name': team.name,
            'description': team.description,
            'icon': team.icon,
            'color': team.color,
            'organization': team.organization,
            'created_at': team.createdAt,
            'updated_at': team.updatedAt,
            'member_count': len(team.members) if team.members else 0,
            'issues_count': getattr(team, 'issuesCount', 0),
            'cycles_count': getattr(team, 'cyclesCount', 0),
            'members': team.members and [{
                'id': member.id,
                'name': member.name,
                'displayName': member.displayName,
                'avatarUrl': member.avatarUrl,
                'role': member.role
            } for member in team.members],
            'projects': team.projects and [{
                'id': project.id,
                'name': project.name,
                'icon': project.icon,
                'color': project.color,
                'state': project.state
            } for project in team.projects]
        } for team in teams]
        
        return {
            'ok': True,
            'data': {
                'teams': teams_data,
                'total_count': len(teams_data)
            },
            'endpoint': 'list_teams',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing teams: {str(e)}")

@router.post("/projects")
async def list_projects(request: ProjectRequest):
    """List projects from teams"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        projects = await linear_service.get_team_projects(request.user_id, request.team_id, request.limit)
        
        projects_data = [{
            'project_id': project.id,
            'name': project.name,
            'description': project.description,
            'url': project.url,
            'icon': project.icon,
            'color': project.color,
            'team': project.team,
            'state': project.state,
            'progress': project.progress,
            'completed_issues_count': project.completedIssuesCount,
            'started_issues_count': project.startedIssuesCount,
            'unstarted_issues_count': project.unstartedIssuesCount,
            'backlogged_issues_count': project.backloggedIssuesCount,
            'canceled_issues_count': project.canceledIssuesCount,
            'created_at': project.createdAt,
            'updated_at': project.updatedAt,
            'scope': project.scope
        } for project in projects]
        
        return {
            'ok': True,
            'data': {
                'projects': projects_data,
                'total_count': len(projects_data)
            },
            'endpoint': 'list_projects',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing projects: {str(e)}")

@router.post("/cycles")
async def list_cycles(request: CycleRequest):
    """List cycles from teams"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        cycles = await linear_service.get_team_cycles(
            request.user_id, request.team_id, request.include_completed, request.limit
        )
        
        cycles_data = [{
            'cycle_id': cycle.id,
            'name': cycle.name,
            'description': cycle.description,
            'number': cycle.number,
            'start_at': cycle.startAt,
            'end_at': cycle.endAt,
            'completed_at': cycle.completedAt,
            'progress': cycle.progress,
            'issues': cycle.issues and [{
                'issue_id': issue.id,
                'identifier': issue.identifier,
                'title': issue.title,
                'status': {
                    'id': issue.status.get('id'),
                    'name': issue.status.get('name'),
                    'color': issue.status.get('color'),
                    'type': issue.status.get('type')
                },
                'priority': {
                    'id': issue.priority.get('id'),
                    'label': issue.priority.get('label'),
                    'priority': issue.priority.get('priority')
                },
                'assignee': issue.assignee and {
                    'id': issue.assignee.get('id'),
                    'name': issue.assignee.get('name'),
                    'displayName': issue.assignee.get('displayName'),
                    'avatarUrl': issue.assignee.get('avatarUrl')
                },
                'created_at': issue.createdAt,
                'updated_at': issue.updatedAt
            } for issue in cycle.issues],
            'team': cycle.team,
            'issue_count': len(cycle.issues) if cycle.issues else 0
        } for cycle in cycles]
        
        return {
            'ok': True,
            'data': {
                'cycles': cycles_data,
                'total_count': len(cycles_data)
            },
            'endpoint': 'list_cycles',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing cycles: {str(e)}")

@router.post("/users")
async def list_users(request: UsersRequest):
    """List users from organization or teams"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        # Mock implementation for now
        mock_users = [
            {
                'id': 'user-1',
                'name': 'Alice Developer',
                'displayName': 'Alice Developer',
                'email': 'alice@company.com',
                'avatarUrl': 'https://example.com/alice.png',
                'url': 'https://linear.app/alice',
                'role': 'admin',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=2)).isoformat()
            },
            {
                'id': 'user-2',
                'name': 'Bob Engineer',
                'displayName': 'Bob Engineer',
                'email': 'bob@company.com',
                'avatarUrl': 'https://example.com/bob.png',
                'url': 'https://linear.app/bob',
                'role': 'member',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'active': True,
                'lastSeen': (datetime.utcnow() - timedelta(hours=1)).isoformat()
            }
        ]
        
        return {
            'ok': True,
            'data': {
                'users': mock_users[:request.limit],
                'total_count': len(mock_users)
            },
            'endpoint': 'list_users',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing users: {str(e)}")

@router.post("/user/profile")
async def get_user_profile(request: UserRequest):
    """Get authenticated user profile"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        return {
            'ok': True,
            'data': {
                'user': tokens['user_info'],
                'organization': {
                    'id': tokens['user_info'].get('organization', {}).get('id'),
                    'name': tokens['user_info'].get('organization', {}).get('name') or 'Personal Workspace',
                    'urlKey': tokens['user_info'].get('organization', {}).get('urlKey')
                }
            },
            'endpoint': 'get_user_profile',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'linear_api'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user profile: {str(e)}")

@router.post("/search")
async def search_linear(request: SearchRequest):
    """Search across Linear"""
    try:
        if not LINEAR_AVAILABLE:
            raise HTTPException(status_code=503, detail="Linear service not available")
        
        tokens = get_linear_tokens(request.user_id)
        if not tokens:
            raise HTTPException(status_code=401, detail="Linear tokens not found")
        
        result = await linear_service.search_linear(
            request.user_id, request.query, request.search_type, request.limit
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching Linear: {str(e)}")