# Chat orchestrator: end-to-end implementation and app readiness

Date: 2026-09-26. Status: work order, not evidence of readiness.

## 1. Mission and ownership

Make the actual Atom app ready for the user to manually exercise representative chat workflows soon, then close the remaining reliability and search gates. The receiving agent owns frontend, backend, fixtures, test harness, browser verification, launch configuration, and handoff. There are no assumed separate owners. Do not end with assignments to nonexistent streams or a list of tests someone else must run.

Deliver two explicit milestones:

1. **Manual-test preview:** a running app with a verified small set of usable workflows, seeded examples, clear limitations, and a short user test script. Reach this before optional ranking optimization or broad connector expansion.
2. **Supported-workflow readiness:** the same user-visible workflows satisfy lifecycle, search, delivery, failure, recovery, and UI acceptance on a final frozen source.

Neither milestone certifies all integrations or all possible conversations. Publish the supported-workflow list and exclusions. Do not promise universal orchestrator completion.

## 2. Integrate the existing plans

Read repository `AGENTS.md`, `CLAUDE.md`, recent commits, and `notes/AGENT_COORDINATION.md`. Then use these plans rather than creating competing machinery:

- [Lifecycle/evidence closeout](LIFECYCLE_EVIDENCE_CLOSEOUT_PLAN_2026_09_26.md): identity/value evidence, durable delivery, retries, recovery, and 27 public-boundary cases.
- [Search work order](AGENT_SEARCH_WORK_ORDER_2026_09_26.md): retrieval outcomes, constraint preservation, ranking measurements, and held-out evaluation.
- Existing lifecycle schema/work order, contracts and workbook work order in this directory.

This document supplies the integrated execution order and UI/user-readiness requirements. Preserve the detailed guarantees in those plans. Search benchmarking beyond correctness is not a prerequisite for the first manual preview; missing authorization, false claims, destructive behavior, or broken persistence are.

At plan creation there are in-flight changes in answer presentation, hybrid retrieval, document hybrid search, memory assembly, and the acceptance launcher. Inspect and preserve them. Do not overwrite the current implementation based on an earlier agent summary.

## 3. Supported pilot scope

Implement and demonstrate these workflows through the app:

| Workflow | User outcome |
|---|---|
| General chat | A normal question receives a relevant answer without accidental workflow execution |
| Named-file lookup | Correct requested entities and values, readable output, expandable exact evidence |
| Conversation continuation | Formatting, field selection, correction, item replacement, and explicit re-search retain the current objective correctly |
| Cross-source retrieval | A document/message question finds supporting evidence and distinguishes current, saved, missing and failed sources |
| Canvas editing | An authorized edit changes the intended artifact once; denial and no-apply are truthful |
| History and recovery | Refresh, restart, retry and interruption preserve context and do not duplicate effects |
| Overlapping turns | Two tabs/requests cannot mix execution, messages, streams or evidence |
| Sandboxed outbound action | Draft and authorized simulated send use the general tool/authorization path; no real external recipient is contacted |

If an adapter is unavailable, expose that honestly and keep the capability outside the supported list. A recorded connector fixture establishes adapter/transport behavior only, not live connectivity. At least one real configured model must produce a successful browser-visible turn before claiming the preview ready for normal chat. Never represent scripted provider output as real-model quality evidence.

## 4. Environment and data safety

Create an isolated test world from a sanitized fixture/snapshot using existing acceptance tooling. Never point destructive tests, corruption injection, race tests, or schema preparation at the live dev database. Do not reseed the user's app. Preserve backups and use SQLite backup APIs where applicable.

Launch your own backend and frontend on available ports. Verify the frontend's API proxy, HTTP endpoint, authentication, WebSocket endpoint and artifact links all target the same isolated world. A separate frontend port alone does not prove isolation. Inspect actual browser network traffic, server process identity and opened database paths.

Use environment-owned test authentication. Do not copy credentials into this document, source, screenshots, logs or final report. Use configured model access only through existing credential mechanisms. Fault tests and simulated sends must remain credential-scrubbed or confined to controlled sinks. If real model access is unavailable, deliver the working fixture preview labeled accordingly and state the exact unmet real-chat gate; do not claim it passed.

Preflight must verify source manifest, loaded module paths/hashes, schema, effective lifecycle/finalization flags, launch identity, database/data paths and fixture identity. Resolve symlinks. A new production change requires a new source fingerprint for final acceptance. Never replace an export under a running server.

Leave the preview running for the user when feasible. Provide exact URLs, supported login instructions without exposing secrets, log locations, and safe restart steps. Do not restart or replace the user's usual environment just to make the preview available. Any later rollout to that environment follows the repo snapshot/restart procedure.

## 5. Phase 0 — Establish the actual app path

Trace one browser request through:

`chat/canvas composer → frontend proxy/client → chat route → task/intent resolution → tool/search/edit → evidence and verification → finalization → durable delivery → HTTP/stream → bubble/history`

Inspect at minimum:

- `frontend-nextjs/pages/chat/index.tsx`, `pages/canvas/[id].tsx`, `components/GlobalChatWidget.tsx`, `hooks/chat/useChatInterface.ts`, and the actual API proxy modules used by those surfaces.
- `backend/integrations/chat_routes.py`, `chat_orchestrator.py`, `core/pending_file_task.py`, `chat_tool_planner.py`, `task_lifecycle.py`, `chat_transport.py`, `answer_presentation.py`, and the current source adapters.

Find parallel entry points and behavior differences. Test both ordinary chat and canvas-bound chat; do not infer one from the other. Record which flags/routes are in use and remove obsolete configuration assumptions from the harness. Do not add another router or presentation rewrite after finalization.

Deliverable: one-page route/config map, reproducible launch, fixture inventory, baseline screenshot and actual request/response trace. Then proceed directly to the preview, not a broad rewrite.

## 6. Phase 1 — Earliest manual-test preview

Implement only the fixes necessary for this first usable slice, reusing current code:

1. Login, open chat, send a general question, and see a real-model response.
2. Open the seeded workbook/canvas and execute the original eight-item lookup. Preserve requested order, ambiguity and exact identity/value evidence; no diagnostic dump.
3. Ask for a cleaner answer, then re-search. Formatting reuses evidence; re-search performs a new observed attempt. Prior answers remain unchanged.
4. Refresh the browser; history and evidence association survive.
5. Edit a disposable canvas through the authorized path; verify the artifact itself changes exactly once. Exercise a denied edit and confirm no fallback mutation.
6. Disconnect or fail a source through isolated controls; the app reports the failure instead of claiming absence or success.

A preview may have explicitly listed advanced cases still pending. It may not have unsafe mutations, mixed live/test environments, false success claims, or a broken login/send/reload path in the advertised workflows.

Immediately produce `MANUAL_TEST_QUICKSTART.md` with the running URLs, fixture names, six copyable prompts, expected visible outcomes, and known limitations. Verify those steps in the browser yourself before inviting the user. Do not wait for full search tuning to provide this milestone. Continue the remaining work after publishing the preview status.

## 7. Phase 2 — Complete conversation semantics

Use the existing task/continuation mechanism to distinguish presentation changes, evidence refreshes, field selection, objective changes, authorization, cancellation and unrelated conversation. Do not add per-route keyword classifiers.

Carry current task entities, fields, source restrictions, freshness and authorization through the full message list and durable state. Do not union old distractor lists into the current request. A new objective must not inherit stale authorization. A return to an earlier task must resolve its identity explicitly or clarify when ambiguous.

Required conversations include:

- Ask → formatting → select a field → replace one item → re-search.
- Ask → unrelated question → resume the earlier task.
- Correct a mistaken assumption → verify subsequent search uses the correction.
- Ambiguous follow-up → focused clarification, with no mutation while unresolved.
- Stop while work is active → stop pending work where possible, report completed effects honestly; do not claim an already-applied effect was undone.
- Restart/cache loss → resume with the same explicit identifiers and constraints.

Evaluate tool/source choice separately from final answer wording. For an LLM-resolved transition, retain the proposed transition and deterministic validation result. Never treat model confidence as authorization or proof of task completion.

## 8. Phase 3 — Finish reliability and search correctness

Execute the lifecycle/evidence closeout plan, including exact identity cells, large replay projection, immutable transport pins, intentional HTTP statuses, delivery history, claim races and crash reconciliation. Reserve operations before mutations. Persist final delivery before claiming durability. Distinguish uncertain outcomes from successful or absent results.

Implement the search plan's correctness phases next: preserve constraints, distinguish successful-empty/partial/failed retrieval, retain source scope, and read supporting content before making precise claims. Fix incorrect reranker configuration and blocking execution where the path is active. Do not delay delivery to add optional contextual indexing or a new search engine.

After correctness, run the search baseline/held-out comparison and adopt ranking changes only when supported by measurements. Track index/model version and fallback behavior. No claimed accuracy percentage based only on the workbook incident or agreement between two models.

## 9. Phase 4 — UI behavior contract

The user should see ordinary task language, with technical detail in expandable evidence/diagnostics:

- Acknowledgement that a request was accepted, followed by meaningful state: searching, waiting for clarification/approval, complete, failed, or outcome uncertain.
- Concise answers in requested order; source freshness and material limitations visible without repeated warnings.
- Evidence disclosure linking each claim to its source and exact identity/value references where applicable.
- A retry action that preserves request identity for transport retry. A new user request, including identical text, gets a new identity. Clarify how UI retry differs from explicit re-search.
- Recoverable errors retain the user's draft and do not leave an indefinite spinner or duplicate assistant bubble.
- Each stream and final response binds to its own execution. Ignore foreign events and handle reconnects, late tokens, final replacement and reload without duplication.
- Provisional streamed content is not treated as finalized evidence. If finalization changes the answer, the final bubble and history must reflect the corrected answer; do not leave stale success text in the UI.
- Authorization denial, unavailable source, unavailable model and uncertain effect are distinguishable. Do not expose internal stack traces or claim generic success.

Review ordinary chat, global chat widget, and canvas chat for consistency. Use existing components where possible. Avoid redesigning the entire UI.

## 10. Phase 5 — Integrated acceptance

Reuse the existing harness and add browser-level checks. Maintain independent required-case IDs, run all cases, preserve Boolean checks and distinguish FAIL, ERROR, BLOCKED and NOT RUN. Do not combine different source fingerprints into a single passing report.

Required suites:

1. All lifecycle closeout cases C00–C26, including actual effect counts.
2. Search work order development/held-out cases, with explicit quality and latency reporting.
3. Conversation sequences in Phase 2, including semantic variations not present in implementation examples.
4. Browser login/send/stream/final/retry/reload on ordinary and canvas chat.
5. Frontend/backend disconnect, provider failure, source failure, restart and overlapping tabs.
6. Access-scope and prompt-injection checks: retrieved text cannot authorize actions, override source restrictions or change recipients; denied reads/mutations remain denied across fallback paths.
7. Repeated sequential turns and overlapping requests on the intended local deployment. Record latency, errors and resource use; set the acceptance budget before comparison. Do not claim multi-host readiness from local process tests.

Use a token-bearing shim for deterministic stream protocol tests and at least one real-model browser smoke test. Report these separately. Use a controlled durable sink for simulated outbound actions and mutation counters; operation rows alone are not proof of effect count.

For each failure identify the first divergent boundary: interpretation, source selection, query, evidence, verification, delivery, frontend, or evaluator. Fix the demonstrated cause. Do not infer a shared cause from similar visible symptoms.

## 11. Manual user test script

Put these steps into the quickstart using the actual running fixture names and URLs. The agent must perform them first.

| Step | User action | Expected visible behavior |
|---|---|---|
| M01 | Ask a normal question | Relevant response, no unintended task/action |
| M02 | Request the seeded eight-item lookup | Eight ordered entries; honest ambiguity; readable evidence |
| M03 | “Make this easier to read” | New concise answer; prior answer unchanged |
| M04 | “Search again and show the same items” | New read; saved/live status truthful |
| M05 | Select one source field/basis | Correct labeled values; no silent substitution |
| M06 | Replace one requested item | Updated list without resurrecting old distractors |
| M07 | Ask unrelated question, then resume | Correct task resumption or focused clarification |
| M08 | Refresh and reopen canvas | Same final answers, artifact and evidence association |
| M09 | Make an authorized disposable edit | Intended artifact changes once |
| M10 | Try an unauthorized edit fixture | Clear denial; artifact unchanged |
| M11 | Use controlled failure fixture, then retry | Honest error/recovery; no duplicate effect |
| M12 | Send from two tabs | Replies and streams stay attached to their own turns |
| M13 | Draft, then authorize a simulated send | No effect during drafting; one recorded sandbox send |

Do not ask the user to perform crashes, corruption injection or database inspection. Those are automated/agent-operated cases. Provide a simple feedback template: step, expected behavior, actual behavior, time, and optional screenshot; the agent correlates it to execution details.

## 12. Release and stopping criteria

### Manual-test preview gate

Phase 1 passes in the actual browser; supported/excluded capabilities are explicit; the environment is isolated and usable; no known unsafe mutation, false completion, or broken durability in the advertised flow. Publish exact URLs and leave the preview running. If a prerequisite is missing, state it precisely rather than claiming readiness.

### Supported-workflow readiness gate

All required critical cases are exercised and pass on the final fingerprint. Critical means access/authorization violations, duplicate or wrong effects, cross-turn identity confusion, lost durable task/delivery state, unsupported success/absence claims, and broken advertised workflows. Unexercised required cases keep acceptance incomplete. Noncritical cosmetic limitations may be documented without blocking readiness if they do not obscure meaning.

Complete the work under this assignment without repeated approval requests for ordinary reversible fixes. Respect existing authorization boundaries: this plan does not authorize sending real messages, deleting user data, or publishing externally. A genuine external dependency can block its case, but not independent progress.

Do not install a new framework or replace the whole orchestrator during closeout. Propose architectural changes separately only if measured residual failures cannot be handled responsibly in the existing design.

## 13. Deliverables

Create a readiness report and quickstart under the existing orchestration-migration docs, and evidence under the existing acceptance structure:

- `MANUAL_TEST_QUICKSTART.md`: exact launch URLs, supported workflows, fixture prompts, expectations, limitations, safe restart and feedback instructions.
- `CHAT_ORCHESTRATOR_READINESS_REPORT.md`: baseline, changes, final support matrix, every required suite/case status, and remaining limitations.
- Immutable source/export/config/schema/fixture manifests with secret-free process and loaded-module identity.
- Per-case public requests/responses, execution-bound stream events, actual effects, operation/evidence/delivery/pin associations and browser observations.
- Search quality/latency comparison, real-model versus shim coverage, scoped test results and rollback guidance.

The user-facing handoff should start with: where to open the app, what they can test now, and what remains limited. Implementation counts belong in the supporting report. Do not say “everything is complete” when only backend tests pass or the browser still points at a different world.
