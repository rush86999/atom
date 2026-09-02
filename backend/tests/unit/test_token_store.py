"""Unit tests for core.integrations.token_store.

The resolve/revoke DB plumbing was previously copy-pasted across
box_service / google_drive_service / onedrive_service; these tests pin the
shared helper's contract: newest-active-row resolution, refresh-on-near-expiry
with persistence, and loud revocation.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.integrations.token_store import (
    resolve_integration_token,
    revoke_integration_tokens,
)


def _fake_db(row):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
    return db


def _row(expires_at, access_token="encrypted-access", refresh_token="encrypted-refresh"):
    row = MagicMock()
    row.access_token = access_token
    row.refresh_token = refresh_token
    row.expires_at = expires_at
    return row


def test_resolve_returns_none_when_no_row():
    fake_db = _fake_db(None)
    refresh = AsyncMock()
    with patch("core.database.SessionLocal", return_value=fake_db):
        result = asyncio.run(
            resolve_integration_token("u1", ("google", "google_drive", "gmail"), refresh)
        )
    assert result is None
    refresh.assert_not_awaited()


def test_resolve_returns_unexpired_token_without_refresh():
    row = _row(datetime.now(timezone.utc) + timedelta(hours=1))
    fake_db = _fake_db(row)
    refresh = AsyncMock()
    with patch("core.database.SessionLocal", return_value=fake_db), \
            patch("core.privsec.token_encryption.decrypt_token",
                  return_value="plain-access") as dec:
        result = asyncio.run(resolve_integration_token("u1", ("box",), refresh))
    assert result == "plain-access"
    dec.assert_called_once_with("encrypted-access", allow_plaintext=True)
    refresh.assert_not_awaited()
    assert not fake_db.commit.called


def test_resolve_refreshes_near_expiry_and_persists():
    row = _row(datetime.now(timezone.utc) + timedelta(seconds=30))
    fake_db = _fake_db(row)
    refresh = AsyncMock(return_value={"access_token": "new-token", "expires_in": 3600})
    with patch("core.database.SessionLocal", return_value=fake_db), \
            patch("core.privsec.token_encryption.decrypt_token",
                  return_value="plain-refresh") as dec, \
            patch("core.privsec.token_encryption.encrypt_token",
                  side_effect=lambda t: f"enc({t})") as enc:
        result = asyncio.run(resolve_integration_token("u1", ("box",), refresh))
    assert result == "new-token"
    refresh.assert_awaited_once_with("plain-refresh")
    assert row.access_token == "enc(new-token)"
    assert fake_db.commit.called


def test_resolve_returns_none_when_refresh_fails():
    row = _row(datetime.now(timezone.utc) - timedelta(hours=1))
    fake_db = _fake_db(row)
    refresh = AsyncMock(return_value=None)
    with patch("core.database.SessionLocal", return_value=fake_db), \
            patch("core.privsec.token_encryption.decrypt_token", return_value="plain-refresh"):
        result = asyncio.run(resolve_integration_token("u1", ("onedrive",), refresh))
    assert result is None
    assert not fake_db.commit.called


def test_resolve_degrades_to_none_on_db_error():
    with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
        result = asyncio.run(
            resolve_integration_token("u1", ("google",), AsyncMock(return_value=None))
        )
    assert result is None


def test_revoke_updates_rows_and_commits():
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.update.return_value = 3
    with patch("core.database.SessionLocal", return_value=fake_db):
        updated = revoke_integration_tokens(
            "u1", ("onedrive", "microsoft", "outlook", "microsoft365")
        )
    assert updated == 3
    assert fake_db.commit.called
    update_kw = fake_db.query.return_value.filter.return_value.update.call_args.args[0]
    assert list(update_kw.values()) == ["revoked"]


def test_revoke_raises_on_db_failure():
    fake_db = MagicMock()
    fake_db.commit.side_effect = RuntimeError("database is locked")
    with patch("core.database.SessionLocal", return_value=fake_db):
        with pytest.raises(RuntimeError):
            revoke_integration_tokens("u1", ("google",))
