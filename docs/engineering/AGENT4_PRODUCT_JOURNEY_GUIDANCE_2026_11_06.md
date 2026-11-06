# Agent 4 product journey and usability verification guidance

Issued 2026-11-06 under the owner's instruction to add ordinary-user journey verification and complete Atom's authorized goals faster. Read [the shared goal-completion directive](AGENT_GOAL_COMPLETION_DIRECTIVE_2026_11_06.md), [Agent 3's integration work order](AGENT3_INTEGRATION_VERIFICATION_GUIDANCE_2026_11_06.md), AGENTS.md, CLAUDE.md and notes/AGENT_COORDINATION.md.

## 1. Mission and lead authority

Agent 4 verifies whether ordinary users can complete the app's advertised jobs through its actual interfaces. Follow the intended interaction, observe the network/state/result, and report the first transition that prevents useful completion. Supply reproducible product evidence and repair guidance to the lead and the implementation owner.

The primary agent remains the lead verifier, senior engineer and senior product manager for the entire app. The lead sets priorities and acceptance criteria, makes architectural/product tradeoffs, coordinates all agents and decides final source-bound acceptance. Agent 4 does not replace those responsibilities or independently declare the app ready.

The repository owner retains the separately required code-owner review, merge, deployment and new external-action authority. This work order grants no new live-provider/model/account/factor/credential/spend/send/download or deployment permission. Its initial journey uses only isolated local test users and no inference.

## 2. Separate the four work lanes

| Role | Owns | Does not take over |
|---|---|---|
| Lead | Whole-app engineering/product direction, prioritization, acceptance criteria, cross-app interpretation and final acceptance | Owner-only external grants and protected merge decisions |
| Agent 1 | Employee/workflow implementation, public approval-scope repair and useful outputs | Agent 2's mutation family |
| Agent 2 | Mutation/authority/receipt implementation and next bounded API family | Agent 1's workflow/HITL runtime |
| Agent 3 | Independent code-contract, receipt, race and integration verification; first merged-675 admission review | The implementation it reviews or Agent 4's active browser journey |
| Agent 4 | Ordinary-user browser journeys, usability failures, role/profile-aware feature readiness and reproducible public-boundary evidence | Shared runtime repairs, Agent 3's active contract review or final acceptance |

Agent 3 may inspect a concrete API/state defect found by Agent 4 as a separate assigned review. Agent 4 may consume Agent 3's accepted evidence to avoid a duplicate test. Neither should launch the same campaign independently. Coordinate source/configuration, ownership and the one missing assertion before running.

Do not edit another agent's runtime branch or silently repair the feature under review. Report the executable counterexample to its implementation owner. If the lead later transfers a repair to Agent 4, record the transfer and arrange independent verification by another agent before acceptance.

Creating this document does not start an Agent 4 chat, browser process, server or model call. It is the work order for the separately started agent.

## 3. Workspace and evidence prerequisites

Use a separate codex worktree/branch and a uniquely named scratch world with explicit database, data, LanceDB, file and jobstore paths where applicable. Use TESTING=1 for test harnesses. Never point a one-off script at the live development database or treat a long-lived seeded world as a fresh-user proof.

Read the current goal map, acceptance records, current refs, shared handoffs and ownership before selecting a journey. Record backend commit/tree, frontend build, product profile, role, test-user/world identity and actual launch configuration. A passing old episode stays bound to its old source. A current unknown is an evidence gap, not automatically a failing product.

Read the actual product profile and advertised prerequisites. Verify enabled routes and supported operations rather than assuming every old sidebar destination is enabled. A truthful deferred page qualifies release scoping only; it does not close the underlying feature goal. Do not enable a hidden feature, force a privilege, bypass onboarding or change scope merely to obtain a pass.

Keep server ownership explicit. Restart only owned scratch processes after backend changes and confirm the served source/build. Respect world-storage guards, external volume checks and the maintenance interlock. Do not replace missing storage with an empty local directory, reseed, reset an arbitrary directory or stop another agent's server.

If browser automation or local port permissions prevent the run, capture that environment limit. Do not report a browser pass from API-only tests or label a port restriction as a product defect. Continue another independent authorized diagnostic that the environment supports.

## 4. First finite assignment

Qualify the account-return journey on one frozen current candidate: ordinary sign-out → fresh browser → normal sign-in → same authorized user/workspace → coherent expired-session recovery. This is the first candidate because accepted onboarding currently proves wizard completion and same-browser reload, not this full return path.

Before execution, check for matching accepted evidence on the same relevant source/configuration. If it already answers every required assertion, reference it and move to the next enabled unqualified journey under section 8. Do not rerun an accepted onboarding or UI campaign just because it is easy to count.

### Required controls

1. Use a unique ordinary test user created through the supported local product setup. Sign in through the normal UI. Establish the existing onboarding prerequisite through its documented setup, and record it as a prerequisite rather than claiming onboarding qualification again.
2. Confirm the intended user and workspace using the app's authenticated public status/profile surface. A dashboard heading alone cannot establish identity.
3. Sign out using the ordinary UI. Confirm the browser cannot continue to use protected app content and that the signed-out state has an actionable sign-in path. Do not demand server-wide JWT revocation unless that is an advertised contract; browser logout and token revocation are different claims.
4. Close the browser context and create a genuinely fresh context without copied cookies, storage or tokens. Visit a protected route and verify the expected authentication requirement rather than a stale success page.
5. Sign in through the normal UI with the same test account. Verify the same authoritative user/workspace, a usable authenticated destination and completed onboarding state. Capture authenticated status readback and confirm the wizard does not incorrectly restart.
6. Exercise one declared invalid/expired-session case without hours of waiting or production configuration changes. Use a supported isolated fixture or controlled negative injection, identify that seam explicitly, and verify the server rejects the invalid session and the UI gives a usable reauthentication path without an endless redirect/retry loop. Successful login must still use the ordinary UI.
7. Reauthenticate and confirm the same account/workspace is usable again. Confirm that the negative attempt did not create another user/workspace or imply new authority. Include a second local user's identity only if needed for a focused cross-user confusion twin.

This batch is complete when the positive return path and negative recovery are reproducible at the real browser/public API boundary, or the first failed transition is captured with a minimal diagnostic. It does not require all admin roles, provider connection, process restart, business calculation, password recovery or live identity-provider operation in the same batch.

Do not infer process restart from a browser reload. If later assigned process recovery, record the old/new process identities and prove durable state under the same job/resource identities. Keep that as its own declared extension.

## 5. Follow the actual user path

Use normal clicks, typing, selection, uploads and downloads. Do not force clicks through hidden/disabled controls, remove overlays in the DOM, set a success flag through JavaScript or call a private mutation instead of the promised UI action. Supported fixtures may prepare a declared prerequisite; they must not supply the expected result.

An API may confirm the durable result of a UI action. An API-only operation may qualify its HTTP contract when explicitly declared. Neither is silently upgraded into a browser journey. Capture which boundary each assertion exercises.

For each operation bind evidence to the exact returned request/run/job/resource/artifact identity. Avoid page-wide numbers, pre-mounted detail panels or an old result that happens to match. Verify reload/reopen against the same resource and, where required, a fresh backend session.

Prefer stable semantic selectors and test IDs. Inspect current labels and request contracts when a selector fails. Do not weaken an assertion to arbitrary visible text merely to avoid diagnosing a changed product surface.

Respect actual roles and permissions. A hidden button alone does not prove authorization. Where access is part of the journey, pair the UI state with the relevant public request under the same identity and verify zero unauthorized durable effect. Use documented isolated role fixtures; never broaden production permissions or promote the whole suite's users to admin.

## 6. Product outcome and usability rubric

| Question | Evidence to seek |
|---|---|
| Can the user discover and start the job? | Correct enabled entry, prerequisites and a valid ordinary interaction |
| Does the action do the promised work? | Actual request, authoritative result identity and durable result rather than a toast/200 alone |
| Is the result useful? | Current content, correct values/units/currency, understandable output and usable download/export where promised |
| Can the user understand a wait or failure? | Specific blocker, preserved completed work and a real next action |
| Does recovery preserve the job? | Same job/resource identity, retained useful receipts and no fabricated completion |
| Are permissions and scope truthful? | Correct role/workspace behavior and rejected unauthorized effects |
| Does the state survive the claimed return boundary? | Readback after reload, sign-in, fresh browser or process restart as actually declared |
| Are unsupported/deferred states honest? | Exact scoped limitation without representing the underlying feature as working |

Make severity proportional to user impact. Cross-scope disclosure/effect, false completion, duplicate irreversible work, unusable authentication or loss of durable results are urgent. Broken primary actions are functional failures. A changed heading may be a fixture issue. Visual polish should not displace a blocked business outcome unless it prevents use or materially misleads the user.

Report product and technical observations together: the user action, first failed transition, actual visible/network/state behavior, expected contract, impact and the smallest reproduction. Distinguish an observed cause from a hypothesis. A screenshot alone rarely explains a failed request or missing durable result.

## 7. Preserve evidence strength and privacy

Screenshots/page text show the visible state. Public request/response and authoritative readback show what happened. Preserve both when the user promise spans both. Inspect downloaded content as well as its hash; for formatted documents/presentations verify the relevant rendered output.

Never publish raw credentials, access/session tokens, OTPs, cookies, provisioning URIs, private production data or unredacted authorization headers. Record opaque test identities and safe request metadata. Inspect captured logs/artifacts before committing them. Redaction must preserve the fields required to understand the result without inventing evidence.

Provider acceptance is not recipient delivery. Search hits are not verified source content or complete population coverage. A parsed model proposal is not a business result. An uploaded document read is not the requested calculation. A local calculation is not an external write. Record controlled/doubled seams and all such limits beside the assertion.

Preserve the historical 111/123 functional result, its fixed denominator, separately tracked claims, original failures and accepted source/configuration boundaries. Do not lower the finish line, hide a feature or mark the entire app accepted based on this batch.

## 8. Continuous journey queue

After the first batch, select the highest-priority enabled, unqualified ordinary-user journey from the existing goal map, checking current ownership and evidence first. Ready examples include tasks/boards primary actions when actually enabled, supported source upload/search/open/export/reload, and a requested output's usable presentation. These are candidates to inspect, not claims that a failure is already reproduced.

Do not force-enable tasks/boards or a deferred workflow/integration surface to create work. Do not repeat completed episodes. If a candidate is already qualified on matching material, reuse the evidence and move on. If every remaining candidate requires missing authority or an unsupported environment, record those exact blockers instead of inventing busy work.

Keep one active journey and at most one prepared independent successor. While an implementation owner repairs a finding, verify another independent ready journey or the existing evidence package. Do not end each stage with “ready for the next phase” when local authorized verification remains.

The public workflow approval-scope repair belongs to Agent 1. Agent 2 owns its next mutation family. Agent 3 owns the merged-675 contract/integration review. Agent 4 may verify a completed successor through the UI when assigned, but must not shadow-edit their runtime or duplicate their active tests.

## 9. Handoff and engineering guidance

Use /private/tmp/brennan-brief/AGENT4.md for active ownership, source, first failed transition, evidence pointer and next action. Link one compact review artifact into the common handoff rather than creating competing readiness dashboards.

A failing handoff contains: exact source/build/profile/world/role; ordinary steps; request/result identity; safe network and browser evidence; durable readback; expected versus actual behavior; a minimal probe if useful; likely owning component; and a bounded validation plan with valid/negative twins.

Send the implementation owner the decisive observations and let it repair the shared mechanism. Suggested patterns should follow existing contracts: exact scope/material at claim time, durable receipt/readback, request-owned provenance/retry state and truthful completion. Do not propose a second router, review system or special-case domain workaround.

A passing handoff distinguishes independent observations from author/older evidence, lists controlled seams and recommends a bounded decision to the lead. The lead retains final acceptance, cross-app prioritization and product scope. Agent 4 does not post GitHub reviews/comments, request review, approve, close or merge PRs without applicable explicit authority.

## 10. Checkpoints and completion

Commit and push owned stable journey tests/probes and safe evidence on the agent's codex branch at coherent checkpoints. Stage exact owned paths, preserve other agents' files, verify the remote tip and do not force-push. A push is a delivery checkpoint, not a reason to stop before the next authorized step.

Freeze the executed candidate before collecting acceptance evidence. Source hashes bind to that source; artifact hashes bind to the evidence commit. Keep product, test-only and documentation successors distinct. Verify tracked bytes from Git, including ignored logs, before submission. Do not rewrite failed attempts or regenerate old logs to fit a manifest.

Pause only the action that needs new external authority, missing unrecoverable business information, destructive changes or an unavailable supported environment. Explain the exact boundary and continue unaffected work. No new provider/model campaign is authorized by this work order; serialize any separately authorized inference with its existing owner.

A batch is delivered when its user boundary is evidenced or its decisive failure is reproducible, owned tests/evidence are pushed, the lead receives a scoped recommendation and the next independent action is recorded. Final product acceptance remains with the lead. Whole-app readiness and deployment remain separate decisions.

Start with the fresh-browser account-return/session-recovery gap after checking for matching accepted evidence. Work through the finite batch, report to the lead and continue the next independent ready journey without routine phase-permission pauses.
