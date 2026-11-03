# Integrated approval/planning/alignment — results

Executed source: `e7758c7f8` in the clean `/private/tmp/atom-full-app`
worktree.

## Backend

`integrated-backend-tests.log` — **424 passed** in one run across:

- goal effect-family, routes, service, loop, events, learning, watchdog,
  access and journey suites;
- HITL resume/approval journeys;
- structured planner/goal consumer contracts and the shared plan validator;
- assignment executor (including the `operation` projection compatibility);
- alignment parser/verdict/certification;
- chat teaching, reviewed-skill, Memento, oracle/presentation and direct
  canvas controls.

The run is one invocation; no overlapping suite totals are added.

## Frontend

`integrated-frontend-tests.log` — **47 passed** across goal-run detail,
goal-run index and approvals. The detail page sends the binding from the
decision actually rendered; after a 409 it reloads the newer decision and
keeps the conflict message. The approvals page surfaces the targeted
stale/refresh message and refreshes the queue.

## Approval controls

| Control | Observed |
|---|---|
| A approval, A opens B, replay A | one effect; replay 409 stale; B pending |
| Unbound legacy request | 409 decision_review_required; HITL unchanged |
| Changed decision after review | 409 stale; no executor |
| Changed plan after review | 409 stale; no executor |
| Duplicate rejection | one override; replay no-op/conflict |
| Terminal/cancelled run | 409 run_terminal; no executor |
| New checkpoint during execution | remains pending; A row closes |
| Restart review -> effect -> replay | persisted binding; one effect; replay refused |
| Two simultaneous resumes | one winner/executor/approval |
| Stale generation snapshot | refused; newer pending retained |
| Integration action operation id | same reviewed decision/step -> same id; new decision -> new id |

`goal-resume-claim-probe.log` / `.json`: **status passed** (simultaneous and
stale-generation scenarios).

`goal-http-binding-adapted.log`: **1 passed** with a legitimately bound first
request. `legacy-unbound-refusal.txt`: the original unbound probe's first
request is refused 409, as intended.

## Planning

`planner-goal-served-report.json` / `planner-goal-served-calls.jsonl` /
`structured-planning-goal-suite.log`:

- planner: **passed** 5/5 model-backed cases, including `use_tool=false`
  with no tool and no transport conflation;
- goal router: **failed** 1/2. The ambiguous-quote case produced REPLAN with
  an empty plan, then a second REPLAN with unsupported step kinds; production
  rejected it and returned `ASK_HUMAN`. The research-finished case produced a
  valid REPLAN. Diagnostic retries outside the production consumer are not
  counted as passes.
- shared plan validator: empty/dict/duplicate/unknown/dependency/auth-expanding
  plans rejected by router and executor; assignment `operation` projections
  explicitly scoped to task-lifecycle runs.

## Alignment

`alignment-invalid-evidence.json`: nine `not-json` judges ->
`ran=true, green=false, evidence_complete=false, valid=false, max_gap=null`,
nine invalid judgments. No certification.
`alignment-valid-green.json`: complete valid sweep -> `green=true`,
`max_gap=0.0`, valid.
`alignment-valid-negative.json`: complete valid sweep -> `green=false`,
`max_gap=7.0`, valid.
`alignment-served-report.json` / `.log` / `-calls.jsonl`: local served sweep,
18 calls, `green=false`, `max_gap=3.0`, `evidence_complete=true`,
`absolute_policy_min=6.0`, 15 material violations. The 2.0 threshold is
unchanged and the genuine negative finding is preserved.

## Boundaries

No live provider action, send, credential, consent or spend. Model
qualification remains failed overall (goal router). Interrupted-claim/provider-
lost reconciliation, whole-app ORACLE-01, soak, multi-worker and PostgreSQL
runtime qualification remain open. Historical `111/123` and accepted
tags/sources unchanged.
