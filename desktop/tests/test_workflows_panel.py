"""Desktop Workflows Panel — structural contract checks.

Round 80u: desktop parity. The menubar app gained a WorkflowsPanel that
mirrors the mobile workflows suite via the same /api/mobile/workflows
endpoints:
  - catalog from GET /api/mobile/workflows
  - trigger via POST /api/mobile/workflows/trigger {workflow_id}
  - session JWT forwarded as Bearer
  - SettingsModal wiring

Source-contract checks runnable WITHOUT Tauri (no Rust IPC exercised).
"""
import re
from pathlib import Path

MENUBAR = Path(__file__).resolve().parents[2] / "menubar"
PANEL = MENUBAR / "src" / "components" / "WorkflowsPanel.tsx"
SETTINGS = MENUBAR / "src" / "components" / "SettingsModal.tsx"


class TestPanelExists:
    def test_panel_file_exists(self):
        assert PANEL.exists(), f"missing {PANEL}"

    def test_settings_modal_wires_panel(self):
        s = SETTINGS.read_text()
        assert 'from "./WorkflowsPanel"' in s
        assert "<WorkflowsPanel" in s


class TestEndpointContract:
    def _src(self):
        return PANEL.read_text()

    def test_catalog_endpoint(self):
        assert "/api/mobile/workflows" in self._src()

    def test_trigger_endpoint_and_payload(self):
        src = self._src()
        assert "/api/mobile/workflows/trigger" in src
        assert "workflow_id" in src

    def test_bearer_token_forwarded(self):
        src = self._src()
        assert "Authorization" in src
        assert "Bearer" in src


class TestUxContract:
    def _src(self):
        return PANEL.read_text()

    def test_loading_state(self):
        assert "loading" in self._src()

    def test_error_state_surfaced(self):
        assert "setError" in self._src()
        assert 'role="alert"' in self._src()

    def test_empty_state(self):
        assert "No workflows found" in self._src()

    def test_trigger_confirmation(self):
        """A triggered run confirms with the execution id."""
        src = self._src()
        assert "execution_id" in src
        assert "data-testid" in src and "trigger-confirmation" in src

    def test_per_row_trigger_buttons(self):
        src = self._src()
        assert 'data-testid={`trigger-${wf.id}`}' in src

    def test_refresh_after_trigger(self):
        """Status refresh scheduled post-trigger so the run shows up."""
        src = self._src()
        assert re.search(r"setTimeout\(load", src)
