# Coverage Enforcement Guide (Phase 153)

## Progressive Rollout Strategy

Atom uses a three-phase rollout to enforce coverage thresholds without blocking development:

- **Phase 1 (70%)**: Baseline enforcement - Prevents coverage regression
- **Phase 2 (75%)**: Interim target - Incremental improvement
- **Phase 3 (80%)**: Final target - Production quality

### Current Phase: Phase 1

**Active Thresholds:**
- Backend: 70%
- Frontend: 70%
- Mobile: 50%
- Desktop: 40%

### Phase Transition Criteria

Move to next phase when:
- **PR pass rate**: >80% of PRs pass current phase threshold
- **Duration**: 2-4 weeks in current phase
- **Coverage trend**: Consistent improvement (no regression)

### Phase Transition Process

1. Set `COVERAGE_PHASE=phase_2` in GitHub repository variables
2. Update backend/docs/COVERAGE_ENFORCEMENT.md with transition date
3. Announce phase transition in team Slack
4. Monitor PR pass rate for 1 week
5. Rollback to previous phase if >50% of PRs fail

### Rollback Process

If new phase blocks too many PRs:
1. Set `COVERAGE_PHASE=phase_1` (previous phase)
2. Investigate failing PRs (identify common patterns)
3. Address root causes (technical debt, complexity, lack of time)
4. Retry phase transition after 2 weeks

---

## Platform-Specific Thresholds

### Backend (Python)
- **Phase 1**: 70%
- **Phase 2**: 75%
- **Phase 3**: 80%
- **Tool**: diff-cover with pytest-cov
- **Enforcement**: Pull requests that decrease coverage on changed lines are blocked
- **Configuration**: backend/tests/scripts/progressive_coverage_gate.py
- **Command**: `python progressive_coverage_gate.py --strict`

### Frontend (Next.js)
- **Phase 1**: 70%
- **Phase 2**: 75%
- **Phase 3**: 80%
- **Tool**: Jest coverageThreshold
- **Enforcement**: Build fails if coverage below current phase threshold
- **Configuration**: frontend-nextjs/jest.config.js
- **Command**: `npm test -- --coverage --watchAll=false`

### Mobile (React Native)
- **Phase 1**: 50%
- **Phase 2**: 55%
- **Phase 3**: 60%
- **Tool**: jest-expo coverageThreshold
- **Enforcement**: Build fails if coverage below current phase threshold
- **Configuration**: mobile/jest.config.js
- **Command**: `npm test -- --coverage --watchAll=false`

**Note:** Mobile thresholds are lower (50-60%) due to React Native testing complexity (platform-specific code, device features, native modules).

### Desktop (Tauri/Rust)
- **Phase 1**: 40%
- **Phase 2**: 45%
- **Phase 3**: 50%
- **Tool**: cargo-tarpaulin --fail-under
- **Enforcement**: Build fails if coverage below current phase threshold
- **Configuration**: frontend-nextjs/src-tauri/scripts/run-coverage.sh
- **Command**: `bash scripts/run-coverage.sh`

**Note:** Desktop thresholds are lower (40-50%) due to Rust unsafe blocks, FFI bindings, and platform-specific code.

---

## New Code Enforcement

All new files require **80% coverage** regardless of current phase.

### Why New Code Has Higher Threshold

- Prevents technical debt accumulation
- Ensures quality from day one
- Avoids "will add tests later" anti-pattern
- Sets standard for future development

### Enforcement Mechanism

**Backend:**
- Tool: `backend/tests/scripts/new_code_coverage_gate.py`
- Scans coverage.json for new files (not in baseline)
- Exits with error if new file below 80%

**Frontend/Mobile:**
- Jest coverageThreshold enforces globally
- New files must meet current phase threshold (70% → 80%)
- Manual PR review for new files below 80%

**Desktop:**
- Manual PR review (tarpaulin lacks per-file threshold support)
- Check coverage report for new files
- Require tests for new IPC handlers, system tray, file operations

---

## Coverage Gate Behavior

### Backend (Python)

**Tool:** diff-cover with pytest-cov

**Enforcement:** Pull requests that decrease coverage on changed lines are blocked

**Configuration:**
```yaml
# .github/workflows/unified-tests-parallel.yml
- name: Enforce diff coverage (Backend)
  run: |
    cd backend
    python tests/scripts/progressive_coverage_gate.py --strict
  env:
    COVERAGE_PHASE: ${{ vars.COVERAGE_PHASE || 'phase_1' }}
    EMERGENCY_COVERAGE_BYPASS: ${{ vars.EMERGENCY_COVERAGE_BYPASS || 'false' }}
```

**Output:**
```
======================================================================
Cross-Platform Coverage Report
======================================================================

Platform Coverage:
  Backend: 75.23% (weight: 35%, contribution: 26.33%)

Overall Weighted Coverage: 72.15%

Platform Threshold Checks:
  Backend     : 75.23% >= 70.00% ... ✓ PASS

All platforms passed minimum thresholds! ✓
```

**Diff-Cover Details:**
- Compares coverage.xml against base branch (origin/main)
- Fails if any changed file has decreased coverage
- Shows specific lines lacking coverage
- Enforces 80% threshold on new files

### Frontend (Next.js)

**Tool:** Jest coverageThreshold

**Enforcement:** Build fails if coverage below current phase threshold

**Configuration:**
```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  coverageThreshold: {
    get global() {
      const phase = process.env.COVERAGE_PHASE || 'phase_1';
      const thresholds = {
        phase_1: { lines: 70, branches: 70, functions: 70, statements: 70 },
        phase_2: { lines: 75, branches: 75, functions: 75, statements: 75 },
        phase_3: { lines: 80, branches: 80, functions: 80, statements: 80 },
      };
      return thresholds[phase] || thresholds.phase_1;
    },
  },
};
```

**Output:**
```
----------------|---------|----------|---------|---------|-------------------
File            | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
----------------|---------|----------|---------|---------|-------------------
All files       |   72.15 |    68.42 |   75.00 |   73.08|
----------------|---------|----------|---------|---------|-------------------
```

### Mobile (React Native)

**Tool:** jest-expo coverageThreshold

**Enforcement:** Build fails if coverage below current phase threshold

**Configuration:**
```javascript
// mobile/jest.config.js
module.exports = {
  coverageThreshold: {
    get global() {
      const phase = process.env.COVERAGE_PHASE || 'phase_1';
      const thresholds = {
        phase_1: { lines: 50, branches: 50, functions: 50, statements: 50 },
        phase_2: { lines: 55, branches: 55, functions: 55, statements: 55 },
        phase_3: { lines: 60, branches: 60, functions: 60, statements: 60 },
      };
      return thresholds[phase] || thresholds.phase_1;
    },
  },
};
```

**Note:** Mobile thresholds are lower (50-60%) due to React Native testing complexity.

### Desktop (Tauri/Rust)

**Tool:** cargo-tarpaulin --fail-under

**Enforcement:** Build fails if coverage below current phase threshold

**Configuration:**
```bash
#!/bin/bash
# frontend-nextjs/src-tauri/scripts/run-coverage.sh

PHASE=${COVERAGE_PHASE:-phase_1}
case $PHASE in
  phase_1) THRESHOLD=40 ;;
  phase_2) THRESHOLD=45 ;;
  phase_3) THRESHOLD=50 ;;
  *) THRESHOLD=40 ;;
esac

cargo tarpaulin \
  --out Json \
  --output-dir coverage \
  --fail-under $THRESHOLD \
  --timeout 300 \
  --verbose
```

**Note:** Desktop thresholds are lower (40-50%) due to Rust unsafe blocks, FFI bindings, and platform-specific code.

---

## Emergency Bypass Process

### When to Use Bypass

**Valid reasons for bypassing coverage gates:**
- **Security fixes**: Critical vulnerabilities requiring immediate deployment
- **Hotfixes**: Production incidents requiring immediate patch
- **False positives**: Coverage tool bugs (document issue in PR)

**Invalid reasons (DO NOT USE):**
- "Not enough time" - Plan ahead for test development
- "Complex code" - Break into smaller, testable chunks
- "Will add tests later" - Tests must accompany code

### Bypass Approval Workflow

1. Set `EMERGENCY_COVERAGE_BYPASS=true` in repository secrets
2. Open pull request with `[EMERGENCY BYPASS]` in title
3. Obtain **2 maintainer approvals** (enforced via GitHub branch protection)
4. Document bypass reason in PR description
5. Add follow-up issue for test coverage improvement

**Example PR Description:**
```markdown
## [EMERGENCY BYPASS] Hotfix: Fix authentication token leak

### Bypass Reason
Critical security issue requiring immediate deployment to production.
Authentication tokens logged in plaintext error messages.

### Risk Assessment
- **Severity**: Critical (CWE-532)
- **Exposure**: All authenticated users
- **Reproduction**: Login → Trigger error → Check logs

### Fix Applied
- Remove token from error messages
- Add token redaction to logging middleware
- Update error handling docs

### Follow-Up Issue
#1234 - Add comprehensive tests for error handling middleware

### Approvals
- @maintainer1
- @maintainer2
```

### Bypass Tracking

All bypass usage is tracked and alerted:
- **GitHub Actions logs**: Show bypass activation
- **Slack webhook**: Alerts team on bypass usage
- **Monthly review**: >3 bypasses/month triggers investigation

**Tracking Script:** `backend/tests/scripts/emergency_coverage_bypass.py`

**Bypass Log:** `backend/tests/coverage_reports/metrics/bypass_log.json`

**Example Log Entry:**
```json
{
  "timestamp": "2026-03-08T12:34:56Z",
  "reason": "Security fix: Authentication token leak",
  "pr_url": "https://github.com/rushiparikh/atom/pull/1234",
  "approvers": ["alice", "bob"],
  "phase": "phase_1",
  "environment": "production"
}
```

### How to Bypass

**Option 1: Repository Secret (Recommended)**

1. Go to GitHub repository Settings → Secrets and variables → Actions
2. Add repository variable:
   - Name: `EMERGENCY_COVERAGE_BYPASS`
   - Value: `true`
3. Re-run workflow or push new commit
4. **IMPORTANT**: Remove bypass after PR merges

**Option 2: Workflow Variable (Temporary)**

1. Edit `.github/workflows/unified-tests-parallel.yml`:
   ```yaml
   env:
     EMERGENCY_COVERAGE_BYPASS: 'true'
   ```
2. Commit and push to PR branch
3. **IMPORTANT**: Remove workflow variable change after PR merges

**Option 3: Environment Variable (Local Testing)**

```bash
EMERGENCY_COVERAGE_BYPASS=true npm test
EMERGENCY_COVERAGE_BYPASS=true pytest tests/
```

### Bypass Abuse Prevention

**Frequency Monitoring:**
- >3 bypasses in 30 days triggers investigation
- Monthly review meeting to assess bypass patterns
- Escalation to tech lead if bypass abuse detected

**Bypass Review Checklist:**
- [ ] Is this a valid emergency (security, hotfix, false positive)?
- [ ] Is there a documented follow-up issue?
- [ ] Have 2 maintainers approved?
- [ ] Is bypass reason documented in PR description?
- [ ] Will bypass be removed after PR merges?

**Consequences of Abuse:**
- First offense: Warning
- Second offense: Loss of bypass privileges
- Third offense: Branch protection review

---

## Troubleshooting

### Coverage Gate Fails Locally But Passes in CI

**Problem:** Coverage files not committed, local environment differs from CI

**Solution:**
```bash
# Backend: Regenerate coverage files
cd backend
rm -rf tests/coverage_reports/
pytest --cov=core --cov=api --cov=tools --cov-report=xml

# Frontend: Clear Jest cache
cd frontend-nextjs
rm -rf coverage/
npm test -- --coverage --watchAll=false

# Mobile: Clear Jest cache
cd mobile
rm -rf coverage/
npm test -- --coverage --watchAll=false

# Desktop: Clear cargo cache
cd frontend-nextjs/src-tauri
cargo clean
cargo tarpaulin --out Json --output-dir coverage
```

### Diff-Cover Reports Wrong Coverage

**Problem:** Comparing against wrong branch, merge commit confusion

**Solution:**
```bash
# Check which branch diff-cover is comparing
git log --oneline --graph --decorate

# Force comparison against main
cd backend
diff-cover coverage.xml --compare-branch=origin/main

# Check coverage.xml source
grep -E 'origin/main|origin/develop' coverage.xml
```

### Jest Threshold Not Enforcing

**Problem:** coverageThreshold not reading COVERAGE_PHASE

**Solution:**
```bash
# Check jest.config.js uses getter function
# Should be: get coverageThreshold() { ... }
# NOT: coverageThreshold: { ... }

cd frontend-nextjs
cat jest.config.js | grep -A 5 'coverageThreshold'

# Verify environment variable
echo $COVERAGE_PHASE  # Should be phase_1, phase_2, or phase_3

# Test Jest with debug output
COVERAGE_PHASE=phase_1 npm run test:ci -- --coverage --verbose
```

### Tarpaulin Fails on macOS

**Problem:** Known linking issues with tarpaulin on macOS x86_64

**Solution:**
- Run desktop coverage in CI/CD (ubuntu-latest) only, not locally
- Use Docker container for local desktop coverage testing:
  ```bash
  docker run --rm -v $(pwd):/work rust:latest \
    bash -c "cd /work && cargo install cargo-tarpaulin && cargo tarpaulin"
  ```

### Coverage Report Not Generated

**Problem:** Coverage JSON file missing, gate script fails

**Solution:**
```bash
# Backend: Check pytest-cov installed
cd backend
pip list | grep pytest-cov

# Frontend: Check Jest configured for coverage
cd frontend-nextjs
cat package.json | grep -A 3 'test:ci'

# Mobile: Check jest-expo installed
cd mobile
npm list jest-expo

# Desktop: Check tarpaulin installed
cd frontend-nextjs/src-tauri
cargo install --list | grep tarpaulin
```

### New Code Gate Fails on Existing Files

**Problem:** `new_code_coverage_gate.py` incorrectly flags existing files as new

**Solution:**
```bash
# Update baseline coverage file
cd backend
cp tests/coverage_reports/metrics/coverage.json \
   tests/coverage_reports/metrics/baseline_coverage.json

# Re-run gate
python tests/scripts/new_code_coverage_gate.py \
  --coverage-file tests/coverage_reports/metrics/coverage.json \
  --baseline-file tests/coverage_reports/metrics/baseline_coverage.json
```

### Cross-Platform Gate Exits 0 Despite Failures

**Problem:** Missing `--strict` flag in CI/CD workflow

**Solution:**
```yaml
# .github/workflows/unified-tests-parallel.yml
- name: Enforce diff coverage (Backend)
  run: |
    cd backend
    python tests/scripts/progressive_coverage_gate.py --strict
  env:
    COVERAGE_PHASE: ${{ vars.COVERAGE_PHASE || 'phase_1' }}
```

**Key:** Add `--strict` flag to enforce gate (exit 1 on failure).

---

## Phase Rollout Timeline

### Phase 1: Baseline (70%)
- **Start Date:** March 8, 2026
- **Target:** Prevent coverage regression
- **Expected Duration:** 2-4 weeks
- **Success Criteria:** >80% of PRs pass 70% threshold

### Phase 2: Interim (75%)
- **Start Date:** TBD (after Phase 1 success)
- **Target:** Incremental improvement
- **Expected Duration:** 2-4 weeks
- **Success Criteria:** >80% of PRs pass 75% threshold

### Phase 3: Final (80%)
- **Start Date:** TBD (after Phase 2 success)
- **Target:** Production quality
- **Expected Duration:** Ongoing
- **Success Criteria:** >80% of PRs pass 80% threshold

---

## Metrics and Monitoring

### Coverage Trend Tracking

**Dashboard:** `backend/tests/coverage_reports/metrics/cross_platform_trend.json`

**Update Frequency:** Every PR (CI/CD), daily (cron job)

**Metrics:**
- Overall weighted coverage percentage
- Platform-specific coverage percentages
- PR pass rate by phase
- Bypass usage frequency
- New code compliance rate

### Alerts and Notifications

**Slack Integration:**
- Coverage gate failure (PR blocked)
- Emergency bypass activated
- >3 bypasses in 30 days (investigation triggered)
- Phase transition announcement

**PR Comments:**
- Cross-platform coverage report
- Platform breakdown with thresholds
- Remediation steps for failing platforms

### Monthly Review Process

**Attendees:** Tech lead, QA lead, senior engineers

**Agenda:**
1. Review coverage trends (last 30 days)
2. Assess phase transition readiness
3. Review bypass usage (investigate abuse)
4. Identify common coverage gaps
5. Plan test development priorities

**Output:**
- Phase transition decision (stay/advance/rollback)
- Follow-up issues for coverage gaps
- Documentation updates (if needed)

---

## References

- **Progressive Coverage Gate:** `backend/tests/scripts/progressive_coverage_gate.py`
- **Cross-Platform Coverage Gate:** `backend/tests/scripts/cross_platform_coverage_gate.py`
- **New Code Coverage Gate:** `backend/tests/scripts/new_code_coverage_gate.py`
- **Emergency Bypass Tracking:** `backend/tests/scripts/emergency_coverage_bypass.py`
- **CI/CD Workflow:** `.github/workflows/unified-tests-parallel.yml`
- **Research:** `.planning/phases/153-coverage-gates-progressive-rollout/153-RESEARCH.md`

---

*Last Updated: March 8, 2026*
*Phase: 153 - Coverage Gates & Progressive Rollout*
*Plan: 04 - Emergency Bypass Documentation*
