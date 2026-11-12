"""MEM-07 restart twin: a reviewed prompt skill born from a REAL tool failure
is consumed by the ordinary Generic request path in a NEW OS process that
shares the same scratch durable state (SQLite file + workspace skills root).

What is real here:

* The failure feedstock: ``GenericAgent._step_act`` invokes a controlled
  local tool that raises; the error is recorded on the real
  ``AgentExecution.metadata_json["tool_errors"]``. ``EpisodeService`` then
  finalizes the run on the real event bus and the registered
  ``ReflectionEngine`` drives the real ``MementoEngine`` to a durable
  ``pending`` ``SkillCandidate``.
* Review and apply: the real mounted ``/api/autodev`` router with real JWT
  auth/role dependencies. Approval is not application; application writes a
  prompt-only package (no generated executable code) and assigns it to the
  reviewed workspace.
* Consumption: four separate OS processes start from the SAME scratch DB
  and skills root. Each runs the real ``GenericAgent._react_step`` prompt
  assembly (including ``SkillRetrievalService``) for the ordinary request.
  Only the model transport is doubled — ``generate_structured`` captures the
  exact request and returns a fixed ``ReActStep``; the raw ``generate``
  fallback is replaced with a tripwire. No provider/network is contacted.

Evidence sequence (marker = the candidate's own skill name):

1. pending candidate                -> marker absent from the model request
2. approved (``validated``) only    -> marker still absent
3. explicit apply (``promoted``)    -> marker present in a NEW process
4. same applied state, wrong scope  -> marker absent for a real agent in
   another workspace of the same tenant
5. generated code is never in any prompt/package, and the agent's stored
   configuration is unchanged.

Scope limits (stated, not claimed): this is not a whole-chat-surface proof;
the boundary exercised is ``GenericAgent._react_step``, the ordinary request
path exercised by the existing MEM-07 prompt-consumption controls. The child
process is a plain Python process, not the full ``main_api_app`` server —
no scheduler/ingestion workers, credentials, sends or live DB are involved.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

TASK = "look up the customer email in outlook"
REQUEST = "outlook customer email search"
GENERATED_CODE = "def repair_unknown_tool():\n    return 1"


_CHILD_SCRIPT = r"""
import asyncio
import json
import os
from pathlib import Path

expected = Path(os.environ["MEM07_EXPECTED_DB"]).resolve()

# First app import is the database module; freeze/verify scratch before any
# product surface is allowed to see the world.
from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("child refused without TESTING=1")

from core.database import SessionLocal
from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep

agent_id = os.environ["MEM07_AGENT_ID"]
workspace_id = os.environ["MEM07_WORKSPACE_ID"]
request = os.environ["MEM07_REQUEST"]

with SessionLocal() as db:
    row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).one()
    agent = GenericAgent(row, workspace_id=workspace_id)

captured = {}


async def capture_structured(**kwargs):
    captured.update(kwargs)
    return ReActStep(thought="controlled prompt capture", final_answer="PIN")


async def forbidden_generate(**kwargs):
    raise AssertionError(
        "raw model generate() was reached; the structured leaf should answer")


agent.llm.generate_structured = capture_structured
agent.llm.generate = forbidden_generate

step = asyncio.run(agent._react_step(
    request, memory={}, history="", context={}))

payload = {
    "pid": os.getpid(),
    "database_file": str(actual),
    "workspace_id": workspace_id,
    "agent_id": agent_id,
    "step_final_answer": step.final_answer,
    "system_instruction": captured.get("system_instruction"),
    "prompt": captured.get("prompt"),
    "model_arg": captured.get("model"),
    "response_model": getattr(captured.get("response_model"), "__name__", None),
}
Path(os.environ["MEM07_RESULT_FILE"]).write_text(json.dumps(payload))
"""


def _scratch_child_env(tmp_path: Path, db_path: Path) -> dict:
    """Freeze the child onto the parent's scratch world.

    ``TESTING=1`` alone makes ``core.database`` ignore ``DATABASE_URL`` and
    force ``backend/test_integration.db`` (core/database.py). Only the
    pytest-process branch honors an explicit non-dev URL, so the child sets
    ``PYTEST_VERSION`` too — the same documented pattern used by
    ``tests/test_mini_app_records_process_restart.py``. The child still never
    sees the LIVE dev DB because every path is pinned under ``tmp_path``.
    """
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in
               ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
            env.pop(key, None)
    data_dir = tmp_path / "data"
    skills_root = tmp_path / "skills"
    lancedb_dir = tmp_path / "lancedb"
    for directory in (data_dir, skills_root, lancedb_dir):
        directory.mkdir(parents=True, exist_ok=True)
    env.update({
        "TESTING": "1",
        "PYTEST_VERSION": "1",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ENVIRONMENT": "development",
        "ATOM_DATA_DIR": str(data_dir),
        "ATOM_WORKSPACE_SKILLS_ROOT": str(skills_root),
        "LANCEDB_URI": str(lancedb_dir),
        "LANCEDB_PATH": str(lancedb_dir),
        "LANCEDB_URI_BASE": str(lancedb_dir),
        "ATOM_SKILL_INJECTION_ENABLED": "true",
        "ATOM_MOCK_DATABASE": "false",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "REDIS_URL": "",
        "SENTRY_DSN": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MEM07_EXPECTED_DB": str(db_path.resolve()),
        "MEM07_REQUEST": REQUEST,
    })
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(BACKEND_DIR), str(REPO_ROOT)) if p)
    return env


def _assert_scratch(env: dict, tmp_path: Path) -> None:
    db_url = env["DATABASE_URL"]
    assert db_url.startswith("sqlite:///"), f"non-sqlite scratch URL: {db_url!r}"
    resolved = Path(db_url.partition("sqlite:///")[2]).resolve()
    assert tmp_path.resolve() in resolved.parents, (
        f"scratch refusal: DATABASE_URL {resolved} is not under tmp_path")
    for var in ("ATOM_DATA_DIR", "ATOM_WORKSPACE_SKILLS_ROOT",
                "LANCEDB_URI", "LANCEDB_PATH", "LANCEDB_URI_BASE"):
        path = Path(env[var]).resolve()
        assert tmp_path.resolve() in path.parents or path == tmp_path.resolve(), (
            f"scratch refusal: {var}={path} is not under tmp_path")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    from contextlib import contextmanager

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.setenv("ATOM_SKILL_INJECTION_ENABLED", "true")
    # Keep in-process memory handlers off the repository's data dir too.
    monkeypatch.setenv("LANCEDB_URI", str(tmp_path / "lancedb"))
    monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path / "lancedb"))
    monkeypatch.setenv("LANCEDB_PATH", str(tmp_path / "lancedb"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.models  # noqa: F401 - register tables on the shared Base
    from core.auto_dev import models as autodev_models  # noqa: F401
    from core.database import Base
    from core.models import (
        AgentExecution,
        AgentRegistry,
        Tenant,
        User,
        Workspace,
    )

    db_path = tmp_path / "mem07-process-restart.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()

    tenant = Tenant(
        id="tenant-mem07-restart", name="MEM-07 Restart Tenant",
        subdomain="mem07-restart")
    workspace = Workspace(
        id="ws-mem07-restart", name="MEM-07 Restart Workspace",
        tenant_id=tenant.id, metadata_json={"auto_dev": {"enabled": True}})
    other_workspace = Workspace(
        id="ws-mem07-other", name="MEM-07 Other Workspace",
        tenant_id=tenant.id, metadata_json={"auto_dev": {"enabled": True}})
    agent_config = {
        "system_prompt": "original",
        "capability_maturities": {"*": "intern"},
    }
    agent = AgentRegistry(
        id="agent-mem07-restart", name="MEM-07 Restart Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration=dict(agent_config), capabilities=[],
        workspace_id=workspace.id, tenant_id=tenant.id)
    other_agent = AgentRegistry(
        id="agent-mem07-other", name="MEM-07 Other Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration=dict(agent_config), capabilities=[],
        workspace_id=other_workspace.id, tenant_id=tenant.id)
    user = User(
        id="reviewer-mem07-restart", email="reviewer@example.invalid",
        hashed_password="x", first_name="R", last_name="V",
        role="workspace_admin", status="active",
        workspace_id=workspace.id, tenant_id=tenant.id, is_active=True)
    execution = AgentExecution(
        id="exec-mem07-restart", agent_id=agent.id, tenant_id=tenant.id,
        workspace_id=workspace.id, status="running", metadata_json={})
    db.add_all([tenant, workspace, other_workspace, agent, other_agent,
                user, execution])
    db.commit()

    @contextmanager
    def _session():
        # Same contract as the real helper: usable as ``with get_db_session()``
        # and as a plain factory by callers.
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("core.database.SessionLocal", factory)
    monkeypatch.setattr("core.database.get_db_session", _session)
    monkeypatch.setattr("core.generic_agent.get_db_session", _session)

    try:
        yield {
            "db": db, "factory": factory, "engine": engine, "path": db_path,
            "tmp_path": tmp_path, "monkeypatch": monkeypatch,
            "tenant": tenant, "workspace": workspace,
            "other_workspace": other_workspace, "agent": agent,
            "other_agent": other_agent, "user": user,
            "agent_config": agent_config, "execution_id": execution.id,
        }
    finally:
        db.close()
        engine.dispose()


def _controlled_memento_llm(monkeypatch, calls):
    """Only the Memento model transport is doubled; lifecycle is real."""
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=lambda **kw: calls.append(kw) or {
            "content": GENERATED_CODE})
    monkeypatch.setattr(
        "core.auto_dev.memento_engine.MementoEngine._get_llm_service",
        lambda self: llm)
    return llm


def _pending_candidate(world):
    """Drive a real tool failure through the real event-bus consumer."""
    from core.auto_dev.event_hooks import event_bus
    from core.auto_dev.models import SkillCandidate
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.episode_service import EpisodeService
    from core.generic_agent import GenericAgent

    saved = (
        list(event_bus._fail_handlers),
        list(event_bus._success_handlers),
        list(event_bus._skill_handlers),
    )
    event_bus._fail_handlers[:] = []
    calls = []
    _controlled_memento_llm(world["monkeypatch"], calls)
    ReflectionEngine(db=None, failure_threshold=1).register()

    async def _run():
        agent = GenericAgent(
            world["agent"], workspace_id=world["workspace"].id)

        def boom(_args, _context):
            raise RuntimeError("400 Syntax error on the customer email search")

        agent._custom_actions = {"unknown.tool": boom}
        context = {
            "execution_id": world["execution_id"],
            "tenant_id": world["tenant"].id,
            "run_id": "run-mem07-restart",
            "operation_id": "op-mem07-restart",
        }
        for _ in range(2):
            result = await agent._step_act("unknown.tool", {}, context)
            assert "Error" in result

        world["db"].expire_all()
        from core.models import AgentExecution

        execution = world["db"].query(AgentExecution).filter(
            AgentExecution.id == world["execution_id"]).one()
        assert execution.metadata_json["tool_errors"]

        episode = await EpisodeService(
            world["db"]).create_episode_from_execution(
                world["execution_id"], TASK, outcome="success", success=True,
                metadata={})
        assert episode.success is False
        assert episode.outcome == "partial"

        # The registered consumer runs on this loop; poll a fresh session for
        # the durable pending candidate it commits.
        for _ in range(300):
            await asyncio.sleep(0.01)
            with world["factory"]() as fresh:
                rows = fresh.query(SkillCandidate).filter(
                    SkillCandidate.agent_id == world["agent"].id).all()
                if rows:
                    assert len(rows) == 1
                    assert rows[0].validation_status == "pending"
                    assert calls, "controlled Memento leaf was not reached"
                    return rows[0]
        raise AssertionError(
            "the emitted failure event did not create a pending candidate")

    try:
        return asyncio.run(_run())
    finally:
        (event_bus._fail_handlers[:],
         event_bus._success_handlers[:],
         event_bus._skill_handlers[:]) = saved


def _http_client(world):
    """Real mounted review router + real JWT auth on the scratch DB."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.autodev_review_routes import router as review_router
    from core.auth import create_access_token
    from core.database import get_db

    app = FastAPI()
    app.include_router(review_router)

    def _db():
        session = world["factory"]()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    user = world["user"]
    token = create_access_token({"sub": user.id}, user=user)
    return (
        TestClient(app, raise_server_exceptions=False),
        {"Authorization": f"Bearer {token}"},
    )


def _run_child(env: dict, tmp_path: Path, name: str, agent_id: str,
               workspace_id: str) -> dict:
    result_file = tmp_path / f"{name}-result.json"
    child_env = dict(
        env, MEM07_AGENT_ID=agent_id, MEM07_WORKSPACE_ID=workspace_id,
        MEM07_RESULT_FILE=str(result_file))
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT],
        cwd=str(BACKEND_DIR), env=child_env, capture_output=True, text=True,
        timeout=90)
    assert completed.returncode == 0, (
        f"child {name} failed rc={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    assert result_file.is_file(), (
        f"child {name} produced no result\nstdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}")
    payload = json.loads(result_file.read_text())
    assert payload["pid"] != os.getpid(), f"{name} must be a separate OS process"
    assert Path(payload["database_file"]).resolve() == Path(
        env["MEM07_EXPECTED_DB"]).resolve()
    assert payload["step_final_answer"] == "PIN"
    assert payload["response_model"] == "ReActStep"
    return payload


def test_reviewed_prompt_skill_is_consumed_after_os_process_restart(
        world, tmp_path):
    candidate = _pending_candidate(world)
    marker = candidate.skill_name
    description = (candidate.skill_description or "").strip()
    generated_code = candidate.generated_code
    assert marker
    assert TASK in description
    assert generated_code == GENERATED_CODE

    db_path = world["path"]
    env = _scratch_child_env(tmp_path, db_path)
    _assert_scratch(env, tmp_path)
    from core.models import Skill, SkillExecution

    # 1) Pending is not permission: ordinary work in a fresh OS process sees
    # nothing, and no typed skill rows exist.
    pending_view = _run_child(
        env, tmp_path, "child_pending", world["agent"].id,
        world["workspace"].id)
    assert marker not in (pending_view["system_instruction"] or "")
    assert "The following skills may be relevant" not in (
        pending_view["system_instruction"] or "")
    assert world["db"].query(Skill).count() == 0
    assert world["db"].query(SkillExecution).count() == 0

    client, headers = _http_client(world)

    # 2) Review alone changes nothing in the ordinary request path.
    approved = client.post(
        f"/api/autodev/skills/{candidate.id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "validated", approved.text
    reviewed_view = _run_child(
        env, tmp_path, "child_reviewed", world["agent"].id,
        world["workspace"].id)
    assert marker not in (reviewed_view["system_instruction"] or "")
    assert world["db"].query(Skill).count() == 0

    # 3) The explicit apply is what writes the prompt skill (no code).
    applied = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert applied.status_code == 200, applied.text
    applied_data = applied.json()["data"]
    assert applied_data["status"] == "promoted", applied_data
    assert applied_data["generated_code_applied"] is False, applied_data

    package = next(
        (tmp_path / "skills" / world["tenant"].id / "skills").glob(
            f"{marker}_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert description in markdown
    assert generated_code not in markdown
    assert not list(package.rglob("*.py"))

    world["db"].expire_all()
    world["db"].refresh(world["agent"])
    assert world["agent"].configuration == world["agent_config"]
    current = world["db"].query(type(candidate)).filter(
        type(candidate).id == candidate.id).one()
    assert current.validation_status == "promoted"
    assert current.generated_code == GENERATED_CODE

    # 4) NEW OS process on the SAME durable state: the ordinary Generic
    # request path actually consumes the reviewed prompt skill.
    applied_view = _run_child(
        env, tmp_path, "child_applied", world["agent"].id,
        world["workspace"].id)
    system = applied_view["system_instruction"] or ""
    assert marker in system, applied_view
    assert description in system
    assert "The following skills may be relevant to the current task:" in system
    assert generated_code not in system
    assert REQUEST in (applied_view["prompt"] or "")

    # 5) Wrong scope: a real agent in another workspace of the same tenant
    # must not consume the skill, even in a fresh process on the same DB.
    other_view = _run_child(
        env, tmp_path, "child_other_workspace", world["other_agent"].id,
        world["other_workspace"].id)
    other_system = other_view["system_instruction"] or ""
    assert marker not in other_system
    assert "The following skills may be relevant" not in other_system
    assert len({
        pending_view["pid"], reviewed_view["pid"],
        applied_view["pid"], other_view["pid"],
    }) == 4
