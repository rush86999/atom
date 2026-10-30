# Conversation learning — applicability enforcement evidence

Source commit: `50b53bef62242bdb8672dac9fbdc34c0ab7b8fcd`

This directory closes the verifier's applicability blocker. The accepted
local-core tag `local-core-2026-10-30-final` (`da9cc8b12`) is unchanged.

## Applicability contract

- Promotion writes the candidate's context through the existing teaching
  normalizer into the journal entry's **top-level** `context` field; provenance
  remains separately in `details.conversation_learning`.
- `apply_lesson_method` evaluates the journal entry's top-level context before
  arithmetic:
  - wrong customer/qualification → `teaching_context_mismatch`, HTTP 409;
  - missing required context → `teaching_context_required` with the missing
    keys, HTTP 409;
  - equally specific, different applicable methods → HTTP 409
    `teaching_context_conflict`;
  - a more specific applicable lesson governs → HTTP 409
    `teaching_context_superseded`.
- Normal work-time `get_agent_lessons` excludes context-bound lessons unless
  the caller supplies matching task context. `resolve_artifact_teaching` keeps
  its existing context resolver for format/mapping lessons.
- Refusal returns before calculation and does not mutate the candidate, the
  lesson journal or any governing state.

## Verification

| Suite | Result |
|---|---|
| Conversation-learning service/routes | **37 passed** |
| Assignment regressions | **126 passed** |
| Teaching/renderer regressions | **137 passed** |
| Frontend targeted (5 suites) | **35 passed** |
| TypeScript `--noEmit` | clean |
| Production frontend build | success |

Public-route coverage includes matching, wrong and missing customer/
qualification, conflicting applicable teaching, and a close/reopen restart.
Service coverage includes ordinary work-time lesson retrieval with matching,
wrong and missing context, plus restart.

## Full-app browser journey

Production frontend + full app on `127.0.0.1:3130` / `127.0.0.1:8071`:

1. open local thread, select authorized employee;
2. propose a `multiply_sum` lesson scoped to **Customer-A / licensed**;
3. review the resolved `rates.xlsx` binding, confirm and promote;
4. apply with **Customer-B / unlicensed** → visible refusal, HTTP 409;
5. apply with matching **Customer-A / licensed** → **15 USD**;
6. change the governing dataset `v1` → `v2`;
7. reload → candidate `invalidated`, apply HTTP 409;
8. restart backend against the same world;
9. reopen → candidate still `invalidated`, top-level context preserved, raw
   lesson `stale`, apply HTTP 409;
10. no page errors.

Artifacts: `context-journey-part1.json`, `context-journey-part2.json`, three
screenshots, and the two journey scripts.

## Bounds

Only persisted local email-canvas audits are read. No live mailbox access,
token refresh, real send, credential change, source writeback, arbitrary URL
fetch or recursive traversal was performed. Deployment, publication, source
shutdown and additional real sends remain deferred.
