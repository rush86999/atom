# Atom: autonomous completion and release guide

Prepared 2026-10-23, America/Toronto. Repository: `/Users/rushiparikh/projects/atom`.

2026-10-24 scope addition: include the bounded BYOK routing/settings UX slice in [BYOK_RELEASE_WORK_ORDER_2026-10-24.md](BYOK_RELEASE_WORK_ORDER_2026-10-24.md). Attempt-9 functional success with unexpected configured-provider fallback established that preference is not containment. Complete effective user policy, actual dispatch enforcement, and truthful status/fallback UX before claiming the selected-provider release profile. Earlier starting identities below remain historical observations and must be refreshed.

## 1. Mission and finish line

You are the completion owner. Finish a usable, truthful local Atom pilot on one integrated build and one declared configuration. Carry implementation, local verification, independent review, isolated acceptance, integration, release preparation, and documentation forward without asking the user to choose routine implementation details. Do not stop after writing a brief, fixing one helper, or publishing another branch-only pass.

The user should be able to sign in, configure a supported provider, upload records, get a concise sourced answer, edit a draft once, repeat the instruction without another write, compare the draft with its source, ask a follow-up, and reload/restart without losing or contradicting the result. The answer, saved status, history, evidence, and artifact must agree. Users should not need to understand model families, execution IDs, receipts, or feature flags to complete that job.

The shortest path is:

1. Close the presently reproduced answer-boundary and canvas-evidence defects.
2. Verify those changes through the real final-return/persistence path using controlled external seams.
3. Freeze one integrated runtime and configuration; conduct one focused independent review.
4. Run the composed public-API/restart workflow once on that frozen successor.
5. Verify clean-export/startup and the actual browser loop on the same shipping content.
6. Prepare a reversible, narrowly scoped deployment, obtain the one outstanding live-cutover decision if the explicit hold still applies, deploy, and verify the served build.
7. Publish one support statement, exact release identity, run instructions, and recovery instructions.

This is a limited pilot release, not proof that every advertised integration, background agent, automation, or installation platform works. Do not let those separate programs block this release, and do not imply they have passed.

## 2. Authority, autonomy, and when to involve the user

Treat this as standing direction for routine, reversible work needed to complete the release candidate. Proceed with repository inspection, scoped fixes, meaningful tests, local candidate commits, isolated environments, replay harnesses, evidence archives, release preparation, and focused scratch acceptance within already authorized access and spending. Reuse existing credentials only within their existing authorization; keep values out of artifacts.

Do not ask: “Should I draft the brief?”, “May I run the focused tests?”, “Would you like the review next?”, or “Should I commit my completed slice?” Resolve ordinary choices from code, measured evidence, and this guide. A passed checkpoint advances automatically to the next checkpoint.

Ask only when progress requires a real human decision that cannot be resolved from standing authorization:

- A new paid service, funding, increased spending, new credential/access, or changed privacy boundary.
- A destructive or incompatible data migration, deletion of user material, or external communication/publication beyond the authorized release scope.
- A genuinely conflicting active owner; silence does not transfer ownership.
- The live pilot cutover while the prior explicit deployment hold remains in force. This guide does not silently revoke that hold. Complete the release and rollback package first, then ask one concrete final approval covering that exact build/configuration and smoke artifacts. If the user has since explicitly authorized cutover, proceed within it without asking again.
- Automatic approval review or an explicit tool policy prevents the action. Report the actual rejected action and reason, not a hypothetical warning.

Provider instability is not a reason to return an open-ended model menu to the user. Diagnose it, compare only authorized options with the same workload, select the measured suitable configuration, and predeclare it. Stop for funding/access if no authorized viable route exists; do not silently switch endpoints or bypass local-only requirements.

If a question is needed, ask it asynchronously while completing independent preparation. Never interpret elapsed time as approval. Do not create new tasks, send messages to other user-owned chats, or schedule monitoring without authorization.

## 3. Reconcile reality before changing anything

Read `AGENTS.md`, `CLAUDE.md`, applicable nested instructions, and `notes/AGENT_COORDINATION.md`. Use explicit working directories. Do not assume the default shell, interpreter, branch, server, or browser belongs to your candidate.

Starting observations from this audit; revalidate them because they are not permanent configuration:

| Item | Observed state | Consequence |
|---|---|---|
| Shared main checkout | `1817cd7393ed9fa8f8521757a584a9906a32db8a`, dirty with unrelated work | Do not stash, reset, clean, or deploy it as a shortcut. |
| Integrated owner branch | `fix/l3-required-read-timeout` | Contains integrated L1/L2/L3 runtime and later repairs; do not reconstruct from isolated parents unnecessarily. |
| Integrated worktree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/l3-required-read-timeout` | Use this only after ownership and current identity are confirmed. |
| Latest observed worktree HEAD | `091830c008a3a56c5957a6af8f626a00bcb6ff09` | Preflight/evidence commit, not a served pass. |
| Pending product pin | `824a94c5ba8b255bb087e49b9f0abd6cf2c85c83` | Contains the answer-boundary defects reproduced below; supersede through new commits. |
| Pending harness | `a4f805cebe49b9a6f990ba18e083feb310d55f34`, gate lineage `f2f8329971129bc14e9f107aa234b98db7f18379` | Preserve per-run identities and partial-aware restart tests. Refresh runtime pin after fixes. |
| Last served campaign | Attempt 4, product `b0bee5dbfd608103bd8875bbc35066c28959ae1e`, 50/59 | Non-passing. Do not rescore it into a product pass after changing code. |
| Pilot, as last reported | Backend `:8001`, frontend `:3000`, runtime `8c593e57031e` | Verify PID/start/cwd/source and store ownership; do not restart during scratch work. |

Inventory the current branch graph, source hashes, working-tree ownership, listener ownership, relevant active owner activity, actual store paths, and test interpreter. Record a compact release manifest. Never print vault contents or broad environment dumps.

The main support statement still contains superseded route-impossibility language. Later evidence proved a required-read control-flow gap instead. Treat docs as claims to reconcile, not immutable truth. The old warning that `subject_admission.py` was untracked is also stale: it and its test are tracked on the inspected main. Verify current tracked/exported content rather than carrying old blocker lists forward.

## 4. Ownership and working method

Use one runtime implementation owner, one independent verifier, and one campaign owner. The implementation owner may launch acceptance after independent review; there must be only one campaign at a time. Delegate read-only audits, test review, or disjoint files when useful. Do not create two editors of the same orchestration functions.

Update the local coordination note when claiming/releasing shared files, freezing a candidate, and finishing a checkpoint. A candidate branch is not permission to overwrite another owner's worktree. Reuse the appropriate integrated worktree or create an isolated `codex/` worktree after checking existing attachments and ownership. Do not prune or archive other owners' worktrees.

Use short commits around coherent behavior changes. Keep source, tests, and essential rationale together. Put large raw evidence in its evidence commit. Do not rewrite thousands of old log lines every time a test is rerun. Stage explicit owned paths only; inspect the staged diff. Preserve failed attempts and existing tags.

Maintain one small status file or coordination entry with: current candidate, current checkpoint, completed proof, first remaining failure, next executable action, and actual blocker if any. Do not make the user assemble the state from a dozen reports.

## 5. Product scope: what must work and what can remain open

### Required pilot capabilities

- Sign-in/onboarding completion persists across reload and sign-out/sign-in.
- A provider can be registered/activated through the product; actual routes are recorded.
- An uploaded document is read through the authorized execution path when the accepted request requires a fresh read.
- Answers address the requested subject, exclude unrelated distractor facts, name the source, and do not expose internal carrier envelopes.
- An explicit draft edit applies once, preserves protected content, has attributable audit evidence, and matches authoritative readback.
- An identical re-ask produces the existing verified no-op result with no additional mutation.
- A comparison reports supported matches/differences and names unassessed requested scope. It never presents partial evidence as universal consistency.
- A narrow continuation binds to the correct durable antecedent, covers its own requested field, and preserves any prior task-level obligation separately.
- Envelope, task outcome, criteria, history, and artifact agree across fresh reads and a real process restart.
- A provider/source failure yields an honest actionable response; a subsequent ordinary request remains usable. No invisible retry loop or silently resumed mutation.

### Visible limitations allowed for this pilot

The broader whole-document comparison may remain partial if the original gates permit that disclosed result and every missing obligation remains named. General natural-language value resume remains constrained to the accepted R3 syntax. J7/J8/J9, broad background recovery, automation, cross-platform pristine installation, all connector combinations, and local-only enforcement must not inherit a pass from this job. Known R4 coverage/outcome inconsistency remains a separate item unless changed by this candidate.

Do not silently weaken a predeclared gate to fit these limits. If the original job cannot satisfy its existing supported contract, repair it or record an explicit scope decision. A pilot claim and a whole-app claim are different deliverables.

## 6. Immediate repair batch: finish it before another provider campaign

### A. Remove lexical factual authority from the answer boundary

At product `824a94c5b`, `backend/core/answer_boundary.py::render_supported_fact` scores sentences by word overlap, and `present_answer` uses uppercase code-anchor presence as a correctness check. These are unsuitable certification relations.

Permanent counterexample:

```text
Request: search my uploaded documents for the launch code for project Zephyr-9 and tell me the code
Evidence:
  Zephyr-9: QUARTZ-77.
  The launch code for project Halcyon-2 is BASALT-13.
Empty answer after carrier removal.
```

The current fallback returns Halcyon's BASALT-13 sentence with a source citation. A second case containing both QUARTZ-77 and BASALT-13 in ordinary answer prose is preserved by `present_answer` when the expected anchors are present.

Required repair:

- Keep the useful removal of the exact internal tool carrier where its origin is known. Preserve full evidence internally.
- Remove sentence-overlap ranking and code-anchor containment as factual authority. Do not add a larger stopword list, code regex, decoy blacklist, or special filename.
- For the captured case, the valid supported suffix can survive removal of the exact carrier cheaply. Do not generate a second answer needlessly.
- Any synthetic fallback must consume an existing, uniquely supported subject/field/value/source association. Inspect `memory_context_assembler.py` and `workbook_read_artifact.py`; do not assume they support arbitrary code fields without proof.
- If no such association exists and no usable answer remains, return a specific limitation under the existing honest-result mechanism. Never cite a highest-scoring unrelated sentence as an answer.
- Ordinary quotations and explicit requests for multiple facts must continue to work. An arbitrary source sentence is not an internal carrier merely because it resembles one.
- Apply the actual acceptance output contract: the requested answer must not include unrelated decoy facts. Do not change the gate to allow the leak.

Trace raw generation -> each transformation -> final return -> persisted message -> history. A source excerpt in final text does not alone prove the model or finalizer introduced it; capture the boundary that did.

### B. Fix empty/stale canvas evidence selection

`chat_tool_planner.py::serialize_canvas_evidence` currently returns the first successfully serialized context even when the result is empty. The local `{"content": ""}` must not mask a populated route-resolved canvas.

Serialize, then skip empty text. Match the expected canvas identity and available revision before accepting populated contexts. When both populated contexts disagree, use authoritative request-bound resolution or fail conservatively; never merge unrelated figures into a global support pool. A supplied current canvas value supports a claim about the draft, not the same value attributed to a source document.

Retain the supported-draft / unsupported-source / wrong-artifact / unavailable-evidence contrasts in `figure_issues`. Inspect callers and parallel streaming/non-streaming guard paths. Do not alter the shared behavior for every caller without the neighborhood audit.

### C. Strengthen successor evidence at the real boundary

`test_attempt4_repairs.py` currently includes a wiring test based on source-string presence and zero-write assertions over historical attempt JSON. Those are useful static/history checks, not proof that the changed successor path works.

Add at least one test through real `process_chat_message` and `_get_qwen_response`, real finalization, scratch persistence, and fresh history. Script only external generation/read inputs as needed. Assert:

- Requested answer and source are correct; unrelated code is absent.
- No internal `LIVE TOOL RESULTS` carrier is delivered.
- Correct draft-supported figures do not invoke corrective generation.
- Source-misattributed figures are not certified.
- No extra corrective model call on the captured successful repair path.
- Actual scratch artifact/audit counts remain unchanged for reads, not merely saved JSON flags.
- Persisted and reloaded outcome/content agree, with non-null required identities.

Keep the already repaired per-run obligation capture and restart gates. Do not redesign them absent a new reproducible defect.

## 7. Architecture rules and coding patterns

### Separate the authorities

| Layer | Owns | Must not infer |
|---|---|---|
| LLM interpretation | Meaning, proposed actions, reference wording, requested fields | Permission, execution success, source truth |
| Deterministic request/policy contract | Accepted scope, authorization, supported capabilities | An invented user assignment or guessed source |
| Retrieval/execution | Attributable observations, source identity/version, operation receipt | Fulfillment merely because a call ran |
| Factual/write validation | Subject/field/value association, preconditions, preservation | Authority from substring presence anywhere |
| Delivery | Supported concise answer or explicit limitation | Whole-request completion from one correct value |
| Settlement | One request-bound outcome with open obligations | A second independently guessed success predicate |
| Durable state/recovery | IDs, receipts, tasks, revisions, delivery idempotency | New mutation permission from recovered prose |

LLMs make sense for semantic interpretation, proposing plans, selecting among meaningful alternatives, and narrative summaries. Use deterministic code for identifiers, enums, permissions, canonical field equality, arithmetic engines, revision guards, persistence, idempotency, and evidence accounting. Lexical/regex discovery may nominate candidates; it cannot certify identity, intent, or truth.

Do not replace every regex, introduce an agent framework, split the whole orchestrator, migrate storage, or rebuild routing to finish this release. Fix the first failed existing transition. Extract a small shared helper only where it removes actual duplication or contradictory authority.

### Required reads survive optional planning failure

The integrated branch's `enforce_required_read` repair must remain. Accepted `source_read/fresh_read` cannot disappear because a general planner times out. Optional planning is bounded, then required-read enforcement remains reachable. Use the existing capability registry, executor, and receipts; do not pick an arbitrary first candidate or fabricate `documents.search` evidence from context assembly.

```python
# Pattern only: use actual existing APIs and scope objects.
proposal = await bounded_optional_planning(...)
plan = enforce_required_read(proposal, accepted_requirement, capabilities, ...)
result = await execute_with_receipt(plan, request_scope, ...)
```

Catch the planner's own allocated timeout at its boundary; do not swallow cancellation of the entire turn. Keep time for execution, validation, and persistence.

### Validate the producer at generation, not after losing its output

Keep required `actions`, required action kinds from the authoritative vocabulary, required five-value scope, and resolved-scope/nonempty-actions validation. Explicit uncertainty remains legal. Missing actions cannot become synthetic conversation. Prompt semantics must distinguish completed-prior-turn follow-up from unfinished task resume.

Preserve structured source references separating observed evidence, requested nominations, and attached artifact. No parenthesis salvage, first-file adoption, casing authority, or dropped short identifiers. Do not reopen closed parsing work to solve a route timeout.

### Delivery and fulfillment are different facts

An executed complete search validates useful work but does not erase missing comparison criteria. Applicable missing obligations are processed even if another branch already validated delivery. A narrow date answer may be complete while the prior broader task remains open. Use distinct turn and prior-task scopes; do not mechanically import old fields or silently discard prior work.

```python
delivery_validated = usable_result_was_delivered
open_work = request_bound_unmet_obligations + still_applicable_prior_work
# Consume the existing resolver decision in persistence; do not recompute it there.
```

`not_dispatched` is not a fabricated successful receipt. Where a verified delivery exists and no hard operation failure exists, preserve the reviewed honest partial with the lookup still open. Real read/search failures retain their failure semantics.

### Deterministic delivery must contain deterministic content

When structured comparison coverage justifies the deterministic path, deliver the renderer alone. Do not append it to model prose that makes unsupported global claims. State what was compared, match/difference, named gaps, source, and whether anything changed. Partial coverage must not be laundered into global consistency.

### Scope and identity are conjunctions, not hints

Bind request, authenticated user/workspace, conversation, execution, artifact/revision, source/version, subject, field, operation, and delivery as applicable. Comparing two copies of the same carried value is not independent authority. Read durable state for antecedents and current write conditions. IDs are exact; overlapping text or a correct value elsewhere cannot donate support.

## 8. Repo map for the completion owner

Paths below are relative to the chosen candidate checkout. Line numbers change; find symbols with `rg`.

| Path | Use |
|---|---|
| `backend/core/turn_decision.py` | Interpretation schema/prompt, accepted decision, observed/requested sources, continuation composition |
| `backend/core/action_program.py` | Authoritative action/source vocabulary and compiled operations |
| `backend/core/chat_tool_planner.py` | Tool eligibility, required-read floor, executor integration, figure evidence helpers |
| `backend/integrations/chat_orchestrator.py` | Request-local orchestration, accepted requirement, current-execution observations, guard order, delivery, resolver/builder |
| `backend/core/answer_boundary.py` | Current answer-envelope cleanup; remove unsafe factual fallback before release |
| `backend/core/memory_context_assembler.py` | Evidence excerpts actually supplied and field associations |
| `backend/core/workbook_read_artifact.py` | Typed observations, subject-bound comparison, request coverage, deterministic renderer |
| `backend/core/factual_change_validation.py` | Common factual mutation validation; do not bypass at a planner seam |
| `backend/core/chat_canvas_editor.py` | Edit planning/apply, current artifact/no-op receipt, preservation/readback |
| `backend/core/llm_service.py`, `backend/core/llm/byok_handler.py` | Scoped client, actual transport, retries, cancellation, dispatch traces |
| `backend/core/llm/pinned_planning.py` | Existing scoped pin preference and bounded fallback |
| `backend/core/request_scope.py` | Authenticated request scope |
| `backend/integrations/chat_routes.py`, `backend/core/finalization.py` | Public response/finalization neighborhood; inspect actual current paths |
| `backend/core/task_lifecycle.py`, `backend/core/goal_run_service.py` | Durable operations, questions, delivery/continuation state |
| `backend/core/runtime_identity.py`, `backend/main_api_app.py` | Frozen served identity and startup/schema behavior |
| `backend/core/world_storage_guard.py`, `backend/config/world_storage.json` | Storage preflight and maintenance interlock |
| `backend/scripts/orchestration_acceptance/journey_contract.py` | Historical journey registry checks; not a complete integration gate |
| `docs/acceptance/READINESS_MATRIX_2026-10-17.md`, `SUPPORT_STATEMENT_2026-10-17.md` | Claims to reconcile onto the actual shipping candidate |

Primary current evidence/harness directory:

`backend/scripts/orchestration_acceptance/journey_matrix/l1_l2_l3_integrated_served_20261020/`

Read `ATTEMPT4_RESULT.md`, `ATTEMPT5_ASSESSMENT.md`, `PREDECLARED_CONFIG_ATTEMPT5.md`, `run_composed_served_attempt5.py`, and `successor_gates.py`. Attempt-5 preflight is not product acceptance. Runtime fixes require a new pin and new source hashes before launch.

Other reusable harnesses: `backend/scripts/orchestration_acceptance/browser_onboarding_completion.py`, `deployment_smoke.py`, `deployment_repeatability.py`, `fresh_install_parity.py`, and the archived composed browser/R4 recovery drivers. Inspect their hardcoded paths, ports, imports, and environment before reuse.

## 9. Verification plan: batch the work, do not retest blindly

Start with focused tests for changed behavior and the real captured boundary. Then run the directly affected neighbors once after the final edit. Re-run only because code changed, a failure remains unexplained, or integration introduced a new concern.

Candidate-focused files include:

```text
backend/tests/test_attempt4_repairs.py
backend/tests/test_successor_s7_gates.py
backend/tests/test_s3_s7_captured_replay.py
backend/tests/test_source_ask_tool_execution.py
backend/tests/test_source_ask_acceptance_cases.py
backend/tests/test_l3_requirement_eligibility.py
backend/tests/test_noop_completion_authority.py
backend/tests/test_verified_field_comparison.py
backend/tests/test_context_backed_fulfillment.py
backend/tests/test_pinned_planning_scope.py
backend/tests/test_pinned_planning_transport.py
backend/tests/test_resume_pending_requirement.py
backend/tests/test_resume_intake_verdict_probes.py
```

Find the current required-read timeout suite and finalization/persistence neighbors in the candidate rather than guessing their filenames. General cancellation, execution recovery, research continuation, and R4 recovery tests are relevant neighbors when those paths change, not blanket claims about the new release.

Use the explicit tested interpreter from the candidate environment, not bare `python`/`pytest`. The shell's `python` on this host may not be the intended runtime. Set `TESTING=1` and isolated stores before importing application modules. Every process in a suite must inherit those paths.

Evidence distinctions are mandatory:

- A helper test proves its helper contract.
- A source-string wiring assertion proves only source structure.
- A controlled production-path test proves orchestration with the declared external seams replaced.
- A real route/direct-call test is not authenticated HTTP acceptance.
- Public API acceptance is not browser verification.
- Fresh sessions/connections are not process restarts.
- An observed crash is not a guaranteed post-commit/pre-delivery barrier.
- One successful run is not a latency tail or reliability estimate.

For pre-existing failures, compare exact named failures and reasons on an immutable parent checkout with the same environment. Never use stash over shared edits as baseline proof. Do not report a passing total that hides unexplained failures. A parent failure is nonblocking only if unrelated to required shipping behavior and recorded honestly.

Use mutation checks selectively on critical safety/attribution controls: reverting the repaired source must break the regression for the intended reason. Do not mutate the live/shared owner tree or create tests that mirror implementation details without user-visible consequences.

## 10. Independent review: one meaningful pass

Provide the verifier a frozen SHA, runtime hashes, changed-path list, parent, focused results, captured reproductions, and boundary/claim limitations. Ask for adversarial verification of the complete local repair batch, not just whichever positive example passed.

The verifier should specifically challenge: wrong subject donation, correct-plus-decoy output, empty canvas masking, wrong canvas/revision, missing capability, planner cancellation, extra prior/turn obligations, cross-run IDs, and persistence disagreement. Require real boundary evidence where appropriate.

Classify findings as product, harness, environment, or provider variance. Fix every blocking finding locally and rerun the affected tests before freezing a successor. A wording nit in the report does not justify a new cloud campaign. A changed runtime needs a new candidate identity and review of that change; do not reuse approval over unexplained code.

Once approved, continue automatically to preflight. Do not ask the user whether to start the next routine phase.

## 11. Campaign preflight and execution

One campaign per frozen successor; never two simultaneous worlds measuring the same job. “Once” protects the measurement, not a permanent requirement to ask the user after every justified successor. A failed run is preserved, diagnosed locally, repaired, reviewed, and then a newly predeclared successor may be measured under standing authority. Do not rerun unchanged merely hoping for model luck.

The manifest must bind:

- Product full SHA, launch HEAD, runtime source hashes, harness/gates SHA, clean tracked runtime status.
- Python version/path and dependency fingerprint; frontend build/commit when involved.
- Exact feature flags, interpretation/edit/reply routes, endpoint family and compatibility settings, timeout/output budgets, actual fallback behavior.
- Explicit scratch DB, WAL/SHM, session, BYOK, vector/index, cache, uploads, log, and diagnostic paths.
- Fresh product-created user/workspace/conversation, original requests/fixtures, distractor source, expected preservation and scope behavior.
- New artifact names, a free owned port, running-pilot identity, expected external requests and no new funding.

The guard must verify both intended runtime acceptance and obsolete/wrong pin rejection. If harness-only commits follow a product pin, compare runtime content explicitly and record both identities; never disable the dirty/source guard to launch. Every imported helper must come from the selected candidate or a declared immutable harness dependency.

For acceptance-world paths, run `core.world_storage_guard` preflight before any mkdir. Do not repair a missing portable drive by creating an empty local worlds directory. Use the maintenance interlock only when coordinating actual writers; do not silently bypass it.

Execute the original integrated job with the existing gates, same-world distractors, no hidden configuration changes, and no repairs mid-run. Required proof includes product upload/registration, actual required-read receipt, concise truthful answer, edit once, no-op re-ask, S3 truthful partial/open work as declared, S7 narrow scope and validated settlement, readback/history, real restart, exact accepted status/delivery identity, and zero extra writes/reads where required.

S7 partial is allowed only under the reviewed contract: current date scope covered, delivery true, and every remaining obligation demonstrably the captured prior work. Capture `expected_prior` from durable state between S3 and S7. Never take expected identities from S7's own answer, hardcode old UUIDs, or accept an additional unknown gap. Restart must reproduce the accepted pre-restart state exactly, including reviewed partial, not force completed or accept null==null.

A green `journey_contract.py --check --release` is insufficient: `RELEASE_SCOPE` covers J1/J2/J3 setup, and the fixed journey list does not automatically include custom SPINE/L1/L2/L3 records. Require the explicit composed verdict and each mandatory assertion.

## 12. On failure: shorten the next cycle

1. Preserve first attempt, raw result, route trace, relevant logs, manifest, source hashes, and available durable records. Do not expose credentials or commit full user databases.
2. Identify the first missing transition, then enumerate independent failures. The first gate in list order is not necessarily the sole cause.
3. Distinguish dispatch attempted, HTTP attempts/retries, completion within bound, schema validity, semantic validity, identity resolution, execution, delivery, and settlement.
4. Reproduce locally from the captured payload/state. Batch all known contract holes into this replay before another provider call.
5. Fix the existing responsible mechanism. Keep unrelated passed slices closed.
6. Freeze/review the successor, update declaration/identity, and measure once. Environment-only failures need a verified environment correction; no changed runtime claim.

Use additive rescoring only for a demonstrated harness bug on the same raw evidence, with old and new verdicts preserved. Synthetic corrected data proves gate behavior, not product success. A changed product cannot be certified by rescoring an older run. No gate relaxation, fixture simplification, dropped distractor, hardcoded source value, or hidden retry.

Timeout diagnosis must include queue/claim wait, HTTP attempts, generation, parsing/retries, tool execution, guard/regeneration, finalization, and persistence. Internal sync workers can survive async cancellation; wait for or account for them before the next sample. Do not count a late result as on-time success. Reserve finishing time so completed work is not lost to an optional guard call at the deadline.

If the identical class recurs after two local repair cycles, stop patching symptoms: compare producer schema, acceptance predicate, and all consumers together. Do not run a campaign to find the next permissive default. Investigate the small contract boundary; avoid a whole-app rewrite.

## 13. Clean export and installation parity

After the integrated scratch run passes, export tracked shipping content into a clean directory or use an independent clean checkout. Do not run from the dirty main filesystem or borrow untracked helper modules through `PYTHONPATH`.

Check required runtime imports, package data/templates, migrations/startup schema behavior, entrypoints, frontend build, and generated configuration. Audit guarded imports: optional must genuinely be optional; a missing safety validator cannot silently disappear in export.

The inspected `scripts/quickstart.sh` supports Python 3.11–3.13 and Node 20.9+. The restart script may prefer `venv314`; do not confuse that preference with tested install support. Keep the deployment interpreter/dependencies identical to the accepted profile. If a different profile is chosen, verify it explicitly rather than borrowing older install evidence.

At least run current export/startup and frontend build parity. Reuse the existing fresh-install harness if dependency/startup/launcher changes justify a new clean-environment loop. Earlier install evidence remains useful, but it does not establish current export completeness. A fresh environment on this host is not a clean machine/other-OS proof.

Verify quickstart flag parity: `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`, `ATOM_TASK_LIFECYCLE_ENABLED=1` where these define the accepted profile. Record exact effective configuration without dumping secrets.

## 14. Browser and user-experience acceptance

Verify the browser against the actual frozen frontend/backend pair. Check listener PID/cwd, frontend API base/auth origin, backend health identity, and build ownership before each leg. A port can be taken by another checkout; an open tab or HTTP 200 is not ownership proof.

Use the product for sign-in, onboarding/provider activation, upload, answer, draft edit, no-op re-ask, and reload. Reuse existing browser helpers after parameterizing their root/ports; `deployment_smoke.py` currently hardcodes the main root and ports 8001/3000 and creates user/document/canvas records. Do not run it unchanged against a preview or accidentally certify another server.

UX checks:

- The main answer leads with the requested result, then concise source/limitations; internal envelopes and debug narration are absent.
- “Saved”, “already applied”, “still checking”, and “needs information” reflect actual durable state. No false completed badge beside open work.
- Read-only comparisons never mutate. A previous edit does not authorize a future mutation.
- Unsupported resume input teaches an accepted form naturally and preserves the artifact.
- Busy state/progress reflects existing stages, avoids a frozen-looking screen, and ends on success, limitation, or failure. The user can recover without creating duplicates. Do not build a new progress subsystem unless the existing UI is broken.
- Provider errors explain the next action without leaking credentials or requiring model-family knowledge. Do not ask users to change providers between ordinary turns.
- Raw backend errors are not displayed as fake successful answers. Reload preserves the actual result and open work.

Collect screenshots and console/request failures for failed user transitions. Do not redesign unrelated screens to polish a pilot. Classify remaining cosmetic work separately from blockers.

## 15. Deployment and rollback: exact content, narrow process scope

Prepare all of this before asking for the final live-cutover decision if the hold persists.

**Do not run `scripts/restart_backend.sh` unchanged on this shared host.** At this audit it globally kills `uvicorn main_api_app:app` processes regardless of `PORT`, injects an opencode-go edit-plan pin, snapshots a hardcoded DB path, and continues after snapshot failure. It can kill other worlds and change the tested configuration. These are specific conflicts with the current shared-host deployment scope, not a generic prohibition on the repository's restart process.

Either harden the existing launcher with focused tests or use the already documented narrow pilot procedure, preserving snapshot/health checks. Required behavior:

1. Rehearse startup on an isolated, WAL-safe copy of the current pilot world. Before startup, prove every effective DB/session/vector/BYOK/upload/cache path resolves inside the clone and all background/outbound mutation mechanisms are disabled. A copied DB may contain runnable automations and credential references; setting a few environment variables is not isolation proof. Fail closed if startup could reach live stores or external mutation endpoints. Observe startup schema repair/migrations. The app can alter schema before normal startup; old-code restart alone may not be a valid rollback.
2. Record prior pilot PID/start/cwd/runtime/source, frontend owner/origin, actual DB engine path, configuration and auxiliary-store recovery inventory, and prior launcher/interpreter. Quickstart can use `atom_dev.db`; do not assume every world is `data/atom.db`.
3. Quiesce ordinary pilot write traffic and its background writers for the cutover window, then take the final rollback snapshot; an earlier online rehearsal copy is not that final snapshot. Coordinate any applicable maintenance interlock before stopping writers without locking unrelated worlds. Do not accept writes between the final snapshot and cutover/rollback that a restore could erase. If safe quiescence cannot be established, stop. Create a verified SQLite backup through SQLite backup facilities or the existing WAL-safe mechanism, not a blind copy of the live DB file. Verify integrity and archive identity. Preserve required other stores safely. If a configured external copy exists, verify it; otherwise record local-only backup honestly. No backup or failed integrity check means stop before terminating the pilot.
4. Stop only the verified pilot PID/process group associated with the intended port/cwd/source. Never global `pkill`, kill unrelated worlds, or deploy uncommitted shared files.
5. Start exactly one backend from the intended immutable shipping checkout, explicit tested interpreter, durable world paths, flags, endpoints, and model settings. Ensure the matching frontend is built/running against it. Do not load a live `.env` wholesale into a scratch process or silently override tested settings at cutover.
6. Require `/api/health` frozen identity agreement: full revision/source identity, dirty state, PID/start, cwd, port, actual database/store. HTTP 200 alone fails the gate.
7. Perform the short served browser smoke: sign-in, provider usable, product upload/sourced answer, saved edit/readback/audit, identical re-ask with zero added writes, comparison/continuation if newly supported, reload. Document any smoke records created; do not delete unrelated user content.
8. If deployment fails, stop only the new owned process. Restore prior runtime/configuration. Restore the verified data snapshot only when necessary and with all relevant writers stopped; preserve failed deployment evidence and never reseed an empty world.

Do not move the shared dirty `main` ref under active editors using clever plumbing just to ship sooner. Use a clean release checkout and an explicit source/branch integration plan. If publishing to a remote is in scope, push only owned reviewed commits and the intended release ref. Evidence publication is not runtime integration, and runtime integration is not deployment.

## 16. Final evidence and support statement

Publish one release record containing: shipping full SHA/tree, runtime/source/config identities, dependency profile, frontend build, original and final campaign outcomes, browser evidence, restart/rollback proof, actual served identity, known limitations, exact commands/launcher, and recovery steps. Scrub credentials and personal data before committing. Keep checksums verifiable from the archive itself; do not make the claim depend only on `/tmp`.

Reconcile the matrix, registry, and support statement on the shipping lineage. Preserve tested candidate separately from recording checkout. Custom integrated assertions need explicit coverage even when the historical journey command is green. Remove superseded categorical impossibility claims while retaining their failed evidence/provenance. Do not append every intermediate report forever to the user-facing support statement; keep it readable and link the history.

A truthful release statement should say what the user can do, on which configuration, whether it is deployed, observed latency/sample size, remaining limits, and how to recover. Do not call a partial whole-document comparison complete. Do not promote R3/R4 diagnostic slices into general background safety or restart readiness for every feature.

After the release gate passes, run the already agreed small repeatability/value sample if needed for the support claim. Predeclare its size and record every attempt; no open-ended benchmark campaign or best-of-N reporting. Report the distribution and failures for that sample, not invented confidence or a p95 from one run. Slow-but-functional behavior is disclosed; performance is a separate optimization unless it violates the supported deadline or makes the UI unusable.

## 17. Stop conditions versus completion conditions

Stop the current campaign for identity mismatch, scratch leakage, missing access/entitlement, exhausted declared budget, or a mandatory gate failure. This stops that measurement, not all useful work. Preserve it and continue the diagnostic/local repair path autonomously.

Stop deployment for missing authorization under the explicit hold, unverified backup, migration incompatibility, dirty/unidentified runtime, foreign process ownership, failed composed proof, or failed browser/identity smoke. Prepare the concrete correction or rollback; do not ask the user to solve a coding problem.

The release mission is complete only when:

- All current mandatory pilot assertions pass on one integrated shipping content/configuration.
- Focused independent review is complete and no blocking findings remain.
- Export/startup and browser proof apply to that content/profile.
- The served build has the intended identity and passed its smoke, or the only remaining action is the explicitly withheld final deployment approval with a ready release package. In the latter case report **release candidate ready; deployment held**, not mission deployed/complete.
- The final support statement and recovery path are accurate, navigable, and preserved.

Do not add new release criteria after these are met. Move nonblocking improvements to the backlog and deliver the usable release.

## 18. Work after the pilot is usable

Next program, ordered by user impact: observed responsiveness/provider resilience; truthful full comparison of additional fields; J7 background continuation/recovery; J8 governed automation lifecycle; J9 failure recovery; broader value-answer interpretation; additional integrations and platforms. Each requires its own scope and evidence. Do not claim “whole app ready” until the advertised capabilities and failure/recovery paths have corresponding proof.

General memory, compaction, and summaries should follow the same authority split: LLM summaries help navigation, but cannot replace exact active requirements, permissions, source identities/versions, formulas, revisions, open obligations, audit IDs, or delivery IDs. Carry those in structured durable state; summaries cite them. Recovery reloads authoritative state, checks current access, and does not silently resume mutations. Do not start a memory/compaction redesign to unblock the current pilot unless a captured failure actually requires it.

Domain independence is a release requirement, not a promise based on fixture names. Vary subjects, identifiers, field labels through reviewed vocabularies, source ordering, business context, and casing in controlled tests. No production branch should know Zephyr, Halcyon, QUARTZ, BASALT, a quotation number, a customer, or an acceptance filename. A fixture-specific acceptance predicate is allowed only when clearly labelled as such and is not reused as a production decision rule.

## 19. Communication and handoff discipline

Start with the outcome. During work, give concise updates about findings and the next resolving action; do not make the user approve every checkpoint. Avoid repeated long histories, inflated totals, and “ready for your direction” when an authorized next step exists.

Use this checkpoint report:

```text
Candidate/configuration:
Checkpoint completed:
Boundary actually exercised:
Remaining blocker (or none):
Next action I am executing:
User decision required only if:
```

If context is running low, write a durable handoff containing exact paths/SHA, current changes/ownership, test command/environment, artifacts, actual remaining failure, and next executable action. A new agent continues the same task; it does not restart discovery, create another brief, or rerun a campaign already preserved.

## 20. Established practice informing this guide

These sources support the small existing-mechanism choices; they are not instructions to migrate providers or frameworks:

- [AWS: timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) — bound remote work and avoid retry amplification. Here that means one request deadline, bounded optional work, and accounting for workers that outlive cancellation.
- [AWS: making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) — preserve request identity and at-most-once effects. Here that means receipts, no-op re-asks, and restart checks rather than trusting success prose.
- [Pydantic: validators](https://docs.pydantic.dev/latest/concepts/validators/) — encode cross-field invariants in validation. Here that means generation validates the same scope/action contract that consumers require, with explicit uncertainty preserved.
- [Anthropic: tool-use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) — typed tool interfaces separate model proposals from application execution. Here the registry/accepted requirement determines eligible capabilities and execution records prove what happened. This does not establish any particular DeepSeek/OpenCode transport capability; verify the actual wire on the declared route.

Where generic advice conflicts with this repository, use the repository's proven mechanisms and document why. For example, “retry on failure” does not authorize repeating an unguarded mutation; a convenient global restart does not authorize killing other owners' worlds; structured output does not prove factual truth; and a green setup registry does not prove the composed user job.
