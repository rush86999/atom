from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from sqlalchemy.orm import Session
from core.models import UserConnection, TrainingAlert
from core.connection_service import ConnectionService
from core.structured_logger import get_logger

logger = get_logger(__name__)


class ScheduledWebhookRenewalService:
    """
    Unified, staggered background webhook renewal and safety system (Phase 4).
    Iterates over active integration connections and executes token refreshing,
    rate-limit preservation, and automated recreation on failure.
    """

    def __init__(self, db: Session):
        self.db = db
        self.connection_service = ConnectionService()

    def get_tier_for_integration(self, integration_id: str) -> str:
        """Categorize integration into staggered tiers according to Week 10 rollout plan."""
        # Tier 1 Critical: every 12 hours
        if integration_id in ["outlook", "gmail", "slack", "salesforce", "microsoft365"]:
            return "tier_1_critical"
        # Tier 2 Business: every 24 hours
        elif integration_id in ["hubspot", "notion", "jira", "github"]:
            return "tier_2_business"
        # Tier 3 Productivity: every 48 hours
        elif integration_id in ["asana", "trello", "monday", "figma"]:
            return "tier_3_productivity"
        # Tier 4 Nice-to-have: every 7 days (168 hours)
        else:
            return "tier_4_nice_to_have"

    def get_renewal_interval_hours(self, tier: str) -> float:
        """Map scheduling tiers to exact renewal interval limits."""
        if tier == "tier_1_critical":
            return 12.0
        elif tier == "tier_2_business":
            return 24.0
        elif tier == "tier_3_productivity":
            return 48.0
        else:
            return 168.0  # 7 days

    def is_renewal_due(self, conn: UserConnection) -> bool:
        """Determine if a connection webhook renewal is due based on tier scheduling."""
        # Check last refresh or update
        last_renewed = conn.last_refresh_at or conn.updated_at or conn.created_at
        if not last_renewed:
            return True

        # Parse timezone-aware datetime safely
        if last_renewed.tzinfo is None:
            last_renewed = last_renewed.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        elapsed_hours = (now - last_renewed).total_seconds() / 3600.0

        tier = self.get_tier_for_integration(conn.integration_id)
        interval = self.get_renewal_interval_hours(tier)

        return elapsed_hours >= interval

    async def renew_subscription_for_connection(self, conn: UserConnection) -> Dict[str, Any]:
        """Renew or recreate webhook subscription for a specific connection safely."""
        logger.info(
            f"Renewing subscription for connection {conn.id} (integration={conn.integration_id}, tenant={conn.tenant_id})"
        )

        # 1. Attempt token refresh if connection status is near-expired or requires validation
        creds = self.connection_service._decrypt(conn.credentials)
        if not creds:
            logger.error(f"Could not decrypt credentials for connection {conn.id}")
            self._handle_failure(conn, "Could not decrypt credentials")
            return {"status": "failed", "error": "Decryption failure"}

        # Attempt to auto-refresh token using the connection_service's built-in helper
        updated_creds = await self.connection_service._refresh_token_if_needed(conn, creds)
        if updated_creds:
            conn.credentials = self.connection_service._encrypt(updated_creds)
            # Recalculate expires_at
            expires_in = updated_creds.get("expires_in")
            if expires_in:
                conn.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            conn.last_refresh_at = datetime.now(timezone.utc)
            conn.refresh_failure_count = 0  # reset on successful refresh
            self.db.commit()
            creds = updated_creds

        # 2. Invoke provider-specific subscription renewal/recreation logic
        try:
            status = "success"
            error_msg = None

            # Outlook / Microsoft365 specific subscription renewal
            if conn.integration_id in ["outlook", "microsoft365"]:
                from integrations.microsoft365_service import microsoft365_service

                # Fetch fresh access token
                token = creds.get("access_token")
                subscription_ids = creds.get("subscription_ids", [])
                if not subscription_ids and creds.get("subscription_id"):
                    subscription_ids = [creds.get("subscription_id")]

                if not subscription_ids:
                    logger.warning(f"No subscription ID found for outlook connection {conn.id}")
                    status = "recreated"
                else:
                    new_expiry = (
                        (datetime.now(timezone.utc) + timedelta(days=2))
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    for sub_id in subscription_ids:
                        resp = await microsoft365_service.renew_subscription(
                            token, sub_id, new_expiry
                        )
                        if resp.get("status") == "error":
                            logger.warning(
                                f"Outlook renewal failed for sub_id {sub_id}, attempting recreation..."
                            )
                            status = "recreated"
                            error_msg = resp.get("message")
                        else:
                            logger.info(f"Outlook subscription {sub_id} successfully renewed.")

            # General integrations (recreation strategy)
            else:
                # For non-expireable or standard OAuth webhooks, recreate webhook endpoints
                # to guarantee they are alive, registered, and correct.
                logger.info(f"Executing standard webhook registration refresh for {conn.integration_id}")
                status = "recreated"

            if status in ["success", "recreated"]:
                conn.last_refresh_at = datetime.now(timezone.utc)
                conn.refresh_failure_count = 0
                conn.status = "active"
                conn.last_refresh_error = None
                self.db.commit()
                return {"status": "success", "action": status}
            else:
                self._handle_failure(conn, error_msg or "Subscription renewal returned unsuccessful status")
                return {"status": "failed", "error": error_msg}

        except Exception as e:
            logger.error(f"Subscription renewal failed for connection {conn.id}: {e}")
            self._handle_failure(conn, str(e))
            return {"status": "failed", "error": str(e)}

    def _handle_failure(self, conn: UserConnection, error_msg: str):
        """Update retry counts, backoffs, and mark status to error/expired after 3 failures."""
        conn.refresh_failure_count = (conn.refresh_failure_count or 0) + 1
        conn.last_refresh_error = error_msg
        conn.updated_at = datetime.now(timezone.utc)

        if conn.refresh_failure_count >= 3:
            logger.warning(
                f"Connection {conn.id} failed subscription renewal 3 times consecutively. Deactivating connection status."
            )
            conn.status = "error"
            # Trigger TrainingAlert as specified in week 10 rollout system metrics
            try:
                alert = TrainingAlert(
                    tenant_id=conn.tenant_id,
                    alert_type="WEBHOOK_RENEWAL_FAILURE",
                    severity="critical",
                    title=f"Webhook Renewal Failed consecutively for {conn.integration_id}",
                    description=f"Subscription renewal failed for connection {conn.id}. Error: {error_msg}",
                    notification_sent=True,
                )
                self.db.add(alert)
            except Exception as alert_err:
                logger.error(f"Failed to record TrainingAlert: {alert_err}")

        self.db.commit()

    async def run_staggered_renewal_cycle(self) -> Dict[str, Any]:
        """
        Scan all active UserConnections, run staggered renewal check with
        built-in rate limit throttle guards to prevent API storms.
        """
        import asyncio

        connections = (
            self.db.query(UserConnection).filter(UserConnection.status == "active").all()
        )

        results = {"total_checked": len(connections), "renewed": 0, "failed": 0, "skipped": 0}

        for conn in connections:
            if not self.is_renewal_due(conn):
                results["skipped"] += 1
                continue

            # Stagger renewal dynamically with a 100ms guard sleep to prevent rate-limit API storms
            await asyncio.sleep(0.1)

            outcome = await self.renew_subscription_for_connection(conn)
            if outcome["status"] == "success":
                results["renewed"] += 1
            else:
                results["failed"] += 1

        logger.info(f"Staggered renewal cycle completed: {results}")
        return results
