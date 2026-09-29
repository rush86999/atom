# Cross-source follow-up fix — result package (2026-09-29)

Fixes the original-canvas failure diagnosed in
`../root_cause_2026_09_29/DIAGNOSIS.md` per the directive
`../../../CROSS_SOURCE_FOLLOWUP_FIX_2026_09_29.md`. One writer (ZCode),
isolated verification only; the dev stack :8001 was never restarted and no
email was sent.

## Root cause (one paragraph)

The exact instruction "check Chandrakant's email and or description in
workbook to find correct sheet and row from workbook for confirmation"
matches the loose retry shape `_FILE_RETRY_RE` (check … workbook … sheet),
so it was classified filename-confirmation AND re-run. Both
`supersedes_pending_task` exemptions (confirmation, refresh) kept the old
eight-price objective alive, and `matching_pending_task`'s refresh branch
returned the stored task BEFORE any new-work check — the orchestrator then
re-ran the price extraction and returned from the confirmed-read lane.
A second trap made a naive fix impossible: `_introduces_new_work` bailed
to "lineage" on ANY confirmation word, and the incident text contains
"correct sheet" / "for confirmation".

## Changed behavior (single authoritative decision)

New public helper `request_extends_objective(message, task)` in
`core/pending_file_task.py`: whether a continuation-shaped turn asks for
work the stored read does NOT cover (new source, changed requested
information, identity resolution), computed by the existing structured
work-signature comparison with retrieval-OPERATION vocabulary
(refresh/presentation words) anchored. Consumers (no per-lane policy
duplication):

- `supersedes_pending_task` — an extending follow-up supersedes (context
  preserved), ahead of the confirmation/refresh exemptions; questions
  exempt as before.
- `matching_pending_task` — coverage gate before the refresh early-return
  (both terminal and pending tasks).
- `recover_pending_task_from_history` — recovery refuses to resurrect the
  old ask under an extending current instruction.
- `merge_pending_task` — an extending turn replaces the task, never merges
  into the old ask.
- `chat_orchestrator._continuation_decision` — the rerun/refresh contract
  is issued only when the stored read covers the whole request; otherwise
  the turn is not a continuation (no format-only contract either).

`_introduces_new_work`'s confirmation-word bail is replaced by
`_is_affirmation_only`: an approval PHRASE (or bare confirmation) with ≤1
qualifier of its own is lineage; confirmation vocabulary inside a
seek-shaped request ("find the correct row", "check … for confirmation")
is requested verification. Articles ("a"/"an") joined the continuation
fillers. Supersession now also stashes the ordered
`requested_targets` with the existing context pins.

Preserved (positive controls, all green): pure/verbose retry, refresh
("check the latest version"), compound retry+presentation ("search again
and a clean response"), formatting-only ("make it cleaner"), bare
approvals/filename confirmations, entity-set edits ("replace U-22 with
U-38" stays a revision of the same objective), canvas-edit precedence.

## Sources changed (working tree, committed)

- `backend/core/pending_file_task.py`
  sha256 f24fefc9bf7998eba8ceacba45eb42abee713fe1eac4ddc0b2908f83b2623155
- `backend/integrations/chat_orchestrator.py`
  sha256 677e1f8467a1af2b37643a6923b3d6cedbc79ff252f68ca5daa0852e2a3b766e
- `backend/tests/test_cross_source_followup_routing.py` (new, 29 tests)

## Tests

- New suite `tests/test_cross_source_followup_routing.py`: 29 passed
  (frozen incident classifier + orchestrator early-return regression +
  generality + positive controls).
- `tests/test_pending_file_task_resume.py`: 166 passed, 2 xfailed.
- Workbook structured-delivery / read-replay / objective-evidence /
  canvas-edit precedence suites: 151 passed.
- Pre-existing failures (fail identically WITHOUT the fix, other streams'
  in-flight work): `test_async_turn_continuation.py` (3),
  `test_chat_canvas_editor.py::test_process_edit_no_apply_stops_before_conversation`.

## Isolated public/browser verification (world `crosssrc_fix_0929`)

World built from the fixed working tree (`--snapshot-working-tree`,
export sha c8e53fc431…, farm @ 79b2a41032; fixture = API-seeded schema +
the frozen 46 workbook parquets, catalog restored from the recorded
`dataset_entries_workbook.json` with parquet paths repointed into the
run's own store). Stack: backend :8052 / frontend :3101, BYOK seeded
(deepseek/opencode-go/openrouter), preview auth world-local. Run DB:
`backend/data/acceptance_worlds/crosssrc_fix_0929/runs/run-2dc6dbd4e4e3/data/atom.db`.

API scenario (`scenario_api_run3.json`, real planner, real providers):

- Session `crosssrc-1790700663`, user ea1aafd9-decb-4472-991c-d1a340701ce3.
- Turn 1 (eight-price ask, request `req-b39ac3249045`, execution
  539cf671-92ef-4459-b0ce-5dccec9ce23a): deterministic structured read,
  ALL 8 items delivered (control — the fix did not break the read lane).
- Incident turn (request `req-d60d11ec1c4e`, execution
  ae712414-4115-4cbb-a5e9-99aa06905b2e): model glm-5.3-flash /
  opencode-go, intent search_request, NOT deterministic delivery, NOT a
  price-table repeat. Answer names the ambiguous items (No. 381, No. 622,
  TK Multi Wheel Gang Slitter), cites candidate rows per item
  (RoperWhitney 88/89/90; 265/266/268; Tennsmith 105/106 vs Tinknocker
  100), reports honestly that the email/description results could not be
  matched, and asks ONE focused clarification.
- Server log line for the incident turn:
  `[pending-file-task] superseded by a newer request` — the fix engaging
  at runtime.

Browser scenario (frontend :3101, form login as admin@example.com;
session `session_1790700821524_ftagjkvsa`):

- Turn 1 (16:55:11, execution 073572af-f8ee-4fda-934b-546f2dca87c7):
  full eight-price read rendered in the chat UI.
- Incident turn (16:55:33, execution 5f5ead8b-a55d-4d92-b91f-8b159a872b70):
  durable assistant row (417 chars) — "I tried to pull Chandrakant's
  email and the workbook description… Could you tell me which of the
  ambiguous machines (No. 381, No. 622, TK Multi Wheel Gang Slitter)
  Chandrakant is inquiring about, or share his email so I can re-run the
  search with a tighter query?" — visible in the UI after scroll
  (`browser_answer_incident_turn.png`).
- Reload: both turns re-rendered from durable rows; the turn-1 price
  answer unchanged; the incident instruction retained verbatim (not
  replaced by the old price objective).
- No outbound message sent; no canvas mutation (read-only turn; the world
  has no mail connector, and the answer reports the email leg as
  unmatched rather than claiming success).

Honest-limit note: this world has no ingested mailbox, so the email leg is
exercised as "source unavailable → honest limit + targeted clarification"
(the directive's accepted outcome). The workbook-description leg is
exercised against the real catalogued sheets. Proving email-search
QUALITY needs a mailbox-seeded run — not claimed here.

## Deployment status

DEPLOYED to the dev stack 2026-09-29 (owner-requested): DB snapshot
`backend/data/backups/atom-pre-restart-20260929-131615.db.gz` (also copied
to the external drive), then `scripts/restart_backend.sh` — healthy pid
70300 on :8001 serving the fixed working tree.

Normal-app probe (`probe_normal_app.py`, `normal_app_probe_run3.json`;
public API on :8001, disposable registered user `probe-check-1@example.com`,
session `crosssrc-probe-1790702589`):

- Turn 1 (eight-price ask, execution 3f155dc1-e9c6-4dc1-ba7c-eb59da530479):
  all eight prices delivered deterministically against the REAL dev
  workbook — the read lane is intact in production.
- Turn 2 — cross-source variant with a DIFFERENT person and DIFFERENT
  channel ("check Priya's text message and or description in workbook…",
  execution a5861609-03ad-4e7a-b91e-f58fac272e74): routed to real planning
  (deepseek-v4-pro / fireworks), NOT a deterministic price re-run, no
  price-table repeat; the answer honestly reports Priya's message was not
  found in the available data and asks for the missing input. Server log
  carries `[pending-file-task] superseded by a newer request`.
- Registrations rate-limited after two probe users — `probe-check-1@…`
  is the only row created; deletable by the owner along with session
  `crosssrc-probe-1790702589`.

## Domain independence

- Diff audit: the only domain words in the change are comments quoting the
  incident; the added vocabulary is generic retrieval-operation words
  (latest/version/refresh/clean/table/…) and articles.
- Pinned matrix (`TestDomainIndependence`): six source/target pairs —
  calendar+PDF, CRM+billing, Slack+CSV, drive+sheet, wiki+notes, plus the
  incident's messaging+workbook — each asserting the cross-source follow-up
  supersedes and never resumes, while same-read retry controls and bare
  approvals stay lineage in every domain. 205 passed in the two routing
  suites after the matrix landed.
- Live generality evidence: the :8001 probe used a different person
  (Priya) and channel (text message) and routed identically to the
  incident's Chandrakant/email shape.

## Earlier verification (isolated world, pre-deployment)

## Disposables for the owner to delete

World `crosssrc_fix_0929` (~360 MB) + farm
`/Users/rushiparikh/projects/atom/.preview-farms/crosssrc_fix_0929` once
the evidence is no longer needed. The preview stack is DOWN.

## Addendum (2026-09-29 evening): the row-338 follow-up chain

The owner continued the ORIGINAL session (replay-retry2-20260923) on the
deployed fix and hit a NEW failure: after "…no. 381 is on Tennsmith sheet
of the workbook under row 338 … $3,254.00 . find this in the workbook",
the agent could not confirm the row. Four distinct seams, each fixed
TDD-first and verified live on :8001:

1. `aa017c587` — ANAPHORIC FILE REFERENCE: "find this in the workbook"
   names no `.xlsx` file, so the deterministic file-ask lane never fired
   and the turn fell to mail/integration planning that cannot match
   workbook cells. `_resolve_anaphoric_file_mention` resolves the generic
   reference against the conversation's RESOLVED identity (live task or
   supersession stash); questions and confirmation-shaped turns excluded.
2. `b834d68da` — PIN THREADING: the reader derived the file from the ask
   text only and still returned None. `_direct_confirmed_file_read` now
   passes `named_file_mention` (resolved_file name, stored mention as
   fallback) and `_datasets_named_file_block` consumes the pin when text
   detection is empty (also fixes legacy extensionless stored mentions).
3. `54d9b43fa` — PASTED DATA ROW: the user's own pasted row ("here's the
   data: 381<TAB>167072381…") colon-mined as the constraint
   `s_the_data = "381 167072381 Roll Bending Machine"`, filtering every
   row. `_is_data_payload_value` rejects constraint values with tabs or
   2+ standalone numbers.
4. `664ad0807` — POSSESSIVE SOURCE REFERENCE (the one that produced the
   live all-miss): the earlier turn "check Priya's text message… in
   workbook" mined organization="Priya", which rode the user history into
   the next read and filtered every row. The possessive miner now skips
   "<name>'s <communication-source noun>" — a source reference, not a
   row attribute.

Verified live (:8001, probe session, exact user wording): the turn now
serves deterministically in ~3s with the row bound —
`381 - 3,254 (Tennsmith!R338, identity A338, column E338 'PRICE'; also
M338 'U.S. LIST' 1,845, O338 'U.S. COST' 1,476 …)` — plus honest
outcomes for the other extracted targets (exchange-index match flagged,
row-number target reported absent, "Roll Bending Machine" left
ambiguous with candidates). Backend restarted twice more with the
documented snapshot procedure (pids 89980, 93166, 94478 healthy).
Suites: routing 45, artifact 27, resume+workbook neighbors 299 passed
+ 2 xfailed. The owner can simply re-send the message in their own
session; no state migration is needed.
