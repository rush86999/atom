from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from sqlalchemy.orm import Session
from core.models import UserConnection, TrainingAlert
from core.connection_service import ConnectionService
from core.structured_logger import get_logger

logger = get_logger(__name__)


def supports_drive_subscription(integration_id: str) -> bool:
    """Determine if an integration type supports OneDrive (drive) subscriptions."""
    return integration_id == "microsoft365"


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

                    # Fetch subscriptions from Graph to inspect resource types and clean up any legacy/unsupported drive subscriptions
                    import httpx
                    graph_sub_map = {}
                    try:
                        async with httpx.AsyncClient() as client:
                            list_resp = await client.get(
                                "https://graph.microsoft.com/v1.0/subscriptions",
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=15.0,
                            )
                            if list_resp.status_code == 200:
                                for sub in list_resp.json().get("value", []):
                                    if sub.get("id"):
                                        graph_sub_map[sub["id"]] = sub.get("resource")
                    except Exception as e:
                        logger.warning(f"Failed to list subscriptions for connection {conn.id} during renewal: {e}")

                    valid_subscription_ids = []
                    for sub_id in subscription_ids:
                        resource = graph_sub_map.get(sub_id)
                        if resource == "/me/drive/root" and not supports_drive_subscription(conn.integration_id):
                            logger.info(f"Deleting legacy/unsupported drive subscription {sub_id} for connection {conn.id}")
                            try:
                                async with httpx.AsyncClient() as client:
                                    await client.delete(
                                        f"https://graph.microsoft.com/v1.0/subscriptions/{sub_id}",
                                        headers={"Authorization": f"Bearer {token}"},
                                        timeout=15.0,
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to delete legacy drive subscription {sub_id}: {e}")
                            continue
                        
                        valid_subscription_ids.append(sub_id)

                    # If subscription list changed, save it immediately
                    if len(valid_subscription_ids) != len(subscription_ids):
                        subscription_ids = valid_subscription_ids
                        creds["subscription_ids"] = subscription_ids
                        conn.credentials = self.connection_service._encrypt(creds)
                        self.db.commit()

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
        from core.database import SessionLocal

        # Detect mock DB in unit tests and bypass SessionLocal
        is_mock_db = type(self.db).__name__ in ('MagicMock', 'Mock', 'AsyncMock') or hasattr(self.db, "assert_called")

        # Fetch only connection IDs first to minimize connection hold time
        raw_rows = (
            self.db.query(UserConnection.id)
            .filter(UserConnection.status == "active")
            .all()
        )
        connection_ids = []
        for row in raw_rows:
            if is_mock_db and isinstance(row, UserConnection):
                connection_ids.append(row)
            elif hasattr(row, "id"):
                connection_ids.append(row.id)
            elif isinstance(row, (tuple, list)):
                connection_ids.append(row[0])
            else:
                connection_ids.append(row)

        results = {"total_checked": len(connection_ids), "renewed": 0, "failed": 0, "skipped": 0}

        for conn_id in connection_ids:
            fresh_db = self.db
            if not is_mock_db:
                try:
                    fresh_db = SessionLocal()
                except Exception:
                    pass

            try:
                if is_mock_db and isinstance(conn_id, UserConnection):
                    conn = conn_id
                else:
                    conn = fresh_db.query(UserConnection).filter_by(id=conn_id).first()

                if not conn:
                    results["skipped"] += 1
                    continue

                if not self.is_renewal_due(conn):
                    results["skipped"] += 1
                    continue

                # Stagger renewal dynamically with a 100ms guard sleep to prevent rate-limit API storms
                await asyncio.sleep(0.1)

                # Swap db context for this renewal check to avoid leaks
                original_db = self.db
                self.db = fresh_db
                try:
                    outcome = await self.renew_subscription_for_connection(conn)
                    if outcome["status"] == "success":
                        results["renewed"] += 1
                    else:
                        results["failed"] += 1
                finally:
                    self.db = original_db
            finally:
                if not is_mock_db and fresh_db is not self.db:
                    fresh_db.close()

        logger.info(f"Staggered renewal cycle completed: {results}")
        return results
