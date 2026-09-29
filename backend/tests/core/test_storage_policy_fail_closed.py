# -*- coding: utf-8 -*-
"""Defects 2-5: activity inspection fails CLOSED, the default fixture is
genuinely small, and deletion is inventory-only behind the interlock AND a
reviewed inventory.

Scope and safety
----------------
Every test runs against a TINY scratch tree under pytest's ``tmp_path`` with
``TESTING=1`` (forced by ``tests/conftest.py``). No test:

* creates, seeds, launches, refreshes or tears down an acceptance world;
* reads or writes ``backend/data/acceptance_worlds``;
* opens ``backend/data/atom.db`` — the live DB is *stat*ed in one measurement
  test and never opened;
* takes the real maintenance interlock, writes to ``backend/config``, or
  touches a port. The interlock is a probe lambda or a monkeypatched
  ``storage_policy.interlock_state``.

Determinism
-----------
* Disk shortage is INJECTED (``check_space(free_bytes=...)`` /
  ``_check_disk_before_world(free_bytes=...)``). No test asserts against real
  free space and no disk is ever filled.
* Inspection failure is INJECTED (a probe that raises, a ``chmod 000``
  manifest, a monkeypatched ``read_text``), never raced against a clock.
* Deletion is observed through an injected ``remove`` callable, so the tests
  assert that nothing was *passed* for removal without deleting anything real.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import storage_policy as SP  # noqa: E402

MB = SP.MB

#: Recorded here so the test that checks the ceiling does not have to trust a
#: comment. Measured 2026-09-28 on this box with ``os.stat`` (the live DB is
#: never opened):
#:   live dev DB        backend/data/atom.db                     413,360,128 B
#:   the OLD default    write_combined/fixture/atom.db          410,861,568 B
#:   run dirs           write_combined/runs/*/data/atom.db      ~409-411 MB each
#:   the NEW default    SP.provision_api_seeded_fixture(...)      8,478,720 B
#:       ... and 8,581,120 B after the app schema grew during this session,
#:       which is why the assertion below is a band and not an exact figure.
LIVE_DB_BYTES_MEASURED = 413_360_128
OLD_DEFAULT_FIXTURE_BYTES = 410_861_568
NEW_DEFAULT_FIXTURE_BYTES_MEASURED = 8_581_120
#: DDL grows as the app schema grows, so the recorded measurement is a band.
#: A 2x regression (back to copying the live file) still fails it.
NEW_DEFAULT_FIXTURE_BAND = (8_000_000, 10_000_000)


# ---------------------------------------------------------------------------
# helpers — a tiny world
# ---------------------------------------------------------------------------
def _run(world: Path, run_id: str, *, pid=777, age_days=30.0, db_bytes=4096,
         record=True, extra=None, run_live: bool = False) -> Path:
    """One scratch run directory.

    ``record=True`` (the default) writes the run's own launch record, which is
    where a pid lives — that record is the only positive evidence of
    ownership. ``pid=None`` writes it with NO pid, which is the shape of most
    real runs and must classify as review-required, not droppable.
    ``record=False`` writes no launch record at all.
    """
    run = world / "runs" / run_id
    (run / "data").mkdir(parents=True, exist_ok=True)
    (run / "data" / "atom.db").write_bytes(b"\0" * db_bytes)
    if record:
        body = {} if pid is None else {"pid": pid}
        if extra:
            body.update(extra)
        (run / "server_env.json").write_text(json.dumps(body))
    if run_live:
        (run / SP.RUN_LIVE_MARKER).write_text("live\n")
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(run, (t, t))
    return run


def _world(tmp_path: Path, name: str = "w", runs: int = 0, **kw) -> Path:
    w = tmp_path / "worlds" / name
    (w / "runs").mkdir(parents=True, exist_ok=True)
    for i in range(runs):
        _run(w, f"run-{i:012x}", age_days=30 - i, **kw)
    return w


def _never(pid):
    """A pid probe that says nothing is running (the test seam)."""
    return False


def _no_runners():
    return []


def _held_interlock():
    return True, "maintenance interlock held (injected)"


def _quiescent(world):
    return False, []


#: Sentinel: "use the real in-progress detector", so a test can say so
#: explicitly instead of getting the quiescent stub by accident.
REAL_STATE = object()


def _apply(inv, *, world, confirm=True, digest=None, interlock=None,
           remove=None, state=REAL_STATE):
    """apply_inventory with every gate injected, and deletion RECORDED.

    ``remove`` collects paths instead of deleting them, so a passing test can
    prove "zero deletions" without having deleted anything.
    """
    removed: list = []
    result = SP.apply_inventory(
        inv, confirm=confirm, world=world,
        reviewed_digest=inv.digest if digest is None else digest,
        interlock_probe=interlock or _held_interlock,
        state_probe=None if state is REAL_STATE else state,
        remove=removed.append if remove is None else remove)
    return result, removed


def _run_ids(world: Path):
    return sorted(p.name for p in (world / "runs").iterdir())


# ===========================================================================
# 2. Activity inspection fails CLOSED
# ===========================================================================
def test_pid_probe_that_raises_is_a_problem_not_an_answer(tmp_path):
    """A pid check that blows up must never read as "not running"."""
    world = _world(tmp_path, runs=1, pid=4242)

    def boom(pid):
        raise OSError("ps refused")

    insp = SP.inspect_activity(world, pid_alive=boom)
    assert not insp.complete
    assert any("pid probe raised" in p for p in insp.problems)
    assert insp.ownership["run-000000000000"] == SP.OWNER_UNKNOWN, \
        "an undecidable pid must leave ownership UNKNOWN, not idle"
    assert "run-000000000000" not in insp.active, \
        "unknown is not in-use: reporting it as active would mislabel why the " \
        "run survived"


def test_pid_probe_raising_refuses_apply_inventory_and_deletes_nothing(tmp_path):
    world = _world(tmp_path, runs=4, pid=4242)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                             pid_alive=lambda _p: False)
    assert inv.deletion_candidates(), "precondition: there is something to drop"

    def boom(pid):
        raise OSError("ps refused")

    inv2 = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                              pid_alive=boom)
    assert not inv2.complete
    result, removed = _apply(inv2, world=world)
    assert removed == [], "an incomplete inspection must delete nothing"
    assert result["deleted"] == []
    assert "REFUSED" in result["note"]
    assert "activity inspection incomplete" in result["refused"]
    assert _run_ids(world) == [f"run-{i:012x}" for i in range(4)]


def test_unreadable_run_manifest_is_a_problem_not_absence(tmp_path):
    """chmod 000 on a scratch copy: the run's own launch record.

    Previously this was `except (OSError, JSONDecodeError): continue`, i.e. a
    manifest we cannot read became a run with no manifest, which became a run
    with no pid, which became "idle, therefore droppable".
    """
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root: mode bits do not deny reads")
    world = _world(tmp_path, runs=3, pid=4242)
    victim = world / "runs" / "run-000000000000" / "server_env.json"
    os.chmod(victim, 0)
    try:
        with pytest.raises(PermissionError):
            victim.read_text()
        inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                                 pid_alive=_never)
    finally:
        os.chmod(victim, stat.S_IRUSR | stat.S_IWUSR)
    assert not inv.complete
    assert any("cannot read" in p and "run-000000000000" in p
               for p in inv.inspection_problems), inv.inspection_problems
    result, removed = _apply(inv, world=world)
    assert removed == []
    assert "activity inspection incomplete" in result["refused"]
    assert _run_ids(world) == [f"run-{i:012x}" for i in range(3)]


def test_unreadable_world_state_is_a_problem_not_an_empty_state(tmp_path):
    """``preview_stack.json`` unreadable: previously `st = {}`."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root: mode bits do not deny reads")
    world = _world(tmp_path, runs=3, pid=4242)
    state = world / "preview_stack.json"
    state.write_text(json.dumps({"run_dir": str(world / "runs" / "run-000000000000"),
                                 "backend_pid": 4242}))
    os.chmod(state, 0)
    try:
        inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                                 pid_alive=_never)
    finally:
        os.chmod(state, stat.S_IRUSR | stat.S_IWUSR)
    assert not inv.complete
    assert any("preview_stack.json" in p for p in inv.inspection_problems)
    result, removed = _apply(inv, world=world)
    assert removed == [] and "incomplete" in result["refused"]


def test_world_state_naming_a_run_with_no_pid_is_unknown_not_safe(tmp_path):
    """The world says a run is being served but records no pid to check.

    This is the "the pid check cannot be performed" case named in the work
    order, and it is the single most common real shape: older
    ``preview_stack.json`` files record the served run and no backend pid.
    """
    world = _world(tmp_path, runs=3, pid=4242)
    (world / "preview_stack.json").write_text(json.dumps(
        {"run_dir": str(world / "runs" / "run-000000000000")}))
    inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert not inv.complete
    assert any("could not be checked" in p for p in inv.inspection_problems)
    assert "run-000000000000" in \
        {e.run_id for e in inv.entries if e.classification == SP.CLASS_ACTIVE}
    result, removed = _apply(inv, world=world)
    assert removed == []


def test_world_state_with_a_pid_and_no_run_dir_is_a_problem(tmp_path):
    """A live process serving an unidentified run is exactly the blind spot."""
    world = _world(tmp_path, runs=2, pid=4242)
    (world / "preview_stack.json").write_text(json.dumps({"backend_pid": os.getpid()}))
    inv = SP.build_inventory(world, cap=0, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert not inv.complete
    assert any("names no run_dir" in p for p in inv.inspection_problems)


def test_unparseable_launch_record_is_a_problem(tmp_path):
    world = _world(tmp_path, runs=2, pid=4242)
    (world / "runs" / "run-000000000000" / "server_env.json").write_text("{not json")
    inv = SP.build_inventory(world, cap=0, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert not inv.complete
    assert any("cannot parse" in p for p in inv.inspection_problems)
    assert inv.deletion_candidates() == []


def test_unreadable_evidence_document_is_a_problem(tmp_path):
    """An evidence document we cannot read names runs we do not know about."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root: mode bits do not deny reads")
    world = _world(tmp_path, runs=2, pid=4242)
    results = tmp_path / "results"
    results.mkdir()
    doc = results / "recorded.json"
    doc.write_text(json.dumps({"run": "run-000000000000"}))
    os.chmod(doc, 0)
    try:
        inv = SP.build_inventory(world, cap=0, evidence_roots=[results],
                                 pinned=[], pid_alive=_never)
    finally:
        os.chmod(doc, stat.S_IRUSR | stat.S_IWUSR)
    assert not inv.complete
    assert any("evidence: cannot read" in p for p in inv.inspection_problems)
    result, removed = _apply(inv, world=world)
    assert removed == []


def test_truncated_evidence_scan_is_a_problem(tmp_path):
    world = _world(tmp_path, runs=2, pid=4242)
    results = tmp_path / "results"
    results.mkdir()
    for i in range(5):
        (results / f"d{i}.json").write_text(json.dumps({"run": f"run-{i:012x}"}))
    inv = SP.build_inventory(world, cap=0, evidence_roots=[results],
                             pinned=[], pid_alive=_never)
    # A full scan is complete...
    assert inv.complete
    # ... and a capped one says so rather than pretending the rest is empty.
    mapping, problems = SP.scan_evidence_runs_audited([results], max_files=2)
    assert problems and "cap" in problems[0]
    assert len(mapping) < 5


def test_unknown_ownership_is_never_droppable(tmp_path):
    world = _world(tmp_path, runs=3, pid=None)
    inv = SP.build_inventory(world, cap=0, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert {e.classification for e in inv.entries} == {SP.CLASS_REVIEW}
    assert inv.deletion_candidates() == []


def test_partial_scan_flag_excludes_everything(tmp_path):
    world = _world(tmp_path, runs=3, pid=4242)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                             scan_world_state=False)
    assert not inv.complete
    assert inv.deletion_candidates() == []
    assert "PARTIAL SCAN" in inv.unclassified_note
    result, removed = _apply(inv, world=world)
    assert removed == []


def test_a_complete_scan_can_still_produce_deletion_candidates(tmp_path):
    """Negative control for the two tests above: the gates are not vacuous."""
    world = _world(tmp_path, runs=4, pid=4242)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert inv.complete
    assert [e.run_id for e in inv.deletion_candidates()] == \
        ["run-000000000000", "run-000000000001", "run-000000000002"]
    result, removed = _apply(inv, world=world)
    assert len(removed) == 3
    assert result["deleted"] == [
        "run-000000000000", "run-000000000001", "run-000000000002"]


def test_pid_state_is_three_valued(tmp_path):
    assert SP.pid_state(os.getpid()) == SP.OWNER_IN_USE
    assert SP.pid_state(None) == SP.OWNER_UNKNOWN
    assert SP.pid_state("not-a-pid") == SP.OWNER_UNKNOWN
    assert SP.pid_state(0) == SP.OWNER_UNKNOWN
    assert SP.pid_state(-1) == SP.OWNER_UNKNOWN
    assert SP._pid_alive_default(None) is True, \
        "the boolean view must fail closed too: None is not 'dead'"


# ===========================================================================
# 3. The default fixture is genuinely small
# ===========================================================================
def test_default_fixture_is_under_a_hard_ceiling(tmp_path):
    """The size is ASSERTED, not asserted-about in a comment."""
    fixture = tmp_path / "fixture" / "atom.db"
    info = SP.provision_api_seeded_fixture(fixture)
    size = os.lstat(fixture).st_size
    assert size <= SP.SMALL_FIXTURE_MAX_BYTES, (
        f"default fixture is {size} bytes, over the "
        f"{SP.SMALL_FIXTURE_MAX_BYTES}-byte ceiling")
    assert info["size_bytes"] == size
    assert info["size_ceiling_bytes"] == SP.SMALL_FIXTURE_MAX_BYTES
    # ... and it is not small because it is empty of tables.
    assert info["table_count"] > 100
    con = sqlite3.connect(f"file:{fixture}?mode=ro", uri=True)
    try:
        assert con.execute("SELECT count(*) FROM users").fetchone()[0] == 0
        pages, free = con.execute(
            "PRAGMA page_count").fetchone()[0], con.execute(
            "PRAGMA freelist_count").fetchone()[0]
    finally:
        con.close()
    assert free == 0, "free pages mean the file is carrying deleted bulk"
    assert pages * 4096 == size


def test_default_fixture_is_at_most_a_tenth_of_the_live_database(tmp_path):
    """The saving is real, and the comparison is against a MEASURED figure."""
    fixture = tmp_path / "fx.db"
    SP.provision_api_seeded_fixture(fixture)
    new_bytes = os.lstat(fixture).st_size
    assert new_bytes * 10 <= LIVE_DB_BYTES_MEASURED, (
        f"default fixture {new_bytes} B is not an order of magnitude below "
        f"the measured live DB {LIVE_DB_BYTES_MEASURED} B")
    lo, hi = NEW_DEFAULT_FIXTURE_BAND
    assert lo <= new_bytes <= hi, (
        f"the default fixture measured {new_bytes} B, outside the recorded band "
        f"{lo}-{hi}. If the app schema grew, re-measure deliberately; if the "
        f"fixture is carrying dev rows again, this is a regression.")
    assert new_bytes * 40 < OLD_DEFAULT_FIXTURE_BYTES


def test_fixture_size_ceiling_is_enforced_not_advisory(tmp_path, monkeypatch):
    """A 'small' fixture that is not small must be refused, not published.

    The ceiling is lowered rather than the file being faked: this exercises the
    real check in :func:`provision_api_seeded_fixture` on a real fixture.
    """
    monkeypatch.setattr(SP, "SMALL_FIXTURE_MAX_BYTES", 1024)
    with pytest.raises(SP.StoragePolicyError) as excinfo:
        SP.provision_api_seeded_fixture(tmp_path / "fx" / "atom.db")
    msg = str(excinfo.value)
    assert "1024" in msg and "ceiling" in msg
    assert "genuinely small" in msg
    # A negative control: the real ceiling lets the same fixture through.
    monkeypatch.setattr(SP, "SMALL_FIXTURE_MAX_BYTES", 32 * SP.MB)
    SP.provision_api_seeded_fixture(tmp_path / "fx2" / "atom.db")


def test_sqlite_backup_does_not_reclaim_space(tmp_path):
    """Why the default is rebuilt rather than copied-then-pruned.

    SQLite's online backup API copies PAGES, so the destination is the size of
    the source no matter how many rows are deleted afterwards. Only VACUUM
    rewrites the file. Measured here on a scratch database so the claim is a
    measurement, not an assertion.
    """
    src = tmp_path / "src.db"
    con = sqlite3.connect(str(src))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, blob BLOB)")
    con.executemany("INSERT INTO t (blob) VALUES (?)",
                    [(os.urandom(900),) for _ in range(4000)])
    con.commit()
    con.close()
    full = os.lstat(src).st_size

    dst = tmp_path / "dst.db"
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dst))
    with d:
        s.backup(d)
    d.close()
    s.close()
    copied = os.lstat(dst).st_size
    assert copied == full, "the backup API is expected to be page-for-page"

    con = sqlite3.connect(str(dst))
    con.execute("DELETE FROM t")
    con.commit()
    con.close()
    pruned = os.lstat(dst).st_size
    assert pruned == full, "DELETE does not shrink the file (that is the point)"

    con = sqlite3.connect(str(dst))
    con.execute("VACUUM")
    con.close()
    vacuumed = os.lstat(dst).st_size
    assert vacuumed < full // 2, "VACUUM is what actually reclaims pages"
    assert (full, copied, pruned, vacuumed) == (full, full, full, vacuumed)


def test_default_never_reads_the_live_database(tmp_path, monkeypatch):
    """Hard proof: make ANY open of the live path explode."""
    import sqlite3 as real_sqlite3

    live = tmp_path / "atom.db"
    live.write_bytes(b"\0" * MB)
    monkeypatch.setattr(SP, "LIVE_DB", live)
    opened: list = []
    real_connect = real_sqlite3.connect

    def guarded(target, *a, **kw):
        if "atom.db" in str(target) and str(tmp_path) in str(target) \
                and "fx" not in str(target) and str(target) == str(live):
            pytest.fail("the default fixture opened the live dev database")
        opened.append(str(target))
        return real_connect(target, *a, **kw)

    monkeypatch.setattr(real_sqlite3, "connect", guarded)
    SP.provision_api_seeded_fixture(tmp_path / "fx" / "atom.db")
    assert str(live) not in opened


def test_full_dev_db_is_opt_in_and_says_what_it_costs():
    default = SP.resolve_fixture_source(False)
    opt_in = SP.resolve_fixture_source(True)
    assert default.mode == SP.FIXTURE_API_SEEDED and default.explicit is False
    assert opt_in.mode == SP.FIXTURE_FULL_DEV_DB and opt_in.explicit is True
    assert "413,360,128" in opt_in.banner(), \
        "the opt-in banner must carry the measured size of the whole copy"
    assert "ENTIRE" in opt_in.banner()
    assert opt_in.banner() != default.banner()
    assert default.as_dict() != opt_in.as_dict()


def test_the_two_fixture_paths_are_distinguishable_in_launch_output(capsys):
    """A build announces which mode it used, before it writes anything."""
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    small = R.SP.resolve_fixture_source(False).banner()
    full = R.SP.resolve_fixture_source(True).banner()
    assert SP.FIXTURE_API_SEEDED in small and SP.FULL_DEV_DB_FLAG in small
    assert SP.FIXTURE_FULL_DEV_DB in full and SP.FULL_DEV_DB_FLAG in full
    # The manifest records the mode too, so a world can be audited later.
    assert R.SP.resolve_fixture_source(False).as_dict()["mode"] != \
        R.SP.resolve_fixture_source(True).as_dict()["mode"]


def test_the_full_dev_path_is_the_only_one_that_copies_the_live_file():
    """AST, because the property is about which BRANCH runs, not about text.

    The opt-in branch must contain the whole-file copy; the default branch must
    contain neither a copy of the live file nor any reference to the fixture
    being pruned down from one.
    """
    src = (Path(SP.__file__).parent / "run_isolated.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_world")
    branches = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and "is_full_dev_db" in ast.unparse(node.test):
            body = "\n".join(ast.unparse(s) for s in node.body)
            branches["full" if "else" not in ast.unparse(node.test)
                      else "other"] = body
            if node.orelse:
                branches["default"] = "\n".join(ast.unparse(s) for s in node.orelse)
    assert "full" in branches, "build_world no longer branches on the fixture mode"
    assert ".backup(" in branches["full"], (
        "the opt-in branch no longer copies the live file; the whole-file copy "
        "is what the flag is for")
    assert "LIVE_SHEET_ROOT" in branches["full"]
    assert "default" in branches, "the default branch disappeared"
    assert ".backup(" not in branches["default"], \
        "the DEFAULT path is copying a database; it must build instead"
    assert "provision_api_seeded_fixture" in branches["default"]
    assert "DELETE" not in branches["default"].upper()


# ===========================================================================
# 4. Deletion needs the interlock AND a reviewed inventory
# ===========================================================================
def _droppable_world(tmp_path, runs=4):
    """Four idle runs, cap=3, so exactly ONE is a deletion candidate."""
    world = _world(tmp_path, runs=runs, pid=4242)
    inv = SP.build_inventory(world, cap=3, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert inv.complete, inv.inspection_problems
    assert [e.run_id for e in inv.deletion_candidates()] == ["run-000000000000"]
    return world, inv


def test_refuses_with_the_interlock_but_no_reviewed_inventory(tmp_path):
    world, inv = _droppable_world(tmp_path)
    removed: list = []
    result = SP.apply_inventory(
        inv, confirm=True, world=world, reviewed_digest=None,
        interlock_probe=_held_interlock, state_probe=_quiescent,
        remove=removed.append)
    assert removed == [], "the interlock alone must not authorise deletion"
    assert "no reviewed inventory" in result["refused"]
    assert result["deleted"] == []


def test_refuses_with_a_reviewed_inventory_but_no_interlock(tmp_path):
    world, inv = _droppable_world(tmp_path)
    removed: list = []
    result = SP.apply_inventory(
        inv, confirm=True, world=world, reviewed_digest=inv.digest,
        interlock_probe=lambda: (False, "maintenance interlock NOT held"),
        state_probe=_quiescent, remove=removed.append)
    assert removed == [], "a reviewed inventory alone must not authorise deletion"
    assert "interlock NOT held" in result["refused"]
    assert result["deleted"] == []


def test_refuses_with_no_confirmation_even_with_both_other_gates(tmp_path):
    world, inv = _droppable_world(tmp_path)
    result, removed = _apply(inv, world=world, confirm=False)
    assert removed == []
    assert "nothing deleted" in result["note"]


def test_refuses_while_a_build_marker_is_present(tmp_path):
    world, inv = _droppable_world(tmp_path)
    marker = SP.write_build_marker(world, operation="build_world")
    assert marker.exists()
    in_progress, why = SP.world_in_progress(world, runner_probe=_no_runners)
    assert in_progress and any("build marker" in r for r in why)
    result, removed = _apply(inv, world=world)
    assert removed == [], "a build marker must block deletion"
    assert "build or run may be in progress" in result["refused"]
    assert str(marker) in result["refused"]


def test_refuses_while_a_run_live_marker_is_present(tmp_path):
    world, inv = _droppable_world(tmp_path)
    (world / "runs" / "run-000000000000" / SP.RUN_LIVE_MARKER).write_text("x")
    result, removed = _apply(inv, world=world)
    assert removed == [], "a run-live marker must block deletion"
    assert SP.RUN_LIVE_MARKER in result["refused"]


def test_refuses_while_a_launcher_is_registered(tmp_path):
    world, inv = _droppable_world(tmp_path)
    result, removed = _apply(
        inv, world=world,
        state=lambda w: SP.world_in_progress(
            w, runner_probe=lambda: [{"pid": 999999, "role": "launcher"}]))
    assert removed == []
    assert "999999" in result["refused"]


def test_refuses_when_the_launcher_registry_cannot_be_read(tmp_path):
    """Fail CLOSED: an unreadable registry is not an empty registry."""
    world, inv = _droppable_world(tmp_path)
    result, removed = _apply(
        inv, world=world,
        state=lambda w: SP.world_in_progress(w, runner_probe=lambda: None))
    assert removed == []
    assert "could not be read" in result["refused"]


def test_refuses_when_the_interlock_probe_raises(tmp_path):
    world, inv = _droppable_world(tmp_path)

    def boom():
        raise RuntimeError("guard unavailable")

    removed: list = []
    result = SP.apply_inventory(inv, confirm=True, world=world,
                                reviewed_digest=inv.digest,
                                interlock_probe=boom, state_probe=_quiescent,
                                remove=removed.append)
    assert removed == []
    assert "interlock probe raised" in result["refused"]


def test_a_stale_reviewed_digest_is_refused(tmp_path):
    """Consenting to the inventory you read is not consenting to another."""
    world, inv = _droppable_world(tmp_path)
    stale = SP.Inventory(world=inv.world, cap=inv.cap,
                         generated_at=inv.generated_at,
                         entries=inv.entries).finalize().digest
    stale = "0" * 64 if stale == inv.digest else stale
    result, removed = _apply(inv, world=world, digest=stale)
    assert removed == []
    assert "does not match this inventory" in result["refused"]


def test_the_digest_changes_when_the_inventory_changes(tmp_path):
    world, inv = _droppable_world(tmp_path)
    before = inv.digest
    (world / "pinned_runs.json").write_text(json.dumps(["run-000000000000"]))
    again = SP.build_inventory(world, cap=1, evidence_roots=[], pinned=None,
                               pid_alive=_never)
    assert again.digest != before, \
        "a pinned run appeared; the inventory a human reviewed must not match"


def test_all_three_gates_together_do_delete(tmp_path):
    """Negative control: the gates are not a blanket refusal."""
    world, inv = _droppable_world(tmp_path)
    result, removed = _apply(inv, world=world)
    assert [p.name for p in removed] == ["run-000000000000"]
    assert result["deleted"] == ["run-000000000000"]
    assert result["freed_bytes"] > 0


def test_a_world_cannot_be_deleted_without_one(tmp_path):
    world, inv = _droppable_world(tmp_path)
    result, removed = _apply(inv, world=None)
    assert removed == []
    assert "no world given" in result["refused"]


# ---------------------------------------------------------------------------
# exclusions cannot be bypassed
# ---------------------------------------------------------------------------
def test_active_pinned_and_evidence_runs_are_never_deletion_candidates(tmp_path):
    world = _world(tmp_path)
    _run(world, "run-0000000000aa", pid=os.getpid(), age_days=1)      # active
    _run(world, "run-0000000000bb", pid=999_999_999, age_days=400)    # idle+old
    _run(world, "run-0000000000cc", pid=999_999_999, age_days=400)    # pinned
    _run(world, "run-0000000000dd", pid=999_999_999, age_days=400)    # evidence
    (world / SP.PIN_FILE).write_text(json.dumps(["run-0000000000cc"]))
    results = tmp_path / "results"
    results.mkdir()
    (results / "rec.json").write_text(json.dumps({"run": "run-0000000000dd"}))

    inv = SP.build_inventory(world, cap=0, evidence_roots=[results],
                             pinned=None, pid_alive=lambda pid: pid == os.getpid())
    by_id = {e.run_id: e for e in inv.entries}
    assert by_id["run-0000000000aa"].classification == SP.CLASS_ACTIVE
    assert by_id["run-0000000000cc"].classification == SP.CLASS_PINNED
    assert by_id["run-0000000000dd"].classification == SP.CLASS_EVIDENCE
    assert "active" in by_id["run-0000000000aa"].protection
    assert "pinned" in by_id["run-0000000000cc"].protection
    assert "evidence" in by_id["run-0000000000dd"].protection
    assert [e.run_id for e in inv.deletion_candidates()] == ["run-0000000000bb"]
    result, removed = _apply(inv, world=world)
    assert [p.name for p in removed] == ["run-0000000000bb"]


def test_rewriting_a_classification_cannot_make_a_protected_run_droppable(tmp_path):
    """The structural defence: eligibility is re-derived from ``protection``.

    A flag cannot reach it; a caller poking at the dataclass cannot either,
    because ``protection`` is recorded at classification time and nothing in
    the apply path clears it.
    """
    world = _world(tmp_path)
    _run(world, "run-0000000000aa", pid=999_999_999, age_days=400)
    _run(world, "run-0000000000cc", pid=999_999_999, age_days=400)
    (world / SP.PIN_FILE).write_text(json.dumps(["run-0000000000cc"]))
    inv = SP.build_inventory(world, cap=0, evidence_roots=[], pinned=None,
                             pid_alive=_never)
    pinned = next(e for e in inv.entries if e.run_id == "run-0000000000cc")
    pinned.classification = SP.CLASS_DROPPABLE       # the "flag" someone would add
    pinned.reasons = ["pretend it is droppable"]
    assert "pinned" in pinned.protection
    assert pinned not in inv.deletion_candidates()
    result, removed = _apply(inv, world=world)
    assert [p.name for p in removed] == ["run-0000000000aa"]


def test_review_required_runs_are_reported_and_block_the_whole_inventory(tmp_path):
    """One unclassifiable run makes the inventory unauthorisable.

    This is the sharp edge of the fail-closed rule and it is intentional: a
    run whose liveness cannot be established is not a smaller deletion set, it
    is an inventory that cannot say what it is looking at. The refusal names
    the run, so the operator knows which record is missing its pid.
    """
    world = _world(tmp_path)
    _run(world, "run-000000000000", pid=999_999_999, age_days=400)
    _run(world, "run-000000000001", pid=None, age_days=400)
    inv = SP.build_inventory(world, cap=0, evidence_roots=[], pinned=[],
                             pid_alive=_never)
    assert [e.run_id for e in inv.review_required] == ["run-000000000001"]
    assert not inv.complete
    result, removed = _apply(inv, world=world)
    assert removed == [], "an incomplete classification must delete NOTHING"
    assert result["deleted"] == []
    assert result["review_required"][0]["run_id"] == "run-000000000001"
    assert "records no usable pid" in result["refused"] or \
        "activity inspection incomplete" in result["refused"]
    assert sorted(_run_ids(world)) == ["run-000000000000", "run-000000000001"]


def test_the_inventory_text_carries_the_digest_and_the_three_requirements(tmp_path):
    world, inv = _droppable_world(tmp_path)
    text = inv.to_text()
    assert inv.digest in text
    assert "python -m core.world_storage_guard lock --reason" in text
    assert "--reviewed-digest" in text
    assert "NOTHING WAS DELETED" in text


def test_the_build_marker_is_written_and_cleared_by_the_launcher(tmp_path):
    """The marker is real state, written by build_world and read by cleanup."""
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    world = _world(tmp_path)
    marker = R.SP.write_build_marker(world, operation="build_world",
                                     detail={"fixture_mode": "api-seeded-fixture"})
    assert json.loads(marker.read_text())["operation"] == "build_world"
    in_progress, why = SP.world_in_progress(world, runner_probe=_no_runners)
    assert in_progress
    assert R.SP.clear_build_marker(world) is True
    assert not marker.exists()
    assert SP.clear_build_marker(world) is False
    in_progress, _ = SP.world_in_progress(world, runner_probe=_no_runners)
    assert not in_progress


def test_build_world_writes_the_marker_and_clears_it():
    """Static: the launcher must actually wire the marker, or the gate above
    is checking a file nobody writes."""
    src = (Path(SP.__file__).parent / "run_isolated.py").read_text()
    assert "SP.write_build_marker(world" in src
    assert "SP.clear_build_marker(world)" in src
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_world")
    lines = {n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("write_build_marker", "clear_build_marker")}
    assert len(lines) == 2, "build_world must write AND clear the marker"
    first_mkdir = min(n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "mkdir")
    write_line = min(l for l in lines if l in
                     {n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "write_build_marker"})
    assert write_line < first_mkdir, "the marker must exist before the first mkdir"


# ===========================================================================
# 5. Deterministic injection seams
# ===========================================================================
def test_disk_shortage_is_injected_not_filled(tmp_path):
    world = _world(tmp_path, runs=0)
    (world / "fixture").mkdir()
    (world / "fixture" / "atom.db").write_bytes(b"\0" * (20 * MB))
    est = SP.estimate_world_build(world, with_build_cache=False, with_run_data=False)
    assert est.total_bytes > 0
    with pytest.raises(SP.InsufficientStorage) as excinfo:
        SP.check_space(est, free_bytes=est.total_bytes, free_probe=tmp_path)
    msg = str(excinfo.value)
    assert "SHORT BY" in msg
    assert "free    : " in msg and "(injected)" in msg, \
        "the refusal must say the free-space figure was injected, not measured"
    # The same estimate with plenty of room passes: exhaustion was the input.
    SP.check_space(est, free_bytes=est.total_bytes + 10 ** 12, free_probe=tmp_path)


def test_launcher_space_refusal_happens_before_anything_is_created(tmp_path):
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    world = tmp_path / "never_created"
    with pytest.raises(SP.InsufficientStorage):
        R._check_disk_before_world(world, free_bytes=1)
    assert not world.exists(), "the refusal must precede every mkdir"


def test_the_free_space_probe_is_a_seam_not_a_reading(tmp_path):
    """No test may depend on real free space; the seam must exist."""
    sig = inspect.signature(SP.check_space)
    assert "free_bytes" in sig.parameters
    sig2 = inspect.signature(SP.estimate_world_build)
    assert "worlds_root" in sig2.parameters
    tiny = SP.Headroom(
        live_db=SP.Component("live_db", 1, "measured:test", True),
        live_wal=SP.Component("live_wal", 1, "measured:test", True),
        snapshot_floor=SP.Component("snapshot_floor", 1, "test", True))
    rep = SP.check_space(SP.SpaceEstimate(target="world:x"),
                         free_bytes=12345, free_probe=tmp_path, headroom=tiny)
    assert rep.free_bytes == 12345 and rep.free_bytes_source == "injected"


def test_inspection_failure_is_injectable_without_timing(tmp_path):
    """Injection points, proved by signature, not by racing a clock."""
    assert "pid_alive" in inspect.signature(SP.inspect_activity).parameters
    assert "pid_probe" in inspect.signature(SP.inspect_activity).parameters
    assert "interlock_probe" in inspect.signature(SP.apply_inventory).parameters
    assert "state_probe" in inspect.signature(SP.apply_inventory).parameters
    assert "reviewed_digest" in inspect.signature(SP.apply_inventory).parameters
    assert "world" in inspect.signature(SP.apply_inventory).parameters
    assert "runner_probe" in inspect.signature(SP.world_in_progress).parameters
    world = _world(tmp_path, runs=2, pid=1)
    assert SP.inspect_activity(
        world, pid_alive=lambda _p: False).complete
    assert not SP.inspect_activity(world, pid_alive=_boom).complete


def _boom(pid):
    raise OSError("injected")


# ---------------------------------------------------------------------------
# the retention path in the launcher is inventory-only
# ---------------------------------------------------------------------------
def test_prune_old_runs_deletes_nothing_and_never_calls_apply(tmp_path):
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    world = _world(tmp_path, runs=4, pid=999_999_999)
    entries = R._prune_old_runs(world, max_retained=1)
    assert [e["run_id"] for e in entries] == [f"run-{i:012x}" for i in range(4)]
    assert all("protection" in e for e in entries)
    assert len(_run_ids(world)) == 4, "the retention path removed something"
    assert "protection" in entries[0]


def test_apply_inventory_is_the_only_destructive_path():
    """``shutil.rmtree`` appears in exactly one function, and it is the
    deletion path behind all three gates.

    The allowlist below is not a rubber stamp: each entry removes a file this
    module (or a world build) just created — the fixture being replaced, a
    build marker being cleared, the export symlink being repointed. None of
    them is a run-directory removal, and none can be reached from a build.
    """
    src = Path(SP.__file__).read_text()
    tree = ast.parse(src)
    # Top-level functions only: the nested default remover inside
    # apply_inventory is a detail of that function, and counting it as a
    # second destructive path would be a false positive.
    rmtree_fns = {
        fn.name for fn in tree.body if isinstance(fn, ast.FunctionDef)
        and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == "rmtree" for c in ast.walk(fn))}
    assert rmtree_fns == {"apply_inventory"}, (
        f"shutil.rmtree is reachable from {sorted(rmtree_fns)}; only the "
        f"gated deletion path may remove a tree")
    assert src.count("shutil.rmtree") >= 1
    rmtree_calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == "rmtree"]
    assert len(rmtree_calls) == 1, (
        f"{len(rmtree_calls)} rmtree call sites in the module; the docstring's "
        f"historical reference is text, a call site is a deletion path")
    destructive = {"rmtree", "unlink", "rmdir", "removedirs"}
    allowed = {
        "apply_inventory",            # the gated deletion path
        "provision_api_seeded_fixture",  # replaces the fixture it is creating
        "clear_build_marker",         # removes the marker it just wrote
        "write_build_marker",         # replaces its own marker
        "load_pinned_runs",           # never destructive; listed for clarity
        "link_shared_export",         # unlinks the export symlink it repoints
        "main",                       # --out overwrites the file it was told to
    }
    offenders = {}
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        calls = {c.func.attr if isinstance(c.func, ast.Attribute)
                 else getattr(c.func, "id", "")
                 for c in ast.walk(fn) if isinstance(c, ast.Call)}
        hit = calls & destructive
        if hit and fn.name not in allowed:
            offenders[fn.name] = sorted(hit)
    assert not offenders, f"unexpected destructive calls: {offenders}"
    # ... and the launchers' build path calls no destructive function at all.
    launcher = (Path(SP.__file__).parent / "run_isolated.py").read_text()
    ltree = ast.parse(launcher)
    for name in ("_prune_old_runs", "_report_storage"):
        fn = next(n for n in ast.walk(ltree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = {c.func.attr if isinstance(c.func, ast.Attribute) else ""
                 for c in ast.walk(fn) if isinstance(c, ast.Call)}
        assert not (calls & destructive), f"{name} is destructive: {calls}"
    prune = next(n for n in ast.walk(ltree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_prune_old_runs")
    assert "apply_inventory" not in ast.unparse(prune)
