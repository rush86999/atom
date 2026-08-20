"""Tests for api/scim_routes.py — SCIM v2 user provisioning.

DB/test conventions mirror tests/api/test_sso_oidc_routes.py (sqlite StaticPool
engine, per-test session, get_db dependency override). SCIM auth is a dedicated
bearer token from ATOM_SCIM_TOKEN (unset -> 503, wrong -> 401).
"""
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api.scim_routes import install_scim_exception_handlers, router
from core.database import Base, get_db
from core.models import User

TOKEN = "test-scim-token"


@pytest.fixture(scope="module")
def engine():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    os.unlink(path)


@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture()
def client(db, monkeypatch):
    monkeypatch.setenv("ATOM_SCIM_TOKEN", TOKEN)
    app = FastAPI()
    app.include_router(router)
    install_scim_exception_handlers(app)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)


@pytest.fixture()
def no_token_client(db, monkeypatch):
    monkeypatch.delenv("ATOM_SCIM_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(router)
    install_scim_exception_handlers(app)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)


def _auth_headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def _create(client, email="scim.user@example.com", active=True):
    resp = client.post(
        "/api/scim/v2/Users",
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": email,
            "name": {"givenName": "Scim", "familyName": "User"},
            "active": active,
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Auth


def test_disabled_without_token_env(no_token_client):
    resp = no_token_client.get("/api/scim/v2/Users", headers=_auth_headers())
    assert resp.status_code == 503
    assert resp.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]


def test_wrong_token_401(client):
    resp = client.get("/api/scim/v2/Users", headers=_auth_headers("wrong"))
    assert resp.status_code == 401
    body = resp.json()
    assert body["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]
    assert body["status"] == "401"


def test_missing_token_401(client):
    assert client.get("/api/scim/v2/Users").status_code == 401


# --------------------------------------------------------------------------- #
# Create / get roundtrip


def test_create_and_get_roundtrip(client):
    created = _create(client, "Round.Case@Example.com")
    assert created["userName"] == "round.case@example.com"  # lowercased
    assert created["active"] is True
    assert created["name"]["givenName"] == "Scim"
    assert created["meta"]["location"].endswith(created["id"])

    resp = client.get(f"/api/scim/v2/Users/{created['id']}", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:User"]


def test_create_duplicate_409(client):
    _create(client)
    resp = client.post(
        "/api/scim/v2/Users",
        json={"userName": "SCIM.USER@example.com"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# List + pagination + filter


def test_list_pagination(client):
    for i in range(5):
        _create(client, f"user{i}@example.com")
    resp = client.get(
        "/api/scim/v2/Users", params={"startIndex": 2, "count": 2}, headers=_auth_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalResults"] == 5
    assert body["startIndex"] == 2
    assert body["itemsPerPage"] == 2
    assert len(body["Resources"]) == 2


def test_list_filter_eq(client):
    _create(client, "alice@example.com")
    _create(client, "bob@example.com")
    resp = client.get(
        "/api/scim/v2/Users",
        params={"filter": 'userName eq "alice@example.com"'},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalResults"] == 1
    assert body["Resources"][0]["userName"] == "alice@example.com"


def test_list_filter_co(client):
    _create(client, "alice@example.com")
    _create(client, "bob@example.com")
    resp = client.get(
        "/api/scim/v2/Users",
        params={"filter": 'userName co "example"'},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["totalResults"] == 2


def test_list_filter_malformed_400(client):
    resp = client.get(
        "/api/scim/v2/Users",
        params={"filter": 'name.givenName ew "x"'},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert resp.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]


# --------------------------------------------------------------------------- #
# PATCH


def test_patch_deactivate_and_reactivate(client):
    user = _create(client)
    resp = client.patch(
        f"/api/scim/v2/Users/{user['id']}",
        json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    resp = client.patch(
        f"/api/scim/v2/Users/{user['id']}",
        json={"Operations": [{"op": "replace", "path": "active", "value": True}]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is True


def test_patch_display_name(client):
    user = _create(client)
    resp = client.patch(
        f"/api/scim/v2/Users/{user['id']}",
        json={"Operations": [{"op": "replace", "path": "displayName", "value": "Ada Lovelace"}]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "Ada Lovelace"


# --------------------------------------------------------------------------- #
# PUT / DELETE / 404


def test_put_replace(client):
    user = _create(client)
    resp = client.put(
        f"/api/scim/v2/Users/{user['id']}",
        json={
            "userName": user["userName"],
            "name": {"givenName": "New", "familyName": "Name"},
            "active": False,
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == {"givenName": "New", "familyName": "Name"}
    assert body["active"] is False


def test_delete_deactivates(client, db):
    user = _create(client)
    resp = client.delete(f"/api/scim/v2/Users/{user['id']}", headers=_auth_headers())
    assert resp.status_code == 204
    row = db.query(User).filter(User.id == user["id"]).first()
    assert row is not None  # soft delete only
    assert row.is_active is False
    assert row.status == "deleted"
    # SCIM-active is now false and the user is excluded from default listings
    got = client.get(f"/api/scim/v2/Users/{user['id']}", headers=_auth_headers())
    assert got.status_code == 200
    assert got.json()["active"] is False


def test_get_missing_404(client):
    resp = client.get("/api/scim/v2/Users/nope", headers=_auth_headers())
    assert resp.status_code == 404
    assert resp.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]


def test_patch_missing_404(client):
    resp = client.patch(
        "/api/scim/v2/Users/nope",
        json={"Operations": []},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


def test_delete_missing_404(client):
    assert client.delete("/api/scim/v2/Users/nope", headers=_auth_headers()).status_code == 404
