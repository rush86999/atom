---
phase: 04-installer
plan: 01
subsystem: packaging
tags: [pyproject.toml, setuptools, feature-flags, package-feature-service, personal-edition, enterprise-edition]

# Dependency graph
requires:
  - phase: 02-local-agent
    provides: local agent service for Personal Edition
provides:
  - PackageFeatureService for Personal vs Enterprise edition feature flags
  - pyproject.toml with [project.optional-dependencies] for enterprise extras
  - setup.py with extras_require for older pip versions
  - requirements-personal.txt with minimal Personal Edition dependencies
affects: [04-installer-02, 04-installer-03]

# Tech tracking
tech-stack:
  added: [setuptools>=70.0.0, build, twine]
  patterns: [edition detection via environment variables, feature flag service singleton, optional dependencies for extras]

key-files:
  created:
    - backend/core/package_feature_service.py (372 lines)
    - backend/requirements-personal.txt (47 lines)
  modified:
    - backend/pyproject.toml (140 lines)
    - backend/setup.py (169 lines)

key-decisions:
  - "Used environment variable ATOM_EDITION for edition detection (personal/enterprise)"
  - "PackageFeatureService singleton with edition detection priority: ATOM_EDITION → package extras → DATABASE_URL → default Personal"
  - "Feature registry with dependencies support (workspace_isolation requires multi_user)"
  - "Separate requirements-personal.txt for minimal Personal Edition dependencies"
  - "Synced pyproject.toml and setup.py for compatibility with old and new pip versions"

patterns-established:
  - "Pattern 1: Feature flag service with singleton pattern and edition detection"
  - "Pattern 2: Optional dependencies in pyproject.toml [project.optional-dependencies]"
  - "Pattern 3: Environment variable-based edition detection with fallbacks"

# Metrics
duration: 2min
completed: 2026-02-16
---

# Phase 04: Installer Plan 01 Summary

**PackageFeatureService with Personal/Enterprise edition detection, pyproject.toml with optional dependencies, and Personal Edition requirements file**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-16T23:18:44Z
- **Completed:** 2026-02-16T23:20:00Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Created PackageFeatureService for controlling Personal vs Enterprise feature flags with edition detection
- Updated pyproject.toml with [project.dependencies] for Personal Edition and [project.optional-dependencies] for enterprise extras
- Updated setup.py with install_requires and extras_require for older pip version compatibility
- Created requirements-personal.txt with minimal dependencies for Personal Edition

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PackageFeatureService for feature flags** - `43363d54` (feat)
2. **Task 2: Create Personal Edition requirements file** - `2f619d32` (feat)
3. **Task 3: Update pyproject.toml with optional dependencies** - `70c47f46` (feat)
4. **Task 4: Update setup.py with optional dependencies** - `594e28f8` (feat)

**Plan metadata:** N/A (not applicable for this plan type)

## Files Created/Modified

### Created

- `backend/core/package_feature_service.py` (372 lines)
  - Edition enum (PERSONAL, ENTERPRISE)
  - Feature enum with 8 Personal features and 10 Enterprise features
  - FeatureInfo dataclass with metadata and dependencies
  - FEATURE_REGISTRY dict with all feature definitions
  - PackageFeatureService singleton with edition detection
  - Environment variable (ATOM_EDITION) detection
  - Package extras detection (postgresql dependency check)
  - DATABASE_URL detection for PostgreSQL
  - is_feature_enabled() for gate checking
  - require_enterprise() for permission errors
  - list_features() for feature discovery
  - Global helper functions: is_enterprise_enabled(), is_feature_enabled(), require_enterprise()

- `backend/requirements-personal.txt` (47 lines)
  - Core framework: FastAPI, uvicorn, pydantic
  - Database: SQLAlchemy with SQLite support
  - Authentication: python-jose, passlib
  - LLM providers: OpenAI, Anthropic
  - Vector embeddings: fastembed (local, no API key)
  - Enterprise dependencies excluded: PostgreSQL, Redis, monitoring, SSO

### Modified

- `backend/pyproject.toml` (140 lines, +100 lines)
  - Added [project.dependencies] with Personal Edition core deps
  - Added [project.optional-dependencies] with enterprise, dev, test, all groups
  - Enterprise extras: PostgreSQL (psycopg2-binary), Redis, monitoring (prometheus-client), SSO (authlib, pyokta), analytics (pandas, numpy), rate limiting (slowapi), cloud integrations (boto3, google-cloud-storage)
  - Development dependencies: pytest, mypy, black, ruff
  - Added [tool.setuptools.packages.find] for package discovery
  - Added [tool.setuptools.package-data] to include non-Python files

- `backend/setup.py` (169 lines, +91 lines)
  - install_requires synced with pyproject.toml dependencies (Personal Edition)
  - extras_require with enterprise, dev, test, all groups
  - Synced with pyproject.toml optional-dependencies section
  - Compatibility with older pip versions

## PackageFeatureService API

### Edition Detection

```python
from core.package_feature_service import get_package_feature_service, is_enterprise_enabled

# Get service singleton
service = get_package_feature_service()

# Check edition
service.edition  # Edition.PERSONAL or Edition.ENTERPRISE
service.is_enterprise  # bool
service.is_personal  # bool

# Quick check
is_enterprise_enabled()  # bool
```

### Feature Checking

```python
from core.package_feature_service import Feature, is_feature_enabled, require_enterprise

# Check if feature is enabled
is_feature_enabled(Feature.MULTI_USER)  # False in Personal, True in Enterprise
is_feature_enabled(Feature.LOCAL_AGENT)  # True in both

# Require feature (raises PermissionError if not available)
service.require_feature(Feature.SSO)  # Raises in Personal Edition

# Quick enterprise check
require_enterprise()  # Raises if Personal Edition
```

### Feature Discovery

```python
# List all features with availability
features = service.list_features()
# Returns: [
#   {"id": "local_agent", "name": "Local Agent", "available": True, "edition": "personal"},
#   {"id": "multi_user", "name": "Multi-User", "available": False, "edition": "enterprise"},
#   ...
# ]

# Get specific feature sets
personal_features = service.get_personal_features()  # 8 features
enterprise_features = service.get_enterprise_features()  # 10 features
```

## Edition Detection Logic

PackageFeatureService detects edition in this priority order:

1. **ATOM_EDITION environment variable**
   - `ATOM_EDITION=enterprise` → Enterprise Edition
   - `ATOM_EDITION=personal` → Personal Edition

2. **Package extras detection**
   - Checks if `psycopg2-binary` is installed (indicates enterprise extras)

3. **DATABASE_URL detection**
   - `postgresql://` in DATABASE_URL → Enterprise Edition

4. **Default**
   - Personal Edition

## Optional Dependencies Structure

### Personal Edition (default)

```bash
pip install atom-os
```

Installs: FastAPI, uvicorn, SQLAlchemy, OpenAI, Anthropic, fastembed, etc.

### Enterprise Edition

```bash
pip install atom-os[enterprise]
```

Installs Personal dependencies PLUS:
- PostgreSQL driver (psycopg2-binary)
- Redis (pub/sub for multi-user)
- Monitoring (prometheus-client)
- SSO providers (authlib, pyokta)
- Analytics (pandas, numpy)
- Rate limiting (slowapi)
- Cloud integrations (boto3, google-cloud-storage)

### Development

```bash
pip install atom-os[dev]  # Development tools
pip install atom-os[test]  # Testing tools
pip install atom-os[all]  # Everything
```

## Feature Registry

### Personal Features (8)

- `local_agent` - Run AI agents on local machine
- `workflows` - Create and run automation workflows
- `canvas` - Rich interactive presentations
- `browser_automation` - Web scraping and form filling
- `episodic_memory` - Agents remember past interactions
- `agent_governance` - Maturity levels and permissions
- `telegram_connector` - Telegram bot integration
- `community_skills` - Import 5,000+ OpenClaw/ClawHub skills

### Enterprise Features (10)

- `multi_user` - Multiple users with role-based access
- `workspace_isolation` - Separate workspaces for teams (requires multi_user)
- `sso` - Okta, Auth0, SAML authentication (requires multi_user)
- `audit_trail` - Compliance logging and reporting
- `monitoring` - Prometheus metrics and Grafana dashboards
- `advanced_analytics` - Workflow performance analytics (requires monitoring)
- `workflow_analytics` - Detailed workflow execution analytics
- `bi_dashboard` - Business intelligence and reporting (requires advanced_analytics)
- `rate_limiting` - API rate limiting and throttling
- `rbac` - Role-based access control (requires multi_user)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- PackageFeatureService ready for use in CLI commands (Plan 02)
- pyproject.toml and setup.py ready for `pip install atom-os` and `pip install atom-os[enterprise]`
- requirements-personal.txt ready for minimal Personal Edition installation
- Edition detection logic ready for CLI `atom enable enterprise` command (Plan 02)

---

*Phase: 04-installer*
*Plan: 01*
*Completed: 2026-02-16*
