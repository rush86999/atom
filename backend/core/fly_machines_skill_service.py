"""
Fly.io Machines Skill Execution Service

Executes skills using Fly.io Machines API instead of local Docker.
This enables secure, isolated execution with cost tracking for tenant billing.
"""

import logging
import json
import time
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import Tenant, SkillExecution

logger = logging.getLogger(__name__)


class FlyMachinesClient:
    """Client for Fly.io Machines API"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("FLY_API_TOKEN")
        self.api_base = "https://api.machines.dev/v1"

        if not self.api_token:
            logger.warning("FLY_API_TOKEN not set - Fly Machines skills will not work")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def create_machine(
        self,
        app_name: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new Fly.io Machine"""
        import httpx

        url = f"{self.api_base}/apps/{app_name}/machines"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
                json=config
            )
            response.raise_for_status()
            return response.json()

    async def get_machine(
        self,
        app_name: str,
        machine_id: str
    ) -> Dict[str, Any]:
        """Get machine status"""
        import httpx

        url = f"{self.api_base}/apps/{app_name}/machines/{machine_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

    async def wait_for_machine(
        self,
        app_name: str,
        machine_id: str,
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """Wait for machine to complete execution"""
        import httpx
        import asyncio

        start_time = time.time()
        url = f"{self.api_base}/apps/{app_name}/machines/{machine_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            while time.time() - start_time < timeout_seconds:
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

                state = data.get("state", "")
                if state in ["succeeded", "failed", "destroyed"]:
                    return data

                # Wait before polling again
                await asyncio.sleep(2)

            raise TimeoutError(f"Machine {machine_id} did not complete within {timeout_seconds}s")

    async def get_machine_logs(
        self,
        app_name: str,
        machine_id: str,
        max_lines: int = 1000
    ) -> str:
        """Get machine logs"""
        import httpx

        url = f"{self.api_base}/apps/{app_name}/machines/{machine_id}/logs?lines={max_lines}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()

            logs = response.json()
            # Combine log lines
            return "\n".join([log.get("message", "") for log in logs])

    async def delete_machine(
        self,
        app_name: str,
        machine_id: str
    ) -> None:
        """Delete/stop a machine"""
        import httpx

        url = f"{self.api_base}/apps/{app_name}/machines/{machine_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send stop request with force=true
            await client.post(
                f"{url}/stop",
                headers=self._get_headers(),
                json={"force": True}
            )


class FlyMachinesSkillExecutor:
    """
    Executes skills using Fly.io Machines API

    Cost calculation using Atom Compute Units (ACUs):
    - 1 ACU = 1 CPU-second of compute
    - Memory is factored in as ratio of CPU (256MB = 1 ACU multiplier)
    - Example: 1 CPU + 256MB for 60s = 60 ACUs

    This provides a simple billing abstraction for tenants.
    """

    # ACU calculation
    # Base: 1 CPU-second = 1 ACU
    # Memory: 256MB = 1x multiplier, 512MB = 2x, etc.
    ACUS_PER_CPU_SECOND = 1.0
    MEMORY_MB_PER_ACU = 256  # 256MB = 1 ACU multiplier

    def __init__(self, db: Session):
        self.db = db
        self.client = FlyMachinesClient()

    def calculate_acus(
        self,
        cpu_count: int,
        execution_seconds: float
    ) -> float:
        """
        Calculate Atom Compute Units (ACUs) for execution.

        Formula: ACUs = cpu_count × execution_seconds

        Memory is NOT factored into ACU billing for simplicity:
        - Fly.io pricing is primarily CPU-based
        - Memory is bundled with CPU tiers
        - Keeps billing transparent for tenants

        Examples:
        - 1 CPU, 60 seconds = 60 ACUs
        - 2 CPUs, 30 seconds = 60 ACUs
        - 4 CPUs, 15 seconds = 60 ACUs
        """
        return cpu_count * execution_seconds

    async def execute_skill(
        self,
        skill_id: str,
        agent_id: str,
        tenant_id: str,
        skill_config: Dict[str, Any],
        input_params: Dict[str, Any],
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Execute a skill using Fly.io Machines

        Args:
            skill_id: UUID of the skill
            agent_id: Agent executing the skill
            tenant_id: Tenant for billing
            skill_config: Skill configuration (image, command, etc.)
            input_params: Parameters to pass to the skill
            execution_id: UUID for tracking

        Returns:
            Dict with execution results and cost info
        """
        try:
            # Get tenant's Fly.io app name (each tenant could have their own app for isolation)
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            # Use a shared app for all tenants or tenant-specific app
            # For multi-tenant isolation, you might want tenant-specific apps
            app_name = os.getenv(
                "FLY_MACHINES_APP_NAME",
                "atom-saas-skills"  # Default shared app
            )

            # Allow tenant-specific override
            if tenant.metadata_json and isinstance(tenant.metadata_json, dict):
                app_name = tenant.metadata_json.get("fly_machines_app", app_name)

            # Build machine config
            image = skill_config.get("image")
            if not image:
                raise ValueError("Skill config must include 'image'")

            command = skill_config.get("command", "")
            cpu_count = skill_config.get("cpu_count", 1)
            memory_mb = skill_config.get("memory_mb", 256)

            # Prepare environment with parameters
            env_vars = {
                "SKILL_PARAMS": json.dumps(input_params),
                **{k.upper(): str(v) for k, v in input_params.items()
                   if isinstance(v, (str, int, float))}
            }

            # Machine configuration
            machine_config = {
                "config": {
                    "image": image,
                    "env": env_vars,
                    "guest": {
                        "cpu_kind": "shared" if cpu_count == 1 else "dedicated",
                        "cpus": cpu_count,
                        "memory_mb": memory_mb
                    },
                    "restart": {
                        "policy": "no"  # Don't restart
                    }
                }
            }

            if command:
                machine_config["config"]["entrypoint"] = ["/bin/sh", "-c"]
                machine_config["config"]["cmd"] = [command]

            logger.info(f"Creating Fly Machine for skill {skill_id} in app {app_name}")

            # Create the machine
            machine_data = await self.client.create_machine(app_name, machine_config)
            machine_id = machine_data.get("id")

            if not machine_id:
                raise ValueError("Failed to create machine - no ID returned")

            # Update execution record with machine_id and tenant_id
            await self._update_execution(execution_id, {
                "tenant_id": tenant_id,
                "machine_id": machine_id,
                "cpu_count": cpu_count,
                "memory_mb": memory_mb
            })

            # Wait for completion
            logger.info(f"Waiting for machine {machine_id} to complete...")
            final_state = await self.client.wait_for_machine(
                app_name,
                machine_id,
                timeout_seconds=skill_config.get("timeout", 300)
            )

            # Get execution time
            started_at = final_state.get("created_at")
            stopped_at = final_state.get("updated_at")
            execution_seconds = self._calculate_duration(started_at, stopped_at)

            # Get logs/output
            logs = await self.client.get_machine_logs(app_name, machine_id)

            # Clean up the machine
            logger.info(f"Deleting machine {machine_id}...")
            try:
                await self.client.delete_machine(app_name, machine_id)
            except Exception as e:
                logger.warning(f"Failed to delete machine {machine_id}: {e}")

            # Check if successful
            if final_state.get("state") == "succeeded":
                # Try to parse JSON output
                output = self._parse_output(logs)

                # Calculate ACUs
                acus = self.calculate_acus(cpu_count, execution_seconds)

                # Update execution record
                await self._update_execution(execution_id, {
                    "status": "completed",
                    "output_result": output,
                    "execution_seconds": execution_seconds,
                    "tenant_id": tenant_id
                })

                return {
                    "success": True,
                    "output": output,
                    "acus": acus,
                    "execution_seconds": execution_seconds,
                    "cpu_count": cpu_count,
                    "memory_mb": memory_mb,
                    "machine_id": machine_id
                }
            else:
                raise Exception(f"Machine failed with state: {final_state.get('state')}\nLogs: {logs}")

        except Exception as e:
            logger.error(f"Fly Machines execution failed: {e}")
            await self._update_execution(execution_id, {
                "status": "failed",
                "error_message": str(e)
            })
            raise

    def _calculate_duration(self, started_at: str, stopped_at: str) -> int:
        """Calculate execution duration in seconds"""
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            stop = datetime.fromisoformat(stopped_at.replace("Z", "+00:00"))
            return int((stop - start).total_seconds())
        except:
            return 0

    def _parse_output(self, logs: str) -> Any:
        """Try to parse logs as JSON, return raw string if fails"""
        logs = logs.strip()
        try:
            return json.loads(logs)
        except:
            return {"output": logs}

    async def _update_execution(self, execution_id: str, updates: Dict[str, Any]) -> None:
        """Update execution record in database using ORM"""
        execution = self.db.query(SkillExecution).filter(SkillExecution.id == execution_id).first()
        if not execution:
            logger.warning(f"Skill execution {execution_id} not found for update")
            return

        for key, value in updates.items():
            if hasattr(execution, key):
                setattr(execution, key, value)
            
        if 'status' in updates and updates['status'] in ['completed', 'failed']:
            execution.completed_at = datetime.now(timezone.utc)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update skill execution {execution_id}: {e}")


# Singleton instance
_fly_machines_executor: Optional[FlyMachinesSkillExecutor] = None


def get_fly_machines_executor() -> FlyMachinesSkillExecutor:
    """Get or create Fly Machines executor singleton"""
    global _fly_machines_executor
    if _fly_machines_executor is None:
        db = SessionLocal()
        _fly_machines_executor = FlyMachinesSkillExecutor(db)
    return _fly_machines_executor
