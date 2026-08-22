"""Desktop Integrations Panel — structural contract checks.

Round 80r: desktop parity. The menubar app gained an IntegrationsPanel that
mirrors the mobile IntegrationsSection journeys:
  - aggregate + per-service health from GET /api/v1/integrations/health
  - Connect via GET /api/v1/auth/oauth/:provider/initiate?format=json
  - Disconnect via DELETE /api/v1/auth/oauth/tokens/:provider
  - session JWT forwarded as Bearer

These are source-contract checks: they pin the endpoints, the auth header,
the OAuth provider allowlist, and the SettingsModal wiring — the same
invariants the web and mobile surfaces are held to. They run WITHOUT Tauri
(no TAURI_CI gate needed) because no Rust IPC is exercised.
"""
import re
from pathlib import Path

MENUBAR = Path(__file__).resolve().parents[2] / "menubar"
PANEL = MENUBAR / "src" / "components" / "IntegrationsPanel.tsx"
SETTINGS = MENUBAR / "src" / "components" / "SettingsModal.tsx"


class TestPanelExists:
    def test_panel_file_exists(self):
        assert PANEL.exists(), f"missing {PANEL}"

    def test_settings_modal_wires_panel(self):
        s = SETTINGS.read_text()
        assert 'from "./IntegrationsPanel"' in s
        assert "<IntegrationsPanel" in s


class TestEndpointContract:
    def _src(self):
        return PANEL.read_text()

    def test_health_endpoint(self):
        assert "/api/v1/integrations/health" in self._src()

    def test_connect_endpoint_json_variant(self):
        """Mobile parity: initiate?format=json returns {url} for browser flow."""
        src = self._src()
        assert "/initiate?format=json" in src
        assert "data?.url" in src or "data.url" in src

    def test_disconnect_endpoint(self):
        assert "/api/v1/auth/oauth/tokens/" in self._src()

    def test_bearer_token_forwarded(self):
        assert "Authorization" in self._src()
        assert "Bearer" in self._src()


class TestProviderAllowlist:
    """Same OAuth allowlist as the mobile IntegrationsSection."""

    def _src(self):
        return PANEL.read_text()

    ALLOWLIST = [
        "google", "microsoft", "salesforce", "slack", "github",
        "asana", "notion", "trello", "dropbox", "whatsapp", "zoho",
    ]

    def test_allowlist_present(self):
        src = self._src()
        for provider in self.ALLOWLIST:
            assert f'"{provider}"' in src, f"allowlist missing {provider}"


class TestUxStates:
    def _src(self):
        return PANEL.read_text()

    def test_loading_state(self):
        assert "loading" in self._src()

    def test_error_state_surfaced(self):
        assert "setError" in self._src()
        assert "integrations-error" in self._src() or 'role="alert"' in self._src()

    def test_connect_and_disconnect_rendered_conditionally_on_status(self):
        src = self._src()
        # Disconnect only when healthy; Connect only when not healthy.
        disconnect_guard = re.search(
            r"canDisconnect\s*=[^;]+status === .healthy.", src)
        connect_guard = re.search(
            r"canConnect\s*=[^;]+status !== .healthy.", src)
        assert disconnect_guard, "Disconnect must require healthy status"
        assert connect_guard, "Connect must require non-healthy status"

    def test_summary_healthy_count(self):
        src = self._src()
        assert "healthy_integrations" in src
        assert "total_integrations" in src
