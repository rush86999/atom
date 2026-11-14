"""Real Docker replay for reviewed benign executable skills.

This is the hosted-CI acceptance twin of
``tests/test_reviewed_executable_skill.py``.  It requires a reachable Docker
daemon because the reviewed executable path has **no host fallback**: execution
goes through the existing registry -> ``HazardSandbox`` Docker container.

Run locally:
    pytest tests/test_reviewed_executable_skill_docker.py  # skips if no Docker

Hosted CI must fail if the container cannot run:
    ATOM_REQUIRE_DOCKER_SANDBOX=1 pytest tests/test_reviewed_executable_skill_docker.py

What is real here:

* the reviewed candidate is approved (``mark_reviewed``) and applied through
  the real ``apply_reviewed_skill(..., executable=True)`` code path;
* a brand-new OS process (fresh interpreter, fresh SQLAlchemy engine records)
  signs in through the real ``POST /api/auth/login`` JWT route against the
  scratch SQLite file, then calls the ordinary authorized
  ``POST /api/skills/execute`` route;
* execution runs the exact registered SKILL.md python block in a real
  ``skill_*`` Docker container with network disabled and a read-only rootfs;
* the container echoes a per-execution nonce, so the persisted receipt proves
  this execution's container ran; and the durable ``SkillExecution`` row is
  re-read from the parent process with the JSON result, digests and receipt.

Provider is simulated: the LLM security scan is stubbed to LOW so no
provider/network/credential is contacted.  The Docker sandbox is real.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

BENIGN_CODE = (
    "def execute(inputs):\n"
    "    values = inputs.get(\"values\", [])\n"
    "    return {\"count\": len(values), \"sum\": sum(values), "
    "\"maximum\": max(values) if values else None}\n"
)
SYNTHETIC_INPUTS = {"values": [3, 5, 7, 11]}
EXPECTED_RESULT = {"count": 4, "maximum": 11, "sum": 26}
PASSWORD = "synthetic-executable-password-1"
RESULT_PREFIX = "ATOM_REVIEWED_EXECUTABLE_RESULT="


class _FakeScanner:
    """Simulated LLM security scan: no provider, no network."""

    async def scan_skill(self, skill_name, skill_content):
        return {"safe": True, "risk_level": "LOW", "findings": []}


def _docker_unavailable_reason():
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return None
    except Exception as exc:  # noqa: BLE001 - reported verbatim
        return f"{type(exc).__name__}: {exc}"


def _source_revision() -> str:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=30)
        if completed.returncode == 0:
            return completed.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _approve_via_public_route(db, *, reviewer, viewer, candidate_id):
    """Approve through the public endpoint with real bearer-token sessions.

    The viewer must be refused (authority), and the reviewer's approval must
    return the exact scope+material digest that apply/execute enforce.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.autodev_review_routes import router
    from core.auto_dev.models import SkillCandidate
    from core.auth import create_access_token
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db

    def _headers(principal):
        token = create_access_token(
            {"sub": principal.id, "type": "access"}, user=principal)
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        denied = client.post(
            f"/api/autodev/skills/{candidate_id}/approve",
            headers=_headers(viewer))
        assert denied.status_code == 403, denied.text
        db.expire_all()
        refused = db.query(SkillCandidate).filter(
            SkillCandidate.id == candidate_id).one()
        assert not (refused.validation_result or {}).get("review")

        approved = client.post(
            f"/api/autodev/skills/{candidate_id}/approve",
            headers=_headers(reviewer))
    assert approved.status_code == 200, approved.text
    return approved.json()["data"]


_CHILD_SCRIPT = r"""
import json
import os
from pathlib import Path

expected = Path(os.environ["ATOM_EXECUTABLE_EXPECTED_DB"]).resolve()

from core.database import engine

actual = Path(engine.url.database).resolve()
if not engine.url.drivername.startswith("sqlite") or actual != expected:
    raise SystemExit(f"child refused a non-scratch database: {engine.url}")
if os.environ.get("TESTING") != "1":
    raise SystemExit("child refused without TESTING=1")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.skill_routes import router as skill_router
from core.auth_endpoints import router as auth_router
from core.security.auth_rate_limit import login_rate_limit

app = FastAPI()
app.include_router(auth_router)
app.include_router(skill_router)
app.dependency_overrides[login_rate_limit] = lambda: None

client = TestClient(app)
login = client.post("/api/auth/login", json={
    "username": os.environ["ATOM_EXECUTABLE_EMAIL"],
    "password": os.environ["ATOM_EXECUTABLE_PASSWORD"],
})
if login.status_code != 200:
    raise SystemExit(f"fresh login failed: {login.status_code} {login.text}")
token = login.json()["access_token"]

response = client.post(
    "/api/skills/execute",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "skill_id": os.environ["ATOM_EXECUTABLE_REGISTRY_ID"],
        "inputs": json.loads(os.environ["ATOM_EXECUTABLE_INPUTS"]),
        "agent_id": os.environ["ATOM_EXECUTABLE_AGENT_ID"],
    },
)
payload = {
    "status_code": response.status_code,
    "body": response.json() if response.headers.get(
        "content-type", "").startswith("application/json") else response.text,
}
print("ATOM_REVIEWED_EXECUTABLE_RESULT=" + json.dumps(payload, sort_keys=True))
"""


def _child_env(scratch: Path, *, db_path: Path, email: str,
               registry_id: str, agent_id: str, secret_key: str) -> dict:
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in
               ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
            env.pop(key, None)
    data_dir = scratch / "data"
    skills_root = scratch / "skills"
    lancedb_dir = scratch / "lancedb"
    for directory in (data_dir, skills_root, lancedb_dir):
        directory.mkdir(parents=True, exist_ok=True)
    env.update({
        "TESTING": "1",
        # The child is not pytest, but this is the documented branch that
        # honors an explicit non-dev scratch DATABASE_URL.
        "PYTEST_VERSION": "1",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "SECRET_KEY": secret_key,
        "ENVIRONMENT": "development",
        "ATOM_DATA_DIR": str(data_dir),
        "ATOM_WORKSPACE_SKILLS_ROOT": str(skills_root),
        "LANCEDB_URI": str(lancedb_dir),
        "LANCEDB_PATH": str(lancedb_dir),
        "LANCEDB_URI_BASE": str(lancedb_dir),
        "PYTHONPATH": str(BACKEND_DIR),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ATOM_EXECUTABLE_EXPECTED_DB": str(db_path),
        "ATOM_EXECUTABLE_EMAIL": email,
        "ATOM_EXECUTABLE_PASSWORD": PASSWORD,
        "ATOM_EXECUTABLE_REGISTRY_ID": registry_id,
        "ATOM_EXECUTABLE_AGENT_ID": agent_id,
        "ATOM_EXECUTABLE_INPUTS": json.dumps(SYNTHETIC_INPUTS),
    })
    return env


def test_reviewed_executable_runs_in_real_docker(tmp_path, monkeypatch):
    reason = _docker_unavailable_reason()
    if reason is not None:
        if os.getenv("ATOM_REQUIRE_DOCKER_SANDBOX") == "1":
            pytest.fail(
                "ATOM_REQUIRE_DOCKER_SANDBOX=1 but the Docker daemon is not "
                f"reachable: {reason}")
        pytest.skip(f"Docker daemon unavailable: {reason}")

    from core.auto_dev.models import SkillCandidate
    from core.auth import get_password_hash
    from core.database import Base
    from core.models import (
        AgentRegistry,
        SkillExecution,
        Tenant,
        User,
        Workspace,
    )
    from core.reviewed_improvement import apply_reviewed_skill
    from core.skill_builder_service import SkillBuilderService
    from core.skill_registry_service import SkillRegistryService

    scratch = tmp_path / "reviewed-executable-docker"
    scratch.mkdir()
    db_path = scratch / "scratch.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()

    tenant_id = "tenant-executable-docker"
    workspace_id = "ws-executable-docker"
    agent_id = "agent-executable-docker"
    user_id = "user-executable-docker"
    viewer_id = "viewer-executable-docker"
    email = "executable@example.invalid"
    try:
        db.add_all([
            Tenant(id=tenant_id, name="Executable Tenant",
                   subdomain="executable-docker"),
            Workspace(id=workspace_id, name="Executable Workspace",
                      tenant_id=tenant_id),
            AgentRegistry(
                id=agent_id, name="Executable Employee",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", status="intern",
                confidence_score=0.5, configuration={}, capabilities=[],
                workspace_id=workspace_id, tenant_id=tenant_id),
            User(
                id=user_id, email=email,
                hashed_password=get_password_hash(PASSWORD),
                first_name="E", last_name="X", role="workspace_admin",
                status="active", workspace_id=workspace_id,
                tenant_id=tenant_id, is_active=True),
            User(
                id=viewer_id, email="viewer-executable@example.invalid",
                hashed_password=get_password_hash(PASSWORD),
                first_name="V", last_name="X", role="viewer",
                status="active", workspace_id=workspace_id,
                tenant_id=tenant_id, is_active=True),
        ])
        candidate = SkillCandidate(
            id=f"cand-executable-docker-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id, agent_id=agent_id,
            source_episode_id="episode-executable-docker",
            skill_name="docker_summarize_values",
            skill_description="deterministically summarize synthetic integers",
            generated_code=BENIGN_CODE,
            failure_pattern={"failure_summary": "synthetic docker replay"},
            validation_status="pending")
        db.add(candidate)
        db.commit()

        # Reviewer authority + exact digest through the PUBLIC approval route.
        reviewer = db.query(User).filter(User.id == user_id).one()
        viewer = db.query(User).filter(User.id == viewer_id).one()
        approved = _approve_via_public_route(
            db, reviewer=reviewer, viewer=viewer, candidate_id=candidate.id)
        db.expire_all()
        candidate = db.query(SkillCandidate).filter(
            SkillCandidate.id == candidate.id).one()
        review = candidate.validation_result["review"]
        from core.reviewed_improvement import _binding_digest
        expected_digest = _binding_digest(
            candidate, tenant_id=tenant_id, workspace_id=workspace_id,
            agent_id=agent_id)
        assert approved["review_digest"] == review["digest"] == expected_digest
        assert approved["review_revision"] == review["review_revision"] == 1
        assert review["reviewed_by"] == user_id
        assert review["tenant_id"] == tenant_id
        assert review["workspace_id"] == workspace_id
        assert review["agent_id"] == agent_id

        monkeypatch.setattr(
            "core.skill_registry_service.SkillSecurityScanner", _FakeScanner)
        applied = asyncio.run(apply_reviewed_skill(
            db, candidate, tenant_id=tenant_id, workspace_id=workspace_id,
            builder=SkillBuilderService(workspace_root=str(scratch / "skills")),
            registry=SkillRegistryService(db),
            executable=True,
        ))
        assert applied["generated_code_applied"] is True
        assert applied["review_digest"] == approved["review_digest"]
        assert applied["review_revision"] == approved["review_revision"]
        registry_id = applied["registry_execution_id"]

        # The registered artifact (Skill row + registry package) must be the
        # approved revision, not merely a matching response field.
        from core.models import Skill
        from core.reviewed_executable import (
            registered_executable_code,
            sha256_text,
        )

        registered_code = registered_executable_code(candidate.generated_code)
        registered_sha = sha256_text(registered_code)
        skill_row = db.query(Skill).filter(
            Skill.id == applied["skill_id"]).one()
        assert skill_row.code == registered_code
        assert skill_row.type == "script"
        assert skill_row.config["sandbox"] == "docker"
        assert skill_row.config["reviewed_executable"]["review_digest"] == (
            approved["review_digest"])
        registry_row = db.query(SkillExecution).filter(
            SkillExecution.id == registry_id).one()
        binding = registry_row.input_params["reviewed_executable"]
        assert binding["review_digest"] == approved["review_digest"]
        assert binding["review_revision"] == approved["review_revision"]
        assert binding["executable_code_sha256"] == registered_sha
        assert binding["candidate_code_sha256"] == sha256_text(
            candidate.generated_code)
        db.close()

        secret_key = "synthetic-reviewed-executable-docker-secret"
        child = subprocess.run(
            [sys.executable, "-c", _CHILD_SCRIPT],
            cwd=str(BACKEND_DIR),
            env=_child_env(
                scratch, db_path=db_path, email=email,
                registry_id=registry_id, agent_id=agent_id,
                secret_key=secret_key),
            capture_output=True, text=True, timeout=600,
        )
        assert child.returncode == 0, (
            f"child failed ({child.returncode})\nstdout:\n{child.stdout}\n"
            f"stderr:\n{child.stderr}")
        marker = [
            line for line in child.stdout.splitlines()
            if line.startswith(RESULT_PREFIX)]
        assert marker, f"child produced no result marker:\n{child.stdout}"
        payload = json.loads(marker[-1][len(RESULT_PREFIX):])
        assert payload["status_code"] == 200, payload
        data = payload["body"]["data"]
        assert data["success"] is True, data
        assert json.loads(data["result"]) == EXPECTED_RESULT
        receipt = data["reviewed_executable"]
        sandbox = receipt["sandbox"]
        assert sandbox["backend"] == "docker"
        assert sandbox["ran"] is True
        assert sandbox["container_id"].startswith("skill_")
        assert sandbox["image"] == "python:3.11-slim"
        assert sandbox["network_disabled"] is True
        assert sandbox["read_only"] is True
        assert sandbox["ephemeral"] is True
        assert sandbox["nonce"] and sandbox["nonce"] == sandbox["nonce_echo"]
        assert receipt["binding"]["executable_code_sha256"] == (
            applied["executable_code_sha256"])

        # Durable receipt: the parent process re-reads the row from the same
        # scratch file after the child exited.
        verify = factory()
        try:
            execution = verify.query(SkillExecution).filter(
                SkillExecution.id == data["execution_id"]).one()
            assert execution.status == "success"
            assert execution.output_result["result"] == data["result"]
            assert execution.container_id == sandbox["container_id"]
            persisted = execution.audit_metadata["reviewed_executable"]
            assert persisted["sandbox"]["ran"] is True
            assert persisted["sandbox"]["nonce_echo"] == sandbox["nonce"]
            assert persisted["binding"]["review_revision"] == (
                applied["review_revision"])
            assert persisted["binding"]["review_digest"] == (
                applied["review_digest"])
        finally:
            verify.close()

        record = {
            "source_revision": _source_revision(),
            "provider_simulated": True,
            "provider_detail": "LLM security scan stubbed to LOW",
            "docker_sandbox_real": True,
            "sandbox_backend": sandbox["backend"],
            "container_id": sandbox["container_id"],
            "image": sandbox["image"],
            "nonce_echo_verified": True,
            "result": json.loads(data["result"]),
            "execution_id": data["execution_id"],
            "registry_execution_id": registry_id,
            "candidate_code_sha256": applied["candidate_code_sha256"],
            "executable_code_sha256": applied["executable_code_sha256"],
            "review_revision": applied["review_revision"],
            "review_digest": applied["review_digest"],
        }
        print("REVIEWED_EXECUTABLE_ACCEPTANCE=" + json.dumps(
            record, sort_keys=True))
        output = os.getenv("ATOM_ACCEPTANCE_OUTPUT")
        if output:
            Path(output).write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
    finally:
        db.close()
        engine.dispose()
