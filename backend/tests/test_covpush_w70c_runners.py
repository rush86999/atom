"""Coverage wave W70c — Firecracker/Docker sandbox runners + ingestion/federation
routes + restricted pickle.

Targets (>=95% statement coverage, standalone):
- core/sandbox_runtime/firecracker_runner.py   (Firecracker microVM runner; 78% before)
- core/sandbox_runtime/docker_runner.py        (Docker sandbox runner; 53% before)
- api/routes/ingestion_crud_routes.py          (ingestion CRUD endpoint matrix; 66% before)
- api/routes/federation_routes.py              (DIDs/VCs zero-trust federation; 57% before)
- core/llm/routing/restricted_pickle.py        (restricted unpickler)

Pattern: mocked deps everywhere — no Firecracker binary, no Docker daemon, no
LLM, no network, no DB. Firecracker subprocess/vsock are fully mocked (fake
procs, fake readers/writers, AsyncMock _exchange). Routes use TestClient with
dependency_overrides + patches on the REAL module names (no `backend.` prefix).

Bug found + fixed in the assigned modules (regression tests below):
1. firecracker_runner.py:182 — `_sem()` read `self._concurrency_sem._bound_loop`,
   an attribute that only exists on Python 3.12+; on 3.11 the FIRST call worked
   only because of the `None` short-circuit, and any SECOND `execute_python` on
   the same runtime instance raised AttributeError inside the semaphore guard.
   Fixed to probe `_bound_loop` then `_loop` (3.11 binding) —
   test_sem_repeated_calls_no_crash / test_sem_recreated_across_loops.
"""
import asyncio
import io
import json
import os
import pickle
import sys
import tempfile
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.sandbox_policy import SandboxPolicy
from core.sandbox_runtime.base import SandboxExecResult
from core.sandbox_runtime import docker_runner as docker_mod
from core.sandbox_runtime import firecracker_runner as fr


def _policy(**kw):
    defaults = dict(
        run_id="run-1",
        agent_id="agent-1",
        tier_at_issuance="SUPERVISED",
        max_bytes_written=1000,
        max_exec_seconds=30,
        max_tool_calls=5,
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


def _utc(day):
    return datetime(2026, 1, day, 12, 0, 0, tzinfo=timezone.utc)


EID_1 = "11111111-1111-1111-1111-111111111111"
EID_2 = "22222222-2222-2222-2222-222222222222"
EID_3 = "33333333-3333-3333-3333-333333333333"


# ===========================================================================
# core/sandbox_runtime/firecracker_runner.py
# ===========================================================================


class TestFirecrackerProbes:
    def test_get_kernel_image_unset(self, monkeypatch):
        monkeypatch.delenv(fr.KERNEL_IMAGE_ENV, raising=False)
        assert fr.get_kernel_image() is None

    def test_get_kernel_image_set(self, monkeypatch):
        monkeypatch.setenv(fr.KERNEL_IMAGE_ENV, "/kern/vmlinux")
        assert fr.get_kernel_image() == "/kern/vmlinux"

    def test_get_rootfs_template_default(self, monkeypatch):
        monkeypatch.delenv(fr.ROOTFS_TEMPLATE_ENV, raising=False)
        assert fr.get_rootfs_template() == fr.DEFAULT_ROOTFS_TEMPLATE

    def test_get_rootfs_template_env(self, monkeypatch):
        monkeypatch.setenv(fr.ROOTFS_TEMPLATE_ENV, "/img/base.ext4")
        assert fr.get_rootfs_template() == "/img/base.ext4"

    def test_get_guest_port_default(self, monkeypatch):
        monkeypatch.delenv(fr.GUEST_PORT_ENV, raising=False)
        assert fr.get_guest_port() == fr.DEFAULT_GUEST_PORT

    def test_get_guest_port_env(self, monkeypatch):
        monkeypatch.setenv(fr.GUEST_PORT_ENV, "7070")
        assert fr.get_guest_port() == 7070

    def test_get_guest_port_invalid_env(self, monkeypatch):
        monkeypatch.setenv(fr.GUEST_PORT_ENV, "not-a-port")
        assert fr.get_guest_port() == fr.DEFAULT_GUEST_PORT

    def test_get_guest_port_zero_clamped(self, monkeypatch):
        monkeypatch.setenv(fr.GUEST_PORT_ENV, "0")
        assert fr.get_guest_port() == 1

    def test_get_guest_boot_args_default_port(self, monkeypatch):
        monkeypatch.delenv(fr.GUEST_PORT_ENV, raising=False)
        args = fr.get_guest_boot_args()
        assert fr.GUEST_AGENT_INIT in args
        assert f"miniapp_port={fr.DEFAULT_GUEST_PORT}" in args

    def test_get_guest_boot_args_explicit_port(self):
        args = fr.get_guest_boot_args(port=9090)
        assert "miniapp_port=9090" in args

    def test_is_available_not_linux(self, monkeypatch):
        monkeypatch.setattr(fr, "_IS_LINUX", False)
        monkeypatch.setattr(fr.shutil, "which", lambda n: "/usr/bin/firecracker")
        assert fr.is_available() is False

    def test_is_available_no_binary(self, monkeypatch):
        monkeypatch.setattr(fr, "_IS_LINUX", True)
        monkeypatch.setattr(fr.shutil, "which", lambda n: None)
        assert fr.is_available() is False

    def test_is_available_no_kernel_env(self, monkeypatch):
        monkeypatch.setattr(fr, "_IS_LINUX", True)
        monkeypatch.setattr(fr.shutil, "which", lambda n: "/usr/bin/firecracker")
        monkeypatch.setattr(fr, "get_kernel_image", lambda: None)
        assert fr.is_available() is False

    def test_is_available_kernel_missing_file(self, monkeypatch):
        monkeypatch.setattr(fr, "_IS_LINUX", True)
        monkeypatch.setattr(fr.shutil, "which", lambda n: "/usr/bin/firecracker")
        monkeypatch.setattr(fr, "get_kernel_image", lambda: "/kern/missing")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: False)
        assert fr.is_available() is False

    def test_is_available_all_ok(self, monkeypatch):
        monkeypatch.setattr(fr, "_IS_LINUX", True)
        monkeypatch.setattr(fr.shutil, "which", lambda n: "/usr/bin/firecracker")
        monkeypatch.setattr(fr, "get_kernel_image", lambda: "/kern/vmlinux")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: True)
        assert fr.is_available() is True

    def test_is_provisioned_for_not_available(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: False)
        assert fr.is_provisioned_for() is False

    def test_is_provisioned_for_template_missing(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/img/missing.ext4")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: False)
        assert fr.is_provisioned_for() is False

    def test_is_provisioned_for_template_ok(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/img/base.ext4")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: True)
        assert fr.is_provisioned_for() is True

    def test_is_provisioned_for_custom_image_skips_template(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/img/base.ext4")
        assert fr.is_provisioned_for(image="/img/app1.ext4") is True

    def test_max_concurrency_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", raising=False)
        assert fr._max_concurrency() == 4

    def test_max_concurrency_env(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "7")
        assert fr._max_concurrency() == 7

    def test_max_concurrency_invalid(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "abc")
        assert fr._max_concurrency() == 4

    def test_max_concurrency_zero_clamped(self, monkeypatch):
        monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "0")
        assert fr._max_concurrency() == 1

    def test_write_vm_config_contents(self, tmp_path):
        path = str(tmp_path / "config.json")
        fr._write_vm_config(
            path,
            vm_id="atom-fc-42",
            kernel_image="/kern/vmlinux",
            boot_args="console=ttyS0 miniapp_port=5050",
            mem_mb=256,
            vcpus=2,
            rootfs="/img/base.ext4",
            vsock_uds="/run/vsock.sock",
        )
        cfg = json.loads(open(path).read())
        assert cfg["boot-source"]["kernel_image_path"] == "/kern/vmlinux"
        assert cfg["machine-config"]["vcpu_count"] == 2
        assert cfg["machine-config"]["mem_size_mib"] == 256
        assert cfg["drives"][0]["drive_id"] == "rootfs"
        assert cfg["drives"][0]["path_on_host"] == "/img/base.ext4"
        assert cfg["drives"][0]["is_root_device"] is True
        assert cfg["drives"][0]["is_read_only"] is True
        assert cfg["vsock"]["guest_cid"] == fr.GUEST_CID
        assert cfg["vsock"]["uds_path"] == "/run/vsock.sock"
        assert cfg["_atom"]["vm_id"] == "atom-fc-42"


class _FakeProc:
    """Mimics asyncio.subprocess.Process for the mocked create_subprocess_exec."""

    def __init__(self, returncode=None):
        self.returncode = returncode
        self.killed = False
        self.waited = 0

    def kill(self):
        self.returncode = -9
        self.killed = True

    async def wait(self):
        self.waited += 1
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class _FakeProcWaitRaises(_FakeProc):
    async def wait(self):
        raise RuntimeError("wait failed")


class TestFirecrackerRuntime:
    @pytest.fixture
    def provisioned(self, monkeypatch, tmp_path):
        """is_available True + temp run dir + fast sandbox config."""
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "get_kernel_image", lambda: "/kern/vmlinux")
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/img/base.ext4")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: True)
        monkeypatch.setattr("tempfile.mkdtemp", lambda *a, **k: str(tmp_path))
        monkeypatch.setattr(fr.shutil, "rmtree", lambda *a, **k: None)
        monkeypatch.setattr(fr.sandbox_config, "get_sandbox_vm_mem_mb", lambda: 256)
        monkeypatch.setattr(fr.sandbox_config, "get_sandbox_vm_vcpus", lambda: 1)
        monkeypatch.setattr(
            fr.sandbox_config, "get_sandbox_vm_boot_timeout_seconds", lambda: 1
        )
        return tmp_path

    def _set_subprocess(self, monkeypatch, proc):
        async def _spawn(*a, **k):
            return proc

        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", _spawn)

    def test_sem_same_loop_returns_same(self):
        runtime = fr.FirecrackerRuntime()

        async def _go():
            s1 = runtime._sem()
            s2 = runtime._sem()
            async with s1:
                pass
            return s1, s2

        s1, s2 = asyncio.run(_go())
        assert s1 is s2

    def test_sem_recreated_across_loops(self):
        runtime = fr.FirecrackerRuntime()
        loop1 = asyncio.new_event_loop()
        s1 = None

        async def _grab():
            nonlocal s1
            s1 = runtime._sem()
            async with s1:
                pass

        loop1.run_until_complete(_grab())
        # On 3.12 the Semaphore captures its loop at construction
        # (_bound_loop); on 3.11 the binding is lazy (``_loop`` stays None
        # until the semaphore is contended). Simulate the construction-time
        # binding to exercise the recreate branch on both versions.
        if not hasattr(s1, "_bound_loop") and getattr(s1, "_loop", None) is None:
            s1._loop = loop1  # type: ignore[attr-defined]
        loop1.close()

        loop2 = asyncio.new_event_loop()
        s2 = None

        async def _grab2():
            nonlocal s2
            s2 = runtime._sem()
            async with s2:
                pass

        loop2.run_until_complete(_grab2())
        loop2.close()
        assert s1 is not s2

    def test_sem_repeated_calls_no_crash(self):
        """REGRESSION: `_bound_loop` is 3.12-only; on 3.11 the second _sem()
        call raised AttributeError (first call only survived via the None
        short-circuit). Fixed to probe `_bound_loop` then `_loop`."""
        runtime = fr.FirecrackerRuntime()

        async def _go():
            async with runtime._sem():
                pass
            async with runtime._sem():
                pass
            return True

        assert asyncio.run(_go()) is True
        assert runtime._concurrency_sem is not None

    def test_execute_python_unavailable(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: False)
        runtime = fr.FirecrackerRuntime()
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is False
        assert result.exit_code == -1
        assert "unavailable" in result.stderr
        assert result.metadata["reason"] == "unavailable"
        assert result.metadata["backend"] == "firecracker"

    def test_execute_python_rootfs_missing(self, monkeypatch):
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/img/missing.ext4")
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: False)
        runtime = fr.FirecrackerRuntime()
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is False
        assert "Rootfs not found" in result.stderr
        assert result.metadata["reason"] == "rootfs_missing"

    def test_execute_command_wraps_subprocess(self):
        runtime = fr.FirecrackerRuntime()
        runtime.execute_python = AsyncMock(
            return_value=SandboxExecResult(success=True, stdout="o", stderr="", exit_code=0)
        )
        result = asyncio.run(
            runtime.execute_command("ls -la", policy=_policy(), env={"A": "1"})
        )
        assert result.success is True
        code = runtime.execute_python.call_args[0][0]
        assert "subprocess.run('ls -la'" in code
        assert "sys.exit(_r.returncode)" in code
        assert runtime.execute_python.call_args[1]["inputs"] == {"A": "1"}

    def test_cleanup_noop(self):
        runtime = fr.FirecrackerRuntime()
        assert asyncio.run(runtime.cleanup()) is None

    def test_run_in_vm_success_with_envelope_callbacks_and_truncation(
        self, monkeypatch, tmp_path, provisioned
    ):
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(
            return_value=(
                "x" * 70000,
                "y" * 70000,
                0,
                {"state": {"n": 1}},
                [{"kind": "fetch_integration", "ok": True}],
            )
        )
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is True
        assert len(result.stdout) == fr.OUTPUT_CAP
        assert len(result.stderr) == fr.OUTPUT_CAP
        assert result.truncated is True
        assert result.metadata["state_envelope"] == {"state": {"n": 1}}
        assert result.metadata["callbacks"] == [{"kind": "fetch_integration", "ok": True}]
        assert result.metadata["vm_id"].startswith("atom-fc-")
        assert proc.killed is True  # VM torn down after the exchange
        cfg = json.loads((tmp_path / "config.json").read_text())
        assert cfg["boot-source"]["kernel_image_path"] == "/kern/vmlinux"
        assert "miniapp_port=" in cfg["boot-source"]["boot_args"]

    def test_run_in_vm_success_no_envelope_no_callbacks(self, monkeypatch, provisioned):
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is True
        assert result.stdout == "out"
        assert result.truncated is False
        assert "state_envelope" not in result.metadata
        assert "callbacks" not in result.metadata

    def test_run_in_vm_nonzero_exit(self, monkeypatch, provisioned):
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("", "boom", 2, None, []))
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is False
        assert result.exit_code == 2
        assert result.stderr == "boom"

    def test_run_in_vm_timeout(self, monkeypatch, provisioned):
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(side_effect=asyncio.TimeoutError())
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is False
        assert result.exit_code == -1
        assert "timeout" in result.stderr.lower()
        assert result.metadata["timeout"] is True
        assert result.metadata["vm_id"].startswith("atom-fc-")
        assert proc.killed is True

    def test_run_in_vm_binary_missing(self, monkeypatch, provisioned):
        async def _spawn(*a, **k):
            raise FileNotFoundError()

        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", _spawn)
        runtime = fr.FirecrackerRuntime()
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is False
        assert result.exit_code == -1
        assert "not found" in result.stderr
        assert result.metadata["reason"] == "binary_missing"

    def test_run_in_vm_proc_already_exited_no_kill(self, monkeypatch, provisioned):
        proc = _FakeProc(returncode=0)
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is True
        assert proc.killed is False
        assert proc.waited == 1

    def test_run_in_vm_proc_wait_exception_swallowed(self, monkeypatch, provisioned):
        proc = _FakeProcWaitRaises()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is True

    def test_run_in_vm_rmtree_exception_swallowed(self, monkeypatch, provisioned):
        def _bad_rmtree(*a, **k):
            raise OSError("permission denied")

        monkeypatch.setattr(fr.shutil, "rmtree", _bad_rmtree)
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        result = asyncio.run(runtime.execute_python("x = 1", policy=_policy()))
        assert result.success is True

    def test_run_in_vm_timeout_clamped_policy(self, monkeypatch, provisioned):
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        policy = type("P", (), {"max_exec_seconds": -5})()
        result = asyncio.run(runtime.execute_python("x = 1", policy=policy))
        assert result.success is True

    def test_run_in_vm_uses_image_rootfs(self, monkeypatch, tmp_path, provisioned):
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: True)
        custom = tmp_path / "custom.ext4"
        custom.write_bytes(b"ext4!")
        proc = _FakeProc()
        self._set_subprocess(monkeypatch, proc)
        runtime = fr.FirecrackerRuntime()
        runtime._exchange = AsyncMock(return_value=("out", "", 0, None, []))
        asyncio.run(
            runtime.execute_python("x = 1", policy=_policy(), image=str(custom))
        )
        runtime._exchange.assert_awaited_once()

    def test_run_in_vm_missing_image_rootfs(self, monkeypatch, provisioned):
        monkeypatch.setattr(fr.os.path, "isfile", lambda p: False)
        runtime = fr.FirecrackerRuntime()
        result = asyncio.run(
            runtime.execute_python(
                "x = 1", policy=_policy(), image="/img/never.ext4"
            )
        )
        assert result.success is False
        assert result.metadata["reason"] == "rootfs_missing"


class TestFirecrackerExchange:
    class _FakeReader:
        def __init__(self, lines):
            self._lines = list(lines)

        async def readline(self):
            if not self._lines:
                return b""
            return self._lines.pop(0)

    class _FakeWriter:
        def __init__(self, close_error=False):
            self.written = []
            self.closed = False
            self.close_error = close_error

        def write(self, b):
            self.written.append(b)

        async def drain(self):
            pass

        def close(self):
            if self.close_error:
                raise RuntimeError("close failed")
            self.closed = True

    def _setup(self, monkeypatch, lines, writer=None):
        reader = self._FakeReader(lines)
        writer = writer or self._FakeWriter()
        monkeypatch.setattr(fr.asyncio, "open_unix_connection",
                            AsyncMock(return_value=(reader, writer)))
        monkeypatch.setattr(fr.os.path, "exists", lambda p: True)
        monkeypatch.setattr(
            fr.sandbox_config, "get_sandbox_vm_boot_timeout_seconds", lambda: 1
        )
        return reader, writer

    def test_exchange_untagged_legacy_final(self, monkeypatch):
        line = json.dumps({"stdout": "out", "stderr": "err", "exit_code": 3})
        _, writer = self._setup(monkeypatch, [line.encode()])
        runtime = fr.FirecrackerRuntime()
        stdout, stderr, code, envelope, callbacks = asyncio.run(
            runtime._exchange("code", {}, "/run/vsock.sock")
        )
        assert (stdout, stderr, code) == ("out", "err", 3)
        assert envelope is None
        assert callbacks == []
        assert writer.closed is True
        assert b'"type": "exec"' in writer.written[0]

    def test_exchange_final_with_envelope(self, monkeypatch):
        line = json.dumps(
            {"type": "final", "stdout": "o", "stderr": "", "exit_code": 0,
             "state_envelope": {"state": {"n": 2}}}
        )
        _, writer = self._setup(monkeypatch, [line.encode()])
        runtime = fr.FirecrackerRuntime()
        stdout, stderr, code, envelope, callbacks = asyncio.run(
            runtime._exchange("code", {}, "/run/vsock.sock")
        )
        assert stdout == "o"
        assert code == 0
        assert envelope == {"state": {"n": 2}}
        assert callbacks == []

    def test_exchange_envelope_non_dict_becomes_none(self, monkeypatch):
        line = json.dumps(
            {"type": "final", "stdout": "o", "stderr": "", "exit_code": 0,
             "state_envelope": "not-a-dict"}
        )
        self._setup(monkeypatch, [line.encode()])
        runtime = fr.FirecrackerRuntime()
        *_, envelope, _ = asyncio.run(runtime._exchange("code", {}, "/run/vsock.sock"))
        assert envelope is None

    def test_exchange_callback_serviced_then_final(self, monkeypatch):
        cb = json.dumps({
            "type": "callback", "kind": "fetch_integration",
            "service": "hubspot", "action": "list", "params": {},
        })
        final = json.dumps({"type": "final", "stdout": "done", "stderr": "",
                            "exit_code": 0})
        _, writer = self._setup(monkeypatch, [cb.encode(), final.encode()])
        runtime = fr.FirecrackerRuntime()
        handler = AsyncMock(return_value={"ok": True, "data": [1, 2]})
        stdout, stderr, code, envelope, callbacks = asyncio.run(
            runtime._exchange("code", {}, "/run/vsock.sock", handler)
        )
        assert stdout == "done"
        assert callbacks == [{
            "kind": "fetch_integration", "service": "hubspot", "action": "list",
            "ok": True, "duration_ms": callbacks[0]["duration_ms"],
        }]
        handler.assert_awaited_once()
        cb_reply = json.loads(writer.written[1])
        assert cb_reply == {"type": "callback_result", "ok": True, "data": [1, 2]}

    def test_exchange_callback_failure_reply(self, monkeypatch):
        cb = json.dumps({
            "type": "callback", "kind": "fetch_integration",
            "service": "hubspot", "action": "list", "params": {},
        })
        final = json.dumps({"type": "final", "stdout": "done", "stderr": "",
                            "exit_code": 0})
        _, writer = self._setup(monkeypatch, [cb.encode(), final.encode()])
        runtime = fr.FirecrackerRuntime()
        handler = AsyncMock(return_value={"ok": False, "error": "denied"})
        asyncio.run(runtime._exchange("code", {}, "/run/vsock.sock", handler))
        cb_reply = json.loads(writer.written[1])
        assert cb_reply == {"type": "callback_result", "ok": False,
                            "error": "denied", "data": None}

    def test_exchange_empty_readline_raises_timeout(self, monkeypatch):
        self._setup(monkeypatch, [])
        runtime = fr.FirecrackerRuntime()
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(runtime._exchange("code", {}, "/run/vsock.sock"))

    def test_exchange_socket_never_appears_raises_timeout(self, monkeypatch):
        monkeypatch.setattr(fr.os.path, "exists", lambda p: False)
        sleep = AsyncMock()
        monkeypatch.setattr(fr.asyncio, "sleep", sleep)
        # deadline calc (0.0) -> first check within deadline (1.0) -> sleeps ->
        # second check past deadline (99999.0) raises.
        ticks = iter([0.0, 1.0, 99999.0])
        monkeypatch.setattr(fr.time, "time", lambda: next(ticks))
        runtime = fr.FirecrackerRuntime()
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(runtime._exchange("code", {}, "/run/vsock.sock"))
        sleep.assert_awaited_once_with(0.05)

    def test_exchange_writer_close_exception_swallowed(self, monkeypatch):
        line = json.dumps({"stdout": "o", "stderr": "", "exit_code": 0})
        writer = self._FakeWriter(close_error=True)
        self._setup(monkeypatch, [line.encode()], writer=writer)
        runtime = fr.FirecrackerRuntime()
        stdout, *_ = asyncio.run(runtime._exchange("code", {}, "/run/vsock.sock"))
        assert stdout == "o"


class TestFirecrackerCallbacks:
    def test_service_callback_disabled(self):
        runtime = fr.FirecrackerRuntime()
        reply, log = asyncio.run(
            runtime._service_callback({"kind": "fetch_integration"}, None)
        )
        assert reply == {"type": "callback_result", "ok": False,
                         "error": "callbacks_disabled"}
        assert log["ok"] is False
        assert log["kind"] == "fetch_integration"

    def test_service_callback_missing_kind(self):
        runtime = fr.FirecrackerRuntime()
        reply, log = asyncio.run(runtime._service_callback({}, None))
        assert reply["error"] == "callbacks_disabled"
        assert log["kind"] == "unknown"

    def test_service_callback_success(self):
        runtime = fr.FirecrackerRuntime()
        handler = AsyncMock(return_value={"ok": True, "data": {"x": 1}})
        reply, log = asyncio.run(
            runtime._service_callback(
                {"kind": "fetch_integration", "service": "s", "action": "a"},
                handler,
            )
        )
        assert reply == {"type": "callback_result", "ok": True, "data": {"x": 1}}
        assert log["ok"] is True
        assert log["service"] == "s"
        assert log["action"] == "a"
        assert "duration_ms" in log

    def test_service_callback_ok_false(self):
        runtime = fr.FirecrackerRuntime()
        handler = AsyncMock(return_value={"ok": False, "error": "nope"})
        reply, log = asyncio.run(
            runtime._service_callback({"kind": "fetch_integration"}, handler)
        )
        assert reply["ok"] is False
        assert reply["error"] == "nope"
        assert log["ok"] is False

    def test_service_callback_exception(self):
        runtime = fr.FirecrackerRuntime()
        handler = AsyncMock(side_effect=RuntimeError("handler crashed"))
        reply, log = asyncio.run(
            runtime._service_callback({"kind": "fetch_integration"}, handler)
        )
        assert reply == {"type": "callback_result", "ok": False, "error": "failed"}
        assert log["error"] == "failed"
        assert log["kind"] == "fetch_integration"


# ===========================================================================
# core/sandbox_runtime/docker_runner.py
# ===========================================================================


class TestDockerRuntime:
    def _fake_to_thread(self, monkeypatch):
        monkeypatch.setattr(
            docker_mod.asyncio,
            "to_thread",
            AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
        )

    def test_init(self):
        runtime = docker_mod.DockerRuntime()
        assert runtime._sandbox is None
        assert isinstance(runtime._init_lock, asyncio.Lock)

    def test_ensure_sandbox_creates_once(self, monkeypatch):
        fake = MagicMock()
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            runtime = docker_mod.DockerRuntime()
            s1 = asyncio.run(runtime._ensure_sandbox())
            s2 = asyncio.run(runtime._ensure_sandbox())
        assert s1 is fake
        assert s2 is fake

    def test_ensure_sandbox_already_set(self):
        runtime = docker_mod.DockerRuntime()
        runtime._sandbox = "prebuilt"
        assert asyncio.run(runtime._ensure_sandbox()) == "prebuilt"

    def test_execute_python_dict_success(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(
            return_value={"success": True, "stdout": "hi", "stderr": "",
                          "returncode": 0}
        )
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(
                runtime.execute_python("print(1)", policy=_policy(max_exec_seconds=10))
            )
        assert result.success is True
        assert result.stdout == "hi"
        assert result.exit_code == 0
        assert result.metadata == {"backend": "docker"}
        fake.execute_python.assert_called_once_with("print(1)", {}, 10, None, None)

    def test_execute_python_exit_code_key(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(
            return_value={"success": False, "stdout": "", "stderr": "err",
                          "exit_code": 3}
        )
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is False
        assert result.exit_code == 3
        assert result.stderr == "err"

    def test_execute_python_missing_rc_defaults_minus_one(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value={"success": True})
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.exit_code == -1
        assert result.stdout == ""

    def test_execute_python_dict_truncation(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(
            return_value={"success": True, "stdout": "x" * 70000,
                          "stderr": "y" * 70000, "returncode": 0}
        )
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert len(result.stdout) == 65536
        assert len(result.stderr) == 65536
        assert result.truncated is True

    def test_execute_python_string_success(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value="output text")
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is True
        assert result.stdout == "output text"
        assert result.stderr == ""
        assert result.exit_code == 0

    def test_execute_python_string_execution_error(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value="EXECUTION_ERROR: boom")
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is False
        assert result.stdout == ""
        assert result.stderr == "EXECUTION_ERROR: boom"
        assert result.exit_code == -1

    def test_execute_python_string_sandbox_error(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value="SANDBOX_ERROR: sandbox blew up")
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is False
        assert result.stderr.startswith("SANDBOX_ERROR:")

    def test_execute_python_string_long_truncated(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value="z" * 70000)
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert len(result.stdout) == 65536
        assert result.truncated is True

    def test_execute_python_empty_string(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value="")
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is True
        assert result.stdout == ""

    def test_execute_python_none_output(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value=None)
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is True
        assert result.stdout == ""

    def test_execute_python_timeout_clamped(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value={"success": True})
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(
                runtime.execute_python("x", policy=_policy(max_exec_seconds=-5))
            )
        assert result.success is True
        fake.execute_python.assert_called_once_with("x", {}, 1, None, None)

    def test_execute_python_none_policy_default_timeout(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value={"success": True})
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=None))
        assert result.success is True
        fake.execute_python.assert_called_once_with("x", {}, 30, None, None)

    def test_execute_python_inputs_and_image(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value={"success": True})
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            self._fake_to_thread(monkeypatch)
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(
                runtime.execute_python(
                    "x", policy=_policy(), inputs={"k": 1}, image="img:1"
                )
            )
        assert result.success is True
        fake.execute_python.assert_called_once_with("x", {"k": 1}, 30, None, "img:1")

    def test_execute_python_exception(self, monkeypatch):
        fake = MagicMock()
        fake.execute_python = MagicMock(return_value={})
        with patch("core.skill_sandbox.HazardSandbox", return_value=fake):
            monkeypatch.setattr(
                docker_mod.asyncio,
                "to_thread",
                AsyncMock(side_effect=RuntimeError("docker daemon down")),
            )
            runtime = docker_mod.DockerRuntime()
            result = asyncio.run(runtime.execute_python("x", policy=_policy()))
        assert result.success is False
        assert result.exit_code == -1
        assert "docker daemon down" in result.stderr
        assert result.metadata["backend"] == "docker"
        assert result.metadata["error"] == "docker daemon down"

    def test_execute_command_wraps_subprocess(self):
        runtime = docker_mod.DockerRuntime()
        runtime.execute_python = AsyncMock(
            return_value=SandboxExecResult(success=True, stdout="o", stderr="", exit_code=0)
        )
        result = asyncio.run(runtime.execute_command("ls", policy=_policy()))
        assert result.success is True
        code = runtime.execute_python.call_args[0][0]
        assert "subprocess.run('ls'" in code
        assert runtime.execute_python.call_args[1]["policy"] is not None

    def test_cleanup_noop(self):
        runtime = docker_mod.DockerRuntime()
        assert asyncio.run(runtime.cleanup()) is None

    def test_parse_legacy_dict_returncode(self):
        result = docker_mod._parse_legacy_output(
            {"success": True, "stdout": "a", "stderr": "b", "returncode": 0}
        )
        assert result.success is True
        assert (result.stdout, result.stderr, result.exit_code) == ("a", "b", 0)
        assert result.truncated is False

    def test_parse_legacy_dict_exit_code(self):
        result = docker_mod._parse_legacy_output(
            {"success": False, "stdout": "a", "exit_code": 7}
        )
        assert result.success is False
        assert result.exit_code == 7

    def test_parse_legacy_dict_missing_fields(self):
        result = docker_mod._parse_legacy_output({})
        assert result.success is False
        assert result.exit_code == -1
        assert result.stdout == ""

    def test_parse_legacy_dict_truncated(self):
        result = docker_mod._parse_legacy_output(
            {"success": True, "stdout": "x" * 70000, "stderr": "y" * 70000,
             "returncode": 0}
        )
        assert len(result.stdout) == 65536
        assert len(result.stderr) == 65536
        assert result.truncated is True


# ===========================================================================
# api/routes/ingestion_crud_routes.py
# ===========================================================================


class TestIngestionCRUDRoutes:
    @pytest.fixture
    def client(self):
        from api.dependencies import get_current_user
        from core.database import get_db
        from api.routes.ingestion_crud_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_db] = lambda: self.db
        yield TestClient(app, raise_server_exceptions=False)

    @pytest.fixture(autouse=True)
    def _user(self):
        self.user = SimpleNamespace(tenant_id="tenant-1", workspace_id="ws-1")
        self.db = MagicMock()
        yield
        self.user = SimpleNamespace(tenant_id="tenant-1", workspace_id="ws-1")

    def _svc(self):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        return patch.object(IngestionCRUDService, "list_entities",
                            MagicMock(return_value=([], 0))), IngestionCRUDService

    @staticmethod
    def _entity(**over):
        e = dict(
            id=EID_1, tenant_id="tenant-1", workspace_id="ws-1",
            sync_job_id="job-1", entity_type_id="et-1",
            _discovered_type="contact", entity_name="Alice",
            properties={"email": "a@x.com"}, confidence_score=0.9,
            source_record_id="s-1", source_record_type="hubspot",
            status="linked", linked_to_graph_node_id="node-1",
            processed_at=_utc(2), created_at=_utc(1), updated_at=_utc(3),
            extraction_metadata={"src": "sync"},
        )
        e.update(over)
        return SimpleNamespace(**e)

    @staticmethod
    def _job(**over):
        j = dict(
            id="j-1", tenant_id="tenant-1", integration_id="hubspot",
            trigger_type="manual", source_connection_id="c-1", status="completed",
            started_at=_utc(2), completed_at=_utc(3), records_fetched=10,
            records_processed=8, entities_extracted=3, relationships_extracted=1,
            error_message=None, error_details={}, total_records=10,
            progress_percentage=80, created_at=_utc(1), updated_at=_utc(3),
        )
        j.update(over)
        return SimpleNamespace(**j)

    # -- serializers (direct unit coverage, avoids response-model validation) --

    def test_serialize_entity_full(self):
        from api.routes.ingestion_crud_routes import serialize_entity

        e = self._entity()
        out = serialize_entity(e)
        assert out["id"] == EID_1
        assert out["tenant_id"] == "tenant-1"
        assert out["workspace_id"] == "ws-1"
        assert out["sync_job_id"] == "job-1"
        assert out["entity_type_id"] == "et-1"
        assert out["_discovered_type"] == "contact"
        assert out["entity_name"] == "Alice"
        assert out["properties"] == {"email": "a@x.com"}
        assert out["confidence_score"] == 0.9
        assert out["source_record_id"] == "s-1"
        assert out["status"] == "linked"
        assert out["linked_to_graph_node_id"] == "node-1"
        assert out["processed_at"] == "2026-01-02T12:00:00+00:00"
        assert out["extraction_metadata"] == {"src": "sync"}

    def test_serialize_entity_none_fields(self):
        from api.routes.ingestion_crud_routes import serialize_entity

        e = self._entity(
            workspace_id=None, sync_job_id=None, entity_type_id=None,
            entity_name=None, properties=None, confidence_score=None,
            source_record_id=None, source_record_type=None, status=None,
            linked_to_graph_node_id=None, processed_at=None, created_at=None,
            updated_at=None, extraction_metadata=None,
        )
        out = serialize_entity(e)
        assert out["workspace_id"] is None
        assert out["sync_job_id"] is None
        assert out["entity_type_id"] is None
        assert out["properties"] == {}
        assert out["confidence_score"] == 0.0
        assert out["status"] == "pending"
        assert out["linked_to_graph_node_id"] is None
        assert out["processed_at"] is None
        assert out["created_at"] is None
        assert out["updated_at"] is None
        assert out["extraction_metadata"] == {}

    def test_serialize_job_full(self):
        from api.routes.ingestion_crud_routes import serialize_job

        j = self._job()
        out = serialize_job(j)
        assert out["id"] == "j-1"
        assert out["integration_id"] == "hubspot"
        assert out["source_connection_id"] == "c-1"
        assert out["status"] == "completed"
        assert out["records_fetched"] == 10
        assert out["entities_extracted"] == 3
        assert out["total_records"] == 10
        assert out["progress_percentage"] == 80
        assert out["error_message"] is None
        assert out["started_at"] == "2026-01-02T12:00:00+00:00"
        assert out["completed_at"] == "2026-01-03T12:00:00+00:00"

    def test_serialize_job_none_fields(self):
        from api.routes.ingestion_crud_routes import serialize_job

        j = self._job(
            source_connection_id=None, started_at=None, completed_at=None,
            records_fetched=None, records_processed=None, entities_extracted=None,
            relationships_extracted=None, error_details=None, total_records=None,
            progress_percentage=None, updated_at=None,
        )
        out = serialize_job(j)
        assert out["source_connection_id"] is None
        assert out["started_at"] is None
        assert out["completed_at"] is None
        assert out["records_fetched"] == 0
        assert out["records_processed"] == 0
        assert out["entities_extracted"] == 0
        assert out["relationships_extracted"] == 0
        assert out["error_details"] == {}
        assert out["total_records"] is None
        assert out["progress_percentage"] == 0
        assert out["updated_at"] is None

    # -- list_pipeline_entities --

    def test_list_entities_success_with_filters(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        entities = [self._entity()]
        with patch.object(IngestionCRUDService, "list_entities",
                          MagicMock(return_value=(entities, 1))) as m:
            resp = client.get(
                "/api/v1/ingestion/hubspot/entities?status=pending&type=contact"
                "&limit=5&offset=10"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["entities"][0]["_discovered_type"] == "contact"
        assert body["entities"][0]["status"] == "linked"
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", integration_id="hubspot",
            status="pending", type="contact", limit=5, offset=10,
        )

    def test_list_entities_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.get("/api/v1/ingestion/hubspot/entities")
        assert resp.status_code == 403
        assert "tenant context" in resp.json()["detail"]

    def test_list_entities_invalid_limit_422(self, client):
        resp = client.get("/api/v1/ingestion/hubspot/entities?limit=0")
        assert resp.status_code == 422

    # -- get_pipeline_entity --

    def test_get_entity_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)):
            resp = client.get(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 200
        assert resp.json()["id"] == EID_1
        assert resp.json()["tenant_id"] == "tenant-1"

    def test_get_entity_not_found(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=None)):
            resp = client.get(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 404

    def test_get_entity_wrong_integration_404(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity(source_record_type="jira")
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)):
            resp = client.get(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 404

    def test_get_entity_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.get(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 403

    # -- delete_pipeline_entity --

    def test_delete_entity_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)), patch.object(
            IngestionCRUDService, "delete_entity", MagicMock(return_value=True)
        ) as m:
            resp = client.delete(
                f"/api/v1/ingestion/hubspot/entities/{EID_1}?performed_by=ops"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "deleted successfully" in body["message"]
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", entity_id=UUID(EID_1), performed_by="ops"
        )

    def test_delete_entity_not_found_404(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=None)):
            resp = client.delete(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 404

    def test_delete_entity_wrong_integration_404(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity(source_record_type="jira")
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)):
            resp = client.delete(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 404

    def test_delete_entity_service_failure_400(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)), patch.object(
            IngestionCRUDService, "delete_entity", MagicMock(return_value=False)
        ):
            resp = client.delete(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 400

    def test_delete_entity_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.delete(f"/api/v1/ingestion/hubspot/entities/{EID_1}")
        assert resp.status_code == 403

    # -- unlink_pipeline_entity --

    def test_unlink_entity_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)), patch.object(
            IngestionCRUDService, "unlink_entity", MagicMock(return_value=True)
        ) as m:
            resp = client.post(
                f"/api/v1/ingestion/hubspot/entities/{EID_1}/unlink?performed_by=ops"
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "unlinked successfully" in resp.json()["message"]
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", entity_id=UUID(EID_1), performed_by="ops"
        )

    def test_unlink_entity_not_found_404(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=None)):
            resp = client.post(f"/api/v1/ingestion/hubspot/entities/{EID_1}/unlink")
        assert resp.status_code == 404

    def test_unlink_entity_service_failure_400(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()
        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=ent)), patch.object(
            IngestionCRUDService, "unlink_entity", MagicMock(return_value=False)
        ):
            resp = client.post(f"/api/v1/ingestion/hubspot/entities/{EID_1}/unlink")
        assert resp.status_code == 400

    def test_unlink_entity_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.post(f"/api/v1/ingestion/hubspot/entities/{EID_1}/unlink")
        assert resp.status_code == 403

    # -- bulk_delete_pipeline_entities --

    def test_bulk_delete_success(self, client):
        from uuid import UUID

        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()

        def fake_get(db, tenant_id, eid):
            return ent if str(eid) in (EID_1, EID_2) else None

        with patch.object(IngestionCRUDService, "get_entity",
                          side_effect=fake_get), patch.object(
            IngestionCRUDService, "bulk_delete_entities",
            MagicMock(return_value=2),
        ) as m:
            resp = client.post(
                "/api/v1/ingestion/hubspot/entities/bulk-delete?performed_by=ops",
                json={"entity_ids": [EID_1, EID_2]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "deleted 2 out of 2" in body["message"]
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1",
            entity_ids=[UUID(EID_1), UUID(EID_2)], performed_by="ops",
        )

    def test_bulk_delete_filters_foreign_entities(self, client):
        from uuid import UUID

        from api.routes.ingestion_crud_routes import IngestionCRUDService

        ent = self._entity()

        def fake_get(db, tenant_id, eid):
            if str(eid) == EID_1:
                return ent
            if str(eid) == EID_2:
                return self._entity(source_record_type="jira")
            return None

        with patch.object(IngestionCRUDService, "get_entity",
                          side_effect=fake_get), patch.object(
            IngestionCRUDService, "bulk_delete_entities", MagicMock(return_value=1)
        ) as m:
            resp = client.post(
                "/api/v1/ingestion/hubspot/entities/bulk-delete",
                json={"entity_ids": [EID_1, EID_2, EID_3]},
            )
        assert resp.status_code == 200
        assert "deleted 1 out of 3" in resp.json()["message"]
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", entity_ids=[UUID(EID_1)],
            performed_by="system",
        )

    def test_bulk_delete_no_valid_ids_400(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        with patch.object(IngestionCRUDService, "get_entity",
                          MagicMock(return_value=None)):
            resp = client.post(
                "/api/v1/ingestion/hubspot/entities/bulk-delete",
                json={"entity_ids": [EID_1]},
            )
        assert resp.status_code == 400
        assert "No valid entity IDs" in resp.json()["detail"]

    def test_bulk_delete_empty_list_422(self, client):
        resp = client.post(
            "/api/v1/ingestion/hubspot/entities/bulk-delete",
            json={"entity_ids": []},
        )
        assert resp.status_code == 422

    def test_bulk_delete_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.post(
            "/api/v1/ingestion/hubspot/entities/bulk-delete",
            json={"entity_ids": [EID_1]},
        )
        assert resp.status_code == 403

    # -- list_pipeline_jobs --

    def test_list_jobs_tenant_scoped_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        jobs = [self._job()]
        with patch.object(IngestionCRUDService, "list_jobs",
                          MagicMock(return_value=(jobs, 1))) as m:
            resp = client.get("/api/v1/ingestion/hubspot/jobs?status=completed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["integration_id"] == "hubspot"
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", workspace_id="ws-1",
            integration_id="hubspot", status="completed", limit=50, offset=0,
        )

    def test_list_jobs_tenant_scoped_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.get("/api/v1/ingestion/hubspot/jobs")
        assert resp.status_code == 403

    def test_list_jobs_personal_scoped_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        with patch.object(IngestionCRUDService, "list_jobs",
                          MagicMock(return_value=([], 0))) as m:
            resp = client.get("/api/v1/ingestion/gmail/jobs")
        assert resp.status_code == 200
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", workspace_id="ws-1",
            integration_id="gmail", status=None, limit=50, offset=0,
        )

    def test_list_jobs_personal_case_insensitive(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        self.user = SimpleNamespace(tenant_id="tenant-1", workspace_id=None)
        with patch.object(IngestionCRUDService, "list_jobs",
                          MagicMock(return_value=([], 0))):
            resp = client.get("/api/v1/ingestion/OUTLOOK/jobs")
        assert resp.status_code == 403  # personal integration, no workspace

    def test_list_jobs_personal_no_workspace_403(self, client):
        self.user = SimpleNamespace(tenant_id="tenant-1", workspace_id=None)
        resp = client.get("/api/v1/ingestion/gmail/jobs")
        assert resp.status_code == 403
        assert "workspace context" in resp.json()["detail"]

    # -- get_pipeline_status --

    def test_get_status_success(self, client):
        from api.routes.ingestion_crud_routes import IngestionCRUDService

        stats = {"integration_id": "hubspot", "status_counts": {"pending": 1},
                 "error_rate": 0.0, "last_sync_time": "2026-01-01T00:00:00+00:00",
                 "latest_job_status": "completed"}
        with patch.object(IngestionCRUDService, "get_status",
                          MagicMock(return_value=stats)) as m:
            resp = client.get("/api/v1/ingestion/hubspot/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["integration_id"] == "hubspot"
        assert body["status_counts"] == {"pending": 1}
        assert body["error_rate"] == 0.0
        assert body["last_sync_time"] == "2026-01-01T00:00:00+00:00"
        assert body["latest_job_status"] == "completed"
        m.assert_called_once_with(
            db=self.db, tenant_id="tenant-1", integration_id="hubspot"
        )

    def test_get_status_no_tenant_403(self, client):
        self.user = SimpleNamespace(tenant_id=None, workspace_id="ws-1")
        resp = client.get("/api/v1/ingestion/hubspot/status")
        assert resp.status_code == 403


# ===========================================================================
# api/routes/federation_routes.py
# ===========================================================================


class TestFederationRoutes:
    @pytest.fixture
    def client(self):
        from core.auth import get_current_user
        from api.routes.federation_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="u-70c", email="fed@example.com"
        )
        return TestClient(app, raise_server_exceptions=False)

    # -- DIDs --

    def test_create_did_success(self, client):
        doc = SimpleNamespace(to_dict=lambda: {"id": "did:atom:abc"})
        manager = MagicMock()
        manager.generate_did.return_value = "did:atom:abc"
        manager.create_did_document.return_value = doc
        with patch("core.identity.did_manager.get_did_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/dids",
                json={"entity_type": "agent", "entity_id": "agent-1",
                      "services": {"endpoint": "https://a.example"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["did"] == "did:atom:abc"
        assert body["document"] == {"id": "did:atom:abc"}
        from core.identity.did_manager import DIDType

        assert manager.generate_did.call_args.kwargs["entity_type"] == DIDType.AGENT
        assert manager.generate_did.call_args.kwargs["entity_id"] == "agent-1"
        assert manager.create_did_document.call_args.kwargs["services"] == {
            "endpoint": "https://a.example"
        }

    def test_create_did_invalid_entity_type(self, client):
        resp = client.post(
            "/federation/dids",
            json={"entity_type": "rocket", "entity_id": "x"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body
        assert "Invalid entity_type" in body["error"]

    def test_create_did_document_without_to_dict(self, client):
        manager = MagicMock()
        manager.generate_did.return_value = "did:atom:abc"
        manager.create_did_document.return_value = "<raw document>"
        with patch("core.identity.did_manager.get_did_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/dids",
                json={"entity_type": "workspace", "entity_id": "ws-1"},
            )
        assert resp.status_code == 200
        assert resp.json()["document"] == "<raw document>"

    def test_resolve_did_success(self, client):
        doc = SimpleNamespace(to_dict=lambda: {"id": "did:atom:abc"})
        manager = MagicMock()
        manager.resolve_did.return_value = doc
        with patch("core.identity.did_manager.get_did_manager",
                   return_value=manager):
            resp = client.get("/federation/dids/did:atom:abc")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is True
        assert body["document"] == {"id": "did:atom:abc"}

    def test_resolve_did_failure_generic(self, client):
        manager = MagicMock()
        manager.resolve_did.side_effect = RuntimeError("secret-did-detail")
        with patch("core.identity.did_manager.get_did_manager",
                   return_value=manager):
            resp = client.get("/federation/dids/did:atom:abc")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is False
        assert "secret-did-detail" not in resp.text
        assert body["error"] == "DID resolution failed"

    # -- credentials --

    def test_create_credential_success(self, client):
        manager = MagicMock()
        vc = SimpleNamespace(id="vc-1")
        manager.create_credential.return_value = vc
        with patch("core.identity.verifiable_credentials.get_vc_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/credentials",
                json={"issuer_did": "did:atom:issuer",
                      "credential_type": "AgentIdentityCredential",
                      "subject_did": "did:atom:subject",
                      "claims": {"name": "alice"}, "expiry_days": 30},
            )
        assert resp.status_code == 200
        assert resp.json() == {"credential_id": "vc-1", "issued": True}
        from core.identity.verifiable_credentials import VCType

        assert manager.create_credential.call_args.kwargs["credential_type"] == (
            VCType.AGENT_IDENTITY
        )
        assert manager.create_credential.call_args.kwargs["issuer_did"] == (
            "did:atom:issuer"
        )
        assert manager.create_credential.call_args.kwargs["subject_did"] == (
            "did:atom:subject"
        )
        assert manager.create_credential.call_args.kwargs["claims"] == {
            "name": "alice"
        }
        assert manager.create_credential.call_args.kwargs["expiry_days"] == 30

    def test_create_credential_invalid_type(self, client):
        resp = client.post(
            "/federation/credentials",
            json={"issuer_did": "did:atom:issuer",
                  "credential_type": "BogusCredential",
                  "subject_did": "did:atom:subject"},
        )
        assert resp.status_code == 200
        assert "Invalid credential_type" in resp.json()["error"]

    def test_create_credential_defaults(self, client):
        manager = MagicMock()
        manager.create_credential.return_value = "raw-vc"
        with patch("core.identity.verifiable_credentials.get_vc_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/credentials",
                json={"issuer_did": "did:atom:issuer", "subject_did": "did:atom:s"},
            )
        assert resp.status_code == 200
        assert resp.json()["credential_id"] == "raw-vc"

    def test_revoke_credential_success(self, client):
        manager = MagicMock()
        manager.revoke_credential.return_value = True
        with patch("core.identity.verifiable_credentials.get_vc_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/credentials/vc-1/revoke",
                json={"reason": "compromised"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"credential_id": "vc-1", "revoked": True}
        manager.revoke_credential.assert_called_once_with(
            "vc-1", reason="compromised"
        )

    def test_revoke_credential_failure(self, client):
        manager = MagicMock()
        manager.revoke_credential.return_value = False
        with patch("core.identity.verifiable_credentials.get_vc_manager",
                   return_value=manager):
            resp = client.post("/federation/credentials/vc-1/revoke", json={})
        assert resp.status_code == 200
        assert resp.json()["revoked"] is False
        manager.revoke_credential.assert_called_once_with("vc-1", reason=None)

    # -- verify --

    def test_verify_allowed(self, client):
        from core.federation.zero_trust_security import AccessAction

        manager = MagicMock()
        decision = SimpleNamespace(
            allowed=True,
            reason=SimpleNamespace(value="valid_credentials"),
            security_level="high",
        )
        manager.verify_request.return_value = decision
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/verify",
                json={
                    "method": "POST",
                    "path": "/api/data",
                    "headers": {"X-Custom": "1"},
                    "source_did": "did:atom:src",
                    "instance_id": "inst-9",
                    "action": "write",
                    "resource_type": "dataset",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is True
        assert body["reason"] == "valid_credentials"
        assert body["security_level"] == "high"
        fed = manager.verify_request.call_args.args[0]
        assert fed.method == "POST"
        assert fed.path == "/api/data"
        assert fed.action == AccessAction.WRITE
        assert fed.resource_type == "dataset"
        assert fed.headers["X-Source-DID"] == "did:atom:src"
        assert fed.headers["X-Instance-ID"] == "inst-9"
        assert fed.headers["X-Custom"] == "1"

    def test_verify_existing_headers_kept(self, client):
        from core.federation.zero_trust_security import AccessAction

        manager = MagicMock()
        manager.verify_request.return_value = SimpleNamespace(
            allowed=True, reason=SimpleNamespace(value="valid_credentials"),
            security_level="low",
        )
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/verify",
                json={"headers": {"X-Source-DID": "did:already"},
                      "source_did": "did:convenience"},
            )
        assert resp.status_code == 200
        fed = manager.verify_request.call_args.args[0]
        assert fed.headers["X-Source-DID"] == "did:already"
        assert fed.action == AccessAction.READ

    def test_verify_invalid_action_falls_back_to_read(self, client):
        manager = MagicMock()
        manager.verify_request.return_value = SimpleNamespace(
            allowed=True, reason=SimpleNamespace(value="valid_credentials"),
            security_level="medium",
        )
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.post(
                "/federation/verify",
                json={"action": "teleport"},
            )
        assert resp.status_code == 200
        from core.federation.zero_trust_security import AccessAction

        assert manager.verify_request.call_args.args[0].action == AccessAction.READ

    def test_verify_denied_without_enum_reason(self, client):
        manager = MagicMock()
        decision = SimpleNamespace(allowed=False, reason="denied")
        manager.verify_request.return_value = decision
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.post("/federation/verify", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is False
        assert body["reason"] == "denied"
        assert body["security_level"] == "unknown"

    def test_verify_decision_without_allowed(self, client):
        manager = MagicMock()
        manager.verify_request.return_value = SimpleNamespace(reason="nope")
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.post("/federation/verify", json={})
        assert resp.json()["allowed"] is False

    # -- security health & stats --

    def test_security_health_success(self, client):
        fed = MagicMock()
        fed.get_health_status.return_value = {"healthy": True, "checks": 3}
        with patch("core.federation.federation_security.get_federation_security",
                   return_value=fed):
            resp = client.get("/federation/security/health")
        assert resp.status_code == 200
        assert resp.json() == {"healthy": True, "checks": 3}

    def test_security_health_failure_generic(self, client):
        with patch(
            "core.federation.federation_security.get_federation_security",
            side_effect=RuntimeError("secret-health-detail"),
        ):
            resp = client.get("/federation/security/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["healthy"] is False
        assert "secret-health-detail" not in resp.text
        assert body["error"] == "Security health check failed"

    def test_security_stats_success(self, client):
        manager = MagicMock()
        manager.get_statistics.return_value = {"checks": 12, "denied": 3}
        with patch("core.federation.zero_trust_security.get_zero_trust_manager",
                   return_value=manager):
            resp = client.get("/federation/security/stats")
        assert resp.status_code == 200
        assert resp.json() == {"checks": 12, "denied": 3}

    def test_security_stats_failure_generic(self, client):
        with patch(
            "core.federation.zero_trust_security.get_zero_trust_manager",
            side_effect=RuntimeError("secret-stats-detail"),
        ):
            resp = client.get("/federation/security/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"error": "Security statistics unavailable"}
        assert "secret-stats-detail" not in resp.text


# ===========================================================================
# core/llm/routing/restricted_pickle.py
# ===========================================================================


def _make_fake_module(monkeypatch, module_name, cls_name):
    """Register a module whose classes pickle against a module prefix."""
    ns = {"__name__": module_name}
    exec(
        f"class {cls_name}:\n"
        f"    def __init__(self, v):\n"
        f"        self.v = v\n"
        f"    def __eq__(self, o):\n"
        f"        return isinstance(o, {cls_name}) and self.v == o.v\n"
        f"    def __reduce__(self):\n"
        f"        return (type(self), (self.v,))\n",
        ns,
    )
    cls = ns[cls_name]
    mod = types.ModuleType(module_name)
    mod.__dict__[cls_name] = cls
    monkeypatch.setitem(sys.modules, module_name, mod)
    return cls


class _EvilEval:
    def __reduce__(self):
        return (eval, ("__import__('os').system('echo pwned')",))


class _EvilOS:
    def __reduce__(self):
        import os as _os

        return (_os.system, ("echo pwned",))


class TestRestrictedPickle:
    def test_restricted_loads_dict_roundtrip(self):
        from core.llm.routing.restricted_pickle import restricted_loads

        data = pickle.dumps({"a": [1, 2, 3], "b": "x"})
        assert restricted_loads(data) == {"a": [1, 2, 3], "b": "x"}

    def test_restricted_load_file_object(self):
        from core.llm.routing.restricted_pickle import restricted_load

        data = pickle.dumps({"n": 5})
        assert restricted_load(io.BytesIO(data)) == {"n": 5}

    @pytest.mark.parametrize(
        "value",
        [
            {"k": 1},
            [1, 2, 3],
            (1, 2),
            {1, 2, 3},
            frozenset({1, 2}),
            "text",
            b"bytes",
            42,
            3.14,
            True,
            1 + 2j,
        ],
    )
    def test_restricted_loads_builtin_containers(self, value):
        from core.llm.routing.restricted_pickle import restricted_loads

        assert restricted_loads(pickle.dumps(value)) == value

    def test_eval_reduce_rejected(self):
        from core.llm.routing.restricted_pickle import restricted_loads

        with pytest.raises(pickle.UnpicklingError):
            restricted_loads(pickle.dumps(_EvilEval()))

    def test_os_reduce_rejected(self):
        from core.llm.routing.restricted_pickle import restricted_loads

        with pytest.raises(pickle.UnpicklingError):
            restricted_loads(pickle.dumps(_EvilOS()))

    def test_numpy_ndarray_roundtrip(self):
        np = pytest.importorskip("numpy")
        from core.llm.routing.restricted_pickle import restricted_loads

        arr = np.array([1, 2, 3])
        loaded = restricted_loads(pickle.dumps(arr))
        assert isinstance(loaded, np.ndarray)
        assert (loaded == arr).all()

    def test_defaultdict_roundtrip(self):
        import collections

        from core.llm.routing.restricted_pickle import restricted_loads

        d = collections.defaultdict(int)
        d["a"] += 1
        loaded = restricted_loads(pickle.dumps(d))
        assert isinstance(loaded, collections.defaultdict)
        assert loaded["a"] == 1

    def test_sklearn_prefix_module_allowed(self, monkeypatch):
        from core.llm.routing.restricted_pickle import restricted_loads

        cls = _make_fake_module(monkeypatch, "sklearn.estimators", "FakeEstimator")
        loaded = restricted_loads(pickle.dumps(cls(7)))
        assert loaded == cls(7)

    def test_scipy_prefix_module_allowed(self, monkeypatch):
        from core.llm.routing.restricted_pickle import restricted_loads

        cls = _make_fake_module(monkeypatch, "scipy.sparse.dok", "FakeMatrix")
        loaded = restricted_loads(pickle.dumps(cls("m")))
        assert loaded == cls("m")

    def test_collections_prefix_module_allowed(self, monkeypatch):
        from core.llm.routing.restricted_pickle import restricted_loads

        cls = _make_fake_module(monkeypatch, "collections.abc", "FakeMapping")
        loaded = restricted_loads(pickle.dumps(cls(1)))
        assert loaded == cls(1)

    def test_bare_numpy_prefix_allowed(self):
        np = pytest.importorskip("numpy")
        from core.llm.routing.restricted_pickle import RestrictedUnpickler

        unpickler = RestrictedUnpickler(io.BytesIO(b""))
        assert unpickler.find_class("numpy", "ndarray") is np.ndarray

    def test_bare_scipy_prefix_allowed(self):
        from core.llm.routing.restricted_pickle import RestrictedUnpickler

        unpickler = RestrictedUnpickler(io.BytesIO(b""))
        # scipy may or may not be installed; the whitelist accepts the module
        # prefix either way — resolution to an object happens only when the
        # payload actually references it.
        try:
            unpickler.find_class("scipy", "zeros")
        except (ImportError, AttributeError):
            pass  # scipy absent — prefix rule still accepted it (no raise here)

    @pytest.mark.parametrize("name", ["eval", "exec", "open", "compile",
                                      "__import__", "getattr", "globals",
                                      "input", "breakpoint"])
    def test_dangerous_builtins_rejected(self, name):
        from core.llm.routing.restricted_pickle import RestrictedUnpickler

        unpickler = RestrictedUnpickler(io.BytesIO(b""))
        with pytest.raises(pickle.UnpicklingError):
            unpickler.find_class("builtins", name)

    @pytest.mark.parametrize(
        "module", ["os", "subprocess", "sys", "socket", "http.server", "base64"]
    )
    def test_arbitrary_modules_rejected(self, module):
        from core.llm.routing.restricted_pickle import RestrictedUnpickler

        unpickler = RestrictedUnpickler(io.BytesIO(b""))
        with pytest.raises(pickle.UnpicklingError):
            unpickler.find_class(module, "system")

    def test_allowed_builtins_by_name(self):
        from core.llm.routing.restricted_pickle import RestrictedUnpickler

        unpickler = RestrictedUnpickler(io.BytesIO(b""))
        assert unpickler.find_class("builtins", "dict") is dict
        assert unpickler.find_class("builtins", "list") is list
        assert unpickler.find_class("builtins", "bytes") is bytes

    def test_corrupt_pickle_raises(self):
        from core.llm.routing.restricted_pickle import restricted_loads

        with pytest.raises((pickle.UnpicklingError, EOFError)):
            restricted_loads(b"garbage-not-a-pickle")
