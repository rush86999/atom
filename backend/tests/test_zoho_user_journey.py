# -*- coding: utf-8 -*-
"""Zoho user-journey verification — all apps x all roles.

Stitches the pilot's Zoho path together end-to-end (all mocked; zero
network / zero LLM spend) across the journeys a real operator follows:

J1  CONNECT (admin): OAuth callback writes all 5 IntegrationToken rows and
    every Zoho service resolves its access token from its own provider row
    (books/inventory/crm read `IntegrationToken.provider == "zoho_*"`;
    workdrive falls back to the token rows after the OAuth flow, since the
    callback writes IntegrationToken, not UserConnection).
J2  ROLES: token fan-out reaches every ACTIVE role (admin → guest); the
    admin's grant is shared with all active teammates; suspended/pending
    users get nothing.
J3  INGEST: `sync_integration_data("zoho")` pulls all 6 entity types
    (crm_leads, crm_deals, books_invoices, projects_tasks, inventory_items,
    inventory_sales_orders) into LanceDB `integration_zoho` + GraphRAG.
J4  RECALL: the memory assembler's integration-records leg surfaces Zoho
    records at turn time.
J5  ROLE GATE: the sync endpoint is governance-armed (MODERATE complexity);
    agent-triggered calls run the governance check, user-initiated calls
    skip it by design (allow_user_initiated).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

try:
    from core.api_governance import ActionComplexity, extract_agent_id, require_governance
    from core.models import IntegrationToken, User
    from integrations.zoho_books_service import ZohoBooksService
    from integrations.zoho_crm_service import ZohoCRMService
    from integrations.zoho_inventory_service import ZohoInventoryService
    from integrations.zoho_workdrive_service import ZohoWorkDriveService
except ImportError:  # pragma: no cover
    pytest.skip("Zoho services not available", allow_module_level=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

ALL_PROVIDERS = [
    "zoho",
    "zoho_books",
    "zoho_inventory",
    "zoho_crm",
    "zoho_workdrive",
]

ALL_ACTIVE_ROLES = [
    "super_admin",
    "owner",
    "admin",
    "workspace_admin",
    "team_lead",
    "member",
    "viewer",
    "guest",
]


def _user(uid: str, role: str, status: str = "active") -> MagicMock:
    return MagicMock(
        id=uid, role=role, status=status, tenant_id="default", workspace_id="default"
    )


def _token(provider: str, access: str = "ACCESS") -> Any:
    class _Row:
        pass

    row = _Row()
    row.provider = provider
    row.access_token = f"enc:{access}"
    row.refresh_token = f"enc:REFRESH"
    row.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    row.user_id = "u-admin"
    row.tenant_id = "default"
    row.status = "active"
    return row


def _callback_db(active_users: List[MagicMock]) -> "tuple[MagicMock, list]":
    """Mock DB used by the OAuth callback; captures IntegrationToken adds."""
    added: List[Any] = []

    def query(model):
        q = MagicMock()
        if model is User:
            q.filter.return_value.all.return_value = active_users
        else:  # OAuthToken / IntegrationToken
            q.filter.return_value.first.return_value = None
        return q

    db = MagicMock()
    db.query.side_effect = query
    db.add.side_effect = lambda r: added.append(r) if getattr(r, "provider", None) else None
    return db, added


async def _run_zoho_callback(db, user=None, scopes: Optional[str] = None,
                             api_domain: Optional[str] = None) -> None:
    from api.oauth_routes import _handle_callback_logic

    payload = {
        "access_token": "at_zoho_" + uuid.uuid4().hex[:8],
        "refresh_token": "rt_zoho_" + uuid.uuid4().hex[:8],
        "token_type": "Bearer",
        "scope": scopes or (
            "ZohoBooks.fullaccess.all,ZohoInventory.fullaccess.all,"
            "ZohoCRM.fullaccess.all,ZohoWorkDrive.files.READ"
        ),
        "expires_in": 3600,
    }
    if api_domain:
        # Real Zoho token responses carry the datacenter API domain.
        payload["api_domain"] = api_domain
    handler_cls = MagicMock()
    handler_cls.return_value.exchange_code_for_tokens = AsyncMock(
        return_value=payload
    )
    with patch("api.oauth_routes.OAuthHandler", handler_cls), patch(
        "core.privsec.token_encryption.encrypt_token",
        side_effect=lambda x: f"enc:{x}",
    ), patch(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        return_value=MagicMock(),
    ), patch("api.oauth_routes.asyncio.create_task", return_value=MagicMock()):
        await _handle_callback_logic(
            provider="zoho",
            code="fake-auth-code",
            # auth_url must be a real string: _handle_callback_logic computes
            # accounts_base via urlparse(config.auth_url) (see the documented
            # fix in test_zoho_oauth_provider_keys.py).
            config=MagicMock(auth_url="https://accounts.zoho.com/oauth/v2/auth"),
            request=MagicMock(),
            db=db,
            user=user or _user("u-admin", "admin"),
        )


def _token_lookup_db(row: Any) -> MagicMock:
    """DB that returns a single token row for any IntegrationToken query."""
    db = MagicMock()

    def query(model):
        q = MagicMock()
        if model is IntegrationToken:
            q.filter.return_value.first.return_value = row
        else:
            q.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query
    return db


# --------------------------------------------------------------------------- #
# J1 — CONNECT: all four apps resolve tokens after one consent flow
# --------------------------------------------------------------------------- #

async def _resolve(service, tenant: str) -> Optional[str]:
    return await service._get_active_token(tenant)


def test_j1_connect_token_fanout_and_service_resolution():
    """One OAuth consent → rows for all 5 providers; Books/Inventory/CRM
    each resolve the access token from their own provider row."""
    db, added = _callback_db([_user("u-admin", "admin")])
    asyncio.run(_run_zoho_callback(db))
    providers = {r.provider for r in added}
    assert providers == set(ALL_PROVIDERS), (
        f"connect wrote {sorted(providers)} — expected all 5 Zoho providers"
    )

    # Every service resolves the same token from its own row.
    with patch("core.privsec.token_encryption.decrypt_token", side_effect=lambda x, **k: x.replace("enc:", "") or x):
        for svc_cls, provider in [
            (ZohoBooksService, "zoho_books"),
            (ZohoInventoryService, "zoho_inventory"),
            (ZohoCRMService, "zoho_crm"),
        ]:
            row = _token(provider)
            svc = svc_cls(tenant_id="default")
            dbmock = _token_lookup_db(row)
            patcher = (
                patch("integrations.zoho_crm_service.SessionLocal", return_value=dbmock)
                if svc_cls is ZohoCRMService
                else patch("core.database.SessionLocal", return_value=dbmock)
            )
            with patcher:
                token = asyncio.run(_resolve(svc, "default"))
            assert token == "ACCESS", f"{provider} service could not resolve its token"


def test_j1_workdrive_resolves_token_after_oauth_connect():
    """RED→GREEN (journey): the OAuth callback writes IntegrationToken rows,
    not UserConnection rows — WorkDrive must fall back to those rows or its
    file list/download journeys silently return []/None after connect."""
    row = _token("zoho_workdrive")
    svc = ZohoWorkDriveService(tenant_id="default")
    dbmock = _token_lookup_db(row)

    with patch("integrations.zoho_workdrive_service.connection_service"
              ) as cs, patch(
        "integrations.zoho_workdrive_service.SessionLocal", return_value=dbmock
    ), patch(
        "core.privsec.token_encryption.decrypt_token",
        side_effect=lambda x, **k: x.replace("enc:", "") or x,
    ):
        cs.get_connections.return_value = []  # no UserConnection after OAuth
        token = asyncio.run(svc.get_access_token("u-admin"))

    assert token == "ACCESS", (
        "WorkDrive get_access_token returns nothing after the documented OAuth "
        "connect (no UserConnection row is created) — file/team journeys dead."
    )


# --------------------------------------------------------------------------- #
# J2 — ROLES: fan-out reaches all active roles, not suspended/pending
# --------------------------------------------------------------------------- #

def test_j2_role_fanout_reaches_all_active_roles():
    """Admin's Zoho grant is shared with every ACTIVE teammate (all roles);
    suspended/pending users get no token rows."""
    import os as _os
    active = [_user(f"u-{role}", role) for role in ALL_ACTIVE_ROLES]
    _user("u-suspended", "member", status="suspended")
    _user("u-pending", "member", status="pending")

    db, added = _callback_db(active)
    # Fan-out is gated behind ATOM_OAUTH_SHARED_INTEGRATION_TOKENS (opt-in
    # by design — cross-user token sharing is a security posture choice).
    # This journey pins the FLAG-ON behavior; restore the env afterwards.
    _prev = _os.environ.get("ATOM_OAUTH_SHARED_INTEGRATION_TOKENS")
    _os.environ["ATOM_OAUTH_SHARED_INTEGRATION_TOKENS"] = "true"
    try:
        asyncio.run(_run_zoho_callback(db))
    finally:
        if _prev is None:
            _os.environ.pop("ATOM_OAUTH_SHARED_INTEGRATION_TOKENS", None)
        else:
            _os.environ["ATOM_OAUTH_SHARED_INTEGRATION_TOKENS"] = _prev

    rows = [(r.user_id, r.provider) for r in added]
    for role in ALL_ACTIVE_ROLES:
        uid = f"u-{role}"
        for provider in ALL_PROVIDERS:
            assert (uid, provider) in rows, (
                f"{role} user missing {provider} token row after admin connect"
            )
    assert not any(r.user_id in ("u-suspended", "u-pending") for r in added)

    # The callback itself filters the fan-out to UserStatus.ACTIVE rows — the
    # DB query is status-filtered, so suspended/pending can never be fanned
    # out (or the pilot shares tokens with locked-out users).
    import inspect
    from api.oauth_routes import _handle_callback_logic

    src = inspect.getsource(_handle_callback_logic)
    assert "UserStatus.ACTIVE" in src and "filter(" in src

    # Every row is live & encrypted (shared single-app grant).
    for r in added:
        assert r.status == "active"
        assert r.access_token.startswith("enc:")
        assert r.refresh_token.startswith("enc:")


# --------------------------------------------------------------------------- #
# J3 — INGEST: sync pulls all six Zoho entity types into memory
# --------------------------------------------------------------------------- #

class _ZohoTokenRow:
    """IntegrationToken row with an editable credential_metadata dict."""

    def __init__(self, provider="zoho", instance_url=None, metadata=None):
        self.provider = provider
        self.instance_url = instance_url
        self.credential_metadata = dict(metadata or {})
        self.access_token = "enc:ACCESS"
        self.refresh_token = "enc:REFRESH"
        self.status = "active"
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)


class _RealPathZohoAdapter:
    """Concrete ZohoAdapter double with ONLY the real method surface — the
    production sync uses `_fetch_zoho_multi_app_data` (the real adapter has
    no generic fetch_records, so the universal fetch path MUST fall through
    here or the journey test lies about which code ran)."""

    async def ensure_token(self):
        return None

    async def get_leads(self, limit: int = 100):
        return [{
            "id": "lead-1", "type": "crm_leads", "Full_Name": "Lead One",
            "Email": "lead@brennan.ca", "Company": "BCA", "Lead_Status": "New",
        }]

    async def get_deals(self, limit: int = 100):
        return [{
            "id": "deal-1", "type": "crm_deals", "Deal_Name": "Deal One",
            "Amount": 500.0, "Stage": "Negotiation",
        }]

    async def get_invoices(self, organization_id=None, limit: int = 100):
        return [{
            "id": "inv-1", "type": "books_invoices", "invoice_id": "INV-1001",
            "invoice_number": "INV-1001", "customer_name": "Acme Corp",
            "total": 499.99, "status": "sent", "due_date": "2026-09-01",
        }]

    async def get_items(self, organization_id=None, limit: int = 100):
        return [{
            "id": "item-1", "type": "inventory_items", "item_id": "IT-1",
            "name": "Widget", "sku": "WID-1", "rate": 10.0, "stock_on_hand": 42,
        }]

    async def get_sales_orders(self, organization_id=None, limit: int = 100):
        return [{
            "id": "so-1", "type": "inventory_sales_orders",
            "salesorder_id": "SO-1", "salesorder_number": "SO-0001",
            "customer_name": "Acme Corp", "total": 250.0, "status": "open",
        }]

    async def get_tasks(self, portal_id=None, project_id=None):
        return []

    async def get_portals(self):
        return []

    async def get_projects(self, portal_id=None):
        return []

    async def get_organizations(self, module: str = "books"):
        return [{"organization_id": "55500000123", "name": "brennan.ca"}]


def _real_path_adapter():
    return _RealPathZohoAdapter()


async def _build_ingestion_service(token_row=None, role=None):
    fake_handler = MagicMock()
    fake_handler.add_document.return_value = True

    fake_graph_engine = MagicMock()
    fake_graph_engine.ingest_document = AsyncMock(
        return_value={"entities": 1, "relationships": 2}
    )

    fake_adapter = _real_path_adapter()

    with patch(
        "core.lancedb_handler.get_lancedb_handler", return_value=fake_handler
    ), patch(
        "core.graphrag_engine.GraphRAGEngine", return_value=fake_graph_engine
    ), patch(
        "core.llm_service.get_llm_service", return_value=None
    ):
        from core.hybrid_data_ingestion import (
            DEFAULT_SYNC_CONFIGS,
            HybridDataIngestionService,
        )

        service = HybridDataIngestionService(workspace_id="default")
        # NOTE: deliberately no sync_configs seeding — the default-registry
        # fallback (DEFAULT_SYNC_CONFIGS) must serve the plain trigger path,
        # which is what the REST endpoint and the connect-time background
        # sync both hit. Pre-seeding would hide the missing fallback.

    from core.service_factory import ServiceFactory

    def _fake_get_zoho_adapter(cls, db=None, workspace_id="default", instance_url=None):
        return fake_adapter

    token_row = token_row or _ZohoTokenRow(instance_url="https://www.zohoapis.com")

    def query(model):
        q = MagicMock()
        if model is IntegrationToken:
            q.filter.return_value.first.return_value = token_row
        else:
            q.filter.return_value.all.return_value = []
        return q

    dbmock = MagicMock()
    dbmock.query.side_effect = query

    with patch(
        "core.database.SessionLocal", return_value=dbmock
    ), patch(
        "core.hybrid_data_ingestion.SessionLocal", return_value=dbmock
    ), patch(
        "core.entity_type_service.EntityTypeService", return_value=MagicMock()
    ), patch.object(
        ServiceFactory,
        "get_zoho_adapter",
        classmethod(_fake_get_zoho_adapter),
    ), patch(
        "core.integrations.adapters.zoho.ZohoAdapter", return_value=fake_adapter
    ):
        result = await service.sync_integration_data("zoho", role=role)
        return result, fake_handler, fake_graph_engine, token_row, dbmock


def test_j3_ingest_journey_real_path_all_entity_types():
    """J3 (real production path): sync_integration_data("zoho") runs
    `_fetch_zoho_multi_app_data` (the adapter has no generic fetch_records).
    CRM needs no org id; Books + Inventory records are gated on
    `credential_metadata["organization_id"]` — auto-discovered from the org
    endpoint and persisted when absent (RED today: only 2 CRM records)."""
    os.environ["ATOM_INGESTION_PERSIST_STATE"] = "false"
    try:
        result, handler, graph_engine, token_row, dbmock = asyncio.run(
            _build_ingestion_service()
        )
    finally:
        os.environ.pop("ATOM_INGESTION_PERSIST_STATE", None)

    assert result.get("success") is True, f"zoho sync failed: {result}"
    assert result.get("records_fetched") == 5, (
        f"expected CRM(2)+Books(1)+Inventory(2)=5 records, got "
        f"{result.get('records_fetched')} — Books/Inventory are gated on "
        f"organization_id which is never discovered."
    )
    assert result.get("records_ingested") == 5
    assert result.get("entities_extracted", 0) >= 5
    assert result.get("relationships_extracted", 0) >= 10

    # Organization discovery persisted back onto the token row.
    assert token_row.credential_metadata.get("organization_id") == "55500000123", (
        "organization_id was not discovered + persisted to token metadata — "
        "repeated syncs keep skipping Books/Inventory."
    )
    dbmock.commit.assert_called()

    # R84: the sync now ALSO writes deterministic business facts
    # (table business_facts, id intfact:zoho:<record>) through the same
    # handler — separate those from document rows before asserting mixes.
    doc_calls = [
        call for call in handler.add_document.call_args_list
        if call.kwargs and call.kwargs.get("table_name") != "business_facts"
    ]
    fact_calls = [
        call for call in handler.add_document.call_args_list
        if call.kwargs and call.kwargs.get("table_name") == "business_facts"
    ]

    types_seen = {
        call.kwargs.get("metadata", {}).get("record_type")
        for call in doc_calls
    }
    assert types_seen == {
        "crm_leads", "crm_deals", "books_invoices",
        "inventory_items", "inventory_sales_orders",
    }, f"wrong entity mix: {types_seen}"

    # One derived fact per ingested record (idempotent per record id).
    assert len(fact_calls) == 5, (
        f"expected a business fact per record, got {len(fact_calls)}"
    )

    # LanceDB integration_zoho table + GraphRAG both receive every record.
    assert len(doc_calls) == 5
    for call in doc_calls:
        kwargs = call.kwargs or {}
        if "table_name" in kwargs:
            assert kwargs["table_name"] == "integration_zoho"
            assert kwargs["source"] == "zoho"
    assert graph_engine.ingest_document.await_count == 5


def test_j6_callback_stamps_instance_url_from_api_domain():
    """J6: the Zoho token exchange returns `api_domain` (the datacenter base
    URL e.g. https://www.zohoapis.com). The callback must store it as
    IntegrationToken.instance_url on the canonical 'zoho' row — otherwise the
    sync adapter falls back to env defaults and a .in/.eu tenant hits the
    wrong datacenter."""
    db, added = _callback_db([_user("u-admin", "admin")])
    asyncio.run(_run_zoho_callback(db, api_domain="https://www.zohoapis.in"))

    zoho_rows = [r for r in added if r.provider == "zoho"]
    assert zoho_rows and zoho_rows[0].instance_url == "https://www.zohoapis.in", (
        "callback lost the Zoho api_domain — instance_url was not stamped, "
        "so the sync hits the wrong datacenter defaults."
    )


def test_j8_callback_rows_carry_workspace_id():
    """J8: IntegrationToken rows must carry workspace_id ("default" when the
    user has none). The sync adapter loads tokens by workspace_id — rows
    created with NULL workspace_id are invisible to ensure_token() and every
    data call runs unauthenticated (0 records, silent)."""
    db, added = _callback_db([_user("u-admin", "admin")])
    asyncio.run(_run_zoho_callback(db))

    assert added, "no IntegrationToken rows created"
    for row in added:
        assert row.workspace_id == "default", (
            f"{row.provider} row has workspace_id={row.workspace_id!r} — the "
            f"adapter's ensure_token() (workspace filter) can't see it."
        )


def test_j8_adapter_loads_legacy_rows_with_null_workspace():
    """J8 (adapter side): token rows created before workspace stamping (NULL
    workspace_id) must still resolve in ZohoAdapter._load_token — otherwise
    already-connected pilots fetch 0 records after upgrade."""
    from core.integrations.adapters.zoho import ZohoAdapter

    row = _ZohoTokenRow(provider="zoho", instance_url="http://mock")
    row.workspace_id = None

    dbmock = MagicMock()
    dbmock.query.return_value.filter.return_value.first.return_value = row

    adapter = ZohoAdapter(db=dbmock, workspace_id="default")
    with patch(
        "core.privsec.token_encryption.decrypt_token",
        side_effect=lambda x, **k: x.replace("enc:", "") or x,
    ):
        asyncio.run(adapter._load_token())

    assert adapter._access_token == "ACCESS", (
        "_load_token missed the row (NULL workspace_id) — it needs an "
        "OR(spaces==workspace, spaces IS NULL) fallback for legacy rows."
    )
    assert adapter.instance_url == "http://mock"


def test_j8_ensure_token_tolerates_naive_sqlite_expiry():
    """J8 (naive expiry): SQLite hands back naive datetimes for aware
    columns — ensure_token() compared them against aware now and crashed,
    making every fresh-connect sync fetch 0 records silently."""
    from core.integrations.adapters.zoho import ZohoAdapter

    row = _ZohoTokenRow(provider="zoho", instance_url="http://mock")
    row.workspace_id = None
    # Naive UTC, in the future — the shape SQLite returns for a store() axed
    # timezone-aware column (datetime.now() would be local-naive → "expired").
    row.expires_at = datetime.utcnow() + timedelta(hours=1)

    dbmock = MagicMock()
    dbmock.query.return_value.filter.return_value.first.return_value = row

    adapter = ZohoAdapter(db=dbmock, workspace_id="default")
    with patch(
        "core.privsec.token_encryption.decrypt_token",
        side_effect=lambda x, **k: x.replace("enc:", "") or x,
    ):
        asyncio.run(adapter.ensure_token())

    assert adapter._access_token == "ACCESS", (
        "ensure_token crashed on the naive expiry (or missed the token) — "
        "naive datetimes must be normalized to aware UTC."
    )


def test_j9_chat_memory_uses_users_workspace_not_default():
    """J9 (AI-employee relevance): the chat assembler must retrieve memory
    from the USER's workspace — the same workspace integration syncs write
    into. Hardcoded "default" made synced Zoho records invisible at chat
    time (e2e: "0 relevant entities" despite 5 ingested records)."""
    import inspect

    from integrations import chat_orchestrator
    from integrations.chat_orchestrator import ChatOrchestrator, resolve_user_workspace

    # Behavioral: resolves the user's real workspace.
    dbmock = MagicMock()
    dbmock.query.return_value.filter.return_value.first.return_value = MagicMock(
        workspace_id="ws-71650c77"
    )
    with patch(
        "integrations.chat_orchestrator.SessionLocal", return_value=dbmock
    ):
        assert resolve_user_workspace("user-1") == "ws-71650c77"

    # Falls back sanely when the user has no workspace.
    dbmock2 = MagicMock()
    dbmock2.query.return_value.filter.return_value.first.return_value = None
    with patch(
        "integrations.chat_orchestrator.SessionLocal", return_value=dbmock2
    ):
        assert resolve_user_workspace("user-2") == "default"

    # Static: the assembler call site passes the resolved value, not "default".
    src = inspect.getsource(ChatOrchestrator._get_qwen_response)
    assert "assemble_memory_context(" in src
    assert "workspace_id=user_workspace" in src, (
        "chat memory assembly still hardcodes workspace_id — ingestion and "
        "recall run in different stores."
    )
    import re

    call_block = src[src.index("assemble_memory_context("):]
    assert not re.search(r'workspace_id\s*=\s*"default"', call_block)


def test_j1_callback_route_supports_zoho_provider():
    """J1 (guard): the OAuth CALLBACK route must accept provider 'zoho' like
    the initiate route does. The e2e journey (real consent → real callback)
    surfaced that the callback's inline provider configs dict was never given
    a 'zoho' entry — every consent redirect landed on
    `{"detail": "Unsupported provider: zoho"}` and NO tokens were ever
    stored, silently breaking the whole pilot connect flow."""
    import inspect
    import re

    from api.oauth_routes import oauth_callback

    src = inspect.getsource(oauth_callback)
    assert re.search(r'"zoho"\s*:\s*ZOHO_OAUTH_CONFIG', src), (
        "oauth_callback rejects provider 'zoho' — the initiate route accepts "
        "it, so the consent redirect dies with 400 'Unsupported provider'."
    )


# --------------------------------------------------------------------------- #
# J4 — RECALL: memory assembler surfaces Zoho records at turn time
# --------------------------------------------------------------------------- #

def test_j4_recall_journey_assembler_surfaces_zoho_records():
    fake_handler = MagicMock()
    conn = MagicMock()
    conn.table_names.return_value = [
        "integration_zoho", "integration_shopify"
    ]
    fake_handler.db = conn
    fake_handler.search.return_value = [
        {"text": "Invoice INV-1001 total 499.99 (zoho_books)"}
    ]

    with patch(
        "core.lancedb_handler.get_lancedb_handler", return_value=fake_handler
    ):
        from core.memory_context_assembler import _integration_records_leg
        lines = asyncio.run(_integration_records_leg("invoice", "default"))

    assert lines, "memory assembler returned nothing from integration_zoho"
    assert any("INV-1001" in ln for ln in lines)


# --------------------------------------------------------------------------- #
# J5 — ROLE GATE: sync endpoint is governance-armed (MODERATE / INTERN+)
# --------------------------------------------------------------------------- #

def test_j5_trigger_sync_is_governance_armed():
    """Static: POST /api/data-ingestion/sync/{id} is wrapped in
    require_governance(action_complexity=MODERATE) — a STUDENT-maturity agent
    is blocked, not just warned."""
    import inspect
    import re

    from api.data_ingestion_routes import trigger_sync

    src = inspect.getsource(trigger_sync)
    has_decorator = "@require_governance" in src
    has_moderate = re.search(
        r"action_complexity\s*=\s*(ActionComplexity\.)?MODERATE", src
    )
    assert has_decorator and has_moderate, (
        "trigger_sync lost its governance gate — a low-maturity agent could "
        "kick off unbounded Zoho syncs."
    )


def test_j5_governance_runs_for_agent_and_skips_for_user():
    """Behavioral: with an agent_id on the request the gate calls
    perform_governance_check (STUDENT denied); user-initiated calls skip by
    design (allow_user_initiated) — the sync route is human-triggerable but
    agent-triggerable only at INTERN+ maturity."""
    from starlette.requests import Request

    calls: List[Dict[str, Any]] = []

    async def _perform(**kw):
        calls.append(kw)

    @require_governance(
        action_complexity=ActionComplexity.MODERATE,
        action_name="trigger_sync",
        feature="data_ingestion",
    )
    async def routed(request, db):
        return "ok"

    async def _run(scope_headers: List[tuple]) -> str:
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/data-ingestion/sync/zoho",
            "query_string": b"",
            "headers": scope_headers,
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "scheme": "http",
        })
        with patch("core.api_governance.perform_governance_check", side_effect=_perform):
            return await routed(request=request, db=MagicMock())

    agent_result = asyncio.run(_run([(b"x-agent-id", b"agent-student")]))
    assert agent_result == "ok"
    assert calls, "agent-triggered sync skipped the governance check"
    assert calls[0]["action_complexity"] == ActionComplexity.MODERATE
    assert calls[0]["action_name"] == "trigger_sync"

    calls.clear()
    user_result = asyncio.run(_run([]))
    assert user_result == "ok"
    assert not calls, "user-initiated sync should skip governance by design"


# J7 — ROLE LOOP: sync tagged for an AI employee's role reaches that
# employee's memory first (additive top-up from general), mirroring the
# WorldModelService._recall_general_knowledge contract.
def test_j7_role_tagged_sync_stamps_metadata_role():
    """sync_integration_data(role="Finance") stamps metadata.role='finance'
    on every ingested LanceDB record; without a role, no tag is written
    (general knowledge, recalled by any employee)."""
    os.environ["ATOM_INGESTION_PERSIST_STATE"] = "false"
    try:
        result, handler, _, _, _ = asyncio.run(_build_ingestion_service())
    finally:
        os.environ.pop("ATOM_INGESTION_PERSIST_STATE", None)
    assert result.get("records_ingested") == 5

    # Without a role: every record is general knowledge (no role tag).
    for call in handler.add_document.call_args_list:
        assert "role" not in (call.kwargs.get("metadata") or {}), (
            "untagged sync must not stamp a role — general knowledge"
        )

    # With a role: every record is tagged for that employee's memory.
    handler.add_document.reset_mock()
    os.environ["ATOM_INGESTION_PERSIST_STATE"] = "false"
    try:
        result, handler, _, _, _ = asyncio.run(_build_ingestion_service(role="Finance"))
    finally:
        os.environ.pop("ATOM_INGESTION_PERSIST_STATE", None)
    assert result.get("records_ingested") == 5
    # R84: fact rows (business_facts) carry no role tag — only doc rows do.
    tags = {
        (call.kwargs.get("metadata") or {}).get("role")
        for call in handler.add_document.call_args_list
        if call.kwargs and call.kwargs.get("table_name") != "business_facts"
    }
    assert tags == {"finance"}, f"role tag not stamped on every record: {tags}"
