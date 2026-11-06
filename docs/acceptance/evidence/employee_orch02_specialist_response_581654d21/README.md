# ORCH-02 — recruited specialist work reaches the user-visible response

Status: **submitted for independent verification.** This is the bounded
ORCH-02 controlled-consumer slice from the submitted ORCH-07 source. It proves
that an enforced open-ended TASK executes the recruited roster through the
shared `GenericAgent`/`AgentRegistry`/BYOK path and returns a response that
cites the specialists' actual work. The chat handler maps that `final_output`
to the user-visible `message`. Recruitment alone, a shadow calculation or an
audit row is not a pass.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/orch02-specialist-response-20261105` |
| Accepted ORCH-01 source | `943fb32d7` |
| ORCH-07 source (base) | `b9ba56995` |
| Executed source | `581654d21` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite; doubled specialist transport; controlled outputs |
| Live model/provider/browser/sandbox calls | none |

ORCH-07 remains on its own branch/evidence. This slice is a separate successor.

## Product outcome

The enforced `AtomMetaAgent` fleet branch no longer returns the recruitment
summary. It:

1. Takes the recruited roster from the existing `FleetAdmiral` route result.
2. Executes each recruited specialist through the shared `GenericAgent` path
   (the same registry, governance and BYOK machinery used by other agents).
3. Synthesizes a deterministic response from the specialists' actual outputs:
   `Specialist contributions: - <name> (<domain>): <output>` plus a combined
   result.
4. Returns that text as `final_output` and `response`; the chat handler's
   existing `message = result.get("final_output")` mapping makes it the
   user-visible reply.
5. Joins the truthful outcome to the exact ORCH-07 audit row: success only when
   at least one specialist output was consumed; failed/cancelled/no-suitable
   outcomes set `failure_reason` so the chat handler reports failure explicitly.

## Contract

### Execution and scope

- Specialists are resolved from `AgentRegistry` by the roster's `agent_id`.
- Missing, disabled, foreign-tenant or foreign-workspace specialists are
  refused before dispatch and reported as explicit non-success results.
- A roster domain that does not match the specialist's capabilities/specialty
  is refused as `capability_mismatch`; it is not dispatched.
- No new router or employee engine is created; the existing `FleetAdmiral`
  roster and `GenericAgent` execution path are reused.

### Failure, cancellation and duplicate continuation

- A failed specialist is preserved in `specialist_results`; a partial success
  cites the successful work and lists the not-completed specialists.
- All-failed is `specialists_failed` with `success=False` and no fabricated
  citations.
- Empty/missing roster or no suitable specialist is `no_suitable_specialists`
  with an explicit message and `failure_reason=fleet_no_suitable_specialist`.
- A cancellation check stops before the next specialist; the result is
  `cancelled`, `success=False`, with any partial contributions preserved.
- A completed result is cached on the `DelegationChain` by task/chain/roster
  digest; duplicate continuation returns the cached result without re-running
  `GenericAgent`.

### User-visible response and audit

- The controlled chat-handler twin calls the real `_handle_agent_request` with
  the real `AtomMetaAgent.execute`; the returned `message` contains both
  specialists' cited findings.
- The exact ORCH-07 outcome join receives the specialist result:
  `success=True` only when work was consumed; failures set the audit row's
  `success=False` and an explicit error.
- The response carries `failure_reason` for failed/cancelled/no-suitable so the
  chat layer marks the turn failed instead of presenting a false success.

## Controls

- **Controlled ORCH-02 consumer: 10 passed on Python 3.14 and 3.11**
  (`consumer-314.log`, `consumer-311.log`):
  successful two-specialist response; chat-handler user message; partial
  success; all-failed; missing/foreign; disabled; wrong capability; cancellation;
  duplicate continuation cache; empty roster.
- **Focused fleet/ORCH gate: 114 passed on both versions**
  (`focused-314.log`, `focused-311.log`).
- **Affected fleet/orchestration selection: 277 passed, 5 exact baseline
  failures on both versions** (`affected-314.log`, `affected-311.log`). The 5
  are pre-existing fleet-deadlock source checks and Round-20 route-security
  checks, identical at `943fb32d7` (`baseline-5-943fb32d7-314.log`,
  `baseline-5-943fb32d7-311.log`).

## Boundaries

- The specialist transport is doubled in the controlled tests; live model
  behavior/quality is not qualified here.
- The existing recruitment ranking (`RecruitmentIntelligenceService`) is
  preserved and exercised by the existing `FleetAdmiral` tests; this slice
  consumes its roster.
- No live model/provider/credential/spend/send/download/deployment/browser or
  real sandbox operation.
- ORCH-07's audit/outcome contract remains separately submitted; this slice
  changes the enforced outcome from recruitment-only to specialist-consumed.
- PostgreSQL runtime/soak, multi-worker qualification and whole-app ORACLE-01
  remain open.
- Accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 and the
  submitted memory/evolution repairs remain independent.

## Artifacts

`consumer-*.log`, `focused-*.log`, `affected-*.log`,
`baseline-5-943fb32d7-*.log`, `source-tree.txt`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`. `MANIFEST.json` records
the SHA-256 of every artifact and source file.
