# Malformed-effect-metadata successor evidence

Predecessor runtime: `92465014e` (authoritative-scope successor, PR714).
Repair commit: `d240c96ee` on `codex/oracle-registry-verdict-20261107`.
Qualified source: `b0a1f538a` — the additive merge of `d240c96ee` with
`origin/main` `8a577f14a` (which carries the MINI-03/MINI-04 CI steps).
Base: `bae68c91d610`.

Prior evidence under `oracle_registry_gap_20261107/`,
`oracle_registry_authoritative_scope_20261107/`,
`oracle_registry_coverage_20261107/` and
`oracle_registry_coverage_20261107_authoritative_scope/` is preserved
unchanged; those directories are re-hashed in this manifest.

## Independent blocker repaired

`LEAD_PROBES/test_lead_oracle_malformed_effects.py` failed at `92465014e`
(**3 failed / 1 passed**). Each negative committed a real scratch SQLite row
through `_action_registry_adapter` and still returned `applied` with
`oracle_verified=None`:

- `[{"effect": "read"}, {}]`
- `[{"effect": "plan_produced"}, {}]`
- `[{"effect": "read"}, 42]`

Root cause: `effect_entries()` silently dropped non-mapping entries and
`effect_names()` filtered empty names, so a malformed entry disappeared during
normalization. The remaining valid `read`/`plan_produced` entry then satisfied
`declares_read_only()` / `declares_plan_output()`, granting a non-mutating
exemption for an action that really wrote durable state. The action's own
`verification.verified=True` flag was not, and is still not, accepted as an
independent verdict.

## Repair

The existing shared classifier (`backend/core/action_effects.py`) now requires
the **whole raw declaration** to be valid before any read/plan exemption:

- the container must be a sequence (a bare string/mapping is invalid, not
  character/key-wise effect metadata);
- every raw entry must be a mapping or a bare effect-name string;
- every effect name must be a non-empty string drawn from the shared known
  vocabulary (`MUTATING_EFFECTS | READ_EFFECTS | PLAN_EFFECTS`);
- malformed non-mapping entries normalize to an empty entry rather than
  disappearing; an invalid container normalizes to an empty list and an
  explicit `effect_declaration_problems()` reason;
- `declares_read_only()` and `declares_plan_output()` return False when any
  problem exists. A declared mutation still wins, and clean `read` /
  `read_only` / `plan_produced` declarations keep their exemption, including
  `goals.decompose`.

No business names, regexes, registry-wide caller changes or new schema were
introduced. The registry inventory consumes the same helper, so the coverage
matrix keeps its existing surface boundaries.

## Added permanent controls

In `backend/tests/test_oracle_registry_verification_gap.py`:

- actual-adapter + real scratch SQLite negatives for read/plan mixed with a
  missing entry, a non-mapping entry, a blank name, a null name, a non-string
  name and an unknown name — each asserts the row landed and the outcome is
  `uncertain` with `oracle_verified=False`;
- clean read / read_only / plan positives through the same adapter, still
  `applied` with `oracle_verified=None`;
- helper matrix negatives for string/mapping containers and malformed entries;
- bounded-semantics positive for valid declarations and mutation precedence.

The CI control step already runs this file, so the controls are permanent.

## Qualification (`b0a1f538a`, clean tracked tree at gate time)

Fresh owned basetemp children under
`<scratch>/opencode/oracle-malformed-final-20261107/` (never a retained world):

- supplied malformed probe: **4 passed** (was 3 failed / 1 passed at
  `92465014e`);
- supplied missing-verifier + authoritative-scope probes: **7 passed**;
- CI control step: **185 passed** (predecessor 166 + 19 new tracked controls);
- original 173 gate remains a subset: 7 supplied probes + 166 predecessor
  controls. With the 19 new controls and the 4 malformed probes the combined
  successor selection is **196 passed**;
- affected 20-file cluster: **761 passed, 9 pre-existing unrelated failures**
  (unchanged paths; see `baseline-unrelated-failures.txt`). The two
  mini-app harness failures recorded at the predecessor are gone because the
  additive merge includes `origin/main`'s harness repair.

Measured logs are stored beside this file; private paths are replaced with
`<repo>` / `<scratch>`.

## Registry snapshot at qualified source

`coverage/inventory.json` (regenerated with the same helper):
90 registered actions, 26 declared mutations, 15 covered, 11 explicitly
uncovered, 0 undeclared, 1 plan-output validator covered. This is unchanged
from the predecessor and is not a whole-app ORACLE claim.

## Boundary

Closes the malformed/missing/unknown effect-entry fail-open in the shared
classifier. Does not qualify uninspected HTTP CRUD variants, provider writes
without readback, or the whole app. No live provider/VM/model/app/account
effect; no force push, merge approval or self-acceptance. Root owns PR714
metadata/review/merge.
