# Deliver the trainable AI employee workflow

This is an implementation work order for the next agent. The owner wants the app to deliver its advertised value: an employee that can be taught, use the teaching during real work, and finish a useful task. Fix that product experience. Do not substitute another architecture proposal, routing score, or infrastructure summary for a working result.

The first release target is a trained sales employee completing the existing workbook and email quote workflow. Implement the mechanisms generally, using the existing integration and learning services. This is a bounded proof of employee value, not certification of every advertised role or integration.

## Immediate blocker Excel work and taught email drafting

The owner clarified the current blockage: working with Excel files and writing emails based on the employee's teaching. These are the two deliverables, completed together. Do not expand this assignment into employee onboarding, marketplace, autonomy graduation, scheduling, or unrelated integrations.

First inspect the existing Sales Agent's actual lessons and the current workbook/email conversation through the authorized app surfaces. Identify which taught instructions govern source selection, price interpretation, missing information, and email composition. Do not replace the owner's real teaching with an easier synthetic lesson and call the original problem solved. Use synthetic controls only after preserving the actual failure.

Trace two distinct uses of teaching:

1. **Excel work:** does the taught instruction reach the point that chooses files, sheets, item identities, columns, formulas and fallback sources? Prove the chosen evidence follows it. A lesson included only in final narration cannot repair a search that never gathered the required rows.
2. **Email drafting:** do the same employee's applicable instructions reach the draft planner with the verified workbook/vendor evidence? Prove the resulting draft follows the taught content, price-source, tone, structure and preservation rules. Merely displaying a lesson card or producing an email-shaped chat reply does not establish this.

Completion is a reviewable email draft in the actual canvas, based on the requested Excel work and applicable teaching, with unresolved facts explicitly identified. Include initial draft creation if that is the owner's failing path, not only edits to a prebuilt draft. Verify both creation and one subsequent instructed revision through the UI and durable read-back. Do not send the email.

The first progress report should say which specific taught instruction failed to influence which source read or draft change, with its observed boundary. The final report should show the finished draft and evidence that the user no longer has to repeat that teaching on the next relevant task.

## Current review and limits

Reviewed on October 3, 2026. HEAD was `7bcb3ae6ee2ed222cdf3394e1309edbc132454c2`. This review inspected code, recent commits, UI wording, and the recent coordination history. It did not run the app, verify loaded modules, or independently rerun other agents' reported tests. Treat the following as source findings, not a new live certification.

There are seven modified tracked files containing another writer's formula propagation work: `answer_presentation.py`, `sheet_dataset_service.py`, `workbook_read_artifact.py`, `chat_orchestrator.py`, `universal_integration_service.py`, and two test files. They are not part of the reviewed commit. Preview farm directories are also untracked. Preserve them; do not stage the entire checkout or rebuild another writer's world.

Recent commits materially change the starting point:

| Commit | What is now present | Consequence for this assignment |
| --- | --- | --- |
| `7bcb3ae6e` | Recovery scan hardening and preservation of tables through absence guards | Reproduce current behavior before reopening old recovery diagnoses. Preserve tables without treating every table assertion as verified. |
| `54492990a` | A broad owner-authorized snapshot including migration and frontend work | HEAD alone does not establish serving identity or which features work together. |
| `410e4d64d` | Connection-health reporting for Zoho | Check actual source access, not merely a connected badge. |
| `50348cebc` | Dialogue state, target-set handling, read/edit chain changes, and many regression tests | The earlier diagnosis that these mechanisms do not exist is obsolete. Trace their current consumers. |
| `c127e938e` | Training availability at decision time and per-turn fetch reset | Test teaching use rather than adding a second lesson store. |
| `7e1e1e948` | Optional read-miss handoff to narration | The current source still defaults this handoff off. Do not claim every taught fallback is active. |

The onboarding UI promises hiring and training, feedback that shapes learning, increasing autonomy, and role-scoped memory. Relevant surfaces are `EmployeeOnboardingGuide.tsx`, `AgentLaunchGuide.tsx`, canvas `TrainingPanel.tsx`, `TeachingNotice.tsx`, and `ChatFeedbackControls.tsx`. Those promises require behavioral evidence, not just a successful save or a maturity badge.

## What completion means for the user

The owner should be able to attach a Sales Agent, teach it how to handle a missing or uncertain quote price, and assign work without restating that lesson on every turn. The employee should identify the requested machines, consult the appropriate connected sources, distinguish confirmed facts from uncertainties, produce a useful comparison, and update an authorized draft without damaging unrelated content.

An honest refusal is preferable to a false success, but it is not completion of a supported, authorized task. A system that reliably says why it could not work has not yet delivered the marketed employee value.

Do not solve the gap by weakening the marketing wording alone. Fix the supported workflow; keep remaining exclusions accurate. Conversely, do not enable all flags or all autonomous actions merely to make the app appear complete.

## Run one complete job first

Use the normal authenticated browser, an API-created disposable email canvas, the existing sales employee, and a small isolated candidate. Reuse the existing acceptance infrastructure. Do not create a new framework, a new language, a fleet of worlds, or another large acceptance matrix.

Preserve the original user canvas and current production data. Recover the exact original eight-item list from the existing fixture/package:

1. No. 381
2. U-22
3. No. 622
4. TK Manual Flanger
5. SLE24-16
6. TK 1624
7. TK Multi Wheel Gang Slitter
8. GSL48-16

The original package is under `acceptance/original_workbook_email/`; the incident fixture is under `acceptance/fixtures/`. Use the current user-confirmed state, not an older copied proposal, when constructing expected outcomes.

Teach a scoped rule through the actual UI, such as: when a requested selling price cannot be established from the designated workbook, inspect the relevant vendor quote and attachments; preserve a confirmed manual quote price; identify unresolved model or price-basis differences before changing the draft. The teaching must not grant permission to send email or overwrite prices.

Then execute this conversation as a job:

1. Find model 381 on the Tennsmith sheet.
2. Ask for the other machines in the attached eight-item quote and whether current evidence justifies any price changes.
3. Ask it to consult the relevant vendor email and attachment for unresolved items, using the taught procedure without repeating its wording.
4. Request a concise comparison: current draft price, proposed price, source and date, price basis/currency, and decision or unresolved issue for each item.
5. Correct one item binding or price-source choice and ask for the revised comparison.
6. Authorize updating only confirmed changes in the draft. Reload the actual canvas and inspect its durable content.
7. Start a new session with the same employee and a different disposable quote. Confirm the teaching still applies, without carrying the previous quote's item or row identities into it.

Keep the provider configuration stable and disclosed for the first pass. No controlled planner substitute for the real-planner job. A shim may isolate a failing executor afterward, but does not complete this workflow.

If an ambiguity is genuinely material, one focused clarification is correct. If the attached draft already identifies the item set, asking the user to list it again is unnecessary work shifted back to the user.

## Fix the first failing boundary

Execute the baseline once and retain its request, response, action record and durable outcome. Find the earliest mismatch between the user's requested work and what the system executed. Fix that mismatch and rerun the failed step plus its immediate neighbors. Do not spend a session polishing later explanations while the necessary source read or edit never ran.

### Resolve the job before selecting tools

Inspect `core/target_set_resolution.py`, `core/dialogue_state.py`, `core/turn_decision.py`, `core/pending_file_task.py`, `core/action_program.py`, and the orchestrator callers.

The target-set module now explicitly addresses contrastive references such as “other” and “remaining.” Prove it receives the current canvas item set and previously served items through the real request path. Do not add another detector for the exact incident sentence.

The accepted task must distinguish:

- Which entities to work on, including an unresolved state rather than an empty list silently filled from history.
- Which sources and scope constraints apply.
- Whether the user wants a search, a freshness check, a comparison, a presentation change, or an authorized artifact change.
- Which facts or choices were confirmed by the user, scoped to which task and source revision.

“The other machinery” must not become another read of 381. “Latest pricing” must not become only a refresh attempt followed by the unchanged old answer. “Use the email too” must create an executed source step or a visible blocked step.

`action_program.execute_program()` currently records `SourceReadOp` as a validated proposal and delegates execution to the read/integration lanes. That is a legitimate migration seam, but `proposed` is not `executed`. Bind actual tool outcomes to the requested action IDs and use those outcomes for the final completion check. Reuse the existing executor; do not build a second parallel dispatcher merely to rename this status.

### Make teaching change the work

Trace the actual chain: employee identity in browser request → lesson save → durable lesson/version → relevant lesson retrieval → decision/planner context → resulting tool action → verified outcome.

Reuse `core/student_learning_service.py`, `core/chat_teaching.py`, the context assembly, and `_agent_lessons` in `chat_orchestrator.py`. Current lesson selection uses relevance scoring and a limit, and can include workspace peers. Those are facts to test, not reasons to replace the storage layer.

Required behavior:

- Show which employee received the rule and allow correction or removal.
- Preserve the rule across session and process restart.
- Retrieve it on a paraphrased relevant task, not only when the request repeats its vocabulary.
- Apply it before the decision it should influence. Injecting a fallback lesson after a deterministic early return is too late.
- Resolve conflicts with newer explicit task instructions and lesson scope. A lesson never manufactures a price, proves a source is current, or grants mutation permission.
- Undo or edit the lesson, then show the next task uses the changed policy.
- Exercise unrelated employee/task controls. Workspace lesson sharing may be intentional, but its scope must match the product promise; do not assume all sharing is either correct or forbidden.

Use a small before/after control: the same novel missing-price task with the lesson absent, then present. Inspect which sources/actions change. A “Learned” badge, a lesson ID in metadata, or a model saying it remembers is insufficient. This need not involve model weight training; durable, correctly applied procedural memory satisfies the practical promise.

The miss-to-narration branch near `ATOM_MISS_HANDOFF_NARRATION` remains default-off in current source. Check effective serving configuration. If it is the first demonstrated obstacle to the taught workflow, complete its wiring and outcome checks, then activate narrowly. Do not simply flip it and count narration as successful fallback: the relevant source must actually be read.

### Produce a useful evidence comparison

Use existing `UniversalIntegrationService`, the tool catalog, workbook artifacts, attachment evidence and connected-service authorization. Do not hardcode a vendor, person's name, sheet or integration as business policy.

A workbook price, vendor quote, user-supplied manual price, computed price, and current draft value are different evidence classes. Preserve their provenance when they enter the same comparison. The canvas proves what is currently quoted; its numbers do not by themselves prove current market or vendor prices.

No. 381's historical 2,902 vendor-quote price was explicitly confirmed by the owner as manually calculated. A workbook match at 3,254 does not automatically invalidate or replace it. Respect subsequent attributable user choices. Do not infer currency from the sheet name or compare COST against selling PRICE as if they were equivalent. Expose relevant formula inputs when explaining a derived value; formula text alone does not prove recalculation, dependency completeness or freshness.

For each requested item, finish with one of: verified unchanged, supported change proposed, conflicting evidence requiring a choice, or unable to verify with a specific cause. If source access fails, retain usable saved evidence and complete unaffected items. State which comparisons remain blocked and provide the appropriate connection-repair action. Do not report “all checked” when only one source or one item was checked.

The current formula propagation work is owned elsewhere. Coordinate its inclusion and test the final candidate rather than duplicating it.

### Apply the decision to the actual draft

Use `core/chat_canvas_editor.py`, the existing server-side canvas store and continuation lifecycle. The browser must send the intended canvas ID and revision. Verify the patch affects only authorized fields and respects the latest user-approved choices.

Read back the actual canvas after reload. Count the request's total audit delta, not just rows with the expected operation ID. A successful response or a transcript containing the requested new price does not prove a mutation.

For the job, preserve recipient, subject, greeting, footer, unrelated rows and manual prices unless explicitly authorized to change them. Do not send the email. A second request with the same transport identity must not create a second edit. If the job backgrounds, show a truthful completion bound to that job and recover it after reload.

Existing recovery, fencing and ownership code already exists. Reopen it only if the current job exposes a failure; do not restart the historical F09/F11 investigation from stale notes.

### Keep the result usable

The normal answer should be the completed comparison or updated draft plus a short unresolved-items section. Put raw coordinates, model routing and detailed traces behind evidence/details, while retaining enough source information to assess the result.

Recent absence-guard fixes exempt tables from prose claim extraction to avoid deleting whole results. Preserve that data-loss fix, but test an unsupported claim in a table as well as prose. Exemption from one text guard is not verification; prefer the existing structured per-item verdicts. A rendering guard must not erase valid rows because one neighboring row is unknown.

A failed action should leave a usable partial deliverable and an explicit next step. A successful job should not require reading logs, resetting a session, restating the item list, or learning the internal routing vocabulary.

## Required proof and completion bar

Use one compact result file with links to retained evidence. Each row records the exact candidate/configuration, requested outcome, actual actions and final state. Do not combine passes across exports into a release claim.

| Check | Required evidence |
| --- | --- |
| Teaching | UI save and destination; lesson/version retrieved and used on a new paraphrased task; update/undo changes later behavior |
| Scope | Attached eight-item list resolved; “other” excludes the already handled item; unresolved alternatives clarify instead of silently inheriting |
| Research | Each required source has an actual tool result or a named access failure; all requested items have individual outcomes |
| Comparison | Baseline and proposed values have identities, bases, dates and provenance; no unsupported conversions or automatic manual-price replacement |
| Editing | Real browser and real planner; intended canvas changed once; unrelated fields preserved; durable reload matches |
| Continuity | New session and a controlled restart preserve relevant teaching and task outcomes without importing stale item bindings |
| Failure handling | Unavailable source and legitimate ambiguity produce actionable partial work; no invented current price or false success |
| Generality | One analogous held-out task with different item names and document structure works without new production vocabulary rules |

Run the primary job on three fresh disposable drafts, including paraphrased instructions, after fixes. This is a small reliability check, not a statistical guarantee. Record completion latency and the number of unnecessary user interventions. Count safe-but-incomplete separately from completed work. Report cost if the existing telemetry provides it; do not invent it.

Use independent source and durable-state checks for correctness. Keep focused regression tests for the demonstrated defects, then run the affected existing suites once on the final source. A large unit-test total is supporting evidence, not the product acceptance criterion.

The milestone closes when the taught employee repeatedly completes this supported job through the normal UI without operator rescue, with only justified clarifications. A source outage can justify a truthful partial result in its negative control; it cannot replace the successful-source completion case.

## Execution discipline and handoff

Before editing, read AGENTS.md, CLAUDE.md and the latest bounded coordination tail. Record file ownership. One writer owns the orchestrator during this assignment. Do not deploy or restart another writer's stack. Use the normal backup/restart procedure for an authorized live rollout; first verify in isolation.

Use one small API-seeded world with necessary workbook/attachment fixtures. Check storage preflight and retain evidence outside disposable run directories. No ad hoc live DB writes, deletion of old worlds, WAL removal, or broad cleanup. Set scratch DB configuration before app imports and verify the server and probe use the same DB. `TESTING=1` does not isolate HTTP calls to a live server.

At each meaningful fix, save its evidence and continue to the next unfulfilled outcome. Do not stop for permission to do already-authorized routine fixes. Do not publish another “everything implemented, verification next session” completion statement.

Commit only owned changes. Final handoff must include the usable URL and employee, the exact supported job, concise reproduction instructions, serving/export identity and effective configuration, final workflow results, relevant tests, rollback, and remaining limitations. Keep credentials out of tracked documents. Deployment is a separate factual claim: committed, pushed, running and verified are distinct states.

## Research used for this guidance

These sources inform the recommendations; none proves Atom's current behavior.

- [Anthropic on agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) distinguishes a transcript from the final environment outcome and recommends multiple trials and outcome-based evaluation. Apply that distinction to saved lessons, actual source reads and durable canvas edits. Do not build a large new evaluation platform for this bounded job.
- [TypeChat examples](https://microsoft.github.io/TypeChat/docs/examples/) demonstrate validated JSON dataflow actions. Atom already has an action representation; use it to preserve scope and connect actual outcomes, rather than invent another language or treating a proposal as execution.
- [LangChain memory concepts](https://docs.langchain.com/oss/python/concepts/memory) distinguish conversation state from persistent memory and discuss procedural knowledge. Keep the current quote's entities separate from the employee's enduring operating rules. This is a design distinction, not a recommendation to migrate frameworks.

## Immediate instruction to the implementing agent

Start with the browser job above on the current candidate. Show the first failing outcome, fix its existing producer or consumer, and continue until the taught employee delivers the comparison and authorized draft update. The deliverable is the repaired app and its measured workflow, not this document and not another plan.
