"""Org Ingestion Hub — continuous org-wide sync (Phase 3).

Org Ingestion Sharing Phase 3
(docs/architecture/ORG_INGESTION_SHARING_PLAN.md): one designated always-on
instance (the hub) owns the org-source connections; members pull signed
delta bundles on a schedule and apply them through the normal Phase 2 import
path. Personal sources never touch the hub.

Design:
- The hub reuses the Phase 2 bundle envelope (kind, records, tombstones,
  signature) plus a monotonic per-source cursor. Members request
  ``?since=<cursor>&sources=...`` and get back only records newer than the
  cursor, capped at the Phase 2 record cap. Cursor = (max updated_at,
  last external_id) per source — monotonic because the hub is the single
  writer for org sources.
- Auth: hub endpoints authenticate ``atom_sk_*`` gateway keys
  (``core/llm/gateway/auth.get_gateway_identity``) — the plan reuses the
  GatewayApiKey mechanism instead of a new table.
- Members persist their cursor in ``ingestion_settings.usage_stats_json``
  (integration_id ``org_hub``) so it survives restarts via Phase 0
  persistence, and a background pull loop in ``main_api_app`` runs on an
  interval when configured.
- Killed hub = members degrade to stale-but-functional local data: the pull
  loop catches all errors and simply retries next interval.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

HUB_CURSOR_INTEGRATION = "org_hub"


class HubError(ValueError):
    """Raised for structurally invalid hub requests (never swallowed)."""


def _normalize_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def cursor_to_json(cursor: Optional[Dict[str, Dict[str, Any]]]) -> Optional[str]:
    """Serialize the per-source cursor to the wire format (or None)."""
    if not cursor:
        return None
    return json.dumps(cursor, sort_keys=True, separators=(",", ":"))


def cursor_from_json(raw: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Parse the wire-format cursor. Invalid/garbage input → empty cursor
    (full snapshot), never a crash."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        logger.warning("Ignoring malformed org-hub cursor")
    return {}


class OrgHubService:
    """Hub-side delta export + member-side pull/apply."""

    # ------------------------------------------------------------------
    # Hub side
    # ------------------------------------------------------------------

    def build_delta_bundle(
        self,
        db: Session,
        workspace_id: str,
        sources: List[str],
        since_cursor: Optional[Dict[str, Dict[str, Any]]],
        sensitivity_ceiling: str = "internal",
        destination: str = "hub:pull",
    ) -> Dict[str, Any]:
        """Build a signed delta bundle containing records newer than the cursor.

        Returns a Phase-2-shaped envelope (``atom_org_data_bundle``) with an
        extra ``cursor`` field carrying the next pull cursor.
        """
        from core.org_data_bundle_service import (
            BUNDLE_VERSION,
            SENSITIVITY_LADDER,
            BundleError,
            sign_and_audit_bundle,
        )

        if sensitivity_ceiling not in SENSITIVITY_LADDER:
            raise BundleError(f"Invalid sensitivity_ceiling {sensitivity_ceiling!r}")
        allowed = set(SENSITIVITY_LADDER[: SENSITIVITY_LADDER.index(sensitivity_ceiling) + 1])

        from core.models import IngestedDocument

        cursor: Dict[str, Dict[str, Any]] = {}
        records: List[Dict[str, Any]] = []
        tombstones: List[str] = []
        breakdown: Dict[str, int] = {}
        excluded: Dict[str, int] = {}

        for source in sources:
            since = (since_cursor or {}).get(source) or {}
            since_ts = _normalize_dt(since.get("updated_at"))
            since_id = since.get("external_id") or ""

            query = db.query(IngestedDocument).filter(
                IngestedDocument.workspace_id == workspace_id,
                IngestedDocument.integration_id == source,
            )
            if since_ts is not None:
                from sqlalchemy import and_, or_

                query = query.filter(
                    or_(
                        IngestedDocument.updated_at > since_ts,
                        and_(
                            IngestedDocument.updated_at == since_ts,
                            IngestedDocument.external_id > since_id,
                        ),
                    )
                )
            query = query.order_by(
                IngestedDocument.updated_at.asc(),
                IngestedDocument.external_id.asc(),
            )

            last_seen: Optional[Dict[str, Any]] = None
            for doc in query.yield_per(1000):
                sensitivity = doc.sensitivity or "internal"
                if sensitivity not in allowed:
                    excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                    continue
                doc_stamp = (doc.updated_at or doc.ingested_at or datetime.now(timezone.utc))
                last_seen = {
                    "updated_at": doc_stamp.isoformat(),
                    "external_id": doc.external_id,
                }
                if doc.freshness_status == "removed":
                    # Tombstone: member imports mark the matching doc removed.
                    if doc.external_id not in tombstones:
                        tombstones.append(doc.external_id)
                    continue
                preview = (doc.content_preview or "")[:20000]
                records.append({
                    "integration_id": doc.integration_id,
                    "external_id": doc.external_id,
                    "file_name": doc.file_name,
                    "file_type": doc.file_type,
                    "content_preview": preview,
                    "external_modified_at": doc.external_modified_at.isoformat() if doc.external_modified_at else None,
                    "sensitivity": sensitivity,
                    "content_hash": _content_hash(doc.integration_id, doc.external_id, doc.external_modified_at, preview),
                })
                breakdown[sensitivity] = breakdown.get(sensitivity, 0) + 1
                if len(records) >= 100_000:
                    logger.warning("Hub delta record cap (100k) reached — truncating")
                    break
            if last_seen:
                cursor[source] = last_seen

        payload = {
            "kind": "atom_org_data_bundle",
            "bundle_version": BUNDLE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": workspace_id,
            "sources": list(sources),
            "sensitivity_ceiling": sensitivity_ceiling,
            "records": records,
            "tombstones": tombstones,
            "sensitivity_breakdown": breakdown,
            "hub_delta": True,
            "cursor": cursor,
        }

        envelope = sign_and_audit_bundle(
            db,
            payload,
            workspace_id=workspace_id,
            sources=sources,
            destination=destination,
        )
        if excluded:
            envelope["excluded_by_sensitivity"] = excluded
        return envelope

    # ------------------------------------------------------------------
    # Member side
    # ------------------------------------------------------------------

    async def pull_and_apply(
        self,
        db: Session,
        hub_url: str,
        api_key: str,
        sources: List[str],
        workspace_id: str,
        tenant_id: Optional[str] = None,
        sensitivity_ceiling: str = "internal",
        performed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pull the delta bundle from the hub and apply it via Phase 2 import.

        The cursor is persisted in ``ingestion_settings.usage_stats_json``
        (integration_id ``org_hub``) so a restart continues where it left off.
        Any failure raises HubError — callers (scheduled loop, route) decide
        whether to surface or retry.
        """
        import asyncio

        from core.org_data_bundle_service import OrgDataBundleService

        cursor = self._load_cursor(db, workspace_id)
        cursor_json = cursor_to_json(cursor)

        url = f"{hub_url.rstrip('/')}/api/data-ingestion/hub/bundles"
        params = {"sources": ",".join(sources), "sensitivity_ceiling": sensitivity_ceiling}
        if cursor_json:
            params["since"] = cursor_json

        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, params=params, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                })
        except Exception as e:
            raise HubError(f"Hub pull failed (network): {e}") from e

        if resp.status_code == 401:
            raise HubError("Hub rejected the API key (401)")
        if resp.status_code == 403:
            raise HubError("Hub denied the pull (403 — sharing/hub disabled on hub side)")
        if resp.status_code != 200:
            raise HubError(f"Hub pull failed (HTTP {resp.status_code})")

        try:
            envelope = resp.json()
        except ValueError as e:
            raise HubError("Hub returned a non-JSON response") from e

        result = await OrgDataBundleService().apply_bundle(
            db,
            envelope,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            performed_by=performed_by,
        )

        next_cursor = (envelope.get("payload") or {}).get("cursor") or {}
        if next_cursor:
            self._store_cursor(db, workspace_id, next_cursor)

        result["cursor"] = next_cursor
        return result

    # ------------------------------------------------------------------
    # Member cursor persistence (Phase 0 ingestion_settings storage)
    # ------------------------------------------------------------------

    def _load_cursor(self, db: Session, workspace_id: str) -> Dict[str, Dict[str, Any]]:
        from core.models import IngestionSettings

        try:
            row = db.query(IngestionSettings).filter(
                IngestionSettings.workspace_id == workspace_id,
                IngestionSettings.integration_id == HUB_CURSOR_INTEGRATION,
            ).first()
            if row is None:
                return {}
            usage = row.usage_stats_json or {}
            return cursor_from_json(usage.get("org_hub_cursor") if isinstance(usage, dict) else None)
        except Exception as e:
            logger.warning(f"Could not load org-hub cursor: {e}")
            return {}

    def _store_cursor(self, db: Session, workspace_id: str, cursor: Dict[str, Dict[str, Any]]) -> None:
        from core.models import IngestionSettings

        try:
            row = db.query(IngestionSettings).filter(
                IngestionSettings.workspace_id == workspace_id,
                IngestionSettings.integration_id == HUB_CURSOR_INTEGRATION,
            ).first()
            if row is None:
                row = IngestionSettings(
                    workspace_id=workspace_id,
                    integration_id=HUB_CURSOR_INTEGRATION,
                    enabled=False,
                )
                db.add(row)
            usage = dict(row.usage_stats_json or {}) if isinstance(row.usage_stats_json, dict) else {}
            usage["org_hub_cursor"] = cursor_to_json(cursor)
            row.usage_stats_json = usage
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not persist org-hub cursor: {e}")


def _content_hash(
    integration_id: str,
    external_id: str,
    external_modified_at: Optional[datetime],
    preview: str,
) -> str:
    import hashlib

    basis = "|".join(str(v or "") for v in (
        integration_id, external_id,
        external_modified_at.isoformat() if external_modified_at else None,
        preview,
    ))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
