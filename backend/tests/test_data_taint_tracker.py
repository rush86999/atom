"""
P4 — Observation-Based Data Taint tests (G4).

Track sensitive data an agent observed during a run and block/escalate risky
outbound actions. Emits the previously-reserved ``VT_PROVENANCE`` violation
type for the first time. Stamps sensitivity into the correct JSON columns:
- AgentExecution.metadata_json (exists)
- CanvasAudit.details_json (NOT metadata_json — correction)
- HITLAction.context_snapshot (NOT metadata_json — correction)
"""
import pytest
from unittest.mock import MagicMock


# ============================================================================
# Sensitivity classifier
# ============================================================================

class TestSensitivityClassifier:
    def test_classify_explicit_labels(self):
        from core.data_taint_tracker import classify_sensitivity
        assert classify_sensitivity("public info") == "public"
        assert classify_sensitivity("internal memo") == "internal"
        assert classify_sensitivity("confidential strategy") == "confidential"
        assert classify_sensitivity("restricted payroll") == "restricted"

    def test_classify_pii_credit_card(self):
        from core.data_taint_tracker import classify_sensitivity
        # Credit-card-shaped number -> restricted (PII / financial).
        text = "card 4111-1111-1111-1111 expires 12/25"
        assert classify_sensitivity(text) == "restricted"

    def test_classify_pii_ssn(self):
        from core.data_taint_tracker import classify_sensitivity
        text = "ssn 123-45-6789 on file"
        assert classify_sensitivity(text) == "restricted"

    def test_classify_pii_api_key(self):
        from core.data_taint_tracker import classify_sensitivity
        text = "sk-live-abcdef1234567890abcdef1234567890"
        assert classify_sensitivity(text) == "restricted"

    def test_classify_defaults_to_internal(self):
        from core.data_taint_tracker import classify_sensitivity
        assert classify_sensitivity("just some text") == "internal"

    def test_sensitivity_ranking(self):
        """higher_sensitivity picks the more-sensitive of two labels."""
        from core.data_taint_tracker import higher_sensitivity
        assert higher_sensitivity("public", "internal") == "internal"
        assert higher_sensitivity("confidential", "restricted") == "restricted"
        assert higher_sensitivity("public", "restricted") == "restricted"


# ============================================================================
# Taint tracker — observed set accumulation
# ============================================================================

class TestTaintTracker:
    def test_observe_accumulates_labels(self):
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="run-1")
        tracker.observe("public doc", source="doc-a")
        tracker.observe("restricted payroll data", source="doc-b")
        assert "public" in tracker.observed_labels
        assert "restricted" in tracker.observed_labels

    def test_observe_classifies_implicit_pii(self):
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="run-1")
        tracker.observe("call me about 4111-1111-1111-1111", source="note")
        assert "restricted" in tracker.observed_labels

    def test_outbound_blocked_when_restricted_observed(self):
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="run-1")
        tracker.observe("restricted data here", source="d1")
        # Restricted observed + external destination -> blocked.
        decision = tracker.check_outbound(destination="external", service="slack")
        assert decision["allowed"] is False
        assert "restricted" in decision.get("reason", "").lower() or "sensitive" in decision.get("reason", "").lower()

    def test_outbound_allowed_when_no_restricted(self):
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="run-1")
        tracker.observe("public info", source="d1")
        decision = tracker.check_outbound(destination="external", service="slack")
        assert decision["allowed"] is True

    def test_outbound_allowed_for_internal_destination(self):
        """Even with restricted observed, an internal destination is allowed."""
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="run-1")
        tracker.observe("restricted data", source="d1")
        decision = tracker.check_outbound(destination="internal", service="canvas")
        assert decision["allowed"] is True


# ============================================================================
# VT_PROVENANCE emission
# ============================================================================

class TestProvenanceEmission:
    def test_vt_provenance_emitted_on_blocked_outbound(self):
        """The first real emission of VT_PROVENANCE must fire when restricted
        data is observed and an outbound action is blocked."""
        from core.data_taint_tracker import DataTaintTracker
        from core.sandbox_policy import VT_PROVENANCE
        tracker = DataTaintTracker(run_id="run-emit")
        tracker.observe("restricted data", source="d1")
        decision = tracker.check_outbound(destination="external", service="slack")
        assert decision["allowed"] is False
        assert decision.get("violation_type") == VT_PROVENANCE

    def test_vt_provenance_constant_is_provenance(self):
        from core.sandbox_policy import VT_PROVENANCE
        assert VT_PROVENANCE == "provenance"


# ============================================================================
# Gatekeeper <-> taint tracker integration (P3 + P4)
# ============================================================================

class TestGatekeeperTaintIntegration:
    @pytest.mark.asyncio
    async def test_gatekeeper_blocks_when_taint_tracker_says_no(self):
        """When a taint_tracker with restricted data is passed, the gatekeeper
        blocks the external outbound call (VT_PROVENANCE)."""
        from middleware.governance_middleware import governance_middleware
        from core.data_taint_tracker import DataTaintTracker
        tracker = DataTaintTracker(run_id="r1")
        tracker.observe("restricted data", source="d1")
        result = await governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1", taint_tracker=tracker,
        )
        assert result["allowed"] is False
        assert result.get("violation_type") == "provenance"

    @pytest.mark.asyncio
    async def test_gatekeeper_allows_without_taint_tracker(self):
        """Omitting taint_tracker preserves existing (P3) behavior."""
        from middleware.governance_middleware import governance_middleware
        result = await governance_middleware.check_action_risk(
            "slack", action="post_message", params={},
            agent_id="a1", workspace_id="ws1",
        )
        assert result["allowed"] is True
