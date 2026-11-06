# Scoped-memory current-authority repair — test results

Executed source: `88ee1e901` (prior submitted `aab2b620d`, product
`4a32ce30b`, evidence `fa651e165`). Runtime: scratch SQLite with fresh
sessions; two-session authority interleaving. No live model/provider/browser
call.

## Verifier probes

`/private/tmp/test_verifier_memory_aab2_authority.py` — 6 public-route
two-session negatives (store/context/delete × deactivate/tenant move):

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **6 passed** | `verifier-probes-314.log` |

Each probe asserts response 401/403/409, byte-identical `TenantSetting` rows
and zero new `AuditLog` rows.

## Focused gate

Command (same selection on both versions):

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_memory_write_contract.py \
  tests/test_memory_authority_contract.py \
  tests/test_covpush_w10d_routes.py::TestMemoryRoutes \
  tests/test_covpush_w10d_routes_b.py::TestMemoryTail \
  tests/test_covpush_w79a_api_routes.py::TestMemoryRoutes \
  tests/unit/api/test_memory_routes.py \
  tests/test_round26_memory_security.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **87 passed** | `focused-314.log` |
| Python 3.11 | **87 passed** | `focused-311.log` |

The 87 are the original 74 controls plus 13 authority/current-scope twins.

## Affected selection

Command (same selection on both versions; the known timing-sensitive
`tests/test_integration_audit.py` file is excluded):

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_memory_write_contract.py \
  tests/test_memory_authority_contract.py \
  tests/test_covpush_w10d_routes.py \
  tests/test_covpush_w10d_routes_b.py \
  tests/test_covpush_w79a_api_routes.py \
  tests/unit/api/test_memory_routes.py \
  tests/test_round26_memory_security.py \
  tests/test_memory_store_bootstrap.py \
  tests/test_memory_integration.py \
  tests/test_memory_symmetry_fixes.py \
  tests/test_memory_context_assembler.py \
  tests/test_memory_epistemic_provenance_scoping.py \
  tests/test_memory_p2.py \
  tests/test_memory_consolidation.py \
  tests/core/test_memory_consolidation_bughunt.py \
  tests/integration/services/test_memory_consolidation_multi_tenant.py \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/test_budget_enforcement_service.py \
  tests/test_budget_control.py \
  tests/test_covpush_w104_spend_aggregation.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **678 passed, 1 skipped, 7 baseline failures** | `affected-314.log` |
| Python 3.11 | **678 passed, 1 skipped, 7 baseline failures** | `affected-311.log` |

The 7 are the same 6 unrelated w79a MiniApp/Office controls and 1 pre-existing
AgentMemory consolidation isolation control named in the prior memory evidence.
The failure lists are identical on both versions.

## Baseline

The accepted admin base selection without the 13 new authority tests:
**665 passed, 1 skipped, 7 failures** (`baseline-314.log`,
`baseline-311.log`). The branch adds exactly 13 passing controls and the
failure lists are identical.

## In-repo authority twins

`tests/test_memory_authority_contract.py` covers:

- six two-session authority negatives (same as the verifier probe);
- deactivated actor before the initial call (403, no effect);
- moved actor before the initial call (old scope untouched; current-scope write
  is explicit);
- same-operation replay under unchanged authority (`already_applied`), under
  deactivation (403) and under tenant move (409 `OPERATION_CONFLICT`);
- bootstrap tenant-less user resolves to the stable `default` scope;
- fresh-session reads after deactivation return 404/empty/zero.

## Boundaries

No new table, migration or authorization engine. No live model/provider/
credential/spend/send/download/deployment operation. PostgreSQL runtime/soak,
multi-worker serialization and whole-app ORACLE-01 remain open.
