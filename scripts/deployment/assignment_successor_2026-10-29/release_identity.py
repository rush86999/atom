#!/usr/bin/env python3
"""Shared identity helpers for the assignment-successor deployment kit.

The deployable PRODUCT source is the frozen release tag
``assignment-successor-2026-10-29``.  The deployment kit is an overlay: its
files are checksummed separately and are not part of the product tree, so the
runtime health identity always reports the product commit it actually loaded.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

RELEASE_TAG = "assignment-successor-2026-10-29"
RELEASE_COMMIT = "ef95ceb3194ec92c51e64941d7bb364c0b8b0e75"
TESTED_RUNTIME_COMMIT = "001f93472"
PRODUCT_PATHS: Sequence[str] = ("backend", "frontend-nextjs")
EXPECTED_PRODUCT_TREE_SHA256 = (
    "12060bee618e7a58a98324f682d39077c144c19a6fb7d22d77de8179237dbb9e"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(root: Path, paths: Iterable[str] | None = None) -> str:
    """Content checksum over a stable sorted file list (relative paths)."""
    root = root.resolve()
    files: list[Path] = []
    if paths is None:
        files = [p for p in root.rglob("*") if p.is_file()]
    else:
        for rel in paths:
            target = root / rel
            if target.is_file():
                files.append(target)
            elif target.is_dir():
                files.extend(p for p in target.rglob("*") if p.is_file())
    entries = []
    for p in sorted(files):
        rel = p.relative_to(root).as_posix()
        entries.append(f"{rel}:{sha256_file(p)}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def product_tree_sha256(repo: Path, commit: str = RELEASE_COMMIT) -> str:
    """Hash the git tree entries for the product paths.

    Independent of commit timestamps and of documentation/kit commits, so the
    tested runtime and the packaged runtime can be compared directly.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "-r", commit, "--", *PRODUCT_PATHS],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return hashlib.sha256(listing.encode()).hexdigest()


def load_identity(root: Path) -> dict:
    path = root / "RELEASE_IDENTITY.json"
    if not path.is_file():
        raise SystemExit(f"REFUSED: missing {path}")
    return json.loads(path.read_text())


def atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)
