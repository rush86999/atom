# Web Agents creation — no duplicate POST, verified receipts, exact reload

Status: **frozen frontend candidate submitted for independent review.** No
merge or self-acceptance.

Base: guided integrated `38dae97a6f9a1e00179a9ac879c14215b9983d1f`  
Executed source: `708d4d6a5`

## Actual source gap

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

Expected safeguard: exactly 1 POST, no automatic replay.

## Repair

`frontend-nextjs/lib/agent-onboarding-api.ts`:

- `createGuidedAgent` and the new shared `createCustomAgent` pass
  `retry: false`.
- Both accept a per-user-intent `operation_id` query parameter.
- 2xx `success:false`, missing/non-string `agent_id`, or missing/non-verified
  `verification` raises `CREATION_NOT_ACCEPTED`/`UNVERIFIED_CREATE`; it is
  never treated as created.
- The raw `agent_id` and `operation_id`/`audit_id`/`verification` are typed
  internally; no opaque ids or proof scores are exposed in the dialogs.
- A guided 202 `pending_approval` is returned as pending with no agent id.

`GuidedAgentCreator`:

- Generates one operation id per unchanged intent and passes it to the
  helper; changing goal/context resets it.
- Calls `onAgentCreated(exactAgentId)` only for a verified result; pending
  does not refresh as if an agent existed.
- On uncertain 5xx/network or unverified responses, shows honest uncertainty;
  it never auto-POSTs. An explicit retry of the unchanged intent reuses the
  operation id for reconciliation.

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

## Verification

| Check | Result |
|---|---|
| Real interceptor + adapter counterprobe | 2 failed before (4 POSTs each) → **8 passed** after |
| Focused frontend: real interceptor, interceptor suite, GuidedAgentCreator, AgentLaunchGuide, AgentAttachModal, Agents page, creation→reload page join | **115 passed** |
| `tsc --noEmit` | **0 errors** |
| Creation→authoritative reload page join | exact returned id appears once; no optimistic duplicate |

The focused logs are included. Existing qualification/backend controls are
preserved by the untouched base `38dae97a6`; no backend, qualification, API
client, store or review-engine change.

## Not yet claimed

The bounded ordinary **custom Hire browser/API join** at this frozen build is
prepared as the next finite step. No browser capture is claimed here. The
guided browser path cannot claim served model quality from a controlled
transport.

## Boundaries

- No live model/provider/DB/credentials/send/spend/deploy/dependency.
- No new API client/store/review engine, worlds or shared test harness.
- Node20 reused; existing frontend `node_modules` linked, not copied.
- 143 claims / 18 goals and all closed lanes unchanged; web-first, mobile-last.
- Root owns backend integration and final review; no merge.
