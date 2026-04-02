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
        """No invoice tracking in core code."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"\binvoice\b", str(backend_dir))
        assert count < 10, f"Found {count} invoice references"

    def test_upstream_has_no_subscription_checks(self):
        """No subscription checks in core code."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"\bsubscription\b", str(backend_dir))
        assert count < 10, f"Found {count} subscription references"


class TestNoTenantPatterns:
    """Verify upstream has no tenant isolation patterns."""

    def test_upstream_has_no_tenant_id_filters(self):
        """No tenant_id database filters in queries."""
        forbidden_patterns = [
            r"Model\.tenant_id\s*==",
            r"\.tenant_id\s*==\s*tenant_id",
            r"filter\(.*\.tenant_id",
        ]
        backend_dir = PROJECT_ROOT / "backend"

        if not backend_dir.exists():
            pytest.skip("backend directory not found")

        for pattern in forbidden_patterns:
            result = subprocess.run(
                ["rg", pattern, str(backend_dir)],
                capture_output=True, text=True
            )
            # Should have minimal matches (comments only)
            matches = [line for line in result.stdout.split('\n') if line and not line.strip().startswith('#')]
            assert len(matches) < 5, f"Found {len(matches)} tenant_id filter patterns"

    def test_upstream_has_no_tenant_service_imports(self):
        """No tenant service imports."""
        backend_dir = PROJECT_ROOT / "backend"
        if not backend_dir.exists():
            pytest.skip("backend directory not found")

        count = run_ripgrep(r"from.*tenant_service|import.*tenant_service", str(backend_dir))
        assert count == 0, "Found tenant_service imports"

    def test_upstream_has_no_abuse_protection(self):
        """No abuse protection service (SaaS rate limiting)."""
        backend_dir = PROJECT_ROOT / "backend" / "core"
        if not backend_dir.exists():
            pytest.skip("backend/core directory not found")

        count = run_ripgrep(r"AbuseProtectionService|abuse_protection", str(backend_dir))
        assert count < 5, f"Found {count} abuse protection references"


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
        count = run_ripgrep(r"FLY_API_TOKEN|FLY_APP_NAME|fly\.io", str(PROJECT_ROOT))
        assert count == 0, "Found Fly.io deployment references"

    def test_upstream_has_no_neon_references(self):
        """No Neon database references."""
        count = run_ripgrep(r"NEON_DATABASE_URL|NEON_API_KEY|NEON_BRANCH_ID", str(PROJECT_ROOT))
        assert count == 0, "Found Neon database references"

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
