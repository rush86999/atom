# Guided create — approved HITL resume

Status: **distinct follow-up submitted for independent review.** No merge or
self-acceptance.

## Confirmed gap

The pending scoped `create_agent` HITL had no resume handler. Approving the
existing review row marked it approved but created no agent and no receipt.
The original guided evidence documented this as the remaining candidate.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-goal14-guided-create-20261110` |
| Parent | `9d2ba566c` (atomic parent claim) |
| Follow-up code | `2e48574ee` |
| Runtime | real scratch SQLite + FastAPI routes + real JWT; guided factory is a deterministic controlled double |

## Repair

`backend/api/agent_onboarding_routes.py`:

- Design the guided material before the trust gate.
- If the existing governance create policy denies direct creation, queue the
  HITL review with the exact reviewed material: name, description, category,
  capabilities, configuration, template, schedule, acting-agent reference,
  creator, tenant/workspace, plus a stable `review_digest`.
- The existing approvals route remains the only review surface.

`backend/core/guided_automation_service.py`:

- Shared review-material projection and SHA-256 digest helper.

`backend/core/hitl_resume.py`:

- `create_agent` is handled by the existing resume bridge.
- Only an already-approved row resumes; rejected, expired or pending rows
  produce no effect.
- The review digest is verified before creation; the approval preflight
  refuses a rewritten payload or changed stored material before the row is
  marked approved.
- The current reviewer is re-read and must still be active in the reviewed
  tenant/workspace.
- The acting parent is re-read under the reviewed scope and bound with the
  same transaction claim as direct guided creation.
- The shared decision writer creates one child and one audit receipt with a
  deterministic `guided-hitl:<action_id>` operation id, the original creator
  identity, STUDENT/0.1 and the reviewed material.
- Duplicate continuation returns `already_applied`; the scheduler runs only
  on the first verified create.

No second review engine was added and the resume bridge never approves its
own facts.

## Controls

| Control | Result |
|---|---|
| valid approval creates one reviewed agent + receipt | pass |
| scheduler once on first verified approval | pass |
| direct duplicate resume is idempotent | pass |
| duplicate public approval returns 400 without a second child | pass |
| rejection creates nothing | pass |
| expired row creates nothing | pass |
| wrong-scope reviewer is 404 | pass |
| modified approval material is 409 before approval | pass |
| changed stored material is 409 before approval | pass |
| fresh-session/restart approval creates the agent | pass |
| root parent-commit probe still 2/2 | pass |

`hitl-focused.log` — **7 passed**.  
`guided-after.log` — **26 passed**.  
`ci-guided-step.log` — **26 passed** under the additive CI env.  
`affected-after.log` — **312 passed** across onboarding, guided, custom,
agent, governance, decision, HITL, workflow and CI-lane controls.  
`root-probe-after.log` — **2 passed**.

## Preserved

- Original `ba497c196` and `9d2ba566c` evidence packets remain unchanged.
- The additive CI workflow/manifest step added for the guided suite now runs
  the expanded 26-test matrix.
- No live model/provider/DB/credential/send/spend/deploy/dependency.
- No budget/BYOK file, no new table/store, no test weakening.
- No merge or self-acceptance; root review remains independent.
