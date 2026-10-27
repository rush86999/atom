# Atom core-release readiness ledger — 2026-10-27

Candidate: `f5f3148d24351217b20e4994fe7602131f8ae220` (tree `d5804aed4be4a920a2c6067c253efc7f89cc539f`), branch `whole-app/successor-f5f`.

Generated: 2026-10-27T23:44:07.356485+00:00

Supersedes `WHOLE_APP_READINESS_LEDGER_2026-10-27` for launch scope. The whole-app ledger remains history. Product decision: `docs/acceptance/CORE_RELEASE_SCOPE_2026-10-27.md`.

Machine-readable source: `docs/acceptance/CORE_RELEASE_LEDGER_2026-10-27.json`.

## Summary

| Status | Count |
|---|---|
| deferred_scope | 47 |
| environment_limited | 2 |
| failed | 2 |
| not_authorized | 1 |
| partial | 12 |
| unproven | 2 |
| verified | 44 |

**Core release ready: no.** The core surface is configured and browser-enforced, and the domain-independent calculation/decision contracts pass. The trained-employee loop, deliverable formats and the production build remain open; deferred surfaces are an explicit product decision, not failures.

## Items

| ID | Area | Action | Status | First failed transition | Next action |
|---|---|---|---|---|---|
| WA-001 | candidate | Verify the frozen candidate identity and package manifest still match | **verified** | — | — |
| WA-002 | candidate | Run the packaged pre-restart acceptance checks | **verified** | — | — |
| WA-003 | candidate | Restart the packaged candidate and run the post-restart checks | **verified** | — | — |
| WA-004 | candidate | Resume the interrupted partial probe | **partial** | The preserved probe did not complete its resume transition. | Keep as partial; do not count it toward whole-app acceptance. |
| WA-005 | deployment | Run the f5f3148d2 launcher read-only preflight | **verified** | — | — |
| WA-006 | deployment | Try to pass an ae0c2fda3 package through the f5f launcher | **verified** | — | — |
| WA-007 | deployment | Try to apply with the old approval token | **verified** | — | — |
| WA-008 | deployment | Exercise scoped stop and automatic code rollback on a fake release | **verified** | — | — |
| WA-009 | deployment | Cut over the live pilot to f5f3148d2 | **not_authorized** | — | Obtain explicit authorization; previous ae0c2fda3 authorization does not transfer. |
| WA-010 | auth | Sign in with email/password and land on the dashboard | **verified** | — | — |
| WA-011 | auth | Reload a deep page and keep the authenticated session | **verified** | — | — |
| WA-012 | auth | Verify a member does not see Approvals or the admin band after role resolution | **verified** | — | — |
| WA-013 | auth | Navigate a member directly to an admin URL | **partial** | The page renders an admin shell for a member instead of a clean denied state; backend correctly denies the data. | Add a page-level 403 state (or redirect) so direct links do not render an empty admin surface. |
| WA-014 | auth | Open JIT Verification and Business Facts as workspace_admin | **verified** | — | — |
| WA-015 | tasks | Create, list, update, and delete a task through /api/v1/tasks | **deferred_scope** | — | Task tracking is deferred; work and results stay in Activity. |
| WA-016 | tasks | Reload and restart the backend, then list the task | **deferred_scope** | — | Task tracking is deferred; work and results stay in Activity. |
| WA-017 | tasks | Create a task while the create endpoint is unavailable | **deferred_scope** | — | Task tracking is deferred; work and results stay in Activity. |
| WA-018 | boards | Create a board and open its detail page | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-019 | boards | Add a task to a board column and reload | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-020 | boards | Post a comment on a board task and reload it | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-021 | boards | Commit a decomposition proposal into child tasks | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-022 | boards | Generate subtask proposals from a task | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-023 | workflows | Create a visual workflow and confirm it is listed after reload | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-024 | workflows | Execute a deterministic failing workflow | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-025 | workflows | Restart the backend and re-read the failed execution | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-026 | workflows | Execute a normal workflow end-to-end | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-027 | workflows | Schedule a workflow, list jobs, remove the job | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-028 | workflows | Wait for a scheduled workflow to fire and record an execution | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-029 | workflows | Pause a workflow on a governance denial and resume it after approval | **deferred_scope** | — | Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work. |
| WA-030 | approvals | List pending HITL actions as the admin | **verified** | — | — |
| WA-031 | approvals | Approve a held goal-run decision through the generic Approvals page/API | **verified** | — | — |
| WA-032 | approvals | Reject a held goal-run decision with guidance | **verified** | — | — |
| WA-033 | approvals | Resume a run through its own endpoint and re-check the generic queue | **verified** | — | — |
| WA-034 | background | Create a supervisor goal run and read it back | **verified** | — | — |
| WA-035 | background | Reach a human_checkpoint step and resolve it | **environment_limited** | Without an LLM the router returns an unusable decision, so execution never reaches the checkpoint step. | Run the checkpoint transition with a configured model or a scripted router stub. |
| WA-036 | background | Restart the backend after a held decision and read the run | **verified** | — | — |
| WA-037 | background | Resume an interrupted chat turn after restart | **partial** | The preserved probe did not complete its resume transition. | Do not rescore; keep the partial probe visible. |
| WA-038 | documents | Upload a text file and find its content by search | **verified** | — | — |
| WA-039 | documents | Upload a Word document and find its content by search | **verified** | — | — |
| WA-040 | documents | Upload a PowerPoint deck and find its slide text by search | **verified** | — | — |
| WA-041 | documents | Upload .doc, .ppt, .rtf, or .odt without docling | **verified** | — | — |
| WA-042 | documents | Upload PDF and Markdown files | **partial** | Not executed in this world. | Upload one PDF and one MD and assert extracted text and search hits. |
| WA-043 | documents | Reload the Documents page and list the uploaded files | **verified** | — | — |
| WA-044 | chat | Send a text turn and reload history | **verified** | — | — |
| WA-045 | canvas | Create a canvas artifact, edit it, reload | **unproven** | Render only. | Run the existing canvas journey against this world or reuse the packaged J5 evidence. |
| WA-046 | search | Search memory/documents and inspect results | **deferred_scope** | — | Unified search is deferred; document search remains in Data. |
| WA-047 | agents | Open the Agents page and read the maturity ladder | **partial** | No agent run/training transition executed (LLM). | Use the existing trained-review evidence for the AI slice; add one non-LLM agent-list assertion. |
| WA-048 | automations | Use the Automations tabs and workflow surface | **verified** | — | — |
| WA-049 | marketplace | Browse the marketplace catalog | **deferred_scope** | — | Marketplace is deferred; agents are created and taught in Agents. |
| WA-050 | command-centers | Open Projects and read its data | **verified** | — | — |
| WA-051 | command-centers | Open Sales & CRM and read its data | **verified** | — | — |
| WA-052 | command-centers | Open Support and read its data | **verified** | — | — |
| WA-053 | command-centers | Open Knowledge and read its data | **verified** | — | — |
| WA-054 | command-centers | Open Communication and read its data | **verified** | — | — |
| WA-055 | business | Open the Sales page and read leads | **deferred_scope** | — | Business dashboards are deferred; business rules come from teaching. |
| WA-056 | business | Open Marketing and load the summary | **deferred_scope** | — | Business dashboards are deferred; business rules come from teaching. |
| WA-057 | business | Open Finance and read its data | **deferred_scope** | — | Business dashboards are deferred; business rules come from teaching. |
| WA-058 | business | Open Analytics and read KPI cards | **deferred_scope** | — | Business dashboards are deferred; business rules come from teaching. |
| WA-059 | productivity | Open Calendar and read events | **deferred_scope** | — | Calendar/health/voice are deferred. |
| WA-060 | productivity | Open Health and read business-health/risk cards | **deferred_scope** | — | Calendar/health/voice are deferred. |
| WA-061 | productivity | Open Voice and check readiness | **deferred_scope** | — | Calendar/health/voice are deferred. |
| WA-062 | governance | Read JIT cache/worker metrics as workspace_admin | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-063 | governance | Open BPE Workspace | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-064 | governance | Open Learning & Verification | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-065 | governance | List business facts as workspace_admin | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-066 | governance | List users as workspace_admin | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-067 | governance | Open runtime settings | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-068 | governance | Open the audit trail and read a decision | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-069 | governance | Open the skill editor | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-070 | governance | Open the owner cockpit and read priorities | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-071 | governance | Open Forensics and read vendor/pricing/waste panels | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-072 | governance | Open Dev Studio | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-073 | platform | Browse the integration catalog | **deferred_scope** | — | Broad connector management is deferred; provider keys stay in Settings. |
| WA-074 | platform | Open Integration Data and list integrations | **deferred_scope** | — | Broad connector management is deferred; provider keys stay in Settings. |
| WA-075 | platform | Open Account/AI/Sessions/Routing/Local Models settings | **partial** | No setting was saved and reloaded. | Save and restore one preference per tab. |
| WA-076 | platform | Open System Status and read the aggregate | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-077 | platform | Open Scheduling and list events | **deferred_scope** | — | Calendar/health/voice are deferred. |
| WA-078 | platform | Open Team Chat | **deferred_scope** | — | Team chat is deferred. |
| WA-079 | platform | Block an API route and inspect the page's error state | **unproven** | Not executed. | Abort /api/v1/tasks and /api/boards and assert a durable error/retry state, not a blank page. |
| WA-080 | platform | Run a clean-machine install from the documented quickstart | **environment_limited** | A clean install on this host would need python3.11; installing dependencies was not run (no spending/network install authorized). | Run scripts/quickstart.sh in a disposable clone with python3.11 and assert health + login. |
| WA-081 | platform | Restart the isolated backend and verify data survival | **verified** | — | — |
| WA-082 | platform | Connect and sync a real external account | **deferred_scope** | — | Broad connector management is deferred; provider keys stay in Settings. |
| WA-083 | auth | Call same-origin API paths that rely on the auth cookie | **verified** | — | — |
| WA-084 | platform | Call API paths that had no explicit Next rewrite | **deferred_scope** | — | Deferred platform surface (connectors/team chat/system status). |
| WA-085 | boards | Open the Kanban board WebSocket with a valid token | **deferred_scope** | — | Kanban is deferred; task definitions live in the accepted task. |
| WA-086 | platform | Read the marketing dashboard after startup schema repair | **deferred_scope** | — | Deferred platform surface (connectors/team chat/system status). |
| WA-087 | platform | Read /api/status and /api/services/registry from the System Status page | **deferred_scope** | — | Deferred platform surface (connectors/team chat/system status). |
| WA-088 | platform | List and revoke sessions from Settings > Sessions | **deferred_scope** | — | Deferred platform surface (connectors/team chat/system status). |
| WA-089 | governance | Open Dev Studio and read the WhatsApp health card | **deferred_scope** | — | Admin/governance/self-healing tools are deferred from the core release. |
| WA-090 | breadth | Visit every sidebar route plus key orphan routes as workspace_admin | **partial** | Most core-profile route visits land on the explicit NotInRelease scope page; the full-profile spot check exposes them cleanly. | Run the full 56-route breadth under the full profile after the product-scope decision, and add the 3 remaining direct-admin/member checks. |
| WA-091 | breadth | Visit every sidebar route plus key orphan routes as a member | **partial** | The member run overlapped backend restarts (transient 500s) and the earlier sidebar failed open during role loading; the sidebar now hides elevated items while the role loads. | Run the member breadth again on the full profile after the scope decision; core-profile direct admin links intentionally land on NotInRelease. |
| CR-001 | surface | Serve /api/product/profile and use it for navigation, dashboard links and direct-page access | **verified** | — | — |
| CR-002 | surface | Open each deferred route directly and confirm the explicit scope page | **verified** | — | — |
| CR-003 | surface | Assert the core profile disables autonomous scheduling, external ingestion sync and agent evolution by default | **verified** | — | — |
| CR-004 | calculation | Run line_total, sum and count through the same provenance/gap discipline, without a quantity x price assumption | **verified** | — | — |
| CR-005 | trained-agent | Accept decisions from the accepted task in three unrelated domains and reject a decision outside the taught set | **verified** | — | — |
| CR-006 | trained-agent | Accept codes, references and human labels as review subjects; no fixed ID regex | **verified** | — | — |
| CR-007 | data | Upload an .eml file and preserve participants, date, subject, body and attachment names | **partial** | The .eml upload has not been exercised through the browser and a durable document row on this successor. | Upload a representative .eml through Data, search its body, and reload. |
| CR-008 | trained-agent | Teach through chat or the canvas Training tab; inspect, edit and delete teaching points; keep global/goal scope | **partial** | The click path through the Training tab was not exercised; the API teach path and restart persistence were. | Run the same teach/correct/delete actions through the rendered UI. |
| CR-009 | trained-agent | Teach through the UI, run an unfamiliar task, inspect deliverable/sources, correct, run a different task, restart, verify scoped persistence | **failed** | Two green assessments produced correct boundary decisions (grants 3200/5000/10000/12000; renamed cases 3200/5000/10000) with source/policy attribution, but the post-restart repeat produced no valid block. Reliability across restart is not green. | Bind the model's task-defined decisions to the deterministic subjects, validate them with build_review_result, render the final table from the validated components, then repeat teach -> unfamiliar task -> correct -> different task -> restart. |
| CR-012 | calculation | When a deterministic file read computes rows, the delivered answer must cite those rows and not a model-written table that contradicts them | **verified** | — | — |
| CR-013 | calculation | List named columns for rows matching a condition in a named table (list Application Ref and Requested Amount for Submitted rows) | **verified** | — | Promote after the browser UI check of the same ask. |
| CR-014 | trained-agent | Use deterministic subjects/facts, accept only task-defined decisions from the model, validate subject/evidence/policy references and render the final table | **partial** | Post-restart generation was not reliable: the same renamed assessment that passed before restart produced no valid block. Judgment on the green runs was correct (all boundary cases). | Make the newest policy authoritative in generation (e.g. a single current policy) and rerun; the structural pipeline is green. |
| CR-016 | trained-agent | Selection -> structured review artifact -> one generation -> subject/evidence/policy validation -> table joined to authoritative rows | **verified** | — | — |
| CR-015 | calculation | A selection turn completes only with a bound source, resolved columns, predicate, row references and delivery | **verified** | — | — |
| CR-017 | trained-agent | Give every selectable policy ID its applicable instruction text in the review prompt; same policy index for generation and validation | **verified** | — | — |
| CR-018 | background | After a validated review, settle only the read obligations it satisfied; keep genuine freshness obligations; leave an incomplete review's work open | **verified** | — | A stale 'Still needed' history row created before settlement remains as history; new continuations must reflect the settled state. |
| CR-019 | trained-agent | Repeat a previously green assessment after a real restart and require a validated decision table | **failed** | The model did not emit a valid review block after restart; no decisions were certified. | Measure the post-restart generation failure (provider/context/format) before changing the loop; do not keep repeating unchanged requests. |
| CR-010 | workspace | Produce and reopen an email draft, document, calculated table and presentation in Workspace | **partial** | No browser deliverable check for email/presentation on this successor. | Create one of each in Workspace, reopen after reload and verify content survives. |
| CR-011 | release | Build the shipping frontend and run the core browser breadth against that build | **verified** | — | — |

Status meanings: `verified` = executed end-to-end on the named candidate/config; `failed` = reproduced failure at the user-visible boundary; `partial` = an early transition passed, a later one did not; `unproven` = no candidate-bound execution; `environment_limited` = needs credentials/a worker this world intentionally disables; `blocked_external` = needs a real external account; `not_authorized` = would deploy/spend/contact outside the sandbox; `deferred_scope` = excluded by the product decision, not a failure.
