"""
Package Governance Service - Maturity-based Python and npm package permissions.

Extends GovernanceCache for package permission checks:
- Cache key format: "pkg:{package_type}:{package_name}:{version}"
- Cache value: {"allowed": bool, "maturity_required": str, "reason": str}
- STUDENT agents: Blocked from all Python and npm packages
- INTERN agents: Require approval for each package version
- SUPERVISED agents: Allowed if min_maturity <= SUPERVISED
- AUTONOMOUS agents: Allowed if min_maturity <= AUTONOMOUS (whitelist still enforced)
- Banned packages: Blocked for all agents regardless of maturity

Performance: <1ms cached lookups via GovernanceCache integration
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from core.governance_cache import get_governance_cache
from core.models import PackageRegistry, AgentRegistry

logger = logging.getLogger(__name__)


class PackageGovernanceService:
    """
    Maturity-based package governance with caching.

    Enforces package access controls based on agent maturity levels
    while maintaining <1ms performance through GovernanceCache integration.
    """

    # Maturity level ordering for comparisons (lowercase to match AgentStatus enum)
    MATURITY_ORDER = {
        "student": 0,
        "intern": 1,
        "supervised": 2,
        "autonomous": 3
    }

    # Package type constants
    PACKAGE_TYPE_PYTHON = "python"
    PACKAGE_TYPE_NPM = "npm"

    # Package permission statuses
    STATUS_UNTRUSTED = "untrusted"
    STATUS_ACTIVE = "active"
    STATUS_BANNED = "banned"
    STATUS_PENDING = "pending"

    def __init__(self):
        """Initialize package governance service with governance cache."""
        self.cache = get_governance_cache()
        logger.info("PackageGovernanceService initialized with governance cache")

    def check_package_permission(
        self,
        agent_id: str,
        package_name: str,
        version: str,
        db: Session,
        package_type: str = PACKAGE_TYPE_PYTHON
    ) -> Dict[str, Any]:
        """
        Check if agent can use specific Python or npm package version.

        Cache key format: "pkg:{package_type}:{package_name}:{version}"
        Returns: {"allowed": bool, "maturity_required": str, "reason": str}

        Args:
            agent_id: Agent ID requesting package access
            package_name: Package name (e.g., "numpy", "lodash")
            version: Package version (e.g., "1.21.0", "4.17.21")
            db: Database session
            package_type: Package type ("python" or "npm", default="python")

        Governance rules:
        1. STUDENT agents: Always blocked (non-negotiable)
        2. Banned packages: Always blocked regardless of maturity
        3. Unknown packages: Require approval (status=untrusted)
        4. Approved packages: Check maturity requirements

        Performance: <1ms for cached results, ~10-50ms for database lookups
        """
        # Check cache first for <1ms performance
        cache_key = f"pkg:{package_type}:{package_name}:{version}"
        cached = self.cache.get(agent_id, cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT for {package_type} package {package_name}@{version}")
            return cached

        logger.debug(f"Cache MISS for {package_type} package {package_name}@{version} - checking database")

        # Get agent maturity (stored in 'status' field)
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        agent_maturity = agent.status if agent else "student"

        # Check package registry FIRST (before STUDENT blocking)
        # This allows banned package reason to take precedence
        package = db.query(PackageRegistry).filter(
            PackageRegistry.name == package_name,
            PackageRegistry.version == version,
            PackageRegistry.package_type == package_type
        ).first()

        # Banned package enforcement (overrides ALL other rules including STUDENT)
        if package and package.status == self.STATUS_BANNED:
            result = {
                "allowed": False,
                "maturity_required": "NONE",
                "reason": f"Package {package_name}@{version} ({package_type}) is banned: {package.ban_reason or 'No reason provided'}"
            }
            self.cache.set(agent_id, cache_key, result)
            logger.warning(f"Banned {package_type} package {package_name}@{version} blocked for agent {agent_id}")
            return result

        # STUDENT blocking rule (non-negotiable - educational restriction)
        # But banned packages already handled above
        if agent_maturity == "student":
            result = {
                "allowed": False,
                "maturity_required": "intern",
                "reason": f"STUDENT agents cannot execute {package_type} packages (educational restriction)"
            }
            self.cache.set(agent_id, cache_key, result)
            logger.info(f"STUDENT agent {agent_id} blocked from {package_type} package {package_name}@{version}")
            return result

        # Unknown package - requires approval
        if not package or package.status == self.STATUS_UNTRUSTED:
            result = {
                "allowed": False,
                "maturity_required": "intern",
                "reason": f"Package {package_name}@{version} ({package_type}) not in registry - requires approval"
            }
            self.cache.set(agent_id, cache_key, result)
            logger.info(f"Unknown {package_type} package {package_name}@{version} blocked for agent {agent_id}")
            return result

        # Pending approval - not yet approved
        if package.status == self.STATUS_PENDING:
            result = {
                "allowed": False,
                "maturity_required": package.min_maturity,
                "reason": f"Package {package_name}@{version} ({package_type}) is pending approval"
            }
            self.cache.set(agent_id, cache_key, result)
            logger.info(f"Pending {package_type} package {package_name}@{version} blocked for agent {agent_id}")
            return result

        # Active package - check maturity requirements
        if package.status == self.STATUS_ACTIVE:
            if self._maturity_cmp(agent_maturity, package.min_maturity) >= 0:
                result = {
                    "allowed": True,
                    "maturity_required": package.min_maturity,
                    "reason": None
                }
                self.cache.set(agent_id, cache_key, result)
                logger.info(f"Agent {agent_id} allowed to use {package_type} package {package_name}@{version}")
                return result
            else:
                result = {
                    "allowed": False,
                    "maturity_required": package.min_maturity,
                    "reason": f"Agent maturity {agent_maturity} < required {package.min_maturity}"
                }
                self.cache.set(agent_id, cache_key, result)
                logger.info(
                    f"Agent {agent_id} blocked from {package_type} package {package_name}@{version}: "
                    f"maturity {agent_maturity} < required {package.min_maturity}"
                )
                return result

        # Default deny for unexpected statuses
        result = {
            "allowed": False,
            "maturity_required": "intern",
            "reason": f"Package {package_name}@{version} ({package_type}) has unexpected status: {package.status}"
        }
        self.cache.set(agent_id, cache_key, result)
        return result

    def request_package_approval(
        self,
        package_name: str,
        version: str,
        requested_by: str,
        reason: str,
        db: Session,
        package_type: str = PACKAGE_TYPE_PYTHON
    ) -> PackageRegistry:
        """
        Create or update package registry entry with status='pending'.

        Args:
            package_name: Package name (e.g., "numpy", "lodash")
            version: Package version (e.g., "1.21.0", "4.17.21")
            requested_by: User ID requesting approval
            reason: Reason for package request
            db: Database session
            package_type: Package type ("python" or "npm", default="python")

        Creates a request for package approval that can be reviewed by admins.
        """
        package_id = f"{package_name}:{version}"
        package = db.query(PackageRegistry).filter(
            PackageRegistry.id == package_id,
            PackageRegistry.package_type == package_type
        ).first()

        if package:
            # Update existing package entry
            package.status = self.STATUS_PENDING
            package.updated_at = datetime.utcnow()
            logger.info(f"Updated {package_type} package {package_id} to pending status")
        else:
            # Create new package registry entry
            package = PackageRegistry(
                id=package_id,
                name=package_name,
                version=version,
                package_type=package_type,
                status=self.STATUS_PENDING,
                min_maturity="intern"  # Default minimum maturity
            )
            db.add(package)
            logger.info(f"Created pending {package_type} package request for {package_id}")

        db.commit()

        # Clear all cache to ensure immediate effect (cache key pattern doesn't support wildcards)
        self.cache.clear()

        return package

    def approve_package(
        self,
        package_name: str,
        version: str,
        min_maturity: str,
        approved_by: str,
        db: Session,
        package_type: str = PACKAGE_TYPE_PYTHON
    ) -> PackageRegistry:
        """
        Approve package for specified maturity level and above.

        Args:
            package_name: Package name (e.g., "numpy", "lodash")
            version: Package version (e.g., "1.21.0", "4.17.21")
            min_maturity: Minimum maturity level required
            approved_by: User ID approving the package
            db: Database session
            package_type: Package type ("python" or "npm", default="python")

        Grants permission for agents at or above the specified maturity level.
        Invalidates cache to ensure immediate effect.
        """
        # Validate maturity level
        if min_maturity not in self.MATURITY_ORDER:
            raise ValueError(
                f"Invalid maturity level: {min_maturity}. "
                f"Must be one of: {list(self.MATURITY_ORDER.keys())}"
            )

        package_id = f"{package_name}:{version}"
        package = db.query(PackageRegistry).filter(
            PackageRegistry.id == package_id,
            PackageRegistry.package_type == package_type
        ).first()

        if package:
            # Update existing package
            package.status = self.STATUS_ACTIVE
            package.min_maturity = min_maturity
            package.approved_by = approved_by
            package.approved_at = datetime.utcnow()
            package.updated_at = datetime.utcnow()
            logger.info(
                f"Approved {package_type} package {package_id} for maturity {min_maturity}+ "
                f"by {approved_by}"
            )
        else:
            # Create new active package
            package = PackageRegistry(
                id=package_id,
                name=package_name,
                version=version,
                package_type=package_type,
                status=self.STATUS_ACTIVE,
                min_maturity=min_maturity,
                approved_by=approved_by,
                approved_at=datetime.utcnow()
            )
            db.add(package)
            logger.info(
                f"Created and approved {package_type} package {package_id} for maturity {min_maturity}+ "
                f"by {approved_by}"
            )

        # Clear all cache to ensure immediate effect
        self.cache.clear()
        logger.info(f"Cleared cache for package {package_id}")

        db.commit()
        return package

    def ban_package(
        self,
        package_name: str,
        version: str,
        reason: str,
        db: Session,
        package_type: str = PACKAGE_TYPE_PYTHON
    ) -> PackageRegistry:
        """
        Ban package version with reason.

        Args:
            package_name: Package name (e.g., "numpy", "lodash")
            version: Package version (e.g., "1.21.0", "4.17.21")
            reason: Reason for banning the package
            db: Database session
            package_type: Package type ("python" or "npm", default="python")

        Banned packages are blocked for ALL agents regardless of maturity.
        Use this for security vulnerabilities, malicious code, or policy violations.
        """
        package_id = f"{package_name}:{version}"
        package = db.query(PackageRegistry).filter(
            PackageRegistry.id == package_id,
            PackageRegistry.package_type == package_type
        ).first()

        if package:
            # Update existing package
            package.status = self.STATUS_BANNED
            package.ban_reason = reason
            package.updated_at = datetime.utcnow()
            logger.warning(f"Banned {package_type} package {package_id}: {reason}")
        else:
            # Create new banned package
            package = PackageRegistry(
                id=package_id,
                name=package_name,
                version=version,
                package_type=package_type,
                status=self.STATUS_BANNED,
                ban_reason=reason,
                min_maturity="autonomous"  # Highest maturity (still blocked)
            )
            db.add(package)
            logger.warning(f"Created banned {package_type} package {package_id}: {reason}")

        # Clear all cache to ensure immediate effect
        self.cache.clear()
        logger.warning(f"Cleared cache for banned package {package_id}")

        db.commit()
        return package

    def list_packages(
        self,
        status: Optional[str] = None,
        package_type: Optional[str] = None,
        db: Session = None
    ) -> list[PackageRegistry]:
        """
        List all packages in registry, optionally filtered by status and package type.

        Args:
            status: Filter by status (untrusted, active, banned, pending)
            package_type: Filter by package type ("python" or "npm")
            db: Database session

        Returns:
            List of PackageRegistry objects
        """
        query = db.query(PackageRegistry)

        if status:
            query = query.filter(PackageRegistry.status == status)

        if package_type:
            query = query.filter(PackageRegistry.package_type == package_type)

        return query.order_by(PackageRegistry.created_at.desc()).all()

    def _maturity_cmp(self, a: str, b: str) -> int:
        """
        Compare maturity levels.

        Returns:
            >0 if a > b (a has higher maturity)
            0 if a == b (same maturity)
            <0 if a < b (a has lower maturity)

        Example:
            _maturity_cmp("autonomous", "intern") > 0
            _maturity_cmp("student", "supervised") < 0
        """
        return self.MATURITY_ORDER.get(a.lower() if a else a, 0) - self.MATURITY_ORDER.get(b.lower() if b else b, 0)

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get governance cache statistics.

        Returns cache performance metrics including hit rate, size, evictions.
        """
        return self.cache.get_stats()
