"""
Test suite for Phase 5: Enhanced Orchestration Patterns

Tests cover:
- Conductor agent pattern
- Workflow state machine with rollback
- Event bus for event-driven workflows
- Dynamic governance adjustment
- Governance policy engine
- Governance-as-a-service
- Workflow templates
- Workflow composition
- Workflow versioning
"""

import pytest
from datetime import datetime, timedelta


# ============================================================================
# Conductor Agent Tests
# ============================================================================

class TestExecutionStrategy:
    """Tests for ExecutionStrategy enum"""

    def test_strategy_import(self):
        """Test that ExecutionStrategy can be imported"""
        try:
            from core.orchestration.conductor_agent import ExecutionStrategy
            assert ExecutionStrategy is not None
        except ImportError as e:
            pytest.fail(f"ExecutionStrategy import failed: {e}")

    def test_strategy_values(self):
        """Test that ExecutionStrategy has required values"""
        from core.orchestration.conductor_agent import ExecutionStrategy

        assert hasattr(ExecutionStrategy, 'SEQUENTIAL')
        assert hasattr(ExecutionStrategy, 'PARALLEL')
        assert hasattr(ExecutionStrategy, 'HYBRID')
        assert hasattr(ExecutionStrategy, 'ADAPTIVE')
        assert hasattr(ExecutionStrategy, 'ROLLBACK_SAFE')


class TestWorkflowExecutionContext:
    """Tests for WorkflowExecutionContext"""

    def test_context_import(self):
        """Test that WorkflowExecutionContext can be imported"""
        try:
            from core.orchestration.conductor_agent import WorkflowExecutionContext
            assert WorkflowExecutionContext is not None
        except ImportError as e:
            pytest.fail(f"WorkflowExecutionContext import failed: {e}")

    def test_context_creation(self):
        """Test that WorkflowExecutionContext can be created"""
        from core.orchestration.conductor_agent import WorkflowExecutionContext

        context = WorkflowExecutionContext(
            workflow_id="wf_001",
            execution_id="exec_001",
            steps=[],
            start_step="step_1"
        )

        assert context.workflow_id == "wf_001"
        assert context.status.name == "PENDING"


class TestOrchestrationResult:
    """Tests for OrchestrationResult"""

    def test_result_import(self):
        """Test that OrchestrationResult can be imported"""
        try:
            from core.orchestration.conductor_agent import OrchestrationResult
            assert OrchestrationResult is not None
        except ImportError as e:
            pytest.fail(f"OrchestrationResult import failed: {e}")

    def test_result_creation(self):
        """Test that OrchestrationResult can be created"""
        from core.orchestration.conductor_agent import OrchestrationResult, ExecutionStatus

        result = OrchestrationResult(
            workflow_id="wf_001",
            execution_id="exec_001",
            status=ExecutionStatus.COMPLETED
        )

        assert result.workflow_id == "wf_001"
        assert result.was_successful() is True


class TestConductorAgent:
    """Tests for ConductorAgent"""

    def test_agent_import(self):
        """Test that ConductorAgent can be imported"""
        try:
            from core.orchestration.conductor_agent import ConductorAgent
            assert ConductorAgent is not None
        except ImportError as e:
            pytest.fail(f"ConductorAgent import failed: {e}")

    def test_agent_initialization(self):
        """Test that agent can be initialized"""
        from core.orchestration.conductor_agent import ConductorAgent, ConductorConfig

        config = ConductorConfig()
        agent = ConductorAgent(config)

        assert agent is not None
        assert agent.config == config

    def test_pause_workflow(self):
        """Test that workflows can be paused"""
        from core.orchestration.conductor_agent import ConductorAgent, WorkflowExecutionContext

        agent = ConductorAgent()
        context = WorkflowExecutionContext(
            workflow_id="wf_001",
            execution_id="exec_001",
            steps=[],
            start_step="step_1"
        )

        agent._active_workflows["exec_001"] = context
        result = agent.pause_workflow("exec_001")

        assert result is True

    def test_resume_workflow(self):
        """Test that workflows can be resumed"""
        from core.orchestration.conductor_agent import ConductorAgent, WorkflowExecutionContext, ExecutionStatus

        agent = ConductorAgent()
        context = WorkflowExecutionContext(
            workflow_id="wf_001",
            execution_id="exec_001",
            steps=[],
            start_step="step_1"
        )
        context.status = ExecutionStatus.PAUSED

        agent._active_workflows["exec_001"] = context
        result = agent.resume_workflow("exec_001")

        assert result is True

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.conductor_agent import get_conductor_agent

        assert callable(get_conductor_agent)


# ============================================================================
# State Machine Tests
# ============================================================================

class TestWorkflowState:
    """Tests for WorkflowState enum"""

    def test_state_import(self):
        """Test that WorkflowState can be imported"""
        try:
            from core.orchestration.workflow_state_machine import WorkflowState
            assert WorkflowState is not None
        except ImportError as e:
            pytest.fail(f"WorkflowState import failed: {e}")

    def test_state_values(self):
        """Test that WorkflowState has required values"""
        from core.orchestration.workflow_state_machine import WorkflowState

        assert hasattr(WorkflowState, 'CREATED')
        assert hasattr(WorkflowState, 'RUNNING')
        assert hasattr(WorkflowState, 'COMPLETED')
        assert hasattr(WorkflowState, 'FAILED')
        assert hasattr(WorkflowState, 'ROLLING_BACK')


class TestStateTransition:
    """Tests for StateTransition"""

    def test_transition_import(self):
        """Test that StateTransition can be imported"""
        try:
            from core.orchestration.workflow_state_machine import StateTransition
            assert StateTransition is not None
        except ImportError as e:
            pytest.fail(f"StateTransition import failed: {e}")


class TestWorkflowStateMachine:
    """Tests for WorkflowStateMachine"""

    def test_machine_import(self):
        """Test that WorkflowStateMachine can be imported"""
        try:
            from core.orchestration.workflow_state_machine import WorkflowStateMachine
            assert WorkflowStateMachine is not None
        except ImportError as e:
            pytest.fail(f"WorkflowStateMachine import failed: {e}")

    def test_machine_initialization(self):
        """Test that state machine can be initialized"""
        from core.orchestration.workflow_state_machine import WorkflowStateMachine, WorkflowState

        machine = WorkflowStateMachine()

        assert machine is not None

    def test_initialize_state(self):
        """Test that state can be initialized"""
        from core.orchestration.workflow_state_machine import WorkflowStateMachine, WorkflowState

        machine = WorkflowStateMachine()

        machine.initialize_state("wf_001", "exec_001", WorkflowState.CREATED)

        assert machine.get_state("wf_001") == WorkflowState.CREATED

    def test_state_transition(self):
        """Test that state transitions work"""
        from core.orchestration.workflow_state_machine import WorkflowStateMachine, WorkflowState

        machine = WorkflowStateMachine()

        machine.initialize_state("wf_001", "exec_001")

        # Follow the correct state path: CREATED -> VALIDATED -> QUEUED -> RUNNING
        result1 = machine.transition("wf_001", "exec_001", WorkflowState.VALIDATED)
        assert result1.value == "success" or result1.value == "SUCCESS"

        result2 = machine.transition("wf_001", "exec_001", WorkflowState.QUEUED)
        assert result2.value == "success" or result2.value == "SUCCESS"

        result3 = machine.transition("wf_001", "exec_001", WorkflowState.RUNNING)
        assert result3.value == "success" or result3.value == "SUCCESS"

    def test_create_rollback_plan(self):
        """Test that rollback plan can be created"""
        from core.orchestration.workflow_state_machine import WorkflowStateMachine, WorkflowState

        machine = WorkflowStateMachine()

        # Initialize state first
        machine.initialize_state("wf_001", "exec_001")

        plan = machine.create_rollback_plan(
            workflow_id="wf_001",
            execution_id="exec_001",
            compensation_actions=["compensate_1", "compensate_2"]
        )

        assert plan.workflow_id == "wf_001"
        assert len(plan.compensation_actions) == 2

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.workflow_state_machine import get_state_machine

        assert callable(get_state_machine)


# ============================================================================
# Event Bus Tests
# ============================================================================

class TestEventType:
    """Tests for EventType enum"""

    def test_type_import(self):
        """Test that EventType can be imported"""
        try:
            from core.orchestration.event_bus import EventType
            assert EventType is not None
        except ImportError as e:
            pytest.fail(f"EventType import failed: {e}")

    def test_type_values(self):
        """Test that EventType has required values"""
        from core.orchestration.event_bus import EventType

        assert hasattr(EventType, 'WORKFLOW_CREATED')
        assert hasattr(EventType, 'STEP_STARTED')
        assert hasattr(EventType, 'TIMER_TRIGGER')


class TestWorkflowEvent:
    """Tests for WorkflowEvent"""

    def test_event_import(self):
        """Test that WorkflowEvent can be imported"""
        try:
            from core.orchestration.event_bus import WorkflowEvent
            assert WorkflowEvent is not None
        except ImportError as e:
            pytest.fail(f"WorkflowEvent import failed: {e}")

    def test_event_creation(self):
        """Test that WorkflowEvent can be created"""
        from core.orchestration.event_bus import WorkflowEvent, EventType

        event = WorkflowEvent(
            event_id="evt_001",
            event_type=EventType.WORKFLOW_CREATED,
            source="wf_001",
            data={"key": "value"}
        )

        assert event.event_type == EventType.WORKFLOW_CREATED
        assert event.source == "wf_001"


class TestEventBus:
    """Tests for EventBus"""

    def test_bus_import(self):
        """Test that EventBus can be imported"""
        try:
            from core.orchestration.event_bus import EventBus
            assert EventBus is not None
        except ImportError as e:
            pytest.fail(f"EventBus import failed: {e}")

    def test_bus_initialization(self):
        """Test that event bus can be initialized"""
        from core.orchestration.event_bus import EventBus, EventBusConfig

        config = EventBusConfig()
        bus = EventBus(config)

        assert bus is not None
        assert bus.config == config

    def test_publish_event(self):
        """Test that events can be published"""
        from core.orchestration.event_bus import EventBus, EventType

        bus = EventBus()

        event_id = bus.publish(
            event_type=EventType.WORKFLOW_CREATED,
            source="wf_001",
            data={"created": "now"}
        )

        assert event_id
        assert len(bus._events) == 1

    def test_subscribe_event(self):
        """Test that events can be subscribed"""
        from core.orchestration.event_bus import EventBus, EventType

        bus = EventBus()

        call_count = []

        def handler(event):
            call_count.append(event)

        sub_id = bus.subscribe(
            subscriber_id="sub_001",
            event_types=[EventType.WORKFLOW_CREATED],
            handler=handler
        )

        bus.start()

        bus.publish(
            event_type=EventType.WORKFLOW_CREATED,
            source="wf_001",
            data={}
        )

        # Wait for delivery
        import time
        time.sleep(0.1)

        bus.stop()

        assert len(call_count) == 1

    def test_unsubscribe(self):
        """Test that subscriptions can be removed"""
        from core.orchestration.event_bus import EventBus, EventType

        bus = EventBus()

        sub_id = bus.subscribe(
            subscriber_id="sub_001",
            event_types=[EventType.WORKFLOW_CREATED],
            handler=lambda e: None
        )

        result = bus.unsubscribe(sub_id)

        assert result is True

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.event_bus import get_event_bus

        assert callable(get_event_bus)


# ============================================================================
# Dynamic Governance Tests
# ============================================================================

class TestGovernanceLayer:
    """Tests for GovernanceLayer enum"""

    def test_layer_import(self):
        """Test that GovernanceLayer can be imported"""
        try:
            from core.governance.dynamic_governance import GovernanceLayer
            assert GovernanceLayer is not None
        except ImportError as e:
            pytest.fail(f"GovernanceLayer import failed: {e}")

    def test_layer_values(self):
        """Test that GovernanceLayer has required values"""
        from core.governance.dynamic_governance import GovernanceLayer

        assert hasattr(GovernanceLayer, 'OPERATIONAL')
        assert hasattr(GovernanceLayer, 'TACTICAL')
        assert hasattr(GovernanceLayer, 'STRATEGIC')


class TestGovernanceDecision:
    """Tests for GovernanceDecision"""

    def test_decision_import(self):
        """Test that GovernanceDecision can be imported"""
        try:
            from core.governance.dynamic_governance import GovernanceDecision
            assert GovernanceDecision is not None
        except ImportError as e:
            pytest.fail(f"GovernanceDecision import failed: {e}")

    def test_decision_creation(self):
        """Test that GovernanceDecision can be created"""
        from core.governance.dynamic_governance import GovernanceDecision, GovernanceLayer

        decision = GovernanceDecision(
            decision_id="dec_001",
            layer=GovernanceLayer.OPERATIONAL,
            agent_id="agent_001",
            action="read"
        )

        assert decision.layer == GovernanceLayer.OPERATIONAL
        assert decision.agent_id == "agent_001"


class TestThreeLayerGovernance:
    """Tests for ThreeLayerGovernance"""

    def test_governance_import(self):
        """Test that ThreeLayerGovernance can be imported"""
        try:
            from core.governance.dynamic_governance import ThreeLayerGovernance
            assert ThreeLayerGovernance is not None
        except ImportError as e:
            pytest.fail(f"ThreeLayerGovernance import failed: {e}")

    def test_governance_initialization(self):
        """Test that governance can be initialized"""
        from core.governance.dynamic_governance import ThreeLayerGovernance

        governance = ThreeLayerGovernance()

        assert governance is not None

    def test_operational_decision(self):
        """Test that operational layer decisions work"""
        from core.governance.dynamic_governance import ThreeLayerGovernance, GovernanceLayer

        governance = ThreeLayerGovernance()

        decision = governance.decide(
            layer=GovernanceLayer.OPERATIONAL,
            agent_id="agent_001",
            action="read",
            context={"maturity": "INTERN", "complexity": 1}
        )

        assert decision.layer == GovernanceLayer.OPERATIONAL
        assert decision.outcome.value in ["allow", "deny", "escalate"]

    def test_add_policy(self):
        """Test that policies can be added"""
        from core.governance.dynamic_governance import ThreeLayerGovernance, GovernancePolicy, GovernanceLayer

        governance = ThreeLayerGovernance()

        policy = GovernancePolicy(
            policy_id="policy_001",
            layer=GovernanceLayer.TACTICAL,
            rules=[]
        )

        governance.add_policy(policy)

        assert "policy_001" in governance.policies


class TestDynamicGovernanceManager:
    """Tests for DynamicGovernanceManager"""

    def test_manager_import(self):
        """Test that DynamicGovernanceManager can be imported"""
        try:
            from core.governance.dynamic_governance import DynamicGovernanceManager
            assert DynamicGovernanceManager is not None
        except ImportError as e:
            pytest.fail(f"DynamicGovernanceManager import failed: {e}")

    def test_manager_initialization(self):
        """Test that manager can be initialized"""
        from core.governance.dynamic_governance import DynamicGovernanceManager, GovernanceConfig

        config = GovernanceConfig()
        manager = DynamicGovernanceManager(config)

        assert manager is not None
        assert manager.config == config

    def test_decide(self):
        """Test that decisions can be made"""
        from core.governance.dynamic_governance import DynamicGovernanceManager

        manager = DynamicGovernanceManager()

        decision = manager.decide(
            agent_id="agent_001",
            action="read",
            context={"maturity": "INTERN"}
        )

        assert hasattr(decision, 'outcome')

    def test_record_performance(self):
        """Test that performance can be recorded"""
        from core.governance.dynamic_governance import DynamicGovernanceManager

        manager = DynamicGovernanceManager()

        manager.record_performance("agent_001", 0.8)

        assert "agent_001" in manager._performance_history

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.governance.dynamic_governance import get_governance_manager

        assert callable(get_governance_manager)


# ============================================================================
# Policy Engine Tests
# ============================================================================

class TestPolicyOperator:
    """Tests for PolicyOperator enum"""

    def test_operator_import(self):
        """Test that PolicyOperator can be imported"""
        try:
            from core.governance.policy_engine import PolicyOperator
            assert PolicyOperator is not None
        except ImportError as e:
            pytest.fail(f"PolicyOperator import failed: {e}")

    def test_operator_values(self):
        """Test that PolicyOperator has required values"""
        from core.governance.policy_engine import PolicyOperator

        assert hasattr(PolicyOperator, 'EQUALS')
        assert hasattr(PolicyOperator, 'GREATER_THAN')
        assert hasattr(PolicyOperator, 'IN')


class TestPolicyRule:
    """Tests for PolicyRule"""

    def test_rule_import(self):
        """Test that PolicyRule can be imported"""
        try:
            from core.governance.policy_engine import PolicyRule
            assert PolicyRule is not None
        except ImportError as e:
            pytest.fail(f"PolicyRule import failed: {e}")

    def test_rule_evaluation(self):
        """Test that rules can be evaluated"""
        from core.governance.policy_engine import PolicyRule, PolicyOperator

        rule = PolicyRule(
            field="status",
            operator=PolicyOperator.EQUALS,
            value="active"
        )

        result = rule.evaluate({"status": "active"})

        assert result is True


class TestPolicyEngine:
    """Tests for PolicyEngine"""

    def test_engine_import(self):
        """Test that PolicyEngine can be imported"""
        try:
            from core.governance.policy_engine import PolicyEngine
            assert PolicyEngine is not None
        except ImportError as e:
            pytest.fail(f"PolicyEngine import failed: {e}")

    def test_engine_initialization(self):
        """Test that engine can be initialized"""
        from core.governance.policy_engine import PolicyEngine, PolicyEngineConfig

        config = PolicyEngineConfig()
        engine = PolicyEngine(config)

        assert engine is not None

    def test_register_policy(self):
        """Test that policies can be registered"""
        from core.governance.policy_engine import PolicyEngine, GovernancePolicy, PolicyPriority

        engine = PolicyEngine()

        policy = GovernancePolicy(
            policy_id="policy_001",
            name="Test Policy",
            priority=PolicyPriority.MEDIUM,
            rules=[]
        )

        engine.register_policy(policy)

        assert "policy_001" in engine._policies

    def test_evaluate(self):
        """Test that policies can be evaluated"""
        from core.governance.policy_engine import PolicyEngine, GovernancePolicy, PolicyRule, PolicyPriority, PolicyOperator

        engine = PolicyEngine()

        policy = GovernancePolicy(
            policy_id="policy_001",
            name="Test Policy",
            priority=PolicyPriority.MEDIUM,
            rules=[
                PolicyRule(
                    field="action",
                    operator=PolicyOperator.EQUALS,
                    value="read"
                )
            ],
            outcome="allow"
        )

        engine.register_policy(policy)

        result = engine.evaluate(
            agent_id="agent_001",
            action="read",
            layer="operational",
            context={"action": "read"}
        )

        assert result.policy_id == "policy_001"

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.governance.policy_engine import get_policy_engine

        assert callable(get_policy_engine)


# ============================================================================
# Governance Service Tests
# ============================================================================

class TestServiceAction:
    """Tests for ServiceAction enum"""

    def test_action_import(self):
        """Test that ServiceAction can be imported"""
        try:
            from core.governance.governance_service import ServiceAction
            assert ServiceAction is not None
        except ImportError as e:
            pytest.fail(f"ServiceAction import failed: {e}")

    def test_action_values(self):
        """Test that ServiceAction has required values"""
        from core.governance.governance_service import ServiceAction

        assert hasattr(ServiceAction, 'CHECK_PERMISSION')
        assert hasattr(ServiceAction, 'REQUEST_ESCALATION')
        assert hasattr(ServiceAction, 'SUBMIT_POLICY')


class TestGovernanceServiceRequest:
    """Tests for GovernanceServiceRequest"""

    def test_request_import(self):
        """Test that GovernanceServiceRequest can be imported"""
        try:
            from core.governance.governance_service import GovernanceServiceRequest
            assert GovernanceServiceRequest is not None
        except ImportError as e:
            pytest.fail(f"GovernanceServiceRequest import failed: {e}")

    def test_request_creation(self):
        """Test that GovernanceServiceRequest can be created"""
        from core.governance.governance_service import GovernanceServiceRequest, ServiceAction

        request = GovernanceServiceRequest(
            request_id="req_001",
            action=ServiceAction.CHECK_PERMISSION,
            agent_id="agent_001",
            resource="read"
        )

        assert request.action == ServiceAction.CHECK_PERMISSION


class TestGovernanceAsAService:
    """Tests for GovernanceAsAService"""

    def test_service_import(self):
        """Test that GovernanceAsAService can be imported"""
        try:
            from core.governance.governance_service import GovernanceAsAService
            assert GovernanceAsAService is not None
        except ImportError as e:
            pytest.fail(f"GovernanceAsAService import failed: {e}")

    def test_service_initialization(self):
        """Test that service can be initialized"""
        from core.governance.governance_service import GovernanceAsAService, GovernanceServiceConfig

        config = GovernanceServiceConfig()
        service = GovernanceAsAService(config)

        assert service is not None

    def test_check_permission(self):
        """Test that permission check works"""
        from core.governance.governance_service import GovernanceAsAService

        service = GovernanceAsAService()

        response = service.check_permission(
            tenant_id="tenant_001",
            user_id="user_001",
            agent_id="agent_001",
            action="read",
            resource="data_001"
        )

        assert hasattr(response, 'allowed')

    def test_get_status(self):
        """Test that service status can be retrieved"""
        from core.governance.governance_service import GovernanceAsAService

        service = GovernanceAsAService()

        status = service.get_status()

        assert "status" in status

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.governance.governance_service import get_governance_service

        assert callable(get_governance_service)


# ============================================================================
# Workflow Templates Tests
# ============================================================================

class TestTemplateCategory:
    """Tests for TemplateCategory enum"""

    def test_category_import(self):
        """Test that TemplateCategory can be imported"""
        try:
            from core.orchestration.workflow_templates import TemplateCategory
            assert TemplateCategory is not None
        except ImportError as e:
            pytest.fail(f"TemplateCategory import failed: {e}")

    def test_category_values(self):
        """Test that TemplateCategory has required values"""
        from core.orchestration.workflow_templates import TemplateCategory

        assert hasattr(TemplateCategory, 'AUTOMATION')
        assert hasattr(TemplateCategory, 'INTEGRATION')
        assert hasattr(TemplateCategory, 'DATA_PIPELINE')


class TestWorkflowTemplate:
    """Tests for WorkflowTemplate"""

    def test_template_import(self):
        """Test that WorkflowTemplate can be imported"""
        try:
            from core.orchestration.workflow_templates import WorkflowTemplate
            assert WorkflowTemplate is not None
        except ImportError as e:
            pytest.fail(f"WorkflowTemplate import failed: {e}")

    def test_template_creation(self):
        """Test that WorkflowTemplate can be created"""
        from core.orchestration.workflow_templates import WorkflowTemplate, TemplateCategory

        template = WorkflowTemplate(
            template_id="tpl_001",
            name="Test Template",
            category=TemplateCategory.AUTOMATION,
            parameters=[]
        )

        assert template.template_id == "tpl_001"
        assert template.category == TemplateCategory.AUTOMATION


class TestTemplateLibrary:
    """Tests for TemplateLibrary"""

    def test_library_import(self):
        """Test that TemplateLibrary can be imported"""
        try:
            from core.orchestration.workflow_templates import TemplateLibrary
            assert TemplateLibrary is not None
        except ImportError as e:
            pytest.fail(f"TemplateLibrary import failed: {e}")

    def test_library_initialization(self):
        """Test that library can be initialized"""
        from core.orchestration.workflow_templates import TemplateLibrary

        library = TemplateLibrary()

        assert library is not None
        assert len(library._templates) > 0  # Has standard templates

    def test_get_template(self):
        """Test that templates can be retrieved"""
        from core.orchestration.workflow_templates import TemplateLibrary

        library = TemplateLibrary()

        template = library.get_template("data_sync_automation")

        assert template is not None
        assert template.template_id == "data_sync_automation"

    def test_search_templates(self):
        """Test that templates can be searched"""
        from core.orchestration.workflow_templates import TemplateLibrary

        library = TemplateLibrary()

        results = library.search_templates("report")

        assert len(results) > 0
        assert any("report" in t.name.lower() for t in results)

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.workflow_templates import get_template_library

        assert callable(get_template_library)


# ============================================================================
# Workflow Composer Tests
# ============================================================================

class TestCompositionPrimitive:
    """Tests for CompositionPrimitive enum"""

    def test_primitive_import(self):
        """Test that CompositionPrimitive can be imported"""
        try:
            from core.orchestration.workflow_composer import CompositionPrimitive
            assert CompositionPrimitive is not None
        except ImportError as e:
            pytest.fail(f"CompositionPrimitive import failed: {e}")

    def test_primitive_values(self):
        """Test that CompositionPrimitive has required values"""
        from core.orchestration.workflow_composer import CompositionPrimitive

        assert hasattr(CompositionPrimitive, 'SEQUENCE')
        assert hasattr(CompositionPrimitive, 'PARALLEL')
        assert hasattr(CompositionPrimitive, 'CHOICE')
        assert hasattr(CompositionPrimitive, 'LOOP')


class TestWorkflowComposer:
    """Tests for WorkflowComposer"""

    def test_composer_import(self):
        """Test that WorkflowComposer can be imported"""
        try:
            from core.orchestration.workflow_composer import WorkflowComposer
            assert WorkflowComposer is not None
        except ImportError as e:
            pytest.fail(f"WorkflowComposer import failed: {e}")

    def test_composer_initialization(self):
        """Test that composer can be initialized"""
        from core.orchestration.workflow_composer import WorkflowComposer, ComposerConfig

        config = ComposerConfig()
        composer = WorkflowComposer(config)

        assert composer is not None

    def test_compose_workflow(self):
        """Test that workflows can be composed"""
        from core.orchestration.workflow_composer import (
            WorkflowComposer,
            CompositionPrimitive,
            CompositionStrategy
        )

        composer = WorkflowComposer()

        primitives = [
            (CompositionPrimitive.SEQUENCE, {"steps": 2}),
            (CompositionPrimitive.PARALLEL, {"branches": 2})
        ]

        workflow = composer.compose(
            primitives=primitives,
            strategy=CompositionStrategy.DEPENDENCY_AWARE,
            name="Composed Workflow"
        )

        assert workflow.workflow_id
        assert workflow.node_count > 0

    def test_decompose_workflow(self):
        """Test that workflows can be decomposed"""
        from core.orchestration.workflow_composer import (
            WorkflowComposer,
            CompositionPrimitive
        )

        composer = WorkflowComposer()

        primitives = [
            (CompositionPrimitive.SEQUENCE, {}),
            (CompositionPrimitive.PARALLEL, {})
        ]

        workflow = composer.compose(primitives=primitives, name="Test Workflow")

        decomposed = composer.decompose(workflow)

        # Composer may create intermediate nodes, so we check for at least 2
        assert len(decomposed) >= 2

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.workflow_composer import get_workflow_composer

        assert callable(get_workflow_composer)


# ============================================================================
# Workflow Versioning Tests
# ============================================================================

class TestVersionIncrement:
    """Tests for VersionIncrement enum"""

    def test_increment_import(self):
        """Test that VersionIncrement can be imported"""
        try:
            from core.orchestration.workflow_versioning import VersionIncrement
            assert VersionIncrement is not None
        except ImportError as e:
            pytest.fail(f"VersionIncrement import failed: {e}")

    def test_increment_values(self):
        """Test that VersionIncrement has required values"""
        from core.orchestration.workflow_versioning import VersionIncrement

        assert hasattr(VersionIncrement, 'MAJOR')
        assert hasattr(VersionIncrement, 'MINOR')
        assert hasattr(VersionIncrement, 'PATCH')


class TestWorkflowVersion:
    """Tests for WorkflowVersion"""

    def test_version_import(self):
        """Test that WorkflowVersion can be imported"""
        try:
            from core.orchestration.workflow_versioning import WorkflowVersion
            assert WorkflowVersion is not None
        except ImportError as e:
            pytest.fail(f"WorkflowVersion import failed: {e}")

    def test_version_creation(self):
        """Test that WorkflowVersion can be created"""
        from core.orchestration.workflow_versioning import WorkflowVersion

        version = WorkflowVersion(
            version_id="ver_001",
            workflow_id="wf_001",
            version="1.0.0"
        )

        assert version.version == "1.0.0"


class TestWorkflowVersioning:
    """Tests for WorkflowVersioning"""

    def test_versioning_import(self):
        """Test that WorkflowVersioning can be imported"""
        try:
            from core.orchestration.workflow_versioning import WorkflowVersioning
            assert WorkflowVersioning is not None
        except ImportError as e:
            pytest.fail(f"WorkflowVersioning import failed: {e}")

    def test_versioning_initialization(self):
        """Test that versioning can be initialized"""
        from core.orchestration.workflow_versioning import WorkflowVersioning, VersioningConfig

        config = VersioningConfig()
        versioning = WorkflowVersioning(config)

        assert versioning is not None

    def test_create_workflow(self):
        """Test that workflows can be created"""
        from core.orchestration.workflow_versioning import WorkflowVersioning

        versioning = WorkflowVersioning()

        workflow = versioning.create_workflow(
            workflow_id="wf_001",
            name="Test Workflow",
            description="Test description"
        )

        assert workflow.workflow_id == "wf_001"

    def test_add_version(self):
        """Test that versions can be added"""
        from core.orchestration.workflow_versioning import WorkflowVersioning

        versioning = WorkflowVersioning()

        versioning.create_workflow("wf_001", "Workflow 1", "Description")

        version = versioning.add_version(
            workflow_id="wf_001",
            version="1.1.0",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            step_schema={}
        )

        assert version.version == "1.1.0"

    def test_increment_version(self):
        """Test that versions can be incremented"""
        from core.orchestration.workflow_versioning import WorkflowVersioning, VersionIncrement

        versioning = WorkflowVersioning()

        versioning.create_workflow("wf_001", "Workflow 1", "Description")

        new_version = versioning.increment_version("wf_001", VersionIncrement.MINOR)

        assert new_version == "1.1.0"

    def test_create_migration_plan(self):
        """Test that migration plans can be created"""
        from core.orchestration.workflow_versioning import WorkflowVersioning

        versioning = WorkflowVersioning()

        versioning.create_workflow("wf_001", "Workflow 1", "Description")
        # Don't add 1.0.0 again since create_workflow already does it
        versioning.add_version("wf_001", "2.0.0", {}, {}, {})

        plan = versioning.create_migration_plan(
            workflow_id="wf_001",
            from_version="1.0.0",
            to_version="2.0.0"
        )

        assert plan.from_version == "1.0.0"
        assert plan.to_version == "2.0.0"

    def test_check_compatibility(self):
        """Test that compatibility can be checked"""
        from core.orchestration.workflow_versioning import WorkflowVersioning

        versioning = WorkflowVersioning()

        versioning.create_workflow("wf_001", "Workflow 1", "Description")
        # Don't add 1.0.0 again since create_workflow already does it
        versioning.add_version("wf_001", "2.0.0", {}, {}, {})

        result = versioning.check_compatibility("wf_001", "1.0.0", "2.0.0")

        assert result.value in ["compatible", "incompatible", "unknown"]

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.orchestration.workflow_versioning import get_workflow_versioning

        assert callable(get_workflow_versioning)


# ============================================================================
# Integration Tests
# ============================================================================

class TestOrchestrationIntegration:
    """Tests for orchestration module integration"""

    def test_orchestration_module_import(self):
        """Test that orchestration module can be imported"""
        try:
            import core.orchestration
            assert core.orchestration is not None
        except ImportError as e:
            pytest.fail(f"orchestration module import failed: {e}")

    def test_governance_module_import(self):
        """Test that governance module can be imported"""
        try:
            import core.governance
            assert core.governance is not None
        except ImportError as e:
            pytest.fail(f"governance module import failed: {e}")

    def test_module_exports(self):
        """Test that modules export required components"""
        from core.orchestration import (
            ConductorAgent,
            WorkflowStateMachine,
            get_conductor_agent,
            get_state_machine,
        )

        from core.governance import (
            ThreeLayerGovernance,
            DynamicGovernanceManager,
            get_governance_manager,
        )

        assert ConductorAgent is not None
        assert WorkflowStateMachine is not None
        assert ThreeLayerGovernance is not None
        assert callable(get_conductor_agent)
        assert callable(get_state_machine)
        assert callable(get_governance_manager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
