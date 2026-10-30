"""Single-user pilot access boundary: wrong account cannot reach office/canvas."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import canvas_capability_routes, office_routes
from core.auth import get_current_user
from core.database import get_db


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "single_user")
    monkeypatch.setenv("ATOM_PILOT_USER_EMAIL", "pilot@example.com")
    app = FastAPI()
    app.include_router(office_routes.router, prefix="/api/v1/office")
    app.include_router(canvas_capability_routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user-b", email="other@example.com", workspace_id="ws-b")
    app.dependency_overrides[get_db] = lambda: None
    return app


def test_wrong_account_cannot_use_guessed_office_path(app):
    client = TestClient(app)
    response = client.get("/api/v1/office/excel", params={
        "file_path": "/Users/pilot/data/office/guess.xlsx",
        "canvas_id": "guessed-canvas-id",
    })
    assert response.status_code == 403


def test_wrong_account_cannot_use_guessed_canvas_id(app):
    client = TestClient(app)
    response = client.get("/api/canvas/guessed-canvas-id/capability")
    assert response.status_code == 403
