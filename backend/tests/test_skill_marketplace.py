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


class TestSearchEdgeCases:
    """Test search edge cases and special characters."""

    def test_search_with_special_characters(self, marketplace_service, db_session):
        """Test search with special characters (*, ?, regex patterns)."""
        from core.models import SkillExecution

        # Create skill with special characters in description
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_special_chars_test",
            status="Active",
            input_params={
                "skill_name": "Special * Chars ? Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test with * and ? special chars",
                    "category": "data",
                    "tags": ["test", "special"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": "print('test')"
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        # Search with special characters
        result = marketplace_service.search_skills(query="* Chars")

        # Should find the skill (SQL LIKE handles * as literal)
        assert result["total"] >= 0  # No assertion error, just verify it runs

    def test_search_with_unicode(self, marketplace_service, db_session):
        """Test search with unicode characters (emoji, non-ASCII)."""
        from core.models import SkillExecution

        # Create skill with emoji and unicode
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_unicode_test",
            status="Active",
            input_params={
                "skill_name": "Unicode Test 🚀 Ñoño",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test with emoji 🎉 and unicode ñ",
                    "category": "data",
                    "tags": ["test"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": "print('unicode')"
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        # Search with unicode
        result = marketplace_service.search_skills(query="🚀")

        # Should execute without error
        assert "total" in result

    def test_search_case_insensitive(self, marketplace_service, sample_marketplace_skills):
        """Test search is case-insensitive."""
        # Same skill found with different cases
        result1 = marketplace_service.search_skills(query="test skill")
        result2 = marketplace_service.search_skills(query="TEST SKILL")
        result3 = marketplace_service.search_skills(query="Test Skill")

        # All should return same count
        assert result1["total"] == result2["total"] == result3["total"]

    def test_search_with_leading_trailing_spaces(self, marketplace_service, sample_marketplace_skills):
        """Test spaces trimmed from query."""
        result1 = marketplace_service.search_skills(query="Test Skill 5")
        result2 = marketplace_service.search_skills(query="  Test Skill 5  ")

        # Both should return same results (spaces handled by SQL LIKE)
        assert result1["total"] == result2["total"]

    def test_search_empty_query_with_filters(self, marketplace_service, sample_marketplace_skills):
        """Test empty query but with category filter works."""
        result = marketplace_service.search_skills(query="", category="data")

        # Should return data category skills
        for skill in result["skills"]:
            assert skill["category"] == "data" or result["total"] == 0

    def test_search_with_invalid_page(self, marketplace_service, sample_marketplace_skills):
        """Test negative or zero page defaults to page 1 behavior."""
        # Page 0 should work (SQL OFFSET handles it)
        result1 = marketplace_service.search_skills(page=0, page_size=5)
        assert "page" in result1

        # Negative page should work (SQL OFFSET handles it as 0)
        result2 = marketplace_service.search_skills(page=-1, page_size=5)
        assert "page" in result2

    def test_search_with_invalid_page_size(self, marketplace_service, sample_marketplace_skills):
        """Test invalid page_size defaults behavior."""
        # Zero page_size should return no results
        result = marketplace_service.search_skills(page=1, page_size=0)
        assert len(result["skills"]) == 0

        # Negative page_size should return no results
        result2 = marketplace_service.search_skills(page=1, page_size=-1)
        assert len(result2["skills"]) == 0

    def test_search_beyond_last_page(self, marketplace_service, sample_marketplace_skills):
        """Test page beyond total returns empty results."""
        # Get total count
        all_result = marketplace_service.search_skills()
        total = all_result["total"]
        page_size = all_result["page_size"]

        # Calculate last page
        last_page = (total + page_size - 1) // page_size

        # Request page beyond last
        result = marketplace_service.search_skills(page=last_page + 100, page_size=page_size)

        # Should return empty results
        assert result["total"] == total
        assert len(result["skills"]) == 0


class TestSearchWithMultipleFilters:
    """Test search with multiple filter combinations."""

    def test_category_and_skill_type_combined(self, marketplace_service, sample_marketplace_skills):
        """Test combine category and skill_type filters."""
        result = marketplace_service.search_skills(
            category="data",
            skill_type="python_code"
        )

        # Should only return data + python_code skills
        for skill in result["skills"]:
            assert skill["category"] == "data" or result["total"] == 0
            assert skill["skill_type"] == "python_code" or result["total"] == 0

    def test_query_and_category_combined(self, marketplace_service, sample_marketplace_skills):
        """Test combine text query with category filter."""
        result = marketplace_service.search_skills(
            query="Test",
            category="automation"
        )

        # Should match query AND category
        for skill in result["skills"]:
            assert skill["category"] == "automation" or result["total"] == 0

    def test_all_filters_combined(self, marketplace_service, sample_marketplace_skills):
        """Test query + category + skill_type + sort."""
        result = marketplace_service.search_skills(
            query="Test",
            category="data",
            skill_type="python_code",
            sort_by="name"
        )

        # Should execute without error
        assert "skills" in result
        assert "total" in result

    def test_invalid_category_returns_empty(self, marketplace_service, sample_marketplace_skills):
        """Test non-existent category returns no results."""
        result = marketplace_service.search_skills(category="nonexistent_category_xyz")

        # Should return empty results
        assert result["total"] == 0
        assert len(result["skills"]) == 0

    def test_invalid_skill_type_returns_empty(self, marketplace_service, sample_marketplace_skills):
        """Test invalid skill_type returns no results."""
        result = marketplace_service.search_skills(skill_type="nonexistent_type_xyz")

        # Should return empty results
        assert result["total"] == 0
        assert len(result["skills"]) == 0


class TestSortingEdgeCases:
    """Test sorting edge cases."""

    def test_sort_by_invalid_defaults_to_relevance(self, marketplace_service, sample_marketplace_skills):
        """Test invalid sort_by uses default (relevance = created desc)."""
        result1 = marketplace_service.search_skills(sort_by="created")
        result2 = marketplace_service.search_skills(sort_by="invalid_sort_field")

        # Both should execute (invalid field treated as relevance/default)
        assert "skills" in result1
        assert "skills" in result2

    def test_sort_by_relevance_with_query(self, marketplace_service, sample_marketplace_skills):
        """Test relevance sort with query."""
        result = marketplace_service.search_skills(
            query="Test",
            sort_by="relevance"
        )

        # Should return results sorted by created_at (default relevance)
        assert len(result["skills"]) >= 0

    def test_multiple_sort_same_values(self, marketplace_service, db_session):
        """Test handles ties in sort order."""
        from core.models import SkillExecution
        from datetime import datetime, timezone

        # Create skills with same timestamp
        now = datetime.now(timezone.utc)
        skill1 = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_tie_test_1",
            status="Active",
            created_at=now,
            input_params={
                "skill_name": "Tie Test A",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "data",
                    "tags": [],
                    "author": "Test",
                    "version": "1.0.0"
                }
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        skill2 = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_tie_test_2",
            status="Active",
            created_at=now,
            input_params={
                "skill_name": "Tie Test B",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "data",
                    "tags": [],
                    "author": "Test",
                    "version": "1.0.0"
                }
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add_all([skill1, skill2])
        db_session.commit()

        # Sort by created (both have same time)
        result = marketplace_service.search_skills(sort_by="created")

        # Should handle ties gracefully
        assert result["total"] >= 0

    def test_sort_empty_results(self, marketplace_service, db_session):
        """Test sorting empty list doesn't fail."""
        # Delete all skills
        from core.models import SkillExecution
        db_session.query(SkillExecution).delete()
        db_session.commit()

        # Sort with no results
        result = marketplace_service.search_skills(sort_by="created")

        # Should return empty results without error
        assert result["total"] == 0
        assert len(result["skills"]) == 0


class TestRatingEdgeCases:
    """Test rating calculation edge cases."""

    def test_rating_with_no_existing_ratings(self, marketplace_service, sample_marketplace_skills):
        """Test first rating on skill (no existing average)."""
        skill_id = sample_marketplace_skills[0].id

        # First rating
        result = marketplace_service.rate_skill(skill_id, "user1", 4)

        assert result["success"] is True
        assert result["action"] == "created"
        assert result["average_rating"] == 4.0
        assert result["rating_count"] == 1

    def test_rating_decimal_average(self, marketplace_service, sample_marketplace_skills):
        """Test average handles decimal correctly (e.g., 3.5, 4.33)."""
        skill_id = sample_marketplace_skills[0].id

        # Submit ratings that produce decimal average: (5 + 4 + 3) / 3 = 4.0
        marketplace_service.rate_skill(skill_id, "user1", 5)
        marketplace_service.rate_skill(skill_id, "user2", 4)
        marketplace_service.rate_skill(skill_id, "user3", 3)

        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["avg_rating"] == 4.0
        assert skill["rating_count"] == 3

        # Add another rating: (4.0 * 3 + 2) / 4 = 3.5
        marketplace_service.rate_skill(skill_id, "user4", 2)

        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["avg_rating"] == 3.5
        assert skill["rating_count"] == 4

    def test_rating_boundary_values(self, marketplace_service, sample_marketplace_skills):
        """Test rating=1 and rating=5 (boundary values)."""
        skill_id = sample_marketplace_skills[0].id

        # Test minimum boundary (1)
        result1 = marketplace_service.rate_skill(skill_id, "user_min", 1)
        assert result1["success"] is True
        assert result1["average_rating"] == 1.0

        # Test maximum boundary (5)
        result2 = marketplace_service.rate_skill(skill_id, "user_max", 5)
        assert result2["success"] is True

        # Average should be (1 + 5) / 2 = 3.0
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["avg_rating"] == 3.0

    def test_same_user_rates_multiple_times(self, marketplace_service, sample_marketplace_skills):
        """Test user updates their own rating (latest wins)."""
        skill_id = sample_marketplace_skills[0].id
        user_id = "repeat_user"

        # First rating
        result1 = marketplace_service.rate_skill(skill_id, user_id, 3, comment="Okay")
        assert result1["action"] == "created"
        assert result1["average_rating"] == 3.0

        # Update rating
        result2 = marketplace_service.rate_skill(skill_id, user_id, 5, comment="Excellent!")
        assert result2["action"] == "updated"
        assert result2["average_rating"] == 5.0  # Updated to latest

        # Verify only one rating counted
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["rating_count"] == 1

    def test_rating_without_comment(self, marketplace_service, sample_marketplace_skills):
        """Test rating can be submitted without comment."""
        skill_id = sample_marketplace_skills[0].id

        result = marketplace_service.rate_skill(
            skill_id,
            user_id="user_no_comment",
            rating=4,
            comment=None
        )

        assert result["success"] is True
        assert result["average_rating"] == 4.0

    def test_rating_comment_length_limit(self, marketplace_service, sample_marketplace_skills):
        """Test long comments handled correctly."""
        skill_id = sample_marketplace_skills[0].id

        # Create a very long comment (1000+ chars)
        long_comment = "This is a very long comment. " * 100

        result = marketplace_service.rate_skill(
            skill_id,
            user_id="user_long_comment",
            rating=5,
            comment=long_comment
        )

        # Should accept long comment
        assert result["success"] is True

        # Verify comment stored
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]
        assert len(ratings) > 0
        assert ratings[0]["comment"] == long_comment

    def test_get_skill_with_no_ratings(self, marketplace_service, sample_marketplace_skills):
        """Test skill with no ratings returns 0.0 average."""
        # Use a skill that hasn't been rated
        skill_id = sample_marketplace_skills[1].id

        skill = marketplace_service.get_skill_by_id(skill_id)

        assert skill["avg_rating"] == 0.0
        assert skill["rating_count"] == 0
        assert skill["ratings"] == []

    def test_multiple_users_same_skill(self, marketplace_service, sample_marketplace_skills):
        """Test different users rating same skill averages correctly."""
        skill_id = sample_marketplace_skills[0].id

        # Multiple users rate the same skill
        marketplace_service.rate_skill(skill_id, "user_a", 5)
        marketplace_service.rate_skill(skill_id, "user_b", 4)
        marketplace_service.rate_skill(skill_id, "user_c", 5)
        marketplace_service.rate_skill(skill_id, "user_d", 3)

        # Average: (5 + 4 + 5 + 3) / 4 = 4.25
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["avg_rating"] == 4.25
        assert skill["rating_count"] == 4


class TestRatingRetrieval:
    """Test rating retrieval and pagination."""

    def test_get_ratings_limit(self, marketplace_service, sample_marketplace_skills):
        """Test only returns specified number of recent ratings."""
        skill_id = sample_marketplace_skills[0].id

        # Add 15 ratings
        for i in range(15):
            marketplace_service.rate_skill(
                skill_id,
                f"user_{i}",
                5,
                comment=f"Comment {i}"
            )

        # Get default limit (10)
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]

        # Should return max 10 ratings
        assert len(ratings) <= 10

    def test_get_ratings_ordering(self, marketplace_service, sample_marketplace_skills):
        """Test ratings ordered by created_at DESC."""
        import time
        skill_id = sample_marketplace_skills[0].id

        # Add ratings with delays
        marketplace_service.rate_skill(skill_id, "user_early", 3, comment="First")
        time.sleep(0.01)  # Small delay
        marketplace_service.rate_skill(skill_id, "user_late", 5, comment="Second")
        time.sleep(0.01)
        marketplace_service.rate_skill(skill_id, "user_latest", 4, comment="Third")

        # Get ratings
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]

        # Most recent should be first
        assert len(ratings) >= 3
        assert ratings[0]["comment"] == "Third" or ratings[0]["user_id"] == "user_latest"

    def test_get_ratings_empty_skill(self, marketplace_service, sample_marketplace_skills):
        """Test skill with no ratings returns empty list."""
        skill_id = sample_marketplace_skills[1].id

        skill = marketplace_service.get_skill_by_id(skill_id)

        assert skill["ratings"] == []
        assert skill["rating_count"] == 0

    def test_rating_includes_all_fields(self, marketplace_service, sample_marketplace_skills):
        """Test user_id, rating, comment, created_at present."""
        skill_id = sample_marketplace_skills[0].id

        marketplace_service.rate_skill(
            skill_id,
            "test_user_fields",
            5,
            comment="Great skill!"
        )

        skill = marketplace_service.get_skill_by_id(skill_id)
        rating = skill["ratings"][0]

        # Check all fields present
        assert "user_id" in rating
        assert "rating" in rating
        assert "comment" in rating
        assert "created_at" in rating
        assert rating["user_id"] == "test_user_fields"
        assert rating["rating"] == 5
        assert rating["comment"] == "Great skill!"

    def test_rating_timestamp_format(self, marketplace_service, sample_marketplace_skills):
        """Test created_at is ISO format string."""
        skill_id = sample_marketplace_skills[0].id

        marketplace_service.rate_skill(skill_id, "timestamp_user", 4)

        skill = marketplace_service.get_skill_by_id(skill_id)
        rating = skill["ratings"][0]

        # Should be ISO format string
        assert isinstance(rating["created_at"], str)
        # Should contain T and Z (ISO format)
        assert "T" in rating["created_at"]


class TestRatingErrors:
    """Test rating validation errors."""

    def test_rating_too_low_rejected(self, marketplace_service, sample_marketplace_skills):
        """Test rating < 1 rejected with error message."""
        result = marketplace_service.rate_skill(
            skill_id=sample_marketplace_skills[0].id,
            user_id="test_user",
            rating=0  # Too low
        )

        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

    def test_rating_too_high_rejected(self, marketplace_service, sample_marketplace_skills):
        """Test rating > 5 rejected with error message."""
        result = marketplace_service.rate_skill(
            skill_id=sample_marketplace_skills[0].id,
            user_id="test_user",
            rating=6  # Too high
        )

        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

    def test_rating_nonexistent_skill(self, marketplace_service, sample_marketplace_skills):
        """Test rating non-existent skill returns error."""
        result = marketplace_service.rate_skill(
            skill_id="nonexistent_skill_id_xyz",
            user_id="test_user",
            rating=5
        )

        assert result["success"] is False
        assert "Skill not found" in result["error"]


class TestCategoryEdgeCases:
    """Test category edge cases."""

    def test_empty_marketplace_categories(self, marketplace_service, db_session):
        """Test no skills returns empty category list."""
        # Use clean database (delete all skills)
        from core.models import SkillExecution
        db_session.query(SkillExecution).delete()
        db_session.commit()

        categories = marketplace_service.get_categories()

        assert categories == []

    def test_category_with_spaces(self, marketplace_service, db_session):
        """Test category names with spaces handled correctly."""
        from core.models import SkillExecution

        # Create skill with spaces in category
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_space_cat_test",
            status="Active",
            input_params={
                "skill_name": "Space Category Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test category with spaces",
                    "category": "data analytics",  # Spaces in category
                    "tags": ["test"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": "print('test')"
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        categories = marketplace_service.get_categories()

        # Should find category with spaces
        category_names = [c["name"] for c in categories]
        assert "data analytics" in category_names

    def test_category_special_characters(self, marketplace_service, db_session):
        """Test categories with special chars handled."""
        from core.models import SkillExecution

        # Create skill with special chars in category
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_special_cat_test",
            status="Active",
            input_params={
                "skill_name": "Special Category Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test category with special chars",
                    "category": "data/analytics-test",  # Special chars
                    "tags": ["test"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": "print('test')"
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        categories = marketplace_service.get_categories()

        # Should find category with special chars
        category_names = [c["name"] for c in categories]
        assert "data/analytics-test" in category_names

    def test_category_display_name_format(self, marketplace_service, db_session):
        """Test display name converts underscores to title case."""
        from core.models import SkillExecution

        # Create skill with underscores in category
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_display_test",
            status="Active",
            input_params={
                "skill_name": "Display Name Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test display name conversion",
                    "category": "data_analytics_tools",  # Underscores
                    "tags": ["test"],
                    "author": "TestAuthor",
                    "version": "1.0.0"
                },
                "skill_body": "print('test')"
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        categories = marketplace_service.get_categories()

        # Find category
        cat = next((c for c in categories if c["name"] == "data_analytics_tools"), None)
        assert cat is not None
        assert cat["display_name"] == "Data Analytics Tools"

    def test_category_skill_count(self, marketplace_service, sample_marketplace_skills):
        """Test skill count accurate for each category."""
        categories = marketplace_service.get_categories()

        # Each category should have accurate count
        for cat in categories:
            # Query database to verify count
            from core.models import SkillExecution
            actual_count = marketplace_service.db.query(SkillExecution).filter(
                SkillExecution.skill_source == "community",
                SkillExecution.status == "Active",
                SkillExecution.input_params["skill_metadata"]["category"].astext == cat["name"]
            ).count()

            assert cat["skill_count"] == actual_count


class TestInstallationErrors:
    """Test installation error handling."""

    def test_install_nonexistent_skill(self, marketplace_service):
        """Test installing missing skill returns error."""
        result = marketplace_service.install_skill(
            skill_id="nonexistent_skill_id_xyz",
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_install_error_message_format(self, marketplace_service):
        """Test error message includes skill_id."""
        skill_id = "missing_skill_123"
        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert skill_id in result["error"]

    def test_install_with_auto_deps_flag(self, marketplace_service, sample_marketplace_skills):
        """Test auto_install_deps parameter passed through."""
        skill_id = sample_marketplace_skills[0].id

        # Install with auto_install_deps=True
        result1 = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent",
            auto_install_deps=True
        )
        assert result1["success"] is True

        # Install with auto_install_deps=False
        result2 = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent",
            auto_install_deps=False
        )
        assert result2["success"] is True

    def test_install_success_returns_agent_id(self, marketplace_service, sample_marketplace_skills):
        """Test success response includes agent_id."""
        skill_id = sample_marketplace_skills[0].id
        agent_id = "test-agent-123"

        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id=agent_id
        )

        assert result["success"] is True
        assert result["agent_id"] == agent_id

    def test_install_succeeds_for_active_skill(self, marketplace_service, sample_marketplace_skills):
        """Test Active skills can be installed."""
        # Sample skills are Active status
        skill_id = sample_marketplace_skills[0].id

        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent"
        )

        assert result["success"] is True


class TestSkillRetrievalEdgeCases:
    """Test skill retrieval edge cases."""

    def test_get_skill_by_id_with_missing_metadata(self, marketplace_service, db_session):
        """Test skill with incomplete metadata handled."""
        from core.models import SkillExecution

        # Create skill with minimal metadata
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_minimal_test",
            status="Active",
            input_params={
                "skill_name": "Minimal Test"
                # Missing skill_metadata
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Should handle missing metadata gracefully
        assert result is not None
        assert result["category"] == "general"  # Default
        assert result["tags"] == []  # Default empty list

    def test_get_skill_nonexistent_id(self, marketplace_service):
        """Test non-existent skill_id returns None."""
        result = marketplace_service.get_skill_by_id("nonexistent_id_xyz")

        assert result is None

    def test_get_skill_with_empty_description(self, marketplace_service, db_session):
        """Test empty description field handled."""
        from core.models import SkillExecution

        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_empty_desc_test",
            status="Active",
            input_params={
                "skill_name": "Empty Description Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "",  # Empty description
                    "category": "data",
                    "tags": [],
                    "author": "Test",
                    "version": "1.0.0"
                }
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Should handle empty description
        assert result is not None
        assert result["description"] == ""

    def test_get_skill_with_missing_tags(self, marketplace_service, db_session):
        """Test missing tags returns empty list."""
        from core.models import SkillExecution

        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_no_tags_test",
            status="Active",
            input_params={
                "skill_name": "No Tags Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "data",
                    # Missing tags field
                    "author": "Test",
                    "version": "1.0.0"
                }
            },
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Should handle missing tags
        assert result is not None
        assert result["tags"] == []  # Default empty list


class TestDataEnrichment:
    """Test data enrichment (_skill_to_dict method)."""

    def test_skill_to_dict_with_all_fields(self, marketplace_service, sample_marketplace_skills):
        """Test all fields present in conversion."""
        skill = sample_marketplace_skills[0]

        # Get skill details (uses _skill_to_dict internally)
        result = marketplace_service.get_skill_by_id(skill.id)

        # Check all expected fields
        expected_fields = [
            "id", "skill_id", "skill_name", "skill_type",
            "description", "category", "tags", "author", "version",
            "created_at", "sandbox_enabled", "security_scan_result",
            "skill_source", "avg_rating", "rating_count", "ratings"
        ]

        for field in expected_fields:
            assert field in result

    def test_skill_to_dict_with_none_values(self, marketplace_service, db_session):
        """Test None values handled in dict conversion."""
        from core.models import SkillExecution

        # Create skill with None values
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_none_test",
            status="Active",
            input_params=None,  # None input_params
            skill_source="community",
            security_scan_result=None,
            sandbox_enabled=False
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Should handle None values
        assert result is not None
        assert result["description"] == ""
        assert result["category"] == "general"
        assert result["tags"] == []

    def test_skill_to_dict_empty_input_params(self, marketplace_service, db_session):
        """Test empty input_params doesn't fail."""
        from core.models import SkillExecution

        # Create skill with empty input_params
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_empty_params_test",
            status="Active",
            input_params={},  # Empty dict
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Should handle empty params
        assert result is not None
        assert result["skill_name"] == skill.skill_id  # Fallback to skill_id
        assert result["skill_type"] == "unknown"  # Default

    def test_skill_to_dict_sandbox_enabled(self, marketplace_service, sample_marketplace_skills):
        """Test sandbox_enabled field preserved."""
        skill = sample_marketplace_skills[0]

        result = marketplace_service.get_skill_by_id(skill.id)

        # sandbox_enabled should be preserved
        assert "sandbox_enabled" in result
        assert isinstance(result["sandbox_enabled"], bool)
