# Lane 2 handoff — frontend WebSocket lifecycle and streamed chat

Date: 2026-09-27. **Lane 2 complete**, including the follow-up pass that closed
every gap the first pass reported. **This lane does not declare the app ready** —
final browser verification is Lane 3's.

## 1. Scope and hashes (sha256)

### New shared mechanisms

| File | sha256 | What it is |
|---|---|---|
| `frontend-nextjs/hooks/chat/turnBinding.ts` | `fa4c215bf838a31a88b613044234f409bdf93e58ec16564d8e7ee7020e139666` | Pure turn-binding rules. Why they are general, not per-surface. |
| `frontend-nextjs/hooks/chat/useTurnStream.ts` | `2b8cb365058aa0f2d4e3ca7b3beb4924ab4b67cad67b99faeab9d22632ae32ec` | Lossless socket intake + binding. **Owns the socket** so a panel cannot open two. |
| `frontend-nextjs/lib/guardedSocket.ts` | `9c25ac32d5b198e88fbd349aaff2b5c386e8fcee65a239fd3b8eafde60486854` | Generation guard for raw `new WebSocket` surfaces. |
| `frontend-nextjs/tests/helpers/wsMock.ts` | `2a8fc7c884b31d32d3d944cf646c276c967b7fca1192bd1667c681f655d2edfc` | One test seam for the `onMessage` migration. |

### Exclusive hooks

| File | sha256 |
|---|---|
| `frontend-nextjs/hooks/useWebSocket.ts` | `c9ecca740548215197e3e932f64683f5765b70459fb345e1d81ba7507f4cd22e` |
| `frontend-nextjs/hooks/chat/useChatInterface.ts` | `d36521954f3a6aad11059fab3ff079e839b4d6608f27d28c768e3c939cf4062f` |

44 files changed, 1279 insertions, 799 deletions. 10 new files, 34 modified.
`frontend-nextjs/next-env.d.ts` is a Next.js-generated file rewritten by another
agent's running preview instance and is **not** part of this diff.

## 2. Event contract — measured from the producers

| Producer | Channel | Envelope |
|---|---|---|
| `integrations/chat_orchestrator.py` (the only POST every chat surface makes) | `user:{user_id}` | `chat_token {session_id, execution_id, delta}` · `chat_token_done {session_id, execution_id, content, elapsed_s}` · `chat_heartbeat` · `agent_step_update {step, agent_id, execution_id, session_id}` · `canvas:update` · `agent_status_change` |
| `core/agent_execution_service.py`, `core/atom_agent_endpoints.py` (agent **task** streaming) | workspace | `streaming:start` · `streaming:update {id, delta}` · `streaming:complete {id, content}` |

**The chat orchestrator emits no `streaming:*` at all.** Verified there are
exactly three `chat_token*`/`chat_heartbeat` emitters in the whole backend, all
in `chat_orchestrator.py`, and **all three carry both `session_id` and
`execution_id`**. So the "make `execution_id` mandatory" item from the first
pass is closed by measurement, not by a backend change: the contract is already
mandatory in practice. `/ws` exists at `websocket_routes.py:17` and
`/ws/{workspace_id}` at `api/websocket_routes.py:36`; the missing-route diagnosis
reverted earlier is not repeated, and the URL contract is unchanged.

`core/websockets.py::connect` auto-subscribes every socket to `user:{id}`, so
each surface receives **every** turn on the account, including turns a second
tab or an API client is driving. That is why binding, not arrival order, decides
which reply a frame belongs to.

## 3. The headline finding

Three surfaces POST to `/api/chat/message`. All three read the socket's
`lastMessage` **state slot** and handled only `streaming:*` — a family no chat
turn produces. So the main chat, the global widget and every other chat surface
received every token of every reply and **rendered none of them**; the reply
appeared only when the POST resolved. `chat_token*` was consumed by exactly one
file, `pages/canvas/[id].tsx`.

This is a frontend omission, not preview churn, and it is the mechanism behind
"the chat does not stream".

## 4. What was fixed

### 4.1 Socket lifecycle (`useWebSocket`)

Commit `59f6ca6d5` added a per-socket generation and applied it to `onclose`
only. Seven defects, each reproduced as a failing test first:

1. stale `onopen` cancelled the **live** generation's pending reconnect — a real outage never recovered;
2. stale `onopen` re-sent `initialChannels` on the dead socket, leaving the live one unsubscribed;
3. stale `onmessage` fanned frames out to every `onMessage` handler;
4. stale `onmessage` overwrote `lastMessage`;
5. stale `onmessage` corrupted `streamingContent`;
6. each observed close overwrote the previous retry handle, so earlier ones opened sockets **after** an explicit `disconnect()`;
7. `connect` depended on the `session` **object**, so every next-auth poll tore the socket down.

Fixed: the generation is checked first in all three callbacks; one cancellable
retry, tagged with the generation that owns it; identity keyed on the token
**string** (`authToken`), with no lint suppression and no captured stale value.

### 4.2 Frame loss — measured, not assumed

Two consumers on one socket, fed the same 50-frame burst: the `onMessage`
listener was called **50 times**, the `[lastMessage]` effect **once**. The
listener is the only lossless path.

**Every production consumer of `useWebSocket` now reads through `onMessage`.**
The 15 that read the state slot:

- `useChatInterface`, `GlobalChatWidget` — via `useTurnStream` (below);
- `AgentWorkspace` — a run's `agent_step_update` frames arrive as a burst, so the trace rendered with holes;
- `pages/canvas/[id].tsx` → `CanvasPanel`, `MiniAppHarness`, and `AgentWorkspace` → `canvas-host` (`CanvasHost`) — all three gained an optional `onSocketMessage`; the prop remains as a fallback for callers with no live socket, so every existing test and call site is unchanged;
- `useBoardWebSocket` — a drag emits create → move → transition as a burst, so the cache was invalidated for only the last event;
- 6 dashboards, `pages/agents`, `pages/sales`, `AgentStudio`, `AutoDevReviewPanel`.

For the "something happened, go refetch" consumers, observing every frame would
have turned a burst into one refetch per frame, so each has an explicit
in-flight ref guard. **The guard suppresses the refetch, never the notification**
— a first attempt guarded the toast too, and `KnowledgeCommandCenter`'s own test
caught it. A toast is cheap and per-frame; a refetch is expensive and idempotent.

### 4.3 Turn binding (`hooks/chat/turnBinding.ts` + `useTurnStream`)

Per `AGENTS.md` ("look for the existing general mechanism"), the rules are pure
functions over a message array, used by every surface, and tested directly with
no socket and no render (29 tests). `useTurnStream` owns the lossless intake and
**owns the socket**, returning `socket` for the surface — so "one socket per
panel" is structural, not a convention a second caller can quietly break.

- the widget and the main chat now **stream live**, bound by `execution_id`;
- reasoning steps attach to the execution they name, opening the turn's bubble
  on demand — replacing "append to the last message if it is an assistant",
  which filed a new turn's trace under the previous turn's answer;
- a foreign or unidentifiable completion cannot clear the local spinner or
  append its answer; the turn is released by its own POST or the 120s net;
- a late frame cannot corrupt a finalized answer; a duplicate completion cannot
  produce a second bubble;
- the HTTP response converges **in place** on the streamed bubble;
- HITL frames are session-scoped;
- an id-less frame is **counted and excluded**, never guessed at. Counters only,
  never content.

### 4.4 Raw sockets with no generation guard

`components/Teams/TeamChatPanel.tsx` (team switch), `components/shared/CommentSection.tsx`
(channel switch), `components/Collaboration/CollaborativeCursor.tsx` (session
switch) each opened a raw socket: when the effect re-ran, the previous socket's
late `onmessage` could still append **another room's messages** to the room now
on screen. All three now use `createSocketGuard()` (14 tests, 2 negative
controls). The guard is per owner, so two independent surfaces don't steal
ownership from each other.

Two behaviours were preserved deliberately: `CommentSection`'s `unsubscribe`
frame (the server expects it — hence the guard's `onRetire` hook) and
`CollaborativeCursor`'s malformed-frame diagnostic (hence `onParseError`).
`CommentSection`'s send now requires an OPEN socket, which is the actual browser
contract — `WebSocket.send` throws `InvalidStateError` while CONNECTING.

`contexts/WakeWordContext.tsx` is **deliberately left alone**: it targets a
different service (the audio processor on :8008) with a different protocol, and
is not part of this app's socket contract. The two dead
`hooks/useWhatsAppWebSocket*.ts` hooks (zero production consumers) carry a
header pointing at the guard so nobody adopts them unguarded, and
`README_TEAM_CHAT.md` no longer shows a bare socket as the example.

## 5. Negative controls

Each asserts the DEFECT is present in a deliberately broken variant. **If a
control starts passing, it has stopped detecting its bug.**

| Control | Detects |
|---|---|
| `CONTROL: stale onmessage DOES reach listeners…` | 4.1 #3 |
| `CONTROL: stale onopen DOES cancel the pending retry…` | 4.1 #1 |
| `CONTROL: duplicate closes DO leak uncancellable retries…` | 4.1 #6 |
| `CONTROL: same-token session churn DOES rebuild the socket…` | 4.1 #7 |
| `CONTROL: a superseded onmessage DOES deliver without the guard` | 4.4 |
| `CONTROL: a superseded onopen DOES subscribe without the guard` | 4.4 |

One candidate defect was **dropped rather than claimed**: duplicate closes do
*not* produce extra sockets, because `connect()`'s OPEN/CONNECTING guard absorbs
the second timer. The test was retargeted to the leak that is real (#6).

## 6. Test results

- New: 24 socket, 20 turn-binding, 29 pure-binding, 17 shared-hook, 14 guard = **104 new tests**.
- **Full suite: 707 suites / 11,541 tests pass. 12 suites / 75 tests fail — the
  identical pre-existing set**, confirmed by stashing this work and re-running
  (outlook-probe, Tableau/Linear/Teams/Workflow/Salesforce, two `.a11y` suites,
  agent-terminal, auth-headers, dashboard, canvas-state). Zero regressions.
- `components/canvas/__tests__/TrainingPanel.test.tsx` is **flaky** (1 failure in
  3 runs, in a component this lane never touched) — not a regression, but worth
  someone owning.
- `tsc --noEmit` clean for `tsconfig.json` **and** `tsconfig.tests.json`, apart
  from one **pre-existing** error in `useWebSocket.generations.test.ts:80`
  (verified on the clean tree).
- ESLint: no errors. **No `eslint-disable` was added anywhere.** One pre-existing
  dead directive in `canvas-host.tsx` was removed. The 4 remaining warnings are
  all pre-existing and unchanged.

### Tests changed, and why

`useWebSocket` consumers are driven through `onMessage` now, so any test that
mocked the hook with a `lastMessage` slot was testing the coalescing behaviour
the code no longer has. 14 suites were migrated onto `tests/helpers/wsMock.ts`,
which delivers to the slot **and** every listener, and whose `burst()` reproduces
the case the change exists to survive. Two tests also had to change meaning, and
both changes are deliberate:

1. `useChatInterface.test.ts` **"mismatched streaming complete resets processing"
   was inverted.** It asserted the cross-turn spinner kill as correct — the exact
   bug the work order asked me to fix. It is now `… does NOT reset processing`.
2. `GlobalChatWidget.test.tsx` **"keeps messages unchanged when an agent step
   arrives while a user message is last" was rewritten.** It asserted that a step
   is buffered and never shown, which was the misattribution bug. It now
   asserts the fix: the step is not attached to the user's message or any
   earlier answer, and opens its own turn.

`pages/agents` tests that staged a frame before mount now deliver it while the
run is in flight. The old effect re-processed the sticky slot whenever
`activeAgentId` changed, so a pre-staged frame was re-appended after the run
started — an artifact of the slot, not a behaviour.

## 7. Socket accounting

`/chat` mounted **three** independent `useWebSocket` instances
(`useChatInterface`, `AgentWorkspace`, and the app-wide `GlobalChatWidget`).
After this change `useChatInterface` and `GlobalChatWidget` each open **one**
socket that they own and that cannot be doubled by a second caller, and
`AgentWorkspace` keeps its own. Per-consumer creation/closure is asserted in
`useTurnStream.test.ts` (`opens exactly one socket`; `does not open a second
socket across re-renders or a reconnect`).

`/chat` still holds two sockets for two distinct subscriptions (the chat's own
`user:{id}`-carried turn stream, and the workspace-channel trace in
`AgentWorkspace`). Consolidating those is a real option but is an architectural
change across two components and the app-wide widget, so it is **left as a
decision, not taken unilaterally** — see §8.

## 8. Residual, for Lane 3

1. **No browser was driven.** Navigation, login/logout, refresh, reconnect and
   two-tab behavior on the final candidate are unverified. TypeScript plus
   deterministic tests are necessary but insufficient for §4.
2. **Decide whether `/chat`'s two sockets should be one.** Both are correct
   today; the duplication is cost, not a defect.
3. **A frame with no `execution_id` is dropped, not displayed.** Measured as
   impossible on the current backend (all three emitters set it), so this is
   defence in depth. If a future emitter omits it, that turn's tokens will not
   render — the counters in `_unboundFramesRef` are the signal.
4. `components/canvas/__tests__/TrainingPanel.test.tsx` is flaky; unrelated to
   this lane.
5. `contexts/WakeWordContext.tsx` keeps an unguarded raw socket, deliberately —
   different service, see §4.4.

## 9. Diagnostics hygiene

No JWT and no message body is logged anywhere in the patch. Socket diagnostics
carry generation, close code, and the endpoint with its query string stripped
(`redactSocketUrl`, and `sanitizedEndpoint` in the hook). Unbound-frame counters
record kinds and counts only. Asserted by
`never writes a token to the console across a full lifecycle`, which sweeps
`log`/`info`/`warn`/`error`/`debug` across a full
connect → message → drop → retry → open → disconnect → settle cycle and fails
if the token string appears in any of them.

## 10. Boundary respected

No backend file, orchestrator, provider config, acceptance launcher, shared
quickstart, or acceptance world was touched. `scripts/restart_backend.sh` was
not run and no backend process was restarted.
