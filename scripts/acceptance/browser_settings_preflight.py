#!/usr/bin/env python3
"""Preflight for the WA-075 signed-in settings acceptance.

This driver launches nothing and writes nothing unless ``--report`` is given.
It answers one question before any browser runs:

    Is this machine able to prove WA-075 honestly, and which of the five
    settings tabs can actually be exercised?

Reused existing infrastructure (no new engine, no installs):

  * ``scripts/acceptance/validate_local_world.py`` - the integrated-local
    world contract (world under the configured ``acceptance_worlds`` root,
    live-DB refusal, port checks, free-space floor, marker/pid safety).
  * ``core.world_storage_guard`` - the worlds-root volume/layout preflight and
    maintenance interlock. ``ATOM_WORLD_STORAGE_BYPASS`` is refused outright.
  * the workspace's own ``frontend-nextjs/node_modules`` and the installed
    Google Chrome - nothing is downloaded.

Hard rules encoded here (see AGENTS.md):

  * never the live dev database or data tree;
  * never a real credential - the scratch admin password is read from a 0600
    file (path only is recorded, never the value);
  * never an external model provider - the launch contract pins
    ``ATOM_LOCAL_ONLY`` and the acceptance world is started with provider
    credential variables blanked (see the companion work order document).

Exit codes: 0 environment ready, 2 environment blocker, 3 environment ready
but at least one tab is expected to be blocked by a known product gap.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
LIVE_DB = (BACKEND / "data" / "atom.db").resolve()
LIVE_MARKERS = ("/whole-app-world/data/atom.db",)

#: ``core.world_storage_guard`` relocates its config, lock and runner paths
#: together when this is set. The preflight must resolve the config the same
#: way, or the guard can validate one root while this report validates another.
STORAGE_PATHS_ENV = "ATOM_WORLD_STORAGE_PATHS"

# Provider/model credential variables that must not reach the acceptance
# world. Setting them to an empty string in the parent shell is enough:
# python-dotenv never overwrites an already-present key, so backend/.env
# values are not loaded on top.
PROVIDER_CREDENTIAL_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
    "GROQ_API_KEY", "TOGETHER_API_KEY", "OPENCODE_API_KEY",
    "MISTRAL_API_KEY", "XAI_API_KEY",
)

# The five WA-075 tabs and the checks the browser driver records for each.
TAB_CHECKS: Dict[str, List[str]] = {
    "account": [
        "account.page_loads",
        "account.profile_readback",
        "account.two_factor_surface",
        "account.password_change_saved",
        "account.password_reload",
        "account.password_restored",
    ],
    "ai": [
        "ai.page_loads",
        "ai.policy_loads",
        "ai.policy_saved",
        "ai.policy_persisted_reload",
        "ai.policy_restored",
    ],
    "sessions": [
        "sessions.page_loads",
        "sessions.disposable_secondary_session",
        "sessions.list_reflects_live_sessions",
        "sessions.revoke_disposable",
    ],
    "routing": [
        "routing.page_loads",
        "routing.metrics_loaded_from_backend",
        "routing.rendered_matches_payload",
        "routing.refresh_refetches",
        "routing.honest_telemetry_state",
    ],
    "local_models": [
        "local_models.page_loads",
        "local_models.register_saved",
        "local_models.persisted_after_reload",
        "local_models.delete_removed",
        "local_models.no_provider_contact",
    ],
}


class PreflightError(RuntimeError):
    """A refusal that must stop the run before anything is written."""


def _load_validate_module():
    path = REPO / "scripts" / "acceptance" / "validate_local_world.py"
    spec = importlib.util.spec_from_file_location("validate_local_world", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise PreflightError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_storage_guard():
    """Import ``core.world_storage_guard`` from this checkout (no DB, no I/O)."""
    backend = str(BACKEND)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        import core.world_storage_guard as guard
    except Exception as exc:  # pragma: no cover - defensive
        raise PreflightError(
            f"cannot import core.world_storage_guard from {backend}: {exc}"
        ) from exc
    return guard


def storage_config_source(repo: Path = REPO) -> Dict[str, Any]:
    """Resolve the storage config the SAME way ``core.world_storage_guard`` does.

    The guard relocates ``CONFIG_PATH`` (plus its lock and runner records) when
    ``ATOM_WORLD_STORAGE_PATHS`` is set. Reading only
    ``backend/config/world_storage.json`` here let the guard validate the
    relocated root while the preflight validated the checkout's root, so a
    world the guard accepted was still refused (or, worse, the reverse). One
    resolver, one answer: this calls the guard's own ``load_config`` with the
    path the guard itself would use.

    Config is read from OUTSIDE the movable worlds tree by contract; a missing
    config falls back to the guard's historical local root.
    """
    guard = _load_storage_guard()
    relocated = (os.environ.get(STORAGE_PATHS_ENV) or "").strip()
    config_dir = (Path(relocated).expanduser() if relocated
                  else repo / "backend" / "config")
    config_path = config_dir / "world_storage.json"
    try:
        config = guard.load_config(config_path)
    except guard.WorldStorageError as exc:
        raise PreflightError(str(exc)) from exc
    return {
        "config_path": str(config_path),
        "relocated_by_env": bool(relocated),
        "relocation_env": STORAGE_PATHS_ENV if relocated else None,
        "enabled": bool(config.enabled),
        "layout": config.layout,
        "worlds_root": str(Path(config.root).resolve()),
    }


def configured_worlds_root(repo: Path = REPO) -> Path:
    """The worlds root from the canonical configured storage config."""
    return Path(storage_config_source(repo)["worlds_root"])


def check_world_layout(world: Path, repo: Path = REPO) -> Dict[str, Any]:
    """Refuse a world path that could touch the live app or escape the root.

    Pure function: creates nothing, reads no database. Mirrors
    ``validate_local_world.py``'s protected-path rules so a caller can report
    the refusal as data instead of a traceback.
    """
    root = configured_worlds_root(repo)
    world = world.resolve()
    problems: List[str] = []
    protected = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo.resolve(),
        (repo / "backend").resolve(),
        (repo / "backend" / "data").resolve(),
        root,
        (repo / "frontend-nextjs").resolve(),
        (repo / "docs").resolve(),
        (repo / "scripts").resolve(),
    }
    if world in protected:
        problems.append("world is a protected repository/home/worlds-root path")
    if world == root or root not in world.parents:
        problems.append(f"world must live under the configured worlds root {root}")
    try:
        live = (repo / "backend" / "data").resolve()
    except OSError:
        problems.append("cannot resolve the live data tree")
        live = None
    if live is not None and (world == live or live in world.parents):
        # A world under backend/data is only acceptable when it is also under
        # the configured worlds root (the historical local layout).
        if root not in world.parents:
            problems.append("world is inside the live data tree")
    if world.name.endswith(".db"):
        problems.append("world must be a directory, not a database file")
    return {
        "world": str(world),
        "configured_worlds_root": str(root),
        "ok": not problems,
        "problems": problems,
        "database": str(world / "atom.db"),
        "live_database": str(LIVE_DB),
        "database_is_live_dev_db": str(world / "atom.db") == str(LIVE_DB),
    }


def check_database_isolation(db_url: Optional[str], repo: Path = REPO) -> Dict[str, Any]:
    """Refuse a caller-supplied DATABASE_URL aimed at the live dev database."""
    if not db_url:
        return {"ok": True, "source": "unset", "path": None}
    if db_url.startswith("sqlite:///"):
        raw = db_url[len("sqlite:///"):]
        path = Path(raw).expanduser().resolve()
        live = (repo / "backend" / "data").resolve()
        inside_live = path == live or live in path.parents
        return {
            "ok": not inside_live,
            "source": "sqlite",
            "path": str(path),
            "problem": (
                "DATABASE_URL points inside the live backend/data tree"
                if inside_live else None),
        }
    if any(marker in db_url for marker in LIVE_MARKERS):
        return {
            "ok": False,
            "source": "postgres",
            "path": None,
            "problem": "DATABASE_URL names the isolated whole-app world database",
        }
    return {"ok": True, "source": "postgres", "path": None}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _resolve_playwright_module(frontend_dir: Path) -> Path:
    explicit = (os.environ.get("ATOM_PLAYWRIGHT_MODULE") or "").strip()
    if explicit:
        if explicit.startswith("file://"):
            from urllib.parse import urlparse, unquote
            explicit = unquote(urlparse(explicit).path)
        return Path(explicit).expanduser()
    return frontend_dir / "node_modules" / "playwright" / "index.mjs"


def dependency_report(frontend_dir: Path) -> Dict[str, Any]:
    """Report the runtime pieces a browser capture needs; installs nothing."""
    chrome = Path("/Applications/Google Chrome.app")
    chrome_exe = (os.environ.get("ATOM_CHROME_EXECUTABLE") or "").strip()
    playwright_mod = _resolve_playwright_module(frontend_dir)
    build_id = frontend_dir / ".next" / "BUILD_ID"
    return {
        "python": sys.version.split()[0],
        "python_modules": {
            "uvicorn": _module_available("uvicorn"),
            "fastapi": _module_available("fastapi"),
            "sqlalchemy": _module_available("sqlalchemy"),
        },
        "node": shutil.which("node"),
        "chrome_app": chrome.is_dir(),
        "chrome_executable": chrome_exe or None,
        "chrome_executable_exists": (Path(chrome_exe).is_file()
                                     if chrome_exe else None),
        "frontend_dir": str(frontend_dir),
        "frontend_node_modules": (frontend_dir / "node_modules").is_dir(),
        "playwright_module": playwright_mod.is_file(),
        "playwright_module_path": str(playwright_mod),
        "playwright_module_source": (
            "ATOM_PLAYWRIGHT_MODULE"
            if os.environ.get("ATOM_PLAYWRIGHT_MODULE") else "frontend_node_modules"),
        "frontend_build_id": build_id.is_file(),
        "frontend_env_local": (frontend_dir / ".env.local").is_file(),
        "nextauth_secret_env": bool(os.environ.get("NEXTAUTH_SECRET")),
    }


def _guard_check() -> Dict[str, Any]:
    """Run the existing worlds-root guard. A bypass is never acceptable."""
    if os.environ.get("ATOM_WORLD_STORAGE_BYPASS"):
        return {
            "ok": False,
            "reason": "ATOM_WORLD_STORAGE_BYPASS is set; unset it and let the "
                      "guard check the worlds root",
        }
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "core.world_storage_guard", "check"],
            cwd=str(BACKEND), capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "reason": f"guard could not run: {exc}"}
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    detail = stdout or stderr
    hint = None
    if "worlds root does not exist" in detail:
        hint = (
            "worlds root is missing in this checkout; use the existing "
            "integrated-local launcher, which creates the configured LOCAL "
            "root only after its own validation (never hand-create it)")
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "reason": None if proc.returncode == 0 else (hint or (detail.splitlines()[-1] if detail else "guard refused")),
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def _port_free(port: int) -> bool:
    module = _load_validate_module()
    return not module.port_open(port)


def _capability_report(
    deps: Dict[str, Any],
    guard: Dict[str, Any],
    world: Dict[str, Any],
    *,
    stack_running: bool,
) -> Dict[str, Dict[str, Any]]:
    """Which tab can be proven, and what would block it.

    Anything not statically knowable (the admin role's band, whether the
    installation env manages the provider policy, whether the session
    registry has rows) stays a runtime check and is labelled as such.
    """
    frontend_ready = (
        deps["playwright_module"]
        and (stack_running
             or (deps["frontend_node_modules"] and deps["frontend_build_id"]))
    )
    runtime_ready = (deps["chrome_app"] or bool(deps.get("chrome_executable_exists"))) \
        and bool(deps["node"])
    world_ready = guard.get("ok") and world.get("ok")

    def blocked(reason: str) -> Dict[str, Any]:
        return {"status": "blocked", "reason": reason}

    def ready(note: str) -> Dict[str, Any]:
        return {"status": "ready", "note": note}

    caps: Dict[str, Dict[str, Any]] = {}
    if not (frontend_ready and runtime_ready and world_ready):
        reason = (
            "frontend/playwright not ready" if not frontend_ready
            else "chrome/node not ready" if not runtime_ready
            else "scratch world not ready"
        )
        for tab in TAB_CHECKS:
            caps[tab] = blocked(reason)
        return caps

    caps["account"] = ready(
        "profile + password rotation with restore; the 2FA toggle is probed "
        "read-only (source review: the Next config routes /api/auth/2fa/status "
        "but not setup|enable|disable; the driver confirms at runtime)")
    if os.environ.get("ATOM_LLM_PROVIDER_POLICY"):
        caps["ai"] = blocked(
            "ATOM_LLM_PROVIDER_POLICY is set in the environment; the policy "
            "is installation-managed and the UI save is disabled (PUT 409)")
    else:
        caps["ai"] = ready(
            "provider-policy save/reload/restore (requires workspace_admin+)")
    caps["sessions"] = ready(
        "runtime check: source review finds no backend writer for UserSession "
        "and a Postgres-only query in the Next /api/auth/sessions route; the "
        "driver reports the observed gap instead of faking a list"
        + ("" if (deps.get("nextauth_secret_env") or deps.get("frontend_env_local"))
           else " (NEXTAUTH_SECRET was not visible to this preflight; the "
                "disposable secondary web session may be unavailable)"))
    caps["routing"] = ready(
        "runtime check: /api/chat/routing-stats requires workspace_admin+; "
        "empty telemetry is reported as empty, never filled in")
    caps["local_models"] = ready(
        "disposable provider at an RFC 2606 .invalid host; Discover/Test are "
        "never clicked and no provider connection is attempted")
    return caps


def _free_space_probe(world: Path, minimum_mb: int) -> Dict[str, Any]:
    probe = world
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        free = shutil.disk_usage(str(probe)).free
    except OSError as exc:
        return {"ok": False, "reason": f"cannot read free space at {probe}: {exc}"}
    free_mb = free // (1024 * 1024)
    return {
        "ok": free_mb >= minimum_mb,
        "probe": str(probe),
        "free_mb": free_mb,
        "minimum_mb": minimum_mb,
        "reason": None if free_mb >= minimum_mb else (
            f"only {free_mb} MiB free; the launcher floor is {minimum_mb} MiB"),
    }


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    frontend_dir = Path(args.frontend_dir).expanduser().resolve()
    world_probe = check_world_layout(Path(args.world), REPO)
    db_probe = check_database_isolation(os.environ.get("DATABASE_URL"), REPO)
    deps = dependency_report(frontend_dir)
    guard = _guard_check()
    space = _free_space_probe(Path(args.world).expanduser(), args.min_free_mb)
    ports = {
        str(args.backend_port): _port_free(args.backend_port),
        str(args.frontend_port): _port_free(args.frontend_port),
    }
    if args.stack_running:
        ports_ok = True  # the stack owns these ports by definition
    else:
        ports_ok = all(ports.values())

    blockers: List[str] = []
    if not world_probe["ok"]:
        blockers.extend(world_probe["problems"])
    if not db_probe["ok"]:
        blockers.append(db_probe.get("problem") or "DATABASE_URL is not isolated")
    if not guard.get("ok"):
        blockers.append(guard.get("reason") or "world storage guard refused")
    if not deps["playwright_module"]:
        blockers.append(
            f"Playwright module not found at {deps.get('playwright_module_path')}; "
            "reuse the workspace's installed frontend-nextjs/node_modules or set "
            "ATOM_PLAYWRIGHT_MODULE (no install is performed)")
    if not deps["chrome_app"] and not deps.get("chrome_executable_exists"):
        blockers.append(
            "no browser: Google Chrome.app is not installed and "
            "ATOM_CHROME_EXECUTABLE is unset or missing")
    elif deps.get("chrome_executable") and deps.get("chrome_executable_exists") is False:
        blockers.append(
            f"ATOM_CHROME_EXECUTABLE points at a missing file: "
            f"{deps['chrome_executable']}")
    if not deps["node"]:
        blockers.append("node is not on PATH")
    if not args.stack_running and not deps["frontend_node_modules"]:
        blockers.append(
            f"{frontend_dir}/node_modules is absent; the existing launcher cannot "
            "start the frontend from this tree")
    if not args.stack_running and not deps["frontend_build_id"]:
        blockers.append(
            f"{frontend_dir}/.next/BUILD_ID is absent and --stack-running was "
            "not passed; either serve an already-built frontend or let the "
            "existing integrated-local launcher start one")
    if not ports_ok:
        blockers.append(
            "requested ports are in use: "
            + ", ".join(f"{p}={v}" for p, v in ports.items()))
    if not space["ok"]:
        blockers.append(space["reason"])

    if args.admin_password_file:
        pw = Path(args.admin_password_file).expanduser()
        mode = (pw.stat().st_mode & 0o777) if pw.is_file() else None
        if not pw.is_file():
            blockers.append(f"admin password file does not exist: {pw}")
        elif mode is not None and mode & 0o077:
            blockers.append(
                f"admin password file {pw} is not 0600 (mode {oct(mode)})")
        password_source = {
            "path": str(pw), "mode": oct(mode) if mode is not None else None,
            "value_recorded": False,
        }
    else:
        password_source = {
            "path": None,
            "note": "ATOM_SCOPE_PASSWORD must be supplied to the browser "
                    "driver; never write it to evidence",
        }

    capabilities = _capability_report(
        deps, guard, world_probe, stack_running=args.stack_running)
    expected_blocked = [k for k, v in capabilities.items() if v["status"] == "blocked"]

    return {
        "schema": "atom-wa075-settings-preflight-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(REPO),
        "source": {
            "head": _git("rev-parse", "HEAD"),
            "tracked_dirty": _git("status", "--porcelain=v1",
                                  "--untracked-files=no"),
        },
        "world": world_probe,
        "storage": storage_config_source(REPO),
        "database": db_probe,
        "storage_guard": {k: v for k, v in guard.items() if k != "stdout_tail"},
        "dependencies": deps,
        "ports": ports,
        "free_space": space,
        "stack_running": bool(args.stack_running),
        "admin_password": password_source,
        "provider_credential_env_set": [
            name for name in PROVIDER_CREDENTIAL_ENV if os.environ.get(name)
        ],
        "tabs": TAB_CHECKS,
        "capabilities": capabilities,
        "blockers": blockers,
        "expected_blocked_tabs": expected_blocked,
        "ok": not blockers,
        "next": (
            "environment ready; start/keep the isolated world, then run "
            "scripts/acceptance/browser_settings_acceptance.mjs --out <evidence>"
            if not blockers else
            "resolve blockers; do not bypass the guard and do not install "
            "dependencies"
        ),
    }


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(REPO), capture_output=True, text=True,
            timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--world", required=True,
                    help="scratch world directory under the configured worlds root")
    ap.add_argument("--frontend-dir", default=str(REPO / "frontend-nextjs"),
                    help="served frontend tree (its node_modules/Playwright are reused)")
    ap.add_argument("--backend-port", type=int, default=8105)
    ap.add_argument("--frontend-port", type=int, default=3001)
    ap.add_argument("--admin-password-file",
                    help="0600 file holding the scratch admin password (path only is recorded)")
    ap.add_argument("--min-free-mb", type=int, default=1024,
                    help="disk floor reported here and enforced by the launcher (default 1024)")
    ap.add_argument("--stack-running", action="store_true",
                    help="the world is already serving; skip build-id and port-free checks")
    ap.add_argument("--report", help="write the JSON report here (path only, no secrets)")
    args = ap.parse_args(argv)

    try:
        report = build_report(args)
    except PreflightError as exc:
        print(json.dumps({"ok": False, "blockers": [str(exc)]}, indent=2))
        return 2

    if args.report:
        out = Path(args.report).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))

    if report["blockers"]:
        return 2
    if report["expected_blocked_tabs"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
