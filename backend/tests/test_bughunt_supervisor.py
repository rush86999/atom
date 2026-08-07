"""TDD bug-hunt: AutonomousSupervisorService monitor loop configurability.

`monitor_execution` hardcodes ``poll_interval=2`` and
``max_duration_seconds=30*60`` — tests exercising "running" executions (or
missing mocks) spin for a full 30 minutes per test, which hung every full
suite run. The service must accept these as constructor params (prod defaults
unchanged) and honor them.
"""
from __future__ import annotations

import asyncio
import time

import pytest
from unittest.mock import MagicMock

from core.autonomous_supervisor_service import AutonomousSupervisorService


def test_constructor_accepts_poll_and_duration_config():
    service = AutonomousSupervisorService(
        db=MagicMock(), poll_interval=0.01, max_duration_seconds=1
    )
    assert service.poll_interval == 0.01
    assert service.max_duration_seconds == 1


@pytest.mark.asyncio
async def test_monitor_loop_terminates_within_configured_duration():
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = None
    db.query.return_value = query

    service = AutonomousSupervisorService(db=db, poll_interval=0.01, max_duration_seconds=1)

    supervisor = MagicMock()
    supervisor.id = "auto-001"

    start = time.monotonic()
    events = []
    async for event in service.monitor_execution("exec-1", supervisor):
        events.append(event)
        if event.event_type == "error":
            break
    elapsed = time.monotonic() - start

    assert elapsed < 30, "monitor loop must terminate within configured max duration"
    assert any(e.event_type == "error" for e in events)


@pytest.mark.asyncio
async def test_monitor_loop_detects_completed_with_fast_poll():
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    executions = iter(
        [
            MagicMock(status="running", id="exec-1"),
            MagicMock(status="completed", id="exec-1", duration_seconds=1.0, output_summary="ok"),
        ]
    )
    query.first.side_effect = lambda: next(executions)
    db.query.return_value = query

    service = AutonomousSupervisorService(db=db, poll_interval=0.01, max_duration_seconds=5)

    supervisor = MagicMock()
    supervisor.id = "auto-001"

    start = time.monotonic()
    events = []
    async for event in service.monitor_execution("exec-1", supervisor):
        events.append(event)
        if event.event_type == "execution_completed":
            break
    elapsed = time.monotonic() - start

    assert elapsed < 30
    assert any(e.event_type == "execution_completed" for e in events)
