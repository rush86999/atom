# Verified agent PUT replacement — nullable-material repair successor

Status: **resubmitted for independent verification.** PR
[#681](https://github.com/rush86999/atom/pull/681). This is the successor to
`employee_agent_replace_7503171ec` after the confirmed nullable-material
regression. No merge or deployment was performed.

## Confirmed regression and repair

The first submission compared `configuration` and `schedule_config` through an
`or {}` coercion. Unchanged rows stored as SQL NULL or JSON null were therefore
refused as `STALE_TARGET`. The supplied external probe
`/private/tmp/test_verifier_replace681_nullable_material.py` failed six of
seven cases on `7503171ec`; it passes **7/7** on this successor.

The repair:

- loads the ORM row and the physical nullable JSON in one snapshot;
- binds `IS NULL` for physical SQL NULL and the raw JSON text for JSON null;
- keeps null and empty-object material digests distinct;
- compares explicit changes exactly;
- preserves the exact-material negative twins and scheduler no-duplicate
  rules.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-agent-replace-20261106-v2` |
| Base main | `33b8d6472605b7fbb4c84a9e21286c3d168b7d5c` |
| Executed source | `51d7d782198cb279b0d6dcd50dec554b45da135a` |
| Original submission bundle | `employee_agent_replace_7503171ec` (restored) |
| Runtime | real scratch SQLite; no live model/provider |

## Verification

| Gate | Candidate | Main `33b8d6472` |
|---|---|---|
| Focused, 3.14 | **80 passed** | — |
| Focused, 3.11 | **80 passed** | — |
| Nullable external probe, 3.14 | **7 passed** | 7 passed (verifier baseline) |
| Affected, 3.14 | **376 passed, 3 skipped, 2 failed** | 358 passed, 3 skipped, 2 failed |
| Affected, 3.11 | **358 passed, 1 failed** | 340 passed, 1 failed |

The successor adds the 8-case nullable/empty matrix to the original 10
controls: **18 replacement controls, zero new failures**. Shared baseline
identities remain:

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` (both)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` (3.14 only; 3.11 lacks `schemathesis`)

## Evidence delivery

- The original bundle’s eight previously ignored artifacts are now tracked and
  match its manifest hashes (12/12).
- This successor bundle contains the source hashes and 13 artifacts for
  `51d7d7821`, all forced into Git after checking for secrets.
- No historical log was regenerated; the original bytes are retained.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment or
  scheduler execution.
- No new table or migration; PostgreSQL/soak and multi-worker remain
  unqualified.
- No merge or deployment; code-owner review remains required.
