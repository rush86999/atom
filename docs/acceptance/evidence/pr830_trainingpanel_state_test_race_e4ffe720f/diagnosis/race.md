# PR830 TrainingPanel state test — race diagnosis

## Observed CI failure

Hosted PR830 merge job `frontend-typecheck` (job 129853448787) ran the exact
selection:

```
npx jest lib/__tests__/api/maturity-api.test.ts tests/pages/approvals-page.test.tsx \
  components/canvas/__tests__/TrainingPanel.test.tsx lib/__tests__/api-interceptors.test.ts \
  components/Agents/__tests__/AgentMaturityGuide.test.tsx \
  components/Agents/__tests__/SelfDirectedPathwayCard.test.tsx \
  --runInBand --no-coverage --watchman=false
```

One test failed:

- `Qualification assessment UI › a stale pending id is not shown as a current pending review`
- expected `Review needs refresh`, received `State: Status unavailable`

## Why it is a timing race, not a component-semantics defect

- The PR830 merge commit `406836f4` has the relevant `TrainingPanel.tsx`,
  `TrainingPanel.test.tsx`, `maturity-api.ts`, and `tests/setup.ts` files
  **byte-identical** to `e4ffe720f` (`git diff --stat` empty for all four).
- On `e4ffe720f`, the exact six-file selection passed `136/136` locally.
- The same test run **alone** on `e4ffe720f` fails reliably with the same
  `Status unavailable` message.
- The component intentionally renders a fallback assessment with
  `state: "unknown"` while `getGraduationReadiness` is in flight
  (`TrainingPanel.tsx` lines 573–579). The adjacent test
  `deferred readiness shows unknown then the valid state` pins that
  unknown-first behavior.
- The failing test used `await screen.findByTestId('qualification-state')`,
  which resolves as soon as the element exists — i.e. on the unknown
  fallback — and then immediately asserted `toHaveTextContent(...)`. Under
  CI/suite timing the readiness promise had not resolved yet.

The component behavior is correct; the test needed to wait for the resolved
state. No product/UI source was changed.

## Fix (test-only)

- The stale-pending test now uses
  `await waitFor(() => expect(...).toHaveTextContent('Review needs refresh'))`,
  preserving the exact expected text and the no-pending/request/promote
  assertions.
- Added a deterministic deferred-stale control:
  `deferred stale readiness shows unknown then the refresh-required state`.
  It asserts the intentional `Status unavailable` first, then after
  resolving readiness asserts `Review needs refresh`, no pending review,
  the request control present, and promote disabled.

No skip, xfail, test removal, or semantic relaxation. The expected-refresh
and unknown-first semantics are both pinned.

## Post-fix local gates

- Single failing test: pass.
- Full `TrainingPanel.test.tsx`: `33 passed`.
- Exact six-file CI selection: `137 passed` (one added control).
- `npx tsc --noEmit --skipLibCheck`: exit 0, no diagnostics.
