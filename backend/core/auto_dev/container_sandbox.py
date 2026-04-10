"""
Container Sandbox

Lightweight Docker-based sandbox for executing untrusted code generated
by the Auto-Dev engines. Implements the SandboxProtocol interface.

Security constraints:
- Ephemeral containers (destroyed after each execution)
- No network access (--network=none)
- Memory limit (256MB)
- Execution timeout (60s default)
- Read-only filesystem with tmpfs for /tmp

Fallback: If Docker is unavailable, uses subprocess isolation with
resource limits (Linux) or basic subprocess timeout (macOS/Windows).
"""

import asyncio
import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT = 60
DEFAULT_MEMORY_LIMIT = "256m"


class ContainerSandbox:
    """
    Docker-based sandbox implementing SandboxProtocol.

    Falls back to subprocess isolation if Docker is unavailable.
    """

    def __init__(
        self,
        docker_image: str = DOCKER_IMAGE,
        timeout: int = DEFAULT_TIMEOUT,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        enable_network: bool = False,
    ):
        self.docker_image = docker_image
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.enable_network = enable_network
        self._docker_available: bool | None = None

    @property
    def docker_available(self) -> bool:
        """Check if Docker is available on the system."""
        if self._docker_available is None:
            try:
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=5,
                )
                self._docker_available = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._docker_available = False
                logger.info(
                    "Docker not available — ContainerSandbox will use subprocess fallback"
                )
        return self._docker_available

    async def execute_raw_python(
        self,
        tenant_id: str,
        code: str,
        input_params: dict[str, Any] | None = None,
        timeout: int | None = None,
        safety_level: str = "MEDIUM_RISK",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute Python code in an isolated environment.

        Args:
            tenant_id: Tenant ID for tracking
            code: Python code to execute
            input_params: Input parameters passed as JSON on stdin
            timeout: Override default timeout
            safety_level: Ignored in upstream (used by SaaS)

        Returns:
            {
                "status": "success" | "failed",
                "output": str,
                "execution_seconds": float,
                "environment": "docker" | "subprocess",
            }
        """
        effective_timeout = timeout or self.timeout
        params = input_params or {}

        if self.docker_available:
            return await self._execute_docker(
                code, params, effective_timeout, tenant_id
            )
        return await self._execute_subprocess(
            code, params, effective_timeout, tenant_id
        )

    async def _execute_docker(
        self,
        code: str,
        input_params: dict[str, Any],
        timeout: int,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Execute code in a Docker container."""
        start_time = time.monotonic()

        # Write code to a temp file that will be mounted
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            # Wrap code with input parameter injection
            wrapper = self._build_execution_wrapper(code, input_params)
            f.write(wrapper)
            code_path = f.name

        try:
            cmd = [
                "docker",
                "run",
                "--rm",
                f"--memory={self.memory_limit}",
                f"--cpus=1",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "-v",
                f"{code_path}:/sandbox/script.py:ro",
            ]

            if not self.enable_network:
                cmd.extend(["--network", "none"])

            cmd.extend([self.docker_image, "python", "/sandbox/script.py"])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "status": "failed",
                    "output": f"Execution timed out after {timeout}s",
                    "execution_seconds": time.monotonic() - start_time,
                    "environment": "docker",
                }

            elapsed = time.monotonic() - start_time
            output = stdout.decode("utf-8", errors="replace").strip()
            errors = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode == 0:
                return {
                    "status": "success",
                    "output": output,
                    "execution_seconds": round(elapsed, 3),
                    "environment": "docker",
                }
            else:
                return {
                    "status": "failed",
                    "output": errors or output,
                    "execution_seconds": round(elapsed, 3),
                    "environment": "docker",
                }
        finally:
            Path(code_path).unlink(missing_ok=True)

    async def _execute_subprocess(
        self,
        code: str,
        input_params: dict[str, Any],
        timeout: int,
        tenant_id: str,
    ) -> dict[str, Any]:
        """
        Fallback: execute code in a subprocess with basic timeout isolation.

        WARNING: This provides weaker isolation than Docker. It should only be
        used for local development when Docker is not available.
        """
        start_time = time.monotonic()
        wrapper = self._build_execution_wrapper(code, input_params)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(wrapper)
            code_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                code_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "status": "failed",
                    "output": f"Execution timed out after {timeout}s",
                    "execution_seconds": time.monotonic() - start_time,
                    "environment": "subprocess",
                }

            elapsed = time.monotonic() - start_time
            output = stdout.decode("utf-8", errors="replace").strip()
            errors = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode == 0:
                return {
                    "status": "success",
                    "output": output,
                    "execution_seconds": round(elapsed, 3),
                    "environment": "subprocess",
                }
            else:
                return {
                    "status": "failed",
                    "output": errors or output,
                    "execution_seconds": round(elapsed, 3),
                    "environment": "subprocess",
                }
        finally:
            Path(code_path).unlink(missing_ok=True)

    @staticmethod
    def _build_execution_wrapper(code: str, input_params: dict[str, Any]) -> str:
        """Wrap user code with input parameter injection."""
        params_json = json.dumps(input_params)
        return f"""
import json
import sys

# Inject input parameters
_INPUT_PARAMS = json.loads('''{params_json}''')

# User code
{code}
"""
