# Canvas lifecycle authority reconciliation — 2026-11-17

**Documentation accuracy correction only.** This page corrects current-tense
wording in two navigation documents. It is not a score, not a new acceptance
campaign, not whole Goal 14 or whole-app ORACLE acceptance, and not a claim about
every Canvas route, family or caller.

## The mismatch this fixes

The [current goal map](CURRENT_GOAL_MAP_2026_11_17.md) and the
[November 14 readiness index](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md)
still described four Canvas delete/undelete scope failures as **current**. They
were real at their recorded baseline, but the repair has been in main since
2026-11-07, so the current-tense wording was stale.

| Question | Answer |
|---|---|
| Were the four failures real? | **Yes, at their baseline.** Four mounted-route controls on the `27a1830a2` backend accepted a former legitimate coeditor after the actor's tenant or workspace moved, returning 200 and appending an effect. |
| Are they still current defects? | **No.** Repair PR [#763](https://github.com/rush86999/atom/pull/763) merged `c97dada13`, which is an ancestor of the current application source `ecce2df80`. |
| Is the whole Canvas/ORACLE family closed? | **No.** The proof is bounded to the mounted delete/undelete lifecycle consumer and its controls. Other Canvas routes, other mutation families and whole-app ORACLE stay open. |
| Does this change any score or audit row? | **No.** 143 claim identities, 18 goals, the historical 111/123 (90.2%) result and `app_complete: false` are untouched. |

## Authority chain

| Step | Source | What it is |
|---|---|---|
| 1. Original negative | `27a1830a2` (2026-11-07) | Nine portable mounted-route controls: 4 expected-refusal failures, 5 compatibility passes. Packet: [canvas lifecycle scope negative](evidence/canvas_lifecycle_scope_negative_27a1830a2/README.md). |
| 2. Scope repair | `8e4b494d7` | First repair of the scope gate; lead packet `canvas_lifecycle_lead_8e4b494d7` (9/31/175 checks). |
| 3. Successor negative | `a981` (backend byte-equal to `8e4`) | Independent actor interleavings moved workspace or deactivated the actor after real preflight; 4 failed, 2 valid twins passed. Preserved unchanged. |
| 4. Runtime repair | `ccaa92ba3` | Current active `User` row becomes authority; frozen identity re-checked in the writer; exact guarded no-op `User` update in the same transaction as the lifecycle CAS/audit. |
| 5. Permanent tests | `19bd74ade` | Native and root scope/actor controls promoted into the normal backend selection; packet `canvas_lifecycle_actor_lead_ccaa92ba3`. |
| 6. Merge | PR [#763](https://github.com/rush86999/atom/pull/763) → `c97dada13` | Squash merge into main. Confirmed ancestor of current application source `ecce2df80`. |
| 7. Current bounded rerun | application source `ecce2df80` | 54 passed at actual current-main Canvas product and test bytes. |

## Current bounded result

Actual public root receipt:
`/private/tmp/atom-root-canvas-current-scope-adjudication-20261117.json`
(public root artifact; its raw log was not re-read for this documentation pass).

- **Command:** `python -m pytest -q tests/test_canvas_lifecycle_verified.py tests/test_lead_canvas_lifecycle_authority.py`
- **Result:** 54 passed. The two permanent modules are `backend/tests/test_canvas_lifecycle_verified.py`
  (native, 37 collected) and `backend/tests/test_lead_canvas_lifecycle_authority.py`
  (root scope/actor, 17 collected).
- **Application source:** `ecce2df80` — the same Canvas product and test bytes as the
  application source adjudicated by root (`canvas_product_and_tests_exact_main: true`).
- **Executed tree head:** `c029470c0`. It is `ecce2df80` plus CI-only
  `--durations=20` reporting flags: five flag lines in `.github/workflows/ci.yml`
  and five mirrored across `backend/tests/fixtures/ci_backend_additions.json` and
  `backend/tests/fixtures/ci_backend_before_parallel.json` (8 changed lines, 3 files).
  A `git diff c029470c0 ecce2df80` over the Canvas product, Oracle verifier,
  MCP service, models, scope helper, CRUD tool and both test modules is empty.
- **Auth boundary:** the mounted routes **inject `get_current_user`** as an explicit
  dependency override. Real `User`/`Canvas`/`Audit` rows, real writers, the scoped
  service, fresh-session Oracle readback and real conditional writes are exercised;
  normal login, session/token issuance and browser flows are **not**.
- **Scope:** mounted real router plus real writer/service/SQLite durable readback on
  a fresh FK-enforced scratch database. Includes the four foreign tenant/workspace
  coeditor delete/undelete refusals, current-actor interleavings before claim,
  unchanged active-actor twins, replay/idempotency, material/operation conflicts,
  `committed_unverified`/`effect_unknown` outcomes and tool-path context authority.
- **Not executed for this pass:** no fresh full server launch, no browser, no
  PostgreSQL/multiworker/soak run, no provider or model call, no new test authored,
  no CI job triggered.

## What the 54 controls do and do not establish

They establish that this bounded delete/undelete lifecycle consumer refuses a
former coeditor whose **current** tenant or workspace no longer permits the
operation, that the refusal happens before any append or broadcast, and that the
compatibility cases (owner, same-scope coeditor, Personal NULL/default, audit-only
canvas) still commit with exact prior/source identity and independent readback.

They do **not** establish:

- every Canvas route or Canvas family (Goal 5 remains open beyond its recorded
  browser slices);
- every caller of canvas mutation, or the legacy direct-tool path with
  `scope_required=False`;
- whole-app ORACLE, Goal 14 completion, postcondition enforcement on other
  mutation families, or a refreshed runtime inventory of reachable routes;
- security, SSO/login, browser, PostgreSQL concurrency, multiworker or soak
  behavior;
- that the historical four failures did not happen. They happened and stay
  recorded.

## Historical records preserved

Nothing below was rewritten, hashed over, or relabelled:

- `docs/engineering/evidence/canvas_lifecycle_scope_negative_27a1830a2/` — the
  original 4-fail/5-pass baseline, its probe, runner, log, spec and exit bytes.
- `docs/acceptance/evidence/canvas_lifecycle_lead_8e4b494d7/` — the scope-repair
  lead packet, including `baseline-portable-4fail5pass`.
- `docs/acceptance/evidence/canvas_lifecycle_actor_lead_ccaa92ba3/` — the actor
  interleaving negative plus the runtime and permanent-test record.
- The retained affected-suite result **175 passed / 2 failed**, with the same two
  pre-existing failure IDs on the main-equivalent baseline. The 54 checks do not
  hide them.
- The original audit JSON, claim IDs, denominators, negative captures and
  historical scores are untouched.

Correction rule for future readers: cite the historical four failures only as
**historical baseline evidence**, with the baseline source, and cite the repair
merge plus the bounded current controls separately. A bounded 54-check pass is not
a reason to credit all Canvas work, Goal 5, Goal 14 or the whole app.

## Linked records

- [Current goal map — 2026-11-17](CURRENT_GOAL_MAP_2026_11_17.md)
- [Current readiness evidence index — 2026-11-14](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md)
- [Canvas lifecycle work order — 2026-11-07](CANVAS_LIFECYCLE_WORKORDER_2026_11_07.md)
- [Original scope negative packet](evidence/canvas_lifecycle_scope_negative_27a1830a2/README.md)
- [Actor/authority lead packet](../acceptance/evidence/canvas_lifecycle_actor_lead_ccaa92ba3/README.md)
- [Scope-repair lead packet](../acceptance/evidence/canvas_lifecycle_lead_8e4b494d7/README.md)
- [Bounded current result record](evidence/canvas_lifecycle_authority_20261117/result.json)

## Validation basis

- Base: exact main `ecce2df80` in the local checkout; `git merge-base --is-ancestor
  c97dada13 HEAD` succeeded.
- The delta between the executed tree head `c029470c0` and `ecce2df80` is restricted
  to the three CI files listed above.
- File-level checks: both test modules are byte-identical to the permanent modules
  recorded in the `ccaa92ba3` packet (`5dcc4974…`, `58d4a242…`); product files have
  legitimately advanced through later merged work, which is why the rerun at
  `ecce2df80` bytes is the current evidence rather than the older packet.
- Changed-file links in this pass resolve; no product, CI, policy, schema,
  dependency or test file was modified by this correction.
