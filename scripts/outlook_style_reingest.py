"""Outlook style re-ingest (Sept 2026, one-off ops).

Re-ingests the Outlook mailbox from the configured beginning so existing
messages are re-processed with the styling-preservation ingestion (links as
markdown, raw HTML in metadata.html_body) instead of the old lossy
tag-stripping.

What it does (in order, with guards):
  1. REFUSES to run while the backend is up (the poller holds in-memory
     cursors and would rewrite the state file over our edits; writes must
     not race the server).
  2. SNAPSHOTS the lance table dir + poll_fetch_state.json into
     backend/data/backups/outlook-style-reingest-<ts>/.
  3. DELETES rows with app_type = 'outlook' from the default-workspace
     atom_communications table (store-level id guard would otherwise skip
     re-ingestion forever).
  4. CLEARS the outlook poll cursors + seen-id map in poll_fetch_state.json
     so the next poller boot re-walks the initial-sync window
     (outlook_history_days, currently 90).

Run:  python3 scripts/outlook_style_reingest.py   (from repo root, server STOPPED)
"""

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import urllib.request

BASE = Path("/Users/rushiparikh/projects/atom/backend")
STORE = BASE / "data" / "atom_memory" / "default"
TABLE_DIR = STORE / "atom_communications.lance"
STATE = STORE / "poll_fetch_state.json"
BACKUPS = BASE / "data" / "backups"
HEALTH = "http://127.0.0.1:8001/health"


def backend_running() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    if backend_running():
        print("REFUSING: backend is running on 8001 — stop it first "
              "(scripts/restart_backend.sh stops+starts; stop only, then run this).")
        sys.exit(1)
    if not TABLE_DIR.exists():
        print(f"REFUSING: table dir missing: {TABLE_DIR}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"outlook-style-reingest-{ts}"
    backup.mkdir(parents=True, exist_ok=True)

    import lancedb

    db = lancedb.connect(str(STORE))
    table = db.open_table("atom_communications")
    before = table.count_rows()
    outlook_before = table.count_rows(filter="app_type = 'outlook'")
    print(f"rows before: total={before} outlook={outlook_before}")

    # 1. Snapshot the table dir + state file.
    shutil.copytree(TABLE_DIR, backup / "atom_communications.lance")
    if STATE.exists():
        shutil.copy2(STATE, backup / "poll_fetch_state.json")
    print(f"snapshot -> {backup}")

    # 2. Purge outlook rows (store-level id guard would block re-ingestion).
    table.delete("app_type = 'outlook'")
    after_total = table.count_rows()
    after_outlook = table.count_rows(filter="app_type = 'outlook'")
    print(f"rows after purge: total={after_total} outlook={after_outlook}")
    if after_outlook != 0:
        print("REFUSING to finish: purge incomplete")
        sys.exit(1)

    # 3. Clear outlook cursors + seen ids so the poll re-walks the window.
    if STATE.exists():
        state = json.loads(STATE.read_text() or "{}")
        cursors = state.get("fetch_timestamps") or {}
        doomed = [k for k in cursors if k == "last_fetch_outlook" or k.startswith("last_fetch_outlook_")]
        for k in doomed:
            cursors.pop(k, None)
        seen = state.get("seen_message_ids") or {}
        if "outlook" in seen:
            seen["outlook"] = {}
        state["fetch_timestamps"] = cursors
        state["seen_message_ids"] = seen
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1))
        tmp.replace(STATE)
        print(f"cleared cursors: {doomed}")
    else:
        print("no poll state file — cursors already clean")

    print(f"\nDone at {datetime.now().isoformat()} (backup: {backup})")
    print("Start the backend now — the outlook poll re-walks "
          "outlook_history_days (90) and re-ingests with styling preserved.")


if __name__ == "__main__":
    main()
