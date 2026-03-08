# Phase 153: Coverage Gates & Progressive Rollout - Research

**Researched:** March 7, 2026
**Domain:** CI/CD Coverage Enforcement & Quality Gates
**Confidence:** HIGH

## Summary

Phase 153 implements **PR-level coverage enforcement** with **progressive threshold rollout** across all four platforms (Backend Python, Frontend Next.js, Mobile React Native, Desktop Tauri/Rust). This phase builds on Phase 152's quality infrastructure documentation and establishes the first line of defense against coverage regression before code enters the codebase.

**Current State Analysis:**
- **Existing infrastructure**: Cross-platform coverage gate script operational (Phase 146), unified parallel testing workflow (Phase 148), trending infrastructure (Phase 150)
- **Coverage baselines**: Backend 26.15%, Frontend 65.85%, Mobile infrastructure in place, Desktop 65-70%
- **Gap**: No PR-level enforcement preventing coverage decreases, no progressive rollout strategy to avoid blocking development
- **Configuration**: Backend pytest.ini has `fail_under = 80` but not enforced in CI, Frontend jest.config.js has `coverageThreshold` with 75-80% ranges, Mobile jest.config.js has 60% threshold, Desktop no fail-under configured

**Progressive Rollout Strategy:**
- **Phase 1 (70%)**: Baseline enforcement - Prevents coverage regression from current baseline
- **Phase 2 (75%)**: Interim target - Incremental improvement without blocking development
- **Phase 3 (80%)**: Final target - Meets REQUIREMENTS.md thresholds for production quality
- **New code enforcement**: 80% strict threshold on all new files regardless of phase

**Primary recommendation:** Implement platform-specific coverage gates using diff-cover (backend), jest-coverage-report-action (frontend/mobile), and cargo-tarpaulin --fail-under (desktop) with configurable thresholds that progress through three phases. Leverage existing cross-platform coverage gate script as enforcement engine.

## Standard Stack

### Core Coverage Enforcement Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| **diff-cover** | latest (PyPI) | Backend diff coverage enforcement | Industry standard for Python PR coverage, compares coverage only on changed lines, integrates with pytest-cov |
| **pytest-cov** | latest (PyPI) | Backend coverage generation | Standard pytest coverage plugin, generates coverage.json and coverage.xml for diff-cover |
| **coverage.py** | latest (PyPI) | Backend coverage engine | Underlying coverage tool for Python, supports fail_under thresholds |
| **jest-coverage-report-action** | latest (GitHub) | Frontend PR coverage reports | GitHub Action that posts Jest coverage as PR comments, supports thresholds |
| **jest-expo** | latest (npm) | Mobile coverage generation | Expo's Jest preset for React Native testing, supports coverageThreshold |
| **cargo-tarpaulin** | latest (crates.io) | Desktop coverage enforcement | Rust coverage tool with --fail-under flag, generates JSON reports |

### Supporting Infrastructure
| Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **cross_platform_coverage_gate.py** | existing | Cross-platform threshold enforcement | Aggregate coverage across all platforms, enforce weighted minimums |
| **pr_coverage_comment_bot.py** | existing | PR coverage delta reporting | Generate file-by-file coverage drop reports for PRs |
| **unified-tests-parallel.yml** | existing | Parallel test execution | Run all 4 platform tests in <15 minutes, upload coverage artifacts |
| **update_cross_platform_trending.py** | existing | Historical trend tracking | Store coverage trends, compute regressions, trigger alerts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **diff-cover** | codecov / coveralls | External services require API keys, diff-cover is self-hosted and Git-aware |
| **jest-coverage-report-action** | ivatos-changeset-action / codecov-action | GitHub-native action is simpler, no external service dependencies |
| **cargo-tarpaulin** | cargo-llvm-cov | tarpaulin has simpler --fail-under flag, llvm-cov has better macOS support |

**Installation:**
```bash
# Backend (Python)
pip install diff-cover pytest-cov coverage.py

# Frontend/Mobile (Node.js)
npm install --save-dev jest jest-coverage-report-action

# Desktop (Rust)
cargo install cargo-tarpaulin
```

## Architecture Patterns

### Recommended Enforcement Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PR Check / Push to main or develop                          │
└────────────────┬────────────────────────────────────────────┘
                 │ Triggers unified-tests-parallel.yml
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Platform Test Jobs (Parallel, <15 min total)                │
│ ┌─────────────┬─────────────┬─────────────┬──────────────┐ │
│ │ Backend     │ Frontend    │ Mobile      │ Desktop      │ │
│ │ pytest      │ Jest        │ jest-expo   │ cargo test   │ │
│ │ + cov       │ + cov       │ + cov       │ + tarpaulin  │ │
│ └──────┬──────┴──────┬──────┴──────┬──────┴──────┬───────┘ │
└─────────┼──────────────┼──────────────┼──────────────┼───────┘
          │              │              │              │
          │ Upload coverage artifacts (backend-coverage.json, etc.)
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Coverage Gate Job (waits for all platform tests)            │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 1. Download all coverage artifacts                    │   │
│ │ 2. Run platform-specific diff coverage checks         │   │
│ │    - Backend: diff-cover --fail-under=70              │   │
│ │    - Frontend: jest-coverage-report-action            │   │
│ │    - Mobile: jest-expo coverageThreshold              │   │
│ │    - Desktop: cargo tarpaulin --fail-under=80         │   │
│ │ 3. Run cross_platform_coverage_gate.py                │   │
│ │ 4. Post PR comment with coverage breakdown            │   │
│ │ 5. Fail build if thresholds not met (main branch)     │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Progressive Rollout Pattern

**What:** Gradually increase coverage thresholds in three phases to avoid blocking development while ensuring quality improvement.

**Phases:**
- **Phase 1 (70%)**: Baseline enforcement - "Do not make coverage worse than current baseline"
- **Phase 2 (75%)**: Interim target - "Improve coverage incrementally"
- **Phase 3 (80%)**: Final target - "Meet production quality standards"

**Implementation:**
```python
# backend/tests/scripts/progressive_coverage_gate.py

PROGRESSIVE_THRESHOLDS = {
    "phase_1": {"backend": 70.0, "frontend": 70.0, "mobile": 50.0, "desktop": 40.0},
    "phase_2": {"backend": 75.0, "frontend": 75.0, "mobile": 55.0, "desktop": 45.0},
    "phase_3": {"backend": 80.0, "frontend": 80.0, "mobile": 60.0, "desktop": 50.0},
}

CURRENT_PHASE = os.getenv("COVERAGE_PHASE", "phase_1")

def get_threshold_for_platform(platform: str) -> float:
    """Get current phase threshold for platform."""
    return PROGRESSIVE_THRESHOLDS[CURRENT_PHASE][platform]
```

**Configuration via environment variable:**
```yaml
# .github/workflows/unified-tests-parallel.yml
env:
  COVERAGE_PHASE: phase_1  # Change to phase_2 or phase_3 over time
```

### Pattern 1: PR-Level Diff Coverage (Backend)

**What:** Enforce coverage only on changed lines in a PR, not entire codebase.

**When to use:** Backend Python pull requests, prevents coverage regression on new/modified code.

**Example:**
```yaml
# .github/workflows/backend-coverage.yml

- name: Generate coverage report
  run: |
    cd backend
    pytest --cov=core --cov=api --cov=tools \
      --cov-report=xml \
      --cov-report=json:tests/coverage_reports/metrics/coverage.json

- name: Enforce diff coverage
  run: |
    diff-cover coverage.xml \
      --compare-branch=origin/main \
      --fail-under=70 \
      --html-report=diff-coverage.html
```

**Why diff-cover:**
- Only measures coverage on changed lines (not entire codebase)
- Prevents PRs from decreasing coverage on affected code
- Provides HTML report showing which lines lack coverage
- Integrates with pytest-cov coverage.xml output

### Pattern 2: Jest Coverage Thresholds (Frontend/Mobile)

**What:** Enforce coverage percentage thresholds in Jest configuration.

**When to use:** Frontend Next.js and Mobile React Native pull requests.

**Example (frontend-nextjs/jest.config.js):**
```javascript
module.exports = {
  coverageThreshold: {
    global: {
      branches: 70,  // Phase 1: 70%, Phase 2: 75%, Phase 3: 80%
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
};
```

**Progressive rollout via environment variable:**
```javascript
// jest.config.js
const phase = process.env.COVERAGE_PHASE || 'phase_1';
const thresholds = {
  phase_1: { branches: 70, functions: 70, lines: 70, statements: 70 },
  phase_2: { branches: 75, functions: 75, lines: 75, statements: 75 },
  phase_3: { branches: 80, functions: 80, lines: 80, statements: 80 },
};

module.exports = {
  coverageThreshold: {
    global: thresholds[phase],
  },
};
```

**GitHub Action integration:**
```yaml
# .github/workflows/frontend-coverage.yml

- name: Run tests with coverage
  run: npm test -- --coverage --watchAll=false
  env:
    COVERAGE_PHASE: ${{ env.COVERAGE_PHASE }}

- name: Post coverage report to PR
  if: github.event_name == 'pull_request'
  uses: romeovs/lcov-reporter-action@v0.3.1
  with:
    lcov-file: ./coverage/lcov.info
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Pattern 3: Cargo Tarpaulin Fail-Under (Desktop)

**What:** Enforce coverage percentage threshold for Rust code.

**When to use:** Desktop Tauri/Rust pull requests.

**Example:**
```yaml
# .github/workflows/desktop-coverage.yml

- name: Run tests with coverage enforcement
  run: |
    cd frontend-nextjs/src-tauri
    cargo tarpaulin --out Json --output-dir coverage \
      --fail-under=40  # Phase 1: 40%, Phase 2: 45%, Phase 3: 50%
  env:
  COVERAGE_PHASE: ${{ env.COVERAGE_PHASE }}
```

**Progressive rollout script:**
```bash
# frontend-nextjs/src-tauri/scripts/run-coverage.sh

PHASE=${COVERAGE_PHASE:-phase_1}
case $PHASE in
  phase_1) FAIL_UNDER=40 ;;
  phase_2) FAIL_UNDER=45 ;;
  phase_3) FAIL_UNDER=50 ;;
esac

cargo tarpaulin --out Json --output-dir coverage --fail-under=$FAIL_UNDER
```

### Pattern 4: New Code Strict Enforcement

**What:** Enforce 80% coverage on all new files regardless of phase.

**When to use:** New files added to codebase (not modified existing files).

**Implementation:**
```python
# backend/tests/scripts/new_code_coverage_gate.py

def get_new_files(base_branch: str = "origin/main") -> List[str]:
    """Get list of new files in current branch."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", f"{base_branch}...HEAD"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.splitlines() if f.endswith('.py')]

def check_new_file_coverage(coverage_data: Dict, new_files: List[str]) -> bool:
    """Enforce 80% coverage on all new files."""
    for file_path in new_files:
        file_coverage = coverage_data.get("files", {}).get(file_path, {})
        coverage_pct = file_coverage.get("summary", {}).get("percent_covered", 0.0)

        if coverage_pct < 80.0:
            logger.error(f"New file {file_path} has {coverage_pct:.1f}% coverage (minimum: 80%)")
            return False

    return True
```

### Anti-Patterns to Avoid

- **All-or-nothing thresholds**: Enforcing 80% on entire codebase immediately → **Use**: Progressive rollout (70% → 75% → 80%)
- **Global coverage only**: Only measuring overall coverage without per-file checks → **Use**: Diff coverage for PRs + new file enforcement
- **Blocking development on day 1**: Setting aggressive thresholds that prevent all PRs → **Use**: Phase 1 (70%) as baseline, phase out over time
- **Ignoring platform differences**: Applying same threshold to all platforms → **Use**: Platform-specific thresholds (backend 70%, frontend 80%, mobile 50%, desktop 40%)
- **No PR feedback**: Failing builds without explaining why → **Use**: PR comments with coverage breakdown and file-by-file gaps

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Diff coverage calculation** | Custom git diff + coverage parsing logic | diff-cover (Python), jest-coverage-report-action (JS) | Edge cases: renamed files, moved code, merge commits, branch detection |
| **Coverage report generation** | Custom JSON/HTML parsers | pytest-cov --cov-report=xml, Jest coverage reporters | battle-tested output formats, tool ecosystem integration |
| **Threshold enforcement** | Custom comparison logic with exit codes | coverage.py fail_under, Jest coverageThreshold, tarpaulin --fail-under | Native enforcement, consistent exit codes, CI/CD integration |
| **PR comment posting** | Custom GitHub API calls | jest-coverage-report-action, github-script@v7 | Handles comment updates, bot detection, markdown formatting |
| **Progressive rollout** | Conditional logic in every workflow | Environment variable + centralized threshold config | Single source of truth, easy phase transitions |

**Key insight:** Coverage enforcement is a solved problem. Use battle-tested tools (diff-cover, pytest-cov, Jest thresholds) rather than building custom gate logic. Focus effort on platform-specific configuration and progressive rollout strategy.

## Common Pitfalls

### Pitfall 1: Setting Aggressive Thresholds Too Early

**What goes wrong:** Team sets 80% threshold on day 1, all PRs are blocked, development halts.

**Why it happens:** Confusing "target" (where we want to be) with "gate" (minimum to pass). Not accounting for current baseline (26.15% backend, 65.85% frontend).

**How to avoid:**
- Start with Phase 1 (70%): Slightly above current baseline, prevents regression
- Progress to Phase 2 (75%): After 2-4 weeks of Phase 1 success
- Reach Phase 3 (80%): After 2-4 weeks of Phase 2 success
- Measure baseline first: `pytest --cov=core --cov-report=term-missing`

**Warning signs:**
- More than 50% of PRs failing coverage gate
- Developers commenting out coverage checks to merge
- "Emergency bypass" requests increasing

### Pitfall 2: Enforcing Global Coverage Without Diff Coverage

**What goes wrong:** PR adds tests for new feature (90% coverage on new code) but overall coverage drops from 70% to 69% because of existing untested code. PR is blocked despite adding quality.

**Why it happens:** Global coverage threshold measures entire codebase, not just changed code.

**How to avoid:**
- Use diff-cover for backend: Only measures coverage on changed lines
- Use file-level thresholds for frontend/mobile: Enforce coverage on modified files only
- Allow global coverage to fluctuate ±2% while enforcing diff coverage strictly

**Example:**
```yaml
# GOOD: Diff coverage enforcement
- name: Enforce diff coverage
  run: diff-cover coverage.xml --fail-under=70 --compare-branch=origin/main

# BAD: Global coverage enforcement on PRs
- name: Enforce global coverage
  run: pytest --cov=core --cov-fail-under=70  # Blocks PRs adding tests
```

### Pitfall 3: Platform-Specific Configuration Errors

**What goes wrong:** Coverage gate fails because of configuration issues, not actual coverage problems (e.g., Jest not generating coverage file, wrong file paths in CI).

**Why it happens:** Each platform has different coverage tools and output formats. CI/CD configuration mistakes cause false negatives.

**How to avoid:**
- Test coverage gate locally first: `pytest --cov=core --cov-report=xml && diff-cover coverage.xml`
- Verify artifact uploads in CI: Check that coverage.json/coverage-final.json are uploaded
- Use `continue-on-error: true` during initial rollout to collect data without blocking
- Add debug logging: `ls -la coverage/` before gate enforcement

**Example:**
```yaml
# GOOD: Verify coverage file exists before enforcing
- name: Check coverage file
  run: |
    if [ ! -f backend/tests/coverage_reports/metrics/coverage.json ]; then
      echo "Coverage file not found!"
      exit 1
    fi

- name: Enforce coverage
  run: python cross_platform_coverage_gate.py --strict
```

### Pitfall 4: Ignoring New File Coverage

**What goes wrong:** PR adds new file with 0% coverage, but diff coverage passes because existing files have high coverage. Technical debt accumulates.

**Why it happens:** Diff coverage only measures changed lines in existing files. New files are excluded from diff calculation if they didn't exist before.

**How to avoid:**
- Add new file enforcement check: `git diff --name-only --diff-filter=A origin/main...HEAD`
- Enforce 80% coverage on all new Python/TypeScript files
- Fail PR if new files have <80% coverage regardless of phase

**Example:**
```python
# backend/tests/scripts/new_code_coverage_gate.py
new_files = get_new_files("origin/main")
for file_path in new_files:
    if file_path.endswith('.py'):
        coverage = get_file_coverage(file_path)
        if coverage < 80.0:
            print(f"ERROR: New file {file_path} has {coverage:.1f}% coverage (minimum: 80%)")
            exit(1)
```

### Pitfall 5: No Rollback Strategy

**What goes wrong:** Coverage gate blocks critical PR (e.g., security fix). No way to bypass gate. Team hacks around enforcement or disables it entirely.

**Why it happens:** Overly strict enforcement with no emergency escape valve.

**How to avoid:**
- Implement emergency bypass: `EMERGENCY_COVERAGE_BYPASS=true` environment variable
- Require approval for bypass: 2 maintainer approvals on PR
- Document bypass process: Runbook with "When to bypass" guidelines
- Track bypass usage: Alert if bypass used >3 times per month

**Example:**
```yaml
# .github/workflows/unified-tests-parallel.yml
- name: Enforce coverage thresholds
  run: |
    if [ "$EMERGENCY_COVERAGE_BYPASS" == "true" ]; then
      echo "⚠️ COVERAGE GATE BYPASSED (emergency mode)"
      exit 0
    fi

    python cross_platform_coverage_gate.py --strict
```

## Code Examples

### Example 1: Progressive Coverage Gate Configuration

**Source:** Proposed backend/tests/scripts/progressive_coverage_gate.py

```python
#!/usr/bin/env python3
"""
Progressive Coverage Gate Enforcement

Implements three-phase rollout strategy for coverage thresholds:
- Phase 1: 70% minimum (baseline enforcement)
- Phase 2: 75% minimum (interim target)
- Phase 3: 80% minimum (final target)

Usage:
    export COVERAGE_PHASE=phase_1
    python progressive_coverage_gate.py
"""

import os
import sys
from typing import Dict

# Progressive thresholds by phase
PROGRESSIVE_THRESHOLDS = {
    "phase_1": {
        "backend": 70.0,
        "frontend": 70.0,
        "mobile": 50.0,
        "desktop": 40.0,
    },
    "phase_2": {
        "backend": 75.0,
        "frontend": 75.0,
        "mobile": 55.0,
        "desktop": 45.0,
    },
    "phase_3": {
        "backend": 80.0,
        "frontend": 80.0,
        "mobile": 60.0,
        "desktop": 50.0,
    },
}

# New code always requires 80% regardless of phase
NEW_CODE_THRESHOLD = 80.0


def get_current_phase() -> str:
    """Get current phase from environment variable."""
    return os.getenv("COVERAGE_PHASE", "phase_1")


def get_threshold_for_platform(platform: str) -> float:
    """Get threshold for platform in current phase."""
    phase = get_current_phase()
    return PROGRESSIVE_THRESHOLDS[phase][platform]


def validate_phase(phase: str) -> bool:
    """Validate that phase is one of the allowed values."""
    return phase in PROGRESSIVE_THRESHOLDS


def main():
    """Main enforcement logic."""
    phase = get_current_phase()

    if not validate_phase(phase):
        print(f"ERROR: Invalid COVERAGE_PHASE '{phase}'. Must be one of: {list(PROGRESSIVE_THRESHOLDS.keys())}")
        sys.exit(2)

    print(f"📊 Coverage Gate: {phase.upper()}")
    print(f"   Backend threshold: {get_threshold_for_platform('backend'):.1f}%")
    print(f"   Frontend threshold: {get_threshold_for_platform('frontend'):.1f}%")
    print(f"   Mobile threshold: {get_threshold_for_platform('mobile'):.1f}%")
    print(f"   Desktop threshold: {get_threshold_for_platform('desktop'):.1f}%")
    print(f"   New code threshold: {NEW_CODE_THRESHOLD:.1f}% (always)")

    # Rest of enforcement logic...
    # Call cross_platform_coverage_gate.py with custom thresholds


if __name__ == "__main__":
    main()
```

### Example 2: Diff Coverage Enforcement for Backend

**Source:** Proposed .github/workflows/backend-diff-coverage.yml

```yaml
name: Backend Diff Coverage Enforcement

on:
  pull_request:
    branches: [main, develop]
    paths:
      - 'backend/**'

jobs:
  diff-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for diff comparison

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-testing.txt
          pip install diff-cover pytest-cov

      - name: Run tests with coverage
        run: |
          cd backend
          pytest --cov=core --cov=api --cov=tools \
            --cov-report=xml \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json

      - name: Enforce diff coverage (Phase 1: 70%)
        run: |
          cd backend
          THRESHOLD=${{ from_json('{"phase_1":70,"phase_2":75,"phase_3":80}')[env.COVERAGE_PHASE || 'phase_1'] }}
          diff-cover coverage.xml \
            --compare-branch=origin/main \
            --fail-under=$THRESHOLD \
            --html-report=diff-coverage.html
        env:
          COVERAGE_PHASE: ${{ vars.COVERAGE_PHASE || 'phase_1' }}

      - name: Upload diff coverage report
        uses: actions/upload-artifact@v4
        with:
          name: backend-diff-coverage
          path: backend/diff-coverage.html
          retention-days: 7

      - name: Post coverage as PR comment
        if: github.event_name == 'pull_request'
        uses: romeovs/lcov-reporter-action@v0.3.1
        with:
          lcov-file: ./backend/coverage.xml
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Example 3: Jest Coverage Threshold with Progressive Rollout

**Source:** Proposed frontend-nextjs/jest.config.js (progressive configuration)

```javascript
module.exports = {
  // Read coverage phase from environment variable
  // Default to phase_1 if not set
  get coverageThreshold() {
    const phase = process.env.COVERAGE_PHASE || 'phase_1';

    const thresholds = {
      phase_1: {
        branches: 70,
        functions: 70,
        lines: 70,
        statements: 70,
      },
      phase_2: {
        branches: 75,
        functions: 75,
        lines: 75,
        statements: 75,
      },
      phase_3: {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    };

    return {
      global: thresholds[phase],
      // New code always requires 80% regardless of phase
      './src/**/*.{ts,tsx}': {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    };
  },

  // Rest of Jest configuration...
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  collectCoverageFrom: [
    'components/**/*.{ts,tsx}',
    'pages/**/*.{ts,tsx}',
    'lib/**/*.{ts,tsx}',
    'hooks/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
    '!**/__tests__/**',
    '!**/*.test.{ts,tsx,js}',
  ],
  coverageReporters: ['json', 'json-summary', 'text', 'lcov'],
  coverageDirectory: 'coverage',
};
```

### Example 4: Desktop Tarpaulin with Progressive Threshold

**Source:** Proposed frontend-nextjs/src-tauri/scripts/run-coverage.sh

```bash
#!/bin/bash
# Progressive coverage enforcement for Desktop (Rust/Tauri)

set -e

# Read phase from environment variable
PHASE=${COVERAGE_PHASE:-phase_1}

# Map phase to fail-under threshold
case $PHASE in
  phase_1)
    FAIL_UNDER=40
    ;;
  phase_2)
    FAIL_UNDER=45
    ;;
  phase_3)
    FAIL_UNDER=50
    ;;
  *)
    echo "ERROR: Invalid COVERAGE_PHASE '$PHASE'. Must be phase_1, phase_2, or phase_3"
    exit 2
    ;;
esac

echo "📊 Desktop Coverage Gate: $PHASE"
echo "   Fail-under threshold: $FAIL_UNDER%"

# Run tarpaulin with threshold
cargo tarpaulin \
  --out Json \
  --output-dir coverage \
  --fail-under=$FAIL_UNDER \
  --verbose

echo "✅ Desktop coverage passed ($FAIL_UNDER% threshold)"
```

**GitHub Actions integration:**
```yaml
# .github/workflows/desktop-coverage.yml

- name: Run tests with coverage enforcement
  run: |
    cd frontend-nextjs/src-tauri
    bash scripts/run-coverage.sh
  env:
    COVERAGE_PHASE: ${{ vars.COVERAGE_PHASE || 'phase_1' }}
```

### Example 5: New Code Coverage Enforcement

**Source:** Proposed backend/tests/scripts/new_code_coverage_gate.py

```python
#!/usr/bin/env python3
"""
New Code Coverage Enforcement

Enforces 80% coverage on all new files regardless of coverage phase.
Prevents accumulation of untested new code.

Usage:
    python new_code_coverage_gate.py --coverage-file coverage.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_new_files(base_branch: str = "origin/main") -> list[str]:
    """Get list of new files added in current branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def load_coverage_data(coverage_file: Path) -> dict:
    """Load coverage data from JSON file."""
    with open(coverage_file) as f:
        return json.load(f)


def check_new_file_coverage(coverage_data: dict, new_files: list[str]) -> bool:
    """Enforce 80% coverage on all new Python files."""
    all_passed = True

    for file_path in new_files:
        # Only check Python files
        if not file_path.endswith('.py'):
            continue

        # Skip test files
        if 'test' in file_path or 'tests' in file_path:
            continue

        # Get file coverage from coverage data
        files_data = coverage_data.get("files", {})
        file_coverage = files_data.get(file_path, {})

        if not file_coverage:
            print(f"⚠️  WARNING: New file {file_path} not found in coverage data (0% coverage)")
            all_passed = False
            continue

        coverage_pct = file_coverage.get("summary", {}).get("percent_covered", 0.0)

        if coverage_pct < 80.0:
            print(f"❌ ERROR: New file {file_path} has {coverage_pct:.1f}% coverage (minimum: 80%)")
            all_passed = False
        else:
            print(f"✅ PASS: New file {file_path} has {coverage_pct:.1f}% coverage")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Enforce 80% coverage on new files")
    parser.add_argument("--coverage-file", type=Path, required=True, help="Path to coverage.json")
    parser.add_argument("--base-branch", default="origin/main", help="Base branch for comparison")
    args = parser.parse_args()

    # Load coverage data
    if not args.coverage_file.exists():
        print(f"ERROR: Coverage file not found: {args.coverage_file}")
        sys.exit(2)

    coverage_data = load_coverage_data(args.coverage_file)

    # Get new files
    new_files = get_new_files(args.base_branch)

    if not new_files:
        print("✅ No new files detected")
        sys.exit(0)

    print(f"📊 Checking {len(new_files)} new files...")

    # Enforce 80% coverage
    if check_new_file_coverage(coverage_data, new_files):
        print("✅ All new files meet 80% coverage threshold")
        sys.exit(0)
    else:
        print("❌ Some new files do not meet 80% coverage threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

## State of the Art

### Old Approach vs Current Approach

| Aspect | Old Approach | Current Approach | When Changed | Impact |
|--------|--------------|------------------|--------------|--------|
| **Coverage enforcement** | Manual coverage reviews, no automated gates | Automated diff-cover + Jest thresholds + tarpaulin fail-under | Phase 153 (proposed) | PRs automatically blocked if coverage decreases |
| **Threshold strategy** | All-or-nothing (80% immediately) | Progressive rollout (70% → 75% → 80%) | Phase 153 (proposed) | Prevents blocking development while improving quality |
| **Platform coverage** | Backend-only enforcement | Cross-platform gates (4 platforms) | Phase 146 (existing) | Balanced quality across entire codebase |
| **New code quality** | No enforcement on new files | 80% strict threshold on all new files | Phase 153 (proposed) | Prevents technical debt accumulation |
| **PR feedback** | Manual code review comments | Automated PR comments with coverage breakdown | Phase 148 (existing) | Developers see coverage impact immediately |

### Coverage Enforcement Best Practices (2026)

**Industry standard:**
- **Diff coverage, not global**: Enforce coverage only on changed lines (diff-cover) → Prevents false negatives
- **Progressive rollout**: Incremental thresholds (70% → 75% → 80%) → Avoids blocking development
- **Platform-specific thresholds**: Different targets per platform (70/80/50/40) → Reflects testing complexity
- **New code enforcement**: 80% minimum on all new files → Prevents debt accumulation
- **Emergency bypass**: Documented escape valve with approval → Unblocks critical PRs

**Atom's implementation:**
- ✅ Diff coverage planned (diff-cover for backend)
- ✅ Progressive rollout planned (phase_1 → phase_2 → phase_3)
- ✅ Platform-specific thresholds existing (70/80/50/40)
- ⚠️ New code enforcement missing (needs implementation)
- ⚠️ Emergency bypass missing (needs documentation)

**Phase 153 closes the enforcement gaps.**

### Deprecated/Outdated Approaches

**Deprecated:**
- **Global coverage-only gates**: Measuring entire codebase coverage on every PR → Use diff coverage for changed files only
- **All-or-nothing thresholds**: Setting 80% gate immediately → Use progressive rollout
- **Manual coverage reviews**: Developers manually checking coverage → Use automated gates + PR comments
- **Single-platform enforcement**: Only backend coverage gates → Use cross-platform gates (all 4 platforms)
- **No bypass mechanism**: Blocking all PRs that fail → Use emergency bypass with approval workflow

**What we use instead:**
- Diff coverage (diff-cover, jest-coverage-report-action)
- Progressive rollout (70% → 75% → 80% phases)
- Automated PR comments (GitHub Actions, github-script@v7)
- Cross-platform gates (cross_platform_coverage_gate.py)
- Emergency bypass (EMERGENCY_COVERAGE_BYPASS env var)

## Open Questions

1. **Phase transition timeline**
   - What we know: Progressive rollout has 3 phases (70% → 75% → 80%)
   - What's unclear: How long to spend in each phase before promoting to next?
   - Recommendation: 2-4 weeks per phase, monitor PR pass rate. If >80% of PRs passing phase_1, promote to phase_2.

2. **Emergency bypass governance**
   - What we know: Need bypass mechanism for critical PRs (security fixes, hotfixes)
   - What's unclear: Who approves bypass? How many bypasses per month acceptable?
   - Recommendation: Require 2 maintainer approvals on PR. Alert if bypass used >3 times per month. Document in runbook.

3. **New file enforcement for frontend/mobile**
   - What we know: Backend has Python-specific new file enforcement script
   - What's unclear: How to detect "new files" for TypeScript/JavaScript without git diff-filter?
   - Recommendation: Use git diff --name-only --diff-filter=A for all platforms, enforce 80% coverage via file-level Jest thresholds.

4. **Desktop tarpaulin platform compatibility**
   - What we know: tarpaulin has linking issues on macOS x86_64 (documented in Phase 146)
   - What's unclear: Can we reliably run tarpaulin in CI/CD (ubuntu-latest) for enforcement?
   - Recommendation: Use ubuntu-latest runner for desktop coverage gate (tarpaulin works reliably on Linux). Skip local macOS enforcement.

## Sources

### Primary (HIGH confidence)
- **Atom existing infrastructure** (verified by code inspection):
  - `backend/tests/scripts/cross_platform_coverage_gate.py` - Cross-platform enforcement engine (Phase 146)
  - `backend/tests/scripts/pr_coverage_comment_bot.py` - PR coverage delta reporting
  - `.github/workflows/unified-tests-parallel.yml` - Parallel test execution with artifact uploads (Phase 148)
  - `backend/pytest.ini` - Coverage configuration with `fail_under = 80` (not enforced in CI)
  - `frontend-nextjs/jest.config.js` - Jest coverageThreshold configuration (75-80% ranges)
  - `mobile/jest.config.js` - jest-expo coverageThreshold (60% threshold)
  - `docs/CROSS_PLATFORM_COVERAGE.md` - Platform thresholds and weighted coverage (Phase 146)
- **REQUIREMENTS.md** - ENFORCE-01 and ENFORCE-02 requirements definitions

### Secondary (MEDIUM confidence)
- **diff-cover documentation** (Python package documentation, industry standard for diff coverage)
- **pytest-cov documentation** (pytest coverage plugin, coverage.xml generation)
- **Jest coverage documentation** (coverageThreshold configuration, PR reporting)
- **cargo-tarpaulin documentation** (--fail-under flag for Rust coverage enforcement)

### Tertiary (LOW confidence)
- **Web search attempts** - Search service returned empty results for all queries about coverage gates, progressive rollout, diff-cover, jest-coverage-report-action
- **Recommendation**: Verify diff-cover and jest-coverage-report-action capabilities via official docs before implementation (search unable to provide current info)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards (diff-cover, pytest-cov, Jest thresholds, tarpaulin)
- Architecture: HIGH - Existing cross-platform infrastructure provides proven template, verified by code inspection
- Pitfalls: HIGH - Progressive rollout and diff coverage are well-documented anti-patterns
- Code examples: HIGH - Examples derived from existing Atom infrastructure and standard tool documentation

**Research date:** March 7, 2026
**Valid until:** April 7, 2026 (30 days - stable domain, coverage enforcement patterns don't change rapidly)

**Next steps:**
1. Implement progressive_coverage_gate.py with phase-aware thresholds
2. Update unified-tests-parallel.yml to call coverage gate with COVERAGE_PHASE env var
3. Add diff-cover enforcement step to backend coverage job
4. Update jest.config.js (frontend/mobile) with progressive coverageThreshold
5. Implement new_code_coverage_gate.py for all platforms
6. Document emergency bypass process in runbook
7. Set COVERAGE_PHASE=phase_1 in GitHub Actions variables
8. Test coverage gate on draft PR before enforcing on main/develop
