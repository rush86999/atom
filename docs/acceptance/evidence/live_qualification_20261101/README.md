# Live qualification — 2026-11-01

**Both authorized live operations executed. Submitted for independent review;
this is not a self-grant of overall acceptance.**

Authorization: the owner replied “i authorize all” to
`LIVE_QUALIFICATION_REQUEST_2026-11-01.md`. Part A and Part B were run
independently against one clean product source and one isolated world. No
deployment, publication or unrelated connector work was added.

## Candidate and configuration

| Item | Value |
|---|---|
| Product execution source | `0aa6105e4872` (clean, `dirty=false`) |
| Restart verification source | `74464af69f98` (script-only normalized-body check; product code unchanged) |
| Frontend build | `qEeLBEVZSyQjyn3v-Wnjh` |
| World | `/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/live_qualification_20261101` |
| Backend / frontend | `127.0.0.1:8071` / `127.0.0.1:3130` |
| Live flags | both `ATOM_ASSIGNMENT_ALLOW_*` set for the authorized run; default restored after |
| Credentials | never printed or stored in this bundle |

## A — Microsoft read-only qualification

Run `0cb8885f-1d30-4080-978a-4fbc5170ef82` (status `completed`).

- Account verified by Graph `/me`: `rish@brennan.ca`
  (`2927f127-c837-4f4b-beac-5c7b723bf887`), tenant
  `8899c7a5-b671-4f16-bb48-15d5e78158af`.
- Existing grant resolved by the normal product token resolver; state `valid`,
  no reconnect, no fallback.
- Genuine source: `HARSLE press brake stock price list.xlsx`, Outlook message
  attachment `In-Stock Press Brakes Available for Fast Delivery From HARSLE`.
- Read-only Graph calls: `/me`, message, attachment list, attachment `$value`.
  No writes, sends, permission changes or credential rotation.
- Bytes: 10,249; SHA-1 `e0a7fb8a…`, SHA-256 `5cd746af…`; sheet `库存产品`;
  8 rows; Price values 24000, 27500, 24000, 27500, 25000, 31800, 27900,
  29000; independent sum **216700**.
- Product materialization `status=current`, coverage known, 8/8 rows, no
  truncation; the product source picker exposed the sheet; assignment
  retrieved and calculated **216700.00** and cited file, sheet, 8 rows and the
  source version.
- The copied world inherited a catalog pointer to the live world’s dataset
  store. The same genuine bytes were re-fetched read-only, hash-matched, and
  the product-materialized copy was placed inside the qualification world
  store; no catalog row was fabricated. See
  `part-a/catalog-relocation.json`.
- Restart at `74464af69f98` reopened the completed assignment and the DOCX
  (`Total 216700.00`, 8-row citation); artifact SHA-256
  `34e7420d9364d04e…`.

### Connector entry-point addendum

The verifier correctly noted that the first Part A run fetched Graph bytes in
the harness and called the materializer directly. The connector entry point was
then exercised through the product API:
`POST /api/intelligence/execute` with `action_type="tool"` and
`email_ingest_message`. The tool fetched the message and both attachments
through the connector pipeline (`status="ingested"`, 2 attachments), refreshed
the catalog row at `2026-11-01T12:37:20.673857` and
`ingested_documents.last_verified_at=2026-11-01T12:37:20.807742`. A new
assignment (`194b3474-3b96-4890-94f3-9986ad795283`) retrieved the
connector-refreshed sheet and returned **216700.00** across 8 rows; restart at
`a49b854ce660` reopened it. Independent source/hash checks are reused. Evidence:
`part-a-connector/`.

Evidence: `part-a/` (identity, independent read, materialization, assignment,
source receipt, restart, artifact) and `part-a-connector/` (product API
ingestion, refreshed catalog row, retrieval and restart).

## B — One authorized Outlook send

Run `9ac79044-0d44-446e-8da8-2482709aa350` (status `completed`).

- Mailbox identity rechecked immediately before send: `rish@brennan.ca`.
- Recipient: `rish@brennan.ca` (owner-controlled self-send).
- Exact subject: `[Atom qualification] One authorized send 2026-11-01`.
- Exact body: the tracked `docs/acceptance/LIVE_QUALIFICATION_B_BODY.txt`
  (already includes the stored signature), SHA-256
  `0b8c96d5aab954cc4b5a879ea95c37b7680a7b0984d877d526294385d8a1e696`.
  `part-b/body-reference.json` points to the tracked text, wire HTML and
  preview files and carries their hashes; the evidence directory does not
  duplicate the private signature. The durable operation binding carries the
  same body hash.
- Attachment: **none**.
- Grant `sga-live-qual-1793535072`: one effect, one recipient, 24h window,
  ended `status=exhausted`, `used_effects=1/1`.
- Provider acceptance: send step `applied`, summary
  “provider accepted message (sent)”.
- Sent Items reconciliation: exactly **one** matching message in the stated
  window; recipient `rish@brennan.ca`, exact subject, `hasAttachments=false`;
  message id `AAMkADdl…HvYQP3AAA=` and internet id
  `<YQBPR0101MB4748…@…OUTLOOK.COM>`.
- Body reconciliation: Exchange wraps the sent HTML in `<html><body>` and empty
  divs, so the raw readback hash is `90490283…`, not the composed wire hash
  `ef3472dd…`. Normalized text is byte-for-byte the frozen body
  (`normalized_sha256 00e97cf1…`); the first-pass raw-hash check in
  `send.json` is retained, and the authoritative reconciliation is
  `verify-result.json`.
- Restart at `74464af69f98`: assignment terminal `completed`; grant exhausted;
  exactly one Sent Items row; no second effect. No `assignment_approval` HITL
  row exists for this run (`hitl-check.json`); the one-use grant was the
  authorization.
- **Scope limits:** this qualifies provider acceptance and exact Sent Items
  reconciliation. It does **not** claim recipient inbox delivery, a second
  recipient, or any second send.

Evidence: `part-b/` (identity, exact body, request/grant, operation binding,
provider acceptance, Sent Items, restart/reconciliation, HITL check).
Authoritative summary: `part-b/result.json`; the restart checks are in
`part-b/verify-result.json`; the raw first-pass check is retained in
`part-b/send.json` with the Graph-wrapper explanation above.

### Disclosed pre-effect failure

A first attempt (`1d945c3e-a457-4824-bcd8-b99e0bbf5750`, grant
`sga-live-qual-1793534594`) failed before transport with “Not the canvas
owner”: the send used a blank document canvas, not an email canvas. Sent Items
had **zero** matches; no provider call occurred. The product’s email-canvas
path was used for the successful retry. That attempt is preserved in
`part-b/pre-effect-failure.json`; it is not counted as an effect.

## Boundaries

- Discretionary model judgment remains unsupported and is not upgraded.
- Recipient delivery is not claimed; only provider acceptance and Sent Items.
- No live Microsoft write, token rotation or new permission was performed.
- Hosted deployment/publication is deferred, not a gate.
