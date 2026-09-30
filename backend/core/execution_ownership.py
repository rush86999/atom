"""Which process owns a running execution, and is that process still alive?

WHY THIS EXISTS
`core.execution_recovery.reconcile_orphaned_executions()` exists to fail
executions that were `RUNNING` when a process died. It selects them by status
alone. That was safe only while it ran in a process that owned every running row
— which is not a property the boot sweep has, and never was: the moment a second
process opens the same database (a sibling API worker, a test run against the
live DB, an operator running a script), its boot sweep sees the *other* live
process's in-flight turns as ghosts and marks them failed underneath it.

A crashed turn being marked failed is the intended outcome. A live turn being
marked failed is data corruption: the turn keeps running, still holds its
reservation, and then tries to finalize into a row that now says it failed —
and nothing anywhere reports the contradiction, because both writes are
individually correct.

So ownership is recorded, and the sweep consults it:

  VERIFIED live owner   -> SKIP. Another live process is on it.
  VERIFIED dead owner   -> reconcile. "Dead" means no such pid, or a CONFIRMED
                           pid reuse (the OS start time differs from the one
                           recorded when the row was written).
  ANYTHING ELSE         -> mark ownership UNKNOWN and leave the row alone: no
                           status change, no release of its keyed request. A
                           missing stamp, an owner on another host, and a failed
                           liveness inspection are all "we cannot tell", and
                           "we cannot tell" is not "it died".

PID ALONE IS NOT ENOUGH
A dead worker's PID gets reused. Reconciling on "PID happens to be alive" would
leave a ghost forever, and skipping on "PID happens to be dead" would kill a live
turn. So the owner records a per-process token *and* the OS process start time;
liveness is `pid alive AND (start time unknown OR start time matches)`. When the
start time cannot be read on this platform, the token cannot help either — the
code says so in the returned reason rather than pretending to a certainty it does
not have.

Cross-host execution stays unsupported, and that is NOT a reason to treat an
unfamiliar host as dead: an owner on another host is classified UNKNOWN, which
leaves the row alone and reports it. Reconciling it would be a guess dressed as
a check, and the guess can fail a live turn.
"""
from __future__ import annotations

import os
import socket
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

#: Identifies THIS process for the life of THIS process. Generated once at
#: import, so every row this process writes carries the same value and a
#: restarted process can never claim the old token.
PROCESS_TOKEN = uuid.uuid4().hex

HOSTNAME = socket.gethostname()

OWNER_KEY = "owner"


def process_started_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_owner(metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return `metadata` with this process recorded as the owner.

    Idempotent and non-destructive: an existing owner is never overwritten, so a
    row handed on to another worker keeps the original claim unless that worker
    explicitly re-claims it. A metadata blob that is not a dict is passed through
    untouched rather than raising -- stamping must never be the reason a turn
    fails to start.
    """
    meta = dict(metadata) if isinstance(metadata, dict) else {}
    if isinstance(meta.get(OWNER_KEY), dict) and meta[OWNER_KEY].get("pid"):
        return meta
    meta[OWNER_KEY] = {
        "pid": os.getpid(),
        "token": PROCESS_TOKEN,
        "host": HOSTNAME,
        "process_started_at": process_started_at(),
    }
    return meta


def _process_state(pid: int) -> Optional[str]:
    """The OS process state of ``pid`` (``S``/``R``/``Z``/...), or None if this
    platform cannot tell us.

    psutil first: it reads the state without spawning anything, which matters
    because the acceptance worlds run under a seatbelt profile that DENIES
    ``process-exec`` -- ``ps`` fails there with EPERM, so a `ps`-only check
    silently returned None under test and the zombie verdict never fired (the
    finish-line F11 case, 2026-09-29). ``/proc`` and ``ps`` remain as fallbacks
    for a host where psutil is unavailable.
    """
    try:
        import psutil

        return psutil.Process(pid).status()
    except Exception:  # noqa: BLE001 — any failure just means "cannot tell"
        pass
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            fields = fh.read().rsplit(b")", 1)[-1].split()
        # First field after comm is the state character.
        return fields[0].decode()
    except (OSError, IndexError, ValueError):
        pass
    try:
        out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out or None
    except (OSError, subprocess.SubprocessError):
        return None


def _os_process_start(pid: int) -> Optional[str]:
    """The OS start time of `pid`, or None if this platform cannot tell us.

    Linux exposes it in /proc; macOS needs `ps`. Both are read-only and cost one
    small subprocess at most, and only during a boot sweep.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            fields = fh.read().rsplit(b")", 1)[-1].split()
        # After the comm field, starttime is field 22 overall -> index 19 here.
        return f"proc:{fields[19].decode()}"
    except (OSError, IndexError, ValueError):
        pass
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"ps:{out}" if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def owner_liveness(metadata: Optional[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Classify the owner recorded in an execution's metadata.

    Returns ``(state, detail)``. There are exactly three verdicts, and the third
    is the one that used to be missing:

    ``self``      this process owns the row. Hands off: we are the live worker.
    ``live``      another process on this host owns it and is still running.
                  VERIFIED, so the row is left untouched.
    ``dead``      the owner is gone (no such pid) or its pid was CONFIRMED reused
                  by a different process (OS start time differs from the one
                  recorded at insert). VERIFIED, so the row may be reconciled.
    ``unknown``   we could not establish either. Specifically:
                    - no owner recorded (a row written before the stamp existed,
                      or by a path that bypassed the mapper listener);
                    - the owner is on ANOTHER HOST, where a pid means nothing;
                    - the liveness inspection itself failed.

    ``unknown`` MUST NOT be treated as ``dead``. An unfamiliar host is not
    evidence that a worker died, and a missing stamp is not evidence of
    anything at all -- reconciling on those is how a live turn gets failed by a
    process that simply could not see who owned it. A row in this state is
    reported, not touched: no status change, and no release of its keyed
    request. The cost is that a genuine ghost whose owner cannot be established
    stays ``running``; that is the correct direction to be wrong in, and the
    report is what makes it visible to whoever can resolve it.

    A pid that is alive but whose recorded OS start time is unavailable is
    ``live``, not ``unknown``: liveness was established, and pid reuse is
    neither confirmed nor refuted. Reconciling there would be the harmful
    direction on a guess.
    """
    if not isinstance(metadata, dict):
        return "unknown", {"reason": "metadata is not a dict"}
    owner = metadata.get(OWNER_KEY)
    if not isinstance(owner, dict) or not owner.get("pid"):
        return "unknown", {"reason": "no owner recorded on this row"}

    detail: Dict[str, Any] = {"pid": owner.get("pid"), "host": owner.get("host"),
                              "token": owner.get("token")}
    try:
        pid = int(owner["pid"])
    except (TypeError, ValueError):
        return "unknown", {**detail, "reason": "owner pid is not an integer"}

    if owner.get("token") == PROCESS_TOKEN and pid == os.getpid():
        return "self", detail
    if owner.get("host") and owner["host"] != HOSTNAME:
        return "unknown", {**detail,
                           "reason": "owner is on another host; a pid there is "
                                     "not evidence of anything on this host"}

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead", {**detail, "reason": "no such process"}
    except PermissionError:
        # Alive, owned by another user. Still alive: do not touch its work.
        return "live", detail
    except OSError as exc:
        return "unknown", {**detail, "reason": f"liveness inspection failed: {exc}"}

    # A ZOMBIE is not a live owner. os.kill(pid, 0) succeeds for one -- the pid
    # entry survives until the parent reaps it -- so a killed-but-unreaped owner
    # was classified `live` and its execution stayed `running` FOREVER. Measured
    # on the finish-line F11 case (2026-09-29): the boot sweep reported "no
    # orphaned executions found" while the killed continuation's row sat
    # `running` with a verified-dead owner; running the same recovery function
    # by hand, after the harness had exited and reaped the child, recovered it
    # immediately (owner_liveness -> dead).
    #
    # A zombie has already exited: it holds no lock, runs no turn, and its work
    # is unrecoverable by definition. Treating it as `dead` therefore cannot
    # fail a RUNNING turn, which is the direction this function is careful
    # about -- so this narrows a false `live`, and leaves `live` (a real
    # process), `unknown` (cannot tell) and the pid-reuse check untouched.
    state = _process_state(pid)
    if state is not None:
        detail["os_process_state"] = state
    # psutil spells states out ("zombie"); /proc and ps use one letter ("Z").
    if state is not None and state.strip()[:1].upper() == "Z":
        return "dead", {**detail, "reason": "owner is a zombie (already exited, "
                                            "awaiting reaping by its parent)"}

    # NOTE: the stamp's "process_started_at" is an ISO WALL-CLOCK time
    # (datetime.now), not an OS process start time, so it must NOT be compared
    # against _os_process_start()'s "ps:..." string -- the formats differ and
    # every live owner would look dead. The comparable value is written by
    # record_os_start() under "os_process_start"; the legacy spelling is
    # accepted only in that same, comparable form.
    recorded = owner.get("os_process_start")
    if recorded:
        current = _os_process_start(pid)
        detail["os_process_start_recorded"] = recorded
        detail["os_process_start_now"] = current
        if current and current != recorded:
            return "dead", {**detail,
                            "reason": "pid is alive but was reused by a different "
                                      "process (OS start time differs)"}
        return "live", detail

    detail["os_process_start_recorded"] = None
    return "live", {**detail,
                    "caveat": "pid is alive; no OS start time was recorded, so pid "
                              "reuse can be neither confirmed nor excluded. Treated "
                              "as live because the harmful direction is failing a "
                              "running turn."}

def record_os_start(metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stamp the current OS start time into this process's owner block.

    Called once per process (from the model listener) so later sweeps can detect
    PID reuse instead of guessing.
    """
    meta = stamp_owner(metadata)
    owner = meta.get(OWNER_KEY)
    if isinstance(owner, dict) and owner.get("token") == PROCESS_TOKEN:
        start = _os_process_start(os.getpid())
        if start:
            owner["os_process_start"] = start
    return meta
