"""
Enhanced Orchestration Module for Phase 5

Provides advanced orchestration patterns:
- Conductor Agent for complex workflows
- Workflow State Machine with rollback
- Event-driven workflow triggering
- Enterprise workflow templates
- Workflow composition primitives

Based on 2025-2026 research:
- Hierarchical Multi-Agent Taxonomy (arXiv:2508.12683)
- AgentOrchestra Case Study (arXiv:2506.12508v4)
- Enterprise Agent Workflows (Medium.com)
"""

from core.orchestration.conductor_agent import (
    ConductorAgent,
    WorkflowExecutionContext,
    ExecutionStrategy,
    OrchestrationResult,
    get_conductor_agent,
)

from core.orchestration.workflow_state_machine import (
    WorkflowState,
    WorkflowStateMachine,
    StateTransition,
    TransitionResult,
    RollbackPlan,
    get_state_machine,
)

from core.orchestration.event_bus import (
    WorkflowEvent,
    EventSubscription,
    EventBus,
    EventType,
    get_event_bus,
)

__all__ = [
    # Conductor Agent
    "ConductorAgent",
    "WorkflowExecutionContext",
    "ExecutionStrategy",
    "OrchestrationResult",
    "get_conductor_agent",

    # State Machine
    "WorkflowState",
    "WorkflowStateMachine",
    "StateTransition",
    "TransitionResult",
    "RollbackPlan",
    "get_state_machine",

    # Event Bus
    "WorkflowEvent",
    "EventSubscription",
    "EventType",
    "get_event_bus",
]
