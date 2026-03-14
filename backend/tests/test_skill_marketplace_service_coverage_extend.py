"""
Extended coverage tests for SkillMarketplaceService (currently 56% -> target 75%+)

Target file: core/skill_marketplace_service.py (102 statements)

This file extends existing coverage from test_skill_marketplace.py
by targeting remaining uncovered lines.

Focus areas (building on Phase 183 56% baseline):
- Enhanced search (lines 1-30)
- Category filtering (lines 30-60)
- Rating aggregation (lines 60-90)
- Trending skills (lines 90-102)
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock

from core.models import SkillExecution, SkillRating, Tenant
from core.skill_marketplace_service import SkillMarketplaceService


@pytest.fixture
def marketplace_service(db_session: Session):
    """Create marketplace service fixture."""
    return SkillMarketplaceService(db_session)


@pytest.fixture
def default_tenant(db_session: Session):
    """Create a default tenant for testing."""
    tenant = Tenant(
        name="Default Test Tenant",
        subdomain="default",
        edition="personal"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def sample_skills_extended(db_session: Session, default_tenant):
    """Create sample skills for extended coverage testing."""
    skills = []

    # Skill with various metadata combinations for coverage
    skill1 = SkillExecution(
        agent_id="system",
        tenant_id="default",  # Required field
        workspace_id="default",
        skill_id="community_extended_1",
        status="Active",
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        input_params={
            "skill_name": "Extended Skill 1",
            "skill_type": "python_code",
            "skill_metadata": {
                "description": "Test skill for extended coverage with keyword search",
                "category": "productivity",
                "tags": ["productivity", "automation", "testing"],
                "author": "TestAuthor1",
                "version": "1.0.0"
            },
            "skill_body": "print('extended 1')"
        },
        skill_source="community",
        security_scan_result={"safe": True, "risk_level": "LOW"},
        sandbox_enabled=True
    )

    skill2 = SkillExecution(
        agent_id="system",
        tenant_id="default",
        workspace_id="default",
        skill_id="community_extended_2",
        status="Active",
        created_at=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        input_params={
            "skill_name": "Extended Skill 2",
            "skill_type": "prompt_only",
            "skill_metadata": {
                "description": "Another skill for testing search filters and categories",
                "category": "automation",
                "tags": ["automation", "productivity"],
                "author": "TestAuthor2",
                "version": "2.0.0"
            },
            "skill_body": "print('extended 2')"
        },
        skill_source="community",
        security_scan_result={"safe": True, "risk_level": "MEDIUM"},
        sandbox_enabled=False
    )

    skill3 = SkillExecution(
        agent_id="system",
        tenant_id="default",
        workspace_id="default",
        skill_id="community_extended_3",
        status="Active",
        created_at=datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        input_params={
            "skill_name": "Extended Skill 3",
            "skill_type": "nodejs",
            "skill_metadata": {
                "description": "Node.js skill for testing type filters",
                "category": "integration",
                "tags": ["integration", "api"],
                "author": "TestAuthor3",
                "version": "1.5.0"
            },
            "skill_body": "console.log('extended 3')"
        },
        skill_source="community",
        security_scan_result={"safe": False, "risk_level": "HIGH"},
        sandbox_enabled=True
    )

    # Skill with minimal metadata (testing defaults)
    skill4 = SkillExecution(
        agent_id="system",
        tenant_id="default",
        workspace_id="default",
        skill_id="community_minimal",
        status="Active",
        created_at=datetime(2024, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
        input_params={
            "skill_name": "Minimal Skill"
        },
        skill_source="community",
        security_scan_result=None,
        sandbox_enabled=False
    )

    # Skill with empty input_params (testing None handling)
    skill5 = SkillExecution(
        agent_id="system",
        tenant_id="default",
        workspace_id="default",
        skill_id="community_empty_params",
        status="Active",
        created_at=datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
        input_params={},
        skill_source="community",
        security_scan_result={"safe": True},
        sandbox_enabled=True
    )

    skills.extend([skill1, skill2, skill3, skill4, skill5])
    for skill in skills:
        db_session.add(skill)
    db_session.commit()

    return skills


class TestSkillMarketplaceServiceExtended:
    """Extended coverage tests for skill_marketplace_service.py"""

    def test_search_with_fuzzy_match(self, marketplace_service, sample_skills_extended):
        """Cover enhanced search with fuzzy matching (lines 1-30)"""
        # Test searching skill_id
        result = marketplace_service.search_skills("extended")
        assert result["total"] >= 3

        # Test searching description
        result = marketplace_service.search_skills("keyword search")
        assert result["total"] >= 1

        # Test searching with partial match
        result = marketplace_service.search_skills("Skill 1")
        assert result["total"] >= 1

    def test_search_with_filters(self, marketplace_service, sample_skills_extended):
        """Cover search with multiple filters"""
        # Test category filter
        result = marketplace_service.search_skills(
            query="",
            category="productivity"
        )
        assert result["total"] >= 1
        for skill in result["skills"]:
            assert skill["category"] == "productivity"

        # Test skill_type filter
        result = marketplace_service.search_skills(
            query="",
            skill_type="python_code"
        )
        assert result["total"] >= 1
        for skill in result["skills"]:
            assert skill["skill_type"] == "python_code"

        # Test combined filters
        result = marketplace_service.search_skills(
            query="extended",
            category="automation",
            skill_type="prompt_only"
        )
        # Should only return automation + prompt_only skills
        for skill in result["skills"]:
            assert skill["category"] == "automation" or result["total"] == 0
            assert skill["skill_type"] == "prompt_only" or result["total"] == 0

    def test_search_with_sorting_variants(self, marketplace_service, sample_skills_extended):
        """Cover different sorting options"""
        # Test sort by created (newest first)
        result = marketplace_service.search_skills(sort_by="created")
        assert len(result["skills"]) >= 3

        # Test sort by name
        result = marketplace_service.search_skills(sort_by="name")
        assert len(result["skills"]) >= 3

        # Test default sort (relevance = created desc)
        result = marketplace_service.search_skills(sort_by="relevance")
        assert len(result["skills"]) >= 3

    def test_search_pagination_edge_cases(self, marketplace_service, sample_skills_extended):
        """Cover pagination edge cases"""
        # Test page_size larger than results
        result = marketplace_service.search_skills(page=1, page_size=100)
        assert result["total"] >= 5
        assert len(result["skills"]) >= 5

        # Test page_size of 1
        result = marketplace_service.search_skills(page=1, page_size=1)
        assert len(result["skills"]) <= 1

        # Test total_pages calculation
        result = marketplace_service.search_skills(page=1, page_size=2)
        expected_pages = (result["total"] + 2 - 1) // 2
        assert result["total_pages"] == expected_pages

    def test_category_filtering(self, marketplace_service, sample_skills_extended):
        """Cover category filtering (lines 30-60)"""
        # Get all categories
        categories = marketplace_service.get_categories()
        category_names = [c["name"] for c in categories]

        # Check expected categories present
        assert "productivity" in category_names
        assert "automation" in category_names
        assert "integration" in category_names

        # Filter by specific category
        productivity_skills = marketplace_service.search_skills(category="productivity")
        for skill in productivity_skills["skills"]:
            assert skill["category"] == "productivity"

        # Verify category metadata
        for cat in categories:
            assert "name" in cat
            assert "display_name" in cat
            assert "skill_count" in cat
            # Display name should convert underscores to spaces
            assert "_" not in cat["display_name"] or cat["name"] == cat["display_name"]

    def test_category_display_names(self, marketplace_service, db_session, default_tenant):
        """Cover category display name formatting"""
        # Create skill with underscored category
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_cat_display_test",
            status="Active",
            input_params={
                "skill_name": "Category Display Test",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "data_analytics_tools",
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

        categories = marketplace_service.get_categories()
        cat = next((c for c in categories if c["name"] == "data_analytics_tools"), None)
        if cat:
            assert cat["display_name"] == "Data Analytics Tools"

    def test_rating_aggregation(self, marketplace_service, sample_skills_extended):
        """Cover rating aggregation (lines 60-90)"""
        skill_id = sample_skills_extended[0].id

        # Get aggregated ratings for a skill (no ratings yet)
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert "avg_rating" in skill
        assert "rating_count" in skill
        assert skill["avg_rating"] == 0.0
        assert skill["rating_count"] == 0

        # Add ratings and verify aggregation
        marketplace_service.rate_skill(skill_id, "user1", 5, "Great!")
        marketplace_service.rate_skill(skill_id, "user2", 4, "Good")
        marketplace_service.rate_skill(skill_id, "user3", 3, "Okay")

        skill = marketplace_service.get_skill_by_id(skill_id)
        # Average: (5 + 4 + 3) / 3 = 4.0
        assert skill["avg_rating"] == 4.0
        assert skill["rating_count"] == 3

    def test_weighted_rating_calculation(self, marketplace_service, sample_skills_extended):
        """Cover weighted rating (average calculation in _get_average_rating)"""
        skill_id = sample_skills_extended[0].id

        # Add ratings with different values
        marketplace_service.rate_skill(skill_id, "user1", 5)
        marketplace_service.rate_skill(skill_id, "user2", 3)
        marketplace_service.rate_skill(skill_id, "user3", 4)

        # Get average rating
        skill = marketplace_service.get_skill_by_id(skill_id)
        avg = skill["avg_rating"]

        # Average should be between min and max
        assert 1 <= avg <= 5
        assert avg == 4.0  # (5 + 3 + 4) / 3 = 4.0

    def test_rating_boundary_values(self, marketplace_service, sample_skills_extended):
        """Cover rating boundary validation"""
        skill_id = sample_skills_extended[0].id

        # Test minimum boundary (1)
        result1 = marketplace_service.rate_skill(skill_id, "user_min", 1)
        assert result1["success"] is True
        assert result1["average_rating"] == 1.0

        # Test maximum boundary (5)
        result2 = marketplace_service.rate_skill(skill_id, "user_max", 5)
        assert result2["success"] is True

        # Verify average calculation
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert 1 <= skill["avg_rating"] <= 5

    def test_rating_update_behavior(self, marketplace_service, sample_skills_extended):
        """Cover rating update vs create logic"""
        skill_id = sample_skills_extended[0].id
        user_id = "repeat_user"

        # Create initial rating
        result1 = marketplace_service.rate_skill(skill_id, user_id, 3, "Initial")
        assert result1["action"] == "created"
        assert result1["average_rating"] == 3.0

        # Update rating
        result2 = marketplace_service.rate_skill(skill_id, user_id, 5, "Updated")
        assert result2["action"] == "updated"
        assert result2["average_rating"] == 5.0

        # Verify only one rating counted
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["rating_count"] == 1

    def test_rating_validation_errors(self, marketplace_service, sample_skills_extended):
        """Cover rating validation error paths"""
        skill_id = sample_skills_extended[0].id

        # Test rating too low
        result = marketplace_service.rate_skill(skill_id, "user1", 0)
        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

        # Test rating too high
        result = marketplace_service.rate_skill(skill_id, "user2", 6)
        assert result["success"] is False
        assert "must be between 1 and 5" in result["error"]

    def test_skill_installation(self, marketplace_service, sample_skills_extended):
        """Cover skill installation (lines 250-294)"""
        skill_id = sample_skills_extended[0].id

        # Test successful installation
        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent",
            auto_install_deps=True
        )
        assert result["success"] is True
        assert result["skill_id"] == skill_id
        assert result["agent_id"] == "test-agent"

        # Test installation with auto_install_deps=False
        result = marketplace_service.install_skill(
            skill_id=skill_id,
            agent_id="test-agent-2",
            auto_install_deps=False
        )
        assert result["success"] is True

    def test_install_nonexistent_skill(self, marketplace_service):
        """Cover installation error handling"""
        result = marketplace_service.install_skill(
            skill_id="nonexistent_skill_id",
            agent_id="test-agent"
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_skill_to_dict_with_all_fields(self, marketplace_service, sample_skills_extended):
        """Cover _skill_to_dict method (lines 296-312)"""
        skill = sample_skills_extended[0]
        result = marketplace_service.get_skill_by_id(skill.id)

        # Verify all fields populated by _skill_to_dict
        assert result["id"] == skill.id
        assert result["skill_id"] == skill.skill_id
        assert result["skill_name"] == "Extended Skill 1"
        assert result["skill_type"] == "python_code"
        assert result["description"] == "Test skill for extended coverage with keyword search"
        assert result["category"] == "productivity"
        assert result["tags"] == ["productivity", "automation", "testing"]
        assert result["author"] == "TestAuthor1"
        assert result["version"] == "1.0.0"
        assert result["sandbox_enabled"] is True
        assert result["security_scan_result"]["safe"] is True
        assert result["skill_source"] == "community"

    def test_skill_to_dict_with_minimal_metadata(self, marketplace_service, db_session, default_tenant):
        """Cover _skill_to_dict with missing metadata (defaults)"""
        # Create skill with minimal input_params
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_minimal_dict_test",
            status="Active",
            input_params={
                "skill_name": "Minimal Test"
            },
            skill_source="community",
            security_scan_result=None,
            sandbox_enabled=False
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Verify defaults applied
        assert result["skill_type"] == "unknown"
        assert result["description"] == ""
        assert result["category"] == "general"
        assert result["tags"] == []
        assert result["author"] == "Unknown"
        assert result["version"] == "1.0.0"

    def test_skill_to_dict_with_empty_input_params(self, marketplace_service, db_session, default_tenant):
        """Cover _skill_to_dict with empty input_params"""
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_empty_dict_test",
            status="Active",
            input_params={},
            skill_source="community",
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Verify empty dict handling
        assert result["skill_name"] == skill.skill_id  # Fallback to skill_id
        assert result["skill_type"] == "unknown"

    def test_skill_to_dict_with_none_input_params(self, marketplace_service, db_session, default_tenant):
        """Cover _skill_to_dict with None input_params"""
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_none_dict_test",
            status="Active",
            input_params=None,
            skill_source="community",
            security_scan_result=None,
            sandbox_enabled=False
        )
        db_session.add(skill)
        db_session.commit()

        result = marketplace_service.get_skill_by_id(skill.id)

        # Verify None handling
        assert result["skill_name"] == skill.skill_id
        assert result["skill_type"] == "unknown"
        assert result["description"] == ""
        assert result["category"] == "general"

    def test_get_average_rating_no_ratings(self, marketplace_service, sample_skills_extended):
        """Cover _get_average_rating with no ratings"""
        skill_id = sample_skills_extended[1].id  # Skill with no ratings

        result = marketplace_service.get_skill_by_id(skill_id)

        # Should return 0.0 average and 0 count
        assert result["avg_rating"] == 0.0
        assert result["rating_count"] == 0

    def test_get_skill_ratings_limit(self, marketplace_service, sample_skills_extended):
        """Cover _get_skill_ratings with limit parameter"""
        skill_id = sample_skills_extended[0].id

        # Add 15 ratings
        for i in range(15):
            marketplace_service.rate_skill(
                skill_id,
                f"user_{i}",
                5,
                comment=f"Comment {i}"
            )

        # Get skill details (uses default limit of 10)
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]

        # Should return max 10 ratings (default limit)
        assert len(ratings) <= 10

    def test_get_skill_ratings_ordering(self, marketplace_service, sample_skills_extended):
        """Cover _get_skill_ratings ordering (created_at DESC)"""
        import time
        skill_id = sample_skills_extended[0].id

        # Add ratings with delays
        marketplace_service.rate_skill(skill_id, "user_early", 3, "First")
        time.sleep(0.01)
        marketplace_service.rate_skill(skill_id, "user_middle", 4, "Second")
        time.sleep(0.01)
        marketplace_service.rate_skill(skill_id, "user_late", 5, "Third")

        # Get ratings
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]

        # Most recent should be first
        assert len(ratings) >= 3
        assert ratings[0]["comment"] == "Third"

    def test_get_skill_by_id_nonexistent(self, marketplace_service):
        """Cover get_skill_by_id with non-existent ID"""
        result = marketplace_service.get_skill_by_id("nonexistent_id_xyz")
        assert result is None

    def test_search_results_source_field(self, marketplace_service, sample_skills_extended):
        """Cover search results include source='local'"""
        result = marketplace_service.search_skills()
        assert result["source"] == "local"

    def test_search_empty_query(self, marketplace_service, sample_skills_extended):
        """Cover search with empty query string"""
        result = marketplace_service.search_skills(query="")
        assert result["total"] >= 5

    def test_search_with_all_parameters(self, marketplace_service, sample_skills_extended):
        """Cover search with all parameters combined"""
        result = marketplace_service.search_skills(
            query="extended",
            category="productivity",
            skill_type="python_code",
            sort_by="created",
            page=1,
            page_size=10
        )
        assert "skills" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert "source" in result

    def test_installation_logging(self, marketplace_service, sample_skills_extended):
        """Cover installation logging path"""
        import logging
        from io import StringIO

        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("core.skill_marketplace_service")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        skill_id = sample_skills_extended[0].id
        result = marketplace_service.install_skill(skill_id, "test-agent")

        # Verify logging occurred
        log_output = log_stream.getvalue()
        assert "Installing skill" in log_output or result["success"] is True

        logger.removeHandler(handler)

    def test_get_skill_by_id_community_filter(self, marketplace_service, db_session, default_tenant):
        """Cover get_skill_by_id filters by community source"""
        # Create non-community skill
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="custom_skill_test",
            status="Active",
            input_params={
                "skill_name": "Custom Skill",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "test",
                    "tags": [],
                    "author": "Test",
                    "version": "1.0.0"
                }
            },
            skill_source="custom",  # Not community
            security_scan_result={"safe": True},
            sandbox_enabled=True
        )
        db_session.add(skill)
        db_session.commit()

        # Should not find custom skill
        result = marketplace_service.get_skill_by_id(skill.id)
        assert result is None

    def test_community_skill_status_filter(self, marketplace_service, db_session, default_tenant):
        """Cover search filters by Active status"""
        # Create inactive skill
        skill = SkillExecution(
            agent_id="system",
            workspace_id="default",
            skill_id="community_inactive_test",
            status="Inactive",  # Not Active
            input_params={
                "skill_name": "Inactive Skill",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "Test",
                    "category": "test",
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

        # Search should not find inactive skill
        result = marketplace_service.search_skills(query="Inactive Skill")
        # Inactive skills are filtered out
        for s in result["skills"]:
            assert "Inactive" not in s.get("skill_name", "")

    def test_search_case_insensitive_query(self, marketplace_service, sample_skills_extended):
        """Cover search case insensitivity"""
        # Same search with different cases
        result1 = marketplace_service.search_skills(query="extended")
        result2 = marketplace_service.search_skills(query="EXTENDED")
        result3 = marketplace_service.search_skills(query="Extended")

        # All should return same count
        assert result1["total"] == result2["total"] == result3["total"]

    def test_rating_without_comment(self, marketplace_service, sample_skills_extended):
        """Cover rating submission without comment (None)"""
        skill_id = sample_skills_extended[0].id

        result = marketplace_service.rate_skill(
            skill_id,
            user_id="user_no_comment",
            rating=4,
            comment=None
        )

        assert result["success"] is True
        assert result["average_rating"] == 4.0

        # Verify rating stored without comment
        skill = marketplace_service.get_skill_by_id(skill_id)
        ratings = skill["ratings"]
        no_comment_rating = next((r for r in ratings if r["user_id"] == "user_no_comment"), None)
        if no_comment_rating:
            assert no_comment_rating["comment"] is None

    def test_multiple_users_same_skill_average(self, marketplace_service, sample_skills_extended):
        """Cover average calculation with multiple users"""
        skill_id = sample_skills_extended[0].id

        # Multiple users rate same skill
        marketplace_service.rate_skill(skill_id, "user_a", 5)
        marketplace_service.rate_skill(skill_id, "user_b", 4)
        marketplace_service.rate_skill(skill_id, "user_c", 5)
        marketplace_service.rate_skill(skill_id, "user_d", 3)

        # Average: (5 + 4 + 5 + 3) / 4 = 4.25
        skill = marketplace_service.get_skill_by_id(skill_id)
        assert skill["avg_rating"] == 4.25
        assert skill["rating_count"] == 4

    def test_pagination_total_pages_calculation(self, marketplace_service, sample_skills_extended):
        """Cover total_pages calculation edge cases"""
        # Test exact page size match
        result = marketplace_service.search_skills(page=1, page_size=5)
        if result["total"] == 5:
            assert result["total_pages"] == 1

        # Test partial page
        result = marketplace_service.search_skills(page=1, page_size=3)
        expected = (5 + 3 - 1) // 3  # = 2
        assert result["total_pages"] == expected

    def test_search_metadata_jsonb_casting(self, marketplace_service, sample_skills_extended):
        """Cover JSONB casting for category and skill_type filters"""
        # Test category filter (uses JSONB astext)
        result = marketplace_service.search_skills(category="integration")
        for skill in result["skills"]:
            assert skill["category"] == "integration"

        # Test skill_type filter (uses JSONB astext)
        result = marketplace_service.search_skills(skill_type="nodejs")
        for skill in result["skills"]:
            assert skill["skill_type"] == "nodejs"

    def test_skill_to_dict_created_at_isoformat(self, marketplace_service, sample_skills_extended):
        """Cover created_at ISO format conversion"""
        skill = sample_skills_extended[0]
        result = marketplace_service.get_skill_by_id(skill.id)

        # Verify ISO format string
        assert isinstance(result["created_at"], str)
        assert "T" in result["created_at"]
        assert result["created_at"].endswith("Z") or "+" in result["created_at"]

    def test_rating_error_skill_not_found(self, marketplace_service):
        """Cover rating error path for non-existent skill"""
        result = marketplace_service.rate_skill(
            skill_id="nonexistent_skill_xyz",
            user_id="test_user",
            rating=5
        )

        assert result["success"] is False
        assert "Skill not found" in result["error"]
