# Agent directive: stop workbook retry from swallowing new research

## Assignment

Fix the demonstrated original-canvas failure and verify the actual cross-source task. The user's latest request asks the app to consult an email and workbook descriptions to resolve ambiguous machine identities. The app instead repeats the old workbook-price lookup. Do not reopen generic recovery, model selection, or framework migration. One writer owns this fix through boundary verification.

Read AGENTS.md, CLAUDE.md, recent scoped diffs and coordination notes before editing. Preserve concurrent work. Record a short start/finish pointer in notes/AGENT_COORDINATION.md. Execution of implementation and isolated verification is authorized; do not stop after reproducing the known classifier error to ask whether to continue. Do not send email or mutate the original live canvas as a test.

## Ground truth and exact reproduction

Primary diagnosis and compact evidence:
- `acceptance/original_workbook_email/root_cause_2026_09_29/DIAGNOSIS.md`
- `acceptance/original_workbook_email/root_cause_2026_09_29/evidence.json`

Paths above are relative to this document's directory. Original canvas: `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb`. Session: `replay-retry2-20260923`.

Latest failed instruction:
> check Chandrakant's email and or description in workbook to find correct sheet and row from workbook for confirmation

User message `e0ca2662-b1ba-49fc-9708-682c098974a9`; assistant message `814e282f-c425-4400-9513-4741437e01d9`; execution `3d8a0a69-417e-421d-a764-92e03b027315`, recorded 2026-09-29 15:05:19.

Stored original objective:
> find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16

The pure current classifier reproduces:
- `_FILE_RETRY_RE` matches `check Chandrakant's email and or description in workbook to find correct sheet`;
- filename confirmation=True, rerun=True, operation=re-run;
- supersedes=False; matching_pending_task returns the old retrieved task.

The actual answer metadata corroborates the consequence: deterministic/structured answer, new_read attempt `attempt-0a894d11-1dc7-42a2-89ae-a33b70ca69ea`, requested_fields=[price], presentation intent still names the original eight-price question. The reply remained a candidate list, not cross-source disambiguation.

Do not misdiagnose cached replay: there was a new workbook attempt. The prior 15:02:52 clean-response request delivered a compact 1,858-character response. The 22,595-character dump in the pasted conversation is September 26 history. New read + wrong objective is the current defect.

## Trace the whole decision path before changing it

Relevant locations (resolve symbols; offsets are hints):
- `backend/core/pending_file_task.py`: `_FILE_RETRY_RE` (~72), `is_filename_confirmation`, `is_rerun_request`, `is_retrieval_refresh_request`, `classify_file_operation`, `supersedes_pending_task`, `_introduces_new_work`, `matching_pending_task` (~541).
- `backend/integrations/chat_orchestrator.py`: pending-task matching (~4496), canvas-edit precedence (~4566), cached delivery (~4603), ask direct read (~4900), pending direct read (~5337), `_continuation_decision` (~14181), `_continuation_from_plan`.
- `backend/core/plan_relevance.py`: request reference and relevance checks; inspect existing task/objective resolution and source-comparison mechanism.
- `backend/core/chat_tool_planner.py`: ToolPlan contract, retrieval_operation/presentation fields and existing search tool dispatch.
- `backend/core/workbook_read_artifact.py` and `core/answer_presentation.py`: evidence semantics and candidate/description data consumed downstream.

The regex allows arbitrary words between a read/check verb and workbook/sheet, treating any such request as an explicit retry. `supersedes_pending_task` exempts it. `matching_pending_task` returns early on refresh before its new-work/history checks. The orchestrator then executes the stored request and returns before general planning.

IMPORTANT secondary trap found during this directive: `_introduces_new_work` returns False whenever `_CONFIRMATION_WORD_RE` matches after mention stripping. The exact incident contains “correct sheet”. Simply moving a call to that helper ahead of the refresh return may STILL classify this request incorrectly. Prove each decision on the exact wording; fix the general distinction between affirmative confirmation and a requested correction/verification, not this person's name.

Also inspect `_continuation_decision`: it returns a refresh/rerun decision before later new-work exclusions. Patching only matching_pending_task can leave a parallel path carrying the same wrong contract. Inventory all callers; do not duplicate slightly different policy in each lane.

## Required semantics

The old task supplies context (eight identities, selected workbook, prior evidence), not authority to discard the current instruction. Decide separately:
1. Which entities and prior sources are referenced?
2. What action and information are requested NOW?
3. Are sources/constraints/fields added or changed?
4. Can the deterministic file path fulfill the entire current request?

Use the existing intent, continuation, task-revision and relevance mechanisms. Keep a single authoritative decision consumed by matching, supersession and direct-delivery eligibility where feasible. A conservative fast path can decline to handle uncertain cases and pass full context to normal planning; it must not silently answer the old question.

Rules:
- Explicit same-objective retry continues the existing read; formatting-only reuses evidence; keyed transport replay remains distinct.
- A request adding evidence, another source, a description comparison, or identity resolution must not be completed solely by rerunning price extraction.
- Additional work remains additional work even when the turn includes “again”, “correct”, “confirmation”, or a known filename.
- Preserve ordered target identities and relevant source pins as context when routing to the current task. Do not fix the bug by clearing all history, losing entities, or making every turn a new unrelated task.
- Preserve the explicit canvas-edit precedence fix and mutation authorization. A research request does not mutate the email draft.
- No name-specific, email-specific, workbook-brand-specific, or product-specific production exclusions. The same behavior must work for other connectors/documents.
- Do not route every simple file lookup through free-form narration; retain deterministic evidence delivery when it fully answers the current instruction.

The request says “email and or description”: resolve the alternatives honestly. Prefer retrieving the named email plus relevant workbook descriptions when available. If a source is unavailable, identify that limit, use permitted available evidence, and ask only for a specific remaining ambiguity. Never claim an email was checked because its name appears in the prompt.

## Implementation sequence

1. Freeze the incident input and a minimal old-task/session fixture using the saved evidence. Keep private email content out of ordinary test logs.
2. Add a failing regression demonstrating both classifier behavior and the real orchestrator early-return error. A classifier-only test is insufficient.
3. Trace existing new-work detection, request resolution and plan relevance, then implement the narrow general policy correction. If introducing a genuinely new architectural mechanism, follow repo research requirements first; the default is reuse.
4. Ensure the normal planner receives the current instruction plus the existing item set and evidence references, not the original price ask substituted as the new message.
5. Trace actual downstream retrieval: named email identification, relevant workbook descriptions, candidate comparison. Fix a demonstrated downstream blocker if routing succeeds but the task still fails. Do not count merely reaching an LLM as completion.
6. Keep ambiguity resolution separate from price sourcing. A matching email description can identify a product; it does not authorize converting currencies, selecting a cost column as selling price, or replacing a vendor quote.
7. Run focused regressions and the isolated public/browser scenario. Only then prepare the intended dev rollout using the repository backup/restart procedure if deployment is in the active authorized scope. Record isolated and normal-app results separately; do not restart :8001 merely for investigation.

## Regression matrix (mandatory)

| Input with prior workbook result | Expected behavior |
|---|---|
| Exact Chandrakant instruction | New evidence/identity-resolution task; old price task cannot be sole answer |
| Same wording with another person's message or another document | Same generic routing, no named-entity special case |
| “Search again and check the supplier message to confirm which model” | Retry plus extra source retained; no early same-task-only return |
| “Use the description in the workbook to identify the correct row” | Requested information changes from price extraction to identity comparison |
| “That filename is correct” / “yes” | Existing legitimate confirmation/redelivery behavior; no invented retrieval |
| “Search again” | New observed attempt against the same source/objective |
| “Search again and give me a clean response” | Retrieval and presentation both honored |
| “Make it cleaner” | Presentation action only; no new read; previous delivery unchanged |
| “Replace U-22 with U-38” | Existing ordered target revision behavior; no accidental canvas edit |
| Explicit edit with attached canvas | Existing edit lane still wins; authorization/effect verification intact |
| New source inaccessible | Honest source-specific limit; no fabrication or silent success |
| Relevant email found but two models still fit | Show evidence-backed candidates and one focused clarification |

For tests with fabricated provider results, label controlled routing/effect coverage. At least one end-to-end run must use the actual available source and real configured planner; controlled evidence does not prove email-search quality.

Test the helper trap explicitly: “find the correct row” and “check … for confirmation” are requests, not bare approvals. Include positive controls so simply disabling every fast path cannot make the suite look green.

Relevant existing suites include test_pending_file_task_resume.py, workbook structured-delivery/replay suites, objective/derivation independence suites, and canvas-edit precedence tests. Discover current names via rg; do not invent a giant full-suite requirement. Re-run affected neighbors after each substantive change. Preserve assertions; distinguish product fixes from flawed fixture assumptions.

## Public/browser acceptance on the original state

Use a small isolated fixture and a disposable clone of the original canvas. Seed via supported product/import APIs; verify run DB identity. Do not copy the entire live database merely to reproduce session context. Existing recorded fixture and workbook parquets/index metadata are starting points.

1. Log in through the browser, open the cloned email canvas, and establish the original ordered eight-item workbook task.
2. Submit the clean-response follow-up, then the exact failed cross-source request with a new request ID.
3. Capture actual request/execution/message IDs and retrieval operations. Subscribe before traffic if observing events. Inspect both tool dispatch and result consumption.
4. Confirm the email evidence is bound by its actual message identity/sender/date/subject and workbook evidence by sheet/row/identity cells/description cells. Do not select the latest unrelated email or latest session artifact.
5. Require the answer to explain the relevant description match and the candidate decision—or exactly what remains ambiguous. Avoid repeating all price bases when they do not help resolve identity. Put full provenance in an expandable evidence area or concise source note.
6. Verify original requested items remain intact, no email/canvas mutation occurred for this read-only instruction, and no outbound message was sent.
7. Reload: the answer and evidence association persist, prior answers remain unchanged, and the new instruction is not replaced in durable task history by the old price objective.

The user confirmed No. 381's $2,902 is a manually calculated vendor-quote price. Preserve that attribution if it is relevant; workbook absence does not invalidate it. Do not infer CAD from an unlabeled Price column. No. 622/slitter selections need actual descriptive evidence or an explicit user selection; prior proposed drafts are not ground truth.

## Evidence and final handoff

Write the compact result package under `acceptance/original_workbook_email/cross_source_fix/` relative to this directory. Include source/export/config/run-DB binding; before/after decision traces; independent evidence comparison; tests; redacted browser captures; answer screenshot; per-case verdicts. Use exact IDs, not timestamp proximity or latest-row queries. No credentials or bulk private mail dumps in commits.

Done means: the exact request no longer becomes a price retry, the requested sources are actually consulted or honestly reported unavailable, the user receives a useful grounded disambiguation, and reload preserves it. A new attempt ID, an LLM call, green helper tests or another price summary is not completion.

Final response should state root cause, changed behavior, the resulting answer or precise unresolved question, tests and browser verification, deployment status, and the disposable conversation/canvas link. No email sent. Do not broaden this work into background-recovery closure or model benchmarking. If interrupted, save the completed case and first unfinished action; resume execution rather than writing another plan.
