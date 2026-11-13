"""Actual-OS-process worker for the Generic information-wait restart row.

The parent pytest process launches this file as a *separate* interpreter. A
worker owns one phase of the scenario and serves the real public
``api.agent_routes`` router in a real uvicorn process against a scratch SQLite
store. Only ``LLMService.generate_structured`` is scripted (from a phase file
shared across processes), so the production ``GenericAgent._react_step``
schema/prompt/validation consumer and every lifecycle/registry seam run
unpatched. No provider, network, live credential or shared DB is used.

Phases are not selected by flags: the worker always boots the same app. The
parent kills the first process after the durable wait and starts a second one
against the same scratch root, which is the restart under test.

Honest seams: authentication uses the existing FastAPI dependency override for
the seeded principal (controlled API scope, not an ordinary login/browser
session), and boot calls the same ``core.execution_recovery`` helper that the
production lifespan calls rather than the full ``main_api_app`` lifespan. The
full application boot therefore remains outside this test's claim.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

SCRATCH = Path(os.environ["GENERIC_WAIT_SCRATCH"]).resolve()
DB_URL = os.environ["DATABASE_URL"]
PHASE_FILE = SCRATCH / "phase.json"
BOARD_ID = os.environ["GENERIC_WAIT_BOARD_ID"]
COLUMN_ID = os.environ["GENERIC_WAIT_COLUMN_ID"]
ANSWER = os.environ["GENERIC_WAIT_ANSWER"]
SOURCE_MODE = str(os.environ.get("GENERIC_WAIT_SOURCE_MODE") or "").strip()
SOURCE_MARKER = str(os.environ.get("GENERIC_WAIT_SOURCE_MARKER") or "")

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LANCEDB_URI", str(SCRATCH / "lance"))
os.environ.setdefault("LANCEDB_URI_BASE", str(SCRATCH / "lance"))

from fastapi import FastAPI  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from api.agent_routes import router as agent_router  # noqa: E402
from api.document_ingestion_routes import (  # noqa: E402
    router as document_ingestion_router,
)
from core.auth import get_current_user  # noqa: E402
from core.database import Base, get_db  # noqa: E402
from core.models import (  # noqa: E402
    AgentRegistry,
    IngestedDocument,
    Tenant,
    User,
    Workspace,
)
from core.models_board import Board, BoardColumn  # noqa: E402

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _seed() -> None:
    session = SessionLocal()
    try:
        if session.get(User, "member-1") is None:
            session.add_all([
                Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
                Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
                User(
                    id="member-1", tenant_id="t1", workspace_id="ws1",
                    email="member@example.com", first_name="M",
                    last_name="One", role="member", status="active",
                    is_active=True),
                AgentRegistry(
                    id="a1", name="Agent One", description="first",
                    category="operations", module_path="agents.one",
                    class_name="AgentOne", status="autonomous",
                    capabilities=[], promotion_episode_floor=None,
                    tenant_id="t1", workspace_id="ws1", configuration={},
                    enabled=True),
                Board(id=BOARD_ID, name="Generic wait board",
                      owner_user_id="member-1"),
                BoardColumn(id=COLUMN_ID, board_id=BOARD_ID, name="Backlog",
                            position=0),
            ])
        session.commit()
        source_id = str(os.environ.get("GENERIC_WAIT_SOURCE_ID") or "")
        if source_id and session.get(IngestedDocument, source_id) is None:
            source_path = os.environ["GENERIC_WAIT_SOURCE_PATH"]
            source_version = os.environ["GENERIC_WAIT_SOURCE_VERSION"]
            session.add(IngestedDocument(
                id=source_id,
                workspace_id="ws1",
                tenant_id="t1",
                file_name=os.environ["GENERIC_WAIT_SOURCE_NAME"],
                file_path=source_path,
                file_type="json",
                integration_id="upload",
                external_id=source_id,
                source_content_hash=source_version,
                freshness_status="fresh",
                content_preview=os.environ.get(
                    "GENERIC_WAIT_SOURCE_MARKER", "")[:500],
            ))
            session.commit()
            # Index the controlled fixture text into the real workspace
            # LanceDB documents table. The answer route persists a path-free
            # binding by design, so the existing reader consumes this index.
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler("ws1")
            if not handler.get_table("documents"):
                handler.create_table("documents")
            if not handler.get_document_by_id("documents", source_id):
                text = Path(source_path).read_text()
                try:
                    payload = json.loads(text)
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    text = json.dumps(payload, indent=2, sort_keys=True)
                stored = handler.add_document(
                    table_name="documents",
                    text=text,
                    source=os.environ["GENERIC_WAIT_SOURCE_NAME"],
                    metadata={
                        "source_content_hash": source_version,
                        "pg_document_id": source_id,
                        "workspace_id": "ws1",
                        "tenant_id": "t1",
                    },
                    user_id="member-1",
                    doc_id=source_id,
                    workspace_id="ws1",
                    extra_columns={"freshness_status": "fresh"},
                )
                if not stored:
                    raise RuntimeError("source fixture index write failed")
    finally:
        session.close()


_seed()


def _read_phase() -> dict:
    try:
        return json.loads(PHASE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {"step": 0}


def _write_phase(data: dict) -> None:
    tmp = PHASE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True))
    tmp.replace(PHASE_FILE)


async def _controlled_structured(
    self, prompt, response_model, system_instruction="", **kwargs
):
    """Script only the transport; the production consumer stays real."""
    from core.react_models import ReActStep

    assert response_model is ReActStep, response_model
    phase = _read_phase()
    step = int(phase.get("step") or 0)
    phase["step"] = step + 1
    phase.setdefault("prompts", []).append(prompt[:8000])
    _write_phase(phase)

    if step == 0:
        if SOURCE_MODE:
            payload = {
                "thought": "The authorized source is missing.",
                "information_wait": {
                    "question": "Which authorized source should be used?",
                    "missing_fact": "authorized source",
                },
            }
        else:
            payload = {
                "thought": "The closing task title is missing.",
                "information_wait": {
                    "question": "What title should the closing task have?",
                    "missing_fact": "title",
                },
            }
    elif step == 1:
        # The authorized answer must have reached the real prompt before the
        # resumed step is allowed to act on it.
        assert "AUTHORIZED INFORMATION ANSWER" in prompt, (
            "resumed prompt is missing the authorized answer section")
        if SOURCE_MODE:
            assert "AUTHORIZED SOURCE EVIDENCE" in prompt, (
                "resumed prompt is missing the source evidence section")
            assert SOURCE_MARKER in prompt, (
                "resumed prompt is missing the accepted source content")
            assert "untrusted evidence" in prompt, (
                "source evidence is not labelled untrusted")
            payload = {
                "thought": "The authorized source is available; create the task.",
                "action": {
                    "tool": "tasks.create",
                    "params": {
                        "board_id": BOARD_ID,
                        "column_id": COLUMN_ID,
                        "title": SOURCE_MARKER,
                        "status": "backlog",
                    },
                },
            }
        else:
            assert ANSWER in prompt, "resumed prompt is missing the answer text"
            payload = {
                "thought": "The authorized title is available; create the task.",
                "action": {
                    "tool": "tasks.create",
                    "params": {
                        "board_id": BOARD_ID,
                        "column_id": COLUMN_ID,
                        "title": ANSWER,
                        "status": "backlog",
                    },
                },
            }
    else:
        payload = {
            "thought": "The registered action result was verified.",
            "final_answer": "Created the task from the authorized title.",
        }
    return response_model.model_validate(payload)


from core.llm_service import LLMService  # noqa: E402

LLMService.generate_structured = _controlled_structured

# Test-only crash boundary. The parent kills a real process at the exact seam
# under test; the hook exists only in this disposable worker and is never
# imported by production code.
CRASH_MODE = os.environ.get("GENERIC_WAIT_CRASH", "").strip()
if CRASH_MODE:
    import api.agent_routes as _agent_routes

    _original_claim = _agent_routes._claim_waiting_job_for_resume

    def _crash_claim(*args, **kwargs):
        if CRASH_MODE == "before_claim":
            os._exit(17)
        _original_claim(*args, **kwargs)
        os._exit(17)

    _agent_routes._claim_waiting_job_for_resume = _crash_claim

# The real startup recovery owner runs before the app accepts requests. A
# durable information wait must be left untouched by orphan recovery.
recovery = {"ran": False}
try:
    from core.execution_recovery import reconcile_orphaned_executions

    recovery = {"ran": True, "result": reconcile_orphaned_executions()}
except Exception as exc:  # noqa: BLE001
    recovery = {"ran": False, "error": f"{type(exc).__name__}:{exc}"}
report = SCRATCH / f"recovery-{os.getpid()}.json"
report.write_text(json.dumps(recovery, indent=2, sort_keys=True, default=str))
print("WORKER_PID=" + str(os.getpid()), flush=True)
print("RECOVERY=" + json.dumps(recovery, default=str), flush=True)

# Owner-set absolute deadlines are enforced before any accepted-answer
# recovery, exactly as the production lifespan orders them. Jobs without a
# deadline are untouched, so this is inert for the legacy scenarios.
try:
    from core.information_wait import expire_due_information_waits

    expiry = {"ran": True, "result": expire_due_information_waits()}
except Exception as exc:  # noqa: BLE001
    expiry = {"ran": False, "error": f"{type(exc).__name__}:{exc}"}
expiry_report = SCRATCH / f"wait-expiry-{os.getpid()}.json"
expiry_report.write_text(
    json.dumps(expiry, indent=2, sort_keys=True, default=str))
print("WAIT_EXPIRY=" + json.dumps(expiry, default=str), flush=True)

# Optional actual startup-join behaviour: call the same recovery function the
# production lifespan wires in, before serving requests.
if os.environ.get("GENERIC_WAIT_RECOVER_ACCEPTED") == "1":
    import asyncio

    # Optional test barrier so two real startup processes can race the same
    # accepted wait. It is only used by the disposable process test.
    gate = os.environ.get("GENERIC_WAIT_RECOVERY_GATE", "")
    if gate:
        (SCRATCH / f"recovery-ready-{os.getpid()}.json").write_text("{}")
        deadline = time.time() + 60
        while not os.path.exists(gate) and time.time() < deadline:
            time.sleep(0.01)

    accepted = {"ran": False}
    try:
        from core.information_wait import drain_accepted_information_waits

        accepted = {
            "ran": True,
            "result": asyncio.run(drain_accepted_information_waits()),
        }
    except Exception as exc:  # noqa: BLE001
        accepted = {"ran": False, "error": f"{type(exc).__name__}:{exc}"}
    accepted_report = SCRATCH / f"accepted-recovery-{os.getpid()}.json"
    accepted_report.write_text(
        json.dumps(accepted, indent=2, sort_keys=True, default=str))
    print("ACCEPTED_RECOVERY=" + json.dumps(accepted, default=str), flush=True)

app = FastAPI()
app.include_router(agent_router)
app.include_router(document_ingestion_router)


def _session_dep():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _actor():
    session = SessionLocal()
    try:
        return session.get(User, "member-1")
    finally:
        session.close()


app.dependency_overrides[get_db] = _session_dep
app.dependency_overrides[get_current_user] = _actor


@app.get("/health")
def health():
    return {"status": "ok", "pid": os.getpid()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="127.0.0.1", port=int(os.environ["GENERIC_WAIT_PORT"]),
        log_level="warning")
