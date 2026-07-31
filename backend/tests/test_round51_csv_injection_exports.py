"""
Round 51 — CSV injection in export endpoints (CWE-1236)
(Red-Green-Refactor).

R21 fixed CSV-injection in `accounting/export_service.py` (`_sanitize_csv_cell`)
but two mounted export paths still write user-controlled free text with NO
sanitization:

  A. `core/feedback_export_service.py:export_to_csv` — served by
     GET /api/feedback/export (feedback_phase2). `original_output` /
     `user_correction` are user/agent-controlled free text — a comment
     starting with `=` becomes a live Excel formula in the exported CSV.

  B. `core/ai_accounting_engine.py:export_general_ledger_csv` — served by
     GET /api/v1/accounting/export/gl + /api/ai-accounting/export/gl.
     `description` / `merchant` come from transaction intake (bank feed,
     manual entry) — same formula-injection class into financial exports.

Fix mirrors R21: prefix cells starting with = + - @ (and tab/CR) with a
single quote so spreadsheet apps render them as text.
"""

from datetime import datetime
from decimal import Decimal

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


FORMULA = '=HYPERLINK("http://evil.example","click")'


class TestFeedbackExportCSV:
    def test_formula_in_original_output_is_neutralized(self):
        from core.feedback_export_service import FeedbackExportService

        service = FeedbackExportService(MagicMock())
        with patch.object(service, "_get_feedback_data", return_value=[{
            "id": "fb-1",
            "agent_id": "ag-1",
            "agent_name": "Agent",
            "agent_execution_id": "ex-1",
            "user_id": "u-1",
            "feedback_type": "correction",
            "thumbs_up_down": "up",
            "rating": 5,
            "original_output": FORMULA,
            "user_correction": "",
            "status": "adjudicated",
            "created_at": "2026-07-31",
            "adjudicated_at": None,
        }]):
            csv_text = service.export_to_csv()

        lines = csv_text.strip().splitlines()
        row = lines[1]
        # The formula cell must be quoted so Excel treats it as text
        assert "'=" in csv_text, (
            "CSV export does not neutralize formula injection (CWE-1236): "
            f"row={row!r}"
        )
        # And the raw formula must not start a cell
        for line in lines:
            assert not line.startswith(FORMULA), (
                f"Unsanitized formula at start of CSV line: {line!r}"
            )

    def test_formula_in_user_correction_is_neutralized(self):
        from core.feedback_export_service import FeedbackExportService

        service = FeedbackExportService(MagicMock())
        with patch.object(service, "_get_feedback_data", return_value=[{
            "id": "fb-1",
            "agent_id": "ag-1",
            "agent_name": "Agent",
            "agent_execution_id": "ex-1",
            "user_id": "u-1",
            "feedback_type": "correction",
            "thumbs_up_down": "up",
            "rating": 5,
            "original_output": "plain text",
            "user_correction": "+cmd|' /C calc'!A0",
            "status": "adjudicated",
            "created_at": "2026-07-31",
            "adjudicated_at": None,
        }]):
            csv_text = service.export_to_csv()

        assert "'+cmd" in csv_text, (
            "CSV export does not neutralize DDE payloads (CWE-1236)"
        )


class TestAICountingGLExportCSV:
    def _engine_with_formula_tx(self):
        from core.ai_accounting_engine import AIAccountingEngine, Transaction

        engine = AIAccountingEngine()
        tx = Transaction(
            id="tx-1",
            date=datetime(2026, 7, 31),
            amount=Decimal("10.00"),
            description=FORMULA,
            merchant="=1+1",
        )
        engine.ingest_transaction(tx)
        return engine

    def test_formula_in_description_is_neutralized(self):
        csv_text = self._engine_with_formula_tx().export_general_ledger_csv()

        assert "'=" in csv_text, (
            "GL CSV export does not neutralize formula injection (CWE-1236)"
        )
        for line in csv_text.strip().splitlines():
            assert not line.startswith(FORMULA), (
                f"Unsanitized formula at start of CSV line: {line!r}"
            )

    def test_formula_in_merchant_is_neutralized(self):
        csv_text = self._engine_with_formula_tx().export_general_ledger_csv()

        assert "'=1+1" in csv_text, (
            "GL CSV export does not neutralize merchant formula injection"
        )

    def test_export_gl_endpoint_returns_sanitized_csv(self):
        """HTTP surface: GET /api/v1/accounting/export/gl (mounted router)."""
        from core.ai_accounting_engine import AIAccountingEngine, Transaction

        engine = AIAccountingEngine()
        tx = Transaction(
            id="tx-1",
            date=datetime(2026, 7, 31),
            amount=Decimal("10.00"),
            description=FORMULA,
        )
        engine.ingest_transaction(tx)

        from api.ai_accounting_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-51", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: MagicMock()

        with patch("core.ai_accounting_engine.ai_accounting", engine):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/export/gl")

        assert resp.status_code == 200
        assert "'=" in resp.text, (
            "GET /export/gl returns unsanitized CSV (CWE-1236)"
        )
