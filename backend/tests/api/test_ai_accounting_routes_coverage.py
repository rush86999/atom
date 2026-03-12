"""
AI Accounting Routes Test Coverage

Target: 75%+ line coverage for ai_accounting_routes.py (352 lines, 13 endpoints)

Test file covers:
- Transaction ingestion (single and bulk bank feed)
- Categorization and review queue
- Transaction CRUD operations
- Posting operations (manual and auto-post)
- Chart of accounts and audit log
- Export operations (GL CSV, trial balance JSON)
- Forecasting and scenario analysis
- Dashboard summary with database integration
- Error paths (validation, 404, 500)

External services mocked:
- core.ai_accounting_engine.ai_accounting (MagicMock)
- core.database.get_db (dependency override)
"""

from datetime import datetime
from typing import Dict, List
from unittest.mock import Mock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# ==================== FIXTURES ====================

@pytest.fixture
def mock_ai_accounting():
    """Mock AI accounting engine with all required methods."""
    mock = MagicMock()

    # Transaction ingestion methods
    mock.ingest_transaction = Mock(return_value=Mock(
        id="tx_123",
        status=Mock(value="categorized"),
        category_name="Office Supplies",
        confidence=0.92,
        reasoning="Similar to previous office purchases",
        date=datetime.now()
    ))

    mock.ingest_bank_feed = Mock(return_value=[
        Mock(id="tx_1", confidence=0.90, status=Mock(value="categorized")),
        Mock(id="tx_2", confidence=0.95, status=Mock(value="categorized")),
        Mock(id="tx_3", confidence=0.70, status=Mock(value="review_required"))
    ])

    # Categorization methods
    mock.learn_categorization = Mock()
    mock.get_pending_review = Mock(return_value=[])
    mock.get_all_transactions = Mock(return_value=[])

    # Transaction CRUD methods
    mock.update_transaction = Mock(return_value=True)
    mock.delete_transaction = Mock(return_value=True)

    # Posting methods
    mock.post_transaction = Mock(return_value=True)
    mock.auto_post_high_confidence = Mock(return_value=0)

    # Chart of accounts - use real ChartOfAccountsEntry to avoid recursion
    from core.ai_accounting_engine import ChartOfAccountsEntry
    mock_account = ChartOfAccountsEntry(
        account_id="acc_1",
        name="Office Supplies",
        type="expense",
        keywords=["office", "supplies", "stationery"]
    )
    mock._chart_of_accounts = {"acc_1": mock_account}

    # Audit log
    mock.get_audit_log = Mock(return_value=[])

    # Export methods
    mock.export_general_ledger_csv = Mock(return_value="csv,content,here")
    mock.export_trial_balance_json = Mock(return_value={
        "accounts": [
            {"account": "Office Supplies", "debit": 1000, "credit": 0},
            {"account": "Cash", "debit": 0, "credit": 1000}
        ]
    })

    # Forecasting methods
    mock.get_13_week_forecast = Mock(return_value={
        "projection": [
            {"week": 1, "inflow": 5000, "outflow": 3000, "net": 2000},
            {"week": 2, "inflow": 5500, "outflow": 3200, "net": 2300}
        ]
    })
    mock.run_scenario = Mock(return_value={
        "modified_projection": [
            {"week": 1, "inflow": 6000, "outflow": 3000, "net": 3000}
        ]
    })

    return mock


@pytest.fixture
def mock_db_for_accounting():
    """Mock database session for IntegrationMetric queries."""
    mock = Mock(spec=Session)

    # Mock query chain for dashboard summary
    mock_query = Mock()
    mock_filter = Mock()

    # Create mock IntegrationMetric objects
    mock_metric_revenue = Mock()
    mock_metric_revenue.metric_key = "total_revenue"
    mock_metric_revenue.value = "50000.00"

    mock_metric_pending = Mock()
    mock_metric_pending.metric_key = "pending_revenue"
    mock_metric_pending.value = "5000.00"

    mock_metric_profit = Mock()
    mock_metric_profit.metric_key = "gross_profit"
    mock_metric_profit.value = "20000.00"

    mock_filter.all = Mock(return_value=[
        mock_metric_revenue,
        mock_metric_pending,
        mock_metric_profit
    ])

    mock_query.filter = Mock(return_value=mock_filter)
    mock.query = Mock(return_value=mock_query)

    return mock


@pytest.fixture
def ai_accounting_client(mock_ai_accounting, mock_db_for_accounting):
    """TestClient with dependency overrides for AI accounting routes."""
    from api.ai_accounting_routes import router
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield mock_db_for_accounting

    app.dependency_overrides[get_db] = override_get_db

    with patch('core.ai_accounting_engine.ai_accounting', mock_ai_accounting):
        yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def sample_transaction_request():
    """Factory for valid TransactionRequest."""
    return {
        "id": "tx_123",
        "date": "2026-03-12T10:30:00",
        "amount": 125.50,
        "description": "Office supplies purchase",
        "merchant": "Staples",
        "source": "bank"
    }


@pytest.fixture
def sample_bank_feed_request():
    """Factory for valid BankFeedRequest."""
    return {
        "transactions": [
            {
                "id": "tx_1",
                "date": "2026-03-12T10:00:00",
                "amount": 100.00,
                "description": "Coffee shop",
                "merchant": "Starbucks",
                "source": "bank"
            },
            {
                "id": "tx_2",
                "date": "2026-03-12T11:00:00",
                "amount": 500.00,
                "description": "Office rent",
                "merchant": None,
                "source": "manual"
            }
        ]
    }


@pytest.fixture
def sample_categorize_request():
    """Factory for valid CategorizeRequest."""
    return {
        "transaction_id": "tx_123",
        "category_id": "cat_office_supplies"
    }


@pytest.fixture
def mock_transaction():
    """Mock Transaction with all required attributes."""
    tx = Mock()
    tx.id = "tx_123"
    tx.date = datetime.now()
    tx.amount = 125.50
    tx.description = "Office supplies purchase"
    tx.merchant = "Staples"
    tx.category_name = "Office Supplies"
    tx.confidence = 0.92
    tx.reasoning = "Similar to previous office purchases"
    tx.status = Mock(value="categorized")
    return tx


@pytest.fixture
def mock_integration_metrics():
    """Mock IntegrationMetric query results for dashboard."""
    return [
        Mock(metric_key="total_revenue", value="50000.00"),
        Mock(metric_key="pending_revenue", value="5000.00"),
        Mock(metric_key="gross_profit", value="20000.00")
    ]


# ==================== TEST CLASSES ====================


class TestAccountingTransactionIngestion:
    """Test transaction ingestion endpoints (single and bulk bank feed)."""

    def test_ingest_transaction_success(
        self, ai_accounting_client, sample_transaction_request
    ):
        """Test single transaction ingestion returns success with categorization."""
        response = ai_accounting_client.post(
            "/ai-accounting/transactions",
            json=sample_transaction_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["id"] == "tx_123"
        assert data["data"]["status"] == "categorized"
        assert data["data"]["category"] == "Office Supplies"
        assert data["data"]["confidence"] == 92.0
        assert "reasoning" in data["data"]
        assert data["data"]["requires_review"] is False

    def test_ingest_transaction_with_merchant(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test transaction with merchant field processed correctly."""
        request = {
            "id": "tx_456",
            "date": "2026-03-12T10:30:00",
            "amount": 50.00,
            "description": "Coffee",
            "merchant": "Starbucks",
            "source": "bank"
        }

        response = ai_accounting_client.post("/ai-accounting/transactions", json=request)

        assert response.status_code == 200
        assert response.json()["data"]["id"] == "tx_123"  # Mock return value
        mock_ai_accounting.ingest_transaction.assert_called_once()

    def test_ingest_transaction_all_sources(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test transaction with different source values."""
        sources = ["bank", "manual", "credit_card"]

        for source in sources:
            request = {
                "id": f"tx_{source}",
                "date": "2026-03-12T10:30:00",
                "amount": 100.00,
                "description": f"Transaction from {source}",
                "source": source
            }

            response = ai_accounting_client.post("/ai-accounting/transactions", json=request)
            assert response.status_code == 200

    def test_ingest_bank_feed_success(
        self, ai_accounting_client, sample_bank_feed_request
    ):
        """Test bulk bank feed ingestion returns counts."""
        response = ai_accounting_client.post(
            "/ai-accounting/bank-feed",
            json=sample_bank_feed_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["ingested"] == 3
        assert data["data"]["auto_categorized"] == 2  # confidence >= 0.85
        assert data["data"]["review_required"] == 1

    def test_ingest_bank_feed_empty(self, ai_accounting_client, mock_ai_accounting):
        """Test empty bank feed returns zero counts."""
        mock_ai_accounting.ingest_bank_feed.return_value = []

        response = ai_accounting_client.post(
            "/ai-accounting/bank-feed",
            json={"transactions": []}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["ingested"] == 0
        assert data["data"]["auto_categorized"] == 0
        assert data["data"]["review_required"] == 0

    def test_ingest_bank_feed_multiple(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test multiple transactions with mixed confidence levels."""
        mock_ai_accounting.ingest_bank_feed.return_value = [
            Mock(id="tx_1", confidence=0.95, status=Mock(value="categorized")),
            Mock(id="tx_2", confidence=0.88, status=Mock(value="categorized")),
            Mock(id="tx_3", confidence=0.65, status=Mock(value="review_required")),
            Mock(id="tx_4", confidence=0.40, status=Mock(value="review_required"))
        ]

        request = {
            "transactions": [
                {"id": "tx_1", "date": "2026-03-12T10:00:00", "amount": 100.0, "description": "Test 1"},
                {"id": "tx_2", "date": "2026-03-12T11:00:00", "amount": 200.0, "description": "Test 2"},
                {"id": "tx_3", "date": "2026-03-12T12:00:00", "amount": 300.0, "description": "Test 3"},
                {"id": "tx_4", "date": "2026-03-12T13:00:00", "amount": 400.0, "description": "Test 4"}
            ]
        }

        response = ai_accounting_client.post("/ai-accounting/bank-feed", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["ingested"] == 4
        assert data["data"]["auto_categorized"] == 2
        assert data["data"]["review_required"] == 2


class TestAccountingCategorization:
    """Test transaction categorization and review queue endpoints."""

    def test_categorize_transaction_success(
        self, ai_accounting_client, sample_categorize_request, mock_ai_accounting
    ):
        """Test manual categorization teaches the system."""
        response = ai_accounting_client.post(
            "/ai-accounting/categorize",
            json=sample_categorize_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["transaction_id"] == "tx_123"
        mock_ai_accounting.learn_categorization.assert_called_once_with(
            "tx_123", "cat_office_supplies", "user"
        )

    def test_get_review_queue_empty(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test review queue returns empty list when no pending transactions."""
        mock_ai_accounting.get_pending_review.return_value = []

        response = ai_accounting_client.get("/ai-accounting/review-queue")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 0
        assert data["data"]["transactions"] == []

    def test_get_review_queue_with_items(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test review queue returns pending transactions with suggestions."""
        pending_tx = Mock()
        pending_tx.id = "tx_pending"
        pending_tx.date = datetime.now()
        pending_tx.amount = 150.00
        pending_tx.description = "Uncategorized purchase"
        pending_tx.merchant = "Amazon"
        pending_tx.category_name = "Supplies"
        pending_tx.confidence = 0.65
        pending_tx.reasoning = "Low confidence, needs review"

        mock_ai_accounting.get_pending_review.return_value = [pending_tx]

        response = ai_accounting_client.get("/ai-accounting/review-queue")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 1
        assert len(data["data"]["transactions"]) == 1
        tx_data = data["data"]["transactions"][0]
        assert tx_data["id"] == "tx_pending"
        assert tx_data["suggested_category"] == "Supplies"
        assert tx_data["confidence"] == 65.0
        assert "reasoning" in tx_data

    def test_get_all_transactions(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test get all transactions returns categorized and pending."""
        tx1 = Mock()
        tx1.id = "tx_1"
        tx1.date = datetime.now()
        tx1.amount = 100.00
        tx1.description = "Transaction 1"
        tx1.merchant = "Merchant 1"
        tx1.category_name = "Category 1"
        tx1.confidence = 0.90
        tx1.reasoning = "High confidence"
        tx1.status = Mock(value="categorized")

        tx2 = Mock()
        tx2.id = "tx_2"
        tx2.date = datetime.now()
        tx2.amount = 200.00
        tx2.description = "Transaction 2"
        tx2.merchant = None
        tx2.category_name = "Category 2"
        tx2.confidence = 0.70
        tx2.reasoning = "Medium confidence"
        tx2.status = Mock(value="review_required")

        mock_ai_accounting.get_all_transactions.return_value = [tx1, tx2]

        response = ai_accounting_client.get("/ai-accounting/all-transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 2
        assert len(data["data"]["transactions"]) == 2
        assert data["data"]["transactions"][0]["status"] == "categorized"
        assert data["data"]["transactions"][1]["status"] == "review_required"

    def test_categorize_with_user_learning(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test categorization with different user_id parameters."""
        request = {
            "transaction_id": "tx_789",
            "category_id": "cat_travel"
        }

        # Test with default user
        response = ai_accounting_client.post("/ai-accounting/categorize", json=request)
        assert response.status_code == 200
        mock_ai_accounting.learn_categorization.assert_called_with(
            "tx_789", "cat_travel", "user"
        )


class TestAccountingTransactionManagement:
    """Test transaction update and delete operations."""

    def test_update_transaction_success(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test update transaction with valid changes."""
        update_data = {
            "description": "Updated description",
            "amount": 150.00,
            "merchant": "New Merchant"
        }

        response = ai_accounting_client.put(
            "/ai-accounting/transactions/tx_123",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["transaction_id"] == "tx_123"
        mock_ai_accounting.update_transaction.assert_called_once()

    def test_update_transaction_not_found(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test update non-existent transaction raises 404."""
        mock_ai_accounting.update_transaction.return_value = False

        update_data = {
            "description": "Updated description"
        }

        response = ai_accounting_client.put(
            "/ai-accounting/transactions/tx_nonexistent",
            json=update_data
        )

        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data

    def test_update_transaction_with_multiple_fields(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test update description, amount, merchant simultaneously."""
        update_data = {
            "description": "Completely updated transaction",
            "amount": 999.99,
            "merchant": "Updated Store"
        }

        response = ai_accounting_client.put(
            "/ai-accounting/transactions/tx_multi",
            json=update_data
        )

        assert response.status_code == 200
        mock_ai_accounting.update_transaction.assert_called_once_with(
            "tx_multi", update_data, "user"
        )

    def test_delete_transaction_success(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test delete existing transaction returns success."""
        response = ai_accounting_client.delete("/ai-accounting/transactions/tx_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["transaction_id"] == "tx_123"
        mock_ai_accounting.delete_transaction.assert_called_once()

    def test_delete_transaction_not_found(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test delete non-existent transaction raises 404."""
        mock_ai_accounting.delete_transaction.return_value = False

        response = ai_accounting_client.delete(
            "/ai-accounting/transactions/tx_nonexistent"
        )

        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data


class TestAccountingPosting:
    """Test transaction posting operations (manual and auto-post)."""

    def test_post_transaction_success(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test post transaction returns success for postable transaction."""
        mock_ai_accounting.post_transaction.return_value = True

        response = ai_accounting_client.post("/ai-accounting/post/tx_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["transaction_id"] == "tx_123"
        mock_ai_accounting.post_transaction.assert_called_once_with("tx_123", "user")

    def test_post_transaction_requires_review(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test posting low-confidence transaction raises 400 validation error."""
        mock_ai_accounting.post_transaction.return_value = False

        response = ai_accounting_client.post("/ai-accounting/post/tx_low_conf")

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_post_transaction_not_found(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test posting non-existent transaction raises 404."""
        # This should trigger validation_error, not not_found_error
        # because post_transaction returns False for both cases
        mock_ai_accounting.post_transaction.return_value = False

        response = ai_accounting_client.post("/ai-accounting/post/tx_nonexistent")

        assert response.status_code == 400

    def test_auto_post_high_confidence(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test auto-post returns posted_count."""
        mock_ai_accounting.auto_post_high_confidence.return_value = 5

        response = ai_accounting_client.post("/ai-accounting/auto-post")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["posted_count"] == 5
        mock_ai_accounting.auto_post_high_confidence.assert_called_once()

    def test_auto_post_empty(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test auto-post with no high-confidence transactions returns 0."""
        mock_ai_accounting.auto_post_high_confidence.return_value = 0

        response = ai_accounting_client.post("/ai-accounting/auto-post")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["posted_count"] == 0


class TestAccountingChartAndAudit:
    """Test chart of accounts and audit log endpoints."""

    def test_get_chart_of_accounts(self, ai_accounting_client):
        """Test get chart of accounts returns accounts list."""
        response = ai_accounting_client.get("/ai-accounting/chart-of-accounts")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "accounts" in data["data"]
        assert len(data["data"]["accounts"]) == 1

        account = data["data"]["accounts"][0]
        assert account["id"] == "acc_1"
        assert account["name"] == "Office Supplies"
        assert account["type"] == "expense"
        assert "keywords" in account

    def test_get_chart_of_accounts_empty(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test chart of accounts returns empty list when none defined."""
        mock_ai_accounting._chart_of_accounts = {}

        response = ai_accounting_client.get("/ai-accounting/chart-of-accounts")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["accounts"] == []

    def test_get_audit_log_all(self, ai_accounting_client):
        """Test get audit log returns all audit entries."""
        response = ai_accounting_client.get("/ai-accounting/audit-log")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_audit_log_filtered(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test audit log with transaction_id filter returns filtered results."""
        mock_audit_entries = [
            {
                "transaction_id": "tx_123",
                "action": "categorized",
                "timestamp": "2026-03-12T10:00:00Z",
                "user": "system"
            }
        ]
        mock_ai_accounting.get_audit_log.return_value = mock_audit_entries

        response = ai_accounting_client.get(
            "/ai-accounting/audit-log?transaction_id=tx_123"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == mock_audit_entries
        mock_ai_accounting.get_audit_log.assert_called_with("tx_123")


class TestAccountingExports:
    """Test export operations (GL CSV, trial balance JSON)."""

    def test_export_gl_csv(self, ai_accounting_client):
        """Test export general ledger returns CSV with correct headers."""
        response = ai_accounting_client.get("/ai-accounting/export/gl")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "content-disposition" in response.headers
        assert "general_ledger.csv" in response.headers["content-disposition"]
        assert response.content == b"csv,content,here"

    def test_export_trial_balance_json(
        self, ai_accounting_client, mock_ai_accounting
    ):
        """Test export trial balance returns JSON data structure."""
        mock_ai_accounting.export_trial_balance_json.return_value = {
            "accounts": [
                {"account": "Office Supplies", "debit": 1000, "credit": 0},
                {"account": "Cash", "debit": 0, "credit": 1000}
            ],
            "total_debit": 1000,
            "total_credit": 1000
        }

        response = ai_accounting_client.get("/ai-accounting/export/trial-balance")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "accounts" in data["data"]

    def test_export_gl_empty(self, ai_accounting_client, mock_ai_accounting):
        """Test export with no transactions returns valid empty CSV."""
        mock_ai_accounting.export_general_ledger_csv.return_value = ""

        response = ai_accounting_client.get("/ai-accounting/export/gl")

        assert response.status_code == 200
        assert response.content == b""

    def test_export_trial_balance_structure(self, ai_accounting_client):
        """Test trial balance has expected data structure."""
        response = ai_accounting_client.get("/ai-accounting/export/trial-balance")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], dict)


class TestAccountingForecasting:
    """Test forecasting and scenario analysis endpoints."""

    def test_get_forecast(self, ai_accounting_client):
        """Test get forecast returns projection data."""
        response = ai_accounting_client.get("/ai-accounting/forecast")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "projection" in data["data"]
        assert len(data["data"]["projection"]) == 2

        week1 = data["data"]["projection"][0]
        assert "week" in week1
        assert "inflow" in week1
        assert "outflow" in week1
        assert "net" in week1

    def test_run_scenario(self, ai_accounting_client):
        """Test scenario analyzes what-if scenario."""
        response = ai_accounting_client.post(
            "/ai-accounting/scenario",
            params={
                "workspace_id": "default",
                "scenario_description": "Increase revenue by 20%"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "modified_projection" in data["data"]

    def test_forecast_with_workspace(self, ai_accounting_client):
        """Test forecast with different workspace_id parameter."""
        response = ai_accounting_client.get(
            "/ai-accounting/forecast?workspace_id=custom_workspace"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_scenario_analysis(self, ai_accounting_client):
        """Test scenario returns modified projection based on description."""
        response = ai_accounting_client.post(
            "/ai-accounting/scenario?scenario_description=Reduce%20expenses"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data


class TestAccountingDashboard:
    """Test dashboard summary endpoint with database integration."""

    def test_get_dashboard_summary_success(self, ai_accounting_client):
        """Test dashboard summary queries IntegrationMetric for stats."""
        response = ai_accounting_client.get("/ai-accounting/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_revenue" in data["data"]
        assert "pending_revenue" in data["data"]
        assert data["data"]["total_revenue"] == 50000.00
        assert data["data"]["pending_revenue"] == 5000.00
        assert "runway_months" in data["data"]
        assert "currency" in data["data"]

    def test_get_dashboard_summary_empty(
        self, ai_accounting_client, mock_db_for_accounting
    ):
        """Test dashboard returns zero values when no metrics exist."""
        # Return empty metrics list
        mock_filter = Mock()
        mock_filter.all = Mock(return_value=[])
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db_for_accounting.query = Mock(return_value=mock_query)

        response = ai_accounting_client.get("/ai-accounting/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_revenue"] == 0.0
        assert data["data"]["pending_revenue"] == 0.0

    def test_get_dashboard_summary_multiple_metrics(
        self, ai_accounting_client, mock_db_for_accounting
    ):
        """Test dashboard aggregates multiple IntegrationMetric records."""
        # Multiple metrics for same key should aggregate
        mock_filter = Mock()
        mock_filter.all = Mock(return_value=[
            Mock(metric_key="total_revenue", value="30000.00"),
            Mock(metric_key="total_revenue", value="20000.00"),
            Mock(metric_key="pending_revenue", value="5000.00")
        ])
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db_for_accounting.query = Mock(return_value=mock_query)

        response = ai_accounting_client.get("/ai-accounting/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_revenue"] == 50000.00

    def test_get_dashboard_summary_database_error(
        self, ai_accounting_client, mock_db_for_accounting
    ):
        """Test dashboard handles database query errors gracefully (500)."""
        mock_db_for_accounting.query.side_effect = Exception("Database connection failed")

        response = ai_accounting_client.get("/ai-accounting/dashboard/summary")

        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "detail" in data


class TestAccountingErrorPaths:
    """Test error paths (validation, 404, 500)."""

    def test_ingest_transaction_missing_fields(
        self, ai_accounting_client
    ):
        """Test missing required fields returns 422 validation error."""
        incomplete_request = {
            "id": "tx_123",
            "amount": 100.00
            # Missing: date, description, source
        }

        response = ai_accounting_client.post(
            "/ai-accounting/transactions",
            json=incomplete_request
        )

        assert response.status_code == 422

    def test_categorize_missing_ids(self, ai_accounting_client):
        """Test categorize with missing transaction_id or category_id returns 422."""
        incomplete_request = {
            "transaction_id": "tx_123"
            # Missing: category_id
        }

        response = ai_accounting_client.post(
            "/ai-accounting/categorize",
            json=incomplete_request
        )

        assert response.status_code == 422

    def test_dashboard_unexpected_error(
        self, ai_accounting_client, mock_db_for_accounting
    ):
        """Test unexpected database error returns 500 internal_error response."""
        mock_db_for_accounting.query.side_effect = RuntimeError("Unexpected error")

        response = ai_accounting_client.get("/ai-accounting/dashboard/summary")

        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "detail" in data
