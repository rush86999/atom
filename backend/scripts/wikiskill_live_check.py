"""Live-app verification for the WikiSkill adaptation (run against the
running dev server's real DB): ledger roundtrip, pattern store + index,
eval-gated playbook approval over HTTP, and one real maintenance cycle.
"""
import json
import sys
import time

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import jwt  # noqa: E402
import requests  # noqa: E402

BASE = "http://127.0.0.1:8011"
TENANT = "default"

# ── 1. mint a dev JWT the same way the backend validates it ────────────────
import os  # noqa: E402

def _backend_secret() -> str:
    env = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET")
    if env:
        return env
    # the app loads backend/.env; mirror its SECRET_KEY exactly
    with open("/Users/rushiparikh/projects/atom/backend/.env") as f:
        for line in f:
            if line.startswith(("SECRET_KEY=", "JWT_SECRET=")):
                return line.split("=", 1)[1].strip().strip("'\"")
    return open("/Users/rushiparikh/projects/atom/backend/data/.dev_secret_key").read().strip()

secret = _backend_secret()
token = jwt.encode({"sub": "8cce0c47-1471-4c3f-bf5f-6a01da01095f", "exp": int(time.time()) + 600},
                   secret, algorithm="HS256")
H = {"Authorization": f"Bearer {token}"}

from core.database import SessionLocal  # noqa: E402
from core.models import IncidentEval, KnowledgePattern  # noqa: E402
from core.auto_dev.models import SkillImpactEntry  # noqa: E402
from core.auto_dev.skill_impact_ledger import record_outcome, proposer_history_block  # noqa: E402
from core.knowledge_pattern_service import upsert_pattern, pattern_index, sample_traces  # noqa: E402

db = SessionLocal()
results = []

# ── 2. skill-impact ledger roundtrip on the live DB ────────────────────────
rid = record_outcome(db, tenant_id=TENANT, target="outlook.search_emails",
                     source="alpha_evolver", status="rejected", stage="regression",
                     reason="live-check: behavioral regression on 2 inputs",
                     proposal_summary="live pipeline check", diff="-x\n+y")
block = proposer_history_block(db, TENANT)
assert rid and "Do NOT re-propose" in block and "outlook.search_emails" in block
results.append(("W1 ledger write+read", "PASS"))

# ── 3. pattern store live: upsert, index, balanced sampler ─────────────────
row, created = upsert_pattern(db, tenant_id=TENANT, name="live-check pattern",
                              kind="failure_mode", root_cause="root cause from live run",
                              workaround="encode the query", evidence_id="live-ep-1")
occurrences = row.occurrence_count
idx = pattern_index(db, TENANT)
assert "live-check pattern" in idx and "[failure_mode]" in idx
sample = sample_traces(db, TENANT)
results.append(("W2/W3 pattern store + index + sampler",
                f"PASS (created={created}, occurrences={occurrences}, "
                f"failing={len(sample['failing'])}, passing={len(sample['passing'])})"))

# ── 4. playbook eval gate over the LIVE HTTP API ───────────────────────────
# 4a. plain draft (no origin evals): approve must succeed, gate vacuous
r = requests.post(f"{BASE}/api/playbooks", headers=H, json={
    "name": "WikiSkill live draft (no evals)", "steps": ["step one"],
    "approval_state": "draft"})
assert r.ok, r.text
pb_id = r.json()["id"]
r = requests.post(f"{BASE}/api/playbooks/{pb_id}/approve", headers=H)
body = r.json()
assert r.ok and body["success"] and body["approval_state"] == "approved", r.text
assert body.get("eval_gate", {}) is not None
results.append(("W5 API approve (no origin evals)", "PASS"))

# 4b. draft that ORIGINATED from a real IncidentEval: shadow replays it
ev = IncidentEval(tenant_id=TENANT, canvas_id="live-canvas", canvas_type="sheet",
                  taxonomy="process", instruction="always include the totals row",
                  context_snapshot={"canvas_type": "sheet", "title": "t", "content": "x"},
                  expected_property={"kind": "includes", "value": "totals"},
                  source="correction", fingerprint=f"fp-live-{time.time()}")
db.add(ev)
db.commit()
r = requests.post(f"{BASE}/api/playbooks", headers=H, json={
    "name": "WikiSkill live draft (with evals)", "steps": ["include totals row"],
    "approval_state": "draft"})
pb2 = r.json()["id"]
from core.playbook_service import PlaybookService  # noqa: E402
import asyncio  # noqa: E402
svc = PlaybookService(db, tenant_id=TENANT)
from sqlalchemy.orm import attributes  # noqa: E402
row = svc.get(pb2)
row.origin_ids = [ev.id]
db.commit()
gate = asyncio.get_event_loop().run_until_complete(svc.approve(pb2, actor="live-check"))
assert gate["approved"] is True          # shadow: replays then approves
assert gate["eval_gate"] is not None and gate["eval_gate"]["ran"] == 1
results.append(("W5 gated approve with origin eval replay", f"PASS (eval ran={gate['eval_gate']['ran']}, failed={gate['eval_gate']['failed']}, skipped={gate['eval_gate']['skipped']})"))

# ── 5. one real maintenance cycle against the live DB ──────────────────────
from core.exchange_memory_maintenance import run_maintenance_cycle  # noqa: E402
summary = asyncio.get_event_loop().run_until_complete(run_maintenance_cycle(db))
assert "patterns" in summary and "import_validation" in summary
results.append(("W2 maintenance cycle live", json.dumps(summary["patterns"])))

db.close()
print("\n".join(f"[{status}] {name}" for name, status in results))
print("ALL LIVE CHECKS PASSED")
