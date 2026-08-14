"""
Firecracker sandbox manager.
Executes commands (e.g. LibreOffice headless macro execution) inside a secure
microVM. FAIL-CLOSED (W109-1): when KVM/Firecracker is unavailable the
untrusted command is never executed on the host — ``execute_in_sandbox``
raises ``SandboxUnavailableError`` instead of silently falling back to
containerized/local execution.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class SandboxUnavailableError(RuntimeError):
    """Raised when no secure execution runtime is available.

    Firecracker sandboxing FAILS CLOSED: when KVM/Firecracker is unavailable
    (or the VM cannot boot) the untrusted command is never executed on the
    host — callers get an explicit error instead of a silent local fallback.
    """


class FirecrackerSandbox:
    """Orchestrates Firecracker microVM execution for untrusted workbook actions."""

    def __init__(self):
        self.has_kvm = os.path.exists("/dev/kvm")
        self.firecracker_path = shutil.which("firecracker")

    @property
    def is_available(self) -> bool:
        """Check if Firecracker virtualization is fully supported on the host."""
        return bool(self.has_kvm and self.firecracker_path)

    async def execute_in_sandbox(
        self,
        command: List[str],
        input_file: Path,
        output_dir: Path,
        timeout: float = 60.0
    ) -> bool:
        """Executes a command inside a Firecracker VM with the input file mapped.

        Fail-closed: if Firecracker/KVM is unavailable, or the VM fails to
        start, ``SandboxUnavailableError`` is raised and the command is
        **never** executed on the host (no silent local fallback). Returns
        ``False`` if the VM orchestration cannot actually run the command.
        """
        if not self.is_available:
            raise SandboxUnavailableError(
                "Firecracker sandbox unavailable (KVM or firecracker binary missing); "
                "refusing to execute untrusted command on host"
            )
        logger.info(f"Executing sandboxed command in Firecracker VM: {command}")
        try:
            # Prepare Firecracker VM config JSON pointing to rootfs and kernel,
            # map input_file into the microVM block device or via vsock, start
            # the Firecracker process, trigger boot, then run the command.
            proc = await asyncio.create_subprocess_exec(
                "firecracker",
                "--api-sock", "/tmp/firecracker.socket",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.sleep(0.5)
            proc.kill()
        except Exception as e:
            logger.debug(f"Firecracker VM startup failed: {e}.")
            raise SandboxUnavailableError(f"Firecracker VM startup failed: {e}") from e

        # VM orchestration cannot run the command yet — fail closed rather
        # than silently executing the untrusted command on the host.
        logger.warning(
            "Firecracker VM orchestration is a placeholder — command not executed; "
            "no host fallback."
        )
        return False


_sandbox: Optional[FirecrackerSandbox] = None


def get_sandbox() -> FirecrackerSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = FirecrackerSandbox()
    return _sandbox
