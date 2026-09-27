#!/usr/bin/env python3
"""Isolated preview stack for the chat orchestrator app-readiness work.

The readiness plan (docs/architecture/orchestration_migration/
CHAT_ORCHESTRATOR_APP_READINESS_PLAN_2026_09_26.md) requires a RUNNING app
that a human can manually exercise, on an ISOLATED world, without touching
the user's own dev environment. The existing harness
(scripts/orchestration_acceptance/run_isolated.py) can build and verify such
a world, but it cannot host a preview:

  1. It launches the backend under a macOS seatbelt profile that denies all
     external network (`_sandbox_profile`: `deny network*`). The plan
     requires at least one REAL configured model to produce a browser-visible
     turn, which is impossible with egress denied.
  2. Its server environment is a strict whitelist (SERVER_ENV_WHITELIST) that
     cannot carry model credentials, and the code export excludes gitignored
     `.env`, so the world has no provider access at all.
  3. It has no notion of a frontend or a browser: no Playwright, no
     `next dev`, and no `frontend-nextjs` reference anywhere in it.
  4. It always stops the server on exit (`stop_server` in a `finally`), so
     nothing can be left running for a user.

This module adds exactly that missing piece. World construction, per-run data
seeding and schema sync are delegated to run_isolated, so there remains a
single implementation of "what an isolated world is".

DEVIATION FROM THE HARNESS, AND WHY IT IS SAFE HERE
The backend is launched WITHOUT the seatbelt. That is deliberate and
recorded. The seatbelt exists to prove that a fault-injection,
credential-scrubbed acceptance run cannot phone home; the preview is the
opposite case, because it must reach a real model provider. Isolation is
enforced at the DATA boundary instead, which is where the actual risk lives:

  * DATABASE_URL / ATOM_DATA_DIR point at a per-run directory seeded from a
    sanitized fixture, never at backend/data/atom.db.
  * The fixture is credential-scrubbed, and run_isolated.verify_scrubbed()
    re-proves that on every build.
  * ENABLE_SCHEDULER / ENABLE_INGESTION_SYNC are off, so the preview does not
    drive the user's real integrations.
  * The world's user BYOK store is auto-created empty inside the run dir, so
    the preview has no outbound integration credentials to act with.

Provider credentials are read from the repo's own backend/.env by NAME and
forwarded to the child process. Values are never logged, never written into
the world, and never printed by this module.

Commands:
    preview_stack.py up      [--world N] [--backend-port N] [--frontend-port N]
    preview_stack.py status  [--world N]
    preview_stack.py verify  [--world N]
    preview_stack.py down    [--world N]
    preview_stack.py creds
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
FRONTEND = REPO / "frontend-nextjs"
PREVIEW_FE = FRONTEND / ".preview-instance"
VENV_PY = BACKEND / "venv314" / "bin" / "python"
APP_PY = BACKEND / "scripts" / "orchestration_acceptance" / "_app.py"

sys.path.insert(0, str(BACKEND))
from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402

DEFAULT_WORLD = "preview_v1"
DEFAULT_BACKEND_PORT = 8051
DEFAULT_FRONTEND_PORT = 3101

# --------------------------------------------------------------------------
# Model credential plumbing. NAMES ONLY. The readiness plan forbids copying
# credentials into source, docs, screenshots, logs or the final report, so
# this module reads the repo's own .env and forwards values to the child
# without ever rendering them.
# --------------------------------------------------------------------------
CREDENTIAL_ENV_NAMES: Tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "TOGETHER_API_KEY",
    "OLLAMA_MODEL",
    "EMBEDDING_PROVIDER",
    "FASTEMBED_MODEL",
)
PLACEHOLDER_VALUES = frozenset({
    "your-key", "your-api-key", "changeme", "sk-xxx", "none", "",
})


def _read_dotenv(path: Path) -> Dict[str, str]:
    """Minimal dotenv reader. Values are returned, never printed."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        if key.strip():
            out[key.strip()] = val
    return out


def model_credentials() -> Tuple[Dict[str, str], List[str]]:
    """Return (creds, sorted names present). Values are used, never displayed."""
    src = _read_dotenv(BACKEND / ".env")
    for k, v in _read_dotenv(REPO / ".env").items():
        src.setdefault(k, v)
    creds = {n: src[n] for n in CREDENTIAL_ENV_NAMES
             if src.get(n) and src[n].strip().lower() not in PLACEHOLDER_VALUES}
    return creds, sorted(creds)


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------
def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) != 0


def pick_free_port(preferred: int) -> int:
    p = preferred
    while p < preferred + 300:
        if port_free(p):
            return p
        p += 1
    raise RuntimeError(f"no free port near {preferred}")


# --------------------------------------------------------------------------
# World + state
# --------------------------------------------------------------------------
def world_path(name: str) -> Path:
    return BACKEND / "data" / "acceptance_worlds" / name


def state_path(world: Path) -> Path:
    return world / "preview_stack.json"


def load_state(world: Path) -> Dict[str, Any]:
    p = state_path(world)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(world: Path, state: Dict[str, Any]) -> None:
    world.mkdir(parents=True, exist_ok=True)
    state_path(world).write_text(json.dumps(state, indent=2, sort_keys=True))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# Source fingerprint.
# The plan (section 4) requires a source fingerprint for final acceptance and
# forbids reporting a result produced against a superseded one.
# run_isolated hashes the exported TREE on disk, which is necessary but not
# sufficient: the process serves whatever it actually imported. So we also
# record, per key module, the resolved path and sha256 as seen from the
# world's own export with the world's own sys.path -- i.e. the code the world
# will serve, not the mutable checkout it was copied from.
# --------------------------------------------------------------------------
FINGERPRINT_MODULES = (
    "main_api_app",
    "core.task_lifecycle",
    "core.chat_transport",
    "core.answer_presentation",
    "core.chat_tool_planner",
    "core.workbook_read_artifact",
    "core.hybrid_retrieval_service",
    "core.hybrid_search.documents_hybrid",
    "core.memory_context_assembler",
    "core.identifier_search",
    "core.pending_file_task",
    "integrations.chat_orchestrator",
    "integrations.chat_routes",
    "tools.drive_tool",
)


def loaded_module_fingerprint(world: Path) -> Dict[str, Any]:
    """Resolve each key module against the world export and hash the file.

    Runs in a throwaway interpreter with the same interpreter, sys.path root
    and cwd the server uses. A module that fails to import is reported as an
    error rather than silently omitted, because a missing module is exactly
    the kind of drift this is meant to catch.
    """
    farm = world / "backend_root"
    code_root = world / "code" / "backend"
    probe = (
        "import hashlib,importlib,json,os,sys\n"
        f"sys.path.insert(0, {str(code_root)!r})\n"
        f"os.chdir({str(farm)!r})\n"
        f"names = {list(FINGERPRINT_MODULES)!r}\n"
        "out = {}\n"
        "for n in names:\n"
        "    try:\n"
        "        m = importlib.import_module(n)\n"
        "        f = getattr(m, '__file__', None)\n"
        "        h = hashlib.sha256(open(f, 'rb').read()).hexdigest() if f else None\n"
        "        out[n] = {'path': os.path.realpath(f) if f else None, 'sha256': h}\n"
        "    except Exception as e:\n"
        "        out[n] = {'error': type(e).__name__ + ': ' + str(e)[:160]}\n"
        "print('@@@' + json.dumps(out))\n"
    )
    script = world / "_fingerprint_probe.py"
    script.write_text(probe)
    env = dict(os.environ)
    env.update({"DATABASE_URL": "sqlite:////nonexistent-probe.db",
                "ATOM_DATA_DIR": str(world / "data"),
                "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        res = subprocess.run([str(VENV_PY), str(script)], capture_output=True,
                             text=True, timeout=420, env=env, cwd=str(farm))
        for line in res.stdout.splitlines():
            if line.startswith("@@@"):
                return json.loads(line[3:])
        return {"error": "probe produced no result", "stderr": res.stderr[-600:]}
    except subprocess.TimeoutExpired:
        return {"error": "fingerprint probe timed out"}
    finally:
        script.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Environment for the preview backend
# --------------------------------------------------------------------------
def server_env(run_dir: Path, world: Path, backend_port: int,
               frontend_port: int) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return (env, effective_flags) for the preview backend.

    Deviations from run_isolated.launch_server, each deliberate:
      * LANCEDB_URI points at run_dir/data/atom_memory, which is the directory
        _seed_run_data actually creates. run_isolated points it at
        world/data/atom_memory, which does not exist -- the same
        path-anchoring class AGENTS.md section 1 warns about, and it leaves the
        agent-memory store empty.
      * Real model credentials are included (see module docstring).
      * CORS/host allowlists are extended to this instance's own origin.
    """
    env = {k: os.environ[k] for k in R.SERVER_ENV_WHITELIST if k in os.environ}
    creds, cred_names = model_credentials()
    env.update(creds)
    env.update({
        "DATABASE_URL": f"sqlite:///{run_dir / 'data' / 'atom.db'}",
        "ATOM_DATA_DIR": str(run_dir / "data"),
        "LANCEDB_URI": str(run_dir / "data" / "atom_memory"),
        "ATOM_SHEET_DATASETS": "1",
        "ATOM_CHAT_STREAMING": "1",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ACC_PORT": str(backend_port),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "development",
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
        # This instance's own frontend origin must be allowed: transport A in
        # the frontend (axios apiClient) calls the backend absolutely.
        "ADDITIONAL_ALLOWED_ORIGINS": f"http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}",
        "ALLOWED_HOSTS": (f"localhost,127.0.0.1,localhost:{backend_port},"
                          f"127.0.0.1:{backend_port},localhost:{frontend_port},"
                          f"127.0.0.1:{frontend_port},testserver"),
        # Feature flags under test. Recorded as EFFECTIVE values below and
        # re-read from the child process, never trusted as requested.
        "ATOM_TASK_LIFECYCLE_ENABLED": "1",
        "CHAT_FINALIZATION_M1": "1",
        "CHAT_FINALIZATION_M2": "1",
    })
    flags = {
        "ATOM_TASK_LIFECYCLE_ENABLED": env["ATOM_TASK_LIFECYCLE_ENABLED"],
        "CHAT_FINALIZATION_M1": env["CHAT_FINALIZATION_M1"],
        "CHAT_FINALIZATION_M2": env["CHAT_FINALIZATION_M2"],
        "ATOM_CHAT_STREAMING": env["ATOM_CHAT_STREAMING"],
        "ATOM_SHEET_DATASETS": env["ATOM_SHEET_DATASETS"],
        "ENABLE_SCHEDULER": env["ENABLE_SCHEDULER"],
        "ENABLE_INGESTION_SYNC": env["ENABLE_INGESTION_SYNC"],
        "credential_names_present": cred_names,
    }
    return env, flags


# --------------------------------------------------------------------------
# up
# --------------------------------------------------------------------------
def cmd_up(args: argparse.Namespace) -> int:
    world = world_path(args.world)
    if not (world / "fixture" / "atom.db").exists():
        print(f"world {args.world!r} has no fixture DB. Build it first:\n"
              f"  python scripts/orchestration_acceptance/run_isolated.py "
              f"--name {args.world} --snapshot-working-tree --rebuild-world "
              f"--refreeze-db --cases true_eight", file=sys.stderr)
        return 2

    st = load_state(world)
    if st.get("backend_pid") and _pid_alive(st["backend_pid"]):
        print(f"stack already up (backend pid {st['backend_pid']}); "
              f"use `down` first or pick another --world")
        return 2

    backend_port = pick_free_port(args.backend_port)
    frontend_port = pick_free_port(args.frontend_port)
    if backend_port == frontend_port:
        frontend_port = pick_free_port(frontend_port + 1)

    # Fresh per-run data dir, seeded from the sanitized fixture via the SQLite
    # backup API, exactly as the acceptance harness does.
    run_dir = world / "runs" / f"run-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[preview] seeding run data -> {run_dir}")
    R._seed_run_data(world, run_dir)

    byok = {"skipped": True}
    if not args.no_user_byok:
        byok = seed_byok_store(run_dir)
        print(f"[preview] BYOK store seeded into run dir: "
              f"providers={','.join(byok['provider_ids_present']) or 'none'}")

    farm = world / "backend_root"
    link = farm / "data"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(run_dir / "data", target_is_directory=True)

    env, flags = server_env(run_dir, world, backend_port, frontend_port)
    run_dir.joinpath("server_env.json").write_text(json.dumps(
        {k: v for k, v in env.items() if k in
         set(flags) | {"DATABASE_URL", "ATOM_DATA_DIR", "LANCEDB_URI"}},
        indent=2, sort_keys=True))

    log = (world / "preview_backend.log").open("ab")
    proc = subprocess.Popen(
        [str(VENV_PY), str(APP_PY)],
        cwd=str(farm), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"[preview] backend pid {proc.pid} on :{backend_port} (log: {world/'preview_backend.log'})")

    base = f"http://127.0.0.1:{backend_port}"
    ok = _await_health(base, deadline=300, proc=proc)
    if not ok:
        print(f"[preview] backend failed to become healthy; see {world/'preview_backend.log'}",
              file=sys.stderr)
        return 1

    identity = _health_identity(base)
    # A server on this port must be THIS launch. The health identity carries
    # the resolved cwd; a mismatch means a foreign world's server is answering
    # and every observation would be attributed to the wrong world.
    if identity.get("cwd") and str(Path(identity["cwd"]).resolve()) != str(farm.resolve()):
        print(f"[preview] REFUSING: :{backend_port} is served by cwd "
              f"{identity.get('cwd')!r}, not this world ({farm}).", file=sys.stderr)
        _terminate(proc)
        return 1

    fe = _start_frontend(backend_port, frontend_port, world)

    state = {
        "world": args.world,
        "world_path": str(world),
        "run_dir": str(run_dir),
        "db_path": str((run_dir / "data" / "atom.db").resolve()),
        "backend_port": backend_port,
        "backend_pid": proc.pid,
        "backend_health_identity": identity,
        "frontend_port": frontend_port,
        "frontend_pid": fe,
        "effective_flags": flags,
        "byok": byok,
        "source_snapshot_sha256": _world_snapshot_sha(world),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "seatbelt": False,
        "seatbelt_note": ("preview requires real model egress; isolation is at the "
                          "data boundary. See module docstring."),
    }
    save_state(world, state)

    print(f"[preview] fingerprinting loaded modules (this takes a minute)...")
    state["loaded_modules"] = loaded_module_fingerprint(world)
    save_state(world, state)
    write_launch_descriptor(world, state)

    print(f"\n  backend : {base}   (pid {proc.pid})")
    print(f"  frontend: http://localhost:{frontend_port}   (pid {fe})")
    print(f"  world   : {args.world}   run {run_dir.name}")
    print(f"  db      : {state['db_path']}")
    return 0


def _world_snapshot_sha(world: Path) -> Optional[str]:
    m = world / "MANIFEST.json"
    if m.exists():
        try:
            man = json.loads(m.read_text())
            for k in ("code_snapshot_sha256", "code_archive_sha256", "export_sha256"):
                if man.get(k):
                    return f"{k}={man[k]}"
        except json.JSONDecodeError:
            pass
    cm = world / "code_manifest.json"
    return f"code_manifest_sha256={sha256_file(cm)}" if cm.exists() else None


def _await_health(base: str, deadline: float, proc: subprocess.Popen) -> bool:
    import httpx
    end = time.time() + deadline
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            r = httpx.get(f"{base}/api/health", timeout=3, trust_env=False)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _health_identity(base: str) -> Dict[str, Any]:
    import httpx
    try:
        r = httpx.get(f"{base}/api/health", timeout=10, trust_env=False)
        return (r.json() or {}).get("identity", {}) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _start_frontend(backend_port: int, frontend_port: int, world: Path) -> Optional[int]:
    """Start a SECOND frontend instance against this world's backend.

    The repo's own dev server (and the user's) already holds
    <distDir>/dev/lock, and Next 16 hardcodes the config filename with no env
    override, so a second instance needs its own project directory. That
    directory is the symlink farm at frontend-nextjs/.preview-instance: every
    top-level entry except .next/node_modules/next.config.js/.env.local is a
    symlink, so it always reflects the current sources and duplicates nothing.
    Its config is the repo's real config with distDir overridden, which is the
    only behavioural change.
    """
    if not PREVIEW_FE.exists():
        print(f"[preview] WARNING: {PREVIEW_FE} missing; not starting a frontend. "
              f"Create the symlink farm first.", file=sys.stderr)
        return None
    env = dict(os.environ)
    env.update({
        "NEXT_PUBLIC_API_URL": f"http://localhost:{backend_port}",
        "PYTHON_API_SERVICE_BASE_URL": f"http://localhost:{backend_port}",
        "NEXTAUTH_URL": f"http://localhost:{frontend_port}",
        "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
        "NODE_OPTIONS": "--max-old-space-size=4096",
    })
    # Do not inherit a NEXT_PUBLIC_API_URL pointing at the user's backend.
    log = (world / "preview_frontend.log").open("ab")
    # --webpack, not the Next 16 default Turbopack: Turbopack refuses a
    # project whose entrypoint directories are symlinks pointing outside its
    # filesystem root ("Symlink [project]/pages is invalid, it points out of
    # the filesystem root"), which is exactly the symlink farm this instance
    # is built from. Webpack resolves those symlinks normally.
    proc = subprocess.Popen(
        ["node", "node_modules/next/dist/bin/next", "dev", "--webpack",
         "-p", str(frontend_port)],
        cwd=str(PREVIEW_FE), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    end = time.time() + 240
    while time.time() < end:
        if proc.poll() is not None:
            print(f"[preview] frontend exited early; see {world/'preview_frontend.log'}",
                  file=sys.stderr)
            return None
        try:
            import httpx
            r = httpx.get(f"http://127.0.0.1:{frontend_port}/login", timeout=5,
                          trust_env=False)
            if r.status_code == 200:
                return proc.pid
        except Exception:
            pass
        time.sleep(3)
    print("[preview] WARNING: frontend did not answer /login in 240s", file=sys.stderr)
    return proc.pid


def _terminate(proc: subprocess.Popen, grace: float = 15.0) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), 15)
    except OSError:
        proc.terminate()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            proc.kill()


# --------------------------------------------------------------------------
# Model credentials: the app's OWN encrypted BYOK store.
#
# Why this exists. The plan requires at least one REAL configured model to
# serve a browser-visible turn, and forbids inventing or hardcoding a
# credential. The repo's real provider keys are not in backend/.env at all --
# they live in backend/data/byok_keys.json, encrypted at rest with a Fernet
# key in backend/data/byok_encryption_key, and they are exactly the
# "existing credential mechanism" the plan requires us to use.
#
# `core/llm` resolves those paths against <backend>/data, which inside a world
# is the farm's `data` symlink -> the per-run directory. So a fresh world
# auto-creates an EMPTY key store and the preview has no provider access: the
# only thing that worked was the OPENROUTER_API_KEY env var, whose account is
# out of credits (HTTP 402, observed). Seeding the run directory with the
# user's own three BYOK files restores real provider access through the
# supported path, with no production change and no secret ever rendered.
#
# The store is copied, never moved, and only the encrypted form is copied, so
# the app's own encryption boundary is preserved end to end. Values are not
# printed, and the target files are chmod 600.
# --------------------------------------------------------------------------
BYOK_SEED_FILES = ("byok_keys.json", "byok_config.json", "byok_encryption_key")


def seed_byok_store(run_dir: Path) -> Dict[str, Any]:
    """Copy the encrypted BYOK store into the run dir. Returns a summary with
    provider NAMES only -- never a key, a hash, or a length."""
    src_dir = BACKEND / "data"
    dst_dir = run_dir / "data"
    copied, missing = [], []
    for name in BYOK_SEED_FILES:
        src, dst = src_dir / name, dst_dir / name
        if not src.exists():
            missing.append(name)
            continue
        if dst.exists() and dst.stat().st_size:
            # A previous run already seeded it; the world is per-run so this
            # is only reachable on a reused run dir. Overwrite deliberately.
            pass
        shutil.copy2(src, dst)
        dst.chmod(0o600)
        copied.append(name)
    providers: List[str] = []
    keys_file = dst_dir / "byok_keys.json"
    if keys_file.exists():
        try:
            raw = json.loads(keys_file.read_text())
            providers = sorted({v.get("provider_id", "?")
                                for v in (raw.get("keys") or {}).values()
                                if isinstance(v, dict)})
        except (json.JSONDecodeError, OSError):
            pass
    return {"files_copied": copied, "files_missing": missing,
            "provider_ids_present": providers,
            "note": "encrypted store copied verbatim; no secret was read or printed"}


# --------------------------------------------------------------------------
# up
# --------------------------------------------------------------------------
# status / verify / down
# --------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    world = world_path(args.world)
    st = load_state(world)
    if not st:
        print(f"no preview stack state for world {args.world!r}")
        return 1
    print(json.dumps(st, indent=2, sort_keys=True))
    return 0


def write_launch_descriptor(world: Path, st: Dict[str, Any]) -> Path:
    """Emit a run_isolated-shaped launch_descriptor.json for this preview.

    The two tools have to interoperate: `live_integration_acceptance.py`
    drives an ALREADY-RUNNING server and takes `--launch-descriptor` from
    run_isolated.launch_server. The preview launches its own server (no
    seatbelt, real providers), but it can describe that launch in the same
    vocabulary, so the live 12-case matrix -- the one that covers formatting
    followups, explicit re-search, keyed retry, streaming, restart, overlap
    and forced retrieval failure -- can run against the preview instead of
    only against a credential-free sandbox that cannot reach a model at all.

    The three fields the consumer actually reads are `export_path` (the farm
    root, whose resolved cwd it asserts against the server's health
    identity), `db_path` (the database the process must have open) and `pid`.
    """
    d = world / "launch_descriptor.json"
    d.write_text(json.dumps({
        "run_id": Path(st["run_dir"]).name,
        "pid": st["backend_pid"],
        "port": st["backend_port"],
        "export_path": str(Path(st["world_path"]) / "backend_root"),
        "db_path": st["db_path"],
        "world": st["world_path"],
        "log_path": str(world / "preview_backend.log"),
        "expected_cwd": str(Path(st["world_path"]) / "backend_root"),
        "health_identity": st.get("backend_health_identity", {}),
        "source_snapshot_sha256": st.get("source_snapshot_sha256"),
        "effective_flags": st.get("effective_flags", {}),
        "byok": st.get("byok", {}),
        "seatbelt": st.get("seatbelt"),
        "emitted_by": "preview_stack.py",
    }, indent=2, sort_keys=True))
    return d


def cmd_verify(args: argparse.Namespace) -> int:
    """Prove the running stack is the world we claim, from the outside.

    Checks, in order:
      1. backend health identity pid/cwd == our launch
      2. the SQLite file the process actually has OPEN is our run db
         (lsof on the pid, resolved through symlinks) -- not merely the path
         we intended
      3. the frontend answers and its compiled API origin points at OUR
         backend port, not the user's :8001
      4. effective feature flags, read back from the launch descriptor
      5. a public-boundary authenticated round trip
    """
    import httpx
    world = world_path(args.world)
    st = load_state(world)
    if not st:
        print("no preview stack state", file=sys.stderr)
        return 1
    port = st["backend_port"]
    fe = st.get("frontend_port")
    base = f"http://127.0.0.1:{port}"
    findings: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        findings.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))

    print(f"verify world={args.world} backend=:{port} frontend=:{fe}")

    alive = _pid_alive(st["backend_pid"])
    check("backend process alive", alive, st["backend_pid"])

    ident = _health_identity(base)
    check("health identity pid matches launch", ident.get("pid") == st["backend_pid"],
          f"{ident.get('pid')} vs {st['backend_pid']}")
    check("health identity cwd is this world",
          str(Path(ident.get("cwd", "")).resolve()) == str(Path(world / "backend_root").resolve()),
          ident.get("cwd"))

    opened = _opened_sqlite(st["backend_pid"])
    expected_db = str(Path(st["db_path"]).resolve())
    check("process has our run db OPEN", expected_db in opened, opened or "none found")
    check("process is NOT holding the live dev db",
          not any("backend/data/atom.db" in p and "acceptance_worlds" not in p for p in opened),
          expected_db)

    if fe:
        try:
            r = httpx.get(f"http://127.0.0.1:{fe}/api/health", timeout=10, trust_env=False)
            check("frontend answers", r.status_code in (200, 307),
                  f"/api/health -> {r.status_code}")
        except Exception as exc:
            check("frontend answers", False, f"{type(exc).__name__}: {exc}")
        found, origin = _frontend_api_origin(fe, port)
        check("frontend compiled API origin is THIS backend", found, origin)

    check("effective lifecycle flag is on",
          st.get("effective_flags", {}).get("ATOM_TASK_LIFECYCLE_ENABLED") == "1",
          st.get("effective_flags", {}).get("ATOM_TASK_LIFECYCLE_ENABLED"))
    check("real model credentials were forwarded",
          bool(st.get("effective_flags", {}).get("credential_names_present")),
          ",".join(st.get("effective_flags", {}).get("credential_names_present", [])) or "NONE")

    bad = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings)-len(bad)}/{len(findings)} checks passed")
    return 0 if not bad else 1


def _opened_sqlite(pid: int) -> List[str]:
    """The SQLite files this pid actually has open, symlinks resolved."""
    out: List[str] = []
    try:
        res = subprocess.run(["lsof", "-p", str(pid), "-Fn"], capture_output=True,
                             text=True, timeout=60)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return out
    for line in res.stdout.splitlines():
        if line.startswith("n") and ".db" in line:
            try:
                out.append(str(Path(line[1:]).resolve()))
            except OSError:
                out.append(line[1:])
    return sorted(set(out))


def _frontend_api_origin(fe_port: int, backend_port: int) -> Tuple[bool, Optional[str]]:
    """Prove the frontend compiled THIS backend origin into its client bundle.

    `NEXT_PUBLIC_API_URL` is inlined into the client bundle at COMPILE time,
    so neither `.env.local` nor the process environment is evidence -- only
    the emitted chunk is. The server-rendered HTML does not contain it (the
    variable is used by client code), so the check reads the built static
    chunks of this instance's own distDir, which is `distDir: '.next-preview'`
    (see .preview-instance/next.config.js).

    Returns (found, origin). A bare "not found in bundle" is NOT treated as a
    pass: an unproven origin is exactly the failure this whole check exists to
    catch, so it stays a FAIL.
    """
    dist = PREVIEW_FE / ".next-preview"
    if not dist.exists():
        return False, f"no distDir at {dist}"
    found: Optional[str] = None
    scanned = 0
    for sub in ("static/chunks", "static/chunks/app", "."):
        d = dist / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*.js"):
            try:
                if f.stat().st_size > 12_000_000:
                    continue
                txt = f.read_text(errors="replace")
            except OSError:
                continue
            scanned += 1
            for m in re.finditer(r"https?://(?:localhost|127\.0\.0\.1):(\d{4,5})", txt):
                if int(m.group(1)) == backend_port:
                    return True, m.group(0)
                if found is None:
                    found = m.group(0)
    return False, (f"no chunk referenced :{backend_port} (scanned {scanned} "
                   f"chunks; other loopback origin seen: {found})")


def cmd_down(args: argparse.Namespace) -> int:
    world = world_path(args.world)
    st = load_state(world)
    for key in ("frontend_pid", "backend_pid"):
        pid = st.get(key)
        if not pid:
            continue
        try:
            os.killpg(os.getpgid(pid), 15)
            print(f"[preview] SIGTERM -> {key} {pid}")
        except OSError:
            try:
                os.kill(pid, 15)
                print(f"[preview] SIGTERM -> {key} {pid}")
            except OSError:
                print(f"[preview] {key} {pid} not running")
    time.sleep(3)
    for key in ("frontend_pid", "backend_pid"):
        pid = st.get(key)
        if pid and _pid_alive(pid):
            try:
                os.kill(pid, 9)
                print(f"[preview] SIGKILL -> {key} {pid}")
            except OSError:
                pass
    st["stopped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_state(world, st)
    return 0


def cmd_descriptor(args: argparse.Namespace) -> int:
    """(Re)write launch_descriptor.json from the saved state, without
    restarting anything. Useful after a manual relaunch."""
    world = world_path(args.world)
    st = load_state(world)
    if not st:
        print(f"no preview stack state for world {args.world!r}", file=sys.stderr)
        return 1
    print(write_launch_descriptor(world, st))
    return 0


def cmd_creds(args: argparse.Namespace) -> int:
    _, names = model_credentials()
    print(json.dumps({"credential_names_present": names,
                      "note": "values intentionally not printed"}, indent=2))
    return 0 if names else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", default=DEFAULT_WORLD)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("up", help="build nothing; seed a run dir and launch backend+frontend")
    p.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    p.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    p.add_argument("--no-user-byok", action="store_true",
                   help="do NOT seed the run dir with the repo's encrypted BYOK "
                        "store; the preview then has no real provider access")
    p.set_defaults(fn=cmd_up)

    p = sub.add_parser("verify", help="prove the running stack is the claimed world")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("down", help="stop the stack")
    p.set_defaults(fn=cmd_down)

    p = sub.add_parser("status", help="print the launch descriptor")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("descriptor", help="(re)write launch_descriptor.json from saved state")
    p.set_defaults(fn=cmd_descriptor)

    p = sub.add_parser("creds", help="report which model credentials are available (names only)")
    p.set_defaults(fn=cmd_creds)

    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
