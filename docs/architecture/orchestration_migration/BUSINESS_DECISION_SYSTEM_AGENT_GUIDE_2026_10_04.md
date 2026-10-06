# Business decision system implementation guide

## Objective and scope

Build an employee that chooses and completes useful actions within a business's context, taught procedures and authority. The first job is Brennan's quotation workflow: research requested machinery, reconcile sources, calculate prices under an approved policy, evaluate suitable alternatives, and prepare an accurate email. Another business must be able to use the same mechanism with different training, tools and criteria.

This is an implementation assignment, not an invitation to replace the orchestrator, create another framework, or continue writing architecture summaries. Extend the existing task lifecycle, action program and integration execution paths. Complete the milestones below in order. First make the real multi-source investigation reliable; then add the pricing and alternatives capabilities needed by the business procedure.

Do not hardcode Brennan, machine identifiers, workbook names, vendor names, markup percentages, email addresses, or source order into production routing. Those belong in fixtures, user input, teaching or business configuration. Explicitly authorized research should not require repeated permission requests. Teaching does not itself grant authority to edit or send.

## Verified starting point and active work

Source inspection on October 4, 2026 found HEAD `8db6f9908`, following `622904302` and `bea8bf4b5`. This document describes source structure, not a certification of the running application.

At inspection, another writer had uncommitted changes in `backend/core/chat_tool_planner.py`, `backend/core/task_lifecycle.py`, `backend/integrations/chat_orchestrator.py`, `backend/tests/test_job_work_ledger.py`, and `backend/tests/test_fallback_chain_workflow.py`. The working tree already contains multi-source begin/settle calls that the earlier completion report said were absent. Do not implement that wiring again from the old report. Inspect the current diff, contact the owner through the authorized coordination process, and verify its actual behavior. One writer owns shared orchestration changes at a time.

Read `AGENTS.md`, `CLAUDE.md`, recent commits and the bounded tail of `notes/AGENT_COORDINATION.md` before editing. Append your scope and findings; do not rewrite the large coordination file. Preserve others' staged and unstaged work; no stash/reset-based baseline experiments in the shared checkout.

Line references below were measured in this changing checkout. Resolve the named symbol again before editing. Record source hashes, runtime configuration and the actual database used by the serving process. HEAD and a checkout digest alone do not establish serving identity.

## Code map and boundaries

Paths are relative to the repository root. These are starting points to trace, not permission to edit every listed module.

| Responsibility | Existing source and entry point | What to verify before changing it |
|---|---|---|
| Public chat | `backend/integrations/chat_routes.py` | Request identity, authenticated context, history, replay and final response binding. This is not `backend/api/chat_routes.py`. |
| Turn coordination | `backend/integrations/chat_orchestrator.py` | Actual selected lane and all callers of planner/executor. Search `MULTI_STEP_PROCESS`, `plan_tool_use`, `execute_tool_plan`. |
| Multi-source invocation | Same file, `_ms_tl_begin` near 12886 and `record_read_outcome` near 13140 | New uncommitted wiring exists. Determine which individual tools it covers, whether no-plan and error branches are recorded, and whether useful work actually continues. |
| Existing direct read lanes | Same file, `begin_retrieval_turn` near 6670/7874 and `record_read_outcome` near 7159/8316 | Reuse semantics without duplicating records when the same execution passes through multiple layers. |
| Freshness | Same file, `_verify_source_freshness` near 10785 | Separate refresh attempt/failure from successful saved-copy readability. Do not derive access failure from planner prose. |
| Planner | `backend/core/chat_tool_planner.py`: `ToolPlan` near 714, `plan_tool_use` near 1163 | Tool exposure, supplied context/teaching, plan parsing, bounded repair and returned planning metadata. |
| Tool execution | Same file, `execute_tool_plan` near 8193 | Returns prompt text or `None`; neither alone is a sufficient execution receipt. It returns early without a usable plan/service. Some branches also ingest content, so do not assume every action is side-effect free. |
| Integration execution | `backend/integrations/universal_integration_service.py`: `execute` near 888, `_dispatch_execution` near 1127, `search` near 1225 | Common place for actual service outcomes; trace local dataset and other bypass paths too. Keep owner-scoped credentials and tool error reporting. |
| Job persistence | `backend/core/task_lifecycle.py`: `find_active_task_for_canvas` near 776, `attach_operation_field` near 1138, `begin_retrieval_turn` near 1982, `finish_retrieval_turn` near 2025 | Revision ownership, operation identity, persisted authorization and replay semantics. |
| Open work | Same file: `open_unresolved_questions` near 2164, `next_unfinished_work` near 2188, add/resolve helpers near 2222/2257, `record_read_outcome` near 2441 | Already implemented. Selection is not execution. Verify attempts advance, resolved work stays resolved and actions are actually dispatched. |
| Typed proposals | `backend/core/action_program.py`: `compute_authorizations` near 681, `execute_program` near 731 | Executor explicitly performs no I/O. Source/workbook reads are marked proposed. Never count these receipts as completed lookups. |
| Item and reference state | `backend/core/dialogue_state.py`: `record_item_outcomes`; `backend/core/target_set_resolution.py`: `resolve_target_set` | Match status is not freshness, applicability or completion. Preserve the complete requested item set through follow-ups. |
| Teaching | `backend/core/student_learning_service.py`: `get_agent_lessons` near 145, `journal_standing_lesson`, `format_lessons_block` | Existing own/workspace lesson behavior, scope and relevance. Do not silently change lesson sharing. Trace which lessons reach the actual decision. |
| Canvas decisions and effects | `backend/core/chat_canvas_editor.py`: `plan_contract_violation` near 123, `plan_canvas_edit` near 2190, `apply_canvas_edit` near 3070 | Authorization, preservation, audit identity, conflict handling and read-back. A model's acceptance is not proof of a write. |
| UI surfaces | `frontend-nextjs/hooks/chat/useChatInterface.ts`, `components/canvas/TrainingPanel.tsx`, `components/canvas/CanvasDataSection.tsx` | Reuse existing teaching/chat/canvas surfaces. Add job visibility only after the backend state is trustworthy. |

The recent provider-pool repair belongs in `backend/core/llm/byok_handler.py`. Preserve failed-pin exclusion, authorization, capability, cooldown, attempted-route and known-unserved controls. Do not start a model comparison or change provider pins as a substitute for diagnosing missing obligations.

## Milestone A Make the trained investigation complete

### Trace the first actual divergence

Run one authorized research request with a real agent, fresh session and disposable canvas. Record the chosen lane, teaching identifiers, requested items, advertised tool names, plan structure, parsing result, invocation identities and observed outcomes. Redact secrets and source bodies; retain enough identifiers to bind the evidence.

If required research receives no executable plan, determine whether the tool was unavailable, context omitted, response rejected, budget exhausted, or the model deliberately returned no action. A successful provider HTTP response is not a successful plan. A declined or empty plan is not source absence or a download failure.

### Connect execution without changing callers accidentally

Associate each required source action with an operation and actual invocation. Reuse existing lifecycle fields and metadata where suitable; do not create a second status taxonomy unnecessarily. If adding structured return data to the text-returning executor, audit every caller and keep an explicit compatibility adapter rather than silently changing its return type.

Record individual attempts and the final result separately. A failed planner/provider attempt followed by successful fallback must end as a successful read with recorded recovered attempts, not `not_dispatched`. Distinguish successful empty search, unreadable source, planning failure, actual access denial, and budget deferral. A readable saved workbook may coexist with a failed refresh.

The no-tool branch also needs a record; opening an operation only immediately before execution cannot explain why execution never began. Conversely, do not mark all requested items checked merely because one aggregate tool returned text. Bind observations to source and item where evidence supports that binding.

### Make remaining work drive actions

Use `next_unfinished_work` and the accepted business procedure to select the next eligible action. Validate tool availability, authorization, input identity and dependencies before executing. Reassess after results arrive. Permit one bounded plan repair when required authorized work remains but no executable action is proposed; persist exhaustion honestly.

Inspect and generalize the recently added mailbox-to-workbook cross-check instead of adding a parallel shortcut. Source order must come from the task and teaching. Test workbook-first, mailbox-first, no mailbox match and a non-mail source. Do not gate continuation on purchasing vocabulary.

Enforce total time/action/cost budgets, per-obligation attempt limits and repeated-no-progress detection. A timeout must persist unfinished work. Resume via the authorized job/canvas identity and applicable revision, not the latest user conversation. A future explicit `continue` must pick up durable work; ordinary progress within the current budget should not need repeated user nudges.

### Acceptance for milestone A

Use: “Check the other machinery and verify whether pricing needs updating, following your training. Don't change the draft yet.” Use the real trained agent and the original eight-item context on a disposable fork. No operator reformulation or hand-added missing source context after the run begins.

Require all eight dispositions based on actual evidence, both taught source obligations performed or concretely blocked, and no unnecessary read-permission question. Inspect the durable state and independently verify source references and draft audit/content. A model-produced eight-row table is not enough. If a bounded run pauses, verify one continuation selects and updates an existing unresolved entry without duplicating completed work.

Milestone A is not complete if the task ledger never engages, the operator steers each source lookup, or the reply invents a failure cause. A concrete external access failure can establish correct blocked behavior, but cannot be reported as successful current-price verification.

## Milestone B Business decisions and outputs

Start after milestone A passes. The goal includes useful pricing, alternative selection and drafting, not only recording unfinished research.

### Turn teaching into scoped procedures

Represent or derive goal, required deliverables, source requirements, prerequisites, calculation rules, hard constraints, preferences, permissions and escalation conditions through existing teaching/configuration mechanisms. Preserve original lesson text and its provenance. Store the applied policy version with the job. A material policy interpretation, such as gross margin versus markup, must be reviewable in plain language.

Do not invent a second training store. Determine whether existing lesson metadata supports this before adding schema. Business facts, procedural instructions and mutation authorization are different things. Conflicting or missing policies remain explicit questions. Undo or policy replacement affects future decisions predictably and does not silently revise already-approved results.

### Pricing

Search existing tool registries and calculation implementations before adding a calculator. Use deterministic decimal arithmetic with explicit currency, units, rounding, effective date and policy inputs. The model selects an applicable authorized policy; it must not supply missing business parameters from habit.

Test, using synthetic policy data: cost 100 with 20% markup gives 120; 20% gross margin gives 125. Include currency conversion, fees, rounding boundaries, invalid margins and missing inputs. These are test examples, not Brennan's policy. Preserve manual approved prices unless an authorized instruction changes them. An accurately computed price based on stale cost remains freshness-limited.

### Alternatives

Obtain actual catalog/inventory evidence. Filter mandatory specifications first, then rank eligible candidates by taught preferences such as delivery, stock and price. Missing mandatory specifications mean unknown suitability, not a match. Return a concise comparison and evidence-based recommendation. A weighted preference score cannot override a hard requirement.

### Drafting

Use the selected evidence-backed options and permitted prices to prepare the email. Verify recipient, subject, CC rule, currency, quoted items, delivery conditions and preservation constraints. Apply authorized edits through the existing verified canvas path and inspect the result after reload. Drafting authority does not imply sending authority. This assignment sends no customer email.

A read-only request that prompts an attempted edit should be recorded as a planning error even when the scope gate prevents harm. Separately test an explicitly authorized draft request so a protective refusal does not masquerade as functional editing.

## Milestone C Prove reuse and expose progress

Use one materially different business procedure through the same mechanism, for example a service estimate with labor rates and appointment constraints. Do not merely replace machine names in the quotation fixture. Require different constraints, calculations and deliverables without business-specific routing code.

Expose the existing job state in the UI: goal, completed findings, current action, remaining decisions and output. Explain recommendations with evidence and policy references, not purported private reasoning. Keep the interface small; do not build a new dashboard before the underlying job works.

Broader autonomous actions are a separate rollout decision. Successful research/drafting does not enable sending, discounts outside policy, or unrelated mutations.

## Evidence and tests

Start with existing neighboring suites: `backend/tests/test_job_work_ledger.py`, `test_action_program.py`, `test_target_set_resolution.py`, `test_pending_file_task_resume.py`, `test_fallback_chain_workflow.py`, `test_chat_teaching.py`, `test_canvas_repair_scope.py`, and `test_write_zero_effect_claims.py`. Read current fixtures and test configuration before choosing invocation commands. New job-work tests are already being edited by another writer.

Pin meaningful controls: proposed-but-never-invoked; first attempt fails then fallback succeeds; true empty search versus read error; expired saved evidence still readable; no tool plan with outstanding obligations; policy conflict; attempt exhaustion; same job after restart; wrong canvas must not resume; resolved question must not recur; legitimate owner approval required; unauthorized edit blocked; authorized edit verified.

Use integration tests that retain real persistence and observe tool/delivery boundaries, then a public UI job with the actual configured planner. Do not mock away the function whose outcome is being certified. Baseline known failures with controlled environment and exact source, without moving others' changes. The previously reported nine failures are historical reports, not an exemption for current failures.

For each gate save: source/configuration identity, sanitized request, agent/job/canvas identifiers, applied lessons, operation/attempt records, source references, expected versus observed behavior, assertion results and draft before/after audit. Evidence must survive beyond `/tmp` and any disposable world's cleanup. Capture incomplete and failed runs too; never combine different candidates into one certification.

## Original quotation facts to preserve

The original canvas is `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb`; leave it untouched. Existing fork `b5676728-5122-4e0d-96f5-292871d4b690` is user-visible work, not disposable test debris. Obtain current state through the supported API/UI; some canvas reads are audit-backed, so a stale base row alone does not establish the visible content.

The eight items are No. 381, U-22, TK Manual Flanger, No. 622, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16. No. 381's $2,902 is an owner-confirmed manual vendor-quote price, not an invalid workbook outlier. Historical workbook cell locations and vendor prices are investigation leads, not automatically current evidence. Resolve the No. 622 identity and conditional TK-Multi offers from current evidence and owner decisions where required. Never infer that every other item is settled merely because one decision is obvious.

Keep separate columns for draft price, saved-workbook value/date/cell, vendor offer/date/conditions, freshness, discrepancy and required decision. Preserve conflicting offers rather than synthesizing an unsupported value.

## Operational boundaries and stop conditions

No live-DB scripts, world deletion, WAL removal, portable-drive move, broad process kills, shared-checkout stash/reset, credential copying, or new full-dev-database snapshots. Use the established small fixture and API seeding. Inspect storage guards and available space before launching. Keep existing previews intact. Coordinate a live backend restart with active work; the backend does not reload automatically. Frozen exports require rebuild and serving-hash verification after changes.

Stop and report a concrete blocker only when it actually prevents progress: missing required access, unavailable source, business ambiguity, conflicting authorized policy, or exhausted bounded execution. A source named only in narration is not evidence of an attempted lookup. Do not stop after writing helpers while the relevant live lane bypasses them.

Do not expand into M3 recovery redesign, provider benchmarking, full C00–C26 acceptance, an onboarding redesign, reinforcement learning, a custom language, or MCTS. Record unrelated defects separately. If a common dependency truly blocks this job, reproduce and fix the narrow dependency with its neighbors tested.

## Design rationale and completion report

[The original AlphaGo research](https://research.google/pubs/mastering-the-game-of-go-with-deep-neural-networks-and-tree-search/) establishes the combination of learned proposals and explicit search. [The Gomoku implementation](https://github.com/junxiaosong/AlphaZero_Gomoku/blob/master/mcts_alphaZero.py) depends on a clonable game state, simulated actions and terminal rules. Atom cannot simulate unknown vendor replies or inventory facts. Adopt explicit state and evaluated choices; defer tree search until a measured comparison shows a benefit over the bounded execution loop. Simulated options must never enter the evidence ledger as observations.

Final report: identify the exact source/configuration, which milestones passed, real user-boundary evidence, actual remaining decisions and external blockers, affected tests, known failures, and preserved user data. Distinguish implementation from exercised behavior. Do not claim statistical reliability from a handful of successful demonstrations.

The finish line is a trained employee completing the appropriate actions and producing a verified business output, with necessary decisions left to the owner. It is not an increasing count of helpers, passing mocked tests, or honest explanations of work that never ran.
