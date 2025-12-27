from fastapi import APIRouter, Depends, HTTPException
from ai.data_intelligence import DataIntelligenceEngine, PlatformType
from typing import List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence"])
engine = DataIntelligenceEngine()

@router.get("/insights")
async def get_insights():
    """
    Fetch cross-platform smart insights and anomalies.
    """
    try:
        # For demo/mock purposes, ensure we have some data if registry is empty
        if not engine.entity_registry:
            logger.info("Initializing Intelligence Engine with mock data for /insights")
            platforms_to_seed = [
                PlatformType.ASANA,
                PlatformType.SALESFORCE,
                PlatformType.HUBSPOT,
            ]
            for platform in platforms_to_seed:
                mock_data = engine._mock_platform_connector(platform)
                engine.ingest_platform_data(platform, mock_data)
        
        anomalies = engine.detect_anomalies()
        
        # Sort critical first
        severity_map = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda x: severity_map.get(x.severity, 3))
        
        return {
            "status": "success",
            "count": len(anomalies),
            "insights": anomalies
        }
    except Exception as e:
        logger.error(f"Error fetching insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh")
async def refresh_intelligence():
    """
    Manually trigger a cross-platform data ingestion and analysis.
    """
    try:
        # In a real scenario, this would trigger background tasks to fetch real data
        # For now, we simulate a refresh
        platforms_to_sync = [
            PlatformType.ASANA,
            PlatformType.SALESFORCE,
            PlatformType.HUBSPOT,
            PlatformType.ZENDESK
        ]
        
        for platform in platforms_to_sync:
            data = engine._get_platform_data(platform)
            if data:
                engine.ingest_platform_data(platform, data)
                
        return {"status": "success", "message": "Intelligence data refreshed"}
    except Exception as e:
        logger.error(f"Error refreshing intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))
