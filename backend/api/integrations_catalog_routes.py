from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from core.database import get_db
from core.models import IntegrationCatalog
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations-catalog"])
logger = logging.getLogger(__name__)

class IntegrationResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    category: str
    icon: Optional[str] = ""
    color: str = "#6366F1"
    authType: str = "none"
    triggers: List[dict] = []
    actions: List[dict] = []
    popular: bool = False
    native_id: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/catalog", response_model=List[IntegrationResponse])
async def get_integrations_catalog(
    category: Optional[str] = Query(None),
    popular: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns the full catalog of integrations from the database.
    """
    try:
        query = db.query(IntegrationCatalog)
        
        if category:
            query = query.filter(IntegrationCatalog.category == category)
        
        if popular is not None:
            query = query.filter(IntegrationCatalog.popular == popular)
            
        if search:
            search_query = f"%{search}%"
            query = query.filter(
                (IntegrationCatalog.name.ilike(search_query)) | 
                (IntegrationCatalog.description.ilike(search_query))
            )
            
        integrations = query.all()
        
        # Map DB model to response (handling underscores vs camelCase)
        response = []
        for i in integrations:
            response.append({
                "id": i.id,
                "name": i.name,
                "description": i.description,
                "category": i.category,
                "icon": i.icon,
                "color": i.color,
                "authType": i.auth_type,
                "triggers": i.triggers or [],
                "actions": i.actions or [],
                "popular": i.popular,
                "native_id": i.native_id
            })
            
        return response
    except Exception as e:
        logger.error(f"Error fetching integrations catalog: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/catalog/{piece_id}", response_model=IntegrationResponse)
async def get_integration_details(piece_id: str, db: Session = Depends(get_db)):
    """
    Returns details for a specific integration piece.
    """
    piece = db.query(IntegrationCatalog).filter(IntegrationCatalog.id == piece_id).first()
    if not piece:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    return {
        "id": piece.id,
        "name": piece.name,
        "description": piece.description,
        "category": piece.category,
        "icon": piece.icon,
        "color": piece.color,
        "authType": piece.auth_type,
        "triggers": piece.triggers or [],
        "actions": piece.actions or [],
        "popular": piece.popular
    }
