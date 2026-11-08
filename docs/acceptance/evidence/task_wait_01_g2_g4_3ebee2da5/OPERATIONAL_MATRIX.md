# TASK-WAIT-01 operational matrix — current continuation

Source: `3ebee2da5`; main `36fa4ce39` merged. TASK-WAIT-01 remains OPEN at
whole-app scope; 143 claims and historical scores unchanged.

| Gap | Status after this checkpoint | Evidence / limit |
|---|---|---|
| G1 Generic active-vs-absolute budget | **Traced; no contract exists** | `AgentRunRequest`/`AgentJob`/`AgentExecution` have no wall/deadline/expiry. Generic active-run timeout/max_steps and spend gate are distinct. 2-hour controlled-clock idle test shows no LLM poll and retained receipt. Assignment budget is not claimed as Generic. |
| G2 source changed after acceptance | **Fixed and tested** | Failure-first test reproduced completed `130.00` stale value; existing `invalidate_step`/CAS now re-reads the current version and completes `210.00`. Clean affected selection 30 passed. |
| G3 Generic source answer | **Trace/proposal delivered; implementation pending root review** | Exact wait/correlation, actor/workspace/tenant, `resolve_assignment_source` versioned read and HITL snapshot reuse proposed; no filename matching/global upload/no new store. |
| G4 Generic two-job isolation | **Covered by new test** | Two real jobs/two waits; A answer leaves B waiting/no call/no task; stale A correlation to B = 409; one verified task each. Test-only; no runtime fix needed. |
| G5 browser badge provenance | **Accepted limitation, not a blocker** | Root accepted the per-file Git proof; badge caveat retained; no browser replay for a successor commit. |
| G6 browser breadth | **Accepted boundary** | At least one ordinary UI journey plus API/process negative/two-order coverage meets the written boundary; not every case must be in one browser campaign. Limits remain visible. |

The prior 82-control reconciliation remains valid at `2d251acdf`; this
checkpoint does not relabel it. Only the affected 30-control selection was
re-run because G2 changed runtime bytes.
