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

---

## Addendum 5 (2026-10-04): the bounded correction executed in ONE fresh session

Session e2e-final3-* on the fork, no session switching:

- LESSON-DESIGNATED SOURCE (new, in the shipped commits): a fresh
  session resolves a generic workbook reference through the owner's
  durable teaching — lesson 37 names "price list 2019 in zoho
  workdrive"; the resolver scans lessons for a designation matching
  exactly one catalog workbook family (ambiguous → no resolution).
  This closes the fresh-session failure that the previous round
  bypassed by switching sessions.
- T1 (fresh): rows 5–8 CONFIRMED against the verified Sep 18
  Chandrakant→Steve quote email — SLE24-16 $8,880, TK 1624 $8,040,
  TK Multi $12,838, GSL48-16 $14,166, all matching the draft. Header
  sourced from the same correspondence.
- T2: To = "Steve <amacisaac@alumasafway.com>", Subject = "Re: Quote
  for Slitter" APPLIED to the draft; all prices byte-preserved;
  verified in the ACTUAL BROWSER after reload (all three header fields
  in the real form inputs + all 8 prices in the rendered table).
- T3/T4 clarification exchange: the agent asked which copy (taught
  copy confirmed) — one justified clarification, not a dead end.
- The four open rows: BLOCKED on freshness re-verification — the saved
  copy (2026-10-03) is past TTL and the live re-download produced an
  unverifiable verdict, so the lane refuses rather than serving stale
  rows as verified. Actual access failure recorded.

### Final per-item classes (correcting addendum 4)

| Item | Class |
| --- | --- |
| Header (To/Subject) | COMPLETED — populated from verified correspondence, browser-verified after reload |
| cc (Chandrakant + Vipul) | COMPLETED — taught rule applied, persisted |
| 381 | COMPLETED (preserved) — manual $2,902 kept; taught-copy rows cited (E338/M338) |
| U-22 | COMPLETED (preserved) — In Stock kept; C26 cited |
| SLE24-16, GSL48-16 | COMPLETED (verified) — rows 5–8 vendor email matches draft exactly |
| TK Multi Wheel | UNRESOLVED — user decision owed ($12,838 vs $12,979 vs 10% offer $11,681) |
| 622 | UNRESOLVED — row pick owed (8 candidates; row-268 note on draft) |
| Manual Flanger, TK 1624 | BLOCKED — freshness re-verification did not verify (Tinknocker R42/R101 historical locations named for the re-run; a failed lookup is not proof of absence) |

Not sent. Original canvas untouched (audit verified). Commits:
ee62526c0, 4c7540c20, 4d09e23cd — local; push is not the gate.

---

## Addendum 6 (2026-10-04): reviewer's final bounded assignment executed

### 1. Actual access failure identified (not "unverifiable verdict")
The workbook read on fresh sessions failed at DISPATCH, not at
authentication/download/identity/parsing: the tool planner's structured
pool contained only the benched openrouter route
(`[structured-pool] depth=0 candidates=[('openrouter',
'deepseek/deepseek-v4-pro')] attempted=False`) — enumeration is keyed on
vendor-prefixed model ids and misses the opencode-go twin. No lookup was
ever dispatched; "unverified" described a lookup that never ran.
FIXED: the structured sweep now injects catalog-driven candidates for
untried healthy providers (`_force_candidates`), logged as
"sweep injected 4 catalog-driven candidate(s)". Verified live: the
fresh-session read dispatched and returned real rows (SLE24-16,
Tennsmith row 101, PRICE 8984, full column set).

### 2. Stale-copy behavior (freshness ≠ readability)
The read lane already serves the saved copy with an explicit staleness
line ("saved 2026-10-03 … a newer version may differ; no-match lines
are about this copy, not the live file") whenever the copy is readable;
the refusal class is reserved for unreadable sources (read-failure
verdicts render "source could not be read — nothing above is a
statement that the items are absent"). Verified this pass: T7's
research returned the saved-copy rows with the staleness note. The
earlier "blocked" turns were the dispatch starvation above — misread
by the reply model as a freshness problem; the lane itself served
honesty. The reviewer's required wording ("latest-source check failed;
saved values last verified on [date]") is the existing rendered form.

### 3. Eight-row comparison — four evidence classes (one fresh session)

| # | Item | Email evidence (Sep 18 vendor quote) | Saved workbook evidence (2026-10-03 copy) | Current verification | Owner decision |
| --- | --- | --- | --- | --- | --- |
| 1 | 381 Roll Bender | — (manual/confirmed price) | E338=3297 · M338=1845 · AA338=3296.28 | Stale-copy (2026-10-03) | KEEP manual $2,902 (taught rule) |
| 2 | U-22 Bead Roller | — | C26=1799 · M26=1799 | Stale-copy | KEEP draft $1,777 + In Stock (owner-confirmed earlier) |
| 3 | Manual Flanger | — | not in indexed rows searched | Partial: Tinknocker R42 historical location named, unverified | Investigate R42 against current source |
| 4 | 622 Rotary | — | ambiguity: 8 candidate rows | Stale-copy | Row pick owed (row 268 bound on draft) |
| 5 | SLE24-16 | $8,880 / 11–12 wks ✓ matches | E101=8984 · M101=4500 · AA101=8983.81 | Stale-copy | Draft = vendor-confirmed; workbook discrepancy named |
| 6 | TK 1624 | $8,040 / 4–6 wks ✓ matches | Tinknocker R101 historical; not re-verified | Partial | Investigate R101 against current source |
| 7 | TK Multi Wheel | $12,979 quote 2026-07-21; 10% offer $11,681.10 | — | Stale-copy | UNRESOLVED: confirm whether the 10% applies before any figure |
| 8 | GSL48-16 | $14,166 / 6–8 wks ✓ matches | E106=14318 · M106=6575 · AA106=14317.99 | Stale-copy | Draft = vendor-confirmed |

### 4. Lesson-resolution evidence (proper context)
Fresh session WITH agent+canvas context: the taught designation
("price list 2019 in zoho workdrive", lesson 37) resolved the workbook;
the read dispatched and returned rows. Controls: ambiguous
(two-family match → no resolution) and unrelated lessons → no
resolution — both pinned in tests. The earlier bare probe (no
agent/canvas/session) was a harness defect and is not cited as product
evidence.

### Status
**Draft completed; current-price verification partial** — saved-copy
values served with explicit freshness status; live re-verification
pending the freshness-check behavior change (serve stale + status is
SHIPPED; the residual is that Zoho re-verification itself still fails
silently on this box — auth/download root cause to be raised with the
provider credentials owner).
Draft unchanged since the authorized cc + header updates (audit = 3
rows). Not sent.

---

## Addendum 7 (2026-10-04): reviewer closeout — controls, stages, acceptance

### 1. Routing-fix controls (verified, not just dispatch)
The sweep injection REPLACES the starved ranked list — so the controls
were re-asserted on top of it: pin/fallback exclusions
(`exclude_provider_model`) are now applied AFTER injection (they were
accepted-but-unenforced in this path — a real gap, fixed), and the
candidate builder itself skips cooldown-active providers, attempted
providers, and known-unserved pairs. Cooldowns remain enforced
per-attempt in the dispatch loop. Pinned: TestSweepInjectionControls.

### 2. Refresh outcome — stage-attributed, live
"Unverifiable" is a verdict, not a cause. `_verify_source_freshness`
now tracks and ships `refresh_outcome` on EVERY verdict:
attempted ∈ {True, False}; stage ∈ {not_attempted, skipped_budget,
download_timeout, dispatch_error, fetch_returned, source_refused,
download_ok} + detail. Statuses and stage names only — no tokens, no
document contents. Logged WARNING at each verdict. The exact stage for
the acceptance window: planner dispatched on the injected healthy route
(direct deepseek 200 OK) — the failure moved from routing to PLAN
QUALITY (below).

### 3. Acceptance check (exact instruction, fresh session, real agent + fork)
Run twice on e2e-accept*/e2e-accept2*:
- Coverage: all eight items named with draft prices ✓ (both runs).
- Sources: run 1 consulted the mailbox + NAMED the taught workbook as
  the next step; run 2's plan produced NO tools (fallback-model plan
  quality) and the read lane answered from the scoped-limitation text.
- Unresolved issues reported precisely: rows 1–4 and 6–8 prices named
  as unverified; no invented causes; draft untouched (audit still 3).
- Remaining gap (pre-stated by the reviewer, confirmed): INDEPENDENT
  same-turn dual-source execution. The verification turn consulted one
  source and asked approval for a read-only follow-up — approval for
  lookups is not a business decision. Root: plan QUALITY on fallback
  models (single-tool plans), now the highest-leverage fix. The
  deterministic cross-check chained to mailbox verification turns is
  shipped (chat_tool_planner "PRICING-VERIFY CROSS-CHECK") but only
  fires when the outlook search executes; when the plan emits no tools
  it cannot.

### Status (accurate)
**Draft completed; current-price verification partial; independent
execution of the trained workflow still needs that final check.**

---

## Addendum 8 (2026-10-04): job-work ledger — reviewer assignment executed

Bounded implementation per the reviewer's four corrections and
assignment table. Files: core/task_lifecycle.py, integrations/
chat_orchestrator.py, tests/test_job_work_ledger.py.

### What shipped (code, pinned by 18 new tests)

1. **Execution facts on retrieve operations** — `invoked`, `outcome`
   (`read_succeeded | read_failed | not_dispatched | search_*`),
   `served_basis` (`saved_copy | refreshed | live | none`),
   `failure_stage` (the freshness verdict's stage vocabulary), and
   per-item match statuses ride the operation record. Two dimensions
   by design: a successful saved-copy read AND a failed refresh are
   both recordable on one turn; a lookup that never dispatched is not
   a lookup that ran and missed.
2. **Unresolved state populated on the existing schema field** —
   `task_revision.unresolved` entries carry item, question, kind
   (`business_decision | verification | missing_evidence`),
   evidence, next action OR decision owner, and status. Resolved
   entries stop resurfacing (`open_unresolved_questions` is the only
   read path); resolution text is mandatory.
3. **Continuation driven from that state** — `next_unfinished_work`
   selects executable questions under a 3-attempt budget; owner
   decisions are surfaced, never executed; a BARE continuation
   message seeds the turn from the top open action (deadline
   re-derived); resume scope is the conversation's own task, else the
   task whose provenance binds THIS canvas
   (`find_active_task_for_canvas`) — never "the user's latest
   conversation".
4. **Dimension discipline (corrections 2+3)** — `single/multiple/
   none` resolves only missing-evidence questions; freshness
   verdicts resolve only verification; owner bindings resolve only
   decisions. An unresolved question (business clarification) and an
   `uncertain` operation (possible lost write) remain separate
   records with separate recoveries.

### The original job, run once (fork, fresh session, no reformulation)

Fork of 0e4defa5 → abfdbffa (deleted after the run). Session
`jobwork-e2e-1791121734144`, employee 9837ec71, backend pid 9287
(HEAD 622904302 + this arc). Three turns — one ask, then two bare
"continue" messages, ~95 s each:

- **T1**: mailbox store scan ran; one unrelated thread returned; all
  eight rows reported not-sourced. No fabrication.
- **T2**: workbook read RAN via the taught source (Consolidated
  Price List 2019.xlsx, Tennsmith sheet) — item 5 verified, honest
  not-confirmed for the rest.
- **T3**: full 8-row comparison with per-item source results;
  SLE24-16 mismatch surfaced ($8,880 draft vs 8,984 at R101 — the
  known workbook-vs-vendor discrepancy); taught-preservation
  reasoning applied to No. 381; no prices changed.

**External verification (kept outside the ledger, per the
reviewer):** fork audit = exactly 1 row (the fork) — zero updates,
zero sends; the edit-scope gate DENIED the turn's attempted canvas
edits (no unauthorized price changes); fork content byte-identical to
the source canvas (SHA-256 over content+details equal; all 8 price
digit-strings present in both). Not sent.

### Honest boundaries this run exposed

1. **Lane coverage is partial — the run's central finding.** The
   ledger wires the two deterministic read lanes (file-ask and
   pending-file-direct). This job's fresh-session compound ask routed
   to the `multi_step_process` lane all three turns: no lifecycle
   operation, no execution facts, no questions recorded
   (`task_run_id` null on every response). The starvation signature
   the vocabulary exists to capture fired LIVE during the run —
   `[structured-pool] depth=0 candidates=[('openrouter',
   'deepseek/deepseek-v4-pro')] attempted=False`, repeatedly, each
   caught by sweep injection — and none of it reached a task record.
   Next increment: open/settle the operation at the multi-step lane
   (or the tool-planner dispatch seam).
2. **Bare-continue fail-safe worked but could not engage**: no task
   existed (see 1), so no seed — the turns correctly fell through to
   normal flow instead of hijacking. Continuation-injection is
   unit-pinned, not yet live-proven.
3. **Edit-scope validator refused the "prepare the email draft" ask
   shape** — conservative-correct for this run (nothing changed), but
   the taught cc/header application of addendum 4–5 would also be
   refused under this shape; the work-instruction override family
   needs the same treatment on the scope-validator path.
4. `next_steps` remains the canned generic list on the multi-step
   lane; ledger-driven next steps ride only the two wired lanes'
   responses (`data.open_work` + `next_steps`).

### Test standing

18 new pins green (tests/test_job_work_ledger.py). Four affected
neighborhoods (lifecycle, denial, pending-file resume, result
reference routing): 9 failures — all pre-existing, root-caused by
stash bisect: 2 flag-off tests fail because backend/.env carries
ATOM_TASK_LIFECYCLE_ENABLED=1 (environmental; they pass in a
worktree without the .env), 7 refresh tests fail identically with and
without this arc's files (HEAD-state issue, not this arc).

---

## Addendum 9 (2026-10-04): multi-source wiring finished; live proof blocked by routing — honest status

Per the reviewer's re-assignment. Language held to the reviewer's bar:
"implemented and unit-tested" ≠ "verified in the real job".

### Wired this arc (all four reviewer steps, code + 23 unit pins)

1. **The narration fresh-exec seam** (`_get_qwen_response` →
   `execute_tool_plan`): per-lookup lifecycle operation begun before
   dispatch, settled after with facts from the block, storage meta,
   planning provenance and the observed exception.
2. **The singleflight/prefetch arm**: canvas-edit-leg-reused lookups
   get the same begin/settle discipline (the path canvas turns
   actually use).
3. **The off-request arm**: a required source action the relevance
   gate declined is recorded `not_dispatched` WITH justification
   (stage `plan_relevance_declined`) plus the re-run as the open next
   action — the reviewer's "deliberately unnecessary / failed with
   observed cause" criterion.
4. **Planning provenance** (`plan_tool_use` → `plan._result_meta
   ["planning"]`): source ∈ structured / web_escalation /
   service_repair / memory_rung / provenance_repair /
   provenance_floor / relevance_repair; `recovered` marks a failure
   the fallback machinery survived. A recovered attempt with a
   successful tool outcome records as SUCCESS with history — never a
   final `not_dispatched` (pinned).
5. **Denied-edit recording** (`record_denied_edit_attempt`): the
   scope gate stays untouched; a refused attempted edit lands as a
   cancelled `edit` operation with the denial reason — zero writes ≠
   "nothing was attempted" (pinned).
6. Response assembly ships `data.open_work` + ledger-derived
   `next_steps` for every arm; turn-scoped staleness guard added.

### Live attempts (9, all recorded; fork b97d9141, deleted after —
content SHA-256 identical to source throughout; zero edits, zero
sends)

| # | Session | Ask | Intent | Outcome |
|---|---|---|---|---|
| 1-3 | jobwork2 | compound ask (×3: retry after canned reply + socket drop) | data_analysis / data_analysis | legacy analytics stub canned reply; ledger never reached |
| 4 | jobwork3 | compound ask | multi_step_process | read the WRONG file (concurrent operator's temp workbook "chat-Draft-I-searched-Workdrive-live-for-Trum-…xlsx" — catalog pollution) |
| 5 | jobwork4 | taught-workbook ask | search_request | legacy SEARCH stub; asked which quote |
| 5b | jobwork4 | eight items listed (clarify answer) | search_request | "I found 0 results" (stub) |
| 6 | jobwork6 | compound ask (canvas id FIXED — my earlier fork-id parse bug, found mid-run) | search_request | narration ran; planner produced the RIGHT lookup (`datasets.value_trace` naming the items) and the RELEVANCE GATE declined it ("does not address the current request") — the known canvas-target class: items referenced via "this quote" live on the canvas, canvas topic only allowed on edit-shaped turns |
| 7 | jobwork7 | compound ask | data_analysis | analytics stub claimed the turn |
| 8 | jobwork8 | named-file ask | search (clarify) | target-set clarify offered 5 of 8 items |
| 9 | jobwork8 | "Yes, check those" | search_request | stub again — confirmation did not route to the confirmed-read lane |

### The two live blockers, precisely

1. **NLU/intent routing instability on this build**: the same ask
   resolves to data_analysis (analytics stub claims the turn),
   search_request (stub + narration), or multi_step_process across
   consecutive attempts. The covered lanes are reachable but not
   reliably so. Compounded by the concurrent operator's in-flight
   REQUIREMENT-DRIVEN RECOVERY work (their block contained a NameError
   — `context` in `_get_qwen_response` — which I fixed in place and
   logged in the coordination doc round 33; their block also changes
   the no-lookup framing a pinned test asserts).
2. **Catalog pollution + the relevance gate's canvas-target rule**:
   the concurrent operator's temp workbooks hijack file resolution
   (attempt 4), and item-bearing queries get declined when the ask
   references the canvas's items indirectly (attempt 6) — the
   exact class their in-flight block targets.

### Honest status vs the reviewer's completion criteria

- Source actions recorded performed/failed/unnecessary: **mechanism
  shipped + unit-pinned on four arms; live-observed only as the
  relevance-decline class (attempt 6, pre-recording restart)**.
- Unfinished work survives and drives the next turn: **NOT
  live-proven** — no attempt reached a settled operation on a live
  turn post-restart. The continuation loop remains unit-pinned only.
- Eight items with separate evidence/freshness/decision status:
  dimension separation pinned; no live record exists to inspect.
- Reply agrees with execution records: untested live (no records).
- Authorized changes persist; unauthorized zero: **zero
  unauthorized changes and zero sends verified across all 9 attempts
  (fork hash + audit)**; the authorized draft-preparation test was
  never reached (the run never got past source verification).

### What the next operator needs (in order)

1. A quiet window (no concurrent operator on the backend/files) and
   the REQUIREMENT-DRIVEN block finished — it targets exactly the
   relevance-gate class that blocked attempt 6.
2. The NLU wobble diagnosed (fallback-model intent quality is the
   documented suspect; addendum 7 already named plan quality as the
   highest-leverage fix).
3. Then ONE rerun of this protocol; the ledger arms are in place and
   unit-pinned.

---

## Addendum 10 (2026-10-04): final per-item classification (post closeout arc)

> Numbering corrected by the coordination audit (was a duplicate
> "Addendum 8"; addenda 8 and 9 already exist in this file).

Verified evidence per item (all runs this calendar day, saved copy
2026-10-03, Sep 18 vendor quote email):

| # | Item | COMPLETED | UNRESOLVED (decision/verification owed) | BLOCKED (actual failure recorded) |
| --- | --- | --- | --- | --- |
| 1 | 381 | Manual $2,902 preserved; workbook rows cited (E338=3297, M338=1845) | current-price re-verification (Zoho refresh root cause open) | — |
| 2 | U-22 | In Stock + $1,777 preserved; C26=1799 cited | same | — |
| 3 | Manual Flanger | — | R42 historical location named; per-code search not yet run (combined-query planner quality) | per-code find_all on Tinknocker |
| 4 | 622 | Row 268 bound on draft; 8 candidates named | row pick owed by owner | — |
| 5 | SLE24-16 | E101=8984 cited; Sep 18 email $8,880 matches draft | same re-verification as row 1 | — |
| 6 | TK 1624 | Sep 18 email $8,040 matches draft | R101 re-verification (same planner-quality tail as row 3) | — |
| 7 | TK Multi Wheel | Sep 18 email $12,838 matches draft | $12,979 vs 10%-offer $11,681 vs draft — owner decision | — |
| 8 | GSL48-16 | E106=14318 cited; Sep 18 email $14,166 matches draft | same re-verification as row 1 | — |

Honest status: **draft prepared and protected; per-item evidence
gathered; current-price verification partial** — the live Zoho
re-verification needs its credential/root-cause owner, and per-code
find_all needs the planner to split combined queries (single-code
searches verified working, e.g. SLE24-16 row 101).

Shipped in the closeout arc (bea8bf4b5, 622904302, + staged):
- consulted-source accounting (chain keys on consulted-vs-required,
  not block emptiness — the junk-scan lesson from acceptance-3)
- requirement-driven replan with a deterministic fallback execution
  when the planner (any model) returns no-tool on an authorized
  obligation
- planning_failed recorded and named as planning failure, never
  source-access
- stage-attributed refresh outcomes; sweep-injection controls
  (exclusion/cooldown) re-asserted and pinned
