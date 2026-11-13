"""WA-075 — Active Sessions inventory must describe, and revocation must act.

Scratch-only: every test builds a private file SQLite database under ``tmp_path``
and overrides ``get_db``. The live development database is never opened.

Contract under test (with the real ``get_current_user`` chain, real signed
tokens, and no dependency override of the principal):

* login records exactly one owned inventory row, keyed by jti, never storing
  the raw bearer;
* the listing is owner-scoped and marks ``is_current`` by jti;
* revoking a session writes the durable ``RevokedToken`` ledger, so the
  revoked bearer is refused by ``/api/auth/me`` while other tokens still work;
* another user's session id is a 404 and a forged row cannot revoke its
  owner's token;
* revoke-all keeps the current device and reports that unrecorded tokens may
  remain valid;
* logout deactivates the matching inventory row;
* the effect survives a fresh Python process.
"""
import json
import os
from datetime import datetime, timezone
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.user_management_routes import router as user_mgmt_router
from core.auth import get_password_hash
from core.auth_endpoints import router as auth_router
from core.database import Base, get_db
from core.models import RevokedToken, Tenant, User, UserSession, Workspace

PASSWORD = "InitialPassword1!"


def _add_scope(db):
    for tenant_id in ("default", "t1", "t2"):
        if db.get(Tenant, tenant_id) is None:
            db.add(Tenant(id=tenant_id, name=tenant_id, subdomain="scope-" + tenant_id))
    db.commit()
    for workspace_id in ("default", "ws1", "ws2"):
        if db.get(Workspace, workspace_id) is None:
            db.add(Workspace(id=workspace_id, name=workspace_id, tenant_id="default", status="active"))
    db.commit()


def _make_user(db, user_id: str, email: str, tenant_id: str = "t1") -> User:
    user = User(
        id=user_id,
        email=email,
        first_name=user_id,
        last_name="Tester",
        role="member",
        status="active",
        hashed_password=get_password_hash(PASSWORD),
        tenant_id=tenant_id,
        workspace_id="ws1",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'wa075-contract.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    _add_scope(db)

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(user_mgmt_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        yield SimpleNamespace(db=db, client=client, engine=engine, tmp_path=tmp_path)
    finally:
        db.close()
        engine.dispose()


def _login(client, email: str) -> str:
    response = client.post("/api/auth/login", json={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _claims(token: str):
    from core.auth import decode_token

    payload = decode_token(token)
    assert payload is not None
    return payload


def _inventory(db, user_id: str):
    db.expire_all()
    return db.query(UserSession).filter(UserSession.user_id == user_id).all()


def test_login_records_one_inventory_row_without_the_raw_bearer(world):
    user = _make_user(world.db, "user-a", "a@example.com")
    token = _login(world.client, user.email)
    payload = _claims(token)

    rows = _inventory(world.db, user.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.is_active is True
    assert row.token_jti == payload["jti"]
    assert row.session_token.startswith("sha256:")
    assert token not in row.session_token
    expected = datetime.fromtimestamp(payload["exp"], timezone.utc).replace(tzinfo=None)
    assert row.expires_at.replace(tzinfo=None) == expected


def test_listing_is_owner_scoped_marks_current_and_never_returns_tokens(world):
    user_a = _make_user(world.db, "user-a", "a@example.com")
    user_b = _make_user(world.db, "user-b", "b@example.com")
    token_a = _login(world.client, user_a.email)
    token_b = _login(world.client, user_b.email)

    response = world.client.get("/api/users/sessions", headers={"Authorization": "Bearer " + token_a})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["is_current"] is True
    assert body[0]["revocable"] is True

    rendered = json.dumps(body)
    assert token_a not in rendered
    assert _claims(token_a)["jti"] not in rendered
    assert "sha256:" not in rendered

    other = world.client.get("/api/users/sessions", headers={"Authorization": "Bearer " + token_b})
    assert [row["id"] for row in other.json()] == [
        row.id for row in _inventory(world.db, user_b.id)
    ]


def test_revoking_one_session_kills_that_bearer_only(world):
    user = _make_user(world.db, "user-a", "a@example.com")
    first = _login(world.client, user.email)
    second = _login(world.client, user.email)
    rows = _inventory(world.db, user.id)
    assert len(rows) == 2

    first_jti = _claims(first)["jti"]
    target = next(row for row in rows if row.token_jti == first_jti)
    response = world.client.delete(
        f"/api/users/sessions/{target.id}",
        headers={"Authorization": "Bearer " + first},
    )
    assert response.status_code == 200, response.text
    assert response.json()["verification"]["status"] == "verified"

    receipt = world.db.query(RevokedToken).filter_by(jti=first_jti).one()
    assert receipt.user_id == user.id
    assert receipt.reason == "session_revoked"

    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + first}).status_code == 401
    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + second}).status_code == 200

    listed = world.client.get("/api/users/sessions", headers={"Authorization": "Bearer " + second}).json()
    assert [row["id"] for row in listed] == [
        row.id for row in _inventory(world.db, user.id) if row.is_active
    ]
    assert target.id not in [row["id"] for row in listed]


def test_another_users_session_is_a_404_and_their_token_stays_valid(world):
    user_a = _make_user(world.db, "user-a", "a@example.com")
    user_b = _make_user(world.db, "user-b", "b@example.com")
    token_a = _login(world.client, user_a.email)
    token_b = _login(world.client, user_b.email)
    victim_row = _inventory(world.db, user_b.id)[0]

    response = world.client.delete(
        f"/api/users/sessions/{victim_row.id}",
        headers={"Authorization": "Bearer " + token_a},
    )
    assert response.status_code == 404
    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token_b}).status_code == 200
    assert world.db.query(RevokedToken).count() == 0


def test_forged_inventory_row_cannot_revoke_its_owners_token(world):
    user_a = _make_user(world.db, "user-a", "a@example.com")
    user_b = _make_user(world.db, "user-b", "b@example.com")
    token_a = _login(world.client, user_a.email)
    token_b = _login(world.client, user_b.email)

    # user A somehow has an inventory row holding user B's raw bearer (the
    # pre-WA-075 "record a client token" primitive).
    forged = UserSession(
        id="forged-row",
        user_id=user_a.id,
        session_token=token_b,
        is_active=True,
        expires_at=datetime.fromtimestamp(_claims(token_b)["exp"], timezone.utc),
    )
    world.db.add(forged)
    world.db.commit()

    response = world.client.delete(
        "/api/users/sessions/forged-row",
        headers={"Authorization": "Bearer " + token_a},
    )
    assert response.status_code == 409
    assert response.json()["revoked"] == 0
    assert world.db.query(RevokedToken).count() == 0
    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token_b}).status_code == 200


def test_revoke_all_keeps_the_current_device_and_is_honest_about_untracked_tokens(world):
    user = _make_user(world.db, "user-a", "a@example.com")
    current = _login(world.client, user.email)
    other_a = _login(world.client, user.email)
    other_b = _login(world.client, user.email)
    current_jti = _claims(current)["jti"]

    response = world.client.delete(
        "/api/users/sessions",
        headers={"Authorization": "Bearer " + current},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revoked"] == 2
    assert body["verification"]["status"] == "verified"
    assert body["current_session_tracked"] is True
    # Inventory-based revocation cannot prove other issuance paths are covered.
    assert body["untracked_tokens_possible"] is True
    assert body["residual_window_seconds"] == 24 * 60 * 60

    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + current}).status_code == 200
    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + other_a}).status_code == 401
    assert world.client.get("/api/auth/me", headers={"Authorization": "Bearer " + other_b}).status_code == 401

    rows = {row.token_jti: row for row in _inventory(world.db, user.id)}
    assert rows[current_jti].is_active is True
    assert sum(1 for row in rows.values() if not row.is_active) == 2

    # Idempotent: a second call has nothing left to revoke and changes nothing.
    ledger_before = world.db.query(RevokedToken).count()
    again = world.client.delete("/api/users/sessions", headers={"Authorization": "Bearer " + current})
    assert again.status_code == 200
    assert again.json()["revoked"] == 0
    assert world.db.query(RevokedToken).count() == ledger_before


def test_logout_deactivates_the_matching_inventory_row(world):
    user = _make_user(world.db, "user-a", "a@example.com")
    token = _login(world.client, user.email)

    response = world.client.post("/api/auth/logout", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert response.json()["verification"]["status"] == "verified"
    rows = _inventory(world.db, user.id)
    assert len(rows) == 1 and rows[0].is_active is False


def test_revocation_survives_a_fresh_python_process(world):
    from core import auth as auth_module

    user = _make_user(world.db, "user-a", "a@example.com")
    token = _login(world.client, user.email)
    row = _inventory(world.db, user.id)[0]
    response = world.client.delete(
        f"/api/users/sessions/{row.id}",
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 200

    snapshot = world.tmp_path / "wa075-restart.db"
    source = world.db.connection().connection.driver_connection
    with sqlite3.connect(snapshot) as target:
        source.backup(target)

    program = """
import asyncio, json, sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.auth import get_current_user_ws
payload = json.load(sys.stdin)
with Session(bind=create_engine(payload["database"])) as db:
    print(json.dumps({"allowed": asyncio.run(
        get_current_user_ws(payload["token"], db)) is not None}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        input=json.dumps({"database": "sqlite:///" + str(snapshot), "token": token}),
        env=dict(os.environ, SECRET_KEY=auth_module.SECRET_KEY, TESTING="1"),
        text=True, capture_output=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1])["allowed"] is False


# --- unit surface: the pieces the endpoints rely on -------------------------
def test_token_fingerprint_is_stable_and_never_the_bearer():
    from core.session_registry import token_fingerprint

    token = "header.payload.signature"
    first = token_fingerprint(token)
    assert first == token_fingerprint(token)
    assert token not in first
    assert first.startswith("sha256:")
    assert token_fingerprint(token + "x") != first


@pytest.mark.parametrize("user_agent,expected", [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ("Chrome", "macOS", "desktop"),
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        ("Safari", "iOS", "mobile"),
    ),
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        ("Chrome", "Android", "mobile"),
    ),
    (
        "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        ("Safari", "iOS", "tablet"),
    ),
    (None, (None, None, "desktop")),
])
def test_user_agent_display_heuristic(user_agent, expected):
    from core.session_registry import describe_user_agent

    assert describe_user_agent(user_agent) == expected


def test_heartbeat_upgrades_a_legacy_row_instead_of_storing_the_bearer(world):
    from core.session_registry import token_fingerprint

    user = _make_user(world.db, "user-a", "a@example.com")
    token = _login(world.client, user.email)
    jti = _claims(token)["jti"]

    # Simulate a pre-WA-075 row: raw bearer, no jti.
    row = _inventory(world.db, user.id)[0]
    row.session_token = token
    row.token_jti = None
    world.db.commit()

    response = world.client.post(
        "/api/users/sessions", headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tracked"] is True
    assert body["registered"] is False

    world.db.expire_all()
    upgraded = world.db.get(UserSession, row.id)
    assert upgraded.session_token == token_fingerprint(token)
    assert token not in upgraded.session_token
    assert upgraded.token_jti == jti


def test_sqlite_repair_adds_token_jti_to_a_pre_wa075_table(tmp_path):
    """A local SQLite file created before WA-075 must not break ORM reads."""
    from sqlalchemy import inspect, text

    from core.models import UserSession as SessionModel
    from core.sqlite_schema_repair import ensure_sqlite_columns

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-sessions.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            """
            CREATE TABLE user_sessions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                tenant_id VARCHAR,
                session_token VARCHAR NOT NULL UNIQUE,
                user_agent VARCHAR,
                ip_address VARCHAR,
                device_type VARCHAR,
                browser VARCHAR,
                os VARCHAR,
                is_active BOOLEAN,
                created_at DATETIME,
                last_active_at DATETIME,
                expires_at DATETIME NOT NULL
            )
            """
        ))
        connection.execute(text(
            "INSERT INTO user_sessions (id, user_id, session_token, is_active, expires_at) "
            "VALUES ('legacy', 'user-a', 'raw-bearer', 1, '2027-01-01 00:00:00')"
        ))

    assert "token_jti" not in {column["name"] for column in inspect(engine).get_columns("user_sessions")}
    ensure_sqlite_columns(engine, SessionModel)
    columns = {column["name"] for column in inspect(engine).get_columns("user_sessions")}
    assert "token_jti" in columns

    from sqlalchemy.orm import Session as SaSession

    with SaSession(bind=engine) as db:
        row = db.query(SessionModel).filter(SessionModel.id == "legacy").one()
        assert row.token_jti is None  # legacy rows are resolved lazily
    engine.dispose()
