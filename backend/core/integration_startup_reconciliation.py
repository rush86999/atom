"""Startup reconciliation for integration tokens — all providers.

Failure class this guards against (2026-09-04/05 incident): the world DB was
wiped and re-seeded (single new user) while file-backed state survived. Any
IntegrationToken row pointing at a user_id that no longer exists kept
pollers/refresh flows running against a dead owner — wasting API quota and
stamping ingested data with an owner no scoped search can ever see (the
memory store ended up full of invisible rows).

Rectification policy (fail-safe directions):
- Tokens whose user_id is absent from the users table -> status='orphaned'.
  Reversible (flip back if the user is restored); every consumer filters on
  status='active', so dead owners stop being polled immediately.
- Tokens that are active but whose access token has been expired for more
  than ``stale_after_hours`` are REPORTED for reconnect, never deactivated —
  the per-service auto-refresh flow may still recover them, and deactivating
  would turn a recoverable token into a dead one.

Safe on fresh installations: no orphaned tokens -> no writes, just a summary
log. Runs at app startup and periodically from the ingestion maintenance
loop, so a wipe/re-seed mid-process is rectified on the next cycle.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def reconcile_integration_tokens(*, stale_after_hours: float = 24.0) -> Dict[str, Any]:
    """Rectify token rows that reference users which no longer exist, and
    report long-expired active tokens. Returns a summary for tests/logs."""
    from core.database import SessionLocal
    from core.models import IntegrationToken, User

    session = SessionLocal()
    try:
        live_user_ids = {str(r[0]) for r in session.query(User.id).all()}
        tokens: List[IntegrationToken] = session.query(IntegrationToken).all()

        now = datetime.now(timezone.utc)
        orphaned: List[IntegrationToken] = []
        stale_expired: List[IntegrationToken] = []
        for t in tokens:
            user_id = str(t.user_id) if t.user_id else ""
            # Tokens not bound to a user (API-key style) have no owner to
            # outlive — skip them.
            if user_id and user_id not in live_user_ids:
                orphaned.append(t)
                continue
            if t.status == "active" and t.expires_at is not None:
                expires = t.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now - expires > timedelta(hours=stale_after_hours):
                    stale_expired.append(t)

        for t in orphaned:
            t.status = "orphaned"
        if orphaned:
            session.commit()

        by_provider: Dict[str, int] = {}
        for t in tokens:
            if t.status == "active":
                by_provider[t.provider] = by_provider.get(t.provider, 0) + 1

        if orphaned:
            logger.warning(
                "Deactivated %d orphaned integration token(s) whose user no "
                "longer exists (world wipe/re-seed?): %s",
                len(orphaned),
                [f"{t.provider}:{str(t.user_id)[:8]}" for t in orphaned],
            )
        if stale_expired:
            logger.warning(
                "%d active integration token(s) expired >%.0fh ago and were "
                "not refreshed — reconnect these in Settings: %s",
                len(stale_expired),
                stale_after_hours,
                sorted({t.provider for t in stale_expired}),
            )
        logger.info(
            "Integration token reconciliation: %d tokens, %d active, "
            "%d orphaned (deactivated), %d stale-expired (reported)",
            len(tokens),
            sum(by_provider.values()),
            len(orphaned),
            len(stale_expired),
        )
        return {
            "total": len(tokens),
            "active_by_provider": by_provider,
            "orphaned": len(orphaned),
            "stale_expired": [t.provider for t in stale_expired],
        }
    finally:
        session.close()
