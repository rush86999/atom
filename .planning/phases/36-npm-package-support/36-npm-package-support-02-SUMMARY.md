---
phase: 36-npm-package-support
plan: 02
subsystem: security
tags: [npm, vulnerability-scanning, postinstall-scripts, shai-hulud, snyk, security-scanning]

# Dependency graph
requires:
  - phase: 35-python-package-support
    provides: PackageGovernanceService, vulnerability scanning patterns
provides:
  - NpmDependencyScanner for npm/yarn/pnpm vulnerability scanning
  - NpmScriptAnalyzer for malicious postinstall/preinstall script detection
  - Shai-Hulud/Sha1-Hulud attack prevention (700+ infected packages)
  - Snyk integration for commercial vulnerability database
affects: [36-03-npm-package-installer, 36-06-security-testing, 36-07-documentation]

# Tech tracking
tech-stack:
  added: [npm audit, yarn audit, pnpm audit, snyk cli, requests library, npm registry api]
  patterns: [vulnerability scanning with timeout fallback, script pattern regex matching, graceful degradation]

key-files:
  created: [backend/core/npm_dependency_scanner.py, backend/core/npm_script_analyzer.py, backend/tests/test_npm_dependency_scanner.py, backend/tests/test_npm_script_analyzer.py]
  modified: []

key-decisions:
  - "Return safe=True on scanning timeouts (timeout != vulnerability)"
  - "Snyk integration is optional - scanner works with npm audit only"
  - "Detect 10 malicious patterns: fetch, axios, https, request, process.env, fs, child_process, exec, eval, Function, atob, btoa"
  - "Flag 3 suspicious package combinations: trufflehog+axios, dotenv+axios, node-fetch+fs"

patterns-established:
  - "Timeout handling: Return safe=True with warning, don't block on scanner failure"
  - "Graceful degradation: Skip Snyk if CLI not installed, continue with npm audit"
  - "Pattern matching: Use regex for flexible malicious script detection"

# Metrics
duration: 18min
completed: 2026-02-19
---

# Phase 36: Plan 02 - npm Dependency & Script Security Scanners Summary

**npm package vulnerability scanner using npm audit + Snyk integration and malicious postinstall script analyzer detecting Shai-Hulud attack patterns**

## Performance

- **Duration:** 18 minutes
- **Started:** 2026-02-19T17:24:55Z
- **Completed:** 2026-02-19T17:43:30Z
- **Tasks:** 5
- **Files modified:** 4

## Accomplishments

- **NpmDependencyScanner** with npm/yarn/pnpm audit integration, Snyk optional support, timeout handling returning safe=True
- **NpmScriptAnalyzer** detecting 10 malicious script patterns (fetch, axios, child_process, eval, process.env, fs, atob/btoa) and 3 suspicious package combinations
- **Shai-Hulud attack prevention** - credential stealer detection (TruffleHog + axios, dotenv + axios)
- **Comprehensive test coverage** - 33 tests (15 scanner + 18 analyzer), 100% pass rate

## Task Commits

Each task was committed atomically:

1. **Task 1-2: NpmDependencyScanner with npm audit and Snyk integration** - `d994a3d4` (feat)
2. **Task 3: NpmScriptAnalyzer for postinstall threat detection** - `4880a292` (feat)
3. **Task 4: NpmDependencyScanner tests** - `5ff9740f` (test)
4. **Task 5: NpmScriptAnalyzer tests** - `cdcd9db6` (test)

**Plan metadata:** (to be committed after STATE update)

_Note: Tasks 1-2 combined into single commit as Snyk integration was implemented together with base scanner_

## Files Created/Modified

- `backend/core/npm_dependency_scanner.py` - npm/yarn/pnpm vulnerability scanner with Snyk integration
- `backend/core/npm_script_analyzer.py` - Malicious postinstall/preinstall script pattern detector
- `backend/tests/test_npm_dependency_scanner.py` - 15 tests covering audit integration, Snyk, timeouts, package managers
- `backend/tests/test_npm_script_analyzer.py` - 18 tests covering malicious patterns, registry API, suspicious combinations

## Decisions Made

- **Timeout handling returns safe=True**: Scanning timeouts indicate infrastructure problems, not security vulnerabilities. Returns warning but doesn't block installation.
- **Snyk is optional**: Scanner works with npm audit alone. Snyk CLI check uses shutil.which() for graceful fallback.
- **Scoped package parsing**: Fixed @angular/core@12.0.0 parsing (second @ delimiter splits version).
- **affected_versions field**: Handle both string and list formats from npm audit JSON.
- **Pattern matching**: Use regex for flexible detection (e.g., \bfetch\s*\() catching variations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed scoped package parsing**
- **Found during:** Task 4 (testing scoped package parsing)
- **Issue:** @angular/core@12.0.0 was parsed incorrectly (split on first @ instead of second)
- **Fix:** Modified _create_package_json to check for @ at start (scoped) and count @ occurrences to split correctly
- **Files modified:** backend/core/npm_dependency_scanner.py
- **Verification:** test_scoped_package_parsing passes, @angular/core@12.0.0 correctly parsed
- **Committed in:** 5ff9740f (Task 4 commit)

**2. [Rule 1 - Bug] Fixed affected_versions field type handling**
- **Found during:** Task 4 (vulnerability parsing test)
- **Issue:** npm audit returns range as string, but test expected list. Inconsistent handling.
- **Fix:** Wrap range in list if not already list: [vuln.get("range", [])] if not isinstance(...)
- **Files modified:** backend/core/npm_dependency_scanner.py
- **Verification:** test_vulnerability_parsing passes, both string and list formats handled
- **Committed in:** 5ff9740f (Task 4 commit)

**3. [Rule 2 - Missing Critical] Added process.env pattern test assertion fix**
- **Found during:** Task 5 (script analyzer testing)
- **Issue:** Warning string contains escaped pattern \\bprocess\\.env\\. so "process.env" in w fails
- **Fix:** Changed assertion to any("process" in w and "env" in w for w in result["warnings"])
- **Files modified:** backend/tests/test_npm_script_analyzer.py
- **Verification:** test_detect_process_env passes
- **Committed in:** cdcd9db6 (Task 5 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 test fix)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep. Tests validate fixes.

## Issues Encountered

- **Python 2.7 vs Python 3**: Initial import test failed because `python` command points to Python 2.7. Fixed by using `python3` for all commands.
- **Test fixture reusability**: Initial yarn/pnpm tests reused npm audit fixture (2 vulnerabilities) causing assertion failures. Fixed by creating minimal single-package fixtures per test.

## User Setup Required

None - no external service configuration required. Optional Snyk integration:
- Set `SNYK_API_KEY` environment variable for commercial vulnerability database
- Install Snyk CLI: `npm install -g snyk` (optional, scanner works without it)

## Next Phase Readiness

- **Scanner infrastructure complete**: Ready for npm package installer (Plan 03) to use scanners before installation
- **Security validation in place**: NpmScriptAnalyzer will be integrated into installation workflow
- **Test coverage solid**: 33 tests provide regression safety for refactoring
- **No blockers**: Proceed to Plan 03 (NpmPackageInstaller) to use these scanners in Docker-based isolated installation

## Self-Check: PASSED

All created files verified:
- ✅ backend/core/npm_dependency_scanner.py
- ✅ backend/core/npm_script_analyzer.py
- ✅ backend/tests/test_npm_dependency_scanner.py
- ✅ backend/tests/test_npm_script_analyzer.py
- ✅ .planning/phases/36-npm-package-support/36-npm-package-support-02-SUMMARY.md

All commits verified:
- ✅ d994a3d4 (NpmDependencyScanner)
- ✅ 4880a292 (NpmScriptAnalyzer)
- ✅ 5ff9740f (scanner tests)
- ✅ cdcd9db6 (analyzer tests)

Test coverage verified:
- ✅ 33 tests total (15 scanner + 18 analyzer)
- ✅ 100% pass rate

---
*Phase: 36-npm-package-support*
*Plan: 02*
*Completed: 2026-02-19*
