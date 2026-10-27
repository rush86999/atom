# Atom whole-app readiness ledger — 2026-10-27

Candidate: `f5f3148d24351217b20e4994fe7602131f8ae220` (tree `d5804aed4be4a920a2c6067c253efc7f89cc539f`), branch `whole-app/successor-f5f`.

Generated: 2026-10-27T20:13:42Z

Machine-readable source: `docs/acceptance/WHOLE_APP_READINESS_LEDGER_2026-10-27.json`.

## Summary

| Status | Count |
|---|---|
| verified | 60 |
| failed | 1 |
| partial | 12 |
| unproven | 11 |
| environment_limited | 4 |
| blocked_external | 1 |
| not_authorized | 1 |

**Whole-app ready: no.** Task/board CRUD, comments/decompose, workflow create/execute/schedule, approval resume/reject, background durability, document formats, auth/proxy, role visibility and several mounted-router repairs pass. Remaining: settings/sessions, PDF/MD, network-failure UX, clean install, workflow governance pause and scheduled firing. An uncommitted core-profile scope gate found in the dirty worktree is not in f5f and was excluded; if merged it would defer 11 capabilities without the required product decision. The 56-route admin breadth and targeted re-checks were captured with the surfaces exposed, before that gate was introduced.

## Concurrent uncommitted work (excluded)

The dirty worktree contains an uncommitted product-profile gate that is **not in f5f3148d2**:

- `backend/core/product_profile.py`, `backend/api/product_profile_routes.py`, `frontend-nextjs/lib/product-profile.tsx`, `frontend-nextjs/components/ProductSurface/NotInRelease.tsx`, `frontend-nextjs/pages/_app.tsx`
- Effect: A core profile that defers search, tasks, boards, automations, marketplace, command centers, business dashboards, productivity, governance, connectors and team chat.
- Disposition: Excluded from this evidence branch and this commit. The assignment requires an explicit product decision before any launch-scope reduction; this gate has none. It also was not present in f5f3148d2. Paths may exist in f5f; the listed paths are the dirty-worktree additions/diffs, not a claim that this branch contains the gate.

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
| WA-015 | tasks | Create, list, update, and delete a task through /api/v1/tasks | **verified** | — | — |
| WA-016 | tasks | Reload and restart the backend, then list the task | **verified** | — | — |
| WA-017 | tasks | Create a task while the create endpoint is unavailable | **verified** | — | — |
| WA-018 | boards | Create a board and open its detail page | **verified** | — | — |
| WA-019 | boards | Add a task to a board column and reload | **verified** | — | — |
| WA-020 | boards | Post a comment on a board task and reload it | **verified** | — | — |
| WA-021 | boards | Commit a decomposition proposal into child tasks | **verified** | — | — |
| WA-022 | boards | Generate subtask proposals from a task | **environment_limited** | No LLM credentials are present in the isolated world by constraint. | Run the proposal step in the preserved candidate environment with a configured provider, or with a local model. |
| WA-023 | workflows | Create a visual workflow and confirm it is listed after reload | **verified** | — | — |
| WA-024 | workflows | Execute a deterministic failing workflow | **verified** | — | — |
| WA-025 | workflows | Restart the backend and re-read the failed execution | **verified** | — | — |
| WA-026 | workflows | Execute a normal workflow end-to-end | **verified** | — | — |
| WA-027 | workflows | Schedule a workflow, list jobs, remove the job | **verified** | — | — |
| WA-028 | workflows | Wait for a scheduled workflow to fire and record an execution | **environment_limited** | The scheduler is intentionally stopped to prevent external pollers; jobs created while stopped are tentative. | Start a scheduler-enabled isolated backend (credentials stripped, integrations tokenless) and wait for one interval. |
| WA-029 | workflows | Pause a workflow on a governance denial and resume it after approval | **unproven** | No governance-denied workflow execution was created in this world (needs a registry agent below the action's maturity tier). | Create a workflow bound to a low-maturity agent and a critical step; approve through /api/agents/approvals and assert the execution moves out of PAUSED. |
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
| WA-046 | search | Search memory/documents and inspect results | **partial** | The unified Search page's own query was not executed. | Run one unified search query with a known document hit. |
| WA-047 | agents | Open the Agents page and read the maturity ladder | **partial** | No agent run/training transition executed (LLM). | Use the existing trained-review evidence for the AI slice; add one non-LLM agent-list assertion. |
| WA-048 | automations | Use the Automations tabs and workflow surface | **verified** | — | — |
| WA-049 | marketplace | Browse the marketplace catalog | **unproven** | Render only. | Install/preview one marketplace item in the isolated world. |
| WA-050 | command-centers | Open Projects and read its data | **verified** | — | — |
| WA-051 | command-centers | Open Sales & CRM and read its data | **verified** | — | — |
| WA-052 | command-centers | Open Support and read its data | **verified** | — | — |
| WA-053 | command-centers | Open Knowledge and read its data | **verified** | — | — |
| WA-054 | command-centers | Open Communication and read its data | **verified** | — | — |
| WA-055 | business | Open the Sales page and read leads | **verified** | — | — |
| WA-056 | business | Open Marketing and load the summary | **verified** | — | — |
| WA-057 | business | Open Finance and read its data | **unproven** | Render only; no financial action executed. | Read one finance summary endpoint and assert non-error. |
| WA-058 | business | Open Analytics and read KPI cards | **verified** | — | — |
| WA-059 | productivity | Open Calendar and read events | **verified** | — | — |
| WA-060 | productivity | Open Health and read business-health/risk cards | **partial** | GET /api/business-health/interventions/generate is 403 for workspace_admin. | Decide the role gate for intervention generation; keep it read-only or grant it to workspace_admin. |
| WA-061 | productivity | Open Voice and check readiness | **unproven** | No microphone/voice turn executed. | Run a voice readiness check in a real browser with microphone permission. |
| WA-062 | governance | Read JIT cache/worker metrics as workspace_admin | **verified** | — | — |
| WA-063 | governance | Open BPE Workspace | **unproven** | Render only. | Execute one BPE workspace read/update. |
| WA-064 | governance | Open Learning & Verification | **unproven** | Render only. | Execute one verification action. |
| WA-065 | governance | List business facts as workspace_admin | **verified** | — | — |
| WA-066 | governance | List users as workspace_admin | **verified** | — | — |
| WA-067 | governance | Open runtime settings | **unproven** | No setting was changed. | Change and restore one harmless setting. |
| WA-068 | governance | Open the audit trail and read a decision | **partial** | The member direct page shows an error state rather than a clean 'supervisor required' state. | Gate the page at the route level and show a clear denied state. |
| WA-069 | governance | Open the skill editor | **unproven** | No skill created. | Create and delete a no-op skill. |
| WA-070 | governance | Open the owner cockpit and read priorities | **verified** | — | — |
| WA-071 | governance | Open Forensics and read vendor/pricing/waste panels | **verified** | — | — |
| WA-072 | governance | Open Dev Studio | **partial** | A panel assumes WhatsApp health; unconfigured is reported as 503. | Treat unconfigured optional integrations as 'not connected', not an error. |
| WA-073 | platform | Browse the integration catalog | **verified** | — | — |
| WA-074 | platform | Open Integration Data and list integrations | **verified** | — | — |
| WA-075 | platform | Open Account/AI/Sessions/Routing/Local Models settings | **partial** | No setting was saved and reloaded. | Save and restore one preference per tab. |
| WA-076 | platform | Open System Status and read the aggregate | **verified** | — | — |
| WA-077 | platform | Open Scheduling and list events | **verified** | — | — |
| WA-078 | platform | Open Team Chat | **unproven** | No message sent. | Send one message between two isolated users. |
| WA-079 | platform | Block an API route and inspect the page's error state | **unproven** | Not executed. | Abort /api/v1/tasks and /api/boards and assert a durable error/retry state, not a blank page. |
| WA-080 | platform | Run a clean-machine install from the documented quickstart | **environment_limited** | A clean install on this host would need python3.11; installing dependencies was not run (no spending/network install authorized). | Run scripts/quickstart.sh in a disposable clone with python3.11 and assert health + login. |
| WA-081 | platform | Restart the isolated backend and verify data survival | **verified** | — | — |
| WA-082 | platform | Connect and sync a real external account | **blocked_external** | Requires real credentials and external communication. | Covered by the preserved candidate smoke only where it used scratch credentials; do not initiate live external traffic without authorization. |
| WA-083 | auth | Call same-origin API paths that rely on the auth cookie | **verified** | — | — |
| WA-084 | platform | Call API paths that had no explicit Next rewrite | **verified** | — | — |
| WA-085 | boards | Open the Kanban board WebSocket with a valid token | **verified** | — | — |
| WA-086 | platform | Read the marketing dashboard after startup schema repair | **verified** | — | — |
| WA-087 | platform | Read /api/status and /api/services/registry from the System Status page | **verified** | — | — |
| WA-088 | platform | List and revoke sessions from Settings > Sessions | **failed** | The page calls /api/auth/sessions, which NextAuth's catch-all answers 401; the real backend surface is /api/users/sessions with a different body/path contract. | Add a pages/api/auth/sessions.ts adapter (or repoint and adapt the page) and test list/revoke/revoke-all. |
| WA-089 | breadth | Visit every sidebar route plus key orphan routes as workspace_admin | **partial** | First pass found 8 route-level API issues (401/404/500/403). Shared-cause repairs and targeted re-checks removed the tested ones; the concurrent uncommitted profile gate later made some shared-worktree routes show NotInRelease, but it is excluded from this branch. | Repeat the 56-route breadth on this clean branch without the concurrent gate or backend restarts, and add the 3 remaining direct-admin/member checks. |
| WA-090 | breadth | Visit every sidebar route plus key orphan routes as a member | **partial** | The member run overlapped backend restarts (transient 500s) and the earlier sidebar failed open during role loading; the sidebar now hides elevated items while the role loads and role visibility passes at 500ms/1.5s/4s. | Repeat the member breadth on this clean branch without restart overlap; direct admin links still need a page-level denied state in the full surface. |

Status meanings: `verified` = Executed end-to-end on the named candidate/config; the stated user-visible action succeeded.; `failed` = Reproduced failure at the boundary the user touches.; `partial` = An early transition passed; the named later transition did not.; `unproven` = Rendered or existed, but the action was not executed; no candidate-bound pass.; `environment_limited` = Cannot execute without credentials or a scheduler this isolated world intentionally disables. Not a pass.; `blocked_external` = Needs a real external account or communication; outside this run's constraints.; `not_authorized` = Would deploy, spend, or contact outside the sandbox; no authorization.
