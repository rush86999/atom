"""Boot-time crash recovery must not be gated by ENABLE_SCHEDULER.

THE DEFECT THIS PINS
`core.execution_recovery.reconcile_orphaned_executions` is documented as the
fix for the "ghost run" problem: a process that dies mid-run leaves an
`AgentExecution` row in `running` forever, invisible to failure dashboards and
retry logic. The sweep was wired into `main_api_app.lifespan` -- but *inside*

    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true" and not is_test_mode:

so any process that does not run schedulers never reconciled anything, and
emitted no log line either, so the omission was invisible. Measured on a real
SIGKILL mid-turn (`acceptance/lane3/crash_recovery_probe.py`, 2026-09-27): the
interrupted execution was still `running` after a clean restart through the real
launcher, and the boot log contained no recovery line at all.

Reconciling durable state is not a background service. It is an integrity pass:
idempotent, one indexed query, and required at every boot.

WHY A STRUCTURAL TEST
The invariant is about the shape of the startup function -- "this call is not
nested under that condition" -- not about a return value. Asserting the shape is
what can actually catch a future re-nesting, and it costs no database, no model
and no server. The negative control below exists because a structural test that
cannot fail is worthless: it is graded against a synthetic module with the calls
deliberately re-nested, and must report them as gated.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

MAIN_APP = Path(__file__).resolve().parents[1] / "main_api_app.py"
RECOVERY_CALLS = ("reconcile_orphaned_executions", "notify_recovered_continuations")


def _lifespan(tree: ast.Module) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            return node
    raise AssertionError("main_api_app has no lifespan() startup function")


def _called_names(fn: ast.AST) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name in RECOVERY_CALLS:
                out.append((name, node.lineno))
    return out


def _enclosing_conditions(fn: ast.AST, line: int) -> list[str]:
    """Every `if` whose body contains `line` -- i.e. every gate it sits behind."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and node.lineno < line <= (node.end_lineno or 0):
            out.append(ast.unparse(node.test))
    return out


def _gated_calls(source: str) -> dict[str, list[str]]:
    tree = ast.parse(source)
    lifespan = _lifespan(tree)
    gated: dict[str, list[str]] = {}
    for name, line in _called_names(lifespan):
        conditions = _enclosing_conditions(lifespan, line)
        if conditions:
            gated[name] = conditions
    return gated


def test_boot_recovery_runs_outside_every_conditional():
    gated = _gated_calls(MAIN_APP.read_text())
    assert gated == {}, (
        "boot-time crash recovery is nested under a condition again: "
        f"{gated}. It must run at every boot, not only when a scheduler does."
    )


def test_both_recovery_passes_are_still_wired():
    called = {name for name, _ in _called_names(_lifespan(ast.parse(MAIN_APP.read_text())))}
    missing = set(RECOVERY_CALLS) - called
    assert not missing, f"boot recovery call(s) disappeared from lifespan(): {missing}"


def test_sweep_runs_before_the_scheduler_gate():
    """Reconcile first, then start new work.

    Ordering is not cosmetic: a scheduler that picks up an orphaned task before
    the sweep has marked its execution failed is the double-fire this pass
    exists to prevent.
    """
    lifespan = _lifespan(ast.parse(MAIN_APP.read_text()))
    sweep_line = dict(_called_names(lifespan)).get("reconcile_orphaned_executions")
    assert sweep_line is not None
    gates = [n.lineno for n in ast.walk(lifespan)
             if isinstance(n, ast.If) and "ENABLE_SCHEDULER" in ast.unparse(n.test)]
    assert gates, "no ENABLE_SCHEDULER gate found; this test can no longer see the ordering"
    assert sweep_line < min(gates), (
        f"the sweep (line {sweep_line}) must run before the scheduler gate "
        f"(line {min(gates)})"
    )


NESTED = '''
async def lifespan(app):
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true" and not is_test_mode:
        from core.execution_recovery import reconcile_orphaned_executions
        reconcile_orphaned_executions()
        from core.async_turn_continuation import notify_recovered_continuations
        notify_recovered_continuations()
'''


@pytest.mark.parametrize("call", RECOVERY_CALLS)
def test_negative_control_the_detector_sees_a_re_nested_call(call: str):
    """If this fails, the checks above are passing vacuously."""
    gated = _gated_calls(NESTED)
    assert call in gated, (
        "the detector did not flag a deliberately re-nested call, so it cannot "
        "be trusted to flag a real one"
    )
    assert any("ENABLE_SCHEDULER" in c for c in gated[call])
