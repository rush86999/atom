"""
Integration tests for the Phase 2/4/5 wiring — verifying that previously-dead
modules are now reachable from the live app.

Each test exercises the minimal integration path: a route resolves, a method
delegates to the right module, an event publishes.
"""

from __future__ import annotations

import pytest


# ===========================================================================
# Unit 0a: docx import fix in office_sync_service
# ===========================================================================

class TestDocxImportFix:
    """The Word-doc canvas→file sync was crashing (missing `import docx`)."""

    def test_docx_is_imported(self):
        """office_sync_service can import docx without NameError."""
        import sys
        sys.path.insert(0, ".")
        from core import office_sync_service
        assert hasattr(office_sync_service, "docx"), "docx module should be imported"


# ===========================================================================
# Unit 0b: memory consolidation wiring
# ===========================================================================

class TestMemoryConsolidationWiring:
    """The factory should return the POMDP-backed service, not the legacy one."""

    def test_pomdp_consolidation_module_exists(self):
        """The POMDP-backed MemoryConsolidationService is importable."""
        from core.memory.memory_consolidation_service import MemoryConsolidationService
        assert MemoryConsolidationService is not None

    def test_pomdp_module_has_run_cycle(self):
        """The POMDP service has run_consolidation_cycle (the method the startup hook calls)."""
        from core.memory.memory_consolidation_service import MemoryConsolidationService
        assert hasattr(MemoryConsolidationService, "run_consolidation_cycle"), (
            "POMDP consolidation must have run_consolidation_cycle for the startup hook"
        )


# ===========================================================================
# Unit 1: GraphRAG enhancement wiring
# ===========================================================================

class TestGraphRAGEnhancementWiring:
    """Phase 2 enhancements are now wired into the production engine."""

    def test_build_communities_method_exists(self):
        """GraphRAGEngine has build_communities (delegates to CommunityDetectionService)."""
        from core.graphrag_engine import GraphRAGEngine
        assert hasattr(GraphRAGEngine, "build_communities"), (
            "GraphRAGEngine must have build_communities — the route calls it"
        )

    def test_multi_hop_expander_importable(self):
        """SQLMultiHopExpander is importable (used inside local_search)."""
        from core.graphrag.multi_hop_expansion import SQLMultiHopExpander, get_sql_expander
        expander = get_sql_expander()
        assert expander is not None

    def test_community_detector_importable(self):
        """CommunityDetectionService is importable (used by build_communities)."""
        from core.graphrag.community_detection import get_community_detector
        detector = get_community_detector()
        assert detector is not None


# ===========================================================================
# Unit 2: Federation API surface
# ===========================================================================

class TestFederationRoutes:
    """Phase 4 federation routes exist and are registered."""

    def test_federation_routes_importable(self):
        """api.routes.federation_routes resolves (the broken import in main_api_app.py)."""
        from api.routes.federation_routes import router
        assert router is not None
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        assert "/federation/dids" in paths
        assert "/federation/credentials" in paths
        assert "/federation/verify" in paths
        assert "/federation/security/health" in paths

    def test_did_manager_factory_works(self):
        """get_did_manager returns a singleton."""
        from core.identity.did_manager import get_did_manager
        m1 = get_did_manager()
        m2 = get_did_manager()
        assert m1 is m2

    def test_vc_manager_factory_works(self):
        """get_vc_manager returns a singleton."""
        from core.identity.verifiable_credentials import get_vc_manager
        m1 = get_vc_manager()
        m2 = get_vc_manager()
        assert m1 is m2

    def test_zero_trust_manager_factory_works(self):
        """get_zero_trust_manager returns a singleton."""
        from core.federation.zero_trust_security import get_zero_trust_manager
        m1 = get_zero_trust_manager()
        m2 = get_zero_trust_manager()
        assert m1 is m2


# ===========================================================================
# Unit 3: Orchestration wiring
# ===========================================================================

class TestOrchestrationWiring:
    """Phase 5 orchestration is wired into the live workflow engine."""

    def test_event_publish_helper_exists(self):
        """WorkflowEngine has _publish_orchestration_event for EventBus lifecycle events."""
        from core.workflow_engine import WorkflowEngine
        assert hasattr(WorkflowEngine, "_publish_orchestration_event"), (
            "WorkflowEngine must have _publish_orchestration_event to publish Phase-5 EventBus events"
        )

    def test_event_bus_factory_works(self):
        """get_event_bus returns a started EventBus singleton."""
        from core.orchestration.event_bus import get_event_bus
        bus = get_event_bus()
        assert bus is not None

    def test_conductor_agent_factory_works(self):
        """get_conductor_agent returns a ConductorAgent."""
        from core.orchestration.conductor_agent import get_conductor_agent
        conductor = get_conductor_agent()
        assert conductor is not None

    def test_conductor_has_5_strategies(self):
        """ExecutionStrategy has exactly the 5 marketed strategies."""
        from core.orchestration.conductor_agent import ExecutionStrategy
        strategies = {s.value for s in ExecutionStrategy}
        assert strategies == {"sequential", "parallel", "hybrid", "adaptive", "rollback_safe"}

    def test_composer_has_9_primitives(self):
        """CompositionPrimitive has 9 primitives (was miscounted as 8 in docs)."""
        from core.orchestration.workflow_composer import CompositionPrimitive
        primitives = list(CompositionPrimitive)
        assert len(primitives) == 9, f"Expected 9 primitives, got {len(primitives)}"

    def test_workflow_endpoints_has_conductor_route(self):
        """The conductor endpoint is registered on the workflow router."""
        from core.workflow_endpoints import router
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        assert "/workflows/conductor/execute" in paths, (
            "Conductor endpoint must be registered for the marketed 5 strategies to be reachable"
        )
