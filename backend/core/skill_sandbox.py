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
- Ephemeral containers (created, run and removed by this module)

Container lifecycle (why it is explicit): ``containers.run`` blocks until the
container exits and does not hand back a handle until then, so a wall-clock
deadline has to be enforced from another thread and the cleanup path is forced
to look the container up by name.  A container that starts after that lookup is
then outside the deadline and can outlive it.  This module instead performs
image preparation, container creation, execution (``wait(timeout=...)``) and
removal as distinct steps on a container object it already owns, so the
deadline and every cleanup path act on the exact container that was created.

Reference: Phase 14 RESEARCH.md Pattern 3 "Docker Sandbox with Resource Limits"
"""

import docker
import uuid
import logging
import json
import time
from typing import Dict, Any, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class SandboxTimeoutError(RuntimeError):
    """A sandbox container outlived its wall-clock budget.

    ``termination`` records what cleanup actually observed (``killed``,
    ``removed``, ``cleanup_error``) so callers never report a kill that did
    not happen.
    """

    def __init__(self, message: str, *, container_id: str,
                 termination: Dict[str, Any]):
        super().__init__(message)
        self.container_id = container_id
        self.termination = termination


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

    # ------------------------------------------------------------------
    # Container lifecycle: image preparation -> creation -> execution ->
    # removal.  Ownership is deterministic because the container exists (and
    # its id is known) before it is started.
    # ------------------------------------------------------------------
    def _prepare_image(self, image: str) -> None:
        """Resolve the image BEFORE any container is created.

        Pulling stays the caller's responsibility (the hosted job pulls the
        base image explicitly).  Resolving it here fails early on a missing
        image and keeps image preparation out of the execution budget, so it
        cannot race with the deadline.
        """
        self.client.images.get(image)

    def _create_container(
        self,
        *,
        container_image: str,
        command: list,
        container_id: str,
        memory_limit: str,
        cpu_limit: float,
    ):
        """Create (do not start) the ephemeral sandbox container.

        Only documented ``containers.create`` kwargs are used: the model-level
        wrapper rejects anything else with a ``TypeError`` before a container
        exists (that is exactly what ``timeout=`` did on ``containers.run`` and
        why real Docker executions used to fail closed as ``SANDBOX_ERROR``).

        ``auto_remove`` is deliberately False.  Docker-side auto-removal races
        ``wait()``/``logs()`` for short-lived containers (the daemon may delete
        the container before the client reads its exit status), which would
        turn a successful benign computation into a spurious failure.  The
        sandbox removes the container itself and records the observed outcome.
        """
        return self.client.containers.create(
            image=container_image,
            command=command,
            name=container_id,
            mem_limit=memory_limit,
            cpu_quota=int(cpu_limit * 100000),  # Docker uses 100000 as base
            cpu_period=100000,
            network_disabled=True,  # CRITICAL: No network access
            read_only=True,  # CRITICAL: Read-only filesystem
            tmpfs={"/tmp": "size=10m"},  # Temporary storage only
            auto_remove=False,  # removal is owned and reported below
        )

    def _execute_container(
        self, container, *, timeout_seconds: int
    ) -> Tuple[int, str, str]:
        """Start the owned container, wait under a deadline, return its output.

        The deadline starts before ``start()``, so a slow image/start phase
        cannot postpone it, and it is applied to the same container object
        that was created -- there is no lookup-by-name and no window in which
        a container could start after cleanup looked for it.
        """
        deadline = (
            time.monotonic() + timeout_seconds
            if timeout_seconds and timeout_seconds > 0 else None)
        container.start()
        remaining = (
            None if deadline is None else deadline - time.monotonic())
        if remaining is not None and remaining <= 0:
            raise self._timeout_error(container, timeout_seconds)
        try:
            wait_result = (
                container.wait() if remaining is None
                else container.wait(timeout=remaining))
        except requests.exceptions.ReadTimeout:
            raise self._timeout_error(container, timeout_seconds) from None
        if deadline is not None and time.monotonic() > deadline:
            # docker-py adds one second of HTTP slack to ``wait(timeout=...)``;
            # the wall-clock budget is authoritative, not the HTTP socket.
            raise self._timeout_error(container, timeout_seconds)
        exit_code = int((wait_result or {}).get("StatusCode", -1))
        stdout = self._decode_output(
            container.logs(stdout=True, stderr=False))
        stderr = self._decode_output(
            container.logs(stdout=False, stderr=True))
        return exit_code, stdout, stderr

    @staticmethod
    def _decode_output(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _timeout_error(self, container, timeout_seconds: int):
        """Kill the over-budget container and describe what actually happened."""
        termination = self._terminate_container(container)
        container_id = str(getattr(container, "name", "") or "")
        if termination["killed"] and termination["removed"]:
            detail = "was killed and removed"
        elif termination["killed"]:
            detail = "was killed but could not be removed"
        elif termination["removed"]:
            detail = "was force-removed"
        else:
            detail = "could NOT be terminated"
        message = (
            "SANDBOX_ERROR: Sandbox execution timed out after "
            f"{timeout_seconds}s; container {container_id} {detail}")
        if termination.get("cleanup_error"):
            message += f" ({termination['cleanup_error']})"
        termination["disposed"] = True
        return SandboxTimeoutError(
            message, container_id=container_id, termination=termination)

    def _terminate_container(self, container) -> Dict[str, Any]:
        """Kill and remove ``container``, reporting the observed outcome.

        ``killed``/``removed`` are True only when the corresponding Docker call
        returned without error (or the container was already gone), so a
        timeout receipt can never claim a termination that failed.
        """
        container_id = str(getattr(container, "name", "") or "")
        outcome: Dict[str, Any] = {
            "killed": False, "removed": False, "cleanup_error": None}
        errors = []
        try:
            container.kill()
            outcome["killed"] = True
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            if type(exc).__name__ == "NotFound":
                # Already gone: nothing is left to kill.
                outcome["removed"] = True
            else:
                errors.append(f"kill failed ({type(exc).__name__}): {exc}")
        if not outcome["removed"]:
            removal = self._remove_container(container)
            outcome["removed"] = removal["removed"]
            if removal["cleanup_error"]:
                errors.append(removal["cleanup_error"])
        if outcome["killed"]:
            logger.warning(
                "Container %s exceeded its timeout and was killed",
                container_id)
        if errors:
            outcome["cleanup_error"] = "; ".join(errors)
            logger.error(
                "Failed to terminate timed-out container %s: %s",
                container_id, outcome["cleanup_error"])
        return outcome

    def _remove_container(self, container) -> Dict[str, Any]:
        """Force-remove ``container``; True only when it is really gone."""
        outcome: Dict[str, Any] = {"removed": False, "cleanup_error": None}
        try:
            container.remove(force=True)
            outcome["removed"] = True
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            if type(exc).__name__ == "NotFound":
                outcome["removed"] = True
                return outcome
            outcome["cleanup_error"] = (
                f"remove failed ({type(exc).__name__}): {exc}")
            logger.error(
                "Failed to remove sandbox container %s: %s",
                str(getattr(container, "name", "") or ""),
                outcome["cleanup_error"])
        return outcome

    def _run_owned_container(
        self,
        *,
        receipt: Dict[str, Any],
        container_image: str,
        command: list,
        container_id: str,
        memory_limit: str,
        cpu_limit: float,
        timeout_seconds: int,
    ) -> Tuple[int, str, str]:
        """Run one container and always dispose of it.

        ``receipt`` is updated in place (``removed``/``ephemeral``/
        ``cleanup_error``/timeout fields) even when execution raises, so the
        truth about cleanup survives every error path.
        """
        container = None
        container_disposed = False
        try:
            self._prepare_image(container_image)
            container = self._create_container(
                container_image=container_image,
                command=command,
                container_id=container_id,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
            )
            receipt["docker_container_id"] = str(
                getattr(container, "id", "") or "")
            return self._execute_container(
                container, timeout_seconds=timeout_seconds)
        except SandboxTimeoutError as exc:
            container_disposed = bool(exc.termination.get("disposed"))
            receipt.update({
                "timed_out": True,
                "killed": bool(exc.termination.get("killed")),
                "terminated": bool(
                    exc.termination.get("killed")
                    or exc.termination.get("removed")),
                "removed": bool(exc.termination.get("removed")),
                "cleanup_error": exc.termination.get("cleanup_error"),
            })
            raise
        finally:
            if container is not None and not container_disposed:
                removal = self._remove_container(container)
                receipt["removed"] = removal["removed"]
                if removal["cleanup_error"]:
                    receipt["cleanup_error"] = removal["cleanup_error"]
            # ``ephemeral`` is a claim about the world: only true when the
            # container is confirmed gone.
            receipt["ephemeral"] = bool(receipt.get("removed"))

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
        receipt = self._run_python_container(
            code=code,
            inputs=inputs,
            timeout_seconds=timeout_seconds,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            image=image,
        )
        if receipt.get("ok"):
            return str(receipt.get("stdout") or "")
        return str(
            receipt.get("error")
            or "SANDBOX_ERROR: Sandbox execution failed")

    def execute_python_receipt(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: int = 30,
        memory_limit: str = "256m",
        cpu_limit: float = 0.5,
        image: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Python code and return the container receipt.

        Used by the reviewed-executable path, which must prove that the code
        actually ran in a fresh ``skill_*`` container (not on the host) and
        must persist a durable execution receipt.  The returned dict contains
        ``ok``, ``stdout``/``stderr``, ``exit_code``, ``container_id``,
        ``image``, backend/security flags, ``timed_out``/``killed``/
        ``terminated``/``cleanup_error`` (the observed cleanup truth),
        ``ephemeral``/``removed`` and the optional nonce the container was
        started with.
        """
        return self._run_python_container(
            code=code,
            inputs=inputs,
            timeout_seconds=timeout_seconds,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            image=image,
            nonce=nonce,
        )

    def _run_python_container(
        self,
        *,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: int,
        memory_limit: str,
        cpu_limit: float,
        image: Optional[str],
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        container_id = f"skill_{uuid.uuid4().hex[:8]}"

        # Use custom image or default base image
        container_image = image if image else "python:3.11-slim"
        receipt: Dict[str, Any] = {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "container_id": container_id,
            "docker_container_id": None,
            "image": container_image,
            "backend": "docker",
            "network_disabled": True,
            "read_only": True,
            "ephemeral": False,  # set from the observed removal below
            "removed": False,
            "timed_out": False,
            "killed": False,
            "terminated": False,
            "cleanup_error": None,
            "timeout_seconds": timeout_seconds,
            "nonce": nonce,
        }

        try:
            # Create wrapper script that injects inputs and executes code
            wrapper_script = self._create_wrapper_script(
                code, inputs, nonce=nonce)

            logger.info(f"Starting container {container_id} with limits: "
                       f"mem={memory_limit}, cpu={cpu_limit}, timeout={timeout_seconds}s, "
                       f"image={container_image}")

            exit_code, stdout, stderr = self._run_owned_container(
                receipt=receipt,
                container_image=container_image,
                command=["python", "-c", wrapper_script],
                container_id=container_id,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                timeout_seconds=timeout_seconds,
            )
            receipt.update({
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            })
            if exit_code != 0:
                # Same contract as the old ContainerError branch: a non-zero
                # exit is an execution failure, not a successful receipt.
                error_msg = (
                    "EXECUTION_ERROR: Container execution failed: "
                    + (stderr or stdout or f"exit code {exit_code}"))
                logger.error(
                    f"Container {container_id} error: {error_msg}")
                receipt.update({"ok": False, "error": error_msg})
                return receipt

            receipt.update({"ok": True})
            logger.info(f"Container {container_id} completed successfully")

            return receipt

        except SandboxTimeoutError as exc:
            # ``exc`` already describes the observed cleanup truthfully (it
            # only says "was killed" when the kill actually returned).
            logger.error(str(exc))
            error_msg = str(exc)
            receipt.update({
                "ok": False,
                "timed_out": True,
                "stderr": error_msg,
                "error": error_msg,
                # Same convention as GNU timeout(1).
                "exit_code": 124,
            })
            return receipt

        except Exception as e:
            error_type = type(e).__name__

            if error_type == 'ContainerError':
                # ContainerError has stderr attribute
                stderr_msg = e.stderr.decode('utf-8') if hasattr(e, 'stderr') and e.stderr else str(e)
                error_msg = f"EXECUTION_ERROR: Container execution failed: {stderr_msg}"
                logger.error(f"Container {container_id} error: {error_msg}")
            elif error_type == 'APIError':
                stderr_msg = str(e)
                error_msg = f"DOCKER_ERROR: Docker API error: {str(e)}"
                logger.error(f"Container {container_id} API error: {error_msg}")
            else:
                stderr_msg = str(e)
                error_msg = (
                    f"SANDBOX_ERROR: Sandbox execution failed ({error_type}): "
                    f"{str(e)}")
                logger.error(f"Container {container_id} unexpected error: {error_msg}")

            receipt.update({
                "ok": False,
                "stderr": stderr_msg,
                "error": error_msg,
                "exit_code": int(getattr(e, "exit_code", -1) or -1),
            })
            return receipt

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
        lifecycle: Dict[str, Any] = {
            "removed": False,
            "ephemeral": False,
            "timed_out": False,
            "cleanup_error": None,
        }

        try:
            # Create wrapper script that injects inputs and executes code
            wrapper_script = self._create_nodejs_wrapper(code, inputs)

            logger.info(f"Starting Node.js container {container_id} with limits: "
                       f"mem={memory_limit}, cpu={cpu_limit}, timeout={timeout_seconds}s, "
                       f"image={container_image}")

            exit_code, stdout, stderr = self._run_owned_container(
                receipt=lifecycle,
                container_image=container_image,
                command=["node", "-e", wrapper_script],
                container_id=container_id,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                timeout_seconds=timeout_seconds,
            )
            if exit_code != 0:
                error_msg = (
                    "EXECUTION_ERROR: Container execution failed: "
                    + (stderr or stdout or f"exit code {exit_code}"))
                logger.error(
                    f"Node.js container {container_id} error: {error_msg}")
                return error_msg

            logger.info(f"Node.js container {container_id} completed successfully")

            return stdout

        except SandboxTimeoutError as exc:
            # Truthful: the message only says "was killed" when it happened.
            logger.error(str(exc))
            return str(exc)

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
                error_msg = (
                    f"Sandbox execution failed ({error_type}): {str(e)}")
                logger.error(f"Node.js container {container_id} unexpected error: {error_msg}")
                return f"SANDBOX_ERROR: {error_msg}"

    def _create_wrapper_script(
        self,
        code: str,
        inputs: Dict[str, Any],
        nonce: Optional[str] = None,
    ) -> str:
        """
        Create wrapper script that injects inputs and executes skill code.

        Args:
            code: Python code to execute
            inputs: Input variables to inject
            nonce: Optional per-execution value exposed as
                ``__atom_sandbox_nonce__``; the reviewed-executable harness
                echoes it so the caller can prove this exact container ran.

        Returns:
            str: Complete wrapper script
        """
        nonce_line = ""
        if nonce is not None:
            nonce_line = (
                "\n__atom_sandbox_nonce__ = "
                f"{json.dumps(str(nonce))}\n")
        return f"""
import sys
import json

# Inject inputs into global scope
inputs = {json.dumps(inputs)}
globals().update(inputs)
{nonce_line}
# Compile the reviewed source instead of splicing it into this try block:
# splicing would require every reviewed line to be pre-indented and silently
# broke multi-line skills.  The source is a Python string here, never a
# command line, so it is evaluated by exec inside the same isolated process.
_atom_skill_source = {repr(str(code))}
try:
    exec(compile(_atom_skill_source, "<atom-skill>", "exec"), globals())
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
