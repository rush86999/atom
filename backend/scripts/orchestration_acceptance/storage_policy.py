#!/usr/bin/env python3
"""Storage policy for the isolated acceptance harness.

Why this module exists
----------------------
Measured on this box on 2026-09-28:

* one world costs ~130 MB of code export, ~392 MB of frozen fixture,
  ~394 MB of world data, ~230-320 MB of frontend build cache, and
  **~400-550 MB per run directory** — every run gets its own writable
  `data/atom.db` seeded from the fixture. Twenty worlds with a couple of
  dozen runs each is how 80 GB accumulated, and the retention rule was
  "delete by hand when the disk complains".
* the live dev database is ~412 MB and growing, its WAL reached 4 MB
  within minutes, and `core/db_safety.py` refuses to snapshot below an
  `ATOM_DB_SNAPSHOT_MIN_FREE_MB` floor (default 500 MB). A world build that
  fills the last gigabyte therefore breaks the *live* DB's safety net, not
  just its own world.
* the previous inline attempt at this policy (`run_isolated.py`, "review
  round 37") had three defects this module replaces: a hardcoded 500 MB
  estimate, a hardcoded 20 GB headroom unrelated to the live DB, and a
  `_prune_old_runs()` that called `shutil.rmtree(..., ignore_errors=True)`
  **unattended, with no inventory, no confirmation and no exclusions**.

The policy it implements (from the storage-policy table):

    daily debugging      one small API-seeded fixture; reuse its world
    browser preview      one persistent world
    final acceptance     one frozen candidate, built only when needed
    historical evidence  keep manifests/results/logs/screenshots; archive
                         required databases separately
    large compat tests   portable drive, with the existing storage guard

Design rules
------------
* **Refuse before the first byte is written.** Every check is called ahead
  of any `mkdir`/`copy`, and a refusal is a named, actionable message — not
  a traceback halfway through a 400 MB copy.
* **Estimate from measured sizes, and say which.** Every component of an
  estimate carries a `source` string: either the path it was measured from
  or the reason it could not be. A number nobody can trace is a guess with
  extra steps.
* **Free space is injectable.** Tests simulate exhaustion deterministically
  instead of filling a real disk, and the caller can pass a probe.
* **The live database is reserved for, not spent on.** The headroom is the
  live DB plus its WAL plus the `db_safety` snapshot floor, all read at
  call time, so a world build can never be the thing that silences the live
  DB's safety net.
* **No unattended broad removal.** Cleanup produces an inventory and exits.
  Deletion requires ALL THREE, and none substitutes for another: an explicit
  confirmation flag, the ``core.world_storage_guard`` maintenance interlock
  held, and the digest of an inventory a human actually read. Runs classified
  ``droppable`` are the only candidates; active, pinned, evidence-referenced
  and ownership-unknown runs never are, and the exclusion is stored as data
  (``RunEntry.protection``) so no flag can switch it off.
* **An incomplete inspection is a refusal, not a smaller deletion set.**
  Every unreadable world state, unreadable run manifest, unparseable
  document, unperformable pid check and truncated scan is recorded in
  ``Inventory.inspection_problems``, and ``apply_inventory`` refuses outright
  when that list is non-empty. The failure mode this replaces read a raised
  ``OSError`` as "not active".
* **Deletion never overlaps a build or a run.** ``apply_inventory`` checks the
  build marker, the per-run live marker, the launcher registry and
  ``preview_stack.json``'s pid, and fails closed when any of them cannot be
  read.
* **Writable state is never shared.** Only the immutable code export may be
  shared (read-only, content-addressed by `code_manifest.json`). Databases,
  logs and frontend build caches are per world, and a writable database is
  never hard-linked into a shared export — two writers on one inode is how
  one world silently corrupts another (the AGENTS.md "shared inodes" class).

Commands:
    python -m scripts.orchestration_acceptance.storage_policy space --world W
    python -m scripts.orchestration_acceptance.storage_policy inventory --world W
    python -m scripts.orchestration_acceptance.storage_policy cleanup --world W
    python -m scripts.orchestration_acceptance.storage_policy report --world W

Deleting requires the interlock AND a reviewed digest:

    python -m core.world_storage_guard lock --reason 'retention'
    python -m scripts.orchestration_acceptance.storage_policy inventory --world W
    # a human reads the output, then:
    python -m scripts.orchestration_acceptance.storage_policy cleanup --world W \
        --confirm-drop --reviewed-digest <digest printed above>

World creation and deletion are currently PAUSED by explicit user instruction.
This module produces inventories and proofs; it does not execute deletions on
its own, and no caller does either.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# backend/scripts/orchestration_acceptance/storage_policy.py -> backend/
BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
WORLDS_ROOT = BACKEND / "data" / "acceptance_worlds"
RESULTS_ROOT = BACKEND / "data" / "acceptance_worlds_results"
ACC = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
LIVE_DB = BACKEND / "data" / "atom.db"
FRONTEND = REPO / "frontend-nextjs"

MB = 1024 * 1024
GB = 1024 * MB

#: Run directories are ``<world>/runs/run-<12 hex>`` (see
#: ``run_isolated.launch_server``). The token is the run's identity in every
#: record that references it, so evidence detection keys on it directly.
RUN_ID_RE = re.compile(r"run-[0-9a-f]{12}")

# Per-launch artifacts: written every time a server starts, and they embed the
# run's own database path. They are authoritative for "is this run being served"
# but must never make a run evidence-bearing for retention purposes.
PER_LAUNCH_ARTIFACTS = frozenset({
    "server_env.json", "serving_provenance.json", "db_fingerprint.json",
})

#: The opt-in name for copying the full live dev database into a world.
#: Deliberately long: it must be impossible to type by accident, and it must
#: name what it costs in the help text -- it copies the ENTIRE live dev
#: database, not a subset of it. Measured 2026-09-28:
#: ``data/atom.db`` = 413,360,128 bytes, and the fixture the pre-policy default
#: produced was 410,861,568 bytes (see :func:`measured_fixture_bytes`).
FULL_DEV_DB_FLAG = "--full-dev-db-snapshot"

#: Hard ceiling on the DEFAULT fixture, in bytes. The default is built by
#: :func:`provision_api_seeded_fixture`, which emits the app's own DDL and zero
#: dev rows: 8,478,720 bytes measured 2026-09-28 (367 tables, 0 rows, 0 free
#: pages). 32 MB leaves ~3.8x headroom for DDL growth while still being ~13x
#: smaller than the live database, so a regression back to "copy the live file
#: and prune it" trips this rather than passing quietly. Enforced by
#: :func:`provision_api_seeded_fixture` itself and asserted by the test suite.
SMALL_FIXTURE_MAX_BYTES = 32 * MB

#: Fallbacks used ONLY when a component cannot be measured. Each carries a
#: `source` string in the report so a reader can tell a fallback from a
#: measurement. The numbers are the ones measured on this box (see module
#: docstring) rounded up.
FALLBACK_CODE_EXPORT_BYTES = 140 * MB     # measured 130 MB
FALLBACK_BUILD_CACHE_BYTES = 320 * MB     # measured 228-321 MB
FALLBACK_LIVE_DB_BYTES = 420 * MB         # measured 412 MB
FALLBACK_FULL_DEV_DB_BYTES = 500 * MB     # the old hardcoded guess, kept only
                                         # for an unreadable live DB
#: A schema-only, API-seeded world: 367 tables, measured 8.1 MB empty, so
#: this ceiling is ~4x the measured empty schema.
FALLBACK_SMALL_FIXTURE_BYTES = 32 * MB

#: Run directories retained per world once active/pinned/evidence runs are
#: excluded. Not a suggestion about how much disk is fine — that is the
#: space check's job. This is the count of *convenience* history.
DEFAULT_RUN_CAP = 5

CLASS_DROPPABLE = "droppable"
CLASS_ACTIVE = "retained-active"
CLASS_PINNED = "retained-pinned"
CLASS_EVIDENCE = "retained-evidence"
#: Inside the cap, but not active/pinned/evidence. Not droppable — it simply
#: has not aged out. Reported separately rather than mislabelled
#: "retained-active", which would be a lie about why it survived.
CLASS_WITHIN_CAP = "retained-within-cap"

#: A run whose ownership could not be established is NOT a deletion candidate.
#:
#: The distinction this encodes is the whole point: a run with a recorded,
#: dead pid is *known* to be idle, while a run with no ownership record is
#: *unknown*. An earlier version treated "unknown" as "safe", on the reasoning
#: that erring toward retention was the safe direction. That is backwards.
#: Retention by default is only protective if the inventory is RELIABLE; an
#: inventory that classifies "we could not tell" as "safe to delete" offers its
#: least-understood runs for removal, and `--confirm-drop` does not make an
#: unreliable inventory reliable -- it only records that someone said yes.
#: Missing ownership evidence is therefore its own class, excluded from
#: ordinary cleanup and requiring a separate, explicit decision.
CLASS_REVIEW = "review-required"

#: Written where a world declares runs that must survive cleanup regardless
#: of age. Lives INSIDE the world on purpose: a pin belongs to the world it
#: pins, and the worlds tree is the only thing that is self-describing.
PIN_FILE = "pinned_runs.json"

#: Written by ``run_isolated.build_world`` for the duration of a world build,
#: and removed on the way out. A build rewrites the fixture, the code export
#: and the symlink farm, so a cleanup that overlaps one is deleting a directory
#: a live process is writing into. The marker is real state, not a convention:
#: :func:`world_in_progress` reads it, and a build that crashes leaves it
#: behind so the next cleanup refuses and says why.
BUILD_MARKER = "build_in_progress.json"

#: The live-run marker a launcher drops in a run directory while its server is
#: up. Read by :func:`world_in_progress` as a second, pid-independent signal.
RUN_LIVE_MARKER = "run_live"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class StoragePolicyError(RuntimeError):
    """Base class. Every refusal here is expected and actionable, so
    launchers convert it into a clean non-zero exit rather than a
    traceback (same reasoning as ``world_storage_guard.guarded_entry``)."""


class InsufficientStorage(StoragePolicyError):
    """Not enough free space to create a world/run. Raised BEFORE any
    bytes are written."""


class SharedWritableError(StoragePolicyError):
    """Writable state was found inside a shared (immutable) export, or a
    writable database is hard-linked into a shared tree."""


class DeletionRefused(StoragePolicyError):
    """A deletion was requested that the policy will not perform.

    Every reason this is raised is a reason the operator has to fix before
    anything is removed: no maintenance interlock, no reviewed inventory, a
    build or run in progress, or an activity inspection that could not
    complete. The message names which one, because "it said no" without a
    reason is indistinguishable from a crash.
    """


# ---------------------------------------------------------------------------
# Measurement primitives
# ---------------------------------------------------------------------------
def _existing_ancestor(path: Path) -> Path:
    """Nearest existing ancestor of ``path``.

    A world that has not been created yet has no directory to stat, and
    ``os.statvfs`` raises on a missing path. The space check runs BEFORE the
    ``mkdir`` by design, so this is the normal case, not an edge case.
    """
    p = Path(path)
    for candidate in [p, *p.parents]:
        if candidate.exists():
            return candidate
    return Path("/")


def real_free_bytes(path: Path) -> int:
    """Bytes available to an unprivileged writer on ``path``'s filesystem."""
    probe = _existing_ancestor(Path(path))
    vfs = os.statvfs(str(probe))
    return int(vfs.f_bavail) * int(vfs.f_frsize)


def dir_usage(path: Path) -> Dict[str, Any]:
    """Apparent and on-disk size of a tree, in one walk.

    ``st_blocks * 512`` is the number that matters for "will this fill the
    disk"; summing ``st_size`` reports what the files claim to be, which
    undercounts sparse files and, for a hard-linked file counted through
    two paths, overcounts. Both are reported, and hard links are surfaced as
    their own warning rather than silently reconciled — a writable database
    reachable through two inodes is a bug, not a rounding difference.

    Symlinks are NOT followed. ``backend_root`` is a farm of symlinks into
    ``code/`` and ``data/``, so following them would double-count the two
    largest directories in a world and make the breakdown lie.
    """
    apparent = 0
    on_disk = 0
    files = 0
    dirs = 0
    hardlinked: List[str] = []
    root = Path(path)
    if not root.exists():
        return {"apparent_bytes": 0, "on_disk_bytes": 0, "files": 0,
                "dirs": 0, "hardlinked": []}
    stack: List[Path] = [root]
    while stack:
        d = stack.pop()
        dirs += 1
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    files += 1
                    apparent += st.st_size
                    on_disk += getattr(st, "st_blocks", 0) * 512
                    if st.st_nlink > 1:
                        hardlinked.append(entry.path)
        except OSError:
            continue
    return {"apparent_bytes": apparent, "on_disk_bytes": on_disk,
            "files": files, "dirs": dirs, "hardlinked": hardlinked}


def size_of(path: Path) -> Optional[int]:
    """On-disk size of a file or tree, or ``None`` when it does not exist."""
    p = Path(path)
    if not p.exists():
        return None
    if p.is_file():
        try:
            st = p.stat()
            return getattr(st, "st_blocks", 0) * 512 or st.st_size
        except OSError:
            return None
    return dir_usage(p)["on_disk_bytes"]


def file_size(path: Path) -> Optional[int]:
    p = Path(path)
    try:
        return p.stat().st_size if p.is_file() else None
    except OSError:
        return None


def measured_fixture_bytes(path: Path) -> Dict[str, Any]:
    """Report a fixture's size and HOW it was measured.

    ``os.stat`` only. The live dev database is never opened here — a separate
    lane owns live-database protection, and an accidental read of a 412 MB WAL
    database is not a measurement anybody needs.
    """
    p = Path(path)
    try:
        st = os.stat(p)
    except OSError as exc:
        return {"path": str(p), "bytes": None, "method": "os.stat",
                "error": str(exc)}
    return {"path": str(p), "bytes": int(st.st_size), "method": "os.stat",
            "blocks_bytes": int(getattr(st, "st_blocks", 0)) * 512}


def snapshot_floor_bytes() -> int:
    """The floor below which ``core/db_safety`` refuses to snapshot the live DB.

    Read from ``db_safety`` itself rather than duplicated, so the space
    check and the snapshotter can never disagree about how much room the
    live database needs. Falls back to the same env var and the same default
    if the import fails.
    """
    try:
        from core.db_safety import _min_free_bytes  # type: ignore

        return int(_min_free_bytes())
    except Exception:
        try:
            return int(float(os.getenv("ATOM_DB_SNAPSHOT_MIN_FREE_MB", "500")) * MB)
        except ValueError:
            return 500 * MB


# ---------------------------------------------------------------------------
# Space accounting
# ---------------------------------------------------------------------------
@dataclass
class Component:
    """One measured (or explicitly-fallback) term of an estimate."""

    name: str
    bytes: int
    source: str
    measured: bool

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "bytes": self.bytes,
                "source": self.source, "measured": self.measured}


@dataclass
class SpaceEstimate:
    """What the operation is about to need, and where each number came from."""

    target: str
    components: List[Component] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(c.bytes for c in self.components)

    def add(self, name: str, bytes_: int, source: str, measured: bool) -> Component:
        c = Component(name, int(bytes_), source, measured)
        self.components.append(c)
        return c

    def as_dict(self) -> Dict[str, Any]:
        return {"target": self.target, "total_bytes": self.total_bytes,
                "components": [c.as_dict() for c in self.components]}


@dataclass
class Headroom:
    """Space reserved for the LIVE database, which a world build must not
    spend. Not a policy knob: every term is measured or read from
    ``db_safety``, so this is what the live lane actually needs right now."""

    live_db: Component
    live_wal: Component
    snapshot_floor: Component

    @property
    def total_bytes(self) -> int:
        return self.live_db.bytes + self.live_wal.bytes + self.snapshot_floor.bytes

    def as_dict(self) -> Dict[str, Any]:
        return {"total_bytes": self.total_bytes,
                "live_db": self.live_db.as_dict(),
                "live_wal": self.live_wal.as_dict(),
                "snapshot_floor": self.snapshot_floor.as_dict()}


@dataclass
class SpaceReport:
    estimate: SpaceEstimate
    headroom: Headroom
    free_bytes: int
    free_bytes_source: str
    probe_path: Path

    @property
    def required_bytes(self) -> int:
        return self.estimate.total_bytes + self.headroom.total_bytes

    @property
    def ok(self) -> bool:
        return self.free_bytes >= self.required_bytes

    @property
    def shortfall_bytes(self) -> int:
        return max(0, self.required_bytes - self.free_bytes)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "target": self.estimate.target,
            "ok": self.ok,
            "required_bytes": self.required_bytes,
            "free_bytes": self.free_bytes,
            "free_bytes_source": self.free_bytes_source,
            "probe_path": str(self.probe_path),
            "shortfall_bytes": self.shortfall_bytes,
            "estimate": self.estimate.as_dict(),
            "headroom": self.headroom.as_dict(),
        }

    def message(self) -> str:
        est = ", ".join(
            f"{c.name} {human(c.bytes)}" + ("" if c.measured else "*")
            for c in self.estimate.components
        )
        h = self.headroom
        parts = [
            "INSUFFICIENT STORAGE — refusing to create anything.",
            f"  target  : {self.estimate.target}",
            f"  need    : {human(self.estimate.total_bytes)}  ({est})",
            f"  reserve : {human(h.total_bytes)}  (live DB {human(h.live_db.bytes)}"
            f" + WAL {human(h.live_wal.bytes)}"
            f" + db_safety snapshot floor {human(h.snapshot_floor.bytes)})",
            f"  free    : {human(self.free_bytes)} at {self.probe_path}"
            f"  ({self.free_bytes_source})",
            f"  SHORT BY: {human(self.shortfall_bytes)}",
        ]
        if any(not c.measured for c in self.estimate.components):
            parts.append("  (*) estimate fell back to a documented default; "
                         "see each component's 'source'.")
        parts += [
            "  The reserve is NOT optional: the live dev database needs it, and",
            "  a world build that consumes it silently disables the live lane's",
            "  db_safety snapshots. Reclaim space first:",
            "    python -m scripts.orchestration_acceptance.storage_policy "
            "inventory --world <W>   # see what is droppable",
            "  or move large compatibility worlds to the portable drive.",
            "  Nothing was created and nothing was written.",
        ]
        return "\n".join(parts)


def human(n: float) -> str:
    for unit, div in (("TB", GB * 1024), ("GB", GB), ("MB", MB), ("kB", 1024)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{int(n)} B"


def live_db_headroom(live_db: Path = LIVE_DB) -> Headroom:
    """Measure the live database, its WAL, and read the snapshot floor."""
    live_db = Path(live_db)
    db_bytes = file_size(live_db)
    if db_bytes is None:
        c_db = Component("live_db", FALLBACK_LIVE_DB_BYTES,
                         f"fallback: live db unreadable at {live_db}", False)
    else:
        c_db = Component("live_db", db_bytes, f"measured:{live_db}", True)
    wal = Path(str(live_db) + "-wal")
    wal_bytes = file_size(wal)
    if wal_bytes is None:
        c_wal = Component("live_wal", 0, f"measured:absent ({wal})", True)
    else:
        c_wal = Component("live_wal", wal_bytes, f"measured:{wal}", True)
    floor = snapshot_floor_bytes()
    c_floor = Component("snapshot_floor", floor,
                        "core.db_safety.ATOM_DB_SNAPSHOT_MIN_FREE_MB", True)
    return Headroom(live_db=c_db, live_wal=c_wal, snapshot_floor=c_floor)


def sibling_worlds(world: Path, worlds_root: Path = WORLDS_ROOT) -> List[Path]:
    root = Path(worlds_root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and p.name != Path(world).name)


def _measure_sibling(world: Path, worlds_root: Path, rel: str) -> Tuple[Optional[int], str]:
    """Measure ``<sibling>/<rel>`` across existing worlds.

    A sibling is a *measurement* of the same thing this world is about to
    write, which is strictly better evidence than a constant. The first
    sibling that yields a non-zero size wins, and its path is recorded.
    """
    for sib in sibling_worlds(world, worlds_root):
        target = sib / rel
        if not target.exists():
            continue
        size = size_of(target)
        if size:
            return size, f"measured:{target}"
    return None, f"unavailable:no sibling world has {rel}"


def _measure_sibling_run(world: Path, worlds_root: Path) -> Tuple[Optional[int], str]:
    """Measure the median data/ size of existing run dirs in sibling worlds."""
    samples: List[int] = []
    source_paths: List[str] = []
    for sib in sibling_worlds(world, worlds_root):
        runs = sib / "runs"
        if not runs.is_dir():
            continue
        for run in sorted(runs.glob("run-*"))[:12]:
            data = run / "data"
            if not data.is_dir():
                continue
            n = size_of(data)
            if n:
                samples.append(n)
                source_paths.append(str(data))
        if len(samples) >= 5:
            break
    if not samples:
        return None, "unavailable:no sibling run data found"
    samples.sort()
    return samples[len(samples) // 2], (
        f"measured:median of {len(samples)} sibling run data dirs "
        f"(e.g. {source_paths[0]})")


def _measure_build_cache(world: Path) -> Tuple[Optional[int], str]:
    for sib in sibling_worlds(world, WORLDS_ROOT):
        if not (sib / "code").exists():
            continue
        base = FRONTEND / ".preview-instance" / sib.name
        if not base.is_dir():
            continue
        for d in sorted(base.glob(".next-preview-*")):
            n = size_of(d)
            if n:
                return n, f"measured:{d}"
    for d in sorted((FRONTEND / ".preview-instance").glob("*/.next-preview-*"))[:1]:
        n = size_of(d)
        if n:
            return n, f"measured:{d}"
    return None, "unavailable:no frontend distDir found"


def estimate_world_build(
    world: Path,
    *,
    full_dev_db: bool = False,
    worlds_root: Path = WORLDS_ROOT,
    with_build_cache: bool = True,
    with_run_data: bool = True,
) -> SpaceEstimate:
    """Estimate what building ``world`` is about to write.

    Components, in the order they are written:

    ``fixture``
        The frozen fixture database. Full dev DB by explicit opt-in
        (measured from the live file) or the small API-seeded fixture.
    ``code_export``
        The immutable code export. 0 when it is shared with a world that
        already holds this revision (see :func:`link_shared_export`).
    ``run_data``
        The first run's writable data directory, measured from sibling runs
        because that is what a run actually costs (~400-540 MB each).
    ``build_cache``
        The frontend distDir, which is per world by policy and measured
        from a sibling world when one exists.
    """
    world = Path(world)
    est = SpaceEstimate(target=f"world:{world.name}")

    fixture = size_of(world / "fixture" / "atom.db")
    if full_dev_db:
        live = file_size(LIVE_DB)
        if live is not None:
            est.add("fixture", live, f"measured:{LIVE_DB} (full dev snapshot)", True)
        else:
            est.add("fixture", FALLBACK_FULL_DEV_DB_BYTES,
                    f"fallback: live db unreadable at {LIVE_DB}", False)
    elif fixture:
        est.add("fixture", fixture, f"measured:{world / 'fixture' / 'atom.db'}", True)
    else:
        est.add("fixture", FALLBACK_SMALL_FIXTURE_BYTES,
                "fallback: schema-only API-seeded fixture (8.1 MB measured empty)", False)

    if (world / "code").is_symlink():
        est.add("code_export", 0, "shared-export:symlinked, nothing copied", True)
    else:
        size, source = _measure_sibling(world, worlds_root, "code")
        if size is None:
            size, source = FALLBACK_CODE_EXPORT_BYTES, (
                "fallback:no sibling world has a code export")
        est.add("code_export", size, source, source.startswith("measured:"))

    if with_run_data:
        # Per-run cost, not per-world: measure an actual run dir when one
        # exists, else fall back to the fixture (a run is seeded from it,
        # so the fixture size is the floor, not a wild guess).
        run_sample, run_source = _measure_sibling_run(world, worlds_root)
        if run_sample:
            est.add("run_data", run_sample, run_source, True)
        else:
            base = est.components[0].bytes if est.components else FALLBACK_LIVE_DB_BYTES
            est.add("run_data", base,
                    "fallback: no measured run data; a run is seeded from the "
                    "fixture, so the fixture size is the floor", False)

    if with_build_cache:
        size, source = _measure_build_cache(world)
        if size:
            est.add("build_cache", size, source, True)
        else:
            est.add("build_cache", FALLBACK_BUILD_CACHE_BYTES,
                    "fallback:no measured frontend distDir on this box", False)
    return est


def estimate_new_run(world: Path, *, worlds_root: Path = WORLDS_ROOT,
                     with_build_cache: bool = False) -> SpaceEstimate:
    """Estimate one more run directory inside an existing world."""
    world = Path(world)
    est = SpaceEstimate(target=f"run:{world.name}")
    fixture = size_of(world / "fixture" / "atom.db")
    if fixture:
        est.add("run_data", fixture, f"measured:{world / 'fixture' / 'atom.db'}", True)
    else:
        sample, source = _measure_sibling_run(world, worlds_root)
        if sample:
            est.add("run_data", sample, source, True)
        else:
            est.add("run_data", FALLBACK_FULL_DEV_DB_BYTES,
                    "fallback:no measured run data on this box", False)
    if with_build_cache:
        size, source = _measure_build_cache(world)
        est.add("build_cache",
                size or FALLBACK_BUILD_CACHE_BYTES,
                source if size else "fallback:no measured frontend distDir", bool(size))
    return est


def _probe_for(target: str) -> Path:
    """The directory whose filesystem the target will be created on."""
    if target.startswith("world:") or target.startswith("run:"):
        return WORLDS_ROOT
    return BACKEND


def check_space(
    estimate: SpaceEstimate,
    *,
    free_bytes: Optional[int] = None,
    free_probe: Optional[Path] = None,
    headroom: Optional[Headroom] = None,
) -> SpaceReport:
    """Refuse creation when the estimate plus reserved headroom will not fit.

    ``free_bytes`` is the injection point the tests use: exhaustion is
    simulated, never produced by filling a real disk.
    """
    probe = Path(free_probe) if free_probe else _probe_for(estimate.target)
    if free_bytes is None:
        free = real_free_bytes(probe)
        source = "statvfs"
    else:
        free = int(free_bytes)
        source = "injected"
    report = SpaceReport(estimate=estimate, headroom=headroom or live_db_headroom(),
                         free_bytes=free, free_bytes_source=source, probe_path=probe)
    if not report.ok:
        raise InsufficientStorage(report.message())
    return report


# ---------------------------------------------------------------------------
# Item 2: the full dev database is opt-in
# ---------------------------------------------------------------------------
FIXTURE_API_SEEDED = "api-seeded-fixture"
FIXTURE_FULL_DEV_DB = "full-dev-db-snapshot"


@dataclass
class FixtureSource:
    """Which database a world is seeded from, and why."""

    mode: str
    explicit: bool
    note: str

    @property
    def is_full_dev_db(self) -> bool:
        return self.mode == FIXTURE_FULL_DEV_DB

    def as_dict(self) -> Dict[str, Any]:
        return {"mode": self.mode, "explicit": self.explicit, "note": self.note}

    def banner(self) -> str:
        if self.is_full_dev_db:
            return (f"[fixture] MODE={FIXTURE_FULL_DEV_DB} (explicit {FULL_DEV_DB_FLAG}): "
                    "copying the ENTIRE live dev database into this world "
                    "(413,360,128 bytes measured 2026-09-28 — a whole-file copy, "
                    "not a subset). Expect ~392 MB per world and ~391 MB per run "
                    "directory seeded from it, and the world will inherit whatever "
                    "the dev lane has accumulated.")
        return (f"[fixture] MODE={FIXTURE_API_SEEDED} (default): small API-seeded "
                f"fixture (app schema, no dev rows; 8.5 MB measured, hard ceiling "
                f"{human(SMALL_FIXTURE_MAX_BYTES)}). Pass "
                f"{FULL_DEV_DB_FLAG} only for a case that genuinely needs dev data.")


def resolve_fixture_source(full_dev_db: bool = False) -> FixtureSource:
    """Default to the small API-seeded fixture; full dev DB only on request.

    The failure this closes: ``build_world`` copied the whole live
    ``data/atom.db`` into every world by default, and every run directory
    was then seeded from that 392 MB fixture. A debugging world therefore
    cost gigabytes it never used, and every debugging run also inherited
    whatever the dev lane happened to contain — including the dev admin's
    ``users.hashed_password``, which the harness deliberately does NOT
    scrub.

    "API-seeded" here means: the fixture carries the app's OWN schema (every
    table the code under test declares) and zero dev rows, so the world is
    provisioned the way a fresh deployment is and then populated through
    the app's public boundary. It is not a byte copy of anybody's database,
    and it never opens the live one.
    """
    if full_dev_db:
        return FixtureSource(
            FIXTURE_FULL_DEV_DB, True,
            f"operator passed {FULL_DEV_DB_FLAG}: snapshot the live dev database")
    return FixtureSource(
        FIXTURE_API_SEEDED, False,
        "default: schema-provisioned API-seeded fixture; no dev rows copied")


def provision_api_seeded_fixture(fixture_db: Path) -> Dict[str, Any]:
    """Create a schema-only, API-seeded fixture database at ``fixture_db``.

    Uses the application's own declarative metadata (367 tables on this
    revision), so the schema is the one the code under test expects — no
    schema-sync drift, no ``dataset_entries`` row pointing at the live sheet
    store, and no dev rows.

    It writes through a NEW engine pointed at the fixture file. It never
    opens, queries or creates tables in the live dev database, which is the
    documented LIVE-DB-WIPE accident (AGENTS.md, 2026-09-04): importing
    ``core.database`` constructs that engine lazily and this function never
    uses it.

    Returns a record of what was created, which the caller stores in the
    world manifest so a later run can tell which fixture mode produced it.
    """
    import sqlite3 as _sq

    from sqlalchemy import create_engine

    fixture_db = Path(fixture_db)
    fixture_db.parent.mkdir(parents=True, exist_ok=True)
    if fixture_db.exists():
        fixture_db.unlink()
        for sidecar in ("-wal", "-shm"):
            Path(str(fixture_db) + sidecar).unlink(missing_ok=True)

    import core.database as cd
    import core.models  # noqa: F401  (registers the model tables)

    engine = create_engine(f"sqlite:///{fixture_db}")
    try:
        cd.Base.metadata.create_all(engine)
        tables = sorted(cd.Base.metadata.tables)
    finally:
        engine.dispose()

    con = _sq.connect(str(fixture_db))
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        free_pages = con.execute("PRAGMA freelist_count").fetchone()[0]
    finally:
        con.close()
    if integrity != "ok":
        raise StoragePolicyError(
            f"provisioned fixture failed integrity_check: {integrity} ({fixture_db})")
    size_bytes = fixture_db.stat().st_size
    if size_bytes > SMALL_FIXTURE_MAX_BYTES:
        # Not a warning. The claim this module makes -- "the default is
        # genuinely small" -- is only true if the size is enforced, and a
        # silently-large default is how 412 MB came back: the pre-policy
        # default backed the live file up and deleted rows, which does not
        # shrink a SQLite file at all (page_count is fixed by the backup).
        raise StoragePolicyError(
            f"API-seeded fixture is {size_bytes} bytes, over the "
            f"{SMALL_FIXTURE_MAX_BYTES}-byte ceiling: the default fixture is "
            f"supposed to be genuinely small (DDL only, 0 dev rows). Either the "
            f"schema grew or something seeded rows into it. Refusing to publish "
            f"a 'small' fixture that is not small -- see {fixture_db}")
    return {
        "mode": FIXTURE_API_SEEDED,
        "path": str(fixture_db),
        "table_count": len(tables),
        "rows": 0,
        "size_bytes": size_bytes,
        "free_pages": free_pages,
        "integrity_check": integrity,
        "schema_source": "core.database.Base.metadata (the app's own schema)",
        "size_ceiling_bytes": SMALL_FIXTURE_MAX_BYTES,
    }


# ---------------------------------------------------------------------------
# Item 3: retention cap, inventory first
# ---------------------------------------------------------------------------
#: Process states. Three, not two: "alive" and "dead" is the pair the code
#: used to assume, and it is the assumption that made a failed pid check read
#: as "safe to delete".
OWNER_IN_USE = "in-use"
OWNER_IDLE = "idle"
OWNER_UNKNOWN = "unknown"


def pid_state(pid: Optional[int]) -> str:
    """Resolve a pid to in-use / idle / UNKNOWN without ever guessing.

    ``os.kill(pid, 0)`` can answer three ways:

    * no exception          -> the process exists. A zombie also exists, and a
      zombie is not serving anything, so it is read as in-use anyway: over-
      retaining a dead run costs disk, under-retaining a live one costs the
      evidence.
    * ``ProcessLookupError`` -> genuinely gone. ``idle``.
    * ``PermissionError``   -> it exists and is owned by somebody else. We are
      not allowed to signal it, so we are not allowed to claim it is idle.
      ``in-use``.
    * anything else (``ValueError`` on a non-numeric pid, ``TypeError`` on a
      non-integer, an ``OSError`` the kernel invented) -> we could not perform
      the check. ``unknown``. This is the case the old boolean signature could
      not express at all, and it is the one that matters: "the pid check could
      not be performed" must never be laundered into "not running".
    """
    if pid is None or pid == "":
        return OWNER_UNKNOWN
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return OWNER_UNKNOWN
    if pid_i <= 0:
        return OWNER_UNKNOWN
    try:
        os.kill(pid_i, 0)
    except ProcessLookupError:
        return OWNER_IDLE
    except PermissionError:
        return OWNER_IN_USE
    except OSError:
        return OWNER_UNKNOWN
    except Exception:  # noqa: BLE001 - a probe that blows up is "unknown"
        return OWNER_UNKNOWN
    return OWNER_IN_USE


def _pid_alive_default(pid: Optional[int]) -> bool:
    """Boolean view of :func:`pid_state`, kept for call sites that only need
    "is something running here".

    Fail-closed: anything that is not positively ``idle`` counts as alive.
    """
    return pid_state(pid) != OWNER_IDLE


@dataclass
class ActivityInspection:
    """The result of looking at a world to decide what is live.

    ``problems`` is the load-bearing field. A picture that could not be taken
    completely is not a picture of "nothing is running" — it is a picture we
    failed to take, and every consumer has to be able to tell those apart.
    Before this existed, four different failure modes (an unreadable
    ``preview_stack.json``, an unreadable ``server_env.json``, an unparseable
    one, and a pid probe that raised) each collapsed into "no active runs",
    which is exactly the answer that permits deletion.

    ``ownership_reasons`` carries the evidence for each state, so the
    inventory can quote *why* a run is known idle ("recorded pid 999 is not
    running") rather than only that it is.
    """

    active: Dict[str, List[str]] = field(default_factory=dict)
    ownership: Dict[str, str] = field(default_factory=dict)
    ownership_reasons: Dict[str, str] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.problems

    def note(self, run_id: str, state: str, why: str) -> None:
        self.ownership[run_id] = state
        self.ownership_reasons[run_id] = why

    def as_dict(self) -> Dict[str, Any]:
        return {"complete": self.complete, "active": self.active,
                "ownership": self.ownership,
                "ownership_reasons": self.ownership_reasons,
                "problems": list(self.problems)}


def _read_json(path: Path, problems: List[str], what: str) -> Optional[Any]:
    """Read JSON, recording a problem instead of swallowing the failure.

    The callers below all used to be ``except (OSError, JSONDecodeError):
    continue``, which is the fail-OPEN shape: a file we cannot read is a file
    whose contents we do not know, and "we do not know" was being recorded as
    "there is nothing there".
    """
    try:
        raw = path.read_text()
    except OSError as exc:
        problems.append(f"{what}: cannot read {path} ({exc})")
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        problems.append(f"{what}: cannot parse {path} ({exc})")
        return None


def inspect_activity(world: Path, *,
                     pid_alive: Optional[Callable[[Optional[int]], bool]] = None,
                     pid_probe: Callable[[Optional[int]], str] = pid_state,
                     ) -> ActivityInspection:
    """Decide, for every run in ``world``, whether something is serving it.

    Signals, all of them positive evidence:

    * the world's ``preview_stack.json`` names a run and the backend pid
      serving it;
    * each run's own ``server_env.json`` records a pid, so a run started by a
      launcher that never wrote world state is still recognised.

    Fail-closed throughout. Every one of these records a problem rather than
    returning an empty answer:

    * ``preview_stack.json`` exists but cannot be read or parsed;
    * ``preview_stack.json`` names a run but records no pid (so the pid check
      cannot be performed on the run the world says is being served);
    * ``preview_stack.json`` records a pid but no ``run_dir`` (a live process,
      an unidentified run);
    * a run's ``server_env.json`` exists but cannot be read or parsed;
    * the runs directory cannot be listed;
    * the pid probe raises or cannot decide.

    ``pid_alive`` is retained as a test seam for callers that inject a boolean
    probe. An injected probe's answer is honoured (``False`` means idle, ``True``
    means in use) and a raise is recorded as a problem — treating an injected
    ``False`` as "unknown" would make the seam untestable, and the seam exists
    so that exhaustion and liveness can be simulated deterministically instead of
    by filling a disk or racing a real process.
    """
    world = Path(world)
    problems: List[str] = []
    active: Dict[str, List[str]] = {}
    ownership: Dict[str, str] = {}
    reasons: Dict[str, str] = {}

    def insp_note(run_id: str, state: str, why: str) -> None:
        ownership[run_id] = state
        reasons[run_id] = why

    def resolve(pid: Optional[int], what: str) -> Optional[str]:
        # A record with no pid is a MISSING record, not a probe verdict. The
        # probe is only ever asked about a pid that exists; asking it about
        # ``None`` is how "there is nothing recorded here" became "nothing is
        # running here".
        if pid is None or pid == "":
            return OWNER_UNKNOWN
        if pid_alive is not None:
            try:
                return OWNER_IN_USE if pid_alive(pid) else OWNER_IDLE
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{what}: pid probe raised ({exc!r})")
                return None
        return pid_probe(pid)

    state = world / "preview_stack.json"
    served: Optional[str] = None
    if state.is_file():
        st = _read_json(state, problems, "world activity state")
        if isinstance(st, dict):
            rd = st.get("run_dir")
            if rd:
                served = Path(str(rd)).name
                st_state = resolve(st.get("backend_pid"), f"preview_stack.json {served}")
                if st_state is None or st_state == OWNER_UNKNOWN:
                    problems.append(
                        f"preview_stack.json names run {served!r} but its backend "
                        f"pid {st.get('backend_pid')!r} could not be checked: "
                        f"liveness UNKNOWN, so this run is not eligible for deletion")
                    active.setdefault(served, []).append(
                        f"named by preview_stack.json (backend pid "
                        f"{st.get('backend_pid')}: liveness could not be established)")
                    insp_note(served, OWNER_IN_USE,
                              f"preview_stack.json names this run but its backend "
                              f"pid {st.get('backend_pid')!r} could not be checked")
                elif st_state == OWNER_IN_USE:
                    active.setdefault(served, []).append(
                        f"named by preview_stack.json (backend pid "
                        f"{st.get('backend_pid')} ALIVE)")
                    insp_note(served, OWNER_IN_USE,
                              f"backend pid {st.get('backend_pid')} is ALIVE "
                              f"(preview_stack.json)")
                else:
                    insp_note(served, OWNER_IDLE,
                              f"recorded pid {st.get('backend_pid')} is not "
                              f"running (preview_stack.json)")
            elif st.get("backend_pid") is not None:
                problems.append(
                    f"preview_stack.json records backend pid "
                    f"{st.get('backend_pid')!r} but names no run_dir: a live "
                    f"process is serving an unidentified run")

    runs = world / "runs"
    if runs.is_dir():
        try:
            children = sorted(runs.iterdir())
        except OSError as exc:
            children = []
            problems.append(f"cannot list {runs} ({exc}): no run's state could "
                            f"be inspected")
        for run in children:
            if not run.name.startswith("run-"):
                continue
            try:
                is_dir = run.is_dir()
            except OSError as exc:
                problems.append(f"cannot stat {run} ({exc})")
                continue
            if not is_dir:
                continue
            env = run / "server_env.json"
            if env.is_file():
                payload = _read_json(env, problems, f"run {run.name} launch state")
                if payload is None:
                    # Unreadable manifest: ownership is unknown, and the reason
                    # is recorded so the refusal can be explained.
                    insp_note(run.name, OWNER_UNKNOWN,
                              f"{env} could not be read or parsed, so this "
                              f"run's liveness cannot be established")
                    continue
                if not isinstance(payload, dict):
                    problems.append(f"run {run.name}: {env} is not a JSON object")
                    insp_note(run.name, OWNER_UNKNOWN,
                              f"{env} is not a JSON object")
                    continue
                pid = payload.get("pid") or payload.get("backend_pid")
                st_state = resolve(pid, f"run {run.name} server_env.json")
                if st_state == OWNER_IN_USE:
                    active.setdefault(run.name, []).append(
                        f"served by live pid {pid} (server_env.json)")
                    insp_note(run.name, OWNER_IN_USE,
                              f"recorded pid {pid} is ALIVE (server_env.json)")
                elif st_state == OWNER_IDLE:
                    insp_note(run.name, OWNER_IDLE,
                              f"recorded pid {pid} is not running "
                              f"(server_env.json)")
                elif st_state is None:
                    # The probe itself failed; `resolve` already recorded why.
                    insp_note(run.name, OWNER_UNKNOWN,
                              f"the pid check for {pid} could not be performed")
                else:
                    # A record with no usable pid. Either way liveness is
                    # UNKNOWN. The run is NOT put in `active` — "unknown" is
                    # not "in use", and labelling it ``retained-active`` would
                    # be a lie about why it survived — it is left UNKNOWN so
                    # :func:`build_inventory` classifies it review-required.
                    problems.append(
                        f"run {run.name}: {env} records no usable pid, so the "
                        f"pid check cannot be performed; liveness UNKNOWN, and "
                        f"this run is not eligible for deletion")
                    insp_note(run.name, OWNER_UNKNOWN,
                              "no ownership record: server_env.json carries no "
                              "pid and no world state names this run; liveness "
                              "could not be established either way")
            else:
                # No launch record at all. That is not an inspection failure —
                # it is a run that was never served here, or whose record was
                # lost. Either way ownership is UNKNOWN and the run is
                # review-required rather than droppable.
                insp_note(run.name, OWNER_UNKNOWN,
                          "no ownership record: no server_env.json and no world "
                          "state names this run; liveness could not be "
                          "established either way")
    if served is not None:
        ownership.setdefault(served, OWNER_UNKNOWN)
        reasons.setdefault(served, "named by preview_stack.json")

    return ActivityInspection(active=active, ownership=ownership,
                              ownership_reasons=reasons, problems=problems)


def active_run_ids(world: Path, *,
                   pid_alive: Callable[[Optional[int]], bool] = _pid_alive_default
                   ) -> Dict[str, List[str]]:
    """Runs a live process is using right now (compatibility view).

    Prefer :func:`inspect_activity`: this returns only the "active" half and
    therefore discards the problems, which is what made the old behaviour
    indistinguishable from a complete scan. Kept because it is the shape the
    inventory builder's docstring and several call sites describe.
    """
    return inspect_activity(world, pid_alive=pid_alive).active


def load_pinned_runs(world: Path) -> List[str]:
    """Run ids this world has pinned, from ``<world>/pinned_runs.json``."""
    p = Path(world) / PIN_FILE
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, dict):
        return [str(x) for x in (raw.get("pinned") or [])]
    return []


def _iter_json_strings(obj: Any, depth: int = 0) -> Iterable[str]:
    if depth > 24:
        return
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _iter_json_strings(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_json_strings(v, depth + 1)


def scan_evidence_runs_audited(roots: Sequence[Path], *, max_files: int = 20000
                               ) -> Tuple[Dict[str, List[str]], List[str]]:
    """Map ``run id -> [document, ...]`` AND report what could not be read.

    Returns ``(mapping, problems)``. ``problems`` is non-empty when the scan
    was partial — a document it could not read, or the file cap it hit — and a
    partial scan is a scan whose silence means nothing.

    How a run is identified as evidence-bearing, from the formats actually
    on disk (read 2026-09-28):

    * ``backend/data/acceptance_worlds_results/<harness>/<world>_<ts>.json``
      carries top-level ``"world"`` and ``"run"`` (``run-<12 hex>``).
    * ``docs/.../acceptance/lane3/**.json`` carries ``run_dir`` and
      ``run_id``, and embeds absolute run database paths
      (``.../<world>/runs/run-<12 hex>/data/atom.db``).
    * a world's own ``preview_stack.json`` (``run_dir``) and
      ``launch_descriptor.json`` (``run_id``) name the launch being described.

    All four reduce to the same token, so detection scans every string in
    the document for ``run-<12 hex>`` rather than keying on four spellings.
    Keying on keys would break the moment a new harness names the field
    something else, and a missed key means a run holding recorded evidence
    gets classified droppable. The referring document is retained so the
    classification can be audited rather than trusted.
    """
    out: Dict[str, List[str]] = {}
    problems: List[str] = []
    seen_files = 0
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        try:
            files = [rp] if rp.is_file() else sorted(rp.rglob("*.json"))
        except OSError as exc:
            problems.append(f"evidence: cannot list {rp} ({exc})")
            continue
        for f in files:
            if seen_files >= max_files:
                break
            seen_files += 1
            # A run's OWN per-launch artifacts are not evidence FOR that run.
            # server_env.json embeds the run's own database path, so it contains
            # its own run-<12 hex> token; counting it made every run reference
            # itself and therefore every run "evidence-bearing". Measured on
            # 2026-09-28: 13 of 14 runs in write_verify_0928 and 26 of 28 in
            # write_combined were retained on that basis, 0 droppable, ~18.7 GB
            # unreclaimable -- the retention cap was a no-op and the "delete by
            # hand when the disk complains" behaviour this policy exists to
            # replace was still in force.
            #
            # These files remain authoritative for the ACTIVE signal, which
            # reads a pid from them directly in active_run_ids; only their use
            # as evidence for retention is removed. A run is still protected by
            # any external document that names it: a recorded result, a world
            # manifest, a lane3 evidence document.
            if f.name in PER_LAUNCH_ARTIFACTS:
                continue
            try:
                raw = f.read_text()
            except (OSError, UnicodeDecodeError) as exc:
                # Recorded, not swallowed. An unreadable evidence document is
                # a document whose run ids we do not know, and "we do not know"
                # was previously indistinguishable from "it named nothing" --
                # i.e. from "this run holds no evidence and may be deleted".
                problems.append(f"evidence: cannot read {f} ({exc})")
                continue
            for run_id in sorted(set(RUN_ID_RE.findall(raw))):
                out.setdefault(run_id, [])
                if len(out[run_id]) < 5:
                    out[run_id].append(str(f))
    if seen_files >= max_files:
        problems.append(
            f"evidence: scan stopped at the {max_files}-file cap; documents "
            f"beyond it were never read, so runs they name are unprotected")
    return out, problems


def scan_evidence_runs(roots: Sequence[Path], *, max_files: int = 20000
                       ) -> Dict[str, List[str]]:
    """Mapping-only view of :func:`scan_evidence_runs_audited`.

    Present for compatibility. It discards the problems list, which is exactly
    the information a caller needs in order to act on the result, so anything
    that deletes must use the audited form.
    """
    return scan_evidence_runs_audited(roots, max_files=max_files)[0]


@dataclass
class RunEntry:
    run_id: str
    path: Path
    size_bytes: int
    mtime_iso: str
    classification: str
    reasons: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    hardlinked_files: int = 0
    #: Structured protection facts, recorded at classification time. Deletion
    #: eligibility is re-derived from THIS list, not from ``classification``,
    #: so a caller that rewrites a classification field cannot turn a pinned,
    #: active or evidence-linked run into a deletion candidate. ``protection``
    #: is empty only for a run that was positively established as idle and
    #: unprotected.
    protection: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id, "path": str(self.path),
            "size_bytes": self.size_bytes,
            "mtime": self.mtime_iso, "classification": self.classification,
            "reasons": self.reasons, "evidence_refs": self.evidence_refs,
            "hardlinked_files": self.hardlinked_files,
            "protection": self.protection,
        }


@dataclass
class Inventory:
    world: str
    cap: int
    generated_at: str
    entries: List[RunEntry] = field(default_factory=list)
    unclassified_note: str = ""
    #: Everything that made the picture incomplete: unreadable world state,
    #: unreadable run manifests, an unreadable evidence document, a pid check
    #: that could not be performed, a truncated scan, an unstat-able run.
    #: Non-empty means "we could not take the picture", which is a refusal to
    #: delete, not a smaller deletion set.
    inspection_problems: List[str] = field(default_factory=list)
    #: SHA-256 over the reviewable projection, fixed at construction so a
    #: reviewed inventory can be bound to the thing that was reviewed.
    digest: str = ""

    @property
    def complete(self) -> bool:
        return not self.inspection_problems

    @property
    def droppable(self) -> List[RunEntry]:
        return [e for e in self.entries if e.classification == CLASS_DROPPABLE]

    def deletion_candidates(self) -> List[RunEntry]:
        """The only list any removal path may iterate.

        Derived from ``protection`` — the facts recorded when the run was
        classified — not from the ``classification`` string. Two independent
        reasons for that:

        * a caller that flips ``entry.classification`` to ``droppable`` does
          not thereby remove the protection facts, so an active, pinned,
          evidence-linked or review-required run stays out of the set;
        * the exclusions therefore cannot be bypassed by a flag, because no
          flag writes to ``protection``.
        """
        return [e for e in self.entries
                if e.classification == CLASS_DROPPABLE and not e.protection]

    @property
    def review_required(self) -> List[RunEntry]:
        """Runs whose ownership could not be established.

        Excluded from ordinary cleanup. A run here is not known to be idle; it
        is known to be unexamined, and deleting it is a separate decision that
        ``--confirm-drop`` does not authorise.
        """
        return [e for e in self.entries if e.classification == CLASS_REVIEW]

    @property
    def retained(self) -> List[RunEntry]:
        return [e for e in self.entries if e.classification != CLASS_DROPPABLE]

    def totals(self) -> Dict[str, int]:
        by_class: Dict[str, int] = {}
        for e in self.entries:
            by_class[e.classification] = by_class.get(e.classification, 0) + e.size_bytes
        return by_class

    def finalize(self) -> "Inventory":
        """Stamp the digest over the reviewable projection and return self."""
        payload = json.dumps({
            "world": self.world, "cap": self.cap,
            "generated_at": self.generated_at,
            "complete": self.complete,
            "entries": [[e.run_id, str(e.path), e.size_bytes, e.mtime_iso,
                         e.classification, sorted(e.protection)]
                        for e in self.entries],
        }, sort_keys=True)
        self.digest = hashlib.sha256(payload.encode()).hexdigest()
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {
            "world": self.world, "cap": self.cap, "generated_at": self.generated_at,
            "run_count": len(self.entries),
            "total_bytes": sum(e.size_bytes for e in self.entries),
            "totals_by_class": self.totals(),
            "droppable_count": len(self.deletion_candidates()),
            "droppable_bytes": sum(e.size_bytes for e in self.deletion_candidates()),
            "retained_count": len(self.retained),
            "unclassified_note": self.unclassified_note,
            "inspection_complete": self.complete,
            "inspection_problems": list(self.inspection_problems),
            "digest": self.digest,
            "entries": [e.as_dict() for e in self.entries],
        }

    def to_text(self) -> str:
        lines = [
            "=" * 78,
            f"DELETION INVENTORY — world {self.world!r} "
            f"(cap {self.cap} runs)  {self.generated_at}",
            "=" * 78,
            f"{len(self.entries)} run director(ies), "
            f"{human(sum(e.size_bytes for e in self.entries))} total",
            "",
        ]
        head = f"{'classification':<24} {'size':>10}  {'mtime':<20} run"
        lines.append(head)
        lines.append("-" * len(head))
        for e in sorted(self.entries, key=lambda x: (x.classification, -x.size_bytes)):
            lines.append(f"{e.classification:<24} {human(e.size_bytes):>10}  "
                         f"{e.mtime_iso:<20} {e.run_id}")
            for r in e.reasons:
                lines.append(f"{'':<24} {'':>10}  - {r}")
            for ref in e.evidence_refs[:3]:
                lines.append(f"{'':<24} {'':>10}  evidence: {ref}")
            if e.hardlinked_files:
                lines.append(f"{'':<24} {'':>10}  WARNING: {e.hardlinked_files} "
                             "hard-linked file(s) in this run")
        lines += ["", "totals by classification:"]
        for cls, n in sorted(self.totals().items()):
            lines.append(f"  {cls:<24} {human(n):>10}")
        if self.deletion_candidates():
            lines += ["",
                      f"Would drop {len(self.deletion_candidates())} run(s) totalling "
                      f"{human(sum(e.size_bytes for e in self.deletion_candidates()))}.",
                      "NOTHING WAS DELETED."]
        else:
            lines += ["", "Nothing is droppable: every run is active, pinned, "
                          "evidence-referenced, review-required, or inside the cap."]
        if self.unclassified_note:
            lines += ["", self.unclassified_note]
        if not self.complete:
            lines += ["", "INSPECTION INCOMPLETE — this inventory cannot authorise "
                          "a deletion:"]
            lines += [f"  - {p}" for p in self.inspection_problems]
        lines += ["",
                  "Deleting requires ALL THREE, and this inventory grants none of them:",
                  "  1. the maintenance interlock held:",
                  "       python -m core.world_storage_guard lock --reason 'retention'",
                  "  2. a reviewed inventory: re-run `cleanup` and pass the digest",
                  f"       printed below with --reviewed-digest {self.digest}",
                  "  3. no build or run in progress for this world",
                  ""]
        lines.append(f"  inventory digest (review this, then pass it back): {self.digest}")
        return "\n".join(lines)






def run_ownership(world: Path, *,
                  pid_alive: Optional[Callable[[Optional[int]], bool]] = None,
                  ) -> Tuple[Dict[str, str], List[str]]:
    """Resolve each run's ownership to in-use / idle / UNKNOWN.

    ``idle`` requires positive evidence that nothing is serving the run: a
    recorded pid that is provably not alive. A run with no such record is
    ``unknown`` -- we did not establish that it is idle, we merely failed to
    find out.

    Two sources carry a pid, and they are not equivalent in practice. The
    world's ``preview_stack.json`` names the served run and its backend pid, and
    is reliable. A run's ``server_env.json`` is a LAUNCH ENVIRONMENT dump -- it
    records flags and paths, and only carries a pid for runs launched after the
    launcher started writing one. So for the large body of older runs the pid is
    absent and the honest answer is ``unknown``, which is why they classify as
    review-required rather than droppable. That is the correct reading: nothing
    was deleted on the strength of an absence.

    Returns ``(ownership, problems)``. The ownership map is a thin projection
    of :func:`inspect_activity`; it is kept because the *reason* strings
    attached to each state are what the inventory quotes at the operator.
    """
    insp = inspect_activity(world, pid_alive=pid_alive)
    out: Dict[str, str] = {}
    for run_id in insp.ownership:
        out[run_id] = insp.ownership[run_id]
    # Anything inspect_activity saw but could not classify stays UNKNOWN.
    runs_dir = Path(world) / "runs"
    if runs_dir.is_dir():
        try:
            for run in sorted(runs_dir.iterdir()):
                if run.name.startswith("run-") and run.is_dir():
                    out.setdefault(run.name, OWNER_UNKNOWN)
        except OSError:
            pass
    return out, list(insp.problems)


def build_inventory(
    world: Path,
    *,
    cap: int = DEFAULT_RUN_CAP,
    evidence_roots: Optional[Sequence[Path]] = None,
    pinned: Optional[Sequence[str]] = None,
    pid_alive: Optional[Callable[[Optional[int]], bool]] = None,
    scan_world_state: bool = True,
) -> Inventory:
    """Classify every run directory in ``world``. Deletes nothing.

    Classification is fail-closed in three independent places, and each of them
    ends at "not droppable" rather than at "drop something smaller":

    1. **ownership** — a run is only ``droppable`` when its liveness was
       POSITIVELY established as idle. ``unknown`` becomes
       :data:`CLASS_REVIEW`, which is excluded from ordinary cleanup.
    2. **protection** — active, pinned and evidence-referenced runs are
       excluded, and the exclusion is recorded in ``RunEntry.protection`` so it
       survives a later rewrite of the classification string.
    3. **completeness** — every way the picture can be incomplete (unreadable
       world state, unreadable run manifest, unparseable JSON, a pid check that
       could not be performed, an unreadable evidence document, a truncated
       evidence scan, an unstat-able run) is recorded in
       ``Inventory.inspection_problems``, which makes the inventory
       *unauthorisable for deletion* rather than merely smaller.
    """
    world = Path(world)
    inv = Inventory(world=world.name, cap=cap,
                    generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))

    roots: List[Path] = ([RESULTS_ROOT, ACC, world] if evidence_roots is None
                         else [Path(r) for r in evidence_roots])
    evidence, problems = scan_evidence_runs_audited(roots)

    if not scan_world_state:
        # Excluding the world state is asking for a partial picture; say so
        # rather than letting the caller believe it got a complete one.
        problems.append("world state (preview_stack.json) excluded from the "
                        "active-run scan by request")
        activity = ActivityInspection()
    else:
        activity = inspect_activity(world, pid_alive=pid_alive)
    problems.extend(activity.problems)
    active = activity.active
    ownership = activity.ownership

    pin_set = set(pinned) if pinned is not None else set(load_pinned_runs(world))
    if pinned is None:
        pin_path = world / PIN_FILE
        if pin_path.is_file():
            try:
                pin_path.read_text()
            except OSError as exc:
                problems.append(
                    f"pins: cannot read {pin_path} ({exc}); pins could not be "
                    f"honoured, so no run can be shown to be unpinned")

    runs_dir = world / "runs"
    if not runs_dir.is_dir():
        inv.unclassified_note = f"no runs directory at {runs_dir}; nothing to classify"
        inv.inspection_problems = list(problems)
        return inv.finalize()

    candidates: List[Tuple[float, Path]] = []
    try:
        run_dirs = sorted(runs_dir.iterdir())
    except OSError as exc:
        run_dirs = []
        problems.append(f"cannot list {runs_dir} ({exc})")
    for run in run_dirs:
        if not run.name.startswith("run-"):
            continue
        try:
            if not run.is_dir():
                continue
            candidates.append((run.stat().st_mtime, run))
        except OSError as exc:
            problems.append(f"cannot stat run directory {run} ({exc})")
    candidates.sort(key=lambda t: t[0])  # oldest first

    # The retention window is the `cap` NEWEST runs by mtime, across all
    # runs. Excluded runs (active/pinned/evidence) are classified before the
    # window is consulted, so a pinned or active run cannot push a fresh
    # debugging run out of the cap -- and a world with no protected runs at
    # all still keeps its newest `cap` runs.
    keep_newest = {run.name for _, run in candidates[-cap:]} if cap > 0 else set()
    protected_ids = {r.name for _, r in
                     [(0, r) for _, r in candidates
                      if r.name in active or r.name in pin_set or r.name in evidence]}

    for mtime, run in candidates:
        usage = dir_usage(run)
        entry = RunEntry(
            run_id=run.name, path=run, size_bytes=usage["on_disk_bytes"],
            mtime_iso=time.strftime("%Y-%m-%dT%H:%M", time.localtime(mtime)),
            classification=CLASS_DROPPABLE,
            hardlinked_files=len(usage["hardlinked"]))
        if run.name in active:
            entry.classification = CLASS_ACTIVE
            entry.reasons += active[run.name]
            entry.protection.append("active")
        if run.name in pin_set:
            entry.classification = (CLASS_ACTIVE if run.name in active else CLASS_PINNED)
            entry.reasons.append(f"pinned in {world / PIN_FILE}")
            entry.protection.append("pinned")
        if run.name in evidence:
            if run.name not in active and run.name not in pin_set:
                entry.classification = CLASS_EVIDENCE
            entry.reasons.append(
                f"referenced by {len(evidence[run.name])} recorded document(s)")
            entry.evidence_refs = list(evidence[run.name])
            entry.protection.append("evidence")
        if run.name in keep_newest:
            entry.protection.append("within-cap")
        own_state = ownership.get(run.name)
        if own_state == OWNER_UNKNOWN and not entry.protection:
            # Absent evidence is not evidence of safety.
            entry.classification = CLASS_REVIEW
            entry.protection.append("ownership-unknown")
            entry.reasons.append(activity.ownership_reasons.get(
                run.name, "ownership could not be established"))
        if entry.classification == CLASS_DROPPABLE:
            if problems:
                # A picture we could not take completely is not a smaller
                # deletion set; it is no deletion set.
                entry.classification = CLASS_WITHIN_CAP
                entry.protection.append("inspection-incomplete")
                entry.reasons.append(
                    f"retention NOT enforced: the inventory is incomplete "
                    f"({len(problems)} problem(s)); first: {problems[0]}")
            elif run.name in keep_newest:
                entry.classification = CLASS_WITHIN_CAP
                entry.reasons.append(f"inside the retention cap ({cap} newest runs)")
            else:
                # Quote the evidence, not just the conclusion: "droppable"
                # with no stated reason is not auditable.
                why = activity.ownership_reasons.get(run.name, "liveness not recorded")
                entry.reasons.append(
                    f"unprotected, unrecorded, idle ({why}), outside the "
                    f"retention cap ({cap} newest runs); {len(protected_ids)} "
                    f"protected run(s) exist")
        inv.entries.append(entry)

    inv.inspection_problems = list(problems)
    if problems:
        inv.unclassified_note = (
            f"PARTIAL SCAN ({len(problems)} problem(s)) — nothing may be dropped: "
            + "; ".join(problems))
    review = [e for e in inv.entries if e.classification == CLASS_REVIEW]
    if review:
        inv.unclassified_note = (
            (inv.unclassified_note + " | " if inv.unclassified_note else "")
            + f"{len(review)} run(s) need review: ownership could not be established")
    return inv.finalize()


# ---------------------------------------------------------------------------
# Deletion is gated on the interlock AND a reviewed inventory. Both, never one.
# ---------------------------------------------------------------------------
def interlock_state() -> Tuple[bool, str]:
    """Is the worlds-storage maintenance interlock held right now?

    Delegates to ``core.world_storage_guard.lock_active`` — the same predicate
    the launchers themselves honour — so the retention gate and the launch
    gate cannot disagree about whether a maintenance window is open.

    Fail-closed: if the guard cannot be imported or raises, the answer is
    "not held", because the alternative is a deletion proceeding on the
    strength of a check that did not run.
    """
    try:
        from core.world_storage_guard import lock_active  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return False, f"could not import core.world_storage_guard ({exc!r})"
    try:
        active = bool(lock_active())
    except Exception as exc:  # noqa: BLE001
        return False, f"could not read the maintenance lock ({exc!r})"
    return active, ("maintenance interlock held" if active
                    else "maintenance interlock NOT held")


def registered_runners() -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """Launchers currently holding worlds open, as the guard sees them.

    ``None`` means "could not be determined", which callers must treat as
    "cannot prove the tree is quiescent".
    """
    try:
        from core.world_storage_guard import list_runners  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return None, f"could not import core.world_storage_guard ({exc!r})"
    try:
        return list(list_runners()), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"could not list registered launchers ({exc!r})"


def write_build_marker(world: Path, *, operation: str = "build",
                       detail: Optional[Dict[str, Any]] = None) -> Path:
    """Announce that ``world`` is being written to. Returns the marker path.

    Written by the launcher immediately after the space check and removed when
    the build finishes. Deliberately NOT removed on failure: a crashed build
    leaves a world in an unknown state, and a retention pass that cannot tell
    "clean" from "half-built" must refuse rather than guess. Removing a stale
    marker is a human decision.
    """
    world = Path(world)
    marker = world / BUILD_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "operation": operation,
        "pid": os.getpid(),
        "started_at": time.time(),
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detail": detail or {},
    }, indent=2, sort_keys=True) + "\n")
    return marker


def clear_build_marker(world: Path) -> bool:
    """Remove a build marker this process wrote. Returns True if one went."""
    marker = Path(world) / BUILD_MARKER
    try:
        marker.unlink()
        return True
    except (FileNotFoundError, OSError):
        return False


def world_in_progress(world: Path, *,
                      runner_probe: Optional[Callable[[], Any]] = None
                      ) -> Tuple[bool, List[str]]:
    """Is a build or a run happening for ``world`` right now?

    Real state only, and fail-closed when it cannot be read:

    * ``<world>/build_in_progress.json`` — written by ``run_isolated.build_world``
      for the duration of a build (see :data:`BUILD_MARKER`);
    * ``<world>/runs/<run>/run_live`` — a live-run marker inside a run dir
      (see :data:`RUN_LIVE_MARKER`);
    * a registered launcher holding worlds open at all, which is the race the
      guard's flock exists to prevent;
    * a ``preview_stack.json`` whose recorded backend pid is still running.

    Returns ``(in_progress, reasons)``. ``reasons`` is non-empty when the
    answer could not be established, and the caller must refuse in that case
    too: "I could not tell whether a build is running" is not permission.
    """
    world = Path(world)
    reasons: List[str] = []

    marker = world / BUILD_MARKER
    if marker.exists():
        reasons.append(f"build marker present: {marker}")

    runs_dir = world / "runs"
    if runs_dir.is_dir():
        try:
            for run in sorted(runs_dir.iterdir()):
                if not run.name.startswith("run-"):
                    continue
                if (run / RUN_LIVE_MARKER).exists():
                    reasons.append(f"run marker present: {run / RUN_LIVE_MARKER}")
        except OSError as exc:
            reasons.append(f"cannot list {runs_dir} ({exc})")

    probe = runner_probe or (lambda: registered_runners()[0])
    try:
        runners = probe()
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"launcher registry unreadable ({exc!r})")
        runners = None
    if runners is None:
        reasons.append("launcher registry could not be read: a launcher may be live")
    else:
        for r in runners:
            pid = r.get("pid") if isinstance(r, dict) else None
            if pid == os.getpid():
                # This process is the one being asked; it is not a build.
                continue
            reasons.append(
                f"a world launcher is registered: pid {pid} "
                f"{(r.get('role') if isinstance(r, dict) else '?')}")

    state = world / "preview_stack.json"
    if state.is_file():
        try:
            st = json.loads(state.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            reasons.append(f"cannot read {state} ({exc})")
        else:
            pid = (st or {}).get("backend_pid")
            if pid is not None and pid_state(pid) == OWNER_IN_USE:
                reasons.append(f"preview_stack.json backend pid {pid} is ALIVE")
    return bool(reasons), reasons


def deletion_preconditions(inventory: Inventory, *,
                           world: Path,
                           confirm: bool,
                           reviewed_digest: Optional[str],
                           interlock_probe: Optional[Callable[[], Tuple[bool, str]]] = None,
                           state_probe: Optional[Callable[[Path], Tuple[bool, List[str]]]] = None,
                           ) -> List[str]:
    """Every reason this deletion must NOT happen. Empty list == may proceed.

    All three gates are required and none substitutes for another:

    * ``confirm`` — an explicit human decision;
    * the maintenance interlock — the tree is quiesced, and the launchers that
      would be racing are already refusing;
    * ``reviewed_digest`` — the operator reviewed *this* inventory. A digest
      that does not match means the inventory changed after it was read (a run
      appeared, a size moved, a classification flipped), and consenting to the
      old one is not consenting to the new one.
    """
    refusals: List[str] = []
    if not confirm:
        refusals.append("no explicit confirmation (--confirm-drop)")
    probe = interlock_probe or interlock_state
    try:
        held, why = probe()
    except Exception as exc:  # noqa: BLE001
        held, why = False, f"interlock probe raised ({exc!r})"
    if not held:
        refusals.append(why)
    if not reviewed_digest:
        refusals.append(
            "no reviewed inventory: pass --reviewed-digest with the digest "
            "printed by the inventory run")
    elif reviewed_digest != inventory.digest:
        refusals.append(
            f"reviewed digest {reviewed_digest[:16]}... does not match this "
            f"inventory ({inventory.digest[:16]}...): it changed after it was "
            f"reviewed. Re-read it and review the new one")
    if not inventory.complete:
        refusals.append(
            f"activity inspection incomplete ({len(inventory.inspection_problems)} "
            f"problem(s)); first: {inventory.inspection_problems[0]}")
    in_progress, why = (state_probe or world_in_progress)(Path(world))
    if in_progress:
        refusals.append("a build or run may be in progress: " + "; ".join(why))
    return refusals


def apply_inventory(inventory: Inventory, *, confirm: bool = False,
                    world: Optional[Path] = None,
                    reviewed_digest: Optional[str] = None,
                    interlock_probe: Optional[Callable[[], Tuple[bool, str]]] = None,
                    state_probe: Optional[Callable[[Path], Tuple[bool, List[str]]]] = None,
                    remove: Optional[Callable[[Path], None]] = None
                    ) -> Dict[str, Any]:
    """Delete only ``deletion_candidates()``, and only behind all three gates.

    With ``confirm=False`` (the default, and what every inventory run passes)
    this is a no-op that returns the inventory. There is no code path in the
    harness that removes a run directory unattended, and none that removes one
    while a build is running or an inspection was incomplete.

    ``world`` is required for the deletion path: "is anything using this world"
    is a question about the filesystem, not about the inventory.
    """
    if remove is None:
        def remove(p: Path) -> None:
            shutil.rmtree(p)

    result: Dict[str, Any] = {
        "confirmed": confirm,
        "deleted": [], "failed": [], "freed_bytes": 0,
        "inventory": inventory.as_dict(),
    }
    if not confirm:
        result["note"] = ("no confirmation flag: inventory written, nothing deleted")
        return result
    if world is None:
        result["refused"] = ("no world given: the in-progress check needs a "
                             "filesystem to look at")
        result["note"] = "REFUSED — nothing deleted"
        return result
    # Reported before the gates are evaluated, so a refusal still tells the
    # operator which runs needed a human decision.
    for entry in inventory.review_required:
        result.setdefault("review_required", []).append(
            {"run_id": entry.run_id, "size_bytes": entry.size_bytes,
             "reason": "; ".join(entry.reasons)})
    refusals = deletion_preconditions(
        inventory, world=Path(world), confirm=True, reviewed_digest=reviewed_digest,
        interlock_probe=interlock_probe, state_probe=state_probe)
    if refusals:
        result["refused"] = "; ".join(refusals)
        result["note"] = "REFUSED — nothing deleted"
        return result
    for entry in inventory.deletion_candidates():
        try:
            remove(entry.path)
        except OSError as exc:
            result["failed"].append({"run_id": entry.run_id, "error": str(exc)})
            continue
        result["deleted"].append(entry.run_id)
        result["freed_bytes"] += entry.size_bytes
    return result


# ---------------------------------------------------------------------------
# Item 4: share the immutable export, never share writable state
# ---------------------------------------------------------------------------
#: What may be shared between worlds, and what may not. Stated here because
#: "reuse the export" is a one-line change and "why not the database too" is
#: the question that has to survive the next person.
#:
#: SHARED — the immutable code export. It is produced by `git archive` of a
#:   pinned revision, content-addressed by `code_manifest.json`, chmod'd
#:   read-only after extraction, and re-verified by file manifest before
#:   every run. Two worlds on the same pinned revision therefore have
#:   byte-identical trees, and the copy buys nothing but ~130 MB each and a
#:   second tree to keep in sync.
#:
#: NEVER SHARED — anything writable:
#:   * `data/atom.db` (+ `-wal`, `-shm`): a world WRITES to its database.
#:     Two writers on one inode is how one world corrupts another, and the
#:     corruption is silent: the DB still opens and the other world's data
#:     is simply gone. Never `os.link` it, and never symlink it.
#:   * `data/` as a whole (memory store, sheet datasets, BYOK store): the
#:     harness rewrites dataset parquet paths per run, and the preview seeds
#:     a per-run credential store into it.
#:   * `logs/`: two processes writing one log file interleaves into
#:     unreadable noise, and a log is evidence.
#:   * `runs/`: each run is a distinct database; sharing the directory would
#:     alias every run onto one database.
#:   * the frontend distDir: `next dev` holds an exclusive lock on
#:     `<distDir>/dev/lock` (that is exactly why farms are per world), and
#:     two builds into one distDir overwrite each other's chunks.
SHARED_EXPORT_OK = ("code",)
SHARED_EXPORT_FORBIDDEN = (
    "data", "logs", "runs", "fixture", "run_secrets",
    "node_modules", ".next", "shm_cache",
)


def assert_not_hardlinked_writable(path: Path) -> None:
    """Refuse a writable file that is a hard link into a shared tree.

    A hard-linked database has ``st_nlink > 1`` and is therefore the SAME
    inode under two names. Every write through either name lands in the
    other world. This is the failure the brief names explicitly, and it is
    undetectable by reading the path — only the link count shows it.
    """
    p = Path(path)
    if not p.exists():
        return
    try:
        st = p.stat()
    except OSError as exc:
        raise SharedWritableError(f"cannot stat writable file {p}: {exc}") from exc
    if getattr(st, "st_nlink", 1) > 1:
        raise SharedWritableError(
            f"WRITABLE FILE IS HARD-LINKED (st_nlink={st.st_nlink}): {p}\n"
            "  Two paths, one inode, two writers. One world would silently\n"
            "  overwrite the other's database. Hard links are acceptable for\n"
            "  the read-only code export; they are never acceptable for a\n"
            "  database, a log, or a credential store.")


def find_hardlinked_writables(root: Path) -> List[List[str]]:
    """Groups of writable-suffixed files under ``root`` sharing one inode."""
    out: List[List[str]] = []
    root = Path(root)
    if not root.is_dir():
        return out
    by_inode: Dict[Tuple[int, int], List[str]] = {}
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                        continue
                    if not entry.name.endswith((".db", ".db-wal", ".db-shm",
                                                ".sqlite", ".sqlite3")):
                        continue
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_nlink > 1:
                        by_inode.setdefault((st.st_dev, st.st_ino), []).append(
                            str(Path(entry.path)))
        except OSError:
            continue
    for paths in by_inode.values():
        if len(paths) > 1:
            out.append(sorted(paths))
    return sorted(out)


def assert_writable_state_separate(world: Path,
                                   export_dir: Optional[Path] = None) -> None:
    """Assert no writable state lives inside the shared export.

    A symlinked ``code`` is the intended shape. Anything under it that the
    harness writes to (a database, a log, a run dir, a build cache) is the
    exact corruption bug, so it is checked rather than assumed. When
    ``export_dir`` is given (an owned export), only the hard-link check
    applies: an owned tree legitimately has no ``data/`` because the farm
    points elsewhere, and a stray writable file inside it would be an
    accident worth failing on.
    """
    world = Path(world)
    shared = False
    if export_dir is None:
        code = world / "code"
        if not code.is_symlink():
            return
        export_dir = code.resolve()
        shared = True
    export = Path(export_dir)
    if not export.exists():
        return
    if shared:
        for name in SHARED_EXPORT_FORBIDDEN:
            candidate = export / name
            if not candidate.exists():
                continue
            # ANY writable thing inside a shared export is the bug, not just a
            # hard link or a symlink. A plain `data/` directory reached
            # through a shared `code` is exactly the corruption case: the
            # world writes to a tree another world also writes to.
            raise SharedWritableError(
                f"WRITABLE STATE INSIDE THE SHARED EXPORT: {candidate}\n"
                f"  world {world.name} shares its code export at {export}, but\n"
                f"  {name!r} is writable state. Sharing it would let this world\n"
                "  write into another world's data. Databases, logs, run dirs and\n"
                "  build caches are per world by policy (see storage_policy).")
    for group in find_hardlinked_writables(export):
        raise SharedWritableError(
            "WRITABLE DATABASES SHARE ONE INODE inside the code export:\n"
            + "\n".join(f"  - {g}" for g in group)
            + "\n  Two paths, one inode, two writers. Hard links are acceptable"
              " for the read-only code export; never for a database.")


def _manifest_sha(world: Path) -> Optional[str]:
    """Content-address a world's ``code_manifest.json``."""
    mf = world / "code_manifest.json"
    if not mf.is_file():
        return None
    try:
        raw = json.loads(mf.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not raw:
        return None
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def link_shared_export(world: Path, owner_world: Path) -> Dict[str, Any]:
    """Point ``<world>/code`` at ``<owner>/code`` when the export matches.

    Returns a record saying what happened, so the launch output states
    whether the export was shared or copied. A mismatch (no manifest, or a
    different manifest hash) is a COPY, never a silent share: sharing an
    export that is not byte-identical would make two worlds test different
    code, which is worse than the 130 MB saved.
    """
    world, owner = Path(world), Path(owner_world)
    if world == owner:
        return {"mode": "own", "code": str(world / "code"),
                "note": "world owns its own export"}
    owner_code = owner / "code"
    if not owner_code.exists():
        return {"mode": "none", "note": f"owner world {owner.name} has no code export"}

    owner_sha = _manifest_sha(owner)
    world_sha = _manifest_sha(world)
    if owner_sha is None or owner_sha != world_sha:
        return {"mode": "copy", "code": str(world / "code"),
                "note": f"export differs from {owner.name}'s (no/other manifest): "
                        f"copy, do not share"}

    code = world / "code"
    if code.is_symlink():
        if Path(os.readlink(code)) == owner_code:
            return {"mode": "shared", "code": str(code),
                    "note": f"already shared with {owner.name}"}
        code.unlink()
    elif code.exists():
        return {"mode": "copy", "code": str(code),
                "note": "world already has its own export; left alone"}
    code.symlink_to(owner_code)
    return {"mode": "shared", "code": str(code),
            "note": f"shared read-only export with {owner.name} "
                    f"(manifest {owner_sha[:12]}; writable data/logs/build caches "
                    f"stay per world)"}


# ---------------------------------------------------------------------------
# Item 5: per-world / per-run storage report
# ---------------------------------------------------------------------------
@dataclass
class RunUsage:
    run_id: str
    size_bytes: int
    db_bytes: int
    mtime_iso: str
    hardlinked_files: int

    def as_dict(self) -> Dict[str, Any]:
        return {"run_id": self.run_id, "size_bytes": self.size_bytes,
                "db_bytes": self.db_bytes, "mtime": self.mtime_iso,
                "hardlinked_files": self.hardlinked_files}


def world_storage_report(world: Path, *, max_runs: int = 0,
                         free_probe: Optional[Path] = None) -> Dict[str, Any]:
    """Explain what a world occupies, per world and per run.

    The breakdown is the point: "the world is 14 GB" is not actionable,
    "26 run directories hold 11 GB of seeded database copies" is. The
    frontend build cache is attributed from that world's farm when one
    exists, and free space plus reserved headroom are reported alongside, so
    growth is visible before a launcher fails rather than discovered by it.
    """
    world = Path(world)
    total = dir_usage(world)
    breakdown: Dict[str, int] = {}

    for name, rel in (("code_export", "code"), ("fixture", "fixture"),
                      ("world_data", "data")):
        p = world / rel
        if p.exists():
            breakdown[name] = dir_usage(p)["on_disk_bytes"]

    runs_dir = world / "runs"
    runs: List[RunUsage] = []
    if runs_dir.is_dir():
        entries = sorted(runs_dir.glob("run-*"),
                         key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if max_runs and len(entries) > max_runs:
            entries = entries[-max_runs:]
        for run in entries:
            if not run.is_dir():
                continue
            u = dir_usage(run)
            runs.append(RunUsage(
                run_id=run.name, size_bytes=u["on_disk_bytes"],
                db_bytes=file_size(run / "data" / "atom.db") or 0,
                mtime_iso=time.strftime("%Y-%m-%dT%H:%M",
                                        time.localtime(run.stat().st_mtime)),
                hardlinked_files=len(u["hardlinked"])))
        breakdown["run_data"] = sum(r.size_bytes for r in runs)

    for log_name in ("server.log", "preview_backend.log", "preview_frontend.log"):
        n = file_size(world / log_name)
        if n:
            breakdown[log_name] = n

    build_cache = 0
    build_cache_source = "none (no frontend farm for this world)"
    farm = FRONTEND / ".preview-instance" / world.name
    if farm.is_dir():
        for d in sorted(farm.glob(".next-preview-*")):
            build_cache += size_of(d) or 0
            build_cache_source = f"measured:{d}"
    breakdown["build_cache"] = build_cache

    probe = Path(free_probe) if free_probe else _existing_ancestor(world)
    free = real_free_bytes(probe)
    headroom = live_db_headroom()
    warnings: List[str] = []
    if total["hardlinked"]:
        warnings.append(
            f"{len(total['hardlinked'])} hard-linked file(s) in this world; the "
            f"on-disk total double-counts them. First: {total['hardlinked'][0]}")
    usable = max(0, free - headroom.total_bytes)
    if usable < DEFAULT_RUN_CAP * 400 * MB:
        warnings.append(
            f"free space minus reserved headroom is {human(usable)}, about "
            f"{usable / (400 * MB):.1f} run directories. The next world/run "
            f"build will refuse.")
    for r in runs:
        if r.hardlinked_files:
            warnings.append(
                f"{r.run_id}: {r.hardlinked_files} hard-linked file(s) — writable "
                f"state must not be shared; check this before trusting its data")

    return {
        "world": world.name,
        "path": str(world),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_on_disk_bytes": total["on_disk_bytes"],
        "total_apparent_bytes": total["apparent_bytes"],
        "file_count": total["files"],
        "breakdown_bytes": breakdown,
        "build_cache_source": build_cache_source,
        "run_count": len(runs),
        "runs": [r.as_dict() for r in runs],
        "run_data_bytes": breakdown.get("run_data", 0),
        "free_bytes": free,
        "free_probe": str(probe),
        "reserved_headroom_bytes": headroom.total_bytes,
        "headroom": headroom.as_dict(),
        "usable_after_reserve_bytes": usable,
        "warnings": warnings,
        "note": ("symlinks are not followed: backend_root is a farm pointing at "
                 "code/ and data/, which are already counted above"),
    }


def render_report(rep: Dict[str, Any]) -> str:
    lines = [
        "=" * 78,
        f"STORAGE — world {rep['world']!r}   {rep['generated_at']}",
        "=" * 78,
        f"  total on disk : {human(rep['total_on_disk_bytes'])} "
        f"({rep['file_count']} files)",
        f"  free          : {human(rep['free_bytes'])} at {rep['free_probe']}",
        f"  reserved      : {human(rep['reserved_headroom_bytes'])} for the live DB "
        f"(live {human(rep['headroom']['live_db']['bytes'])}"
        f" + WAL {human(rep['headroom']['live_wal']['bytes'])}"
        f" + snapshot floor {human(rep['headroom']['snapshot_floor']['bytes'])})",
        f"  usable now    : {human(rep['usable_after_reserve_bytes'])}",
        "",
        "  breakdown (what explains the total):",
    ]
    for k, v in sorted(rep["breakdown_bytes"].items(), key=lambda kv: -kv[1]):
        if v:
            note = f"   ({rep['build_cache_source']})" if k == "build_cache" else ""
            lines.append(f"    {k:<24} {human(v):>10}{note}")
    if rep["runs"]:
        lines += ["", f"  runs ({rep['run_count']}), newest last:"]
        for r in rep["runs"]:
            share = (r["db_bytes"] / r["size_bytes"] * 100) if r["size_bytes"] else 0
            lines.append(f"    {r['run_id']:<20} {human(r['size_bytes']):>9}  "
                         f"db={human(r['db_bytes'])} ({share:.0f}%)  {r['mtime']}")
    if rep["warnings"]:
        lines += ["", "  WARNINGS:"]
        lines += [f"    - {w}" for w in rep["warnings"]]
    lines += ["", f"  {rep['note']}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def render_space(rep: SpaceReport) -> str:
    lines = [
        f"space check OK for {rep.estimate.target}",
        f"  free    : {human(rep.free_bytes)} ({rep.free_bytes_source}) at {rep.probe_path}",
        f"  need    : {human(rep.estimate.total_bytes)}",
        f"  reserve : {human(rep.headroom.total_bytes)}",
    ]
    for c in rep.estimate.components:
        lines.append(f"    {c.name:<14} {human(c.bytes):>10}  {c.source}")
    for c in (rep.headroom.live_db, rep.headroom.live_wal, rep.headroom.snapshot_floor):
        lines.append(f"    {c.name:<14} {human(c.bytes):>10}  {c.source}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="storage_policy", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("space", help="estimate a world build and report the verdict")
    p.add_argument("--world", required=True)
    p.add_argument(FULL_DEV_DB_FLAG, dest="full_dev_db", action="store_true",
                   help="assume the ENTIRE live dev database will be copied "
                        "into the world. This is a full copy of "
                        "data/atom.db -- 413,360,128 bytes measured "
                        "2026-09-28, ~392 MB per world AND ~391 MB per run "
                        "directory seeded from it. OFF by default: a world is "
                        "built from a small API-seeded fixture (the app's own "
                        "schema, zero dev rows, 8,478,720 bytes, live database "
                        "never opened). Pass this only for a case that genuinely "
                        "needs dev data.")
    p.add_argument("--no-build-cache", action="store_true")
    p.add_argument("--no-run-data", action="store_true")
    p.add_argument("--free-bytes", type=int, default=None,
                   help="override the free-space probe (testing/dry runs)")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("inventory", help="write the deletion inventory (deletes nothing)")
    p.add_argument("--world", required=True)
    p.add_argument("--cap", type=int, default=DEFAULT_RUN_CAP)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", default="", help="also write the inventory JSON here")

    p = sub.add_parser("cleanup",
                       help="inventory, then delete ONLY droppable runs "
                            "— and only with the interlock held AND a "
                            "reviewed inventory digest")
    p.add_argument("--world", required=True)
    p.add_argument("--cap", type=int, default=DEFAULT_RUN_CAP)
    p.add_argument("--confirm-drop", action="store_true",
                   help="REQUIRED to delete anything. Without it the inventory "
                        "is written and nothing is removed. Not sufficient on "
                        "its own: the maintenance interlock must also be held "
                        "and --reviewed-digest must match.")
    p.add_argument("--reviewed-digest", default="",
                   help="REQUIRED to delete anything: the digest printed by the "
                        "inventory run you read. A mismatch means the inventory "
                        "changed after you reviewed it, and the deletion is "
                        "refused.")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("report", help="per-world and per-run storage report")
    p.add_argument("--world", required=True)
    p.add_argument("--max-runs", type=int, default=0)
    p.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    world = WORLDS_ROOT / args.world

    if args.cmd == "space":
        src = resolve_fixture_source(args.full_dev_db)
        est = estimate_world_build(
            world, full_dev_db=src.is_full_dev_db,
            with_build_cache=not args.no_build_cache,
            with_run_data=not args.no_run_data)
        try:
            rep = check_space(est, free_bytes=args.free_bytes)
        except InsufficientStorage as exc:
            if args.json:
                print(json.dumps({"ok": False, "message": str(exc),
                                  "estimate": est.as_dict()}, indent=2))
            else:
                print(str(exc))
            return 1
        print(json.dumps(rep.as_dict(), indent=2) if args.json else render_space(rep))
        return 0

    if args.cmd in ("inventory", "cleanup"):
        inv = build_inventory(world, cap=args.cap)
        # `--confirm-drop` is only defined on the cleanup subparser, so reading
        # it unconditionally made `inventory` die with an AttributeError --
        # i.e. the dry run, the step the whole policy depends on, was the one
        # command that could not be run.
        confirm = bool(getattr(args, "confirm_drop", False))
        result = apply_inventory(
            inv, confirm=confirm, world=world,
            reviewed_digest=getattr(args, "reviewed_digest", "") or None)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(inv.to_text())
            if result.get("refused"):
                print(f"\nREFUSING TO DELETE: {result['refused']}\n"
                      f"Nothing was removed. To proceed, hold the interlock and "
                      f"re-run with the digest above:\n"
                      f"  python -m core.world_storage_guard lock --reason 'retention'\n"
                      f"  python -m scripts.orchestration_acceptance.storage_policy "
                      f"cleanup --world {args.world} --confirm-drop "
                      f"--reviewed-digest {inv.digest}")
            elif confirm:
                print(f"\ndeleted {len(result['deleted'])} run(s), freed "
                      f"{human(result['freed_bytes'])}")
                for f in result["failed"]:
                    print(f"  FAILED {f['run_id']}: {f['error']}")
            else:
                print("\nnothing deleted (no --confirm-drop)")
        if getattr(args, "out", ""):
            Path(args.out).write_text(json.dumps(inv.as_dict(), indent=2))
        return 1 if result.get("refused") else 0

    if args.cmd == "report":
        rep = world_storage_report(world, max_runs=args.max_runs)
        print(json.dumps(rep, indent=2) if args.json else render_report(rep))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
