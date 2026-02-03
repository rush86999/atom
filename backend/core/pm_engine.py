import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from service_delivery.models import Milestone, MilestoneStatus, Project, ProjectStatus, ProjectTask
from sqlalchemy.orm import Session

from core.ai_service import get_ai_service
from core.database import get_db_session
from core.graphrag_engine import graphrag_engine
from core.knowledge_extractor import KnowledgeExtractor
from core.pm_swarm import AutonomousBusinessSwarm
from core.resource_reasoning import ResourceReasoningEngine
from core.workforce_analytics import WorkforceAnalyticsService

logger = logging.getLogger(__name__)

class AIProjectManager:
    """
    Engine for AI-driven Project Management automations.
    """
    def __init__(self, db_session: Any = None):
        self.extractor = KnowledgeExtractor()
        self.ai = get_ai_service()
        self.db_session = db_session
        self.analytics = WorkforceAnalyticsService(db_session=db_session)
        self.reasoning = ResourceReasoningEngine(db_session=db_session)

    async def generate_project_from_nl(self, prompt: str, user_id: str, workspace_id: str = "default", contract_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translates a natural language prompt into a structured Project -> Milestone -> Task hierarchy.
        """
        logger.info(f"Generating project from NL for user {user_id}: {prompt}")
        
        system_prompt = """
        You are an expert Project Manager. Decompose the user's request into a structured project plan.
        Return a JSON object with:
        - "name": Project name
        - "description": Project summary
        - "priority": low, medium, high, critical
        - "planned_duration_days": estimate
        - "budget_amount": estimate if mentioned
        - "milestones": List of objects:
            - "name": Milestone name
            - "order": Integer
            - "planned_start_day": (Day offset from project start)
            - "duration_days": estimate
            - "tasks": List of objects:
                - "name": Task name
                - "description": Detailed task instruction
        """
        
        try:
            response = await self.ai.process_with_nlu(prompt, provider="openai", system_prompt=system_prompt)
            # Assuming nlu_result contains the parsed JSON
            project_data = response.get("nlu_result", response)
            
            db = self.db_session or get_db_session()
            try:
                # 0. Calculate Workspace Bias for duration adjustment
                ws_bias = self.analytics.calculate_estimation_bias(workspace_id)
                bias_factor = ws_bias.get("bias_factor", 1.0)
                
                # 1. Create Project
                start_date = datetime.now()
                planned_days = project_data.get("planned_duration_days", 30)
                
                # Adjust duration by workspace bias
                adjusted_days = planned_days * bias_factor
                end_date = start_date + timedelta(days=adjusted_days)
                
                project = Project(
                    id=f"proj_{uuid.uuid4().hex[:8]}",
                    workspace_id=workspace_id,
                    contract_id=contract_id,
                    name=project_data.get("name", "New AI Generated Project"),
                    description=project_data.get("description", ""),
                    priority=project_data.get("priority", "medium"),
                    budget_amount=float(project_data.get("budget_amount", 0.0)),
                    planned_start_date=start_date,
                    planned_end_date=end_date,
                    status=ProjectStatus.PENDING
                )
                db.add(project)
                
                # 2. Create Milestones and Tasks
                for m_data in project_data.get("milestones", []):
                    m_start = start_date + timedelta(days=m_data.get("planned_start_day", 0))
                    m_end = m_start + timedelta(days=m_data.get("duration_days", 7))
                    
                    milestone = Milestone(
                        id=f"ms_{uuid.uuid4().hex[:8]}",
                        workspace_id=workspace_id,
                        project_id=project.id,
                        name=m_data.get("name"),
                        order=m_data.get("order", 0),
                        planned_start_date=m_start,
                        due_date=m_end,
                        status=MilestoneStatus.PENDING
                    )
                    db.add(milestone)
                    db.flush() # Get milestone ID for tasks
                    
                    for t_data in m_data.get("tasks", []):
                        task = ProjectTask(
                            id=f"task_{uuid.uuid4().hex[:8]}",
                            workspace_id=workspace_id,
                            project_id=project.id,
                            milestone_id=milestone.id,
                            name=t_data.get("name"),
                            description=t_data.get("description"),
                            status="pending"
                        )
                        db.add(task)
                
                db.commit()
                logger.info(f"Successfully generated project {project.id}")
                return {"status": "success", "project_id": project.id, "name": project.name}
            finally:
                if not self.db_session:
                    db.close()
                
        except Exception as e:
            logger.error(f"Failed to generate project: {e}")
            return {"status": "failed", "error": str(e)}

    async def infer_project_status(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        Infers project progress by querying GraphRAG and system activity.
        """
        logger.info(f"Inferring status for project {project_id}")
        
        db = self.db_session or get_db_session()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"status": "error", "message": "Project not found"}
            
            milestones = db.query(Milestone).filter(Milestone.project_id == project_id).all()
            
            updates = []
            for milestone in milestones:
                tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == milestone.id).all()
                for task in tasks:
                    if task.status == "completed":
                        continue
                        
                    # Query GraphRAG for progress on this specific task
                    query = f"Has the task '{task.name}' for project '{project.name}' been completed or worked on recently?"
                    rag_result = graphrag_engine.query(user_id, query, mode="local")
                    
                    # Analyze RAG result for evidence
                    evidence = rag_result.get("answer", "").lower()
                    if "completed" in evidence or "done" in evidence or "finished" in evidence:
                        task.status = "completed"
                        task.completed_at = datetime.now()
                        updates.append(f"Task '{task.name}' inferred as COMPLETED")
                    elif "started" in evidence or "working" in evidence or "in progress" in evidence:
                        task.status = "in_progress"
                        updates.append(f"Task '{task.name}' inferred as IN_PROGRESS")
            
            # Update Milestone status if all tasks are done
            for milestone in milestones:
                total_tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == milestone.id).count()
                completed_tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == milestone.id, ProjectTask.status == "completed").count()
                
                if total_tasks > 0 and total_tasks == completed_tasks:
                    milestone.status = MilestoneStatus.COMPLETED
                    milestone.completed_at = datetime.now()
                    updates.append(f"Milestone '{milestone.name}' marked as COMPLETED")
            
            db.commit()
            return {"status": "success", "updates": updates}
        finally:
            if not self.db_session:
                db.close()

    async def analyze_project_risks(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        Detects schedule slips and budget risks.
        """
        db = self.db_session or get_db_session()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"status": "error", "message": "Project not found"}
            
            risks = []
            now = datetime.now()
            
            # 1. Schedule Risk
            if project.planned_end_date and now > project.planned_end_date and project.status != ProjectStatus.COMPLETED:
                risks.append({
                    "type": "schedule",
                    "severity": "high",
                    "message": f"Project '{project.name}' has passed its planned end date."
                })
            
            # 2. Milestone Slippage
            milestones = db.query(Milestone).filter(Milestone.project_id == project_id).all()
            for ms in milestones:
                if ms.due_date and now > ms.due_date and ms.status != MilestoneStatus.COMPLETED:
                    risks.append({
                        "type": "milestone_slip",
                        "severity": "medium",
                        "milestone": ms.name,
                        "message": f"Milestone '{ms.name}' is overdue."
                    })
            
            # 3. Budget Risk (if actual_hours > budget_hours)
            if project.budget_hours > 0 and project.actual_hours > project.budget_hours:
                risks.append({
                    "type": "budget",
                    "severity": "high",
                    "message": f"Project '{project.name}' has exceeded its hourly budget."
                })
            
            # Update project risk level
            if any(r["severity"] == "high" for r in risks):
                project.risk_level = "high"
            elif any(r["severity"] == "medium" for r in risks):
                project.risk_level = "medium"
            else:
                project.risk_level = "low"
            
            db.commit()
            return {"status": "success", "risks": risks, "risk_level": project.risk_level}
        finally:
            if not self.db_session:
                db.close()

    async def auto_assign_resources(self, project_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Automatically assigns the best team members to all tasks in a project.
        """
        logger.info(f"Auto-assigning resources for project {project_id}")
        
        db = self.db_session or get_db_session()
        try:
            tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            assignments = []
            
            for task in tasks:
                if task.assigned_to:
                    continue
                
                suggestion = await self.reasoning.get_optimal_assignee(workspace_id, task.name, task.description)
                best_user = suggestion.get("suggested_user")
                
                if best_user:
                    task.assigned_to = best_user["user_id"]
                    assignments.append({
                        "task_id": task.id,
                        "task_name": task.name,
                        "assigned_to": best_user["name"],
                        "confidence": best_user["composite_score"]
                    })
            
            db.commit()
            return {"status": "success", "assignments": assignments}
        finally:
            if not self.db_session:
                db.close()

    async def trigger_autonomous_correction(self, workspace_id: str = "default", project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Invokes the PM Swarm to analyze the current state and apply autonomous corrections.
        """
        logger.info(f"Triggering autonomous correction for workspace {workspace_id}, project {project_id}")
        swarm = AutonomousBusinessSwarm(db_session=self.db_session)
        try:
            result = await swarm.run_correction_cycle(workspace_id, project_id)
            return result
        except Exception as e:
            logger.error(f"Autonomous correction failed: {e}")
            return {"status": "failed", "error": str(e)}

# Global Instance
pm_engine = AIProjectManager()
