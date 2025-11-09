#!/usr/bin/env python3
"""
Enhanced Integration Service Base Class
Provides common functionality for all integration services
"""

import os
import json
import logging
import httpx
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from asyncpg import Pool

logger = logging.getLogger(__name__)

@dataclass
class ServiceMetrics:
    """Service performance metrics"""
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    last_request_time: Optional[str] = None
    total_response_time: float = 0.0

@dataclass
class ServiceStatus:
    """Service status information"""
    name: str
    status: str  # 'active', 'inactive', 'error', 'degraded'
    last_check: str
    error_message: Optional[str] = None
    metrics: Optional[ServiceMetrics] = None

class EnhancedIntegrationService(ABC):
    """Enhanced base class for all integration services"""
    
    def __init__(self, service_name: str, user_id: str):
        self.service_name = service_name
        self.user_id = user_id
        self.access_token = None
        self.refresh_token = None
        self.db_pool = None
        self._initialized = False
        self.metrics = ServiceMetrics()
        self.status = ServiceStatus(
            name=service_name,
            status="inactive",
            last_check=datetime.now(timezone.utc).isoformat(),
            metrics=self.metrics
        )
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
    
    @abstractmethod
    async def initialize(self, db_pool: Pool) -> bool:
        """Initialize the service with database pool"""
        pass
    
    @abstractmethod
    def get_api_base_url(self) -> str:
        """Get the base URL for the API"""
        pass
    
    @abstractmethod
    async def refresh_access_token(self) -> bool:
        """Refresh the access token"""
        pass
    
    @abstractmethod
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        pass
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception(f"{self.service_name} service not initialized. Call initialize() first.")
    
    async def _make_request(self, method: str, endpoint: str, 
                           data: Dict[str, Any] = None, 
                           params: Dict[str, Any] = None,
                           headers: Dict[str, str] = None,
                           timeout: float = 30.0) -> Dict[str, Any]:
        """Make authenticated API request with comprehensive error handling and rate limiting"""
        start_time = time.time()
        self.metrics.request_count += 1
        
        try:
            # Rate limiting
            async with self._rate_limit_lock:
                current_time = time.time()
                time_since_last_request = current_time - self._last_request_time
                if time_since_last_request < self._min_request_interval:
                    await asyncio.sleep(self._min_request_interval - time_since_last_request)
                self._last_request_time = time.time()
            
            # Prepare request
            url = f"{self.get_api_base_url()}{endpoint}"
            request_headers = self.get_auth_headers()
            if headers:
                request_headers.update(headers)
            
            # Make request with timeout
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=request_headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=request_headers, json=data, params=params)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=request_headers, json=data, params=params)
                elif method.upper() == "PATCH":
                    response = await client.patch(url, headers=request_headers, json=data, params=params)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=request_headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response_time = (time.time() - start_time) * 1000  # milliseconds
                self._update_metrics(response_time, True)
                
                # Handle authentication errors
                if response.status_code == 401:
                    logger.warning(f"{self.service_name} token expired, attempting refresh")
                    refresh_success = await self.refresh_access_token()
                    if refresh_success:
                        # Retry with new token
                        request_headers = self.get_auth_headers()
                        if headers:
                            request_headers.update(headers)
                        
                        if method.upper() == "GET":
                            response = await client.get(url, headers=request_headers, params=params)
                        elif method.upper() == "POST":
                            response = await client.post(url, headers=request_headers, json=data, params=params)
                        elif method.upper() == "PUT":
                            response = await client.put(url, headers=request_headers, json=data, params=params)
                        elif method.upper() == "PATCH":
                            response = await client.patch(url, headers=request_headers, json=data, params=params)
                        elif method.upper() == "DELETE":
                            response = await client.delete(url, headers=request_headers, params=params)
                    else:
                        return {
                            "success": False,
                            "error": "Authentication failed - unable to refresh token",
                            "status_code": 401
                        }
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.text
                    logger.error(f"{self.service_name} API error {response.status_code}: {error_data}")
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}",
                        "details": error_data,
                        "status_code": response.status_code
                    }
                
                # Success
                try:
                    response_data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    response_data = {"raw_response": response.text}
                
                return {
                    "success": True,
                    "data": response_data,
                    "status_code": response.status_code,
                    "response_time": response_time
                }
                
        except httpx.TimeoutException as e:
            response_time = (time.time() - start_time) * 1000
            self._update_metrics(response_time, False)
            logger.error(f"{self.service_name} API timeout: {e}")
            return {
                "success": False,
                "error": "Request timeout",
                "response_time": response_time
            }
        except httpx.ConnectError as e:
            response_time = (time.time() - start_time) * 1000
            self._update_metrics(response_time, False)
            logger.error(f"{self.service_name} connection error: {e}")
            return {
                "success": False,
                "error": "Connection error",
                "details": str(e),
                "response_time": response_time
            }
        except httpx.HTTPStatusError as e:
            response_time = (time.time() - start_time) * 1000
            self._update_metrics(response_time, False)
            logger.error(f"{self.service_name} HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP error {e.response.status_code}",
                "details": e.response.text,
                "response_time": response_time
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self._update_metrics(response_time, False)
            logger.error(f"{self.service_name} request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_time": response_time
            }
    
    def _update_metrics(self, response_time: float, success: bool):
        """Update service metrics"""
        self.metrics.total_response_time += response_time
        self.metrics.last_request_time = datetime.now(timezone.utc).isoformat()
        
        if success:
            self.metrics.success_count += 1
        else:
            self.metrics.error_count += 1
        
        # Calculate average response time
        if self.metrics.request_count > 0:
            self.metrics.avg_response_time = self.metrics.total_response_time / self.metrics.request_count
        
        # Update status based on recent performance
        self._update_service_status()
    
    def _update_service_status(self):
        """Update service status based on metrics"""
        total_requests = self.metrics.request_count
        if total_requests == 0:
            self.status.status = "inactive"
            return
        
        success_rate = self.metrics.success_count / total_requests
        
        if success_rate >= 0.95:
            self.status.status = "active"
        elif success_rate >= 0.7:
            self.status.status = "degraded"
        else:
            self.status.status = "error"
        
        self.status.last_check = datetime.now(timezone.utc).isoformat()
        self.status.error_message = None
    
    async def health_check(self) -> ServiceStatus:
        """Perform a comprehensive health check"""
        try:
            if not self._initialized:
                self.status.status = "inactive"
                self.status.error_message = "Service not initialized"
                self.status.last_check = datetime.now(timezone.utc).isoformat()
                return self.status
            
            # Try a simple health check request
            health_endpoint = self._get_health_check_endpoint()
            if health_endpoint:
                result = await self._make_request("GET", health_endpoint, timeout=10.0)
                if result["success"]:
                    self.status.status = "active"
                    self.status.error_message = None
                else:
                    self.status.status = "error"
                    self.status.error_message = result.get("error", "Unknown error")
            else:
                # If no health endpoint, check if we have valid tokens
                if self.access_token:
                    self.status.status = "active"
                    self.status.error_message = None
                else:
                    self.status.status = "error"
                    self.status.error_message = "No valid access token"
            
            self.status.last_check = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            self.status.status = "error"
            self.status.error_message = str(e)
            self.status.last_check = datetime.now(timezone.utc).isoformat()
            logger.error(f"{self.service_name} health check failed: {e}")
        
        return self.status
    
    def _get_health_check_endpoint(self) -> Optional[str]:
        """Override this method to provide a health check endpoint"""
        return None
    
    def get_metrics(self) -> ServiceMetrics:
        """Get current service metrics"""
        return self.metrics
    
    def get_status(self) -> ServiceStatus:
        """Get current service status"""
        return self.status
    
    async def reset_metrics(self):
        """Reset service metrics"""
        self.metrics = ServiceMetrics()
        self.status.metrics = self.metrics
        logger.info(f"{self.service_name} metrics reset")
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get comprehensive service information"""
        return {
            "service_name": self.service_name,
            "user_id": self.user_id,
            "initialized": self._initialized,
            "status": asdict(self.status),
            "metrics": asdict(self.metrics),
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token)
        }