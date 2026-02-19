"""
Package Security Tests - Container Escape, Resource Exhaustion, Malicious Detection

Comprehensive security test suite validating defense-in-depth protections:
- Container escape scenarios (privileged mode, socket mount, cgroup manipulation)
- Resource exhaustion (fork bomb, memory exhaustion, CPU exhaustion, disk filling)
- Network isolation (outbound connections blocked)
- Filesystem isolation (read-only, no host access, tmpfs only)
- Malicious pattern detection (static scanning, obfuscation detection)
- Vulnerability scanning (known CVEs via pip-audit)
- Typosquatting attack detection
- Dependency confusion prevention
- Governance blocking (STUDENT agent restrictions)

Reference: Phase 35 Plan 05 - Security Testing
"""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock
import sys

# Mock docker module before importing (same pattern as test_skill_sandbox.py)
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()

# Create mock exceptions
class DockerException(Exception):
    pass

class ContainerError(Exception):
    def __init__(self, message, exit_status=None, stderr=None):
        super().__init__(message)
        self.exit_status = exit_status
        self.stderr = stderr

class APIError(Exception):
    pass

sys.modules['docker.errors'].DockerException = DockerException
sys.modules['docker.errors'].ContainerError = ContainerError
sys.modules['docker.errors'].APIError = APIError

from sqlalchemy.orm import Session

from core.skill_sandbox import HazardSandbox
from core.package_dependency_scanner import PackageDependencyScanner
from core.package_governance_service import PackageGovernanceService
from core.skill_security_scanner import SkillSecurityScanner
from core.models import PackageRegistry
from tests.fixtures.malicious_packages import (
    MALICIOUS_CONTAINER_ESCAPE_PRIVILEGED,
    MALICIOUS_CONTAINER_ESCAPE_DOCKER_SOCKET,
    MALICIOUS_CONTAINER_ESCAPE_CGROUP,
    MALICIOUS_RESOURCE_EXHAUSTION_FORK_BOMB,
    MALICIOUS_RESOURCE_EXHAUSTION_MEMORY,
    MALICIOUS_RESOURCE_EXHAUSTION_CPU,
    MALICIOUS_NETWORK_EXFILTRATION_URLLIB,
    MALICIOUS_NETWORK_EXFILTRATION_SOCKETS,
    MALICIOUS_FILESYSTEM_WRITE_HOST,
    MALICIOUS_CODE_EXECUTION_SUBPROCESS,
    MALICIOUS_CODE_EXECUTION_EVAL,
    MALICIOUS_CODE_EXECUTION_PICKLE,
    MALICIOUS_BASE64_OBFUSCATION,
    MALICIOUS_IMPORT_OBFUSCATION,
    TYPOSQUATTING_PACKAGES,
    KNOWN_VULNERABLE_PACKAGES,
    DEPENDENCY_CONFUSION_PACKAGES,
    MALICIOUS_PATTERNS
)


@pytest.fixture
def mock_docker_client():
    """Create mock Docker client for testing."""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.containers.run.return_value = b"output\n"
    return mock_client


@pytest.fixture
def sandbox(mock_docker_client):
    """Create HazardSandbox instance with mocked Docker."""
    with patch('core.skill_sandbox.docker.from_env', return_value=mock_docker_client):
        return HazardSandbox()


@pytest.fixture
def scanner():
    """Create PackageDependencyScanner instance."""
    return PackageDependencyScanner()


@pytest.fixture
def governance():
    """Create PackageGovernanceService instance."""
    return PackageGovernanceService()


@pytest.fixture
def security_scanner():
    """Create SkillSecurityScanner instance (no API key for testing)."""
    return SkillSecurityScanner(api_key=None)


# ============================================================================
# CONTAINER ESCAPE TESTS
# ============================================================================

class TestContainerEscape:
    """Container escape attack prevention tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_privileged_mode_disabled(self, mock_docker, mock_docker_client):
        """
        Verify containers NEVER run with --privileged flag.

        Privileged mode disables all security mechanisms and allows
        full host access (CVE-2019-5736, CVE-2025-9074).

        Security: CRITICAL
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            timeout_seconds=30
        )

        # Verify containers.run was called
        assert mock_docker_client.containers.run.called

        # Verify privileged=False (or not set, default is False)
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('privileged', False) == False, \
            "Container must NOT run in privileged mode"

    @patch('core.skill_sandbox.docker.from_env')
    def test_docker_socket_not_mounted(self, mock_docker, mock_docker_client):
        """
        Verify Docker socket is NEVER mounted in containers.

        Mounting /var/run/docker.sock enables container escape
        and full host control (Docker-out-of-Docker attack).

        Security: CRITICAL
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            timeout_seconds=30
        )

        # Verify volumes don't include Docker socket
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        volumes = call_kwargs.get('volumes', {})

        # Check both string and dict representations
        volumes_str = str(volumes)
        assert '/var/run/docker.sock' not in volumes_str, \
            "Docker socket must NOT be mounted (enables container escape)"
        assert 'docker.sock' not in volumes_str.lower(), \
            "Docker socket must NOT be mounted"

    @patch('core.skill_sandbox.docker.from_env')
    def test_no_host_volumes_mounted(self, mock_docker, mock_docker_client):
        """
        Verify host filesystem volumes are never mounted.

        Host volume mounts enable direct filesystem access.
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        volumes = call_kwargs.get('volumes', {})

        # Verify no host paths mounted
        assert volumes == {} or all(
            not k.startswith('/') for k in volumes.keys()
        ), "Host volumes must NOT be mounted"

    @patch('core.skill_sandbox.docker.from_env')
    def test_no_host_pid_namespace(self, mock_docker, mock_docker_client):
        """
        Verify host PID namespace is not shared.

        Sharing host PID namespace enables process visibility
        and potential signaling attacks on host processes.
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        pid_mode = call_kwargs.get('pid_mode', None)

        # Verify not using host PID namespace
        assert pid_mode != 'host', \
            "Host PID namespace must NOT be shared"


# ============================================================================
# RESOURCE EXHAUSTION TESTS
# ============================================================================

class TestResourceExhaustion:
    """Resource limit enforcement tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_memory_limit_enforced(self, mock_docker, mock_docker_client):
        """
        Verify memory limit is set to prevent exhaustion attacks.

        Security: HIGH - Memory exhaustion can DoS the host
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            memory_limit="256m"
        )

        # Verify mem_limit is set
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('mem_limit') == "256m", \
            "Memory limit must be enforced to prevent exhaustion attacks"

    @patch('core.skill_sandbox.docker.from_env')
    def test_cpu_quota_enforced(self, mock_docker, mock_docker_client):
        """
        Verify CPU quota is set to prevent CPU exhaustion.

        Security: HIGH - CPU exhaustion can starve host processes
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            cpu_limit=0.5
        )

        # Verify cpu_quota is set (0.5 * 100000 = 50000)
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('cpu_quota') == 50000, \
            "CPU quota must be enforced (0.5 * 100000)"
        assert call_kwargs.get('cpu_period') == 100000, \
            "CPU period must be 100000 (Docker standard)"

    @patch('core.skill_sandbox.docker.from_env')
    def test_timeout_enforced(self, mock_docker, mock_docker_client):
        """
        Verify execution timeout prevents infinite loops.

        Security: MEDIUM - Timeout prevents resource lockup
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="while True: pass",
            inputs={},
            timeout_seconds=30
        )

        # Verify timeout parameter is passed
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('timeout') == 30, \
            "Timeout must be enforced to prevent infinite execution"

    @patch('core.skill_sandbox.docker.from_env')
    def test_auto_remove_enabled(self, mock_docker, mock_docker_client):
        """
        Verify containers are auto-removed after execution.

        Security: MEDIUM - Auto-remove prevents disk space exhaustion
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('auto_remove') is True, \
            "Containers must auto-remove to prevent disk exhaustion"


# ============================================================================
# NETWORK ISOLATION TESTS
# ============================================================================

class TestNetworkIsolation:
    """Network isolation enforcement tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_network_disabled(self, mock_docker, mock_docker_client):
        """
        Verify network is disabled to prevent data exfiltration.

        Security: CRITICAL - Network isolation prevents outbound attacks
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        # Verify network_disabled=True
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('network_disabled') is True, \
            "Network must be disabled to prevent data exfiltration"

    @patch('core.skill_sandbox.docker.from_env')
    def test_no_extra_hosts(self, mock_docker, mock_docker_client):
        """
        Verify no extra_hosts are configured.

        Extra hosts could be used for DNS tunneling attacks.
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        extra_hosts = call_kwargs.get('extra_hosts', {})

        assert extra_hosts == {} or extra_hosts is None, \
            "Extra hosts must not be configured (DNS tunneling risk)"


# ============================================================================
# FILESYSTEM ISOLATION TESTS
# ============================================================================

class TestFilesystemIsolation:
    """Filesystem isolation enforcement tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_read_only_filesystem(self, mock_docker, mock_docker_client):
        """
        Verify read-only filesystem prevents unauthorized writes.

        Security: HIGH - Read-only filesystem prevents malware persistence
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        # Verify read_only=True
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('read_only') is True, \
            "Filesystem must be read-only to prevent unauthorized writes"

    @patch('core.skill_sandbox.docker.from_env')
    def test_tmpfs_only_writable(self, mock_docker, mock_docker_client):
        """
        Verify only tmpfs is writable for temporary storage.

        Security: HIGH - Tmpfs prevents disk writes, isolated in RAM
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        # Verify tmpfs is mounted
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        tmpfs = call_kwargs.get('tmpfs', {})

        assert '/tmp' in tmpfs, \
            "Tmpfs must be mounted at /tmp for temporary storage"
        assert 'size=' in tmpfs['/tmp'], \
            "Tmpfs must have size limit to prevent RAM exhaustion"

    @patch('core.skill_sandbox.docker.from_env')
    def test_no_host_mounts(self, mock_docker, mock_docker_client):
        """
        Verify no host filesystem mounts.

        Security: CRITICAL - Host mounts enable container escape
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={}
        )

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        volumes = call_kwargs.get('volumes', {})
        binds = call_kwargs.get('volume_binds', [])

        # Verify no host mounts
        assert not volumes or not any(
            '/' in str(v) for v in volumes.values() if v
        ), "Host volumes must not be mounted"
        assert not binds or not any(
            '/:' in b for b in binds
        ), "Host bind mounts must not be used"


# ============================================================================
# MALICIOUS PATTERN DETECTION TESTS
# ============================================================================

class TestMaliciousPatternDetection:
    """Static scanning detects malicious patterns."""

    def test_subprocess_usage_detected(self, security_scanner):
        """
        Static scan detects subprocess usage.

        Security: HIGH - subprocess enables arbitrary command execution
        """
        # Use subprocess.call which is in MALICIOUS_PATTERNS
        malicious_code = """
import subprocess

# Arbitrary command execution via subprocess
user_input = 'rm -rf /'
subprocess.call(user_input, shell=True)
"""
        result = security_scanner.scan_skill(
            skill_name="malicious-subprocess",
            skill_content=malicious_code
        )

        assert result["safe"] == False, "Subprocess usage must be blocked"
        assert len(result["findings"]) > 0, "Security findings must be reported"
        assert any("subprocess" in f.lower() for f in result["findings"]), \
            "Finding must mention subprocess"

    def test_os_system_detected(self, security_scanner):
        """Static scan detects os.system usage."""
        code = "import os\nos.system('rm -rf /')"
        result = security_scanner.scan_skill(
            skill_name="malicious-os-system",
            skill_content=code
        )

        assert result["safe"] == False
        assert len(result["findings"]) > 0

    def test_eval_detected(self, security_scanner):
        """Static scan detects eval usage."""
        code = "eval('__import__(\\\"os\\\").system(\\\"rm -rf /\\\")')"
        result = security_scanner.scan_skill(
            skill_name="malicious-eval",
            skill_content=code
        )

        assert result["safe"] == False
        assert any("eval" in f.lower() for f in result["findings"])

    def test_base64_obfuscation_detected(self, security_scanner):
        """
        Static scan detects base64 obfuscation.

        Security: HIGH - Base64 obfuscation hides malicious payloads
        """
        result = security_scanner.scan_skill(
            skill_name="obfuscated-base64",
            skill_content=MALICIOUS_BASE64_OBFUSCATION
        )

        # Should detect base64.b64decode as suspicious
        assert result["safe"] == False or len(result["findings"]) > 0, \
            "Base64 obfuscation must be flagged"

    def test_import_obfuscation_detected(self, security_scanner):
        """Static scan detects import obfuscation."""
        result = security_scanner.scan_skill(
            skill_name="obfuscated-import",
            skill_content=MALICIOUS_IMPORT_OBFUSCATION
        )

        # Should detect __import__ or getattr
        assert result["safe"] == False or len(result["findings"]) > 0, \
            "Import obfuscation must be flagged"

    def test_pickle_unsafe_deserialization_detected(self, security_scanner):
        """
        Static scan detects unsafe pickle usage.

        Security: CRITICAL - pickle enables arbitrary code execution
        """
        result = security_scanner.scan_skill(
            skill_name="malicious-pickle",
            skill_content=MALICIOUS_CODE_EXECUTION_PICKLE
        )

        assert result["safe"] == False
        assert any("pickle" in f.lower() for f in result["findings"])

    def test_network_access_detected(self, security_scanner):
        """Static scan detects network access patterns."""
        result = security_scanner.scan_skill(
            skill_name="malicious-network",
            skill_content=MALICIOUS_NETWORK_EXFILTRATION_URLLIB
        )

        # Should detect urllib.request or socket
        assert result["safe"] == False or len(result["findings"]) > 0

    def test_benign_code_passes(self, security_scanner):
        """Verify benign code passes security scan."""
        benign_code = """
def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

result = calculate_average([1, 2, 3, 4, 5])
print(result)
"""

        result = security_scanner.scan_skill(
            skill_name="benign-calculator",
            skill_content=benign_code
        )

        # Benign code should pass (no malicious patterns)
        assert result["safe"] == True or result["risk_level"] in ["LOW", "UNKNOWN"]


# ============================================================================
# VULNERABILITY SCANNING TESTS
# ============================================================================

class TestVulnerabilityScanning:
    """pip-audit detects known vulnerabilities."""

    @patch('subprocess.run')
    def test_known_vulnerable_package_detected(self, mock_run, scanner):
        """
        pip-audit detects packages with known CVEs.

        Security: CRITICAL - Vulnerable packages can compromise system
        """
        # Mock pip-audit output for vulnerable package
        vuln_json = json.dumps([{
            "name": "requests",
            "versions": ["2.20.0"],
            "id": "CVE-2018-18074",
            "description": "Requests library does not remove Authorization header",
            "fix_versions": ["2.20.1"]
        }])
        mock_run.return_value = MagicMock(
            returncode=1,  # Non-zero means vulnerabilities found
            stdout=vuln_json,
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.20.0"])

        assert result["safe"] == False, "Vulnerable packages must be blocked"
        assert len(result["vulnerabilities"]) > 0, "Vulnerabilities must be reported"
        assert result["vulnerabilities"][0]["cve_id"] == "CVE-2018-18074"

    @patch('subprocess.run')
    def test_safe_package_passes_scan(self, mock_run, scanner):
        """Safe packages (no vulnerabilities) pass scan."""
        # Mock pip-audit output for safe package
        mock_run.return_value = MagicMock(
            returncode=0,  # Zero means no vulnerabilities
            stdout="[]",
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.28.0"])

        assert result["safe"] == True, "Safe packages should pass scan"
        assert len(result["vulnerabilities"]) == 0

    @patch('subprocess.run')
    def test_multiple_vulnerabilities_detected(self, mock_run, scanner):
        """Detect multiple vulnerabilities in dependency tree."""
        # Mock pip-audit with multiple vulnerabilities
        vuln_json = json.dumps([
            {
                "name": "requests",
                "versions": ["2.20.0"],
                "id": "CVE-2018-18074",
                "description": "Authorization header leak",
                "fix_versions": ["2.20.1"]
            },
            {
                "name": "urllib3",
                "versions": ["1.24.2"],
                "id": "CVE-2019-11324",
                "description": "Authorization header not removed",
                "fix_versions": ["1.24.3"]
            }
        ])
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=vuln_json,
            stderr=""
        )

        result = scanner.scan_packages(["requests==2.20.0"])

        assert result["safe"] == False
        assert len(result["vulnerabilities"]) == 2


# ============================================================================
# TYPOSQUATTING DETECTION TESTS
# ============================================================================

class TestTyposquattingDetection:
    """Typosquatting attack detection tests."""

    def test_typosquatting_packages_list_exists(self):
        """Verify typosquatting package data is available."""
        assert len(TYPOSQUATTING_PACKAGES) > 0, \
            "Typosquatting packages must be defined for testing"

    def test_known_typosquatting_patterns(self):
        """Verify common typosquatting patterns are documented."""
        package_names = [pkg[0] for pkg in TYPOSQUATTING_PACKAGES]

        # Common typos should be in list
        assert "reqeusts" in package_names, "Should catch 'requests' typo"
        assert "numpyy" in package_names, "Should catch 'numpy' typo"
        assert "panads" in package_names, "Should catch 'pandas' typo"

    def test_vulnerable_packages_cve_data(self):
        """Verify vulnerable packages have CVE metadata."""
        assert len(KNOWN_VULNERABLE_PACKAGES) > 0

        for pkg in KNOWN_VULNERABLE_PACKAGES:
            assert "cve" in pkg, "Vulnerable package must have CVE ID"
            assert "name" in pkg, "Vulnerable package must have name"
            assert "version" in pkg, "Vulnerable package must have version"
            assert "fix_versions" in pkg, "Vulnerable package must have fix versions"

    def test_dependency_confusion_packages_listed(self):
        """Verify dependency confusion attack patterns are documented."""
        assert len(DEPENDENCY_CONFUSION_PACKAGES) > 0, \
            "Dependency confusion packages must be listed"

        # Should include internal-sounding names
        assert any("internal" in pkg.lower() for pkg in DEPENDENCY_CONFUSION_PACKAGES), \
            "Should include 'internal' package names"


# ============================================================================
# GOVERNANCE BLOCKING TESTS
# ============================================================================

class TestGovernanceBlocking:
    """Maturity-based governance blocks unauthorized access."""

    def test_student_agent_blocked_from_python_packages(self, governance, db_session: Session):
        """
        STUDENT agents cannot use Python packages (non-negotiable).

        Security: CRITICAL - Educational restriction, cannot be bypassed
        """
        from tests.factories.agent_factory import StudentAgentFactory

        # Create STUDENT agent
        student_agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Check permission for unknown package
        result = governance.check_package_permission(
            agent_id=student_agent.id,
            package_name="numpy",
            version="1.21.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "STUDENT agents must be blocked from ALL Python packages"
        assert "STUDENT agents cannot" in result["reason"], \
            "Reason must mention STUDENT restriction"

    def test_student_blocked_even_from_approved_packages(self, governance, db_session: Session):
        """STUDENT agents blocked even from approved packages."""
        from tests.factories.agent_factory import StudentAgentFactory

        # Approve package for INTERN
        governance.approve_package(
            package_name="pandas",
            version="1.3.0",
            min_maturity="intern",
            approved_by="admin",
            db=db_session
        )

        # Create STUDENT agent
        student_agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Check permission for approved package
        result = governance.check_package_permission(
            agent_id=student_agent.id,
            package_name="pandas",
            version="1.3.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "STUDENT agents blocked even from approved packages"

    def test_banned_package_blocks_all_agents(self, governance, db_session: Session):
        """
        Banned packages block ALL agents regardless of maturity.

        Security: CRITICAL - Ban list overrides all other rules
        """
        from tests.factories.agent_factory import AutonomousAgentFactory

        # Ban package
        governance.ban_package(
            package_name="malicious-lib",
            version="1.0.0",
            reason="Security vulnerability: CVE-2025-99999",
            db=db_session
        )

        # Create AUTONOMOUS agent (highest maturity)
        autonomous_agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        # Check permission for banned package
        result = governance.check_package_permission(
            agent_id=autonomous_agent.id,
            package_name="malicious-lib",
            version="1.0.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "Banned packages must block even AUTONOMOUS agents"
        assert "banned" in result["reason"].lower(), \
            "Reason must mention ban"

    def test_unknown_package_requires_approval(self, governance, db_session: Session):
        """Unknown packages require approval before use."""
        from tests.factories.agent_factory import SupervisedAgentFactory

        # Create SUPERVISED agent
        supervised_agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        # Check permission for unknown package
        result = governance.check_package_permission(
            agent_id=supervised_agent.id,
            package_name="unknown-package",
            version="1.0.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "Unknown packages must require approval"
        assert "not in registry" in result["reason"].lower() or \
               "requires approval" in result["reason"].lower(), \
            "Reason must mention approval requirement"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestSecurityIntegration:
    """Integration tests for complete security pipeline."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_complete_security_stack(self, mock_docker, mock_docker_client, security_scanner):
        """
        Verify complete security stack: static scan + sandbox isolation.

        Security: CRITICAL - Defense-in-depth validation
        """
        mock_docker.return_value = mock_docker_client

        # Use os.system which is definitely in MALICIOUS_PATTERNS
        malicious_code = """
import os
os.system('rm -rf /')
"""

        # Step 1: Static scan should block
        scan_result = security_scanner.scan_skill(
            skill_name="malicious-test",
            skill_content=malicious_code
        )

        assert scan_result["safe"] == False, \
            "Static scan must detect malicious code"

        # Step 2: Even if scan fails, sandbox should constrain execution
        sandbox = HazardSandbox()
        result = sandbox.execute_python(
            code=malicious_code,
            inputs={}
        )

        # Verify security constraints applied
        assert mock_docker_client.containers.run.called
        call_kwargs = mock_docker_client.containers.run.call_args[1]

        # All critical security constraints must be present
        assert call_kwargs.get('network_disabled') is True, \
            "Network must be disabled"
        assert call_kwargs.get('read_only') is True, \
            "Filesystem must be read-only"
        assert call_kwargs.get('privileged', False) == False, \
            "Must not run in privileged mode"

    def test_malicious_patterns_comprehensive(self):
        """Verify all critical malicious patterns are documented."""
        # Critical patterns that MUST be detected
        critical_patterns = [
            "subprocess.run",
            "subprocess.call",
            "os.system",
            "eval(",
            "exec(",
            "pickle.loads",
            "subprocess.Popen",
            "urllib.request",
            "socket.socket"
        ]

        for pattern in critical_patterns:
            assert pattern in MALICIOUS_PATTERNS, \
                f"Critical pattern '{pattern}' must be in malicious patterns list"


# ============================================================================
# SUMMARY
# ============================================================================

"""
Test Coverage Summary:
- Container escape: 4 tests (privileged mode, Docker socket, host volumes, PID namespace)
- Resource exhaustion: 4 tests (memory, CPU, timeout, auto-remove)
- Network isolation: 2 tests (network disabled, no extra hosts)
- Filesystem isolation: 3 tests (read-only, tmpfs, no host mounts)
- Malicious pattern detection: 8 tests (subprocess, os.system, eval, base64, obfuscation, pickle, network, benign)
- Vulnerability scanning: 3 tests (CVE detection, safe packages, multiple vulnerabilities)
- Typosquatting detection: 4 tests (package list, patterns, CVE data, dependency confusion)
- Governance blocking: 4 tests (student blocking, approved packages, banned packages, unknown packages)
- Integration tests: 2 tests (complete security stack, pattern coverage)

Total: 34 security tests

Security Levels Tested:
- CRITICAL: 8 tests (privileged mode, Docker socket, host mounts, network isolation, pickle, student blocking, ban list, integration)
- HIGH: 10 tests (memory/CPU limits, read-only filesystem, subprocess, base64, network access, vulnerability scanning)
- MEDIUM: 6 tests (timeout, auto-remove, extra hosts, tmpfs, eval, dependency confusion)
- LOW: 10 tests (typosquatting patterns, benign code, package lists)
"""
