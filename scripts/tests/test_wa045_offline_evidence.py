"""Guards for the packaged WA-045 offline/bundled-editor evidence.

Cheap structural checks: the package must stay sanitized, internally
consistent (artifact / audit / text hashes), and genuinely offline (deny policy
with zero non-loopback attempts and same-origin editor assets). No browser,
server, or log file is read.
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
    / "wa045_canvas_offline_20261113"
    / "canvas-blank-lifecycle.json"
)
README = PACKAGE.parent / "README.md"
EARLIER_HARNESS = (
    REPO
    / "docs"
    / "acceptance"
    / "evidence"
    / "wa045_canvas_blank_20261113"
    / "canvas-blank-lifecycle.json"
)
LEDGER = REPO / "docs" / "acceptance" / "WHOLE_APP_READINESS_LEDGER_2026-10-27.json"

SECRET_KEY = re.compile(
    r"(authorization|cookie|token|secret|password|api[_-]?key|bearer)", re.IGNORECASE
)
LOOPBACK_ORIGINS = ("http://127.0.0.1:", "http://localhost:")


class OfflineEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(PACKAGE.read_text())
        cls.checks = (
            cls.payload["browser_checks"] + cls.payload["database_checks"]
        )

    def test_source_is_the_clean_executed_revision(self) -> None:
        payload = self.payload
        self.assertEqual(payload["schema"], "atom-wa045-canvas-blank-lifecycle-1")
        self.assertEqual(payload["wa_id"], "WA-045")
        self.assertEqual(payload["status"], "passed")
        self.assertRegex(payload["commit"], r"^[0-9a-f]{40}$")
        identity = payload["environment"]["backend_identity"]
        self.assertEqual(identity["revision"], payload["commit"])
        self.assertEqual(identity["source_id"], payload["commit"][:12])
        self.assertNotIn("dirty", identity["source_id"])
        self.assertFalse(payload["environment"]["live_database"])
        self.assertTrue(payload["environment"]["fresh_scratch_database"])

    def test_the_journey_is_create_edit_save_reload(self) -> None:
        payload = self.payload
        journey = payload["journey"]
        canvas_id = journey["create"]["canvas_id"]
        self.assertEqual(journey["create"]["status"], 200)
        self.assertEqual(journey["create"]["url"], f"/canvas/{canvas_id}")
        self.assertEqual(journey["save"]["status"], 200)
        self.assertEqual(journey["save"]["canvas_id"], canvas_id)
        self.assertEqual(journey["save"]["verification"]["status"], "verified")
        self.assertEqual(journey["save"]["verification"]["effect"], "committed")
        self.assertEqual(
            journey["save"]["expected_prior_audit_id"],
            journey["create"]["audit_id"],
        )
        self.assertEqual(
            journey["reload"]["revision_audit_id"], journey["save"]["audit_id"]
        )
        self.assertEqual(journey["reload"]["version_badge"], "v2")
        self.assertEqual(journey["reload"]["history_count"], 2)
        self.assertEqual(
            sorted(journey["reload"]["action_types"]), ["create", "update"]
        )
        db_row = next(
            check for check in payload["database_checks"]
            if check["name"] == "scratch database holds the created artifact row"
        )
        self.assertEqual(db_row["detail"]["id"], canvas_id)

    def test_exact_text_agrees_at_every_boundary(self) -> None:
        payload = self.payload
        text = payload["journey"]["exact_text"]
        digest = hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(payload["journey"]["exact_text_sha256"], digest)
        self.assertEqual(
            payload["journey"]["save"]["request_body"], {"content": text}
        )
        self.assertEqual(
            payload["journey"]["reload"]["editor_value_sha256"], digest
        )
        self.assertEqual(
            payload["journey"]["reload"]["get_content_sha256"], digest
        )
        content_check = next(
            check for check in payload["database_checks"]
            if check["name"] == "scratch database content is the exact saved envelope"
        )
        self.assertEqual(content_check["detail"]["content"], {"content": text})
        update_check = next(
            check for check in payload["database_checks"]
            if check["name"] == "scratch database update audit stores the exact text"
        )
        self.assertEqual(update_check["detail"]["content_sha256"], digest)

    def test_external_traffic_was_refused_not_merely_observed(self) -> None:
        payload = self.payload
        self.assertEqual(payload["environment"]["external_asset_policy"], "deny")
        self.assertTrue(payload["environment"]["monaco_assets"].startswith(
            "bundled same-origin /monaco/vs build"
        ))
        traffic = payload["journey"]["external_traffic"]
        self.assertEqual(traffic["policy"], "deny")
        self.assertEqual(traffic["attempted_count"], 0)
        self.assertEqual(traffic["blocked_count"], 0)
        self.assertEqual(traffic["blocked"], [])
        self.assertEqual(payload["journey"]["non_loopback"], [])
        # The editor must have been served by the app, not skipped.
        self.assertGreater(traffic["local_monaco_asset_requests"], 0)
        for origin in payload["journey"]["origins"]:
            with self.subTest(origin=origin):
                self.assertTrue(
                    origin.startswith(LOOPBACK_ORIGINS) or origin == "blob:",
                    origin,
                )

    def test_every_check_passed_including_the_deny_checks(self) -> None:
        self.assertEqual(len(self.checks), 32)
        self.assertTrue(all(check["ok"] for check in self.checks))
        names = {check["name"] for check in self.payload["browser_checks"]}
        self.assertIn("Monaco asset CDN was not contacted (deny policy)", names)
        self.assertIn(
            "external traffic was refused end-to-end (zero non-loopback attempts)",
            names,
        )
        self.assertIn("editor rendered from the bundled same-origin build", names)

    def test_same_exact_text_as_the_earlier_online_runs(self) -> None:
        earlier = json.loads(EARLIER_HARNESS.read_text())
        self.assertEqual(
            self.payload["journey"]["exact_text"],
            earlier["journey"]["exact_text"],
        )
        self.assertEqual(
            self.payload["journey"]["exact_text_sha256"],
            earlier["journey"]["exact_text_sha256"],
        )

    def test_package_has_no_credentials(self) -> None:
        def items(value, path="root"):
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}"
                    yield child_path, key, child
                    yield from items(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from items(child, f"{path}[{index}]")

        for path, key, value in items(self.payload):
            if not isinstance(value, str):
                continue
            with self.subTest(path=path):
                for marker in ("Bearer ", "eyJ", "sk-", "-----BEGIN"):
                    self.assertNotIn(marker, value)
                # A credential-shaped key may only carry a redaction marker or
                # an empty value; never a live secret.
                if SECRET_KEY.search(key):
                    self.assertTrue(
                        value == "" or value.endswith("_redacted"), path
                    )

    def test_readme_and_ledger_reference_this_package(self) -> None:
        self.assertTrue(README.is_file())
        readme = README.read_text()
        self.assertIn("external traffic", readme.lower())
        self.assertIn("f201216b6", readme)
        ledger = json.loads(LEDGER.read_text())
        wa045 = [item for item in ledger["items"] if item["id"] == "WA-045"]
        self.assertEqual(len(wa045), 1)
        item = wa045[0]
        self.assertEqual(item["status"], "verified")
        self.assertFalse(item["candidate_bound"])
        paths = [entry["path"] for entry in item["evidence"]]
        self.assertIn(PACKAGE.relative_to(REPO).as_posix(), paths)
        for relative in paths:
            with self.subTest(path=relative):
                self.assertTrue((REPO / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
