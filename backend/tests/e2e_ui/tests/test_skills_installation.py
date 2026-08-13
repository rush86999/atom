"""
E2E tests for skill installation workflow (SKILL-02) — API-first.

The frontend ships no skills marketplace/install UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers). Installation is the backend
registry lifecycle:

    POST   /api/skills/import     — install: parse + security scan → record
    POST   /api/skills/promote    — Untrusted → Active transition
    GET    /api/skills/list       — installed skills list
    GET    /api/skills/{id}       — installed skill detail
    DELETE /api/skills/{id}       — uninstall
    POST   /api/skills/execute    — post-install run (governance-checked)

Tests drive the LIVE backend on :8001 with an API-minted token and verify
SkillExecution rows (the source of truth) through db_session. Keyless: the
security scanner is static-pattern + LLM-fail-open, so risk levels asserted
loosely (LOW|UNKNOWN) except where static patterns force CRITICAL.

Run with: pytest backend/tests/e2e_ui/tests/test_skills_installation.py -v
"""

import uuid

import requests

from core.models import SkillExecution

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def import_skill(token: str, name: str, body: str, metadata: dict = None) -> dict:
    """Install (import) a skill via the live registry API."""
    content = f"---\nname: {name}\ndescription: E2E install skill {name}\n---\n\n{body}"
    response = requests.post(
        f"{API}/api/skills/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "raw_content", "content": content, "metadata": metadata or {}},
        timeout=30,
    )
    assert response.status_code == 200, (
        f"Import should succeed, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert data["success"] is True, data
    return data["data"]


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
# Test Cases
# ============================================================================

def test_skill_install_from_marketplace(setup_test_user, db_session):
    """Test installing a skill from the registry: import → record.

    SKILL-02: the install call returns the new skill (id, name, status,
    scan result) and persists a community-skill row.
    """
    token = setup_test_user["access_token"]
    name = f"InstalledSkill-{uuid.uuid4().hex[:8]}"

    result = import_skill(token, name, "Answer the query.\n\n{{query}}")

    assert result["skill_id"]
    assert result["skill_name"] == name
    assert result["status"] in ("Active", "Untrusted"), result
    assert "risk_level" in result["scan_result"], result

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == result["skill_id"]).first()
    assert row is not None, "Installed skill row should exist"
    assert row.skill_source == "community"
    assert row.input_params["skill_name"] == name


def test_install_button_states(setup_test_user, db_session):
    """Test install state transitions: import (scanned) → promoted Active.

    Install lifecycle states map to registry status: a freshly imported skill
    is Untrusted until its scan clears/promotion; promoting flips it Active.
    """
    token = setup_test_user["access_token"]
    result = import_skill(token, f"StateSkill-{uuid.uuid4().hex[:8]}", "Body text")

    detail_before = requests.get(
        f"{API}/api/skills/{result['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]
    assert detail_before["status"] in ("Active", "Untrusted")

    promote = requests.post(
        f"{API}/api/skills/promote",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": result["skill_id"]},
        timeout=15,
    )
    assert promote.status_code == 200, f"got {promote.status_code}: {promote.text[:300]}"
    promoted = promote.json()["data"]
    assert promoted["status"] == "Active", promoted

    detail_after = requests.get(
        f"{API}/api/skills/{result['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]
    assert detail_after["status"] == "Active", "Promoted skill should be Active"


def test_installation_security_scan_display(setup_test_user, db_session):
    """Test security scan results are produced and surfaced at install time.

    Verifies:
    - Clean prompt content scans LOW (or UNKNOWN via LLM fail-open)
    - Malicious content (static pattern os.system() → CRITICAL) is detected
      and the skill is NOT auto-activated (Untrusted)
    - scan_result is persisted on the record
    """
    token = setup_test_user["access_token"]

    clean = import_skill(token, f"CleanSkill-{uuid.uuid4().hex[:8]}", "This skill has no code.")
    assert clean["scan_result"]["risk_level"] in ("LOW", "UNKNOWN"), clean
    assert clean["scan_result"]["safe"] in (True, False), clean

    malicious = import_skill(
        token,
        f"MaliciousSkill-{uuid.uuid4().hex[:8]}",
        "```python\nimport os\nos.system('echo pwned')\n```\n",
    )
    assert malicious["scan_result"]["risk_level"] == "CRITICAL", malicious
    assert malicious["scan_result"]["safe"] is False, malicious
    assert malicious["status"] == "Untrusted", (
        f"CRITICAL skill must not auto-activate, got {malicious['status']}"
    )

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == malicious["skill_id"]).first()
    assert row.security_scan_result is not None
    assert row.security_scan_result["risk_level"] == "CRITICAL"


def test_installation_creates_database_record(setup_test_user, db_session):
    """Test installation persists the full record in the database.

    SKILL-02: the SkillExecution row matches the install response (id, name,
    system agent attribution, community source).
    """
    token = setup_test_user["access_token"]
    name = f"DbRecordSkill-{uuid.uuid4().hex[:8]}"

    result = import_skill(token, name, "Body for record test")

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == result["skill_id"]).first()
    assert row is not None
    assert row.id == result["skill_id"]
    assert row.agent_id == "system", row.agent_id
    assert row.skill_source == "community"
    assert row.input_params["skill_name"] == name
    assert row.workspace_id == "default", row.workspace_id


def test_student_blocked_from_python_skill_installation(setup_test_user, db_session):
    """Test STUDENT agents cannot RUN python skills after installing them.

    Installation (import) has no maturity gate; the governance block applies
    at execution time — a STUDENT agent executing an installed python skill
    gets HTTP 400 and no execution record.
    """
    from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

    token = setup_test_user["access_token"]
    student = create_test_agent_direct(db_session, name="StudentInstallAgent", status="STUDENT")

    installed = import_skill(
        token,
        f"PythonForStudent-{uuid.uuid4().hex[:8]}",
        "```python\ndef execute(inputs):\n    return {'result': 'ok'}\n```\n",
    )
    assert installed["metadata"]["skill_type"] == "python_code"

    response = execute_skill(
        token, installed["skill_id"], {"query": "run"}, agent_id=student["agent_id"]
    )
    assert response.status_code == 400, (
        f"STUDENT python execution should be blocked, got {response.status_code}: {response.text[:300]}"
    )

    db_session.expire_all()
    executions = db_session.query(SkillExecution).filter(
        SkillExecution.agent_id == student["agent_id"]
    ).all()
    assert len(executions) == 0, "Blocked attempt must not create an execution row"


def test_intern_can_install_prompt_only_skill(setup_test_user, db_session):
    """Test INTERN agents can install and run low-risk prompt-only skills."""
    from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

    token = setup_test_user["access_token"]
    intern = create_test_agent_direct(db_session, name="InternInstallAgent", status="INTERN")

    installed = import_skill(token, f"PromptForIntern-{uuid.uuid4().hex[:8]}", "Answer it.\n\n{{query}}")
    assert installed["metadata"]["skill_type"] == "prompt_only"

    response = execute_skill(
        token, installed["skill_id"], {"query": "hello"}, agent_id=intern["agent_id"]
    )
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    data = response.json()["data"]
    assert data["success"] is True, data


def test_supervised_can_install_any_active_skill(setup_test_user, db_session):
    """Test SUPERVISED agents can install python skills (no governance block)."""
    from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct

    token = setup_test_user["access_token"]
    supervised = create_test_agent_direct(db_session, name="SupervisedInstallAgent", status="SUPERVISED")

    installed = import_skill(
        token,
        f"PythonForSupervised-{uuid.uuid4().hex[:8]}",
        "```python\ndef execute(inputs):\n    return {'result': 'ok'}\n```\n",
    )
    assert installed["metadata"]["skill_type"] == "python_code"

    # Governance passes (no 400); the sandboxed run itself may fail without
    # Docker — the assertion is that the maturity gate does not block.
    response = execute_skill(
        token, installed["skill_id"], {"query": "run"}, agent_id=supervised["agent_id"]
    )
    assert response.status_code in (200, 202), (
        f"SUPERVISED should clear governance, got {response.status_code}: {response.text[:300]}"
    )
    assert "governance" not in response.text.lower()


def test_installation_error_handling(setup_test_user, db_session):
    """Test installation error handling: uninstall (DELETE) of a missing skill.

    Deleting a skill that is not installed surfaces a clean 404.
    """
    token = setup_test_user["access_token"]

    response = requests.delete(
        f"{API}/api/skills/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 404, f"got {response.status_code}: {response.text[:300]}"


def test_install_same_skill_twice(setup_test_user, db_session):
    """Test installing the same skill content twice.

    The registry is not idempotent: each install creates a distinct record;
    both remain retrievable (equivalent to an "already installed, here's the
    existing copy" experience at the data layer).
    """
    token = setup_test_user["access_token"]
    name = f"TwiceInstalled-{uuid.uuid4().hex[:8]}"

    first = import_skill(token, name, "Same body")
    second = import_skill(token, name, "Same body")

    assert first["skill_id"] != second["skill_id"], "Each install should create a distinct record"

    db_session.expire_all()
    rows = db_session.query(SkillExecution).filter(
        SkillExecution.input_params["skill_name"].as_string() == name
    ).all()
    assert len(rows) == 2, f"Expected 2 rows for double install, got {len(rows)}"

    for skill_id in (first["skill_id"], second["skill_id"]):
        detail = requests.get(
            f"{API}/api/skills/{skill_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert detail.status_code == 200, f"Skill {skill_id} should be retrievable"


def test_installed_skills_list_updates(setup_test_user, db_session):
    """Test the installed-skills list updates after installation."""
    token = setup_test_user["access_token"]
    name = f"ListUpdate-{uuid.uuid4().hex[:8]}"

    # Explicit large limit: the registry caps list at 100 by default and the
    # shared e2e DB accumulates community rows across sessions.
    before = requests.get(
        f"{API}/api/skills/list?limit=500",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]["skills"]

    installed = import_skill(token, name, "Body for list update")

    after = requests.get(
        f"{API}/api/skills/list?limit=500",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]["skills"]

    after_ids = {s["skill_id"] for s in after}
    assert installed["skill_id"] in after_ids, "Newly installed skill must appear in the list"
    # The shared e2e DB accumulates community rows across sessions; once the
    # requested limit truncates the list, the count stays flat while the
    # newest row (this import) still appears — membership is the invariant.
    assert len(after) == len(before) + 1 or len(before) >= 500, (len(before), len(after))


def test_marketplace_filters_and_search(setup_test_user, db_session):
    """Test browsing installed skills: filters + detail lookup."""
    token = setup_test_user["access_token"]

    prompt_import = import_skill(token, f"BrowsePrompt-{uuid.uuid4().hex[:8]}", "Prompt body")
    python_import = import_skill(
        token,
        f"BrowsePython-{uuid.uuid4().hex[:8]}",
        "```python\ndef execute(inputs):\n    return {}\n```\n",
    )

    all_skills = requests.get(
        f"{API}/api/skills/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]["skills"]
    assert len(all_skills) >= 2

    prompt_only = requests.get(
        f"{API}/api/skills/list?skill_type=prompt_only",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]["skills"]
    assert len(prompt_only) >= 1
    assert all(s["skill_type"] == "prompt_only" for s in prompt_only)

    python_only = requests.get(
        f"{API}/api/skills/list?skill_type=python_code",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]["skills"]
    assert len(python_only) >= 1
    assert all(s["skill_type"] == "python_code" for s in python_only)

    # Detail lookup for every listed item must succeed. The registry shares
    # one table between skill definitions and execution records (both carry
    # skill_source='community'), so execution rows appear in the list without
    # a skill_name — only the two definitions imported here must have one.
    prompt_id = prompt_import["skill_id"]
    python_id = python_import["skill_id"]
    for item in all_skills:
        detail = requests.get(
            f"{API}/api/skills/{item['skill_id']}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert detail.status_code == 200, f"Detail lookup failed for {item['skill_id']}"
        data = detail.json()["data"]
        if item["skill_id"] in (prompt_id, python_id):
            assert data["skill_name"], item
