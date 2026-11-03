# Public goal approval binding — results

Executed source: `013e1b7cc` in the clean detached worktree
`/private/tmp/atom-goal-bind-clean`.

## Backend

`goal-approval-tests.log` — **204 passed** in one clean run:

- goal effect-family controls (15), including bound replay, unbound refusal,
  changed decision, changed plan, duplicate rejection, checkpoint-during-
  execution, simultaneous/stale/fresh-session service claims;
- goal route/service/loop/journey/access/event/notification/watchdog suites;
- HITL resume bridge and approvals journey, including the stale goal action
  preflight through the public approvals alias.

The original unbound verifier probe now receives its first-request refusal:
`legacy-unbound-refusal.txt` shows `409 decision_review_required` and
`assert 409 == 200`. That is the intended legacy-client refusal, not a
passing approval.

The adapted probe with a legitimately bound first request passes:
`goal-http-binding-adapted.log` — **1 passed**.

`goal-resume-claim-probe.log` / `.json` — **status passed**: simultaneous
service callers execute once; a stale generation-1 snapshot cannot clear the
newer generation-2 pending decision.

## Frontend

`goal-approval-frontend-tests.log` — **46 passed** across the goal-run detail,
goal-run index and approvals page. The detail page sends the reviewed
`decision_id`/`decision_binding`; the approvals page surfaces the targeted
stale message and refreshes the queue after a 409.

## Verified behavior

| Control | Observed |
|---|---|
| A bound approval, A opens B, A replayed | one execution; replay 409 stale; B remains pending |
| Unbound legacy approval | 409 decision_review_required; HITL unchanged |
| Decision rationale changed after review | 409 stale; no executor |
| Plan changed after review | 409 stale; no executor |
| Duplicate rejection | one override; second no-op/conflict |
| New checkpoint during execution | checkpoint remains pending; A row closes |
| Two simultaneous service resumes | one winner; one executor; one approval |
| Stale generation-1 snapshot | refused; newer pending retained |

## Boundaries

No live provider action, send, credential, consent or spend. No claim of
interrupted-claim/provider-lost-confirmation reconciliation, whole-app
ORACLE-01, soak or multi-worker closure. Historical `111/123` and prior
accepted sources/tags are unchanged.
