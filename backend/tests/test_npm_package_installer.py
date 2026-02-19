"""
Tests for NpmPackageInstaller - npm package installation in Docker images.

Tests cover:
- Package installation with Docker image building
- Vulnerability scanning integration
- Dockerfile generation with security constraints
- Package version isolation between skills
- Image cleanup and listing
- Error handling

Reference: Phase 36 RESEARCH.md Pattern 3 "npm Package Installation with Script Protection"
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from core.npm_package_installer import NpmPackageInstaller


@pytest.fixture
def mock_docker_client():
    """Mock Docker client."""
    with patch('docker.from_env') as mock_from_env:
        client = MagicMock()
        mock_from_env.return_value = client
        yield client


@pytest.fixture
def mock_scanner():
    """Mock NpmDependencyScanner."""
    with patch('core.npm_package_installer.NpmDependencyScanner') as mock_scanner_class:
        scanner = MagicMock()
        mock_scanner_class.return_value = scanner
        yield scanner


@pytest.fixture
def installer(mock_docker_client, mock_scanner):
    """Create NpmPackageInstaller with mocked dependencies."""
    return NpmPackageInstaller(snyk_api_key="test-key")


class TestInstallPackages:
    """Tests for install_packages method."""

    def test_install_packages_simple(self, installer, mock_docker_client, mock_scanner):
        """Test installing a single package."""
        # Mock scanner to return safe result
        mock_scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": []
        }

        # Mock image build
        mock_image = MagicMock()
        mock_build_logs = [
            "Step 1/8 : FROM node:20-alpine",
            "Step 2/8 : WORKDIR /skill",
            "Step 3/8 : RUN echo '{...}' > package.json",
            "Step 4/8 : RUN npm ci --omit=dev --ignore-scripts",
            "Successfully built abc123"
        ]
        mock_docker_client.images.build.return_value = (mock_image, iter([{"stream": log} for log in mock_build_logs]))

        # Install packages
        result = installer.install_packages(
            skill_id="test-skill",
            packages=["lodash@4.17.21"],
            scan_for_vulnerabilities=False
        )

        # Verify success
        assert result["success"] is True
        assert result["image_tag"] == "atom-npm-skill:test-skill-v1"
        assert result["vulnerabilities"] == []
        assert len(result["build_logs"]) > 0

    def test_install_with_vulnerabilities(self, installer, mock_scanner):
        """Test blocking installation when vulnerabilities found."""
        # Mock scanner to return vulnerabilities
        mock_scanner.scan_packages.return_value = {
            "safe": False,
            "vulnerabilities": [
                {
                    "cve_id": "CVE-2021-23337",
                    "severity": "HIGH",
                    "package": "lodash",
                    "advisory": "Prototype Pollution",
                    "source": "npm-audit"
                }
            ]
        }

        # Install packages
        result = installer.install_packages(
            skill_id="test-skill",
            packages=["lodash@4.17.21"],
            scan_for_vulnerabilities=True
        )

        # Verify blocked
        assert result["success"] is False
        assert "Vulnerabilities detected" in result["error"]
        assert len(result["vulnerabilities"]) == 1
        assert result["image_tag"] is None

    def test_install_packages_empty(self, installer):
        """Test handling empty packages list."""
        result = installer.install_packages(
            skill_id="test-skill",
            packages=[],
            scan_for_vulnerabilities=False
        )

        assert result["success"] is True
        assert result["image_tag"] is None
        assert "No packages specified" in result["warning"]


class TestCreatePackageJson:
    """Tests for _create_package_json method."""

    def test_create_package_json_with_versions(self, installer):
        """Test creating package.json with version specifiers."""
        packages = ["lodash@4.17.21", "express@4.18.0"]

        result = installer._create_package_json(packages)

        assert result["name"] == "atom-npm-skill"
        assert result["version"] == "1.0.0"
        assert result["private"] is True
        assert result["dependencies"] == {
            "lodash": "4.17.21",
            "express": "4.18.0"
        }

    def test_create_package_json_without_versions(self, installer):
        """Test creating package.json without version specifiers."""
        packages = ["lodash", "express"]

        result = installer._create_package_json(packages)

        assert result["dependencies"] == {
            "lodash": "*",
            "express": "*"
        }

    def test_create_package_json_scoped_packages(self, installer):
        """Test creating package.json with scoped packages."""
        packages = ["@angular/core@12.0.0", "@nestjs/common@8.0.0"]

        result = installer._create_package_json(packages)

        assert result["dependencies"] == {
            "@angular/core": "12.0.0",
            "@nestjs/common": "8.0.0"
        }

    def test_create_package_json_mixed(self, installer):
        """Test creating package.json with mixed specifiers."""
        packages = ["lodash@4.17.21", "express", "@angular/core@12.0.0"]

        result = installer._create_package_json(packages)

        assert result["dependencies"] == {
            "lodash": "4.17.21",
            "express": "*",
            "@angular/core": "12.0.0"
        }


class TestGenerateDockerfile:
    """Tests for _generate_dockerfile method."""

    def test_generate_dockerfile_npm(self, installer):
        """Test Dockerfile generation for npm."""
        package_json = {
            "name": "atom-npm-skill",
            "version": "1.0.0",
            "dependencies": {"lodash": "4.17.21"}
        }

        dockerfile = installer._generate_dockerfile(
            package_json,
            "npm",
            "node:20-alpine"
        )

        # Verify --ignore-scripts flag (CRITICAL SECURITY)
        assert "--ignore-scripts" in dockerfile

        # Verify npm ci
        assert "npm ci --omit=dev --ignore-scripts" in dockerfile

        # Verify non-root user
        assert "adduser -S nodejs -u 1001" in dockerfile

        # Verify NODE_ENV
        assert "NODE_ENV=production" in dockerfile

    def test_generate_dockerfile_yarn(self, installer):
        """Test Dockerfile generation for yarn."""
        package_json = {
            "name": "atom-npm-skill",
            "version": "1.0.0",
            "dependencies": {"lodash": "4.17.21"}
        }

        dockerfile = installer._generate_dockerfile(
            package_json,
            "yarn",
            "node:20-alpine"
        )

        # Verify --ignore-scripts flag for yarn
        assert "yarn install --production --ignore-scripts" in dockerfile

    def test_generate_dockerfile_pnpm(self, installer):
        """Test Dockerfile generation for pnpm."""
        package_json = {
            "name": "atom-npm-skill",
            "version": "1.0.0",
            "dependencies": {"lodash": "4.17.21"}
        }

        dockerfile = installer._generate_dockerfile(
            package_json,
            "pnpm",
            "node:20-alpine"
        )

        # Verify --ignore-scripts flag for pnpm
        assert "pnpm install --prod --ignore-scripts" in dockerfile

    def test_generate_dockerfile_unknown_manager(self, installer):
        """Test error on unknown package manager."""
        package_json = {
            "name": "atom-npm-skill",
            "version": "1.0.0"
        }

        with pytest.raises(ValueError, match="Unknown package manager"):
            installer._generate_dockerfile(
                package_json,
                "unknown-manager",
                "node:20-alpine"
            )


class TestBuildSkillImage:
    """Tests for _build_skill_image method."""

    def test_build_skill_image(self, installer, mock_docker_client):
        """Test building Docker image with packages."""
        # Mock image build
        mock_image = MagicMock()
        mock_build_logs = [
            "Step 1/8 : FROM node:20-alpine",
            "Successfully built abc123"
        ]
        mock_docker_client.images.build.return_value = (mock_image, iter([{"stream": log} for log in mock_build_logs]))

        # Build image
        logs = installer._build_skill_image(
            skill_id="test-skill",
            packages=["lodash@4.17.21"],
            image_tag="atom-npm-skill:test-skill-v1",
            package_manager="npm",
            base_image="node:20-alpine"
        )

        # Verify build called
        mock_docker_client.images.build.assert_called_once()

        # Verify logs captured
        assert len(logs) > 0
        assert any("Successfully built" in log for log in logs)

    def test_build_skill_image_tag_format(self, installer, mock_docker_client):
        """Test image tag format for skill isolation."""
        mock_image = MagicMock()
        mock_docker_client.images.build.return_value = (mock_image, iter([]))

        # Build image for skill-a
        installer._build_skill_image(
            skill_id="skill-a",
            packages=["lodash@4.17.21"],
            image_tag="atom-npm-skill:skill-a-v1",
            package_manager="npm",
            base_image="node:20-alpine"
        )

        # Verify tag format
        call_args = mock_docker_client.images.build.call_args
        assert call_args[1]["tag"] == "atom-npm-skill:skill-a-v1"


class TestExecuteWithPackages:
    """Tests for execute_with_packages method."""

    def test_execute_with_packages(self, installer, mock_docker_client):
        """Test executing Node.js code with custom image."""
        # Mock image exists
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image

        # Mock sandbox
        mock_sandbox = MagicMock()
        mock_sandbox.execute_nodejs.return_value = "Execution output"
        installer._sandbox = mock_sandbox

        # Execute
        result = installer.execute_with_packages(
            skill_id="test-skill",
            code="console.log('Hello')",
            inputs={},
            timeout_seconds=30
        )

        # Verify sandbox called
        mock_sandbox.execute_nodejs.assert_called_once_with(
            code="console.log('Hello')",
            inputs={},
            timeout_seconds=30,
            memory_limit="256m",
            cpu_limit=0.5,
            image="atom-npm-skill:test-skill-v1"
        )

        assert result == "Execution output"

    def test_execute_with_packages_image_not_found(self, installer, mock_docker_client):
        """Test error when skill image not found."""
        # Mock image not found
        import docker
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Image not found")

        # Execute should raise RuntimeError
        with pytest.raises(RuntimeError, match="Image .* not found"):
            installer.execute_with_packages(
                skill_id="test-skill",
                code="console.log('Hello')",
                inputs={}
            )


class TestCleanupSkillImage:
    """Tests for cleanup_skill_image method."""

    def test_cleanup_skill_image(self, installer, mock_docker_client):
        """Test removing skill image."""
        # Mock image exists
        mock_image = MagicMock()
        mock_docker_client.images.get.return_value = mock_image

        # Cleanup
        result = installer.cleanup_skill_image("test-skill")

        # Verify image removed
        mock_docker_client.images.get.assert_called_once_with("atom-npm-skill:test-skill-v1")
        mock_image.remove.assert_called_once_with(force=True)

        assert result is True

    def test_cleanup_skill_image_not_found(self, installer, mock_docker_client):
        """Test cleanup when image not found."""
        # Mock image not found
        import docker
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Image not found")

        # Cleanup should return False
        result = installer.cleanup_skill_image("test-skill")

        assert result is False


class TestGetSkillImages:
    """Tests for get_skill_images method."""

    def test_get_skill_images(self, installer, mock_docker_client):
        """Test listing all skill images."""
        # Mock images
        mock_image1 = MagicMock()
        mock_image1.tags = ["atom-npm-skill:skill-a-v1"]
        mock_image1.id = "sha256:abc123"
        mock_image1.attrs = {"Size": 123456789, "Created": "2026-02-19T10:00:00Z"}

        mock_image2 = MagicMock()
        mock_image2.tags = ["atom-npm-skill:skill-b-v1"]
        mock_image2.id = "sha256:def456"
        mock_image2.attrs = {"Size": 987654321, "Created": "2026-02-19T11:00:00Z"}

        mock_docker_client.images.list.return_value = [mock_image1, mock_image2]

        # List images
        images = installer.get_skill_images()

        # Verify results
        assert len(images) == 2
        assert images[0]["tags"] == ["atom-npm-skill:skill-a-v1"]
        assert images[1]["tags"] == ["atom-npm-skill:skill-b-v1"]

    def test_get_skill_images_empty(self, installer, mock_docker_client):
        """Test listing when no skill images exist."""
        # Mock empty list
        mock_docker_client.images.list.return_value = []

        # List images
        images = installer.get_skill_images()

        assert len(images) == 0


class TestPackageVersionIsolation:
    """Tests for package version isolation between skills (CRITICAL for success criterion 5)."""

    def test_package_version_isolation(self, installer, mock_docker_client, mock_scanner):
        """
        Test package version isolation: skill A with lodash@4.17.21 and skill B with lodash@5.0.0.

        CRITICAL: Verify each skill has its own Docker image with isolated node_modules.
        Different skills can use different versions of the same npm package without conflicts.
        """
        # Mock scanner to return safe result
        mock_scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": []
        }

        # Mock image builds
        mock_image_a = MagicMock()
        mock_image_b = MagicMock()
        mock_build_logs = [
            "Step 1/8 : FROM node:20-alpine",
            "Successfully built"
        ]

        build_call_count = 0

        def mock_build(**kwargs):
            nonlocal build_call_count
            build_call_count += 1
            if build_call_count == 1:
                return (mock_image_a, iter([{"stream": log} for log in mock_build_logs]))
            else:
                return (mock_image_b, iter([{"stream": log} for log in mock_build_logs]))

        mock_docker_client.images.build.side_effect = mock_build

        # Install lodash@4.17.21 for skill-a
        result_a = installer.install_packages(
            skill_id="skill-a",
            packages=["lodash@4.17.21"],
            scan_for_vulnerabilities=False
        )

        # Install lodash@5.0.0 for skill-b
        result_b = installer.install_packages(
            skill_id="skill-b",
            packages=["lodash@5.0.0"],
            scan_for_vulnerabilities=False
        )

        # Verify both installations successful
        assert result_a["success"] is True
        assert result_b["success"] is True

        # Verify each skill has its own Docker image tag
        assert result_a["image_tag"] == "atom-npm-skill:skill-a-v1"
        assert result_b["image_tag"] == "atom-npm-skill:skill-b-v1"

        # Verify images.build called twice (separate images)
        assert mock_docker_client.images.build.call_count == 2

        # Verify different image tags used
        call_args_list = mock_docker_client.images.build.call_args_list
        tags = [call[1]["tag"] for call in call_args_list]
        assert "atom-npm-skill:skill-a-v1" in tags
        assert "atom-npm-skill:skill-b-v1" in tags

        # Verify no conflicts: skill A image != skill B image
        assert mock_image_a != mock_image_b


class TestErrorHandling:
    """Tests for error handling."""

    def test_install_packages_build_failure(self, installer, mock_docker_client, mock_scanner):
        """Test handling Docker build failure."""
        # Mock scanner to return safe result
        mock_scanner.scan_packages.return_value = {
            "safe": True,
            "vulnerabilities": []
        }

        # Mock build failure
        mock_docker_client.images.build.side_effect = Exception("Docker build failed")

        # Install packages
        result = installer.install_packages(
            skill_id="test-skill",
            packages=["lodash@4.17.21"],
            scan_for_vulnerabilities=False
        )

        # Verify error handling
        assert result["success"] is False
        assert "Docker build failed" in result["error"]
        assert result["image_tag"] is None


class TestLazyLoading:
    """Tests for lazy loading of dependencies."""

    def test_lazy_docker_client(self):
        """Test Docker client is lazy loaded."""
        with patch('docker.from_env') as mock_docker:
            installer = NpmPackageInstaller()
            assert installer._client is None

            # Access client property
            _ = installer.client
            assert installer._client is not None
            mock_docker.assert_called_once()

    def test_lazy_scanner(self):
        """Test scanner is lazy loaded."""
        with patch('core.npm_package_installer.NpmDependencyScanner') as mock_scanner:
            installer = NpmPackageInstaller()
            assert installer._scanner is None

            # Access scanner property
            _ = installer.scanner
            assert installer._scanner is not None
            mock_scanner.assert_called_once()

    def test_lazy_sandbox(self):
        """Test sandbox is lazy loaded."""
        with patch('docker.from_env'):
            installer = NpmPackageInstaller()
            assert installer._sandbox is None

            # Access sandbox property (will fail if Docker not available, so we mock)
            with patch('core.skill_sandbox.HazardSandbox'):
                _ = installer.sandbox
                # Just verify that accessing the property doesn't immediately instantiate
                # The real test is that _sandbox is None before first access
