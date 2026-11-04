# Employee G5 — held-out continuation and same-job recovery

2026-11-04, America/Toronto.

**Status: bounded same-job continuation and deterministic recovery — SUPPORTED.
This is not a fresh held-out content/event-order qualification.** The held-out
values and identifiers became known during the failed run; this bundle
preserves that failed run and demonstrates recovery on the same job after two
targeted repairs. A fresh unseen-value batch is still required for the final
held-out claim.

| Item | Value |
|---|---|
| Executed product source (recovery) | `b16172c8df3a5244f7748282469673b1ee02f294` |
| Evidence tip | `60d464a5f1ac4be51a46c3c2f9bfa858c4c3c9d1` (token-count journal preservation only) |
| Run | `d40c94ee-2128-4f56-8165-1d2b8fcbd01a` |
| Wait | `await-e94400ac76450659e0de` (receiving, PO-HX-7001) |
| Quote | **125.00 USD**, operation `9ea5f0de-8bcc-4152-b1fe-dd3b4127fd9b` |
| Reconciliation | **101.00 USD**, step `invoice-reconcile` |
| Requested document | `review.docx`, sha256 `0271e1074b2e8937ba87915038f950a41d671a06390b01625e66d0acf1deba72` |
| Recovery checks | **9/9** |
| Focused regression | **130 passed** |

## Independent arithmetic

```
quote:        4 * 12.50 + 2 * 30.00 + freight 15.00 = 125.00 USD
reconciliation: 3 * 30.00 + freight 11.00          = 101.00 USD
```

The expected totals were computed independently from the fixtures. They were
never sent to the model. The model selected the typed invoice reconciliation
and the three accepted role step IDs; the compiler resolved the default field
maps, executed the arithmetic and verified the receipts.

## Attempt history on the frozen failed job

The original run produced the durable receiving wait and the independent quote
before the restart. After the authorized receiving answer, the all-purpose
adaptation profile timed out and left the job blocked with the quote receipt
and no reconciliation. The follow-up work below preserved those receipts.

| Attempt | Source | Model stage | Result | Repair |
|---|---|---|---|---|
| 1 | `18cb7bd0f` | compact, pinned local route | 20.5s; valid semantic request but the small model copied a JSON-schema `$ref` into `evidence` and sent a numeric cell value where a column name belongs | expose only the model-owned invoice operation/role IDs/currency; compiler owns field maps |
| 2 | `74b9ef487` | compact, pinned local route | 11.2s; valid typed replan, adoption refused because the model omitted opaque observation IDs | bind exactly the compact call's own observations when omitted |
| 3 | `3b3f9ef92` | compact, pinned local route | 4.28s; valid typed replan, adoption **applied**, then the executor refused the step at its wall-step budget | owner budget extension + retry on the same job |
| Recovery | `b16172c8d` | no new model call | owner raised the wall/step budget and retried `invoice-reconcile`; same job completed, artifact published | new increase-only `/api/assignments/{run_id}/budget` route |

The three model calls were pinned to `ollama/llama3.1:8b` and served on that
exact route under the separately declared
`employee_adaptive_planning_compact` profile. There was no provider
substitution. The all-purpose `employee_adaptive_planning` profile in this
world remains measured-failure-disqualified, which is why the compact
continuation is a distinct declared capability configuration rather than a
relabel of the old profile.

## Recovery checks

| Check | Result |
|---|---|
| same run | PASS |
| same wait identity | PASS |
| quote receipt preserved (125.00, same operation) | PASS |
| reconciliation 101.00 | PASS |
| assignment completed | PASS |
| every business requirement satisfied | PASS |
| requested document applied | PASS |
| document contains 125.00 | PASS |
| document contains 101.00 | PASS |
| document sha256 matches | PASS |

The recovery result is `state.json`; the intermediate continuation results are
`result-attempt1.json`, `result-attempt2.json` and `result-attempt3.json`. Raw
model requests, parsed responses and failures are under
`attempts-compact-1.jsonl`, `attempts-compact-2.jsonl` and
`attempts-compact-3.jsonl`. `server.log` retains the provider-side validation
trace, including the first malformed output and the later served-route
attribution.

## Focused regression

`focused-tests.log` records **130 passed** at the evidence tip, covering:

- adaptation contract, compact single-operation continuation and budget-skip
  accounting;
- business requirements, exact namespaced identity, empty-scope and
  wrong-subject completion guards;
- durable-wait G5, work-request bindings, model-proposal and prerequisite
  eligibility;
- structured cancellation ownership, single-flight retention and retry-budget
  controls;
- workload capability routing, including the separate compact profile;
- the new owner budget-extension route.

The previously accepted `2eb433f41` 410-test result and the `70a74cd02b5`
episode remain at their original source identities; they were not replayed.

## What this does and does not establish

It establishes that the frozen failed job can be recovered without re-uploading
sources or restarting the task: the useful quote and receiving receipts stay
intact, the model selects the dependent reconciliation through a narrow typed
continuation, the compiler owns the field maps and arithmetic, and the owner
can raise an exhausted budget in place.

It does **not** establish held-out content/event-order qualification on unseen
values. The `HX-1`/`HX-2`/`PO-HX-7001`/`INV-HX-88` values are now known, so a
fresh new-value, new-identifier batch is still required. It also does not
establish general adaptive judgment, alternate served event ordering, customer
email send, live Zoho/Microsoft breadth, Linux/KVM, multi-worker/soak, or a
whole-app ORACLE claim.

Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 remain
unchanged. No live/cloud provider, credential, spend, send, download or
deployment authority was used.
