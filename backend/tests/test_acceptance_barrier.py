"""Tests for core/acceptance_barrier.py — the test-only synchronization
barrier that holds a worker between two real steps.

The three properties that matter, and that this file exists to pin:

* **Inert by default.** With no ``ATOM_ACCEPTANCE_BARRIER`` the barrier is not
  even importable-armed: the module-level ``ARMED`` is False, both entry
  points return immediately, no directory is created, no file appears, and the
  event loop is never held. A seam that costs a production turn anything in
  the default configuration is not a test seam.
* **Refuses outside an isolated acceptance world.** Arming the variable
  against a database that is not a disposable world copy must be a loud
  refusal and NO barrier, not an exception and not a silent hold — the
  product's behaviour has to be exactly what it would have been.
* **Arms and releases correctly.** Armed inside a world, the caller signals
  arrival (a file the harness can read, carrying the pid) and then blocks
  until a release file appears, and returns ``True`` only if it really
  blocked.

Every test points ``DATABASE_URL`` at a tmp tree under ``acceptance_worlds``
and also fixes ``core.database.DATABASE_URL`` to the same value, because the
barrier requires the engine's URL and the environment's to AGREE. Nothing
here can touch a real world or a real database.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from core import acceptance_barrier as B

STAGE = B.STAGE_CONTINUATION_AFTER_EFFECT


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _world_db(tmp_path: Path, monkeypatch, *, stage: str | None = None,
              match: str = "", timeout: str = "") -> Path:
    """An `acceptance_worlds`-shaped database the barrier is allowed to arm on.

    The tmp path deliberately contains the same `acceptance_worlds` fragment a
    real world has, because that fragment IS the confinement test.
    """
    db_dir = tmp_path / "backend" / "data" / "acceptance_worlds" / "w" / \
        "runs" / "run-1" / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db = db_dir / "atom.db"
    db.write_text("")
    url = f"sqlite:///{db}"
    monkeypatch.setenv("DATABASE_URL", url)
    # The engine's own view must agree, or the barrier refuses by design.
    import core.database as database_module

    monkeypatch.setattr(database_module, "DATABASE_URL", url, raising=False)
    monkeypatch.setenv(B.ENV_STAGE, stage if stage is not None else "")
    if match:
        monkeypatch.setenv(B.ENV_MATCH, match)
    else:
        monkeypatch.delenv(B.ENV_MATCH, raising=False)
    monkeypatch.delenv(B.ENV_DIR, raising=False)
    if timeout:
        monkeypatch.setenv(B.ENV_TIMEOUT, timeout)
    else:
        monkeypatch.delenv(B.ENV_TIMEOUT, raising=False)
    return db


def _arm(monkeypatch, db: Path, stage: str = STAGE) -> None:
    """Re-evaluate the import-time switch the way a process launch would."""
    monkeypatch.setattr(B, "ARMED", bool(os.environ.get(B.ENV_STAGE)))


def _barrier_dir(db: Path) -> Path:
    return db.parent / "acceptance_barrier"


# ---------------------------------------------------------------------------
# 1. inert by default
# ---------------------------------------------------------------------------
def test_unset_variable_leaves_the_barrier_disarmed(monkeypatch, tmp_path):
    db = _world_db(tmp_path, monkeypatch, stage="")
    _arm(monkeypatch, db)
    assert B.ARMED is False


def test_inert_by_default_writes_nothing_and_returns_immediately(
        monkeypatch, tmp_path):
    """No env var => one dict lookup, no file, no hold, no work skipped."""
    db = _world_db(tmp_path, monkeypatch, stage="")
    _arm(monkeypatch, db)
    before = time.monotonic()
    held = B.block(STAGE, {"session_id": "s1"})
    assert held is False
    assert time.monotonic() - before < 0.05
    assert not _barrier_dir(db).exists(), "an inert barrier must create nothing"


def test_inert_by_default_never_holds_the_event_loop(monkeypatch, tmp_path):
    """The async entry point with no arming must not even yield."""
    db = _world_db(tmp_path, monkeypatch, stage="")
    _arm(monkeypatch, db)

    async def _go() -> bool:
        return await B.await_barrier(STAGE, {"session_id": "s1"})

    assert asyncio.run(_go()) is False
    assert not _barrier_dir(db).exists()


def test_arming_a_different_stage_does_not_arm_this_one(monkeypatch, tmp_path):
    """A stage is a name, not a switch: arming one must not hold another."""
    db = _world_db(tmp_path, monkeypatch, stage="some_other_stage")
    _arm(monkeypatch, db)
    assert B.stage_armed("some_other_stage") is True
    assert B.stage_armed(STAGE) is False
    assert B.block(STAGE, {"session_id": "s1"}) is False
    assert not _barrier_dir(db).exists()


def test_session_narrowing_can_only_fire_less_often(monkeypatch, tmp_path):
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, match="s-good")
    _arm(monkeypatch, db)
    assert B.matches_turn({"session_id": "s-good"}) is True
    assert B.matches_turn({"session_id": "s-other"}) is False
    assert B.matches_turn({}) is False
    assert B.block(STAGE, {"session_id": "s-other"}) is False
    assert not _barrier_dir(db).exists()


# ---------------------------------------------------------------------------
# 2. refuses outside an isolated acceptance world
# ---------------------------------------------------------------------------
def test_refuses_when_the_database_is_not_a_world(monkeypatch, tmp_path,
                                                  caplog):
    """The production shape: an armed variable on a real database is refused."""
    db = tmp_path / "data" / "atom.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text("")
    url = f"sqlite:///{db}"
    monkeypatch.setenv("DATABASE_URL", url)
    import core.database as database_module

    monkeypatch.setattr(database_module, "DATABASE_URL", url, raising=False)
    monkeypatch.setenv(B.ENV_STAGE, STAGE)
    _arm(monkeypatch, db)

    with caplog.at_level("ERROR"):
        assert B.block(STAGE, {"session_id": "s1"}) is False
    assert "ACCEPTANCE BARRIER REFUSED" in caplog.text
    assert not (db.parent / "acceptance_barrier").exists()


def test_refuses_when_the_engine_and_the_environment_disagree(
        monkeypatch, tmp_path, caplog):
    """A DATABASE_URL the engine did not open is exactly the dangerous case:
    writes would land somewhere other than what the env claims."""
    world = _world_db(tmp_path, monkeypatch, stage=STAGE)
    import core.database as database_module

    other = tmp_path / "elsewhere" / "atom.db"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("")
    monkeypatch.setattr(database_module, "DATABASE_URL",
                        f"sqlite:///{other}", raising=False)
    _arm(monkeypatch, world)

    with caplog.at_level("ERROR"):
        assert B.block(STAGE, {"session_id": "s1"}) is False
    assert "ACCEPTANCE BARRIER REFUSED" in caplog.text


def test_refuses_a_non_sqlite_database(monkeypatch, tmp_path, caplog):
    """A Postgres deployment is not a disposable world; guessing at a host
    string to arm a barrier would be a way to stop a real turn."""
    url = "postgresql://user:pw@db.internal:5432/atom"
    monkeypatch.setenv("DATABASE_URL", url)
    import core.database as database_module

    monkeypatch.setattr(database_module, "DATABASE_URL", url, raising=False)
    monkeypatch.setenv(B.ENV_STAGE, STAGE)
    _arm(monkeypatch, tmp_path / "x")

    with caplog.at_level("ERROR"):
        assert B.resolve_barrier_dir() is None
    assert "ACCEPTANCE BARRIER REFUSED" in caplog.text


def test_refuses_when_no_database_url_is_visible(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import core.database as database_module

    monkeypatch.setattr(database_module, "DATABASE_URL", "", raising=False)
    monkeypatch.setenv(B.ENV_STAGE, STAGE)
    _arm(monkeypatch, tmp_path / "x")

    with caplog.at_level("ERROR"):
        assert B.resolve_barrier_dir() is None
    assert "ACCEPTANCE BARRIER REFUSED" in caplog.text


def test_refuses_a_barrier_directory_outside_the_world(monkeypatch, tmp_path,
                                                       caplog):
    db = _world_db(tmp_path, monkeypatch, stage=STAGE)
    monkeypatch.setenv(B.ENV_DIR, str(tmp_path / "not-the-world"))
    _arm(monkeypatch, db)

    with caplog.at_level("ERROR"):
        assert B.block(STAGE, {"session_id": "s1"}) is False
    assert "ACCEPTANCE BARRIER REFUSED" in caplog.text
    assert not (tmp_path / "not-the-world").exists()


# ---------------------------------------------------------------------------
# 3. arms and releases correctly
# ---------------------------------------------------------------------------
def test_armed_inside_a_world_signals_arrival_and_blocks_until_released(
        monkeypatch, tmp_path):
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, timeout="30")
    _arm(monkeypatch, db)
    directory = _barrier_dir(db)

    observed: dict = {}

    def _watch() -> None:
        # The harness's side of the contract: WAIT FOR THE ARRIVAL FILE (not
        # for a database row), then read the pid out of it, then release.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            arrivals = B.arrived_paths(directory, STAGE)
            if arrivals:
                observed.update(json.loads(arrivals[0].read_text()))
                (directory / f"barrier.{STAGE}.release").write_text("go")
                return
            time.sleep(0.01)
        observed["timeout"] = True

    import threading

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    started = time.monotonic()
    held = B.block(STAGE, {"session_id": "s1", "continuation_id": "c1"})
    watcher.join(timeout=10)
    waited = time.monotonic() - started

    assert held is True
    assert waited > 0.0
    assert observed.get("pid") == os.getpid()
    assert observed.get("stage") == STAGE
    assert (observed.get("context") or {}).get("continuation_id") == "c1"
    events = (directory / f"barrier.{STAGE}.events.log").read_text()
    assert "arrived" in events and "released" in events


def test_armed_async_barrier_blocks_and_releases(monkeypatch, tmp_path):
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, timeout="30")
    _arm(monkeypatch, db)
    directory = _barrier_dir(db)

    async def _go() -> bool:
        return await B.await_barrier(STAGE, {"session_id": "s1"})

    async def _release_when_arrived() -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if B.arrived_paths(directory, STAGE):
                (directory / f"barrier.{STAGE}.release").write_text("go")
                return
            await asyncio.sleep(0.01)

    async def _both() -> bool:
        await asyncio.gather(_release_when_arrived(), _go())
        return True

    assert asyncio.run(_both()) is True
    assert (directory / f"barrier.{STAGE}.arrived.{os.getpid()}.json").exists()


def test_a_missing_release_times_out_and_the_work_continues(
        monkeypatch, tmp_path, caplog):
    """A test seam must not be able to wedge a worker forever: the hold ends
    and the caller proceeds exactly as if no barrier existed."""
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, timeout="0.2")
    _arm(monkeypatch, db)

    with caplog.at_level("ERROR"):
        started = time.monotonic()
        assert B.block(STAGE, {"session_id": "s1"}) is False
        waited = time.monotonic() - started
    assert "ACCEPTANCE BARRIER TIMED OUT" in caplog.text
    # The requested bound is the one that applies (a floor that silently
    # rounded a 200 ms hold up to a second would make the seam untunable).
    assert 0.2 <= waited < 2.0, waited


def test_a_non_positive_timeout_falls_back_to_the_default(monkeypatch, tmp_path):
    """A test seam must not be able to disable its own bound."""
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, timeout="0")
    _arm(monkeypatch, db)
    assert B._timeout_seconds() == B.DEFAULT_TIMEOUT_SECONDS
    assert B._timeout_seconds.__doc__ is not None


def test_arming_all_fires_any_stage(monkeypatch, tmp_path):
    db = _world_db(tmp_path, monkeypatch, stage="all", timeout="0.05")
    _arm(monkeypatch, db)
    assert B.stage_armed(STAGE) is True
    assert B.stage_armed(B.STAGE_CHAT_TURN_AFTER_CLAIM) is True
    # The hold is bounded here, so it ends as a timeout -- what proves the
    # stage FIRED is the arrival marker, not the return value.
    B.block(STAGE, {"session_id": "s1"})
    arrivals = B.arrived_paths(_barrier_dir(db), STAGE)
    assert len(arrivals) == 1, arrivals
    assert arrivals[0].name == f"barrier.{STAGE}.arrived.{os.getpid()}.json"


def test_barrier_touches_no_database(monkeypatch, tmp_path):
    """The barrier's entire effect on the world is its own two files: it opens
    no session and writes no row, so it cannot fabricate or destroy state."""
    db = _world_db(tmp_path, monkeypatch, stage=STAGE, timeout="0.05")
    _arm(monkeypatch, db)
    before = db.read_bytes()
    B.block(STAGE, {"session_id": "s1"})
    assert db.read_bytes() == before
    names = sorted(p.name for p in _barrier_dir(db).iterdir())
    assert all(n.startswith(f"barrier.{STAGE}.") for n in names), names
