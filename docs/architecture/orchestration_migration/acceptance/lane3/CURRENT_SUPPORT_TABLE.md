# CURRENT SUPPORT TABLE (2026-09-29) — FINAL

## The candidate
Commit **`79b2a41032c355d84dfd58229966d85a73a7d079`**, immutable export **`64b44f297617b050`**, world `cand_79b2a4103_preview`
(backend :8072, frontend :3160), planner pin `deepseek/deepseek-v4-pro` recorded in
`preview_stack.effective_flags`. Chain: `d78613777` (production fixes) → `05c38de54`
(zombie owner) → `43cbc434d` (recovery verdicts) → `79b2a41032c3` (psutil under the seatbelt).

Every row below is bound to one export. Results from different exports are never combined.

## Results on THIS candidate (`79b2a41032c3` / export `64b44f29`)
| Case | Track | Status |
|---|---|---|
| F11 effect-before-kill reconciliation | crash recovery | **PASS 7/7** |
| F12 read workflows (API) | read | **PASS 8/8** |
| F12B read workflows (real browser) | read | **PASS 8/8** |
| F06B real-browser edit (pinned) | browser edit | **Functional edit checks PASS; strict origin-isolation check FAILED** — the durable change, single operation-linked audit row, real-reload survival and truthful reply all passed; the failure is the disclosed Monaco-CDN load (condition 2 below). Kept visible as an exception, not absorbed into a pass count. |
| F06B negative control (unpinned) | browser edit | **PASS** — truthful decline, zero mutation |

## Historical supporting evidence — OLDER EXPORTS, retained but never merged into the rows above
| Case | Track | Status | Export it belongs to |
|---|---|---|---|
| F03 controlled synchronous edit | effect layer (shim) | PASS | `d78613777` |
| F04 controlled background success | effect layer (shim) | PASS | `d78613777` |
| F05 controlled background failure | effect layer (shim) | PASS | `d78613777` |
| F08 completion delivery / recovery | effect layer (shim) | PASS | `d78613777` |
| F09 overlap / duplicate terminal events | effect layer (shim) | PASS | `d78613777`, export `5d2bed16` |
| F10 keyed replay / payload conflict | transport | PASS | `d78613777` |
| F06/F07 real-planner browser edits (pinned) | browser edit | PASS | `f530c509948d947d` (candidate P, :8140/:3140) |
| F09 overlap PARTIAL | effect layer (shim) | retained | `3d557bb13` |
| F11 candidate-A restart survival | crash recovery | 6/6 | candidate A |

Retained, not merged: the rows above are evidence from their own exports only.

## Promotion decision: **PROMOTE, with two disclosed conditions**

Both cases that blocked the previous decision are resolved on this candidate, and the
browser path — the thing that was unexercised — now has first-party evidence on it:
a real Chromium session, a real login, a real composer, a real mutation attributable to an
operation id, and survival of a real reload. The negative control confirms the decline
path is honest and mutation-free.

Conditions, both disclosed rather than fixed:
1. **Editing works only under the disclosed pin.** With the unpinned default
   (`glm-5.3-flash`) the same browser edit declined — truthfully, with zero mutation.
   Promotion ships the pin.
2. **The canvas page loads Monaco from `cdn.jsdelivr.net`** (26 requests,
   recorded in the F06B run summary; no per-request capture was persisted).
   What the browser trace actually observed: all captured API and WebSocket
   traffic stayed on localhost origins (146 requests, 80 to the isolated
   backend, `foreign_origin_hits` empty). The CDN requests are separate: they
   necessarily transmit standard network information (client IP, user agent)
   and execute third-party-served JavaScript; their payloads were NOT
   captured, so no claim is made about what they carried — and the earlier
   "no data leaves" phrasing is withdrawn as unproven. Supply-chain/offline
   consideration; not repaired in this closeout.

## Standing limitations
- Provenance: the "16/16 byte-identical" claim was withdrawn and replaced by the
  measured **15/16**; `integrations.chat_orchestrator` differs by an env-gated
  `ATOM_ACCEPTANCE_BARRIER` hook and a `core.log_redaction` import. Inert unless armed.
- F02a remains **UNEXPLAINED**. PDF rendering remains fixed-but-unverified.
- The preserved `:3102` preview is untouched and still broken (no world database);
  it was not re-provisioned, and F12B used a fresh isolated candidate instead.
- The suite is order-dependent under `pytest-randomly` (pre-existing isolation debt);
  475 tests pass in fixed order.

Written 2026-09-28T23:37:57-0400.

## Addendum 2026-09-29 (auditor closeout) — fingerprint reconciliation and scope notes

Bind to the reconciliation section at the end of `FINISH_LINE_STATUS.md`; the
short form:

1. **The F09 automatic-recovery PASS (10/10, `f09_auto_recovery_0928/`) is
   export-bound to `80905c7bf1788d2b`** (a dirty-tree snapshot, base
   `79b2a41032c3`), NOT to this table's `64b44f297617b050`. Five product files
   differ between the two exports (`acceptance_barrier`,
   `async_turn_continuation`, `execution_ownership`, `execution_recovery`,
   `models` — the recovery path). A rerun of the five-fact scenario on
   `64b44f29` ends INVALID at the prerequisite gate, no kill: the
   `continuation_after_claim` test seam exists only in the uncommitted working
   tree. The recovery MECHANISM (lease table, recurring scan) is in the
   committed code. Treat the recovery pass as mechanism-matching SUPPORTING
   evidence; this candidate's export-bound crash evidence is F11 7/7 at the
   after-effect boundary.
2. The earlier "two duplicate notifications" observation is RESOLVED as two
   distinct continuations (one notification and one terminal row each); no
   defect.
3. The promotion preview was re-verified live 2026-09-29: :8072/:3160 up,
   health identity `79b2a41032c3`, `/login` 200, served module bytes equal to
   the `64b44f29` archive for six key modules. Advertised flows unchanged;
   claim-boundary crash recovery is NOT advertised on this export.
4. F02a UNEXPLAINED and F02c PENDING stand; the stale 2026-09-28 promotion
   table in `FINISH_LINE_STATUS.md` §10 is marked SUPERSEDED (rows retained).

## Manual preview handoff (immediate use — scoped, 2026-09-29)

**URL:** http://localhost:3160 (frontend) — isolated backend http://localhost:8072.
Verified live 2026-09-29 (health identity `79b2a41032c3`, `/login` 200, served
module bytes equal to the `64b44f29` archive). Do not restart it casually; it
is the promotion preview.

**Login (isolated):** next-auth CredentialsProvider. User `admin@example.com`;
the password is the world-local secret at
`backend/data/acceptance_worlds/cand_79b2a4103_preview/run_secrets/preview_auth.json`
(mode 0600 — read it locally; never copy it into tracked docs or tickets).
The F12B browser run performed this exact form login and landed on `/dashboard`.

**Supported actions (and nothing more):** general chat; the six recorded read
workflows incl. the named-file price lookup with cell-grounded citations
(F12B, real browser, 8/8); canvas editing under the disclosed pin
`deepseek/deepseek-v4-pro` (F06B; truthful zero-mutation decline on the
unpinned default). The first-run "Welcome to Atom" wizard must be dismissed
once; its scrim intercepts the composer.

**Excluded / limitations:** claim-boundary crash recovery is NOT supported on
this export (supporting evidence only, on `80905c7b`; the test seam is not in
the release source — see the next-writer item). Streaming, cross-host
execution, ranking/connector claims: excluded. F02a remains UNEXPLAINED;
F02c remains PENDING. Monaco loads from a public CDN (condition 2). The
preserved :3102 preview stays untouched and non-restartable.

## For the next writer — full recovery closure (single scoped step)

Add ONLY the existing confined claim-stage test seam to the intended release
source — the `continuation_after_claim` stage (+8 lines) in
`core/acceptance_barrier.py` and its one call site — NOT the working tree's
423-line `async_turn_continuation.py` rewrite, which must not be imported
merely to obtain the hook. Then freeze a new export, and rerun the five-fact
test (`f09_targeted_cases.py --phase 2`) against it. Until that lands,
claim-boundary recovery stays excluded from the preview exactly as stated
above.

## PRODUCTION ROLLOUT COMPLETE (2026-09-29, migrated to the normal app)

The verified configuration is **enabled and exercised in the normal dev app**
(`:3000`/`:8001`), not only in previews:

- **Code:** `main` through `0f0dd0889` (canvas-edit precedence fix `d84a42552`,
  env-docs fix `c647b0ca1`, acceptance harness + closeout package
  `29ab91bc4`). Released-line seam branch: `release/claim-stage-seam`
  (`658632c5`). Pushed to `origin`.
- **Enabled (backend/.env):** `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`,
  `ATOM_TASK_LIFECYCLE_ENABLED=1`. **M3 stays OFF** — explicit-rollout-only;
  its claim-boundary deferral behavior on the release line is not yet
  equivalent to the verified candidate (five-fact 7/10 on the seam export —
  boot delivers instead of deferring; see
  `original_workbook_email/RESULT_*.json` context and f09_auto_recovery_0928).
  Rollback: remove the three flag lines, re-run `scripts/restart_backend.sh`.
- **Effective-flag proof (serving process):** durable `=="1"`-gated artifacts
  after live turns — 3 lifecycle outcome records, 3 M1/M2 execution-bound
  messages, 3 keyed `chat_request_records`.
- **Flows verified in the normal app:** ordinary chat; the original eight-item
  workbook search against the real saved copy (all 8, exact order, honest
  ambiguity); formatting (no new retrieval); re-search (new attempt id, no
  mutation); and **the 8-row mixed-source draft edit LANDED** on a disposable
  quote clone (audit exactly +1, truthful terminal, reload persisted).
- **Known boundaries (recorded, not hidden):** the canvas panel's Send button
  is overlaid by the ATOM Assistant launcher at some viewport sizes and Enter
  does not submit there (UI defect — programmatic click works); the
  task-scope guard refuses edits whose scope does not match the session's
  retained task (honest, by design; no cross-canvas path yet); the unpinned
  default planner declines clear edits (the pin is the supported editing
  config); one undetermined backend process death (restarted per procedure).
- **Editing is supported under the disclosed pin** `deepseek/deepseek-v4-pro`.
  The email was never sent. F02a remains UNEXPLAINED; F02c PENDING.
