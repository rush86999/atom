"""
ATOM Marketing Unified Service
Unified interface for Google Ads and TikTok Ads.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

from core.integration_service import IntegrationService

try:
    from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline, RecordType
except ImportError:
    logging.warning("Core services not available for Marketing Service")

logger = logging.getLogger(__name__)

class MarketingPlatform(Enum):
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"

class MarketingUnifiedService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.config = config

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Marketing Unified integration capabilities"""
        return {
            "operations": [
                {"id": "get_campaign_performance", "name": "Get Campaign Performance", "parameters": {"platform": "string"}}
            ],
            "required_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if Marketing Unified service is healthy"""
        return {
            "ok": True,
            "status": "healthy",
            "healthy": True,
            "service": "marketing_unified",
            "message": "Marketing Unified service initialized",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a Marketing Unified operation with tenant context."""
        try:
            # Validate tenant_id from context
            if context:
                tenant_id = context.get("tenant_id")
                if tenant_id != self.tenant_id:
                    return {"success": False, "error": "Tenant ID mismatch"}

            if operation == "get_campaign_performance":
                platform = MarketingPlatform(parameters.get("platform", "google_ads"))
                result = await self.get_campaign_performance(platform)
                return {"success": True, "result": result}
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error(f"Error executing Marketing Unified operation {operation}: {e}")
            return {"success": False, "error": str(e)}

    async def get_campaign_performance(self, platform: MarketingPlatform) -> Dict[str, Any]:
        """Fetches ROI and conversion data for marketing campaigns."""
        logger.info(f"Fetching {platform.value} performance data")
        
        # Simulator
        metrics = {
            "platform": platform.value,
            "campaign_id": "c_555",
            "name": "Summer Blowout",
            "spend": 500.0,
            "conversions": 22,
            "cpa": 22.72
        }
        
        atom_ingestion_pipeline.ingest_record(
            app_type=platform.value,
            record_type="campaign",
            data=metrics
        )
        return metrics

# NOTE: Legacy singleton instance removed - use IntegrationRegistry instead
# marketing_service = MarketingUnifiedService(tenant_id="default", config={})
