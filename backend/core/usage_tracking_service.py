import logging
from typing import Any, Union
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class UsageTrackingService:
    """
    Shim for UsageTrackingService in atom-upstream.
    Provides a compatible interface without the SaaS-specific ACU/Quota logic.
    """

    def __init__(self, tenant_id: str, db: Session = None):
        self.tenant_id = tenant_id
        self.db = db

    def close(self):
        """Close session if needed (stub)"""
        pass

    async def track_acu_usage(self, **kwargs) -> Any:
        """Stub for tracking usage (does nothing in OS)"""
        logger.debug(f"Usage tracked (stub): {kwargs}")
        return None

    async def check_quota_before_job(self, **kwargs) -> dict[str, Any]:
        """Stub for quota check (always allowed in OS)"""
        return {
            "allowed": True,
            "remaining_quota": 999999,
            "current_usage": 0,
            "plan_limit": 999999,
        }

    def calculate_acu_consumed(self, **kwargs) -> float:
        """Stub for ACU calculation"""
        return 0.0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
