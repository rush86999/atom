# Manual test quickstart — isolated chat preview

Status: **partial preview.** Some advertised workflows are verified at the
API boundary; the visual browser pass and the real-model general-chat turn
are **not** done. Read "Verified" and "Not verified" before inviting
anyone to test.

## Where to open the app

| Surface | URL | Notes |
|---|---|---|
| App (chat) | http://127.0.0.1:3090/chat | Isolated frontend instance, `NEXT_PUBLIC_API_URL=http://127.0.0.1:8090` |
| Login | http://127.0.0.1:3090/login | Standard Atom login |
| API | http://127.0.0.1:8090 | Isolated backend, macOS seatbelt, loopback only |

Both processes are running now. Your own dev frontend on
`http://localhost:3000` was **not** touched — the preview runs from a
separate directory (`/tmp/preview_frontend`) so it cannot collide with it.

### Isolation (verified)

- Backend world: `backend/data/acceptance_worlds/preview_app`
  - source `a3ebb7837` (export `7622552d22`), fixture DB `78daa152219…`,
    credential-scrubbed, seatbelt network boundary, own PID 88554.
- The compiled frontend bundle references `127.0.0.1:8090` and contains
  **no** reference to `localhost:8001`, so the browser cannot reach the
  usual development backend from this instance.
- Contract preflight on launch: `ATOM_TASK_LIFECYCLE_ENABLED=1`,
  `CHAT_FINALIZATION_M2=1`, all lifecycle tables present.

## Logging in

Use the ordinary Atom login for the preview world. Do not paste
credentials here — this file is committed. The preview world is seeded
from the sanitized acceptance fixture, so the usual local account applies.

## Copyable prompts

1. **Eight-item lookup**
   ```
   find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16
   ```
2. **Formatting** — `make this easier to read`
3. **Re-search** — `search again and show the same items`
4. **Field selection** — `show the list price column`
5. **Item replacement** — `replace TK 1624 with SLE16-8`
6. **Unrelated then resume** — `what is a bead roller?` then
   `back to the price list`

## Expected visible outcomes

| Step | Expected |
|---|---|
| 1 | Eight entries **in the requested order**; ambiguous ones say so honestly; each entry shows where the identity matched (e.g. `matched at A26`) and the value cell with its basis |
| 2 | A new concise answer; the previous answer is unchanged |
| 3 | A new read; saved-copy vs live status stated truthfully |
| 4 | Correct labelled values, no silent substitution |
| 5 | Updated list, without resurrecting earlier distractors |
| 6 | Correct resumption, or a focused clarifying question |

## What is verified, and how

Verified by driving the same HTTP endpoints the browser calls, against
the running preview backend. **This is not a visual browser pass.**

| Step | Result | Evidence |
|---|---|---|
| Eight-item lookup | **Verified** | All 8 in order; `matched at A26 / A101 / A42 / A106`, `at A88, B88, L88`; exec `60742008…` |
| Formatting | **Verified** | Second answer differs, first answer unchanged |
| Re-search | **Verified** | Third turn served, saved-copy status truthful |
| History durability | **Partial** | 6 rows durable in the world DB; `GET /api/chat/sessions/{id}` returns metadata only, so reload was not verified through the UI |
| General chat (real model) | **NOT verified** | No real model credential is configured in this world. The plan requires one real-model browser turn before claiming normal chat |
| Login / send / stream in the browser | **NOT verified** | Login page renders (HTTP 200); the authenticated browser session was not exercised |
| Canvas edit (M09/M10) | **NOT verified** | No disposable canvas fixture is seeded in the preview world |
| Simulated send (M13) | **NOT verified** | No controlled sink is wired in the preview world |

## Known limitations

- **Do not treat mutation, recovery, streaming, or concurrency guarantees
  as demonstrated by this preview.** Streaming emits no tokens in this
  world; crash reconciliation, concurrent-claim races and durable
  effect counts are covered only by integration tests, not by this
  running instance.
- The workbook answers come from a **materialized copy** (ingested
  2026-09-07), not a live file. The UI says so; absence is never claimed
  beyond the indexed content.
- Canvas editing, cross-source connectors, and sandboxed outbound send
  are **outside** the supported list for this preview.

## Safe restart

```bash
# backend (isolated world)
cd /Users/rushiparikh/projects/atom/backend
venv314/bin/python /tmp/preview_server.py 8090 preview_app

# frontend (separate instance; does not touch your :3000)
cd /tmp/preview_frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8090 NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
  npx next dev -p 3090
```

Logs: `backend/data/acceptance_worlds/preview_app/server.log` and
`/tmp/preview_frontend.log`. Never point these at the live dev database.

## Feedback template

Step · expected behaviour · actual behaviour · time · optional
screenshot. Do not attempt crashes, corruption injection, or database
inspection — those are agent-operated cases.
