"""
Tests for Local-Only Mode Guard

Tests LocalOnlyGuard enforcement for blocking cloud services.
Covers environment variable checks, service blocking, and allowed services.
"""

import pytest
from unittest.mock import patch
import os

from core.privsec.local_only_guard import (
    LocalOnlyGuard,
    LocalOnlyModeError,
    get_local_only_guard,
    require_local_allowed,
)


# ============================================================================
# LocalOnlyMode Tests
# ============================================================================

class TestLocalOnlyMode:
    """Test local-only mode functionality."""

    def test_is_local_only_enabled_returns_false_by_default(self, monkeypatch):
        """Test local-only mode is disabled by default."""
        # Ensure env var is not set
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)

        guard = get_local_only_guard()
        result = guard.is_local_only_enabled()

        assert result is False

    def test_is_local_only_enabled_returns_true_when_env_set(self, monkeypatch):
        """Test local-only mode returns true when env var is set."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        guard = get_local_only_guard()
        result = guard.is_local_only_enabled()

        assert result is True

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")

    def test_allow_external_request_returns_true_when_disabled(self, monkeypatch):
        """Test external requests allowed when local-only mode disabled."""
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)

        guard = get_local_only_guard()
        result = guard.is_service_blocked("spotify")

        assert result is False

    def test_allow_external_request_raises_when_enabled(self, monkeypatch):
        """Test external requests raise error when local-only mode enabled."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        guard = get_local_only_guard()
        result = guard.is_service_blocked("spotify")

        assert result is True

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")


# ============================================================================
# Decorator Tests
# ============================================================================

class TestRequireLocalAllowedDecorator:
    """Test @require_local_allowed decorator."""

    def test_require_local_allowed_decorator_blocks_function(self, monkeypatch):
        """Test decorator blocks function when service not allowed."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("spotify")
        def call_spotify_api():
            return "Success"

        with pytest.raises(LocalOnlyModeError, match="spotify"):
            call_spotify_api()

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")

    def test_require_local_allowed_decorator_allows_local_service(self, monkeypatch):
        """Test decorator allows local services in local-only mode."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("sonos")
        def call_sonos_api():
            return "Success"

        # Sonos is a local service, should be allowed
        result = call_sonos_api()

        assert result == "Success"

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")


# ============================================================================
# Blocked Services Tests
# ============================================================================

class TestBlockedServices:
    """Test blocked services list."""

    def test_get_blocked_services_list(self):
        """Test getting list of blocked services."""
        guard = get_local_only_guard()
        blocked = guard.get_blocked_services()

        # Should include cloud services
        assert "spotify" in blocked
        assert "notion" in blocked

    def test_get_local_allowed_services_list(self):
        """Test getting list of local-allowed services."""
        guard = get_local_only_guard()
        allowed = guard.get_local_allowed_services()

        # Should include local network services
        assert "sonos" in allowed
        assert "hue" in allowed
        assert "home_assistant" in allowed
        assert "ffmpeg" in allowed


# ============================================================================
# Local Services Tests
# ============================================================================

class TestLocalServices:
    """Test local services work in local-only mode."""

    def test_local_services_not_blocked(self, monkeypatch):
        """Test local services are not blocked in local-only mode."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        guard = get_local_only_guard()

        # Test all local services
        local_services = ["sonos", "hue", "home_assistant", "ffmpeg"]

        for service in local_services:
            result = guard.is_service_blocked(service)
            assert result is False, f"{service} should be allowed in local-only mode"

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")

    def test_cloud_services_blocked_in_local_only_mode(self, monkeypatch):
        """Test cloud services are blocked in local-only mode."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        guard = get_local_only_guard()

        # Test cloud services
        cloud_services = ["spotify", "notion"]

        for service in cloud_services:
            result = guard.is_service_blocked(service)
            assert result is True, f"{service} should be blocked in local-only mode"

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")


# ============================================================================
# Integration Tests
# ============================================================================

class TestLocalOnlyGuardIntegration:
    """Integration tests for local-only guard."""

    def test_local_only_guard_with_real_tools(self, monkeypatch):
        """Test local-only guard works with real tool scenarios."""
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        guard = get_local_only_guard()

        # Simulate tool checking before external call
        tools_scenarios = [
            ("spotify", True),  # Cloud - blocked
            ("notion", True),   # Cloud - blocked
            ("sonos", False),   # Local - allowed
            ("hue", False),     # Local - allowed
            ("home_assistant", False),  # Local - allowed
            ("ffmpeg", False),    # Local - allowed
        ]

        for service, should_be_blocked in tools_scenarios:
            result = guard.is_service_blocked(service)
            assert result == should_be_blocked, f"{service} expected {should_be_blocked}"

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")

    def test_local_only_mode_respects_environment_priority(self, monkeypatch):
        """Test local-only mode respects ATOM_LOCAL_ONLY environment variable."""
        guard = get_local_only_guard()

        # Test default (disabled)
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
        assert guard.is_local_only_enabled() is False

        # Test enabled
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        assert guard.is_local_only_enabled() is True

        # Test explicitly disabled
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        assert guard.is_local_only_enabled() is False

        # Cleanup
        monkeypatch.delenv("ATOM_LOCAL_ONLY")

    def test_local_only_guard_case_insensitive(self, monkeypatch):
        """Test local-only mode is case-insensitive."""
        guard = get_local_only_guard()

        test_cases = ["true", "True", "TRUE", "1", "yes", "Yes"]

        for value in test_cases:
            monkeypatch.setenv("ATOM_LOCAL_ONLY", value)
            assert guard.is_local_only_enabled() is True, f"ATOM_LOCAL_ONLY={value} should enable local-only mode"
            monkeypatch.delenv("ATOM_LOCAL_ONLY")
