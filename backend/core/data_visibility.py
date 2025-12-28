"""
Data Visibility Module for ATOM Platform

Provides visibility scoping (private, team, workspace) for data entities.
Enables proper data segregation based on user, team, and workspace membership.
"""

from enum import Enum
from typing import List, Any, TYPE_CHECKING
from sqlalchemy import Column, String, ForeignKey, and_, or_
from sqlalchemy.orm import declared_attr, Query

if TYPE_CHECKING:
    from core.models import User


class DataVisibility(str, Enum):
    """Data visibility levels for scoping access"""
    PRIVATE = "private"      # Only creator can see
    TEAM = "team"            # Team members can see
    WORKSPACE = "workspace"  # All workspace members can see (default)


class VisibilityMixin:
    """
    Mixin to add visibility scoping to any SQLAlchemy model.
    
    Usage:
        class MyModel(Base, VisibilityMixin):
            __tablename__ = "my_table"
            # ... other columns
    
    This adds:
        - visibility: str (private/team/workspace)
        - owner_id: FK to users
        - team_id: FK to teams (optional, for team-scoped data)
    """
    
    visibility = Column(String, default=DataVisibility.WORKSPACE.value, nullable=False)
    
    @declared_attr
    def owner_id(cls):
        """Owner of the data - required for private visibility"""
        return Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    @declared_attr
    def team_id(cls):
        """Team for team-scoped data"""
        return Column(String, ForeignKey("teams.id"), nullable=True, index=True)


def apply_visibility_filter(query: Query, user: "User", model_class: Any) -> Query:
    """
    Apply visibility filtering to any SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query to filter
        user: Current authenticated user
        model_class: The model class being queried (must have VisibilityMixin)
    
    Returns:
        Filtered query respecting visibility rules
    
    Example:
        query = db.query(Workflow)
        filtered = apply_visibility_filter(query, current_user, Workflow)
    """
    # Check if model has visibility column
    if not hasattr(model_class, 'visibility'):
        return query
    
    # Get user's team and workspace IDs
    team_ids = [t.id for t in user.teams] if hasattr(user, 'teams') and user.teams else []
    workspace_ids = [w.id for w in user.workspaces] if hasattr(user, 'workspaces') and user.workspaces else []
    
    # Build visibility filter
    conditions = [
        # PRIVATE: Only owner can see
        and_(
            model_class.visibility == DataVisibility.PRIVATE.value,
            model_class.owner_id == user.id
        ),
        # WORKSPACE: Default - visible to all (no additional filter needed for now)
        model_class.visibility == DataVisibility.WORKSPACE.value
    ]
    
    # TEAM: Must be in the same team
    if team_ids:
        conditions.append(
            and_(
                model_class.visibility == DataVisibility.TEAM.value,
                model_class.team_id.in_(team_ids)
            )
        )
    
    return query.filter(or_(*conditions))


def get_visibility_for_user(user: "User", visibility: str = None) -> dict:
    """
    Get default visibility settings for a user creating new data.
    
    Args:
        user: The user creating data
        visibility: Optional explicit visibility override
    
    Returns:
        Dict with owner_id, team_id, visibility for new record
    """
    default_team_id = None
    if hasattr(user, 'teams') and user.teams:
        default_team_id = user.teams[0].id  # Use first team as default
    
    return {
        "owner_id": user.id,
        "team_id": default_team_id,
        "visibility": visibility or DataVisibility.WORKSPACE.value
    }


def can_access(user: "User", resource: Any) -> bool:
    """
    Check if a user can access a specific resource.
    
    Args:
        user: The user requesting access
        resource: The resource to check (must have VisibilityMixin attrs)
    
    Returns:
        True if user can access, False otherwise
    """
    if not hasattr(resource, 'visibility'):
        return True  # No visibility control = public
    
    visibility = resource.visibility
    
    # PRIVATE: Only owner
    if visibility == DataVisibility.PRIVATE.value:
        return resource.owner_id == user.id
    
    # TEAM: Must be in team
    if visibility == DataVisibility.TEAM.value:
        if not hasattr(user, 'teams') or not user.teams:
            return False
        team_ids = [t.id for t in user.teams]
        return resource.team_id in team_ids
    
    # WORKSPACE: Default accessible
    if visibility == DataVisibility.WORKSPACE.value:
        return True
    
    return False
