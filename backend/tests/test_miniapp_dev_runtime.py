"""Mini-app docker-dev runtime — DEV-ONLY local execution on macOS/desktop.

Covers: the guest agent's ``--stdio`` transport (same protocol/execution core
as a Firecracker boot, exercised here as a REAL subprocess — no Docker, no
VM), dev-image tag resolution, factory selection + production guard, and the
``prepare_runtime`` docker-dev branch. The Docker-backed integration tests
run only when a daemon is reachable (skipped elsewhere, e.g. CI without
Docker) — they exercise the FULL ``execute_python`` contract: state envelope,
callback channel, no-network, timeout kill.
"""
import asyncio
import json
import os
import subprocess
import sys

import pytest

AGENT_PATH = "core/sandbox_runtime/firecracker_guest/agent.py"


# ---------------------------------------------------------------------------
# Guest agent --stdio transport (real subprocess, no Docker needed)
# ---------------------------------------------------------------------------
class TestAgentStdio:
    def _run_agent(self, request_line: str, reply_lines: list, timeout: float = 15.0):
        """Drive ``agent.py --stdio`` over real pipes.

        When the agent sends a callback request, the next scripted reply is
        written back (single-threaded: the agent blocks on readline until we
        answer — same blocking shape as the host-side callback handler).
        Returns the final reply dict, every callback request seen, and the
        exit code.
        """
        proc = subprocess.Popen(
            [sys.executable, AGENT_PATH, "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        callbacks = []
        final = None
        replies = list(reply_lines)
        try:
            proc.stdin.write(request_line + "\n")
            proc.stdin.flush()
            for _ in range(100):  # bounded line loop
                line = proc.stdout.readline()
                if not line:
                    break
                data = json.loads(line)
                if data.get("type") == "callback":
                    callbacks.append(data)
                    reply = replies.pop(0) if replies else {
                        "type": "callback_result", "ok": False,
                        "error": "callbacks_disabled"}
                    proc.stdin.write(json.dumps(reply) + "\n")
                    proc.stdin.flush()
                else:
                    final = data
                    break
            proc.stdin.close()
            proc.wait(timeout=timeout)
        finally:
            if proc.poll() is None:
                proc.kill()
        return final, callbacks, proc.returncode

    def test_exec_and_exit_code(self):
        final, callbacks, rc = self._run_agent(
            json.dumps({"type": "exec", "code": "print('hello'); import sys; sys.exit(3)",
                        "inputs": {}}),
            reply_lines=[],
        )
        assert final["type"] == "final"
        assert final["stdout"] == "hello\n"
        assert final["exit_code"] == 3
        assert callbacks == []

    def test_inputs_injected_as_globals(self):
        final, _, _ = self._run_agent(
            json.dumps({"type": "exec", "code": "print(n * 2)", "inputs": {"n": 21}}),
            reply_lines=[],
        )
        assert final["stdout"] == "42\n"
        assert final["exit_code"] == 0

    def test_state_envelope_harvested(self):
        code = (
            "state = dict(state or {})\n"
            "state['runs'] = state.get('runs', 0) + 1\n"
            "storage_ops = [{'op': 'put', 'key': 'k', 'data': 'v'}]\n"
        )
        final, _, _ = self._run_agent(
            json.dumps({"type": "exec", "code": code,
                        "inputs": {"state": {"runs": 1}}}),
            reply_lines=[],
        )
        env = final["state_envelope"]
        assert env["state"] == {"runs": 2}
        assert env["storage_ops"] == [{"op": "put", "key": "k", "data": "v"}]
        assert "record_ops" in env

    def test_callback_round_trip(self):
        code = "data = fetch_integration('gsheet', 'read', {'id': '1'}); print(data['x'])"
        final, callbacks, _ = self._run_agent(
            json.dumps({"type": "exec", "code": code, "inputs": {}}),
            reply_lines=[{"type": "callback_result", "ok": True, "data": {"x": 7}}],
        )
        assert len(callbacks) == 1
        assert callbacks[0]["kind"] == "fetch_integration"
        assert callbacks[0]["service"] == "gsheet"
        assert final["stdout"] == "7\n"
        assert final["exit_code"] == 0

    def test_callback_error_surfaces_to_user_code(self):
        code = (
            "try:\n"
            "    fetch_integration('slack', 'post', {})\n"
            "except RuntimeError as e:\n"
            "    print('caught:', e)\n"
        )
        final, callbacks, _ = self._run_agent(
            json.dumps({"type": "exec", "code": code, "inputs": {}}),
            reply_lines=[{"type": "callback_result", "ok": False,
                          "error": "callbacks_disabled"}],
        )
        assert "caught:" in final["stdout"]
        assert "slack.post" in final["stdout"]

    def test_traceback_captured_in_stderr(self):
        final, _, _ = self._run_agent(
            json.dumps({"type": "exec", "code": "1/0", "inputs": {}}),
            reply_lines=[],
        )
        assert final["exit_code"] == 1
        assert "ZeroDivisionError" in final["stderr"]

    def test_malformed_request_replied_not_crashed(self):
        final, _, rc = self._run_agent("this is not json", reply_lines=[])
        assert final["stderr"] == "malformed request"
        assert final["exit_code"] == 1

    def test_no_argv_keeps_vsock_boot_path(self):
        """The FC boot path is untouched: with no argv (kernel init= boot) the
        agent goes to the vsock transport and fails loudly off-Linux
        (AF_VSOCK unavailable) instead of silently using stdio."""
        proc = subprocess.run(
            [sys.executable, AGENT_PATH],
            capture_output=True, text=True, timeout=15,
        )
        assert proc.returncode != 0
        assert "AF_VSOCK" in (proc.stderr or "")


# ---------------------------------------------------------------------------
# Dev image resolution (pure)
# ---------------------------------------------------------------------------
class TestResolveDevImage:
    def test_no_deps_returns_base(self):
        from core.sandbox_runtime.miniapp_dev_runner import BASE_TAG, resolve_dev_image
        assert resolve_dev_image([]) == (BASE_TAG, [])
        assert resolve_dev_image(None) == (BASE_TAG, [])

    def test_deps_hash_stable_and_order_insensitive(self):
        from core.sandbox_runtime.miniapp_dev_runner import resolve_dev_image
        t1, _ = resolve_dev_image(["pandas", "numpy>=2"])
        t2, _ = resolve_dev_image(["numpy>=2", "pandas"])
        assert t1 == t2
        assert t1.startswith("atom-miniapp-dev:deps-")

    def test_dep_change_new_tag(self):
        from core.sandbox_runtime.miniapp_dev_runner import resolve_dev_image
        t1, _ = resolve_dev_image(["pandas"])
        t2, _ = resolve_dev_image(["pandas==2.0"])
        assert t1 != t2


# ---------------------------------------------------------------------------
# Factory — docker-dev selection, production guard, fail-closed preserved
# ---------------------------------------------------------------------------
class TestFactoryDockerDev:
    def test_selects_dev_runtime_when_available(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "development")
        from core.sandbox_runtime import miniapp_dev_runner as dr
        monkeypatch.setattr(dr, "is_available", lambda: True)
        monkeypatch.setattr("core.mini_app_runtime._is_production", lambda: False)
        runtime = m.get_miniapp_runtime()
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime
        assert isinstance(runtime, MiniAppDevRuntime)

    def test_refused_in_production(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(RuntimeError, match="DEV-ONLY"):
            m.get_miniapp_runtime()
        assert m.is_docker_dev_selected() is False

    def test_refused_when_docker_daemon_down(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "development")
        from core.sandbox_runtime import miniapp_dev_runner as dr
        monkeypatch.setattr(dr, "is_available", lambda: False)
        with pytest.raises(RuntimeError, match="Docker daemon"):
            m.get_miniapp_runtime()

    def test_unknown_runtime_still_fails_closed(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker")
        with pytest.raises(RuntimeError):
            m.get_miniapp_runtime()

    def test_default_env_unchanged_firecracker_fail_closed(self, monkeypatch):
        """No env set → default stays 'firecracker' → still fail-closed on a
        macOS host (the production posture is untouched)."""
        import core.mini_app_runtime as m
        monkeypatch.delenv("ATOM_MINIAAP_RUNTIME", raising=False)
        from core.sandbox_runtime import firecracker_runner as fr
        monkeypatch.setattr(fr, "is_available", lambda: False)
        monkeypatch.setattr(fr, "get_kernel_image", lambda: None)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/tmp/nope.ext4")
        with pytest.raises(RuntimeError):
            m.get_miniapp_runtime()

    def test_fc_unavailable_error_carries_dev_hint_off_production(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.delenv("ATOM_MINIAAP_RUNTIME", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        from core.sandbox_runtime import firecracker_runner as fr
        monkeypatch.setattr(fr, "is_available", lambda: False)
        monkeypatch.setattr(fr, "get_kernel_image", lambda: None)
        monkeypatch.setattr(fr, "get_rootfs_template", lambda: "/tmp/nope.ext4")
        with pytest.raises(RuntimeError, match="docker-dev"):
            m.get_miniapp_runtime()

    def test_is_docker_dev_selected_env_only(self, monkeypatch):
        import core.mini_app_runtime as m
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert m.is_docker_dev_selected() is True
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert m.is_docker_dev_selected() is False
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "firecracker")
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert m.is_docker_dev_selected() is False


# ---------------------------------------------------------------------------
# deps param — interface parity across runtimes (no Docker needed)
# ---------------------------------------------------------------------------
class TestDepsParamParity:
    def test_all_runtimes_accept_deps_kwarg(self):
        import inspect

        from core.sandbox_runtime.docker_runner import DockerRuntime
        from core.sandbox_runtime.e2b_runner import E2BRuntime
        from core.sandbox_runtime.firecracker_runner import FirecrackerRuntime
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

        for cls in (FirecrackerRuntime, DockerRuntime, E2BRuntime, MiniAppDevRuntime):
            params = inspect.signature(cls.execute_python).parameters
            assert "deps" in params, f"{cls.__name__} lacks deps param"

    def test_docker_runtime_deps_kwarg_no_typeerror(self):
        """DockerRuntime called with deps (daemon may be absent in tests) must
        return a structured SandboxExecResult, never raise TypeError on the
        new param."""
        from core.sandbox_runtime.base import SandboxExecResult
        from core.sandbox_runtime.docker_runner import DockerRuntime

        class _P:
            max_exec_seconds = 5

        result = asyncio.run(DockerRuntime().execute_python(
            "print('x')", policy=_P(), deps=["pandas"]))
        assert isinstance(result, SandboxExecResult)


# ---------------------------------------------------------------------------
# prepare_runtime — docker-dev branch (skip ext4 gate, keep dep scan)
# ---------------------------------------------------------------------------
class TestPrepareRuntimeDevBranch:
    def _app(self, deps):
        class _A:
            id = "app-1"
            name = "T"
            manifest = {"dependencies": deps}
            runtime_image = None
            runtime_version = 0
        return _A()

    def test_dev_mode_skips_rootfs_gate(self, monkeypatch):
        import core.mini_app_service as svc
        monkeypatch.setattr(svc, "is_docker_dev_selected", lambda: True)
        from core.package_dependency_scanner import PackageDependencyScanner

        class _DB:
            def commit(self):
                pass

        monkeypatch.setattr(PackageDependencyScanner, "scan_packages",
                            lambda self, pkgs: {"safe": True})
        app = self._app(["requests"])
        rootfs = os.path.join(
            svc.get_miniapp_rootfs_dir(), f"miniapp-{app.id}.ext4")
        assert not os.path.isfile(rootfs), "test requires the rootfs to be absent"
        assert svc.prepare_runtime(app, _DB()) is None

    def test_fc_mode_still_requires_rootfs(self, monkeypatch):
        import core.mini_app_service as svc
        monkeypatch.setattr(svc, "is_docker_dev_selected", lambda: False)
        from core.package_dependency_scanner import PackageDependencyScanner

        class _DB:
            def commit(self):
                pass

        monkeypatch.setattr(PackageDependencyScanner, "scan_packages",
                            lambda self, pkgs: {"safe": True})
        app = self._app(["requests"])
        with pytest.raises(RuntimeError, match="build_miniapp_rootfs"):
            svc.prepare_runtime(app, _DB())

    def test_dev_mode_still_fails_closed_on_unsafe_deps(self, monkeypatch):
        import core.mini_app_service as svc
        monkeypatch.setattr(svc, "is_docker_dev_selected", lambda: True)
        from core.package_dependency_scanner import PackageDependencyScanner

        class _DB:
            def commit(self):
                pass

        monkeypatch.setattr(PackageDependencyScanner, "scan_packages",
                            lambda self, pkgs: {"safe": False, "vulnerabilities": [1],
                                                "conflicts": []})
        with pytest.raises(ValueError, match="fail-closed"):
            svc.prepare_runtime(self._app(["requests"]), _DB())


# ---------------------------------------------------------------------------
# Container argv — locks the security-critical docker run flags (no daemon)
# ---------------------------------------------------------------------------
class TestContainerArgv:
    def test_run_flags_mirror_sandbox_posture(self, monkeypatch):
        """The container must run with the mini-app isolation contract: no
        network, read-only rootfs, tmpfs only, mem/CPU caps, dropped caps,
        no privilege escalation, ephemeral, same guest agent + stdio."""
        import asyncio

        from core.sandbox_runtime import miniapp_dev_runner as dr

        captured = {}

        class _FakeProc:
            returncode = 0

            def __init__(self, cmd):
                captured["cmd"] = cmd
                self.stdout = asyncio.StreamReader()
                self.stdout.feed_data(json.dumps(
                    {"type": "final", "stdout": "", "stderr": "",
                     "exit_code": 0}).encode() + b"\n")
                self.stdout.feed_eof()
                self.stderr = asyncio.StreamReader()
                self.stderr.feed_eof()
                self.stdin = _FakeWriter()

            def kill(self):
                pass

            async def wait(self):
                return 0

        class _FakeWriter:
            def write(self, data):
                pass

            async def drain(self):
                return None

        async def _fake_exec(*cmd, **kwargs):
            return _FakeProc(cmd)

        monkeypatch.setattr(dr, "is_available", lambda: True)
        monkeypatch.setattr(dr.asyncio, "create_subprocess_exec", _fake_exec)
        result = asyncio.run(
            dr.MiniAppDevRuntime().execute_python(
                "x = 1", policy=_Policy(), inputs={}, deps=[])
        )
        assert result.success is True, result.stderr
        cmd = captured["cmd"]
        assert cmd[0] == "docker" and cmd[1] == "run"
        for required in (
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:size=10m",
            "--memory", "256m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--rm",
        ):
            assert required in cmd, f"missing {required!r} in {cmd}"
        # Same guest agent file the FC rootfs bakes in, stdio transport.
        assert "python3" in cmd and "/opt/atom-guest/agent.py" in cmd
        assert cmd[-1] == "--stdio"


# ---------------------------------------------------------------------------
# Docker-backed integration — skipped without a reachable daemon
# ---------------------------------------------------------------------------
def _docker_up() -> bool:
    try:
        return subprocess.run(
            ["docker", "info", "--format", "ok"],
            capture_output=True, timeout=10,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


docker_ready = pytest.mark.skipif(not _docker_up(), reason="Docker daemon not reachable")


class _Policy:
    max_exec_seconds = 20


@docker_ready
class TestDockerDevIntegration:
    async def test_hello_and_envelope(self):
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

        result = await MiniAppDevRuntime().execute_python(
            "state = dict(state or {})\nstate['runs'] = state.get('runs', 0) + 1\nprint('ran')",
            policy=_Policy(),
            inputs={"state": {"runs": 5}},
            deps=[],
        )
        assert result.success, result.stderr
        assert result.stdout == "ran\n"
        assert result.metadata["backend"] == "docker-dev"
        assert result.metadata["state_envelope"]["state"] == {"runs": 6}

    async def test_callback_channel(self):
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

        async def handler(request):
            assert request["service"] == "gsheet"
            return {"ok": True, "data": {"rows": 3}}

        result = await MiniAppDevRuntime().execute_python(
            "d = fetch_integration('gsheet', 'read', {}); print(d['rows'])",
            policy=_Policy(),
            callback_handler=handler,
            deps=[],
        )
        assert result.success, result.stderr
        assert result.stdout == "3\n"
        assert result.metadata["callbacks"][0]["ok"] is True

    async def test_network_disabled(self):
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

        result = await MiniAppDevRuntime().execute_python(
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('example.com', 80), timeout=3)\n"
            "    print('NETWORK UP')\n"
            "except OSError as e:\n"
            "    print('BLOCKED', type(e).__name__)\n",
            policy=_Policy(),
            deps=[],
        )
        assert result.success, result.stderr
        assert "BLOCKED" in result.stdout, result.stdout

    async def test_timeout_kills_container(self):
        from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

        class _Slow:
            max_exec_seconds = 3

        result = await MiniAppDevRuntime().execute_python(
            "import time; time.sleep(120)",
            policy=_Slow(),
            deps=[],
        )
        assert result.success is False
        assert result.metadata.get("timeout") is True
        assert result.duration_seconds < 30

    async def test_deps_image_built_and_reused(self):
        from core.sandbox_runtime.miniapp_dev_runner import (
            MiniAppDevRuntime,
            resolve_dev_image,
        )

        rt = MiniAppDevRuntime()
        tag, _ = resolve_dev_image(["six==1.16.0"])
        first = await rt.execute_python(
            "import six; print(six.__version__)", policy=_Policy(), deps=["six==1.16.0"])
        assert first.success, first.stderr
        assert first.stdout == "1.16.0\n"
        # Second run must reuse the cached image (and succeed identically).
        second = await rt.execute_python(
            "import six; print('again')", policy=_Policy(), deps=["six==1.16.0"])
        assert second.success, second.stderr
        assert second.metadata["image"] == tag
