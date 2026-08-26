"""R87 RED tests — trust-calibration certification statistics + record path.

Two findings:

1. certify() temporal split used max(70% cut, n - MIN_EVAL), which pins the
   holdout at EXACTLY MIN_EVAL=8 rows for any dataset >= 27 rows. The
   load-bearing P2 statistic (Brier / denial-coverage -> resolved enforce)
   never gained reliability with volume: 100 rows and 400 rows both
   certified on the same 8-sample holdout. The floor term belongs under min()
   so holdout = max(MIN_EVAL, 30%).

2. gateway.assess_and_record() swallowed commit failures WITHOUT rollback.
   Callers pass their ambient request session (HITL ask-paths); after a
   failed flush/commit SQLAlchemy requires rollback before any further use,
   so the next ORM operation on that session raises PendingRollbackError —
   breaking exactly the ask-path the method promises to never break.
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, exc, text
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.trust_calibration.certify import ResolvedDecision, certify


def _rows(n):
    rows = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        good = i % 2 == 0
        p, y = (0.9, 1) if good else (0.1, 0)
        rows.append(ResolvedDecision(
            p_approve=p, y=y,
            decided_at=now - timedelta(days=(n - i)),
            features_json={"tool": [p, p, p], "ctx": [0.5]},
        ))
    return rows


def test_holdout_grows_with_dataset():
    """100 resolved decisions must evaluate on ~30%, not a pinned 8."""
    result = certify(_rows(100))
    assert result.n_train + result.n_eval == 100
    assert result.n_eval >= 25, (
        f"holdout pinned at {result.n_eval}; expected ~30% of 100"
    )


def test_holdout_keeps_min_eval_floor_on_small_data():
    """Small datasets still reserve at least MIN_EVAL=8 for evaluation."""
    result = certify(_rows(30))
    assert result.n_eval >= 8
    assert result.n_train >= 20


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _enabled(monkeypatch):
    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")


def test_assess_and_record_rolls_back_after_commit_failure(monkeypatch, db):
    """A transient DB failure during shadow recording must leave the shared
    session usable — no PendingRollbackError on the caller's next ORM op."""
    import core.models as models_mod
    from core.models import TrustCalibrationAssessment
    from core.trust_calibration.gateway import TrustCalibrationGateway

    _enabled(monkeypatch)
    gw = TrustCalibrationGateway(db=None)

    # Pre-seed the PK the pinned insert will collide with, so the failure is
    # a genuine IntegrityError raised INSIDE db.commit() (not an injected
    # exception), which marks the SQLAlchemy session pending-rollback.
    db.add(TrustCalibrationAssessment(
        id="pinned-collision", action_type="seed", platform="internal",
        features_json={"tool": [0.0], "ctx": [0.5]}, p_approve=0.5,
        uncertainty=0.1, recommendation="ask", source_path="seed",
    ))
    db.commit()

    class PinnedAssessment(TrustCalibrationAssessment):
        def __init__(self, *a, **k):
            k.pop("id", None)
            super().__init__(*a, **k)
            self.id = "pinned-collision"

    monkeypatch.setattr(models_mod, "TrustCalibrationAssessment", PinnedAssessment)

    rollback_calls = []
    real_rollback = db.rollback

    def spy_rollback():
        rollback_calls.append(1)
        return real_rollback()

    db.rollback = spy_rollback
    res = gw.assess_and_record(
        db, action_type="send_email", platform="gmail", agent_id="agent-1"
    )
    db.rollback = real_rollback

    assert res is None  # swallowed, as designed
    assert rollback_calls, (
        "assess_and_record must roll back the shared session after a failed "
        "commit; otherwise the caller's next ORM op raises PendingRollbackError"
    )

    # Session must remain usable for the ambient request flow.
    db.execute(text("SELECT 1"))
