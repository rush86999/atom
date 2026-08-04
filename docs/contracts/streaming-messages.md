# WebSocket Streaming & Agent-Response Message Contracts

Single source of truth for the wire format shared between the backend
(`core/websockets.py`, `core/atom_agent_endpoints.py`,
`core/agent_execution_service.py`) and the frontend (`hooks/useWebSocket.ts`,
canvas components, `SlashCommandBar`).

These contracts were derived from the code paths exercised during the
end-to-end TDD bug hunt (see `backend/tests/BUG_HUNT_LOG.md`, BUG-004/006/008).
Drift between the two sides is what caused those bugs; this document is the
reference both suites assert against.

---

## 1. Streaming token messages

The backend streams LLM output token-by-token over the workspace WS channel
(`/ws/{workspace_id}`), then sends a terminal "complete" message.

### `streaming:update` — partial delta

```json
{
  "type": "streaming:update",
  "id": "<message-id>",
  "delta": "<incremental text>"
}
```

- `type` **MUST** be `"streaming:update"`.
- `id` correlates deltas belonging to the same logical message.
- `delta` is appended to the accumulated buffer for `id`.

### `streaming:complete` — stream finished

```json
{
  "type": "streaming:complete",
  "id": "<message-id>",
  "content": "<full final text>",
  "complete": true,
  "metadata": { "execution_id": "...", "tokens_total": 123 }
}
```

- `type` **MUST** be `"streaming:complete"`. This is the **authoritative**
  completion signal — the frontend keys buffer deletion on `type`
  (BUG-004 fix). The `complete: true` field is redundant and emitted for
  backward compatibility; consumers MUST NOT rely on it as the sole signal.
- `content` carries the full assembled text (replaces the accumulated buffer).

### Frontend contract (`useWebSocket.ts`)

- Enter the streaming branch on `type === "streaming:update" | "streaming:complete"`.
- Accumulate `delta` for updates; on `streaming:complete` the buffer entry is
  **deleted** (the final text lives in the regular message channel).
- Deletion MUST key on `message.type === "streaming:complete"`, never on a
  separate `complete` flag.

### Backend emitters

- `core/atom_agent_endpoints.py:1967` — `STREAMING_COMPLETE` with `complete: True`.
- `core/agent_execution_service.py:328` — same shape, plus `metadata`.

---

## 2. Agent HTTP response envelope (`/api/atom-agent/chat`)

Logical success and failure are both returned over HTTP; the `success` boolean
is authoritative, NOT the HTTP status code alone.

### Success

```json
{
  "success": true,
  "response": { "message": "<reply>", "actions": [] },
  "session_id": "..."
}
```

### Logical failure (HTTP 200)

The backend returns several logical-error envelopes with HTTP 200
(`core/atom_agent_endpoints.py:204,238,693,946`):

```json
{ "success": false, "error": "<human-readable reason>" }
```

- Frontend consumers MUST check `data.success === false` and surface an error
  state — they MUST NOT infer success from `response.ok` or the presence of a
  body (BUG-006 fix in `SlashCommandBar`).

### Hard HTTP errors

Genuine transport/server errors (500, 503, network) arrive via the
`catch` path of the HTTP client; these carry no parsed body.

---

## 3. Budget-exceeded exit status

When the pre-LLM spend gate denies an agent run, the internal loop sentinel is
`status="budget_exceeded"`. This is an **internal** value and MUST be normalized
before crossing any boundary:

- **DB persistence** (`atom_meta_agent.py`): maps to `ExecutionStatus.FAILED`
  (`"failed"`) with `error_message = "Budget exceeded — execution halted by
  spend gate"`.
- **`GenericAgent.execute` return payload** (`generic_agent.py`): maps to
  `"failed"` before constructing the return dict (BUG-002 fix). The return
  payload status MUST always be a valid `ExecutionStatus` value.

`budget_exceeded` is NOT a member of `ExecutionStatus`
(`core/models.py:128`) and must never reach the API/WS layer or the frontend.

---

## 4. Admin budget API status codes (`/api/admin/tenants/{id}/budget`)

| Scenario                         | Status | Body                      |
|----------------------------------|--------|---------------------------|
| Valid GET / PUT                  | 200    | resolved budget state     |
| Unknown tenant (GET or PUT)      | 404    | `{"detail": "Tenant not found"}` |
| Invalid `enforcement_mode` (PUT) | 422    | `{"detail": "Invalid enforcement_mode..."}` |
| Non-super-admin caller           | 403    | `{"detail": "Super Admin access required..."}` |

Logical errors MUST use the correct 4xx status code, never 200 with an error
body (BUG-008 fix).
