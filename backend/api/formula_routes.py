"""
Formula Routes - API endpoints for workflow formulas (reusable patterns)
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/formulas", tags=["Formulas"])

# In-memory formula store
_formula_store: Dict[str, Dict[str, Any]] = {}

# Pydantic Models
class FormulaStep(BaseModel):
    type: str = Field(..., description="Step type: action, condition, loop")
    service: Optional[str] = Field(None, description="Service to use")
    action: Optional[str] = Field(None, description="Action to perform")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Step parameters")

class FormulaCreateRequest(BaseModel):
    name: str = Field(..., description="Formula name")
    description: Optional[str] = Field(None, description="Formula description")
    steps: List[FormulaStep] = Field(default_factory=list, description="Formula steps")
    tags: Optional[List[str]] = Field(None, description="Formula tags")
    category: str = Field("general", description="Formula category")

class FormulaResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    steps: List[Dict[str, Any]]
    tags: List[str]
    category: str
    created_at: str
    updated_at: str
    usage_count: int

class FormulaExecuteResponse(BaseModel):
    formula_id: str
    execution_id: str
    status: str
    result: Optional[Dict[str, Any]]
    timestamp: str

@router.post("", response_model=FormulaResponse)
async def create_formula(request: FormulaCreateRequest):
    """Create a new formula"""
    try:
        formula_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        formula = {
            "id": formula_id,
            "name": request.name,
            "description": request.description,
            "steps": [s.dict() for s in request.steps],
            "tags": request.tags or [],
            "category": request.category,
            "created_at": now,
            "updated_at": now,
            "usage_count": 0
        }
        _formula_store[formula_id] = formula
        
        return FormulaResponse(**formula)
    except Exception as e:
        logger.error(f"Failed to create formula: {e}")
        raise router.internal_error(message="Failed to create formula", details={"error": str(e)})

@router.get("", response_model=List[FormulaResponse])
async def list_formulas(category: Optional[str] = None, tag: Optional[str] = None):
    """List all formulas"""
    formulas = list(_formula_store.values())
    
    if category:
        formulas = [f for f in formulas if f.get("category") == category]
    if tag:
        formulas = [f for f in formulas if tag in f.get("tags", [])]
    
    return [FormulaResponse(**f) for f in formulas]

@router.get("/{formula_id}", response_model=FormulaResponse)
async def get_formula(formula_id: str):
    """Get a formula by ID"""
    if formula_id not in _formula_store:
        raise router.not_found_error("Formula", formula_id)
    return FormulaResponse(**_formula_store[formula_id])

@router.put("/{formula_id}", response_model=FormulaResponse)
async def update_formula(formula_id: str, request: FormulaCreateRequest):
    """Update a formula"""
    if formula_id not in _formula_store:
        raise router.not_found_error("Formula", formula_id)
    
    formula = _formula_store[formula_id]
    formula.update({
        "name": request.name,
        "description": request.description,
        "steps": [s.dict() for s in request.steps],
        "tags": request.tags or [],
        "category": request.category,
        "updated_at": datetime.now().isoformat()
    })
    _formula_store[formula_id] = formula
    
    return FormulaResponse(**formula)

@router.delete("/{formula_id}")
async def delete_formula(formula_id: str):
    """Delete a formula"""
    if formula_id not in _formula_store:
        raise router.not_found_error("Formula", formula_id)
    del _formula_store[formula_id]
    return {"message": f"Formula '{formula_id}' deleted"}

@router.post("/{formula_id}/execute", response_model=FormulaExecuteResponse)
async def execute_formula(formula_id: str, context: Optional[Dict[str, Any]] = None):
    """Execute a formula"""
    if formula_id not in _formula_store:
        raise router.not_found_error("Formula", formula_id)
    
    try:
        formula = _formula_store[formula_id]
        formula["usage_count"] = formula.get("usage_count", 0) + 1
        
        execution_id = str(uuid.uuid4())
        
        # Mock execution (would actually run steps in production)
        return FormulaExecuteResponse(
            formula_id=formula_id,
            execution_id=execution_id,
            status="completed",
            result={
                "steps_executed": len(formula.get("steps", [])),
                "context": context or {},
                "message": f"Formula '{formula['name']}' executed successfully"
            },
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Formula execution failed: {e}")
        raise router.internal_error(message="Formula execution failed", details={"error": str(e)})

@router.get("/categories")
async def list_categories():
    """List available formula categories"""
    return {
        "categories": [
            {"id": "general", "name": "General"},
            {"id": "communication", "name": "Communication"},
            {"id": "productivity", "name": "Productivity"},
            {"id": "data", "name": "Data Processing"},
            {"id": "automation", "name": "Automation"},
            {"id": "analytics", "name": "Analytics"},
        ]
    }
