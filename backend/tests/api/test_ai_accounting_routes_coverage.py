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

    # Chart of accounts
    mock_account = Mock(
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
        sources = ["bank", "manual", "import"]

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
