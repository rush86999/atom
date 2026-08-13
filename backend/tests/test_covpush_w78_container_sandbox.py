# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/container_sandbox. Docker and subprocess execution
fully mocked (asyncio.create_subprocess_exec / subprocess.run) — nothing runs
for real, no network.

- docker_available: returncode-based detection, cached result, FileNotFoundError
  and TimeoutExpired fallbacks.
- execute_raw_python: routes to docker (success / non-zero exit / timeout with
  cidfile-based kill) and subprocess fallback (success / failure / timeout).
- _kill_docker_container: missing cidfile, empty cid, real kill, exception.
- _resource_limit_preexec: win32 → None, POSIX → callable; rlimit failures
  swallowed.
- _build_execution_wrapper: params serialized as base64 (never interpolated
  raw), user code preserved verbatim (braces/quotes safe).
"""
import asyncio
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.container_sandbox as cs
from core.container_sandbox import (
    DEFAULT_MEMORY_LIMIT,
    DEFAULT_TIMEOUT,
    ContainerSandbox,
)


class _FakeProc:
    """Minimal stand-in for the object returned by create_subprocess_exec."""

    def __init__(self, out=b"", err=b"", rc=0, communicate=None):
        self._out = out
        self._err = err
        self.returncode = rc
        self.killed = False
        self.waited = False
        self._comm = communicate

    async def communicate(self):
        if self._comm is not None:
            return await self._comm()
        return (self._out, self._err)

    def kill(self):
        self.killed = True

    async def wait(self):
        self.waited = True


class _FakeNamedTemporaryFile:
    """Replaces tempfile.NamedTemporaryFile with a known path."""

    def __init__(self, path):
        self.name = str(path)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, content):
        pass


class TestDockerAvailable:
    def test_available_when_info_ok(self):
        with patch.object(cs.subprocess, "run") as run_mock:
            run_mock.return_value = MagicMock(returncode=0)
            assert ContainerSandbox().docker_available is True
        run_mock.assert_called_once()

    def test_unavailable_when_info_fails(self):
        with patch.object(cs.subprocess, "run") as run_mock:
            run_mock.return_value = MagicMock(returncode=1)
            sandbox = ContainerSandbox()
            assert sandbox.docker_available is False
            assert sandbox.docker_available is False  # cached
        run_mock.assert_called_once()

    def test_unavailable_when_docker_missing(self):
        with patch.object(cs.subprocess, "run",
                          side_effect=FileNotFoundError("docker")):
            assert ContainerSandbox().docker_available is False

    def test_unavailable_when_info_times_out(self):
        with patch.object(cs.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(["docker"], 5)):
            assert ContainerSandbox().docker_available is False


class TestExecuteRawPythonDocker:
    def test_success(self):
        sandbox = ContainerSandbox()
        proc = _FakeProc(out=b"hello world\n", rc=0)
        with patch.object(cs.ContainerSandbox, "docker_available", new=True):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)) as exec_mock:
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "print(1)", timeout=30)
                )
        assert result["status"] == "success"
        assert result["output"] == "hello world"
        assert result["environment"] == "docker"
        assert result["execution_seconds"] >= 0
        cmd = exec_mock.await_args.args
        assert "--network" in cmd and "none" in cmd
        assert f"--memory={DEFAULT_MEMORY_LIMIT}" in cmd
        assert "--read-only" in cmd

    def test_success_with_network_enabled(self):
        sandbox = ContainerSandbox(enable_network=True)
        proc = _FakeProc(out=b"ok", rc=0)
        with patch.object(cs.ContainerSandbox, "docker_available", new=True):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)) as exec_mock:
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "print(1)", timeout=30)
                )
        assert result["status"] == "success"
        cmd = exec_mock.await_args.args
        assert "--network" not in cmd

    def test_nonzero_exit_returns_stderr(self):
        sandbox = ContainerSandbox()
        proc = _FakeProc(err=b"Traceback boom", rc=1)
        with patch.object(cs.ContainerSandbox, "docker_available", new=True):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)):
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "raise X()", timeout=30)
                )
        assert result["status"] == "failed"
        assert "Traceback boom" in result["output"]
        assert result["environment"] == "docker"

    def test_timeout_kills_container_via_cidfile(self, tmp_path):
        script = tmp_path / "script.py"
        cidfile = tmp_path / "script.py.cid"
        cidfile.write_text("abc123")
        async def _timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        sandbox = ContainerSandbox(timeout=5)
        proc = _FakeProc(rc=0, communicate=_timeout)
        with patch.object(cs.ContainerSandbox, "docker_available", new=True):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)):
                with patch.object(cs.tempfile, "NamedTemporaryFile",
                                  return_value=_FakeNamedTemporaryFile(script)):
                    with patch.object(cs.asyncio, "create_subprocess_exec",
                                      new=AsyncMock(return_value=proc)) as exec_mock:
                        result = asyncio.run(
                            sandbox.execute_raw_python("t1", "while True: pass", timeout=5)
                        )
        assert result["status"] == "failed"
        assert "timed out after 5s" in result["output"]
        assert proc.killed is True
        assert proc.waited is True
        # second call: docker kill <cid>
        exec_mock.await_args_list[1].args == ("docker", "kill", "abc123")
        assert not script.exists()
        assert not cidfile.exists()


class TestKillDockerContainer:
    def test_no_cidfile_noop(self, tmp_path):
        sandbox = ContainerSandbox()
        with patch.object(cs.asyncio, "create_subprocess_exec",
                          new=AsyncMock()) as exec_mock:
            asyncio.run(sandbox._kill_docker_container(str(tmp_path / "nope.cid")))
        exec_mock.assert_not_called()

    def test_empty_cid_noop(self, tmp_path):
        cidfile = tmp_path / "x.cid"
        cidfile.write_text("   ")
        sandbox = ContainerSandbox()
        with patch.object(cs.asyncio, "create_subprocess_exec",
                          new=AsyncMock()) as exec_mock:
            asyncio.run(sandbox._kill_docker_container(str(cidfile)))
        exec_mock.assert_not_called()

    def test_kills_container(self, tmp_path):
        cidfile = tmp_path / "x.cid"
        cidfile.write_text("cid-999")
        sandbox = ContainerSandbox()
        with patch.object(cs.asyncio, "create_subprocess_exec",
                          new=AsyncMock(return_value=_FakeProc(rc=0))) as exec_mock:
            asyncio.run(sandbox._kill_docker_container(str(cidfile)))
        assert exec_mock.await_args.args == ("docker", "kill", "cid-999")

    def test_exception_swallowed(self, tmp_path):
        cidfile = tmp_path / "x.cid"
        cidfile.write_text("cid-1")
        sandbox = ContainerSandbox()
        with patch.object(cs.asyncio, "create_subprocess_exec",
                          new=AsyncMock(side_effect=OSError("docker down"))):
            asyncio.run(sandbox._kill_docker_container(str(cidfile)))  # no raise


class TestExecuteSubprocessFallback:
    def test_success(self, tmp_path):
        sandbox = ContainerSandbox()
        proc = _FakeProc(out=b"sub ok", rc=0)
        with patch.object(cs.ContainerSandbox, "docker_available", new=False):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)) as exec_mock:
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "print('sub')", timeout=30)
                )
        assert result["status"] == "success"
        assert result["output"] == "sub ok"
        assert result["environment"] == "subprocess"
        args, kwargs = exec_mock.call_args
        assert args[0] == "python3"
        assert kwargs["preexec_fn"] is not None

    def test_failure(self):
        sandbox = ContainerSandbox()
        proc = _FakeProc(err=b"oops", rc=2)
        with patch.object(cs.ContainerSandbox, "docker_available", new=False):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)):
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "sys.exit(2)", timeout=30)
                )
        assert result["status"] == "failed"
        assert result["output"] == "oops"

    def test_timeout(self):
        async def _timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        sandbox = ContainerSandbox()
        proc = _FakeProc(rc=0, communicate=_timeout)
        with patch.object(cs.ContainerSandbox, "docker_available", new=False):
            with patch.object(cs.asyncio, "create_subprocess_exec",
                              new=AsyncMock(return_value=proc)):
                result = asyncio.run(
                    sandbox.execute_raw_python("t1", "sleep(999)", timeout=5)
                )
        assert result["status"] == "failed"
        assert "timed out after 5s" in result["output"]
        assert result["environment"] == "subprocess"
        assert proc.killed is True


class TestResourceLimitPreexec:
    def test_win32_returns_none(self):
        with patch.object(sys, "platform", "win32"):
            assert ContainerSandbox._resource_limit_preexec() is None

    def test_posix_apply_limits(self):
        fn = ContainerSandbox._resource_limit_preexec()
        assert callable(fn)
        with patch("resource.setrlimit") as setrlimit_mock:
            fn()
        assert setrlimit_mock.call_count == 2

    def test_apply_limits_swallows_errors(self):
        fn = ContainerSandbox._resource_limit_preexec()
        with patch("resource.setrlimit", side_effect=ValueError("bad")):
            fn()  # no raise


class TestBuildExecutionWrapper:
    def test_params_base64_encoded(self):
        wrapper = ContainerSandbox._build_execution_wrapper(
            "print(_INPUT_PARAMS)", {"k": "v", "tricky": "'''\nnot code\n'''"}
        )
        assert "b64decode" in wrapper
        assert "'''\nnot code\n'''" not in wrapper  # never interpolated raw
        import base64
        import json
        marker = wrapper.split("b64decode('")[1].split("')")[0]
        assert json.loads(base64.b64decode(marker))["tricky"] == "'''\nnot code\n'''"

    def test_user_code_preserved_verbatim(self):
        code = "def f(x):\n    return {'a': x}\nprint(f(1))"
        wrapper = ContainerSandbox._build_execution_wrapper(code, {})
        assert "def f(x):" in wrapper
        assert "'a': x" in wrapper
        assert wrapper.endswith(code.strip() + "\n")
