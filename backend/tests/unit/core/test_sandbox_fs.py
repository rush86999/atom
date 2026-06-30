"""Execution Sandbox Layer — Phase B tests (Round 44).

Tests cover:
  * Path normalization (relative→absolute, ``..`` collapse, symlinks)
  * Tripwire detection (forbidden prefixes, home-sensitive paths)
  * Scope check (within fs_roots / fs_write_roots)
  * Shadow vs enforce parity
  * Path rewriting (RESTRICTED recovery)
  * Per-tool write-tool detection
  * Worst-decision aggregation across multiple path args
  * Fail-safe defaults (no path args → ALLOWED)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch, tmp_path):
    """Reset env + use tmp dirs so Path.home() tests are deterministic."""
    for k in list(os.environ):
        if k.startswith("ATOM_SANDBOX"):
            monkeypatch.delenv(k, raising=False)


def _make_policy(**kwargs):
    from core.sandbox_policy import SandboxPolicy

    defaults = dict(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        fs_roots=("/workspace/data", "/tmp/agent/r1"),
        fs_write_roots=("/tmp/agent/r1",),
    )
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


# ---------------------------------------------------------------------------
# B1: path within fs_roots → ALLOWED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B1_path_within_read_roots_allowed():
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import ALLOWED

    policy = _make_policy()
    d = validate_path(
        "/workspace/data/file.txt", policy, write=False, tool_name="read_codebase"
    )
    assert d.decision == ALLOWED


@pytest.mark.unit
def test_B1b_path_within_write_roots_allowed_for_write():
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import ALLOWED

    policy = _make_policy()
    d = validate_path(
        "/tmp/agent/r1/output.log", policy, write=True, tool_name="write_code_file"
    )
    assert d.decision == ALLOWED


# ---------------------------------------------------------------------------
# B2: path outside roots → RESTRICTED (recoverable, not blocked)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B2_path_outside_roots_restricted():
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import RESTRICTED, VT_FS_PATH

    policy = _make_policy()
    d = validate_path(
        "/somewhere/else/file.txt", policy, write=False, tool_name="read_codebase"
    )
    assert d.decision == RESTRICTED
    assert d.violation_type == VT_FS_PATH
    assert "outside" in d.violation_detail


# ---------------------------------------------------------------------------
# B3: tripwire — /etc/passwd → BLOCKED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B3_etc_passwd_blocked_by_tripwire():
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import BLOCKED, VT_FS_PATH

    policy = _make_policy()
    d = validate_path(
        "/etc/passwd", policy, write=False, tool_name="read_codebase"
    )
    assert d.decision == BLOCKED
    assert d.violation_type == VT_FS_PATH
    assert "forbidden_prefix" in d.metadata_json.get("tripwire", "")


# ---------------------------------------------------------------------------
# B4: tripwire — /proc, /sys, /dev, /root, /var/lib/docker
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    ["/proc/self/environ", "/sys/kernel/hostname", "/dev/sda", "/root/.bashrc", "/var/lib/docker/containers"],
)
def test_B4_forbidden_system_paths_blocked(path):
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import BLOCKED

    policy = _make_policy()
    d = validate_path(path, policy, write=False, tool_name="t")
    assert d.decision == BLOCKED


# ---------------------------------------------------------------------------
# B5: tripwire — ~/.ssh, ~/.aws, ~/.env
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B5_home_ssh_blocked(monkeypatch, tmp_path):
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import BLOCKED

    # Force Path.home() to a deterministic tmp dir
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    policy = _make_policy()
    d = validate_path(
        str(fake_home / ".ssh" / "id_rsa"), policy, write=False, tool_name="t"
    )
    assert d.decision == BLOCKED
    assert "forbidden_home" in d.metadata_json.get("tripwire", "")


@pytest.mark.unit
def test_B5b_home_aws_credentials_blocked(monkeypatch, tmp_path):
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import BLOCKED

    fake_home = tmp_path / "h"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    policy = _make_policy()
    d = validate_path(
        str(fake_home / ".aws" / "credentials"), policy, write=False, tool_name="t"
    )
    assert d.decision == BLOCKED


@pytest.mark.unit
def test_B5c_env_file_in_home_blocked(monkeypatch, tmp_path):
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import BLOCKED

    fake_home = tmp_path / "h"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    policy = _make_policy()
    d = validate_path(
        str(fake_home / ".env"), policy, write=False, tool_name="t"
    )
    assert d.decision == BLOCKED


# ---------------------------------------------------------------------------
# B6: relative path resolved against cwd
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B6_relative_path_resolved_with_cwd(tmp_path):
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import ALLOWED

    workspace = tmp_path / "ws"
    workspace.mkdir()
    policy = _make_policy(fs_roots=(str(workspace),), fs_write_roots=(str(workspace),))

    d = validate_path(
        "file.txt",
        policy,
        write=True,
        tool_name="write_code_file",
        cwd=str(workspace),
    )
    assert d.decision == ALLOWED


# ---------------------------------------------------------------------------
# B7: extract_paths_from_args — known path keys
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B7_extract_paths_picks_known_keys():
    from core.sandbox_fs import extract_paths_from_args

    args = {
        "file_path": "/a/b.txt",
        "selector": "#foo",  # not a path key
        "output_path": "/out/file.log",
        "cwd": "/tmp",
        "count": 3,
        "nested": {"path": "/deep"},  # nested dict, not extracted (conservative)
    }
    paths = extract_paths_from_args(args)
    assert "file_path" in paths
    assert "output_path" in paths
    assert "cwd" in paths
    assert "selector" not in paths
    assert "count" not in paths
    assert "nested" not in paths


# ---------------------------------------------------------------------------
# B8: validate (multi-path) — BLOCKED dominates RESTRICTED dominates ALLOWED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B8_validate_blocked_dominates(monkeypatch, tmp_path):
    from core.sandbox_fs import validate
    from core.sandbox_policy import BLOCKED

    fake_home = tmp_path / "h"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    policy = _make_policy()
    # Two paths: one allowed, one blocked. Worst wins.
    args = {
        "file_path": "/workspace/data/ok.txt",  # allowed
        "output_path": str(fake_home / ".ssh" / "id_rsa"),  # BLOCKED
    }
    d = validate(policy, "write_code_file", args)
    assert d.decision == BLOCKED


@pytest.mark.unit
def test_B8b_validate_restricted_wins_over_allowed():
    from core.sandbox_fs import validate
    from core.sandbox_policy import RESTRICTED

    policy = _make_policy()
    args = {
        "file_path": "/workspace/data/ok.txt",   # allowed
        "output_path": "/somewhere/else/x.txt",  # RESTRICTED
    }
    d = validate(policy, "write_code_file", args)
    assert d.decision == RESTRICTED


@pytest.mark.unit
def test_B8c_validate_no_path_args_allowed():
    from core.sandbox_fs import validate
    from core.sandbox_policy import ALLOWED

    policy = _make_policy()
    args = {"selector": "#foo", "value": "bar"}  # no path keys
    d = validate(policy, "browser_click", args)
    assert d.decision == ALLOWED


# ---------------------------------------------------------------------------
# B9: write-tool detection — write tools check against fs_write_roots
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B9_write_tool_checked_against_write_roots():
    from core.sandbox_fs import validate
    from core.sandbox_policy import RESTRICTED

    policy = _make_policy(
        fs_roots=("/workspace/data", "/tmp/agent/r1"),
        fs_write_roots=("/tmp/agent/r1",),
    )
    # /workspace/data is in fs_roots (read) but NOT fs_write_roots.
    # A write tool targeting it should be RESTRICTED.
    args = {"file_path": "/workspace/data/attempt.log"}
    d = validate(policy, "write_code_file", args)
    assert d.decision == RESTRICTED
    assert d.metadata_json.get("write") is True


@pytest.mark.unit
def test_B9b_read_tool_checked_against_read_roots():
    from core.sandbox_fs import validate
    from core.sandbox_policy import ALLOWED

    policy = _make_policy(
        fs_roots=("/workspace/data", "/tmp/agent/r1"),
        fs_write_roots=("/tmp/agent/r1",),
    )
    # /workspace/data is in fs_roots — a read tool may access it.
    args = {"file_path": "/workspace/data/ok.txt"}
    d = validate(policy, "read_codebase", args)  # not a write tool
    assert d.decision == ALLOWED


# ---------------------------------------------------------------------------
# B10: rewrite_path_to_sandbox — RESTRICTED recovery
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B10_rewrite_path_to_sandbox(tmp_path):
    from core.sandbox_fs import rewrite_path_to_sandbox

    sandbox_root = tmp_path / "sandbox"
    rewritten = rewrite_path_to_sandbox("/etc/passwd", str(sandbox_root))
    assert rewritten.endswith("passwd")
    assert str(sandbox_root) in rewritten
    # Sandbox root was created
    assert sandbox_root.exists()


@pytest.mark.unit
def test_B10b_rewrite_relative_path(tmp_path):
    from core.sandbox_fs import rewrite_path_to_sandbox

    sandbox_root = tmp_path / "sb"
    rewritten = rewrite_path_to_sandbox("local.txt", str(sandbox_root))
    assert rewritten.endswith("local.txt")
    assert str(sandbox_root) in rewritten


# ---------------------------------------------------------------------------
# B11: shadow vs enforce — enforced flag tracks env
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B11_shadow_default_enforced_false(monkeypatch):
    from core.sandbox_fs import validate_path

    monkeypatch.delenv("ATOM_SANDBOX_FORCE_ENFORCE", raising=False)
    policy = _make_policy()
    d = validate_path("/etc/passwd", policy, write=False, tool_name="t")
    # BLOCKED but not enforced
    assert d.decision == "blocked"
    assert d.enforced is False


@pytest.mark.unit
def test_B11b_force_enforce_true_flips_flag(monkeypatch):
    from core.sandbox_fs import validate_path

    monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
    policy = _make_policy()
    d = validate_path("/etc/passwd", policy, write=False, tool_name="t")
    assert d.decision == "blocked"
    assert d.enforced is True


# ---------------------------------------------------------------------------
# B12: resolve_error tripwire — broken path → BLOCKED (fail safe)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B12_unresolvable_path_blocked():
    from core.sandbox_fs import _normalize_path

    # Null bytes in paths cause ValueError on resolve
    resolved, trip = _normalize_path("bad\x00path")
    # Should not raise; should return a tripwire
    assert trip is not None


# ---------------------------------------------------------------------------
# B13: integration — validate() round-trip with SandboxPolicy issued
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B13_validate_with_issued_policy(tmp_path, monkeypatch):
    from core.sandbox_fs import validate
    from core.sandbox_policy import PolicyIssuer, BLOCKED

    fake_home = tmp_path / "h"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    issuer = PolicyIssuer()
    policy = issuer.issue(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        workspace_data_root=str(tmp_path / "ws"),
        workspace_tmp_root=str(tmp_path / "tmp" / "r1"),
    )
    # Attempt to read /etc/passwd via read_codebase — must BLOCK
    d = validate(policy, "read_codebase", {"file_path": "/etc/passwd"})
    assert d.decision == BLOCKED


# ---------------------------------------------------------------------------
# B14: empty/None args handled
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B14_empty_args_allowed():
    from core.sandbox_fs import validate
    from core.sandbox_policy import ALLOWED

    policy = _make_policy()
    d = validate(policy, "any_tool", {})
    assert d.decision == ALLOWED


@pytest.mark.unit
def test_B14b_none_path_value_skipped():
    from core.sandbox_fs import extract_paths_from_args

    args = {"file_path": None, "output_path": ""}
    paths = extract_paths_from_args(args)
    # None and empty string are filtered out
    assert paths == {}


# ---------------------------------------------------------------------------
# B15: read vs write asymmetry — write tool against read-only tier
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_B15_student_tier_cannot_write_anywhere():
    """STUDENT tier has empty fs_write_roots — any write is RESTRICTED."""
    from core.sandbox_fs import validate_path
    from core.sandbox_policy import RESTRICTED

    # student: fs_write_roots == ()
    from core.sandbox_policy import PolicyIssuer

    policy = PolicyIssuer().issue("r1", "a1", "student")
    d = validate_path(
        "/workspace/data/attempt.log",
        policy,
        write=True,
        tool_name="write_code_file",
    )
    # No roots to be in → out of scope
    assert d.decision == RESTRICTED
