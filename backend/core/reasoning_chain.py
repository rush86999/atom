"""
Reasoning Chain - Track and visualize AI decision-making steps
Enhanced with feedback capabilities for agent learning.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningStepType(Enum):
    """Types of reasoning steps"""
    INTENT_ANALYSIS = "intent_analysis"
    MEMORY_QUERY = "memory_query"
    AGENT_SELECTION = "agent_selection"
    AGENT_SPAWN = "agent_spawn"
    INTEGRATION_CALL = "integration_call"
    WORKFLOW_TRIGGER = "workflow_trigger"
    DECISION = "decision"
    ACTION = "action"
    CONCLUSION = "conclusion"


class FeedbackType(Enum):
    """Types of feedback on reasoning steps"""
    APPROVE = "approve"       # Step was correct
    REJECT = "reject"         # Step was wrong
    SUGGEST = "suggest"       # Alternative suggestion
    EXPLAIN = "explain"       # Request explanation


@dataclass
class ReasoningFeedback:
    """Feedback on a specific reasoning step"""
    id: str
    step_id: str
    chain_id: str
    user_id: str
    user_specialty: Optional[str]
    is_trusted: bool  # Based on specialty match or admin role
    feedback_type: FeedbackType
    comment: str
    suggested_alternative: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processed: bool = False


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain"""
    id: str
    step_type: ReasoningStepType
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    duration_ms: float
    timestamp: datetime
    parent_id: Optional[str] = None  # For branching reasoning
    metadata: Dict[str, Any] = field(default_factory=dict)
    feedback: List[ReasoningFeedback] = field(default_factory=list)
    agent_id: Optional[str] = None  # Agent that executed this step
    
    def add_feedback(self, fb: ReasoningFeedback):
        """Add feedback to this step"""
        self.feedback.append(fb)


@dataclass
class ReasoningChain:
    """Complete reasoning chain for an execution"""
    execution_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[ReasoningStep] = field(default_factory=list)
    final_outcome: Optional[str] = None
    total_duration_ms: float = 0.0
    agent_id: Optional[str] = None  # Primary agent for this chain
    
    def add_step(self, step: ReasoningStep):
        """Add a step to the chain"""
        self.steps.append(step)
    
    def get_step(self, step_id: str) -> Optional[ReasoningStep]:
        """Get a step by ID"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def to_mermaid(self) -> str:
        """Convert chain to Mermaid diagram format"""
        lines = ["graph TD"]
        
        for i, step in enumerate(self.steps):
            node_id = f"step{i}"
            # Show feedback indicator
            fb_icon = "✅" if any(f.feedback_type == FeedbackType.APPROVE for f in step.feedback) else ""
            fb_icon = "❌" if any(f.feedback_type == FeedbackType.REJECT for f in step.feedback) else fb_icon
            label = f"{step.step_type.value}\\n{step.description[:30]}...{fb_icon}"
            lines.append(f"    {node_id}[\"{label}\"]")
            
            # Connect to previous step
            if i > 0:
                prev_id = f"step{i-1}"
                lines.append(f"    {prev_id} --> {node_id}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "execution_id": self.execution_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_ms": self.total_duration_ms,
            "final_outcome": self.final_outcome,
            "agent_id": self.agent_id,
            "step_count": len(self.steps),
            "steps": [
                {
                    "id": s.id,
                    "type": s.step_type.value,
                    "description": s.description,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                    "confidence": s.confidence,
                    "duration_ms": s.duration_ms,
                    "timestamp": s.timestamp.isoformat(),
                    "agent_id": s.agent_id,
                    "feedback_count": len(s.feedback),
                    "feedback": [
                        {
                            "id": f.id,
                            "type": f.feedback_type.value,
                            "comment": f.comment,
                            "is_trusted": f.is_trusted,
                            "user_id": f.user_id
                        }
                        for f in s.feedback
                    ]
                }
                for s in self.steps
            ],
            "mermaid_diagram": self.to_mermaid()
        }


class ReasoningTracker:
    """
    Tracks reasoning steps during Atom execution.
    Thread-safe and can handle concurrent executions.
    Enhanced with feedback collection and agent learning integration.
    """
    
    def __init__(self):
        self._chains: Dict[str, ReasoningChain] = {}
        self._current_chain_id: Optional[str] = None
        self._feedback_store: List[ReasoningFeedback] = []
    
    def start_chain(self, execution_id: str = None, agent_id: str = None) -> str:
        """Start a new reasoning chain"""
        chain_id = execution_id or str(uuid.uuid4())
        self._chains[chain_id] = ReasoningChain(
            execution_id=chain_id,
            started_at=datetime.utcnow(),
            agent_id=agent_id
        )
        self._current_chain_id = chain_id
        logger.debug(f"Started reasoning chain: {chain_id}")
        return chain_id
    
    def add_step(
        self,
        step_type: ReasoningStepType,
        description: str,
        inputs: Dict[str, Any] = None,
        outputs: Dict[str, Any] = None,
        confidence: float = 1.0,
        duration_ms: float = 0.0,
        chain_id: str = None,
        metadata: Dict[str, Any] = None,
        agent_id: str = None
    ) -> ReasoningStep:
        """Add a reasoning step to the current or specified chain"""
        target_chain_id = chain_id or self._current_chain_id
        
        if not target_chain_id or target_chain_id not in self._chains:
            target_chain_id = self.start_chain(target_chain_id)
        
        step = ReasoningStep(
            id=str(uuid.uuid4()),
            step_type=step_type,
            description=description,
            inputs=inputs or {},
            outputs=outputs or {},
            confidence=confidence,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
            agent_id=agent_id
        )
        
        self._chains[target_chain_id].add_step(step)
        logger.debug(f"Added reasoning step: {step_type.value} - {description[:50]}")
        
        return step
    
    async def submit_step_feedback(
        self,
        chain_id: str,
        step_id: str,
        user_id: str,
        feedback_type: FeedbackType,
        comment: str,
        suggested_alternative: str = None
    ) -> Optional[ReasoningFeedback]:
        """
        Submit feedback on a reasoning step.
        Feedback from trusted users (matching specialty or admin) triggers agent learning.
        """
        chain = self.get_chain(chain_id)
        if not chain:
            logger.warning(f"Chain {chain_id} not found")
            return None
        
        step = chain.get_step(step_id)
        if not step:
            logger.warning(f"Step {step_id} not found in chain {chain_id}")
            return None
        
        # Check if user is trusted (specialty match or admin)
        is_trusted, user_specialty = await self._check_user_trust(user_id, step.agent_id)
        
        feedback = ReasoningFeedback(
            id=str(uuid.uuid4()),
            step_id=step_id,
            chain_id=chain_id,
            user_id=user_id,
            user_specialty=user_specialty,
            is_trusted=is_trusted,
            feedback_type=feedback_type,
            comment=comment,
            suggested_alternative=suggested_alternative
        )
        
        step.add_feedback(feedback)
        self._feedback_store.append(feedback)
        
        # Trigger agent learning if trusted feedback
        if is_trusted:
            await self._apply_feedback_to_agent(feedback, step)
        
        logger.info(f"Feedback submitted on step {step_id}: {feedback_type.value} (trusted={is_trusted})")
        return feedback
    
    async def _check_user_trust(self, user_id: str, agent_id: str = None) -> tuple:
        """Check if user is trusted to provide feedback"""
        try:
            from core.database import SessionLocal
            from core.models import User, AgentRegistry, UserRole
            
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, None
                
                # Admins are always trusted
                if user.role in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
                    return True, user.specialty
                
                # Check specialty match with agent
                if agent_id:
                    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                    if agent and user.specialty:
                        if user.specialty.lower() == agent.category.lower():
                            return True, user.specialty
                
                return False, user.specialty
                
        except Exception as e:
            logger.warning(f"Could not check user trust: {e}")
            return False, None
    
    async def _apply_feedback_to_agent(self, feedback: ReasoningFeedback, step: ReasoningStep):
        """Apply trusted feedback to agent learning via Governance Service"""
        try:
            from core.database import SessionLocal
            from core.agent_governance_service import AgentGovernanceService
            
            if not step.agent_id:
                return
            
            with SessionLocal() as db:
                governance = AgentGovernanceService(db)
                
                # Convert reasoning feedback to agent feedback
                if feedback.feedback_type == FeedbackType.APPROVE:
                    # Positive feedback increases confidence
                    governance._update_confidence_score(
                        step.agent_id, 
                        feedback.user_id, 
                        is_positive=True
                    )
                elif feedback.feedback_type == FeedbackType.REJECT:
                    # Negative feedback decreases confidence
                    governance._update_confidence_score(
                        step.agent_id,
                        feedback.user_id,
                        is_positive=False
                    )
                
                logger.info(f"Applied feedback to agent {step.agent_id} learning")
                
        except Exception as e:
            logger.error(f"Failed to apply feedback to agent: {e}")
    
    def complete_chain(
        self, 
        outcome: str = None, 
        chain_id: str = None
    ) -> Optional[ReasoningChain]:
        """Complete and finalize a reasoning chain"""
        target_chain_id = chain_id or self._current_chain_id
        
        if not target_chain_id or target_chain_id not in self._chains:
            return None
        
        chain = self._chains[target_chain_id]
        chain.completed_at = datetime.utcnow()
        chain.final_outcome = outcome
        chain.total_duration_ms = (
            (chain.completed_at - chain.started_at).total_seconds() * 1000
        )
        
        logger.info(f"Completed reasoning chain {target_chain_id}: {len(chain.steps)} steps")
        return chain
    
    def get_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """Retrieve a reasoning chain by ID"""
        return self._chains.get(chain_id)
    
    def get_all_chains(self, limit: int = 50) -> List[ReasoningChain]:
        """Get recent reasoning chains"""
        chains = list(self._chains.values())
        return sorted(chains, key=lambda c: c.started_at, reverse=True)[:limit]
    
    def get_pending_feedback(self) -> List[ReasoningFeedback]:
        """Get all unprocessed feedback"""
        return [f for f in self._feedback_store if not f.processed]


# Global tracker instance
_reasoning_tracker: Optional[ReasoningTracker] = None


def get_reasoning_tracker() -> ReasoningTracker:
    """Get the global reasoning tracker"""
    global _reasoning_tracker
    if _reasoning_tracker is None:
        _reasoning_tracker = ReasoningTracker()
    return _reasoning_tracker

