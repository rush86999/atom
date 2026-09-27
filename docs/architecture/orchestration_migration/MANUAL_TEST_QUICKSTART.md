# Manual test quickstart — chat orchestrator preview

**Status: preview ready for you to test now.** This is the *manual-test preview*
milestone from `CHAT_ORCHESTRATOR_APP_READINESS_PLAN_2026_09_26.md`, not a claim
that every workflow is finished. The supported list and the known limits are
below; read the limits before you conclude anything from a failure.

Every step in section "What to test" has already been run in a real browser
against this exact running instance. Where a step is listed as NOT VERIFIED, it
is because it did not pass — not because it was skipped.

---

## 1. Where to open the app

| | |
|---|---|
| **Open this** | **http://localhost:3101** |
| Backend API | http://127.0.0.1:8051 (you do not need to open this) |
| Isolated world | `preview_v1`, run `run-560c6ce8afe9` |
| Isolated database | `backend/data/acceptance_worlds/preview_v1/runs/run-560c6ce8afe9/data/atom.db` |
| Backend log | `backend/data/acceptance_worlds/preview_v1/preview_backend.log` |
| Frontend log | `backend/data/acceptance_worlds/preview_v1/preview_frontend.log` |

**This is a separate app from your usual one.** Your normal stack (frontend on
:3000, backend on :8001) is untouched and still running. Do not point this
frontend at :8001, and do not expect the preview to see anything you create in
your normal app after this world was built.

## 2. Signing in

Use **the same email and password you normally use** — `admin@example.com` and
your usual password. No new credentials were created for you and none are
written down here.

Why your normal password works: this world is a sanitized snapshot of your own
development database, so the `admin@example.com` row — including its password
hash — is byte-identical to the one in your real app. That was verified, not
assumed. What is *not* carried over is anything you have done since the
snapshot was taken.

If you would rather not type a password: `GET /api/dev/bootstrap-session` on
the preview frontend returns a session token without one. It is a development
convenience that exists in the current code; it is not part of what is being
certified here.

## 3. What you can test now

| Supported and verified in a browser | Notes |
|---|---|
| **General chat** — a normal question gets a real answer | Real model, `opencode-go`. No workflow is triggered. |
| **The seeded eight-item workbook lookup** | Requested order preserved, ambiguity reported honestly, every value carries its sheet, row, identity cell and price cell. |
| **Following-up turns in the same conversation** | "Make this easier to read" re-renders from existing evidence without a new read. |
| **Explicit re-search** | "Search again…" performs a genuinely new read. |
| **Selecting a different basis** | "Use the factory price instead" returns that column, labelled. |
| **Replacing an item** | "Replace U-22 with U-38" updates the list. |
| **An unrelated question, then back** | The task is not lost or corrupted. |
| **Refresh / reopen** | The final answer and its evidence survive a real browser reload. |
| **Two turns at once** | Replies and streams stay attached to their own turn. |
| **Honest source failures** | When a source cannot be read, the app says so instead of claiming the item is absent. |

### Not supported — do not test these, and do not read a failure as a defect

| Excluded | Why |
|---|---|
| Canvas editing / artifact mutation (M09, M10) | **No browser-level verification exists.** The edit lanes are covered by integration tests only. Do not use this preview to try an edit. |
| Sandboxed outbound send (M13) | **Not implemented in the preview.** No draft-then-authorize flow is wired. |
| Live email, calendar, drive, HubSpot and other connectors | The world's credential store is seeded with *model* providers only, deliberately. Integration credentials are not copied, so these adapters are honestly unavailable. |
| Multi-user / multi-host behaviour | Single local process. Nothing here supports a multi-host claim. |
| Crash, corruption and restart injection | Automated, agent-operated. Not for you to run. |

## 4. What to test — the prompts

Open http://localhost:3101, sign in, then send these **in order, in one
conversation**. The order matters: steps 3–6 only mean anything as
continuations of step 2.

**1 — Normal question**
```
In one sentence, what is a price list used for?
```
Expect: a relevant answer. No file is created, no tool runs, nothing is edited.

**2 — The seeded eight-item lookup**
```
find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16
```
Expect all eight, **in the order you asked**:
- `No. 381` and `No. 622` are reported as **ambiguous** — several rows match
  and the app asks which one you mean. That is the correct answer, not a bug.
- `U-22` → 1,777 · `TK Manual Flanger` → 1,609 · `SLE24-16` → 8,880 ·
  `TK 1624` → 8,040 · `GSL48-16` → 14,166
- `TK Multi Wheel Gang Slitter` is reported as a **candidate** matched through
  an alias, with its price and provenance attached.
- Each found item shows its sheet, row, the **identity cell** it matched in, and
  the **price cell** with its column name. Example shape:
  `1,777 (LINMAC!R26 matched at A26, column C26 'List Price')`
- The footer names the source as a **saved copy** with its saved-at timestamp,
  and says unlisted sheets may contain more. That is not an absence claim about
  the live workbook.

**3 — Same content, easier to read**
```
Make this easier to read
```
Expect: a shorter, re-ordered answer. Scrolling up, the previous answer is
**unchanged**. This must not re-read the workbook.

**4 — Explicit re-search**
```
Search again and show the same items
```
Expect: a new read actually happens, and the saved/live status is restated
honestly. The wording may differ from step 2; the values must not.

**5 — Choose a different basis**
```
Use the factory price instead
```
Expect: the `Factory Price` column's values, clearly labelled as that basis.
Expect **no silent substitution** — if a basis is unavailable, the app should
say which bases exist rather than quietly returning a different one.

**6 — Replace one item**
```
Replace U-22 with U-38
```
Expect: the list now reflects U-38 in place of U-22, and the previously
distracting items do **not** reappear.

**7 — Unrelated question, then come back**
```
What is the capital of France?
```
Expect: a normal answer to that, and the workbook task is not corrupted.
Then ask `show the items again` and expect the same task, not a fresh or
confused one.

**8 — Refresh the browser**
Press the browser reload (or close and reopen the tab).
Expect: the same final answers, the same evidence, and the same artifact
association. Nothing duplicated, no duplicate assistant bubble.

**9 — Two turns at once**
Open a second tab on http://localhost:3101 and send a question in each.
Expect: each reply and each stream belongs to its own turn. No crossed
messages.

## 5. Known limitations, stated plainly

- **Streaming tokens are not visible in this world.** The workbook path answers
  deterministically over HTTP, so there are no token frames to watch. The
  general-chat path does stream, but slowly enough that partial text is easy to
  miss. Token-level streaming is verified separately, not here.
- **Answers name a saved copy, not your live workbook.** That is correct
  behaviour and will keep being correct: this world has no live file
  integrations.
- **Ambig items stay ambiguous until you choose.** Steps 2 and 4 will keep
  asking about `No. 381` and `No. 622`. Nothing is lost; a later turn can
  disambiguate.
- **The preview is a snapshot.** Work you do here does not appear in your normal
  app, and later edits to your real data will not appear here.
- **Some messages are the app being honest about a limit**, not a bug: "no
  matching row in the indexed content searched" is scoped to what was indexed,
  and a source that cannot be read is reported as unreadable rather than as an
  absence. Both are deliberate.

## 6. If something looks wrong

1. Check the backend log first:
   `tail -40 backend/data/acceptance_worlds/preview_v1/preview_backend.log`
2. If the preview is wedged, restart it (below). Nothing you do in the preview
   can affect your normal app.
3. Tell me using the template below.

### Feedback template

```
Step:        M0_            (e.g. M02, or "refresh")
What I did:  <the exact prompt, or what you clicked>
Expected:    <what you think should have happened>
Actual:      <what you saw — quote the message text if it is an answer>
Time:        <approx, with timezone>
Screenshot:  <optional — save into backend/data/acceptance_worlds/preview_v1/>
```

Do not send passwords, API keys, or tokens. If a message contains something
that looks like a credential, say so rather than pasting it.

## 7. Safe restart

Never run a destructive test, corruption injection or schema change against
your real database. This preview is already isolated; keep it that way.

```bash
cd /Users/rushiparikh/projects/atom/backend

# stop (leaves your normal :3000 / :8001 stack alone)
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py down

# start again, same world, same isolated database, same model providers
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py up

# prove it is still the isolated world and not something else on those ports
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py verify
```

`verify` must print `9/9 checks passed`. It checks the backend's process
identity, that the process has *this world's* database file open, that it is
**not** holding your live development database, and that the frontend compiled
*this* backend's address into its client bundle. If any check fails, stop and
tell me rather than testing against it.

To fold in code changes made since the last start, re-snapshot the world first:

```bash
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py down
venv314/bin/python scripts/orchestration_acceptance/run_isolated.py \
  --name preview_v1 --port 8051 --cases true_eight --samples 1 --lifecycle \
  --snapshot-working-tree --rebuild-world --refreeze-db
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py up
```

Note that a re-snapshot creates a **new** isolated database, so conversations
from the previous run are not carried over. That is expected.

## 8. Current verified state, in one place

- Real model turn in a browser: **yes** (`opencode-go`, `kimi-k2.7-code`).
- Isolation proven from browser network traffic: **yes** — every request went to
  the preview frontend and the preview backend, and to no other local port.
- Restart durability, including byte-identical retry-pin survival: **11/11
  checks passed**.
- Workbook eight-item lookup, scored against the frozen acceptance
  expectations: **8/8 targets pass**.
- The full 12-case acceptance matrix, and every remaining gap, are itemised in
  `CHAT_ORCHESTRATOR_READINESS_REPORT.md`. Read that before treating any single
  behaviour as certified.
