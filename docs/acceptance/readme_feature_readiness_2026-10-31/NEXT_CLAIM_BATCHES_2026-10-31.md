# Next claim batches — path from 82/123 to 99/123

**Date:** 2026-10-31
**Owner:** Agent 2 (README breadth / common-data surface)
**Denominator:** 123 eligible functional claims (frozen; no removals, no re-splitting)
**Current authoritative count:** **82/123 = 66.7%**
**Target:** **99/123 = 80.5%** — 17 additional claims
**Status:** plan only. No broad campaign was run. Shared repairs (objective
status, cached BYOK refresh) belong to Agent 1 and must be integrated and
rechecked before their claims are counted.

This file replaces the earlier "next 17" sketch. Every selected claim below is
an **executable boundary test**: the claimed operation is invoked and its
observable result is asserted. Registration counts, route-presence checks,
source-string searches, unconditional passes and "prerequisite served" checks
do not count.

---

## 1. Ground rules

1. Keep the 123-claim denominator fixed. A claim is either proven at its stated
   boundary or left Partial/unverified/inaccurate.
2. One claim = one observable. A test may share a fixture across claims, but
   each claim needs its own assertion and evidence file.
3. Every positive test needs a negative control: the refusal, the empty result,
   the unchanged state, or the unearned path.
4. Preserve failed attempts. A failed batch is evidence, not something to
   delete or rewrite into a pass.
5. Controlled-provider evidence is labelled separately from model-quality
   evidence. A local stub proving a transport/hook does not establish that a
   real model reasons well.
6. Do not deploy, send real messages, change credentials, or write to a
   connected system. Use isolated marked worlds and local stubs.
7. Run only the affected group/boundary per batch. No full campaign until the
   shared repairs and these 17 are integrated.

---

## 2. The 17 claims (5 waves)

| # | Wave | Claim | Current | Practical user value | Acceptance boundary |
|---:|---|---|---|---|---|
| 1 | A | **GOV-02** | partial | approve a held action and see the work actually run | goal-run checkpoint → HITL → approve → side effect re-read |
| 2 | A | **GOV-03** | partial | audit "who did what to which target, and did it work" | execution audit feed + replay |
| 3 | A | **GOAL-05** | partial | a goal keeps its status across a restart | create/advance → restart → re-read/resume |
| 4 | A | **WF-07** | partial | import a starter workflow and run it | template import → execute → execution completed |
| 5 | B | **MEM-01** | partial | durable facts are captured from a finished turn | `sync_turn` hook → `TurnFact` rows |
| 6 | B | **MEM-04** | partial | episodes count toward graduation | episodes → readiness → exam/promote → audit |
| 7 | B | **CORE-04** | partial | a taught rule is applied on a later task | teach → later prompt contains lesson |
| 8 | C | **ASK-01** | partial | proven actions stop asking; unproven ones still ask | oracle-verified successes → autonomy gate |
| 9 | C | **ASK-03** | partial | a regression automatically revokes autonomy | certified enable → regression → revoked |
| 10 | C | **ASK-05** | partial | stats and relaxation are gated, not automatic | stats before/after → certified queue → approve |
| 11 | D | **ROUTE-03** | partial | a failing provider falls back to the next | two local upstreams, first fails |
| 12 | D | **ROUTE-04** | partial | routing learns from observed outcomes | feedback rows → readiness → re-rank |
| 13 | D | **IO-06** | partial | a request produces a trace; export is optional | gateway request → span feed; local collector |
| 14 | E | **OFF-07** | partial | a live canvas shows an agent's write immediately | subscribed WS client receives structured snapshot |
| 15 | E | **TEAM-06** | partial | incumbency/COI baselines are reportable | emit events → org dynamics report |
| 16 | E | **INT-07** | partial | signed webhooks work and replay is rejected | HMAC accept-once + forged/duplicate controls |
| 17 | E | **INT-04** | partial | read data through a connected provider adapter | controlled local provider → adapter read |

**Score arithmetic:** 82 + 17 = **99/123 = 80.5%**. The 17th is the last
counted claim; nothing else moves the denominator.

**GOAL-01 contingency:** the claim is not in these 17. A targeted rerun now
records `objective_satisfied` on the early break and `max_steps_exceeded` on
the control (`evidence/goals-status-recheck.json`), but it remains Partial
until the verifier accepts that recheck. If accepted, the count is 83/123 and
only 16 of these 17 are needed for 99; if not, all 17 are needed. Do not count
GOAL-01 twice.

---

## 3. Wave A — approval, audit, goal durability, templates

Shared fixture: one isolated acceptance world, one admin token, one supervised
agent, and a goal run whose plan contains a `human_checkpoint` followed by a
deterministic step (canvas or `integration_action`). No model call is needed.

### GOV-02 — execute only after approval

**Execute**

1. Create a goal run with an explicit plan: a `human_checkpoint` step, then a
   deterministic step that creates a canvas or task.
2. Advance until the run is `paused_hitl`; capture the `HITLAction` id and the
   pending decision.
3. Assert **no side effect exists yet** (no target canvas/task row).
4. Approve through the user-facing decision route
   (`POST /api/agents/approvals/{action_id}` with `{"decision":"approved"}`,
   or `POST /api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve`).
5. Re-read the run and the target; assert the run advanced and the side effect
   now exists exactly once.

**Pass:** pending state + absent effect before approval; approved state +
present effect after; a repeated approval is idempotent (`already_resolved`),
not a second effect.

**Negative controls:** reject instead of approve → no side effect and the run
rewinds/fails per the product's stated path; approving a non-existent action
returns 404; a student/low-tier approver is refused.

**Evidence:** `evidence/governance/approval_execution.json`.

### GOV-03 — actor/action/target/outcome audit

**Execute**

1. Reuse the GOV-02 execution (or a real `tasks.create` tool call) and capture
   its `execution_id`.
2. Read `GET /api/audit/events?execution_id=...` as a supervisor.
3. Assert a row carries all four dimensions:
   - actor: `agent_id` / user id;
   - action: the tool/action name;
   - target: the resource id in metadata/params;
   - outcome: `success` true/false (and the error when false).
4. Read `GET /api/audit/executions/{execution_id}` and assert the replay has
   start and complete events for the same run.

**Pass:** all four dimensions present on one governed action; replay is
ordered and complete.

**Negative controls:** unauthenticated audit request → 401/403; a non-supervisor
→ 403; a deliberately failed tool call is recorded with `success=false` and an
error, not silently dropped.

**Evidence:** `evidence/governance/audit_execution.json`.

### GOAL-05 — durable goal status through restart

**Execute**

1. Create a goal and a goal run with a deterministic plan; advance one step.
2. Record `run_id`, status, decisions, and canvas ids.
3. Stop the backend and start a new process on the **same** data root (the
   install harness already does this for tasks/workflows/canvases).
4. Re-read `GET /api/goal-runs/{run_id}` and the decisions/canvases lists.
5. Call `/resume` or `/advance` on the same run and assert it progresses (or
   is already terminal) without creating a replacement run.

**Pass:** same run id and durable status/history after restart; resume acts on
that run.

**Negative controls:** a canceled run stays canceled after restart; an unknown
run id returns 404; no duplicate run is created by the restart.

**Evidence:** `evidence/goals/durable_restart.json`.

### WF-07 — import and execute a starter template

**Execute**

1. `GET /api/workflow-templates/`, pick a template.
2. `POST /api/workflow-templates/{id}/import` and capture the imported
   workflow id.
3. `POST /api/workflow-templates/{id}/execute` (or execute the imported
   workflow through the normal workflow route).
4. Poll the execution history until terminal; assert `COMPLETED`, a non-zero
   step count, and per-step results for the executed template.

**Pass:** import and execute are connected; execution is re-readable and
completed, not merely a 200 on the execute route.

**Negative controls:** unknown template id → 404; a template missing a required
input → paused/4xx, not a false success; executing before import does not
silently use a different workflow.

**Evidence:** `evidence/workflows/template_execution.json`.

**Wave A exit:** all four claims verified, or the failing claim stays Partial
with the failure preserved. Do not proceed to count until the evidence files
are in the manifest.

---

## 4. Wave B — memory, graduation, lesson application

### MEM-01 — per-turn extraction through the sync_turn hook

**Execute**

1. Run `GenericAgent.execute()` with a scripted `_react_step`/`_step_act` so
   the turn is deterministic and the extraction hook fires.
2. Use a **controlled LLM stub** that returns a valid five-category extraction
   payload; label this evidence `controlled_provider=true`.
3. Await the pending extraction task; query `TurnFact` by the execution id.
4. Assert the durable fact is persisted with the correct category and the
   transient chatter is absent.

**Pass:** the hook (not a direct extractor call) persisted the categorized
fact; a second identical turn does not duplicate it.

**Negative controls:** extraction disabled → no rows; an empty/irrelevant turn
→ no rows; the stub's transient sentence is not stored.

**Evidence:** `evidence/memory/sync_turn.json`.

### MEM-04 — episodes to graduation

**Execute**

1. Create a student agent.
2. Create real episodes through `POST /api/episodes/create` with outcomes and
   metadata that satisfy the selected tier's floors (or use the documented
   service path if the route requires a completed execution).
3. `GET /api/episodes/graduation/readiness/{agent_id}`; assert readiness
   reflects the episode evidence and names the remaining gaps.
4. `POST /api/episodes/graduation/exam` with edge-case episode ids; then
   `POST /api/episodes/graduation/promote` to the next maturity.
5. `GET /api/episodes/graduation/audit/{agent_id}`; assert the promotion and
   its validation are recorded.

**Pass:** created/retrieved episodes drive readiness and a recorded promotion.

**Negative controls:** insufficient or low-quality episodes → not ready and
promotion refused/no-op; an out-of-scope agent → 404; the audit never invents
a promotion.

**Evidence:** `evidence/memory/graduation.json`.

### CORE-04 — teach a rule, apply it later

**Execute**

1. Create an agent and `POST /api/agents/{agent_id}/teach` with a distinctive
   rule (e.g. "Always quote the FX rate before proposing a price").
2. Confirm the lesson is listed by the teaching-point read surface.
3. Run a later `GenericAgent.execute()` for a different task with a scripted
   `_react_step` that captures the prompt/messages it receives.
4. Assert the lesson block is present in that later turn's prompt.
5. Run the same task with a different agent and assert the lesson is absent.

**Pass:** the taught rule is recalled and injected on a later task, scoped to
the taught agent.

**Negative controls:** an unrelated agent does not receive it; a goal-scoped
lesson does not leak into a different goal; transient chat text is not stored
as a lesson.

**Evidence:** `evidence/core/lesson_application.json`.

**Wave B exit:** MEM-01 is explicitly controlled-provider evidence. Do not
present it as proof that a real model extracts facts well.

---

## 5. Wave C — Ask/trust: earned autonomy and revocation

### ASK-01 — per-action autonomy from verified outcomes

**Execute**

1. Create an agent with a capability for one action type.
2. Perform real actions whose outcomes are re-derived through the oracle
   (`tasks.create` / `_oracle_check`), then record the **verified** tri-state
   through `CapabilityGraduationService.record_usage(..., verified="verified")`.
3. Call the autonomy gate for that action (`gate_for_topic` and the runtime
   decision path). Assert the verified action reaches `execute` without asking
   when the tier/trust thresholds are met.
4. Call the gate for an unproven action type; assert it still returns
   `propose`/asks.

**Pass:** verified successes graduate the action; unproven actions still ask.

**Negative controls:** five self-reported/unverified successes do not graduate;
a verified failure increments the failure counter; an unknown agent cannot
inherit another agent's maturity.

**Evidence:** `evidence/ask/verified_autonomy.json`.

### ASK-03 — automatic revocation on regression

**Execute**

1. Set `ATOM_TRUST_CALIBRATION_ENABLED=true` and automation mode `auto`.
2. Seed at least 30 resolved assessment/outcome pairs whose probabilities and
   labels satisfy the certification gate; run `/run-now` and assert an
   `enable` verdict is applied (`resolved_trust_enforce=true`).
3. Add a regression cluster (rejected outcomes with high approval
   probability), run `/run-now` again, and assert the prior allow is
   `revoked` and `resolved_trust_enforce=false`.
4. Re-read `/automation` and the ledger row; assert the state change is
   durable.

**Pass:** a previously applied allow is revoked automatically after a verified
regression, without a human click.

**Negative controls:** insufficient data → `collecting`, no relaxation;
mode `off` → no ledger write; a manual mode does not auto-apply.

**Evidence:** `evidence/ask/revocation.json`.

### ASK-05 — stats and gated relaxation

**Execute**

1. `GET /api/v1/trust-calibration/stats` on a cold world; assert the counts
   are zero/consistent and `enabled=true`.
2. Add observations (approved/rejected) and re-read; assert `observations.total`,
   `by_source`, `approved`/`rejected`, and the calibration block reflect them.
3. In `approve` mode, run certification and assert an approval-state row is
   queued but `resolved_trust_enforce` is still false.
4. Approve the queued row and assert enforcement becomes true.

**Pass:** stats are real, and relaxation is refused/queued until certification
and explicit approval.

**Negative controls:** flag off → 503; invalid mode → 422; attempting to
relax without certification → no applied row; a rejected queued row leaves
enforcement false.

**Evidence:** `evidence/ask/gated_relaxation.json`.

**Wave C exit:** these tests seed real resolved outcomes. Synthetic label
arrays that bypass the certification join are not acceptable evidence.

---

## 6. Wave D — routing and request tracing

### ROUTE-03 — provider fallback

**Execute**

1. Run two local OpenAI-compatible stubs: primary returns 500/timeout,
   secondary returns 200 with a distinct marker.
2. Configure both as providers in the isolated world and select the primary.
3. Make a `/v1/chat/completions` request; assert the response contains the
   secondary's marker and that the attempt record shows primary → secondary.
4. Re-read the provider health/attempt evidence.

**Pass:** an upstream failure produces a successful fallback response from the
next provider.

**Negative controls:** both upstreams fail → 502 `all_providers_failed`;
only one provider configured → no fabricated fallback; a non-retryable 4xx
does not silently switch providers unless the product says it should.

**Evidence:** `evidence/routing/fallback.json` (controlled-provider).

### ROUTE-04 — learning re-rank

**Execute**

1. Insert at least 30 `LLMRoutingFeedback` rows in the window, ≥8 per model
   across two models, with outcomes favouring model A.
2. Set `ATOM_LEARNING_ROUTER=auto`; `GET
   /api/v1/llm/learning-router/status`; assert `ready=true` and re-ranking is
   live.
3. Call `LearningBasedRouter.route()` for a matching request; assert model A
   is selected and the result carries the learned score.
4. Add/invert feedback to favour model B; clear the readiness cache or wait
   for its TTL; assert the selection flips.

**Pass:** the readiness gate flips on real history, and the selected model
changes with observed outcomes.

**Negative controls:** 29 rows or one qualified model → `ready=false`;
mode `false` → re-ranking off; stale rows outside the window do not count.

**Evidence:** `evidence/routing/learning_rerank.json`.

### IO-06 — request-level span, optional export

**Execute**

1. Clear the span buffer; make a real gateway chat request.
2. `GET /api/observability/spans`; assert a span exists with `trace_id`, name,
   kind, status, latency, and request attributes for that request.
3. `GET /api/observability/status` with Langfuse unset; assert `configured=false`
   and no export attempt.
4. Point `LANGFUSE_HOST` at a local collector, set dummy keys, make another
   traced request, and assert the collector receives a well-formed
   `trace-create` + `span-create` batch with no secret values.

**Pass:** the request is traced at the request boundary; export is optional
and well-formed when configured.

**Negative controls:** no credentials → local span still recorded, no network;
an unreachable collector never fails the request; the span payload contains no
API keys.

**Evidence:** `evidence/interop/tracing.json` (local collector).

**Wave D exit:** ROUTE-03/04 evidence is controlled-provider; do not use it to
claim real-model quality.

---

## 7. Wave E — live office, team baselines, webhooks, connected read

### OFF-07 — live canvas broadcast

**Execute**

1. Present a DOCX (or XLSX) and capture `canvas_id`; open
   `/api/canvas/ws/{canvas_id}?token=...`.
2. Perform an agent-side office write (`POST /api/v1/office/word` or the
   append/write route) so `broadcast_file_update` fires.
3. Receive the WS message; assert it carries the file binding and a structured
   `content` snapshot (`paragraphs` for DOCX, `cells` for XLSX, `slides` for
   PPTX) plus the update type.
4. Assert a second subscriber/user channel receives the same update if the
   product exposes both.

**Pass:** a subscribed client receives the structured snapshot after the write.

**Negative controls:** unauthenticated WS → close 1008; a deleted canvas does
not broadcast/revive; a write to an unbound file does not target that canvas.

**Evidence:** `evidence/office/live_broadcast.json`.

### TEAM-06 — incumbency and COI baselines

**Execute**

1. Emit `fleet_recruit` events for repeated coordinator→specialist pairs, plus
   radio messages that create a COI pair; emit reviewer verdicts.
2. Run the real report path (`backend/scripts/org_dynamics_report.py` or the
   service functions it calls) with a window that includes the events.
3. Assert `incumbency.total_recruits`, `distinct_pairs`, `repeat_pairs`,
   `repeat_pair_ratio`, `review_rates`, and `coi_pairs` contain the expected
   pairs and counts.
4. Assert no policy was changed by the report.

**Pass:** the report computes baselines from persisted events.

**Negative controls:** empty window → zero/empty baselines, not fabricated
rows; a pair with only a radio message (no recruit) is not an incumbency pair;
the report is read-only.

**Evidence:** `evidence/teams/org_baselines.json`.

### INT-07 — signed webhook accepted exactly once

**Execute**

1. Set `SLACK_SIGNING_SECRET` in the isolated world.
2. Build a Slack event body with a unique `event_id` and a `url_verification`
   or message event; compute
   `v0=HMAC-SHA256(secret, "v0:{timestamp}:{body}")`.
3. `POST /api/webhooks/slack` with the timestamp/signature headers; assert the
   event is processed and the callback fires once.
4. Replay the identical body; assert `{"status":"duplicate"}` and no second
   callback.
5. Send a forged signature; assert 401.

**Pass:** correct signature → accepted once; replay → duplicate; forged → 401.

**Negative controls:** missing secret in production → 401 (fail closed);
missing timestamp/signature → 401; an unhandled event type is ignored without
marking a duplicate.

**Evidence:** `evidence/integrations/signed_webhook.json`.

### INT-04 — connected-provider read through the adapter

**Execute**

1. Start a local HTTP provider stub with a read endpoint and controlled
   records.
2. Create a connected-provider record/credentials in the isolated world and
   bind it to the universal adapter.
3. Call the adapter read path through the product API; assert the returned
   records match the stub and the connection id.
4. Assert the adapter reports the provider and the read operation, not just a
   catalog entry.

**Pass:** a real adapter read returns the provider's controlled records.

**Negative controls:** missing/invalid credentials → explicit auth error, no
data; an unconnected provider → 4xx; a connection for another workspace is
not readable.

**Evidence:** `evidence/integrations/controlled_read.json`
(controlled-provider; not live qualification).

**Contingency:** if the chosen provider's adapter needs a product change, swap
this slot for **CORE-06** only after Agent 1's cached-BYOK refresh is
integrated, or **GRAPH-05** (browser explorer) if a browser run is available.
The count stays 17 either way; do not count the substitute until it passes.

---

## 8. What is deliberately not in the first 17

| Claim(s) | Why not yet |
|---|---|
| ORCH-01, ORCH-02, ORCH-07 | require a usable authorized reasoning model at the served boundary; controlled-provider evidence is separate |
| GOAL-02, GOAL-04 | execute inside the model-backed ReAct loop |
| ROUTE-07 | needs a real opencode-go subscription key |
| MINI-03, MINI-04, MINI-05 | Firecracker/KVM unavailable on this host; runtime fails closed by design |
| INT-09 | live qualification of 46+ providers needs real accounts/permissions |
| ORCH-08 | documented **inaccurate**: `max_depth` is stored, not enforced; a product change is required before it can count |
| ORACLE-01 | registry covers only `trigger_workflow` and `tasks.create`; "every mutating action" is overstated until the registry is expanded |
| GOV-04 | session creation is triggered by a blocked model-backed run; can move after a controlled-provider batch |
| GOV-05 | OIDC config round-trips but login returned 503; needs a local IdP callback/product repair |
| TEAM-01 | the contract field exists but exactly-one accountability is not enforced; product change or mark inaccurate |
| TEAM-05 | nightly alignment sweep currently needs a model-backed judge; the opt-in scheduler path is not a substitute for a real sweep |
| MEM-07 | evolution candidate path is disabled and needs a controlled LLM mutation run |
| WF-05 | workflow pause/resume needs a low-maturity agent run; GOV-02 covers the generic approval bridge |
| GRAPH-05 | D3 explorer is a browser check; API query is already verified |
| CORE-06, ROUTE-06 | blocked on Agent 1's cached-BYOK refresh (Settings → save key → Chat without restart) |
| INST-01 | pristine `make setup` bootstrap is a separate installation campaign |

These are not deleted. They remain Partial/unverified/inaccurate in the frozen
inventory and can be picked up in a later batch.

---

## 9. Execution order and exit criteria

1. **Wave A** (GOV-02, GOV-03, GOAL-05, WF-07) — approval bridge, audit,
   restart, template execution. This also supplies the fixture for the later
   audit and goal claims.
2. **Wave B** (MEM-01, MEM-04, CORE-04) — memory and lesson application.
3. **Wave C** (ASK-01, ASK-03, ASK-05) — verified autonomy, revocation,
   gated relaxation.
4. **Wave D** (ROUTE-03, ROUTE-04, IO-06) — fallback, learning re-rank,
   request tracing.
5. **Wave E** (OFF-07, TEAM-06, INT-07, INT-04) — live broadcast, team
   baselines, signed webhooks, controlled connected read.

For each wave:

- run only that wave's boundary tests in a fresh marked world;
- record evidence under the wave's `evidence/...` path;
- run the negative controls in the same world;
- update the audit only after the positive and negative assertions pass;
- regenerate the manifest (hashes) after the wave;
- do not mark the claim verified if the only evidence is a route, a catalog
  entry, a source string or a synthetic history.

**Exit to 99/123:** all 17 counted claims have executable evidence and a
negative control, the shared objective/BYOK defects are integrated and
rechecked, and the independent verifier accepts the new evidence. Until then,
the authoritative score remains **82/123 = 66.7%**.

---

## 10. Shared dependencies handed to Agent 1

1. **Objective termination reporting.** The verifier observed an early
   predicate break returning `max_steps_exceeded`. The self-contained test
   (`backend/tests/test_objective_loop_termination.py`) now asserts
   `objective_satisfied` on the break and `max_steps_exceeded` on the
   exhausted-budget control. Agent 1 must integrate the reporting repair and
   re-run that test; GOAL-01 stays Partial until then.
2. **Cached BYOK refresh.** A key stored after `LLMService` construction is not
   seen by `/api/chat/message` until restart, while `/v1/chat/completions`
   works. Acceptance: Settings → save key → Chat works in the same process,
   with a test that constructs the service first, saves the key, then chats.
   CORE-06 and ROUTE-06 are deferred until this is integrated.

No deployment, real send, credential change or connected-system write was
performed for this plan.
