# Agent 2 commercial readback verification contract

This contract separates two facts that were previously conflated:

| Fact | Question | If false |
|---|---|---|
| Effect observation | Did the provider create a remote object? | `proven_not_applied` or `uncertain`; never a success |
| Desired-state verification | Does the remote object match the complete authorized request? | `incomplete` or `mismatch`; never a second create |

A remote id plus a matching total is **not** verified. It is incomplete until
every material field is present and equal.

## Result envelope

```json
{
  "status": "success|conflict|uncertain|duplicate|error",
  "success": true,
  "action_result": "applied|proven_not_applied|uncertain|conflict|unavailable",
  "provider": "zoho_books",
  "operation": "create_estimate",
  "remote_id": "provider-object-id",
  "payload_sha256": "authorized payload digest",
  "provider_receipt": {
    "operation_id": "...",
    "authority_reference": "...",
    "payload_sha256": "...",
    "remote_id": "...",
    "observed_remote_id": "...",
    "readback_attempts": 1
  },
  "verification": {
    "effect": "observed",
    "status": "verified|incomplete|mismatch",
    "checked_fields": ["..."],
    "missing_fields": ["customer_id", "line_items[0].rate"],
    "mismatches": [{"field": "...", "expected": "...", "observed": "..."}],
    "provider_managed_fields": ["estimate_id", "estimate_number", "line_item_id"],
    "normalization": {"decimals": "...", "dates": "...", "lines": "..."},
    "observed_remote_id": "..."
  },
  "conflicts": ["human-readable mismatch messages"]
}
```

- `applied` only when `verification.status=verified`.
- `conflict` when the effect was observed and a material field differs.
- `uncertain` when the effect was observed but the readback is incomplete,
  unavailable or contradictory.
- `proven_not_applied` only when no provider effect was attempted or a trusted
  pre-dispatch failure occurred.
- A created object with a sparse readback is never `proven_not_applied`.

## Material fields

Estimate:

- organization (request-scoped; compared when the provider echoes it),
- estimate id (effect observation),
- customer id,
- currency,
- document date,
- reference number,
- total, subtotal, tax total and discount total when supplied,
- line identity, quantity, rate, account id, unit/pack, discount and tax,
- explicit terms when the caller supplied them.

Bill:

- organization (request-scoped; compared when echoed),
- bill id (effect observation),
- vendor id,
- currency,
- document date and due date,
- reference/bill number,
- total, subtotal, tax total and credit/discount total,
- line identity, quantity, rate, account id, unit/pack, discount and tax.

Provider-managed fields (`estimate_id`, `estimate_number`, `bill_id`,
`line_item_id`, timestamps) are recorded but not required to equal caller
input. Generated numbers are not treated as the caller's reference.

## Normalization

- Money/quantity: `Decimal(str(value))`; numeric equality ignores trailing
  zeros (`5 == 5.00`).
- Dates: ISO date; time and `Z` are dropped.
- Currency: upper-case ISO code.
- Identifiers: exact provider/customer/item ids; no substring matching.
- Lines: canonical multiset keyed by stable item id (or exact normalized name
  only when the caller supplied no item id). Order is ignored; duplicate lines
  are preserved.
- Discounts: `discount_percent`/provider percentages are percentage points
  (`5`); `discount_rate` from `quote.calculate` is a fraction (`0.05`).
  `discount_amount` is an amount. Equivalent percentage/amount formulas are
  accepted; an ambiguous mode is incomplete.
- Text: trim and collapse whitespace. Names/terms are otherwise compared
  exactly; whitespace normalization is not permission for semantic drift.

## Missing versus mismatch

- Expected material field absent from the readback -> `incomplete`.
- Expected field present but different -> `mismatch`.
- All material fields present and equal -> `verified`.

If the first readback is sparse, the action performs one bounded read of the
**same remote object** and never repeats the create. A definite mismatch is
returned immediately.

## Safe recovery

- The remote id, payload digest, operation id and authority reference are
  retained in every result, including incomplete/mismatch.
- Dependent actions remain blocked by the executor's `uncertain`/`conflict`
  outcome; no replacement object is created.
- Reconciliation re-reads the same remote object. An identical repeated
  request may replay a verified result; a conflicting payload under the same
  durable operation identity is refused by the executor's operation record.
- Restart during reconciliation keeps the same operation and remote id; the
  action never infers "not applied" from a missing remote id in a mutation
  response.

## Controls

`backend/tests/unit/test_brennan_commercial_readback.py` covers id+total only,
wrong customer/currency/date, wrong item with the same total, wrong
quantity/rate with the same total, missing/extra lines, changed discount/tax,
equivalent decimals, equivalent percentage/amount discounts, reordered lines,
duplicate lines, sparse bills and full bill matches.

`backend/tests/unit/test_brennan_agent2_connected_operations.py` covers
action-level sparse readback (`uncertain`, no second create), wrong line
(`conflict`, remote id preserved), sparse-then-full retry (one create, two
reads) and bill sparse readback.
