# ORIGINAL WORKBOOK → EMAIL WORKFLOW — RESULT TABLE (2026-09-29)

Candidate: preview `cand_79b2a4103_preview` — commit `79b2a41032c3`, export
`64b44f297617b050`, frontend :3160, backend :8072, planner pin
`deepseek/deepseek-v4-pro`. Clone canvas `fc99d46f-7a6b-4b75-b4ed-750cc8bfed2b`
(created via `POST /api/canvas/email/create` + `PUT /api/canvas/{id}`, baseline
2 audit rows). Session `05188adb-fc2f-466a-9da6-7e68c319ca62` (canvas panel),
plus one main-chat session. No email sent; original live canvas `0e4defa5…`
untouched.

| ID | Verdict | Evidence |
|---|---|---|
| O01 original request recovered | **PASS** | `ORIGINAL_REQUEST.md`; ask + follow-up quoted verbatim; email-instruction gap declared unrecoverable; reconstruction labelled |
| O02 isolated env verified | **PASS** | health pid 40833 = commit 79b2a4103, run DB = world run dir; live canvas untouched; clone via product endpoints only |
| O03 independent evidence checklist | **PASS** | `phase1_evidence_checklist.json` — direct parquet read of revision `ff2597d26fc6`; identities/bases/values per item; ambiguities mapped |
| O04 real-browser eight-item search | **PASS** | exact order, all 8; U-22 1777 / Flanger 1609 / SLE24-16 8880 / TK 1624 8040 / GSL48-16 14166 match the checklist; honest ambiguity on 381/622/gang-slitter; no diagnostic dump; execution `accb84fb`, attempt `attempt-47768045` |
| O05 retry + clean response | **PASS** | exact follow-up text; NEW retrieval proven — `attempt-1da901d6` ≠ `attempt-47768045`, same evidence revision (unchanged copy, permitted); clean presentation again; execution `1e51f44b` |
| O06 email update through real planner | **FAILED — demonstrated boundary** | Three attempts, all honest, none reached the edit planner: (1) canvas composer after research → routed to workbook search (`88f3b06f`, canvas_edit None); (2) edit-first phrasing → routed to search AND false-absence "no matching row" for all 8 items incl. spurious probes "FOB: Woodstock" (`2e5b0d65`); (3) main chat, canvas named → truthful "I can't see the open canvas from here" (no canvas bound). Audit rows stayed at baseline 2; canvas durably unchanged. Root boundary: an active workbook objective in the session captures subsequent turns; canvas-edit intent is unreachable; no discoverable canvas-context attachment in main chat. |
| O07 durable intended content | **BLOCKED by O06** | canvas unchanged (verified in DB, not echoed text); no mutation to explain |
| O08 reload persistence | **PASS (for what exists)** | fresh tab rehydrated the full conversation and preserved canvas content byte-stable; `reloaded_canvas_and_panel.png` |
| O09 rendered review, not sent | **PASS with scope note** | rendered email reviewed (recipient/subject/footer preserved; original 4-row table intact); **email NOT sent**; no outbound action exercised |

## Divergences found (recorded, not patched)

0. **Two independent Phase-1 passes exist in this package and agree.** A second
   writer ran its own all-46-sheet pass in parallel (`phase1_evidence.py` →
   `evidence_checklist.{json,md}`, 25,251 rows); this table's checklist
   (`phase1_evidence_checklist.json`) read the four relevant sheets with
   anchor-verified column letters. Overlapping values are identical
   (1,777 / 1,609 / 8,040 / 8,880 / 14,166); the parallel pass found MORE
   No. 381 candidates (7, incl. `tennsmith!338` PRICE 3,254 and likely
   numeric-coincidence rows in gmpump/servo) — reinforcing, not contradicting,
   the ambiguity finding.

1. **O06 routing blocker (workflow-critical).** After workbook research in the
   canvas session, edit-intent turns are consumed by the workbook objective and
   never reach the canvas-edit planner. Turn 4 additionally reproduced the
   original incident's false-absence failure class — every probe returned "no
   matching row in the indexed content searched", including non-item strings
   tokenized from the edit request. This is the PREVIEW-01 failure class
   re-observed on the promotion preview, now blocking the research→edit arc.
2. The app's search did not surface `tennsmith!A338 '381'` (CAT 167 072 381,
   PRICE=3254) — the cross-listed second No. 381 the independent checklist
   found; it reported only the price-blank RoperWhitney rows.
3. Turn 5's honest refusal ("can't see the open canvas") is correct behaviour
   for an unbound session — recorded as the truthful counterpart to the
   routing failure, not a defect.

## Pending business questions (updated 2026-09-29 after user input)

**User answer received (2026-09-29):** not all list prices exist in the
workbook — other data is **manually calculated from vendor pricing quotes**,
and this knowledge is part of **agent training** (the app's main purpose is to
create AI employees). Consequences applied to the record:

- The original canvas's No. 381 price **$2,902.00 is a legitimate vendor-quote
  price**, not an unsupported outlier. The earlier "matches no column of the
  current revision" note stands as a workbook fact but is NOT evidence of a
  wrong price. Vendor-quote prices must be **preserved, never flagged as
  contradicted by workbook absence**.
- The proposed draft keeps $2,902.00 for No. 381 (vendor-quote basis, carried
  from the original canvas). Workbook TBDs remain TBD only where no vendor
  price exists yet.
- Product direction recorded: vendor-quote prices belong in **agent training**
  (the canvas co-editor's Training tab / feedback notes), not in workbook
  search results — the AI-employee model the app is built around.

Still open (genuine model-mapping choices, not price-basis questions):

1. **No. 622 variant**: machine (2,421), 622LR (2,583), or roll package (670)?
2. **Gang slitter mapping**: Tinknocker "TK Gang Slitter" (12,838) vs the
   Tennsmith GSL48-16 row already quoted as item 8?
3. **Delivery estimates** for the newly added rows (the original canvas had
   10–11 weeks / 3–4 months / 3–4 weeks / TBD — vendor-quote territory).

## Proposed draft content (prepared, NOT applied — O06 failed through the planner)

8 rows in the original order: No. 381 **$2,902.00** (vendor-quote price carried
from the original canvas — workbook-independent by design); U-22 $1,777.00;
No. 622 "TBD — model confirmation pending"; TK Manual Flanger $1,609.00;
SLE24-16 $8,880.00; TK 1624 $8,040.00; TK Multi Wheel Gang Slitter "TBD —
model confirmation pending"; GSL48-16 $14,166.00. Recipient, subject,
greeting, footer (Unit Price: CAD / FOB: Woodstock / Payment Terms: TBD) and
the closing note preserved. Internal-cost columns excluded from customer
prose. Held out of the canvas on purpose: applying it by API would have
falsified O06's evidence. Per the user's 2026-09-29 input, vendor-quote
prices like 381's belong in agent training going forward.

## Files

`ORIGINAL_REQUEST.md`, `phase1_evidence_checklist.json`,
`clone_baseline.json`, `phase2_search_results.json`,
`reloaded_canvas_and_panel.png`, `checkpoints.md`, this table.
