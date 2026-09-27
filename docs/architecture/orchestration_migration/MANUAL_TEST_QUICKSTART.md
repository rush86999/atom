# Manual test quickstart — Atom isolated preview

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
| **Named-file lookup returns a value** | **NO — open defect `PREVIEW-01`.** It answers honestly but returns no row. Do not expect prices. Details below. |

So: **normal chat, formatting, re-search and reload are working and worth
trying. The seeded-workbook price lookup is not.** Everything else in this
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
`__sheet_row = 26` (i.e. `linmac!A26`). The framing around the miss is exactly
what the search work order asked for; the retrieval is what fails.

**Not caused by the recent search work.** That work changed the hybrid coverage
envelope, query decomposition and the reranker loader. The dataset probe path
(`_resolve_active_items` → `_probe_cached` → `search_all_datasets_sync`) was not
touched.

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
| WebSocket live updates | working (11 app sockets observed on the isolated backend) |
| Cross-source retrieval, ambiguity, absence bounding | partially — the *framing* is correct, the value resolution is `PREVIEW-01` |
| Canvas editing, authorized mutations | **not verified — do not test** |
| Sandboxed outbound send | **not verified — do not test** |
| Live connectors (mail, WorkDrive) | **excluded.** The world is network-isolated by design |

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
