# Web Agents creation — retry safety, exact receipts, bounded browser join

Status: **frozen frontend candidate submitted for independent review.** No
merge or self-acceptance.

Base: guided integrated `38dae97a6f9a1e00179a9ac879c14215b9983d1f`

Two source-bound slices:

- Browser custom Hire join executed product `708d4d6a5` (evidence head
  `416094ffb`): **PASS 23/23 controls**.
- Receipt-binding repair committed at `31a82b316`: strict exact-receipt
  binding; **25/25 receipt tests**, **132 focused tests**, `tsc` 0, exact
  receipt gate **14/14**.

## Actual gaps

### 1. Transport replay could duplicate a create

The shared `lib/api.ts` axios interceptor auto-retries retryable failures
(5xx/network). `createGuidedAgent` and the onboarding custom Hire
`apiClient.post('/api/agents/custom', ...)` did not opt out with the existing
`retry: false`, and had no stable operation id. A lost/503 confirmation could
therefore POST a second create after the first request had already committed.

Failure-first with the **real shared interceptor** and an adapter counter
(`failure-first-interceptor.log`):

```
guided create after 503: 4 POST attempts
custom hire after 503:   4 POST attempts
```

### 2. A mismatched or contradictory receipt could still claim success

Root's real-module probe (`/private/tmp/root_creation_receipt_binding_probe.cjs`,
preserved negative at `/private/tmp/brennan-brief/CREATION_UI_RECEIPT_BINDING_ROOT_PROBE.json`)
found the helper accepted:

- a wrong operation/audit receipt;
- a missing operation/audit receipt;
- a `verified` receipt with `effect: none`.

Failure-first Jest twins (`receipt-binding-failure-first.log`): **13 failed**
before the repair. The root probe's minimal valid twin omits the nested
`verification.audit_id` that the actual backend returns; that minimal fixture
is **not** treated as a backend-shaped valid receipt and is not weakened for.

## Repair

`frontend-nextjs/lib/agent-onboarding-api.ts`:

- `createGuidedAgent` and the new shared `createCustomAgent` pass
  `retry: false`.
- Each call always submits one `operation_id`: the caller's per-intent id, or
  an internally generated id when none is supplied. A changed goal/role/name/
  context resets it; an explicit unchanged-intent retry keeps it.
- The submitted id is normalized with the backend create prefix
  (`agent:create:<submitted>`), never with a guessed receipt prefix.
- A 2xx result is trusted only when all of these agree with the submitted
  operation:
  - exact non-empty `agent_id`;
  - top-level `operation_id` and `audit_id`;
  - nested `verification.audit_id`;
  - `verification.status` is `verified` or `already_applied`;
  - `verification.effect` is `committed`.
- `success:false`, missing/malformed ids, non-verified status, contradictory
  effect, or any receipt mismatch raises `UNVERIFIED_CREATE`; it is never
  toasted as created.
- A guided 202 `pending_approval` returns pending with no agent id; no
  refresh/attach is invented.
- No auto-resend after uncertain/5xx/network outcomes.

`GuidedAgentCreator`:

- Generates one operation id per unchanged intent and passes it to the
  helper; changing goal/context resets it.
- Calls `onAgentCreated(exactAgentId)` only for a verified result; pending
  does not refresh as if an agent existed.
- On uncertain 5xx/network or unverified responses, shows honest uncertainty;
  it never auto-POSTs.

`AgentLaunchGuide` custom Hire (onboarding-conditional):

- Uses the shared custom-create helper with the same operation-id/retry rule.
- Refreshes the parent with the exact returned `agent_id`; malformed or
  unverified 2xx does not notify the parent as created.
- Keeps `configuration:{}` / inactive `schedule_config:{}`; no promotion or
  scheduler call.

`AgentAttachModal` (canvas):

- Uses the shared guided helper with an intent operation id; attaches only the
  exact verified `agent_id`.
- Pending 202 attaches nothing; unverified/uncertain failures do not attach.

Not enabled and not touched: Agent Studio (not mounted) and template spawn
(no frontend caller). No spawn UI was invented.

## Bounded browser/API join

Executed at product `708d4d6a5`, through the existing isolated world launcher
and storage guard, with the real frontend and backend:

- ordinary custom Hire from the Agents onboarding guide;
- exactly **one** POST `/api/agents/custom`;
- request carries the submitted `operation_id`;
- 201 `success:true`, `verification.status=verified`,
  `effect=committed`, audit id equals operation id;
- authoritative list has the exact returned `agent_id` once;
- after a real reload the exact agent card appears once;
- maturity is **STUDENT**; no promotion and no scheduler configuration;
- no provider host requested; backend network boundary proved external-blocked;
- **23/23 controls PASS**.

Raw capture, screenshots, server/frontend logs and world manifest are in
`browser_custom_hire_join/`.

### Source identity reconciliation

The join's health line reported `ec69e24f4385-dirty.d48ca`, which is **ambient
canonical-repo metadata**, not the loaded snapshot: the world lives inside
`/Users/rushiparikh/projects/atom`, and `core.runtime_identity` runs
`git -C <world>`, which walks up to that repository's HEAD and dirty state.

The executed backend is the recorded working-tree snapshot
`b4aa64edb48cc5f24ed318afb627fc5a700c795f3f5626b6b0fa654455f5be49`
(recomputed and matched). Backend product files match `708d4d6a5`. The
frontend copy came from the clean `416094ffb` tree, whose files are
byte-identical to `708d4d6a5`; the run capture had no frontend dirty entry.
The build log's `79b2a41032` is the hardcoded `PINNED_REV` print in snapshot
mode, not the export identity.

Raw `/api/health` JSON and `launch_descriptor.json` were not preserved before
the disposable world was removed. Backend PID, cwd, and the identity fields
the launcher consumed are preserved in the server log. Therefore product-code
attribution is proven, while **raw health-payload attribution is incomplete**.
See `SOURCE_IDENTITY_RECONCILIATION.md` / `.json`.

## Verification

| Check | Result |
|---|---|
| Real interceptor + adapter counterprobe | 2 failed before (4 POSTs each) → **8 passed** after |
| Receipt-binding failure-first Jest twins | **13 failed** before |
| Receipt-binding after repair (guided/custom, real interceptor) | **25 passed** |
| Focused frontend suite at `31a82b316` | **132 passed** |
| `tsc --noEmit` at `31a82b316` | **0 errors** |
| Exact-receipt after-gate at `31a82b316` | **14/14**, 0 failing |
| Browser custom Hire join at `708d4d6a5` | **23/23 controls PASS** |
| Creation→authoritative reload page join | exact returned id appears once; no optimistic duplicate |
| Root independent receipt gate at `31a82b316` | **5/5 CJS counterprobes**, **51 tests / 5 suites**, helper Git match true |
| Fresh gates after current-main merge `7301110ac` | **132 passed**, `tsc` 0, exact-receipt gate **14/14** |

Logs are included. The browser join was not re-run for the receipt repair
because the backend contract was unchanged; the receipt repair is verified by
the committed focused tests, the exact-receipt gate, and root's independent
gate.

## Current-main reconciliation

Current main `230231f5114612f4b31a602190c318667e94f2f1` is the squashed guided
integration whose tree equals the guided base `38dae97a6`. It was merged into
this slice as `7301110acf5e60f913259884ab3e749b5d9d4abc`, so current main is
now an ancestor of the reviewed head. The merged product tree is exactly the
tested `31a82b316` tree; only the coordination log merged. Fresh focused tests
and the exact-receipt gate were re-run at `7301110ac` (132 passed, `tsc` 0,
gate 14/14). The browser join remains the earlier `708d4d6a5` capture; its
source identity is reconciled in `SOURCE_IDENTITY_RECONCILIATION.md`.

## Not claimed

- No guided browser served-model quality claim from a controlled transport.
- Raw `/api/health` payload / launch descriptor was not preserved (attribution
  incomplete on that field only).
- No browser claim is made for the post-browser receipt-binding repair; it is
  source-bound to `31a82b316` by tests and the exact-receipt gate.

## Boundaries

- No live model/provider/DB/credentials/send/spend/deploy/dependency.
- No backend, qualification, API client, store or review-engine change.
- No new shared test harness; the browser driver reuses the existing
  `run_isolated` + case-5 frontend-copy + `browser_verify` path.
- Node20 reused; existing frontend `node_modules` linked, not copied.
- 143 claims / 18 goals and all closed lanes unchanged; web-first, mobile-last.
- Root owns backend integration and final review; no merge.
