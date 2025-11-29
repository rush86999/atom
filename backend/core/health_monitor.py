"""
Health Monitoring System

Periodically checks the health of all integrations and tracks their status.
Provides alerting for degraded services.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

class ServiceHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

class HealthCheck:
    """Single health check result"""
    def __init__(
        self,
        service_name: str,
        status: ServiceHealth,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        checked_at: Optional[datetime] = None
    ):
        self.service_name = service_name
        self.status = status
        self.response_time_ms = response_time_ms
        self.error_message = error_message
        self.checked_at = checked_at or datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "checked_at": self.checked_at.isoformat()
        }

class HealthMonitor:
    """
    Monitors health of all integrations and tracks historical data.
    """
    
    def __init__(self, data_dir: str = "./health_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.current_health: Dict[str, HealthCheck] = {}
        self.health_history: List[HealthCheck] = []
        self.running = False
        
        # Service endpoints for health checks
        self.service_endpoints = {
            "google": "https://www.googleapis.com/oauth2/v1/tokeninfo",
            "microsoft": "https://graph.microsoft.com/v1.0/$metadata",
            "salesforce": "https://login.salesforce.com/services/oauth2/token",
            "slack": "https://slack.com/api/api.test",
            "github": "https://api.github.com",
        }
    
    async def check_service_health(self, service_name: str, endpoint: str) -> HealthCheck:
        """
        Check health of a single service.
        """
        start_time = datetime.now()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint)
                
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                # Determine health based on status code and response time
                if response.status_code < 400:
                    if elapsed_ms < 1000:
                        status = ServiceHealth.HEALTHY
                    else:
                        status = ServiceHealth.DEGRADED
                    error_message = None
                else:
                    status = ServiceHealth.DEGRADED
                    error_message = f"HTTP {response.status_code}"
                
                return HealthCheck(
                    service_name=service_name,
                    status=status,
                    response_time_ms=elapsed_ms,
                    error_message=error_message
                )
                
        except asyncio.TimeoutError:
            return HealthCheck(
                service_name=service_name,
                status=ServiceHealth.DOWN,
                error_message="Request timeout"
            )
        except Exception as e:
            return HealthCheck(
                service_name=service_name,
                status=ServiceHealth.DOWN,
                error_message=str(e)
            )
    
    async def check_all_services(self) -> List[HealthCheck]:
        """
        Check health of all configured services.
        """
        logger.info("Starting health check for all services")
        
        tasks = [
            self.check_service_health(service, endpoint)
            for service, endpoint in self.service_endpoints.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_checks = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check failed with exception: {result}")
            else:
                health_checks.append(result)
                # Update current health
                self.current_health[result.service_name] = result
                # Add to history
                self.health_history.append(result)
        
        # Save health data
        self._save_health_data()
        
        # Check for alerts
        self._check_alerts(health_checks)
        
        logger.info(f"Health check complete. {len(health_checks)} services checked.")
        return health_checks
    
    def _check_alerts(self, health_checks: List[HealthCheck]):
        """
        Check if any services need alerts.
        """
        for check in health_checks:
            if check.status == ServiceHealth.DOWN:
                logger.warning(f"ALERT: Service {check.service_name} is DOWN - {check.error_message}")
            elif check.status == ServiceHealth.DEGRADED:
                logger.warning(f"ALERT: Service {check.service_name} is DEGRADED - {check.error_message}")
    
    def _save_health_data(self):
        """Save current health data to disk"""
        try:
            # Save current health
            current_file = self.data_dir / "current_health.json"
            with open(current_file, 'w') as f:
                data = {
                    service: check.to_dict()
                    for service, check in self.current_health.items()
                }
                json.dump(data, f, indent=2)
            
            # Save recent history (last 1000 checks)
            history_file = self.data_dir / "health_history.json"
            with open(history_file, 'w') as f:
                data = [check.to_dict() for check in self.health_history[-1000:]]
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving health data: {e}")
    
    def get_service_status(self, service_name: str) -> Optional[HealthCheck]:
        """Get current status of a service"""
        return self.current_health.get(service_name)
    
    def get_service_uptime(self, service_name: str, hours: int = 24) -> float:
        """
        Calculate uptime percentage for a service over the last N hours.
        
        Returns:
            Uptime percentage (0.0 to 100.0)
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        relevant_checks = [
            check for check in self.health_history
            if check.service_name == service_name and check.checked_at >= cutoff
        ]
        
        if not relevant_checks:
            return 0.0
        
        healthy_checks = sum(
            1 for check in relevant_checks
            if check.status == ServiceHealth.HEALTHY
        )
        
        return (healthy_checks / len(relevant_checks)) * 100.0
    
    async def start_background_monitoring(self, interval_minutes: int = 15):
        """
        Start background health monitoring service.
        
        Args:
            interval_minutes: How often to check service health
        """
        self.running = True
        logger.info(f"Starting health monitoring service (interval: {interval_minutes}m)")
        
        while self.running:
            try:
                await self.check_all_services()
            except Exception as e:
                logger.error(f"Error in health monitoring cycle: {e}")
            
            # Wait for next cycle
            await asyncio.sleep(interval_minutes * 60)
    
    def stop(self):
        """Stop the background monitoring service"""
        self.running = False
        logger.info("Health monitoring service stopped")


# Global instance
_health_monitor = None

def get_health_monitor() -> HealthMonitor:
    """Get or create global HealthMonitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
