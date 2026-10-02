# Manual test quickstart — Atom isolated preview

> **SUPERSEDED for the live preview.** The `:3091` preview this file describes is
> stopped. The current preview, its fingerprint, and what is verified on it are in
> `acceptance/lane3/PREVIEW_STATUS.md`. Its how-to-use guide is
> `acceptance/lane3/PREVIEW_QUICKSTART_CANDIDATE.md` (**http://localhost:3102/chat**).
> Everything below is kept as the historical record of the `:3091` run, including
> the `PREVIEW-01` lookup defect that is closed on the current candidate.

**The app is running now.** Open **http://localhost:3091**

| | |
|---|---|
| Frontend | http://localhost:3091 |
| Backend API | http://127.0.0.1:8091 |
| Sign in | `admin@example.com` / `preview-only-local-2026` |
| Model | a **real** local model — `llama3.1:8b` via Ollama. The UI badge reads `o4-mini`; that is an alias pointing at the same weights (see *Model identity* below). |
| Your own environment | **untouched.** The live backend on `:8001` and the frontend on `:3000` are still running and were not restarted or modified. |
| Evidence | `preview_verification.json`, `screenshots/` |

This is a disposable isolated world. Nothing you do here touches your real
Atom data, and it is safe to break.

---

## First, the honest status

| | |
|---|---|
| Browser flows verified | **11 pass, 0 fail, 1 cosmetic block** (`preview_verify.py`, real Chromium) |
| Real model answering in the browser | **yes** — verified, transcript quoted below |
| **FUNCTIONAL BLOCKER — named-file lookup returns a value** | **`PREVIEW-01`. Root cause traced; NOT fixed. The advertised M02 flow does not work.** |
| Cosmetic block (separate, minor) | the page `<title>` is empty. No effect on any answer or evidence. |

**Two different things — do not conflate them.** `PREVIEW-01` is a **functional
blocker**: the core read workflow is broken and is the current priority. The
empty page title is cosmetic and blocks nothing.

So: **normal chat, formatting, re-search and reload are working and worth
trying. The seeded-workbook price lookup is broken, and M02 stays off the
supported list until it is fixed and re-verified here.** Everything else in this
document is verified; that one is named as broken rather than quietly included.

---

## Try these six prompts

Copy them exactly. Each was run before publishing; the "expected" column is what
was actually observed, not what should happen.

### M01 — normal question *(verified)*

> In one sentence: what is a bandsaw used for?

**Expected:** a real model answer in a few seconds. Observed verbatim:
> "A bandsaw is typically used for curved cuts or resawing in woodworking, as
> well as cutting metal pipes and profiles in metalworking."

### M02 — the seeded workbook lookup *(KNOWN BROKEN — `PREVIEW-01`)*

> In Consolidated Price List 2019.xlsx, what is the list price for U-22 and SLE24-16?

**Expected today:** *"U-22 - no matching row in the indexed content searched"*
and the same for SLE24-16, followed by an honest provenance line naming the
saved copy, its date, 46 indexed sheets, and stating this is **not** an absence
claim about the live workbook.

**Why that is a defect and not correct behaviour:** the row exists. The
world's `..._linmac.parquet` contains `Part Number = U-22`, `List Price = 1777.0`,
`__sheet_row = 26` (i.e. `linmac!A26`).

**Root cause (traced, not fixed).** Asked **first** in a fresh session, the same
request works and returns the exact binding: *"U-22 - 1,777 (LINMAC!R26 matched
at A26, column C26 'List Price')"*. Asked **after any general-chat turn**, it
misses. So a preceding turn is the trigger — not the short form, not the amount
of data.

The scan for the failing turn recorded, in the durable trace:
`per_item: {"U-22": "matched", "SLE24-16": "matched"}`, 46 entries, no
truncation, no probe failure — and the reply said "no matching row" anyway.
**The retrieval is correct and the delivery throws the result away.** Two readers
of the same dataset disagree inside one turn: the planner's named-file scan
matched, the pending-file direct reader missed, and the *pending* result is the
one rendered and pinned. The pending file objective is reconstructed from chat
history, and that history-tainted context is what the direct read runs with.

A second, genuine defect was found and fixed along the way
(`PROBE-CACHE-01`): the dataset probe cached a **miss** for 300s, so one
transient read failure could publish "no matching row" for five minutes. It is
fixed and pinned by tests — but it is **not** the cause of `PREVIEW-01`, which
still reproduces with the fix in place.

### M03 — formatting follow-up *(verified)*

> Make that a table please

**Expected:** a new, reformatted answer. The previous answer stays in the
transcript unchanged. No new retrieval is performed for a formatting request.

### M04 — explicit re-search *(verified)*

> search again for U-22

**Expected:** a new read attempt and a fresh answer, not a replay of the cached
one. (It will hit the same `PREVIEW-01` miss, since the underlying lookup is
unchanged.)

### M05 — unrelated question, then resume

> What is 2 + 2?
>
> …then: *back to the price list*

**Expected:** the unrelated question does not disturb the price-list task, and
resuming returns to it. *Not yet verified in the browser — treat as a probe, and
tell me if it misbehaves.*

### M06 — refresh *(verified)*

Press refresh, or reopen http://localhost:3091/chat.

**Expected:** the conversation and its evidence association survive. Verified:
identifiers still present after reload.

---

## Supported right now

| Workflow | Status |
|---|---|
| Sign in, navigate the app | working |
| Normal chat with a real model | working (slow first turn — see below) |
| Conversation continuation: formatting, re-search | working |
| History and reload | working |
| WebSocket status updates | working, but see the correction below — this is **not** streaming |
| Cross-source retrieval, ambiguity, absence bounding | partially — the *framing* is correct, the value resolution is `PREVIEW-01` |
| Canvas editing, authorized mutations | **not verified — do not test** |
| Sandboxed outbound send | **not verified — do not test** |
| Live connectors (mail, WorkDrive) | **excluded.** The world is network-isolated by design |

## Correction: WebSockets are not streaming

An earlier version of this document said "11 WebSockets — working". That was a
**connection count** and it was not evidence of anything. Measured properly:

- 6 app sockets opened (2 at t=5.5s, 4 at t=8.5s); **two of the first batch were
  closed by t=7.2s**. That is churn, not one healthy link.
- 6 messages arrived, all `agent_status_change` (running → success).
- **0 token events.**

So the socket carries status transitions only; **the answer arrives whole in the
HTTP response.** Token streaming is *unexercised*, not proven. Matches the prior
lifecycle session's finding on the same rig.

## Limitations you should know before you start

1. **First turn after a launch is slow** — 50–95s observed. Ollama pays a model
   load and the app has a per-turn time budget; a cold first turn can hit it and
   answer *"This turn ran past its time budget."* Later turns are 5–30s. If the
   very first message fails this way, send it again.
2. **The model is an 8B local model.** It is a real model doing real inference,
   but it is not a frontier model — expect weaker reasoning than a cloud model.
   This is a preview of the *pipeline*, not of answer quality.
3. **The UI model badge says `o4-mini`.** It is an Ollama alias for
   `llama3.1:8b`; the router selects that route name and the alias resolves to
   the real local weights. No cloud provider is reachable from this world.
4. **The preview password is disposable** and only valid in this world.
5. **Nothing here is a claim of chat-orchestrator readiness.** This is the
   manual-test preview milestone: a running app with a verified subset of
   flows, not a completed system.

---

## Safe restart / stop

The preview owns its own ports and its own world. To stop it:

```bash
cd docs/architecture/orchestration_migration/acceptance/preview
../../../../backend/venv314/bin/python preview_launch.py --stop
```

To bring it back (rebuilds the world, so the DB resets to the fixture):

```bash
../../../../backend/venv314/bin/python preview_launch.py \
    --port 8091 --frontend-port 3091 --name search_preview
```

To re-run the browser verification:

```bash
../../../../backend/venv314/bin/python preview_login.py     # sets the preview password
../../../../backend/venv314/bin/python preview_verify.py     # 11 checks + screenshots
```

**Never** restart or reconfigure your usual backend on `:8001` to make the
preview work. It does not need it, and the plan explicitly forbids it.

Logs:

* backend — `backend/data/acceptance_worlds/search_preview/preview_backend.log`
* frontend — `backend/data/acceptance_worlds/search_preview/preview_frontend.log`

---

## Feedback

Tell me: the step (M0x), what you expected, what actually happened, and roughly
when. A screenshot helps. I correlate it back to the execution logs — you do not
need to inspect anything yourself, and please don't run crash or corruption
tests by hand; those are agent-operated.

## Two defects found while building this, worth knowing

* **`PREVIEW-01`** — named-file lookup misses a row that exists (above).
* **Harness gap (not a product defect):** the acceptance credential scrub
  covers 15 database tables but not the BYOK **key file**, so a world built by
  `build_world` inherits `byok_keys.json` from the developer's data directory.
  In this world that file was empty, so no real key was present or usable — but
  the scrub should cover it, and it should be checked before any world is
  published. Not fixed here; flagged.
