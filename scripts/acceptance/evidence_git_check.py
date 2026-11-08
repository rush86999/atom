#!/usr/bin/env python3
"""Verify an evidence manifest against Git blobs, not the working tree.

The G5 evidence bundles declare an ``executed_source`` and hash the source files
that actually ran, plus the evidence artifacts that must be reviewable from a
checkout. A disk-only check can pass while the declared logs are ignored by
``.gitignore`` or while a manifest hash was collected from a later working tree.
This checker reads both sides from Git:

* The manifest itself is read from the selected Git ref (or index), never
  from an unstaged working-tree copy. Named refs are resolved once per check.
* ``source_files`` are compared against ``git show <executed_source>:<path>``;
  evidence bundles that call their frozen source ``runtime_source`` are also
  supported;
* ``artifacts`` are compared against the evidence ref (default ``HEAD``);
* ``--strict`` also rejects tracked evidence files that the manifest omits;
* ``--candidate-ref`` additionally checks the delivered commit source bytes.
  Without it, a valid historical packet does not certify a later candidate.

Use ``--evidence-ref :0`` to check the index before committing.

Usage:
  python scripts/acceptance/evidence_git_check.py <evidence-dir>
  python scripts/acceptance/evidence_git_check.py <evidence-dir> --json
  python scripts/acceptance/evidence_git_check.py <evidence-dir> --evidence-ref :0 --strict
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

INDEX_REFS = {":0", "INDEX", "index"}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _resolve_commit(repo: Path, ref: str) -> Optional[str]:
    proc = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        return None
    return proc.stdout.decode().strip()


def _blob(repo: Path, ref: str, path: str) -> Optional[bytes]:
    spec = f":{path}" if ref in INDEX_REFS else f"{ref}:{path}"
    proc = _git(repo, "show", spec)
    return proc.stdout if proc.returncode == 0 else None


def _tracked(repo: Path, ref: str, path: str) -> List[str]:
    if ref in INDEX_REFS:
        proc = _git(repo, "ls-files", "--", path)
    else:
        proc = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", path)
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.decode().splitlines() if line]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _matches_sha256(data: bytes, expected: object) -> bool:
    """Accept exact legacy hex or an explicit algorithm-qualified digest.

    The algorithm:encoded form follows OCI descriptor digest notation. No
    shortening, alternate algorithm, whitespace or case normalization is used.
    Both forms compare all 256 bits against the actual selected Git blob.
    """
    if not isinstance(expected, str):
        return False
    encoded = expected[7:] if expected.startswith("sha256:") else expected
    return (len(encoded) == 64
            and all(character in "0123456789abcdef" for character in encoded)
            and _sha(data) == encoded)


def verify(repo: Path, evidence: Path, evidence_ref: str, strict: bool,
           candidate_ref: Optional[str] = None) -> Dict:
    result: Dict = {
        "evidence": str(evidence),
        "evidence_ref": evidence_ref,
        "source_ok": 0,
        "source_total": 0,
        "artifact_ok": 0,
        "artifact_total": 0,
        "extra_tracked": [],
        "failures": [],
        "passed": False,
    }
    try:
        evidence_rel = evidence.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        result["failures"].append("evidence directory is outside the Git worktree")
        return result
    result["evidence_path"] = evidence_rel
    selected_ref = (
        evidence_ref if evidence_ref in INDEX_REFS
        else _resolve_commit(repo, evidence_ref))
    if not selected_ref:
        result["failures"].append(f"evidence ref does not resolve: {evidence_ref!r}")
        return result
    if evidence_ref not in INDEX_REFS:
        result["evidence_ref_commit"] = selected_ref
    candidate_commit = None
    if candidate_ref is not None:
        result["candidate_ref"] = candidate_ref
        candidate_commit = (selected_ref if candidate_ref == evidence_ref
                            and evidence_ref not in INDEX_REFS
                            else _resolve_commit(repo, candidate_ref))
        if not candidate_commit:
            result["failures"].append(
                f"candidate ref does not resolve to a commit: {candidate_ref!r}")
            return result
        result["candidate_ref_commit"] = candidate_commit
        result["candidate_ok"] = 0
    manifest_rel = f"{evidence_rel}/MANIFEST.json"
    try:
        manifest_bytes = _blob(repo, selected_ref, manifest_rel)
        if manifest_bytes is None:
            raise ValueError(f"manifest missing at {evidence_ref}: {manifest_rel}")
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be a JSON object")
        for collection in ("source_files", "artifacts"):
            if manifest.get(collection) is not None and not isinstance(
                    manifest[collection], dict):
                raise ValueError(f"manifest {collection} must be an object")
    except Exception as exc:  # noqa: BLE001
        result["failures"].append(f"manifest unreadable: {exc}")
        return result

    executed = str(
        manifest.get("executed_source")
        or manifest.get("runtime_source")
        or ""
    ).strip()
    result["executed_source"] = executed
    source_commit = _resolve_commit(repo, executed) if executed else None
    if not source_commit:
        result["failures"].append(
            f"executed_source does not resolve to a commit: {executed!r}")
    else:
        result["executed_source_commit"] = source_commit

    source_files = manifest.get("source_files") or {}
    result["source_total"] = len(source_files)
    if source_commit:
        for path, expected in sorted(source_files.items()):
            data = _blob(repo, source_commit, path)
            if data is None:
                result["failures"].append(
                    f"source missing at {source_commit[:12]}: {path}")
            elif not _matches_sha256(data, expected):
                result["failures"].append(
                    f"source hash mismatch at {source_commit[:12]}: {path} "
                    f"expected {expected} got {_sha(data)}")
            else:
                result["source_ok"] += 1

    if candidate_commit:
        if not source_files:
            result["failures"].append("candidate comparison requires source_files")
        for path, expected in sorted(source_files.items()):
            data = _blob(repo, candidate_commit, path)
            if data is None:
                result["failures"].append(
                    f"candidate source missing at {candidate_commit[:12]}: {path}")
            elif not _matches_sha256(data, expected):
                result["failures"].append(
                    f"candidate source hash mismatch at {candidate_commit[:12]}: {path}")
            else:
                result["candidate_ok"] += 1

    artifacts = manifest.get("artifacts") or {}
    result["artifact_total"] = len(artifacts)
    if evidence_rel:
        for name, expected in sorted(artifacts.items()):
            rel = f"{evidence_rel}/{Path(name).as_posix()}"
            data = _blob(repo, selected_ref, rel)
            if data is None:
                result["failures"].append(
                    f"artifact missing at {evidence_ref}: {rel}")
            elif not _matches_sha256(data, expected):
                result["failures"].append(
                    f"artifact hash mismatch at {evidence_ref}: {rel} "
                    f"expected {expected} got {_sha(data)}")
            else:
                result["artifact_ok"] += 1

        listed = {
            f"{evidence_rel}/{Path(name).as_posix()}" for name in artifacts
        }
        manifest_rel = f"{evidence_rel}/MANIFEST.json"
        listed.add(manifest_rel)
        tracked = set(_tracked(repo, selected_ref, evidence_rel))
        if manifest_rel not in tracked:
            result["failures"].append(
                f"manifest is not tracked at {evidence_ref}: {manifest_rel}")
        result["extra_tracked"] = sorted(tracked - listed)
        if strict and result["extra_tracked"]:
            for path in result["extra_tracked"]:
                result["failures"].append(
                    f"tracked evidence file not listed in manifest: {path}")

    result["passed"] = not result["failures"]
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", help="evidence directory inside the repo")
    parser.add_argument(
        "--repo", default=".", help="repository root (default: current directory)")
    parser.add_argument(
        "--evidence-ref", default="HEAD",
        help="Git ref holding the evidence artifacts (default: HEAD; use :0 for the index)")
    parser.add_argument(
        "--strict", action="store_true",
        help="also fail when a tracked evidence file is missing from the manifest")
    parser.add_argument(
        "--candidate-ref", default=None,
        help="also require declared source bytes in this delivered commit/ref")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    evidence = Path(args.evidence)
    if not evidence.is_absolute():
        evidence = (repo / evidence).resolve()
    result = verify(repo, evidence, args.evidence_ref, args.strict, args.candidate_ref)

    if args.json:
        print(json.dumps(result, indent=1, sort_keys=True))
    else:
        print(f"evidence: {result.get('evidence')}")
        print(f"executed source: {result.get('executed_source')}")
        print(
            f"source files: {result['source_ok']}/{result['source_total']} "
            f"match at {result.get('executed_source_commit', '?')[:12]}")
        print(
            f"artifacts: {result['artifact_ok']}/{result['artifact_total']} "
            f"match at {args.evidence_ref}")
        if result["extra_tracked"]:
            print(
                f"extra tracked files: {len(result['extra_tracked'])} "
                f"(strict={'on' if args.strict else 'off'})")
        if result["failures"]:
            print("FAIL")
            for failure in result["failures"]:
                print(f"  - {failure}")
        else:
            print("PASS")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
