"""Probe: a directly recorded run must become qualification evidence.

This exercises the real recording path (GenericAgent._record_execution ->
AgentExecution + EpisodeService.create_episode_from_execution) against the
shared acceptance world (a scratch SQLite file), then asks the real
qualification picker (list_qualification_evidence_bundles) to surface that
work. Nothing about the evidence is seeded: the only episode/execution rows
are the ones the recording path itself creates.

The expected end state, which the picker's contract requires:

* the execution is ``completed`` and scoped to the run's workspace;
* the episode is ``completed`` and scoped to the same workspace;
* the picker returns exactly that episode, including the controlled output.

At the probed revision the episode was inserted without an explicit ``status``
and without a ``workspace_id``, so it landed as ``active``/unscoped and the
completed-only picker never saw it. The asserts below capture the intended
invariant rather than that symptom.

The negative control complements that: a waiting (non-terminal) run and a
failed (terminal but unsuccessful) execution must never be relabelled as
completed evidence just because they reached the writer. Completion is
derived from the durable execution lifecycle, not from the caller's
``success`` flag alone.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core import generic_agent as generic_agent_module
from core.agent_graduation_service import list_qualification_evidence_bundles
from core.generic_agent import GenericAgent
from core.models import AgentEpisode, AgentExecution, AgentRegistry
from tests.acceptance.fixtures import world  # noqa: F401 — fixture re-export

PROBE_TASK = (
    "PROBE_TASK_9f3c1a7e: produce the controlled direct-recording output"
)
PROBE_OUTPUT = (
    "PROBE_OUTPUT_9f3c1a7e: the recorded execution output must reach the "
    "graduation picker unchanged"
)
PROBE_EXECUTION_ID = "probe-execution-9f3c1a7e"


def test_direct_recording_reaches_qualification_picker(world, monkeypatch):
    # The world fixture registers agent-1 in ws-1/tenant-1. Put it at INTERN
    # so the student milestone notification path stays out of this probe; the
    # target is its next tier, SUPERVISED.
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    @contextmanager
    def _scratch_session():
        """Equivalent of core.database.get_db_session, bound to the world."""
        db = world.Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # _record_execution imports get_db_session by name, so patch it where it
    # was imported. Only the persistence path is redirected; the episode
    # service and picker are the real implementations.
    monkeypatch.setattr(
        generic_agent_module, "get_db_session", _scratch_session)

    agent = GenericAgent.__new__(GenericAgent)
    agent.id = world.agent_id
    agent.name = "Agent One"
    agent.workspace_id = world.workspace_id
    agent.tenant_id = world.tenant_id
    agent.config = {}
    # The world-model experience is a separate LanceDB-backed side channel;
    # stub it so the probe stays on the durable SQLite recording path.
    agent.world_model = SimpleNamespace(record_experience=AsyncMock())

    asyncio.run(agent._record_execution(
        PROBE_TASK,
        {
            "status": "objective_satisfied",
            "output": PROBE_OUTPUT,
            "steps": [],
            "complexity": "moderate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {"run_id": PROBE_EXECUTION_ID, "trigger": "probe"},
    ))

    # Always run the picker, even if the recording assertions below fail, so
    # the probe reports the full recording -> picker chain.
    with world.Session() as db:
        execution = db.get(AgentExecution, PROBE_EXECUTION_ID)
        episode = (
            db.query(AgentEpisode)
            .filter(AgentEpisode.execution_id == PROBE_EXECUTION_ID)
            .one_or_none()
        )
        scoped_agent = db.get(AgentRegistry, world.agent_id)
        bundles = list_qualification_evidence_bundles(
            db,
            scoped_agent,
            "SUPERVISED",
            world.tenant_id,
            world.workspace_id,
            limit=10,
        )

    assert execution is not None, (
        "the direct-recording path persisted no AgentExecution row"
    )
    assert execution.status == "completed", (
        "a successful direct run must persist the execution as completed, "
        f"got {execution.status!r}"
    )
    assert execution.workspace_id == world.workspace_id, (
        "the execution must carry the run's workspace, "
        f"got {execution.workspace_id!r}"
    )

    assert episode is not None, (
        "the direct-recording path created no AgentEpisode for the execution"
    )
    assert episode.status == "completed", (
        "the qualification picker only considers completed episodes; the "
        f"recorded episode landed as {episode.status!r}"
    )
    assert episode.workspace_id == world.workspace_id, (
        "the episode must be scoped to the same workspace as its execution "
        f"({world.workspace_id!r}), got {episode.workspace_id!r}"
    )
    assert episode.agent_id == world.agent_id

    items = bundles["items"]
    assert len(items) == 1, (
        "the picker must surface the one directly recorded episode, "
        f"got {len(items)} item(s): {items!r}"
    )
    bundle = items[0]
    assert bundle["episode_id"] == episode.id
    assert bundle["task_preview"] == PROBE_TASK
    assert bundle["output_preview"] == PROBE_OUTPUT

    evidence_refs = {(ref["kind"], ref["id"]) for ref in bundle["evidence_refs"]}
    assert ("agent_episode", episode.id) in evidence_refs
    assert ("agent_execution", PROBE_EXECUTION_ID) in evidence_refs


def test_non_terminal_or_failed_execution_is_not_completed_evidence(
    world, monkeypatch
):
    """Negative control: only a terminal successful run may say "completed".

    A waiting run never reaches the writer's success branch, and a failed run
    is terminal without being successful. Neither may be relabelled as
    completed qualification evidence by the caller's ``success`` flag.
    """
    from core.episode_service import EpisodeService

    @contextmanager
    def _scratch_session():
        db = world.Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(
        generic_agent_module, "get_db_session", _scratch_session)

    agent = GenericAgent.__new__(GenericAgent)
    agent.id = world.agent_id
    agent.name = "Agent One"
    agent.workspace_id = world.workspace_id
    agent.tenant_id = world.tenant_id
    agent.config = {}
    agent.world_model = SimpleNamespace(record_experience=AsyncMock())

    waiting_execution_id = "probe-waiting-9f3c1a7e"
    asyncio.run(agent._record_execution(
        PROBE_TASK,
        {
            "status": "waiting",
            "output": PROBE_OUTPUT,
            "steps": [],
            "complexity": "moderate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "wait_receipt": {"id": "probe-wait-9f3c1a7e"},
            "resume_state": {},
        },
        {"run_id": waiting_execution_id, "trigger": "probe"},
    ))

    with world.Session() as db:
        waiting_execution = db.get(AgentExecution, waiting_execution_id)
        waiting_recorded_episode = (
            db.query(AgentEpisode)
            .filter(AgentEpisode.execution_id == waiting_execution_id)
            .one_or_none()
        )

    assert waiting_execution is not None
    assert waiting_execution.status == "waiting"
    assert waiting_recorded_episode is None, (
        "the recording path must not mint an episode for a non-terminal run"
    )

    failed_execution_id = "probe-failed-9f3c1a7e"
    with world.Session() as db:
        db.add(AgentExecution(
            id=failed_execution_id,
            agent_id=world.agent_id,
            tenant_id=world.tenant_id,
            workspace_id=world.workspace_id,
            status="failed",
            input_summary=PROBE_TASK,
            output_summary=PROBE_OUTPUT,
            metadata_json={},
        ))
        db.commit()

    async def _write(execution_id, outcome, success):
        with world.Session() as db:
            return await EpisodeService(db).create_episode_from_execution(
                execution_id=execution_id,
                task_description=PROBE_TASK,
                outcome=outcome,
                success=success,
            )

    waiting_episode = asyncio.run(_write(
        waiting_execution_id, "waiting", False))
    failed_episode = asyncio.run(_write(
        failed_execution_id, "failure", False))

    assert waiting_episode.status == "active", (
        "a non-terminal execution must leave its episode active, "
        f"got {waiting_episode.status!r}"
    )
    assert failed_episode.status == "failed", (
        "a terminal failure must not be recorded as completed evidence, "
        f"got {failed_episode.status!r}"
    )
    assert waiting_episode.workspace_id == world.workspace_id
    assert failed_episode.workspace_id == world.workspace_id

    with world.Session() as db:
        scoped_agent = db.get(AgentRegistry, world.agent_id)
        bundles = list_qualification_evidence_bundles(
            db,
            scoped_agent,
            "SUPERVISED",
            world.tenant_id,
            world.workspace_id,
            limit=10,
        )
    assert bundles["items"] == [], (
        "non-completed episodes must never reach the qualification picker, "
        f"got {bundles['items']!r}"
    )
