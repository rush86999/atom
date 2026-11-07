"""Pure helper guards for the prepared Documents stored-text export driver.

These tests do not launch a world, server, browser, model or download. They
exercise only the anti-false-positive logic that decides whether a browser
download really is the same bytes as the corresponding export API response.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
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
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "text", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]
    assert proof["download_sha256"] == proof["api_sha256"]


def test_markdown_payload_exact_download_passes(driver):
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "markdown", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]


def test_json_payload_exact_download_passes(driver):
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    proof = _proof(driver, "json", text, doc_id, version, "file.txt")
    assert proof["ok"], proof["failures"]
    assert proof["json"]["source_version"] == version


def test_truncated_tail_fails(driver):
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
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
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
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
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
    doc_id = "doc_" + "d" * 24
    version = "ev4:" + "e" * 64
    body = text.encode("utf-8")
    proof = _proof(driver, "text", text, doc_id, version, "file.txt",
                   body=body, downloaded=b"tampered")
    assert not proof["ok"]
    assert "download_equals_api_bytes" in proof["failures"]
    assert "download_sha256_equals_api" in proof["failures"]


def test_json_source_version_mismatch_fails(driver):
    text = ("line\n" * 3000) + "FINAL-TAIL\n"
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
