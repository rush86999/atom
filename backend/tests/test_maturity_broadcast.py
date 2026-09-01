"""
Tests for the real-time maturity broadcast circuit.

The user-facing contract: when an agent learns (outcome drip, feedback
adjudication, correction penalty, training completion, graduation), the
workspace UI sees a `maturity_update` WebSocket frame immediately — not on
the next poll/reload. These tests lock the helper (channel selection,
payload shape, never-raise) and the governance scoring choke point wiring.
"""

import os
os.environ["TESTING"] = "1"

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.maturity_broadcast import (
    broadcast_maturity_update,
    schedule_maturity_broadcast,
    workspace_channels,
)
from core.models import AgentRegistry
from core.agent_governance_service import AgentGovernanceService


class TestWorkspaceChannels:
    def test_default_workspace_gets_only_default_channel(self):
        assert workspace_channels("default") == ["workspace:default"]

    def test_tenant_scoped_workspace_gets_both_channels(self):
        assert workspace_channels("acme") == [
            "workspace:default",
            "workspace:acme",
        ]

    def test_none_falls_back_to_default(self):
        assert workspace_channels(None) == ["workspace:default"]


class TestBroadcastMaturityUpdate:
    def test_pushes_maturity_update_frame_to_each_channel(self):
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            await broadcast_maturity_update(
                workspace_id="acme",
                agent_id="agent-1",
                previous_confidence=0.52,
                confidence=0.53,
                previous_tier="intern",
                tier="intern",
                source="outcome",
            )

        with patch("core.websockets.get_connection_manager", return_value=manager):
            asyncio.run(main())

        assert manager.broadcast_event.await_count == 2
        channels = [call.args[0] for call in manager.broadcast_event.await_args_list]
        assert channels == ["workspace:default", "workspace:acme"]
        event_type = manager.broadcast_event.await_args_list[0].args[1]
        assert event_type == "maturity_update"
        payload = manager.broadcast_event.await_args_list[0].args[2]
        assert payload["agent_id"] == "agent-1"
        assert payload["confidence"] == 0.53
        assert payload["previous_confidence"] == 0.52
        assert payload["transition"] is False
        assert payload["source"] == "outcome"

    def test_transition_flag_true_when_tier_changes(self):
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            await broadcast_maturity_update(
                workspace_id="default",
                agent_id="agent-1",
                previous_tier="student",
                tier="intern",
            )

        with patch("core.websockets.get_connection_manager", return_value=manager):
            asyncio.run(main())

        payload = manager.broadcast_event.await_args_list[0].args[2]
        assert payload["transition"] is True

    def test_broken_websocket_layer_never_raises(self):
        async def main():
            with patch(
                "core.websockets.get_connection_manager",
                side_effect=RuntimeError("no ws layer"),
            ):
                await broadcast_maturity_update(
                    workspace_id="default", agent_id="agent-1", confidence=0.5
                )

        asyncio.run(main())  # must not raise


class TestScheduleMaturityBroadcast:
    def test_schedules_on_running_loop_and_delivers(self):
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            schedule_maturity_broadcast(
                workspace_id="default",
                agent_id="agent-1",
                previous_confidence=0.4,
                confidence=0.41,
                previous_tier="student",
                tier="student",
                source="training",
            )
            # yield so the scheduled task actually runs
            for _ in range(3):
                await asyncio.sleep(0)

        with patch("core.websockets.get_connection_manager", return_value=manager):
            asyncio.run(main())

        assert manager.broadcast_event.await_count == 1
        payload = manager.broadcast_event.await_args.args[2]
        assert payload["source"] == "training"

    def test_skips_silently_without_a_running_loop(self):
        # No asyncio.run wrapper — sync context. Must not raise and must
        # not attempt a broadcast.
        schedule_maturity_broadcast(
            workspace_id="default", agent_id="agent-1", confidence=0.5
        )


class TestGovernanceScoreBroadcast:
    """The scoring choke point pushes a frame on every confidence delta."""

    def _service_with_agent(self, agent):
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        service = AgentGovernanceService(db=mock_db, workspace_id="acme")
        return service, mock_db

    def test_score_drip_broadcasts_maturity_update(self):
        agent = AgentRegistry(
            id="agent-1",
            name="A",
            category="c",
            module_path="m",
            class_name="X",
            workspace_id="acme",
            status="intern",
            confidence_score=0.52,
        )
        service, mock_db = self._service_with_agent(agent)
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            with patch(
                "core.agent_governance_service.get_governance_cache"
            ) as cache, patch(
                "core.websockets.get_connection_manager", return_value=manager
            ):
                service._update_confidence_score(
                    "agent-1", positive=True, impact_level="low"
                )
                for _ in range(3):
                    await asyncio.sleep(0)

            cache.return_value.invalidate.assert_called_once_with("agent-1")

        with patch("core.agent_governance_service.ContinuousLearningService"):
            asyncio.run(main())

        mock_db.commit.assert_called_once()
        assert agent.confidence_score == 0.53
        payload = manager.broadcast_event.await_args.args[2]
        assert payload["agent_id"] == "agent-1"
        assert payload["confidence"] == 0.53
        assert payload["previous_confidence"] == 0.52
        assert payload["tier"] == "intern"
        assert payload["previous_tier"] == "intern"
        assert payload["transition"] is False
        assert payload["source"] == "outcome"

    def test_feedback_source_is_labeled(self):
        agent = AgentRegistry(
            id="agent-2",
            name="B",
            category="c",
            module_path="m",
            class_name="X",
            workspace_id="default",
            status="student",
            confidence_score=0.40,
        )
        service, _ = self._service_with_agent(agent)
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            with patch(
                "core.agent_governance_service.get_governance_cache"
            ), patch(
                "core.websockets.get_connection_manager", return_value=manager
            ):
                service._update_confidence_score(
                    "agent-2", positive=True, impact_level="high", source="feedback"
                )
                for _ in range(3):
                    await asyncio.sleep(0)

        with patch("core.agent_governance_service.ContinuousLearningService"):
            asyncio.run(main())

        payload = manager.broadcast_event.await_args.args[2]
        assert payload["source"] == "feedback"
        assert payload["previous_tier"] == "student"

    def test_no_delta_no_broadcast(self):
        agent = AgentRegistry(
            id="agent-3",
            name="C",
            category="c",
            module_path="m",
            class_name="X",
            workspace_id="default",
            status="autonomous",
            confidence_score=1.0,
        )
        service, _ = self._service_with_agent(agent)
        manager = Mock()
        manager.broadcast_event = AsyncMock()

        async def main():
            with patch(
                "core.agent_governance_service.get_governance_cache"
            ), patch(
                "core.websockets.get_connection_manager", return_value=manager
            ):
                service._update_confidence_score(
                    "agent-3", positive=True, impact_level="low"
                )
                for _ in range(3):
                    await asyncio.sleep(0)

        with patch("core.agent_governance_service.ContinuousLearningService"):
            asyncio.run(main())

        # Score already capped at 1.0 → no change → nothing pushed
        manager.broadcast_event.assert_not_awaited()
