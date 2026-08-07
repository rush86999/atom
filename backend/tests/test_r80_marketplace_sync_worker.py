# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/marketplace_sync_worker.py.

Covers instance auto-registration (existing + new + failure), the analytics
sync pipeline (disabled flag, no records, push success updating
last_reported_at / last_sync_at, SaaS rejection, exception), and the
run_sync entry point. The SaaS client is fully mocked.
"""
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from core.marketplace_sync_worker import AnalyticsSyncWorker, run_sync


@pytest.fixture()
def db(monkeypatch):
    """Function-scoped in-memory SQLite with the marketplace tables, and
    SessionLocal patched so the worker's default session hits it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import MarketplaceInstance, MarketplaceUsage

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        bind=engine,
        tables=[MarketplaceInstance.__table__, MarketplaceUsage.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    # marketplace_sync_worker does `from core.database import SessionLocal` —
    # patch the module-level name, not the core.database attribute.
    monkeypatch.setattr("core.marketplace_sync_worker.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def enable_analytics(monkeypatch):
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")


def _instance(db, saas_id="saas-1"):
    from core.models import MarketplaceInstance

    inst = MarketplaceInstance(saas_instance_id=saas_id, registration_token="tok",
                               status="active")
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def _usage(db, item_type="skill", item_id="skill-1", executions=5, successes=4, duration=1234.5):
    from core.models import MarketplaceUsage

    rec = MarketplaceUsage(item_type=item_type, item_id=item_id,
                           execution_count=executions, success_count=successes,
                           total_duration_ms=duration)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _client(register_result=None, push_result=None):
    client = MagicMock()
    client.register_instance_sync.return_value = register_result or {
        "instance_id": "saas-new", "registration_token": "tok-2"
    }
    client.push_analytics_sync.return_value = push_result or {"success": True}
    return client


class TestInstanceRegistration:
    def test_returns_existing_instance(self, db, enable_analytics):
        _instance(db, "saas-1")
        worker = AnalyticsSyncWorker(db=db)
        assert worker._ensure_instance_registered() == "saas-1"

    def test_auto_registers_new_instance(self, db, enable_analytics):
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client()) as mock_cls:
            worker = AnalyticsSyncWorker(db=db)
            saas_id = worker._ensure_instance_registered()
        assert saas_id == "saas-new"
        mock_cls.return_value.register_instance_sync.assert_called_once()
        from core.models import MarketplaceInstance
        row = db.query(MarketplaceInstance).first()
        assert row.saas_instance_id == "saas-new"
        assert row.registration_token == "tok-2"

    def test_failed_registration_returns_none(self, db, enable_analytics):
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client(register_result={"error": "nope"})):
            worker = AnalyticsSyncWorker(db=db)
            assert worker._ensure_instance_registered() is None
        from core.models import MarketplaceInstance
        assert db.query(MarketplaceInstance).count() == 0

    def test_exception_during_registration_returns_none(self, db, enable_analytics):
        client = MagicMock()
        client.register_instance_sync.side_effect = RuntimeError("network down")
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=client):
            worker = AnalyticsSyncWorker(db=db)
            assert worker._ensure_instance_registered() is None


class TestSyncUsage:
    def test_disabled_returns_zero(self, db, monkeypatch):
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        worker = AnalyticsSyncWorker(db=db)
        assert worker.sync_usage() == 0

    def test_no_instance_aborts(self, db, enable_analytics):
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client(register_result={"error": "denied"})):
            worker = AnalyticsSyncWorker(db=db)
            assert worker.sync_usage() == 0

    def test_no_usage_records_returns_zero(self, db, enable_analytics):
        _instance(db, "saas-1")
        worker = AnalyticsSyncWorker(db=db)
        assert worker.sync_usage() == 0

    def test_push_success_updates_timestamps(self, db, enable_analytics):
        _instance(db, "saas-1")
        rec = _usage(db)
        # The worker must be constructed INSIDE the patch: __init__ instantiates
        # the (real) SaaS client itself.
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client()) as mock_cls:
            worker = AnalyticsSyncWorker(db=db)
            count = worker.sync_usage()
        assert count == 1
        db.refresh(rec)
        assert rec.last_reported_at is not None
        from core.models import MarketplaceInstance
        inst = db.query(MarketplaceInstance).first()
        assert inst.last_sync_at is not None
        push = mock_cls.return_value.push_analytics_sync
        assert push.call_args.kwargs["instance_id"] == "saas-1"
        reports = push.call_args.kwargs["reports"]
        assert reports[0]["item_type"] == "skill"
        assert reports[0]["execution_count"] == 5
        assert reports[0]["success_count"] == 4
        assert reports[0]["total_duration_ms"] == 1234.5

    def test_multiple_records_all_synced(self, db, enable_analytics):
        _instance(db, "saas-1")
        _usage(db, "skill", "s1")
        _usage(db, "agent", "a1")
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client()) as mock_cls:
            worker = AnalyticsSyncWorker(db=db)
            assert worker.sync_usage() == 2
        assert mock_cls.return_value.push_analytics_sync.call_count == 1

    def test_saas_rejection_returns_zero_and_keeps_timestamps(self, db, enable_analytics):
        _instance(db, "saas-1")
        rec = _usage(db)
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client(push_result={"success": False, "error": "quota"})):
            worker = AnalyticsSyncWorker(db=db)
            assert worker.sync_usage() == 0
        db.refresh(rec)
        assert rec.last_reported_at is None

    def test_exception_during_push_returns_zero(self, db, enable_analytics):
        _instance(db, "saas-1")
        _usage(db)
        client = MagicMock()
        client.push_analytics_sync.side_effect = RuntimeError("timeout")
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=client):
            worker = AnalyticsSyncWorker(db=db)
            assert worker.sync_usage() == 0


class TestEntryPoint:
    def test_run_sync_disabled(self, monkeypatch, capsys):
        monkeypatch.setenv("ANALYTICS_ENABLED", "false")
        with patch("core.marketplace_sync_worker.SessionLocal") as _:
            run_sync()
        out = capsys.readouterr().out
        assert "Synced 0 marketplace usage records." in out

    def test_run_sync_uses_own_session(self, monkeypatch, capsys):
        monkeypatch.setenv("ANALYTICS_ENABLED", "true")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.database import Base
        from core.models import MarketplaceInstance, MarketplaceUsage

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine,
                                 tables=[MarketplaceInstance.__table__, MarketplaceUsage.__table__])
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr("core.marketplace_sync_worker.SessionLocal", factory)
        db = factory()
        db.add(MarketplaceInstance(saas_instance_id="saas-1", status="active"))
        db.commit()
        db.close()
        with patch("core.marketplace_sync_worker.AtomAgentOSMarketplaceClient",
                   return_value=_client()):
            run_sync()
        out = capsys.readouterr().out
        assert "Synced 0 marketplace usage records." in out
        engine.dispose()
