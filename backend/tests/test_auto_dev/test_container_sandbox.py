"""
Test ContainerSandbox Docker execution.

Tests cover:
- Docker execution
- Subprocess fallback
- Security constraints
- Result format
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.auto_dev.container_sandbox import ContainerSandbox


class TestContainerSandboxDockerExecution:
    """Test ContainerSandbox executes Python code in Docker."""

    @pytest.mark.skipif(
        True,  # Skip if Docker not available in CI
        reason="Docker not available in test environment"
    )
    def test_docker_available_property(self):
        """Test checks Docker availability."""
        sandbox = ContainerSandbox()

        # Should check Docker availability
        assert isinstance(sandbox.docker_available, bool)

    @pytest.mark.asyncio
    async def test_execute_raw_python_runs_code(self, monkeypatch):
        """Test execute_raw_python() runs code in container."""
        sandbox = ContainerSandbox()

        # Mock docker subprocess
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"test output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="print('test')",
                input_params={},
            )

            assert result["status"] in ["success", "failed"]


class TestContainerSandboxSubprocessFallback:
    """Test falls back to subprocess if Docker unavailable."""

    @pytest.mark.asyncio
    async def test_falls_back_to_subprocess(self, monkeypatch):
        """Test falls back to subprocess if Docker unavailable."""
        sandbox = ContainerSandbox()

        # Force Docker to be unavailable
        sandbox._docker_available = False

        # Mock subprocess
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="print('test')",
                input_params={},
            )

            assert result["environment"] == "subprocess"

    @pytest.mark.asyncio
    async def test_uses_same_interface(self, monkeypatch):
        """Test uses same interface as Docker."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="x = 1",
                input_params={"data": "test"},
            )

            assert "status" in result
            assert "output" in result


class TestContainerSandboxSecurityConstraints:
    """Test enforces security constraints."""

    @pytest.mark.asyncio
    async def test_enforces_timeout(self, monkeypatch):
        """Test enforces timeout (default 60s)."""
        sandbox = ContainerSandbox(timeout=5)
        sandbox._docker_available = False

        # Mock subprocess that times out
        async def mock_timeout():
            import asyncio
            await asyncio.sleep(10)

        mock_process = MagicMock()
        mock_process.communicate = mock_timeout
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await sandbox.execute_raw_python(
                    tenant_id="tenant-001",
                    code="import time; time.sleep(100)",
                    input_params={},
                )

                assert result["status"] == "failed"


class TestContainerSandboxResultFormat:
    """Test returns execution results."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_status(self, monkeypatch):
        """Test returns dict with status."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="print('test')",
                input_params={},
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_includes_output_string(self, monkeypatch):
        """Test includes output string."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"test output\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="print('test')",
                input_params={},
            )

            assert "output" in result
            assert isinstance(result["output"], str)

    @pytest.mark.asyncio
    async def test_includes_execution_seconds(self, monkeypatch):
        """Test includes execution_seconds."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="x = 1",
                input_params={},
            )

            assert "execution_seconds" in result
            assert isinstance(result["execution_seconds"], (int, float))


class TestContainerSandboxErrorHandling:
    """Test handles execution errors gracefully."""

    @pytest.mark.asyncio
    async def test_handles_syntax_errors(self, monkeypatch):
        """Test handles syntax errors."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        # Mock subprocess that returns syntax error
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"SyntaxError: invalid syntax\n")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="print('unclosed quote",
                input_params={},
            )

            assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handles_runtime_errors(self, monkeypatch):
        """Test handles runtime errors."""
        sandbox = ContainerSandbox()
        sandbox._docker_available = False

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"RuntimeError: test error\n")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await sandbox.execute_raw_python(
                tenant_id="tenant-001",
                code="raise RuntimeError('test error')",
                input_params={},
            )

            assert result["status"] == "failed"
            assert "RuntimeError" in result.get("output", "")


class TestContainerSandboxExecutionWrapper:
    """Test _build_execution_wrapper()."""

    def test_wraps_code_with_input_params(self):
        """Test wraps code with input parameter injection."""
        from core.auto_dev.container_sandbox import ContainerSandbox

        code = "print(_INPUT_PARAMS)"
        input_params = {"key": "value"}

        wrapper = ContainerSandbox._build_execution_wrapper(code, input_params)

        assert "_INPUT_PARAMS" in wrapper
        assert "json.loads" in wrapper

    def test_injects_params_as_json(self):
        """Test injects params as JSON."""
        from core.auto_dev.container_sandbox import ContainerSandbox

        code = "x = _INPUT_PARAMS['test']"
        input_params = {"test": 123}

        wrapper = ContainerSandbox._build_execution_wrapper(code, input_params)

        assert "'test': 123" in wrapper or '"test": 123' in wrapper
