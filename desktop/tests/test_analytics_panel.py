"""Desktop Analytics Panel — structural contract checks.

Round 80v: desktop parity (last matrix gap). The menubar app gained an
AnalyticsPanel mirroring the mobile AnalyticsDashboardScreen via
GET /api/analytics/dashboard/kpis?time_window=… with:
  - time-window switcher (1h/24h/7d/30d)
  - KPI grid: executions, success rate, failures, avg duration
  - session JWT forwarded as Bearer
  - SettingsModal wiring

Source-contract checks runnable WITHOUT Tauri.
"""
import re
from pathlib import Path

MENUBAR = Path(__file__).resolve().parents[2] / "menubar"
PANEL = MENUBAR / "src" / "components" / "AnalyticsPanel.tsx"
SETTINGS = MENUBAR / "src" / "components" / "SettingsModal.tsx"


class TestPanelExists:
    def test_panel_file_exists(self):
        assert PANEL.exists(), f"missing {PANEL}"

    def test_settings_modal_wires_panel(self):
        s = SETTINGS.read_text()
        assert 'from "./AnalyticsPanel"' in s
        assert "<AnalyticsPanel" in s


class TestEndpointContract:
    def _src(self):
        return PANEL.read_text()

    def test_kpis_endpoint_with_time_window(self):
        src = self._src()
        assert "/api/analytics/dashboard/kpis" in src
        assert "time_window=" in src

    def test_all_windows_supported(self):
        src = self._src()
        for w in ("1h", "24h", "7d", "30d"):
            assert f'"{w}"' in src, f"missing time window {w}"

    def test_bearer_token_forwarded(self):
        assert "Authorization" in self._src()


class TestKpiContract:
    def _src(self):
        return PANEL.read_text()

    def test_core_kpis_rendered(self):
        src = self._src()
        for kpi in ("total_executions", "success_rate", "failed_executions"):
            assert kpi in src, f"KPI {kpi} not rendered"

    def test_duration_optional(self):
        """average_duration_seconds is optional — guarded render."""
        assert "average_duration_seconds" in self._src()


class TestUxContract:
    def _src(self):
        return PANEL.read_text()

    def test_loading_state(self):
        assert "loading" in self._src()

    def test_error_state_surfaced(self):
        assert "setError" in self._src()
        assert 'role="alert"' in self._src()

    def test_window_switcher_refetches(self):
        """Changing the window refetches (window_ in load deps)."""
        src = self._src()
        assert re.search(r"useEffect\(\(\) => \{\s*load\(window_\);", src)
