"""Unit tests for Swarm Coordination subsystems.

Covers:
  1. FieldGuideService — line-budget enforcement, context injection,
     deduplication, section management.
  2. ConductorAgent._reconcile_branch_conflicts — conflict-free merge,
     disagreement resolution, empty-branch guard.
  3. MegafileDetector — LOC threshold, edit-frequency threshold, reset,
     CRITICAL vs WARNING severity, patch proposal format.
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrapping (backend is the package root)
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parents[3]  # tests/unit/core/ → backend/
sys.path.insert(0, str(BACKEND_DIR))


# ===========================================================================
# 1. FieldGuideService
# ===========================================================================

class TestFieldGuideService:
    """Tests for core.field_guide_service.FieldGuideService."""

    @pytest.fixture
    def tmp_service(self, tmp_path):
        """Return a FieldGuideService scoped to a temp directory."""
        from core.field_guide_service import FieldGuideService
        return FieldGuideService(base_dir=tmp_path)

    def test_get_field_guide_context_empty(self, tmp_service):
        """Returns empty string when no guide has been written yet."""
        result = tmp_service.get_field_guide_context("ws_new")
        assert result == ""

    def test_update_creates_guide(self, tmp_service):
        """First update creates the file with the expected preamble."""
        result = tmp_service.update_field_guide("ws1", "Tool Failures", "shell tool always times out at 30 s")
        assert "path" in result
        assert Path(result["path"]).exists()
        raw = tmp_service.get_raw_guide("ws1")
        assert "Field Guide" in raw
        assert "Tool Failures" in raw
        assert "shell tool always times out" in raw

    def test_context_injection_header(self, tmp_service):
        """get_field_guide_context wraps content in injection header."""
        tmp_service.update_field_guide("ws2", "Layout", "src/ holds all entry points")
        ctx = tmp_service.get_field_guide_context("ws2")
        assert "🗺 Workspace Field Guide" in ctx
        assert "Layout" in ctx

    def test_line_budget_enforced(self, tmp_service):
        """Guide never exceeds the configured budget."""
        budget = 20
        for i in range(40):
            tmp_service.update_field_guide(
                "ws_budget",
                f"Topic {i}",
                f"Insight number {i} about something interesting.",
                budget=budget,
            )
        raw = tmp_service.get_raw_guide("ws_budget")
        lines = raw.splitlines()
        assert len(lines) <= budget, f"Guide has {len(lines)} lines, expected ≤ {budget}"

    def test_deduplication_skips_identical_insight(self, tmp_service):
        """Identical insight under the same topic is not appended twice."""
        insight = "always use absolute paths for tool arguments"
        tmp_service.update_field_guide("ws_dedup", "Paths", insight)
        result2 = tmp_service.update_field_guide("ws_dedup", "Paths", insight)
        assert result2.get("duplicate_skipped") is True
        raw = tmp_service.get_raw_guide("ws_dedup")
        assert raw.count(insight) == 1

    def test_multiple_topics_create_sections(self, tmp_service):
        """Different topics create distinct section headings."""
        tmp_service.update_field_guide("ws_multi", "Credentials", "never print env vars")
        tmp_service.update_field_guide("ws_multi", "Timeouts", "default timeout is 60 s")
        raw = tmp_service.get_raw_guide("ws_multi")
        assert "### Credentials" in raw
        assert "### Timeouts" in raw

    def test_clear_guide(self, tmp_service):
        """clear_guide removes the file and returns True."""
        tmp_service.update_field_guide("ws_clear", "X", "something")
        cleared = tmp_service.clear_guide("ws_clear")
        assert cleared is True
        assert tmp_service.get_field_guide_context("ws_clear") == ""

    def test_clear_nonexistent_returns_false(self, tmp_service):
        assert tmp_service.clear_guide("ws_ghost") is False

    def test_agent_id_tagged_in_entry(self, tmp_service):
        """agent_id appears in the written entry line."""
        tmp_service.update_field_guide("ws_tag", "Debug", "prefer step-debug over print", agent_id="conductor-01")
        raw = tmp_service.get_raw_guide("ws_tag")
        assert "conductor-01" in raw


# ===========================================================================
# 2. ConductorAgent._reconcile_branch_conflicts
# ===========================================================================

class TestBranchReconciler:
    """Tests for ConductorAgent._reconcile_branch_conflicts."""

    @pytest.fixture
    def conductor(self):
        from core.orchestration.conductor_agent import ConductorAgent, ConductorConfig
        return ConductorAgent(ConductorConfig())

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_all_branches_agree(self, conductor):
        """When all branches return the same dict, it is returned unchanged."""
        branches = [
            {"step_id": "s1", "output": "hello", "status": "completed"},
            {"step_id": "s1", "output": "hello", "status": "completed"},
            {"step_id": "s1", "output": "hello", "status": "completed"},
        ]
        result = self._run(conductor._reconcile_branch_conflicts("s1", branches))
        assert result is not None
        assert result["output"] == "hello"
        assert result["_reconciled"] is True

    def test_partial_disagreement_merged(self, conductor):
        """Agreed keys are merged; contested keys resolved by frequency."""
        branches = [
            {"step_id": "s2", "action": "read",  "target": "file.py", "status": "ok"},
            {"step_id": "s2", "action": "read",  "target": "file.py", "status": "ok"},
            {"step_id": "s2", "action": "write", "target": "file.py", "status": "ok"},
        ]
        result = self._run(conductor._reconcile_branch_conflicts("s2", branches))
        assert result is not None
        # "read" appears 2× — should win for "action"
        assert result["action"] == "read"
        # "target" and "status" agree across all → merged cleanly
        assert result["target"] == "file.py"

    def test_empty_branch_list_returns_none(self, conductor):
        result = self._run(conductor._reconcile_branch_conflicts("s3", []))
        assert result is None

    def test_non_dict_branches_handled_gracefully(self, conductor):
        """Non-dict branch outputs don't crash the reconciler."""
        branches: List[Any] = ["text_result", "text_result", 42]
        # Should not raise — returns None or a result
        result = self._run(conductor._reconcile_branch_conflicts("s4", branches))
        # Result may be None since no dict keys to merge
        assert result is None or isinstance(result, dict)

    def test_metadata_fields_present(self, conductor):
        branches = [{"step_id": "s5", "x": 1}, {"step_id": "s5", "x": 1}]
        result = self._run(conductor._reconcile_branch_conflicts("s5", branches))
        assert result["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"
        assert result["_branch_count"] == 2


# ===========================================================================
# 3. MegafileDetector
# ===========================================================================

class TestMegafileDetector:
    """Tests for core.sandbox_tripwire.MegafileDetector."""

    @pytest.fixture
    def detector(self):
        from core.sandbox_tripwire import MegafileDetector
        return MegafileDetector(loc_threshold=800, edit_threshold=5)

    def test_no_warning_below_thresholds(self, detector):
        warning = detector.record_edit("/src/small.py", line_count=100)
        assert warning is None

    def test_loc_threshold_triggers_warning(self, detector):
        warning = detector.record_edit("/src/big.py", line_count=850)
        assert warning is not None
        assert warning.severity == "WARNING"
        assert warning.line_count == 850

    def test_edit_threshold_triggers_warning(self, detector):
        for i in range(4):
            w = detector.record_edit("/src/hot.py", line_count=50)
            assert w is None, f"Premature warning on edit {i+1}"
        warning = detector.record_edit("/src/hot.py", line_count=50)
        assert warning is not None
        assert warning.edit_count == 5
        assert warning.severity == "WARNING"

    def test_both_thresholds_critical(self, detector):
        for _ in range(5):
            detector.record_edit("/src/mega.py", line_count=900)
        warning = detector.record_edit("/src/mega.py", line_count=900)
        assert warning is not None
        assert warning.severity == "CRITICAL"

    def test_is_blocked_after_threshold(self, detector):
        for _ in range(5):
            detector.record_edit("/src/blocked.py")
        assert detector.is_blocked("/src/blocked.py") is True

    def test_is_not_blocked_before_threshold(self, detector):
        detector.record_edit("/src/ok.py")
        assert detector.is_blocked("/src/ok.py") is False

    def test_reset_clears_counters(self, detector):
        for _ in range(5):
            detector.record_edit("/src/reset_me.py")
        detector.reset()
        assert not detector.is_blocked("/src/reset_me.py")
        # Next edit starts fresh
        w = detector.record_edit("/src/reset_me.py", line_count=50)
        assert w is None

    def test_summary_sorted_descending(self, detector):
        for _ in range(3):
            detector.record_edit("/src/a.py")
        for _ in range(7):
            detector.record_edit("/src/b.py")
        summary = detector.summary()
        assert summary[0]["edits"] >= summary[-1]["edits"]

    def test_patch_proposal_format(self, detector):
        for _ in range(5):
            detector.record_edit("/src/large.py", line_count=900)
        warning = detector.record_edit("/src/large.py", line_count=900)
        assert warning is not None
        proposal = warning.to_harness_patch_proposal()
        assert proposal["target_component"] == "file_modularization"
        assert proposal["mutation_payload"]["action"] == "decompose_into_modules"
        assert "patch_id" in proposal
