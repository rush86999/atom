"""Storage policy: space refusal, fixture cost, run retention, shared writables.

These properties are asserted against ``storage_policy`` as it exists, and each
one corresponds to a directive in the storage-policy table:

  * space is checked and refused BEFORE anything is written, with the live
    database's own size, WAL and snapshot floor reserved rather than spent;
  * a world is not created on a full-snapshot fixture unless that was asked for
    explicitly;
  * run retention never removes an active, pinned or evidence-referenced run,
    and applying an inventory requires explicit confirmation;
  * writable state is never shared between worlds.

The first version of this file was written against a parallel local draft of the
module and was replaced when the shared implementation landed; keeping the
assertions and re-pointing them at the shipped API is cheaper than losing the
coverage, which matters because a retention policy that has never been exercised
is exactly the policy that fails silently.
"""
import os
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# The PACKAGE-qualified name, the same one both launchers use. Importing a
# SIBLING copy under the bare name ``storage_policy`` (by putting
# ``scripts/orchestration_acceptance`` on sys.path) loads this same file a
# SECOND time as a different module object, so every constant below would be a
# different object's constant from the one the launcher enforces. That is
# precisely the divergence the single-import rule exists to prevent: a test
# could assert against a ceiling the launcher never applied.
from scripts.orchestration_acceptance import storage_policy as SP  # noqa: E402

MIB = 1024 * 1024


def _make_world(tmp_path: Path, name: str = "w", runs: int = 4) -> Path:
    world = tmp_path / name
    runs_dir = world / "runs"
    for i in range(runs):
        d = runs_dir / f"run-{i:012x}"
        (d / "data").mkdir(parents=True)
        (d / "data" / "atom.db").write_bytes(b"x" * (64 * 1024))
        # A launch-env dump that also records the serving pid, so ownership is
        # positively establishable (idle) rather than unknown.
        (d / "server_env.json").write_text(
            '{"pid": %d, "ATOM_CHAT_STREAMING": "true"}' % (9000 + i))
        (d / "serving_provenance.json").write_text("{}")
        ts = 1_700_000_000 + i * 1000
        os.utime(d, (ts, ts))
    return world


# ---------------------------------------------------------------------------
# 1. space
# ---------------------------------------------------------------------------
def test_check_space_refuses_when_the_live_reserve_would_be_spent(tmp_path):
    est = SP.SpaceEstimate(
        target="world that cannot fit",
        components=[SP.Component(name="code export", bytes=10 * 1024 ** 4,
                                 source="test", measured=False)],
    )
    try:
        SP.check_space(est, free_bytes=2 * 1024 ** 3, free_probe=tmp_path)
    except SP.InsufficientStorage as exc:
        # the refusal must be actionable: a named reason, not a bare failure
        assert str(exc).strip(), "refusal carried no explanation"
        assert "INSUFFICIENT STORAGE" in str(exc)
    else:
        raise AssertionError("a build that cannot fit must be refused")


def test_check_space_allows_a_build_that_fits(tmp_path):
    est = SP.SpaceEstimate(
        target="small world",
        components=[SP.Component(name="code export", bytes=1 * MIB,
                                 source="test", measured=True)],
    )
    report = SP.check_space(est, free_bytes=64 * 1024 ** 3, free_probe=tmp_path)
    assert report.ok is True


def test_estimate_components_carry_a_source(tmp_path):
    """A number nobody can trace is a guess with extra steps."""
    world = _make_world(tmp_path)
    est = SP.estimate_world_build(world, worlds_root=tmp_path)
    assert est.components, "an estimate with no components is not an estimate"
    for comp in est.components:
        assert comp.source, f"component {comp.name} has no source"
        assert comp.bytes > 0, f"component {comp.name} has no size"


# ---------------------------------------------------------------------------
# 2. fixture cost
# ---------------------------------------------------------------------------
def test_full_dev_db_snapshot_requires_the_explicit_flag():
    default = SP.resolve_fixture_source(False)
    explicit = SP.resolve_fixture_source(True)
    assert default.mode == SP.FIXTURE_API_SEEDED
    assert explicit.mode == SP.FIXTURE_FULL_DEV_DB
    assert default.explicit is False and explicit.explicit is True


def test_api_seeded_fixture_is_schema_only_and_small(tmp_path):
    """Built from the app's own metadata: full schema, zero dev rows.

    Copying DDL plus an allowlist of seed rows was the first attempt and it
    drifts from the code under test. Using the declarative metadata keeps the
    schema identical to what the app expects, with no documents, embeddings or
    agent memory -- the ~392 MB the full snapshot carried.
    """
    dest = tmp_path / "fixture.db"
    summary = SP.provision_api_seeded_fixture(dest)
    assert dest.exists(), "no fixture was written"
    size = os.lstat(dest).st_size / MIB
    assert size < 64, f"api-seeded fixture is {size} MiB; it is carrying bulk data"
    con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert len(tables) > 50, f"only {len(tables)} tables; the app schema is missing"
    for t in ("users", "canvases", "documents"):
        if t in tables:
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            assert n == 0, f"schema-only fixture carries {n} dev rows in {t}"
    con.close()
    assert isinstance(summary, dict)


# ---------------------------------------------------------------------------
# 3. run retention
# ---------------------------------------------------------------------------
def test_inventory_classifies_runs_and_drops_nothing_by_itself(tmp_path):
    world = _make_world(tmp_path, runs=4)
    inv = SP.build_inventory(world, cap=2, pid_alive=lambda _pid: False)
    assert inv.cap == 2
    by_id = {e.run_id: e for e in inv.entries}
    assert len(by_id) == 4
    droppable = [e for e in inv.entries if e.classification == SP.CLASS_DROPPABLE]
    assert droppable, "with cap=2 and four idle runs, two must be droppable"
    for e in droppable:
        assert e.reasons, f"{e.run_id} is droppable with no stated reason"
    # nothing has been removed
    assert len(list((world / "runs").iterdir())) == 4


def test_pinned_runs_are_never_droppable(tmp_path):
    world = _make_world(tmp_path, runs=4)
    pinned = "run-000000000000"
    inv = SP.build_inventory(world, cap=2, pinned=[pinned],
                             pid_alive=lambda _pid: False)
    entry = {e.run_id: e for e in inv.entries}[pinned]
    assert entry.classification != SP.CLASS_DROPPABLE
    assert SP.CLASS_PINNED in entry.classification or "pinned" in " ".join(entry.reasons)


def test_evidence_referenced_runs_are_never_droppable(tmp_path):
    import json as _json
    world = _make_world(tmp_path, runs=4)
    # Evidence is a RECORDED RESULT document naming the world and run, which is
    # the format actually on disk -- not a file sitting inside the run.
    results = tmp_path / "results"
    results.mkdir()
    (results / f"{world.name}_2026-09-28.json").write_text(
        _json.dumps({"world": world.name, "run": "run-000000000000", "result": "pass"}))
    inv = SP.build_inventory(world, cap=2, evidence_roots=[results],
                             pid_alive=lambda _pid: False)
    entry = {e.run_id: e for e in inv.entries}["run-000000000000"]
    assert entry.classification != SP.CLASS_DROPPABLE, entry.reasons
    assert entry.evidence_refs, "an evidence-referenced run must say so"


def test_active_run_is_never_droppable(tmp_path):
    import json as _json
    world = _make_world(tmp_path, runs=4)
    # No preview_stack.json: the run's OWN server_env.json records its pid, so a
    # launcher that never wrote world state is still recognised. Two signals
    # because each has been wrong alone.
    (world / "runs" / "run-000000000000" / "server_env.json").write_text(
        _json.dumps({"pid": 4242}))
    inv = SP.build_inventory(world, cap=2, pid_alive=lambda pid: pid == 4242)
    entry = {e.run_id: e for e in inv.entries}["run-000000000000"]
    assert entry.classification != SP.CLASS_DROPPABLE, entry.reasons
    assert any("live pid" in r for r in entry.reasons), entry.reasons


def test_apply_requires_confirmation(tmp_path):
    world = _make_world(tmp_path, runs=4)
    inv = SP.build_inventory(world, cap=2, pid_alive=lambda _pid: False)
    SP.apply_inventory(inv, confirm=False)
    assert len(list((world / "runs").iterdir())) == 4, \
        "apply_inventory removed runs without confirmation"
    # Confirmation alone is no longer sufficient either: deletion needs the
    # maintenance interlock AND a reviewed inventory digest (and refuses
    # outright when the activity inspection was incomplete). The full gate
    # matrix is in tests/core/test_storage_policy_fail_closed.py.
    refused = SP.apply_inventory(inv, confirm=True, world=world,
                                 reviewed_digest=None,
                                 interlock_probe=lambda: (True, "held (injected)"),
                                 state_probe=lambda w: (False, []))
    assert "no reviewed inventory" in refused["refused"]
    assert refused["deleted"] == []
    assert len(list((world / "runs").iterdir())) == 4
    # All three together: cap=2 over four unprotected scratch runs, so the two
    # NEWEST survive.
    # ``remove`` is a collector, so the assertion is on what was PASSED for
    # removal, not on the filesystem: the scratch tree is deliberately left
    # intact so the test cannot destroy anything it did not mean to.
    removed = []
    applied = SP.apply_inventory(inv, confirm=True, world=world,
                                 reviewed_digest=inv.digest,
                                 interlock_probe=lambda: (True, "held (injected)"),
                                 state_probe=lambda w: (False, []),
                                 remove=removed.append)
    assert not applied.get("refused"), applied.get("refused")
    assert [p.name for p in removed] == ["run-000000000000", "run-000000000001"]
    assert applied["deleted"] == ["run-000000000000", "run-000000000001"]
    assert len(list((world / "runs").iterdir())) == 4


def test_active_runs_are_retained_regardless_of_cap(tmp_path):
    """Pins the retention semantics, which are stricter than "keep the newest N".

    ``cap`` bounds how many PINNED/EVIDENCE runs are retained. An ACTIVE run is
    never a deletion candidate no matter how many accumulate, because deleting a
    run a live process has open is the one outcome a cleanup pass must never
    produce. So a world with five live runs keeps all five even at cap=2, and
    the reclaimable set is empty until those processes actually stop.

    The related hazard is deliberately surfaced rather than hidden: a run is
    "protected" only while something positively identifies it. A world whose
    ``preview_stack.json`` and every ``server_env.json`` have been lost has no
    protected runs, so even its newest run is offered for deletion. That is why
    ``apply_inventory`` is gated on an explicit confirm.
    """
    import json as _json
    world = _make_world(tmp_path, runs=5)
    for i in range(5):
        (world / "runs" / f"run-{i:012x}" / "server_env.json").write_text(
            _json.dumps({"pid": 100 + i}))
    inv = SP.build_inventory(world, cap=2, pid_alive=lambda _pid: True)
    assert len(inv.entries) == 5
    for e in inv.entries:
        assert e.classification != SP.CLASS_DROPPABLE, \
            f"{e.run_id} is active but was offered for deletion"
    # nothing is reclaimable while every run is in use
    SP.apply_inventory(inv, confirm=True)
    assert len(list((world / "runs").iterdir())) == 5, \
        "an active run was removed"


def test_pinned_runs_are_retained_independently_of_the_cap(tmp_path):
    """A pin is an absolute promise, not a slot in a retention budget.

    The cap bounds how many *unprotected* scratch runs are kept. A pinned run is
    never a deletion candidate however many accumulate, so a pin cannot be
    starved by a busy day the way a "keep newest N of everything" rule would
    allow.
    """
    world = _make_world(tmp_path, runs=5)
    pinned = [f"run-{i:012x}" for i in range(5)]
    inv = SP.build_inventory(world, cap=2, pinned=pinned,
                             pid_alive=lambda _pid: False)
    SP.apply_inventory(inv, confirm=True)
    left = {p.name for p in (world / "runs").iterdir()}
    assert left == set(pinned), f"a pinned run was removed; left {left}"


# ---------------------------------------------------------------------------
# 5. unknown ownership is NOT evidence of safety
# ---------------------------------------------------------------------------
def test_run_without_ownership_evidence_is_review_required(tmp_path):
    """Absent evidence must not be read as permission.

    A run whose ownership cannot be established is UNKNOWN, not idle. The
    earlier version classified "no ownership record" as droppable, on the
    reasoning that retaining by default was the safe direction. That is
    backwards: retention by default only protects anything if the inventory is
    reliable, and `--confirm-drop` records consent without repairing an
    inventory that cannot tell idle from unexamined.
    """
    world = _make_world(tmp_path, runs=3)
    # every run has a launch-env dump but NO pid: ownership unestablished
    for run in (world / "runs").iterdir():
        (run / "server_env.json").write_text('{"ATOM_CHAT_STREAMING": "true"}')
    inv = SP.build_inventory(world, cap=1, pid_alive=lambda _p: False)
    for e in inv.entries:
        if e.classification == SP.CLASS_DROPPABLE:
            raise AssertionError(
                f"{e.run_id} is droppable with no ownership evidence: {e.reasons}")
    assert any(e.classification == SP.CLASS_REVIEW for e in inv.entries), \
        "runs with unknown ownership must be review-required"


def test_review_required_runs_survive_confirmed_cleanup(tmp_path):
    """Confirmation authorises deletion; it does not manufacture evidence.

    Stronger than the previous version of this test, which expected the idle
    sibling to be deleted while the review-required runs survived. A run whose
    ownership cannot be established is not a smaller deletion set: it makes the
    whole inventory unauthorisable, because the inventory is what says what is
    being removed. So NOTHING is removed, the refusal says why, and the
    review-required runs are named in the report.
    """
    import json as _json
    world = _make_world(tmp_path, runs=4)
    for i, run in enumerate(sorted((world / "runs").iterdir())):
        if i == 0:
            (run / "server_env.json").write_text(
                _json.dumps({"pid": 999}))          # recorded, dead -> idle
        else:
            (run / "server_env.json").write_text('{"ATOM_CHAT_STREAMING": "true"}')
    inv = SP.build_inventory(world, cap=0, pid_alive=lambda _p: False)
    entry = {e.run_id: e for e in inv.entries}["run-000000000000"]
    # The idle sibling is NOT promoted to droppable either: with three runs
    # unclassifiable, retention is simply not enforced and nothing is a
    # candidate. (cap=0 so every run is outside the window; with a cap the
    # newest runs are retained by age before ownership is even consulted.)
    assert entry.classification == SP.CLASS_WITHIN_CAP, entry.reasons
    assert "retention NOT enforced" in " ".join(entry.reasons)
    assert inv.deletion_candidates() == []
    removed = []
    result = SP.apply_inventory(inv, confirm=True, world=world,
                                reviewed_digest=inv.digest,
                                interlock_probe=lambda: (True, "held (injected)"),
                                state_probe=lambda w: (False, []),
                                remove=removed.append)
    assert removed == [], "an unclassifiable run must block the whole pass"
    assert "activity inspection incomplete" in result["refused"]
    assert result.get("review_required"), "review-required runs must be reported"
    assert {r["run_id"] for r in result["review_required"]} == {
        "run-000000000001", "run-000000000002", "run-000000000003"}
    assert len(list((world / "runs").iterdir())) == 4


def test_recorded_dead_pid_makes_a_run_idle_and_droppable(tmp_path):
    import json as _json
    world = _make_world(tmp_path, runs=4)
    for i, run in enumerate(sorted((world / "runs").iterdir())):
        (run / "server_env.json").write_text(
            _json.dumps({"pid": 500 + i}))
    inv = SP.build_inventory(world, cap=1, pid_alive=lambda _p: False)
    oldest = "run-000000000000"
    entry = {e.run_id: e for e in inv.entries}[oldest]
    assert entry.classification == SP.CLASS_DROPPABLE, entry.reasons
    assert any("not running" in r for r in entry.reasons), entry.reasons
