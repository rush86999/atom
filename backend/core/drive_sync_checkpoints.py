"""Durable paged sync for WorkDrive/OneDrive knowledge sources.

The provider adapters already expose a strict single-page read with an opaque
cursor.  This module adds the part a long-running employee needs:

* the cursor and coverage counters survive a restart;
* a resumed call continues from the stored cursor instead of re-reading the
  first page or silently declaring the source complete;
* a complete re-listing reports items that disappeared remotely (deletion) as
  candidates, without deleting memory rows behind the user's back;
* a revoked/unavailable grant is persisted as a typed state and surfaced by
  the status action, never as an empty successful listing.

Checkpoints live in the existing per-workspace ``IngestionSettings`` row
(``usage_stats_json.sync_cursors``) through ``HybridDataIngestionService``.
No new job table or retry loop is introduced.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

CHECKPOINT_VERSION = 1
CHECKPOINT_PREFIX = "drive_page"
MAX_TRACKED_IDS = 2000
MAX_RUN_IDS = 5000
STALE_AFTER_SECONDS = 24 * 60 * 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_service(workspace_id: str, tenant_id: str):
    from core.hybrid_data_ingestion import get_hybrid_ingestion_service

    return get_hybrid_ingestion_service(workspace_id or "default",
                                       tenant_id or "default")


def checkpoint_scope(
    provider: str,
    *,
    folder_id: Optional[str] = None,
    drive_id: Optional[str] = None,
    site_id: Optional[str] = None,
    provider_workspace_id: Optional[str] = None,
) -> str:
    """Stable scope identity for one paged listing."""
    provider = str(provider or "").strip().lower()
    if provider == "onedrive":
        return (f"site={site_id or '-'}|drive={drive_id or 'me'}|"
                f"folder={folder_id or 'root'}")
    return (f"workspace={provider_workspace_id or '-'}|"
            f"folder={folder_id or 'root'}")


def _checkpoint_key(provider: str, scope: str) -> str:
    return f"{CHECKPOINT_PREFIX}:{provider}:{scope}"


def load_checkpoint(
    provider: str,
    scope: str,
    *,
    workspace_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    service = _state_service(workspace_id, tenant_id)
    stats = service.usage_stats.get(provider)
    raw = ((stats.sync_cursors or {}).get(_checkpoint_key(provider, scope))
           if stats else None)
    if not raw:
        return {}
    try:
        state = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        logger.warning("discarding unreadable drive checkpoint for %s", provider)
        return {}
    if not isinstance(state, dict):
        return {}
    return state


def save_checkpoint(
    provider: str,
    scope: str,
    state: Dict[str, Any],
    *,
    workspace_id: str,
    tenant_id: str,
) -> None:
    from core.hybrid_data_ingestion import IntegrationUsageStats

    service = _state_service(workspace_id, tenant_id)
    stats = service.usage_stats.get(provider)
    if stats is None:
        stats = IntegrationUsageStats(
            integration_id=provider,
            integration_name=provider,
            workspace_id=workspace_id or "default",
        )
        service.usage_stats[provider] = stats
    state["updated_at"] = _now()
    stats.sync_cursors = dict(stats.sync_cursors or {})
    stats.sync_cursors[_checkpoint_key(provider, scope)] = json.dumps(
        state, sort_keys=True, separators=(",", ":"))
    service._persist_integration(provider)


def _new_state(provider: str, scope: str, prior_known: Sequence[str]) -> Dict[str, Any]:
    return {
        "version": CHECKPOINT_VERSION,
        "provider": provider,
        "scope": scope,
        "state": "in_progress",
        "next_cursor": None,
        "pages_completed": 0,
        "rows_seen": 0,
        "rows_written": 0,
        "run_seen_ids": [],
        "prior_known_ids": list(prior_known or [])[:MAX_TRACKED_IDS],
        "known_ids": [],
        "missing_external_ids": [],
        "ids_truncated": False,
        "deletion_check": "pending",
        "last_error": None,
        "last_success_at": None,
        "started_at": _now(),
        "updated_at": _now(),
    }


def _merge_ids(unique: List[str], incoming: Sequence[str], *,
               cap: int) -> Tuple[List[str], bool]:
    truncated = False
    for item in incoming:
        text = str(item or "").strip()
        if not text or text in unique:
            continue
        if len(unique) >= cap:
            truncated = True
            break
        unique.append(text)
    return unique, truncated


def _normalize_rows(
    provider: str, items: Sequence[Dict[str, Any]], scope: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        external_id = str(item.get("id") or "").strip()
        if not external_id:
            continue
        kind = "folder" if str(item.get("type") or "") == "folder" else "file"
        rows.append({
            "external_id": external_id,
            "kind": kind,
            "entity_type": kind,
            "name": item.get("name") or "Untitled",
            "path": scope,
            "size": int(item.get("size") or 0),
            "modified": item.get("modified_at") or item.get("modified"),
            "version": item.get("version") or "",
            "web_url": item.get("web_url") or "",
            "parent_id": item.get("parent_id") or "",
            "provider": provider,
        })
    return rows


async def _read_page(
    provider: str,
    *,
    user_id: str,
    tenant_id: str,
    folder_id: Optional[str],
    drive_id: Optional[str],
    site_id: Optional[str],
    provider_workspace_id: Optional[str],
    team_id: Optional[str],
    cursor: Optional[str],
    page_size: int,
) -> Dict[str, Any]:
    if provider == "zoho_workdrive":
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        service = ZohoWorkDriveService(tenant_id, {})
        return await service.list_files_page(
            user_id, folder_id or "root",
            team_id=team_id, workspace_id=provider_workspace_id,
            cursor=cursor, page_size=page_size)
    if provider == "onedrive":
        from integrations.onedrive_service import OneDriveService

        service = OneDriveService(tenant_id, {})
        token, resolution = await service.get_access_token_resolution(user_id)
        if not token:
            state = str((resolution or {}).get("state") or "auth_unavailable")
            kind = "auth_revoked" if state in (
                "invalid_grant", "revoked", "refresh_unavailable") else "auth_unavailable"
            return {
                "status": "error",
                "success": False,
                "provider": "onedrive",
                "operation": "list_files_page",
                "error_kind": kind,
                "error": "No Microsoft Graph token for this user.",
                "retryable": False,
                "requires_reconnect": True,
                "resolution_state": state,
            }
        return await service.list_files_page(
            token, folder_id, cursor=cursor, page_size=page_size,
            drive_id=drive_id, site_id=site_id)
    return {
        "status": "error",
        "success": False,
        "provider": provider,
        "operation": "list_files_page",
        "error_kind": "invalid_request",
        "error": f"Unsupported drive provider: {provider}",
        "retryable": False,
        "requires_reconnect": False,
    }


def _status_from_state(state: Dict[str, Any]) -> str:
    if not state:
        return "never_synced"
    current = str(state.get("state") or "")
    if current in ("revoked", "unavailable", "failed"):
        return current
    if current == "in_progress":
        return "in_progress"
    if current == "complete":
        if state.get("missing_external_ids"):
            return "complete_with_remote_deletions"
        return "complete"
    return "unknown"


def coverage_status(
    provider: str,
    scope: str,
    *,
    workspace_id: str,
    tenant_id: str,
    max_age_seconds: int = STALE_AFTER_SECONDS,
) -> Dict[str, Any]:
    state = load_checkpoint(provider, scope, workspace_id=workspace_id,
                            tenant_id=tenant_id)
    coverage = _status_from_state(state)
    last_success = state.get("last_success_at") if state else None
    age = None
    stale = None
    if last_success:
        try:
            parsed = datetime.fromisoformat(str(last_success).replace("Z", "+00:00"))
            age = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
            stale = age > max_age_seconds
        except ValueError:
            stale = None
    return {
        "status": "success",
        "provider": provider,
        "scope": scope,
        "coverage": coverage,
        "stale": stale,
        "age_seconds": age,
        "checkpoint": state or None,
        "missing_external_ids": list(
            (state or {}).get("missing_external_ids") or []),
        "next_cursor": (state or {}).get("next_cursor"),
        "last_error": (state or {}).get("last_error"),
    }


async def sync_drive_page(
    *,
    provider: str,
    user_id: str,
    workspace_id: str = "default",
    tenant_id: str = "default",
    folder_id: Optional[str] = None,
    drive_id: Optional[str] = None,
    site_id: Optional[str] = None,
    provider_workspace_id: Optional[str] = None,
    team_id: Optional[str] = None,
    cursor: Optional[str] = None,
    page_size: int = 100,
    fresh: bool = False,
    index_content: bool = True,
    max_rows: int = 500,
) -> Dict[str, Any]:
    """Read one page, index it, and durably advance the checkpoint.

    ``fresh=True`` starts a new complete enumeration while retaining the last
    complete ID set for deletion comparison.  Without ``fresh`` an unfinished
    checkpoint resumes from its stored cursor.  A completed checkpoint starts
    a new run so scheduled syncs keep discovering new files.
    """
    provider = str(provider or "").strip().lower()
    scope = checkpoint_scope(
        provider, folder_id=folder_id, drive_id=drive_id, site_id=site_id,
        provider_workspace_id=provider_workspace_id)
    existing = load_checkpoint(provider, scope, workspace_id=workspace_id,
                               tenant_id=tenant_id)
    if not existing or fresh or (
            str(existing.get("state")) == "complete" and not cursor):
        state = _new_state(provider, scope, existing.get("known_ids") or [])
        resume_cursor = cursor
    else:
        state = existing
        resume_cursor = cursor or existing.get("next_cursor")
        state["state"] = "in_progress"
        state["last_error"] = None

    result = await _read_page(
        provider, user_id=user_id, tenant_id=tenant_id, folder_id=folder_id,
        drive_id=drive_id, site_id=site_id,
        provider_workspace_id=provider_workspace_id, team_id=team_id,
        cursor=resume_cursor, page_size=page_size)

    if result.get("status") != "success":
        kind = str(result.get("error_kind") or "provider_error")
        if kind in ("auth_expired", "auth_revoked"):
            state["state"] = "revoked"
        elif kind in ("auth_unavailable", "rate_limited", "transient"):
            state["state"] = "unavailable"
        else:
            state["state"] = "failed"
        state["last_error"] = {
            "error_kind": kind,
            "error": result.get("error"),
            "operation": result.get("operation") or "list_files_page",
            "at": _now(),
        }
        save_checkpoint(provider, scope, state, workspace_id=workspace_id,
                        tenant_id=tenant_id)
        result = dict(result)
        result["checkpoint"] = coverage_status(
            provider, scope, workspace_id=workspace_id, tenant_id=tenant_id)
        result["action_result"] = "unavailable"
        return result

    items = list(result.get("items") or [])
    rows = _normalize_rows(provider, items, scope)
    indexed: Dict[str, Any] = {"success": True, "rows_written": 0}
    if index_content and rows:
        from core.drive_tree_ingestion import IntegrationMemoryIndexer

        indexed = await IntegrationMemoryIndexer(workspace_id).index_rows(
            provider, rows, max_rows=max(1, min(int(max_rows), 5000)))
    if not indexed.get("success"):
        state["state"] = "failed"
        state["last_error"] = {
            "error_kind": "memory_unavailable",
            "error": indexed.get("error") or "Memory index write failed.",
            "operation": "index_rows",
            "at": _now(),
        }
        save_checkpoint(provider, scope, state, workspace_id=workspace_id,
                        tenant_id=tenant_id)
        return {
            "status": "error",
            "success": False,
            "action_result": "unavailable",
            "provider": provider,
            "operation": "sync_page",
            "error_kind": "memory_unavailable",
            "error": indexed.get("error") or "Memory index write failed.",
            "retryable": True,
            "requires_reconnect": False,
            "rows_read": len(rows),
            "checkpoint": coverage_status(
                provider, scope, workspace_id=workspace_id,
                tenant_id=tenant_id),
        }

    state["pages_completed"] = int(state.get("pages_completed") or 0) + 1
    state["rows_seen"] = int(state.get("rows_seen") or 0) + len(rows)
    state["rows_written"] = int(
        state.get("rows_written") or 0) + int(indexed.get("rows_written") or 0)
    run_ids, run_truncated = _merge_ids(
        list(state.get("run_seen_ids") or []),
        [row["external_id"] for row in rows], cap=MAX_RUN_IDS)
    state["run_seen_ids"] = run_ids
    state["ids_truncated"] = bool(
        state.get("ids_truncated") or run_truncated)
    state["next_cursor"] = result.get("next_cursor")
    has_more = bool(result.get("has_more"))
    state["state"] = "in_progress" if has_more else "complete"
    state["last_success_at"] = _now()
    if not has_more:
        prior = set(state.get("prior_known_ids") or [])
        seen = set(run_ids)
        if state.get("ids_truncated"):
            state["missing_external_ids"] = []
            state["deletion_check"] = "skipped_truncated"
        else:
            state["missing_external_ids"] = sorted(prior - seen)[
                :MAX_TRACKED_IDS]
            state["deletion_check"] = "complete"
        state["known_ids"] = sorted(seen)[:MAX_TRACKED_IDS]
        state["prior_known_ids"] = []
        state["next_cursor"] = None
    else:
        state["deletion_check"] = "pending"

    save_checkpoint(provider, scope, state, workspace_id=workspace_id,
                    tenant_id=tenant_id)
    checkpoint = coverage_status(
        provider, scope, workspace_id=workspace_id, tenant_id=tenant_id)
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": provider,
        "operation": "sync_page",
        "scope": scope,
        "items": items,
        "rows_written": int(indexed.get("rows_written") or 0),
        "next_cursor": result.get("next_cursor"),
        "has_more": has_more,
        "coverage": "partial" if has_more else "page_complete",
        "deletion_check": state.get("deletion_check"),
        "missing_external_ids": state.get("missing_external_ids") or [],
        "checkpoint": checkpoint,
        "read_receipt": {
            "provider": provider,
            "operation": "list_files_page",
            "resource_id": scope,
            "account_id": provider_workspace_id or drive_id or site_id,
            "access": "granted",
            "retrieved_at": _now(),
            "coverage": "partial" if has_more else "page_complete",
            "fields": ["id", "name", "type", "size", "modified_at",
                       "version"],
            "continuation": {
                "next_cursor": result.get("next_cursor"),
                "has_more": has_more,
            },
        },
    }
