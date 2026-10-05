#!/usr/bin/env python3
"""Credential isolation for a preview world: sanitize, then PROVE.

The acceptance harness scrubs 15 credential-bearing DATABASE TABLES. It does
not touch the credential-bearing FILES that a world inherits from the developer's
data directory, and two of those matter:

- `byok_keys.json` — stored BYOK provider keys. An empty one in this run is not
  a guarantee: the same launcher against a populated development database
  inherits live keys, and nothing in the build would notice.
- `byok_encryption_key` — the Fernet key that DECRYPTS tokens at rest. Handing a
  world the same key means anything encrypted in a copied row is readable
  there. A world must not be able to decrypt the developer's credentials.

`byok_config.json` is deliberately PRESERVED: it holds provider *definitions*
(`api_key_env_var` — the NAME of an environment variable, not its value) and
the app needs it to know which providers exist. Verified by inspection, not
assumed; `assert_benign` re-checks it on every run.

The proof is separate from the sanitizer on purpose. Sanitizing and then
asserting "the sanitizer ran" is circular; what matters is that no usable
credential is present, checked against the live data directory.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any

# Files replaced outright: they carry credential material.
BYOK_KEYS_FILE = "byok_keys.json"
ENCRYPTION_KEY_FILE = "byok_encryption_key"

# Files deliberately kept, with the reason recorded so a reviewer does not have
# to re-derive it. Each is checked to contain no secret material.
RETAINED_FILES = {
    "byok_config.json": "provider definitions (api_key_env_var = a NAME, not a value)",
}

# Columns that must be empty/NULL in the world. Mirrors the harness's DB scrub
# and is re-verified here so a world is never published on the harness's word.
SECRET_COLUMN_RE = re.compile(
    r"(token|secret|password|credential|private|api_key|access_key|refresh|client_id)",
    re.I,
)
SECRET_TABLES = (
    "federation_credentials", "integration_connections", "link_tokens",
    "user_connections", "push_tokens", "oauth_states", "integration_tokens",
    "notion_tokens", "password_reset_tokens", "desktop_api_keys",
    "public_api_keys", "gateway_api_keys", "oauth_clients",
    "llm_oauth_credentials", "active_tokens",
)


class CredentialLeak(RuntimeError):
    """A world would carry usable credential material. Never publish it."""


def sanitize(run_data_dir: Path, live_data_dir: Path) -> dict[str, Any]:
    """Make the world's credential stores empty and its key material unique.

    Returns a record of what was done, for the world manifest.
    """
    import sqlite3

    run_data_dir = Path(run_data_dir)
    live_data_dir = Path(live_data_dir)
    report: dict[str, Any] = {"sanitized": [], "regenerated": [], "retained": {}}

    keys_path = run_data_dir / BYOK_KEYS_FILE
    inherited_keys = None
    if keys_path.exists():
        try:
            doc = json.loads(keys_path.read_text() or "{}")
            entries = doc.get("keys") if isinstance(doc, dict) else None
            inherited_keys = sorted(entries.keys()) if isinstance(entries, dict) else []
        except Exception:
            inherited_keys = ["<unparseable>"]
    # Replaced, not emptied: an empty file and a missing file are different
    # states to the app, and a missing one has been observed to change startup
    # behaviour. The replacement is schema-shaped and empty.
    keys_path.write_text(json.dumps({"keys": {}}, indent=1))
    os.chmod(keys_path, stat.S_IRUSR | stat.S_IWUSR)
    report["sanitized"].append({
        "file": BYOK_KEYS_FILE,
        "inherited_provider_key_names": inherited_keys or [],
        "note": "replaced with an empty key store; names only, no values recorded",
    })

    key_path = run_data_dir / ENCRYPTION_KEY_FILE
    live_key_path = live_data_dir / ENCRYPTION_KEY_FILE
    live_key = live_key_path.read_bytes() if live_key_path.exists() else None
    fresh = Fernet_key()
    key_path.write_bytes(fresh)
    os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    report["regenerated"].append({
        "file": ENCRYPTION_KEY_FILE,
        "inherited": live_key is not None,
        "rotated": True,
        "note": ("world-local key; anything encrypted with the developer's key is "
                 "undecryptable here by construction"),
    })

    for name, why in RETAINED_FILES.items():
        path = run_data_dir / name
        if path.exists():
            report["retained"][name] = why

    db_path = run_data_dir / "atom.db"
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        try:
            report["db_secret_columns_null"] = _assert_db(con)
        finally:
            con.close()

    # A FINGERPRINT, never the key. This report is serialised into
    # preview_state.json, which is a committed, tracked file -- so writing the
    # world Fernet key here put a live at-rest decryption key into git, in the
    # very module whose premise is that nothing secret is ever rendered.
    #
    # The field exists to prove one thing: this world's key is not the
    # developer's. A sha256 proves that just as well, and discloses nothing:
    # the comparison at prove_isolated() is `world_key != live_key`, and that
    # holds for the digests exactly when it holds for the keys.
    import hashlib
    raw = fresh.decode() if isinstance(fresh, bytes) else str(fresh)
    report["world_unique"] = {
        "sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "length": len(raw),
        "note": "fingerprint of the world-local Fernet key; the key itself is "
                "written only to the world's own data dir, never to a report",
    }
    return report


def Fernet_key() -> bytes:  # noqa: N802 - factory, mirrors the cryptography name
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key()
    except Exception:
        # A world must still get a unique key if the library is unavailable; it
        # only has to be unguessable and different from the developer's.
        return secrets.token_bytes(32)


def _assert_db(con) -> dict[str, Any]:
    out: dict[str, Any] = {"tables_checked": 0, "non_null_cells": 0, "offenders": []}
    for table in SECRET_TABLES:
        try:
            cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        except Exception:
            continue
        if not cols:
            continue
        out["tables_checked"] += 1
        for col in cols:
            name = col[1]
            if not SECRET_COLUMN_RE.search(name):
                continue
            try:
                (count,) = con.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{name}" IS NOT NULL'
                ).fetchone()
            except Exception:
                continue
            if count:
                out["non_null_cells"] += int(count)
                out["offenders"].append(f"{table}.{name}={count}")
    return out


def prove_isolated(run_data_dir: Path, live_data_dir: Path) -> dict[str, Any]:
    """Independent check that NO usable credential was inherited.

    Deliberately does not trust the sanitizer's own report: it re-reads the
    world and compares it against the live data directory.
    """
    import sqlite3

    run_data_dir = Path(run_data_dir)
    live_data_dir = Path(live_data_dir)
    problems: list[str] = []
    evidence: dict[str, Any] = {}

    # 1. No stored provider keys.
    keys_path = run_data_dir / BYOK_KEYS_FILE
    try:
        doc = json.loads(keys_path.read_text() or "{}")
        entries = doc.get("keys") or {}
        evidence["byok_provider_keys"] = sorted(entries.keys()) if isinstance(entries, dict) else "UNEXPECTED_SHAPE"
        if entries:
            problems.append(f"{BYOK_KEYS_FILE} carries {len(entries)} provider key(s)")
    except Exception as exc:
        problems.append(f"{BYOK_KEYS_FILE} unreadable: {exc}")

    # 2. The at-rest key is world-local.
    key_path = run_data_dir / ENCRYPTION_KEY_FILE
    live_key_path = live_data_dir / ENCRYPTION_KEY_FILE
    world_key = key_path.read_bytes() if key_path.exists() else b""
    live_key = live_key_path.read_bytes() if live_key_path.exists() else b""
    evidence["encryption_key_present"] = bool(world_key)
    evidence["encryption_key_is_world_local"] = bool(world_key) and world_key != live_key
    if live_key and world_key == live_key:
        problems.append(
            f"{ENCRYPTION_KEY_FILE} is IDENTICAL to the developer's — the world can "
            "decrypt anything encrypted at rest in copied rows")

    # 3. Retained files carry no secret material.
    for name in RETAINED_FILES:
        path = run_data_dir / name
        if not path.exists():
            continue
        raw = path.read_text()
        suspicious = _secret_shaped_values(raw)
        evidence[f"{name}_secret_shaped_values"] = len(suspicious)
        if suspicious:
            problems.append(f"{name} contains {len(suspicious)} secret-shaped value(s)")

    # 4. No secret column holds a value.
    db_path = run_data_dir / "atom.db"
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        try:
            db_report = _assert_db(con)
        finally:
            con.close()
        evidence["db_secret_cells"] = db_report["non_null_cells"]
        evidence["db_secret_tables_checked"] = db_report["tables_checked"]
        if db_report["non_null_cells"]:
            problems.append(
                f"{db_report['non_null_cells']} non-null secret cell(s): "
                f"{db_report['offenders'][:6]}")

    return {
        "isolated": not problems,
        "problems": problems,
        "evidence": evidence,
    }


def _secret_shaped_values(raw: str) -> list[str]:
    """Values that look like live credentials, by shape only. Names are not
    reported, so a definition file listing `api_key_env_var` does not trip it.
    """
    found: list[str] = []
    for pat in (
        r"sk-[A-Za-z0-9]{16,}",                      # openai-style
        r"sk-or-v1-[A-Za-z0-9]{16,}",                # openrouter
        r"ghp_[A-Za-z0-9]{20,}",                     # github
        r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}",  # jwt
        r"AKIA[0-9A-Z]{16}",                          # aws
        r"AIza[0-9A-Za-z_-]{30,}",                    # google
    ):
        found.extend(re.findall(pat, raw))
    return found
