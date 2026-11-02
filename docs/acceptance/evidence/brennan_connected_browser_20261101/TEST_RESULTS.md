# Connected repair batch — executed evidence

Executed source: `6431bcb7857fd43dffc1ed685fffe47044669e5c`
(branch `codex/brennan-joint-review-20261101`, clean tree).
Browser artifact commit: `f8a55adf9` (artifacts/logs only; it was not the
served code). This manifest commit is docs-only and was not served either.

Interpreter: `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`
(the earlier 3.11 venv was no longer present).

## Browser

Command:

```bash
BRENNAN_BROWSER_OUT=/private/tmp/brennan-browser-evidence-25 \
  node scripts/acceptance/brennan_connected_browser.cjs
```

Result: **25/25 checks passed**.

Covered:

- occupied acceptance port refused before spawn;
- production registered WorkDrive action and CSV parser (provider service faked only);
- qualification wait, leave, real backend restart (old/new PID and instance recorded);
- serving code identity equals the declared candidate source (`6431bcb7857f`), clean tree;
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

The scratch screenshot paths in `checks.json` are the paths used during
execution; the same images and backend logs are committed in this directory.

## Focused tests

| Suite | Result |
|---|---|
| Joint core | **284 passed** |
| Data-transfer boundary, tracked (79/80/81, partial, oversized, exact limit, backslashes, nested, restart) | **32 passed** |
| Consolidated batch (all tracked focused files plus campaign/real-effect) | **312 passed** |
| Agent 2 focused provider/accounting/readback/bookkeeping | **279 passed** |
| Agent 1 required assignment suite | **178 passed** |

The independent verifier's focused run (including its own transfer probe) is
recorded separately; this checkout does not depend on the external probe file.

Known pre-existing baseline failures: 4 turn-count/LLM-orchestration tests in
`tests/test_task_lifecycle.py`; they reproduce at baseline `acd86a2aa` and are
not counted as passes.

## Scenario verdicts

| Scenario | Verdict |
|---|---|
| Unsupported pricing semantics (caps, fixed, tiers, formulas, unknown fields) | Pass — public route 422 before arithmetic; no action runs |
| Persisted serialized byte budget | Pass — exact limit accepted; limit+1, escapes, controls, multibyte and nested receipts refused |
| Read overflow / descendant blocking | Pass — typed failure; no descendant effect |
| Post-dispatch mutation overflow | Pass — uncertain with original operation/remote identity; restart adds no effect; reconciliation settles it |
| Complete row population and provenance | Pass — 79/80/81 rows and byte-exact base64; 501-row partial source blocks calculation; oversized inline content refuses; restart persists |
| Production WorkDrive browser path | Pass — real registered action/parser/executor; only provider transport faked |
| OneDrive XLSX public assignment route | Pass — production parser; receipt version/hash/coverage |
| Connected browser journey | Pass — 25/25, v1 362.50 prior, v2 376.75, full readback, draft, zero sends, reload |
| Recovery siblings | Pass — duplicate resume no-op; late correlated response refused; lost readback uncertain across restart; no second create; reconciliation releases draft |
| Registered bookkeeping controls | Pass — happy path, missing/ambiguous vendor, closed period, changed payload, incomplete sweep, incomplete/mismatched readback |
| Missing / ambiguous qualification via public route | Pass — scope gap resolves 90.00; unrecognized conflict answer buys no arithmetic and re-asks |
| Non-sales expense reconciliation portability | Pass — same public route, miles/nights, 260.40 USD, document artifact |
| Occupied acceptance port | Pass — runner refuses to reuse an unknown server |

## Boundaries

- No live Zoho/Microsoft lookup, refresh, write or send.
- The acceptance server is standalone; this evidence does not claim full-app
  authentication, profiles or navigation.
- No user-authored canvas/runtime claim is made here.
- Historical 111/123 scope is unchanged.
