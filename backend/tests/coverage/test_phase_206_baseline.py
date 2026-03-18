"""Phase 206 baseline coverage verification tests."""
import json
import pytest


def test_baseline_coverage_from_phase_205():
    """Verify baseline coverage matches Phase 205 final of 74.69%."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    overall = coverage['totals']
    assert overall['percent_covered'] >= 74.0, f"Coverage dropped below 74%: {overall['percent_covered']:.2f}%"
    assert overall['num_statements'] > 1000, "Too few statements measured"

    # Verify the two key files from previous phases are present
    assert 'core/workflow_analytics_engine.py' in coverage['files']
    assert 'core/workflow_debugger.py' in coverage['files']


def test_collection_stability():
    """Verify zero collection errors maintained from Phase 205."""
    import subprocess
    result = subprocess.run(
        ['python3', '-m', 'pytest', '--collect-only', '-q'],
        capture_output=True,
        text=True,
        cwd='/Users/rushiparikh/projects/atom/backend'
    )

    # Check for collection errors
    assert 'ERROR collecting' not in result.stderr, "Collection errors detected"
    assert result.returncode == 0, f"Collection failed: {result.stderr}"
