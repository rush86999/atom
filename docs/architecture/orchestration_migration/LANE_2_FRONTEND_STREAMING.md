# Lane 2 — Frontend WebSocket lifecycle and streamed chat

Date: 2026-09-27. Assign to a separate frontend agent. Own implementation and component verification without editing backend correction code.

## Objective and scope

Maintain correct socket ownership and deliver every relevant event to the correct turn. Prove behavior under reconnect, session updates, late events, bursts and overlapping tabs. Read repository instructions and the app-readiness plan first.

Exclusive files, after confirming no existing writer:

- `frontend-nextjs/hooks/useWebSocket.ts`
- `frontend-nextjs/hooks/chat/useChatInterface.ts`
- Their focused tests, including `hooks/chat/__tests__/useWebSocket.generations.test.ts` and existing WebSocket hook suites.

Inspect consumers in ordinary/global/canvas chat before behavior changes. Announce any necessary component edits. Do not edit backend routes, orchestrator, provider configuration, acceptance launchers, or shared quickstarts. Send backend contract discrepancies to Lane 3 with exact evidence.

## Findings to reproduce

The current generation hardening protects `onclose`; audit stale `onopen`, `onmessage` and retry timers as well. A late callback must not change state, deliver tokens, or clear the current socket.

The chat consumer uses `lastMessage` state; under frame bursts React can coalesce intermediate updates. The hook already exposes a synchronous per-message subscription mechanism. Trace current consumers and reuse that mechanism where needed instead of adding another event bus.

Review completion handling: a mismatched `streaming:complete` must not clear another turn's spinner or overwrite its answer. Treat these as source findings to reproduce, not already measured explanations of preview churn.

Also inspect reasoning-step placement: steps appended to the latest assistant must instead resolve the intended execution. Main chat consumes `streaming:*` while the canvas consumer handles `chat_token`/`chat_token_done`; capture the actual producer envelope and deliberately reconcile supported event types before claiming token coverage.

Both `/ws` and `/ws/{workspace_id}` exist in the reviewed backend. Do not repeat the reverted missing-route diagnosis. Curl/browser differences do not establish a route defect. Preserve the existing URL contract unless the exact loaded runtime disproves it.

## Implementation requirements

1. Give each socket instance a generation/identity. Only callbacks belonging to the current generation may mutate connection state or deliver events.
2. Explicit disconnect retires ownership, clears timers/state and prevents intentional-close reconnects.
3. A current transient failure schedules at most one retry. Backoff, cancellation and auth/policy terminal closes remain consistent.
4. Distinguish meaningful auth-token changes from incidental session-object changes. A same-token render must not churn connections; a changed token must follow a deliberate reconnect policy. Keep dependencies accurate; do not suppress lint to hide captured stale values.
5. Deliver token bursts through an event listener that observes every frame, with correct cleanup. Keep state snapshots only for consumers that need snapshots.
6. Bind events to session/execution/request according to the actual backend contract. Unknown/foreign completion events cannot finish a local turn. Preserve compatibility only where it can be resolved unambiguously; document unidentifiable legacy events as unsupported rather than guessing.
7. Finalization may replace provisional text. HTTP/final event/history must converge without duplicate bubbles, late-token corruption or stale success text.
8. Do not log JWTs or private message bodies. Diagnostic socket IDs, timestamps, close codes and sanitized endpoints are sufficient.

## Focused test plan

Use one hook instance and a deterministic fake socket with explicit event sequencing. Control timers and React updates; diagnose failed tests rather than assuming the harness is wrong.

- Current socket opens → connected state true.
- Socket A enters CLOSING; B becomes current; A closes once → B remains current and usable.
- Stale A open/message callbacks cannot change B's state or deliver frames.
- Explicit disconnect → disconnected, no scheduled reconnect.
- Current close → one retry; unmount cancels it; stale timers cannot create extra sockets.
- Same-token session refresh → no unnecessary teardown; changed-token refresh behaves as specified.
- Burst of uniquely numbered frames → all expected frames delivered once and in order.
- Two executions overlap → each token/completion affects only its own turn.
- Late token after finalization cannot corrupt the final answer.
- Current failure/reconnect resubscribes required channels without multiplying listeners.
- Legacy hook consumers still receive the supported state API.

Run the stale-close and frame-loss negative controls against the pre-fix implementation or a controlled deliberately broken variant. A test that passes a broken baseline does not demonstrate the fix. TypeScript compilation is necessary but insufficient.

## Integration boundary

Lane 3 owns the final browser environment. Supply your patch and deterministic results, then jointly verify actual browser navigation, login/logout, refresh, reconnect and two tabs on the final candidate.

Measure socket creation/closure and active connections per mounted consumer; total socket count alone is not a correctness metric. Distinguish expected navigation from unexpected reconnect churn. Use a token-bearing test provider for protocol verification and a real-model browser smoke separately. Do not claim streaming from status frames alone.

No new acceptance-world copies, model installation, storage moves or shared-server restarts from this lane. If browser testing needs a separate frontend, request an assigned farm/distDir/port from Lane 3.

## Handoff

Deliver scoped diff and hashes, test results and negative controls, event-contract assumptions, residual backend dependencies, and sanitized diagnostics. Do not declare the app ready; this lane closes frontend behavior only, with final public verification owned by Lane 3.
