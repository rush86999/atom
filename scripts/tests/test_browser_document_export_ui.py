"""Pure helper guards for the prepared Documents stored-text export driver.

These tests do not launch a world, server, browser, model or download. They
exercise only the anti-false-positive logic that decides whether a browser
download really is the same bytes as the corresponding export API response.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
DRIVER_PATH = REPO / "scripts" / "acceptance" / "browser_document_export_ui.py"


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_document_export_ui_helpers", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_checksums(fixtures: Path, digests: dict[str, str]) -> None:
    lines = [f"{digest}  ./{name}\n" for name, digest in digests.items()]
    (fixtures / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.invalid",
         "-c", "user.name=Fixture Test", "-c", "commit.gpgsign=false",
         *args],
        capture_output=True, text=True, check=True)
    return proc.stdout


def _commit(repo: Path, message: str = "fixtures", *paths: str) -> None:
    targets = ["--", *paths] if paths else ["-A"]
    _git(repo, "add", *targets)
    _git(repo, "commit", "-q", "-m", message)


def _fixture_repo(tmp_path: Path, files: dict[str, bytes]):
    repo = tmp_path / "repo"
    fixtures = repo / "fixtures"
    fixtures.mkdir(parents=True)
    for name, blob in files.items():
        path = fixtures / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    _write_checksums(fixtures, {name: _sha(blob) for name, blob in files.items()})
    _git(repo, "init", "-q")
    _commit(repo)
    return repo, fixtures


def _headers(driver, export_format: str, body: bytes, text: str,
             doc_id: str, version: str, filename: str) -> dict:
    expected_name = driver._expected_download_name(
        filename, export_format, doc_id)
    headers = {
        "content-type": driver.FORMAT_CONTENT_TYPE[export_format],
        "content-disposition": f'attachment; filename="{expected_name}"',
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
        "x-document-id": doc_id,
        "x-document-content-kind": "extracted_text",
        "x-document-provenance": "authoritative",
        "x-document-source-version": version,
        "x-document-source-version-kind": "versioned",
        "x-document-source-version-status": "matched",
        "x-document-freshness": "fresh",
        "x-document-stored-text-sha256": _sha(text.encode("utf-8")),
        "x-document-export-sha256": _sha(body),
    }
    if export_format == "markdown":
        headers["x-document-export-transform"] = "none"
    return headers


def _json_body(text: str, doc_id: str, version: str, filename: str) -> bytes:
    payload = {
        "schema_version": 1,
        "document_id": doc_id,
        "title": filename,
        "file_name": filename,
        "file_type": "txt",
        "source": "manual_upload",
        "source_version": version,
        "source_version_kind": "versioned",
        "source_version_status": "matched",
        "freshness_status": "fresh",
        "provenance_status": "authoritative",
        "content_kind": "extracted_text",
        "format": "json",
        "reader": "lancedb.documents.get_document_by_id",
        "stored_text_bytes": len(text.encode("utf-8")),
        "stored_text_truncated": None,
        "stored_text_sha256": _sha(text.encode("utf-8")),
        "content": text,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _proof(driver, export_format: str, text: str, doc_id: str,
           version: str, filename: str, *, body: bytes | None = None,
           downloaded: bytes | None = None, headers: dict | None = None):
    if body is None:
        if export_format == "json":
            body = _json_body(text, doc_id, version, filename)
        else:
            body = text.encode("utf-8")
    if downloaded is None:
        downloaded = body
    if headers is None:
        headers = _headers(
            driver, export_format, body, text, doc_id, version, filename)
    return driver._verify_export_payload(
        export_format=export_format,
        api_bytes=body,
        downloaded_bytes=downloaded,
        expected_text=text,
        tail_marker=text.rstrip("\n").split("\n")[-1],
        doc_id=doc_id,
        expected_version=version,
        headers=headers,
        expected_filename=driver._expected_download_name(
            filename, export_format, doc_id),
        source_filename=filename,
    )


def test_fixture_is_over_20k_with_a_unique_final_tail(driver):
    filename, text, tail = driver._fixture_document("abc123")
    assert filename.endswith(".txt")
    assert len(text) > 20000
    assert text.count(tail) == 1
    assert text.rstrip("\n").endswith(tail)
    assert "[SYNTHETIC USER FILE]" in text


def test_expected_download_name_matches_frontend_rules(driver):
    assert driver._expected_download_name(
        "report.final.txt", "text", "doc_" + "a" * 24
    ) == "report.final.txt"
    assert driver._expected_download_name(
        "a/b:c?.txt", "markdown", "doc_" + "b" * 24
    ) == "a_b_c_.md"
    assert driver._expected_download_name(
        "x.pdf", "json", "doc_" + "c" * 24
    ) == "x.json"


def test_content_disposition_parses_ascii_and_rfc5987(driver):
    parsed = driver._parse_content_disposition(
        'attachment; filename="simple.txt"')
    assert parsed["decoded"] == "simple.txt"
    parsed = driver._parse_content_disposition(
        "attachment; filename=\"cafe.txt\"; "
        "filename*=utf-8''caf%C3%A9.txt")
    assert parsed["decoded"] == "café.txt"


def test_query_key_names_keeps_forbidden_keys(driver):
    assert driver._query_key_names(
        "http://localhost:1/api/documents/x/export?format=text&path=/tmp"
    ) == ["format", "path"]
    assert driver._has_forbidden_export_query(
        "http://localhost:1/api/documents/x/export?format=text&path=/tmp")
    assert not driver._has_forbidden_export_query(
        "http://localhost:1/api/documents/x/export?format=text")


def test_checkset_rejects_empty_or_false(driver):
    with pytest.raises(driver.DriverError):
        driver._checkset({})
    with pytest.raises(driver.DriverError):
        driver._checkset({"ok": False})
    assert driver._checkset({"ok": True}) == {"ok": True}


def test_source_contract_refuses_missing_head_or_dirty_tree(driver):
    good = driver._source_contract_checks(
        "abc", True, True, True, True)
    assert all(good.values())
    missing = driver._source_contract_checks(
        "", True, True, True, True)
    assert not all(missing.values())
    assert missing["head_present"] is False
    dirty = driver._source_contract_checks(
        "abc", False, True, True, True)
    assert dirty["tracked_tree_clean"] is False


def test_profile_contract_refuses_full_or_search_enabled(driver):
    good_defaults = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
    }
    good = driver._profile_contract_checks(
        "core", True, False, False, False, "documents", good_defaults)
    assert all(good.values())
    wrong = driver._profile_contract_checks(
        "full", True, True, False, False, "documents", good_defaults)
    assert not all(wrong.values())
    assert wrong["profile_core"] is False
    assert wrong["search_deferred"] is False


def test_text_payload_exact_download_passes(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "text", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]
    assert proof["download_sha256"] == proof["api_sha256"]


def test_markdown_payload_exact_download_passes(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "markdown", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]


def test_json_payload_exact_download_passes(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "json", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]
    assert proof["json"]["source_version"] == version


def test_truncated_tail_fails(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    truncated = text[:-200]
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    body = truncated.encode("utf-8")
    headers = _headers(driver, "text", body, text, doc_id, version,
                       "file.txt")
    proof = _proof(driver, "text", text, doc_id, version, "file.txt",
                   body=body, downloaded=body, headers=headers)
    assert not proof["ok"]
    assert "body_equals_full_stored_text" in proof["failures"]
    assert "body_contains_tail_marker" in proof["failures"]


def test_wrong_document_id_fails(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    wrong_id = "doc_" + "f" * 24
    version = "ev4:" + "e" * 64
    body = text.encode("utf-8")
    headers = _headers(driver, "text", body, text, doc_id, version,
                       "file.txt")
    headers["x-document-id"] = wrong_id
    proof = _proof(driver, "text", text, doc_id, version, "file.txt",
                   body=body, headers=headers)
    assert not proof["ok"]
    assert "x_document_id_exact" in proof["failures"]


def test_wrong_downloaded_bytes_fail(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    body = text.encode("utf-8")
    proof = _proof(driver, "text", text, doc_id, version, "file.txt",
                   body=body, downloaded=b"tampered")
    assert not proof["ok"]
    assert "download_equals_api_bytes" in proof["failures"]
    assert "download_sha256_equals_api" in proof["failures"]


def test_json_source_version_mismatch_fails(driver):
    text = ("line\n" * 5000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    wrong = "ev4:" + "a" * 64
    body = _json_body(text, doc_id, wrong, "file.txt")
    headers = _headers(driver, "json", body, text, doc_id, wrong, "file.txt")
    proof = _proof(driver, "json", text, doc_id, version, "file.txt",
                   body=body, headers=headers)
    assert not proof["ok"]
    assert "json_source_version_exact" in proof["failures"]


def test_fastembed_cache_proof_accepts_complete_and_rejects_incomplete(
        driver, tmp_path):
    cache = tmp_path / "fastembed_cache"
    repo = cache / driver.DEFAULT_FASTEMBED_REPO
    snapshot = repo / "snapshots" / "rev1"
    files = {
        "model_optimized.onnx": b"x" * 128,
        "config.json": b"{}",
        "tokenizer.json": b"{}",
        "tokenizer_config.json": b"{}",
        "special_tokens_map.json": b"{}",
    }
    metadata = {}
    for name, blob in files.items():
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        metadata[f"snapshots/rev1/{name}"] = {
            "size": len(blob), "blob_id": "0" * 64}
    (repo / "files_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8")
    (repo / "refs").mkdir()
    (repo / "refs" / "main").write_text("rev1\n", encoding="utf-8")

    proof = driver._fastembed_cache_proof(cache)
    assert proof["ok"], proof["problems"]
    assert proof["file_count"] == 5

    (snapshot / "tokenizer.json").unlink()
    incomplete = driver._fastembed_cache_proof(cache)
    assert not incomplete["ok"]
    assert incomplete["missing_required"] == ["tokenizer.json"]


def test_output_target_refuses_worlds_and_unmarked_reuse(driver, tmp_path):
    worlds = tmp_path / "worlds"
    worlds.mkdir()
    inside = driver._output_target_probe(
        worlds / "evidence", worlds_root=worlds, require_empty=True)
    assert not inside["ok"]
    assert inside["inside_worlds_root"] is True

    out = tmp_path / "out"
    out.mkdir()
    (out / "random.txt").write_text("not a marker", encoding="utf-8")
    reused = driver._output_target_probe(
        out, worlds_root=worlds, require_empty=True)
    assert not reused["ok"]
    assert reused["unknown_entries"] == ["random.txt"]

    fresh = tmp_path / "fresh"
    allowed = driver._output_target_probe(
        fresh, worlds_root=worlds, require_empty=True)
    assert allowed["ok"], allowed["problems"]


def test_acc_metadata_probe_missing_dir_is_not_ready_and_does_not_mkdir(
        driver, tmp_path):
    acc = tmp_path / "acceptance"
    proof = driver._acc_metadata_probe(acc)
    assert not proof["ok"]
    assert proof["exists"] is False
    assert proof["mkdir_in_preflight"] is False
    assert proof["write_in_preflight"] is False
    assert proof["venv_freeze_is_generated_output"] is True
    assert not acc.exists()


def test_acc_metadata_probe_accepts_existing_dir_without_writing(
        driver, tmp_path):
    acc = tmp_path / "acceptance"
    acc.mkdir()
    proof = driver._acc_metadata_probe(acc)
    assert proof["ok"], proof["problems"]
    assert proof["writable"] is True
    assert not (acc / "venv_freeze.txt").exists()


def test_acc_metadata_probe_refuses_tracked_fake_venv_freeze(
        driver, tmp_path):
    repo = tmp_path / "repo"
    acc = repo / "acceptance"
    acc.mkdir(parents=True)
    (acc / "venv_freeze.txt").write_text("fake freeze\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _commit(repo)
    proof = driver._acc_metadata_probe(acc, git_root=repo)
    assert not proof["ok"]
    assert proof["venv_freeze_tracked"] is True
    assert proof["checks"]["venv_freeze_not_tracked"] is False


def test_checksum_inventory_rejects_empty_bad_and_truncated(driver):
    digest = "a" * 64
    bad_inventories = [
        "",
        "\n",
        f"{digest[:63]}  ./a.txt\n",
        f"{digest[:-1]}z  ./a.txt\n",
        f"{digest} ./a.txt\n",
        f"{digest}  \n",
    ]
    for text in bad_inventories:
        parsed = driver._parse_checksum_inventory(text, expected_count=1)
        assert not parsed["ok"], text


def test_checksum_inventory_rejects_duplicate_and_escaped_names(driver):
    digest = "a" * 64
    other = "b" * 64
    duplicate = driver._parse_checksum_inventory(
        f"{digest}  ./a.txt\n{other}  a.txt\n", expected_count=1)
    assert not duplicate["ok"]
    assert duplicate["duplicate_names"] == ["a.txt"]

    escaped = driver._parse_checksum_inventory(
        f"{digest}  ../a.txt\n", expected_count=1)
    assert not escaped["ok"]
    assert escaped["escaped_names"] == ["../a.txt"]

    absolute = driver._parse_checksum_inventory(
        f"{digest}  /tmp/a.txt\n", expected_count=1)
    assert not absolute["ok"]
    assert absolute["escaped_names"] == ["/tmp/a.txt"]

    backslash = driver._parse_checksum_inventory(
        f"{digest}  sub\\a.txt\n", expected_count=1)
    assert not backslash["ok"]
    assert backslash["escaped_names"] == ["sub\\a.txt"]


def test_fixture_checksum_probe_missing_checksums_is_not_ready(
        driver, tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=tmp_path)
    assert not proof["ok"]
    assert proof["checksums_git_tracked"] is False
    assert proof["generated_or_repaired"] is False
    assert not (fixtures / "SHA256SUMS").exists()


def test_fixture_checksum_probe_accepts_exact_git_twins(driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert proof["ok"], proof["problems"]
    assert proof["entry_count"] == 2
    assert proof["expected_entry_count"] == 2
    assert proof["checksums_git_exact"] is True
    assert proof["all_files_git_exact"] is True
    assert proof["generated_or_repaired"] is False
    assert proof["uploaded_as_user_document"] is False


def test_fixture_checksum_probe_rejects_bad_or_truncated_inventory(
        driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    (fixtures / "SHA256SUMS").write_text(
        f"{_sha(b'alpha')[:63]}  ./a.txt\n", encoding="utf-8")
    _commit(repo, "truncated inventory")
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert not proof["ok"]
    assert proof["checks"]["inventory_parsed"] is False
    assert proof["checks"]["entry_count_exact"] is False


def test_fixture_checksum_probe_rejects_wrong_digest(driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    _write_checksums(fixtures, {
        "a.txt": _sha(b"alpha"), "b.txt": _sha(b"not-beta")})
    _commit(repo, "wrong digest")
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert not proof["ok"]
    assert proof["digest_mismatches"] == ["b.txt"]


def test_fixture_checksum_probe_rejects_missing_fixture(driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    (fixtures / "b.txt").unlink()
    _commit(repo, "remove fixture")
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert not proof["ok"]
    assert proof["missing_fixtures"] == ["b.txt"]


def test_fixture_checksum_probe_rejects_symlink_borrow(driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    (fixtures / "b.txt").unlink()
    (fixtures / "b.txt").symlink_to(fixtures / "a.txt")
    _write_checksums(fixtures, {
        "a.txt": _sha(b"alpha"), "b.txt": _sha(b"alpha")})
    _commit(repo, "symlink fixture")
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert not proof["ok"]
    assert proof["symlinked_fixtures"] == ["b.txt"]
    assert proof["checks"]["no_symlinked_fixtures"] is False


def test_fixture_checksum_probe_rejects_worktree_bytes_not_in_git(
        driver, tmp_path):
    repo, fixtures = _fixture_repo(
        tmp_path, {"a.txt": b"alpha", "b.txt": b"beta"})
    (fixtures / "b.txt").write_bytes(b"beta-drifted")
    _write_checksums(fixtures, {
        "a.txt": _sha(b"alpha"), "b.txt": _sha(b"beta-drifted")})
    _git(repo, "add", "--", "fixtures/SHA256SUMS")
    _git(repo, "commit", "-q", "-m", "only checksums committed")
    proof = driver._fixture_checksum_probe(
        fixtures_dir=fixtures, expected_count=2, git_root=repo)
    assert not proof["ok"]
    assert proof["checksums_git_exact"] is True
    assert proof["git_mismatches"] == ["b.txt"]


def test_checksum_source_binding_records_git_identity(driver):
    binding = driver._checksum_source_binding({
        "checksums_path": "/repo/fixtures/SHA256SUMS",
        "checksums_git_relpath": "fixtures/SHA256SUMS",
        "checksums_git_blob": "0" * 40,
        "checksums_sha256": "1" * 64,
        "checksums_bytes": 123,
        "checksums_git_tracked": True,
        "checksums_git_exact": True,
        "ok": True,
    })
    assert binding["git_relpath"] == "fixtures/SHA256SUMS"
    assert binding["git_blob"] == "0" * 40
    assert binding["git_exact"] is True
    assert binding["ok"] is True


@pytest.mark.parametrize("failed_check", [
    "acc_metadata_dir_writable",
    "legacy_fixture_inventory_verified",
])
def test_build_world_refuses_missing_prereq_before_builder(
        driver, tmp_path, monkeypatch, failed_check):
    world = tmp_path / "document_export_ui_test"
    built: list[str] = []

    monkeypatch.delenv("ATOM_WORLD_STORAGE_BYPASS", raising=False)
    monkeypatch.setattr(driver, "_heavy_probe", lambda path: {
        "disk": {"ok": True},
        "requires_root_heavy_approval": False,
    })
    import core.world_storage_guard as WSG
    monkeypatch.setattr(WSG, "require_storage_ready", lambda: None)
    checks = {failed_check: False}
    monkeypatch.setattr(driver, "_prebuild_support_probe", lambda: {
        "ok": False,
        "checks": checks,
        "launcher": {},
        "fixture_inventory": {},
    })
    monkeypatch.setattr(
        driver.R, "build_world", lambda *args, **kwargs: built.append("built"))

    with pytest.raises(driver.DriverError, match="prerequisites"):
        driver._build_world(world, "a" * 40, False)

    assert built == []
    assert not world.exists()


BYOK_SOURCE = '''\
class BYOKManager:
    def _initialize_default_providers(self):
        defaults = [
            AIProviderConfig(
                id="alpha",
                name="Alpha",
                api_key_env_var="ALPHA_API_KEY",
                base_url="https://alpha.invalid/v1",
                model="alpha-1",
            ),
            AIProviderConfig(
                id="local",
                name="Local",
                api_key_env_var="LOCAL_API_KEY",
                base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1"),
                model=os.getenv("LOCAL_MODEL", "local-1"),
            ),
        ]
        self._save_configuration()

    @staticmethod
    def _provider_to_dict(provider):
        return {
            "id": provider.id,
            "name": provider.name,
            "description": provider.description,
            "api_key_env_var": provider.api_key_env_var,
            "base_url": provider.base_url,
            "model": provider.model,
            "cost_per_token": provider.cost_per_token,
            "supported_tasks": list(provider.supported_tasks or []),
            "supports_vision": provider.supports_vision,
            "supports_tools": provider.supports_tools,
            "supports_cache": provider.supports_cache,
            "supports_structured_output": provider.supports_structured_output,
            "reasoning_level": provider.reasoning_level,
            "quality_score": provider.quality_score,
            "max_requests_per_minute": provider.max_requests_per_minute,
            "rate_limit_window": provider.rate_limit_window,
            "is_active": provider.is_active,
            "requires_encryption": provider.requires_encryption,
        }
'''

RUNTIME_PROFILE_SOURCE = '''\
DEFAULT_PROFILE = "core"

def apply_runtime_defaults():
    applied = {}
    if active_profile() != "core":
        return applied
    defaults = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
    }
    for key, value in defaults.items():
        applied[key] = value
    return applied
'''

RUNTIME_APP_SOURCE = '''\
try:
    from core.product_profile import apply_runtime_defaults as _apply_profile_defaults
    _apply_profile_defaults()
except Exception:
    pass
'''


def _byok_entry(provider_id: str, name: str, env_var: str,
                base_url: str, model: str) -> dict:
    return {
        "id": provider_id,
        "name": name,
        "description": "synthetic",
        "api_key_env_var": env_var,
        "base_url": base_url,
        "model": model,
        "cost_per_token": 0.0,
        "supported_tasks": ["chat"],
        "supports_vision": False,
        "supports_tools": False,
        "supports_cache": False,
        "supports_structured_output": False,
        "reasoning_level": 1,
        "quality_score": 0.0,
        "max_requests_per_minute": 60,
        "rate_limit_window": 60,
        "is_active": True,
        "requires_encryption": True,
    }


def _byok_config() -> dict:
    return {"providers": [
        _byok_entry("alpha", "Alpha", "ALPHA_API_KEY",
                    "https://alpha.invalid/v1", "alpha-1"),
        _byok_entry("local", "Local", "LOCAL_API_KEY",
                    "http://localhost:11434/v1", "local-1"),
    ]}


def _write_byok_files(run_dir: Path, *, config: dict | None = None,
                      keys: dict | None = None,
                      encryption_key: str = "A" * 43 + "=") -> None:
    data = run_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "byok_config.json").write_text(
        json.dumps(config if config is not None else _byok_config()),
        encoding="utf-8")
    (data / "byok_keys.json").write_text(
        json.dumps(keys if keys is not None else {"keys": {}}),
        encoding="utf-8")
    (data / "byok_encryption_key").write_text(
        encryption_key, encoding="utf-8")


def test_runtime_defaults_probe_is_diagnostic_only(driver, tmp_path):
    world = tmp_path / "world"
    core = world / "code" / "backend" / "core"
    core.mkdir(parents=True)
    (core / "product_profile.py").write_text(
        RUNTIME_PROFILE_SOURCE, encoding="utf-8")
    # The fixture profile only constructs/returns a dict; it never writes
    # os.environ. Source shape must never certify a live worker flag.
    assert "os.environ" not in RUNTIME_PROFILE_SOURCE
    dead_call = RUNTIME_APP_SOURCE.replace(
        "    _apply_profile_defaults()",
        "    if False:\n        _apply_profile_defaults()")
    (world / "code" / "backend" / "main_api_app.py").write_text(
        dead_call, encoding="utf-8")
    proof = driver._runtime_defaults_probe(
        world, {"effective_env": {}},
        {"status": 200, "body": {"profile": "core"}})
    assert proof["ok"] is False
    assert proof["diagnostic_only"] is True
    assert proof["positive_authority"] is False
    assert proof["live_profile"]["profile"] == "core"


def test_runtime_defaults_probe_valid_source_still_only_diagnostic(
        driver, tmp_path):
    world = tmp_path / "world"
    core = world / "code" / "backend" / "core"
    core.mkdir(parents=True)
    (core / "product_profile.py").write_text(
        RUNTIME_PROFILE_SOURCE, encoding="utf-8")
    (world / "code" / "backend" / "main_api_app.py").write_text(
        RUNTIME_APP_SOURCE, encoding="utf-8")
    proof = driver._runtime_defaults_probe(
        world, {"effective_env": {}},
        {"status": 200, "body": {"profile": "core"}})
    assert proof["ok"] is False
    assert proof["diagnostic_only"] is True
    assert proof["positive_authority"] is False


def test_byok_source_and_generated_config_accept(driver):
    source = driver._byok_source_contract(BYOK_SOURCE)
    assert source["ok"], source["problems"]
    proof = driver._byok_config_content_probe(_byok_config(), source)
    assert proof["ok"], proof["problems"]
    assert proof["provider_count"] == 2
    assert "local.base_url" in proof["env_derived_fields"]
    assert "local.model" in proof["env_derived_fields"]


def test_byok_config_rejects_credential_field_and_wrong_provider(driver):
    source = driver._byok_source_contract(BYOK_SOURCE)
    credential = _byok_config()
    credential["providers"][0]["api_key"] = "sk-not-allowed"
    proof = driver._byok_config_content_probe(credential, source)
    assert not proof["ok"]
    assert proof["checks"]["no_credential_value_fields"] is False
    assert proof["checks"]["provider_fields_exact"] is False

    wrong = _byok_config()
    wrong["providers"][0]["id"] = "not-alpha"
    proof = driver._byok_config_content_probe(wrong, source)
    assert not proof["ok"]
    assert proof["checks"]["provider_ids_exact"] is False


def test_byok_generated_default_probe_accepts_generated_files(
        driver, tmp_path):
    world = tmp_path / "world"
    run_dir = tmp_path / "run"
    _write_byok_files(run_dir)
    proof = driver._byok_generated_default_probe(
        world, run_dir, {"effective_env": {}}, source_text=BYOK_SOURCE)
    assert proof["ok"], proof["problems"]
    assert proof["generated_default_catalog"] is True
    assert proof["operator_config_present"] is False
    assert proof["credential_free"] is True
    assert proof["checks"]["generated_or_absent"] is True
    assert proof["files"]["encryption_key"]["present"] is True
    assert Path(proof["files"]["encryption_key"]["path"]).name == "byok_encryption_key"
    assert "content" not in proof["files"]["encryption_key"]


def test_byok_generated_default_probe_rejects_keys_or_env_override(
        driver, tmp_path):
    world = tmp_path / "world"
    run_dir = tmp_path / "run"
    _write_byok_files(
        run_dir, keys={"keys": {"alpha": {"encrypted_key": "x"}}})
    proof = driver._byok_generated_default_probe(
        world, run_dir, {"effective_env": {}}, source_text=BYOK_SOURCE)
    assert not proof["ok"]
    assert proof["operator_config_present"] is True
    assert proof["credential_free"] is False

    run_dir_2 = tmp_path / "run2"
    _write_byok_files(run_dir_2)
    overridden = driver._byok_generated_default_probe(
        world, run_dir_2,
        {"effective_env": {"BYOK_CONFIG_FILE": "/tmp/live.json"}},
        source_text=BYOK_SOURCE)
    assert not overridden["ok"]
    assert overridden["checks"]["no_byok_env_forwarded"] is False
    assert overridden["byok_env_keys"] == ["BYOK_CONFIG_FILE"]


def test_byok_key_shape_is_diagnostic_not_origin_proof(
        driver, tmp_path):
    world = tmp_path / "world"
    run_dir = tmp_path / "run"
    _write_byok_files(run_dir, encryption_key="A" * 42 + "/=")
    proof = driver._byok_generated_default_probe(
        world, run_dir, {"effective_env": {}}, source_text=BYOK_SOURCE)
    # A non-URL-safe key shape is recorded as a diagnostic, but shape alone
    # does not label the catalog/operator origin either way.
    assert proof["checks"]["encryption_key_shape_diagnostic"] is False
    assert proof["encryption_key_shape_ok"] is False
    assert proof["generated_default_catalog"] is True
    assert proof["operator_config_present"] is False
    assert proof["credential_free"] is True
    assert proof["ok"] is True


def test_byok_generated_default_probe_rejects_world_code_seed(
        driver, tmp_path):
    world = tmp_path / "world"
    run_dir = tmp_path / "run"
    _write_byok_files(run_dir)
    seed = world / "code" / "backend" / "data" / "byok_config.json"
    seed.parent.mkdir(parents=True)
    seed.write_text("{}", encoding="utf-8")
    proof = driver._byok_generated_default_probe(
        world, run_dir, {"effective_env": {}}, source_text=BYOK_SOURCE)
    assert not proof["ok"]
    assert proof["checks"]["no_world_code_byok_seed"] is False


def test_launcher_dotenv_isolation_stops_at_world(driver, tmp_path,
                                                  monkeypatch):
    from dotenv import find_dotenv
    parent_marker = tmp_path / ".env"
    parent_local = tmp_path / ".env.local"
    parent_marker.write_text("PARENT_MARKER=do-not-load\n", encoding="utf-8")
    parent_local.write_text(
        "PARENT_LOCAL_MARKER=do-not-load\n", encoding="utf-8")
    world = tmp_path / "backend" / "data" / "acceptance_worlds" / "world"
    (world / "backend_root").mkdir(parents=True)
    report = driver.R._install_dotenv_isolation(world)
    assert report["ok"], report["problems"]
    for path in (
            world / ".env", world / ".env.local",
            world / "backend_root" / ".env",
            world / "backend_root" / ".env.local"):
        text = path.read_text(encoding="utf-8")
        assert text == driver.R.DOTENV_WORLD_GUARD
        assert "PARENT_MARKER" not in text
    # The synthetic parent markers are untouched and never copied.
    assert parent_marker.read_text(encoding="utf-8") == (
        "PARENT_MARKER=do-not-load\n")
    assert parent_local.read_text(encoding="utf-8") == (
        "PARENT_LOCAL_MARKER=do-not-load\n")
    # A bare find starting at the world farm stops at the world guard, not
    # at the synthetic parent credentials.
    monkeypatch.chdir(world / "backend_root")
    found = Path(find_dotenv(usecwd=True)).resolve()
    assert found == (world / "backend_root" / ".env").resolve()
    assert found != parent_marker.resolve()


def test_launcher_dotenv_isolation_refuses_nonempty_and_symlink(
        driver, tmp_path):
    world = tmp_path / "world"
    (world / "backend_root").mkdir(parents=True)
    (world / ".env").write_text(
        "OPERATOR_MARKER=do-not-load\n", encoding="utf-8")
    report = driver.R._install_dotenv_isolation(world)
    assert not report["ok"]
    assert "OPERATOR_MARKER=do-not-load\n" == (
        world / ".env").read_text(encoding="utf-8")

    live = tmp_path / "live.env"
    live.write_text("LIVE_MARKER=do-not-load\n", encoding="utf-8")
    guard_path = world / "backend_root" / ".env.local"
    if guard_path.exists() or guard_path.is_symlink():
        guard_path.unlink()
    guard_path.symlink_to(live)
    report = driver.R._install_dotenv_isolation(world)
    assert not report["ok"]
    assert live.read_text(encoding="utf-8") == "LIVE_MARKER=do-not-load\n"


def test_launcher_whitelist_forwards_the_evolution_flag(driver):
    assert "ATOM_AGENT_EVOLUTION_ENABLED" in driver.R.SERVER_ENV_WHITELIST


def test_worker_defaults_all_actual_false_is_the_valid_twin(
        driver, tmp_path, monkeypatch):
    log = tmp_path / "server.log"
    log.write_text("no worker defaults line\n", encoding="utf-8")
    values = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
        "TMPDIR": tempfile.gettempdir(),
    }
    monkeypatch.setattr(
        driver, "_process_env_probe",
        lambda pid, keys: {"ok": True, "values": dict(values)})
    proven = driver._worker_defaults_probe(1, log)
    assert proven["checks"]["worker_flags_proven"] is True


def test_worker_defaults_absent_actual_env_cannot_certify(
        driver, tmp_path, monkeypatch):
    log = tmp_path / "server.log"
    log.write_text("no worker defaults line\n", encoding="utf-8")
    values = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": None,
        "TMPDIR": tempfile.gettempdir(),
    }
    monkeypatch.setattr(
        driver, "_process_env_probe",
        lambda pid, keys: {"ok": True, "values": dict(values)})
    runtime = {
        "ok": False,
        "diagnostic_only": True,
    }
    proof = driver._worker_defaults_probe(1, log, runtime_defaults=runtime)
    assert proof["checks"]["worker_flags_off_from_actual_env"] is False
    assert proof["checks"]["worker_flags_proven"] is False
    assert proof["runtime_defaults_diagnostic_only"] is True


def test_worker_defaults_true_actual_env_fails_even_with_diagnostic(
        driver, tmp_path, monkeypatch):
    log = tmp_path / "server.log"
    log.write_text("no worker defaults line\n", encoding="utf-8")
    values = {
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "true",
        "TMPDIR": tempfile.gettempdir(),
    }
    monkeypatch.setattr(
        driver, "_process_env_probe",
        lambda pid, keys: {"ok": True, "values": dict(values)})
    runtime = {
        "ok": False,
        "diagnostic_only": True,
    }
    proof = driver._worker_defaults_probe(1, log, runtime_defaults=runtime)
    assert proof["checks"]["worker_flags_proven"] is False


def test_pricing_token_metric_is_not_a_credential_value(driver):
    contract = driver._byok_source_contract(BYOK_SOURCE)
    config = _byok_config()
    config["providers"][0]["cost_per_token"] = 0.0123
    proof = driver._byok_config_content_probe(config, contract)
    assert proof["ok"], proof
    assert proof["checks"]["no_credential_value_fields"] is True


def test_pricing_token_metric_still_requires_numeric_material(driver):
    contract = driver._byok_source_contract(BYOK_SOURCE)
    config = _byok_config()
    config["providers"][0]["cost_per_token"] = "not-a-number"
    proof = driver._byok_config_content_probe(config, contract)
    assert proof["ok"] is False
    assert proof["checks"]["provider_types_valid"] is False


# Root order-only probes: no product import, DB seed or server starts.
class SeedStoppedBeforeAnyProductImport(Exception):pass

@pytest.mark.parametrize('pre_guard',[False,True],ids=['launcher-installs-before-seed','already-guarded-valid-twin'])
def test_dotenv_isolation_precedes_frozen_product_seed(driver,tmp_path,monkeypatch,pre_guard):
    world=tmp_path/'world';(world/'backend_root').mkdir(parents=True)
    if pre_guard:assert driver.R._install_dotenv_isolation(world)['ok']
    def seed(w,run):
        for root in [world,world/'backend_root']:
            for name in ['.env','.env.local']:
                assert (root/name).is_file(),f'Product metadata import would precede isolation: {root/name}'
                assert (root/name).read_text()==driver.R.DOTENV_WORLD_GUARD
        raise SeedStoppedBeforeAnyProductImport()
    monkeypatch.setattr(driver.R,'_seed_run_data',seed)
    monkeypatch.setattr(driver.R.subprocess,'Popen',lambda *a,**k:pytest.fail('No server may start in this order-only probe'))
    with pytest.raises(SeedStoppedBeforeAnyProductImport):driver.R.launch_server(8047,world,provider_shim=False)


def test_documents_navigation_accepts_intentionally_hidden_upload_input(driver):
    from unittest.mock import Mock
    page = Mock()
    link = Mock()
    page.locator.return_value = link
    driver._open_documents(page)
    page.wait_for_url.assert_called_once()
    assert any(call.kwargs.get("state") == "attached"
               for call in link.wait_for.call_args_list)
    page.wait_for_selector.assert_not_called()
    page.get_by_role.assert_called_once_with(
        "heading", name="Knowledge Base", exact=True)
