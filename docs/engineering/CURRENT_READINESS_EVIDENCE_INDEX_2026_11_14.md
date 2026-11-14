# Current readiness evidence index — 2026-11-14

**Status: navigation and evidence reconciliation only. Not a new score, not a
completion claim, and not a replacement for the original records.**

This index reconciles the original 18 app goals and all 143 original README
claims against the repository state at the requested base
`b4370d0d41ae6e9e5a280387d1230a80c82e14a7` (`#937`, tree
`73cccebaebf01a42dd854158d5e39de30563ca1f`) and records the immediately
following merge `a868435fdcc7be66753366362d7542cc1082ce84` (`#943`, tree
`90966fcad598f2789f522118ab668e038e608db1`), which advanced `origin/main`
during this pass. It preserves the historical denominator and score exactly:
**143 claim identities, 18 goal rows, 111/123 functional (90.2%),
`app_complete: false`**. No claim is re-scored, no goal is renumbered and no
bounded test is promoted to whole-goal or whole-app completion.

- Branch: `codex/readiness-evidence-index`, based on `b4370d0d4`.
- Evidence cut: 2026-11-14, Toronto. The repository was read from local Git
  history; no remote fetch, CI query, product run, model call, credential
  access or dependency install was performed by this documentation worker. A
  concurrent process fetched `origin/main` at 09:40 local time; that fetch is
  the source of the `#943` identity recorded here.
- Current main observed: `a868435fd` (`#943`), a direct child of
  `b4370d0d4` (`#937`). `#943` was still a draft at the start of this pass and
  merged during it. Both the requested base and the observed merge are stated
  explicitly so neither is mistaken for the other.
- Private evidence paths are recorded where the exact retained artifact is
  outside the repository. They are not committed and are not independently
  re-verified by this pass.

## Read this first

| Question | Answer |
|---|---|
| Did the denominator shrink? | **No.** 143 original claims remain: 123 functional + 20 separately tracked. |
| Was the score recomputed? | **No.** Historical functional result remains **111/123 (90.2%)**. |
| Were goals renumbered? | **No.** The canonical 18-goal catalogue is unchanged; historical 12-row numbering is crosswalked below. |
| Is the app complete? | **No.** `app_complete: false` is preserved. |
| Is current main merged? | Yes through `a868435fd` (`#943`). Drafts `#919` and `#932` are **not** main. `#943` was draft at task start and merged during this pass. |
| Is every original goal now verified? | **No.** Several goals remain open, unverified, environment-limited, external-blocked or bounded to narrow evidence. |
| Can bounded tests be counted as whole-goal acceptance? | **No.** They are evidence at a named source and scope only. |
| Is the 48-hour Goal 10 wait ready? | **No.** It is not due before **2026-11-16T06:42:25.414033Z**. |

## Contents

- [Canonical 18 goals and historical numbering](#1-canonical-18-goals--do-not-renumber)
- [Merged source and open drafts](#3-current-merged-source-and-open-drafts)
- Goals: [1](#goal-1) · [2](#goal-2) · [3](#goal-3) · [4](#goal-4) · [5](#goal-5) · [6](#goal-6) · [7](#goal-7) · [8](#goal-8) · [9](#goal-9) · [10](#goal-10) · [11](#goal-11) · [12](#goal-12) · [13](#goal-13) · [14](#goal-14) · [15](#goal-15) · [16](#goal-16) · [17](#goal-17) · [18](#goal-18)
- [All 143 claim rows](#5-claim-register--all-143-original-claims)
- [Remaining user-boundary acceptance](#6-remaining-user-boundary-acceptance--ranked)
- [Historical negatives](#7-historical-negatives-and-retained-failures)
- [Missing evidence](#8-unresolved-or-missing-evidence--stated-plainly)
- [Original audit links](#9-ledger-relationships-and-original-audit-links)

## Source identities and status vocabulary

| Term | Exact meaning in this index |
|---|---|
| `audit` | `docs/engineering/APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json` — the 143-claim record, including each claim's historical evidence array and gap. |
| `audit-preserved` | The historical claim result is retained at its original source. This index did not re-run it and did not promote it. |
| `bounded` | An independent decision accepted a narrower mechanism/source scope. It is not full claim completion. |
| `merged` | The named commit is in local first-parent history ending at the observed `origin/main` `a868435fd`. Merge identity does not widen the tested scope. |
| `draft` | A branch/commit exists but is not an ancestor of observed main `a868435fd`. No main qualification is implied. |
| `retained-private` | A named artifact outside Git. Exact path recorded; not committed or re-verified here. |
| `handoff` | A dated entry in `/private/tmp/brennan-brief/READINESS_CURRENT_MAIN.md`. Used for appended status and private-run summaries where no committed packet exists. |
| `missing` | No exact retained source was found for the assertion in this pass. The assertion is left open. |
| `not re-run` | An earlier source-bound result exists, but current main was not executed for it. |

Two rules govern the rest of the document:

1. **Newest appended evidence supersedes stale PR status, but never a prior
   failure at its original source.** A merged status can correct “draft/open”
   wording. It cannot erase a recorded failed run, a preserved
   counterexample, or the original negative scope.
2. **Merged, green CI, a passing unit test, a controlled model, a loopback
   transport, a scratch world or a component render is never whole-app
   acceptance.** Each row states the source and the remaining user boundary.

## 1. Canonical 18 goals — do not renumber

The canonical catalogue is
[`APP_GOALS_INDEX.json`](APP_GOALS_INDEX.json) → `goal_catalog`. These numbers
are used throughout this document.

| # | Canonical goal |
|---:|---|
| 1 | Setup and ordinary account use |
| 2 | BYOK and suitable model selection |
| 3 | Authorized common data and search |
| 4 | Spreadsheet and calculation |
| 5 | Canvas and editable outputs |
| 6 | Teaching and reusable agent capability |
| 7 | Assessment and unfamiliar work |
| 8 | Durable employee objectives |
| 9 | Runtime configured-budget enforcement |
| 10 | TASK-WAIT-01 long tasks pause/resume |
| 11 | Documents, presentations and email drafts |
| 12 | Repeatable workflows and schedules |
| 13 | Fleet, goals and background work |
| 14 | Direct mutations and whole-app ORACLE |
| 15 | Remaining exposed application |
| 16 | Installation, compatibility and operations |
| 17 | Performance and comparative promises |
| 18 | Profile breadth |

## 2. Historical numbering reconciliation

Several retained ledgers use different numbering. They are not
interchangeable.

| Record | What it counts | Why it is not this index |
|---|---|---|
| [`WHOLE_APP_READINESS_LEDGER_2026-10-27.md`](../acceptance/WHOLE_APP_READINESS_LEDGER_2026-10-27.md) | 91 operational `WA-*` checklist items on candidate `f5f3148d2` | A whole-app operational ledger, not the 143 README claims. Its recorded counts are 61 verified, 1 failed, 13 partial, 10 unproven, 4 environment-limited, 1 blocked-external, 1 not-authorized. It is historical and does not override current main. |
| [`PRODUCT_GOAL_LEDGER_2026-10-29.md`](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md) | 12 product-action rows (current as of 2026-10-31) | A 12-row product ledger, not the 18-goal catalogue. The old row numbers must not be quoted as canonical goal numbers. |
| [`CLAIM_INVENTORY.json`](../acceptance/readme_feature_readiness_2026-11-01/CLAIM_INVENTORY.json) | 143 README claims, 123 functional + 20 separate, 111/123 | The frozen historical claim denominator and score. |
| [`APP_GOALS_INDEX.json`](APP_GOALS_INDEX.json) | 18 goal rows plus explicit user requirements | The canonical goal catalogue. Goal rows are not added to the 143 claim count. |
| This index | Current evidence overlay for the same 18 goals and 143 claims | Navigation only; no new denominator and no new score. |

### 2.1 The 12-row ledger → canonical goals

| 12-row ledger row | Its actual subject | Canonical goal(s) | Common misread |
|---:|---|---|---|
| 1 | Create/select an employee, teach, start work, complete the same job in another domain | 6, 7, 8 | Not a single canonical goal. |
| 2 | Teach method, exception, qualification, period, conflict, correction, transfer | 6 | **Not** canonical 2 (BYOK). |
| 3 | Resolve unfamiliar columns/units, confirm/correct mapping, resume | 7 | Not canonical 3 (common data/search). |
| 4 | Upload/connect authorized data and retrieve it | 3 | — |
| 5 | Multi-sheet workbook ingest, formulas, calculation, citations | 4 | — |
| 6 | Create/bind/edit/export/reload a user canvas | 5 | — |
| 7 | Grounded selection, calculation and assessment with citations | 7 | — |
| 8 | Editable DOCX/PPTX and email draft | 11 | **Not** canonical 8 (durable objectives). |
| 9 | User canvases inherit supported capabilities | 5 | — |
| 10 | Long-running multi-source assignment, restart, delayed response, cancellation | 8, 10 | Not canonical 10 alone. |
| 11 | Approval binds exact payload/artifact; duplicate approval is inert | 14, 15 | **Not** canonical 11 (documents/email). |
| 12 | Install/start, sign in, use workspace, restart/recover | 1, 16 | **Not** canonical 12 (workflows/schedules). |

Two concrete corrections follow from this table:

- The old “Goal 12” label on the dashboard Canvas 405 defect was wrong.
  Canvas belongs to canonical **5 / 15**, while canonical 12 is repeatable
  workflows and schedules.
- “Goal 10” in an old long-running-assignment note can mean the 12-row
  long-running row (canonical **8 + 10**), not only canonical 10
  (`TASK-WAIT-01`). This index uses canonical 8 for durable objectives and
  canonical 10 for the wait/resume requirement.

## 3. Current merged source and open drafts

### 3.1 Merged on current main (through `a868435fd`)

The following commits are in local first-parent history ending at the observed
`origin/main` `a868435fd`. “Merged” refers to that Git fact only. CI and live
acceptance status are separately scoped. The requested base was `b4370d0d4`;
`#943` is the one later merge observed during this pass.

| PR | Merge commit | Current-main scope | Goal(s) | Evidence binding |
|---:|---|---|---|---|
| #943 | `a868435fd` | Native menu bar sign-in, session restore, logout, 2FA and chat wiring | 1, 16 | Merged tree differs from reviewed draft `5d1f11de4` only by `#937`'s two skill files. Native login/relaunch/logout/2FA evidence is bound to the draft head and its sanitized packet; public-API live Go chat passed at the reviewed head (see the verifier update below); native UI chat remains unverified. |
| #926 | `1c00a72fc` | Accept unslashed `GET /api/canvas`; Canvas list dashboard path | 5, 15 | Post-merge signed-in replay 22/22 at `6ad2738ed`; `retained-private` result `/private/tmp/canvas-926-postmerge-20261113_221126/evidence/result.json`; initial browser proof was at PR head `7d3e2bfc4`. |
| #927 | `d12d68b86` | Test-only quote term binding repair | 4 | No product change; merged test repair. Do not count as product capability. |
| #928 | `b39cc2982` | Source-grounded quote discounts | 4 | Module/compiler changes merged; no ordinary served-model or live-source proof in this pass. |
| #929 | `bbf08de05` | Assignment count measure/unit handling | 4 | Test and executor changes merged; no ordinary served-model proof in this pass. |
| #930 | `67ad1df80` | Cross-sheet workbook population | 4 | Synthetic 24-sheet full-population replay passed on merged main `6ad2738ed` (1 passed, 8.14s); five focused tests passed at `ea4a0a952`; source `/private/tmp/atom-main-fullpop.Q5pZMN/results/full-population-result.json`. |
| #931 | `6ad2738ed` | Offline Canvas editor assets and WA-045 docs/ledger edits | 5, 15 | WA-045 browser replay 32/32 at `6ad2738ed`; `retained-private` `/private/tmp/atom-main-canvas.W1hk5v/evidence/canvas-blank-lifecycle.json`. Full Canvas D2 remains open. |
| #934 | `58c1f44f5` | Fleet recruitment, launch binding and crash recovery | 13 | Merged tree exactly equals tested `5dadad938` (tree `a3a7c8460d16`). Live response completeness remains open. |
| #935 | `a53b56fdc` | Fleet specialist findings, synthesis and receipt/dispatch evidence | 13 | Merged tree exactly equals reviewed `fcc129444` (tree `666d2688258d`). Private frozen live replay and focused tests are recorded in the handoff; no current-main re-run after `#935`. |
| #936 | `d1e3ddac8` | Local quickstart auth URLs and private configuration creation | 1, 16 | Merged quickstart script matches reviewed head `f7bf3d4f60`; macOS Python 3.12 clean install/restore/rollback evidence is recorded in the handoff; native/KVM/PostgreSQL remain open. |
| #938 | `471494e5d` | Hosted CI selection of document delete truth | 3, 14 | `ci.yml` now selects `tests/test_document_delete_truth.py`; both changed files match reviewed head `2f2b376a0`. Hosted selection is not a live signed-in document replay. |
| #939 | `e855a9bf0` | Documentation of the signed-in Settings replay | 1 | Changes only `docs/acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md`; 29/29 at `a53b56fdc` is the bound evidence, not `b4370d0d4`. |
| #940 | `760997df8` | Hosted CI selection of workbook aggregation regressions | 4 | `test_assignment_multi_source_total.py` selected in backend CI; no product behavior change. |
| #941 | `935a890e7` | Root mobile CI workflow and mobile test/typecheck repairs | 16, 18 | Hosted mobile job passed 133 suites / 4,327 tests / 2 skipped at `3a0efed9c`; native device journey remains open. |
| #942 | `d08892617` | Preserve query complexity across provider selection | 2, 13 | Merged `llm_service.py` and regression test; controlled provider selection only; no live multi-model quality claim. |
| #937 | `b4370d0d4` | Enforce approval for reviewed executable skills | 6 | Approves/denies the exact reviewed artifact before sandbox dispatch. Both merged files are byte-identical to reviewed head `1387b7dd1`. Automatic model-invoked skill dispatch remains open. |

Note on review/CI: the handoff records exact-head checks and an authorized
review-only bypass for several merges. This index does **not** re-query GitHub
checks. A merge identity is not restated as a fresh CI pass for current main.

**Path-scoped ancestry checks (not a fresh acceptance):**

- `6ad2738ed..b4370d0d4`: the only non-doc/CI/mobile/frontend-shared product
  paths changed are `backend/core/fleet_admiral.py`,
  `backend/core/generic_agent.py`, `backend/core/llm_service.py`,
  `backend/core/skill_registry_service.py`, `scripts/dev.sh` and
  `scripts/quickstart.sh` (plus tests/fixtures). Workbook, Canvas and Settings
  product paths are unchanged in that range.
- `a53b56fdc..b4370d0d4`: the only such non-doc/CI/mobile/shared product paths
  changed are `backend/core/llm_service.py`,
  `backend/core/skill_registry_service.py`, `scripts/dev.sh` and
  `scripts/quickstart.sh` (plus tests/fixtures). Settings product paths are
  unchanged in that range.

These facts support carrying an earlier result forward as *ancestry evidence*;
they do **not** replace the current-main replay that several sections below
still list as missing. The later `#943` merge (`b4370d0d4..a868435fd`) adds
menu-bar, auth-adjacent backend and chat wiring paths. It does not change
workbook/Canvas product code, but it does touch auth-adjacent files, so the
earlier Settings result is not re-qualified merely by ancestry.

### 3.2 Drafts and live checks — not main

| PR | Draft head | Scope | Current evidence | Remaining gate |
|---:|---|---|---|---|
| #919 | `0c3b29f8a` | Opt-in real Flash transport for invoice replay | Loopback simulator path is 13/13 per handoff; no authorized live Zen invoice replay. | Authorized live provider replay. Keep draft. |
| #932 | `818bd0fd9` | Whisper audio-duration billing and settlement | Focused scratch suite 41, worker accounting 133; branch is based on `ad6ecbd5d`. | Live OpenAI transcription settlement with a configured credential. Keep draft. |

`#943` was a draft at the start of this pass and merged as `a868435fd` during
it. Its draft head `5d1f11de4` remains the evidence identity for the native
packet; the merge added only the already-merged `#937` skill files to that
tree.

### 3.3 `#943` native evidence — merged lineage and exact scope

`#943` was a **three-commit draft branch** ending at `5d1f11de4`
(“Enable native Keychain storage on macOS”), based on `bf1c50147`. It merged
during this pass as `a868435fd`, a direct child of `b4370d0d4`. It was not
main at the requested base; it is main at the observed ref.

Accepted at that exact draft scope:

- Native password sign-in reached the backend `POST /api/menubar/auth/login`.
- A fresh process restored the saved session from the macOS Keychain and made
  authenticated recent-items requests without another password entry.
- Settings logout removed both disposable Keychain entries; the next fresh
  launch stayed signed out.
- Native 2FA: password-only submission displayed the authenticator challenge
  with no session/Keychain write; a wrong code showed
  `Invalid two-factor code` with no session/Keychain write; a valid current
  code authenticated, recorded the replay-fence step, created device/audit
  state, and supported authenticated status/recent requests.

Evidence:

- `retained-private` sanitized packet:
  `/private/tmp/atom-menubar-2fa-native-evidence/`
  (`observations.jsonl`, `durable-state-sanitized.json`,
  `keychain-timeline.txt`, `runtime.txt`, `backend-requests-sanitized.log`).
- `retained-private` report:
  `/private/tmp/atom-menubar-2fa-native-report.md`
  (pinned binary sha256 `5d32077c…`, scratch DB proof, three audit attempts).
- `retained-private` relaunch/logout log:
  `/private/tmp/atom-menubar-relaunch-worker.log` (scratch artifacts removed;
  the log is retained, not replayable scratch).
- `handoff` `READINESS_CURRENT_MAIN.md` entries for `a3098543e`, `5d1f11de4`
  and the takeover review.

Explicit non-claims from the native packets:

- The direct-IPC cleanup logout cleared native session/Keychain but left the
  already-rendered React menu on screen. The separate earlier Settings logout
  replay covers UI logout; the 2FA lane did not claim it.
- 2FA backup codes, replay of an accepted code, rate-limit/lockout, 2FA
  enrollment, and session restore immediately after a 2FA sign-in were **not**
  covered.
- Live provider chat through the native UI is still pending. Another worker
  owns that lane; this index does not duplicate it.

Merge-lineage check: `git diff --name-status 5d1f11de4 a868435fd` lists only
`backend/core/skill_registry_service.py` and
`backend/tests/test_reviewed_executable_agent_consumption.py`, both from
`#937`. All `#943` menu-bar/backend native files and tests are unchanged
between the evidence head and the merge.

## 4. The 18 goals — current evidence and remaining boundary

The “Audit state” column is the 2026-11-07 row from
`APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json` → `goal_map`. The “Current
state” column is a qualitative evidence reconciliation, not a new score.
Every row remains short of whole-goal acceptance unless explicitly stated.

<a id="goal-1"></a>
### Goal 1 — Setup and ordinary account use

- **Audit state:** accepted-bounded.
- **Current state:** bounded. Signed-in Settings passed 29/29 at
  `a53b56fdc`, including Sessions and the full 2FA setup/enable/reload/disable
  round trip. This is a Settings boundary, not the whole account lifecycle.
- **Exact sources:** `#923` `d253602f1` (durable session revocation);
  `#939` `e855a9bf0` and
  [`WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md`](../acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md)
  §8 (29/29, run `wa075-20261114070119-89e3cb`, 409 API requests, 0 external
  requests, source `a53b56fdc`); `#936` `d1e3ddac8` (quickstart auth URL and
  private config); `#943` `a868435fd` (merged native login/session/2FA;
  evidence at draft head `5d1f11de4`).
- **Remaining user-boundary acceptance:** ordinary sign-up/recovery/SSO
  browser journey, fresh-profile sign-out, password reset, process-restart
  session recovery outside the scratch settings world, and a current-main
  replay. The 29/29 result is bound to `a53b56fdc`; later commits changed no
  Settings page/backend files, but no fresh current-main run exists.
- **Preserved negatives:** the committed WA-075 history records 25 pass /
  2 missing / 1 skipped, exit 3, then 27 pass / 1 missing / 1 skipped, exit 3.
  Those are not erased by §8. The `#943` direct-IPC logout observation is
  retained.
- **Claim rows:** 4 (below).

<a id="goal-2"></a>
### Goal 2 — BYOK and suitable model selection

- **Audit state:** accepted-bounded.
- **Current state:** bounded. Routing/gateway mechanisms are historically
  verified; `#942` preserves query complexity during provider selection. There
  is still no measured two-or-more-model quality/cost comparison at a served
  boundary.
- **Exact sources:** `#942` `d08892617` (`backend/core/llm_service.py` +
  regression test); audit rows `ROUTE-*`, `GW-*`; the historical controlled
  auto-selection evidence is in the audit's claim arrays.
- **Remaining user-boundary acceptance:** configure two real providers, request
  a workload, record requested vs served provider/model, score quality and
  expected cost, and show that capable Flash models remain first-class. No new
  key, spend or provider authority is implied.
- **Preserved negatives:** no live served multi-model comparison exists;
  `ROUTE-07` (OpenCode Go subscription) remains external-blocked without a
  live key/spend gate.
- **Claim rows:** 13.

<a id="goal-3"></a>
### Goal 3 — Authorized common data and search

- **Audit state:** accepted-bounded.
- **Current state:** bounded. WorkDrive code and live receipts exist, but the
  live 52-check and 56/56 receipts are bound to earlier PR heads, not
  current main `a868435fd`. Document delete truth and joined lifecycle are now
  hosted-CI selected; hosted selection is not a live signed-in replay.
- **Exact sources:** `#911` `04cb6ad6d` and `#921` `9062bb71e` (WorkDrive
  delivery; 56/56 private replay bound to `24794f257`); `#912` `9a0fc333d`
  (joined lifecycle selector); `#938` `471494e5d` (delete-truth selector at
  `.github/workflows/ci.yml`); `INT-09` remains external-blocked.
- **Remaining user-boundary acceptance:** a fresh signed-in WorkDrive replay on
  current main with a fresh grant; ordinary UI upload/open/search/export/delete
  and grounding; live connector qualification. `INT-09` remains external.
- **Preserved negatives:** `test_document_delete_truth.py` was **not** hosted-
  selected before `#938`; the WorkDrive 56/56 receipt is not a current-main
  run; live provider/account breadth was never granted in the audit.
- **Claim rows:** 31.

<a id="goal-4"></a>
### Goal 4 — Spreadsheet and calculation

- **Audit state:** accepted-bounded.
- **Current state:** bounded with new synthetic workbook evidence. `#928`,
  `#929`, `#930` and `#940` are merged. The 24-sheet full-population replay on
  merged main `6ad2738ed` returned 34,533.00 with 500 audited rows, 20 sheet
  citations and an explicitly labeled 80-row preview. This is a synthetic
  API/document-download journey, not a live connected-source or ordinary
  browser acceptance.
- **Exact sources:** `#928` `b39cc2982`; `#929` `bbf08de05`; `#930`
  `67ad1df80`; `#940` `760997df8`; private
  `/private/tmp/atom-main-fullpop.Q5pZMN/results/full-population-result.json`
  and `silent-partial-grand-total.docx.txt`; focused five-test log
  `/private/tmp/brennan-brief/workbook-current-main-tests.log` at
  `ea4a0a952`.
- **Remaining user-boundary acceptance:** ordinary browser and live connected-
  source run, extraction of the contributing-sheet population, exact export/
  restart readback, and reconciliation of ambiguous requests. The current
  evidence is synthetic fixtures.
- **Preserved negatives:** the pre-#930 single-sheet **1758.00** counterexample
  remains historical. The quote-discount and count-unit merges do not by
  themselves prove an ordinary served-model run.
- **Claim rows:** 2.

<a id="goal-5"></a>
### Goal 5 — Canvas and editable outputs

- **Audit state:** accepted-bounded.
- **Current state:** bounded. `#926` fixed the unslashed Canvas list route and
  passed a 22/22 post-merge signed-in replay at `6ad2738ed`. `#931` merged the
  offline editor assets; WA-045 passed 32/32 at `6ad2738ed`. Full Canvas D2 and
  remaining canvas families remain open.
- **Exact sources:** `#926` `1c00a72fc`; `#931` `6ad2738ed`; private
  `/private/tmp/canvas-926-postmerge-20261113_221126/evidence/result.json`
  and `/private/tmp/atom-main-canvas.W1hk5v/evidence/canvas-blank-lifecycle.json`;
  `MINI-03`/`MINI-05` remain environment-limited.
- **Remaining user-boundary acceptance:** full Canvas D2, ordinary-user reopen/
  export across remaining canvas families, and the Firecracker/KVM mini-app
  legs. Title/count-only renders are insufficient.
- **Preserved negatives:** Canvas list 405 existed before `#926`; the earlier
  Canvas family failures remain at their original sources. The 22/22 and 32/32
  results are bound to `6ad2738ed`, not current main `a868435fd`.
- **Claim rows:** 9.

<a id="goal-6"></a>
### Goal 6 — Teaching and reusable agent capability

- **Audit state:** accepted-bounded.
- **Current state:** bounded. `#918` introduced the reviewed-executable
  exception; `#925` added skill-package deletion; `#937` now fails closed
  before sandbox dispatch when the exact reviewed artifact/approval binding is
  missing. The ordinary agent can consume an approved skill through the
  ordinary execute route with a simulated sandbox; real Docker restart
  coverage exists separately. **Automatic model-invoked skill execution is not
  implemented/qualified and is owned by another worker.**
- **Exact sources:** `#918` `bb1e2b3f3`; `#925` `ad6ecbd5d`; `#937`
  `b4370d0d4` (files byte-identical to `1387b7dd1`);
  `backend/tests/test_reviewed_executable_agent_consumption.py` (four controls:
  fresh-session consumption, unreviewed pending denial, registry-binding
  removal denial, linked-Skill-binding removal denial);
  `backend/tests/test_reviewed_executable_skill_docker.py`;
  `retained-private` `/private/tmp/atom-937-root-review.log` (22 scratch
  tests per handoff).
- **Remaining user-boundary acceptance:** an approved executable skill invoked
  automatically by the ordinary agent loop (not just the API execute route),
  with a denial twin before sandbox dispatch. That worker is in
  `/private/tmp/atom-approved-skill-dispatch` and is not duplicated here.
- **Preserved negatives:** generated-code promotion was recorded as
  unimplemented before `#918`; `#937` is a defensive approval gate, not
  automatic invocation; earlier exploratory probes without assertions are not
  acceptance.
- **Claim rows:** 5.

<a id="goal-7"></a>
### Goal 7 — Assessment and unfamiliar work

- **Audit state:** accepted-bounded.
- **Current state:** bounded. Deterministic taught-rule judgment passes
  18/18 under V1 and 19/19 under V3 with safe abstention. The configured
  `ollama/llama3.1:8b` judgment path remains failed/unsafe for autonomous
  substantive recommendations.
- **Exact sources:** audit `ASK-*`, `ORACLE-06`; the historical deterministic
  packet is referenced in
  [`PRODUCT_GOAL_LEDGER_2026-10-29.md`](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md)
  and its evidence directories. No new held-out qualification was added in
  this pass.
- **Remaining user-boundary acceptance:** new held-out/served-domain
  qualification and any general adaptive judgment claim. The deterministic
  path does not interpret arbitrary prose.
- **Preserved negatives:** `Q-012` invented APPROVE (Amount 0) and `Q-021`
  returned REVIEW on a blank-region record; the model configuration is not
  reliable enough for autonomous substantive recommendations.
- **Claim rows:** 6.

<a id="goal-8"></a>
### Goal 8 — Durable employee objectives

- **Audit state:** accepted-bounded.
- **Current state:** bounded. The Goal 10 multi-source replay at
  `ad6ecbd5d` completed one durable assignment with two sources, a real
  restart, a matched delayed response and exactly one effect (362.50 USD).
  `GOAL-02` utility targets have scoped service/API/component evidence, but
  the ordinary real-agent utility episode is not whole-goal acceptance.
- **Exact sources:** `/private/tmp/brennan-brief/GOAL10_MULTISOURCE_DELAYED_RESULT_20261113.md`
  (bound to `ad6ecbd5d`; 4 focused tests; private evidence archive
  `/private/tmp/atom-goal10-multisource-artifacts/run-20261113/`);
  `#754` `8ded00232`; `#870` `5b563a38d`;
  audit `GOAL-*`.
- **Remaining user-boundary acceptance:** served/event-order behavior beyond
  accepted episodes, multi-worker/soak, arbitrary-domain extraction, and the
  canonical Goal 10 wait matrix. The multi-source run is one worker, one
  synthetic world, controlled outbox.
- **Preserved negatives:** no changed-teaching leg in that run; document prose
  was not converted into an automatic calculation rule; no live provider,
  recipient/inbox or multi-day soak.
- **Claim rows:** 5.

<a id="goal-9"></a>
### Goal 9 — Runtime configured-budget enforcement

- **Audit state:** accepted-bounded.
- **Current state:** open at the live-settlement boundary. The durable
  accounting/hard-stop work is not accepted until one priced `TokenUsage` row,
  matching tenant spend delta, idempotent duplicate settle, and a second
  dispatch refused before transport when budget is short are demonstrated.
  `#932` is a draft for Whisper duration billing, not merged live settlement.
- **Exact sources:** historical PR #722 / `5b9610b56` and the audit's Goal 9
  row; `#932` `818bd0fd9` draft (41 focused + 133 worker accounting per
  handoff); audit negative `b0` distinguishes production in-memory settlement
  from the durable ledger.
- **Remaining user-boundary acceptance:** live/durable priced settlement,
  pre-transport refusal, concurrent spend, failure degradation and PostgreSQL.
  No live dollar spend is authorized.
- **Preserved negatives:** the `#896` pre-repair three-case settlement failure;
  production settlement used an in-memory tracker while admission read
  `TokenUsage`/ACU; unreadable hard-stop failed open; unknown pricing became 0.
- **Claim rows:** 0 original 143 claims. Goal 9 is an explicit user
  requirement, not one of the 143 README claims.

<a id="goal-10"></a>
### Goal 10 — TASK-WAIT-01 long tasks pause/resume

- **Audit state:** open.
- **Current state:** open. A durable 48-hour wait was started and the worker was
  stopped with `SIGKILL`; the wait survived. **The resume gate is not due
  before 2026-11-16T06:42:25.414033Z.** No resume result exists. Separately,
  the multi-source delayed-response run at `ad6ecbd5d` passed a bounded
  restart/resume/approval journey, but it is not the 48-hour elapsed wait.
- **Exact sources:** `/private/tmp/atom-elapsed-wait-driver/state/wait-case.json`
  (`phase=awaiting_48h_elapsed`, `resume_not_before=2026-11-16T06:42:25.414033+00:00`,
  `required_elapsed_seconds=172800`, job `96c65751-…`, execution
  `a21bc264-…`, correlation `75d4fd80-…`); `evidence/verification.json`
  (`all_passed=true`, worker dead, wait pending, scratch DB); `evidence/resume-refusal.log`;
  `README.md` (real 48h gate, no `--force`/clock injection).
  The driver's source head is `2f2b376a0` (the `#938` head), not current main.
  Multi-source evidence:
  `/private/tmp/brennan-brief/GOAL10_MULTISOURCE_DELAYED_RESULT_20261113.md`.
- **Remaining user-boundary acceptance:** actual elapsed 48-hour resume on
  the retained scratch world; both event orders; repeated/partial replies;
  revocation/cancellation during wait; all supported surfaces; ordinary UI;
  multi-worker/soak. Arrival of information is not completion.
- **Preserved negatives:** `0bbe` overall failure and the `d3` 29-stage/162-
  assertion episode; the first elapsed-wait run was archived after a startup
  pricing-cache fetch; premature-resume refusal is retained.
- **Claim rows:** 0 original 143 claims. TASK-WAIT-01 is an explicit user
  requirement added to the goal register, not a README claim.

<a id="goal-11"></a>
### Goal 11 — Documents, presentations and email drafts

- **Audit state:** accepted-bounded.
- **Current state:** bounded. Office document/presentation and controlled
  email-draft packets exist; the one-use live send was exhausted and recipient
  delivery is a separate, unclaimed boundary. `#919` is a draft for a live
  invoice replay; its accepted path is a loopback simulator, not a live Zen
  provider.
- **Exact sources:** audit `OFF-01`, `OFF-04`; historical Office/email packets;
  `#919` `0c3b29f8a` (draft; 13/13 loopback, live leg unproven).
- **Remaining user-boundary acceptance:** ordinary document journey, provider
  draft readback, real recipient inbox delivery, and the authorized live
  invoice replay. The one-use live send authority is exhausted.
- **Preserved negatives:** no real recipient in the approval replay; `#919`
  simulator is not live; the live send was one declared payload only.
- **Claim rows:** 2.

<a id="goal-12"></a>
### Goal 12 — Repeatable workflows and schedules

- **Audit state:** accepted-bounded.
- **Current state:** bounded. Workflow create/execute/replay/schedule and
  HITL mechanisms are historically verified. ORCH-01 has controlled
  blueprint evidence plus a local-Ollama route test, but no production served
  route/deadline attribution. Full scheduled result/receipt on current main is
  still open.
- **Exact sources:** `ORCH-01` `0fae2d46c`; public scope `49d45c7f3`;
  scheduler `78d2e0ca8`; restart `b9ed05c6f`; recovery `e2ba4b01c`; `#899`
  `4e2caffc8` (test-only local Ollama route qualification); audit `WF-*`.
- **Remaining user-boundary acceptance:** one real served workflow request
  through the production route/deadline path; a full scheduled real-workflow
  result and receipt; PostgreSQL/multi-worker/soak.
- **Preserved negatives:** the audit's ORCH-01 gap remains: the accepted route
  uses a controlled LLM double; served model/provider quality is unobserved.
- **Claim rows:** 11.

<a id="goal-13"></a>
### Goal 13 — Fleet, goals and background work

- **Audit state:** accepted-bounded.
- **Current state:** bounded, with two different evidence cuts. The Goal 13
  live replay at `ad6ecbd5d` used one local `llama3.1:8b`, one delegation
  chain, one in-scope specialist, and a restart/cache tripwire. It **predates**
  #934 and #935. `#934` (tree equal to tested `5dadad938`) and `#935` (tree
  equal to reviewed `fcc129444`) are merged later. A separate #935 frozen live
  replay is recorded in the handoff, but current main (`a868435fd`) was not
  re-run.
- **Exact sources:**
  `/private/tmp/brennan-brief/GOAL13_LIVE_FLEET_REPLAY_2026-11-13.md`
  (source `ad6ecbd5d`, 1 passed in 115.06s, local Ollama digest
  `46e0c10c…`, one chain, cache hit after restart; limitations include the
  pre-#934 `user_id` signature failure in recruitment and stochastic 8B
  finalization);
  `/private/tmp/brennan-brief/fleet-combined-live.log` and
  `fleet-final-frozen-captured.txt` (`retained-private` #935 frozen replay:
  both links completed, 42,000 / 36,000 / 6,000, proposal-only footer; churn
  ratio wording remains awkward);
  `#934` `58c1f44f5`; `#935` `a53b56fdc`.
- **Remaining user-boundary acceptance:** current-main live fleet replay after
  #934/#935; real served recruitment/quality; broader delegation and restart;
  no shadow success; no out-of-scope specialist. `TEAM-05` still needs one real
  scheduled fire through the configured transport.
- **Preserved negatives:** the long fleet sequence includes budget_exceeded,
  max_steps_exceeded, foreign-specialist exclusion, omitted corrective
  actions, wrong `36,000` total, unsupported `22,000` subtotal, `-6,000` sign
  errors, and the pre-#934 recruitment signature failure. These remain at
  their original logs; the #935 replay does not erase them.
- **Claim rows:** 14.

<a id="goal-14"></a>
### Goal 14 — Direct mutations and whole-app ORACLE

- **Audit state:** open.
- **Current state:** open. Scoped mutation families and merged receipts exist,
  but there is no whole-app runtime coverage. The ORACLE inventory is a
  static count of decorator declarations/high-risk names/provider write
  methods, not a count of qualified reachable routes.
- **Exact sources:** audit `ORACLE-01` (827 mutating routes / 366 high-risk /
  311 provider writes at the historical cut; a later read-only inventory at
  `8ded00232` recorded 836 / 371 / 311); merged scoped families #650–#695;
  `#938` `471494e5d` adds hosted delete-truth selection; `GOV-02/03/06` and
  `SEC-01..08` remain baseline-verified at their historical sources.
- **Remaining user-boundary acceptance:** every reachable mutation family
  enforcing current authority/material, exact operation, durable effect and
  independent readback; replay/rollback/unknown truth; refreshed inventory on
  current main; PostgreSQL/multi-worker.
- **Preserved negatives:** four real mounted-route delete/undelete cases
  confirmed current-scope defects for former coeditors; 827/366/311 (or
  836/371/311) static routes are not runtime qualification. Green CI is not
  whole-app ORACLE.
- **Claim rows:** 16.

<a id="goal-15"></a>
### Goal 15 — Remaining exposed application

- **Audit state:** open/partial.
- **Current state:** partial. Settings now has a 29/29 signed-in replay at
  `a53b56fdc`; Canvas list has 22/22 at `6ad2738ed`; Tasks/Projects have
  authority-bound HTTP evidence in `#797`. Many other enabled surfaces were
  never re-run after the 2026-10-27 whole-app ledger, so its partial/unproven
  items are historical, not current failures or current passes.
- **Exact sources:** `#797` `3541e8115`; `#926` `1c00a72fc`; `#939`/WA-075;
  [`WHOLE_APP_READINESS_LEDGER_2026-10-27.md`](../acceptance/WHOLE_APP_READINESS_LEDGER_2026-10-27.md)
  for the historical 91-item checklist (candidate `f5f3148d2`).
- **Remaining user-boundary acceptance:** primary action + durable readback on
  Tasks/Boards, marketplace install, unified search, finance/voice/BPE/runtime
  settings/skill editor/team chat, blocked-route error state, and direct admin/
  member route behavior. Re-run on current main before crediting.
- **Preserved negatives:** WA-013 admin-shell partial, WA-046 search partial,
  WA-049 marketplace unproven, WA-057 finance unproven, WA-061 voice unproven,
  WA-063/64/67/69 render-only, WA-078 team chat unproven, WA-079 error state
  unproven, WA-088 sessions failed at `f5f` (later #923 repaired the route, but
  the historical ledger row is not rewritten). These are historical records;
  do not recycle them as current failures without a current replay.
- **Claim rows:** 8.

<a id="goal-16"></a>
### Goal 16 — Installation, compatibility and operations

- **Audit state:** open.
- **Current state:** open with bounded slices. macOS Python 3.12 clean
  quickstart, scratch backup/restore and live previous-release rollback passed;
  `#936` merged the quickstart hardening. Mobile CI is merged (`#941`) and
  passed hosted strict TypeScript/Jest; native device journeys remain open.
  Menu bar native login/session/logout/2FA is merged in `#943` (`a868435fd`;
  native evidence at draft head `5d1f11de4`), with public-API live Go chat verified and native UI chat pending. Linux
  3.11–3.13 CI is bounded; KVM/Firecracker, PostgreSQL/multi-worker and native
  mobile/menubar live use remain open.
- **Exact sources:** `#936` `d1e3ddac8`; `#941` `935a890e7` (hosted mobile job
  133 suites / 4,327 tests / 2 skipped at `3a0efed9c`);
  `#943` `a868435fd` plus the native packet/report above (evidence bound to
  draft head `5d1f11de4`);
  `retained-private` quickstart/restore/rollback evidence paths in the handoff
  (`/private/tmp/atom-quickstart-verify-evidence-20261114`,
  `/private/tmp/atom-quickstart-verify-evidence-20261114/restore-child-evidence/run-report.json`,
  `/private/tmp/atom-rollback-rehearsal.EA2Kfg/run/rollback_receipt.json`);
  COMPAT-01 Linux CI packet
  `docs/acceptance/evidence/compat01_quickstart_main_ci_20261112/`.
- **Remaining user-boundary acceptance:** supported clean install on macOS/
  Linux/ARM with the documented interpreter; PostgreSQL runtime/concurrency/
  soak; mobile native simulator/device journey; menu bar native live chat;
  KVM/Firecracker; full rollback/public login/restore/restart child flow.
- **Preserved negatives:** mobile TypeScript parser diagnostics (4 → 652 → 544
  / 429 / 297 across intermediate candidates) and failed Expo export before
  dependency repair; menu bar scratch HTTP health 404 and earlier native
  WebSocket/2FA gaps; the published `v1.0.0` tag is old and not evidence of a
  current package. `#943` is merged, but native live provider chat remains
  unverified.
- **Claim rows:** 8.

<a id="goal-17"></a>
### Goal 17 — Performance and comparative promises

- **Audit state:** unverified.
- **Current state:** unverified. No declared-environment/workload/sample
  measurement exists for the advertised performance/comparative numbers. The
  governance cache benchmark at `dd2610502` is source-bound cache-only
  correctness and DB isolation (37 independent tests), not full governance/
  HTTP performance or universal throughput.
- **Exact sources:** audit `PERF-01..03`, `MKT-01..05`;
  [`APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json`](APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json)
  → `performance_reconciliation`.
- **Remaining user-boundary acceptance:** reproducible measurement with
  declared environment, workload, sample size and source; dated pricing/
  competitor source for comparative claims. No invented numbers.
- **Preserved negatives:** historical missing public reproducer statement;
  the cache-only benchmark does not certify full governance or HTTP
  performance.
- **Claim rows:** 8.

<a id="goal-18"></a>
### Goal 18 — Profile breadth

- **Audit state:** open/deferred.
- **Current state:** open/deferred. `CORE-07` (`ATOM_PRODUCT_PROFILE=full`
  restores the wider surface) is baseline-verified, but full-profile breadth
  is an owner decision. Deferred affordances were not force-enabled.
- **Exact sources:** audit `CORE-07`; `APP_GOALS_INDEX.json` explicit user
  requirements.
- **Remaining user-boundary acceptance:** explicit owner decision on
  full-profile enablement and qualified journeys for the restored surfaces.
  Do not add SaaS gates or force-enable deferred profiles to close rows.
- **Preserved negatives:** `CORE-07` is a profile switch, not evidence that
  every restored surface is accepted.
- **Claim rows:** 1.

## 5. Claim register — all 143 original claims

**How to read these tables.** The claim IDs, historical status, audit overlay
and evidence sufficiency are copied from
`APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json`. A cell of `audit` means
the exact retained source is that JSON's `claims[]` entry for the ID, including
its evidence array and gap; this index adds no fresh adjudication. `bounded` /
`open` / `environment` / `external` / `none` are the audit's evidence-
sufficiency meanings, not new counts.

The grouping of claim rows under goals is **navigational only**. The audit
JSON does not carry a canonical claim→goal foreign key; the grouping below is
this document's subject-matter crosswalk. It does not change any claim status,
evidence sufficiency, score or denominator. Goals 9 and 10 have no original
README claim row and are recorded separately in §5.18.

### 5.1 Counts preserved (not a new score)

| Audit state | Count | Claims |
|---|---:|---|
| baseline-verified | 119 | All rows marked `baseline-verified` below |
| accepted-bounded | 6 | `ORCH-01`, `ORCH-02`, `ORCH-07`, `MEM-07`, `MINI-04`, `GOAL-02` |
| open | 2 | `ORACLE-01`, `TEAM-05` |
| environment-limited | 2 | `MINI-03`, `MINI-05` |
| external-blocked | 2 | `INT-09`, `ROUTE-07` |
| unverified | 12 | `PERF-01..03`, `COMPAT-01..04`, `MKT-01..05` |
| **Total** | **143** | 123 functional + 20 separately tracked |

Historical functional score remains **111/123 (90.2%)**. The counts above are
the audit's overlay, not a new numerator. Do not add them to produce a new
completion percentage.

### 5.2 Goal 1 — 4 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `CORE-06` | Settings for providers and data configuration | verified | baseline-verified | sufficient-at-historical-source | WA-075 29/29 at `a53b56fdc`; settings only; not current-main re-run. |
| `GOV-05` | OIDC SSO | verified | baseline-verified | sufficient-at-historical-source | Controlled local OIDC browser proof `b27551a9c` (31 boundary checks); live IdP open. |
| `GOV-07` | 8-role RBAC | verified | baseline-verified | sufficient-at-historical-source | audit; role visibility not fully re-run. |
| `INST-04` | Sign in as the seeded admin | verified | baseline-verified | sufficient-at-historical-source | `#936` quickstart auth URL fix; WA-075 scratch login. |

### 5.3 Goal 2 — 13 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `GW-01` | OpenAI-compatible API | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GW-02` | Anthropic-compatible API | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GW-03` | Point OpenAI-SDK apps at Atom | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GW-04` | `atom_sk_*` keys | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GW-05` | Gateway over BYOK | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GW-06` | Error propagation | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-01` | 5-tier cognitive classification | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-02` | 16+ providers | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-03` | Cost-aware routing/fallback | verified | baseline-verified | sufficient-at-historical-source | audit; `#942` preserves query complexity. |
| `ROUTE-04` | Opt-in learning router | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-05` | RTK token compression | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-06` | Local Ollama/OpenAI-compatible server | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ROUTE-07` | OpenCode Go subscription provider | unverified | external-blocked | external | no live key/spend gate; audit. |

### 5.4 Goal 3 — 31 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `CORE-02` | Bring records/data | verified | baseline-verified | sufficient-at-historical-source | audit |
| `CORE-03` | Review/correct workspace data | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GRAPH-01` | GraphRAG | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GRAPH-02` | Multi-hop expansion | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GRAPH-03` | Leiden community detection | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GRAPH-04` | JIT fact verification | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GRAPH-05` | D3 visual explorer | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-01` | 46+ business integrations | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-02` | Truthful connected state | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-03` | OAuth connect | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-04` | Use connected data | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-05` | Outbound actions | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-06` | Disconnect | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-07` | Webhook triggers | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-08` | Named provider breadth | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INT-09` | Live qualification | blocked_external | external-blocked | external | no live accounts/consent; audit. |
| `MEM-01` | Per-turn fact extraction | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-02` | 2-tier recall (SQL + LanceDB) | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-03` | LanceDB recall | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-04` | Episodic memory | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-05` | `memory_remember` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-06` | `memory_forget` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEARCH-01` | BM25 (FTS5/tsvector) | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEARCH-02` | + vector (LanceDB) | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEARCH-03` | Reciprocal Rank Fusion | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEARCH-04` | Semantic + precise citations | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEARCH-05` | Search behaviour | verified | baseline-verified | sufficient-at-historical-source | audit |
| `VFS-01` | `ls` / tree | verified | baseline-verified | sufficient-at-historical-source | audit |
| `VFS-02` | `cat` with line citations | verified | baseline-verified | sufficient-at-historical-source | audit |
| `VFS-03` | `grep` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `VFS-04` | Knowledge VFS instead of bespoke queries | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.5 Goal 4 — 2 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `OFF-02` | Excel editing | verified | baseline-verified | sufficient-at-historical-source | audit; `#928`/`#929`/`#930` merged; synthetic workbook at `6ad2738ed`; ordinary served boundary open. |
| `OFF-03` | Formula-evaluating workbook runtime | verified | baseline-verified | sufficient-at-historical-source | audit; 24-sheet full-population replay at `6ad2738ed`; 1758.00 negative preserved. |

### 5.6 Goal 5 — 9 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `MINI-01` | Agent-authored stateful canvas apps | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MINI-02` | Syntax-gated logic | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MINI-03` | `dev_run` / `run_tests` | environment_limited | environment-limited | environment | no KVM/Firecracker; audit. |
| `MINI-04` | Per-instance state | environment_limited | accepted-bounded | bounded | host-mediated record leg at `d84e46a4a`/`8a577f14a`; MINI-05 separate. |
| `MINI-05` | Firecracker isolation/per-instance chat | architecture_only | environment-limited | environment | fail-closed; no microVM; audit. |
| `OFF-05` | Agent editing on Canvas | verified | baseline-verified | sufficient-at-historical-source | audit; WA-045 32/32 at `6ad2738ed`. |
| `OFF-06` | Agent ↔ document sync | verified | baseline-verified | sufficient-at-historical-source | audit |
| `OFF-07` | Live preview broadcast | verified | baseline-verified | sufficient-at-historical-source | audit |
| `OFF-08` | Live Canvas co-editing | verified | baseline-verified | sufficient-at-historical-source | audit; full D2 open. |

### 5.7 Goal 6 — 5 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `CORE-04` | Teach an agent | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOV-01` | 4-tier maturity | verified | baseline-verified | sufficient-at-historical-source | audit; graduation PRs #782–#785; no general competence. |
| `GOV-04` | AI-powered training | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOV-08` | Agent lifecycle | verified | baseline-verified | sufficient-at-historical-source | audit |
| `MEM-07` | Self-evolution / Memento/AlphaEvolver | unverified | accepted-bounded | bounded | `#751` `4590560d7` finite local chain; no served/general repair. |

**Goal 6 post-audit note (not a claim promotion):** `#918`, `#925` and `#937`
add a reviewed-executable skill path. `#937` is a defensive approval gate, not
automatic model-invoked execution. See Goal 6 above for exact sources.

### 5.8 Goal 7 — 6 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `ASK-01` | Earn interruption-free status from verified record | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ASK-02` | Ask fails safe | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ASK-03` | Lose privilege on regression | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ASK-04` | Held-out Brier/denial-coverage gate | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ASK-05` | Relax autonomy only after gate | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORACLE-06` | Opt-in reviewer re-delegation | verified | baseline-verified | sufficient-at-historical-source | audit |

**Goal 7 post-audit note (not a claim promotion):** deterministic assessment
is 18/18 V1 and 19/19 V3; the `llama3.1:8b` configuration remains failed
(`Q-012`, `Q-021`). See Goal 7 above.

### 5.9 Goal 8 — 5 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `GOAL-01` | `definition_of_done` early termination | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOAL-02` | Utility targets | unverified | accepted-bounded | bounded | `#754` `8ded00232`; `#870` `5b563a38d`; controlled utility UI packet; ordinary real-agent utility episode open. |
| `GOAL-03` | Custom action surfaces | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOAL-04` | Stuck detection | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOAL-05` | Goal-driven loops | verified | baseline-verified | sufficient-at-historical-source | audit |

**Goal 8 post-audit note (not a claim promotion):** the multi-source
delayed-response run at `ad6ecbd5d` is bounded Goal 8/10 evidence; it does not
close the claim rows.

### 5.10 Goal 11 — 2 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `OFF-01` | Agent-driven Excel/Word/PPTX editing | verified | baseline-verified | sufficient-at-historical-source | audit; Office/email packets; `#919` draft live invoice replay not main. |
| `OFF-04` | PPTX editing | verified | baseline-verified | sufficient-at-historical-source | audit; presentation evidence; recipient delivery separate. |

### 5.11 Goal 12 — 11 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `ORCH-01` | Queen Agent structured workflows | unverified | accepted-bounded | bounded | `#899` `4e2caffc8` test-only local Ollama route; still controlled, no served production route. |
| `ORCH-03` | Conductor 5 strategies | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORCH-04` | Validated state machine | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORCH-05` | Rollback | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-01` | Build and run a workflow | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-02` | Run the workflow | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-03` | Replayable workflow | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-04` | Scheduled workflow | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-05` | HITL approval gates | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-06` | Governed, replayable workflow | verified | baseline-verified | sufficient-at-historical-source | audit |
| `WF-07` | Import a personal starter | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.12 Goal 13 — 14 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `ORCH-02` | Fleet Admiral open-ended tasks | unverified | accepted-bounded | bounded | Goal13 replay at `ad6ecbd5d` + `#934`/`#935`; one local model; current main not re-run. |
| `ORCH-06` | Governed fleet routing/ranked matching | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORCH-07` | Governed fleet routing | unverified | accepted-bounded | bounded | same as ORCH-02; served recruitment quality open. |
| `ORCH-08` | Delegation contracts | verified | baseline-verified | sufficient-at-historical-source | audit |
| `RADIO-01` | Lateral peer messaging | verified | baseline-verified | sufficient-at-historical-source | audit |
| `RADIO-02` | Mention-first | verified | baseline-verified | sufficient-at-historical-source | audit |
| `RADIO-03` | Budget-governed | verified | baseline-verified | sufficient-at-historical-source | audit |
| `RADIO-04` | No hardcoded teams | verified | baseline-verified | sufficient-at-historical-source | audit |
| `TEAM-01` | Single accountable agent | verified | baseline-verified | sufficient-at-historical-source | audit |
| `TEAM-02` | Expiring privilege leases | verified | baseline-verified | sufficient-at-historical-source | audit |
| `TEAM-03` | Conflict-of-interest detection | verified | baseline-verified | sufficient-at-historical-source | audit |
| `TEAM-04` | Contribution credit to graduation | verified | baseline-verified | sufficient-at-historical-source | audit |
| `TEAM-05` | Opt-in nightly alignment sweeps | partial | open | partial | `#903` `236f15ca1` harness; final real scheduled fire/readback pending. |
| `TEAM-06` | Telemetry for ignored/redone work | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.13 Goal 14 — 16 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `GOV-02` | Policy-gated HITL approval | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOV-03` | Comprehensive audit trail | verified | baseline-verified | sufficient-at-historical-source | audit |
| `GOV-06` | SCIM v2 provisioning | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORACLE-01` | Postcondition oracle on by default | partial | open | partial | inventory 836/371/311 at `8ded`; four delete/undelete current-scope failures; scoped families merged; whole-app open. |
| `ORACLE-02` | Re-derive success from system of record | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORACLE-03` | Refuted self-report stamped UNVERIFIED | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORACLE-04` | `ATOM_ORACLE_ENFORCE` kill switch | verified | baseline-verified | sufficient-at-historical-source | audit |
| `ORACLE-05` | Two-tier confidence provenance | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-01` | Sandbox at every dispatch hub | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-02` | OAuth tokens encrypted at rest | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-03` | Per-agent capability bindings | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-04` | Outbound gatekeeper | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-05` | Data-taint tracking | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-06` | External MCP client | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-07` | OIDC SSO + SCIM + 8-role RBAC | verified | baseline-verified | sufficient-at-historical-source | audit |
| `SEC-08` | Production fails closed without key | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.14 Goal 15 — 8 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `CORE-01` | Chat | verified | baseline-verified | sufficient-at-historical-source | audit |
| `CORE-05` | Activity/results/failures | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-01` | MCP client | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-02` | External tool execution | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-03` | A2A Agent Card | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-04` | A2A message/send | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-05` | ACP endpoint | verified | baseline-verified | sufficient-at-historical-source | audit |
| `IO-06` | Span tracing/Langfuse | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.15 Goal 16 — 8 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `COMPAT-01` | Python 3.11+ | unverified | unverified | partial | Linux CI 3.11–3.13; macOS 3.12 manual; 3.14 rejected by guard. |
| `COMPAT-02` | FastAPI/SQLAlchemy/LangChain/Playwright/Next.js | unverified | unverified | none | no clean pinned-stack matrix; audit. |
| `COMPAT-03` | PostgreSQL | unverified | unverified | none | runtime/concurrency/soak open; audit. |
| `COMPAT-04` | Mobile Expo / menubar Tauri | unverified | unverified | none | `#941` mobile CI and merged `#943` menubar slice are partial; native journeys/live chat open. |
| `INST-01` | `make setup` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INST-02` | `make backend` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INST-03` | `make frontend` | verified | baseline-verified | sufficient-at-historical-source | audit |
| `INST-05` | Data on your infrastructure | verified | baseline-verified | sufficient-at-historical-source | audit |

### 5.16 Goal 17 — 8 claims

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `PERF-01` | 0.027 ms P99 per check | unverified | unverified | none | no declared measurement; cache-only benchmark `dd2610502` is not this claim. |
| `PERF-02` | 616k ops/s cached throughput | unverified | unverified | none | no declared measurement; audit. |
| `PERF-03` | 85k+ test functions | unverified | unverified | none | no reproducible count/source; audit. |
| `MKT-01` | Self-hosted + 46+ integrations | unverified | unverified | none | no sourced comparison; audit. |
| `MKT-02` | “Only open-source platform…” | unverified | unverified | none | no sourced comparison; audit. |
| `MKT-03` | Comparison matrix | unverified | unverified | none | no verified matrix; audit. |
| `MKT-04` | 88% pilot statistic | unverified | unverified | none | source not retained; audit. |
| `MKT-05` | OpenCode Go ~90% savings | unverified | unverified | none | no dated pricing/comparison; audit. |

### 5.17 Goal 18 — 1 claim

| Claim | Requirement (short) | Historical | Overlay | Sufficiency | Current source note |
|---|---|---|---|---|---|
| `CORE-07` | `ATOM_PRODUCT_PROFILE=full` restores wider surface | verified | baseline-verified | sufficient-at-historical-source | profile switch verified; full-profile breadth is owner-deferred. |

### 5.18 Goals 9 and 10 — explicit requirements, zero original README claims

The 143-claim inventory contains **no** claim row primarily for canonical
Goal 9 (runtime configured-budget enforcement) or canonical Goal 10
(`TASK-WAIT-01`). They remain in the goal register as explicit user
requirements and are tracked through separate evidence, not by inflating the
claim denominator.

- Goal 9: PR #722 / `5b9610b56` historical bounded work; draft `#932`
  `818bd0fd9`; live settlement/hard stop open.
- Goal 10: 48-hour wait pending; not due before
  `2026-11-16T06:42:25.414033Z`; multi-source bounded run at `ad6ecbd5d`;
  full TASK-WAIT-01 open.

## 6. Remaining user-boundary acceptance — ranked

This is the shortest honest execution list. It is not a work-order
reassignment; other workers own the lanes noted.

| Rank | Boundary | Current exact position | What would count |
|---:|---|---|---|
| 1 | **Goal 10 elapsed wait** | Durable wait persisted at 06:42:25.414033Z on 2026-11-14; worker stopped; resume gate refuses until **2026-11-16T06:42:25.414033Z**. Source head `2f2b376a0`. | Actual resume on/after the gate, same job/execution/wait identity, no model continuation/task effect before the answer, then a verified outcome. Do not run early or force the gate. |
| 2 | **Goal 9 live settlement/hard stop** | `#932` draft `818bd0fd9`; no live OpenAI credential; no durable live settlement claim. | One priced `TokenUsage` row (`billed`, settled, tokens>0), matching tenant spend delta, idempotent duplicate settle, second dispatch refused before transport when short, Whisper duration case. |
| 3 | **Goal 13 current-main fleet** | Pre-#934 live replay at `ad6ecbd5d`; #934/#935 merged after it; #935 private frozen replay; current main not re-run. | One current-main live TASK, one in-scope chain, specialist findings in the reply, terminal state after restart, no shadow success/no out-of-scope specialist; model-driven recruitment quality separately. |
| 4 | **Goal 6 automatic skill invocation** | `#937` approval gate merged; ordinary execute route tested; **no model-callable skill execution tool**. Another worker owns the auto-invoke lane. | An approved executable skill invoked by the ordinary agent loop, with a pre-dispatch denial twin for an unapproved/changed artifact. Do not duplicate the worker. |
| 5 | **Goal 16 native menu bar live chat** | Native login/relaunch/logout/2FA is merged in `#943` `a868435fd`; native evidence remains bound to draft `5d1f11de4`; public-API Go chat passed. | Native UI chat with a real configured provider and no credential leakage. The public-API replay is complete. |
| 6 | **Goal 3 WorkDrive/document current main** | 56/56 WorkDrive replay bound to `24794f257`; delete truth now hosted-selected; no current-main signed-in replay. | Fresh signed-in WorkDrive/document journey at `b4370d0d4` or later, ordinary upload/open/search/export/delete readback. |
| 7 | **Goal 4 workbook ordinary/live** | Synthetic 24-sheet replay at `6ad2738ed`; full-population 34,533.00; no live connected source or browser. | Ordinary browser + live connected source; exact export/restart values; ambiguous-request refusal. |
| 8 | **Goal 5 Canvas full families** | WA-045 32/32 and Canvas list 22/22 at `6ad2738ed`; full D2 open; mini-app KVM legs environment-limited. | Full Canvas D2, remaining families, ordinary reopen/export, and a KVM/microVM run where applicable. |
| 9 | **Goal 1 full account lifecycle** | WA-075 29/29 Settings at `a53b56fdc`; native 2FA/menubar merged in `#943`; no current-main ordinary signup/recovery/SSO. | Ordinary signup, recovery, SSO and restart-session journeys at the current main, not just Settings. |
| 10 | **Goal 14 whole-app ORACLE** | Scoped families merged; static inventory 836/371/311; four delete/undelete failures preserved. | One genuinely unqualified high-risk family with authority/material/readback/replay/uncertainty and negative twins; refreshed inventory. |
| 11 | **Goal 15 exposed app primary actions** | Settings and Canvas have current bounded proofs; many WA-ledger surfaces were not re-run. | Primary action + durable readback on Tasks/Boards, marketplace install, search, finance/voice/BPE/settings/skill editor/team chat, blocked-route error state. |
| 12 | **Goal 16 operations breadth** | macOS 3.12 quickstart/restore/rollback bounded; mobile CI merged; native mobile/KVM/PostgreSQL open. | Supported clean installs, PostgreSQL/multi-worker/soak, native mobile device journey, KVM/Firecracker, full rollback/login/restore/restart. |
| 13 | **Goal 2 measured model selection** | Routing mechanisms verified; #942 preserved query complexity; no measured served comparison. | Two or more real served models with requested/served identity and scored quality/cost, including cheap Flash as first-class. No new spend authority. |
| 14 | **Goal 17 performance/comparative** | Unverified; cache-only benchmark only. | Declared environment/workload/sample, reproducible command, dated source for comparative claims. |
| 15 | **Goal 18 profile breadth** | `CORE-07` switch baseline; owner-deferred. | Explicit owner decision and qualified journeys for restored surfaces; no force-enable. |

## 7. Historical negatives and retained failures

These are preserved at their original sources. A later success may supersede
the *current status* of a PR or a slice, but it does not erase these records.

| Negative | Original source | Why it remains |
|---|---|---|
| **1758.00 single-sheet workbook result** | `PRODUCT_GOAL_LEDGER_MAIN_96cd526b` / handoff §5; pre-#930 main | The counterexample motivated #930; the synthetic full-population pass does not rewrite the earlier failure. |
| **#896 pre-repair three-case settlement failure** | Handoff §6; audit Goal 9 | Settlement later work does not erase the pre-repair failure. |
| **`llama3.1:8b` judgment failures** | [`PRODUCT_GOAL_LEDGER_2026-10-29.md`](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md) (Q-012 invented APPROVE, Q-021 REVIEW) | The deterministic path passes; the model path remains failed for autonomous substantive recommendations. |
| **`0bbe` overall failure; `d3` 29/162 episode** | Audit §2 / handoff | The `f179` 30-stage/195-assertion packet is bounded; the old failures are not relabelled. |
| **WA-075 25/2/1 exit 3; then 27/1/1 exit 3** | `WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md` §6–§7 | The later 29/29 §8 supersedes the current verdict, but the historical missing/skipped states stay. |
| **#924 GitGuardian incident 40037405** | Handoff §2/§6; issue/PR record | Closed unmerged; #931 is the clean replacement. No scanner waiver or history rewrite. |
| **Live quote credential-boundary failure** | `/private/tmp/brennan-brief/live-quote-replay-credential-boundary.log` | No credential produced `provider_failure` and deterministic fallback; it is a preserved negative, not a live pass. |
| **Fleet failure sequence** | `/private/tmp/brennan-brief/` fleet logs; Goal 13 report | `budget_exceeded`, `max_steps_exceeded`, foreign-specialist exclusion, omitted actions, wrong `36,000` total, unsupported `22,000` subtotal, `-6,000` sign errors. The #935 frozen replay does not erase them. |
| **Mobile TypeScript/export failures** | Handoff §Goal 16; `/Volumes/Seagate Portable Drive/atom-mobile-verify.QT2kmX/` | Parser diagnostics 4 → 652 → 544/429/297, failed Expo export before dependency repair. #941's green CI does not erase the earlier candidate failures. |
| **Menu bar scratch HTTP 404 / native WebSocket gap** | Handoff §Goal 16; `/private/tmp/atom-menu-*` logs | The merged `#943` slice (native evidence at draft `5d1f11de4`) does not retroactively qualify the removed HTTP adapter or native WebSocket/live chat. |
| **Whole-app `WA-088` failed sessions row** | `WHOLE_APP_READINESS_LEDGER_2026-10-27.md` | #923 later repaired the route; the historical ledger row remains failed at `f5f`. Do not rewrite it. |
| **#943 direct-IPC logout observation** | `/private/tmp/atom-menubar-2fa-native-report.md` §Findings | Cleared native session/Keychain but left the rendered React menu; UI logout must come from the separate Settings replay. |

## 8. Unresolved or missing evidence — stated plainly

| Item | State | Exact gap |
|---|---|---|
| Current-main live fleet after #934/#935 | **missing** | The accepted live reports are at `ad6ecbd5d` (pre-#934) and a private #935 frozen replay; current main `a868435fd` was not re-run. |
| Current-main signed-in WorkDrive/document journey | **missing** | 56/56 is bound to `24794f257`; delete truth is hosted-selected, not live-replayed on current main. |
| Current-main Settings replay | **not re-run** | 29/29 is bound to `a53b56fdc`; later non-Settings paths changed, but no fresh run exists. |
| Current-main workbook/canvas browser | **not re-run** | 34,533.00 and 32/32 / 22/22 are bound to `6ad2738ed`; product files outside the listed change set did not change, but no fresh run exists. |
| Goal 10 48-hour resume | **not due / not run** | Gate is `2026-11-16T06:42:25.414033Z`; no resume report. |
| Goal 9 live settlement | **missing** | No live priced settlement/hard-stop evidence; #932 is draft. |
| Goal 11 live invoice | **missing** | #919 live leg unproven; simulator path only. |
| Goal 6 automatic skill invocation | **missing** | #937 approval gate is not auto-invocation; other worker active. |
| Goal 16 native menu bar live chat | **missing** | Native login/session/2FA and public-API live Go chat verified on the reviewed `#943` source; native UI chat pending. |
| Goal 16 native mobile device journey | **missing** | Hosted CI/Jest passed; no supported simulator/device native journey. |
| Goal 17 measurement | **missing** | No declared environment/workload/sample; cache-only benchmark is narrower. |
| Goal 18 full profile | **owner-deferred** | No force-enable decision/qualified breadth run. |
| Goal 14 whole-app ORACLE | **open** | Static inventory and scoped families only; no whole-app runtime coverage. |
| Goal 15 many exposed surfaces | **past-ledger only** | 2026-10-27 WA items were not re-run on current main; historical partial/unproven/failed rows are not current passes. |

## 9. Ledger relationships and original audit links

| Document | Role |
|---|---|
| [`APP_GOALS_INDEX.json`](APP_GOALS_INDEX.json) | Canonical 18 goals, explicit user requirements, historical quick reference. |
| [`APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json`](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json) | Machine-readable 143-claim audit: historical status, current disposition, evidence refs, gap, owner, next work order. |
| [`APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.md`](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.md) | Narrative audit; §7 is the 18-goal map. |
| [`APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json`](APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json) | Later web/SSO/performance reconciliation; dated source-bound updates. |
| [`CLAIM_INVENTORY.json`](../acceptance/readme_feature_readiness_2026-11-01/CLAIM_INVENTORY.json) | Frozen 143-claim denominator and historical 111/123 score. |
| [`WHOLE_APP_READINESS_LEDGER_2026-10-27.md`](../acceptance/WHOLE_APP_READINESS_LEDGER_2026-10-27.md) | Historical 91-item whole-app operational ledger; not the 143 claims. |
| [`PRODUCT_GOAL_LEDGER_2026-10-29.md`](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md) | Historical 12-row product-action ledger; not the 18 goals. |
| [`AGENT_GOAL_COMPLETION_DIRECTIVE_2026_11_06.md`](AGENT_GOAL_COMPLETION_DIRECTIVE_2026_11_06.md) | Delivery rules, documentation gate and goal-map history. |
| [`APP_COMPLETION_TAKEOVER_2026_11_10.md`](APP_COMPLETION_TAKEOVER_2026_11_10.md) | Continuity snapshot; older queue text is historical. |
| [`WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md`](../acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md) | Signed-in Settings method, history and 29/29 §8 result. |
| `/private/tmp/brennan-brief/READINESS_CURRENT_MAIN.md` | Newest appended operational evidence and private-run summaries; read with the rule that newest status supersedes stale PR state but not prior failures. |

## 10. Review notes and limits

- This document is **documentation only**. It did not run pytest, a browser,
  a server, a model, an installer or a dependency install. It did not read a
  live database or use a credential.
- Merged identities were read from local first-parent Git history. GitHub check
  status, review decisions and mergeability were **not** re-queried in this
  pass. Where CI is mentioned, it is from a retained packet or the handoff.
- Private paths under `/private/tmp` and `/Volumes` are recorded for
  traceability; they are not committed. Their contents may be deleted by their
  owners; the committed summary remains the durable record.
- The 143 claim rows and 18 goal rows are covered, but coverage is not
  completion. A row marked `baseline-verified` is a historical preservation,
  not a fresh pass. A row marked `bounded` is narrower than its original claim.
- The canonical score is still **111/123 (90.2%)**. This index deliberately
  does not add, subtract or extrapolate from later bounded evidence.
- Other workers own the menu bar live-chat and automatic skill-invocation
  lanes. This index records their accepted scope and open gates; it does not
  duplicate their runs or claim their unfinished work.

## Verifier update after the index pass

On the reviewed #943 head `5d1f11de4932292c45aa04b86c90d19fd8f634b1`, the real ASGI public menu bar quick-chat route returned `ATOM_LIVE_OK` from the subscribed OpenCode Go endpoint. The provider response identified `deepseek-v4.1-flash` with 79 input and 7 output tokens. The completed execution, successful menu bar audit and priced settled usage row persisted. All 42 PR files were independently verified byte-identical after merge `a868435fdcc7be66753366362d7542cc1082ce84`. This replay used TestClient and real middleware, not native UI chat typing. The first diagnostic call used the default Zen endpoint and returned 402; the successful call configured the supported Go base URL. Evidence: `/private/tmp/atom-menubar-live-chat-report.md` and `/private/tmp/atom-menubar-live-chat-evidence/` (private local artifacts).

The settled usage row has no `execution_id`, so this result does not close Goal 9 attribution. That gap has a separate implementation lane. The native UI chat journey remains open.

At transcription candidate #932 `818bd0fd960d71549af160288e4bf5482e5918fb`, a real local `openai/whisper-tiny.en` model decoded WAV, MP3, M4A, OGG and WebM and returned the expected text through LLMService/VoiceService only with a harness-injected local compatible client. The normal no-key configuration still has no supported local speech provider; its fallback reports transcription unavailable. The controlled billing suite passed 21 tests. Local calls priced at OpenAI's list rate are not remote billing evidence. No OpenAI key or cloud speech request was used. Evidence: `/private/tmp/atom-local-transcription-report.md` and `/private/tmp/atom-local-transcription-evidence/` (private local artifacts). This records a verified decoder and service-boundary result plus an unresolved configuration gap, not full local transcription readiness.
