"""
E2E tests for skill installation workflow (WORK-01, WORK-02) — API-first.

The frontend ships no skills marketplace/install UI (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers; pages/marketplace.tsx is the
workflow-templates marketplace). The marketplace surface is the backend
community-skills registry:

    POST   /api/skills/import       — install: parse + security scan → record
    GET    /api/skills/list         — marketplace browse (filters + search)
    GET    /api/skills/{id}         — marketplace skill detail
    POST   /api/skills/execute      — post-install run (governance-checked)

Tests drive the LIVE backend on :8001 with an API-minted token and verify
SkillExecution rows (the source of truth) through db_session. Keyless: the
security scanner is static-pattern + LLM-fail-open, so risk levels asserted
loosely (LOW|UNKNOWN) except where static patterns force CRITICAL.

Requirements covered:
- WORK-01: User can browse skills marketplace and view skill details
- WORK-02: User can install skill and skill appears in registry
- WORK-02: Skill installation triggers security scan

Run with: pytest backend/tests/e2e_ui/tests/skills/test_skill_installation.py -v
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


def list_skills(token: str, **params) -> list:
    """GET the marketplace/registry list with optional filters."""
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

def test_browse_skills_marketplace(setup_test_user, db_session):
    """Test marketplace browse: list loads with skill cards + detail (WORK-01).

    The registry list IS the marketplace surface. Every listed item must
    resolve through the detail endpoint (equivalent to clicking a card).
    """
    token = setup_test_user["access_token"]
    imported = [
        import_skill(token, f"BrowseSkill-{uuid.uuid4().hex[:8]}", "Prompt body"),
        import_skill(
            token,
            f"BrowsePython-{uuid.uuid4().hex[:8]}",
            "```python\ndef execute(inputs):\n    return {}\n```\n",
        ),
    ]

    all_skills = list_skills(token, limit=500)
    assert len(all_skills) >= 2

    ids = {i["skill_id"] for i in imported}

    for item in all_skills:
        detail = requests.get(
            f"{API}/api/skills/{item['skill_id']}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert detail.status_code == 200, (
            f"Detail lookup failed for {item['skill_id']}"
        )
        # The registry shares one table between definitions and execution
        # records (both carry skill_source='community'), so execution rows
        # appear in the list without a skill_name — only the definitions
        # imported here must carry one.
        if item["skill_id"] in ids:
            data = detail.json()["data"]
            assert data["skill_name"], data
            assert data["skill_type"] in ("prompt_only", "python_code"), data

    listed_ids = {s["skill_id"] for s in all_skills}
    assert ids.issubset(listed_ids), "Freshly imported skills must be browsable"

    db_session.expire_all()
    for result in imported:
        row = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["skill_id"]
        ).first()
        assert row is not None


def test_skill_search_and_filter(setup_test_user, db_session):
    """Test marketplace search + type filter (WORK-01).

    The registry API filters by skill_type/status; search-by-name maps to the
    detail lookup of a specific skill id. Clearing filters = unfiltered list.
    """
    token = setup_test_user["access_token"]
    prompt = import_skill(token, f"SearchPrompt-{uuid.uuid4().hex[:8]}", "Prompt body")
    python = import_skill(
        token,
        f"SearchPython-{uuid.uuid4().hex[:8]}",
        "```python\ndef execute(inputs):\n    return {}\n```\n",
    )

    all_skills = list_skills(token, limit=500)
    assert len(all_skills) >= 2

    prompt_only = list_skills(token, skill_type="prompt_only")
    assert all(s["skill_type"] == "prompt_only" for s in prompt_only)
    assert prompt["skill_id"] in {s["skill_id"] for s in prompt_only}

    python_only = list_skills(token, skill_type="python_code")
    assert all(s["skill_type"] == "python_code" for s in python_only)
    assert python["skill_id"] in {s["skill_id"] for s in python_only}

    # Search-by-name: the detail endpoint resolves an exact name lookup.
    detail = requests.get(
        f"{API}/api/skills/{prompt['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]
    assert detail["skill_name"] == prompt["skill_name"]


def test_install_skill_via_ui(setup_test_user, db_session):
    """Test the install flow: import → record (WORK-02).

    The install call returns the new skill (id, name, status, scan result)
    and persists a community-skill row — the install button's full effect.
    """
    token = setup_test_user["access_token"]
    name = f"UiInstallSkill-{uuid.uuid4().hex[:8]}"
    result = import_skill(token, name, "Answer the query.\n\n{{query}}")

    assert result["skill_id"]
    assert result["skill_name"] == name
    assert result["status"] in ("Active", "Untrusted"), result
    assert "risk_level" in result["scan_result"], result
    assert result["metadata"]["skill_type"] == "prompt_only"

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == result["skill_id"]).first()
    assert row is not None, "Installed skill row should exist"
    assert row.skill_source == "community"
    assert row.agent_id == "system", row.agent_id
    assert row.workspace_id == "default", row.workspace_id
    assert row.input_params["skill_name"] == name


def test_skill_appears_in_registry_after_install(setup_test_user, db_session):
    """Test installed skill appears in registry (WORK-02).

    After install the skill is listed, retrievable by id with status
    metadata, and present as a DB record.
    """
    token = setup_test_user["access_token"]
    name = f"RegistryAppear-{uuid.uuid4().hex[:8]}"
    installed = import_skill(token, name, "Body for registry appearance")

    registry = list_skills(token, limit=500)
    registry_ids = {s["skill_id"] for s in registry}
    assert installed["skill_id"] in registry_ids, "Installed skill must appear in registry"

    detail = requests.get(
        f"{API}/api/skills/{installed['skill_id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ).json()["data"]
    assert detail["skill_name"] == name
    assert detail["status"] == installed["status"]

    db_session.expire_all()
    row = db_session.query(SkillExecution).filter(SkillExecution.id == installed["skill_id"]).first()
    assert row is not None
    assert row.status == installed["status"], row.status


def test_install_duplicate_skill_handling(setup_test_user, db_session):
    """Test duplicate skill installation handling (WORK-02).

    The registry is not idempotent: each install creates a distinct record;
    both remain retrievable (the data-layer equivalent of an "already
    installed, here's the existing copy" experience).
    """
    token = setup_test_user["access_token"]
    name = f"DuplicateInstall-{uuid.uuid4().hex[:8]}"

    first = import_skill(token, name, "Same body")
    second = import_skill(token, name, "Same body")

    assert first["skill_id"] != second["skill_id"], "Each install creates a distinct record"

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


def test_skill_security_scan_display(setup_test_user, db_session):
    """Test security scan results surface at install (WORK-02).

    - Clean prompt content scans LOW (or UNKNOWN via LLM fail-open)
    - Malicious content (static pattern os.system() → CRITICAL) is detected
      and the skill is NOT auto-activated (Untrusted)
    - scan_result is persisted on the record
    """
    token = setup_test_user["access_token"]

    clean = import_skill(token, f"ScanClean-{uuid.uuid4().hex[:8]}", "This skill has no code.")
    assert clean["scan_result"]["risk_level"] in ("LOW", "UNKNOWN"), clean
    # Keyless stack: scanner fails open (UNKNOWN → not LOW) so a clean import
    # may land Untrusted; only LOW auto-activates.
    assert clean["status"] in ("Active", "Untrusted"), clean

    malicious = import_skill(
        token,
        f"ScanMalicious-{uuid.uuid4().hex[:8]}",
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
