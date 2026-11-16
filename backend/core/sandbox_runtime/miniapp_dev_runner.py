"""MiniAppDevRuntime — DEV-ONLY Docker-backed mini-app execution (macOS/desktop).

Mini apps execute ONLY in Firecracker microVMs in production; that posture
stays fail-closed (``core.mini_app_runtime.get_miniapp_runtime``). This
runtime is the explicitly-opt-in local-development equivalent for hosts where
Firecracker cannot run (macOS has no KVM): the SAME guest agent
(``firecracker_guest/agent.py --stdio``), the SAME JSON-line protocol
(exec / callback / final — see ``guest_protocol``), and the SAME result
contract (state envelope + callback audit in metadata) — with a Docker
container swapped for the microVM and the vsock UDS swapped for pipes.

Parity contract with ``FirecrackerRuntime``:
  * ``execute_python(code, policy=, inputs=, image=, callback_handler=, deps=``
    → ``SandboxExecResult`` with ``metadata["state_envelope"]`` and
    ``metadata["callbacks"]`` (identical shapes).
  * No network (``--network none`` ↔ no tap device), read-only rootfs
    (``--read-only`` ↔ read-only rootfs drive), memory/CPU caps, ephemeral
    container (``--rm`` ↔ auto-removed VM), non-root ``app`` user,
    caps dropped.
  * Integration tokens stay host-side — the callback handler resolves them;
    the container never sees credentials.

Isolation honesty: Docker on macOS runs inside Docker Desktop's Linux VM, so
the Mac host is shielded by that VM boundary, but containers share the guest
kernel with each other — weaker than Firecracker's dedicated kernel per run.
That is the accepted DEV posture (mirrors the generic
``ATOM_SANDBOX_RUNTIME=docker`` tier); production keeps microVM isolation and
the factory refuses ``docker-dev`` when ``ENVIRONMENT=production``.

Images: built locally from the same recipe ``scripts/build_miniapp_rootfs.sh``
uses (``python:3.11-slim`` + guest agent [+ pip deps from the manifest]), but
tagged by dependency-set hash instead of ext4 paths — repeat dev-runs reuse
the cache and a dependency change rebuilds:

    atom-miniapp-dev:base            # no dependencies
    atom-miniapp-dev:deps-<sha1_12>  # with dependencies
"""
from __future__ import annotations

import asyncio
from core.asyncio_compat import get_event_loop
import hashlib
import itertools
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core import sandbox_config
from core.sandbox_runtime.base import SandboxExecResult
from core.sandbox_runtime.capacity import (
    CapacityQuarantined, CleanupUncertain, await_teardown,
    get_capacity_semaphore, quarantine,
)
from core.sandbox_runtime.guest_protocol import OUTPUT_CAP
from core.sandbox_runtime.guest_protocol import exchange as _guest_exchange

logger = logging.getLogger(__name__)

# Image naming. The base image mirrors build_miniapp_rootfs.sh --base
# (python:3.11-slim + the guest agent, non-root `app` user); dependency
# images layer pip requirements on top of it.
IMAGE_REPO = "atom-miniapp-dev"
BASE_TAG = f"{IMAGE_REPO}:base"
BASE_FROM = os.getenv("MINIAPP_BASE_IMAGE", "python:3.11-slim")

# The guest agent is the same file the Firecracker rootfs bakes in.
_AGENT_SOURCE = os.path.join(
    os.path.dirname(__file__), "firecracker_guest", "agent.py"
)
_AGENT_IN_CONTAINER = "/opt/atom-guest/agent.py"

_BUILD_TIMEOUT_SECONDS = 900
_AVAIL_TTL_SECONDS = 10.0
CAPACITY_SCOPE = "miniapp-docker"
_RM_CAPTURE_BYTES = 4096
_REMOVE_TIMEOUT_SECONDS = 5.0
_REMOVE_CONFIRM_SECONDS = 10.0
_REMOVE_POLL_INTERVAL = 0.1

# Availability probe TTL cache — ``docker info`` spawns a process (~100ms);
# the factory + execute path both probe, so cache briefly.
_avail_cache: Tuple[float, bool] = (0.0, False)


def is_available() -> bool:
    """CHEAP probe: True when the Docker daemon is reachable.

    Used by the fail-closed mini-app factory. Unlike the Firecracker probe
    there is no strict variant — image presence is resolved lazily at
    execution time (missing images are built from the app's deps).
    """
    global _avail_cache
    now = time.time()
    cached_ts, cached = _avail_cache
    if now - cached_ts < _AVAIL_TTL_SECONDS:
        return cached
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "ok"],
            capture_output=True,
            timeout=10,
        )
        ok = proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    _avail_cache = (now, ok)
    return ok


def deps_hash(deps: List[str]) -> str:
    """Stable short hash of a dependency set (order-insensitive)."""
    return hashlib.sha256("\n".join(sorted(deps or [])).encode("utf-8")).hexdigest()[:12]


def resolve_dev_image(deps: Optional[List[str]]) -> Tuple[str, List[str]]:
    """Map a dependency set to its dev image tag.

    Returns ``(tag, deps)``. Content-addressed: same deps → same tag, so
    repeat dev-runs skip the build and a dependency change gets a fresh tag
    (old tags linger until ``docker image prune`` — fine on a dev host).
    """
    deps = list(deps or [])
    if not deps:
        return BASE_TAG, deps
    return f"{IMAGE_REPO}:deps-{deps_hash(deps)}", deps


def _dev_dockerfile(tag: str, deps: List[str]) -> str:
    """Dockerfile matching build_miniapp_rootfs.sh's recipe (minus ext4)."""
    if not deps:
        return (
            f"FROM {BASE_FROM}\n"
            "RUN useradd -m app\n"
            "COPY agent.py /opt/atom-guest/agent.py\n"
            "USER app\n"
        )
    return (
        f"FROM {BASE_TAG}\n"
        "COPY requirements.txt /tmp/requirements.txt\n"
        # RUN inherits the base image's non-root `app` user — the rootfs
        # builder's recipe relies on the same layering (COPY → pip → USER).
        "RUN pip install --no-cache-dir -r /tmp/requirements.txt\n"
        "USER app\n"
    )


class _CaptureOverflow(RuntimeError):
    pass


def _valid_returncode(proc) -> Optional[int]:
    value = getattr(proc, "returncode", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _removal_in_progress(stdout, stderr, container: str) -> bool:
    """Docker's exact --rm race line, for this exact case-sensitive target."""
    try:
        if bytes(stdout or b"").strip():
            return False
        text = bytes(stderr or b"").decode("utf-8", "strict")
    except Exception:  # noqa: BLE001
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return False
    expected = (
        "Error response from daemon: removal of container "
        f"{str(container or '')} is already in progress")
    return lines[0] == expected


def _known_absent_inspect(stdout, stderr, container: str) -> bool:
    """Inspect-only absence: exact real lowercase form plus documented uppercase.

    Real `docker inspect --format` on this host returns exit 1 with whitespace
    stdout and exactly: ``error: no such object: <name>``. The command also
    accepts the existing documented ``No such object/container`` forms. This is
    intentionally not a global case-insensitive match; the target comparison is
    exact and case-sensitive.
    """
    try:
        if bytes(stdout or b"").strip():
            return False
        text = bytes(stderr or b"").decode("utf-8", "strict")
    except Exception:  # noqa: BLE001
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return False
    match = re.fullmatch(
        r"(?:"
        r"Error response from daemon: No such (?:container|object):\s*(?P<a>\S+)"
        r"|Error: No such (?:container|object):\s*(?P<b>\S+)"
        r"|No such (?:container|object):\s*(?P<c>\S+)"
        r"|error: no such object:\s*(?P<d>\S+)"
        r")", lines[0])
    if not match:
        return False
    found = next(group for group in match.groupdict().values()
                 if group is not None)
    return found == str(container or "")


def _known_absent(stdout, stderr, container: str) -> bool:
    """One complete daemon absence record for the exact case-sensitive name."""
    try:
        if bytes(stdout or b"").strip():
            return False
        text = bytes(stderr or b"").decode("utf-8", "strict")
    except Exception:  # noqa: BLE001
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return False
    match = re.fullmatch(
        r"(?:Error response from daemon:\s*|Error:\s*)?"
        r"No such (?:container|object):\s*(\S+)", lines[0])
    return bool(match and match.group(1) == str(container or ""))


async def _read_bounded(stream, limit: int = _RM_CAPTURE_BYTES) -> bytes:
    """Read one owned pipe with a pre-read cap.

    Python's asyncio subprocess guidance is to consume stdout/stderr
    concurrently so a child cannot block on a full pipe; this helper also
    bounds the retained bytes instead of allocating the whole output first.
    https://docs.python.org/3/library/asyncio-subprocess.html
    """
    buf = bytearray()
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return bytes(buf)
        if len(buf) + len(chunk) > limit:
            raise _CaptureOverflow("docker rm output cap")
        buf.extend(chunk)


def _cleanup_uncertain(reason: str) -> "CleanupUncertain":
    quarantine(CAPACITY_SCOPE, reason)
    return CleanupUncertain(reason)


# ===========================================================================
# Runtime
# ===========================================================================
class MiniAppDevRuntime:
    """Docker-backed DEV-ONLY driver speaking the Firecracker guest protocol.

    Concurrency is bounded by a process-wide semaphore (default 4, sized by
    ``ATOM_SANDBOX_VM_MAX_CONCURRENCY`` like the Firecracker runner); image
    builds are serialized behind their own lock.
    """

    def __init__(self) -> None:
        self._vmid_iter = itertools.count(1)
        self._concurrency_sem: Optional[asyncio.Semaphore] = None
        self._build_lock: Optional[asyncio.Lock] = None

    def _sem(self) -> asyncio.Semaphore:
        # Shared process-wide across every MiniAppDevRuntime instance and
        # event loop. Factories construct new instances; the Docker/VM
        # capacity is a process resource, held through teardown.
        sem = get_capacity_semaphore(CAPACITY_SCOPE, _max_concurrency())
        self._concurrency_sem = sem
        return sem

    def _build_sem(self) -> asyncio.Lock:
        lock = self._build_lock
        if lock is None:
            self._build_lock = asyncio.Lock()
            return self._build_lock
        bound_loop = getattr(lock, "_bound_loop", None)
        if bound_loop is None:
            bound_loop = getattr(lock, "_loop", None)
        if bound_loop is not None and bound_loop != get_event_loop():
            self._build_lock = asyncio.Lock()
            return self._build_lock
        return lock

    async def execute_python(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]] = None,
        cwd: Optional[str] = None,
        image: Optional[str] = None,
        callback_handler: Any = None,
        deps: Optional[List[str]] = None,
    ) -> SandboxExecResult:
        """Run ``code`` in the dev container, capture output + state envelope.

        ``deps`` (the app manifest's dependencies) drives image resolution —
        the deps-tagged dev image is built on demand. ``image`` (the FC ext4
        rootfs path) is accepted for protocol parity but NOT used to resolve
        the dev image: the ext4 file is meaningless to Docker, and the
        manifest's dep set is the source of truth. ``cwd`` is ignored — the
        container has no host filesystem (all storage is host-mediated),
        matching the microVM contract.
        """
        if not await asyncio.to_thread(is_available):
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=(
                    "docker-dev runtime unavailable: the Docker daemon is not "
                    "reachable. Start Docker Desktop (macOS) or the docker "
                    "daemon, then retry."
                ),
                exit_code=-1,
                metadata={"backend": "docker-dev", "reason": "unavailable"},
            )
        if deps is None and image is not None:
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=(
                    "docker-dev needs the app's dependency list (deps=...) to "
                    "resolve its dev image; got image=... without deps"
                ),
                exit_code=-1,
                metadata={"backend": "docker-dev", "reason": "deps_unspecified"},
            )
        tag, dep_list = resolve_dev_image(deps)
        build_error = await self._ensure_image(tag, dep_list)
        if build_error is not None:
            return SandboxExecResult(
                success=False,
                stdout="",
                stderr=f"Dev image build failed for {tag}: {build_error}",
                exit_code=-1,
                metadata={"backend": "docker-dev", "reason": "image_build_failed",
                          "image": tag},
            )
        return await self._run_in_container(
            code,
            policy=policy,
            inputs=inputs,
            tag=tag,
            callback_handler=callback_handler,
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
        # Containers run with --rm — nothing to release.
        return None

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------
    async def _run_in_container(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]],
        tag: str,
        callback_handler: Any = None,
    ) -> SandboxExecResult:
        """Hold one shared capacity permit through the complete container lifecycle."""
        try:
            async with self._sem():
                return await self._run_in_container_locked(
                    code, policy=policy, inputs=inputs, tag=tag,
                    callback_handler=callback_handler)
        except CapacityQuarantined:
            return SandboxExecResult(
                success=False, stdout="", stderr=(
                    "docker-dev capacity is quarantined after an unconfirmed "
                    "owned-process cleanup; refusing a new launch"),
                exit_code=-1,
                metadata={"backend": "docker-dev",
                          "reason": "capacity_quarantined"})
        except CleanupUncertain as exc:
            quarantine(CAPACITY_SCOPE, str(exc))
            return SandboxExecResult(
                success=False, stdout="", stderr=(
                    f"docker-dev cleanup unconfirmed: {exc}"),
                exit_code=-1,
                metadata={"backend": "docker-dev",
                          "reason": "cleanup_unconfirmed"})

    async def _run_in_container_locked(
        self,
        code: str,
        *,
        policy: Any,
        inputs: Optional[Dict[str, Any]],
        tag: str,
        callback_handler: Any = None,
    ) -> SandboxExecResult:
        """Start the container, exchange the guest protocol, tear down."""
        container = f"{IMAGE_REPO}-run-{os.getpid()}-{uuid.uuid4().hex[:12]}"

        mem_mb = sandbox_config.get_sandbox_vm_mem_mb()
        vcpus = sandbox_config.get_sandbox_vm_vcpus()
        cmd = [
            "docker", "run",
            "--rm",
            "-i",
            "--name", container,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:size=10m",
            "--memory", f"{mem_mb}m",
            "--cpus", str(vcpus),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-e", "PYTHONUNBUFFERED=1",
            tag,
            "python3", _AGENT_IN_CONTAINER, "--stdio",
        ]

        timeout = max(1, int(getattr(policy, "max_exec_seconds", 30) or 30))
        overall_timeout = timeout + 10  # container start slack (no VM boot)
        start = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return SandboxExecResult(
                success=False, stdout="",
                stderr="docker binary not found",
                exit_code=-1,
                metadata={"backend": "docker-dev", "reason": "binary_missing"},
            )

        stderr_chunks: List[bytes] = []

        async def _drain_stderr() -> None:
            # Concurrent drain so a chatty stderr can't fill its pipe and
            # deadlock the protocol exchange. Kept tail-sized for errors.
            while True:
                line = await proc.stderr.readline()
                if not line:
                    return
                stderr_chunks.append(line)
                if sum(len(c) for c in stderr_chunks) > 16_384:
                    del stderr_chunks[0]

        drain_task = asyncio.create_task(_drain_stderr())
        try:
            try:
                stdout_text, stderr_text, exit_code, envelope, callbacks = await asyncio.wait_for(
                    _guest_exchange(
                        proc.stdout, proc.stdin, code, inputs or {}, callback_handler
                    ),
                    timeout=overall_timeout,
                )
            except asyncio.TimeoutError as e:
                elapsed = time.time() - start
                stderr_tail = b"".join(stderr_chunks).decode("utf-8", "replace")[-2000:]
                detail = str(e) or f"no response within {overall_timeout}s"
                return SandboxExecResult(
                    success=False, stdout="",
                    stderr=f"docker-dev timeout after {elapsed:.0f}s: {detail}"
                           + (f" | guest stderr: {stderr_tail}" if stderr_tail else ""),
                    exit_code=-1,
                    duration_seconds=elapsed,
                    metadata={"backend": "docker-dev", "container": container,
                              "image": tag, "timeout": True},
                )
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                stderr_tail = b"".join(stderr_chunks).decode("utf-8", "replace")[-2000:]
                return SandboxExecResult(
                    success=False, stdout="",
                    stderr=f"docker-dev protocol corruption ({e})."
                           + (f" | guest stderr: {stderr_tail}" if stderr_tail else ""),
                    exit_code=-1,
                    duration_seconds=time.time() - start,
                    metadata={"backend": "docker-dev", "container": container,
                              "image": tag, "reason": "protocol_error"},
                )
            except (OSError, EOFError) as e:
                stderr_tail = b"".join(stderr_chunks).decode("utf-8", "replace")[-2000:]
                return SandboxExecResult(
                    success=False, stdout="",
                    stderr=f"docker-dev guest died before replying ({e})."
                           + (f" | guest stderr: {stderr_tail}" if stderr_tail else ""),
                    exit_code=-1,
                    duration_seconds=time.time() - start,
                    metadata={"backend": "docker-dev", "container": container,
                              "image": tag, "reason": "guest_died"},
                )
        finally:
            # The permit is held by the wrapper until this completes, even if
            # the caller is cancelled while the container is draining.
            await await_teardown(
                self._teardown_container(proc, container, drain_task))

        stdout_text = stdout_text or ""
        stderr_text = stderr_text or ""
        meta: Dict[str, Any] = {
            "backend": "docker-dev",
            "container": container,
            "image": tag,
        }
        if envelope is not None:
            # Structured state — preserved verbatim, immune to stdout cap.
            meta["state_envelope"] = envelope
        if callbacks:
            meta["callbacks"] = callbacks
        return SandboxExecResult(
            success=int(exit_code) == 0,
            stdout=stdout_text[:OUTPUT_CAP],
            stderr=stderr_text[:OUTPUT_CAP],
            exit_code=int(exit_code),
            duration_seconds=time.time() - start,
            truncated=len(stdout_text) > OUTPUT_CAP or len(stderr_text) > OUTPUT_CAP,
            metadata=meta,
        )

    async def _teardown_container(self, proc, container: str, drain_task) -> None:
        if proc.returncode is None:
            try:
                proc.kill()
            except Exception as exc:  # noqa: BLE001
                raise _cleanup_uncertain(
                    f"docker kill failed: {type(exc).__name__}") from None
        try:
            await proc.wait()
        except Exception as exc:  # noqa: BLE001
            if proc.returncode is None:
                raise _cleanup_uncertain(
                    f"docker wait failed: {type(exc).__name__}") from None
        if proc.returncode is None:
            raise _cleanup_uncertain("docker process exit was not confirmed")
        drain_task.cancel()
        try:
            await drain_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        if proc.returncode not in (0, None):
            await self._remove_container(container)

    async def _remove_container(self, container: str) -> None:
        """Confirm the owned container is removed, or fail closed.

        A killed `docker run` client is not proof its container exited. The
        explicit `docker rm -f` result is authoritative: success means the
        daemon stopped/removed it; exit 1 is accepted only when the stderr is
        the daemon's exact-target "No such container/object" absence. Generic
        exit 1, timeout, connection/daemon errors and unrelated targets are
        cleanup uncertainty, never success.
        """
        deadline = time.monotonic() + _REMOVE_CONFIRM_SECONDS + _REMOVE_TIMEOUT_SECONDS
        try:
            rm = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", container,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:  # noqa: BLE001
            raise _cleanup_uncertain(
                f"docker rm failed: {type(exc).__name__}") from None
        reads = [asyncio.create_task(_read_bounded(rm.stdout)),
                 asyncio.create_task(_read_bounded(rm.stderr))]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*reads, rm.wait(), return_exceptions=True),
                timeout=_REMOVE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            for task in reads:
                task.cancel()
            await self._reap_rm(rm)
            raise _cleanup_uncertain("docker rm timed out") from None
        except Exception as exc:  # noqa: BLE001
            for task in reads:
                task.cancel()
            await self._reap_rm(rm)
            raise _cleanup_uncertain(
                f"docker rm failed: {type(exc).__name__}") from None
        out, err, wait_result = results[0], results[1], results[2]
        if isinstance(out, BaseException) or isinstance(err, BaseException):
            await self._reap_rm(rm)
            if isinstance(out, _CaptureOverflow) or isinstance(err, _CaptureOverflow):
                raise _cleanup_uncertain("docker rm output cap") from None
            raise _cleanup_uncertain("docker rm read failed") from None

        wait_failed = isinstance(wait_result, BaseException)
        if wait_failed:
            # A failed wait leaves the CLI/container status unresolved: finish
            # the bounded kill/reap attempt before deciding.
            await self._reap_rm(rm)
        rc = _valid_returncode(rm)
        if wait_failed and rc is None:
            raise _cleanup_uncertain("docker rm wait failed; exit unknown")
        if rc == 0:
            return
        if rc is None:
            raise _cleanup_uncertain("docker rm status invalid")
        if _known_absent(out, err, container):
            return
        if wait_failed:
            raise _cleanup_uncertain("docker rm wait failed")
        if _removal_in_progress(out, err, container):
            await self._confirm_container_removed(
                container, deadline=deadline)
            return
        raise _cleanup_uncertain(
            f"docker rm did not confirm removal (exit {rc})")

    async def _confirm_container_removed(self, container: str, *,
                                         deadline: float) -> None:
        """Poll exact owned-target status until absent or the deadline.

        `removal ... already in progress` is NOT absence. Docker --rm can
        report that race while it finishes removing the container. Confirm via
        `docker inspect` exact-target absence within the cleanup deadline;
        persistent present/removing/error/invalid output is uncertainty.
        """
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _cleanup_uncertain(
                    "docker removal not confirmed before cleanup deadline")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "--format", "{{.State.Status}}",
                    container,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except Exception as exc:  # noqa: BLE001
                raise _cleanup_uncertain(
                    f"docker inspect failed: {type(exc).__name__}") from None
            reads = [asyncio.create_task(_read_bounded(proc.stdout)),
                     asyncio.create_task(_read_bounded(proc.stderr))]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*reads, proc.wait(),
                                   return_exceptions=True),
                    timeout=min(2.0, remaining))
            except asyncio.TimeoutError:
                for task in reads:
                    task.cancel()
                await self._reap_rm(proc)
                raise _cleanup_uncertain("docker inspect timed out") from None
            except Exception as exc:  # noqa: BLE001
                for task in reads:
                    task.cancel()
                await self._reap_rm(proc)
                raise _cleanup_uncertain(
                    f"docker inspect failed: {type(exc).__name__}") from None
            out, err, wait_result = results[0], results[1], results[2]
            if isinstance(out, BaseException) or isinstance(err, BaseException):
                await self._reap_rm(proc)
                raise _cleanup_uncertain("docker inspect read failed") from None
            if isinstance(wait_result, BaseException):
                await self._reap_rm(proc)
                raise _cleanup_uncertain("docker inspect wait failed") from None
            rc = _valid_returncode(proc)
            if rc is None:
                await self._reap_rm(proc)
                raise _cleanup_uncertain("docker inspect status invalid")
            if rc == 0:
                status = bytes(out or b"").decode("utf-8", "replace").strip()
                if status not in ("running", "exited", "paused", "restarting",
                                  "removing", "created", "dead"):
                    await self._reap_rm(proc)
                    raise _cleanup_uncertain(
                        "docker inspect target status unknown")
                await asyncio.sleep(_REMOVE_POLL_INTERVAL)
                continue
            if _known_absent_inspect(out, err, container):
                return
            await self._reap_rm(proc)
            raise _cleanup_uncertain(
                f"docker inspect did not confirm absence (exit {rc})")

    async def _reap_rm(self, rm) -> None:
        try:
            if rm.returncode is None:
                rm.kill()
        except Exception:  # noqa: BLE001
            pass
        try:
            await asyncio.wait_for(rm.wait(), timeout=2)
        except BaseException:  # noqa: BLE001 - cleanup must not mask uncertainty
            pass

    async def _ensure_image(self, tag: str, deps: List[str]) -> Optional[str]:
        """Build ``tag`` if absent; return None on success, error text on failure.

        Dependency images build FROM the local base image, so ensure that
        first. Builds are serialized (dev host) and double-checked under the
        lock — concurrent dev-runs of the same dep set build once.
        """
        if await asyncio.to_thread(_image_exists, tag):
            return None
        async with self._build_sem():
            if await asyncio.to_thread(_image_exists, tag):
                return None
            if deps and not await asyncio.to_thread(_image_exists, BASE_TAG):
                err = await self._build_image(BASE_TAG, [])
                if err is not None:
                    return f"base image build failed: {err}"
            return await self._build_image(tag, deps)

    async def _build_image(self, tag: str, deps: List[str]) -> Optional[str]:
        build_dir = tempfile.mkdtemp(prefix=f"{IMAGE_REPO}-build-")
        try:
            with open(os.path.join(build_dir, "Dockerfile"), "w", encoding="utf-8") as f:
                f.write(_dev_dockerfile(tag, deps))
            shutil.copyfile(_AGENT_SOURCE, os.path.join(build_dir, "agent.py"))
            if deps:
                with open(os.path.join(build_dir, "requirements.txt"), "w",
                          encoding="utf-8") as f:
                    f.write("\n".join(deps) + "\n")
            proc = await asyncio.create_subprocess_exec(
                "docker", "build", "-t", tag, build_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(),
                                                timeout=_BUILD_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"docker build exceeded {_BUILD_TIMEOUT_SECONDS}s"
            if proc.returncode != 0:
                return (out or b"").decode("utf-8", "replace")[-4000:] or (
                    f"docker build exited {proc.returncode}"
                )
            logger.info("docker-dev image ready: %s (deps=%d)", tag, len(deps))
            return None
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)


def _image_exists(tag: str) -> bool:
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True, timeout=15,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _max_concurrency() -> int:
    try:
        return max(1, int(os.getenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "4")))
    except (TypeError, ValueError):
        return 4
