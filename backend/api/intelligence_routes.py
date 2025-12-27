from fastapi import APIRouter, Depends, HTTPException
from ai.data_intelligence import DataIntelligenceEngine, PlatformType
from typing import List, Optional, Dict, Any
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
                # We can't await in a generator or similar easily if it's not async
                # But here we are in an async function
                data = await engine._get_platform_data(platform)
                await engine.ingest_platform_data(platform, data)
        
        anomalies = await engine.detect_anomalies()
        
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

@router.get("/entities")
async def get_entities(type: Optional[str] = None, platform: Optional[str] = None):
    """
    Fetch unified entities from the intelligence engine.
    """
    try:
        results = []
        for entity in engine.entity_registry.values():
            if type and entity.entity_type.value != type:
                continue
            if platform and platform not in [p.value for p in entity.source_platforms]:
                continue
            
            # Map UnifiedEntity to a JSON-serializable format
            results.append({
                "id": entity.entity_id,
                "name": entity.canonical_name,
                "type": entity.entity_type.value,
                "platforms": [p.value for p in entity.source_platforms],
                "status": entity.attributes.get("status"),
                "value": entity.attributes.get("amount") or entity.attributes.get("value"),
                "modified_at": entity.updated_at.isoformat()
            })
        
        return {"status": "success", "entities": results}
    except Exception as e:
        logger.error(f"Error fetching entities: {e}")
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
            data = await engine._get_platform_data(platform)
            if data:
                await engine.ingest_platform_data(platform, data)
                
        return {"status": "success", "message": "Intelligence data refreshed"}
    except Exception as e:
        logger.error(f"Error refreshing intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/execute")
async def execute_insight_action(request: Dict[str, Any]):
    """
    Execute an actionable recommendation from an insight.
    """
    try:
        action_type = request.get("action_type")
        payload = request.get("action_payload", {})
        user_id = request.get("user_id", "default_user")

        if action_type == "workflow":
            from advanced_workflow_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            workflow_id = payload.get("workflow_id")
            inputs = payload.get("inputs", {})
            
            logger.info(f"Executing workflow action: {workflow_id}")
            result = await orchestrator.execute_workflow(workflow_id, inputs)
            return {"status": "success", "result": result}

        elif action_type == "tool":
            from integrations.mcp_service import mcp_service
            tool_name = payload.get("tool_name")
            arguments = payload.get("arguments", {})
            
            logger.info(f"Executing tool action: {tool_name}")
            result = await mcp_service.execute_tool(
                "local-tools", 
                tool_name, 
                arguments, 
                {"user_id": user_id}
            )
            return {"status": "success", "result": result}

        raise HTTPException(status_code=400, detail=f"Unsupported action type: {action_type}")
    except Exception as e:
        logger.error(f"Error executing insight action: {e}")
        raise HTTPException(status_code=500, detail=str(e))
