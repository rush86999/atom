"""
Canvas-aware recall path — canonical fusion + canvas boosts + tool mode.
"""

import os
os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_recall_episodes_fuses_canonical_table():
    """Canonical episodes (segmentation-written) must be recallable even when
    the agent_episodes mirror is empty, and canvas_id in metadata boosts."""
    from core.agent_world_model import WorldModelService

    wm = WorldModelService.__new__(WorldModelService)
    wm.db = MagicMock()
    wm.db.search = lambda table_name, query, limit: {
        "agent_episodes": [],
        "episodes": [
            {
                "text": "Episode: prepare quote\nOutcome: success",
                "score": 0.8,
                "metadata": {
                    "episode_id": "e-canonical-1", "agent_id": "atom_main",
                    "type": "episode", "outcome": "success",
                    "canvas_id": "canvas-42", "agent_role": None,
                },
                "id": "e-canonical-1",
            },
            {
                # No type marker → filtered
                "text": "junk", "score": 0.9, "metadata": {"type": "other"}, "id": "x",
            },
        ],
    }[table_name]

    rows = await wm.recall_episodes(
        task_description="prepare a quote",
        agent_role="sales",
        canvas_id="canvas-42",
        limit=5,
    )
    assert len(rows) == 1
    assert rows[0]["episode_id"] == "e-canonical-1"
    assert rows[0]["canvas_boost"] == 0.3  # same-canvas boost applied to canonical row


@pytest.mark.asyncio
async def test_recall_episodes_dedupes_mirror_and_canonical():
    from core.agent_world_model import WorldModelService

    wm = WorldModelService.__new__(WorldModelService)
    wm.db = MagicMock()
    shared_meta = {"episode_id": "e-dup", "agent_role": "sales", "type": "episode", "agent_id": "a1"}
    wm.db.search = lambda table_name, query, limit: [
        {"text": "Episode: t", "score": 0.7, "metadata": dict(shared_meta), "id": "e-dup"}
    ]
    rows = await wm.recall_episodes(task_description="t", agent_role="sales", limit=5)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_recall_tool_canvas_mode_routes_through_world_model():
    from core.action_registry import action_registry

    wm = MagicMock()
    wm.recall_episodes = AsyncMock(return_value=[
        {"episode_id": "e1", "task_description": "quote", "outcome": "success",
         "canvas_id": "c1", "final_score": 1.1}
    ])
    with patch("core.agent_world_model.WorldModelService", return_value=wm):
        r = await action_registry.execute_action(
            "recall_episodes",
            {"task": "prepare a quote", "canvas_id": "c1"},
            context={"agent_id": "atom_main"},
        )
    assert r.get("success") is True
    assert r.get("mode") == "canvas_aware"
    assert r["episodes"][0]["canvas_id"] == "c1"
    # canvas_id forwarded to the world model
    assert wm.recall_episodes.call_args.kwargs.get("canvas_id") == "c1"


def test_segmentation_metadata_stamps_canvas_and_feedback():
    import inspect
    from core.episode_segmentation_service import EpisodeSegmentationService

    src = inspect.getsource(EpisodeSegmentationService._archive_to_lancedb)
    assert '"canvas_id"' in src
    assert '"feedback_score"' in src
