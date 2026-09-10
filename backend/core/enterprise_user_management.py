"""
Enterprise User Management - Database-backed Implementation
Multi-tenant user management with team collaboration, permissions, and workspace isolation
Migrated from in-memory to SQLAlchemy persistence
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Make EmailStr optional to avoid email-validator dependency
try:
    from pydantic import EmailStr
    EMAIL_VALIDATION_AVAILABLE = True
except ImportError:
    EMAIL_VALIDATION_AVAILABLE = False
    EmailStr = str  # Fallback to regular string

import logging

from core.auth import get_password_hash, get_current_user
from core.database import get_db
from core.models import Team, User, UserRole, UserStatus, Workspace, WorkspaceStatus
from core.rbac_service import Permission
from core.security.rbac import role_level, user_meets_role
from core.security_dependencies import require_permission

# SECURITY: every endpoint in this router manages users/workspaces/teams —
# create, update, delete, role changes. ALL require admin auth. Previously
# the entire router had zero auth dependencies, so any anonymous caller could
# PATCH /api/enterprise/users/{id} {"role":"super_admin"} for full takeover.
# 2026-09-08 role-journey pass: `get_current_user` alone still let ANY
# authenticated member drive the whole surface (self-serve super_admin).
# This is the workspace-administration plane — WORKSPACE_ADMIN+ (hierarchy
# via core.security.rbac, so admin/owner/super_admin all pass).
async def require_workspace_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Router-wide gate: the re-queried user must hold WORKSPACE_ADMIN or higher."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user or not user_meets_role(user, UserRole.WORKSPACE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: workspace_admin or higher",
        )
    return user


router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_workspace_admin)]
)
logger = logging.getLogger(__name__)


def _ensure_can_manage(db: Session, actor_id: str, target: User) -> None:
    """An admin may not act on a user ranked above them (a workspace_admin
    cannot disable/promote an owner)."""
    actor = db.query(User).filter(User.id == actor_id).first()
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if role_level(target.role) > role_level(actor.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage a user with a higher role than your own",
        )


def _ensure_grantable_role(actor_id: str, new_role: str, db: Session) -> str:
    """Validate a role assignment target: must be a UserRole value and may
    not exceed the actor's own level (no self-serve escalation)."""
    normalized = (new_role or "").strip().lower()
    try:
        target_role = UserRole(normalized)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(r.value for r in UserRole)}",
        )
    actor = db.query(User).filter(User.id == actor_id).first()
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if role_level(target_role) > role_level(actor.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot grant a role higher than your own",
        )
    return target_role.value

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
    email: str  # Using str instead of EmailStr to avoid email-validator dependency
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None  # admin UI convenience — split into first/last
    role: str = UserRole.MEMBER.value
    workspace_id: Optional[str] = None

    def names(self) -> tuple:
        """(first_name, last_name) from explicit fields or full_name."""
        if self.first_name or self.last_name:
            return self.first_name or "", self.last_name or ""
        parts = (self.full_name or "").strip().split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

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

@router.get("/api/enterprise/roles")
async def list_roles():
    """Role catalog for the admin user-management UI (dropdowns, caps)."""
    return [
        {"name": r.value, "level": role_level(r)}
        for r in sorted(UserRole, key=role_level)
    ]


@router.post(
    "/api/enterprise/users",
    status_code=201,
    # user:manage per the permission matrix (workspace_admin+/owner; a
    # plain domain admin deliberately does not provision accounts). This
    # is the enforcement the journey tripwire flagged as granted-but-never-
    # checked; the router-level workspace_admin+ gate stays as defense in
    # depth.
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Provision a user account (admin UI 'Add employee'). The granted role
    may not exceed the creating admin's own level."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    role_value = _ensure_grantable_role(current_user.id, data.role, db)
    first_name, last_name = data.names()
    if not first_name:
        first_name = data.email.split("@")[0]

    import uuid as _uuid

    user = User(
        id=str(_uuid.uuid4()),
        email=data.email,
        hashed_password=get_password_hash(data.password),
        first_name=first_name,
        last_name=last_name,
        role=role_value,
        status=UserStatus.ACTIVE.value,
        is_active=True,
        workspace_id=data.workspace_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Created user {user.email} with role {role_value}")
    return {"user_id": user.id, "email": user.email, "role": user.role}


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


@router.patch(
    "/api/enterprise/users/{user_id}",
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user. Role/status changes are capped: an admin may not modify
    a higher-ranked user nor grant a role above their own level."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    _ensure_can_manage(db, current_user.id, user)

    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.role is not None:
        user.role = _ensure_grantable_role(current_user.id, data.role, db)
    if data.status is not None:
        user.status = data.status
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"Updated user: {user_id}")
    return {"message": "User updated successfully"}


@router.delete(
    "/api/enterprise/users/{user_id}",
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate user (soft delete). May not target a higher-ranked user."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    _ensure_can_manage(db, current_user.id, user)

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
