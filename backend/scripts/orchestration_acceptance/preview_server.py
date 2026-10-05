"""Launch a PERSISTENT isolated preview backend and leave it running.

Reuses the acceptance runner's world build and launch recipe, so the
preview server is the same code under test, in the same isolated world,
with the same preflight — it just does not stop at the end of a case, so
a human can open the app against it.

    venv314/bin/python scripts/orchestration_acceptance/preview_server.py \
        --port 8090 --name preview_app --frontend-origin http://127.0.0.1:3090

Why the frontend origin is part of the LAUNCHER rather than a shell
export: the browser treats a different port as cross-origin, so the API
must allow it or the CORS preflight fails and login reports "Unable to
connect to the server". The value is injected through
SERVER_ENV_WHITELIST because launch_server builds its own environment
and ignores any dict passed to it — setting the variable in the caller's
shell alone silently did nothing.
"""
import importlib.util, os, sys, time
from pathlib import Path

os.chdir("/Users/rushiparikh/projects/atom/backend")
spec = importlib.util.spec_from_file_location(
    "ri", "scripts/orchestration_acceptance/run_isolated.py")
ri = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ri)

import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--port", type=int, default=8090)
_ap.add_argument("--name", default="preview_app")
_ap.add_argument("--frontend-origin", default="http://127.0.0.1:3090",
                 help="origin(s) the preview frontend is served from; "
                      "comma-separated for several")
# STORAGE POLICY: the full dev database is opt-in. Without this flag the
# world is built from the small API-seeded fixture (app schema, zero dev
# rows) and the live dev database is never read.
_ap.add_argument("--full-dev-db-snapshot", dest="full_dev_db",
                 action="store_true",
                 help="copy the FULL live dev database into this world "
                      "(~412 MB, plus ~400-550 MB per run directory seeded "
                      "from it, and the world inherits the dev lane's rows)")
_a = _ap.parse_args()
PORT, NAME = _a.port, _a.name
SP_FULL_DEV_DB = bool(_a.full_dev_db)
# Established local real-model configuration (no live credentials).
_MODEL_DEFAULTS = {
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
    "OLLAMA_MODELS": "llama3.1:8b,o4-mini",
    "OLLAMA_LOAD_TIMEOUT": "15m",
    "ATOM_PROVIDER": "ollama",
    "ATOM_DEFAULT_MODEL": "llama3.1:8b",
    "PREFERRED_PROVIDER": "ollama",
    "OPENAI_API_KEY": "local-ollama-not-a-secret",
    "ATOM_PROVIDER_MODEL_CATALOG_PATH": "",
}
FRONTEND_ORIGINS = ",".join(
    o.strip() for o in _a.frontend_origin.split(",") if o.strip())
world = Path("/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds") / NAME
# Refuse to build or serve a world unless worlds storage is in the configured
# state and no maintenance lock is held. Note this path is hardcoded (not
# derived from __file__) because the preview is launched from a different
# working directory; the guard's config is anchored to backend/ instead, so
# the two agree on which tree is under protection.
ri.require_storage_ready()
if not (world / "MANIFEST.json").exists():
    # STORAGE POLICY: the default fixture is the small API-seeded one (app
    # schema, zero dev rows, live dev database never read). Pass
    # --full-dev-db-snapshot to this launcher to get the previous behaviour,
    # which copied the whole ~412 MB live dev database into the world.
    ri.build_world(world, refreeze_db=True, full_dev_db=SP_FULL_DEV_DB)
    print("world built")
env = {k: os.environ[k] for k in ri.SERVER_ENV_WHITELIST if k in os.environ}
env.update({
    "DATABASE_URL": f"sqlite:///{world / 'runs' / 'preview' / 'data' / 'atom.db'}",
    "ATOM_DATA_DIR": str(world / "runs" / "preview" / "data"),
    "LANCEDB_URI": str(world / "data" / "atom_memory"),
    "ATOM_SHEET_DATASETS": "1",
    "ATOM_CHAT_STREAMING": "1",
    "ATOM_TASK_LIFECYCLE_ENABLED": "1",
    "CHAT_FINALIZATION_M2": "1",
    "ENABLE_SCHEDULER": "false",
    "ENABLE_INGESTION_SYNC": "false",
    "ACC_PORT": str(PORT),
    # The preview frontend runs on its own port, so the browser treats it
    # as a cross-origin request and the API must allow it or the CORS
    # preflight fails and the POST is never sent. This widens CORS for the
    # PREVIEW world only; the usual development origins are untouched.
    "ADDITIONAL_ALLOWED_ORIGINS": FRONTEND_ORIGINS,
    "PYTHONDONTWRITEBYTECODE": "1",
})
# launch_server builds its own environment from SERVER_ENV_WHITELIST and
# ignores any dict we assemble here, so the CORS origin has to go through
# the whitelist to reach the process. Verified: an origin in the default
# list preflights 200 while ours returned 400 until this was set.
if "ADDITIONAL_ALLOWED_ORIGINS" not in ri.SERVER_ENV_WHITELIST:
    ri.SERVER_ENV_WHITELIST = tuple(ri.SERVER_ENV_WHITELIST) + (
        "ADDITIONAL_ALLOWED_ORIGINS",)

# Real-model (local Ollama) configuration must reach the preview process the
# same way. launch_server rebuilds the environment from SERVER_ENV_WHITELIST,
# so exporting these in the caller's shell alone silently does nothing --
# which is exactly how a preview ended up with no usable model while still
# reporting itself as a real-model preview. OPENAI_API_KEY here is the local
# Ollama placeholder, never a live credential.
_MODEL_ENV = (
    "OLLAMA_BASE_URL", "OLLAMA_MODELS", "OLLAMA_LOAD_TIMEOUT",
    "ATOM_PROVIDER", "ATOM_DEFAULT_MODEL", "PREFERRED_PROVIDER",
    "ATOM_PROVIDER_MODEL_CATALOG_PATH", "OPENAI_API_KEY",
)
ri.SERVER_ENV_WHITELIST = tuple(ri.SERVER_ENV_WHITELIST) + tuple(
    k for k in _MODEL_ENV if k not in ri.SERVER_ENV_WHITELIST)
# PIN, do not default. A developer's shell can already export these -- one
# had OLLAMA_MODELS=/Volumes/Seagate, a volume path in a variable that
# expects a model list. setdefault() would defer to that, the model list
# would resolve to nothing, and the preview would silently fall back to a
# non-local provider while still looking like a real-model preview. The
# preview's model configuration is therefore set unconditionally.
for _k in _MODEL_ENV:
    if _k in _MODEL_DEFAULTS:
        os.environ[_k] = _MODEL_DEFAULTS[_k]
    else:
        os.environ.pop(_k, None)
os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = FRONTEND_ORIGINS
os.environ["ATOM_TASK_LIFECYCLE_ENABLED"] = "1"
os.environ["CHAT_FINALIZATION_M2"] = "1"
proc = ri.launch_server(PORT, world)
print(f"PREVIEW_SERVER_PID={proc.pid}")
print(f"PREVIEW_WORLD={world}")
print(f"PREVIEW_PORT={PORT}")
Path("/tmp/preview_server.pid").write_text(str(proc.pid))
