"""No-execution helper controls for the prepared child restore smoke.

These tests load the harness/readback modules directly. They never start a
backend, seed a world, call HTTP, use a product database or launch a subprocess.
They pin the path/source-absence/exact-artifact/preflight/wrong-world helpers
that the root-run smoke depends on.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
HARNESS_PATH = SCRIPTS / "acceptance" / "restore_child_smoke.py"
READBACK_PATH = SCRIPTS / "acceptance" / "restore_child_readback.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


smoke = _load("restore_child_smoke_contract", HARNESS_PATH)
readback = _load("restore_child_readback_contract", READBACK_PATH)


@pytest.fixture()
def private_scratch_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "SCRATCH_PARENT", tmp_path)
    monkeypatch.setattr(smoke, "DISK_FLOOR_BYTES", 0)
    repo = tmp_path / "repo"
    repo.mkdir()
    return tmp_path, repo


def test_preflight_is_default_and_execute_is_explicit():
    args = smoke.parse_args(["--scratch", "/private/tmp/example"])
    assert args.execute is False
    assert args.preflight is False

    args = smoke.parse_args(["--preflight", "--scratch", "/private/tmp/example"])
    assert args.execute is False

    args = smoke.parse_args(["--execute", "--scratch", "/private/tmp/example"])
    assert args.execute is True

    with pytest.raises(SystemExit):
        smoke.parse_args(["--execute", "--preflight", "--scratch", "/private/tmp/x"])
    with pytest.raises(SystemExit):
        smoke.parse_args([])


def test_scratch_validation_writes_nothing_and_accepts_fresh_child(
        private_scratch_parent):
    parent, repo = private_scratch_parent
    scratch = parent / "fresh-scratch"
    report = smoke.validate_scratch_path(scratch, repo_root=repo)
    assert report["ok"] is True, report
    assert report["checks"]["under_private_tmp"] is True
    assert report["checks"]["outside_repo"] is True
    assert scratch.exists() is False


def test_scratch_validation_rejects_nonempty_and_symlink(
        private_scratch_parent):
    parent, repo = private_scratch_parent
    scratch = parent / "used-scratch"
    scratch.mkdir()
    (scratch / "world.txt").write_text("occupied", encoding="utf-8")
    report = smoke.validate_scratch_path(scratch, repo_root=repo)
    assert report["ok"] is False
    assert report["checks"]["absent_or_empty_dir"] is False
    assert (scratch / "world.txt").is_file()

    link = parent / "scratch-link"
    link.symlink_to(parent / "fresh-target")
    report = smoke.validate_scratch_path(link, repo_root=repo)
    assert report["ok"] is False
    assert report["checks"]["no_symlink_components"] is False


def test_scratch_validation_rejects_repo_world_and_disk_floor(
        private_scratch_parent, monkeypatch):
    parent, repo = private_scratch_parent
    wrong_world = repo / "backend" / "data" / "acceptance_worlds" / "child"
    wrong_world.mkdir(parents=True)
    report = smoke.validate_scratch_path(wrong_world, repo_root=repo)
    assert report["ok"] is False
    assert report["checks"]["outside_repo"] is False

    monkeypatch.setattr(smoke, "DISK_FLOOR_BYTES", 10**30)
    report = smoke.validate_scratch_path(parent / "disk-floor", repo_root=repo)
    assert report["ok"] is False
    assert report["checks"]["disk_floor_ok"] is False


def test_target_path_accepts_exact_target_and_rejects_both_source_prefixes(
        tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    expected = target / "office" / "artifact.docx"
    expected.parent.mkdir()
    expected.write_bytes(b"artifact")
    missing = tmp_path / "source"
    preserved = tmp_path / "source-unavailable"
    preserved.mkdir()

    report = smoke.resolve_target_managed_path(
        str(expected), expected=str(expected), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved)
    assert report["ok"] is True, report

    wrong_expected = target / "office" / "other.docx"
    report = smoke.resolve_target_managed_path(
        str(expected), expected=str(wrong_expected), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved)
    assert report["ok"] is False
    assert report["checks"]["exact_expected_path"] is False

    missing_path = missing / "office" / "artifact.docx"
    report = smoke.resolve_target_managed_path(
        str(missing_path), expected=str(expected), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved)
    assert report["ok"] is False
    assert report["checks"]["not_original_source"] is False

    preserved_path = preserved / "office" / "artifact.docx"
    preserved_path.parent.mkdir()
    preserved_path.write_bytes(b"artifact")
    report = smoke.resolve_target_managed_path(
        str(preserved_path), expected=str(expected), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved)
    assert report["ok"] is False
    assert report["checks"]["not_preserved_source"] is False


def test_managed_file_requires_exact_hash_and_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    artifact = target / "office" / "artifact.docx"
    artifact.parent.mkdir()
    data = b"exact artifact bytes"
    artifact.write_bytes(data)
    expected_sha = hashlib.sha256(data).hexdigest()
    missing = tmp_path / "source"
    preserved = tmp_path / "source-unavailable"
    preserved.mkdir()

    report = smoke.validate_managed_file(
        str(artifact), expected=str(artifact), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved,
        expected_sha256=expected_sha)
    assert report["ok"] is True, report

    report = smoke.validate_managed_file(
        str(artifact), expected=str(artifact), target_root=target,
        missing_source_root=missing, preserved_source_root=preserved,
        expected_sha256="0" * 64)
    assert report["ok"] is False
    assert report["checks"]["sha256_exact"] is False


def test_exact_artifact_requires_binding_download_and_docx_controls(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    artifact = target / "office" / "artifact.docx"
    artifact.parent.mkdir()
    data = b"docx bytes"
    artifact.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    missing = tmp_path / "source"
    preserved = tmp_path / "source-unavailable"
    preserved.mkdir()

    report = smoke.validate_exact_artifact(
        returned_binding=str(artifact), expected_path=str(artifact),
        target_root=target, missing_source_root=missing,
        preserved_source_root=preserved, expected_sha256=sha,
        disk_sha256=sha, download_sha256=sha,
        docx_valid=True, text_exact=True)
    assert report["ok"] is True, report

    report = smoke.validate_exact_artifact(
        returned_binding=str(artifact), expected_path=str(artifact),
        target_root=target, missing_source_root=missing,
        preserved_source_root=preserved, expected_sha256=sha,
        disk_sha256=sha, download_sha256="f" * 64,
        docx_valid=True, text_exact=True)
    assert report["ok"] is False
    assert report["checks"]["download_sha256_exact"] is False

    report = smoke.validate_exact_artifact(
        returned_binding=str(artifact), expected_path=str(artifact),
        target_root=target, missing_source_root=missing,
        preserved_source_root=preserved, expected_sha256=sha,
        disk_sha256=sha, download_sha256=sha,
        docx_valid=False, text_exact=False)
    assert report["ok"] is False
    assert report["checks"]["docx_valid"] is False
    assert report["checks"]["docx_text_exact"] is False


def test_child_env_is_explicit_testing_zero_and_has_no_provider_keys(tmp_path):
    layout = smoke.build_layout(tmp_path / "scratch")
    secret = "synthetic-not-a-live-secret"
    env = smoke.build_child_env(layout, port=18771, secret_key=secret)
    report = smoke.validate_explicit_env(
        env, layout, port=18771, secret_key=secret)
    assert report["ok"] is True, report
    assert env["TESTING"] == "0"
    assert env["ENVIRONMENT"] == "test"
    assert env["DATABASE_URL"] == f"sqlite:///{layout['target_db']}"
    assert smoke.find_provider_env_keys(env) == []
    assert env["BYOK_CONFIG_FILE"] == str(layout["target"] / "byok_config.json")
    assert env["BYOK_KEYS_FILE"] == str(layout["target"] / "byok_keys.json")
    assert env["BYOK_ENC_KEY_FILE"] == str(
        layout["target"] / "byok_encryption_key")
    assert env["EMBEDDING_REGISTRY_FILE"] == str(
        layout["target"] / "embedding_registry.json")
    assert env["ATOM_PAIR_MEMO_PATH"] == str(
        layout["target"] / "llm_pair_memos.json")
    assert env["ATOM_BPE_DATA_DIR"] == str(
        layout["target"] / "bpe_workspaces")
    assert env["LOG_FILE"] == str(layout["logs"] / "atom.log")
    assert env["AUDIT_LOG_PATH"] == str(layout["logs"] / "audit.log")
    assert env["ATOM_BOOTSTRAP_PASSWORD_FILE"] == str(
        layout["logs"] / "bootstrap_admin_password.txt")
    assert report["checks"]["byok_config_exact"] is True
    assert report["checks"]["byok_keys_exact"] is True
    assert report["checks"]["byok_enc_key_exact"] is True
    assert report["checks"]["embedding_registry_exact"] is True
    assert report["checks"]["pair_memo_exact"] is True
    assert report["checks"]["bpe_data_exact"] is True
    assert report["checks"]["log_file_scratch"] is True
    assert report["checks"]["audit_log_scratch"] is True
    assert report["checks"]["bootstrap_password_file_scratch"] is True

    dirty = dict(env)
    dirty["OPENAI_API_KEY"] = "not-a-real-key"
    assert smoke.find_provider_env_keys(dirty) == ["OPENAI_API_KEY"]
    report = smoke.validate_explicit_env(
        dirty, layout, port=18771, secret_key=secret)
    assert report["ok"] is False
    assert "OPENAI_API_KEY" in report["provider_key_names_present"]

    wrong_testing = dict(env)
    wrong_testing["TESTING"] = "1"
    report = smoke.validate_explicit_env(
        wrong_testing, layout, port=18771, secret_key=secret)
    assert report["ok"] is False
    assert report["checks"]["testing_is_explicit_zero"] is False


def test_source_env_uses_the_source_root_not_the_target(tmp_path):
    layout = smoke.build_layout(tmp_path / "scratch")
    env = smoke.build_source_env(layout, secret_key="synthetic-secret")
    assert env["DATABASE_URL"] == f"sqlite:///{layout['source'] / 'atom.db'}"
    assert env["ATOM_DATA_DIR"] == str(layout["source"])
    assert env["TESTING"] == "0"


def test_health_identity_requires_pid_cwd_db_revision_and_source_binding(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    target_db = tmp_path / "target" / "atom.db"
    target_db.parent.mkdir()
    target_db.write_bytes(b"")
    revision = "a" * 40
    source_id = revision[:12]
    identity = {
        "pid": 123,
        "cwd": str(backend),
        "backend_path": str(backend),
        "database": str(target_db),
        "revision": revision,
        "source_id": source_id,
        "instance_id": f"{source_id}.123.1",
        "port": 18771,
        "dirty": False,
        "dirty_paths": [],
        "untracked_paths": ["LEAD_NEXT.md", "opencode.jsonc"],
    }
    report = smoke.validate_health_identity(
        identity, pid=123, port=18771, backend_root=backend,
        target_db=target_db, expected_revision=revision)
    assert report["ok"] is True, report

    mutations = {
        "pid": (124, "pid_exact"),
        "cwd": (str(tmp_path / "foreign"), "cwd_exact"),
        "database": (str(tmp_path / "foreign.db"), "database_exact"),
        "revision": ("b" * 40, "revision_exact"),
        "dirty_paths": (["backend/core/models.py"], "no_tracked_product_dirty"),
        "untracked_paths": (["backend/core/untracked.py"],
                            "untracked_non_product_only"),
        "instance_id": (f"{source_id}.999.1", "instance_bound"),
        "port": (18772, "port_exact"),
    }
    for field, (value, failed_check) in mutations.items():
        changed = dict(identity)
        changed[field] = value
        report = smoke.validate_health_identity(
            changed, pid=123, port=18771, backend_root=backend,
            target_db=target_db, expected_revision=revision)
        assert report["ok"] is False, (field, report)
        assert report["checks"][failed_check] is False, (field, report)


def test_dirty_source_is_allowed_only_for_named_non_product_handoffs(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    target_db = tmp_path / "target" / "atom.db"
    target_db.parent.mkdir()
    target_db.write_bytes(b"")
    revision = "c" * 40
    source_id = revision[:12] + "-dirty.abc123"
    identity = {
        "pid": 55,
        "cwd": str(backend),
        "backend_path": str(backend),
        "database": str(target_db),
        "revision": revision,
        "source_id": source_id,
        "instance_id": f"{source_id}.55.1",
        "port": 18771,
        "dirty": True,
        "dirty_paths": [],
        "untracked_paths": ["LEAD_NEXT.md"],
    }
    report = smoke.validate_health_identity(
        identity, pid=55, port=18771, backend_root=backend,
        target_db=target_db, expected_revision=revision)
    assert report["ok"] is True, report

    identity["untracked_paths"] = ["scripts/acceptance/new_product.py"]
    report = smoke.validate_health_identity(
        identity, pid=55, port=18771, backend_root=backend,
        target_db=target_db, expected_revision=revision)
    assert report["ok"] is False


def test_named_booleans_reject_empty_and_non_true_values():
    with pytest.raises(smoke.HarnessError):
        smoke.check_named_booleans({})
    report = smoke.check_named_booleans({"one": True, "two": True})
    assert report["ok"] is True
    report = smoke.check_named_booleans({"one": True, "two": False})
    assert report["ok"] is False
    assert report["failed_checks"] == ["two"]
    report = smoke.check_named_booleans({"one": True, "two": 1})
    assert report["ok"] is False
    assert report["failed_checks"] == ["two"]


def test_sandbox_profile_denies_network_except_loopback_port():
    profile = smoke.sandbox_profile(18771)
    assert "(deny network*)" in profile
    assert 'localhost:18771' in profile
    assert "(allow network-inbound (local ip4))" in profile


def test_readback_docx_helper_requires_real_docx_and_text(tmp_path):
    from docx import Document
    doc = Document()
    doc.add_paragraph("child restore smoke office artifact")
    path = tmp_path / "artifact.docx"
    doc.save(path)
    result = readback._docx_check(
        path.read_bytes(), "child restore smoke office artifact")
    assert result["valid"] is True
    assert result["text_exact"] is True
    invalid = readback._docx_check(b"not a docx", "child restore smoke")
    assert invalid["valid"] is False
    assert invalid["text_exact"] is False


def test_readback_parquet_helper_requires_real_rows(tmp_path):
    import pandas as pd
    path = tmp_path / "sheet.parquet"
    pd.DataFrame({"value": [1, 2]}).to_parquet(path, index=False)
    result = readback._parquet_check(path, ["value"], [[1], [2]])
    assert result["readable"] is True
    assert result["columns_exact"] is True
    assert result["rows_exact"] is True
    result = readback._parquet_check(path, ["value"], [[9], [9]])
    assert result["rows_exact"] is False


@pytest.mark.parametrize("extra_action", [None, "update"])
def test_audit_result_checks_real_rows_and_rejects_extra_effect(tmp_path, extra_action):
    import json
    import sqlite3
    db = tmp_path / "audit.db"
    con = sqlite3.connect(db)
    columns = ["id", "action_type", "details_json", "tenant_id", "canvas_id",
               "user_id", "agent_id", "session_id", "episode_id"]
    con.execute("CREATE TABLE canvas_audit (" + ",".join(c + " TEXT" for c in columns) + ")")
    original = dict(zip(columns, ["old", "create", "{}", "t", "c", "u", None, None, None]))
    provenance = {"audit_id": "old", "restore_event_id": "new", "manifest_sha256": "manifest",
                  "original_details_sha256": "details", "source_data_dir": "/source",
                  "target_data_dir": "/target", "binding": "rebased_to_target",
                  "source_canvas_tenant_id": "t", "source_audit_tenant_id": "t"}
    con.execute("INSERT INTO canvas_audit VALUES (?,?,?,?,?,?,?,?,?)", list(original.values()))
    con.execute("INSERT INTO canvas_audit VALUES (?,?,?,?,?,?,?,?,?)",
                ["new", "restore", json.dumps({"restored_from": provenance}), "t", "c", None, None, None, None])
    if extra_action:
        con.execute("INSERT INTO canvas_audit VALUES (?,?,?,?,?,?,?,?,?)",
                    ["extra", extra_action, "{}", "t", "c", "u", None, None, None])
    con.commit(); con.close()
    baseline = {"audit": {"rows": [original], "columns": columns,
                          "original_rows_sha256": readback._canonical_hash([original]),
                          "original_details_sha256": "details"},
                "restore": {"manifest_sha256": "manifest", "source_data_dir": "/source",
                            "target_data_dir": "/target"}}
    result = readback._audit_result(db, baseline, {"audit_id": "old", "tenant_id": "t", "canvas_id": "c"})
    assert result["original_unchanged"] is True
    assert result["non_restore_new_rows"] == (1 if extra_action else 0)
    assert result["ok"] is (extra_action is None)
