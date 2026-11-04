# Exact-run UI continuation — source ec2d9dbf0

Status: **the normal UI continuation now resolves the retained authorized
source scope exactly once. The captured `/from-objective` request selected
three authorized documents; the returned run read exactly three and reconciled
270.00 completed.**

## Source and run

| Item | Value |
|---|---|
| Product source | `ec2d9dbf0` (retained authorized source scope) |
| Harness successor | `7c9f1cdf2` (exact-run polling fallback) |
| Frontend build | `cf840c14d` UI build, `BUILD_ID=Sqe_aXJSKB66cAJQ3fniG` |
| World | `backend/data/acceptance_worlds/g5-ui-exact-final` |
| Returned run | `67b4cd87-f589-4a8a-bdac-6a8cd05eeae9` |
| Request status | HTTP 200 |
| Selected authorized sources | 3 |
| Read steps | 3 documents, no duplicate reads |
| Final | **completed / satisfied**, `invoice.reconcile = 270.00` |

## What was captured

- The actual `/api/assignments/from-objective` request body: three document
  source references with resource/version identities.
- The response status and returned `run_id`; all subsequent checks are bound
  to that ID.
- The model adaptation round: `invoice_reconciliation` adopted and executed
  after the three reads.
- Exact steps and result value in `final.json`.
- Raw dispatch/parsed/raw model events in `attempts.jsonl`.

The earlier accepted browser episode at `cf840c14d` (quote 370.00,
procurement question/restart/recovery 270.00, cancellation) remains unchanged.

## Boundaries

This short continuation establishes retained-scope evidence retrieval and
same-run reconciliation. Independent branch progress, changing qualifications/
selective retention, requested artifact/proposal output, late-response refusal
and served controlled uncertainty on this integrated browser run remain
separate gates. Full G5 remains open. No live/cloud provider, credential,
consent, send, spend or deployment was used. Historical 111/123, planner 5/5,
goal router 1/2 and alignment gap 3.0 unchanged.
