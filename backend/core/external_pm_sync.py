import logging
from typing import Any, Dict, List, Optional
from service_delivery.models import Milestone, Project, ProjectTask
from sqlalchemy.orm import Session

from core.database import get_db_session
from integrations.asana_real_service import asana_real_service
from integrations.linear_service import linear_service

logger = logging.getLogger(__name__)

class ExternalPMSyncService:
    """
    Handles synchronization of projects and tasks with external PM tools.
    """

    async def sync_project_to_external(self, project_id: str, platform: str, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Mirrors an Atom project and its tasks to an external platform.
        """
        logger.info(f"Syncing project {project_id} to {platform}")
        
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"status": "error", "message": "Project not found"}
            
            if platform.lower() == "asana":
                return await self._sync_to_asana(project, db)
            elif platform.lower() == "linear":
                return await self._sync_to_linear(project, db)
            else:
                return {"status": "error", "message": f"Platform {platform} not supported for sync"}

    async def _sync_to_asana(self, project: Project, db: Session) -> Dict[str, Any]:
        """Specific logic for Asana sync"""
        try:
            # 1. Create Project
            asana_project = await asana_real_service.create_project({
                "name": project.name,
                "description": project.description or f"Synced from Atom (Project ID: {project.id})"
            })
            
            if not asana_project:
                return {"status": "error", "message": "Failed to create project in Asana"}
                
            asana_project_gid = asana_project["id"]
            
            # 2. Sync Milestones and Tasks
            milestones = db.query(Milestone).filter(Milestone.project_id == project.id).all()
            for ms in milestones:
                # In Asana, milestones can be tasks with the 'milestone' flag, 
                # but for MVP we'll create them as tasks or sections if wanted.
                # Let's create sections or just tasks with markers.
                tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == ms.id).all()
                for task in tasks:
                    await asana_real_service.create_task({
                        "title": f"[{ms.name}] {task.name}",
                        "description": task.description or "",
                        "project": asana_project_gid
                    })
            
            return {"status": "success", "external_id": asana_project_gid, "platform": "asana"}
        except Exception as e:
            logger.error(f"Asana sync failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _sync_to_linear(self, project: Project, db: Session) -> Dict[str, Any]:
        """Specific logic for Linear sync"""
        try:
            # 1. Create Project (Requires a Team ID - for MVP we'll use a hack or assume default)
            # In a real app, we'd look up the workspace's Linear team.
            teams = await linear_service.get_teams()
            if not teams:
                return {"status": "error", "message": "No teams found in Linear to assign project"}
            
            team_id = teams[0]["id"]
            
            linear_resp = await linear_service.create_project(
                name=project.name,
                team_ids=[team_id],
                description=project.description or f"Synced from Atom"
            )
            
            if not linear_resp.get("success"):
                return {"status": "error", "message": "Failed to create project in Linear"}
                
            linear_project_id = linear_resp["project"]["id"]
            
            # 2. Sync Tasks (Linear Issues)
            milestones = db.query(Milestone).filter(Milestone.project_id == project.id).all()
            for ms in milestones:
                tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == ms.id).all()
                for task in tasks:
                    await linear_service.create_issue(
                        title=f"[{ms.name}] {task.name}",
                        team_id=team_id,
                        description=task.description or ""
                    )
            
            return {"status": "success", "external_id": linear_project_id, "platform": "linear"}
        except Exception as e:
            logger.error(f"Linear sync failed: {e}")
            return {"status": "error", "message": str(e)}

# Global Instance
external_pm_sync = ExternalPMSyncService()
