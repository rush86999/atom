# Original canvas: cross-source confirmation swallowed by file retry

Read-only diagnosis, 2026-09-29. No production changes, chat requests, live writes or restarts. Evidence: `evidence.json`; exact user message reproduced against the pure pending-file classifier with no application/database imports. Live DB inspected using SQLite mode=ro and query_only. PID 12881 on :8001 has open handles to backend/data/atom.db.

## Distinguish three turns

- The 22,595-character diagnostic answer is historical: assistant message 4b72410a-4723-451f-b7b4-af93c4e88cd5, 2026-09-26 10:36:35.
- The new 2026-09-29 15:02:52 clean-response turn delivered 1,858 characters, eight items, compact style. Metadata records a new_read attempt, not the old dump.
- The 15:05:19 request to check Chandrakant's email and workbook descriptions delivered 2,233 characters, deterministic/structured, a new workbook attempt, requested_fields=[price]. Its presentation action still names the ORIGINAL eight-price request. This is the new failure.

Session: replay-retry2-20260923. Latest execution: 3d8a0a69-417e-421d-a764-92e03b027315. User message: e0ca2662-b1ba-49fc-9708-682c098974a9. Assistant: 814e282f-c425-4400-9513-4741437e01d9.

## Mechanism reproduced

core/pending_file_task.py `_FILE_RETRY_RE` accepts check/read/search followed by up to 80 arbitrary characters and workbook/sheet/file; it does not require an explicit retry or constrain introduced work. Exact matched span:

`check Chandrakant's email and or description in workbook to find correct sheet`

For the complete user request the actual functions return:
- is_filename_confirmation=True
- is_rerun_request=True
- classify_file_operation='re-run'
- supersedes_pending_task=False
- matching_pending_task returns the old retrieved price task.

The refresh branch in matching_pending_task returns the pending task before its history/new-work checks. The orchestrator resolves this task before ordinary planning, calls the direct file reader with the stored original request, renders the price evidence, and returns from the confirmed-read lane. The recent canvas-edit precedence guard does not cover this research request, and should not be extended with another email-specific regex.

Navigation: pending_file_task.py `_FILE_RETRY_RE` (~72), is_filename_confirmation (~178), supersedes_pending_task (~412), matching_pending_task (~541, especially refresh return ~620). chat_orchestrator.py pending task match (~4496), canvas precedence (~4566), pending direct-read branch (~5337). Resolve symbols against current hashes, not offsets.

This is objective substitution by an overbroad retry classifier and an early-return fast path. New retrieval alone is not task completion. The user requested additional evidence to disambiguate identity; the executed contract remained price extraction from the same workbook. The same source revision on both turns is legitimate; it does not explain ignoring the email request.

## Correct scope of fix

Use the existing request/continuation and plan-relevance mechanisms to distinguish repeating the SAME read from adding sources, changing requested fields, comparing descriptions, or resolving identities. Preserve the active eight items as context without preserving the old action as the entire objective. Deterministic direct delivery is allowed only when it satisfies the CURRENT request in full. Cross-source work must reach the existing search/planner and evidence-comparison path.

Do not hardcode Chandrakant, email, these product names, or a particular connector. Do not solve by forcing all traffic through the LLM or dropping saved evidence. If requested email cannot be accessed, report that exact limitation instead of claiming the repeated workbook list answers the request. Do not assume downstream search correctness until that path is exercised.

Regression requirements:
1. Old workbook result + exact reported message does not resume the old task as the sole objective; email/description evidence is sought and identity candidates compared.
2. Equivalent additional-source requests for another person/document/integration behave consistently.
3. Bare confirmation, formatting-only, explicit same-read retry, compound retry+formatting, target replacement and canvas edit retain their existing distinct behavior.
4. New-source request containing 'again' still preserves the extra work rather than discarding it.
5. User-facing answer identifies checked evidence, candidate resolution or remaining ambiguity; no guessed row or selling price; preserve user-confirmed vendor-quote values outside workbook evidence.
6. Verify through the public chat/browser with old-session state in a small isolated fixture, then verify approved deployment separately. No email send or original-canvas mutation is needed for the diagnosis.

Why previous acceptance missed it: prior reported successes cover lookup, formatting, retry, replacement, and draft edits. They do not establish cross-source disambiguation after an active workbook objective. This exact transition needs its own test; the current report is not a claim that the subsequent email-retrieval layer works.
