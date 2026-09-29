# -*- coding: utf-8 -*-
"""Storage-policy unit tests (storage policy for the acceptance harness).

Scope and safety
----------------
Every test here runs against SCRATCH directories under pytest's ``tmp_path``
with ``TESTING=1`` (forced by ``tests/conftest.py``). No test:

* creates, seeds, launches, refreshes or tears down an acceptance world;
* reads or writes ``backend/data/acceptance_worlds``;
* opens ``backend/data/atom.db``;
* touches a port or starts a server.

Free space is INJECTED (``check_space(free_bytes=...)``) so exhaustion is
simulated deterministically instead of by filling a real disk.

One test (``test_provisioned_fixture_never_opens_the_live_database``) does
import the app's declarative metadata and create a schema-only sqlite in
tmp_path. That is the small API-seeded fixture this policy ships as the
DEFAULT, and building it is the one thing that must actually work. It is
still a scratch database.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

from scripts.orchestration_acceptance import storage_policy as SP

MB = SP.MB

#: Run ids must match the harness's own naming (``run-<12 hex>``) or the
#: evidence detector will not recognise them -- which would make these tests
#: pass for the wrong reason.
PINNED_RUN = "run-0000000000aa"
EVIDENCE_RUN = "run-0000000000bb"
ACTIVE_RUN = "run-0000000000cc"
FRESH_RUN = "run-0000000000dd"
LAUNCH_RUN = "run-0000000000ee"


def _function_node(src: str, name: str):
    """The ast node for a top-level function, located by name (not by
    string slicing -- a multi-line signature defeats that)."""
    import ast
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"no top-level function {name!r} in the module")


def _destructive_calls(src: str, name: str) -> list:
    """Names of destructive filesystem calls inside one function.

    AST, not substring matching: a docstring that says ``shutil.rmtree`` is
    documentation, a call to it is a deletion, and only the second one
    should fail a test about not deleting.
    """
    import ast
    node = _function_node(src, name)
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        attr = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if attr in ("rmtree", "remove", "unlink", "rmdir", "removedirs"):
            out.append(attr)
    return out


def _module_source(name: str) -> str:
    return (Path(SP.BACKEND) / "scripts" / "orchestration_acceptance" / name).read_text()


def _function_source(src: str, name: str) -> str:
    """Exact source of a top-level function, via ast line numbers."""
    node = _function_node(src, name)
    lines = src.splitlines()
    return "\n".join(lines[node.lineno - 1:node.end_lineno])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
#: Every scratch run gets a POSITIVE ownership record: a recorded pid that the
#: injected probe reports as not running. That is the only shape that can be
#: classified ``droppable`` — the policy requires liveness to be positively
#: established as idle, so a run with no recorded pid is ``review-required``
#: and its inventory is unauthorisable for deletion. The no-pid shape is
#: asserted on purpose in tests/core/test_storage_policy_fail_closed.py.
DEAD_PID = 900_000  # a pid that cannot be running


def _make_run(world: Path, run_id: str, *, db_bytes: int = 0, age_days: float = 0.0,
              payload: dict = None) -> Path:
    run = world / "runs" / run_id
    (run / "data").mkdir(parents=True)
    db = run / "data" / "atom.db"
    db.write_bytes(b"\0" * db_bytes)
    body = {"pid": DEAD_PID}
    body.update(payload or {})
    (run / "server_env.json").write_text(json.dumps(body))
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(run, (t, t))
        os.utime(db, (t, t))
    return run


def _alive(pid):
    """A pid probe whose answer is INVERTED relative to the recorded pid.

    A recorded pid is treated as alive when it is not the scratch world's
    sentinel, so a run naming a real pid is active and a sentinel run is idle.
    """
    return pid is not None and pid != DEAD_PID


def _world(tmp_path: Path, name: str = "w") -> Path:
    w = tmp_path / "worlds" / name
    w.mkdir(parents=True)
    return w


def _evidence_file(root: Path, run_id: str, **extra) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    f = root / f"{run_id}.json"
    f.write_text(json.dumps({"world": "w", "run": run_id, **extra}))
    return f


# ===========================================================================
# 1. Space check: refuse when it does not fit, allow when it does, and
#    reserve the live DB / WAL / backup floor.
# ===========================================================================
def test_space_check_allows_when_estimate_plus_reserve_fits(tmp_path):
    world = _world(tmp_path)
    (world / "fixture").mkdir()
    (world / "fixture" / "atom.db").write_bytes(b"\0" * (40 * MB))
    est = SP.estimate_world_build(world, with_build_cache=False, with_run_data=False)
    headroom = SP.Headroom(
        live_db=SP.Component("live_db", 412 * MB, "measured:test", True),
        live_wal=SP.Component("live_wal", 4 * MB, "measured:test", True),
        snapshot_floor=SP.Component("snapshot_floor", 500 * MB, "db_safety", True))
    required = est.total_bytes + headroom.total_bytes
    rep = SP.check_space(est, free_bytes=required, headroom=headroom)
    assert rep.ok and rep.free_bytes == required
    assert rep.shortfall_bytes == 0


def test_space_check_refuses_when_estimate_exceeds_free_space(tmp_path):
    """The refusal is a named shortfall, not a traceback mid-copy."""
    world = _world(tmp_path)
    est = SP.estimate_world_build(world, with_build_cache=False, with_run_data=False)
    rep_free = est.total_bytes  # exactly the estimate, nothing left for the reserve
    with pytest.raises(SP.InsufficientStorage) as excinfo:
        SP.check_space(est, free_bytes=rep_free)
    msg = str(excinfo.value)
    assert "INSUFFICIENT STORAGE" in msg
    assert "SHORT BY" in msg
    assert "Nothing was created and nothing was written." in msg
    # The shortfall is quantified, not just signalled.
    assert "reserve" in msg and "live DB" in msg and "snapshot floor" in msg


def test_space_check_reserves_headroom_for_live_db_wal_and_backup_floor(tmp_path):
    """Headroom is measured live DB + WAL + db_safety's floor, and a build
    that would consume it is refused even though the estimate alone fits."""
    est = SP.SpaceEstimate(target="world:t")
    est.add("fixture", 10 * MB, "measured:test", True)
    headroom = SP.Headroom(
        live_db=SP.Component("live_db", 412 * MB, "measured:test", True),
        live_wal=SP.Component("live_wal", 4 * MB, "measured:test", True),
        snapshot_floor=SP.Component("snapshot_floor", 500 * MB, "db_safety", True))
    assert headroom.total_bytes == 916 * MB

    # Estimate (10 MB) fits in 500 MB, but 500 MB does not cover 916 MB.
    with pytest.raises(SP.InsufficientStorage):
        SP.check_space(est, free_bytes=500 * MB, headroom=headroom)
    # 926 MB covers estimate + reserve exactly.
    rep = SP.check_space(est, free_bytes=926 * MB, headroom=headroom)
    assert rep.ok


def test_headroom_reads_the_snapshot_floor_from_db_safety(monkeypatch, tmp_path):
    """The floor is read from core.db_safety, not duplicated, so the space
    check and the snapshotter cannot drift apart."""
    monkeypatch.setenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "750")
    live = tmp_path / "atom.db"
    live.write_bytes(b"\0" * (300 * MB))
    (tmp_path / "atom.db-wal").write_bytes(b"\0" * (7 * MB))
    h = SP.live_db_headroom(live_db=live)
    assert h.live_db.bytes == 300 * MB
    assert h.live_wal.bytes == 7 * MB
    assert h.snapshot_floor.bytes == 750 * MB
    assert h.total_bytes == 1057 * MB


def test_estimate_prefers_measured_sizes_over_constants(tmp_path):
    """A sibling world's real code export and run data are the measurement;
    the estimate must say where each number came from."""
    worlds = tmp_path / "worlds"
    worlds.mkdir()
    sib = worlds / "sib"
    (sib / "code").mkdir(parents=True)
    (sib / "code" / "blob.bin").write_bytes(b"\0" * (7 * MB))
    (sib / "runs" / "run-aaaaaaaaaaaa" / "data").mkdir(parents=True)
    (sib / "runs" / "run-aaaaaaaaaaaa" / "data" / "atom.db").write_bytes(b"\0" * (11 * MB))
    target = worlds / "new"

    est = SP.estimate_world_build(target, worlds_root=worlds, with_build_cache=False)
    code = next(c for c in est.components if c.name == "code_export")
    run = next(c for c in est.components if c.name == "run_data")
    assert code.measured and code.bytes == 7 * MB and "sib" in code.source
    assert run.measured and run.bytes == 11 * MB and "sib" in run.source
    # A fixture the world does not have yet falls back, and says so.
    fixture = next(c for c in est.components if c.name == "fixture")
    assert not fixture.measured and "fallback" in fixture.source


def test_shared_export_costs_nothing_to_estimate(tmp_path):
    world = _world(tmp_path)
    (world / "fixture").mkdir()
    (world / "fixture" / "atom.db").write_bytes(b"\0" * MB)
    (world / "code").symlink_to(tmp_path / "elsewhere")
    est = SP.estimate_world_build(world, with_build_cache=False, with_run_data=False)
    code = next(c for c in est.components if c.name == "code_export")
    assert code.bytes == 0 and code.measured


def test_new_run_estimate_is_measured_from_the_world_fixture(tmp_path):
    world = _world(tmp_path)
    (world / "fixture").mkdir()
    (world / "fixture" / "atom.db").write_bytes(b"\0" * (30 * MB))
    est = SP.estimate_new_run(world)
    comp = next(c for c in est.components if c.name == "run_data")
    assert comp.bytes == 30 * MB and comp.measured


# ===========================================================================
# 2. The full dev DB copy is OFF by default and needs the explicit flag.
# ===========================================================================
def test_full_dev_db_is_off_by_default():
    src = SP.resolve_fixture_source(False)
    assert src.mode == SP.FIXTURE_API_SEEDED
    assert src.is_full_dev_db is False
    assert src.explicit is False


def test_full_dev_db_requires_the_explicit_flag():
    assert SP.FULL_DEV_DB_FLAG == "--full-dev-db-snapshot"
    assert SP.resolve_fixture_source(True).mode == SP.FIXTURE_FULL_DEV_DB
    assert SP.resolve_fixture_source(True).is_full_dev_db is True


def test_default_fixture_never_reads_the_live_database(tmp_path, monkeypatch):
    """The default must not depend on data/atom.db existing or being
    readable. Point LIVE_DB at a path that raises if it is opened."""
    fixture = tmp_path / "fixture" / "atom.db"
    monkeypatch.setattr(SP, "LIVE_DB", tmp_path / "does-not-exist" / "atom.db")
    info = SP.provision_api_seeded_fixture(fixture)
    assert fixture.is_file()
    assert info["rows"] == 0
    assert info["mode"] == SP.FIXTURE_API_SEEDED
    assert info["integrity_check"] == "ok"
    assert info["table_count"] > 100, "the app schema should be many tables"


def test_provisioned_fixture_never_opens_the_live_database(tmp_path, monkeypatch):
    """Hard proof, not intent: patch sqlite3.connect so any attempt to open
    the live dev database raises. The small fixture must still build."""
    import sqlite3 as real_sqlite3

    live = tmp_path / "atom.db"
    live.write_bytes(b"\0" * MB)
    monkeypatch.setattr(SP, "LIVE_DB", live)

    real_connect = real_sqlite3.connect
    opened = []

    def guarded(target, *a, **kw):
        if "does-not-exist" in str(target):
            pytest.fail("the small fixture opened the live dev database")
        opened.append(str(target))
        return real_connect(target, *a, **kw)

    monkeypatch.setattr(real_sqlite3, "connect", guarded)
    before = live.read_bytes()
    info = SP.provision_api_seeded_fixture(tmp_path / "fx" / "atom.db")
    assert info["table_count"] > 100
    assert str(live) not in opened, "the live dev database was opened"
    assert live.read_bytes() == before, "the live dev database was modified"


def test_launch_banner_states_which_fixture_mode_was_used():
    small = SP.resolve_fixture_source(False).banner()
    full = SP.resolve_fixture_source(True).banner()
    assert SP.FIXTURE_API_SEEDED in small and SP.FULL_DEV_DB_FLAG in small
    assert SP.FIXTURE_FULL_DEV_DB in full
    assert "ENTIRE live dev database" in full
    assert "413,360,128" in full, \
        "the banner must carry the measured size of the whole-file copy"
    assert "explicit" in full


def test_cli_exposes_the_opt_in_flag_and_help_says_the_default_is_small():
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(SystemExit):
        SP.main(["space", "--help"])
    # argparse hard-wraps help at the terminal width, so a phrase can be split
    # across lines and even hyphenated ("small API-\nseeded"). Normalise both
    # before matching a phrase.
    help_text = " ".join(buf.getvalue().split()).replace("- ", "-")
    assert SP.FULL_DEV_DB_FLAG in help_text
    assert "small API-seeded fixture" in help_text
    assert "ENTIRE live dev database" in help_text


def test_estimate_uses_the_live_db_size_only_for_the_opt_in_mode(monkeypatch, tmp_path):
    worlds = tmp_path / "worlds"
    worlds.mkdir()
    live = tmp_path / "atom.db"
    live.write_bytes(b"\0" * (250 * MB))
    monkeypatch.setattr(SP, "LIVE_DB", live)
    target = worlds / "w"

    small = SP.estimate_world_build(target, worlds_root=worlds, full_dev_db=False,
                                    with_build_cache=False, with_run_data=False)
    full = SP.estimate_world_build(target, worlds_root=worlds, full_dev_db=True,
                                   with_build_cache=False, with_run_data=False)
    small_fx = next(c for c in small.components if c.name == "fixture")
    full_fx = next(c for c in full.components if c.name == "fixture")
    assert small_fx.bytes < full_fx.bytes
    assert full_fx.bytes == 250 * MB and "full dev snapshot" in full_fx.source


# ===========================================================================
# 3. Retention excludes active / pinned / evidence runs; inventory only.
# ===========================================================================
def test_inventory_excludes_the_active_run(tmp_path):
    world = _world(tmp_path)
    active = _make_run(world, "run-aaaaaaaaaaaa", db_bytes=1 * MB, age_days=90)
    for i in range(6):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=90 - i)
    (world / "preview_stack.json").write_text(json.dumps({
        "run_dir": str(active), "backend_pid": 4242}))
    inv = SP.build_inventory(world, cap=1, pinned=[],
                             evidence_roots=[], pid_alive=lambda p: p == 4242)
    cls = {e.run_id: e.classification for e in inv.entries}
    assert cls["run-aaaaaaaaaaaa"] == SP.CLASS_ACTIVE
    assert active.exists(), "an active run must never be a deletion candidate"


def test_inventory_excludes_pinned_runs(tmp_path):
    world = _world(tmp_path)
    pinned = _make_run(world, PINNED_RUN, db_bytes=1 * MB, age_days=200)
    _make_run(world, FRESH_RUN, db_bytes=1 * MB, age_days=1)
    (world / SP.PIN_FILE).write_text(json.dumps({"pinned": [PINNED_RUN]}))
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pid_alive=lambda p: False)
    cls = {e.run_id: e.classification for e in inv.entries}
    assert cls[PINNED_RUN] == SP.CLASS_PINNED
    assert cls[FRESH_RUN] == SP.CLASS_WITHIN_CAP
    assert pinned.exists()


def test_inventory_excludes_evidence_referenced_runs(tmp_path):
    world = _world(tmp_path)
    ev = _make_run(world, EVIDENCE_RUN, db_bytes=1 * MB, age_days=200)
    _make_run(world, FRESH_RUN, db_bytes=1 * MB, age_days=1)
    results = tmp_path / "results"
    _evidence_file(results, EVIDENCE_RUN, correct_completion=True)

    inv = SP.build_inventory(world, cap=1, evidence_roots=[results],
                             pinned=[], pid_alive=lambda p: False)
    entry = next(e for e in inv.entries if e.run_id == EVIDENCE_RUN)
    assert entry.classification == SP.CLASS_EVIDENCE
    assert entry.evidence_refs and "results" in entry.evidence_refs[0]
    assert "recorded document" in " ".join(entry.reasons)
    assert ev.exists()


def test_evidence_detection_finds_runs_embedded_in_absolute_paths(tmp_path):
    """The recorded formats embed run database paths, not just run ids."""
    world = _world(tmp_path)
    ev = _make_run(world, "run-777777777777", db_bytes=1 * MB, age_days=50)
    _make_run(world, "run-888888888888", db_bytes=1 * MB, age_days=1)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "crash_recovery.json").write_text(json.dumps({
        "run_dir": str(ev),
        "db": str(ev / "data" / "atom.db"),
        "timeline": [{"run_id": "run-777777777777"}],
        "unrelated": "run-888888888888 was never in this document",
    }))
    inv = SP.build_inventory(world, cap=1, evidence_roots=[docs],
                             pinned=[], pid_alive=lambda p: False)
    cls = {e.run_id: e.classification for e in inv.entries}
    # The literal "was never in this document" text still contains the token,
    # so the detector is deliberately conservative: it over-retains rather
    # than risking a drop of evidence-bearing history.
    assert cls["run-777777777777"] == SP.CLASS_EVIDENCE
    assert cls["run-888888888888"] == SP.CLASS_EVIDENCE


def test_evidence_detection_also_reads_world_launch_state(tmp_path):
    world = _world(tmp_path)
    _make_run(world, LAUNCH_RUN, db_bytes=1 * MB, age_days=99)
    (world / "launch_descriptor.json").write_text(
        json.dumps({"run_id": LAUNCH_RUN}))
    inv = SP.build_inventory(world, cap=1, pinned=[], pid_alive=lambda p: False)
    entry = next(e for e in inv.entries if e.run_id == LAUNCH_RUN)
    assert entry.classification == SP.CLASS_EVIDENCE


def test_unpinned_unreferenced_runs_outside_the_cap_are_droppable(tmp_path):
    world = _world(tmp_path)
    for i in range(6):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=30 - i)
    inv = SP.build_inventory(world, cap=2, evidence_roots=[],
                             pinned=[], pid_alive=_alive)
    assert inv.complete, inv.inspection_problems
    droppable = [e.run_id for e in inv.deletion_candidates()]
    keep = [e.run_id for e in inv.entries if e.classification == SP.CLASS_WITHIN_CAP]
    assert len(droppable) == 4 and len(keep) == 2
    assert "run-000000000005" in keep and "run-000000000004" in keep


def test_pinned_runs_do_not_consume_retention_slots(tmp_path):
    """A pinned run must not push a fresh debugging run out of the cap."""
    world = _world(tmp_path)
    _make_run(world, PINNED_RUN, db_bytes=1 * MB, age_days=500)
    for i in range(3):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=10 - i)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pinned=[PINNED_RUN], pid_alive=lambda p: False)
    cls = {e.run_id: e.classification for e in inv.entries}
    assert cls[PINNED_RUN] == SP.CLASS_PINNED
    assert cls["run-000000000002"] == SP.CLASS_WITHIN_CAP, "newest run must survive"


def test_inventory_is_produced_with_no_deletion_when_confirm_is_absent(tmp_path):
    world = _world(tmp_path)
    for i in range(5):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=30 - i)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pinned=[], pid_alive=_alive)
    assert len(inv.deletion_candidates()) == 4, "there is something to drop"

    removed = []
    result = SP.apply_inventory(inv, confirm=False, remove=lambda p: removed.append(p))
    assert removed == [], "no confirmation flag must mean no removal"
    assert result["deleted"] == [] and result["freed_bytes"] == 0
    assert "nothing deleted" in result["note"]
    assert len(list((world / "runs").iterdir())) == 5, "all runs still on disk"


def test_apply_inventory_only_deletes_droppable_runs_when_confirmed(tmp_path):
    """Behind ALL THREE gates, only unprotected runs are removed.

    The gates are the interlock and the reviewed digest as well as the
    confirmation flag, so this test supplies all three; the tests in
    tests/core/test_storage_policy_fail_closed.py prove that omitting any one
    of them deletes nothing.
    """
    world = _world(tmp_path)
    _make_run(world, PINNED_RUN, db_bytes=2 * MB, age_days=500)
    ev = _make_run(world, EVIDENCE_RUN, db_bytes=2 * MB, age_days=400)
    for i in range(4):
        _make_run(world, f"run-{i:012d}", db_bytes=2 * MB, age_days=30 - i)
    results = tmp_path / "res"
    _evidence_file(results, EVIDENCE_RUN)
    (world / SP.PIN_FILE).write_text(json.dumps([PINNED_RUN]))

    inv = SP.build_inventory(world, cap=1, evidence_roots=[results],
                             pid_alive=_alive)
    assert inv.complete, inv.inspection_problems
    removed = []
    result = SP.apply_inventory(
        inv, confirm=True, world=world, reviewed_digest=inv.digest,
        interlock_probe=lambda: (True, "held (injected)"),
        state_probe=lambda w: (False, []), remove=removed.append)
    assert not result.get("refused"), result.get("refused")
    assert sorted(removed) == sorted(e.path for e in inv.deletion_candidates())
    assert PINNED_RUN not in result["deleted"]
    assert EVIDENCE_RUN not in result["deleted"]
    assert ev.exists() and (world / "runs" / PINNED_RUN).exists()
    assert result["freed_bytes"] == sum(e.size_bytes
                                        for e in inv.deletion_candidates())


def test_inventory_text_advertises_what_would_be_dropped(tmp_path):
    world = _world(tmp_path)
    for i in range(4):
        _make_run(world, f"run-{i:012d}", db_bytes=2 * MB, age_days=20 - i)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pinned=[], pid_alive=_alive)
    text = inv.to_text()
    assert "Would drop 3 run(s)" in text
    assert "NOTHING WAS DELETED" in text
    assert "--confirm-drop" not in text  # the confirm hint lives in the CLI


def test_partial_scan_refuses_to_drop_anything(tmp_path):
    """Fail-safe: if the active-run signal was not consulted, nothing may be
    classified droppable."""
    world = _world(tmp_path)
    for i in range(4):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=30 - i)
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pinned=[], scan_world_state=False)
    assert inv.droppable == []
    assert "PARTIAL SCAN" in inv.unclassified_note
    assert "PARTIAL SCAN" in inv.as_dict()["unclassified_note"]


def test_inventory_text_lists_classification_size_and_reasons(tmp_path):
    world = _world(tmp_path)
    _make_run(world, "run-000000000001", db_bytes=3 * MB, age_days=5)
    _make_run(world, "run-000000000002", db_bytes=3 * MB, age_days=1)
    (world / SP.PIN_FILE).write_text(json.dumps(["run-000000000001"]))
    inv = SP.build_inventory(world, cap=1, evidence_roots=[],
                             pid_alive=lambda p: False)
    text = inv.to_text()
    assert "DELETION INVENTORY" in text
    assert SP.CLASS_PINNED in text
    assert "totals by classification" in text
    assert "Nothing is droppable" in text
    d = inv.as_dict()
    assert d["world"] == "w" and d["cap"] == 1
    assert d["entries"] and "classification" in d["entries"][0]


def test_run_id_pattern_matches_the_harness_naming():
    assert SP.RUN_ID_RE.findall("run-a2569ae8e003") == ["run-a2569ae8e003"]
    assert not SP.RUN_ID_RE.findall("run-nothex")
    assert not SP.RUN_ID_RE.findall("run-abc")  # too short


# ===========================================================================
# 4. A writable database is never hard-linked into a shared export.
# ===========================================================================
def test_hardlinked_writable_database_is_refused(tmp_path):
    world = _world(tmp_path)
    shared = tmp_path / "shared_code"
    shared.mkdir()
    target = shared / "atom.db"
    target.write_bytes(b"\0" * 1024)
    other = world / "data" / "atom.db"
    other.parent.mkdir(parents=True)
    os.link(target, other)
    with pytest.raises(SP.SharedWritableError) as exc:
        SP.assert_not_hardlinked_writable(other)
    assert "HARD-LINKED" in str(exc.value)
    assert "two writers" in str(exc.value).lower()


def test_separate_writable_database_is_accepted(tmp_path):
    world = _world(tmp_path)
    db = world / "data" / "atom.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"\0" * 1024)
    SP.assert_not_hardlinked_writable(db)  # must not raise


def test_writable_state_inside_a_shared_export_is_refused(tmp_path):
    world = _world(tmp_path)
    owner_code = tmp_path / "owner" / "code"
    owner_code.mkdir(parents=True)
    (world / "code_manifest.json").write_text(json.dumps({"a.py": "0" * 64}))
    (tmp_path / "owner" / "code_manifest.json").write_text(
        json.dumps({"a.py": "0" * 64}))
    (world / "code").symlink_to(owner_code)
    # A database that leaked into the shared tree, reached from the world.
    leaked = world / "code" / "data" / "atom.db"
    leaked.parent.mkdir(parents=True)
    leaked.write_bytes(b"\0" * 512)
    with pytest.raises(SP.SharedWritableError) as exc:
        SP.assert_writable_state_separate(world)
    assert "WRITABLE STATE INSIDE THE SHARED EXPORT" in str(exc.value)


def test_clean_shared_export_passes_the_writable_separation_check(tmp_path):
    world = _world(tmp_path)
    owner_code = tmp_path / "owner" / "code"
    (owner_code / "backend").mkdir(parents=True)
    (world / "code").symlink_to(owner_code)
    (world / "data").mkdir()
    (world / "data" / "atom.db").write_bytes(b"\0" * 512)
    SP.assert_writable_state_separate(world)  # writable state is per world


def test_find_hardlinked_writables_groups_one_inode(tmp_path):
    world = _world(tmp_path)
    a = world / "a" / "atom.db"
    b = world / "b" / "atom.db"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"\0" * 64)
    os.link(a, b)
    lone = world / "c" / "atom.db"
    lone.parent.mkdir(parents=True)
    lone.write_bytes(b"\0" * 64)
    groups = SP.find_hardlinked_writables(world)
    assert len(groups) == 1 and len(groups[0]) == 2
    assert all(".db" in g for g in groups[0])


def test_identical_exports_are_shared_not_recopied(tmp_path):
    owner = tmp_path / "owner"
    world = _world(tmp_path)
    # The owner holds the export; the sharing world does not have one yet --
    # that is the situation at build time, before extraction.
    (owner / "code" / "backend").mkdir(parents=True)
    for w in (owner, world):
        (w / "code_manifest.json").write_text(
            json.dumps({"backend/x.py": "a" * 64, "backend/y.py": "b" * 64}))
    res = SP.link_shared_export(world, owner)
    assert res["mode"] == "shared"
    assert (world / "code").is_symlink()
    assert Path(os.readlink(world / "code")) == owner / "code"


def test_differing_exports_are_copied_never_shared(tmp_path):
    """Sharing a non-identical export would make two worlds test different
    code, which is worse than the ~130 MB saved."""
    owner = tmp_path / "owner"
    world = _world(tmp_path)
    for w in (owner, world):
        (w / "code").mkdir(parents=True)
    (owner / "code_manifest.json").write_text(json.dumps({"a": "1"}))
    (world / "code_manifest.json").write_text(json.dumps({"a": "2"}))
    res = SP.link_shared_export(world, owner)
    assert res["mode"] == "copy"
    assert not (world / "code").is_symlink()


def test_manifestless_export_is_not_shared(tmp_path):
    owner = tmp_path / "owner"
    world = _world(tmp_path)
    for w in (owner, world):
        (w / "code").mkdir(parents=True)
    res = SP.link_shared_export(world, owner)
    assert res["mode"] == "copy"


def test_policy_documents_what_may_and_may_not_be_shared():
    assert SP.SHARED_EXPORT_OK == ("code",)
    for name in ("data", "logs", "runs", "fixture", "node_modules"):
        assert name in SP.SHARED_EXPORT_FORBIDDEN
    src = (Path(SP.__file__)).read_text()
    assert "NEVER SHARED" in src and "two writers on one inode" in src.lower()


# ===========================================================================
# 5. Status reports per-world and per-run sizes with a breakdown.
# ===========================================================================
def test_report_breaks_a_world_down_and_attributes_run_databases(tmp_path):
    world = _world(tmp_path)
    (world / "code").mkdir()
    (world / "code" / "a.py").write_bytes(b"\0" * 2 * MB)
    (world / "fixture").mkdir()
    (world / "fixture" / "atom.db").write_bytes(b"\0" * 3 * MB)
    (world / "data").mkdir()
    (world / "data" / "atom.db").write_bytes(b"\0" * 4 * MB)
    (world / "server.log").write_bytes(b"\0" * MB)
    _make_run(world, "run-111111111111", db_bytes=5 * MB, age_days=2)
    _make_run(world, "run-222222222222", db_bytes=6 * MB, age_days=1)

    rep = SP.world_storage_report(world)
    b = rep["breakdown_bytes"]
    # run_data covers the seeded databases plus each run's server_env.json.
    assert b["code_export"] == 2 * MB
    assert b["fixture"] == 3 * MB
    assert b["world_data"] == 4 * MB
    assert b["run_data"] >= 11 * MB, "both seeded databases are attributed to run data"
    assert b["run_data"] - 11 * MB < 64 * 1024, "run_data is not counting anything else"
    assert b["server.log"] == MB
    assert b["build_cache"] == 0
    assert rep["run_count"] == 2
    assert rep["total_on_disk_bytes"] >= 21 * MB
    assert [r["run_id"] for r in rep["runs"]] == ["run-111111111111", "run-222222222222"]
    assert rep["runs"][0]["db_bytes"] == 5 * MB


def test_report_states_free_space_and_the_reserved_headroom(tmp_path, monkeypatch):
    world = _world(tmp_path)
    _make_run(world, "run-111111111111", db_bytes=1 * MB)
    live = tmp_path / "atom.db"
    live.write_bytes(b"\0" * (412 * MB))
    monkeypatch.setattr(SP, "LIVE_DB", live)
    rep = SP.world_storage_report(world, free_probe=world)
    assert rep["free_bytes"] > 0
    assert rep["reserved_headroom_bytes"] >= 412 * MB
    assert rep["usable_after_reserve_bytes"] == max(
        0, rep["free_bytes"] - rep["reserved_headroom_bytes"])
    text = SP.render_report(rep)
    assert "free" in text and "reserved" in text and "breakdown" in text
    assert "run-111111111111" in text


def test_report_warns_when_the_world_has_hard_linked_writables(tmp_path):
    world = _world(tmp_path)
    a = world / "data" / "atom.db"
    a.parent.mkdir(parents=True)
    a.write_bytes(b"\0" * 64)
    os.link(a, world / "data" / "copy.db")
    rep = SP.world_storage_report(world, free_probe=world)
    assert any("hard-linked" in w for w in rep["warnings"])


def test_report_does_not_follow_symlinks_into_a_double_count(tmp_path):
    """backend_root is a farm pointing at code/ and data/. Following it would
    count the world's two largest directories twice and make the total lie."""
    world = _world(tmp_path)
    (world / "code").mkdir()
    (world / "code" / "a.py").write_bytes(b"\0" * 4 * MB)
    (world / "data").mkdir()
    (world / "data" / "atom.db").write_bytes(b"\0" * 6 * MB)
    farm = world / "backend_root"
    farm.mkdir()
    (farm / "code").symlink_to(world / "code")
    (farm / "data").symlink_to(world / "data", target_is_directory=True)
    rep = SP.world_storage_report(world, free_probe=world)
    # 4 MB code + 6 MB data only, not 20 MB.
    assert rep["total_on_disk_bytes"] < 20 * MB
    assert "not followed" in rep["note"]


def test_report_max_runs_bounds_the_listing(tmp_path):
    world = _world(tmp_path)
    for i in range(5):
        _make_run(world, f"run-{i:012d}", db_bytes=1 * MB, age_days=5 - i)
    rep = SP.world_storage_report(world, max_runs=2, free_probe=world)
    assert rep["run_count"] == 2
    assert [r["run_id"] for r in rep["runs"]] == ["run-000000000003", "run-000000000004"]


def test_build_world_produces_the_inventory_instead_of_pruning():
    """The retention path must never delete: no rmtree, and it says so."""
    src = _module_source("run_isolated.py")
    body = _function_source(src, "_prune_old_runs")
    assert "SP.build_inventory" in body
    assert not _destructive_calls(src, "_prune_old_runs"), \
        "the retention path must not delete"
    # The build path reports the inventory and prints the explicit command.
    build = _function_source(src, "build_world")
    assert "_prune_old_runs(world)" in build
    assert "NOTHING DELETED" in build
    assert "apply_inventory" not in build, "a build must never act on the inventory"
    # And the policy's own apply path is the ONLY place that can delete.
    assert _destructive_calls(_module_source("storage_policy.py"), "apply_inventory")


# ===========================================================================
# Cross-cutting: launchers refuse BEFORE the first byte is written.
# ===========================================================================
def test_build_world_checks_space_before_any_mkdir():
    body = _function_source(_module_source("run_isolated.py"), "build_world")
    check_at = body.index("_check_disk_before_world")
    first_mkdir = body.index(".mkdir(")
    assert check_at < first_mkdir, "the refusal must precede every mkdir"
    # ... and the guard's own mkdir-shape check also precedes it.
    assert body.index("assert_worlds_root_usable") < first_mkdir


def test_preview_up_checks_space_before_creating_the_run_dir():
    body = _function_source(_module_source("preview_stack.py"), "cmd_up")
    assert body.index("SP.check_space") < body.index("run_dir.mkdir(")
    assert "SP.InsufficientStorage" in body
    assert "No run directory was created." in body
    # A seeded run database is writable state: it must be its own inode.
    assert "SP.assert_not_hardlinked_writable" in body


def test_preview_status_includes_the_storage_block():
    body = _function_source(_module_source("preview_stack.py"), "cmd_status")
    assert "SP.world_storage_report" in body
    assert 'st["storage"]' in body
    assert "SP.render_report" in body


def test_refusal_is_a_clean_exit_not_a_traceback():
    """A refusal is an expected outcome; it must not surface as a crash."""
    est = SP.SpaceEstimate(target="world:x")
    est.add("fixture", 10 * MB, "measured:t", True)
    with pytest.raises(SP.StoragePolicyError):
        SP.check_space(est, free_bytes=1 * MB)
    assert issubclass(SP.InsufficientStorage, SP.StoragePolicyError)
    assert issubclass(SP.SharedWritableError, SP.StoragePolicyError)
