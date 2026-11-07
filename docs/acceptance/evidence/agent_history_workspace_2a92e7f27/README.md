# Agents history and readback workspace scope

Executed source: `4aef8e318e223df308993355a54dbd95fba8d91c` (branch
`codex/agent-history-scope-20261107`, based on main `accc53347`). The
implementation checkpoint is `2a92e7f27`; `4aef8e318` adds the authoritative
role and unavailable-authority controls.

The supplied confirmed negative at `dd871b2c6f771466eedea1b7e62866189b0273ee`
showed a real member in workspace `ws1` receiving a `ws2` AgentExecution
`result_summary` from `GET /api/agents/history`, while the member's own `ws1`
row was also present. Root captured 1 failure, actual exit 1 in 2.41s. The
original probe, spec, log and exit file remain immutable at
`/private/tmp/test_lead_agent_history_workspace.py` and
`/private/tmp/root-agent-history-workspace*`; their hashes are recorded in
`verification.json`.

## Repair

`GET /api/agents/history` now scopes by the execution's frozen
`workspace_id`/`tenant_id`, not by the agent's current workspace. Moving an
agent does not relabel an old result. A missing execution workspace stays
unknown; it is never assigned from the caller or the agent. Personal/null
compatibility applies only to an authoritative personal principal and never
becomes an unfiltered read. A contradictory real tenant is excluded.

The same bounded read scope now covers the existing Agents list, detail,
status and graduation-progress methods. Shared personal/`default` registry
agents remain visible; peer-workspace and foreign-tenant agents do not. The
current User is re-read from the database (active/status/role/workspace) for
every read, so a stale token object, moved principal or deactivated account
cannot authorize a read. No read creates a job, effect, audit receipt or
claim.

History storage failure is now an explicit `503 AGENT_HISTORY_UNAVAILABLE`
instead of a successful empty list. List failures no longer echo raw internal
text. Existing public response shapes are preserved where the row is visible.

## Controls and results

- New failure-first public-route contract:
  `backend/tests/test_agent_read_scope_contract.py`.
  Before the fix it was 1 passed / 8 failed; at executed source it is
  **11 passed**, actual exit 0 (`contract.log`, `contract.xml`).
- Supplied counterexample rerun at executed source:
  **1 passed**, actual exit 0 (`supplied-probe.log`, `supplied-probe.xml`).
- Focused preservation suite (read contract, history route, full agent route
  coverage, replace/admission writes):
  **119 passed**, actual exit 0 (`focused.log`, `focused.xml`).

Controls include own current-workspace history, peer-workspace absence,
same-tenant foreign workspace, foreign tenant, legacy personal/`default`
positive, missing workspace exclusion, contradictory tenant exclusion, frozen
old-workspace result after agent movement, stale moved principal, deactivated
stale principal, stale persisted role, unavailable authority store, admin
current-workspace positive, and no-effect read/job readback.
Detail/status/graduation peer and foreign agents answer 404 while shared and
current-workspace agents remain readable.

## Scope boundary

Scratch SQLite and controlled authentication leaf only; no live dev DB/world,
model, provider, credential, spend, send, download or deploy. UI worker
`84915` job GET/frontend ownership and Agent2 assignment/employee ownership
are untouched. No new authorization store/router or broad administrator /
`default` bypass was added. This is not a full-app acceptance claim.
