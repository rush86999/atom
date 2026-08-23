"""Desktop Approvals Panel — structural contract checks.

Round 80t2: desktop parity (last surface for HITL). The menubar app gained
an ApprovalsPanel mirroring mobile ApprovalsScreen and CLI approvals:
  - pending list from GET /api/agent-governance/pending-approvals
  - approve via POST /api/agent-governance/approve/:id
  - reject via POST /api/agent-governance/reject/:id
  - session JWT forwarded as Bearer
  - SettingsModal wiring

Source-contract checks runnable WITHOUT Tauri.
"""
import re
from pathlib import Path

MENUBAR = Path(__file__).resolve().parents[2] / "menubar"
PANEL = MENUBAR / "src" / "components" / "ApprovalsPanel.tsx"
SETTINGS = MENUBAR / "src" / "components" / "SettingsModal.tsx"


class TestPanelExists:
    def test_panel_file_exists(self):
        assert PANEL.exists(), f"missing {PANEL}"

    def test_settings_modal_wires_panel(self):
        s = SETTINGS.read_text()
        assert 'from "./ApprovalsPanel"' in s
        assert "<ApprovalsPanel" in s


class TestEndpointContract:
    def _src(self):
        return PANEL.read_text()

    def test_pending_endpoint(self):
        assert "/api/agent-governance/pending-approvals" in self._src()

    def test_approve_endpoint(self):
        assert "/api/agent-governance/approve/" in self._src()

    def test_reject_endpoint(self):
        assert "/api/agent-governance/reject/" in self._src()

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
        assert "No pending approvals" in self._src()

    def test_optimistic_removal_on_decision(self):
        """Decided cards are removed without a refetch."""
        src = self._src()
        assert re.search(r"setApprovals\(\(prev\)", src)

    def test_both_decisions_rendered(self):
        src = self._src()
        assert '"approve"' in src and '"reject"' in src
