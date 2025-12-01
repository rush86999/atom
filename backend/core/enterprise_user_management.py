"""
Enterprise User Management - Database-backed Implementation
Multi-tenant user management with team collaboration, permissions, and workspace isolation
Migrated from in-memory to SQLAlchemy persistence
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import logging

from core.database import get_db
from core.models import User, Team, Workspace, UserRole, UserStatus, WorkspaceStatus
from core.auth import get_password_hash

router = APIRouter()
logger = logging.getLogger(__name__)

# ==================== Pydantic Models ====================

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    plan_tier: str = "standard"

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    plan_tier: Optional[str] = None

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    workspace_id: str

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str = UserRole.MEMBER.value
    workspace_id: Optional[str] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


# ==================== Workspace Endpoints ====================

@router.post("/api/enterprise/workspaces", status_code=201)
async def create_workspace(
    data: WorkspaceCreate,
    db: Session = Depends(get_db)
):
    """Create a new workspace"""
    workspace = Workspace(
        name=data.name,
        description=data.description,
        plan_tier=data.plan_tier,
        status=WorkspaceStatus.ACTIVE.value
    )
    
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    logger.info(f"Created workspace: {workspace.id}")
    return {"workspace_id": workspace.id}


@router.get("/api/enterprise/workspaces")
async def list_workspaces(
    db: Session = Depends(get_db)
):
    """List all workspaces"""
    workspaces = db.query(Workspace).all()
    
    return [{
        "workspace_id": w.id,
        "name": w.name,
        "description": w.description,
        "status": w.status,
        "plan_tier": w.plan_tier,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
        "user_count": len(w.users),
        "team_count": len(w.teams)
    } for w in workspaces]


@router.get("/api/enterprise/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get workspace details"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    return {
        "workspace_id": workspace.id,
        "name": workspace.name,
        "description":workspace.description,
        "status": workspace.status,
        "plan_tier": workspace.plan_tier,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
        "user_count": len(workspace.users),
        "team_count": len(workspace.teams)
    }


@router.patch("/api/enterprise/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    db: Session = Depends(get_db)
):
    """Update workspace"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    if data.name is not None:
        workspace.name = data.name
    if data.description is not None:
        workspace.description = data.description
    if data.status is not None:
        workspace.status = data.status
    if data.plan_tier is not None:
        workspace.plan_tier = data.plan_tier
    
    db.commit()
    db.refresh(workspace)
    
    logger.info(f"Updated workspace: {workspace_id}")
    return {"message": "Workspace updated successfully"}


@router.delete("/api/enterprise/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Delete workspace (soft delete)"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Soft delete
    workspace.status = "deleted"
    db.commit()
    
    logger.info(f"Deleted workspace: {workspace_id}")
    return {"message": "Workspace deleted successfully"}


@router.get("/api/enterprise/workspaces/{workspace_id}/teams")
async def get_workspace_teams(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get all teams in a workspace"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    teams = db.query(Team).filter(Team.workspace_id == workspace_id).all()
    
    return [{
        "team_id": t.id,
        "name": t.name,
        "description": t.description,
        "workspace_id": t.workspace_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "member_count": len(t.members)
    } for t in teams]


# ==================== Team Endpoints ====================

@router.post("/api/enterprise/teams", status_code=201)
async def create_team(
    data: TeamCreate,
    db: Session = Depends(get_db)
):
    """Create a new team"""
    workspace = db.query(Workspace).filter(Workspace.id == data.workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    team = Team(
        name=data.name,
        description=data.description,
        workspace_id=data.workspace_id
    )
    
    db.add(team)
    db.commit()
    db.refresh(team)
    
    logger.info(f"Created team: {team.id} in workspace: {data.workspace_id}")
    return {"team_id": team.id}


@router.get("/api/enterprise/teams")
async def list_teams(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all teams"""
    query = db.query(Team)
    
    if workspace_id:
        query = query.filter(Team.workspace_id == workspace_id)
    
    teams = query.all()
    
    return [{
        "team_id": t.id,
        "name": t.name,
        "description": t.description,
        "workspace_id": t.workspace_id,
        "created_at":t.created_at.isoformat() if t.created_at else None,
        "member_count": len(t.members)
    } for t in teams]


@router.get("/api/enterprise/teams/{team_id}")
async def get_team(
    team_id: str,
    db: Session = Depends(get_db)
):
    """Get team details"""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return {
        "team_id": team.id,
        "name": team.name,
        "description": team.description,
        "workspace_id": team.workspace_id,
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "member_count": len(team.members),
        "members": [{
            "user_id": m.id,
            "email": m.email,
            "first_name": m.first_name,
            "last_name": m.last_name,
            "role": m.role
        } for m in team.members]
    }


@router.patch("/api/enterprise/teams/{team_id}")
async def update_team(
    team_id: str,
    data: TeamUpdate,
    db: Session = Depends(get_db)
):
    """Update team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description
    
    db.commit()
    db.refresh(team)
    
    logger.info(f"Updated team: {team_id}")
    return {"message": "Team updated successfully"}


@router.delete("/api/enterprise/teams/{team_id}")
async def delete_team(
    team_id: str,
    db: Session = Depends(get_db)
):
    """Delete team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    db.delete(team)
    db.commit()
    
    logger.info(f"Deleted team: {team_id}")
    return {"message": "Team deleted successfully"}


@router.post("/api/enterprise/teams/{team_id}/users/{user_id}")
async def add_team_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Add user to team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user in team.members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a team member"
        )
    
    team.members.append(user)
    db.commit()
    
    logger.info(f"Added user {user_id} to team {team_id}")
    return {"message": "User added to team successfully"}


@router.delete("/api/enterprise/teams/{team_id}/users/{user_id}")
async def remove_team_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Remove user from team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user not in team.members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a team member"
        )
    
    team.members.remove(user)
    db.commit()
    
    logger.info(f"Removed user {user_id} from team {team_id}")
    return {"message": "User removed from team successfully"}


# ==================== User Endpoints ====================

@router.get("/api/enterprise/users")
async def list_users(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all users"""
    query = db.query(User)
    
    if workspace_id:
        query = query.filter(User.workspace_id == workspace_id)
    
    users = query.all()
    
    return [{
        "user_id": u.id,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "role": u.role,
        "status": u.status,
        "workspace_id": u.workspace_id,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None
    } for u in users]


@router.get("/api/enterprise/users/{user_id}")
async def get_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get user details"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "user_id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "status": user.status,
        "workspace_id": user.workspace_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "teams": [{
            "team_id": t.id,
            "name": t.name
        } for t in user.teams]
    }


@router.patch("/api/enterprise/users/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update user"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"Updated user: {user_id}")
    return {"message": "User updated successfully"}


@router.delete("/api/enterprise/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Deactivate user (soft delete)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.status = UserStatus.DELETED.value
    db.commit()
    
    logger.info(f"Deactivated user: {user_id}")
    return {"message": "User deactivated successfully"}


@router.get("/api/enterprise/users/{user_id}/teams")
async def get_user_teams(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get all teams for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return [{
        "team_id": t.id,
        "name": t.name,
        "description": t.description,
        "workspace_id": t.workspace_id
    } for t in user.teams]
