#!/usr/bin/env python3
"""Restart the isolated DeepSeek world without changing its declared config."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

WORLD = Path(
    "/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/"
    "core_release_deepseek_20261028")
BACKEND_ROOT = WORLD / "backend_root"
STATE = json.loads((WORLD / "preview_stack.json").read_text())
RUN = Path(STATE["run_dir"])
ENV_FILE = RUN / "server_env.json"
PYTHON = "/Users/rushiparikh/projects/atom/backend/venv314/bin/python"
APP = str(Path(__file__).resolve().parents[2]
          / "backend/scripts/orchestration_acceptance/_app.py")

old = int(STATE["backend_pid"])
try:
    os.kill(old, 15)
except ProcessLookupError:
    pass
for _ in range(40):
    try:
        os.kill(old, 0)
        time.sleep(0.5)
    except ProcessLookupError:
        break

env = dict(os.environ)
env.update(json.loads(ENV_FILE.read_text()))
bp = int(STATE["backend_port"])
fp = int(STATE.get("frontend_port") or 3114)
env["ACC_PORT"] = str(bp)
env["ADDITIONAL_ALLOWED_ORIGINS"] = (
    f"http://localhost:{fp},http://127.0.0.1:{fp}")
env["ALLOWED_HOSTS"] = (
    f"localhost,127.0.0.1,localhost:{bp},127.0.0.1:{bp},"
    f"localhost:{fp},127.0.0.1:{fp},testserver")
env["ATOM_REVIEW_CAPTURE"] = "1"
# No local-only/provider overrides here: the declared child environment is
# loaded verbatim from server_env.json.
log = (WORLD / "preview_backend.log").open("ab")
proc = subprocess.Popen([PYTHON, APP], cwd=str(BACKEND_ROOT), env=env,
                        stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True)
base = f"http://127.0.0.1:{bp}"
ok = False
for _ in range(240):
    if proc.poll() is not None:
        break
    try:
        response = httpx.get(base + "/api/health", timeout=3, trust_env=False)
        if response.status_code == 200:
            ok = True
            break
    except Exception:
        pass
    time.sleep(0.5)
if not ok:
    print(json.dumps({"ok": False, "pid": proc.pid}))
    sys.exit(1)
ident = httpx.get(
    base + "/api/health", timeout=10, trust_env=False).json().get(
        "identity", {})
STATE["backend_pid"] = proc.pid
STATE["backend_health_identity"] = ident
(WORLD / "preview_stack.json").write_text(
    json.dumps(STATE, indent=2, sort_keys=True))
print(json.dumps({"ok": True, "pid": proc.pid, "health": ident}, default=str))
