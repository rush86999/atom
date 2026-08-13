"""Coverage wave W66c — WhatsApp config/dev + Messenger + GitHub integration push.

Targets (>=95% statement coverage, standalone):
- integrations/whatsapp_environment_config.py     (was 0%, never imported by tests)
- integrations/whatsapp_start_development.py      (was 12%, import-only)
- integrations/whatsapp_configuration_setup.py    (was 0%, never imported by tests)
- integrations/messenger_service.py               (was 0%, never imported by tests)
- integrations/github_integration.py              (was 92% — 6 dead-code lines)

Pattern: pure unit tests, mocked deps, ZERO LLM spend, no network (requests/
httpx mocked), no DB. __main__ blocks exercised via runpy.run_path (run_name
='__main__') with builtins.open mocked.

Bugs found + fixed in the assigned modules (regression tests below):
1. whatsapp_start_development.py:6 — `start_sprint_development()` referenced
   `timedelta` (line 20) but only `datetime` was imported at module scope
   (timedelta import lived inside `__main__`) -> NameError on EVERY call
   (sprint plan generation completely broken, not just in __main__). Fixed by
   importing timedelta at module level —
   test_start_sprint_development_returns_plan.
2. github_integration.py — 6 lines of dead code from a multi-provider template:
   `if 'github' == 'github':` (always True, lines 24-27) and
   `if 'github' == 'teams':` / `if 'github' in ['teams', 'outlook']:` (always
   False, lines 79/92/105) could never be exercised and would silently
   misbehave if the hardcoded provider literal ever changed. Removed the
   unreachable branches (behavior identical: github always uses `token <t>`
   auth and api.github.com). Regression tests: test_get_headers_token_auth /
   test_get_headers_no_token / test_all_endpoints_github_base.
"""
import asyncio
import importlib
import json
import os
import runpy
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from core.integration_service import IntegrationService


def _module_path(module_name: str) -> str:
    module = importlib.import_module(f"integrations.{module_name}")
    return module.__file__


def _run_module_main(module_name: str):
    """Execute a module's `if __name__ == '__main__'` block via runpy."""
    return runpy.run_path(_module_path(module_name), run_name="__main__")


# ---------------------------------------------------------------------------
# integrations/whatsapp_environment_config.py
# ---------------------------------------------------------------------------

class TestWhatsappEnvironmentConfig:
    def test_get_whatsapp_environment_config_defaults(self, monkeypatch):
        for key in (
            "WHATSAPP_ACCESS_TOKEN_PRODUCTION",
            "WHATSAPP_PHONE_NUMBER_ID_PRODUCTION",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION",
            "WHATSAPP_WEBHOOK_URL_PRODUCTION",
            "WHATSAPP_ACCESS_TOKEN_STAGING",
            "WHATSAPP_PHONE_NUMBER_ID_STAGING",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_STAGING",
            "WHATSAPP_WEBHOOK_URL_STAGING",
            "WHATSAPP_ACCESS_TOKEN_DEV",
            "WHATSAPP_PHONE_NUMBER_ID_DEV",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV",
        ):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("WHATSAPP_WEBHOOK_URL_DEV", raising=False)
        from integrations.whatsapp_environment_config import (
            get_whatsapp_environment_config,
        )

        configs = get_whatsapp_environment_config()
        assert set(configs) == {"production", "staging", "development"}
        for env in ("production", "staging", "development"):
            assert configs[env]["access_token"] is None
            assert configs[env]["phone_number_id"] is None
            assert configs[env]["api_base_url"] == "https://graph.facebook.com/v18.0"
        assert (
            configs["development"]["webhook_url"]
            == "http://localhost:5058/api/whatsapp/webhook"
        )
        assert configs["production"]["webhook_url"] is None
        assert configs["staging"]["webhook_url"] is None

    def test_get_whatsapp_environment_config_env_values(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_PRODUCTION", "tok-prod")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_PRODUCTION", "id-prod")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION", "v-prod")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_URL_PRODUCTION", "https://wa.example/prod")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_STAGING", "tok-stg")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_STAGING", "id-stg")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_STAGING", "v-stg")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_URL_STAGING", "https://wa.example/stg")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "tok-dev")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_DEV", "id-dev")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV", "v-dev")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_URL_DEV", "https://wa.example/dev")
        from integrations.whatsapp_environment_config import (
            get_whatsapp_environment_config,
        )

        configs = get_whatsapp_environment_config()
        assert configs["production"]["access_token"] == "tok-prod"
        assert configs["production"]["phone_number_id"] == "id-prod"
        assert configs["production"]["webhook_verify_token"] == "v-prod"
        assert configs["production"]["webhook_url"] == "https://wa.example/prod"
        assert configs["staging"]["access_token"] == "tok-stg"
        assert configs["staging"]["phone_number_id"] == "id-stg"
        assert configs["staging"]["webhook_verify_token"] == "v-stg"
        assert configs["staging"]["webhook_url"] == "https://wa.example/stg"
        assert configs["development"]["access_token"] == "tok-dev"
        assert configs["development"]["phone_number_id"] == "id-dev"
        assert configs["development"]["webhook_verify_token"] == "v-dev"
        assert configs["development"]["webhook_url"] == "https://wa.example/dev"

    def test_get_current_environment_default(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        from integrations.whatsapp_environment_config import get_current_environment

        assert get_current_environment() == "development"

    def test_get_current_environment_upper(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "PRODUCTION")
        from integrations.whatsapp_environment_config import get_current_environment

        assert get_current_environment() == "production"

    def _loaded_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "tok-dev")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_DEV", "id-dev")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV", "v-dev")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_URL_DEV", "https://wa.example/dev")
        monkeypatch.setenv("WHATSAPP_BUSINESS_NAME", "Acme")
        monkeypatch.setenv("WHATSAPP_AUTO_REPLY_ENABLED", "true")
        monkeypatch.setenv("WHATSAPP_BUSINESS_HOURS_ENABLED", "false")
        monkeypatch.setenv("WHATSAPP_MESSAGE_RETENTION_DAYS", "90")
        monkeypatch.setenv("WHATSAPP_HEALTH_CHECK_INTERVAL", "120")
        monkeypatch.setenv("WHATSAPP_MAX_CONSECUTIVE_FAILURES", "9")
        monkeypatch.setenv("WHATSAPP_MESSAGES_PER_SECOND", "25")
        monkeypatch.setenv("WHATSAPP_MESSAGES_PER_MINUTE", "500")
        monkeypatch.setenv("WHATSAPP_MESSAGES_PER_HOUR", "5000")
        monkeypatch.setenv("WHATSAPP_API_CALLS_PER_HOUR", "500")
        monkeypatch.setenv("DATABASE_HOST", "db1")
        monkeypatch.setenv("DATABASE_NAME", "atom_prod")
        monkeypatch.setenv("DATABASE_USER", "alice")
        monkeypatch.setenv("DATABASE_PASSWORD", "pw")
        monkeypatch.setenv("DATABASE_PORT", "6543")
        from integrations.whatsapp_environment_config import (
            get_whatsapp_config_for_current_env,
        )

        return get_whatsapp_config_for_current_env()

    def test_get_whatsapp_config_for_current_env_overrides(self, monkeypatch):
        config = self._loaded_config(monkeypatch)
        assert config["environment"] == "development"
        assert config["access_token"] == "tok-dev"
        assert config["phone_number_id"] == "id-dev"
        assert config["webhook_verify_token"] == "v-dev"
        assert config["webhook_url"] == "https://wa.example/dev"
        assert config["api_base_url"] == "https://graph.facebook.com/v18.0"
        assert config["database"] == {
            "host": "db1",
            "database": "atom_prod",
            "user": "alice",
            "password": "pw",
            "port": "6543",
        }
        assert config["business_profile"]["name"] == "Acme"
        assert config["business_profile"]["email"] == "support@atom.ai"
        assert config["business_profile"]["website"] == "https://atom.ai"
        assert config["features"]["auto_reply_enabled"] is True
        assert config["features"]["business_hours_enabled"] is False
        assert config["features"]["business_hours_start"] == "09:00"
        assert config["features"]["business_hours_end"] == "18:00"
        assert config["features"]["message_retention_days"] == 90
        assert config["features"]["rate_limiting_enabled"] is True
        assert config["features"]["webhook_security_enabled"] is True
        assert config["features"]["analytics_tracking_enabled"] is True
        assert config["monitoring"]["health_check_interval"] == 120
        assert config["monitoring"]["max_consecutive_failures"] == 9
        assert config["monitoring"]["alert_webhook"] == ""
        assert config["rate_limits"] == {
            "messages_per_second": 25,
            "messages_per_minute": 500,
            "messages_per_hour": 5000,
            "api_calls_per_hour": 500,
        }

    def test_get_whatsapp_config_for_current_env_defaults(self, monkeypatch):
        for key in (
            "ENVIRONMENT",
            "DATABASE_HOST",
            "DATABASE_NAME",
            "DATABASE_USER",
            "DATABASE_PASSWORD",
            "DATABASE_PORT",
            "WHATSAPP_BUSINESS_NAME",
            "WHATSAPP_BUSINESS_DESCRIPTION",
            "WHATSAPP_BUSINESS_EMAIL",
            "WHATSAPP_BUSINESS_WEBSITE",
            "WHATSAPP_BUSINESS_ADDRESS",
            "WHATSAPP_BUSINESS_PHONE",
            "WHATSAPP_AUTO_REPLY_ENABLED",
            "WHATSAPP_BUSINESS_HOURS_ENABLED",
            "WHATSAPP_BUSINESS_HOURS_START",
            "WHATSAPP_BUSINESS_HOURS_END",
            "WHATSAPP_MESSAGE_RETENTION_DAYS",
            "WHATSAPP_RATE_LIMITING_ENABLED",
            "WHATSAPP_WEBHOOK_SECURITY_ENABLED",
            "WHATSAPP_ANALYTICS_TRACKING_ENABLED",
            "WHATSAPP_HEALTH_CHECK_INTERVAL",
            "WHATSAPP_MAX_CONSECUTIVE_FAILURES",
            "WHATSAPP_ALERT_WEBHOOK",
            "WHATSAPP_MESSAGES_PER_SECOND",
            "WHATSAPP_MESSAGES_PER_MINUTE",
            "WHATSAPP_MESSAGES_PER_HOUR",
            "WHATSAPP_API_CALLS_PER_HOUR",
        ):
            monkeypatch.delenv(key, raising=False)
        from integrations.whatsapp_environment_config import (
            get_whatsapp_config_for_current_env,
        )

        config = get_whatsapp_config_for_current_env()
        assert config["environment"] == "development"
        assert config["database"] == {
            "host": "localhost",
            "database": "atom_development",
            "user": "postgres",
            "password": "",
            "port": "5432",
        }
        assert config["business_profile"]["name"] == "ATOM AI Assistant"
        assert config["business_profile"]["description"] == (
            "AI-powered business automation platform"
        )
        assert config["features"]["auto_reply_enabled"] is False
        assert config["features"]["business_hours_enabled"] is True
        assert config["features"]["business_hours_start"] == "09:00"
        assert config["features"]["business_hours_end"] == "18:00"
        assert config["features"]["message_retention_days"] == 30
        assert config["monitoring"]["health_check_interval"] == 60
        assert config["monitoring"]["max_consecutive_failures"] == 5
        assert config["rate_limits"]["messages_per_second"] == 50
        assert config["rate_limits"]["messages_per_minute"] == 1000
        assert config["rate_limits"]["messages_per_hour"] == 10000
        assert config["rate_limits"]["api_calls_per_hour"] == 1000

    def test_unknown_environment_falls_back_to_development(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "mystery")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "dev-tok")
        from integrations.whatsapp_environment_config import (
            get_whatsapp_config_for_current_env,
        )

        config = get_whatsapp_config_for_current_env()
        assert config["environment"] == "mystery"
        assert config["access_token"] == "dev-tok"

    def _valid_config(self, monkeypatch):
        config = self._loaded_config(monkeypatch)
        config["business_hours_enabled"] = True
        config["features"]["business_hours_start"] = "09:00"
        config["features"]["business_hours_end"] = "18:00"
        return config

    def test_validate_valid_config(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        result = validate_whatsapp_config(self._valid_config(monkeypatch))
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert result["warnings"] == []
        assert result["missing_required"] == []

    def test_validate_missing_required_fields(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        result = validate_whatsapp_config({"access_token": "", "phone_number_id": None})
        assert result["is_valid"] is False
        assert result["missing_required"] == ["access_token", "phone_number_id"]
        assert "Required field access_token is missing" in result["errors"]
        assert "Required field phone_number_id is missing" in result["errors"]

    def test_validate_missing_recommended_fields(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        config = {
            "access_token": "tok",
            "phone_number_id": "id",
            "database": {"host": "h", "database": "d", "user": "u"},
        }
        result = validate_whatsapp_config(config)
        assert result["is_valid"] is True
        assert "Recommended field webhook_verify_token is missing" in result["warnings"]
        assert "Recommended field webhook_url is missing" in result["warnings"]

    def test_validate_business_hours_missing_times(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        config = {
            "access_token": "tok",
            "phone_number_id": "id",
            "features": {
                "business_hours_enabled": True,
                "business_hours_start": None,
                "business_hours_end": None,
            },
            "database": {"host": "h", "database": "d", "user": "u"},
        }
        result = validate_whatsapp_config(config)
        assert "Business hours enabled but start or end time not set" in result["warnings"]
        assert result["is_valid"] is True

    def test_validate_business_hours_disabled_no_warning(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        config = {
            "access_token": "tok",
            "phone_number_id": "id",
            "webhook_verify_token": "v",
            "webhook_url": "https://wa.example/hook",
            "features": {"business_hours_enabled": False},
            "database": {"host": "h", "database": "d", "user": "u"},
        }
        result = validate_whatsapp_config(config)
        assert result["warnings"] == []

    def test_validate_database_fields_missing(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        config = {"access_token": "tok", "phone_number_id": "id", "database": {}}
        result = validate_whatsapp_config(config)
        assert result["is_valid"] is False
        assert "Database field host is missing" in result["errors"]
        assert "Database field database is missing" in result["errors"]
        assert "Database field user is missing" in result["errors"]

    def test_validate_no_database_section(self, monkeypatch):
        from integrations.whatsapp_environment_config import validate_whatsapp_config

        result = validate_whatsapp_config({"access_token": "tok", "phone_number_id": "id"})
        assert result["is_valid"] is False
        assert "Database field host is missing" in result["errors"]

    def test_get_whatsapp_config_with_validation(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_STAGING", "tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_STAGING", "id")
        from integrations.whatsapp_environment_config import (
            get_whatsapp_config_with_validation,
        )

        result = get_whatsapp_config_with_validation()
        assert result["environment"] == "staging"
        assert result["config"]["environment"] == "staging"
        assert result["config"]["access_token"] == "tok"
        assert result["validation"]["is_valid"] is True

    def test_main_block_runs(self, monkeypatch, capsys):
        for key in (
            "ENVIRONMENT",
            "WHATSAPP_ACCESS_TOKEN_DEV",
            "WHATSAPP_PHONE_NUMBER_ID_DEV",
        ):
            monkeypatch.delenv(key, raising=False)
        _run_module_main("whatsapp_environment_config")
        output = capsys.readouterr().out
        assert "Environment:" in output
        assert "Configuration valid:" in output


# ---------------------------------------------------------------------------
# integrations/whatsapp_start_development.py
# ---------------------------------------------------------------------------

class TestWhatsappStartDevelopment:
    def test_start_sprint_development_returns_plan(self):
        """REGRESSION: timedelta was only imported inside __main__ -> NameError."""
        from integrations.whatsapp_start_development import start_sprint_development

        plan = start_sprint_development()
        assert plan["sprint_info"]["number"] == 1
        assert plan["sprint_info"]["duration"] == "1 week"
        assert "start_date" in plan["sprint_info"]
        assert "end_date" in plan["sprint_info"]
        assert plan["current_focus"] == "Real-time Message Status Updates"
        features = plan["features_in_development"]
        assert len(features) == 2
        assert features[0]["feature"] == "WebSocket Real-time Updates"
        assert features[0]["status"] == "In Progress"
        assert features[0]["estimated_hours"] == 16
        assert features[1]["feature"] == "Database Performance Optimization"
        assert plan["immediate_actions"]["today"][0]["action"] == (
            "Set up development database"
        )
        assert plan["immediate_actions"]["today"][0]["priority"] == "HIGH"
        assert len(plan["immediate_actions"]["today"]) == 3
        assert len(plan["immediate_actions"]["tomorrow"]) == 2
        assert len(plan["immediate_actions"]["week_remaining"]) == 4
        assert plan["development_environment"]["setup_status"] == "Ready"
        assert plan["development_environment"]["requirements"]["backend"] == [
            "fastapi",
            "uvicorn",
            "websockets",
            "psycopg2-binary",
            "pytest",
            "pytest-asyncio",
        ]
        assert plan["development_environment"]["environment_variables"]["development"][0] == (
            "ENVIRONMENT=development"
        )
        assert plan["success_metrics"]["performance_targets"]["api_response_time"] == "< 200ms"
        assert plan["success_metrics"]["feature_completion"]["websocket_integration"] == "100%"
        assert plan["blocking_issues"] == []
        assert len(plan["risks"]) == 2
        assert plan["risks"][0]["risk"] == "PostgreSQL service not available"
        assert plan["risks"][0]["mitigation"].startswith("Use SQLite")

    def test_sprint_dates_span_seven_days(self):
        from datetime import datetime

        from integrations.whatsapp_start_development import start_sprint_development

        plan = start_sprint_development()
        start = datetime.fromisoformat(plan["sprint_info"]["start_date"])
        end = datetime.fromisoformat(plan["sprint_info"]["end_date"])
        assert (end - start).days == 7

    def test_create_first_feature_returns_handler_code(self):
        from integrations.whatsapp_start_development import create_first_feature

        code = create_first_feature()
        assert "WhatsApp WebSocket Handler" in code
        assert "class WhatsAppWebSocketManager" in code
        assert "async def websocket_endpoint" in code
        assert "async def notify_message_status_change" in code
        assert "async def start_websocket_health_check" in code
        assert "websocket_manager" in code

    def test_create_react_component_returns_tsx(self):
        from integrations.whatsapp_start_development import create_react_component

        code = create_react_component()
        assert "WhatsAppRealtimeStatus" in code
        assert "@chakra-ui/react" in code
        assert "useWhatsAppWebSocket" in code
        assert "MessageStatus" in code
        assert "ConversationStatus" in code

    def test_start_development_now_writes_files_and_returns_plan(self, capsys):
        from integrations.whatsapp_start_development import start_development_now

        m = mock_open()
        with patch("builtins.open", m):
            plan = start_development_now()

        assert plan["current_focus"] == "Real-time Message Status Updates"
        written_paths = [call.args[0] for call in m.call_args_list]
        assert "/tmp/whatsapp_sprint_1_plan.json" in written_paths
        assert any("whatsapp_websocket_handler.py" in p for p in written_paths)
        assert any("WhatsAppRealtimeStatus.tsx" in p for p in written_paths)
        output = capsys.readouterr().out
        assert "STARTING WHATSAPP BUSINESS DEVELOPMENT" in output
        assert "Sprint 1 Plan Created" in output
        assert "WebSocket handler created" in output
        assert "React component created" in output
        assert "IMMEDIATE ACTIONS FOR TODAY" in output
        assert "Set up development database" in output
        assert "Create WebSocket handler foundation" in output
        assert "Implement database indexing" in output
        assert "TOMORROW'S ACTIONS" in output
        assert "Build WebSocket client in React" in output
        assert "SPRINT 1 GOALS" in output
        assert "FILES CREATED" in output
        assert "DEVELOPMENT READY TO START!" in output
        assert "HAPPY CODING" in output

    def test_main_block_runs(self, capsys):
        m = mock_open()
        with patch("builtins.open", m):
            _run_module_main("whatsapp_start_development")
        output = capsys.readouterr().out
        assert "DEVELOPMENT READY TO START!" in output


# ---------------------------------------------------------------------------
# integrations/whatsapp_configuration_setup.py
# ---------------------------------------------------------------------------

class TestWhatsappConfigurationSetup:
    def test_setup_demo_configuration(self):
        from integrations.whatsapp_configuration_setup import setup_demo_configuration

        config = setup_demo_configuration()
        assert config["is_demo"] is True
        assert config["status"] == "demo_configured"
        assert config["environment"] == "development"
        assert config["access_token"].startswith("demo_token_")
        assert len(config["access_token"]) == 11 + 100
        assert config["phone_number_id"] == "123456789012345"
        assert config["webhook_verify_token"].startswith("demo_verify_token_atom_")
        assert config["webhook_url"] == "http://localhost:5058/api/whatsapp/webhook"
        assert config["database"]["host"] == "localhost"
        assert config["business_profile"]["name"] == "ATOM AI Assistant (Demo)"
        assert config["features"]["auto_reply_enabled"] is False
        assert config["features"]["business_hours_enabled"] is True
        assert config["features"]["message_retention_days"] == 30
        assert config["monitoring"]["health_check_interval"] == 60
        assert config["rate_limits"]["messages_per_second"] == 50

    def test_get_or_create_from_env(self, monkeypatch, caplog):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "env-tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_DEV", "env-id")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV", "env-v")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_HOST", "dbh")
        monkeypatch.setenv("WHATSAPP_BUSINESS_NAME", "Acme Env")
        monkeypatch.setenv("WHATSAPP_AUTO_REPLY_ENABLED", "true")
        monkeypatch.setenv("WHATSAPP_MESSAGE_RETENTION_DAYS", "14")
        monkeypatch.setenv("WHATSAPP_HEALTH_CHECK_INTERVAL", "99")
        monkeypatch.setenv("WHATSAPP_MESSAGES_PER_SECOND", "7")
        from integrations.whatsapp_configuration_setup import get_or_create_configuration

        config = get_or_create_configuration()
        assert config["access_token"] == "env-tok"
        assert config["phone_number_id"] == "env-id"
        assert config["webhook_verify_token"] == "env-v"
        assert config["environment"] == "development"
        assert config["is_demo"] is False
        assert config["status"] == "configured"
        assert config["database"]["host"] == "dbh"
        assert config["database"]["database"] == "atom_development"
        assert config["database"]["port"] == "5432"
        assert config["business_profile"]["name"] == "Acme Env"
        assert config["business_profile"]["website"] == "https://atom.ai"
        assert config["features"]["auto_reply_enabled"] is True
        assert config["features"]["business_hours_enabled"] is True
        assert config["features"]["message_retention_days"] == 14
        assert config["monitoring"]["health_check_interval"] == 99
        assert config["rate_limits"]["messages_per_second"] == 7
        assert config["rate_limits"]["messages_per_hour"] == 10000

    def test_get_or_create_missing_creds_falls_back_to_demo(self, monkeypatch, caplog):
        monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN_DEV", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID_DEV", raising=False)
        from integrations.whatsapp_configuration_setup import get_or_create_configuration

        with patch("builtins.open", mock_open()) as m:
            config = get_or_create_configuration()
        assert config["is_demo"] is True
        assert config["status"] == "demo_configured"
        m.assert_any_call("/tmp/whatsapp_demo_config.json", "w")
        assert any(
            "Missing required WhatsApp configuration" in r.message for r in caplog.records
        )

    def test_get_or_create_env_exception_falls_back_to_demo(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "env-tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_DEV", "env-id")
        monkeypatch.setenv("WHATSAPP_MESSAGE_RETENTION_DAYS", "not-a-number")
        from integrations.whatsapp_configuration_setup import get_or_create_configuration

        with patch("builtins.open", mock_open()):
            config = get_or_create_configuration()
        assert config["is_demo"] is True
        assert config["status"] == "demo_configured"

    def test_validate_demo_configuration(self):
        from integrations.whatsapp_configuration_setup import (
            setup_demo_configuration,
            validate_configuration,
        )

        result = validate_configuration(setup_demo_configuration())
        assert result["is_valid"] is True
        assert result["is_demo"] is True
        assert result["configuration_type"] == "demo"
        assert result["warnings"] == ["Using demo configuration for testing"]
        assert result["errors"] == []
        assert result["missing_required"] == []

    def test_validate_production_valid(self):
        from integrations.whatsapp_configuration_setup import validate_configuration

        config = {
            "is_demo": False,
            "access_token": "tok",
            "phone_number_id": "id",
            "webhook_verify_token": "v",
            "webhook_url": "https://wa.example/hook",
        }
        result = validate_configuration(config)
        assert result["is_valid"] is True
        assert result["is_demo"] is False
        assert result["configuration_type"] == "production"
        assert result["warnings"] == []
        assert result["errors"] == []

    def test_validate_production_missing_required(self):
        from integrations.whatsapp_configuration_setup import validate_configuration

        result = validate_configuration(
            {"is_demo": False, "access_token": "", "phone_number_id": None}
        )
        assert result["is_valid"] is False
        assert result["configuration_type"] == "incomplete"
        assert result["missing_required"] == ["access_token", "phone_number_id"]
        assert "Required field access_token is missing" in result["errors"]

    def test_validate_production_missing_recommended_warns(self):
        from integrations.whatsapp_configuration_setup import validate_configuration

        config = {"is_demo": False, "access_token": "tok", "phone_number_id": "id"}
        result = validate_configuration(config)
        assert result["is_valid"] is True
        assert result["configuration_type"] == "production"
        assert "Recommended field webhook_verify_token is missing" in result["warnings"]
        assert "Recommended field webhook_url is missing" in result["warnings"]

    def test_setup_configuration_file(self, caplog):
        from integrations.whatsapp_configuration_setup import setup_configuration_file

        with patch("builtins.open", mock_open()) as m:
            setup_configuration_file()
        m.assert_called_once_with("/tmp/whatsapp_configuration_guide.json", "w")
        handle = m()
        assert handle.write.called
        assert any(
            "Configuration guide saved" in r.message for r in caplog.records
        )

    def test_setup_configuration_file_error(self, caplog):
        from integrations.whatsapp_configuration_setup import setup_configuration_file

        with patch("builtins.open", side_effect=OSError("disk full")):
            setup_configuration_file()
        assert any("Error creating configuration file" in r.message for r in caplog.records)

    def test_initialize_system_demo_mode(self, monkeypatch, capsys, caplog):
        monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN_DEV", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID_DEV", raising=False)
        from integrations.whatsapp_configuration_setup import (
            initialize_configuration_system,
        )

        with patch("builtins.open", mock_open()):
            result = initialize_configuration_system()
        assert result["setup_complete"] is True
        assert result["config"]["is_demo"] is True
        assert result["validation"]["is_demo"] is True
        assert result["validation"]["configuration_type"] == "demo"
        assert "DEMO mode" in capsys.readouterr().out

    def test_initialize_system_valid_configuration(self, monkeypatch, capsys):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN_DEV", "tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID_DEV", "id")
        monkeypatch.setenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV", "v")
        from integrations.whatsapp_configuration_setup import (
            initialize_configuration_system,
        )

        with patch("builtins.open", mock_open()):
            result = initialize_configuration_system()
        assert result["setup_complete"] is True
        assert result["validation"]["is_valid"] is True
        assert result["validation"]["is_demo"] is False
        assert "valid configuration" in capsys.readouterr().out

    def test_initialize_system_incomplete_configuration(self, monkeypatch, capsys):
        """incomplete branch is unreachable via real get_or_create (it always
        falls back to demo), so drive it with a patched non-demo config."""
        from integrations import whatsapp_configuration_setup as mod

        incomplete = {
            "is_demo": False,
            "access_token": "",
            "phone_number_id": "",
        }
        with patch.object(
            mod, "get_or_create_configuration", return_value=incomplete
        ), patch("builtins.open", mock_open()):
            result = mod.initialize_configuration_system()
        assert result["setup_complete"] is True
        assert result["validation"]["is_valid"] is False
        assert result["validation"]["configuration_type"] == "incomplete"
        assert result["validation"]["missing_required"] == [
            "access_token",
            "phone_number_id",
        ]
        assert "configuration incomplete" in capsys.readouterr().out

    def test_initialize_system_exception(self, monkeypatch):
        from integrations import whatsapp_configuration_setup as mod

        with patch.object(
            mod, "get_or_create_configuration", side_effect=RuntimeError("boom")
        ):
            result = mod.initialize_configuration_system()
        assert result["setup_complete"] is False
        assert result["config"]["is_demo"] is True
        assert result["validation"]["is_valid"] is False
        assert result["validation"]["is_demo"] is True
        assert result["validation"]["errors"] == ["boom"]

    def test_main_block_runs(self, monkeypatch, capsys):
        monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN_DEV", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID_DEV", raising=False)
        with patch("builtins.open", mock_open()):
            _run_module_main("whatsapp_configuration_setup")
        output = capsys.readouterr().out
        assert "Configuration Status:" in output
        assert "Demo:" in output


# ---------------------------------------------------------------------------
# integrations/messenger_service.py
# ---------------------------------------------------------------------------

class TestMessengerService:
    def _svc(self, **config):
        with patch("integrations.messenger_service.httpx.AsyncClient") as mock_cls:
            from integrations.messenger_service import MessengerService

            svc = MessengerService(tenant_id="t-msg", config=config)
        svc.client = mock_cls.return_value
        return svc

    def test_init_defaults(self, monkeypatch):
        monkeypatch.delenv("MESSENGER_PAGE_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("MESSENGER_API_VERSION", raising=False)
        with patch("integrations.messenger_service.httpx.AsyncClient") as mock_cls:
            from integrations.messenger_service import MessengerService

            svc = MessengerService(tenant_id="t")
        assert svc.tenant_id == "t"
        assert svc.page_access_token is None
        assert svc.api_version == "v19.0"
        assert svc.base_url == "https://graph.facebook.com/v19.0"
        assert svc.config == {}
        mock_cls.assert_called_once_with(timeout=30.0)

    def test_init_config_none(self, monkeypatch):
        monkeypatch.delenv("MESSENGER_PAGE_ACCESS_TOKEN", raising=False)
        with patch("integrations.messenger_service.httpx.AsyncClient"):
            from integrations.messenger_service import MessengerService

            svc = MessengerService(tenant_id="t", config=None)
        assert svc.config == {}
        assert svc.page_access_token is None

    def test_init_config_and_env(self, monkeypatch):
        monkeypatch.delenv("MESSENGER_PAGE_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("MESSENGER_API_VERSION", "v21.0")
        with patch("integrations.messenger_service.httpx.AsyncClient"):
            from integrations.messenger_service import MessengerService

            svc = MessengerService(tenant_id="t", config={"page_access_token": "cfg-tok"})
        assert svc.page_access_token == "cfg-tok"
        assert svc.api_version == "v21.0"
        assert svc.base_url == "https://graph.facebook.com/v21.0"

    def test_init_env_token_fallback(self, monkeypatch):
        monkeypatch.setenv("MESSENGER_PAGE_ACCESS_TOKEN", "env-tok")
        with patch("integrations.messenger_service.httpx.AsyncClient"):
            from integrations.messenger_service import MessengerService

            svc = MessengerService(tenant_id="t", config={"api_version": "v20.0"})
        assert svc.page_access_token == "env-tok"
        assert svc.api_version == "v20.0"
        assert svc.base_url == "https://graph.facebook.com/v20.0"

    async def test_close(self):
        svc = self._svc(page_access_token="tok")
        svc.client.aclose = AsyncMock(return_value=None)
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    def test_get_capabilities(self):
        svc = self._svc()
        caps = svc.get_capabilities()
        ops = {op["id"] for op in caps["operations"]}
        assert ops == {"send_message", "get_webhook", "subscribe"}
        assert caps["required_params"] == ["page_access_token"]
        assert caps["optional_params"] == ["api_version"]
        assert caps["rate_limits"] == {
            "requests_per_minute": 240,
            "requests_per_hour": 14400,
        }
        assert caps["supports_webhooks"] is True

    def test_health_check_healthy(self):
        svc = self._svc(page_access_token="tok")
        result = svc.health_check()
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["service"] == "messenger"
        assert "last_check" in result

    def test_health_check_degraded(self):
        svc = self._svc()
        result = svc.health_check()
        assert result["healthy"] is False
        assert result["status"] == "degraded"
        assert result["message"] == "Page access token not configured"

    def test_is_integration_service_subclass(self):
        svc = self._svc()
        assert isinstance(svc, IntegrationService)

    async def test_execute_operation_tenant_mismatch(self):
        svc = self._svc(page_access_token="tok")
        result = await svc.execute_operation(
            "send_message",
            {"recipient_id": "r", "message": "hi"},
            context={"tenant_id": "other-tenant"},
        )
        assert result["success"] is False
        assert result["error"] == "Tenant ID validation failed"
        assert result["details"]["reason"] == "cross_tenant_access_prevented"

    async def test_execute_operation_tenant_match_proceeds(self):
        svc = self._svc(page_access_token="tok")
        with patch.object(svc, "_send_message", new=AsyncMock(return_value={"success": True})):
            result = await svc.execute_operation(
                "send_message",
                {"recipient_id": "r", "message": "hi"},
                context={"tenant_id": "t-msg"},
            )
        assert result["success"] is True

    async def test_execute_operation_no_context_proceeds(self):
        svc = self._svc(page_access_token="tok")
        with patch.object(svc, "_get_webhook", new=AsyncMock(return_value={"success": True})):
            result = await svc.execute_operation("get_webhook", {})
        assert result["success"] is True

    async def test_execute_operation_dispatch_subscribe(self):
        svc = self._svc(page_access_token="tok")
        with patch.object(svc, "_subscribe", new=AsyncMock(return_value={"success": True})):
            result = await svc.execute_operation("subscribe", {})
        assert result["success"] is True

    async def test_execute_operation_unknown_raises(self):
        svc = self._svc(page_access_token="tok")
        with pytest.raises(NotImplementedError, match="not supported by Messenger service"):
            await svc.execute_operation("delete_message", {})

    async def test_send_message_missing_params(self):
        svc = self._svc(page_access_token="tok")
        result = await svc.execute_operation("send_message", {})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]
        assert result["details"]["provided_parameters"] == []

    async def test_send_message_missing_one_param(self):
        svc = self._svc(page_access_token="tok")
        result = await svc.execute_operation("send_message", {"recipient_id": "r"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    async def test_send_message_no_token(self):
        svc = self._svc()
        result = await svc.execute_operation(
            "send_message", {"recipient_id": "r", "message": "hi"}
        )
        assert result["success"] is False
        assert result["error"] == "Messenger page access token not configured"
        assert result["details"]["tenant_id"] == "t-msg"

    async def test_send_message_success(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(return_value=None)
        svc.client.post = AsyncMock(return_value=response)
        result = await svc.execute_operation(
            "send_message",
            {"recipient_id": "psid-1", "message": "hello", "messaging_type": "UPDATE"},
        )
        assert result["success"] is True
        assert result["result"] == {"message_sent": True, "recipient_id": "psid-1"}
        call = svc.client.post.call_args
        assert call.args[0] == "https://graph.facebook.com/v19.0/me/messages"
        assert call.kwargs["params"] == {"access_token": "tok"}
        assert call.kwargs["json"]["recipient"] == {"id": "psid-1"}
        assert call.kwargs["json"]["message"] == {"text": "hello"}
        assert call.kwargs["json"]["messaging_type"] == "UPDATE"

    async def test_send_message_default_messaging_type(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(return_value=None)
        svc.client.post = AsyncMock(return_value=response)
        await svc.execute_operation(
            "send_message", {"recipient_id": "psid-1", "message": "hi"}
        )
        assert svc.client.post.call_args.kwargs["json"]["messaging_type"] == "RESPONSE"

    async def test_send_message_http_error(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(side_effect=RuntimeError("403 Forbidden"))
        svc.client.post = AsyncMock(return_value=response)
        result = await svc.execute_operation(
            "send_message", {"recipient_id": "r", "message": "hi"}
        )
        assert result["success"] is False
        assert result["error"] == "403 Forbidden"
        assert result["details"]["tenant_id"] == "t-msg"

    async def test_send_message_network_error(self):
        svc = self._svc(page_access_token="tok")
        svc.client.post = AsyncMock(side_effect=TimeoutError("timed out"))
        result = await svc.execute_operation(
            "send_message", {"recipient_id": "r", "message": "hi"}
        )
        assert result["success"] is False
        assert "timed out" in result["error"]

    async def test_get_webhook(self):
        svc = self._svc(page_access_token="tok")
        result = await svc.execute_operation("get_webhook", {"webhook_url": "https://w.example"})
        assert result["success"] is True
        assert result["result"]["message"] == "Messenger uses webhook-based message delivery"
        assert result["result"]["webhook_url"] == "https://w.example"
        assert (
            result["result"]["configure_webhook"]
            == "https://graph.facebook.com/v19.0/me/subscribed_apps"
        )
        assert result["details"]["tenant_id"] == "t-msg"

    async def test_get_webhook_no_url(self):
        svc = self._svc()
        result = await svc.execute_operation("get_webhook", {})
        assert result["success"] is True
        assert result["result"]["webhook_url"] is None

    async def test_subscribe_no_token(self):
        svc = self._svc()
        result = await svc.execute_operation("subscribe", {})
        assert result["success"] is False
        assert result["error"] == "Messenger page access token not configured"

    async def test_subscribe_success_default_fields(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(return_value=None)
        svc.client.post = AsyncMock(return_value=response)
        result = await svc.execute_operation("subscribe", {})
        assert result["success"] is True
        assert result["result"]["fields"] == ["messages", "messaging_postbacks"]
        assert svc.client.post.call_args.args[0] == (
            "https://graph.facebook.com/v19.0/me/subscribed_apps"
        )
        assert svc.client.post.call_args.kwargs["json"]["fields"] == [
            "messages",
            "messaging_postbacks",
        ]

    async def test_subscribe_success_custom_fields(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(return_value=None)
        svc.client.post = AsyncMock(return_value=response)
        result = await svc.execute_operation(
            "subscribe", {"fields": ["messages", "message_deliveries"]}
        )
        assert result["success"] is True
        assert result["result"]["fields"] == ["messages", "message_deliveries"]

    async def test_subscribe_http_error(self):
        svc = self._svc(page_access_token="tok")
        response = MagicMock()
        response.raise_for_status = MagicMock(side_effect=RuntimeError("400"))
        svc.client.post = AsyncMock(return_value=response)
        result = await svc.execute_operation("subscribe", {})
        assert result["success"] is False
        assert result["error"] == "400"

    async def test_subscribe_network_error(self):
        svc = self._svc(page_access_token="tok")
        svc.client.post = AsyncMock(side_effect=OSError("conn refused"))
        result = await svc.execute_operation("subscribe", {})
        assert result["success"] is False
        assert "conn refused" in result["error"]


# ---------------------------------------------------------------------------
# integrations/github_integration.py
# ---------------------------------------------------------------------------

def _gh_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


class TestGithubIntegration:
    def _gi(self, monkeypatch=None):
        if monkeypatch is not None:
            monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
            monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
        from integrations.github_integration import GithubIntegration

        return GithubIntegration()

    def test_init_env_vars(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "cid")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "csec")
        from integrations.github_integration import GithubIntegration

        gi = GithubIntegration()
        assert gi.client_id == "cid"
        assert gi.client_secret == "csec"
        assert gi.api_endpoint == "https://api.github.com"
        assert gi.access_token is None

    def test_init_env_missing(self, monkeypatch):
        gi = self._gi(monkeypatch)
        assert gi.client_id is None
        assert gi.client_secret is None

    def test_set_access_token(self):
        gi = self._gi()
        gi.set_access_token("tok123")
        assert gi.access_token == "tok123"

    def test_get_headers_with_token(self):
        """REGRESSION: github must always use `token <t>` auth."""
        gi = self._gi()
        gi.set_access_token("tok123")
        headers = gi.get_headers()
        assert headers == {
            "Content-Type": "application/json",
            "Authorization": "token tok123",
        }

    def test_get_headers_without_token(self):
        """REGRESSION: no Authorization header when no token set."""
        gi = self._gi()
        headers = gi.get_headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    async def test_get_user_info_ok(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response({"login": "octo"}),
        ) as mock_get:
            result = await gi.get_user_info()
        assert result == {"login": "octo"}
        mock_get.assert_called_once_with(
            "https://api.github.com/user", headers=gi.get_headers()
        )

    async def test_get_user_info_non_200(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response({}, status_code=404),
        ):
            result = await gi.get_user_info()
        assert result is None

    async def test_get_user_info_exception(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            side_effect=ValueError("boom"),
        ):
            result = await gi.get_user_info()
        assert result is None

    async def test_list_items_ok(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response([{"id": 1}]),
        ) as mock_get:
            result = await gi.list_items()
        assert result == [{"id": 1}]
        assert mock_get.call_args.args[0] == "https://api.github.com/user/repos"

    async def test_list_items_non_200(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            return_value=_gh_response([], status_code=500),
        ):
            result = await gi.list_items()
        assert result == []

    async def test_list_items_exception(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.get",
            side_effect=RuntimeError("boom"),
        ):
            result = await gi.list_items()
        assert result == []

    async def test_create_item_ok(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.post",
            return_value=_gh_response({"id": 1}, status_code=201),
        ) as mock_post:
            result = await gi.create_item({"name": "repo1"})
        assert result == {"id": 1}
        call = mock_post.call_args
        assert call.args[0] == "https://api.github.com/user/repos"
        assert call.kwargs["json"] == {"name": "repo1"}

    async def test_create_item_ok_200(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.post",
            return_value=_gh_response({"id": 2}, status_code=200),
        ):
            result = await gi.create_item({"name": "repo2"})
        assert result == {"id": 2}

    async def test_create_item_non_2xx(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.post",
            return_value=_gh_response(None, status_code=422),
        ):
            result = await gi.create_item({"name": "x"})
        assert result is None

    async def test_create_item_exception(self):
        gi = self._gi()
        with patch(
            "integrations.github_integration.requests.post",
            side_effect=ValueError("boom"),
        ):
            result = await gi.create_item({"name": "x"})
        assert result is None

    def test_all_endpoints_github_base(self):
        """REGRESSION: all three endpoints stay on api.github.com."""
        gi = self._gi()
        assert gi._get_user_endpoint() == "https://api.github.com/user"
        assert gi._get_list_endpoint() == "https://api.github.com/user/repos"
        assert gi._get_create_endpoint() == "https://api.github.com/user/repos"

    def test_global_instance(self):
        from integrations.github_integration import GithubIntegration
        from integrations.github_integration import github_integration

        assert isinstance(github_integration, GithubIntegration)


# ---------------------------------------------------------------------------
# Cross-file sanity: __main__ blocks execute without exceptions under runpy.
# ---------------------------------------------------------------------------

class TestModuleMainBlocks:
    def test_all_three_whatsapp_main_blocks(self, monkeypatch, capsys):
        for key in (
            "ENVIRONMENT",
            "WHATSAPP_ACCESS_TOKEN_DEV",
            "WHATSAPP_PHONE_NUMBER_ID_DEV",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV",
        ):
            monkeypatch.delenv(key, raising=False)
        with patch("builtins.open", mock_open()):
            _run_module_main("whatsapp_configuration_setup")
            _run_module_main("whatsapp_start_development")
            _run_module_main("whatsapp_environment_config")
        output = capsys.readouterr().out
        assert "Configuration Status:" in output
        assert "DEVELOPMENT READY TO START!" in output
        assert "Environment:" in output
