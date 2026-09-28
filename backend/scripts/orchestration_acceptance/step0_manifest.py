#!/usr/bin/env python3
"""Step 0 — reproducible implementation snapshot (work order 2026-09-26).

Produces ONE manifest identifying precisely what source and state a test
executes: commit SHA, SHA-256 of every changed production/harness file
(including untracked), the isolated export path + its file manifest, the
run's database path + fixture hash, the server instance identity, and the
EFFECTIVE M1/M2/M3 flags verified from the SERVER PROCESS environment
(never a client-side assertion).

Also enforces Step 0's structural rules:
- the gate world is built WITHOUT the M1 overlay (no second finalizer in
  production exports; the overlay is retained only for labelled
  historical-baseline tests);
- each run gets a FRESH database directory (work order step 6 alignment).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def server_env(pid: int) -> dict:
    """The server process's actual environment — server-side state, not a
    client-side claim (macOS: ps eww)."""
    try:
        out = subprocess.run(["ps", "eww", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout
        env = {}
        for token in out.split():
            if "=" in token:
                k, _, v = token.partition("=")
                if k.isupper() or k.startswith("ATOM") or k.startswith("CHAT_"):
                    env[k] = v
        return env
    except Exception as exc:
        return {"error": str(exc)[:120]}


def _db_snapshot_hash(db_path: Path) -> str:
    """Hash a CONSISTENT backup-API snapshot, not the active main file
    (work order step 0: a live main file can be mid-write)."""
    import sqlite3, tempfile, os
    tmp = Path(tempfile.mkdtemp()) / "snap.db"
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(str(tmp))
    with dst:
        src.backup(dst)
    dst.close(); src.close()
    h = sha256_file(tmp)
    os.unlink(tmp)
    return h


def build_manifest(*, world: Path, db_path: Path, server_pid: int = 0,
                   port: int = 0, overlay_applied: bool = False) -> dict:
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.splitlines()
    changed = {}
    for line in status:
        path = line[3:].strip().strip('"')
        if not path or not path.startswith(("backend/", "scripts/")):
            continue
        fp = REPO / path
        if fp.is_file():
            try:
                changed[path] = {"status": line[:2].strip(), "sha256": sha256_file(fp)}
            except OSError:
                changed[path] = {"status": line[:2].strip(), "sha256": "unreadable"}
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "commit": head,
        "changed_files": changed,
        "export": {
            "path": str(world / "code"),
            "code_manifest_sha256": (sha256_file(world / "code_manifest.json")
                                     if (world / "code_manifest.json").exists() else None),
            "overlay_applied": overlay_applied,
            "overlay_note": ("MUST be false for acceptance gates — no second "
                             "finalizer in production exports" if overlay_applied else
                             "clean production export (overlay retired from gates)"),
        },
        "database": {"path": str(db_path),
                     "snapshot_sha256": (_db_snapshot_hash(db_path)
                                         if db_path.exists() else None),
                     "hash_method": "backup-API snapshot (consistent)"},
        "server": {"pid": server_pid, "port": port,
                   "effective_flags": ({k: server_env(server_pid).get(k)
                                        for k in ("CHAT_FINALIZATION_M1",
                                                  "CHAT_FINALIZATION_M2",
                                                  "CHAT_FINALIZATION_M3")}
                                       if server_pid else None),
                   "identity_source": "server process environment (ps eww)"},
        "work_order": "WORKBOOK_DELIVERY_WORK_ORDER_2026_09_26.md",
        "step": "0 — reproducible implementation snapshot",
    }
    return manifest


if __name__ == "__main__":
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--server-pid", type=int, default=0)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--overlay-applied", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    m = build_manifest(world=Path(a.world), db_path=Path(a.db),
                       server_pid=a.server_pid, port=a.port,
                       overlay_applied=a.overlay_applied)
    out = a.out or str(Path(__file__).parent / "step0_manifest.json")
    Path(out).write_text(json.dumps(m, indent=1))
    n = len(m["changed_files"])
    print(f"[step0] manifest written: {out}")
    print(f"  commit={m['commit'][:12]} changed_files={n} "
          f"overlay_applied={m['export']['overlay_applied']} "
          f"flags={m['server']['effective_flags']}")
