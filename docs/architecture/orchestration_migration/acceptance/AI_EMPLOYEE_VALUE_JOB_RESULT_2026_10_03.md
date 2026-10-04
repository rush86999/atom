# AI Employee Value — Job Execution Result (2026-10-03)

Work order: `AI_EMPLOYEE_VALUE_COMPLETION_2026_10_03.md`. Employee: Sales
Agent `9837ec71-4f1b-41db-b014-119862362d44`. Canvas:
`0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb` (owner's Wayne Knott quote, 8 items).
Session: `replay-retry2-20260923` (panel). Running app pid 38948, HEAD
7bcb3ae6e + this arc's fixes (uncommitted at run time).

## Teaching (via the actual UI)

- Message typed in the canvas panel chat; agent acknowledged; UI surfaced
  "Save as a permanent lesson?"; Save clicked. UI evidence: "Learned ·
  Sales Agent SUPERVISED" chip with Undo button.
- Durable: `agent_registry.configuration.learning.log` grew 45 → 46,
  source=teacher, the exact rule text (workbook → vendor email +
  attachments → preserve confirmed manual price → flag unresolved
  basis/model differences).

## Job steps and outcomes

| Step | Ask | Outcome |
| --- | --- | --- |
| 1 | Find 381 on the Tennsmith sheet | ✅ Read scoped to Tennsmith (lessons [40]/[42] brand rule), row 338, five price bases, "the row you confirmed" |
| 2 | Other machines — any justified changes? | ✅ "No" with per-item provenance; older quote explicitly not treated as authority; U-22 delivery discrepancy flagged as lead-time, not price |
| 3 | Consult supplier correspondence for the open items (paraphrased) | ❌→✅ First run hit the delivery-retry lane (vendor source never read). FIXED: outcome-seek gate is source-shaped (any outcome reference naming another source). Rerun: mailbox lookup executed, irrelevant hits honestly discounted, concrete next searches given |
| 4 | Concise 8-row comparison | ✅ Full table: draft price, proposed, source+date, basis/currency, decision; honest "none established this turn"; no invented prices |
| 5 | Correct 622 binding to RoperWhitney row 268; use the June 17 thread as source; revised comparison | ❌→✅ First run hit the delivery-retry lane again (non-substantive scoring). FIXED: work-instruction shapes (correction/bind/revise/compare/source-choice) override delivery classification. Rerun: row-268 binding applied, blocked rows explicit, unverified-write disclaimer |
| 6 | Authorize only the confirmed changes | ✅ One edit, one audit row (26→27, chat_to_canvas): U-22 delivery → In Stock (June 17 vendor thread), row-268 note on item 4. Durable read-back via the app's read path: both changes present, ALL 8 prices byte-preserved, recipients/subject untouched. Not sent. |
| 7 | New session + held-out quote (Detroit 4445 / Chicago 812 / Wukson 4x10), paraphrased | ❌→✅ First run: agent saw "an empty email draft" — save_draft audits carry an EMPTY content shell while the body lives under details.draft.body; read_canvas served the shell. FIXED (read-shape normalization). Rerun: taught procedure applied from paraphrase, zero stale identities (no 381/622/Tennsmith), competitor-price check invoked (lessons [14]/[15]), honest TBC + next step |

## Boundaries found and fixed (each: first failure → producer fix → rerun)

1. **Outcome-seek gate was verb-shaped** — "go through the supplier
   correspondence" escaped `search|check|look`. Now source-shaped: any
   outcome reference naming another source is a consult
   (`chat_orchestrator._outcome_seek_elsewhere`).
2. **Outcome-subset vocabulary** — "still open", "nothing was found for"
   missed. Added generic English state words
   (`target_set_resolution._OUTCOME_SUBSET_RE`); resolver returns the
   ledger set (GSL24-16, SLE16-8, U-38, 622, 56,100).
3. **Work instructions swallowed by delivery classification** —
   correction/binding/revision/comparison shapes override both delivery
   entrances (`_WORK_INSTRUCTION_RE`).
4. **save_draft-blind canvas read** — `read_canvas` serves the draft body
   when the audit's content shell is blank
   (`tools/canvas_crud_tool.read_canvas`).

## Completion bar

| Check | Evidence |
| --- | --- |
| Teaching | UI save + "Learned" chip; lesson #46 in durable store; applied on steps 1 (sheet scope), 7 (full procedure, paraphrase) |
| Scope | 8-item set from the draft, not retyped; "other machines" resolved from the canvas; ambiguity clarified (622) |
| Research | Workbook read (step 1), mailbox searches (steps 2/3/4/7) executed with named results; blocked items carry specific causes |
| Comparison | Step 4/5 tables: identities, bases, currency (CAD), provenance; manual prices preserved; no conversions invented |
| Editing | Real UI panel + real planner; one audit row; prices/recipients preserved; durable reload matches |
| Continuity | Step 7: fresh session + new canvas; teaching applied; no stale item/row identities |
| Failure handling | Provider-402 turn failed honestly with a user action; step 3/7 partials name exact next searches; no invented prices anywhere |
| Generality | Held-out quote with different names/structure: no new vocabulary rules needed |

Latency: 12–120 s/turn (narration turns ~90 s). Unnecessary user
interventions: 1 (step-3 rerun asked which rows the ledger already
resolved — afterward the resolved set seeds the mail query).
Safe-but-incomplete: the three not-found items stay honestly TBC with
named next searches (no source carries them). Cost telemetry: not read
(provider dashboards external).

## Fixes in this arc (code)

- `integrations/chat_orchestrator.py`: source-shaped outcome-seek gate;
  `_WORK_INSTRUCTION_RE` override on both delivery entrances.
- `core/target_set_resolution.py`: generalized outcome-state vocabulary.
- `tools/canvas_crud_tool.py`: draft-body read normalization.
- Tests: `tests/test_result_reference_routing.py::TestWorkInstructionOverride`,
  chain-suite pins (32), target-set resolution suite (68 total green).

## Remaining limitations

- Mailbox excerpt search still misses deep thread content (step 3 named
  the concrete grep/open path; excerpts are what the tool returns).
- The three not-found items have no source anywhere in the connected
  stores — honestly TBC, not a workflow failure.
- openrouter is out of credits (owner top-up needed); other routes served.
- Multi-job statistical reliability (3 fresh drafts) not yet run — the
  work order's reliability pass is next.

---

## Addendum (2026-10-03 late): provider-credit routing + reliability pass

### Provider availability (owner directive: opencode-go and deepseek available)

- Verified live: opencode-go IS serving (200s, cost-attributed) and direct
  deepseek BYOK is initialized — through the whole job. Only OPENROUTER's
  account balance is exhausted.
- Root cause of the step-4 false outage: the reply-leg ladder's ranked
  pool collapsed to openrouter-hosted models, and openrouter's quota bench
  was only 300s — it expired mid-job and re-admitted the dead gateway to
  the TOP of the ranking, whose 402s then killed the turn.
- FIXED (core/llm/byok_handler.py):
  1. Non-stream completion ladder now ends with the same catalog-driven
     sweep the stream path has — walks untried, non-cooldown providers'
     served catalogs (opencode-go/deepseek) before giving up.
  2. Quota bench extended 300s → 1800s (ATOM_PROVIDER_QUOTA_COOLDOWN_
     SECONDS overrides) — a balance does not refill in five minutes.
  3. The completion path now benches on quota errors too (mirrors the
     structured path).
  4. The exhaustion message tells the truth: names the providers that
     failed, and only says "every configured provider" when the sweep
     genuinely found nothing untried.

### Reliability pass (3 fresh disposable drafts, paraphrased)

| Draft | Items | Outcome |
| --- | --- | --- |
| A (Northern) | PE-16 (TBC), MidWest brake | SAFE-BUT-POORLY-EXPLAINED: the editor correctly refused to fill the TBC line (no source anywhere), but across 5 runs the decline message was generic/misattributed. Boundaries fixed en route: scope_dropped_product now names the dropped identity in the decline (was: a misleading empty-CC hint); a deterministic TBC-row catalog probe feeds the editor evidence. Known remaining: the probe→decline-message plumbing does not always surface the probe text (bounded 4×; documented). |
| B (Kalitto) | SteelMaster 616 (TBC), used Delta | ✅ Taught behavior: lookup ran, nothing matched, line stays TBC, next steps in the owner's own lesson vocabulary (attachments scan, value_trace); commits to verified-only application |
| C (Ridge) | Ajax shear (manually confirmed), Acra (TBC) | ✅ Manual price EXPLICITLY preserved ("left it untouched per your note"); Acra honestly unfilled with next step |

Counted per the work order: 2 completed, 1 safe-but-incomplete (its
protective behavior is the taught rule; the gap is the explanation
routing, not the decision).

### Tests

394 green across the arc's neighborhoods, including new pins: quota
cooldown 30-min default, quota bench fires on the completion path,
work-instruction override, TBC probe (domain-free fixtures).

---

## Addendum 2 (2026-10-04): all limitation tails closed + independence audit

### Run-A decline plumbing — CLOSED

Root cause found by gate instrumentation: a one-line NameError (the probe
referenced `context`, absent in that method's scope) — the probe silently
excepted into a DEBUG log on every run. Fixed (workspace_id=None; the
catalog is deployment-wide, user_id scopes it). A9 verified live: the
decline now ships the probe's findings ("PE-16 Hand Seam Tool — no
cataloged document carries it … the moment a vendor quote turns up, I'll
apply it immediately").

### Mailbox excerpt depth — improved, general mechanism

Root cause: per-term search took the query's FIRST three tokens, while
the outcome-resolved codes ride the query TAIL. Identifier-shaped tokens
(letters+digits — any domain's code convention) now join the per-term
pool (chat_tool_planner). Live proof: the vendor consult's next run
surfaced an identifier-matched thread (26-1657) it previously missed.
The June 17 thread remains excerpt-bound (Graph excerpt search); opening
a thread's full body stays the named follow-up (the outlook.read path
already fetches full bodies by message id).

### Statistical pass — 6 runs total

Rounds 2 (D/E/F): marine-supply (TBA), clinic fitout (pending), print
shop (TBD) — three placeholder conventions, three value domains,
paraphrased instructions. All three applied the taught procedure
(workbook → vendor email + attachments → value_trace → preserve manual
prices → verified-only drafting) with honest partials. Combined: 6/6
behaviorally correct (A's decline explanation fixed and re-verified in
A9). Disposable canvases deleted after each run; the owner's canvas
untouched (audit verified).

### Independence audit (owner directive)

Generalized in this addendum:
- Outcome-seek gate source nouns: purchasing words joined GENERIC
  document/store vocabulary (records, documents, files, folders,
  archives, notes, registers, system) — a legal/clinic/fabrication
  chain gates the same way.
- Work-instruction vocabulary: price-only compounds → the value family
  (price/value/cost/rate/fee/lead-time-source; use X as source/basis/
  reference).
- TBC probe placeholders: TBC/TBD → the family (TBA, n/a, pending, ?),
  pinned with a 3-placeholder-domain test.
Pins: TestArcIndependence + TestTbcCatalogProbe (40 chain-suite tests),
398 total across the arc's neighborhoods.

---

## Addendum 3 (2026-10-04): thread-depth mechanics + the last tail

### Delivered (live-verified)
- SEARCH AUTO-READ: a search whose top hits are preview-only or excerpt-
  truncated now chains bounded full-body reads in the SAME turn (top-2,
  read-cap bodies, per-id outcomes; chat_tool_planner). No second turn
  for live-hit depth.
- IDENTIFIER TOKENS: outcome-resolved codes ride the query tail —
  identifier-shaped tokens (letters+digits) join the per-term pool;
  live-verified surfacing an identifier-matched thread previously missed.
- INFLIGHT-CLAIM TTL: attempts claims had NO expiry — one leaked claim
  (a hung turn) blocked opencode-go/kimi across turns as "model_inflight"
  while it was the healthiest route. Claims now expire at 120s
  (ATOM_MODEL_ATTEMPT_INFLIGHT_TTL) and leaked claims are stolen.

### The last tail — precisely diagnosed, fix designed, not yet wired
Store (ingested-mailbox) hits render as lines WITHOUT their message id
(`[ingested mailbox] From: … | outlook — date | excerpt…`), so neither
the agent nor the auto-read can deepen them: the id exists in the store
records but the three line builders (figure/address/hybrid legs of
_ingested_mailbox_lines) drop it at format time. Fix design: carry
message_id in each line ("| message_id: …"), extend the auto-read to
store ids via the same _outlook_read_by_ids. Deliberately left unwired
at this session's depth rather than shipped half-tested; every other
depth mechanic is live.

### Structural finding for the next operator
When openrouter's credit bench is active, the STRUCTURED planner pool
can collapse to a single openrouter-hosted candidate (the gateway
fan-out is keyed on vendor-prefixed model ids and misses the
opencode-go twin). The inflight-TTL fix unblocks the healthy sibling
route, but the fan-out itself deserves a look: gateway variants of a
model should enumerate independently of the vendor prefix.

---

## Addendum 4 (2026-10-04): completion job on a disposable fork — the gate

Per the reviewer's instruction, the ORIGINAL job was finished: fork of
canvas 0e4defa5 → b5676728 (disposable copy, exact content parity
verified including the empty to/subject FIELDS of the source lineage).
Session e2e-final2-*, employee 9837ec71, saved teaching (46 lessons).

Two more boundaries found and fixed in-run:
- NEGATED-EDIT CLAIM: "Don't change the draft yet" matched the edit
  shape; the editor (correctly) declined and the turn shipped "editor
  declined" instead of the requested research. Negated-edit vocabulary
  now exits the shape matcher (research path owns the turn). Pinned.
- PLANNER_DECLINED DEAD END: "Search it for all eight items … add the
  workbook rows to the comparison" matched the verb "add"; editor
  declined; decline reply shipped instead of research. When the editor
  itself judges not-an-edit (wants_edit=False) and the message carries
  research vocabulary, the flow now falls through to the tool path.
  Pinned.

### Job outcome (per-item, honest classes)

| Item | Class | Detail |
| --- | --- | --- |
| 381 | COMPLETED (preserved) | Manual $2,902 kept; workbook 3,297/1,845 E338/M338 cited as non-authoritative for the draft per lesson |
| U-22 | COMPLETED (preserved + taught cc) | In Stock kept; workbook 1,799 C26 cited |
| 622 | COMPLETED (bound) | Row 268 note on draft; workbook ambiguity (8 rows) named, user pick still owed |
| Manual Flanger | CORRECTLY-STOPPED | No workbook row, no vendor thread on file — named as such |
| SLE24-16 | COMPLETED | Workbook 8,984/4,500 row 101 vs draft 8,880 — draft is a user-era price; workbook discrepancy named |
| TK 1624 | CORRECTLY-STOPPED | No source on file |
| TK Multi Wheel | COMPLETED (conflict surfaced) | Vendor $12,979 / 10% offer $11,681 vs draft $12,838 — owner's call required, nothing changed |
| GSL48-16 | COMPLETED | Workbook 14,318 row 106 cited vs draft 14,166 |
| cc rule | COMPLETED (taught rule applied) | Lesson 17: Chandrakant + Vipul added to cc — teaching changed the real draft |

### Draft verification (durable)
cc = "Chandrakant <chandrakant@brennan.ca>, Vipul <vipul@brennan.ca>";
all 8 prices byte-preserved; row-268 note and In Stock statuses kept;
footer present; to/subject fields in exact parity with the source
canvas; audit = fork + exactly 1 update. NOT sent. Reload persistence:
read_canvas (audit-trail backed) matches.

### Honest counts (correcting the earlier "6/6")
- Completed requested work: the original job above (research + cc rule
  application + verified draft).
- Correctly stopped, evidence genuinely unavailable: Flanger, TK 1624
  prices; 622 row pick (user decision owed).
- Fixed after being stopped-despite-available: T1 negated-edit claim,
  T2 planner_declined dead end, run-A probe plumbing, credit-routing
  collapse.
- The 6 paraphrased runs are a regression check, not a statistical
  reliability claim.

### Playbooks + attachment state (reviewer recheck)
- /api/playbooks returns 200 with data; the panel's Playbooks network
  error matched the dead-backend window (19:24–21:13, root-caused and
  fixed as the recovery outage) and is absent on live reload.
- The inconsistent attachment state was real: the panel showed the
  provenance hire's badge AND an "Attach agent" gate simultaneously.
  CanvasDataSection now offers one-click attach of the provenance hire
  (idempotent POST /{canvas_id}/agents) instead of the dead-end gate.
