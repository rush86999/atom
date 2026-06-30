"""Execution Sandbox Layer — Phase D tests (Round 46).

Tests cover:
  * SandboxRuntime protocol + factory (get_runtime)
  * DockerRuntime adapter (lazy init, parsing legacy output)
  * FirecrackerRuntime availability probe + binary-missing fallback
  * E2BRuntime availability probe (env-driven)
  * NullRuntime as last-resort no-op
  * Egress proxy host normalization + allowlist matching
  * Dual-proxy split (LLM proxy vs Tool proxy)
  * URL extraction from args
  * Block non-allowlisted host (the canonical exfil attempt)
  * Allow pypi/anthropic/github hosts
  * Wildcard *.example.com matching
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_SANDBOX"):
            monkeypatch.delenv(k, raising=False)
    # Also reset E2B_API_KEY so availability probes are deterministic
    monkeypatch.delenv("E2B_API_KEY", raising=False)


def _policy(**kw):
    from core.sandbox_policy import SandboxPolicy

    defaults = dict(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        egress_hosts=(
            "api.anthropic.com",
            "pypi.org",
            "api.openai.com",
        ),
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


# ===========================================================================
# D1: SandboxExecResult frozen dataclass
# ===========================================================================


@pytest.mark.unit
def test_D1_exec_result_is_frozen():
    from dataclasses import FrozenInstanceError

    from core.sandbox_runtime.base import SandboxExecResult

    r = SandboxExecResult(success=True, stdout="ok", stderr="", exit_code=0)
    with pytest.raises(FrozenInstanceError):
        r.success = False  # type: ignore[misc]


# ===========================================================================
# D2: get_runtime returns DockerRuntime by default
# ===========================================================================


@pytest.mark.unit
def test_D2_get_runtime_default_is_docker(monkeypatch):
    from core.sandbox_runtime import get_runtime
    from core.sandbox_runtime.docker_runner import DockerRuntime

    monkeypatch.delenv("ATOM_SANDBOX_RUNTIME", raising=False)
    runtime = get_runtime()
    assert isinstance(runtime, DockerRuntime)


@pytest.mark.unit
def test_D2b_get_runtime_firecracker_falls_back_when_unavailable(monkeypatch):
    """When firecracker is selected but unavailable, falls back to Docker."""
    from core.sandbox_runtime import get_runtime
    from core.sandbox_runtime.docker_runner import DockerRuntime

    monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "firecracker")
    runtime = get_runtime()
    # On macOS (no KVM), FirecrackerRuntime.is_available() is False → falls back
    assert isinstance(runtime, DockerRuntime)


@pytest.mark.unit
def test_D2c_get_runtime_e2b_falls_back_without_apikey(monkeypatch):
    from core.sandbox_runtime import get_runtime
    from core.sandbox_runtime.docker_runner import DockerRuntime

    monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "e2b")
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    runtime = get_runtime()
    assert isinstance(runtime, DockerRuntime)


@pytest.mark.unit
def test_D2d_get_runtime_invalid_value_falls_back(monkeypatch):
    from core.sandbox_runtime import get_runtime
    from core.sandbox_runtime.docker_runner import DockerRuntime

    monkeypatch.setenv("ATOM_SANDBOX_RUNTIME", "garbage_xyz")
    runtime = get_runtime()
    assert isinstance(runtime, DockerRuntime)


# ===========================================================================
# D3: NullRuntime — last-resort no-op
# ===========================================================================


@pytest.mark.unit
async def test_D3_null_runtime_returns_failure():
    from core.sandbox_runtime.base import NullRuntime

    runtime = NullRuntime()
    policy = _policy()
    result = await runtime.execute_python("print('hi')", policy=policy)
    assert result.success is False
    assert result.exit_code == -1
    assert "No sandbox runtime" in result.stderr


# ===========================================================================
# D4: FirecrackerRuntime availability probe
# ===========================================================================


@pytest.mark.unit
def test_D4_firecracker_availability(monkeypatch):
    from core.sandbox_runtime import firecracker_runner

    # On macOS, is_available should be False (not Linux)
    if not firecracker_runner._IS_LINUX:
        assert firecracker_runner.is_available() is False


@pytest.mark.unit
async def test_D4b_firecracker_returns_failure_when_unavailable(monkeypatch):
    """When binary missing, execute returns structured failure (not raise)."""
    from core.sandbox_runtime.firecracker_runner import FirecrackerRuntime

    runtime = FirecrackerRuntime()
    policy = _policy()

    # Patch is_available to return False — simulates macOS or missing binary
    monkeypatch.setattr(
        "core.sandbox_runtime.firecracker_runner.is_available",
        lambda: False,
    )
    result = await runtime.execute_python("print('hi')", policy=policy)
    assert result.success is False
    assert result.exit_code == -1
    assert "not found" in result.stderr.lower() or "binary" in result.stderr.lower()


# ===========================================================================
# D5: E2BRuntime availability probe
# ===========================================================================


@pytest.mark.unit
def test_D5_e2b_availability_requires_api_key(monkeypatch):
    from core.sandbox_runtime.e2b_runner import is_available

    monkeypatch.delenv("E2B_API_KEY", raising=False)
    assert is_available() is False


@pytest.mark.unit
def test_D5b_e2b_availability_requires_sdk(monkeypatch):
    from core.sandbox_runtime.e2b_runner import is_available

    monkeypatch.setenv("E2B_API_KEY", "fake-key")
    # Even with key, is_available is False when SDK not installed
    # (tests run without e2b in venv)
    assert is_available() is False  # SDK missing in test env


@pytest.mark.unit
async def test_D5c_e2b_returns_failure_when_unavailable(monkeypatch):
    from core.sandbox_runtime.e2b_runner import E2BRuntime

    monkeypatch.delenv("E2B_API_KEY", raising=False)
    runtime = E2BRuntime()
    policy = _policy()
    result = await runtime.execute_python("print('hi')", policy=policy)
    assert result.success is False
    assert "E2B_API_KEY" in result.stderr or "SDK" in result.stderr


# ===========================================================================
# D6: Egress proxy host normalization
# ===========================================================================


@pytest.mark.unit
def test_D6_normalize_host_strips_port_and_case():
    from core.sandbox_egress_proxy import normalize_host

    assert normalize_host("API.Anthropic.COM") == "api.anthropic.com"
    assert normalize_host("api.anthropic.com:443") == "api.anthropic.com"
    assert normalize_host("api.anthropic.com.") == "api.anthropic.com"
    assert normalize_host(None) == ""
    assert normalize_host("") == ""


# ===========================================================================
# D7: host_matches — exact + wildcard
# ===========================================================================


@pytest.mark.unit
def test_D7_host_matches_exact():
    from core.sandbox_egress_proxy import host_matches

    assert host_matches("api.anthropic.com", ("api.anthropic.com",)) is True
    assert host_matches("other.com", ("api.anthropic.com",)) is False


@pytest.mark.unit
def test_D7b_host_matches_wildcard():
    from core.sandbox_egress_proxy import host_matches

    allowlist = ("*.example.com",)
    assert host_matches("api.example.com", allowlist) is True
    assert host_matches("sub.api.example.com", allowlist) is True
    assert host_matches("example.com", allowlist) is True  # suffix match
    assert host_matches("notexample.com", allowlist) is False  # prefix differs


# ===========================================================================
# D8: check_egress — allowlisted host
# ===========================================================================


@pytest.mark.unit
def test_D8_check_egress_allowlisted():
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import ALLOWED

    policy = _policy()
    d = check_egress(policy, url="https://api.anthropic.com/v1/messages", tool_name="t")
    assert d.decision == ALLOWED


@pytest.mark.unit
def test_D8b_check_egress_pypi_allowlisted():
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import ALLOWED

    policy = _policy()
    d = check_egress(policy, url="https://pypi.org/simple/", tool_name="t")
    assert d.decision == ALLOWED


# ===========================================================================
# D9: check_egress — non-allowlisted host BLOCKED (exfil attempt)
# ===========================================================================


@pytest.mark.unit
def test_D9_check_egress_exfil_blocked(monkeypatch):
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import BLOCKED, VT_EGRESS_HOST

    monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
    policy = _policy()
    d = check_egress(
        policy,
        url="https://exfil.attacker.com/x?data=$(cat /etc/passwd)",
        tool_name="t",
    )
    assert d.decision == BLOCKED
    assert d.violation_type == VT_EGRESS_HOST
    assert "exfil.attacker.com" in d.violation_detail


# ===========================================================================
# D10: check_egress disabled when feature flag off
# ===========================================================================


@pytest.mark.unit
def test_D10_check_egress_disabled_by_default(monkeypatch):
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import ALLOWED

    monkeypatch.delenv("ATOM_SANDBOX_EGRESS_ENABLED", raising=False)
    policy = _policy()
    # Even non-allowlisted host allowed because feature off
    d = check_egress(policy, url="https://exfil.attacker.com/x", tool_name="t")
    assert d.decision == ALLOWED
    assert d.metadata_json.get("egress_check") == "disabled"


# ===========================================================================
# D11: validate (multi-URL) — BLOCKED dominates
# ===========================================================================


@pytest.mark.unit
def test_D11_validate_blocked_dominates(monkeypatch):
    from core.sandbox_egress_proxy import validate
    from core.sandbox_policy import BLOCKED

    monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
    policy = _policy()
    args = {
        "url": "https://exfil.attacker.com/x",  # BLOCKED
        "callback_url": "https://api.anthropic.com",  # allowed
    }
    d = validate(policy, "browser_navigate", args)
    assert d.decision == BLOCKED


@pytest.mark.unit
def test_D11b_validate_no_url_args_allowed():
    from core.sandbox_egress_proxy import validate
    from core.sandbox_policy import ALLOWED

    policy = _policy()
    args = {"selector": "#foo", "value": "bar"}
    d = validate(policy, "browser_click", args)
    assert d.decision == ALLOWED


# ===========================================================================
# D12: extract_urls_from_args
# ===========================================================================


@pytest.mark.unit
def test_D12_extract_urls_picks_url_keys():
    from core.sandbox_egress_proxy import extract_urls_from_args

    args = {
        "url": "https://api.anthropic.com",
        "selector": "#foo",  # not a URL key
        "webhook_url": "https://hooks.example.com",
        "host": "pypi.org",
        "count": 3,
    }
    urls = extract_urls_from_args(args)
    assert "url" in urls
    assert "webhook_url" in urls
    # "host": "pypi.org" doesn't have a scheme → not extracted
    assert "host" not in urls
    assert "selector" not in urls
    assert "count" not in urls


# ===========================================================================
# D13: Dual-proxy split — LLM proxy vs Tool proxy
# ===========================================================================


@pytest.mark.unit
def test_D13_dual_proxy_split():
    from core.sandbox_egress_proxy import get_dual_proxy_split, LlmProxy, ToolProxy

    policy = _policy(egress_hosts=("api.anthropic.com", "github.com"))
    llm_proxy, tool_proxy = get_dual_proxy_split(policy)

    assert isinstance(llm_proxy, LlmProxy)
    assert isinstance(tool_proxy, ToolProxy)

    # LLM proxy allows Anthropic
    assert llm_proxy.can_connect("api.anthropic.com") is True
    # LLM proxy does NOT allow GitHub (not in LLM set)
    assert llm_proxy.can_connect("github.com") is False

    # Tool proxy allows both (effective allowlist = baseline + policy)
    assert tool_proxy.can_connect("api.anthropic.com") is True
    assert tool_proxy.can_connect("github.com") is True
    # Tool proxy blocks attacker
    assert tool_proxy.can_connect("exfil.attacker.com") is False


# ===========================================================================
# D14: effective_allowlist — baseline + policy union
# ===========================================================================


@pytest.mark.unit
def test_D14_effective_allowlist_union():
    from core.sandbox_egress_proxy import effective_allowlist

    policy = _policy(egress_hosts=("custom.tool.com",))
    allow = effective_allowlist(policy)
    # baseline always present
    assert "api.anthropic.com" in allow
    assert "pypi.org" in allow
    # policy addition
    assert "custom.tool.com" in allow


# ===========================================================================
# D15: malformed URL → ALLOWED with metadata (fail-open on parse)
# ===========================================================================


@pytest.mark.unit
def test_D15_malformed_url_fail_open(monkeypatch):
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import ALLOWED

    monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
    policy = _policy()
    d = check_egress(policy, url="not-a-url-at-all", tool_name="t")
    # No host parsed → allowed (caller will hit DNS failure upstream)
    assert d.decision == ALLOWED


# ===========================================================================
# D16: DockerRuntime _parse_legacy_output handles str + dict
# ===========================================================================


@pytest.mark.unit
def test_D16_parse_legacy_string_output():
    from core.sandbox_runtime.docker_runner import _parse_legacy_output

    result = _parse_legacy_output("hello world")
    assert result.success is True
    assert result.stdout == "hello world"
    assert result.exit_code == 0


@pytest.mark.unit
def test_D16b_parse_legacy_error_string():
    from core.sandbox_runtime.docker_runner import _parse_legacy_output

    result = _parse_legacy_output("EXECUTION_ERROR: boom")
    assert result.success is False
    assert "EXECUTION_ERROR" in result.stderr


@pytest.mark.unit
def test_D16c_parse_legacy_dict_output():
    from core.sandbox_runtime.docker_runner import _parse_legacy_output

    result = _parse_legacy_output(
        {"success": True, "stdout": "ok", "stderr": "", "returncode": 0}
    )
    assert result.success is True
    assert result.exit_code == 0
    assert result.metadata.get("backend") == "docker"


# ===========================================================================
# D17: SandboxRuntime is a runtime_checkable Protocol
# ===========================================================================


@pytest.mark.unit
def test_D17_sandbox_runtime_protocol_runtime_checkable():
    from core.sandbox_runtime.base import SandboxRuntime
    from core.sandbox_runtime.docker_runner import DockerRuntime

    # isinstance works because the protocol is @runtime_checkable
    runtime = DockerRuntime()
    assert isinstance(runtime, SandboxRuntime)


# ===========================================================================
# D18: tier egress baseline — autonomous has more hosts than student
# ===========================================================================


@pytest.mark.unit
def test_D18_autonomous_egress_superset_of_student():
    from core.sandbox_policy import PolicyIssuer

    issuer = PolicyIssuer()
    student = issuer.issue("r1", "a1", "student")
    auto = issuer.issue("r2", "a1", "autonomous")
    # student has NO egress; autonomous has multiple
    assert len(student.egress_hosts) == 0
    assert len(auto.egress_hosts) > 0


# ===========================================================================
# D19: allowlist normalizes policy hosts (case-insensitive)
# ===========================================================================


@pytest.mark.unit
def test_D19_case_insensitive_host_match():
    from core.sandbox_egress_proxy import check_egress
    from core.sandbox_policy import ALLOWED

    policy = _policy(egress_hosts=("api.anthropic.com",))
    d = check_egress(
        policy,
        url="https://API.ANTHROPIC.COM/v1/messages",
        tool_name="t",
    )
    assert d.decision == ALLOWED


# ===========================================================================
# D20: integration — egress check on policy-issued whitelist
# ===========================================================================


@pytest.mark.unit
def test_D20_integration_policy_egress(monkeypatch):
    monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
    from core.sandbox_egress_proxy import validate
    from core.sandbox_policy import PolicyIssuer, BLOCKED

    issuer = PolicyIssuer()
    # autonomous gets the curated egress list (api.anthropic.com, pypi, github)
    policy = issuer.issue("r1", "a1", "autonomous")

    # Allowlisted: OK
    d1 = validate(policy, "browser_navigate", {"url": "https://api.anthropic.com"})
    assert d1.decision != BLOCKED

    # Non-allowlisted: BLOCKED
    d2 = validate(
        policy,
        "browser_navigate",
        {"url": "https://evil.example.com/exfil"},
    )
    assert d2.decision == BLOCKED
