"""Regression tests for the Stripe invoice-connection setup route.

The tests deliberately exercise Atom's real router, models, authentication and
connection service.  The only thing replaced is outbound Stripe HTTP, which is
served by an in-process synthetic responder.  Persistence is redirected to a
throw-away SQLite file under pytest's ``tmp_path`` so the developer's database
can never be touched.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

STRIPE_ROUTE = "/api/integrations/stripe/invoice-connection"
STRIPE_ACCOUNT_URL = "https://api.stripe.com/v1/account"
STRIPE_INTEGRATION_ID = "stripe"

TENANT_ID = "stripe-fixture"
WORKSPACE_ID = "stripe-fixture-workspace"
ADMIN_ID = "stripe-workspace-admin"
MEMBER_ID = "stripe-member"

ACCOUNT_ID = "acct_fixture"
RESTRICTED_KEY = "rk_test_" + "SyntheticFixture000" * 3


@dataclass
class AtomHarness:
    """The real Atom objects, wired to a scratch database."""

    client: TestClient
    session_factory: sessionmaker
    Tenant: Any
    Workspace: Any
    User: Any
    UserConnection: Any
    connection_service: Any
    admin_token: str
    member_token: str


@dataclass
class SyntheticStripe:
    """Mutable state for the mocked Stripe account endpoint."""

    provider_account_id: str = ACCOUNT_ID
    calls: list = field(default_factory=list)
    during_probe: Optional[Callable[[], None]] = None
    expected_key: str = RESTRICTED_KEY


@pytest.fixture()
def atom_harness(tmp_path, monkeypatch) -> AtomHarness:
    """Build an isolated Atom app backed only by a temporary SQLite file."""
    scratch_dir = tmp_path / "stripe-invoice-connection"
    scratch_dir.mkdir()
    db_path = scratch_dir / "scratch.sqlite3"
    assert db_path.resolve().is_relative_to(tmp_path.resolve())

    database_url = f"sqlite:///{db_path}"
    # Set these before importing Atom modules in case their config reads them
    # at import time.  The explicit engine/session redirection below still
    # applies when the modules were already imported by another test.
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ATOM_DATABASE_URL", database_url)
    monkeypatch.setenv("TESTING", "1")

    # AUTOCOMMIT avoids a lingering SQLite read snapshot in the request
    # session, so a role change committed during the provider probe is
    # visible to the route's post-probe revalidation.
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        isolation_level="AUTOCOMMIT",
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    from core import auth as auth_module
    from core import connection_service as connection_service_module
    from core import database as database_module
    from core.database import Base, get_db
    from core.models import Tenant, User, UserConnection, Workspace
    from integrations.stripe_routes import router

    @contextmanager
    def scratch_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_db():
        with scratch_session() as session:
            yield session

    # Route dependencies use get_db; auth and the connection service may have
    # imported get_db_session/SessionLocal by value.  Redirect every one of
    # those module-level names so no code path can reach the real database.
    if hasattr(database_module, "engine"):
        monkeypatch.setattr(database_module, "engine", engine)
    for module in (database_module, auth_module, connection_service_module):
        if hasattr(module, "SessionLocal"):
            monkeypatch.setattr(module, "SessionLocal", session_factory)
        if hasattr(module, "get_db_session"):
            monkeypatch.setattr(module, "get_db_session", scratch_session)
    if not hasattr(connection_service_module, "get_db_session"):
        monkeypatch.setattr(
            connection_service_module, "get_db_session", scratch_session
        )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    harness: Optional[AtomHarness] = None
    try:
        Base.metadata.create_all(bind=engine)

        with scratch_session() as db:
            db.add(
                Tenant(
                    id=TENANT_ID,
                    name="Stripe Fixture",
                    subdomain="stripe-fixture",
                    is_active=True,
                )
            )
            db.flush()
            db.add(
                Workspace(
                    id=WORKSPACE_ID,
                    tenant_id=TENANT_ID,
                    name="Stripe Fixture Workspace",
                    status="active",
                )
            )
            db.flush()

            for user_id, role in (
                (ADMIN_ID, "workspace_admin"),
                (MEMBER_ID, "member"),
            ):
                db.add(
                    User(
                        id=user_id,
                        tenant_id=TENANT_ID,
                        workspace_id=WORKSPACE_ID,
                        role=role,
                        status="active",
                        is_active=True,
                        email=f"{user_id}@example.invalid",
                        first_name="Fixture",
                        last_name="Stripe",
                    )
                )
            db.flush()
            db.commit()

            admin = db.get(User, ADMIN_ID)
            member = db.get(User, MEMBER_ID)
            tokens = {
                "admin": auth_module.create_access_token(
                    {"sub": admin.id}, user=admin
                ),
                "member": auth_module.create_access_token(
                    {"sub": member.id}, user=member
                ),
            }

        harness = AtomHarness(
            client=client,
            session_factory=session_factory,
            Tenant=Tenant,
            Workspace=Workspace,
            User=User,
            UserConnection=UserConnection,
            connection_service=connection_service_module.connection_service,
            admin_token=tokens["admin"],
            member_token=tokens["member"],
        )

        with client:
            yield harness
    finally:
        app.dependency_overrides.clear()
        try:
            Base.metadata.drop_all(bind=engine)
        finally:
            engine.dispose()


@pytest.fixture()
def synthetic_stripe(monkeypatch) -> SyntheticStripe:
    """Replace Stripe's account GET with an in-process synthetic response."""
    state = SyntheticStripe()

    async def fake_get(client, url, **kwargs):
        assert str(url) == STRIPE_ACCOUNT_URL
        # The production route must not follow redirects away from Stripe.
        assert getattr(client, "follow_redirects", False) is False

        headers = httpx.Headers(kwargs.get("headers") or {})
        assert headers.get("authorization") == f"Bearer {state.expected_key}"

        state.calls.append(str(url))
        if state.during_probe is not None:
            state.during_probe()

        return httpx.Response(
            200,
            json={"object": "account", "id": state.provider_account_id},
            request=httpx.Request("GET", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return state


def _body() -> Dict[str, str]:
    return {
        "restricted_key": RESTRICTED_KEY,
        "account_id": ACCOUNT_ID,
    }


def _post(harness: AtomHarness, token: str, body: Optional[dict] = None):
    return harness.client.post(
        STRIPE_ROUTE,
        json=body if body is not None else _body(),
        headers={"Authorization": f"Bearer {token}"},
    )


def _assert_not_exposed(response, *values: str) -> None:
    haystack = "\n".join((response.text, repr(dict(response.headers))))
    for value in values:
        assert value not in haystack


def _connection_count(harness: AtomHarness) -> int:
    with harness.session_factory() as db:
        return db.query(harness.UserConnection).count()


def test_member_is_denied_before_any_provider_call(
    atom_harness: AtomHarness,
    synthetic_stripe: SyntheticStripe,
) -> None:
    response = _post(atom_harness, atom_harness.member_token)

    assert response.status_code in (401, 403), response.text
    _assert_not_exposed(response, RESTRICTED_KEY)
    assert synthetic_stripe.calls == []
    assert _connection_count(atom_harness) == 0


def test_invalid_restricted_key_is_rejected_without_probe(
    atom_harness: AtomHarness,
    synthetic_stripe: SyntheticStripe,
) -> None:
    invalid_key = "synthetic-unrestricted-value"
    response = _post(
        atom_harness,
        atom_harness.admin_token,
        {**_body(), "restricted_key": invalid_key},
    )

    assert response.status_code in (400, 422), response.text
    _assert_not_exposed(response, RESTRICTED_KEY, invalid_key)
    assert synthetic_stripe.calls == []
    assert _connection_count(atom_harness) == 0


def test_mismatched_provider_account_is_not_persisted(
    atom_harness: AtomHarness,
    synthetic_stripe: SyntheticStripe,
) -> None:
    synthetic_stripe.provider_account_id = "acct_different"

    response = _post(atom_harness, atom_harness.admin_token)

    assert response.status_code in (400, 403, 409, 422), response.text
    _assert_not_exposed(response, RESTRICTED_KEY)
    assert synthetic_stripe.calls == [STRIPE_ACCOUNT_URL]
    assert _connection_count(atom_harness) == 0


def test_role_revoked_during_provider_probe_is_denied(
    atom_harness: AtomHarness,
    synthetic_stripe: SyntheticStripe,
) -> None:
    def revoke_admin_role() -> None:
        with atom_harness.session_factory() as db:
            admin = db.get(atom_harness.User, ADMIN_ID)
            assert admin is not None
            admin.role = "member"
            db.commit()

    synthetic_stripe.during_probe = revoke_admin_role

    response = _post(atom_harness, atom_harness.admin_token)

    assert response.status_code == 403, response.text
    _assert_not_exposed(response, RESTRICTED_KEY)
    assert synthetic_stripe.calls == [STRIPE_ACCOUNT_URL]
    assert _connection_count(atom_harness) == 0


def test_verified_admin_connection_is_scoped_and_encrypted(
    atom_harness: AtomHarness,
    synthetic_stripe: SyntheticStripe,
) -> None:
    response = _post(atom_harness, atom_harness.admin_token)

    assert response.status_code in (200, 201), response.text
    _assert_not_exposed(response, RESTRICTED_KEY)
    assert synthetic_stripe.calls == [STRIPE_ACCOUNT_URL]

    payload = response.json()
    assert payload["account"] == ACCOUNT_ID
    assert payload["mode"] == "test"

    with atom_harness.session_factory() as db:
        rows = (
            db.query(atom_harness.UserConnection)
            .filter_by(integration_id=STRIPE_INTEGRATION_ID)
            .all()
        )
        assert len(rows) == 1
        row = rows[0]

        assert row.id == payload["connection_id"]
        assert row.user_id == ADMIN_ID
        assert row.tenant_id == TENANT_ID
        assert row.workspace_id == WORKSPACE_ID

        # The raw key must only ever exist encrypted at rest.
        assert isinstance(row.credentials, str)
        assert RESTRICTED_KEY not in row.credentials

        values = atom_harness.connection_service._decrypt(row.credentials)
        assert values.get("restricted_key") == RESTRICTED_KEY
        assert values.get("account_id") == ACCOUNT_ID
        assert values.get("mode") == "test"
