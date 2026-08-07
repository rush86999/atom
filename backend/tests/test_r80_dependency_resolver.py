# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/dependency_resolver.py.

Unit tests for Python + npm dependency resolution, conflict detection,
scoped-package parsing and compatibility checks.
"""
import pytest

from core.dependency_resolver import DependencyResolver


@pytest.fixture()
def resolver():
    return DependencyResolver()


class TestPythonResolution:
    def test_simple_resolution_success(self, resolver):
        result = resolver.resolve_python_dependencies(["numpy==1.21.0", "pandas>=1.3.0"])
        assert result["success"] is True
        assert result["total_count"] == 2
        assert "numpy==1.21.0" in result["dependencies"]
        assert result["conflicts"] == []

    def test_versionless_package_ok(self, resolver):
        result = resolver.resolve_python_dependencies(["requests"])
        assert result["success"] is True
        assert result["dependencies"] == ["requests"]

    def test_conflict_between_versions(self, resolver):
        result = resolver.resolve_python_dependencies(["numpy==1.21.0", "numpy>=1.22.0"])
        assert result["success"] is False
        assert result["error"] == "Dependency conflicts detected"
        assert result["conflicts"][0]["package"] == "numpy"
        assert set(result["conflicts"][0]["conflicting_versions"]) == {"==1.21.0", ">=1.22.0"}

    def test_identical_specifier_is_not_a_conflict(self, resolver):
        result = resolver.resolve_python_dependencies(["numpy==1.21.0", "numpy==1.21.0"])
        assert result["success"] is True
        assert result["total_count"] == 2

    def test_multiple_packages_can_conflict(self, resolver):
        result = resolver.resolve_python_dependencies(
            ["django==4.0", "flask==2.0", "django>=5.0"]
        )
        assert result["success"] is False
        assert result["conflicts"][0]["package"] == "django"

    def test_invalid_requirement_returns_error(self, resolver):
        result = resolver.resolve_python_dependencies(["not a valid spec!!"])
        assert result["success"] is False
        assert "Invalid requirement" in result["error"]

    def test_empty_list_succeeds(self, resolver):
        result = resolver.resolve_python_dependencies([])
        assert result["success"] is True
        assert result["total_count"] == 0

    def test_extras_and_markers_are_preserved(self, resolver):
        result = resolver.resolve_python_dependencies(["requests[socks]==2.28.0"])
        assert result["success"] is True
        assert result["dependencies"][0].startswith("requests[socks]==2.28.0")


class TestNpmResolution:
    def test_simple_npm_success(self, resolver):
        result = resolver.resolve_npm_dependencies(["lodash@4.17.21", "express@^4.18.0"])
        assert result["success"] is True
        assert result["total_count"] == 2

    def test_npm_version_conflict(self, resolver):
        result = resolver.resolve_npm_dependencies(["lodash@4.17.21", "lodash@4.17.20"])
        assert result["success"] is False
        assert result["conflicts"][0]["package"] == "lodash"
        assert set(result["conflicts"][0]["requested_versions"]) == {"4.17.21", "4.17.20"}

    def test_npm_duplicate_package_deduplicated(self, resolver):
        result = resolver.resolve_npm_dependencies(["lodash@4.17.21", "lodash@4.17.21"])
        assert result["success"] is True
        assert result["total_count"] == 1

    def test_npm_empty(self, resolver):
        result = resolver.resolve_npm_dependencies([])
        assert result["success"] is True
        assert result["total_count"] == 0


class TestNpmParse:
    def test_plain_package_returns_latest(self, resolver):
        assert resolver._parse_npm_package("express") == ("express", "latest")

    def test_versioned_package(self, resolver):
        assert resolver._parse_npm_package("lodash@4.17.21") == ("lodash", "4.17.21")

    def test_scoped_package_with_version(self, resolver):
        name, version = resolver._parse_npm_package("@babel/core@7.20.0")
        assert name == "@babel/core"
        assert version == "7.20.0"

    def test_scoped_package_without_version(self, resolver):
        assert resolver._parse_npm_package("@babel/core") == ("@babel/core", "latest")

    def test_scoped_package_version_contains_hyphen(self, resolver):
        name, version = resolver._parse_npm_package("@types/node@^18.11.0")
        assert name == "@types/node"
        assert version == "^18.11.0"


class TestCompatibilityCheck:
    def test_compatible_python_packages(self, resolver):
        result = resolver.check_package_compatibility(
            ["numpy==1.21.0"], ["pandas>=1.3.0"], package_type="python"
        )
        assert result["success"] is True
        assert result["total_count"] == 2

    def test_conflicting_new_python_package(self, resolver):
        result = resolver.check_package_compatibility(
            ["numpy==1.21.0"], ["numpy>=2.0.0"], package_type="python"
        )
        assert result["success"] is False
        assert result["conflicts"]

    def test_compatible_npm_packages(self, resolver):
        result = resolver.check_package_compatibility(
            ["react@18.2.0"], ["react-dom@18.2.0"], package_type="npm"
        )
        assert result["success"] is True

    def test_conflicting_npm_package(self, resolver):
        result = resolver.check_package_compatibility(
            ["react@18.2.0"], ["react@17.0.0"], package_type="npm"
        )
        assert result["success"] is False

    def test_unknown_package_type_treated_as_npm(self, resolver):
        result = resolver.check_package_compatibility(
            ["a@1.0.0", "a@2.0.0"], [], package_type="yarn"
        )
        assert result["success"] is False


class TestFlatten:
    def test_flatten_returns_strings(self, resolver):
        from packaging.requirements import Requirement

        reqs = [Requirement("numpy==1.21.0"), Requirement("requests")]
        assert resolver._flatten_requirements(reqs) == ["numpy==1.21.0", "requests"]

    def test_detect_conflicts_empty(self, resolver):
        assert resolver._detect_conflicts({}) == []
        assert resolver._detect_conflicts({"numpy": {"==1.21.0"}}) == []

    def test_detect_conflicts_multi(self, resolver):
        conflicts = resolver._detect_conflicts({"numpy": {"==1.21.0", ">=1.22.0"}})
        assert len(conflicts) == 1
        assert conflicts[0]["package"] == "numpy"
