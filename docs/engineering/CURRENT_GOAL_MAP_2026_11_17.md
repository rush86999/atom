# Current goal map — 2026-11-17

**Navigation and remaining-acceptance overlay only.** This is not a new score,
not a completion declaration, and not a replacement for the original audit. It
preserves **143 original claim identities**, **18 canonical goals**, the
historical **111/123 functional result (90.2%)**, and `app_complete: false`.
No readiness percentage is invented, no claim is re-scored, and no bounded test
is promoted to whole-goal acceptance.

It exists because the current-tense banner in
[the November 14 readiness index](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md)
still named the #972 release cut and described #932/#919 as drafts after both
had merged. The historical sections and negative records in that index remain
intact; this map is the current navigation layer over them.

## Release facts at this cut

| Fact | Actual source |
|---|---|
| Observed main | `0e9b0dfc9c7ee41b047714c1e1a5fc8a1f2bb464` (PR [#977](https://github.com/rush86999/atom/pull/977)) |
| Merged tree | `9386a4861e9ed2fef14d96fda64fc5cedba6b3b3` |
| Parent | `8b48dd84ad845e79c27bfcfa45cae669586d2b88` (PR [#976](https://github.com/rush86999/atom/pull/976)) |
| Learning merge | PR [#975](https://github.com/rush86999/atom/pull/975) → `7a22e6d0748057d80b4bf198fca9916e1ee55765` |
| Activity merge | PR [#976](https://github.com/rush86999/atom/pull/976) → `8b48dd84ad845e79c27bfcfa45cae669586d2b88` |
| Task-family merge | PR [#977](https://github.com/rush86999/atom/pull/977) → `0e9b0dfc9c7ee41b047714c1e1a5fc8a1f2bb464` |
| #977 exact PR head | `488e956c688383d2a220b05442fb47b51c8cc4f4` — all **15** check runs completed successfully (independently queried) |
| #977 post-merge main | [CI 43985428885](https://github.com/rush86999/atom/actions/runs/43985428885) and [Docker 43985428863](https://github.com/rush86999/atom/actions/runs/43985428863) — both completed successfully on exact merge `0e9b0dfc9`; root independently re-queried both runs on 2026-11-17 |
| #976 post-merge main | [CI 43950917401](https://github.com/rush86999/atom/actions/runs/43950917401) and [Docker 43950917434](https://github.com/rush86999/atom/actions/runs/43950917434) — both successful |
| #975 post-merge main | [CI 43934281143](https://github.com/rush86999/atom/actions/runs/43934281143) and [Docker 43934281125](https://github.com/rush86999/atom/actions/runs/43934281125) — both successful |

The merge/CI facts above are delivery status only. They do not qualify real-model
quality, PostgreSQL migration/runtime, deployment, or any whole goal.

## Status vocabulary used below

- **merged implementation** — commit is in first-parent main; merge is not
  acceptance.
- **API proof** / **browser proof** — source-bound execution at the named source
  and scope.
- **model-quality gap** — no real-model served comparison or unfamiliar-work
  qualification.
- **operator/deployment gap** — PostgreSQL breadth, multi-worker/soak, native
  device, KVM, or deployment is not established.
- **deferred scope** — owner-deferred product scope (not a pass and not a
  current failure merely because it is absent).
- **unknown** — no retained source, or another worker is in flight; no credit.

## All 18 goals plus DOCS-REF-01

| # | Goal | Audit state (unchanged) | Latest source-bound evidence and scope | Class | Concrete still-open user boundary |
|---:|---|---|---|---|---|
| 1 | Setup and ordinary account use | accepted-bounded | [Account browser lifecycle](ACCOUNT_BROWSER_LIFECYCLE_2026_11_16.md) @ `97e43`; [TOTP login/replay](ACCOUNT_TOTP_LOGIN_REPLAY_2026_11_16.md) @ candidate `268efd405`; [SMTP trust](SMTP_CERTIFICATE_VALIDATION_2026_11_16.md) merged #971; [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) login/settings | browser + API proof; merged auth | SSO/live IdP, rate-limit breadth, actual one-hour reset expiry, external mail delivery, other deployment audiences, and a current-main full-lifecycle replay. |
| 2 | BYOK and suitable model selection | accepted-bounded | [Audit ROUTE/GW rows](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [readiness §2](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#goal-2); #942 `d08892617` preserves query complexity | merged routing; **model-quality gap**; `ROUTE-07` external | Two or more real served models with requested/served identity and scored quality/cost, including capable Flash as first-class. No new key or spend authority. |
| 3 | Authorized common data and search | accepted-bounded | [Documents browser lifecycle](DOCUMENTS_BROWSER_LIFECYCLE_2026_11_16.md) @ `ed6ae3c98` (33KB synthetic TXT, all three downloads, delete/readback); [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) 88-byte TXT; WorkDrive 56/56 was bound to `24794f257` (readiness §11) | browser/API proof, synthetic; **live connector gap**; [multi-format document API proof](DOCUMENT_SOURCE_AUTHORITY_2026_11_17.md) @ `0249f3eaa` (162 checks; DOCX/PDF/CSV) | Fresh-grant current-main WorkDrive replay; multi-format upload/open/search/export/delete and grounding; live connector qualification. `INT-09` remains external. The multi-format API proof does not close the ordinary-browser, restart or live-connector gaps. |
| 4 | Spreadsheet and calculation | accepted-bounded | [24-sheet workbook browser](WORKBOOK_BROWSER_LIFECYCLE_2026_11_16.md) @ `3316b0fe7` (exact 34,610 total, formula/cache checks, export before/after restart); full-population API replay 34,533 @ `6ad2738ed` (readiness §4) | browser + API proof, synthetic; **model/live-source gap** | Live connected source; model-driven extraction of the contributing population; reconciliation of ambiguous requests. The historical 1758.00 single-sheet counterexample remains retained. |
| 5 | Canvas and editable outputs | accepted-bounded | [PDF browser](PDF_CANVAS_BROWSER_LIFECYCLE_2026_11_16.md) @ `bb7017af3`; [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX pictures](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689` (merged #974) | browser + merged implementation | Full Canvas D2; other Canvas families; broader embedded media; cross-user ownership; Firecracker/KVM mini-app legs. Title/count-only renders are insufficient. |
| 6 | Teaching and reusable agent capability | accepted-bounded | [Learning correction/renewed approval](LEARNING_CORRECTION_REPROMOTION_2026_11_16.md) @ `1d4f409e1`, merged #975; [real-Docker ordinary skill dispatch](CURRENT_SKILL_DOCKER_ACCEPTANCE_2026_11_16.md) @ `3316b0fe7`; [scoped maturity](SCOPED_SKILL_MATURITY_2026_11_15.md) | browser + API/container proof; merged; **model-quality gap** | Independent real-model skill selection/consumption; unfamiliar-skill quality; generated-code promotion; PostgreSQL concurrency. Scripted decisions do not establish model quality. |
| 7 | Assessment and unfamiliar work | accepted-bounded | [Audit ASK/ORACLE-06](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [historical product ledger](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md); deterministic 18/18 V1 and 19/19 V3 | deterministic proof; **model-quality failure** | New held-out/served-domain qualification and any general adaptive judgment claim. The deterministic path does not interpret arbitrary prose; `Q-012`/`Q-021` remain preserved failures. |
| 8 | Durable employee objectives | accepted-bounded | [Atomic Activity checkpoint decisions](ACTIVITY_CHECKPOINT_ATOMIC_DECISIONS_2026_11_16.md) @ `1f70c1708`, merged #976 (234 backend + 68 frontend controls; browser approve/reject/restart); [real 48-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0`; [goal-run WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968 | API/browser proof; merged; **model-quality gap** | Current-main ordinary-model objectives; event-order breadth; multi-worker/soak; full TASK-WAIT-01 integration. The Activity fixture goals were already achieved, so model competence is not proven. |
| 9 | Runtime configured-budget enforcement | accepted-bounded | [PR #932](https://github.com/rush86999/atom/pull/932) merged `ab14eb391` (Whisper duration/billing and settlement controls; joint 360-test qualification); historical #722 `5b9610b56` | merged implementation; controlled proof; **live/operator gap** | One priced `TokenUsage` row, matching tenant spend delta, idempotent duplicate settle, and a second dispatch refused before transport when short. Whisper live/remote settlement and PostgreSQL remain unproven. No live spend is authorized. |
| 10 | TASK-WAIT-01 long tasks pause/resume | open | [Real 48.0203-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0` (same job/execution, one effect, duplicate/late-answer refusal); [WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968; multi-source run @ `ad6ecbd5d` | process/API proof; **current-main/model/operator gap** | Ordinary UI; current-main real-model work; partial and independent progress; revocation/cancellation during the wait; all supported surfaces; multi-worker/soak. Arrival alone is not completion. Never rearm the terminal elapsed-wait case. |
| 11 | Documents, presentations and email drafts | accepted-bounded | [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689`; #919 merged `9de6ef33` (loopback path only) | browser proof for documents; **provider/email unknown** | Ordinary presentation and email-draft journey; provider draft readback; real recipient inbox delivery; authorized live invoice replay. The one-use live send authority is exhausted. |
| 12 | Repeatable workflows and schedules | accepted-bounded | Public workflow scope `49d45c7f3`; scheduler `78d2e0ca8`; recovery `e2ba4b01c`; ORCH-01 `0fae2d46c`; [readiness §12](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#goal-12) | merged + controlled proof; **served-model/operator gap** | One real served workflow request through the production route/deadline path; a full scheduled real-workflow result and receipt; PostgreSQL/multi-worker/soak. ORCH-01 still uses a controlled LLM double. |
| 13 | Fleet, goals and background work | accepted-bounded | [Real fleet delegation, incomplete answer](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#fleet-real-delegation-incomplete-deliverable) @ `a868435fd` (#943, final answer not accepted); one capped synthesis sample (#951); [fleet diagnostics](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md#fleet-diagnostics-remain-separate-from-application-acceptance) (capped live test failed; 11 offline fault controls, including 17 attempted / 16 synthetic send starts) | merged implementation; scripted/API proof; **model-quality failure**; current live pass **unknown** | Current-main live TASK with a real model, one in-scope chain, complete attributed final answer, restart/durable state, no shadow success or out-of-scope specialist. Root reports case 6 live **FAILED** and the 16-admission guard consumed; no new provider allowance. The old 43-case scripted pass remains source-bound, not a current live pass. |
| 14 | Direct mutations and whole-app ORACLE | open | Activity checkpoint authority (#976) and [never-autonomous task fences](NEVER_AUTONOMOUS_TASK_BASKETS_2026_11_16.md) (#977) are scoped mutation/authority families; static inventory 836/371/311; merged families #650–#695 | merged scoped implementation; **whole-app runtime unknown** | Every reachable mutation family enforcing current authority/material, exact operation, durable effect and independent readback; replay/rollback/unknown truth; refreshed current-main inventory; PostgreSQL/multi-worker. The four retained delete/undelete failures remain. |
| 15 | Remaining exposed application | open/partial | [Web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) core pages render; [signed-in Settings](../acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md) 29/29 @ `a53b56fdc`; Canvas list 22/22 @ `6ad2738ed`; Tasks/Projects #797 `3541e8115` | browser proof, partial; **deferred scope**; many surfaces **unknown** | Primary action + durable readback on Tasks/Boards, marketplace install, search, finance/voice/BPE/settings/skill editor/team chat, blocked-route errors, and direct admin/member behavior. Tasks/Boards are owner-deferred by the core release profile and must not be force-enabled. |
| 16 | Installation, compatibility and operations | open | [Persistent PostgreSQL restart](POSTGRES_PERSISTENT_RESTART_2026_11_16.md) @ `3316b0fe7`; [logical restore](POSTGRES_LOGICAL_RESTORE_2026_11_16.md) @ `c1ab1af1`; [full-app restart](POSTGRES_FULLAPP_RESTART_2026_11_16.md); [fresh bootstrap](POSTGRES_FRESH_BOOTSTRAP_2026_11_16.md) @ `5aa8c1c8`; #936/#941/#943 | bounded operator/deployment proof; merged; **unknown breadth** | Existing upgrades, async transport, abrupt outage, cluster/PITR, multi-worker/soak, Linux/ARM, native mobile device, menu-bar native live chat, KVM, and full rollback/restore child flow. #977 exercised only SQLite migration, not PostgreSQL. |
| 17 | Performance and comparative promises | unverified | [Audit PERF/MKT rows](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [performance reconciliation](APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json); cache-only benchmark `dd2610502` (37 tests) | **unknown** — no declared measurement | Reproducible measurement with declared environment, workload, sample size and command; dated source for every comparative/pricing claim. A cache-only test is not app throughput or model quality. No invented numbers. |
| 18 | Profile breadth | open/deferred | `CORE-07` profile switch; [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) confirms core defers Tasks/Boards; [goal catalogue](APP_GOALS_INDEX.json) explicit requirements | **deferred scope** | Explicit owner decision on full-profile enablement and qualified journeys for the restored surfaces. Do not force-enable deferred profiles or add SaaS gates to close the row. |
| — | **DOCS-REF-01** documentation and diagrams | open (additional closure requirement) | [Frozen reference inventory](reference_inventory_ac2b73778_20261108.json): 1,729 reference files, 11 diagram candidates, 633 image/PDF candidates at `ac2b73778`. This map is navigation only. | inventory only; **accuracy unknown** | Complete classification of every reference/diagram with owner and canonical destination; accurate user/operator paths; architecture diagrams with render + semantic review; API/config reference; reproducible safe commands; final no-contradiction acceptance audit. Inventory counts are not accuracy or rendering passes. |

**DOCS-REF-01 validation note:** an inventory run at product source
`0e9b0dfc9` during this pass (not committed) counts 1,934 reference files, 13
diagram candidates and 681 image/PDF candidates; the frozen `ac2b73778` counts
above remain the preserved historical baseline. A repository-wide link check
still reports pre-existing broken links in files outside this overlay; the
changed-file scan is clean. Neither result closes DOCS-REF-01.

## What the #975–#977 deliveries do and do not establish

| Delivery | Source-bound scope | Does not establish |
|---|---|---|
| **#977 optional never-autonomous task families** | Product source `d271e25eb`; independent root **319 backend** checks, **642 CI-contract** checks, **110 UI** checks plus TypeScript/build; ordinary browser empty/default rule CRUD, two-tab stale-save 409, restart readback, exact synthetic task approval, and cold receipt that accepts only the unchanged task and refuses changed material. Merged at `0e9b0dfc9`. | Real-model output quality; a completed worker run; PostgreSQL migration (only SQLite migration exercised); every integration approval surface. |
| **#976 Activity checkpoint decisions** | Product source `1f70c1708`; 234 backend and 68 frontend controls; ordinary browser approve/reject and restart; atomic stale-claim refusal and current reviewer authority across callers. Merged at `8b48dd84a`. | Model competence; goal evaluator work (fixture goals were already achieved); every approval family; PostgreSQL concurrency. |
| **#975 Learning correction** | Product source `1d4f409e1`; 162 backend, 12 frontend, 642 CI-contract checks; correction/repromotion and exact 15 USD deterministic reuse after full-stack restart. Merged at `7a22e6d07`. | Live model quality; external indexed resources; PostgreSQL concurrency; broader Learning. |
| **#974 inline DOCX pictures** | Product source `8d98b0689`; 674 focused checks; real drawing XML/references and decoded pixels preserved through native edits and restart. Merged at `7316a0155`. | Every drawing/media case; all Office families; whole Goal 5. |
| **#973 evidence record** | Documentation-only merge at `5fd0560f3` for browser, PostgreSQL restart and skill-execution records. | No new product behavior; no widened runtime scope. |

## What a reader must not infer

- A merged PR, a green exact-head check, or a passing bounded suite is **not**
  whole-goal or whole-app acceptance.
- #977's 319/642/110 checks and synthetic browser journey are **not** a
  readiness percentage and **not** real-model quality.
- #977's exact-head and post-merge main CI successes are delivery evidence,
  not a substitute for broader user-boundary or real-model acceptance.
- A SQLite migration pass is **not** PostgreSQL migration or concurrency.
- The source-bound Goal 3 multi-format API proof is bounded acceptance; it
  does not establish a multi-format browser journey, restart or live connector.
- The old 43-case scripted fleet pass is **not** a current real-model fleet pass;
  the current case 6 live attempt failed and the 16-admission guard was consumed.
- The frozen documentation inventory is **not** DOCS-REF-01 closure.

Account deletion is a separately inferred possible improvement, not an original
143-claim requirement or an added completion gate for Goal 1.

## Preserved, not reopened

- Original 143 claim identities, 18 goal rows, historical **111/123 (90.2%)**
  and `app_complete: false` are unchanged.
- Original audit JSON, claim IDs, source pointers, negative captures and
  retained failed attempts are not rewritten in this pass.
- Owner-deferred Tasks/Boards and full-profile breadth remain deferred; web
  delivery remains first and mobile remains last.
- No app, browser, provider, credential, dependency install, deployment or
  private packet was used. No stable campaign was rerun to refresh a date.
- The November 14 readiness index remains the detailed claim/evidence ledger;
  only its current-tense release banner and stale #932/#919 draft labels are
  corrected to point at this map.

## Source and validation basis

- Local Git: product source cut `0e9b0dfc9...`, tree `9386a486...`, parent
  `8b48dd84a`; first-parent history and `origin/main` agreed. The documentation
  commit that adds this file is docs-only and changes no product tree bytes.
- Public repository read: PRs #975/#976/#977 are merged at the recorded
  commits; the #977 exact head `488e956...` has 15/15 successful check runs;
  main post-merge run states are recorded above without promoting them.
- Recent source docs were traced in place; no stable browser/model/PostgreSQL
  campaign was rerun.
- Reference/path checks are reported in the worker summary that accompanies
  this commit. This file adds no product source, CI, policy or configuration
  change.
