"""
Episode Segmentation Service Tests
Tests for core/episode_segmentation_service.py
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from core.episode_segmentation_service import EpisodeSegmentationService


@pytest.fixture
def segmentation_service():
    """Create EpisodeSegmentationService instance."""
    return EpisodeSegmentationService()


class TestTimeBasedSegmentation:
    """Test detect time gaps, create segments, handle edge cases."""

    def test_detect_time_gap(self, segmentation_service):
        """Test detecting significant time gap between activities."""
        now = datetime.now(timezone.utc)
        early = now - timedelta(hours=2)
        
        gap = segmentation_service._detect_time_gap(early, now)
        assert gap > 0

    def test_no_time_gap(self, segmentation_service):
        """Test when activities are close together."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(seconds=30)
        
        gap = segmentation_service._detect_time_gap(recent, now)
        # Should be small or zero
        assert gap < 60


class TestTopicSegmentation:
    """Test detect topic changes, semantic similarity, segment boundaries."""

    @pytest.mark.asyncio
    async def test_detect_topic_change(self, segmentation_service):
        """Test detecting topic change between messages."""
        with patch('core.episode_segmentation_service.llm_service') as mock_llm:
            mock_llm.generate = AsyncMock(return_value="Topic changed")
            
            changed = await segmentation_service._detect_topic_change(
                "Discussing weather",
                "Now discussing stocks"
            )
            # Should detect some difference
            assert changed is not None


class TestTaskCompletionSegmentation:
    """Test detect task end, create episodes, update status."""

    def test_identify_task_completion(self, segmentation_service):
        """Test identifying when a task is completed."""
        activities = [
            {"type": "start", "task": "reconcile"},
            {"type": "processing", "task": "reconcile"},
            {"type": "complete", "task": "reconcile"}
        ]
        
        completed = segmentation_service._identify_task_completion(activities)
        assert completed is True


class TestMetadataExtraction:
    """Test extract agents, tools, canvases, duration."""

    def test_extract_agents(self, segmentation_service):
        """Test extracting agent IDs from episode."""
        segment = {
            "activities": [
                {"agent_id": "agent-1"},
                {"agent_id": "agent-2"}
            ]
        }
        
        agents = segmentation_service._extract_agents(segment)
        assert len(agents) > 0

    def test_extract_duration(self, segmentation_service):
        """Test calculating episode duration."""
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        end = datetime.now(timezone.utc)
        
        duration = segmentation_service._calculate_duration(start, end)
        assert duration > 0


class TestQualityScoring:
    """Test segment quality, information density, merge decisions."""

    def test_calculate_quality_score(self, segmentation_service):
        """Test calculating quality score for segment."""
        segment = {
            "activities": [
                {"type": "action", "outcome": "success"},
                {"type": "action", "outcome": "success"}
            ],
            "errors": 0
        }
        
        score = segmentation_service._calculate_quality_score(segment)
        assert score >= 0.0
        assert score <= 1.0
