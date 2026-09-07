"""Proactive OAuth token refresh for the Zoho suite.

Zoho access tokens live one hour. Refreshing only when a data sync happened
to run left idle integrations sitting on expired tokens for as long as no
sync fired — a degraded ingestion that looked like a broken connector. This
worker refreshes expiring rows ahead of expiry, the same lifecycle the
scheduled-token-refresh services in mature harnesses use (refresh when a
fixed window before expiry is entered, not at the 401).

Spawned from main_api_app like the other workers; never raises out of run().
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# One grant covers the whole Zoho suite: the canonical "zoho" row plus the
# record rows written by the connect-time fan-out. ZohoWorkDriveService is
# deliberately excluded — it manages its own row's refresh lifecycle and
# caches the token in-process.
ZOHO_REFRESH_PROVIDERS = ("zoho", "zoho_crm", "zoho_books", "zoho_inventory")


class TokenRefreshWorker:
    def __init__(self, interval_seconds: int = 300, refresh_window_seconds: int = 600):
        self.interval_seconds = interval_seconds
        self.refresh_window_seconds = refresh_window_seconds
        self.running = False

    async def run(self):
        self.running = True
        logger.info(
            f"TokenRefreshWorker started (interval={self.interval_seconds}s, "
            f"window={self.refresh_window_seconds}s)"
        )
        while self.running:
            try:
                await self.refresh_expiring_tokens()
            except Exception as e:
                logger.error(f"TokenRefreshWorker cycle failed: {e}")
            await asyncio.sleep(self.interval_seconds)

    def _expiring_rows(self, db):
        """Active zoho-family rows whose access token expires within the
        refresh window (SQLite returns naive datetimes — normalize)."""
        from core.models import IntegrationToken

        horizon = datetime.now(timezone.utc) + timedelta(
            seconds=self.refresh_window_seconds
        )
        rows = (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.provider.in_(ZOHO_REFRESH_PROVIDERS),
                IntegrationToken.status == "active",
            )
            .all()
        )
        expiring = []
        for row in rows:
            expires_at = row.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at <= horizon:
                expiring.append(row)
        return expiring

    async def refresh_expiring_tokens(self):
        from core.database import SessionLocal
        from core.integrations.adapters.zoho import ZohoAdapter

        db = SessionLocal()
        try:
            expiring = self._expiring_rows(db)
            if not expiring:
                return
            logger.info(
                f"TokenRefreshWorker: {len(expiring)} zoho-family token row(s) "
                f"expire within {self.refresh_window_seconds}s"
            )
            # All family rows share one grant — a single refresh updates the
            # canonical row AND fans the new access token out to the record
            # rows (ZohoAdapter.refresh_token), so one pass per cycle is
            # enough even if several siblings are expiring together.
            adapter = ZohoAdapter(db=db, workspace_id="default")
            if await adapter.refresh_token():
                logger.info("TokenRefreshWorker: zoho suite token refreshed ahead of expiry")
            else:
                logger.warning(
                    "TokenRefreshWorker: zoho token refresh failed — "
                    "the grant may need a manual reconnect"
                )
        finally:
            db.close()
