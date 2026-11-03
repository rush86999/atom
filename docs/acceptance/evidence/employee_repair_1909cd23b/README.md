# Employee evidence-strength and patch-invariant repair

Status: **submitted for independent verification; the served adaptive
two-domain campaign (G5 level 2) is not claimed.**

This successor closes the five contract failures on the Batch A/B core. It
also tracks the four previously untracked Batch B log artifacts and preserves
the old manifests as historical records.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `1909cd23b` (full SHA in `MANIFEST.json`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

## Repairs

1. **Verified receipts.** `require=verified` now demands explicit verified
   proof bound to the operation/resource/subject/version/sha, with no missing,
   mismatched, conflicting or refuted fields and complete non-truncated
   coverage. Empty results, weaker statuses and free-form evidence remain
   unknown. `require` accepts only `applied|verified`.
2. **Provider acceptance vs Sent Items.** Provider acceptance no longer sets
   `sent_record_confirmed` or recipient delivery. Sent Items requires its own
   correlated readback; mismatch is false, absent readback is unknown.
3. **Complete affected closure.** A patch computes the full downstream
   closure first and checks every affected step and durable operation. A
   running/uncertain descendant makes the patch refuse without clearing its
   operation_id, result, prior history, grant or provider effect.
4. **Authoritative task state version.** `base_task_version` is the lifecycle
   `record.task_version`, not `task_revision.revision` (the objective
   revision). The CAS callback rechecks it after duplicate identity; a fact/
   teaching/authority change that advances task_version without changing
   plan_revision refuses the old patch. Producers and tests use task_version;
   missing/ambiguous versions require refresh.
5. **Patch identity conflict.** A canonical material digest is stored in a
   durable `patch_registry` beside the bounded display history. Same ID and
   same material replay the first result; same ID with different material
   conflicts; concurrent duplicate adoption returns one applied and one
   already_applied; restart replay remains idempotent.

Additional guards: required steps cannot be removed by a model patch;
requirements cannot be erased/weakened; established facts require accepted
source refs or authored confirmation; registered mutating adapters cannot be
relabelled read-only; added actions are checked against accepted authority.

## Results

| Scope | Result |
|---|---|
| Integrated backend neighborhood | **675 passed**, 8 known WebSocket tests deselected |
| Frontend assignment/goal/approval surfaces | **54 passed** |
| G0 + verified-receipt/Sent Items probes | **9 passed** |
| Patch invariants | **7 passed** |
| Deterministic two-domain campaign | **4 passed** |
| Focused affected suites | **203 passed** |

The deterministic two-domain campaign covers industrial quote adaptation and
procurement/bookkeeping reconciliation on the same lifecycle/readiness/patch/
outcome mechanisms. It is **not** a served-model adaptive claim.

## Evidence repair

The four Batch B logs previously absent from Git are now tracked:
`backend-integrated.log`, `frontend-integrated.log`,
`patch-adaptation-controls.log`, `verifier-boundary-probes.log`. The old
manifests remain historical; this bundle is the successor evidence.

## Boundaries

- No served model adaptive choice on held-out content/event ordering.
- No operating/provider qualification or two-domain model campaign.
- No live provider lookup/write/send/credential/consent/spend/reseed/deploy.
- Existing planner 5/5, goal router 1/2, alignment gap 3.0 and historical
  111/123 remain unchanged.
