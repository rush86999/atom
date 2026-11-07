# fix(shopify): make completed fulfillment line id authoritative

## Why

Root's permanent probe at `147e66c29` reproduced a false positive: a completed
`Fulfillment.line_items[]` entry could certify a foreign official `id` whenever
the optional `line_item_id` alias was made to match the dispatch plan.

The official completed line `id` is the order-line identity. The optional
`line_item_id` echo must never override it.

## What changed

- Completed line identity now reads official `id` only.
- `id` + matching alias is valid.
- `id` + different alias refutes in both directions and records both values.
- Missing official `id` is unknown, even when an optional alias is present.
- Source `FulfillmentOrder` namespaces remain separate: source `id` is the
  FO-line id, source `line_item_id` is required before POST.
- Producer, receipt, Oracle and durable replay share the same material/plan
  proof.

Added valid id-only, matching id+alias, both contradiction directions, and
missing-identity twins.

## Verification

Actual processes on clean committed source `0556c7478`:

| Phase | Result | Exit |
| --- | --- | --- |
| Failure-first on `147e66c29` | 1 failed | **1** |
| Exact permanent controls | 7 passed | **0** |
| Affected controls | 77 passed | **0** |

The affected 77 are the prior 72 controls plus five new binding twins.

Only the provider HTTP leaf is doubled. Every phase used `TESTING=1`, a fresh
scratch SQLite database, and no live provider/model/server/browser/account/
credential/spend/install action.

Evidence:
`docs/acceptance/evidence/shopify_fulfillment_completed_line_binding_repair_20261107/`

Prior packets are preserved unchanged. Root acceptance remains withheld.

## Finite delivery

A contradictory optional alias can no longer certify a wrong official completed
line, and the legitimate id-only official shape remains valid.
