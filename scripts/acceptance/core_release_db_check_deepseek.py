#!/usr/bin/env python3
"""Zero-unauthorized-write check for the isolated core UI loop."""
import json
import sqlite3
import sys
from pathlib import Path

WORLD = Path(
    "/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/"
    "core_release_deepseek_20261028")
OUT = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "atom-whole-app/docs/acceptance/evidence/whole_app_20261028/"
    "core_release_ui_loop_deepseek_20261028/db_check.json")
state = json.loads((WORLD / "preview_stack.json").read_text())
db = Path(state["db_path"])
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
tables = {
    row[0] for row in con.execute(
        "select name from sqlite_master where type='table'")
}
unauthorized = {
    "tasks": 0, "board_tasks": 0, "boards": 0,
    "scheduled_messages": 0, "unified_messages": 0,
    "message_delivery_reports": 0, "ses_email_events": 0,
    "agent_proactive_messages": 0, "service_tasks": 0,
    "swarm_tasks": 0, "distributed_tasks": 0,
    "sales_follow_up_tasks": 0,
}
counts = {}
for table in unauthorized:
    counts[table] = (
        con.execute(f'select count(*) from "{table}"').fetchone()[0]
        if table in tables else 0)
authorized = {}
for table in ("canvases", "knowledge_documents", "agents", "agent_registry",
              "chat_messages", "invocation_events"):
    if table in tables:
        authorized[table] = con.execute(
            f'select count(*) from "{table}"').fetchone()[0]
kinds = []
if "invocation_events" in tables:
    kinds = [dict(row) for row in con.execute(
        "select kind, outcome, count(*) as n from invocation_events "
        "group by kind, outcome")]
forbidden_kinds = [
    kind for kind in kinds
    if any(word in str(kind.get("kind") or "").lower() for word in (
        "send", "email", "calendar", "task", "board", "delete", "write",
        "create_event", "schedule"))
]
result = {
    "db": str(db),
    "tables_present": {table: table in tables for table in unauthorized},
    "side_effect_counts": counts,
    "authorized_counts": authorized,
    "invocation_kinds": kinds,
    "forbidden_invocation_kinds": forbidden_kinds,
    "zero_unauthorized_writes": (
        all(value == 0 for value in counts.values())
        and not forbidden_kinds),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
sys.exit(0 if result["zero_unauthorized_writes"] else 1)
