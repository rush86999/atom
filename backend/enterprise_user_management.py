"""
Enterprise User Management System
Multi-tenant user management with team collaboration, permissions, and workspace isolation
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, validator

router = APIRouter()


class UserRole(Enum):
    """User roles for permission management"""

    SUPER_ADMIN = "super_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    TEAM_LEAD = "team_lead"
    MEMBER = "member"
    GUEST = "guest"


class UserStatus(Enum):
    """User account status"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class WorkspaceStatus(Enum):
    """Workspace status"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"


class UserCreate(BaseModel):
    """User creation request model"""

    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole = UserRole.MEMBER
    workspace_id: Optional[str] = None

    @validator("first_name", "last_name")
    def validate_name_length(cls, v):
        if len(v) < 1:
            raise ValueError("Name must be at least 1 character long")
        if len(v) > 50:
            raise ValueError("Name must be less than 50 characters")
        return v


class UserUpdate(BaseModel):
    """User update request model"""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class WorkspaceCreate(BaseModel):
    """Workspace creation request model"""

    name: str
    description: Optional[str] = None
    plan_tier: str = "standard"


class TeamCreate(BaseModel):
    """Team creation request model"""

    name: str
    description: Optional[str] = None
    workspace_id: str


class User(BaseModel):
    """User model"""

    user_id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    workspace_id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class Workspace(BaseModel):
    """Workspace model"""

    workspace_id: str
    name: str
    description: Optional[str]
    status: WorkspaceStatus
    plan_tier: str
    created_at: datetime
    updated_at: datetime
    user_count: int
    team_count: int


class Team(BaseModel):
    """Team model"""

    team_id: str
    name: str
    description: Optional[str]
    workspace_id: str
    created_at: datetime
    member_count: int


class EnterpriseUserManagement:
    """Enterprise-grade user management system with multi-tenant support"""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.workspaces: Dict[str, Workspace] = {}
        self.teams: Dict[str, Team] = {}
        self.user_workspace_mapping: Dict[str, str] = {}  # user_id -> workspace_id
        self.team_members: Dict[str, List[str]] = {}  # team_id -> list of user_ids
        self.workspace_teams: Dict[
            str, List[str]
        ] = {}  # workspace_id -> list of team_ids

        # Initialize with sample data for testing
        self._initialize_sample_data()

    def _initialize_sample_data(self):
        """Initialize with sample enterprise data"""
        # Create sample workspace
        workspace_id = str(uuid.uuid4())
        workspace = Workspace(
            workspace_id=workspace_id,
            name="Acme Corporation",
            description="Enterprise workspace for Acme Corporation",
            status=WorkspaceStatus.ACTIVE,
            plan_tier="enterprise",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_count=0,
            team_count=0,
        )
        self.workspaces[workspace_id] = workspace

        # Create sample teams
        engineering_team_id = str(uuid.uuid4())
        sales_team_id = str(uuid.uuid4())

        engineering_team = Team(
            team_id=engineering_team_id,
            name="Engineering",
            description="Software development team",
            workspace_id=workspace_id,
            created_at=datetime.now(),
            member_count=0,
        )

        sales_team = Team(
            team_id=sales_team_id,
            name="Sales",
            description="Sales and business development",
            workspace_id=workspace_id,
            created_at=datetime.now(),
            member_count=0,
        )

        self.teams[engineering_team_id] = engineering_team
        self.teams[sales_team_id] = sales_team
        self.workspace_teams[workspace_id] = [engineering_team_id, sales_team_id]
        self.workspaces[workspace_id].team_count = 2

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user in the system"""
        # Check if user already exists
        existing_user = next(
            (u for u in self.users.values() if u.email == user_data.email), None
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Validate workspace
        if user_data.workspace_id and user_data.workspace_id not in self.workspaces:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )

        user_id = str(uuid.uuid4())
        now = datetime.now()

        user = User(
            user_id=user_id,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            status=UserStatus.ACTIVE,
            workspace_id=user_data.workspace_id or "",
            created_at=now,
            updated_at=now,
        )

        self.users[user_id] = user

        if user_data.workspace_id:
            self.user_workspace_mapping[user_id] = user_data.workspace_id
            # Update workspace user count
            workspace = self.workspaces[user_data.workspace_id]
            workspace.user_count += 1
            workspace.updated_at = now

        return user

    def create_workspace(self, workspace_data: WorkspaceCreate) -> Workspace:
        """Create a new workspace"""
        workspace_id = str(uuid.uuid4())
        now = datetime.now()

        workspace = Workspace(
            workspace_id=workspace_id,
            name=workspace_data.name,
            description=workspace_data.description,
            status=WorkspaceStatus.ACTIVE,
            plan_tier=workspace_data.plan_tier,
            created_at=now,
            updated_at=now,
            user_count=0,
            team_count=0,
        )

        self.workspaces[workspace_id] = workspace
        self.workspace_teams[workspace_id] = []

        return workspace

    def create_team(self, team_data: TeamCreate) -> Team:
        """Create a new team within a workspace"""
        # Validate workspace exists
        if team_data.workspace_id not in self.workspaces:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )

        team_id = str(uuid.uuid4())
        now = datetime.now()

        team = Team(
            team_id=team_id,
            name=team_data.name,
            description=team_data.description,
            workspace_id=team_data.workspace_id,
            created_at=now,
            member_count=0,
        )

        self.teams[team_id] = team
        self.team_members[team_id] = []

        # Add team to workspace
        if team_data.workspace_id in self.workspace_teams:
            self.workspace_teams[team_data.workspace_id].append(team_id)
        else:
            self.workspace_teams[team_data.workspace_id] = [team_id]

        # Update workspace team count
        workspace = self.workspaces[team_data.workspace_id]
        workspace.team_count += 1
        workspace.updated_at = now

        return team

    def add_user_to_team(self, user_id: str, team_id: str) -> bool:
        """Add user to a team"""
        if user_id not in self.users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if team_id not in self.teams:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
            )

        user = self.users[user_id]
        team = self.teams[team_id]

        # Verify user is in the same workspace as team
        if user.workspace_id != team.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User and team must be in the same workspace",
            )

        # Add user to team if not already a member
        if user_id not in self.team_members[team_id]:
            self.team_members[team_id].append(user_id)
            team.member_count += 1
            return True

        return False

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID"""
        return self.workspaces.get(workspace_id)

    def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID"""
        return self.teams.get(team_id)

    def get_users_in_workspace(self, workspace_id: str) -> List[User]:
        """Get all users in a workspace"""
        return [
            user for user in self.users.values() if user.workspace_id == workspace_id
        ]

    def get_users_in_team(self, team_id: str) -> List[User]:
        """Get all users in a team"""
        if team_id not in self.team_members:
            return []

        user_ids = self.team_members[team_id]
        return [self.users[user_id] for user_id in user_ids if user_id in self.users]

    def get_teams_in_workspace(self, workspace_id: str) -> List[Team]:
        """Get all teams in a workspace"""
        if workspace_id not in self.workspace_teams:
            return []

        team_ids = self.workspace_teams[workspace_id]
        return [self.teams[team_id] for team_id in team_ids if team_id in self.teams]

    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """Update user information"""
        if user_id not in self.users:
            return None

        user = self.users[user_id]

        # Update fields if provided
        if user_update.first_name is not None:
            user.first_name = user_update.first_name
        if user_update.last_name is not None:
            user.last_name = user_update.last_name
        if user_update.role is not None:
            user.role = user_update.role
        if user_update.status is not None:
            user.status = user_update.status

        user.updated_at = datetime.now()

        return user

    def delete_user(self, user_id: str) -> bool:
        """Soft delete a user"""
        if user_id not in self.users:
            return False

        user = self.users[user_id]
        user.status = UserStatus.DELETED
        user.updated_at = datetime.now()

        # Remove user from all teams
        for team_id in self.team_members:
            if user_id in self.team_members[team_id]:
                self.team_members[team_id].remove(user_id)
                self.teams[team_id].member_count -= 1

        return True


# Initialize the enterprise user management system
enterprise_user_mgmt = EnterpriseUserManagement()


# API Routes
@router.post(
    "/api/enterprise/users", response_model=User, status_code=status.HTTP_201_CREATED
)
async def create_user_endpoint(user_data: UserCreate):
    """Create a new user"""
    return enterprise_user_mgmt.create_user(user_data)


@router.get("/api/enterprise/users/{user_id}", response_model=User)
async def get_user_endpoint(user_id: str):
    """Get user by ID"""
    user = enterprise_user_mgmt.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/api/enterprise/users/{user_id}", response_model=User)
async def update_user_endpoint(user_id: str, user_update: UserUpdate):
    """Update user information"""
    user = enterprise_user_mgmt.update_user(user_id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/api/enterprise/users/{user_id}")
async def delete_user_endpoint(user_id: str):
    """Delete a user"""
    success = enterprise_user_mgmt.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


@router.post(
    "/api/enterprise/workspaces",
    response_model=Workspace,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_endpoint(workspace_data: WorkspaceCreate):
    """Create a new workspace"""
    return enterprise_user_mgmt.create_workspace(workspace_data)


@router.get("/api/enterprise/workspaces/{workspace_id}", response_model=Workspace)
async def get_workspace_endpoint(workspace_id: str):
    """Get workspace by ID"""
    workspace = enterprise_user_mgmt.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.post(
    "/api/enterprise/teams", response_model=Team, status_code=status.HTTP_201_CREATED
)
async def create_team_endpoint(team_data: TeamCreate):
    """Create a new team"""
    return enterprise_user_mgmt.create_team(team_data)


@router.get("/api/enterprise/teams/{team_id}", response_model=Team)
async def get_team_endpoint(team_id: str):
    """Get team by ID"""
    team = enterprise_user_mgmt.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("/api/enterprise/teams/{team_id}/users/{user_id}")
async def add_user_to_team_endpoint(team_id: str, user_id: str):
    """Add user to a team"""
    success = enterprise_user_mgmt.add_user_to_team(user_id, team_id)
    if not success:
        raise HTTPException(
            status_code=400, detail="User already in team or operation failed"
        )
    return {"message": "User added to team successfully"}


@router.get(
    "/api/enterprise/workspaces/{workspace_id}/users", response_model=List[User]
)
async def get_workspace_users_endpoint(workspace_id: str):
    """Get all users in a workspace"""
    return enterprise_user_mgmt.get_users_in_workspace(workspace_id)


@router.get("/api/enterprise/teams/{team_id}/users", response_model=List[User])
async def get_team_users_endpoint(team_id: str):
    """Get all users in a team"""
    return enterprise_user_mgmt.get_users_in_team(team_id)


@router.get(
    "/api/enterprise/workspaces/{workspace_id}/teams", response_model=List[Team]
)
async def get_workspace_teams_endpoint(workspace_id: str):
    """Get all teams in a workspace"""
    return enterprise_user_mgmt.get_teams_in_workspace(workspace_id)


@router.get("/api/enterprise/stats")
async def get_enterprise_stats():
    """Get enterprise statistics"""
    total_users = len(enterprise_user_mgmt.users)
    total_workspaces = len(enterprise_user_mgmt.workspaces)
    total_teams = len(enterprise_user_mgmt.teams)

    active_users = len(
        [
            u
            for u in enterprise_user_mgmt.users.values()
            if u.status == UserStatus.ACTIVE
        ]
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_workspaces": total_workspaces,
        "total_teams": total_teams,
        "timestamp": datetime.now().isoformat(),
    }
