from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from core.database import get_db
from core.models import User, Artifact, ArtifactVersion, AgentRegistry
from core.security_dependencies import get_current_user

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

class ArtifactBase(BaseModel):
    name: str
    type: str
    content: str
    metadata_json: Optional[dict] = {}
    session_id: Optional[str] = None
    agent_id: Optional[str] = None

class ArtifactCreate(ArtifactBase):
    pass

class ArtifactUpdate(BaseModel):
    id: str
    name: Optional[str] = None
    content: Optional[str] = None
    metadata_json: Optional[dict] = None

class ArtifactResponse(ArtifactBase):
    id: str
    version: int
    is_locked: bool
    author_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[ArtifactResponse])
async def list_artifacts(
    session_id: Optional[str] = None,
    type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Artifact).filter(Artifact.workspace_id == "default") # Standardized workspace
    
    if session_id:
        query = query.filter(Artifact.session_id == session_id)
    if type:
        query = query.filter(Artifact.type == type)
        
    return query.order_by(Artifact.updated_at.desc()).all()

@router.post("/", response_model=ArtifactResponse)
async def save_artifact(
    artifact_data: ArtifactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if we are updating or creating
    # For now, we'll assume creation unless an ID is provided (if we use a wrapper class)
    # But let's handle the logic properly
    
    new_artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id="default",
        agent_id=artifact_data.agent_id,
        session_id=artifact_data.session_id,
        name=artifact_data.name,
        type=artifact_data.type,
        content=artifact_data.content,
        metadata_json=artifact_data.metadata_json or {},
        author_id=current_user.id
    )
    
    db.add(new_artifact)
    db.commit()
    db.refresh(new_artifact)
    return new_artifact

@router.post("/update", response_model=ArtifactResponse)
async def update_artifact(
    update_data: ArtifactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    artifact = db.query(Artifact).filter(Artifact.id == update_data.id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
        
    # 1. Create version record from current state
    version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=artifact.id,
        version=artifact.version,
        content=artifact.content,
        metadata_json=artifact.metadata_json,
        author_id=artifact.author_id
    )
    db.add(version)
    
    # 2. Update artifact
    if update_data.name:
        artifact.name = update_data.name
    if update_data.content:
        artifact.content = update_data.content
    if update_data.metadata_json:
        artifact.metadata_json = update_data.metadata_json
        
    artifact.version += 1
    artifact.updated_at = datetime.now()
    
    db.commit()
    db.refresh(artifact)
    return artifact

@router.get("/{artifact_id}/versions")
async def get_artifact_versions(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    versions = db.query(ArtifactVersion).filter(
        ArtifactVersion.artifact_id == artifact_id
    ).order_by(ArtifactVersion.version.desc()).all()
    return versions
