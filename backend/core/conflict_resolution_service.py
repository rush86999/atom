"""
Conflict Resolution Service for Atom SaaS Skill Sync

Detects and resolves conflicts when skills exist both locally (Community Skills)
and remotely (Atom SaaS) with different metadata/versions.

Phase 61 Plan 04 - Conflict Resolution
"""
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import ConflictLog

logger = logging.getLogger(__name__)

# Conflict types
ConflictType = Literal["VERSION_MISMATCH", "CONTENT_MISMATCH", "DEPENDENCY_CONFLICT", "OTHER"]

# Severity levels
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Resolution strategies
ResolutionStrategy = Literal["remote_wins", "local_wins", "merge", "manual"]


class ConflictResolutionService:
    """
    Detect and resolve skill synchronization conflicts.

    Supports 4 resolution strategies:
    - remote_wins: Atom SaaS is source of truth (default)
    - local_wins: Local skill takes precedence
    - merge: Intelligently merge fields
    - manual: Create conflict log for human review
    """

    def __init__(self, db: Session):
        """
        Initialize conflict resolution service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def detect_skill_conflict(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> Optional[ConflictType]:
        """
        Detect if local and remote skills conflict.

        Checks version, content hash, and dependencies for differences.

        Args:
            local_skill: Local skill data (from Community Skill)
            remote_skill: Remote skill data (from Atom SaaS)

        Returns:
            Conflict type string or None if no conflict
        """
        # Check version mismatch
        version_conflict = self._compare_versions(local_skill, remote_skill)
        if version_conflict:
            logger.debug(f"Version conflict detected: {local_skill.get('skill_id')}")
            return "VERSION_MISMATCH"

        # Check content mismatch
        content_conflict = self._compare_content(local_skill, remote_skill)
        if content_conflict:
            logger.debug(f"Content conflict detected: {local_skill.get('skill_id')}")
            return "CONTENT_MISMATCH"

        # Check dependency conflict
        dep_conflict = self._compare_dependencies(local_skill, remote_skill)
        if dep_conflict:
            logger.debug(f"Dependency conflict detected: {local_skill.get('skill_id')}")
            return "DEPENDENCY_CONFLICT"

        return None

    def calculate_severity(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any],
        conflict_type: ConflictType
    ) -> Severity:
        """
        Calculate conflict severity based on what changed.

        Severity levels:
        - LOW: Description, tags, examples changed
        - MEDIUM: Metadata, parameters changed
        - HIGH: Dependencies, version changed
        - CRITICAL: Code, command, security-sensitive fields changed

        Args:
            local_skill: Local skill data
            remote_skill: Remote skill data
            conflict_type: Type of conflict detected

        Returns:
            Severity level string
        """
        # Check critical fields first
        critical_fields = ['code', 'command', 'local_files']
        for field in critical_fields:
            local_val = local_skill.get(field)
            remote_val = remote_skill.get(field)
            if local_val != remote_val:
                if local_val is not None and remote_val is not None:
                    return "CRITICAL"

        # Check high-severity fields
        high_fields = ['version', 'python_packages', 'npm_packages']
        for field in high_fields:
            if local_skill.get(field) != remote_skill.get(field):
                return "HIGH"

        # Check medium-severity fields
        medium_fields = ['parameters', 'metadata', 'env_vars']
        for field in medium_fields:
            if local_skill.get(field) != remote_skill.get(field):
                return "MEDIUM"

        # Default to LOW for description, tags, examples
        return "LOW"

    def compare_versions(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """
        Check if skill versions match.

        Args:
            local_skill: Local skill data
            remote_skill: Remote skill data

        Returns:
            True if versions differ, False if they match
        """
        local_version = local_skill.get('version', '1.0.0')
        remote_version = remote_skill.get('version', '1.0.0')

        # Handle None values
        if local_version is None:
            local_version = '1.0.0'
        if remote_version is None:
            remote_version = '1.0.0'

        return str(local_version) != str(remote_version)

    def _compare_versions(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """Internal version comparison (alias for compare_versions)."""
        return self.compare_versions(local_skill, remote_skill)

    def compare_content(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """
        Check if skill content/code matches.

        Compares content_hash if available, otherwise compares code field.

        Args:
            local_skill: Local skill data
            remote_skill: Remote skill data

        Returns:
            True if content differs, False if it matches
        """
        # Use content_hash if available
        local_hash = local_skill.get('content_hash')
        remote_hash = remote_skill.get('content_hash')

        if local_hash and remote_hash:
            return local_hash != remote_hash

        # Fall back to code comparison
        local_code = local_skill.get('code', '')
        remote_code = remote_skill.get('code', '')

        # Normalize for comparison (strip whitespace)
        local_code_normalized = local_code.strip() if local_code else ''
        remote_code_normalized = remote_code.strip() if remote_code else ''

        return local_code_normalized != remote_code_normalized

    def _compare_content(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """Internal content comparison (alias for compare_content)."""
        return self.compare_content(local_skill, remote_skill)

    def compare_dependencies(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """
        Check if skill dependencies match.

        Compares python_packages and npm_packages fields.

        Args:
            local_skill: Local skill data
            remote_skill: Remote skill data

        Returns:
            True if dependencies differ, False if they match
        """
        # Get dependencies (handle None)
        local_python = local_skill.get('python_packages') or []
        remote_python = remote_skill.get('python_packages') or []

        local_npm = local_skill.get('npm_packages') or []
        remote_npm = remote_skill.get('npm_packages') or []

        # Sort for consistent comparison
        local_python_sorted = sorted(local_python) if isinstance(local_python, list) else []
        remote_python_sorted = sorted(remote_python) if isinstance(remote_python, list) else []

        local_npm_sorted = sorted(local_npm) if isinstance(local_npm, list) else []
        remote_npm_sorted = sorted(remote_npm) if isinstance(remote_npm, list) else []

        return (local_python_sorted != remote_python_sorted or
                local_npm_sorted != remote_npm_sorted)

    def _compare_dependencies(
        self,
        local_skill: Dict[str, Any],
        remote_skill: Dict[str, Any]
    ) -> bool:
        """Internal dependency comparison (alias for compare_dependencies)."""
        return self.compare_dependencies(local_skill, remote_skill)

    def calculate_content_hash(self, skill_data: Dict[str, Any]) -> str:
        """
        Calculate content hash for skill data.

        Args:
            skill_data: Skill data dictionary

        Returns:
            SHA256 hash string
        """
        # Extract relevant fields for hash
        hash_fields = {
            'skill_id': skill_data.get('skill_id', ''),
            'name': skill_data.get('name', ''),
            'code': skill_data.get('code', ''),
            'version': skill_data.get('version', '1.0.0'),
            'python_packages': skill_data.get('python_packages', []),
            'npm_packages': skill_data.get('npm_packages', []),
        }

        # Serialize and hash
        hash_str = str(sorted(hash_fields.items()))
        return hashlib.sha256(hash_str.encode()).hexdigest()

    def log_conflict(
        self,
        skill_id: str,
        conflict_type: ConflictType,
        severity: Severity,
        local_data: Dict[str, Any],
        remote_data: Dict[str, Any]
    ) -> ConflictLog:
        """
        Log a conflict to the database.

        Args:
            skill_id: Skill identifier
            conflict_type: Type of conflict
            severity: Severity level
            local_data: Local skill data
            remote_data: Remote skill data

        Returns:
            Created ConflictLog record
        """
        conflict = ConflictLog(
            skill_id=skill_id,
            conflict_type=conflict_type,
            severity=severity,
            local_data=local_data,
            remote_data=remote_data,
            resolution_strategy=None,  # Not yet resolved
            resolved_data=None,
            resolved_at=None,
            resolved_by=None
        )

        self.db.add(conflict)
        self.db.commit()
        self.db.refresh(conflict)

        logger.info(f"Logged conflict: {skill_id} - {conflict_type} ({severity})")
        return conflict

    def get_unresolved_conflicts(
        self,
        severity: Optional[Severity] = None,
        conflict_type: Optional[ConflictType] = None,
        limit: int = 100
    ) -> list[ConflictLog]:
        """
        Get unresolved conflicts from database.

        Args:
            severity: Filter by severity (optional)
            conflict_type: Filter by conflict type (optional)
            limit: Maximum number of conflicts to return

        Returns:
            List of unresolved ConflictLog records
        """
        query = self.db.query(ConflictLog).filter(
            ConflictLog.resolved_at.is_(None)
        )

        if severity:
            query = query.filter(ConflictLog.severity == severity)

        if conflict_type:
            query = query.filter(ConflictLog.conflict_type == conflict_type)

        return query.order_by(ConflictLog.created_at.desc()).limit(limit).all()

    def get_conflict_by_id(self, conflict_id: int) -> Optional[ConflictLog]:
        """
        Get conflict by ID.

        Args:
            conflict_id: Conflict log ID

        Returns:
            ConflictLog record or None
        """
        return self.db.query(ConflictLog).filter(
            ConflictLog.id == conflict_id
        ).first()
