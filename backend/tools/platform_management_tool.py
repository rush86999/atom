"""
Platform Management Tools for Atom
Provides administrative tools for managing tenants, workspaces, members, and teams.
"""

import logging
import uuid
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.database import SessionLocal
from core.models import Tenant, Workspace, User, Team, team_members
from sqlalchemy import or_

logger = logging.getLogger(__name__)

async def get_platform_settings(context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Retrieves platform-wide settings and configuration for the current tenant."""
    from core.database import SessionLocal
    from core.models import TenantSetting
    
    workspace_id = context.get("workspace_id") if context else None
    if not workspace_id:
        return {"error": "No workspace context found."}
        
    try:
        with SessionLocal() as db:
            settings = db.query(TenantSetting).filter(TenantSetting.tenant_id == workspace_id).all()
            return {s.setting_key: s.setting_value for s in settings}
    except Exception as e:
        logger.error(f"Error fetching platform settings: {e}")
        return {"error": f"Failed to fetch settings: {str(e)}"}

async def update_platform_setting(key: str, value: str, context: Dict[str, Any] = None) -> str:
    """Updates or creates a platform-wide setting."""
    from core.database import SessionLocal
    from core.models import TenantSetting
    
    workspace_id = context.get("workspace_id") if context else None
    if not workspace_id:
        return "Error: No workspace context found."
        
    try:
        with SessionLocal() as db:
            setting = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == workspace_id,
                TenantSetting.setting_key == key
            ).first()
            
            if setting:
                setting.setting_value = value
            else:
                setting = TenantSetting(tenant_id=workspace_id, setting_key=key, setting_value=value)
                db.add(setting)
            
            db.commit()
            return f"Setting '{key}' successfully updated to '{value}'."
    except Exception as e:
        logger.error(f"Error updating platform setting: {e}")
        return f"Error: Failed to update setting: {str(e)}"

async def update_tenant_profile(
    name: Optional[str] = None,
    billing_email: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    budget_limit_usd: Optional[float] = None,
    context: Dict[str, Any] = None
) -> str:
    """Updates the tenant's profile information."""
    from core.database import SessionLocal
    from core.models import Tenant, Workspace
    
    workspace_id = context.get("workspace_id") if context else None
    if not workspace_id:
        return "Error: No workspace context found."
        
    try:
        with SessionLocal() as db:
            # First get tenant_id from workspace
            ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not ws:
                return f"Error: Workspace {workspace_id} not found."
            
            tenant_id = ws.tenant_id
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return f"Error: Tenant {tenant_id} not found."
            
            updates = []
            if name:
                tenant.name = name
                updates.append("name")
            if billing_email:
                tenant.billing_email = billing_email
                updates.append("billing_email")
            if logo_url:
                metadata = tenant.metadata_json or {}
                metadata["logo_url"] = logo_url
                tenant.metadata_json = metadata
                updates.append("logo_url")
            if primary_color:
                metadata = tenant.metadata_json or {}
                metadata["primary_color"] = primary_color
                tenant.metadata_json = metadata
                updates.append("primary_color")
            if budget_limit_usd is not None:
                tenant.budget_limit_usd = budget_limit_usd
                updates.append("budget_limit_usd")
                
            if not updates:
                return "No updates provided."
                
            db.commit()
            return f"Tenant profile updated successfully. Fields modified: {', '.join(updates)}."
    except Exception as e:
        logger.error(f"Error updating tenant profile: {e}")
        return f"Error: Failed to update tenant profile: {str(e)}"

async def set_byok_api_key(
    provider: str,
    api_key: str,
    context: Dict[str, Any] = None
) -> str:
    """Sets or updates a Bring-Your-Own-Key (BYOK) API key for a provider."""
    from core.database import SessionLocal
    from core.byok_endpoints import BYOKManager
    
    tenant_id = context.get("workspace_id") if context else None
    if not tenant_id:
        return "Error: Could not resolve tenant/workspace ID from context."
        
    db = SessionLocal()
    try:
        manager = BYOKManager(db)
        await manager.set_api_key(tenant_id, provider, api_key)
        db.commit()
        return f"Successfully set API key for {provider} in tenant {tenant_id}."
    except Exception as e:
        db.rollback()
        logger.error(f"Error setting BYOK API key: {e}")
        return f"Error setting BYOK API key: {str(e)}"
    finally:
        db.close()

async def list_tenant_members(context: Dict[str, Any] = None) -> str:
    """Lists all members of the current tenant."""
    from core.database import SessionLocal
    from core.models import User, Workspace
    
    workspace_id = context.get("workspace_id") if context else None
    if not workspace_id:
        return "Error: Could not resolve workspace ID from context."
        
    db = SessionLocal()
    try:
        # First get the tenant_id from the workspace
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            return f"Error: Workspace {workspace_id} not found."
            
        tenant_id = ws.tenant_id
        
        # Get all users belonging to this tenant
        # In multi-tenant architecture, users usually have a tenant_id
        members = db.query(User).filter(User.tenant_id == tenant_id).all()
        
        if not members:
            return "No members found for this tenant."
            
        result = [f"Members for Tenant {tenant_id}:"]
        for m in members:
            result.append(f"- {m.full_name or m.email} (ID: {m.id}, Role: {getattr(m, 'role', 'N/A')}, Status: {getattr(m, 'status', 'N/A')})")
            
        return "\n".join(result)
    except Exception as e:
        logger.error(f"Error listing tenant members: {e}")
        return f"Error listing tenant members: {str(e)}"
    finally:
        db.close()

async def manage_tenant_member(
    user_id: str,
    action: str, # "update_role", "deactivate", "reactivate"
    role: Optional[str] = None,
    context: Dict[str, Any] = None
) -> str:
    """Updates a member's role or status within a tenant."""
    from core.database import SessionLocal
    from core.models import User
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return f"Error: User {user_id} not found."
            
        if action == "update_role":
            if not role:
                return "Error: role is required for update_role action."
            user.role = role
            msg = f"User {user_id} role updated to {role}."
        elif action == "deactivate":
            user.is_active = False
            msg = f"User {user_id} deactivated."
        elif action == "reactivate":
            user.is_active = True
            msg = f"User {user_id} reactivated."
        else:
            return f"Error: Unknown action {action}."
            
        db.commit()
        return msg
    except Exception as e:
        db.rollback()
        logger.error(f"Error managing tenant member: {e}")
        return f"Error managing tenant member: {str(e)}"
    finally:
        db.close()

async def manage_workspace(
    name: str,
    action: str = "create", # "create", "update"
    workspace_id: Optional[str] = None,
    description: Optional[str] = None,
    is_startup: bool = False,
    context: Dict[str, Any] = None
) -> str:
    """Creates or updates a workspace within a tenant."""
    from core.database import SessionLocal
    from core.models import Workspace, Tenant
    
    # Resolve tenant_id
    actual_tenant_id = context.get("tenant_id") if context else None
    if not actual_tenant_id:
        workspace_id_ctx = context.get("workspace_id") if context else None
        if workspace_id_ctx:
            # Try to lookup tenant from workspace
            with SessionLocal() as db_temp:
                ws_temp = db_temp.query(Workspace).filter(Workspace.id == workspace_id_ctx).first()
                if ws_temp:
                    actual_tenant_id = ws_temp.tenant_id
        
    if not actual_tenant_id:
        return "Error: Could not resolve tenant ID from context."

    db = SessionLocal()
    try:
        if action == "create":
            new_ws = Workspace(
                name=name,
                description=description,
                is_startup=is_startup,
                tenant_id=actual_tenant_id
            )
            db.add(new_ws)
            db.commit()
            return f"Workspace '{name}' created successfully with ID {new_ws.id}."
        
        elif action == "update":
            if not workspace_id:
                return "Error: workspace_id is required for update action."
            ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not ws:
                return f"Error: Workspace {workspace_id} not found."
            
            ws.name = name
            if description is not None:
                ws.description = description
            ws.is_startup = is_startup
            db.commit()
            return f"Workspace {workspace_id} updated successfully."
        else:
            return f"Error: Unknown action {action}."
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error managing workspace: {e}")
        return f"Error managing workspace: {str(e)}"
    finally:
        db.close()

async def manage_team(
    name: str,
    action: str = "create", # "create", "update"
    team_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    add_members: Optional[List[str]] = None, # List of user emails or IDs
    context: Dict[str, Any] = None
) -> str:
    """Creates or updates a Team and its members."""
    from core.database import SessionLocal
    from core.models import Team, User, team_members, Workspace, Tenant
    
    tenant_id = context.get("workspace_id") if context else None
    if not tenant_id:
        return "Error: Could not resolve tenant/workspace context."

    db = SessionLocal()
    try:
        # Resolve actual workspace_id if not provided
        if not workspace_id:
            workspace_id = context.get("workspace_id")

        if action == "create":
            team = Team(
                name=name,
                workspace_id=workspace_id
            )
            db.add(team)
            db.flush() # Get team.id
            team_id = team.id
            msg = f"Team '{name}' created successfully with ID {team_id}."
        elif action == "update":
            if not team_id:
                return "Error: team_id is required for update action."
            team = db.query(Team).filter(Team.id == team_id).first()
            if not team:
                return f"Error: Team {team_id} not found."
            team.name = name
            msg = f"Team {team_id} updated successfully."
        else:
            return f"Error: Unknown action {action}."

        # Add members if provided
        if add_members and team_id:
            added = 0
            for identifier in add_members:
                user = db.query(User).filter(or_(User.id == identifier, User.email == identifier)).first()
                if user:
                    # Check if already in team
                    existing = db.query(team_members).filter(
                        team_members.c.user_id == user.id,
                        team_members.c.team_id == team_id
                    ).first()
                    if not existing:
                        db.execute(team_members.insert().values(user_id=user.id, team_id=team_id))
                        added += 1
            msg += f" Added {added} members."

        db.commit()
        return msg
    except Exception as e:
        db.rollback()
        logger.error(f"Error managing team: {e}")
        return f"Error managing team: {str(e)}"
    finally:
        db.close()
