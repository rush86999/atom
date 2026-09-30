"""Storage preflight + maintenance interlock for isolated acceptance worlds.

Why this exists
---------------
``backend/data/acceptance_worlds`` is planned to move onto the external
drive, with the canonical path preserved as a symlink. Two failure modes
make that unsafe to do casually, and BOTH of them are silent:

1. **Silent empty world.** Every world launcher ends up calling
   ``world.mkdir(parents=True, exist_ok=True)`` (preview_stack.save_state,
   run_isolated.main_async, preview_launch). If the worlds root is ever a
   plain local directory again — drive unmounted and the symlink replaced,
   or a restore that recreated it — that mkdir *succeeds* and produces a
   brand-new empty world. A run then "passes" against nothing. This is the
   same class of incident as ``core/db_safety.py`` (2026-09-04), where a
   stray script emptied the dev DB and the app silently re-seeded a blank
   world.

2. **Concurrent writers.** Worlds are built by several launchers at once
   (a preview stack, the acceptance harness, ad-hoc agents). Stopping
   processes once is not enough: a supervisor respawns them, so a relocation
   can race a respawn and snapshot a half-written world. Writers must be
   *refused* by the launchers themselves, not merely killed.

What this module provides
-------------------------
``preflight()``
    The single storage check every world launcher calls BEFORE it creates
    anything. Rejects, with an actionable message:

    * a maintenance interlock being active,
    * a missing/unmounted expected volume,
    * a volume whose identity (name or UUID) is not the configured one,
    * a dangling worlds symlink,
    * a worlds root that is a plain local directory when the configured
      layout requires a drive-backed symlink,
    * worlds-root symlinks that do not resolve to the configured target,
    * already-broken or wrongly-anchored internal world symlinks.

``acquire_maintenance_lock()`` / ``release_maintenance_lock()``
    The interlock. Take the lock FIRST, then stop writers; that ordering is
    the only one that converges, because a lock is observed cooperatively
    while ``kill`` is not.

Design rules
------------
* **Configuration lives outside the movable tree.** It is read from
  ``backend/config/world_storage.json``; nothing under
  ``backend/data/acceptance_worlds`` is ever trusted as configuration.
  (``backend/data/`` is gitignored, so config could not live there anyway.)
* **Anchored to ``backend/``, never CWD-relative** (AGENTS.md path-anchoring
  rule).
* **No I/O error swallowing.** A startup check cannot protect against the
  drive being unplugged *while a world is running*, so this module does not
  pretend to. ``EIO``/``ENOENT`` from a running server propagate to the
  caller unchanged and stay loud. Nothing here retries or caches a
  "probably fine" verdict across calls.
* **Default-off.** With no config file, or ``enabled: false``,
  ``preflight()`` is a no-op, so adding the guard cannot break a fresh
  install or the local-only layout.
"""
from __future__ import annotations

import atexit
import fcntl
import json
import logging
import os
import plistlib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# backend/core/world_storage_guard.py -> backend/
BACKEND = Path(__file__).resolve().parents[1]
CONFIG_PATH = BACKEND / "config" / "world_storage.json"
LOCK_PATH = BACKEND / "config" / "world_storage.maintenance.lock"
#: flock target. This — not LOCK_PATH — is the atomic gate (see below).
REGISTRY_LOCK_PATH = BACKEND / "config" / "world_storage.registry.lock"
#: One small record per live launcher, so a blocked relocation can NAME what
#: is holding worlds open instead of just timing out.
RUNNERS_DIR = BACKEND / "config" / "world_storage_runners"

#: Escape hatch for an operator who has verified the storage by hand.
#: Deliberately an env var, not a flag: it must be visible in the process
#: environment of whatever is being launched.
BYPASS_ENV = "ATOM_WORLD_STORAGE_BYPASS"

_BANNER = "=" * 72

#: fd of the exclusive lock held by this process while a window is open.
_MAINTENANCE_FD: Optional[int] = None
#: This process's held shared runner lock, if it registered.
_REGISTRATION: Optional["Registration"] = None

# Relocate every lock/config path under one directory. Unset in production, so
# this is a no-op there; it exists so an isolated run (notably the interlock
# tests, which need parent and child processes to agree on the SAME lock) can
# redirect all four paths together. Splitting them would defeat the point: a
# launcher and a maintenance command that disagree about the lock file are not
# interlocked at all.
_PATHS_ENV = "ATOM_WORLD_STORAGE_PATHS"
if os.environ.get(_PATHS_ENV):
    _p = Path(os.environ[_PATHS_ENV])
    CONFIG_PATH = _p / CONFIG_PATH.name
    LOCK_PATH = _p / LOCK_PATH.name
    REGISTRY_LOCK_PATH = _p / REGISTRY_LOCK_PATH.name
    RUNNERS_DIR = _p / RUNNERS_DIR.name

LAYOUT_LOCAL = "local"
LAYOUT_DRIVE_SYMLINK = "drive_symlink"


class WorldStorageError(RuntimeError):
    """Raised when the worlds root is not in the configured, expected state.

    Deliberately a hard failure. Every call site is a launcher that is about
    to create or write a world, so continuing would mean writing into an
    unverified location.
    """


@dataclass
class WorldStorageConfig:
    enabled: bool = False
    layout: str = LAYOUT_LOCAL
    root: Path = field(default_factory=lambda: BACKEND / "data" / "acceptance_worlds")
    link_target: Optional[Path] = None
    volume_mount: Optional[Path] = None
    volume_name: Optional[str] = None
    volume_uuid: Optional[str] = None
    # How many internal world symlinks to spot-check for resolution.
    #   > 0  sample that many (the tree holds >10k links and this runs on
    #        every launch)
    #   = 0  skip the audit entirely
    #   < 0  audit every link
    symlink_sample: int = 25
    # Reject a broken internal symlink during preflight. Off by default:
    # pre-existing broken links are a data condition to report, not a
    # reason to block an unrelated run.
    fail_on_broken_symlinks: bool = False

    @property
    def is_drive_layout(self) -> bool:
        return self.layout == LAYOUT_DRIVE_SYMLINK


@dataclass
class PreflightReport:
    ok: bool
    checks: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    broken_symlinks: List[str] = field(default_factory=list)
    misanchored_symlinks: List[str] = field(default_factory=list)
    bypassed: bool = False
    #: Cap on per-item detail in summary(). Full lists stay available via
    #: the `audit-symlinks` subcommand; a launcher that printed 10k links on
    #: every start would be unreadable and would train people to ignore it.
    detail_limit: int = 3

    def summary(self) -> str:
        if self.ok:
            head = "world storage preflight OK"
        else:
            head = f"world storage preflight FAILED ({len(self.problems)} problem(s))"
        if self.bypassed:
            head += f" [BYPASSED via {BYPASS_ENV}]"
        lines = [head]
        lines += [f"  ok       {c}" for c in self.checks]
        lines += [f"  PROBLEM  {p}" for p in self.problems]
        for label, items in (
            ("broken", self.broken_symlinks),
            ("mis-anchored", self.misanchored_symlinks),
        ):
            if not items:
                continue
            note = (
                " (preserved verbatim by rsync -a)"
                if label == "broken"
                else " (correct only while the worlds root is itself a symlink)"
            )
            lines.append(f"  {label} internal symlinks: {len(items)}{note}")
            lines += [f"    - {s}" for s in items[: self.detail_limit]]
            if len(items) > self.detail_limit:
                lines.append(
                    f"    ... and {len(items) - self.detail_limit} more "
                    f"(python -m core.world_storage_guard audit-symlinks --all)"
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config(path: Optional[Path] = None) -> WorldStorageConfig:
    """Read the expected worlds root + volume identity.

    A missing file is not an error: the guard is default-off so a fresh
    install or a local-only layout is unaffected.
    """
    p = path or CONFIG_PATH
    if not p.is_file():
        return WorldStorageConfig()
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        # A corrupt config must not silently disable the guard.
        raise WorldStorageError(
            f"world storage config is unreadable: {p}: {exc}. "
            f"Fix the file or remove it to run unverified."
        ) from exc

    worlds = raw.get("worlds") or {}
    volume = raw.get("volume") or {}

    root = worlds.get("root")
    resolved_root = _anchor(root) if root else (BACKEND / "data" / "acceptance_worlds")
    link_target = worlds.get("link_target")
    volume_mount = volume.get("mount_point")

    # `layout` is read from BOTH the top level and inside `worlds`. The two
    # spellings existed simultaneously during development and the code read
    # one while the shipped file used the other — which meant a config saying
    # "drive_symlink" was silently IGNORED, and the guard would never enforce
    # the symlink requirement it exists to enforce. Accepting both here, plus
    # test_load_shipped_config_layout_is_honoured, keeps that class of drift
    # from coming back.
    layout = worlds.get("layout") or raw.get("layout") or LAYOUT_LOCAL
    if layout not in (LAYOUT_LOCAL, LAYOUT_DRIVE_SYMLINK):
        raise WorldStorageError(f"unknown worlds layout {layout!r} in {p}")

    return WorldStorageConfig(
        enabled=bool(raw.get("enabled", False)),
        layout=layout,
        root=resolved_root,
        link_target=_anchor(link_target) if link_target else None,
        volume_mount=Path(volume_mount) if volume_mount else None,
        volume_name=volume.get("name"),
        volume_uuid=volume.get("uuid"),
        symlink_sample=int(raw.get("symlink_sample", 25)),
        fail_on_broken_symlinks=bool(raw.get("fail_on_broken_symlinks", False)),
    )


def _anchor(p: str) -> Path:
    """Resolve a config path.

    Absolute paths are used as-is. Relative paths are anchored to
    ``backend/`` so the guard behaves identically regardless of CWD
    (AGENTS.md: never CWD-relative).
    """
    path = Path(p)
    return path if path.is_absolute() else (BACKEND / path)


# ---------------------------------------------------------------------------
# Maintenance interlock
# ---------------------------------------------------------------------------
def _read_lock() -> Optional[Dict[str, Any]]:
    if not LOCK_PATH.is_file():
        return None
    try:
        return json.loads(LOCK_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        # An unreadable lock is treated as ACTIVE. Failing closed is the
        # whole point: a lock we cannot read must not silently permit writes.
        logger.error("maintenance lock unreadable at %s: %s", LOCK_PATH, exc)
        return {"active": True, "reason": f"unreadable lock file: {exc}"}


def lock_active() -> bool:
    lock = _read_lock()
    return bool(lock and lock.get("active"))


# ---------------------------------------------------------------------------
# Runner registration — the atomic half of the interlock
# ---------------------------------------------------------------------------
# WHY THIS EXISTS, and why the lock FILE alone is not enough
# -----------------------------------------------------------
# A lock file closes only half the race. A launcher can read "no lock", pass
# preflight, and be descheduled; the operator then writes the lock file and
# believes the tree is quiesced — while that launcher wakes up and starts
# writing worlds. The flag was checked at T0 and acted on at T1, and nothing
# holds T0 and T1 together.
#
# So the gate is an advisory lock, not a flag:
#
#   launcher   -> flock(REGISTRY_LOCK, LOCK_SH)  held for the whole process
#                 lifetime, i.e. across the entire check-to-launch window
#   maintenance -> flock(REGISTRY_LOCK, LOCK_EX)  acquired BLOCKING, so it
#                 cannot complete until every registered launcher has exited
#
# flock is the right primitive because the kernel drops it when the process
# dies: a SIGKILLed launcher cannot wedge a relocation shut, and there are no
# stale lock files to reap. LOCK_NB on the launcher side means a launcher that
# arrives during a window is refused immediately with a clear message rather
# than hanging.
#
# The lock FILE is kept as well, and for two reasons: it carries the operator's
# reason string for the refusal message, and it keeps refusing after the
# maintenance process exits and its flock is released. The file is the
# persistent gate; the flock is the drain barrier.


class Registration:
    """A held shared lock plus its runner record. Released on close/exit."""

    def __init__(self, fd: int, record: Path, payload: Dict[str, Any]) -> None:
        self._fd = fd
        self._record = record
        self.payload = payload
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._fd < 0:
            return  # bypass sentinel: no lock was ever taken
        try:
            self._record.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self._fd)
        except OSError:
            pass

    def __enter__(self) -> "Registration":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _reap_dead_runners() -> None:
    """Delete records whose process is gone.

    A SIGKILLed launcher releases its flock automatically but leaves its record
    behind, which would otherwise make `list_runners` report a phantom holder
    forever.
    """
    if not RUNNERS_DIR.is_dir():
        return
    for p in RUNNERS_DIR.glob("*.json"):
        try:
            pid = int(p.stem.split("-")[0])
        except (ValueError, IndexError):
            p.unlink(missing_ok=True)
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            p.unlink(missing_ok=True)
        except PermissionError:
            pass  # alive, owned by someone else


def list_runners() -> List[Dict[str, Any]]:
    _reap_dead_runners()
    out: List[Dict[str, Any]] = []
    if not RUNNERS_DIR.is_dir():
        return out
    for p in sorted(RUNNERS_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            out.append({"pid": p.stem, "error": "unreadable runner record"})
    return out


def register_runner(role: str = "launcher", **meta: Any) -> Registration:
    """Take a shared lock for this process's lifetime, or refuse.

    Call this INSTEAD of (or immediately after) a bare lock-file check, and
    hold the returned object open. That closes the check-to-launch window: the
    shared lock is what a relocation's exclusive lock has to wait on.
    """
    if os.environ.get(BYPASS_ENV):
        logger.warning("runner registration BYPASSED via %s", BYPASS_ENV)
        return Registration(-1, Path("/dev/null"), {"bypassed": True})

    RUNNERS_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(REGISTRY_LOCK_PATH), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        lock = _read_lock() or {}
        raise WorldStorageError(
            _lock_message(lock) if lock.get("active") else (
                "another session is holding worlds for a maintenance window "
                f"(could not take the shared runner lock: {exc}).\n"
                "  Wait for the window to finish, then retry."
            )
        ) from exc

    payload: Dict[str, Any] = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "role": role,
        "argv": sys.argv[:8],
        "cwd": os.getcwd(),
        "registered_at": time.time(),
        "registered_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        **meta,
    }
    record = RUNNERS_DIR / f"{os.getpid()}-{int(time.time() * 1000)}.json"
    try:
        record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError as exc:  # a record we cannot write is not worth failing over
        logger.warning("could not write runner record %s: %s", record, exc)
        record = Path("/dev/null")
    logger.info("registered %s runner pid=%s", role, os.getpid())
    return Registration(fd, record, payload)


def acquire_maintenance_lock(
    reason: str,
    *,
    operator: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
    drain_timeout: float = 0.0,
) -> Dict[str, Any]:
    """Mark worlds storage as under maintenance. Launchers then refuse.

    Acquires the registry lock EXCLUSIVELY and BLOCKINGLY, so this call does
    not return until every launcher that registered before it has finished.
    That is the difference between asserting quiescence and hoping for it:
    with ``drain_timeout=0`` (the default) it waits indefinitely, and on
    timeout it names the PIDs still holding worlds open.

    Ordering matters: call this BEFORE stopping writers. Killing processes is
    unreliable here because a supervisor respawns them, and a lock is observed
    by the launchers themselves.
    """
    RUNNERS_DIR.mkdir(parents=True, exist_ok=True)
    # If THIS process registered as a launcher earlier, drop that
    # registration before asking for the exclusive lock. Otherwise the
    # process would be blocking itself and the window could never open —
    # a footgun for any caller that preflights and then relocates.
    global _REGISTRATION
    if _REGISTRATION is not None:
        _REGISTRATION.close()
        _REGISTRATION = None

    fd = os.open(str(REGISTRY_LOCK_PATH), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + max(0.0, drain_timeout)
    waited = False
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError as exc:
            if time.monotonic() >= deadline:
                holders = list_runners()
                os.close(fd)
                lines = "\n".join(
                    f"    pid {h.get('pid')}  {h.get('role', '?')}  "
                    f"{' '.join(h.get('argv') or [])[:70]}"
                    for h in holders
                ) or "    (no runner records — a launcher may be mid-registration)"
                raise WorldStorageError(
                    "maintenance window CANNOT start: worlds are still in use.\n"
                    f"  waited {drain_timeout:.0f}s for in-flight launchers to finish.\n"
                    f"  still registered:\n{lines}\n"
                    "  Stop those PIDs (or wait for them) and retry. Refusing to\n"
                    "  claim a quiescent tree while a launcher is live — that is\n"
                    "  exactly the race this interlock exists to prevent."
                ) from exc
            if not waited:
                waited = True
                logger.warning(
                    "waiting for in-flight world launchers to finish (drain)..."
                )
            time.sleep(0.2)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "active": True,
        "reason": reason,
        "operator": operator or os.environ.get("USER", "unknown"),
        "pid": os.getpid(),
        "acquired_at": time.time(),
        "acquired_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "drained": waited,
        "drain_waited_s": round(drain_timeout - max(0.0, (deadline - time.monotonic())), 1)
        if waited
        else 0.0,
    }
    if ttl_seconds:
        payload["ttl_seconds"] = int(ttl_seconds)
    LOCK_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    # Keep the exclusive lock open for this process's lifetime. When the
    # process exits the kernel drops it, and LOCK_PATH continues to refuse
    # launches on its own.
    global _MAINTENANCE_FD
    _MAINTENANCE_FD = fd
    logger.warning("maintenance lock ACQUIRED (drained=%s): %s", waited, reason)
    return payload


def release_maintenance_lock() -> None:
    global _MAINTENANCE_FD
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()
    if _MAINTENANCE_FD is not None:
        try:
            fcntl.flock(_MAINTENANCE_FD, fcntl.LOCK_UN)
            os.close(_MAINTENANCE_FD)
        except OSError:
            pass
        _MAINTENANCE_FD = None
    logger.warning("maintenance lock RELEASED")


def _lock_message(lock: Dict[str, Any]) -> str:
    return (
        "worlds storage is under MAINTENANCE LOCK — refusing to start.\n"
        f"  reason : {lock.get('reason', 'unspecified')}\n"
        f"  by     : {lock.get('operator', '?')} (pid {lock.get('pid', '?')})\n"
        f"  at     : {lock.get('acquired_at_iso', '?')}\n"
        "  Worlds are mid-relocation or being verified. Another session is\n"
        "  writing worlds right now would race the relocation and could\n"
        "  produce a torn snapshot. Wait for the window, or release the lock\n"
        "  with: python -m core.world_storage_guard release"
    )


# ---------------------------------------------------------------------------
# Volume identity
# ---------------------------------------------------------------------------
def volume_identity(mount_point: Path) -> Dict[str, str]:
    """Read name + UUID for a mounted volume via ``diskutil``.

    Name alone is not identity: a volume can be renamed, and two volumes can
    share a name. The UUID is what actually pins "this is the drive we
    copied onto".
    """
    try:
        out = subprocess.run(
            ["diskutil", "info", str(mount_point)],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorldStorageError(
            f"cannot read identity of {mount_point}: {exc}"
        ) from exc

    info: Dict[str, str] = {}
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        info[key.strip()] = value.strip()

    # Fall back to the plist form for keys the text form omits.
    if "Volume UUID" not in info or "Volume Name" not in info:
        try:
            raw = subprocess.run(
                ["diskutil", "info", "-plist", str(mount_point)],
                capture_output=True,
                check=True,
                timeout=30,
            ).stdout
            plist = plistlib.loads(raw)
            for key, out_key in (
                ("VolumeName", "Volume Name"),
                ("VolumeUUID", "Volume UUID"),
                ("APFSVolumeUUID", "APFS Volume UUID"),
            ):
                val = plist.get(key)
                if isinstance(val, bytes):
                    val = val.decode("utf-8", "replace")
                if val:
                    info.setdefault(out_key, str(val))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

    return info


# ---------------------------------------------------------------------------
# Internal symlink audit
# ---------------------------------------------------------------------------
def audit_internal_symlinks(
    root: Path, sample: int = 25
) -> tuple[List[str], List[str]]:
    """Return ``(broken, misanchored)`` internal world symlinks.

    Two distinct defects, deliberately reported separately because
    ``rsync -a`` preserves BOTH silently:

    ``broken``
        The target does not resolve. Pre-existing damage, or damage from a
        copy that followed links.

    ``misanchored``
        An absolute link that points back into the canonical worlds root
        (e.g. ``.../acceptance_worlds/<world>/code/backend/x``). These are
        correct only while the canonical root is itself a symlink into the
        drive. If the root is ever a real directory again they still
        resolve, but they silently point back at the *old* tree — which is
        exactly the "looks fine, reads the wrong world" failure.

    Sampling is bounded: the tree holds >10k links and this runs on every
    launch. ``sample <= 0`` audits ALL of them; the caller decides whether
    that is affordable (see ``WorldStorageConfig.symlink_sample``, where
    ``0`` instead means "skip the audit" and only a negative value means
    "audit everything").
    """
    broken: List[str] = []
    misanchored: List[str] = []
    if not root.is_dir():
        return broken, misanchored

    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in list(dirnames) + filenames:
            p = Path(dirpath) / name
            if not p.is_symlink():
                continue
            seen += 1
            if sample > 0 and seen > sample:
                return broken, misanchored
            try:
                target = os.readlink(p)
            except OSError:
                broken.append(f"{p} (unreadable link)")
                continue
            if not p.exists():
                broken.append(f"{p} -> {target}")
            elif os.path.isabs(target) and str(root) in target:
                misanchored.append(f"{p} -> {target}")
    return broken, misanchored


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
def preflight(config: Optional[WorldStorageConfig] = None) -> PreflightReport:
    """Verify worlds storage before any launcher creates or writes anything.

    Raises :class:`WorldStorageError` on failure. Returns a report on
    success so callers can log what was actually verified.
    """
    if os.environ.get(BYPASS_ENV):
        logger.warning(
            "world storage preflight BYPASSED via %s — storage NOT verified", BYPASS_ENV
        )
        return PreflightReport(
            ok=True, bypassed=True, checks=[f"bypassed via {BYPASS_ENV}"]
        )

    cfg = config or load_config()
    if not cfg.enabled:
        return PreflightReport(
            ok=True, checks=["guard disabled in config (default) — storage not checked"]
        )

    report = PreflightReport(ok=True)

    # 1. Interlock first: cheapest check, and the reason it exists.
    lock = _read_lock()
    if lock and lock.get("active"):
        raise WorldStorageError(_lock_message(lock))
    report.checks.append("no maintenance lock")

    # 2. Volume present and identifiable.
    if cfg.is_drive_layout:
        if cfg.volume_mount is None:
            raise WorldStorageError(
                "config layout is drive_symlink but volume.mount_point is unset"
            )
        if not cfg.volume_mount.is_dir():
            raise WorldStorageError(
                f"expected volume is NOT mounted at {cfg.volume_mount}.\n"
                "  The worlds live on that drive. Replug it (macOS mounts it\n"
                "  automatically a few seconds after plug-in) and retry.\n"
                "  Refusing to run: proceeding would create a NEW local\n"
                "  acceptance_worlds and silently start writing to it."
            )
        report.checks.append(f"volume mounted at {cfg.volume_mount}")

        info = volume_identity(cfg.volume_mount)
        actual_name = info.get("Volume Name", "")
        actual_uuid = info.get("Volume UUID") or info.get("APFS Volume UUID", "")
        if cfg.volume_name and actual_name != cfg.volume_name:
            raise WorldStorageError(
                f"volume name mismatch at {cfg.volume_mount}: "
                f"expected {cfg.volume_name!r}, found {actual_name!r}. "
                "Refusing to treat a different volume as the worlds drive."
            )
        if cfg.volume_uuid and actual_uuid != cfg.volume_uuid:
            raise WorldStorageError(
                f"volume UUID mismatch at {cfg.volume_mount}: "
                f"expected {cfg.volume_uuid}, found {actual_uuid or 'unknown'}. "
                "This is a different device than the one the worlds were "
                "copied onto. Refusing to continue."
            )
        report.checks.append(
            f"volume identity ok (name={actual_name!r} uuid={actual_uuid})"
        )

    # 3. Worlds root shape.
    root = cfg.root
    if root.is_symlink():
        if not root.exists():
            target = os.readlink(root)
            raise WorldStorageError(
                f"worlds root symlink is DANGLING: {root} -> {target}\n"
                "  The drive is missing or was renamed. Refusing to run:\n"
                "  a launcher that proceeded would recreate a local\n"
                "  acceptance_worlds and write a fresh, empty world."
            )
        if cfg.link_target is not None:
            actual = Path(os.path.realpath(root))
            expected = Path(os.path.realpath(cfg.link_target))
            if actual != expected:
                raise WorldStorageError(
                    f"worlds root symlink points at the wrong place:\n"
                    f"  {root} -> {actual}\n"
                    f"  expected -> {expected}\n"
                    "  Refusing to run against an unexpected location."
                )
        report.checks.append(
            f"worlds root is a symlink resolving to {os.path.realpath(root)}"
        )

    elif root.is_dir():
        if cfg.is_drive_layout:
            raise WorldStorageError(
                f"worlds root is a plain local DIRECTORY: {root}\n"
                "  Config expects it to be a symlink into the worlds drive.\n"
                "  This is the failure that silently produces empty worlds:\n"
                "  launchers would mkdir happily and write into a fresh tree.\n"
                "  Restore the symlink (or set layout to 'local' in\n"
                f"  {CONFIG_PATH} if the move was abandoned)."
            )
        report.checks.append(f"worlds root is a local directory ({root})")
    else:
        raise WorldStorageError(
            f"worlds root does not exist and is not a symlink: {root}\n"
            "  Refusing to run: the first mkdir would create a new tree\n"
            "  that is not the verified one."
        )

    # 4. Spot-check internal symlinks (reported; blocking only on request).
    #    symlink_sample == 0 disables the audit; < 0 audits every link.
    if cfg.symlink_sample != 0:
        broken, misanchored = audit_internal_symlinks(root, cfg.symlink_sample)
        report.broken_symlinks = broken
        report.misanchored_symlinks = misanchored
        if broken:
            if cfg.fail_on_broken_symlinks:
                raise WorldStorageError(
                    f"{len(broken)} broken internal symlink(s) under {root}:\n"
                    + "\n".join(f"  - {b}" for b in broken[:20])
                    + "\n  These are preserved verbatim by `rsync -a`. Fix or"
                    " accept them explicitly before relocating."
                )
            logger.warning(
                "%d broken internal symlink(s) under %s (preserved by rsync -a)",
                len(broken),
                root,
            )
        if misanchored:
            logger.warning(
                "%d internal symlink(s) anchored to the canonical worlds root; "
                "correct only while that root is itself a symlink",
                len(misanchored),
            )

    if not report.ok:  # pragma: no cover - defensive; problems are raised above
        raise WorldStorageError(report.summary())
    return report


def assert_worlds_root_usable(
    config: Optional[WorldStorageConfig] = None, *, where: str = ""
) -> None:
    """Cheap root-shape + interlock check, safe to call at every mkdir site.

    ``preflight()`` is the thorough entry check: it shells out to
    ``diskutil`` and walks a sample of internal symlinks, which is too much
    to repeat on every state save. This variant only answers the question
    that actually guards a ``mkdir``:

        is the worlds root the shape the config says it is, and is the
        maintenance interlock down?

    Raises :class:`WorldStorageError` otherwise. Cheap enough (a few stat
    calls) to sit directly in front of the ``mkdir(parents=True,
    exist_ok=True)`` calls that would otherwise create an empty world.
    """
    if os.environ.get(BYPASS_ENV):
        return
    cfg = config or load_config()
    if not cfg.enabled:
        return

    at = f" (while {where})" if where else ""

    lock = _read_lock()
    if lock and lock.get("active"):
        raise WorldStorageError(_lock_message(lock) + at)

    root = cfg.root
    if root.is_symlink() and not root.exists():
        raise WorldStorageError(
            f"worlds root symlink is DANGLING{at}: {root} -> {os.readlink(root)}\n"
            "  Refusing to create anything: the tree it should point at is gone."
        )
    if cfg.is_drive_layout and root.is_dir() and not root.is_symlink():
        raise WorldStorageError(
            f"worlds root is a plain local DIRECTORY{at}: {root}\n"
            "  Config expects a symlink into the worlds drive. Refusing to\n"
            "  mkdir here: that is how an empty world gets created silently."
        )
    if not root.exists():
        raise WorldStorageError(
            f"worlds root does not exist and is not a symlink{at}: {root}\n"
            "  Refusing to create it: a fresh tree is not the verified one."
        )


def require_storage_ready(config: Optional[WorldStorageConfig] = None) -> PreflightReport:
    """Launcher entry point: run the preflight, print it, raise on failure.

    Deliberately chatty. The operator running a preview needs to see WHAT was
    verified, because the failure mode this guards against is invisible.

    On failure the banner is printed once here and the error is re-raised, so
    a caller that also reports the error must not print it again. Launcher
    entry points should use :func:`guarded_entry` to turn the raise into a
    clean non-zero exit instead of a traceback.
    """
    try:
        report = preflight(config)
    except WorldStorageError as exc:
        print(f"\n{_BANNER}\nWORLD STORAGE PREFLIGHT FAILED\n{_BANNER}\n{exc}\n", flush=True)
        raise
    print(report.summary(), flush=True)
    # Register AFTER the checks pass, and hold the shared lock for this
    # process's lifetime. This is what closes the check-to-launch window: a
    # relocation's exclusive lock cannot be granted while we hold this, so a
    # launcher that passed preflight microseconds before the window opened is
    # still accounted for. A bare lock-file check could not do that.
    _register_current_process()
    return report


def _register_current_process() -> Optional[Registration]:
    global _REGISTRATION
    if _REGISTRATION is not None:
        return _REGISTRATION
    reg = register_runner(role="launcher")
    _REGISTRATION = reg
    # Release on normal exit so short-lived commands do not leave records
    # behind. The flock is dropped by the kernel either way; this only cleans
    # up the bookkeeping file. A SIGKILLed launcher is handled by
    # _reap_dead_runners() instead.
    atexit.register(reg.close)
    return reg


def guarded_entry(fn):
    """Wrap a launcher ``main`` so a storage refusal exits 1 without a traceback.

    The refusal is an expected, actionable outcome — a drive is unplugged, a
    window is locked — not a crash. A traceback buries the recovery
    instructions that ``preflight`` took care to write.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except WorldStorageError as exc:
            print(
                f"\n{_BANNER}\nREFUSING TO START: world storage\n{_BANNER}\n"
                f"{exc}\n"
                "No world was created and nothing was written.\n",
                flush=True,
            )
            raise SystemExit(1) from None

    return wrapper


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Worlds storage guard utilities.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="Run the preflight and report.")

    p_lock = sub.add_parser("lock", help="Acquire the maintenance interlock.")
    p_lock.add_argument("--reason", required=True)
    p_lock.add_argument("--operator", default=None)
    p_lock.add_argument(
        "--drain-timeout",
        type=float,
        default=0.0,
        help="seconds to wait for in-flight launchers to finish (0 = wait forever)",
    )

    p_rel = sub.add_parser("release", help="Release the maintenance interlock.")
    p_rel.add_argument("--yes", action="store_true", help="Required safety flag.")

    sub.add_parser("runners", help="List launchers currently holding worlds open.")

    p_audit = sub.add_parser("audit-symlinks", help="Audit internal world symlinks.")
    p_audit.add_argument("--all", action="store_true", help="Audit every link, not a sample.")
    p_audit.add_argument("--max-report", type=int, default=50)

    args = ap.parse_args(argv)

    if args.cmd == "check":
        # Clean message + non-zero exit. A launcher-facing diagnostic that
        # ends in a traceback trains people to skip reading it, and this is
        # the message an operator reads mid-window.
        try:
            report = require_storage_ready()
        except WorldStorageError:
            return 1  # banner + message already printed by require_storage_ready
        return 0 if report.ok else 1

    if args.cmd == "lock":
        try:
            payload = acquire_maintenance_lock(
                args.reason,
                operator=args.operator,
                drain_timeout=args.drain_timeout,
            )
        except WorldStorageError as exc:
            print(f"\n{_BANNER}\nMAINTENANCE WINDOW REFUSED\n{_BANNER}\n{exc}\n")
            return 1
        print(json.dumps(payload, indent=2, sort_keys=True))
        if payload.get("drained"):
            print(
                "\nDrained: waited for in-flight launchers to finish before "
                "granting the window. Quiescence is established, not assumed."
            )
        return 0

    if args.cmd == "runners":
        holders = list_runners()
        if not holders:
            print("no world launchers are currently registered")
            return 0
        print(f"{len(holders)} registered world launcher(s):")
        for h in holders:
            print(
                f"  pid {h.get('pid'):>7}  {h.get('role', '?'):<9} "
                f"{(h.get('argv') or ['?'])[0][-60:]}"
            )
            print(f"             since {h.get('registered_at_iso', '?')}")
        return 0

    if args.cmd == "release":
        if not args.yes:
            print("refusing to release the maintenance lock without --yes", flush=True)
            return 2
        release_maintenance_lock()
        print("maintenance lock released")
        return 0

    if args.cmd == "audit-symlinks":
        cfg = load_config()
        broken, misanchored = audit_internal_symlinks(
            cfg.root, 0 if args.all else cfg.symlink_sample
        )
        print(f"broken     : {len(broken)}")
        for b in broken[: args.max_report]:
            print(f"  - {b}")
        print(f"misanchored: {len(misanchored)}")
        for m in misanchored[: args.max_report]:
            print(f"  - {m}")
        return 1 if broken else 0

    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
