# Ordinary UI graduation qualification -> review -> promotion (2026-11-10)

Status: **PASS for one bounded ordinary-UI mechanism episode**. This is not a
full-app, all-tier, unseen-quality, general-autonomy, live-model-competence or
marketing acceptance claim.

## Exact identity

| Item | Value |
|---|---|
| Branch | `codex/web-graduation-ordinary-ui-20261110` |
| Product source | `6da3374abd2fdd2d88df5cfae1635f4d495301d8` (unchanged) |
| World | `grad_ordinary_ui_6da_1794315411_4d66ed51fe` |
| Run dir | `runs/run-9c939f4aeb4d` |
| Agent | `4cca507d-fe5c-43e6-bf2c-cd158f32bd62` |
| Canvas | `507e8792-6976-4cd5-840e-fea764f94af0` |
| Qualification HITL | `9a19f509-86a2-4770-a016-4f913e25542d` |
| Receipt | `qualification:9a19f509-86a2-4770-a016-4f913e25542d` |
| Promotion history | `1177d21d-9164-415b-a2cc-9d9223002213` |
| Notification | `6969f91c-2ccf-4711-a1cf-71f146d890bf` |
| Admin | `e260f8b0-e322-4590-8a47-40b6f01c5dc6` (bootstrap raw-NULL) |

Product/backend/frontend diff versus `6da3374`: **0 files**. Frontend source
parity is exact; the prior full tsc/UI test packet remains bound to the same
frontend bytes. Only the acceptance driver and evidence files were added.

## Release profile and UI paths

The core profile enables `agents`, `canvas` and `approvals`; `/approvals` is
`nav=false`, `min_role=team_lead`. The bootstrap admin is `workspace_admin`, so
the ordinary Approve control is enabled. No deferred surface was force-enabled.

Observed ordinary paths:

1. `/login` real email/password form, POST 200, token persisted.
2. `/dashboard` ordinary onboarding wizard, completed/dismissed through its own
   controls (backdrop/Escape on the retained continuation).
3. `/agents` unique card; ordinary **Teach** control created the canvas and
   attached the agent, then navigated to `/canvas/{id}?side=training`.
4. `/canvas/{id}` TrainingPanel: missing assessment, explicit evidence picker,
   request review, pending copy, valid qualified state, promote control.
5. `/approvals` ordinary qualification card showing task/output/frozen rubric;
   Approve created the receipt.

`AgentMaturityGuide` was traced: its button is present but disabled until an
active run sets `activeAgentId`. No model run was made, so it was **not**
force-enabled. Qualification state was observed in TrainingPanel instead.

## What passed

### Initial missing assessment, despite experience readiness

`GET /api/episodes/graduation/readiness/{agent}` returned `ready: true`,
`score: 89.9`, `gaps: []`, ten reviewable bundles, and
`assessment.state: unresolved_missing`. TrainingPanel showed **Review needed**
(`title=unresolved_missing`) and **zero** promote controls. No promotion was
possible before review.

### Ordinary evidence selection and review request

The supervisor selected the explicit bundle `agent_episode:...ep-09` +
`agent_execution:...exec-09`. The ordinary
`Request qualification review` control POSTed to
`/api/episodes/graduation/qualification/request` (200). The UI then showed
`Review pending in Approvals.` The durable pending HITL was exactly one row for
this agent, bound to `target_level=INTERN`, policy revision `1`, policy digest
`f2069edf...`, rubric `heldout-v1` with criteria `task_context`, `actual_output`,
`task_completion`, `scope`, `safety`, and the selected evidence refs. The agent
was still `student` with no `last_exam_id`; no early promotion occurred.

### Ordinary Approvals review

The `/approvals` card for this exact action showed the task, actual output,
frozen rubric, and Approve control. Clicking Approve POSTed to
`/api/agents/approvals/{action_id}` (200). The HITL became `approved`; exactly
one `graduation_exams` receipt exists:
`qualification:9a19f509-...`, `receipt_kind=capability_qualification`,
`candidate_capability_qualified=true`, `review_action_id` matching the HITL.
The agent was still `student` immediately after approval.

### Valid qualified state and actual promote control

On return/refetch the TrainingPanel showed **Qualified**
(`title=valid`), no pending copy, no review-required copy, and exactly one
enabled promote control. Clicking it POSTed to
`/api/episodes/graduation/promote` (200, `promoted: true`).

Authoritative durable readback:

- `AgentRegistry.status = intern`, `promotion_count = 1`,
  `last_exam_id = qualification:9a19f509-...`.
- `PromotionHistory.exam_id = qualification:9a19f509-...`,
  `from_level=student`, `to_level=intern`,
  `justification="public graduation; assessment=valid"`.
- Exactly one internal `agent_graduated` Notification for the admin user in
  `default` tenant/workspace.
- Fresh UI reload showed tier badge **INTERN** and no pending-review copy.

After promotion the qualification assessment state becomes
`unresolved_scope` for the *next* tier because the receipt is bound to the
completed `student -> intern` transition. That is transition binding, not a
stale pending review; the fresh reload showed no pending copy and the DB
matches.

## Controlled fixture disclosure (not model competence)

The agent was created through the public `/api/agents/custom` route. The
following records were seeded into the scratch run DB as controlled
preconditions:

- 10 `agent_executions`, 10 `agent_episodes`, 1 `artifact`, 1
  `episode_segment` with unique IDs `4d66ed51fe-*`, scoped to `default`
  tenant/workspace. These are controlled task/context + actual durable output
  fixtures, not fresh model work.
- 3 `agent_proposals` + 3 completed `training_sessions` (IDs
  `4d66ed51fe-training-session-0..2`) were added only after the initial UI run
  showed the student self-directed card requires 3 completed sessions.
- Agent confidence was updated from `0.35` to `0.62` as an exposure
  precondition because the card's `ready_for_review` also requires
  `confidence >= 0.5`.

**No** `graduation_exams`, approved HITL, qualification receipt,
`last_exam_id`, promoted status or policy exception was seeded. The HITL and
receipt in this packet were created by the ordinary UI request/approve actions;
the promotion was created by the ordinary UI promote control.

The initial run6 capture is preserved (`journey-initial-run6.json`,
`ui-run-initial.log`, screenshots): it reached missing -> pending -> approvals
-> valid qualified, but no promote control because the 3 sessions/confidence
exposure preconditions were not yet present. Continuation logs show the
sessions seed and the confidence precondition, then the PASS.

The earlier run5 negative is also preserved
(`journey-onboarding-intercept-run5.json`,
`ui-run5-onboarding-intercept.log`, `screenshots/agents-page-run5.png`): the
ordinary onboarding modal was still open and intercepted the Teach click, so
no canvas/action/receipt existed. The run6/continuation then completed or
dismissed onboarding through its own controls before Teach. No onboarding
completion was seeded via DB/API.

## Safety and scope

- World storage preflight: canonical local root via the worktree symlink; no
  maintenance lock; no root mkdir, bypass or config rewrite.
- Existing `run_isolated` world builder and existing frontend-copy mechanism;
  fresh world for the initial run, retained same world/run for continuation.
- Shared heavy gate used; distinct ports; owned server/frontend stopped after
  capture.
- Backend sandbox denied external network. No model/provider call, no external
  email/send, no live DB, no credentials or spend. The internal Notification
  row is real persistence; external email was not invoked.
- No product code edits; no PR/merge/CI yaml/goal index/new store/schema/judge/
  lifecycle.
- Screenshots/logs were secret-reviewed; no JWT, password, raw credentials or
  private query log is included.
