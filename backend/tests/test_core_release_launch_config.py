# -*- coding: utf-8 -*-
"""The recorded core UI evidence is bound to its actual launch settings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "docs/acceptance/CORE_RELEASE_UI_LAUNCH_CONFIG_2026-10-28.json"
FAILED_MANIFEST = (
    ROOT / "docs/acceptance/evidence/whole_app_20261027/"
    "core_release_ui_loop_20261028/source_manifest.json"
)
CANVAS = ROOT / "frontend-nextjs/pages/canvas/[id].tsx"


def test_failed_ui_run_is_bound_to_180s_backend_and_300s_client():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    failed = config["recorded_failed_run"]
    assert failed["backend"]["ATOM_CHAT_TURN_BUDGET_SECONDS"] == 180
    assert failed["client"]["timeout_ms"] == 300000

    manifest = json.loads(FAILED_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["config"]["ATOM_CHAT_TURN_BUDGET_SECONDS"] == "180"
    assert manifest["config"]["ATOM_CHAT_STREAMING"] == "false"
    assert manifest["config"]["ATOM_LOCAL_ONLY"] == "true"
    assert manifest["config"]["ATOM_REVIEW_STRUCTURED"] == "0"


def test_canvas_client_still_uses_the_frozen_300s_timeout():
    source = CANVAS.read_text(encoding="utf-8")
    assert "timeout: 300000," in source


def test_candidate_loop_did_not_inherit_an_earlier_budget():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert all(
        item["transferable"] is False
        for item in config["superseded_configurations"]
    )
    assert config["candidate_run"]["backend"][
        "ATOM_CHAT_TURN_BUDGET_SECONDS"] == 180
    assert config["candidate_run"]["client"]["timeout_ms"] == 300000
