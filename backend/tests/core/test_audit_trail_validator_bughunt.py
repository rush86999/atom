"""
Bug-hunt tests for core/audit_trail_validator.py (TDD).

Uses a self-contained in-memory SQLite database (no external fixtures) so the
tests are isolated and fast. Each test documents a genuine, net-new bug.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, FinancialAudit, FinancialAccount, User, Tenant
from core.audit_trail_validator import AuditTrailValidator


# ==================== ISOLATED DB FIXTURE ====================

@pytest.fixture
def db():
    """Fresh in-memory SQLite DB with the full schema, one session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_account(db, account_id="acct-1"):
    """Create the prerequisite Tenant + User + FinancialAccount rows."""
    tenant = Tenant(id="t1", name="T", subdomain="t1")
    db.add(tenant)
    db.flush()
    user = User(id="u1", email="u@example.com", first_name="U", last_name="S",
                role="member", status="active", tenant_id="t1")
    db.add(user)
    db.flush()
    acct = FinancialAccount(
        id=account_id, tenant_id="t1", name="A", account_type="checking",
        balance=0.0, currency="USD", is_active=True, status="active",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(acct)
    db.commit()
    return acct


def _make_audit(db, account_id="acct-1", seq=1, record_id="r1",
                operation_type="INSERT", timestamp=None):
    aud = FinancialAudit(
        id=str(uuid.uuid4()),
        sequence_number=seq,
        account_id=account_id,
        operation_type=operation_type,
        table_name="FinancialAccount",
        record_id=record_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        hash_chain="deadbeef",
    )
    db.add(aud)
    db.commit()
    return aud


# ==================== BUG TESTS ====================

class TestAuditTrailValidatorBugs:
    """Net-new bugs in audit_trail_validator."""

    def test_get_audit_statistics_does_not_crash_on_action_type(self, db):
        """BUG: get_audit_statistics (line 249) reads `audit.action_type`, but
        FinancialAudit has no `action_type` column (it is `operation_type`).
        Any non-empty audit table raises AttributeError, breaking SOX
        statistics reporting entirely.
        """
        _make_account(db)
        _make_audit(db, operation_type="INSERT")
        v = AuditTrailValidator(db)
        # Must not raise AttributeError. NOTE: creating the FinancialAccount
        # above auto-audits it via the after_flush listener (a 'create' entry),
        # so the table holds 2 entries: the auto 'create' + our manual INSERT.
        stats = v.get_audit_statistics()
        assert stats["total_audits"] == 2
        assert stats["by_action_type"]["INSERT"] == 1
        assert stats["by_action_type"]["create"] == 1

    def test_get_audit_statistics_success_rate_does_not_crash(self, db):
        """BUG: get_audit_statistics (line 254) reads `audit.success`, but
        FinancialAudit has no `success` column. AttributeError on any audit.
        """
        _make_account(db)
        _make_audit(db, operation_type="INSERT")
        _make_audit(db, operation_type="UPDATE", seq=2, record_id="r2")
        v = AuditTrailValidator(db)
        stats = v.get_audit_statistics()
        assert "success_rate" in stats
        assert isinstance(stats["success_rate"], float)

    def test_validate_completeness_with_model_name_filter_does_not_crash(self, db):
        """BUG: validate_completeness (line 79) filters on
        `FinancialAudit.action_type == model_name`, but the column is
        `operation_type`. Passing model_name raises AttributeError, so the
        public model-name filter API is unusable.
        """
        _make_account(db)
        _make_audit(db, operation_type="INSERT")
        v = AuditTrailValidator(db)
        # Must not raise when filtering by model_name
        result = v.validate_completeness(model_name="INSERT")
        assert "complete" in result
        assert "coverage_percentage" in result
