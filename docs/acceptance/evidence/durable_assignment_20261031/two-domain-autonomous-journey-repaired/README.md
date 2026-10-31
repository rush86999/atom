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
- one **1-use** grant per domain, consumed once (`usedOnce: true`,
  `covered: true` in the runner's check details). Grant counters are runtime
  state; they are not persisted in the world database, so the assertion is the
  live check output rather than a post-hoc table read.

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
