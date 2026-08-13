# -*- coding: utf-8 -*-
"""W72B — coverage push for 8 API modules (standalone >=95% each).

Targets:
1. api/ai_accounting_routes.py    (94% baseline — missing dashboard-summary metric loop)
2. api/apar_routes.py             (46% baseline)
3. api/data_ingestion_routes.py   (44% baseline)
4. api/entity_type_routes.py      (59% baseline)
5. api/forensics_api.py           (58% baseline)
6. api/gateway_log_routes.py      (80% baseline)
7. api/learn_routes.py            (0% baseline — never tested)
8. api/artifact_routes.py         (59% baseline)

Style: FastAPI TestClient + app.dependency_overrides; patches use real
module names (no `backend.` prefix). Engine singletons are module-level lazy
imports in the routes, so patch targets are the source module attributes
(`core.ai_accounting_engine.ai_accounting`, `core.apar_engine.apar_engine`,
`core.hybrid_data_ingestion.get_hybrid_ingestion_service`, ...) while
top-level imports are patched on the importing module
(`api.entity_type_routes.get_entity_type_service`, `api.forensics_api.*`,
`api.learn_routes.MementoEngine`). Zero LLM spend, zero network, no real DB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user
from core.database import get_db
from core.models import Base, UserRole


# ============================================================================
# Shared fixtures / helpers
# ============================================================================


def make_client(router, overrides=None):
    """Build an isolated TestClient for a router with dependency overrides.

    ``overrides`` must be keyed by dependency callable objects
    (e.g. ``{get_current_user: override_fn}``).
    """
    app = FastAPI()
    app.include_router(router)
    for dep, value in (overrides or {}).items():
        app.dependency_overrides[dep] = value
    return TestClient(app, raise_server_exceptions=False)


def fake_user(user_id="u-72", email="user@test.com", role=UserRole.SUPER_ADMIN):
    u = MagicMock()
    u.id = user_id
    u.email = email
    u.role = role
    return u


def user_override(user_id="u-72", email="user@test.com", role=UserRole.SUPER_ADMIN):
    def _override():
        return fake_user(user_id, email, role)
    return _override


def db_override(db):
    def _override():
        yield db
    return _override


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()
    engine.dispose()


# ============================================================================
# 1. api/ai_accounting_routes.py
# ============================================================================

class TestAiAccountingRoutes:
    """Endpoints under the AI Accounting router (module-level lazy imports of
    core.ai_accounting_engine — patch the source module attribute)."""

    @pytest.fixture(autouse=True)
    def _client(self):
        self.client = make_client(
            __import__("api.ai_accounting_routes", fromlist=["router"]).router,
            overrides={get_current_user: user_override()},
        )
        yield
        self.client = None

    @pytest.fixture
    def engine(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "ingest_transaction") as m:
            yield m

    def _tx(self, tx_id="tx-1", status="categorized", confidence=0.9,
            category="Software", reasoning="merchant match"):
        from core.ai_accounting_engine import Transaction, TransactionStatus
        status_map = {
            "categorized": TransactionStatus.CATEGORIZED,
            "review_required": TransactionStatus.REVIEW_REQUIRED,
            "posted": TransactionStatus.POSTED,
            "pending": TransactionStatus.PENDING,
        }
        return Transaction(
            id=tx_id,
            date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            amount=Decimal("49.99"),
            description="Netflix",
            merchant="Netflix",
            category_name=category,
            confidence=confidence,
            reasoning=reasoning,
            status=status_map[status],
        )

    def test_ingest_transaction_success(self, engine):
        engine.return_value = self._tx()
        resp = self.client.post("/transactions", json={
            "id": "tx-1", "date": "2026-05-01T00:00:00Z", "amount": 49.99,
            "description": "Netflix", "merchant": "Netflix", "source": "bank",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "tx-1"
        assert data["status"] == "categorized"
        assert data["category"] == "Software"
        assert data["confidence"] == 90.0
        assert data["requires_review"] is False

    def test_ingest_transaction_credit_card_source(self, engine):
        engine.return_value = self._tx("tx-2")
        resp = self.client.post("/transactions", json={
            "id": "tx-2", "date": "2026-05-02", "amount": 10.0,
            "description": "Coffee", "source": "credit_card",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "tx-2"

    def test_ingest_transaction_review_required(self, engine):
        engine.return_value = self._tx(status="review_required", confidence=0.4)
        resp = self.client.post("/transactions", json={
            "id": "tx-3", "date": "2026-05-03", "amount": 5.0,
            "description": "Misc", "source": "paypal",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["requires_review"] is True
        assert resp.json()["data"]["status"] == "review_required"

    def test_ingest_transaction_validation_error(self):
        resp = self.client.post("/transactions", json={
            "id": "tx-4", "date": "2026-05-04", "amount": 0,
            "description": "Bad",
        })
        assert resp.status_code == 422

    def test_ingest_transaction_missing_id(self):
        resp = self.client.post("/transactions", json={
            "date": "2026-05-04", "amount": 5.0, "description": "Bad",
        })
        assert resp.status_code == 422

    def test_bank_feed_ingest(self):
        from core.ai_accounting_engine import ai_accounting
        results = [
            self._tx("b1", confidence=0.9),
            self._tx("b2", status="review_required", confidence=0.4),
            self._tx("b3", confidence=0.85),
        ]
        with patch.object(ai_accounting, "ingest_bank_feed", return_value=results) as m:
            resp = self.client.post("/bank-feed", json={
                "transactions": [
                    {"id": "b1", "date": "2026-05-01", "amount": 10.0,
                     "description": "x", "merchant": "m", "source": "bank"},
                    {"id": "b2", "date": "2026-05-01", "amount": 11.0,
                     "description": "y", "source": "bank"},
                    {"id": "b3", "date": "2026-05-01", "amount": 12.0,
                     "description": "z", "source": "bank"},
                ]
            })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ingested"] == 3
        assert data["auto_categorized"] == 2
        assert data["review_required"] == 1
        assert len(m.call_args[0][0]) == 3

    def test_bank_feed_empty(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "ingest_bank_feed", return_value=[]):
            resp = self.client.post("/bank-feed", json={"transactions": []})
        assert resp.status_code == 200
        assert resp.json()["data"]["ingested"] == 0

    def test_categorize_transaction(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "learn_categorization") as m:
            resp = self.client.post("/categorize", json={
                "transaction_id": "tx-1", "category_id": "cat-1",
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["transaction_id"] == "tx-1"
        m.assert_called_once_with("tx-1", "cat-1", "u-72")

    def test_categorize_transaction_validation(self):
        resp = self.client.post("/categorize", json={"transaction_id": "tx-1"})
        assert resp.status_code == 422

    def test_review_queue(self):
        from core.ai_accounting_engine import ai_accounting
        pending = [self._tx("r1", status="review_required", confidence=0.3)]
        with patch.object(ai_accounting, "get_pending_review", return_value=pending):
            resp = self.client.get("/review-queue")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 1
        assert data["transactions"][0]["id"] == "r1"
        assert data["transactions"][0]["date"].startswith("2026-05-01")
        assert data["transactions"][0]["confidence"] == 30.0

    def test_review_queue_empty(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "get_pending_review", return_value=[]):
            resp = self.client.get("/review-queue")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0

    def test_all_transactions(self):
        from core.ai_accounting_engine import ai_accounting
        txs = [self._tx("a1"), self._tx("a2", status="posted", confidence=0.95)]
        with patch.object(ai_accounting, "get_all_transactions", return_value=txs):
            resp = self.client.get("/all-transactions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 2
        assert data["transactions"][1]["status"] == "posted"

    def test_update_transaction_success(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "update_transaction", return_value=True) as m:
            resp = self.client.put("/transactions/tx-1", json={"description": "New"})
        assert resp.status_code == 200
        assert resp.json()["data"]["transaction_id"] == "tx-1"
        m.assert_called_once_with("tx-1", {"description": "New"}, "u-72")

    def test_update_transaction_not_found(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "update_transaction", return_value=False):
            resp = self.client.put("/transactions/missing", json={"description": "New"})
        assert resp.status_code == 404

    def test_delete_transaction_success(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "delete_transaction", return_value=True) as m:
            resp = self.client.delete("/transactions/tx-1")
        assert resp.status_code == 200
        m.assert_called_once_with("tx-1", "u-72")

    def test_delete_transaction_not_found(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "delete_transaction", return_value=False):
            resp = self.client.delete("/transactions/missing")
        assert resp.status_code == 404

    def test_post_transaction_success(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "post_transaction", return_value=True) as m:
            resp = self.client.post("/post/tx-1")
        assert resp.status_code == 200
        m.assert_called_once_with("tx-1", "u-72")

    def test_post_transaction_requires_review(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "post_transaction", return_value=False):
            resp = self.client.post("/post/tx-1")
        assert resp.status_code == 422

    def test_auto_post(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "auto_post_high_confidence", return_value=3):
            resp = self.client.post("/auto-post")
        assert resp.status_code == 200
        assert resp.json()["data"]["posted_count"] == 3

    def test_chart_of_accounts(self):
        from core.ai_accounting_engine import ai_accounting, ChartOfAccountsEntry
        coa = {
            "software": ChartOfAccountsEntry(
                account_id="software", name="Software", type="expense",
                keywords=["netflix", "adobe"],
            )
        }
        with patch.object(ai_accounting, "_chart_of_accounts", coa):
            resp = self.client.get("/chart-of-accounts")
        assert resp.status_code == 200
        accounts = resp.json()["data"]["accounts"]
        assert accounts[0]["id"] == "software"
        assert accounts[0]["keywords"] == ["netflix", "adobe"]

    def test_audit_log_all(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "get_audit_log", return_value=[{"event": "x"}]) as m:
            resp = self.client.get("/audit-log")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"event": "x"}]
        m.assert_called_once_with(None)

    def test_audit_log_for_transaction(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "get_audit_log", return_value=[]) as m:
            resp = self.client.get("/audit-log?transaction_id=tx-1")
        assert resp.status_code == 200
        m.assert_called_once_with("tx-1")

    def test_export_gl_csv(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "export_general_ledger_csv",
                          return_value="id,date,amount\n1,2026-05-01,10.0\n"):
            resp = self.client.get("/export/gl")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.text.startswith("id,date")

    def test_export_trial_balance(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "export_trial_balance_json",
                          return_value={"debits": 100, "credits": 100}):
            resp = self.client.get("/export/trial-balance")
        assert resp.status_code == 200
        assert resp.json()["data"]["debits"] == 100

    def test_forecast(self):
        from core.ai_accounting_engine import ai_accounting
        with patch.object(ai_accounting, "get_13_week_forecast",
                          return_value={"projection": []}):
            resp = self.client.get("/forecast")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"projection": []}

    def test_scenario(self):
        from core.ai_accounting_engine import ai_accounting
        projection = [{"week": 1, "balance": 100}]
        with patch.object(ai_accounting, "get_13_week_forecast",
                          return_value={"projection": projection}), \
             patch.object(ai_accounting, "run_scenario", return_value={"impact": "up"}) as m:
            resp = self.client.post("/scenario", params={
                "workspace_id": "default", "scenario_description": "cut costs",
            })
        assert resp.status_code == 200
        assert resp.json()["data"] == {"impact": "up"}
        m.assert_called_once_with("cut costs", projection)

    def test_dashboard_summary_success(self):
        from core.ai_accounting_engine import ai_accounting
        db = MagicMock()
        m1 = MagicMock(); m1.metric_key = "total_revenue"; m1.value = "1200.50"
        m2 = MagicMock(); m2.metric_key = "pending_revenue"; m2.value = "300"
        m3 = MagicMock(); m3.metric_key = "gross_profit"; m3.value = "899.5"
        db.query.return_value.filter.return_value.all.return_value = [m1, m2, m3]
        client = make_client(
            __import__("api.ai_accounting_routes", fromlist=["router"]).router,
            overrides={get_current_user: user_override(), get_db: db_override(db)},
        )
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_revenue"] == 1200.5
        assert data["pending_revenue"] == 300.0
        assert data["runway_months"] == 12
        assert data["currency"] == "USD"
        assert data["source"] == "synced_database"

    def test_dashboard_summary_null_values(self):
        from core.ai_accounting_engine import ai_accounting
        db = MagicMock()
        m1 = MagicMock(); m1.metric_key = "total_revenue"; m1.value = None
        m2 = MagicMock(); m2.metric_key = "other"; m2.value = None
        db.query.return_value.filter.return_value.all.return_value = [m1, m2]
        client = make_client(
            __import__("api.ai_accounting_routes", fromlist=["router"]).router,
            overrides={get_current_user: user_override(), get_db: db_override(db)},
        )
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_revenue"] == 0.0
        assert resp.json()["data"]["pending_revenue"] == 0.0

    def test_dashboard_summary_error(self):
        from core.ai_accounting_engine import ai_accounting
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        client = make_client(
            __import__("api.ai_accounting_routes", fromlist=["router"]).router,
            overrides={get_current_user: user_override(), get_db: db_override(db)},
        )
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 500

    def test_requires_auth(self):
        client = make_client(
            __import__("api.ai_accounting_routes", fromlist=["router"]).router,
            overrides={get_db: db_override(MagicMock())},
        )
        assert client.get("/all-transactions").status_code == 401
        assert client.post("/transactions", json={
            "id": "x", "date": "2026-05-01", "amount": 1, "description": "x",
        }).status_code == 401


# ============================================================================
# 2. api/apar_routes.py
# ============================================================================

class TestAparRoutes:
    """AP/AR endpoints — lazy import of core.apar_engine.apar_engine; router
    has a module-level `dependencies=[Depends(get_current_user)]`."""

    @pytest.fixture(autouse=True)
    def _client(self):
        from api.apar_routes import router
        self.client = make_client(router, overrides={get_current_user: user_override()})
        yield
        self.client = None

    def _invoice(self, inv_id="inv-1", vendor="Acme", amount="123.45",
                 status="approved", approved_by=None, due_date=None,
                 customer=None):
        from types import SimpleNamespace
        inv = SimpleNamespace(
            id=inv_id,
            vendor=vendor,
            amount=Decimal(amount),
            status=SimpleNamespace(value=status),
            approved_by=approved_by,
            due_date=due_date or datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        if customer is not None:
            inv.customer = customer
        return inv

    def test_intake_ap_invoice(self):
        from core.apar_engine import apar_engine
        inv = self._invoice(approved_by="auto")
        with patch.object(apar_engine, "intake_invoice", return_value=inv) as m:
            resp = self.client.post("/apar/ap/intake", json={
                "vendor": "Acme", "amount": "123.45", "due_date": "2026-06-01",
                "line_items": [{"sku": "x", "qty": 1}], "payment_terms": "Net 30",
                "source": "email",
            })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "inv-1"
        assert data["vendor"] == "Acme"
        assert data["status"] == "approved"
        assert data["auto_approved"] is True
        assert m.call_args[0][0] == "email"
        assert m.call_args[0][1]["payment_terms"] == "Net 30"

    def test_intake_ap_invoice_manual_approval(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "intake_invoice",
                          return_value=self._invoice(approved_by=None)):
            resp = self.client.post("/apar/ap/intake", json={
                "vendor": "Acme", "amount": 10, "source": "manual",
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["auto_approved"] is False

    def test_intake_ap_invoice_zero_amount(self):
        resp = self.client.post("/apar/ap/intake", json={"vendor": "Acme", "amount": 0})
        assert resp.status_code == 422

    def test_intake_ap_invoice_negative_amount(self):
        resp = self.client.post("/apar/ap/intake", json={"vendor": "Acme", "amount": -5})
        assert resp.status_code == 422

    def test_approve_ap_invoice_uses_email(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "approve_invoice",
                          return_value=self._invoice()) as m:
            resp = self.client.post("/apar/ap/inv-1/approve")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "approved"
        m.assert_called_once_with("inv-1", "user@test.com")

    def test_approve_ap_invoice_uses_id_when_no_email(self):
        from core.apar_engine import apar_engine
        from api.apar_routes import router
        client = make_client(router, overrides={
            get_current_user: user_override(email=None),
        })
        with patch.object(apar_engine, "approve_invoice",
                          return_value=self._invoice()) as m:
            resp = client.post("/apar/ap/inv-1/approve")
        assert resp.status_code == 200
        m.assert_called_once_with("inv-1", "u-72")

    def test_get_pending_approvals(self):
        from core.apar_engine import apar_engine
        pending = [self._invoice("p1", vendor="V1"), self._invoice("p2", vendor="V2")]
        with patch.object(apar_engine, "get_pending_approvals", return_value=pending):
            resp = self.client.get("/apar/ap/pending")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 2
        assert data["invoices"][0]["vendor"] == "V1"

    def test_get_pending_approvals_empty(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "get_pending_approvals", return_value=[]):
            resp = self.client.get("/apar/ap/pending")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0

    def test_get_upcoming_payments(self):
        from core.apar_engine import apar_engine
        upcoming = [self._invoice("u1", amount="50"), self._invoice("u2", amount="25")]
        with patch.object(apar_engine, "get_upcoming_payments", return_value=upcoming) as m:
            resp = self.client.get("/apar/ap/upcoming?days=14")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 2
        assert data["total_due"] == Decimal("75")
        assert data["invoices"][0]["due_date"].startswith("2026-06-01")
        m.assert_called_once_with(14)

    def test_get_upcoming_payments_default_days(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "get_upcoming_payments",
                          return_value=[]) as m:
            resp = self.client.get("/apar/ap/upcoming")
        assert resp.status_code == 200
        m.assert_called_once_with(7)

    def test_generate_ar_invoice(self):
        from core.apar_engine import apar_engine
        inv = self._invoice(customer="Client Co")
        with patch.object(apar_engine, "generate_invoice", return_value=inv) as m:
            resp = self.client.post("/apar/ar/generate", json={
                "customer": "Client Co", "amount": "99.99",
                "line_items": [{"sku": "s"}], "source": "manual",
            })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "inv-1"
        assert data["customer"] == "Client Co"
        assert m.call_args[0][0] == "manual"

    def test_generate_ar_invoice_zero_amount(self):
        resp = self.client.post("/apar/ar/generate", json={
            "customer": "Client Co", "amount": 0,
        })
        assert resp.status_code == 422

    def test_send_ar_invoice(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "send_invoice", return_value=self._invoice()):
            resp = self.client.post("/apar/ar/inv-1/send")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "sent"

    def test_mark_ar_paid(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "mark_paid", return_value=self._invoice()):
            resp = self.client.post("/apar/ar/inv-1/paid")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "paid"

    def test_get_overdue_invoices(self):
        from core.apar_engine import apar_engine
        overdue = [self._invoice("o1", customer="C1"), self._invoice("o2", customer="C2")]
        with patch.object(apar_engine, "get_overdue_invoices", return_value=overdue):
            resp = self.client.get("/apar/ar/overdue")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 2
        assert data["invoices"][1]["customer"] == "C2"

    def test_get_all_invoices_ar_and_ap(self):
        from core.apar_engine import apar_engine
        ar = self._invoice("ar-1", customer="Client")
        ap = self._invoice("ap-1", vendor="Vendor", customer=None)
        with patch.object(apar_engine, "get_all_invoices", return_value=[ar, ap]):
            resp = self.client.get("/apar/all")
        assert resp.status_code == 200
        invoices = resp.json()["data"]["invoices"]
        assert invoices[0]["type"] == "AR"
        assert invoices[0]["customer"] == "Client"
        assert invoices[0]["vendor"] is None
        assert invoices[1]["type"] == "AP"
        assert invoices[1]["customer"] is None
        assert invoices[1]["vendor"] == "Vendor"
        assert invoices[0]["due_date"].startswith("2026-06-01")

    def test_get_all_invoices_empty(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "get_all_invoices", return_value=[]):
            resp = self.client.get("/apar/all")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0

    def test_send_reminder(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_reminder",
                          return_value={"subject": "Reminder", "body": "Pay!"}):
            resp = self.client.post("/apar/ar/inv-1/remind")
        assert resp.status_code == 200
        assert resp.json()["data"]["subject"] == "Reminder"

    def test_get_collection_summary(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "get_collection_summary",
                          return_value={"outstanding": 1000}):
            resp = self.client.get("/apar/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["outstanding"] == 1000

    def test_download_ar_invoice_success(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          return_value=b"%PDF-1.4 fake"):
            resp = self.client.get("/apar/ar/inv-1/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "invoice_inv-1.pdf" in resp.headers["content-disposition"]

    def test_download_ar_invoice_value_error(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          side_effect=ValueError("no invoice")):
            resp = self.client.get("/apar/ar/missing/download")
        assert resp.status_code == 404

    def test_download_ar_invoice_import_error(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          side_effect=ImportError("no pdf lib")):
            resp = self.client.get("/apar/ar/inv-1/download")
        assert resp.status_code == 500

    def test_download_ap_invoice_success(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          return_value=b"%PDF-1.4 fake"):
            resp = self.client.get("/apar/ap/inv-1/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_download_ap_invoice_value_error(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          side_effect=ValueError("no invoice")):
            resp = self.client.get("/apar/ap/missing/download")
        assert resp.status_code == 404

    def test_download_ap_invoice_import_error(self):
        from core.apar_engine import apar_engine
        with patch.object(apar_engine, "generate_invoice_pdf",
                          side_effect=ImportError("no pdf lib")):
            resp = self.client.get("/apar/ap/inv-1/download")
        assert resp.status_code == 500

    def test_requires_auth(self):
        from api.apar_routes import router
        client = make_client(router, overrides={get_db: db_override(MagicMock())})
        assert client.get("/apar/ap/pending").status_code == 401
        assert client.post("/apar/ap/intake", json={
            "vendor": "Acme", "amount": 5,
        }).status_code == 401


# ============================================================================
# 3. api/data_ingestion_routes.py
# ============================================================================

class TestDataIngestionRoutes:
    """Hybrid data ingestion endpoints — lazy imports of
    core.hybrid_data_ingestion; @require_governance passes through for
    user-initiated requests without agent_id."""

    @pytest.fixture
    def client(self):
        from api.data_ingestion_routes import router
        return make_client(router, overrides={get_current_user: user_override()})

    @pytest.fixture
    def service(self):
        svc = MagicMock()
        svc.usage_stats = {}
        svc.sync_configs = {}
        with patch("core.hybrid_data_ingestion.get_hybrid_ingestion_service",
                   return_value=svc) as m:
            m.svc = svc
            yield m

    def test_get_workspace_id_helper(self):
        from api.data_ingestion_routes import get_workspace_id
        assert get_workspace_id() == "default"

    def test_usage_summary(self, client, service):
        svc = service.svc
        svc.get_usage_summary.return_value = {
            "workspace_id": "default",
            "integrations": [{"integration_id": "salesforce", "auto_sync_enabled": True}],
            "total_synced_records": 42,
            "auto_sync_enabled_count": 1,
        }
        resp = client.get("/api/data-ingestion/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workspace_id"] == "default"
        assert body["total_synced_records"] == 42

    def test_usage_summary_error(self, client, service):
        service.svc.get_usage_summary.side_effect = RuntimeError("boom")
        resp = client.get("/api/data-ingestion/usage")
        assert resp.status_code == 500

    def test_usage_summary_unauthenticated(self):
        from api.data_ingestion_routes import router
        client = make_client(router, overrides={get_db: db_override(MagicMock())})
        assert client.get("/api/data-ingestion/usage").status_code == 401

    def test_enable_sync_with_config_and_frequency(self, client, service):
        svc = service.svc
        stats = MagicMock()
        stats.sync_frequency_minutes = 60
        svc.usage_stats["sf"] = stats
        with patch("core.hybrid_data_ingestion.SyncConfiguration") as cfg_cls:
            cfg_cls.return_value = MagicMock()
            resp = client.post("/api/data-ingestion/enable-sync", json={
                "integration_id": "sf",
                "entity_types": ["contacts", "deals"],
                "sync_frequency_minutes": 30,
                "sync_last_n_days": 15,
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["integration_id"] == "sf"
        svc.enable_auto_sync.assert_called_once()
        cfg_cls.assert_called_once()
        assert stats.sync_frequency_minutes == 30

    def test_enable_sync_no_entity_types_no_frequency(self, client, service):
        svc = service.svc
        with patch("core.hybrid_data_ingestion.SyncConfiguration") as cfg_cls:
            resp = client.post("/api/data-ingestion/enable-sync", json={
                "integration_id": "sf",
                "sync_frequency_minutes": None,
                "sync_last_n_days": None,
            })
        assert resp.status_code == 200
        cfg_cls.assert_not_called()
        svc.enable_auto_sync.assert_called_once_with("sf", None)

    def test_enable_sync_zero_frequency_skips_stats(self, client, service):
        svc = service.svc
        stats = MagicMock()
        stats.sync_frequency_minutes = 60
        svc.usage_stats["sf"] = stats
        with patch("core.hybrid_data_ingestion.SyncConfiguration"):
            resp = client.post("/api/data-ingestion/enable-sync", json={
                "integration_id": "sf",
                "sync_frequency_minutes": 0,
            })
        assert resp.status_code == 200
        assert stats.sync_frequency_minutes == 60

    def test_enable_sync_stats_missing(self, client, service):
        svc = service.svc
        with patch("core.hybrid_data_ingestion.SyncConfiguration"):
            resp = client.post("/api/data-ingestion/enable-sync", json={
                "integration_id": "unknown", "sync_frequency_minutes": 30,
            })
        assert resp.status_code == 200

    def test_enable_sync_error(self, client, service):
        service.svc.enable_auto_sync.side_effect = RuntimeError("boom")
        resp = client.post("/api/data-ingestion/enable-sync", json={
            "integration_id": "sf",
        })
        assert resp.status_code == 500

    def test_enable_sync_missing_integration_id(self, client):
        resp = client.post("/api/data-ingestion/enable-sync", json={})
        assert resp.status_code == 422

    def test_disable_sync(self, client, service):
        resp = client.post("/api/data-ingestion/disable-sync/sf")
        assert resp.status_code == 200
        assert resp.json()["data"]["integration_id"] == "sf"
        service.svc.disable_auto_sync.assert_called_once_with("sf")

    def test_disable_sync_error(self, client, service):
        service.svc.disable_auto_sync.side_effect = RuntimeError("boom")
        resp = client.post("/api/data-ingestion/disable-sync/sf")
        assert resp.status_code == 500

    def test_trigger_sync_force_full(self, client, service):
        service.svc.sync_integration_data = AsyncMock(return_value={
            "success": True,
            "records_fetched": 10,
            "records_ingested": 8,
            "entities_extracted": 4,
            "relationships_extracted": 3,
        })
        resp = client.post("/api/data-ingestion/sync/sf?force=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["integration_id"] == "sf"
        assert body["records_fetched"] == 10
        assert body["records_ingested"] == 8
        assert body["entities_extracted"] == 4
        assert body["relationships_extracted"] == 3
        assert body["message"] == "Sync completed"

    def test_trigger_sync_with_error_message(self, client, service):
        service.svc.sync_integration_data = AsyncMock(return_value={
            "success": False, "error": "rate limited",
        })
        resp = client.post("/api/data-ingestion/sync/sf")
        assert resp.status_code == 200
        assert resp.json()["message"] == "rate limited"

    def test_trigger_sync_with_skipped_message(self, client, service):
        service.svc.sync_integration_data = AsyncMock(return_value={
            "success": True, "skipped": "recently synced",
        })
        resp = client.post("/api/data-ingestion/sync/sf")
        assert resp.status_code == 200
        assert resp.json()["message"] == "recently synced"

    def test_trigger_sync_error(self, client, service):
        service.svc.sync_integration_data = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/data-ingestion/sync/sf")
        assert resp.status_code == 500

    def test_sync_status_found_full(self, client, service):
        svc = service.svc
        stats = MagicMock()
        stats.auto_sync_enabled = True
        stats.total_calls = 5
        stats.successful_calls = 4
        stats.last_used = datetime(2026, 5, 1, tzinfo=timezone.utc)
        stats.last_synced = datetime(2026, 5, 2, tzinfo=timezone.utc)
        stats.sync_frequency_minutes = 30
        svc.usage_stats["sf"] = stats
        config = MagicMock()
        config.entity_types = ["contacts"]
        svc.sync_configs["sf"] = config
        resp = client.get("/api/data-ingestion/sync-status/sf")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is True
        assert body["auto_sync_enabled"] is True
        assert body["total_calls"] == 5
        assert body["last_used"] == "2026-05-01T00:00:00+00:00"
        assert body["entity_types"] == ["contacts"]

    def test_sync_status_found_no_timestamps_no_config(self, client, service):
        svc = service.svc
        stats = MagicMock()
        stats.auto_sync_enabled = False
        stats.total_calls = 0
        stats.successful_calls = 0
        stats.last_used = None
        stats.last_synced = None
        stats.sync_frequency_minutes = 60
        svc.usage_stats["sf"] = stats
        resp = client.get("/api/data-ingestion/sync-status/sf")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is True
        assert body["last_used"] is None
        assert body["entity_types"] == []

    def test_sync_status_not_found(self, client, service):
        resp = client.get("/api/data-ingestion/sync-status/unknown")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is False
        assert "No usage data" in body["message"]

    def test_sync_status_error(self, client, service):
        service.svc.usage_stats = None
        resp = client.get("/api/data-ingestion/sync-status/sf")
        assert resp.status_code == 500

    def test_available_integrations(self, client):
        def _cfg(iid):
            cfg = MagicMock()
            cfg.entity_types = ["a", "b"]
            cfg.sync_last_n_days = 30
            cfg.max_records_per_sync = 500
            return cfg
        with patch("core.hybrid_data_ingestion.DEFAULT_SYNC_CONFIGS",
                   {"salesforce": _cfg("salesforce"), "hubspot": _cfg("hubspot")}):
            resp = client.get("/api/data-ingestion/available-integrations")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["id"] == "salesforce"
        assert data[0]["default_sync_days"] == 30
        assert data[0]["max_records"] == 500
        assert resp.json()["metadata"]["count"] == 2

    def test_available_integrations_empty(self, client):
        with patch("core.hybrid_data_ingestion.DEFAULT_SYNC_CONFIGS", {}):
            resp = client.get("/api/data-ingestion/available-integrations")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["metadata"]["count"] == 0


# ============================================================================
# 4. api/entity_type_routes.py
# ============================================================================

class TestEntityTypeRoutes:
    """Entity type endpoints — top-level imports of the service getters, so
    patch api.entity_type_routes.<name>."""

    @pytest.fixture
    def client(self):
        from api.entity_type_routes import router
        return make_client(router, overrides={get_current_user: user_override()})

    def _entity_type(self, et_id="et-1", slug="invoice"):
        et = MagicMock()
        et.id = et_id
        et.slug = slug
        et.display_name = "Invoice"
        et.description = "desc"
        et.json_schema = {"type": "object"}
        et.available_skills = ["skill-1"]
        et.is_system = False
        return et

    def test_create_entity_type_success(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            svc = getter.return_value
            svc.create_entity_type.return_value = self._entity_type()
            resp = client.post("/api/entity-types?workspace_id=default", json={
                "slug": "invoice", "display_name": "Invoice",
                "json_schema": {"type": "object"},
                "description": "desc", "available_skills": ["s1"],
            })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "et-1"
        assert data["slug"] == "invoice"
        svc.create_entity_type.assert_called_once_with(
            tenant_id="default", slug="invoice", display_name="Invoice",
            json_schema={"type": "object"}, description="desc",
            available_skills=["s1"],
        )

    def test_create_entity_type_value_error(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.create_entity_type.side_effect = ValueError("duplicate slug")
            resp = client.post("/api/entity-types?workspace_id=default", json={
                "slug": "invoice", "display_name": "Invoice",
                "json_schema": {"type": "object"},
            })
        assert resp.status_code == 422
        assert "duplicate slug" in resp.json()["detail"]["error"]["message"]

    def test_create_entity_type_missing_fields(self, client):
        resp = client.post("/api/entity-types?workspace_id=default",
                           json={"slug": "invoice"})
        assert resp.status_code == 422

    def test_list_entity_types(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            svc = getter.return_value
            svc.list_entity_types.return_value = [
                self._entity_type("a", "alpha"), self._entity_type("b", "beta"),
            ]
            resp = client.get("/api/entity-types?workspace_id=default&include_system=true")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["slug"] == "alpha"
        assert data[0]["is_system"] is False
        assert data[0]["available_skills"] == ["skill-1"]
        svc.list_entity_types.assert_called_once_with(
            tenant_id="default", include_system=True)

    def test_list_entity_types_default_include_system(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.list_entity_types.return_value = []
            resp = client.get("/api/entity-types?workspace_id=default")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        getter.return_value.list_entity_types.assert_called_once_with(
            tenant_id="default", include_system=False)

    def test_get_entity_type_success(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.get_entity_type.return_value = self._entity_type()
            resp = client.get("/api/entity-types/et-1?workspace_id=default")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "et-1"
        assert data["display_name"] == "Invoice"
        getter.return_value.get_entity_type.assert_called_once_with(
            tenant_id="default", entity_type_id="et-1")

    def test_get_entity_type_not_found(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.get_entity_type.return_value = None
            resp = client.get("/api/entity-types/missing?workspace_id=default")
        assert resp.status_code == 404

    def test_update_entity_type_success(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            svc = getter.return_value
            svc.update_entity_type.return_value = self._entity_type()
            resp = client.patch("/api/entity-types/et-1?workspace_id=default", json={
                "display_name": "New Name", "description": "new desc",
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "et-1"
        svc.update_entity_type.assert_called_once_with(
            tenant_id="default", entity_type_id="et-1",
            display_name="New Name", json_schema=None,
            description="new desc", available_skills=None,
        )

    def test_update_entity_type_full(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.update_entity_type.return_value = self._entity_type()
            resp = client.patch("/api/entity-types/et-1?workspace_id=default", json={
                "json_schema": {"type": "object", "x": 1},
                "available_skills": ["s1", "s2"],
            })
        assert resp.status_code == 200

    def test_update_entity_type_value_error(self, client):
        with patch("api.entity_type_routes.get_entity_type_service") as getter:
            getter.return_value.update_entity_type.side_effect = ValueError("bad schema")
            resp = client.patch("/api/entity-types/et-1?workspace_id=default",
                                json={"display_name": "X"})
        assert resp.status_code == 422

    def test_suggest_entity_schema(self, client):
        with patch("api.entity_type_routes.get_entity_schema_suggestion_service") as getter:
            svc = getter.return_value
            svc.suggest_schema = AsyncMock(return_value={"type": "object", "props": {}})
            resp = client.post("/api/entity-types/suggest-schema", json={
                "display_name": "Invoice", "description": "a customer invoice",
            })
        assert resp.status_code == 200
        assert resp.json()["data"] == {"type": "object", "props": {}}
        svc.suggest_schema.assert_awaited_once_with(
            display_name="Invoice", description="a customer invoice")

    def test_suggest_entity_schema_default_description(self, client):
        with patch("api.entity_type_routes.get_entity_schema_suggestion_service") as getter:
            svc = getter.return_value
            svc.suggest_schema = AsyncMock(return_value={})
            resp = client.post("/api/entity-types/suggest-schema",
                               json={"display_name": "Invoice"})
        assert resp.status_code == 200
        svc.suggest_schema.assert_awaited_once_with(
            display_name="Invoice", description="")

    def test_suggest_schema_missing_display_name(self, client):
        resp = client.post("/api/entity-types/suggest-schema", json={})
        assert resp.status_code == 422

    def test_requires_auth(self):
        from api.entity_type_routes import router
        client = make_client(router, overrides={get_db: db_override(MagicMock())})
        assert client.get("/api/entity-types?workspace_id=default").status_code == 401
        assert client.post("/api/entity-types?workspace_id=default", json={
            "slug": "s", "display_name": "S", "json_schema": {},
        }).status_code == 401


# ============================================================================
# 5. api/forensics_api.py
# ============================================================================

class TestForensicsApi:
    """Financial forensics endpoints — router-level auth dependency plus
    top-level get_forensics_services import (patch api.forensics_api.*)."""

    @pytest.fixture
    def client(self):
        from api.forensics_api import router
        return make_client(router, overrides={get_current_user: user_override()})

    @pytest.fixture
    def services(self):
        vendor = MagicMock()
        vendor.detect_price_drift = AsyncMock(return_value=[{"vendor": "X", "drift": 0.2}])
        pricing = MagicMock()
        pricing.get_pricing_recommendations = AsyncMock(return_value=[{"action": "raise"}])
        waste = MagicMock()
        waste.find_zombie_subscriptions = AsyncMock(return_value=[{"service": "Z"}])
        svcs = {"vendor": vendor, "pricing": pricing, "waste": waste}
        with patch("api.forensics_api.get_forensics_services", return_value=svcs) as m:
            m.svcs = svcs
            yield m

    def test_vendor_drift_success(self, client, services):
        resp = client.get("/api/forensics/vendor-drift")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"vendor": "X", "drift": 0.2}]
        assert resp.json()["message"] == "Vendor drift data retrieved successfully"

    def test_pricing_opportunities_success(self, client, services):
        resp = client.get("/api/forensics/pricing-opportunities")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"action": "raise"}]

    def test_subscription_waste_success(self, client, services):
        resp = client.get("/api/forensics/subscription-waste")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"service": "Z"}]

    def test_vendor_drift_error(self, client, services):
        services.svcs["vendor"].detect_price_drift.side_effect = RuntimeError("boom")
        resp = client.get("/api/forensics/vendor-drift")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_pricing_opportunities_error(self, client, services):
        services.svcs["pricing"].get_pricing_recommendations.side_effect = RuntimeError("boom")
        resp = client.get("/api/forensics/pricing-opportunities")
        assert resp.status_code == 500

    def test_subscription_waste_error(self, client, services):
        services.svcs["waste"].find_zombie_subscriptions.side_effect = RuntimeError("boom")
        resp = client.get("/api/forensics/subscription-waste")
        assert resp.status_code == 500

    def test_services_getter_error(self, client, services):
        services.side_effect = RuntimeError("boom")
        resp = client.get("/api/forensics/vendor-drift")
        assert resp.status_code == 500

    def test_requires_auth(self):
        from api.forensics_api import router
        client = make_client(router, overrides={get_db: db_override(MagicMock())})
        assert client.get("/api/forensics/vendor-drift").status_code == 401
        assert client.get("/api/forensics/pricing-opportunities").status_code == 401
        assert client.get("/api/forensics/subscription-waste").status_code == 401


# ============================================================================
# 6. api/gateway_log_routes.py
# ============================================================================

class TestGatewayLogRoutes:
    """Gateway request-log viewer — real in-memory SQLite with
    GatewayRequestLog rows; owner-scoped queries."""

    @pytest.fixture
    def client(self, memory_db):
        from api.gateway_log_routes import router
        return make_client(router, overrides={
            get_current_user: user_override(),
            get_db: db_override(memory_db),
        })

    def _log_row(self, row_id="log-1", user_id="u-72", created_at=None, **kw):
        from core.models import GatewayRequestLog
        row = GatewayRequestLog(
            id=row_id,
            user_id=user_id,
            provider=kw.get("provider", "opencode-go"),
            model=kw.get("model", "deepseek-v4-flash"),
            stream=kw.get("stream", False),
            status_code=kw.get("status_code", 200),
            latency_ms=kw.get("latency_ms", 12),
            prompt_tokens=kw.get("prompt_tokens", 10),
            completion_tokens=kw.get("completion_tokens", 20),
            cost_usd=kw.get("cost_usd", 0.001),
            created_at=created_at or datetime(2026, 5, 1, tzinfo=timezone.utc),
            request_json=kw.get("request_json", '{"messages": []}'),
            response_json=kw.get("response_json", '{"choices": []}'),
        )
        return row

    def test_list_logs(self, client, memory_db):
        memory_db.add_all([
            self._log_row("log-1"),
            self._log_row("log-2", created_at=datetime(2026, 5, 2, tzinfo=timezone.utc)),
        ])
        memory_db.commit()
        resp = client.get("/api/v1/gateway/logs")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["id"] == "log-2"
        assert data[0]["provider"] == "opencode-go"
        assert data[0]["stream"] is False
        assert data[0]["created_at"].startswith("2026-05-02")
        assert data[0]["request_json"] == '{"messages": []}'

    def test_list_logs_with_created_at_none(self):
        from api.gateway_log_routes import router
        row = MagicMock()
        row.id = "log-null"
        row.provider = "opencode-go"
        row.model = "deepseek-v4-flash"
        row.stream = False
        row.status_code = 200
        row.latency_ms = 1
        row.prompt_tokens = 1
        row.completion_tokens = 1
        row.cost_usd = 0.001
        row.created_at = None
        row.request_json = None
        row.response_json = None
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [row]
        client = make_client(router, overrides={
            get_current_user: user_override(),
            get_db: db_override(db),
        })
        resp = client.get("/api/v1/gateway/logs")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["created_at"] is None

    def test_list_logs_empty_and_filters(self, client):
        resp = client.get("/api/v1/gateway/logs?limit=5&offset=10")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_logs_owner_scoped(self, client, memory_db):
        memory_db.add(self._log_row("mine"))
        memory_db.add(self._log_row("other", user_id="someone-else"))
        memory_db.commit()
        resp = client.get("/api/v1/gateway/logs")
        assert [r["id"] for r in resp.json()["data"]] == ["mine"]

    def test_list_logs_limit_validation(self, client):
        assert client.get("/api/v1/gateway/logs?limit=201").status_code == 422
        assert client.get("/api/v1/gateway/logs?limit=0").status_code == 422

    def test_get_log_success(self, client, memory_db):
        memory_db.add(self._log_row("log-1"))
        memory_db.commit()
        resp = client.get("/api/v1/gateway/logs/log-1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "log-1"
        assert data["model"] == "deepseek-v4-flash"
        assert data["cost_usd"] == 0.001

    def test_get_log_not_found(self, client):
        resp = client.get("/api/v1/gateway/logs/missing")
        assert resp.status_code == 404

    def test_get_log_other_users_row_404(self, client, memory_db):
        memory_db.add(self._log_row("theirs", user_id="other"))
        memory_db.commit()
        resp = client.get("/api/v1/gateway/logs/theirs")
        assert resp.status_code == 404

    def test_requires_auth(self, memory_db):
        from api.gateway_log_routes import router
        client = make_client(router, overrides={get_db: db_override(memory_db)})
        assert client.get("/api/v1/gateway/logs").status_code == 401
        assert client.get("/api/v1/gateway/logs/log-1").status_code == 401


# ============================================================================
# 7. api/learn_routes.py
# ============================================================================

class TestLearnRoutes:
    """POST /api/v1/learn — MementoEngine imported at module top, so patch
    api.learn_routes.MementoEngine; require_permission internally depends on
    core.auth.get_current_user (same callable overridden here)."""

    @pytest.fixture
    def client(self, memory_db):
        from api.learn_routes import router
        tenant = MagicMock()
        tenant.id = "tenant-1"
        from core.auth import get_current_tenant
        return make_client(router, overrides={
            get_current_user: user_override(),
            get_db: db_override(memory_db),
            get_current_tenant: lambda: tenant,
        })

    @pytest.fixture
    def engine_cls(self):
        with patch("api.learn_routes.MementoEngine") as m:
            m.return_value.learn_from_execution = AsyncMock()
            yield m

    def _result(self, success=True, skill_name="distilled_skill", error=None):
        return {"success": success, "skill_name": skill_name, "error": error}

    def test_learn_success(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.return_value = self._result()
        resp = client.post("/api/v1/learn", json={
            "execution_id": "exec-1", "skill_name": "my_skill",
            "description": "distilled skill",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True
        engine_cls.assert_called_once()
        engine_cls.return_value.learn_from_execution.assert_awaited_once_with(
            tenant_id="tenant-1", agent_id="u-72", execution_id="exec-1",
            skill_name="my_skill", description="distilled skill",
        )

    def test_learn_success_defaults(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.return_value = self._result()
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 200
        engine_cls.return_value.learn_from_execution.assert_awaited_once_with(
            tenant_id="tenant-1", agent_id="u-72", execution_id="exec-1",
            skill_name=None, description=None,
        )

    def test_learn_user_without_id(self, client, engine_cls):
        from api.learn_routes import router
        from core.auth import get_current_tenant
        tenant = MagicMock()
        tenant.id = "tenant-1"
        client = make_client(router, overrides={
            get_current_user: user_override(user_id=None),
            get_db: db_override(MagicMock()),
            get_current_tenant: lambda: tenant,
        })
        engine_cls.return_value.learn_from_execution.return_value = self._result()
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 200
        engine_cls.return_value.learn_from_execution.assert_awaited_once_with(
            tenant_id="tenant-1", agent_id=None, execution_id="exec-1",
            skill_name=None, description=None,
        )

    def test_learn_execution_not_found(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.return_value = self._result(
            success=False, error="Execution not found")
        resp = client.post("/api/v1/learn", json={"execution_id": "nope"})
        assert resp.status_code == 404
        assert "Execution not found" in resp.json()["detail"]

    def test_learn_not_found_case_insensitive(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.return_value = self._result(
            success=False, error="NOt FOUND anywhere")
        resp = client.post("/api/v1/learn", json={"execution_id": "nope"})
        assert resp.status_code == 404

    def test_learn_other_failure(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.return_value = self._result(
            success=False, error="skill name conflicts")
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 422
        assert "skill name conflicts" in resp.json()["detail"]

    def test_learn_exception(self, client, engine_cls):
        engine_cls.return_value.learn_from_execution.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_learn_validation_error(self, client):
        resp = client.post("/api/v1/learn", json={})
        assert resp.status_code == 422

    def test_learn_forbidden_without_permission(self):
        from api.learn_routes import router
        from core.auth import get_current_tenant
        tenant = MagicMock()
        tenant.id = "tenant-1"
        client = make_client(router, overrides={
            get_current_user: user_override(role=UserRole.GUEST),
            get_db: db_override(MagicMock()),
            get_current_tenant: lambda: tenant,
        })
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 403

    def test_requires_auth(self):
        from api.learn_routes import router
        client = make_client(router, overrides={get_db: db_override(MagicMock())})
        resp = client.post("/api/v1/learn", json={"execution_id": "exec-1"})
        assert resp.status_code == 401


# ============================================================================
# 8. api/artifact_routes.py
# ============================================================================

class TestArtifactRoutes:
    """Artifact CRUD + versioning — real in-memory SQLite; get_current_user
    imported from core.security_dependencies, which re-exports the same
    core.auth callable."""

    @pytest.fixture
    def client(self, memory_db):
        from api.artifact_routes import router
        return make_client(router, overrides={
            get_current_user: user_override(),
            get_db: db_override(memory_db),
        })

    def _artifact(self, artifact_id="art-1", session_id="sess-1", type="code",
                  name="script.py", content="print(1)"):
        from core.models import Artifact
        return Artifact(
            id=artifact_id,
            workspace_id="default",
            tenant_id="default_tenant",
            agent_id=None,
            session_id=session_id,
            name=name,
            type=type,
            content=content,
            metadata_json={"k": "v"},
            author_id="u-72",
        )

    def test_list_artifacts_all(self, client, memory_db):
        memory_db.add_all([
            self._artifact("art-1"),
            self._artifact("art-2", type="markdown", name="notes.md"),
        ])
        memory_db.commit()
        resp = client.get("/api/artifacts/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] in ("script.py", "notes.md")
        assert data[0]["version"] == 1
        assert data[0]["is_locked"] is False
        assert data[0]["author_id"] == "u-72"
        assert data[0]["created_at"] is not None

    def test_list_artifacts_filter_session(self, client, memory_db):
        memory_db.add_all([
            self._artifact("art-1", session_id="sess-1"),
            self._artifact("art-2", session_id="sess-2"),
        ])
        memory_db.commit()
        resp = client.get("/api/artifacts/?session_id=sess-1")
        assert resp.status_code == 200
        assert [a["id"] for a in resp.json()] == ["art-1"]

    def test_list_artifacts_filter_type(self, client, memory_db):
        memory_db.add_all([
            self._artifact("art-1", type="code"),
            self._artifact("art-2", type="markdown"),
        ])
        memory_db.commit()
        resp = client.get("/api/artifacts/?type=markdown")
        assert resp.status_code == 200
        assert [a["id"] for a in resp.json()] == ["art-2"]

    def test_list_artifacts_both_filters(self, client, memory_db):
        memory_db.add_all([
            self._artifact("art-1", session_id="sess-1", type="code"),
            self._artifact("art-2", session_id="sess-1", type="markdown"),
        ])
        memory_db.commit()
        resp = client.get("/api/artifacts/?session_id=sess-1&type=code")
        assert resp.status_code == 200
        assert [a["id"] for a in resp.json()] == ["art-1"]

    def test_list_artifacts_empty(self, client):
        resp = client.get("/api/artifacts/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_save_artifact(self, client, memory_db):
        resp = client.post("/api/artifacts/", json={
            "name": "hello.py", "type": "code", "content": "print('hi')",
            "metadata_json": {"lang": "python"}, "session_id": "sess-1",
            "agent_id": "agent-1",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "hello.py"
        assert body["id"]
        assert body["version"] == 1
        assert body["author_id"] == "u-72"
        assert body["metadata_json"] == {"lang": "python"}
        saved = memory_db.get(
            __import__("core.models", fromlist=["Artifact"]).Artifact, body["id"])
        assert saved is not None
        assert saved.workspace_id == "default"

    def test_save_artifact_no_metadata(self, client, memory_db):
        resp = client.post("/api/artifacts/", json={
            "name": "x.py", "type": "code", "content": "x",
        })
        assert resp.status_code == 200
        assert resp.json()["metadata_json"] == {}
        assert resp.json()["session_id"] is None

    def test_save_artifact_validation(self, client):
        resp = client.post("/api/artifacts/", json={"name": "x"})
        assert resp.status_code == 422

    def test_update_artifact_full(self, client, memory_db):
        from core.models import ArtifactVersion
        memory_db.add(self._artifact())
        memory_db.commit()
        resp = client.post("/api/artifacts/update", json={
            "id": "art-1", "name": "renamed.py", "content": "print(2)",
            "metadata_json": {"k": "w"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "renamed.py"
        assert body["content"] == "print(2)"
        assert body["metadata_json"] == {"k": "w"}
        assert body["version"] == 2
        versions = memory_db.query(ArtifactVersion).filter(
            ArtifactVersion.artifact_id == "art-1").all()
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].content == "print(1)"
        assert versions[0].author_id == "u-72"

    def test_update_artifact_partial(self, client, memory_db):
        memory_db.add(self._artifact())
        memory_db.commit()
        resp = client.post("/api/artifacts/update", json={"id": "art-1", "name": "only-name.py"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "only-name.py"
        assert body["content"] == "print(1)"
        assert body["version"] == 2

    def test_update_artifact_content_only(self, client, memory_db):
        memory_db.add(self._artifact())
        memory_db.commit()
        resp = client.post("/api/artifacts/update", json={"id": "art-1", "content": "print(3)"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "print(3)"

    def test_update_artifact_metadata_only(self, client, memory_db):
        memory_db.add(self._artifact())
        memory_db.commit()
        resp = client.post("/api/artifacts/update", json={
            "id": "art-1", "metadata_json": {"only": "meta"},
        })
        assert resp.status_code == 200
        assert resp.json()["metadata_json"] == {"only": "meta"}

    def test_update_artifact_not_found(self, client):
        resp = client.post("/api/artifacts/update", json={"id": "missing"})
        assert resp.status_code == 404

    def test_update_artifact_validation(self, client):
        resp = client.post("/api/artifacts/update", json={})
        assert resp.status_code == 422

    def test_get_artifact_versions(self, client, memory_db):
        from core.models import ArtifactVersion
        memory_db.add(self._artifact())
        memory_db.add_all([
            ArtifactVersion(id="v1", artifact_id="art-1", version=1,
                            content="v1", author_id="u-72"),
            ArtifactVersion(id="v2", artifact_id="art-1", version=2,
                            content="v2", author_id="u-72"),
        ])
        memory_db.commit()
        resp = client.get("/api/artifacts/art-1/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert [v["version"] for v in versions] == [2, 1]
        assert versions[0]["content"] == "v2"

    def test_get_artifact_versions_empty(self, client):
        resp = client.get("/api/artifacts/art-1/versions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self, memory_db):
        from api.artifact_routes import router
        client = make_client(router, overrides={get_db: db_override(memory_db)})
        assert client.get("/api/artifacts/").status_code == 401
        assert client.post("/api/artifacts/", json={
            "name": "x", "type": "code", "content": "x",
        }).status_code == 401
        assert client.get("/api/artifacts/art-1/versions").status_code == 401
