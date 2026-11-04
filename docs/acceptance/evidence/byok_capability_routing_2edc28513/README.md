# BYOK workload capability routing — 2edc28513

Runtime candidate: `2edc28513415c980b8670568e472f1fa5e914514`
(branch `codex/brennan-full-app-20261102`). Product code is stable at
`d752d6bb4`; `2edc28513` adds the controlled probe script. No provider was
called, no credential or provider policy was changed, and no spend or model
download occurred.

## Contract implemented

- Server-selected, versioned capability profiles are carried by
  `LLMService` and `pinned_structured_call` into BYOK. Route-only metadata is
  consumed by the handler and never sent to a provider.
- Existing provider policy/local-only, credential, catalog route, structured/
  tool protocol, context, rate and budget gates run first. The workload
  profile then applies task-specific quality/evidence floors and ordering.
- Profiles exist for employee evidence selection, semantic mapping, adaptive
  planning/wait choice, goal replanning, alignment judging, extraction,
  document drafting, and a legacy best-effort planning profile.
- **Economy-first is the default.** Among routes meeting the workload floor
  and evidence contract, the lowest expected cost of a satisfactory result
  wins; latency is a tiebreak. Static quality is a prior, not branding proof.
  Flash models are ordinary eligible candidates, including on complex employee
  work. The generic complexity floor cannot silently exclude a route below the
  profile's own floor.
- An explicit owner preference can be `economy`, `balanced` or `quality`.
  Quality never bypasses the required floor or provider/authority gates.
- A quality-critical profile with no eligible route returns an explicit
  `no_suitable_configured_model` outcome (journal + exception) instead of
  relaxing to the cheapest ineligible route. Ordinary chat/extraction
  compatibility is preserved; `planning` without an employee label keeps its
  historical path.
- Strict qualification pins are exact route or failed attempt. A pin never
  silently escapes to another model. The pin decision is journaled with its
  profile, version, route, reasons and evidence state.
- Profile/version/workspace/tenant-scoped evidence is read from the existing
  `LLMRoutingFeedback` table. Rows from another workspace, another profile
  version or another task do not poison this decision. The audit journal is
  observational only and survives restart.
- The existing `/api/ai/provider-policy` settings surface now reports the
  profiles, the economy-first preference and recent routing decisions.

## Controlled probe (no inference)

`routing-probe.json`:

- Employee adaptive planning pool: Flash (`quality 90`, cost 1.0) vs frontier
  (`quality 99`, cost 20.0) → economy order **Flash first**, frontier second.
- Explicit `quality` preference → frontier first.
- A measured Flash failure rate (1/6 success, 3 retries, semantic failure) →
  Flash excluded, frontier remains; no repeated failing pair.
- A weak-only pool (`quality 60`) → **no_suitable**, not a silent downgrade.
- Good pin `fast/flash` at quality 90 → eligible, exact route returned.
- Bad pin `local/llama3.1:8b` at quality 75 → failed, exact route recorded;
  no escape to another model.

## Tests

`focused-tests.log`: **119 passed** in 19.61 seconds, covering:

- workload selector: cheap suitable Flash vs costly equivalent; explicit
  quality preference; measured failure exclusion; expensive failure excluded;
  no eligible candidate; context mismatch; evidence scope/version isolation;
  alignment failure not banning extraction; strict pins; persisted journal;
- BPC production path: Flash wins economy ordering; no-suitable returns empty
  and journals; profile floor keeps a quality-85 Flash eligible on COMPLEX
  where the generic floor is higher;
- existing pinned planning/transport, LLMService task-type forwarding,
  employee proposal/adaptation, work requests/bindings and two-domain campaign
  regressions.

## Boundaries

- This is controlled-candidate and production-path selection evidence, not a
  new model capability campaign. No claim is made that any specific model is
  generally qualified beyond the measured rows and the static prior.
- The local `llama3.1:8b` quality score is 75 in the benchmark table; a
  registered local route's declared quality (for example 90) remains its
  route-level prior, and measured profile failures can still exclude it.
- Full adaptive G5 remains open on the durable-wait capability contract owned
  by Agent 1; this change does not create wait authority or a new planner.
- Historical 111/123, previous tags, planner 5/5, goal router 1/2 and alignment
  gap 3.0 are unchanged.
