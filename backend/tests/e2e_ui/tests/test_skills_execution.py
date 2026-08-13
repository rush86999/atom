"""
E2E tests for skill execution workflow (SKILL-04) — API-first.

The frontend ships no skills execution UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers; pages/marketplace.tsx is the
workflow-templates marketplace). The real execution surface is the backend
community-skills registry:

    POST /api/skills/import            — register a skill (returns skill_id)
    POST /api/skills/execute           — run it (governance-checked)
    GET  /api/skills/{skill_id}        — execution detail / history lookup

These tests drive that API against the LIVE backend on :8001 with an
API-minted token and verify the source of truth (SkillExecution rows) through
db_session. Keyless by design:

- prompt_only execution is pure template interpolation
  (core/skill_adapter.py::_execute_prompt_skill) — no LLM call.
- python_code execution requires a Docker sandbox; on this stack Docker is
  unavailable, so python runs deterministically FAIL via the sandbox error
  path (still an honest governance/error-handling assertion).
- import runs an LLM security scan that fails open (risk UNKNOWN), so the
  import status is asserted loosely (Active|Untrusted).

Run with: pytest tests/e2e_ui/tests/test_skills_execution.py -v
"""

import json
import requests
import uuid
from datetime import datetime, timezone

import pytest

from core.models import SkillExecution

# Import fixtures/helpers
from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def import_skill(token: str, name: str, body: str) -> dict:
    """Import a community skill via the live registry API.

    Args:
        token: API JWT
        name: Skill name (frontmatter)
        body: Markdown skill body

    Returns:
        Parsed import response data (skill_id, skill_name, status, scan_result)
    """
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


def naive_utc_now():
    """SQLite stores naive datetimes regardless of DateTime(timezone=True)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================================
# Test Cases
# ============================================================================

def test_skill_execution_from_marketplace(setup_test_user, db_session):
    """Test executing a skill end-to-end: import → execute → DB record.

    SKILL-04: a skill registered in the registry can be executed and the
    execution is recorded. This is the marketplace→execute flow (there is no
    marketplace UI; the registry list is the marketplace surface).
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"ExecFromMarketplace-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "What is 2+2?"})
    assert response.status_code == 200, (
        f"Execute should return 200, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert data["success"] is True, data
    assert data["data"]["execution_id"], data
    assert len(data["data"]["result"]) > 0, data

    # DB source of truth: execution row recorded with success + output
    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["data"]["execution_id"]
    ).first()
    assert execution is not None, "Execution row should exist"
    assert execution.status == "success", execution.status
    assert execution.output_result is not None
    assert "2+2" in execution.output_result["result"]


def test_skill_execution_from_chat(setup_test_user, db_session):
    """Test skill execution attributed to a registered INTERN agent.

    There is no chat→skill UI; the chat-equivalent path is an agent-triggered
    execution, so this runs the API with a seeded INTERN agent and verifies
    the execution is attributed to it in the DB.
    """
    token = setup_test_user["access_token"]
    agent = create_test_agent_direct(
        db_session,
        name="TestChatExecutionAgent",
        status="INTERN",
    )
    skill = import_skill(token, f"ExecFromChat-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "hello"}, agent_id=agent["agent_id"])
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    data = response.json()
    assert data["success"] is True, data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["data"]["execution_id"]
    ).first()
    assert execution is not None
    assert execution.agent_id == agent["agent_id"], execution.agent_id


def test_execution_progress_indicator(setup_test_user, db_session):
    """Test the execution lifecycle lands in a completed state.

    There is no progress-bar UI; progress is the execution record's state
    machine (running → success/failed). Verify the final state and completion
    timestamp are recorded for a successful run.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"ProgressSkill-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "long running task"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True, data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["data"]["execution_id"]
    ).first()
    assert execution.status == "success"
    assert execution.completed_at is not None, "completed_at should be set after run"


def test_text_output_display(setup_test_user, db_session):
    """Test plain-text output is produced and persisted.

    prompt_only output is the interpolated prompt (template + user query);
    verify the API result and the persisted output_result carry it.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"TextOutput-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "test query"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True, data

    result = data["data"]["result"]
    assert "test query" in result, result

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["data"]["execution_id"]
    ).first()
    assert execution.output_result is not None
    assert "test query" in execution.output_result["result"]


def test_json_output_display(setup_test_user, db_session):
    """Test the JSON response envelope and structured output record.

    The execution API returns a JSON envelope (success/result/execution_id)
    and persists structured output in output_result — verify both parse.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"JsonOutput-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "test", "format": "json"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload["success"] is True, payload
    assert isinstance(payload["data"]["result"], str)

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == payload["data"]["execution_id"]
    ).first()
    assert isinstance(execution.output_result, dict)
    assert "result" in execution.output_result


@pytest.mark.skip(reason="Canvas presentation output requires the frontend canvas host + execution UI, which do not exist for skills (no pages/skills/*); covered by canvas clusters for agents.")
def test_canvas_output_display(authenticated_page, db_session):
    """Test canvas presentation output display (requires canvas frontend)."""
    pass


def test_execution_success_message(setup_test_user, db_session):
    """Test the success response surfaces the execution id and records it.

    SKILL-04: the execute response carries a success message with the
    execution_id and the row completes with a recent timestamp.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"SuccessMsg-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(token, skill["skill_id"], {"query": "test"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True, payload
    assert "execution_id" in payload["data"]

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == payload["data"]["execution_id"]
    ).first()
    assert execution is not None
    assert execution.status == "success"
    assert execution.completed_at is not None
    assert (naive_utc_now() - execution.completed_at).total_seconds() < 10


def test_execution_error_handling(setup_test_user, db_session):
    """Test error handling: failed python execution is surfaced and recorded.

    python_code skills run in a Docker sandbox; without a Docker daemon the
    run fails deterministically. Verify the API reports success:false with an
    error and the DB row is marked failed with the message.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"ErrorHandling-{uuid.uuid4().hex[:8]}", python_skill_body())
    assert skill["metadata"]["skill_type"] == "python_code", skill

    response = execute_skill(token, skill["skill_id"], {"query": "invalid input"})
    # Failure is reported as 202 with success:false (service returns a result envelope)
    assert response.status_code in (200, 202), f"got {response.status_code}: {response.text[:300]}"
    data = response.json()["data"]
    assert data["success"] is False, data
    assert data["error"], data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution is not None
    assert execution.status == "failed", execution.status
    assert execution.error_message, "error_message should be recorded"


@pytest.mark.skip(reason="Error suggestions are not part of the skills API/UI surface (no execution frontend); covered structurally by test_execution_error_handling.")
def test_execution_error_with_suggestion(authenticated_page, db_session):
    """Test error with actionable suggestion (requires suggestion UI)."""
    pass


def test_execution_history_updates(setup_test_user, db_session):
    """Test execution history grows after a run (DB source of truth)."""
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"History-{uuid.uuid4().hex[:8]}", prompt_skill_body())
    # Service keys execution rows as "{skill_name}_{skill_pk[:8]}" (see
    # SkillRegistryService.execute_skill) — the import row is the baseline.
    exec_key = f"{skill['skill_name']}_{skill['skill_id'][:8]}"

    initial_count = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).count()

    response = execute_skill(token, skill["skill_id"], {"query": "test query"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True, data

    db_session.expire_all()
    final_count = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).count()
    assert final_count == initial_count + 1, (initial_count, final_count)

    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution.status == "success"
    assert execution.completed_at is not None
    assert (naive_utc_now() - execution.completed_at).total_seconds() < 10


def test_governance_blocks_restricted_execution(setup_test_user, db_session):
    """Test STUDENT agent is blocked from executing python skills.

    SKILL-04 governance: STUDENT + python_code → ValueError → HTTP 400, and
    NO execution row is created (the governance check precedes the insert).
    """
    token = setup_test_user["access_token"]
    student_agent = create_test_agent_direct(
        db_session,
        name="StudentExecutionAgent",
        status="STUDENT",
    )
    skill = import_skill(token, f"GovernanceBlock-{uuid.uuid4().hex[:8]}", python_skill_body())

    response = execute_skill(
        token, skill["skill_id"], {"query": "test"}, agent_id=student_agent["agent_id"]
    )
    assert response.status_code == 400, (
        f"STUDENT python execution should be blocked with 400, got {response.status_code}: {response.text[:300]}"
    )

    db_session.expire_all()
    executions = db_session.query(SkillExecution).filter(
        SkillExecution.agent_id == student_agent["agent_id"]
    ).all()
    assert len(executions) == 0, "No execution row should be created for the blocked attempt"


def test_intern_approval_for_sensitive_execution(setup_test_user, db_session):
    """Test INTERN clears governance for python skills.

    Only STUDENT is blocked; INTERN passes the maturity gate and the run is
    attempted (fails at the Docker sandbox on this stack — the governance
    outcome is what matters here: no 400).
    """
    token = setup_test_user["access_token"]
    intern_agent = create_test_agent_direct(
        db_session,
        name="InternExecutionAgent",
        status="INTERN",
    )
    skill = import_skill(token, f"InternExec-{uuid.uuid4().hex[:8]}", python_skill_body())

    response = execute_skill(
        token, skill["skill_id"], {"query": "test"}, agent_id=intern_agent["agent_id"]
    )
    assert response.status_code in (200, 202), (
        f"INTERN should not be governance-blocked, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()["data"]
    assert data["success"] is False, "Python run should fail without a Docker sandbox"
    assert "docker" in data["error"].lower(), data["error"]

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution is not None
    assert execution.agent_id == intern_agent["agent_id"]


def test_supervised_auto_execution(setup_test_user, db_session):
    """Test SUPERVISED agent executes a prompt skill without approval.

    The API has no approval step — SUPERVISED runs succeed directly.
    """
    token = setup_test_user["access_token"]
    supervised_agent = create_test_agent_direct(
        db_session,
        name="SupervisedExecutionAgent",
        status="SUPERVISED",
    )
    skill = import_skill(token, f"SupervisedExec-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    response = execute_skill(
        token, skill["skill_id"], {"query": "test"}, agent_id=supervised_agent["agent_id"]
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True, data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution is not None
    assert execution.status == "success"


def test_execution_retry(setup_test_user, db_session):
    """Test retrying a failed execution creates a new attempt.

    Retry = re-execute the same skill; each attempt gets its own row and the
    failed attempt's error is preserved.
    """
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"RetrySkill-{uuid.uuid4().hex[:8]}", python_skill_body())

    first = execute_skill(token, skill["skill_id"], {"query": "bad input"}).json()["data"]
    assert first["success"] is False

    second = execute_skill(token, skill["skill_id"], {"query": "bad input"}).json()["data"]
    assert second["success"] is False
    assert first["execution_id"] != second["execution_id"]

    db_session.expire_all()
    rows = db_session.query(SkillExecution).filter(
        SkillExecution.id.in_([first["execution_id"], second["execution_id"]])
    ).all()
    assert len(rows) == 2
    for row in rows:
        assert row.status == "failed"
        assert row.error_message


def test_multiple_executions_same_skill(setup_test_user, db_session):
    """Test multiple executions of the same skill are independent records."""
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"MultiExec-{uuid.uuid4().hex[:8]}", prompt_skill_body())
    exec_key = f"{skill['skill_name']}_{skill['skill_id'][:8]}"

    execution_ids = []
    for i in range(3):
        response = execute_skill(token, skill["skill_id"], {"query": f"test {i}"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is True, data
        execution_ids.append(data["execution_id"])

    assert len(set(execution_ids)) == 3

    db_session.expire_all()
    executions = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).all()
    assert len(executions) >= 3
    for exec_id in execution_ids:
        execution = db_session.query(SkillExecution).filter(SkillExecution.id == exec_id).first()
        assert execution is not None
        assert execution.status == "success"


def test_execution_with_complex_inputs(setup_test_user, db_session):
    """Test execution with complex nested inputs round-trips exactly."""
    token = setup_test_user["access_token"]
    skill = import_skill(token, f"ComplexInputs-{uuid.uuid4().hex[:8]}", prompt_skill_body())

    complex_inputs = {
        "query": "process complex data",
        "data": {
            "nested": {
                "value": 123,
                "items": ["a", "b", "c"],
            }
        },
        "array": [1, 2, 3, 4, 5],
        "metadata": {
            "source": "test",
            "timestamp": "2026-02-23T00:00:00Z",
        },
    }

    response = execute_skill(token, skill["skill_id"], complex_inputs)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True, data

    db_session.expire_all()
    execution = db_session.query(SkillExecution).filter(
        SkillExecution.id == data["execution_id"]
    ).first()
    assert execution is not None
    assert execution.input_params == complex_inputs


@pytest.mark.skip(reason="Timeout enforcement requires a long-running sandboxed run (Docker) plus a timeout UI; neither exists on this stack (python runs fail instantly without Docker).")
def test_execution_timeout_handling(authenticated_page, db_session):
    """Test timeout handling for long-running skills (requires sandbox runtime)."""
    pass
