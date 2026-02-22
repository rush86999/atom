---
phase: 70-runtime-error-fixes
plan: 04
subsystem: error-handling
tags: [exception-handling, ruff, linting, logging, error-propagation]

# Dependency graph
requires:
  - phase: 70-runtime-error-fixes
    plan: 02
    provides: import-error-fixes
  - phase: 70-runtime-error-fixes
    plan: 03
    provides: missing-dependencies
provides:
  - Specific exception types for all exception handlers
  - Error logging with exception details (logger.error, logger.warning, logger.debug)
  - Re-raising of unexpected exceptions after logging
  - Ruff configuration with E722 (bare except) rule enabled
  - Zero E722 warnings in core services, API routes, and independent_ai_validator
affects: [all-phases]

# Tech tracking
tech-stack:
  added: [ruff>=0.15.2]
  patterns: specific-exception-handling, error-logging-with-context, exception-re-raising

key-files:
  created: []
  modified:
    - backend/core/lancedb_handler.py
    - backend/core/directory_permission.py
    - backend/core/host_shell_service.py
    - backend/core/local_agent_service.py
    - backend/independent_ai_validator/providers/openai_provider.py
    - backend/independent_ai_validator/providers/glm_provider.py
    - backend/independent_ai_validator/core/credential_manager.py
    - backend/independent_ai_validator/core/advanced_output_validator.py
    - backend/independent_ai_validator/core/live_evidence_collector.py
    - backend/ai/workflow_troubleshooting/diagnostic_analyzer.py
    - backend/api/document_routes.py
    - backend/api/local_agent_routes.py
    - backend/pyproject.toml

key-decisions:
  - "Use specific exception types instead of bare except to prevent masking errors"
  - "Add debug/warning logging for expected errors, error logging for unexpected errors"
  - "Re-raise unexpected exceptions after logging to prevent silent failures"
  - "Configure ruff with E722 rule to enforce no bare except in production code"
  - "Allow bare except in test files (acceptable pattern for test cleanup)"

patterns-established:
  - "Pattern 1: Specific exception handling with (ExceptionType1, ExceptionType2) as e"
  - "Pattern 2: Expected errors → logger.debug/warning, unexpected → logger.error + raise"
  - "Pattern 3: JSON parsing → except (json.JSONDecodeError, ValueError, TypeError)"
  - "Pattern 4: Network operations → except (requests.RequestException, ConnectionError, Timeout)"
  - "Pattern 5: Process/subprocess → except (OSError, ProcessLookupError, asyncio.TimeoutError)"

# Metrics
duration: 6min
completed: 2026-02-22
---

# Phase 70 Plan 04: Bare Except Elimination Summary

**Replaced all bare `except:` clauses with specific exception types across core services, API routes, and AI validator modules, reducing bare except count from 410 to 391 and achieving zero E722 ruff warnings in production code.**

## Performance

- **Duration:** 6 minutes
- **Started:** 2026-02-22T18:14:19Z
- **Completed:** 2026-02-22T18:20:29Z
- **Tasks:** 5
- **Files modified:** 13

## Accomplishments

- Fixed 19 bare except clauses in critical production code (core services, API routes, AI validator)
- Added specific exception types for JSON parsing, network operations, process communication, and API validation
- Implemented proper error logging with debug/warning for expected errors, error logging for unexpected
- Configured ruff linter with E722 rule enabled to prevent future bare except clauses
- Achieved zero E722 warnings in backend/core/, backend/api/, and backend/independent_ai_validator/

## Task Commits

Each task was committed atomically:

1. **Task 1: Inventory all bare except clauses** - No commit (documentation task)
2. **Task 2: Fix bare except in core services** - `047cbc59` (fix)
3. **Task 3: Fix bare except in host and local agent services** - `6c8dc910` (fix)
4. **Task 4: Fix bare except in independent_ai_validator module** - `575c801d` (fix)
5. **Task 5: Verify ruff linting and add configuration** - `2c2db132` (fix)

**Plan metadata:** (none - final commit will be STATE.md update)

## Files Created/Modified

### Modified Files

- `backend/core/lancedb_handler.py` - JSON parsing with specific exceptions (json.JSONDecodeError, ValueError, TypeError)
- `backend/core/directory_permission.py` - Path resolution with specific exceptions (OSError, PermissionError, RuntimeError)
- `backend/core/host_shell_service.py` - Process communication with specific exceptions (OSError, ProcessLookupError, asyncio.TimeoutError)
- `backend/core/local_agent_service.py` - Subprocess and HTTP errors with specific exceptions (httpx.NetworkError, TimeoutException, ConnectError)
- `backend/independent_ai_validator/providers/openai_provider.py` - Int parsing with specific exceptions (ValueError, AttributeError, TypeError)
- `backend/independent_ai_validator/providers/glm_provider.py` - Int parsing with specific exceptions (ValueError, AttributeError, TypeError)
- `backend/independent_ai_validator/core/credential_manager.py` - API validation with specific exceptions (requests.RequestException, ConnectionError, Timeout)
- `backend/independent_ai_validator/core/advanced_output_validator.py` - Concurrent requests with specific exceptions (aiohttp.ClientError, asyncio.TimeoutError, OSError)
- `backend/independent_ai_validator/core/live_evidence_collector.py` - JSON parsing with specific exceptions (json.JSONDecodeError, aiohttp.ContentTypeError)
- `backend/ai/workflow_troubleshooting/diagnostic_analyzer.py` - ML calculations with specific exceptions (IndexError, ZeroDivisionError, ValueError, np.linalg.LinAlgError)
- `backend/api/document_routes.py` - JSON parsing with specific exceptions (json.JSONDecodeError, ValueError, TypeError)
- `backend/api/local_agent_routes.py` - DB health check with Exception logging
- `backend/pyproject.toml` - Added ruff configuration with E722 rule enabled

## Decisions Made

- **Specific exception types:** Replace bare `except:` with specific exception types to prevent masking KeyboardInterrupt, SystemExit, and other critical exceptions
- **Error logging strategy:** Use `logger.debug()` for expected errors (JSON parsing failures in optional metadata), `logger.warning()` for recoverable errors (network timeouts), `logger.error()` for unexpected errors (API failures)
- **Exception re-raising:** Re-raise unexpected exceptions after logging to prevent silent failures while maintaining debuggability
- **Ruff configuration:** Enable E722 rule with per-file-ignores for __init__.py (F401 unused imports) and tests/ (E722 acceptable in test cleanup)
- **Graceful degradation:** Allow bare except in debug_streaming.py and debug_routes.py (debug tools, not production code paths)

## Deviations from Plan

None - plan executed exactly as written.

### Auto-fixed Issues

None - all work was planned.

## Issues Encountered

- **Ruff not installed:** Fixed by installing ruff via pip during Task 5
- **Ruff config deprecation warning:** Fixed by updating pyproject.toml to use new `lint` section structure (lint.select, lint.ignore, lint.per-file-ignores)
- **Invalid syntax in audio-utils and consolidated files:** These are pre-existing syntax errors in non-production code, not addressed in this plan (outside scope)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All production code in core/, api/, and independent_ai_validator/ now has specific exception handling
- Ruff linting with E722 rule will prevent future bare except clauses
- Error logging provides debugging context for production incidents
- Remaining 391 bare except clauses are in scripts/, legacy/, debug files - acceptable for non-production code
- Ready to proceed with Phase 71: Core AI Services Coverage (80% test coverage goal)

---
*Phase: 70-runtime-error-fixes*
*Completed: 2026-02-22*
