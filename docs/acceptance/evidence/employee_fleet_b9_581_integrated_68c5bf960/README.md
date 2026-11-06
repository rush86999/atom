# Fleet integrated repair — B9/581 outcome, scope, cache and execution identity

Status: **submitted for independent verification.** This is the single
successor to the submitted ORCH-07 (`b9ba56995`) and ORCH-02 (`581654d21`)
slices, addressing the verifier's integrated 19-probe batch. Both predecessors
and their evidence remain unchanged.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/fleet-b9-581-integrated-repair-20261105` |
| Accepted ORCH-01 source | `943fb32d7` |
| ORCH-07 predecessor | `b9ba56995` |
| ORCH-02 predecessor | `581654d21` |
| Executed source | `68c5bf960` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite, doubled NLU/specialist transport |
| Live model/provider/browser/sandbox calls | none |

## ORCH-07 repairs

- **Atomic first writer and scope linearization.** `record_fleet_execution_outcome`
  now uses one guarded DML over the exact audit id, execution id, complete
  tenant/workspace/agent scope, `success IS NULL`, and a correlated `EXISTS`
  check of the authoritative `AgentExecution` row. A peer outcome or a moved
  execution matches zero rows; the actual winner is reloaded and compared by
  exact success/error/model/provider material, not the boolean alone. A dirty
  ORM flush cannot follow the CAS.
- **Complete scope.** Decision rows require execution tenant/workspace/agent;
  missing agent is `scope_unverified` with no caller-agent substitution.
  Changed execution agent cannot certify the old decision.
- **Eligible calibration.** Workload stats, recruitment health and automation
  exclude `scope_unverified`/incomplete-scope rows even when success or
  recruitment fields are populated. Historical rows remain for diagnosis.
- **Generation-owned provenance.** Served model/provider comes only from the
  request-owned BYOK route attribution. An earlier handler last-used route is
  not reported for an unserved current call.

## ORCH-02 repairs

- **Chain authorization before cache/read/write.** The delegation chain tenant
  and stored workspace are checked before cache payloads, prompts, dispatch or
  metadata writes. A foreign chain returns no output and mutates neither chain
  nor audit.
- **Exact cache material.** The cache digest preserves the opaque task exactly
  and binds the full roster (id/name/domain/capability score), authorized scope
  and source/teaching/authority basis. Case/punctuation changes and changed
  domains are not the same completed execution.
- **Terminal state first.** A cancelled/failed chain does not return an old
  completed cache; cancellation is explicit non-success with no dispatch.
- **Positive capability.** Domain-specific assignments require a matching
  registry capability/specialty; unknown is a typed capability refusal. An
  explicit generic/general route remains supported.
- **Truthful specialist outcomes.** Explicit failure or a recognized terminal
  failure (`failed/timeout/budget_exceeded/cancelled/error/killed_sandbox`)
  cannot be rescued by a success-looking status; contradictory results are
  failures. Cited names come from the authoritative registry.
- **Canonical execution identity and finalization.** The outer audit bracket,
  `AgentExecution`, fleet decision, specialist context, outcome join and
  returned response share one execution id. The enforced result now runs the
  same shared durable finalizer as the normal path: terminal status,
  `completed_at`, result summary, duration and one outcome join. The audit
  bracket uses truthful success, not `status == "success"` only.

## Controls

- **19 integrated verifier probes: 19 passed on Python 3.14 and 3.11**
  (`probes-314.log`, `probes-311.log`): 7 ORCH-07 binding/scope/provenance and
  12 ORCH-02 chain/cache/capability/finalizer/identity cases.
- **ORCH-07 gate: 65 passed on both versions** (`orch07-gate-314.log`,
  `orch07-gate-311.log`): the original 65 controls, with the enforced response
  assertion adapted to the corrected specialist-consumed contract.
- **ORCH-02 gate: 116 passed on both versions** (`orch02-gate-314.log`,
  `orch02-gate-311.log`): the original 114 controls plus the adapted enforced
  finalization twin and the explicit generic-domain positive twin.
- **Affected fleet/orchestration/chat/outcome selection: 516 passed on 3.14,
  515 on 3.11.** Both have the same 11 baseline failures: 5 pre-existing fleet
  deadlock/route-security controls and 6 pre-existing chat controls, identical
  at `581654d21` (`baseline-affected-314.log`, `baseline-affected-311.log`;
  base: 495 passed, 11 failed on both).
- On 3.11 the combined selection additionally shows
  `test_covpush_w115_chat_orchestrator.py::TestGetQwenResponse::test_success_with_history`
  failing in that order only. It passes alone (`w115-alone-311.log`), passes
  with the new contract files plus all chat files, and is a pre-existing
  order-sensitive chat-history control, not a fleet regression.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment,
  browser or real sandbox operation.
- Specialist transport is doubled; live model quality is not qualified.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.
- Accepted ORCH-01/employee/feedback/wait/admin/memory scopes and historical
  scores remain unchanged.

## Artifacts

`probes-*.log`, `orch07-gate-*.log`, `orch02-gate-*.log`, `affected-*.log`,
`baseline-affected-*.log`, `w115-alone-311.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
