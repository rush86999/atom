# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/rating_sync_service (RatingSyncService).

Real in-memory SQLite + a fake AtomSaaSClient (no network, no LLM). Covers the
previously-missing lines 91-92 (invalid rating value), 113-115 (upload
exception), 147 (batch exception results), 173 (mark_as_synced miss),
272-277 (sync success without remote id), 288-290 (sync outer exception),
331-332 (conflict skip: local has no created_at), 347-349 (invalid remote
timestamp), 362-363 (naive timestamp normalization), 397-398 (ConflictLog
commit failure is swallowed).
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    ConflictLog,
    FailedRatingUpload,
    Skill,
    SkillRating,
    Tenant,
    User,
)  # noqa: F401 (register models)
from core.rating_sync_service import RatingSyncService


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


class _FakeSaasClient:
    """Records rate_skill calls; response per rating id via side effects."""

    def __init__(self, responses=None, exc=None):
        self.responses = responses or {}
        self.exc = exc
        self.calls = []
        self.rate_skill = AsyncMock(side_effect=self._respond)

    def _respond(self, skill_id=None, user_id=None, rating=None, comment=None):
        self.calls.append({
            "skill_id": skill_id, "user_id": user_id,
            "rating": rating, "comment": comment,
        })
        if self.exc is not None:
            raise self.exc
        return self.responses.get(skill_id, {"success": True, "id": "remote-1"})


def _make_tenant(db, tenant_id="t1"):
    if db.query(Tenant).filter(Tenant.id == tenant_id).first():
        return db.query(Tenant).get(tenant_id)
    tenant = Tenant(id=tenant_id, subdomain=f"sub-{tenant_id}",
                    name=f"Tenant {tenant_id}")
    db.add(tenant)
    db.flush()
    return tenant


def _make_user(db, user_id="u1", tenant_id="t1"):
    _make_tenant(db, tenant_id)
    if db.query(User).filter(User.id == user_id).first():
        return db.query(User).get(user_id)
    user = User(id=user_id, email=f"{user_id}@example.com",
                tenant_id=tenant_id, role="member", status="active",
                first_name="Test", last_name="User")
    db.add(user)
    db.flush()
    return user


def _make_skill(db, skill_id="s1", tenant_id="t1"):
    _make_tenant(db, tenant_id)
    if db.query(Skill).filter(Skill.id == skill_id).first():
        return db.query(Skill).get(skill_id)
    skill = Skill(id=skill_id, tenant_id=tenant_id, name="Skill",
                  type="function")
    db.add(skill)
    db.flush()
    return skill


def _make_rating(db, rating_id=None, *, rating=5, review="good",
                 skill_id="s1", user_id=None, tenant_id="t1",
                 synced=False, remote_id=None,
                 created_at=None, include_created=True):
    _make_skill(db, skill_id, tenant_id)
    # (skill_id, user_id) is unique — default each rating to its own user.
    if user_id is None:
        user_id = f"u-{rating_id or uuid.uuid4()}"
    _make_user(db, user_id, tenant_id)
    if include_created and created_at is None:
        created_at = datetime.now(timezone.utc) - timedelta(days=1)
    r = SkillRating(
        id=rating_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        skill_id=skill_id,
        user_id=user_id,
        rating=rating,
        review=review,
        synced_to_saas=synced,
        remote_rating_id=remote_id,
        created_at=created_at,
    )
    db.add(r)
    db.commit()
    return r


def _run(awaitable):
    return asyncio.run(awaitable)


def _service(db, client=None):
    return RatingSyncService(db, atom_saas_client=client or _FakeSaasClient())


# ============================================================================
# Pending queries & single uploads
# ============================================================================

class TestPendingAndUpload:
    def test_get_pending_returns_only_unsynced_ordered(self, db):
        r1 = _make_rating(db, rating_id="r1", rating=5)
        _make_rating(db, rating_id="r2", rating=4, synced=True)
        r3 = _make_rating(db, rating_id="r3", rating=3)
        svc = _service(db)
        pending = svc.get_pending_ratings()
        assert [r.id for r in pending] == ["r1", "r3"]

    def test_get_pending_respects_limit(self, db):
        for i in range(5):
            _make_rating(db, rating_id=f"r{i}", rating=5)
        svc = _service(db)
        assert len(svc.get_pending_ratings(limit=2)) == 2

    def test_upload_rating_success_by_id(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        client = _FakeSaasClient({"s1": {"success": True, "id": "remote-9"}})
        svc = _service(db, client)
        result = _run(svc.upload_rating(r))
        assert result == {"success": True, "rating_id": "remote-9"}
        assert client.calls[0]["rating"] == 4
        assert client.calls[0]["comment"] == "good"

    def test_upload_rating_success_via_rating_id_key(self, db):
        r = _make_rating(db, rating_id="r1", rating=5)
        client = _FakeSaasClient({"s1": {"success": True, "rating_id": "rid"}})
        svc = _service(db, client)
        assert _run(svc.upload_rating(r)) == {"success": True, "rating_id": "rid"}

    def test_upload_rating_invalid_values(self, db):
        r_low = _make_rating(db, rating_id="r0", rating=0)
        r_high = _make_rating(db, rating_id="r6", rating=6)
        svc = _service(db)
        assert _run(svc.upload_rating(r_low))["error"] == \
            "Invalid rating value: 0. Must be 1-5"
        assert _run(svc.upload_rating(r_high))["error"] == \
            "Invalid rating value: 6. Must be 1-5"

    def test_upload_rating_update_unsupported(self, db):
        r = _make_rating(db, rating_id="r1", rating=4, remote_id="rem-x")
        svc = _service(db)
        result = _run(svc.upload_rating(r))
        assert result == {"success": False,
                          "error": "Rating updates not yet supported"}

    def test_upload_rating_failure_response_passthrough(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        client = _FakeSaasClient({"s1": {"success": False,
                                         "error": "Rejected by SaaS"}})
        svc = _service(db, client)
        result = _run(svc.upload_rating(r))
        assert result == {"success": False, "error": "Rejected by SaaS"}

    def test_upload_rating_exception_is_caught(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        client = _FakeSaasClient(exc=RuntimeError("boom"))
        svc = _service(db, client)
        result = _run(svc.upload_rating(r))
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_upload_ratings_batch_parallel_with_exception(self, db):
        r1 = _make_rating(db, rating_id="r1", rating=4)
        r2 = _make_rating(db, rating_id="r2", rating=5)
        client = _FakeSaasClient(exc=RuntimeError("network"))
        svc = _service(db, client)
        results = _run(svc.upload_ratings_batch([r1, r2]))
        assert all(res["success"] is False for res in results)
        assert any("network" in res["error"] for res in results)

    def test_upload_ratings_batch_exception_results_collected(self, db):
        r1 = _make_rating(db, rating_id="r1", rating=4)

        async def _explode(rating):
            raise ValueError("inner")

        svc = _service(db)
        with patch.object(svc, "upload_rating", new=_explode):
            results = _run(svc.upload_ratings_batch([r1]))
        assert results == [{
            "success": False, "error": "inner", "rating_id": "r1"}]


# ============================================================================
# Sync state & dead letter queue
# ============================================================================

class TestSyncStateAndDlq:
    def test_mark_as_synced_found(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        svc = _service(db)
        svc.mark_as_synced("r1", "remote-42")
        db.refresh(r)
        assert r.synced_to_saas is True
        assert r.remote_rating_id == "remote-42"
        assert r.synced_at is not None

    def test_mark_as_synced_not_found_warns(self, db):
        svc = _service(db)
        svc.mark_as_synced("missing", "remote-42")  # no raise

    def test_handle_upload_failure_creates_dlq_row(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        svc = _service(db)
        svc.handle_upload_failure(r, "timeout")
        row = db.query(FailedRatingUpload).filter(
            FailedRatingUpload.rating_id == "r1").one()
        assert row.retry_count == 1
        assert row.error_message == "timeout"
        assert row.tenant_id == "t1"

    def test_handle_upload_failure_increments_retry(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        svc = _service(db)
        svc.handle_upload_failure(r, "err1")
        svc.handle_upload_failure(r, "err2")
        rows = db.query(FailedRatingUpload).all()
        assert len(rows) == 1
        assert rows[0].retry_count == 2
        assert rows[0].error_message == "err2"
        assert rows[0].last_retry_at is not None

    def test_sync_ratings_reentrance_guard(self, db):
        svc = _service(db)
        svc._sync_in_progress = True
        result = _run(svc.sync_ratings())
        assert result == {"success": False,
                          "error": "Sync already in progress",
                          "uploaded": 0, "failed": 0, "skipped": 0}

    def test_sync_ratings_empty(self, db):
        svc = _service(db)
        result = _run(svc.sync_ratings())
        assert result["success"] is True
        assert result["message"] == "No pending ratings"

    def test_sync_ratings_uploads_and_marks_synced(self, db):
        _make_rating(db, rating_id="r1", rating=4)
        _make_rating(db, rating_id="r2", rating=5)
        svc = _service(db)
        result = _run(svc.sync_ratings())
        assert result == {"success": True, "uploaded": 2,
                          "failed": 0, "skipped": 0}
        assert db.query(SkillRating).filter(
            SkillRating.synced_to_saas == True).count() == 2  # noqa: E712

    def test_sync_ratings_success_without_remote_id_counts_failed(self, db):
        _make_rating(db, rating_id="r1", rating=4)
        client = _FakeSaasClient({"s1": {"success": True}})  # no id key
        svc = _service(db, client)
        result = _run(svc.sync_ratings())
        assert result["uploaded"] == 0
        assert result["failed"] == 1

    def test_sync_ratings_failure_goes_to_dlq(self, db):
        _make_rating(db, rating_id="r1", rating=4)
        client = _FakeSaasClient({"s1": {"success": False, "error": "nope"}})
        svc = _service(db, client)
        result = _run(svc.sync_ratings())
        assert result["failed"] == 1
        assert db.query(FailedRatingUpload).count() == 1

    def test_sync_ratings_outer_exception_returns_error(self, db):
        svc = _service(db)
        with patch.object(svc, "get_pending_ratings",
                          side_effect=RuntimeError("db down")):
            result = _run(svc.sync_ratings())
        assert result["success"] is False
        assert "db down" in result["error"]
        assert svc._sync_in_progress is False

    def test_sync_ratings_upload_all_requeries_all(self, db):
        _make_rating(db, rating_id="r1", rating=4, synced=True)
        svc = _service(db)
        result = _run(svc.sync_ratings(upload_all=True))
        assert result["uploaded"] == 1  # synced rows re-uploaded too


# ============================================================================
# Conflict resolution
# ============================================================================

class TestConflictResolution:
    def test_conflict_local_missing_created_at_skips(self, db):
        r = _make_rating(db, rating_id="r1", rating=4, include_created=False)
        # server_default=func.now() fills created_at at INSERT — force NULL
        # with an explicit UPDATE to exercise the skip branch.
        from sqlalchemy import update
        db.execute(
            update(SkillRating).where(SkillRating.id == "r1").values(created_at=None)
        )
        db.commit()
        db.expire(r)
        db.refresh(r)
        assert r.created_at is None
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {"created_at": "2026-01-01"}))
        assert result["action"] == "skip"

    def test_conflict_remote_missing_timestamp_skips(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {"rating": 5}))
        assert result["action"] == "skip"

    def test_conflict_invalid_remote_timestamp_skips(self, db):
        r = _make_rating(db, rating_id="r1", rating=4)
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {"timestamp": "not-a-date"}))
        assert result["action"] == "skip"
        assert "format" in result["reason"]

    def test_remote_newer_updates_local_and_logs_conflict(self, db):
        r = _make_rating(db, rating_id="r1", rating=4, review="old",
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-02-01T00:00:00+00:00",
            "rating": 5, "comment": "new", "id": "remote-1",
        }))
        assert result["action"] == "updated_local"
        db.refresh(r)
        assert r.rating == 5
        assert r.review == "new"
        assert r.remote_rating_id == "remote-1"
        log = db.query(ConflictLog).filter(
            ConflictLog.conflict_type == "CONTENT_MISMATCH").one()
        assert log.resolution_strategy == "remote_wins"
        assert log.severity == "LOW"

    def test_remote_newer_same_content_no_conflict_logged(self, db):
        r = _make_rating(db, rating_id="r1", rating=4, review="same",
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-02-01T00:00:00+00:00",
            "rating": 4, "comment": "same",
        }))
        assert result["action"] == "updated_local"
        assert db.query(ConflictLog).count() == 0

    def test_local_newer_should_update_remote(self, db):
        r = _make_rating(db, rating_id="r1", rating=4,
                         created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-01-01T00:00:00+00:00", "rating": 3,
        }))
        assert result["action"] == "should_update_remote"

    def test_equal_timestamps_no_change(self, db):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r = _make_rating(db, rating_id="r1", rating=4, created_at=ts)
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-01-01T00:00:00+00:00", "rating": 4,
        }))
        assert result["action"] == "no_change"

    def test_naive_local_timestamp_assumed_utc(self, db):
        r = _make_rating(db, rating_id="r1", rating=4,
                         created_at=datetime(2026, 1, 1))  # naive
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-01-02T00:00:00+00:00", "rating": 5,
        }))
        assert result["action"] == "updated_local"

    def test_naive_remote_timestamp_assumed_utc(self, db):
        r = _make_rating(db, rating_id="r1", rating=4,
                         created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-01-01T00:00:00",  # naive ISO
            "rating": 5,
        }))
        assert result["action"] == "should_update_remote"

    def test_remote_timestamp_with_z_suffix_parsed(self, db):
        r = _make_rating(db, rating_id="r1", rating=4,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = _service(db)
        result = _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-02-01T00:00:00Z", "rating": 5,
        }))
        assert result["action"] == "updated_local"

    def test_conflict_log_commit_failure_swallowed(self, db):
        r = _make_rating(db, rating_id="r1", rating=4,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = _service(db)
        real_commit = svc.db.commit
        calls = {"n": 0}

        def _fail_once():
            calls["n"] += 1
            real_commit()
            if calls["n"] == 1:
                raise RuntimeError("log db down")

        # Fail only the ConflictLog commit (first one); the resolution commit
        # afterwards must still succeed.
        with patch.object(svc.db, "commit", side_effect=_fail_once):
            result = _run(svc.resolve_rating_conflict(r, {
                "created_at": "2026-02-01T00:00:00+00:00",
                "rating": 5, "comment": "new",
            }))
        # resolution still proceeds; conflict logging failure is non-fatal
        assert result["action"] == "updated_local"
        assert r.rating == 5

    def test_get_sync_metrics_counts(self, db):
        _make_rating(db, rating_id="r1", rating=4)
        _make_rating(db, rating_id="r2", rating=5, synced=True)
        _make_rating(db, rating_id="r3", rating=5, synced=True)
        r = _make_rating(db, rating_id="r4", rating=4,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        svc = _service(db)
        svc.handle_upload_failure(r, "err")
        _run(svc.resolve_rating_conflict(r, {
            "created_at": "2026-02-01T00:00:00+00:00",
            "rating": 5, "comment": "x",
        }))
        metrics = svc.get_sync_metrics()
        assert metrics == {"pending_count": 2, "synced_count": 2,
                           "failed_count": 1, "conflicts_count": 1}
