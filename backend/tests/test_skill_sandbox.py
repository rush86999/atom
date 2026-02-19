"""
Comprehensive unit tests for HazardSandbox - Docker-based isolated Python execution.

Tests cover:
- Docker client initialization and availability checks
- Container execution lifecycle (success, timeout, errors)
- Resource limit enforcement (memory, CPU, network, read-only)
- Security constraint validation
- Error handling and logging
- Manual container cleanup

Reference: backend/tests/test_governance_cache.py for mock patterns
Reference: RESEARCH.md Pitfall 3 for security constraints
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock docker module before importing skill_sandbox
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()

# Create mock exceptions
class DockerException(Exception):
    pass

class ContainerError(Exception):
    def __init__(self, message, exit_status=None, stderr=None):
        super().__init__(message)
        self.exit_status = exit_status
        self.stderr = stderr

class APIError(Exception):
    pass

class NotFound(Exception):
    pass

sys.modules['docker.errors'].DockerException = DockerException
sys.modules['docker.errors'].ContainerError = ContainerError
sys.modules['docker.errors'].APIError = APIError
sys.modules['docker.errors'].NotFound = NotFound

from core.skill_sandbox import HazardSandbox


class TestDockerClientInitialization:
    """Test Docker client initialization and availability checks."""

    @patch('core.skill_sandbox.docker')
    def test_docker_client_initialization_success(self, mock_docker_module):
        """Verify Docker client initializes successfully."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()

        assert sandbox.client is not None
        mock_docker_module.from_env.assert_called_once()
        mock_client.ping.assert_called_once()

    @patch('core.skill_sandbox.docker')
    def test_docker_unavailable_error(self, mock_docker_module):
        """Verify clear error when Docker daemon is not running."""
        mock_client = Mock()
        mock_client.ping.side_effect = DockerException("Daemon not running")
        mock_docker_module.from_env.return_value = mock_client

        with pytest.raises(RuntimeError) as exc_info:
            HazardSandbox()

        assert "Docker daemon is not running" in str(exc_info.value)
        assert "Start Docker with:" in str(exc_info.value)

    @patch('core.skill_sandbox.docker')
    def test_docker_import_error(self, mock_docker_module):
        """Verify clear error when Docker SDK is not installed."""
        mock_docker_module.from_env.side_effect = ImportError("No module named 'docker'")

        with pytest.raises(RuntimeError) as exc_info:
            HazardSandbox()

        assert "Failed to initialize Docker client" in str(exc_info.value)
        assert "Ensure Docker daemon is running" in str(exc_info.value)


class TestPythonExecution:
    """Test Python code execution in Docker containers."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_success(self, mock_docker_module):
        """Verify successful Python code execution."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Hello from sandbox\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print('Hello from sandbox')",
            inputs={}
        )

        assert result == "Hello from sandbox\n"
        mock_client.containers.run.assert_called_once()

        # Verify security constraints are applied
        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['network_disabled'] is True
        assert call_args.kwargs['read_only'] is True
        assert call_args.kwargs['auto_remove'] is True

    @patch('core.skill_sandbox.docker')
    def test_execute_python_with_inputs(self, mock_docker_module):
        """Verify inputs are injected into execution context."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"42\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print(x)",
            inputs={"x": 42}
        )

        assert result == "42\n"

        # Verify wrapper script includes inputs
        call_args = mock_client.containers.run.call_args
        wrapper_script = call_args.kwargs['command'][2]  # python -c <script>
        assert "inputs = " in wrapper_script
        assert '"x": 42' in wrapper_script


class TestTimeoutHandling:
    """Test timeout enforcement for container execution."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_timeout_enforced(self, mock_docker_module):
        """Verify timeout is applied to container execution."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            timeout_seconds=60
        )

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['timeout'] == 60

    @patch('core.skill_sandbox.docker')
    def test_execute_python_timeout_default(self, mock_docker_module):
        """Verify default timeout is 30 seconds."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['timeout'] == 30


class TestResourceLimits:
    """Test resource limit enforcement (memory, CPU, network, filesystem)."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_memory_limit(self, mock_docker_module):
        """Verify memory constraint is applied."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            memory_limit="512m"
        )

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['mem_limit'] == "512m"

    @patch('core.skill_sandbox.docker')
    def test_execute_python_cpu_limit(self, mock_docker_module):
        """Verify CPU quota is applied."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            cpu_limit=0.75
        )

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['cpu_quota'] == 75000  # 0.75 * 100000
        assert call_args.kwargs['cpu_period'] == 100000

    @patch('core.skill_sandbox.docker')
    def test_execute_python_network_disabled(self, mock_docker_module):
        """Verify network is disabled (CRITICAL security constraint)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['network_disabled'] is True

    @patch('core.skill_sandbox.docker')
    def test_execute_python_read_only_filesystem(self, mock_docker_module):
        """Verify filesystem is read-only (CRITICAL security constraint)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['read_only'] is True

    @patch('core.skill_sandbox.docker')
    def test_execute_python_tmpfs_mounted(self, mock_docker_module):
        """Verify tmpfs is mounted for temporary storage."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['tmpfs'] == {"/tmp": "size=10m"}

    @patch('core.skill_sandbox.docker')
    def test_execute_python_auto_remove(self, mock_docker_module):
        """Verify container is auto-removed after execution."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['auto_remove'] is True


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_container_error(self, mock_docker_module):
        """Verify ContainerError is caught and logged."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.side_effect = ContainerError(
            "Execution failed",
            exit_status=1,
            stderr=b"ERROR: Something went wrong\n"
        )
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(code="raise Exception()", inputs={})

        assert result.startswith("EXECUTION_ERROR:")
        assert "Something went wrong" in result

    @patch('core.skill_sandbox.docker')
    def test_execute_python_api_error(self, mock_docker_module):
        """Verify Docker APIError is caught and logged."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.side_effect = APIError("Docker daemon error")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(code="print('test')", inputs={})

        assert result.startswith("DOCKER_ERROR:")
        assert "Docker daemon error" in result

    @patch('core.skill_sandbox.docker')
    def test_execute_python_generic_exception(self, mock_docker_module):
        """Verify generic exceptions are caught and logged."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.side_effect = Exception("Unexpected error")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(code="print('test')", inputs={})

        assert result.startswith("SANDBOX_ERROR:")
        assert "Unexpected error" in result


class TestContainerCleanup:
    """Test manual container cleanup functionality."""

    @patch('core.skill_sandbox.docker')
    def test_cleanup_container_success(self, mock_docker_module):
        """Verify manual container cleanup works."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.cleanup_container("skill_abc123")

        assert result is True
        mock_client.containers.get.assert_called_once_with("skill_abc123")
        mock_container.remove.assert_called_once_with(force=True)

    @patch('core.skill_sandbox.docker')
    def test_cleanup_container_not_found(self, mock_docker_module):
        """Verify cleanup handles missing container gracefully."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.cleanup_container("skill_nonexistent")

        assert result is False

    @patch('core.skill_sandbox.docker')
    def test_cleanup_container_error(self, mock_docker_module):
        """Verify cleanup handles errors gracefully."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.get.side_effect = Exception("Docker error")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.cleanup_container("skill_error")

        assert result is False


class TestSecurityConstraints:
    """Test that security constraints are always enforced."""

    @patch('core.skill_sandbox.docker')
    def test_never_mount_docker_socket(self, mock_docker_module):
        """Verify Docker socket is NEVER mounted (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        # Verify no volumes parameter (would mount Docker socket)
        assert 'volumes' not in call_args.kwargs

    @patch('core.skill_sandbox.docker')
    def test_never_use_privileged_mode(self, mock_docker_module):
        """Verify privileged mode is NEVER used (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        # Verify no privileged=True in kwargs
        assert call_args.kwargs.get('privileged') is not True

    @patch('core.skill_sandbox.docker')
    def test_always_network_disabled(self, mock_docker_module):
        """Verify network is ALWAYS disabled (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        # Try with different parameters
        sandbox.execute_python(code="print('Done')", inputs={}, memory_limit="1g")

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['network_disabled'] is True

    @patch('core.skill_sandbox.docker')
    def test_always_read_only(self, mock_docker_module):
        """Verify filesystem is ALWAYS read-only (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        # Try with different parameters
        sandbox.execute_python(code="print('Done')", inputs={}, cpu_limit=1.0)

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['read_only'] is True

    @patch('core.skill_sandbox.docker')
    def test_always_resource_limited(self, mock_docker_module):
        """Verify resources are ALWAYS limited (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        # Verify memory and CPU limits are set
        assert 'mem_limit' in call_args.kwargs
        assert 'cpu_quota' in call_args.kwargs
        assert 'cpu_period' in call_args.kwargs


class TestContainerNaming:
    """Test container naming and identification."""

    @patch('core.skill_sandbox.docker')
    def test_container_name_format(self, mock_docker_module):
        """Verify container names follow skill_<uuid8> format."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        container_name = call_args.kwargs['name']
        assert container_name.startswith('skill_')
        assert len(container_name) == len('skill_') + 8  # skill_ + 8 char hex


class TestCustomImageSupport:
    """Test custom Docker image support for package installation."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_with_default_image(self, mock_docker_module):
        """Verify default image is python:3.11-slim when no image specified."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['image'] == "python:3.11-slim"

    @patch('core.skill_sandbox.docker')
    def test_execute_python_with_custom_image(self, mock_docker_module):
        """Verify custom Docker image is used when provided."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            image="atom-skill:custom-skill-v1"
        )

        call_args = mock_client.containers.run.call_args
        assert call_args.kwargs['image'] == "atom-skill:custom-skill-v1"

    @patch('core.skill_sandbox.docker')
    def test_custom_image_maintains_security(self, mock_docker_module):
        """Verify custom images still enforce all security constraints."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.run.return_value = b"Done\n"
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            image="atom-skill:custom-v1"
        )

        call_args = mock_client.containers.run.call_args
        # Verify all security constraints still apply
        assert call_args.kwargs['network_disabled'] is True
        assert call_args.kwargs['read_only'] is True
        assert call_args.kwargs['auto_remove'] is True
        assert 'mem_limit' in call_args.kwargs
        assert 'cpu_quota' in call_args.kwargs
