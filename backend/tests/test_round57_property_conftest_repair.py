"""
Round 57 — Test-infra: stale `from main_api_app import app` breaks suite collection
(Red-Green-Refactor).

tests/property_tests/conftest.py:13 does `from main_api_app import app` — there is no
main.py (the real app is main_api_app.py). Every conftest/test that imports
db_session from it (tests/security/, tests/scenarios/,
tests/integration/websocket/, tests/integration/test_websocket_integration)
fails collection with ModuleNotFoundError, so whole suites never run —
flagged as pre-existing breakage since R44.

Fix: import the real app (main_api_app.app) in property_tests/conftest.py.
"""

import importlib


class TestPropertyConftestImports:
    def test_property_conftest_imports_cleanly(self):
        """The root breakage: property_tests/conftest must import without
        ModuleNotFoundError ('from main_api_app import app')."""
        mod = importlib.import_module("tests.property_tests.conftest")
        assert hasattr(mod, "client"), "conftest must still expose the client fixture"

    def test_security_conftest_imports_cleanly(self):
        """tests/security/conftest imports db_session from property_tests —
        the chain must resolve end to end."""
        mod = importlib.import_module("tests.security.conftest")
        assert mod.db_session is not None

    def test_property_tests_collect(self):
        """The property test modules must collect (they were unrunnable)."""
        import pytest

        collected = pytest.main(
            [
                "tests/property_tests/",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ]
        )
        assert collected == 0, "property_tests/ collection still fails"
