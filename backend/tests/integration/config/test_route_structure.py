"""
Integration tests for API route registration in main_api_app.py

These tests verify that routes are properly structured in the main app file.
They test the "wiring" pattern without importing the full app (which has
pre-existing SQLAlchemy issues).
"""

import os
import sys
import re
from pathlib import Path

import pytest


class TestRouteStructure:
    """Test route structure in main_api_app.py."""

    @pytest.fixture
    def main_app_content(self):
        """Read main_api_app.py content."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        main_app_path = backend_dir / "main_api_app.py"

        if not main_app_path.exists():
            pytest.skip(f"main_api_app.py not found at {main_app_path}")

        with open(main_app_path, 'r') as f:
            return f.read()

    def test_health_routes_defined(self, main_app_content):
        """Test that health check routes are defined."""
        # Check for health route patterns
        assert '"/health"' in main_app_content or '"/health/live"' in main_app_content
        assert "@app.get" in main_app_content or "app.get(" in main_app_content

    def test_agent_routes_imported(self, main_app_content):
        """Test that agent-related routes are imported."""
        # Check for agent route imports
        patterns = [
            r"agent.*route",
            r"agent_governance",
            r"api\.agent"
        ]
        content_lower = main_app_content.lower()

        matches = sum(1 for pattern in patterns if re.search(pattern, content_lower))
        assert matches > 0, "No agent route imports found"

    def test_canvas_routes_imported(self, main_app_content):
        """Test that canvas routes are imported."""
        patterns = [
            r"canvas.*route",
            r"api\.canvas"
        ]
        content_lower = main_app_content.lower()

        matches = sum(1 for pattern in patterns if re.search(pattern, content_lower))
        assert matches > 0, "No canvas route imports found"

    def test_browser_routes_imported(self, main_app_content):
        """Test that browser automation routes are imported."""
        assert "browser" in main_app_content.lower()
        assert "route" in main_app_content.lower()

    def test_device_routes_imported(self, main_app_content):
        """Test that device capability routes are imported."""
        assert "device" in main_app_content.lower()
        assert "route" in main_app_content.lower()

    def test_feedback_routes_imported(self, main_app_content):
        """Test that feedback routes are imported."""
        assert "feedback" in main_app_content.lower()
        assert "route" in main_app_content.lower()

    def test_deeplink_routes_imported(self, main_app_content):
        """Test that deeplink routes are imported."""
        assert "deeplink" in main_app_content.lower() or "deep_link" in main_app_content.lower()

    def test_workflow_routes_imported(self, main_app_content):
        """Test that workflow routes are imported."""
        assert "workflow" in main_app_content.lower()
        assert "route" in main_app_content.lower()

    def test_auth_routes_imported(self, main_app_content):
        """Test that authentication routes are imported."""
        patterns = [
            r"auth.*route",
            r"oauth",
        ]
        content_lower = main_app_content.lower()

        matches = sum(1 for pattern in patterns if re.search(pattern, content_lower))
        assert matches > 0, "No auth route imports found"

    def test_app_instantiation(self, main_app_content):
        """Test that FastAPI app is instantiated."""
        assert "FastAPI" in main_app_content
        assert "app = FastAPI" in main_app_content or "app=FastAPI" in main_app_content

    def test_middleware_configured(self, main_app_content):
        """Test that middleware is configured."""
        # Check for CORS middleware
        assert "CORSMiddleware" in main_app_content or "cors" in main_app_content.lower()

    def test_minimum_route_count(self, main_app_content):
        """Test that main_api_app.py includes multiple route registrations."""
        # Count app.include_router calls
        include_count = main_app_content.count("app.include_router")
        assert include_count >= 25, f"Expected at least 25 route registrations, found {include_count}"

    def test_core_routes_section(self, main_app_content):
        """Test that core routes section exists."""
        # Check for comments marking core routes
        assert "CORE ROUTES" in main_app_content or "Core API Routes" in main_app_content

    def test_health_check_endpoints(self, main_app_content):
        """Test that health check endpoints are defined."""
        # Look for health endpoint definitions
        health_patterns = [
            r'@app\.get\(["\']/?health["\']',
            r'@app\.get\(["\']/?["\']',
            r'def health',
            r'def root\(',
        ]
        content_lower = main_app_content.lower()

        matches = sum(1 for pattern in health_patterns if re.search(pattern, content_lower))
        assert matches >= 1, "No health check endpoints found"

    def test_route_prefixes_used(self, main_app_content):
        """Test that route prefixes are used correctly."""
        # Check for API version prefixes
        assert '"/api/' in main_app_content or 'prefix=' in main_app_content


class TestAppStructure:
    """Test overall app structure."""

    @pytest.fixture
    def main_app_path(self):
        """Get path to main_api_app.py."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        return backend_dir / "main_api_app.py"

    def test_main_app_exists(self, main_app_path):
        """Test that main_api_app.py exists."""
        assert main_app_path.exists(), f"main_api_app.py not found at {main_app_path}"

    def test_main_app_size(self, main_app_path):
        """Test that main_api_app.py has reasonable size (not empty)."""
        size = main_app_path.stat().st_size
        assert size > 1000, f"main_api_app.py is too small ({size} bytes)"

    def test_main_app_imports_fastapi(self, main_app_path):
        """Test that main_api_app.py imports FastAPI."""
        with open(main_app_path, 'r') as f:
            content = f.read()

        assert "from fastapi import" in content or "import fastapi" in content

    def test_main_app_has_lifespan(self, main_app_path):
        """Test that main_api_app.py has lifespan function."""
        with open(main_app_path, 'r') as f:
            content = f.read()

        assert "lifespan" in content.lower() or "startup" in content.lower()


class TestCriticalRoutePatterns:
    """Test critical route patterns for 25+ routes."""

    @pytest.fixture
    def route_patterns(self):
        """Define expected route patterns."""
        return {
            "health": ["health", "root"],
            "agents": ["agent"],
            "canvases": ["canvas"],
            "browser": ["browser"],
            "device": ["device"],
            "feedback": ["feedback"],
            "deeplinks": ["deeplink", "deep_link"],
            "workflows": ["workflow"],
            "auth": ["auth", "oauth"],
            "memory": ["memory"],
            "integrations": ["integration"],
        }

    def test_critical_route_categories_present(self, route_patterns):
        """Test that all critical route categories are present."""
        backend_dir = Path(__file__).parent.parent.parent.parent
        main_app_path = backend_dir / "main_api_app.py"

        with open(main_app_path, 'r') as f:
            content = f.read().lower()

        missing_categories = []
        for category, keywords in route_patterns.items():
            if not any(keyword in content for keyword in keywords):
                missing_categories.append(category)

        if missing_categories:
            pytest.fail(f"Missing route categories: {', '.join(missing_categories)}")
