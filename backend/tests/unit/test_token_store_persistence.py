"""DB-backed refresh-token rotation controls.

These exercise the actual shared resolver against a scratch IntegrationToken
row: replacement refresh tokens must be persisted, omitted replacements must
preserve the old token, and a later resolution must read the persisted value.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from core.database import Base, SessionLocal, engine
import core.models  # noqa: F401
from core.models import IntegrationToken
from core.integrations.token_store import resolve_integration_token


@pytest.fixture()
def token_row(monkeypatch):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(IntegrationToken).filter(
            IntegrationToken.id == "rotation-token"
        ).delete()
        db.add(IntegrationToken(
            id="rotation-token", tenant_id="default", user_id="rotation-user",
            workspace_id="default", provider="onedrive",
            access_token="enc(old-access)", refresh_token="enc(old-refresh)",
            status="active",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
    monkeypatch.setattr(
        "core.privsec.token_encryption.decrypt_token",
        lambda value, allow_plaintext=True: (
            value[4:-1] if str(value).startswith("enc(") else value),
    )
    monkeypatch.setattr(
        "core.privsec.token_encryption.encrypt_token",
        lambda value: f"enc({value})",
    )
    yield
    with SessionLocal() as db:
        db.query(IntegrationToken).filter(
            IntegrationToken.id == "rotation-token"
        ).delete()
        db.commit()


def _stored():
    with SessionLocal() as db:
        return db.query(IntegrationToken).filter(
            IntegrationToken.id == "rotation-token"
        ).one()


def test_replacement_refresh_token_is_persisted_and_read_after_restart(token_row):
    refresh = AsyncMock(return_value={
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
    })
    status = {}
    token = asyncio.run(resolve_integration_token(
        "rotation-user", ("onedrive",), refresh, status_out=status))
    assert token == "new-access"
    assert status["state"] == "refreshed"
    assert status["refresh_token_replaced"] is True
    row = _stored()
    assert row.access_token == "enc(new-access)"
    assert row.refresh_token == "enc(new-refresh)"

    # A fresh resolver call (new session) must use the persisted access token;
    # the refresh callback must not run again.
    second_refresh = AsyncMock()
    second_status = {}
    token = asyncio.run(resolve_integration_token(
        "rotation-user", ("onedrive",), second_refresh,
        status_out=second_status))
    assert token == "new-access"
    assert second_status["state"] == "valid"
    second_refresh.assert_not_awaited()
    assert _stored().refresh_token == "enc(new-refresh)"


def test_omitted_replacement_preserves_existing_refresh_token(token_row):
    refresh = AsyncMock(return_value={
        "access_token": "new-access-2",
        "expires_in": 3600,
    })
    status = {}
    token = asyncio.run(resolve_integration_token(
        "rotation-user", ("onedrive",), refresh, status_out=status))
    assert token == "new-access-2"
    assert status["refresh_token_replaced"] is False
    row = _stored()
    assert row.access_token == "enc(new-access-2)"
    assert row.refresh_token == "enc(old-refresh)"


def test_expired_access_refreshes_then_authorized_graph_read(token_row):
    from integrations.onedrive_service import OneDriveService

    service = OneDriveService()
    service._refresh = AsyncMock(return_value={
        "access_token": "fresh-access",
        "refresh_token": "fresh-refresh",
        "expires_in": 3600,
    })
    service._graph_get = AsyncMock(return_value={
        "id": "disposable-item", "name": "disposable.xlsx",
    })
    token, status = asyncio.run(
        service.get_access_token_resolution("rotation-user"))
    assert token == "fresh-access"
    assert status["state"] == "refreshed"
    assert status["refresh_succeeded"] is True
    result = asyncio.run(service.get_file_metadata(token, "disposable-item"))
    assert result["status"] == "success"
    service._graph_get.assert_awaited_once()
    assert service._graph_get.await_args.args[0] == "fresh-access"
