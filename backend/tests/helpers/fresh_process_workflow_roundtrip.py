"""Fresh-OS-process workflow roundtrip helper (test-only).

This process shares only the scratch SQLite database, the scratch JSON catalog
and ATOM_DATA_DIR with its parent. It authenticates as the real scratch user
via the existing dependency seam, uses the normal public routes, re-registers
the canonical SQL blueprint in this process, and runs the real read-only entity
lookup handler. It never calls a model and never mocks execution.

Usage (parent supplies the same scratch paths):
  python fresh_process_workflow_roundtrip.py run|verify ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys


def _fail(message: str) -> None:
    raise SystemExit(f"fresh-process failure: {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "verify", "export"))
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--execution-id", default="")
    parser.add_argument("--operation-id", default="")
    parser.add_argument("--owner-id", default="")
    args = parser.parse_args()

    if os.environ.get("TESTING") != "1":
        _fail("TESTING=1 is required")
    database_path = (
        args.db_url[len("sqlite:///"):]
        if args.db_url.startswith("sqlite:///") else "")
    if not database_path or not os.path.isabs(database_path):
        _fail("child database must be an absolute scratch SQLite path")
    if database_path.endswith("/backend/data/atom.db") or (
            database_path.endswith("/backend/dev.db")):
        _fail("child database points at a live/dev database")
    if not os.path.isabs(args.catalog):
        _fail("child catalog must be an absolute scratch path")
    if args.catalog.endswith("/backend/workflows.json"):
        _fail("child catalog points at the live catalog")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.auth as auth_module
    import core.database as database_module
    import core.workflow_endpoints as endpoints_module
    import ai.workflow_scheduler as scheduler_module
    from core.models import User
    from core.workflow_endpoints import router as workflow_router
    from advanced_workflow_api import router as advanced_router

    engine = create_engine(
        args.db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def get_db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    # The routes' Depends(get_db) captured the original function object; the
    # helper routes that call next(get_db()) read the module attribute.
    original_get_db = endpoints_module.get_db
    endpoints_module.WORKFLOWS_FILE = args.catalog
    endpoints_module.get_db = get_db_override

    db = Session()
    try:
        actor = db.query(User).filter(User.id == args.user_id).one()
    finally:
        db.close()
    if str(actor.tenant_id) != args.tenant_id:
        _fail("actor tenant does not match the requested scratch scope")
    if str(actor.workspace_id) != args.workspace_id:
        _fail("actor workspace does not match the requested scratch scope")

    class NoScheduler:
        def list_jobs(self):
            return []

        def schedule_workflow(self, *a, **k):
            raise AssertionError("fresh child attempted to schedule a workflow")

    scheduler_module.workflow_scheduler = NoScheduler()

    # A fresh child must not call a model at all. This guard fails loudly if
    # any execution path tries.
    from core.llm_service import LLMService
    from core.agents.queen_agent import QueenAgent

    def forbidden_model(*a, **k):
        raise AssertionError("fresh child attempted a model call")

    LLMService.generate_structured_response = forbidden_model
    QueenAgent.generate_workflow_blueprint = forbidden_model

    app = FastAPI()
    app.include_router(workflow_router, prefix="/api/v1/workflows")
    app.include_router(advanced_router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def override_user():
        db = Session()
        try:
            return db.query(User).filter(User.id == args.user_id).one()
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_db
    app.dependency_overrides[auth_module.get_current_user] = override_user

    client = TestClient(app)
    result = {
        "mode": args.mode,
        "workflow_id": args.workflow_id,
        "definition_digest": args.digest,
        "workflow_ids": None,
        "execution_id": args.execution_id or None,
        "execution_status": None,
        "execution_results": None,
        "execution_ids": None,
        "deploy_status": None,
        "operation_id": args.operation_id or None,
        "owner_user_id": args.owner_id or None,
        "scheduler_jobs": None,
        "model_calls": False,
        "export_sha256": None,
        "export_bytes": None,
        "export_filename": None,
        "export_schema": None,
        "export_execution_id": None,
        "export_workflow_id": None,
    }

    rows = client.get("/api/v1/workflows/workflows")
    if rows.status_code != 200:
        _fail(f"list failed: {rows.status_code} {rows.text[:300]}")
    listed = rows.json()
    result["workflow_ids"] = [row.get("id") for row in listed]
    if result["workflow_ids"] != [args.workflow_id]:
        _fail(f"unexpected My Workflows ids: {result['workflow_ids']}")
    deployment = listed[0].get("deployment") or {}
    if deployment.get("definition_digest") != args.digest:
        _fail("catalog digest does not match")
    if deployment.get("owner_user_id") != args.owner_id:
        _fail("catalog owner does not match")
    if deployment.get("operation_id") != args.operation_id:
        _fail("catalog operation id does not match")

    jobs = client.get("/api/v1/workflows/scheduler/jobs")
    if jobs.status_code != 200 or jobs.json() != []:
        _fail(f"unexpected scheduler jobs: {jobs.status_code} {jobs.text[:300]}")
    result["scheduler_jobs"] = jobs.json()

    if args.mode == "run":
        executed = client.post(
            f"/api/v1/workflows/workflows/{args.workflow_id}/execute",
            json={"fresh_process": True})
        if executed.status_code != 200:
            _fail(f"execute failed: {executed.status_code} "
                  f"{executed.text[:500]}")
        body = executed.json()
        result["execution_id"] = body.get("execution_id")
        result["execution_status"] = body.get("status")
        result["execution_results"] = body.get("results")
        if body.get("status") != "completed":
            _fail(f"execution did not complete: {body}")
        steps = {item.get("step_id"): item for item in body.get("results") or []}
        lookup = steps.get("lookup") or {}
        if lookup.get("status") != "completed" or "matches" not in lookup:
            _fail(f"real read-only lookup handler did not run: {steps}")
        history = client.get(
            f"/api/v1/workflows/workflows/{args.workflow_id}/executions")
        if history.status_code != 200:
            _fail(f"history failed: {history.status_code} {history.text[:300]}")
        result["execution_ids"] = [
            item.get("execution_id") for item in history.json()]
        if result["execution_ids"] != [result["execution_id"]]:
            _fail(f"unexpected execution rows: {result['execution_ids']}")
    elif args.mode == "verify":
        if not args.execution_id:
            _fail("verify mode requires --execution-id")
        detail = client.get(
            f"/api/v1/workflows/workflows/executions/{args.execution_id}")
        if detail.status_code != 200:
            _fail(f"execution readback failed: {detail.status_code} "
                  f"{detail.text[:500]}")
        persisted = detail.json()
        result["execution_status"] = persisted.get("status")
        result["execution_results"] = persisted.get("results")
        if persisted.get("status") != "completed":
            _fail(f"persisted execution is not completed: {persisted}")
        if str(persisted.get("execution_id")) != args.execution_id:
            _fail("persisted execution id changed")
        history = client.get(
            f"/api/v1/workflows/workflows/{args.workflow_id}/executions")
        if history.status_code != 200:
            _fail(f"history failed: {history.status_code} {history.text[:300]}")
        result["execution_ids"] = [
            item.get("execution_id") for item in history.json()]
        if result["execution_ids"] != [args.execution_id]:
            _fail(f"unexpected execution rows: {result['execution_ids']}")
        replay = client.post(
            f"/api/v1/workflows/workflows/{args.workflow_id}/deploy",
            json={"definition_digest": args.digest})
        if replay.status_code != 200:
            _fail(f"replay failed: {replay.status_code} {replay.text[:300]}")
        replay_body = replay.json()
        result["deploy_status"] = replay_body.get("status")
        result["operation_id"] = replay_body.get("operation_id")
        if replay_body.get("status") != "already_deployed":
            _fail(f"replay was not already_deployed: {replay_body}")
        if replay_body.get("operation_id") != args.operation_id:
            _fail("replay operation id changed")
        replay_jobs = client.get("/api/v1/workflows/scheduler/jobs")
        if replay_jobs.status_code != 200 or replay_jobs.json() != []:
            _fail(f"replay created a scheduler job: {replay_jobs.text[:300]}")
        result["scheduler_jobs"] = replay_jobs.json()

    if args.mode == "export":
        if not args.execution_id:
            _fail("export mode requires --execution-id")
        exported = client.get(
            f"/api/v1/workflows/workflows/executions/{args.execution_id}/export")
        if exported.status_code != 200:
            _fail(f"export failed: {exported.status_code} "
                  f"{exported.text[:500]}")
        body = exported.content
        result["export_sha256"] = hashlib.sha256(body).hexdigest()
        result["export_bytes"] = len(body)
        disposition = exported.headers.get("content-disposition") or ""
        match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
        result["export_filename"] = match.group(1) if match else None
        document = json.loads(body.decode("utf-8"))
        result["export_schema"] = document.get("schema")
        result["export_execution_id"] = (document.get("execution") or {}).get(
            "execution_id")
        result["export_workflow_id"] = (document.get("workflow") or {}).get(
            "workflow_id")

    print("RESULT_JSON:" + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
