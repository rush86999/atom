# Current goal map — 2026-11-17

**Navigation and remaining-acceptance overlay only.** This is not a new score,
not a completion declaration, and not a replacement for the original audit. It
preserves **143 original claim identities**, **18 canonical goals**, the
historical **111/123 functional result (90.2%)**, and `app_complete: false`.
No readiness percentage is invented, no claim is re-scored, and no bounded test
is promoted to whole-goal acceptance.

When this map was created, the current-tense banner in
[the November 14 readiness index](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md)
still named the #972 release cut and described #932/#919 as drafts after both
had merged; the banner now carries the current cut. The historical sections and
negative records in that index remain intact; this map is the current navigation
layer over them.

## Release facts at this cut

| Fact | Actual source |
|---|---|
| Observed main | `ba66f5e22db9f1755a8074adc256f4e978289b50` — CI/test scaffolds only (PR [#989](https://github.com/rush86999/atom/pull/989)); application bytes remain those of #986 `8afac828c` |
| Merged tree | `d967cc20beb8885309c693d82f0135ad24964582` |
| Sole parent | `8afac828c8d96d9b7773522fdcfc938ec2458fdc` (PR [#986](https://github.com/rush86999/atom/pull/986)) |
| #989 exact PR head | `0e1b9065e55d00e717db6a62e82fbdf25697683a` — all **17** check runs completed successfully; branch protections and rules verified unchanged. Root receipt: `/private/tmp/atom-pr989-root-actual-merge-verification-20261117.json` |
| #989 post-merge main | [Docker Build 44157075848](https://github.com/rush86999/atom/actions/runs/44157075848) recorded successful at this cut; [CI 44157075691](https://github.com/rush86999/atom/actions/runs/44157075691) still **pending** when this work order was cut. The root receipt at `2026-11-17T19:23:16Z` observed both as `in_progress`. No GitHub query was made by this worker, and the pending run is not described as successful |
| Structured wire contracts | PR [#980](https://github.com/rush86999/atom/pull/980) → `ecce2df80e1949083405eeb1e56a417dc5bbefee` |
| PostgreSQL existing-table lineage | PR [#981](https://github.com/rush86999/atom/pull/981) → `0ef449aeae4235b31ba0e1d7d83bdc1f585b07fe` |
| CI per-test durations | PR [#982](https://github.com/rush86999/atom/pull/982) → `708b7ae2dd1971b34a523a34dc887e9db736a21a` (reporting only) |
| Canvas historical wording | PR [#983](https://github.com/rush86999/atom/pull/983) → `fbabef87fe85a00f9d9fea9f97fd3c43c9c99752` (documentation only) |
| Explicit collaboration authority | PR [#984](https://github.com/rush86999/atom/pull/984) → `7f7952c65cd8014fcf60da6bce51720f85658ea9` |
| M3 canonical final reply | PR [#985](https://github.com/rush86999/atom/pull/985) → `7e51e097675943a72ebc31067187e17cdac505a2` |
| Task-profile isolation | PR [#986](https://github.com/rush86999/atom/pull/986) → `8afac828c8d96d9b7773522fdcfc938ec2458fdc` |
| CI lineage-preserving lanes | PR [#989](https://github.com/rush86999/atom/pull/989) → `ba66f5e22`; 79 post-setup core/extra step dictionaries unchanged and registered once across four lanes (19 / 20 / 14 / 26) |

### Retained prior-cut facts (unchanged records)

| Fact | Actual source |
|---|---|
| Preceding documentation cut | `1453f2cf42e822943e52390ef2c7b0d544609c20` (PR [#979](https://github.com/rush86999/atom/pull/979)); tree `7734fb38a8574963db90bc149f8367d2719b81ea`, parent `02c9b1674`. All 15 exact-head checks successful; post-merge main checks were pending at that cut and are not re-queried here |
| Learning merge | PR [#975](https://github.com/rush86999/atom/pull/975) → `7a22e6d0748057d80b4bf198fca9916e1ee55765` |
| Activity merge | PR [#976](https://github.com/rush86999/atom/pull/976) → `8b48dd84ad845e79c27bfcfa45cae669586d2b88` |
| Document authority merge | PR [#978](https://github.com/rush86999/atom/pull/978) → `02c9b16744e4fc9cfe7c81dce2ebf82cac7bf909`; exact PR head `8c142c101` had all **15** checks successful; actual Git tree and parent independently verified |
| #978 post-merge main | [CI 44011603158](https://github.com/rush86999/atom/actions/runs/44011603158) and [Docker 44011603162](https://github.com/rush86999/atom/actions/runs/44011603162) — both completed successfully at exact merge `02c9b1674`; independently re-queried on November 17 |
| Task-family merge | PR [#977](https://github.com/rush86999/atom/pull/977) → `0e9b0dfc9c7ee41b047714c1e1a5fc8a1f2bb464` |
| #977 exact PR head | `488e956c688383d2a220b05442fb47b51c8cc4f4` — all **15** check runs completed successfully (independently queried) |
| #977 post-merge main | [CI 43985428885](https://github.com/rush86999/atom/actions/runs/43985428885) and [Docker 43985428863](https://github.com/rush86999/atom/actions/runs/43985428863) — both completed successfully on exact merge `0e9b0dfc9`; root independently re-queried both runs on 2026-11-17 |
| #976 post-merge main | [CI 43950917401](https://github.com/rush86999/atom/actions/runs/43950917401) and [Docker 43950917434](https://github.com/rush86999/atom/actions/runs/43950917434) — both successful |
| #975 post-merge main | [CI 43934281143](https://github.com/rush86999/atom/actions/runs/43934281143) and [Docker 43934281125](https://github.com/rush86999/atom/actions/runs/43934281125) — both successful |

The merge/CI facts above are delivery status only. They do not qualify real-model
quality, PostgreSQL migration/runtime, deployment, application performance, or
any whole goal.

## Open queue at the 2026-11-17 work-order cut — dated and unqualified

These are **open candidates, not merged**, and they carry no acceptance credit
here. The detail is recorded only because it was current at the stated cut; it
may be stale and no CI state is asserted by this worker.

- PR #987: remote head `6973…`; a new current-main local `69f12…` root HTTP
  replay was reported as running at the cut.
- PR #988: remote head `4459e680d22fb688191436a81d1a6336e064eaa2`, **706 root CI checks passed**;
  CI checks and transfer of the old `1034…` synthetic product gate, with all
  `18927` non-CI tracked entries exact, were reported at the cut.

Later root review on November 17: #987's broader 16-file replay at local
`69f12d7388f9a141134dc9434d1244a08e965abe` finished with **1,424 passed and
59 failed**, with no errors or skips. Its 12 actor/history cases passed, but
the broader result remains **unqualified**, with causes under investigation.
That local head is not published and the earlier remote head remains open.
For #988, the 706 current-head checks and preceding 1,034-check gate overlap;
they are not an additive test total, and hosted CI is still required.

Later root CI observation on November 17: main #989's
[CI 44157075691](https://github.com/rush86999/atom/actions/runs/44157075691)
completed successfully at exact `ba66f5e22`. Its first attempt took 46m 14s
from workflow start to the last job finishing, compared with 68m 24s for
[main #986 CI 44141818847](https://github.com/rush86999/atom/actions/runs/44141818847)
at exact `8afac828c`. These are two observed successful hosted runs, not a
controlled benchmark: cache, runner contention and queue differences were not
normalized. This is delivery evidence, not application latency or Goal 17
acceptance. The earlier pending-at-cut record above remains historical.

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
- **historical repair** — a defect that was real at a named baseline and has a
  named merged repair plus bounded current controls; the old failure stays
  recorded and the repair is not whole-family acceptance.
- **delivery improvement** — a CI layout, timing or reporting change. It is not
  application latency, throughput or a performance claim.
- **requested / approved / executed / verified** — four distinct states. An
  actual correction that was applied and resolved is not the same as a change
  that was only requested, an approval that was granted, a run that started, or
  an independent verification that passed. Only the last, at the named scope,
  earns current evidence.
- **unknown** — no retained source, or another worker is in flight; no credit.

## All 18 goals plus DOCS-REF-01

| # | Goal | Audit state (unchanged) | Latest source-bound evidence and scope | Class | Concrete still-open user boundary |
|---:|---|---|---|---|---|
| 1 | Setup and ordinary account use | accepted-bounded | [Account browser lifecycle](ACCOUNT_BROWSER_LIFECYCLE_2026_11_16.md) @ `97e43`; [TOTP login/replay](ACCOUNT_TOTP_LOGIN_REPLAY_2026_11_16.md) @ candidate `268efd405`; [SMTP trust](SMTP_CERTIFICATE_VALIDATION_2026_11_16.md) merged #971; [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) login/settings | browser + API proof; merged auth | SSO/live IdP, rate-limit breadth, actual one-hour reset expiry, external mail delivery, other deployment audiences, and a current-main full-lifecycle replay. |
| 2 | BYOK and suitable model selection | accepted-bounded | [Audit ROUTE/GW rows](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [readiness §2](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#goal-2); #942 `d08892617` preserves query complexity; [structured wire contracts](STRUCTURED_WIRE_CONTRACTS_2026_11_17.md) merged #980 `ecce2df80` with 97 focused and 11 quota-caller offline controls | merged routing; merged endpoint-bound request contracts; **model-quality gap**; `ROUTE-07` external | Two or more real served models with requested/served identity and scored quality/cost, including capable Flash as first-class. [Case 7](FLEET_LIVE_COMPATIBILITY_2026_11_17.md) confirms one served Flash direct response, not a multi-model benchmark; its one-shot allowance is consumed. |
| 3 | Authorized common data and search | accepted-bounded | [Documents browser lifecycle](DOCUMENTS_BROWSER_LIFECYCLE_2026_11_16.md) @ `ed6ae3c98` (33KB synthetic TXT, all three downloads, delete/readback); [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) 88-byte TXT; WorkDrive 56/56 was bound to `24794f257` (readiness §11) | browser/API/restart proof, synthetic; **live connector gap**; [multi-format document API proof](DOCUMENT_SOURCE_AUTHORITY_2026_11_17.md) @ `0249f3eaa` (162 checks; DOCX/PDF/CSV) | Fresh-grant current-main WorkDrive replay; live connectors and model-grounded file answers; broader parser/format variants. `INT-09` remains external. [Multi-format browser and full restart](DOCUMENT_FORMAT_BROWSER_RESTART_2026_11_17.md) passed at `8c142c101`; live connector, generative grounding and parser breadth remain open. |
| 4 | Spreadsheet and calculation | accepted-bounded | [24-sheet workbook browser](WORKBOOK_BROWSER_LIFECYCLE_2026_11_16.md) @ `3316b0fe7` (exact 34,610 total, formula/cache checks, export before/after restart); full-population API replay 34,533 @ `6ad2738ed` (readiness §4) | browser + API proof, synthetic; **model/live-source gap** | Live connected source; model-driven extraction of the contributing population; reconciliation of ambiguous requests. The historical 1758.00 single-sheet counterexample remains retained. |
| 5 | Canvas and editable outputs | accepted-bounded | [PDF browser](PDF_CANVAS_BROWSER_LIFECYCLE_2026_11_16.md) @ `bb7017af3`; [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX pictures](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689` (merged #974) | browser + merged implementation | Full Canvas D2; other Canvas families; broader embedded media; cross-user ownership; Firecracker/KVM mini-app legs. Title/count-only renders are insufficient. |
| 6 | Teaching and reusable agent capability | accepted-bounded | [Learning correction/renewed approval](LEARNING_CORRECTION_REPROMOTION_2026_11_16.md) @ `1d4f409e1`, merged #975; [real-Docker ordinary skill dispatch](CURRENT_SKILL_DOCKER_ACCEPTANCE_2026_11_16.md) @ `3316b0fe7`; [scoped maturity](SCOPED_SKILL_MATURITY_2026_11_15.md) | browser + API/container proof; merged; **model-quality gap** | Independent real-model skill selection/consumption; unfamiliar-skill and unfamiliar-model work; generated-code promotion; a real browser/restart journey for approve→correct→renew that also covers keyboard-only, export and access checks; PostgreSQL concurrency. Scripted decisions do not establish model quality. |
| 7 | Assessment and unfamiliar work | accepted-bounded | [Audit ASK/ORACLE-06](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [historical product ledger](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md); deterministic 18/18 V1 and 19/19 V3 | deterministic proof; **model-quality failure** | New held-out/served-domain qualification and any general adaptive judgment claim. The deterministic path does not interpret arbitrary prose; `Q-012`/`Q-021` remain preserved failures. |
| 8 | Durable employee objectives | accepted-bounded | [Atomic Activity checkpoint decisions](ACTIVITY_CHECKPOINT_ATOMIC_DECISIONS_2026_11_16.md) @ `1f70c1708`, merged #976 (234 backend + 68 frontend controls; browser approve/reject/restart); [real 48-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0`; [goal-run WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968 | API/browser proof; merged; **model-quality gap** | Current-main ordinary-model objectives; event-order breadth; multi-worker/soak; full TASK-WAIT-01 integration. The Activity fixture goals were already achieved, so model competence is not proven. |
| 9 | Runtime configured-budget enforcement | accepted-bounded | [PR #932](https://github.com/rush86999/atom/pull/932) merged `ab14eb391` (Whisper duration/billing and settlement controls; joint 360-test qualification); historical #722 `5b9610b56` | merged implementation; controlled proof; **live/operator gap** | One priced `TokenUsage` row, matching tenant spend delta, idempotent duplicate settle, and a second dispatch refused before transport when short. Whisper live/remote settlement and PostgreSQL remain unproven. No live spend is authorized. |
| 10 | TASK-WAIT-01 long tasks pause/resume | open | [Real 48.0203-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0` (same job/execution, one effect, duplicate/late-answer refusal); [WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968; multi-source run @ `ad6ecbd5d` | process/API proof; **current-main/model/operator gap** | Ordinary UI; current-main real-model work; partial and independent progress; revocation/cancellation during the wait; all supported surfaces; multi-worker/soak. Arrival alone is not completion. Never rearm the terminal elapsed-wait case. |
| 11 | Documents, presentations and email drafts | accepted-bounded | [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689`; #919 merged `9de6ef33` (loopback path only) | browser proof for documents; **provider/email unknown** | Ordinary presentation and email-draft journey; provider draft readback; real recipient inbox delivery; authorized live invoice replay. The one-use live send authority is exhausted. |
| 12 | Repeatable workflows and schedules | accepted-bounded | Public workflow scope `49d45c7f3`; scheduler `78d2e0ca8`; recovery `e2ba4b01c`; ORCH-01 `0fae2d46c`; [readiness §12](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#goal-12) | merged + controlled proof; **served-model/operator gap** | One real served workflow request through the production route/deadline path; a full scheduled real-workflow result and receipt; PostgreSQL/multi-worker/soak. ORCH-01 still uses a controlled LLM double. |
| 13 | Fleet, goals and background work | accepted-bounded | [Real fleet delegation, incomplete answer](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#fleet-real-delegation-incomplete-deliverable) @ `a868435fd` (#943, final answer not accepted); one capped synthesis sample (#951); [fleet diagnostics](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md#fleet-diagnostics-remain-separate-from-application-acceptance) (capped live test failed; 11 offline fault controls, including 17 attempted / 16 synthetic send starts) | merged implementation; scripted/API proof; **live workflow failed**; broader model quality **unknown** | Current-main live TASK with a real model, one in-scope chain, complete attributed final answer, restart/durable state, no shadow success or out-of-scope specialist. Case 6 remains **FAILED**. [Case 7](FLEET_LIVE_COMPATIBILITY_2026_11_17.md) also failed fleet acceptance: 14 actual upstream requests, 13 structured HTTP 400 and one correct direct Flash reply; verifier error-contract limits prevent a definitive upstream-cause claim. Its allowance is consumed; no automatic rerun. [Case 8](FLEET_LIVE_DELEGATION_2026_11_17.md) recovered the optional-logprob rejection and completed structured calls on merged main `02c9b1674`, but chose direct conversation: zero specialist chains/links. Six starts stayed within the cap; its one-shot allowance is consumed. [Explicit collaboration authority](EXPLICIT_COLLABORATION_AUTHORITY_2026_11_17.md) merged later at #984 `7f7952c65` carries an accepted specialist requirement into the existing fleet lane with 85 offline checks; case 8's source predates it, so it is not a live delegation pass and needs a fresh allowance. The old 43-case scripted pass remains source-bound, not a current live pass. |
| 14 | Direct mutations and whole-app ORACLE | open | Activity checkpoint authority (#976) and [never-autonomous task fences](NEVER_AUTONOMOUS_TASK_BASKETS_2026_11_16.md) (#977) are scoped mutation/authority families; static inventory 836/371/311; merged families #650–#695; Canvas delete/undelete current-actor authority repaired by [#763](https://github.com/rush86999/atom/pull/763) `c97dada13` | merged scoped implementation; **whole-app runtime unknown** | Every reachable mutation family enforcing current authority/material, exact operation, durable effect and independent readback; replay/rollback/unknown truth; refreshed current-main inventory; PostgreSQL/multi-worker. The four historical delete/undelete scope failures stay preserved at their baseline; 54 bounded current controls pass, which does not qualify every Canvas route or whole-app ORACLE ([reconciliation](CANVAS_LIFECYCLE_AUTHORITY_RECONCILIATION_2026_11_17.md)). Adjacent bounded authority controls merged later: [entry task-profile isolation](NEVER_AUTONOMOUS_TASK_PROFILE_ISOLATION_2026_11_17.md) #986 `8afac828c` (737 independent checks; SQLite only), [M3 canonical final reply](../architecture/orchestration_migration/acceptance/lane3/M3_CANONICAL_DELIVERY_PROOF.md) #985 `7e51e0976` (22 public-boundary controls; flag default OFF), and [durable collaboration pending authority](EXPLICIT_COLLABORATION_AUTHORITY_2026_11_17.md) #984 `7f7952c65` (85 offline checks). |
| 15 | Remaining exposed application | open/partial | [Web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) core pages render; [signed-in Settings](../acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md) 29/29 @ `a53b56fdc`; Canvas list 22/22 @ `6ad2738ed`; Tasks/Projects #797 `3541e8115` | browser proof, partial; **deferred scope**; many surfaces **unknown** | Primary action + durable readback on Tasks/Boards, marketplace install, search, finance/voice/BPE/settings/skill editor/team chat, blocked-route errors, and direct admin/member behavior. Tasks/Boards are owner-deferred by the core release profile and must not be force-enabled. |
| 16 | Installation, compatibility and operations | open | [Persistent PostgreSQL restart](POSTGRES_PERSISTENT_RESTART_2026_11_16.md) @ `3316b0fe7`; [logical restore](POSTGRES_LOGICAL_RESTORE_2026_11_16.md) @ `c1ab1af1`; [full-app restart](POSTGRES_FULLAPP_RESTART_2026_11_16.md); [fresh bootstrap](POSTGRES_FRESH_BOOTSTRAP_2026_11_16.md) @ `5aa8c1c8`; #936/#941/#943 | bounded operator/deployment proof; merged; **unknown breadth** | [Document-lineage existing-table revision](POSTGRES_DOCUMENT_LINEAGE_UPGRADE_2026_11_17.md) merged #981 `0ef449aea` with a bounded PostgreSQL 14.24 proof (29 independent tests including one real cluster, clean restart/data/index preservation) for that single revision. Other existing upgrades, full migration graph/app upgrade, async transport, abrupt outage, cluster/PITR, multi-worker/soak, Linux/ARM, native mobile device, menu-bar native live chat, KVM, and full rollback/restore child flow. #977 exercised only SQLite migration, not PostgreSQL. |
| 17 | Performance and comparative promises | unverified | [Audit PERF/MKT rows](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [performance reconciliation](APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json); cache-only benchmark `dd2610502` (37 tests) | **unknown** — no declared measurement | Reproducible measurement with declared environment, workload, sample size and command; dated source for every comparative/pricing claim. A cache-only test is not app throughput or model quality. No invented numbers. CI delivery work is explicitly **not** app performance: #982 adds `--durations=20` reporting only, and #989 repartitions lanes with an **estimated** 42.6-minute critical lane, +5.7 runner-minutes and no measured speedup or whole-app latency result. |
| 18 | Profile breadth | open/deferred | `CORE-07` profile switch; [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) confirms core defers Tasks/Boards; [goal catalogue](APP_GOALS_INDEX.json) explicit requirements | **deferred scope** | Explicit owner decision on full-profile enablement and qualified journeys for the restored surfaces. Do not force-enable deferred profiles or add SaaS gates to close the row. |
| — | **DOCS-REF-01** documentation and diagrams | open (additional closure requirement) | [Frozen reference inventory](reference_inventory_ac2b73778_20261108.json): 1,729 reference files, 11 diagram candidates, 633 image/PDF candidates at `ac2b73778`. This map is navigation only. | inventory only; **accuracy unknown** | Complete classification of every reference/diagram with owner and canonical destination; accurate user/operator paths; architecture diagrams with render + semantic review; API/config reference; reproducible safe commands; final no-contradiction acceptance audit. Inventory counts are not accuracy or rendering passes. |

**DOCS-REF-01 validation note:** an inventory run at product source
`0e9b0dfc9` during this pass (not committed) counts 1,934 reference files, 13
diagram candidates and 681 image/PDF candidates; the frozen `ac2b73778` counts
above remain the preserved historical baseline. A repository-wide link check
still reports pre-existing broken links in files outside this overlay; the
changed-file scan is clean. Neither result closes DOCS-REF-01.

## What the #975–#989 deliveries do and do not establish

| Delivery | Source-bound scope | Does not establish |
|---|---|---|
| **#989 CI lineage-preserving lanes** | Four backend core lanes (19 / 20 / 14 / 26 post-setup steps) with all 79 existing step dictionaries byte-identical and registered once; `backend-tests` still needs all six backend lanes and adds no retry/skip/soft gate. Local contract run 706 passed. README records an **estimated** 42.6-minute critical lane and +5.7 runner-minutes, with the unmetered M3 caveat and concurrency/queueing limit. Merged at `ba66f5e22`; exact PR head `0e1b9065e` had all 17 checks successful. | Any measured speedup or app latency; a post-merge main result for CI `44157075691` (pending at this cut); runtime behavior of the product merges it now schedules; Goal 17. |
| **#986 task-profile isolation** | Product/tests at #986; root independently ran the six whole policy files plus CI preservation and quickstart contracts: **737 passed**; wider five-file set **281 passed / 1 failed**, the failure reproducing on unchanged main; all 251 original assertions preserved. Real-entry isolation covers both `GenericAgent.execute` and `WorkflowEngine._run_execution` plus the dict-scoped meta entry. | PostgreSQL or multi-worker; any live app entry observed hitting the double builder fault; reviewer approval path; browser/UI; model quality. SQLite and synthetic fault injection only. |
| **#985 M3 canonical final reply** | `chat_orchestrator.py` at #985; 22 public-boundary controls (real router/JWT/reply leg/WS frames/fresh durable row, only model outputs, memory, planner and transport doubled), plus 110 passed with the 2 pre-existing strict XFAILs; empty-withheld fail-closed follow-up retained with its failing baselines. | Whole-app semantic truth; vocabulary outside the frozen legacy and M3 matchers; mid-stream release of a claim split across already-released chunks; `CHAT_FINALIZATION_M3` stays default **OFF**; non-canvas turns. |
| **#984 explicit collaboration authority** | Frozen source `d2d6cb204`; 85 focused checks (9 public-HTTP + 28 semantics + 48 pending authority) and 642 CI-preservation controls offline. Carries an accepted `collaboration` requirement through the one shared structured interpreter into the governed fleet lane, preserves master/pilot/shadow gates, and adds durable pending CAS plus one canonical conversation id. | Live model quality, browser journey or current-main acceptance; a fresh manager/orchestrator is not a whole-app restart; PostgreSQL breadth (12 shared-method checks only); fleet cases 6/7/8 remain **FAILED** with allowances consumed. Cross-caller behavior change in `update_session_metadata`. |
| **#983 Canvas historical wording** | Documentation-only correction at `fbabef87f`; 54 bounded controls at actual current-main Canvas bytes (application source `ecce2df80`; executed tree head `c029470c0` differs only by CI `--durations=20` flag lines). Four historical failures relabelled as repaired, not rewritten. | Every Canvas route/family, legacy direct-tool path, whole-app ORACLE, Goal 5 or Goal 14; login/browser, PostgreSQL or multi-worker. |
| **#982 per-test durations** | `--durations=20` added to five existing pytest invocations in three heavy steps; 642 lane/matrix contract checks passed; stripping the flag restores each command byte-for-byte. | Any speedup, selection change, timeout change or performance claim. Reporting only. |
| **#981 PostgreSQL document-lineage upgrade** | Qualified source `51fedc077` against migration source `02c9b1674`; 29 tests including one private PostgreSQL 14.24 cluster; upgrade/downgrade/idempotence/repair/restart and SQLSTATE 23505 uniqueness before and after restart. | Any other migration, the full Alembic graph, app runtime on PostgreSQL, concurrency, other versions/platforms, PITR or production. Hosted CI runs the database-free controls with the real case visibly skipped. |
| **#980 structured wire contracts** | Product `739538368`; 97 focused plus 11 existing quota-caller offline controls with network denied; endpoint-bound family declarations for native deepseek and the exact `opencode-go` v4-pro route, with unknown routes keeping historical payloads and reactive recovery. | Live provider behavior or quality; the cause of fleet case 7's upstream 400s; case 8's missing delegation; latency or cost comparison. |

### Earlier deliveries retained

| Delivery | Source-bound scope | Does not establish |
|---|---|---|
| **#978 document source authority** | Product `0249f3eaa`, root **162 checks** and real authenticated DOCX/PDF/CSV API replay; later browser/restart proof at exact PR head `8c142c101`; merged tree independently verified. | Live WorkDrive; model-driven grounding; original binaries; parser breadth; PostgreSQL runtime; whole Goal 3/4. |
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
- The source-bound Goal 3 API and later browser/restart proofs remain small
  synthetic cases; they do not establish live connectors or model quality.
- The old 43-case scripted fleet pass is **not** a current real-model fleet pass;
  cases 6, 7 and 8 failed fleet acceptance; their one-shot
  allowances are consumed. A correct direct reply is not completed delegation.
- The #984 collaboration path is **not** a live fleet pass: it reproduces the
  missing requirement semantics offline, and its 85 checks do not qualify model
  answer quality, specialist recruitment judgment or a browser journey.
- #985's canonical final-text boundary is **not** whole-app truthfulness: it is a
  limited-vocabulary guard whose flag remains default OFF.
- #986's isolated SQLite entries and synthetic double-builder faults are **not**
  PostgreSQL, multi-worker or a live runtime observation.
- #981's single-revision PostgreSQL 14.24 run is **not** migration breadth,
  full-graph upgrade, app-on-PostgreSQL or concurrency.
- #982 timing output and #989 lane partitioning are **delivery and observability**,
  not application performance, throughput or Goal 17; #989's lane budget is
  explicitly an estimate and no speedup is claimed.
- The frozen documentation inventory is **not** DOCS-REF-01 closure.
- An open PR in the dated queue (for example #987/#988 at the work-order cut) is
  **not** merged and carries no acceptance, even when its author reports local
  or root runs.

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
- The #983 Canvas correction, #984 collaboration record, #985 M3 addendum and
  #986 profile-isolation record relabel or bound current-tense claims only. The
  original `27a1830a2`/`8e4b494d7`/`ccaa92ba3` packets, the 175/2 affected-suite
  result, strict XFAILs, `Q-012`/`Q-021` and every retained failure stay as
  published.
- #989 did not edit, merge, split or deselect a test step and did not change
  branch protection; its contract suite proves preservation, not runtime speed.

## Original overlay source and validation basis

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

## Navigation refresh at #989 (this pass)

- Local checkout: branch `codex/readiness-navigation-refresh-20261117` at
  `ba66f5e22db9f1755a8074adc256f4e978289b50`, tree
  `d967cc20beb8885309c693d82f0135ad24964582`, sole parent
  `8afac828c8d96d9b7773522fdcfc938ec2458fdc`; worktree clean before editing.
  First-parent history `1453f2cf4 → ecce2df80 → 0ef449aea → 708b7ae2d →
  fbabef87f → 7f7952c65 → 7e51e0976 → 8afac828c → ba66f5e22` was read in
  order, and each delivery's own doc/test files were read for scope rather than
  inferred from its title.
- Root receipt `/private/tmp/atom-pr989-root-actual-merge-verification-20261117.json`
  (`verified_at 2026-11-17T19:23:16Z`) supplied the 17 exact-head check results,
  the merge/tree/sole-parent identity and the unchanged-protection result. It
  also observed both new main runs as `in_progress`; the later work-order cut
  records Docker `44157075848` successful and CI `44157075691` still pending.
  Neither this file nor its commit queries GitHub or claims the pending run.
- Scope of this pass: documentation and reference checks only — no app, server,
  browser, test run, provider/model call, PostgreSQL cluster, install, data,
  credential or portable-media write. No product, CI, test, schema, policy or
  configuration byte changed.
- New bounded evidence above does not change the original audit, the 143 claim
  identities, the 18 goal states or `app_complete: false`.
