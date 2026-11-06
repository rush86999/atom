# ORCH-02 / ORCH-07 caller and acceptance map (read-only)

Prepared 2026-11-05 while the ORCH-01 review runs. No inference, provider call
or code change was made for this map.

## ORCH-02 — Fleet Admiral open-ended TASK

### Entry / callers

- `core/atom_meta_agent.py` — `AtomMetaAgent.execute()` TASK/one-off branch
  (fleet-eligible when `len(request) > 40`), calls
  `route_with_governance(..., agent_id="atom_main")`.
- `core/atom_meta_agent.py` — module-level `_route_to_task()` compatibility
  entry (`FleetAdmiral(db, llm)`).
- `core/fleet_admiral.py` — `FleetAdmiral.recruit_and_execute()` performs task
  analysis, recruitment, chain creation and specialist execution.
- `core/fleet_orchestration/` — coordinator, scaling, tracing, progress,
  contracts and task decomposition services.

### Flags and mode

- `ATOM_FLEET_ROUTING_ENABLED` — default ON since 2026-08-21.
- `ATOM_FLEET_ROUTING_FORCE_ENFORCE` — default OFF. OFF means **shadow**:
  recruitment is computed/audited, but the user-visible response still comes
  from Queen → ReAct. ON returns the fleet recruitment result directly.
- Flag off is the exact pre-P1a kill-switch parity path.

### Durable audit

`FleetRoutingAudit` (`core/models.py`, table `fleet_routing_audit`) records
tenant/workspace/agent/execution, workload key, truncated request, chain,
roster, recruitment success, enforced/shadow, error, and the later
outcome-join fields (`success`, latency, actual model/provider).
`record_fleet_decision()` writes the decision; `record_fleet_execution_outcome()`
joins the finalized run. Calibration reads only rows with `success` populated.

### Acceptance gap for a future finite slice

- Needs a configured reasoning model at the served boundary; no cloud key is
  assumed.
- Shadow mode is not proof that the fleet result is user-visible; an enforced
  pilot would need the existing spend/credential/authority boundaries.
- Audit-row acceptance should inspect a fresh DB row (roster/chain/enforced)
  and the joined outcome, not only a returned summary.

## ORCH-07 — governed fleet-routing audit

### Entry / callers

- `core/atom_meta_agent.py` — fleet branch writes `record_fleet_decision()` for
  every fleet-eligible decision (shadow or enforced, success or failure).
- `core/fleet_orchestration/fleet_routing_stats.py` — audit writer, outcome
  join, per-workload calibration, global recruitment health.
- `core/fleet_orchestration/fleet_router_automation.py` — calibration actions,
  approval queue and `FleetRouterAutomationAction` audit rows.
- `core/models.py` — `FleetRoutingAudit` and
  `FleetRouterAutomationAction`.

### Acceptance checks for a future finite slice

1. Run one eligible TASK intent with a controlled transport.
2. Query the fresh `fleet_routing_audit` row: candidates/roster, chosen
   specialists, chain, `enforced`, error and scope.
3. Finalize the execution and verify the same row receives the outcome join.
4. Verify calibration/automation reads only reviewed, success-populated rows
   and never treats shadow recruitment as a live-fleet win.

No ORCH-02/07 inference or evidence campaign was started here.
