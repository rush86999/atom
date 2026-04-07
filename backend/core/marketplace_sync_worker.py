"""
Marketplace Analytics Sync Worker

Periodically pushes aggregated usage metrics from the self-hosted instance
to the Atom SaaS platform. Handles instance registration automatically.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import MarketplaceUsage, MarketplaceInstance
from core.atom_saas_client import AtomAgentOSMarketplaceClient

logger = logging.getLogger(__name__)


class AnalyticsSyncWorker:
    """
    Worker responsible for syncing marketplace usage data to SaaS.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.saas_client = AtomAgentOSMarketplaceClient()
        self.analytics_enabled = os.getenv("ANALYTICS_ENABLED", "false").lower() == "true"

    def _ensure_instance_registered(self) -> Optional[str]:
        """
        Ensure this instance is registered with SaaS.
        Returns the saas_instance_id if successful.
        """
        try:
            instance = self.db.query(MarketplaceInstance).first()
            if instance:
                return instance.saas_instance_id

            # Auto-registration
            logger.info("Registering new instance for marketplace analytics...")
            reg_data = self.saas_client.register_instance_sync(
                instance_name=os.getenv("INSTANCE_NAME", "Self-Hosted-Atom"),
                platform=os.getenv("PLATFORM", "docker"),
                version="1.0.0"
            )

            if reg_data and reg_data.get("instance_id"):
                saas_id = reg_data["instance_id"]
                token = reg_data.get("registration_token")
                
                new_instance = MarketplaceInstance(
                    saas_instance_id=saas_id,
                    registration_token=token,
                    status="active"
                )
                self.db.add(new_instance)
                self.db.commit()
                logger.info(f"Instance registered successfully. ID: {saas_id}")
                return saas_id
            else:
                logger.error(f"SaaS registration failed: {reg_data.get('error', 'Unknown error')}")
                return None
        except Exception as e:
            logger.error(f"Error during instance registration: {e}")
            return None

    def sync_usage(self) -> int:
        """
        Finds updated usage records and pushes them to SaaS.
        Returns the number of records synced.
        """
        if not self.analytics_enabled:
            logger.info("Marketplace analytics sync is disabled (ANALYTICS_ENABLED=false)")
            return 0

        saas_instance_id = self._ensure_instance_registered()
        if not saas_instance_id:
            logger.warning("Marketplace sync aborted: Instance registration failed or not available.")
            return 0

        # Fetch all usage records (aggregated locally)
        # In a more advanced implementation, we might only fetch those with changes 
        # since last_reported_at.
        usage_records = self.db.query(MarketplaceUsage).all()
        if not usage_records:
            logger.debug("No marketplace usage found to sync.")
            return 0

        # Format reports for SaaS ingestion
        reports = []
        for record in usage_records:
            reports.append({
                "item_type": record.item_type,
                "item_id": record.item_id,
                "execution_count": record.execution_count,
                "success_count": record.success_count,
                "total_duration_ms": record.total_duration_ms
            })

        try:
            logger.info(f"Pushing {len(reports)} usage reports to Atom SaaS...")
            result = self.saas_client.push_analytics_sync(
                instance_id=saas_instance_id,
                reports=reports
            )

            if result.get("success"):
                sync_time = datetime.now()
                # Update last reported timestamp
                for record in usage_records:
                    record.last_reported_at = sync_time
                
                # Update instance sync time
                instance = self.db.query(MarketplaceInstance).filter(
                    MarketplaceInstance.saas_instance_id == saas_instance_id
                ).first()
                if instance:
                    instance.last_sync_at = sync_time
                
                self.db.commit()
                logger.info(f"Successfully synced marketplace analytics at {sync_time.isoformat()}")
                return len(reports)
            else:
                logger.error(f"SaaS rejected analytics push: {result.get('error')}")
                return 0

        except Exception as e:
            logger.error(f"Failed to push analytics to SaaS: {e}")
            return 0

    def close(self):
        """Cleanup resources."""
        if self.db:
            self.db.close()


def run_sync():
    """Entry point for cron/background job."""
    worker = AnalyticsSyncWorker()
    try:
        count = worker.sync_usage()
        print(f"Synced {count} marketplace usage records.")
    finally:
        worker.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sync()
