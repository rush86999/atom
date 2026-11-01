# Part A connector entry-point proof

**Result: passed.** This closes the verifier's Part A gap: connector ingestion
now runs through the product API, not a harness that fetches Graph bytes and
calls `materialize_sheet_bytes_sync()` directly.

## Entry point

`POST /api/intelligence/execute` with `action_type="tool"` and
`action_payload.tool_name="email_ingest_message"` (see `request.json`). The
product's `local-tools` registry invoked the mailbox ingestion tool, which
fetched the Outlook message and its two attachments through the connector
pipeline. No bytes or rows were supplied by this request.

Response (`connector-response.json`, 2026-11-01T12:37:20Z):

- `success=true`, `status="ingested"`
- subject `In-Stock Press Brakes Available for Fast Delivery From HARSLE`
- attachments `2`
- message `Email ingested into memory (body + attachments)`

The connector refreshed the existing catalog entry at
`2026-11-01T12:37:20.673857`; `ingested_documents.last_verified_at` is
`2026-11-01T12:37:20.807742` (`dataset-entry.json`). The materialized HARSLE
sheet remains 8 rows, hash `e0a7fb8a…`, in the qualification world's dataset
store.

## Retrieval after connector ingestion

A new assignment (`194b3474-3b96-4890-94f3-9986ad795283`) used that
connector-refreshed source and completed with **216700.00** across 8 rows,
citing `HARSLE press brake stock price list.xlsx / 库存产品`. The independent
read from the accepted Part A evidence is reused (`independent-read.json`):
SHA-1 `e0a7fb8a…`, SHA-256 `5cd746af…`, eight Price values, sum **216700**.

Restart at `a49b854ce660` (`dirty=false`) reopened the completed assignment and
the DOCX (`Total 216700.00`); see `reopen.json` and `artifact.docx`.

## Boundary

Read-only connector path; no source write, send, permission change or
credential rotation. The accepted Part A live evidence remains unchanged; this
addendum only verifies the normal connector entry point.
