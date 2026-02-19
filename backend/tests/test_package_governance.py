"""
Package Governance Service Tests

Test coverage:
- Cache hit/miss behavior
- STUDENT agent blocking (non-negotiable)
- INTERN agent approval workflow
- SUPERVISED/AUTONOMOUS maturity checks
- Banned package enforcement
- Package approval and banning
- Maturity comparison logic
- API endpoint validation
- Cache statistics tracking
- Package lifecycle management
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from core.package_governance_service import PackageGovernanceService
from core.models import PackageRegistry, AgentRegistry, AgentStatus
from tests.factories.agent_factory import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)


@pytest.fixture
def governance_service():
    """Create PackageGovernanceService instance for testing."""
    return PackageGovernanceService()


@pytest.fixture
def student_agent(db_session: Session):
    """Create STUDENT maturity agent."""
    agent = StudentAgentFactory(_session=db_session)
    db_session.commit()
    return agent


@pytest.fixture
def intern_agent(db_session: Session):
    """Create INTERN maturity agent."""
    agent = InternAgentFactory(_session=db_session)
    db_session.commit()
    return agent


@pytest.fixture
def supervised_agent(db_session: Session):
    """Create SUPERVISED maturity agent."""
    agent = SupervisedAgentFactory(_session=db_session)
    db_session.commit()
    return agent


@pytest.fixture
def autonomous_agent(db_session: Session):
    """Create AUTONOMOUS maturity agent."""
    agent = AutonomousAgentFactory(_session=db_session)
    db_session.commit()
    return agent


class TestStudentBlocking:
    """STUDENT agents must be blocked from all Python packages (non-negotiable)."""

    def test_student_blocked_from_unknown_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from package not in registry."""
        result = governance_service.check_package_permission(
            student_agent.id, "numpy", "1.21.0", db_session
        )
        assert result["allowed"] is False
        assert result["maturity_required"] == "intern"
        assert "STUDENT agents cannot" in result["reason"]

    def test_student_blocked_from_approved_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked even from INTERN-approved package."""
        # Pre-approve package for INTERN
        governance_service.approve_package("numpy", "1.21.0", "intern", "admin", db_session)

        result = governance_service.check_package_permission(
            student_agent.id, "numpy", "1.21.0", db_session
        )
        assert result["allowed"] is False
        assert "STUDENT agents cannot" in result["reason"]

    def test_student_blocked_from_autonomous_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from AUTONOMOUS-approved package."""
        governance_service.approve_package("tensorflow", "2.8.0", "autonomous", "admin", db_session)

        result = governance_service.check_package_permission(
            student_agent.id, "tensorflow", "2.8.0", db_session
        )
        assert result["allowed"] is False
        assert "STUDENT agents cannot" in result["reason"]

    def test_student_blocked_from_banned_package(self, governance_service, student_agent, db_session):
        """STUDENT agent blocked from banned package (different reason)."""
        governance_service.ban_package("malicious-pkg", "1.0.0", "Contains malware", db_session)

        result = governance_service.check_package_permission(
            student_agent.id, "malicious-pkg", "1.0.0", db_session
        )
        assert result["allowed"] is False
        # Should be banned reason, not STUDENT blocking
        assert "banned" in result["reason"]


class TestInternApproval:
    """INTERN agents require approval for each package version."""

    def test_intern_blocked_from_unknown_package(self, governance_service, intern_agent, db_session):
        """INTERN agent blocked from package not in registry."""
        result = governance_service.check_package_permission(
            intern_agent.id, "pandas", "1.3.0", db_session
        )
        assert result["allowed"] is False
        assert "not in registry" in result["reason"]

    def test_intern_allowed_after_approval(self, governance_service, intern_agent, db_session):
        """INTERN agent allowed after package is approved for INTERN."""
        governance_service.approve_package("pandas", "1.3.0", "intern", "admin", db_session)

        result = governance_service.check_package_permission(
            intern_agent.id, "pandas", "1.3.0", db_session
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "intern"
        assert result["reason"] is None

    def test_intern_blocked_from_supervised_package(self, governance_service, intern_agent, db_session):
        """INTERN agent blocked from SUPERVISED-required package."""
        governance_service.approve_package("scipy", "1.7.0", "supervised", "admin", db_session)

        result = governance_service.check_package_permission(
            intern_agent.id, "scipy", "1.7.0", db_session
        )
        assert result["allowed"] is False
        assert "intern < required supervised" in result["reason"]


class TestMaturityGating:
    """SUPERVISED and AUTONOMOUS agents require appropriate maturity levels."""

    def test_supervised_allowed_intern_package(self, governance_service, supervised_agent, db_session):
        """SUPERVISED agent allowed to use INTERN-approved package."""
        governance_service.approve_package("requests", "2.28.0", "intern", "admin", db_session)

        result = governance_service.check_package_permission(
            supervised_agent.id, "requests", "2.28.0", db_session
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "intern"

    def test_supervised_allowed_supervised_package(self, governance_service, supervised_agent, db_session):
        """SUPERVISED agent allowed to use SUPERVISED-approved package."""
        governance_service.approve_package("matplotlib", "3.5.0", "supervised", "admin", db_session)

        result = governance_service.check_package_permission(
            supervised_agent.id, "matplotlib", "3.5.0", db_session
        )
        assert result["allowed"] is True
        assert result["maturity_required"] == "supervised"

    def test_supervised_blocked_from_autonomous_package(self, governance_service, supervised_agent, db_session):
        """SUPERVISED agent blocked from AUTONOMOUS-required package."""
        governance_service.approve_package("tensorflow", "2.8.0", "autonomous", "admin", db_session)

        result = governance_service.check_package_permission(
            supervised_agent.id, "tensorflow", "2.8.0", db_session
        )
        assert result["allowed"] is False
        assert "supervised < required autonomous" in result["reason"]

    def test_autonomous_allowed_all_levels(self, governance_service, autonomous_agent, db_session):
        """AUTONOMOUS agent allowed to use packages at all maturity levels."""
        governance_service.approve_package("requests", "2.28.0", "intern", "admin", db_session)
        governance_service.approve_package("scipy", "1.7.0", "supervised", "admin", db_session)
        governance_service.approve_package("tensorflow", "2.8.0", "autonomous", "admin", db_session)

        for pkg, version in [("requests", "2.28.0"), ("scipy", "1.7.0"), ("tensorflow", "2.8.0")]:
            result = governance_service.check_package_permission(
                autonomous_agent.id, pkg, version, db_session
            )
            assert result["allowed"] is True, f"AUTONOMOUS should be allowed {pkg}@{version}"


class TestBannedPackages:
    """Banned packages must be blocked for all agents."""

    def test_banned_package_blocked_for_student(self, governance_service, student_agent, db_session):
        """Banned package blocked for STUDENT agent."""
        governance_service.ban_package("malicious-pkg", "1.0.0", "Contains malware", db_session)

        result = governance_service.check_package_permission(
            student_agent.id, "malicious-pkg", "1.0.0", db_session
        )
        assert result["allowed"] is False
        assert "banned" in result["reason"]

    def test_banned_package_blocked_for_intern(self, governance_service, intern_agent, db_session):
        """Banned package blocked for INTERN agent."""
        governance_service.ban_package("vulnerable-lib", "2.0.0", "CVE-2024-1234", db_session)

        result = governance_service.check_package_permission(
            intern_agent.id, "vulnerable-lib", "2.0.0", db_session
        )
        assert result["allowed"] is False
        assert "banned" in result["reason"]

    def test_banned_package_blocked_for_supervised(self, governance_service, supervised_agent, db_session):
        """Banned package blocked for SUPERVISED agent."""
        governance_service.ban_package("bad-pkg", "1.5.0", "Policy violation", db_session)

        result = governance_service.check_package_permission(
            supervised_agent.id, "bad-pkg", "1.5.0", db_session
        )
        assert result["allowed"] is False
        assert "banned" in result["reason"]

    def test_banned_package_blocked_for_autonomous(self, governance_service, autonomous_agent, db_session):
        """Banned package blocked for AUTONOMOUS agent (highest maturity)."""
        governance_service.ban_package("dangerous-pkg", "3.0.0", "Security risk", db_session)

        result = governance_service.check_package_permission(
            autonomous_agent.id, "dangerous-pkg", "3.0.0", db_session
        )
        assert result["allowed"] is False
        assert "banned" in result["reason"]


class TestCacheBehavior:
    """Cache integration for <1ms lookups."""

    def test_cache_hit_returns_same_result(self, governance_service, autonomous_agent, db_session):
        """Second call should return cached result (same data)."""
        governance_service.approve_package("requests", "2.28.0", "intern", "admin", db_session)

        # First call - cache miss
        result1 = governance_service.check_package_permission(
            autonomous_agent.id, "requests", "2.28.0", db_session
        )

        # Second call - cache hit
        result2 = governance_service.check_package_permission(
            autonomous_agent.id, "requests", "2.28.0", db_session
        )

        assert result1 == result2

    def test_cache_invalidation_on_approval(self, governance_service, intern_agent, db_session):
        """Cache should be invalidated when package is approved."""
        # First check - package not approved
        result1 = governance_service.check_package_permission(
            intern_agent.id, "new-package", "1.0.0", db_session
        )
        assert result1["allowed"] is False

        # Approve package
        governance_service.approve_package("new-package", "1.0.0", "intern", "admin", db_session)

        # Second check - should get new result (cache invalidated)
        result2 = governance_service.check_package_permission(
            intern_agent.id, "new-package", "1.0.0", db_session
        )
        assert result2["allowed"] is True

    def test_cache_invalidation_on_ban(self, governance_service, autonomous_agent, db_session):
        """Cache should be invalidated when package is banned."""
        # Approve package first
        governance_service.approve_package("will-ban", "1.0.0", "autonomous", "admin", db_session)

        # First check - allowed
        result1 = governance_service.check_package_permission(
            autonomous_agent.id, "will-ban", "1.0.0", db_session
        )
        assert result1["allowed"] is True

        # Ban package
        governance_service.ban_package("will-ban", "1.0.0", "Security issue", db_session)

        # Second check - should be blocked (cache invalidated)
        result2 = governance_service.check_package_permission(
            autonomous_agent.id, "will-ban", "1.0.0", db_session
        )
        assert result2["allowed"] is False

    def test_cache_stats_accessible(self, governance_service):
        """Cache statistics should be accessible."""
        stats = governance_service.get_cache_stats()
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats


class TestPackageLifecycle:
    """Package approval, banning, and lifecycle management."""

    def test_approve_package_creates_registry_entry(self, governance_service, db_session):
        """Approving package should create registry entry."""
        package = governance_service.approve_package("scipy", "1.7.0", "supervised", "admin", db_session)

        assert package.id == "scipy:1.7.0"
        assert package.name == "scipy"
        assert package.version == "1.7.0"
        assert package.status == "active"
        assert package.min_maturity == "supervised"
        assert package.approved_by == "admin"
        assert package.approved_at is not None

    def test_approve_package_updates_existing_entry(self, governance_service, db_session):
        """Approving existing package should update it."""
        # Create initial entry
        governance_service.request_package_approval("numpy", "1.21.0", "user1", "Need it", db_session)

        # Approve it
        package = governance_service.approve_package("numpy", "1.21.0", "intern", "admin", db_session)

        assert package.status == "active"
        assert package.min_maturity == "intern"
        assert package.approved_by == "admin"

    def test_ban_package_updates_status(self, governance_service, db_session):
        """Banning package should update status and reason."""
        # Approve first
        governance_service.approve_package("bad-pkg", "1.0.0", "intern", "admin", db_session)

        # Ban it
        package = governance_service.ban_package("bad-pkg", "1.0.0", "Security issue", db_session)

        assert package.status == "banned"
        assert package.ban_reason == "Security issue"

    def test_request_package_approval_creates_pending_entry(self, governance_service, db_session):
        """Requesting approval should create pending entry."""
        package = governance_service.request_package_approval(
            "new-lib", "2.0.0", "user1", "Need for data processing", db_session
        )

        assert package.id == "new-lib:2.0.0"
        assert package.status == "pending"
        assert package.min_maturity == "intern"

    def test_list_packages_returns_all(self, governance_service, db_session):
        """Listing packages should return all packages."""
        # Create packages with different statuses
        governance_service.approve_package("pkg1", "1.0.0", "intern", "admin", db_session)
        governance_service.ban_package("pkg2", "1.0.0", "Bad", db_session)
        governance_service.request_package_approval("pkg3", "1.0.0", "user", "Need it", db_session)

        packages = governance_service.list_packages(db=db_session)

        assert len(packages) == 3
        package_names = {p.name for p in packages}
        assert package_names == {"pkg1", "pkg2", "pkg3"}

    def test_list_packages_filters_by_status(self, governance_service, db_session):
        """Listing packages should filter by status."""
        governance_service.approve_package("pkg1", "1.0.0", "intern", "admin", db_session)
        governance_service.ban_package("pkg2", "1.0.0", "Bad", db_session)

        active_packages = governance_service.list_packages(status="active", db=db_session)
        banned_packages = governance_service.list_packages(status="banned", db=db_session)

        assert len(active_packages) == 1
        assert active_packages[0].name == "pkg1"

        assert len(banned_packages) == 1
        assert banned_packages[0].name == "pkg2"


class TestMaturityComparison:
    """Maturity level comparison logic."""

    def test_maturity_cmp_ordering(self, governance_service):
        """Maturity comparison should follow student < intern < supervised < autonomous."""
        assert governance_service._maturity_cmp("autonomous", "intern") > 0
        assert governance_service._maturity_cmp("supervised", "student") > 0
        assert governance_service._maturity_cmp("intern", "supervised") < 0
        assert governance_service._maturity_cmp("student", "autonomous") < 0

    def test_maturity_cmp_equal(self, governance_service):
        """Same maturity levels should return 0."""
        assert governance_service._maturity_cmp("intern", "intern") == 0
        assert governance_service._maturity_cmp("autonomous", "autonomous") == 0

    def test_invalid_maturity_level_raises_error(self, governance_service, db_session):
        """Approving package with invalid maturity should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid maturity level"):
            governance_service.approve_package("pkg", "1.0.0", "Linvalid_level", "admin", db_session)


class TestPendingPackages:
    """Pending approval package behavior."""

    def test_pending_package_blocked_for_all(self, governance_service, autonomous_agent, db_session):
        """Pending packages should be blocked even for AUTONOMOUS agents."""
        governance_service.request_package_approval("pending-pkg", "1.0.0", "user", "Need it", db_session)

        result = governance_service.check_package_permission(
            autonomous_agent.id, "pending-pkg", "1.0.0", db_session
        )

        assert result["allowed"] is False
        assert "pending approval" in result["reason"]


class TestPackageNotFound:
    """Package not in registry (untrusted) behavior."""

    def test_unknown_package_blocked_for_all_maturities(self, governance_service, db_session):
        """Unknown packages should be blocked for all agents."""
        agents = [
            StudentAgentFactory(_session=db_session),
            InternAgentFactory(_session=db_session),
            SupervisedAgentFactory(_session=db_session),
            AutonomousAgentFactory(_session=db_session),
        ]
        db_session.commit()

        for agent in agents:
            result = governance_service.check_package_permission(
                agent.id, "unknown-package", "1.0.0", db_session
            )
            assert result["allowed"] is False
            # STUDENT agents get "STUDENT agents cannot" reason, others get "not in registry"
            assert "not in registry" in result["reason"] or "STUDENT agents cannot" in result["reason"]


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_different_versions_separate_entries(self, governance_service, autonomous_agent, db_session):
        """Different versions of same package should have separate entries."""
        governance_service.approve_package("numpy", "1.21.0", "intern", "admin", db_session)
        governance_service.ban_package("numpy", "1.20.0", "Old version has bug", db_session)

        # Should be allowed for 1.21.0
        result1 = governance_service.check_package_permission(
            autonomous_agent.id, "numpy", "1.21.0", db_session
        )
        assert result1["allowed"] is True

        # Should be banned for 1.20.0
        result2 = governance_service.check_package_permission(
            autonomous_agent.id, "numpy", "1.20.0", db_session
        )
        assert result2["allowed"] is False

    def test_agent_not_found_defaults_to_student(self, governance_service, db_session):
        """Non-existent agent should default to STUDENT (blocked)."""
        result = governance_service.check_package_permission(
            "non-existent-agent-id", "numpy", "1.21.0", db_session
        )
        assert result["allowed"] is False
        assert result["maturity_required"] == "intern"
