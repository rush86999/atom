"""DockerRuntime — SandboxRuntime adapter over existing Docker code.

Default backend. Preserves pre-Round-46 behavior: code executes in a
Docker container with network disabled, read-only rootfs, tmpfs /tmp,
memory + CPU limits.

This adapter wraps the existing ``core.skill_sandbox.HazardSandbox``
sync API in ``asyncio.to_thread`` so it satisfies the async
``SandboxRuntime`` protocol.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from core.sandbox_runtime.base import SandboxExecResult

logger = logging.getLogger(__name__)


class DockerRuntime:
    """SandboxRuntime adapter over HazardSandbox (Docker-based).

    Construction is lazy: the underlying Docker client is only poked on
    first execution. This means tests can construct ``DockerRuntime()``
    without a Docker daemon present.
    """

    def __init__(self) -> None:
        self._sandbox = None  # lazy HazardSandbox
        self._init_lock = asyncio.Lock()

    async def _ensure_sandbox(self):
        if self._sandbox is None:
            async with self._init_lock:
                if self._sandbox is None:
                    # Import lazily so the module loads even without Docker.
                    from core.skill_sandbox import HazardSandbox

                    self._sandbox = HazardSandbox()
        return self._sandbox

    async def execute_python(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]] = None,
        cwd: Optional[str] = None,
    ) -> SandboxExecResult:
        try:
            sandbox = await self._ensure_sandbox()
            timeout = max(1, int(getattr(policy, "max_exec_seconds", 30) or 30))
            mem_mb = None  # let HazardSandbox default (256m) stand for now
            result = await asyncio.to_thread(
                sandbox.execute_python,
                code,
                inputs or {},
                timeout,
                mem_mb,
            )
            return _parse_legacy_output(result)
        except Exception as e:  # noqa: BLE001
            logger.warning("DockerRuntime python exec failed: %s", e)
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=f"Docker runtime unavailable: {e}",
                exit_code=-1,
                metadata={"backend": "docker", "error": str(e)},
            )

    async def execute_command(
        self,
        command: str,
        *,
        policy: Any,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecResult:
        # HazardSandbox only exposes execute_python; we wrap shell commands
        # as a subprocess.run inside the python wrapper.
        code = (
            "import subprocess, sys\n"
            f"_r = subprocess.run({command!r}, shell=True, capture_output=True, text=True)\n"
            "sys.stdout.write(_r.stdout); sys.stderr.write(_r.stderr)\n"
        )
        return await self.execute_python(code, policy=policy)

    async def cleanup(self) -> None:
        # HazardSandbox uses auto_remove=True containers — nothing to do.
        return None


def _parse_legacy_output(output: Any) -> SandboxExecResult:
    """Parse HazardSandbox's str/dict return into SandboxExecResult."""
    if isinstance(output, dict):
        return SandboxExecResult(
            success=bool(output.get("success", False)),
            stdout=str(output.get("stdout", ""))[:65536],
            stderr=str(output.get("stderr", ""))[:65536],
            exit_code=int(output.get("returncode", output.get("exit_code", -1))),
            truncated=len(str(output.get("stdout", ""))) > 65536,
            metadata={"backend": "docker"},
        )
    # Plain string output — HazardSandbox returns this on success.
    text = str(output or "")
    is_error = text.startswith("EXECUTION_ERROR:") or text.startswith("SANDBOX_ERROR:")
    return SandboxExecResult(
        success=not is_error,
        stdout=text[:65536] if not is_error else "",
        stderr=text if is_error else "",
        exit_code=-1 if is_error else 0,
        truncated=len(text) > 65536,
        metadata={"backend": "docker"},
    )
