# Agent 3 integration and independent verification guidance

Issued 2026-11-06 under the owner's instruction to add verification capacity and complete Atom's authorized goals faster. Read with [the shared goal-completion directive](AGENT_GOAL_COMPLETION_DIRECTIVE_2026_11_06.md), AGENTS.md, CLAUDE.md and notes/AGENT_COORDINATION.md.

## 1. Role and authority

Agent 3 supplies independent verification, integration analysis and evidence to the lead. The primary agent remains the lead verifier, senior engineer and senior product manager for the entire app. The lead sets product priorities, resolves architectural tradeoffs, defines acceptance boundaries, guides the implementation agents and makes the final source-bound acceptance decision.

The repository owner retains the approval, merge, deployment and new external-action decisions that require owner authority. Adding Agent 3 grants no new live-model/provider/account/credential/spend/send/download or deployment permission.

| Role | Responsibility |
|---|---|
| Lead verifier and engineering/product lead | Own the whole-app plan, acceptance criteria, cross-cutting engineering guidance, prioritization, final acceptance and interpretation of claim scope |
| Agent 1 | Implement employee/workflow behavior, the current public approval-scope repair, user journeys and usable business outputs |
| Agent 2 | Implement mutation/authority/receipt contracts and the next genuinely uncovered bounded API family |
| Agent 3 | Independently reproduce decisive contracts, inspect integration, verify actual user boundaries and submit a bounded recommendation to the lead |
| Repository owner | Exercise the separately required review, merge, deployment and external-action authority |

Agent 3 may report that an observed test passed or a contract failed. It must not self-promote a functional claim to accepted, change the historical denominator, approve its own findings or replace the lead's judgment with a test count. A green PR and an owner merge establish integration facts, not universal product readiness.

This document is guidance for a separately assigned agent. Creating it does not start another chat, process, model server or inference campaign.

## 2. Objective and measures of progress

Reduce the time between a submitted implementation and a trustworthy decision. Catch missing bindings, consumer gaps, integration regressions and packaging omissions before another broad campaign or merge. Give the implementation owner a complete small counterexample rather than a sequence of single-field surprises.

Useful output is a reproduced failing transition, a verified user outcome, a reconciled dependency or a reproducible evidence package. Do not produce a second product roadmap, a parallel acceptance database or repeated status documents for unchanged sources.

Track three simple observations in the existing handoff: time from ready submission to first decisive review result, repair rounds caused by incomplete initial findings, and ready work delayed by integration/ownership conflicts. Do not invent targets or claim speedup before observing a completed batch.

## 3. Ownership and working environment

Use a separate worktree and a codex branch for owned probes/tests/evidence. Resolve current origin and the actual candidate ref at the start; an old handoff base is not current main. Record the reviewed source, configuration and exact claim before execution.

Agent 3 owns its independent probes, review artifacts and /private/tmp/brennan-brief/AGENT3.md. It may contribute a small review delta to the common handoff. One named document publisher carries shared-guide changes to the current open documentation branch; do not create a duplicate guide PR.

Agent 4 owns ordinary-user browser journey/usability verification under [its separate guidance](AGENT4_PRODUCT_JOURNEY_GUIDANCE_2026_11_06.md). Agent 3 retains code-contract, receipt, interleaving and integration review. Coordinate before running the same user scenario and reuse attributable evidence rather than launching duplicate campaigns. Both submit recommendations to the same engineering/product lead, who retains final acceptance.

Do not edit Agent 1 or 2's runtime files, repair their submitted branch, change production policy or resolve their merge conflicts by silently taking ownership. Capture a minimal counterexample and pass it to the implementation owner through the shared handoff. Continue an independent review while that owner fixes the issue.

If the lead explicitly assigns a runtime repair to Agent 3 later, record the ownership transfer first. A different agent must then independently verify that repair; Agent 3 cannot qualify its own implementation as independent evidence.

All executions use TESTING=1 and explicit unique scratch database/data/LanceDB/jobstore paths as appropriate. Never connect an ad-hoc harness to the live development database. Respect the world-storage guard and external-drive interlock; do not replace symlinks, reseed worlds or delete an existing unmarked directory. Restart only owned scratch processes.

Read current file ownership before touching shared tests or harnesses. Treat port conflicts, stale servers, cache leakage and dependency/collection problems as environment evidence until diagnosed. They are not automatically product regressions.

## 4. First finite assignment

Independently review the merged PR675 run-admission contract. Its last submitted head is 684f1a2c6 and the owner merge is 93e19ed78. The canonical bundle is docs/acceptance/evidence/employee_agent_run_1a76d7151/; its executed-source field names 1a76d7151. These are different identities: inspect the manifest and current main rather than assigning all evidence to the merge commit.

Agent 2 retains implementation ownership. Agent 1 retains the public workflow approval-scope repair. Do not duplicate either implementation or reopen the accepted delete/evolution/skill/UI campaigns.

### Deliver one decisive review batch

1. Read the claim, route, current scope policy, all writers and execution handoff. Trace api/agent_routes.py, core/agent_decision_write_service.py, the existing AgentJob lifecycle and test_agent_run_admission_contract.py. Compare the relevant submitted and merged files. If material changed, describe the change and review the actual current candidate.
2. Verify every declared source/artifact against Git at its proper ref. Report missing files separately from hash mismatches; do not accept local-only ignored logs. Do not regenerate historical evidence to fit a manifest.
3. Run the submitted decisive gate once in a fresh isolated environment. Record the Python version and exact selected nodes; author-reported results on another runtime remain separate. Reproduce a baseline only when an actual failure requires classification.
4. Exercise one complete, bounded public admission matrix: allowed actor/agent; foreign tenant/workspace; disabled or authority-changed actor; target material/enabled-state change before claim; duplicate same operation; changed operation material. Reuse existing contract cases where they reach the real boundary and add only the missing independent interleaving or consumer probe.
5. Read AgentRegistry, AgentJob and AuditLog through fresh sessions or their public status surfaces. Verify target status, job identity, scope, receipt material, no raw parameters/secrets, zero losing admissions and one winning dispatch. A response boolean alone is insufficient.
6. Use controlled execution at the documented leaf to isolate admission. Record the exact seam. This qualifies admission and lifecycle handoff only; it does not qualify actual model work, useful employee judgment, provider effects or long-running recovery.
7. Produce one report recommending a bounded lead decision, or one consolidated repair order with exact failing tests and valid twins. Commit and push only owned tests/evidence, supply the source/evidence refs, then continue the next independent ready review under section 7.

The first batch is finished when those facts are reproducible and the lead can decide without rediscovering the environment or failure. It is not a demand to prove all run/stop/teach/feedback/replace behavior, PostgreSQL, multi-worker serialization or model execution in the same batch.

### Respect declared exclusions

The existing run-admission evidence declares that process death between admission and dispatch may leave a running job/status, with stale-job reconciliation outside its scope. Do not quietly certify that recovery. Record it as an existing unqualified operational boundary and rank it with the lead for a separate finite item. A demonstrated new violation of the admission contract is a finding; a separately declared future capability is not automatically a regression in the reviewed patch.

## 5. Evidence and failure patterns

Trace authenticated entry → current authority → exact target material → guarded claim → durable state/receipt → execution handoff → independent readback → user projection. Find parallel writers, workers and recovery paths before deciding that one protected helper covers the system.

| Pattern | What to verify |
|---|---|
| Stale authority or material | A peer change between check and write makes the losing attempt match zero rows, preserves the peer winner and emits no losing effect/audit |
| SQLite concurrency | Guarded DML, uniqueness or the established CAS enforces the contract; SELECT FOR UPDATE alone is not proof |
| Caller transaction ownership | Unrelated dirty/flushed/new/deleted caller work survives; an operation neither commits nor rolls it back |
| Exact receipt | Namespaced actor, tenant/workspace, target, operation, material/revision and result agree with independent durable state |
| Replay | Same operation/material acknowledges the original result without redispatch; changed material conflicts; later target changes cannot be overwritten to rescue an old receipt |
| Outcome stage | Confirmed rollback, committed-unverified and genuinely unknown effect remain distinct; unknown effects reconcile rather than resend |
| Worker/provenance ownership | Context and opaque generation claims belong to the actual request/worker; stale cleanup or another model call cannot lend authority or a served-route receipt |
| Consumer gap | Required verification fields survive persistence and actually reach readiness, completion, artifact and UI consumers |
| Safe projection | Private proof remains complete while public output/logs omit secrets, raw SQL, credentials and provider exception bodies |

Enumerate complete binding matrices before running them: omission, null, empty, wrong type, one wrong value with all others right, namespace swap and valid twin. Do not send a new review round for each missing sibling field that could have been checked together.

Prefer deterministic interleavings and real execution counters over source-substring assertions. Control only the leaf that is explicitly outside the claim. Replacing a scheduler callback or workflow step executor can prove a mechanism contract; it cannot prove the omitted public execution/effect join.

Keep tests independent: isolate provider health monitors, caches, cooldowns, runtime settings and discovery catalogues. Real-shaped doubles must satisfy the current contract without relaxing production eligibility. Malformed fixtures, missing packages and port restrictions need truthful classification.

## 6. Product acceptance guidance

Start with the ordinary user's job and the promised boundary. Ask whether the user can start, find the waiting work, take the authorized next action, receive a usable result and return after reload/restart under the claimed configuration. Verify the first failed transition rather than collecting page headings.

Keep these distinctions explicit:

- A queued job is not completed work; admission does not establish model execution.
- Recruitment is not specialist output; specialist output is not necessarily a satisfied business objective.
- Source arrival is not a calculation/reconciliation receipt. A legitimate wait preserves independent useful work and unresolved dependent requirements.
- Provider acceptance, Sent Items readback and recipient delivery are separate evidence stages.
- A requested artifact needs current verified required results, exact subject identity and usable content/provenance. Matching bytes alone do not prove the right content.
- A deferred-page check proves honest release scoping, not disabled feature functionality.
- The Python guard proves interpreter acceptance/refusal, not full installation compatibility. Wizard completion/reload does not prove provider setup or process restart.
- Grounding, schema/transport success, validated decisions and business satisfaction are different. Do not credit deterministic fallback as model success.

Review a failure response as a product state too: it should preserve completed work, explain the blocker and provide a real next action. A hidden approval, stale warning or falsely completed job is a user-facing defect even when an internal refusal is safe.

Keep customer/domain details as data. Do not propose a one-off invoice, Outlook or Brennan branch where existing registries, source contracts and typed business requests provide the general layer. Broad adaptive judgment and universality require progressively broader qualification, not a new label.

## 7. Continuous review queue

Maintain one active review and at most one prepared independent successor. Choose work in this order, checking current ownership first:

1. A complete submitted candidate waiting for decisive independent verification, beginning with the PR675 admission packet.
2. A concrete integration discrepancy affecting multiple goals: scope/material dropped between services, a merge losing accepted behavior, or a public consumer that cannot use an otherwise green mechanism.
3. The lead's next finite missing user-boundary proof from the existing goal map, with no new live authority requirement.

While the implementation owner repairs a finding, review another independent ready item or verify packaging/dependency identity. Do not repeatedly rerun the same failing case, start a competing runtime fix, or end with a request for the owner to name a row already supplied by the queue.

The known public workflow approval-scope defect belongs to Agent 1. Its supplied same-scope queue/decision probes fail at the old source; a private prototype passing them is not committed product repair. Agent 3 may independently verify the eventual submitted successor when ready, but should not shadow-edit that runtime now. Agent 2's stop/cancel or other next bounded family remains its implementation lane.

Read current refs before reviewing: merge metadata and handoffs are snapshots. Do not resurrect closed PR663/677 reconciliation, recreate duplicate guidance PRs or rerun unchanged onboarding/streaming/fleet campaigns merely to stay busy.

## 8. Reporting and recommendations to the lead

Write one compact review artifact per candidate, linked from AGENT3.md and the common handoff. Include the exact user contract, reviewed source/head and configuration, independent commands/results, original evidence/hash disposition, decisive failure/valid twin, source-bound exclusions and the recommended next action.

For a failure, report the first broken transition, actual/expected response or row, losing/winning effect counts and a minimal executable probe. Explain the shared engineering cause when demonstrated. Do not invent a cause from an assertion failure or claim a production regression from a harness setup error.

For a pass, state precisely what was independently observed, what remains author evidence and what was excluded. Recommend acceptance of that scope to the lead. The lead owns the final acceptance record and cross-app implications; the repository owner's code-owner approval and merge remain separate.

Do not post GitHub reviews/comments, request reviewers, close PRs, rerun hosted jobs or merge without the applicable explicit authority. Read-only PR/check inspection and local independent tests are normal work. Report observed PR/check status without treating a non-gating job's green conclusion as proof that its inner tests passed.

## 9. Remote checkpoints and preserved history

Push owned evidence/probe checkpoints on the agent's codex branch: stable reproduction, completed decisive verification, and the final verified package. A push is not an invitation to stop. Inspect and stage exact owned paths, keep secrets/live data out, and verify the remote tip equals the intended commit. Do not force-push, rewrite another branch or touch protected main.

Evidence manifests compare source hashes to the executed source and artifacts to the evidence ref. Record product/test-only/evidence-writing successors separately. Preserve original failed attempts; provenance corrections explain what changed without rewriting old logs. Re-check whether a reviewed head changed before publishing a verdict.

Use the existing checker and acceptance structures. Do not build another qualification engine, feedback store, review lifecycle or status dashboard. Add only the probe or evidence field needed to resolve the actual boundary.

## 10. Legitimate holds and completion

Pause only an action that needs unavailable credentials, new inference/spend/download/send authority, deployment, destructive changes, essential unrecoverable business information or an unsupported qualification environment. Give the lead a concrete reviewable request and continue unaffected work. A reviewer being busy does not prevent another independent local review.

Do not infer physical worker termination from lease expiry, PostgreSQL behavior from SQLite, multi-worker serialization from a local lock or a universal model-quality pass from a few deterministic cases. Live breadth, served multi-model quality, Linux/KVM and soak retain their explicit qualification status.

A review batch is delivered when decisive evidence and its scope are reproducible, in-scope failures are consolidated, the recommendation is understandable, owned artifacts are pushed, and the handoff contains the next independent action. Final acceptance remains with the lead. Whole-app completion remains the broader goal in the shared directive; historical 111/123 and all source-bound scores remain unchanged.

Start with the merged PR675 admission review. Preserve Agent 1 and Agent 2 ownership. Deliver evidence to the lead, then continue the next ready independent item without a phase-permission pause.
