# Manual test quickstart — isolated chat preview (world `preview_v1`)

> **Naming note.** Another agent maintains a second isolated preview on
> :3091/:8091 and owns `MANUAL_TEST_QUICKSTART.md`. This file is the quickstart
> for the *different* preview described here (world `preview_v1`, :3101/:8051).
> Both previews are real; they are not interchangeable, and the open defects
> listed in `CHAT_ORCHESTRATOR_READINESS_REPORT.md` belong to this one.

**Status: preview ready to test now.** This is the *manual-test preview*
milestone, not a claim that every workflow is finished. Read §5 before drawing a
conclusion from a failure.

---

## 1. Where to open the app

| | |
|---|---|
| **Open this** | **http://localhost:3101** |
| Backend API | http://127.0.0.1:8051 (you do not need to open this) |
| Isolated world | `preview_v1`, run `run-65fdffe7d20c` |
| Isolated database | `backend/data/acceptance_worlds/preview_v1/runs/run-65fdffe7d20c/data/atom.db` |
| Backend log | `backend/data/acceptance_worlds/preview_v1/preview_backend.log` |
| Frontend log | `backend/data/acceptance_worlds/preview_v1/preview_frontend.log` |
| Model | a **real** model: `opencode-go` serving `kimi-k2.7-code` |

**This is separate from your usual app.** Your stack (frontend :3000, backend
:8001) is untouched and still running. Another agent's preview also runs
independently on :3091/:8091.

## 2. Signing in

Use **your usual email and password** (`admin@example.com` and whatever you
normally use). No credentials were created for you and none are written here.

Why your normal password works: this world is a sanitized snapshot of your own
development database, so the `admin@example.com` row — including its password
hash — is byte-identical to your real app's. That was verified by comparing the
rows, not assumed. What is *not* carried over is anything you have done since
the snapshot was taken.

## 3. What is verified working

| Workflow | Verified how |
|---|---|
| General chat — real model answer, no accidental tool run | browser + API |
| Seeded eight-item lookup — 8/8 targets, requested order, honest ambiguity, identity **and** value cells disclosed | browser + scored against the frozen expectations |
| Formatting follow-up re-renders from existing evidence, no new read | browser |
| Explicit re-search performs a genuinely new read | browser |
| Basis selection returns the requested column, and **names the available bases where it does not exist** — never a silent substitution | browser |
| Unrelated question answered without corrupting the task | browser |
| Browser reload: same answers, same evidence, no duplication | browser |
| Two concurrent turns stay bound to their own execution | acceptance matrix 3/3 |
| Retry pins survive a restart byte-for-byte | 11/11, incl. real restart |
| A corrupt source is reported as **unreadable**, never as "not found" | acceptance matrix 5/5 |

### EXCLUDED from the verified list — do not test, do not rely on

| Excluded workflow | Why it is excluded |
|---|---|
| **Replacing an item in the list** ("Replace U-22 with U-38") | **Correctness blocker.** It returns the *previous* list unchanged instead of applying the change, and on that turn the model reworded a citation the evidence had exactly right. It can therefore show you a stale list as if it were the answer to your new question. Being fixed on a separate candidate; it returns to this list only after it passes public-boundary tests. |
| Canvas editing / artifact mutation | No browser-level verification exists. Integration tests only. |
| Sandboxed outbound send (draft → authorise) | Not implemented in the preview. |
| Live email / calendar / drive / HubSpot and other connectors | Only *model* provider credentials are present, deliberately. See the credential note in §5. |
| Any claim about crash, corruption or restart injection | Automated, agent-operated. Not for you to run. |
| Multi-user or multi-host behaviour | Single local process. |


## 4. What to test — send these in order, in one conversation

Order matters: steps 3–6 only mean anything as continuations of step 2.

**1 — Normal question**
```
In one sentence, what is a price list used for?
```
Expect a relevant answer. No file created, no tool run, nothing edited.

**2 — The seeded eight-item lookup**
```
find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16
```
Expect all eight **in the order you asked**:
- `No. 381` and `No. 622` reported as **ambiguous** — several rows match, and it
  asks which one you mean. Correct, not a bug.
- `U-22` → 1,777 · `TK Manual Flanger` → 1,609 · `SLE24-16` → 8,880 ·
  `TK 1624` → 8,040 · `GSL48-16` → 14,166
- `TK Multi Wheel Gang Slitter` reported as a **candidate** matched via an
  alias, with price and provenance.
- Every found item shows sheet, row, the **identity cell** it matched in, and
  the **price cell** with its column name, e.g.
  `1,777 (LINMAC!R26, identity A26, column C26 'List Price')`
- The footer names the source as a **saved copy** with its timestamp and says
  unlisted sheets may contain more. That is not an absence claim about your
  live workbook.

**3 — Same content, easier to read**
```
Make this easier to read
```
Expect a shorter answer, and **scrolling up, the previous answer unchanged**.
This must not re-read the workbook.

**4 — Explicit re-search**
```
Search again and show the same items
```
Expect a new read to actually happen and the saved/live status restated.
Wording may differ from step 2; the **values must not**.

**5 — Choose a different basis**
```
Use the factory price instead
```
Expect the `Factory Price` values where they exist (`TK Manual Flanger` → 950,
`TK 1624` → 3,950), and for items that have no Factory Price column, expect it
to **list the bases that do exist** and ask which to use. A silent substitution
is a defect.

**6 — ~~Replace one item~~ — EXCLUDED, DO NOT RUN**
```
Replace U-22 with U-38
```
This one is a known correctness blocker: it answers with the *previous* list
rather than applying your change. Running it can show you a stale list as if it
answered the new question, which is exactly the failure mode this preview is
supposed to be free of. It is deliberately not in the test script. It comes
back only when it passes public-boundary tests.

**7 — Unrelated question, then come back**
```
What is the capital of France?
```
Expect a normal answer, and the workbook task uncorrupted. Then ask
`show the items again` and expect the same task back.

**8 — Reload the browser**
Expect the same final answers, the same evidence, no duplicated bubble.

**9 — Two turns at once**
Open a second tab on :3101 and send a question in each. Expect each reply and
stream to stay with its own turn.

## 5. Known problems and limits — read before concluding anything

- **Replacing an item is excluded from the support list** because it is a
  correctness blocker, not a cosmetic gap: the change is not applied to the
  underlying task, and a model-rewritten answer can present the stale list as
  the response. Do not run step 6. Details in the readiness report §6.1.
- **Treat model-rewritten citations with suspicion in general.** The same turn
  that failed to apply a replacement also reworded a sheet name the evidence
  had exactly right (`Tinknock!R100` vs `Tinknocker!R100`).
- **The very first lookup on a freshly restarted preview can come back empty.**
  Retrying works. Under investigation — not dismissed as a flake.
- **Canvas editing and simulated sends have no browser coverage at all.** Do not
  test them here; they are excluded from the supported list rather than claimed.
- **Email, calendar, drive, HubSpot and other connectors are unavailable by
  design.** Only *model* provider credentials were seeded; integration
  credentials deliberately were not, so those adapters are honestly unavailable.
- **No token-by-token streaming to watch** on the workbook path — it answers
  deterministically over HTTP. General chat does stream, but partial text is
  easy to miss. Token-level streaming is verified separately, not here.
- **Answers name a saved copy, not your live workbook**, and will keep doing so.
- **Single local process.** Nothing here supports any multi-host claim.

Some messages are the app being honest about a limit rather than a bug: "no
matching row in the indexed content searched" is scoped to what was indexed,
and an unreadable source is reported as unreadable rather than as an absence.

## 6. If something looks wrong

1. `tail -40 backend/data/acceptance_worlds/preview_v1/preview_backend.log`
2. Restart it (§7). Nothing you do in the preview can affect your normal app.
3. Send feedback using the template below.

```
Step:        M0_            (e.g. M02, or "reload")
What I did:  <exact prompt, or what you clicked>
Expected:    <what you think should happen>
Actual:      <what you saw — quote the message text if it is an answer>
Time:        <approx, with timezone>
Screenshot:  <optional>
```

Please do not send passwords, API keys or tokens. If a message contains
something that looks like a credential, say so rather than pasting it.

## 7. Safe restart

Never point destructive tests, corruption injection or schema changes at your
real database. This preview is already isolated; keep it that way.

```bash
cd /Users/rushiparikh/projects/atom/backend

venv314/bin/python scripts/orchestration_acceptance/preview_stack.py down
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py up
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py verify
```

`verify` must print `9/9 checks passed`. It checks the backend's process
identity, that the process has **this world's** database file open, that it is
**not** holding your live development database, and that the frontend compiled
**this** backend's address into its client bundle. If any check fails, stop and
tell me rather than testing against it.

To fold in code changes made since the last start, re-snapshot the world first:

```bash
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py down
venv314/bin/python scripts/orchestration_acceptance/run_isolated.py \
  --name preview_v1 --port 8051 --cases true_eight --samples 1 --lifecycle \
  --snapshot-working-tree --rebuild-world --refreeze-db
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py up
```

A re-snapshot creates a **new** isolated database, so earlier conversations are
not carried over. That is expected.

## 8. Verified state in one place

- Real model turn in a real browser: **yes** (`opencode-go` / `kimi-k2.7-code`).
- Isolation from browser network traffic: **yes** — every request went to this
  frontend and this backend, and to no other local port.
- Eight-item lookup vs frozen expectations: **8/8**.
- Restart durability incl. byte-identical retry-pin survival: **11/11**.
- Full acceptance matrix and every remaining gap:
  `CHAT_ORCHESTRATOR_READINESS_REPORT.md`. Read it before treating any single
  behaviour as certified.
