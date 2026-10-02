"""Extract real recorded decision data for the strands-decider spike.

Sources (read-only):
- docs/architecture/orchestration_migration/acceptance/fixtures/conversation_*.json
  (real dialogue extracted from backend/data/atom.db)
- backend/data/acceptance_worlds/learning_loop_01/shim_learning_loop.jsonl
  (real intercepted planner/intent LLM requests + authored served labels)

No DB connections. Writes eval_data/ JSON files.
"""
import json
import re
from pathlib import Path

REPO = Path("/Users/rushiparikh/projects/atom")
FIXTURES = REPO / "docs/architecture/orchestration_migration/acceptance/fixtures"
SHIM = REPO / "backend/data/acceptance_worlds/learning_loop_01/shim_learning_loop.jsonl"
OUT = Path(__file__).parent / "eval_data"
OUT.mkdir(exist_ok=True)

# Verbatim from backend/integrations/chat_orchestrator.py:733
_INABILITY_RE = re.compile(
    r"\b(i\s+(?:don't|do not|can't|cannot|can not|won't|will not|am unable|'m unable)"
    r"\s+(?:have|see|find|access|research|browse|check|reach|view)|"
    r"unable\s+to\s+(?:research|access|find|browse|check|view|reach)|"
    r"no\s+(?:access|ability|visibility)\s+to|"
    r"i\s+don't\s+have\s+(?:the\s+)?(?:ability|access|capability|tools?))",
    re.IGNORECASE,
)

turns = []
for f in sorted(FIXTURES.glob("conversation_*.json")):
    d = json.loads(f.read_text())
    for i, m in enumerate(d["messages"]):
        turns.append({"file": f.name, "idx": i, "role": m["role"],
                      "content": m["content"], "created_at": m.get("created_at")})

# --- Seam B: user messages (to be labeled by planner rubric) ---
user_msgs = []
for i, t in enumerate(turns):
    if t["role"] != "user":
        continue
    ctx = [x for x in turns[:i] if x["file"] == t["file"]][-3:]
    user_msgs.append({
        "id": f"{t['file']}#{t['idx']}",
        "content": t["content"],
        "context": [{"role": x["role"], "content": x["content"][:500]} for x in ctx],
    })
(OUT / "user_messages_for_labeling.json").write_text(json.dumps(user_msgs, indent=1))
print(f"user messages: {len(user_msgs)}")

# --- Seam C: assistant replies, mechanically labeled by the repo's regex ---
ability = []
for t in turns:
    if t["role"] != "assistant":
        continue
    m = _INABILITY_RE.search(t["content"])
    ability.append({"id": f"{t['file']}#{t['idx']}", "content": t["content"][:2000],
                    "inability_label": bool(m),
                    "match": m.group(0) if m else None})
pos = [a for a in ability if a["inability_label"]]
(OUT / "assistant_replies_inability.json").write_text(json.dumps(ability, indent=1))
print(f"assistant replies: {len(ability)}, inability positives: {len(pos)}")
for p in pos:
    print("  POS:", p["id"], "|", p["match"])

# --- Seam A: recorded CommandIntentResult examples ---
ci, tp = [], []
for line in SHIM.open():
    d = json.loads(line)
    names = d.get("tool_names") or []
    served = d.get("served_head") or ""
    try:
        args = json.loads(served).get("tool_call", {}).get("arguments", {})
    except json.JSONDecodeError:
        continue
    if "CommandIntentResult" in names and "command_type" in args:
        cmd = d.get("last_user", "")
        cmd = cmd[len("Command: "):] if cmd.startswith("Command: ") else cmd
        ci.append({"id": d.get("t"), "command": cmd[:2000],
                   "label": args["command_type"]})
    elif "ToolPlan" in names and "use_tool" in args:
        tp.append({"id": d.get("t"), "planner_user_prompt": d.get("last_user", ""),
                   "use_tool": args["use_tool"]})
(OUT / "command_intent_examples.json").write_text(json.dumps(ci, indent=1))
(OUT / "toolplan_recorded.json").write_text(json.dumps(tp, indent=1))
print(f"CommandIntentResult examples: {len(ci)}, ToolPlan recorded: {len(tp)}")
from collections import Counter
print("CI label distribution:", Counter(x["label"] for x in ci).most_common())
