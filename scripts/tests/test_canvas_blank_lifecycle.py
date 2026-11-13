"""Unit tests for the WA-045 canvas acceptance driver (no browser, no servers)."""
from __future__ import annotations

import importlib.util
import json
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "acceptance" / "canvas_blank_lifecycle.py"
)
SPEC = importlib.util.spec_from_file_location("canvas_blank_lifecycle", MODULE_PATH)
assert SPEC and SPEC.loader
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


class GuardedWorldPathTests(unittest.TestCase):
    def test_refuses_repository_paths(self) -> None:
        root = DRIVER.configured_worlds_root()
        for refusals in (
            DRIVER.REPO,
            DRIVER.REPO / "backend",
            DRIVER.REPO / "backend" / "data",
            DRIVER.LIVE_DB,
            root,
        ):
            with self.subTest(path=str(refusals)):
                with self.assertRaises(DRIVER.Refused):
                    DRIVER.guarded_world_path(refusals)

    def test_refuses_world_outside_configured_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "not-a-world"
            with self.assertRaises(DRIVER.Refused):
                DRIVER.guarded_world_path(outside)

    def test_accepts_fresh_world_under_configured_root(self) -> None:
        candidate = DRIVER.configured_worlds_root() / "wa045-unit-test-does-not-exist"
        self.assertEqual(DRIVER.guarded_world_path(candidate), candidate)


class SanitizeTests(unittest.TestCase):
    def test_redacts_credential_shaped_keys_recursively(self) -> None:
        # Values are generated per run so no credential-shaped literal is stored
        # in the repository while every field still carries a real value.
        authorization = f"Bearer {secrets.token_urlsafe(24)}"
        access_token = secrets.token_urlsafe(24)
        cookie = secrets.token_urlsafe(24)
        api_key = secrets.token_urlsafe(24)
        password = secrets.token_urlsafe(24)
        client_secret = secrets.token_urlsafe(24)
        payload = {
            "canvas_id": "abc",
            "save": {
                "authorization": authorization,
                "access_token": access_token,
                "cookie": cookie,
                "api_key": api_key,
                "password": password,
                "audit_id": "keep",
            },
            "nested": [{"client_secret": client_secret, "content": "keep"}],
        }
        clean = DRIVER.sanitize(payload)
        text = json.dumps(clean)
        self.assertNotIn(authorization, text)
        for field, value in (
            ("access_token", access_token),
            ("cookie", cookie),
            ("api_key", api_key),
            ("password", password),
            ("client_secret", client_secret),
        ):
            with self.subTest(field=field):
                self.assertNotIn(value, text)
                self.assertNotIn(json.dumps(value), text)
        self.assertEqual(clean["canvas_id"], "abc")
        self.assertEqual(clean["save"]["audit_id"], "keep")
        self.assertEqual(clean["nested"][0]["content"], "keep")
        self.assertTrue(clean["save"]["authorization_redacted"])
        self.assertTrue(clean["nested"][0]["client_secret_redacted"])


class ChildEnvTests(unittest.TestCase):
    def test_blanks_provider_credentials_and_drops_test_mode(self) -> None:
        live_key = secrets.token_urlsafe(24)
        base = {
            "OPENAI_API_KEY": live_key,
            "DATABASE_URL": "sqlite:////live/atom.db",
            "TESTING": "1",
            "PYTEST_CURRENT_TEST": "x",
            "ENVIRONMENT": "production",
            "KEEP": "yes",
        }
        env = DRIVER.child_env({"DATABASE_URL": "sqlite:////scratch/atom.db"}, base=base)
        self.assertEqual(env["OPENAI_API_KEY"], "")
        self.assertNotIn(live_key, env.values())
        self.assertEqual(env["DATABASE_URL"], "sqlite:////scratch/atom.db")
        self.assertNotIn("TESTING", env)
        self.assertNotIn("PYTEST_CURRENT_TEST", env)
        self.assertNotIn("ENVIRONMENT", env)
        self.assertEqual(env["KEEP"], "yes")


class DatabaseCheckTests(unittest.TestCase):
    def _make_db(self, path: Path, text: str) -> str:
        canvas_id = "11111111-1111-4111-8111-111111111111"
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                "CREATE TABLE canvases (id TEXT PRIMARY KEY, name TEXT, "
                "canvas_type TEXT, content TEXT, created_by TEXT)")
            conn.execute(
                "CREATE TABLE canvas_audit (id TEXT, canvas_id TEXT, "
                "action_type TEXT, details_json TEXT, created_at TEXT)")
            conn.execute(
                "INSERT INTO canvases VALUES (?,?,?,?,?)",
                (canvas_id, "Untitled canvas", "document",
                 json.dumps({"content": text}), "user-1"))
            conn.execute(
                "INSERT INTO canvas_audit VALUES (?,?,?,?,?)",
                ("audit-1", canvas_id, "create",
                 json.dumps({"content": {"content": ""}}), "2026-11-13T00:00:00"))
            conn.execute(
                "INSERT INTO canvas_audit VALUES (?,?,?,?,?)",
                ("audit-2", canvas_id, "update",
                 json.dumps({"content": {"content": text}}), "2026-11-13T00:00:01"))
            conn.commit()
        finally:
            conn.close()
        return canvas_id

    def test_all_checks_pass_for_exact_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atom.db"
            text = "exact\ntext"
            canvas_id = self._make_db(db, text)
            checks = DRIVER.database_checks(db, canvas_id, text)
            self.assertTrue(checks)
            self.assertTrue(all(check["ok"] for check in checks), checks)

    def test_mismatched_text_fails_the_store_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atom.db"
            canvas_id = self._make_db(db, "stored")
            checks = DRIVER.database_checks(db, canvas_id, "different")
            self.assertTrue(checks)
            self.assertFalse(all(check["ok"] for check in checks))

    def test_missing_database_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checks = DRIVER.database_checks(Path(tmp) / "absent.db", "x", "y")
            self.assertEqual(len(checks), 1)
            self.assertFalse(checks[0]["ok"])


class HarnessRecordTests(unittest.TestCase):
    def test_missing_record_is_a_failed_status_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = DRIVER.read_harness_record(Path(tmp) / "absent.json")
            self.assertEqual(record["status"], "failed")
            self.assertIn("error", record)

    def test_malformed_record_is_a_failed_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json")
            record = DRIVER.read_harness_record(path)
            self.assertEqual(record["status"], "failed")


if __name__ == "__main__":
    unittest.main()
