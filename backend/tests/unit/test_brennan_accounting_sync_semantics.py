"""Accounting sync semantics against a real scratch SQLite database.

The legacy mapper converted provider amounts to floats, defaulted missing
dates to now, and looked for duplicates with a JSON substring match.  These
controls use the real ``Transaction`` table so the exact identity query is
exercised, not a fake that ignores filters.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounting.models import Transaction
from accounting.sync_manager import AccountingSyncManager
from core.database import Base
from core.models import Workspace


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@contextmanager
def _manager(db, zoho_rows):
    zoho = MagicMock()
    zoho.get_bank_transactions = AsyncMock(return_value=zoho_rows)
    categorizer = MagicMock()
    pipeline = MagicMock()
    pipeline.ingest_message = AsyncMock(return_value=None)
    with patch("accounting.sync_manager.ZohoBooksService", return_value=zoho), \
         patch("accounting.sync_manager.XeroService", return_value=MagicMock()), \
         patch("accounting.sync_manager.QuickBooksService", return_value=MagicMock()), \
         patch("accounting.sync_manager.AICategorizer", return_value=categorizer), \
         patch("accounting.sync_manager.ingestion_pipeline", pipeline):
        yield AccountingSyncManager(db), pipeline


def _credentials():
    return {"access_token": "t", "organization_id": "org-1"}


def test_exact_external_id_duplicate_and_substring_neighbour(db_session):
    db_session.add(Workspace(id="ws-sync", name="Sync Test"))
    db_session.commit()

    with _manager(db_session, [
        {"transaction_id": "z1", "amount": "12.50", "date": "2026-01-05"},
        {"transaction_id": "z10", "amount": "99.99", "date": "2026-01-06"},
        {"transaction_id": "z1", "amount": "12.50", "date": "2026-01-05"},
    ]) as (manager, _pipeline):
        first = asyncio.run(manager.sync_external_transactions(
            "ws-sync", "zoho", _credentials()))
        # z1 and z10 are both new; "z1" must not match "z10".
        assert first["status"] == "success"
        assert first["ingested"] == 2
        rows = db_session.query(Transaction).order_by(
            Transaction.external_id).all()
        assert [row.external_id for row in rows] == ["z1", "z10"]
        assert all(row.source == "zoho" for row in rows)
        assert rows[0].amount == Decimal("12.5")

        # The boundary record from the next page is the exact same z1.
        second = asyncio.run(manager.sync_external_transactions(
            "ws-sync", "zoho", _credentials()))
        assert second["ingested"] == 0
        assert db_session.query(Transaction).count() == 2


def test_missing_date_creates_no_local_transaction(db_session):
    db_session.add(Workspace(id="ws-sync", name="Sync Test"))
    db_session.commit()

    with _manager(db_session, [
        {"transaction_id": "z2", "amount": "5.00"},
    ]) as (manager, _pipeline):
        result = asyncio.run(manager.sync_external_transactions(
            "ws-sync", "zoho", _credentials()))

    assert result["status"] == "failed"
    assert result["ingested"] == 0
    assert result["mapping_errors"][0]["field"] == "date"
    assert db_session.query(Transaction).count() == 0


def test_partial_sync_reports_semantic_ingestion_gap(db_session):
    db_session.add(Workspace(id="ws-sync", name="Sync Test"))
    db_session.commit()

    with _manager(db_session, [
        {"transaction_id": "z3", "amount": "7.25", "date": "2026-02-01"},
    ]) as (manager, pipeline):
        pipeline.ingest_message = AsyncMock(side_effect=RuntimeError("index down"))
        result = asyncio.run(manager.sync_external_transactions(
            "ws-sync", "zoho", _credentials()))

    assert result["status"] == "partial"
    assert result["ingested"] == 1
    assert result["ingestion_errors"][0]["external_id"] == "z3"
    assert db_session.query(Transaction).count() == 1
