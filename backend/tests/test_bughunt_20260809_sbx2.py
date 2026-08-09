"""Bug hunt wave-2 — sandbox cap instrumentation + canvas per-run semantics.

T1  sandbox_caps: ``max_bytes_written`` and ``max_cost_usd`` are computed
    into the policy but NEVER enforced — ``record_write``/``record_cost``
    have zero production callers, so only ``max_tool_calls`` +
    ``max_exec_seconds`` actually bound a run. A file-writing tool can
    stream gigabytes into the run's workspace and an LLM-invoking tool
    can spend unbounded money. ``check_caps`` must estimate per-call
    bytes/cost from (tool_name, args) at the choke point and RESTRICT
    before the call when the cumulative budget would be exceeded.

T2  ``canvas_logic_service.run()`` issues its policy with the DETERMINISTIC
    run_id ``canvas-{namespace}`` (``mini_app_service.run_stateful``:
    ``miniapp-{ns}``). Caps/KillRun counters are keyed on run_id, so
    counters persist ACROSS runs of the same canvas — a long-lived canvas
    permanently burns its budget. Each run needs a fresh per-run run_id
    (uuid) while per-canvas identity is preserved.

T3  ``sanitize_namespace`` maps ``a.b``, ``a-b`` and ``a b`` all to ``a-b``:
    two distinct canvases share one per-canvas FS dir (cross-canvas file
    bleed). The mapping must be injective (separators encoded).
"""
import os

import pytest

from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch):
    """Reset ATOM_SANDBOX_* env vars + counter registries."""
    for k in list(os.environ):
        if k.startswith("ATOM_SANDBOX"):
            monkeypatch.delenv(k, raising=False)
    from core.sandbox_caps import get_registry as get_caps_registry
    from core.sandbox_killrun import get_registry as get_killrun_registry

    get_caps_registry().reset()
    get_killrun_registry().reset()


def _policy(**kw):
    from core.sandbox_policy import SandboxPolicy

    defaults = dict(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="autonomous",
        max_tool_calls=200,
        max_exec_seconds=600,
        max_bytes_written=100 * 1024 * 1024,
        max_cost_usd=5.0,
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


# ===========================================================================
# T1 — bytes/cost caps must be enforced at the check_caps choke point
# ===========================================================================


def test_caps_reject_write_that_exceeds_bytes_budget():
    """RED: a single write whose payload exceeds max_bytes_written is
    currently ALLOWED (bytes_written is never incremented by callers)."""
    from core import sandbox_caps
    from core.sandbox_policy import RESTRICTED, VT_CAP_EXCEEDED

    policy = _policy(max_bytes_written=100)
    d = sandbox_caps.check_caps(
        policy,
        tool_name="write_code_file",
        args={"path": "/tmp/x.py", "content": "y" * 200},
    )
    assert d.decision == RESTRICTED
    assert d.violation_type == VT_CAP_EXCEEDED
    assert d.metadata_json.get("cap") == "max_bytes_written"


def test_caps_bytes_accumulate_across_writes_then_restrict():
    """RED: writes accrue against the budget across calls; the call that
    would cross the line is denied. Today nothing accrues, so all pass."""
    from core import sandbox_caps
    from core.sandbox_policy import ALLOWED, RESTRICTED

    policy = _policy(max_bytes_written=100)
    d1 = sandbox_caps.check_caps(
        policy, tool_name="write_code_file", args={"content": "a" * 40}
    )
    d2 = sandbox_caps.check_caps(
        policy, tool_name="write_code_file", args={"content": "b" * 59}
    )
    d3 = sandbox_caps.check_caps(
        policy, tool_name="write_code_file", args={"content": "c" * 1}
    )
    assert d1.decision == ALLOWED
    assert d2.decision == ALLOWED
    assert d3.decision == RESTRICTED
    assert d3.metadata_json.get("cap") == "max_bytes_written"


def test_caps_non_write_tool_passes_bytes_budget():
    """A read-only tool with a large payload does not accrue write bytes."""
    from core import sandbox_caps
    from core.sandbox_policy import ALLOWED

    policy = _policy(max_bytes_written=100)
    d = sandbox_caps.check_caps(
        policy, tool_name="browser_click", args={"content": "y" * 500}
    )
    assert d.decision == ALLOWED


def test_caps_reject_llm_call_that_exceeds_cost_budget():
    """RED: an LLM-invoking tool whose estimated prompt cost exceeds
    max_cost_usd is currently ALLOWED (cost is never incremented)."""
    from core import sandbox_caps
    from core.sandbox_policy import RESTRICTED, VT_CAP_EXCEEDED

    policy = _policy(max_cost_usd=0.001)
    d = sandbox_caps.check_caps(
        policy,
        tool_name="documents.ask_image",
        args={"path": "/tmp/x.png", "prompt": "x" * 500},
    )
    assert d.decision == RESTRICTED
    assert d.violation_type == VT_CAP_EXCEEDED
    assert d.metadata_json.get("cap") == "max_cost_usd"


def test_caps_cost_accumulates_then_restricts():
    """RED: LLM-call cost accrues across calls; the call that would cross
    the line is denied."""
    from core import sandbox_caps
    from core.sandbox_policy import ALLOWED, RESTRICTED

    policy = _policy(max_cost_usd=0.001)
    d1 = sandbox_caps.check_caps(
        policy, tool_name="documents.ask_image", args={"prompt": "x" * 200}
    )
    d2 = sandbox_caps.check_caps(
        policy, tool_name="documents.ask_image", args={"prompt": "y" * 200}
    )
    assert d1.decision == ALLOWED
    assert d2.decision == RESTRICTED
    assert d2.metadata_json.get("cap") == "max_cost_usd"


def test_gate_enforces_bytes_cap_at_choke_point(monkeypatch):
    """RED: the shared P9 gate (used by integrations.mcp_service.call_tool)
    must RESTRICT a bytes-exceeding write tool call. Today the cap decision
    is ALLOWED because bytes_written stays at zero."""
    monkeypatch.setenv("ATOM_SANDBOX_ENABLED", "true")
    monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_SANDBOX_FS_ENABLED", "true")
    monkeypatch.setenv("ATOM_SANDBOX_WHITELIST_ENABLED", "true")
    monkeypatch.setenv("ATOM_SANDBOX_TRIPWIRES_ENABLED", "true")
    monkeypatch.setenv("ATOM_SANDBOX_CAPS_ENABLED", "true")
    monkeypatch.setenv("ATOM_SANDBOX_MAX_BYTES_WRITTEN", "100")

    from core.sandbox_gate import evaluate_tool_call

    ctx = {"run_id": "r-gate", "tier": "autonomous", "agent_id": "a1"}
    d = evaluate_tool_call(
        "write_code_file",
        {"path": "/tmp/agent/r-gate/out.py", "content": "x" * 500},
        ctx,
    )
    assert d is not None, "gate must engage"
    assert d.requires_review
    assert d.metadata_json.get("cap") == "max_bytes_written"


# ===========================================================================
# T2 — canvas logic runs get a fresh per-run budget (run_id is not
#      deterministic per canvas)
# ===========================================================================


class _FakeRuntime:
    """Captures the issued policy per execution."""

    def __init__(self):
        self.policies = []

    async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
        self.policies.append(policy)
        result = MagicMock()
        result.success = True
        result.stdout = ""
        result.stderr = ""
        result.exit_code = 0
        return result


@pytest.mark.asyncio
async def test_canvas_logic_run_id_fresh_per_run(monkeypatch, tmp_path, db_session):
    """RED: two sequential runs of the same canvas issue the SAME
    deterministic run_id (`canvas-{ns}`), so per-run counters (tool calls,
    bytes, cost, KillRun) persist across runs. Each run needs a fresh
    run_id with per-canvas identity preserved."""
    from core import canvas_logic_service as cls

    runtime = _FakeRuntime()
    monkeypatch.setattr(cls, "get_runtime", lambda: runtime)
    monkeypatch.setattr(cls, "CANVAS_RUNTIME_ROOT", str(tmp_path))

    svc = cls.CanvasLogicService(db_session)
    svc.save_logic(canvas_id="c9", source="x = 1", created_by="u1")
    await svc.run("c9", inputs={})
    await svc.run("c9", inputs={})

    run_ids = [p.run_id for p in runtime.policies]
    assert run_ids[0] != run_ids[1], (
        "same canvas must not reuse the same run_id across runs"
    )
    # Per-canvas identity preserved in the run_id.
    assert run_ids[0].startswith("canvas-")
    assert run_ids[1].startswith("canvas-")


@pytest.mark.asyncio
async def test_canvas_logic_fresh_budget_after_previous_run_spent(
    monkeypatch, tmp_path, db_session
):
    """RED: burn run 1's full tool-call budget; run 2 of the same canvas
    must start with a fresh budget. Today both runs share the run_id
    `canvas-<ns>`, so run 2 inherits run 1's exhausted counters."""
    monkeypatch.setenv("ATOM_SANDBOX_MAX_TOOL_CALLS", "1")
    from core import canvas_logic_service as cls
    from core import sandbox_caps
    from core.sandbox_policy import ALLOWED, RESTRICTED

    runtime = _FakeRuntime()
    monkeypatch.setattr(cls, "get_runtime", lambda: runtime)
    monkeypatch.setattr(cls, "CANVAS_RUNTIME_ROOT", str(tmp_path))

    svc = cls.CanvasLogicService(db_session)
    svc.save_logic(canvas_id="c9", source="x = 1", created_by="u1")
    await svc.run("c9", inputs={})
    await svc.run("c9", inputs={})

    p1, p2 = runtime.policies
    assert p1.run_id != p2.run_id

    # Run 1 spends its single allowed call.
    assert sandbox_caps.check_caps(p1, tool_name="browser_click", args={}).decision == ALLOWED
    assert sandbox_caps.check_caps(p1, tool_name="browser_click", args={}).decision == RESTRICTED
    # Run 2 must start fresh.
    assert sandbox_caps.check_caps(p2, tool_name="browser_click", args={}).decision == ALLOWED


# ===========================================================================
# T3 — sanitize_namespace must be injective
# ===========================================================================


def test_sanitize_namespace_distinct_for_separator_collisions():
    """RED: `a.b` and `a-b` map to the SAME namespace (`a-b`) — two
    distinct canvases share one per-canvas FS dir. The mapping must be
    injective: separators must be encoded, not collapsed."""
    from core.canvas_logic_service import sanitize_namespace

    assert sanitize_namespace("a.b") != sanitize_namespace("a-b")
    assert sanitize_namespace("a b") != sanitize_namespace("a-b")
    assert sanitize_namespace("a_b") != sanitize_namespace("a-b")


def test_sanitize_namespace_no_collisions_on_mixed_ids():
    from core.canvas_logic_service import sanitize_namespace

    ids = ["a.b", "a-b", "a_b", "a b", "a/b", "a..b", "a.b-c", "canvas-1", "c9"]
    namespaces = [sanitize_namespace(i) for i in ids]
    assert len(set(namespaces)) == len(ids), (
        "namespace mapping must be collision-free for mixed separator ids"
    )


def test_sanitize_namespace_still_path_safe():
    from core.canvas_logic_service import sanitize_namespace

    for evil in ("../../etc", "/etc/passwd", "a/../b", ".."):
        ns = sanitize_namespace(evil)
        assert ns != evil
        assert "/" not in ns
        assert ".." not in ns
