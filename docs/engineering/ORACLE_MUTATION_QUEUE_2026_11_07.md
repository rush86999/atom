# ORACLE mutation queue — current-main static reconciliation (2026-11-07)

Status: **read-only static inventory and finite work order preparation. Not a
qualification run, not an acceptance, not a merge.** All 143 claim dispositions
remain with the root audit; whole-app ORACLE-01 remains open.

Evidence cut: remote `origin/main` = `8ded00232c30961a990e675e06ec672ef6a43910`
(PR #754 merge). Audit head `33a9b541a` is docs-only on top of `8ded`; the code
tree is unchanged. The selected candidate source is the same `8ded` code.

## 1. Original canonical inventory is preserved, not overwritten

The 2026-11-02 inventory remains the canonical initial denominator at its
recorded source:

| Field | Original value |
|---|---|
| Inventory commit | `95454de7a` |
| Recorded code source | `0f9796401` |
| `inventory.json` blob | `6d9734dfa3b1f5b98af4a691ce3eafb0c5c4cefd` |
| README blob | `3f09abc08b27957f2fbdd74cccdaf95f1e3e7522` |
| Mutating HTTP routes | **827** |
| High-risk route names/paths | **366** |
| Provider-adapter write methods | **311** |
| Registered actions (runtime import at that source) | **90** |
| External mutations | 6 total / 6 covered |
| Local mutations | 9 total / 1 covered |

This packet does **not** rewrite that JSON or its README. The new counts below
are a separate static re-derivation at current main.

## 2. Current-main static re-derivation

Method: the existing AST rules from
`scripts/acceptance/oracle_mutation_surface_inventory.py` were replayed over
Git objects with a read-only stdlib scanner (`docs/engineering/probes/`), without
checking out `backend/`, importing the app, starting a server, or touching a DB.
The same rules reproduce the original 827 / 366 / 311 exactly at `0f9796401`,
which validates the method before applying it to current main.

| Surface | Original `0f9796401` | Current `8ded00232` | Delta |
|---|---:|---:|---:|
| Mutating HTTP route declarations | 827 | **836** | **+9** |
| High-risk route names/paths | 366 | **371** | **+5** |
| Provider-adapter write methods | 311 | **311** | **0** |
| POST | 711 | 718 | +7 |
| PUT | 40 | 41 | +1 |
| DELETE | 61 | 62 | +1 |
| PATCH | 15 | 15 | 0 |

Added routes (all source-bound, none removed):

| Method | Route | Handler | File |
|---|---|---|---|
| POST | `/{agent_id}/jobs/{job_id}/answer` | `answer_agent_job_information_wait` | `backend/api/agent_routes.py` |
| POST | `/{run_id}/sources` | `add_assignment_source` | `backend/api/assignment_routes.py` |
| POST | `/{run_id}/advance` | `advance_assignment` | `backend/api/assignment_routes.py` |
| POST | `/{run_id}/budget` | `extend_assignment_budget` | `backend/api/assignment_routes.py` |
| POST | `/{run_id}/patch` | `patch_assignment_plan` | `backend/api/assignment_routes.py` |
| POST | `/from-objective` | `start_employee_objective` | `backend/api/assignment_routes.py` |
| POST | `/skills/{candidate_id}/apply` | `apply_skill_candidate` | `backend/api/autodev_review_routes.py` |
| PUT | `/{goal_id}/utility` | `set_goal_utility` | `backend/api/goal_routes.py` |
| DELETE | `/{goal_id}/utility` | `clear_goal_utility` | `backend/api/goal_routes.py` |

High-risk additions are the five assignment routes above. Provider write methods
did not change. No route was removed.

**Boundary:** this is a declaration-surface denominator. It is not mounted-route
proof, not runtime reachability, not effect proof and not coverage acceptance.
The earlier reachable map required a live OpenAPI server; this run intentionally
did not start one.

## 3. Registered-action coverage

Two different snapshots matter and must not be conflated:

| Snapshot | Source | Actions | Mutations | Covered | Uncovered |
|---|---|---:|---:|---:|---:|
| Original inventory | `0f9796401` / `95454de7a` | 90 | 15 declared by its own classification (6 external + 9 local) | 7 (6 external + 1 local) | 8 recorded by that packet |
| PR #757 executed snapshot | `90eac34a7` (head `7d4ca4d7d`) | **98** | **30** | **27** | **3** |
| Current remote main | `8ded00232` / `33a9b541a` | **98** | **30** | **26** | **4** |

PR #757 / `90eac34a7` uncovered: `mini_app_run`, `workspace.commit`,
`workspace.note`. **Submitted, not merged.**

Current main uncovered: `mini_app_run`, `radio.create_thread`,
`workspace.commit`, `workspace.note`.

The difference is exactly the PR #757 radio verifier:
`radio.create_thread` is a registered action on main but has no verifier until
the submitted `radio_thread_mutations` packet lands. The static comparison
shows **no action added/removed and no effect-declaration change** between
`90eac34a7` and current main; only that verifier registration differs. This is a
`submitted_not_merged` distinction, not a main regression and not a runtime
failure claim.

The lazy `core.agent_radio.radio_actions` and `core.bpe.actions` modules account
for 8 of the 98 actions. The original 90-action inventory imported only
`core.action_registry` + `core.connected_actions`, so its 90 is consistent with
the 98 tree count; it is not evidence that 8 actions disappeared.

`docs/acceptance/evidence/oracle_registry_coverage_20261107/` (source
`bb807d62d`) reports the older 90 / 26 / 15 / 11 shape. It predates the lazy
modules and later verifier registrations and is **not** the current snapshot.
The `90eac34a7` snapshot above is the one to compare against current main.

## 4. Classification vocabulary

- `covered_bounded` — a recorded bounded family has accepted/merged evidence for
  the exact action or route set; it never implies whole-family or whole-app
  coverage.
- `submitted_not_merged` — evidence or a PR exists but is `REVIEW_REQUIRED` or
  otherwise not merged into current main.
- `unqualified` — no accepted or submitted bounded evidence was found for the
  exact reachable family at current main.
- `live_authority` — qualification needs a real account/provider authority
  (OAuth, send, connect/disconnect/refresh, external write) that this static run
  did not exercise.
- `environment_limited` — needs PostgreSQL, multi-worker, KVM/Firecracker,
  browser, soak or another environment not present in this run.
- `deferred_profile` — outside the single-user Personal Edition profile and not
  the next finite work.

## 5. Prioritized queue

P0 is the selected canvas lifecycle candidate. “Routes” are static declarations,
not proof of reachability.

| P | Family | Category | Static routes | Why it is here | Next finite action |
|---|---|---|---|---:|---|
| P0 | `canvas.lifecycle.delete_undelete` | `unqualified` | 2 | Direct DELETE/undelete bypass the accepted PUT/restore scope + oracle service; no verifier, operation identity or scope check. | Run the bounded work order in `CANVAS_LIFECYCLE_WORKORDER_2026_11_07.md`. |
| P1 | `assignment.delta_20261107` | `unqualified` | 5 | Five post-inventory assignment routes (`sources`, `advance`, `budget`, `patch`, `from-objective`) are high-risk additions with no matching inventory-family packet. | Trace one route’s authority/CAS/receipt, then qualify or keep out of assignment dispatch. |
| P1 | `agent.jobs.answer` | `submitted_not_merged` | 1 | `POST /{agent_id}/jobs/{job_id}/answer` is on main; TASK-WAIT-01 remains open and the relevant PRs are review-required. | Use the TASK-WAIT-01 order; do not create a second wait engine. |
| P1 | `autodev.skill_apply` | `unqualified` | 1 | `POST /skills/{candidate_id}/apply` is new; the evolution-review packet covers decision routes, not this apply route. | Trace candidate/authority/readback and decide whether it belongs to the existing review family. |
| P2 | `goal.utility` | `covered_bounded` | 2 | PR #754 merged deterministic target/ranking and scoped reads; ordinary Goal Runs browser journey remains unrun. | WO-GOAL-UI-03, not this packet. |
| P2 | `canvas.capability` | `submitted_not_merged` for receipt/assign/teaching subset; `unqualified` for manifest/bind/select/export/edit/assess remainder | 16 | `canvas_assignment_batch_20261102` is submitted at its source; the file also contains routes outside that packet. | Read the packet’s exact route list before qualifying any subset; do not claim the whole file. |
| P2 | `canvas.pdf` | `unqualified` | 18 | PDF mutation routes (pages/merge/redact/sign/form/archive/docusign) have no whole-family oracle packet at this cut. | Trace one high-risk PDF lifecycle route after the canvas lifecycle order. |
| P2 | `canvas.email.draft_attachments` | `unqualified` | 9 | Draft/message/attachment/categorize routes bypass a shared postcondition; send is separate. | Separate from live send; trace save-draft/attachment authority and readback. |
| P2 | `canvas.email.live_send` | `live_authority` | 1 | `POST /send` requires a live provider/account and send authority; not exercised here. | Owner environment decision; no send in this campaign. |
| P2 | `canvas.sheets/docs/coding/terminal` | `unqualified` | 13 | Typed-canvas content routes exist outside the accepted direct PUT/restore slice. | Pick one typed route with a real caller; reuse `canvas.update` mechanics where possible. |
| P2 | `office.file_canvas` | `unqualified` | 11 | Office file→canvas and snapshot routes write canvas/file state; only `deleted_canvas_ids` read-side protection is visible. | Trace one office write route; no browser/office file material in this run. |
| P2 | `mini_app.host_writes` | `covered_bounded` | 18 | Host-side mini-app producer/verifier evidence exists for the supported subset. | Do not re-run unchanged blobs; use the existing packet. |
| P2 | `mini_app.run` | `unqualified` | 1 action + route family | `mini_app_run` is one of the four current-main uncovered declared mutations. | Qualify or keep out of mutating assignment dispatch. |
| P3 | `provider.connected_and_shopify_create` | `covered_bounded` | 311 write methods total; bounded subset | Six connected estimate/bill/draft actions and four Shopify create actions have recorded verifiers; the rest do not. | Use the merged packets; do not treat this as provider breadth. |
| P3 | `provider.live_connect_send_refresh` | `live_authority` | subset of 311 | OAuth/connect/disconnect/refresh/send require live authority. | Owner decision; no account/provider action in this campaign. |
| P3 | `provider.non_core_integrations` | `deferred_profile` | subset of 311 | Trello/Dropbox/Asana/Telegram/etc. are outside the single-user pilot next slice. | Defer; no breadth campaign. |
| P3 | `merged_bounded_misc` | `covered_bounded` | various | Audit records merged bounded families for document settings, memory write, skill review, evolution review, workflow template, marketplace, chat/fork, agent delete/run/replace/stop, knowledge-document deletion and direct HTTP canvas PUT/restore. | Do not re-open without contrary evidence; no duplicate engines. |
| P3 | `postgres_multiwriter_soak` | `environment_limited` | n/a | SQLite CAS and single-process evidence do not qualify PostgreSQL/multi-worker/soak. | Separate COMPAT-03 environment order. |
| P3 | `installation_profile` | `deferred_profile` | n/a | Install/backup/restore/rollback/restart is its own profile order. | Separate MINI/installation order. |

## 6. Selected candidate: canvas delete/undelete

The candidate is real and reachable in the declared source:

- HTTP `DELETE /api/canvas/{canvas_id}` → `api.canvas_routes.delete_canvas`
  (`backend/api/canvas_routes.py:797`) → `tools.canvas_crud_tool.delete_canvas`.
- HTTP `POST /api/canvas/{canvas_id}/undelete` →
  `api.canvas_routes.undelete_canvas` (`backend/api/canvas_routes.py:813`) →
  `tools.canvas_crud_tool.restore_deleted_canvas`.
- Parallel registered-tool consumers: `tools.registry` manually registers
  `delete_canvas` (`backend/tools/registry.py:751`) and auto-discovers the public
  async `restore_deleted_canvas` through `discover_tools`. Both reach the same
  writers. No `canvas.delete` / `canvas.undelete` action exists in
  `core.action_registry`.

Static contract gap (hypothesis, not proven runtime failure):

1. Both routes pass only `user_id` + `canvas_id`. They do not call
   `canvas_write_scope_error` and do not pass the principal's tenant/workspace.
   `_verify_canvas_owner` accepts the creator **or any non-`submit` audit
   author**. That is the existing co-editor/owner policy and must be preserved,
   but it is not a tenant/workspace check.
2. Delete/undelete have no server-owned operation identity, no expected-prior
   CAS, no postcondition verifier and no durable readback. A duplicate HTTP
   delete returns `already_deleted` without the original tombstone id; a second
   undelete returns “Canvas is not deleted”.
3. `delete_canvas`/`restore_deleted_canvas` order the latest row by
   `created_at` only, unlike update/restore/list which also use `id` as a
   tiebreak. Existing µs bumping reduces but does not remove legacy tie risk.
4. Undelete copies the newest non-delete row’s details, strips operation
   identity/evidence/postconditions, and records only
   `restored_from_delete=True`. It returns no `audit_id`, operation id, content
   digest or source-row identity.
5. The registered-tool path can receive a model-supplied `user_id` argument;
   `mcp_service.execute_tool` does not strip it (it only strips `user_id` for
   `operator_*`). That is a hypothesis to probe, not a runtime finding.

The accepted PUT/restore slice at
`docs/acceptance/evidence/oracle01_direct_canvas_82ac9681a_atomic_scope/`
covers **only** `PUT /api/canvas/{canvas_id}` and
`POST /api/canvas/{canvas_id}/restore`; its own `routes.json` lists “other canvas
routes” as not covered. This packet does not re-open those acceptances.

The bounded design and probe matrix are in
`docs/engineering/CANVAS_LIFECYCLE_WORKORDER_2026_11_07.md` and
`docs/engineering/probes/canvas_lifecycle_probe_2026_11_07.py`.

## 7. Exact inputs and read-back commands

All refs are Git objects; no whole backend was materialized.

```sh
# Current code and docs-only audit head
git -C /private/tmp/atom-current-claim-audit-20261107 rev-parse origin/main
# 8ded00232c30961a990e675e06ec672ef6a43910
git -C /private/tmp/atom-current-claim-audit-20261107 rev-parse 33a9b541a
# docs-only on 8ded; code diff is empty

# Original inventory and its recorded source
git -C /private/tmp/atom-current-claim-audit-20261107 show \
  95454de7a:docs/acceptance/evidence/oracle_whole_app_inventory_20261102/inventory.json
git -C /private/tmp/atom-current-claim-audit-20261107 rev-parse \
  95454de7a:docs/acceptance/evidence/oracle_whole_app_inventory_20261102/inventory.json
# 6d9734dfa3b1f5b98af4a691ce3eafb0c5c4cefd

# Submitted PR #757 snapshot (not merged)
git -C /private/tmp/atom-current-claim-audit-20261107 show \
  90eac34a7:docs/acceptance/evidence/oracle_radio_mcp_replay_90eac34a7/registry-counts.json
# 98 actions / 30 mutations / 27 covered / 3 uncovered

# Canvas lifecycle source
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/api/canvas_routes.py
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/tools/canvas_crud_tool.py
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/core/canvas_write_service.py
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/core/oracle/postcondition_verifiers.py
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/tools/registry.py
git -C /private/tmp/atom-current-claim-audit-20261107 show origin/main:backend/integrations/mcp_service.py

# Reproduce the static delta (read-only; no app import/server/DB)
python3 docs/engineering/probes/oracle_mutation_inventory_static_2026_11_07.py \
  0f9796401 origin/main /tmp/atom-oracle-delta
python3 docs/engineering/probes/oracle_registry_static_2026_11_07.py \
  0f9796401 origin/main /tmp/atom-oracle-delta
python3 docs/engineering/probes/oracle_registry_static_2026_11_07.py \
  90eac34a7 origin/main /tmp/atom-oracle-delta-pr757
```

Source blobs read at `origin/main`:

| File | Blob |
|---|---|
| `backend/api/canvas_routes.py` | `a27c3ca6446fb8d675ad096582d34e02b3f55949` |
| `backend/tools/canvas_crud_tool.py` | `07d1a107228a53850025d11c6c79d5a4919778e5` |
| `backend/core/canvas_write_service.py` | `f5425d67f04ee3654ecd39806d0224be2a368590` |
| `backend/core/oracle/postcondition_verifiers.py` | `b011e2bc788b3442d470b0a87f887b1b07954d8c` |
| `backend/core/oracle/request_expectations.py` | `131b53d7f4b25a703888f80d8a36c8e755f1e231` |
| `backend/core/models.py` | `403113778fb29099df4f60d1780367b22906def2` |
| `backend/core/action_registry.py` | `a5461ed3267c915027763857bb3a09286da9f224` |
| `backend/core/connected_actions.py` | `3c6a611c804648ac573415106d9223fbf780809f` |
| `backend/core/agent_radio/radio_actions.py` | `9b92ff68773d765a3d8068cf1b9789830258812c` |
| `backend/core/bpe/actions.py` | `4c170ed61edebe4682fbe65b95bce2bbd7124943` |
| `backend/tools/registry.py` | `68d38564849d78253c4e9d7b25245db578402621` |
| `backend/integrations/mcp_service.py` | `811e953df8261ef6c20568dbae1413895271873f` |
| `backend/core/deployment_audience.py` | `7bc92a952fa86a0539bb5a9822101441b7c88c98` |
| `backend/core/personal_scope.py` | `ed530e39585f6ed0d2fcbcaeb79e4d51dc62f9a9` |
| `frontend-nextjs/pages/canvas/index.tsx` | `403a169b99215f126f933110ed49f8083def7a3a` |

## 8. What this packet does not do

- It does not rewrite the 143-claim audit, scores, historical evidence or any
  accepted packet.
- It does not run tests, import the app, start a server, use a browser, call a
  model/provider, touch a live DB, install/download, send, spend, deploy, merge
  or post review comments.
- It does not close ORACLE-01. It supplies a current denominator, a machine
  delta and one finite next family.
- It does not treat the 836/371/311 static counts as runtime qualification.
