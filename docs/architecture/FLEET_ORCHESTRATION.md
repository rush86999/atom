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
