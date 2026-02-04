"""
FastAPI ServiceNow Integration Router
ServiceNow IT Service Management integration for ATOM Chat Interface
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ServiceNow integration models
class ServiceNowAuth(BaseModel):
    instance_url: str = Field(..., description="ServiceNow instance URL")
    username: str = Field(..., description="ServiceNow username")
    password: str = Field(..., description="ServiceNow password")


class ServiceNowIncident(BaseModel):
    short_description: str = Field(..., description="Short description")
    description: str = Field(..., description="Detailed description")
    urgency: str = Field("3", description="Urgency (1=High, 2=Medium, 3=Low)")
    impact: str = Field("3", description="Impact (1=High, 2=Medium, 3=Low)")
    category: str = Field("inquiry", description="Category")
    assignment_group: Optional[str] = Field(None, description="Assignment group")


class ServiceNowChange(BaseModel):
    short_description: str = Field(..., description="Short description")
    description: str = Field(..., description="Detailed description")
    type: str = Field("normal", description="Change type (normal, emergency, standard)")
    risk: str = Field("low", description="Risk level")
    impact: str = Field("low", description="Impact level")


class ServiceNowKnowledge(BaseModel):
    short_description: str = Field(..., description="Article title")
    text: str = Field(..., description="Article content")
    category: str = Field("general", description="Article category")
    kb_knowledge_base: str = Field("ServiceNow", description="Knowledge base")


# Create FastAPI router
servicenow_router = APIRouter()


# Mock ServiceNow service for demonstration
class ServiceNowService:
    def __init__(self):
        self.connected = False
        self.instance_url = None
        self.incidents = []
        self.changes = []
        self.knowledge_articles = []

    async def connect(self, auth: ServiceNowAuth):
        try:
            self.instance_url = auth.instance_url
            self.connected = True

            # Mock data initialization
            self.incidents = [
                {
                    "number": "INC0012345",
                    "short_description": "VPN connection issues",
                    "description": "Users unable to connect to corporate VPN",
                    "urgency": "2",
                    "impact": "2",
                    "state": "In Progress",
                    "priority": "3",
                    "assignment_group": "Network Team",
                    "sys_created_on": datetime.utcnow().isoformat(),
                },
                {
                    "number": "INC0012346",
                    "short_description": "Email delivery delays",
                    "description": "External emails taking longer than usual to deliver",
                    "urgency": "3",
                    "impact": "3",
                    "state": "New",
                    "priority": "4",
                    "assignment_group": "Email Team",
                    "sys_created_on": datetime.utcnow().isoformat(),
                },
            ]

            self.changes = [
                {
                    "number": "CHG0012345",
                    "short_description": "Server patching - November",
                    "description": "Monthly security patching for production servers",
                    "type": "normal",
                    "risk": "low",
                    "impact": "low",
                    "state": "Scheduled",
                    "start_date": datetime.utcnow().isoformat(),
                }
            ]

            self.knowledge_articles = [
                {
                    "number": "KB0012345",
                    "short_description": "How to reset your password",
                    "text": "Step-by-step guide for password reset...",
                    "category": "User Support",
                    "kb_knowledge_base": "ServiceNow",
                    "workflow_state": "Published",
                }
            ]

            return True
        except Exception as e:
            logger.error(f"Failed to connect to ServiceNow: {e}")
            return False

    async def create_incident(self, incident: ServiceNowIncident) -> Dict[str, Any]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")

        incident_number = f"INC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        new_incident = {
            "number": incident_number,
            "short_description": incident.short_description,
            "description": incident.description,
            "urgency": incident.urgency,
            "impact": incident.impact,
            "category": incident.category,
            "assignment_group": incident.assignment_group,
            "state": "New",
            "priority": self._calculate_priority(incident.urgency, incident.impact),
            "sys_created_on": datetime.utcnow().isoformat(),
        }

        self.incidents.append(new_incident)
        return new_incident

    async def get_incidents(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")

        if state:
            return [inc for inc in self.incidents if inc.get("state") == state]
        return self.incidents

    async def create_change(self, change: ServiceNowChange) -> Dict[str, Any]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")

        change_number = f"CHG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        new_change = {
            "number": change_number,
            "short_description": change.short_description,
            "description": change.description,
            "type": change.type,
            "risk": change.risk,
            "impact": change.impact,
            "state": "New",
            "start_date": datetime.utcnow().isoformat(),
        }

        self.changes.append(new_change)
        return new_change

    async def get_changes(self) -> List[Dict[str, Any]]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
        return self.changes

    async def create_knowledge_article(
        self, article: ServiceNowKnowledge
    ) -> Dict[str, Any]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")

        article_number = f"KB{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        new_article = {
            "number": article_number,
            "short_description": article.short_description,
            "text": article.text,
            "category": article.category,
            "kb_knowledge_base": article.kb_knowledge_base,
            "workflow_state": "Draft",
            "sys_created_on": datetime.utcnow().isoformat(),
        }

        self.knowledge_articles.append(new_article)
        return new_article

    async def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        if not self.connected:
            raise HTTPException(status_code=400, detail="Not connected to ServiceNow")

        results = []
        for article in self.knowledge_articles:
            if (
                query.lower() in article["short_description"].lower()
                or query.lower() in article["text"].lower()
            ):
                results.append(article)
        return results

    def _calculate_priority(self, urgency: str, impact: str) -> str:
        urgency_val = int(urgency)
        impact_val = int(impact)

        if urgency_val == 1 and impact_val == 1:
            return "1"  # Critical
        elif urgency_val <= 2 and impact_val <= 2:
            return "2"  # High
        elif urgency_val <= 3 and impact_val <= 3:
            return "3"  # Moderate
        else:
            return "4"  # Low


# Initialize ServiceNow service
servicenow_service = ServiceNowService()


# ServiceNow API endpoints
@servicenow_router.post("/servicenow/auth/connect")
async def servicenow_connect(auth: ServiceNowAuth):
    try:
        connected = await servicenow_service.connect(auth)
        if connected:
            return {
                "success": True,
                "message": "Successfully connected to ServiceNow",
                "instance_url": servicenow_service.instance_url,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=400, detail="Failed to connect to ServiceNow"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@servicenow_router.get("/servicenow/health")
async def servicenow_health_check():
    return {
        "status": "healthy" if servicenow_service.connected else "disconnected",
        "service": "servicenow_integration",
        "connected": servicenow_service.connected,
        "instance_url": servicenow_service.instance_url,
        "incidents_count": len(servicenow_service.incidents),
        "changes_count": len(servicenow_service.changes),
        "knowledge_articles_count": len(servicenow_service.knowledge_articles),
        "timestamp": datetime.utcnow().isoformat(),
    }


@servicenow_router.post("/servicenow/incidents")
async def create_incident(incident: ServiceNowIncident):
    try:
        result = await servicenow_service.create_incident(incident)
        return {
            "success": True,
            "incident_number": result["number"],
            "message": "Incident created successfully",
            "incident": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create incident: {str(e)}"
        )


@servicenow_router.get("/servicenow/incidents")
async def get_incidents(
    state: Optional[str] = Query(None, description="Filter by state"),
):
    try:
        incidents = await servicenow_service.get_incidents(state)
        return {"incidents": incidents, "total": len(incidents), "state_filter": state}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get incidents: {str(e)}"
        )


@servicenow_router.post("/servicenow/changes")
async def create_change(change: ServiceNowChange):
    try:
        result = await servicenow_service.create_change(change)
        return {
            "success": True,
            "change_number": result["number"],
            "message": "Change request created successfully",
            "change": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create change: {str(e)}"
        )


@servicenow_router.get("/servicenow/changes")
async def get_changes():
    try:
        changes = await servicenow_service.get_changes()
        return {"changes": changes, "total": len(changes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get changes: {str(e)}")


@servicenow_router.post("/servicenow/knowledge")
async def create_knowledge_article(article: ServiceNowKnowledge):
    try:
        result = await servicenow_service.create_knowledge_article(article)
        return {
            "success": True,
            "article_number": result["number"],
            "message": "Knowledge article created successfully",
            "article": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create knowledge article: {str(e)}"
        )


@servicenow_router.get("/servicenow/knowledge/search")
async def search_knowledge(query: str = Query(..., description="Search query")):
    try:
        results = await servicenow_service.search_knowledge(query)
        return {"results": results, "query": query, "total": len(results)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search knowledge: {str(e)}"
        )


@servicenow_router.get("/servicenow/dashboard")
async def get_servicenow_dashboard():
    try:
        open_incidents = [
            inc for inc in servicenow_service.incidents if inc.get("state") != "Closed"
        ]
        pending_changes = [
            chg for chg in servicenow_service.changes if chg.get("state") == "New"
        ]

        return {
            "dashboard": {
                "open_incidents": len(open_incidents),
                "pending_changes": len(pending_changes),
                "knowledge_articles": len(servicenow_service.knowledge_articles),
                "incident_breakdown": {
                    "new": len(
                        [
                            inc
                            for inc in servicenow_service.incidents
                            if inc.get("state") == "New"
                        ]
                    ),
                    "in_progress": len(
                        [
                            inc
                            for inc in servicenow_service.incidents
                            if inc.get("state") == "In Progress"
                        ]
                    ),
                    "resolved": len(
                        [
                            inc
                            for inc in servicenow_service.incidents
                            if inc.get("state") == "Resolved"
                        ]
                    ),
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get dashboard: {str(e)}"
        )


logger.info("ServiceNow FastAPI router initialized")

# Export router for main application integration
router = servicenow_router
