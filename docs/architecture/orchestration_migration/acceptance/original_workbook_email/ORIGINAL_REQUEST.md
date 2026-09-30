# ORIGINAL_REQUEST — recovered instructions and evidence gaps

Written 2026-09-29 at assignment start. Exact historical text is quoted verbatim;
reconstruction is labelled as such.

## The authoritative workbook request (exact historical text)

From `WORKBOOK_DELIVERY_WORK_ORDER_2026_09_26.md` (marked authoritative there):

> find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16

Order and membership are authoritative. `GSL24-16`, `SLE16-8`, `U-38` are NOT
substitutes.

## The follow-up (exact historical text)

From `retry_replay_incident.json` (captured 2026-09-26, session tail
`replay-retry2-20260923`):

> try the search again and give me a clean response

The incident: the compound ask returned a byte-identical 22,595-character
diagnostic dump (10 of 13 dumps shared one hash), 11 per-match rows for 8
requested machines, repeated FIELD SELECTION diagnostics, and a blank price
rendered as a raw cell reference.

## The email canvas (from `canvas_incident_quote.json`)

Canvas `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb`, title "Quote – Roper Whitney
Roll Bender, Linmac Bead Roller, Manual Flanger & Slitter", type email,
recipient "Steve Macisaac <amacisaac@alumasafway.com>", created 2026-09-22,
12 audit rows through 2026-09-23 17:15:58. Serialized body (parsed, not
guessed): a 4-row quote table —

| # | Description | Unit Price | Delivery |
|---|---|---|---|
| 1 | Roper Whitney 36" Gauge Manual Roll Bender, No. 381 | $2,902.00 | 10–11 weeks |
| 2 | Linmac Bead Roller 22 Gauge, 7" Throat, U-22 | $1,777.00 | 3–4 months |
| 3 | Manual Flanger | $1,609.00 | 3–4 weeks |
| 4 | Tennsmith Single Wheel Slitter SLE24-16 | TBD | TBD |

Footer: "**Unit Price:** CAD / **FOB:** Woodstock / **Payment Terms:** TBD" and
a note that slitter pricing and delivery would follow.

## Recovered vs. not recovered

- Recovered exactly: the eight-item ask; the retry/clean follow-up; the canvas
  baseline (above); the source revision the incident ran against
  (`Consolidated Price List 2019.xlsx`, content hash prefix `ff2597d26fc6`,
  ingested 2026-09-07T23:06:19, 46 sheets).
- RECOVERED (2026-09-29, by the parallel session, from original evidence): the
  user's original email-composition instruction —
  > rebuild the draft with requested quotes and alternatives to those machinery.
  (session `bd04ff7f…`, 2026-09-22 17:05:28 — the turn that ran past its time
  budget). The requirement this adds beyond a plain quote table:
  **alternatives** to the machinery must appear in the draft.
- ANSWERED by the user 2026-09-29: the price basis. **Not all list prices exist
  in the workbook — other prices are manually calculated from vendor pricing
  quotes**, and that knowledge is part of agent training (the app's main
  purpose is creating AI employees). Workbook prices and vendor-quote prices
  are both legitimate sources; a workbook absence never invalidates a
  vendor-quote price (No. 381 = $2,902.00 is such a price). The workbook-sourced
  rows quote the PRICE / List Price basis (7 of 8 historical prices match those
  columns exactly). Vendor-quote knowledge belongs in agent training, not in
  workbook search results.

## Reconstructed email spec (labelled reconstruction)

From the artifact alone: an email to Steve Macisaac quoting the requested
machines with unit prices (CAD per the footer), FOB Woodstock, payment terms
TBD, preserving greeting/signature and the slitter-pending note. The original
ask's eight machines, not the canvas's four, define the item set; items
without an authorized basis stay explicitly pending rather than guessed.
Internal-cost columns (Factory Price, U.S. COST, CANADIAN COST, FULL COST
CDN) are not customer quote fields.

## Rule keepers

- Exact eight-item order/membership; distractors never union in.
- A failed/unreadable source is not "not found"; absence is limited to
  successfully searched indexed coverage; zero ≠ blank; unknown ≠ formula
  error; a saved-copy read never implies a live refresh.
- Identity cells are distinct from value cells; same-row citations are not
  several products; A101 ≠ AA101; no merging by display string.
- Old implementation findings in the work order are historical; current
  symbols were re-verified before any use.
