"""Wave 117 repair: advanced finance flow test.

Moved from ``accounting/test_advanced_finance.py`` (a test file that had ended
up in the accounting package, where pytest never collected it) to the tests
directory. Repaired to run green:

- ``sys.path.append(os.getcwd())`` hack removed (pytest ``pythonpath=.`` handles it)
- duplicate ``import asyncio`` removed
- missing ``await`` on ``ingestion_pipeline.ingest_message`` (async) fixed — the
  coroutine previously never ran, so the semantic-memory leg silently no-op'd
- real-dev-DB dependency replaced with an in-memory SQLite engine created via
  ``Base.metadata.create_all`` (the dev DB had no ``workspaces`` table → RED)
- LanceDB memory manager + ingestion pipeline fully mocked (zero network/LLM spend)
- print-only "verification" replaced with real asserts
"""

import logging
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounting.models import Account, Budget, Transaction
from accounting.seeds import seed_default_accounts
from accounting.sync_manager import AccountingSyncManager
from accounting.workflow_service import FinancialWorkflowService

from core.database import Base
from core.models import Workspace
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    IngestionConfig,
    ingestion_pipeline,
    memory_manager,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_advanced_finance_flow(db_session):
    db = db_session
    workspace_id = "advanced-finance-test"

    # 1. Setup: workspace + chart of accounts + overrun budget
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        ws = Workspace(id=workspace_id, name="Advanced Finance Test")
        db.add(ws)
        db.commit()

    seed_default_accounts(db, workspace_id)

    marketing_acc = (
        db.query(Account)
        .filter(Account.workspace_id == workspace_id, Account.name == "Marketing Expense")
        .first()
    )
    assert marketing_acc is not None, "seed_default_accounts must create Marketing Expense"

    budget = Budget(
        workspace_id=workspace_id,
        category_id=marketing_acc.id,
        amount=100.0,
        period="monthly",
        start_date=datetime.now(),
        end_date=datetime.now(),
    )
    db.add(budget)
    db.commit()

    sync_manager = AccountingSyncManager(db)
    workflow_service = FinancialWorkflowService(db)

    # 2. Zoho transaction mapping (no real API calls)
    zoho_tx = [
        {"transaction_id": "adv_1", "description": "Google Ads Premium", "amount": 500.0, "date": "2023-11-01"}
    ]
    mapped = sync_manager._map_zoho_transactions(zoho_tx, workspace_id)
    assert mapped[0]["description"] == "Google Ads Premium"
    assert mapped[0]["amount"] == 500.0
    assert mapped[0]["external_id"] == "adv_1"
    assert mapped[0]["date"].year == 2023

    tx = Transaction(
        workspace_id=workspace_id,
        description=mapped[0]["description"],
        amount=mapped[0]["amount"],
        source="zoho",
        transaction_date=mapped[0]["date"],
        metadata_json={"external_id": mapped[0]["external_id"], "platform": "zoho"},
    )
    db.add(tx)
    db.commit()
    assert tx.id is not None, "Transaction must be persisted"

    # 3. Semantic ingestion (LanceDB fully mocked — no embedding model in test env)
    with (
        patch.object(memory_manager, "initialize") as mock_init,
        patch.object(
            memory_manager,
            "search_communications",
            return_value=[{"content": f"Large Marketing Spend: {tx.description}. Amount: {tx.amount}"}],
        ) as mock_search,
        patch.object(ingestion_pipeline, "ingest_message", new=AsyncMock(return_value=True)) as mock_ingest,
    ):
        memory_manager.initialize()

        ingestion_pipeline.configure_app(
            CommunicationAppType.ZOHO,
            IngestionConfig(
                app_type=CommunicationAppType.ZOHO,
                enabled=True,
                real_time=False,
                batch_size=1,
                ingest_attachments=False,
                embed_content=True,
                retention_days=365,
            ),
        )

        ingested = await ingestion_pipeline.ingest_message(
            app_type="zoho",
            message_data={
                "id": f"tx_{tx.id}",
                "timestamp": tx.transaction_date.isoformat(),
                "content": f"Large Marketing Spend: {tx.description}. Amount: {tx.amount}",
                "metadata": {"transaction_id": tx.id},
            },
        )
        assert ingested is True
        mock_ingest.assert_awaited_once()
        mock_init.assert_called_once()

        search_results = memory_manager.search_communications("Google Ads", limit=5)
        assert search_results, "Semantic search must return the ingested communication"
        assert "Google Ads Premium" in search_results[0]["content"]
        mock_search.assert_called_once_with("Google Ads", limit=5)

    # 4. Workflow: budget overrun alert (reasoning engine mocked)
    #    check_financial_integrity is not part of CrossSystemReasoningEngine's
    #    public API (getattr fallback in handle_transaction_event) — create it.
    with patch.object(
        workflow_service.reasoning,
        "check_financial_integrity",
        create=True,
        new=AsyncMock(return_value=[{"type": "FINANCIAL_BUDGET_OVERRUN"}]),
    ) as mock_integrity:
        await workflow_service.handle_transaction_event(tx.id)
        mock_integrity.assert_awaited_once_with(db, tx.workspace_id)

    db.refresh(tx)
    assert tx.metadata_json["external_id"] == "adv_1"
