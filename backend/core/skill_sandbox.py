"""
HazardSandbox - Isolated Docker container execution for untrusted Python skill code.

This module provides defense-in-depth security for community skill execution.
Even if a malicious skill passes LLM security scanning, sandbox isolation
prevents system damage.

Security constraints:
- Network access disabled (network_disabled=True)
- Read-only filesystem (read_only=True)
- Resource limits (memory, CPU)
- No privileged mode
- No Docker socket mount
- Ephemeral containers (auto_remove=True)

Reference: Phase 14 RESEARCH.md Pattern 3 "Docker Sandbox with Resource Limits"
"""

import docker
import uuid
import logging
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class HazardSandbox:
    """
    Isolated Docker container for safe skill execution.

    Executes untrusted Python code in ephemeral containers with:
    - Memory limits (default 256m)
    - CPU quotas (default 0.5 cores)
    - Network isolation (no outbound/inbound)
    - Read-only filesystem
    - Temporary storage via tmpfs
    - Automatic cleanup after execution

    Example:
        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print('Hello from sandbox')",
            inputs={},
            timeout_seconds=30,
            memory_limit="256m",
            cpu_limit=0.5,
            image="python:3.11-slim"  # Optional custom image
        )
    """

    def __init__(self):
        """Initialize Docker client from environment."""
        try:
            self.client = docker.from_env()
            self._validate_docker_available()
        except Exception as e:
            msg = f"Failed to initialize Docker client: {e}. "
            msg += "Ensure Docker daemon is running: 'docker version'"
            raise RuntimeError(msg) from e

    def _validate_docker_available(self) -> None:
        """Check if Docker daemon is running and accessible."""
        try:
            self.client.ping()
        except Exception as e:
            # Check if it's a DockerException (daemon not running)
            error_type = type(e).__name__
            if error_type == 'DockerException' or 'docker' in error_type.lower():
                msg = "Docker daemon is not running or not accessible. "
                msg += "Start Docker with: 'docker start' or Docker Desktop"
                raise RuntimeError(msg) from e
            else:
                raise

    def execute_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: int = 30,
        memory_limit: str = "256m",
        cpu_limit: float = 0.5,
        image: Optional[str] = None
    ) -> str:
        """
        Execute Python code in isolated Docker container.

        Args:
            code: Python code to execute
            inputs: Input variables to inject into execution context
            timeout_seconds: Maximum execution time (default: 30s)
            memory_limit: Memory limit (e.g., "256m", "512m")
            cpu_limit: CPU quota (0.5 = 50% of one core)
            image: Custom Docker image (default: "python:3.11-slim")

        Returns:
            str: Execution output (stdout) or error message

        Raises:
            RuntimeError: If Docker is not available
            ValueError: If code execution fails

        Security constraints (per RESEARCH.md Pitfall 3):
        - NEVER mount /var/run/docker.sock
        - NEVER use --privileged mode
        - Always use network_disabled=True
        - Always use read_only=True
        - Limit resources with mem_limit and cpu_quota
        """
        container_id = f"skill_{uuid.uuid4().hex[:8]}"

        # Use custom image or default base image
        container_image = image if image else "python:3.11-slim"

        try:
            # Create wrapper script that injects inputs and executes code
            wrapper_script = self._create_wrapper_script(code, inputs)

            logger.info(f"Starting container {container_id} with limits: "
                       f"mem={memory_limit}, cpu={cpu_limit}, timeout={timeout_seconds}s, "
                       f"image={container_image}")

            # Run container with security constraints
            output = self.client.containers.run(
                image=container_image,
                command=["python", "-c", wrapper_script],
                name=container_id,
                mem_limit=memory_limit,
                cpu_quota=int(cpu_limit * 100000),  # Docker uses 100000 as base
                cpu_period=100000,
                network_disabled=True,  # CRITICAL: No network access
                read_only=True,  # CRITICAL: Read-only filesystem
                tmpfs={"/tmp": "size=10m"},  # Temporary storage only
                auto_remove=True,  # Ephemeral container
                stdout=True,
                stderr=True,
                timeout=timeout_seconds
            )

            result = output.decode("utf-8")
            logger.info(f"Container {container_id} completed successfully")

            return result

        except Exception as e:
            error_type = type(e).__name__

            if error_type == 'ContainerError':
                # ContainerError has stderr attribute
                stderr_msg = e.stderr.decode('utf-8') if hasattr(e, 'stderr') and e.stderr else str(e)
                error_msg = f"Container execution failed: {stderr_msg}"
                logger.error(f"Container {container_id} error: {error_msg}")
                return f"EXECUTION_ERROR: {error_msg}"

            elif error_type == 'APIError':
                error_msg = f"Docker API error: {str(e)}"
                logger.error(f"Container {container_id} API error: {error_msg}")
                return f"DOCKER_ERROR: {error_msg}"

            else:
                error_msg = f"Sandbox execution failed: {str(e)}"
                logger.error(f"Container {container_id} unexpected error: {error_msg}")
                return f"SANDBOX_ERROR: {error_msg}"

    def execute_nodejs(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: int = 30,
        memory_limit: str = "256m",
        cpu_limit: float = 0.5,
        image: Optional[str] = None
    ) -> str:
        """
        Execute Node.js code in isolated Docker container.

        Args:
            code: Node.js code to execute
            inputs: Input variables to inject into execution context
            timeout_seconds: Maximum execution time (default: 30s)
            memory_limit: Memory limit (e.g., "256m", "512m")
            cpu_limit: CPU quota (0.5 = 50% of one core)
            image: Custom Docker image (default: "node:20-alpine")

        Returns:
            str: Execution output (stdout) or error message

        Raises:
            RuntimeError: If Docker is not available
            ValueError: If code execution fails

        Security constraints (per RESEARCH.md Pitfall 4):
        - NEVER mount /var/run/docker.sock
        - NEVER use --privileged mode
        - Always use network_disabled=True
        - Always use read_only=True
        - Limit resources with mem_limit and cpu_quota
        """
        container_id = f"skill_{uuid.uuid4().hex[:8]}"

        # Use custom image or default base image
        container_image = image if image else "node:20-alpine"

        try:
            # Create wrapper script that injects inputs and executes code
            wrapper_script = self._create_nodejs_wrapper(code, inputs)

            logger.info(f"Starting Node.js container {container_id} with limits: "
                       f"mem={memory_limit}, cpu={cpu_limit}, timeout={timeout_seconds}s, "
                       f"image={container_image}")

            # Run container with security constraints
            output = self.client.containers.run(
                image=container_image,
                command=["node", "-e", wrapper_script],
                name=container_id,
                mem_limit=memory_limit,
                cpu_quota=int(cpu_limit * 100000),  # Docker uses 100000 as base
                cpu_period=100000,
                network_disabled=True,  # CRITICAL: No network access
                read_only=True,  # CRITICAL: Read-only filesystem
                tmpfs={"/tmp": "size=10m"},  # Temporary storage only
                auto_remove=True,  # Ephemeral container
                stdout=True,
                stderr=True,
                timeout=timeout_seconds
            )

            result = output.decode("utf-8")
            logger.info(f"Node.js container {container_id} completed successfully")

            return result

        except Exception as e:
            error_type = type(e).__name__

            if error_type == 'ContainerError':
                # ContainerError has stderr attribute
                stderr_msg = e.stderr.decode('utf-8') if hasattr(e, 'stderr') and e.stderr else str(e)
                error_msg = f"Container execution failed: {stderr_msg}"
                logger.error(f"Node.js container {container_id} error: {error_msg}")
                return f"EXECUTION_ERROR: {error_msg}"

            elif error_type == 'APIError':
                error_msg = f"Docker API error: {str(e)}"
                logger.error(f"Node.js container {container_id} API error: {error_msg}")
                return f"DOCKER_ERROR: {error_msg}"

            else:
                error_msg = f"Sandbox execution failed: {str(e)}"
                logger.error(f"Node.js container {container_id} unexpected error: {error_msg}")
                return f"SANDBOX_ERROR: {error_msg}"

    def _create_wrapper_script(self, code: str, inputs: Dict[str, Any]) -> str:
        """
        Create wrapper script that injects inputs and executes skill code.

        Args:
            code: Python code to execute
            inputs: Input variables to inject

        Returns:
            str: Complete wrapper script
        """
        return f"""
import sys
import json

# Inject inputs into global scope
inputs = {json.dumps(inputs)}
globals().update(inputs)

# Execute skill code
try:
{code}
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""

    def _create_nodejs_wrapper(self, code: str, inputs: Dict[str, Any]) -> str:
        """
        Create Node.js wrapper script that injects inputs and executes code.

        Args:
            code: Node.js code to execute
            inputs: Input variables to inject

        Returns:
            str: Complete wrapper script
        """
        # Convert inputs to JavaScript object
        inputs_json = json.dumps(inputs)

        wrapper = f"""
// Inject inputs
const inputs = {inputs_json};

// User code
{code}

"""
        return wrapper

    def cleanup_container(self, container_id: str) -> bool:
        """
        Manually cleanup a container if needed (rare - auto_remove=True).

        Use this only if auto_remove failed or container is stuck.

        Args:
            container_id: Container name or ID

        Returns:
            bool: True if cleanup successful
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            logger.info(f"Manually cleaned up container {container_id}")
            return True
        except Exception as e:
            error_type = type(e).__name__

            if error_type == 'NotFound':
                logger.warning(f"Container {container_id} not found (already removed)")
                return False
            else:
                logger.error(f"Failed to cleanup container {container_id}: {e}")
                return False


def test_sandbox_basic():
    """Basic smoke test to verify sandbox functionality."""
    try:
        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print('Sandbox test passed')",
            inputs={},
            timeout_seconds=5
        )
        assert "Sandbox test passed" in result
        print("✓ HazardSandbox basic test passed")
        return True
    except Exception as e:
        print(f"✗ HazardSandbox test failed: {e}")
        return False


if __name__ == "__main__":
    # Run basic test when module executed directly
    test_sandbox_basic()
