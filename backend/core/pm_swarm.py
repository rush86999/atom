from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from service_delivery.models import Milestone, Project, ProjectTask

from core.database import get_db_session
from core.models import User, Workspace
from core.workforce_analytics import WorkforceAnalyticsService

logger = logging.getLogger(__name__)

class AutonomousBusinessSwarm:
    """
    A multi-agent swarm that negotiates project/operational corrections.
    Roles: Planner, Risk Agent, Finance Agent, Executor, Auditor.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session
        self.analytics = WorkforceAnalyticsService(db_session=db_session)

    async def run_correction_cycle(self, workspace_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a full 'Correction Cycle' for either a specific project or general operations.
        """
        db = self.db or get_db_session()
        try:
            # 1. Gather State
            state = self._gather_state(workspace_id, project_id, db)
            
            # 2. Sequential/Parallel Negotiation
            # In a real system, these would be separate LLM calls. 
            # Here we implement the logic for their 'decision making'.
            
            # Phase A: Planner Proposes
            proposal = self._planner_propose(state)
            
            # Phase B: Specialized Agents Critique
            risk_critique = self._risk_critique(proposal, state)
            finance_critique = self._finance_critique(proposal, state)
            executor_critique = self._executor_critique(proposal, state)
            
            # Phase C: Auditor Reconciles
            final_decision = self._auditor_finalize(
                proposal, 
                [risk_critique, finance_critique, executor_critique],
                state
            )
            
            # 3. Apply Decision if approved
            if final_decision.get("status") == "approved":
                # Guardrail: Learning Phase check
                workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
                if workspace and not workspace.is_startup and not workspace.learning_phase_completed:
                    final_decision["status"] = "learning_mode"
                    final_decision["hitl_request"] = "Swarm is in 'Learning Phase'. Recommendations are generated but not applied autonomously. Please review and approve manually."
                else:
                    self._apply_corrections(final_decision, db)
                
            return {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "decision": final_decision,
                "negotiation_log": {
                    "proposal": proposal,
                    "critiques": {
                        "risk": risk_critique,
                        "finance": finance_critique,
                        "executor": executor_critique
                    }
                }
            }
        finally:
            if not self.db:
                db.close()

    def _gather_state(self, workspace_id: str, project_id: Optional[str], db: Any) -> Dict[str, Any]:
        """Collects metrics, tasks, and constraints for the swarm."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "workspace_id": workspace_id,
            "bias_profile": self.analytics.calculate_estimation_bias(workspace_id),
            "skill_gaps": self.analytics.map_skill_gaps(workspace_id)
        }
        
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.warning(f"Project {project_id} not found during state gathering.")
                return state
                
            tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            state["project"] = {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "planned_end_date": project.planned_end_date.isoformat() if project.planned_end_date else None,
                "tasks_total": len(tasks),
                "tasks_overdue": len([t for t in tasks if t.due_date and t.due_date < datetime.now() and t.status != "completed"])
            }
        return state

    def _planner_propose(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Proposes changes based on delays or bottlenecks."""
        proposal = {"type": "stabilization", "actions": []}
        project_id = state.get("project", {}).get("id")
        
        # If project is falling behind, propose extension
        if state.get("project") and state["project"]["tasks_overdue"] > 0:
            proposal["actions"].append({
                "action": "extend_timeline",
                "project_id": project_id,
                "days": 7,
                "reason": "Overdue tasks detected"
            })
            
        # If there are skill gaps, propose reallocation
        mismatches = state["skill_gaps"].get("assignment_mismatches", [])
        for m in mismatches:
            proposal["actions"].append({
                "action": "reassign_task",
                "task_id": m["task_id"],
                "project_id": project_id,
                "reason": f"Missing skills: {m['missing_skills']}"
            })
            
        return proposal

    def _risk_critique(self, proposal: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates if the proposal is realistic based on historical bias."""
        bias_factor = state["bias_profile"].get("bias_factor", 1.0)
        
        for action in proposal["actions"]:
            if action["action"] == "extend_timeline":
                # If team is chronically optimistic (bias > 1.2), suggest more time
                if bias_factor > 1.2:
                    return {"status": "request_change", "adjustment": "Add 3 more days due to historical bias."}
                    
        return {"status": "ok"}

    def _finance_critique(self, proposal: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Checks if timeline extensions or reassignments impact budget/runway."""
        # Simplified: Check if any action costs 'credits' or 'unbilled hours'
        return {"status": "ok"}

    def _executor_critique(self, proposal: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Checks if there's someone actually available for reassignment."""
        unmet = state["skill_gaps"].get("unmet_requirements", {})
        
        for action in proposal["actions"]:
            if action["action"] == "reassign_task":
                # Check if we actually have anyone with the skill now
                # In this swarm, if we can't find anyone, we flag for Auditor to ask user
                if any(action["reason"].lower().find(skill) != -1 for skill in unmet):
                    return {"status": "blocker", "reason": "missing_skill_data"}
                    
        return {"status": "ok"}

    def _auditor_finalize(self, proposal: Dict[str, Any], critiques: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
        """Final decision node. Triggers HITL if needed."""
        status = "approved"
        modified_actions = proposal["actions"]
        hitl_request = None
        
        for c in critiques:
            if c["status"] == "blocker":
                if c.get("reason") == "missing_skill_data":
                    status = "pending_user"
                    hitl_request = "Skill gap detected with no available team matches. Please provide guidance or update team skills."
            elif c["status"] == "request_change":
                # Apply risk adjustments
                for action in modified_actions:
                    if action["action"] == "extend_timeline" and "3 more days" in c.get("adjustment", ""):
                        action["days"] += 3
                        
        return {
            "status": status,
            "actions": modified_actions,
            "hitl_request": hitl_request
        }

    def _apply_corrections(self, decision: Dict[str, Any], db: Any):
        """Persists the agreed variations to the database."""
        for action in decision["actions"]:
            if action["action"] == "extend_timeline":
                # Update project planned_end_date
                project_id = action.get("project_id")
                if project_id:
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if project:
                        delta = timedelta(days=action["days"])
                        project.planned_end_date = project.planned_end_date + delta
                        logger.info(f"Swarm extended project {project_id} by {action['days']} days.")
                        
            elif action["action"] == "reassign_task":
                # Unassign task and mark as 'needs_reassignment'
                task_id = action.get("task_id")
                if task_id:
                    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
                    if task:
                        task.assigned_to = None
                        if not task.metadata_json:
                            task.metadata_json = {}
                        task.metadata_json["needs_reassignment"] = True
                        task.metadata_json["reassignment_reason"] = action["reason"]
                        logger.info(f"Swarm unassigned task {task_id} due to skill gap.")
        db.commit()
