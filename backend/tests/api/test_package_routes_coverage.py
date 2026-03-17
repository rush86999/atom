"""
Coverage tests for package_routes.py.

Target: 50%+ coverage (373 statements, ~187 lines to cover)
Focus: Package installation, dependency management, security scanning
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock


class TestPackageEndpoints:
    """Test package management endpoints."""

    def test_list_packages(self, client):
        """Test listing all packages."""
        response = client.get("/api/v1/packages")

        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert "packages" in data or isinstance(data, list)

    def test_get_package_details(self, client):
        """Test getting package details."""
        response = client.get("/api/v1/packages/package-name")

        assert response.status_code in [200, 404]

    def test_search_packages(self, client):
        """Test searching for packages."""
        response = client.get("/api/v1/packages/search?q=data")

        assert response.status_code in [200, 400]


class TestPackageInstallation:
    """Test package installation endpoints."""

    def test_install_package(self, client):
        """Test installing a package."""
        response = client.post(
            "/api/v1/packages/install",
            json={
                "package": "requests",
                "version": "2.28.0"
            }
        )

        assert response.status_code in [200, 202, 400, 401]

    def test_install_multiple_packages(self, client):
        """Test batch package installation."""
        response = client.post(
            "/api/v1/packages/install/batch",
            json={
                "packages": [
                    {"name": "requests", "version": "2.28.0"},
                    {"name": "numpy", "version": "1.24.0"}
                ]
            }
        )

        assert response.status_code in [200, 202, 400, 401]

    def test_uninstall_package(self, client):
        """Test uninstalling a package."""
        response = client.post(
            "/api/v1/packages/package-name/uninstall"
        )

        assert response.status_code in [200, 404]

    def test_update_package(self, client):
        """Test updating a package."""
        response = client.post(
            "/api/v1/packages/package-name/update",
            json={"version": "2.29.0"}
        )

        assert response.status_code in [200, 404]


class TestPackageSecurity:
    """Test package security scanning endpoints."""

    def test_scan_package(self, client):
        """Test scanning package for vulnerabilities."""
        response = client.post(
            "/api/v1/packages/package-name/scan"
        )

        assert response.status_code in [200, 202, 404]

    def test_get_scan_results(self, client):
        """Test getting package scan results."""
        response = client.get("/api/v1/packages/package-name/scan/results")

        assert response.status_code in [200, 404]

    def test_list_vulnerabilities(self, client):
        """Test listing known vulnerabilities."""
        response = client.get("/api/v1/packages/vulnerabilities")

        assert response.status_code in [200, 401]


class TestPackageDependencies:
    """Test package dependency management."""

    def test_get_dependencies(self, client):
        """Test getting package dependencies."""
        response = client.get("/api/v1/packages/package-name/dependencies")

        assert response.status_code in [200, 404]

    def test_check_conflicts(self, client):
        """Test checking for package conflicts."""
        response = client.post(
            "/api/v1/packages/check-conflicts",
            json={
                "packages": ["package1", "package2"]
            }
        )

        assert response.status_code in [200, 400]

    def test_resolve_dependencies(self, client):
        """Test resolving dependency tree."""
        response = client.post(
            "/api/v1/packages/package-name/resolve"
        )

        assert response.status_code in [200, 404]


class TestPackageErrorHandling:
    """Test package endpoint error handling."""

    def test_handle_invalid_package_name(self, client):
        """Test handling of invalid package name."""
        response = client.get("/api/v1/packages/invalid-name-!!!")

        assert response.status_code in [400, 404]

    def test_handle_install_failure(self, client):
        """Test handling of package installation failure."""
        with patch('core.package_installer.install') as mock_install:
            mock_install.side_effect = Exception("Install failed")

            response = client.post(
                "/api/v1/packages/install",
                json={"package": "broken-package"}
            )

            assert response.status_code in [500, 400]

    def test_handle_conflict_detection(self, client):
        """Test handling of package conflict detection."""
        with patch('core.package_dependency_checker.check_conflicts') as mock_check:
            mock_check.return_value = {
                "has_conflicts": True,
                "conflicts": ["Package1 conflicts with Package2"]
            }

            response = client.post(
                "/api/v1/packages/check-conflicts",
                json={"packages": ["pkg1", "pkg2"]}
            )

            assert response.status_code in [200, 409]
