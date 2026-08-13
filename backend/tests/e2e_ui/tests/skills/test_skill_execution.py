"""
E2E tests for skill execution workflow (WORK-03) — API-first.

The frontend ships no skills execution UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers). The real execution surface
is the backend community-skills registry:

    POST /api/skills/import       — register a skill (returns skill_id)
    POST /api/skills/execute      — run it (governance-checked)
    GET  /api/skills/{skill_id}   — execution detail / history lookup

Tests drive that API against the LIVE backend on :8001 with an API-minted
token and verify the source of truth (SkillExecution rows) through db_session.
Keyless by design:

- prompt_only execution is pure template interpolation
  (core/skill_adapter.py::_execute_prompt_skill) — no LLM call.
- python_code execution requires a Docker sandbox; on this stack Docker is
  unavailable, so python runs deterministically FAIL via the sandbox error
  path (still an honest governance/error-handling assertion).
- import runs an LLM security scan that fails open (risk UNKNOWN), so the
  import status is asserted loosely (Active|Untrusted).

Requirements covered:
- WORK-03: User can execute skill with parameters and output parses correctly
- WORK-03: Skill execution output is valid JSON (response envelope)
- WORK-03: Skill execution history is tracked

Run with: pytest backend/tests/e2e_ui/tests/skills/test_skill_execution.py -v
"""

import json
import uuid

import pytest
import requests

from core.models import SkillExecution

from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def import_skill(token: str, name: str, body: str) -> dict:
    """Import a community skill via the live registry API."""
    content = f"---\nname: {name}\ndescription: E2E skill {name}\n---\n\n{body}"
    response = requests.post(
        f"{API}/api/skills/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "raw_content", "content": content, "metadata": {"author": "e2e"}},
        timeout=30,
    )
    assert response.status_code == 200, (
        f"Import should succeed, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert data["success"] is True, data
    return data["data"]


def prompt_skill_body() -> str:
    """Deterministic prompt_only skill body (no LLM needed to run it)."""
    return "You are a calculator. Answer the user's query.\n\n{{query}}"


def python_skill_body() -> str:
    """Python skill body — sandbox execution, deterministically fails without Docker."""
    return (
        "```python\n"
        "def execute(inputs):\n"
        "    query = inputs.get('query', '')\n"
        "    return {'result': f'Processed: {query}'}\n"
        "```\n"
    )


def execute_skill(token: str, skill_id: str, inputs: dict, agent_id: str = "system") -> requests.Response:
    """Execute a skill via the live registry API.

    The python sandbox path can take >60s to fail when no Docker daemon is
    running (docker client read timeout), so the client timeout is generous.
    """
    return requests.post(
        f"{API}/api/skills/execute",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": skill_id, "inputs": inputs, "agent_id": agent_id},
        timeout=180,
    )


# ============================================================================
# Tests
# ============================================================================

def test_execute_skill_with_parameters(setup_test_user, db_session):
    """Test skill execution with parameters (WORK-03).

    A prompt skill templated on {{query}} executes with parameters, returns
    the interpolated output, and records an execution row with the inputs.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"ParamExec-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "What is 2+2?"})
    assert response.status_code == 200, (
        f"Execute should return 200, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert data["success"] is True, data
    assert data["data"]["execution_id"], data
    assert "2+2" in data["data"]["result"], data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["data"]["execution_id"]
    ).first()
    assert execution is not None, "Execution row should exist"
    assert execution.status == "success", execution.status
    assert execution.input_params == {"query": "What is 2+2?"}
    assert execution.output_result is not None
    assert "2+2" in execution.output_result["result"]


def test_skill_output_json_validation(setup_test_user, db_session):
    """Test skill output JSON validation (WORK-03).

    The execution API returns a JSON envelope (success/result/execution_id)
    and persists structured output in output_result — both must parse.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"JsonExec-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "test", "format": "json"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload["success"] is True, payload
    assert isinstance(payload["data"]["result"], str)
    assert "test" in payload["data"]["result"]

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == payload["data"]["execution_id"]
    ).first()
    assert isinstance(execution.output_result, dict)
    assert "result" in execution.output_result

    json.dumps(payload)  # envelope round-trips as JSON


def test_skill_execution_error_handling(setup_test_user, db_session):
    """Test skill execution error handling (WORK-03).

    Two error surfaces:
    1. Governance: a STUDENT agent executing a python skill → HTTP 400 and no
       execution row (the block precedes the insert).
    2. Sandbox: python execution without Docker fails deterministically → the
       API reports success:false with an error and the row is marked failed.
    """
    token = setup_test_user["access_token"]

    student_agent = create_test_agent_direct(
        db_session,
        name="SubdirStudentExecAgent",
        status="STUDENT",
    )
    python_skill = import_skill(token, f"ErrorPython-{uuid.uuid4().hex[:8]}", python_skill_body())

    blocked = execute_skill(
        token, python_skill["skill_id"], {"query": "run"}, agent_id=student_agent["agent_id"]
    )
    assert blocked.status_code == 400, (
        f"STUDENT python execution should be blocked with 400, got {blocked.status_code}"
    )

    db_session.expire_all()
    blocked_rows = db_session.query(SkillExecution).filter(
        SkillExecution.agent_id == student_agent["agent_id"]
    ).all()
    assert len(blocked_rows) == 0, "Blocked attempt must not create an execution row"

    failed = execute_skill(token, python_skill["skill_id"], {"query": "invalid input"})
    assert failed.status_code in (200, 202), f"got {failed.status_code}: {failed.text[:300]}"
    data = failed.json()["data"]
    assert data["success"] is False, data
    assert data["error"], data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution is not None
    assert execution.status == "failed", execution.status
    assert execution.error_message, "error_message should be recorded"


def test_skill_execution_history(setup_test_user, db_session):
    """Test skill execution history tracking (WORK-03).

    Multiple executions create independent history records keyed by
    "{skill_name}_{skill_pk[:8]}"; each completes with a timestamp.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"HistoryExec-{uuid.uuid4().hex[:8]}", prompt_skill_body())
    exec_key = f"{skill['skill_name']}_{skill['skill_id'][:8]}"

    execution_ids = []
    for i in range(3):
        response = execute_skill(token, skill["skill_id"], {"query": f"test {i}"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is True, data
        execution_ids.append(data["execution_id"])

    assert len(set(execution_ids)) == 3, "Each execution gets a distinct id"

    db_session.expire_all()
    executions = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).all()
    assert len(executions) >= 3
    for exec_id in execution_ids:
        execution = db_session.query(SkillExecution).filter(SkillExecution.id == exec_id).first()
        assert execution is not None
        assert execution.status == "success", execution.status
        assert execution.completed_at is not None, "completed_at should be set after run"


@pytest.mark.skip(reason="Progress indicators are frontend-only (no skills UI); long-running sandbox runs require a Docker daemon that this stack lacks — deterministic coverage is via test_skill_execution_history.")
def test_long_running_skill_execution(authenticated_page_api, db_session):
    """Test long-running skill execution with progress (WORK-03)."""
    pass
