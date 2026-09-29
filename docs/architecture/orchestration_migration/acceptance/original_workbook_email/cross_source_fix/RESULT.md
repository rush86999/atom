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

NOT deployed to the dev stack. The fix is verified in the isolated world
only; :8001 was left untouched. To roll out when in scope:
`scripts/restart_backend.sh` (snapshot + restart), then re-run this
scenario in the normal app.

## Disposables for the owner to delete

World `crosssrc_fix_0929` (~360 MB) + farm
`/Users/rushiparikh/projects/atom/.preview-farms/crosssrc_fix_0929` once
the evidence is no longer needed. The preview stack is DOWN.
