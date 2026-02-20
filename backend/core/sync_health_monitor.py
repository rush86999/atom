"""
Sync Health Monitor
Health check service for Atom SaaS sync subsystem
Monitors sync status, WebSocket connection, and overall system health
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import SyncState

logger = logging.getLogger(__name__)


class SyncHealthMonitor:
    """
    Monitors health of sync subsystem for Kubernetes probes and monitoring

    Health checks:
    - Last sync age (default: within 30 minutes)
    - WebSocket connection status
    - Recent error count (within 5 minutes)
    - Scheduler status
    """

    def __init__(self):
        self.expected_sync_interval_minutes = 30
        self.error_window_minutes = 5

    def check_health(self, db: Session) -> Dict[str, Any]:
        """
        Perform comprehensive health check

        Returns:
            Health status dict with status, checks, and details
        """
        health_status = {
            "status": "healthy",
            "last_sync": None,
            "sync_age_minutes": None,
            "websocket_connected": False,
            "scheduler_running": False,
            "recent_errors": 0,
            "details": {},
            "checks": {}
        }

        # Check 1: Last sync age
        sync_check = self._check_last_sync(db)
        health_status["checks"]["last_sync"] = sync_check
        health_status["last_sync"] = sync_check.get("last_sync")
        health_status["sync_age_minutes"] = sync_check.get("age_minutes")

        # Check 2: WebSocket connection (placeholder)
        websocket_check = self._check_websocket()
        health_status["checks"]["websocket"] = websocket_check
        health_status["websocket_connected"] = websocket_check.get("connected")

        # Check 3: Scheduler status (placeholder)
        scheduler_check = self._check_scheduler()
        health_status["checks"]["scheduler"] = scheduler_check
        health_status["scheduler_running"] = scheduler_check.get("running")

        # Check 4: Recent errors (placeholder)
        error_check = self._check_recent_errors()
        health_status["checks"]["errors"] = error_check
        health_status["recent_errors"] = error_check.get("error_count")

        # Determine overall status
        failed_checks = [k for k, v in health_status["checks"].items() if not v.get("healthy")]
        degraded_checks = [k for k, v in health_status["checks"].items() if v.get("degraded")]

        if failed_checks:
            health_status["status"] = "unhealthy"
        elif degraded_checks:
            health_status["status"] = "degraded"

        health_status["details"] = {
            "failed_checks": failed_checks,
            "degraded_checks": degraded_checks,
            "total_checks": len(health_status["checks"]),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        return health_status

    def _check_last_sync(self, db: Session) -> Dict[str, Any]:
        """
        Check if last sync is within expected interval

        Returns:
            Dict with healthy status, last_sync time, age_minutes
        """
        try:
            sync_state = db.query(SyncState).order_by(SyncState.last_sync.desc()).first()

            if not sync_state:
                return {
                    "healthy": False,
                    "degraded": True,
                    "message": "No sync records found",
                    "last_sync": None,
                    "age_minutes": None
                }

            last_sync = sync_state.last_sync
            age_minutes = (datetime.utcnow() - last_sync).total_seconds() / 60

            # Healthy if within 1x interval, degraded if within 2x, unhealthy if >2x
            if age_minutes <= self.expected_sync_interval_minutes:
                return {
                    "healthy": True,
                    "degraded": False,
                    "message": f"Last sync {age_minutes:.1f} minutes ago",
                    "last_sync": last_sync.isoformat() + "Z",
                    "age_minutes": round(age_minutes, 1)
                }
            elif age_minutes <= self.expected_sync_interval_minutes * 2:
                return {
                    "healthy": False,
                    "degraded": True,
                    "message": f"Last sync {age_minutes:.1f} minutes ago (stale)",
                    "last_sync": last_sync.isoformat() + "Z",
                    "age_minutes": round(age_minutes, 1)
                }
            else:
                return {
                    "healthy": False,
                    "degraded": False,
                    "message": f"Last sync {age_minutes:.1f} minutes ago (very stale)",
                    "last_sync": last_sync.isoformat() + "Z",
                    "age_minutes": round(age_minutes, 1)
                }

        except Exception as e:
            logger.error(f"Error checking last sync: {e}")
            return {
                "healthy": False,
                "degraded": False,
                "message": f"Error checking sync: {str(e)}",
                "last_sync": None,
                "age_minutes": None
            }

    def _check_websocket(self) -> Dict[str, Any]:
        """
        Check WebSocket connection status

        Returns:
            Dict with healthy status and connected flag
        """
        # Placeholder: Will be implemented in 61-03-websocket-updates
        # For now, assume WebSocket is healthy if not explicitly failed
        return {
            "healthy": True,
            "degraded": False,
            "message": "WebSocket check not yet implemented",
            "connected": None
        }

    def _check_scheduler(self) -> Dict[str, Any]:
        """
        Check if sync scheduler is running

        Returns:
            Dict with healthy status and running flag
        """
        # Placeholder: Will be implemented in 61-01-background-sync
        # For now, assume scheduler is running
        return {
            "healthy": True,
            "degraded": False,
            "message": "Scheduler check not yet implemented",
            "running": None
        }

    def _check_recent_errors(self) -> Dict[str, Any]:
        """
        Check for recent errors in sync operations

        Returns:
            Dict with healthy status and error_count
        """
        # Placeholder: Will query sync error logs from 61-01-background-sync
        # For now, assume no errors
        return {
            "healthy": True,
            "degraded": False,
            "message": "Error check not yet implemented",
            "error_count": 0
        }

    def get_http_status(self, health_status: Dict[str, Any]) -> int:
        """
        Get appropriate HTTP status code for health status

        Args:
            health_status: Health check result dict

        Returns:
            HTTP status code (200, 503)
        """
        if health_status["status"] == "unhealthy":
            return 503
        else:
            # 200 for healthy or degraded
            return 200


# Singleton instance
_health_monitor = None


def get_sync_health_monitor() -> SyncHealthMonitor:
    """Get or create singleton health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SyncHealthMonitor()
    return _health_monitor
