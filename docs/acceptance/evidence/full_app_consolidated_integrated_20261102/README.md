# Consolidated integrated candidate — oracle, evolution, taught artifacts, bookkeeping

Status: **submitted for independent verification; not self-accepted.**

This supersedes the `full_app_consolidated_20261102/` bundle, which was frozen
at `2b5db4b98` before the other agent's effect-family and bookkeeping commit
landed. Both bundles are preserved; this one is bound to the true integrated
source.

It is the integrator's verification superset of the owner's
`full_app_integrated_f8f8de387/` bundle for the **same** source: it adds the
454-test combined matrix, the actual `canvas_audit` duplicate counter, and the
pending-operation/payload identity comparison across restart. Both manifests
are tracked and hash-clean.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree used | `/private/tmp/atom-consolidated-clean` (isolated clean worktree) |
| Executed source | `f8f8de387bfb8979bf9e2d17779f71b53bcb982d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime identity | `source_id=f8f8de387bfb ... dirty=False` |
| Frontend build | `4LIiyOI205pK5RCpBKH87` |
| World | `/private/tmp/atom-consolidated-clean/backend/data/acceptance_worlds/full-app-consolidated-20261102` |
| Ports | API `8101`, frontend `3142` |
| Transport | controlled canvas + controlled Books; no live provider |

The world is a copy of the durable full-app world, relabelled for the clean
worktree. `books-state.json` is the controlled local provider state. The
bookkeeping run requires `ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS=1`,
`ATOM_BOOKS_CONTROLLED_TRANSPORT=1` and `ATOM_BOOKS_CONTROLLED_STATE`; these
are acceptance-only, environment-gated switches and were set explicitly.

## What is integrated

- **Accepted connected oracle + frozen requests** (`6d62855d0..0f9796401`,
  inventory `95454de7a`): before-dispatch deep request snapshots, canonical
  provider/operation/organization/target bindings, six connected verifiers,
  fail-closed readback.
- **Effect-family verifiers** (`f8f8de387`): canvas present markdown/chart,
  canvas update/restore, goal create/evaluate/decompose, goal-run start and
  task creation. The registry union is now **16** verifiers; the inventory is
  **6/6 external** and **9/9 local registered action mutations** covered.
- **One evolution lifecycle**: the parallel HITL candidate store is removed;
  tool failures feed `record_tool_error` → episode metadata → TaskEvent →
  ReflectionEngine → Memento `SkillCandidate` (pending, existing review API).
- **Taught artifacts**: receipt-derived deliverables, lessons resolved at
  assignment creation, applied-operation remote identity, canvas-audit
  postcondition.

## Journeys on this source

### Normal-app quote/service/exception — 17/17

Pending operation id and approval payload digest are identical across a real
restart (`cc…`/`442…` in earlier evidence; this run records its own), status
remains `awaiting_approval` with `remote_id=null`. The duplicate approval
returns `404`; the durable `canvas_audit` count for the action remote id
`d398c22a-88e4-47eb-94ee-359832d5b7b4` is **1 before and 1 after**. Quote
`350.00` (`f7ad5d27…`), service `630.00 CAD` (`5223416e…`), exception
`3 / 170.00` (`a4b235fb…`); all Georgia 18 with receipt provenance.

### Invoice → reviewed Books bill — 12/12

Real document-ingestion upload/extraction, normal assignment planning, vendor
and chart-of-accounts resolution, balanced proposal, restart with the same
pending approval, one approved `connected.books.create_bill`, authoritative
readback (`verification.status=verified`), provider effect count **1**, and
two duplicate controls that leave the create count at **1** (second assignment
step `failed` with a duplicate message).

## Tests

- Backend combined matrix (27 files): **454 passed** (`backend-tests.log`).
- Frontend canvas panels: **7 passed** (`frontend-tests.log`).
- Known pre-existing exclusion: `tests/test_task_lifecycle.py` has four
  retrieval-revision failures on the accepted successor branch and on this
  source; it is unrelated to this work and is not counted. It is not silently
  green.

## Remaining open

Whole-app HTTP/provider surfaces outside the action registry (827 mutating
routes, 311 provider-adapter writes) remain unqualified; TEAM-05's real LLM
sweep transport and MEM-07's approval/apply consumption; ORCH/GOAL model work,
MINI Linux/KVM, INT/ROUTE live authorization. No live action.

## Exclusions

- No live provider lookup, refresh, write, send, credential, consent or spend.
- No database reseed; the durable world was copied.
- Earlier evidence bundles and their manifests are unchanged.
- The 123-feature denominator and historical 111/123 are unchanged.
