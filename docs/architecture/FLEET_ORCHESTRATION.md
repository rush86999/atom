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
