# Typed canvas receipts → assignments, guarded actions and teaching

Status: **submitted for independent verification; not self-accepted.** This
continues the accepted typed-canvas batch (`4859b0ce2477`) without changing the
connected acceptance at `6431bcb78` or historical 111/123.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Executed source | `acc22b9283bc` |
| Tree at execution | clean (`dirty=false`) |
| Backend identity | pid `22696`, source `acc22b9283bc`, instance `acc22b9283bc.22696.1793625234` |
| World | `canvas-successor-20261101-assignment` |
| Frontend | production build `X_PhH8Q4l6qVCB2K0XQLf` on `127.0.0.1:3133` |
| Backend | `127.0.0.1:8092`, real routes/executor/sqlite |

## What is connected

- **Receipt → ordinary assignment.** `canvas.receipt` consumes the exact
  server-issued `input_receipt`, verifies its digest and rechecks the current
  canvas revision/manifest/source/workspace before returning it as assignment
  evidence.
- **Guarded registered actions.** A `canvas.guard` step validates the declared
  action, then `canvas.action` performs the final revision/manifest/source/
  authority check immediately before dispatch. The action itself runs through
  the existing registered `action.registry` handler and executor approval
  operation. A changed canvas, removed action, cross-workspace context or
  changed operation blocks before any provider call.
- **Durable operation/readback.** The tested action is the registered
  `connected.outlook.create_draft` with a stable operation ID; the fake provider
  returns a draft ID and result. No send path is used.
- **Teaching proposals.** A proposal binds the receipt digest, source,
  manifest/state revisions and field/aggregate provenance. It is stored as
  shadow canvas state and does not change the agent. Promotion is a separate
  explicit call (`approved: true`) that writes through the existing teaching
  journal; duplicate promotion is idempotent, and a stale receipt or missing
  approval refuses.
- **Ordinary UI.** The capability panel now starts the governed assignment from
  the current revisions; the browser smoke does so on the industrial quote
  canvas and gets a completed receipt-only run.

## Controls

| Control | Result |
|---|---|
| Receipt → receipt step → guard → approved Outlook draft | Pass; one draft, body `350.00 USD`, stable run |
| Duplicate execute/approval | Pass; no second draft |
| Fresh executor after completion | Pass; no second draft |
| Canvas edit while action awaits approval | Pass; final `canvas.action` check fails, zero drafts |
| Manifest/action revocation while approval waits | Pass; manifest recheck fails, zero drafts |
| Teaching proposal | Stored as `proposed`; agent lesson journal unchanged |
| Teaching promotion without approval | 403 |
| Explicit teaching promotion | Lesson appears once; duplicate promotion is `already_promoted` |
| Stale teaching receipt / canvas revision | 409 before proposal or promotion |
| Unknown action template reference | Refused at manifest save |
| Three canvas shapes | Industrial quote `350.00 USD`, service `630.00 CAD`, queue `170.00 USD / 3 exceptions` |
| Source replacement old answer | 409; new question for replacement subject completes at `2000.00` |

## Tests

| Scope | Result |
|---|---|
| Canvas focused suite (including assignment integration) | **122 passed** |
| Typed canvas suite | **25 passed** |
| Assignment integration (receipt/guard/action/teaching) | **5 passed** |
| Assignment regression (`routes/executor/quote`) | **167 passed** |
| Verifier canvas boundaries probe | **3 passed** |
| Frontend canvas suites | **7 passed** |
| Ordinary-UI browser smoke | **17/17 checks** |

Logs and browser bundle are tracked in this directory. `backend-health.json`,
`frontend-health.json`, `world.json` and `frontend-build-id.txt` bind the
serving identity.

## Changed files

```text
backend/core/canvas_assignment.py
backend/core/canvas_capability_service.py
backend/api/canvas_capability_routes.py
backend/core/assignment_executor.py
backend/tests/test_canvas_typed_fields.py
backend/tests/test_canvas_assignment_integration.py
frontend-nextjs/components/canvas/CanvasCapabilityPanel.tsx
frontend-nextjs/components/canvas/__tests__/CanvasCapabilityDerive.test.tsx
scripts/acceptance/canvas_typed_canvases_local.py
```

## Exclusions

- No live provider lookup, refresh, write or send; the action test uses a
  controlled Outlook service behind the production registered action.
- No assignment-owned missing-value resume; incomplete receipts still use the
  accepted canvas clarification path.
- Canvas action arguments are a bounded template grammar, not arbitrary
  payload code.
- Teaching promotion is explicit human approval, not autonomous learning.
- No hosted deployment, universal mini-app/runtime claim, multi-worker/soak,
  or unfamiliar-user utility study.
- Connected acceptance remains `6431bcb78`; historical 111/123 unchanged.
