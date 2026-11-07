# Shared ORACLE registry verification gap — evidence

Source base: `bae68c91d610` (`codex/oracle-registry-verdict-20261107`).
Code/tests/CI commit: `bb807d62d58eb9a3e84a59f8598857e74358d5ac`.
Final qualification ran with a clean tracked tree at that commit (only
untracked LEAD/PR files remained).

## Defect reproduced at base

- `LEAD_PROBES/test_lead_oracle_missing_verifier.py`:
  `test_mutation_without_independent_verifier_cannot_certify_applied` failed
  (1 failed, 1 passed). A declared `write` with no verifier committed a row to
  scratch SQLite and the adapter returned `applied` with
  `oracle_verified=None`; the read-only twin passed.
- Real registered `mini_app_set_tests` probe (ported to
  `backend/tests/integration/journeys/test_oracle_registry_mutation_journey.py`):
  the real RPC scaffold + real handler wrote `MiniApp.manifest["tests"]`, and
  the adapter returned `applied` with `oracle_verified=None` because the
  registration declared `effects=[]` and had no verifier.

## Repair

- `backend/core/action_effects.py` is the shared trusted effect vocabulary
  (`local`/`external` scope; plan/read distinction). Empty or unknown metadata
  is unqualified, not an implicit read proof.
- All 90 baseline registered actions now declare effects. Real local and
  provider writes (canvas, tasks, goals, mini-app, Shopify, radio, BPE) are
  explicit; `_LOCAL_MUTATING_ACTIONS` remains as the legacy compatibility
  guard.
- `_action_registry_adapter` freezes a server-owned request digest and
  operation id before dispatch. A declared mutation that is already
  dispatched cannot return `applied` when the verifier is missing, disabled,
  returns `None`, raises, or refutes. It becomes `uncertain`, keeps remote and
  operation identity in the execution/receipt, blocks dependents and is not
  resent.
- `mini_app_set_tests` now uses an exact-prior-manifest CAS (SQL NULL / JSON
  null / empty object / full object), appends a `CanvasAudit` receipt bound to
  app id + tests digest + operation id + tenant + workspace + actor, and has an
  independent verifier. A peer manifest change returns a truthful
  `proven_not_applied` conflict with no audit row.
- CI adds a shared ORACLE registry-verification step; existing MEM/alignment/
  utility/workflow/mini steps are untouched.

## Final verification

Fresh basetemp root:
`<scratch>/opencode/oracle-final-20261107-a` (new child `pytest-*` per run).

- Supplied missing-verifier probe: **2 passed**.
- CI step (`test_oracle_registry_verification_gap.py`,
  `test_oracle_effect_families.py`, `test_oracle_connected_mutations.py`,
  `test_assignment_executor.py`, real mini-app journey): **156 passed**.
- Affected-cluster run: **631 passed, 11 pre-existing unrelated failures**
  (listed in `baseline-unrelated-failures.txt`; their code paths are not in the
  reparsed diff).
- Baseline focused oracle/canvas/mini suites: **131 passed**.
- Baseline `tests/test_assignment_executor.py`: **107 passed**.

## Registry/verifier snapshot

`docs/acceptance/evidence/oracle_registry_coverage_20261107/` is generated from
the actual 90-action import surface (`core.action_registry` +
`core.connected_actions`) at `bb807d62d`:

- 26 declared mutations: 15 covered, 11 uncovered.
- 10 external/provider mutations: 6 covered.
- 16 local durable mutations: 9 covered.
- 0 undeclared actions after this repair.
- `goals.decompose` remains plan-output validation, not a mutation.

Uncovered declared mutations (explicit, not a whole-app ORACLE completion
claim): Shopify product/blog/article/fulfillment creates; `mini_app_scaffold`,
`mini_app_write_logic`, `mini_app_publish`, `mini_app_install`, `mini_app_run`,
`mini_app_db_write`, `mini_app_revert_logic`. Through the assignment adapter
these are `uncertain` after dispatch, never applied.

## Boundary

This slice closes the shared registered-action fail-open and the real legacy
`mini_app_set_tests` classification/receipt gap. It does not qualify
uninspected HTTP CRUD variants, external provider writes without readback, or
the whole app. No live DB, world directory, install, credential, model,
provider, VM or network call was used.
