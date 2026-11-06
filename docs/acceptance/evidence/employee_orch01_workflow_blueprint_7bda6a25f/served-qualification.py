"""One two-case served qualification for ORCH-01.

Uses the already-configured local Ollama route, one single-flight structured
call per case. No expected blueprint is supplied. The durable store is an
isolated scratch SQLite file.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11436/v1")
os.environ.setdefault("OLLAMA_MODEL", "llama3.1:8b")
os.environ.setdefault("OLLAMA_CONTEXT_WINDOW", "16384")
os.environ.setdefault(
    "ATOM_LLM_PROVIDER_POLICY",
    '{"mode":"selected","allowed_providers":["ollama"],"preferred":'
    '{"provider":"ollama","model":"llama3.1:8b"}}')
os.environ.setdefault("ATOM_WORKFLOW_BLUEPRINT_DEADLINE_SECONDS", "180")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agents.queen_agent import QueenAgent
from core.agents.workflow_blueprint import (
    BlueprintValidationError, WorkflowBlueprintDraft, compile_blueprint,
)
from core.database import Base
from core.employee_attempt_journal import AttemptJournal
from core.llm.pinned_planning import pinned_structured_call
from core.llm_service import LLMService
from core.models import Tenant, User
from core.workflow_blueprint_service import load_blueprint, persist_blueprint

TENANT = "tenant-orch"
WORKSPACE = "ws-orch"
USER = "user-orch"

CASES = [
    {
        "case": "service_intake_review",
        "mode": "one_off",
        "prompt": (
            "Design a one-off service intake and review workflow: intake the "
            "request, triage it, notify the reviewer, and record the review "
            "decision. Read-only analysis must not need approval; any send "
            "or state change must be gated."),
    },
    {
        "case": "inventory_operations_review",
        "mode": "recurring_automation",
        "prompt": (
            "Design a recurring inventory operations review workflow that "
            "runs every Monday at 8am: collect stock counts, compare them "
            "with thresholds, and update the stock review record. The trigger "
            "is a schedule, not a manual run."),
    },
]


async def main():
    root = Path(tempfile.mkdtemp(prefix="orch01-served-"))
    engine = create_engine(f"sqlite:///{root}/orch01.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add(Tenant(id=TENANT, name="ORCH Tenant", subdomain="orch-tenant"))
    db.add(User(
        id=USER, email="orch@example.com", hashed_password="x",
        first_name="O", last_name="R", role="member", status="active",
        workspace_id=WORKSPACE, tenant_id=TENANT, is_active=True))
    db.commit()

    llm = LLMService(db=None, workspace_id=WORKSPACE, tenant_id=TENANT)
    queen = QueenAgent(
        db=None, llm=llm, workspace_id=WORKSPACE, tenant_id=TENANT)
    output = {
        "schema": "orch01-served-qualification-1",
        "route": {
            "provider": "ollama", "model": "llama3.1:8b",
            "base_url": os.environ["OLLAMA_BASE_URL"],
            "profile": "workflow_blueprint",
        },
        "scope": {
            "tenant_id": TENANT, "workspace_id": WORKSPACE, "user_id": USER,
        },
        "cases": [],
        "model_calls": 0,
    }
    for case in CASES:
        record = {
            "case": case["case"], "mode": case["mode"],
            "prompt": case["prompt"],
            "started_at": time.time(),
        }
        journal = AttemptJournal()
        provenance = {}
        prompt_text = queen._workflow_blueprint_prompt(
            case["prompt"], case["mode"])
        record["structured_prompt"] = prompt_text
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                pinned_structured_call(
                    llm,
                    prompt=prompt_text,
                    response_model=WorkflowBlueprintDraft,
                    system_instruction=(
                        "You are a workflow architect. Design only. "
                        "Return JSON only."),
                    temperature=0.0,
                    task_type="planning",
                    capability_profile="workflow_blueprint",
                    workspace_id=WORKSPACE,
                    tenant_id=TENANT,
                    attempt_observer=journal.record,
                    provenance=provenance,
                    extra_kwargs={
                        "max_tokens": 4096,
                        "output_mode": "json",
                    },
                ),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            result = None
            record["timeout"] = True
        record["elapsed_seconds"] = time.monotonic() - started
        output["model_calls"] += 1
        record["journal"] = journal.events
        record["provenance"] = provenance
        if result is None:
            record["status"] = "no_result"
            output["cases"].append(record)
            continue
        draft = result.model_dump() if hasattr(result, "model_dump") else result
        record["draft"] = draft
        try:
            compiled = compile_blueprint(
                draft, execution_mode=case["mode"])
        except BlueprintValidationError as exc:
            record["status"] = "validation_failed"
            record["validation_error"] = {
                "code": exc.code, "message": exc.message,
                "details": exc.details,
            }
            output["cases"].append(record)
            continue
        record["compiled"] = compiled
        try:
            stored = persist_blueprint(
                db, compiled=compiled, tenant_id=TENANT,
                workspace_id=WORKSPACE, user_id=USER,
                route_reasoning="served qualification",
                provenance={
                    "profile": "workflow_blueprint",
                    "routing": provenance,
                    "attempt_id": journal.attempt_id,
                })
            fresh = Session()
            readback = load_blueprint(
                fresh, workflow_id=stored["workflow_id"],
                tenant_id=TENANT, workspace_id=WORKSPACE)
            fresh.close()
            record["persisted"] = stored
            record["readback"] = readback
            record["readback_exact"] = bool(
                readback and readback.get("definition_digest")
                == stored.get("definition_digest")
                and readback.get("steps") == stored.get("steps"))
            record["status"] = "accepted"
        except Exception as exc:  # noqa: BLE001 — preserve the exact boundary
            record["status"] = "persistence_failed"
            record["persistence_error"] = f"{type(exc).__name__}: {exc}"
            db.rollback()
        output["cases"].append(record)
    output["completed_at"] = time.time()
    out = Path("/private/tmp/orch01-served-qualification.json")
    out.write_text(json.dumps(output, indent=1, default=str) + "\n")
    print(json.dumps({
        "output": str(out),
        "model_calls": output["model_calls"],
        "cases": [
            {
                "case": c["case"], "status": c["status"],
                "elapsed": c.get("elapsed_seconds"),
                "workflow_id": (c.get("persisted") or {}).get("workflow_id"),
                "readback_exact": c.get("readback_exact"),
                "validation_error": c.get("validation_error"),
            }
            for c in output["cases"]
        ],
    }, indent=1, default=str)[:4000])

asyncio.run(main())
