# Complete the original workbook-search → email-canvas workflow

## Assignment and finish line

Return to the user's original problem: the conversation around canvas `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb` produced unreadable workbook-search output, did not visibly honor the request to search again and give a clean response, and has never been conclusively demonstrated to produce the intended, evidence-grounded email draft end to end.

Deliver a usable isolated browser workflow and the resulting email draft, with source-grounded prices, explicit unresolved choices, preserved unrelated content, and reload persistence. This is not another generic quote-validity edit, recovery project, or infrastructure handoff. Work is authorized through draft creation/editing and verification. DO NOT SEND THE EMAIL or invoke any outbound-send action. Do not mutate the original live canvas or conversation as part of acceptance.

One agent owns implementation and verification. Follow AGENTS.md/CLAUDE.md, inspect callers and existing mechanisms before editing, preserve other agents' dirty/staged files, and leave a brief coordination pointer. No new intent keyword classifier, product-name special case, planner rewrite, model comparison, framework migration, or broad acceptance expansion.

## Start with original evidence, not a reconstructed story

Read these local sources in this order:
1. `docs/architecture/orchestration_migration/acceptance/fixtures/canvas_incident_quote.json` — original email canvas plus audit history. Canvas ID above, title begins “Quote – Roper Whitney Roll Bender…”. Parse the actual serialized content; do not substitute bare HTML for the email document schema.
2. `docs/architecture/orchestration_migration/acceptance/fixtures/retry_replay_incident.json` — captured user follow-up and the 22,595-character diagnostic reply. This is a tail, not proof of the entire conversation.
3. `docs/architecture/orchestration_migration/WORKBOOK_DELIVERY_WORK_ORDER_2026_09_26.md` — authoritative original eight-item request and meaning-preservation requirements. Its old implementation findings are HISTORICAL; verify current symbols before acting. Request identity and AgentExecution recovery already exist.
4. `docs/architecture/orchestration_migration/acceptance/lane3/CURRENT_SUPPORT_TABLE.md` — scoped preview, exact candidate identities and login procedure. Historical evidence is not a current-candidate pass.
5. Existing task-correction, workbook delivery, browser, and canvas-write acceptance drivers. Reuse working login/composer/context attachment and evidence readers instead of creating another framework.

Recover the precise original email instruction from the captured conversation/audit trail. If necessary, use the app's read-only history/canvas endpoints to inspect the original, without modifying it or connecting a write-capable scratch script to the live DB. If critical business intent cannot be recovered—such as which price basis the customer should receive—ask one focused question while completing independent search/fixture work. Do not invent currency, margin, discounts, lead times, recipient, tax, freight, or a send instruction.

Create `ORIGINAL_REQUEST.md` in the result directory: quote the recovered user instructions, identify sources and gaps, and distinguish exact historical text from any explicit reconstruction. Lost historical evidence stays unavailable; new tests do not explain the old F02a incident.

## Authoritative workbook request

> find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16

Preserve this exact order and membership. GSL24-16, SLE16-8 and U-38 are not substitutes for this initial task. Historical distractors must not union into the active set. Product names belong in fixtures and evidence, never in generic production routing rules.

The original follow-up is:
> try the search again and give me a clean response

A genuine reread of the same saved copy may return identical values. A changed string is not proof of a search, and identical text is not proof of replay. Measure retrieval and presentation independently.

## Environment: preserve, isolate, verify

The last recorded usable preview is frontend `http://localhost:3160`, backend `http://localhost:8072`, world `cand_79b2a4103_preview`, commit `79b2a41032c3`, export `64b44f297617b050`, planner pin `deepseek/deepseek-v4-pro`. Verify current health, loaded-module hashes, effective configuration and run DB before relying on these facts. Credentials are world-local; follow the support table, never copy passwords/tokens into tracked docs or logs.

Prefer a new session and uniquely named API-created draft in the existing isolated preview if it is suitable and available. If source edits are required, preserve that preview and create one small isolated candidate with new ports and an immutable export. Do not mutate frozen code in place. Record working-tree modifications explicitly; a checkout-derived source_id is not serving identity.

Use a small schema/bootstrap fixture, one user, the copied original email payload, and the required workbook/index artifacts. Create the email via the normal product create endpoint and supported content update, recording baseline audit counts after seeding. Do not inject canvas/audit rows directly to bypass product creation. Seed source/index metadata through the existing fixture/import mechanism and verify it points to the actual copied workbook data. Hash source files and record saved-copy ingestion/version information.

No full dev DB snapshot is needed simply because a fixture has zero canvases. No world cleanup, WAL/SHM deletion, live DB writes, disk reclamation, or portable-drive move. Respect storage preflight/interlock. Preserve :3000/:8001 and other named previews. Kill/restart only this run's recorded processes with verified identity. An unavailable old preview is not permission to recreate its missing database.

This task includes external model use only under existing authorized configuration. Capture this workflow's browser traffic separately. Previous read-workflow network traces do not establish edit-run isolation. The editor's CDN dependency is disclosed; never claim no data leaves on that basis. Keep private content and full payload captures access-controlled and out of ordinary logs.

## Phase 1 — Build the independent evidence checklist

Before asking the app to compose the email, independently inspect the fixture workbook/materialized data for the eight requested identities. Do not derive expected values by parsing the application's answer or hardcode values from older reports as current truth.

For each item record:
- requested label, resolved aliases and identity candidate(s);
- identity cell coordinates separately from value cell coordinates;
- original column/basis label, raw typed value and displayed value;
- explicitly recorded currency/unit only;
- source file identity/revision and coverage;
- ambiguity, missing field, blank, zero, formula error, or failed read.

Keep values attached to their own identity candidate. Several citations on one product row are not automatically several products; distinct variants can also share a row. Do not merge solely by display string or blindly choose the first row. Exact cell matching must not confuse A101 with AA101.

Prior reports mentioned List Price, List Price_2, PRICE, U.S. LIST, U.S. COST, Factory Price, FULL COST CDN and CDN LIST. These are distinct bases, not interchangeable prices. Internal cost fields are not automatically customer quote fields. If the intended selling basis is unresolved, present a decision to the user or retain an explicit pending-price placeholder. A partially resolved draft is acceptable when accurately labeled; a fabricated complete quote is not.

A failed/unreadable source is not “not found.” An absence is limited to successfully searched indexed coverage. Zero is not blank; unknown is not formula error. Never infer a live-source refresh from a saved-copy read.

## Phase 2 — Execute the original search in the browser

Use the real login, chat composer and canvas context attachment. Establish the cloned email canvas ID in the actual outgoing request. Capture request/execution/message IDs without exposing secrets. No shim or direct SQL can substitute for this user-facing end-to-end run.

1. Open the isolated copy of the original email. Record its subject, recipient/cc, body and revision hashes; preserve the initial rendered screenshot.
2. Submit the authoritative eight-item workbook request through chat. Confirm the intended source is selected.
3. Inspect the delivered answer against the independent checklist: eight ordered entries, honest ambiguity, correct bases/values, one concise source/coverage note, no diagnostic dump or internal markers. Full evidence may be expandable; it must remain available.
4. Submit the exact combined retry/clean-response follow-up. Prove a new retrieval attempt executed, record its outcome/revision, and verify the requested concise presentation. No new evidence may be invented when the copy is unchanged.
5. If needed, use one formatting-only follow-up to verify no retrieval, a new presentation action, and unchanged prior history. Do not require different bytes if the requested format was already satisfied.

When a step fails, capture the actual request, selected evidence, relevant decision and final output; trace the first divergence through existing scan, persisted record, presentation, continuation and finalization mechanisms. Fix the smallest demonstrated cause, test its neighbors, then verify on a new frozen export. Avoid reintroducing old keyword or per-product patches.

## Phase 3 — Complete the email draft from that evidence

Use the recovered original instruction, not a generic replacement prompt. If it only asked for research, do not silently infer extra commercial terms; make a clearly labeled proposed draft in the isolated copy. Ask only for material unresolved business choices, not routine permission to continue authorized draft work.

Submit the email update through the browser composer with the correct cloned canvas open. The real configured planner must generate the plan; no controlled accepting plan counts here. Carry the current task/evidence association through the existing mechanisms so a model cannot silently regenerate different identities, prices, sheet names or bases.

The final draft must:
- address the intended recipient using preserved fields;
- reflect the original requested scope, with each required item accounted for once;
- contain only verified prices on the authorized basis, with unresolved alternatives clearly pending rather than guessed;
- keep internal costs out of customer-facing prose unless explicitly requested;
- preserve unrelated subject/body/signature, terms, delivery estimates and formatting unless the user asked to change them;
- render readable email content, without diagnostic metadata, literal escaping artifacts, or accidental changes to the subject;
- keep evidence accessible in the app without dumping raw diagnostic prose into the email.

If the model declines a valid requested update, record a task-completion failure even if the refusal is honest. If ambiguity prevents a final price, the correct result is a specific clarification and a safely pending draft—not false success. Do not force wants_edit=true or bypass authorization to make the test pass.

Verify the durable canvas itself, not echoed request text in chat. Require the correct canvas ID, operation/audit linkage, revision, expected field changes and absence of unintended changes. Count ALL mutation audit rows added by this request after the seed baseline; counting only a recognized operation ID can hide duplicates. Exactly one intended update is expected for a simple draft application; explain any legitimate multi-operation flow rather than relaxing counts arbitrarily.

## Phase 4 — Reload and show the user

Wait for the actual terminal outcome if the edit backgrounds. A pending acknowledgment is not completion. Confirm the live outcome and stored history agree with durable content. A timeout must remain incomplete rather than becoming a success claim.

Reload the browser and reopen the cloned email and conversation. Verify all intended fields, prior answers, source association and terminal outcome persist. Do not confuse session-metadata endpoints with the UI's actual history endpoint. Select evidence by exact execution/message identity, never latest-in-session.

Inspect the rendered email visually: table/list legibility, row order, currency/basis labels, unresolved placeholders, subject/recipient preservation, no exposed diagnostics. Capture before/after/reloaded screenshots. Do not send, click Send, or exercise any external outbound integration.

## Fixed completion checklist

| ID | Required proof |
|---|---|
| O01 | Original request/source and cloned canvas baseline recovered; reconstruction gaps explicit |
| O02 | Isolated serving source/configuration/run DB verified; original live canvas untouched |
| O03 | Independent per-item identity/value/basis checklist tied to the source revision |
| O04 | Real-browser eight-item search: exact order, correct evidence and concise answer |
| O05 | Combined search-again/clean follow-up: observed retrieval plus appropriate presentation |
| O06 | Email composition/update through real planner and browser on correct canvas |
| O07 | Intended content durable and evidence-grounded; unrelated fields preserved; actual effect count verified |
| O08 | Terminal reply/history truthful; browser reload preserves draft and conversation |
| O09 | Rendered draft reviewed, no email sent, ready for user inspection |

If business ambiguity requires user input, distinguish “workflow correctly requests clarification” from “final commercial quote completed.” Deliver the safe draft and exact pending question; do not mark O06–O09 fully complete when the requested result is still missing. Keep old F02a historical attribution separate.

## Output package and stopping rule

Persist a compact package under `docs/architecture/orchestration_migration/acceptance/original_workbook_email/` (sensitive captures excluded from commits): original request mapping, manifest, per-case results, source evidence checklist, draft field diff, redacted browser trace, screenshots, and one current result table. Store checkpoints as each phase finishes; resume the first unfinished step after interruption.

Final user handoff must lead with:
1. isolated preview URL and exact cloned canvas link;
2. whether the original workflow is complete, awaiting a named business choice, or failed at a specific boundary;
3. a readable preview of the draft and unresolved items;
4. what was verified against source and after reload;
5. explicit “not sent” status and remaining limitations.

Do not report generic lifecycle tests as completion of this task. Do not spend this assignment finishing claim-crash recovery, streaming, PDF, search-ranking benchmarks or unrelated UI bugs unless one directly blocks the workflow above. Patch only reproduced blockers, run affected checks, preserve other work. The goal is the user's actual workbook-to-email experience, demonstrated in the app—not another infrastructure milestone.
