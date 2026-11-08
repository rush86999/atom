"""Evidence certification must use the manifest belonging to the selected Git ref."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/acceptance/evidence_git_check.py"
spec = importlib.util.spec_from_file_location("evidence_git_ref_contract_checker", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

@pytest.fixture
def packet(tmp_path):
    repo=tmp_path/"repo";repo.mkdir();git(repo,"init","-q");git(repo,"config","user.name","Evidence Test");git(repo,"config","user.email","evidence@example.test")
    (repo/"runtime.py").write_text("runtime = 1\n");git(repo,"add","runtime.py");git(repo,"commit","-qm","runtime");source=git(repo,"rev-parse","HEAD")
    directory=repo/"evidence";directory.mkdir();(directory/"result.txt").write_text("recorded result\n")
    sha=lambda b:hashlib.sha256(b).hexdigest()
    manifest={"executed_source":source,"source_files":{"runtime.py":sha((repo/"runtime.py").read_bytes())},"artifacts":{"result.txt":sha((directory/"result.txt").read_bytes())}}
    (directory/"MANIFEST.json").write_text(json.dumps(manifest));git(repo,"add","evidence");git(repo,"commit","-qm","packet")
    return repo,directory,manifest

def test_dirty_manifest_cannot_turn_committed_hash_mismatch_into_pass(packet):
    repo,directory,manifest=packet
    committed=json.loads(json.dumps(manifest));committed["artifacts"]["result.txt"]="0"*64
    (directory/"MANIFEST.json").write_text(json.dumps(committed));git(repo,"add","evidence/MANIFEST.json");git(repo,"commit","-qm","bad recorded hash")
    (directory/"MANIFEST.json").write_text(json.dumps(manifest))
    result=checker.verify(repo,directory,"HEAD",True)
    assert result["passed"] is False,result
    assert any("artifact hash mismatch" in reason for reason in result["failures"]),result

def test_unstaged_manifest_cannot_refute_valid_committed_packet(packet):
    repo,directory,manifest=packet
    (directory/"MANIFEST.json").write_text("not JSON")
    result=checker.verify(repo,directory,"HEAD",True)
    assert result["passed"] is True,result

def test_git_packet_does_not_require_a_working_tree_manifest(packet):
    repo,directory,manifest=packet
    (directory/"MANIFEST.json").unlink();(directory/"result.txt").unlink();directory.rmdir()
    result=checker.verify(repo,directory,"HEAD",True)
    assert result["passed"] is True,result

def test_index_check_uses_staged_manifest_not_later_unstaged_edit(packet):
    repo,directory,manifest=packet
    git(repo,"add","evidence/MANIFEST.json")
    (directory/"MANIFEST.json").write_text("not JSON")
    result=checker.verify(repo,directory,":0",True)
    assert result["passed"] is True,result

def test_missing_manifest_cli_returns_truthful_failure_without_traceback(packet,capsys):
    repo,directory,manifest=packet
    exit_code=checker.main([str(repo/"missing"),"--repo",str(repo),"--json"])
    result=json.loads(capsys.readouterr().out)
    assert exit_code==1 and result["passed"] is False,result
    assert result["failures"],result

@pytest.mark.parametrize("body", ["{", "[]"])
def test_bad_committed_manifest_is_a_failed_result(packet, body):
    repo, directory, manifest = packet
    (directory / "MANIFEST.json").write_text(body)
    git(repo, "add", "evidence/MANIFEST.json")
    git(repo, "commit", "-qm", "malformed manifest")
    result = checker.verify(repo, directory, "HEAD", True)
    assert result["passed"] is False and result["failures"], result


def test_named_ref_is_frozen_before_concurrent_head_change(packet, monkeypatch):
    repo, directory, manifest = packet
    expected_head = git(repo, "rev-parse", "HEAD")
    original_resolve = checker._resolve_commit
    changed = []

    def resolve_then_move(repo_path, ref):
        resolved = original_resolve(repo_path, ref)
        if ref == "HEAD" and not changed:
            changed.append(True)
            (directory / "result.txt").write_text("later peer result\n")
            manifest["artifacts"]["result.txt"] = hashlib.sha256(
                (directory / "result.txt").read_bytes()).hexdigest()
            (directory / "MANIFEST.json").write_text(json.dumps(manifest))
            git(repo, "add", "evidence")
            git(repo, "commit", "-qm", "peer moves head")
        return resolved

    monkeypatch.setattr(checker, "_resolve_commit", resolve_then_move)
    result = checker.verify(repo, directory, "HEAD", True)
    assert changed and git(repo, "rev-parse", "HEAD") != expected_head
    assert result["passed"] is True, result
    assert result["evidence_ref_commit"] == expected_head, result
    assert result["source_ok"] == 1 and result["artifact_ok"] == 1, result


@pytest.mark.parametrize("source_prefix,artifact_prefix", [
    ("sha256:", "sha256:"), ("sha256:", ""), ("", "sha256:"),
])
def test_algorithm_qualified_digests_verify_the_same_complete_git_bytes(
        packet, source_prefix, artifact_prefix):
    repo, directory, manifest = packet
    manifest["source_files"]["runtime.py"] = source_prefix + manifest["source_files"]["runtime.py"]
    manifest["artifacts"]["result.txt"] = artifact_prefix + manifest["artifacts"]["result.txt"]
    (directory / "MANIFEST.json").write_text(json.dumps(manifest))
    git(repo, "add", "evidence/MANIFEST.json")
    git(repo, "commit", "-qm", "explicit digest algorithms")
    result = checker.verify(repo, directory, "HEAD", True)
    assert result["passed"] is True, result
    assert result["source_ok"] == result["artifact_ok"] == 1


@pytest.mark.parametrize("section,key", [
    ("source_files", "runtime.py"), ("artifacts", "result.txt"),
])
@pytest.mark.parametrize("invalid", [
    "sha512:" + "a" * 64, "sha256:" + "a" * 63,
    "sha256:" + "g" * 64, "SHA256:" + "a" * 64,
    "sha256:" + "0" * 64, {"sha256": "a" * 64},
])
def test_explicit_digest_never_accepts_bad_algorithm_encoding_or_material(
        packet, section, key, invalid):
    repo, directory, manifest = packet
    manifest[section][key] = invalid
    (directory / "MANIFEST.json").write_text(json.dumps(manifest))
    git(repo, "add", "evidence/MANIFEST.json")
    git(repo, "commit", "-qm", "invalid explicit digest")
    result = checker.verify(repo, directory, "HEAD", True)
    assert result["passed"] is False and result["failures"], result
