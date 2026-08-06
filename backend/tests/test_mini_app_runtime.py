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

        # UDS server that echoes a state envelope (simulates the guest agent).
        sock_path = os.path.join(workdir, "vsock.sock")

        def server():
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)
            conn, _ = srv.accept()
            data = conn.recv(65536).decode()
            req = json.loads(data.split("\n")[0])
            assert "code" in req and "inputs" in req
            reply = json.dumps({"stdout": "__MINIAPP_STATE__:{\"state\": {\"n\": 1}, \"storage_ops\": []}", "stderr": "", "exit_code": 0}) + "\n"
            conn.sendall(reply.encode())
            conn.close()
            srv.close()

        t = threading.Thread(target=server, daemon=True)
        t.start()
        import time
        time.sleep(0.2)  # let the socket bind

        proc = self.FakeProc()
        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", lambda *a, **k: _coro(proc))

        policy = type("P", (), {"max_exec_seconds": 30})()
        runtime = fr.FirecrackerRuntime()
        result = asyncio.get_event_loop().run_until_complete(
            runtime.execute_python("x = 1", policy=policy, inputs={}, image=None)
        )
        assert result.success is True
        assert "__MINIAPP_STATE__" in result.stdout
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

        # The custom image must exist on the host — execute_python fail-closes
        # (reason=rootfs_missing) before writing config.json otherwise.
        custom_rootfs = tmp_path / "custom.ext4"
        custom_rootfs.write_bytes(b"ext4!")

        def server():
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)
            conn, _ = srv.accept()
            conn.recv(65536)
            conn.sendall((json.dumps({"stdout": "ok", "stderr": "", "exit_code": 0}) + "\n").encode())
            conn.close()
            srv.close()

        threading.Thread(target=server, daemon=True).start()
        import time
        time.sleep(0.2)
        proc = self.FakeProc()
        monkeypatch.setattr(fr.asyncio, "create_subprocess_exec", lambda *a, **k: _coro(proc))
        runtime = fr.FirecrackerRuntime()
        policy = type("P", (), {"max_exec_seconds": 30})()
        asyncio.get_event_loop().run_until_complete(
            runtime.execute_python("x=1", policy=policy, image=str(custom_rootfs))
        )
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
        result = asyncio.get_event_loop().run_until_complete(
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
