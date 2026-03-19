"""Phase 206 final coverage aggregation tests."""
import json
import pytest
from pathlib import Path


def test_phase_206_80_percent_target_achieved():
    """Verify Phase 206 achieved 80% overall coverage."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    overall = coverage['totals']
    assert overall['percent_covered'] >= 80.0, f"Coverage target not met: {overall['percent_covered']:.2f}%"

    # Verify expansion strategy worked (more files under test)
    assert len(coverage['files']) >= 10, f"Expected at least 10 files under test, got {len(coverage['files'])}"


def test_coverage_expansion_validated():
    """Verify coverage expansion strategy (new files added)."""
    with open('coverage_phase_206_baseline.json', 'r') as f:
        baseline = json.load(f)

    with open('coverage.json', 'r') as f:
        final = json.load(f)

    # Verify more files in final coverage
    baseline_files = set(baseline.get('existing_files', []))
    final_files = set(final['files'].keys())

    new_files = final_files - baseline_files

    assert len(new_files) >= 8, f"Expected at least 8 new files, got {len(new_files)}"

    # Verify expected files are present
    expected_files = [
        "core/agent_governance_service.py",
        "core/agent_governance_cache.py",
        "core/agent_context_resolver.py",
        "core/llm/byok_handler.py",
        "core/workflow_engine.py",
        "core/episode_segmentation_service.py",
        "core/episode_retrieval_service.py",
        "core/agent_graduation_service.py",
        "core/workflow_template_system.py",
        "core/llm/cognitive_tier_system.py"
    ]

    for expected in expected_files:
        assert any(expected in f for f in final_files), f"Expected file {expected} not in coverage"


def test_coverage_improvement_calculated():
    """Verify coverage improvement from baseline."""
    with open('coverage_phase_206_baseline.json', 'r') as f:
        baseline = json.load(f)

    with open('coverage.json', 'r') as f:
        final = json.load(f)

    baseline_pct = baseline['current_coverage']['overall_percent']
    final_pct = final['totals']['percent_covered']
    improvement = final_pct - baseline_pct

    assert improvement >= 5.0, f"Coverage improvement too small: {improvement:.2f}pp"
    assert improvement <= 6.0, f"Coverage improvement too large (unexpected): {improvement:.2f}pp"

    # Verify target gap closed
    target_gap = baseline['target']['gap_percentage_points']
    assert final_pct >= 80.0, "80% target not achieved"


def test_file_level_coverage_quality():
    """Verify file-level coverage quality (75%+ per file)."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    low_coverage_files = []
    for filename, file_data in coverage['files'].items():
        pct = file_data['summary']['percent_covered']
        if pct < 75.0:
            low_coverage_files.append((filename, pct))

    # At most 1 file can be below 75% (external dependencies)
    assert len(low_coverage_files) <= 1, f"Too many files below 75%: {low_coverage_files}"


def test_collection_stability_maintained():
    """Verify zero collection errors throughout Phase 206."""
    import subprocess

    result = subprocess.run(
        ['python3', '-m', 'pytest', '--collect-only', '-q'],
        capture_output=True,
        text=True,
        cwd='/Users/rushiparikh/projects/atom/backend'
    )

    # Check for collection errors
    assert 'ERROR collecting' not in result.stderr, f"Collection errors detected: {result.stderr}"
    assert result.returncode == 0, f"Collection failed: {result.stderr}"


def test_wave_contributions_documented():
    """Verify all wave contributions are documented."""
    with open('phase_206_final_coverage.json', 'r') as f:
        final = json.load(f)

    # Verify wave breakdown
    assert 'waves' in final
    assert len(final['waves']) == 6

    # Verify each wave has required fields
    for wave in final['waves']:
        assert 'wave_number' in wave
        assert 'files_added' in wave
        assert 'tests_created' in wave
        assert 'coverage_gain' in wave


def test_test_count_validated():
    """Verify expected test count created."""
    # Count test files created in Phase 206
    test_files = [
        "tests/core/governance/test_agent_governance_service_coverage.py",
        "tests/core/governance/test_agent_governance_cache_coverage.py",
        "tests/core/governance/test_agent_context_resolver_coverage.py",
        "tests/core/llm/test_byok_handler_coverage.py",
        "tests/core/workflow/test_workflow_engine_coverage.py",
        "tests/core/memory/test_episode_segmentation_service_coverage.py",
        "tests/core/memory/test_episode_retrieval_service_coverage.py",
        "tests/core/memory/test_agent_graduation_service_coverage.py",
        "tests/core/workflow/test_workflow_template_system_coverage.py",
        "tests/core/llm/test_cognitive_tier_system_coverage.py"
    ]

    created_count = 0
    for test_file in test_files:
        if Path(test_file).exists():
            created_count += 1

    assert created_count >= 10, f"Expected at least 10 test files, got {created_count}"


@pytest.mark.skip("Run manually for detailed report")
def test_generate_detailed_coverage_report():
    """Generate detailed coverage report by file."""
    with open('coverage.json', 'r') as f:
        coverage = json.load(f)

    report = []
    report.append("=== Phase 206 Detailed Coverage Report ===\n")

    for filename, file_data in sorted(coverage['files'].items()):
        summary = file_data['summary']
        report.append(f"{filename}:")
        report.append(f"  Coverage: {summary['percent_covered']:.1f}%")
        report.append(f"  Lines: {summary['covered_lines']}/{summary['num_statements']}")
        report.append(f"  Missing: {summary['missing_lines']}")
        report.append("")

    report.append(f"=== Overall ===")
    report.append(f"Coverage: {coverage['totals']['percent_covered']:.2f}%")
    report.append(f"Files: {len(coverage['files'])}")

    print("\n".join(report))
