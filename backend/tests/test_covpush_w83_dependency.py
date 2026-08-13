# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/dependency_resolver.py to >=95% (pure resolver
logic; no network, no installs).

Covers:
- resolve_python_dependencies: success, invalid requirement spec, version
  conflicts (multiple specifiers), parse failures per package.
- resolve_npm_dependencies: success (dedupe), version conflicts, scoped
  packages, unversioned packages, exception path.
- _parse_npm_package: scoped @pkg/name@version, scoped unversioned, plain
  name@version, plain name.
- check_package_compatibility: python + npm routes.
"""
import logging
from unittest.mock import patch

import pytest

from core.dependency_resolver import DependencyResolver

resolver = DependencyResolver()


# ============================================================================
# resolve_python_dependencies
# ============================================================================

def test_resolve_python_success():
    result = resolver.resolve_python_dependencies(["numpy==1.21.0", "pandas>=1.3.0"])
    assert result["success"] is True
    assert set(result["dependencies"]) == {"numpy==1.21.0", "pandas>=1.3.0"}
    assert result["total_count"] == 2
    assert result["conflicts"] == []


def test_resolve_python_invalid_requirement():
    result = resolver.resolve_python_dependencies(["numpy!!1.0", "valid"])
    assert result["success"] is False
    assert "Invalid requirement" in result["error"]
    assert "details" in result


def test_resolve_python_duplicate_versions_conflict():
    result = resolver.resolve_python_dependencies(["requests==2.0", "requests>=3.0"])
    assert result["success"] is False
    assert result["error"] == "Dependency conflicts detected"
    conflict = result["conflicts"][0]
    assert conflict["package"] == "requests"
    assert set(conflict["conflicting_versions"]) == {"==2.0", ">=3.0"}


def test_resolve_python_duplicate_identical_specifier_no_conflict():
    result = resolver.resolve_python_dependencies(["requests==2.0", "requests==2.0"])
    assert result["success"] is True
    assert result["total_count"] == 2  # unified list keeps both entries


def test_resolve_python_unversioned_packages():
    result = resolver.resolve_python_dependencies(["flask", "requests==2.0"])
    assert result["success"] is True
    assert set(result["dependencies"]) == {"flask", "requests==2.0"}


def test_resolve_python_empty_list():
    result = resolver.resolve_python_dependencies([])
    assert result["success"] is True
    assert result["dependencies"] == []
    assert result["total_count"] == 0


def test_resolve_python_outer_exception_path():
    with patch.object(resolver, "_detect_conflicts", side_effect=RuntimeError("kaboom")):
        result = resolver.resolve_python_dependencies(["numpy"])
    assert result["success"] is False
    assert result["error"] == "kaboom"


# ============================================================================
# resolve_npm_dependencies
# ============================================================================

def test_resolve_npm_success_dedupes():
    result = resolver.resolve_npm_dependencies(["lodash@4.17.21", "lodash@4.17.21", "express@^4.18.0"])
    assert result["success"] is True
    assert set(result["dependencies"]) == {"lodash@4.17.21", "express@^4.18.0"}
    assert result["total_count"] == 2


def test_resolve_npm_version_conflict():
    result = resolver.resolve_npm_dependencies(["lodash@4.17.21", "lodash@5.0.0"])
    assert result["success"] is False
    assert result["error"] == "npm version conflicts detected"
    conflict = result["conflicts"][0]
    assert conflict["package"] == "lodash"
    assert conflict["requested_versions"] == ["4.17.21", "5.0.0"]


def test_resolve_npm_scoped_same_version_no_conflict():
    result = resolver.resolve_npm_dependencies(["@scope/pkg@1.0.0", "@scope/pkg@1.0.0"])
    assert result["success"] is True


def test_resolve_npm_exception_path():
    with patch.object(resolver, "_parse_npm_package", side_effect=RuntimeError("boom")):
        result = resolver.resolve_npm_dependencies(["lodash@1.0.0"])
    assert result["success"] is False
    assert result["error"] == "boom"


# ============================================================================
# _parse_npm_package
# ============================================================================

def test_parse_npm_scoped_with_version():
    assert resolver._parse_npm_package("@scope/pkg@1.2.3") == ("@scope/pkg", "1.2.3")


def test_parse_npm_scoped_without_version():
    assert resolver._parse_npm_package("@scope/pkg") == ("@scope/pkg", "latest")


def test_parse_npm_plain_with_version():
    assert resolver._parse_npm_package("lodash@4.17.21") == ("lodash", "4.17.21")


def test_parse_npm_plain_without_version():
    assert resolver._parse_npm_package("express") == ("express", "latest")


def test_parse_npm_scoped_split_exact():
    # name containing @ but no version -> unversioned scoped
    assert resolver._parse_npm_package("@a/b") == ("@a/b", "latest")


# ============================================================================
# check_package_compatibility
# ============================================================================

def test_check_package_compatibility_python():
    result = resolver.check_package_compatibility(["numpy==1.21.0"], ["numpy>=2.0"])
    assert result["success"] is False
    assert result["error"] == "Dependency conflicts detected"


def test_check_package_compatibility_python_ok():
    result = resolver.check_package_compatibility(["numpy==1.21.0"], ["pandas>=1.3.0"])
    assert result["success"] is True


def test_check_package_compatibility_npm():
    result = resolver.check_package_compatibility(["lodash@4.0.0"], ["lodash@5.0.0"], package_type="npm")
    assert result["success"] is False
    assert result["error"] == "npm version conflicts detected"


def test_check_package_compatibility_npm_ok():
    result = resolver.check_package_compatibility(["lodash@4.0.0"], ["express@4.0.0"], package_type="npm")
    assert result["success"] is True
