---
phase: 04-installer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/pyproject.toml
  - backend/setup.py
  - backend/requirements.txt
  - backend/requirements-personal.txt
  - backend/core/package_feature_service.py
autonomous: true

must_haves:
  truths:
    - User can install with pip install atom-os[enterprise] for full features
    - User can install with pip install atom-os for Personal Edition only
    - PackageFeatureService controls which features are available
    - Enterprise features hidden by default in Personal Edition
    - pyproject.toml uses [project.optional-dependencies] for extras
    - setup.py compatible with older pip versions
  artifacts:
    - path: backend/core/package_feature_service.py
      provides: Feature flag service controlling Personal vs Enterprise
      min_lines: 100
      exports: ["PackageFeatureService", "is_enterprise_enabled", "get_available_features"]
    - path: backend/pyproject.toml
      provides: Modern packaging with optional dependencies
      contains: "[project.optional-dependencies]"
    - path: backend/requirements-personal.txt
      provides: Personal Edition minimal dependencies
      contains: "fastapi", "uvicorn", "sqlalchemy"
  key_links:
    - from: "backend/pyproject.toml"
      to: "backend/setup.py"
      via: "Optional dependencies synchronized"
      pattern: "extras_require"
    - from: "backend/core/package_feature_service.py"
      to: "Environment variables"
      via: "ATOM_EDITION environment variable"
      pattern: "ATOM_EDITION.*personal|enterprise"
---

<objective>
Create pyproject.toml setup with setuptools, feature flags (PackageFeatureService), and Personal Edition dependencies.

Purpose: Enable Personal Edition (minimal features) with optional enterprise extras via pip install atom-os[enterprise]
Output: Package metadata with optional dependencies, feature flag service
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
@/Users/rushiparikh/.claude/get-shit-done/references/checkpoints.md
</execution_context>

<context>
@.planning/phases/04-installer/04-RESEARCH.md
@.planning/ROADMAP.md
@.planning/STATE.md
@docs/PERSONAL_EDITION.md

# Existing packaging
@backend/pyproject.toml
@backend/setup.py
@backend/requirements.txt
</context>

<tasks>

<task type="auto">
  <name>Create PackageFeatureService for feature flags</name>
  <files>backend/core/package_feature_service.py</files>
  <action>
Create backend/core/package_feature_service.py (150-200 lines):

```python
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
```

Follow Atom patterns:
- Singleton service pattern
- Environment variable detection
- Feature registry with metadata
- Type hints and docstrings
  </action>
  <verify>
```bash
# Verify PackageFeatureService created
test -f backend/core/package_feature_service.py
grep -n "class PackageFeatureService" backend/core/package_feature_service.py
grep -n "Edition.PERSONAL\|Edition.ENTERPRISE" backend/core/package_feature_service.py
grep -n "def is_enterprise_enabled" backend/core/package_feature_service.py
```
  </verify>
  <done>
PackageFeatureService created with:
- Edition enum (PERSONAL, ENTERPRISE)
- Feature enum with Personal and Enterprise features
- FEATURE_REGISTRY with metadata for all features
- PackageFeatureService singleton with edition detection
- Environment variable (ATOM_EDITION) detection
- Package extras detection (postgresql dependency)
- is_feature_enabled() for gate checking
- require_enterprise() for permission errors
- list_features() for feature discovery
  </done>
</task>

<task type="auto">
  <name>Create Personal Edition requirements file</name>
  <files>backend/requirements-personal.txt</files>
  <action>
Create backend/requirements-personal.txt (minimal dependencies for Personal Edition):

```txt
# Atom Personal Edition - Minimal dependencies
# Install: pip install -r requirements-personal.txt
# Or: pip install atom-os

# Core framework
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
pydantic>=2.0.0
python-multipart>=0.0.5

# Database (SQLite for Personal)
sqlalchemy>=2.0.0
alembic>=1.8.0

# Authentication
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# Configuration
python-dotenv>=1.0.0

# LLM providers
openai>=1.0.0
anthropic>=0.18.0

# Websockets
websockets>=11.0

# HTTP client
httpx>=0.24.0

# CLI (already installed with pip)
click>=8.0.0

# Vector embeddings (Personal Edition - local)
fastembed>=0.2.0
# Note: fastembed uses local models, no API key needed

# Basic logging
structlog>=23.1.0

# NOTE: Enterprise dependencies excluded:
# - PostgreSQL drivers (psycopg2-binary)
# - Redis (for pub/sub in multi-user)
# - Monitoring (prometheus-client)
# - SSO providers (authlib, python-okta)
# - Advanced analytics
```

This file defines the minimal dependency set for Personal Edition.
  </action>
  <verify>
```bash
# Verify requirements-personal.txt created
test -f backend/requirements-personal.txt
grep -n "fastapi" backend/requirements-personal.txt
grep -n "sqlite" backend/requirements-personal.txt || grep -n "sqlalchemy" backend/requirements-personal.txt
```
  </verify>
  <done>
requirements-personal.txt created with:
- Core framework (FastAPI, uvicorn, pydantic)
- Database (SQLAlchemy with SQLite)
- Authentication (python-jose, passlib)
- LLM providers (OpenAI, Anthropic)
- Vector embeddings (fastembed local)
- Enterprise dependencies excluded (PostgreSQL, Redis, monitoring)
  </done>
</task>

<task type="auto">
  <name>Update pyproject.toml with optional dependencies</name>
  <files>backend/pyproject.toml</files>
  <action>
Update backend/pyproject.toml to add optional enterprise dependencies:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "atom-os"
version = "0.1.0"
description = "AI-powered business automation platform"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Atom Platform", email = "contact@atom-platform.dev"},
]
keywords = ["automation", "ai", "agents", "governance", "llm", "workflow"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

# Core dependencies (Personal Edition)
dependencies = [
    # Core framework
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.5",

    # Database (SQLite for Personal)
    "sqlalchemy>=2.0.0",
    "alembic>=1.8.0",

    # Authentication
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",

    # Configuration
    "python-dotenv>=1.0.0",

    # LLM providers
    "openai>=1.0.0",
    "anthropic>=0.18.0",

    # Websockets
    "websockets>=11.0",

    # HTTP client
    "httpx>=0.24.0",

    # CLI
    "click>=8.0.0",

    # Vector embeddings (local)
    "fastembed>=0.2.0",

    # Logging
    "structlog>=23.1.0",
]

# Optional dependencies for Enterprise Edition
[project.optional-dependencies]
# Full enterprise features
enterprise = [
    # PostgreSQL driver
    "psycopg2-binary>=2.9.0",

    # Redis for pub/sub (multi-user)
    "redis>=4.5.0",

    # Monitoring
    "prometheus-client>=0.17.0",

    # SSO providers
    "authlib>=1.2.0",
    "pyokta>=1.0.0",

    # Advanced analytics
    "pandas>=2.0.0",
    "numpy>=1.24.0",

    # Rate limiting
    "slowapi>=0.1.9",

    # Additional integrations
    "boto3>=1.28.0",  # AWS
    "google-cloud-storage>=2.5.0",
]

# Development dependencies
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.0.0",
    "black>=23.0.0",
    "ruff>=0.0.280",
]

# Testing dependencies
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "httpx>=0.24.0",
    "faker>=19.0.0",
]

# All dependencies (dev + enterprise)
all = [
    "atom-os[enterprise,dev,test]",
]

[project.urls]
Homepage = "https://github.com/rush86999/atom"
Documentation = "https://github.com/rush86999/atom/tree/main/docs"
Repository = "https://github.com/rush86999/atom"
"Bug Tracker" = "https://github.com/rush86999/atom/issues"

[project.scripts]
atom-os = "cli.main:main_cli"

[tool.setuptools]
zip_safe = false

# Package discovery
[tool.setuptools.packages.find]
exclude = ["tests.*", "tests", "*.tests", "*.tests.*"]

# Include data files
[tool.setuptools.package-data]
"*" = ["*.md", "*.txt", "*.yml", "*.yaml"]
```

Key changes:
- Added [project.dependencies] for Personal Edition
- Added [project.optional-dependencies] with enterprise extras
- Added dev, test, and all dependency groups
  </action>
  <verify>
```bash
# Verify pyproject.toml updated
grep -n "\[project.dependencies\]" backend/pyproject.toml
grep -n "\[project.optional-dependencies\]" backend/pyproject.toml
grep -n "enterprise = \[" backend/pyproject.toml
grep -n "psycopg2-binary" backend/pyproject.toml
```
  </verify>
  <done>
pyproject.toml updated with:
- [project.dependencies] for Personal Edition core deps
- [project.optional-dependencies] with enterprise, dev, test, all groups
- PostgreSQL, Redis, monitoring, SSO in enterprise extras
- Development and testing dependency groups
  </done>
</task>

<task type="auto">
  <name>Update setup.py with optional dependencies</name>
  <files>backend/setup.py</files>
  <action>
Update backend/setup.py to sync with pyproject.toml:

```python
"""
Setup configuration for pip installable Atom OS package.

Personal Edition: pip install atom-os
Enterprise Edition: pip install atom-os[enterprise]

Feature flags controlled by PackageFeatureService.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text()

# Core dependencies (Personal Edition)
install_requires = [
    # Core framework
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.5",

    # Database (SQLite for Personal)
    "sqlalchemy>=2.0.0",
    "alembic>=1.8.0",

    # Authentication
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",

    # Configuration
    "python-dotenv>=1.0.0",

    # LLM providers
    "openai>=1.0.0",
    "anthropic>=0.18.0",

    # Websockets
    "websockets>=11.0",

    # HTTP client
    "httpx>=0.24.0",

    # CLI
    "click>=8.0.0",

    # Vector embeddings (local)
    "fastembed>=0.2.0",

    # Logging
    "structlog>=23.1.0",
]

# Optional dependencies for Enterprise Edition
extras_require = {
    "enterprise": [
        # PostgreSQL driver
        "psycopg2-binary>=2.9.0",

        # Redis for pub/sub (multi-user)
        "redis>=4.5.0",

        # Monitoring
        "prometheus-client>=0.17.0",

        # SSO providers
        "authlib>=1.2.0",
        "pyokta>=1.0.0",

        # Advanced analytics
        "pandas>=2.0.0",
        "numpy>=1.24.0",

        # Rate limiting
        "slowapi>=0.1.9",

        # Additional integrations
        "boto3>=1.28.0",  # AWS
        "google-cloud-storage>=2.5.0",
    ],
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "mypy>=1.0.0",
        "black>=23.0.0",
        "ruff>=0.0.280",
    ],
    "test": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "httpx>=0.24.0",
        "faker>=19.0.0",
    ],
    "all": [
        "atom-os[enterprise,dev,test]",
    ],
}

setup(
    name="atom-os",
    version="0.1.0",
    description="AI-powered business automation platform with multi-agent governance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Atom Platform",
    author_email="contact@atom-platform.dev",
    url="https://github.com/rush86999/atom",
    project_urls={
        "Bug Tracker": "https://github.com/rush86999/atom/issues",
        "Documentation": "https://github.com/rush86999/atom/tree/main/docs",
        "Source Code": "https://github.com/rush86999/atom",
    },

    packages=find_packages(exclude=["tests.*", "tests", "*.tests", "*.tests.*"]),
    include_package_data=True,

    # Python version requirement
    python_requires=">=3.11",

    # Dependencies
    install_requires=install_requires,
    extras_require=extras_require,

    # Console script entry points
    entry_points={
        "console_scripts": [
            "atom-os=cli.main:main_cli",
        ],
    },

    # Package metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],

    # Keywords for PyPI
    keywords="automation ai agents governance multi-agent llm business workflow",

    # Zip safe
    zip_safe=False,

    # Include data files
    package_data={
        "atom_os": ["templates/*", "static/*"],
    },
)
```

Sync setup.py extras_require with pyproject.toml optional-dependencies.
  </action>
  <verify>
```bash
# Verify setup.py updated
grep -n "extras_require" backend/setup.py
grep -n "\"enterprise\":" backend/setup.py
grep -n "psycopg2-binary" backend/setup.py
```
  </verify>
  <done>
setup.py updated with:
- install_requires synced with pyproject.toml dependencies
- extras_require with enterprise, dev, test, all groups
- PostgreSQL, Redis, monitoring, SSO in enterprise extras
- Compatibility with older pip versions
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. PackageFeatureService exists with edition detection
2. pyproject.toml has [project.optional-dependencies] with enterprise extras
3. setup.py has extras_require synced with pyproject.toml
4. requirements-personal.txt exists with minimal dependencies
5. Enterprise dependencies include PostgreSQL, Redis, monitoring, SSO
6. PackageFeatureService detects ATOM_EDITION environment variable
7. is_feature_enabled() works for gating features
8. require_enterprise() raises helpful error messages
</verification>

<success_criteria>
- pip install atom-os installs Personal Edition (minimal deps)
- pip install atom-os[enterprise] installs Enterprise Edition (all deps)
- PackageFeatureService detects edition from ATOM_EDITION env var
- is_enterprise_enabled() returns correct boolean
- Enterprise features (multi_user, sso, monitoring) gated properly
- Personal features (local_agent, workflows, canvas) always available
</success_criteria>

<output>
After completion, create `.planning/phases/04-installer/04-installer-01-SUMMARY.md` with:
- Files created/modified
- PackageFeatureService API
- Edition detection logic
- Optional dependencies structure
- Enterprise extras list
</output>
