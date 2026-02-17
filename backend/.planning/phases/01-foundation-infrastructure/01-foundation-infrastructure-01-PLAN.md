# Plan 1-1: Baseline Coverage Measurement

**Phase:** 1 - Foundation & Infrastructure
**Wave:** 1
**Autonomous:** yes
**Depends on:** None

## Objective

Generate comprehensive coverage report to establish baseline metrics for AI components, identify gaps by module, and flag critical paths with insufficient coverage.

## Requirements

- AR-01: Baseline Coverage Measurement - Run coverage report to establish baseline, identify gaps in AI components

## Files Modified

- `coverage_reports/BASELINE_COVERAGE.md` - Baseline coverage documentation
- `coverage_reports/metrics/coverage.json` - Machine-readable coverage metrics
- `coverage_reports/trending.json` - Historical trending data
- `coverage_reports/CRITICAL_PATHS_UNCOVERED.md` - Critical paths lacking coverage

## Tasks

### Task 1: Generate Coverage Report

**Files:** `coverage_reports/htmlcov/index.html`, `coverage_reports/coverage.json`

**Action:**
```bash
# Run pytest with coverage for all AI-related components
pytest \
  --cov=core \
  --cov=api \
  --cov=tools \
  --cov-report=html:coverage_reports/htmlcov \
  --cov-report=json:coverage_reports/metrics/coverage.json \
  --cov-report=term-missing \
  -v \
  tests/

# Generate trending data for historical tracking
echo "{\"date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"coverage\": $(python -c "import json; data=json.load(open('coverage_reports/metrics/coverage.json')); print(data['totals']['percent_covered'])")}" > coverage_reports/trending.json
```

**Verify:**
- [ ] Coverage report generated successfully (exit code 0)
- [ ] HTML report accessible at `coverage_reports/htmlcov/index.html`
- [ ] JSON report contains metrics for core, api, and tools
- [ ] Terminal output shows per-module coverage percentages
- [ ] No collection errors or import errors

**Done:**
- Coverage report artifacts exist in `coverage_reports/` directory

---

### Task 2: Analyze Coverage Gaps by AI Component

**Files:** `coverage_reports/BASELINE_COVERAGE.md`

**Action:**
```python
# Analyze coverage.json and generate module breakdown
import json
from pathlib import Path

# Load coverage data
with open('coverage_reports/metrics/coverage.json') as f:
    coverage = json.load(f)

# Define AI components to analyze
ai_components = {
    'Governance': ['core/agent_governance_service.py', 'core/agent_context_resolver.py', 'core/governance_cache.py'],
    'LLM': ['core/llm/byok_handler.py', 'core/llm_usage_tracker.py'],
    'Episodic Memory': ['core/episode_segmentation_service.py', 'core/episode_retrieval_service.py', 'core/episode_lifecycle_service.py'],
    'Agent System': ['core/agent_execution_service.py', 'core/agent_graduation_service.py'],
    'Social Layer': ['core/agent_social_layer.py', 'core/agent_communication.py'],
    'Community Skills': ['core/skill_parser.py', 'core/skill_adapter.py', 'core/skill_sandbox.py'],
    'Local Agent': ['core/local_agent_service.py', 'core/command_whitelist.py'],
    'IM Adapters': ['core/im_governance_service.py']
}

# Generate markdown report
markdown = []
markdown.append("# Baseline Coverage Report\n")
markdown.append("**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)\n")
markdown.append("**Total Coverage:** {:.1f}%\n".format(coverage['totals']['percent_covered']))

for component, files in ai_components.items():
    markdown.append(f"## {component}\n")
    for file in files:
        file_path = Path(file)
        if file_path.as_posix() in coverage['files']:
            file_data = coverage['files'][file_path.as_posix()]
            summary = file_data['summary']
            markdown.append(f"### {file_path.name}\n")
            markdown.append(f"- **Coverage:** {summary['percent_covered']:.1f}%\n")
            markdown.append(f"- **Lines Covered:** {summary['covered_lines']}/{summary['num_statements']}\n")
            markdown.append(f"- **Lines Missing:** {summary['missing_lines']}\n")
        else:
            markdown.append(f"### {file_path.name}\n")
            markdown.append(f"- **Status:** File not found in coverage report\n")

# Write report
Path('coverage_reports/BASELINE_COVERAGE.md').write_text('\n'.join(markdown))
```

**Verify:**
- [ ] BASELINE_COVERAGE.md created successfully
- [ ] All 8 AI components analyzed (Governance, LLM, Episodic Memory, Agent System, Social Layer, Community Skills, Local Agent, IM Adapters)
- [ ] Each component shows coverage percentage and missing line count
- [ ] Files not in coverage report are noted
- [ ] Markdown is well-formatted with proper headers and tables

**Done:**
- BASELINE_COVERAGE.md exists with component-by-component breakdown
- Baseline documented for future comparison

---

### Task 3: Flag Critical Paths with <50% Coverage

**Files:** `coverage_reports/CRITICAL_PATHS_UNCOVERED.md`

**Action:**
```python
# Identify critical paths with insufficient coverage
import json
from pathlib import Path

# Load coverage data
with open('coverage_reports/metrics/coverage.json') as f:
    coverage = json.load(f)

# Define critical paths (from ROADMAP.md success criteria)
critical_paths = {
    'Agent Execution Flow': [
        'core/agent_governance_service.py',
        'core/agent_execution_service.py'
    ],
    'LLM Integration Flow': [
        'core/llm/byok_handler.py',
        'core/atom_agent_endpoints.py'
    ],
    'Governance Checks': [
        'core/governance_cache.py',
        'core/agent_context_resolver.py'
    ],
    'Memory Operations': [
        'core/episode_segmentation_service.py',
        'core/episode_retrieval_service.py'
    ],
    'Local Agent Security': [
        'core/local_agent_service.py',
        'core/command_whitelist.py',
        'core/directory_permission.py'
    ],
    'Community Skills Security': [
        'core/skill_sandbox.py',
        'core/skill_security_scanner.py'
    ]
}

# Generate critical paths report
markdown = []
markdown.append("# Critical Paths Coverage Analysis\n")
markdown.append("**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)\n")
markdown.append("**Threshold:** <50% coverage flagged for priority attention\n\n")

total_files = 0
low_coverage_files = 0

for path, files in critical_paths.items():
    markdown.append(f"## {path}\n")
    for file in files:
        total_files += 1
        file_path = Path(file)
        if file_path.as_posix() in coverage['files']:
            file_data = coverage['files'][file_path.as_posix()]
            summary = file_data['summary']
            coverage_pct = summary['percent_covered']

            if coverage_pct < 50.0:
                low_coverage_files += 1
                markdown.append(f"### ⚠️ {file_path.name} - {coverage_pct:.1f}%\n")
                markdown.append(f"**Status:** Below 50% threshold - PRIORITY for coverage expansion\n")
                markdown.append(f"- **Missing Lines:** {summary['missing_lines']}\n")
                markdown.append(f"- **Total Lines:** {summary['num_statements']}\n")

                # Show uncovered lines with security-sensitive code
                missing_lines = file_data.get('missing_lines', [])
                if missing_lines:
                    markdown.append(f"- **Sample Uncovered Lines:**\n")
                    for line_num in sorted(missing_lines)[:10]:  # Show first 10
                        markdown.append(f"  - Line {line_num}\n")
                    if len(missing_lines) > 10:
                        markdown.append(f"  - ... and {len(missing_lines) - 10} more\n")
            else:
                markdown.append(f"### ✅ {file_path.name} - {coverage_pct:.1f}%\n")
                markdown.append(f"**Status:** Above 50% threshold\n")
        else:
            markdown.append(f"### ❓ {file_path.name}\n")
            markdown.append(f"**Status:** File not in coverage report - may need investigation\n")

# Summary section
markdown.append(f"\n## Summary\n")
markdown.append(f"- **Total Critical Files:** {total_files}\n")
markdown.append(f"- **Files Below 50% Coverage:** {low_coverage_files}\n")
markdown.append(f"- **Coverage Gap:** {total_files - low_coverage_files} files meet minimum threshold\n")

# Write report
Path('coverage_reports/CRITICAL_PATHS_UNCOVERED.md').write_text('\n'.join(markdown))
```

**Verify:**
- [ ] CRITICAL_PATHS_UNCOVERED.md created successfully
- [ ] All 6 critical paths analyzed (Agent Execution, LLM Integration, Governance Checks, Memory Operations, Local Agent Security, Community Skills Security)
- [ ] Files with <50% coverage flagged with ⚠️ warning
- [ ] Sample uncovered lines shown (first 10)
- [ ] Summary section shows total files and count below threshold
- [ ] Security-sensitive code areas prioritized

**Done:**
- CRITICAL_PATHS_UNCOVERED.md identifies priority areas for coverage expansion
- Clear baseline for measuring progress in Phase 11

---

## Success Criteria

### Must Haves

1. **Coverage Report Generated**
   - [ ] pytest-cov executed successfully with HTML, JSON, and terminal output
   - [ ] Coverage reports saved to `coverage_reports/` directory
   - [ ] No errors during coverage generation

2. **Baseline Documented**
   - [ ] BASELINE_COVERAGE.md created with module-by-module breakdown
   - [ ] Overall coverage percentage documented (current: ~15.2%)
   - [ ] All 8 AI components analyzed with individual metrics

3. **Gaps Identified**
   - [ ] Component gaps documented in BASELINE_COVERAGE.md
   - [ ] Files not in coverage report noted for investigation
   - [ ] Coverage percentage documented for each component

4. **Critical Paths Flagged**
   - [ ] CRITICAL_PATHS_UNCOVERED.md created
   - [ ] All 6 critical paths analyzed
   - [ ] Files with <50% coverage flagged with ⚠️ warning
   - [ ] Sample uncovered lines shown for priority areas
   - [ ] Security-sensitive areas (Local Agent, Community Skills) highlighted

5. **Historical Data Established**
   - [ ] trending.json created with date and overall coverage
   - [ ] Baseline established for measuring progress in Phase 11

### Success Definition

Plan is **SUCCESSFUL** when:
- All 3 tasks completed successfully
- Coverage reports generated (HTML, JSON, terminal, markdown)
- Baseline documented for all 8 AI components
- Critical paths with <50% coverage identified and prioritized
- Historical trending data established for future comparison

---

## Open Questions

1. **Coverage Baseline Unknown**: Current coverage estimated at 15.2%, but actual baseline needs to be measured with this plan.
2. **AI Component Scope**: Are there additional AI components beyond the 8 identified that should be analyzed?
3. **50% Threshold**: Is 50% the right threshold for critical paths, or should it be higher (e.g., 60%)?

---

*Plan created: February 17, 2026*
*Estimated effort: 0.5 day*
*Dependencies: None*
