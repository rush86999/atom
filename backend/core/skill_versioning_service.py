"""
Skill Versioning Service

Manages skill versioning, rollback, and version history.
Enables semver support and version comparison.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from core.models import Skill, SkillVersion

logger = logging.getLogger(__name__)


class SkillVersioningService:
    """
    Service for managing skill versions.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_version(
        self,
        skill_id: str,
        changelog: str,
        tenant_id: str,
        is_stable: bool = False
    ) -> SkillVersion:
        """
        Create a new version snapshot of a skill.

        Args:
            skill_id: Skill ID to version
            changelog: Version notes
            tenant_id: Tenant ID
            is_stable: Whether this is a stable release

        Returns:
            New SkillVersion
        """
        # Get current skill
        skill = self.db.query(Skill).filter(
            and_(
                Skill.id == skill_id,
                Skill.tenant_id == tenant_id
            )
        ).first()

        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        # Determine next version (bump patch)
        current_version = skill.version
        next_version = self._bump_version(current_version, "patch")

        # Create version snapshot
        version = SkillVersion(
            skill_id=skill_id,
            tenant_id=tenant_id,
            version=next_version,
            changelog=changelog,
            name=skill.name,
            description=skill.description,
            type=skill.type,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema,
            config=skill.config,
            code=skill.code,
            dependencies=skill.dependencies,
            is_stable=is_stable
        )

        self.db.add(version)

        # Update skill version
        skill.version = next_version

        self.db.commit()
        self.db.refresh(version)

        logger.info(f"Created version {next_version} for skill {skill_id}")

        return version

    def _bump_version(self, version: str, bump_type: str = "patch") -> str:
        """
        Bump semver version.

        Args:
            version: Current version (e.g., "1.2.3")
            bump_type: "major", "minor", or "patch"

        Returns:
            New version string
        """
        try:
            parts = version.split(".")
            if len(parts) != 3:
                return version

            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

            if bump_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif bump_type == "minor":
                minor += 1
                patch = 0
            else:  # patch
                patch += 1

            return f"{major}.{minor}.{patch}"
        except (ValueError, IndexError):
            return version

    def rollback_to_version(
        self,
        skill_id: str,
        version_id: str,
        tenant_id: str
    ) -> Skill:
        """
        Rollback a skill to a previous version.

        Args:
            skill_id: Skill ID to rollback
            version_id: Target version ID
            tenant_id: Tenant ID

        Returns:
            Updated skill
        """
        # Get version to rollback to
        target_version = self.db.query(SkillVersion).filter(
            and_(
                SkillVersion.id == version_id,
                SkillVersion.skill_id == skill_id
            )
        ).first()

        if not target_version:
            raise ValueError("Target version not found")

        # Get current skill
        skill = self.db.query(Skill).filter(
            and_(
                Skill.id == skill_id,
                Skill.tenant_id == tenant_id
            )
        ).first()

        if not skill:
            raise ValueError("Skill not found")

        # Create version snapshot of current state before rollback
        current_version = SkillVersion(
            skill_id=skill_id,
            tenant_id=tenant_id,
            version=skill.version + "-pre-rollback",
            changelog=f"Pre-rollback snapshot of {skill.version}",
            name=skill.name,
            description=skill.description,
            type=skill.type,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema,
            config=skill.config,
            code=skill.code,
            dependencies=skill.dependencies,
            is_stable=False
        )

        self.db.add(current_version)

        # Rollback skill fields
        skill.name = target_version.name
        skill.description = target_version.description
        skill.version = target_version.version
        skill.type = target_version.type
        skill.input_schema = target_version.input_schema
        skill.output_schema = target_version.output_schema
        skill.config = target_version.config
        skill.code = target_version.code
        skill.dependencies = target_version.dependencies

        self.db.commit()

        logger.info(f"Rolled back skill {skill_id} to version {target_version.version}")

        return skill

    def get_version_history(
        self,
        skill_id: str,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a skill.

        Args:
            skill_id: Skill ID
            tenant_id: Tenant ID

        Returns:
            List of versions
        """
        versions = self.db.query(SkillVersion).filter(
            SkillVersion.skill_id == skill_id
        ).order_by(SkillVersion.created_at.desc()).all()

        return [
            {
                "id": v.id,
                "version": v.version,
                "changelog": v.changelog,
                "is_stable": v.is_stable,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]

    def compare_versions(
        self,
        skill_id: str,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """
        Compare two versions of a skill.

        Args:
            skill_id: Skill ID
            version_id_1: First version ID
            version_id_2: Second version ID

        Returns:
            Comparison result
        """
        v1 = self.db.query(SkillVersion).filter(SkillVersion.id == version_id_1).first()
        v2 = self.db.query(SkillVersion).filter(SkillVersion.id == version_id_2).first()

        if not v1 or not v2:
            raise ValueError("One or both versions not found")

        # Compare versions
        comparison = self._compare_versions(v1.version, v2.version)

        # Compare fields
        differences = []

        if v1.name != v2.name:
            differences.append({"field": "name", "v1": v1.name, "v2": v2.name})

        if v1.description != v2.description:
            differences.append({"field": "description", "v1": v1.description, "v2": v2.description})

        if v1.type != v2.type:
            differences.append({"field": "type", "v1": v1.type, "v2": v2.type})

        if v1.config != v2.config:
            differences.append({"field": "config", "changed": True})

        if v1.input_schema != v2.input_schema:
            differences.append({"field": "input_schema", "changed": True})

        if v1.code != v2.code:
            differences.append({"field": "code", "changed": True})

        return {
            "comparison": comparison,  # "v1_older", "v1_newer", "equal"
            "version_1": {
                "id": v1.id,
                "version": v1.version,
                "created_at": v1.created_at.isoformat()
            },
            "version_2": {
                "id": v2.id,
                "version": v2.version,
                "created_at": v2.created_at.isoformat()
            },
            "differences": differences
        }

    def _compare_versions(self, version1: str, version2: str) -> str:
        """
        Compare two semver versions.

        Returns:
            "v1_older", "v1_newer", or "equal"
        """
        try:
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]

            if v1_parts < v2_parts:
                return "v1_older"
            elif v1_parts > v2_parts:
                return "v1_newer"
            else:
                return "equal"
        except (ValueError, IndexError):
            return "equal"

    def get_latest_version(
        self,
        skill_id: str
    ) -> Optional[SkillVersion]:
        """
        Get the latest stable version of a skill.

        Args:
            skill_id: Skill ID

        Returns:
            Latest SkillVersion or None
        """
        return self.db.query(SkillVersion).filter(
            and_(
                SkillVersion.skill_id == skill_id,
                SkillVersion.is_stable == True
            )
        ).order_by(SkillVersion.created_at.desc()).first()
