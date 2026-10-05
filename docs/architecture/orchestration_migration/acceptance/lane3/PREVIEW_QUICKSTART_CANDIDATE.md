# Preview quickstart — candidate (item replacement now included)

Date: 2026-09-27. Read this before opening anything.

## Where to open it

**http://localhost:3102**

That is the candidate's own frontend. It talks to **its own** backend on `:8071`
and to nothing else — the browser was watched making requests during the test
and the only origins it touched were `:3102` and `:8071`. This is proved, not
assumed: `NEXT_PUBLIC_API_URL` is baked into the client bundle at compile time,
so the harness reads the compiled chunks and fails if they name a different
backend.

| | |
|---|---|
| Frontend | http://localhost:3102 |
| Backend API | http://127.0.0.1:8071 |
| World | `candidate_fix1` (fully isolated — your dev database is never opened) |
| Login | `admin@example.com` / `preview-only-local-2026` |

The old preview is still up on **http://localhost:3101** and is deliberately left
running. It is one commit behind and does **not** have item replacement. Use
`:3102` for everything below.

## What works now — try these in order

Open http://localhost:3102/chat and send these four messages in one conversation.

**1. The seeded eight-item lookup**

> find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16

*Expect:* all eight items, in exactly that order, each with the source cells it
read. Several legitimately have more than one matching row and will say so and
ask you to confirm which one you meant — that is correct behaviour, not a bug.

**2. Replace one item**

> Replace U-22 with U-38

*Expect:* the list updates to the same eight slots with **U-38 in U-22's place**.
U-22 is gone. And U-38 is reported as:

> U-38 - no matching row in the indexed content searched

That is the honest answer. **U-38 is not in that workbook.** A tool that showed
you a price for it would be inventing one. If you ever see a number next to
U-38, that is a bug — please report it.

**3. Make it easier to read**

> Make this easier to read

*Expect:* a shorter rendering of the **revised** list. Your first two answers stay
exactly as they were — scroll up and check. No new search runs.

**4. Search again**

> Search again and show the same items

*Expect:* a fresh read returning the same revised list. Still no U-22.

**Then refresh the browser (F5).** Everything comes back identical, including
which cells each claim came from.

**5. Plain chat with a real model**

> In two sentences, what is a price list used for?

*Expect:* a real local model's answer (`llama3.1:8b`). While it works the bubble
shows a **"Reasoning Process"** line, and the finished answer replaces it. That
loading-then-complete state is the supported behaviour.

*Do not expect word-by-word streaming.* It is intermittent: the token-growth
check passed on an earlier run of this world and failed on the most recent one
(`PREVIEW_STATUS.md` §4.1). **Delivery here is HTTP, whole answer** — that path
is what the checks above cover.

## What is still excluded — please do not test these

These are honestly untested, not "probably fine":

- **Editing a canvas or any artifact.** No authorized edit has ever been
  observed working. Do not rely on it.
- **Deny / no-apply paths and concurrent requests.** Covered only by unit tests.
- **"Your machine lost power mid-answer."** The durable retry pin is proven to
  survive a full server restart (byte-identical replay, no second execution, 409
  on a changed payload), but a mid-answer crash is not tested.
- **Anything involving your real dev data.** This world is a disposable copy.

## A note on streaming, because it was broken in a quiet way

Until today this preview set `ATOM_CHAT_STREAMING=1`, but the chat code only
treats the literal string `true` as on. So the streaming code path had **never
run** in any preview, while the settings panel reported streaming as enabled.
Every "0 token frames" in the project's history was recorded as a product
observation when it was really a configuration error.

The launcher is fixed, so the streaming leg now runs at all — but it is **not
reliably visible in the UI**. It worked on an earlier run of this world (16 token
frames, then 27 progressive samples) and did not on the most recent one, where
the bubble went straight from the "Reasoning Process" line to the finished
answer. Treat the answer as arriving whole over HTTP. **The old preview on
`:3101` is still on the broken setting**, so you will always get whole answers
there. That is expected; it is the old build.

## If something goes wrong

Tell me: which step, what you expected, what you saw instead, roughly when, and
a screenshot if you have one. That is enough for me to find the exact execution.

## Restarting it safely

Do not rebuild the world — a rebuild re-exports the working tree and you lose the
exact code these results were measured against.

```bash
cd /Users/rushiparikh/projects/atom

# is it healthy?
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world candidate_fix1 verify          # expect 10/10

# restart it (same run dir, same database, same code)
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world candidate_fix1 down
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world candidate_fix1 up --reuse-run \
  backend/data/acceptance_worlds/candidate_fix1/runs/run-7325767729a0
```

If the frontend does not come up, the launch now **fails loudly** instead of
reporting a URL that does not work. That is deliberate. Re-attach it with:

```bash
backend/venv314/bin/python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world candidate_fix1 frontend-up
```

Never touch `:3000` / `:8001` — that is your own environment and nothing here
has ever restarted it.

## Where the evidence is

**`PREVIEW_STATUS.md` in this directory is the one current status document** —
read that first. This quickstart is the how-to-use-it companion.

`docs/architecture/orchestration_migration/acceptance/lane3/`

| File | What it holds |
|---|---|
| `PREVIEW_STATUS.md` | **the current state**: URL, fingerprint, what passed, what is excluded |
| `browser_live_2026_09_27/` | the current browser run — 25/26, full transcripts, screenshots, on fingerprint `…e2323daaad44` |
| `task_correction_live_2026_09_27.json` | 4/4 HTTP cases on the same fingerprint |
| `candidate_e2323daaad44/candidate_freeze.json` | the frozen code identity: 6554 files hashed, export tree digest |
| `browser_final/`, `task_correction_extended.json` | earlier runs on fingerprint `…90f75e4ad858` — history, not current |
| `restart_durability_candidate.json` | 15/15 across a real restart |
| `CASE_ACCOUNTING_C00_C26.md` | which of the 27 required cases are actually proven |
| `LANE_3_INVENTORY.md` | every preview, fingerprint and dead artifact, so nothing stale gets read as current |
