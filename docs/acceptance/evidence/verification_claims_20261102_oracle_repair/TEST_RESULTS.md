# Verification claims batch 1b — results

Executed source: `6f0acd0bd` (clean).

## Oracle false-pass probes

```text
/private/tmp/test_verifier_oracle_boundaries.py ... 3 passed
```

- missing verification -> refuted
- empty verification -> refuted
- top-level/provider-receipt digest disagreement -> refuted

`oracle_registry.json` lists all six connected mutating actions and the
existing task/workflow verifiers.

## Readback and consumer controls

| Control | Result |
|---|---|
| Applied connected result with verified readback | Oracle verifies |
| Applied result with uncertain/missing/empty/incomplete verification | Refuted; consumer downgrades to uncertain |
| Top-level vs provider-receipt digest disagreement | Refuted |
| Outlook correct draft readback | Applied, verification `verified` |
| Outlook wrong recipients/subject/body | Conflict, mismatches listed, one create only |
| Outlook readback missing | Uncertain, remote id retained, one create only |
| Action consumer with a false oracle pass | Executor step `uncertain` |

## MEM-07 runtime trigger

Real `TaskEvent` tool failure -> episode/segment analysis -> `ReflectionEngine`
-> Memento candidate pending -> review API lists it; agent configuration
unchanged. Covered by `tests/test_memento_candidate_review.py` (2 passed).

## Test totals

| Scope | Result |
|---|---|
| Oracle/team/MEM + independent probes | **29 passed** |
| Connected action/readback neighborhood | **59 passed** |
| Canvas/assignment probes | **42 passed** |
| Canvas focused suite | **127 passed** |
| Assignment regression | **167 passed** |
| Teaching neighborhood | **203 passed** |
| Frontend canvas suites | **7 passed** |

Logs: `oracle-team-mem.log`, `connected-readback.log`, `canvas-probes.log`,
`canvas-focused.log`, `assignment-regression.log`, `teaching-neighborhood.log`,
`frontend-tests.log`.

## Boundaries

No browser/UI rerun is claimed for this bundle. No live provider action. The
Outlook readback uses the production service method with a controlled service
in tests; no send path is touched. TEAM-05 remains the accepted controlled
service mechanism; MEM-07 is closed only at pending-candidate/review, not safe
autonomous application.
