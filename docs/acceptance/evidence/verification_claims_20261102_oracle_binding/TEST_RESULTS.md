# Verification claims batch 1c — results

Executed source: `45d015fa3` (clean tree).

## Independent false-pass probes

`verifier-oracle-boundaries.py` (original three) and
`verifier-oracle-repair-boundaries.py` (three added) both pass:

- missing, empty or malformed verification -> refuted;
- top-level/provider-receipt digest disagreement -> refuted;
- oracle exception after dispatch -> consumer `uncertain`;
- returned digest cannot replace the expected request digest -> `uncertain`;
- draft readback with a different object id -> not `applied`.

## Full adjacent matrix

Covered in `tests/test_oracle_connected_mutations.py`:

| Case | Expected |
|---|---|
| Correct bound state | verified |
| Missing/empty/malformed verification | refuted |
| Mismatch/incomplete status | refuted |
| Explicit missing/mismatch lists | refuted |
| Receipt, expected or verification digest drift | refuted |
| Short or non-hex digest | refuted |
| Missing/wrong remote id | refuted |
| Partial/unknown coverage | refuted |
| Empty or sparse material fields | refuted |
| Wrong/missing target identity | refuted |
| Wrong/missing operation identity | refuted |
| Wrong/missing organization identity | refuted |
| Wrong/missing provider identity | refuted |
| Missing read receipt or provider receipt | refuted |
| Verifier raises / returns `None` | consumer `uncertain` |
| Read-only action with refuted verifier | remains read outcome |

## Readback controls

- Estimate readback of a different provider object -> `conflict`, one create.
- Bill readback of a different provider object -> `conflict`, one create.
- Outlook wrong object id with matching content -> `conflict`, one create.
- Outlook missing object id -> `uncertain`/`incomplete`, requested id not
  invented as observed; one create.
- Outlook sparse material fields -> `uncertain`/`incomplete`, one create.
- Outlook material mismatch -> `conflict`, one create.
- Outlook correct same object -> `applied`/`verified`, no send.

## Runtime reconciliation

Real registered estimate handler, controlled provider transport:

1. one create and one successful readback;
2. oracle raises after dispatch;
3. executor marks `uncertain` with remote id and reconciliation required;
4. dependent draft remains blocked;
5. fresh lifecycle/session reload performs no second create;
6. reconcile the original operation as applied;
7. dependent draft becomes approvable, is created once, read back and applied;
8. no send occurs.

## Test totals

| Log | Scope | Result |
|---|---|---|
| `oracle-team-mem.log` | oracle, TEAM-05, MEM-07, probes | **36 passed** |
| `connected-readback.log` | connected actions, quote/document/real-effect, canvas assignment | **77 passed** |
| `assignment-oracle.log` | assignment routes/executor/quote, oracle confidence | **188 passed** |
| `canvas-focused.log` | canvas typed/assessment/binding/crud/fork/assignment | **127 passed** |
| `teaching-neighborhood.log` | teaching and conversation learning | **203 passed** |
| `serialization-generic-oracle.log` | serialization budget + generic-agent oracle path | **29 passed** |
| `frontend-tests.log` | canvas capability frontend suites | **7 passed** |

Total: **667 passed**, zero failures in the claimed scopes.

## Pre-existing unrelated failures

The broader `tests/test_covpush_genericagent.py` module has pre-existing
`SimpleNamespace.model_dump` failures on the same Python/runtime at the
previous source `22e7ab10a`; the oracle-specific generic-agent path
(`tests/test_covpush_w31_generic_agent.py`) passes. Those failures are not part
of this claim and were not introduced by this batch.

## Boundaries

No browser/UI rerun is claimed for this bundle. No live provider action. The
Outlook and commercial readbacks use production service methods with controlled
providers in tests. TEAM-05 remains the accepted controlled service mechanism;
MEM-07 remains pending-candidate/review only. ORACLE coverage is the six
registered connected mutation classes plus task/workflow verifiers, not every
application dispatch surface.
