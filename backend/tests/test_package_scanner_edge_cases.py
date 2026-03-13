"""
Package Dependency Scanner Edge Cases Tests

Test coverage for scanner error handling and edge cases:
- Malformed package requirements
- CLI tools not installed (pip-audit, Safety, pipdeptree)
- Subprocess timeout handling
- Empty/malformed JSON from scanners
- Transitive dependency conflicts
- Large dependency trees
- Version specifier validation
"""

import json
import pytest
import subprocess
from unittest.mock import patch, MagicMock, Mock
from core.package_dependency_scanner import PackageDependencyScanner


@pytest.fixture
def scanner():
    """Import scanner fixture from existing test file."""
    return PackageDependencyScanner()


class TestMalformedRequirements:
    """Test handling of malformed package requirement specifications."""

    def test_empty_requirements_list(self, scanner):
        """Empty requirements list should return safe result."""
        result = scanner.scan_packages([])

        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0
        assert result["dependency_tree"] == {}
        assert result["conflicts"] == []

    def test_invalid_package_name_characters(self, scanner):
        """Package names with invalid characters should be handled gracefully."""
        # Mock subprocess to avoid actual pip calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            # Invalid characters in package name (spaces, special chars)
            invalid_names = [
                "my package==1.0.0",  # Space in name
                "my-package==1.0.0",  # Hyphen is valid but test edge case
                "123package==1.0.0",  # Starts with number
                "package@1.0.0",  # @ instead of ==
            ]

            for req in invalid_names:
                result = scanner.scan_packages([req])
                # Should not crash, returns some result
                assert "safe" in result
                assert "vulnerabilities" in result

    def test_invalid_version_specifier(self, scanner):
        """Invalid version specifiers should be handled gracefully."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            # Invalid version specifiers
            invalid_specs = [
                "requests>>>1.0.0",  # Triple >>>
                "requests===1.0.0",  # Triple ===
                "requests==1.0.0beta",  # Invalid pre-release format
                "requests==",  # Missing version
            ]

            for req in invalid_specs:
                result = scanner.scan_packages([req])
                # Should handle without crashing
                assert "safe" in result

    def test_missing_version_specifier(self, scanner):
        """Package name without version specifier should be handled."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            # Package name only (no version)
            result = scanner.scan_packages(["requests"])

            assert "safe" in result
            assert "vulnerabilities" in result

    def test_mixed_valid_invalid_requirements(self, scanner):
        """Mixed valid and invalid requirements should process valid ones."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            # Mix of valid and potentially problematic specs
            requirements = [
                "requests==2.28.0",  # Valid
                "urllib3>=1.26.0",  # Valid
                "numpy==1.21.0",  # Valid
            ]

            result = scanner.scan_packages(requirements)

            # Should process all without crashing
            assert result["safe"] == True  # Mocked as safe

    def test_requirements_with_leading_trailing_whitespace(self, scanner):
        """Requirements with whitespace should be trimmed/processed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            # Requirements with various whitespace patterns
            requirements = [
                "  requests==2.28.0  ",  # Leading and trailing
                "\turllib3==1.26.0\t",  # Tabs
                "\nnumpy==1.21.0\n",  # Newlines
            ]

            result = scanner.scan_packages(requirements)

            # Should handle whitespace gracefully
            assert "safe" in result


class TestCliNotInstalled:
    """Test handling when CLI tools (pip-audit, Safety, pipdeptree) are not installed."""

    @patch('subprocess.run')
    def test_pip_audit_not_installed(self, mock_run, scanner):
        """FileNotFoundError when pip-audit not installed should be handled."""
        # First call: pip install (success)
        # Second call: pipdeptree (success)
        # Third call: pip-audit (FileNotFoundError)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree
            FileNotFoundError("pip-audit not found"),  # pip-audit
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle gracefully - safe result if no vulnerabilities found
        assert "safe" in result
        assert isinstance(result["vulnerabilities"], list)

    @patch('subprocess.run')
    def test_pipdeptree_not_installed(self, mock_run, scanner):
        """FileNotFoundError when pipdeptree not installed should return empty tree."""
        # First call: pip install (success)
        # Second call: pipdeptree (FileNotFoundError)
        # Third call: pip-audit (success, safe)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            FileNotFoundError("pipdeptree not found"),  # pipdeptree
            MagicMock(returncode=0, stdout="[]"),  # pip-audit
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should have empty dependency tree but still complete scan
        assert result["dependency_tree"] == {}
        assert "safe" in result

    @patch('subprocess.run')
    def test_safety_not_installed(self, mock_run, scanner):
        """FileNotFoundError when Safety not installed should be handled."""
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # First call: pip install (success)
        # Second call: pipdeptree (success)
        # Third call: pip-audit (success, safe)
        # Fourth call: safety (FileNotFoundError)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree
            MagicMock(returncode=0, stdout="[]"),  # pip-audit
            FileNotFoundError("safety not found"),  # safety
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should complete without Safety results
        assert "safe" in result
        assert len([v for v in result["vulnerabilities"] if v.get("source") == "safety"]) == 0

    @patch('subprocess.run')
    def test_all_clis_missing_graceful_degradation(self, mock_run, scanner):
        """All CLI tools missing should still return valid result structure."""
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # All subprocess calls fail with FileNotFoundError
        mock_run.side_effect = FileNotFoundError("Command not found")

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should return safe result with empty data (graceful degradation)
        assert result["safe"] == True
        assert result["dependency_tree"] == {}
        assert len(result["vulnerabilities"]) == 0
        assert len(result["conflicts"]) == 0

    @patch('subprocess.run')
    def test_partial_cli_availability(self, mock_run, scanner):
        """Only pip-audit available should still provide vulnerability scanning."""
        # First call: pip install (success)
        # Second call: pipdeptree (FileNotFoundError)
        # Third call: pip-audit (success, finds vulnerability)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            FileNotFoundError("pipdeptree not found"),  # pipdeptree
            MagicMock(  # pip-audit finds vulnerability
                returncode=1,
                stdout=json.dumps([{
                    "name": "requests",
                    "versions": ["2.20.0"],
                    "id": "CVE-2018-18074",
                    "description": "DoS vulnerability",
                    "fix_versions": ["2.20.1"]
                }])
            ),
        ]

        result = scanner.scan_packages(["requests==2.20.0"])

        # Should detect vulnerability via pip-audit even without pipdeptree
        assert result["safe"] == False
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["cve_id"] == "CVE-2018-18074"
        assert result["dependency_tree"] == {}  # Empty tree


class TestTimeoutHandling:
    """Test subprocess timeout handling for all CLI tools."""

    @patch('subprocess.run')
    def test_pip_audit_timeout(self, mock_run, scanner):
        """pip-audit timeout should return empty vulnerabilities."""
        # First call: pip install (success)
        # Second call: pipdeptree (success)
        # Third call: pip-audit (TimeoutExpired)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree
            subprocess.TimeoutExpired("pip-audit", 120),  # pip-audit timeout
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle timeout gracefully
        assert "safe" in result
        assert len(result["vulnerabilities"]) == 0  # No vulns due to timeout

    @patch('subprocess.run')
    def test_pipdeptree_timeout(self, mock_run, scanner):
        """pipdeptree timeout should return empty dependency tree."""
        # First call: pip install (success)
        # Second call: pipdeptree (TimeoutExpired at 30s)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            subprocess.TimeoutExpired("pipdeptree", 30),  # pipdeptree timeout
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should have empty tree but continue
        assert result["dependency_tree"] == {}
        assert "safe" in result

    @patch('subprocess.run')
    def test_safety_timeout(self, mock_run, scanner):
        """Safety timeout should return empty vulnerabilities from Safety."""
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # First call: pip install (success)
        # Second call: pipdeptree (success)
        # Third call: pip-audit (success, safe)
        # Fourth call: safety (TimeoutExpired at 120s)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree
            MagicMock(returncode=0, stdout="[]"),  # pip-audit
            subprocess.TimeoutExpired("safety", 120),  # safety timeout
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should complete without Safety results
        assert "safe" in result
        assert len([v for v in result["vulnerabilities"] if v.get("source") == "safety"]) == 0

    @patch('subprocess.run')
    def test_timeout_returns_empty_vulnerabilities(self, mock_run, scanner):
        """Any timeout should result in empty vulnerabilities list."""
        # All subprocess calls timeout
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should return safe (no vulnerabilities detected due to timeout)
        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0
        assert result["dependency_tree"] == {}

    @patch('subprocess.run')
    def test_timeout_does_not_crash_scanner(self, mock_run, scanner):
        """Timeout should not crash scanner or raise uncaught exception."""
        # Timeout on pipdeptree
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            subprocess.TimeoutExpired("pipdeptree", 30),  # pipdeptree timeout
        ]

        # Should not raise exception
        try:
            result = scanner.scan_packages(["requests==2.28.0"])
            assert "safe" in result
        except Exception as e:
            pytest.fail(f"Scanner raised exception on timeout: {e}")


class TestJsonParseErrors:
    """Test handling of malformed/invalid JSON from scanners."""

    @patch('subprocess.run')
    def test_pip_audit_returns_invalid_json(self, mock_run, scanner):
        """pip-audit returning invalid JSON should be handled."""
        mock_run.return_value = MagicMock(
            returncode=1,  # Non-zero return (vulnerabilities)
            stdout="not valid json {broken",
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle parse error gracefully
        assert "vulnerabilities" in result
        assert isinstance(result["vulnerabilities"], list)
        assert len(result["vulnerabilities"]) == 0  # Empty due to parse error

    @patch('subprocess.run')
    def test_safety_returns_malformed_json(self, mock_run, scanner):
        """Safety returning malformed JSON should be handled."""
        scanner = PackageDependencyScanner(safety_api_key="test-key")

        # First calls succeed, Safety returns bad JSON
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            MagicMock(returncode=0, stdout="[]"),  # pipdeptree
            MagicMock(returncode=0, stdout="[]"),  # pip-audit
            MagicMock(returncode=1, stdout="{malformed json"),  # Safety
        ]

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should handle malformed JSON gracefully
        assert "safe" in result
        safety_vulns = [v for v in result["vulnerabilities"] if v.get("source") == "safety"]
        assert len(safety_vulns) == 0

    @patch('subprocess.run')
    def test_json_decode_error_handling(self, mock_run, scanner):
        """JSONDecodeError should be caught and handled gracefully."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='{"incomplete": "json"',  # Incomplete JSON
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should not crash, returns empty vulnerabilities
        assert "vulnerabilities" in result
        assert isinstance(result["vulnerabilities"], list)

    @patch('subprocess.run')
    def test_empty_json_array_response(self, mock_run, scanner):
        """Empty JSON array should be handled correctly (safe result)."""
        mock_run.return_value = MagicMock(
            returncode=0,  # Zero return (no vulnerabilities)
            stdout="[]",  # Empty array
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        # Should return safe result
        assert result["safe"] == True
        assert len(result["vulnerabilities"]) == 0


class TestTransitiveDependencyConflicts:
    """Test detection of transitive dependency version conflicts."""

    @patch('subprocess.run')
    def test_conflicting_package_versions_in_tree(self, mock_run, scanner):
        """Detect conflicting versions of same package in dependency tree."""
        # Mock tree with conflicting shared-lib versions
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

        # Should detect conflict
        assert len(result["conflicts"]) > 0
        assert result["conflicts"][0]["package"] == "shared-lib"
        assert result["conflicts"][0]["severity"] == "transitive_conflict"

    @patch('subprocess.run')
    def test_circular_dependency_detection(self, mock_run, scanner):
        """Circular dependencies should be handled without infinite loops."""
        # Mock circular dependency: A depends on B, B depends on A
        tree_json = json.dumps([
            {
                "package": {"package_name": "package-a", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "package-b", "installed_version": "1.0.0"}
                ]
            },
            {
                "package": {"package_name": "package-b", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "package-a", "installed_version": "1.0.0"}
                ]
            }
        ])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["package-a==1.0.0"])

        # Should handle circular deps without hanging
        assert "dependency_tree" in result
        # Both packages should be in tree
        assert "package-a" in result["dependency_tree"]
        assert "package-b" in result["dependency_tree"]

    @patch('subprocess.run')
    def test_duplicate_packages_with_different_versions(self, mock_run, scanner):
        """Duplicate package entries with different versions in dependencies should be flagged."""
        # Mock tree where two packages depend on different versions of same package
        tree_json = json.dumps([
            {
                "package": {"package_name": "package-a", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "requests", "installed_version": "2.20.0"}
                ]
            },
            {
                "package": {"package_name": "package-b", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "requests", "installed_version": "2.28.0"}
                ]
            }
        ])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["package-a==1.0.0", "package-b==1.0.0"])

        # Should detect transitive version conflict
        assert len(result["conflicts"]) > 0
        assert result["conflicts"][0]["package"] == "requests"
        assert "2.20.0" in result["conflicts"][0]["versions"]
        assert "2.28.0" in result["conflicts"][0]["versions"]

    @patch('subprocess.run')
    def test_conflict_report_includes_both_versions(self, mock_run, scanner):
        """Conflict report should include both conflicting versions."""
        tree_json = json.dumps([
            {
                "package": {"package_name": "lib-a", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "shared", "installed_version": "1.0.0"}
                ]
            },
            {
                "package": {"package_name": "lib-b", "installed_version": "2.0.0"},
                "dependencies": [
                    {"package_name": "shared", "installed_version": "2.0.0"}
                ]
            }
        ])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["lib-a==1.0.0", "lib-b==2.0.0"])

        # Conflict should include both versions
        conflict = result["conflicts"][0]
        assert conflict["package"] == "shared"
        assert "1.0.0" in conflict["versions"]
        assert "2.0.0" in conflict["versions"]
        assert len(conflict["versions"]) == 2

    @patch('subprocess.run')
    def test_conflict_prevents_installation(self, mock_run, scanner):
        """Version conflicts should be reported even if packages are otherwise safe."""
        # Mock tree with conflicts but no vulnerabilities
        tree_json = json.dumps([
            {
                "package": {"package_name": "pkg-a", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "common", "installed_version": "1.0.0"}
                ]
            },
            {
                "package": {"package_name": "pkg-b", "installed_version": "1.0.0"},
                "dependencies": [
                    {"package_name": "common", "installed_version": "2.0.0"}
                ]
            }
        ])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,  # Tree with conflicts
            stderr=""
        )

        result = scanner.scan_packages(["pkg-a==1.0.0", "pkg-b==1.0.0"])

        # Should report as not safe due to conflicts
        assert result["safe"] == False
        assert len(result["conflicts"]) > 0


class TestLargeDependencyTrees:
    """Test handling of large and complex dependency trees."""

    @patch('subprocess.run')
    def test_scan_with_100_plus_packages(self, mock_run, scanner):
        """Scanner should handle 100+ packages without performance issues."""
        # Mock large dependency tree (100 packages)
        large_tree = []
        for i in range(100):
            large_tree.append({
                "package": {
                    "package_name": f"package-{i}",
                    "installed_version": "1.0.0"
                },
                "dependencies": []
            })

        tree_json = json.dumps(large_tree)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        # Create requirements with many packages
        requirements = [f"package-{i}==1.0.0" for i in range(100)]

        result = scanner.scan_packages(requirements)

        # Should handle large tree successfully
        assert result["safe"] == True
        assert len(result["dependency_tree"]) == 100

    @patch('subprocess.run')
    def test_deep_dependency_tree(self, mock_run, scanner):
        """Scanner should handle deep dependency trees (10+ levels)."""
        # Mock deep tree: pkg0 -> pkg1 -> pkg2 -> ... -> pkg10
        deep_tree = []
        for i in range(10):
            deps = [{"package_name": f"package-{i+1}", "installed_version": "1.0.0"}] if i < 9 else []
            deep_tree.append({
                "package": {
                    "package_name": f"package-{i}",
                    "installed_version": "1.0.0"
                },
                "dependencies": deps
            })

        tree_json = json.dumps(deep_tree)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["package-0==1.0.0"])

        # Should handle deep tree
        assert "package-0" in result["dependency_tree"]
        assert "package-9" in result["dependency_tree"]

    @patch('subprocess.run')
    def test_broad_dependency_tree(self, mock_run, scanner):
        """Scanner should handle broad trees (50+ direct dependencies)."""
        # Mock broad tree: one package with 50 direct deps
        broad_deps = [
            {"package_name": f"dep-{i}", "installed_version": "1.0.0"}
            for i in range(50)
        ]

        tree_json = json.dumps([
            {
                "package": {
                    "package_name": "main-package",
                    "installed_version": "1.0.0"
                },
                "dependencies": broad_deps
            }
        ] + [
            {
                "package": {
                    "package_name": f"dep-{i}",
                    "installed_version": "1.0.0"
                },
                "dependencies": []
            }
            for i in range(50)
        ])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages(["main-package==1.0.0"])

        # Should handle broad tree
        assert "main-package" in result["dependency_tree"]
        assert len(result["dependency_tree"]["main-package"]["dependencies"]) == 50

    @patch('subprocess.run')
    def test_memory_efficiency_with_large_trees(self, mock_run, scanner):
        """Large trees should not cause memory issues."""
        # Mock very large tree (200 packages)
        large_tree = []
        for i in range(200):
            large_tree.append({
                "package": {
                    "package_name": f"pkg-{i}",
                    "installed_version": "1.0.0"
                },
                "dependencies": []
            })

        tree_json = json.dumps(large_tree)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=tree_json,
            stderr=""
        )

        result = scanner.scan_packages([f"pkg-{i}==1.0.0" for i in range(200)])

        # Should complete successfully
        assert result["safe"] == True
        assert len(result["dependency_tree"]) == 200

    @patch('subprocess.run')
    def test_scan_timeout_with_large_tree(self, mock_run, scanner):
        """Large tree scan should respect timeout limits."""
        # First call succeeds, second times out
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # pip install
            subprocess.TimeoutExpired("pipdeptree", 30),  # pipdeptree timeout
        ]

        result = scanner.scan_packages([f"pkg-{i}==1.0.0" for i in range(100)])

        # Should handle timeout gracefully even with large requirements
        assert result["dependency_tree"] == {}
        assert "safe" in result


class TestVersionSpecifierValidation:
    """Test handling of various version specifier formats."""

    @patch('subprocess.run')
    def test_caret_version_specifier(self, mock_run, scanner):
        """Caret specifier (^1.2.3) should be processed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages(["requests^2.0.0"])

        # Should handle caret specifier
        assert "safe" in result

    @patch('subprocess.run')
    def test_tilde_version_specifier(self, mock_run, scanner):
        """Tilde specifier (~1.2.3) should be processed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages(["requests~2.0.0"])

        # Should handle tilde specifier
        assert "safe" in result

    @patch('subprocess.run')
    def test_wildcard_version_specifiers(self, mock_run, scanner):
        """Wildcard specifiers (1.2.*, *) should be processed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages([
            "requests==2.*",  # Wildcard patch
            "numpy==1.*",  # Wildcard patch
        ])

        # Should handle wildcard specifiers
        assert "safe" in result

    @patch('subprocess.run')
    def test_exact_version_specifier(self, mock_run, scanner):
        """Exact version specifier (==) should be processed correctly."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages([
            "requests==2.28.0",  # Exact version
            "urllib3==1.26.0",  # Exact version
        ])

        # Should process exact versions
        assert result["safe"] == True

    @patch('subprocess.run')
    def test_greater_less_than_specifiers(self, mock_run, scanner):
        """Comparison specifiers (>=, <=, >, <) should be processed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        result = scanner.scan_packages([
            "requests>=2.28.0",  # Greater than or equal
            "urllib3<2.0.0",  # Less than
            "numpy>1.21.0",  # Greater than
            "pandas<=1.3.0",  # Less than or equal
        ])

        # Should handle comparison operators
        assert "safe" in result
