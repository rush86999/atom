"""
Integration Health Monitor
Periodic health checks for all OAuth integrations
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class IntegrationHealthCheck:
    """Health check for a single integration"""
    
    def __init__(self, name: str, check_func: callable):
        self.name = name
        self.check_func = check_func
        self.last_check_time: Optional[datetime] = None
        self.last_status = HealthStatus.UNKNOWN
        self.last_response_time_ms: Optional[float] = None
        self.consecutive_failures = 0
    
    async def run_check(self) -> Dict:
        """Execute health check and return results"""
        start_time = time.time()
        
        try:
            # Run the health check function
            result = await self.check_func()
            
            response_time_ms = (time.time() - start_time) * 1000
            self.last_response_time_ms = response_time_ms
            self.last_check_time = datetime.now()
            
            # Determine status based on response time and result
            if result and response_time_ms < 5000:  # Less than 5 seconds
                self.last_status = HealthStatus.HEALTHY
                self.consecutive_failures = 0
            elif result and response_time_ms < 10000:  # 5-10 seconds
                self.last_status = HealthStatus.DEGRADED
                self.consecutive_failures = 0
            else:
                self.last_status = HealthStatus.UNHEALTHY
                self.consecutive_failures += 1
            
            return {
                "name": self.name,
                "status": self.last_status.value,
                "response_time_ms": round(response_time_ms, 2),
                "last_check": self.last_check_time.isoformat(),
                "consecutive_failures": self.consecutive_failures
            }
        
        except Exception as e:
            self.consecutive_failures += 1
            self.last_status = HealthStatus.UNHEALTHY
            self.last_check_time = datetime.now()
            
            logger.error(f"Health check failed for {self.name}: {str(e)}")
            
            return {
                "name": self.name,
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e),
                "last_check": self.last_check_time.isoformat(),
                "consecutive_failures": self.consecutive_failures
            }


class HealthMonitor:
    """Central health monitoring service for all integrations"""
    
    def __init__(self, check_interval_seconds: int = 300):  # 5 minutes default
        self.health_checks: Dict[str, IntegrationHealthCheck] = {}
        self.check_interval_seconds = check_interval_seconds
        self.monitoring_task: Optional[asyncio.Task] = None
        self.alerts_enabled = True
        self.alert_threshold = 3  # Alert after 3 consecutive failures
    
    def register_health_check(
        self,
        service_name: str,
        check_func: callable
    ):
        """Register a health check for a service"""
        self.health_checks[service_name] = IntegrationHealthCheck(service_name, check_func)
        logger.info(f"Registered health check for {service_name}")
    
    async def check_all_services(self) -> List[Dict]:
        """Run health checks for all registered services"""
        if not self.health_checks:
            return []
        
        tasks = [check.run_check() for check in self.health_checks.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions from gather
        valid_results = [r for r in results if isinstance(r, dict)]
        
        # Check for alerts
        if self.alerts_enabled:
            self._check_alerts(valid_results)
        
        return valid_results
    
    def _check_alerts(self, results: List[Dict]):
        """Check if any services need alerting"""
        for result in results:
            if result.get("consecutive_failures", 0) >= self.alert_threshold:
                logger.error(
                    f"ALERT: {result['name']} has failed {result['consecutive_failures']} "
                    f"consecutive health checks. Status: {result.get('status')}"
                )
    
    async def start_monitoring(self):
        """Start periodic health check monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Health monitoring is already running")
            return
        
        logger.info(f"Starting health monitoring (interval: {self.check_interval_seconds}s)")
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def _monitoring_loop(self):
        """Continuous monitoring loop"""
        while True:
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def stop_monitoring(self):
        """Stop periodic health monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            logger.info("Stopped health monitoring")
    
    def get_health_summary(self) -> Dict:
        """Get summary of all service health"""
        services = []
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        
        for check in self.health_checks.values():
            status = check.last_status
            if status == HealthStatus.HEALTHY:
                healthy_count += 1
            elif status == HealthStatus.DEGRADED:
                degraded_count += 1
            elif status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
            
            services.append({
                "name": check.name,
                "status": status.value,
                "last_check": check.last_check_time.isoformat() if check.last_check_time else None,
                "response_time_ms": check.last_response_time_ms,
                "consecutive_failures": check.consecutive_failures
            })
        
        total_services = len(self.health_checks)
        health_percentage = (healthy_count / total_services * 100) if total_services > 0 else 0
        
        return {
            "total_services": total_services,
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "health_percentage": round(health_percentage, 1),
            "services": services,
            "last_updated": datetime.now().isoformat()
        }


# Example health check functions
async def check_google_health() -> bool:
    """Health check for Google OAuth"""
    # In production, this would make a lightweight API call
    await asyncio.sleep(0.1)  # Simulate API call
    return True

async def check_microsoft_health() -> bool:
    """Health check for Microsoft OAuth"""
    await asyncio.sleep(0.1)
    return True

async def check_salesforce_health() -> bool:
    """Health check for Salesforce OAuth"""
    await asyncio.sleep(0.1)
    return True


# Global health monitor instance
health_monitor = HealthMonitor(check_interval_seconds=300)

# Register OAuth services for health monitoring
health_monitor.register_health_check("google", check_google_health)
health_monitor.register_health_check("microsoft", check_microsoft_health)
health_monitor.register_health_check("salesforce", check_salesforce_health)
