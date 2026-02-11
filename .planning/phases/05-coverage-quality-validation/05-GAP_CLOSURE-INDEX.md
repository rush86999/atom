# Phase 05 Gap Closure Plans

**Created:** 2026-02-11
**Status:** Ready for execution
**Total Plans:** 6

## Overview

Phase 05 execution completed with 8/8 plans, but verification found 6 gaps with only 3/7 must_haves verified (43%). These gap closure plans address the identified issues to achieve the 80% coverage target across all domains.

## Gap Closure Plans

| Plan | Domain | Wave | Tasks | Gap Addressed |
|------|--------|------|-------|---------------|
| [05-GAP_CLOSURE-PLAN-governance.md](./05-GAP_CLOSURE-PLAN-governance.md) | Governance | 1 | 3 | Database setup, integration tests for action execution and graduation exams |
| [05-GAP_CLOSURE-PLAN-security.md](./05-GAP_CLOSURE-PLAN-security.md) | Security | 1 | 3 | Auth endpoint paths, token cleanup, async refresher mocking |
| [05-GAP_CLOSURE-PLAN-episodes.md](./05-GAP_CLOSURE-PLAN-episodes.md) | Episodic Memory | 1 | 4 | LanceDB integration, segmentation/lifecycle enhancement, graduation validation |
| [05-GAP_CLOSURE-PLAN-mobile.md](./05-GAP_CLOSURE-PLAN-mobile.md) | Mobile | 2 | 3 | NotificationService destructuring, DeviceContext tests, missing tests |
| [05-GAP_CLOSURE-PLAN-desktop.md](./05-GAP_CLOSURE-PLAN-desktop.md) | Desktop | 2 | 4 | WebSocket reconnection, error paths, network timeouts, token refresh |
| [05-GAP_CLOSURE-PLAN-backend.md](./05-GAP_CLOSURE-PLAN-backend.md) | Backend Overall | 2 | 3 | Coverage re-measurement after all tests pass |

## Wave Structure

**Wave 1** (Can run in parallel):
- GAP_CLOSURE-01: Governance database and integration tests
- GAP_CLOSURE-02: Security endpoint and token fixes
- GAP_CLOSURE-03: Episodic memory LanceDB integration

**Wave 2** (After Wave 1 completes):
- GAP_CLOSURE-04: Mobile test fixes
- GAP_CLOSURE-05: Desktop test additions
- GAP_CLOSURE-06: Backend coverage re-measurement

## Gap Summary

| Domain | Current Coverage | Target | Gap | Plan |
|--------|------------------|--------|-----|------|
| Governance | 14-83% | 80% | DB issues, integration gaps | GAP_CLOSURE-01 |
| Security | 0-91% | 80% | Missing endpoints, token issues | GAP_CLOSURE-02 |
| Episodes | ~40% | 80% | LanceDB integration | GAP_CLOSURE-03 |
| Backend Overall | ~15.57% | 80% | Tests not passing | GAP_CLOSURE-06 |
| Mobile | 32.09% | 80% | 67 failing tests | GAP_CLOSURE-04 |
| Desktop | 74% | 80% | WebSocket, error paths | GAP_CLOSURE-05 |

## Execution

Run gap closure plans:

```bash
/gsd:execute-phase 05-coverage-quality-validation --gaps-only
```

This will execute only the GAP_CLOSURE plans in wave order.
