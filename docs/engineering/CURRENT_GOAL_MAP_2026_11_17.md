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

## Release facts at this cut — merged #994 (2026-11-18)

| Fact | Actual source |
|---|---|
| Observed main | `d701872287b16f1e74b512aa7b81fb40b92fe69a` — Make audit evidence and Learning corrections traceable (PR [#994](https://github.com/rush86999/atom/pull/994)); tree `fa66625df9423938e190d17c3425ed59d4e4ffb6`, sole parent `a33e8d8ab9352fa59324ebc067772fea4efe24d2` (#993) |
| #994 exact PR head | `b57be40f5183c294c91f81e659e1518a7daaf8dd` — all **17** exact-head checks successful; merge tree equals the PR-head tree. Receipts: `/private/tmp/atom-pr994-final-merge-receipt.json` and `/private/tmp/atom-pr994-qualified-merge-result-20261117.json` |
| #994 qualified scope | **520 browser assertions** and **34 acceptance cases** across the audit and Learning phases, including evidence download, truthful correction receipt, refusal, revision history, reapproval, restart readback and role boundaries; **49** selected audit/agent-access/header tests and **692** CI-contract checks. An offline recheck in a distinct local output tree held one intercepted request **1,501 ms** (1,338 ms to the pending UI snapshot plus 163 ms to release) and matched all **42** original evidence files by hash. **Synthetic browser and persistence evidence only** |
| #994 retained verifier failure | The original verifier failure is retained as the obsolete `delayed switch report has no recorded latency` assertion. The immutable run summary still says `failed`; the 1,501 ms hold is a captured request-stage hold, not end-user latency, and the historical artifact was not rewritten |
| #994 post-merge main | [CI 44233465790](https://github.com/rush86999/atom/actions/runs/44233465790) and [Docker 44233465698](https://github.com/rush86999/atom/actions/runs/44233465698) were **pending** at this cut; no completed, failed or performance result is claimed |
| #993 ordinary workbook upload | PR [#993](https://github.com/rush86999/atom/pull/993) → `a33e8d8ab9352fa59324ebc067772fea4efe24d2`, tree `a69fc37d3ecea25746b317b55944adf711f63d06`, exact head `3ae4a03c4a9d8d671b4bb6d68ff6d965b3025352` with all **17** checks successful. The isolated ordinary-upload campaign improved **14/18 → 18/18** on the fix: DOCX with the correct **USD 370.00** total, workbook source and matching SHA-256, restart/reconciliation without a second send, cancellation and resend protection; **692** CI-contract checks |
| #993 post-merge main | [CI 44217198387](https://github.com/rush86999/atom/actions/runs/44217198387) passed on **attempt 2** after the Python 3.11 package download broke attempt 1; [Docker 44217198440](https://github.com/rush86999/atom/actions/runs/44217198440) passed |
| #993 / TASK-WAIT boundary | The **normal `/api/documents/upload` route only**. The legacy text-only ingestion route and its replay are **not adjudicated**; the prior **5 PASS / 7 FAIL / 6 NOT EVALUATED** legacy campaign remains a negative. No claim is made that the legacy route is repaired or assignable, or that every TASK-WAIT branch is supported |

The #994 qualification is **scoped audit/Learning correction and persistence evidence**. It is not a compliance certification, a broader audit-integrity proof, a live-model result or a whole-goal/whole-app completion claim.

## Release facts at the #990 cut (retained)

| Fact | Actual source |
|---|---|
| Observed main | `a7eccddb45872182a6e2af096b0ad4ee0516b7e6` — preserve reviewed approval parameters through dispatch and decision history (PR [#990](https://github.com/rush86999/atom/pull/990)); application bytes include #990 on top of #987, #988 and #991 |
| Merged tree | `d2424e36f83f90e06ab60148aca290690e3a8a70` — equal to the exact #990 PR-head tree |
| Sole parent | `31e2aebf7cec3fe265e131a1ad27374bbe082654` (PR [#987](https://github.com/rush86999/atom/pull/987)) |
| #990 exact PR head | `a84de131cf37fc9dd5d10bc00a0265f29843171c` — all **17** check runs completed successfully, including `backend-core-extra-isolated`, `backend-tests` and GitGuardian. The squash merge keeps the PR-head tree `d2424e36`; merge/tree identity, unchanged protections and empty review threads are recorded in `/private/tmp/atom-pr990-final-merge-receipt.json` and `/private/tmp/atom-pr990-qualified-merge-result-v3-20261117.json` |
| #990 qualified scope | **3 independent integrated targeted tests** and **692 CI-contract checks** at the integrated head. The local compatibility repair `007f43b555656b36f1a92b9003d1d8c71ec24c02` also passed 26 guided, 139 common decision, 167 adjacent approval, 73 checkpoint and 94 regression controls; the wider 264-node sweep passed 257 with 7 failures reproduced identically on unchanged `85fbd6357`. **Scoped correction/compat tests only: there is no broad replay at the integrated or merged tree** |
| #990 post-merge main | [CI 44201417963](https://github.com/rush86999/atom/actions/runs/44201417963) and [Docker 44201418036](https://github.com/rush86999/atom/actions/runs/44201418036) were **pending as of the merge**; no completed, failed or performance result is claimed here |
| Preceding main (#987) | `31e2aebf7cec3fe265e131a1ad27374bbe082654` — durable chat ownership and scoped history access; merged tree `991cd1cf96aeead642d6455c4352c92e673b8441`, sole parent `4071ef9ba11f68e645c4514ce7621fa9db9403c8` (#991) |
| #987 exact PR head (retained) | `8b0e5367af0bbf840c173b849e01c9e5888afddb` — all **17** check runs completed successfully (including `backend-tests` and GitGuardian). The squash merge keeps the PR-head tree `991cd1cf`; merge/tree identity and unchanged protections are recorded in `/private/tmp/atom-pr987-final-merge-receipt.json` |
| #987 qualified scope (retained) | **1,483 independent tests** on the pre-merge source `070d1b46b` (tree `ee098d8b1`, the same tracked tree as `395cbb`); after integration with main the non-CI feature patch is independently identical and **692** CI-contract checks pass. There is **no broad replay at the integrated head** |
| #987 post-merge main (retained) | [CI 44192476933](https://github.com/rush86999/atom/actions/runs/44192476933) and [Docker 44192476883](https://github.com/rush86999/atom/actions/runs/44192476883) were **started** at exact `31e2aebf`; no completed, failed or performance result is claimed here |
| #991 acceptance-world storage preflight (retained) | PR [#991](https://github.com/rush86999/atom/pull/991) → `4071ef9ba` |
| #991 exact PR head (retained) | `734725186b2d5d41b0fc19b1e451cbfeae6a44fe` — all **17** check runs completed successfully (including `backend-tests` and GitGuardian); merge/tree identity and unchanged protections are recorded in `/private/tmp/atom-pr991-final-merge-receipt.json` |
| #991 qualified scope (retained) | Root re-ran the launcher file as **29 independent storage-preflight tests**; current-main integration preserves all non-CI feature changes and the worker **692** CI-contract checks; no browser run was made. Storage preflight only, not browser acceptance |
| #988 graduation evidence binding (retained) | PR [#988](https://github.com/rush86999/atom/pull/988) → `59fa6b64b` |
| #988 exact PR head (retained) | `4459e680d22fb688191436a81d1a6336e064eaa2` — all **17** check runs completed successfully; merge `59fa6b64b`, tree `b4fd6ed0b`, parent `ba66f5e22`, recorded in `/private/tmp/atom-pr988-final-merge-receipt.json` |
| #988 qualified scope (retained) | Root **706 current-head CI checks** at `4459e680d`; the earlier **1,034-check** synthetic product gate transfers because all **18,927** non-CI tracked entries are exact. Those two counts overlap and are **not** additive. Synthetic campaign evidence only; real served-model quality remains **unknown** |
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
| #989 exact PR head | `0e1b9065e55d00e717db6a62e82fbdf25697683a` — all **17** check runs completed successfully; branch protections and rules verified unchanged. Root receipt: `/private/tmp/atom-pr989-root-actual-merge-verification-20261117.json` |
| #989 post-merge main | [Docker Build 44157075848](https://github.com/rush86999/atom/actions/runs/44157075848) recorded successful; [CI 44157075691](https://github.com/rush86999/atom/actions/runs/44157075691) later observed completed successfully at exact `ba66f5e22` (46m 14s first attempt). Delivery only — not application latency |
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

## Open queue at the 2026-11-17 #990 cut — dated and unqualified

These are **open candidates or bounded records**, not acceptance credit. The
detail is recorded only because it was current at the stated cut; it may be
stale and no CI state is asserted by this worker beyond the receipts named.

- **PR #990 older published variant — preserved hosted failure (not the merged
  head).** `85fbd6357f7e30efe3718c22fc2782fce94edaa4` (tree `83c72091`, parent
  `4071ef9ba`) remains the **dated record** of hosted run `44184658257`, which
  failed `backend-core-extra-isolated` job `134397829262` in
  `test_guided_hitl_approval_creates_one_reviewed_agent`: the first guided
  create returned 200, while the duplicate approval returned 409
  `DECISION_CONFLICT` where the established alias endpoint contract expects
  plain 400. That failure stays preserved as dated evidence; the **81** root
  repair tests at that pinned head remain real but do not cover that path.
- **PR #990 merged repair — scope and side-effect limits.** The local
  compatibility repair `007f43b555656b36f1a92b9003d1d8c71ec24c02` (tree
  `74333d47`, two files) restores the alias route's plain 400 only for a
  decision repeated on an already-terminal row, after every existing auth,
  scope, role, never-autonomous and preflight gate. The shared writer keeps its
  strict 409 `DECISION_CONFLICT`, so genuine claim races are unchanged; the
  legacy agent route keeps its independent idempotent-200 semantics. The repeat
  performs **no side effect**: no parameter/history rewrite, no status change,
  no scheduler call and no resume. Merged as part of #990 at
  `a7eccddb`/tree `d2424e36`; the qualification is scoped correction/compat
  evidence only, with no broad replay, PostgreSQL, browser, restart or
  whole-goal claim. The post-merge main CI/Docker runs were pending as of the
  merge.
- Audit member-route candidate `76a3bbc15e029dc293e0ba4e28c7adf39505c4ea`
  (tree `13ed22d5a5a6dc7227c836e5468ee9d8d70102f`) is integrated at
  `72f9a8bab6efc1238a99bbfaebef075b1d43c5d6` (tree
  `45edc4087b29be1a2e6a6c54b6bbc9df9247f10f`) atop the actual main
  `31e2aebf`. The frontend tree is identical
  (`3c54891feb4840335ee47f2eb6dd2911d42d90d8`), so the integration adds no
  frontend byte. The candidate remains **unmerged**, so it carries no
  shipped-behavior or acceptance credit. It narrowly moves `/audit-trail` from
  deferred `governance` to enabled `activity` in the backend route table and
  the frontend core fallback; `/admin`, forensics, risk, system-status and the
  harness-evolution dashboard stay governance-only, and the historical
  acceptance-ledger bytes are unchanged. Root independently ran **83**
  profile, audit owner-scope/correction and supervisor-gate checks; the worker
  reports 15 Jest tests and a clean TypeScript check.
- **Audit core2 browser run at `72f9a8ba` — member login, core mount and two
  reads, then a dialog abort.** The fresh isolated run `audit-core2`
  (`/private/tmp/atom-audit-browser-core-72f9a8-20261117`) passed real member
  login (`signin.navigation` 200, exact return `/learning`, 200 session, cookie
  and user present, intended synthetic member email) and the audit **core
  mount** itself: exactly **one** `/api/audit/summary` read and **one**
  `/api/audit/executions` read, both 200. It then failed the very next check,
  `audit.mount.visible_dialogs` (actual **1**, expected **0**), and aborted
  before any correction, learning/export, provider mutation or restart phase.
  The failed report's request log and empty UI snapshots do not identify the
  dialog; a read-only diagnosis traced the only default-mounted candidate to
  the first-run `OnboardingWizard` and its asynchronous status gate rather than
  an Audit Explorer defect. This is **not** browser or restart acceptance, and
  the core mount/read success does not qualify corrections, learning,
  export or restart.
- **Audit first-run dialog diagnostic — the open thread at this cut.** A new
  isolated runtime (`/private/tmp/atom-audit-browser-dialogid-20261117`, run
  label `audit-core2-dialogid`, default first-run seed) was created with a
  fresh build and the reviewed identity/timing instrument only. The first-run
  diagnostic is the active next step; no dismissal, seeding change, product
  fix or acceptance is recorded here.
- Audit/Learning browser **replay2** (pinned source `60a8b7050`, build
  `j7CZbuv5eLLT0wE6OnYyZ`) remains the earlier dated record: real browser
  same-origin sign-in **passed** with the intended seeded member and
  secure/httpOnly cookies; the credentials callback returned 200 with no CSRF
  refusal or error and the shell stayed alive. The run then failed its first
  **route** assertion because the core product profile classified
  `/audit-trail` as deferred `governance` while the sidebar advertised it as
  `activity`. Zero audit reads, corrections or provider calls occurred. That
  defect is what the unmerged candidate above targets; replay2 itself remains
  a failure and is not browser or restart acceptance.
- **TASK-WAIT-01 current-main revocation contract — 1 passed.** The focused
  contract file `backend/tests/test_task_wait_source_revocation.py` was run
  against the pinned code at this cut (checkout `49402b9e4`, whose non-doc
  bytes equal `31e2aebf`; the new main `a7eccddb` changed no wait source):
  exit **0**, JUnit `tests` **1**, `failures` **0**, `errors` **0**,
  `skipped` **0**, suite time **3.240 s** (pytest total 17.25 s, 1 passed).
  It records the revoked local grant refusing the source answer **403** before
  any read/quote, the exact question staying open, and the valid twin
  completing one verified quote. The revocation is still a **direct
  `IntegrationToken.status` row mutation**, not an ordinary route, and no
  browser episode was run.
- **TASK-WAIT-01 legacy-ingestion campaign — partial negative, 5 PASS / 7
  FAIL / 6 NOT EVALUATED.** The unchanged normal-app campaign
  `scripts/acceptance/employee_g5_remaining_normal_app.py` was executed at the
  pinned source. Observed passes: normal upload accepted; distinct branch
  operation receipts (`7dc040c9…` ≠ `eb6cc947…`); selective branch
  re-evaluation with one prior result; late response after cancellation
  refused 409 with the assignment `cancelled`; both branch receipts survived
  cancellation. Observed failures: artifact run (checks 2–5), independent
  branch/wait completion and the retained waiting operation (checks 6 and 9),
  and controlled-outbound approval (check 12). Checks 13–18 were never run
  because the harness aborted on a **409** from `POST …/approve/send`; no
  `report.json`/`REPORT.md` exists, so those checks are **NOT EVALUATED**, not
  failed. The traced single causal chain is the **source representation**: the
  campaign uploads through the text-only
  `POST /api/document-ingestion/upload`, which writes
  `file_path="upload:<name>"` and never materializes bytes, while the current
  consumption gate requires a real local file; `document.text` applies, then
  `_source_consumption_gap` re-authorizes and parks the source with
  `source_unavailable`. The 409 on `/approve/send` is the route's correct
  guard for a step with no prepared approval request, not a second defect. The
  real product negative is the accept-then-park inconsistency for text-only
  ingestion uploads; whether such uploads are meant to be assignable is a
  product decision this run does not establish.
- **TASK-WAIT-01 next diagnostic — source representation and ordinary route
  replay pending.** The exact discriminator is to replace only the campaign
  upload call with the ordinary UI/assignment route
  `POST /api/documents/upload` (reading its `id` field) and rerun unchanged;
  a minimal replay variant and its limits were prepared, **not executed**.
  The diagnosis of the source representation and the ordinary-route replay are
  therefore **pending** at this cut. Opaque/text-only ingestion uploads are
  **not** shown to work, be assignable or be released, and no release or
  whole-app G5 claim is made.

Earlier root runs remain retained negatives: the broader 16-file replay at
local `69f12d7388f9a141134dc9434d1244a08e965abe` finished with **1,424 passed
and 59 failed** of 1,483, with no errors or skips. Those failures were later
diagnosed as stale legacy test fixtures, not product regressions: every
failing path was already byte-identical to `ba66`, they were repaired
tests-only inside #987, and the final pre-merge replay passed all **1,483**.
The integrated head still has no broad replay, and the failed run is not erased
by the repair.

Later root CI observation on November 17: main #989's
[CI 44157075691](https://github.com/rush86999/atom/actions/runs/44157075691)
completed successfully at exact `ba66f5e22`. Its first attempt took 46m 14s
from workflow start to the last job finishing, compared with 68m 24s for
[main #986 CI 44141818847](https://github.com/rush86999/atom/actions/runs/44141818847)
at exact `8afac828c`. These are two observed successful hosted runs, not a
controlled benchmark: cache, runner contention and queue differences were not
normalized. This is delivery evidence, not application latency or Goal 17
acceptance. The earlier pending-at-cut record above remains historical.

### Audit/learning browser attempt at this cut — not acceptance

- The audit/learning cut `60a8b7050` (tree `6000726b9`, frontend tree
  `f5da7c95a`) is **not merged**. Its Next build passed (`build_id`
  `j7CZbuv5eLLT0wE6OnYyZ`, 74.4 s, exact source `60a8b7050`) and its isolated
  world-store/harness preflight passed (fresh world, canonical worlds root
  absent and untouched).
- The first browser run failed before any HTTP/browser interaction at harness
  start-up (`Cannot read properties of null (reading 'goto')`). The next
  labelled run reached the sign-in page, then failed at the harness
  `web_session.email` read after sign-in. The separate seeded replay failed
  again at harness sign-in start-up. None of these failures is an application
  assertion, and no correction/learning/provider mutation was made.
- Therefore there is **no browser acceptance and no restart acceptance** for
  the audit/learning surface at this cut. Replay 1 evidence stays preserved;
  a further attempt requires a separately labelled, validated harness on the
  unchanged seeded state, without weakening authentication.

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
| 4 | Spreadsheet and calculation | accepted-bounded | [24-sheet workbook browser](WORKBOOK_BROWSER_LIFECYCLE_2026_11_16.md) @ `3316b0fe7` (exact 34,610 total, formula/cache checks, export before/after restart); full-population API replay 34,533 @ `6ad2738ed` (readiness §4); #993 merged `a33e8d8ab` (ordinary upload **18/18**, USD 370.00 DOCX, source/SHA-256 provenance, restart/resend controls) | browser + API proof, synthetic; **model/live-source gap** | Live connected source; model-driven extraction of the contributing population; reconciliation of ambiguous requests. #993's 18/18 is the normal `/api/documents/upload` route only; legacy text-only ingestion remains separate and unadjudicated. The historical 1758.00 single-sheet counterexample remains retained. |
| 5 | Canvas and editable outputs | accepted-bounded | [PDF browser](PDF_CANVAS_BROWSER_LIFECYCLE_2026_11_16.md) @ `bb7017af3`; [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX pictures](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689` (merged #974) | browser + merged implementation | Full Canvas D2; other Canvas families; broader embedded media; cross-user ownership; Firecracker/KVM mini-app legs. Title/count-only renders are insufficient. |
| 6 | Teaching and reusable agent capability | accepted-bounded | [Learning correction/renewed approval](LEARNING_CORRECTION_REPROMOTION_2026_11_16.md) @ `1d4f409e1`, merged #975; [real-Docker ordinary skill dispatch](CURRENT_SKILL_DOCKER_ACCEPTANCE_2026_11_16.md) @ `3316b0fe7`; [scoped maturity](SCOPED_SKILL_MATURITY_2026_11_15.md); #988 graduation evidence binding merged `59fa6b64b` (synthetic campaign scope); #994 merged `d701872` (Learning source excerpt/revision history, revision clears approval, reviewer reapproval and restart readback) | browser + API/container proof; merged; **model-quality gap** | Independent real-model skill selection/consumption; unfamiliar-skill and unfamiliar-model work; generated-code promotion; a real browser/restart journey for approve→correct→renew that also covers keyboard-only, export and access checks beyond #994's synthetic run; PostgreSQL concurrency. Scripted decisions do not establish model quality. #988 binds synthetic campaign evidence to dispatch but proves no real served-model quality. #994's 520 assertions do not certify audit integrity, live models or the whole goal. |
| 7 | Assessment and unfamiliar work | accepted-bounded | [Audit ASK/ORACLE-06](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [historical product ledger](../acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md); deterministic 18/18 V1 and 19/19 V3 | deterministic proof; **model-quality failure** | New held-out/served-domain qualification and any general adaptive judgment claim. The deterministic path does not interpret arbitrary prose; `Q-012`/`Q-021` remain preserved failures. |
| 8 | Durable employee objectives | accepted-bounded | [Atomic Activity checkpoint decisions](ACTIVITY_CHECKPOINT_ATOMIC_DECISIONS_2026_11_16.md) @ `1f70c1708`, merged #976 (234 backend + 68 frontend controls; browser approve/reject/restart); [real 48-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0`; [goal-run WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968 | API/browser proof; merged; **model-quality gap** | Current-main ordinary-model objectives; event-order breadth; multi-worker/soak; full TASK-WAIT-01 integration. The Activity fixture goals were already achieved, so model competence is not proven. |
| 9 | Runtime configured-budget enforcement | accepted-bounded | [PR #932](https://github.com/rush86999/atom/pull/932) merged `ab14eb391` (Whisper duration/billing and settlement controls; joint 360-test qualification); historical #722 `5b9610b56` | merged implementation; controlled proof; **live/operator gap** | One priced `TokenUsage` row, matching tenant spend delta, idempotent duplicate settle, and a second dispatch refused before transport when short. Whisper live/remote settlement and PostgreSQL remain unproven. No live spend is authorized. |
| 10 | TASK-WAIT-01 long tasks pause/resume | open | [Real 48.0203-hour wait](REAL48H_WAIT_ACCEPTANCE_2026_11_16.md) @ `2f2b376a0` (same job/execution, one effect, duplicate/late-answer refusal); [WAIT validation](GOAL_RUN_WAIT_VALIDATION_2026_11_16.md) merged #968; multi-source run @ `ad6ecbd5d`; current-main revocation contract **1 passed** (`test_task_wait_source_revocation.py`, exit 0, 1 test/0 failures/0 errors/0 skips, 3.240 s, direct grant-row revocation not an ordinary route); #993 merged `a33e8d8ab` (normal-upload workbook read/restart lane); legacy-ingestion campaign **5 PASS / 7 FAIL / 6 NOT EVALUATED** (source-representation failure; checks 13–18 never run after a correct 409 guard) | process/API proof; **current-main/model/operator gap** | Ordinary UI; current-main real-model work; partial and independent progress; revocation/cancellation during the wait through an ordinary route; source-representation diagnosis and the ordinary-route replay (both pending and **not adjudicated**); all supported surfaces; multi-worker/soak. The campaign's partial result is a negative, not a pass. #993 addresses the normal upload route only and does not establish that the legacy text-only route is repaired or that every TASK-WAIT branch is supported. Arrival alone is not completion. Never rearm the terminal elapsed-wait case. |
| 11 | Documents, presentations and email drafts | accepted-bounded | [DOCX/PPTX browser + restart](OFFICE_DOCX_PPTX_BROWSER_RESTART_2026_11_16.md) @ `3316b0fe7`; [inline DOCX](DOCX_INLINE_IMAGE_PRESERVATION_2026_11_16.md) @ `8d98b0689`; #919 merged `9de6ef33` (loopback path only) | browser proof for documents; **provider/email unknown** | Ordinary presentation and email-draft journey; provider draft readback; real recipient inbox delivery; authorized live invoice replay. The one-use live send authority is exhausted. |
| 12 | Repeatable workflows and schedules | accepted-bounded | Public workflow scope `49d45c7f3`; scheduler `78d2e0ca8`; recovery `e2ba4b01c`; ORCH-01 `0fae2d46c`; [readiness §12](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#goal-12) | merged + controlled proof; **served-model/operator gap** | One real served workflow request through the production route/deadline path; a full scheduled real-workflow result and receipt; PostgreSQL/multi-worker/soak. ORCH-01 still uses a controlled LLM double. |
| 13 | Fleet, goals and background work | accepted-bounded | [Real fleet delegation, incomplete answer](CURRENT_READINESS_EVIDENCE_INDEX_2026_11_14.md#fleet-real-delegation-incomplete-deliverable) @ `a868435fd` (#943, final answer not accepted); one capped synthesis sample (#951); [fleet diagnostics](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md#fleet-diagnostics-remain-separate-from-application-acceptance) (capped live test failed; 11 offline fault controls, including 17 attempted / 16 synthetic send starts) | merged implementation; scripted/API proof; **live workflow failed**; broader model quality **unknown** | Current-main live TASK with a real model, one in-scope chain, complete attributed final answer, restart/durable state, no shadow success or out-of-scope specialist. Case 6 remains **FAILED**. [Case 7](FLEET_LIVE_COMPATIBILITY_2026_11_17.md) also failed fleet acceptance: 14 actual upstream requests, 13 structured HTTP 400 and one correct direct Flash reply; verifier error-contract limits prevent a definitive upstream-cause claim. Its allowance is consumed; no automatic rerun. [Case 8](FLEET_LIVE_DELEGATION_2026_11_17.md) recovered the optional-logprob rejection and completed structured calls on merged main `02c9b1674`, but chose direct conversation: zero specialist chains/links. Six starts stayed within the cap; its one-shot allowance is consumed. [Explicit collaboration authority](EXPLICIT_COLLABORATION_AUTHORITY_2026_11_17.md) merged later at #984 `7f7952c65` carries an accepted specialist requirement into the existing fleet lane with 85 offline checks; case 8's source predates it, so it is not a live delegation pass and needs a fresh allowance. The old 43-case scripted pass remains source-bound, not a current live pass. |
| 14 | Direct mutations and whole-app ORACLE | open | Activity checkpoint authority (#976) and [never-autonomous task fences](NEVER_AUTONOMOUS_TASK_BASKETS_2026_11_16.md) (#977) are scoped mutation/authority families; static inventory 836/371/311; merged families #650–#695; Canvas delete/undelete current-actor authority repaired by [#763](https://github.com/rush86999/atom/pull/763) `c97dada13`; #994 merged `d701872` (audit correction request/receipt/refusal and scoped timeline reads) | merged scoped implementation; **whole-app runtime unknown** | Every reachable mutation family enforcing current authority/material, exact operation, durable effect and independent readback; replay/rollback/unknown truth; refreshed current-main inventory; PostgreSQL/multi-worker. #994's audit correction/refusal path is synthetic browser evidence, not a census of mutation families or whole-app ORACLE. The four historical delete/undelete scope failures stay preserved at their baseline; 54 bounded current controls pass, which does not qualify every Canvas route or whole-app ORACLE ([reconciliation](CANVAS_LIFECYCLE_AUTHORITY_RECONCILIATION_2026_11_17.md)). Adjacent bounded authority controls merged later: [entry task-profile isolation](NEVER_AUTONOMOUS_TASK_PROFILE_ISOLATION_2026_11_17.md) #986 `8afac828c` (737 independent checks; SQLite only), [M3 canonical final reply](../architecture/orchestration_migration/acceptance/lane3/M3_CANONICAL_DELIVERY_PROOF.md) #985 `7e51e0976` (22 public-boundary controls; flag default OFF), and [durable collaboration pending authority](EXPLICIT_COLLABORATION_AUTHORITY_2026_11_17.md) #984 `7f7952c65` (85 offline checks). |
| 15 | Remaining exposed application | open/partial | [Web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) core pages render; [signed-in Settings](../acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md) 29/29 @ `a53b56fdc`; Canvas list 22/22 @ `6ad2738ed`; Tasks/Projects #797 `3541e8115`; #994 merged `d701872` (core-workspace Audit Trail, actor/supervisor-scoped reads, correction receipt/refusal, evidence export) | browser proof, partial; **deferred scope**; many surfaces **unknown** | Primary action + durable readback on Tasks/Boards, marketplace install, search, finance/voice/BPE/settings/skill editor/team chat, blocked-route errors, and direct admin/member behavior. #994 is one synthetic 520-assertion audit/Learning campaign, not every exposed surface or broader audit integrity. Tasks/Boards are owner-deferred by the core release profile and must not be force-enabled. |
| 16 | Installation, compatibility and operations | open | [Persistent PostgreSQL restart](POSTGRES_PERSISTENT_RESTART_2026_11_16.md) @ `3316b0fe7`; [logical restore](POSTGRES_LOGICAL_RESTORE_2026_11_16.md) @ `c1ab1af1`; [full-app restart](POSTGRES_FULLAPP_RESTART_2026_11_16.md); [fresh bootstrap](POSTGRES_FRESH_BOOTSTRAP_2026_11_16.md) @ `5aa8c1c8`; #936/#941/#943; #991 acceptance-world storage preflight merged `4071ef9ba`; #994 `d701872` isolated fresh-store launch + same-world restart (SQLite/loopback; addendum below) | bounded operator/deployment proof; merged; **unknown breadth** | [Document-lineage existing-table revision](POSTGRES_DOCUMENT_LINEAGE_UPGRADE_2026_11_17.md) merged #981 `0ef449aea` with a bounded PostgreSQL 14.24 proof (29 independent tests including one real cluster, clean restart/data/index preservation) for that single revision. Other existing upgrades, full migration graph/app upgrade, async transport, abrupt outage, cluster/PITR, multi-worker/soak, Linux/ARM, native mobile device, menu-bar native live chat, KVM, and full rollback/restore child flow. #977 exercised only SQLite migration, not PostgreSQL. #991's storage guard was offline preflight only **at that dated cut**: no browser, restart, fresh-world launch, drive-pull-while-running or operator deployment was exercised then. The later #994 fresh-launch/same-world restart below covers the isolated SQLite/loopback path only; browser interaction, true deployment, PostgreSQL, cloud/model, portable-drive removal and operator breadth remain open. |
| 17 | Performance and comparative promises | unverified | [Audit PERF/MKT rows](APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json); [performance reconciliation](APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json); cache-only benchmark `dd2610502` (37 tests) | **unknown** — no declared measurement | Reproducible measurement with declared environment, workload, sample size and command; dated source for every comparative/pricing claim. A cache-only test is not app throughput or model quality. No invented numbers. CI delivery work is explicitly **not** app performance: #982 adds `--durations=20` reporting only, and #989 repartitions lanes with an **estimated** 42.6-minute critical lane, +5.7 runner-minutes and no measured speedup or whole-app latency result. |
| 18 | Profile breadth | open/deferred | `CORE-07` profile switch; [web boundary](../acceptance/WEB_BOUNDARY_VERIFICATION_2026_11_16.md) confirms core defers Tasks/Boards; [goal catalogue](APP_GOALS_INDEX.json) explicit requirements | **deferred scope** | Explicit owner decision on full-profile enablement and qualified journeys for the restored surfaces. Do not force-enable deferred profiles or add SaaS gates to close the row. |
| — | **DOCS-REF-01** documentation and diagrams | open (additional closure requirement) | [Frozen reference inventory](reference_inventory_ac2b73778_20261108.json): 1,729 reference files, 11 diagram candidates, 633 image/PDF candidates at `ac2b73778`. This map is navigation only. | inventory only; **accuracy unknown** | Complete classification of every reference/diagram with owner and canonical destination; accurate user/operator paths; architecture diagrams with render + semantic review; API/config reference; reproducible safe commands; final no-contradiction acceptance audit. Inventory counts are not accuracy or rendering passes. |

**DOCS-REF-01 validation note:** an inventory run at product source
`0e9b0dfc9` during this pass (not committed) counts 1,934 reference files, 13
diagram candidates and 681 image/PDF candidates; the frozen `ac2b73778` counts
above remain the preserved historical baseline. Every relative link added or
changed by this overlay resolves on disk. A whole-repository check still reports
pre-existing broken links, including two long-standing entries in
`docs/INDEX.md` (`../../Makefile`, which resolves outside the repository, and
the absent `.planning/phases/236-cross-platform-and-stress-testing/`); both are
recorded here, not silently repaired. Neither result closes DOCS-REF-01.

## What the #975–#994 deliveries do and do not establish

| Delivery | Source-bound scope | Does not establish |
|---|---|---|
| **#994 audit evidence and Learning corrections traceable** | Audit Trail is reachable from the core workspace; timeline reads are scoped to the actor or an authorized workspace supervisor. The timeline, correction form and evidence export stay attached to the selected run/event, a refusal states its reason, and an unsigned export declares its read scope and integrity limits. The Learning source excerpt and revision history are shown; a revision clears approval and requires reviewer confirmation and promotion. Merged at `d701872`, tree `fa66625` (equal to exact head `b57be40f5`), sole parent `a33e8d8ab`; all 17 exact-head checks passed. Reported scope: **520 browser assertions** and **34 acceptance cases** across both phases, including evidence download, truthful correction receipt, refusal, revision history, reapproval, restart readback and role boundaries; **49** selected audit/agent-access/header tests and **692** CI-contract checks; the offline recheck measured a **1,501 ms** browser request hold from the recorded timestamps and matched all **42** original evidence files by hash. | Broader audit integrity, a compliance certification, live-model behavior, PostgreSQL/multi-worker, every route or approval family, and whole Goal 6/14/15 or whole-app completion. The original verifier failure — the obsolete `delayed switch report has no recorded latency` assertion — is retained; its immutable run summary still says `failed`. The 1,501 ms figure is a captured request-stage hold (1,338 ms + 163 ms), not end-user UX latency. Post-merge CI `44233465790` and Docker `44233465698` were pending at the cut. |
| **#993 ordinary uploaded-workbook reads** | Binary/container uploads (`.xlsx`/`.xls`/`.xlsm`/`.ppt*`/`.pdf`) now fall through to the authoritative version-matched indexed extraction instead of decoding raw container bytes as text; text-native files keep their real-path reads, and a missing, stale or out-of-scope extraction refuses with `NeedsContext`. Merged at `a33e8d8ab`, tree `a69fc37d3` (exact head `3ae4a03c4`), all 17 exact-head checks passed. The same isolated ordinary-upload campaign improved **14/18 → 18/18**, producing a DOCX with the correct **USD 370.00** total, workbook source and matching SHA-256, then restart/reconciliation without a second send, plus cancellation and resend protection; **692** CI-contract checks. | The legacy text-only ingestion/assignment route, which remains a separate unadjudicated boundary with the prior **5 PASS / 7 FAIL / 6 NOT EVALUATED** negative preserved; live connectors; model-driven extraction; every workbook format; PostgreSQL; whole Goal 4. The 18/18 used the normal `/api/documents/upload` route, so it does not show that opaque ingestion uploads are assignable, released or repaired, or that every TASK-WAIT branch is supported. Post-merge CI `44217198387` passed on attempt 2 after the Python 3.11 package download failed on attempt 1; Docker `44217198440` passed. |
| **#990 reviewed approval parameters through dispatch and decision history** | Merged at `a7eccddb`, tree `d2424e36` (equal to exact head `a84de131`), sole parent `31e2aebf`. An approved action's reviewed parameters are preserved into dispatch and decision history. The alias approve/reject surface answers a decision repeated on an already-terminal row with its established plain 400, after every existing authority gate; the shared intervention writer keeps strict 409 `DECISION_CONFLICT`, and a repeat performs no write, status change, scheduler call or resume. All 17 exact-head checks passed; qualification is **3 independent integrated targeted tests** and **692 CI-contract checks**, plus the local repair's 26/139/167/73/94 controls and a 264-node sweep at 257 pass / 7 identical pre-existing failures. The older `85fbd6357` hosted guided-duplicate failure remains preserved as dated evidence. | A broad replay at the integrated or merged tree; PostgreSQL, browser, restart, live provider/model or whole-app acceptance. The post-merge main CI `44201417963` and Docker `44201418036` were pending as of the merge, so no main green is claimed. Changing the alias surface back to plain 400 for a terminal repeat does not make a duplicate a success/idempotent 200, and it does not alter service/governance callers, the legacy idempotent-200 agent route or genuine claim races. |
| **#987 durable chat ownership and scoped history access** | `core/chat_message_authority.py` resolves the write authority inside the transcript write transaction and CAS-fences the exact actor and durable `ChatSession`; the admitted actor/scope snapshot is captured at turn entry, so a same-user tenant/workspace move mid-turn, a suspension, deletion or unreadable authority refuses the append while still delivering the answer. External bridge senders keep their declared scope and cannot be adopted by a local caller. One read twin (`resolve_chat_read_scope`) authorizes history/trace/task/memory/details/list/fork/rename/delete/feedback on every request, with the durable owner beating a stale label and an authority outage returning 503 instead of an empty cache. The enabled M3 boundary feeds the same canonical text to WS close, HTTP and the durable row and fails closed when validation is unreadable. Merged at `31e2aebf`, tree `991cd1cf`; exact head `8b0e5367a` had all 17 checks successful; **1,483** independent tests on pre-merge tree `ee098d8b`, feature-patch equivalence and **692** CI-contract checks. | Live database, provider/model, browser, restart, PostgreSQL or multi-worker acceptance; whole-app semantic truth or model quality. `CHAT_FINALIZATION_M3` stays default **OFF** and remains a limited-vocabulary pre-delivery boundary; a frozen legacy claim split across already-released chunks can still reach the live bubble mid-stream (the final carriers are covered), and non-canvas or protocol-rejection turns are unchanged. No chat per-session grant or admin-all-tenant bypass was invented. No broad replay exists at the integrated head. |
| **#991 acceptance-world storage preflight** | `validate_local_world.resolve_storage_config` is the one resolver shared by the launcher, browser preflight and canvas harness: it calls the guard's own `load_config` (env relocation + guard precedence) and refuses a missing relocated config instead of falling back to the checkout root. Both private parse-and-mkdir bootstraps are removed, the launcher re-checks `assert_worlds_root_usable` immediately before the first world `mkdir`, and `provision_isolated_world_store.py` creates only an empty store root plus an out-of-tree config, refusing the canonical root, bypass, non-empty stores and overwrite. Real shell launcher/guard/validator controls stop at a labelled pre-server boundary; **103 focused tests** passed (new 19 + browser preflight 39 + canvas 10 + guard 35), the lane ledgers register the step exactly once, the lane/quickstart contract passed **711**, and root independently ran the file as **29 passed**. Merged at `4071ef9ba`; exact head `734725186` had all 17 checks successful. | Any browser, login or restart acceptance; an actual acceptance journey from a fresh world; a root that disappears while a world is already running; drive-removal runtime behavior; PostgreSQL, provider/model or whole Goal 16. At the #991 cut the canonical worlds root stayed absent throughout, so the fresh-world launch path itself was not exercised end to end *then*; the separate Goal 16 dated addendum below records the later isolated launch/restart. |
| **#988 graduation evidence binding** | The campaign producer's digest-sealed `benchmark_evidence` becomes the only binding authority: embedded execution id, agent, tenant, workspace and completion time must match; bare identity/dataset/rubric/scope metadata is audit-only; multiple differing records fail closed as `conflict`; bundle enumeration lists bound campaign executions before episode work; v2 receipts bound from bare metadata revalidate as `unresolved_stale` and need a fresh review. A new end-to-end counter test drives producer → canonical validator → review/receipt → promotion → runtime baseline → resolver → real `LLMService`/`BYOKHandler` over `httpx.MockTransport`, with 21 tamper/digest/accuracy/build/receipt/revision/scope/profile/dataset/rubric/scoring/supersession/stale/echo/cooldown/401/concurrency cases. Offline **84** for the migrated plus new files, **231** in the wider graduation neighborhood and **54** decision-contract checks. Merged at `59fa6b64b`; exact head `4459e680d` had all 17 checks successful. | Real served-model quality, an unfamiliar-work qualification, a live campaign, any provider/model call, PostgreSQL, or evidence that the stricter binding improves answer quality. Synthetic campaign journal, in-repo registry and fake transport only. |
| **#989 CI lineage-preserving lanes** | Four backend core lanes (19 / 20 / 14 / 26 post-setup steps) with all 79 existing step dictionaries byte-identical and registered once; `backend-tests` still needs all six backend lanes and adds no retry/skip/soft gate. Local contract run 706 passed. README records an **estimated** 42.6-minute critical lane and +5.7 runner-minutes, with the unmetered M3 caveat and concurrency/queueing limit. Merged at `ba66f5e22`; exact PR head `0e1b9065e` had all 17 checks successful. | Any measured speedup or app latency; the runtime behavior of the product merges it now schedules; Goal 17. Its main Docker and CI runs later completed successfully, but that is delivery, not application latency. |
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
- #988's digest-sealed synthetic campaign records, mocked transport and 21
  drift cases are **not** real served-model quality, a live campaign or a
  graduation quality improvement.
- #991's 103 focused offline storage-preflight tests (including the 29-test
  launcher file) are **not** browser, login or restart acceptance. At that
  dated cut the canonical worlds root stayed absent and the fresh-world launch
  path was not exercised end to end; the later Goal 16 pass below does exercise
  an isolated provisioned store plus a same-world restart, bounded to SQLite
  and loopback.
- #987's 1,483-test pre-merge replay, its feature-patch equivalence and its
  17/17 checks are **not** a broad replay at the integrated head, and not a
  live database, provider/model, browser, restart, PostgreSQL or whole-app
  semantic acceptance. Its M3 boundary remains default OFF and
  limited-vocabulary, and it does not prove model answer quality.
- The audit/learning browser attempt at `60a8b7050` produced **no** acceptance:
  build and preflight passed, but the browser runs failed in the harness at
  start-up and at the post-sign-in `web_session.email` read, with no restart
  run at all. Replay2 later passed real sign-in but failed the audit route
  gate with zero audit reads, so it adds no browser or restart acceptance
  either. The later `audit-core2` run at `72f9a8ba` passed member login, the
  audit core mount and exactly one summary plus one executions read (both 200),
  then aborted on one visible dialog before any correction/learning/export,
  provider mutation or restart phase. That is partial browser evidence, not an
  audit, correction or restart acceptance.
- The integrated-but-unmerged audit candidate `76a3bbc15` (merge
  `72f9a8ba`, identical frontend tree) and its 83 passing root checks are
  **not** merged and **not** browser/restart acceptance. Its narrow Activity
  mapping is still a candidate, not shipped behavior; `audit-core2` reached the
  mount and two reads but did not complete a correction or restart, and the
  first-run dialog that aborted it remains under diagnosis.
- #990 is **merged** at `a7eccddb` (tree `d2424e36`, sole parent `31e2aebf`,
  exact head `a84de131`, 17/17 checks). The older published `85fbd6357` head
  and its hosted guided-duplicate failure stay recorded as dated evidence, and
  the 81-test repair replay covers a different path. The merged qualification
  is bounded to 3 independent integrated targeted tests and 692 CI-contract
  checks plus the local repair controls; there is no broad replay at the
  merged tree, and the post-merge main CI `44201417963` and Docker
  `44201418036` were pending as of the merge.
- #994 is **merged** at `d701872` (tree `fa66625`, sole parent `a33e8d8ab`,
  exact head `b57be40f5`, 17/17 checks). Its **520 synthetic browser
  assertions** and **34 acceptance cases**, the 49 selected tests and 692
  CI-contract checks are **not** a compliance certification, a broader
  audit-integrity proof, a live-model result or whole-goal/whole-app
  acceptance. The original verifier failure is retained as an obsolete
  latency assertion; the immutable run summary still says `failed`, and the
  1,501 ms captured request hold is not UX latency.
- #993 is **merged** at `a33e8d8ab` (tree `a69fc37d3`, exact head
  `3ae4a03c4`, 17/17 checks). Its **18/18** ordinary-upload campaign is the
  **normal `/api/documents/upload` route only**; it is **not** evidence that
  the legacy text-only ingestion route is repaired, assignable or released.
  The prior **5 PASS / 7 FAIL / 6 NOT EVALUATED** legacy campaign remains a
  negative, its replay remains unadjudicated, and no claim is made that every
  TASK-WAIT branch is supported. The post-merge CI passed only on attempt 2,
  which is delivery, not application performance.
- #981's single-revision PostgreSQL 14.24 run is **not** migration breadth,
  full-graph upgrade, app-on-PostgreSQL or concurrency.
- #982 timing output and #989 lane partitioning are **delivery and observability**,
  not application performance, throughput or Goal 17; #989's lane budget is
  explicitly an estimate and no speedup is claimed.
- The frozen documentation inventory is **not** DOCS-REF-01 closure.
- The only open PR candidate in the dated #990 queue is the
  integrated-but-unmerged `76a3bbc15` audit mapping at `72f9a8ba`; it carries
  no acceptance, even though root reports 83 audit checks and the core2 run
  reached member login, the mount and two 200 reads. #990's `a84de131` head is
  no longer an open candidate: it is merged as `a7eccddb`, but a merge and a
  scoped correction/compat suite are not broad or whole-goal acceptance.
  (**Later dated fact:** the merged #994 audit/Learning implementation
  supersedes that candidate's surface; the candidate record stays unmerged and
  unaccepted as written.)
- The TASK-WAIT-01 revocation contract pass (1 test) and the campaign's 5 PASS
  / 7 FAIL / 6 NOT EVALUATED result are **not** ordinary-UI, ordinary-route
  revocation, independent-progress, current-model or whole-goal acceptance.
  The campaign's failures stay failures; its unrun checks stay unmeasured, and
  the source-representation diagnosis plus ordinary-route replay remain
  pending.

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
- #987, #988, #990, #991, #993 and #994 are recorded as merged deliveries with
  their own bounded limits; their addition revises no original claim, goal
  state, audit byte or the historical **111/123** result. #987's 1,424/59
  broader-gate failure is preserved as a real failed run; its later tests-only
  fixture repair and the 1,483-pass replay do not erase it. #990's older
  `85fbd6357` hosted guided-duplicate failure and the local repair's 7 identical
  wider-sweep failures stay preserved; merging the repaired head does not erase
  either. #994's original verifier failure stays recorded as the obsolete
  latency assertion, its immutable run summary is not rewritten, and all 42
  original evidence files remain hash-identical. #993's 18/18 is the normal
  ordinary-upload route; the legacy-ingestion campaign's 5 PASS / 7 FAIL / 6
  NOT EVALUATED stays a negative and its replay is not adjudicated here. The
  audit/learning browser attempts, replay2's sign-in pass, the
  integrated-but-unmerged `76a3bbc15` mapping and the partial `audit-core2`
  mount contribute no goal state and no score.
- The TASK-WAIT-01 campaign's 7 failed and 6 unmeasured checks stay recorded as
  a partial negative; the revocation contract pass stays bounded to a direct
  grant-row mutation. Neither is promoted, and no failure is dropped.

## Original overlay source and validation basis

- Original local Git at first publication: product source cut `0e9b0dfc9...`,
  tree `9386a486...`, parent `8b48dd84a`; first-parent history and `origin/main`
  agreed. The documentation commit that adds this file is docs-only and changes
  no product tree bytes.
- Public repository read: PRs #975/#976/#977 are merged at the recorded
  commits; the #977 exact head `488e956...` has 15/15 successful check runs;
  main post-merge run states are recorded above without promoting them.
- Recent source docs were traced in place; no stable browser/model/PostgreSQL
  campaign was rerun.
- Reference/path checks are reported in the worker summary that accompanies
  this commit. This file adds no product source, CI, policy or configuration
  change.

## Navigation refresh at #991 (this pass)

- Local checkout: branch `codex/readiness-navigation-refresh-20261117` at
  `ebdf023d5a7b44b929f53f8e3ee2160f557eff22`, tree
  `a40c21c6549a81b03cf22e1cf1f9ed4b3ea14059`, parent `207b4d80e`; worktree
  clean before editing. Verified `origin/main`
  `4071ef9ba11f68e645c4514ce7621fa9db9403c8` (tree `52a7dbd66`, parent
  `59fa6b64b`) was merged naturally as `d8f3686ef` (tree `20ce931d4`), with
  **zero conflicts**: this cut had changed only four documentation files and
  main changed none of them, so every non-doc file is byte-identical to main.
- Root receipts supplied the delivery identities without a new GitHub query:
  `/private/tmp/atom-pr988-final-merge-receipt.json` and
  `/private/tmp/atom-pr991-final-merge-receipt.json` (17/17 successful checks,
  tree equality, unchanged protections), `/private/tmp/atom-pr987-qualified-merge-result-v3-20261117.json`
  (unmerged and waiting exact-head CI at that cut; later merged as `31e2aebf`),
  `/private/tmp/atom-root-approval-atomic-main991-20261117.{xml,log,json}`
  (81 repair tests on the pinned #990 review merge) and
  `/private/tmp/atom-root-chat-main988-root-20261117.log` (1,483-test replay).
- The audit/learning browser evidence comes from
  `/private/tmp/atom-audit-browser-60a8b7-build.log`,
  `...-manifest.log`, `...-preflight.log`,
  `/private/tmp/atom-audit-browser-60a8b7-replay1.log`,
  `/private/tmp/atom-audit-browser-session-diagnosis.md` and
  `/private/tmp/atom-audit-browser-replay-repair.md`; no runtime, credential or
  secret file was read.
- Scope of this pass: documentation and reference checks only — no app, server,
  browser, test run, provider/model call, PostgreSQL cluster, install, data,
  credential, portable-media write or push. No product, CI, test, schema,
  policy or configuration byte changed beyond the verified main merge.
- New bounded evidence above does not change the original audit, the 143 claim
  identities, the 18 goal states or `app_complete: false`.

## Navigation refresh at #987 (this pass)

- Local checkout: branch `codex/readiness-navigation-refresh-20261117` at
  `6b34adf740e3a0983a96fdc64df2911456922c65`, tree
  `5f29386aba995ead5a057985b584aaba29956390`, parent `d8f3686ef`; worktree
  clean before editing. Verified pinned main
  `31e2aebf7cec3fe265e131a1ad27374bbe082654` (tree `991cd1cf`, sole parent
  `4071ef9ba`, a squash merge of PR #987) was merged naturally, with **zero
  conflicts**: this branch had changed only four documentation files since
  `4071ef9ba`, and #987 changed no document this overlay owns.
- The merge is verified by content, not by message: `git diff 31e2aebf HEAD`
  shows only the four documentation files, so every non-doc path is
  byte-identical to pinned main. The upstream squash commit `31e2aebf` itself
  has tree `991cd1cf`, equal to the PR-head tree; this branch's local merge
  commit adds only the four documentation edits on top of that tree.
- Delivery identities came from retained receipts and records, not a new
  GitHub query: `/private/tmp/atom-pr987-final-merge-receipt.json` (17/17
  successful checks, tree equality, unchanged protections),
  `/private/tmp/atom-pr987-qualified-merge-result-v3-20261117.json`,
  `/private/tmp/atom-audit-browser-60a8b7-replay2.log`,
  `/private/tmp/atom-audit-mount-diagnosis.md`,
  `/private/tmp/atom-audit-member-route-summary.md`,
  `/private/tmp/atom-pr990-guided-compat-summary.md` and
  `/private/tmp/atom-pr990-85fbd635-failed-job.log`. The post-merge main run
  IDs are recorded as **started** only.
- Scope of this pass: documentation and reference checks only — no app, server,
  browser, test run, provider/model call, PostgreSQL cluster, install, data,
  credential, portable-media write or push. No product, CI, test, schema,
  policy or configuration byte changed beyond the verified main merge.
- The 143 original claim identities, 18 goal rows, historical **111/123
  (90.2%)** and `app_complete: false` are unchanged; the original audit JSON is
  byte-identical. #987's merge, replay2's sign-in, the integrated-but-unmerged
  `76a3bbc15` mapping and #990's then-unmerged current head revise no claim or
  goal. (#990 has since merged as `a7eccddb`; that later fact does not change
  this dated pass.)

## Approved-head correction (docs-only follow-up)

- This pass started from clean worktree
  `codex/readiness-navigation-refresh-20261117` at
  `c56a17cc4d86653e6208e7612315cf093308ddb4` (tree
  `ac17240e9a6456069749177b39342063097e0eff`). It corrects the local approval
  repair identifier to
  `007f43b555656b36f1a92b9003d1d8c71ec24c02` and records two dated head
  updates: #990's now-published `a84de131` (tree `d2424e36`, integrated atop
  actual main `31e2aebf`, 3 independent integrated targeted tests and 692
  CI-contract checks, still awaiting hosted gates/merge) and audit candidate
  `76a3bbc15` now integrated at `72f9a8ba` with an identical frontend tree.
  (#990 later merged as `a7eccddb`; this paragraph remains the dated record.)
- The older `85fbd6357` hosted guided failure remains recorded as dated
  evidence; nothing about it is erased or promoted.
- Scope of this follow-up: documentation only — no push, app, server, browser,
  test run, provider/model call or GitHub query. The original audit JSON, the
  143 claim identities, the 18 goal rows, the historical **111/123 (90.2%)**
  result and `app_complete: false` are unchanged.

## Navigation refresh at merged #990 (this pass)

- Started from clean worktree at
  `49402b9e4a59a514802081a48f267c6195d7d11f` (tree
  `27fa676e3a34e4d6e3f29e733f4659883d8d3469`) on branch
  `codex/readiness-navigation-refresh-20261117`.
- Verified actual main
  `a7eccddb45872182a6e2af096b0ad4ee0516b7e6` (tree
  `d2424e36f83f90e06ab60148aca290690e3a8a70`, sole parent
  `31e2aebf`, the squash merge of PR #990) was merged naturally as
  `b56b722c5409f36eabaf6c3a350b068758c735ea` (tree
  `117bbd380d4b599edf9ae16bde3d0e1206bc434a`, parents `49402b9e4` and
  `a7eccddb`) with **zero conflicts**. The main commit changed 30 files
  (product, tests, CI fixtures and two main-owned engineering documents); it
  changed neither document this overlay owns, and this branch changed no
  non-doc path at the merge.
- The merge tree equals the exact #990 PR-head tree (`a84de131`, tree
  `d2424e36`). All 17 exact-head checks completed successfully; the only
  post-merge main runs recorded are CI `44201417963` and Docker `44201418036`,
  **pending as of the merge**. Receipts:
  `/private/tmp/atom-pr990-final-merge-receipt.json` and
  `/private/tmp/atom-pr990-qualified-merge-result-v3-20261117.json`.
- The #990 qualification is recorded as scoped correction/compat evidence only:
  **3** independent integrated targeted tests, **692** CI-contract checks, and
  the local repair's 26/139/167/73/94 controls plus a 264-node sweep at 257
  passed / 7 identical pre-existing failures. **No broad replay exists at the
  integrated or merged tree**, and no PostgreSQL, browser, restart,
  provider/model or whole-goal result is claimed.
- The older `85fbd6357` hosted guided-duplicate failure (run `44184658257`,
  job `134397829262`, 409 `DECISION_CONFLICT` where plain 400 is expected) is
  preserved as dated evidence. The merged repair restores plain 400 only on the
  alias surface for a terminal repeat, performs no write/status/scheduler/resume
  side effect, and leaves the shared writer's strict 409 for service/governance
  callers and genuine races.
- TASK-WAIT-01 at this cut: the current-main revocation contract file passed
  **1 test** (exit 0; JUnit `tests=1`, `failures=0`, `errors=0`, `skipped=0`,
  **3.240 s**; pytest total 17.25 s) with the revocation still a direct
  `IntegrationToken.status` row mutation. The unchanged legacy-ingestion
  campaign returned **5 PASS / 7 FAIL / 6 NOT EVALUATED**; checks 13–18 were
  never run after the correct 409 guard on `/approve/send`, and no `report.json`
  was written. The traced cause is the text-only ingestion upload
  representation (`upload:<name>`, no materialized bytes) colliding with the
  consumption gate; the accept-then-park inconsistency is preserved as a real
  product negative. The source-representation diagnosis and the ordinary
  `/api/documents/upload` replay remain **pending**; the prepared replay variant
  was not executed, and no claim is made that opaque ingestion uploads work.
- Audit at candidate `72f9a8ba` (`audit-core2`): real member login passed, the
  audit core mount occurred, and exactly **one** summary plus **one**
  executions read returned 200, but `audit.mount.visible_dialogs` reported
  actual **1** against expected **0** and aborted the run before correction,
  learning/export, provider mutation or restart. A read-only diagnosis attributes
  the dialog to the first-run onboarding wizard's asynchronous status gate; the
  first-run dialog-identity diagnostic (new isolated
  `audit-core2-dialogid` runtime) was **underway** at this cut, with no dismissal
  and no acceptance. Receipts: the sanitized `audit-core2` report under
  `/private/tmp/atom-audit-browser-core-72f9a8-20261117`,
  `/private/tmp/atom-audit-dialog-diagnosis-summary.md`,
  `/private/tmp/atom-audit-onboarding-harness-summary.md` and
  `/private/tmp/atom-task-wait-normal-upload-replay-summary.md`.
- Sources, read only: `/private/tmp/atom-root-task-wait-revocation-main987-20261117.{json,xml,log}`,
  `/private/tmp/atom-task-wait-api-triage-summary.md`,
  `/private/tmp/atom-task-wait-normal-upload-replay-summary.md`,
  `/private/tmp/atom-task-wait-current-main-assessment-summary.md`,
  `/private/tmp/atom-audit-dialog-diagnosis-summary.md`,
  `/private/tmp/atom-audit-core-profile-gate-repair-summary.md` and
  `/private/tmp/atom-audit-onboarding-harness-summary.md`.
- Scope of this pass: documentation only — no push, GitHub query, app/server,
  browser, test run, provider/model call, credential, live data, PostgreSQL
  cluster, install, deployment or large checkout. No product, CI, test, schema,
  policy or configuration byte changed beyond the verified main merge. The
  original audit JSON is byte-identical; the 143 claim identities, the 18 goal
  rows, the historical **111/123 (90.2%)** result and `app_complete: false` are
  unchanged.

## Navigation refresh at merged #994 (this pass)

- Started from a clean worktree on a fresh branch
  `codex/readiness-evidence-through-994` at the exact actual main
  `d701872287b16f1e74b512aa7b81fb40b92fe69a`, tree
  `fa66625df9423938e190d17c3425ed59d4e4ffb6`, sole parent
  `a33e8d8ab9352fa59324ebc067772fea4efe24d2` (#993). `origin/main` was
  verified at that exact commit; branch and base needed no synthetic merge.
- PR #994 is **merged**, not pending: exact PR head
  `b57be40f5183c294c91f81e659e1518a7daaf8dd`, all **17** check runs
  successful, and the squash merge keeps the PR-head tree `fa66625`. The
  post-merge main CI `44233465790` and Docker `44233465698` were **pending**
  at this cut, so neither a green nor a failure is claimed for them.
  Receipts: `/private/tmp/atom-pr994-final-merge-receipt.json` and
  `/private/tmp/atom-pr994-qualified-merge-result-20261117.json`.
- The #994 qualified scope is recorded exactly: **520 browser assertions** and
  **34 acceptance cases** across the audit and Learning phases, covering
  evidence download, truthful correction receipt, refusal, revision history,
  reapproval, restart readback and role boundaries; **49** selected
  audit/agent-access/header tests and **692** CI-contract checks. The local
  offline recheck measured the **1,501 ms** browser request hold from captured
  timestamps (1,338 ms to the pending UI snapshot and 163 ms from snapshot to
  release). All **42** original evidence files matched their hashes. This is **synthetic browser and persistence evidence only**;
  broader audit integrity, live models and whole-app completion remain
  unproven.
- The original verifier failure is retained, not erased: it is the obsolete
  `delayed switch report has no recorded latency` assertion. The immutable
  run summary still says `failed`, and the captured hold is not presented as
  UX latency or a before/after performance result.
- PR #993 is also **merged** at `a33e8d8ab` (tree `a69fc37d3`, exact head
  `3ae4a03c4`, all 17 checks successful). Its isolated ordinary-upload
  campaign scored **18/18** on the normal `/api/documents/upload` route with a
  USD 370.00 DOCX, workbook source and matching SHA-256, restart/reconciliation
  without a second send, cancellation and resend protection. Post-merge CI
  `44217198387` passed on **attempt 2** after the Python 3.11 package download
  broke attempt 1; Docker `44217198440` passed. The legacy text-only ingestion
  route, its replay and the prior **5 PASS / 7 FAIL / 6 NOT EVALUATED** negative
  remain separate and unadjudicated; no legacy repair, assignability or
  all-branch TASK-WAIT support is claimed.
- Sources read for this pass: this work order, the scoped readiness brief,
  the #993/#994 merge receipts and qualified-result JSON, the audit verifier
  adjudication and hold-verifier summaries, the CI-selection summary, the
  workbook PR body and the legacy-ingestion contract summary. No GitHub query,
  browser, build, test run, app/server, provider/model call, PostgreSQL
  cluster, credential, live data, install, deployment or push was made.
- Scope of this pass: **documentation only**. No product, CI, test, schema,
  policy, app or configuration byte changed. The original audit JSON is
  byte-identical; the 143 claim identities, 18 goal rows, historical
  **111/123 (90.2%)** and `app_complete: false` are unchanged.

## Goal 16 isolated fresh launch and same-world restart (dated addendum)

- **What passed:** on a detached, clean, exact main
  `d701872287b16f1e74b512aa7b81fb40b92fe69a` (#994, tree
  `fa66625df9423938e190d17c3425ed59d4e4ffb6`), the shipped provisioner created
  the isolated store. A separate command built the production Next frontend with webpack. The documented
  `launch_integrated_local_candidate.sh` then started the backend on loopback
  `8071` and the frontend on `3130` using the launcher guard and a scratch
  **SQLite** store. Real HTTP sign-in and a synthetic task create went through
  frontend-facing routes; both processes shut down and released their ports;
  the launcher restarted both, and an authenticated task read returned the
  **same task ID and title** after signing in again. The runtime source stayed
  clean at `d701872287b1`, the backend instance/child PID changed, the secret hash and
  marker creation stayed stable, and the canonical store was untouched.
  The build and replay both exited successfully. The local verification
  receipt is `/private/tmp/atom-fresh-store-qa.KShIJm/launch-verification.json`.
- **Retained first attempt:** a separate earlier child world also launched,
  signed in and created a task, then was correctly refused a restart because
  the verifier waited only for closed ports while the isolated backend PID was
  still exiting. Its logs and world are kept, and the verifier now waits for
  process exit before the official restart, which then passed.
- **Limits:** **SQLite and loopback with existing dependencies only.** This is
  not browser-interaction, true-deployment, PostgreSQL, cloud/model or
  portable-drive-removal evidence. Goal 16 remains **open**, and #995 status
  and CI are unchanged and not claimed here.
