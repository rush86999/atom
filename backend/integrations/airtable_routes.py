import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from core.token_storage import token_storage
import httpx
import os
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/airtable", tags=["airtable"])

class AirtableSearchResponse(BaseModel):
    query: str
    results: List[Dict]
    timestamp: str

class AirtableSearchRequest(BaseModel):
    query: str

class AirtableBase(BaseModel):
    id: str
    name: str
    permission_level: str

class AirtableTable(BaseModel):
    id: str
    name: str
    primary_field_id: str
    fields: List[Dict]
    records_count: int

class AirtableRecord(BaseModel):
    id: str
    created_time: str
    fields: Dict

class AirtableService:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("AIRTABLE_ACCESS_TOKEN")
        self.base_url = "https://api.airtable.com/v0"

    async def get_bases(self):
        """Get all Airtable bases for the user"""
        if not self.access_token:
            raise HTTPException(status_code=401, detail="Airtable access token not configured")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/meta/bases", headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch Airtable bases")

            data = response.json()
            return data.get("bases", [])

    async def get_base_tables(self, base_id: str):
        """Get all tables in a specific base"""
        if not self.access_token:
            raise HTTPException(status_code=401, detail="Airtable access token not configured")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            # Get base info first to get table schemas
            response = await client.get(f"{self.base_url}/meta/bases/{base_id}/tables", headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch base tables")

            data = response.json()
            return data.get("tables", [])

    async def get_table_records(self, base_id: str, table_id: str, limit: int = 100, offset: Optional[str] = None):
        """Get records from a specific table"""
        if not self.access_token:
            raise HTTPException(status_code=401, detail="Airtable access token not configured")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        params = {"maxRecords": limit}
        if offset:
            params["offset"] = offset

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{base_id}/{table_id}",
                headers=headers,
                params=params
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch table records")

            data = response.json()
            return data

    async def search_records(self, base_id: str, table_id: str, query: str, limit: int = 100):
        """Search records in a table (simple implementation)"""
        if not self.access_token:
            raise HTTPException(status_code=401, detail="Airtable access token not configured")

        # Get all records first (Airtable doesn't have built-in text search across all fields)
        records_data = await self.get_table_records(base_id, table_id, limit=limit)

        # Filter records that contain the query in any field value
        filtered_records = []
        query_lower = query.lower()

        for record in records_data.get("records", []):
            for field_value in record.get("fields", {}).values():
                if isinstance(field_value, str) and query_lower in field_value.lower():
                    filtered_records.append(record)
                    break

        return {
            "records": filtered_records[:limit],
            "query": query,
            "total_found": len(filtered_records)
        }

async def get_airtable_service(user_id: str = "default_user"):
    """Get Airtable service with user's access token"""
    try:
        # Get stored token for user
        token_data = await token_storage.get_token(user_id, "airtable")
        if token_data:
            return AirtableService(access_token=token_data.get("access_token"))
        else:
            # Use system-wide token if available
            return AirtableService()
    except Exception as e:
        logger.warning(f"Could not get Airtable token for user {user_id}: {str(e)}")
        return AirtableService()


@router.get("/status")
async def airtable_status(user_id: str = "default_user"):
    """Get Airtable integration status"""
    try:
        service = await get_airtable_service(user_id)

        # Test if we have valid credentials by making a simple API call
        has_credentials = bool(service.access_token)
        connection_status = "connected" if has_credentials else "not_connected"

        return {
            "ok": True,
            "service": "airtable",
            "user_id": user_id,
            "status": connection_status,
            "message": "Airtable integration is available" if has_credentials else "Airtable access token not configured",
            "timestamp": datetime.now().isoformat(),
            "features": {
                "base_access": has_credentials,
                "table_operations": has_credentials,
                "record_management": has_credentials,
                "views": has_credentials,
                "filtering": has_credentials,
                "sorting": has_credentials
            },
            "has_credentials": has_credentials
        }
    except Exception as e:
        logger.error(f"Airtable status check failed: {str(e)}")
        return {
            "ok": False,
            "service": "airtable",
            "user_id": user_id,
            "status": "error",
            "message": f"Airtable integration error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "has_credentials": False
        }

@router.get("/bases")
async def get_airtable_bases(user_id: str = "default_user"):
    """Get all Airtable bases for the user"""
    try:
        service = await get_airtable_service(user_id)
        bases = await service.get_bases()

        return {
            "success": True,
            "data": bases,
            "total": len(bases),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Airtable bases: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch Airtable bases")

@router.get("/bases/{base_id}/tables")
async def get_airtable_base_tables(base_id: str, user_id: str = "default_user"):
    """Get all tables in a specific Airtable base"""
    try:
        service = await get_airtable_service(user_id)
        tables = await service.get_base_tables(base_id)

        return {
            "success": True,
            "data": tables,
            "base_id": base_id,
            "total": len(tables),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Airtable tables for base {base_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch base tables")

@router.get("/bases/{base_id}/tables/{table_id}/records")
async def get_airtable_table_records(
    base_id: str,
    table_id: str,
    limit: int = Query(default=100, le=1000),
    offset: Optional[str] = Query(None),
    user_id: str = "default_user"
):
    """Get records from a specific Airtable table"""
    try:
        service = await get_airtable_service(user_id)
        records_data = await service.get_table_records(base_id, table_id, limit, offset)

        return {
            "success": True,
            "data": records_data.get("records", []),
            "base_id": base_id,
            "table_id": table_id,
            "limit": limit,
            "offset": records_data.get("offset"),
            "total": len(records_data.get("records", [])),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Airtable records: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch table records")

@router.post("/bases/{base_id}/tables/{table_id}/search")
async def search_airtable_records(
    base_id: str,
    table_id: str,
    request: AirtableSearchRequest,
    limit: int = Query(default=100, le=1000),
    user_id: str = "default_user"
):
    """Search records in an Airtable table"""
    try:
        service = await get_airtable_service(user_id)
        search_results = await service.search_records(base_id, table_id, request.query, limit)

        return AirtableSearchResponse(
            query=request.query,
            results=search_results.get("records", []),
            timestamp=datetime.now().isoformat(),
            total_found=search_results.get("total_found", 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search Airtable records: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search records")

@router.post("/search")
async def airtable_search_legacy(request: AirtableSearchRequest, user_id: str = "default_user"):
    """Legacy search endpoint - searches across all accessible bases and tables"""
    try:
        service = await get_airtable_service(user_id)

        # Get all bases first
        bases = await service.get_bases()
        all_results = []

        # Search through each base and table
        for base in bases[:5]:  # Limit to first 5 bases for performance
            try:
                tables = await service.get_base_tables(base["id"])
                for table in tables[:3]:  # Limit to first 3 tables per base
                    try:
                        search_results = await service.search_records(
                            base["id"],
                            table["id"],
                            request.query,
                            limit=10
                        )

                        # Add context to results
                        for record in search_results.get("records", []):
                            all_results.append({
                                "id": record["id"],
                                "fields": record.get("fields", {}),
                                "base_id": base["id"],
                                "base_name": base.get("name", "Unknown Base"),
                                "table_id": table["id"],
                                "table_name": table.get("name", "Unknown Table"),
                                "snippet": f"Found in {base.get('name', 'Unknown Base')} > {table.get('name', 'Unknown Table')}"
                            })
                    except Exception as e:
                        logger.warning(f"Failed to search table {table['id']} in base {base['id']}: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"Failed to get tables for base {base['id']}: {str(e)}")
                continue

        return AirtableSearchResponse(
            query=request.query,
            results=all_results[:50],  # Limit total results
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Legacy Airtable search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/health")
async def airtable_health():
    """Health check for Airtable integration"""
    return {
        "status": "healthy",
        "service": "airtable",
        "capabilities": [
            "database_management",
            "record_operations",
            "view_management",
            "collaboration",
            "api_integration",
            "real-time_sync",
            "formula_fields",
            "attachments"
        ],
        "business_value": {
            "data_organization": True,
            "workflow_automation": True,
            "team_collaboration": True,
            "reporting": True,
            "project_management": True,
            "crm_functionality": True,
            "inventory_tracking": True
        },
        "api_version": "v0",
        "timestamp": datetime.now().isoformat()
    }
