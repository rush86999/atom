"""Mini-app Firecracker runtime — fail-closed factory, boot path, guest agent.

All Firecracker execution is mocked (subprocess + UDS/vsock) — no real VM/KVM.
"""
import asyncio
import json
import os
import socket
import threading

import pytest


# ---------------------------------------------------------------------------
# get_miniapp_runtime — fail closed
# ---------------------------------------------------------------------------
class TestGetMiniappRuntime:
    def test_fails_closed_on_non_linux(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setattr(m, "_env_runtime", lambda: "firecracker")
        monkeypatch.setattr("core.sandbox_runtime.firecracker_runner._IS_LINUX", False)
        from core.sandbox_runtime import firecracker_runner as fr
        monkeypatch.setattr(fr, "is_available", lambda: False)
        monkeypatch.setattr(fr, "get_kernel_image", lambda: None)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/tmp/nope.ext4")
        with pytest.raises(RuntimeError):
            m.get_miniapp_runtime()

    def test_fails_closed_on_wrong_runtime_env(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setattr(m, "_env_runtime", lambda: "docker")
        with pytest.raises(RuntimeError):
            m.get_miniapp_runtime()

    def test_returns_runtime_when_available(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setattr(m, "_env_runtime", lambda: "firecracker")
        from core.sandbox_runtime import firecracker_runner as fr
        # get_miniapp_runtime uses the STRICT probe (is_provisioned_for), which
        # composes is_available() with the base rootfs template check.
        monkeypatch.setattr(fr, "is_provisioned_for", lambda image: True)
        r = m.get_miniapp_runtime()
        from core.sandbox_runtime.firecracker_runner import FirecrackerRuntime
        assert isinstance(r, FirecrackerRuntime)


# ---------------------------------------------------------------------------
# FirecrackerRuntime real boot path (mocked subprocess + UDS)
# ---------------------------------------------------------------------------
class TestFirecrackerRuntimeBoot:
    @pytest.fixture
    def provisioned(self, monkeypatch, tmp_path):
        """Kernel + template files exist; firecracker "on PATH"; is_available True."""
        kernel = tmp_path / "vmlinux"
        template = tmp_path / "miniapp-base.ext4"
        kernel.write_bytes(b"\x7fELF")
        template.write_bytes(b"ext4!")
        monkeypatch.setenv("FIRECRACKER_KERNEL_IMAGE", str(kernel))
        monkeypatch.setenv("FIRECRACKER_ROOTFS_TEMPLATE", str(template))
        monkeypatch.setenv("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", "1")
        from core.sandbox_runtime import firecracker_runner as fr
        monkeypatch.setattr(fr, "is_available", lambda: True)
        monkeypatch.setattr(fr, "_IS_LINUX", True)
        return fr

    class FakeProc:
        def __init__(self):
            self.returncode = None
            self.killed = False
        def kill(self):
            self.returncode = -9
            self.killed = True
        async def wait(self):
            if self.returncode is None:
                self.returncode = 0
            return self.returncode

    def _short_workdir(self):
        import tempfile
        return tempfile.mkdtemp(dir="/tmp", prefix="fc-")

    def test_config_and_vsock_exchange(self, monkeypatch, tmp_path, provisioned):
        fr = provisioned
        workdir = self._short_workdir()
        monkeypatch.setattr("tempfile.mkdtemp", lambda *a, **k: workdir)
        # Keep the run dir alive so we can inspect config.json after the run
        # (the runner normally cleans it up in a finally block).
        monkeypatch.setattr(fr.shutil, "rmtree", lambda *a, **k: None)

        # The runtime owns the listening UDS; the fake guest dials it.
        sock_path = os.path.join(workdir, "vsock.sock")
        guest_path = f"{sock_path}_{fr.get_guest_port()}"
        guest_errors = []

        def guest():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                    conn.connect(guest_path)
                    req = json.loads(conn.makefile("r").readline())
                    assert req == {"type": "exec", "code": "x = 1", "inputs": {}}
                    reply = json.dumps({
                        "type": "final",
                        "stdout": "__MINIAPP_STATE__:{\"state\": {\"n\": 1}, \"storage_ops\": []}",
                        "stderr": "",
                        "exit_code": 0,
                        "state_envelope": {"state": {"n": 1}, "storage_ops": []},
                    }) + "\n"
                    conn.sendall(reply.encode())
            except BaseException as exc:  # noqa: BLE001
                guest_errors.append(exc)

        guest_thread = threading.Thread(target=guest, daemon=True)
        proc = self.FakeProc()

        def fake_exec(*a, **k):
            guest_thread.start()
            return _coro(proc)

        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", fake_exec)

        policy = type("P", (), {"max_exec_seconds": 30})()
        runtime = fr.FirecrackerRuntime()
        result = asyncio.run(
            runtime.execute_python("x = 1", policy=policy, inputs={}, image=None)
        )
        guest_thread.join(timeout=5)
        assert not guest_thread.is_alive()
        assert not guest_errors, guest_errors
        assert result.success is True
        assert "__MINIAPP_STATE__" in result.stdout
        assert result.metadata["state_envelope"] == {"state": {"n": 1}, "storage_ops": []}
        assert "controller_error" not in result.metadata
        assert proc.killed is True  # VM torn down after the command channel

        # config.json assertions
        cfg = json.loads(open(os.path.join(workdir, "config.json")).read())
        assert cfg["boot-source"]["kernel_image_path"] == os.environ["FIRECRACKER_KERNEL_IMAGE"]
        assert "init=/opt/atom-guest/agent.py" in cfg["boot-source"]["boot_args"]
        drive = cfg["drives"][0]
        assert drive["path_on_host"] == os.environ["FIRECRACKER_ROOTFS_TEMPLATE"]  # image None → template
        assert drive["is_read_only"] is True
        assert cfg["machine-config"]["vcpu_count"] >= 1
        assert cfg["vsock"]["uds_path"] == sock_path

    def test_image_selects_rootfs(self, monkeypatch, tmp_path, provisioned):
        fr = provisioned
        workdir = self._short_workdir()
        monkeypatch.setattr("tempfile.mkdtemp", lambda *a, **k: workdir)
        monkeypatch.setattr(fr.shutil, "rmtree", lambda *a, **k: None)
        sock_path = os.path.join(workdir, "vsock.sock")
        guest_path = f"{sock_path}_{fr.get_guest_port()}"

        # The custom image must exist on the host — execute_python fail-closes
        # (reason=rootfs_missing) before writing config.json otherwise.
        custom_rootfs = tmp_path / "custom.ext4"
        custom_rootfs.write_bytes(b"ext4!")
        guest_errors = []

        def guest():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                    conn.connect(guest_path)
                    req = json.loads(conn.makefile("r").readline())
                    assert req == {"type": "exec", "code": "x=1", "inputs": {}}
                    conn.sendall((json.dumps({
                        "type": "final",
                        "stdout": "ok",
                        "stderr": "",
                        "exit_code": 0,
                    }) + "\n").encode())
            except BaseException as exc:  # noqa: BLE001
                guest_errors.append(exc)

        guest_thread = threading.Thread(target=guest, daemon=True)
        proc = self.FakeProc()

        def fake_exec(*a, **k):
            guest_thread.start()
            return _coro(proc)

        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", fake_exec)
        runtime = fr.FirecrackerRuntime()
        policy = type("P", (), {"max_exec_seconds": 30})()
        result = asyncio.run(
            runtime.execute_python("x=1", policy=policy, image=str(custom_rootfs))
        )
        guest_thread.join(timeout=5)
        assert not guest_thread.is_alive()
        assert not guest_errors, guest_errors
        assert result.success is True
        cfg = json.loads(open(os.path.join(workdir, "config.json")).read())
        assert cfg["drives"][0]["path_on_host"] == str(custom_rootfs)

    def test_boot_timeout(self, monkeypatch, tmp_path, provisioned):
        fr = provisioned
        workdir = self._short_workdir()
        monkeypatch.setattr("tempfile.mkdtemp", lambda *a, **k: workdir)
        # No vsock socket is created → _exchange times out on boot.
        proc = self.FakeProc()
        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", lambda *a, **k: _coro(proc))
        runtime = fr.FirecrackerRuntime()
        policy = type("P", (), {"max_exec_seconds": 1})()
        result = asyncio.run(
            runtime.execute_python("x=1", policy=policy)
        )
        assert result.success is False
        assert result.exit_code == -1


def _coro(proc):
    async def _f(*a, **k):
        return proc
    return _f()


# ---------------------------------------------------------------------------
# Guest agent logic (pure exec path)
# ---------------------------------------------------------------------------
class TestGuestAgent:
    def test_inputs_injected_and_stdout_captured(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("result = 1 + 1\nprint(result)", {"x": 5})
        assert res["stdout"].strip() == "2"
        assert res["exit_code"] == 0

    def test_state_global_roundtrip(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("state = {**state, 'n': state.get('n', 0) + 1}", {"state": {"n": 0}})
        assert res["exit_code"] == 0

    def test_syntax_error_captured(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("def broken(:", {})
        assert res["exit_code"] == 1
        assert "SyntaxError" in res["stderr"]

    def test_malformed_message_handled(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("", {"state": None})
        # empty code still executes (no-op) without crashing
        assert res["exit_code"] == 0


# ---------------------------------------------------------------------------
# Guest controller diagnostic (optional controller_error)
# ---------------------------------------------------------------------------
class TestGuestAgentControllerError:
    @pytest.mark.parametrize("exc_name", [
        "UnboundLocalError",
        "NameError",
        "TypeError",
        "KeyError",
        "IndexError",
        "ValueError",
        "ZeroDivisionError",
    ])
    def test_allowlisted_exact_class_reported(self, exc_name):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code(f"raise {exc_name}('boom')", {})
        assert res["exit_code"] == 1
        assert res["controller_error"] == exc_name
        assert exc_name in res["stderr"]  # existing stderr unchanged

    def test_unlisted_exception_not_reported(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("raise RuntimeError('boom')", {})
        assert res["exit_code"] == 1
        assert "controller_error" not in res
        assert "RuntimeError" in res["stderr"]

    def test_subclass_not_reported(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code(
            "class Custom(ValueError):\n"
            "    pass\n"
            "raise Custom('boom')", {})
        assert res["exit_code"] == 1
        assert "controller_error" not in res
        assert "Custom" in res["stderr"]

    def test_system_exit_not_reported(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("raise SystemExit(3)", {})
        assert res["exit_code"] == 3
        assert "controller_error" not in res

    def test_compile_failure_not_reported(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("def broken(:", {})
        assert res["exit_code"] == 1
        assert "controller_error" not in res
        assert "SyntaxError" in res["stderr"]

    def test_compile_valueerror_not_reported(self, monkeypatch):
        # ValueError is allowlisted for RUNTIME failures, but a compile-time
        # ValueError must stay unclassified. CPython versions disagree on
        # whether a null byte is ValueError or SyntaxError, so force the
        # compile-time ValueError explicitly instead of depending on that.
        from core.sandbox_runtime.firecracker_guest import agent

        def raise_value_error(*args, **kwargs):
            raise ValueError("source code string cannot contain null bytes")

        monkeypatch.setattr(agent, "compile", raise_value_error, raising=False)
        res = agent.run_code("\x00", {})
        assert res["exit_code"] == 1
        assert "controller_error" not in res
        assert "ValueError" in res["stderr"]

    def test_positive_run_not_reported(self):
        from core.sandbox_runtime.firecracker_guest import agent
        res = agent.run_code("print('ok')", {})
        assert res["exit_code"] == 0
        assert "controller_error" not in res


class _FakeReader:
    def __init__(self, payloads):
        self._lines = [json.dumps(p) + "\n" for p in payloads]

    async def readline(self):
        if not self._lines:
            return b""
        return self._lines.pop(0).encode("utf-8")


class _FakeWriter:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None


class TestGuestProtocolControllerError:
    def _exchange(self, payload):
        from core.sandbox_runtime import guest_protocol
        return asyncio.run(guest_protocol.exchange(
            _FakeReader([payload]), _FakeWriter(), "x", {}))

    def test_allowlisted_value_validated_and_returned(self):
        result = self._exchange({
            "type": "final", "stdout": "",
            "stderr": "Traceback\nNameError: boom",
            "exit_code": 1, "controller_error": "NameError"})
        assert len(result) == 6
        assert result[5] == "NameError"

    def test_unknown_value_dropped(self):
        result = self._exchange({
            "type": "final", "stdout": "", "stderr": "OSError: boom",
            "exit_code": 1, "controller_error": "OSError"})
        assert len(result) == 5

    def test_non_string_value_dropped(self):
        result = self._exchange({
            "type": "final", "stdout": "", "stderr": "", "exit_code": 1,
            "controller_error": ["NameError"]})
        assert len(result) == 5

    def test_absent_for_old_guest(self):
        result = self._exchange({
            "type": "final", "stdout": "", "stderr": "NameError: boom",
            "exit_code": 1})
        assert len(result) == 5

    def test_suppressed_on_successful_exit(self):
        result = self._exchange({
            "type": "final", "stdout": "ok", "stderr": "", "exit_code": 0,
            "controller_error": "NameError"})
        assert len(result) == 5

    def test_untagged_reply_not_reported(self):
        result = self._exchange({
            "stdout": "", "stderr": "NameError: boom",
            "exit_code": 1, "controller_error": "NameError"})
        assert len(result) == 5
        assert result[2] == 1

    def test_negative_exit_not_reported(self):
        result = self._exchange({
            "type": "final", "stdout": "", "stderr": "NameError: boom",
            "exit_code": -1, "controller_error": "NameError"})
        assert len(result) == 5
        assert result[2] == -1

    def test_exit_two_not_reported(self):
        result = self._exchange({
            "type": "final", "stdout": "", "stderr": "NameError: boom",
            "exit_code": 2, "controller_error": "NameError"})
        assert len(result) == 5
        assert result[2] == 2


class TestRunnerControllerErrorMetadata:
    class _EmptyStderr:
        async def readline(self):
            return b""

    def test_firecracker_metadata_carries_hint(self, monkeypatch, tmp_path):
        from core.sandbox_runtime import firecracker_runner as fr
        runtime = fr.FirecrackerRuntime()
        workdir = TestFirecrackerRuntimeBoot()._short_workdir()
        monkeypatch.setattr(fr.tempfile, "mkdtemp", lambda *a, **k: workdir)

        async def fake_exchange(*a, **k):
            return ("", "Traceback\nNameError: boom", 1, None, [], "NameError")

        async def fake_teardown(proc):
            return None

        monkeypatch.setattr(runtime, "_exchange", fake_exchange)
        monkeypatch.setattr(runtime, "_teardown_vm", fake_teardown)
        proc = TestFirecrackerRuntimeBoot.FakeProc()
        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec",
                            lambda *a, **k: _coro(proc))
        policy = type("P", (), {"max_exec_seconds": 30})()
        result = asyncio.run(runtime._run_in_vm_locked(
            "raise NameError('boom')", policy=policy, inputs={},
            rootfs=str(tmp_path / "unused.ext4")))
        assert result.success is False
        assert result.stderr == "Traceback\nNameError: boom"
        assert result.metadata["controller_error"] == "NameError"

    def test_docker_dev_metadata_carries_hint(self, monkeypatch):
        from core.sandbox_runtime import miniapp_dev_runner as mr
        proc = TestFirecrackerRuntimeBoot.FakeProc()
        proc.returncode = 0
        proc.stdout = _FakeReader([])
        proc.stdin = _FakeWriter()
        proc.stderr = self._EmptyStderr()

        async def fake_guest_exchange(*a, **k):
            return ("", "Traceback\nKeyError: boom", 1, None, [], "KeyError")

        monkeypatch.setattr(mr, "_guest_exchange", fake_guest_exchange)
        monkeypatch.setattr(mr.asyncio, "create_subprocess_exec",
                            lambda *a, **k: _coro(proc))
        runtime = mr.MiniAppDevRuntime()
        policy = type("P", (), {"max_exec_seconds": 30})()
        result = asyncio.run(runtime._run_in_container_locked(
            "raise KeyError('boom')", policy=policy, inputs={}, tag="test"))
        assert result.success is False
        assert result.stderr == "Traceback\nKeyError: boom"
        assert result.metadata["controller_error"] == "KeyError"

    def test_firecracker_five_element_exchange_has_no_hint(
            self, monkeypatch, tmp_path):
        from core.sandbox_runtime import firecracker_runner as fr
        runtime = fr.FirecrackerRuntime()
        workdir = TestFirecrackerRuntimeBoot()._short_workdir()
        monkeypatch.setattr(fr.tempfile, "mkdtemp", lambda *a, **k: workdir)

        async def fake_exchange(*a, **k):
            return ("ok", "", 0, None, [])

        async def fake_teardown(proc):
            return None

        monkeypatch.setattr(runtime, "_exchange", fake_exchange)
        monkeypatch.setattr(runtime, "_teardown_vm", fake_teardown)
        proc = TestFirecrackerRuntimeBoot.FakeProc()
        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec",
                            lambda *a, **k: _coro(proc))
        policy = type("P", (), {"max_exec_seconds": 30})()
        result = asyncio.run(runtime._run_in_vm_locked(
            "print('ok')", policy=policy, inputs={},
            rootfs=str(tmp_path / "unused.ext4")))
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "ok"
        assert "controller_error" not in result.metadata

    def test_docker_dev_five_element_exchange_has_no_hint(self, monkeypatch):
        from core.sandbox_runtime import miniapp_dev_runner as mr
        proc = TestFirecrackerRuntimeBoot.FakeProc()
        proc.returncode = 0
        proc.stdout = _FakeReader([])
        proc.stdin = _FakeWriter()
        proc.stderr = self._EmptyStderr()

        async def fake_guest_exchange(*a, **k):
            return ("ok", "", 0, None, [])

        monkeypatch.setattr(mr, "_guest_exchange", fake_guest_exchange)
        monkeypatch.setattr(mr.asyncio, "create_subprocess_exec",
                            lambda *a, **k: _coro(proc))
        runtime = mr.MiniAppDevRuntime()
        policy = type("P", (), {"max_exec_seconds": 30})()
        result = asyncio.run(runtime._run_in_container_locked(
            "print('ok')", policy=policy, inputs={}, tag="test"))
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "ok"
        assert "controller_error" not in result.metadata
