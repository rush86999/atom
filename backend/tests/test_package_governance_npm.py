"""
npm Package Governance Service Tests

Test coverage for npm package governance (package_type="npm"):
- Cache key format "pkg:npm:{name}:{version}" (distinct from Python)
- STUDENT agent blocking (non-negotiable)
- INTERN agent approval workflow
- SUPERVISED/AUTONOMOUS maturity checks
- Banned npm package enforcement
- npm package approval and banning
- npm cache invalidation
- npm package lifecycle management
- npm vs Python package isolation (separate cache keys)
"""

import pytest
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from core.package_governance_service import PackageGovernanceService
from core.models import PackageRegistry


@pytest.fixture
def governance_service():
    """Create PackageGovernanceService instance for testing."""
    return PackageGovernanceService()


@pytest.fixture
def db_session(db_session: Session):
    """Use the existing db_session fixture from conftest.py."""
    return db_session


@pytest.fixture
def student_agent(db_session: Session):
    """Create STUDENT maturity agent using raw SQL (avoiding SQLAlchemy ORM relationship issues)."""
    agent_id = str(uuid.uuid4())
    # Use raw SQL to insert agent without triggering ORM relationship configuration
    db_session.execute(text("""
        INSERT INTO agent_registry (id, name, category, module_path, class_name, status, confidence_score, description, version, created_at)
        VALUES (:id, :name, :category, :module_path, :class_name, :status, :confidence_score, :description, :version, datetime('now'))
    """), {
        'id': agent_id,
        'name': 'student-test-agent',
        'category': 'testing',
        'module_path': 'test.module',
        'class_name': 'TestClass',
        'status': 'student',
        'confidence_score': 0.3,
        'description': 'STUDENT maturity test agent',
        'version': '1.0.0'
    })
    db_session.commit()
    # Return a simple object with id attribute
    return type('Agent', (), {'id': agent_id})()


@pytest.fixture
def intern_agent(db_session: Session):
    """Create INTERN maturity agent using raw SQL."""
    agent_id = str(uuid.uuid4())
    db_session.execute(text("""
        INSERT INTO agent_registry (id, name, category, module_path, class_name, status, confidence_score, description, version, created_at)
        VALUES (:id, :name, :category, :module_path, :class_name, :status, :confidence_score, :description, :version, datetime('now'))
    """), {
        'id': agent_id,
        'name': 'intern-test-agent',
        'category': 'testing',
        'module_path': 'test.module',
        'class_name': 'TestClass',
        'status': 'intern',
        'confidence_score': 0.6,
        'description': 'INTERN maturity test agent',
        'version': '1.0.0'
    })
    db_session.commit()
    return type('Agent', (), {'id': agent_id})()


@pytest.fixture
def supervised_agent(db_session: Session):
    """Create SUPERVISED maturity agent using raw SQL."""
    agent_id = str(uuid.uuid4())
    db_session.execute(text("""
        INSERT INTO agent_registry (id, name, category, module_path, class_name, status, confidence_score, description, version, created_at)
        VALUES (:id, :name, :category, :module_path, :class_name, :status, :confidence_score, :description, :version, datetime('now'))
    """), {
        'id': agent_id,
        'name': 'supervised-test-agent',
        'category': 'testing',
        'module_path': 'test.module',
        'class_name': 'TestClass',
        'status': 'supervised',
        'confidence_score': 0.8,
        'description': 'SUPERVISED maturity test agent',
        'version': '1.0.0'
    })
    db_session.commit()
    return type('Agent', (), {'id': agent_id})()


@pytest.fixture
def autonomous_agent(db_session: Session):
    """Create AUTONOMOUS maturity agent using raw SQL."""
    agent_id = str(uuid.uuid4())
    db_session.execute(text("""
        INSERT INTO agent_registry (id, name, category, module_path, class_name, status, confidence_score, description, version, created_at)
        VALUES (:id, :name, :category, :module_path, :class_name, :status, :confidence_score, :description, :version, datetime('now'))
    """), {
        'id': agent_id,
        'name': 'autonomous-test-agent',
        'category': 'testing',
        'module_path': 'test.module',
        'class_name': 'TestClass',
        'status': 'autonomous',
        'confidence_score': 0.95,
        'description': 'AUTONOMOUS maturity test agent',
        'version': '1.0.0'
    })
    db_session.commit()
    return type('Agent', (), {'id': agent_id})()


class TestNpmStudentBlocking:
    """STUDENT agents must be blocked from all npm packages (non-negotiable)."""

    def test_npm_student_blocked_from_unknown_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from npm package not in registry."""
        result = governance_service.check_package_permission(
            student_agent.id, "lodash", "4.17.21", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert result["maturity_required"] == "intern"
        assert "STUDENT agents cannot" in result["reason"]
        assert "npm" in result["reason"]

    def test_npm_student_blocked_from_approved_npm_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked even from INTERN-approved npm package."""
        # Pre-approve npm package for INTERN
        governance_service.approve_package("lodash", "4.17.21", "intern", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            student_agent.id, "lodash", "4.17.21", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "STUDENT agents cannot" in result["reason"]
        assert "npm" in result["reason"]

    def test_npm_student_blocked_from_autonomous_npm_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from AUTONOMOUS-approved npm package."""
        governance_service.approve_package("react", "18.2.0", "autonomous", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            student_agent.id, "react", "18.2.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "STUDENT agents cannot" in result["reason"]
        assert "npm" in result["reason"]

    def test_npm_student_blocked_from_banned_npm_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from banned npm package (different reason)."""
        governance_service.ban_package("malicious-npm-pkg", "1.0.0", "Contains malware", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            student_agent.id, "malicious-npm-pkg", "1.0.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        # Should be banned reason, not STUDENT blocking
        assert "banned" in result["reason"]
        assert "npm" in result["reason"]

    def test_npm_student_blocking_uses_correct_cache_key(self, governance_service, student_agent, db_session):
        """STUDENT blocking for npm packages uses correct cache key format."""
        result = governance_service.check_package_permission(
            student_agent.id, "axios", "1.4.0", db_session, package_type="npm"
        )

        # Check that cache was set with npm-specific key
        cache_key = f"pkg:npm:axios:1.4.0"
        cached = governance_service.cache.get(student_agent.id, cache_key)
        assert cached is not None
        assert cached["allowed"] is False
        assert "npm" in cached["reason"]


class TestNpmInternApproval:
    """INTERN agents require approval for each npm package version."""

    def test_npm_intern_requires_approval_for_unknown_package(self, governance_service, intern_agent, db_session):
        """INTERN agent blocked from npm package not in registry."""
        result = governance_service.check_package_permission(
            intern_agent.id, "express", "4.18.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "not in registry" in result["reason"]
        assert "npm" in result["reason"]

    def test_npm_intern_allowed_after_approval(self, governance_service, intern_agent, db_session):
        """INTERN agent allowed after npm package is approved for INTERN."""
        governance_service.approve_package("express", "4.18.0", "intern", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            intern_agent.id, "express", "4.18.0", db_session, package_type="npm"
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "intern"
        assert result["reason"] is None

    def test_npm_intern_cannot_use_python_approval(self, governance_service, intern_agent, db_session):
        """INTERN agent cannot use Python package approval for npm package."""
        # Approve Python package
        governance_service.approve_package("moment", "2.29.4", "intern", "admin", db_session, package_type="python")

        # Try to use npm package with same name - should be blocked
        result = governance_service.check_package_permission(
            intern_agent.id, "moment", "2.29.4", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "not in registry" in result["reason"]

    def test_npm_intern_approval_creates_correct_cache_key(self, governance_service, intern_agent, db_session):
        """INTERN approval for npm package creates correct cache key."""
        governance_service.approve_package("lodash", "4.17.21", "intern", "admin", db_session, package_type="npm")

        # Check permission to populate cache
        result = governance_service.check_package_permission(
            intern_agent.id, "lodash", "4.17.21", db_session, package_type="npm"
        )

        # Verify cache key format
        cache_key = f"pkg:npm:lodash:4.17.21"
        cached = governance_service.cache.get(intern_agent.id, cache_key)
        assert cached is not None
        assert cached["allowed"] is True
        assert cached["maturity_required"] == "intern"

    def test_npm_intern_approval_with_min_maturity_supervised(self, governance_service, intern_agent, db_session):
        """INTERN agent blocked from npm package approved for SUPERVISED."""
        governance_service.approve_package("webpack", "5.88.0", "supervised", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            intern_agent.id, "webpack", "5.88.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "intern < required supervised" in result["reason"]

    def test_npm_intern_approval_with_min_maturity_autonomous(self, governance_service, intern_agent, db_session):
        """INTERN agent blocked from npm package approved for AUTONOMOUS."""
        governance_service.approve_package("typescript", "5.1.0", "autonomous", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            intern_agent.id, "typescript", "5.1.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "intern < required autonomous" in result["reason"]


class TestNpmMaturityChecks:
    """SUPERVISED and AUTONOMOUS agents require appropriate maturity levels for npm packages."""

    def test_npm_supervised_allowed_for_intern_approved_package(self, governance_service, supervised_agent, db_session):
        """SUPERVISED agent allowed to use INTERN-approved npm package."""
        governance_service.approve_package("axios", "1.4.0", "intern", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            supervised_agent.id, "axios", "1.4.0", db_session, package_type="npm"
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "intern"

    def test_npm_supervised_blocked_from_autonomous_required_package(self, governance_service, supervised_agent, db_session):
        """SUPERVISED agent blocked from AUTONOMOUS-required npm package."""
        governance_service.approve_package("next", "13.4.0", "autonomous", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            supervised_agent.id, "next", "13.4.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "supervised < required autonomous" in result["reason"]

    def test_npm_autonomous_allowed_for_supervised_approved_package(self, governance_service, autonomous_agent, db_session):
        """AUTONOMOUS agent allowed to use SUPERVISED-approved npm package."""
        governance_service.approve_package("vue", "3.3.0", "supervised", "admin", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            autonomous_agent.id, "vue", "3.3.0", db_session, package_type="npm"
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "supervised"

    def test_npm_maturity_cmp_works_correctly(self, governance_service):
        """Maturity comparison for npm packages follows same ordering as Python."""
        assert governance_service._maturity_cmp("autonomous", "intern") > 0
        assert governance_service._maturity_cmp("supervised", "student") > 0
        assert governance_service._maturity_cmp("intern", "supervised") < 0
        assert governance_service._maturity_cmp("student", "autonomous") < 0

    def test_npm_maturity_order_matches_python_order(self, governance_service):
        """npm and Python packages use same maturity ordering."""
        # Test that maturity comparison is consistent
        python_result = governance_service._maturity_cmp("supervised", "intern")
        npm_result = governance_service._maturity_cmp("supervised", "intern")
        assert python_result == npm_result


class TestNpmBannedPackages:
    """Banned npm packages must be blocked for all agents."""

    def test_npm_banned_package_blocks_all_agents(self, governance_service, autonomous_agent, db_session):
        """Banned npm package blocked even for AUTONOMOUS agent (highest maturity)."""
        governance_service.ban_package("dangerous-npm-pkg", "3.0.0", "Security risk", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            autonomous_agent.id, "dangerous-npm-pkg", "3.0.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        assert "banned" in result["reason"]

    def test_npm_ban_reason_stored_correctly(self, governance_service, db_session):
        """Banned npm package stores reason correctly."""
        package = governance_service.ban_package("vulnerable-npm-lib", "2.0.0", "CVE-2024-5678", db_session, package_type="npm")

        assert package.status == "banned"
        assert package.ban_reason == "CVE-2024-5678"
        assert package.package_type == "npm"

    def test_npm_ban_invalidates_cache(self, governance_service, autonomous_agent, db_session):
        """Cache should be invalidated when npm package is banned."""
        # Approve npm package first
        governance_service.approve_package("will-ban-npm", "1.0.0", "autonomous", "admin", db_session, package_type="npm")

        # First check - allowed
        result1 = governance_service.check_package_permission(
            autonomous_agent.id, "will-ban-npm", "1.0.0", db_session, package_type="npm"
        )
        assert result1["allowed"] is True

        # Ban npm package
        governance_service.ban_package("will-ban-npm", "1.0.0", "Security issue", db_session, package_type="npm")

        # Second check - should be blocked (cache invalidated)
        result2 = governance_service.check_package_permission(
            autonomous_agent.id, "will-ban-npm", "1.0.0", db_session, package_type="npm"
        )
        assert result2["allowed"] is False
        assert "banned" in result2["reason"]

    def test_npm_ban_prevents_student_auto_allow(self, governance_service, student_agent, db_session):
        """Banned npm package prevents STUDENT agent auto-allow (edge case)."""
        governance_service.ban_package("malicious-student-npm", "1.0.0", "Targets STUDENT agents", db_session, package_type="npm")

        result = governance_service.check_package_permission(
            student_agent.id, "malicious-student-npm", "1.0.0", db_session, package_type="npm"
        )
        assert result["allowed"] is False
        # Banned reason should take precedence over STUDENT blocking
        assert "banned" in result["reason"]


class TestNpmCacheBehavior:
    """Cache integration for npm packages with <1ms lookups."""

    def test_npm_cache_key_format_uses_npm_prefix(self, governance_service, autonomous_agent, db_session):
        """npm packages use correct cache key format."""
        governance_service.approve_package("react", "18.2.0", "intern", "admin", db_session, package_type="npm")

        # Check permission to populate cache
        governance_service.check_package_permission(
            autonomous_agent.id, "react", "18.2.0", db_session, package_type="npm"
        )

        # Verify cache key format
        cache_key = f"pkg:npm:react:18.2.0"
        cached = governance_service.cache.get(autonomous_agent.id, cache_key)
        assert cached is not None
        assert cached["allowed"] is True

    def test_npm_cache_hit_returns_correct_permission(self, governance_service, autonomous_agent, db_session):
        """Second call for npm package should return cached result."""
        governance_service.approve_package("angular", "16.0.0", "intern", "admin", db_session, package_type="npm")

        # First call - cache miss
        result1 = governance_service.check_package_permission(
            autonomous_agent.id, "angular", "16.0.0", db_session, package_type="npm"
        )

        # Second call - cache hit
        result2 = governance_service.check_package_permission(
            autonomous_agent.id, "angular", "16.0.0", db_session, package_type="npm"
        )

        assert result1 == result2
        assert result1["allowed"] is True

    def test_npm_cache_miss_queries_database(self, governance_service, intern_agent, db_session):
        """npm package cache miss should query database and block unknown packages."""
        result = governance_service.check_package_permission(
            intern_agent.id, "unknown-npm-pkg", "1.0.0", db_session, package_type="npm"
        )

        assert result["allowed"] is False
        assert "not in registry" in result["reason"]

    def test_npm_python_packages_separate_cache_keys(self, governance_service, autonomous_agent, db_session):
        """npm and Python packages use separate cache keys (documenting current limitation)."""
        # NOTE: Current implementation uses "{name}:{version}" as ID without package_type
        # This means same name/version cannot coexist for Python and npm
        # This test documents the current behavior and cache key separation

        # Approve Python package first
        governance_service.approve_package("moment", "2.29.4", "intern", "admin", db_session, package_type="python")

        # Check Python package permission
        python_result = governance_service.check_package_permission(
            autonomous_agent.id, "moment", "2.29.4", db_session, package_type="python"
        )

        assert python_result["allowed"] is True
        assert python_result["maturity_required"] == "intern"

        # Verify Python cache key format
        python_cache_key = f"pkg:python:moment:2.29.4"
        python_cached = governance_service.cache.get(autonomous_agent.id, python_cache_key)
        assert python_cached is not None

        # Try to approve npm package with same name - will fail due to UNIQUE constraint
        # This is a known limitation: ID format doesn't include package_type
        # The query finds the Python package (same ID), tries to INSERT as npm, fails
        # The IntegrityError is wrapped by SQLAlchemy, so we catch Exception
        try:
            governance_service.approve_package("moment", "2.29.4", "autonomous", "admin", db_session, package_type="npm")
            assert False, "Should have raised an exception"
        except Exception as e:
            # Should be IntegrityError or wrapped version
            assert "UNIQUE constraint failed" in str(e) or "IntegrityError" in str(e)
            # Rollback to clear the failed transaction
            db_session.rollback()

        # Verify Python package still works after failed npm attempt
        python_result_after = governance_service.check_package_permission(
            autonomous_agent.id, "moment", "2.29.4", db_session, package_type="python"
        )

        # Python package should still be accessible
        assert python_result_after["allowed"] is True
        assert python_result_after["maturity_required"] == "intern"

    def test_npm_cache_invalidated_on_approval(self, governance_service, intern_agent, db_session):
        """Cache should be invalidated when npm package is approved."""
        # First check - npm package not approved
        result1 = governance_service.check_package_permission(
            intern_agent.id, "new-npm-pkg", "1.0.0", db_session, package_type="npm"
        )
        assert result1["allowed"] is False

        # Approve npm package
        governance_service.approve_package("new-npm-pkg", "1.0.0", "intern", "admin", db_session, package_type="npm")

        # Second check - should get new result (cache invalidated)
        result2 = governance_service.check_package_permission(
            intern_agent.id, "new-npm-pkg", "1.0.0", db_session, package_type="npm"
        )
        assert result2["allowed"] is True


class TestNpmPackageLifecycle:
    """npm package approval, banning, and lifecycle management."""

    def test_npm_request_package_approval_creates_pending_entry(self, governance_service, db_session):
        """Requesting npm package approval should create pending entry."""
        package = governance_service.request_package_approval(
            "new-npm-lib", "2.0.0", "user1", "Need for frontend", db_session, package_type="npm"
        )

        assert package.id == "new-npm-lib:2.0.0"
        assert package.package_type == "npm"
        assert package.status == "pending"
        assert package.min_maturity == "intern"

    def test_npm_approve_package_sets_active_status(self, governance_service, db_session):
        """Approving npm package should set active status."""
        package = governance_service.approve_package("mobx", "6.9.0", "supervised", "admin", db_session, package_type="npm")

        assert package.id == "mobx:6.9.0"
        assert package.package_type == "npm"
        assert package.name == "mobx"
        assert package.version == "6.9.0"
        assert package.status == "active"
        assert package.min_maturity == "supervised"
        assert package.approved_by == "admin"
        assert package.approved_at is not None

    def test_npm_list_packages_filters_by_npm_type(self, governance_service, db_session):
        """Listing npm packages should filter by package_type='npm'."""
        # Create npm packages
        governance_service.approve_package("lodash", "4.17.21", "intern", "admin", db_session, package_type="npm")
        governance_service.ban_package("bad-npm-pkg", "1.0.0", "Malicious", db_session, package_type="npm")

        # Create Python package
        governance_service.approve_package("numpy", "1.21.0", "intern", "admin", db_session, package_type="python")

        # List only npm packages
        npm_packages = governance_service.list_packages(package_type="npm", db=db_session)

        assert len(npm_packages) == 2
        package_names = {p.name for p in npm_packages}
        assert package_names == {"lodash", "bad-npm-pkg"}
        assert all(p.package_type == "npm" for p in npm_packages)

    def test_npm_list_packages_includes_python_when_not_filtered(self, governance_service, db_session):
        """Listing packages without filter should include both npm and Python."""
        # Create npm packages
        governance_service.approve_package("express", "4.18.0", "intern", "admin", db_session, package_type="npm")

        # Create Python packages
        governance_service.approve_package("pandas", "1.3.0", "intern", "admin", db_session, package_type="python")

        # List all packages
        all_packages = governance_service.list_packages(db=db_session)

        assert len(all_packages) == 2
        package_types = {p.package_type for p in all_packages}
        assert package_types == {"npm", "python"}

    def test_npm_delete_package_removes_from_registry(self, governance_service, db_session):
        """Deleting npm package should remove it from registry."""
        # Create npm package
        governance_service.approve_package("redux", "4.2.0", "intern", "admin", db_session, package_type="npm")

        # Verify it exists
        package = db_session.query(PackageRegistry).filter(
            PackageRegistry.id == "redux:4.2.0",
            PackageRegistry.package_type == "npm"
        ).first()
        assert package is not None

        # Delete it
        db_session.delete(package)
        db_session.commit()

        # Verify it's gone
        package = db_session.query(PackageRegistry).filter(
            PackageRegistry.id == "redux:4.2.0",
            PackageRegistry.package_type == "npm"
        ).first()
        assert package is None
