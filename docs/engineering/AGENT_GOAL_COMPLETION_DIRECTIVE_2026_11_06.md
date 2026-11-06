# Agent 1 and Agent 2 guidance for completing Atom goals

Issued 2026-11-06 by the engineering and product lead under the owner's instruction to complete the authorized goals, provide detailed guidance, and push progress between phases.

## 1. Mandate and finish line

Continue each authorized goal through diagnosis, implementation, meaningful regression, the required user boundary, evidence, remote push and review handoff. A phase checkpoint is an intermediate result. Do not stop after a plan, a small green test set, a packaging correction or a statement that you are ready for the next phase.

The product goal is an application people can use to complete business work. The employee system belongs to the overall agent framework: it pursues objectives using evidence, qualifications, teaching, authority and dependencies. Workflow automation supplies repeatable procedures when requested. Both use the existing shared execution and governance mechanisms.

The whole-app target includes the original functional promises and ordinary user journeys. Passing a quote, an invoice, a route family or a release-profile smoke is valuable scoped evidence; it does not make the whole product complete. Preserve the historical 111/123 result, its 123 functional-claim denominator and the 20 separately tracked claims. Do not delete difficult goals, change the denominator or hide features to manufacture completion.

This directive authorizes continued work within the existing engineering assignment. It does not grant new live-provider, account, factor, credential, sending, spending, model-download, deployment or destructive-world authority. Merge and PR-management actions require their own existing authorization. Pause only the dependent action at such a boundary and continue useful independent work.

## 2. Instruction and evidence precedence

Follow current owner instructions and AGENTS.md, then the applicable repository and coordination instructions. Read CLAUDE.md and notes/AGENT_COORDINATION.md before changing shared behavior. This directive supersedes stale queue and stop instructions in the November 5 delivery directive; it does not rewrite historical evidence or override an explicit owner restriction.

Use these existing records rather than inventing a new application state system:

| Record | Purpose |
|---|---|
| Original CLAIM_INVENTORY.json in readme_feature_readiness_2026-11-01 | Frozen functional and separately tracked promises; historical statuses need later evidence reconciliation |
| GOAL_RECONCILIATION_2026-10-31.md | Twelve business goals and the source-bound limits of earlier results |
| G5_EVIDENCE_MATRIX.md and EMPLOYEE_G5_RECONCILIATION_2026-11-04.md | Employee evidence, negatives, later repairs and controlled-scope acceptance |
| WHOLE_APP_COMPLETION_2026-10-27.md | Whole-app finish line beyond a successful pilot |
| ACCEPTANCE_CONTRACT.md and the existing journey registry | Public-boundary journey requirements and candidate attribution |
| /private/tmp/brennan-brief/COMMON.md, AGENT1.md, AGENT2.md and STATUS.md | Current ownership, submission pointers and asynchronous handoff |
| Canonical evidence manifests and independent verifier decisions | Exact accepted source, configuration, boundary and exclusions |

Some records live on newer branches or in assigned worktrees rather than the old local main checkout. Locate their committed version before concluding they are missing. Do not copy old base commits into a new branch merely because an old header names them. Inspect current origin, branch ancestry and accepted dependency commits.

Maintain one current queue table in the shared handoff, linked to these records. For each item retain: goal or route family, user outcome, owner, branch/base, dependency, current state, first failing transition, next action, decisive tests, source/evidence refs and external boundary. This is coordination metadata, not another runtime scheduler or feedback store.

Use distinct states: queued, active, submitted, accepted at stated scope, integrated, externally blocked and superseded. Submitted is not accepted; accepted is not integrated; integrated is not deployed. Unknown is an evidence gap rather than a reproduced failure. Every external blocker names the unavailable action, required input or authority and unaffected work that can continue.

## 3. Current closures and immediate reconciliation

The following are the latest independently reviewed states in this handoff. Preserve their source attribution when building a successor.

| Area | Preserved decision | Immediate action |
|---|---|---|
| PR664 streaming and skill journey | Controlled repairs accepted; final UI source 83dc39c45 and evidence 3c7a6607f accepted at release-profile scope | PR664 merged as d860072a7. Start from current origin and preserve it; do not try to merge it again |
| PR663 alternative CI fixture repair | Overlaps PR664 and lacks its streaming runtime fix; last readback open/non-mergeable | Compare unique behavior against current main. Port only a genuinely missing improvement if needed. Recommend supersession when redundant; closing the PR requires authorization |
| UI journey successor | Hosted 211 API passes, 28 UI passes and 40 role-UI passes; 15 source and 8 artifact hashes verified | Keep these controls. Deferred-page positives establish honest release scope, not disabled feature functionality |
| Evolution caller transaction repair | Product d4cce1625, executed a39dbd12a, reviewed rebased tip ee19946d3; independent 67 passes including all five supplied probes; 28 hashes match | Closed at controlled SQLite scope. Do not resubmit unchanged runtime or replay the sandbox campaign |
| Fleet ORCH07/02 and ORCH01 checkpoints | Accepted at their recorded controlled consumer/binding scopes | Preserve as regression; served quality and broader operational reliability retain separate statuses |
| Feedback, BYOK boundaries, wait policy, Canvas, admin, memory and 2FA | Accepted within their respective exact recorded scopes | Reuse their mechanisms. Reopen only for a new concrete finding affecting the current work |
| Additional Agent2 families | Community skills, agent decisions, goal mode/cancel, document settings, workflow templates, marketplace and chat work have separate preparation/submission records | Reconcile each current ref and verdict before starting another implementation. No acceptance by association |

The detailed verifier records remain in /private/tmp/brennan-brief/, including VERIFIER_PR664_STREAM_SKILL_ACCEPTANCE_20261106.md, VERIFIER_PR664_UI_ACCEPTANCE_20261106.md and VERIFIER_EVOLUTION_CALLER_ACCEPTANCE_20261106.md. Green historical evidence is not transferred to changed code without checking the affected dependency.

## 4. Ownership and parallel work

| Responsibility | Agent 1 | Agent 2 |
|---|---|---|
| Primary delivery | Employee planning, adaptation, workflow/fleet consumers, assignment UI and business-result/artifact journeys | Direct mutation contracts, provider/source identity and freshness, accounting adapters, durable receipts, authority and parallel writers |
| Cross-cutting product work | Normal UI progression, useful outputs, waiting/recovery language, role/profile-aware journeys | Public API correctness, scoped durable state, effect/readback and safe recovery across callers |
| Integration | Trace the end-to-end consumer and verify accepted dependencies actually reach the user | Supply exact service/action contracts, migration/recovery checks and the affected writer inventory |
| Shared files | One named owner for a change window | Other agent works on independent callers, tests or a separate branch until coordination resolves ownership |
| Acceptance | Submit immutable evidence and address findings | Same; neither self-grants independent acceptance |

Keep separate codex branches and worktrees. A clean worktree does not establish a correct base. Read recent commits and current remote state before selecting the branch parent. Record file ownership before touching shared models, registries, LLM routing, employee_adaptation.py, chat orchestration or workflow execution.

Do not silently edit the other agent's dirty files or stage their changes. When a shared interface is needed, write the contract and one testable example to the handoff. Continue independent work while waiting for that interface. If a shared-file conflict is the only blocker, use a separate worktree for reproduction and tests rather than racing edits.

Agent 1 starts by reconciling the merged PR664 and overlapping PR663, then selecting the earliest unclosed user-visible dependency from the existing goal map. Agent 2 starts by reconciling its already-submitted families and selects the first genuinely unclosed bounded family or reviewer finding. Neither starts the community-skill, evolution or UI work again simply because an old directive calls it next.

Each agent keeps one active implementation family and at most one prepared independent successor. Independent verification or CI may run asynchronously. Do not accumulate many unintegrated fixes on incompatible bases to create the appearance of throughput.

## 5. Complete goal map

Read this table as the target and verification pattern for all goals, not a new declaration that each is failing. Reuse accepted evidence first and establish only the missing boundary.

| Goal group | Product result and completion evidence | Ownership and efficient next pattern |
|---|---|---|
| Setup and ordinary account use | Supported install/start, login, onboarding, roles, logout, reload and actionable session expiry; effective runtime configuration | Agent1 user journey, Agent2 auth/state support. Diagnose the first failed transition; feature-test onboarding suppression does not prove onboarding completion |
| BYOK and suitable model selection | Authorized configured routes satisfy workload contracts, economy preference and explicit pins; no-suitable is actionable; failures affect the next scoped decision truthfully | Shared LLM ownership coordinated. Existing one-route and controlled two-route proofs stay separate from served multi-model qualification |
| Authorized common data and search | Upload/connect, list/open/search/export; complete useful extraction with resource/version/scope/coverage; ambiguous names clarify | Agent2 source contract, Agent1 discovery/use UI. Verify real material rather than filename/search hits; one canonical source identity through every hop |
| Spreadsheet and calculation | Correct full-population filter/select/formula/reconciliation with decimal arithmetic, identifiers, units, currency and row/cell provenance | Agent1 business request/compiler, Agent2 source proof. Fix references and typed terms before another model run; verify exported values and restart |
| Canvas and editable outputs | Create/edit/export/reopen the requested current content exactly once; unrelated/protected material survives | Agent1 output/UI, Agent2 effect verification. Existing exact material/digest and audit mechanisms; no title/count-only certification |
| Teaching and reusable agent capability | User creates/selects employee, teaches method/context/qualification/format, corrects it and sees scoped consumption in ordinary work after restart | Agent1 consumer journey, Agent2 durable skill/review boundaries. Lesson storage alone is not behavior; executable generated code remains outside prompt-only promotion |
| Assessment and unfamiliar work | Evidence-grounded decisions on unseen records; unknown/conflicting/expired qualification produces a targeted gap; independent work continues | Agent1 typed semantic choices, Agent2 qualification/source truth. Preserve deterministic policy scope and model-quality failures separately |
| Durable employee objectives | Model-selected useful work and legitimate waits, same-job replies, restart, changing evidence, selective retention, cancellation and late-response refusal | Agent1 end-to-end; Agent2 exact receipt/correlation/recovery. Completion requires every scoped business outcome, not arrival of a reply or last-step success |
| Documents, presentations and email drafts | Requested usable editable output with current verified results and provenance; download/readback agree; no partial artifact while a required result is unresolved | Agent1 composition and usability; Agent2 outbound stages. Verify content as well as bytes; do not claim recipient delivery from provider acceptance |
| Repeatable workflows and schedules | Reviewable blueprint, honest execution_ready, real approval/rejection, registered actions, safe run/pause/cancel, durable schedule/restart behavior | Agent1 workflow consumer; Agent2 mutation/authority boundaries. Blueprint generation and controlled checkpoint tests do not establish scheduling reliability |
| Fleet, goals and background work | User receives actual specialist work, exact execution/outcome linkage, useful progress and truthful terminal states; no duplicate cache/effect after restart | Agent1 consumer/finalization; Agent2 durable state as needed. Recruitment is not work completion; shadow data is not enforced success |
| Direct mutations and whole-app ORACLE | Each reachable family enforces current authority/material, exact operation, durable effect and independent readback; replay/rollback/unknown stages are truthful | Agent2 bounded families, Agent1 caller UX. Discovery counts remain an inventory, not runtime coverage; continue remaining routes without claiming whole-app closure |
| Remaining exposed application | Tasks/boards, communication, search, calendars, marketplace, admin and other enabled surfaces perform their advertised primary action with real state | Split by existing ownership. Inventory role/profile-enabled actions beyond the sidebar; a scope placeholder is not working feature acceptance |
| Installation, compatibility and operations | Supported build and documented versions work; backup/isolated restore and rollback are usable; paths and data survive restart | Shared final integration. SQLite, PostgreSQL, Linux/KVM and multi-worker/soak each keep their own supported/qualified status |
| Performance and comparative promises | Reproducible measurement with declared environment, workload, sample sizes and sources; marketing comparisons have actual support | Select the matching inventory row. Test counts are not quality; local latency is not universal performance; no invented measurements |

Brennan quote/procurement are business configurations and useful acceptance cases, not branches to hardcode. WorkDrive/OneDrive knowledge, customer-specific quote preparation, invoice-to-Books work and an Outlook draft share the same general contracts. Existing one-use send authorization remains exhausted. Prepare local/controlled connector work while any new live qualification awaits its own grant.

Universality is a direction of reuse and broader qualification, not a binary label earned by two domains. Extend through registries, source contracts, typed requests and acceptance cases. Unsupported operations get an honest explanation and an appropriate next action; do not silently substitute a simpler task and call the original goal complete.

## 6. Daily execution loop without phase pauses

1. Read the current ownership, remote status and first failing goal transition. Reuse matching accepted evidence and discard stale queue instructions.
2. Write a short contract card: user outcome, scope, authoritative input/authority, durable effect, verification, recovery and the decisive negative/positive twin. Record the owner and branch. Do this in the existing handoff; do not spend a phase building a planning framework.
3. Reproduce the earliest failed boundary in a unique scratch world. Capture the actual payload, current row and response. Classify the failure before editing.
4. Trace callers and every parallel writer. Repair the existing shared mechanism. Keep a short hypothesis and the observation that would refute it.
5. Run the smallest meaningful contract matrix. Fix it until green, then run the affected neighborhood once. Broaden only for an actual shared dependency or unresolved concern.
6. Freeze the code, restart your own scratch processes when required, and verify the missing public API/UI/served boundary. Do not verify new code against a stale server.
7. Push the coherent implementation, then tracked evidence and exact source pointers. Submit for review and continue an independent authorized item or review preparation.
8. When findings arrive, consolidate the complete supplied matrix and repair the first broken shared contract. Preserve earlier negatives and valid twins. Do not resubmit unchanged runtime with a larger unrelated pass count.

If review or CI is pending, inspect another independent failure, prepare its contract, reduce duplicate tests, review a pending branch's dependency or prepare exact reproduction commands. Do not make a known submitted candidate mutable while its review runs.

After two attempts produce the same failure class without a new diagnostic observation, stop repeating the experiment. Inspect the raw call, state or consumer; revise the hypothesis and continue. This is a change of method, not a request to stop work. A fresh failure before a paid/model attempt should be caught by local preflight rather than another long campaign.

## 7. Engineering patterns that prevent another repair round

### Trace the full consumer path

Map authenticated entry → authoritative scope → source/teaching/context → model proposal if needed → compiler → durable claim → effect → independent verification → durable result → UI/output. A correct helper is insufficient if its fields are dropped on persistence or its result never reaches the consumer. Capture the final payload actually sent, not an imagined helper output.

Find parallel implementations before adding a special case. Prefer UniversalIntegrationService, action registry, existing skill retrieval, task lifecycle, workflow execution, shared feedback CAS and established audit/receipt contracts. Do not create another employee router, approval engine, operation ledger or scheduler to bypass a difficult integration.

For genuinely new architecture, first research mature production patterns using primary documentation as AGENTS.md requires; cite the relevant findings and explain any repo-specific departure. This directive's recipes reuse existing mechanisms and do not require replacing them.

### Make the write condition authoritative

A preflight read gives a useful error; it does not prevent a race. At the actual mutation bind current actor authority, raw/effective scope according to established policy, exact target material/revision, review generation and operation identity in guarded DML. On SQLite, SELECT FOR UPDATE alone is not a concurrency fence. Use the existing CAS, uniqueness/FK constraints and correct transaction ownership.

On a lost claim preserve the peer winner, roll back only owned work, reload authoritative state and apply the established precedence. Never let a dirty ORM flush follow a guarded update with an unconditional primary-key write. All writers of evaluation or material state must participate in the same revision contract.

Caller sessions belong to callers. Empty ORM dirty/new/deleted sets do not establish that no writes were flushed. Do not commit or roll back unrelated work. An already-flushed caller transaction may require a truthful defer until its owner commits or rolls back. This is the accepted evolution pattern, not a reason to create another transaction engine.

### Keep retry callbacks pure and worker ownership exact

No provider/file/model effect belongs inside a retried lifecycle mutation callback. A forced callback retry must yield one plan revision and zero duplicate adapter effects. Worker claims need opaque generations so expired cleanup cannot release or extend a newer claim. ContextVars must be copied per worker submission. Lease takeover is not proof the old physical worker stopped.

Streaming retry state belongs to one request across initial, paid, repair, ranked and sweep paths. Any visible output blocks a subsequent generation; preserve the partial under the existing interruption contract. Failed pairs are tracked across all hops and sweeps remain one-shot. Explicit repair limits do not multiply through recursion or SDK retries.

### Require typed material evidence

Use exact identity namespaces. Operation, resource, message, account, PO and invoice identities are different. Compare the required opaque values under the accepted policy, not substrings or inferred aliases. Missing is unknown; a known mismatch refutes. A boolean, matching title/count or returned digest cannot replace the material the server froze.

Source proof needs observed identity/version and complete known non-truncated coverage. Validate boolean flags and finite integral paired counts strictly. Keep source bytes/hash/version separate from extraction text digest and extractor lineage. An authoritative new hash cannot relabel stale indexed content. Preserve exact supported version prefixes and scope.

Execution uses full durable rows by reference, not just sampled model previews. Preserve verification, coverage and readback when serializing step results. Resolve facts against accepted source scope or explicit authored authority; arbitrary model references establish nothing.

### Bind monetary meaning and output content

Currency, unit, pack size, price basis and material qualifiers are observed evidence when mapped. Do not drop them to enable a request default. Resolve currency, freight, tax rate/amount and exemption through the accepted typed term contract; role/dimension/source/revision/scope/value/expiry matter at compilation and consumption. No implicit FX, zero tax or freight substitution.

Artifact completion needs current verified required results and provenance. Wrong-subject, missing-scope, stale or absent outcomes withhold the report. Preserve earlier artifacts in history while presenting the current one. Verify download bytes/hash and extracted content; for visual quality inspect the rendered supported document/presentation rather than relying only on text presence.

### Separate public safety from private proof

Keep the complete private verification inputs even when public projections must redact them. Stored credentials may require private password/hash verification and a keyed commitment; neither credentials nor hashes belong in public receipts/logs. Error handling exposes safe stage/class codes and opaque identities, never raw SQL, bound parameters, OTPs or provider secrets.

## 8. Effect and recovery semantics

| Outcome | Required meaning | Next action |
|---|---|---|
| Refused or not applied | No effect for this attempt; confirmed rollback is effect=none | Correct/refresh the request under the existing operation contract |
| Verified | Exact effect and required durable evidence match | Continue eligible dependent work |
| Already applied | Original operation/material reconciled; no new dispatch | Return the original acknowledgement with truthful current verification |
| Committed unverified | Commit known, required readback absent/refuted | Reconcile original effect; do not claim success or overwrite newer state |
| Effect unknown | Commit/provider outcome cannot yet be established | Preserve identity, block dependents and reconcile; do not blindly resend |
| No change | No new effect required | Verify current applicable state without inventing a mutation receipt |

Same operation ID with different material conflicts. An exact accepted reply replay is already_applied, not a new late reply; a new late reply cannot resurrect cancellation. Provider acceptance, Sent Items readback and recipient delivery remain separate. A recovered audit can acknowledge an old event but cannot manufacture a new authentication event or consume another recovery code.

Local SQL mutation and audit should be atomic when the existing family uses one database. SQL plus a file or remote effect is not made atomic by a process-local lock; use the existing compensation/reconciliation contract, verify failure windows, and retain multi-worker limitations. Do not certify PostgreSQL by inference from SQLite or distributed serialization from an in-process lock.

## 9. Product rules for employee work

Model choices should express business decisions: evidence to read, a semantic mapping, a supported work request, a targeted question, a genuine wait or a proposal to reconcile. Deterministic compilers own action bindings, step IDs, dependency references, operation/correlation identities, authority, arithmetic, receipts and outcome checks.

Readiness must distinguish established false, missing, stale, conflicting and unavailable. A missing fact blocks only its dependent branch. Skipped or result-less predecessors do not meet required receipts. Recheck readiness immediately before claiming an operation. An independent branch is useful only when it advances an actual objective and produces a durable result, not a fabricated busy-work step.

Wait choice must be supported by trusted readiness and allowed decisions. Do not wait for evidence already available in unread authorized scope, hide ambiguity as missing, or invent authority in a wait. A genuine missing external fact can still justify a wait while independent work remains available. Clarification names the missing role and known business identity. Answers reauthorize sources and settle only the matching obligation on the same job.

Outcome truth is separate from plan and wait status. Arrival of evidence is not the dependent calculation/reconciliation receipt. Retain, no result, no-suitable routing and an unrelated successful operation leave scoped required outcomes unresolved. Replanning cannot erase or weaken them. Exact subject_identity is required where the business operation requires it; an unscoped quote still needs a real applied verified quote result.

Teachings and corrections apply under explicit scope, revision and validity. Changed source/qualification invalidates the affected closure and preserves unrelated operation IDs, results and receipts. Running/uncertain descendants cannot be replaced to escape their effects. Reconcile them first.

The UI explains what completed, what is waiting, why and the next useful action. A terminal job does not display a stale configuration warning. Ordinary authorized work should not gain unnecessary approval prompts. Business users should not need step JSON, model names, scores, stack traces or internal audit mechanics to make normal decisions.

## 10. BYOK and faster model resolution

Use the existing capability-aware BYOK path. Economy is the default among eligible configured routes, with expected cost of a satisfactory result and latency considered. Capable Flash routes are first-class; branding and model size are not eligibility rules. Explicit quality preference reorders eligible candidates and never bypasses authority, scope, credentials, protocol, capacity or safety.

| Observation | Diagnose first | Efficient repair pattern |
|---|---|---|
| No dispatch or no-suitable | Actual policy/catalogue/local registration, exact profile/version, scope, protocol and real request context size | Fix eligibility context; do not silently relax quality or swap providers |
| Timeout/cancellation | Remaining monotonic deadline, provider queue, actual worker ownership and hidden retry multiplication | One retry owner; bounded cancellation/lease handling; no concurrent duplicate probe |
| Schema echo or malformed instance | Actual final prompt/schema/raw response and first validation error | Narrow typed instance shape; one bounded feedback repair; no expected answer injection |
| Wrong evidence/mapping/wait | Trusted readiness, full evidence identities, distractors and observation binding | Correct consumer context/semantic guard; preserve the negative and exact model attribution |
| Valid choice blocked at execution | Proof, freshness, authority, term binding, inputs and budget | Fix the broken deterministic boundary, not the model by guesswork |
| Useful work but unresolved outcome | Required identity/result receipt, continuation and artifact criteria | Preserve job/results; invoke supported continuation or owner budget recovery rather than recreating work |

Use compact profiles for narrow business choices when supported. Do not replace a model's decision with a hardcoded correct plan to create qualification. Strict pins are exact-route-or-failure. An attempted route is not a served route; record served provenance only when established by that generation. Clear stale provenance at each new boundary.

Transport/schema success, grounding support, validated decision success and business satisfaction are distinct. Unresolved grounding earns no capability success; genuine negative judgments remain observable. Persist evaluation only through the shared CAS bound to the exact generation, tenant/workspace, provider/model and profile/version. Keep incident identity, reviewed recovery and post-commit cache invalidation. Never add another feedback store or let a deterministic fallback inherit model credit.

Run authorized inference under the named owner and finite budget. Do not launch another server or generation to bypass a busy owner. Compare models on the same held-out task/configuration before declaring one better. Served multi-model qualification requires the configured/authorized routes; controlled two-route doubles remain valuable but separate. No automatic new key, download, cloud fallback or spending authority is supplied here.

## 11. Test once at the right boundary

Start with a complete finite failure matrix rather than discovering one omitted field per review round. For bindings exercise every required field omitted, null, empty, wrong type, contradicted independently, namespace-swapped and complete valid. Add stale revision, unauthorized actor, peer authority change, replay same/different material and restart where durable state matters.

For races use deterministic interleavings with a second session between check and claim. Assert losing call count, peer winner, unchanged unrelated work and durable fresh-session result. Test both verdict/writer orders where precedence matters. Include legacy/parallel writers rather than protecting only the new path.

Run meaningful tests that reach the real service/route/consumer. Source-substring assertions and mocks that invent attributes do not replace execution. Use real-shaped doubles, isolated discovery catalogues, local health monitors/caches/cooldowns and exact scope. A doubled route still obeys production eligibility. Never loosen the gate merely to make a fixture dispatch.

Use this sequence: decisive probes and valid twins → affected neighborhood → exact CI selection when integration changes → missing public boundary → fresh-checkout evidence check. Do not repeatedly broaden tests after a passing relevant set unless new code/failures justify it. Frozen sources may reuse unaffected earlier evidence with explicit dependency attribution.

Compare baseline failures by exact node/signature and environment; counts alone are insufficient. Name skips and exclusions. An infrastructure PermissionError is not a product failure. A provider validation error is not automatically transport. A timing flake needs a controlled diagnosis, not retries until green. If a check is non-gating, report its actual log result separately from the overall green job.

Browser tests must follow actual configuration. Assert exact deferred capability labels while retaining enabled-feature positives. A heading smoke does not prove the primary action. Feature fixtures may isolate onboarding; onboarding acceptance must exercise the real first-run completion separately. Reuse the proven stable journey before promoting additional browser checks to gating; do not weaken existing required checks.

## 12. Faster packaging and reproducibility

Freeze source before the acceptance run. Record product commit, executed commit/tree, dirty/runtime-file identity if applicable, frontend build, configuration, test world and actual process launch. A test-only successor and an evidence-writing commit are separate from runtime. Capture the exact returned run/operation/audit IDs; never assert a page-wide total that might belong to an older job.

Track original raw requests, parsed/raw completions where allowed, relevant states, artifact bytes, logs and a compact verification report. Use the existing Git evidence checker to compare source_files against executed_source and artifacts against the evidence ref. Review ignored files explicitly: a local log absent from Git is not delivered evidence. Do not include secrets or live data.

Run packaging checks before submission, not after the verifier finds missing files. Verify both counts and named assertions; distinguish unique tests from overlapping subsets. Preserve original negative runs and provenance corrections. Never regenerate a historical log to fit a manifest or silently replace the source hash with the bytes present during documentation writing.

A valid submission lets the verifier reproduce the decisive result without guessing a Python path, plugin, environment, source, model owner or fixture. Include exact commands, prerequisites and safe scratch paths. Copy accepted evidence pointers instead of duplicating entire archives.

## 13. Remote checkpoints and integration

Commit and push on your own codex branch between coherent phases. Continue after each push; it is a backup/review point, not a request for the owner to say continue.

| Checkpoint | What to push | What follows without a pause |
|---|---|---|
| Stable reproduction/contract | Owned reproduction tests and scoped diagnosis; label intentional failures | Repair the shared cause |
| Runtime fix passes decisive gate | Coherent implementation and relevant tests | Affected regression |
| Regression complete | Any resulting fixes and the exact tested checkpoint | Freeze required acceptance boundary |
| Evidence checks pass | Tracked safe logs/artifacts/manifests and final refs | Review handoff and independent next work |

Inspect branch, status and staged diff. Stage explicit owned paths, never all changes. Inspect logs for credentials before adding them. Normal first push is git push -u origin HEAD; later pushes are git push origin HEAD. Check success and equality with the intended remote tip. Do not claim a push merely because the worktree is clean.

A push rejection is a concrete remote problem: preserve the local commit, inspect the changed remote and coordinate. Do not force-push, overwrite another agent, rewrite evidence history or merge protected main to make the problem disappear. New external authorization, if required by the environment, stays pending while safe local work continues.

Integration owner checks actual current PR state first. PR664 is already merged. PR663 needs behavioral reconciliation against current main, not a second wholesale application. If there is a unique improvement, port only it on a fresh codex branch, keep the stronger accepted streaming/UI/authority contracts and run the affected gate. If redundant, record that result and recommend closure through the authorized PR owner. Do not close, review or merge on assumption.

For other accepted branches build a dependency order from shared files and source bases. Integrate one coherent dependency family at a time under the existing merge authorization. Run combined relevant regressions and CI on the actual proposed head; individual old branch passes do not prove conflict resolution. Preserve accepted original bundles and add an integration index rather than reattributing them to main. No blanket force/ours/theirs resolution.

## 14. Authority boundaries without idle work

| Condition | Continue now | Hold only |
|---|---|---|
| Review/CI pending | Independent diagnostics, next contract, evidence validation, source/branch reconciliation | Acceptance promotion or dependent integration |
| Shared file owned elsewhere | Separate worktree, callers, tests, interface examples | Conflicting edit until ownership agreed |
| Missing live connector/model route | Controlled/local mechanisms, configuration UX and exact qualification plan | The new live call/key/spend/download |
| Missing business fact | Useful independent branch and targeted question | Its dependent operation/result |
| Known effect, lost confirmation | Durable readback/reconciliation under existing contract | Blind resend or new operation |
| Unsupported PostgreSQL/Linux/KVM/soak environment | Portable contract checks and reproducible setup plan | Runtime qualification claim |
| Product policy or scope must change | Trace options, impacts and a concrete reviewable proposal | Applying the new policy or hiding a feature |
| No ready authorized work remains | Report completed local goals and exact external blockers once | Invented work or a false whole-app pass |

Do not ask permission for routine implementation choices, reversible fixes, relevant tests, evidence packaging or already-authorized branch pushes. Do not treat silence as consent to a new external action. Explain the exact missing authority/input only when it is genuinely needed, with the work already made concrete and reviewable.

## 15. Progress reports and escalation

During active work provide concise updates at meaningful changes and at least about once a minute: what was learned, what remains uncertain and what the next check resolves. Do not narrate every command or send repetitive unchanged CI polls.

Use a compact report: goal/branch and latest pushed commit; first failed transition or closed contract; decisive test result; current boundary and next action. End a phase report with the next action you are taking, not an offer to continue. Report source-bound acceptance separately from CI, integration, deployment and broad model quality.

When a hypothesis stalls, produce the smallest counterexample and the captured observation, then change method. Escalate a policy/authority decision with options and impact. Escalate a technical finding with the exact frozen source, decisive test and expected contract. A count of passing unrelated tests is not an answer to a concrete failure.

## 16. Definition of done

A finite item is ready for independent acceptance when its intended runtime behavior exists on the submitted source, every known in-scope finding and valid twin passes, affected checks are complete with truthful exclusions, the required public boundary is evidenced, artifacts match Git, owned commits are pushed, and recovery/limitations are documented. It remains submitted until independently accepted.

Local engineering completion means all currently authorized finite items are either accepted/integrated as required or explicitly awaiting a named external dependency. It is not whole-app readiness if material capabilities remain unqualified. Keep general adaptive judgment, served multi-model breadth, live connector breadth, PostgreSQL runtime, Linux/KVM and multi-worker/soak at their real statuses. Do not change historical planner 5/5, goal router 1/2 or alignment gap3.0 through documentation.

Whole-app readiness requires one declared integrated candidate/configuration with the exposed user promises reconciled, useful ordinary journeys passing, honest configuration/error states, durable/recovery behavior, reproducible evidence, supported install/backup/rollback instructions and a current support statement. No silent release-scope reduction. Deployment is a separate owner decision.

## 17. Start immediately

Agent1: preserve merged PR664 and accepted fleet/employee/workflow evidence. Reconcile PR663's actual remaining behavior without merging duplicates. Then claim the earliest unclosed user-facing dependency in the current goal map, implement through the missing boundary, push checkpoints and continue until that finite scope is delivered. Do not repeat closed model/browser episodes to fill a phase.

Agent2: preserve accepted evolution caller ownership, admin, memory, Canvas, 2FA and feedback contracts. Reconcile the already-submitted local families and their review status first. Prioritize a supplied failing contract; otherwise claim the next genuinely uncovered bounded family, finish its real consumer/replay/authority/rollback matrix, push and submit. Do not restart a submitted family based on an old next-task note.

Both agents: own the complete delivery loop, keep one implementation family active, help resolve the earliest shared blocker, push between coherent phases and keep independent work moving while review is pending. Stop only at the specific authority or information boundary that actually prevents further progress. The owner should not have to repeatedly authorize the next test, correction, evidence file or push in the same assignment.
