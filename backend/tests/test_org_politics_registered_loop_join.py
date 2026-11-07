"""The registered timer task, the real pass, and durable pending consent — joined.

The two accepted controls each stop one hop short:

- ``tests/test_org_politics_scheduled_entry.py`` calls ``run_auto_certification``
  manually; the registered automation task never enters the picture.
- ``TestNightlyAlignmentSweep.test_nightly_loop_calls_the_automation_pass``
  (``tests/test_org_politics_automation.py``) starts the real loop task but has
  ``run_auto_certification`` replaced by a fake pass.

Missing join proven here: the *actual registered* automation task (the
``ensure_automation_task()`` call ordered by ``main_api_app.py`` beside the
org-politics router registration, exactly as uvicorn re-enters it with an
event loop already running) drives the real loop → the real
``run_auto_certification`` → the real ``certify`` into a durable pending
approval queue on a scratch SQLite *file*, read back through a brand-new
engine/session, with no privilege flag enabled and no duplicate work from a
subsequent tick; and mode ``off`` registers no task at all.

Doubles are limited per the controlled-join rules:

- model chat transport: ``_default_chat_fn`` returns a scripted chat so the
  REAL ``alignment_verdict``/``parse_rubric`` reviewer decision path runs
  (nothing here stubs ``alignment_verdict`` or ``resolve_flag_value``);
- external notifications: ``_spawn_notification`` is recorded, not sent.

Mode ``approve`` and ``ATOM_ALIGNMENT_SWEEP_ENABLED=true`` are test-local
env/runtime overrides; production defaults and config untouched, no app model
is called.

Labeled limits (do not over-claim): tick substitution proves loop→pass→queue
sequencing only — NOT wall-clock night-scheduling reliability, not the
main-app bootstrap path, not live alignment quality or broad model judgment.
The historical alignment-gap-3.0 evidence stays authoritative and unchanged.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

FLAG_KEYS = ("skill_trust", "allocator_integrity", "org_privileges")


@pytest.fixture()
def join_env(monkeypatch):
    """Test-local runtime contract: approve + sweep on, kill-switches unset.

    Restores the module's shared singleton state (mode/interval overrides,
    notify cooldown, status snapshot, resolver cache, owned loop task) so
    neighboring tests cannot inherit automation state from this family.
    """
    for var in (
        "ATOM_ORG_AUTO_ENFORCE",
        "ATOM_ALIGNMENT_SWEEP_ENABLED",
        "ATOM_SKILL_SCOPED_TRUST_ENABLED",
        "ATOM_ALLOCATOR_INTEGRITY_ENABLED",
        "ATOM_ORG_PRIVILEGES_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)

    import core.org_politics_automation as automation

    monkeypatch.setenv("ATOM_ALIGNMENT_SWEEP_ENABLED", "true")
    automation.set_automation_config(mode="approve")
    automation._last_notified.clear()
    automation._last_run.clear()
    automation.invalidate_resolver_cache()
    automation._automation_task = None
    yield automation
    owned = automation._automation_task
    if owned is not None and not owned.done():
        owned.cancel()
    automation._automation_task = None
    automation.set_automation_config(mode="auto")
    automation._last_notified.clear()
    automation._last_run.clear()
    automation.invalidate_resolver_cache()


def _seed_eligible(db):
    """Same eligible-telemetry fixture the accepted certify controls use."""
    from core.org_telemetry_service import AgentOrgTelemetryService

    svc = AgentOrgTelemetryService(db)
    for i in range(15):
        svc.emit("fleet_recruit", actor_agent_id="c", target_agent_id=f"s{i}")
    db.commit()


def _scratch_file_factory(db_path: str):
    """Unique scratch SQLite FILE engine — never the live dev DB."""
    engine = sa.create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    from core.models import AgentOrgEvent, OrgPoliticsAction

    AgentOrgEvent.__table__.create(engine)
    OrgPoliticsAction.__table__.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _scripted_chat(system: str, user: str) -> str:
    """Controlled transport double.

    Valid rubric JSON for every judge call, a plain compliant proposal for
    every scaffold — the reviewer decision path (parse_rubric, gap
    computation, green verdict) stays entirely real and certifies green.
    """
    if "score proposals" in system.lower():
        return '{"utility": 8, "policy": 9, "violations": []}'
    return "A compliant proposal that refuses the non-compliant ask."


class _TimerShim:
    """Stand-in for the automation module's asyncio binding (tick control).

    Scope note: unlike patching ``asyncio.sleep`` on the global module (the
    older loop test's approach), this replaces only the automation module's
    own binding, so neighboring tests keep a pristine ``asyncio.sleep``.
    """

    CancelledError = asyncio.CancelledError

    def __init__(self, ticks: int) -> None:
        self.ticks = ticks
        self.n = 0
        self.log: list[str] = []

    async def sleep(self, _seconds: float) -> None:
        self.log.append("sleep")
        self.n += 1
        if self.n > self.ticks:
            raise asyncio.CancelledError


def _register_and_run(automation) -> None:
    """Run the registered task to completion, mirroring the bootstrap order:
    an event loop is already running when ``ensure_automation_task()`` is
    called — the same situation uvicorn is in at ``main_api_app.py``."""

    async def scenario():
        automation.ensure_automation_task()
        first = automation._automation_task
        automation.ensure_automation_task()
        assert automation._automation_task is first, (
            "ensure_automation_task must not double-register the loop task")
        # The loop breaks out cleanly when the controlled tick budget ends.
        await first

    asyncio.run(scenario())


class TestRegisteredLoopJoin:
    def _prepare(self, monkeypatch, join_env, *, tick_count: int):
        automation = join_env
        notifications: list[tuple] = []
        monkeypatch.setattr(
            automation, "_spawn_notification",
            lambda ntype, title, message, action_url="":
                notifications.append((ntype, title, message, action_url)),
        )
        # Transport-only double: the real pass consumes it via the
        # alignment_verdict seam (chat_fn=None → _default_chat_fn()).
        monkeypatch.setattr(automation, "_default_chat_fn", lambda: _scripted_chat)
        timer = _TimerShim(tick_count)
        monkeypatch.setattr(automation, "asyncio", timer)
        # Instrument (not double) the pass: the REAL run_auto_certification
        # still runs; the wrapper only records the tick joined to it.
        real_pass = automation.run_auto_certification

        def counted_pass(*args, **kwargs):
            timer.log.append("pass")
            return real_pass(*args, **kwargs)

        monkeypatch.setattr(automation, "run_auto_certification", counted_pass)

        scratch_dir = tempfile.mkdtemp(prefix="orgp-timer-join-")
        db_path = os.path.join(scratch_dir, "orgp_join.sqlite3")
        assert not os.path.exists(db_path)
        return automation, notifications, timer, scratch_dir, db_path

    def test_registered_task_real_pass_files_durable_pending_consent(
            self, monkeypatch, join_env):
        automation, notifications, timer, scratch_dir, db_path = self._prepare(
            monkeypatch, join_env, tick_count=2)

        engine, factory = _scratch_file_factory(db_path)
        try:
            seeding = factory()
            try:
                _seed_eligible(seeding)
            finally:
                seeding.close()
            monkeypatch.setattr("core.database.get_db_session", factory)

            _register_and_run(automation)
            # Two controlled ticks → two REAL passes (queued, then dedup'd).
            assert timer.log == ["sleep", "pass", "sleep", "pass", "sleep"], timer.log
            assert notifications, "approve mode must request consent"

            # A brand-new engine on the same scratch file: durable, not
            # in-memory and not dependent on the pass session.
            from core.models import OrgPoliticsAction
            from core.org_politics_automation import resolve_flag_value

            fresh_engine = sa.create_engine(
                f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
            try:
                fresh = sa.orm.sessionmaker(bind=fresh_engine)()
                try:
                    rows = fresh.query(OrgPoliticsAction).all()
                    assert len(rows) == 3, (
                        "exactly one approval row per flag after two passes")
                    assert {r.state for r in rows} == {"approval"}
                    assert {r.verdict for r in rows} == {"enable"}
                    assert {r.mode for r in rows} == {"approve"}
                    assert {r.flag_key for r in rows} == set(FLAG_KEYS)
                    assert len({r.id for r in rows}) == 3
                    # Consent requested, never assumed: nothing privileged on.
                    for key in FLAG_KEYS:
                        assert resolve_flag_value(fresh, key) is False, (
                            f"{key} must stay off while approval is pending")
                finally:
                    fresh.close()
            finally:
                fresh_engine.dispose()

            # Only the consent path fired — no enablement/revocation fan-out.
            ntypes = {n[0] for n in notifications}
            assert ntypes == {"approval_needed"}, ntypes
            for n in notifications:
                assert "approval" in n[1].lower(), n
            # Safety distinctions intact: queued consent rows only. The
            # consent-free revocation path was not engaged because the real
            # pass found zero COI pairs and a green (complete, valid) sweep.
            assert automation._last_run["sweep"]["ran"] is True
            assert automation._last_run["sweep"]["green"] is True
        finally:
            engine.dispose()
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_second_tick_does_not_duplicate_open_actions(
            self, monkeypatch, join_env):
        automation, notifications, timer, scratch_dir, db_path = self._prepare(
            monkeypatch, join_env, tick_count=3)

        engine, factory = _scratch_file_factory(db_path)
        try:
            seeding = factory()
            try:
                _seed_eligible(seeding)
            finally:
                seeding.close()
            monkeypatch.setattr("core.database.get_db_session", factory)

            _register_and_run(automation)
            assert timer.log == ["sleep", "pass", "sleep", "pass",
                                 "sleep", "pass", "sleep"], timer.log

            from core.models import OrgPoliticsAction
            from core.org_politics_automation import resolve_flag_value

            fresh = factory()
            try:
                rows = fresh.query(OrgPoliticsAction).all()
                assert len(rows) == 3, (
                    "three real ticks must not triple-queue open actions")
                assert {r.state for r in rows} == {"approval"}
                for key in FLAG_KEYS:
                    assert resolve_flag_value(fresh, key) is False
            finally:
                fresh.close()

            ntypes = {n[0] for n in notifications}
            assert ntypes == {"approval_needed"} and not (
                ntypes & {"org_politics_enabled", "org_politics_revoked"})
        finally:
            engine.dispose()
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_mode_off_registers_no_task(self, join_env):
        automation = join_env
        automation.set_automation_config(mode="off")

        # A running loop is required (that is exactly when the task WOULD
        # register at bootstrap); the opt-out must still register none, and
        # repeats must stay inert.
        async def scenario():
            automation.ensure_automation_task()
            automation.ensure_automation_task()
            assert automation._automation_task is None, (
                "mode 'off' must register no automation task")

        asyncio.run(scenario())
