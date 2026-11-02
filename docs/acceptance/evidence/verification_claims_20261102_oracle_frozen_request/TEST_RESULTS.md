# Verification claims batch 1d — results

Executed source: `0f9796401` (clean tree).

## Independent immutable-request probes

`verifier-oracle-immutable-request.py`:

- handler rewrites `arguments["body"]` -> adapter `uncertain`;
- handler rewrites nested `arguments["to"][0]` -> adapter `uncertain`.

Both pass. The authorized request object is unchanged in both cases.

## New table controls

`tests/test_oracle_connected_mutations.py`:

| Case | Expected |
|---|---|
| Unchanged connected request | applied/verified |
| Handler rewrites body | uncertain |
| Handler rewrites nested recipient | uncertain |
| Handler rewrites subject (frozen target) | uncertain |
| Handler rewrites operation id | uncertain |
| Handler rewrites estimate organization id | uncertain |
| Supplied digest != canonical frozen digest | failed before dispatch, handler count 0 |
| Canonical binding unavailable for known connected action | failed before dispatch, handler count 0 |
| Original request after handler mutation | deep-equal to the authorized snapshot |

`tests/integration/test_brennan_joint_real_connected_effect.py`:

| Case | Expected |
|---|---|
| Handler rewrites body + nested recipient, returns self-consistent altered readback | step `uncertain`, one dispatch |
| Operation receipt | remote id retained, reconciliation required |
| Fresh lifecycle/session reload | no second dispatch |
| Reconcile original operation as applied | step applied, still one dispatch |

## Test totals

| Log | Scope | Result |
|---|---|---|
| `oracle-team-mem-probes.log` | oracle, TEAM-05, MEM-07, all probe files | **46 passed** |
| `connected-readback.log` | connected actions, quote/document/real-effect, canvas assignment | **78 passed** |
| `assignment-oracle.log` | assignment routes/executor/quote, oracle confidence, serialization/generic-agent oracle | **217 passed** |
| `canvas-focused.log` | canvas typed/assessment/binding/crud/fork/assignment | **127 passed** |
| `teaching-neighborhood.log` | teaching and conversation learning | **203 passed** |
| `frontend-tests.log` | canvas capability frontend suites | **7 passed** |

Total: **678 passed**, zero failures in the claimed scopes.

## Boundaries

No browser/UI rerun is claimed for this bundle. No live provider action. The
previously submitted request/readback identity checks, TEAM-05 scope and
MEM-07 pending/review scope are carried forward. ORACLE coverage is the six
registered connected mutation classes plus task/workflow verifiers, not a
whole-app dispatch inventory.
