"""BPE workspace unit tests (docs/architecture/BPE_WORKSPACE_PLAN.md, Phase 0+1).

Covers the paper-grounded invariants: bounded Progress (cap 8), LFU-bounded
Experience (cap 80/category, top-3 recall), note buffering, render bounds,
round-trip serialization, meta-action registration, and flag gating
(shadow-first).
"""
from __future__ import annotations

import asyncio

import pytest

from core.bpe.workspace import (
    EXPERIENCE_CATEGORIES,
    MAX_ENTRIES_PER_CATEGORY,
    MAX_RENDER_CHARS,
    MAX_SUBGOALS,
    BPEWorkspace,
    get_workspace,
    reset_registry,
    workspace_key,
)


def apply(ws: BPEWorkspace, *args):
    """Sync helper: run one meta-action."""
    return asyncio.run(ws.apply(*args))


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Progress (P): commit semantics + cap
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgress:
    def test_commit_adds_subgoal(self):
        ws = BPEWorkspace()
        result = apply(ws, "commit", "draft invoice")
        assert result["success"] is True
        assert result["op"] == "added"
        assert len(ws.progress) == 1
        assert ws.progress[0].status == "pending"

    @pytest.mark.asyncio
    async def test_commit_via_apply_async(self):
        ws = BPEWorkspace()
        result = await ws.apply("commit", {"title": "verify totals"})
        assert result["success"] is True
        assert ws.progress[0].title == "verify totals"

    def test_commit_requires_title(self):
        assert apply(BPEWorkspace(), "commit", "  ")["success"] is False

    def test_progress_capped_at_eight(self):
        ws = BPEWorkspace()
        for i in range(12):
            apply(ws, "commit", f"subgoal {i}")
        assert len(ws.progress) == MAX_SUBGOALS
        # All pending → oldest dropped first.
        assert ws.progress[0].title == "subgoal 4"

    def test_status_update_by_prefix(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "fetch quarterly report")
        result = apply(ws, "commit", {"title": "fetch quarterly", "status": "done"})
        assert result["success"] is True
        assert result["op"] == "status"
        assert ws.progress[0].status == "done"

    def test_status_update_rejects_invalid_status(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "task")
        result = apply(ws, "commit", {"title": "task", "status": "exploded"})
        assert result["success"] is False

    def test_status_update_no_match_fails(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "real task")
        result = apply(ws, "commit", {"title": "nonexistent", "status": "done"})
        assert result["success"] is False

    def test_done_subgoals_drop_first_at_cap(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "finished early")
        apply(ws, "commit", {"title": "finished early", "status": "done"})
        for i in range(MAX_SUBGOALS):
            apply(ws, "commit", f"pending {i}")
        titles = [s.title for s in ws.progress]
        assert "finished early" not in titles  # done dropped before pending
        assert len(titles) == MAX_SUBGOALS


# ---------------------------------------------------------------------------
# Experience (E): LFU bounds + recall
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExperience:
    def test_add_and_recall_keyword_overlap(self):
        ws = BPEWorkspace()
        ws.experience.add("skills", "always verify invoice totals before export")
        results = ws.experience.recall("invoice totals")
        assert len(results) == 1
        assert "invoice" in results[0]["content"]
        assert results[0]["category"] == "skills"

    def test_recall_top3_per_query(self):
        ws = BPEWorkspace()
        for i in range(6):
            ws.experience.add("priors", f"slack files live in channel-{i} archive")
        results = ws.experience.recall("slack channel archive")
        assert len(results) == 3

    def test_recall_no_match_empty(self):
        ws = BPEWorkspace()
        ws.experience.add("skills", "unrelated entry")
        assert ws.experience.recall("quantum chromodynamics") == []

    def test_unknown_category_rejected(self):
        ws = BPEWorkspace()
        assert ws.experience.add("not_a_category", "x") is False

    def test_lfu_cap_evicts_least_used(self):
        ws = BPEWorkspace()
        cat = "mistakes"
        ws.experience.add(cat, "do not edit production rows directly")
        ws.experience.add(cat, "never trust cached auth tokens")
        # Mark the first entry used so LFU must keep it.
        ws.experience.recall("production rows")
        for i in range(MAX_ENTRIES_PER_CATEGORY - 1):
            ws.experience.add(cat, f"filler mistake number {i}")
        assert len(ws.experience._categories[cat]) == MAX_ENTRIES_PER_CATEGORY
        contents = [e.content for e in ws.experience._categories[cat].values()]
        assert "do not edit production rows directly" in contents

    def test_dedupe_increments_uses(self):
        ws = BPEWorkspace()
        assert ws.experience.add("skills", "check currency before convert") is True
        assert ws.experience.add("skills", "check currency before convert") is False
        entry = ws.experience._categories["skills"]["check currency before convert"]
        assert entry.uses == 1

    def test_consolidate_removes(self):
        ws = BPEWorkspace()
        ws.experience.add("skills", "obsolete procedure")
        removed = ws.experience.consolidate("skills", ["obsolete procedure"])
        assert removed == 1
        assert ws.experience.recall("obsolete procedure") == []

    def test_all_four_categories_exist(self):
        ws = BPEWorkspace()
        for cat in EXPERIENCE_CATEGORIES:
            assert ws.experience.add(cat, f"entry for {cat}") is True


# ---------------------------------------------------------------------------
# note (temp buffer) + drain
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNotes:
    def test_note_buffers(self):
        ws = BPEWorkspace()
        result = apply(ws, "note", "user prefers CSV exports")
        assert result["success"] is True
        assert ws._pending_notes == ["user prefers CSV exports"]

    def test_note_requires_content(self):
        assert apply(BPEWorkspace(), "note", "")["success"] is False

    def test_note_truncated_to_cap(self):
        ws = BPEWorkspace()
        apply(ws, "note", "x" * 5000)
        assert len(ws._pending_notes[0]) == 400

    def test_drain_clears_buffer(self):
        ws = BPEWorkspace()
        apply(ws, "note", "lesson one")
        notes = ws.drain_pending_notes()
        assert notes == ["lesson one"]
        assert ws.drain_pending_notes() == []


# ---------------------------------------------------------------------------
# track + unknown actions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTrack:
    @pytest.mark.asyncio
    async def test_track_without_adapter_empty_belief(self):
        ws = BPEWorkspace()
        result = await ws.apply("track", "acme corp", {"workspace_id": "w"})
        assert result["success"] is True
        assert result["belief"] == ""

    @pytest.mark.asyncio
    async def test_track_with_async_adapter(self):
        class Adapter:
            async def belief_summary(self, topic, context):
                return f"facts about {topic}"

        ws = BPEWorkspace()
        ws.adapter = Adapter()
        result = await ws.apply("track", "acme corp", {})
        assert result["belief"] == "facts about acme corp"

    @pytest.mark.asyncio
    async def test_track_sync_adapter_supported(self):
        class Adapter:
            def belief_summary(self, topic, context):
                return f"sync facts about {topic}"

        ws = BPEWorkspace()
        ws.adapter = Adapter()
        result = await ws.apply("track", "acme", {})
        assert result["belief"] == "sync facts about acme"

    @pytest.mark.asyncio
    async def test_track_belief_truncated(self):
        class Adapter:
            async def belief_summary(self, topic, context):
                return "y" * 5000

        ws = BPEWorkspace()
        ws.adapter = Adapter()
        result = await ws.apply("track", "t", {})
        assert len(result["belief"]) == 800

    @pytest.mark.asyncio
    async def test_unknown_action_fails_gracefully(self):
        result = await BPEWorkspace().apply("explode")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_adapter_crash_never_raises(self):
        class Adapter:
            async def belief_summary(self, topic, context):
                raise RuntimeError("boom")

        ws = BPEWorkspace()
        ws.adapter = Adapter()
        result = await ws.apply("track", "t", {})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Render bounds + serialization round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderAndSerialize:
    def test_render_empty_when_unused(self):
        assert BPEWorkspace().render() == ""

    def test_render_includes_sections(self):
        ws = BPEWorkspace()
        apply(ws, "commit", "collect data")
        apply(ws, "commit", {"title": "collect data", "status": "done"})
        apply(ws, "note", "user hates pie charts")
        ws.experience.add("priors", "invoices live in /finance/2026")
        block = ws.render()
        assert block.startswith("WORKSPACE STATE")
        assert "[done] collect data" in block
        assert "user hates pie charts" in block
        assert "invoices live in /finance/2026" in block

    def test_render_bounded(self):
        ws = BPEWorkspace()
        for i in range(MAX_SUBGOALS):
            apply(ws, "commit", "x" * 500 + str(i))
        assert len(ws.render()) <= MAX_RENDER_CHARS + 1  # + ellipsis

    def test_round_trip(self):
        ws = BPEWorkspace("ws1", "agentA", "sess1")
        apply(ws, "commit", "step one")
        apply(ws, "note", "a lesson")
        ws.experience.add("skills", "procedure alpha")
        restored = BPEWorkspace.from_dict(ws.to_dict())
        assert restored.workspace_id == "ws1"
        assert restored.agent_id == "agentA"
        assert restored.scope_key == "sess1"
        assert restored.progress[0].title == "step one"
        assert restored._pending_notes == ["a lesson"]
        assert restored.experience.recall("procedure alpha")

    def test_from_dict_none_safe(self):
        ws = BPEWorkspace.from_dict(None)
        assert ws.progress == []
        assert ws.render() == ""

    def test_from_dict_caps_progress(self):
        data = {"progress": [{"title": f"t{i}"} for i in range(20)]}
        assert len(BPEWorkspace.from_dict(data).progress) == MAX_SUBGOALS


# ---------------------------------------------------------------------------
# Registry scoping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistry:
    def test_same_scope_returns_same_instance(self):
        a = get_workspace("w", "agent", "s1")
        b = get_workspace("w", "agent", "s1")
        assert a is b

    def test_different_scope_different_instance(self):
        a = get_workspace("w", "agent", "s1")
        b = get_workspace("w", "agent", "s2")
        assert a is not b

    def test_key_normalization(self):
        assert workspace_key(None, None, None) == ("default", "agent", "")


# ---------------------------------------------------------------------------
# Telemetry spans
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTelemetry:
    def test_apply_records_span(self):
        from core.observability.tracing import clear_spans, get_recent_spans

        clear_spans()
        ws = BPEWorkspace()
        apply(ws, "note", "span check")
        spans = get_recent_spans(name_prefix="bpe.")
        assert spans, "expected at least one bpe span"
        span = spans[0]
        assert span["name"] == "bpe.note"
        assert span["attributes"]["success"] is True
        assert span["attributes"]["agent_id"] == "agent"

    def test_failed_action_records_error_span(self):
        from core.observability.tracing import clear_spans, get_recent_spans

        clear_spans()
        apply(BPEWorkspace(), "note", "")
        spans = get_recent_spans(name_prefix="bpe.")
        assert spans[0]["attributes"]["success"] is False


# ---------------------------------------------------------------------------
# Action registration + flag gating (Phase 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestActionRegistration:
    def test_four_meta_actions_registered(self):
        import core.bpe.actions  # noqa: F401 — registration side effect
        from core.action_registry import action_registry

        for name in ("workspace.track", "workspace.commit",
                     "workspace.recall", "workspace.note"):
            assert action_registry.get_action(name) is not None

    @pytest.mark.asyncio
    async def test_commit_action_end_to_end(self):
        import core.bpe.actions  # noqa: F401
        from core.action_registry import action_registry

        reset_registry()
        result = await action_registry.execute_action(
            "workspace.commit",
            {"title": "e2e subgoal"},
            {"workspace_id": "w", "agent_id": "a", "session_id": "s"},
        )
        assert result["success"] is True
        ws = get_workspace("w", "a", "s")
        assert ws.progress[0].title == "e2e subgoal"

    def test_flag_default_on(self, monkeypatch):
        from core.bpe.actions import bpe_enabled

        # The BPE workspace is a default platform feature (2026-08-29): with
        # no env var set, the workspace is ON. false opts out.
        monkeypatch.delenv("ATOM_BPE_WORKSPACE_ENABLED", raising=False)
        assert bpe_enabled() is True
        monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "false")
        assert bpe_enabled() is False

    def test_flag_gating_on(self, monkeypatch):
        from core.bpe.actions import bpe_enabled

        monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
        assert bpe_enabled() is True
