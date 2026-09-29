"""TEST-ONLY synchronization barrier: hold a worker between two real steps.

WHY
The acceptance lanes need to kill the serving process inside a window that is
too small to hit by polling. The measured instance (2026-09-28, background
continuation): the canvas audit row committed at ``10:12:53.334944`` and the
continuation's terminal record at ``10:12:53.354743`` -- a ~20 ms gap, so a
20 ms poll loop only ever saw both at once. Seizing SQLite's write lock after
the effect becomes visible is too late for the same reason: by the time a
reader can see the audit row, both commits have already happened.

So the window is made deterministic instead of raced for. A harness arms a
named stage; the worker signals arrival at that stage and blocks there until
the harness releases it. The kill can then be placed inside the window by
construction.

WHAT IT IS NOT
It is a pause and nothing else. It does not authorize, apply, verify,
persist, finalize, notify, or decide anything; it never opens the database;
it writes exactly two files of its own under the world's run directory. Both
steps on either side of a barrier are steps the product takes anyway, and a
stage is only ever placed where the step before it has already committed and
the step after it has not yet run. Consequently a barrier cannot make a failed
operation look applied, cannot skip a store write, and cannot skip a
verification: if the work before the barrier failed, the barrier is simply
reached later or not at all, with the same outcome it would have had.

CONFINEMENT (all of it is here, so a call site stays one line)
1. **Inert by default.** ``ARMED`` is one ``os.environ`` lookup evaluated at
   import. A process that did not ask for a barrier pays nothing: no import of
   this module, no thread, no timer, no file, no branch outcome change.
2. **Refuses outside an isolated acceptance world.** Arming is honoured only
   when EVERY database URL this process can be seen to have opened resolves to
   a path containing ``acceptance_worlds``. Set the variable in production and
   the barrier logs a loud refusal and continues WITHOUT it -- the product
   behaviour is unchanged, which is the entire point of refusing rather than
   raising.
3. **Optional narrowing.** ``ATOM_ACCEPTANCE_BARRIER_MATCH`` restricts the
   barrier to one session id. This can only make the barrier fire less often;
   it can never arm a stage that would otherwise stay inert.
4. **Bounded.** A release that never comes times out, loudly, and the work
   continues exactly as if no barrier existed. A test seam must not be able to
   wedge a worker forever.

MECHANISM (plain files plus polling; no new dependency, no socket, no signal)
* arrival: ``<dir>/barrier.<stage>.arrived.<pid>.json`` (and a convenience
  ``barrier.<stage>.arrived.json`` carrying the newest arrival),
* release: the harness creates ``<dir>/barrier.<stage>.release``,
* ``<dir>`` defaults to ``acceptance_barrier/`` beside the world's database,
  i.e. inside that world's own run directory, and can be moved with
  ``ATOM_ACCEPTANCE_BARRIER_DIR`` -- which is itself refused if it would move
  the files out of the world.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: The arming switch. Its VALUE selects the stage (or ``all``).
ENV_STAGE = "ATOM_ACCEPTANCE_BARRIER"
#: Optional narrowing: only pause for this session id. Narrows, never widens.
ENV_MATCH = "ATOM_ACCEPTANCE_BARRIER_MATCH"
#: Optional relocation of the barrier directory (still confined to the world).
ENV_DIR = "ATOM_ACCEPTANCE_BARRIER_DIR"
#: Hard bound on a single hold, so a missing release cannot wedge a worker.
ENV_TIMEOUT = "ATOM_ACCEPTANCE_BARRIER_TIMEOUT"

#: The path fragment that makes a database an isolated acceptance world. Same
#: test the lane probes apply before they will write to a world's database.
WORLD_MARKER = "acceptance_worlds"

DEFAULT_TIMEOUT_SECONDS = 120.0
POLL_SECONDS = 0.02

#: One ``os.environ`` lookup, evaluated once at import. The call sites guard
#: on this, so the default path is a global read and a branch.
ARMED: bool = bool(os.environ.get(ENV_STAGE))


def _sqlite_path(url: str) -> str:
    """The filesystem path of a ``sqlite:///...`` URL, or "" for anything
    else. A non-SQLite URL yields "" on purpose: a Postgres deployment is not
    an acceptance world, and guessing at a host string would be a way to arm
    the barrier against something that is not a disposable world copy."""
    if not url or not url.startswith("sqlite"):
        return ""
    _scheme, sep, rest = url.partition(":///")
    if not sep:
        return ""
    return rest.split("?", 1)[0].strip()


def _candidate_urls() -> List[str]:
    """Every database URL this process can be seen to have opened.

    ``DATABASE_URL`` is what the launcher set; ``core.database.DATABASE_URL``
    is what the engine was actually built from after ``TESTING=1`` /
    ``ATOM_MOCK_DATABASE`` rewriting. They can disagree, and the disagreement
    is exactly the condition under which writes land somewhere unexpected, so
    BOTH are checked and the barrier needs them to agree.
    """
    out: List[str] = []
    env_url = os.environ.get("DATABASE_URL") or ""
    if env_url.strip():
        out.append(env_url.strip())
    module = sys.modules.get("core.database")
    module_url = str(getattr(module, "DATABASE_URL", "") or "").strip() \
        if module is not None else ""
    if module_url and module_url not in out:
        out.append(module_url)
    return out


def resolve_barrier_dir() -> Optional[Path]:
    """The directory this process's barrier files live in, or None when the
    barrier is not allowed to arm here.

    Returns None (after a loud refusal) for: a non-world database, a
    ``DATABASE_URL`` the engine disagrees with, a missing database, or a
    requested directory outside the world.
    """
    urls = _candidate_urls()
    if not urls:
        logger.error(
            "ACCEPTANCE BARRIER REFUSED (%s=%r): no DATABASE_URL is visible in "
            "this process, so it cannot be shown to be an isolated acceptance "
            "world. Continuing WITHOUT the barrier.",
            ENV_STAGE, os.environ.get(ENV_STAGE))
        return None
    paths = []
    for url in urls:
        path = _sqlite_path(url)
        if not path or WORLD_MARKER not in path:
            logger.error(
                "ACCEPTANCE BARRIER REFUSED (%s=%r): database %r does not "
                "resolve inside %r. This is not an isolated acceptance world, "
                "and a barrier that could stop a real turn in production is "
                "not a test seam. Continuing WITHOUT the barrier.",
                ENV_STAGE, os.environ.get(ENV_STAGE), url, WORLD_MARKER)
            return None
        paths.append(os.path.normpath(path))

    requested = (os.environ.get(ENV_DIR) or "").strip()
    if requested:
        directory = Path(requested).expanduser()
        resolved = str(Path(os.path.abspath(str(directory))))
        if not any(resolved.startswith(p + os.sep) for p in paths):
            logger.error(
                "ACCEPTANCE BARRIER REFUSED (%s=%r): %s=%r is not inside the "
                "world's database directory %r, so the barrier files would "
                "land outside the disposable world. Continuing WITHOUT the "
                "barrier.", ENV_STAGE, os.environ.get(ENV_STAGE), ENV_DIR,
                requested, paths[0])
            return None
        return directory
    return Path(paths[0]).parent / "acceptance_barrier"


def stage_armed(stage: str) -> bool:
    """Is ``stage`` the armed one? Exact match, or ``all``/``*``/``1``."""
    selected = (os.environ.get(ENV_STAGE) or "").strip()
    if not selected:
        return False
    return selected in {"all", "*", "1", "true"} or selected == stage


def matches_turn(context: Optional[Dict[str, Any]]) -> bool:
    """Apply the optional session narrowing. Absent match => no narrowing."""
    wanted = (os.environ.get(ENV_MATCH) or "").strip()
    if not wanted:
        return True
    return str((context or {}).get("session_id") or "") == wanted


def _timeout_seconds() -> float:
    """The hold's bound. A non-positive or unparsable value falls back to the
    default rather than to "no bound": a test seam must not be able to disable
    its own timeout. Sub-second values ARE honoured, so a test can ask for a
    short hold."""
    raw = os.environ.get(ENV_TIMEOUT)
    if raw is None or not str(raw).strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return max(0.05, value)


def arrived_paths(directory: Path, stage: str) -> List[Path]:
    """Every arrival marker for ``stage`` (one per blocked process)."""
    return sorted(directory.glob(f"barrier.{stage}.arrived.*.json"))


def release_path(directory: Path, stage: str) -> Path:
    return directory / f"barrier.{stage}.release"


def _write_arrival(directory: Path, stage: str,
                   context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "stage": stage,
        "pid": os.getpid(),
        "arrived_at": datetime.now(timezone.utc).isoformat(),
        "wall_clock": time.time(),
        "context": dict(context or {}),
    }
    blob = json.dumps(payload, indent=1, default=str)
    (directory / f"barrier.{stage}.arrived.{os.getpid()}.json").write_text(blob)
    # Convenience pointer: the newest arrival, so a harness that knows nothing
    # about pids can still watch one file.
    (directory / f"barrier.{stage}.arrived.json").write_text(blob)
    with (directory / f"barrier.{stage}.events.log").open("a") as fh:
        fh.write(f"arrived {stage} pid={os.getpid()} "
                 f"at={payload['arrived_at']} "
                 f"context={json.dumps(payload['context'], default=str)[:400]}\n")
    return payload


def _note_release(directory: Path, stage: str, waited: float,
                  context: Optional[Dict[str, Any]]) -> None:
    with (directory / f"barrier.{stage}.events.log").open("a") as fh:
        fh.write(f"released {stage} pid={os.getpid()} after={waited:.3f}s "
                 f"context={json.dumps(context or {}, default=str)[:400]}\n")


def block(stage: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Synchronous hold. Returns True if it actually blocked.

    The event loop must not be blocked with this -- use :func:`await_barrier`
    from async code. Provided for synchronous call sites and for tests.
    """
    if not ARMED or not stage_armed(stage) or not matches_turn(context):
        return False
    directory = resolve_barrier_dir()
    if directory is None:
        return False
    payload = _write_arrival(directory, stage, context)
    logger.warning(
        "ACCEPTANCE BARRIER HOLDING: stage=%s pid=%s dir=%s — waiting for %s",
        stage, payload["pid"], directory, release_path(directory, stage).name)
    started = time.monotonic()
    released = release_path(directory, stage)
    budget = _timeout_seconds()
    try:
        while not released.exists():
            if time.monotonic() - started > budget:
                logger.error(
                    "ACCEPTANCE BARRIER TIMED OUT after %.0fs: stage=%s pid=%s "
                    "no %s was ever created. Continuing WITHOUT it; the work "
                    "after the barrier runs exactly as it would have with no "
                    "barrier at all.", time.monotonic() - started, stage,
                    os.getpid(), released.name)
                _note_release(directory, stage, time.monotonic() - started,
                              context)
                return False
            time.sleep(POLL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — a test seam never breaks the work
        logger.error(
            "ACCEPTANCE BARRIER ERRORED (%s: %s); continuing WITHOUT it",
            type(exc).__name__, exc)
        return False
    waited = time.monotonic() - started
    _note_release(directory, stage, waited, context)
    logger.warning(
        "ACCEPTANCE BARRIER RELEASED: stage=%s pid=%s after %.3fs",
        stage, os.getpid(), waited)
    return True


async def await_barrier(stage: str,
                        context: Optional[Dict[str, Any]] = None) -> bool:
    """Async hold that yields to the event loop while it waits.

    The process stays responsive and health-checkable during the hold, which
    is what lets a harness confirm the worker is ALIVE and parked rather than
    merely slow. Returns True if it actually blocked.
    """
    if not ARMED or not stage_armed(stage) or not matches_turn(context):
        return False
    directory = resolve_barrier_dir()
    if directory is None:
        return False
    _write_arrival(directory, stage, context)
    released = release_path(directory, stage)
    logger.warning(
        "ACCEPTANCE BARRIER HOLDING: stage=%s pid=%s dir=%s — waiting for %s",
        stage, os.getpid(), directory, released.name)
    started = time.monotonic()
    budget = _timeout_seconds()
    try:
        while not released.exists():
            if time.monotonic() - started > budget:
                logger.error(
                    "ACCEPTANCE BARRIER TIMED OUT after %.0fs: stage=%s pid=%s "
                    "no %s was ever created. Continuing WITHOUT it; the work "
                    "after the barrier runs exactly as it would have with no "
                    "barrier at all.", time.monotonic() - started, stage,
                    os.getpid(), released.name)
                _note_release(directory, stage, time.monotonic() - started,
                              context)
                return False
            await asyncio.sleep(POLL_SECONDS)
    except asyncio.CancelledError:
        logger.warning(
            "ACCEPTANCE BARRIER CANCELLED: stage=%s pid=%s after %.3fs; the "
            "caller's own cancellation is honoured and nothing is fabricated",
            stage, os.getpid(), time.monotonic() - started)
        raise
    except Exception as exc:  # noqa: BLE001 — a test seam never breaks the work
        logger.error(
            "ACCEPTANCE BARRIER ERRORED (%s: %s); continuing WITHOUT it",
            type(exc).__name__, exc)
        return False
    waited = time.monotonic() - started
    _note_release(directory, stage, waited, context)
    logger.warning(
        "ACCEPTANCE BARRIER RELEASED: stage=%s pid=%s after %.3fs",
        stage, os.getpid(), waited)
    return True


#: The stage names the product call sites use. Named here so a harness and a
#: call site cannot drift apart on a string literal.
STAGE_CONTINUATION_AFTER_EFFECT = "continuation_after_effect"
#: Inside ``_apply_effects``, AFTER the terminal-delivery claim is taken and
#: BEFORE the durable terminal message is written. That window is microseconds
#: wide and cannot be hit by polling, and it is the one state recovery exists
#: for: the claim says a delivery is owned, and nothing was written. Same
#: confinement as every other stage -- inert unless armed, refused outside an
#: isolated acceptance world, bounded, and a pause that changes no outcome.
STAGE_CONTINUATION_AFTER_CLAIM = "continuation_after_claim"
STAGE_CHAT_TURN_AFTER_CLAIM = "chat_turn_after_claim"
STAGE_RECOVERY_DELIVERY_HELD = "recovery_delivery_held"
