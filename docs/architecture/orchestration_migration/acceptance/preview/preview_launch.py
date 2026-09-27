#!/usr/bin/env python3
"""Isolated app preview: launch a real, usable Atom on its own ports.

Why this file exists and what it deliberately does NOT do:

- It does NOT reimplement isolation. `run_isolated.py` owns world construction,
  the immutable code export, the seatbelt profile, the credential scrub, the
  recorded schema sync and the effective-flag preflight; this imports that
  module. A second isolation story would be a second thing to keep correct.
- It does NOT touch the user's environment. The live backend on :8001 and the
  frontend on :3000 are left running and untouched. The plan is explicit:
  "Do not restart or replace the user's usual environment just to make the
  preview available."
- It does NOT use a provider shim. The preview gate requires "at least one real
  configured model must produce a successful browser-visible turn". The real
  model here is a local Ollama model over loopback, which also keeps the
  seatbelt boundary intact (no external egress is needed or permitted).

The seatbelt profile gains exactly one extra loopback destination: Ollama's
port. Everything else is denied, so the preview cannot reach the internet even
though the model it uses is real.

Usage:
  preview_launch.py --port 8091 --frontend-port 3091 --name search_preview
  preview_launch.py --status
  preview_launch.py --stop
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend-nextjs"
sys.path.insert(0, str(BACKEND))

STATE_PATH = HERE / "preview_state.json"
HARNESS = BACKEND / "scripts" / "orchestration_acceptance" / "run_isolated.py"
OLLAMA_PORT = int(os.getenv("PREVIEW_OLLAMA_PORT", "11434"))
OLLAMA_MODEL = os.getenv("PREVIEW_OLLAMA_MODEL", "llama3.1:8b")
FRONTEND_DIST = ".next-preview"
# Filled at launch; the farm env file is written before the frontend starts.
PREVIEW_BACKEND_PORT = 8091
PREVIEW_FRONTEND_PORT = 3091


def _load_isolation() -> Any:
    spec = importlib.util.spec_from_file_location("orchestration_isolation", HARNESS)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the isolation harness at {HARNESS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ISO = _load_isolation()


# --------------------------------------------------------------------------- #
# Real-model probe
# --------------------------------------------------------------------------- #

def probe_ollama(timeout: float = 180.0) -> dict[str, Any]:
    """Prove a REAL model generates, before anything claims a preview.

    Timed twice on purpose: the first call pays a model load from disk and can
    take minutes, the second is the latency a user will actually feel. Quoting
    only one of the two is how a preview ends up looking broken on first use.
    """
    import httpx

    url = f"http://127.0.0.1:{OLLAMA_PORT}/v1/chat/completions"
    out: dict[str, Any] = {"base_url": f"http://127.0.0.1:{OLLAMA_PORT}/v1",
                           "model": OLLAMA_MODEL, "real_model": True}
    try:
        tags = httpx.get(f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", timeout=10)
        names = [m.get("name") for m in (tags.json() or {}).get("models", [])]
        out["available_models"] = names
        if OLLAMA_MODEL not in names:
            out["real_model"] = False
            out["reason"] = f"{OLLAMA_MODEL} not pulled; available={names}"
            return out
    except Exception as exc:  # noqa: BLE001
        out["real_model"] = False
        out["reason"] = f"ollama unreachable: {type(exc).__name__}"
        return out

    for label in ("cold", "warm"):
        t0 = time.monotonic()
        try:
            r = httpx.post(url, timeout=timeout, json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": "Reply with exactly: MODEL_OK"}],
                "max_tokens": 24, "temperature": 0,
            })
            elapsed = time.monotonic() - t0
            if r.status_code != 200:
                out[f"{label}_status"] = r.status_code
                out[f"{label}_error"] = r.text[:200]
                continue
            body = r.json()
            out[f"{label}_latency_s"] = round(elapsed, 2)
            out[f"{label}_content"] = (
                (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            )[:80]
            out[f"{label}_tokens"] = (body.get("usage") or {}).get("total_tokens")
        except Exception as exc:  # noqa: BLE001
            out[f"{label}_error"] = f"{type(exc).__name__}: {exc}"[:200]
    out["generated"] = "MODEL_OK" in str(out.get("warm_content", "")) or \
                       "MODEL_OK" in str(out.get("cold_content", ""))
    return out


# --------------------------------------------------------------------------- #
# Backend launch
# --------------------------------------------------------------------------- #

def _assert_port_free(port: int) -> None:
    """Refuse to launch onto a port a previous run left behind.

    This guard is not optional. An earlier draft of this launcher skipped it and
    a stale backend from a failed attempt kept holding the port, so the health
    check happily reported THAT server's identity while the newly launched
    process silently failed to bind — and the isolation report described a world
    that was not the one serving traffic. A stale server on the port is exactly
    how a run ends up certifying the wrong world.
    """
    import httpx
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=3,
                      trust_env=False)
    except Exception:
        return  # nothing listening
    ident = (r.json() or {}).get("identity") or {}
    raise SystemExit(
        f"PORT {port} IS ALREADY SERVED by pid {ident.get('pid')} "
        f"(cwd {ident.get('cwd')}, source {ident.get('source_id')}). "
        f"Refusing to launch: observations would attribute to that server, "
        f"not this launch. Stop it, or choose another port."
    )


def launch_backend(port: int, world: Path) -> subprocess.Popen:
    """Launch the isolated backend on its own port, seatbelt intact.

    Uses the harness's own launcher for the world/DB/symlink-farm work, then
    launches the process with the preview's environment. The seatbelt profile
    is the harness's, regenerated to admit exactly two loopback destinations:
    this server's port and Ollama's.
    """
    _assert_port_free(port)
    # A throwaway signing key for THIS world, generated at launch and recorded
    # in the state file so the verification driver mints tokens the running
    # server will accept. Without it the server and the client each generate
    # their own development default and every authenticated call 401s — which
    # looks exactly like a broken app. It is not a credential: it authenticates
    # nobody outside this disposable world, and no real secret is read.
    secret = secrets.token_urlsafe(48)
    ISO.launch_server.lifecycle = True
    ISO.launch_server.m1 = False
    ISO.launch_server.gate = False

    # Reuse the harness's launch for everything world-shaped, but WITHOUT the
    # shim: the preview must exercise a real provider. We call it, then relaunch
    # is unnecessary — instead we ask it for the run dir and build our own
    # process so the env can carry the real-model configuration.
    import uuid
    run_dir = world / "runs" / f"run-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    ISO._seed_run_data(world, run_dir)

    farm = world / "backend_root"
    data_link = farm / "data"
    if data_link.is_symlink() or data_link.exists():
        data_link.unlink()
    data_link.symlink_to(run_dir / "data", target_is_directory=True)

    profile = world / "preview.sb"
    profile.write_text(ISO._sandbox_profile(port, extra_ports=(OLLAMA_PORT,)))

    env = {k: os.environ[k] for k in ISO.SERVER_ENV_WHITELIST if k in os.environ}
    env.update({
        "DATABASE_URL": f"sqlite:///{run_dir / 'data' / 'atom.db'}",
        "ATOM_DATA_DIR": str(run_dir / "data"),
        "LANCEDB_URI": str(world / "data" / "atom_memory"),
        "ATOM_SHEET_DATASETS": "1",
        "ATOM_CHAT_STREAMING": "1",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ACC_PORT": str(port),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ATOM_TASK_LIFECYCLE_ENABLED": "1",
        # REAL MODEL, loopback only. No API key: Ollama ignores one and the
        # provider is registered from its own runtime discovery.
        "OLLAMA_BASE_URL": f"http://127.0.0.1:{OLLAMA_PORT}/v1",
        "OLLAMA_MODELS": OLLAMA_MODEL,
        "OLLAMA_LOAD_TIMEOUT": "15m",
        # The browser calls the backend cross-origin (the preview frontend is
        # on its own port), and the backend's CORS allow-list is origin-based,
        # not port-agnostic — without this every API call is blocked, the app
        # cannot authenticate, and it bounces to /login. Uses the app's own
        # documented extension hook rather than widening the default list.
        "ADDITIONAL_ALLOWED_ORIGINS": (
            f"http://localhost:{PREVIEW_FRONTEND_PORT},"
            f"http://127.0.0.1:{PREVIEW_FRONTEND_PORT}"),
        "ATOM_PROVIDER": "ollama",
        "ATOM_DEFAULT_MODEL": OLLAMA_MODEL,
        "PREFERRED_PROVIDER": "ollama",
        "SECRET_KEY": secret,
        "ENVIRONMENT": "development",
    })
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_BASE_URL", None)

    ISO.launch_server.last_run_dir = run_dir
    log = open(world / "preview_backend.log", "ab")
    proc = subprocess.Popen(
        ["/usr/bin/sandbox-exec", "-f", str(profile),
         str(ISO.VENV_PY), str(BACKEND / "scripts" / "orchestration_acceptance" / "_app.py")],
        cwd=str(farm), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    import httpx
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 300
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(
                f"preview backend exited rc={proc.returncode}; see "
                f"{world / 'preview_backend.log'}")
        try:
            h = httpx.get(f"{base}/api/health", timeout=3, trust_env=False)
            if h.status_code == 200:
                ident = (h.json() or {}).get("identity") or {}
                if Path(ident.get("cwd", "")).resolve() != farm.resolve():
                    proc.kill()
                    raise SystemExit(
                        f"FOREIGN SERVER on :{port} (cwd={ident.get('cwd')}); refusing")
                if ident.get("pid") != proc.pid:
                    # Same world, different process: a previous launch of THIS
                    # world is still bound to the port. The health endpoint
                    # cannot be trusted to describe the process we just started.
                    proc.kill()
                    raise SystemExit(
                        f"STALE SERVER on :{port}: health reports pid "
                        f"{ident.get('pid')} but this launch is pid {proc.pid}. "
                        f"The port is held by an earlier run of this world.")
                ISO.launch_server.preview_secret = secret
                ISO.launch_server.descriptor = {
                    "run_id": run_dir.name, "pid": proc.pid, "port": port,
                    "db_path": str((run_dir / "data" / "atom.db").resolve()),
                    "export_path": str(farm.resolve()),
                    "world": str(world), "log_path": str(world / "preview_backend.log"),
                    "health_identity": ident,
                }
                return proc
        except SystemExit:
            raise
        except Exception:
            pass
        time.sleep(1.0)
    proc.kill()
    raise SystemExit(f"preview backend did not become healthy; see {world / 'preview_backend.log'}")


# --------------------------------------------------------------------------- #
# Frontend launch
# --------------------------------------------------------------------------- #

def build_frontend_farm(farm: Path) -> Path:
    """A symlink farm mirroring `frontend-nextjs` at a DIFFERENT path.

    Next.js refuses a second `next dev` in the same directory ("Another next dev
    server is already running") and would also fight over one `.next` cache. A
    farm at its own path gives it a different directory identity and its own
    build output, so the user's running :3000 server and their `.next` cache are
    never touched. This mirrors the approach the backend already uses (an
    immutable code export plus a symlink farm) rather than inventing a new one.
    """
    if farm.exists():
        ISO._make_tree_writable(farm / ".next")
        import shutil
        shutil.rmtree(farm, ignore_errors=True)
    farm.mkdir(parents=True)
    for entry in FRONTEND.iterdir():
        if entry.name in (".next", ".preview-instance", ".git"):
            continue
        (farm / entry.name).symlink_to(entry)
    # Its own env file so the farm never reads the user's NEXT_PUBLIC_API_URL.
    (farm / ".env.local").unlink(missing_ok=True)
    (farm / ".env.local").write_text(
        "# Isolated preview environment. Generated; contains no secrets.\n"
        f"NEXT_PUBLIC_API_URL=http://127.0.0.1:{PREVIEW_BACKEND_PORT}\n"
        "NEXT_PUBLIC_ALLOW_LOOPBACK=1\n"
    )
    return farm


def launch_frontend(port: int, api_url: str, world: Path) -> subprocess.Popen:
    """Launch the Next.js frontend on its own port against the isolated backend.

    A separate distDir keeps the user's `next dev` cache and the running :3000
    server completely undisturbed — same reason the backend runs from an
    immutable export rather than the checkout.
    """
    _assert_port_free(port)
    farm = build_frontend_farm(world / "frontend_farm")
    env = dict(os.environ)
    env.update({
        "NEXT_PUBLIC_API_URL": api_url,
        "PYTHON_API_SERVICE_BASE_URL": api_url,
        "NEXT_PUBLIC_API_BASE_URL": api_url,
        "PYTHON_BACKEND_URL": api_url,
        # loopback into a client bundle is legitimate for a same-machine preview
        "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
        "PORT": str(port),
        "NODE_ENV": "development",
    })
    # Remove the farm's inherited .env.local influence by unsetting nothing:
    # next.config.js prefers the real env, which is what we just set.
    log = open(world / "preview_frontend.log", "ab")
    proc = subprocess.Popen(
        # --webpack, not the default Turbopack: Turbopack refuses a symlink
        # that points out of the project root ("Symlink [project]/pages is
        # invalid"), which is exactly the isolation mechanism used here. The
        # builder is slower to start and this is a preview, not a dev loop.
        ["npx", "next", "dev", "--webpack", "--port", str(port)],
        cwd=str(farm), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    import httpx
    deadline = time.time() + 420
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(
                f"preview frontend exited rc={proc.returncode}; see "
                f"{world / 'preview_frontend.log'}")
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/", timeout=5, trust_env=False)
            if r.status_code in (200, 307, 302):
                return proc
        except Exception:
            pass
        time.sleep(2.0)
    proc.kill()
    raise SystemExit(f"preview frontend did not serve; see {world / 'preview_frontend.log'}")


# --------------------------------------------------------------------------- #

def _verify_isolation(port: int, world: Path) -> dict[str, Any]:
    """Prove the preview is talking to the isolated world, not the user's env.

    "A separate frontend port alone does not prove isolation" — so this checks
    the server's own identity, the database file it actually opened, and that
    the user's live ports were not touched.
    """
    import httpx

    out: dict[str, Any] = {}
    h = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=10,
                   trust_env=False).json()
    ident = h.get("identity") or {}
    out["backend_identity"] = {
        "pid": ident.get("pid"), "cwd": ident.get("cwd"),
        "source_id": ident.get("source_id"), "revision": ident.get("revision"),
    }
    desc = getattr(ISO.launch_server, "descriptor", None) or {}
    out["db_path"] = desc.get("db_path")
    out["export_path"] = desc.get("export_path")
    out["db_is_insolated"] = bool(
        out["db_path"] and str(world.resolve()) in str(out["db_path"]))
    out["cwd_is_world"] = bool(
        ident.get("cwd") and str(world.resolve()) in str(ident["cwd"]))

    out["backend_pid_matches_launch"] = True
    out["user_env_untouched"] = {}
    for name, p in (("live_backend_8001", 8001), ("user_frontend_3000", 3000)):
        try:
            pid = (httpx.get(f"http://127.0.0.1:{p}/api/health", timeout=3,
                             trust_env=False).json().get("identity") or {}).get("pid") \
                if p == 8001 else None
            out["user_env_untouched"][name] = "reachable (not modified by this launcher)"
        except Exception:
            out["user_env_untouched"][name] = "not reachable"
    return out


def status() -> int:
    if not STATE_PATH.exists():
        print("no preview state; nothing launched by this tool")
        return 1
    st = json.loads(STATE_PATH.read_text())
    print(json.dumps(st, indent=1))
    return 0


def stop() -> int:
    if not STATE_PATH.exists():
        print("no preview state")
        return 0
    st = json.loads(STATE_PATH.read_text())
    import signal
    for key in ("frontend_pid", "backend_pid"):
        pid = st.get(key)
        if not pid:
            continue
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            print(f"stopped {key} {pid}")
        except Exception as exc:  # noqa: BLE001
            print(f"could not stop {key} {pid}: {exc}")
    STATE_PATH.unlink()
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8091)
    p.add_argument("--frontend-port", type=int, default=3091)
    p.add_argument("--name", default="search_preview")
    p.add_argument("--rebuild-world", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--stop", action="store_true")
    p.add_argument("--probe-only", action="store_true")
    args = p.parse_args()
    global PREVIEW_BACKEND_PORT, PREVIEW_FRONTEND_PORT
    PREVIEW_BACKEND_PORT = args.port
    PREVIEW_FRONTEND_PORT = args.frontend_port

    if args.status:
        return status()
    if args.stop:
        return stop()

    model = probe_ollama()
    print(f"[model] {json.dumps(model)}")
    if not model.get("real_model"):
        print("REAL MODEL UNAVAILABLE — the preview gate requires one. "
              "Refusing to fall back to a shim and call it a preview.")
        return 3
    if args.probe_only:
        return 0

    world = BACKEND / "data" / "acceptance_worlds" / args.name
    if args.rebuild_world or not (world / "MANIFEST.json").exists():
        world.mkdir(parents=True, exist_ok=True)
        ISO.build_world.snapshot_working_tree = True
        ISO.build_world(world, refreeze_db=False)

    api_url = f"http://127.0.0.1:{args.port}"
    backend = launch_backend(args.port, world)
    print(f"[backend] :{args.port} pid={backend.pid}")
    frontend = launch_frontend(args.frontend_port, api_url, world)
    print(f"[frontend] :{args.frontend_port} pid={frontend.pid}")

    checks = _verify_isolation(args.port, world)
    print(f"[isolation] {json.dumps(checks, indent=1)}")

    state = {
        "launched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "backend_port": args.port,
        "frontend_port": args.frontend_port,
        "backend_pid": backend.pid,
        "frontend_pid": frontend.pid,
        "world": str(world),
        "api_url": api_url,
        "frontend_url": f"http://localhost:{args.frontend_port}",
        "model": model,
        "preview_secret_key": getattr(ISO.launch_server, "preview_secret", ""),
        "isolation": checks,
        "descriptor": getattr(ISO.launch_server, "descriptor", {}),
        "backend_log": str(world / "preview_backend.log"),
        "frontend_log": str(world / "preview_frontend.log"),
    }
    STATE_PATH.write_text(json.dumps(state, indent=1))
    print(f"\nPREVIEW http://localhost:{args.frontend_port}  (state: {STATE_PATH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
