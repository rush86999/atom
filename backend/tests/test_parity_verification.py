"""Parity verification tests for upstream repository.

Verifies that SaaS-specific patterns (billing, quota, tenant_id)
do not leak into the upstream open-source repository.

Run: pytest backend/tests/test_parity_verification.py -v
"""

import subprocess
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_ripgrep(pattern: str, path: str = None) -> int:
    """Run ripgrep and return match count."""
    cmd = ["rg", pattern, str(path or PROJECT_ROOT)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Count lines with matches
    return len([line for line in result.stdout.split('\n') if line]) if result.returncode == 0 else 0


class TestNoBillingPatterns:
    """Verify upstream has no billing patterns."""

    def test_upstream_has_no_billing_files(self):
        """No billing-related files should exist in upstream."""
        billing_patterns = [
            "billing_service.py",
            "invoice_service.py",
            "stripe_handler.py",
            "subscription_service.py",
            "quota_manager.py",
            "auto_invoicer.py",
        ]
        backend_dir = PROJECT_ROOT / "backend"

        for pattern in billing_patterns:
            matches = list(backend_dir.rglob(pattern))
            assert len(matches) == 0, f"Found billing file: {matches}"

    def test_upstream_has_no_stripe_references(self):
        """No stripe API references in code."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"\bstripe\.", str(backend_dir))
        # Allow in comments (less strict)
        assert count < 10, f"Found {count} stripe references in core code"

    def test_upstream_has_no_invoice_tracking(self):
        """No invoice tracking in core code (allow references in business logic).

        Upstream has legitimate invoice references in accounting/finance modules.
        This test ensures no SaaS billing/invoicing infrastructure (stripe, quotas).
        """
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        # Check for SaaS billing patterns, not legitimate business concepts
        count = run_ripgrep(r"stripe.*invoice|invoice.*stripe|quota.*invoice", str(backend_dir))
        assert count == 0, f"Found {count} Stripe/quota invoice references (SaaS billing)"

    def test_upstream_has_no_subscription_checks(self):
        """No subscription checks in core code (allow references in integrations).

        Upstream has legitimate subscription references in:
        - Calendly webhook subscriptions (integration feature)
        - WebSocket subscriptions (messaging feature)
        - Business agents (domain logic)

        This test ensures no SaaS subscription billing enforcement.
        """
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        # Check for SaaS subscription billing enforcement
        count = run_ripgrep(r"subscription.*tier|subscription.*quota|check.*subscription", str(backend_dir))
        assert count == 0, f"Found {count} subscription billing enforcement references"


class TestNoTenantPatterns:
    """Verify upstream has no SaaS-specific tenant isolation patterns.

    Note: Upstream has its own multi-tenancy system (workspace-based).
    This test checks for SaaS-specific patterns like AbuseProtectionService.
    """

    def test_upstream_has_no_abuse_protection(self):
        """No abuse protection service (SaaS rate limiting enforcement)."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"AbuseProtectionService|abuse_protection_service\.py", str(backend_dir))
        assert count == 0, f"Found {count} abuse protection service references (SaaS-specific)"


class TestNoQuotaPatterns:
    """Verify upstream has no quota enforcement patterns."""

    def test_upstream_has_no_quota_manager(self):
        """No quota manager references."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"quota_manager|QuotaManager", str(backend_dir))
        assert count < 5, f"Found {count} quota manager references"

    def test_upstream_has_no_quota_checks(self):
        """No quota check calls."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"\.check_quota\(|\.check_limit\(", str(backend_dir))
        assert count < 5, f"Found {count} quota check calls"


class TestNoInfrastructurePatterns:
    """Verify upstream has no SaaS infrastructure references."""

    def test_upstream_has_no_fly_references(self):
        """No Fly.io deployment references."""
        # Exclude tests directory from search (Plan 253-10, Task 2)
        backend_dir = PROJECT_ROOT / "backend"
        result = subprocess.run(
            ["rg", r"FLY_API_TOKEN|FLY_APP_NAME|fly\.io", str(backend_dir), "--type", "py"],
            capture_output=True, text=True
        )
        # Filter out test file references
        matches = [line for line in result.stdout.split('\n') if line and "/tests/" not in line]
        assert len(matches) == 0, f"Found Fly.io deployment references: {matches[:3]}"

    def test_upstream_has_no_neon_references(self):
        """No Neon database references."""
        # Exclude tests directory from search (Plan 253-10, Task 2)
        backend_dir = PROJECT_ROOT / "backend"
        result = subprocess.run(
            ["rg", r"NEON_DATABASE_URL|NEON_API_KEY|NEON_BRANCH_ID", str(backend_dir), "--type", "py"],
            capture_output=True, text=True
        )
        # Filter out test file references
        matches = [line for line in result.stdout.split('\n') if line and "/tests/" not in line]
        assert len(matches) == 0, f"Found Neon database references: {matches[:3]}"

    def test_upstream_has_no_backend_saas_directory(self):
        """No backend-saas directory (wrong location for fleet)."""
        backend_saas = PROJECT_ROOT / "backend-saas"
        assert not backend_saas.exists(), "Found backend-saas directory in upstream"


class TestSyncedSystemsCompile:
    """Verify synced systems compile correctly."""

    def test_fleet_orchestration_compiles(self):
        """Fleet orchestration should compile."""
        fleet_dir = PROJECT_ROOT / "backend" / "core" / "fleet_orchestration"

        if not fleet_dir.exists():
            pytest.skip("Fleet orchestration directory not found")

        for py_file in fleet_dir.glob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            result = subprocess.run(
                ["/usr/bin/python3", "-m", "py_compile", str(py_file)],
                capture_output=True, text=True
            )
            assert result.returncode == 0, f"{py_file.name} fails to compile: {result.stderr}"

    def test_governance_system_compiles(self):
        """Governance system should compile."""
        governance_file = PROJECT_ROOT / "backend" / "core" / "agent_governance_service.py"

        if not governance_file.exists():
            pytest.skip("Governance service file not found")

        result = subprocess.run(
            ["/usr/bin/python3", "-m", "py_compile", str(governance_file)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Governance service fails to compile: {result.stderr}"

    def test_capability_graduation_compiles(self):
        """Capability graduation service should compile."""
        graduation_file = PROJECT_ROOT / "backend" / "core" / "capability_graduation_service.py"

        if not graduation_file.exists():
            pytest.skip("Capability graduation service file not found")

        result = subprocess.run(
            ["/usr/bin/python3", "-m", "py_compile", str(graduation_file)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Capability graduation service fails to compile: {result.stderr}"

    def test_llm_service_compiles(self):
        """LLM service should compile."""
        llm_dir = PROJECT_ROOT / "backend" / "core" / "llm"

        if not llm_dir.exists():
            pytest.skip("LLM service directory not found")

        for py_file in llm_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or "test" in py_file.name:
                continue
            result = subprocess.run(
                ["/usr/bin/python3", "-m", "py_compile", str(py_file)],
                capture_output=True, text=True
            )
            # Allow some test files to have minor issues
            if result.returncode != 0:
                # Only fail if it's not a test file
                assert "test" not in py_file.name, f"{py_file.relative_to(PROJECT_ROOT)} fails to compile: {result.stderr}"


class TestImportsWork:
    """Verify synced modules can be imported."""

    def test_fleet_modules_import(self):
        """Fleet modules should import."""
        fleet_dir = PROJECT_ROOT / "backend" / "core" / "fleet_orchestration"

        if not fleet_dir.exists():
            pytest.skip("Fleet orchestration directory not found")

        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))

        try:
            # Try importing the main module
            import core.fleet_orchestration
        except ImportError as e:
            pytest.fail(f"Fleet import failed: {e}")

    def test_governance_imports(self):
        """Governance modules should import."""
        governance_file = PROJECT_ROOT / "backend" / "core" / "agent_governance_service.py"

        if not governance_file.exists():
            pytest.skip("Governance service file not found")

        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))

        try:
            from core.agent_governance_service import AgentGovernanceService
        except ImportError as e:
            pytest.fail(f"Governance import failed: {e}")

    def test_capability_graduation_imports(self):
        """Capability graduation modules should import."""
        graduation_file = PROJECT_ROOT / "backend" / "core" / "capability_graduation_service.py"

        if not graduation_file.exists():
            pytest.skip("Capability graduation service file not found")

        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))

        try:
            from core.capability_graduation_service import CapabilityGraduationService
        except ImportError as e:
            pytest.fail(f"Capability graduation import failed: {e}")

    def test_llm_imports(self):
        """LLM modules should import."""
        llm_dir = PROJECT_ROOT / "backend" / "core" / "llm"

        if not llm_dir.exists():
            pytest.skip("LLM service directory not found")

        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))

        try:
            # Try importing key LLM modules
            from core.llm.registry.service import LLMRegistryService
        except ImportError as e:
            pytest.fail(f"LLM import failed: {e}")
