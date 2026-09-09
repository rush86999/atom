from fastapi import Depends, HTTPException, status

from core.auth import get_current_user
from core.models import User, UserRole


async def get_super_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency to ensure the current user is a super admin.
    Used for sensitive platform-level health and administrative routes.
    """
    if current_user.role != UserRole.SUPER_ADMIN.value and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required for this operation"
        )
    return current_user


from core.security.rbac import user_meets_role


async def get_platform_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency for the operator admin band (WORKSPACE_ADMIN and above, via
    the shared role hierarchy).

    2026-09-08b role-journey pass: the daemon-control, cache, skill,
    budget, system-health and workspace-context surfaces were gated by
    exact-super_admin (get_super_admin) — but no local flow ever grants
    super_admin (registration pins member; bootstrap pins workspace_admin;
    role grants are capped at the actor's level), so the operator could
    never reach their own daemon controls. The admin band that actually
    exists locally is workspace_admin+ — same band as runtime settings,
    org politics, ontology drafts and trust calibration.
    """
    if not user_meets_role(current_user, UserRole.WORKSPACE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: workspace_admin or higher",
        )
    return current_user
