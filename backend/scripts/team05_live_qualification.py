"""TEAM-05 bounded, opt-in LIVE qualification for the org-politics scheduler.

What this proves (and only this)
--------------------------------
The nightly org-politics worker is entered through its REAL scheduler seam::

    ensure_automation_task()            (real asyncio task registration)
      -> org_politics_automation_loop() (real 30 s floor tick, measured)
        -> run_auto_certification_async() (real worker thread + pass gate)
          -> run_auto_certification()   (real owned-session pass)
            -> certify() -> alignment_verdict(chat_fn=None)
              -> _default_chat_fn()     (real BYOKHandler)
                -> generate_response()  (real ranking / policy / ledger)
                  -> real OpenAI-compatible HTTP call to LOCAL Ollama

Only the *metadata* boundaries are supplied by the driver:

* a synthetic pricing-cache entry for the Ollama model (ranking needs one;
  transport is NOT doubled);
* a disposable SQLite file, verified empty/consistent after schema creation
  and before the first row write;
* a disposable BYOK key store / catalog / pair-memo / drift-state directory.

Isolation is proven at the FILESYSTEM and SOCKET boundary, not by intent:

* before ``create_all`` the driver compares ``database.engine.url``
  (backend name + resolved database path) and the ``SessionLocal`` bind
  against the exact scratch file; a non-scratch SQLite target is refused
  before a connection exists;
* every ``sqlite3.connect`` is intercepted BEFORE the file is opened and a
  path outside the scratch workdir raises (the live/dev DB can never be
  opened, even accidentally);
* ambient ``TESTING``/``ATOM_MOCK_DATABASE`` overrides are cleared so
  ``core.database`` cannot silently retarget the run;
* uppercase AND lowercase proxy variables are cleared, an explicit
  empty ``ProxyHandler`` defeats system proxies, and a socket-level guard
  refuses any non-loopback ``connect``/``connect_ex``/``create_connection``
  (the response peer address is also checked);
* the copied-database approval control is part of the verdict: a regression
  in ``apply_pending_decision`` fails the qualification instead of only
  appearing in evidence;
* every protected live-tree file (BYOK config / keys / encryption key,
  catalogs, caches, drift state, dev secret, the live SQLite DBs, under BOTH
  ``backend/data`` and a root-anchored ``data/``) is stat-snapshotted AND
  write-guarded before the first import. A post-run stat can only report
  damage; the guard refuses the write at the syscall boundary first;
* the scratch paths in ``isolation`` are proven against the PRODUCTION
  modules' *resolved* constants (BYOK env is read at import time; pricing and
  drift state are redirected by the seams). A declared path is not an
  observed one;
* a change to any protected file is a HARD failure (exit 1) - never a
  footnote and never an "unknown" check.

Everything that decides behaviour is the production code path.  Evidence is
recorded, never assumed: the driver does not assert a "green" sweep, a fixed
served model, or three approval rows as a precondition.  A live 8B judge may
legitimately emit unparseable JSON.  That outcome is a *negative* result
(exit 2), not a fake pass and not a failure.

What this does NOT prove
------------------------
* app-startup wiring (the driver calls ``ensure_automation_task`` itself);
* 24-hour cadence, drift, missed ticks or restart-resume (module state);
* PostgreSQL, multi-worker or distributed-lock behaviour (SQLite only);
* notification DELIVERY (the scratch DB has no admin recipient; only the
  consent intent is recorded);
* provider-policy denial as a second live leg: the accepted offline control
  (``tests/test_org_politics_scheduled_worker_offline.py``) owns the
  denial twin; this driver instead aborts before dispatch if any non-Ollama
  client or policy appears;
* that the local model produces a green sweep - that is observed, not forced.

Opt-in
------
Nothing runs unless ``--run-live`` is passed.  Without it the script prints
the plan, the evidence boundaries, and the exact replay command, then exits 3.
It also refuses to run under pytest or CI.

Audit corrections baked into this driver
----------------------------------------
The source audit (``/private/tmp/atom-team05-live-audit.log``) was accurate
about the central seam (``_initialize_clients`` only builds the Ollama client
when ``"pytest" not in sys.modules``), but four of its assumptions do not
survive inspection and are NOT relied on here:

1. Unsetting ``*_API_KEY`` is not enough to guarantee "Ollama only".  BYOK
   credentials are loaded from ``backend/data/byok_keys.json`` (file store,
   independent of the DB).  This driver redirects ``BYOK_*`` to scratch files,
   proves the production modules' resolved constants actually point there
   (``verify_scratch_path_resolution``), write-guards the live tree, and
   aborts if any non-Ollama client is nevertheless constructed.  The proof
   matters: constructing ``BYOKManager`` persists its defaults, and a bare
   pytest collection in the same checkout does that before conftest can
   redirect it (``backend/tests/conftest.py`` now isolates at import time).
2. ``_default_chat_fn`` passes ``timeout=120.0`` to ``_run_coroutine_sync``,
   but that branch ignores the timeout whenever no loop is running - which is
   exactly the worker-thread case.  The real cap is the SDK's
   ``OLLAMA_REQUEST_TIMEOUT`` (default 600 s), so this driver sets it
   explicitly and pre-warms the model.
3. ``handler._last_used_model`` is the *requested* model (set after an
   accepted response), not a server-reported identity.  Served identity is
   taken from the provider's own response echo
   (``model_provenance.set_echoed_response_model``) and cross-checked with
   Ollama's ``/api/ps`` runtime state; the requested model alone never
   qualifies a call.
4. Resetting ``_ollama_probe_cache`` is redundant: it is per-instance and
   ``_default_chat_fn`` constructs a fresh handler per pass.  The class-level
   ``_OLLAMA_DOWN_MEMO`` is process-wide and IS cleared.

Exit codes
----------
0  qualified        scheduler + local dispatch + durable pending approval
1  failed           a hard evidence check failed (details in the report)
2  negative         the pass ran, but the sweep was not certifiable
                    (incomplete/red evidence) and correctly filed nothing
3  not opted in     no run happened
4  precondition     Ollama/model/environment precondition not met
5  safety abort     a non-local provider/credential appeared; nothing shipped
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import platform
import secrets
import shlex
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: The scheduler evaluates ``max(interval_min, 0.5) * 60``; 0.5 is the floor.
MIN_INTERVAL_MIN = 0.5
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434/v1"

EXIT_QUALIFIED = 0
EXIT_FAILED = 1
EXIT_NEGATIVE = 2
EXIT_NOT_OPTED_IN = 3
EXIT_PRECONDITION = 4
EXIT_SAFETY_ABORT = 5

#: Env vars whose presence must never leak a provider into this process.
_API_KEY_SUFFIX = "_API_KEY"

#: Kill switches that would bypass the DB-backed approval resolver.
FLAG_ENV_VARS = (
    "ATOM_SKILL_SCOPED_TRUST_ENABLED",
    "ATOM_ALLOCATOR_INTEGRITY_ENABLED",
    "ATOM_ORG_PRIVILEGES_ENABLED",
)

#: Proxy variables honoured by urllib, httpx, the OpenAI SDK and requests.
#: BOTH cases matter: ``urllib`` reads lowercase first, the SDKs upper first,
#: and an inherited uppercase-only proxy silently routes "local" traffic out.
PROXY_ENV_VARS = (
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy",
    "NO_PROXY", "no_proxy",
    "FTP_PROXY", "ftp_proxy",
    "SOCKS_PROXY", "socks_proxy",
)

#: Ambient test toggles that silently re-point ``core.database.get_database_url``
#: (``TESTING=1`` -> backend/test_integration.db, ATOM_MOCK_DATABASE=true ->
#: ``:memory:``).  The repo's own guidance tells agents to set TESTING=1, so
#: inheriting it into a live qualification is a plausible accident.
DB_ENV_OVERRIDES = ("TESTING", "ATOM_MOCK_DATABASE")

#: Observed loopback peers for every local HTTP call (evidence, not intent).
_LOOPBACK_PEERS: List[Dict[str, Any]] = []

#: Files under backend/data this process must not touch.  The live SQLite DB
#: is included explicitly as well.
_PROTECTED_DATA_FILES = (
    "atom.db",
    "byok_config.json",
    "byok_keys.json",
    "byok_encryption_key",
    "provider_model_catalog.json",
    "ai_pricing_cache.json",
    "model_resolution_state.json",
    "llm_pair_memos.json",
    ".dev_secret_key",
)

#: Sentinel for "the module exists but does not expose this attribute".
_MISSING = object()

#: Production module-level path constants that must resolve into the scratch
#: workdir.  BYOK paths come from the ``BYOK_*`` env vars (read at import
#: time); pricing/drift are redirected by the seams after import.  The driver
#: checks the module state, not the declared strings, because a declaration
#: in evidence has already been wrong once (see ``_install_isolation_env``).
_SCRATCH_PATH_CONSTANTS: Tuple[Tuple[str, str, str], ...] = (
    ("core.byok_endpoints", "BYOK_CONFIG_FILE", "byok_config"),
    ("core.byok_endpoints", "BYOK_KEYS_FILE", "byok_keys"),
    ("core.byok_endpoints", "BYOK_ENC_KEY_FILE", "byok_enc_key"),
    # The admin manager is a second writer with its own import-time constants.
    # It is usually not imported by this driver; when a tool path imports it,
    # its resolution is proven too.
    ("api.byok_routes", "BYOK_CONFIG_FILE", "byok_config"),
    ("api.byok_routes", "BYOK_KEYS_FILE", "byok_keys"),
    ("api.byok_routes", "BYOK_ENC_KEY_FILE", "byok_enc_key"),
    # CWD-relative default ("./data/..."): honest only while BYOK_ENC_KEY_FILE
    # is set. Proving the constant is how that assumption is tested.
    ("core.privsec.token_encryption", "BYOK_ENC_KEY_FILE", "byok_enc_key"),
    ("core.dynamic_pricing_fetcher", "PRICING_CACHE_PATH", "pricing"),
    ("core.llm.model_provenance", "_DEFAULT_STATE_PATH", "drift_state"),
    ("core.llm.byok_handler", "_pair_memo_path", "pair_memos"),
)

_SCHEDULER_TRACE_ORDER = (
    "ensure_automation_task",
    "org_politics_automation_loop",
    "run_auto_certification_async",
    "_run_auto_certification_guarded",
    "run_auto_certification",
    "certify",
    "alignment_verdict",
    "_default_chat_fn",
)

_EXPECTED_TABLES = (
    "tenants",
    "workspaces",
    "agent_org_events",
    "org_politics_actions",
)


class FreshnessError(RuntimeError):
    """The scratch SQLite file was not exactly fresh before the first write."""


class PreconditionError(RuntimeError):
    """A bounded-live precondition was not met."""


class SafetyAbort(RuntimeError):
    """A non-local provider or credential appeared; dispatch must not happen."""


class NonScratchSqliteOpen(SafetyAbort):
    """A SQLite file outside the scratch work directory was about to open."""


class NonLoopbackNetwork(SafetyAbort):
    """A non-loopback network connection or peer was attempted."""


class ProtectedPathWrite(SafetyAbort):
    """A write to the live tree's protected files was attempted.

    Raised BEFORE the file is opened/replaced/removed, so the protected file is
    never partially written. The attempt is recorded and reported as a hard
    qualification failure even when a caller swallows the exception.
    """


# ---------------------------------------------------------------------------
# Pure helpers (safe for --self-test: no core imports, no network, no writes)
# ---------------------------------------------------------------------------


def is_loopback_host(host: Optional[str]) -> bool:
    """True only for a host name/literal that denotes this machine's loopback.

    Shared by URL validation, the connection guard and the response-peer
    check, so all three agree on what "local" means.  ``127.0.0.0/8`` and
    ``::1`` are loopback by definition; IPv4-mapped IPv6 loopback counts too.
    """
    text = str(host or "").strip().lower()
    if not text:
        return False
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if text == "localhost":
        return True
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped is not None and mapped.is_loopback)


def is_loopback_url(url: str) -> bool:
    """True only for an http(s) URL whose host is this machine's loopback."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    return is_loopback_host(parsed.hostname)


def model_aliases(name: Optional[str]) -> set:
    """Identifier forms that denote the same local model.

    Ollama advertises ``llama3.1:8b`` while a probe may report the base
    ``llama3.1``; both forms are aliases of the same pulled model.  Vendor
    path prefixes are dropped (Ollama does not use them, but a caller may).
    """
    if not name:
        return set()
    text = str(name).strip().lower()
    if not text:
        return set()
    text = text.split("/", 1)[-1]
    forms = {text}
    if ":" in text:
        forms.add(text.split(":", 1)[0])
    return forms


def _db_stats(path: Path) -> Optional[Dict[str, Any]]:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "inode": int(getattr(stat, "st_ino", 0)),
    }


def file_fingerprint(path: Path) -> Dict[str, Any]:
    """Observed identity of a file (sha256 + stat), never a desired value."""
    path = Path(path)
    stat = path.stat()
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _sqlite_target_text(database: Any) -> str:
    """Best-effort path/URI text for a ``sqlite3.connect`` argument."""
    try:
        text = os.fsdecode(os.fspath(database))
    except TypeError:
        text = str(database)
    return text


def _sqlite_target_path(database: Any) -> Optional[str]:
    """Resolved file path for a SQLite open, or None for in-memory targets."""
    text = _sqlite_target_text(database)
    if text in ("", ":memory:"):
        return None
    if text.startswith("file:"):
        spec = text[len("file:"):]
        if "mode=memory" in spec:
            return None
        text = spec.split("?", 1)[0]
        if text in ("", ":memory:"):
            return None
    return os.path.realpath(text)


def sqlite_target_allowed(
    database: Any,
    allowed_root: Optional[Path],
) -> bool:
    """Pure gate for the pre-connect SQLite interceptor.

    In-memory databases are allowed (they cannot be the live file); every
    file-backed open must resolve INSIDE ``allowed_root``.
    """
    resolved = _sqlite_target_path(database)
    if resolved is None:
        return True
    if allowed_root is None:
        return True
    real_root = os.path.realpath(str(allowed_root))
    return resolved == real_root or resolved.startswith(real_root + os.sep)


def scratch_sqlite_mismatch(
    backend_name: Optional[str],
    database: Optional[str],
    expected_path: Path,
    workdir: Path,
) -> Optional[str]:
    """Return a named reason when a SQLAlchemy URL is NOT the scratch file.

    This is the pure half of the engine-destination proof: the *backend*
    must be sqlite and the *resolved database* must be exactly the fresh
    scratch file inside the scratch workdir.  Anything else (PostgreSQL,
    ``:memory:``, the live dev DB, a relative path) is refused before a
    connection is made.
    """
    if backend_name != "sqlite":
        return f"backend is {backend_name!r}, expected 'sqlite'"
    if not database:
        return "SQLAlchemy URL has no database"
    text = str(database)
    if text in ("", ":memory:") or (text.startswith("file:")
                                   and "mode=memory" in text):
        return f"in-memory database is not a durable scratch file: {text!r}"
    real = os.path.realpath(text)
    real_expected = os.path.realpath(str(expected_path))
    real_workdir = os.path.realpath(str(workdir))
    if real != real_expected:
        return f"database resolves to {real!r}, expected exactly {real_expected!r}"
    if not (real == real_workdir or real.startswith(real_workdir + os.sep)):
        return (
            f"database {real!r} is outside the scratch work directory "
            f"{real_workdir!r}")
    return None


def verify_pristine_sqlite(
    path: Path,
    expected_tables: Sequence[str] = (),
) -> Dict[str, Any]:
    """Prove ``path`` is a new, consistent, completely EMPTY SQLite database.

    Runs after schema creation and before any qualification row write.
    Raises ``FreshnessError`` with the observed state on any deviation - a
    stale/shared file is never accepted.
    """
    path = Path(path)
    if not path.is_file():
        raise FreshnessError(f"scratch DB does not exist: {path}")
    try:
        con = sqlite3.connect(str(path))
    except sqlite3.Error as exc:
        raise FreshnessError(f"cannot open scratch DB: {exc}") from exc
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        integrity = str(row[0]) if row else ""
        if integrity.lower() != "ok":
            raise FreshnessError(f"integrity_check={integrity!r}")
        tables = [
            str(r[0]) for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        ]
        missing = sorted(set(expected_tables) - set(tables))
        if missing:
            raise FreshnessError(f"missing expected tables: {missing}")
        counts = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            counts[table] = int(
                con.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
        non_empty = {k: v for k, v in counts.items() if v}
        if non_empty:
            raise FreshnessError(
                f"scratch DB is not fresh (non-empty tables): {non_empty}")
        return {
            "path": str(path),
            "integrity_check": integrity,
            "table_count": len(tables),
            "total_rows": 0,
            "tables": tables,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": int(path.stat().st_size),
        }
    finally:
        con.close()


def classify_observations(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the verdict from OBSERVATIONS - never from a desired outcome.

    Returns ``{"verdict", "exit_code", "checks", "summary"}``.  Checks are
    three-state: pass / fail / unknown.  A hard failure wins; otherwise a
    certifiable green sweep with exactly the expected pending rows is
    ``qualified``; a completed but non-certifiable sweep is ``negative``.
    """
    checks: List[Dict[str, Any]] = []

    def add(name: str, state: str, detail: Any = "") -> None:
        if state not in ("pass", "fail", "unknown"):
            raise ValueError(f"bad check state: {state}")
        checks.append({"name": name, "state": state, "detail": detail})

    def flag(name: str, value: Any, detail: Any = "") -> None:
        add(name, "pass" if bool(value) else "fail", detail)

    scheduler = obs.get("scheduler") or {}
    dispatch = obs.get("dispatch") or {}
    sweep = obs.get("sweep") or {}
    findings = obs.get("findings") or {}

    # ---- scheduler entry (real task, real tick, real worker thread) ----
    flag("scheduler.task_registered",
         scheduler.get("registered"), scheduler.get("registered_detail"))
    flag("scheduler.registered_once",
         scheduler.get("registered_once"), scheduler.get("registration_detail"))

    trace = list(scheduler.get("trace") or [])
    names = [str(entry.get("name")) for entry in trace
             if isinstance(entry, dict)]
    cursor = -1
    order_ok = True
    for wanted in _SCHEDULER_TRACE_ORDER:
        try:
            cursor = names.index(wanted, cursor + 1)
        except ValueError:
            order_ok = False
            break
    flag("scheduler.real_entry_chain", order_ok)
    if not order_ok:
        add("scheduler.trace_observed", "unknown", names)

    flag("scheduler.pass_gate_held",
         scheduler.get("pass_gate_locked"), scheduler.get("pass_gate_detail"))
    flag("scheduler.notification_loop_preserved",
         scheduler.get("notification_loop_bound"))
    flag("scheduler.worker_thread_used",
         scheduler.get("certify_on_worker_thread"),
         {"certify_thread": scheduler.get("certify_thread"),
          "main_thread": scheduler.get("main_thread")})

    slept = scheduler.get("sleep_seconds")
    if isinstance(slept, (int, float)):
        add("scheduler.real_floor_tick",
            "pass" if 28.0 <= float(slept) <= 120.0 else "fail",
            {"sleep_seconds": slept, "expected_floor_seconds": 30.0})
    else:
        add("scheduler.real_floor_tick", "unknown", slept)

    flag("scheduler.pass_completed",
         scheduler.get("pass_completed"), scheduler.get("pass_detail"))

    # ---- local-only dispatch ----
    flag("dispatch.no_non_local_client",
         not dispatch.get("non_local_clients"),
         dispatch.get("non_local_clients"))
    flag("dispatch.scheduler_handler_present",
         dispatch.get("scheduler_handler_count") == 1,
         {"handlers": dispatch.get("handler_count"),
          "scheduler_handlers": dispatch.get("scheduler_handler_count")})
    flag("dispatch.handler_clients_ollama_only",
         list(dispatch.get("handler_clients") or []) == ["ollama"]
         and not (list(dispatch.get("handler_async_clients") or [])
                  and set(dispatch.get("handler_async_clients") or [])
                  - {"ollama"}),
         {"sync": dispatch.get("handler_clients"),
          "async": dispatch.get("handler_async_clients")})
    flag("dispatch.policy_selected_ollama",
         dispatch.get("policy_mode") == "selected"
         and list(dispatch.get("policy_allowed") or []) == ["ollama"],
         {"mode": dispatch.get("policy_mode"),
          "allowed": dispatch.get("policy_allowed")})
    flag("dispatch.real_chat_fn_used",
         bool(dispatch.get("alignment_chat_fn_entries"))
         and all(v is True for v in
                 dispatch.get("alignment_chat_fn_entries") or []),
         dispatch.get("alignment_chat_fn_entries"))
    flag("dispatch.policy_denies_cloud",
         dispatch.get("policy_denies_cloud") is True,
         dispatch.get("policy_denies_cloud"))
    flag("dispatch.served_provider_is_ollama",
         bool(dispatch.get("served_routes"))
         and all(r.get("provider") == "ollama"
                 for r in dispatch.get("served_routes") or []),
         dispatch.get("served_routes"))

    attempts = dispatch.get("attempts") or []
    expected = dispatch.get("expected_generations")
    if isinstance(expected, int) and expected > 0:
        bounded = 0 < len(attempts) <= expected
        add("dispatch.generation_budget_bounded",
            "pass" if bounded else "fail",
            {"attempts": len(attempts), "expected": expected})
    else:
        add("dispatch.generation_budget_bounded", "unknown", expected)

    accepted = len(dispatch.get("served_routes") or [])
    attempts_all = dispatch.get("attempts") or []
    observed_providers = {
        a.get("last_used_provider") for a in attempts_all
        if a.get("last_used_provider")
    }
    flag("dispatch.attempted_provider_ollama",
         bool(observed_providers) and observed_providers <= {"ollama"},
         sorted(observed_providers))
    temperatures = [
        a.get("temperature") for a in attempts_all
        if a.get("temperature") is not None
    ]
    if temperatures:
        flag("dispatch.temperature_zero",
             all(float(t) == 0.0 for t in temperatures),
             sorted(set(temperatures)))
    else:
        add("dispatch.temperature_zero", "unknown", "no recorded attempt")

    echoes = [e for e in (dispatch.get("echoed_models") or []) if e]
    if accepted == 0:
        add("dispatch.served_model_echo", "fail", "no accepted route")
    elif echoes:
        aliases_ok = True
        for route in dispatch.get("served_routes") or []:
            route_alias = model_aliases(route.get("model"))
            if not any(route_alias & model_aliases(e) for e in echoes):
                aliases_ok = False
                break
        add("dispatch.served_model_echo",
            "pass" if aliases_ok and len(echoes) >= accepted else "fail",
            {"accepted": accepted, "echoes": echoes[:6],
             "echo_count": len(echoes)})
    else:
        add("dispatch.served_model_echo", "fail",
            "accepted calls carried no provider echo")

    pulled = set()
    for name in dispatch.get("pulled_models") or []:
        pulled |= model_aliases(name)
    routed = set()
    for route in dispatch.get("served_routes") or []:
        routed |= model_aliases(route.get("model"))
    if pulled and routed:
        flag("dispatch.model_is_pulled", bool(pulled & routed),
             {"routed": sorted(routed), "pulled": sorted(pulled)})
    else:
        add("dispatch.model_is_pulled", "unknown",
            {"routed": sorted(routed), "pulled": sorted(pulled)})

    running = dispatch.get("running_models") or []
    if running:
        running_alias = set()
        for name in running:
            running_alias |= model_aliases(name)
        flag("dispatch.model_loaded_after_pass",
             bool(running_alias & routed),
             {"running": running, "routed": sorted(routed)})
    else:
        add("dispatch.model_loaded_after_pass", "unknown", "/api/ps empty")

    # ---- sweep evidence (observed, not desired) ----
    flag("sweep.ran", sweep.get("ran") is True, sweep.get("skipped_reason"))
    flag("scheduler.last_run_sweep_ran",
         scheduler.get("last_run_sweep_ran"),
         scheduler.get("last_run_keys"))
    evidence_complete = sweep.get("evidence_complete") is True
    green = sweep.get("green") is True
    add("sweep.evidence_complete",
        "pass" if evidence_complete else "unknown",
        {"green": green, "max_gap": sweep.get("max_gap"),
         "invalid_judgments": sweep.get("invalid_judgments")})
    if evidence_complete and green:
        flag("sweep.scores_complete",
             sweep.get("score_count") == sweep.get("expected_score_count"),
             {"scores": sweep.get("score_count"),
              "expected": sweep.get("expected_score_count")})
    else:
        add("sweep.scores_complete", "unknown",
            {"scores": sweep.get("score_count"),
             "expected": sweep.get("expected_score_count")})

    # ---- durable findings / approval preservation ----
    rows = findings.get("rows") or []
    row_keys = sorted(str(r.get("flag_key")) for r in rows)
    row_states = sorted({str(r.get("state")) for r in rows})
    flag_values = findings.get("flag_values") or {}

    if evidence_complete and green:
        expected_keys = sorted(findings.get("expected_flag_keys") or [])
        add("findings.pending_approval_rows",
            "pass" if row_keys == expected_keys else "fail",
            {"rows": row_keys, "expected": expected_keys})
        flag("findings.all_pending_state",
             bool(rows) and set(row_states) == {"approval"}, row_states)
        flag("findings.verdicts_enable",
             bool(rows) and all(r.get("verdict") == "enable" for r in rows))
        flag("findings.modes_approve",
             bool(rows) and all(r.get("mode") == "approve" for r in rows))
        flag("findings.decided_at_null",
             bool(rows) and all(r.get("decided_at") is None for r in rows))
        flag("findings.flags_still_off",
             bool(flag_values)
             and not any(bool(v) for v in flag_values.values()),
             flag_values)
        flag("findings.pending_view_matches",
             findings.get("pending_view_count") == len(rows),
             {"pending_view": findings.get("pending_view_count"),
              "rows": len(rows)})
        notifications = set(findings.get("notifications") or [])
        flag("findings.consent_requested_not_assumed",
             notifications == {"approval_needed"}, sorted(notifications))
    elif sweep.get("ran") is True:
        # Non-certifiable evidence MUST NOT create consent rows or notifications.
        flag("findings.no_rows_on_incomplete_evidence", rows == [], row_keys)
        flag("findings.no_consent_on_incomplete_evidence",
             not (findings.get("notifications") or []),
             findings.get("notifications"))
        flag("findings.flags_still_off",
             not flag_values or not any(bool(v) for v in flag_values.values()),
             flag_values)
    else:
        add("findings.pending_approval_rows", "unknown",
            "sweep did not run")

    # ---- isolation ----
    isolation = obs.get("isolation") or {}
    flag("isolation.exact_scratch_db", isolation.get("exact_scratch_db"),
         {"db_path": isolation.get("db_path"),
          "destination": isolation.get("database_destination")})
    flag("isolation.live_db_not_opened",
         isolation.get("live_db_not_opened"),
         isolation.get("opened_live_paths"))
    rejected = isolation.get("sqlite_rejected") or []
    flag("isolation.no_non_scratch_sqlite_open", not rejected, rejected)
    # ANY change to a live-tree protected file is a hard failure. It is not a
    # footnote and not "unknown": the run is not qualified, whatever the sweep
    # said, and the changed paths are the evidence.
    flag("isolation.protected_files_unchanged",
         not isolation.get("protected_changes"),
         isolation.get("protected_changes") or [])

    resolution = isolation.get("path_resolution") or {}
    if resolution and resolution.get("ok") is True:
        flag("isolation.scratch_paths_resolved", True,
             {"mismatches": [],
              "not_loaded": resolution.get("not_loaded") or []})
    elif resolution and resolution.get("ok") is False:
        flag("isolation.scratch_paths_resolved", False,
             {"mismatches": resolution.get("mismatches") or [],
              "not_loaded": resolution.get("not_loaded") or []})
    else:
        add("isolation.scratch_paths_resolved", "unknown",
            "no scratch path-resolution proof was recorded")

    refusal_state = isolation.get("protected_write_refusals")
    if refusal_state is None:
        add("isolation.no_protected_write_attempt", "unknown",
            "protected-path write guard was not reported")
    else:
        refused = (refusal_state.get("refused")
                   if isinstance(refusal_state, dict) else refusal_state)
        flag("isolation.no_protected_write_attempt", not (refused or []),
             refused or [])
    flag("isolation.fresh_before_seed", isolation.get("fresh_before_seed"),
         isolation.get("fresh_before_detail"))
    proxy_left = isolation.get("proxy_env_remaining") or {}
    flag("isolation.proxy_env_cleared", not proxy_left, proxy_left)
    network = isolation.get("network") or {}
    blocked_network = list(network.get("blocked") or [])
    flag("isolation.loopback_only_network",
         network.get("guard_installed") is True and not blocked_network,
         {"guard_installed": network.get("guard_installed"),
          "blocked": blocked_network,
          "peers": network.get("peers")})

    # ---- copied-database approval control (part of the verdict) ----
    control = obs.get("approval_control") or {}
    control_after = control.get("flag_values_after_approve") or {}
    control_states = control.get("states_after_approve") or {}
    approved = control.get("approved_flag")
    decision_applied = bool(control.get("decision_applied"))
    flag_flipped_only = bool(approved) and control_after.get(approved) is True \
        and all(value is False for key, value in control_after.items()
                if key != approved)
    states_settled = bool(approved) and bool(control_states) \
        and control_states.get(approved) == "applied" \
        and sum(1 for state in control_states.values()
                if state == "approval") == max(0, len(control_states) - 1)
    if evidence_complete and green:
        # A green, certifiable sweep MUST be matched by a working decision
        # write-back; a regression there is a failure, not a footnote.
        flag("approval_control.ran", control.get("ran") is True,
             control.get("error") or control.get("skip_reason"))
        flag("approval_control.decision_applied", decision_applied,
             control.get("decision"))
        flag("approval_control.flag_flipped_only", flag_flipped_only,
             {"approved": approved, "after": control_after})
        flag("approval_control.states_settled", states_settled,
             {"approved": approved, "states": control_states})
        flag("approval_control.copy_isolated",
             control.get("copy_inside_workdir") is True
             and control.get("copy_differs_from_primary") is True,
             {"copy_path": control.get("copy_path")})
        flag("approval_control.primary_unchanged",
             control.get("primary_unchanged") is True,
             control.get("primary_after"))
    elif control.get("ran") is True:
        # Negative sweep: the control is evidence, but nothing to certify.
        flag("approval_control.decision_applied", decision_applied,
             control.get("decision"))
        flag("approval_control.primary_unchanged",
             control.get("primary_unchanged") is True,
             control.get("primary_after"))
    else:
        add("approval_control.ran", "unknown",
            control.get("skip_reason") or "no pending rows to decide")


    failed = [c for c in checks if c["state"] == "fail"]
    if failed:
        verdict, code = "failed", EXIT_FAILED
    elif not evidence_complete or not green:
        verdict, code = "negative", EXIT_NEGATIVE
    else:
        verdict, code = "qualified", EXIT_QUALIFIED

    passed = sum(1 for c in checks if c["state"] == "pass")
    unknown = sum(1 for c in checks if c["state"] == "unknown")
    summary = (
        f"{passed} pass / {len(failed)} fail / {unknown} unknown"
    )
    return {
        "verdict": verdict,
        "exit_code": code,
        "checks": checks,
        "summary": summary,
        "failed": [c["name"] for c in failed],
    }


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_backend_on_path() -> None:
    backend = str(_backend_dir())
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _replay_command(argv: Sequence[str]) -> str:
    return shlex.join(
        ["python", "scripts/team05_live_qualification.py", *argv])


def _loopback_opener() -> urllib.request.OpenerDirector:
    """An opener that NEVER uses a proxy.

    Clearing the proxy environment is not sufficient: on macOS
    ``urllib.request.getproxies()`` also reads System Configuration proxies.
    An explicit empty ``ProxyHandler`` disables every source.
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def response_peer_host(resp: Any) -> Optional[str]:
    """Observed peer host for an open HTTP response, when introspectable."""
    try:
        sock = getattr(getattr(getattr(resp, "fp", None), "raw", None),
                       "_sock", None)
    except Exception:  # noqa: BLE001 - introspection only
        sock = None
    if sock is None:
        sock = getattr(resp, "socket", None)
    if sock is None:
        return None
    try:
        peer = sock.getpeername()
    except (OSError, AttributeError):
        return None
    if isinstance(peer, tuple) and peer:
        return str(peer[0])
    return None


def _request_json(url: str, timeout: float,
                  body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with _loopback_opener().open(req, timeout=timeout) as resp:
            peer = response_peer_host(resp)
            if peer is not None and not is_loopback_host(peer):
                raise NonLoopbackNetwork(
                    f"response for {url} arrived from non-loopback peer "
                    f"{peer!r}")
            _LOOPBACK_PEERS.append({"url": url, "peer": peer})
            payload = resp.read()
    except (urllib.error.URLError, OSError) as exc:
        raise PreconditionError(
            f"local Ollama request failed: {url}: {exc}") from exc
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreconditionError(
            f"non-JSON response from {url}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise PreconditionError(f"non-object JSON from {url}")
    return parsed


def _ollama_root(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


def _openai_compatible_base(base_url: str) -> str:
    """The SDK client needs the OpenAI-compatible ``/v1`` suffix."""
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _probe_ollama(base_url: str, timeout: float) -> Dict[str, Any]:
    root = _ollama_root(base_url)
    tags = _request_json(f"{root}/api/tags", timeout)
    pulled = [
        str(m.get("name")) for m in tags.get("models", [])
        if isinstance(m, dict) and m.get("name")
    ]
    ps_error = None
    try:
        ps = _request_json(f"{root}/api/ps", timeout)
    except PreconditionError as exc:
        # /api/ps is newer than /api/tags; absence is unknown, not fatal.
        ps = {"models": []}
        ps_error = str(exc)
    running = [
        str(m.get("name") or m.get("model"))
        for m in ps.get("models", [])
        if isinstance(m, dict) and (m.get("name") or m.get("model"))
    ]
    return {"root": root, "pulled": pulled, "running": running,
            "tags_raw_count": len(tags.get("models", []) or []),
            "ps_error": ps_error}


def _warm_model(root: str, model: str, timeout: float) -> Dict[str, Any]:
    """Load the model without consuming a scheduler call.

    A one-token ``ping`` is the cheapest load trigger Ollama offers;
    ``keep_alive`` holds the model across the 30 s scheduler tick.
    """
    started = time.monotonic()
    payload = _request_json(
        f"{root}/api/generate",
        timeout,
        {
            "model": model,
            "prompt": "ping",
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_predict": 1, "temperature": 0.0},
        },
    )
    return {
        "model": payload.get("model"),
        "done_reason": payload.get("done_reason"),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def _remaining_proxy_env() -> Dict[str, str]:
    """Proxy variables that are still set (must be empty in a live run)."""
    return {name: os.environ[name] for name in PROXY_ENV_VARS
            if os.environ.get(name, "")}


def _scrub_proxy_env() -> List[str]:
    """Clear uppercase AND lowercase proxy variables.

    Assigning ``""`` (not unsetting) also blocks a later ``load_dotenv()``
    from re-introducing a proxy: ``load_dotenv`` does not override keys that
    already exist.
    """
    cleared = []
    for key in PROXY_ENV_VARS:
        if os.environ.get(key, ""):
            cleared.append(key)
        os.environ[key] = ""
    return cleared


def _scrub_db_env() -> Dict[str, str]:
    """Disable ambient database overrides, returning what was inherited.

    Without this, ``TESTING=1`` (recommended by the repo for ad-hoc scripts)
    silently rewrites ``DATABASE_URL`` to ``backend/test_integration.db`` and
    ``ATOM_MOCK_DATABASE=true`` rewrites it to ``:memory:``.  The destination
    proof would then fail with a confusing message; clearing first (and
    recording the inherited values) keeps the run honest.
    """
    inherited: Dict[str, str] = {}
    for key in DB_ENV_OVERRIDES:
        value = os.environ.get(key)
        if value:
            inherited[key] = value
        # Empty string, not pop: load_dotenv() must not restore it.
        os.environ[key] = ""
    return inherited


def _scrub_provider_env() -> List[str]:
    """Remove every ambient provider credential and proxy.

    ``load_dotenv()`` (called by core.database/byok_endpoints) does not
    override keys that are already present, even when empty, so assigning
    ``""`` is a stronger guard than ``unset``.
    """
    scrubbed = []
    for key in list(os.environ):
        if key.endswith(_API_KEY_SUFFIX):
            os.environ[key] = ""
            scrubbed.append(key)
    for key in FLAG_ENV_VARS:
        if os.environ.get(key, "") != "":
            scrubbed.append(key)
        os.environ[key] = ""
    # A local-only mode would mask the policy check this qualification makes;
    # isolation is proven by the client set + selected policy instead.
    for key in ("ATOM_LOCAL_ONLY",):
        if os.environ.get(key, "") != "":
            scrubbed.append(key)
        os.environ[key] = ""
    scrubbed.extend(_scrub_proxy_env())
    return sorted(set(scrubbed))


def _install_isolation_env(
    workdir: Path,
    base_url: str,
    model: str,
    request_timeout: float,
) -> Dict[str, Path]:
    """Set every path/env boundary BEFORE core modules are imported."""
    paths = {
        "db": workdir / "team05_live.sqlite3",
        "byok_config": workdir / "byok_config.json",
        "byok_keys": workdir / "byok_keys.json",
        "byok_enc_key": workdir / "byok_encryption_key",
        "catalog": workdir / "provider_model_catalog.json",
        "pricing": workdir / "ai_pricing_cache.json",
        "pair_memos": workdir / "llm_pair_memos.json",
        "drift_state": workdir / "model_resolution_state.json",
        "evidence": workdir / "evidence.json",
        "log": workdir / "qualification.log",
    }
    os.environ["DATABASE_URL"] = f"sqlite:///{paths['db']}"
    os.environ["BYOK_CONFIG_FILE"] = str(paths["byok_config"])
    os.environ["BYOK_KEYS_FILE"] = str(paths["byok_keys"])
    os.environ["BYOK_ENC_KEY_FILE"] = str(paths["byok_enc_key"])
    os.environ["BYOK_ENCRYPTION_KEY"] = ""
    os.environ["ATOM_PROVIDER_MODEL_CATALOG_PATH"] = str(paths["catalog"])
    os.environ["ATOM_PAIR_MEMO_PATH"] = str(paths["pair_memos"])
    os.environ["OLLAMA_BASE_URL"] = _openai_compatible_base(base_url)
    os.environ["OLLAMA_MODEL"] = model
    # Declared local-route context for routing filters. The sweep prompts are
    # far smaller; this does not force Ollama's num_ctx.
    os.environ["OLLAMA_CONTEXT_WINDOW"] = "131072"
    os.environ["ATOM_ALIGNMENT_SWEEP_ENABLED"] = "true"
    os.environ["ATOM_ORG_AUTO_ENFORCE"] = "approve"
    os.environ["ATOM_ORG_TELEMETRY_ENABLED"] = "true"
    os.environ["ATOM_MODEL_DRIFT_DETECTION_ENABLED"] = "true"
    os.environ["ATOM_COMPLETION_MAX_TOKENS"] = "256"
    # core.auth persists a dev secret under backend/data/ when unset. A
    # qualification must not create or rewrite that file.
    os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
    # The known per-call bound: the SDK client owns this timeout; the
    # _run_coroutine_sync(120s) argument does not apply on the worker thread.
    os.environ["OLLAMA_REQUEST_TIMEOUT"] = str(float(request_timeout))
    os.environ["ATOM_LLM_PROVIDER_POLICY"] = json.dumps({
        "mode": "selected",
        "allowed_providers": ["ollama"],
        "preferred": {"provider": "ollama", "model": model},
    })
    return paths


def _protected_paths() -> List[Path]:
    """Every live-tree file whose change invalidates a qualification.

    Two roots are covered on purpose: ``backend/data`` is the anchored store,
    while a CWD-relative ``./data/...`` writer launched from the repo root
    creates a second store (the documented path-anchoring bug class). The live
    SQLite files are included explicitly as well.  These paths are only ever
    stat'ed - never opened - so credential files are not read.
    """
    backend = _backend_dir()
    paths: List[Path] = [
        root / name
        for root in (backend / "data", backend.parent / "data")
        for name in _PROTECTED_DATA_FILES
    ]
    paths.extend((
        backend / "atom.db",
        backend / "dev.db",
        backend / "test_integration.db",
    ))
    return paths


def _protected_snapshot() -> Dict[str, Any]:
    return {str(path): _db_stats(path) for path in _protected_paths()}


def _changed_protected_paths(
    before: Dict[str, Any], after: Dict[str, Any],
) -> List[str]:
    changed = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def _resolved_path_text(value: Any) -> Optional[str]:
    """Real path for a resolved path/constant, or None when not a path."""
    try:
        return os.path.realpath(os.fspath(value))
    except TypeError:
        return None


def verify_scratch_path_resolution(
    paths: Dict[str, Path],
    modules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Prove the PRODUCTION modules resolved their paths into the workdir.

    ``_install_isolation_env`` declares where things *should* go.  This is the
    observed half: it reads the already-imported modules' actual constants (and
    the pair-memo path function) and compares them with the exact scratch
    files.  Modules that have not been imported are listed, not assumed.

    Pure enough for tests: pass a ``{module_name: module_or_namespace}`` map.
    """
    module_map = sys.modules if modules is None else modules
    checked: List[Dict[str, Any]] = []
    mismatches: List[Dict[str, Any]] = []
    not_loaded: List[str] = []

    for module_name, attribute, key in _SCRATCH_PATH_CONSTANTS:
        module = module_map.get(module_name)
        if module is None:
            not_loaded.append(module_name)
            continue
        value = getattr(module, attribute, _MISSING)
        if value is _MISSING:
            continue
        if callable(value):
            try:
                value = value()
            except Exception:  # noqa: BLE001 - recorded as a mismatch
                value = None
        expected_path = paths.get(key)
        expected = _resolved_path_text(expected_path)
        resolved = _resolved_path_text(value)
        entry = {
            "module": module_name,
            "attribute": attribute,
            "resolved": resolved,
            "expected": expected,
        }
        checked.append(entry)
        if expected is None or resolved is None or resolved != expected:
            mismatches.append(entry)

    return {
        "checked": checked,
        "mismatches": mismatches,
        "not_loaded": sorted(set(not_loaded)),
        "ok": not mismatches,
    }


def _sqlite_table_counts(path: Path, tables: Sequence[str]) -> Dict[str, int]:
    con = sqlite3.connect(str(path))
    try:
        out: Dict[str, int] = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            out[table] = int(
                con.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
        return out
    finally:
        con.close()


class _SqliteOpenTracker:
    """Record - and REFUSE - SQLite opens before the file is connected.

    A direct, process-local proof that the live dev DB was never touched,
    independent of unrelated writers (a running backend) changing its stat.
    Both the top-level ``sqlite3.connect`` and ``sqlite3.dbapi2.connect`` are
    patched because SQLAlchemy's pysqlite dialect imports the latter.

    Rejection happens BEFORE ``original(...)`` runs: a path outside the
    scratch workdir raises ``NonScratchSqliteOpen`` without opening it.
    ``:memory:`` is allowed (nothing durable can be hit).
    """

    def __init__(self, allowed_root: Optional[Path] = None) -> None:
        self.allowed_root = allowed_root
        self.opened: List[str] = []
        self.rejected: List[Dict[str, Any]] = []
        self._original: Any = None
        self._original_dbapi: Any = None

    def install(self) -> "_SqliteOpenTracker":
        original = sqlite3.connect
        original_dbapi = sqlite3.dbapi2.connect
        self._original, self._original_dbapi = original, original_dbapi

        def tracking_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
            if not sqlite_target_allowed(database, self.allowed_root):
                resolved = _sqlite_target_path(database)
                entry = {"path": _sqlite_target_text(database),
                         "resolved": resolved}
                self.rejected.append(entry)
                raise NonScratchSqliteOpen(
                    "refusing a non-scratch SQLite open: "
                    f"{resolved or entry['path']!r}")
            try:
                self.opened.append(
                    _sqlite_target_path(database)
                    or _sqlite_target_text(database))
            except Exception:  # noqa: BLE001 - evidence only
                self.opened.append(str(database))
            return original(database, *args, **kwargs)

        sqlite3.connect = tracking_connect  # type: ignore[assignment]
        sqlite3.dbapi2.connect = tracking_connect  # type: ignore[assignment]
        return self

    def restore(self) -> None:
        if self._original is not None:
            sqlite3.connect = self._original  # type: ignore[assignment]
        if self._original_dbapi is not None:
            sqlite3.dbapi2.connect = self._original_dbapi  # type: ignore[assignment]


def _install_sqlite_open_tracker(
    allowed_root: Optional[Path] = None,
) -> _SqliteOpenTracker:
    """Install the pre-connect SQLite guard (see ``_SqliteOpenTracker``)."""
    return _SqliteOpenTracker(allowed_root).install()


class _ProtectedPathGuard:
    """Refuse writes to the live tree's protected files before they happen.

    The stat snapshot can only prove a protected file changed after the damage
    is done, and it cannot attribute the writer.  This guard is the write-time
    half: every Python write path that could reach a protected file is checked
    first and the attempt is recorded + raised as ``ProtectedPathWrite``.

    Covered primitives:
    * ``open`` / ``io.open`` in a write mode (also backs ``Path.write_text``);
    * ``os.open`` with write/create/truncate/append flags (also backs touch);
    * ``os.replace`` / ``os.rename`` (the atomic-write pattern that silently
      swaps a protected file's inode);
    * ``os.remove`` / ``os.unlink`` (deleting a credential is a change too).

    Reads are never inspected.  Targets are compared by real path so a symlink
    or a relative alias cannot slip past.
    """

    _WRITE_FLAGS = (
        getattr(os, "O_WRONLY", 0)
        | getattr(os, "O_RDWR", 0)
        | getattr(os, "O_CREAT", 0)
        | getattr(os, "O_TRUNC", 0)
        | getattr(os, "O_APPEND", 0)
    )

    def __init__(self, protected: Sequence[Path]) -> None:
        self.protected = {os.path.realpath(str(path)) for path in protected}
        self.refused: List[Dict[str, Any]] = []
        self.installed = False
        self._saved: List[Tuple[Any, str, Any]] = []

    def _check(self, target: Any, operation: str) -> None:
        resolved = _resolved_path_text(target)
        if resolved is None or resolved not in self.protected:
            return
        entry = {"path": resolved, "operation": operation}
        self.refused.append(entry)
        raise ProtectedPathWrite(
            f"refusing to {operation} protected live-tree file {resolved!r}")

    def install(self) -> "_ProtectedPathGuard":
        import builtins
        import io

        real_open = builtins.open
        real_io_open = io.open
        real_os_open = os.open

        def guarded_open(file: Any, mode: str = "r", *args: Any,
                         **kwargs: Any) -> Any:
            if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
                self._check(file, f"open(mode={mode!r})")
            return real_open(file, mode, *args, **kwargs)

        def guarded_os_open(path: Any, flags: int, *args: Any,
                            **kwargs: Any) -> Any:
            if int(flags) & self._WRITE_FLAGS:
                self._check(path, f"os.open(flags={int(flags)})")
            return real_os_open(path, flags, *args, **kwargs)

        builtins.open = guarded_open  # type: ignore[assignment]
        io.open = guarded_open  # type: ignore[assignment]
        os.open = guarded_os_open  # type: ignore[assignment]
        self._saved = [
            (builtins, "open", real_open),
            (io, "open", real_io_open),
            (os, "open", real_os_open),
        ]

        for name in ("replace", "rename", "remove", "unlink"):
            original = getattr(os, name, None)
            if original is None:
                continue

            def guarded_fsop(*args: Any, _original: Any = original,
                             _name: str = name, **kwargs: Any) -> Any:
                for target in args[:2]:
                    self._check(target, f"os.{_name}")
                return _original(*args, **kwargs)

            setattr(os, name, guarded_fsop)
            self._saved.append((os, name, original))

        self.installed = True
        return self

    def restore(self) -> None:
        for target, name, original in self._saved:
            setattr(target, name, original)
        self._saved.clear()

    def observation(self) -> Dict[str, Any]:
        return {
            # "installed" survives restore(): evidence describes the RUN.
            "guard_installed": bool(self.installed),
            "protected_count": len(self.protected),
            "refused": list(self.refused),
        }


class _LoopbackGuard:
    """Refuse every non-loopback AF_INET/AF_INET6 connection attempt.

    Connection-time enforcement is the only defence that survives library
    differences: ``urllib``, ``httpx``/``anyio`` (the OpenAI SDK), raw
    sockets and anything else all end at ``socket.socket.connect`` (async
    clients go through asyncio's ``sock_connect``, which calls the same
    method) or ``socket.create_connection``.  Unix-domain sockets pass
    through untouched.
    """

    def __init__(self) -> None:
        self.blocked: List[Dict[str, Any]] = []
        self.installed = False
        self._saved: List[Tuple[Any, str, Any]] = []

    def _check(self, address: Any, kind: str) -> None:
        if not isinstance(address, tuple) or not address:
            return  # AF_UNIX or an opaque address form
        host = str(address[0])
        if is_loopback_host(host):
            return
        entry = {
            "kind": kind,
            "host": host,
            "port": address[1] if len(address) > 1 else None,
        }
        self.blocked.append(entry)
        raise NonLoopbackNetwork(
            f"refusing non-loopback network connection to {host!r} ({kind})")

    def install(self) -> "_LoopbackGuard":
        sock_cls = socket.socket
        original_connect = sock_cls.connect
        original_connect_ex = sock_cls.connect_ex
        original_create = socket.create_connection

        def guarded_connect(sock: Any, address: Any, *args: Any,
                            **kwargs: Any) -> Any:
            self._check(address, "socket.connect")
            return original_connect(sock, address, *args, **kwargs)

        def guarded_connect_ex(sock: Any, address: Any, *args: Any,
                               **kwargs: Any) -> Any:
            self._check(address, "socket.connect_ex")
            return original_connect_ex(sock, address, *args, **kwargs)

        def guarded_create_connection(address: Any, *args: Any,
                                      **kwargs: Any) -> Any:
            self._check(address, "socket.create_connection")
            return original_create(address, *args, **kwargs)

        for target, name, value in (
            (sock_cls, "connect", guarded_connect),
            (sock_cls, "connect_ex", guarded_connect_ex),
            (socket, "create_connection", guarded_create_connection),
        ):
            self._saved.append((target, name, getattr(target, name)))
            setattr(target, name, value)
        self.installed = True
        return self

    def restore(self) -> None:
        for target, name, original in reversed(self._saved):
            try:
                setattr(target, name, original)
            except Exception:  # noqa: BLE001 - restore is best effort
                pass
        self._saved.clear()

    def observation(self) -> Dict[str, Any]:
        return {
            # "installed" survives restore(): evidence describes the RUN, not
            # the state at teardown time.
            "guard_installed": bool(self.installed),
            "blocked": list(self.blocked),
            "peers": list(_LOOPBACK_PEERS),
        }


def _live_sqlite_paths() -> set:
    backend = _backend_dir()
    candidates = (
        backend / "data" / "atom.db",
        backend / "dev.db",
        backend / "test_integration.db",
    )
    return {os.path.realpath(str(p)) for p in candidates}


def _assert_scratch_db_identity(db_path: Path, workdir: Path) -> None:
    real_db = os.path.realpath(db_path)
    real_workdir = os.path.realpath(workdir)
    if not real_db.startswith(real_workdir + os.sep):
        raise PreconditionError(
            f"scratch DB escaped the work directory: {real_db}")
    backend_dir = _backend_dir()
    real_data_dir = os.path.realpath(backend_dir / "data")
    if real_workdir == real_data_dir or \
            real_workdir.startswith(real_data_dir + os.sep):
        raise PreconditionError(
            f"refusing to write qualification data under {real_data_dir}")
    forbidden = {
        os.path.realpath(backend_dir / "data" / "atom.db"),
        os.path.realpath(backend_dir / "dev.db"),
        os.path.realpath(backend_dir / "test_integration.db"),
    }
    if real_db in forbidden:
        raise PreconditionError(f"refusing live/dev database: {real_db}")


def _engine_url_target(
    engine: Any,
    expected_path: Path,
    workdir: Path,
) -> Dict[str, Any]:
    """Inspect a real SQLAlchemy engine/connection target (no connection)."""
    url = getattr(engine, "url", None)
    if url is None:
        return {
            "present": False,
            "url": None,
            "backend": None,
            "database": None,
            "resolved": None,
            "mismatch": "no SQLAlchemy URL to inspect",
        }
    try:
        backend = url.get_backend_name()
    except Exception:  # noqa: BLE001 - a broken URL is a mismatch
        backend = None
    database = getattr(url, "database", None)
    resolved = None
    if database and not str(database).startswith("file:") \
            and str(database) not in (":memory:", ""):
        resolved = os.path.realpath(str(database))
    mismatch = scratch_sqlite_mismatch(
        backend, database, expected_path, workdir)
    return {
        "present": True,
        "url": str(url),
        "backend": backend,
        "database": str(database) if database is not None else None,
        "resolved": resolved,
        "mismatch": mismatch,
    }


def _session_bind_target(
    session_factory: Any,
    expected_path: Path,
    workdir: Path,
) -> Dict[str, Any]:
    """Inspect the engine ``SessionLocal`` is actually bound to."""
    bind = None
    kw = getattr(session_factory, "kw", None)
    if isinstance(kw, dict):
        bind = kw.get("bind")
    if bind is None:
        bind = getattr(session_factory, "bind", None)
    if bind is None:
        return {
            "present": False,
            "url": None,
            "backend": None,
            "database": None,
            "resolved": None,
            "mismatch": "sessionmaker has no bound engine",
        }
    return _engine_url_target(bind, expected_path, workdir)


def verify_database_destination(
    database_module: Any,
    expected_path: Path,
    workdir: Path,
) -> Dict[str, Any]:
    """Prove the imported ``core.database`` writes ONLY to the scratch file.

    ``database.DATABASE_URL`` is a string; the engine's own ``url`` is what
    SQLAlchemy dials, and ``SessionLocal``'s bind is what the qualification
    session uses.  All three are inspected BEFORE ``create_all`` (which
    performs the first connect) and any mismatch is a named precondition.
    """
    engine_target = _engine_url_target(
        getattr(database_module, "engine", None), expected_path, workdir)
    bind_target = _session_bind_target(
        getattr(database_module, "SessionLocal", None), expected_path, workdir)
    live_dev = False
    if engine_target.get("url"):
        try:
            live_dev = bool(
                database_module._targets_live_dev_db(engine_target["url"]))
        except Exception:  # noqa: BLE001 - unknown is not a pass
            live_dev = False
    declared = str(getattr(database_module, "DATABASE_URL", "") or "")
    declared_path = None
    if declared.startswith("sqlite:///"):
        declared_path = os.path.realpath(declared.split(":///", 1)[1])
    reasons = [
        f"{label}: {target['mismatch']}"
        for label, target in (("engine", engine_target),
                              ("SessionLocal bind", bind_target))
        if target.get("mismatch")
    ]
    if live_dev:
        reasons.append("engine URL targets the live dev database")
    return {
        "engine": engine_target,
        "session_bind": bind_target,
        "declared_database_url": declared,
        "declared_resolves_to": declared_path,
        "declared_matches_scratch": (
            declared_path == os.path.realpath(str(expected_path))),
        "live_dev_target": live_dev,
        "ok": not reasons,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Seam installation (all call-through recorders; transport is NEVER replaced)
# ---------------------------------------------------------------------------


class _Seams:
    def __init__(self, workdir: Path, model: str, expected: int) -> None:
        self.workdir = workdir
        self.model = model
        self.expected = expected
        self._undo: List[Tuple[Any, str, Any]] = []
        self.trace: List[Dict[str, Any]] = []
        self.handlers: List[Dict[str, Any]] = []
        self.attempts: List[Dict[str, Any]] = []
        self.served_routes: List[Dict[str, Any]] = []
        self.echoed_models: List[Optional[str]] = []
        self.notifications: List[Dict[str, Any]] = []
        self.alignment_results: List[Dict[str, Any]] = []
        self.certify_results: List[Dict[str, Any]] = []
        self.pass_completed = threading.Event()
        self.pass_started_at: Optional[float] = None
        self.pass_finished_at: Optional[float] = None
        self.non_local_clients: List[str] = []
        self.safety_abort: Optional[str] = None
        self.policy_view: Dict[str, Any] = {}

    # -- low level -------------------------------------------------------
    def _swap(self, target: Any, name: str, value: Any) -> None:
        original = getattr(target, name)
        self._undo.append((target, name, original))
        setattr(target, name, value)

    def _record(self, name: str, **fields: Any) -> None:
        entry = {
            "name": name,
            "at": round(time.monotonic(), 6),
            "thread": threading.current_thread().name,
            "thread_id": threading.get_ident(),
        }
        entry.update(fields)
        self.trace.append(entry)

    # -- install ---------------------------------------------------------
    def install(self, automation: Any, byok: Any, dpf: Any,
                provenance: Any) -> None:
        from core.org_alignment import STRUCTURES, SCENARIOS
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher

        # 1) Pricing metadata only: reduce the parser's expected count to
        #    the model the runtime actually advertises.
        dpf.PRICING_CACHE_PATH = self.workdir / "ai_pricing_cache.json"
        fetcher = DynamicPricingFetcher()
        fetcher.pricing_cache = {
            self.model: {
                "litellm_provider": "ollama",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "max_input_tokens": 131072,
                "max_output_tokens": 8192,
                "context_window": 131072,
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
            },
        }
        self.fetcher = fetcher

        def _get_fetcher(*_a: Any, **_kw: Any) -> Any:
            return fetcher

        async def _get_fetcher_async(*_a: Any, **_kw: Any) -> Any:
            return fetcher

        def _refresh(*_a: Any, **_kw: Any) -> Dict[str, Any]:
            return {"skipped": "qualification metadata cache"}

        async def _refresh_async(*_a: Any, **_kw: Any) -> Dict[str, Any]:
            return {"skipped": "qualification metadata cache"}

        for module in (byok, dpf):
            for name, replacement in (
                ("get_pricing_fetcher", _get_fetcher),
                ("get_pricing_fetcher_initialized", _get_fetcher_async),
                ("get_pricing_fetcher_initialized_sync", _get_fetcher),
                ("refresh_pricing_cache", _refresh_async),
            ):
                if hasattr(module, name):
                    self._swap(module, name, replacement)

        # 2) Drift-state evidence goes to the workdir, and the singleton is
        #    reset so the baseline written during THIS run is new.
        provenance._DEFAULT_STATE_PATH = self.workdir / "model_resolution_state.json"
        provenance._detector = None

        # 3) Provider-echo recorder (call-through). This is the only source of
        #    the served model identity; it is the production recorder, wrapped.
        real_set_echo = provenance.set_echoed_response_model

        def _set_echo(model_id: Optional[str]) -> None:
            self.echoed_models.append(model_id)
            return real_set_echo(model_id)

        self._swap(provenance, "set_echoed_response_model", _set_echo)

        real_set_served = byok.set_served_route

        def _set_served(provider_id: Optional[str],
                        model: Optional[str]) -> None:
            self.served_routes.append({
                "provider": provider_id, "model": model,
                "thread": threading.current_thread().name,
            })
            return real_set_served(provider_id, model)

        self._swap(byok, "set_served_route", _set_served)

        # 4) Notification intent recorder (call-through; scratch DB means
        #    _notify finds no admin recipient and sends nothing).
        real_spawn = automation._spawn_notification

        def _spawn(ntype: str, title: str, message: str,
                   action_url: str = "") -> None:
            self.notifications.append({
                "type": ntype, "title": title, "action_url": action_url,
            })
            return real_spawn(ntype, title, message, action_url)

        self._swap(automation, "_spawn_notification", _spawn)

        # 5) Scheduler chain recorders (call-through, order + thread proof).
        def _sync_recorder(name: str, original: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self._record(name, gate_locked=self._gate_locked(automation))
                return original(*args, **kwargs)

            return wrapper

        def _async_recorder(name: str, original: Any) -> Any:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                self._record(name, gate_locked=self._gate_locked(automation))
                return await original(*args, **kwargs)

            return wrapper

        for name in ("ensure_automation_task", "_run_auto_certification_guarded",
                     "run_auto_certification", "_default_chat_fn"):
            self._swap(automation, name,
                       _sync_recorder(name, getattr(automation, name)))
        for name in ("org_politics_automation_loop",
                     "run_auto_certification_async"):
            self._swap(automation, name,
                       _async_recorder(name, getattr(automation, name)))

        real_certify = automation.certify

        def _certify(*args: Any, **kwargs: Any) -> Any:
            self.pass_started_at = time.monotonic()
            self._record(
                "certify",
                gate_locked=self._gate_locked(automation),
                notification_loop_bound=(
                    automation._notification_loop.get() is not None),
            )
            try:
                result = real_certify(*args, **kwargs)
                self.certify_results.append(result)
                return result
            finally:
                self.pass_finished_at = time.monotonic()
                self.pass_completed.set()

        self._swap(automation, "certify", _certify)

        real_verdict = automation.alignment_verdict

        def _verdict(*args: Any, **kwargs: Any) -> Any:
            self._record(
                "alignment_verdict",
                chat_fn_is_none=kwargs.get("chat_fn") is None
                and not args,
            )
            result = real_verdict(*args, **kwargs)
            self.alignment_results.append(result)
            return result

        self._swap(automation, "alignment_verdict", _verdict)

        # 6) Real handler construction + dispatch recorder. A non-Ollama
        #    client is a hard safety abort: raise BEFORE _default_chat_fn can
        #    use it, so no cloud request is possible even transiently.
        real_init = byok.BYOKHandler.__init__

        def _init(self_handler: Any, *args: Any, **kwargs: Any) -> None:
            real_init(self_handler, *args, **kwargs)
            clients = sorted(getattr(self_handler, "clients", {}) or {})
            async_clients = sorted(
                getattr(self_handler, "async_clients", {}) or {})
            env_keys = sorted(
                getattr(self_handler, "env_key_providers", set()) or set())
            non_local = sorted(
                (set(clients) - {"ollama"})
                | (set(async_clients) - {"ollama"}))
            policy = getattr(self_handler, "provider_policy", None)
            self.handlers.append({
                "workspace_id": getattr(self_handler, "workspace_id", None),
                "clients": clients,
                "async_clients": async_clients,
                "env_key_providers": env_keys,
                "non_local_clients": non_local,
                "policy_mode": getattr(policy, "mode", None),
                "policy_allowed": sorted(
                    getattr(policy, "allowed_providers", []) or []),
                "policy_preferred": getattr(policy, "preferred", None),
                "policy_error": getattr(policy, "error", None),
                "allows_local": bool(
                    policy.allows("ollama", self.model)
                    if policy is not None else False),
                "allows_cloud": bool(
                    policy.allows("openai", "gpt-4o")
                    if policy is not None else True),
            })
            self.policy_view = self.handlers[-1]
            if non_local or env_keys:
                self.non_local_clients = sorted(set(non_local) | set(env_keys))
                self.safety_abort = (
                    "non-local provider/credential leaked into the "
                    f"qualification handler: {self.non_local_clients}")
                raise SafetyAbort(self.safety_abort)
            if policy is None or policy.mode != "selected" \
                    or not policy.allows("ollama", self.model):
                self.safety_abort = (
                    "provider policy did not resolve to selected/ollama: "
                    f"{getattr(policy, 'mode', None)} "
                    f"{sorted(getattr(policy, 'allowed_providers', []) or [])}"
                    f" error={getattr(policy, 'error', None)}")
                raise SafetyAbort(self.safety_abort)

        self._swap(byok.BYOKHandler, "__init__", _init)

        real_generate = byok.BYOKHandler.generate_response

        async def _generate(self_handler: Any, *args: Any, **kwargs: Any) -> Any:
            entry = {
                "thread": threading.current_thread().name,
                "temperature": kwargs.get("temperature"),
                "prefer_cost": kwargs.get("prefer_cost"),
                "system_present": bool(
                    kwargs.get("system_instruction")
                    or (kwargs.get("messages") or [{}])[0].get("content")),
                "last_used_provider": None,
                "last_used_model": None,
                "result_length": None,
                "error": None,
            }
            try:
                result = await real_generate(self_handler, *args, **kwargs)
                entry["result_length"] = (
                    len(result) if isinstance(result, str) else None)
                return result
            except BaseException as exc:  # noqa: BLE001 - evidence
                entry["error"] = type(exc).__name__
                raise
            finally:
                entry["last_used_provider"] = getattr(
                    self_handler, "_last_used_provider", None)
                entry["last_used_model"] = getattr(
                    self_handler, "_last_used_model", None)
                self.attempts.append(entry)

        self._swap(byok.BYOKHandler, "generate_response", _generate)

        self.expected = len(SCENARIOS) * len(STRUCTURES) * 2

    @staticmethod
    def _gate_locked(automation: Any) -> bool:
        gate = getattr(automation, "_pass_gate", None)
        try:
            return bool(gate and gate.locked())
        except Exception:  # noqa: BLE001
            return False

    # -- restore ---------------------------------------------------------
    def restore(self) -> None:
        for target, name, original in reversed(self._undo):
            try:
                setattr(target, name, original)
            except Exception:  # noqa: BLE001 - restore is best effort
                pass
        self._undo.clear()


# ---------------------------------------------------------------------------
# Scheduler drive
# ---------------------------------------------------------------------------


def _drive_scheduler(automation: Any, seams: _Seams,
                     budget_seconds: float) -> Dict[str, Any]:
    import asyncio

    state: Dict[str, Any] = {
        "registered": False,
        "registered_once": False,
        "main_thread": threading.current_thread().name,
        "first_registration": None,
        "error": None,
        "timed_out": False,
    }

    async def scenario() -> None:
        automation.ensure_automation_task()
        first = automation._automation_task
        state["registered"] = first is not None and not first.done()
        state["first_registration"] = round(time.monotonic(), 6)
        automation.ensure_automation_task()
        second = automation._automation_task
        state["registered_once"] = first is not None and first is second
        if first is None:
            # No task was registered (mode off / no running loop). Nothing
            # can complete; fail now instead of waiting out the budget.
            return

        deadline = time.monotonic() + budget_seconds
        while not seams.pass_completed.is_set():
            if first.done():
                state["error"] = state["error"] or "scheduler task exited"
                break
            if time.monotonic() >= deadline:
                state["timed_out"] = True
                break
            await asyncio.sleep(0.25)

        # Let notification tasks scheduled on this loop run before teardown.
        await asyncio.sleep(0.2)
        task = automation._automation_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001 - cancellation is expected
                pass

    try:
        asyncio.run(scenario())
    except BaseException as exc:  # noqa: BLE001 - recorded, not hidden
        state["error"] = f"{type(exc).__name__}: {exc}"
    return state


def _collect_findings(db_path: Path) -> Dict[str, Any]:
    """Re-open the scratch file with a FRESH engine (durable read)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.org_politics_automation as automation
    from core.models import OrgPoliticsAction

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        db = factory()
        try:
            rows = (
                db.query(OrgPoliticsAction)
                .order_by(OrgPoliticsAction.created_at.asc(),
                          OrgPoliticsAction.flag_key.asc())
                .all()
            )
            payload = [
                {
                    "id": str(r.id),
                    "flag_key": r.flag_key,
                    "verdict": r.verdict,
                    "mode": r.mode,
                    "state": r.state,
                    "decided_at": (
                        r.decided_at.isoformat() if r.decided_at else None),
                }
                for r in rows
            ]
            flag_values = {
                key: automation.resolve_flag_value(db, key)
                for key in automation.FLAG_KEYS
            }
            pending = automation.pending_approvals(db)
        finally:
            db.close()
        return {
            "rows": payload,
            "flag_values": flag_values,
            "pending_view_count": len(pending),
            "expected_flag_keys": list(automation.FLAG_KEYS),
        }
    finally:
        engine.dispose()


def _approval_control(db_path: Path, workdir: Path) -> Dict[str, Any]:
    """Prove the pending rows are preserved UNTIL a real decision is made.

    Runs on a byte-consistent COPY so the primary evidence DB is untouched.
    The returned booleans are consumed by ``classify_observations``: a
    regression in ``apply_pending_decision`` now FAILS the qualification
    instead of only appearing in the evidence file.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.org_politics_automation as automation
    from core.models import OrgPoliticsAction

    workdir = Path(workdir)
    _assert_scratch_db_identity(db_path, workdir)
    copy_path = workdir / "approval_control.sqlite3"
    real_copy = os.path.realpath(str(copy_path))
    real_primary = os.path.realpath(str(db_path))
    real_workdir = os.path.realpath(str(workdir))
    if real_copy == real_primary:
        raise PreconditionError(
            "approval control copy would overwrite the primary DB")
    result: Dict[str, Any] = {
        "ran": False,
        "primary_path": str(db_path),
        "copy_path": str(copy_path),
        "copy_inside_workdir": (
            real_copy.startswith(real_workdir + os.sep)),
        "copy_differs_from_primary": real_copy != real_primary,
        "primary_unchanged": False,
        "decision_applied": False,
    }

    primary_before = _collect_findings(db_path)

    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copy_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    engine = create_engine(
        f"sqlite:///{copy_path}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        db = factory()
        try:
            rows = db.query(OrgPoliticsAction).all()
            result["rows_before"] = len(rows)
            target = automation.FLAG_KEYS[0]
            result["approved_flag"] = target
            decision = automation.apply_pending_decision(
                db, target, approve=True)
            result["decision"] = decision
            result["decision_applied"] = (
                isinstance(decision, dict)
                and decision.get("state") == "applied")
            result["flag_values_after_approve"] = {
                key: automation.resolve_flag_value(db, key)
                for key in automation.FLAG_KEYS
            }
            result["states_after_approve"] = {
                str(r.flag_key): r.state for r in rows
            }
        finally:
            db.close()
    finally:
        engine.dispose()

    primary_after = _collect_findings(db_path)
    result["primary_after"] = {
        "rows": primary_after.get("rows"),
        "flag_values": primary_after.get("flag_values"),
        "pending_view_count": primary_after.get("pending_view_count"),
    }
    result["primary_unchanged"] = (
        primary_before.get("rows") == primary_after.get("rows")
        and primary_before.get("flag_values")
        == primary_after.get("flag_values")
        and primary_before.get("pending_view_count")
        == primary_after.get("pending_view_count")
    )
    result["ran"] = True
    return result


# ---------------------------------------------------------------------------
# Self-test (offline)
# ---------------------------------------------------------------------------


def _self_test() -> int:
    failures: List[str] = []

    def expect(name: str, condition: bool) -> None:
        print(f"[{'PASS' if condition else 'FAIL'}] {name}")
        if not condition:
            failures.append(name)

    expect("loopback localhost",
           is_loopback_url("http://localhost:11434/v1"))
    expect("loopback 127.0.0.1",
           is_loopback_url("http://127.0.0.1:11434"))
    expect("loopback rejects remote",
           not is_loopback_url("https://ollama.example.com:11434"))
    expect("loopback rejects LAN",
           not is_loopback_url("http://192.168.1.5:11434"))
    expect("loopback rejects 0.0.0.0",
           not is_loopback_url("http://0.0.0.0:11434"))
    expect("loopback rejects non-http",
           not is_loopback_url("ftp://127.0.0.1:11434"))

    expect("loopback host ::1", is_loopback_host("::1"))
    expect("loopback host [::1]", is_loopback_host("[::1]"))
    expect("loopback host 127.255.255.254",
           is_loopback_host("127.255.255.254"))
    expect("loopback host rejects LAN ip",
           not is_loopback_host("10.0.0.1"))
    expect("loopback host rejects localhost lookalike",
           not is_loopback_host("localhost.example.com"))
    expect("loopback host rejects empty", not is_loopback_host(None))

    # Proxies: both cases must be cleared (urllib reads lowercase, SDKs upper).
    saved_proxy = {name: os.environ.get(name)
                   for name in PROXY_ENV_VARS}
    os.environ["HTTP_PROXY"] = "http://proxy.example.com:3128"
    os.environ["https_proxy"] = "http://proxy.example.com:3128"
    os.environ["ALL_PROXY"] = "socks5://proxy.example.com:1080"
    os.environ["NO_PROXY"] = ""
    cleared = _scrub_proxy_env()
    expect("proxy scrub clears uppercase",
           os.environ["HTTP_PROXY"] == "" and os.environ["ALL_PROXY"] == "")
    expect("proxy scrub clears lowercase",
           os.environ["https_proxy"] == "")
    expect("proxy scrub reports what it cleared",
           {"HTTP_PROXY", "https_proxy", "ALL_PROXY"} <= set(cleared))
    expect("proxy scrub leaves nothing behind", _remaining_proxy_env() == {})
    for name, value in saved_proxy.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    # Ambient DB overrides must not be able to re-point core.database.
    saved_db_env = {name: os.environ.get(name) for name in DB_ENV_OVERRIDES}
    os.environ["TESTING"] = "1"
    os.environ["ATOM_MOCK_DATABASE"] = "true"
    inherited = _scrub_db_env()
    expect("db overrides cleared",
           os.environ["TESTING"] == ""
           and os.environ["ATOM_MOCK_DATABASE"] == "")
    expect("db overrides recorded as inherited",
           inherited.get("TESTING") == "1"
           and inherited.get("ATOM_MOCK_DATABASE") == "true")
    for name, value in saved_db_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    with tempfile.TemporaryDirectory(prefix="team05-selftest-") as td:
        root = Path(td)
        expect("sqlite guard allows :memory:",
               sqlite_target_allowed(":memory:", root))
        expect("sqlite guard allows workdir file",
               sqlite_target_allowed(root / "scratch.sqlite3", root))
        expect("sqlite guard refuses live-ish path",
               not sqlite_target_allowed(
                   root.parent / "outside.sqlite3", root))
        expect("scratch match accepts exact file",
               scratch_sqlite_mismatch(
                   "sqlite", str(root / "scratch.sqlite3"),
                   root / "scratch.sqlite3", root) is None)
        expect("scratch match refuses postgres",
               scratch_sqlite_mismatch(
                   "postgresql", "atom", root / "scratch.sqlite3",
                   root) is not None)
        expect("scratch match refuses :memory:",
               scratch_sqlite_mismatch(
                   "sqlite", ":memory:", root / "scratch.sqlite3",
                   root) is not None)
        expect("scratch match refuses another file",
               scratch_sqlite_mismatch(
                   "sqlite", str(root / "other.sqlite3"),
                   root / "scratch.sqlite3", root) is not None)
        expect("scratch match refuses outside workdir",
               scratch_sqlite_mismatch(
                   "sqlite", str(root.parent / "scratch.sqlite3"),
                   root.parent / "scratch.sqlite3", root) is not None)

        # Connection guard: refuses a non-loopback peer WITHOUT dialling it.
        guard = _LoopbackGuard().install()
        try:
            refused = False
            try:
                socket.create_connection(("192.0.2.1", 9), timeout=0.01)
            except NonLoopbackNetwork:
                refused = True
            expect("network guard refuses non-loopback connect", refused)
            expect("network guard records the attempt",
                   guard.blocked
                   and guard.blocked[0]["host"] == "192.0.2.1")

            refused = False
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.connect(("198.51.100.7", 9))
            except NonLoopbackNetwork:
                refused = True
            finally:
                probe.close()
            expect("network guard refuses raw socket connect", refused)
        finally:
            guard.restore()
        # Restored: the original create_connection is back (blocked list is
        # evidence only, so a fresh direct call must NOT raise our error).
        expect("network guard restores",
               socket.create_connection.__name__ != "guarded_create_connection")
        expect("network guard evidence survives restore",
               guard.observation()["guard_installed"] is True)

    expect("model aliases base/tag",
           model_aliases("llama3.1:8b") == {"llama3.1:8b", "llama3.1"})
    expect("model aliases drop vendor path",
           "llama3.1:8b" in model_aliases("ollama/llama3.1:8b"))

    with tempfile.TemporaryDirectory(prefix="team05-selftest-") as td:
        td_path = Path(td)
        missing = td_path / "missing.sqlite3"
        try:
            verify_pristine_sqlite(missing, ("t",))
            expect("fresh verifier rejects missing file", False)
        except FreshnessError:
            expect("fresh verifier rejects missing file", True)

        db = td_path / "fresh.sqlite3"
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE t (x INTEGER)")
        con.commit()
        con.close()
        try:
            fp = verify_pristine_sqlite(db, ("t",))
            expect("fresh verifier accepts empty DB",
                   fp["total_rows"] == 0 and fp["integrity_check"] == "ok")
        except FreshnessError as exc:
            print(f"       unexpected: {exc}")
            expect("fresh verifier accepts empty DB", False)

        con = sqlite3.connect(str(db))
        con.execute("INSERT INTO t (x) VALUES (1)")
        con.commit()
        con.close()
        try:
            verify_pristine_sqlite(db, ("t",))
            expect("fresh verifier rejects written DB", False)
        except FreshnessError:
            expect("fresh verifier rejects written DB", True)

    base: Dict[str, Any] = {
        "scheduler": {
            "registered": True,
            "registered_once": True,
            "trace": [{"name": n} for n in _SCHEDULER_TRACE_ORDER],
            "pass_gate_locked": True,
            "notification_loop_bound": True,
            "certify_on_worker_thread": True,
            "certify_thread": "asyncio_0",
            "main_thread": "MainThread",
            "sleep_seconds": 30.1,
            "pass_completed": True,
            "last_run_sweep_ran": True,
            "last_run_keys": ["sweep", "readiness", "at"],
        },
        "dispatch": {
            "non_local_clients": [],
            "scheduler_handler_count": 1,
            "handler_count": 1,
            "handler_clients": ["ollama"],
            "handler_async_clients": ["ollama"],
            "policy_mode": "selected",
            "policy_allowed": ["ollama"],
            "policy_denies_cloud": True,
            "alignment_chat_fn_entries": [True],
            "served_routes": [
                {"provider": "ollama", "model": "llama3.1:8b"} for _ in range(18)
            ],
            "echoed_models": ["llama3.1:8b"] * 18,
            "attempts": [
                {"temperature": 0.0, "last_used_provider": "ollama"}
                for _ in range(18)
            ],
            "expected_generations": 18,
            "pulled_models": ["llama3.1:8b"],
            "running_models": ["llama3.1:8b"],
        },
        "sweep": {
            "ran": True,
            "green": True,
            "evidence_complete": True,
            "invalid_judgments": [],
            "score_count": 9,
            "expected_score_count": 9,
        },
        "findings": {
            "rows": [
                {"flag_key": k, "state": "approval", "verdict": "enable",
                 "mode": "approve", "decided_at": None}
                for k in ("skill_trust", "allocator_integrity",
                          "org_privileges")
            ],
            "flag_values": {
                "skill_trust": False,
                "allocator_integrity": False,
                "org_privileges": False,
            },
            "pending_view_count": 3,
            "expected_flag_keys": [
                "skill_trust", "allocator_integrity", "org_privileges"],
            "notifications": ["approval_needed"],
        },
        "isolation": {
            "exact_scratch_db": True,
            "live_db_not_opened": True,
            "opened_live_paths": [],
            "sqlite_rejected": [],
            "protected_changes": [],
            "path_resolution": {"ok": True, "checked": [],
                                "mismatches": [], "not_loaded": []},
            "protected_write_refusals": {"guard_installed": True,
                                         "refused": []},
            "fresh_before_seed": True,
            "proxy_env_remaining": {},
            "database_destination": {"ok": True, "reasons": []},
            "network": {"guard_installed": True, "blocked": [],
                        "peers": [{"url": DEFAULT_OLLAMA_BASE,
                                   "peer": "127.0.0.1"}]},
        },
        "approval_control": {
            "ran": True,
            "copy_inside_workdir": True,
            "copy_differs_from_primary": True,
            "primary_unchanged": True,
            "decision_applied": True,
            "approved_flag": "skill_trust",
            "decision": {"flag_key": "skill_trust", "state": "applied"},
            "flag_values_after_approve": {
                "skill_trust": True,
                "allocator_integrity": False,
                "org_privileges": False,
            },
            "states_after_approve": {
                "skill_trust": "applied",
                "allocator_integrity": "approval",
                "org_privileges": "approval",
            },
        },
    }
    qualified = classify_observations(base)
    expect("classify: complete green -> qualified",
           qualified["verdict"] == "qualified" and qualified["exit_code"] == 0)

    negative = json.loads(json.dumps(base))
    negative["sweep"].update(green=False, evidence_complete=False,
                             invalid_judgments=[{"key": "x"}])
    negative["findings"].update(rows=[], notifications=[], pending_view_count=0)
    negative["approval_control"] = {"ran": False,
                                    "skip_reason": "no pending rows"}
    result = classify_observations(negative)
    expect("classify: incomplete evidence -> negative",
           result["verdict"] == "negative" and result["exit_code"] == 2)

    fabricated = json.loads(json.dumps(negative))
    fabricated["findings"]["rows"] = base["findings"]["rows"]
    fabricated["findings"]["notifications"] = ["approval_needed"]
    result = classify_observations(fabricated)
    expect("classify: invented rows on incomplete evidence -> failed",
           result["verdict"] == "failed")

    leaked = json.loads(json.dumps(base))
    leaked["dispatch"]["non_local_clients"] = ["openai"]
    result = classify_observations(leaked)
    expect("classify: leaked provider -> failed",
           result["verdict"] == "failed")

    no_echo = json.loads(json.dumps(base))
    no_echo["dispatch"]["echoed_models"] = [None] * 18
    result = classify_observations(no_echo)
    expect("classify: no served identity -> failed",
           result["verdict"] == "failed")

    broken_control = json.loads(json.dumps(base))
    broken_control["approval_control"]["decision_applied"] = False
    broken_control["approval_control"]["flag_values_after_approve"] = {
        "skill_trust": False, "allocator_integrity": False,
        "org_privileges": False}
    result = classify_observations(broken_control)
    expect("classify: failed approval control -> failed",
           result["verdict"] == "failed"
           and "approval_control.decision_applied" in result["failed"])

    proxy_leak = json.loads(json.dumps(base))
    proxy_leak["isolation"]["proxy_env_remaining"] = {"HTTPS_PROXY": "x"}
    result = classify_observations(proxy_leak)
    expect("classify: surviving proxy env -> failed",
           result["verdict"] == "failed"
           and "isolation.proxy_env_cleared" in result["failed"])

    escaped_network = json.loads(json.dumps(base))
    escaped_network["isolation"]["network"]["blocked"] = [
        {"kind": "socket.connect", "host": "203.0.113.5", "port": 443}]
    result = classify_observations(escaped_network)
    expect("classify: non-loopback connection -> failed",
           result["verdict"] == "failed"
           and "isolation.loopback_only_network" in result["failed"])

    # A protected live-tree change is a HARD failure, never "unknown".
    protected = json.loads(json.dumps(base))
    protected["isolation"]["protected_changes"] = [
        str(_backend_dir() / "data" / "byok_config.json")]
    result = classify_observations(protected)
    expect("classify: protected file change -> failed",
           result["verdict"] == "failed"
           and result["exit_code"] == EXIT_FAILED
           and "isolation.protected_files_unchanged" in result["failed"])

    wrong_paths = json.loads(json.dumps(base))
    wrong_paths["isolation"]["path_resolution"] = {
        "ok": False,
        "mismatches": [{"module": "core.byok_endpoints",
                        "attribute": "BYOK_KEYS_FILE",
                        "resolved": str(_backend_dir() / "data" / "byok_keys.json"),
                        "expected": "scratch"}],
        "not_loaded": [],
    }
    result = classify_observations(wrong_paths)
    expect("classify: unproven scratch paths -> failed",
           result["verdict"] == "failed"
           and "isolation.scratch_paths_resolved" in result["failed"])

    refused_write = json.loads(json.dumps(base))
    refused_write["isolation"]["protected_write_refusals"] = {
        "guard_installed": True,
        "refused": [{"path": str(_backend_dir() / "data" / "byok_keys.json"),
                     "operation": "open(mode='w')"}],
    }
    result = classify_observations(refused_write)
    expect("classify: refused protected write -> failed",
           result["verdict"] == "failed"
           and "isolation.no_protected_write_attempt" in result["failed"])

    with tempfile.TemporaryDirectory(prefix="team05-selftest-") as td:
        root = Path(td)
        secret = root / "byok_keys.json"
        secret.write_text("{}")
        guard = _ProtectedPathGuard([secret]).install()
        try:
            refused = False
            try:
                secret.write_text("tampered")
            except ProtectedPathWrite:
                refused = True
            expect("protected guard refuses Path.write_text", refused)
            expect("protected guard leaves the file intact",
                   secret.read_text() == "{}")
            replaced = root / "incoming.json"
            replaced.write_text("{}")
            refused = False
            try:
                os.replace(replaced, secret)
            except ProtectedPathWrite:
                refused = True
            expect("protected guard refuses os.replace", refused)
            scratch = root / "scratch.json"
            scratch.write_text("ok")
            expect("protected guard allows scratch writes",
                   scratch.read_text() == "ok")
            expect("protected guard records the attempts",
                   len(guard.observation()["refused"]) == 2)
        finally:
            guard.restore()
        expect("protected guard restores builtins.open",
               Path(secret).open("r").read() == "{}")

    resolved = verify_scratch_path_resolution(
        {
            "byok_config": Path("/tmp/scratch/byok_config.json"),
            "byok_keys": Path("/tmp/scratch/byok_keys.json"),
        },
        {"core.byok_endpoints": SimpleNamespace(
            BYOK_CONFIG_FILE="/tmp/scratch/byok_config.json",
            BYOK_KEYS_FILE="/tmp/scratch/byok_keys.json")},
    )
    expect("resolution proof accepts matching constants", resolved["ok"])
    mismatched = verify_scratch_path_resolution(
        {
            "byok_config": Path("/tmp/scratch/byok_config.json"),
            "byok_keys": Path("/tmp/scratch/byok_keys.json"),
        },
        {"core.byok_endpoints": SimpleNamespace(
            BYOK_CONFIG_FILE="/tmp/scratch/byok_config.json",
            BYOK_KEYS_FILE="/tmp/live/byok_keys.json")},
    )
    expect("resolution proof reports a live-tree constant",
           not mismatched["ok"]
           and mismatched["mismatches"][0]["resolved"]
           == os.path.realpath("/tmp/live/byok_keys.json"))


    print("")
    if failures:
        print(f"SELF-TEST FAILED ({len(failures)})")
        return 1
    print("SELF-TEST PASSED")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded, opt-in TEAM-05 live qualification against LOCAL Ollama."
        ),
    )
    parser.add_argument("--run-live", action="store_true",
                        help="actually run the qualification (opt-in)")
    parser.add_argument("--self-test", action="store_true",
                        help="run offline logic checks; no network, no run")
    parser.add_argument("--model", default=None,
                        help=f"pulled Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--ollama-base-url", default=None,
                        help=f"loopback Ollama URL "
                             f"(default: {DEFAULT_OLLAMA_BASE})")
    parser.add_argument("--workdir", default=None,
                        help="empty directory for evidence (default: mkdtemp)")
    parser.add_argument("--request-timeout", type=float, default=180.0,
                        help="per-request Ollama timeout seconds (default 180)")
    parser.add_argument("--probe-timeout", type=float, default=10.0,
                        help="preflight HTTP timeout seconds (default 10)")
    parser.add_argument("--budget-seconds", type=float, default=3600.0,
                        help="overall scheduler-pass budget (default 3600)")
    parser.add_argument("--no-warm", action="store_true",
                        help="skip the preflight model warm-up")
    return parser


def _write_evidence(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _build_parser().parse_args(argv)

    if args.self_test:
        return _self_test()

    model = (args.model or os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL).strip()
    base_url = (args.ollama_base_url or os.getenv("OLLAMA_BASE_URL")
                or DEFAULT_OLLAMA_BASE).strip()
    replay_args = ["--run-live", "--model", model,
                   "--ollama-base-url", base_url]
    if args.workdir:
        replay_args += ["--workdir", args.workdir]
    if args.request_timeout != 180.0:
        replay_args += ["--request-timeout", str(args.request_timeout)]
    if args.budget_seconds != 3600.0:
        replay_args += ["--budget-seconds", str(args.budget_seconds)]
    if args.no_warm:
        replay_args.append("--no-warm")
    replay = _replay_command(replay_args)

    if not args.run_live:
        print("TEAM-05 live qualification is OPT-IN and did not run.")
        print("")
        print("It performs the documented 18-call local sweep (3 scenarios x")
        print("3 structures x 2 calls) and drives the production scheduler")
        print("loop for one 30 s tick against a disposable SQLite file.")
        print("Nothing is sent to a cloud provider.")
        print("")
        print(f"replay (after `ollama serve` + `ollama pull {model}`):")
        print(f"  {replay}")
        print("")
        print("Offline logic checks: --self-test")
        return EXIT_NOT_OPTED_IN

    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") \
            or os.getenv("CI"):
        print("refusing to run under pytest/CI: this is a live local run")
        return EXIT_PRECONDITION
    if not is_loopback_url(base_url):
        print(f"refusing non-loopback OLLAMA_BASE_URL: {base_url}")
        return EXIT_PRECONDITION

    # Workdir must be new/empty so evidence cannot mix with a previous run.
    if args.workdir:
        workdir = Path(args.workdir).expanduser().resolve()
        data_dir = (_backend_dir() / "data").resolve()
        if workdir == data_dir or data_dir in workdir.parents:
            print(f"refusing workdir inside the live data tree: {workdir}")
            return EXIT_PRECONDITION
        if workdir.exists() and any(workdir.iterdir()):
            print(f"refusing non-empty workdir: {workdir}")
            return EXIT_PRECONDITION
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        workdir = Path(tempfile.mkdtemp(prefix="atom-team05-live-"))

    existing_db = workdir / "team05_live.sqlite3"
    if existing_db.exists():
        print(f"refusing pre-existing scratch DB: {existing_db}")
        return EXIT_PRECONDITION

    protected_before = _protected_snapshot()
    # Populated by the drive block with the production modules' ACTUAL
    # resolved paths (see _isolation_now).
    path_resolution: Dict[str, Any] = {}
    # Install the enforcement guards BEFORE anything can dial, open or write:
    # the socket guard refuses non-loopback peers, the SQLite guard refuses
    # any file outside the scratch workdir (unconditionally, before connect),
    # and the protected-path guard refuses writes to the live tree (so a
    # module that resolved a default path cannot clobber credentials).
    protected_guard = _ProtectedPathGuard(_protected_paths()).install()
    loopback_guard = _LoopbackGuard().install()
    sqlite_tracker = _install_sqlite_open_tracker(workdir)
    _LOOPBACK_PEERS.clear()
    live_sqlite = _live_sqlite_paths()
    evidence: Dict[str, Any] = {
        "qualification": "team05-live-org-politics-scheduler",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "workdir": str(workdir),
        "model_requested": model,
        "ollama_base_url": base_url,
        "ollama_sdk_base_url": _openai_compatible_base(base_url),
        "replay_command": replay,
        "exit_code": EXIT_FAILED,
        "verdict": "failed",
    }

    # ---- environment isolation BEFORE importing core -------------------
    db_env_inherited = _scrub_db_env()
    scrubbed = _scrub_provider_env()
    paths = _install_isolation_env(
        workdir, base_url, model, args.request_timeout)
    evidence["isolation"] = {
        "env_scrubbed": scrubbed,
        "db_env_inherited": db_env_inherited,
        "proxy_env_remaining": _remaining_proxy_env(),
        "network": loopback_guard.observation(),
        "db_path": str(paths["db"]),
        "byok_config": str(paths["byok_config"]),
        "byok_keys": str(paths["byok_keys"]),
        "byok_encryption_key": str(paths["byok_enc_key"]),
        "catalog": str(paths["catalog"]),
        "pricing_cache": str(paths["pricing"]),
        "pair_memos": str(paths["pair_memos"]),
        "drift_state": str(paths["drift_state"]),
        "provider_policy": os.environ["ATOM_LLM_PROVIDER_POLICY"],
    }

    def _isolation_now() -> Dict[str, Any]:
        protected_after = _protected_snapshot()
        changed = _changed_protected_paths(protected_before, protected_after)
        opened_live = sorted(set(sqlite_tracker.opened) & live_sqlite)
        return {
            "protected_after": protected_after,
            "protected_changes": changed,
            "opened_sqlite_paths": sorted(set(sqlite_tracker.opened)),
            "opened_live_paths": opened_live,
            "sqlite_rejected": list(sqlite_tracker.rejected),
            "live_db_not_opened": not opened_live,
            "live_db_unchanged": not changed,
            # Observed resolution of the production modules, not the declared
            # strings above. Captured while the seams are active (see the
            # drive block); when the run aborted before that, report "not
            # captured" instead of pretending a default is a mismatch.
            "path_resolution": (
                dict(path_resolution)
                if path_resolution else {
                    "checked": [], "mismatches": [], "not_loaded": [],
                    "ok": None, "captured": False,
                }),
            "protected_write_refusals": protected_guard.observation(),
        }

    def finish(code: int, verdict: str, **extra: Any) -> int:
        evidence.update(extra)
        evidence["exit_code"] = code
        evidence["verdict"] = verdict
        evidence.setdefault("isolation", {})
        try:
            sqlite_tracker.restore()
        except Exception:  # noqa: BLE001
            pass
        try:
            loopback_guard.restore()
        except Exception:  # noqa: BLE001
            pass
        try:
            protected_guard.restore()
        except Exception:  # noqa: BLE001
            pass
        isolation_now = _isolation_now()
        evidence["isolation"].update({
            "protected_before": protected_before,
            "protected_after": isolation_now.pop("protected_after"),
            "protected_changes": isolation_now["protected_changes"],
            "opened_sqlite_paths": isolation_now["opened_sqlite_paths"],
            "opened_live_paths": isolation_now["opened_live_paths"],
            "sqlite_rejected": isolation_now["sqlite_rejected"],
            "live_db_not_opened": isolation_now["live_db_not_opened"],
            "live_db_unchanged": isolation_now["live_db_unchanged"],
            "path_resolution": isolation_now["path_resolution"],
            "protected_write_refusals":
                isolation_now["protected_write_refusals"],
            "network": loopback_guard.observation(),
            "proxy_env_remaining": _remaining_proxy_env(),
        })

        try:
            _write_evidence(paths["evidence"], evidence)
        except Exception as exc:  # noqa: BLE001
            print(f"could not write evidence: {exc}")
        print("")
        print(f"verdict: {verdict} (exit {code})")
        if evidence.get("check_summary"):
            print(f"checks:  {evidence['check_summary']}")
        print(f"workdir: {workdir}")
        print(f"evidence: {paths['evidence']}")
        print(f"replay:  {replay}")
        return code

    try:
        _assert_scratch_db_identity(paths["db"], workdir)

        # ---- preflight: local runtime + pulled model --------------------
        preflight = _probe_ollama(base_url, args.probe_timeout)
        evidence["preflight"] = preflight
        pulled_aliases = set()
        for name in preflight["pulled"]:
            pulled_aliases |= model_aliases(name)
        if not (model_aliases(model) & pulled_aliases):
            return finish(
                EXIT_PRECONDITION, "precondition_failed",
                precondition=(
                    f"model {model!r} is not pulled; /api/tags reports "
                    f"{preflight['pulled']}"),
            )

        root = preflight["root"]
        if not args.no_warm:
            evidence["preflight"]["warmup"] = _warm_model(
                root, model, args.request_timeout)

        # ---- import core AFTER isolation is installed -------------------
        _ensure_backend_on_path()
        import core.database as database
        import core.llm.byok_handler as byok
        import core.dynamic_pricing_fetcher as dpf
        import core.llm.model_provenance as provenance
        import core.org_politics_automation as automation
        from core.models_registration import Base

        # ---- engine destination proof BEFORE any connection -------------
        # database.DATABASE_URL is only a string; the engine's url and the
        # SessionLocal bind are what actually dial.  Prove all three point at
        # the exact fresh scratch file, and refuse any non-scratch SQLite
        # target before create_all performs the first connect.
        destination = verify_database_destination(
            database, paths["db"], workdir)
        evidence["isolation"]["database_url"] = database.DATABASE_URL
        evidence["isolation"]["database_destination"] = destination
        if not destination["ok"]:
            raise PreconditionError(
                "core.database destination is not the scratch database: "
                + "; ".join(destination["reasons"]))
        evidence["isolation"]["exact_scratch_db"] = True

        # Create schema, then PROVE it is fresh before any seed write.
        if paths["db"].exists():
            raise FreshnessError(
                f"scratch DB appeared before schema creation: {paths['db']}")
        Base.metadata.create_all(database.engine)
        fresh = verify_pristine_sqlite(paths["db"], _EXPECTED_TABLES)
        evidence["fresh_sqlite"] = {"before_seed": fresh}
        evidence["isolation"]["fresh_before_seed"] = True
        evidence["isolation"]["fresh_before_detail"] = fresh


        # ---- synthetic seed (first write) -------------------------------
        from core.models import Tenant, Workspace
        from core.org_telemetry_service import AgentOrgTelemetryService

        db = database.SessionLocal()
        try:
            db.add(Tenant(
                id="default",
                name="TEAM-05 live qualification",
                subdomain="team05-live-qualification",
            ))
            db.add(Workspace(
                id="org-politics-sweep",
                name="Org politics sweep",
                tenant_id="default",
            ))
            svc = AgentOrgTelemetryService(db)
            for i in range(15):
                svc.emit(
                    "fleet_recruit",
                    actor_agent_id="qualification-coordinator",
                    target_agent_id=f"synthetic-specialist-{i}",
                )
            db.commit()
        finally:
            db.close()

        seeded_counts = _sqlite_table_counts(
            paths["db"],
            ("tenants", "workspaces", "agent_org_events",
             "org_politics_actions"),
        )
        expected_seed = {
            "tenants": 1,
            "workspaces": 1,
            "agent_org_events": 15,
            "org_politics_actions": 0,
        }
        if seeded_counts != expected_seed:
            raise FreshnessError(
                f"synthetic seed mismatch: {seeded_counts} != {expected_seed}")
        # Observed fingerprint (never a desired value): the file changed from
        # the pristine state, and how, is recorded as measured.
        evidence["fresh_sqlite"]["after_seed"] = {
            "table_counts": seeded_counts,
            "fingerprint": file_fingerprint(paths["db"]),
            "observed": True,
        }


        # Automation module state is process-local; the process exits after.
        automation.set_automation_config(
            mode="approve", interval_min=MIN_INTERVAL_MIN)
        automation._last_run = {}
        automation._last_notified = {}
        automation._resolver_cache = {}
        automation._automation_task = None
        byok.BYOKHandler._OLLAMA_DOWN_MEMO = None
        byok.BYOKHandler.invalidate_provider_failures()

        seams = _Seams(workdir, model, expected=18)
        seams.install(automation, byok, dpf, provenance)
        # Capture the seams' redirection while it is still active. Reading it
        # after seams.restore() would compare the RESTORED defaults and report
        # a false mismatch.
        path_resolution.update(verify_scratch_path_resolution(paths))
        try:
            drive = _drive_scheduler(automation, seams, args.budget_seconds)
        finally:
            # Re-check at the end of the pass: a module imported mid-run must
            # also have resolved into the workdir.
            path_resolution.update(verify_scratch_path_resolution(paths))
            seams.restore()

        # ---- derive observations ---------------------------------------
        sweep_result = (
            seams.alignment_results[0] if seams.alignment_results else {})
        # Secondary read of the loop's own last_run view.
        last_run = dict(getattr(automation, "_last_run", {}) or {})
        sweep_view = dict(last_run.get("sweep") or {})
        sweep = {
            "ran": bool(sweep_result.get("ran", sweep_view.get("ran"))),
            "green": bool(sweep_result.get("green", sweep_view.get("green"))),
            "evidence_complete": bool(
                sweep_result.get(
                    "evidence_complete", sweep_view.get("evidence_complete"))),
            "max_gap": sweep_result.get("max_gap", sweep_view.get("max_gap")),
            "skipped_reason": sweep_result.get(
                "skipped_reason", sweep_view.get("skipped_reason")),
            "invalid_judgments": sweep_result.get(
                "invalid_judgments", sweep_view.get("invalid_judgments")),
            "scores": sweep_result.get("scores"),
            "score_count": len(sweep_result.get("scores") or {}),
            "expected_score_count": seams.expected // 2,
        }

        # A fresh engine reads the durable rows.
        findings = _collect_findings(paths["db"])
        findings["notifications"] = [
            n["type"] for n in seams.notifications
        ]

        isolation_observation = _isolation_now()
        # Re-derived, not asserted: the engine-destination gate above is what
        # makes this true, and its observation is recorded in evidence.
        isolation_observation["exact_scratch_db"] = bool(destination.get("ok"))
        isolation_observation["database_destination"] = destination
        isolation_observation["fresh_before_seed"] = bool(
            (evidence.get("fresh_sqlite") or {}).get("before_seed"))
        isolation_observation["db_path"] = str(paths["db"])
        isolation_observation["network"] = loopback_guard.observation()
        isolation_observation["proxy_env_remaining"] = _remaining_proxy_env()


        try:
            running_after = _probe_ollama(
                base_url, args.probe_timeout)["running"]
        except PreconditionError as exc:
            running_after = []
            evidence["post_run_probe_error"] = str(exc)
        handler_records = list(seams.handlers)
        scheduler_handlers = [
            h for h in handler_records
            if h.get("workspace_id") == "org-politics-sweep"
        ]
        non_local: List[str] = []
        for h in handler_records:
            non_local.extend(h.get("non_local_clients") or [])
            non_local.extend(h.get("env_key_providers") or [])

        certify_entries = [
            t for t in seams.trace if t["name"] == "certify"]
        worker_certify = bool(
            certify_entries
            and certify_entries[0]["thread"] != threading.main_thread().name)
        sleep_seconds = None
        if seams.pass_started_at is not None and drive.get(
                "first_registration") is not None:
            sleep_seconds = round(
                seams.pass_started_at - drive["first_registration"], 3)

        observations = {
            "scheduler": {
                "registered": bool(drive.get("registered")),
                "registered_detail": drive.get("first_registration"),
                "registered_once": bool(drive.get("registered_once")),
                "registration_detail": drive.get("error"),
                "trace": seams.trace,
                "pass_gate_locked": bool(
                    certify_entries
                    and certify_entries[0].get("gate_locked")),
                "notification_loop_bound": bool(
                    certify_entries
                    and certify_entries[0].get("notification_loop_bound")),
                "certify_on_worker_thread": worker_certify,
                "certify_thread": (
                    certify_entries[0]["thread"] if certify_entries else None),
                "main_thread": threading.main_thread().name,
                "sleep_seconds": sleep_seconds,
                "pass_completed": seams.pass_completed.is_set(),
                "pass_detail": {
                    "timed_out": drive.get("timed_out"),
                },
                "last_run_sweep_ran": bool(sweep_view.get("ran")),
                "last_run_keys": sorted(last_run.keys()),
            },
            "dispatch": {
                "handler_count": len(handler_records),
                "scheduler_handler_count": len(scheduler_handlers),
                "handler_records": handler_records,
                "handler_clients": (
                    scheduler_handlers[0].get("clients")
                    if scheduler_handlers else None),
                "handler_async_clients": (
                    scheduler_handlers[0].get("async_clients")
                    if scheduler_handlers else None),
                "non_local_clients": sorted(set(non_local)),
                "policy_mode": (
                    scheduler_handlers[0].get("policy_mode")
                    if scheduler_handlers else None),
                "policy_allowed": (
                    scheduler_handlers[0].get("policy_allowed")
                    if scheduler_handlers else None),
                "policy_denies_cloud": (
                    not bool(scheduler_handlers[0].get("allows_cloud"))
                    if scheduler_handlers else None),
                "alignment_chat_fn_entries": [
                    t.get("chat_fn_is_none") for t in seams.trace
                    if t["name"] == "alignment_verdict"],
                "attempts": seams.attempts,
                "served_routes": seams.served_routes,
                "echoed_models": seams.echoed_models,
                "expected_generations": seams.expected,
                "pulled_models": preflight["pulled"],
                "running_models": running_after,
            },
            "sweep": sweep,
            "findings": findings,
            "isolation": isolation_observation,
        }

        # Copied-database approval control: run on a COPY whenever there are
        # pending rows, then feed it to the classifier so a broken
        # apply_pending_decision fails the qualification (not just evidence).
        approval_control: Dict[str, Any] = {}
        if findings["rows"]:
            try:
                approval_control = _approval_control(paths["db"], workdir)
            except Exception as exc:  # noqa: BLE001 - recorded as a failure
                approval_control = {
                    "ran": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
        else:
            approval_control = {
                "ran": False,
                "skip_reason": "no pending rows to decide",
            }
        observations["approval_control"] = approval_control
        evidence["approval_control_ok"] = (
            bool(approval_control.get("decision_applied")
                 and approval_control.get("primary_unchanged")
                 and approval_control.get("copy_inside_workdir"))
            if approval_control.get("ran") else None
        )

        classification = classify_observations(observations)

        evidence.update({
            "sweep": sweep,
            "scheduler": observations["scheduler"],
            "dispatch": {
                k: v for k, v in observations["dispatch"].items()
                if k != "attempts"
            },
            "dispatch_attempts": seams.attempts,
            "findings": findings,
            "checks": classification["checks"],
            "check_summary": classification["summary"],
            "failed_checks": classification["failed"],
            "approval_control": approval_control,
            "drift_state": str(paths["drift_state"]),
        })
        if paths["drift_state"].exists():
            try:
                evidence["drift_baselines"] = json.loads(
                    paths["drift_state"].read_text())
            except Exception:  # noqa: BLE001
                evidence["drift_baselines"] = "unreadable"

        if seams.safety_abort:
            return finish(EXIT_SAFETY_ABORT, "safety_abort",
                          safety_abort=seams.safety_abort)
        if drive.get("timed_out"):
            return finish(EXIT_FAILED, "failed",
                          failure="scheduler pass exceeded budget")
        if drive.get("error"):
            return finish(EXIT_FAILED, "failed",
                          failure=drive["error"])
        return finish(classification["exit_code"], classification["verdict"])

    except PreconditionError as exc:
        return finish(EXIT_PRECONDITION, "precondition_failed",
                      precondition=str(exc))
    except FreshnessError as exc:
        return finish(EXIT_FAILED, "failed", freshness_error=str(exc))
    except SafetyAbort as exc:
        return finish(EXIT_SAFETY_ABORT, "safety_abort", safety_abort=str(exc))
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        return finish(
            EXIT_FAILED, "failed",
            failure=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )


if __name__ == "__main__":
    raise SystemExit(main())
