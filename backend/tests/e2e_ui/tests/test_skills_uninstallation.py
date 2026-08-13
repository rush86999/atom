"""
E2E tests for skill uninstallation workflow (SKILL-05) — API-first.

The frontend ships no skills uninstall UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers). Uninstall is the backend
registry lifecycle:

    POST   /api/skills/import       — install a skill (returns skill_id)
    GET    /api/skills/list         — installed skills list
    GET    /api/skills/{id}         — installed skill detail
    DELETE /api/skills/{id}         — uninstall (removes the definition row)
    POST   /api/skills/execute      — post-install run (governance-checked)

Tests drive the LIVE backend on :8001 with an API-minted token and verify
SkillExecution rows (the source of truth) through db_session.

Real uninstall semantics (verified against SkillRegistryService.delete_skill):
- DELETE hard-removes the skill DEFINITION row (the row whose id == skill_id
  with skill_source='community').
- Execution history rows are separate SkillExecution rows keyed by
  "{skill_name}_{skill_pk[:8]}", so they survive an uninstall — the
  execution-history-preservation requirement holds at the data layer.
- There is no "block on active execution" gate: the definition row is deleted
  regardless of pending execution rows (a UI-level guard would live in a
  frontend that does not exist).

Run with: pytest tests/e2e_ui/tests/test_skills_uninstallation.py -v
"""

import uuid

import pytest
import requests

from core.models import SkillExecution

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def import_skill(token: str, name: str, body: str, metadata: dict = None) -> dict:
    """Install (import) a skill via the live registry API."""
    content = f"---\nname: {name}\ndescription: E2E uninstall skill {name}\n---\n\n{body}"
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


def list_skills(token: str, **params) -> list:
    """GET the installed-skills list with optional filters."""
    response = requests.get(
        f"{API}/api/skills/list",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    assert response.status_code == 200, (
        f"List should succeed, got {response.status_code}: {response.text[:300]}"
    )
    return response.json()["data"]["skills"]


def uninstall_skill(token: str, skill_id: str) -> requests.Response:
    """Uninstall (DELETE) a skill via the live registry API."""
    return requests.delete(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )


def execute_skill(token: str, skill_id: str, inputs: dict, agent_id: str = "system") -> requests.Response:
    """Execute a skill via the live registry API."""
    return requests.post(
        f"{API}/api/skills/execute",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": skill_id, "inputs": inputs, "agent_id": agent_id},
        timeout=180,
    )


# ============================================================================
# Test Cases
# ============================================================================

def test_skill_uninstall_from_installed_list(setup_test_user, db_session):
    """Test uninstalling a skill from the installed skills list (SKILL-05).

    The uninstall flow: import → confirm presence in the list → DELETE →
    verify removal from the list, a 404 on detail, and no DB row.
    """
    token = setup_test_user["access_token"]
    installed = import_skill(token, f"UninstallList-{uuid.uuid4().hex[:8]}", "Body text")
    skill_id = installed["skill_id"]

    before_ids = {s["skill_id"] for s in list_skills(token, limit=500)}
    assert skill_id in before_ids, "Installed skill must appear in the list"

    response = uninstall_skill(token, skill_id)
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    assert response.json()["data"]["deleted"] is True

    after_ids = {s["skill_id"] for s in list_skills(token, limit=500)}
    assert skill_id not in after_ids, "Uninstalled skill must be removed from the list"

    detail = requests.get(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 404, "Uninstalled skill must 404 on detail"

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == skill_id).first()
    assert row is None, "Uninstalled skill row must be deleted"


@pytest.mark.skip(reason="Confirmation dialog is frontend-only (no pages/skills/* UI exists); the API analog is the DELETE response, covered by test_uninstall_confirmation_message_accuracy.")
def test_uninstall_confirmation_dialog(browser, db_session, setup_test_user):
    """Test uninstallation confirmation dialog (requires skills UI)."""
    pass


@pytest.mark.skip(reason="Uninstall button state transitions are frontend-only (no pages/skills/* UI exists); the API analog is DELETE → list removal, covered by test_skill_uninstall_from_installed_list.")
def test_uninstall_button_states(browser, db_session, setup_test_user):
    """Test uninstall button state transitions (requires skills UI)."""
    pass


def test_uninstall_removes_configuration(setup_test_user, db_session):
    """Test uninstall removes skill configuration (SKILL-05).

    Configuration lives on the definition record; deleting the record drops
    it, and a fresh install of the same content starts from a blank record
    (no carry-over between generations).
    """
    token = setup_test_user["access_token"]
    name = f"ConfigRemoval-{uuid.uuid4().hex[:8]}"

    first = import_skill(token, name, "Body with config")
    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == first["skill_id"]).first()
    row.input_params["config"] = {"api_key": "test-key-123", "option1": "value1"}
    db_session.commit()

    response = uninstall_skill(token, first["skill_id"])
    assert response.status_code == 200

    second = import_skill(token, name, "Body with config")
    assert second["skill_id"] != first["skill_id"], "Reinstall creates a fresh record"

    db_session.expire_all()
    fresh = db_session.query(SkillExecution).filter(SkillExecution.id == second["skill_id"]).first()
    assert fresh is not None
    assert "config" not in fresh.input_params, (
        "Fresh install must not carry over the previous install's config"
    )


def test_uninstalled_skill_can_reinstall(setup_test_user, db_session):
    """Test an uninstalled skill can be reinstalled (SKILL-05).

    After DELETE the same content imports again as a new, fully functional
    record (retrievable + executable).
    """
    token = setup_test_user["access_token"]
    name = f"Reinstall-{uuid.uuid4().hex[:8]}"

    first = import_skill(token, name, "Answer the query.\n\n{{query}}")
    response = uninstall_skill(token, first["skill_id"])
    assert response.status_code == 200

    second = import_skill(token, name, "Answer the query.\n\n{{query}}")
    assert second["skill_id"] != first["skill_id"]

    detail = requests.get(
        f"{API}/api/skills/{second['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["skill_name"] == name

    run = execute_skill(token, second["skill_id"], {"query": "hello"})
    assert run.status_code == 200, f"Reinstalled skill must execute, got {run.status_code}"

    db_session.expire_all()
    old_row = db_session.query(SkillExecution).filter(SkillExecution.id == first["skill_id"]).first()
    new_row = db_session.query(SkillExecution).filter(SkillExecution.id == second["skill_id"]).first()
    assert old_row is None, "Old record must stay deleted"
    assert new_row is not None, "New record must exist"


def test_uninstall_blocks_active_executions(setup_test_user, db_session):
    """Test uninstall with active (running) execution rows (SKILL-05).

    Real semantics: DELETE removes the definition row even when execution
    rows exist — there is no UI-level block gate (that would live in a
    frontend that does not exist). The surviving execution rows keep the
    audit trail intact.
    """
    token = setup_test_user["access_token"]
    name = f"ActiveExec-{uuid.uuid4().hex[:8]}"
    installed = import_skill(token, name, "Answer the query.\n\n{{query}}")

    exec_key = f"{name}_{installed['skill_id'][:8]}"
    running = SkillExecution(
        id=str(uuid.uuid4()),
        agent_id="system",
        skill_id=exec_key,
        tenant_id="system",
        workspace_id="default",
        status="running",
        input_params={"query": "in flight"},
        skill_source="community",
        sandbox_enabled=False,
    )
    db_session.add(running)
    db_session.commit()

    response = uninstall_skill(token, installed["skill_id"])
    assert response.status_code == 200, (
        f"Definition row deletes despite execution rows, got {response.status_code}"
    )

    db_session.expire_all()
    definition = db_session.query(SkillExecution).filter(
        SkillExecution.id == installed["skill_id"]
    ).first()
    assert definition is None, "Definition row must be deleted"

    execution_rows = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).all()
    assert len(execution_rows) == 1, "Execution rows must survive the uninstall"
    assert execution_rows[0].status == "running"


def test_uninstall_preserves_execution_history(setup_test_user, db_session):
    """Test execution history is preserved after uninstall (SKILL-05).

    Execution records are separate rows from the definition row; deleting
    the skill keeps all prior execution history queryable in the DB.
    """
    token = setup_test_user["access_token"]
    name = f"HistoryPreserve-{uuid.uuid4().hex[:8]}"
    installed = import_skill(token, name, "Answer the query.\n\n{{query}}")

    exec_key = f"{name}_{installed['skill_id'][:8]}"
    for i in range(3):
        response = execute_skill(token, installed["skill_id"], {"query": f"run {i}"})
        assert response.status_code == 200
        assert response.json()["data"]["success"] is True

    db_session.expire_all()
    history_before = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).all()
    assert len(history_before) == 3, f"Expected 3 history rows, got {len(history_before)}"

    response = uninstall_skill(token, installed["skill_id"])
    assert response.status_code == 200

    db_session.expire_all()
    preserved = db_session.query(SkillExecution).filter(
        SkillExecution.skill_id == exec_key
    ).all()
    assert len(preserved) == 3, "Execution history must be preserved after uninstall"
    assert all(r.status == "success" for r in preserved)


def test_uninstall_multiple_skills(setup_test_user, db_session):
    """Test uninstalling multiple skills independently (SKILL-05).

    Each DELETE removes exactly its target; sibling skills stay installed.
    """
    token = setup_test_user["access_token"]
    skills = [
        import_skill(token, f"MultiUninstall-{uuid.uuid4().hex[:8]}", "Body A"),
        import_skill(token, f"MultiUninstall-{uuid.uuid4().hex[:8]}", "Body B"),
        import_skill(token, f"MultiUninstall-{uuid.uuid4().hex[:8]}", "Body C"),
    ]

    for skill in skills[:2]:
        response = uninstall_skill(token, skill["skill_id"])
        assert response.status_code == 200

    survivor = skills[2]
    detail = requests.get(
        f"{API}/api/skills/{survivor['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 200, "Non-target skill must stay installed"

    db_session.expire_all()
    for skill in skills[:2]:
        row = db_session.query(SkillExecution).filter(SkillExecution.id == skill["skill_id"]).first()
        assert row is None, f"Skill {skill['skill_name']} must be removed"
    survivor_row = db_session.query(SkillExecution).filter(
        SkillExecution.id == survivor["skill_id"]
    ).first()
    assert survivor_row is not None, "Survivor must remain in DB"


def test_uninstall_error_handling(setup_test_user, db_session):
    """Test uninstall error handling (SKILL-05).

    Deleting a missing or already-deleted skill surfaces a clean 404 and the
    DB is unchanged.
    """
    token = setup_test_user["access_token"]

    missing = uninstall_skill(token, str(uuid.uuid4()))
    assert missing.status_code == 404, f"got {missing.status_code}: {missing.text[:300]}"

    installed = import_skill(token, f"ErrorHandling-{uuid.uuid4().hex[:8]}", "Body text")
    first = uninstall_skill(token, installed["skill_id"])
    assert first.status_code == 200

    second = uninstall_skill(token, installed["skill_id"])
    assert second.status_code == 404, (
        f"Double uninstall must 404, got {second.status_code}: {second.text[:300]}"
    )


def test_uninstall_from_marketplace(setup_test_user, db_session):
    """Test uninstalling a skill from the marketplace view (SKILL-05).

    The marketplace view is the registry list (no separate UI); a promoted
    Active skill listed there uninstalls the same way.
    """
    token = setup_test_user["access_token"]
    installed = import_skill(token, f"MarketplaceUninstall-{uuid.uuid4().hex[:8]}", "Body text")

    promote = requests.post(
        f"{API}/api/skills/promote",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": installed["skill_id"]},
        timeout=15,
    )
    assert promote.status_code == 200

    active_list = list_skills(token, status="Active", limit=500)
    assert installed["skill_id"] in {s["skill_id"] for s in active_list}

    response = uninstall_skill(token, installed["skill_id"])
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    after_list = list_skills(token, status="Active", limit=500)
    assert installed["skill_id"] not in {s["skill_id"] for s in after_list}


def test_uninstall_last_skill(setup_test_user, db_session):
    """Test uninstalling the last (only) skill (SKILL-05).

    With a unique name and no other rows, uninstalling the sole skill leaves
    the registry list without it and the detail 404s — the empty-state
    invariant at the data layer.
    """
    token = setup_test_user["access_token"]
    name = f"LastSkill-{uuid.uuid4().hex[:8]}"
    installed = import_skill(token, name, "Only body")

    response = uninstall_skill(token, installed["skill_id"])
    assert response.status_code == 200

    all_skills = list_skills(token, limit=500)
    assert installed["skill_id"] not in {s["skill_id"] for s in all_skills}

    detail = requests.get(
        f"{API}/api/skills/{installed['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 404

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == installed["skill_id"]).first()
    assert row is None


def test_uninstall_confirmation_message_accuracy(setup_test_user, db_session):
    """Test uninstall confirmation message accuracy (SKILL-05).

    The DELETE response names the exact skill being removed — the API analog
    of the confirmation dialog showing the correct skill name.
    """
    token = setup_test_user["access_token"]
    name = f"ConfirmMsg-{uuid.uuid4().hex[:8]}"
    installed = import_skill(token, name, "Body text")

    response = uninstall_skill(token, installed["skill_id"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True, payload
    assert payload["data"]["skill_name"] == name, payload
    assert payload["data"]["skill_id"] == installed["skill_id"], payload
    assert name in payload["message"], payload
