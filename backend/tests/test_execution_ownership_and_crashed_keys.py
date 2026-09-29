"""Boot recovery must respect execution ownership, and a crashed key must resolve.

TWO PROPERTIES, ONE FILE, BOTH MEASURED ON REAL PROCESSES
==========================================================

1. THE SWEEP MUST NOT FAIL A LIVE WORKER'S EXECUTION.
   `reconcile_orphaned_executions` selects by status alone, so a second process
   opening the same database treats the first process's in-flight turn as a
   ghost and marks it failed underneath it. The turn keeps running and then tries
   to finalize into a row that now says it failed, and nothing reports the
   contradiction. Ownership is now recorded on insert and classified by
   liveness; a live owner means "hands off".

2. A KEYED REQUEST MUST NOT BE "IN PROGRESS" FOREVER.
   The transport deliberately holds `in_progress` on a crash rather than risk
   repeating a possibly-completed side effect, and told the client to mint a
   fresh id. That was fine while nothing ever resolved the key -- but the sweep
   now marks the execution failed, so the truth is known and an indefinite
   in-progress answer is not a policy, it is the absence of one. The key moves
   to a terminal `crashed` state, which is neither replayed nor re-executed.

NEGATIVE CONTROLS
Every liveness test spawns a real process and a real dead pid. The suite fails
if the "dead owner" case silently stops reconciling (a fix that skips
everything would pass the hands-off test and break recovery), and the live-owner
test uses a genuinely live pid rather than a fabricated owner block.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import chat_transport as ct  # noqa: E402
from core.execution_ownership import (  # noqa: E402
    HOSTNAME,
    PROCESS_TOKEN,
    owner_liveness,
    stamp_owner,
)
from core.models_registration import Base  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def sweep(db, monkeypatch):
    """Run the real sweep against the test database."""
    import core.database as database_module
    import core.execution_recovery as er

    monkeypatch.setattr(er, "SessionLocal", db)
    return er.reconcile_orphaned_executions


def _running_execution(factory, metadata):
    from core.models import AgentExecution

    session = factory()
    try:
        row = AgentExecution(id=str(uuid.uuid4()), status="running",
                             input_summary="x", triggered_by="chat",
                             metadata_json=metadata)
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _status(factory, execution_id):
    from core.models import AgentExecution

    session = factory()
    try:
        row = session.get(AgentExecution, execution_id)
        return (row.status, dict(row.metadata_json or {})) if row else (None, None)
    finally:
        session.close()


def _dead_pid() -> int:
    """A pid that is not running. Spawn-then-wait is the only portable way."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _live_process():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    return proc


# ------------------------------------------------------------------ ownership
def test_no_owner_is_UNKNOWN_not_guessed():
    for meta in (None, {}, {"owner": "not-a-dict"}, {"owner": {"host": HOSTNAME}},
                 {"owner": {"pid": "not-an-int"}}):
        state, info = owner_liveness(meta)
        assert state == "unknown", (meta, info)


def test_a_failed_liveness_inspection_is_unknown(monkeypatch):
    """An inspection that blows up is not a death certificate."""
    import core.execution_ownership as ownership
    meta = stamp_owner({})
    meta["owner"]["token"] = "other"

    def boom(pid, sig):
        raise OSError("inspection exploded")

    monkeypatch.setattr(ownership.os, "kill", boom)
    state, info = ownership.owner_liveness(meta)
    assert state == "unknown", info
    assert "inspection failed" in info["reason"]


def test_this_process_is_self():
    state, info = owner_liveness(stamp_owner({}))
    assert state == "self"
    assert info["pid"] == os.getpid()
    assert info["token"] == PROCESS_TOKEN


def test_a_dead_owner_is_dead():
    state, info = owner_liveness(
        {"owner": {"pid": _dead_pid(), "token": "x", "host": HOSTNAME}})
    assert state == "dead", info


def test_a_live_foreign_owner_is_live():
    proc = _live_process()
    try:
        state, info = owner_liveness(
            {"owner": {"pid": proc.pid, "token": "other", "host": HOSTNAME}})
        assert state == "live", info
        assert info["pid"] == proc.pid
    finally:
        proc.kill()
        proc.wait()


def test_a_live_pid_with_a_different_start_time_is_dead():
    """PID reuse: the number is alive, the process behind it is not ours."""
    proc = _live_process()
    try:
        state, info = owner_liveness({
            "owner": {"pid": proc.pid, "token": "other", "host": HOSTNAME,
                      "os_process_start": "ps:definitely-not-this-process"}})
        assert state == "dead", info
        assert "reused" in info["reason"]
    finally:
        proc.kill()
        proc.wait()


def test_a_remote_owner_is_UNKNOWN_not_dead():
    """A PID says nothing about another machine.

    Cross-host execution stays unsupported, and that is not a reason to declare
    the row crashed: the honest verdict is "cannot tell".
    """
    state, info = owner_liveness(
        {"owner": {"pid": os.getpid(), "token": "x", "host": "some-other-host"}})
    assert state == "unknown", info
    assert "another host" in info["reason"]


def test_stamp_owner_never_overwrites_an_existing_claim():
    original = {"owner": {"pid": 4242, "token": "theirs", "host": HOSTNAME}}
    assert stamp_owner(original)["owner"]["token"] == "theirs"
    # and it does not mutate the caller's dict
    assert original["session_id"] if "session_id" in original else True
    stamped = stamp_owner({"session_id": "s"})
    assert stamped["session_id"] == "s" and stamped["owner"]["pid"] == os.getpid()


# ------------------------------------------------------ the sweep, on a real DB
def test_sweep_leaves_a_live_workers_execution_alone(db, sweep):
    proc = _live_process()
    try:
        live_id = _running_execution(db, {
            "owner": {"pid": proc.pid, "token": "other", "host": HOSTNAME}})
        result = sweep()
        assert _status(db, live_id)[0] == "running", "a live worker's turn was failed"
        assert result["agent_untouched_live"] == 1
        assert result["agent_recovered"] == 0
    finally:
        proc.kill()
        proc.wait()


def test_sweep_still_reconciles_a_dead_owner(db, sweep):
    dead = _running_execution(db, {
        "owner": {"pid": _dead_pid(), "token": "gone", "host": HOSTNAME}})
    result = sweep()
    status, meta = _status(db, dead)
    assert status == "failed"
    assert meta["recovery"]["crashed"] is True
    assert meta["recovery"]["owner_state"] == "dead"
    assert result["agent_recovered"] == 1
    assert result["agent_untouched_live"] == 0


def test_sweep_does_NOT_reconcile_an_unstamped_row(db, sweep):
    """A missing stamp is not evidence of death.

    Every row already in every existing database predates the insert listener, so
    this is not hypothetical -- but "we cannot tell who owns this" must not
    become "it crashed". The row is left running and REPORTED. Written with raw
    SQL because the listener would otherwise stamp it and hide the case.
    """
    legacy = _running_execution(db, {"session_id": "s"})
    session = db()
    try:
        session.execute(
            text("UPDATE agent_executions SET metadata_json=:m WHERE id=:i"),
            {"m": json.dumps({"session_id": "s"}), "i": legacy})
        session.commit()
    finally:
        session.close()
    result = sweep()
    status, meta = _status(db, legacy)
    assert status == "running", "a row with no owner was declared crashed"
    assert "recovery" not in (meta or {})
    assert result["agent_recovered"] == 0
    assert result["agent_unknown_owner"] == 1
    assert "no owner recorded" in result["agent_unknown_detail"][0]["reason"]


def test_sweep_is_idempotent(db, sweep):
    dead = _running_execution(db, {"owner": {"pid": _dead_pid(), "token": "g",
                                             "host": HOSTNAME}})
    first = sweep()
    second = sweep()
    assert first["agent_recovered"] == 1
    assert second["agent_recovered"] == 0
    assert _status(db, dead)[0] == "failed"


def test_insert_listener_stamps_the_creating_process(db):
    from core.models import AgentExecution

    session = db()
    try:
        row = AgentExecution(status="running", triggered_by="chat")
        session.add(row)
        session.commit()
        owner = (row.metadata_json or {}).get("owner")
        assert owner, "an insert was not stamped with an owner"
        assert owner["pid"] == os.getpid()
        assert owner["token"] == PROCESS_TOKEN
        assert owner["host"] == HOSTNAME
    finally:
        session.close()


# ------------------------------------------------- the crashed keyed request
def _keyed_record(factory, execution_id, state=ct.IN_PROGRESS):
    from core.models import ChatRequestRecord

    session = factory()
    try:
        rec = ChatRequestRecord(tenant_id="t", user_id="u", session_id="s",
                                request_id="req-1", payload_sha256="d",
                                state=state, execution_id=execution_id)
        session.add(rec)
        session.commit()
        return rec.request_id
    finally:
        session.close()


def _state_of(factory, request_id="req-1"):
    from core.models import ChatRequestRecord

    session = factory()
    try:
        rec = (session.query(ChatRequestRecord)
               .filter(ChatRequestRecord.request_id == request_id).first())
        return (rec.state, rec.error) if rec else (None, None)
    finally:
        session.close()


def test_a_live_workers_execution_alone_check_can_actually_fail(db, sweep, monkeypatch):
    """Negative control for the test above, in the exact shape of the old code.

    With ownership information unavailable -- which is what the sweep saw before
    this change, and what it still sees for any writer whose metadata is not a
    dict -- the row is reconciled, i.e. a live worker's turn IS failed. That is
    the pre-fix behaviour, reproduced deliberately here, so the hands-off test
    cannot be passing because the sweep skips everything.
    """
    import core.execution_ownership as ownership

    monkeypatch.setattr(ownership, "owner_liveness",
                        lambda metadata: ("absent", {"forced": True}))
    proc = _live_process()
    try:
        live_id = _running_execution(db, {
            "owner": {"pid": proc.pid, "token": "other", "host": HOSTNAME}})
        result = sweep()
        assert _status(db, live_id)[0] == "failed"
        assert result["agent_untouched_live"] == 0
    finally:
        proc.kill()
        proc.wait()


def test_sweep_resolves_the_crashed_key_instead_of_leaving_it_in_progress(db, sweep):
    execution_id = _running_execution(db, {
        "owner": {"pid": _dead_pid(), "token": "gone", "host": HOSTNAME},
        # what the chat turn now records at claim time
        "request_id": "req-1"})
    _keyed_record(db, execution_id)
    result = sweep()
    state, error = _state_of(db)
    assert result["chat_requests_released"] == 1
    assert state == ct.CRASHED, "the key is still in progress, so a retry is told 'in progress' forever"
    assert "did not complete" in (error or "")


def test_a_crashed_execution_with_no_recorded_request_id_releases_nothing(db, sweep):
    """Attribution, not recency.

    The join is on the request id the turn recorded when it claimed the
    execution, because `ChatRequestRecord.execution_id` is NULL until
    finalization. Without that id there is no exact join, and resolving a key on
    a guess would tell a client its turn crashed when it may have completed
    under a different id -- so nothing is released.
    """
    execution_id = _running_execution(db, {
        "owner": {"pid": _dead_pid(), "token": "gone", "host": HOSTNAME}})
    _keyed_record(db, execution_id)
    result = sweep()
    assert result["chat_requests_released"] == 0
    assert _state_of(db)[0] == ct.IN_PROGRESS


def test_a_crashed_key_answers_crashed_not_in_progress(db):
    execution_id = _running_execution(db, {"session_id": "s"})
    _keyed_record(db, execution_id, state=ct.CRASHED)
    session = db()
    try:
        action, _rec = ct.check(session, tenant_id="t", user_id="u", session_id="s",
                                request_id="req-1", digest="d", payload_text="{}")
    finally:
        session.close()
    assert action == "crashed"


def test_a_crashed_key_is_not_replayed_even_with_an_identical_payload(db):
    """A crash is not a completion: same payload must still not replay."""
    execution_id = _running_execution(db, {"session_id": "s"})
    _keyed_record(db, execution_id, state=ct.CRASHED)
    session = db()
    try:
        action, _rec = ct.check(session, tenant_id="t", user_id="u", session_id="s",
                                request_id="req-1", digest="d", payload_text="{}")
    finally:
        session.close()
    assert action == "crashed"
    assert action != "replay"


def test_a_live_workers_key_is_untouched(db, sweep):
    proc = _live_process()
    try:
        execution_id = _running_execution(db, {
            "owner": {"pid": proc.pid, "token": "other", "host": HOSTNAME},
            "request_id": "req-1"})
        _keyed_record(db, execution_id)
        result = sweep()
        assert result["chat_requests_released"] == 0
        assert _state_of(db)[0] == ct.IN_PROGRESS, "a live turn's key was resolved"
    finally:
        proc.kill()
        proc.wait()


def test_a_completed_key_is_never_reclassified_as_crashed(db, sweep):
    """Only in-progress keys are released; a delivered answer must survive."""
    execution_id = _running_execution(db, {
        "owner": {"pid": _dead_pid(), "token": "gone", "host": HOSTNAME},
        "request_id": "req-1"})
    _keyed_record(db, execution_id, state=ct.COMPLETED)
    sweep()
    assert _state_of(db)[0] == ct.COMPLETED


# --------------------------------------------------------------------------
# THE NEGATIVE TESTS: unknown ownership must be inert
# --------------------------------------------------------------------------
# Each of the three ways ownership can fail to be established -- a missing
# stamp, an owner on another host, a liveness inspection that failed -- must
# leave the row running, leave its key in progress, and above all must not allow
# a second execution of the same turn. Parametrised so a future edit that
# reintroduces reconciliation for one of the three is caught per-case rather
# than in aggregate.
UNKNOWN_CASES = {
    "missing_stamp": {},
    "other_host": {"owner": {"pid": 424242, "token": "x", "host": "some-other-host"}},
    "inspection_failed": {"owner": {"pid": 424242, "token": "x", "host": HOSTNAME,
                                    "os_process_start": None}},
}


@pytest.mark.parametrize("case", sorted(UNKNOWN_CASES))
def test_unknown_ownership_cannot_terminate_an_execution(db, sweep, case, monkeypatch):
    if case == "inspection_failed":
        import core.execution_ownership as ownership

        def boom(pid, sig):
            raise OSError("inspection exploded")

        monkeypatch.setattr(ownership.os, "kill", boom)
    metadata = dict(UNKNOWN_CASES[case])
    if case == "missing_stamp":
        execution_id = _running_execution(db, {"session_id": "s"})
        session = db()
        try:
            session.execute(
                text("UPDATE agent_executions SET metadata_json=:m WHERE id=:i"),
                {"m": json.dumps({"session_id": "s"}), "i": execution_id})
            session.commit()
        finally:
            session.close()
    else:
        execution_id = _running_execution(db, metadata)
    result = sweep()
    status, meta = _status(db, execution_id)
    assert status == "running", f"{case}: unknown ownership declared the row crashed"
    assert "recovery" not in (meta or {}), f"{case}: a recovery marker was written"
    assert result["agent_recovered"] == 0, case
    assert result["agent_unknown_owner"] == 1, case


@pytest.mark.parametrize("case", sorted(UNKNOWN_CASES))
def test_unknown_ownership_cannot_release_the_request_key(db, sweep, case, monkeypatch):
    if case == "inspection_failed":
        import core.execution_ownership as ownership

        def boom(pid, sig):
            raise OSError("inspection exploded")

        monkeypatch.setattr(ownership.os, "kill", boom)
    execution_id = _running_execution(db, {
        "request_id": "req-1", **UNKNOWN_CASES[case]})
    if case == "missing_stamp":
        session = db()
        try:
            session.execute(
                text("UPDATE agent_executions SET metadata_json=:m WHERE id=:i"),
                {"m": json.dumps({"request_id": "req-1"}), "i": execution_id})
            session.commit()
        finally:
            session.close()
    _keyed_record(db, execution_id)
    result = sweep()
    assert result["chat_requests_released"] == 0, case
    assert _state_of(db)[0] == ct.IN_PROGRESS, (
        f"{case}: the key was released without a verified dead owner")


@pytest.mark.parametrize("case", sorted(UNKNOWN_CASES))
def test_unknown_ownership_cannot_permit_duplicate_work(db, sweep, case, monkeypatch):
    """The point of not releasing: the turn is still claimed, so a retry of the
    same identity cannot start a second execution."""
    if case == "inspection_failed":
        import core.execution_ownership as ownership

        def boom(pid, sig):
            raise OSError("inspection exploded")

        monkeypatch.setattr(ownership.os, "kill", boom)
    execution_id = _running_execution(db, {
        "request_id": "req-1", **UNKNOWN_CASES[case]})
    if case == "missing_stamp":
        session = db()
        try:
            session.execute(
                text("UPDATE agent_executions SET metadata_json=:m WHERE id=:i"),
                {"m": json.dumps({"request_id": "req-1"}), "i": execution_id})
            session.commit()
        finally:
            session.close()
    _keyed_record(db, execution_id)
    sweep()
    session = db()
    try:
        action, _rec = ct.check(session, tenant_id="t", user_id="u", session_id="s",
                                request_id="req-1", digest="d", payload_text="{}")
    finally:
        session.close()
    assert action == "in_progress", (
        f"{case}: a retry could start a SECOND execution of the same turn")
    assert _status(db, execution_id)[0] == "running"
