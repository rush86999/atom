"""
Event-Sourced AI Architecture - Scalability Foundation
Separates: Perception (LLM) → Planning (State Machine) → Execution (Idempotent Workers)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

# ==================== EVENT SOURCING ====================

class EventType(Enum):
    # Perception Events (LLM decisions)
    PERCEPTION_STARTED = "perception.started"
    PERCEPTION_COMPLETED = "perception.completed"
    PERCEPTION_FAILED = "perception.failed"
    
    # Planning Events (State Machine)
    PLAN_CREATED = "plan.created"
    PLAN_STEP_ADDED = "plan.step_added"
    PLAN_APPROVED = "plan.approved"
    PLAN_REJECTED = "plan.rejected"
    
    # Execution Events (Idempotent Workers)
    EXECUTION_STARTED = "execution.started"
    EXECUTION_STEP_COMPLETED = "execution.step_completed"
    EXECUTION_STEP_FAILED = "execution.step_failed"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_ROLLED_BACK = "execution.rolled_back"

@dataclass
class Event:
    """Immutable event record"""
    event_id: str
    event_type: EventType
    aggregate_id: str  # e.g., workflow_id, transaction_id
    timestamp: datetime
    data: Dict[str, Any]
    ai_confidence: Optional[float] = None
    ai_reasoning: Optional[str] = None
    actor: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "aggregate_id": self.aggregate_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "ai_confidence": self.ai_confidence,
            "ai_reasoning": self.ai_reasoning,
            "actor": self.actor
        }

class EventStore:
    """Append-only event store"""
    
    def __init__(self):
        self._events: List[Event] = []
        self._subscribers: List[Callable[[Event], None]] = []
    
    def append(self, event: Event):
        """Append event to store (immutable)"""
        self._events.append(event)
        logger.info(f"Event: {event.event_type.value} | {event.aggregate_id} | conf={event.ai_confidence}")
        
        # Notify subscribers
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
    
    def get_events(self, aggregate_id: str) -> List[Event]:
        """Get all events for an aggregate"""
        return [e for e in self._events if e.aggregate_id == aggregate_id]
    
    def get_all(self) -> List[Event]:
        return self._events.copy()
    
    def subscribe(self, callback: Callable[[Event], None]):
        self._subscribers.append(callback)

# ==================== PERCEPTION LAYER (LLM) ====================

@dataclass
class PerceptionResult:
    """Result from LLM perception"""
    intent: str
    entities: Dict[str, Any]
    confidence: float
    reasoning: str
    suggested_actions: List[str]

class PerceptionLayer:
    """LLM-based perception - analyzes and understands inputs"""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    async def perceive(self, aggregate_id: str, input_data: Dict[str, Any]) -> PerceptionResult:
        """Perceive and understand input using LLM"""
        
        # Log start
        self.event_store.append(Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PERCEPTION_STARTED,
            aggregate_id=aggregate_id,
            timestamp=datetime.now(),
            data={"input": input_data}
        ))
        
        try:
            # Simulate LLM analysis (in production, call actual LLM)
            result = await self._analyze_with_llm(input_data)
            
            # Log completion with confidence
            self.event_store.append(Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.PERCEPTION_COMPLETED,
                aggregate_id=aggregate_id,
                timestamp=datetime.now(),
                data={"result": result.__dict__},
                ai_confidence=result.confidence,
                ai_reasoning=result.reasoning
            ))
            
            return result
            
        except Exception as e:
            self.event_store.append(Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.PERCEPTION_FAILED,
                aggregate_id=aggregate_id,
                timestamp=datetime.now(),
                data={"error": str(e)}
            ))
            raise
    
    async def _analyze_with_llm(self, input_data: Dict[str, Any]) -> PerceptionResult:
        """Placeholder for LLM analysis"""
        # In production, this calls the AI service
        return PerceptionResult(
            intent="process_transaction",
            entities=input_data,
            confidence=0.85,
            reasoning="Analyzed input structure and content",
            suggested_actions=["categorize", "post"]
        )

# ==================== PLANNING LAYER (State Machine) ====================

class PlanStatus(Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class PlanStep:
    """Single step in a plan"""
    step_id: str
    action: str
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    idempotency_key: Optional[str] = None

@dataclass
class ExecutionPlan:
    """State machine for execution planning"""
    plan_id: str
    aggregate_id: str
    status: PlanStatus
    steps: List[PlanStep]
    created_at: datetime
    approved_by: Optional[str] = None

class PlanningLayer:
    """Graph/state machine - creates and manages execution plans"""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self._plans: Dict[str, ExecutionPlan] = {}
    
    def create_plan(self, aggregate_id: str, perception: PerceptionResult) -> ExecutionPlan:
        """Create execution plan from perception result"""
        
        plan_id = str(uuid.uuid4())
        steps = []
        
        for i, action in enumerate(perception.suggested_actions):
            steps.append(PlanStep(
                step_id=f"step_{i}",
                action=action,
                parameters={},
                idempotency_key=f"{plan_id}_{action}_{i}"
            ))
        
        plan = ExecutionPlan(
            plan_id=plan_id,
            aggregate_id=aggregate_id,
            status=PlanStatus.PENDING_APPROVAL if perception.confidence < 0.85 else PlanStatus.APPROVED,
            steps=steps,
            created_at=datetime.now()
        )
        
        self._plans[plan_id] = plan
        
        self.event_store.append(Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PLAN_CREATED,
            aggregate_id=aggregate_id,
            timestamp=datetime.now(),
            data={"plan_id": plan_id, "steps": [s.action for s in steps], "status": plan.status.value},
            ai_confidence=perception.confidence
        ))
        
        return plan
    
    def approve_plan(self, plan_id: str, approver: str) -> ExecutionPlan:
        """Approve a pending plan"""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        plan.status = PlanStatus.APPROVED
        plan.approved_by = approver
        
        self.event_store.append(Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PLAN_APPROVED,
            aggregate_id=plan.aggregate_id,
            timestamp=datetime.now(),
            data={"plan_id": plan_id},
            actor=approver
        ))
        
        return plan
    
    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        return self._plans.get(plan_id)

# ==================== EXECUTION LAYER (Idempotent Workers) ====================

class ExecutionLayer:
    """Idempotent workers - executes plans safely"""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self._executed_keys: set = set()  # Idempotency tracking
    
    async def execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute an approved plan idempotently"""
        
        if plan.status != PlanStatus.APPROVED:
            raise ValueError(f"Plan {plan.plan_id} not approved")
        
        plan.status = PlanStatus.EXECUTING
        
        self.event_store.append(Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.EXECUTION_STARTED,
            aggregate_id=plan.aggregate_id,
            timestamp=datetime.now(),
            data={"plan_id": plan.plan_id}
        ))
        
        results = {}
        
        for step in plan.steps:
            try:
                result = await self._execute_step_idempotent(plan, step)
                results[step.step_id] = result
                
                self.event_store.append(Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.EXECUTION_STEP_COMPLETED,
                    aggregate_id=plan.aggregate_id,
                    timestamp=datetime.now(),
                    data={"step_id": step.step_id, "result": result}
                ))
                
            except Exception as e:
                self.event_store.append(Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.EXECUTION_STEP_FAILED,
                    aggregate_id=plan.aggregate_id,
                    timestamp=datetime.now(),
                    data={"step_id": step.step_id, "error": str(e)}
                ))
                plan.status = PlanStatus.FAILED
                raise
        
        plan.status = PlanStatus.COMPLETED
        
        self.event_store.append(Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.EXECUTION_COMPLETED,
            aggregate_id=plan.aggregate_id,
            timestamp=datetime.now(),
            data={"plan_id": plan.plan_id, "results": results}
        ))
        
        return results
    
    async def _execute_step_idempotent(self, plan: ExecutionPlan, step: PlanStep) -> Dict[str, Any]:
        """Execute step with idempotency guarantee"""
        
        key = step.idempotency_key or f"{plan.plan_id}_{step.step_id}"
        
        if key in self._executed_keys:
            logger.info(f"Step {step.step_id} already executed (idempotent skip)")
            return {"status": "skipped", "reason": "already_executed"}
        
        # Execute (in production, this calls the actual action)
        await asyncio.sleep(0.01)  # Simulate work
        
        self._executed_keys.add(key)
        return {"status": "completed", "action": step.action}

# ==================== ORCHESTRATOR ====================

class EventSourcedOrchestrator:
    """
    Main orchestrator combining Perception → Planning → Execution
    with full event sourcing and AI decision logging.
    """
    
    def __init__(self):
        self.event_store = EventStore()
        self.perception = PerceptionLayer(self.event_store)
        self.planning = PlanningLayer(self.event_store)
        self.execution = ExecutionLayer(self.event_store)
    
    async def process(self, aggregate_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input through the full pipeline"""
        
        # 1. Perception (LLM)
        perception_result = await self.perception.perceive(aggregate_id, input_data)
        
        # 2. Planning (State Machine)
        plan = self.planning.create_plan(aggregate_id, perception_result)
        
        # 3. Execution (if auto-approved)
        if plan.status == PlanStatus.APPROVED:
            results = await self.execution.execute_plan(plan)
            return {"status": "completed", "results": results}
        else:
            return {"status": "pending_approval", "plan_id": plan.plan_id}
    
    def get_event_log(self, aggregate_id: str = None) -> List[Dict[str, Any]]:
        """Get event log for debugging/audit"""
        if aggregate_id:
            return [e.to_dict() for e in self.event_store.get_events(aggregate_id)]
        return [e.to_dict() for e in self.event_store.get_all()]

# Global instance
event_sourced_orchestrator = EventSourcedOrchestrator()
