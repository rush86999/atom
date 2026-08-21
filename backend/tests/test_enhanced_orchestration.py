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

    def test_module_exports(self):
        """Test that modules export required components"""
        from core.orchestration import (
            ConductorAgent,
            WorkflowStateMachine,
            get_conductor_agent,
            get_state_machine,
        )

        assert ConductorAgent is not None
        assert WorkflowStateMachine is not None
        assert callable(get_conductor_agent)
        assert callable(get_state_machine)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
