"""Coverage wave W65f — api/financial_routes.py, api/enterprise_auth_endpoints.py,
api/learning_plan_routes.py (TDD).

Every endpoint x {success, error branch, validation, auth}. Services are
patched at their real module attributes (api.<module>.<name>); enterprise-auth
rate limiters are bypassed via BYPASS_RATE_LIMIT=1 (repo pattern); DB sessions
are MagicMock. Zero LLM spend, zero network, zero real DB writes.

Bugs found + fixed in api/financial_routes.py (regression tests below):
1. Every FinancialAudit(...) construction passed phantom kwargs
   (agent_id/action_type/changes/success/...) the model does not have
   (core/models.py:9567 uses operation_type/table_name/record_id/
   audit_metadata) -> TypeError -> EVERY create/update/delete financial
   account 500'd. Now built via _build_audit() per the documented pattern in
   core/financial_audit_service.py. Tests: test_create_account_*,
   test_update_account_*, test_delete_account_*.
2. FinancialAccount(user_id=..., provider=...) -> TypeError (no such
   columns; ownership/provider now live in account_metadata JSON; queries
   scope via _account_owner_scope).
3. NetWorthSnapshot(snapshot_date/assets/liabilities=...) -> TypeError (real
   columns: created_at/total_assets/total_liabilities) -> summary + create
   snapshot 500'd.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# NOTE: BYPASS_RATE_LIMIT must NOT be set at module level — it leaks into
# every later test in the process and silently disables ALL auth rate
# limiters (the w75 auth-endpoint 429 tests fail with 200). Scope it to
# the tests that need it via the _bypass_rate_limit fixture below.

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from core.auth import get_current_user


@pytest.fixture(autouse=True)
def _bypass_rate_limit():
    """Scoped rate-limit bypass for THIS module's tests only.

    The enterprise login/register tests fire many requests from the shared
    'testclient' IP, tripping the real (non-overridden) limiters. Set the
    bypass per-test and restore afterwards so no later test file inherits it.
    """
    prev = os.environ.get("BYPASS_RATE_LIMIT")
    os.environ["BYPASS_RATE_LIMIT"] = "1"
    yield
    if prev is None:
        os.environ.pop("BYPASS_RATE_LIMIT", None)
    else:
        os.environ["BYPASS_RATE_LIMIT"] = prev
from core.database import get_db

USER = SimpleNamespace(id="u-1", tenant_id="t-1", role="member", email="u@t.com")


def _make_app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db, user=USER):
    app = _make_app(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _anon_client(router, db):
    app = _make_app(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _refresh_ids(db):
    """Real models get their PK/server defaults only at flush; simulate it so
    response models (which require id/created_at) validate."""
    def _refresh(inst):
        if getattr(inst, "id", None) is None:
            inst.id = f"id-{uuid.uuid4().hex[:8]}"
        if getattr(inst, "created_at", None) is None:
            inst.created_at = datetime.now(timezone.utc)

    db.refresh.side_effect = _refresh


def _added_instances(db, cls):
    return [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], cls)]


# =========================================================================== #
# api/financial_routes.py
# =========================================================================== #
def _account(**overrides):
    a = SimpleNamespace(
        id="acct-1",
        account_type="checking",
        name="Main",
        balance=Decimal("1234.56"),
        currency="USD",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        account_metadata={"user_id": "u-1", "provider": "Chase"},
        tenant_id="t-1",
    )
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


def _snapshot(**overrides):
    s = SimpleNamespace(
        user_id="u-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        net_worth=Decimal("500.00"),
        total_assets=Decimal("1000.00"),
        total_liabilities=Decimal("500.00"),
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestFinancialRoutes:
    def _c(self, db=None, user=USER):
        from api.financial_routes import router

        return _client(router, db or MagicMock(), user=user)

    def _anon(self, db=None):
        from api.financial_routes import router

        return _anon_client(router, db or MagicMock())

    @pytest.fixture
    def governance(self):
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(
            return_value=(SimpleNamespace(id="a-1", status="supervised"), None)
        )
        gov = MagicMock()
        gov.can_perform_action.return_value = {"allowed": True, "requires_human_approval": False}
        with patch("api.financial_routes.AgentContextResolver", return_value=resolver), \
             patch("api.financial_routes.AgentGovernanceService", return_value=gov):
            yield gov

    # -- net worth summary --
    def test_net_worth_summary_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        r = self._c(db).get("/api/financial/net-worth/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["net_worth"] == "0.00"
        assert body["assets"] == "0.00"

    def test_net_worth_summary_with_snapshot_datetime(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _snapshot()
        r = self._c(db).get("/api/financial/net-worth/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["snapshot_date"] == "2026-01-01"
        assert body["net_worth"] == "500.00"

    def test_net_worth_summary_with_snapshot_date_value(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _snapshot(
            created_at=date(2026, 2, 2)
        )
        r = self._c(db).get("/api/financial/net-worth/summary")
        assert r.status_code == 200
        assert r.json()["snapshot_date"] == "2026-02-02"

    def test_net_worth_summary_requires_auth(self):
        assert self._anon().get("/api/financial/net-worth/summary").status_code == 401

    # -- list / get accounts --
    def test_list_accounts(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _account(), _account(id="acct-2", name="Savings", account_metadata={"user_id": "u-1", "provider": None})
        ]
        r = self._c(db).get("/api/financial/accounts")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["provider"] == "Chase"
        assert rows[0]["balance"] == "1234.56"

    def test_list_accounts_requires_auth(self):
        assert self._anon().get("/api/financial/accounts").status_code == 401

    def test_get_account_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).get("/api/financial/accounts/acct-1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "acct-1"
        assert body["user_id"] == "u-1"
        assert body["provider"] == "Chase"

    def test_get_account_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/financial/accounts/ghost")
        assert r.status_code == 404

    def test_get_account_requires_auth(self):
        assert self._anon().get("/api/financial/accounts/acct-1").status_code == 401

    # -- create --
    def test_create_account_success(self):
        from core.models import FinancialAccount, FinancialAudit

        db = MagicMock()
        _refresh_ids(db)
        r = self._c(db).post("/api/financial/accounts", json={
            "account_type": "checking", "provider": "Chase", "name": "Main",
            "balance": "1234.56", "currency": "USD",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["account_type"] == "checking"
        assert body["provider"] == "Chase"
        assert body["balance"] == "1234.56"
        accounts = _added_instances(db, FinancialAccount)
        assert len(accounts) == 1
        assert accounts[0].account_metadata["user_id"] == "u-1"
        assert accounts[0].account_metadata["provider"] == "Chase"
        audits = _added_instances(db, FinancialAudit)
        assert len(audits) == 1
        assert audits[0].operation_type == "INSERT"
        assert audits[0].audit_metadata["action_type"] == "create"
        assert audits[0].audit_metadata["success"] is True

    def test_create_account_name_defaults_to_type(self):
        db = MagicMock()
        _refresh_ids(db)
        self._c(db).post("/api/financial/accounts", json={
            "account_type": "savings", "balance": "10.00",
        })
        from core.models import FinancialAccount

        account = _added_instances(db, FinancialAccount)[0]
        assert account.name == "savings"
        assert account.tenant_id == "t-1"
        assert account.account_metadata["provider"] is None

    def test_create_account_with_agent_governance_allowed(self, governance):
        from core.models import FinancialAudit

        db = MagicMock()
        _refresh_ids(db)
        r = self._c(db).post("/api/financial/accounts", json={
            "account_type": "investment", "name": "Broker", "balance": "5000.00",
            "agent_id": "a-1",
        })
        assert r.status_code == 201
        audit = _added_instances(db, FinancialAudit)[0]
        assert audit.audit_metadata["agent_id"] == "a-1"
        assert audit.agent_maturity == "supervised"
        assert audit.audit_metadata["governance_check_passed"] is True

    def test_create_account_governance_denied_403(self, governance):
        governance.can_perform_action.return_value = {
            "allowed": False, "requires_human_approval": True
        }
        from core.models import FinancialAudit

        db = MagicMock()
        r = self._c(db).post("/api/financial/accounts", json={
            "account_type": "checking", "name": "X", "balance": "1.00",
            "agent_id": "a-1",
        })
        assert r.status_code == 403
        audit = _added_instances(db, FinancialAudit)[0]
        assert audit.audit_metadata["success"] is False
        assert audit.audit_metadata["required_approval"] is True

    def test_create_account_agent_resolves_none(self, governance):
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(None, None))
        with patch("api.financial_routes.AgentContextResolver", return_value=resolver):
            db = MagicMock()
            _refresh_ids(db)
            r = self._c(db).post("/api/financial/accounts", json={
                "account_type": "credit_card", "name": "Card", "balance": "0.00",
                "agent_id": "ghost-agent",
            })
        assert r.status_code == 201

    def test_create_account_missing_type_422(self):
        r = self._c().post("/api/financial/accounts", json={"balance": "1.00"})
        assert r.status_code == 422

    def test_create_account_negative_balance_422(self):
        r = self._c().post("/api/financial/accounts", json={
            "account_type": "checking", "balance": "-5.00",
        })
        assert r.status_code == 422

    def test_create_account_requires_auth(self):
        assert self._anon().post("/api/financial/accounts", json={
            "account_type": "checking", "balance": "1.00",
        }).status_code == 401

    # -- update --
    def test_update_account_all_fields(self):
        from core.models import FinancialAudit

        db = MagicMock()
        _refresh_ids(db)
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).patch("/api/financial/accounts/acct-1", json={
            "account_type": "savings", "provider": "Wells Fargo", "name": "New Name",
            "balance": "2000.00", "currency": "EUR",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["account_type"] == "savings"
        assert body["provider"] == "Wells Fargo"
        assert body["name"] == "New Name"
        audit = _added_instances(db, FinancialAudit)[0]
        assert audit.operation_type == "UPDATE"
        assert audit.audit_metadata["action_type"] == "update"
        assert audit.audit_metadata["changes"]["provider"]["new"] == "Wells Fargo"

    def test_update_account_partial_fields(self):
        db = MagicMock()
        _refresh_ids(db)
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).patch("/api/financial/accounts/acct-1", json={"name": "Only Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "Only Name"

    def test_update_account_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).patch("/api/financial/accounts/acct-1", json={"name": "X"})
        assert r.status_code == 404

    def test_update_account_governance_denied_403(self, governance):
        governance.can_perform_action.return_value = {"allowed": False, "requires_human_approval": False}
        db = MagicMock()
        r = self._c(db).patch("/api/financial/accounts/acct-1", json={
            "name": "X", "agent_id": "a-1",
        })
        assert r.status_code == 403

    def test_update_account_with_agent_allowed(self, governance):
        db = MagicMock()
        _refresh_ids(db)
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).patch("/api/financial/accounts/acct-1", json={
            "name": "X", "agent_id": "a-1",
        })
        assert r.status_code == 200

    def test_update_account_negative_balance_422(self):
        r = self._c().patch("/api/financial/accounts/acct-1", json={"balance": "-1.00"})
        assert r.status_code == 422

    def test_update_account_requires_auth(self):
        assert self._anon().patch("/api/financial/accounts/acct-1", json={"name": "X"}).status_code == 401

    # -- delete --
    def test_delete_account_success(self):
        from core.models import FinancialAudit

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).delete("/api/financial/accounts/acct-1")
        assert r.status_code == 200
        assert r.json()["message"] == "Financial account deleted successfully"
        audit = _added_instances(db, FinancialAudit)[0]
        assert audit.operation_type == "DELETE"
        assert audit.audit_metadata["action_type"] == "delete"

    def test_delete_account_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).delete("/api/financial/accounts/acct-1")
        assert r.status_code == 404

    def test_delete_account_governance_denied_403(self, governance):
        governance.can_perform_action.return_value = {"allowed": False, "requires_human_approval": False}
        db = MagicMock()
        r = self._c(db).delete("/api/financial/accounts/acct-1", params={"agent_id": "a-1"})
        assert r.status_code == 403

    def test_delete_account_with_agent_allowed(self, governance):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _account()
        r = self._c(db).delete("/api/financial/accounts/acct-1", params={"agent_id": "a-1"})
        assert r.status_code == 200

    def test_delete_account_requires_auth(self):
        assert self._anon().delete("/api/financial/accounts/acct-1").status_code == 401

    # -- net worth snapshot --
    def test_create_snapshot_default_date(self):
        db = MagicMock()
        _refresh_ids(db)
        r = self._c(db).post("/api/financial/net-worth/snapshot", json={
            "net_worth": "1000.00", "assets": "2000.00", "liabilities": "1000.00",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["net_worth"] == "1000.0"
        assert body["snapshot_date"] == str(date.today())

    def test_create_snapshot_with_explicit_date(self):
        from core.models import NetWorthSnapshot

        db = MagicMock()
        _refresh_ids(db)
        r = self._c(db).post("/api/financial/net-worth/snapshot", json={
            "snapshot_date": "2026-03-03",
            "net_worth": "100.00", "assets": "300.00", "liabilities": "200.00",
        })
        assert r.status_code == 201
        assert r.json()["snapshot_date"] == "2026-03-03"
        snap = _added_instances(db, NetWorthSnapshot)[0]
        assert snap.total_assets == 300.0
        assert snap.total_liabilities == 200.0
        assert snap.created_at is not None

    def test_create_snapshot_negative_assets_422(self):
        r = self._c().post("/api/financial/net-worth/snapshot", json={
            "net_worth": "1.00", "assets": "-1.00", "liabilities": "2.00",
        })
        assert r.status_code == 422

    def test_create_snapshot_requires_auth(self):
        assert self._anon().post("/api/financial/net-worth/snapshot", json={
            "net_worth": "1.00", "assets": "1.00", "liabilities": "0.00",
        }).status_code == 401


# =========================================================================== #
# api/enterprise_auth_endpoints.py
# =========================================================================== #
class _FakeUser:
    # class-level attrs the endpoint code references (e.g. User.email in
    # queries) before any instance exists
    email = None
    hashed_password = None
    role = None
    status = None
    tenant_id = None
    workspace_id = None

    def __init__(self, **kw):
        self.id = "u-reg-1"
        self.email = kw.get("email")
        self.first_name = kw.get("first_name")
        self.last_name = kw.get("last_name")
        self.role = kw.get("role")
        self.status = kw.get("status")
        self.created_at = kw.get("created_at")
        self.tenant_id = None
        self.workspace_id = None


class _FakeTenant:
    id = None
    name = None

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.name = kw.get("name")


class _FakeWorkspace:
    id = None
    name = None
    tenant_id = None

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.name = kw.get("name")
        self.tenant_id = kw.get("tenant_id")


class _FakePlanType:
    FREE = SimpleNamespace(value="free")


def _auth_client(db, token="tok-1"):
    from api.enterprise_auth_endpoints import oauth2_scheme, router

    app = _make_app(router)
    app.dependency_overrides[get_db] = lambda: db
    if token is not None:
        app.dependency_overrides[oauth2_scheme] = lambda: token
    return TestClient(app, raise_server_exceptions=False)


class TestEnterpriseAuthEndpoints:
    def _c(self, db=None, token="tok-1"):
        return _auth_client(db or MagicMock(), token=token)

    @pytest.fixture
    def auth_svc(self):
        s = MagicMock()
        s.access_token_expiry = timedelta(hours=1)
        s.create_access_token.return_value = "access-1"
        s.create_refresh_token.return_value = "refresh-1"
        with patch("core.enterprise_auth_service.EnterpriseAuthService", return_value=s):
            yield s

    def _user_record(self, **overrides):
        u = SimpleNamespace(
            id="u-1", email="u@b.com", role="member", status="active",
            hashed_password="hashed",
            first_name="First", last_name="Last",
            workspace_id="w-1", tenant_id="t-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for k, v in overrides.items():
            setattr(u, k, v)
        return u

    def _creds(self, **overrides):
        c = {
            "user_id": "u-1", "username": "u@b.com", "email": "u@b.com",
            "roles": ["member"], "security_level": "standard", "permissions": [],
        }
        c.update(overrides)
        return c

    # -- register --
    def test_register_success(self, auth_svc):
        auth_svc.hash_password.return_value = "hashed"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.models.User", _FakeUser), \
             patch("core.models.Tenant", _FakeTenant), \
             patch("core.models.Workspace", _FakeWorkspace), \
             patch("core.models.PlanType", _FakePlanType):
            r = self._c(db).post("/api/auth/register", json={
                "email": "new@example.com", "password": "SecurePass123!",
                "first_name": "New", "last_name": "User", "role": "member",
            })
        assert r.status_code == 201
        body = r.json()
        assert body["success"] is True
        assert body["data"]["email"] == "new@example.com"

    def test_register_duplicate_email_409(self, auth_svc):
        db = MagicMock()
        r = self._c(db).post("/api/auth/register", json={
            "email": "dup@example.com", "password": "SecurePass123!",
            "first_name": "A", "last_name": "B",
        })
        assert r.status_code == 409

    def test_register_integrity_error_race_409(self, auth_svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.commit.side_effect = IntegrityError("INSERT", {}, Exception("dup"))
        r = self._c(db).post("/api/auth/register", json={
            "email": "race@example.com", "password": "SecurePass123!",
            "first_name": "A", "last_name": "B",
        })
        assert r.status_code == 409
        db.rollback.assert_called_once()

    def test_register_weak_password_422(self, auth_svc):
        r = self._c().post("/api/auth/register", json={
            "email": "a@example.com", "password": "short",
            "first_name": "A", "last_name": "B",
        })
        assert r.status_code == 422

    def test_register_invalid_email_422(self, auth_svc):
        r = self._c().post("/api/auth/register", json={
            "email": "not-an-email", "password": "SecurePass123!",
            "first_name": "A", "last_name": "B",
        })
        assert r.status_code == 422

    def test_register_tenant_creation_failure_still_201(self, auth_svc):
        auth_svc.hash_password.return_value = "hashed"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        class _BoomTenant:
            def __init__(self, **kw):
                raise RuntimeError("tenant service down")

        with patch("core.models.User", _FakeUser), \
             patch("core.models.Tenant", _BoomTenant), \
             patch("core.models.Workspace", _FakeWorkspace), \
             patch("core.models.PlanType", _FakePlanType):
            r = self._c(db).post("/api/auth/register", json={
                "email": "t@example.com", "password": "SecurePass123!",
                "first_name": "T", "last_name": "U",
            })
        assert r.status_code == 201

    def test_register_internal_error_500(self, auth_svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.commit.side_effect = RuntimeError("db down")
        r = self._c(db).post("/api/auth/register", json={
            "email": "x@example.com", "password": "SecurePass123!",
            "first_name": "X", "last_name": "Y",
        })
        assert r.status_code == 500

    # -- login --
    @pytest.fixture
    def login_patch(self):
        with patch("api.enterprise_auth_endpoints._verify_enterprise_credentials") as v:
            yield v

    def test_login_success(self, auth_svc, login_patch):
        login_patch.return_value = self._creds()
        db = MagicMock()
        r = self._c(db).post("/api/auth/login", json={
            "username": "u@b.com", "password": "SecurePass123!",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"] == "access-1"
        assert body["refresh_token"] == "refresh-1"
        assert body["user_id"] == "u-1"
        assert body["roles"] == ["member"]
        assert body["expires_in"] == 3600

    def test_login_user_record_missing(self, auth_svc, login_patch):
        login_patch.return_value = self._creds()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/auth/login", json={
            "username": "u@b.com", "password": "SecurePass123!",
        })
        assert r.status_code == 200

    def test_login_invalid_credentials_401(self, auth_svc, login_patch):
        login_patch.return_value = None
        r = self._c().post("/api/auth/login", json={
            "username": "u@b.com", "password": "wrongpass",
        })
        assert r.status_code == 401

    def test_login_exception_500(self, auth_svc, login_patch):
        login_patch.side_effect = RuntimeError("boom")
        r = self._c().post("/api/auth/login", json={
            "username": "u@b.com", "password": "SecurePass123!",
        })
        assert r.status_code == 500

    def test_login_missing_password_422(self, auth_svc, login_patch):
        r = self._c().post("/api/auth/login", json={"username": "u@b.com"})
        assert r.status_code == 422

    # -- refresh --
    def test_refresh_success_with_credentials(self, auth_svc):
        auth_svc.verify_token.return_value = {"type": "refresh", "user_id": "u-1"}
        auth_svc.verify_credentials.return_value = SimpleNamespace(
            user_id="u-1", username="u@b.com", email="u@b.com",
            roles=["member"], security_level="standard", permissions=[],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record()
        r = self._c(db).post("/api/auth/refresh", json={"refresh_token": "refresh-1"})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"] == "access-1"
        assert body["refresh_token"] == "refresh-1"
        assert body["user_id"] == "u-1"
        auth_svc.verify_credentials.assert_called_once_with(db, "u@b.com", "")

    def test_refresh_success_fallback_credentials(self, auth_svc):
        auth_svc.verify_token.return_value = {"type": "refresh", "user_id": "u-1"}
        auth_svc.verify_credentials.return_value = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record()
        r = self._c(db).post("/api/auth/refresh", json={"refresh_token": "refresh-1"})
        assert r.status_code == 200
        assert r.json()["email"] == "u@b.com"

    def test_refresh_invalid_token_401(self, auth_svc):
        auth_svc.verify_token.return_value = None
        r = self._c().post("/api/auth/refresh", json={"refresh_token": "bad"})
        assert r.status_code == 401

    def test_refresh_wrong_token_type_401(self, auth_svc):
        auth_svc.verify_token.return_value = {"type": "access", "user_id": "u-1"}
        r = self._c().post("/api/auth/refresh", json={"refresh_token": "at"})
        assert r.status_code == 401

    def test_refresh_user_missing_401(self, auth_svc):
        auth_svc.verify_token.return_value = {"type": "refresh", "user_id": "u-1"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/auth/refresh", json={"refresh_token": "rt"})
        assert r.status_code == 401

    def test_refresh_exception_401(self, auth_svc):
        auth_svc.verify_token.side_effect = RuntimeError("boom")
        r = self._c().post("/api/auth/refresh", json={"refresh_token": "rt"})
        assert r.status_code == 401

    def test_refresh_missing_token_422(self, auth_svc):
        r = self._c().post("/api/auth/refresh", json={})
        assert r.status_code == 422

    # -- me --
    def test_me_success(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record()
        r = self._c(db).get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == "u@b.com"
        assert body["data"]["created_at"] is not None
        assert body["data"]["last_login"] is not None

    def test_me_no_timestamps(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record(
            created_at=None, last_login=None
        )
        r = self._c(db).get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["created_at"] is None
        assert body["data"]["last_login"] is None

    def test_me_invalid_token_401(self, auth_svc):
        auth_svc.verify_token.return_value = None
        r = self._c().get("/api/auth/me")
        assert r.status_code == 401

    def test_me_user_missing_404(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "ghost"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/auth/me")
        assert r.status_code == 404

    def test_me_exception_500(self, auth_svc):
        auth_svc.verify_token.side_effect = RuntimeError("boom")
        r = self._c().get("/api/auth/me")
        assert r.status_code == 500

    def test_me_missing_token_401(self, auth_svc):
        r = self._c(token=None).get("/api/auth/me")
        assert r.status_code == 401

    # -- change password --
    def test_change_password_success(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1"}
        auth_svc.verify_password.return_value = True
        auth_svc.hash_password.return_value = "new-hash"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record()
        r = self._c(db).post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "newpass123",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True
        db.commit.assert_called_once()

    def test_change_password_locked_401(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record(status="locked")
        r = self._c(db).post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "newpass123",
        })
        assert r.status_code == 401

    def test_change_password_wrong_old_password_401(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1"}
        auth_svc.verify_password.return_value = False
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._user_record()
        r = self._c(db).post("/api/auth/change-password", json={
            "old_password": "wrongpass", "new_password": "newpass123",
        })
        assert r.status_code == 401

    def test_change_password_user_missing_404(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "ghost"}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "newpass123",
        })
        assert r.status_code == 404

    def test_change_password_invalid_token_401(self, auth_svc):
        auth_svc.verify_token.return_value = None
        r = self._c().post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "newpass123",
        })
        assert r.status_code == 401

    def test_change_password_exception_500(self, auth_svc):
        auth_svc.verify_token.side_effect = RuntimeError("boom")
        r = self._c().post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "newpass123",
        })
        assert r.status_code == 500

    def test_change_password_short_new_422(self, auth_svc):
        r = self._c().post("/api/auth/change-password", json={
            "old_password": "oldpass123", "new_password": "short",
        })
        assert r.status_code == 422

    # -- test-auth + get_current_user_dependency --
    def test_auth_endpoint_success(self, auth_svc):
        auth_svc.verify_token.return_value = {"user_id": "u-1", "roles": ["member"]}
        r = self._c().get("/api/auth/test-auth")
        assert r.status_code == 200
        assert r.json()["message"] == "Authentication working"

    def test_auth_endpoint_invalid_token_401(self, auth_svc):
        auth_svc.verify_token.return_value = None
        r = self._c().get("/api/auth/test-auth")
        assert r.status_code == 401

    # -- require_role / require_permission decorators --
    async def test_require_role_allowed(self):
        from api.enterprise_auth_endpoints import require_role

        @require_role(["admin"])
        async def _wrapped(user):
            return user["roles"]

        assert await _wrapped({"roles": ["admin"]}) == ["admin"]

    async def test_require_role_denied_403(self):
        from api.enterprise_auth_endpoints import require_role

        @require_role(["admin"])
        async def _wrapped(user):
            return user["roles"]

        with pytest.raises(HTTPException) as exc:
            await _wrapped({"roles": ["member"]})
        assert exc.value.status_code == 403

    async def test_require_permission_all_wildcard(self):
        from api.enterprise_auth_endpoints import require_permission

        @require_permission("finance.read")
        async def _wrapped(user):
            return user["permissions"]

        assert await _wrapped({"permissions": ["all"]}) == ["all"]

    async def test_require_permission_granted(self):
        from api.enterprise_auth_endpoints import require_permission

        @require_permission("finance.read")
        async def _wrapped(user):
            return True

        assert await _wrapped({"permissions": ["finance.read"]}) is True

    async def test_require_permission_denied_403(self):
        from api.enterprise_auth_endpoints import require_permission

        @require_permission("finance.read")
        async def _wrapped(user):
            return True

        with pytest.raises(HTTPException) as exc:
            await _wrapped({"permissions": ["other.perm"]})
        assert exc.value.status_code == 403

    # -- credential helpers --
    async def test_verify_enterprise_credentials_legacy_delegates(self):
        from api.enterprise_auth_endpoints import (
            _verify_enterprise_credentials,
            _verify_enterprise_credentials_new,
        )

        with patch("api.enterprise_auth_endpoints._verify_enterprise_credentials_new",
                   new=AsyncMock(return_value={"user_id": "u-1"})) as v:
            result = await _verify_enterprise_credentials("u@b.com", "pw")
        assert result == {"user_id": "u-1"}
        v.assert_awaited_once_with("u@b.com", "pw")
        assert _verify_enterprise_credentials_new is not None

    async def test_verify_enterprise_credentials_new_success(self, auth_svc):
        from api.enterprise_auth_endpoints import _verify_enterprise_credentials_new

        auth_svc.verify_credentials.return_value = SimpleNamespace(
            user_id="u-1", username="u@b.com", email="u@b.com",
            roles=["member"], security_level="standard", permissions=[],
        )
        db = MagicMock()
        with patch("core.database.get_db") as gd:
            gd.return_value.__next__.return_value = db
            result = await _verify_enterprise_credentials_new("u@b.com", "pw")
        assert result["user_id"] == "u-1"
        db.close.assert_called_once()

    async def test_verify_enterprise_credentials_new_invalid(self, auth_svc):
        from api.enterprise_auth_endpoints import _verify_enterprise_credentials_new

        auth_svc.verify_credentials.return_value = None
        with patch("core.database.get_db") as gd:
            gd.return_value.__next__.return_value = MagicMock()
            result = await _verify_enterprise_credentials_new("u@b.com", "bad")
        assert result is None

    async def test_verify_enterprise_credentials_new_exception(self, auth_svc):
        from api.enterprise_auth_endpoints import _verify_enterprise_credentials_new

        auth_svc.verify_credentials.side_effect = RuntimeError("boom")
        with patch("core.database.get_db") as gd:
            gd.return_value.__next__.return_value = MagicMock()
            result = await _verify_enterprise_credentials_new("u@b.com", "pw")
        assert result is None


# =========================================================================== #
# api/learning_plan_routes.py
# =========================================================================== #
class _FakeLearningPlan:
    def __init__(self, **kw):
        self.id = kw.get("id")
        self.user_id = kw.get("user_id")
        self.topic = kw.get("topic")
        self.current_skill_level = kw.get("current_skill_level")
        self.duration_weeks = kw.get("duration_weeks")
        self.modules = kw.get("modules")
        self.progress = kw.get("progress", 0)
        self.status = kw.get("status")
        self.notion_database_id = kw.get("notion_database_id")
        self.learning_goals = kw.get("learning_goals")
        self.time_commitment = kw.get("time_commitment")
        self.preferred_format = kw.get("preferred_format")
        self.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _plan_record(**overrides):
    modules = [
        {
            "week": 1, "title": "Intro", "objectives": ["o1"],
            "resources": [], "exercises": ["e1"], "estimated_hours": 5.0,
        }
    ]
    p = SimpleNamespace(
        id="plan-1",
        user_id="u-1",
        topic="Python",
        current_skill_level="beginner",
        duration_weeks=4,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        progress=25,
        modules={
            "modules": modules,
            "target_skill_level": "intermediate",
            "milestones": ["Week 4: Complete Python foundation course"],
            "assessment_criteria": ["crit"],
            "notion_page_id": None,
            "progress": {"completed_modules": [], "feedback_scores": {}, "time_spent": {}, "adjustments_made": []},
        },
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


class TestLearningPlanRoutes:
    def _c(self, db=None, user=USER):
        from api.learning_plan_routes import router

        return _client(router, db or MagicMock(), user=user)

    def _anon(self, db=None):
        from api.learning_plan_routes import router

        return _anon_client(router, db or MagicMock())

    @pytest.fixture
    def modules(self):
        from api.learning_plan_routes import LearningModule

        return [
            LearningModule(
                week=1, title="Intro to Python", objectives=["Setup"],
                resources=[{"type": "article", "url": "https://x"}],
                exercises=["Hello World"], estimated_hours=5.0,
            )
        ]

    @pytest.fixture
    def gen_modules(self, modules):
        with patch("api.learning_plan_routes.generate_learning_modules",
                   new=AsyncMock(return_value=modules)) as g:
            yield g

    @pytest.fixture
    def notion(self):
        n = MagicMock()
        n.create_page.return_value = {"id": "page-1"}
        with patch("api.learning_plan_routes.NotionService", return_value=n):
            yield n

    def _patch_plan_model(self):
        return patch("api.learning_plan_routes.LearningPlan", _FakeLearningPlan)

    # -- create --
    def test_create_plan_success(self, gen_modules):
        db = MagicMock()
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "Python", "current_skill_level": "beginner",
                "learning_goals": ["Become productive"], "time_commitment": "medium",
                "duration_weeks": 4, "preferred_format": ["articles", "videos"],
            })
        assert r.status_code == 200
        body = r.json()
        assert body["topic"] == "Python"
        assert body["target_skill_level"] == "intermediate"
        assert len(body["modules"]) == 1
        assert body["milestones"] == ["Week 4: Complete Python foundation course"]
        assert len(body["assessment_criteria"]) == 4
        assert body["plan_id"]

    def test_create_plan_notion_export_success(self, gen_modules, notion):
        db = MagicMock()
        token = SimpleNamespace(user_id="u-1", provider="notion", status="active",
                                access_token="plain-token")
        db.query.return_value.filter.return_value.first.return_value = token
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "Rust", "duration_weeks": 8,
                "notion_database_id": "db-1",
            })
        assert r.status_code == 200
        notion.create_page.assert_called_once()
        kwargs = notion.create_page.call_args.args
        assert kwargs[0] == {"type": "database_id", "database_id": "db-1"}
        assert kwargs[1]["Topic"]["title"][0]["text"]["content"] == "Rust"
        assert kwargs[1]["Target Level"]["select"]["name"] == "Intermediate"

    def test_create_plan_notion_export_no_page_id(self, gen_modules, notion):
        notion.create_page.return_value = {"no": "id"}
        db = MagicMock()
        token = SimpleNamespace(user_id="u-1", provider="notion", status="active",
                                access_token="plain-token")
        db.query.return_value.filter.return_value.first.return_value = token
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "Go", "duration_weeks": 4, "notion_database_id": "db-1",
            })
        assert r.status_code == 200

    def test_create_plan_notion_export_exception(self, gen_modules, notion):
        notion.create_page.side_effect = RuntimeError("notion down")
        db = MagicMock()
        token = SimpleNamespace(user_id="u-1", provider="notion", status="active",
                                access_token="plain-token")
        db.query.return_value.filter.return_value.first.return_value = token
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "ML", "duration_weeks": 4, "notion_database_id": "db-1",
            })
        assert r.status_code == 200

    def test_create_plan_notion_no_token_record(self, gen_modules, notion):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "SQL", "duration_weeks": 4, "notion_database_id": "db-1",
            })
        assert r.status_code == 200
        notion.create_page.assert_not_called()

    def test_create_plan_notion_token_without_access_token(self, gen_modules, notion):
        db = MagicMock()
        token = SimpleNamespace(user_id="u-1", provider="notion", status="active",
                                access_token="")
        db.query.return_value.filter.return_value.first.return_value = token
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={
                "topic": "SQL", "duration_weeks": 4, "notion_database_id": "db-1",
            })
        assert r.status_code == 200
        notion.create_page.assert_not_called()

    def test_create_plan_blank_topic_400(self, gen_modules):
        r = self._c().post("/api/v1/learning/plans", json={"topic": "   "})
        assert r.status_code == 400

    def test_create_plan_invalid_skill_level_400(self, gen_modules):
        r = self._c().post("/api/v1/learning/plans", json={
            "topic": "X", "current_skill_level": "guru",
        })
        assert r.status_code == 400

    def test_create_plan_invalid_time_commitment_400(self, gen_modules):
        r = self._c().post("/api/v1/learning/plans", json={
            "topic": "X", "time_commitment": "all-day",
        })
        assert r.status_code == 400

    def test_create_plan_db_error_500(self, gen_modules):
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")
        with self._patch_plan_model():
            r = self._c(db).post("/api/v1/learning/plans", json={"topic": "X"})
        assert r.status_code == 500

    def test_create_plan_invalid_duration_422(self, gen_modules):
        r = self._c().post("/api/v1/learning/plans", json={
            "topic": "X", "duration_weeks": 0,
        })
        assert r.status_code == 422

    def test_create_plan_requires_auth(self, gen_modules):
        r = self._anon().post("/api/v1/learning/plans", json={"topic": "X"})
        assert r.status_code == 401

    # -- get --
    def test_get_plan_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record()
        r = self._c(db).get("/api/v1/learning/plans/plan-1")
        assert r.status_code == 200
        body = r.json()
        assert body["plan_id"] == "plan-1"
        assert body["target_skill_level"] == "intermediate"
        assert body["modules"][0]["title"] == "Intro"

    def test_get_plan_success_legacy_plain_list(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record(
            modules=[{"week": 1, "title": "Legacy", "objectives": [],
                      "resources": [], "exercises": [], "estimated_hours": 1.0}]
        )
        r = self._c(db).get("/api/v1/learning/plans/plan-1")
        assert r.status_code == 200
        assert r.json()["target_skill_level"] == "intermediate"

    def test_get_plan_success_module_instances(self):
        from api.learning_plan_routes import LearningModule

        db = MagicMock()
        rec = _plan_record()
        rec.modules["modules"] = [
            LearningModule(week=1, title="T", objectives=[], resources=[],
                           exercises=[], estimated_hours=1.0)
        ]
        db.query.return_value.filter.return_value.first.return_value = rec
        r = self._c(db).get("/api/v1/learning/plans/plan-1")
        assert r.status_code == 200

    def test_get_plan_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/v1/learning/plans/ghost")
        assert r.status_code == 404

    def test_get_plan_other_user_403(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record(user_id="other")
        r = self._c(db).get("/api/v1/learning/plans/plan-1")
        assert r.status_code == 403

    def test_get_plan_requires_auth(self):
        assert self._anon().get("/api/v1/learning/plans/plan-1").status_code == 401

    # -- list --
    def test_list_plans(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            _plan_record(), _plan_record(id="plan-2", topic="Rust")
        ]
        db.query.return_value.filter.return_value.count.return_value = 2
        r = self._c(db).get("/api/v1/learning/plans", params={"limit": 5, "offset": 10})
        assert r.status_code == 200
        body = r.json()
        assert len(body["plans"]) == 2
        assert body["total"] == 2
        assert body["limit"] == 5
        assert body["offset"] == 10
        assert body["plans"][0]["target_skill_level"] == "intermediate"
        assert body["plans"][0]["progress"] == {
            "completed_modules": [], "feedback_scores": {},
            "time_spent": {}, "adjustments_made": [],
        }

    def test_list_plans_requires_auth(self):
        assert self._anon().get("/api/v1/learning/plans").status_code == 401

    # -- progress --
    def test_update_progress_neutral(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record()
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 4, "time_spent_hours": 3.0,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["adjustments"] == []
        assert body["progress"]["completed_modules"] == ["1"]

    def test_update_progress_remediation(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record()
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 2, "feedback_score": 2, "time_spent_hours": 5.0,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["adjustments"][0]["type"] == "remediation"
        assert len(body["progress"]["adjustments_made"]) == 1

    def test_update_progress_acceleration(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record()
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 3, "feedback_score": 5, "time_spent_hours": 1.0,
        })
        assert r.status_code == 200
        assert r.json()["adjustments"][0]["type"] == "acceleration"

    def test_update_progress_non_dict_progress_reinit(self):
        rec = _plan_record()
        rec.modules["progress"] = "corrupted"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 3, "time_spent_hours": 2.0,
        })
        assert r.status_code == 200
        assert r.json()["progress"]["completed_modules"] == ["1"]

    def test_update_progress_duplicate_week(self):
        rec = _plan_record()
        rec.modules["progress"]["completed_modules"] = ["1"]
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 3, "time_spent_hours": 2.0,
        })
        assert r.status_code == 200
        assert r.json()["progress"]["completed_modules"] == ["1"]

    def test_update_progress_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 3, "time_spent_hours": 1.0,
        })
        assert r.status_code == 404

    def test_update_progress_other_user_403(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record(user_id="other")
        r = self._c(db).post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 3, "time_spent_hours": 1.0,
        })
        assert r.status_code == 403

    def test_update_progress_invalid_score_422(self):
        r = self._c().post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 0, "time_spent_hours": 1.0,
        })
        assert r.status_code == 422

    def test_update_progress_requires_auth(self):
        assert self._anon().post("/api/v1/learning/plans/plan-1/progress", json={
            "module_week": 1, "feedback_score": 3, "time_spent_hours": 1.0,
        }).status_code == 401

    # -- delete --
    def test_delete_plan_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record()
        r = self._c(db).delete("/api/v1/learning/plans/plan-1")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_delete_plan_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).delete("/api/v1/learning/plans/plan-1")
        assert r.status_code == 404

    def test_delete_plan_other_user_403(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _plan_record(user_id="other")
        r = self._c(db).delete("/api/v1/learning/plans/plan-1")
        assert r.status_code == 403

    def test_delete_plan_requires_auth(self):
        assert self._anon().delete("/api/v1/learning/plans/plan-1").status_code == 401

    # -- suggested topics --
    def test_suggested_topics(self):
        r = self._c().get("/api/v1/learning/topics/suggested")
        assert r.status_code == 200
        body = r.json()
        assert body["categories"]["programming"] == [
            "Python", "JavaScript", "TypeScript", "Go", "Rust",
            "Web Development", "Mobile Development", "DevOps",
        ]
        assert body["total_topics"] == 23

    # -- module generators (direct) --
    async def test_generate_learning_modules_llm_success(self):
        from api.learning_plan_routes import LearningModule, generate_learning_modules

        modules = [LearningModule(week=1, title="T", objectives=["o"], resources=[],
                                  exercises=[], estimated_hours=1.0)]
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=SimpleNamespace(modules=modules))
        with patch("api.learning_plan_routes.LLMService", return_value=llm):
            result = await generate_learning_modules(
                topic="Python", current_level="beginner", duration_weeks=4,
                preferred_formats=["articles"], learning_goals=["goal"],
            )
        assert result == modules
        assert llm.generate_structured.await_args.kwargs["temperature"] == 0.4

    async def test_generate_learning_modules_llm_empty_fallback(self):
        from api.learning_plan_routes import generate_learning_modules

        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=SimpleNamespace(modules=[]))
        with patch("api.learning_plan_routes.LLMService", return_value=llm):
            result = await generate_learning_modules(
                topic="Python", current_level="advanced", duration_weeks=4,
                preferred_formats=["articles", "videos", "exercises"],
            )
        assert len(result) == 4

    async def test_generate_learning_modules_llm_none_fallback(self):
        from api.learning_plan_routes import generate_learning_modules

        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=None)
        with patch("api.learning_plan_routes.LLMService", return_value=llm):
            result = await generate_learning_modules(
                topic="Python", current_level="beginner", duration_weeks=4,
                preferred_formats=["articles", "videos", "exercises"],
            )
        assert len(result) == 4

    async def test_generate_learning_modules_llm_error_fallback(self):
        from api.learning_plan_routes import generate_learning_modules

        llm = MagicMock()
        llm.generate_structured = AsyncMock(side_effect=RuntimeError("llm down"))
        with patch("api.learning_plan_routes.LLMService", return_value=llm):
            result = await generate_learning_modules(
                topic="Python", current_level="guru", duration_weeks=4,
                preferred_formats=["articles", "videos", "exercises"],
            )
        assert len(result) == 4
        assert result[0].title.startswith("Python Foundation")

    async def test_generate_learning_modules_fallback_no_formats(self):
        from api.learning_plan_routes import generate_learning_modules

        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=None)
        with patch("api.learning_plan_routes.LLMService", return_value=llm):
            result = await generate_learning_modules(
                topic="Python", current_level="beginner", duration_weeks=2,
                preferred_formats=[],
            )
        assert len(result) == 2
        assert result[0].resources == []
        # duration=2 boundary math: week1 in (d/3, 2d/3] = Application,
        # week2 > 2d/3 = Mastery
        assert result[0].title.startswith("Python Application")
        assert result[1].title.startswith("Python Mastery")

    async def test_generate_milestones_thresholds(self):
        from api.learning_plan_routes import generate_milestones

        assert generate_milestones("T", 3) == []
        assert generate_milestones("T", 4) == ["Week 4: Complete T foundation course"]
        m8 = generate_milestones("T", 8)
        assert len(m8) == 2 and "Week 8" in m8[1]
        m12 = generate_milestones("T", 12)
        assert len(m12) == 3 and "Week 12" in m12[2]
        m16 = generate_milestones("T", 16)
        assert len(m16) == 4 and "Week 16" in m16[3]

    async def test_generate_assessment_criteria(self):
        from api.learning_plan_routes import generate_assessment_criteria

        criteria = generate_assessment_criteria("Python")
        assert len(criteria) == 4
        assert all("Python" in c for c in criteria)

    # -- notion export helper (direct) --
    async def test_export_to_notion_success_with_milestones(self, notion):
        from api.learning_plan_routes import LearningModule, export_learning_plan_to_notion

        plan = SimpleNamespace(
            modules={"modules": [], "milestones": ["M1", "M2"],
                     "target_skill_level": "advanced", "notion_page_id": None},
            notion_database_id="db-1", topic="Python", current_skill_level="beginner",
            duration_weeks=4, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        modules = [
            LearningModule(week=1, title="Intro", objectives=["o1", "o2"],
                           resources=[], exercises=["e1", "e2"], estimated_hours=1.0)
        ]
        page_id = await export_learning_plan_to_notion(plan, modules, "tok")
        assert page_id == "page-1"
        children = notion.create_page.call_args.args[2]
        assert any("Milestones" in str(b) for b in children)
        assert any(b["type"] == "to_do" for b in children)
        assert any(b["type"] == "numbered_list_item" for b in children)

    async def test_export_to_notion_no_milestones_no_objectives(self, notion):
        from api.learning_plan_routes import LearningModule, export_learning_plan_to_notion

        plan = SimpleNamespace(
            modules={"modules": [], "milestones": [],
                     "target_skill_level": "", "notion_page_id": None},
            notion_database_id="db-1", topic="Python", current_skill_level="beginner",
            duration_weeks=4, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        modules = [
            LearningModule(week=1, title="Intro", objectives=[], resources=[],
                           exercises=[], estimated_hours=1.0)
        ]
        page_id = await export_learning_plan_to_notion(plan, modules, "tok")
        assert page_id == "page-1"
        children = notion.create_page.call_args.args[2]
        assert not any("Milestones" in str(b) for b in children)

    async def test_export_to_notion_legacy_plain_modules(self, notion):
        from api.learning_plan_routes import LearningModule, export_learning_plan_to_notion

        plan = SimpleNamespace(
            modules=["legacy", "list"], notion_database_id="db-1", topic="T",
            current_skill_level="beginner", duration_weeks=4,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        page_id = await export_learning_plan_to_notion(plan, [], "tok")
        assert page_id == "page-1"
        kwargs = notion.create_page.call_args.args[1]
        # export derives the TARGET level: beginner + 1 step = intermediate
        assert kwargs["Target Level"]["select"]["name"] == "Intermediate"

    async def test_export_to_notion_no_id_returns_none(self, notion):
        notion.create_page.return_value = {"no": "id"}
        from api.learning_plan_routes import export_learning_plan_to_notion

        plan = SimpleNamespace(
            modules={"modules": [], "milestones": [], "target_skill_level": "",
                     "notion_page_id": None},
            notion_database_id="db-1", topic="T", current_skill_level="beginner",
            duration_weeks=4, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert await export_learning_plan_to_notion(plan, [], "tok") is None

    async def test_export_to_notion_exception_returns_none(self, notion):
        notion.create_page.side_effect = RuntimeError("notion down")
        from api.learning_plan_routes import export_learning_plan_to_notion

        plan = SimpleNamespace(
            modules={"modules": [], "milestones": [], "target_skill_level": "",
                     "notion_page_id": None},
            notion_database_id="db-1", topic="T", current_skill_level="beginner",
            duration_weeks=4, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert await export_learning_plan_to_notion(plan, [], "tok") is None
