"""
Package Feature Service - Controls Personal vs Enterprise edition features.

Purpose:
- Personal Edition: Minimal features, single-user, SQLite (default)
- Enterprise Edition: All features, multi-user, PostgreSQL, monitoring

Feature Flags:
- ATOM_EDITION: personal|enterprise (env var or package detection)
- multi_user: Enterprise-only (workspace isolation, SSO)
- monitoring: Enterprise-only (Prometheus metrics, Grafana)
- advanced_analytics: Enterprise-only (workflow analytics, BI)
- sso: Enterprise-only (Okta, Auth0, SAML)
- audit_trail: Enterprise-only (compliance logging)
"""

import os
import logging
from enum import Enum
from typing import Set, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class Edition(str, Enum):
    """Atom edition types."""
    PERSONAL = "personal"
    ENTERPRISE = "enterprise"


class Feature(str, Enum):
    """Feature flags for Personal vs Enterprise."""
    # Personal features (always available)
    LOCAL_AGENT = "local_agent"
    WORKFLOWS = "workflows"
    CANVAS = "canvas"
    BROWSER_AUTOMATION = "browser_automation"
    EPISODIC_MEMORY = "episodic_memory"
    AGENT_GOVERNANCE = "agent_governance"
    TELEGRAM_CONNECTOR = "telegram_connector"
    COMMUNITY_SKILLS = "community_skills"

    # Enterprise features (require enterprise edition)
    MULTI_USER = "multi_user"
    WORKSPACE_ISOLATION = "workspace_isolation"
    SSO = "sso"  # Okta, Auth0, SAML
    AUDIT_TRAIL = "audit_trail"
    MONITORING = "monitoring"  # Prometheus, Grafana
    ADVANCED_ANALYTICS = "advanced_analytics"
    WORKFLOW_ANALYTICS = "workflow_analytics"
    BI_DASHBOARD = "bi_dashboard"
    RATE_LIMITING = "rate_limiting"
    RBAC = "rbac"  # Role-based access control


@dataclass
class FeatureInfo:
    """Feature metadata."""
    name: str
    description: str
    edition: Edition
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


# Feature registry with metadata
FEATURE_REGISTRY: Dict[Feature, FeatureInfo] = {
    # Personal features
    Feature.LOCAL_AGENT: FeatureInfo(
        "Local Agent",
        "Run AI agents on local machine",
        Edition.PERSONAL
    ),
    Feature.WORKFLOWS: FeatureInfo(
        "Workflow Automation",
        "Create and run automation workflows",
        Edition.PERSONAL
    ),
    Feature.CANVAS: FeatureInfo(
        "Canvas Presentations",
        "Rich interactive presentations",
        Edition.PERSONAL
    ),
    Feature.BROWSER_AUTOMATION: FeatureInfo(
        "Browser Automation",
        "Web scraping and form filling",
        Edition.PERSONAL
    ),
    Feature.EPISODIC_MEMORY: FeatureInfo(
        "Episodic Memory",
        "Agents remember past interactions",
        Edition.PERSONAL
    ),
    Feature.AGENT_GOVERNANCE: FeatureInfo(
        "Agent Governance",
        "Maturity levels and permissions",
        Edition.PERSONAL
    ),
    Feature.TELEGRAM_CONNECTOR: FeatureInfo(
        "Telegram Connector",
        "Telegram bot integration",
        Edition.PERSONAL
    ),
    Feature.COMMUNITY_SKILLS: FeatureInfo(
        "Community Skills",
        "Import 5,000+ OpenClaw/ClawHub skills",
        Edition.PERSONAL
    ),

    # Enterprise features
    Feature.MULTI_USER: FeatureInfo(
        "Multi-User",
        "Multiple users with role-based access",
        Edition.ENTERPRISE
    ),
    Feature.WORKSPACE_ISOLATION: FeatureInfo(
        "Workspace Isolation",
        "Separate workspaces for teams",
        Edition.ENTERPRISE,
        dependencies=[Feature.MULTI_USER]
    ),
    Feature.SSO: FeatureInfo(
        "Single Sign-On",
        "Okta, Auth0, SAML authentication",
        Edition.ENTERPRISE,
        dependencies=[Feature.MULTI_USER]
    ),
    Feature.AUDIT_TRAIL: FeatureInfo(
        "Audit Trail",
        "Compliance logging and reporting",
        Edition.ENTERPRISE
    ),
    Feature.MONITORING: FeatureInfo(
        "Monitoring",
        "Prometheus metrics and Grafana dashboards",
        Edition.ENTERPRISE
    ),
    Feature.ADVANCED_ANALYTICS: FeatureInfo(
        "Advanced Analytics",
        "Workflow performance analytics",
        Edition.ENTERPRISE,
        dependencies=[Feature.MONITORING]
    ),
    Feature.WORKFLOW_ANALYTICS: FeatureInfo(
        "Workflow Analytics",
        "Detailed workflow execution analytics",
        Edition.ENTERPRISE
    ),
    Feature.BI_DASHBOARD: FeatureInfo(
        "BI Dashboard",
        "Business intelligence and reporting",
        Edition.ENTERPRISE,
        dependencies=[Feature.ADVANCED_ANALYTICS]
    ),
    Feature.RATE_LIMITING: FeatureInfo(
        "Rate Limiting",
        "API rate limiting and throttling",
        Edition.ENTERPRISE
    ),
    Feature.RBAC: FeatureInfo(
        "Role-Based Access Control",
        "Fine-grained permissions",
        Edition.ENTERPRISE,
        dependencies=[Feature.MULTI_USER]
    ),
}


class PackageFeatureService:
    """
    Service for managing Personal vs Enterprise feature flags.

    Detection Priority:
    1. ATOM_EDITION environment variable
    2. Package extras detection (if enterprise extras installed)
    3. Default to Personal Edition
    """

    _instance: Optional["PackageFeatureService"] = None
    _edition: Optional[Edition] = None
    _available_features: Set[Feature] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._edition is None:
            self._detect_edition()
            self._build_feature_set()

    def _detect_edition(self) -> None:
        """Detect edition from environment or package installation."""
        # 1. Check environment variable
        env_edition = os.getenv("ATOM_EDITION", "").lower()
        if env_edition in ("enterprise", "full"):
            self._edition = Edition.ENTERPRISE
            logger.info("Atom Edition: ENTERPRISE (from ATOM_EDITION)")
            return
        elif env_edition == "personal":
            self._edition = Edition.PERSONAL
            logger.info("Atom Edition: PERSONAL (from ATOM_EDITION)")
            return

        # 2. Check if enterprise extras are installed
        try:
            import importlib.metadata
            # Try to detect enterprise extras
            try:
                dist = importlib.metadata.distribution("atom-os")
                # Check if enterprise dependencies are installed
                for req in dist.requires or []:
                    if "postgresql" in req.lower() or "psycopg" in req.lower():
                        self._edition = Edition.ENTERPRISE
                        logger.info("Atom Edition: ENTERPRISE (detected enterprise extras)")
                        return
            except importlib.metadata.PackageNotFoundError:
                pass
        except Exception:
            pass

        # 3. Check DATABASE_URL for PostgreSQL (common indicator)
        db_url = os.getenv("DATABASE_URL", "")
        if "postgresql" in db_url or "postgres" in db_url:
            self._edition = Edition.ENTERPRISE
            logger.info("Atom Edition: ENTERPRISE (detected PostgreSQL)")
            return

        # 4. Default to Personal Edition
        self._edition = Edition.PERSONAL
        logger.info("Atom Edition: PERSONAL (default)")

    def _build_feature_set(self) -> None:
        """Build set of available features based on edition."""
        if self._edition == Edition.ENTERPRISE:
            # Enterprise has all features
            self._available_features = set(Feature)
        else:
            # Personal has only Personal features
            self._available_features = {
                f for f, info in FEATURE_REGISTRY.items()
                if info.edition == Edition.PERSONAL
            }

    @property
    def edition(self) -> Edition:
        """Get current edition."""
        return self._edition

    @property
    def is_enterprise(self) -> bool:
        """Check if Enterprise edition is enabled."""
        return self._edition == Edition.ENTERPRISE

    @property
    def is_personal(self) -> bool:
        """Check if Personal Edition is enabled."""
        return self._edition == Edition.PERSONAL

    def is_feature_enabled(self, feature: Feature) -> bool:
        """
        Check if a feature is enabled in current edition.

        Args:
            feature: Feature to check

        Returns:
            True if feature is available, False otherwise
        """
        # Check dependencies first
        feature_info = FEATURE_REGISTRY.get(feature)
        if feature_info and feature_info.dependencies:
            for dep in feature_info.dependencies:
                if dep not in self._available_features:
                    return False

        return feature in self._available_features

    def get_available_features(self) -> Set[Feature]:
        """Get all available features for current edition."""
        return self._available_features.copy()

    def get_enterprise_features(self) -> Set[Feature]:
        """Get enterprise-only features."""
        return {
            f for f, info in FEATURE_REGISTRY.items()
            if info.edition == Edition.ENTERPRISE
        }

    def get_personal_features(self) -> Set[Feature]:
        """Get Personal Edition features."""
        return {
            f for f, info in FEATURE_REGISTRY.items()
            if info.edition == Edition.PERSONAL
        }

    def require_feature(self, feature: Feature) -> None:
        """
        Raise exception if feature is not available.

        Raises:
            PermissionError: If feature is not available in current edition
        """
        if not self.is_feature_enabled(feature):
            feature_info = FEATURE_REGISTRY.get(feature)
            raise PermissionError(
                f"Feature '{feature_info.name if feature_info else feature}' "
                f"requires Enterprise Edition. "
                f"Enable with: atom enable enterprise "
                f"or pip install atom-os[enterprise]"
            )

    def get_feature_info(self, feature: Feature) -> Optional[FeatureInfo]:
        """Get feature metadata."""
        return FEATURE_REGISTRY.get(feature)

    def list_features(self) -> List[Dict[str, any]]:
        """
        List all features with availability status.

        Returns:
            List of feature dicts with name, description, available, edition
        """
        result = []
        for feature, info in FEATURE_REGISTRY.items():
            result.append({
                "id": feature.value,
                "name": info.name,
                "description": info.description,
                "available": feature in self._available_features,
                "edition": info.edition.value,
                "dependencies": [d.value for d in info.dependencies],
            })
        return sorted(result, key=lambda x: (not x["available"], x["name"]))


# Global singleton
_package_feature_service: Optional[PackageFeatureService] = None


def get_package_feature_service() -> PackageFeatureService:
    """Get global PackageFeatureService singleton."""
    global _package_feature_service
    if _package_feature_service is None:
        _package_feature_service = PackageFeatureService()
    return _package_feature_service


def is_enterprise_enabled() -> bool:
    """Quick check if Enterprise edition is enabled."""
    return get_package_feature_service().is_enterprise


def is_feature_enabled(feature: Feature) -> bool:
    """Quick check if feature is enabled."""
    return get_package_feature_service().is_feature_enabled(feature)


def require_enterprise() -> None:
    """Raise exception if not Enterprise edition."""
    service = get_package_feature_service()
    if not service.is_enterprise:
        raise PermissionError(
            "This feature requires Enterprise Edition. "
            "Enable with: atom enable enterprise "
            "or pip install atom-os[enterprise]"
        )
