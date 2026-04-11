"""
Test conftest import behavior - RED phase tests.

These tests verify that pytest can import root conftest without errors,
even when e2e_ui fixtures are not available.
"""

import pytest
import sys
from pathlib import Path


class TestRootConftestImports:
    """Test suite for root conftest.py import behavior"""

    def test_root_conftest_exists(self):
        """Test 1: Root conftest.py file exists"""
        root_conftest = Path(__file__).parent / "conftest.py"
        assert root_conftest.exists(), "Root conftest.py must exist"

    def test_root_conftest_imports_without_error(self):
        """Test 2: Root conftest can be imported without ModuleNotFoundError"""
        # Clear any cached imports
        sys.modules.pop("conftest", None)

        # Try importing the root conftest
        try:
            import conftest
            assert True, "Root conftest imported successfully"
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(f"Root conftest import failed with: {e}")

    def test_pytest_plugins_list_exists(self):
        """Test 3: pytest_plugins variable exists in conftest"""
        import conftest
        assert hasattr(conftest, "pytest_plugins"), "conftest must have pytest_plugins variable"

    def test_pytest_plugins_is_list(self):
        """Test 4: pytest_plugins is a list (can be empty)"""
        import conftest
        assert isinstance(conftest.pytest_plugins, list), "pytest_plugins must be a list"

    def test_pytest_can_discover_tests_from_backend(self):
        """Test 5: pytest can discover tests from backend directory"""
        import subprocess

        # Try to collect tests from backend directory
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q", "tests/api/test_ab_testing_routes.py"],
            cwd=Path(__file__).parent.parent / "backend",
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not have ImportError
        assert "ImportError" not in result.stderr, f"ImportError found: {result.stderr}"
        assert "ModuleNotFoundError" not in result.stderr, f"ModuleNotFoundError found: {result.stderr}"

    def test_e2e_fixtures_load_conditionally(self):
        """Test 6: E2E fixtures load when available, skipped when not"""
        import conftest

        # Check if pytest_plugins is a list
        assert isinstance(conftest.pytest_plugins, list)

        # If e2e_ui fixtures are available, they should be in the list
        # If not available, the list should be empty or contain only available plugins
        for plugin in conftest.pytest_plugins:
            try:
                __import__(plugin)
            except ImportError:
                pytest.fail(f"Plugin {plugin} in pytest_plugins but cannot be imported")
