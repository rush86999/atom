# PR831 TrainingPanel async ordering repair (2026-11-10)

Status: **test-only CI unblock**. No product component change. This is not a
full-goal or general-UI acceptance claim.

## Source

- PR head: `346b9a6c5a230812ed8ab08ac814483e8cf9b1f9`
- Base main: `0d5132c2e060a5f2ac338bca143c5e138e607658`
- PR merge commit in the failing CI run: `0267d57233110cf03f8bdfeae89c86d9c917d387`
- Changed file: `frontend-nextjs/components/canvas/__tests__/TrainingPanel.test.tsx`
- Component `TrainingPanel.tsx` hash unchanged:
  `f72b9aac6160a112c5ece154f2eecc81b146e9d462f919c6f0173dcbb8260869`

## Before failure

Sanitized root CI log:
`/private/tmp/root-pr831-frontend-failure-20261110.log`
(sha256 recorded in `before-failure-summary.json`).

Result: **2 failed / 135 passed / 137 total**.

1. `TrainingPanel › an unconfirmed promotion shows the next action without a graduation notice`
   clicked the promote control while the readiness assessment was still the
   initial unknown state, so the click did not dispatch and the expected
   confirmation failure never appeared.
2. `Qualification assessment UI › request uses only the selected task/output bundle`
   read checkboxes as soon as the picker shell appeared, before the evidence
   bundles had settled; the shell correctly showed no reviewable work yet.

Both are the same test-side pattern: asserting/clicking on the first async
paint rather than the actual user-observable settled control.

## General async consumer review

The whole TrainingPanel test file was reviewed for the same pattern. The fix is
test-only:

- Promotion click waits for the control to become enabled after readiness
  resolves.
- Unconfirmed promotion now uses a **deferred readiness** promise: the initial
  unknown state is disabled, a click dispatches nothing, then the resolved
  valid assessment enables one click; the rejection shows the next action and
  no graduation notice.
- Qualification request uses **deferred readiness**: the picker shell initially
  has zero checkboxes and a disabled request; a click dispatches nothing; after
  the bundles resolve, exactly two checkboxes appear, the selected bundle is
  used, and exactly one request is dispatched.
- `unresolved_failed` / `unresolved_stale` twins use deferred readiness too:
  initial unknown never offers a dispatchable review action; after resolution
  the resolved label and blocked controls are asserted.
- Session completion waits for the control to be enabled before clicking.

No arbitrary sleeps, no flush-all, no force-enabled surface, no skipped/xfailed
test, and no weakening of unknown/stale/scope assertions. The component was not
changed because the tests prove test timing, not a runtime dispatch bug.

## After gates

| Gate | Result |
|---|---|
| Full TrainingPanel | **33 passed** |
| Exact six-file PR831 CI selection | **137 passed** |
| TrainingPanel repeated 3× | **33 passed each** |
| TypeScript (`tsc --noEmit --skipLibCheck`) | **exit 0** |

Exact six-file selection matches `.github/workflows/ci.yml`:
maturity-api, approvals-page, TrainingPanel, api-interceptors,
AgentMaturityGuide, SelfDirectedPathwayCard.

## Scope

Frontend test-only change; no backend/model/provider/browser campaign, no live
DB, no install, no PR edit or merge. The original before-failure capture is
preserved in excerpt/summary form; the full sanitized root log remains private
and is hash-referenced. General UI, all-tier behavior and whole-app acceptance
are not claimed.
