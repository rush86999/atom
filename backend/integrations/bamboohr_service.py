"""
BambooHR Service for ATOM Platform
Provides BambooHR HR management integration (employees, time-off)
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

BAMBOOHR_BASE_URL = "https://api.bamboohr.com/api/gateway.php"


def bamboohr_configured() -> bool:
    """Check whether BambooHR credentials are configured."""
    return bool(os.getenv("BAMBOOHR_SUBDOMAIN") and os.getenv("BAMBOOHR_API_KEY"))


class BambooHRService:
    """Service for BambooHR REST API interactions"""

    def __init__(self, subdomain: str = None, api_key: str = None):
        self.subdomain = subdomain or os.getenv("BAMBOOHR_SUBDOMAIN", "")
        self.api_key = api_key or os.getenv("BAMBOOHR_API_KEY", "")
        self.base_url = f"{BAMBOOHR_BASE_URL}/{self.subdomain}/v1" if self.subdomain else BAMBOOHR_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _check_configured(self):
        """Raise if the service is not configured"""
        if not self.subdomain or not self.api_key:
            raise HTTPException(
                status_code=503,
                detail="BambooHR integration not configured. Set BAMBOOHR_SUBDOMAIN and BAMBOOHR_API_KEY."
            )

    def _get_headers(self) -> Dict[str, str]:
        """BambooHR uses basic auth with API key as username and 'x' as password"""
        import base64
        credentials = base64.b64encode(f"{self.api_key}:x".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }

    async def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Any:
        """Make authenticated request to BambooHR API"""
        self._check_configured()
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()

        try:
            response = await self.client.request(
                method, url, headers=headers, data=data, params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"BambooHR API returned {e.response.status_code} for {method} {endpoint}")
            raise HTTPException(
                status_code=e.response.status_code if e.response.status_code >= 400 else 400,
                detail=f"BambooHR API error: {e.response.status_code}"
            )
        except httpx.HTTPError as e:
            logger.error(f"BambooHR API request failed: {e}")
            raise HTTPException(status_code=502, detail="Internal error")

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def list_employees(self) -> List[Dict[str, Any]]:
        """List employees from the employee directory (GET /employees/directory)"""
        result = await self._make_request("GET", "employees/directory")
        return result.get("employees", [])

    async def get_employee(self, employee_id: str) -> Dict[str, Any]:
        """Get a single employee (GET /employees/{id})"""
        fields = [
            "firstName", "lastName", "workEmail", "jobTitle",
            "department", "location", "hireDate", "status",
        ]
        return await self._make_request(
            "GET", f"employees/{employee_id}", params={"fields": ",".join(fields)}
        )

    async def create_employee(
        self,
        first_name: str,
        last_name: str,
        work_email: str = None,
        job_title: str = None,
    ) -> Dict[str, Any]:
        """Create an employee (POST /employees, form-encoded fields)"""
        payload = {"firstName": first_name, "lastName": last_name}
        if work_email:
            payload["workEmail"] = work_email
        if job_title:
            payload["jobTitle"] = job_title

        return await self._make_request("POST", "employees", data=payload)

    async def get_time_off_requests(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get time-off requests (GET /time_off/requests)"""
        return await self._make_request("GET", "time_off/requests", params=params)

    async def health_check(self) -> Dict[str, Any]:
        """Health check for BambooHR service"""
        return {
            "ok": bamboohr_configured(),
            "status": "healthy" if bamboohr_configured() else "not_configured",
            "service": "bamboohr",
            "configured": bamboohr_configured(),
        }


# Singleton instance
bamboohr_service = BambooHRService()


def get_bamboohr_service() -> BambooHRService:
    """Get BambooHR service instance"""
    return bamboohr_service
