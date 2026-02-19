"""
Tests for NpmDependencyScanner - npm package vulnerability scanning.

Tests cover:
- npm audit integration
- yarn/pnpm package manager support
- Snyk integration (optional)
- Timeout handling
- Vulnerability parsing
- Dependency tree building
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.core.npm_dependency_scanner import NpmDependencyScanner


@pytest.fixture
def scanner():
    """Create NpmDependencyScanner instance."""
    return NpmDependencyScanner()


@pytest.fixture
def mock_npm_audit_json():
    """Mock npm audit JSON output with vulnerabilities."""
    return {
        "vulnerabilities": {
            "lodash": [
                {
                    "cwe": "CWE-787",
                    "severity": "high",
                    "range": "<4.17.21",
                    "title": "Out-of-bounds Write in lodash"
                }
            ],
            "axios": [
                {
                    "cwe": "CWE-79",
                    "severity": "medium",
                    "range": "<0.21.0",
                    "title": "Cross-site Scripting in axios"
                }
            ]
        }
    }


@pytest.fixture
def mock_npm_list_json():
    """Mock npm list JSON output."""
    return {
        "dependencies": {
            "lodash": {
                "version": "4.17.20",
                "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz"
            },
            "axios": {
                "version": "0.20.0",
                "resolved": "https://registry.npmjs.org/axios/-/axios-0.20.0.tgz"
            }
        }
    }


class TestNpmDependencyScanner:
    """Test suite for NpmDependencyScanner."""

    def test_scan_packages_empty(self, scanner):
        """Test scanning empty package list returns safe."""
        result = scanner.scan_packages([])

        assert result["safe"] is True
        assert result["vulnerabilities"] == []
        assert result["dependency_tree"] == {}
        assert result["warning"] is None

    def test_scan_packages_with_vulnerabilities(
        self,
        scanner,
        mock_npm_audit_json,
        mock_npm_list_json
    ):
        """Test scanning packages with vulnerabilities."""
        packages = ["lodash@4.17.20", "axios@0.20.0"]

        with patch('subprocess.run') as mock_run:
            # Mock npm install
            mock_install = Mock(returncode=0)
            # Mock npm list
            mock_list = Mock(
                returncode=0,
                stdout=json.dumps(mock_npm_list_json)
            )
            # Mock npm audit
            mock_audit = Mock(
                returncode=1,  # 1 = vulnerabilities found
                stdout=json.dumps(mock_npm_audit_json)
            )

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages)

            assert result["safe"] is False
            assert len(result["vulnerabilities"]) == 2
            assert result["vulnerabilities"][0]["package"] == "lodash"
            assert result["vulnerabilities"][0]["severity"] == "high"
            assert result["vulnerabilities"][1]["package"] == "axios"
            assert result["vulnerabilities"][1]["severity"] == "medium"
            assert len(result["dependency_tree"]) == 2

    def test_scan_packages_no_vulnerabilities(
        self,
        scanner,
        mock_npm_list_json
    ):
        """Test scanning packages without vulnerabilities."""
        packages = ["lodash@4.17.21"]

        with patch('subprocess.run') as mock_run:
            # Mock npm install
            mock_install = Mock(returncode=0)
            # Mock npm list
            mock_list = Mock(
                returncode=0,
                stdout=json.dumps(mock_npm_list_json)
            )
            # Mock npm audit (no vulnerabilities)
            mock_audit = Mock(
                returncode=0,  # 0 = no vulnerabilities
                stdout=json.dumps({"vulnerabilities": {}})
            )

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages)

            assert result["safe"] is True
            assert len(result["vulnerabilities"]) == 0

    def test_npm_audit_timeout(self, scanner):
        """Test npm audit timeout returns safe=True with warning."""
        packages = ["lodash@4.17.20"]

        with patch('subprocess.run') as mock_run:
            from subprocess import TimeoutExpired

            # Mock npm install success, but _install_packages times out
            # This will propagate to top-level try/except
            mock_run.side_effect = TimeoutExpired("npm install", 120)

            result = scanner.scan_packages(packages)

            assert result["safe"] is True  # Timeout doesn't mean unsafe
            assert result["warning"] is not None
            assert "timed out" in result["warning"].lower() or "failed" in result["warning"].lower()

    def test_create_package_json(self, scanner):
        """Test package.json creation from package specifiers."""
        packages = ["lodash@4.17.21", "express@^4.18.0", "react"]

        result = scanner._create_package_json(packages)

        assert result["name"] == "atom-scan-temp"
        assert result["private"] is True
        assert result["dependencies"]["lodash"] == "4.17.21"
        assert result["dependencies"]["express"] == "^4.18.0"
        assert result["dependencies"]["react"] == "*"

    def test_scoped_package_parsing(self, scanner):
        """Test scoped package name parsing (@scope/name)."""
        packages = ["@angular/core@12.0.0", "@babel/preset-env"]

        result = scanner._create_package_json(packages)

        assert "@angular/core" in result["dependencies"]
        assert result["dependencies"]["@angular/core"] == "12.0.0"
        assert "@babel/preset-env" in result["dependencies"]
        assert result["dependencies"]["@babel/preset-env"] == "*"

    def test_yarn_package_manager(
        self,
        scanner
    ):
        """Test yarn package manager support."""
        packages = ["lodash@4.17.20"]

        # Create minimal mock for single package
        mock_list_json = {
            "dependencies": {
                "lodash": {
                    "version": "4.17.20",
                    "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz"
                }
            }
        }

        mock_audit_json = {
            "vulnerabilities": {
                "lodash": [
                    {
                        "cwe": "CWE-787",
                        "severity": "high",
                        "range": "<4.17.21",
                        "title": "Out-of-bounds Write in lodash"
                    }
                ]
            }
        }

        with patch('subprocess.run') as mock_run:
            # Mock yarn install
            mock_install = Mock(returncode=0)
            # Mock npm list (same format for all)
            mock_list = Mock(
                returncode=0,
                stdout=json.dumps(mock_list_json)
            )
            # Mock yarn audit
            mock_audit = Mock(
                returncode=1,
                stdout=json.dumps(mock_audit_json)
            )

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages, package_manager="yarn")

            assert len(result["vulnerabilities"]) == 1
            assert result["vulnerabilities"][0]["source"] == "yarn-audit"
            assert result["vulnerabilities"][0]["package"] == "lodash"

            # Verify yarn commands were called
            calls = mock_run.call_args_list
            assert "yarn" in calls[0][0][0][0]
            assert "yarn" in calls[2][0][0][0]

    def test_pnpm_package_manager(
        self,
        scanner
    ):
        """Test pnpm package manager support."""
        packages = ["lodash@4.17.20"]

        # Create minimal mock for single package
        mock_list_json = {
            "dependencies": {
                "lodash": {
                    "version": "4.17.20",
                    "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz"
                }
            }
        }

        mock_audit_json = {
            "vulnerabilities": {
                "lodash": [
                    {
                        "cwe": "CWE-787",
                        "severity": "high",
                        "range": "<4.17.21",
                        "title": "Out-of-bounds Write in lodash"
                    }
                ]
            }
        }

        with patch('subprocess.run') as mock_run:
            mock_install = Mock(returncode=0)
            mock_list = Mock(
                returncode=0,
                stdout=json.dumps(mock_list_json)
            )
            mock_audit = Mock(
                returncode=1,
                stdout=json.dumps(mock_audit_json)
            )

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages, package_manager="pnpm")

            assert len(result["vulnerabilities"]) == 1
            assert result["vulnerabilities"][0]["source"] == "pnpm-audit"

    def test_snyk_integration(self, scanner):
        """Test Snyk integration when API key is provided."""
        scanner.snyk_api_key = "test-snyk-key"
        packages = ["lodash@4.17.21"]

        mock_snyk_json = {
            "vulnerabilities": [
                {
                    "identifiers": {"CVE": ["CVE-2021-23337"]},
                    "severity": "high",
                    "packageName": "lodash",
                    "semver": {"vulnerable": ["<4.17.21"]},
                    "title": "Prototype Pollution in lodash"
                }
            ]
        }

        with patch('subprocess.run') as mock_run:
            with patch('shutil.which') as mock_which:
                mock_which.return_value = "/usr/bin/snyk"

                mock_install = Mock(returncode=0)
                mock_list = Mock(returncode=0, stdout='{"dependencies": {}}')
                mock_audit = Mock(returncode=0, stdout='{"vulnerabilities": {}}')
                mock_snyk = Mock(
                    returncode=1,  # Vulnerabilities found
                    stdout=json.dumps(mock_snyk_json)
                )

                mock_run.side_effect = [mock_install, mock_list, mock_audit, mock_snyk]

                result = scanner.scan_packages(packages)

                assert len(result["vulnerabilities"]) == 1
                assert result["vulnerabilities"][0]["source"] == "snyk"
                assert result["vulnerabilities"][0]["cve_id"] == "CVE-2021-23337"

    def test_snyk_not_available(self, scanner):
        """Test graceful skip when Snyk CLI not installed."""
        scanner.snyk_api_key = "test-snyk-key"
        packages = ["lodash@4.17.21"]

        with patch('subprocess.run') as mock_run:
            with patch('shutil.which') as mock_which:
                mock_which.return_value = None  # Snyk not found

                mock_install = Mock(returncode=0)
                mock_list = Mock(returncode=0, stdout='{"dependencies": {}}')
                mock_audit = Mock(returncode=0, stdout='{"vulnerabilities": {}}')

                mock_run.side_effect = [mock_install, mock_list, mock_audit]

                result = scanner.scan_packages(packages)

                # Should not fail, just skip Snyk
                assert "safe" in result
                assert result["vulnerabilities"] == []

    def test_snyk_no_api_key(self, scanner):
        """Test Snyk not run when API key not provided."""
        scanner.snyk_api_key = None
        packages = ["lodash@4.17.21"]

        with patch('subprocess.run') as mock_run:
            mock_install = Mock(returncode=0)
            mock_list = Mock(returncode=0, stdout='{"dependencies": {}}')
            mock_audit = Mock(returncode=0, stdout='{"vulnerabilities": {}}')

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages)

            # Should only run npm audit (3 calls), not Snyk
            assert mock_run.call_count == 3

    def test_vulnerability_parsing(self, scanner):
        """Test correct parsing of npm audit JSON format."""
        packages = ["lodash@4.17.20"]

        mock_audit_json = {
            "vulnerabilities": {
                "lodash": [
                    {
                        "cwe": "CWE-1321",
                        "severity": "critical",
                        "range": "<4.17.21",
                        "title": "Prototype Pollution"
                    }
                ]
            }
        }

        with patch('subprocess.run') as mock_run:
            mock_install = Mock(returncode=0)
            mock_list = Mock(returncode=0, stdout='{"dependencies": {}}')
            mock_audit = Mock(
                returncode=1,
                stdout=json.dumps(mock_audit_json)
            )

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages)

            assert len(result["vulnerabilities"]) == 1
            vuln = result["vulnerabilities"][0]
            assert vuln["package"] == "lodash"
            assert vuln["severity"] == "critical"
            assert vuln["cve_id"] == "CWE-1321"
            assert vuln["affected_versions"] == "<4.17.21" or vuln["affected_versions"] == ["<4.17.21"]
            assert "Prototype Pollution" in vuln["advisory"]

    def test_dependency_tree_building(self, scanner):
        """Test dependency tree parsing from npm list."""
        packages = ["lodash@4.17.21"]

        mock_list_json = {
            "dependencies": {
                "lodash": {
                    "version": "4.17.21",
                    "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz"
                }
            }
        }

        with patch('subprocess.run') as mock_run:
            mock_install = Mock(returncode=0)
            mock_list = Mock(
                returncode=0,
                stdout=json.dumps(mock_list_json)
            )
            mock_audit = Mock(returncode=0, stdout='{"vulnerabilities": {}}')

            mock_run.side_effect = [mock_install, mock_list, mock_audit]

            result = scanner.scan_packages(packages)

            assert "lodash" in result["dependency_tree"]
            assert result["dependency_tree"]["lodash"]["version"] == "4.17.21"
            assert "registry.npmjs.org" in result["dependency_tree"]["lodash"]["resolved"]

    def test_invalid_package_manager(self, scanner):
        """Test error handling for invalid package manager."""
        packages = ["lodash@4.17.20"]

        # ValueError is raised internally but caught in scan_packages
        # which returns safe=True with a warning
        result = scanner.scan_packages(packages, package_manager="invalid")

        # Should handle gracefully, not raise
        assert result["safe"] is True
        assert result["warning"] is not None
        assert "failed" in result["warning"].lower()

    def test_install_failure_handling(self, scanner):
        """Test handling of npm install failure."""
        packages = ["lodash@4.17.20"]

        with patch('subprocess.run') as mock_run:
            mock_install = Mock(returncode=1, stderr="Install failed")
            mock_run.side_effect = [mock_install]

            result = scanner.scan_packages(packages)

            # Should return safe=True with warning (install failure != vulnerability)
            assert result["safe"] is True
            assert "warning" in result
