# Fleet Orchestration — CSO→Division→Specialist Wiring (W4)

> **Status:** Phase 1 (P1a–P1d) implemented behind feature flags. The
> previously-dead `route_with_governance` path is wired into the live
> `AtomMetaAgent.execute()` dispatch; the fleet recruits real ranked
> specialists with depth-enforced nesting. **Flags default OFF — kill-switch
> parity with pre-P1 behavior.**
>
> **Last Updated:** Aug 8, 2026
>
> **Related code:** `backend/core/atom_meta_agent.py`,
> `backend/core/fleet_routing_config.py`, `backend/core/specialist_matcher.py`,
> `backend/core/agent_governance_service.py`, `backend/core/models.py`
> **Cross-references:** [`STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md`](./STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md)

---

## TL;DR

- The dead fleet path (`route_with_governance` had zero live callers) is now
  reachable from `execute()` behind `ATOM_FLEET_ROUTING_ENABLED` (default
  false). A fleet-eligible ONE_OFF task routes through governance and returns
  a recruitment summary.
- `SpecialistMatcher` is real: ranked candidates from `AgentRegistry` via an
  explicit scoring metric (capability overlap + tier + verified-episode ratio
  + confidence + recency).
- `DelegationChain.max_depth` now gates **nesting depth** (root→a→b→c = 3),
  not total link count — fixing the R1 bug where 3 flat siblings tripped the
  same limit as a 3-deep nested chain.
- The Virtual Biotech pattern: `QueenAgent` = orchestrator (no data tools),
  divisions = specialists, `agent_radio` = cross-team thread, the W3 reviewer
  = re-delegation.

## Feature flags (`core/fleet_routing_config.py`)

| Flag | Default | Gates |
|---|---|---|
| `ATOM_FLEET_ROUTING_ENABLED` | **false** | Master switch — whether TASK intents route through the governed fleet path |
| `ATOM_FLEET_ROUTING_FORCE_ENFORCE` | false | Shadow mode: compute/audit recruitment but fall through to Queen→ReAct for the response |

Kill-switch parity: both off == exact pre-P1 behavior (covered by
`test_fleet_routing_wire.py::test_flag_off_never_routes_through_governance`).

## Architecture

```
execute(request)
  ├── classify_route → RouteCategory.ONE_OFF + len>40  ← fleet-eligible
  │   (only if ATOM_FLEET_ROUTING_ENABLED)
  ├── route_with_governance(:2229)                      ← the wired method
  │   ├── _check_governance (defense-in-depth double-gate)
  │   └── _route_to_task → FleetAdmiral.recruit_and_execute
  │       └── RecruitmentIntelligenceService
  │           └── SpecialistMatcher.find_specialists_for_domains  ← real, ranked
  ├── emit synthetic "fleet_recruitment" step (net-new; no prior step_callback)
  └── if force_enforce: return {status:"fleet_recruited", chain_id, ...}
      else (shadow): fall through to Queen→ReAct
```

## Scoring metric (`SpecialistMatcher`)

```
score = 0.40 * capability_overlap(required_keywords, agent.capabilities)
      + 0.25 * tier_floor_weight(agent.status)            # AUTONOMOUS=1.0 … STUDENT=0.3
      + 0.20 * verified_episode_ratio(agent.id)           # AgentEpisode verified/total
      + 0.10 * confidence_score(agent.confidence_score)
      + 0.05 * recency_bonus(agent.last_request_date)     # NOT last_active_at (UserSession)
```

## Depth enforcement (R1 fix)

`agent_governance_service._max_nesting_depth()` walks the `ChainLink`
parent→child tree from the chain root; `max_depth` gates that. Flat chains
(depth 1) no longer trip the limit; nested chains do.

## Division hierarchy (`agent_divisions` table)

| Column | Purpose |
|---|---|
| `lead_agent_id` | Division head (a real `AgentRegistry` row, never a placeholder) |
| `parent_id` | Nested divisions (self-FK) |
| `domain` | Canonical specialty domain |

`AgentRegistry` gains `division_id`, `parent_agent_id`, `specialty`.

## Fleet scaler real recruitment (P1d)

`fleet_scaler_service._execute_expansion` no longer fabricates
`recruited-agent-{hex}` strings or `parent_agent_id="system"`. Recruitment now
queries `AgentRegistry` for real available agents (AUTONOMOUS/SUPERVISED,
enabled, not already in the chain); when the pool is short it registers real
placeholder `AgentRegistry` rows (`flush()`-ed so `ChainLink` FKs never dangle).
Parent links use the chain root (a real agent) instead of the literal `"system"`.

## Fleet sub-agent budget + memory (P1d)

Recruited specialists execute via `GenericAgent.execute()`, which enforces:
- **Spend gate** (`_check_budget_before_react`) before each LLM call — halts
  on `budget_exceeded`.
- **Episodic memory** (`record_experience` → `AgentEpisode`) so fleet
  successes can graduate (interacts with the W2 oracle).

## Known scale-blockers (deferred — H10)

- `action_registry` and `ToolRegistry` are process-global singletons; per-
  tenant partitioning is a future phase.
- `agent_id="atom_main"` is hardcoded; the `_atom_instance` singleton forbids
  competing meta-agents.

## Verification

- `test_fleet_routing_wire.py` (4) — kill-switch parity, flag-on routing,
  shadow mode, broken-copy deletion.
- `test_specialist_matcher_real.py` (6) — ranked candidates, tier weight,
  domains, unknown-domain fallback, backward compat.
- `test_fleet_depth_enforcement.py` (5) — nested blocks, flat doesn't, FK
  (PRAGMA on), columns, table.
- `test_fleet_budget_memory_hooks.py` (3) — gate denies when budget exhausted,
  halted runs never reach the LLM step, successful runs record experiences.
- `test_fleet_scaler_service.py` (+2) — expansion recruits registered
  AgentRegistry rows (no fake ids / no `"system"` parent), prefers real pool
  agents before placeholder fallback.

## Fleet Routing Validation & Automation (2026-08-21)

The master switch flipped to **ON (shadow)** on 2026-08-21 — fleet-eligible TASK
intents get governed recruitment computed + audited on every `execute()`, while
responses still come from Queen→ReAct. This section is the data-driven,
consent-gated path from shadow to force-enforce (pilot).

**Honest single-arm semantics.** In shadow mode the fleet is recruited but NOT
auto-executed, so `fleet_routing_audit` rows measure the *incumbent* baseline
on fleet-eligible tasks (joined from the `AgentExecution` finalize points).
There is no fleet-arm outcome until force-enforce is on. Certification
therefore means "baseline healthy + recruitment machinery works" → recommend
the pilot; it does NOT claim "fleet beats incumbent".

**Pipeline:**

1. **Audit** — `core/fleet_orchestration/fleet_routing_stats.py`:
   `record_fleet_decision` (every fleet-eligible decision incl. recruitment
   failure, never raises) + `record_fleet_execution_outcome` (joined at both
   finalize points in `execute()`; only `success IS NOT NULL` rows are
   calibration-eligible). `workload_key` = sha1 of the normalized request.
2. **Calibration** — `fleet_calibration_status()`: per-workload phase
   (off / blocked / collecting / ready / enforced), incumbent success rate,
   min detectable gap (reuses `min_turns_per_arm` / `min_detectable_gap` from
   `core.llm.stage_router`). Public at `GET /health/fleet-router`.
3. **Automation** — `core/fleet_orchestration/fleet_router_automation.py`:
   consent-gated verdicts (`enable` = pilot-ready, `blocked`, `revoke`).
   Modes: `off | notify | approve | auto` (env `ATOM_FLEET_ROUTER_AUTO_ENFORCE`,
   default `approve`). Escalation requires consent (approval action row →
   `POST /api/v1/fleet/automation/approve`); **revocation is always automatic**
   in all non-off modes (baseline success < 0.5 over ≥20 rows, or recruitment
   success < 0.8 over ≥10 attempts).
4. **Enforcement resolution** — `resolved_fleet_enforce()`: the env kill-switch
   `ATOM_FLEET_ROUTING_FORCE_ENFORCE=true` ALWAYS wins; otherwise the latest
   applied/revoked automation action `fleet_router_automation_actions`
   (workload `__global__`) drives the switch. Failures degrade to shadow.
   In `auto` mode the automation applies the override itself; in `approve`
   mode an admin approves it via the management API. The automation loop
   lazy-starts from the hot path (mirrors the stage-router pattern).

**Action flow example (approve mode):** shadow data collects → calibration
pass (every `ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN` min, default 60, or
`POST /api/v1/fleet/automation/run-now`) sees ≥30 outcome-joined rows + healthy
baseline + healthy recruitment → action row `state=approval` + in-app
notification `approval_needed` → admin approves → `state=applied` →
`resolved_fleet_enforce()` returns True → eligible tasks return the fleet
recruitment summary (`status: fleet_recruited`). Baseline regression after
that point → auto-revoke → override cleared → shadow again.

**Env knobs:**

| Env | Default | Meaning |
|---|---|---|
| `ATOM_FLEET_ROUTER_AUTO_ENFORCE` | `approve` | off\|notify\|approve\|auto |
| `ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN` | `60` | certification cadence (min) |
| `ATOM_FLEET_ROUTER_AUTO_MIN_ROWS` | `30` | outcome-joined rows floor per verdict (hardcoded in stats module today) |
| `ATOM_FLEET_ROUTER_AUTO_SUCCESS_GAP` | `0.70` | incumbent baseline floor to pilot |
| `ATOM_FLEET_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS` | `24` | notify-mode dedupe |

**Admin surface**: `GET /api/v1/fleet/automation` (status), `POST .../config`,
`POST .../run-now`, `POST .../approve`, `POST .../reject` (all admin-gated,
403 otherwise); `GET /api/v1/fleet/automation/status` + `/health/fleet-router`
are public read-only.

## Final synthesis completion contract (2026-11-14)

The live Goal 13 replay returned a user-visible answer that stopped
mid-action ("... slipped deals are more likely") while the fleet reported
`status=success`; the specialist's durable output contained all three
corrective actions. Two independent truncation axes were conflated:

| Axis | Field | Meaning |
|---|---|---|
| INPUT | `final_synthesis.evidence_truncated` | The bounded synthesis prompt omitted specialist text. |
| OUTPUT (proven) | `final_synthesis.finish_reason` / `output_truncated` | The provider reported a truncating limit (`length` / `max_tokens` / `model_context_window_exceeded`). Only this is proof. The first two are the request's output cap; the last is the model's context window, so disclosures say "a limit the provider reported", never "output limit". |
| OUTPUT (suspected) | `final_synthesis.output_ending_unverified` | The text shape is weak evidence of a cut and no usable stop reason survived. This is suspicion, never a provider fact, and it does not claim the provider omitted a reason. |
| PROVENANCE | `final_synthesis.truncation_evidence` | `provider_finish_reason` (provider-proven), `text_shape` (a fresh probe actually observed the shape), `legacy_record_unverified` (a cached repair knows only that the old boolean survived), or `None`. |

`evidence_truncated=true` is **not** evidence that the provider hit the 900
token cap (the replay used 820 completion tokens).

**Provider contract.** `BYOKHandler` has always known the provider stop reason
but `generate_response` dropped it. The accepted route now writes it into a
caller-owned `finish_reason_sink` passed by `LLMService.generate_completion`
(one fresh mapping per call), and the service surfaces real provider metadata
as `finish_reason`. The legacy `_last_finish_reason` attribute is retained only
for the backward-compatible text API; `generate_completion` never consults it,
not even as a fallback. It is shared mutable state whose value belongs to
whichever concurrent call wrote last, so borrowing it would attribute another
call's provider metadata to this answer. A handler that cannot receive a sink
(narrow legacy signature, non-introspectable callable) keeps working -- no
additive keyword is sent -- and reports `None` (unknown); a sink that was
passed but never written is likewise `None`. Nothing is invented: no stop
reason from the provider means `None`, `empty_synthesis`, or an error reason,
never a fabricated `"stop"`. The shared result boundary trims/lowercases the
provider value and normalizes a blank/missing value to `None`, so `""` can
neither masquerade as a known reason nor suppress the missing-metadata shape
backstop. Truncation is detected from the provider vocabulary, not from the
input flag:

- OpenAI Chat Completions: `finish_reason="length"` means the maximum number of
  tokens specified in the request was reached
  (<https://platform.openai.com/docs/api-reference/chat/object>).
- Anthropic Messages: `stop_reason="max_tokens"` means the response was cut at
  `max_tokens`, and `model_context_window_exceeded` is treated as truncated
  (<https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons>).

**Text shape is weak evidence.** With no provider stop reason, only a
structural clue is considered: an unbalanced opening bracket, or a trailing
article/conjunction/preposition that cannot end an English clause (e.g.
"... corrective actions on the", "... 2 of"). Evaluative endings such as
"Risk: unlikely", "Recovery is likely", and the live "... slipped deals are
more likely" are **valid concise answers**, not model truncation; the old
letters-only tokenizer also dropped the final number in "Completed items:
2 of 2" and inspected the preceding "of". Auxiliary, modal, and copula verbs
are deliberately not continuation tokens either: "It should.", "Ownership:
the platform team does.", and "It is." are complete elliptical answers, so
the backstop reports unknown rather than fabricating a cut. A provider reason
always wins over this weak shape signal: `stop` uses the text, `length`/
`max_tokens` uses the durable fallback even when the text looks complete.
There is no quantity or domain special case.

**Proof is not the same as suspicion (2026-11-14 root counterprobe).** The
same shape can complete a status label or a particle imperative ("Device
status: on", "Count me in", "Carry on"). With `finish_reason=None` the old
code escalated that shape to `output_truncated=true` and told the user the
answer "was cut off at the model's output limit" -- a provider fact no one
reported. The two outcomes are now separate:

- `output_truncated=true` + `reason="output_truncated"` +
  `truncation_evidence="provider_finish_reason"` only when the provider
  reported a truncating stop reason;
- `output_ending_unverified=true` + `reason="output_ending_unverified"` +
  `truncation_evidence="text_shape"` for the missing-stop-reason backstop.
  The cautious fallback is unchanged (the editorial text is still withheld),
  but the disclosure says the ending could not be verified as complete
  instead of asserting an output limit. It also does not say "the provider
  reported no stop reason": a missing call-local reason is unknown, and a
  legacy adapter may simply have lost one the provider sent.
- an explicit non-truncating reason (`stop`), a missing `None` reason with no
  shape concern, and a blank reason that normalizes to `None` all leave the
  editorial text usable; a blank reason still arms the shape backstop.

`reason` therefore never overstates proof. The same distinction survives a
cached readback, using only what the durable record actually retains:

- a retained truncating reason (`length` / `max_tokens` /
  `model_context_window_exceeded`) stays provider-proven
  (`output_truncated`, `truncation_evidence="provider_finish_reason"`);
- an old `output_truncated=true` claim with **no** retained reason was never
  supported by anything in the record, so it is relabelled
  `output_ending_unverified` with `truncation_evidence="legacy_record_unverified"`
  -- not `text_shape`, because the repair observed no text and cannot know
  whether the provider omitted a reason or a legacy adapter dropped it;
- an old `output_truncated=true` claim contradicted by a retained
  non-truncating reason (e.g. `stop`) is repaired to
  `reason="cached_output_claim_unproven"` with no truncation or unverified-
  ending assertion, because the withheld editorial text was never persisted.

Every repair takes zero synthesis calls and zero dispatches, and is persisted
for later readbacks.

**Deliverable rule.** The editorial synthesis is used only when the output was
not truncated and the bounded prompt carried the complete specialist
evidence. Otherwise the existing durable raw-contribution fallback is used:
full attributed specialist outputs + deterministic quantitative
reconciliation (including a non-zero residual) + the execution-status footer.
No extra provider call is made and no specialist is re-dispatched, so there is
no unpriced retry and no duplicate work. `final_synthesis.used=false` with
`reason="output_truncated"`, `"output_ending_unverified"`,
`"cached_output_claim_unproven"`, or `"evidence_truncated"` records why.

**Budget.** The synthesis remains one bounded read-only call:
`_SYNTHESIS_MAX_OUTPUT_TOKENS=1400` (up from 900; the five required sections
plus a 3-action list did not fit) and a shared
`_SYNTHESIS_TOTAL_EVIDENCE_MAX_CHARS=10000` budget with a 6,000-char
per-contribution ceiling (up from 2,000, which cut the replay's action list
after item 1). The evidence budget is unchanged, so a large roster still
cannot dominate the prompt.

**Durable readback.** A cached result written before output truncation was
tracked (`used=true` + `evidence_truncated=true`) is repaired on read from its
own durable `specialist_results`, then persisted. A cached result that claimed
`output_truncated=true` is relabelled from what the record retained: no reason
surviving means `output_ending_unverified` with the
`legacy_record_unverified` basis; a retained `stop` (or any other
non-truncating reason) means `cached_output_claim_unproven` with no cause
asserted; a retained `length`/`max_tokens`/`model_context_window_exceeded`
remains provider-proven. This makes the retained live replay complete without
a new provider call, and a restart readback returns the same text with zero
synthesis calls and zero dispatches.

**Completion outcome contract (2026-11-14 live failure).**
`generate_response` is a TEXT API: every terminal failure returns a
human-readable string, and direct callers rely on that. `generate_completion`
therefore could not tell an accepted answer from the failure text and returned
`success=True` for both. The live 2,000-token replay exposed the worst case:
Fleet's synthesis call made ZERO provider requests, the handler returned
"every configured provider failed. Last error: no provider attempted", and
the facade published it as `content` with
`success=True`/`provider="deepseek"` (the provider was inferred from the model
name, although no provider answered). Fleet appended its quantitative block
to that text as if it were a valid synthesis.

The EXACT routing cause of that zero-attempt call is **UNCONFIRMED**. The
retained live runtime policy row was never inspected, and an empty ranked pool
(policy, capability, catalog, or window filters), a cooldown/catalog skip, and
"all candidates skipped" all leave `last_error=None`. The first call in the
same process did dispatch and was served, so a process-wide policy exclusion
alone does not explain why the second call differed. This is not evidence for
any one filter, and the routing, policy, cooldown, and breaker behavior was
not weakened to manufacture a live reproduction.

The shared seam is a caller-owned `outcome_sink` (one fresh mapping per
`generate_completion` call), written by `BYOKHandler.generate_response` on
every terminal return:

- the six accepted routes write `success=True` plus the REAL served
  provider/model; `generate_completion` uses only that call-local identity on
  success (never the request alias or a shared handler attribute);
- every failure writes `success=False`, a typed `reason`
  (`all_providers_failed`, `empty_generation`, `no_dispatchable_candidates`,
  `policy_blocked`, `budget_exceeded`, `accounting_blocked`,
  `no_providers_configured`, `trial_restricted`, `no_eligible_providers`,
  `credit_exhausted`, `prompt_blocked`, `generation_error`), a truthful
  message and attempt diagnostics (`last_error`, `last_error_type`,
  `last_finish_reason`, `candidate_count`, `routing`, and the enforcing
  policy's allowed set/revision when relevant);
- `generate_completion` returns the existing structured failure shape
  (`success=False`, zero usage, no served provider/model) with EMPTY
  `content`/`text`; the human message is `error`, and the structured detail
  is `failure`. A retained attempt `finish_reason` (e.g. `length` on an
  empty generation) stays inside `failure.last_finish_reason`; the result's
  top-level `finish_reason` is `None` because no reply was accepted;
- the legacy text API keeps its exact strings for direct consumers. A
  producer that cannot receive the sink, or accepts it and leaves it
  unwritten, keeps the historical `success=True` contract (silence is
  legacy, not a guessed failure).

A zero-attempt result is NOT a provider failure: nothing was dispatched, so
"every configured provider failed" is false. The structured result names the
ROUTING state instead:

- `no_dispatchable_candidates` with `routing="empty_ranked_pool"` when routing
  produced no ranked candidate; the message says the pool was empty;
- `no_dispatchable_candidates` with `routing="all_candidates_skipped"` when
  candidates existed but every one was filtered out before dispatch. The
  retained metadata does not identify WHICH filter skipped them, so the
  message says filtered/unknown and never invents cooldown, catalog, or policy
  as the cause;
- one REPRODUCIBLE zero-attempt control -- an installing policy that allows
  none of the configured providers -- is typed `policy_blocked` /
  `routing="provider_policy_excluded_all"` with `candidate_count=0` and
  `last_error=None`. BPC filters before ranking and the cascade plus the
  last-resort catalog sweep re-check the same policy before transport, so no
  provider is dispatched. The policy is not weakened and no cooldown/breaker
  was touched. This control is NOT evidence of the observed live cause.

Behavior change for other callers: consumers that previously treated the
failure text as content now receive empty content and must read `success`
(and optionally `error`). The chat orchestrator's bounded guard regeneration
treats `success=False` as a failed regeneration so it keeps the already-good
reply instead of replacing it with an empty one; the match-confidence
tiebreaker records a circuit-breaker failure instead of a success. The
Auto-Dev Memento/AlphaEvolve code proposers use their existing failure
fallback instead of persisting/returning empty code. Consumers that already
checked `success` (Fleet, operator loop, lux computer-use, NLU, PDF OCR) keep
their existing failure branches.
Tests:
`backend/tests/test_generate_completion_failure_contract.py` (all providers
failed / zero-attempt policy block / empty `length` generation / budget and
accounting denial / pre-dispatch refusals / accepted identity + stop reason /
legacy text-API and unwritten-sink compatibility / one shared handler with
concurrent accepted, failed and empty calls); plus
`backend/tests/test_fleet_synthesis_truncation_contract.py` (complete /
truncated / missing finish_reason / provider failure / evidence-vs-output /
cached readback / legacy durable repair / unproven-label relabel /
cached twins for no retained reason, retained `stop`, retained `length`, and
retained `model_context_window_exceeded` /
wrapper propagation / valid concise and elliptical negative twins /
complete label and particle-imperative negatives / explicit-reason precedence /
potential concurrency twins for a real sink producer, a `**kwargs` wrapper that
ignores the sink, a narrow legacy handler, and non-introspectable/positional-only
callables / blank-reason normalization / structured provider-failure
withholding) plus the existing `tests/test_fleet_final_synthesis.py` contract.
