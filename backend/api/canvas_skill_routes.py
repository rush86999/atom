from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from core.database import get_db
from core.canvas_skill_integration import CanvasSkillIntegrationService
from core.auth import get_current_user
from typing import Dict, Any, Optional, List
from core.models import Skill, CanvasComponent

router = APIRouter(prefix="/canvas-skills", tags=["Canvas-Skill Integration"])

@router.post("/create")
async def create_component_with_skill(
    component_data: Dict[str, Any],
    skill_data: Dict[str, Any],
    tenant_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Creates a pairing of a Canvas Component and an Agent Skill.
    """
    svc = CanvasSkillIntegrationService(db)
    result = await svc.create_component_with_skill(
        tenant_id=tenant_id,
        agent_id=agent_id,
        user_id=current_user.id,
        component_data=component_data,
        skill_data=skill_data
    )
    return result

@router.post("/install/{component_id}")
async def install_component(
    component_id: str,
    tenant_id: str,
    canvas_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Installs a component to a tenant (auto-installs required skill).
    """
    svc = CanvasSkillIntegrationService(db)
    result = await svc.install_component_to_tenant(
        tenant_id=tenant_id,
        user_id=current_user.id,
        component_id=component_id,
        canvas_id=canvas_id,
        config=config
    )
    return result

@router.get("/skills")
async def list_skills(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List installed skills for a tenant.
    """
    skills = db.query(Skill).filter(Skill.tenant_id == tenant_id).all()
    return skills

@router.get("/components")
async def list_components(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List available canvas components for a tenant.
    """
    components = db.query(CanvasComponent).filter(
        (CanvasComponent.tenant_id == tenant_id) | (CanvasComponent.is_public == True)
    ).all()
    return components
