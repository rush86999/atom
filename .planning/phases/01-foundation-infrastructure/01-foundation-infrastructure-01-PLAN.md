---
phase: 01-foundation-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/coverage_reports/BASELINE_COVERAGE.md
  - backend/tests/coverage_reports/metrics/coverage.json
  - backend/tests/coverage_reports/trending.json
autonomous: true

must_haves:
  truths:
    - Coverage report generated showing baseline metrics by module
    - Gaps identified in AI components (governance, LLM, memory, agents, social, skills, local agent, IM)
    - Critical paths with <50% coverage flagged
    - Uncovered lines in critical services catalogued
  artifacts:
    - path: backend/tests/coverage_reports/BASELINE_COVERAGE.md
      provides: Baseline coverage documentation with module breakdown
      min_lines: 100
    - path: backend/tests/coverage_reports/metrics/coverage.json
      provides: Machine-readable coverage data for trending
      contains: totals, files
    - path: backend/tests/coverage_reports/trending.json
      provides: Historical coverage tracking
      contains: baseline
  key_links:
    - from: pytest --cov command
      to: coverage.json output
      via: pytest-cov plugin
      pattern: pytest --cov=core --cov=api --cov=tools --cov-report=json
---

<objective>
Generate comprehensive baseline coverage report identifying gaps in AI-related components to establish 80% coverage roadmap.

Purpose: Establish measurable baseline for 80% test coverage initiative by generating coverage reports across all modules and identifying specific gaps in AI components (governance, LLM, memory, agents, social, skills, local agent, IM adapters).

Output: HTML coverage report, JSON metrics file, and BASELINE_COVERAGE.md documenting baseline metrics and prioritized gap list.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Codebase Context
@backend/pytest.ini (test configuration, markers, coverage settings)
@backend/tests/conftest.py (root fixtures, db_session, environment isolation)
@backend/tests/property_tests/conftest.py (Hypothesis settings, test agents)
@backend/tests/factories/ (factory_boy test data factories)
</context>

<tasks>

<task type="auto">
  <name>Generate Coverage Report with HTML, JSON, and Terminal Output</name>
  <files>backend/tests/coverage_reports/</files>
  <action>
Run comprehensive coverage report generation:

1. Ensure coverage directory exists:
   ```bash
   mkdir -p backend/tests/coverage_reports/metrics
   mkdir -p backend/tests/coverage_reports/html
   mkdir -p backend/tests/coverage_reports/baseline
   ```

2. Run pytest with coverage on all target modules:
   ```bash
   cd backend
   PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
     --cov=core \
     --cov=api \
     --cov=tools \
     --cov-report=html \
     --cov-report=json:tests/coverage_reports/metrics/coverage.json \
     --cov-report=term-missing \
     --cov-report=xml:tests/coverage_reports/metrics/coverage.xml \
     -v \
     tests/ 2>&1 | tee tests/coverage_reports/baseline/coverage_run.log
   ```

3. Extract baseline metrics from coverage.json:
   ```bash
   python -c "
import json
with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)
totals = data.get('totals', {})
print(f'Overall Coverage: {totals.get(\"percent_covered\", 0):.2f}%')
print(f'Lines Covered: {totals.get(\"covered_lines\", 0)}')
print(f'Lines Missing: {totals.get(\"missing_lines\", 0)}')
print(f'Total Lines: {totals.get(\"num_statements\", 0)}')
   "
   ```

4. Generate module-by-module breakdown:
   ```bash
   python -c "
import json
with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)
print('Module Coverage Breakdown:')
for file, metrics in data.get('files', []).items():
    pct = metrics.get('summary', {}).get('percent_covered', 0)
    covered = metrics.get('summary', {}).get('covered_lines', 0)
    total = metrics.get('summary', {}).get('num_statements', 0)
    if total > 0:
        print(f'{file}: {pct:.1f}% ({covered}/{total})')
   " | sort -t: -k2 -n
   ```

DO NOT modify any test code. DO NOT create new tests. This task is MEASUREMENT only.
  </action>
  <verify>
1. File exists: backend/tests/coverage_reports/metrics/coverage.json
2. File exists: backend/tests/coverage_reports/html/index.html
3. coverage.json contains valid JSON with 'totals' and 'files' keys
4. Coverage percentage is extracted and logged

Command:
```bash
cd backend && test -f tests/coverage_reports/metrics/coverage.json && \
python -c "import json; d=json.load(open('tests/coverage_reports/metrics/coverage.json')); print('Valid:', 'totals' in d)"
```
  </verify>
  <done>
Coverage report generated with:
- HTML report available at backend/tests/coverage_reports/html/index.html
- JSON metrics at backend/tests/coverage_reports/metrics/coverage.json
- Terminal output showing overall coverage percentage
- Module-by-module breakdown extracted
  </done>
</task>

<task type="auto">
  <name>Analyze Coverage Gaps and Create Baseline Documentation</name>
  <files>backend/tests/coverage_reports/BASELINE_COVERAGE.md</files>
  <action>
Create comprehensive baseline documentation analyzing coverage gaps:

1. Create trending.json with baseline entry:
   ```bash
   cd backend
   python -c "
import json
from datetime import datetime

# Read current coverage
with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

# Create trending entry
baseline = {
    'date': datetime.utcnow().isoformat(),
    'phase': '01-foundation-infrastructure',
    'plan': '01-baseline-coverage',
    'overall_coverage': data['totals']['percent_covered'],
    'covered_lines': data['totals']['covered_lines'],
    'missing_lines': data['totals']['missing_lines'],
    'total_lines': data['totals']['num_statements'],
    'modules': {}
}

# Add module breakdown
for file_path, metrics in data.get('files', {}).items():
    module_name = file_path.replace('backend/', '').split('/')[0]
    if module_name not in baseline['modules']:
        baseline['modules'][module_name] = {'covered': 0, 'total': 0}
    summary = metrics.get('summary', {})
    baseline['modules'][module_name]['covered'] += summary.get('covered_lines', 0)
    baseline['modules'][module_name]['total'] += summary.get('num_statements', 0)

# Save trending.json
with open('tests/coverage_reports/trending.json', 'w') as f:
    json.dump({'history': [baseline]}, f, indent=2)

print(f'Baseline: {baseline[\"overall_coverage\"]:.2f}% coverage')
"
   ```

2. Create BASELINE_COVERAGE.md with:
   - Executive summary (overall coverage percentage, current vs 80% goal)
   - Module breakdown table (core, api, tools coverage percentages)
   - Critical path gaps (<50% coverage files in governance, LLM, memory)
   - Zero-coverage file list (files with 0% coverage)
   - Priority ranking (largest impact files first)

3. Identify AI component gaps:
   ```bash
   cd backend
   python -c "
import json

# AI-related components to analyze
ai_modules = [
    'agent_governance_service',
    'agent_context_resolver',
    'governance_cache',
    'trigger_interceptor',
    'student_training_service',
    'supervision_service',
    'episode_segmentation_service',
    'episode_retrieval_service',
    'episode_lifecycle_service',
    'agent_graduation_service',
    'byok_handler',
    'streaming_handler',
    'atom_agent_endpoints',
    'canvas_tool',
    'browser_tool',
    'device_tool',
    'agent_social_layer',
    'host_shell_service',
    'local_agent_service'
]

with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

print('AI Component Coverage Analysis:')
print('-' * 60)
for file_path, metrics in data.get('files', {}).items():
    for module in ai_modules:
        if module in file_path:
            pct = metrics.get('summary', {}).get('percent_covered', 0)
            covered = metrics.get('summary', {}).get('covered_lines', 0)
            total = metrics.get('summary', {}).get('num_statements', 0)
            status = 'CRITICAL' if pct < 20 else 'LOW' if pct < 50 else 'MEDIUM' if pct < 70 else 'GOOD'
            print(f'{module}: {pct:.1f}% ({covered}/{total}) [{status}]')
            break
"
   ```

4. Generate prioritized gap list (files with most uncovered lines):
   ```bash
   cd backend
   python -c "
import json

with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

print('Priority Gap List (Top 20 by Uncovered Lines):')
print('-' * 60)
gaps = []
for file_path, metrics in data.get('files', {}).items():
    missing = metrics.get('summary', {}).get('missing_lines', 0)
    total = metrics.get('summary', {}).get('num_statements', 0)
    if missing > 0:
        gaps.append((file_path, missing, total))

# Sort by missing lines (descending)
gaps.sort(key=lambda x: x[1], reverse=True)

for i, (file_path, missing, total) in enumerate(gaps[:20], 1):
    pct_covered = ((total - missing) / total * 100) if total > 0 else 0
    print(f'{i:2d}. {file_path}')
    print(f'    Missing: {missing} lines | Coverage: {pct_covered:.1f}%')
"
   ```

Output format should be markdown with:
- Tables for module breakdown
- Code blocks for gap lists
- Actionable recommendations for Phase 2 planning
  </action>
  <verify>
1. File exists: backend/tests/coverage_reports/BASELINE_COVERAGE.md
2. File exists: backend/tests/coverage_reports/trending.json
3. BASELINE_COVERAGE.md contains:
   - Overall coverage percentage
   - Module breakdown table
   - AI component gap analysis
   - Priority gap list

Command:
```bash
cd backend && grep -q "Overall Coverage" tests/coverage_reports/BASELINE_COVERAGE.md && \
grep -q "Module Breakdown" tests/coverage_reports/BASELINE_COVERAGE.md && \
grep -q "AI Component Gaps" tests/coverage_reports/BASELINE_COVERAGE.md && \
test -f tests/coverage_reports/trending.json
```
  </verify>
  <done>
BASELINE_COVERAGE.md created with:
- Executive summary showing baseline coverage percentage and gap to 80% goal
- Module breakdown table (core, api, tools with percentages)
- AI component gap analysis (governance, LLM, memory, agents, social, skills, local agent, IM)
- Zero-coverage file catalog
- Prioritized gap list (most uncovered lines first)
- trending.json initialized with baseline entry for historical tracking
  </done>
</task>

<task type="auto">
  <name>Catalog Uncovered Lines in Critical Services</name>
  <files>backend/tests/coverage_reports/CRITICAL_PATHS_UNCOVERED.md</files>
  <action>
Create detailed catalog of uncovered code in critical paths:

1. Generate line-by-line coverage report for critical services:
   ```bash
   cd backend

   # Identify critical service files
   critical_files=(
     "core/agent_governance_service.py"
     "core/agent_context_resolver.py"
     "core/governance_cache.py"
     "core/trigger_interceptor.py"
     "core/student_training_service.py"
     "core/supervision_service.py"
     "core/episode_segmentation_service.py"
     "core/episode_retrieval_service.py"
     "core/episode_lifecycle_service.py"
     "core/agent_graduation_service.py"
     "core/llm/byok_handler.py"
     "core/llm/streaming_handler.py"
     "tools/canvas_tool.py"
     "tools/browser_tool.py"
     "tools/device_tool.py"
   )

   # Generate per-file uncovered lines analysis
   for file in "${critical_files[@]}"; do
     if [ -f "$file" ]; then
       echo "=== $file ===" >> tests/coverage_reports/baseline/uncovered_lines.txt
       python -c "
import json
import sys

file_path = '$file'
with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

# Find file in coverage data
for fp, metrics in data.get('files', {}).items():
    if file_path in fp:
        missing_lines = metrics.get('missing_lines', [])
        if missing_lines:
            print(f'Uncovered lines ({len(missing_lines)}):')
            # Group by function/method context
            for line in sorted(missing_lines)[:50]:  # First 50
                print(f'  Line {line}')
        else:
            print('All lines covered!')
        break
       " >> tests/coverage_reports/baseline/uncovered_lines.txt
       echo "" >> tests/coverage_reports/baseline/uncovered_lines.txt
     fi
   done
   ```

2. Create CRITICAL_PATHS_UNCOVERED.md with:
   - Per-service uncovered line count
   - High-risk functions (uncovered code in security/financial paths)
   - Complexity metrics (large uncovered blocks)
   - Test priority recommendations

3. Flag security-sensitive uncovered code:
   ```bash
   cd backend
   python -c "
import json
import re

# Security-sensitive patterns to flag
security_patterns = [
    (r'authorize', 'Authorization check'),
    (r'authenticate', 'Authentication'),
    (r'permission', 'Permission check'),
    (r'validate.*input', 'Input validation'),
    (r'sanitize', 'Sanitization'),
    (r'encrypt', 'Encryption'),
    (r'decrypt', 'Decryption'),
    (r'jwt', 'JWT handling'),
    (r'secret', 'Secret handling'),
    (r'password', 'Password handling'),
]

with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

print('Security-Sensitive Uncovered Code:')
print('-' * 60)

security_gaps = []
for file_path, metrics in data.get('files', {}).items():
    missing_lines = metrics.get('missing_lines', [])
    if not missing_lines:
        continue

    # Read file to check security patterns
    try:
        with open(file_path.replace('backend/', '')) as f:
            lines = f.readlines()

        for line_num in missing_lines:
            if line_num <= len(lines):
                line = lines[line_num - 1]
                for pattern, desc in security_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        security_gaps.append((file_path, line_num, desc, line.strip()))
    except Exception:
        pass

if security_gaps:
    for file_path, line_num, desc, code in security_gaps[:20]:
        print(f'[{desc}] {file_path}:{line_num}')
        print(f'  {code[:60]}')
else:
    print('No security-sensitive uncovered code found (good!)')
"
   ```

4. Generate complexity-weighted priority list:
   - Combine coverage gap (uncovered lines) with cyclomatic complexity
   - Prioritize: high complexity + low coverage = highest risk

Output should be markdown with:
- Tables showing per-service uncovered line counts
- Security gap analysis
- Complexity-weighted priority ranking
- Recommendations for test order in subsequent phases
  </action>
  <verify>
1. File exists: backend/tests/coverage_reports/CRITICAL_PATHS_UNCOVERED.md
2. Document contains:
   - Per-service uncovered line counts
   - Security gap analysis
   - Complexity-weighted priority list

Command:
```bash
cd backend && grep -q "Critical Paths" tests/coverage_reports/CRITICAL_PATHS_UNCOVERED.md && \
grep -q "Uncovered Lines" tests/coverage_reports/CRITICAL_PATHS_UNCOVERED.md
```
  </verify>
  <done>
CRITICAL_PATHS_UNCOVERED.md created with:
- Per-service catalog of uncovered lines (governance, LLM, memory, tools)
- Security-sensitive uncovered code flagged (auth, permission, validation, encryption)
- Complexity-weighted priority list for test planning
- Recommendations for Phase 2: prioritize high-complexity, low-coverage services
  </done>
</task>

</tasks>

<verification>
After all tasks complete, verify:

1. Coverage report generation:
   - HTML report accessible: backend/tests/coverage_reports/html/index.html
   - JSON metrics valid: tests/coverage_reports/metrics/coverage.json parses correctly
   - Overall coverage percentage documented

2. Gap analysis completeness:
   - All AI components analyzed (governance, LLM, memory, agents, social, skills, local agent, IM)
   - Critical paths with <50% coverage flagged
   - Uncovered lines in critical services catalogued

3. Documentation quality:
   - BASELINE_COVERAGE.md provides actionable baseline metrics
   - CRITICAL_PATHS_UNCOVERED.md prioritizes test development
   - trending.json initialized for historical tracking

Command:
```bash
cd backend && \
test -f tests/coverage_reports/BASELINE_COVERAGE.md && \
test -f tests/coverage_reports/CRITICAL_PATHS_UNCOVERED.md && \
test -f tests/coverage_reports/trending.json && \
test -f tests/coverage_reports/html/index.html && \
python -c "import json; d=json.load(open('tests/coverage_reports/trending.json')); assert 'history' in d, 'trending.json missing history'"
```
</verification>

<success_criteria>
1. Coverage report generated in 3 formats (HTML, JSON, terminal) showing baseline metrics
2. Baseline coverage percentage documented by module (core, api, tools)
3. Gaps identified in AI components: governance, LLM, memory, agents, social, skills, local agent, IM
4. Critical paths with <50% coverage flagged in CRITICAL_PATHS_UNCOVERED.md
5. Uncovered lines in critical services catalogued with security-sensitive code highlighted
6. trending.json initialized with baseline entry for historical tracking
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-infrastructure/01-foundation-infrastructure-01-SUMMARY.md` with:
- Actual baseline coverage percentage achieved
- Top 5 coverage gaps by lines of code
- Security-sensitive uncovered code count
- Recommendations for Plan 1-2 (Test Infrastructure Standardization)
</output>
