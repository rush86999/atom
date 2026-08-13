"""Coverage wave 69c — fleet overage_service / privsec local_only_guard /
mock_mode / skill_builder_service -> >=95% each.

Standalone file (final probe runs only this file), so every branch of the 4
target modules is exercised here:

- ``core.fleet_orchestration.overage_service``: approve_overage (ValueError on
  overage > max, tenant-found vs missing plan defaults, duration default =
  max//2, duration capped at plan max, active-overage cancellation, notification
  send + failure tolerance, result dict), get_effective_limit (active overage /
  missing chain default 2 / chain base limit), get_active_overage (found/missing),
  check_overage_expiry (nothing expired / expiry with + without admin owner /
  notification failure tolerance), get_expiring_overages, _send_*_notification
  success + exception branches, get_overage_service.
- ``core.privsec.local_only_guard``: LocalOnlyModeError message assembly
  (reason/alternatives present + absent, 403 status), singleton __new__,
  __init__ env cache + cached skip, reset_cache, is_local_only_enabled,
  allow_external_request (disabled / blocked + alternatives + reason / local /
  unknown fail-open), sorted service lists, is_service_blocked /
  is_service_local_allowed (case-insensitive), _get_local_alternatives (all map
  keys + unknown), require_local_allowed sync + async wrappers (blocked and
  allowed), get_local_only_guard singleton.
- ``core.mock_mode``: __init__ env on/off, is_mock_mode (disabled / no-creds /
  creds), get_mock_data with all 7 generators + unknown-generator fallback,
  module global + get_mock_mode_manager.
- ``core.skill_builder_service``: yaml available + ImportError fallback reload,
  SkillMetadata defaults, __init__ default/custom root, _get_tenant_skills_dir
  (mkdir parents), create_skill_package (safe-name sanitize, invalid name,
  already-exists, success + scripts + unsafe-filename skip, write failure
  exception path, YAML fallback frontmatter), module global.

No LLM spend, no network, no real DB — the DB session is a MagicMock and
NotificationService is patched.
"""
import asyncio
import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import mock_mode as mm
from core import skill_builder_service as sbs
from core.privsec import local_only_guard as guard_mod
from core.fleet_orchestration.overage_service import OverageService, get_overage_service
from core.mock_mode import MockModeManager, get_mock_mode_manager
from core.privsec.local_only_guard import (
    LocalOnlyGuard,
    LocalOnlyModeError,
    get_local_only_guard,
    require_local_allowed,
)
from core.skill_builder_service import SkillBuilderService, SkillMetadata


def _overage(**kw):
    data = {
        "id": "ov-1",
        "tenant_id": "tenant-1",
        "chain_id": "chain-1",
        "base_limit": 5,
        "temporary_limit": 9,
        "current_size": 0,
        "is_active": True,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "approved_by": "u1",
    }
    data.update(kw)
    return SimpleNamespace(**data)


# =============================================================================
# core.fleet_orchestration.overage_service
# =============================================================================

class TestOverageService:
    @pytest.fixture
    def svc(self):
        """OverageService over a MagicMock db + patched NotificationService."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("core.fleet_orchestration.overage_service.NotificationService") as ns_cls:
            service = OverageService(db)
            service.notification_service.send_notification = AsyncMock()
            yield service, db

    @pytest.mark.asyncio
    async def test_approve_overage_exceeds_max_raises(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        with pytest.raises(ValueError, match="exceeds maximum allowed overage"):
            await service.approve_overage("chain-1", "tenant-1", proposed_size=999, user_id="u1")

    @pytest.mark.asyncio
    async def test_approve_overage_no_tenant_free_plan(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1", duration_hours=12)
        assert result["success"] is True
        assert result["approved_size"] == 15
        assert result["base_limit"] == 10
        assert result["duration_hours"] == 12
        assert result["expires_at"].endswith("+00:00") or "T" in result["expires_at"]
        assert result["overage_id"]
        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.query.return_value.filter.return_value.update.assert_called_once_with(
            {"is_active": False})
        service.notification_service.send_notification.assert_awaited_once()
        kwargs = service.notification_service.send_notification.await_args.kwargs
        assert kwargs["user_id"] == "u1"
        assert kwargs["workspace_id"] == "tenant-1"
        assert kwargs["title"] == "Fleet Expansion Approved"
        assert kwargs["channels"] == ["in_app", "email"]

    @pytest.mark.asyncio
    async def test_approve_overage_default_duration_free_half_max(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1")
        assert result["duration_hours"] == 12  # free max 24 // 2

    @pytest.mark.asyncio
    async def test_approve_overage_with_tenant_enterprise_plan(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="tenant-1", plan_type="enterprise")
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=19, user_id="u1")
        assert result["success"] is True
        # enterprise: multiplier 2.0, max_duration 168 -> default 84
        assert result["duration_hours"] == 84
        assert result["approved_size"] == 19

    @pytest.mark.asyncio
    async def test_approve_overage_uses_tenant_plan_type(self, svc, monkeypatch):
        """Regression: plan limits must come from the tenant's actual plan,
        not 'enterprise' just because the tenant exists."""
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="tenant-1", plan_type="free")
        # free multiplier 1.5 -> max 15; 16 must be rejected (was allowed under
        # the old "enterprise" hardcode: 2.0 -> max 20)
        with pytest.raises(ValueError, match="exceeds maximum allowed overage"):
            await service.approve_overage("chain-1", "tenant-1", proposed_size=16, user_id="u1")

    @pytest.mark.asyncio
    async def test_approve_overage_team_plan_duration_cap(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="tenant-1", plan_type="team")
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1", duration_hours=1000)
        assert result["duration_hours"] == 72  # team max
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_approve_overage_unknown_plan_uses_defaults(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="tenant-1", plan_type="mystery-plan")
        # unknown plan -> multiplier 1.5 (max 15), duration 48
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1")
        assert result["success"] is True
        assert result["duration_hours"] == 24  # 48 // 2 default
        with pytest.raises(ValueError, match="exceeds maximum allowed overage"):
            await service.approve_overage("chain-1", "tenant-1", proposed_size=16, user_id="u1")

    @pytest.mark.asyncio
    async def test_approve_overage_duration_capped_at_plan_max(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1", duration_hours=1000)
        assert result["duration_hours"] == 24  # free max

    @pytest.mark.asyncio
    async def test_approve_overage_notification_failure_tolerated(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        service.notification_service.send_notification = AsyncMock(
            side_effect=RuntimeError("smtp down"))
        result = await service.approve_overage(
            "chain-1", "tenant-1", proposed_size=15, user_id="u1")
        assert result["success"] is True

    def test_get_effective_limit_active_overage_wins(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        active = _overage(base_limit=5, temporary_limit=9)
        db.query.return_value.filter.return_value.first.return_value = active
        assert service.get_effective_limit("chain-1") == 9

    def test_get_effective_limit_no_chain_returns_default_2(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_effective_limit("missing-chain") == 2

    def test_get_effective_limit_chain_found_base_limit(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.setenv("MAX_FLEET_SIZE", "10")
        db.query.return_value.filter.return_value.first.side_effect = [None, SimpleNamespace(id="chain-1")]
        assert service.get_effective_limit("chain-1") == 10

    def test_get_effective_limit_env_default_100(self, svc, monkeypatch):
        service, db = svc
        monkeypatch.delenv("MAX_FLEET_SIZE", raising=False)
        db.query.return_value.filter.return_value.first.side_effect = [None, SimpleNamespace(id="chain-1")]
        assert service.get_effective_limit("chain-1") == 100

    def test_get_active_overage_found_and_missing(self, svc):
        service, db = svc
        db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_active_overage("chain-1") is None
        active = _overage()
        db.query.return_value.filter.return_value.first.return_value = active
        assert service.get_active_overage("chain-1") is active

    @pytest.mark.asyncio
    async def test_check_overage_expiry_nothing_expired(self, svc):
        service, db = svc
        db.query.return_value.filter.return_value.all.return_value = []
        assert await service.check_overage_expiry("chain-1") is False
        service.notification_service.send_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_overage_expiry_with_admin_owner(self, svc):
        service, db = svc
        expired = [
            _overage(id="ov-1", tenant_id="t1", base_limit=5, temporary_limit=9),
            _overage(id="ov-2", tenant_id="t1", base_limit=5, temporary_limit=9),
        ]
        db.query.return_value.filter.return_value.all.return_value = expired
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="admin-1", role="admin")
        assert await service.check_overage_expiry("chain-1") is True
        assert expired[0].is_active is False
        assert expired[1].is_active is False
        db.flush.assert_called_once()
        service.notification_service.send_notification.assert_awaited_once()
        kwargs = service.notification_service.send_notification.await_args.kwargs
        assert kwargs["user_id"] == "admin-1"
        assert kwargs["title"] == "Fleet Expansion Expired"
        assert kwargs["notification_type"] == "warning"

    @pytest.mark.asyncio
    async def test_check_overage_expiry_no_admin_owner_skips_send(self, svc):
        service, db = svc
        db.query.return_value.filter.return_value.all.return_value = [_overage(tenant_id="t1")]
        db.query.return_value.filter.return_value.first.return_value = None
        assert await service.check_overage_expiry("chain-1") is True
        service.notification_service.send_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_overage_expiry_notification_failure_tolerated(self, svc):
        service, db = svc
        db.query.return_value.filter.return_value.all.return_value = [_overage(tenant_id="t1")]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="admin-1", role="admin")
        service.notification_service.send_notification = AsyncMock(
            side_effect=RuntimeError("down"))
        assert await service.check_overage_expiry("chain-1") is True

    def test_get_expiring_overages(self, svc):
        service, db = svc
        db.query.return_value.filter.return_value.all.return_value = [_overage()]
        result = service.get_expiring_overages(hours_threshold=2)
        assert result == [_overage()] or len(result) == 1

    def test_get_expiring_overages_default_threshold(self, svc):
        service, db = svc
        assert service.get_expiring_overages() == []
        call = db.query.return_value.filter.call_args
        assert len(call.args) == 3  # is_active, expires_at <= threshold, expires_at > now

    def test_get_overage_service_convenience(self):
        db = MagicMock()
        with patch("core.fleet_orchestration.overage_service.NotificationService"):
            svc = get_overage_service(db)
        assert isinstance(svc, OverageService)
        assert svc.db is db


# =============================================================================
# core.privsec.local_only_guard
# =============================================================================

@pytest.fixture(autouse=True)
def _reset_guard_state():
    guard_mod._local_only_guard_instance = None
    LocalOnlyGuard.reset_cache()
    yield
    guard_mod._local_only_guard_instance = None
    LocalOnlyGuard.reset_cache()


class TestLocalOnlyModeError:
    def test_error_minimal_message_and_403(self):
        err = LocalOnlyModeError("spotify")
        assert err.service == "spotify"
        assert err.reason is None
        assert err.suggested_alternatives == []
        assert err.status_code == 403
        assert "Service 'spotify' is blocked in local-only mode" in str(err.detail)
        assert "Disable local-only mode" in str(err.detail)

    def test_error_with_reason(self):
        err = LocalOnlyModeError("notion", reason="OAuth requires cloud")
        assert "OAuth requires cloud" in str(err.detail)
        assert err.reason == "OAuth requires cloud"

    def test_error_with_alternatives(self):
        err = LocalOnlyModeError("spotify", suggested_alternatives=["sonos", "airplay"])
        assert err.suggested_alternatives == ["sonos", "airplay"]
        detail = str(err.detail)
        assert "Local alternatives: sonos, airplay" in detail
        assert ".\n\nDisable local-only mode" in detail

    def test_error_is_http_exception(self):
        from fastapi import HTTPException
        assert isinstance(LocalOnlyModeError("spotify"), HTTPException)


class TestLocalOnlyGuardSingleton:
    def test_singleton_same_instance(self):
        assert LocalOnlyGuard() is LocalOnlyGuard()

    def test_init_enabled_from_env_true(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        assert LocalOnlyGuard().is_local_only_enabled() is True

    def test_init_enabled_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "TRUE")
        assert LocalOnlyGuard().is_local_only_enabled() is True

    def test_init_disabled_when_env_false(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        assert LocalOnlyGuard().is_local_only_enabled() is False

    def test_init_default_disabled_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
        assert LocalOnlyGuard().is_local_only_enabled() is False

    def test_init_cached_value_not_reread(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        guard = LocalOnlyGuard()
        assert guard.is_local_only_enabled() is True
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        assert guard.is_local_only_enabled() is True  # cached

    def test_reset_cache_forces_env_reread(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        assert LocalOnlyGuard().is_local_only_enabled() is True
        LocalOnlyGuard.reset_cache()
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        assert LocalOnlyGuard().is_local_only_enabled() is False


class TestAllowExternalRequest:
    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        yield

    def test_disabled_mode_allows_everything(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")
        assert LocalOnlyGuard().allow_external_request("spotify") is True

    def test_blocked_service_raises_with_alternatives(self):
        guard = LocalOnlyGuard()
        with pytest.raises(LocalOnlyModeError) as exc_info:
            guard.allow_external_request("spotify")
        assert exc_info.value.suggested_alternatives == ["sonos", "airplay"]

    def test_blocked_service_with_reason(self):
        guard = LocalOnlyGuard()
        with pytest.raises(LocalOnlyModeError) as exc_info:
            guard.allow_external_request("notion", reason="no local fallback")
        assert "no local fallback" in str(exc_info.value.detail)
        assert exc_info.value.suggested_alternatives == ["local markdown files"]

    def test_local_service_allowed(self):
        assert LocalOnlyGuard().allow_external_request("sonos") is True

    def test_unknown_service_allowed_fail_open(self):
        assert LocalOnlyGuard().allow_external_request("mystery_service") is True


class TestServiceLists:
    def test_get_blocked_services_sorted(self):
        blocked = LocalOnlyGuard().get_blocked_services()
        assert "spotify" in blocked
        assert "openai" in blocked
        assert blocked == sorted(blocked)

    def test_get_local_allowed_services_sorted(self):
        allowed = LocalOnlyGuard().get_local_allowed_services()
        assert "sonos" in allowed
        assert "ffmpeg" in allowed
        assert allowed == sorted(allowed)

    def test_is_service_blocked_case_insensitive(self):
        guard = LocalOnlyGuard()
        assert guard.is_service_blocked("Spotify") is True
        assert guard.is_service_blocked("gmail") is True
        assert guard.is_service_blocked("sonos") is False
        assert guard.is_service_blocked("mystery") is False

    def test_is_service_local_allowed(self):
        guard = LocalOnlyGuard()
        assert guard.is_service_local_allowed("HUE") is True
        assert guard.is_service_local_allowed("home_assistant") is True
        assert guard.is_service_local_allowed("spotify") is False
        assert guard.is_service_local_allowed("mystery") is False


class TestLocalAlternatives:
    CASES = {
        "spotify": ["sonos", "airplay"],
        "apple_music": ["sonos", "airplay"],
        "youtube_music": ["sonos"],
        "notion": ["local markdown files"],
        "trello": ["local kanban boards"],
        "asana": ["local task management"],
        "slack": ["local messaging"],
        "gmail": ["local email client"],
        "google_calendar": ["local calendar"],
        "openai": ["local LLM (Ollama)"],
        "anthropic": ["local LLM (Ollama)"],
        "deepseek": ["local LLM (Ollama)"],
        "tavily": ["local search"],
        "brave_search": ["local search"],
    }

    def test_all_known_services_map(self):
        guard = LocalOnlyGuard()
        for service, expected in self.CASES.items():
            assert guard._get_local_alternatives(service) == expected, service

    def test_unknown_service_returns_empty(self):
        assert LocalOnlyGuard()._get_local_alternatives("mystery") == []

    def test_case_insensitive_lookup(self):
        assert LocalOnlyGuard()._get_local_alternatives("Spotify") == ["sonos", "airplay"]


class TestRequireLocalAllowedDecorator:
    def test_sync_blocked_raises(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("spotify")
        def call_spotify():
            return "unreachable"

        with pytest.raises(LocalOnlyModeError, match="spotify"):
            call_spotify()

    def test_sync_local_service_runs(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("sonos")
        def call_sonos():
            return "Success"

        assert call_sonos() == "Success"

    def test_sync_wrapper_preserves_name(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("sonos")
        def my_target():
            return 1

        assert my_target.__name__ == "my_target"

    @pytest.mark.asyncio
    async def test_async_blocked_raises(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("openai")
        async def call_openai():
            return "unreachable"

        with pytest.raises(LocalOnlyModeError, match="openai"):
            await call_openai()

    @pytest.mark.asyncio
    async def test_async_local_service_runs(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")

        @require_local_allowed("hue")
        async def call_hue():
            return "Success"

        assert await call_hue() == "Success"

    def test_decorator_disabled_mode_runs(self, monkeypatch):
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "false")

        @require_local_allowed("spotify")
        def call_spotify():
            return "allowed"

        assert call_spotify() == "allowed"


class TestGetLocalOnlyGuard:
    def test_returns_singleton_and_caches(self):
        first = get_local_only_guard()
        assert guard_mod._local_only_guard_instance is first
        assert get_local_only_guard() is first
        assert isinstance(first, LocalOnlyGuard)


# =============================================================================
# core.mock_mode
# =============================================================================

class TestMockModeManager:
    def test_init_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("MOCK_MODE_ENABLED", raising=False)
        assert MockModeManager().enabled is False

    def test_init_enabled_from_env(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        assert MockModeManager().enabled is True

    def test_init_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "TRUE")
        assert MockModeManager().enabled is True

    def test_is_mock_mode_off_when_disabled(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "false")
        manager = MockModeManager()
        assert manager.is_mock_mode("salesforce", has_credentials=False) is False

    def test_is_mock_mode_on_when_enabled_and_no_credentials(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        assert manager.is_mock_mode("salesforce", has_credentials=False) is True

    def test_is_mock_mode_off_with_credentials(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        assert manager.is_mock_mode("salesforce", has_credentials=True) is False

    def test_get_mock_data_salesforce_accounts(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("salesforce", "accounts", count=3)
        assert len(rows) == 3
        for row in rows:
            assert row["Id"].startswith("001")
            assert row["Name"].startswith("Mock Company")
            assert row["Industry"] in ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing"]

    def test_get_mock_data_salesforce_contacts(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("salesforce", "contacts", count=2)
        assert len(rows) == 2
        assert rows[0]["FirstName"] == "MockUser1"
        assert rows[0]["LastName"] == "Doe"
        assert rows[0]["AccountId"].startswith("001")

    def test_get_mock_data_salesforce_opportunities(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("salesforce", "opportunities", count=4)
        assert len(rows) == 4
        assert rows[0]["Id"].startswith("006")
        assert rows[0]["StageName"] in [
            "Prospecting", "Qualification", "Needs Analysis",
            "Value Proposition", "Closed Won", "Closed Lost"]
        assert isinstance(rows[0]["Amount"], int)

    def test_get_mock_data_hubspot_contacts(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("hubspot", "contacts", count=2)
        assert len(rows) == 2
        assert rows[0]["properties"]["firstname"] == "HubSpotUser1"
        assert rows[0]["archived"] is False

    def test_get_mock_data_hubspot_deals(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("hubspot", "deals", count=2)
        assert len(rows) == 2
        assert rows[0]["properties"]["dealname"] == "Mock Deal 1"
        assert rows[0]["properties"]["amount"].isdigit()

    def test_get_mock_data_zoom_meetings(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        rows = manager.get_mock_data("zoom", "meetings", count=2)
        assert len(rows) == 2
        assert rows[0]["topic"] == "Mock Zoom Meeting 1"
        assert rows[0]["type"] in [1, 2, 3, 8]
        assert rows[0]["join_url"].startswith("https://zoom.us/j/")

    def test_get_mock_data_count_zero(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        assert manager.get_mock_data("salesforce", "accounts", count=0) == []

    def test_get_mock_data_unknown_generator_falls_back(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODE_ENABLED", "true")
        manager = MockModeManager()
        assert manager.get_mock_data("salesforce", "widgets", count=3) == []
        assert manager.get_mock_data("unknown", "unknown", count=3) == []

    def test_get_mock_mode_manager_global(self):
        assert get_mock_mode_manager() is mm.mock_mode_manager
        assert isinstance(mm.mock_mode_manager, MockModeManager)


# =============================================================================
# core.skill_builder_service
# =============================================================================

class TestSkillBuilderService:
    def test_skill_metadata_defaults(self):
        meta = SkillMetadata(name="Test", description="Desc")
        assert meta.version == "1.0.0"
        assert meta.author == "User"
        assert meta.capabilities == []
        assert meta.instructions == ""

    def test_skill_metadata_custom(self):
        meta = SkillMetadata(
            name="Test", description="Desc", version="2.0.0", author="a",
            capabilities=["x"], instructions="instr")
        assert meta.version == "2.0.0"
        assert meta.capabilities == ["x"]

    def test_init_default_workspace_root(self):
        from pathlib import Path
        svc = SkillBuilderService()
        assert svc.workspace_root == Path("./data/workspaces").resolve()

    def test_init_custom_workspace_root(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        assert svc.workspace_root == tmp_path.resolve()

    def test_get_tenant_skills_dir_creates_parents(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        skills_dir = svc._get_tenant_skills_dir("tenant-1")
        assert skills_dir == (tmp_path.resolve() / "tenant-1" / "skills")
        assert skills_dir.is_dir()

    def test_yaml_available_flag(self):
        assert sbs.YAML_AVAILABLE is True

    def test_create_skill_package_success(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        meta = SkillMetadata(name="My Cool Skill!", description="A great skill",
                             instructions="Do the thing")
        result = svc.create_skill_package(
            "tenant-1", meta, {"script.py": 'print("hi")', "notes.txt": "notes"})
        assert result["success"] is True
        assert result["message"] == "Skill 'My Cool Skill!' created successfully"
        assert result["scripts"] == ["script.py", "notes.txt"]
        skill_dir = tmp_path.resolve() / "tenant-1" / "skills" / "mycoolskill"
        assert result["path"] == str(skill_dir)
        assert (skill_dir / "SKILL.md").is_file()
        content = (skill_dir / "SKILL.md").read_text()
        assert content.startswith("---\n")
        assert "name: My Cool Skill!" in content
        assert "# My Cool Skill!" in content
        assert "A great skill" in content
        assert "## Instructions" in content
        assert "Do the thing" in content
        assert "- `script.py`" in content
        assert (skill_dir / "script.py").read_text() == 'print("hi")'

    def test_create_skill_package_keeps_hyphens_and_underscores(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        result = svc.create_skill_package(
            "tenant-1", SkillMetadata(name="My_Skill-2", description="d"), {"a.py": "x"})
        assert result["success"] is True
        assert result["path"].endswith("my_skill-2")

    def test_create_skill_package_invalid_name(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        result = svc.create_skill_package(
            "tenant-1", SkillMetadata(name="!!!", description="d"), {"a.py": "x"})
        assert result["success"] is False
        assert result["message"] == "Invalid skill name"

    def test_create_skill_package_already_exists(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        meta = SkillMetadata(name="dup", description="d")
        assert svc.create_skill_package("tenant-1", meta, {"a.py": "x"})["success"] is True
        result = svc.create_skill_package("tenant-1", meta, {"a.py": "x"})
        assert result["success"] is False
        assert "already exists" in result["message"]

    def test_create_skill_package_skips_unsafe_filenames(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        result = svc.create_skill_package(
            "tenant-1", SkillMetadata(name="safe", description="d"),
            {"../evil.py": "bad", "a/b.py": "nested", "ok.py": "fine"})
        assert result["success"] is True
        assert result["scripts"] == ["ok.py"]
        skill_dir = tmp_path.resolve() / "tenant-1" / "skills" / "safe"
        assert not (skill_dir / ".." / "evil.py").exists()
        assert (skill_dir / "ok.py").read_text() == "fine"

    def test_create_skill_package_write_failure_returns_error(self, tmp_path):
        svc = SkillBuilderService(workspace_root=str(tmp_path))
        orig_write_text = sbs.Path.write_text

        def _fail_on_skillmd(self, *args, **kwargs):
            if self.name == "SKILL.md":
                raise OSError("disk full")
            return orig_write_text(self, *args, **kwargs)

        with patch.object(sbs.Path, "write_text", autospec=True,
                          side_effect=_fail_on_skillmd):
            result = svc.create_skill_package(
                "tenant-1", SkillMetadata(name="failskill", description="d"),
                {"a.py": "x"})
        assert result["success"] is False
        assert "disk full" in result["message"]

    def test_create_skill_package_yaml_fallback(self, tmp_path):
        real_yaml = sys.modules.get("yaml")
        try:
            sys.modules["yaml"] = None  # force ImportError on `import yaml`
            reloaded = importlib.reload(sbs)
            assert reloaded.YAML_AVAILABLE is False
            assert reloaded.yaml is None

            svc = reloaded.SkillBuilderService(workspace_root=str(tmp_path))
            result = svc.create_skill_package(
                "tenant-1", reloaded.SkillMetadata(name="fallback", description="d"),
                {"a.py": "x"})
            assert result["success"] is True
            skill_dir = tmp_path.resolve() / "tenant-1" / "skills" / "fallback"
            content = (skill_dir / "SKILL.md").read_text()
            assert content.startswith("# Skill Metadata (YAML fallback)\n")
            assert "- name: fallback" in content
            assert "- capabilities: []" in content
        finally:
            if real_yaml is not None:
                sys.modules["yaml"] = real_yaml
            else:
                sys.modules.pop("yaml", None)
            importlib.reload(sbs)
        assert sbs.YAML_AVAILABLE is True

    def test_module_global_service(self):
        assert isinstance(sbs.skill_builder_service, sbs.SkillBuilderService)
