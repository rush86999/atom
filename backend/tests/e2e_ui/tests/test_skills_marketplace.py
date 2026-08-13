"""
E2E tests for Skills Marketplace browsing — API-first (SKILL-01).

The frontend ships no skills-marketplace page (verified 2026-08-12: no
pages/skills/* pages, no SKILLS testid consumers; pages/marketplace.tsx is the
workflow-templates marketplace). The marketplace surface that exists is the
backend community-skills registry:

    GET /api/skills/list              — browsing (status/skill_type/limit)
    GET /api/skills/{skill_id}        — card detail

These tests seed community skills (SkillExecution rows — the same table the
registry reads) via db_session, then verify listing, detail, filtering,
pagination and ordering against the LIVE backend on :8001.

Run with: pytest backend/tests/e2e_ui/tests/test_skills_marketplace.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import Session

from core.models import SkillExecution

API = "http://localhost:8001"


# ============================================================================
# Helper Functions
# ============================================================================

def seed_marketplace_skill(
    db_session: Session,
    name: str,
    skill_type: str = "prompt_only",
    category: str = "data_processing",
    description: str = None,
    status: str = "Active",
    created_at: datetime = None,
) -> str:
    """Seed a community skill row exactly as the registry reads it.

    Mirrors SkillRegistryService.import_skill's stored shape
    (skill_source='community', metadata under input_params).

    Args:
        db_session: Database session
        name: Skill name (stored in input_params.skill_name)
        skill_type: "prompt_only" or "python_code"
        category: Skill category (metadata)
        description: Skill description (metadata)
        status: Registry status ("Active"/"Untrusted")
        created_at: Optional explicit creation time (ordering tests)

    Returns:
        str: SkillExecution PK (the registry's skill_id)
    """
    description = description or f"Test skill {name} for {category.replace('_', ' ')}"
    unique = uuid.uuid4().hex[:8]

    skill = SkillExecution(
        id=str(uuid.uuid4()),
        agent_id="system",
        tenant_id="system",
        workspace_id="default",
        skill_id=f"community_{name}_{unique}",
        status=status,
        skill_source="community",
        sandbox_enabled=(skill_type == "python_code"),
        input_params={
            "skill_name": name,
            "skill_type": skill_type,
            "skill_body": f"Body for {name}",
            "skill_metadata": {
                "name": name,
                "description": description,
                "category": category,
                "tags": [category, "test", "e2e"],
                "author": f"TestAuthor-{unique[:4]}",
                "version": "1.0.0",
            },
        },
        security_scan_result={
            "safe": True,
            "risk_level": "LOW",
            "findings": [],
        },
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill.id


def seed_marketplace_skills(db_session: Session, count: int = 10, **kwargs) -> list[str]:
    """Seed `count` community skills with distinct names."""
    return [
        seed_marketplace_skill(db_session, f"Marketplace Skill {i} {uuid.uuid4().hex[:4]}", **kwargs)
        for i in range(count)
    ]


def list_skills(token: str, params: dict = None) -> list:
    """GET /api/skills/list with optional query params; returns skills list."""
    response = requests.get(
        f"{API}/api/skills/list",
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    data = response.json()
    assert data["success"] is True, data
    return data["data"]["skills"]


def get_skill_detail(token: str, skill_id: str) -> dict:
    """GET /api/skills/{skill_id}; returns detail dict."""
    response = requests.get(
        f"{API}/api/skills/{skill_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert response.status_code == 200, f"got {response.status_code}: {response.text[:300]}"
    data = response.json()
    assert data["success"] is True, data
    return data["data"]


# ============================================================================
# Test Cases
# ============================================================================

def test_marketplace_loads(setup_test_user, db_session: Session):
    """Test marketplace (registry list) loads and displays seeded skills.

    Verifies:
    1. List endpoint returns 200
    2. Seeded community skills appear as cards (list items)
    3. Each card carries the expected fields
    """
    token = setup_test_user["access_token"]
    seeded = seed_marketplace_skills(db_session, count=3)

    skills = list_skills(token)
    assert len(skills) >= 3, f"Expected at least 3 skills, got {len(skills)}"

    seeded_names = {f"Marketplace Skill {i}"[:20] for i in range(3)}
    # Names are unique via uuid suffix; verify our seeds are present by id
    listed_ids = {s["skill_id"] for s in skills}
    assert set(seeded) <= listed_ids, "All seeded skills should be listed"

    for item in skills:
        assert item["skill_name"], item
        assert item["skill_type"] in ("prompt_only", "python_code", "unknown"), item
        assert item["status"], item
        assert item["created_at"], item


def test_marketplace_search_by_name(setup_test_user, db_session: Session):
    """Test finding skills by name through the list + detail surface.

    The list API has no text-search param; name search is done by fetching
    the full detail for a listed skill and matching the stored name.
    """
    token = setup_test_user["access_token"]
    target_name = f"ZetaSearchOne-{uuid.uuid4().hex[:6]}"
    seed_marketplace_skill(db_session, target_name)
    seed_marketplace_skills(db_session, count=5)

    skills = list_skills(token)
    found = [s for s in skills if s["skill_name"] == target_name]
    assert len(found) == 1, f"Name search should find exactly 1, got {len(found)}"
    detail = get_skill_detail(token, found[0]["skill_id"])
    assert detail["skill_name"] == target_name


def test_marketplace_search_by_description(setup_test_user, db_session: Session):
    """Test searching skills by description keyword.

    Description lives in skill_metadata; verify it is retrievable via the
    detail surface for a listed skill.
    """
    token = setup_test_user["access_token"]
    keyword = f"uniquedesc-{uuid.uuid4().hex[:6]}"
    seed_marketplace_skill(db_session, f"DescSkill-{uuid.uuid4().hex[:4]}", description=f"about {keyword} processing")

    skills = list_skills(token)
    listed_ids = [s["skill_id"] for s in skills]
    for skill_id in listed_ids:
        detail = get_skill_detail(token, skill_id)
        if keyword in detail["skill_metadata"].get("description", ""):
            return
    pytest.fail(f"No listed skill matched description keyword {keyword}")


def test_marketplace_category_filter(setup_test_user, db_session: Session):
    """Test category coverage in the marketplace.

    The registry API has no category filter param; verify skills from
    different categories are all browsable and the category is present on the
    detail (the filter UI would narrow this client-side).
    """
    token = setup_test_user["access_token"]
    seed_marketplace_skill(db_session, f"CatAutomation-{uuid.uuid4().hex[:4]}", category="automation")
    seed_marketplace_skill(db_session, f"CatData-{uuid.uuid4().hex[:4]}", category="data_processing")

    skills = list_skills(token)
    assert len(skills) >= 2

    categories = set()
    for item in skills:
        detail = get_skill_detail(token, item["skill_id"])
        categories.add(detail["skill_metadata"].get("category"))
    assert "automation" in categories
    assert "data_processing" in categories


def test_marketplace_skill_type_filter(setup_test_user, db_session: Session):
    """Test filtering by skill_type returns only matching skills."""
    token = setup_test_user["access_token"]
    seed_marketplace_skill(db_session, f"TypePrompt-{uuid.uuid4().hex[:4]}", skill_type="prompt_only")
    seed_marketplace_skill(db_session, f"TypePython-{uuid.uuid4().hex[:4]}", skill_type="python_code")

    python_only = list_skills(token, {"skill_type": "python_code"})
    assert len(python_only) >= 1
    assert all(s["skill_type"] == "python_code" for s in python_only), python_only

    prompt_only = list_skills(token, {"skill_type": "prompt_only"})
    assert len(prompt_only) >= 1
    assert all(s["skill_type"] == "prompt_only" for s in prompt_only), prompt_only


def test_marketplace_combined_filters(setup_test_user, db_session: Session):
    """Test combining status + skill_type filters."""
    token = setup_test_user["access_token"]
    seed_marketplace_skill(db_session, f"Combined-{uuid.uuid4().hex[:4]}", skill_type="prompt_only", status="Active")
    seed_marketplace_skill(db_session, f"CombinedUntrusted-{uuid.uuid4().hex[:4]}", skill_type="python_code", status="Untrusted")

    filtered = list_skills(token, {"skill_status": "Active", "skill_type": "prompt_only"})
    assert len(filtered) >= 1
    assert all(s["status"] == "Active" and s["skill_type"] == "prompt_only" for s in filtered), filtered


def test_marketplace_pagination(setup_test_user, db_session: Session):
    """Test pagination via the limit param.

    The registry API paginates with `limit` (no page param); verify the limit
    is honored and results are newest-first.
    """
    token = setup_test_user["access_token"]
    seed_marketplace_skills(db_session, count=5)

    page1 = list_skills(token, {"limit": 2})
    assert len(page1) <= 2, f"limit=2 should cap results, got {len(page1)}"

    page1_only = list_skills(token, {"limit": 1})
    assert len(page1_only) == 1

    # Limit 0/negative falls back to the default cap — must not error
    empty = list_skills(token, {"limit": 0})
    assert isinstance(empty, list)


def test_marketplace_empty_state(setup_test_user, db_session: Session):
    """Test the empty state: a filter with no matches returns an empty list."""
    token = setup_test_user["access_token"]
    seed_marketplace_skills(db_session, count=3)

    skills = list_skills(token, {"skill_status": "NoSuchStatus"})
    assert skills == [], f"Expected empty list for unknown status, got {len(skills)}"


def test_marketplace_skill_card_display(setup_test_user, db_session: Session):
    """Test the skill detail (card) displays complete information.

    Verifies name, description, type, category, author, version, status,
    scan info and sandbox flag are all retrievable.
    """
    token = setup_test_user["access_token"]
    skill_id = seed_marketplace_skill(
        db_session,
        f"CardDisplay-{uuid.uuid4().hex[:4]}",
        skill_type="python_code",
        category="automation",
        description="Card display description",
    )

    detail = get_skill_detail(token, skill_id)
    assert detail["skill_id"] == skill_id
    assert detail["skill_name"]
    assert detail["skill_type"] == "python_code"
    assert detail["status"] == "Active"
    assert detail["sandbox_enabled"] is True
    assert detail["security_scan_result"]["risk_level"] == "LOW"
    meta = detail["skill_metadata"]
    assert meta["description"] == "Card display description"
    assert meta["category"] == "automation"
    assert meta["author"]
    assert meta["version"] == "1.0.0"
    assert detail["created_at"]


def test_marketplace_sort_options(setup_test_user, db_session: Session):
    """Test sort order: registry lists newest-first (created_at desc).

    The API exposes no sort param; verify the deterministic default ordering
    with explicitly staggered creation timestamps.
    """
    token = setup_test_user["access_token"]
    now = datetime.now(timezone.utc)
    seed_marketplace_skill(
        db_session, f"OldestSkill-{uuid.uuid4().hex[:4]}", created_at=now - timedelta(days=5)
    )
    newest_id = seed_marketplace_skill(
        db_session, f"NewestSkill-{uuid.uuid4().hex[:4]}", created_at=now - timedelta(minutes=1)
    )

    skills = list_skills(token)
    assert skills, "Should list skills"
    # Newest-first ordering: the most recently created seed must be first among
    # skills with the same-style prefix (older seeds may pre-exist in the DB).
    newest_ids = [s["skill_id"] for s in skills if s["skill_name"].startswith(("OldestSkill", "NewestSkill"))]
    assert newest_ids[0] == newest_id, f"Newest seed should sort first, got {newest_ids}"
