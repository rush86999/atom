"""Independent personal-scope equivalence and missing-actor authority controls.

These are the failure-first twins for the two root-confirmed regressions:

1. ``resolve_workspace_id`` treats ``None``, ``""`` and ``"default"`` as the
   Personal Edition default, but the SQL authority predicate only accepted
   ``None``/``"default"``.  A legitimate personal actor carrying an empty
   workspace therefore passed the Python pre-check and then lost the same
   conditional claim UPDATE.
2. A wait binding with no original actor returned ``(None, "")`` from the
   Python helper and no SQL predicate, so the claim ran with wildcard authority
   and an admin reviewer's answer resumed the original job.

Both are exercised through the real ``resume_information_wait_action``
consumer and the real startup recovery driver.  Only the descendant dispatch
boundary (``execute_agent_task``) is doubled.
"""
import pytest

from tests.test_generic_information_wait_recovery_authority import (
    _assert_direct_refused,
    _assert_refused_without_dispatch,
    _durable_state,
    _recover,
    _resume_direct,
    _set_user,
    _wait,
    world,  # noqa: F401 — requested by every test below
)


@pytest.mark.parametrize("workspace", [None, "", "default"])
def test_personal_actor_current_scope_matches_resolver_at_resume_claim(
        world, monkeypatch, workspace):
    """None/empty/default are the same personal scope at the real claim."""
    target = _wait(
        world, actor_id="personal-admin", agent_id="personal-agent",
        workspace_id="default", tenant_id=None)
    _set_user(world, "personal-admin", workspace_id=workspace)
    calls = []

    result = _resume_direct(world, target, monkeypatch, calls)

    assert result.get("resumed") is True, result
    assert len(calls) == 1, calls
    assert calls[0]["context"]["workspace_id"] == "default"
    assert _durable_state(world, target)["job_status"] == "success"


def test_personal_actor_moved_to_a_foreign_workspace_is_refused(
        world, monkeypatch):
    """The default alias must not wildcard-match a real foreign workspace."""
    target = _wait(
        world, actor_id="personal-admin", agent_id="personal-agent",
        workspace_id="default", tenant_id=None)
    _set_user(world, "personal-admin", workspace_id="ws2")
    calls = []

    result = _resume_direct(world, target, monkeypatch, calls)

    _assert_direct_refused(
        world, target, result, calls, "actor_workspace_mismatch")


def test_empty_workspace_is_not_an_alias_for_a_real_workspace(
        world, monkeypatch):
    """A real workspace stays exact; only the personal default aliases it."""
    target = _wait(world)
    _set_user(world, target.actor_id, workspace_id="")
    calls = []

    result = _resume_direct(world, target, monkeypatch, calls)

    _assert_direct_refused(
        world, target, result, calls, "actor_workspace_mismatch")


@pytest.mark.parametrize(
    "actor_id,reason",
    [("", "actor_missing"), (None, "actor_missing"),
     ("ghost-actor", "actor_unavailable")],
)
def test_missing_or_corrupt_actor_cannot_resume_from_an_answerer(
        world, monkeypatch, actor_id, reason):
    """An answerer/reviewer never substitutes for the original actor."""
    target = _wait(world, actor_id=actor_id)
    calls = []

    result = _resume_direct(
        world, target, monkeypatch, calls, reviewer_id="admin-1")

    _assert_direct_refused(world, target, result, calls, reason)


def test_claim_update_fails_closed_without_an_actor(world):
    """The claim CAS itself cannot turn an absent actor into a wildcard."""
    from api.agent_routes import _claim_waiting_job_for_resume

    target = _wait(world, actor_id="")

    claimed = _claim_waiting_job_for_resume(
        target.job_id,
        world.engine,
        agent_id="a1",
        execution_id=target.execution_id,
        action_id=target.action_id,
        actor_id=None,
        workspace_id=target.workspace_id,
        tenant_id="t1",
    )

    assert claimed is False
    assert _durable_state(world, target)["job_status"] == "waiting"


@pytest.mark.parametrize(
    "actor_id,reason",
    [("", "actor_missing"), (None, "actor_missing"),
     ("ghost-actor", "actor_unavailable")],
)
def test_missing_or_corrupt_actor_is_refused_on_startup(
        world, monkeypatch, actor_id, reason):
    """Startup recovery must not turn an absent actor into execution authority."""
    target = _wait(world, actor_id=actor_id)
    calls = []

    result = _recover(monkeypatch, calls)

    _assert_refused_without_dispatch(world, target, result, calls, reason)
