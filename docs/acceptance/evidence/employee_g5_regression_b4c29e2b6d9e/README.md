# Cancellation and controlled-uncertainty regression — source b4c29e2b6d9e

Status: **the already accepted cancellation/late-response and controlled
provider-lost-confirmation controls were re-run unchanged on the integrated
final source. Both normal-application campaigns pass.** They are cited as
regression support only; the branch formulas in the remaining campaign are
deterministic mechanics and are not presented as new adaptive G5 evidence.

## Runs

| Campaign | Report | Result |
|---|---|---|
| Remaining normal app (cancellation, late response, branch retention) | `remaining/report.json` | **18/18** |
| Controlled uncertainty (lost confirmation, restart, reconcile, no resend) | `uncertain/report.json` | **11/11** |

Both serving identities report `source_id=b4c29e2b6d9e`, `dirty=false`. The
remaining campaign runs: artifact `36f07cbb-49f2-476f-9f4c-33f843c9d3fb`, branch
`549b1197-580b-43dd-8924-92dc2e5a1259`, uncertain `2dcbb34d-7144-4e0b-b455-36bf7606907d`.

## Re-used controls

- Cancellation while the carrier wait is open: the assignment is `cancelled`
  and a late external response returns **409**, not a resume.
- Applied branch operation ids and results survive cancellation.
- Controlled outbound: provider acceptance with lost confirmation leaves the
  step `uncertain` and the assignment `blocked`, not completed.
- Process restart keeps the same original operation identity
  (`148ae9bc-8844-4b43-9e21-fd4d0fe371d4`) and creates no second effect.
- Human-authorized reconciliation marks the original operation `applied`, the
  assignment completes, and exactly one controlled effect exists.

## Boundaries

- The remaining campaign's independent branches use harness-authored
  deterministic formula steps; that mechanism was accepted earlier and is not
  re-submitted as evidence-sensitive model work.
- No live provider, credential, consent, send or spend was used; the outbox
  is the environment-gated controlled adapter.
- Full G5 remains open; historical counts are unchanged.
