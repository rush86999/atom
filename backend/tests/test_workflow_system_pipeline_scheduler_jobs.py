"""System pipeline scheduler jobs must stay picklable and durable.

Regression coverage for the 2026-11-12 mounted-path blocker. Registering
``pipeline.run_pipeline`` (a bound method) made ``SQLAlchemyJobStore`` pickle
the pipeline instance, whose LanceDB memory manager owns a
``threading.Lock``. APScheduler flushed those pending jobs inside
``WorkflowScheduler.start()`` and raised
``TypeError: cannot pickle '_thread.lock' object`` while the scheduler was
still stopped, so every browser-created schedule only lived in memory.

The pipeline modules are stubbed (the real ones build a LanceDB store and
read integration credentials at import). Each stub deliberately carries a
real ``threading.Lock``, so a regression back to bound-method jobs fails here
for exactly the production reason.
"""
from __future__ import annotations

import sqlite3
import sys
import threading
import types

import pytest

import ai.workflow_scheduler as scheduler_module
from ai.workflow_scheduler import WorkflowScheduler

JOB_IDS = {
    "sales": "system_sales_ingestion",
    "projects": "system_projects_ingestion",
}

PIPELINE_MODULES = {
    "sales": "integrations.atom_sales_memory_pipeline",
    "projects": "integrations.atom_projects_memory_pipeline",
}


class _StubPipeline:
    """Minimal pipeline carrying the same unpicklable member as production."""

    def __init__(self) -> None:
        # LanceDBMemoryManager._store_surgery_lock
        self._store_surgery_lock = threading.Lock()
        self.calls = 0

    async def run_pipeline(self) -> None:
        self.calls += 1


@pytest.fixture
def stub_pipelines(monkeypatch):
    instances = {}
    for name, module_name in PIPELINE_MODULES.items():
        pipeline = _StubPipeline()
        module = types.ModuleType(module_name)
        setattr(module, f"{name}_pipeline", pipeline)
        monkeypatch.setitem(sys.modules, module_name, module)
        instances[name] = pipeline
    return instances


@pytest.fixture
def pipeline_settings(monkeypatch):
    """Stub the settings source so no on-disk/live settings file is read."""
    class _Settings:
        @staticmethod
        def get_settings():
            return {
                "pipelines": {
                    "sales": {"mode": "scheduled", "cron": "*/30 * * * *"},
                    "projects": {"mode": "scheduled", "cron": "*/15 * * * *"},
                }
            }

    module = types.ModuleType("core.automation_settings")
    module.get_automation_settings = lambda: _Settings()
    monkeypatch.setitem(sys.modules, "core.automation_settings", module)


def _jobstore_ids(db_path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        return {row[0] for row in connection.execute(
            "select id from apscheduler_jobs")}
    finally:
        connection.close()


async def test_pipeline_jobs_are_picklable_and_survive_restart(
        tmp_path, stub_pipelines, pipeline_settings):
    """The startup flush and a fresh scheduler both keep the two jobs."""
    db_url = f"sqlite:///{tmp_path / 'jobs.db'}"

    first = WorkflowScheduler(db_url=db_url)
    try:
        # Production startup order: register while stopped, then start. This
        # is the path that used to raise on the pending-job flush.
        first.reschedule_system_pipelines()
        first.start()
        assert first.scheduler.running
        listed = {job["id"] for job in first.list_jobs()}
        assert set(JOB_IDS.values()) <= listed
    finally:
        first.shutdown()

    assert _jobstore_ids(tmp_path / "jobs.db") == set(JOB_IDS.values())

    second = WorkflowScheduler(db_url=db_url)
    try:
        second.start()
        for name, job_id in JOB_IDS.items():
            job = second.scheduler.get_job(job_id)
            assert job is not None, f"{job_id} was lost across restart"
            # The persisted target is the module-level dispatcher plus the
            # pipeline name — never the instance.
            assert job.func is scheduler_module._run_system_pipeline
            assert tuple(job.args) == (name,)
    finally:
        second.shutdown()


async def test_persisted_pipeline_job_dispatches_by_name(
        tmp_path, stub_pipelines, pipeline_settings):
    """A job reloaded from disk resolves the live singleton when it fires."""
    db_url = f"sqlite:///{tmp_path / 'jobs.db'}"

    first = WorkflowScheduler(db_url=db_url)
    try:
        first.start()
    finally:
        first.shutdown()

    second = WorkflowScheduler(db_url=db_url)
    try:
        second.start()
        job = second.scheduler.get_job(JOB_IDS["sales"])
        assert job is not None
        await job.func(*job.args)
    finally:
        second.shutdown()

    assert stub_pipelines["sales"].calls == 1
    assert stub_pipelines["projects"].calls == 0


async def test_pipeline_registration_failure_does_not_block_start(
        tmp_path, monkeypatch, stub_pipelines, pipeline_settings):
    """A bad pipeline job must not hold the whole scheduler hostage."""
    # A lambda cannot be referenced by the SQLAlchemy jobstore, which is how
    # any future unpicklable/bound-method registration fails at add_job time.
    monkeypatch.setattr(
        scheduler_module, "_run_system_pipeline", lambda name: None)

    scheduler = WorkflowScheduler(db_url=f"sqlite:///{tmp_path / 'jobs.db'}")
    try:
        scheduler.start()
        assert scheduler.scheduler.running
        assert scheduler.scheduler.get_jobs() == []
    finally:
        scheduler.shutdown()
