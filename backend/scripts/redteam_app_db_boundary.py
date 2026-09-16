#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end red-team of the app-DB read boundary (audit item 1).

Reproduces, against a SCRATCH database containing dummy secrets, whether a
model-authored SELECT can read a table outside the allowlist. Parse-time
validation is necessary but not sufficient: the authoritative question is what
SQLite is actually permitted to read once the statement is handed to it.

Run::

    cd backend && ./venv/bin/python scripts/redteam_app_db_boundary.py

Exit code 0 = every attack was contained; 1 = at least one read escaped.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.app_db_query as adb  # noqa: E402

DUMMY_SECRET = "DUMMY-SECRET-DO-NOT-READ"

# Each attack is (name, sql). The target table `users` is NOT allowlisted and
# carries a column whose name is secret-shaped; `user_sessions` is neither
# allowlisted nor secret-shaped, which isolates "the allowlist failed" from
# "the column-name regex happened to catch it".
ATTACKS: List[Tuple[str, str]] = [
    ("double-quoted table", 'SELECT * FROM "users"'),
    ("single-quoted table", "SELECT * FROM 'users'"),
    ("bracket-quoted table", "SELECT * FROM [users]"),
    ("backtick-quoted table", "SELECT * FROM `users`"),
    ("subquery aliased to allowlisted name",
     "SELECT * FROM (SELECT * FROM users) canvases"),
    ("single-quoted subquery alias",
     "SELECT * FROM (SELECT * FROM 'users') canvases"),
    ("non-secret-shaped unlisted table", "SELECT * FROM user_sessions"),
    ("single-quoted non-secret table", "SELECT * FROM 'user_sessions'"),
    ("comma join", "SELECT c.title, u.password_hash FROM canvases c, users u"),
    ("union", "SELECT title FROM canvases UNION SELECT password_hash FROM users"),
    ("in-subquery", "SELECT id FROM canvases WHERE id IN "
                    "(SELECT id FROM users)"),
    ("catalog table", "SELECT name FROM sqlite_master"),
    ("wildcard over withheld column", "SELECT * FROM canvases"),
    ("explicit withheld column", "SELECT api_key FROM canvases"),
    ("withheld column in predicate", "SELECT id FROM canvases WHERE api_key IS NOT NULL"),
]


def make_scratch_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE canvases (id TEXT, title TEXT, tenant_id TEXT, api_key TEXT);
        CREATE TABLE users (id TEXT, email TEXT, password_hash TEXT);
        CREATE TABLE user_sessions (id TEXT, user_id TEXT, refresh_token TEXT);
        CREATE TABLE integration_tokens (id TEXT, access_token TEXT);
        INSERT INTO canvases VALUES ('c1','Quote','default','CANVAS-KEY');
        INSERT INTO users VALUES ('u1','a@b.c','%s');
        INSERT INTO user_sessions VALUES ('s1','u1','%s');
        INSERT INTO integration_tokens VALUES ('t1','%s');
        """ % (DUMMY_SECRET, DUMMY_SECRET, DUMMY_SECRET))
    con.commit()
    con.close()


class _StubResult:
    def __init__(self, sql: str) -> None:
        self.sql = sql


class _StubLLM:
    """Returns whatever SQL the attack supplies, as the real generator would."""

    def __init__(self, sql: str) -> None:
        self._sql = sql


async def _run_attack(sql: str, db_path: str) -> Dict[str, Any]:
    import core.database as dbmod
    import core.llm.pinned_planning as pp

    original_url = dbmod.get_database_url
    original_call = pp.pinned_structured_call

    async def fake_call(llm, prompt, response_model, call_kwargs=None,
                        system_instruction=""):
        return _StubResult(llm._sql)

    dbmod.get_database_url = lambda: f"sqlite:///{db_path}"
    pp.pinned_structured_call = fake_call
    adb._schema_lines = lambda: ["canvases(id, title)", "chat_sessions(id)"]
    try:
        return await adb.answer_from_app_db("q", "default",
                                            llm_service=_StubLLM(sql)) or {}
    finally:
        dbmod.get_database_url = original_url
        pp.pinned_structured_call = original_call


async def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "scratch.db")
        make_scratch_db(db_path)

        escaped: List[str] = []
        print(f"{'attack':46} {'contained?':11} detail")
        print("-" * 100)
        for name, sql in ATTACKS:
            out = await _run_attack(sql, db_path)
            blob = repr(out)
            leaked = DUMMY_SECRET in blob
            # A withheld column returned as a value is also an escape, even
            # when it is not the dummy secret.
            leaked_cols = [c for c in (out.get("columns") or [])
                           if adb._FORBIDDEN_COLUMN_RE.search(str(c))]
            if leaked or leaked_cols:
                escaped.append(name)
                detail = ("LEAKED SECRET" if leaked
                          else f"LEAKED COLUMNS {leaked_cols}")
                print(f"{name:46} {'NO':11} {detail}")
            else:
                detail = (f"returned {out.get('row_count')} row(s) "
                          f"cols={out.get('columns')}") if out else "refused/empty"
                print(f"{name:46} {'yes':11} {detail}")

        print("-" * 100)
        if escaped:
            print(f"BOUNDARY FAILED for {len(escaped)}/{len(ATTACKS)} attacks: {escaped}")
            return 1
        print(f"All {len(ATTACKS)} attacks contained.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
