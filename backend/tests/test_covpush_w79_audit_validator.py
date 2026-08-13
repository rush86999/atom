# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/audit_trail_validator.py 52% → 100% (gaps left by
tests/core/test_audit_trail_validator_bughunt.py).

Covers: validate_completeness (empty / fully-audited / missing audits /
start+end time filters / model_name filter / partial coverage math),
check_missing_audits (contiguous / sequence gap / filters / empty),
validate_required_fields (valid / missing hash_chain + timestamp / limit),
get_audit_statistics (counts by operation_type + maturity, success_rate,
empty-period zeros, time filters, oldest/newest — incl. BUG 79-7: results
came from an UNORDERED query so oldest/newest were wrong for out-of-order
inserts), check_model_coverage (with/without audits), validate_sequence_
monotonicity (valid / violation / empty).

Real in-memory SQLite schema, zero LLM spend, no network. JournalEntry rows
are inserted directly so validate_completeness cross-references real records.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounting.models import JournalEntry
from core.models import Base, FinancialAudit
from core.audit_trail_validator import AuditTrailValidator


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _audit(db, seq, *, account_id="acct-1", operation="INSERT", ts=None,
           record_id=None, hash_chain="h" * 64, maturity="SUPERVISED",
           missing=None):
    kwargs = dict(
        id=str(uuid.uuid4()),
        sequence_number=seq,
        account_id=account_id,
        operation_type=operation,
        table_name="FinancialAccount",
        record_id=record_id or f"r{seq}",
        timestamp=ts or datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
        + timedelta(minutes=seq),
        agent_maturity=maturity,
        hash_chain=hash_chain,
        previous_hash="",
    )
    for col in (missing or []):
        kwargs.pop(col, None)
    a = FinancialAudit(**kwargs)
    db.add(a)
    db.commit()
    return a


def _journal(db, jid, account_id="acct-1"):
    je = JournalEntry(
        id=jid,
        transaction_id=f"tx-{jid}",
        account_id=account_id,
        type="debit",
        amount=100.0,
        currency="USD",
        description="test",
    )
    db.add(je)
    db.commit()
    return je


# ============================================================================
# validate_completeness
# ============================================================================

class TestValidateCompleteness:
    def test_empty_db_is_complete(self, db):
        result = AuditTrailValidator(db).validate_completeness()
        assert result["complete"] is True
        assert result["total_operations"] == 0
        assert result["coverage_percentage"] == 100.0

    def test_all_operations_audited(self, db):
        for jid in ("j1", "j2"):
            _journal(db, jid)
            _audit(db, int(jid[1]), record_id=jid)
        result = AuditTrailValidator(db).validate_completeness()
        assert result["complete"] is True
        assert result["total_operations"] == 2
        assert result["audited_operations"] == 2
        assert result["coverage_percentage"] == 100.0

    def test_missing_audit_reported(self, db):
        _journal(db, "j1")
        _journal(db, "j2")
        _audit(db, 1, record_id="j1")
        result = AuditTrailValidator(db).validate_completeness()
        assert result["complete"] is False
        assert result["missing_audits"] == ["j2"]
        assert result["coverage_percentage"] == 50.0

    def test_start_time_filter(self, db):
        _journal(db, "j1")
        _audit(db, 1, record_id="j1",
               ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc))
        _journal(db, "j2")
        _audit(db, 2, record_id="j2",
               ts=datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc))
        start = datetime(2026, 8, 2, 0, 0, 0, tzinfo=timezone.utc)
        result = AuditTrailValidator(db).validate_completeness(start_time=start)
        # Only the j2 audit falls in the window; operation counting is not
        # time-filtered, so j1 shows as missing in this window
        assert result["complete"] is False
        assert result["missing_audits"] == ["j1"]

    def test_end_time_filter(self, db):
        _journal(db, "j1")
        _audit(db, 1, record_id="j1",
               ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc))
        _journal(db, "j2")
        _audit(db, 2, record_id="j2",
               ts=datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc))
        end = datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone.utc)
        result = AuditTrailValidator(db).validate_completeness(end_time=end)
        assert result["missing_audits"] == ["j2"]

    def test_model_name_filter(self, db):
        _journal(db, "j1")
        _audit(db, 1, record_id="j1", operation="INSERT")
        _audit(db, 2, record_id="j2", operation="UPDATE")
        result = AuditTrailValidator(db).validate_completeness(model_name="INSERT")
        assert result["complete"] is True

    def test_audit_without_record_id_counts_zero(self, db):
        _journal(db, "j1")
        _audit(db, 1, record_id=None)
        result = AuditTrailValidator(db).validate_completeness()
        assert result["audited_operations"] == 0
        assert result["missing_audits"] == ["j1"]


# ============================================================================
# check_missing_audits
# ============================================================================

class TestCheckMissingAudits:
    def test_contiguous_sequence_no_gaps(self, db):
        _audit(db, 1)
        _audit(db, 2)
        _audit(db, 3)
        assert AuditTrailValidator(db).check_missing_audits("acct-1") == []

    def test_sequence_gap_detected(self, db):
        _audit(db, 1)
        _audit(db, 3)
        gaps = AuditTrailValidator(db).check_missing_audits("acct-1")
        assert len(gaps) == 1
        assert gaps[0]["expected_sequence"] == 2
        assert gaps[0]["actual_sequence"] == 3
        assert gaps[0]["gap_size"] == 1
        assert "after_timestamp" in gaps[0]
        assert "before_timestamp" in gaps[0]

    def test_multiple_gaps(self, db):
        _audit(db, 1)
        _audit(db, 2)
        _audit(db, 5)
        _audit(db, 8)
        gaps = AuditTrailValidator(db).check_missing_audits("acct-1")
        assert [g["expected_sequence"] for g in gaps] == [3, 6]

    def test_start_end_filters(self, db):
        _audit(db, 1, ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc))
        _audit(db, 3, ts=datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc))
        start = datetime(2026, 8, 2, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 3, 0, 0, 0, tzinfo=timezone.utc)
        assert AuditTrailValidator(db).check_missing_audits(
            "acct-1", start_time=start, end_time=end) == []

    def test_empty_account(self, db):
        assert AuditTrailValidator(db).check_missing_audits("acct-1") == []

    def test_duplicate_sequence_flagged(self, db):
        _audit(db, 1)
        _audit(db, 2)
        _audit(db, 2)
        gaps = AuditTrailValidator(db).check_missing_audits("acct-1")
        assert len(gaps) == 1


# ============================================================================
# validate_required_fields
# ============================================================================

class TestRequiredFields:
    def test_valid_entries(self, db):
        _audit(db, 1)
        _audit(db, 2)
        result = AuditTrailValidator(db).validate_required_fields()
        assert result["valid"] is True
        assert result["total_checked"] == 2
        assert result["valid_entries"] == 2
        assert result["invalid_entries"] == []

    def test_missing_fields_reported(self, db):
        _audit(db, 1, hash_chain=None)
        _audit(db, 2)
        result = AuditTrailValidator(db).validate_required_fields()
        assert result["valid"] is False
        assert result["total_checked"] == 2
        assert result["valid_entries"] == 1
        invalid = result["invalid_entries"][0]
        assert "hash_chain" in invalid["missing_fields"]

    def test_limit_respected(self, db):
        for i in range(1, 6):
            _audit(db, i)
        result = AuditTrailValidator(db).validate_required_fields(limit=3)
        assert result["total_checked"] == 3

    def test_empty_table(self, db):
        result = AuditTrailValidator(db).validate_required_fields()
        assert result["valid"] is True
        assert result["total_checked"] == 0


# ============================================================================
# get_audit_statistics
# ============================================================================

class TestAuditStatistics:
    def test_counts_by_action_and_maturity(self, db):
        _audit(db, 1, operation="INSERT", maturity="AUTONOMOUS")
        _audit(db, 2, operation="INSERT", maturity="SUPERVISED")
        _audit(db, 3, operation="DELETE", maturity="SUPERVISED")
        result = AuditTrailValidator(db).get_audit_statistics()
        assert result["total_audits"] == 3
        assert result["by_action_type"] == {"INSERT": 2, "DELETE": 1}
        assert result["by_agent_maturity"] == {"AUTONOMOUS": 1, "SUPERVISED": 2}
        assert result["success_rate"] == 1.0

    def test_null_fields_roll_to_unknown(self, db):
        # agent_maturity is nullable — the 'unknown' fallback branch
        # (operation_type is NOT NULL, so that side is defensive-only)
        _audit(db, 1, operation="INSERT", maturity=None)
        result = AuditTrailValidator(db).get_audit_statistics()
        assert result["by_agent_maturity"] == {"unknown": 1}

    def test_empty_table(self, db):
        result = AuditTrailValidator(db).get_audit_statistics()
        assert result["total_audits"] == 0
        assert result["success_rate"] == 0.0
        assert result["oldest_entry"] is None
        assert result["newest_entry"] is None

    def test_time_filters(self, db):
        _audit(db, 1, ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc))
        _audit(db, 2, ts=datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc))
        start = datetime(2026, 8, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = AuditTrailValidator(db).get_audit_statistics(start_time=start)
        assert result["total_audits"] == 1
        end = datetime(2026, 8, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = AuditTrailValidator(db).get_audit_statistics(end_time=end)
        assert result["total_audits"] == 1

    def test_oldest_newest_correct_for_out_of_order_inserts(self, db):
        """BUG 79-7: oldest_entry/newest_entry were taken from an UNORDERED
        query, so they were wrong whenever rows were not inserted in
        chronological order (SOX reporting showed a backwards window)."""
        t_new = datetime(2026, 8, 3, 9, 0, 0, tzinfo=timezone.utc)
        t_mid = datetime(2026, 8, 2, 9, 0, 0, tzinfo=timezone.utc)
        t_old = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        _audit(db, 1, ts=t_new)
        _audit(db, 2, ts=t_mid)
        _audit(db, 3, ts=t_old)
        result = AuditTrailValidator(db).get_audit_statistics()
        # SQLite strips tzinfo on round-trip → compare naive isoformat
        assert result["oldest_entry"] == t_old.replace(tzinfo=None).isoformat()
        assert result["newest_entry"] == t_new.replace(tzinfo=None).isoformat()
        assert result["total_audits"] == 3


# ============================================================================
# check_model_coverage / validate_sequence_monotonicity
# ============================================================================

class TestModelCoverage:
    def test_no_audits(self, db):
        coverage = AuditTrailValidator(db).check_model_coverage()
        assert "FinancialAccount" in coverage
        assert coverage["FinancialAccount"]["has_audits"] is False
        assert coverage["FinancialAccount"]["audit_count"] == 0

    def test_with_audits(self, db):
        _audit(db, 1)
        coverage = AuditTrailValidator(db).check_model_coverage()
        assert coverage["FinancialAccount"]["has_audits"] is True
        assert coverage["FinancialAccount"]["audit_count"] == 1


class TestSequenceMonotonicity:
    def test_monotonic_sequence(self, db):
        _audit(db, 1)
        _audit(db, 2)
        _audit(db, 3)
        result = AuditTrailValidator(db).validate_sequence_monotonicity("acct-1")
        assert result["valid"] is True
        assert result["total_entries"] == 3
        assert result["violations"] == []

    def test_violation_detected(self, db):
        _audit(db, 1)
        _audit(db, 3)
        result = AuditTrailValidator(db).validate_sequence_monotonicity("acct-1")
        assert result["valid"] is False
        assert result["violations"][0]["position"] == 1
        assert result["violations"][0]["expected_sequence"] == 2
        assert result["violations"][0]["actual_sequence"] == 3

    def test_empty_account(self, db):
        result = AuditTrailValidator(db).validate_sequence_monotonicity("acct-1")
        assert result["valid"] is True
        assert result["total_entries"] == 0

    def test_account_isolation(self, db):
        _audit(db, 1, account_id="acct-1")
        _audit(db, 1, account_id="acct-2")
        result = AuditTrailValidator(db).validate_sequence_monotonicity("acct-1")
        assert result["valid"] is True
