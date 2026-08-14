# -*- coding: utf-8 -*-
"""Coverage wave 99 — integrations/whatsapp_service_manager.py (was 20%).

- load_configuration: demo config, valid real config, incomplete (is_valid
  False), exception fallback to demo configuration.
- initialize_service: config status error, status incomplete, init success
  (incl. _register_with_service_registry), init failure, exception.
- health_check: config not "configured", healthy / degraded / unhealthy score
  bands, exception path, consecutive-failure accounting.
- get_service_metrics: integration missing get_analytics, full metrics path
  (incl. all four performance sub-calls), exception.
- _test_api_connectivity: no token, 200, non-200, exception.
- _test_database_connectivity: no db_connection, healthy cursor, exception.
- _calculate_health_score: api/db failures, consecutive-failure penalty,
  clamp-to-zero.
- _get_active_conversation_count: with/without get_conversations, exception.
- _register_with_service_registry: writes registration JSON, exception path.
- module helpers: initialize_whatsapp_service, get_whatsapp_service_status,
  get_whatsapp_service_metrics.

Fully mocked (requests, configuration module, integration), zero network,
zero DB, zero LLM spend.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from integrations.whatsapp_service_manager import (
    WhatsAppServiceManager,
    get_whatsapp_service_metrics,
    get_whatsapp_service_status,
    initialize_whatsapp_service,
)


@pytest.fixture()
def manager():
    m = WhatsAppServiceManager()
    m.integration = MagicMock()
    return m


def _demo_config():
    return {
        "access_token": "demo_token_x",
        "phone_number_id": "123456789012345",
        "status": "demo_configured",
        "features": {"auto_reply_enabled": False, "business_hours_enabled": True,
                     "message_retention_days": 30},
    }


# ============================================================================
# load_configuration
# ============================================================================

class TestLoadConfiguration:
    def test_demo_configuration(self, manager):
        with patch("integrations.whatsapp_configuration_setup.get_or_create_configuration",
                   return_value=_demo_config()) as g, \
             patch("integrations.whatsapp_configuration_setup.validate_configuration",
                   return_value={"is_demo": True, "is_valid": False,
                                 "missing_required": [], "errors": [],
                                 "warnings": ["demo"], "configuration_type": "demo"}):
            config = manager.load_configuration()
        assert config["service_manager"] is True
        assert config["validation"]["is_demo"] is True
        assert "loaded_at" in config
        assert manager.config is config
        g.assert_called_once()

    def test_valid_real_configuration(self, manager):
        cfg = dict(_demo_config(), status="configured", is_demo=False)
        with patch("integrations.whatsapp_configuration_setup.get_or_create_configuration",
                   return_value=cfg), \
             patch("integrations.whatsapp_configuration_setup.validate_configuration",
                   return_value={"is_demo": False, "is_valid": True,
                                 "missing_required": [], "errors": [],
                                 "warnings": [], "configuration_type": "real"}):
            config = manager.load_configuration()
        assert config["validation"]["is_valid"] is True
        assert config["validation"]["is_demo"] is False

    def test_incomplete_configuration(self, manager):
        cfg = dict(_demo_config(), status="configured", is_demo=False)
        with patch("integrations.whatsapp_configuration_setup.get_or_create_configuration",
                   return_value=cfg), \
             patch("integrations.whatsapp_configuration_setup.validate_configuration",
                   return_value={"is_demo": False, "is_valid": False,
                                 "missing_required": ["access_token"],
                                 "errors": ["missing"], "warnings": [],
                                 "configuration_type": "real"}):
            config = manager.load_configuration()
        assert config["validation"]["is_valid"] is False
        assert config["validation"]["missing_required"] == ["access_token"]

    def test_exception_falls_back_to_demo(self, manager):
        with patch("integrations.whatsapp_configuration_setup.get_or_create_configuration",
                   side_effect=RuntimeError("boom")), \
             patch("integrations.whatsapp_configuration_setup.setup_demo_configuration",
                   return_value=_demo_config()) as demo:
            config = manager.load_configuration()
        assert config["validation"]["is_demo"] is True
        assert config["validation"]["configuration_type"] == "demo_fallback"
        demo.assert_called_once()


# ============================================================================
# initialize_service
# ============================================================================

class TestInitializeService:
    def test_config_status_error(self, manager):
        with patch.object(manager, "load_configuration",
                          return_value={"status": "error", "error": "bad config"}):
            result = manager.initialize_service()
        assert result == {"success": False, "error": "bad config",
                          "status": "configuration_error"}

    def test_config_status_incomplete(self, manager):
        with patch.object(manager, "load_configuration",
                          return_value={"status": "incomplete"}):
            result = manager.initialize_service()
        assert result["success"] is False
        assert result["status"] == "incomplete_configuration"
        assert result["missing_fields"] == ["access_token", "phone_number_id"]

    def test_init_success(self, manager):
        manager.config = {"status": "configured", "features": {"auto_reply_enabled": True}}
        manager.integration.initialize.return_value = True
        with patch.object(manager, "load_configuration", return_value=manager.config), \
             patch.object(manager, "_register_with_service_registry") as register:
            result = manager.initialize_service()
        assert result["success"] is True
        assert result["status"] == "initialized"
        assert result["features_enabled"] == {"auto_reply_enabled": True}
        assert manager.status == "connected"
        assert manager.health_metrics["consecutive_failures"] == 0
        register.assert_called_once()

    def test_init_failure(self, manager):
        manager.config = {"status": "configured", "features": {}}
        manager.integration.initialize.return_value = False
        with patch.object(manager, "load_configuration", return_value=manager.config):
            result = manager.initialize_service()
        assert result == {"success": False, "error": "Failed to initialize WhatsApp integration",
                          "status": "initialization_failed"}
        assert manager.status == "failed"

    def test_exception(self, manager):
        manager.config = {"status": "configured", "features": {}}
        manager.integration.initialize.side_effect = RuntimeError("boom")
        with patch.object(manager, "load_configuration", return_value=manager.config):
            result = manager.initialize_service()
        assert result["success"] is False
        assert result["status"] == "initialization_error"
        assert manager.status == "error"


# ============================================================================
# health_check
# ============================================================================

class TestHealthCheck:
    def test_config_not_configured(self, manager):
        manager.config = {"status": "demo_configured"}
        result = manager.health_check()
        assert result["status"] == "unhealthy"
        assert "Configuration incomplete" in result["error"]

    def test_healthy(self, manager):
        manager.config = {"status": "configured"}
        with patch.object(manager, "_test_api_connectivity",
                          return_value={"status": "healthy"}), \
             patch.object(manager, "_test_database_connectivity",
                          return_value={"status": "healthy"}):
            result = manager.health_check()
        assert result["status"] == "healthy"
        assert result["health_score"] == 1.0
        assert manager.status == "healthy"

    def test_degraded(self, manager):
        # Score = 1.0 - 0.1*consecutive_failures = 0.8 -> degraded band [0.7, 0.9)
        manager.config = {"status": "configured"}
        manager.health_metrics["consecutive_failures"] = 2
        with patch.object(manager, "_test_api_connectivity",
                          return_value={"status": "healthy"}), \
             patch.object(manager, "_test_database_connectivity",
                          return_value={"status": "healthy"}):
            result = manager.health_check()
        assert result["status"] == "degraded"
        assert result["health_score"] == pytest.approx(0.8)
        assert result["consecutive_failures"] == 2

    def test_unhealthy_with_penalty(self, manager):
        manager.config = {"status": "configured"}
        manager.health_metrics["consecutive_failures"] = 5
        with patch.object(manager, "_test_api_connectivity",
                          return_value={"status": "failed"}), \
             patch.object(manager, "_test_database_connectivity",
                          return_value={"status": "failed"}):
            result = manager.health_check()
        assert result["status"] == "unhealthy"
        assert result["health_score"] == pytest.approx(0.0)
        assert result["consecutive_failures"] == 6
        assert manager.status == "unhealthy"

    def test_exception(self, manager):
        manager.config = {"status": "configured"}
        with patch.object(manager, "_test_api_connectivity",
                          side_effect=RuntimeError("boom")):
            result = manager.health_check()
        assert result["status"] == "unhealthy"
        assert result["consecutive_failures"] == 1


# ============================================================================
# get_service_metrics
# ============================================================================

class TestGetServiceMetrics:
    def test_integration_unavailable(self, manager):
        manager.integration = None
        result = manager.get_service_metrics()
        assert result["status"] == "unavailable"

    def test_integration_missing_analytics(self, manager):
        manager.integration = MagicMock()
        del manager.integration.get_analytics
        result = manager.get_service_metrics()
        assert result["status"] == "unavailable"

    def test_full_metrics(self, manager):
        manager.config = {"features": {"auto_reply_enabled": True,
                                       "business_hours_enabled": False,
                                       "message_retention_days": 7}}
        manager.integration.get_analytics.return_value = {"messages_sent": 10}
        manager.integration.get_conversations.return_value = [{"id": 1}, {"id": 2}]
        with patch.object(manager, "_calculate_average_response_time",
                          return_value=1.5), \
             patch.object(manager, "_get_peak_usage_hours",
                          return_value=["09:00"]), \
             patch.object(manager, "_get_top_templates",
                          return_value=["welcome"]):
            result = manager.get_service_metrics()
        assert result["status"] == "disconnected"
        assert result["analytics"] == {"messages_sent": 10}
        assert result["configuration"]["auto_reply_enabled"] is True
        assert result["configuration"]["business_hours_enabled"] is False
        assert result["configuration"]["message_retention_days"] == 7
        assert result["performance"]["average_response_time"] == 1.5
        assert result["performance"]["active_conversations"] == 2
        manager.integration.get_analytics.assert_called_once()

    def test_exception(self, manager):
        manager.integration.get_analytics.side_effect = RuntimeError("boom")
        result = manager.get_service_metrics()
        assert result["status"] == "error"
        assert "boom" in result["error"]


# ============================================================================
# Connectivity internals
# ============================================================================

class TestApiConnectivity:
    def test_no_token(self, manager):
        manager.integration.access_token = None
        result = manager._test_api_connectivity()
        assert result["status"] == "failed"
        assert "No access token" in result["error"]

    def test_success(self, manager):
        manager.integration.access_token = "tok"
        manager.integration.base_url = "https://graph.facebook.com/v18.0"
        fake_response = MagicMock(status_code=200)
        fake_response.elapsed.total_seconds.return_value = 0.42
        with patch("requests.get", return_value=fake_response) as get:
            result = manager._test_api_connectivity()
        assert result == {"status": "healthy", "response_time": 0.42, "api_version": "v18.0"}
        get.assert_called_once()
        assert get.call_args.args[0] == "https://graph.facebook.com/v18.0/me"

    def test_non_200(self, manager):
        manager.integration.access_token = "tok"
        manager.integration.base_url = "https://graph.facebook.com/v18.0"
        fake_response = MagicMock(status_code=400)
        fake_response.text = "bad request body"
        with patch("requests.get", return_value=fake_response):
            result = manager._test_api_connectivity()
        assert result["status"] == "failed"
        assert result["response_text"] == "bad request body"

    def test_exception(self, manager):
        manager.integration.access_token = "tok"
        manager.integration.base_url = "https://graph.facebook.com/v18.0"
        with patch("requests.get", side_effect=RuntimeError("net down")):
            result = manager._test_api_connectivity()
        assert result["status"] == "failed"
        assert "net down" in result["error"]


class TestDatabaseConnectivity:
    def test_no_connection(self, manager):
        manager.integration.db_connection = None
        result = manager._test_database_connectivity()
        assert result["status"] == "failed"
        assert "not available" in result["error"]

    def test_healthy(self, manager):
        cursor = MagicMock()
        manager.integration.db_connection = MagicMock()
        manager.integration.db_connection.cursor.return_value.__enter__.return_value = cursor
        result = manager._test_database_connectivity()
        assert result == {"status": "healthy", "database": "PostgreSQL"}
        cursor.execute.assert_called_once_with("SELECT 1")
        cursor.fetchone.assert_called_once()

    def test_exception(self, manager):
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("db down")
        manager.integration.db_connection = conn
        result = manager._test_database_connectivity()
        assert result["status"] == "failed"
        assert "db down" in result["error"]


class TestHealthScore:
    def test_all_healthy(self, manager):
        assert manager._calculate_health_score({"status": "healthy"}, {"status": "healthy"}) == 1.0

    def test_api_failure(self, manager):
        assert manager._calculate_health_score({"status": "failed"}, {"status": "healthy"}) == pytest.approx(0.5)

    def test_db_failure(self, manager):
        assert manager._calculate_health_score({"status": "healthy"}, {"status": "failed"}) == pytest.approx(0.6)

    def test_consecutive_failures_capped(self, manager):
        manager.health_metrics["consecutive_failures"] = 10
        score = manager._calculate_health_score({"status": "healthy"}, {"status": "healthy"})
        assert score == pytest.approx(0.7)

    def test_clamped_at_zero(self, manager):
        manager.health_metrics["consecutive_failures"] = 5
        score = manager._calculate_health_score({"status": "failed"}, {"status": "failed"})
        assert score == 0.0


class TestMiscInternals:
    def test_average_response_time(self, manager):
        assert manager._calculate_average_response_time() == 2.5

    def test_peak_usage_hours(self, manager):
        assert manager._get_peak_usage_hours() == ["09:00-11:00", "14:00-16:00"]

    def test_top_templates(self, manager):
        assert manager._get_top_templates() == ["appointment_reminder", "welcome_message", "follow_up"]

    def test_active_conversation_count_success(self, manager):
        manager.integration.get_conversations.return_value = [1, 2, 3]
        assert manager._get_active_conversation_count() == 3
        manager.integration.get_conversations.assert_called_once_with(limit=100)

    def test_active_conversation_count_missing_method(self, manager):
        del manager.integration.get_conversations
        assert manager._get_active_conversation_count() == 0

    def test_active_conversation_count_exception(self, manager):
        manager.integration.get_conversations.side_effect = RuntimeError("boom")
        assert manager._get_active_conversation_count() == 0


class TestRegisterWithRegistry:
    def test_success_writes_json(self, manager, tmp_path):
        with patch("builtins.open", MagicMock()) as open_mock:
            manager._register_with_service_registry()
        assert open_mock.call_args.args[0].startswith("/tmp/whatsapp_business_registration.json")
        handle = open_mock.return_value.__enter__.return_value
        payload = "".join(call.args[0] for call in handle.write.call_args_list)
        assert "WhatsApp Business" in payload
        assert "send_messages" in payload

    def test_exception(self, manager):
        with patch("builtins.open", side_effect=OSError("no /tmp")):
            manager._register_with_service_registry()  # must not raise


# ============================================================================
# Module-level helpers
# ============================================================================

class TestModuleHelpers:
    def test_initialize_whatsapp_service(self):
        with patch("integrations.whatsapp_service_manager.whatsapp_service_manager",
                   autospec=True) as svc:
            svc.initialize_service.return_value = {"success": True}
            assert initialize_whatsapp_service() == {"success": True}
            svc.initialize_service.assert_called_once()

    def test_get_whatsapp_service_status(self):
        with patch("integrations.whatsapp_service_manager.whatsapp_service_manager",
                   autospec=True) as svc:
            svc.health_check.return_value = {"status": "healthy"}
            assert get_whatsapp_service_status() == {"status": "healthy"}
            svc.health_check.assert_called_once()

    def test_get_whatsapp_service_metrics(self):
        with patch("integrations.whatsapp_service_manager.whatsapp_service_manager",
                   autospec=True) as svc:
            svc.get_service_metrics.return_value = {"status": "ok"}
            assert get_whatsapp_service_metrics() == {"status": "ok"}
            svc.get_service_metrics.assert_called_once()
