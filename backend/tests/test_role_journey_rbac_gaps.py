# -*- coding: utf-8 -*-
"""Role-journey RBAC gap closure (2026-09-08 pass).

Every user role must be able to complete its journey without privilege
inversion (a HIGHER role denied something a LOWER role is allowed) and
without unguarded write surfaces. This file locks the fixes:

1.  core/security/rbac.py exposes the hierarchy as data (role_level /
    user_meets_role) so ad-hoc allowlists stop forgetting roles.
2.  Supervisor gates (TEAM_LEAD+) accept ADMIN and OWNER — previously the
    five _require_supervisor copies plus agent-governance approve excluded
    them (an admin was denied what a team_lead may do).
3.  Admin gates (WORKSPACE_ADMIN+) accept ADMIN and OWNER (trust
    calibration, ontology drafts).
4.  Enterprise user management (the REAL user table) requires
    WORKSPACE_ADMIN+, caps granted roles at the actor's own level, and
    gains a create-user endpoint + role catalog for the admin UI.
5.  Dead is_admin gates (User has no such column — even super_admin got
    403 forever): mini-app approve, integration schema registration,
    analytics cross-user patterns.
6.  Bootstrap never downgrades a promoted admin's role on boot.
7.  Admin/owner count as trusted reviewers for feedback adjudication.
8.  Supervision live reads (sessions/active, execution stream) are
    supervisor-gated instead of auth-only.
9.  Operational intervention execution + supervised-queue mutations are
    supervisor actions, not any-authenticated-user actions.

Gate-only assertions use `!= 403` for the allowed bands: the subject is
the role gate, and the handler behind it may legitimately 4xx/5xx on the
mock db. Precision lives in the member/denied assertions (== 403).
"""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user as auth_get_current_user
from core.database import Base, get_db
from core.models import AgentRegistry, User, UserRole


def _user_mock(user_id="u-1", role="member"):
    u = MagicMock()
    u.id = user_id
    u.role = role
    u.email = f"{user_id}@example.com"
    return u


def make_role_client(router, role):
    """TestClient whose re-queried User row carries `role` (round-65
    pattern: gates re-read the user from the db)."""
    app = FastAPI()
    app.include_router(router)
    db = MagicMock()
    db_user = _user_mock(role=role)
    db.query.return_value.filter.return_value.first.return_value = db_user
    app.dependency_overrides[auth_get_current_user] = lambda: db_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False), db


# ============================================================================
# 1. Hierarchy helpers
# ============================================================================


class TestRoleHierarchyHelpers:
    def test_role_level_ordering(self):
        from core.security.rbac import role_level

        assert role_level(UserRole.GUEST) < role_level(UserRole.VIEWER)
        assert role_level(UserRole.VIEWER) < role_level(UserRole.MEMBER)
        assert role_level(UserRole.MEMBER) < role_level(UserRole.TEAM_LEAD)
        assert role_level(UserRole.TEAM_LEAD) < role_level(UserRole.WORKSPACE_ADMIN)
        assert role_level(UserRole.WORKSPACE_ADMIN) < role_level(UserRole.ADMIN)
        assert role_level(UserRole.ADMIN) < role_level(UserRole.OWNER)
        assert role_level(UserRole.OWNER) < role_level(UserRole.SUPER_ADMIN)

    def test_role_level_accepts_raw_string(self):
        from core.security.rbac import role_level

        assert role_level("team_lead") == role_level(UserRole.TEAM_LEAD)
        assert role_level("TEAM_LEAD") == role_level(UserRole.TEAM_LEAD)
        assert role_level("nonexistent_role") == 0

    def test_user_meets_role(self):
        from core.security.rbac import user_meets_role

        assert user_meets_role(_user_mock(role="admin"), UserRole.TEAM_LEAD)
        assert user_meets_role(_user_mock(role="owner"), UserRole.WORKSPACE_ADMIN)
        assert user_meets_role(_user_mock(role="super_admin"), UserRole.SUPER_ADMIN)
        assert not user_meets_role(_user_mock(role="team_lead"), UserRole.WORKSPACE_ADMIN)
        assert not user_meets_role(_user_mock(role="member"), UserRole.TEAM_LEAD)


# ============================================================================
# 2. Supervisor gates accept admin/owner (privilege inversion)
# ============================================================================


class TestSupervisorGatesAcceptAdminAndOwner:
    """admin (level 6) must pass every TEAM_LEAD+ gate; member must not."""

    def test_supervision_intervene_admin_allowed(self):
        from api.supervision_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        with patch("api.supervision_routes.SupervisionService") as svc:
            svc.return_value.intervene = AsyncMock(
                return_value=MagicMock(success=True, message="paused", session_state="paused")
            )
            resp = client.post(
                "/api/supervision/sessions/s1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 200, resp.text

    def test_maturity_proposal_approve_admin_not_denied(self):
        from api.agent_maturity_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        resp = client.post("/api/maturity/training/proposals/p1/approve", json={"approve": True})
        assert resp.status_code != 403, f"admin denied a TEAM_LEAD+ surface: {resp.text}"

    def test_graduation_promote_admin_not_denied(self):
        from api.episode_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        resp = client.post("/api/episodes/graduation/promote?agent_id=a1&new_maturity=INTERN")
        assert resp.status_code != 403, f"admin denied graduation promote: {resp.text}"

    def test_playbook_approve_admin_not_denied(self):
        from api.playbook_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        resp = client.post("/api/playbooks/pb1/approve")
        assert resp.status_code != 403, f"admin denied playbook approve: {resp.text}"

    def test_audit_events_admin_not_denied(self):
        from api.audit_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        resp = client.get("/api/audit/events")
        assert resp.status_code != 403, f"admin denied audit trail: {resp.text}"

    def test_hitl_approve_admin_not_denied(self):
        from api.agent_governance_routes import router

        client, _ = make_role_client(router, UserRole.ADMIN.value)
        with patch("api.agent_governance_routes.intervention_service") as svc:
            svc.approve_intervention = AsyncMock(return_value={"success": True, "action_id": "a1"})
            resp = client.post("/api/agent-governance/approve/appr1")
        assert resp.status_code != 403, f"admin denied HITL approve: {resp.text}"

    @pytest.mark.parametrize("role", [UserRole.OWNER.value, UserRole.SUPER_ADMIN.value])
    def test_owner_band_passes_supervisor_gate(self, role):
        from api.supervision_routes import router

        client, _ = make_role_client(router, role)
        with patch("api.supervision_routes.SupervisionService") as svc:
            svc.return_value.intervene = AsyncMock(
                return_value=MagicMock(success=True, message="paused", session_state="paused")
            )
            resp = client.post(
                "/api/supervision/sessions/s1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 200, f"{role} denied supervision intervene: {resp.text}"

    def test_member_still_denied(self):
        from api.supervision_routes import router as sup
        from api.agent_governance_routes import router as gov

        client, _ = make_role_client(sup, UserRole.MEMBER.value)
        resp = client.post(
            "/api/supervision/sessions/s1/intervene",
            json={"intervention_type": "pause", "guidance": "stop"},
        )
        assert resp.status_code == 403, "member slipped into supervision intervene"

        client, _ = make_role_client(gov, UserRole.MEMBER.value)
        resp = client.post("/api/agent-governance/approve/appr1")
        assert resp.status_code == 403, "member slipped into HITL approve"


class TestAdminGatesAcceptAdminAndOwner:
    """WORKSPACE_ADMIN+ gates must accept admin/owner too."""

    @pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OWNER.value])
    def test_trust_calibration_admin_band_not_denied(self, role):
        from api.trust_calibration_routes import router

        client, _ = make_role_client(router, role)
        resp = client.get("/api/v1/trust-calibration/stats")
        assert resp.status_code != 403, f"{role} denied trust calibration: {resp.text}"

    @pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OWNER.value])
    def test_ontology_draft_admin_band_not_denied(self, role):
        from api.ontology_draft_routes import router

        client, _ = make_role_client(router, role)
        resp = client.get("/api/v1/ontology-drafts/pending")
        assert resp.status_code != 403, f"{role} denied ontology drafts: {resp.text}"

    def test_member_denied_trust_calibration(self):
        from api.trust_calibration_routes import router

        client, _ = make_role_client(router, UserRole.MEMBER.value)
        resp = client.get("/api/v1/trust-calibration/stats")
        assert resp.status_code == 403


# ============================================================================
# 3. Enterprise user management (real User table)
# ============================================================================


def _seed_user(db, id, email, role="member"):
    u = User(
        id=id,
        email=email,
        hashed_password="x",
        first_name="F",
        last_name="L",
        role=role,
        status="active",
        is_active=True,
    )
    db.add(u)
    return u


@pytest.fixture()
def eum_env():
    """Real sqlite scratch db with an actor + a target user; TestClient on
    the enterprise router with the actor as the authenticated user."""
    from core.enterprise_user_management import router as eum_router

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    actor = _seed_user(db, "actor-1", "actor@example.com")
    _seed_user(db, "target-9", "target@example.com")
    db.commit()

    app = FastAPI()
    app.include_router(eum_router)
    app.dependency_overrides[auth_get_current_user] = lambda: actor
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app, raise_server_exceptions=False)
    return client, db, actor


class TestEnterpriseUserManagementAuthz:
    def test_member_cannot_grant_super_admin(self, eum_env):
        client, db, _ = eum_env
        resp = client.patch("/api/enterprise/users/target-9", json={"role": "super_admin"})
        assert resp.status_code == 403, "member escalated to super_admin"
        assert db.query(User).filter(User.id == "target-9").first().role == "member"

    def test_unauthenticated_cannot_list_users(self):
        from core.enterprise_user_management import router as eum_router

        app = FastAPI()
        app.include_router(eum_router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/enterprise/users")
        assert resp.status_code in (401, 403)

    def test_team_lead_cannot_manage_users(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.TEAM_LEAD.value
        db.commit()
        resp = client.patch("/api/enterprise/users/target-9", json={"first_name": "X"})
        assert resp.status_code == 403

    def test_workspace_admin_can_set_role_below_own_level(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        db.commit()
        resp = client.patch("/api/enterprise/users/target-9", json={"role": "team_lead"})
        assert resp.status_code == 200, resp.text
        assert db.query(User).filter(User.id == "target-9").first().role == "team_lead"

    def test_workspace_admin_cannot_grant_super_admin(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        db.commit()
        resp = client.patch("/api/enterprise/users/target-9", json={"role": "super_admin"})
        assert resp.status_code == 403, "workspace_admin granted super_admin"
        assert db.query(User).filter(User.id == "target-9").first().role == "member"

    def test_cannot_modify_higher_level_user(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        target = db.query(User).filter(User.id == "target-9").first()
        target.role = UserRole.OWNER.value
        db.commit()
        resp = client.patch("/api/enterprise/users/target-9", json={"status": "deleted"})
        assert resp.status_code == 403, "workspace_admin modified an owner"
        assert db.query(User).filter(User.id == "target-9").first().status == "active"

    def test_super_admin_can_grant_super_admin(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.SUPER_ADMIN.value
        db.commit()
        resp = client.patch("/api/enterprise/users/target-9", json={"role": "super_admin"})
        assert resp.status_code == 200, resp.text
        assert db.query(User).filter(User.id == "target-9").first().role == "super_admin"

    def test_create_user_endpoint(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        db.commit()
        resp = client.post(
            "/api/enterprise/users",
            json={
                "email": "new.hire@example.com",
                "password": "s3cret-password",
                "full_name": "New Hire",
                "role": "member",
            },
        )
        assert resp.status_code == 201, resp.text
        created = db.query(User).filter(User.email == "new.hire@example.com").first()
        assert created is not None
        assert created.role == "member"
        assert created.hashed_password != "s3cret-password"

    def test_create_user_cannot_grant_above_own_level(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        db.commit()
        resp = client.post(
            "/api/enterprise/users",
            json={
                "email": "sneaky@example.com",
                "password": "s3cret-password",
                "first_name": "S",
                "last_name": "N",
                "role": "owner",
            },
        )
        assert resp.status_code == 403

    def test_role_catalog_endpoint(self, eum_env):
        client, db, actor = eum_env
        actor.role = UserRole.WORKSPACE_ADMIN.value
        db.commit()
        resp = client.get("/api/enterprise/roles")
        assert resp.status_code == 200
        names = {r["name"] for r in resp.json()}
        assert names == {r.value for r in UserRole}


# ============================================================================
# 4. Dead is_admin gates (User has no is_admin/is_staff columns)
# ============================================================================


class TestDeadAdminGatesReachableBySuperAdmin:
    def test_mini_app_approve_super_admin_allowed(self):
        from api.mini_app_routes import router

        app = FastAPI()
        app.include_router(router)
        admin = _user_mock(role=UserRole.SUPER_ADMIN.value)
        app.dependency_overrides[auth_get_current_user] = lambda: admin
        db = MagicMock()
        app_obj = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app_obj
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mini-apps/app-1/approve")
        assert resp.status_code == 200, f"even super_admin got {resp.status_code}"
        assert app_obj.is_approved is True

    def test_mini_app_approve_member_denied(self):
        from api.mini_app_routes import router

        app = FastAPI()
        app.include_router(router)
        member = _user_mock(role=UserRole.MEMBER.value)
        app.dependency_overrides[auth_get_current_user] = lambda: member
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/mini-apps/app-1/approve")
        assert resp.status_code == 403

    def _schema_client(self, role):
        from core.integration_enhancement_endpoints import get_data_mapper, router

        app = FastAPI()
        app.include_router(router)
        user = _user_mock(role=role)
        app.dependency_overrides[auth_get_current_user] = lambda: user
        mapper = MagicMock()
        mapper.register_schema.return_value = MagicMock(
            integration_id="hubspot",
            integration_name="HubSpot",
            version="1",
            fields=[],
            supported_operations=[],
            bulk_operations_supported=False,
            max_bulk_size=100,
        )
        app.dependency_overrides[get_data_mapper] = lambda: mapper
        return TestClient(app, raise_server_exceptions=False), mapper

    def _schema_payload(self):
        return {
            "integration_id": "hubspot",
            "integration_name": "HubSpot",
            "version": "1.0",
            "fields": {"email": {"type": "string"}},
            "supported_operations": ["read"],
        }

    def test_integration_schema_registration_admin_allowed(self):
        client, mapper = self._schema_client(UserRole.SUPER_ADMIN.value)
        resp = client.post("/api/v1/integrations/schemas", json=self._schema_payload())
        assert resp.status_code != 403, f"admin denied schema registration: {resp.text}"
        mapper.register_schema.assert_called_once()

    def test_integration_schema_registration_member_denied(self):
        client, mapper = self._schema_client(UserRole.MEMBER.value)
        resp = client.post("/api/v1/integrations/schemas", json=self._schema_payload())
        assert resp.status_code == 403
        mapper.register_schema.assert_not_called()


class TestAnalyticsPatternsAdminOverride:
    def _client(self, role):
        from api.analytics_dashboard_routes import router

        app = FastAPI()
        app.include_router(router)
        user = _user_mock(user_id="me-1", role=role)
        app.dependency_overrides[auth_get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: MagicMock()
        engine = MagicMock()
        engine.get_user_pattern.return_value = {"active_hours": [9, 10]}
        patcher = patch(
            "api.analytics_dashboard_routes.get_predictive_insights_engine",
            return_value=engine,
        )
        return TestClient(app, raise_server_exceptions=False), patcher

    def test_admin_band_cross_user_patterns_allowed(self):
        client, patcher = self._client(UserRole.ADMIN.value)
        with patcher:
            resp = client.get("/api/analytics/patterns/other-user")
        assert resp.status_code != 403, f"admin denied cross-user patterns: {resp.text}"

    def test_member_cross_user_patterns_denied(self):
        client, patcher = self._client(UserRole.MEMBER.value)
        with patcher:
            resp = client.get("/api/analytics/patterns/other-user")
        assert resp.status_code == 403


# ============================================================================
# 5. Bootstrap must not downgrade a promoted role
# ============================================================================


class TestBootstrapNoDowngrade:
    def _bootstrap_over(self, monkeypatch, db):
        """Patch admin_bootstrap to run against the scratch db."""
        import core.admin_bootstrap as bootstrap

        @contextmanager
        def _session():
            yield db

        monkeypatch.setattr(bootstrap, "get_db_session", _session)
        monkeypatch.setattr(bootstrap, "ensure_default_tenant_and_workspace", lambda db: None)
        monkeypatch.setattr(bootstrap, "ensure_demo_agent", lambda db: None)
        return bootstrap

    def _scratch_db(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        # expire_on_commit=False: ensure_admin_user closes the session; the
        # assertions below read the detached instances' loaded attributes.
        return sessionmaker(bind=engine, expire_on_commit=False)()

    def test_admin_password_reset_preserves_owner_role(self, monkeypatch):
        db = self._scratch_db()
        bootstrap = self._bootstrap_over(monkeypatch, db)
        old_hash = bootstrap.get_password_hash("old")
        user = User(
            id="boot-1",
            email="admin@example.com",
            hashed_password=old_hash,
            first_name="Admin",
            last_name="User",
            role=UserRole.OWNER.value,
            status="active",
            is_active=True,
        )
        db.add(user)
        db.commit()
        monkeypatch.setenv("ADMIN_PASSWORD", "new-password-from-env")

        bootstrap.ensure_admin_user()

        assert user.role == UserRole.OWNER.value, (
            "ADMIN_PASSWORD boot reset downgraded an operator-promoted owner"
        )
        assert user.hashed_password != old_hash, "password was not reset"

    def test_fresh_bootstrap_still_workspace_admin(self, monkeypatch):
        db = self._scratch_db()
        bootstrap = self._bootstrap_over(monkeypatch, db)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

        bootstrap.ensure_admin_user()

        user = db.query(User).filter(User.email == "admin@example.com").first()
        assert user is not None
        assert user.role == UserRole.WORKSPACE_ADMIN.value


# ============================================================================
# 6. Feedback adjudication trusts admin/owner
# ============================================================================


class TestFeedbackAdjudicationTrustsAdminBand:
    def _svc_with_db(self, role):
        from core.agent_governance_service import AgentGovernanceService

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        user = User(
            id="rev-1",
            email="rev@example.com",
            hashed_password="x",
            first_name="R",
            last_name="V",
            role=role,
            status="active",
            is_active=True,
        )
        agent = AgentRegistry(
            id="agent-x",
            name="Agent X",
            category="general",
            module_path="core.agents.queen_agent",
            class_name="QueenAgent",
        )
        db.add_all([user, agent])
        db.commit()

        svc = MagicMock(spec=AgentGovernanceService)
        svc.db = db
        svc._workspace_scope_condition.return_value = True
        return svc

    def _real_feedback(self, db):
        from core.models import AgentFeedback

        fb = AgentFeedback(
            agent_id="agent-x",
            user_id="rev-1",
            rating=5,
            feedback_type="thumbs_up",
            original_output="out",
            user_correction="corr",
            input_context="ctx",
        )
        db.add(fb)
        db.commit()
        return fb

    @pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OWNER.value])
    def test_admin_band_feedback_auto_accepted(self, role):
        from core.agent_governance_service import AgentGovernanceService

        svc = self._svc_with_db(role)
        feedback = self._real_feedback(svc.db)

        asyncio.run(AgentGovernanceService._adjudicate_feedback(svc, feedback))

        assert feedback.status == "accepted"

    def test_member_feedback_not_auto_accepted(self):
        from core.agent_governance_service import AgentGovernanceService

        svc = self._svc_with_db(UserRole.MEMBER.value)
        feedback = self._real_feedback(svc.db)

        asyncio.run(AgentGovernanceService._adjudicate_feedback(svc, feedback))

        assert feedback.status != "accepted"


# ============================================================================
# 7. Supervision live reads + operational mutations
# ============================================================================


class TestSupervisionReadGates:
    def test_active_sessions_member_denied(self):
        from api.supervision_routes import router

        client, _ = make_role_client(router, UserRole.MEMBER.value)
        with patch("api.supervision_routes.SupervisionService") as svc:
            svc.return_value.get_active_sessions = AsyncMock(return_value=[])
            resp = client.get("/api/supervision/sessions/active")
        assert resp.status_code == 403, "member can list everyone's live supervision sessions"

    def test_active_sessions_supervisor_allowed(self):
        from api.supervision_routes import router

        client, _ = make_role_client(router, UserRole.TEAM_LEAD.value)
        with patch("api.supervision_routes.SupervisionService") as svc:
            svc.return_value.get_active_sessions = AsyncMock(return_value=[])
            resp = client.get("/api/supervision/sessions/active")
        assert resp.status_code == 200, resp.text

    def test_execution_stream_member_denied(self):
        from api.supervision_routes import router

        client, _ = make_role_client(router, UserRole.MEMBER.value)
        resp = client.get("/api/supervision/exec-1/stream")
        assert resp.status_code == 403, "member can tail any execution's live logs"


class TestOperationalAndQueueGates:
    def test_operational_intervention_execute_requires_auth(self):
        from api.operational_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)
        with patch("api.operational_routes.active_intervention_service") as svc:
            svc.execute_intervention = AsyncMock(return_value={"ok": True})
            resp = client.post("/api/business-health/interventions/i1/execute", json={"action": "x"})
        assert resp.status_code in (401, 403), "anonymous execution of operational interventions"

    def test_operational_intervention_execute_member_denied(self):
        from api.operational_routes import router

        app = FastAPI()
        app.include_router(router)
        member = _user_mock(role=UserRole.MEMBER.value)
        app.dependency_overrides[auth_get_current_user] = lambda: member
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = member
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/business-health/interventions/i1/execute",
            json={"action": "x", "payload": {"k": 1}},
        )
        assert resp.status_code == 403

    def test_supervised_queue_process_member_denied(self):
        from api.supervised_queue_routes import router

        client, _ = make_role_client(router, UserRole.MEMBER.value)
        with patch("api.supervised_queue_routes.SupervisedQueueService") as svc:
            svc.return_value.process_queue = AsyncMock(return_value={"processed": 0})
            resp = client.post("/api/supervised-queue/process")
        assert resp.status_code == 403, "member can drive the supervised queue"

    def test_supervised_queue_process_supervisor_allowed(self):
        from api.supervised_queue_routes import router

        client, _ = make_role_client(router, UserRole.TEAM_LEAD.value)
        with patch("api.supervised_queue_routes.SupervisedQueueService") as svc:
            svc.return_value.process_queue = AsyncMock(return_value={"processed": 0})
            resp = client.post("/api/supervised-queue/process")
        assert resp.status_code != 403, f"team_lead denied queue processing: {resp.text}"


# ============================================================================
# 8. Platform-admin band (2026-09-08b: daemon control, cache, skills,
#    workspace context were exact-super_admin — unreachable locally since no
#    flow grants super_admin; the operator (workspace_admin) could never
#    stop their own daemon). WORKSPACE_ADMIN+ via the shared hierarchy.
# ============================================================================


class TestPlatformAdminBand:
    def _client_for(self, router, role):
        app = FastAPI()
        app.include_router(router)
        user = _user_mock(role=role)
        app.dependency_overrides[auth_get_current_user] = lambda: user
        return TestClient(app, raise_server_exceptions=False)

    def test_agent_stop_workspace_admin_allowed(self):
        from api.agent_control_routes import router

        client = self._client_for(router, UserRole.WORKSPACE_ADMIN.value)
        with patch("api.agent_control_routes.DaemonManager") as dm:
            dm.is_running.return_value = True
            dm.stop_daemon.return_value = 4242
            resp = client.post("/api/agent/stop")
        assert resp.status_code == 200, f"operator cannot stop own daemon: {resp.text}"
        assert resp.json()["success"] is True

    def test_agent_stop_member_denied(self):
        from api.agent_control_routes import router

        client = self._client_for(router, UserRole.MEMBER.value)
        resp = client.post("/api/agent/stop")
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OWNER.value, UserRole.SUPER_ADMIN.value])
    def test_agent_stop_admin_band_allowed(self, role):
        from api.agent_control_routes import router

        client = self._client_for(router, role)
        with patch("api.agent_control_routes.DaemonManager") as dm:
            dm.is_running.return_value = True
            dm.stop_daemon.return_value = 4242
            resp = client.post("/api/agent/stop")
        assert resp.status_code == 200, f"{role} denied daemon stop: {resp.text}"

    def test_cache_stats_workspace_admin_not_denied(self):
        from api.admin.cache_routes import router

        client = self._client_for(router, UserRole.WORKSPACE_ADMIN.value)
        # gate-only assertion: handler may 5xx on real singleton caches; the
        # subject is that workspace_admin passes the (formerly exact-
        # super_admin) gate.
        resp = client.get("/api/v1/admin/cache/stats")
        assert resp.status_code != 403, f"operator denied cache stats: {resp.text}"

    def test_cache_stats_member_denied(self):
        from api.admin.cache_routes import router

        client = self._client_for(router, UserRole.MEMBER.value)
        resp = client.get("/api/v1/admin/cache/stats")
        assert resp.status_code == 403

    def test_skill_create_workspace_admin_not_denied(self):
        from api.admin.skill_routes import router

        client = self._client_for(router, UserRole.WORKSPACE_ADMIN.value)
        resp = client.post(
            "/api/admin/skills/",
            json={"name": "x", "instructions": "do x", "capabilities": [], "scripts": {}},
        )
        assert resp.status_code != 403, f"operator denied skill builder: {resp.text}"

    def test_skill_create_member_denied(self):
        from api.admin.skill_routes import router

        client = self._client_for(router, UserRole.MEMBER.value)
        resp = client.post("/api/admin/skills/", json={"name": "x"})
        assert resp.status_code == 403


