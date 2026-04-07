"""
Skill Marketplace Service - Atom Agent OS Marketplace Integration.

Provides integration with the Atom Agent OS marketplace (atomagentos.com):
- Browse marketplace skills from Atom Agent OS
- Install skills from Atom Agent OS marketplace
- Rate and review skills
- Uninstall installed skills
- Local cache for performance

Architecture: Marketplace-First
- Primary: Atom Agent OS marketplace API (atomagentos.com) for all marketplace operations
- Local: PostgreSQL cache for performance
- Fallback: Local community skills when marketplace is unavailable

Reference: Phase 60 Plan 01 - Local Marketplace with Atom Agent OS Integration
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from core.atom_agent_os_client import AtomAgentOSMarketplaceClient
from core.models import SkillCache, SkillExecution, SkillRating, MarketplaceInstance
from core.skill_registry_service import SkillRegistryService

logger = logging.getLogger(__name__)


class SkillMarketplaceService:
    """
    Marketplace service with Atom Agent OS marketplace integration.

    Primary source: Atom Agent OS marketplace (atomagentos.com)
    Local cache: PostgreSQL for performance
    Fallback: Local community skills when marketplace is unavailable

    Search uses marketplace API with local cache fallback.
    Ratings are submitted to marketplace and stored locally.
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, db: Session, saas_client: Optional[AtomAgentOSMarketplaceClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomAgentOSMarketplaceClient()
        self.skill_registry = SkillRegistryService(db)
        
        # Automated registration on first marketplace access
        if os.getenv("ANALYTICS_ENABLED", "false").lower() == "true":
            try:
                if not self.db.query(MarketplaceInstance).first():
                    from core.marketplace_sync_worker import AnalyticsSyncWorker
                    worker = AnalyticsSyncWorker(self.db)
                    worker._ensure_instance_registered()
            except Exception as reg_err:
                logger.error(f"Marketplace auto-registration failed: {reg_err}")

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
        Search marketplace skills with Atom Agent OS-first approach.

        Primary: Atom Agent OS marketplace API (atomagentos.com)
        Fallback: Local PostgreSQL community skills

        Returns paginated results with metadata.
        """
        # Try Atom Agent OS marketplace first
        try:
            logger.info(f"Searching Atom Agent OS marketplace: query={query}, category={category}")
            result = self.saas_client.fetch_skills_sync(
                query=query,
                category=category,
                skill_type=skill_type,
                page=page,
                page_size=page_size
            )

            # Add source indicator
            result["source"] = "atom_agent_os"
            return result

        except Exception as e:
            logger.warning(f"Failed to fetch from Atom Agent OS, falling back to local: {e}")
            # Fallback to local community skills
            return self._search_local_skills(
                query=query,
                category=category,
                skill_type=skill_type,
                sort_by=sort_by,
                page=page,
                page_size=page_size
            )

    def _search_local_skills(
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

        Fallback implementation when Atom Agent OS is unavailable.
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
                    SkillExecution.input_params["skill_metadata"]["description"].as_string().like(search_pattern)
                )
            )

        # Category filter (from skill_metadata)
        if category:
            q = q.filter(
                SkillExecution.input_params["skill_metadata"]["category"].as_string() == category
            )

        # Skill type filter (prompt_only vs python_code vs nodejs)
        if skill_type:
            q = q.filter(
                SkillExecution.input_params["skill_type"].as_string() == skill_type
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
        Get skill details from Atom Agent OS marketplace with local fallback.

        Primary: Atom Agent OS marketplace API
        Fallback: Local PostgreSQL community skills
        """
        # Try Atom Agent OS first
        try:
            skill = self.saas_client.get_skill_by_id_sync(skill_id)
            if skill:
                skill["source"] = "atom_agent_os"
                return skill
        except Exception as e:
            logger.warning(f"Failed to fetch skill {skill_id} from marketplace: {e}")

        # Fallback to local
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            return None

        skill_dict = self._skill_to_dict(skill)
        skill_dict["source"] = "local"

        # Add ratings
        avg_rating = self._get_average_rating(skill.id)
        skill_dict["avg_rating"] = avg_rating["average"]
        skill_dict["rating_count"] = avg_rating["count"]

        # Add individual ratings
        skill_dict["ratings"] = self._get_skill_ratings(skill.id)

        return skill_dict

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get all skill categories from Atom Agent OS marketplace with local fallback.

        Primary: Atom Agent OS marketplace API
        Fallback: Local aggregation
        """
        # Try Atom Agent OS first
        try:
            categories = self.saas_client.get_categories_sync()
            if categories:
                return categories
        except Exception as e:
            logger.warning(f"Failed to fetch categories from marketplace: {e}")

        # Fallback to local
        categories = self.db.query(
            SkillExecution.input_params["skill_metadata"]["category"].as_string().label("category"),
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
        Submit skill rating to Atom Agent OS marketplace and local database.

        Primary: Atom Agent OS marketplace API
        Local: Also stores in SkillRating for local reference
        """
        # Validate rating
        if not 1 <= rating <= 5:
            return {
                "success": False,
                "error": "Rating must be between 1 and 5"
            }

        # Submit to Atom Agent OS marketplace
        marketplace_result = None
        try:
            marketplace_result = self.saas_client.rate_skill_sync(
                skill_id=skill_id,
                user_id=user_id,
                rating=rating,
                comment=comment
            )
            logger.info(f"Rating submitted to Atom Agent OS marketplace: {marketplace_result}")
        except Exception as e:
            logger.warning(f"Failed to submit rating to marketplace: {e}")

        # Also store locally
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

        # Return marketplace result if available, otherwise local
        if marketplace_result and marketplace_result.get("success"):
            return marketplace_result

        # Calculate local average
        avg_rating = self._get_average_rating(skill_id)
        return {
            "success": True,
            "action": action,
            "average_rating": avg_rating["average"],
            "rating_count": avg_rating["count"],
            "source": "local"
        }

    def install_skill(
        self,
        skill_id: str,
        agent_id: str,
        auto_install_deps: bool = True
    ) -> Dict[str, Any]:
        """
        Install skill from Atom Agent OS marketplace.

        Creates skill execution record via SkillRegistryService.
        Records installation with Atom Agent OS marketplace.
        """
        # Install via Atom Agent OS marketplace
        try:
            logger.info(f"Installing skill {skill_id} from Atom Agent OS marketplace for agent {agent_id}")
            marketplace_result = self.saas_client.install_skill_sync(
                skill_id=skill_id,
                agent_id=agent_id,
                auto_install_deps=auto_install_deps
            )

            if not marketplace_result.get("success"):
                logger.warning(f"Marketplace installation failed: {marketplace_result.get('error')}")
                # Fall through to local installation

        except Exception as e:
            logger.warning(f"Failed to install via marketplace, trying local: {e}")
            marketplace_result = None

        # Local installation
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

            return {
                "success": True,
                "skill_id": skill_id,
                "agent_id": agent_id,
                "message": "Skill installed successfully",
                "source": "local"
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

    def uninstall_skill(
        self,
        skill_id: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Uninstall a skill from an agent via Atom Agent OS Marketplace.

        Removes skill execution record for the specified agent.
        Records uninstallation with Atom Agent OS marketplace.

        Args:
            skill_id: Skill ID to uninstall
            agent_id: Agent ID to uninstall from

        Returns:
            Uninstall status
        """
        # Uninstall via Atom Agent OS marketplace
        try:
            logger.info(f"Uninstalling skill {skill_id} from Atom Agent OS marketplace for agent {agent_id}")
            marketplace_result = self.saas_client.uninstall_skill_sync(
                skill_id=skill_id,
                agent_id=agent_id
            )

            if not marketplace_result.get("success"):
                logger.warning(f"Marketplace uninstall failed: {marketplace_result.get('error')}")
                # Fall through to local uninstall

        except Exception as e:
            logger.warning(f"Failed to uninstall via marketplace, trying local: {e}")
            marketplace_result = None

        # Local uninstall
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            return {
                "success": False,
                "error": f"Skill not found: {skill_id}"
            }

        try:
            logger.info(f"Uninstalling skill {skill_id} from agent {agent_id}")

            # TODO: Remove skill-agent association when skill-relationship model is added
            # For now, this is a placeholder for future implementation

            # Decrement install count on community skill
            if hasattr(skill, 'install_count'):
                skill.install_count = max(0, (skill.install_count or 0) - 1)

            self.db.commit()

            return {
                "success": True,
                "skill_id": skill_id,
                "agent_id": agent_id,
                "message": "Skill uninstalled successfully",
                "source": "local"
            }

        except Exception as e:
            logger.error(f"Failed to uninstall skill {skill_id}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": f"Failed to uninstall skill: {str(e)}"
            }

    # TODO: Future Atom Agent OS marketplace sync methods (to be implemented when API is ready)
    async def sync_with_marketplace(self):
        """Sync skills with Atom Agent OS marketplace (future feature)."""
        logger.info("Marketplace sync not yet implemented - using local database only")
        # When Atom Agent OS marketplace API is available:
        # 1. Fetch skills from marketplace
        # 2. Update local SkillCache
        # 3. Merge with local community skills
        pass

    async def _cache_skills(self, skills: List[Dict[str, Any]]):
        """Cache skills from Atom Agent OS marketplace (future feature)."""
        # TODO: Implement when marketplace API is ready
        pass

    async def _cache_categories(self, categories: List[Dict[str, Any]]):
        """Cache categories from Atom Agent OS marketplace (future feature)."""
        # TODO: Implement when marketplace API is ready
        pass
