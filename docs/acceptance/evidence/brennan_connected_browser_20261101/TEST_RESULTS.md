# Connected repair batch — executed evidence

Executed source: `97c43c7e7dcc61e517095f91595942241ba2ea60`
(branch `codex/brennan-joint-review-20261101`, clean tree).
Evidence commit: `8b03e8083` (this directory only; it was not the served code).

Interpreter: `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`
(the earlier 3.11 venv was no longer present).

## Browser

Command:

```bash
BRENNAN_BROWSER_OUT=/private/tmp/brennan-browser-final3 \
  node scripts/acceptance/brennan_connected_browser.cjs
```

Result: **24/24 checks passed**.

Covered:

- production registered WorkDrive action and CSV parser (provider service faked only);
- qualification wait, leave, real backend restart (old/new PID and instance recorded);
- serving code identity equals the declared candidate source (`97c43c7e7dcc`), clean tree;
- source v1 -> v2, read branch invalidation;
- v1 calculation **362.50** retained in `prior_results`;
- corrected calculation **376.75**, lines/evidence identify v2 and its SHA-256;
- complete estimate readback **376.75**;
- Outlook draft **376.75**, zero send attempts;
- duplicate resume from two pages is a no-op;
- cancellation refuses a late correlated response;
- provider acceptance followed by lost readback is uncertain, survives restart
  without a second create, reconciles the original object, and only then
  releases the dependent draft.

## Focused tests

| Suite | Command result |
|---|---|
| Joint core | **281 passed** |
| Data-transfer boundary, tracked (79/80/81, partial, oversized, exact limit, backslashes, nested, restart) | **32 passed** |
| Consolidated batch (all focused files below plus campaign/real-effect) | **309 passed** |
| Agent 2 focused provider/accounting/readback/bookkeeping | **279 passed** |
| Agent 1 required assignment suite | **175 passed** |

The independent verifier's focused run (14 controls, including its own
transfer probe) is recorded separately; this checkout does not depend on the
external probe file.

Known pre-existing baseline failures: 4 turn-count/LLM-orchestration tests in
`tests/test_task_lifecycle.py`; they reproduce at baseline `acd86a2aa` and are
not counted as passes.

## Boundaries

- No live Zoho/Microsoft lookup, refresh, write or send.
- The acceptance server is standalone; this evidence does not claim full-app
  authentication, profiles or navigation.
- No user-authored canvas/runtime claim is made here.
