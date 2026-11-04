# Held-out two-domain batch — bounded model-timeout result 6bc97759284

Status: **the held-out content batch did not complete. The wait, independent
quote (96.30 USD), process restart and same-job receiving answer succeeded,
but the local model did not produce the dependent reconciliation before the
bounded reasoning deadline. The job remains blocked with the required
business result unresolved and no report artifact. This is a model-quality/
timeout boundary, not an identity or completion false pass.**

## Held-out content and independent arithmetic

New identifiers and values, not used in the accepted episode:

| Item | Value |
|---|---|
| Purchase order | PO-7302, vendor V-41 |
| Invoice | INV-4491, qty 3, unit price 42.50, freight 12.75, USD |
| Receiving | qty 3, version rec-h1 |
| Price rows | E 4 x 17.25; F 2 x 9.90; taught freight 7.50 |
| Expected quote | **96.30 USD** (69.00 + 19.80 + 7.50) |
| Expected reconciliation | **140.25 USD** (127.50 + 12.75) |

## Observed sequence

1. The served model selected the PO-7302 receiving wait and the independent
   quote calculation; the quote receipt is **96.30 USD**.
2. The application was stopped and relaunched on the same world and source.
   The wait correlation and pending requirement were retained.
3. The authorized receiving record was added and the exact reply accepted;
   the wait applied and the requirement remained unresolved.
4. The model adaptation after the answer timed out at the bounded deadline
   (first 180s, then an explicit 300s retry). The journal records
   `deadline_exceeded: initial` and `deadline_exceeded: compact`, profile
   `employee_adaptive_planning`, pinned `ollama/llama3.1:8b`, no served
   route. No model substitution or hidden retry was used.
5. The job remained `blocked`; no invoice reconciliation was applied and no
   artifact was published. Useful quote receipt and the accepted answer were
   retained.

## Checks observed

| Check | Result |
|---|---|
| Wait survived restart, same identity | pass |
| Independent quote 96.30 | pass |
| Same-job receiving reply accepted | pass |
| Dependent reconciliation 140.25 | **not produced** |
| Business result satisfied | **no** |
| Requested report published | **no** |
| Raw attempts and routing boundary | `attempts-start.jsonl`, `attempts-restart.jsonl` |

## Boundary

- This batch does **not** establish held-out completion, two-domain
  qualification, general model judgment or full G5.
- It does not change the accepted episode at `70a74cd02b5` / `4fd8951cc`.
- No cloud/live provider, credential, consent, send, spend, download or
  deployment was used; the configured local model was not replaced.
- Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 are
  unchanged.
