"""
Test Skill Marketplace Service - Local PostgreSQL marketplace with Atom SaaS sync architecture.

Coverage:
- Local PostgreSQL marketplace search (full-text search on skill_id and description)
- Category filtering and aggregation
- Skill type filtering (prompt_only, python_code, nodejs)
- Pagination (page, page_size)
- Sorting (relevance, created, name)
- Skill details with ratings from local SkillRating model
- Category listing from community skills
- Rating submission (create/update logic)
- Skill installation via SkillRegistryService
- Average rating calculation

Tests use local community skills database (SkillExecution model).
Atom SaaS client mocking not needed (local implementation).

Reference: Phase 60 Plan 01 - Local Marketplace Implementation
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.models import SkillExecution, SkillRating
from core.skill_marketplace_service import SkillMarketplaceService


@pytest.fixture
def marketplace_service(db_session: Session):
    """Create marketplace service fixture."""
    return SkillMarketplaceService(db_session)


@pytest.fixture
def sample_marketplace_skills(db_session: Session):
    """Create sample marketplace skills for testing."""
    skills = []
    categories = ["data", "automation", "integration"]
    skill_types = ["prompt_only", "python_code", "nodejs"]

    for i in range(15):
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id=f"community_test_skill_{i}",
            status="Active",
            input_params={
                "skill_name": f"Test Skill {i}",
                "skill_type": skill_types[i % 3],
                "skill_metadata": {
                    "description": f"Test skill {i} for marketplace testing",
                    "category": categories[i % 3],
                    "tags": ["test", "sample", f"tag{i}"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": f"print('skill {i}')"
            },
            skill_source="community",
            security_scan_result={"safe": True, "risk_level": "LOW"},
            sandbox_enabled=(i % 2 == 1)
        )
        skills.append(skill)
        db.add(skill)

    db.commit()
    return skills


class TestMarketplaceSearch:
    """Test marketplace search functionality."""

    def test_search_all_skills(self, marketplace_service, sample_marketplace_skills):
        """Test searching all skills without filters."""
        result = marketplace_service.search_skills()

        assert result["total"] >= 15
        assert len(result["skills"]) >= 15
        assert result["page"] == 1
        assert result["source"] == "local"

    def test_search_with_query(self, marketplace_service, sample_marketplace_skills):
        """Test searching with text query."""
        result = marketplace_service.search_skills(query="Test Skill 5")

        assert result["total"] >= 1
        assert any("5" in s["skill_name"] for s in result["skills"])

    def test_search_by_category(self, marketplace_service, sample_marketplace_skills):
        """Test filtering by category."""
        result = marketplace_service.search_skills(category="data")

        # Should only return skills in "data" category
        for skill in result["skills"]:
            assert skill["category"] == "data" or result["total"] == 0

    def test_search_by_skill_type(self, marketplace_service, sample_marketplace_skills):
        """Test filtering by skill type."""
        result = marketplace_service.search_skills(skill_type="python_code")

        # Should only return python_code skills
        for skill in result["skills"]:
            assert skill["skill_type"] == "python_code"

    def test_search_by_nodejs_type(self, marketplace_service, sample_marketplace_skills):
        """Test filtering by nodejs skill type."""
        result = marketplace_service.search_skills(skill_type="nodejs")

        for skill in result["skills"]:
            assert skill["skill_type"] == "nodejs"

    def test_pagination(self, marketplace_service, sample_marketplace_skills):
        """Test pagination with page and page_size."""
        result = marketplace_service.search_skills(page=1, page_size=5)

        assert len(result["skills"]) <= 5
        assert result["page"] == 1
        assert result["page_size"] == 5

    def test_pagination_second_page(self, marketplace_service, sample_marketplace_skills):
        """Test pagination on second page."""
        result1 = marketplace_service.search_skills(page=1, page_size=5)
        result2 = marketplace_service.search_skills(page=2, page_size=5)

        # Different skills on different pages
        skills1_ids = [s["id"] for s in result1["skills"]]
        skills2_ids = [s["id"] for s in result2["skills"]]
        assert len(set(skills1_ids) & set(skills2_ids)) == 0  # No overlap

    def test_sorting_by_created(self, marketplace_service, sample_marketplace_skills):
        """Test sorting by creation date."""
        result = marketplace_service.search_skills(sort_by="created")

        # Verify skills are returned (newest first by default)
        assert len(result["skills"]) >= 15

    def test_sorting_by_name(self, marketplace_service, sample_marketplace_skills):
        """Test sorting by skill name."""
        result = marketplace_service.search_skills(sort_by="name")

        # Verify skills are returned
        assert len(result["skills"]) >= 15

    def test_empty_search(self, marketplace_service, sample_marketplace_skills):
        """Test search with no matching results."""
        result = marketplace_service.search_skills(query="nonexistent_skill_xyz")

        assert result["total"] == 0
        assert len(result["skills"]) == 0


class TestMarketplaceSkillDetails:
    """Test skill details retrieval."""

    def test_get_skill_by_id(self, marketplace_service, sample_marketplace_skills):
        """Test getting skill details by ID."""
        skill_id = sample_marketplace_skills[0].id
        skill = marketplace_service.get_skill_by_id(skill_id)

        assert skill is not None
        assert skill["id"] == skill_id
        assert "skill_name" in skill
        assert "skill_type" in skill
        assert "category" in skill

    def test_get_nonexistent_skill(self, marketplace_service):
        """Test getting a skill that doesn't exist."""
        skill = marketplace_service.get_skill_by_id("nonexistent_id")

        assert skill is None

    def test_skill_has_ratings_field(self, marketplace_service, sample_marketplace_skills):
        """Test skill details include ratings information."""
        skill_id = sample_marketplace_skills[0].id
        skill = marketplace_service.get_skill_by_id(skill_id)

        assert "avg_rating" in skill
        assert "rating_count" in skill
        assert "ratings" in skill
        assert isinstance(skill["ratings"], list)


class TestMarketplaceRatings:
    """Test rating submission and aggregation."""

    def test_submit_rating(self, marketplace_service, sample_marketplace_skills):
        """Test submitting a new rating."""
        skill_id = sample_marketplace_skills[0].id
        result = marketplace_service.rate_skill(
            skill_id=skill_id,
            user_id="test-user",
            rating=5,
            comment="Great skill!"
        )

        assert result["success"] is True
        assert result["action"] == "created"
        assert result["average_rating"] == 5.0
        assert result["rating_count"] == 1

    def test_submit_rating_with_comment(self, marketplace_service, sample_marketplace_skills):
        """Test submitting a rating with a comment."""
        skill_id = sample_marketplace_skills[0].id
        result = marketplace_service.rate_skill(
            skill_id=skill_id,
            user_id="test-user-2",
            rating=4,
            comment="Good skill, works well"
        )

        assert result["success"] is True
        assert result["action"] == "created"

    def test_update_existing_rating(self, marketplace_service, sample_marketplace_skills):
        """Test updating an existing rating."""
        skill_id = sample_marketplace_skills[0].id
        user_id = "test-user-3"

        # Create initial rating
        marketplace_service.rate_skill(skill_id, user_id, 3, "Okay")

        # Update rating
        result = marketplace_service.rate_skill(
            skill_id=skill_id,
            user_id=user_id,
            rating=5,
            comment="Updated to 5 stars"
        )

        assert result["action"] == "updated"
        assert result["average_rating"] == 5.0

    def test_invalid_rating_too_low(self, marketplace_service, sample_marketplace_skills):
        """Test rejection of rating below 1."""
        result = marketplace_service.rate_skill(
            skill_id=sample_marketplace_skills[0].id,
            user_id="test-user",
            rating=0  # Invalid
        )

        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

    def test_invalid_rating_too_high(self, marketplace_service, sample_marketplace_skills):
        """Test rejection of rating above 5."""
        result = marketplace_service.rate_skill(
            skill_id=sample_marketplace_skills[0].id,
            user_id="test-user",
            rating=6  # Invalid
        )

        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

    def test_rate_nonexistent_skill(self, marketplace_service):
        """Test rating a skill that doesn't exist."""
        result = marketplace_service.rate_skill(
            skill_id="nonexistent_id",
            user_id="test-user",
            rating=5
        )

        assert result["success"] is False
        assert "Skill not found" in result["error"]

    def test_average_rating_calculation(self, marketplace_service, sample_marketplace_skills):
        """Test average rating is calculated correctly."""
        skill_id = sample_marketplace_skills[0].id

        # Submit multiple ratings
        marketplace_service.rate_skill(skill_id, "user1", 5)
        marketplace_service.rate_skill(skill_id, "user2", 4)
        marketplace_service.rate_skill(skill_id, "user3", 3)

        # Get skill details
        skill = marketplace_service.get_skill_by_id(skill_id)

        # Average should be (5 + 4 + 3) / 3 = 4.0
        assert skill["avg_rating"] == 4.0
        assert skill["rating_count"] == 3


class TestMarketplaceCategories:
    """Test category listing."""

    def test_list_categories(self, marketplace_service, sample_marketplace_skills):
        """Test getting all categories."""
        categories = marketplace_service.get_categories()

        assert len(categories) > 0
        assert all("name" in c and "display_name" in c for c in categories)

    def test_category_has_count(self, marketplace_service, sample_marketplace_skills):
        """Test categories include skill counts."""
        categories = marketplace_service.get_categories()

        for cat in categories:
            assert "skill_count" in cat
            assert isinstance(cat["skill_count"], int)
            assert cat["skill_count"] >= 0

    def test_expected_categories_present(self, marketplace_service, sample_marketplace_skills):
        """Test expected categories are present from sample data."""
        categories = marketplace_service.get_categories()
        category_names = [c["name"] for c in categories]

        # Sample data includes these categories
        assert "data" in category_names
        assert "automation" in category_names
        assert "integration" in category_names


class TestMarketplaceInstall:
    """Test skill installation."""

    def test_install_skill(self, marketplace_service, sample_marketplace_skills):
        """Test installing a skill from marketplace."""
        skill_id = sample_marketplace_skills[0].id
        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent"
        )

        assert result["success"] is True
        assert result["skill_id"] == skill_id
        assert "agent_id" in result

    def test_install_nonexistent_skill(self, marketplace_service):
        """Test installing a skill that doesn't exist."""
        result = marketplace_service.install_skill(
            skill_id="nonexistent_id",
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_install_skill_with_deps(self, marketplace_service, sample_marketplace_skills):
        """Test installing a skill with auto_install_deps flag."""
        skill_id = sample_marketplace_skills[0].id
        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent",
            auto_install_deps=True
        )

        # Installation should succeed (deps flag is parameter)
        assert result["success"] is True


class TestMarketplaceDataEnrichment:
    """Test data enrichment in search results."""

    def test_search_results_include_ratings(self, marketplace_service, sample_marketplace_skills):
        """Test search results include rating information."""
        # Add a rating first
        skill_id = sample_marketplace_skills[0].id
        marketplace_service.rate_skill(skill_id, "test-user", 5)

        # Search
        result = marketplace_service.search_skills()

        # Find the rated skill
        rated_skill = next((s for s in result["skills"] if s["id"] == skill_id), None)
        assert rated_skill is not None
        assert "avg_rating" in rated_skill
        assert "rating_count" in rated_skill

    def test_search_results_include_skill_metadata(self, marketplace_service, sample_marketplace_skills):
        """Test search results include complete skill metadata."""
        result = marketplace_service.search_skills()

        if len(result["skills"]) > 0:
            skill = result["skills"][0]
            # Check required fields
            assert "id" in skill
            assert "skill_id" in skill
            assert "skill_name" in skill
            assert "skill_type" in skill
            assert "description" in skill
            assert "category" in skill
            assert "tags" in skill
            assert "author" in skill
            assert "version" in skill
            assert "created_at" in skill
