"""
Enhanced Airtable Service for ATOM Platform
Demonstrates consolidation using BaseIntegrationService to reduce code duplication
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import HTTPException

# Import base integration service
from core.base_integration import (
    BaseIntegrationService,
    IntegrationConfig,
    IntegrationResponse,
    IntegrationStatus
)

logger = logging.getLogger(__name__)

class AirtableService(BaseIntegrationService):
    """Enhanced Airtable service using BaseIntegrationService"""

    def __init__(self):
        config = IntegrationConfig(
            name="Airtable",
            base_url="https://api.airtable.com/v0",
            api_key_env_var="AIRTABLE_API_KEY",
            oauth_enabled=False,  # Airtable uses API key, not OAuth
            rate_limit_per_minute=100,
            timeout_seconds=30,
            retry_attempts=3,
            backoff_factor=2.0
        )

        super().__init__(config)

        # Airtable-specific configuration
        self.headers = {
            "Content-Type": "application/json"
        }

    async def health_check(self) -> IntegrationResponse:
        """Check Airtable service health"""
        if not self.api_key:
            return IntegrationResponse(
                success=False,
                error="API key not configured",
                status_code=401
            )

        try:
            async with self.get_http_client() as client:
                # Test with a simple API call
                response = await client.get(
                    f"{self.config.base_url}/meta/bases",
                    headers=self._get_auth_headers()
                )

                if response.status_code == 200:
                    bases = response.json().get("bases", [])
                    return IntegrationResponse(
                        success=True,
                        data={
                            "status": "healthy",
                            "bases_count": len(bases),
                            "timestamp": datetime.now().isoformat()
                        },
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                else:
                    return IntegrationResponse(
                        success=False,
                        error=f"API test failed: {response.status_code}",
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Airtable health check failed: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authenticated headers"""
        headers = self.headers.copy()
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_bases(self) -> IntegrationResponse:
        """List all available Airtable bases"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                response = await client.get(
                    f"{self.config.base_url}/meta/bases",
                    headers=self._get_auth_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    return IntegrationResponse(
                        success=True,
                        data=data,
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to list Airtable bases: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    async def list_records(
        self,
        base_id: str,
        table_name: str,
        max_records: int = 100,
        view: str = None,
        filter_formula: str = None,
        sort: List[Dict[str, str]] = None,
        fields: List[str] = None
    ) -> IntegrationResponse:
        """List records from a table"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                params = {"maxRecords": max_records}

                if view:
                    params["view"] = view
                if filter_formula:
                    params["filterByFormula"] = filter_formula
                if sort:
                    params["sort"] = sort
                if fields:
                    params["fields"] = fields

                response = await client.get(
                    f"{self.config.base_url}/{base_id}/{table_name}",
                    headers=self._get_auth_headers(),
                    params=params
                )

                if response.status_code == 200:
                    data = response.json()
                    return IntegrationResponse(
                        success=True,
                        data=data,
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to list Airtable records: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    async def get_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> IntegrationResponse:
        """Get a specific record"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                response = await client.get(
                    f"{self.config.base_url}/{base_id}/{table_name}/{record_id}",
                    headers=self._get_auth_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    return IntegrationResponse(
                        success=True,
                        data=data,
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                elif response.status_code == 404:
                    return IntegrationResponse(
                        success=False,
                        error="Record not found",
                        status_code=404
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to get Airtable record: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    async def create_record(
        self,
        base_id: str,
        table_name: str,
        records: List[Dict[str, Any]]
    ) -> IntegrationResponse:
        """Create new records"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                data = {"records": records}

                response = await client.post(
                    f"{self.config.base_url}/{base_id}/{table_name}",
                    headers=self._get_auth_headers(),
                    json=data
                )

                if response.status_code == 200:
                    data = response.json()
                    return IntegrationResponse(
                        success=True,
                        data=data,
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to create Airtable records: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    async def update_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
        fields: Dict[str, Any]
    ) -> IntegrationResponse:
        """Update a record"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                data = {
                    "records": [{
                        "id": record_id,
                        "fields": fields
                    }]
                }

                response = await client.patch(
                    f"{self.config.base_url}/{base_id}/{table_name}",
                    headers=self._get_auth_headers(),
                    json=data
                )

                if response.status_code == 200:
                    result = response.json()
                    return IntegrationResponse(
                        success=True,
                        data=result,
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to update Airtable record: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    async def delete_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> IntegrationResponse:
        """Delete a record"""
        try:
            if not self.api_key:
                return IntegrationResponse(
                    success=False,
                    error="API key not configured",
                    status_code=401
                )

            async with self.get_http_client() as client:
                response = await client.delete(
                    f"{self.config.base_url}/{base_id}/{table_name}/{record_id}",
                    headers=self._get_auth_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    return IntegrationResponse(
                        success=True,
                        data={"deleted": True, "record_id": record_id},
                        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", 0))
                    )
                elif response.status_code == 404:
                    return IntegrationResponse(
                        success=False,
                        error="Record not found",
                        status_code=404
                    )
                else:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    return IntegrationResponse(
                        success=False,
                        error=error_data.get("error", "Unknown error"),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error(f"Failed to delete Airtable record: {e}")
            return IntegrationResponse(
                success=False,
                error=str(e)
            )

    # OAuth integration (for future Airtable OAuth support)
    async def get_oauth_url(self, redirect_uri: str, state: str) -> IntegrationResponse:
        """Get OAuth URL (placeholder for future OAuth support)"""
        return IntegrationResponse(
            success=False,
            error="OAuth not implemented for Airtable (uses API key authentication)"
        )

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> IntegrationResponse:
        """Exchange authorization code for access token (placeholder)"""
        return IntegrationResponse(
            success=False,
            error="OAuth not implemented for Airtable (uses API key authentication)"
        )


# Enhanced service instance
airtable_enhanced_service = AirtableService()

# Backward compatibility wrapper
class AirtableServiceLegacy:
    """Legacy wrapper for backward compatibility"""

    def __init__(self):
        self.enhanced_service = airtable_enhanced_service

    async def close(self):
        """Close connection (legacy method)"""
        # BaseIntegrationService handles connection management
        pass

    async def list_records(self, base_id: str, table_name: str, **kwargs) -> List[Dict[str, Any]]:
        """Legacy wrapper for list_records"""
        result = await self.enhanced_service.list_records(base_id, table_name, **kwargs)
        if result.success:
            return result.data.get("records", [])
        else:
            raise HTTPException(status_code=result.status_code or 500, detail=result.error)

    async def get_record(self, base_id: str, table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Legacy wrapper for get_record"""
        result = await self.enhanced_service.get_record(base_id, table_name, record_id)
        if result.success:
            return result.data
        elif result.status_code == 404:
            return None
        else:
            raise HTTPException(status_code=result.status_code or 500, detail=result.error)

    async def create_record(self, base_id: str, table_name: str, records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Legacy wrapper for create_record"""
        result = await self.enhanced_service.create_record(base_id, table_name, records)
        if result.success:
            return result.data
        else:
            raise HTTPException(status_code=result.status_code or 500, detail=result.error)

    async def update_record(self, base_id: str, table_name: str, record_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy wrapper for update_record"""
        result = await self.enhanced_service.update_record(base_id, table_name, record_id, fields)
        if result.success:
            return result.data
        else:
            raise HTTPException(status_code=result.status_code or 500, detail=result.error)

    async def delete_record(self, base_id: str, table_name: str, record_id: str) -> bool:
        """Legacy wrapper for delete_record"""
        result = await self.enhanced_service.delete_record(base_id, table_name, record_id)
        return result.success

# Create singleton instances for backward compatibility
airtable_service = AirtableServiceLegacy()

def get_airtable_service() -> AirtableServiceLegacy:
    """Get Airtable service instance (legacy compatibility)"""
    return airtable_service

def get_airtable_enhanced_service() -> AirtableService:
    """Get enhanced Airtable service instance"""
    return airtable_enhanced_service