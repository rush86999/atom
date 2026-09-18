"""TTL cache for idempotent integration READS.

The audit's gap #6: re-search speed came from the local LanceDB mirrors +
FTS5, but a live provider read was re-issued every time — the same
``outlook.search`` for the same query inside one agent turn, the same
``hubspot.list`` from two steps of one plan. Provider quota is real money
(and real rate limits), and the second identical call in a turn can never
return different data.

Design rules, all deliberate:

- **Reads only.** A write action is never cached, and any successful write
  to a service invalidates that service's whole namespace — a list read
  after a create must never serve the pre-create page.
- **Bounded.** A fixed-capacity LRU with a monotonic clock; an unbounded
  dict keyed by query text is a memory leak in a long-running daemon.
- **Never raises.** A cache failure degrades to a live fetch; it must not
  become a new failure mode for the integration layer.
- **Tenant-scoped key.** The key carries tenant + workspace so a cached
  page can never cross a tenant boundary (same rule as
  ``mcp_service.register_integration_tools``' cache-key comment).
- **Kill switch.** ``ATOM_INTEGRATION_READ_CACHE_ENABLED`` (default ON) —
  TTL ``ATOM_INTEGRATION_READ_CACHE_TTL`` (default 45s) covers one agent
  turn's worth of duplicate reads without serving stale data across turns.

Thread-safety matters here: the agent loop, workflow engine and fleet all
dispatch concurrently, and a raw dict read during a resize is a real crash
class in CPython if the value is mutated.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

#: Actions that never mutate provider state. Everything else is treated as a
#: write and is neither cached nor allowed to be served from cache.
READ_ACTIONS = frozenset({
    "list", "get", "read", "search", "search_emails", "search_messages",
    "search_files", "search_items", "search_contacts", "search_content",
    "query", "fetch", "download", "describe", "count", "aggregate",
    "get_insights", "list_reviews", "get_workbooks", "list_teams",
    "list_projects", "list_boards", "list_tasks", "get_events",
    "list_contacts", "list_deals", "list_accounts", "list_opportunities",
    "list_orders", "list_products", "list_customers", "read_emails",
    "read_calendar", "read_contacts", "get_profile", "get_channels",
    "get_users", "get_messages", "get_calendar", "analytics", "report",
    "export", "preview", "metadata",
})

#: Substrings that mark an action as mutating even if it also contains a
#: read-shaped verb ("get_or_create", "search_and_replace").
_WRITE_MARKERS = (
    "create", "update", "delete", "send", "post", "put", "patch", "remove",
    "archive", "move", "copy", "upload", "insert", "add", "set", "assign",
    "reply", "publish", "schedule", "cancel", "close", "merge", "import",
    "grant", "revoke", "approve", "reject", "trigger", "run", "execute",
    "start", "stop", "write", "edit", "modify", "rename", "fulfill",
    "refund", "charge", "pay", "subscribe", "unsubscribe", "invite",
    "share", "unshare", "enable", "disable", "activate", "deactivate",
)


def is_read_action(action: str) -> bool:
    """True only for actions that provably do not mutate provider state.

    Fail-closed: anything not recognized as a read is treated as a write,
    because caching a write's response would be a correctness bug (and a
    replayed side effect if a caller ever served it back).
    """
    text = (action or "").strip().lower()
    if not text:
        return False
    if any(marker in text for marker in _WRITE_MARKERS):
        # "search" contains no write marker; "get_or_create" does.
        return False
    if text in READ_ACTIONS:
        return True
    # Unlisted but read-shaped (tenant connectors name their own operations:
    # "list_invoices", "get_ticket", "search_orders").
    return any(text.startswith(verb) for verb in (
        "list", "get", "read", "search", "query", "fetch", "describe",
        "count", "aggregate", "report", "export", "preview",
    ))


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except (TypeError, ValueError):
        return default


class IntegrationReadCache:
    """Bounded, TTL'd, tenant-scoped cache over integration read responses."""

    def __init__(self, capacity: int = 256, ttl_seconds: float = 45.0):
        self._capacity = max(1, int(capacity))
        self._ttl = max(0.0, float(ttl_seconds))
        self._entries: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # -- configuration is read per call so a settings-UI flip is live -------

    @property
    def enabled(self) -> bool:
        return _env_flag("ATOM_INTEGRATION_READ_CACHE_ENABLED", True)

    @property
    def ttl_seconds(self) -> float:
        return _env_float("ATOM_INTEGRATION_READ_CACHE_TTL", self._ttl)

    # -- keys ---------------------------------------------------------------

    @staticmethod
    def make_key(
        service: str,
        action: str,
        tenant_id: Optional[str],
        workspace_id: Optional[str],
        query_key: str,
        params_key: str = "",
        user_id: Optional[str] = None,
    ) -> str:
        """Full call identity.

        ``query_key`` alone is NOT enough: it covers the read SHAPE (limit /
        cursor / fields / filter) but not the action's own parameters, so
        ``hubspot.list entity=contact`` and ``hubspot.list entity=deal``
        hashed identically and the second call was served the first one's
        contacts. ``params_key`` (see :func:`params_fingerprint`) closes
        that. ``user_id`` is in the scope because a read can be
        user-scoped ("my mailbox") inside one tenant.
        """
        return "|".join([
            str(tenant_id or "-"),
            str(workspace_id or "-"),
            str(user_id or "-"),
            str(service or "").lower(),
            str(action or "").lower(),
            query_key,
            params_key,
        ])

    # -- operations ---------------------------------------------------------

    def get(self, key: str) -> Tuple[bool, Any]:
        """(hit, value). Expired entries are dropped on read."""
        if not self.enabled:
            return False, None
        now = time.monotonic()
        try:
            with self._lock:
                entry = self._entries.get(key)
                if entry is None:
                    self._misses += 1
                    return False, None
                stamped, value = entry
                if now - stamped > self.ttl_seconds:
                    self._entries.pop(key, None)
                    self._misses += 1
                    return False, None
                self._entries.move_to_end(key)
                self._hits += 1
                return True, value
        except Exception:  # pragma: no cover - defensive
            logger.debug("read cache get failed", exc_info=True)
            return False, None

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        try:
            with self._lock:
                self._entries[key] = (time.monotonic(), value)
                self._entries.move_to_end(key)
                while len(self._entries) > self._capacity:
                    self._entries.popitem(last=False)
        except Exception:  # pragma: no cover - defensive
            logger.debug("read cache set failed", exc_info=True)

    def invalidate_service(self, service: str) -> int:
        """Drop every entry for a service (called after any write)."""
        needle = f"|{str(service or '').lower()}|"
        try:
            with self._lock:
                doomed = [k for k in self._entries if needle in k]
                for key in doomed:
                    self._entries.pop(key, None)
                return len(doomed)
        except Exception:  # pragma: no cover - defensive
            return 0

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "enabled": self.enabled,
                "size": len(self._entries),
                "capacity": self._capacity,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (self._hits / total) if total else 0.0,
            }


def params_fingerprint(params: Any) -> str:
    """Stable, order-independent digest of an action's own parameters.

    Distinct entities/searches of the same action must not share a cache
    entry; equal params must. Falls back to a sorted repr for values JSON
    cannot render (datetime, ORM rows a caller slipped in).
    """
    import json as _json
    try:
        material = _json.dumps(params or {}, sort_keys=True, default=str)
    except Exception:  # pragma: no cover - defensive
        try:
            material = repr(sorted((str(k), str(v))
                                   for k, v in dict(params or {}).items()))
        except Exception:
            material = repr(params)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


#: Process-wide cache the integration layer routes through.
integration_read_cache = IntegrationReadCache()


def cache_lookup(
    *,
    service: str,
    action: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    query: Any,
    params: Any = None,
    user_id: Optional[str] = None,
) -> Tuple[bool, Any]:
    """(hit, value) for a read. The ONE place the cache key is composed.

    Both ``cached_read*`` and the universal service's ``search()`` entry
    (which cannot delegate to a callable-wrapping helper without
    restructuring its dispatch chain) go through this, so the scope rules —
    tenant, workspace, user, service, action, read shape, params — can never
    drift between the two entry points.
    """
    key = integration_read_cache.make_key(
        service, action, tenant_id, workspace_id,
        getattr(query, "cache_key", lambda: str(query))(),
        params_fingerprint(params),
        user_id,
    )
    return integration_read_cache.get(key)


def cache_store(
    *,
    service: str,
    action: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    query: Any,
    result: Any,
    params: Any = None,
    user_id: Optional[str] = None,
) -> None:
    """Store a read result, unless it is an error envelope."""
    if isinstance(result, dict) and result.get("status") == "error":
        return
    key = integration_read_cache.make_key(
        service, action, tenant_id, workspace_id,
        getattr(query, "cache_key", lambda: str(query))(),
        params_fingerprint(params),
        user_id,
    )
    integration_read_cache.set(key, result)


def cached_read(
    *,
    service: str,
    action: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    query: Any,
    fetch: Callable[[], Any],
    params: Any = None,
    user_id: Optional[str] = None,
) -> Any:
    """Return a cached read result or run ``fetch`` and cache it.

    Never raises on cache problems and never caches an error envelope (a
    transient 500 must not be pinned for the TTL).
    """
    if not is_read_action(action) or not integration_read_cache.enabled:
        return fetch()

    hit, value = cache_lookup(
        service=service, action=action, tenant_id=tenant_id,
        workspace_id=workspace_id, query=query, params=params, user_id=user_id,
    )
    if hit:
        return value

    result = fetch()
    cache_store(
        service=service, action=action, tenant_id=tenant_id,
        workspace_id=workspace_id, query=query, result=result,
        params=params, user_id=user_id,
    )
    return result


async def cached_read_async(
    *,
    service: str,
    action: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    query: Any,
    fetch: Callable[[], Any],
    params: Any = None,
    user_id: Optional[str] = None,
) -> Any:
    """``cached_read`` for an async ``fetch`` (the integration dispatch path).

    Same rules: read actions only, errors never cached, cache failures
    degrade to a live fetch.
    """
    if not is_read_action(action) or not integration_read_cache.enabled:
        return await fetch()

    hit, value = cache_lookup(
        service=service, action=action, tenant_id=tenant_id,
        workspace_id=workspace_id, query=query, params=params, user_id=user_id,
    )
    if hit:
        return value

    result = await fetch()
    cache_store(
        service=service, action=action, tenant_id=tenant_id,
        workspace_id=workspace_id, query=query, result=result,
        params=params, user_id=user_id,
    )
    return result


def invalidate_after_write(service: str) -> int:
    """Invalidate a service's cached reads after a mutating action."""
    return integration_read_cache.invalidate_service(service)
