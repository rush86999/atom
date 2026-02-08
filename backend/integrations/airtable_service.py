"""
Airtable Service for ATOM Platform
Provides comprehensive Airtable database and spreadsheet integration functionality
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class AirtableService:
    def __init__(self):
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_url = "https://api.airtable.com/v0"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def list_records(
        self,
        base_id: str,
        table_name: str,
        max_records: int = 100,
        view: str = None,
        filter_formula: str = None
    ) -> List[Dict[str, Any]]:
        """List records from a table"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            params = {"maxRecords": max_records}
            
            if view:
                params["view"] = view
            if filter_formula:
                params["filterByFormula"] = filter_formula
            
            response = await self.client.get(
                f"{self.base_url}/{base_id}/{table_name}",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("records", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list records: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list records: {str(e)}"
            )

    async def get_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> Dict[str, Any]:
        """Get a specific record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            response = await self.client.get(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get record: {str(e)}"
            )

    async def create_record(
        self,
        base_id: str,
        table_name: str,
        fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {"fields": fields}
            
            response = await self.client.post(
                f"{self.base_url}/{base_id}/{table_name}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create record: {str(e)}"
            )

    async def update_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
        fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {"fields": fields}
            
            response = await self.client.patch(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to update record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update record: {str(e)}"
            )

    async def delete_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> Dict[str, Any]:
        """Delete a record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            response = await self.client.delete(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete record: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Airtable service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "airtable",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "airtable",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

airtable_service = AirtableService()

def get_airtable_service() -> AirtableService:
    return airtable_service
