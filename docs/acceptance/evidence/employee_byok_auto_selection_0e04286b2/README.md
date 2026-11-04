# BYOK employee auto-selection — single-route served qualification + controlled multi-route matrix

2026-11-04, America/Toronto.

**Status: the served employee evidence-selection stage automatically selected the
one configured local route with no pin, and the controlled two-route consumer
matrix proves economy choice, measured-failure exclusion, bounded alternative
selection and honest no-suitable behavior. Multi-route **served** selection is
not claimed because only one route was configured/authorized in this batch.**

| Item | Value |
|---|---|
| Executed source | `0e04286b29dd81e1c25e2b0f735f3f2aa5f98773` |
| Served route | `ollama/llama3.1:8b` (exact local runtime) |
| Pin | none (`mode: unpinned`; requested/selected/served all local) |
| Evidence-selection calls | **5/5 parsed and served** on the local route |
| Evidence-selection usage | 28,034 prompt + 1,058 completion tokens |
| Evidence-selection latency | 98.78 s across 5 calls |
| Focused successor regression | **114 passed** |
| Controlled multi-route tests | **9 passed** through real LLMService/BYOKHandler |

## Served auto-mode episode

The objective was the broad procurement pool: seven authorized documents
including the correct invoice/PO/receiving chain plus wrong-PO, obsolete,
wrong-receiving and an irrelevant instruction-bearing memo. The user did not
name the answer subset or role mapping; the objective named only the business
invoice/PO.

The employee evidence-selection stage made five served calls. Every call was:

- `mode: unpinned` (no qualification pin);
- `requested_route: ollama/llama3.1:8b`;
- `served_route: ollama/llama3.1:8b`;
- parsed into a valid evidence-read proposal;
- journaled with prompt/schema, usage and the call-local route.

| Call | Prompt chars | Seconds | Prompt tokens | Completion tokens | Served |
|---|---:|---:|---:|---:|---|
| 1 | 12,111 | 28.03 | 4,327 | 384 | ollama/llama3.1:8b |
| 2 | 14,316 | 16.24 | 4,933 | 123 | ollama/llama3.1:8b |
| 3 | 13,737 | 21.93 | 4,742 | 380 | ollama/llama3.1:8b |
| 4 | 22,197 | 27.01 | 7,613 | 98 | ollama/llama3.1:8b |
| 5 | 18,416 | 5.58 | 6,419 | 73 | ollama/llama3.1:8b |

All seven authorized sources were read (the model chose the reads; the harness
did not supply a role subset). The job later reached the wait-choice stage with
a 27,513-character prompt; that call was also auto-dispatched to the local
route but produced no parsed proposal after 104.9 s. That is recorded as a
**semantic/protocol no-result at the wait-choice stage**, not as a routing
failure and not as accepted business work. The procurement selection/completion
row remains Agent 1's lane and is not claimed here.

## Controlled multi-route consumer matrix

These controls call `propose_employee_work`/`propose_adaptation` with a real
`LLMService` forwarding to a real `BYOKHandler`; only the provider transport is
doubled. The pool has two capable local routes: cheap `llama3.1:8b` and a
costlier `pricey-model`, both above the profile floor.

| Control | Result |
|---|---|
| cheap capable + costlier capable | economy selects the cheap route; journal served route matches |
| cheap route measured semantic failure | cheap excluded; one eligible alternative served |
| costlier route measured failure | cheap remains served; costlier not dispatched |
| both routes measured failure | explicit deterministic/no-suitable path; receipts retained; no work request |
| caller scope unresolved | deterministic fallback; no other-scope dispatch |
| caller deadline exhausted | deterministic fallback; `deadline_cancelled` attribution |
| wait-choice stage with missing prerequisite | dedicated `employee_wait_choice` profile; served cheap |
| compact continuation | `employee_adaptive_planning_compact` profile; served cheap; journal route recorded |

The controls count actual handler/client calls, not only selector output. A
measured semantic failure is disqualifying even when transport previously
succeeded; a failed costlier route cannot displace a healthy cheap one; and a
no-suitable outcome does not fabricate a completed result.

## Stage-to-profile matrix

| Stage | Profile | Dispatch path | Evidence-selection feedback |
|---|---|---|---|
| Evidence selection | `employee_evidence_selection` | `propose_employee_work` -> `LLMService` -> `pinned_structured_call` -> BYOK | served route/usage journal + scoped feedback |
| Wait choice | `employee_wait_choice` | `propose_adaptation` initial with missing prerequisite -> LLMService -> BYOK | route journal; this served call had no parsed proposal |
| Adaptive planning | `employee_adaptive_planning` | full adaptation -> LLMService -> BYOK | route journal + scoped feedback |
| Compact continuation | `employee_adaptive_planning_compact` | narrow typed continuation -> LLMService -> BYOK | route journal + scoped feedback |
| Goal replanning / extraction / document drafting / alignment judging | declared profiles | no current employee consumer in this batch | not qualified here |

A required profile being dropped or replaced by legacy is covered by the
consumer tests' profile assertions. Profiles are resolved from server labels or
explicit profile arguments, not client claims.

## Evidence and limits

`attempts-auto.jsonl` is the raw journal (dispatch/prompt/schema, parsed result,
route, usage, failures). `state.json` is the run projection. `server.log`
retains the provider/runtime trace. `consumer-routing-tests.log` and
`focused-tests.log` record the controlled and successor suites.

Limits: one configured/authorized local route, so the served demonstration
proves automatic selection of that route and honest controlled no-suitable
behavior, not served multi-route comparison. Route choice is not a guarantee of
business judgment; the later wait-choice no-result and the outstanding
procurement source-selection row are separate. No live/cloud provider,
credential, spend, send, download or deployment authority was used. Historical
111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 remain unchanged.
