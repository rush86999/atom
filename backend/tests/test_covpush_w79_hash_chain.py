# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/hash_chain_integrity.py to 100%.

- _to_canonical_json: key sorting, None/hash_chain filtering, datetime
  isoformat, nested dict/list canonicalization.
- compute_entry_hash: determinism, prev_hash/seq/timestamp sensitivity,
  aware-vs-naive timestamp equality (SQLite round-trip normalization).
- verify_chain: empty / single-valid / single-None-prev (BUG 79-1: None
  previous_hash falsely flagged as tampering) / first-entry-prev non-empty /
  valid 3-chain / content tamper (hash_mismatch) / link tamper
  (prev_hash_mismatch) / start+end sequence range filters / multi-break count.
- detect_tampering: clean scan, tampered accounts + details, limit_accounts.
- get_chain_status: empty / valid / tampered.
- recompute_hash: missing entry, with-previous recompute (unchanged hash),
  first-entry recompute (prev=''), commit + warning log.

Real DB (in-memory SQLite + full schema), zero LLM spend, no network.
"""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, FinancialAudit
from core.hash_chain_integrity import HashChainIntegrity


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _entry(db, seq, *, account_id="acct-1", action="create", prev_hash="",
           hash_chain=None, old=None, new=None, timestamp=None, audit_id=None,
           user_id="u1"):
    """Insert a FinancialAudit row. When hash_chain is None a placeholder is
    used; callers fix it up via compute_entry_hash for valid chains."""
    e = FinancialAudit(
        id=audit_id or f"aud-{account_id}-{seq}",
        sequence_number=seq,
        account_id=account_id,
        operation_type=action,
        table_name="FinancialAccount",
        record_id=f"r{seq}",
        old_values=old,
        new_values=new,
        user_id=user_id,
        agent_maturity="SUPERVISED",
        hash_chain=hash_chain or ("0" * 64),
        previous_hash=prev_hash,
        timestamp=timestamp or datetime(2026, 8, 1, 12, 0, 0) + timedelta(minutes=seq),
    )
    db.add(e)
    db.commit()
    return e


def _chain(db, account_id="acct-1", n=3, start=1):
    """Build a cryptographically valid chain of n entries."""
    prev = ""
    created = []
    for i in range(start, start + n):
        ts = datetime(2026, 8, 1, 12, 0, 0) + timedelta(minutes=i)
        h = HashChainIntegrity.compute_entry_hash(
            account_id=account_id, action_type="create",
            old_values=None, new_values={"v": i},
            timestamp=ts, sequence_number=i, prev_hash=prev, user_id="u1")
        created.append(_entry(
            db, i, account_id=account_id, prev_hash=prev, hash_chain=h,
            new={"v": i}, timestamp=ts))
        prev = h
    return created


# ============================================================================
# _to_canonical_json / compute_entry_hash
# ============================================================================

class TestCanonicalJson:
    def test_sorted_keys_and_separators(self):
        out = HashChainIntegrity._to_canonical_json({"b": 2, "a": 1})
        assert out == '{"a":1,"b":2}'

    def test_filters_none_and_hash_chain_key(self):
        out = HashChainIntegrity._to_canonical_json(
            {"a": None, "b": 1, "hash_chain": "should-be-dropped"})
        assert out == '{"b":1}'

    def test_datetime_converted_to_iso(self):
        ts = datetime(2026, 1, 1, 10, 30, 0)
        out = HashChainIntegrity._to_canonical_json({"ts": ts})
        assert out == '{"ts":"2026-01-01T10:30:00"}'

    def test_nested_dict_and_list_canonicalized(self):
        out = HashChainIntegrity._to_canonical_json(
            {"nested": {"z": 1, "a": [2, 1]}, "lst": [3, 1, 2]})
        # json.dumps(sort_keys=True) default separators for nested structures
        assert '"nested":"{\\"a\\": [2, 1], \\"z\\": 1}"' in out

    def test_previous_hash_is_kept(self):
        out = HashChainIntegrity._to_canonical_json({"previous_hash": "abc"})
        assert "previous_hash" in out


class TestComputeEntryHash:
    def test_deterministic(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        a = HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 1, "", "u1")
        b = HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 1, "", "u1")
        assert a == b
        assert len(a) == 64

    def test_changes_with_prev_hash(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        a = HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 1, "", "u1")
        b = HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 1, "deadbeef", "u1")
        assert a != b

    def test_changes_with_sequence_and_content(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        base = HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 1, "", "u1")
        assert base != HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 2}, ts, 1, "", "u1")
        assert base != HashChainIntegrity.compute_entry_hash("a1", "create", None, {"x": 1}, ts, 2, "", "u1")

    def test_aware_and_naive_timestamps_hash_equally(self):
        # SQLite strips tzinfo on round-trip; the service normalizes aware
        # timestamps to naive wall-clock UTC so insert-time == verify-time.
        aware = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
        naive = datetime(2026, 8, 1, 12, 0, 0)
        a = HashChainIntegrity.compute_entry_hash("a1", "create", None, {}, aware, 1, "", "u1")
        b = HashChainIntegrity.compute_entry_hash("a1", "create", None, {}, naive, 1, "", "u1")
        assert a == b

    def test_none_old_new_values_allowed(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert len(HashChainIntegrity.compute_entry_hash(
            "a1", "delete", None, None, ts, 1, "", "u1")) == 64


# ============================================================================
# verify_chain
# ============================================================================

class TestVerifyChain:
    def test_no_entries_is_valid(self, db):
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is True
        assert result["total_entries"] == 0
        assert result["break_count"] == 0

    def test_single_valid_entry(self, db):
        ts = datetime(2026, 8, 1, 12, 0, 0)
        h = HashChainIntegrity.compute_entry_hash(
            "acct-1", "create", None, {"v": 1}, ts, 1, "", "u1")
        _entry(db, 1, hash_chain=h, new={"v": 1}, timestamp=ts)
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is True
        assert result["total_entries"] == 1
        assert result["break_count"] == 0

    def test_first_entry_none_prev_hash_is_valid(self, db):
        """BUG 79-1: previous_hash defaults to NULL on the column, but
        verify_chain only accepted '' as 'no previous' — a legitimately
        created first entry was flagged `first_entry_has_prev_hash`."""
        ts = datetime(2026, 8, 1, 12, 0, 0)
        h = HashChainIntegrity.compute_entry_hash(
            "acct-1", "create", None, {"v": 1}, ts, 1, "", "u1")
        _entry(db, 1, prev_hash=None, hash_chain=h, new={"v": 1}, timestamp=ts)
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is True
        assert result["break_count"] == 0

    def test_first_entry_with_nonempty_prev_is_break(self, db):
        # Attacker-appended first entry: valid hash computed over a forged
        # prev_hash — only the first-entry check can catch it.
        ts = datetime(2026, 8, 1, 12, 0, 0)
        forged_prev = "a" * 64
        h = HashChainIntegrity.compute_entry_hash(
            "acct-1", "create", None, {"v": 1}, ts, 1, forged_prev, "u1")
        _entry(db, 1, prev_hash=forged_prev, hash_chain=h, new={"v": 1}, timestamp=ts)
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is False
        assert result["break_count"] == 1
        assert result["first_break"]["issue"] == "first_entry_has_prev_hash"
        assert result["first_break"]["expected_prev_hash"] == ""

    def test_first_entry_content_tamper_detected(self, db):
        """BUG 79-11: verify_chain never recomputed the FIRST entry's hash
        (the loop started at index 1), so tampering the first audit entry's
        content was completely undetectable."""
        _chain(db, n=2)
        victim = db.query(FinancialAudit).filter(
            FinancialAudit.sequence_number == 1).first()
        victim.new_values = {"v": 999}
        db.commit()
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is False
        assert result["break_count"] == 1
        assert result["first_break"]["sequence_number"] == 1
        assert result["first_break"]["issue"] == "hash_mismatch"

    def test_valid_three_entry_chain(self, db):
        _chain(db, n=3)
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is True
        assert result["total_entries"] == 3
        assert result["break_count"] == 0

    def test_content_tamper_detected_as_hash_mismatch(self, db):
        _chain(db, n=3)
        # Tamper with the middle entry's stored values
        middle = db.query(FinancialAudit).filter(
            FinancialAudit.sequence_number == 2).first()
        middle.new_values = {"v": 999}
        db.commit()
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is False
        assert result["break_count"] == 1
        assert result["first_break"]["sequence_number"] == 2
        assert result["first_break"]["issue"] == "hash_mismatch"
        assert result["first_break"]["expected_hash"] != result["first_break"]["actual_hash"]

    def test_link_tamper_detected_as_prev_hash_mismatch(self, db):
        entries = _chain(db, n=3)
        # Attacker rewrites entry 3's link AND recomputes its own hash over the
        # forged link (so its hash matches) — only the link check catches this.
        entry3 = entries[2]
        forged = "f" * 64
        entry3.previous_hash = forged
        entry3.hash_chain = HashChainIntegrity.compute_entry_hash(
            account_id=entry3.account_id,
            action_type=entry3.operation_type,
            old_values=entry3.old_values,
            new_values=entry3.new_values,
            timestamp=entry3.timestamp,
            sequence_number=entry3.sequence_number,
            prev_hash=forged,
            user_id=entry3.user_id,
        )
        db.commit()
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["is_valid"] is False
        assert result["break_count"] == 1
        assert result["first_break"]["issue"] == "prev_hash_mismatch"
        assert result["first_break"]["expected_prev_hash"] == entries[1].hash_chain

    def test_sequence_range_filters(self, db):
        _chain(db, n=5)
        result = HashChainIntegrity(db).verify_chain("acct-1", start_sequence=2, end_sequence=4)
        assert result["total_entries"] == 3
        # BUG 79-10: a range starting mid-chain was falsely flagged because the
        # range's first entry legitimately has a non-empty previous_hash.
        assert result["is_valid"] is True

    def test_sequence_range_filters_only_start(self, db):
        _chain(db, n=5)
        result = HashChainIntegrity(db).verify_chain("acct-1", start_sequence=4)
        assert result["total_entries"] == 2
        assert result["is_valid"] is True
    def test_multiple_breaks_counted(self, db):
        _chain(db, n=3)
        for seq in (1, 3):
            e = db.query(FinancialAudit).filter(
                FinancialAudit.sequence_number == seq).first()
            e.new_values = {"v": -1}
            db.commit()
        result = HashChainIntegrity(db).verify_chain("acct-1")
        assert result["break_count"] == 2
        assert result["is_valid"] is False


# ============================================================================
# detect_tampering / get_chain_status / recompute_hash
# ============================================================================

class TestDetectTampering:
    def test_clean_scan(self, db):
        _chain(db, "acct-1", n=2)
        _chain(db, "acct-2", n=2)
        result = HashChainIntegrity(db).detect_tampering()
        assert result["accounts_checked"] == 2
        assert result["tampered_accounts"] == []
        assert result["total_breaks"] == 0

    def test_tampered_accounts_detected_with_details(self, db):
        _chain(db, "acct-1", n=2)
        _chain(db, "acct-2", n=2)
        victim = db.query(FinancialAudit).filter(
            FinancialAudit.account_id == "acct-2",
            FinancialAudit.sequence_number == 1).first()
        victim.new_values = {"v": 999}
        db.commit()
        result = HashChainIntegrity(db).detect_tampering()
        assert result["tampered_accounts"] == ["acct-2"]
        assert result["total_breaks"] == 1
        assert "acct-2" in result["details"]
        assert result["details"]["acct-2"]["is_valid"] is False

    def test_limit_accounts(self, db):
        _chain(db, "acct-1", n=2)
        _chain(db, "acct-2", n=2)
        _chain(db, "acct-3", n=2)
        result = HashChainIntegrity(db).detect_tampering(limit_accounts=2)
        assert result["accounts_checked"] == 2

    def test_no_accounts(self, db):
        result = HashChainIntegrity(db).detect_tampering()
        assert result["accounts_checked"] == 0
        assert result["tampered_accounts"] == []


class TestGetChainStatus:
    def test_empty_chain(self, db):
        result = HashChainIntegrity(db).get_chain_status("acct-1")
        assert result["status"] == "empty"
        assert result["chain_length"] == 0
        assert result["first_entry"] is None

    def test_valid_chain(self, db):
        entries = _chain(db, n=2)
        result = HashChainIntegrity(db).get_chain_status("acct-1")
        assert result["status"] == "valid"
        assert result["is_valid"] is True
        assert result["chain_length"] == 2
        assert result["first_entry"]["hash"] == entries[0].hash_chain
        assert result["last_entry"]["hash"] == entries[1].hash_chain

    def test_tampered_chain(self, db):
        _chain(db, n=2)
        victim = db.query(FinancialAudit).filter(
            FinancialAudit.sequence_number == 1).first()
        victim.new_values = {"v": -5}
        db.commit()
        result = HashChainIntegrity(db).get_chain_status("acct-1")
        assert result["status"] == "tampered"
        assert result["is_valid"] is False
        assert result["breaks"] >= 1


class TestRecomputeHash:
    def test_missing_entry_returns_error(self, db):
        result = HashChainIntegrity(db).recompute_hash("nope")
        assert result == {"error": "Audit entry not found"}

    def test_recompute_with_previous(self, db, caplog):
        entries = _chain(db, n=3)
        target = entries[1]
        with caplog.at_level(logging.WARNING, logger="core.hash_chain_integrity"):
            result = HashChainIntegrity(db).recompute_hash(target.id)
        assert result["audit_id"] == target.id
        assert result["old_hash"] == target.hash_chain
        assert result["hash_changed"] is False
        db.refresh(target)
        assert target.hash_chain == result["new_hash"]
        assert "Recomputed hash" in caplog.text

    def test_recompute_first_entry_uses_empty_prev(self, db):
        entries = _chain(db, n=2)
        target = entries[0]
        result = HashChainIntegrity(db).recompute_hash(target.id)
        assert result["hash_changed"] is False
        assert result["new_hash"] == target.hash_chain

    def test_recompute_repairs_broken_hash(self, db):
        entries = _chain(db, n=2)
        target = entries[1]
        target.new_values = {"v": 42}
        db.commit()
        # verify_chain now reports a break
        assert HashChainIntegrity(db).verify_chain("acct-1")["is_valid"] is False
        result = HashChainIntegrity(db).recompute_hash(target.id)
        assert result["hash_changed"] is True
        assert HashChainIntegrity(db).verify_chain("acct-1")["is_valid"] is True
