# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/marketing_agent.py.

TDD targets:
- Both ``MarketingAgent.trigger_review_request`` and
  ``RetentionEngine.scan_for_rebooking_opportunities`` used
  ``db = self.db or get_db_session()`` — with no injected session that is a
  context manager, not a Session, so the no-session path crashed with
  ``AttributeError: '_GeneratorContextManager' object has no attribute
  'close'`` (and a query would have raised 'query' instead).
- Customer-not-found must return an error dict, not raise.
"""
import asyncio

import pytest

from core.marketing_agent import MarketingAgent, RetentionEngine


@pytest.fixture()
def db(monkeypatch):
    """Function-scoped in-memory SQLite with the needed tables, and
    SessionLocal patched so the service's get_db_session() hits it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import EcommerceCustomer, Tenant

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        bind=engine,
        tables=[Tenant.__table__, EcommerceCustomer.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    # marketing_agent does `from core.database import SessionLocal` — patch the
    # module-level name, not the core.database attribute.
    monkeypatch.setattr("core.marketing_agent.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _tenant(session, tid="t-1"):
    from core.models import Tenant

    session.add(Tenant(id=tid, name="T", subdomain=tid))
    session.commit()


def _customer(session, cid="c-1", tid="t-1"):
    from core.models import EcommerceCustomer

    customer = EcommerceCustomer(id=cid, tenant_id=tid, email="c@example.com")
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


class TestTriggerReviewRequest:
    def test_positive_sentiment_drafts_public_review_request(self, db):
        _tenant(db)
        _customer(db)
        result = asyncio.run(MarketingAgent(db_session=db).trigger_review_request("c-1", "w-1"))
        assert result["status"] == "success"
        assert "c-1" in result["message"]
        assert "review" in result["message"].lower()
        assert result["target"] == "sms/email"

    def test_unknown_customer_returns_error(self, db):
        _tenant(db)
        result = asyncio.run(MarketingAgent(db_session=db).trigger_review_request("ghost", "w-1"))
        assert result == {"status": "error", "message": "Customer not found"}

    def test_customer_isolation(self, db):
        _tenant(db, "t-1")
        _tenant(db, "t-2")
        _customer(db, "c-1", "t-1")
        result = asyncio.run(MarketingAgent(db_session=db).trigger_review_request("ghost-2", "w-1"))
        assert result["status"] == "error"

    def test_works_without_injected_session(self, monkeypatch):
        """RED: no-session path used get_db_session()'s context manager as a
        Session and crashed."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.database import Base
        from core.models import EcommerceCustomer, Tenant

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine, tables=[Tenant.__table__, EcommerceCustomer.__table__])
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr("core.marketing_agent.SessionLocal", factory)
        db = factory()
        _tenant(db)
        _customer(db)
        db.close()

        result = asyncio.run(MarketingAgent().trigger_review_request("c-1", "w-1"))
        assert result["status"] == "success"
        engine.dispose()


class TestRetentionEngine:
    def test_scan_returns_empty_opportunities(self, db):
        result = asyncio.run(RetentionEngine(db_session=db).scan_for_rebooking_opportunities("w-1"))
        assert result == []

    def test_scan_without_injected_session(self, monkeypatch):
        """RED: same context-manager-as-Session bug in RetentionEngine."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.database import Base
        from core.models import Tenant

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine, tables=[Tenant.__table__])
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr("core.marketing_agent.SessionLocal", factory)
        db = factory()
        _tenant(db)
        db.close()

        result = asyncio.run(RetentionEngine().scan_for_rebooking_opportunities("w-1"))
        assert result == []
        engine.dispose()
