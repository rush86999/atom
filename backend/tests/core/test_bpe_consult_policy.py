"""BPE Phase 2+3 tests: consult policy, consolidation, episode wiring.

Consult policy (docs/architecture/BPE_WORKSPACE_PLAN.md Phase 2): complexity
gate, value EMA gate, recall-only annealing mode. Consolidation (Phase 3
v1): deterministic note → Experience promotion on success only, nightly
sweep, memory_consolidator wire-in.
"""
from __future__ import annotations

import asyncio

import pytest

from core.bpe.consult_policy import (
    MIN_EPISODES_FOR_VALUE_GATE,
    RECALL_ONLY_MIN_EPISODES,
    ConsultPolicy,
    policy_gating_enabled,
)
from core.bpe.workspace import BPEWorkspace, get_workspace, reset_registry


def apply(ws: BPEWorkspace, *args):
    return asyncio.run(ws.apply(*args))


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Consult policy — gating (Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConsultPolicyGating:
    def test_empty_workspace_never_renders(self):
        policy = ConsultPolicy()
        assert policy.should_render("a", "complex", workspace_nonempty=False) is False

    def test_simple_complexity_suppressed(self):
        policy = ConsultPolicy()
        assert policy.should_render("a", "simple", workspace_nonempty=True) is False

    def test_auto_mode_gating_active_but_healthy_renders(self, monkeypatch):
        """Default (env unset) is AUTO: the value-gate is active but
        self-regulating — a healthy agent (no negative evidence) renders."""
        monkeypatch.delenv("ATOM_BPE_CONSULT_POLICY", raising=False)
        policy = ConsultPolicy()
        assert policy_gating_enabled() is True  # auto mode
        assert policy.should_render("a", "moderate", workspace_nonempty=True) is True

    def test_kill_switch_false_disables_gating(self, monkeypatch):
        """Kill-switch: false = shadow recording only; rendering is never
        suppressed even for a badly-failing agent."""
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "false")
        policy = ConsultPolicy()
        assert policy_gating_enabled() is False
        for _ in range(MIN_EPISODES_FOR_VALUE_GATE + 2):
            policy.record_episode("a", consult_count=2, success=False, step_efficiency=2.0)
        assert policy.should_render("a", "moderate", workspace_nonempty=True) is True

    def test_default_off_allows_until_evidence(self, monkeypatch):
        """Value gate needs MIN_EPISODES before it may suppress."""
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "true")
        policy = ConsultPolicy()
        for _ in range(MIN_EPISODES_FOR_VALUE_GATE - 1):
            policy.record_episode("a", consult_count=2, success=False, step_efficiency=2.0)
        assert policy.should_render("a", "moderate", workspace_nonempty=True) is True

    def test_failing_agent_suppressed_after_evidence(self, monkeypatch):
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "true")
        policy = ConsultPolicy()
        for _ in range(MIN_EPISODES_FOR_VALUE_GATE + 2):
            policy.record_episode("a", consult_count=2, success=False, step_efficiency=2.0)
        assert policy.value_below_threshold("a") is True
        assert policy.should_render("a", "moderate", workspace_nonempty=True) is False

    def test_succeeding_agent_keeps_rendering(self, monkeypatch):
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "true")
        policy = ConsultPolicy()
        for _ in range(MIN_EPISODES_FOR_VALUE_GATE + 2):
            policy.record_episode("a", consult_count=1, success=True, step_efficiency=1.0)
        assert policy.should_render("a", "moderate", workspace_nonempty=True) is True


# ---------------------------------------------------------------------------
# Consult policy — annealing (commit/note decay, recall persists)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnnealing:
    def test_full_mode_early(self):
        policy = ConsultPolicy()
        assert policy.render_mode("a") == "full"

    def test_recall_only_when_commit_note_share_collapses(self):
        policy = ConsultPolicy()
        # Enough episodes; consults dominated by track/recall (no mix recorded).
        for _ in range(RECALL_ONLY_MIN_EPISODES + 2):
            policy.record_episode("a", consult_count=1, success=True, step_efficiency=1.0)
        assert policy.render_mode("a") == "recall_only"

    def test_full_mode_while_commit_note_active(self):
        policy = ConsultPolicy()
        for _ in range(RECALL_ONLY_MIN_EPISODES + 2):
            policy.record_episode("a", consult_count=2, success=True, step_efficiency=1.0)
            policy.record_consult_mix("a", 1)  # 50% commit/note share
        assert policy.render_mode("a") == "full"

    def test_harness_call_rate_metric(self):
        policy = ConsultPolicy()
        for _ in range(4):
            policy.record_episode("a", consult_count=2, success=True, step_efficiency=1.0)
        assert policy.harness_call_rate("a") == 2.0
        assert policy.harness_call_rate("unknown") == 0.0

    def test_snapshot_shape(self):
        policy = ConsultPolicy()
        policy.record_episode("a", consult_count=1, success=True, step_efficiency=1.0)
        snap = policy.snapshot()["a"]
        assert snap["episodes"] == 1
        assert snap["consults_total"] == 1
        assert "value_ema" in snap


# ---------------------------------------------------------------------------
# Workspace episode counters
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEpisodeCounters:
    def test_counters_increment_on_successful_consults(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "goal")
        apply(ws, "note", "insight")
        apply(ws, "note", "")  # failed — must not count
        assert ws.episode_consults == 2
        assert ws.episode_commit_notes == 2

    def test_reset(self):
        ws = BPEWorkspace()
        apply(ws, "note", "x")
        ws.reset_episode_counters()
        assert ws.episode_consults == 0
        assert ws.episode_commit_notes == 0


# ---------------------------------------------------------------------------
# Recall-only render mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderMode:
    def test_recall_only_header(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "goal")
        block = ws.render(mode="recall_only")
        assert "commit/note only if essential" in block
        assert "[pending] goal" in block

    def test_full_header_default(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "goal")
        assert "track/commit/recall/note meta-actions available" in ws.render()


# ---------------------------------------------------------------------------
# Consolidation (Phase 3 v1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConsolidation:
    def test_note_classification(self):
        from core.bpe.consolidation import classify_note

        assert classify_note("Never trust cached auth tokens") == "mistakes"
        assert classify_note("invoices live in /finance/2026") == "priors"
        assert classify_note("always verify totals before export") == "skills"

    def test_success_promotes_notes(self):
        from core.bpe.consolidation import consolidate_workspace_notes

        ws = BPEWorkspace()
        apply(ws, "note", "avoid editing production rows")
        apply(ws, "note", "verify totals first")
        report = consolidate_workspace_notes(ws)
        assert report["mistakes"] == 1
        assert report["skills"] == 1
        assert ws._pending_notes == []
        assert ws.experience.recall("production rows")

    def test_failure_drops_notes(self):
        from core.bpe.consolidation import consolidate_workspace_notes

        ws = BPEWorkspace()
        apply(ws, "note", "verify totals first")
        ws.drain_pending_notes()  # failure path drops via plain drain
        assert ws.experience.recall("verify totals") == []

    def test_nightly_sweep_covers_all_workspaces(self):
        from core.bpe.consolidation import sweep_pending_notes

        ws_a = get_workspace("w", "a", "s1")
        ws_b = get_workspace("w", "b", "s2")
        apply(ws_a, "note", "never deploy on friday")
        apply(ws_b, "note", "reports live in the drive folder")
        report = sweep_pending_notes(dict(_workspaces()))
        assert report["mistakes"] == 1
        assert report["priors"] == 1
        assert ws_a._pending_notes == []
        assert ws_b._pending_notes == []

    def test_memory_consolidator_wire_in(self, monkeypatch):
        from core.memory_consolidator import consolidate_workspace

        ws = get_workspace("w", "agent", "sess")
        apply(ws, "note", "avoid double-charging invoices")
        report = consolidate_workspace("default")
        assert report["bpe_notes_consolidated"]["mistakes"] == 1
        assert ws.experience.recall("double-charging")


def _workspaces():
    from core.bpe import workspace as ws_mod

    return ws_mod._workspaces
