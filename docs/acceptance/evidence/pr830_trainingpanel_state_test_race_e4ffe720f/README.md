# PR830 / PR829 TrainingPanel stale-state test — bounded repair

- Reviewed/repair base: `e4ffe720f14d2fdf2b77147c6fc1dfbf1627fcdc`
- PR830 CI merge commit: `406836f4b1ac6e5586c53c072430372cbb1aa159`
  (merge of `e4ffe720f` into main `0d5132c2e`)
- Repair branch: `codex/pr830-trainingpanel-state-repair-20261110`
- Worktree: `<repair-worktree>`
  (separate from the root graduation worktree and the active 6da UI
  worktree)
- Test-only fix; no product, component, CI, PR, or merge change.

## CI failure

Job `frontend-typecheck` (129853448787) ran the six-file graduation/frontend
selection and failed exactly one test:

- `components/canvas/__tests__/TrainingPanel.test.tsx` →
  `Qualification assessment UI › a stale pending id is not shown as a current
  pending review`
- expected `Review needs refresh`, received `State: Status unavailable`
- hosted result: `1 failed, 135 passed, 136 total`

## Diagnosis: a test race, not a component defect

- The PR830 merge commit's `TrainingPanel.tsx`, `TrainingPanel.test.tsx`,
  `maturity-api.ts`, and `tests/setup.ts` are **byte-identical** to
  `e4ffe720f` (empty diff for each).
- On `e4ffe720f`, the exact six-file selection passed `136/136` locally.
- The same test run **in isolation** fails reliably with `Status unavailable`.
- The component intentionally renders the fallback
  `assessment.state = "unknown"` while `getGraduationReadiness` is in flight
  (`TrainingPanel.tsx` 573–579). The adjacent test
  `deferred readiness shows unknown then the valid state` pins unknown-first.
- The failing test used `await findByTestId('qualification-state')`, which
  resolves on the fallback element, then immediately asserted
  `toHaveTextContent('Review needs refresh')`. Under CI/suite timing the
  readiness promise had not resolved.

## Fix (test-only, semantics preserved)

- The stale-pending test now waits for the settled text:
  `await waitFor(() => expect(getByTestId('qualification-state'))
  .toHaveTextContent('Review needs refresh'))`, keeping the no-pending,
  request-control, and promote-disabled assertions.
- Added `deferred stale readiness shows unknown then the refresh-required
  state`: it asserts the intentional `Status unavailable` first, then after
  resolving readiness asserts `Review needs refresh`, no pending review, the
  request control present, and promote disabled.
- No skip, xfail, test removal, or expected/unknown relaxation.

## Post-fix local gates (existing deps, no installs)

- Single failing test: **pass**
- Full `TrainingPanel.test.tsx`: **33 passed / 33**
- Exact six-file CI selection: **137 passed / 137** (one added control)
- `npx tsc --noEmit --skipLibCheck`: **exit 0**, no diagnostics

## Evidence map

- `diagnosis/race.md` — CI failure, merge identity, race proof, fix
- `source/fix.diff` — test-only diff
- `source/source-hashes.json` — base/after test-file hashes; no product/CI change
- `gates/sixfile-e4-before.log` — exact selection at e4 before the fix (136 pass)
- `gates/single-e4-before-fail.log` — isolated failing test (race reproduction)
- `gates/single-after-pass.log` — isolated test after fix
- `gates/trainingpanel-file-after.log` — full file 33 passed
- `gates/sixfile-after.log` — exact selection 137 passed
- `gates/tsc.log` — tsc command/exit

## Non-claims

No browser campaign, model/provider/send/live DB, new deps, CI edit, PR, or
merge. The hosted CI run is not re-executed here; the fix is validated against
the exact local Jest selection and typecheck. Root owns review, cherry-pick,
and final acceptance.
