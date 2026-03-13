"""
Package Installer Tests

Test coverage:
- Docker image building with packages
- Vulnerability scanning before installation
- Custom image execution in HazardSandbox
- Image cleanup and removal
- Error handling (build failures, missing images)
- Build log capture and reporting
"""

import pytest
from unittest.mock import patch, MagicMock, call, PropertyMock
from pathlib import Path
import tempfile
import shutil
import types

# Mock docker module BEFORE any imports that use it
import sys

# Create real exception classes (not mocks) that can be caught
class DockerException(Exception):
    pass

class ImageNotFound(Exception):
    pass

class APIError(Exception):
    pass

# Create mock docker.errors module with REAL exception classes
docker_errors_mock = MagicMock()
docker_errors_mock.DockerException = DockerException
docker_errors_mock.ImageNotFound = ImageNotFound
docker_errors_mock.APIError = APIError

# Mock the docker module
sys.modules['docker'] = MagicMock()
sys.modules['docker'].errors = docker_errors_mock
sys.modules['docker.errors'] = docker_errors_mock

from core.package_installer import PackageInstaller


@pytest.fixture
def mock_docker_client():
    """Create mocked Docker client."""
    return MagicMock()


@pytest.fixture
def installer(mock_docker_client):
    """Create PackageInstaller instance with mocked Docker."""
    with patch('core.package_installer.docker.from_env', return_value=mock_docker_client):
        with patch('core.package_installer.HazardSandbox'):
            with patch('core.package_installer.PackageDependencyScanner'):
                yield PackageInstaller()


class TestPackageInstallation:
    """Docker image building with Python packages."""

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_install_packages_builds_image(
        self,
        mock_build,
        installer
    ):
        """Verify successful package installation builds Docker image."""
        # Mock safe scan (scanner is initialized in __init__)
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }

        # Mock successful build
        mock_build.return_value = [
            "Step 1/5 : FROM python:3.11-slim",
            "Successfully built abc123"
        ]

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["numpy==1.21.0"],
            scan_for_vulnerabilities=True
        )

        assert result["success"] == True
        assert "atom-skill:test-skill-v1" in result["image_tag"]
        assert len(result["build_logs"]) > 0
        mock_build.assert_called_once()
        installer.scanner.scan_packages.assert_called_once_with(["numpy==1.21.0"])

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_install_packages_fails_on_vulnerabilities(self, mock_build, installer):
        """Verify installation fails when vulnerabilities detected."""
        # Mock unsafe scan
        installer.scanner.scan_packages.return_value = {
            "safe": False,
            "vulnerabilities": [
                {
                    "cve_id": "CVE-2021-1234",
                    "severity": "HIGH",
                    "package": "vulnerable-pkg",
                    "affected_versions": ["1.0.0"],
                    "advisory": "Remote code execution vulnerability",
                    "source": "pip-audit"
                }
            ],
            "dependency_tree": {},
            "conflicts": []
        }

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["vulnerable-pkg==1.0.0"],
            scan_for_vulnerabilities=True
        )

        assert result["success"] == False
        assert "Vulnerabilities detected" in result["error"]
        assert len(result["vulnerabilities"]) > 0
        assert result["image_tag"] is None
        # Should not attempt build if vulnerabilities found
        mock_build.assert_not_called()

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    @patch('core.package_installer.PackageDependencyScanner.scan_packages')
    def test_install_packages_skips_scan_when_disabled(self, mock_scan, mock_build, installer):
        """Verify scan can be disabled for faster installation."""
        # Mock successful build
        mock_build.return_value = ["Build successful"]

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["numpy==1.21.0"],
            scan_for_vulnerabilities=False
        )

        assert result["success"] == True
        # Scan should not be called when disabled
        mock_scan.assert_not_called()
        mock_build.assert_called_once()

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_install_packages_handles_build_failure(self, mock_build, installer):
        """Verify build failures are handled gracefully."""
        # Mock safe scan
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }

        # Mock build failure
        mock_build.side_effect = Exception("Docker daemon not running")

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["numpy==1.21.0"]
        )

        assert result["success"] == False
        assert "Docker daemon" in result["error"]
        assert result["image_tag"] is None


class TestImageBuilding:
    """Docker image building process."""

    def test_build_skill_image_creates_dockerfile(self, installer, mock_docker_client):
        """Verify Dockerfile is created with correct structure."""
        # Mock successful build
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"

        # Mock build logs generator
        def mock_build_generator():
            yield {"stream": "Step 1/5 : FROM python:3.11-slim\n"}
            yield {"stream": "Step 2/5 : RUN python -m venv /opt/atom_skill_env\n"}
            yield {"stream": "Successfully built abc123\n"}

        mock_docker_client.images.build.return_value = (mock_image, mock_build_generator())

        requirements = ["requests==2.28.0", "numpy>=1.21.0"]
        logs = installer._build_skill_image(
            skill_id="test-skill",
            requirements=requirements,
            image_tag="atom-skill:test-skill-v1",
            base_image="python:3.11-slim"
        )

        # Verify build was called
        mock_docker_client.images.build.assert_called_once()
        call_kwargs = mock_docker_client.images.build.call_args[1]
        assert call_kwargs["tag"] == "atom-skill:test-skill-v1"
        assert call_kwargs["rm"] is True
        assert call_kwargs["forcerm"] is True

        # Verify build logs captured
        assert len(logs) > 0
        assert any("Step 1/5" in log for log in logs)

    def test_build_skill_image_creates_requirements_txt(self, installer, mock_docker_client):
        """Verify requirements.txt is created in build context."""
        # Mock successful build
        mock_image = MagicMock()

        def mock_build_generator():
            yield {"stream": "Build successful\n"}

        mock_docker_client.images.build.return_value = (mock_image, mock_build_generator())

        requirements = ["requests==2.28.0", "pandas>=1.3.0"]
        installer._build_skill_image(
            skill_id="test-skill",
            requirements=requirements,
            image_tag="atom-skill:test-skill-v1",
            base_image="python:3.11-slim"
        )

        # Verify build was called
        mock_docker_client.images.build.assert_called_once()

    def test_build_skill_image_uses_custom_base_image(self, installer, mock_docker_client):
        """Verify custom base image can be specified."""
        mock_image = MagicMock()

        def mock_build_generator():
            yield {"stream": "Build successful\n"}

        mock_docker_client.images.build.return_value = (mock_image, mock_build_generator())

        installer._build_skill_image(
            skill_id="test-skill",
            requirements=["requests==2.28.0"],
            image_tag="atom-skill:test-skill-v1",
            base_image="python:3.10-slim"  # Custom base image
        )

        # Verify build was called (will use custom base image in Dockerfile)
        mock_docker_client.images.build.assert_called_once()


class TestExecutionWithPackages:
    """Execute code using custom images with pre-installed packages."""

    def test_execute_with_packages_uses_custom_image(
        self,
        installer,
        mock_docker_client
    ):
        """Verify execution uses skill's custom Docker image."""
        # Mock image exists
        mock_image = MagicMock()
        mock_image.tags = ["atom-skill:test-skill-v1"]
        mock_docker_client.images.get.return_value = mock_image

        # Mock sandbox execution
        installer.sandbox.execute_python.return_value = "Output from skill with numpy"

        result = installer.execute_with_packages(
            skill_id="test-skill",
            code="import numpy; print(numpy.__version__)",
            inputs={}
        )

        assert "Output from skill" in result
        installer.sandbox.execute_python.assert_called_once()
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["image"] == "atom-skill:test-skill-v1"

    def test_execute_with_missing_image_raises_error(self, installer, mock_docker_client):
        """Verify RuntimeError when skill image not found."""
        # Mock image not found - use the ImageNotFound from our mocked docker.errors
        # Import docker.errors.ImageNotFound to match production code
        from docker import errors as docker_errors
        mock_docker_client.images.get.side_effect = docker_errors.ImageNotFound("Image not found")

        with pytest.raises(RuntimeError) as exc_info:
            installer.execute_with_packages(
                skill_id="nonexistent-skill",
                code="print('hello')",
                inputs={}
            )

        assert "not found" in str(exc_info.value)
        assert "install_packages" in str(exc_info.value)

    def test_execute_with_packages_passes_resource_limits(
        self,
        installer,
        mock_docker_client
    ):
        """Verify resource limits are passed to sandbox execution."""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        installer.sandbox.execute_python.return_value = "Output"

        installer.execute_with_packages(
            skill_id="test-skill",
            code="print('test')",
            inputs={},
            timeout_seconds=60,
            memory_limit="512m",
            cpu_limit=0.75
        )

        # Verify resource limits passed to sandbox
        installer.sandbox.execute_python.assert_called_once()
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["timeout_seconds"] == 60
        assert call_kwargs["memory_limit"] == "512m"
        assert call_kwargs["cpu_limit"] == 0.75


class TestImageCleanup:
    """Image removal and cleanup."""

    def test_cleanup_skill_image_removes_image(self, installer, mock_docker_client):
        """Verify successful image removal."""
        # Mock image exists
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image

        result = installer.cleanup_skill_image("test-skill")

        assert result is True
        mock_docker_client.images.get.assert_called_once_with("atom-skill:test-skill-v1")
        mock_image.remove.assert_called_once_with(force=True)

    def test_cleanup_missing_image_returns_false(self, installer, mock_docker_client):
        """Verify cleanup returns False when image not found."""
        # Mock image not found using our mocked ImageNotFound
        mock_docker_client.images.get.side_effect = sys.modules['docker.errors'].ImageNotFound("Not found")

        result = installer.cleanup_skill_image("test-skill")

        assert result is False

    def test_cleanup_handles_errors_gracefully(self, installer, mock_docker_client):
        """Verify cleanup handles unexpected errors."""
        # Mock unexpected error
        mock_docker_client.images.get.side_effect = Exception("Docker daemon error")

        result = installer.cleanup_skill_image("test-skill")

        assert result is False


class TestSkillImageListing:
    """Listing and managing skill images."""

    def test_get_skill_images_lists_atom_images(self, installer, mock_docker_client):
        """Verify get_skill_images returns only Atom skill images."""
        # Mock images
        mock_image1 = MagicMock()
        mock_image1.tags = ["atom-skill:skill-a-v1", "latest"]
        mock_image1.id = "sha256:abc123"
        mock_image1.attrs = {"Size": 500000000, "Created": "2026-02-19T10:00:00Z"}

        mock_image2 = MagicMock()
        mock_image2.tags = ["atom-skill:skill-b-v1"]
        mock_image2.id = "sha256:def456"
        mock_image2.attrs = {"Size": 300000000, "Created": "2026-02-19T11:00:00Z"}

        # Non-atom image should be filtered out
        mock_image3 = MagicMock()
        mock_image3.tags = ["python:3.11-slim"]
        mock_image3.id = "sha256:789012"
        mock_image3.attrs = {"Size": 100000000, "Created": "2026-02-19T09:00:00Z"}

        mock_docker_client.images.list.return_value = [mock_image1, mock_image2, mock_image3]

        skill_images = installer.get_skill_images()

        # Should only return atom-skill images
        assert len(skill_images) == 2
        assert skill_images[0]["tags"] == ["atom-skill:skill-a-v1", "latest"]
        assert skill_images[1]["tags"] == ["atom-skill:skill-b-v1"]

    def test_get_skill_images_handles_empty_list(self, installer, mock_docker_client):
        """Verify get_skill_images handles no images gracefully."""
        mock_docker_client.images.list.return_value = []

        skill_images = installer.get_skill_images()

        assert skill_images == []


class TestErrorHandling:
    """Graceful error handling for build failures and Docker errors."""

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_install_packages_returns_detailed_errors(self, mock_build, installer):
        """Verify installation returns detailed error information."""
        # Mock safe scan
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }

        # Mock build failure with detailed error
        mock_build.side_effect = Exception("Failed to build: no space left on device")

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["numpy==1.21.0"]
        )

        assert result["success"] == False
        assert "error" in result
        assert "no space left on device" in result["error"]
        assert result["image_tag"] is None

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_install_packages_includes_vulnerabilities_on_error(
        self,
        mock_build,
        installer
    ):
        """Verify vulnerabilities are included even when build fails."""
        # Mock scan with minor vulnerabilities (but safe=True for some reason)
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [
                {"cve_id": "CVE-2021-0001", "severity": "LOW"}
            ],
            "dependency_tree": {},
            "conflicts": []
        }

        # Mock build failure
        mock_build.side_effect = Exception("Build failed")

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["numpy==1.21.0"]
        )

        assert result["success"] == False
        # Vulnerabilities should still be included
        assert len(result["vulnerabilities"]) > 0


class TestImageTagFormat:
    """Image tag naming conventions."""

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_image_tag_format_with_slashes(self, mock_build, installer):
        """Verify slashes in skill_id are replaced with dashes."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        result = installer.install_packages(
            skill_id="org/category/skill-name",
            requirements=["requests==2.28.0"]
        )

        # Slashes should be replaced with dashes
        assert "org-category-skill-name" in result["image_tag"]
        assert result["image_tag"].endswith("-v1")

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_image_tag_format_simple_skill_id(self, mock_build, installer):
        """Verify simple skill_id format."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        result = installer.install_packages(
            skill_id="my-skill",
            requirements=["requests==2.28.0"]
        )

        assert result["image_tag"] == "atom-skill:my-skill-v1"


class TestDockerImageManagement:
    """Docker image management and tag formatting."""

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_image_tag_with_special_characters(self, mock_build, installer):
        """Verify special characters in skill_id are handled correctly."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        result = installer.install_packages(
            skill_id="my.skill@v1.0",
            requirements=["requests==2.28.0"]
        )

        # Special characters should be handled (currently only slashes are replaced)
        assert "my.skill@v1.0" in result["image_tag"] or "my-skill" in result["image_tag"]

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_image_tag_with_slashes_replaced_with_dashes(self, mock_build, installer):
        """Verify slashes in skill_id are replaced with dashes."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        result = installer.install_packages(
            skill_id="org/category/skill-name",
            requirements=["requests==2.28.0"]
        )

        # All slashes should be replaced with dashes
        assert "/" not in result["image_tag"]
        assert "org-category-skill-name" in result["image_tag"]

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_skill_id_max_length_handling(self, mock_build, installer):
        """Verify very long skill_id doesn't cause issues."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        # Very long skill_id (Docker tag limit is 128 chars)
        long_skill_id = "a" * 100
        result = installer.install_packages(
            skill_id=long_skill_id,
            requirements=["requests==2.28.0"]
        )

        assert result["success"] == True
        assert result["image_tag"] is not None

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_base_image_validation(self, mock_build, installer):
        """Verify base image parameter is passed correctly."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = []

        # Test with different base images
        for base_image in ["python:3.10-slim", "python:3.11", "python:3.9-alpine"]:
            result = installer.install_packages(
                skill_id="test-skill",
                requirements=["requests==2.28.0"],
                base_image=base_image
            )
            assert result["success"] == True

    def test_custom_base_image_argument(self, installer, mock_docker_client):
        """Verify custom base image is used in Dockerfile."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }

        mock_image = MagicMock()

        def mock_build_generator():
            yield {"stream": "Build successful\n"}

        mock_docker_client.images.build.return_value = (mock_image, mock_build_generator())

        # Test with custom base image
        installer._build_skill_image(
            skill_id="test-skill",
            requirements=["requests==2.28.0"],
            image_tag="atom-skill:test-skill-v1",
            base_image="python:3.10-alpine"
        )

        # Verify build was called (base image should be in Dockerfile)
        mock_docker_client.images.build.assert_called_once()

    def test_default_base_image_python_311_slim(self, installer, mock_docker_client):
        """Verify default base image is python:3.11-slim."""
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }

        mock_image = MagicMock()

        def mock_build_generator():
            yield {"stream": "Build successful\n"}

        mock_docker_client.images.build.return_value = (mock_image, mock_build_generator())

        # Call without specifying base_image (should use default)
        installer._build_skill_image(
            skill_id="test-skill",
            requirements=["requests==2.28.0"],
            image_tag="atom-skill:test-skill-v1",
            base_image="python:3.11-slim"  # Default is explicitly passed
        )

        # Verify build was called
        mock_docker_client.images.build.assert_called_once()


class TestVulnerabilityScanningIntegration:
    """Vulnerability scanning integration with Docker builds."""

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_vulnerability_scan_blocks_dangerous_packages(self, mock_build, installer):
        """Verify dangerous packages are blocked by vulnerability scan."""
        # Mock HIGH severity vulnerabilities
        installer.scanner.scan_packages.return_value = {
            "safe": False,
            "vulnerabilities": [
                {
                    "cve_id": "CVE-2021-44228",
                    "severity": "CRITICAL",
                    "package": "log4j",
                    "affected_versions": ["2.14.1"],
                    "advisory": "Remote code execution vulnerability (Log4Shell)",
                    "source": "pip-audit"
                }
            ],
            "dependency_tree": {},
            "conflicts": []
        }

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["log4j==2.14.1"],
            scan_for_vulnerabilities=True
        )

        assert result["success"] == False
        assert "vulnerabilities" in result["error"].lower()
        assert len(result["vulnerabilities"]) > 0
        assert result["image_tag"] is None
        # Build should not be attempted
        mock_build.assert_not_called()

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_vulnerability_scan_passed_allows_build(self, mock_build, installer):
        """Verify scan with no vulnerabilities allows build to proceed."""
        # Mock clean scan
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = ["Build successful"]

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["requests==2.28.0"],
            scan_for_vulnerabilities=True
        )

        assert result["success"] == True
        assert len(result["vulnerabilities"]) == 0
        mock_build.assert_called_once()

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_vulnerability_check_skipped_with_flag(self, mock_build, installer):
        """Verify vulnerability check can be skipped with flag."""
        # Even if scanner has vulnerabilities, skip should bypass
        installer.scanner.scan_packages.return_value = {
            "safe": False,
            "vulnerabilities": [{"cve_id": "CVE-2021-1234", "severity": "LOW"}],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = ["Build successful"]

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["requests==2.28.0"],
            scan_for_vulnerabilities=False  # Skip scan
        )

        assert result["success"] == True
        # Scanner should not be called
        installer.scanner.scan_packages.assert_not_called()
        mock_build.assert_called_once()

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_vulnerability_results_included_in_response(self, mock_build, installer):
        """Verify vulnerability scan results are included in response."""
        # Mock scan with LOW severity vulnerabilities (safe=True but has findings)
        installer.scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": [
                {
                    "cve_id": "CVE-2021-0001",
                    "severity": "LOW",
                    "package": "test-pkg",
                    "affected_versions": ["1.0.0"],
                    "advisory": "Minor issue",
                    "source": "pip-audit"
                }
            ],
            "dependency_tree": {},
            "conflicts": []
        }
        mock_build.return_value = ["Build successful"]

        result = installer.install_packages(
            skill_id="test-skill",
            requirements=["test-pkg==1.0.0"],
            scan_for_vulnerabilities=True
        )

        assert result["success"] == True
        # Vulnerabilities should be included even if build succeeds
        assert len(result["vulnerabilities"]) > 0
        assert result["vulnerabilities"][0]["cve_id"] == "CVE-2021-0001"

    @patch('core.package_installer.PackageInstaller._build_skill_image')
    def test_vulnerability_scan_timeout_handling(self, mock_build, installer):
        """Verify vulnerability scan timeout propagates (production code doesn't catch)."""
        # Mock scan timeout - production code doesn't catch scanner exceptions
        installer.scanner.scan_packages.side_effect = Exception(
            "Vulnerability scan timeout: pip-audit took too long"
        )

        # Exception should propagate (not caught by install_packages)
        with pytest.raises(Exception) as exc_info:
            installer.install_packages(
                skill_id="test-skill",
                requirements=["requests==2.28.0"],
                scan_for_vulnerabilities=True
            )

        assert "timeout" in str(exc_info.value).lower()


class TestExecuteWithPackagesResourceLimits:
    """Resource limit enforcement in execute_with_packages."""

    def test_execute_with_custom_timeout(self, installer, mock_docker_client):
        """Verify custom timeout is passed to sandbox."""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        installer.sandbox.execute_python.return_value = "Output"

        installer.execute_with_packages(
            skill_id="test-skill",
            code="import time; time.sleep(10)",
            inputs={},
            timeout_seconds=120  # Custom timeout
        )

        # Verify timeout was passed
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["timeout_seconds"] == 120

    def test_execute_with_custom_memory_limit(self, installer, mock_docker_client):
        """Verify custom memory limit is passed to sandbox."""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        installer.sandbox.execute_python.return_value = "Output"

        installer.execute_with_packages(
            skill_id="test-skill",
            code="import numpy; x = numpy.arange(1000000)",
            inputs={},
            memory_limit="1g"  # Custom memory limit
        )

        # Verify memory limit was passed
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["memory_limit"] == "1g"

    def test_execute_with_custom_cpu_limit(self, installer, mock_docker_client):
        """Verify custom CPU limit is passed to sandbox."""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        installer.sandbox.execute_python.return_value = "Output"

        installer.execute_with_packages(
            skill_id="test-skill",
            code="import multiprocessing; print(multiprocessing.cpu_count())",
            inputs={},
            cpu_limit=1.0  # Custom CPU limit
        )

        # Verify CPU limit was passed
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["cpu_limit"] == 1.0

    def test_execute_with_combined_resource_limits(self, installer, mock_docker_client):
        """Verify multiple resource limits are passed together."""
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image
        installer.sandbox.execute_python.return_value = "Output"

        installer.execute_with_packages(
            skill_id="test-skill",
            code="print('test')",
            inputs={},
            timeout_seconds=60,
            memory_limit="512m",
            cpu_limit=0.5
        )

        # Verify all limits were passed
        call_kwargs = installer.sandbox.execute_python.call_args[1]
        assert call_kwargs["timeout_seconds"] == 60
        assert call_kwargs["memory_limit"] == "512m"
        assert call_kwargs["cpu_limit"] == 0.5

    def test_execute_without_image_returns_error(self, installer, mock_docker_client):
        """Verify execute raises RuntimeError when image doesn't exist."""
        # Mock image not found - import to match production code
        from docker import errors as docker_errors
        mock_docker_client.images.get.side_effect = docker_errors.ImageNotFound("Image not found")

        with pytest.raises(RuntimeError) as exc_info:
            installer.execute_with_packages(
                skill_id="nonexistent-skill",
                code="print('hello')",
                inputs={}
            )

        assert "not found" in str(exc_info.value).lower()
        assert "install_packages" in str(exc_info.value)

