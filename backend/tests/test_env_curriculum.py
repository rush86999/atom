"""Tests for core/env_curriculum: fail-closed sandbox + rollout/admission math.

Covers the rev 2 plan's blocking prerequisites (ENV_HARNESS_ADOPTION_PLAN
§Phase 1a, §Phase 5 protocol):
- the mutation sandbox REFUSES to execute when Docker is absent — no host
  subprocess fallback, and a non-container result is refused (defence in
  depth against a future parent refactor reintroducing the fallback);
- Wilson intervals at known boundary values;
- two-stage band admission: impossible/trivial rejections, band overlap,
  harness errors never reaching the decision;
- the declarative mutation shapes validate against a bridge-provided schema.
"""

import asyncio
import pytest

from core.env_curriculum.mutations import (
    MutationStack,
    RuleSpec,
    RulesMutation,
    SetupMutation,
)
from core.env_curriculum.outcomes import (
    BandSpec,
    RolloutOutcome,
    RolloutStatus,
    admit_mutation,
    pass_rate,
    wilson_interval,
)
from core.env_curriculum.sandbox import (
    FailClosedMutationSandbox,
    MutationSandboxUnavailable,
    execute_mutation,
)
import core.env_curriculum.sandbox as sandbox_mod
from core.auto_dev.container_sandbox import ContainerSandbox


# ---------------------------------------------------------------------------
# Fail-closed sandbox (Phase 1a)
# ---------------------------------------------------------------------------

def _outcome(status: str, environment: str) -> dict:
    return {"status": status, "output": "ok", "execution_seconds": 0.01,
            "environment": environment}


def test_sandbox_refuses_when_docker_unavailable(monkeypatch):
    monkeypatch.setattr(sandbox_mod, "_probe_docker", lambda: False)
    sandbox = FailClosedMutationSandbox()

    called = {}

    async def _refuse(*a, **k):  # the parent's fallback must be unreachable
        called["subprocess"] = True
        return _outcome("success", "subprocess")

    async def _no_exec(*a, **k):  # nothing may spawn at all
        called["exec"] = True
        raise AssertionError("create_subprocess_exec called on refusal path")

    monkeypatch.setattr(ContainerSandbox, "_execute_subprocess", _refuse)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _no_exec)

    with pytest.raises(MutationSandboxUnavailable):
        asyncio.run(sandbox.execute_raw_python(
            tenant_id="t", code="import os; os.listdir('/')"))

    assert called == {}  # neither fallback nor any subprocess was reached


def test_execute_mutation_structured_refusal(monkeypatch):
    monkeypatch.setattr(sandbox_mod, "_probe_docker", lambda: False)
    result = asyncio.run(execute_mutation(
        FailClosedMutationSandbox(), tenant_id="t", code="pass"))
    assert result["status"] == "refused"
    assert result["environment"] is None
    assert "fail-closed" in result["output"]


def test_sandbox_attests_container_isolation(monkeypatch):
    monkeypatch.setattr(sandbox_mod, "_probe_docker", lambda: True)

    async def _fake_docker(self, *a, **kw):
        return _outcome("success", "docker")

    monkeypatch.setattr(ContainerSandbox, "execute_raw_python", _fake_docker)
    result = asyncio.run(execute_mutation(
        FailClosedMutationSandbox(), tenant_id="t", code="pass"))
    assert result["status"] == "success"
    assert result["isolation"] == "container:network=none:fs=read-only"


def test_sandbox_refuses_non_container_result(monkeypatch):
    """Defence in depth: a parent refactor that reintroduces the fallback
    must surface as a refusal, never as a silently degraded execution."""
    monkeypatch.setattr(sandbox_mod, "_probe_docker", lambda: True)

    async def _sneaky_fallback(self, *a, **kw):
        return _outcome("success", "subprocess")

    monkeypatch.setattr(ContainerSandbox, "execute_raw_python", _sneaky_fallback)
    sandbox = FailClosedMutationSandbox()
    with pytest.raises(MutationSandboxUnavailable):
        asyncio.run(sandbox.execute_raw_python(tenant_id="t", code="pass"))
    result = asyncio.run(execute_mutation(sandbox, tenant_id="t", code="pass"))
    assert result["status"] == "refused"
    assert "non-container" in result["output"]


def test_sandbox_refuses_network():
    with pytest.raises(ValueError):
        FailClosedMutationSandbox(enable_network=True)


# ---------------------------------------------------------------------------
# Rollout taxonomy
# ---------------------------------------------------------------------------

def _rollouts(status: RolloutStatus, n: int, task_id: str = "t1") -> list:
    return [RolloutOutcome(task_id=task_id, status=status) for _ in range(n)]


def test_pass_rate_excludes_harness_errors():
    outcomes = (_rollouts(RolloutStatus.PASS, 2)
                + _rollouts(RolloutStatus.AGENT_FAIL, 2)
                + _rollouts(RolloutStatus.HARNESS_ERROR, 3))
    stats = pass_rate(outcomes)
    assert stats == {"n": 4, "passes": 2, "rate": 0.5, "harness_errors": 3}


def test_pass_rate_all_harness_errors_is_none_not_zero():
    stats = pass_rate(_rollouts(RolloutStatus.HARNESS_ERROR, 2))
    assert stats["rate"] is None and stats["n"] == 0


# ---------------------------------------------------------------------------
# Wilson interval — boundary values
# ---------------------------------------------------------------------------

def test_wilson_known_values():
    lo, hi = wilson_interval(0, 3)
    assert lo == 0.0 and hi == pytest.approx(0.5615, abs=1e-3)
    lo, hi = wilson_interval(3, 3)
    assert lo == pytest.approx(0.4385, abs=1e-3) and hi == 1.0
    lo, hi = wilson_interval(4, 6)
    assert lo == pytest.approx(0.2997, abs=1e-3)
    assert hi == pytest.approx(0.9029, abs=1e-3)
    lo, hi = wilson_interval(5, 6)
    assert lo == pytest.approx(0.4363, abs=1e-3)
    assert hi == pytest.approx(0.9701, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 1.0)  # degenerate, not a crash


def test_wilson_stays_in_unit_interval_everywhere():
    for n in range(1, 25):
        for s in range(n + 1):
            lo, hi = wilson_interval(s, n)
            assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# Two-stage admission (screen 3 → confirm 6 by default)
# ---------------------------------------------------------------------------

def _screen(passes: int) -> list:
    return ([RolloutOutcome(task_id="t", status=RolloutStatus.PASS)] * passes
            + [RolloutOutcome(task_id="t", status=RolloutStatus.AGENT_FAIL)]
            * (3 - passes))


def _confirm(passes: int, n: int = 6) -> list:
    return ([RolloutOutcome(task_id="t", status=RolloutStatus.PASS)] * passes
            + [RolloutOutcome(task_id="t", status=RolloutStatus.AGENT_FAIL)]
            * (n - passes))


def test_admission_rejects_impossible_at_screening():
    decision = admit_mutation(_screen(0), _confirm(3))
    assert not decision.admitted
    assert "impossible" in decision.reason


def test_admission_rejects_trivial_when_confirmation_all_pass():
    decision = admit_mutation(_screen(3), _confirm(6))
    assert not decision.admitted
    assert "trivial" in decision.reason


def test_admission_rejects_impossible_confirmation():
    decision = admit_mutation(_screen(1), _confirm(0))
    assert not decision.admitted
    assert "impossible" in decision.reason


def test_admission_accepts_midband_with_uncertainty():
    decision = admit_mutation(_screen(2), _confirm(4))
    assert decision.admitted
    lo, hi = decision.interval
    assert lo < 0.75 and hi > 0.25          # overlaps the band
    assert 0 < lo and hi < 1                 # excludes trivial + impossible


def test_admission_too_hard_and_too_easy_branches():
    # lo > band.high → too easy (needs a large confirmation set)
    decision = admit_mutation(_screen(3), _confirm(29, n=30),
                              band=BandSpec(low=0.25, high=0.75))
    assert not decision.admitted
    assert "too easy" in decision.reason
    # hi < band.low → too hard (3/30 interval just overlaps the floor;
    # 2/30 clears it — pinned so the branch's arithmetic stays honest)
    decision = admit_mutation(_screen(3), _confirm(2, n=30),
                              band=BandSpec(low=0.25, high=0.75))
    assert not decision.admitted
    assert "too hard" in decision.reason


def test_admission_refuses_to_decide_on_harness_errors():
    # 1 scorable + 1 harness error < the 3-rollout screening requirement —
    # the protocol must refuse to decide rather than silently shrink n.
    screen = [RolloutOutcome(task_id="t", status=RolloutStatus.PASS),
              RolloutOutcome(task_id="t", status=RolloutStatus.HARNESS_ERROR)]
    with pytest.raises(ValueError, match="rerun harness errors"):
        admit_mutation(screen, _confirm(4))


def test_admission_needs_full_confirmation_set():
    with pytest.raises(ValueError, match="confirmation"):
        admit_mutation(_screen(2), _confirm(1, n=2))


def test_admission_decision_serializes():
    decision = admit_mutation(_screen(2), _confirm(4))
    payload = decision.to_dict()
    assert payload["admitted"] is True
    assert len(payload["interval"]) == 2


# ---------------------------------------------------------------------------
# Declarative mutation shapes
# ---------------------------------------------------------------------------

def test_setup_mutation_rejects_non_world_keys():
    with pytest.raises(ValueError, match="non-world keys"):
        SetupMutation({"form_submissions": 99}).validate(
            {"headline", "docs", "creds"})


def test_setup_mutation_accepts_world_keys():
    SetupMutation({"headline": "x"}).validate({"headline", "docs"})  # no raise


def test_rulespec_validates_kind_and_params():
    kinds = {"hide_link": {"href"}, "block_path": {"path"}}
    RuleSpec("hide_link", {"href": "/x"}).validate(kinds)  # no raise
    with pytest.raises(ValueError, match="Unknown rule kind"):
        RuleSpec("explode", {}).validate(kinds)
    with pytest.raises(ValueError, match="missing params"):
        RuleSpec("block_path", {}).validate(kinds)


def test_mutation_stack_describe_shape():
    stack = MutationStack(
        name="s1",
        setup=SetupMutation({"headline": "H"}),
        rules=RulesMutation(observe=(RuleSpec("redact_text", {"text": "x"}),)),
    )
    described = stack.describe()
    assert described["setup"] == {"headline": "H"}
    assert described["rules"]["observe"][0]["kind"] == "redact_text"
    assert described["rules"]["action"] == []
