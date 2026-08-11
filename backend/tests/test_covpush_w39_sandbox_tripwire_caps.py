"""Coverage push W39 — core/sandbox_tripwire.py + core/sandbox_caps.py.

Drives the remaining uncovered branches of both modules:

Tripwire:
  * `_extract_text_for_matching` non-string scalar fallback (int/bool/None)
  * `match()` re.error containment path (registry patterns never raise on
    real inputs, so a synthetic broken pattern is injected)
  * `all_patterns()` introspection API
  * `check_python_ast`: SyntaxError + JS-marker path → `check_js_ast`
    (all 4 JS patterns: eval(, Function(, child_process, process.env.*)
  * `ast.ImportFrom` forbidden-module branch
  * `getattr()` reflection call branch
  * dunder-class traversal via Call (`().__class__.__base__.__subclasses__()`)
    and bare `ast.Attribute` (Load and Store contexts)
  * `globals["__builtins__"]` subscript reflection
  * `os.environ["HOME"]` (non-secret key → no tripwire)
  * `_check_ast_violations` list/tuple walk
  * `check()` exception path: fail-CLOSED under enforcement, fail-open in shadow

Caps:
  * `_payload_char_count` str/bytes/dict/list payload branches
  * `_serialized_char_count` fallback + exception path
  * `estimate_write_bytes` / `estimate_cost_usd` positive accrual paths
  * `estimate_tool_usage` fail-open exception path
  * `max_exec_seconds` elapsed-cap branch
  * in-lock re-check race branch (counter bumped between fast-path and
    locked re-check — simulated deterministically with a bumping lock)
  * byte/cost accrual in both counter-increment paths
  * `record_write` / `record_cost` / `release_run` exception containment

MegafileDetector + MegafileWarning (tripwire module): full lifecycle.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from core import sandbox_caps, sandbox_tripwire
from core.sandbox_policy import ALLOWED, BLOCKED, RESTRICTED, SandboxPolicy, VT_TRIPWIRE
from core.sandbox_tripwire import MegafileDetector, MegafileWarning, TripwirePattern


@pytest.fixture(autouse=True)
def _clean_sandbox_state(monkeypatch):
    """Reset ATOM_SANDBOX_* env vars + the process-wide counter registry."""
    for k in list(__import__("os").environ):
        if k.startswith("ATOM_SANDBOX"):
            monkeypatch.delenv(k, raising=False)
    sandbox_caps.get_registry().reset()


def _policy(**kw: Any) -> SandboxPolicy:
    defaults: dict[str, Any] = dict(
        run_id="cov39-r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        max_tool_calls=10,
        max_exec_seconds=60,
        max_bytes_written=1024 * 1024,
        max_cost_usd=5.0,
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


# ===========================================================================
# Tripwire — matching internals
# ===========================================================================


def test_tripwire_extract_text_scalar_fallback_allowed():
    """Non-string args (int/bool/float/None) flatten via str() and do not trip."""
    d = sandbox_tripwire.check(
        tool_name="t",
        args={
            "count": 42,
            "flag": True,
            "nested": [7, None, 3.14],
            "obj": {"depth": 1, "units": "none"},
        },
    )
    assert d.decision == ALLOWED
    text = sandbox_tripwire._extract_text_for_matching(
        {"a": 1, "b": [None, False], "c": {"d": 2.5}}
    )
    assert "1" in text and "None" in text and "False" in text and "2.5" in text


def test_tripwire_match_swallows_regex_errors(monkeypatch):
    """A broken registry pattern must be logged + skipped, not raised."""

    class _BadRegex:
        def search(self, text):  # noqa: ANN001
            raise re.error("simulated catastrophic regex failure")

    bad = TripwirePattern(
        id="bad_pattern",
        category="CREDENTIAL",
        regex=_BadRegex(),  # type: ignore[arg-type]
        description="synthetic broken pattern",
    )
    monkeypatch.setattr(sandbox_tripwire, "_TRIPWIRES", (bad,))
    assert sandbox_tripwire.match({"command": "ls -la"}) is None


def test_tripwire_all_patterns_introspection():
    patterns = sandbox_tripwire.all_patterns()
    ids = {p.id for p in patterns}
    assert len(patterns) >= 19
    assert {"cred_aws", "destructive_drop_table", "rshell_dev_tcp", "exfil_curl_to_external"} <= ids
    for p in patterns:
        assert p.id and p.category and p.description


# ===========================================================================
# Tripwire — JS/TS AST checks (SyntaxError → JS markers → check_js_ast)
# ===========================================================================

@pytest.mark.parametrize(
    "code, expected_fragment",
    [
        ("function x() { eval('doBad()'); }", "eval() execution"),
        ("const f = new Function('return process')", "Function constructor execution"),
        ("const cp = require('child_process'); cp.exec('ls')", "child_process execution"),
        ("let k = process.env.API_KEY", "process.env secret access"),
        ("var t = process.env.AWS_ACCESS_KEY_ID", "process.env secret access"),
        ("const w = process.env.TOKEN", "process.env secret access"),
    ],
)
def test_tripwire_js_ast_violations_blocked(code, expected_fragment):
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == BLOCKED
    assert d.violation_type == VT_TRIPWIRE
    assert "JS/TS AST violation" in d.violation_detail
    assert expected_fragment in d.violation_detail


def test_tripwire_js_looking_but_safe_code_allowed():
    """JS syntax markers without a dangerous pattern must not trip."""
    d = sandbox_tripwire.check(
        tool_name="t",
        args={"code": "const x = 1; console.log(x);"},
    )
    assert d.decision == ALLOWED


def test_tripwire_plain_prose_skips_js_check():
    """Prose (SyntaxError, no JS markers) must not run the JS checker."""
    d = sandbox_tripwire.check(
        tool_name="t",
        args={"note": "the quick brown fox jumps over the lazy dog"},
    )
    assert d.decision == ALLOWED


# ===========================================================================
# Tripwire — remaining Python AST branches
# ===========================================================================


@pytest.mark.parametrize(
    "code, expected_fragment",
    [
        ("from os import system", "Forbidden import from module 'os'"),
        ("from subprocess import run", "Forbidden import from module 'subprocess'"),
        ("from socket import socket", "Forbidden import from module 'socket'"),
        ("from pty import spawn", "Forbidden import from module 'pty'"),
    ],
)
def test_tripwire_ast_forbidden_from_import(code, expected_fragment):
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == BLOCKED
    assert expected_fragment in d.violation_detail


def test_tripwire_ast_getattr_reflection_blocked():
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": "getattr(os, 'system')('ls')"}
    )
    assert d.decision == BLOCKED
    assert "Forbidden reflection getattr() on module 'os'" in d.violation_detail


def test_tripwire_ast_getattr_non_module_target_allowed():
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": "getattr(foo, 'bar')()"}
    )
    assert d.decision == ALLOWED


def test_tripwire_ast_dunder_subclasses_call_blocked():
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": "().__class__.__base__.__subclasses__()"}
    )
    assert d.decision == BLOCKED
    assert "Forbidden dunder-class traversal __subclasses__()" in d.violation_detail


def test_tripwire_ast_dunder_bases_mro_calls_blocked():
    d1 = sandbox_tripwire.check(tool_name="t", args={"code": "x.__class__.__bases__()"})
    assert d1.decision == BLOCKED
    assert "__bases__" in d1.violation_detail
    d2 = sandbox_tripwire.check(tool_name="t", args={"code": "obj.__class__.__mro__()"})
    assert d2.decision == BLOCKED
    assert "__mro__" in d2.violation_detail


def test_tripwire_ast_globals_subscript_blocked():
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": 'globals["__builtins__"]["eval"]'}
    )
    assert d.decision == BLOCKED
    assert "Reflection via globals[] subscript" in d.violation_detail


@pytest.mark.parametrize("fn", ["vars", "locals"])
def test_tripwire_ast_vars_locals_subscript_blocked(fn):
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": f'{fn}()["__builtins__"]'}
    )
    # globals()/vars()/locals() call itself is a forbidden built-in call
    assert d.decision == BLOCKED
    assert d.metadata_json["tripwire_id"] == "ast_violation"


def test_tripwire_ast_bare_dunder_attribute_load_allowed():
    """Bare `x.__class__` (isinstance-style reads) must not trip."""
    d = sandbox_tripwire.check(tool_name="t", args={"code": "c = x.__class__"})
    assert d.decision == ALLOWED


def test_tripwire_ast_dunder_attribute_store_allowed():
    d = sandbox_tripwire.check(tool_name="t", args={"code": "x.__class__ = Foo"})
    assert d.decision == ALLOWED


def test_tripwire_ast_env_non_secret_key_allowed():
    d = sandbox_tripwire.check(tool_name="t", args={"code": "h = os.environ['HOME']"})
    assert d.decision == ALLOWED


def test_tripwire_ast_env_secret_key_blocked():
    d = sandbox_tripwire.check(
        tool_name="t", args={"code": "k = os.environ['AWS_SECRET_ACCESS_KEY']"}
    )
    assert d.decision == BLOCKED
    assert "secret-bearing environment variable" in d.violation_detail


def test_tripwire_ast_system_attribute_call_blocked():
    d = sandbox_tripwire.check(tool_name="t", args={"code": "os.system('ls -la')"})
    assert d.decision == BLOCKED
    assert "Forbidden system attribute call 'os.system()'" in d.violation_detail


def test_tripwire_ast_violation_via_nested_list_tuple_args():
    d = sandbox_tripwire.check(
        tool_name="t",
        args={"items": ["import os", ("from sys import exit",)], "note": "x" * 10},
    )
    assert d.decision == BLOCKED
    assert "Forbidden import of module 'os'" in d.violation_detail


# ===========================================================================
# Tripwire — match()/check() core paths
# ===========================================================================


def test_tripwire_match_empty_and_hit_paths():
    assert sandbox_tripwire.match({}) is None
    hit = sandbox_tripwire.match({"command": "DROP TABLE users"})
    assert hit is not None
    assert hit.id == "destructive_drop_table"
    d = sandbox_tripwire.check(tool_name="t", args={"command": "DROP TABLE users"})
    assert d.decision == BLOCKED
    assert d.metadata_json["tripwire_id"] == "destructive_drop_table"


# ===========================================================================
# Tripwire — check() exception paths (fail-closed / fail-open)
# ===========================================================================


def test_tripwire_check_fail_closed_under_enforcement(monkeypatch):
    """A tripwire internal error under enforcement must BLOCK (fail closed)."""
    monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("simulated tripwire registry failure")

    monkeypatch.setattr(sandbox_tripwire, "match", _boom)
    d = sandbox_tripwire.check(tool_name="t", args={"command": "ls"})
    assert d.decision == BLOCKED
    assert d.killrun_triggered is True
    assert d.metadata_json.get("fail_closed") is True
    assert "fail-closed" in d.violation_detail


def test_tripwire_check_fail_open_in_shadow(monkeypatch):
    """In shadow mode a tripwire error must not block legitimate work."""
    monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("simulated tripwire registry failure")

    monkeypatch.setattr(sandbox_tripwire, "match", _boom)
    d = sandbox_tripwire.check(tool_name="t", args={"command": "ls"})
    assert d.decision == ALLOWED
    assert "error" in d.metadata_json


# ===========================================================================
# MegafileDetector + MegafileWarning
# ===========================================================================


def test_megafile_warning_to_harness_patch_proposal():
    w = MegafileWarning(
        file_path="/tmp/big_module.py",
        line_count=1200,
        edit_count=7,
        threshold_loc=800,
        threshold_edits=5,
        severity="CRITICAL",
        recommendation="decompose it",
    )
    p = w.to_harness_patch_proposal()
    assert p["patch_id"] == "megafile_big_module"
    assert p["target_component"] == "file_modularization"
    assert p["mutation_payload"]["file_path"] == "/tmp/big_module.py"
    assert p["mutation_payload"]["current_line_count"] == 1200
    assert p["model_scope"] == "workspace"
    assert p["severity"] == "CRITICAL"


def test_megafile_detector_no_warning_below_thresholds():
    det = MegafileDetector(loc_threshold=800, edit_threshold=5)
    assert det.record_edit("new_project.py", line_count=100) is None
    assert det.is_blocked("new_project.py") is False
    assert det.summary() == [{"file": "new_project.py", "edits": 1}]


def test_megafile_detector_loc_warning_existing_path():
    det = MegafileDetector(loc_threshold=100, edit_threshold=5)
    w = det.record_edit(__file__, line_count=900)
    assert w is not None
    assert w.severity == "WARNING"
    assert w.file_path == str(Path(__file__).resolve())
    assert "900 LOC" in w.recommendation


def test_megafile_detector_edit_threshold_warning():
    det = MegafileDetector(loc_threshold=800, edit_threshold=3)
    assert det.record_edit("hot.py", line_count=10) is None
    assert det.record_edit("hot.py", line_count=10) is None
    w = det.record_edit("hot.py", line_count=10)
    assert w is not None
    assert w.severity == "WARNING"
    assert "3 edits this loop" in w.recommendation
    assert det.is_blocked("hot.py") is True


def test_megafile_detector_critical_both_thresholds():
    det = MegafileDetector(loc_threshold=100, edit_threshold=2)
    det.record_edit("sprawl.py", line_count=500)
    w = det.record_edit("sprawl.py", line_count=600)
    assert w is not None
    assert w.severity == "CRITICAL"
    assert "hotspot megafile" in w.recommendation
    assert det.is_blocked("sprawl.py") is True


def test_megafile_detector_reset_and_summary_order():
    det = MegafileDetector(loc_threshold=1, edit_threshold=1)
    det.record_edit("a.py", line_count=2)
    det.record_edit("b.py", line_count=2)
    det.record_edit("b.py", line_count=2)
    rows = det.summary()
    assert rows == [
        {"file": "b.py", "edits": 2},
        {"file": "a.py", "edits": 1},
    ]
    det.reset()
    assert det.summary() == []
    assert det.is_blocked("a.py") is False


# ===========================================================================
# Caps — estimation internals
# ===========================================================================


def test_caps_payload_char_count_str_bytes_dict_list():
    assert sandbox_caps._payload_char_count({"content": "abcd"}, ("content",)) == 4
    assert sandbox_caps._payload_char_count({"content": b"ab"}, ("content",)) == 2
    assert sandbox_caps._payload_char_count({"content": {"a": 1}}, ("content",)) == len('{"a": 1}')
    assert sandbox_caps._payload_char_count({"content": ["ab", "cd"]}, ("content",)) == len('["ab", \'cd\']'.replace("'", '"'))
    assert sandbox_caps._payload_char_count({"other": "zzz"}, ("content",)) == 0


def test_caps_estimate_write_bytes_mapped_and_non_write_tools():
    assert sandbox_caps.estimate_write_bytes("write_code_file", {"content": "x" * 50}) == 50
    assert sandbox_caps.estimate_write_bytes("write_code_file", {"code": "y" * 30}) == 30
    # write-capable tool with no payload falls back to serialized args size
    assert sandbox_caps.estimate_write_bytes("browser_download_file", {}) >= 2
    # read-only tool never accrues bytes, even with a big content arg
    assert sandbox_caps.estimate_write_bytes("read_file", {"content": "z" * 1000}) == 0


def test_caps_estimate_write_bytes_serialized_fallback():
    est = sandbox_caps.estimate_write_bytes(
        "write_code_file", {"blob": "q" * 200, "n": 7, "nested": [1, 2]}
    )
    assert est > 200


def test_caps_serialized_char_count_exception_fails_closed_to_zero(monkeypatch):
    with mock.patch("json.dumps", side_effect=TypeError("non-serializable")):
        assert sandbox_caps._serialized_char_count({"x": object()}) == 0
        assert sandbox_caps.estimate_write_bytes("write_code_file", {"x": object()}) == 0


def test_caps_estimate_cost_usd_positive_and_zero():
    assert sandbox_caps.estimate_cost_usd("llm_chat", {"prompt": "x" * 100}) == 0.00025
    assert sandbox_caps.estimate_cost_usd("documents.ask_image", {"question": "what?"}) > 0.0
    assert sandbox_caps.estimate_cost_usd("write_code_file", {"content": "z" * 5000}) == 0.0
    assert sandbox_caps.estimate_cost_usd("", {}) == 0.0


def test_caps_estimate_tool_usage_fail_open(monkeypatch):
    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("estimator broke")

    monkeypatch.setattr(sandbox_caps, "estimate_write_bytes", _boom)
    assert sandbox_caps.estimate_tool_usage("t", {}) == (0, 0.0)


# ===========================================================================
# Caps — cap evaluation branches
# ===========================================================================


def test_caps_tool_calls_fast_path_deny():
    policy = _policy(run_id="cov39-fast", max_tool_calls=1)
    assert sandbox_caps.check_caps(policy, tool_name="t", args={}).decision == ALLOWED
    d = sandbox_caps.check_caps(policy, tool_name="t", args={})
    assert d.decision == RESTRICTED
    assert d.metadata_json["cap"] == "max_tool_calls"


def test_caps_bytes_cap_deny_via_recorded_writes():
    policy = _policy(run_id="cov39-bytes", max_bytes_written=100)
    sandbox_caps.record_write(policy, 80)
    d = sandbox_caps.check_caps(policy, tool_name="write_code_file", args={"content": "x" * 30})
    assert d.decision == RESTRICTED
    assert d.metadata_json["cap"] == "max_bytes_written"
    assert d.metadata_json["pending"] == 30


def test_caps_cost_cap_deny_via_recorded_cost():
    policy = _policy(run_id="cov39-cost", max_cost_usd=0.4)
    sandbox_caps.record_cost(policy, 0.4)
    d = sandbox_caps.check_caps(policy, tool_name="llm_chat", args={"prompt": "x" * 800})
    assert d.decision == RESTRICTED
    assert d.metadata_json["cap"] == "max_cost_usd"
    assert d.metadata_json["pending"] > 0.0


def test_caps_check_caps_fail_open_on_error(monkeypatch):
    def _broken_get():  # noqa: ANN202
        raise RuntimeError("registry broken")

    monkeypatch.setattr(sandbox_caps, "get_registry", _broken_get)
    d = sandbox_caps.check_caps(_policy(), tool_name="t", args={})
    assert d.decision == ALLOWED
    assert "error" in d.metadata_json


def test_caps_release_run_clears_counters():
    policy = _policy(run_id="cov39-rel", max_tool_calls=1)
    assert sandbox_caps.check_caps(policy, tool_name="t", args={}).decision == ALLOWED
    assert sandbox_caps.check_caps(policy, tool_name="t", args={}).decision == RESTRICTED
    sandbox_caps.release_run(policy.run_id)
    assert policy.run_id not in sandbox_caps.get_registry()._counters  # type: ignore[attr-defined]
    assert sandbox_caps.check_caps(policy, tool_name="t", args={}).decision == ALLOWED


def test_caps_exec_seconds_cap_exceeded():
    policy = _policy(run_id="cov39-exec", max_exec_seconds=60)
    counters = sandbox_caps.get_registry().get(policy.run_id)
    counters.exec_seconds_started_at = time.time() - 120
    d = sandbox_caps.check_caps(policy, tool_name="t", args={})
    assert d.decision == RESTRICTED
    assert d.metadata_json["cap"] == "max_exec_seconds"


def test_caps_tool_calls_race_deny_under_lock():
    """Simulate a concurrent caller slipping in between the fast-path read
    and the locked re-check: the re-check must still deny."""
    policy = _policy(run_id="cov39-race", max_tool_calls=3)
    counters = sandbox_caps.get_registry().get(policy.run_id)
    counters.tool_calls = 2

    class _BumpLock:
        def __enter__(self):
            counters.tool_calls = 3

        def __exit__(self, *exc):  # noqa: ANN002
            return False

    counters.lock = _BumpLock()  # type: ignore[assignment]
    d = sandbox_caps.check_caps(policy, tool_name="t", args={})
    assert d.decision == RESTRICTED
    assert d.metadata_json["cap"] == "max_tool_calls"


def test_caps_byte_accrual_in_locked_path():
    policy = _policy(run_id="cov39-w", max_bytes_written=10_000)
    d = sandbox_caps.check_caps(policy, tool_name="write_code_file", args={"content": "x" * 40})
    assert d.decision == ALLOWED
    assert d.metadata_json["bytes_written"] == 40


def test_caps_cost_accrual_in_locked_path():
    policy = _policy(run_id="cov39-c", max_cost_usd=1.0)
    d = sandbox_caps.check_caps(policy, tool_name="llm_chat", args={"prompt": "y" * 200})
    assert d.decision == ALLOWED
    assert d.metadata_json["cost_usd"] > 0.0


def test_caps_byte_accrual_unlimited_path():
    policy = _policy(run_id="cov39-w0", max_tool_calls=0, max_bytes_written=0)
    d = sandbox_caps.check_caps(policy, tool_name="write_code_file", args={"content": "z" * 25})
    assert d.decision == ALLOWED
    assert d.metadata_json["bytes_written"] == 25


def test_caps_cost_accrual_unlimited_path():
    policy = _policy(run_id="cov39-c0", max_tool_calls=0, max_cost_usd=0.0)
    d = sandbox_caps.check_caps(policy, tool_name="summarize_doc", args={"text": "w" * 400})
    assert d.decision == ALLOWED
    assert d.metadata_json["cost_usd"] > 0.0


# ===========================================================================
# Caps — record_* / release_run exception containment
# ===========================================================================


def test_caps_record_write_fail_open(monkeypatch):
    def _broken_get():  # noqa: ANN202
        raise RuntimeError("registry broken")

    monkeypatch.setattr(sandbox_caps, "get_registry", _broken_get)
    policy = _policy()
    sandbox_caps.record_write(policy, 100)  # must not raise


def test_caps_record_cost_fail_open(monkeypatch):
    def _broken_get():  # noqa: ANN202
        raise RuntimeError("registry broken")

    monkeypatch.setattr(sandbox_caps, "get_registry", _broken_get)
    policy = _policy()
    sandbox_caps.record_cost(policy, 1.5)  # must not raise


def test_caps_release_run_fail_open(monkeypatch):
    def _broken_get():  # noqa: ANN202
        raise RuntimeError("registry broken")

    monkeypatch.setattr(sandbox_caps, "get_registry", _broken_get)
    sandbox_caps.release_run("cov39-nope")  # must not raise
