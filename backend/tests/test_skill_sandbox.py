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
import time

import requests

from tests.sandbox_lifecycle_mocks import install_container, make_container

# Mock docker module before importing skill_sandbox.
# Save the originals so they can be restored after the import — leaving the
# MagicMocks in sys.modules permanently would poison later test modules that
# import the real docker package.
_DOCKER_ORIGINAL = sys.modules.get('docker')
_DOCKER_ERRORS_ORIGINAL = sys.modules.get('docker.errors')
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

# Restore sys.modules now that skill_sandbox is imported (it captured the mock
# at import time; the tests patch core.skill_sandbox.docker at runtime).
if _DOCKER_ORIGINAL is not None:
    sys.modules['docker'] = _DOCKER_ORIGINAL
else:
    sys.modules.pop('docker', None)
if _DOCKER_ERRORS_ORIGINAL is not None:
    sys.modules['docker.errors'] = _DOCKER_ERRORS_ORIGINAL
else:
    sys.modules.pop('docker.errors', None)


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
        install_container(mock_client, stdout=b"Hello from sandbox\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print('Hello from sandbox')",
            inputs={}
        )

        assert result == "Hello from sandbox\n"
        mock_client.containers.create.assert_called_once()

        # Verify security constraints are applied
        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['network_disabled'] is True
        assert call_args.kwargs['read_only'] is True
        # Removal is owned by the sandbox (not the daemon) so the observed
        # outcome can be reported; the container is still ephemeral.
        assert call_args.kwargs['auto_remove'] is False
        created = mock_client.containers.create.return_value
        created.remove.assert_called_once_with(force=True)

    @patch('core.skill_sandbox.docker')
    def test_execute_python_with_inputs(self, mock_docker_module):
        """Verify inputs are injected into execution context."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"42\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print(x)",
            inputs={"x": 42}
        )

        assert result == "42\n"

        # Verify wrapper script includes inputs
        call_args = mock_client.containers.create.call_args
        wrapper_script = call_args.kwargs['command'][2]  # python -c <script>
        assert "inputs = " in wrapper_script
        assert '"x": 42' in wrapper_script


class TestTimeoutHandling:
    """Test timeout enforcement and deterministic container ownership."""

    # docker-py's model-level wrapper rejects undocumented kwargs before a
    # container exists.  A Mock silently accepts them, which is how an invalid
    # ``timeout=`` argument broke every real Docker execution while the mocked
    # suite stayed green (#918).
    _CREATE_KWARGS = frozenset({
        "image", "command", "name", "mem_limit", "cpu_quota", "cpu_period",
        "network_disabled", "read_only", "tmpfs", "auto_remove",
    })

    @patch('core.skill_sandbox.docker')
    def test_execute_python_only_passes_documented_create_kwargs(
            self, mock_docker_module):
        """Regression for #918: no ``timeout``/``stdout``/``stderr`` kwargs."""
        seen = {}

        def strict_create(**kwargs):
            unexpected = set(kwargs) - self._CREATE_KWARGS
            assert not unexpected, (
                f"containers.create() got unexpected keyword arguments "
                f"{sorted(unexpected)}")
            seen.update(kwargs)
            return make_container(stdout=b"Done\n")

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = strict_create
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code="print('Done')", inputs={}, timeout_seconds=60)

        assert result == "Done\n"
        mock_client.containers.create.assert_called_once()
        assert "timeout" not in seen
        assert seen["auto_remove"] is False, (
            "removal is owned by the sandbox so it can be reported truthfully")

    @patch('core.skill_sandbox.docker')
    def test_timeout_kills_and_removes_the_owned_container(
            self, mock_docker_module):
        """The deadline acts on the created container, never a name lookup."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(
            mock_client, name="skill_deadline1",
            wait_side_effect=requests.exceptions.ReadTimeout("budget"))
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        started = time.monotonic()
        receipt = sandbox.execute_python_receipt(
            code="while True: pass", inputs={}, timeout_seconds=1)
        elapsed = time.monotonic() - started

        assert receipt["ok"] is False
        assert receipt["timed_out"] is True
        assert receipt["killed"] is True
        assert receipt["terminated"] is True
        assert receipt["removed"] is True
        assert receipt["ephemeral"] is True
        assert receipt["exit_code"] == 124
        assert "was killed and removed" in receipt["error"]
        assert elapsed < 5, "the deadline must not wait for the container"
        created.start.assert_called_once()
        created.kill.assert_called_once()
        created.remove.assert_called_once_with(force=True)
        # Deterministic ownership: cleanup never re-resolves the container by
        # name, so a container that starts late cannot escape the deadline.
        mock_client.containers.get.assert_not_called()

    @patch('core.skill_sandbox.docker')
    def test_delayed_start_cannot_outlive_the_deadline(
            self, mock_docker_module):
        """Regression: a START slower than the budget is killed immediately.

        The old daemon-thread/``containers.run`` design joined the worker and
        then looked the container up by name; a container that started after
        that lookup kept running.  Starting the known container under the same
        deadline removes that window.
        """
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(mock_client, name="skill_delayed1")

        def slow_start():
            time.sleep(0.6)

        created.start.side_effect = slow_start
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="print('never')", inputs={}, timeout_seconds=0.2)

        assert receipt["timed_out"] is True
        assert receipt["killed"] is True
        assert receipt["removed"] is True
        assert "was killed and removed" in receipt["error"]
        created.wait.assert_not_called()
        created.kill.assert_called_once()
        created.remove.assert_called_once_with(force=True)
        mock_client.containers.get.assert_not_called()

    @patch('core.skill_sandbox.docker')
    def test_timeout_receipt_never_claims_a_failed_kill(
            self, mock_docker_module):
        """Regression: termination failure must be explicit, not "was killed"."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(
            mock_client, name="skill_stuck1",
            wait_side_effect=requests.exceptions.ReadTimeout("budget"))
        created.kill.side_effect = APIError("daemon refused kill")
        created.remove.side_effect = APIError("daemon refused remove")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="while True: pass", inputs={}, timeout_seconds=1)

        assert receipt["timed_out"] is True
        assert receipt["killed"] is False
        assert receipt["terminated"] is False
        assert receipt["removed"] is False
        assert receipt["ephemeral"] is False
        assert "could NOT be terminated" in receipt["error"]
        assert "was killed" not in receipt["error"]
        assert "kill failed" in receipt["error"]
        assert "remove failed" in receipt["error"]
        assert receipt["cleanup_error"]
        created.kill.assert_called_once()
        created.remove.assert_called_once_with(force=True)

    @patch('core.skill_sandbox.docker')
    def test_timeout_reports_force_removal_when_kill_failed(
            self, mock_docker_module):
        """The message distinguishes a kill from a force-removal."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(
            mock_client, name="skill_exited1",
            wait_side_effect=requests.exceptions.ReadTimeout("budget"))
        created.kill.side_effect = APIError("container is not running")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="while True: pass", inputs={}, timeout_seconds=1)

        assert receipt["timed_out"] is True
        assert receipt["killed"] is False
        assert receipt["terminated"] is True
        assert receipt["removed"] is True
        assert "was force-removed" in receipt["error"]
        assert "was killed" not in receipt["error"]
        assert "container is not running" in receipt["cleanup_error"]

    @patch('core.skill_sandbox.docker')
    def test_successful_run_reports_leaked_container_truthfully(
            self, mock_docker_module):
        """A successful run whose removal fails must not claim ephemerality."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(mock_client, stdout=b"Done\n")
        created.remove.side_effect = APIError("device or resource busy")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="print('Done')", inputs={})

        assert receipt["ok"] is True
        assert receipt["stdout"] == "Done\n"
        assert receipt["removed"] is False
        assert receipt["ephemeral"] is False
        assert "device or resource busy" in receipt["cleanup_error"]
        created.remove.assert_called_once_with(force=True)

    @patch('core.skill_sandbox.docker')
    def test_create_kwargs_are_accepted_by_the_real_docker_sdk(
            self, mock_docker_module):
        """The mocked suite must not hide an invalid SDK kwarg (#918).

        Feed the exact kwargs the sandbox passes into docker-py's own
        ``_create_container_args`` -- the function that raised the production
        ``TypeError`` for ``timeout=`` -- so this regression needs no daemon.
        """
        from docker.models.containers import _create_container_args

        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        HazardSandbox().execute_python(code="print('Done')", inputs={})
        kwargs = dict(mock_client.containers.create.call_args.kwargs)
        assert "timeout" not in kwargs
        kwargs["version"] = "1.45"  # what ContainerCollection.create adds

        normalised = _create_container_args(kwargs)

        assert normalised["network_disabled"] is True
        host_config = normalised["host_config"]
        assert host_config["ReadonlyRootfs"] is True
        assert host_config["Tmpfs"] == {"/tmp": "size=10m"}
        assert host_config["Memory"] == 256 * 1024 * 1024
        assert host_config["CpuQuota"] == 50000
        assert host_config["CpuPeriod"] == 100000

    @patch('core.skill_sandbox.docker')
    def test_execute_python_default_timeout_is_30_seconds(
            self, mock_docker_module):
        """Verify default timeout is 30 seconds and reported in the receipt."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="print('Done')", inputs={})

        assert receipt["ok"] is True
        assert receipt["timeout_seconds"] == 30
        assert receipt["timed_out"] is False
        assert "timeout" not in mock_client.containers.create.call_args.kwargs



class TestResourceLimits:
    """Test resource limit enforcement (memory, CPU, network, filesystem)."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_memory_limit(self, mock_docker_module):
        """Verify memory constraint is applied."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            memory_limit="512m"
        )

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['mem_limit'] == "512m"

    @patch('core.skill_sandbox.docker')
    def test_execute_python_cpu_limit(self, mock_docker_module):
        """Verify CPU quota is applied."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            cpu_limit=0.75
        )

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['cpu_quota'] == 75000  # 0.75 * 100000
        assert call_args.kwargs['cpu_period'] == 100000

    @patch('core.skill_sandbox.docker')
    def test_execute_python_network_disabled(self, mock_docker_module):
        """Verify network is disabled (CRITICAL security constraint)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['network_disabled'] is True

    @patch('core.skill_sandbox.docker')
    def test_execute_python_read_only_filesystem(self, mock_docker_module):
        """Verify filesystem is read-only (CRITICAL security constraint)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['read_only'] is True

    @patch('core.skill_sandbox.docker')
    def test_execute_python_tmpfs_mounted(self, mock_docker_module):
        """Verify tmpfs is mounted for temporary storage."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['tmpfs'] == {"/tmp": "size=10m"}

    @patch('core.skill_sandbox.docker')
    def test_execute_python_removed_after_execution(self, mock_docker_module):
        """Verify the sandbox (not the daemon) removes the container."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        created = install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        receipt = sandbox.execute_python_receipt(
            code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['auto_remove'] is False
        created.remove.assert_called_once_with(force=True)
        assert receipt["removed"] is True
        assert receipt["ephemeral"] is True


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    @patch('core.skill_sandbox.docker')
    def test_execute_python_container_error(self, mock_docker_module):
        """Verify ContainerError is caught and logged."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.containers.create.side_effect = ContainerError(
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
        mock_client.containers.create.side_effect = APIError(
            "Docker daemon error")
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
        mock_client.containers.create.side_effect = Exception(
            "Unexpected error")
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
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        # Verify no volumes parameter (would mount Docker socket)
        assert 'volumes' not in call_args.kwargs

    @patch('core.skill_sandbox.docker')
    def test_never_use_privileged_mode(self, mock_docker_module):
        """Verify privileged mode is NEVER used (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        # Verify no privileged=True in kwargs
        assert call_args.kwargs.get('privileged') is not True

    @patch('core.skill_sandbox.docker')
    def test_always_network_disabled(self, mock_docker_module):
        """Verify network is ALWAYS disabled (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        # Try with different parameters
        sandbox.execute_python(code="print('Done')", inputs={}, memory_limit="1g")

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['network_disabled'] is True

    @patch('core.skill_sandbox.docker')
    def test_always_read_only(self, mock_docker_module):
        """Verify filesystem is ALWAYS read-only (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        # Try with different parameters
        sandbox.execute_python(code="print('Done')", inputs={}, cpu_limit=1.0)

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['read_only'] is True

    @patch('core.skill_sandbox.docker')
    def test_always_resource_limited(self, mock_docker_module):
        """Verify resources are ALWAYS limited (CRITICAL security)."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
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
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
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
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('Done')", inputs={})

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['image'] == "python:3.11-slim"

    @patch('core.skill_sandbox.docker')
    def test_execute_python_with_custom_image(self, mock_docker_module):
        """Verify custom Docker image is used when provided."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            image="atom-skill:custom-skill-v1"
        )

        call_args = mock_client.containers.create.call_args
        assert call_args.kwargs['image'] == "atom-skill:custom-skill-v1"

    @patch('core.skill_sandbox.docker')
    def test_custom_image_maintains_security(self, mock_docker_module):
        """Verify custom images still enforce all security constraints."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        install_container(mock_client, stdout=b"Done\n")
        mock_docker_module.from_env.return_value = mock_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('Done')",
            inputs={},
            image="atom-skill:custom-v1"
        )

        call_args = mock_client.containers.create.call_args
        # Verify all security constraints still apply
        assert call_args.kwargs['network_disabled'] is True
        assert call_args.kwargs['read_only'] is True
        assert call_args.kwargs['auto_remove'] is False
        assert 'mem_limit' in call_args.kwargs
        assert 'cpu_quota' in call_args.kwargs
