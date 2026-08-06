"""FirecrackerRuntime — self-hosted microVM backend (real bootable microVM).

Mini Apps (stateful canvas-UI apps) execute ONLY in Firecracker microVMs. This
runtime driver boots a REAL microVM from a configured kernel (``vmlinux``) and
an ext4 rootfs, and talks to a PID-1 Python guest agent over a **vsock command
channel**:

  * ``config.json`` boot-source = ``FIRECRACKER_KERNEL_IMAGE`` with boot_args
    ``console=ttyS0 reboot=k panic=1 pci=off init=/opt/atom-guest/agent.py
    miniapp_port=<port>``.
  * The rootfs drive is the app's ``runtime_image`` (or the base template
    ``FIRECRACKER_ROOTFS_TEMPLATE`` when ``image`` is None) — read-only, root
    device.
  * ``vsock`` = ``{guest_cid: 3, uds_path: <run_dir>/vsock.sock}``.
  * After boot the runner accepts on the UDS, sends one JSON line
    ``{"code", "inputs"}``, the guest agent executes and replies with one JSON
    line ``{"stdout", "stderr", "exit_code"}``.

Host provisioning (kernel download, per-app rootfs build) is operator-run via
``scripts/build_miniapp_rootfs.sh`` + ``docs/deployment/FIRECRACKER_HOST_SETUP.md``.
Docker is a build-time-only host tool for rootfs construction — never the app
runtime.

Availability is split into two probes so the two callers get the right
semantics:

  * ``is_available()`` — the CHEAP probe used by the generic
    ``get_runtime()`` factory: Linux AND ``firecracker`` on PATH AND the
    kernel image resolves. It does NOT require the base rootfs template,
    so generic sandbox users (legacy canvas logic, skill sandbox) keep
    their Docker fallback unchanged when Firecracker is installed but
    only mini-app rootfs templates are missing (or vice versa).
  * ``is_provisioned_for(image)`` — the STRICT probe used by the mini-app
    fail-closed factory: ``is_available()`` AND (when ``image`` is None)
    the base rootfs template resolves. Per-app rootfs paths are checked
    at execution time (a stale/missing per-app rootfs is a runtime
    failure, not a host-provisioning failure).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, Optional

from core import sandbox_config
from core.sandbox_runtime.base import SandboxExecResult

logger = logging.getLogger(__name__)

# Detect Linux once at import (cheap). Referenced by is_available().
_IS_LINUX = sys.platform.startswith("linux")

# Output cap per stream (mirrors the Docker/E2B runners).
OUTPUT_CAP = 65536  # 64 KiB

# Guest-side metadata.
GUEST_CID = 3
HOST_CID = 2

# Env vars / defaults.
KERNEL_IMAGE_ENV = "FIRECRACKER_KERNEL_IMAGE"
ROOTFS_TEMPLATE_ENV = "FIRECRACKER_ROOTFS_TEMPLATE"
DEFAULT_ROOTFS_TEMPLATE = os.path.join("data", "firecracker", "miniapp-base.ext4")
GUEST_PORT_ENV = "ATOM_MINIAAP_GUEST_PORT"
DEFAULT_GUEST_PORT = 5050
GUEST_AGENT_INIT = "/opt/atom-guest/agent.py"


def get_kernel_image() -> Optional[str]:
    """Path to the ``vmlinux`` kernel image, or None if unset."""
    val = os.getenv(KERNEL_IMAGE_ENV)
    return val or None


def get_rootfs_template() -> str:
    """Base ext4 rootfs template used when no per-app ``image`` is supplied."""
    return os.getenv(ROOTFS_TEMPLATE_ENV, DEFAULT_ROOTFS_TEMPLATE)


def get_guest_port() -> int:
    """Vsock port the guest agent listens on (via boot_args)."""
    try:
        return max(1, int(os.getenv(GUEST_PORT_ENV, str(DEFAULT_GUEST_PORT))))
    except (TypeError, ValueError):
        return DEFAULT_GUEST_PORT


def get_guest_boot_args(port: Optional[int] = None) -> str:
    """Boot args handed to the kernel; the guest agent parses ``miniapp_port``
    from ``/proc/cmdline`` (boot_args can't set env vars)."""
    p = port or get_guest_port()
    return (
        f"console=ttyS0 reboot=k panic=1 pci=off "
        f"init={GUEST_AGENT_INIT} miniapp_port={p}"
    )


# ===========================================================================
# Availability probes
# ===========================================================================
def is_available() -> bool:
    """CHEAP probe: True when the host could boot a Firecracker microVM.

    Linux AND ``firecracker`` on PATH AND the kernel image resolves. Does
    NOT check for the base rootfs template — that's the job of
    ``is_provisioned_for()``. Used by the generic ``get_runtime()`` factory
    so generic sandbox users keep their Docker fallback when the template
    is absent (only mini apps require it).
    """
    if not _IS_LINUX:
        return False
    if shutil.which("firecracker") is None:
        return False
    kernel = get_kernel_image()
    if not kernel or not os.path.isfile(kernel):
        return False
    return True


def is_provisioned_for(image: Optional[str] = None) -> bool:
    """STRICT probe: True when a mini-app microVM can be booted for ``image``.

    ``is_available()`` AND, when ``image`` is None, the base rootfs template
    resolves (mini apps without dependencies boot from the template). Used by
    the fail-closed mini-app factory. A non-None ``image`` (a per-app rootfs)
    is NOT checked here — a stale/missing per-app rootfs surfaces as a runtime
    failure from ``execute_python`` with ``reason="rootfs_missing"``.
    """
    if not is_available():
        return False
    if image is None:
        template = get_rootfs_template()
        if not template or not os.path.isfile(template):
            return False
    return True


# ===========================================================================
# Runtime
# ===========================================================================
# Cap concurrent microVM boots. Each VM needs KVM, vCPU, and RAM (default
# ATOM_SANDBOX_VM_VCPUS / ATOM_SANDBOX_VM_MEM_MB) — unbounded concurrency
# would exhaust the host. Sized by ATOM_SANDBOX_VM_MAX_CONCURRENCY (default 4).
# Unlike a per-process asyncio.Lock (which serialized ALL runs), this semaphore
# allows up to N VMs to boot in parallel.
def _max_concurrency() -> int:
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "4")))
    except (TypeError, ValueError):
        return 4


class FirecrackerRuntime:
    """Self-hosted Firecracker microVM driver with a vsock command channel.

    The driver does NOT include the firecracker/jailer binaries, the kernel,
    or the rootfs — those are host-provisioned. See
    ``docs/deployment/FIRECRACKER_HOST_SETUP.md``. When the host isn't fully
    provisioned, ``execute_python`` returns a structured failure; the generic
    factory falls back to Docker, while mini apps hard-fail upstream.

    Concurrency is bounded by a process-wide semaphore (``_concurrency_sem``)
    sized to KVM/host capacity — VMs no longer serialize behind a single lock.
    """

    def __init__(self) -> None:
        # Atomic VM id counter (no lock needed — itertools.count is thread-safe
        # and we only need uniqueness, not dense sequencing).
        self._vmid_iter = itertools.count(1)
        self._concurrency_sem: Optional[asyncio.Semaphore] = None

    def _sem(self) -> asyncio.Semaphore:
        # Lazily create the semaphore against the running loop so it survives
        # across loop recreations in tests.
        if self._concurrency_sem is None or self._concurrency_sem._bound_loop != asyncio.get_event_loop():  # type: ignore[attr-defined]
            self._concurrency_sem = asyncio.Semaphore(_max_concurrency())
        return self._concurrency_sem

    async def execute_python(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]] = None,
        cwd: Optional[str] = None,
        image: Optional[str] = None,
    ) -> SandboxExecResult:
        """Boot a microVM, run ``code`` in the guest agent, capture output.

        ``image`` selects the rootfs drive (ext4 path). ``None`` → base
        template. ``cwd`` is accepted for protocol conformance but ignored —
        the guest has no host filesystem (all storage is host-mediated).
        """
        if not is_available():
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=(
                    "Firecracker runtime unavailable: Linux host with the "
                    "'firecracker' binary, FIRECRACKER_KERNEL_IMAGE, and the "
                    "base rootfs template (FIRECRACKER_ROOTFS_TEMPLATE) required"
                ),
                exit_code=-1,
                metadata={"backend": "firecracker", "reason": "unavailable"},
            )
        rootfs = image or get_rootfs_template()
        if not os.path.isfile(rootfs):
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=f"Rootfs not found: {rootfs}",
                exit_code=-1,
                metadata={"backend": "firecracker", "reason": "rootfs_missing"},
            )
        return await self._run_in_vm(
            code,
            policy=policy,
            inputs=inputs,
            rootfs=rootfs,
        )

    async def execute_command(
        self,
        command: str,
        *,
        policy: Any,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecResult:
        """Run a shell command by wrapping it in Python for the guest agent."""
        code = (
            "import subprocess\n"
            f"_r = subprocess.run({command!r}, shell=True, capture_output=True, text=True)\n"
            "import sys\n"
            "sys.stdout.write(_r.stdout); sys.stderr.write(_r.stderr); sys.exit(_r.returncode)\n"
        )
        return await self.execute_python(code, policy=policy, inputs=env or {})

    async def cleanup(self) -> None:
        # Firecracker VMs are ephemeral per-execution (auto-removed on exit).
        return None

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------
    async def _run_in_vm(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]],
        rootfs: str,
    ) -> SandboxExecResult:
        """Boot a microVM, exchange a vsock command, tear down.

        Concurrency is bounded by ``_concurrency_sem`` (KVM capacity) — VMs
        boot in parallel up to the cap rather than serializing behind a lock.
        """
        async with self._sem():
            vm_id = f"atom-fc-{os.getpid()}-{next(self._vmid_iter)}"

        run_dir = tempfile.mkdtemp(prefix=f"{vm_id}-")
        start = time.time()
        try:
            config_path = os.path.join(run_dir, "config.json")
            vsock_path = os.path.join(run_dir, "vsock.sock")
            _write_vm_config(
                config_path,
                vm_id=vm_id,
                kernel_image=get_kernel_image(),
                boot_args=get_guest_boot_args(),
                mem_mb=sandbox_config.get_sandbox_vm_mem_mb(),
                vcpus=sandbox_config.get_sandbox_vm_vcpus(),
                rootfs=rootfs,
                vsock_uds=vsock_path,
            )

            timeout = max(1, int(getattr(policy, "max_exec_seconds", 30) or 30))
            boot_timeout = sandbox_config.get_sandbox_vm_boot_timeout_seconds()
            overall_timeout = timeout + boot_timeout + 2  # slack

            try:
                proc = await asyncio.create_subprocess_exec(
                    "firecracker",
                    "--api-sock",
                    os.path.join(run_dir, "api.sock"),
                    "--config-file",
                    config_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                return SandboxExecResult(
                    success=False,
                    stdout="",
                    stderr="firecracker binary not found",
                    exit_code=-1,
                    metadata={"backend": "firecracker", "reason": "binary_missing"},
                )

            try:
                stdout_text, stderr_text, exit_code, envelope = await asyncio.wait_for(
                    self._exchange(code, inputs or {}, vsock_path),
                    timeout=overall_timeout,
                )
            except asyncio.TimeoutError:
                return SandboxExecResult(
                    success=False,
                    stdout="",
                    stderr=f"Firecracker VM timeout after {overall_timeout}s",
                    exit_code=-1,
                    duration_seconds=time.time() - start,
                    metadata={"backend": "firecracker", "vm_id": vm_id, "timeout": True},
                )
            finally:
                # The command channel has completed (or timed out): tear the VM
                # down. The guest agent sleeps after replying; the host kills
                # it. We reap the child so a killed firecracker/jailer doesn't
                # leave a dangling process (a kill without wait would orphan it
                # and possibly leak the jailer cgroup on the host).
                if proc.returncode is None:
                    proc.kill()
                try:
                    await proc.wait()
                except Exception:  # noqa: BLE001
                    pass

            stdout_text = stdout_text or ""
            stderr_text = stderr_text or ""
            meta: Dict[str, Any] = {"backend": "firecracker", "vm_id": vm_id}
            if envelope is not None:
                # Structured state — preserved verbatim, immune to stdout cap.
                meta["state_envelope"] = envelope
            return SandboxExecResult(
                success=int(exit_code) == 0,
                stdout=stdout_text[:OUTPUT_CAP],
                stderr=stderr_text[:OUTPUT_CAP],
                exit_code=int(exit_code),
                duration_seconds=time.time() - start,
                truncated=len(stdout_text) > OUTPUT_CAP or len(stderr_text) > OUTPUT_CAP,
                metadata=meta,
            )
        finally:
            try:
                shutil.rmtree(run_dir, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass

    async def _exchange(
        self,
        code: str,
        inputs: Dict[str, Any],
        vsock_path: str,
    ) -> tuple:
        """Wait for the vsock UDS socket, send ``{code, inputs}``, read reply.

        Returns ``(stdout, stderr, exit_code, envelope)`` where ``envelope`` is
        the guest's structured ``{state, storage_ops}`` payload if it sent one
        (None otherwise). Returning state over the vsock reply channel — rather
        than parsing a ``__MINIAPP_STATE__:`` line out of stdout — sidesteps the
        64 KiB stdout cap that would otherwise corrupt large state objects.
        Raises ``asyncio.TimeoutError`` if the socket never appears (boot
        timeout) or the guest never replies.
        """
        boot_timeout = sandbox_config.get_sandbox_vm_boot_timeout_seconds()
        deadline = time.time() + max(1, boot_timeout)
        while not os.path.exists(vsock_path):
            if time.time() > deadline:
                raise asyncio.TimeoutError(
                    f"vsock socket {vsock_path} never appeared (boot timeout)"
                )
            await asyncio.sleep(0.05)

        reader, writer = await asyncio.open_unix_connection(vsock_path)
        try:
            payload = json.dumps({"code": code, "inputs": inputs})
            writer.write((payload + "\n").encode("utf-8"))
            await writer.drain()
            line = await reader.readline()
            if not line:
                raise asyncio.TimeoutError("guest agent returned no response")
            data = json.loads(line.decode("utf-8"))
            stdout = str(data.get("stdout", ""))
            stderr = str(data.get("stderr", ""))
            exit_code = int(data.get("exit_code", -1))
            # Structured state envelope (preferred over stdout parsing). May be
            # absent for non-mini-app callers / older guest agents.
            envelope = data.get("state_envelope")
            if not isinstance(envelope, dict):
                envelope = None
            return (stdout, stderr, exit_code, envelope)
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


# ===========================================================================
# Internal: VM config writer
# ===========================================================================


def _write_vm_config(
    path: str,
    *,
    vm_id: str,
    kernel_image: Optional[str],
    boot_args: str,
    mem_mb: int,
    vcpus: int,
    rootfs: str,
    vsock_uds: str,
) -> None:
    """Write a bootable Firecracker ``config.json``.

    ``boot-source``: kernel + boot args (``init=`` the guest agent so it runs
    as PID 1 with no init system). ``drives``: the rootfs, read-only root
    device. ``vsock``: the command-channel UDS. ``machine-config``: vCPU/mem.
    """
    config = {
        "boot-source": {
            "kernel_image_path": kernel_image or "",
            "boot_args": boot_args,
        },
        "machine-config": {
            "vcpu_count": int(vcpus),
            "mem_size_mib": int(mem_mb),
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": rootfs,
                "is_root_device": True,
                "is_read_only": True,
            }
        ],
        "vsock": {
            "guest_cid": GUEST_CID,
            "uds_path": vsock_uds,
        },
        "_atom": {
            "vm_id": vm_id,
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
