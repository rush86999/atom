"""Trust-bridge tests: the join between the adjudicated feedback pipeline
and the BPE harness (core/bpe/trust_bridge.py).

Covers the four join points from the design:
- corrections bypass the consult-policy value gate (protocol signal),
- role-scaled evidence thresholds (STUDENT 3×, INTERN 2×, else 1×),
- evolution apply veto while adjudicated corrections are pending,
- de-inflation of Experience entries overlapping a rejected output.
"""
from __future__ import annotations

import asyncio

import pytest

from core.bpe import trust_bridge as tb
from core.bpe.consult_policy import ConsultPolicy, MIN_EPISODES_FOR_VALUE_GATE
from core.bpe.workspace import (
    BPEWorkspace,
    get_workspace,
    iter_agent_workspaces,
    reset_registry,
)


def apply(ws: BPEWorkspace, *args):
    return asyncio.run(ws.apply(*args))


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_registry()
    tb.reset_trust()
    # Hermetic: no DB reads for org role unless a test opts in.
    monkeypatch.setattr(tb.TrustBridge, "_read_role", staticmethod(lambda aid: None))
    yield
    reset_registry()
    tb.reset_trust()


def _record(policy: ConsultPolicy, agent_id: str, n: int, success: bool = False,
            efficiency: float = 1.0) -> None:
    for _ in range(n):
        policy.record_episode(agent_id, consult_count=1, success=success,
                              step_efficiency=efficiency)


# ---------------------------------------------------------------------------
# Protocol signal — accepted corrections gate the gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProtocolSignal:
    def test_accepted_correction_raises_protocol_signal(self):
        bridge = tb.get_trust_bridge()
        assert bridge.has_protocol_signal("a") is False
        bridge.record_adjudication("a", accepted=True, is_correction=True,
                                   original_output="x", user_correction="y")
        assert bridge.has_protocol_signal("a") is True

    def test_approval_alone_is_not_protocol_signal(self):
        bridge = tb.get_trust_bridge()
        bridge.record_adjudication("a", accepted=True, is_correction=False)
        assert bridge.has_protocol_signal("a") is False

    def test_rejected_feedback_is_ignored(self):
        bridge = tb.get_trust_bridge()
        bridge.record_adjudication("a", accepted=False, is_correction=True)
        assert bridge.has_protocol_signal("a") is False
        assert bridge.pending_corrections() == 0

    def test_bypass_renders_despite_negative_ema(self, monkeypatch):
        """Value gate would suppress; an accepted correction overrides."""
        monkeypatch.delenv("ATOM_BPE_CONSULT_POLICY", raising=False)
        policy = ConsultPolicy()
        _record(policy, "a", MIN_EPISODES_FOR_VALUE_GATE + 1)  # all failures
        assert policy.value_below_threshold("a") is True
        assert policy.should_render("a", "complex", workspace_nonempty=True) is False

        tb.get_trust_bridge().record_adjudication("a", accepted=True,
                                                  is_correction=True,
                                                  original_output="x",
                                                  user_correction="y")
        assert policy.should_render("a", "complex", workspace_nonempty=True) is True


# ---------------------------------------------------------------------------
# Role-scaled evidence threshold
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoleScaledThreshold:
    def test_unknown_role_uses_base_threshold(self):
        bridge = tb.get_trust_bridge()
        assert bridge.evidence_multiplier("a") == 1.0
        policy = ConsultPolicy()
        _record(policy, "a", MIN_EPISODES_FOR_VALUE_GATE)
        assert policy.should_render("a", "complex", workspace_nonempty=True) is False

    def test_student_needs_triple_evidence(self, monkeypatch):
        monkeypatch.setattr(tb.TrustBridge, "_read_role",
                            staticmethod(lambda aid: "student"))
        bridge = tb.get_trust_bridge()
        assert bridge.evidence_multiplier("a") == 3.0
        policy = ConsultPolicy()
        _record(policy, "a", MIN_EPISODES_FOR_VALUE_GATE)  # would gate at 1×
        assert policy.should_render("a", "complex", workspace_nonempty=True) is True
        assert policy.value_below_threshold("a") is False
        _record(policy, "a", 2 * MIN_EPISODES_FOR_VALUE_GATE)  # now ≥ 15
        assert policy.should_render("a", "complex", workspace_nonempty=True) is False

    def test_intern_needs_double_evidence(self, monkeypatch):
        monkeypatch.setattr(tb.TrustBridge, "_read_role",
                            staticmethod(lambda aid: "intern"))
        assert tb.get_trust_bridge().evidence_multiplier("a") == 2.0

    @pytest.mark.parametrize("role", ["supervised", "autonomous", "paused", ""])
    def test_senior_and_exotic_roles_fail_open(self, monkeypatch, role):
        monkeypatch.setattr(tb.TrustBridge, "_read_role",
                            staticmethod(lambda aid: role))
        assert tb.get_trust_bridge().evidence_multiplier("a") == 1.0

    def test_role_read_failure_fails_open(self, monkeypatch):
        def _boom(aid):
            raise RuntimeError("db down")

        monkeypatch.setattr(tb.TrustBridge, "_read_role", staticmethod(_boom))
        assert tb.get_trust_bridge().evidence_multiplier("a") == 1.0


# ---------------------------------------------------------------------------
# Evolution veto — human signal holds the genome, operator override wins
# ---------------------------------------------------------------------------


class _VetoHarness:
    """Seed a population that would auto-apply (≥3 distinct, fit genomes)."""

    @staticmethod
    def _genome():
        return {"max_subgoals": 6, "recall_top_k": 3,
                "max_entries_per_category": 80, "max_render_chars": 2400}

    def seed(self, monkeypatch):
        from core.bpe import evolution

        monkeypatch.delenv(evolution.EVOLUTION_FLAG, raising=False)
        monkeypatch.delenv("ATOM_BPE_AUTOMATION", raising=False)
        pop = evolution.Population()
        for i, cap in enumerate((50, 60, 70, 80)):
            genome = dict(self._genome(), max_entries_per_category=cap)
            pop.report("fam", genome, fitness=3.0 + i)
        monkeypatch.setattr(evolution, "population", pop)
        return evolution


@pytest.mark.unit
class TestEvolutionVeto:
    def test_pending_corrections_hold_apply(self, monkeypatch):
        evolution = _VetoHarness().seed(monkeypatch)
        tb.get_trust_bridge().record_adjudication("a", accepted=True,
                                                  is_correction=True,
                                                  original_output="x",
                                                  user_correction="y")
        assert evolution.apply_best("fam") is None

    def test_apply_clears_the_veto_window(self, monkeypatch):
        evolution = _VetoHarness().seed(monkeypatch)
        bridge = tb.get_trust_bridge()
        bridge.record_adjudication("a", accepted=True, is_correction=True,
                                   original_output="x", user_correction="y")
        bridge.mark_applied()
        assert evolution.apply_best("fam") is not None
        assert bridge.pending_corrections() == 0

    def test_explicit_true_bypasses_veto(self, monkeypatch):
        evolution = _VetoHarness().seed(monkeypatch)
        monkeypatch.setenv(evolution.EVOLUTION_FLAG, "true")  # operator wins
        tb.get_trust_bridge().record_adjudication("a", accepted=True,
                                                  is_correction=True,
                                                  original_output="x",
                                                  user_correction="y")
        assert evolution.apply_best("fam") is not None

    def test_no_corrections_no_veto(self, monkeypatch):
        evolution = _VetoHarness().seed(monkeypatch)
        assert evolution.apply_best("fam") is not None


# ---------------------------------------------------------------------------
# De-inflation — adjudicated channel demotes misled experience
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeinflation:
    REJECTED_OUTPUT = "the agent emailed all conference attendees directly"
    CORRECTION = "only contact people who opted in"

    def _workspace_with_suspect_entry(self) -> BPEWorkspace:
        ws = get_workspace("w1", "agentA", "s1")
        ws.experience.add("priors", "emailed all conference attendees")
        ws.experience.add("skills", "reconciliation must complete before publishing")
        return ws

    @staticmethod
    def _entry_uses(ws: BPEWorkspace, content: str) -> int:
        return next(e["uses"] for cat in ws.experience.to_dict().values()
                    for e in cat if e["content"] == content)

    def test_overlapping_entry_demoted_other_untouched(self):
        ws = self._workspace_with_suspect_entry()
        ws.experience.recall("emailed all conference attendees")  # uses → 1
        ws.experience.recall("reconciliation must complete before publishing")
        assert self._entry_uses(ws, "emailed all conference attendees") == 1

        demoted = tb.deinflate_experience(ws, self.REJECTED_OUTPUT, self.CORRECTION)
        assert demoted == 1
        assert self._entry_uses(ws, "emailed all conference attendees") == 0
        assert self._entry_uses(ws, "reconciliation must complete before publishing") == 1

    def test_correction_tokens_are_not_demotion_signals(self):
        ws = get_workspace("w1", "agentA", "s1")
        ws.experience.add("skills", "only contact people who opted in")
        ws.experience.recall("only contact people who opted in")  # uses → 1
        assert tb.deinflate_experience(ws, self.REJECTED_OUTPUT,
                                       self.CORRECTION) == 0
        assert self._entry_uses(ws, "only contact people who opted in") == 1

    def test_record_adjudication_sweeps_agent_workspaces(self):
        ws = self._workspace_with_suspect_entry()
        ws.experience.recall("emailed all conference attendees")  # uses → 1
        assert len(iter_agent_workspaces("agentA")) == 1
        tb.get_trust_bridge().record_adjudication(
            "agentA", accepted=True, is_correction=True,
            original_output=self.REJECTED_OUTPUT,
            user_correction=self.CORRECTION)
        assert self._entry_uses(ws, "emailed all conference attendees") == 0
        assert ws.experience._categories["skills"]  # unrelated entry survives

    def test_empty_texts_noop(self):
        ws = self._workspace_with_suspect_entry()
        assert tb.deinflate_experience(ws, "", "") == 0
