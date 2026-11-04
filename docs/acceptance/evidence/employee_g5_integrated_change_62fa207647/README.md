# Integrated employee artifact + real source-version change — source 62fa207647

Status: **one employee job produced a requested DOCX from its own typed quote
calculation, then a revised workbook version (real unit-price change) was
authorized on the same completed job. The served local model chose
`quote_calculation` again from the changed evidence, the compiler added new
steps under a new plan revision, and the affected artifact re-rendered from
the verified receipt. The superseded quote/artifact and an unrelated note
read kept their operation ids and results.**

## Source and run

| Item | Value |
|---|---|
| Product source | `62fa207647` (requested artifact for quote/procurement; version reassessment) |
| Frontend build | `X8jwE6ACQOmwiGXPFjzKD` (`next build --webpack`; UI source unchanged since `f2aa6518d`) |
| World | `backend/data/acceptance_worlds/g5-integrated-change-clean` |
| Run | `f6465719-3cf6-4087-913c-4d0c1b2a1a93` |
| Phase 1 | completed, quote **370.00 USD**, artifact sha `4486b1274c0a9855e6fd4e972eb428e5a4879fb08f20a519daa67ca44e8dfe5f` |
| Phase 2 | completed, quote **425.00 USD**, artifact sha `5d26049c83641f4d155f9c20c0ce7d9f1f6b1294b53fa618ddd4cfadbe419cd2` |
| Model rounds | phase 1 `quote_calculation`; phase 2 `quote_calculation`, `source=model`, `technical_fallback=false` |

## Phase 1 — employee-decided artifact

The ordinary Assignments UI uploaded `price-book.xlsx`, selected the
authorized `price-book.xlsx / Prices` scope, enabled employee-decided work,
requested a **Document**, and supplied only the taught commercial terms
(USD, freight 20.00, tax none). The captured `/from-objective` request
contains no line items, deliverables, steps or totals.

The served local model chose `quote_calculation`, mapped `Item`/`Qty`/`Price`,
and the compiler derived rows through `quote.lines_from_rows` and
`quote.calculate`: A 2 x 100.00 = 200.00, B 3 x 50.00 = 150.00, freight 20.00
-> **370.00 USD**. `requested-artifact` depended on the verified receipt and
rendered the DOCX from durable results.

## Phase 2 — real source change, model-chosen reassessment

The supplier's revised workbook (`A` 100 -> 120, `B` 50 -> 55) was uploaded
through the same normal document route under the same file name. The catalog
superseded the old dataset version and created a new active version of
`upload_price_book__prices`; the run authorized it by
`dataset_name` + `source_version` (`a519254f8ccef6e9d52c3545a63b4c3a3f58926f`).
That version identity is persisted on the new `dataset.read` step and its
verified result.

Because the version belongs to the same business source, the job re-entered
the existing adaptation contract. The model chose `quote_calculation` from
the new step (raw parsed request in `attempts.jsonl` binds `source-3`). The
compiler added `quote-lines-2`, `quote-total-2` and `requested-artifact-2`;
`quote.calculate` produced A 2 x 120.00 = 240.00, B 3 x 55.00 = 165.00,
freight 20.00 -> **425.00 USD**. The artifact re-rendered from the new
receipt only; the superseded 370.00 total is retained in durable history but
not printed in the current customer document.

## Selective retention (independently checked)

| Item | Before | After |
|---|---|---|
| `quote-total` value | 370.00 | 370.00 (same operation `718e4a0e-d480-4ad0-921f-14c756cbe567`) |
| `quote-total-2` value | — | 425.00 |
| unrelated note `source-2` | operation `d963c2b1-5ceb-4cdc-9b82-154870fae9a9` | same operation and result |
| deliverable artifact | sha `4486b1274c0a9855e6fd4e972eb428e5a4879fb08f20a519daa67ca44e8dfe5f` | sha `5d26049c83641f4d155f9c20c0ce7d9f1f6b1294b53fa618ddd4cfadbe419cd2` |

## Checks

All 18 campaign checks pass (`capture.json` -> `phase2.checks`), including:
no supplied line items; revised version authorized and persisted; model (not
technical fallback) chose the quote work; affected quote changed; prior quote
result/operation retained; unrelated note operation/result retained; artifact
revision changed; new total present and superseded total absent; artifact
criterion satisfied.

## Boundaries

- The taught commercial terms are the user's contract terms from the existing
  UI field; the model chose the business operation and column mapping and the
  compiler derived every row/amount from accepted source rows.
- The change is a real workbook unit-price revision, not a reason string or
  constant formula. The reassessment is triggered only for a different version
  of the same business source; unrelated sources stay inert.
- Cancellation/late-response and controlled lost-confirmation remain separate
  regression support in this batch.
- No live/cloud provider, credential, consent, send, spend or deployment was
  used. Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0
  remain unchanged.
