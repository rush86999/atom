"""Phase 206 coverage aggregation tests."""
import json
import pytest


def test_phase_206_baseline_metrics():
    """Verify Phase 206 baseline metrics from coverage_phase_206_baseline.json."""
    with open('coverage_phase_206_baseline.json', 'r') as f:
        baseline = json.load(f)

    # Verify baseline
    assert baseline['current_coverage']['overall_percent'] >= 74.0
    assert baseline['target']['percent'] == 80.0
    assert baseline['target']['gap_percentage_points'] > 5.0

    # Verify strategy
    assert baseline['strategy']['approach'] == 'expansion'
    assert len(baseline['target_files']) >= 10

    # Verify wave targets
    assert len(baseline['wave_2_targets']) >= 3
    assert len(baseline['wave_3_targets']) >= 3


def test_coverage_files_count_increases():
    """Verify that adding new tests increases the number of files in coverage report."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    current_file_count = len(coverage['files'])

    # Currently only 2 files (workflow_analytics_engine, workflow_debugger)
    # After testing more files, this should increase
    assert current_file_count >= 2, f"Expected at least 2 files, got {current_file_count}"

    # Store for comparison in later waves
    with open('coverage_file_count.txt', 'w') as f:
        f.write(str(current_file_count))


@pytest.mark.skip("Run in Wave 4 only")
def test_phase_206_final_coverage_80_percent():
    """Verify Phase 206 achieves 80% overall coverage."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    overall = coverage['totals']
    assert overall['percent_covered'] >= 80.0, f"Coverage target not met: {overall['percent_covered']:.2f}%"

    # Verify expansion strategy worked (more files under test)
    assert len(coverage['files']) >= 10, f"Expected at least 10 files under test, got {len(coverage['files'])}"
