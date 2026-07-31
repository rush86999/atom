"""
Round 49 — Financial input validation: negative/zero amounts accepted
(Red-Green-Refactor).

Mounted financial routers accept non-positive amounts with no validation:
  - /apar/ap/intake + /apar/ar/generate — negative invoices are AUTO-APPROVED
    (negative < auto-approve threshold) and distort AP/AR balances
  - /api/financial-ops/budget/limits — negative monthly limit inverts budget
    guardrails (every positive spend exceeds → category self-DoS)
  - /api/financial-ops/budget/check, /invoices, /contracts — negative amounts
  - /ai-accounting/transactions — negative transaction amounts
Engines also lack guards for non-API callers (defense in depth).
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def make_client(router, user=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: (
        user if user is not None else MagicMock(id="u-49", email="u@example.com")
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestAPARAmountValidation:
    def _client(self):
        from api.apar_routes import router
        return make_client(router)

    def test_ap_intake_rejects_negative_amount(self):
        resp = self._client().post(
            "/apar/ap/intake",
            json={"vendor": "V", "amount": -100.0},
        )
        assert resp.status_code == 422

    def test_ap_intake_rejects_zero_amount(self):
        resp = self._client().post(
            "/apar/ap/intake",
            json={"vendor": "V", "amount": 0},
        )
        assert resp.status_code == 422

    def test_ar_generate_rejects_negative_amount(self):
        resp = self._client().post(
            "/apar/ar/generate",
            json={"customer": "C", "amount": -50.0},
        )
        assert resp.status_code == 422

    def test_positive_amount_still_accepted(self):
        from core.apar_engine import apar_engine

        with patch.object(apar_engine, "intake_invoice", return_value=MagicMock(
            id="ap_1", vendor="V", amount="10.0",
            status=MagicMock(value="approved"), approved_by="auto",
        )):
            resp = self._client().post(
                "/apar/ap/intake",
                json={"vendor": "V", "amount": 10.0},
            )
        assert resp.status_code == 200


class TestFinancialOpsAmountValidation:
    def _client(self):
        from api.financial_ops_routes import router
        return make_client(router)

    def test_budget_limit_rejects_negative(self):
        resp = self._client().post(
            "/api/financial-ops/budget/limits",
            json={"category": "marketing", "monthly_limit": -100.0},
        )
        assert resp.status_code == 422

    def test_spend_check_rejects_negative(self):
        resp = self._client().post(
            "/api/financial-ops/budget/check",
            json={"category": "marketing", "amount": -50.0},
        )
        assert resp.status_code == 422

    def test_invoice_rejects_negative(self):
        resp = self._client().post(
            "/api/financial-ops/invoices",
            json={
                "id": "inv-1", "vendor": "V", "amount": -100.0,
                "date": "2026-07-31",
            },
        )
        assert resp.status_code == 422

    def test_contract_rejects_negative(self):
        resp = self._client().post(
            "/api/financial-ops/contracts",
            json={
                "id": "c-1", "vendor": "V", "monthly_amount": -100.0,
                "start_date": "2026-01-01", "end_date": "2026-12-31",
            },
        )
        assert resp.status_code == 422


class TestAICountingAmountValidation:
    def _client(self):
        from api.ai_accounting_routes import router
        return make_client(router)

    def test_transaction_rejects_negative_amount(self):
        resp = self._client().post(
            "/transactions",
            json={
                "id": "tx-1", "date": "2026-07-31", "amount": -99.99,
                "description": "Refund?",
            },
        )
        assert resp.status_code == 422


class TestEngineGuards:
    def test_apar_engine_rejects_non_positive(self):
        from core.apar_engine import apar_engine

        with patch.object(apar_engine, "_ap_invoices", {}):
            try:
                apar_engine.intake_invoice("manual", {"vendor": "V", "amount": -1})
            except ValueError:
                pass
            else:
                raise AssertionError("intake_invoice must reject negative amounts")

    def test_budget_engine_rejects_non_positive_limit(self):
        from core.financial_ops_engine import BudgetLimit, budget_guardrails

        try:
            budget_guardrails.set_limit(BudgetLimit(category="x", monthly_limit=-1))
        except ValueError:
            pass
        else:
            raise AssertionError("set_limit must reject negative monthly limits")
