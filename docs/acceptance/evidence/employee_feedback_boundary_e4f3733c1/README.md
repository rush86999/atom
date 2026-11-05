# Feedback boundary repair — exact write binding and cross-task receipt

2026-11-04, America/Toronto.

**Status: the two withheld feedback boundaries are repaired at a frozen source
and requalified at controlled scratch-DB scope.** Business annotations now bind
to the exact generation receipt, and the generation receipt/served route are
returned explicitly across an awaited child task. The `model_wait_choice` origin
is integrated: a parsed wait is not a business success, a server-validated wait
decision is a scoped positive decision, and a rejected wait is a semantic
failure rather than deterministic-fallback credit.

| Item | Value |
|---|---|
| Repaired source | `e4f3733c1399ac1ca5ecef44adc02eec2fbe4da2` |
| Predecessor proof (preserved) | `employee_business_feedback_2ab959fc0` |
| Feedback controls | **22 passed** |
| Broad affected regression | **466 passed** (Python 3.11.16 and 3.14) |
| Independent boundary probes | **3/3 passed** (3.11 and 3.14) |
| Write-binding proof | `feedback-boundary-proof.json` |

## Blocker 1 — the write is now bound to the exact receipt

The transport outcome row is an immutable server-owned receipt:
`routing_result_id` + tenant + workspace + provider + model + profile/version.
A business annotation is accepted only when every field matches the stored
row. The check and the conditional update run inside one transaction with a row
lock; SQLite serializes writers and Postgres locks the row. The verdict-rank
gate still decides whether a weaker/duplicate evaluation may replace a stronger
one.

Verified finite matrix:

| Case | Result |
|---|---|
| Correct binding | one row annotated; no row inserted; cost/latency preserved |
| Wrong workspace / tenant | `refused_workspace` / `refused_tenant`; original success row unchanged |
| Missing workspace / tenant | `refused_missing_scope`; no default/current inference |
| Wrong provider / model / profile / version | specific `refused_*`; original row unchanged |
| Unknown generation | `skipped_missing_generation`; zero orphan rows |
| Same model on two providers | exact provider row annotated; the other provider row unchanged |
| Duplicate evaluation | `annotated` then `skipped_verdict`; row unchanged |
| Concurrent stronger/weaker | final row is the stronger failure, never the weaker success |

The persistence path now returns a truthful status
(`annotated`/`inserted`/`skipped_*`/`refused_*`/`error`) instead of reporting
success when a best-effort helper did nothing. The legacy
fabrication/correction annotation path keeps its established behavior; the
stricter receipt binding applies to business evaluations.

## Blocker 2 — the generation receipt survives a child task

The consumer creates a request-owned provenance mapping and passes it to
`pinned_structured_call`. The wrapper snapshots the final attempt's mode,
requested/served route, resolved model, profile, error and generation id into
that mapping before returning. The parent reads the mapping after
`asyncio.wait_for`, even when the call ran in a child task. ContextVars remain
for ambient inbound scope, but are no longer used as a return channel.

The control schedules the awaited call as a child and asserts the parent sees
`routing_result_id=generation-a`, `served_route=controlled/model-a`, and the
profile. A timeout clears the served route and receipt; a failed pin cannot
lend its id to a successful alternate, and a prior successful call cannot fill
a failed boundary.

## Wait-choice feedback integration

`model_wait_choice` is now a recognized model origin. It is not a universal
success:

| Shape | Feedback |
|---|---|
| Parsed wait/clarify with unresolved task outcome | `business_outcome=unresolved`; excluded from capability samples |
| Server-validated wait decision (`business_decision_validated=True`) | scoped positive decision (`business_outcome=satisfied`, scope `decision`) |
| Rejected unnecessary wait | `invalid_plan_reference` semantic failure on the model generation |
| Deterministic fallback | never credited as model success |

The real compact wait consumer test produces the receipt and proves the parsed
row is excluded from `employee_wait_choice` evidence. The real rejected-wait
test proves the model generation, not the fallback, is annotated.

## Test isolation

`test_employee_business_feedback.py` runs the independent
`test_actual_request_size_beats_the_coarse_complexity_context_floor` control
before and after the feedback fixtures. Both pass; the earlier order-dependent
failure was fixture contamination, not a context-capacity regression. No
production filter or eligibility assertion was lowered.

## Verification

The repaired source was extracted directly with `git archive e4f3733c1 backend`
into a clean directory. The broad affected neighborhood passed **466** tests
under Python 3.11.16 and **466** under Python 3.14. The verifier's three
boundary probes passed **3/3** under both (the 3.11 full-file run needs
`-p no:randomly` to avoid a plugin seeding error at setup; the probe itself
passes).

Artifacts:

- `feedback-boundary-proof.json` — fresh-session binding matrix, child-task
  receipt, wait-choice states and the preserved controlled decision change.
- `proof.py` — deterministic reproducer (no live model).
- `feedback-tests.log` — 22 feedback controls.
- `frozen-affected-311.log`, `frozen-affected-314.log` — 466-test runs.
- `probes-311.log`, `probes-314.log` — 3/3 independent probes.
- `MANIFEST.json` — source/artifact hashes.

## Boundaries

Scratch SQLite and doubled provider transport only. No live model inference,
provider, credential, spend, download or deployment. The predecessor proof
`employee_business_feedback_2ab959fc0` is preserved unchanged; this bundle
qualifies its successor rather than rewriting it. General adaptive judgment,
served multi-model comparison and Agent 1's separate wait-policy semantic
acceptance remain their own rows. Historical `111/123`, planner `5/5`, goal
router `1/2` and alignment gap `3.0` are unchanged.
