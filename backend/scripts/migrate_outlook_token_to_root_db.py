"""
Migrate the Outlook/Microsoft OAuth tokens from the stale backend-local DB
(backend/atom_dev.db, encrypted with backend/data/byok_encryption_key) into
the canonical repo-root DB (atom_dev.db, encrypted with data/byok_encryption_key).

Why: DATABASE_URL=sqlite:///./atom_dev.db is CWD-relative, so the app created
TWO DBs over time (run from repo root vs. run from backend/). The live user's
Zoho tokens landed in the root DB, but the Outlook token was written to the
backend DB under an older user id. The tokens are Fernet-encrypted with
per-CWD key files, so a raw row copy would be undecryptable — this script
decrypts with the source key and re-encrypts with the destination key.

Usage:
    PYTHONPATH=".;./backend" python backend/scripts/migrate_outlook_token_to_root_db.py
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List

from cryptography.fernet import Fernet, InvalidToken

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SRC_DB = os.path.join(ROOT, "backend", "atom_dev.db")
DST_DB = os.path.join(ROOT, "atom_dev.db")
SRC_KEY_FILE = os.path.join(ROOT, "backend", "data", "byok_encryption_key")
DST_KEY_FILE = os.path.join(ROOT, "data", "byok_encryption_key")

# Live user (has Zoho tokens + chat sessions in the root DB).
TARGET_USER_ID = "67e0bae3-4256-495a-bc8a-cab9d8c4d81f"

_COLUMNS = [
    "id", "tenant_id", "user_id", "workspace_id", "provider", "access_token",
    "refresh_token", "token_type", "expires_at", "instance_url", "scope",
    "status", "credential_metadata", "created_at", "updated_at",
]


def _load_key(path: str) -> bytes:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip().encode()


def _decrypt(ciphertext: str, key: bytes) -> str:
    if not ciphertext:
        return ""
    try:
        return Fernet(key).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""


def _encrypt(plaintext: str, key: bytes) -> str:
    if not plaintext:
        return ""
    return Fernet(key).encrypt(plaintext.encode()).decode()


def _rows(db_path: str, provider_filter: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM integration_tokens WHERE provider IN (?, ?)",
            ("outlook", "microsoft"),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def main() -> int:
    src_key = _load_key(SRC_KEY_FILE)
    dst_key = _load_key(DST_KEY_FILE)

    src_rows = _rows(SRC_DB, "microsoft")
    print(f"Source rows (backend/atom_dev.db): {len(src_rows)}")

    migrated = 0
    for row in src_rows:
        provider = row["provider"]
        access = _decrypt(row["access_token"], src_key)
        refresh = _decrypt(row["refresh_token"] or "", src_key)
        if not access:
            print(f"  ! {provider}: could not decrypt with source key — skipping")
            continue
        print(f"  {provider}: decrypted ok "
              f"(access={len(access)} chars, refresh={'yes' if refresh else 'no'})")

        con = sqlite3.connect(DST_DB)
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT id FROM integration_tokens WHERE provider = ? AND user_id = ?",
                (provider, TARGET_USER_ID),
            )
            existing = cur.fetchone()

            payload = dict(row)
            payload["user_id"] = TARGET_USER_ID
            payload["access_token"] = _encrypt(access, dst_key)
            payload["refresh_token"] = _encrypt(refresh, dst_key) if refresh else None
            payload["status"] = "active"

            if existing:
                set_clause = ", ".join(f"{c} = ?" for c in _COLUMNS if c != "id")
                cur.execute(
                    f"UPDATE integration_tokens SET {set_clause} WHERE id = ?",
                    [payload[c] for c in _COLUMNS if c != "id"] + [existing[0]],
                )
                print(f"  {provider}: updated existing row {existing[0]}")
            else:
                cur.execute(
                    f"INSERT INTO integration_tokens ({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join('?' for _ in _COLUMNS)})",
                    [payload[c] for c in _COLUMNS],
                )
                print(f"  {provider}: inserted new row {payload['id']}")
            con.commit()
            migrated += 1
        finally:
            con.close()

    # Verify: read back from the destination DB and decrypt with the dest key.
    con = sqlite3.connect(DST_DB)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM integration_tokens WHERE provider IN ('outlook','microsoft') "
            "AND user_id = ?",
            (TARGET_USER_ID,),
        )
        for r in cur.fetchall():
            plain = _decrypt(r["access_token"], dst_key)
            ok = plain.startswith("eyJ") or len(plain) > 100
            print(f"verify {r['provider']}: decrypt with dest key -> {'OK' if ok else 'FAIL'}")
    finally:
        con.close()

    print(f"Done. Migrated {migrated} token row(s) to {DST_DB} for user {TARGET_USER_ID}.")
    return 0 if migrated else 1


if __name__ == "__main__":
    sys.exit(main())
