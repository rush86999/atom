"""
Test suite for WorkflowEngine DAG cycle detection bugs.

RED PHASE: These tests expose bugs in workflow cycle detection.

The bug: The topological sort (Kahn's algorithm) in _convert_nodes_to_steps
doesn't check for cycles. If the graph has a cycle, the algorithm will not
process all nodes, but the code doesn't detect or report this.
"""

import pytest
from core.workflow_engine import WorkflowEngine


class TestWorkflowEngineCycleDetectionBugs:
    """
    Test suite revealing cycle detection bugs in WorkflowEngine.

    The bug: Lines 90-131 implement Kahn's algorithm without cycle detection.
    After the sort, there's no check that all nodes were processed.
    """

    def test_self_referencing_step_cycle(self):
        """
        Test workflow with a step that references itself.

        EXPECTED FAILURE: A step that depends on itself creates a cycle.
        The current implementation doesn't detect this and will either
        hang or produce incorrect results.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "step1", "type": "action", "title": "Step 1", "config": {}}
            ],
            "connections": [
                {"source": "step1", "target": "step1"}  # Self-reference!
            ]
        }

        # This should raise an error due to cycle
        # But it doesn't - BUG!
        with pytest.raises(ValueError, match="cycle|circular|self"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_circular_dependency_two_steps(self):
        """
        Test workflow with circular dependency: A→B→A.

        EXPECTED FAILURE: Two steps that depend on each other create a cycle.
        The current implementation doesn't detect this.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "stepA", "type": "action", "title": "Step A", "config": {}},
                {"id": "stepB", "type": "action", "title": "Step B", "config": {}}
            ],
            "connections": [
                {"source": "stepA", "target": "stepB"},
                {"source": "stepB", "target": "stepA"}  # Cycle!
            ]
        }

        # This should raise an error due to cycle
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_complex_cycle_three_steps(self):
        """
        Test workflow with complex cycle: A→B→C→A.

        EXPECTED FAILURE: Three steps in a cycle should be detected.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "stepA", "type": "action", "title": "Step A", "config": {}},
                {"id": "stepB", "type": "action", "title": "Step B", "config": {}},
                {"id": "stepC", "type": "action", "title": "Step C", "config": {}}
            ],
            "connections": [
                {"source": "stepA", "target": "stepB"},
                {"source": "stepB", "target": "stepC"},
                {"source": "stepC", "target": "stepA"}  # Cycle back to A!
            ]
        }

        # This should raise an error due to cycle
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_partial_cycle_with_valid_nodes(self):
        """
        Test workflow with a cycle plus some valid nodes.

        EXPECTED FAILURE: A workflow with both cycles and valid DAG
        portions should still reject the entire workflow.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "step1", "type": "action", "title": "Step 1", "config": {}},
                {"id": "step2", "type": "action", "title": "Step 2", "config": {}},
                {"id": "step3", "type": "action", "title": "Step 3", "config": {}},
                {"id": "step4", "type": "action", "title": "Step 4", "config": {}}
            ],
            "connections": [
                {"source": "step1", "target": "step2"},
                {"source": "step2", "target": "step3"},
                {"source": "step3", "target": "step1"},  # Cycle: 1→2→3→1
                {"source": "step3", "target": "step4"}  # step4 depends on step3
            ]
        }

        # This should raise an error due to cycle
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_multiple_independent_cycles(self):
        """
        Test workflow with multiple independent cycles.

        EXPECTED FAILURE: Multiple cycles should all be detected.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "A", "type": "action", "title": "A", "config": {}},
                {"id": "B", "type": "action", "title": "B", "config": {}},
                {"id": "C", "type": "action", "title": "C", "config": {}},
                {"id": "D", "type": "action", "title": "D", "config": {}}
            ],
            "connections": [
                {"source": "A", "target": "B"},
                {"source": "B", "target": "A"},  # Cycle 1: A→B→A
                {"source": "C", "target": "D"},
                {"source": "D", "target": "C"}   # Cycle 2: C→D→C
            ]
        }

        # This should raise an error due to cycles
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_valid_dag_should_work(self):
        """
        Test that a valid DAG still works correctly.

        This should PASS - it's not a bug, just a baseline test.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "step1", "type": "action", "title": "Step 1", "config": {}},
                {"id": "step2", "type": "action", "title": "Step 2", "config": {}},
                {"id": "step3", "type": "action", "title": "Step 3", "config": {}}
            ],
            "connections": [
                {"source": "step1", "target": "step2"},
                {"source": "step1", "target": "step3"}  # step1 fans out to step2 and step3
            ]
        }

        # Valid DAG should work
        steps = engine._convert_nodes_to_steps(workflow)
        assert len(steps) == 3
        # step1 should be first (no dependencies)
        assert steps[0]["id"] == "step1"

    def test_cycle_results_in_incomplete_sort(self):
        """
        Test that cycles are now detected and raise an error.

        GREEN PHASE: After the fix, cycles should raise ValueError.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "step1", "type": "action", "title": "Step 1", "config": {}},
                {"id": "step2", "type": "action", "title": "Step 2", "config": {}},
                {"id": "step3", "type": "action", "title": "Step 3", "config": {}}
            ],
            "connections": [
                {"source": "step1", "target": "step2"},
                {"source": "step2", "target": "step3"},
                {"source": "step3", "target": "step1"}  # Cycle
            ]
        }

        # After the fix: This now raises ValueError
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)

    def test_isolated_cycle_components(self):
        """
        Test workflow with isolated components that form a cycle.

        EXPECTED FAILURE: Even isolated cycles should be detected.
        """
        engine = WorkflowEngine()

        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "valid1", "type": "action", "title": "Valid 1", "config": {}},
                {"id": "valid2", "type": "action", "title": "Valid 2", "config": {}},
                {"id": "cycleA", "type": "action", "title": "Cycle A", "config": {}},
                {"id": "cycleB", "type": "action", "title": "Cycle B", "config": {}}
            ],
            "connections": [
                {"source": "valid1", "target": "valid2"},  # Valid chain
                {"source": "cycleA", "target": "cycleB"},  # Cycle
                {"source": "cycleB", "target": "cycleA"}   # Cycle back
            ]
        }

        # Should reject the entire workflow
        with pytest.raises(ValueError, match="cycle|circular"):
            steps = engine._convert_nodes_to_steps(workflow)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
