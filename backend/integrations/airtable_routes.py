"""
Airtable Integration Routes for ATOM Platform
Uses the real airtable_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import the real Airtable service
from .airtable_service import AirtableService, airtable_service

logger = logging.getLogger(__name__)

# Auth Type: API Key
router = APIRouter(prefix="/api/airtable", tags=["airtable"])


# Pydantic models
class AirtableSearchRequest(BaseModel):
    query: str
    base_id: Optional[str] = None
    table_name: Optional[str] = None


class AirtableSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str


class AirtableRecordRequest(BaseModel):
    base_id: str
    table_name: str
    fields: Dict[str, Any]


class AirtableUpdateRequest(BaseModel):
    base_id: str
    table_name: str
    record_id: str
    fields: Dict[str, Any]


@router.get("/status")
async def airtable_status(user_id: str = "test_user"):
    """Get Airtable integration status"""
    health = await airtable_service.health_check()
    return {
        "ok": health.get("ok", True),
        "service": "airtable",
        "user_id": user_id,
        "status": "connected" if airtable_service.api_key else "not_configured",
        "message": "Airtable integration is available" if airtable_service.api_key else "API key not configured",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "base_access": True,
            "table_operations": True,
            "record_management": True,
            "views": True,
            "filtering": True,
            "sorting": True
        }
    }


@router.get("/records/{base_id}/{table_name}")
async def list_records(
    base_id: str,
    table_name: str,
    max_records: int = Query(100, le=1000),
    view: Optional[str] = None,
    filter_formula: Optional[str] = None
):
    """List records from an Airtable table"""
    try:
        records = await airtable_service.list_records(
            base_id=base_id,
            table_name=table_name,
            max_records=max_records,
            view=view,
            filter_formula=filter_formula
        )
        return {
            "ok": True,
            "records": records,
            "count": len(records),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/{base_id}/{table_name}/{record_id}")
async def get_record(base_id: str, table_name: str, record_id: str):
    """Get a specific record from Airtable"""
    try:
        record = await airtable_service.get_record(
            base_id=base_id,
            table_name=table_name,
            record_id=record_id
        )
        return {
            "ok": True,
            "record": record,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/records")
async def create_record(request: AirtableRecordRequest):
    """Create a new record in Airtable"""
    try:
        record = await airtable_service.create_record(
            base_id=request.base_id,
            table_name=request.table_name,
            fields=request.fields
        )
        return {
            "ok": True,
            "record": record,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/records")
async def update_record(request: AirtableUpdateRequest):
    """Update a record in Airtable"""
    try:
        record = await airtable_service.update_record(
            base_id=request.base_id,
            table_name=request.table_name,
            record_id=request.record_id,
            fields=request.fields
        )
        return {
            "ok": True,
            "record": record,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/records/{base_id}/{table_name}/{record_id}")
async def delete_record(base_id: str, table_name: str, record_id: str):
    """Delete a record from Airtable"""
    try:
        result = await airtable_service.delete_record(
            base_id=base_id,
            table_name=table_name,
            record_id=record_id
        )
        return {
            "ok": True,
            "deleted": True,
            "record_id": record_id,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def airtable_search(request: AirtableSearchRequest):
    """Search Airtable content"""
    logger.info(f"Searching Airtable for: {request.query}")

    # If base_id and table_name provided, search with filter formula
    if request.base_id and request.table_name:
        try:
            records = await airtable_service.list_records(
                base_id=request.base_id,
                table_name=request.table_name,
                filter_formula=f"SEARCH('{request.query}', {{Name}})"
            )
            return AirtableSearchResponse(
                ok=True,
                query=request.query,
                results=records,
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return AirtableSearchResponse(
                ok=False,
                query=request.query,
                results=[],
                timestamp=datetime.now().isoformat()
            )
    
    # Without base/table, return empty with guidance
    return AirtableSearchResponse(
        ok=True,
        query=request.query,
        results=[],
        timestamp=datetime.now().isoformat()
    )


@router.get("/health")
async def airtable_health():
    """Health check for Airtable integration"""
    health = await airtable_service.health_check()
    return {
        "status": "healthy" if health.get("ok") else "unhealthy",
        "service": "airtable",
        "configured": bool(airtable_service.api_key),
        "capabilities": [
            "database_management",
            "record_operations",
            "view_management",
            "collaboration",
            "api_integration"
        ],
        "business_value": {
            "data_organization": True,
            "workflow_automation": True,
            "team_collaboration": True,
            "reporting": True
        },
        "timestamp": datetime.now().isoformat()
    }
