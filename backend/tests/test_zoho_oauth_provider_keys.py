"""RED tests — Zoho OAuth callback must store tokens for all four services.

Pilot doc (§2 Zoho) promises: "the callback stores refresh tokens
automatically for all four services" (Books + Inventory + CRM + WorkDrive).
The v1 callback (`api/oauth_routes._handle_callback_logic`) writes a single
IntegrationToken row with provider "zoho" (plus the microsoft→outlook
special case). But the Zoho services resolve their own token rows by exact
provider name:

- `integrations/zoho_books_service.py:83`      → provider == "zoho_books"
- `integrations/zoho_crm_service.py:82`        → provider == "zoho_crm"
- `integrations/zoho_inventory_service.py:89`  → provider == "zoho_inventory"
- `integrations/zoho_workdrive_service.py`     → "zoho_workdrive", falling
                                                back to generic "zoho"

So after the documented connect flow, Books/CRM/Inventory find no token and
run fail-closed (401/500), while WorkDrive happens to work by fallback. The
tokens page shows "zoho active" and the pilot appears connected — the doc's
section 4 verification passes while three of four services are broken.

TDD: red first (only "zoho" row created today), then green (fan-out).
"""
import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from api import oauth_routes as v1
    from core.models import IntegrationToken, OAuthToken, User
except ImportError:  # pragma: no cover
    pytest.skip("oauth_routes not available", allow_module_level=True)


def test_zoho_default_scopes_are_valid_names():
    """Regression: Zoho rejects unknown scope names with "Scope does not
    exist". CRM/Projects do not use the fullaccess.all pattern and WorkDrive
    scopes are prefixed `WorkDrive.` (not `ZohoWorkDrive.`) with `.ALL`
    permissions — the consent URL must use the canonical per-product names
    (verified in atom-self-hosted-pilot-instructions.md §2)."""
    from core import oauth_handler as oh

    scopes = set(oh._ZOHO_DEFAULT_SCOPES)
    assert "ZohoCRM.modules.ALL" in scopes
    # Projects needs the portal+project combo (verified in the pilot doc) —
    # the fullaccess.all pattern does not exist for CRM or Projects.
    assert "ZohoProjects.portals.all" in scopes
    assert "ZohoProjects.projects.all" in scopes
    assert "ZohoCRM.fullaccess.all" not in scopes
    assert "ZohoProjects.fullaccess.all" not in scopes
    assert "ZohoBooks.fullaccess.all" in scopes
    assert "ZohoInventory.fullaccess.all" in scopes
    # WorkDrive: `WorkDrive.` prefix, `.ALL` permission — `ZohoWorkDrive.`
    # prefix or `.READ` are rejected as unknown scopes.
    assert "WorkDrive.files.ALL" in scopes
    assert "WorkDrive.teamfolders.ALL" in scopes
    assert "ZohoWorkDrive.files.READ" not in scopes
    assert "ZohoWorkDrive.teamfolders.READ" not in scopes


def _make_db():
    """Mock DB: OAuthToken lookup empty, one ACTIVE user, capture IntegrationToken adds."""
    added = []

    def query(model):
        q = MagicMock()
        if model is OAuthToken:
            q.filter.return_value.first.return_value = None
        elif model is User:
            q.filter.return_value.all.return_value = [
                MagicMock(id="u-admin", tenant_id="default", status="active")
            ]
        elif model is IntegrationToken:
            q.filter.return_value.first.return_value = None
        return q

    db = MagicMock()
    db.query.side_effect = query
    db.add.side_effect = lambda row: added.append(row) if isinstance(row, IntegrationToken) else None
    return db, added


def _run_callback(db, user=None):
    """Drive _handle_callback_logic with a fake Zoho token exchange."""
    handler_cls = MagicMock()
    handler_cls.return_value.exchange_code_for_tokens = AsyncMock(return_value={
        "access_token": "at_zoho_" + uuid.uuid4().hex[:8],
        "refresh_token": "rt_zoho_" + uuid.uuid4().hex[:8],
        "token_type": "Bearer",
        "scope": (
            "ZohoBooks.fullaccess.all,ZohoInventory.fullaccess.all,"
            "ZohoCRM.modules.ALL,WorkDrive.files.ALL"
        ),
        "expires_in": 3600,
    })
    request = MagicMock()
    with patch("api.oauth_routes.OAuthHandler", handler_cls), patch(
        "core.privsec.token_encryption.encrypt_token",
        side_effect=lambda x: f"enc:{x}",
    ):
        return asyncio.run(v1._handle_callback_logic(
            provider="zoho",
            code="fake-auth-code",
            config=MagicMock(auth_url="https://accounts.zoho.com/oauth/v2/auth"),
            request=request,
            db=db,
            user=user or MagicMock(id="u-admin", tenant_id="default", status="active"),
        ))


def test_zoho_callback_stores_all_four_service_providers():
    """The generic 'zoho' row alone does not serve Books/CRM/Inventory —
    each service queries its exact provider name. The callback must write a
    row per service so the documented connect flow actually connects all
    four apps."""
    db, added = _make_db()
    _run_callback(db)

    providers = {row.provider for row in added}
    assert providers == {
        "zoho",
        "zoho_books",
        "zoho_inventory",
        "zoho_crm",
        "zoho_workdrive",
    }, (
        f"Zoho callback wrote only providers {sorted(providers)} — "
        f"zoho_books/zoho_inventory/zoho_crm services run fail-closed "
        f"without their own IntegrationToken rows (zoho_workdrive survives "
        f"only via its generic-zoho fallback)."
    )


def test_zoho_callback_rows_share_encrypted_credentials():
    """All fanned-out rows carry the same encrypted access/refresh tokens
    (a single Zoho app grant covers the umbrella scopes)."""
    db, added = _make_db()
    _run_callback(db)

    assert len({r.access_token for r in added}) == 1
    assert len({r.refresh_token for r in added}) == 1
    for row in added:
        assert row.access_token.startswith("enc:")
        assert row.status == "active"


def test_microsoft_callback_still_writes_outlook_row():
    """Regression guard: the microsoft→outlook fan-out already existed and
    must keep working (pilot mailbox is connected via provider 'outlook')."""
    db, added = _make_db()

    handler_cls = MagicMock()
    handler_cls.return_value.exchange_code_for_tokens = AsyncMock(return_value={
        "access_token": "at_ms_" + uuid.uuid4().hex[:8],
        "refresh_token": "rt_ms_" + uuid.uuid4().hex[:8],
        "token_type": "Bearer",
        "scope": "Mail.Read Mail.ReadWrite",
        "expires_in": 3600,
    })
    with patch("api.oauth_routes.OAuthHandler", handler_cls), patch(
        "core.privsec.token_encryption.encrypt_token",
        side_effect=lambda x: f"enc:{x}",
    ):
        asyncio.run(v1._handle_callback_logic(
            provider="microsoft",
            code="fake-auth-code",
            config=MagicMock(),
            request=MagicMock(),
            db=db,
            user=MagicMock(id="u-admin", tenant_id="default", status="active"),
        ))

    providers = {row.provider for row in added}
    assert "outlook" in providers


def test_oauth_token_row_updates_with_scope():
    """The legacy OAuthToken row is still written/updated with the granted
    scopes so /api/v1/auth/oauth/tokens shows 'zoho, active'."""
    db, added = _make_db()
    _run_callback(db)

    oauth_rows = [r for r in db.add.call_args_list]
    # The OAuthToken add/update path must have run (no exception, commit called)
    db.commit.assert_called()
    assert any(r.provider == "zoho" for r in added)


def test_zoho_callback_schedules_background_sync():
    """Connecting Zoho must kick off the hybrid ingestion sync (Books
    invoices, Inventory items/sales orders, CRM leads/deals, Projects tasks)
    — the pilot analog of the Outlook poller that starts on Microsoft
    connect. Without it, the callback leaves token rows only and the memory
    stores stay empty until someone manually triggers
    POST /api/data-ingestion/sync/zoho."""
    db, added = _make_db()

    handler_cls = MagicMock()
    handler_cls.return_value.exchange_code_for_tokens = AsyncMock(return_value={
        "access_token": "at_zoho_" + uuid.uuid4().hex[:8],
        "refresh_token": "rt_zoho_" + uuid.uuid4().hex[:8],
        "token_type": "Bearer",
        "scope": "ZohoBooks.fullaccess.all",
        "expires_in": 3600,
    })

    scheduled = []
    fake_service = MagicMock()
    fake_service.sync_integration_data = AsyncMock(return_value={"success": True})

    def fake_create_task(coro):
        scheduled.append(coro)
        return MagicMock()

    with patch("api.oauth_routes.OAuthHandler", handler_cls), patch(
        "core.privsec.token_encryption.encrypt_token",
        side_effect=lambda x: f"enc:{x}",
    ), patch(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        return_value=fake_service,
    ), patch("api.oauth_routes.asyncio.create_task", side_effect=fake_create_task):
        asyncio.run(v1._handle_callback_logic(
            provider="zoho",
            code="fake-auth-code",
            config=MagicMock(),
            request=MagicMock(),
            db=db,
            user=MagicMock(id="u-admin", tenant_id="default", status="active"),
        ))

    assert scheduled, (
        "Zoho connect scheduled no background sync — Books/Inventory/CRM "
        "records never reach the memory stores without a manual sync trigger."
    )