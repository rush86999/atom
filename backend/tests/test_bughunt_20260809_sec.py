"""TDD bug-hunt (2026-08-09) — security closes and new scans.

RED first, then GREEN:
 1. `api/feedback_batch.py` — /pending + approve/reject/adjudicate let ANY
    authenticated user read ALL users' pending feedback (original outputs +
    corrections) and flip statuses. Add a TEAM_LEAD+ moderator gate.
 2. `api/document_routes.py` /search — unbounded `limit` (no pagination cap).
 3. `core/agent_radio/radio_service.py` — send_message budget check is
    TOCTOU-racy (concurrent sends overspend ATOM_RADIO_TEAM_BUDGET_USD) and
    thread_budget_used_usd fail-opens to 0.0 on corrupted metadata.
 4. `api/deeplinks.py` /stats — cross-user aggregate audit (R37 scopes /audit
    to the current user; /stats did not).
 5. `core/privsec/token_encryption.py` — prod check is exact-match
    `env == "production"`; "Production"/"prod" mints a throwaway dev key.
 6. `core/specialist_matcher.py` `_verified_episode_ratio` — uses
    `confidence_score >= 0.8` as a "verified" proxy instead of the real
    tri-state `verified` flag (AgentReasoningStep, models.py:1056).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import deeplinks as deeplinks_api
from api import document_routes
from api import feedback_batch
from core.agent_radio.radio_service import (
    RadioAccessError,
    RadioBudgetExceeded,
    create_thread,
    get_thread_snapshot,
    send_message,
)
from core.privsec.token_encryption import MissingKeyError, reset_fernet_cache
from core.specialist_matcher import _verified_episode_ratio

pytestmark = pytest.mark.asyncio


# ===========================================================================
# 1. feedback_batch — moderator role gate (RED: member gets 200 today)
# ===========================================================================
@pytest.fixture
def feedback_app(worker_database):
    from core.models import AgentFeedback

    app = FastAPI()
    app.include_router(feedback_batch.router)
    session_factory = worker_database

    def _override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[feedback_batch.get_db] = _override_db

    cleanup = session_factory()
    cleanup.query(AgentFeedback).delete()
    cleanup.commit()
    cleanup.close()
    return app


def _override_user(app, role: str):
    app.dependency_overrides[feedback_batch.get_current_user] = (
        lambda: SimpleNamespace(id="u-member", role=role)
    )


def _seed_feedback(db, user_id="u-owner"):
    import uuid

    from core.models import AgentFeedback

    row = AgentFeedback(
        id=f"fb-{uuid.uuid4().hex[:12]}",
        agent_id="agent-1",
        user_id=user_id,
        original_output="original answer",
        user_correction="corrected answer",
        status="pending",
    )
    db.add(row)
    db.commit()
    return row


class TestFeedbackBatchRoleGate:
    def test_member_cannot_list_pending(self, feedback_app, worker_database):
        _override_user(feedback_app, "member")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.get("/api/feedback/batch/pending")
        assert resp.status_code == 403

    def test_member_cannot_approve(self, feedback_app, worker_database):
        _override_user(feedback_app, "member")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.post(
            "/api/feedback/batch/approve",
            json={"feedback_ids": ["fb-x"], "user_id": "u-member"},
        )
        assert resp.status_code == 403

    def test_member_cannot_reject(self, feedback_app, worker_database):
        _override_user(feedback_app, "member")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.post(
            "/api/feedback/batch/reject",
            json={"feedback_ids": ["fb-x"], "user_id": "u-member"},
        )
        assert resp.status_code == 403

    def test_member_cannot_update_status(self, feedback_app, worker_database):
        _override_user(feedback_app, "member")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.post(
            "/api/feedback/batch/update-status",
            json={
                "feedback_ids": ["fb-1"],
                "user_id": "u-member",
                "new_status": "approved",
            },
        )
        assert resp.status_code == 403

    def test_member_cannot_read_stats(self, feedback_app, worker_database):
        _override_user(feedback_app, "member")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.get("/api/feedback/batch/stats")
        assert resp.status_code == 403

    def test_team_lead_can_list_and_adjudicate(self, feedback_app, worker_database):
        _override_user(feedback_app, "team_lead")
        db = worker_database()
        row = _seed_feedback(db)
        client = TestClient(feedback_app)

        resp = client.get("/api/feedback/batch/pending")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

        resp = client.post(
            "/api/feedback/batch/approve",
            json={"feedback_ids": [row.id], "user_id": "u-member"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["processed"] == 1

        from core.models import AgentFeedback

        db.expire_all()
        assert (
            db.query(AgentFeedback).filter_by(id=row.id).first().status
            == "approved"
        )

    def test_admin_can_list_pending(self, feedback_app, worker_database):
        _override_user(feedback_app, "admin")
        db = worker_database()
        _seed_feedback(db)
        client = TestClient(feedback_app)
        resp = client.get("/api/feedback/batch/pending")
        assert resp.status_code == 200


# ===========================================================================
# 2. document_routes /search — limit pagination cap (RED: 500 accepted today)
# ===========================================================================
@pytest.fixture
def documents_app(worker_database, monkeypatch):
    app = FastAPI()
    app.include_router(document_routes.router)
    app.dependency_overrides[document_routes.get_current_user] = (
        lambda: SimpleNamespace(id="u-1", workspaces=[])
    )
    mock_handler = MagicMock()
    mock_handler.search.return_value = []
    monkeypatch.setattr(
        "api.document_routes.get_lancedb_handler", lambda ws_id: mock_handler
    )
    app.state.search_mock = mock_handler
    return app


class TestDocumentSearchLimitCap:
    def test_oversized_limit_rejected(self, documents_app):
        client = TestClient(documents_app)
        resp = client.get("/api/documents/search", params={"q": "hello", "limit": 500})
        assert resp.status_code == 422

    def test_capped_limit_accepted(self, documents_app):
        client = TestClient(documents_app)
        resp = client.get("/api/documents/search", params={"q": "hello", "limit": 200})
        assert resp.status_code == 200

    def test_negative_limit_rejected(self, documents_app):
        client = TestClient(documents_app)
        resp = client.get("/api/documents/search", params={"q": "hello", "limit": -1})
        assert resp.status_code == 422

    def test_search_does_not_pass_bogus_min_score_kwarg(self, documents_app):
        """Latent 500: the endpoint passed min_score=0.0 to LanceDBHandler.search,
        which has no such kwarg — every search crashed with TypeError."""
        client = TestClient(documents_app)
        resp = client.get("/api/documents/search", params={"q": "hello", "limit": 10})
        assert resp.status_code == 200
        call_kwargs = documents_app.state.search_mock.search.call_args.kwargs
        assert "min_score" not in call_kwargs


# ===========================================================================
# 3. radio_service — budget TOCTOU + fail-open metadata (RED both today)
# ===========================================================================
class TestRadioBudgetFailClosed:
    def test_corrupted_budget_metadata_rejects_send(self, db_session):
        thread = create_thread(
            db_session,
            name="corrupt",
            created_by_agent_id="agent_a",
            member_agent_ids=["agent_b"],
        )
        thread.metadata_json = {"used_budget_usd": "not-a-number"}
        db_session.commit()
        with pytest.raises(RadioBudgetExceeded):
            send_message(
                db_session,
                thread_id=thread.id,
                from_agent_id="agent_a",
                content="x",
                mention_agent_ids=["agent_b"],
                cost_usd=0.01,
            )

    def test_non_numeric_budget_rejects_send(self, db_session):
        thread = create_thread(
            db_session,
            name="nullbudget",
            created_by_agent_id="agent_a",
            member_agent_ids=["agent_b"],
        )
        thread.metadata_json = {"used_budget_usd": None}
        db_session.commit()
        with pytest.raises(RadioBudgetExceeded):
            send_message(
                db_session,
                thread_id=thread.id,
                from_agent_id="agent_a",
                content="x",
                mention_agent_ids=["agent_b"],
                cost_usd=0.01,
            )

    def test_snapshot_reports_unreadable_budget_without_crashing(self, db_session):
        thread = create_thread(
            db_session,
            name="snap-corrupt",
            created_by_agent_id="agent_a",
            member_agent_ids=["agent_b"],
        )
        thread.metadata_json = {"used_budget_usd": "garbage"}
        db_session.commit()
        snap = get_thread_snapshot(db_session, thread.id, "agent_b")
        assert snap["found"] is True
        assert snap["budget_used_usd"] is None


class TestRadioBudgetAtomic:
    def test_concurrent_sends_cannot_overspend(self, worker_database, monkeypatch):
        import threading

        monkeypatch.setattr(
            "core.agent_radio.radio_config.team_budget_usd", lambda: 0.10
        )
        seed_session = worker_database()
        thread = create_thread(
            seed_session,
            name="race",
            created_by_agent_id="agent_a",
            member_agent_ids=["agent_b"],
        )
        seed_session.close()

        outcomes = []
        barrier = threading.Barrier(2)

        def _sender(name):
            session = worker_database()
            barrier.wait()
            try:
                send_message(
                    session,
                    thread_id=thread.id,
                    from_agent_id="agent_a",
                    content=name,
                    mention_agent_ids=["agent_b"],
                    cost_usd=0.06,
                )
                outcomes.append("ok")
            except RadioBudgetExceeded:
                outcomes.append("exceeded")
            finally:
                session.close()

        t1 = threading.Thread(target=_sender, args=("m1",))
        t2 = threading.Thread(target=_sender, args=("m2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert outcomes.count("ok") == 1, f"expected 1 success, got {outcomes}"
        assert outcomes.count("exceeded") == 1, f"expected 1 rejection, got {outcomes}"

        check = worker_database()
        from core.models import AgentThread

        persisted = (
            check.query(AgentThread).filter(AgentThread.id == thread.id).first()
        )
        assert persisted.metadata_json["used_budget_usd"] == 0.06
        check.close()


# ===========================================================================
# 4. deeplinks /stats — user-scoped aggregates, admin sees all
# ===========================================================================
@pytest.fixture
def db(worker_database):
    from core.models import DeepLinkAudit, GatewayApiKey, User

    session = worker_database()
    session.query(DeepLinkAudit).delete()
    session.query(GatewayApiKey).delete()
    session.query(User).delete()
    session.commit()
    yield session
    session.close()


class TestDeeplinkStatsScoping:
    def _seed(self, db, user_id, resource_id, source="external", status="success"):
        from core.models import DeepLinkAudit

        row = DeepLinkAudit(
            id=f"dl-{user_id}-{resource_id}",
            user_id=user_id,
            agent_id="agent-1",
            resource_type="agent",
            resource_id=resource_id,
            action="execute",
            source=source,
            deeplink_url=f"atom://agent/{resource_id}",
            status=status,
            created_at=datetime.now(),
        )
        db.add(row)
        db.commit()
        return row

    async def test_member_stats_are_own_only(self, db):
        self._seed(db, "user-a", "res-1")
        self._seed(db, "user-b", "res-2")

        stats = await deeplinks_api.get_deeplink_stats(
            current_user=SimpleNamespace(id="user-a", role="member"),
            db=db,
        )
        assert stats.total_executions == 1
        assert stats.by_resource_type["agent"] == 1
        assert stats.successful_executions == 1

    async def test_admin_stats_cover_all_users(self, db):
        self._seed(db, "user-a", "res-1")
        self._seed(db, "user-b", "res-2")

        stats = await deeplinks_api.get_deeplink_stats(
            current_user=SimpleNamespace(id="user-a", role="admin"),
            db=db,
        )
        assert stats.total_executions == 2

    async def test_member_stats_do_not_count_other_user_recent_activity(self, db):
        from datetime import timedelta

        self._seed(db, "user-a", "res-1")
        self._seed(db, "user-b", "res-2")

        stats = await deeplinks_api.get_deeplink_stats(
            current_user=SimpleNamespace(id="user-a", role="member"),
            db=db,
        )
        assert stats.last_24h_executions == 1
        assert stats.last_7d_executions == 1


# ===========================================================================
# 5. token_encryption — production env aliases fail closed
# ===========================================================================
class TestTokenEncryptionProductionAliases:
    def _prod_alias_fails_closed(self, monkeypatch, tmp_path, alias):
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", alias)
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE",
            str(tmp_path / "missing_key_file"),
        )
        reset_fernet_cache()
        from core.privsec.token_encryption import encrypt_token

        with pytest.raises(MissingKeyError):
            encrypt_token("secret")
        reset_fernet_cache()

    def test_uppercase_production_fails_closed(self, monkeypatch, tmp_path):
        self._prod_alias_fails_closed(monkeypatch, tmp_path, "Production")

    def test_prod_alias_fails_closed(self, monkeypatch, tmp_path):
        self._prod_alias_fails_closed(monkeypatch, tmp_path, "prod")

    def test_whitespace_production_fails_closed(self, monkeypatch, tmp_path):
        self._prod_alias_fails_closed(monkeypatch, tmp_path, "  PRODUCTION  ")

    def test_development_still_mints_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BYOK_ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        key_file = tmp_path / "dev_key"
        monkeypatch.setattr(
            "core.privsec.token_encryption.BYOK_ENC_KEY_FILE", str(key_file)
        )
        reset_fernet_cache()
        from core.privsec.token_encryption import encrypt_token

        encrypt_token("secret")
        assert key_file.exists()
        reset_fernet_cache()


# ===========================================================================
# 6. specialist_matcher — verified ratio uses the real tri-state flag
# ===========================================================================
class TestSpecialistMatcherVerifiedRatio:
    def test_confidence_proxy_does_not_count_as_verified(self, db_session):
        from core.models import AgentEpisode, AgentReasoningStep

        # Episode 1: execution has a VERIFIED reasoning step -> counts.
        # Episode 2: execution has an UNVERIFIED step (high confidence!) -> must NOT count.
        # Episode 3: no execution at all -> must NOT count.
        db_session.add(
            AgentEpisode(
                id="ep-1",
                agent_id="agent-1",
                tenant_id="t",
                maturity_at_time="intern",
                outcome="success",
                confidence_score=0.9,
                execution_id="exec-1",
            )
        )
        db_session.add(
            AgentEpisode(
                id="ep-2",
                agent_id="agent-1",
                tenant_id="t",
                maturity_at_time="intern",
                outcome="success",
                confidence_score=0.9,
                execution_id="exec-2",
            )
        )
        db_session.add(
            AgentEpisode(
                id="ep-3",
                agent_id="agent-1",
                tenant_id="t",
                maturity_at_time="intern",
                outcome="success",
                confidence_score=0.95,
                execution_id=None,
            )
        )
        db_session.add(
            AgentReasoningStep(
                id="rs-1",
                execution_id="exec-1",
                step_number=1,
                step_type="action",
                verified="verified",
            )
        )
        db_session.add(
            AgentReasoningStep(
                id="rs-2",
                execution_id="exec-2",
                step_number=1,
                step_type="action",
                verified="unverified",
            )
        )
        db_session.commit()

        assert _verified_episode_ratio(db_session, "agent-1") == pytest.approx(1 / 3)

    def test_no_episodes_stays_neutral(self, db_session):
        assert _verified_episode_ratio(db_session, "agent-none") == 0.5
