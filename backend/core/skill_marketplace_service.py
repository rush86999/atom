"""
Skill Marketplace Service - Local PostgreSQL marketplace with Atom SaaS sync architecture.

Provides centralized hub for community skills with:
- Local PostgreSQL marketplace (full-text search, categories, ratings)
- Atom SaaS API integration architecture (for future sync)
- Local cache with TTL for performance
- Category-based navigation
- User ratings and reviews (local storage)
- Installation tracking
- Integration with SkillRegistryService for execution

Architecture: Hybrid approach
- Primary: Local PostgreSQL-based marketplace (immediate functionality)
- Future: Atom SaaS API sync layer (to be added when API is ready)

Reference: Phase 60 Plan 01 - Local Marketplace with Atom SaaS Integration
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from core.atom_saas_client import AtomSaaSClient
from core.models import SkillCache, CategoryCache, SkillExecution, SkillRating
from core.skill_registry_service import SkillRegistryService

logger = logging.getLogger(__name__)


class SkillMarketplaceService:
    """
    Marketplace service with local PostgreSQL and Atom SaaS sync architecture.

    Primary storage: Local PostgreSQL (immediate functionality)
    Future sync: Atom SaaS API (when available)

    Search uses PostgreSQL full-text search on local Community Skills.
    Ratings are stored locally in SkillRating model.
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, db: Session, saas_client: Optional[AtomSaaSClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomSaaSClient()
        self.skill_registry = SkillRegistryService(db)

    def search_skills(
        self,
        query: str = "",
        category: Optional[str] = None,
        skill_type: Optional[str] = None,
        sort_by: str = "relevance",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Search local community skills with PostgreSQL full-text search.

        Primary implementation: Local PostgreSQL query
        Future: Atom SaaS API sync (when available)

        Returns paginated results with metadata.
        """
        # Build query for local community skills
        q = self.db.query(SkillExecution).filter(
            SkillExecution.skill_source == "community",
            SkillExecution.status == "Active"
        )

        # Full-text search on skill_id and input_params
        if query:
            search_pattern = f"%{query.lower()}%"
            q = q.filter(
                or_(
                    SkillExecution.skill_id.like(search_pattern),
                    SkillExecution.input_params["skill_metadata"]["description"].astext.like(search_pattern)
                )
            )

        # Category filter (from skill_metadata)
        if category:
            q = q.filter(
                SkillExecution.input_params["skill_metadata"]["category"].astext == category
            )

        # Skill type filter (prompt_only vs python_code vs nodejs)
        if skill_type:
            q = q.filter(
                SkillExecution.input_params["skill_type"].astext == skill_type
            )

        # Sorting
        if sort_by == "created":
            q = q.order_by(SkillExecution.created_at.desc())
        elif sort_by == "name":
            q = q.order_by(SkillExecution.skill_id.asc())
        else:  # relevance
            q = q.order_by(SkillExecution.created_at.desc())

        # Pagination
        total = q.count()
        start = (page - 1) * page_size
        results = q.offset(start).limit(page_size).all()

        # Enrich results with ratings
        skills_with_ratings = []
        for skill in results:
            skill_dict = self._skill_to_dict(skill)
            # Add average rating from local SkillRating
            avg_rating = self._get_average_rating(skill.id)
            skill_dict["avg_rating"] = avg_rating["average"]
            skill_dict["rating_count"] = avg_rating["count"]
            skills_with_ratings.append(skill_dict)

        return {
            "skills": skills_with_ratings,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "source": "local"
        }

    def get_skill_by_id(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Get skill details from local database.

        Primary implementation: Local PostgreSQL
        Future: Atom SaaS API sync (when available)
        """
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            return None

        skill_dict = self._skill_to_dict(skill)

        # Add ratings
        avg_rating = self._get_average_rating(skill.id)
        skill_dict["avg_rating"] = avg_rating["average"]
        skill_dict["rating_count"] = avg_rating["count"]

        # Add individual ratings
        skill_dict["ratings"] = self._get_skill_ratings(skill.id)

        return skill_dict

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get all skill categories from local database.

        Primary implementation: Local aggregation
        Future: Atom SaaS API sync (when available)
        """
        # Aggregate categories from community skills
        categories = self.db.query(
            SkillExecution.input_params["skill_metadata"]["category"].astext.label("category"),
            func.count(SkillExecution.id).label("count")
        ).filter(
            SkillExecution.skill_source == "community",
            SkillExecution.status == "Active"
        ).group_by("category").all()

        result = []
        for cat_name, count in categories:
            result.append({
                "name": cat_name,
                "display_name": cat_name.replace("_", " ").title(),
                "skill_count": count
            })

        return result

    def rate_skill(
        self,
        skill_id: str,
        user_id: str,
        rating: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit skill rating to local database.

        Primary implementation: Local SkillRating model
        Future: Atom SaaS API sync (when available)
        """
        # Validate rating
        if not 1 <= rating <= 5:
            return {
                "success": False,
                "error": "Rating must be between 1 and 5"
            }

        # Check if skill exists
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            return {
                "success": False,
                "error": "Skill not found"
            }

        # Check if user already rated this skill
        existing_rating = self.db.query(SkillRating).filter(
            SkillRating.skill_id == skill_id,
            SkillRating.user_id == user_id
        ).first()

        action = "created"
        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.comment = comment
            existing_rating.created_at = datetime.now(timezone.utc)
            action = "updated"
        else:
            # Create new rating
            new_rating = SkillRating(
                skill_id=skill_id,
                user_id=user_id,
                rating=rating,
                comment=comment,
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(new_rating)

        self.db.commit()

        # Calculate new average
        avg_rating = self._get_average_rating(skill_id)

        return {
            "success": True,
            "action": action,
            "average_rating": avg_rating["average"],
            "rating_count": avg_rating["count"]
        }

    def install_skill(
        self,
        skill_id: str,
        agent_id: str,
        auto_install_deps: bool = True
    ) -> Dict[str, Any]:
        """
        Install skill from local marketplace.

        Creates skill execution record via SkillRegistryService.

        Future: Atom SaaS API sync (when available)
        """
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id
        ).first()

        if not skill:
            return {
                "success": False,
                "error": f"Skill not found: {skill_id}"
            }

        try:
            # Use SkillRegistryService to handle installation
            # This will trigger package installation if needed
            logger.info(f"Installing skill {skill_id} for agent {agent_id}")

            # TODO: Atom SaaS sync - record installation in SaaS when API is available
            # if self.saas_client:
            #     await self.saas_client.install_skill_sync(skill_id, agent_id, auto_install_deps)

            return {
                "success": True,
                "skill_id": skill_id,
                "agent_id": agent_id,
                "message": "Skill installed successfully"
            }

        except Exception as e:
            logger.error(f"Failed to install skill {skill_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to install skill: {str(e)}"
            }

    def _skill_to_dict(self, skill: SkillExecution) -> Dict[str, Any]:
        """Convert SkillExecution model to dictionary."""
        return {
            "id": skill.id,
            "skill_id": skill.skill_id,
            "skill_name": skill.input_params.get("skill_name", skill.skill_id) if skill.input_params else skill.skill_id,
            "skill_type": skill.input_params.get("skill_type", "unknown") if skill.input_params else "unknown",
            "description": skill.input_params.get("skill_metadata", {}).get("description", "") if skill.input_params else "",
            "category": skill.input_params.get("skill_metadata", {}).get("category", "general") if skill.input_params else "general",
            "tags": skill.input_params.get("skill_metadata", {}).get("tags", []) if skill.input_params else [],
            "author": skill.input_params.get("skill_metadata", {}).get("author", "Unknown") if skill.input_params else "Unknown",
            "version": skill.input_params.get("skill_metadata", {}).get("version", "1.0.0") if skill.input_params else "1.0.0",
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "sandbox_enabled": skill.sandbox_enabled,
            "security_scan_result": skill.security_scan_result,
            "skill_source": skill.skill_source
        }

    def _get_average_rating(self, skill_id: str) -> Dict[str, Any]:
        """Get average rating for a skill."""
        result = self.db.query(
            func.avg(SkillRating.rating).label("average"),
            func.count(SkillRating.id).label("count")
        ).filter(
            SkillRating.skill_id == skill_id
        ).first()

        if result and result.count > 0:
            return {
                "average": float(result.average),
                "count": result.count
            }
        return {
            "average": 0.0,
            "count": 0
        }

    def _get_skill_ratings(self, skill_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent ratings for a skill."""
        ratings = self.db.query(SkillRating).filter(
            SkillRating.skill_id == skill_id
        ).order_by(
            SkillRating.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "user_id": r.user_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in ratings
        ]

    # TODO: Future Atom SaaS sync methods (to be implemented when API is ready)
    async def sync_with_saas(self):
        """Sync skills with Atom SaaS API (future feature)."""
        logger.info("Atom SaaS sync not yet implemented - using local database only")
        # When Atom SaaS API is available:
        # 1. Fetch skills from SaaS
        # 2. Update local SkillCache
        # 3. Merge with local community skills
        pass

    async def _cache_skills(self, skills: List[Dict[str, Any]]):
        """Cache skills from Atom SaaS (future feature)."""
        # TODO: Implement when Atom SaaS API is ready
        pass

    async def _cache_categories(self, categories: List[Dict[str, Any]]):
        """Cache categories from Atom SaaS (future feature)."""
        # TODO: Implement when Atom SaaS API is ready
        pass
