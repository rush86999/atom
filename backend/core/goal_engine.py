import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)

class GoalSubTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    due_date: datetime
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, DELAYED
    assigned_to: Optional[str] = None
    task_id: Optional[str] = None # Reference to unified task system

class Goal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    target_date: datetime
    status: str = "ACTIVE"  # ACTIVE, COMPLETED, ON_HOLD, AT_RISK
    progress: float = 0.0  # 0 to 100
    sub_tasks: List[GoalSubTask] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: str = "default"
    blueprint_id: Optional[str] = None

class GoalEngine:
    def __init__(self):
        self.goals: Dict[str, Goal] = {}
        # Mock storage for now, would be a DB in production
    
    async def create_goal_from_text(self, title: str, target_date: datetime, owner_id: str = "default", tenant_id: str = "default") -> Goal:
        """Create a new goal and automatically decompose it into sub-tasks"""
        goal = Goal(
            title=title,
            target_date=target_date,
            owner_id=owner_id
        )
        
        # Determine if we should use the advanced Queen Agent or simple template
        use_advanced = len(title.split()) > 3 or any(k in title.lower() for k in ["build", "create", "integrate", "automate"])
        
        if use_advanced:
            try:
                from core.database import SessionLocal
                from core.llm_router import LLMRouter
                from core.agents.queen_agent import QueenAgent
                
                with SessionLocal() as db:
                    llm = LLMRouter()
                    queen = QueenAgent(db, llm)
                    blueprint = await queen.generate_blueprint(title, tenant_id=tenant_id)
                    
                    sub_tasks = []
                    # Map blueprint nodes to sub-tasks
                    now = datetime.utcnow()
                    days_total = (target_date - now).days
                    if days_total < 1: days_total = 7
                    
                    nodes = blueprint.get("nodes", [])
                    for i, node in enumerate(nodes):
                        # Approximate due date linearly
                        node_due = now + timedelta(days=max(1, (i + 1) * days_total // len(nodes)))
                        sub_tasks.append(GoalSubTask(
                            title=node["name"],
                            description=node.get("capability_required"),
                            due_date=min(node_due, target_date)
                        ))
                    
                    # Add missing capabilities as research tasks
                    for missing in blueprint.get("missing_capabilities", []):
                        sub_tasks.append(GoalSubTask(
                            title=f"Research capability: {missing['name']}",
                            description=missing.get("description"),
                            due_date=now + timedelta(days=2)
                        ))
                    
                    goal.sub_tasks = sub_tasks
                    goal.blueprint_id = blueprint.get("blueprint_id")
                    logger.info(f"Queen Architected Goal: {goal.title} with {len(goal.sub_tasks)} steps (Blueprint: {goal.blueprint_id})")
            except Exception as e:
                logger.error(f"Error using Queen Agent for goal: {e}")
                # Fallback to simple decomposition
                sub_tasks = await self.decompose_goal(title, target_date)
                goal.sub_tasks = sub_tasks
        else:
            # Decompose goal into sub-tasks (Template-based fallback)
            sub_tasks = await self.decompose_goal(title, target_date)
            goal.sub_tasks = sub_tasks
        
        self.goals[goal.id] = goal
        return goal

    async def decompose_goal(self, title: str, target_date: datetime) -> List[GoalSubTask]:
        """Use logic or LLM to break a goal into actionable steps"""
        # In a real implementation, this would call an LLM with the goal context
        # For now, we use a template-based mock decomposition
        
        now = datetime.utcnow()
        days_total = (target_date - now).days
        if days_total < 1: days_total = 7
        
        # Mock decomposition for common goal keywords
        if "deal" in title.lower() or "sales" in title.lower():
            return [
                GoalSubTask(title="Initial Outreach", due_date=now + timedelta(days=max(1, days_total // 4))),
                GoalSubTask(title="Proposal Drafting", due_date=now + timedelta(days=max(2, days_total // 2))),
                GoalSubTask(title="Follow-up Call", due_date=now + timedelta(days=max(3, 3 * days_total // 4))),
                GoalSubTask(title="Contract Signing", due_date=target_date)
            ]
        elif "hire" in title.lower() or "recruiting" in title.lower():
            return [
                GoalSubTask(title="Job Description Review", due_date=now + timedelta(days=2)),
                GoalSubTask(title="Sourcing Candidates", due_date=now + timedelta(days=days_total // 3)),
                GoalSubTask(title="Interview Rounds", due_date=now + timedelta(days=2 * days_total // 3)),
                GoalSubTask(title="Offer Negotiation", due_date=target_date)
            ]
        else:
            # Generic decomposition
            return [
                GoalSubTask(title="Planning Phase", due_date=now + timedelta(days=max(1, days_total // 5))),
                GoalSubTask(title="Execution Step 1", due_date=now + timedelta(days=max(2, 2 * days_total // 5))),
                GoalSubTask(title="Execution Step 2", due_date=now + timedelta(days=max(3, 3 * days_total // 5))),
                GoalSubTask(title="Final Review", due_date=target_date)
            ]

    async def update_goal_progress(self, goal_id: str):
        """Re-calculate goal progress based on sub-task status"""
        if goal_id not in self.goals:
            return
        
        goal = self.goals[goal_id]
        if not goal.sub_tasks:
            goal.progress = 0
            return
            
        completed = [st for st in goal.sub_tasks if st.status == "COMPLETED"]
        goal.progress = (len(completed) / len(goal.sub_tasks)) * 100
        
        # Update goal status based on progress and sub-task health
        now = datetime.utcnow()
        is_at_risk = any(st.due_date < now and st.status != "COMPLETED" for st in goal.sub_tasks)
        if is_at_risk:
            goal.status = "AT_RISK"
        elif goal.progress == 100:
            goal.status = "COMPLETED"
        else:
            goal.status = "ACTIVE"

    async def check_for_escalations(self) -> List[Dict[str, Any]]:
        """Identify goals that are behind and need intervention"""
        escalations = []
        now = datetime.utcnow()
        
        for goal_id, goal in self.goals.items():
            for st in goal.sub_tasks:
                if st.due_date < now and st.status != "COMPLETED" and st.status != "DELAYED":
                    # Mark as delayed and add to escalations
                    st.status = "DELAYED"
                    escalations.append({
                        "goal_id": goal_id,
                        "goal_title": goal.title,
                        "sub_task_title": st.title,
                        "due_date": st.due_date,
                        "remediation": f"Should I nudge the stakeholders for '{st.title}' or reschedule?"
                    })
        
        return escalations

# Global engine instance
goal_engine = GoalEngine()
