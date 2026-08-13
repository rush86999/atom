"""
E2E tests for skill registry management (WORK-02) — API-first.

The frontend ships no skills registry UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers; pages/marketplace.tsx is the
workflow-templates marketplace). The registry surface is the backend
community-skills API:

    POST   /api/skills/import       — install: parse + security scan → record
    GET    /api/skills/list         — registry listing (status/type filters)
    GET    /api/skills/{id}         — registry detail
    POST   /api/skills/promote      — Untrusted → Active transition
    DELETE /api/skills/{id}         — uninstall

Tests drive the LIVE backend on :8001 with an API-minted token and verify
SkillExecution rows (the source of truth) through db_session. Keyless: the
security scanner is static-pattern + LLM-fail-open, so risk levels asserted
loosely (LOW|UNKNOWN) except where static patterns force CRITICAL.

Requirements covered:
- WORK-02: Skill appears in registry after installation
- WORK-02: Registry displays skill metadata (name, status, type)

Run with: pytest backend/tests/e2e_ui/tests/skills/test_skill_registry.py -v
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
    content = f"---\nname: {name}\ndescription: E2E registry skill {name}\n---\n\n{body}"
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
    """GET the registry list with optional filters (status/skill_type/limit)."""
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


# ============================================================================
# Tests
# ============================================================================

def test_skill_registry_lists_installed_skills(setup_test_user, db_session):
    """Test skill registry lists all installed skills (WORK-02).

    Installing 3 skills makes them visible in the registry list with name,
    status, and type metadata; DB rows are the source of truth.
    """
    token = setup_test_user["access_token"]
    names = [f"RegistrySkill-{uuid.uuid4().hex[:8]}" for _ in range(3)]

    imported = [import_skill(token, name, f"Body for {name}") for name in names]

    registry = list_skills(token, limit=500)
    registry_ids = {s["skill_id"] for s in registry}
    for result in imported:
        assert result["skill_id"] in registry_ids, (
            f"Imported skill {result['skill_name']} must appear in registry"
        )

    # The shared e2e DB accumulates rows across sessions; execution records
    # share the table (skill_source='community') and surface with status
    # success/failed — assert strictly only for skills this test imported.
    for item in registry:
        assert "skill_id" in item and "skill_name" in item, item
        assert item["status"], item
    for result in imported:
        item = next(s for s in registry if s["skill_id"] == result["skill_id"])
        assert item["skill_name"] == result["skill_name"]
        assert item["status"] in ("Active", "Untrusted"), item
        assert item["skill_type"] in ("prompt_only", "python_code"), item

    db_session.expire_all()
    for result in imported:
        row = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert row is not None, f"Skill {result['skill_name']} missing in DB"
        assert row.input_params["skill_name"] == result["skill_name"]


def test_skill_registry_filtering(setup_test_user, db_session):
    """Test skill registry filtering by type (WORK-02).

    The registry API filters on skill_type (prompt_only|python_code) — the
    real filter surface. Category filtering lives in skill_metadata and is
    not an API query parameter.
    """
    token = setup_test_user["access_token"]
    prompt = import_skill(token, f"FilterPrompt-{uuid.uuid4().hex[:8]}", "Prompt body")
    python = import_skill(
        token,
        f"FilterPython-{uuid.uuid4().hex[:8]}",
        "```python\ndef execute(inputs):\n    return {}\n```\n",
    )

    prompt_only = list_skills(token, skill_type="prompt_only")
    assert all(s["skill_type"] == "prompt_only" for s in prompt_only)
    assert prompt["skill_id"] in {s["skill_id"] for s in prompt_only}

    python_only = list_skills(token, skill_type="python_code")
    assert all(s["skill_type"] == "python_code" for s in python_only)
    assert python["skill_id"] in {s["skill_id"] for s in python_only}

    active = list_skills(token, status="Active", skill_status="Active")
    assert all(s["status"] == "Active" for s in active)

    db_session.expire_all()
    for result in (prompt, python):
        row = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert row is not None


def test_skill_uninstall_flow(setup_test_user, db_session):
    """Test skill uninstall flow (WORK-02).

    DELETE removes the definition row from the registry: the skill 404s on
    detail, disappears from the list, and cannot be executed.
    """
    token = setup_test_user["access_token"]
    installed = import_skill(token, f"UninstallFlow-{uuid.uuid4().hex[:8]}", "Body text")
    skill_id = installed["skill_id"]

    detail = requests.get(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 200

    removed = requests.delete(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert removed.status_code == 200, f"got {removed.status_code}: {removed.text[:300]}"
    assert removed.json()["data"]["deleted"] is True

    detail_after = requests.get(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail_after.status_code == 404, "Deleted skill must 404 on detail"

    execute_after = requests.post(
        f"{API}/api/skills/execute",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": skill_id, "inputs": {"query": "run"}, "agent_id": "system"},
        timeout=30,
    )
    assert execute_after.status_code == 400, (
        f"Deleted skill must not execute, got {execute_after.status_code}"
    )

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == skill_id).first()
    assert row is None, "Uninstalled skill row must be deleted"


def test_skill_details_page(setup_test_user, db_session):
    """Test skill details lookup (WORK-02).

    GET /api/skills/{id} returns the full definition metadata: name, type,
    status, body, scan result, sandbox flag.
    """
    token = setup_test_user["access_token"]
    installed = import_skill(token, f"DetailsSkill-{uuid.uuid4().hex[:8]}", "Detail body")

    detail = requests.get(
        f"{API}/api/skills/{installed['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert detail.status_code == 200
    data = detail.json()["data"]

    assert data["skill_id"] == installed["skill_id"]
    assert data["skill_name"] == installed["skill_name"]
    assert data["skill_type"] in ("prompt_only", "python_code"), data
    assert data["status"] in ("Active", "Untrusted"), data
    assert "skill_body" in data, data
    assert "security_scan_result" in data, data
    assert isinstance(data["sandbox_enabled"], bool), data

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(
        SkillExecution.id == installed["skill_id"]
    ).first()
    assert row is not None
    assert row.skill_source == "community"


def test_skill_status_badges(setup_test_user, db_session):
    """Test skill status transitions (WORK-02).

    Status is the registry's badge surface: a clean skill imports Active, a
    CRITICAL-scan skill imports Untrusted, and promote flips it Active. The
    list and detail both surface the status.
    """
    token = setup_test_user["access_token"]
    clean = import_skill(token, f"BadgeClean-{uuid.uuid4().hex[:8]}", "No code here")
    malicious = import_skill(
        token,
        f"BadgeMalicious-{uuid.uuid4().hex[:8]}",
        "```python\nimport os\nos.system('echo pwned')\n```\n",
    )

    # Keyless stack: the scanner fails open (risk UNKNOWN) for clean content,
    # and only LOW auto-activates — so a clean import may be Untrusted.
    assert clean["status"] in ("Active", "Untrusted"), clean
    assert malicious["status"] == "Untrusted", (
        f"CRITICAL scan must import Untrusted, got {malicious['status']}"
    )

    promote = requests.post(
        f"{API}/api/skills/promote",
        headers={"Authorization": f"Bearer {token}"},
        json={"skill_id": malicious["skill_id"]},
        timeout=15,
    )
    assert promote.status_code == 200, f"got {promote.status_code}: {promote.text[:300]}"
    assert promote.json()["data"]["status"] == "Active"

    detail = requests.get(
        f"{API}/api/skills/{malicious['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]
    assert detail["status"] == "Active", "Promoted skill must be Active in detail"

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(
        SkillExecution.id == malicious["skill_id"]
    ).first()
    assert row.status == "Active", row.status
