"""App-record dataset sync — connected apps land in the same dataset catalog.

The `datasets` planner service and the read fast path answer value questions
from `dataset_entries`. Files (spreadsheets) are one producer; this module is
the OTHER: connected apps' records (invoices, payments, items, leads, deals,
charges) synced incrementally into one Parquet per (integration, entity).

Design contract (differs from file datasets by necessity):
- Records are WATERMARK-tracked (max updated/modified time), not byte-hash
  tracked. The Parquet for an entity is replaced IN PLACE on each clean pull
  and the DatasetEntry row updated in place (no version churn) — freshness is
  `synced_at` vs the TTL, the same gate the read fast path already applies.
- Watermarks live ON the DatasetEntry row (source_modified_at): the cursor IS
  the data. A failed pull never advances it.
- Adapters are no-ops without credentials: an install covers exactly the apps
  it connected, with zero per-business configuration. New apps add one
  EntitySpec — the probe/routing/catalog layers need nothing.

Registries: ZohoAdapter (core/integrations/adapters/zoho.py) already
implements the paged, watermark-filtered fetch; QuickBooks/Xero read their
env config; Stripe uses STRIPE_SECRET_KEY when present.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.sheet_dataset_service import (
    _catalog_session,
    _column_schema_json,
    datasets_root,
    sheet_datasets_enabled,
)

logger = logging.getLogger(__name__)

# Schedule + caps (defaults need no configuration).
_SYNC_INTERVAL_MINUTES = max(5, int(os.getenv("ATOM_APP_DATASET_SYNC_MINUTES", "60") or 60))
_MAX_ROWS_PER_ENTITY = max(100, int(os.getenv("ATOM_APP_DATASET_MAX_ROWS", "50000") or 50000))
_STALE_CURSOR = timedelta(days=7)


def app_datasets_enabled() -> bool:
    return sheet_datasets_enabled() and os.getenv("ATOM_APP_DATASETS", "1") != "0"


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _flatten_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Scalars stay; nested dicts/lists become compact JSON strings — Parquet
    columns must be scalars, and agents query values, not structure."""
    out: Dict[str, Any] = {}
    for key, val in record.items():
        if isinstance(val, (dict, list)):
            try:
                out[key] = json.dumps(val, default=str)[:2000]
            except (TypeError, ValueError):
                out[key] = str(val)[:2000]
        elif val is not None and not isinstance(val, (str, int, float, bool)):
            out[key] = str(val)
        else:
            out[key] = val
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Adapter registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EntitySpec:
    """One syncable entity of one integration.

    fetch(workspace_id, since) -> (rows, new_watermark, error)
      rows: flat dicts; new_watermark: max updated-time seen (None = now);
      error: non-None means the pull failed and the cursor must NOT advance.
    configured(): cheap credential check — False = skip silently.
    """

    name: str
    fetch: Callable
    configured: Callable[[], bool]


async def _zoho_context(workspace_id: str):
    """Token + org resolution, mirroring the hybrid sync's proven pattern:
    the 'zoho' IntegrationToken row carries instance_url + credential_metadata
    (organization_id persisted on first discovery). Returns None when no
    active token exists; caller MUST call _close_zoho_context when done."""
    from core.database import SessionLocal
    from core.integrations.adapters.zoho import ZohoAdapter
    from core.models import IntegrationToken

    db = SessionLocal()
    try:
        token = (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.provider == "zoho",
                IntegrationToken.status == "active",
            )
            .first()
        )
        if token is None:
            db.close()
            return None
        instance_url = (token.credential_metadata or {}).get("instance_url") or getattr(token, "instance_url", None)
        adapter = ZohoAdapter(db=db, workspace_id=workspace_id, instance_url=instance_url)
        await adapter.ensure_token()

        org_meta = (token.credential_metadata or {}).get("organization_id")

        async def _resolve_org() -> Optional[str]:
            nonlocal org_meta
            if org_meta:
                return org_meta
            for module in ("books", "inventory"):
                try:
                    orgs = await adapter.get_organizations(module=module)
                except Exception:  # noqa: BLE001
                    orgs = []
                if orgs and orgs[0].get("organization_id"):
                    org_meta = orgs[0]["organization_id"]
                    if token.credential_metadata is None:
                        token.credential_metadata = {}
                    token.credential_metadata["organization_id"] = org_meta
                    db.commit()
                    return org_meta
            return None

        def _commit_org() -> None:
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                pass

        return {
            "adapter": adapter,
            "resolve_org": _resolve_org,
            "commit_org": _commit_org,
            "db": db,
        }
    except Exception:
        db.close()
        raise


def _close_zoho_context(ctx: Any) -> None:
    db = (ctx or {}).get("db")
    if db is not None:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass


async def _zoho_books_invoices(workspace_id: str, since: Optional[datetime]):
    ctx = await _zoho_context(workspace_id)
    if ctx is None:
        return [], None, None
    try:
        org = await ctx["resolve_org"]()
        if not org:
            return [], None, None
        rows = await ctx["adapter"].get_invoices(
            organization_id=org, limit=_MAX_ROWS_PER_ENTITY,
            modified_since=since,
        )
        ctx["commit_org"]()
        if ctx["adapter"].last_error:
            return [], None, f"zoho books invoices: {ctx['adapter'].last_error}"
        return rows, None, None
    finally:
        _close_zoho_context(ctx)


async def _zoho_inventory_items(workspace_id: str, since: Optional[datetime]):
    ctx = await _zoho_context(workspace_id)
    if ctx is None:
        return [], None, None
    try:
        org = await ctx["resolve_org"]()
        if not org:
            return [], None, None
        rows = await ctx["adapter"].get_items(
            organization_id=org, limit=_MAX_ROWS_PER_ENTITY,
            modified_since=since,
        )
        ctx["commit_org"]()
        if ctx["adapter"].last_error:
            return [], None, f"zoho inventory items: {ctx['adapter'].last_error}"
        return rows, None, None
    finally:
        _close_zoho_context(ctx)


async def _zoho_crm_deals(workspace_id: str, since: Optional[datetime]):
    ctx = await _zoho_context(workspace_id)
    if ctx is None:
        return [], None, None
    try:
        rows = await ctx["adapter"].get_deals(limit=1000, modified_since=since)
        if ctx["adapter"].last_error:
            return [], None, f"zoho crm deals: {ctx['adapter'].last_error}"
        return rows, None, None
    finally:
        _close_zoho_context(ctx)


def _zoho_configured() -> bool:
    try:
        from core.database import SessionLocal
        from core.models import IntegrationToken

        with SessionLocal() as db:
            return (
                db.query(IntegrationToken.id)
                .filter(IntegrationToken.provider == "zoho", IntegrationToken.status == "active")
                .first()
                is not None
            )
    except Exception:  # noqa: BLE001
        return False


def _env_configured(*keys: str) -> Callable[[], bool]:
    def _check() -> bool:
        return all(os.getenv(k) for k in keys)
    return _check


async def _quickbooks_invoices(workspace_id: str, since: Optional[datetime]):
    from integrations.quickbooks_service import QuickBooksService

    svc = QuickBooksService()
    rows = await svc.get_invoices(
        os.getenv("QUICKBOOKS_REALM_ID", ""),
        os.getenv("QUICKBOOKS_ACCESS_TOKEN", ""),
        max_results=_MAX_ROWS_PER_ENTITY,
    )
    if since:
        rows = [
            r for r in rows
            if (_parse_dt((r.get("MetaData") or {}).get("LastUpdatedTime")) or _dt_min())
            > since
        ]
    return rows, None, None


def _dt_min() -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


async def _xero_invoices(workspace_id: str, since: Optional[datetime]):
    from integrations.xero_service import XeroService

    svc = XeroService()
    rows = await svc.get_invoices(
        os.getenv("XERO_ACCESS_TOKEN", ""),
        os.getenv("XERO_TENANT_ID", ""),
        limit=_MAX_ROWS_PER_ENTITY,
    )
    if since:
        rows = [
            r for r in rows
            if (_parse_dt(r.get("UpdatedDateUTC")) or _dt_min()) > since
        ]
    return rows, None, None


async def _stripe_charges(workspace_id: str, since: Optional[datetime]):
    from core.integrations.adapters.stripe import StripeAdapter

    adapter = StripeAdapter(db=None, workspace_id=workspace_id)
    # OAuth tokens are memory-only in this deployment; a direct account token
    # (env) is the only durable way to sync. configured() gates on it.
    adapter._access_token = os.getenv("STRIPE_ACCESS_TOKEN")
    gte = int(since.timestamp()) if since else None
    rows = await adapter.get_charges(limit=_MAX_ROWS_PER_ENTITY, created={"gte": gte} if gte else None)
    return rows, None, None


ADAPTERS: Dict[str, List[EntitySpec]] = {
    "zoho": [
        EntitySpec("books_invoices", _zoho_books_invoices, _zoho_configured),
        EntitySpec("inventory_items", _zoho_inventory_items, _zoho_configured),
        EntitySpec("crm_deals", _zoho_crm_deals, _zoho_configured),
    ],
    "quickbooks": [
        EntitySpec("invoices", _quickbooks_invoices, _env_configured("QUICKBOOKS_ACCESS_TOKEN", "QUICKBOOKS_REALM_ID")),
    ],
    "xero": [
        EntitySpec("invoices", _xero_invoices, _env_configured("XERO_ACCESS_TOKEN", "XERO_TENANT_ID")),
    ],
    "stripe": [
        # Stripe OAuth tokens are memory-only in this repo (no IntegrationToken
        # row), so this stays a documented no-op unless a deploy sets a direct
        # account token. Charges watermark on `created`.
        EntitySpec("charges", _stripe_charges, _env_configured("STRIPE_ACCESS_TOKEN")),
    ],
}

# Column extraction for the watermark of a record (first present wins).
_WATERMARK_FIELDS = (
    "last_modified_time", "modified_time", "UpdatedDateUTC",
    "MetaData.LastUpdatedTime", "last_updated", "created",
)


def _record_watermark(rows: List[Dict[str, Any]]) -> Optional[datetime]:
    best: Optional[datetime] = None
    for row in rows:
        for field in _WATERMARK_FIELDS:
            if "." in field:
                nested_key, sub = field.split(".", 1)
                raw = (row.get(nested_key) or {}).get(sub) if isinstance(row.get(nested_key), dict) else None
            else:
                raw = row.get(field)
            dt = _parse_dt(raw)
            if dt and (best is None or dt > best):
                best = dt
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Landing (in-place replace — watermark-tracked, no version churn)
# ─────────────────────────────────────────────────────────────────────────────


# Module-level regexes: never put backslash-patterns inside f-string
# expressions — Python ≤3.11 (the server runtime) rejects them at compile
# time, which silently made sheet_dataset_service unimportable (2026-09-07).
_PARQUET_NAME_SAFE_RE = re.compile(r"[^A-Za-z0-9_\-]")
_ENTITY_ALIAS_RE = re.compile(r"[^a-z0-9_]+")


def _entity_path(workspace_id: str, integration_id: str, entity: str) -> Path:
    safe_ws = re.sub(r"[^A-Za-z0-9_\-]", "_", workspace_id or "default")[:64] or "default"
    path = datasets_root() / safe_ws / "app"
    path.mkdir(parents=True, exist_ok=True)
    name = _PARQUET_NAME_SAFE_RE.sub("_", integration_id + "__" + entity)
    return path / f"{name}.parquet"


def land_app_records_sync(
    workspace_id: str,
    integration_id: str,
    entity: str,
    rows: List[Dict[str, Any]],
    watermark: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Upsert one entity's records as THE dataset for that (app, entity).

    Same bytes as the previous sync → skip (no rewrite, no churn). Changed →
    atomic in-place replace; the single active DatasetEntry row is updated
    (hash, row count, schema, synced watermark), never versioned.
    """
    import pandas as pd

    flat = [_flatten_record(r) for r in rows[:_MAX_ROWS_PER_ENTITY]]
    if not flat:
        return {"status": "skipped", "reason": "no_rows"}
    df = pd.DataFrame(flat)
    now = datetime.now(timezone.utc)
    # Hash the DATA before stamping synced_at — the stamp changes every pull,
    # and a data-changed check that includes it can never answer "current".
    content_hash = hashlib.sha1(df.to_csv(index=False).encode()).hexdigest()
    df["synced_at"] = now.isoformat()

    from core.models import DatasetEntry

    with _catalog_session() as db:
        row = (
            db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "app_records",
                DatasetEntry.source == integration_id,
                DatasetEntry.entity_name == entity,
                DatasetEntry.status == "active",
            )
            .first()
        )
        if row is not None and row.content_hash == content_hash:
            return {"status": "current", "rows": len(df)}

        target = _entity_path(workspace_id, integration_id, entity)
        tmp = target.with_suffix(f".{next(_tmp_counter())}.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, target)

        columns = _column_schema_json(df)
        if row is None:
            row = DatasetEntry(
                workspace_id=workspace_id,
                source_kind="app_records",
                source=integration_id,
                external_id=f"{integration_id}:{entity}",
                file_name=f"{integration_id} {entity}",
                content_hash=content_hash,
                entity_name=entity,
                dataset_name=re.sub(r"[^a-z0-9_]+", "_", f"app_{integration_id}_{entity}".lower())[:80],
                parquet_path=str(target),
                status="active",
            )
            db.add(row)
        row.content_hash = content_hash
        row.parquet_path = str(target)
        row.row_count = int(len(df))
        row.column_count = int(len(df.columns))
        row.columns_json = columns
        row.source_modified_at = watermark or now
        row.ingested_at = now
        db.commit()
    logger.info(
        f"app datasets: synced {integration_id}/{entity} — {len(df)} rows (hash {content_hash[:12]})"
    )
    return {"status": "synced", "rows": int(len(df))}


def _tmp_counter():
    import itertools
    import uuid

    return (f"{uuid.uuid4().hex}{i}" for i in itertools.count())


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


def _last_watermark(workspace_id: str, integration_id: str, entity: str) -> Optional[datetime]:
    from core.models import DatasetEntry

    with _catalog_session() as db:
        row = (
            db.query(DatasetEntry)
            .filter(
                DatasetEntry.source_kind == "app_records",
                DatasetEntry.source == integration_id,
                DatasetEntry.entity_name == entity,
                DatasetEntry.status == "active",
            )
            .first()
        )
        return _parse_dt(row.source_modified_at) if row and row.source_modified_at else None


async def run_app_dataset_syncs(workspace_id: str = "default") -> Dict[str, Any]:
    """One pass over every registered adapter. A failed pull never advances
    its watermark; an unchanged pull is a no-op."""
    if not app_datasets_enabled():
        return {"status": "disabled"}
    summary: Dict[str, Any] = {}
    for integration_id, entities in ADAPTERS.items():
        for spec in entities:
            key = f"{integration_id}/{spec.name}"
            try:
                if not spec.configured():
                    summary[key] = "not_configured"
                    continue
                since = _last_watermark(workspace_id, integration_id, spec.name)
                if since and (datetime.now(timezone.utc) - since) > _STALE_CURSOR:
                    since = None  # stale cursor ⇒ full re-pull for reconciliation
                rows, watermark, error = await spec.fetch(workspace_id, since)
                if error:
                    summary[key] = f"error: {error[:120]}"
                    continue
                if watermark is None:
                    watermark = _record_watermark(rows) or datetime.now(timezone.utc)
                outcome = land_app_records_sync(workspace_id, integration_id, spec.name, rows, watermark)
                summary[key] = outcome.get("status") + (
                    f":{outcome.get('rows')}" if outcome.get("rows") is not None else ""
                )
            except Exception as err:  # noqa: BLE001 — one entity never blocks the rest
                logger.warning(f"app datasets: {key} sync failed: {err}")
                summary[key] = f"error: {str(err)[:120]}"
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Background loop (started from main_api_app beside ENABLE_INGESTION_SYNC)
# ─────────────────────────────────────────────────────────────────────────────

_BACKGROUND_TASKS: set = set()


def start_app_dataset_sync_loop(workspace_id: str = "default") -> None:
    """Hourly pass (ATOM_APP_DATASET_SYNC_MINUTES). Own loop rather than a
    branch in _fetch_integration_data: app datasets must NOT flow into the
    record-ingestion/LanceDB pipeline, and this keeps the hot hybrid module
    untouched."""
    import asyncio

    async def _run() -> None:
        while True:
            try:
                summary = await run_app_dataset_syncs(workspace_id)
                if any(not str(v).startswith(("current", "not_configured", "skipped")) for v in summary.values()):
                    logger.info(f"app datasets: sync pass done: {summary}")
            except Exception as err:  # noqa: BLE001
                logger.warning(f"app datasets: sync pass failed: {err}")
            await asyncio.sleep(_SYNC_INTERVAL_MINUTES * 60)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("app datasets: no running loop; sync loop not started")
        return
    task = loop.create_task(_run())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    logger.info(f"app dataset sync loop started ({_SYNC_INTERVAL_MINUTES}min interval)")
