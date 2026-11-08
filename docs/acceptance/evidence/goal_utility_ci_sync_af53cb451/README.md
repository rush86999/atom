# Goal utility detail CI synchronization — af53cb451

Executed source: `af53cb451` (based on main `8ded00232`).

## Finding

Hosted PR753 (`bd209add6`) and docs PR755 (`755e081`) both failed exactly one
Jest case:

`tests/pages/goal-runs/detail.test.tsx`
→ `Goal utility target (GOAL-02) › supervisor sets the existing target and sees the ranking after reload`
→ `Unable to find an element by: [data-testid="goal-utility-metric"]`
→ 24 passed, 1 failed.

This is a test synchronization race, not a product authority/utility defect.
The page renders `goal-utility-no-target` before the run loads and before the
first `getGoalUtility` settles. The test waited only for that placeholder; on
a slower CI microtask order the await returned on the pre-load placeholder,
then the utility loading render removed the editor, so the next synchronous
`getByTestId("goal-utility-metric")` failed.

Deterministic reproduction: an exact copy of the test with the first
`getGoalUtility` response held pending reproduces the same failure
(`deterministic-race-old-pattern-fail.log`).

## Fix

Test-only synchronization. The supervisor test now uses a controlled deferred
first response:

1. wait for the real first `getGoalUtility` call;
2. observe `goal-utility-loading`;
3. resolve the first response;
4. wait for the settled `goal-utility-no-target`;
5. assert the editor exists, then interact.

No product code, role default, capability gate, error withholding, assertion,
timeout or sleep changed. Member read-only behavior, supervisor mutation, and
advisory-only target/ranking remain intact.

## Evidence

| Case | Result | Raw |
|---|---|---|
| Hosted PR753 at bd209 | 24 passed / 1 failed | `hosted-753-bd209-failure.log` |
| Hosted PR755 at 755e081 | 24 passed / 1 failed | `hosted-755-e081-failure.log` |
| Deterministic held-response reproduction | 1 failed (same test) | `deterministic-race-old-pattern-fail.log` |
| Local detail suite before (normal mocks) | 25 passed | `local-detail-25-before-pass.log` |
| Local detail suite after | 25 passed | `local-detail-25-after-pass.log` |
| Goal-run detail + list matrix after | 39 passed | `local-goalrun-39-pass.log` |
| TypeScript | `tsc --noEmit` exit 0 | `tsc-noemit.log` |

Environment seam: existing x64 `/usr/local/bin/node`, Jest
`--runInBand --watchman=false --no-cache`, and the pre-existing
`frontend-nextjs/node_modules` symlink from
`/private/tmp/atom-browser-capture-frozen-20261107/frontend-nextjs/node_modules`.
No installs, npx fetch, browser, model/provider, live DB, deploy or force push.

`RUNS.json` records exact commands/exits. `MANIFEST.json` is checked by
`scripts/acceptance/evidence_git_check.py --strict` against `executed_source`.
