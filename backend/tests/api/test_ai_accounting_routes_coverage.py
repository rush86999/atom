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
