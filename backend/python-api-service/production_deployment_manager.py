"""
Production Deployment Manager with Health Monitoring

This module provides comprehensive production deployment automation
with health checks, monitoring, and deployment orchestration.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import docker
import psutil
import requests

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"
    CANCELLED = "cancelled"


class HealthStatus(Enum):
    """Health status enumeration"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class DeploymentConfig:
    """Deployment configuration"""

    name: str
    version: str
    environment: str
    services: List[str]
    health_check_endpoints: Dict[str, str]
    rollback_enabled: bool = True
    max_rollback_attempts: int = 3
    health_check_timeout: int = 300  # 5 minutes
    health_check_interval: int = 10  # 10 seconds


@dataclass
class HealthCheckResult:
    """Health check result"""

    service: str
    status: HealthStatus
    response_time_ms: float
    error: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class DeploymentResult:
    """Deployment result"""

    deployment_id: str
    status: DeploymentStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    services_deployed: List[str] = None
    health_check_results: List[HealthCheckResult] = None
    rollback_attempts: int = 0
    error: Optional[str] = None

    def __post_init__(self):
        if self.services_deployed is None:
            self.services_deployed = []
        if self.health_check_results is None:
            self.health_check_results = []


class ProductionDeploymentManager:
    """
    Production deployment manager with comprehensive health monitoring
    and automated rollback capabilities.
    """

    def __init__(self, docker_client=None, deployment_config: DeploymentConfig = None):
        self.docker_client = docker_client or docker.from_env()
        self.deployment_config = deployment_config
        self.current_deployment = None
        self.deployment_history = []
        self.health_monitors = {}
        self.metrics_collector = MetricsCollector()

        # Initialize deployment configuration if not provided
        if not self.deployment_config:
            self.deployment_config = self._get_default_config()

        logger.info("Production Deployment Manager initialized")

    def _get_default_config(self) -> DeploymentConfig:
        """Get default deployment configuration"""
        return DeploymentConfig(
            name="atom-platform",
            version="1.0.0",
            environment="production",
            services=[
                "backend-api",
                "frontend-nextjs",
                "database",
                "redis",
                "lancedb",
                "nginx",
            ],
            health_check_endpoints={
                "backend-api": "http://localhost:5058/health",
                "frontend-nextjs": "http://localhost:3000/api/health",
                "database": "http://localhost:5432/health",
                "redis": "http://localhost:6379/health",
                "lancedb": "http://localhost:8080/health",
            },
        )

    async def deploy(self, config: DeploymentConfig = None) -> DeploymentResult:
        """Execute a complete production deployment"""
        deployment_config = config or self.deployment_config
        deployment_id = self._generate_deployment_id()

        self.current_deployment = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.RUNNING,
            start_time=datetime.now(),
        )

        logger.info(f"Starting deployment {deployment_id} for {deployment_config.name}")

        try:
            # 1. Pre-deployment checks
            await self._run_pre_deployment_checks(deployment_config)

            # 2. Stop existing services
            await self._stop_existing_services(deployment_config)

            # 3. Deploy new services
            await self._deploy_services(deployment_config)

            # 4. Run health checks
            health_results = await self._run_health_checks(deployment_config)
            self.current_deployment.health_check_results = health_results

            # 5. Verify deployment success
            if self._is_deployment_successful(health_results):
                self.current_deployment.status = DeploymentStatus.SUCCESS
                self.current_deployment.services_deployed = deployment_config.services
                logger.info(f"Deployment {deployment_id} completed successfully")
            else:
                # 6. Rollback if health checks fail
                await self._rollback_deployment(deployment_config)
                self.current_deployment.status = DeploymentStatus.ROLLBACK
                logger.error(f"Deployment {deployment_id} failed, rolled back")

        except Exception as e:
            logger.error(f"Deployment {deployment_id} failed: {str(e)}")
            self.current_deployment.status = DeploymentStatus.FAILED
            self.current_deployment.error = str(e)

            # Attempt rollback on failure
            try:
                await self._rollback_deployment(deployment_config)
            except Exception as rollback_error:
                logger.error(f"Rollback also failed: {str(rollback_error)}")

        finally:
            self.current_deployment.end_time = datetime.now()
            self.deployment_history.append(self.current_deployment)

            # Clean up
            await self._cleanup_deployment_resources()

        return self.current_deployment

    async def _run_pre_deployment_checks(self, config: DeploymentConfig):
        """Run pre-deployment validation checks"""
        logger.info("Running pre-deployment checks...")

        checks = [
            self._check_disk_space,
            self._check_memory_availability,
            self._check_network_connectivity,
            self._check_docker_availability,
            self._check_configuration_validity,
        ]

        for check in checks:
            try:
                await check(config)
            except Exception as e:
                raise Exception(f"Pre-deployment check failed: {str(e)}")

        logger.info("All pre-deployment checks passed")

    async def _check_disk_space(self, config: DeploymentConfig):
        """Check available disk space"""
        disk_usage = psutil.disk_usage("/")
        free_gb = disk_usage.free / (1024**3)

        if free_gb < 5:  # Less than 5GB free
            raise Exception(
                f"Insufficient disk space: {free_gb:.2f}GB free, need at least 5GB"
            )

        logger.info(f"Disk space check passed: {free_gb:.2f}GB free")

    async def _check_memory_availability(self, config: DeploymentConfig):
        """Check available memory"""
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)

        if available_gb < 2:  # Less than 2GB available
            raise Exception(
                f"Insufficient memory: {available_gb:.2f}GB available, need at least 2GB"
            )

        logger.info(f"Memory check passed: {available_gb:.2f}GB available")

    async def _check_network_connectivity(self, config: DeploymentConfig):
        """Check network connectivity to required endpoints"""
        required_endpoints = [
            "https://api.github.com",
            "https://oauth2.googleapis.com",
            "https://graph.microsoft.com",
        ]

        for endpoint in required_endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                if response.status_code >= 400:
                    raise Exception(
                        f"Endpoint {endpoint} returned {response.status_code}"
                    )
            except Exception as e:
                raise Exception(
                    f"Network connectivity check failed for {endpoint}: {str(e)}"
                )

        logger.info("Network connectivity checks passed")

    async def _check_docker_availability(self, config: DeploymentConfig):
        """Check Docker availability and version"""
        try:
            info = self.docker_client.info()
            version = self.docker_client.version()
            logger.info(f"Docker check passed: Version {version['Version']}")
        except Exception as e:
            raise Exception(f"Docker not available: {str(e)}")

    async def _check_configuration_validity(self, config: DeploymentConfig):
        """Validate deployment configuration"""
        if not config.services:
            raise Exception("No services specified in deployment configuration")

        if not config.health_check_endpoints:
            raise Exception("No health check endpoints specified")

        # Verify all services have health check endpoints
        for service in config.services:
            if service not in config.health_check_endpoints:
                logger.warning(f"Service {service} has no health check endpoint")

        logger.info("Configuration validation passed")

    async def _stop_existing_services(self, config: DeploymentConfig):
        """Stop existing running services"""
        logger.info("Stopping existing services...")

        for service in config.services:
            try:
                # Stop Docker containers
                containers = self.docker_client.containers.list(
                    filters={"name": service}, all=True
                )

                for container in containers:
                    if container.status == "running":
                        container.stop(timeout=30)
                        logger.info(f"Stopped container: {service}")

            except Exception as e:
                logger.warning(f"Failed to stop service {service}: {str(e)}")

        logger.info("Existing services stopped")

    async def _deploy_services(self, config: DeploymentConfig):
        """Deploy new services using Docker Compose"""
        logger.info("Deploying new services...")

        try:
            # Build and start services using docker-compose
            compose_file = "docker-compose.production.yml"

            if os.path.exists(compose_file):
                # Build services
                build_result = subprocess.run(
                    ["docker-compose", "-f", compose_file, "build"],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )

                if build_result.returncode != 0:
                    raise Exception(f"Build failed: {build_result.stderr}")

                # Start services
                up_result = subprocess.run(
                    ["docker-compose", "-f", compose_file, "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )

                if up_result.returncode != 0:
                    raise Exception(f"Deployment failed: {up_result.stderr}")

                logger.info("Services deployed successfully using docker-compose")

            else:
                logger.warning(
                    "docker-compose.production.yml not found, using individual container deployment"
                )
                await self._deploy_individual_containers(config)

        except Exception as e:
            raise Exception(f"Service deployment failed: {str(e)}")

    async def _deploy_individual_containers(self, config: DeploymentConfig):
        """Deploy services as individual containers"""
        # This would contain logic to deploy each service individually
        # For now, we'll just log the intent
        for service in config.services:
            logger.info(f"Would deploy service: {service}")
            # Actual deployment logic would go here

    async def _run_health_checks(
        self, config: DeploymentConfig
    ) -> List[HealthCheckResult]:
        """Run comprehensive health checks on all services"""
        logger.info("Running health checks...")

        health_results = []
        start_time = time.time()

        while (time.time() - start_time) < config.health_check_timeout:
            all_healthy = True

            for service, endpoint in config.health_check_endpoints.items():
                result = await self._check_service_health(service, endpoint)
                health_results.append(result)

                if result.status != HealthStatus.HEALTHY:
                    all_healthy = False
                    logger.warning(f"Service {service} is unhealthy: {result.error}")

            if all_healthy:
                logger.info("All health checks passed")
                break

            # Wait before next health check round
            await asyncio.sleep(config.health_check_interval)
        else:
            logger.error("Health checks timed out")

        return health_results

    async def _check_service_health(
        self, service: str, endpoint: str
    ) -> HealthCheckResult:
        """Check health of a single service"""
        start_time = time.time()

        try:
            response = requests.get(endpoint, timeout=10)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                status = HealthStatus.HEALTHY
                error = None
            else:
                status = HealthStatus.UNHEALTHY
                error = f"HTTP {response.status_code}"

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.UNHEALTHY
            error = str(e)

        return HealthCheckResult(
            service=service,
            status=status,
            response_time_ms=response_time,
            error=error,
            timestamp=datetime.now(),
        )

    def _is_deployment_successful(
        self, health_results: List[HealthCheckResult]
    ) -> bool:
        """Determine if deployment was successful based on health checks"""
        critical_services = ["backend-api", "frontend-nextjs", "database"]

        critical_health = [
            result
            for result in health_results
            if result.service in critical_services
            and result.status == HealthStatus.HEALTHY
        ]

        return len(critical_health) == len(critical_services)

    async def _rollback_deployment(self, config: DeploymentConfig):
        """Rollback to previous deployment version"""
        if not config.rollback_enabled:
            logger.info("Rollback disabled, skipping")
            return

        logger.info("Initiating rollback...")

        try:
            # Stop current deployment
            await self._stop_existing_services(config)

            # Start previous version (implementation depends on your rollback strategy)
            await self._start_previous_version(config)

            # Verify rollback success
            health_results = await self._run_health_checks(config)

            if self._is_deployment_successful(health_results):
                logger.info("Rollback completed successfully")
            else:
                raise Exception("Rollback health checks failed")

        except Exception as e:
            raise Exception(f"Rollback failed: {str(e)}")

    async def _start_previous_version(self, config: DeploymentConfig):
        """Start previous version of services"""
        # Implementation would depend on your specific rollback strategy
        # This could involve starting previous Docker images, restoring backups, etc.
        logger.info("Starting previous version...")

        # For now, we'll just restart the existing services
        compose_file = "docker-compose.production.yml"

        if os.path.exists(compose_file):
            subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                capture_output=True,
                text=True,
            )

    async def _cleanup_deployment_resources(self):
        """Clean up temporary deployment resources"""
        logger.info("Cleaning up deployment resources...")

        try:
            # Remove unused Docker images
            subprocess.run(["docker", "image", "prune", "-f"], capture_output=True)

            # Remove unused containers
            subprocess.run(["docker", "container", "prune", "-f"], capture_output=True)

            logger.info("Deployment resources cleaned up")

        except Exception as e:
            logger.warning(f"Cleanup failed: {str(e)}")

    def _generate_deployment_id(self) -> str:
        """Generate a unique deployment ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"deploy-{timestamp}"

    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentResult]:
        """Get status of a specific deployment"""
        for deployment in self.deployment_history:
            if deployment.deployment_id == deployment_id:
                return deployment
        return None

    def get_deployment_history(self, limit: int = 10) -> List[DeploymentResult]:
        """Get recent deployment history"""
        return self.deployment_history[-limit:]

    async def monitor_health_continuously(self, config: DeploymentConfig):
        """Continuously monitor service health"""
        logger.info("Starting continuous health monitoring...")

        while True:
            try:
                health_results = await self._run_health_checks(config)

                # Log any unhealthy services
                unhealthy_services = [
                    result
                    for result in health_results
                    if result.status != HealthStatus.HEALTHY
                ]

                if unhealthy_services:
                    logger.warning(
                        f"Unhealthy services detected: {[s.service for s in unhealthy_services]}"
                    )

                # Wait before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Health monitoring error: {str(e)}")
                await asyncio.sleep(30)  # Wait 30 seconds before retrying


class MetricsCollector:
    """Collect and report deployment metrics"""

    def __init__(self):
        self.metrics = {}

    def record_deployment_metric(self, deployment_id: str, metric: str, value: Any):
        """Record a deployment metric"""
        if deployment_id not in self.metrics:
            self.metrics[deployment_id] = {}

        self.metrics[deployment_id][metric] = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }

    def get_deployment_metrics(self, deployment_id: str) -> Dict[str, Any]:
        """Get metrics for a specific deployment"""
        return self.metrics.get(deployment_id, {})

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "network_io": psutil.net_io_counters()._asdict(),
            "timestamp": datetime.now().isoformat(),
        }


# Utility functions for common deployment tasks
async def create_production_deployment(
    environment: str = "production",
) -> Dict[str, Any]:
    """Create a production deployment with the specified environment"""
    deployment_manager = ProductionDeploymentManager()

    # Create deployment configuration
    deployment_config = DeploymentConfig(
        name="atom-platform",
        version="1.0.0",
        environment=environment,
        services=[
            "backend-api",
            "frontend-nextjs",
            "database",
            "redis",
            "lancedb",
            "nginx",
        ],
        health_check_endpoints={
            "backend-api": "http://localhost:5058/health",
            "frontend-nextjs": "http://localhost:3000/api/health",
            "database": "http://localhost:5432/health",
            "redis": "http://localhost:6379/health",
            "lancedb": "http://localhost:8080/health",
        },
    )

    # Execute deployment
    deployment_result = await deployment_manager.deploy(deployment_config)

    return {
        "deployment_id": deployment_result.deployment_id,
        "status": deployment_result.status.value,
        "services_deployed": deployment_result.services_deployed,
        "health_check_results": [
            {
                "service": result.service,
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "error": result.error,
            }
            for result in deployment_result.health_check_results
        ],
        "start_time": deployment_result.start_time.isoformat(),
        "end_time": deployment_result.end_time.isoformat()
        if deployment_result.end_time
        else None,
        "error": deployment_result.error,
    }
