"""
Formula API Routes for ATOM Platform
REST API endpoints for formula storage, search, and execution.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from core.formula_memory import get_formula_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/formulas", tags=["formulas"])


# Request/Response Models

class FormulaCreateRequest(BaseModel):
    """Request to create a new formula."""
    expression: str = Field(..., description="Formula expression (e.g., 'Revenue - Cost')")
    name: str = Field(..., description="Human-readable name (e.g., 'Net Profit')")
    domain: str = Field("general", description="Category (e.g., 'finance', 'sales')")
    use_case: str = Field("", description="Description of when to use this formula")
    parameters: List[Dict[str, str]] = Field(
        default=[],
        description="Parameter definitions [{'name': 'Revenue', 'type': 'number'}]"
    )
    example_input: Optional[Dict[str, Any]] = Field(None, description="Example input values")
    example_output: Optional[Any] = Field(None, description="Expected output for example")
    dependencies: Optional[List[str]] = Field(None, description="IDs of formulas this depends on")


class FormulaApplyRequest(BaseModel):
    """Request to execute a formula."""
    inputs: Dict[str, Any] = Field(..., description="Parameter values to apply")


class FormulaResponse(BaseModel):
    """Standard formula response."""
    id: Optional[str] = None
    expression: str = ""
    name: str = ""
    domain: str = ""
    use_case: str = ""
    parameters: List[Dict[str, str]] = []
    source: str = ""
    created_at: Optional[str] = None


class FormulaSearchResponse(BaseModel):
    """Search results response."""
    query: str
    count: int
    formulas: List[Dict[str, Any]]


class FormulaLineageResponse(BaseModel):
    """Lineage/dependency response."""
    formula_id: str
    upstream: List[Dict[str, str]]
    downstream: List[Dict[str, str]]


class FormulaApplyResponse(BaseModel):
    """Formula execution response."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    formula_name: Optional[str] = None
    expression: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None


# API Endpoints

@router.post("", response_model=Dict[str, Any])
async def create_formula(
    request: FormulaCreateRequest,
    workspace_id: str = Query("default", description="Workspace ID"),
    user_id: str = Query("default_user", description="User ID")
):
    """
    Create a new formula in Atom's memory.
    
    The formula will be embedded for semantic search and can be retrieved
    by natural language queries like "calculate profit margin".
    """
    manager = get_formula_manager(workspace_id)
    
    formula_id = manager.add_formula(
        expression=request.expression,
        name=request.name,
        domain=request.domain,
        use_case=request.use_case,
        parameters=request.parameters,
        example_input=request.example_input,
        example_output=request.example_output,
        source="api",
        user_id=user_id,
        dependencies=request.dependencies
    )
    
    if formula_id:
        return {
            "success": True,
            "formula_id": formula_id,
            "message": f"Formula '{request.name}' created successfully"
        }
    
    raise HTTPException(status_code=500, detail="Failed to create formula")


@router.get("/search", response_model=FormulaSearchResponse)
async def search_formulas(
    q: str = Query(..., description="Natural language search query"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    workspace_id: str = Query("default", description="Workspace ID"),
    user_id: Optional[str] = Query(None, description="Filter by user")
):
    """
    Search for formulas by natural language query.
    
    Examples:
    - "calculate profit margin"
    - "how to compute burn rate"
    - "revenue calculation"
    """
    manager = get_formula_manager(workspace_id)
    
    formulas = manager.search_formulas(
        query=q,
        domain=domain,
        limit=limit,
        user_id=user_id
    )
    
    return FormulaSearchResponse(
        query=q,
        count=len(formulas),
        formulas=formulas
    )


@router.get("/{formula_id}", response_model=Dict[str, Any])
async def get_formula(
    formula_id: str,
    workspace_id: str = Query("default", description="Workspace ID")
):
    """Get a specific formula by ID."""
    manager = get_formula_manager(workspace_id)
    
    formula = manager.get_formula(formula_id)
    
    if formula:
        return formula
    
    raise HTTPException(status_code=404, detail=f"Formula {formula_id} not found")


@router.get("/{formula_id}/lineage", response_model=FormulaLineageResponse)
async def get_formula_lineage(
    formula_id: str,
    workspace_id: str = Query("default", description="Workspace ID")
):
    """
    Get the dependency lineage for a formula.
    
    Returns upstream formulas (dependencies) and downstream formulas
    (formulas that depend on this one).
    """
    manager = get_formula_manager(workspace_id)
    
    lineage = manager.get_formula_lineage(formula_id)
    
    return FormulaLineageResponse(**lineage)


@router.post("/{formula_id}/apply", response_model=FormulaApplyResponse)
async def apply_formula(
    formula_id: str,
    request: FormulaApplyRequest,
    workspace_id: str = Query("default", description="Workspace ID")
):
    """
    Execute a formula with given inputs.
    
    Provide parameter values matching the formula's defined parameters.
    """
    manager = get_formula_manager(workspace_id)
    
    result = manager.apply_formula(
        formula_id=formula_id,
        inputs=request.inputs
    )
    
    return FormulaApplyResponse(**result)


@router.delete("/{formula_id}")
async def delete_formula(
    formula_id: str,
    workspace_id: str = Query("default", description="Workspace ID")
):
    """Delete a formula from memory."""
    manager = get_formula_manager(workspace_id)
    
    success = manager.delete_formula(formula_id)
    
    if success:
        return {"success": True, "message": f"Formula {formula_id} deleted"}
    
    raise HTTPException(status_code=404, detail=f"Formula {formula_id} not found or delete failed")


# Agent Integration Endpoint

@router.get("/agent/relevant")
async def get_relevant_formulas_for_agent(
    context: str = Query(..., description="Agent's current task context"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(5, description="Maximum formulas to return"),
    workspace_id: str = Query("default", description="Workspace ID")
):
    """
    Get formulas relevant to an agent's current context.
    
    Used by Atom agents to find applicable calculations for their tasks.
    """
    manager = get_formula_manager(workspace_id)
    
    formulas = manager.search_formulas(
        query=context,
        domain=domain,
        limit=limit
    )
    
    # Return simplified format for agent consumption
    return {
        "context": context,
        "available_formulas": [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "expression": f.get("expression"),
                "use_case": f.get("use_case"),
                "parameters": f.get("parameters")
            }
            for f in formulas
        ]
    }
