from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import asyncio
import os

from integrations.asana_service import asana_service
from integrations.jira_service import get_jira_service
from integrations.zoho_projects_service import ZohoProjectsService
from integrations.microsoft365_service import microsoft365_service
from db_connection import get_db_connection

router = APIRouter(prefix="/api/atom/projects/live", tags=["projects-live"])
logger = logging.getLogger(__name__)

# --- Data Models ---

class UnifiedTask(BaseModel):
    name: str
    platform: str  # 'asana', 'jira', 'zoho', 'planner'
    status: str
    priority: Optional[str] = "normal"
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    project_name: Optional[str] = None
    url: Optional[str] = None

class ProjectStats(BaseModel):
    total_active_tasks: int
    completed_today: int
    overdue_count: int
    tasks_by_platform: Dict[str, int]

class LiveProjectsResponse(BaseModel):
    ok: bool = True
    stats: ProjectStats
    tasks: List[UnifiedTask]
    providers: Dict[str, bool]

# --- Helper Functions ---

def map_asana_task(task: Dict[str, Any]) -> UnifiedTask:
    return UnifiedTask(
        id=task.get("gid"),
        name=task.get("name") or "Untitled Task",
        platform="asana",
        status="completed" if task.get("completed") else "active",
        assignee=task.get("assignee_name"),
        due_date=task.get("due_on"),
        project_name=None, # Expensive to fetch per task, skipped for live view speed
        url=task.get("url")
    )

def map_jira_issue(issue: Dict[str, Any], base_url: str) -> UnifiedTask:
    fields = issue.get("fields", {})
    return UnifiedTask(
        id=issue.get("key"),
        name=fields.get("summary") or "Untitled Issue",
        platform="jira",
        status=fields.get("status", {}).get("name", "Unknown"),
        priority=fields.get("priority", {}).get("name", "normal"),
        assignee=fields.get("assignee", {}).get("displayName"),
        due_date=fields.get("duedate"),
        project_name=fields.get("project", {}).get("name"),
        url=f"{base_url}/browse/{issue.get('key')}"
    )

def map_zoho_task(task: Dict[str, Any]) -> UnifiedTask:
    return UnifiedTask(
        id=task.get("id_string"),
        name=task.get("name") or "Untitled Zoho Task",
        platform="zoho",
        status="completed" if task.get("status", {}).get("type") == "completed" else "active",
        priority=task.get("priority", "normal"),
        assignee=task.get("created_person"),
        due_date=task.get("end_date"),
        project_name=task.get("project_name")
    )

def map_planner_task(task: Dict[str, Any]) -> UnifiedTask:
    return UnifiedTask(
        id=task.get("id", "planner_task"),
        name=task.get("title") or "Untitled MS Task",
        platform="planner",
        status="completed" if task.get("completedDateTime") else "active",
        priority="normal", # Planner has complexity in priority mapping
        due_date=task.get("dueDateTime"),
        project_name="MS Planner"
    )

# --- Endpoints ---

@router.get("/board", response_model=LiveProjectsResponse)
async def get_live_project_board(
    limit: int = 50,
    # User ID dependency would ideally be here
):
    """
    Fetch live tasks from connected Project Management tools (Asana, Jira)
    and aggregate them into a unified board view.
    """
    tasks = []
    providers_status = {"asana": False, "jira": False, "zoho": False, "planner": False}

    # 1. Fetch Asana Tasks
    try:
         # Placeholder for token retrieval logic
         # In a real user-context, we'd fetch tokens from DB
         pass
    except Exception as e:
        logger.warning(f"Failed to fetch live Asana tasks: {e}")

    # 2. Fetch Jira Issues
    try:
        jira = get_jira_service()
        # Verify if environmental config is present (Mock/Dev mode)
        test_conn = jira.test_connection()
        if test_conn.get("authenticated"):
             # JQL for open issues assigned to current user fallback
             # "assignee = currentUser() AND status != Done"
             jql = "order by created DESC" 
             raw_data = jira.search_issues(jql=jql, max_results=limit)
             raw_issues = raw_data.get("issues", [])
             
             base_url = jira.base_url
             tasks.extend([map_jira_issue(i, base_url) for i in raw_issues])
             providers_status["jira"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Jira issues: {e}")

    # 3. Fetch Zoho Projects Tasks
    try:
        zoho_token = os.getenv("ZOHO_CRM_ACCESS_TOKEN") # Reusing same base secret if applicable or ZOHO_PROJECTS_TOKEN
        portal_id = os.getenv("ZOHO_PROJECTS_PORTAL_ID")
        
        if zoho_token and portal_id:
            zoho = ZohoProjectsService()
            raw_tasks = await zoho.get_all_active_tasks(zoho_token, portal_id, limit=limit)
            tasks.extend([map_zoho_task(t) for t in raw_tasks])
            providers_status["zoho"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Zoho Projects tasks: {e}")

    # 4. Fetch Microsoft Planner Tasks
    try:
        ms_token = os.getenv("MICROSOFT_365_ACCESS_TOKEN")
        if ms_token:
            res = await microsoft365_service.get_planner_tasks(access_token=ms_token, top=limit)
            if res.get("status") == "success":
                raw_tasks = res.get("data", {}).get("value", [])
                tasks.extend([map_planner_task(t) for t in raw_tasks])
                providers_status["planner"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live MS Planner tasks: {e}")

    # Calculate Stats
    total_active = len(tasks)
    # Simple logic for overdue - robust logic would parse dates
    overdue = 0 
    
        "asana": len([t for t in tasks if t.platform == 'asana']),
        "jira": len([t for t in tasks if t.platform == 'jira']),
        "zoho": len([t for t in tasks if t.platform == 'zoho']),
        "planner": len([t for t in tasks if t.platform == 'planner'])
    }
    
    return LiveProjectsResponse(
        ok=True,
        stats=ProjectStats(
            total_active_tasks=total_active,
            completed_today=0, # Need more logic/history for this
            overdue_count=overdue,
            tasks_by_platform=platform_counts
        ),
        tasks=tasks,
        providers=providers_status
    )
