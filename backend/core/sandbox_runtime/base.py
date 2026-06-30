"""Execution Sandbox Layer — Phase D (Round 46).

Unified ``SandboxRuntime`` protocol — the abstraction the three existing
Docker-based sandboxes (``auto_dev/container_sandbox.py``,
``skill_sandbox.py``, ``sandbox_executor.py``) lack. Each existing
sandbox hard-codes Docker; this protocol lets Phase D plug in
Firecracker microVMs (self-hosted) or E2B (managed) without rewriting
the callers.

The protocol is intentionally minimal — three async methods. Existing
sandboxes can adopt it incrementally by delegating their existing
Docker code to a ``DockerRuntime`` adapter (Phase D ships this too as
the default fallback when neither Firecracker nor E2B is configured).

Design contract:
  * Protocol-based — runtime selection happens at call time, not
    import time. ``ATOM_SANDBOX_RUNTIME`` env var selects backend.
  * Async-first — all execution methods are coroutines. Existing
    Docker code is sync; the DockerRuntime adapter wraps it in
    ``asyncio.to_thread``.
  * No execution happens in this module — it's pure protocol.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ===========================================================================
# Execution result
# ===========================================================================
@dataclass(frozen=True)
class SandboxExecResult:
    """Result of a single code/command execution inside a sandbox.

    Mirrors the shape of ``HazardSandbox.execute_python`` return values
    so existing callers don't need to change their parsing.

    Attributes:
        success: True if exit code was 0.
        stdout: captured stdout (truncated to a sane cap; see impl).
        stderr: captured stderr.
        exit_code: process exit code; -1 indicates sandbox-level failure
            (boot timeout, OOM kill, etc.).
        duration_seconds: wall-clock execution time.
        truncated: True if stdout/stderr were truncated.
        metadata: backend-specific extras (container_id, vm_id, etc.).
    """

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float = 0.0
    truncated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# Protocol
# ===========================================================================
@runtime_checkable
class SandboxRuntime(Protocol):
    """Unified execution sandbox interface.

    Backends:
      * ``DockerRuntime`` — pre-Round-46 behavior, used as fallback when
        ATOM_SANDBOX_RUNTIME=docker (default).
      * ``FirecrackerRuntime`` — self-hosted microVMs
        (ATOM_SANDBOX_RUNTIME=firecracker). Requires KVM-enabled Linux host.
      * ``E2BRuntime`` — managed microVMs via E2B SDK
        (ATOM_SANDBOX_RUNTIME=e2b). Requires E2B_API_KEY.

    All methods are async. All methods accept the active ``SandboxPolicy``
    so backends can enforce caps (mem / vCPU / timeout) per-policy.
    """

    async def execute_python(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]] = None,
        cwd: Optional[str] = None,
    ) -> SandboxExecResult:
        """Execute Python code inside the sandbox.

        Args:
            code: Python source to execute.
            policy: SandboxPolicy with max_exec_seconds / max_bytes_written caps.
            inputs: optional dict exposed as module-level globals.
            cwd: optional working directory inside the sandbox.
        """
        ...

    async def execute_command(
        self,
        command: str,
        *,
        policy: Any,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecResult:
        """Execute a shell command inside the sandbox.

        Args:
            command: shell command line.
            policy: SandboxPolicy with caps.
            cwd: optional working directory.
            env: optional env-var overrides (existing sandbox env is preserved).
        """
        ...

    async def cleanup(self) -> None:
        """Release all sandbox resources (containers, VMs, sockets)."""
        ...


# ===========================================================================
# Factory
# ===========================================================================


def get_runtime() -> SandboxRuntime:
    """Return the configured SandboxRuntime backend.

    Selection order:
      1. ``ATOM_SANDBOX_RUNTIME=e2b`` → E2BRuntime (if E2B_API_KEY set)
      2. ``ATOM_SANDBOX_RUNTIME=firecracker`` → FirecrackerRuntime
         (if firecracker-bin available)
      3. ``ATOM_SANDBOX_RUNTIME=docker`` (default) → DockerRuntime
      4. Any failure → DockerRuntime fallback (or ``NullRuntime`` if
         Docker is also unavailable)

    Returns a singleton per process.
    """
    from core import sandbox_config

    backend = sandbox_config.get_sandbox_runtime()
    try:
        if backend == "e2b":
            from core.sandbox_runtime.e2b_runner import E2BRuntime, is_available as e2b_ok

            if e2b_ok():
                return E2BRuntime()
        if backend == "firecracker":
            from core.sandbox_runtime.firecracker_runner import (
                FirecrackerRuntime,
                is_available as fc_ok,
            )

            if fc_ok():
                return FirecrackerRuntime()
        # Fallback always: Docker
        from core.sandbox_runtime.docker_runner import DockerRuntime

        return DockerRuntime()
    except Exception as e:  # noqa: BLE001
        logger.warning("sandbox runtime %s unavailable, falling back: %s", backend, e)
        from core.sandbox_runtime.docker_runner import DockerRuntime

        try:
            return DockerRuntime()
        except Exception:
            return NullRuntime()


class NullRuntime:
    """Last-resort no-op runtime. Returns failure without raising.

    Used when neither Firecracker, E2B, nor Docker is available. The
    alternative — raising — would break agent execution; returning a
    structured failure lets the agent see "no sandbox available" and
    proceed via other means (or surface the error to the user).
    """

    async def execute_python(self, code, *, policy, inputs=None, cwd=None):
        return SandboxExecResult(
            success=False,
            stdout="",
            stderr="No sandbox runtime available",
            exit_code=-1,
            metadata={"backend": "null"},
        )

    async def execute_command(self, command, *, policy, cwd=None, env=None):
        return SandboxExecResult(
            success=False,
            stdout="",
            stderr="No sandbox runtime available",
            exit_code=-1,
            metadata={"backend": "null"},
        )

    async def cleanup(self):
        return None
