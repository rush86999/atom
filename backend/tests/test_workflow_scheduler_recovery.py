"""Scheduler persistence recovery — no duplicate effects across restart.

The approval/effect matrix already exists in
``test_workflow_hitl_resume_once.py``. This file covers the other half of the
public workflow/scheduling recovery boundary:

* a paused one-shot job survives a scheduler restart without firing;
* a cancelled one-shot job survives a restart without firing;
* a job that fired exactly once does not fire again after a restart.

The real ``WorkflowScheduler`` and its SQLAlchemy jobstore are used; only the
job callback is a harmless local counter (no workflow/network effect).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from ai.workflow_scheduler import WorkflowScheduler


FIRED: list[str] = []


async def _counted_fire(workflow_id, input_data=None, authorized=False):
    """Harmless local callback used as the persisted scheduler job."""
    FIRED.append(str(workflow_id))


@pytest.fixture(autouse=True)
def _clear_fired():
    FIRED.clear()
    yield
    FIRED.clear()


def _make_scheduler(db_path, monkeypatch) -> WorkflowScheduler:
    monkeypatch.setattr(
        WorkflowScheduler, "_execute_job", staticmethod(_counted_fire))
    scheduler = WorkflowScheduler(db_url=f"sqlite:///{db_path}")
    # System pipeline imports are unrelated to this boundary and would add
    # their own jobs to the store.
    scheduler.reschedule_system_pipelines = lambda: None
    scheduler.start()
    return scheduler


def _date_config(seconds: float) -> dict:
    return {
        "trigger_type": "date",
        "trigger_config": {
            "run_date": datetime.now(timezone.utc) + timedelta(seconds=seconds)
        },
    }


@pytest.mark.asyncio
async def test_paused_schedule_survives_restart_without_firing(
        tmp_path, monkeypatch):
    db_path = tmp_path / "paused-jobs.db"
    first = _make_scheduler(db_path, monkeypatch)
    job_id = first.schedule_workflow("wf-paused", **_date_config(0.3))
    first.scheduler.pause_job(job_id)
    first.shutdown()

    second = _make_scheduler(db_path, monkeypatch)
    try:
        await asyncio.sleep(0.7)
        assert FIRED == [], "paused job fired after scheduler restart"
        job = second.scheduler.get_job(job_id)
        assert job is not None, "paused job was lost across restart"
        assert job.next_run_time is None, "paused job became runnable again"
    finally:
        second.shutdown()


@pytest.mark.asyncio
async def test_cancelled_schedule_survives_restart_without_firing(
        tmp_path, monkeypatch):
    db_path = tmp_path / "cancelled-jobs.db"
    first = _make_scheduler(db_path, monkeypatch)
    job_id = first.schedule_workflow("wf-cancelled", **_date_config(0.3))
    first.remove_schedule(job_id)
    first.shutdown()

    second = _make_scheduler(db_path, monkeypatch)
    try:
        await asyncio.sleep(0.7)
        assert FIRED == [], "cancelled job fired after scheduler restart"
        assert second.scheduler.get_job(job_id) is None
    finally:
        second.shutdown()


@pytest.mark.asyncio
async def test_fired_once_schedule_does_not_duplicate_after_restart(
        tmp_path, monkeypatch):
    db_path = tmp_path / "fired-jobs.db"
    first = _make_scheduler(db_path, monkeypatch)
    first.schedule_workflow("wf-once", **_date_config(0.1))
    await asyncio.sleep(0.6)
    assert FIRED == ["wf-once"], "one-shot job did not fire exactly once"
    first.shutdown()

    second = _make_scheduler(db_path, monkeypatch)
    try:
        await asyncio.sleep(0.6)
        assert FIRED == ["wf-once"], (
            "fired one-shot job re-fired after scheduler restart")
    finally:
        second.shutdown()
