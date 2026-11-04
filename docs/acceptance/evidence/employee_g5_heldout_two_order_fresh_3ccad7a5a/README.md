# Employee G5 — fresh held-out two-domain batch, both event orders

2026-11-04, America/Toronto.

**Status: held-out content and both required event orders are demonstrated on a
fresh, unseen fixture set at the controlled local scope. Overall successor
bundle acceptance is WITHHELD for combined review: the runtime successor
`5abbeaa48` records both worker repairs (15/15 matrix, 198 affected
regression), and the packaging/source-attribution corrections are included in
this evidence commit. This bundle is evidence, not an acceptance claim.** Two independent employee jobs reached a durable
receiving wait, produced the independent quote, survived a process restart,
consumed the authorized receiving answer, selected the dependent invoice
reconciliation through the narrow typed continuation and published the
requested review document with both verified totals.

This is a finite, declared local campaign. It does not establish universal
employee judgment, live-provider breadth or a whole-app ORACLE claim.

| Item | Value |
|---|---|
| Executed product source | `3ccad7a5a99afdcef7784f903b3744e36d86ea4b` |
| Served model | `ollama/llama3.1:8b` (exact local pin) |
| Frontend | unchanged from the accepted source; no UI change in this batch |
| Focused regression | **133 passed** |
| Named finish checks | **22/22** (11/11 per run) |

## Fresh unseen fixtures

New identifiers and values, independent Decimal oracle, never supplied as a
final plan or expected result:

- Quote rows: `QH-21` 5 × 14.00, `QH-22` 3 × 22.00; taught freight 9.00; tax
  none; expected quote **145.00 USD**.
- Purchase order / invoice: `PO-QH-8100` / `INV-QH-99`; 4 × 25.00 plus freight
  13.00; expected reconciliation **113.00 USD**.
- Authorized receiving record: `PO-QH-8100`, received quantity 4,
  `rcv-qh-1`.
- Requested output: internal review document containing both verified results.

```
quote:          5 * 14.00 + 3 * 22.00 + freight 9.00 = 145.00 USD
reconciliation: 4 * 25.00 + freight 13.00             = 113.00 USD
```

## Event orders and run identity

| Order | What differs | Run | Wait | Quote op | Reconciliation op | Artifact sha256 |
|---|---|---|---|---|---|---|
| 1 | receiving source authorized **before** restart | `cfa9cccf-4049-4f7d-96c8-8d42b4ef48b4` | `await-9ac5fe9af53639aa278b` | `f55964e1-2df6-47bc-9dd3-fd5843ff89d3` | `eb343a12-ac4c-4649-aae2-3661c2c4461e` | `628fe6b1dbba38d7c6228cb667cf10c0cd39e6c8bc8758d72f385aa4d4f76ae7` |
| 2 | restart **while waiting**; receiving source authorized after restart | `88306561-92b4-492c-a6b3-00d0621c3d08` | `await-2a1cf445bfb818525fac` | `44900a74-81aa-4a96-b327-617b97b2b1da` | `7f0981cf-8e1a-4634-b14b-f82a38e40159` | `83d31a97ba8b694ac601e9534e3a281d783ac106996f30ee37febb2dd40775d3` |

Both runs preserved the same run, wait and quote identities across the restart.
Both completed with every business requirement satisfied. The requested
document was applied and contained **145.00** and **113.00** with a matching
sha256. The failed same-job HX continuation remains a separate recovery bundle
(`employee_g5_heldout_continuation_60d464a5f`); it is not reused as this fresh
result.

## Model work and measured cost

All calls used the exact pinned local route. The compact stages used the
separately declared `employee_adaptive_planning_compact` profile; the initial
wait choice used `employee_adaptive_planning`.

| Run/stage | Prompt chars | Seconds | Prompt tokens | Completion tokens | Result |
|---|---:|---:|---:|---:|---|
| order 1, wait | 21,758 | 54.89 | 9,590 | 141 | model chose the durable receiving wait |
| order 1, compact quote | 4,726 | 16.96 | 2,381 | 146 | model chose the quote columns/terms |
| order 1, compact reconciliation after restart | 6,775 | 21.19 | 2,954 | 152 | model chose the invoice role IDs |
| order 2, wait | 21,758 | 48.69 | 9,595 | 143 | model chose the durable receiving wait |
| order 2, compact quote | 4,726 | 16.37 | 2,389 | 156 | first proposal repaired once, then accepted |
| order 2, compact quote repair | 5,657 | 8.43 | 2,637 | 156 | corrected the typed quote |
| order 2, compact reconciliation after restart | 6,775 | 20.15 | 2,955 | 147 | model chose the invoice role IDs |

The expected reconciliation total **113.00** does not appear in any model
prompt. The accepted quote receipt **145.00** is visible in the post-restart
compact context as prior authorized work, exactly as it would be to a real
employee; it is not the dependent expected result.

## What is model-owned vs deterministic

- The served model selected the receiving wait, the quote column mapping and
  taught term keys, and the invoice/purchase-order/receiving role step IDs.
- The compiler built the execution steps, resolved the taught freight and tax
  terms, computed both totals with Decimal arithmetic, verified the receipts
  and composed the requested document.
- No final plan, expected total, oracle row or harness-injected typed request
  was fed to the model.

## Checks and artifacts

`state-order1.json` and `state-order2.json` contain the full run state,
artifact text and **11 true named finish checks** (11/11 per run): `same_run`,
`same_wait`, `restart_preserved_waiting`, `quote_total_145`,
`reconciliation_total_113`, `assignment_completed`, `requirements_satisfied`,
`artifact_applied`, `artifact_quote_145`, `artifact_reconciliation_113`,
`artifact_sha_matches`. The earlier 10/10 summary omitted the separate
`same_wait` check; the historical state bytes are unchanged. Raw model
requests, parsed responses and the one repaired quote are in the four
`attempts-order*.jsonl` files. Server logs are `server-order1.log` and
`server-order2.log`; the review documents are `review-order1.docx` and
`review-order2.docx`. `focused-tests.log` records the same-source 133-test
neighborhood.

## Boundaries

The objective supplied the three relevant authorized source references
(`price-book-fresh.xlsx`, `purchase-order-fresh.json`,
`invoice-fresh.json`). This demonstrates typed role selection and execution
from those sources, not independent procurement evidence discovery/selection
among authorized alternatives or distractors. The earlier negative
source-selection probes `80e3bd702` / `20f3ffc19` remain open.

Controlled local inference only: no live/cloud provider, credential, spend,
send, download or deployment authority. The two runs are a finite declared
campaign on one local machine; they do not prove general adaptive breadth,
live Zoho/Microsoft behavior, Linux/KVM, multi-worker/soak or whole-app ORACLE
equivalence. Overall successor bundle acceptance remains withheld for combined review;
the runtime successor `5abbeaa48` records both worker repairs, and
packaging/source-attribution corrections are included in this evidence commit.
Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 remain
unchanged. Full G5 is not claimed beyond this tested scope.
