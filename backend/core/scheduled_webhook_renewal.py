"""Scheduled webhook renewal entry point.

atom's real renewal logic lives in core.webhook_renewal_service
(class ScheduledWebhookRenewalService, run_staggered_renewal_cycle) but
nothing ever invoked it: main_api_app's startup block imports that class
from THIS module name, which never existed (2026-05 port left the file
behind; 2026-09-05 recovered from atom-saas and re-pointed at the real
implementation, whose class name and method signature differ from the
saas upstream).
"""
import logging
from typing import Any, Dict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from core.webhook_renewal_service import (
    ScheduledWebhookRenewalService as _AtomRenewalService,
)


class ScheduledWebhookRenewalService(_AtomRenewalService):
    """Startup-block facade: same name main_api_app imports, plus the
    run_renewal_job() entry the renewal loop calls."""

    async def run_renewal_job(self) -> Dict[str, Any]:
        logger.info("Running scheduled webhook renewal job")
        try:
            results = await self.run_staggered_renewal_cycle()
            logger.info(f"Webhook renewal results: {results}")
            return {"status": "success", "renewals": results}
        except Exception as e:
            logger.error(f"Failed to run webhook renewal: {e}")
            return {"status": "error", "message": str(e)}
