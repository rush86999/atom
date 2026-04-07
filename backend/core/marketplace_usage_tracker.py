import logging
from datetime import datetime, timezone
from core.database import get_db_session
from core.models import MarketplaceUsage

logger = logging.getLogger(__name__)

class MarketplaceUsageTracker:
    """
    Handles local aggregation of marketplace item usage.
    This is non-blocking and designed for high-frequency updates.
    """

    @staticmethod
    def track_usage(item_type: str, item_id: str, success: bool = True, duration_ms: float = 0.0):
        """
        Record a usage event for a marketplace item.
        Increments counters in the local SQLite database.
        """
        try:
            with get_db_session() as db:
                # Use subquery for performance if needed, but for SQLite simple filter is fine
                usage = db.query(MarketplaceUsage).filter(
                    MarketplaceUsage.item_type == item_type,
                    MarketplaceUsage.item_id == item_id
                ).first()
                
                if not usage:
                    usage = MarketplaceUsage(
                        item_type=item_type,
                        item_id=item_id,
                        execution_count=1,
                        success_count=1 if success else 0,
                        total_duration_ms=duration_ms
                    )
                    db.add(usage)
                else:
                    usage.execution_count += 1
                    if success:
                        usage.success_count += 1
                    usage.total_duration_ms += duration_ms
                
                db.commit()
        except Exception as e:
            # We don't want analytics to break the main application flow
            logger.error(f"Failed to track marketplace usage: {e}")

    @staticmethod
    def get_pending_reports():
        """
        Get all usage metrics that need to be reported to SaaS.
        Returns a list of reports and resets local counters.
        """
        reports = []
        try:
            with get_db_session() as db:
                usages = db.query(MarketplaceUsage).filter(MarketplaceUsage.execution_count > 0).all()
                now = datetime.now(timezone.utc)
                for usage in usages:
                    # Calculate duration avg safely
                    avg_duration = usage.total_duration_ms / usage.execution_count if usage.execution_count > 0 else 0
                    
                    reports.append({
                        "item_type": usage.item_type,
                        "item_id": usage.item_id,
                        "execution_count": usage.execution_count,
                        "success_count": usage.success_count,
                        "avg_duration_ms": avg_duration,
                        "period_start": usage.last_reported_at or usage.updated_at,
                        "period_end": now
                    })
                    
                    # Reset counters for the next period
                    usage.execution_count = 0
                    usage.success_count = 0
                    usage.total_duration_ms = 0.0
                    usage.last_reported_at = now
                
                db.commit()
        except Exception as e:
            logger.error(f"Failed to get marketplace reports: {e}")
            
        return reports
