# Connected repair batch — executed evidence

Executed source: `6431bcb7857fd43dffc1ed685fffe47044669e5c`
(branch tip `codex/brennan-joint-review-20261101`, clean checkout at
`/private/tmp/atom-brennan-clean`).
Evidence is docs-only after the executed source head; it was not the served
code.

Interpreter: `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`
(the earlier 3.11 venv was no longer present).

## Browser

Command shape:

```bash
BRENNAN_REQUIRE_CLEAN=1 \
BRENNAN_UI_BASE=http://127.0.0.1:3013 \
BRENNAN_API_BASE=http://127.0.0.1:8093 \
BRENNAN_BROWSER_WORLD=<scratch world> \
BRENNAN_BROWSER_OUT=<evidence dir> \
  node scripts/acceptance/brennan_connected_browser.cjs
```

Result: **25/25 checks passed**.

Covered:

- occupied acceptance port refused, not reused;
- production registered WorkDrive action and CSV parser (provider service faked only);
- qualification wait, leave, real backend restart (old/new PID and instance recorded);
- serving code identity equals the declared candidate source (`6431bcb7857f`), clean tree;
- source v1 -> v2, read branch invalidation;
- v1 calculation **362.50** retained in `prior_results`;
- corrected calculation **376.75**, lines/evidence identify v2 and its SHA-256;
- complete estimate readback **376.75**;
- Outlook draft **376.75**, zero send attempts (explicit counter);
- duplicate resume from two pages is a no-op;
- cancellation refuses a late correlated response;
- provider acceptance followed by lost readback is uncertain, survives restart
  without a second create, reconciles the original object, and only then
  releases the dependent draft.

## Focused tests

| Suite | Command result |
|---|---|
| Joint core | **284 passed** |
| Tracked data-transfer boundary (79/80/81, partial, oversized, exact limit, backslashes, nested, restart) | **32 passed** |
| Consolidated batch (all focused files below plus campaign/real-effect) | **312 passed** |
| Agent 2 focused provider/accounting/readback/bookkeeping | **279 passed** |
| Agent 1 required assignment suite | **178 passed** |

Known pre-existing baseline failures: 4 turn-count/LLM-orchestration tests in
`tests/test_task_lifecycle.py`; they reproduce at baseline `acd86a2aa` and are
not counted as passes.

## Boundaries

- No live Zoho/Microsoft lookup, refresh, write or send.
- The acceptance server is standalone; this evidence does not claim full-app
  authentication, profiles or navigation.
- No user-authored canvas/runtime claim is made here.
- Earlier 24-check and dirty development attempts are preserved separately and
  are not this final acceptance evidence.
