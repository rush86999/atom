# Final integrated smoke on the repaired execution boundary

Reuses the existing two-domain autonomous journey (`scripts/acceptance/two_domain_autonomous_ui.cjs`)
on source **`b7ee7ee22`** (recorded head `803ef2666`). The earlier journey
bundle predates the execution-boundary repair; this run does not.

## Result — 5/5

| Check | Result |
|---|---|
| Sales starts and waits | pass |
| Grants starts and waits | pass |
| Sales completes under bounded standing authority | pass |
| Grants completes under bounded standing authority | pass |
| Exactly two covered effects, no approval | pass |

## Identity and agreement

- backend PID **43597 → 43717** (real restart while both jobs waited);
- both runs `achieved`; `human_interventions = 0`; `hitl_actions` rows = **0**;
- decision log records `standing authority use for send` and
  `step send covered by standing authority` for both domains.

## Effects and grants

- controlled outbox: **exactly 2** rows — `sales@example.invalid` and
  `grants@example.invalid`;
- one **1-use** grant per domain, consumed once and **durably recorded** at
  `GoalRun.parameters.task_lifecycle.assignment.standing_authority`:

  | Domain | grant_id | max | used | status | usage operation |
  |---|---|---|---|---|---|
  | Sales | `sga-2c58c11bcf4342d6` | 1 | 1 | `exhausted` | `5707b16e…` |
  | Grants | `sga-c212266b61554ec2` | 1 | 1 | `exhausted` | `c98c5678…` |

  Each usage entry names `step_id=send` and the outbox operation id, so the
  grant consumption and the controlled effect are joined by the same id.

## Artifacts

| File | sha256 | bytes |
|---|---|---|
| `sales-sum-the-scotch-parts-total-b5e00538.docx` | `29e3a157774b7107…` | 36,755 |
| `grants-sum-the-approved-applications-92c1b9a2.docx` | `1ad9f45a255fd81b…` | 36,780 |

Full digests are in `artifacts.json`.

## Qualifications that remain explicit

- Hard-cost protection depends on trusted adapters declaring truthful cost
  bounds. It is **not** a universal provider-billing guarantee.
- The controlled outbox is the only opted-in adapter; live autonomous sending
  remains unsupported.
- The model qualification remains failed; hosted deployment remains deferred.

## Files

`two-domain.json` (runner output), `artifacts.json` (effects, grants, hashes),
`outbox.jsonl`, `backend-reset.log`, `backend-restart.log`, `screenshots/`.
`manifest.json` hashes every entry.
