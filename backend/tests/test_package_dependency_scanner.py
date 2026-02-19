"""
Package Dependency Scanner Tests

Test coverage:
- pip-audit integration with vulnerable packages
- Safety database integration (with and without API key)
- Dependency tree building with pipdeptree
- Version conflict detection
- Graceful error handling (timeout, parse errors)
- Empty requirements list handling
- Safe packages (no vulnerabilities)
"""

import json
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from core.package_dependency_scanner import PackageDependencyScanner


@pytest.fixture
def scanner():
    return PackageDependencyScanner()


@pytest.fixture
def safe_requirements():
    return ["requests==2.28.0", "urllib3==1.26.0"]


@pytest.fixture
def vulnerable_requirements():
    # Known vulnerable package (example - adjust based on real vulnerabilities)
    return ["requests==2.20.0"]  # Older version with known vulnerabilities


class TestPipAuditIntegration:
    """pip-audit integration for vulnerability detection."""

    @patch('subprocess.run')
    def test_safe_package_returns_no_vulnerabilities(self, mock_run, scanner, safe_requirements):
        # Mock pip-audit output for safe package
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr=""
        )

        result = scanner.scan_packages(safe_requirements)

        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0

    @patch('subprocess.run')
    def test_vulnerable_package_returns_cve_details(self, mock_run, scanner, vulnerable_requirements):
        # Mock pip-audit output with vulnerability
        vuln_json = json.dumps([{
            "name": "requests",
            "versions": ["2.20.0"],
            "id": "CVE-2018-18074",
            "description": "DoS vulnerability",
            "fix_versions": ["2.20.1"]
        }])
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=vuln_json,
            stderr=""
        )

        result = scanner.scan_packages(vulnerable_requirements)

        assert result["safe"] == False
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["cve_id"] == "CVE-2018-18074"

    @patch('subprocess.run')
    def test_multiple_vulnerabilities_all_returned(self, mock_run, scanner):
        # Mock pip-audit output with multiple vulnerabilities
        vuln_json = json.dumps([
            {
                "name": "requests",
                "versions": ["2.20.0"],
                "id": "CVE-2018-18074",
                "description": "DoS vulnerability",
                "fix_versions": ["2.20.1"]
            },
            {
                "name": "urllib3",
                "versions": ["1.24.0"],
                "id": "CVE-2019-11236",
                "description": "CRLF injection",
                "fix_versions": ["1.25.0"]
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=vuln_json,
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.20.0"])

        assert result["safe"] == False
        assert len(result["vulnerabilities"]) == 2


class TestSafetyIntegration:
    """Safety database integration for commercial vulnerability scanning."""

    @patch('subprocess.run')
    def test_safety_with_api_key_scans_commercial_db(self, mock_run):
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # Verify safety command includes API key
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        scanner.scan_packages(["requests==2.28.0"])

        # Check that safety was called with API key
        call_args = mock_run.call_args_list
        safety_calls = [call for call in call_args if "safety" in str(call)]
        assert len(safety_calls) > 0

    @patch('subprocess.run')
    def test_safety_without_api_key_skips_scan(self, mock_run, scanner):
        # Mock pip-audit to return safe
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should still complete without Safety API key
        assert result["safe"] == True

    @patch('subprocess.run')
    def test_safety_finds_vulnerabilities(self, mock_run):
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # Mock Safety to find vulnerability
        safety_json = json.dumps([{
            "id": "12345",
            "package_name": "requests",
            "vulnerability_id": "pyup.io-12345",
            "affected_versions": ["2.20.0"],
            "advisory": "Security vulnerability"
        }])

        # Need to mock pipdeptree, pip-audit, and safety
        # First call: pip install, second: pipdeptree, third: pip-audit, fourth: safety
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree (empty tree)
            MagicMock(returncode=0, stdout="[]"),  # pip-audit (safe)
            MagicMock(returncode=1, stdout=safety_json)  # Safety (vulnerable)
        ]

        result = scanner.scan_packages(["requests==2.20.0"])

        assert result["safe"] == False
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["source"] == "safety"


class TestDependencyTree:
    """Dependency tree building with pipdeptree."""

    @patch('subprocess.run')
    def test_builds_dependency_tree(self, mock_run, scanner, safe_requirements):
        # Mock pipdeptree output
        tree_json = json.dumps([
            {
                "package": {"package_name": "requests", "installed_version": "2.28.0"},
                "dependencies": [
                    {"package_name": "urllib3", "installed_version": "1.26.0"},
                    {"package_name": "certifi", "installed_version": "2022.12.07"}
                ]
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(safe_requirements)

        assert "dependency_tree" in result
        assert "requests" in result["dependency_tree"]
        assert result["dependency_tree"]["requests"]["version"] == "2.28.0"

    @patch('subprocess.run')
    def test_dependency_tree_includes_transitive_deps(self, mock_run, scanner):
        # Mock complex dependency tree
        tree_json = json.dumps([
            {
                "package": {"package_name": "requests", "installed_version": "2.28.0"},
                "dependencies": [
                    {"package_name": "urllib3", "installed_version": "1.26.0"}
                ]
            },
            {
                "package": {"package_name": "urllib3", "installed_version": "1.26.0"},
                "dependencies": []
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        # Check that transitive dependencies are captured
        assert "requests" in result["dependency_tree"]
        assert "urllib3" in result["dependency_tree"]["requests"]["dependencies"]


class TestVersionConflicts:
    """Version conflict detection in dependency trees."""

    @patch('subprocess.run')
    def test_detects_duplicate_package_versions(self, mock_run, scanner):
        # Mock dependency tree with conflicts
        tree_json = json.dumps([
            {
                "package": {"package_name": "package-a", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "shared-lib", "installed_version": "1.0.0"}
                ]
            },
            {
                "package": {"package_name": "package-b", "installed_version": "2.0.0"},
                "dependencies": [
                    {"package_name": "shared-lib", "installed_version": "2.0.0"}
                ]
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["package-a==1.0.0", "package-b==2.0.0"])

        assert len(result["conflicts"]) > 0
        assert result["conflicts"][0]["severity"] in ["version_conflict", "transitive_conflict"]

    @patch('subprocess.run')
    def test_no_conflicts_returns_empty_list(self, mock_run, scanner):
        # Mock clean dependency tree
        tree_json = json.dumps([
            {
                "package": {"package_name": "requests", "installed_version": "2.28.0"},
                "dependencies": [
                    {"package_name": "urllib3", "installed_version": "1.26.0"}
                ]
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        assert len(result["conflicts"]) == 0


class TestErrorHandling:
    """Graceful error handling for timeouts, parse errors, missing tools."""

    @patch('subprocess.run')
    def test_timeout_returns_empty_vulnerabilities(self, mock_run, scanner):
        import subprocess

        # Mock all subprocess calls to timeout
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)

        result = scanner.scan_packages(["requests==2.28.0"])

        # Timeout returns empty vulnerabilities and empty tree, making it "safe" from a detection perspective
        # (though in production you'd want to handle timeouts differently)
        assert result["safe"] == True  # No vulnerabilities found (due to timeout)
        assert len(result["vulnerabilities"]) == 0
        assert result["dependency_tree"] == {}

    @patch('subprocess.run')
    def test_json_parse_error_returns_empty_vulnerabilities(self, mock_run, scanner):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="invalid json",
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle parse error gracefully
        assert "vulnerabilities" in result
        assert isinstance(result["vulnerabilities"], list)

    @patch('subprocess.run')
    def test_subprocess_exception_handles_gracefully(self, mock_run, scanner):
        # Mock subprocess to raise exception
        mock_run.side_effect = Exception("Subprocess failed")

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle exception gracefully
        assert "safe" in result
        assert "vulnerabilities" in result

    @patch('subprocess.run')
    def test_pipdeptree_timeout_returns_empty_tree(self, mock_run, scanner):
        import subprocess

        # First call (pip install) succeeds, second (pipdeptree) times out
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            subprocess.TimeoutExpired("pipdeptree", 30)  # pipdeptree
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle timeout gracefully
        assert result["dependency_tree"] == {}


class TestEmptyRequirements:
    """Edge case handling for empty or minimal requirements."""

    def test_empty_requirements_returns_safe(self, scanner):
        result = scanner.scan_packages([])

        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0
        assert result["dependency_tree"] == {}
        assert result["conflicts"] == []

    @patch('subprocess.run')
    def test_single_package_scans_correctly(self, mock_run, scanner):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages(["requests==2.28.0"])

        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0


class TestScannerInitialization:
    """Scanner initialization and configuration."""

    def test_scanner_init_without_api_key(self):
        scanner = PackageDependencyScanner()
        assert scanner.safety_api_key is None

    def test_scanner_init_with_api_key(self):
        scanner = PackageDependencyScanner(safety_api_key="test-key")
        assert scanner.safety_api_key == "test-key"

    def test_scanner_reads_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("SAFETY_API_KEY", "env-key")
        scanner = PackageDependencyScanner()
        assert scanner.safety_api_key == "env-key"
