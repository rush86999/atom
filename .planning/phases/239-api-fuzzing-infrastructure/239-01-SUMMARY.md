---
phase: 239-api-fuzzing-infrastructure
plan: 01
subsystem: api-fuzzing-campaign-management
tags: [fuzzing, atheris, campaign-orchestration, crash-deduplication, bug-filing]

# Dependency graph
requires:
  - phase: 236-cross-platform-and-stress-testing
    plan: 09
    provides: BugFilingService for automated GitHub issue filing
provides:
  - FuzzingOrchestrator service for campaign lifecycle management (start, stop, monitor)
  - CrashDeduplicator for SHA256-based crash deduplication using error signatures
  - Corpus/crashes directory structure for artifact storage
  - Integration with BugFilingService for automated bug filing
affects: [api-fuzzing, bug-discovery, crash-analysis, automated-testing]

# Tech tracking
tech-stack:
  added: [subprocess.Popen, signal.SIGTERM/SIGKILL, hashlib.sha256, stack trace extraction, pytest subprocess management]
  patterns:
    - "Campaign lifecycle management with subprocess.Popen for pytest execution"
    - "Graceful shutdown with SIGTERM (10s timeout) followed by SIGKILL"
    - "SHA256 hashing of normalized stack traces for crash deduplication"
    - "Environment variable injection (FUZZ_CAMPAIGN_ID, FUZZ_CRASH_DIR, FUZZ_ITERATIONS)"
    - "BugFilingService integration for automated GitHub issue filing"
    - "Timestamped crash directories per campaign for artifact isolation"

key-files:
  created:
    - backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py (507 lines, 5 core methods)
    - backend/tests/fuzzing/campaigns/crash_deduplicator.py (202 lines, 5 core methods)
    - backend/tests/fuzzing/campaigns/__init__.py (package exports)
    - backend/tests/fuzzing/campaigns/corpus/README.md (corpus management guide)
    - backend/tests/fuzzing/campaigns/crashes/README.md (crash artifacts guide)
    - backend/tests/fuzzing/campaigns/.gitignore (exclude crash artifacts)
  modified: []

key-decisions:
  - "Integrated fuzzing campaigns into existing tests/fuzzing/ directory (INFRA-01 requirement)"
  - "SHA256 hashing of normalized stack traces (line numbers removed) for stable deduplication"
  - "Graceful subprocess shutdown with SIGTERM (10s timeout) before SIGKILL"
  - "Timestamped campaign IDs for artifact isolation: {endpoint}_{timestamp}"
  - "Environment variable injection for campaign context (FUZZ_CAMPAIGN_ID, FUZZ_CRASH_DIR)"
  - "Corpus re-seeding with subdirectories (auth, agent, workflow) for faster coverage"
  - "Crash artifacts excluded from git via .gitignore (large binary files)"

patterns-established:
  - "Pattern: Campaign lifecycle management with subprocess tracking"
  - "Pattern: Crash deduplication using error signature hashing"
  - "Pattern: Automated bug filing via BugFilingService integration"
  - "Pattern: Corpus re-seeding for faster coverage discovery"
  - "Pattern: Timestamped artifact directories per campaign"

# Metrics
duration: ~3 minutes (180 seconds)
completed: 2026-03-24
---

# Phase 239: API Fuzzing Infrastructure - Plan 01 Summary

**FuzzingOrchestrator service and CrashDeduplicator for centralized campaign management**

## Performance

- **Duration:** ~3 minutes (180 seconds)
- **Started:** 2026-03-24T23:22:02Z
- **Completed:** 2026-03-24T23:25:02Z
- **Tasks:** 4
- **Files created:** 8
- **Files modified:** 0

## Accomplishments

- **FuzzingOrchestrator service created** (507 lines) with campaign lifecycle management
  - start_campaign(): Start pytest subprocess with environment variables
  - stop_campaign(): Graceful shutdown with SIGTERM/SIGKILL
  - monitor_campaign(): Read crash directory for statistics
  - file_bugs_for_crashes(): Integrate with BugFilingService from Phase 236
  - run_campaign_with_bug_filing(): Full campaign orchestration
- **CrashDeduplicator created** (202 lines) with SHA256-based deduplication
  - deduplicate_crashes(): Group crashes by error signature hash
  - _extract_stack_trace(): Extract Python traceback from crash logs
  - _generate_signature_hash(): Create SHA256 hash for deduplication
  - get_unique_crashes(): Get representative crash per signature
  - get_signature_summary(): Get crash summary sorted by count
- **Package structure created** with exports and convenience functions
  - __init__.py exports FuzzingOrchestrator, CrashDeduplicator
  - Package-level functions: start_campaign, stop_campaign, monitor_campaign
- **Corpus/crashes directories** with README.md documentation
  - corpus/ subdirectories: auth, agent, workflow for re-seeding
  - crashes/ timestamped per campaign: *.input (crashing input), *.log (stack trace)
  - .gitignore excludes crash artifacts from git

## Task Commits

Each task was committed atomically:

1. **Task 1: FuzzingOrchestrator service** - `c9f82fab8` (feat)
2. **Task 2: CrashDeduplicator** - `5c5acbf6b` (feat)
3. **Task 3/4: Package structure and directories** - `94aa7d49a` (feat)

**Plan metadata:** 3 tasks, 3 commits, 180 seconds execution time

## Files Created

### Created (8 files, 944 total lines)

**`backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py`** (507 lines)
- **FuzzingOrchestrator class:**
  - __init__(github_token, github_repository): Initialize with BugFilingService
  - start_campaign(target_endpoint, test_file, duration_seconds, iterations): Start pytest subprocess
  - stop_campaign(campaign_id): Send SIGTERM (10s timeout) then SIGKILL
  - monitor_campaign(campaign_id): Read crash directory for statistics
  - file_bugs_for_crashes(target_endpoint, crashes_by_signature): Integrate with BugFilingService
  - run_campaign_with_bug_filing(target_endpoint, test_file, duration_seconds): Full orchestration
- **Convenience functions:** start_campaign, stop_campaign, monitor_campaign, file_bugs_for_crashes
- **Subprocess management:** Popen with environment variables (FUZZ_CAMPAIGN_ID, FUZZ_CRASH_DIR, FUZZ_ITERATIONS)
- **Campaign tracking:** Dict[campaign_id, subprocess.Popen] for running campaigns
- **Directory creation:** corpus_dir, crash_dir with pathlib.Path

**`backend/tests/fuzzing/campaigns/crash_deduplicator.py`** (202 lines)
- **CrashDeduplicator class:**
  - deduplicate_crashes(crash_dir): Group crashes by SHA256 hash of error signature
  - _extract_stack_trace(crash_log_file): Extract Python traceback from crash log
  - _generate_signature_hash(stack_trace): Create SHA256 hash (normalized, line numbers removed)
  - get_unique_crashes(crashes_by_signature): Get representative crash per signature
  - get_signature_summary(crashes_by_signature): Get summary sorted by crash count
- **Stack trace normalization:** Remove line numbers (line N, :N) for stable hashing
- **Fallback behavior:** Use filename hash if log extraction fails
- **Convenience function:** deduplicate_crashes(crash_dir)

**`backend/tests/fuzzing/campaigns/__init__.py`** (47 lines)
- **Package exports:** FuzzingOrchestrator, CrashDeduplicator
- **Convenience functions:** start_campaign, stop_campaign, monitor_campaign, file_bugs_for_crashes
- **Comprehensive docstring:** Campaign lifecycle usage example

**`backend/tests/fuzzing/campaigns/corpus/README.md`** (62 lines)
- **Purpose:** Interesting inputs discovered during fuzzing for re-seeding
- **Structure:** auth/, agent/, workflow/ subdirectories
- **Re-seeding:** Atheris automatically reads corpus for seed inputs
- **Corpus quality:** Edge cases, boundary conditions, security-relevant inputs
- **File format:** Binary files containing raw input data

**`backend/tests/fuzzing/campaigns/crashes/README.md`** (108 lines)
- **Purpose:** Crash artifacts discovered during fuzzing (crashing input + stack trace)
- **Structure:** {campaign_id}/ with *.input and *.log file pairs
- **Analysis:** Manual (xxd, cat) and automated (CrashDeduplicator)
- **Reproduction:** Read crash input and pass to test function
- **Bug filing:** Automated via BugFilingService integration
- **Cleanup:** Periodic removal of crash artifacts older than 30 days

**`backend/tests/fuzzing/campaigns/.gitignore`** (14 lines)
- **Ignore:** *.input, *.log files (crash artifacts)
- **Ignore:** crashes/*/ directories (timestamped per campaign)
- **Keep:** README.md, .gitkeep files

**`backend/tests/fuzzing/campaigns/corpus/.gitkeep`** (0 lines)
- **Purpose:** Ensure corpus/ directory is tracked by git

**`backend/tests/fuzzing/campaigns/crashes/.gitkeep`** (0 lines)
- **Purpose:** Ensure crashes/ directory is tracked by git

## Implementation Details

### Campaign Lifecycle Management

**start_campaign():**
- Generate campaign_id: `{endpoint}_{timestamp}` (e.g., "api-v1-agents_2026-03-24T23-22-02Z")
- Create campaign_crash_dir: `crashes/{campaign_id}/`
- Set environment variables:
  - FUZZ_CAMPAIGN_ID: Campaign identifier
  - FUZZ_CRASH_DIR: Path to crash artifacts directory
  - FUZZ_ITERATIONS: Number of fuzzing iterations
- Start subprocess: `pytest {test_file} -v -m fuzzing`
- Track process: `self.running_campaigns[campaign_id] = subprocess.Popen`
- Return: campaign_id, status, pid, target_endpoint, duration_seconds, iterations, crash_dir

**stop_campaign():**
- Get process from `self.running_campaigns[campaign_id]`
- Send SIGTERM for graceful shutdown
- Wait up to 10 seconds for process to terminate
- Send SIGKILL if still running after timeout
- Remove from `self.running_campaigns`
- Return: campaign_id, status

**monitor_campaign():**
- List `campaign_crash_dir.glob("*.input")` for crash count
- Extract execution count from crash logs (parse "Executions: 1234")
- Estimate executions if not found: `crash_count * 100`
- Check if process still running (poll() for None)
- Return: campaign_id, status, executions, crashes, crash_dir

### Crash Deduplication

**deduplicate_crashes():**
- Iterate `crash_dir.glob("*.input")` for crash files
- Read crash log from `{crash_file}.log`
- Extract stack trace using `_extract_stack_trace()`
- Generate SHA256 hash using `_generate_signature_hash()`
- Group crashes: `Dict[signature_hash, List[Path]]`
- Return: crashes_by_signature dict

**_extract_stack_trace():**
- Find "Traceback" line (start of stack trace)
- Extract lines until non-indented line (end of traceback)
- Include error message line (contains ":")
- Limit to 2000 characters to prevent hash collisions
- Fallback: Entire log if no traceback found

**_generate_signature_hash():**
- Normalize stack trace: Remove line numbers (line N, :N)
- Generate SHA256 hash: `hashlib.sha256(normalized_trace.encode()).hexdigest()`
- Return: signature_hash as hex digest

### BugFilingService Integration

**file_bugs_for_crashes():**
- Import BugFilingService from `tests.bug_discovery.bug_filing_service`
- For each (signature_hash, crash_files) in crashes_by_signature:
  - Read crash_input (binary) from crash_files[0]
  - Read crash_log from crash_log_file
  - Call bug_filing_service.file_bug() with metadata:
    - test_name: `fuzzing_{target_endpoint}`
    - error_message: `Crash in {target_endpoint}: {crash_log[:200]}`
    - metadata: {
        test_type: "fuzzing",
        target_endpoint: target_endpoint,
        crash_input: crash_input.hex()[:1000],
        crash_log: crash_log[:500],
        signature_hash: signature_hash,
        related_crashes: len(crash_files)
      }
  - Collect bug_result: {status, issue_url, issue_number}
- Return: filed_bugs list

**run_campaign_with_bug_filing():**
- Start campaign: `start_campaign(target_endpoint, test_file, duration_seconds)`
- Wait for duration: `time.sleep(duration_seconds)`
- Stop campaign: `stop_campaign(campaign_id)`
- Deduplicate crashes: `CrashDeduplicator.deduplicate_crashes(campaign_crash_dir)`
- File bugs: `file_bugs_for_crashes(target_endpoint, crashes_by_signature)`
- Return: {campaign_id, executions, crashes, unique_crashes, bugs_filed, bug_results, status}

## Verification Results

All verification steps passed:

1. ✅ **Import verification** - `from tests.fuzzing.campaigns import FuzzingOrchestrator, CrashDeduplicator`
2. ✅ **Campaign lifecycle verification** - All 5 methods exist (start, stop, monitor, file_bugs, run_campaign)
3. ✅ **Deduplication verification** - All 3 methods exist (deduplicate_crashes, _extract_stack_trace, _generate_signature_hash)
4. ✅ **Directory structure verification** - corpus/auth, corpus/agent, corpus/workflow created
5. ✅ **BugFilingService integration** - BugFilingService import verified in file_bugs_for_crashes source

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
- FuzzingOrchestrator service with 507 lines (exceeds 200 minimum)
- CrashDeduplicator with 202 lines (exceeds 80 minimum)
- Package structure with __init__.py exports
- Corpus/crashes directories with README.md documentation
- .gitignore excludes crash artifacts

## Issues Encountered

**Issue 1: Python 2.7 default system Python**
- **Symptom:** ImportError: No module named campaigns.fuzzing_orchestrator
- **Root Cause:** System Python is Python 2.7, but code uses Python 3 type hints
- **Fix:** Use `python3` command for all verification commands
- **Impact:** Fixed by using `python3` instead of `python`

## Next Steps

**Ready for:**
- Phase 239 Plan 02: Create fuzzing harnesses for auth endpoints
- Phase 239 Plan 03: Create fuzzing harnesses for agent endpoints
- Phase 239 Plan 04: Create fuzzing harnesses for workflow endpoints

**Campaign Management Infrastructure Established:**
- FuzzingOrchestrator for campaign lifecycle (start, stop, monitor)
- CrashDeduplicator for SHA256-based crash deduplication
- BugFilingService integration for automated bug filing
- Corpus/crashes directory structure with README documentation
- Package exports for easy import

## Self-Check: PASSED

All files created:
- ✅ backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py (507 lines)
- ✅ backend/tests/fuzzing/campaigns/crash_deduplicator.py (202 lines)
- ✅ backend/tests/fuzzing/campaigns/__init__.py (47 lines)
- ✅ backend/tests/fuzzing/campaigns/corpus/README.md (62 lines)
- ✅ backend/tests/fuzzing/campaigns/crashes/README.md (108 lines)
- ✅ backend/tests/fuzzing/campaigns/.gitignore (14 lines)
- ✅ backend/tests/fuzzing/campaigns/corpus/.gitkeep (0 lines)
- ✅ backend/tests/fuzzing/campaigns/crashes/.gitkeep (0 lines)

All commits exist:
- ✅ c9f82fab8 - FuzzingOrchestrator service (507 lines)
- ✅ 5c5acbf6b - CrashDeduplicator (202 lines)
- ✅ 94aa7d49a - Package structure and directories

All verifications passed:
- ✅ Import verification: FuzzingOrchestrator, CrashDeduplicator
- ✅ Campaign lifecycle: start_campaign, stop_campaign, monitor_campaign, file_bugs_for_crashes, run_campaign_with_bug_filing
- ✅ Deduplication: deduplicate_crashes, _extract_stack_trace, _generate_signature_hash
- ✅ Directory structure: corpus/auth, corpus/agent, corpus/workflow
- ✅ BugFilingService integration: Verified in source code

---

*Phase: 239-api-fuzzing-infrastructure*
*Plan: 01*
*Completed: 2026-03-24*
