# ORACLE-01 — scoped memory current-authority repair

Status: **submitted for independent verification.** This is the bounded repair
of the verifier's six authority negatives on the submitted scoped-memory
family. The durable storage, exact-document CAS, namespace isolation, audit and
replay controls from `aab2b620d` remain. The six supplied probes now pass, and
the active/current-scope twins are in the ordinary regression.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-memory-write-20261105` |
| Prior submitted source | `aab2b620d` (product `4a32ce30b`, evidence `fa651e165`) |
| Executed repair source | `88ee1e901` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; two-session authority interleaving |
| Model/provider/browser calls | none |

## Verifier finding and repair

The request-entry `User` object was only a snapshot. `_actor_snapshot` resolved
its tenant and checked only a nonempty id. A concurrent deactivation or tenant
reassignment after the current document read could still let store, context
merge and delete commit under stale authority. The target document CAS protected
the document from another writer but not authority from revocation.

The repair:

1. `_resolve_authority(db, actor)` reads the authoritative `User` row and
   freezes `id`, `status`, `is_active`, raw `tenant_id`, effective personal
   scope (via the existing `resolve_tenant_id` policy), email and role. Missing
   or inactive principals are refused before any effect.
2. After the current memory document read and before the first target DML,
   `_claim_authority(db, authority)` executes a guarded no-op `UPDATE User`
   binding the frozen id/status/is_active/raw tenant in the **same transaction**
   as the target CAS and `AuditLog` receipt.
3. A zero-match rolls back all attempted state, preserves the peer authority and
   prior memory/context, appends no audit, and returns `AUTHORITY_CHANGED`
   (409, `effect=none`). No target or audit commit survives.
4. Replay responses are authority-checked before they can report
   `already_applied`; changed authority refuses with no effect.
5. Scoped reads use the same current-principal resolution, so a deactivated or
   reassigned caller cannot read the old scope. A bootstrap tenant-less user
   keeps the existing `default` personal fallback.

## Exact negatives and twins

The six supplied public-route two-session probes are
`/private/tmp/test_verifier_memory_aab2_authority.py`:

- store / context / delete crossed with actor deactivation and tenant move;
- each changes the `User` row after the current document read and before the
  write;
- each must return 401/403/409, leave the `TenantSetting` rows byte-identical,
  and add zero audit rows.

All six pass on the repair source (`verifier-probes-314.log`).

In-repo twins in `tests/test_memory_authority_contract.py`:

- the same six two-session negatives;
- deactivated actor before the initial call (403, no effect);
- moved actor before the initial call (old scope untouched; current-scope write
  is explicit);
- same-operation replay under unchanged authority (`already_applied`) and
  under deactivation (403) / tenant move (409 `OPERATION_CONFLICT`);
- bootstrap tenant-less user resolves to the stable `default` scope;
- fresh-session reads after deactivation return 404/empty/zero.

## Controls

- **Focused memory gate: 87 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): the original 74 controls plus 13
  authority/current-scope twins.
- **Affected memory/TenantSetting/audit selection: 678 passed, 1 skipped, 7
  exact baseline failures on both versions** (`affected-314.log`,
  `affected-311.log`). The 7 are the same 6 unrelated w79a MiniApp/Office
  controls and 1 pre-existing AgentMemory consolidation isolation control named
  in the prior memory evidence. The timing-sensitive
  `test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`
  is excluded from the frozen affected selection; it passes in the same
  selection on Python 3.11 and is a known order-sensitive baseline flake.
- **Baseline: 665 passed, 1 skipped, 7 failures** at the accepted admin base
  selection without the 13 new authority tests (`baseline-314.log`,
  `baseline-311.log`). The branch adds exactly 13 passing controls; the failure
  lists are identical.

## Boundaries

- Same bounded key/value and session-context family; no new table, migration or
  authorization engine.
- No LanceDB/AgentMemory/ingestion/webhook surfaces.
- No live model, provider, credential, spend, send, download, deployment or
  browser operation.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.
- Accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 and the
  submitted tool-mutation review branch are independent and not merged.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `verifier-probes-314.log`,
`source-tree.txt`, `README.md`, `TEST_RESULTS.md`, `verification.json`,
`routes.json`. `MANIFEST.json` records the SHA-256 of every artifact and source
file.
