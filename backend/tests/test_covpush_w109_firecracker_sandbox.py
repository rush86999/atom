# -*- coding: utf-8 -*-
"""Coverage wave 109 — core/firecracker_sandbox.py (never-tested module,
36% import baseline -> target 100%; all subprocess/VFS effects mocked).

CRITICAL FAIL-CLOSED CONTRACT (W109-1): `execute_in_sandbox` must NEVER run
the untrusted command on the host when the Firecracker runtime is missing.
Prior behavior silently fell back to `asyncio.create_subprocess_exec(*command)`
on the host — fail-open for untrusted workbook/macro execution. Now:
  * no KVM/firecracker binary  -> SandboxUnavailableError (RED: previously
    executed locally and returned success instead of raising)
  * VM boot failure             -> SandboxUnavailableError
  * VM orchestration placeholder -> returns False (command never run on host)
Callers (workbook_runtime.run_macro) surface the error as a clean failure.

Also covers: is_available (both flags), get_sandbox lazy singleton + caching,
VM-available path (spawn/kill), unavailable-path property readouts.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.firecracker_sandbox import FirecrackerSandbox, SandboxUnavailableError, get_sandbox


@pytest.fixture
def sandbox_cls():
    return FirecrackerSandbox


class TestAvailability:
    def test_not_available_without_kvm(self):
        with patch("os.path.exists", return_value=False), patch("shutil.which", return_value=None):
            sb = FirecrackerSandbox()
        assert sb.has_kvm is False
        assert sb.firecracker_path is None
        assert sb.is_available is False

    def test_not_available_without_binary(self):
        with patch("os.path.exists", return_value=True), patch("shutil.which", return_value=None):
            sb = FirecrackerSandbox()
        assert sb.has_kvm is True
        assert sb.is_available is False

    def test_available_when_kvm_and_binary(self):
        with patch("os.path.exists", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/firecracker"):
            sb = FirecrackerSandbox()
        assert sb.is_available is True


class TestFailClosed:
    @pytest.mark.asyncio
    async def test_no_runtime_raises_and_never_executes_locally(self):
        """RED (W109-1): old code executed the command locally and returned
        True; now raises SandboxUnavailableError with no host execution."""
        with patch("os.path.exists", return_value=False), \
             patch("shutil.which", return_value=None):
            sb = FirecrackerSandbox()
        proc = MagicMock()
        proc.returncode = 0
        create_mock = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", new=create_mock):
            with pytest.raises(SandboxUnavailableError):
                await sb.execute_in_sandbox(["soffice", "--headless"], Path("in.xlsx"), Path("/tmp"))
        # The untrusted command must NEVER be spawned on the host.
        create_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_vm_boot_failure_raises(self):
        with patch("os.path.exists", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/firecracker"):
            sb = FirecrackerSandbox()
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("kvm busy")):
            with pytest.raises(SandboxUnavailableError):
                await sb.execute_in_sandbox(["soffice"], Path("in.xlsx"), Path("/tmp"))

    @pytest.mark.asyncio
    async def test_vm_available_but_command_not_run_on_host(self):
        """When Firecracker IS available, the (placeholder) VM boot runs, but
        the command is NOT executed on the host — returns False (fail closed).
        """
        with patch("os.path.exists", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/firecracker"):
            sb = FirecrackerSandbox()
        proc = MagicMock()
        proc.returncode = 0
        commands = []

        async def fake_create_subprocess_exec(*args, **kwargs):
            commands.append(args)
            return proc

        with patch("asyncio.create_subprocess_exec", new=fake_create_subprocess_exec), \
             patch("asyncio.sleep", new=AsyncMock()):
            result = await sb.execute_in_sandbox(["soffice", "--headless"], Path("in.xlsx"), Path("/tmp"))
        assert result is False
        # Only the firecracker VM was spawned — never the user command.
        assert commands == [("firecracker", "--api-sock", "/tmp/firecracker.socket")]

    @pytest.mark.asyncio
    async def test_workbook_runtime_run_macro_fails_closed(self, tmp_path):
        """Consumer contract: workbook_runtime.run_macro surfaces the
        SandboxUnavailableError as a clean failure, never a host run."""
        from core.workbook_runtime import WorkbookRuntime
        xlsx = tmp_path / "in.xlsx"
        xlsx.write_bytes(b"not really xlsx")
        runtime = WorkbookRuntime()
        runtime._soffice = "/usr/bin/soffice"
        with patch("os.path.exists", return_value=False), \
             patch("shutil.which", return_value=None):
            sb = FirecrackerSandbox()
        with patch("core.firecracker_sandbox.get_sandbox", return_value=sb), \
             patch("asyncio.create_subprocess_exec") as create_mock:
            result = await runtime.run_macro(str(xlsx), "Macro1")
        assert result["success"] is False
        assert "Firecracker" in result["error"]
        create_mock.assert_not_awaited()


class TestGetSandbox:
    def test_lazy_singleton(self):
        with patch("core.firecracker_sandbox._sandbox", None):
            a = get_sandbox()
            b = get_sandbox()
            assert isinstance(a, FirecrackerSandbox)
            assert a is b
        with patch("core.firecracker_sandbox._sandbox", None):
            pass
