"""Coverage wave 100 — integrations/oauth_config.py (TDD, 0% baseline).

Pure config manager — no routes, no network. Tests cover env-driven
credential loading for all 10 services, redirect-URI protocol selection,
per-service getters, validate_all, get_status, get_missing_credentials,
the singleton get_oauth_config, and validate_oauth_before_deployment.

The module-level singleton is reset between tests so env changes are
always observed (no cross-test leakage from previously cached configs).
"""
import pytest

from integrations import oauth_config as oc


ALL_ENV_VARS = {
    "GOOGLE_CLIENT_ID": "g-id", "GOOGLE_CLIENT_SECRET": "g-secret",
    "SLACK_CLIENT_ID": "s-id", "SLACK_CLIENT_SECRET": "s-secret",
    "TRELLO_API_KEY": "t-key", "TRELLO_API_SECRET": "t-secret",
    "ASANA_CLIENT_ID": "a-id", "ASANA_CLIENT_SECRET": "a-secret",
    "NOTION_CLIENT_ID": "n-id", "NOTION_CLIENT_SECRET": "n-secret",
    "DROPBOX_CLIENT_ID": "d-id", "DROPBOX_CLIENT_SECRET": "d-secret",
    "OUTLOOK_CLIENT_ID": "o-id", "OUTLOOK_CLIENT_SECRET": "o-secret",
    "TEAMS_CLIENT_ID": "tm-id", "TEAMS_CLIENT_SECRET": "tm-secret",
    "GITHUB_CLIENT_ID": "gh-id", "GITHUB_CLIENT_SECRET": "gh-secret",
    "WHATSAPP_CLIENT_ID": "w-id", "WHATSAPP_CLIENT_SECRET": "w-secret",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Pin every OAuth env var so host env cannot leak in."""
    for var in ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("PRODUCTION_DOMAIN", raising=False)
    oc._oauth_config = None
    yield
    oc._oauth_config = None


def _set_all(monkeypatch, values=ALL_ENV_VARS):
    for var, val in values.items():
        monkeypatch.setenv(var, val)


class TestLoadCredentials:
    def test_all_configured(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        for service in oc.OAuthService:
            creds = config.get_credentials(service)
            assert creds.configured is True
            assert creds.client_id
            assert creds.client_secret
            assert creds.scopes is not None

    def test_scopes_per_service(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        assert "openid" in config.get_credentials(oc.OAuthService.GOOGLE).scopes
        assert config.get_credentials(oc.OAuthService.NOTION).scopes == []
        assert config.get_credentials(oc.OAuthService.TEAMS).scopes == [
            "https://graph.microsoft.com/Team.ReadBasic.All",
            "https://graph.microsoft.com/Chat.Read"]
        assert config.get_credentials(oc.OAuthService.WHATSAPP).scopes == [
            "whatsapp_business_messaging", "whatsapp_business_management"]

    def test_none_configured(self, monkeypatch):
        config = oc.OAuthConfig()
        for service in oc.OAuthService:
            assert config.get_credentials(service).configured is False

    def test_partial_configured(self, monkeypatch):
        monkeypatch.setenv("OUTLOOK_CLIENT_ID", "o-id")
        config = oc.OAuthConfig()
        assert config.get_credentials(oc.OAuthService.OUTLOOK).configured \
            is False

    def test_localhost_redirect_http(self, monkeypatch):
        _set_all(monkeypatch)
        monkeypatch.setenv("PRODUCTION_DOMAIN", "localhost:8000")
        config = oc.OAuthConfig()
        assert config.get_outlook_config().redirect_uri.startswith(
            "http://localhost:8000/api/auth/outlook/oauth2callback")

    def test_production_redirect_https(self, monkeypatch):
        _set_all(monkeypatch)
        monkeypatch.setenv("PRODUCTION_DOMAIN", "atom.example.com")
        config = oc.OAuthConfig()
        assert config.get_credentials(oc.OAuthService.SLACK).redirect_uri == \
            "https://atom.example.com/api/auth/slack/oauth2callback"

    def test_google_redirect_uri(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        assert config.get_credentials(oc.OAuthService.GOOGLE).redirect_uri \
            == "http://localhost:8000/api/auth/google/oauth2callback"

    def test_unknown_service_returns_default(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        default = config.get_credentials("not_a_service")
        assert default.client_id == ""
        assert default.configured is False


class TestGetters:
    @pytest.fixture
    def config(self, monkeypatch):
        _set_all(monkeypatch)
        return oc.OAuthConfig()

    def test_get_outlook_config(self, config):
        assert config.get_outlook_config().client_id == "o-id"

    def test_get_teams_config(self, config):
        assert config.get_teams_config().client_id == "tm-id"

    def test_get_github_config(self, config):
        assert config.get_github_config().client_id == "gh-id"

    def test_get_whatsapp_config(self, config):
        assert config.get_whatsapp_config().client_id == "w-id"


class TestValidation:
    def test_validate_all_pass(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        result = config.validate_all()
        assert result["valid"] is True
        assert result["total"] == len(oc.OAuthService)
        assert result["configured"] == len(oc.OAuthService)
        assert result["missing"] == []

    def test_validate_all_fail(self, monkeypatch):
        config = oc.OAuthConfig()
        result = config.validate_all()
        assert result["valid"] is False
        assert result["configured"] == 0
        assert len(result["missing"]) == len(oc.OAuthService)
        assert "outlook" in result["missing"]
        assert "github" in result["missing"]

    def test_validate_all_partial(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "g-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "g-secret")
        config = oc.OAuthConfig()
        result = config.validate_all()
        assert result["valid"] is False
        assert result["configured"] == 1
        assert "google" not in result["missing"]
        assert "teams" in result["missing"]

    def test_get_status(self, monkeypatch):
        _set_all(monkeypatch)
        config = oc.OAuthConfig()
        status = config.get_status()
        assert set(status) == {s.value for s in oc.OAuthService}
        for entry in status.values():
            assert entry["configured"] is True
            assert entry["has_client_id"] is True
            assert entry["has_client_secret"] is True
            assert "redirect_uri" in entry
        assert status["outlook"]["redirect_uri"].endswith("/oauth2callback")

    def test_get_status_unconfigured(self, monkeypatch):
        config = oc.OAuthConfig()
        status = config.get_status()
        assert all(not entry["configured"] for entry in status.values())
        assert all(entry["has_client_id"] is False
                   for entry in status.values())

    def test_get_missing_credentials_all(self, monkeypatch):
        config = oc.OAuthConfig()
        missing = config.get_missing_credentials()
        assert len(missing) == 20
        assert "OUTLOOK_CLIENT_ID" in missing
        assert "WHATSAPP_CLIENT_SECRET" in missing

    def test_get_missing_credentials_partial(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "g-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "g-secret")
        monkeypatch.setenv("OUTLOOK_CLIENT_ID", "o-id")
        monkeypatch.setenv("OUTLOOK_CLIENT_SECRET", "o-secret")
        config = oc.OAuthConfig()
        missing = config.get_missing_credentials()
        assert "GOOGLE_CLIENT_ID" not in missing
        assert "GOOGLE_CLIENT_SECRET" not in missing
        assert "OUTLOOK_CLIENT_ID" not in missing
        assert "TEAMS_CLIENT_ID" in missing


class TestSingletonAndDeployment:
    def test_singleton(self, monkeypatch):
        _set_all(monkeypatch)
        first = oc.get_oauth_config()
        second = oc.get_oauth_config()
        assert first is second
        assert first.get_credentials(oc.OAuthService.GITHUB).client_id \
            == "gh-id"

    def test_validate_oauth_before_deployment_pass(self, monkeypatch):
        _set_all(monkeypatch)
        assert oc.validate_oauth_before_deployment() is True

    def test_validate_oauth_before_deployment_fail(self, monkeypatch):
        assert oc.validate_oauth_before_deployment() is False
