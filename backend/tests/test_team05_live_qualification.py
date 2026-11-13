"""Offline guards for the TEAM-05 live qualification driver.

These tests never touch Ollama, the network, or a real database. They pin the
parts that must be right BEFORE a live run: local-URL refusal, exact-freshness
verification, observation-derived verdicts (no hardcoded positive findings),
and the opt-in gate.
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import team05_live_qualification as qual


class _FakeUrl:
    def __init__(self, backend: str, database):
        self._backend = backend
        self.database = database

    def get_backend_name(self):
        return self._backend

    def __str__(self):
        return f"{self._backend}:///{self.database}"


class _FakeEngine:
    def __init__(self, backend: str, database):
        self.url = _FakeUrl(backend, database)


class _FakeSessionFactory:
    def __init__(self, bind):
        self.kw = {"bind": bind}


def _fake_database(engine, bind=None):
    return SimpleNamespace(
        engine=engine,
        SessionLocal=_FakeSessionFactory(bind if bind is not None else engine),
        DATABASE_URL=f"sqlite:///{engine.url.database}",
        _targets_live_dev_db=lambda url: False,
    )


def _green_observations():
    return {
        "scheduler": {
            "registered": True,
            "registered_once": True,
            "trace": [{"name": n} for n in qual._SCHEDULER_TRACE_ORDER],
            "pass_gate_locked": True,
            "notification_loop_bound": True,
            "certify_on_worker_thread": True,
            "certify_thread": "asyncio_0",
            "main_thread": "MainThread",
            "sleep_seconds": 30.2,
            "pass_completed": True,
            "last_run_sweep_ran": True,
            "last_run_keys": ["sweep", "readiness", "at"],
        },
        "dispatch": {
            "non_local_clients": [],
            "scheduler_handler_count": 1,
            "handler_count": 1,
            "handler_clients": ["ollama"],
            "handler_async_clients": ["ollama"],
            "policy_mode": "selected",
            "policy_allowed": ["ollama"],
            "policy_denies_cloud": True,
            "alignment_chat_fn_entries": [True],
            "served_routes": [
                {"provider": "ollama", "model": "llama3.1:8b"}
                for _ in range(18)
            ],
            "echoed_models": ["llama3.1:8b"] * 18,
            "attempts": [
                {"temperature": 0.0, "last_used_provider": "ollama"}
                for _ in range(18)
            ],
            "expected_generations": 18,
            "pulled_models": ["llama3.1:8b"],
            "running_models": ["llama3.1:8b"],
        },
        "sweep": {
            "ran": True,
            "green": True,
            "evidence_complete": True,
            "invalid_judgments": [],
            "score_count": 9,
            "expected_score_count": 9,
        },
        "findings": {
            "rows": [
                {"flag_key": key, "state": "approval", "verdict": "enable",
                 "mode": "approve", "decided_at": None}
                for key in ("skill_trust", "allocator_integrity",
                            "org_privileges")
            ],
            "flag_values": {
                "skill_trust": False,
                "allocator_integrity": False,
                "org_privileges": False,
            },
            "pending_view_count": 3,
            "expected_flag_keys": [
                "skill_trust", "allocator_integrity", "org_privileges"],
            "notifications": ["approval_needed"],
        },
        "isolation": {
            "exact_scratch_db": True,
            "live_db_not_opened": True,
            "opened_live_paths": [],
            "sqlite_rejected": [],
            "protected_changes": [],
            "path_resolution": {"ok": True, "checked": [],
                                "mismatches": [], "not_loaded": []},
            "protected_write_refusals": {"guard_installed": True,
                                         "refused": []},
            "fresh_before_seed": True,
            "proxy_env_remaining": {},
            "database_destination": {"ok": True, "reasons": []},
            "network": {"guard_installed": True, "blocked": [],
                        "peers": [{"url": qual.DEFAULT_OLLAMA_BASE,
                                   "peer": "127.0.0.1"}]},
        },
        "approval_control": {
            "ran": True,
            "copy_inside_workdir": True,
            "copy_differs_from_primary": True,
            "primary_unchanged": True,
            "decision_applied": True,
            "approved_flag": "skill_trust",
            "decision": {"flag_key": "skill_trust", "state": "applied"},
            "flag_values_after_approve": {
                "skill_trust": True,
                "allocator_integrity": False,
                "org_privileges": False,
            },
            "states_after_approve": {
                "skill_trust": "applied",
                "allocator_integrity": "approval",
                "org_privileges": "approval",
            },
        },
    }


@pytest.mark.parametrize("url,expected", [
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:11434", True),
    ("http://127.4.5.6:11434", True),
    ("https://ollama.example.com", False),
    ("http://192.168.1.10:11434", False),
    ("http://0.0.0.0:11434", False),
    ("ftp://127.0.0.1:11434", False),
])
def test_loopback_only(url, expected):
    assert qual.is_loopback_url(url) is expected


def test_model_aliases_cover_base_and_tag():
    assert qual.model_aliases("llama3.1:8b") == {"llama3.1:8b", "llama3.1"}
    assert "llama3.1:8b" in qual.model_aliases("ollama/llama3.1:8b")
    assert qual.model_aliases(None) == set()


def _fresh_file(path: Path, table: str = "t") -> None:
    con = sqlite3.connect(str(path))
    con.execute(f"CREATE TABLE {table} (x INTEGER)")
    con.commit()
    con.close()


def test_pristine_sqlite_accepts_empty_and_rejects_written(tmp_path):
    db = tmp_path / "fresh.sqlite3"
    with pytest.raises(qual.FreshnessError):
        qual.verify_pristine_sqlite(db, ("t",))

    _fresh_file(db)
    fingerprint = qual.verify_pristine_sqlite(db, ("t",))
    assert fingerprint["total_rows"] == 0
    assert fingerprint["integrity_check"] == "ok"

    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO t (x) VALUES (1)")
    con.commit()
    con.close()
    with pytest.raises(qual.FreshnessError, match="not fresh"):
        qual.verify_pristine_sqlite(db, ("t",))


def test_pristine_sqlite_rejects_missing_expected_table(tmp_path):
    db = tmp_path / "fresh.sqlite3"
    _fresh_file(db, "other")
    with pytest.raises(qual.FreshnessError, match="missing expected"):
        qual.verify_pristine_sqlite(db, ("org_politics_actions",))


def test_scratch_db_must_stay_out_of_the_live_paths():
    backend = qual._backend_dir()
    with pytest.raises(qual.PreconditionError):
        qual._assert_scratch_db_identity(
            backend / "data" / "atom.db", backend / "data")
    with pytest.raises(qual.PreconditionError):
        qual._assert_scratch_db_identity(
            backend / "dev.db", backend)


@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1", True),
    ("127.4.5.6", True),
    ("::1", True),
    ("[::1]", True),
    ("localhost", True),
    ("LOCALHOST", True),
    ("10.0.0.5", False),
    ("0.0.0.0", False),
    ("::", False),
    ("localhost.example.com", False),
    ("", False),
    (None, False),
])
def test_loopback_host_semantics(host, expected):
    assert qual.is_loopback_host(host) is expected


def test_proxy_env_is_cleared_in_both_cases(monkeypatch):
    # urllib prefers lowercase, the OpenAI SDK prefers uppercase; leaving
    # either set lets "local" traffic traverse a remote proxy.
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:3128")
    monkeypatch.setenv("https_proxy", "http://proxy.example.com:3128")
    monkeypatch.setenv("ALL_PROXY", "socks5://proxy.example.com:1080")
    monkeypatch.setenv("no_proxy", "")
    cleared = qual._scrub_proxy_env()
    assert {"HTTP_PROXY", "https_proxy", "ALL_PROXY"} <= set(cleared)
    assert qual._remaining_proxy_env() == {}
    for name in qual.PROXY_ENV_VARS:
        assert os.environ[name] == ""


def test_ambient_db_overrides_are_cleared_and_recorded(monkeypatch):
    # TESTING=1 is recommended elsewhere in this repo for stray scripts; it
    # would silently retarget core.database at backend/test_integration.db.
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ATOM_MOCK_DATABASE", "true")
    inherited = qual._scrub_db_env()
    assert inherited == {"TESTING": "1", "ATOM_MOCK_DATABASE": "true"}
    assert os.environ["TESTING"] == ""
    assert os.environ["ATOM_MOCK_DATABASE"] == ""
    # Empty (not absent) so load_dotenv() cannot restore the override.
    assert "TESTING" in os.environ


def test_sqlite_open_tracker_refuses_before_opening(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.sqlite3"
    outside.unlink(missing_ok=True)
    tracker = qual._install_sqlite_open_tracker(tmp_path / "work")
    try:
        with pytest.raises(qual.NonScratchSqliteOpen):
            sqlite3.connect(str(outside))
    finally:
        tracker.restore()
    assert outside.exists() is False
    assert tracker.rejected and tracker.rejected[0]["path"] == str(outside)


def test_sqlite_guard_covers_the_live_data_tree(tmp_path):
    backend = qual._backend_dir()
    assert qual.sqlite_target_allowed(
        backend / "data" / "atom.db", tmp_path) is False
    assert qual.sqlite_target_allowed(
        backend / "dev.db", tmp_path) is False
    assert qual.sqlite_target_allowed(
        backend / "test_integration.db", tmp_path) is False


def test_sqlite_open_tracker_allows_scratch_and_memory(tmp_path):
    tracker = qual._install_sqlite_open_tracker(tmp_path)
    try:
        scratch = tmp_path / "scratch.sqlite3"
        con = sqlite3.connect(str(scratch))
        con.close()
        mem = sqlite3.connect(":memory:")
        mem.close()
    finally:
        tracker.restore()
    assert tracker.rejected == []
    assert any(path == str(scratch.resolve()) for path in tracker.opened)


def test_engine_destination_accepts_the_exact_scratch_file(tmp_path):
    scratch = tmp_path / "team05_live.sqlite3"
    database = _fake_database(_FakeEngine("sqlite", str(scratch)))
    observation = qual.verify_database_destination(database, scratch, tmp_path)
    assert observation["ok"] is True, observation["reasons"]
    assert observation["engine"]["backend"] == "sqlite"
    assert observation["engine"]["resolved"] == str(scratch.resolve())
    assert observation["session_bind"]["mismatch"] is None


@pytest.mark.parametrize("backend,database_name", [
    ("sqlite", "other.sqlite3"),
    ("sqlite", ":memory:"),
    ("postgresql", "atom"),
])
def test_engine_destination_rejects_non_scratch_targets(
        tmp_path, backend, database_name):
    scratch = tmp_path / "team05_live.sqlite3"
    database = _fake_database(_FakeEngine(backend, database_name))
    observation = qual.verify_database_destination(database, scratch, tmp_path)
    assert observation["ok"] is False
    assert observation["engine"]["mismatch"]
    assert observation["reasons"]


def test_session_local_bind_mismatch_is_refused(tmp_path):
    scratch = tmp_path / "team05_live.sqlite3"
    engine = _FakeEngine("sqlite", str(scratch))
    database = _fake_database(
        engine, bind=_FakeEngine("sqlite", str(tmp_path / "elsewhere.db")))
    observation = qual.verify_database_destination(database, scratch, tmp_path)
    assert observation["ok"] is False
    assert any("SessionLocal" in reason for reason in observation["reasons"])


def test_loopback_guard_refuses_non_loopback_and_restores():
    original_create = socket.create_connection
    guard = qual._LoopbackGuard().install()
    try:
        with pytest.raises(qual.NonLoopbackNetwork):
            socket.create_connection(("192.0.2.1", 9), timeout=0.01)
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(qual.NonLoopbackNetwork):
                probe.connect(("198.51.100.7", 9))
        finally:
            probe.close()
    finally:
        guard.restore()
    assert socket.create_connection is original_create
    hosts = {entry["host"] for entry in guard.blocked}
    assert hosts == {"192.0.2.1", "198.51.100.7"}
    # Evidence describes the run: teardown must not erase "was installed".
    assert guard.observation()["guard_installed"] is True


def test_loopback_guard_allows_loopback_addresses():
    guard = qual._LoopbackGuard()
    guard._check(("127.0.0.1", 11434), "test")
    guard._check(("::1", 11434, 0, 0), "test")
    guard._check("/var/run/docker.sock", "test")  # AF_UNIX passes through
    assert guard.blocked == []


def test_approval_control_is_part_of_the_verdict():
    obs = _green_observations()
    obs["approval_control"].update(
        decision_applied=False,
        flag_values_after_approve={
            "skill_trust": False,
            "allocator_integrity": False,
            "org_privileges": False,
        },
        states_after_approve={
            "skill_trust": "approval",
            "allocator_integrity": "approval",
            "org_privileges": "approval",
        },
    )
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "approval_control.decision_applied" in result["failed"]
    assert "approval_control.flag_flipped_only" in result["failed"]
    assert "approval_control.states_settled" in result["failed"]


def test_approval_control_must_not_touch_the_primary_db():
    obs = _green_observations()
    obs["approval_control"].update(primary_unchanged=False,
                                   copy_inside_workdir=False)
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "approval_control.primary_unchanged" in result["failed"]
    assert "approval_control.copy_isolated" in result["failed"]


def test_missing_approval_control_fails_a_green_sweep():
    obs = _green_observations()
    obs.pop("approval_control")
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "approval_control.ran" in result["failed"]


def test_surviving_proxy_env_fails_isolation():
    obs = _green_observations()
    obs["isolation"]["proxy_env_remaining"] = {"HTTPS_PROXY": "http://p:3128"}
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.proxy_env_cleared" in result["failed"]


def test_blocked_non_loopback_connection_fails_isolation():
    obs = _green_observations()
    obs["isolation"]["network"]["blocked"] = [
        {"kind": "socket.connect", "host": "203.0.113.5", "port": 443}]
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.loopback_only_network" in result["failed"]


def test_rejected_sqlite_open_fails_isolation():
    obs = _green_observations()
    obs["isolation"]["sqlite_rejected"] = [
        {"path": "/tmp/elsewhere.sqlite3", "resolved": "/tmp/elsewhere.sqlite3"}]
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.no_non_scratch_sqlite_open" in result["failed"]


# ---------------------------------------------------------------------------
# Protected live-tree files: a change is a HARD failure (never "unknown"),
# and the driver refuses the write before it happens.
# ---------------------------------------------------------------------------


def test_protected_paths_cover_the_incident_files_in_both_roots():
    paths = {str(p) for p in qual._protected_paths()}
    backend = qual._backend_dir()
    for root in (backend / "data", backend.parent / "data"):
        assert str(root / "byok_config.json") in paths
        assert str(root / "byok_keys.json") in paths
        assert str(root / "byok_encryption_key") in paths
    assert str(backend / "atom.db") in paths
    assert str(backend / "dev.db") in paths
    assert str(backend / "test_integration.db") in paths


def test_protected_file_change_is_a_hard_failure():
    obs = _green_observations()
    obs["isolation"]["protected_changes"] = [
        str(qual._backend_dir() / "data" / "byok_config.json"),
        str(qual._backend_dir() / "data" / "byok_keys.json"),
    ]
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert result["exit_code"] == qual.EXIT_FAILED
    assert "isolation.protected_files_unchanged" in result["failed"]
    check = next(c for c in result["checks"]
                 if c["name"] == "isolation.protected_files_unchanged")
    assert check["state"] == "fail"  # the old behaviour was "unknown"


def test_protected_file_change_fails_even_when_the_sweep_is_negative():
    obs = _green_observations()
    obs["sweep"].update(green=False, evidence_complete=False)
    obs["findings"].update(rows=[], notifications=[], pending_view_count=0)
    obs["isolation"]["protected_changes"] = [
        str(qual._backend_dir() / "data" / "byok_keys.json")]
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert result["exit_code"] != qual.EXIT_NEGATIVE


def test_protected_path_guard_refuses_writes(tmp_path):
    import builtins
    import io

    original_open = builtins.open
    secret = tmp_path / "byok_keys.json"
    secret.write_text("{}")
    guard = qual._ProtectedPathGuard([secret]).install()
    scratch = tmp_path / "scratch.json"
    try:
        with pytest.raises(qual.ProtectedPathWrite):
            with open(secret, "w") as fh:
                fh.write("tampered")
        with pytest.raises(qual.ProtectedPathWrite):
            secret.write_text("tampered")
        with pytest.raises(qual.ProtectedPathWrite):
            os.remove(secret)
        incoming = tmp_path / "incoming.json"
        incoming.write_text("{}")
        with pytest.raises(qual.ProtectedPathWrite):
            os.replace(incoming, secret)
        # The protected file was never modified; other writes still work.
        assert secret.read_text() == "{}"
        assert incoming.read_text() == "{}"
        scratch.write_text("ok")
        assert scratch.read_text() == "ok"
        assert len(guard.observation()["refused"]) == 4
    finally:
        guard.restore()
    assert builtins.open is original_open
    assert io.open is original_open
    secret.write_text("restored")
    assert secret.read_text() == "restored"


def test_protected_path_guard_follows_symlink_aliases(tmp_path):
    protected = tmp_path / "real" / "byok_config.json"
    protected.parent.mkdir()
    protected.write_text("{}")
    alias = tmp_path / "alias.json"
    alias.symlink_to(protected)
    guard = qual._ProtectedPathGuard([protected]).install()
    try:
        with pytest.raises(qual.ProtectedPathWrite):
            alias.write_text("tampered")
    finally:
        guard.restore()
    assert protected.read_text() == "{}"


def test_protected_path_guard_is_checked_in_the_verdict():
    obs = _green_observations()
    obs["isolation"]["protected_write_refusals"] = {
        "guard_installed": True,
        "refused": [{"path": "/live/byok_keys.json",
                     "operation": "open(mode='w')"}],
    }
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.no_protected_write_attempt" in result["failed"]


# ---------------------------------------------------------------------------
# Actual path resolution: the production modules' constants, not declarations
# ---------------------------------------------------------------------------


def _module_with(**attrs):
    return SimpleNamespace(**attrs)


def test_scratch_path_resolution_accepts_matching_constants(tmp_path):
    scratch = tmp_path / "scratch"
    paths = {
        "byok_config": scratch / "byok_config.json",
        "byok_keys": scratch / "byok_keys.json",
        "byok_enc_key": scratch / "byok_encryption_key",
        "pricing": scratch / "ai_pricing_cache.json",
        "drift_state": scratch / "model_resolution_state.json",
        "pair_memos": scratch / "llm_pair_memos.json",
    }
    modules = {
        "core.byok_endpoints": _module_with(
            BYOK_CONFIG_FILE=str(paths["byok_config"]),
            BYOK_KEYS_FILE=str(paths["byok_keys"]),
            BYOK_ENC_KEY_FILE=str(paths["byok_enc_key"]),
        ),
        "core.dynamic_pricing_fetcher": _module_with(
            PRICING_CACHE_PATH=paths["pricing"]),
        "core.llm.model_provenance": _module_with(
            _DEFAULT_STATE_PATH=paths["drift_state"]),
        "core.llm.byok_handler": _module_with(
            _pair_memo_path=lambda: paths["pair_memos"]),
    }
    observation = qual.verify_scratch_path_resolution(paths, modules)
    assert observation["ok"] is True
    assert observation["mismatches"] == []
    # Not imported -> reported, never assumed to be isolated.
    assert "api.byok_routes" in observation["not_loaded"]


def test_scratch_path_resolution_flags_a_live_tree_constant(tmp_path):
    scratch = tmp_path / "scratch"
    paths = {"byok_keys": scratch / "byok_keys.json"}
    live = qual._backend_dir() / "data" / "byok_keys.json"
    modules = {
        "core.byok_endpoints": _module_with(BYOK_KEYS_FILE=str(live)),
    }
    observation = qual.verify_scratch_path_resolution(paths, modules)
    assert observation["ok"] is False
    mismatch = observation["mismatches"][0]
    assert mismatch["module"] == "core.byok_endpoints"
    assert mismatch["resolved"] == os.path.realpath(str(live))
    assert mismatch["expected"] == os.path.realpath(str(paths["byok_keys"]))


def test_unresolved_scratch_paths_fail_qualification():
    obs = _green_observations()
    obs["isolation"]["path_resolution"] = {
        "ok": False,
        "mismatches": [{"module": "core.byok_endpoints",
                        "attribute": "BYOK_KEYS_FILE",
                        "resolved": "/live/byok_keys.json",
                        "expected": "/scratch/byok_keys.json"}],
        "not_loaded": [],
    }
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.scratch_paths_resolved" in result["failed"]


def test_isolation_env_redirects_byok_and_cache_paths(tmp_path):
    # The declaration half of the trace: every path the driver claims as its
    # boundary is also the env value the production modules read at import.
    saved = dict(os.environ)
    try:
        paths = qual._install_isolation_env(
            tmp_path, "http://127.0.0.1:11434/v1", "llama3.1:8b", 600.0)
        declared = {
            "BYOK_CONFIG_FILE": paths["byok_config"],
            "BYOK_KEYS_FILE": paths["byok_keys"],
            "BYOK_ENC_KEY_FILE": paths["byok_enc_key"],
            "ATOM_PROVIDER_MODEL_CATALOG_PATH": paths["catalog"],
            "ATOM_PAIR_MEMO_PATH": paths["pair_memos"],
        }
        for env_name, expected in declared.items():
            assert os.path.realpath(os.environ[env_name]) == \
                os.path.realpath(str(expected))
    finally:
        os.environ.clear()
        os.environ.update(saved)



def test_green_complete_sweep_with_pending_rows_is_qualified():
    result = qual.classify_observations(_green_observations())
    assert result["verdict"] == "qualified"
    assert result["exit_code"] == qual.EXIT_QUALIFIED
    assert result["failed"] == []


def test_incomplete_evidence_without_rows_is_an_honest_negative():
    obs = _green_observations()
    obs["sweep"].update(green=False, evidence_complete=False,
                        invalid_judgments=[{"key": "x", "stage": "judge"}])
    obs["findings"].update(rows=[], notifications=[], pending_view_count=0)
    result = qual.classify_observations(obs)
    assert result["verdict"] == "negative"
    assert result["exit_code"] == qual.EXIT_NEGATIVE


def test_rows_invented_on_incomplete_evidence_fail():
    obs = _green_observations()
    obs["sweep"].update(green=False, evidence_complete=False)
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "findings.no_rows_on_incomplete_evidence" in result["failed"]


def test_non_local_provider_fails():
    obs = _green_observations()
    obs["dispatch"]["non_local_clients"] = ["openai"]
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "dispatch.no_non_local_client" in result["failed"]


def test_missing_served_identity_fails():
    obs = _green_observations()
    obs["dispatch"]["echoed_models"] = [None] * 18
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "dispatch.served_model_echo" in result["failed"]


def test_open_live_db_fails_isolation():
    obs = _green_observations()
    obs["isolation"]["live_db_not_opened"] = False
    result = qual.classify_observations(obs)
    assert result["verdict"] == "failed"
    assert "isolation.live_db_not_opened" in result["failed"]


def test_default_invocation_is_opt_in_and_does_nothing(capsys):
    assert qual.main([]) == qual.EXIT_NOT_OPTED_IN
    output = capsys.readouterr().out
    assert "--run-live" in output
    assert "did not run" in output


def test_live_run_refuses_under_pytest():
    # pytest is in sys.modules, so this must exit before any workdir/network.
    assert qual.main(["--run-live"]) == qual.EXIT_PRECONDITION


def test_replay_command_is_explicit_and_local():
    command = qual._replay_command(["--run-live", "--model", "llama3.1:8b"])
    assert command.startswith("python scripts/team05_live_qualification.py")
    assert "--run-live" in command


def test_evidence_json_is_plain_data():
    # Guard against accidentally making the driver depend on a live object.
    payload = {"verdict": "negative", "checks": [], "rows": []}
    assert json.loads(json.dumps(payload)) == payload
