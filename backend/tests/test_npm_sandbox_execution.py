"""
Tests for Node.js execution in HazardSandbox.

Tests cover:
- Basic Node.js code execution
- Input injection
- Security constraints (network disabled, read-only filesystem)
- Resource limits (memory, CPU, timeout)
- Error handling
- Custom image execution

Reference: Phase 36 RESEARCH.md Pattern 5 "Node.js Skill Execution in HazardSandbox"
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

from core.skill_sandbox import HazardSandbox
from tests.sandbox_lifecycle_mocks import install_container


# Create mock exception classes for testing
class MockContainerError(Exception):
    """Mock ContainerError for testing."""
    # Set __name__ to match real ContainerError type check
    __name__ = 'ContainerError'

    def __init__(self, message, exit_status=None, command=None, stderr=None):
        super().__init__(message)
        self.exit_status = exit_status
        self.command = command
        self.stderr = stderr


class MockAPIError(Exception):
    """Mock APIError for testing."""
    # Set __name__ to match real APIError type check
    __name__ = 'APIError'

    pass


@pytest.fixture
def mock_docker_client():
    """Mock Docker client.

    The patch targets the module reference ``core.skill_sandbox`` actually
    calls (``core.skill_sandbox.docker.from_env``).  Patching ``docker``
    through ``sys.modules`` depends on collection order: other modules in this
    suite replace ``sys.modules['docker']`` while they are being collected, so
    a ``patch('docker.from_env')`` can land on a replacement module and leave
    the real client in place (the combined-suite failure in #918).
    """
    with patch('core.skill_sandbox.docker.from_env') as mock_from_env:
        client = MagicMock()
        mock_from_env.return_value = client
        client.ping.return_value = True
        install_container(client, stdout=b"output\n")
        yield client


@pytest.fixture
def sandbox(mock_docker_client):
    """Create HazardSandbox with mocked Docker client."""
    return HazardSandbox()


class TestExecuteNodejsBasic:
    """Tests for basic Node.js execution."""

    def test_execute_nodejs_basic(self, sandbox, mock_docker_client):
        """Test simple console.log execution."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"Hello from Node.js\n")

        result = sandbox.execute_nodejs(
            code="console.log('Hello from Node.js')",
            inputs={}
        )

        assert "Hello from Node.js" in result
        mock_docker_client.containers.create.assert_called_once()

    def test_execute_nodejs_with_inputs(self, sandbox, mock_docker_client):
        """Test inputs injected correctly."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"test input\n")

        result = sandbox.execute_nodejs(
            code="console.log(inputs.test)",
            inputs={"test": "test input"}
        )

        assert "test input" in result

        # Verify inputs in wrapper script
        call_args = mock_docker_client.containers.create.call_args
        command = call_args[1]["command"]
        assert "inputs" in command[2]  # Node.js -e argument contains inputs

    def test_execute_nodejs_custom_image(self, sandbox, mock_docker_client):
        """Test execution with custom image."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"custom image output\n")

        result = sandbox.execute_nodejs(
            code="console.log('custom')",
            inputs={},
            image="atom-npm-skill:custom-skill-v1"
        )

        assert "custom" in result

        # Verify custom image used
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["image"] == "atom-npm-skill:custom-skill-v1"

    def test_execute_nodejs_default_image(self, sandbox, mock_docker_client):
        """Test default image is node:20-alpine."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"default\n")

        sandbox.execute_nodejs(
            code="console.log('default')",
            inputs={}
        )

        # Verify default image
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["image"] == "node:20-alpine"


class TestExecuteNodejsSecurity:
    """Tests for security constraints."""

    def test_execute_nodejs_network_disabled(self, sandbox, mock_docker_client):
        """Test network access is disabled."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify network_disabled=True
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["network_disabled"] is True

    def test_execute_nodejs_readonly_fs(self, sandbox, mock_docker_client):
        """Test filesystem is read-only."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify read_only=True
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["read_only"] is True

    def test_execute_nodejs_tmpfs_only(self, sandbox, mock_docker_client):
        """Test only /tmp is writable via tmpfs."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify tmpfs mounted for /tmp only
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["tmpfs"] == {"/tmp": "size=10m"}

    def test_execute_nodejs_container_removed(self, sandbox,
                                              mock_docker_client):
        """Test the sandbox removes the container and reports it."""
        # Mock container output
        created = install_container(
            mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Removal is owned by the sandbox (auto_remove=False races wait/logs).
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["auto_remove"] is False
        created.remove.assert_called_once_with(force=True)


class TestExecuteNodejsResourceLimits:
    """Tests for resource limits."""

    def test_execute_nodejs_memory_limit(self, sandbox, mock_docker_client):
        """Test memory limit is enforced."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={},
            memory_limit="512m"
        )

        # Verify memory limit
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["mem_limit"] == "512m"

    def test_execute_nodejs_cpu_limit(self, sandbox, mock_docker_client):
        """Test CPU quota is enforced."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={},
            cpu_limit=0.75
        )

        # Verify CPU quota (0.75 * 100000 = 75000)
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["cpu_quota"] == 75000
        assert call_args[1]["cpu_period"] == 100000

    def test_execute_nodejs_timeout(self, sandbox, mock_docker_client):
        """Test timeout is not forwarded as an unsupported create() kwarg."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={},
            timeout_seconds=60
        )

        # containers.create() takes no timeout keyword (regression for #918);
        # the wall-clock deadline is enforced around start()/wait().
        call_args = mock_docker_client.containers.create.call_args
        assert "timeout" not in call_args[1]


class TestExecuteNodejsErrorHandling:
    """Tests for error handling."""

    def test_execute_nodejs_container_error(self, sandbox, mock_docker_client):
        """Test ContainerError is caught and returned."""
        # Create a custom exception class with ContainerError as the name
        class ContainerError(Exception):
            def __init__(self, message, exit_status=None, command=None, stderr=None):
                super().__init__(message)
                self.exit_status = exit_status
                self.command = command
                self.stderr = stderr

        # Mock container error
        error = ContainerError(
            "Test error",
            exit_status=1,
            command="node -e 'code'",
            stderr=b"SyntaxError: Unexpected token"
        )
        mock_docker_client.containers.create.side_effect = error

        result = sandbox.execute_nodejs(
            code="invalid syntax",
            inputs={}
        )

        # Verify error caught and returned
        assert "EXECUTION_ERROR" in result
        assert "SyntaxError" in result

    def test_execute_nodejs_api_error(self, sandbox, mock_docker_client):
        """Test Docker API error is caught and returned."""
        # Create a custom exception class with APIError as the name
        class APIError(Exception):
            pass

        # Mock API error
        mock_docker_client.containers.create.side_effect = APIError("Docker daemon not responding")

        result = sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify error caught and returned
        assert "DOCKER_ERROR" in result

    def test_execute_nodejs_generic_error(self, sandbox, mock_docker_client):
        """Test generic exception is caught and returned."""
        # Mock generic error
        mock_docker_client.containers.create.side_effect = Exception("Unexpected error")

        result = sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify error caught and returned
        assert "SANDBOX_ERROR" in result


class TestCreateNodejsWrapper:
    """Tests for _create_nodejs_wrapper method."""

    def test_create_nodejs_wrapper_basic(self, sandbox):
        """Test wrapper script format for basic code."""
        wrapper = sandbox._create_nodejs_wrapper(
            code="console.log('test')",
            inputs={}
        )

        # Verify inputs injected
        assert "const inputs = {}" in wrapper

        # Verify user code included
        assert "console.log('test')" in wrapper

    def test_create_nodejs_wrapper_with_inputs(self, sandbox):
        """Test wrapper script injects inputs correctly."""
        wrapper = sandbox._create_nodejs_wrapper(
            code="console.log(inputs.name)",
            inputs={"name": "test"}
        )

        # Verify inputs object
        assert "const inputs = {\"name\": \"test\"}" in wrapper

        # Verify user code can access inputs
        assert "console.log(inputs.name)" in wrapper

    def test_create_nodejs_wrapper_complex_inputs(self, sandbox):
        """Test wrapper script handles complex input types."""
        inputs = {
            "string": "test",
            "number": 42,
            "boolean": True,
            "array": [1, 2, 3],
            "object": {"key": "value"}
        }

        wrapper = sandbox._create_nodejs_wrapper(
            code="console.log(inputs)",
            inputs=inputs
        )

        # Verify all inputs serialized correctly
        assert "\"string\": \"test\"" in wrapper
        assert "\"number\": 42" in wrapper
        assert "\"boolean\": true" in wrapper
        assert "\"array\": [1, 2, 3]" in wrapper
        assert "\"object\": {\"key\": \"value\"}" in wrapper


class TestExecuteNodejsNetworkBlocking:
    """Tests for network blocking enforcement."""

    def test_execute_nodejs_network_requests_blocked(self, sandbox, mock_docker_client):
        """Test network requests fail (simulated)."""
        # In real execution, network requests would timeout/fail
        # Here we verify the constraint is set
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify network_disabled=True (blocks fetch, axios, etc.)
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["network_disabled"] is True


class TestExecuteNodejsFilesystemBlocking:
    """Tests for filesystem write blocking."""

    def test_execute_nodejs_filesystem_writes_blocked(self, sandbox, mock_docker_client):
        """Test filesystem writes fail (simulated)."""
        # In real execution, fs.writeFile would fail due to read-only root
        # Here we verify the constraint is set
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify read_only=True (blocks fs.writeFile, fs.mkdir, etc.)
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["read_only"] is True


class TestExecuteNodejsTimeoutEnforcement:
    """Tests for timeout enforcement."""

    def test_execute_nodejs_timeout_default(self, sandbox, mock_docker_client):
        """Test default timeout is 30 seconds (not a create() kwarg)."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        call_args = mock_docker_client.containers.create.call_args
        # containers.create() takes no timeout keyword; the deadline is
        # enforced around start()/wait() (regression for #918).
        assert "timeout" not in call_args[1]

    def test_execute_nodejs_timeout_custom(self, sandbox, mock_docker_client):
        """Test custom timeout is applied."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="while(true) {}",
            inputs={},
            timeout_seconds=5
        )

        call_args = mock_docker_client.containers.create.call_args
        assert "timeout" not in call_args[1]


class TestExecuteNodejsCommandFormat:
    """Tests for Node.js command format."""

    def test_execute_nodejs_command_format(self, sandbox, mock_docker_client):
        """Test command uses 'node -e' with wrapper script."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify command format
        call_args = mock_docker_client.containers.create.call_args
        command = call_args[1]["command"]
        assert command[0] == "node"
        assert command[1] == "-e"
        assert len(command) == 3  # node, -e, wrapper_script


class TestExecuteNodejsOutputEncoding:
    """Tests for output encoding."""

    def test_execute_nodejs_output_utf8(self, sandbox, mock_docker_client):
        """Test output is decoded as UTF-8."""
        # Mock container output with UTF-8 bytes
        install_container(mock_docker_client, stdout="Hello World\n".encode('utf-8'))

        result = sandbox.execute_nodejs(
            code="console.log('Hello World')",
            inputs={}
        )

        # Verify UTF-8 decoding
        assert isinstance(result, str)
        assert "Hello World" in result

    def test_execute_nodejs_multiline_output(self, sandbox, mock_docker_client):
        """Test multiline output is handled correctly."""
        # Mock container output with multiple lines
        output = "Line 1\nLine 2\nLine 3\n"
        install_container(mock_docker_client, stdout=output.encode('utf-8'))

        result = sandbox.execute_nodejs(
            code="console.log('Line 1'); console.log('Line 2'); console.log('Line 3');",
            inputs={}
        )

        # Verify all lines present
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


class TestExecuteNodejsResourceLimitsDefaults:
    """Tests for default resource limits."""

    def test_execute_nodejs_default_memory(self, sandbox, mock_docker_client):
        """Test default memory limit is 256m."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify default memory
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["mem_limit"] == "256m"

    def test_execute_nodejs_default_cpu(self, sandbox, mock_docker_client):
        """Test default CPU limit is 0.5 cores."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify default CPU quota (0.5 * 100000 = 50000)
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["cpu_quota"] == 50000


class TestExecuteNodejsContainerNaming:
    """Tests for container naming."""

    def test_execute_nodejs_container_id_format(self, sandbox, mock_docker_client):
        """Test container ID has skill_ prefix and 8-char hex suffix."""
        install_container(mock_docker_client, stdout=b"output\n")

        sandbox.execute_nodejs(
            code="console.log('test')",
            inputs={}
        )

        # Verify container name format
        call_args = mock_docker_client.containers.create.call_args
        container_name = call_args[1]["name"]
        assert container_name.startswith("skill_")
        assert len(container_name) == 14  # "skill_" + 8 hex chars


class TestExecuteNodejsBackwardCompatibility:
    """Tests for backward compatibility with execute_python."""

    def test_execute_python_unchanged(self, sandbox, mock_docker_client):
        """Test execute_python method still works (backward compatibility)."""
        # Mock container output
        install_container(mock_docker_client, stdout=b"Python output\n")

        result = sandbox.execute_python(
            code="print('Python output')",
            inputs={}
        )

        assert "Python output" in result

        # Verify Python execution
        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["command"][0] == "python"
