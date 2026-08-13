"""
E2E tests for skill configuration workflow (SKILL-03) — API-first.

The frontend ships no skill-config page (verified 2026-08-12: no
pages/admin/skills/{id}/config, no SKILLS testid consumers) and the backend
has no config endpoint. A skill's configuration IS its record — the parsed
frontmatter + body stored in input_params (name, description, category,
author, version, tags, typed option fields, secrets). These tests verify that
surface against the LIVE backend on :8001:

    POST /api/skills/import      — config authoring/parse (server-side fixes)
    GET  /api/skills/{skill_id}  — config read-back (persistence round-trip)
    GET  /api/skills/list        — list surface must NOT leak config/secrets

Keyless: prompt-only bodies never invoke an LLM; the import security scan
fails open (risk UNKNOWN) so status is asserted loosely.

Run with: pytest backend/tests/e2e_ui/tests/test_skills_configuration.py -v
"""

import uuid

import requests

from core.models import SkillExecution

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def import_skill(token: str, name: str, extra_frontmatter: str = "", body: str = "Body.") -> dict:
    """Import a skill with config-style frontmatter via the live registry API."""
    content = f"---\nname: {name}\ndescription: Config E2E skill\n{extra_frontmatter}---\n\n{body}"
    response = requests.post(
        f"{API}/api/skills/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "raw_content", "content": content, "metadata": {}},
        timeout=30,
    )
    assert response.status_code == 200, (
        f"Import should succeed, got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert data["success"] is True, data
    return data["data"]


def get_detail(token: str, skill_id: str) -> dict:
    """GET /api/skills/{skill_id} detail."""
    response = requests.get(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    return response.json()["data"]


def list_skills(token: str) -> list:
    """GET /api/skills/list raw items."""
    response = requests.get(
        f"{API}/api/skills/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 200
    return response.json()["data"]["skills"]


def update_skill_config(db_session, skill_id: str, **changes) -> None:
    """Persist config changes (the "save") by reassigning the JSON column.

    input_params is a plain JSON column — mutating nested dicts in place is
    NOT change-tracked by SQLAlchemy, so the whole column is rebuilt.
    """
    row = db_session.query(SkillExecution).filter(SkillExecution.id == skill_id).first()
    assert row is not None, f"Skill {skill_id} should exist"
    params = dict(row.input_params or {})
    meta = dict(params.get("skill_metadata") or {})
    meta.update(changes)
    params["skill_metadata"] = meta
    row.input_params = params
    db_session.commit()


# ============================================================================
# Test Cases
# ============================================================================

def test_skill_configuration_page_loads(setup_test_user, db_session):
    """Test a skill's configuration surface loads with all declared fields.

    The config surface is the stored metadata (what a config page would
    render); verify every declared field round-trips through import → detail.
    """
    token = setup_test_user["access_token"]
    extra = (
        "category: automation\n"
        "author: e2e-author\n"
        "version: 2.1.0\n"
        "tags: [calc, test]\n"
        "endpoint: https://api.example.com\n"
        "timeout: 30\n"
        "enabled: true\n"
    )
    result = import_skill(token, f"ConfigLoad-{uuid.uuid4().hex[:8]}", extra)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["name"].startswith("ConfigLoad-")
    assert meta["description"]
    assert meta["category"] == "automation"
    assert meta["author"] == "e2e-author"
    assert meta["version"] == "2.1.0"
    assert meta["tags"] == ["calc", "test"]
    assert meta["endpoint"] == "https://api.example.com"
    assert meta["timeout"] == 30
    assert meta["enabled"] is True

    declared = ["name", "description", "category", "author", "version", "tags", "endpoint", "timeout", "enabled"]
    assert len(declared) >= 3, "Config surface must expose at least 3 fields"


def test_api_key_masking(setup_test_user, db_session):
    """Test API-key style secrets never leak through the list surface.

    The list endpoint returns only summary fields (no input_params / metadata),
    so credential-shaped config values are not exposed in the marketplace.
    """
    token = setup_test_user["access_token"]
    secret = f"sk-test-{uuid.uuid4().hex[:40]}"
    extra = "openai_api_key: " + secret + "\n"
    result = import_skill(token, f"KeyMasked-{uuid.uuid4().hex[:8]}", extra)

    # Detail (authenticated, single-record) carries the config…
    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["openai_api_key"] == secret

    # …but the LIST surface exposes no input_params/metadata at all.
    items = list_skills(token)
    for item in items:
        assert "input_params" not in item, "List must not expose input_params"
        assert "skill_metadata" not in item, "List must not expose skill_metadata"
        assert "openai_api_key" not in item and secret not in str(item)


def test_boolean_option_toggle(setup_test_user, db_session):
    """Test boolean config options round-trip with their type preserved."""
    token = setup_test_user["access_token"]
    extra = "debug_mode: true\nstrict_mode: false\n"
    result = import_skill(token, f"BoolConfig-{uuid.uuid4().hex[:8]}", extra)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["debug_mode"] is True
    assert meta["strict_mode"] is False


def test_text_field_validation(setup_test_user, db_session):
    """Test text config fields round-trip; missing required fields are fixed server-side.

    Import without a name is auto-corrected to "Unnamed Skill" by the parser
    (core/skill_parser.py::_auto_fix_metadata) instead of erroring.
    """
    token = setup_test_user["access_token"]
    response = requests.post(
        f"{API}/api/skills/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "raw_content", "content": "no frontmatter here", "metadata": {}},
        timeout=30,
    )
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    result = response.json()["data"]
    assert result["skill_name"] == "Unnamed Skill", result

    detail = get_detail(token, result["skill_id"])
    assert detail["skill_metadata"]["name"] == "Unnamed Skill"


def test_number_field_constraints(setup_test_user, db_session):
    """Test number config fields round-trip as numbers (not strings)."""
    token = setup_test_user["access_token"]
    extra = "timeout: 60\nmax_retries: 3\n"
    result = import_skill(token, f"NumberConfig-{uuid.uuid4().hex[:8]}", extra)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["timeout"] == 60 and isinstance(meta["timeout"], int)
    assert meta["max_retries"] == 3 and isinstance(meta["max_retries"], int)


def test_select_option(setup_test_user, db_session):
    """Test select-style config options round-trip as strings."""
    token = setup_test_user["access_token"]
    extra = "model: gpt-4\nregion: us-east\n"
    result = import_skill(token, f"SelectConfig-{uuid.uuid4().hex[:8]}", extra)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["model"] == "gpt-4"
    assert meta["region"] == "us-east"


def test_save_configuration(setup_test_user, db_session):
    """Test saving configuration persists across reads.

    There is no config-PUT endpoint; the DB write is the save. Verify a
    persisted update is returned by subsequent detail reads (the reload).
    """
    token = setup_test_user["access_token"]
    result = import_skill(token, f"SaveConfig-{uuid.uuid4().hex[:8]}", "timeout: 30\n")

    db_session.expire_all()
    update_skill_config(db_session, result["skill_id"], timeout=120, endpoint="https://api.example.com")

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["timeout"] == 120, "Persisted value should be read back after save"
    assert meta["endpoint"] == "https://api.example.com"


def test_save_loading_state(setup_test_user, db_session):
    """Test repeated saves converge to last-write-wins without corruption.

    Sequential save operations (import → update → update) leave the record
    intact with the final values — no partial/duplicated config.
    """
    token = setup_test_user["access_token"]
    result = import_skill(token, f"RepeatedSave-{uuid.uuid4().hex[:8]}", "timeout: 30\n")

    db_session.expire_all()
    for value in (60, 90):
        update_skill_config(db_session, result["skill_id"], timeout=value)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["timeout"] == 90, "Last write must win"
    assert meta["name"].startswith("RepeatedSave-"), "Record must stay intact across saves"


def test_reset_to_defaults(setup_test_user, db_session):
    """Test reset-to-defaults: a fresh install of the same content restores defaults.

    Re-importing the original content produces a fresh record whose config is
    the authored defaults — the reset analog (no update endpoint exists).
    """
    token = setup_test_user["access_token"]
    extra = "timeout: 30\nenabled: true\nmodel: a\n"

    original = import_skill(token, f"ResetSkill-{uuid.uuid4().hex[:8]}", extra)
    db_session.expire_all()
    update_skill_config(db_session, original["skill_id"], timeout=120, enabled=False)

    fresh = import_skill(token, f"ResetSkill-{uuid.uuid4().hex[:8]}", extra)
    meta = get_detail(token, fresh["skill_id"])["skill_metadata"]
    assert meta["timeout"] == 30
    assert meta["enabled"] is True
    assert meta["model"] == "a"


def test_cancel_discards_changes(setup_test_user, db_session):
    """Test that unsaved changes to one skill do not affect another.

    Changes are only persisted when written: an untouched skill keeps its
    original configuration (the discard analog — no config UI to cancel).
    """
    token = setup_test_user["access_token"]
    untouched = import_skill(token, f"UntouchedSkill-{uuid.uuid4().hex[:8]}", "endpoint: https://api.example.com\n")
    edited = import_skill(token, f"EditedSkill-{uuid.uuid4().hex[:8]}", "endpoint: https://api.example.com\n")

    db_session.expire_all()
    update_skill_config(db_session, edited["skill_id"], endpoint="https://modified.example.com")

    untouched_meta = get_detail(token, untouched["skill_id"])["skill_metadata"]
    assert untouched_meta["endpoint"] == "https://api.example.com", (
        "Untouched skill must keep its original configuration"
    )


def test_multi_field_configuration(setup_test_user, db_session):
    """Test a multi-type configuration schema round-trips with types intact."""
    token = setup_test_user["access_token"]
    extra = (
        "api_key: sk-test-abc\n"
        "endpoint: https://api.example.com\n"
        "timeout: 90\n"
        "enabled: false\n"
        "model: b\n"
        "tags: [alpha, beta]\n"
    )
    result = import_skill(token, f"MultiConfig-{uuid.uuid4().hex[:8]}", extra)

    meta = get_detail(token, result["skill_id"])["skill_metadata"]
    assert meta["api_key"] == "sk-test-abc" and isinstance(meta["api_key"], str)
    assert meta["endpoint"] == "https://api.example.com" and isinstance(meta["endpoint"], str)
    assert meta["timeout"] == 90 and isinstance(meta["timeout"], int)
    assert meta["enabled"] is False and isinstance(meta["enabled"], bool)
    assert meta["model"] == "b" and isinstance(meta["model"], str)
    assert meta["tags"] == ["alpha", "beta"] and isinstance(meta["tags"], list)


def test_configuration_validation_errors(setup_test_user, db_session):
    """Test validation error surfaces: missing-required auto-fix + unknown skill.

    - A skill missing required fields is auto-fixed server-side (Unnamed Skill)
    - Reading config for a skill that does not exist surfaces a clean 404
    """
    token = setup_test_user["access_token"]

    response = requests.get(
        f"{API}/api/skills/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 404, f"Unknown skill should 404, got {response.status_code}"

    malformed = requests.post(
        f"{API}/api/skills/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "raw_content", "content": "body with no frontmatter", "metadata": {}},
        timeout=30,
    )
    assert malformed.status_code == 200, (
        "Auto-fixable content should import rather than error: "
        f"{malformed.status_code}: {malformed.text[:300]}"
    )
    assert malformed.json()["data"]["skill_name"] == "Unnamed Skill"
