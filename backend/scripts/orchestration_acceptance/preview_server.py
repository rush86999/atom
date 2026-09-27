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
_a = _ap.parse_args()
PORT, NAME = _a.port, _a.name
FRONTEND_ORIGINS = ",".join(
    o.strip() for o in _a.frontend_origin.split(",") if o.strip())
world = Path("/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds") / NAME
if not (world / "MANIFEST.json").exists():
    ri.build_world(world, refreeze_db=True)
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
os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = FRONTEND_ORIGINS
os.environ["ATOM_TASK_LIFECYCLE_ENABLED"] = "1"
os.environ["CHAT_FINALIZATION_M2"] = "1"
proc = ri.launch_server(PORT, world)
print(f"PREVIEW_SERVER_PID={proc.pid}")
print(f"PREVIEW_WORLD={world}")
print(f"PREVIEW_PORT={PORT}")
Path("/tmp/preview_server.pid").write_text(str(proc.pid))
