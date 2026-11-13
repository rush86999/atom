"""Guards for the packaged WA-045 connected-browser evidence.

These are cheap structural checks: the package must stay sanitized, internally
consistent (artifact id / exact text / hash), and referenced by the ledger with
paths that actually exist. No browser, server, or log file is read.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = (
    REPO
    / "docs"
    / "acceptance"
    / "evidence"
    / "wa045_canvas_connected_20261113"
    / "canvas-connected-browser.json"
)
LEDGER = REPO / "docs" / "acceptance" / "WHOLE_APP_READINESS_LEDGER_2026-10-27.json"

SECRET_KEY = re.compile(
    r"(authorization|cookie|token|secret|password|api[_-]?key|bearer)", re.IGNORECASE
)
ABSOLUTE_PATH = re.compile(r"^/(Users|Volumes|private|tmp|var|home)/")


class ConnectedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(PACKAGE.read_text())

    def test_artifact_identity_is_consistent(self) -> None:
        payload = self.payload
        canvas_id = payload["artifact"]["canvas_id"]
        self.assertEqual(payload["schema"], "atom-wa045-connected-browser-1")
        self.assertEqual(payload["wa_id"], "WA-045")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["save"]["path"], f"/api/canvas/{canvas_id}")
        self.assertIn(f"/canvas/{canvas_id}", payload["artifact"]["url"])
        self.assertIn(f"/canvas/{canvas_id}", payload["reload"]["url"])
        self.assertEqual(
            payload["save"]["query"]["expected_prior_audit_id"],
            payload["artifact"]["prior_revision_audit_id"],
        )

    def test_exact_text_and_hash_agree(self) -> None:
        payload = self.payload
        text = payload["exact_text"]
        digest = hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(payload["exact_text_sha256"], digest)
        self.assertEqual(payload["exact_text_length"], len(text))
        self.assertEqual(payload["exact_text_lines"], len(text.splitlines()))
        self.assertEqual(payload["save"]["content_sha256"], digest)
        self.assertEqual(payload["reload"]["editor_value_sha256"], digest)
        self.assertTrue(payload["reload"]["editor_value_equals_saved_text"])

    def test_save_and_reload_are_the_claimed_boundary(self) -> None:
        payload = self.payload
        self.assertEqual(payload["save"]["status"], 200)
        self.assertEqual(payload["save"]["method"], "PUT")
        self.assertTrue(payload["reload"]["page_reloaded"])
        self.assertEqual(payload["reload"]["read_back_after_reload"]["GET /api/canvas/{canvas_id}"], 200)
        self.assertEqual(payload["source"]["revision"], "8bb0c66f5fd30988c16585214707bf784fa39d41")
        self.assertEqual(payload["exact_text_length"], payload["save"]["content_length"])

    def test_cdn_scope_is_pinned_and_get_only(self) -> None:
        cdn = self.payload["external_origins"]["cdn"]
        self.assertEqual(cdn["origin"], "https://cdn.jsdelivr.net")
        self.assertEqual(cdn["package"], "monaco-editor@0.55.1")
        self.assertEqual(cdn["methods"], ["GET"])
        self.assertFalse(cdn["data_plane"])
        self.assertFalse(cdn["workspace_data_sent"])
        self.assertEqual(self.payload["external_origins"]["observed_origins"][-1], cdn["origin"])
        for asset in cdn["unique_assets"]:
            with self.subTest(asset=asset):
                self.assertTrue(asset.startswith(cdn["path_prefix"]))
        self.assertEqual(self.payload["checks"][-1]["detail"]["other_non_loopback_requests"], [])

    def test_package_has_no_secrets_or_absolute_paths(self) -> None:
        def items(value, path="root", under_sanitization=False):
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}"
                    yield child_path, key, child, under_sanitization
                    yield from items(
                        child,
                        child_path,
                        under_sanitization or key == "sanitization",
                    )
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from items(child, f"{path}[{index}]", under_sanitization)

        for path, key, value, under_sanitization in items(self.payload):
            with self.subTest(path=path):
                self.assertIsNone(ABSOLUTE_PATH.match(value) if isinstance(value, str) else None)
                if under_sanitization or not isinstance(value, str):
                    continue
                # A key may be *named* like a credential only if it carries no
                # value; every credential-shaped value is rejected outright.
                self.assertIsNone(SECRET_KEY.match(key), key)
                for marker in ("Bearer ", "eyJ", "sk-", "-----BEGIN"):
                    self.assertNotIn(marker, value)
        self.assertTrue(self.payload["sanitization"]["allowlisted_fields_only"])
        self.assertFalse(self.payload["sanitization"]["secrets_present"])
        self.assertFalse(self.payload["sanitization"]["raw_logs_committed"])

    def test_ledger_references_only_existing_evidence(self) -> None:
        ledger = json.loads(LEDGER.read_text())
        wa045 = [item for item in ledger["items"] if item["id"] == "WA-045"]
        self.assertEqual(len(wa045), 1)
        item = wa045[0]
        self.assertEqual(item["status"], "verified")
        self.assertFalse(item["candidate_bound"])
        paths = [entry["path"] for entry in item["evidence"]]
        self.assertIn(
            "docs/acceptance/evidence/wa045_canvas_connected_20261113/canvas-connected-browser.json",
            paths,
        )
        for relative in paths:
            with self.subTest(path=relative):
                self.assertTrue((REPO / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
