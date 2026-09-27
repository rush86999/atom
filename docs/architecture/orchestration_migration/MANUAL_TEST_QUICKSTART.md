# Manual test quickstart — isolated chat preview

Status: **read-only preview, browser-verified.** Login, the eight-item
lookup, formatting, re-search and reload were performed in a real browser
against the running preview. Canvas editing, simulated sends, general
chat with a real model, and streaming are **not** available — see
Limitations. Acceptance overall remains incomplete.

## Where to open the app

| Surface | URL |
|---|---|
| **App (chat)** | **http://127.0.0.1:3090/chat** |
| Login | http://127.0.0.1:3090/login |
| API | http://127.0.0.1:8090 |

Both processes are running. Your own frontend on `http://localhost:3000`
was **not** touched — the preview runs from a separate directory
(`/tmp/preview_frontend`).

## Logging in

A fixture account exists **only** in this isolated world:

- email: `preview@fixture.local`
- password: `PreviewOnly-2026!`

No live credential was imported. Sign in at the login URL with those.

## Isolation (verified from real browser traffic, not bundle strings)

Every off-origin request the browser made went to `http://127.0.0.1:8090`
— auth, chat message, chat history, sessions, trace. **Nothing** reached
`localhost:8001` (the usual development backend). Chat calls observed:

```
POST API/api/chat/message
GET  API/api/chat/history/{session_id}
GET  API/api/chat/sessions
GET  API/api/chat/sessions/{session_id}
GET  API/api/chat/trace/{session_id}
```

Backend world: `backend/data/acceptance_worlds/preview_app`, source
`a3ebb7837`, credential-scrubbed fixture, macOS seatbelt (loopback only),
own process. Contract preflight: `ATOM_TASK_LIFECYCLE_ENABLED=1`,
`CHAT_FINALIZATION_M2=1`, all lifecycle tables present.

> Note: the preview backend adds `http://127.0.0.1:3090` to its CORS
> allowlist for this world only. Without it the browser preflight fails
> and login silently reports "Unable to connect to the server".

## Browser-verified workflows

| Step | Action | Verified result |
|---|---|---|
| Login | email + password above | Redirects to `/dashboard`; API `POST /api/auth/login` → 200 |
| M02 | eight-item lookup (prompt below) | **8/8 items visible, in the requested order**; ambiguous ones state "several rows match … needs your confirmation"; evidence shows identity cells (e.g. `matched at A26`, `at A88, B88, L88`) alongside the value cell and its basis |
| M03 | "make this easier to read" | New answer rendered; the previous answer is unchanged |
| M04 | "search again and show the same items" | New read served; 8/8 still visible; saved-copy status stated |
| M08 | Refresh the browser | **8/8 items and both user turns survive reload**; history loads via `GET /api/chat/history/{session_id}` |

The history endpoint the UI actually uses is `/api/chat/history/{id}`.
(`/api/chat/sessions/{id}` returns session metadata only — that is not the
history path and its behaviour is not a defect.)

## Copyable prompts

1. ```
   find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16
   ```
2. `make this easier to read`
3. `search again and show the same items`

## Limitations — read before assuming a workflow works

- **General chat is NOT verified and does not answer.** No model provider
  is configured in this world; a general question renders the user turn
  with no assistant reply. Normal chat stays unverified until a
  real-model browser turn succeeds. No fixture answer is substituted, so
  you will not be misled by canned text.
- **No streaming.** The browser opened **no WebSocket** in this
  configuration; chat is HTTP request/response only.
- **No canvas editing, no simulated send.** No disposable canvas fixture
  and no controlled send sink are wired, so M09–M13 are unavailable.
- **Answers come from a materialized copy** (ingested 2026-09-07), not a
  live file. The UI says so; absence is never claimed beyond the indexed
  content.
- Mutation, crash recovery, concurrency and durable-effect guarantees
  are **not** demonstrated by this instance.

## Safe restart

```bash
# backend (isolated world; keeps CORS allowance for :3090)
cd /Users/rushiparikh/projects/atom/backend
venv314/bin/python /tmp/preview_server.py 8090 preview_app

# frontend (separate instance; does not touch your :3000)
cd /tmp/preview_frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8090 NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
  npx next dev -p 3090
```

Logs: `backend/data/acceptance_worlds/preview_app/server.log`,
`/tmp/preview_frontend.log`. Never point these at the live dev database.

## Feedback template

Step · expected behaviour · actual behaviour · time · optional
screenshot. Do not attempt crashes, corruption injection or database
inspection — those are agent-operated cases.
