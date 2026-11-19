"""
TDD regression test: WorkflowScheduler._execute_job only resolved scheduled
workflows via load_workflows() (workflows.json). DB templates (WorkflowTemplate)
are schedulable via POST /workflows/{id}/schedule but, when the job fired, the
scheduler logged "Scheduled workflow ... not found" and never started them.
A scheduled template fire must fall back to _load_template_definition, matching
POST /workflows/{id}/execute.

The fallback is authorized by the complete frozen scope (tenant/workspace/user)
through the shared _current_read_actor check, so a revoked/inactive actor cannot
select a private definition. Incomplete legacy identity still resolves public
templates with actor=None. An unresolved definition only triggers the original
dead-schedule cleanup when the DB positively confirms the template is absent.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.workflow_scheduler import WorkflowScheduler

EXECUTION_SCOPE_KEY = "_atom_execution_scope"


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, user=None, template=None, template_error=None):
        self._user = user
        self._template = template
        self._template_error = template_error

    def expire_all(self):
        pass

    def query(self, model, *args, **kwargs):
        if getattr(model, "__name__", "") == "WorkflowTemplate":
            if self._template_error is not None:
                raise self._template_error
            return _FakeQuery(self._template)
        return _FakeQuery(self._user)


@contextmanager
def _fake_db_session(user=None, template=None, template_error=None):
    yield _FakeDB(user, template, template_error)


def _scheduler_with_jobs(*jobs):
    return SimpleNamespace(
        scheduler=SimpleNamespace(
            get_jobs=MagicMock(return_value=list(jobs)),
            remove_job=MagicMock(),
        )
    )


@pytest.mark.asyncio
async def test_scheduled_template_fire_uses_template_fallback():
    """A scheduled DB template (absent from workflows.json) must be resolved via
    the template fallback and started on the durable WorkflowEngine."""
    template_def = {"id": "tpl_1", "name": "Template", "steps": [
        {"id": "s1", "service": "http", "action": "get", "parameters": {}},
    ]}

    durable_engine = AsyncMock()

    with (
        patch("core.workflow_engine.frozen_execution_scope", return_value={}),
        patch("core.database.get_db_session", return_value=_fake_db_session()),
        patch("core.workflow_engine.get_workflow_engine", return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._load_template_definition", return_value=template_def),
    ):
        await WorkflowScheduler._execute_job("tpl_1", {"k": "v"}, authorized=True)

    assert durable_engine.start_workflow.await_count >= 1, (
        "scheduled template fire did not start the durable WorkflowEngine"
    )


@pytest.mark.asyncio
async def test_scheduled_template_fire_uses_current_read_actor_for_complete_scope():
    """The frozen scope is revalidated through _current_read_actor, not a stale
    user row or a plain job input user_id."""
    frozen_scope = {
        "tenant_id": "tenant_a",
        "workspace_id": "workspace_a",
        "user_id": "usr_frozen",
    }
    current_user = SimpleNamespace(
        id="usr_frozen", is_active=True, status="active",
        tenant_id="tenant_a", workspace_id="workspace_a",
    )
    template_def = {"id": "tpl_1", "name": "Template", "steps": []}
    resolver = MagicMock(return_value=template_def)
    read_actor = MagicMock(return_value=current_user)
    durable_engine = AsyncMock()

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value=frozen_scope),
        patch("core.database.get_db_session",
              return_value=_fake_db_session(user=current_user)),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._current_read_actor", read_actor),
        patch("core.workflow_endpoints._load_template_definition", resolver),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_1",
            {
                "user_id": "usr_spoofed",
                EXECUTION_SCOPE_KEY: frozen_scope,
            },
            authorized=True,
        )

    assert read_actor.call_args.args[1] == frozen_scope
    assert resolver.call_args.kwargs["user"] is current_user
    assert resolver.call_args.kwargs["db"] is not None
    assert durable_engine.start_workflow.await_count >= 1


@pytest.mark.asyncio
async def test_incomplete_legacy_identity_resolves_public_template_without_actor():
    """Legacy jobs without tenant/workspace cannot use the read-actor check;
    they stay anonymous so public/catalog templates still resolve."""
    template_def = {"id": "tpl_1", "name": "Template", "steps": []}
    resolver = MagicMock(return_value=template_def)
    read_actor = MagicMock()
    durable_engine = AsyncMock()

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value={"user_id": "usr_legacy"}),
        patch("core.database.get_db_session", return_value=_fake_db_session()),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._current_read_actor", read_actor),
        patch("core.workflow_endpoints._load_template_definition", resolver),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_1",
            {EXECUTION_SCOPE_KEY: {"user_id": "usr_legacy"}},
            authorized=True,
        )

    read_actor.assert_not_called()
    assert resolver.call_args.kwargs["user"] is None
    assert durable_engine.start_workflow.await_count >= 1


@pytest.mark.asyncio
async def test_private_revoked_template_does_not_delete_schedules():
    """A revoked actor yields resolver None for a private template; the DB row
    still exists, so this is not a dead schedule."""
    frozen_scope = {
        "tenant_id": "tenant_a",
        "workspace_id": "workspace_a",
        "user_id": "usr_revoked",
    }
    resolver = MagicMock(return_value=None)
    read_actor = MagicMock(return_value=None)
    durable_engine = AsyncMock()
    dead_job = SimpleNamespace(id="job_private_owner", args=["tpl_1", {}, True])
    scheduler = _scheduler_with_jobs(dead_job)

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value=frozen_scope),
        patch("core.database.get_db_session",
              return_value=_fake_db_session(
                  template=SimpleNamespace(id="tpl_1"))),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._current_read_actor", read_actor),
        patch("core.workflow_endpoints._load_template_definition", resolver),
        patch("ai.workflow_scheduler.workflow_scheduler", scheduler),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_1",
            {EXECUTION_SCOPE_KEY: frozen_scope},
            authorized=True,
        )

    assert resolver.call_args.kwargs["user"] is None
    assert durable_engine.start_workflow.await_count == 0
    scheduler.scheduler.remove_job.assert_not_called()


@pytest.mark.asyncio
async def test_unverifiable_template_existence_does_not_delete_schedules():
    """If DB existence cannot be checked, fail closed without cleanup."""
    frozen_scope = {
        "tenant_id": "tenant_a",
        "workspace_id": "workspace_a",
        "user_id": "usr_author",
    }
    durable_engine = AsyncMock()
    dead_job = SimpleNamespace(id="job_maybe_alive", args=["tpl_1", {}, True])
    scheduler = _scheduler_with_jobs(dead_job)

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value=frozen_scope),
        patch("core.database.get_db_session",
              return_value=_fake_db_session(
                  template_error=RuntimeError("template lookup failed"))),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._current_read_actor", return_value=None),
        patch("core.workflow_endpoints._load_template_definition",
              return_value=None),
        patch("ai.workflow_scheduler.workflow_scheduler", scheduler),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_1",
            {EXECUTION_SCOPE_KEY: frozen_scope},
            authorized=True,
        )

    assert durable_engine.start_workflow.await_count == 0
    scheduler.scheduler.remove_job.assert_not_called()


@pytest.mark.asyncio
async def test_confirmed_missing_definition_runs_original_dead_cleanup():
    """A DB-confirmed absent template is a dead schedule and is removed."""
    frozen_scope = {
        "tenant_id": "tenant_a",
        "workspace_id": "workspace_a",
        "user_id": "usr_author",
    }
    durable_engine = AsyncMock()
    dead_job = SimpleNamespace(id="job_dead", args=["tpl_deleted", {}, True])
    other_job = SimpleNamespace(id="job_other", args=["tpl_other", {}, True])
    scheduler = _scheduler_with_jobs(dead_job, other_job)

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value=frozen_scope),
        patch("core.database.get_db_session",
              return_value=_fake_db_session(template=None)),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._current_read_actor", return_value=None),
        patch("core.workflow_endpoints._load_template_definition",
              return_value=None),
        patch("ai.workflow_scheduler.workflow_scheduler", scheduler),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_deleted",
            {EXECUTION_SCOPE_KEY: frozen_scope},
            authorized=True,
        )

    assert durable_engine.start_workflow.await_count == 0
    scheduler.scheduler.remove_job.assert_called_once_with("job_dead")


@pytest.mark.asyncio
async def test_template_resolution_db_error_does_not_delete_schedules():
    """A DB failure must fail closed without destructive job cleanup."""
    durable_engine = AsyncMock()
    dead_job = SimpleNamespace(id="job_other_owner", args=["tpl_1", {}, True])
    scheduler = _scheduler_with_jobs(dead_job)

    with (
        patch("core.workflow_engine.frozen_execution_scope",
              return_value={"user_id": "usr_author"}),
        patch("core.database.get_db_session",
              side_effect=RuntimeError("scratch db unavailable")),
        patch("core.workflow_engine.get_workflow_engine",
              return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("ai.workflow_scheduler.workflow_scheduler", scheduler),
    ):
        await WorkflowScheduler._execute_job(
            "tpl_1",
            {EXECUTION_SCOPE_KEY: {"user_id": "usr_author"}},
            authorized=True,
        )

    assert durable_engine.start_workflow.await_count == 0
    scheduler.scheduler.remove_job.assert_not_called()
