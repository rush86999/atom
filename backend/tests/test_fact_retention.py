"""
PII retention / right-to-erasure for turn facts (rev.2 plan #2 completion).

RED: no retention sweep or user-purge exists — facts persist indefinitely,
which rev.2 flags as a compliance gap (GDPR Art. 17 tension vs audit trail).

Contracts pinned here:
  - apply_retention_policy(workspace_id): invalidates ACTIVE facts older than
    the cutoff (env TURN_FACT_RETENTION_DAYS, default 0 = disabled) —
    anonymizes fact_text to "[erased per retention policy]", clears tags,
    flips status to "invalidated" (excluded from recall; row preserved for
    the audit trail).
  - purge_user_facts(workspace_id, user_id): right-to-erasure for one user.
    soft (default) = anonymize + invalidate; hard=True = DELETE rows.
    Other users' facts untouched.
  - both never raise; disabled/unknown workspaces return zeroed reports.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import TurnFact


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _fact(db, *, user_id="u1", text="Dana Whitfield processes invoices",
          age_days=0, status="active"):
    row = TurnFact(
        workspace_id="ws-1",
        extraction_source="turn",
        fact_text=text,
        category="exact_value",
        confidence=0.9,
        content_hash=f"h-{text}-{user_id}-{age_days}-{status}",
        status=status,
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
        user_id=user_id,
    )
    db.add(row)
    db.commit()
    return row


def _ctx(session):
    class _C:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return _C()


class TestRetentionPolicy:
    def test_disabled_by_default_noop(self, db):
        _fact(db, age_days=400)
        from core.memory_consolidator import apply_retention_policy

        with patch.dict("os.environ", {}, clear=False):
            import os

            env = dict(os.environ)
            env.pop("TURN_FACT_RETENTION_DAYS", None)
            with patch.dict("os.environ", env, clear=True):
                report = apply_retention_policy("ws-1", db=db)
        assert report["disabled"] is True
        assert report["invalidated"] == 0
        # fact untouched
        assert db.query(TurnFact).filter(
            TurnFact.status == "active").count() == 1

    def test_old_facts_invalidated_and_anonymized(self, db):
        _fact(db, age_days=400, text="Dana Whitfield processes invoices")
        _fact(db, age_days=1, text="fresh fact stays")
        from core.memory_consolidator import apply_retention_policy

        report = apply_retention_policy("ws-1", retention_days=90, db=db)
        assert report["invalidated"] == 1

        old = db.query(TurnFact).filter(
            TurnFact.status == "invalidated").one()
        new = db.query(TurnFact).filter(
            TurnFact.fact_text == "fresh fact stays").one()
        assert old.fact_text == "[erased per retention policy]"
        assert new.status == "active"

    def test_invalidated_excluded_from_recall(self, db):
        from core.turn_fact_extractor import get_active_facts_for_prompt
        from core.memory_consolidator import apply_retention_policy

        _fact(db, age_days=400, text="ancient payroll detail")
        apply_retention_policy("ws-1", retention_days=90, db=db)
        rows = get_active_facts_for_prompt(db, "ws-1")
        assert rows == []

    def test_env_default_used_when_param_absent(self, db):
        _fact(db, age_days=10)
        from core.memory_consolidator import apply_retention_policy

        with patch.dict("os.environ", {"TURN_FACT_RETENTION_DAYS": "5"}):
            report = apply_retention_policy("ws-1", db=db)
        assert report["invalidated"] == 1


class TestUserErasure:
    def test_soft_purge_anonymizes_and_invalidates(self, db):
        _fact(db, user_id="u-erase", text=" erased user's salary info ")
        _fact(db, user_id="u-other", text="other user keeps their facts")
        from core.memory_consolidator import purge_user_facts

        report = purge_user_facts("ws-1", "u-erase", db=db)
        assert report["purged"] == 1 and report["deleted"] == 0

        erased = db.query(TurnFact).filter(
            TurnFact.user_id == "u-erase").one()
        kept = db.query(TurnFact).filter(
            TurnFact.user_id == "u-other").one()
        assert erased.status == "invalidated"
        assert erased.fact_text == "[erased per retention policy]"
        assert erased.tags is None
        assert kept.status == "active"

    def test_hard_purge_deletes_rows(self, db):
        _fact(db, user_id="u-erase", text="sensitive personal note")
        _fact(db, user_id="u-other", text="untouched")
        from core.memory_consolidator import purge_user_facts

        report = purge_user_facts("ws-1", "u-erase", hard=True, db=db)
        assert report["deleted"] == 1
        assert db.query(TurnFact).filter(
            TurnFact.user_id == "u-erase").count() == 0
        assert db.query(TurnFact).filter(
            TurnFact.user_id == "u-other").count() == 1

    def test_never_raises_on_unknown_user(self, db):
        from core.memory_consolidator import purge_user_facts

        report = purge_user_facts("ws-1", "nobody", db=db)
        assert report["purged"] == 0 and report["deleted"] == 0


class TestWorkerWiring:
    def test_consolidate_workspace_includes_retention(self, db):
        """consolidate_workspace applies the retention policy when enabled."""
        from core.memory_consolidator import consolidate_workspace

        _fact(db, age_days=400, text="stale restricted payroll export")
        with patch("core.database.get_db_session", return_value=_ctx(db)), \
             patch.dict("os.environ", {"TURN_FACT_RETENTION_DAYS": "90"}):
            report = consolidate_workspace("ws-1")
        assert report["facts_expired"] == 1