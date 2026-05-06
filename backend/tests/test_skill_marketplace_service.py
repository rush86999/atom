"""
Comprehensive test suite for Skill Marketplace Service

Tests marketplace search, skill installation, ratings management,
local fallback, category management, and Atom Agent OS integration.
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

sys.path.append(os.getcwd())

from core.database import Base
from core.models import SkillExecution, SkillRating
from core.skill_marketplace_service import SkillMarketplaceService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestSkillMarketplaceService(unittest.TestCase):
    """Test suite for SkillMarketplaceService"""

    def setUp(self):
        """Setup test database and service"""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Mock SaaS client
        self.mock_saas_client = Mock()
        self.mock_saas_client.fetch_skills_sync.return_value = {
            "skills": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }
        self.mock_saas_client.get_skill_by_id_sync.return_value = None
        self.mock_saas_client.get_categories_sync.return_value = []

        self.service = SkillMarketplaceService(
            db=self.db,
            saas_client=self.mock_saas_client
        )

    def tearDown(self):
        """Cleanup database"""
        self.db.close()
        self.engine.dispose()

    # =========================================================================
    # Search Skills Tests
    # =========================================================================

    def test_search_skills_uses_marketplace_first(self):
        """Test search tries Atom Agent OS marketplace first"""
        self.mock_saas_client.fetch_skills_sync.return_value = {
            "skills": [
                {
                    "id": "skill-1",
                    "name": "Test Skill",
                    "description": "A test skill"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "source": "atom_agent_os"
        }

        result = self.service.search_skills(query="test")

        self.assertEqual(result["source"], "atom_agent_os")
        self.assertEqual(len(result["skills"]), 1)
        self.mock_saas_client.fetch_skills_sync.assert_called_once()

    def test_search_skills_fallback_to_local(self):
        """Test search falls back to local on marketplace failure"""
        # Create local skill
        skill = SkillExecution(
            id=str(uuid4()),
            skill_id="local-skill-1",
            skill_source="community",
            status="Active",
            input_params={
                "skill_name": "Local Skill",
                "skill_type": "python_code",
                "skill_metadata": {
                    "description": "A local skill",
                    "category": "automation",
                    "author": "Test Author",
                    "version": "1.0.0",
                    "tags": ["automation", "python"]
                }
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)
        self.db.commit()

        # Mock marketplace failure
        self.mock_saas_client.fetch_skills_sync.side_effect = Exception("Marketplace unavailable")

        result = self.service.search_skills(query="local")

        self.assertEqual(result["source"], "local")
        self.assertGreaterEqual(len(result["skills"]), 1)

    def test_search_skills_with_category_filter(self):
        """Test search with category filter"""
        self.mock_saas_client.fetch_skills_sync.return_value = {
            "skills": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "source": "atom_agent_os"
        }

        result = self.service.search_skills(category="automation")

        # Verify marketplace was called with category
        call_args = self.mock_saas_client.fetch_skills_sync.call_args
        self.assertEqual(call_args[1]["category"], "automation")

    def test_search_skills_with_skill_type_filter(self):
        """Test search with skill type filter"""
        self.mock_saas_client.fetch_skills_sync.return_value = {
            "skills": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "source": "atom_agent_os"
        }

        result = self.service.search_skills(skill_type="python_code")

        # Verify marketplace was called with skill_type
        call_args = self.mock_saas_client.fetch_skills_sync.call_args
        self.assertEqual(call_args[1]["skill_type"], "python_code")

    def test_search_skills_pagination(self):
        """Test search with pagination"""
        self.mock_saas_client.fetch_skills_sync.return_value = {
            "skills": [],
            "total": 0,
            "page": 2,
            "page_size": 50,
            "source": "atom_agent_os"
        }

        result = self.service.search_skills(page=2, page_size=50)

        self.assertEqual(result["page"], 2)
        self.assertEqual(result["page_size"], 50)

    # =========================================================================
    # Get Skill By ID Tests
    # =========================================================================

    def test_get_skill_by_id_from_marketplace(self):
        """Test get_skill_by_id tries marketplace first"""
        self.mock_saas_client.get_skill_by_id_sync.return_value = {
            "id": "skill-1",
            "name": "Test Skill",
            "description": "Test description"
        }

        result = self.service.get_skill_by_id("skill-1")

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "skill-1")
        self.mock_saas_client.get_skill_by_id_sync.assert_called_once_with("skill-1")

    def test_get_skill_by_id_fallback_to_local(self):
        """Test get_skill_by_id falls back to local"""
        # Create local skill
        skill_id = str(uuid4())
        skill = SkillExecution(
            id=skill_id,
            skill_id="local-skill-1",
            skill_source="community",
            status="Active",
            input_params={
                "skill_name": "Local Skill",
                "skill_type": "prompt_only",
                "skill_metadata": {
                    "description": "A local skill",
                    "category": "automation",
                    "author": "Test Author",
                    "version": "1.0.0"
                }
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)
        self.db.commit()

        # Mock marketplace failure
        self.mock_saas_client.get_skill_by_id_sync.side_effect = Exception("Not found")

        result = self.service.get_skill_by_id(skill_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "local")
        self.assertEqual(result["id"], skill_id)

    def test_get_skill_by_id_not_found(self):
        """Test get_skill_by_id returns None when not found"""
        self.mock_saas_client.get_skill_by_id_sync.return_value = None

        result = self.service.get_skill_by_id("nonexistent")

        self.assertIsNone(result)

    # =========================================================================
    # Categories Tests
    # =========================================================================

    def test_get_categories_from_marketplace(self):
        """Test get_categories tries marketplace first"""
        self.mock_saas_client.get_categories_sync.return_value = [
            {"name": "automation", "display_name": "Automation", "skill_count": 10},
            {"name": "integration", "display_name": "Integration", "skill_count": 5}
        ]

        result = self.service.get_categories()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "automation")
        self.mock_saas_client.get_categories_sync.assert_called_once()

    def test_get_categories_fallback_to_local(self):
        """Test get_categories falls back to local aggregation"""
        # Create local skills with different categories
        for i in range(3):
            skill = SkillExecution(
                id=str(uuid4()),
                skill_id=f"skill-{i}",
                skill_source="community",
                status="Active",
                input_params={
                    "skill_name": f"Skill {i}",
                    "skill_type": "python_code",
                    "skill_metadata": {
                        "category": "automation",
                        "description": "Test"
                    }
                },
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(skill)
        self.db.commit()

        # Mock marketplace failure
        self.mock_saas_client.get_categories_sync.side_effect = Exception("Unavailable")

        result = self.service.get_categories()

        self.assertGreaterEqual(len(result), 1)
        # Check that local aggregation worked
        automation_cats = [c for c in result if c["name"] == "automation"]
        self.assertGreater(len(automation_cats), 0)

    # =========================================================================
    # Rate Skill Tests
    # =========================================================================

    def test_rate_skill_success(self):
        """Test successful skill rating"""
        # Create skill
        skill = SkillExecution(
            id=str(uuid4()),
            skill_id="skill-1",
            skill_source="community",
            status="Active",
            input_params={
                "skill_name": "Test Skill",
                "skill_type": "python_code",
                "skill_metadata": {"description": "Test"}
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)
        self.db.commit()

        # Mock marketplace response
        self.mock_saas_client.rate_skill_sync.return_value = {
            "success": True,
            "average_rating": 4.5,
            "rating_count": 10
        }

        result = self.service.rate_skill(
            skill_id="skill-1",
            user_id="user-1",
            rating=5,
            comment="Great skill!"
        )

        self.assertTrue(result["success"])

        # Verify local rating was created
        local_rating = self.db.query(SkillRating).filter_by(
            skill_id="skill-1",
            user_id="user-1"
        ).first()

        self.assertIsNotNone(local_rating)
        self.assertEqual(local_rating.rating, 5)

    def test_rate_skill_invalid_rating(self):
        """Test rate_skill validates rating range"""
        result = self.service.rate_skill(
            skill_id="skill-1",
            user_id="user-1",
            rating=6  # Invalid - must be 1-5
        )

        self.assertFalse(result["success"])
        self.assertIn("between 1 and 5", result["error"])

    def test_rate_skill_update_existing(self):
        """Test updating existing rating"""
        # Create skill and existing rating
        skill = SkillExecution(
            id=str(uuid4()),
            skill_id="skill-1",
            skill_source="community",
            status="Active",
            input_params={
                "skill_name": "Test Skill",
                "skill_type": "python_code",
                "skill_metadata": {"description": "Test"}
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)

        existing_rating = SkillRating(
            skill_id="skill-1",
            user_id="user-1",
            rating=3,
            comment="Okay",
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(existing_rating)
        self.db.commit()

        # Mock marketplace failure
        self.mock_saas_client.rate_skill_sync.side_effect = Exception("Unavailable")

        # Update rating
        result = self.service.rate_skill(
            skill_id="skill-1",
            user_id="user-1",
            rating=5,
            comment="Much better now!"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "updated")

        # Verify rating was updated
        local_rating = self.db.query(SkillRating).filter_by(
            skill_id="skill-1",
            user_id="user-1"
        ).first()

        self.assertEqual(local_rating.rating, 5)
        self.assertEqual(local_rating.comment, "Much better now!")

    # =========================================================================
    # Install Skill Tests
    # =========================================================================

    def test_install_skill_success(self):
        """Test successful skill installation"""
        # Create skill
        skill_id = str(uuid4())
        skill = SkillExecution(
            id=skill_id,
            skill_id="skill-1",
            skill_source="community",
            status="Active",
            input_params={
                "skill_name": "Test Skill",
                "skill_type": "python_code",
                "skill_metadata": {"description": "Test"}
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)
        self.db.commit()

        result = self.service.install_skill(
            skill_id=skill_id,
            agent_id="agent-1",
            auto_install_deps=True
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["skill_id"], skill_id)
        self.assertEqual(result["agent_id"], "agent-1")

    def test_install_skill_not_found(self):
        """Test install_skill fails when skill not found"""
        result = self.service.install_skill(
            skill_id="nonexistent",
            agent_id="agent-1"
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    # =========================================================================
    # Uninstall Skill Tests
    # =========================================================================

    def test_uninstall_skill_success(self):
        """Test successful skill uninstallation"""
        # Create skill with install_count
        skill_id = str(uuid4())
        skill = SkillExecution(
            id=skill_id,
            skill_id="skill-1",
            skill_source="community",
            status="Active",
            install_count=5,
            input_params={
                "skill_name": "Test Skill",
                "skill_type": "python_code",
                "skill_metadata": {"description": "Test"}
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(skill)
        self.db.commit()

        result = self.service.uninstall_skill(
            skill_id=skill_id,
            agent_id="agent-1"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["skill_id"], skill_id)

        # Verify install_count was decremented
        self.db.refresh(skill)
        self.assertEqual(skill.install_count, 4)

    def test_uninstall_skill_not_found(self):
        """Test uninstall_skill fails when skill not found"""
        result = self.service.uninstall_skill(
            skill_id="nonexistent",
            agent_id="agent-1"
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    # =========================================================================
    # Helper Methods Tests
    # =========================================================================

    def test_skill_to_dict_conversion(self):
        """Test _skill_to_dict converts skill to dictionary"""
        skill = SkillExecution(
            id=str(uuid4()),
            skill_id="test-skill",
            skill_source="community",
            status="Active",
            sandbox_enabled=True,
            security_scan_result={"vulnerabilities": []},
            input_params={
                "skill_name": "Test Skill",
                "skill_type": "python_code",
                "skill_metadata": {
                    "description": "A test skill",
                    "category": "automation",
                    "author": "Test Author",
                    "version": "2.0.0",
                    "tags": ["test", "automation"]
                }
            },
            created_at=datetime.now(timezone.utc)
        )

        result = self.service._skill_to_dict(skill)

        self.assertEqual(result["skill_id"], "test-skill")
        self.assertEqual(result["skill_name"], "Test Skill")
        self.assertEqual(result["skill_type"], "python_code")
        self.assertEqual(result["description"], "A test skill")
        self.assertEqual(result["category"], "automation")
        self.assertEqual(result["author"], "Test Author")
        self.assertEqual(result["version"], "2.0.0")
        self.assertEqual(result["tags"], ["test", "automation"])
        self.assertTrue(result["sandbox_enabled"])
        self.assertEqual(result["skill_source"], "community")

    def test_get_average_rating(self):
        """Test _get_average_rating calculates correctly"""
        skill_id = str(uuid4())

        # Add multiple ratings
        for rating in [5, 4, 3, 5, 4]:
            skill_rating = SkillRating(
                skill_id=skill_id,
                user_id=f"user-{rating}",
                rating=rating
            )
            self.db.add(skill_rating)

        self.db.commit()

        result = self.service._get_average_rating(skill_id)

        self.assertEqual(result["average"], 4.2)  # (5+4+3+5+4) / 5
        self.assertEqual(result["count"], 5)

    def test_get_average_rating_no_ratings(self):
        """Test _get_average_rating with no ratings"""
        result = self.service._get_average_rating("nonexistent")

        self.assertEqual(result["average"], 0.0)
        self.assertEqual(result["count"], 0)

    def test_get_skill_ratings(self):
        """Test _get_skill_ratings returns recent ratings"""
        skill_id = str(uuid4())

        # Add ratings
        for i in range(5):
            skill_rating = SkillRating(
                skill_id=skill_id,
                user_id=f"user-{i}",
                rating=i + 1,
                comment=f"Comment {i}",
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(skill_rating)

        self.db.commit()

        result = self.service._get_skill_ratings(skill_id, limit=3)

        self.assertEqual(len(result), 3)  # Limited to 3

        # Verify they're in descending order by created_at
        # (most recent first, which should be the last ones added)


if __name__ == "__main__":
    unittest.main()
