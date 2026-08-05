"""
TDD tests for WorkflowEngine._check_dependencies.

Covers dependency satisfaction and the missing-'steps' robustness case (a
KeyError would crash step gating during execution).
"""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import WorkflowEngine


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


def test_all_dependencies_met(engine):
    state = {"steps": {"a": {"status": "COMPLETED"}, "b": {"status": "COMPLETED"}}}
    step = {"id": "c", "depends_on": ["a", "b"]}
    assert engine._check_dependencies(step, state) is True


def test_pending_dependency_blocks(engine):
    state = {"steps": {"a": {"status": "RUNNING"}}}
    step = {"id": "c", "depends_on": ["a"]}
    assert engine._check_dependencies(step, state) is False


def test_no_dependencies(engine):
    step = {"id": "c"}
    assert engine._check_dependencies(step, {}) is True


def test_missing_steps_key_does_not_crash(engine):
    """A state without 'steps' must not raise KeyError during gating."""
    step = {"id": "c", "depends_on": ["a"]}
    assert engine._check_dependencies(step, {}) is False
