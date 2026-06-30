"""E2BRuntime — managed microVM backend via E2B SDK.

E2B (https://e2b.dev) is a managed service providing Firecracker-based
microVMs via a Python SDK. Zero host dependencies — works on macOS,
Linux, Windows. Costs per-execution (~$0.05).

Used when ``ATOM_SANDBOX_RUNTIME=e2b`` AND ``E2B_API_KEY`` is set.
Otherwise the factory falls back to Docker or Firecracker.

The E2B SDK is imported lazily so this module loads even when the SDK
isn't installed.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from core.sandbox_runtime.base import SandboxExecResult

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """True if ``E2B_API_KEY`` is set and the e2b SDK is importable."""
    if not os.getenv("E2B_API_KEY"):
        return False
    try:
        import e2b  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


class E2BRuntime:
    """Managed microVM backend via E2B SDK.

    Construction is lazy — the SDK client is created on first execution.
    Tests can construct ``E2BRuntime()`` without the SDK installed.
    """

    def __init__(self) -> None:
        self._client = None
        self._init_lock = asyncio.Lock()

    async def _ensure_client(self):
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    import e2b  # type: ignore[import-not-found]

                    self._client = e2b.Sandbox()
        return self._client

    async def execute_python(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]] = None,
        cwd: Optional[str] = None,
    ) -> SandboxExecResult:
        if not is_available():
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr="E2B_API_KEY missing or e2b SDK not installed",
                exit_code=-1,
                metadata={"backend": "e2b", "reason": "unavailable"},
            )
        try:
            client = await self._ensure_client()
            timeout = max(1, int(getattr(policy, "max_exec_seconds", 30) or 30))
            result = await asyncio.to_thread(
                client.run,
                code,
                language="python",
                timeout=timeout,
            )
            return _parse_e2b_result(result)
        except Exception as e:  # noqa: BLE001
            logger.warning("E2B python exec failed: %s", e)
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=f"E2B runtime error: {e}",
                exit_code=-1,
                metadata={"backend": "e2b", "error": str(e)},
            )

    async def execute_command(
        self,
        command: str,
        *,
        policy: Any,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecResult:
        if not is_available():
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr="E2B_API_KEY missing or e2b SDK not installed",
                exit_code=-1,
                metadata={"backend": "e2b", "reason": "unavailable"},
            )
        try:
            client = await self._ensure_client()
            timeout = max(1, int(getattr(policy, "max_exec_seconds", 30) or 30))
            result = await asyncio.to_thread(
                client.commands.run,
                command,
                timeout=timeout,
            )
            return _parse_e2b_result(result)
        except Exception as e:  # noqa: BLE001
            logger.warning("E2B command exec failed: %s", e)
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=f"E2B runtime error: {e}",
                exit_code=-1,
                metadata={"backend": "e2b", "error": str(e)},
            )

    async def cleanup(self) -> None:
        if self._client is not None:
            try:
                await asyncio.to_thread(self._client.kill)
            except Exception:  # noqa: BLE001
                pass
            self._client = None


def _parse_e2b_result(result: Any) -> SandboxExecResult:
    """Parse E2B SDK result into SandboxExecResult.

    E2B's result object shape varies by SDK version; we duck-type the
    common attributes.
    """
    stdout = getattr(result, "stdout", None) or getattr(result, "text", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    exit_code = getattr(result, "exit_code", getattr(result, "returncode", 0))
    return SandboxExecResult(
        success=int(exit_code) == 0,
        stdout=str(stdout)[:65536],
        stderr=str(stderr)[:65536],
        exit_code=int(exit_code),
        truncated=len(str(stdout)) > 65536,
        metadata={"backend": "e2b"},
    )
