# M3 canonical delivery — repair proof (2026-11-17)

Branch `codex/m3-canonical-delivery-20261117`, base `ecce2df80`.
Source changed: `backend/integrations/chat_orchestrator.py` (M3 delivery
boundaries only). New public-boundary tests:
`backend/tests/test_m3_canonical_delivery_contract.py`.

## What the earlier audit missed

The prior read-only audit concluded "M3 sanitizes the WS close only". The
independent trace showed that was **overstated**:

- On a 6-case M3=1 streaming matrix, `FakeLLM.stream_completion` ran
  exactly once per case and `_m3_reconcile_stream_done` ran **zero**
  times.
- The cause is the `_stream_done_validation.valid` branch of
  `_get_qwen_response`: an ordinary valid payload assigned the raw
  `_streamed` buffer to `chat_token_done` and every later carrier.
  `_m3_reconcile_stream_done` was only reached when final-text validation
  **failed**.
- Carrier divergence followed: the raw stream buffer also fed
  `response_data["content"]`, the HTTP `message`, and the durable
  `ChatMessage` assistant row.
- A later post-stream guard regeneration could replace the text again,
  with no M3 pass at all (reproduced while validating the first repair:
  the "generic non-answer" guard regenerated an unsupported send after
  the close).

## Repair (reuse, no new grammar)

One canonical text boundary, `_m3_canonical_delivery_text`, reuses:

1. the existing legacy guard/receipt renderer `_canvas_claim_correction`;
2. the existing M3 pre-delivery workflow strip (same `_M3_WORKFLOW_CLAIM_RE`,
   same whitespace normalization).

`_m3_reconcile_stream_done` is now a thin compatibility wrapper over it.

- **Streaming valid payload:** the canonical text is produced at the close
  and assigned to `chat_token_done`, `response_data["content"]`, and
  therefore the HTTP response and durable row. The raw buffer is not
  reintroduced by a truthiness fallback.
- **Non-streaming M3=1:** the same boundary runs after the legacy
  correction in the shared delivery tail.
- **Post-stream replacement:** the exact canonical text is remembered; if a
  later guard replaces or appends text, the boundary runs again. An
  append-only deterministic suffix is not given a second Operation-status
  section (idempotent re-entry).
- **Incremental withholding unchanged:** `_m3_gate_stream_chunk` still
  holds unverified claims mid-stream, and the final canonical text strips
  the same claims at close. This is NOT a guarantee that every claim was
  invisible during streaming: a frozen legacy claim split across
  already-released chunks can already have reached the live bubble before
  the close (the gate only inspects its current unreleased window). The
  repair's guarantee is the FINAL carriers — WS close, HTTP and durable —
  never reintroduce such a claim when the receipt read is unavailable.
- **Fail closed:** a guard fault with a non-empty withheld span or a
  claim-shaped reply returns a non-empty honest notice that neither claims
  a send/write nor says "nothing happened". **An EMPTY withheld span does
  not disable the claim-shape check**: the incremental gate only sees its
  current window, so a claim split across already-released chunks can
  leave `withheld == ""` while the full raw buffer still carries a frozen
  claim (root counter, 2026-11-17). Empty/`None` stay empty and a benign
  reply with no claim shape is delivered unchanged.

No vocabulary/regex expansion, no new intent classifier, no email-provider
special case, no extra LLM call, no flag flip. `CHAT_FINALIZATION_M3`
remains default OFF.

## Control proof (actual public boundary)

`backend/tests/test_m3_canonical_delivery_contract.py` drives the real
`POST /api/chat/message` router with a real signed JWT validated by
`core.auth.get_current_user`, the real `process_chat_message` →
`_get_qwen_response` reply leg, the real WebSocket `chat_token` /
`chat_token_done` frames, and a fresh read of the durable `ChatMessage`
assistant row. Only the external model outputs, memory assembly, planner,
and WS transport are doubled. No email is sent and no receipt is
fabricated as a legitimate send.

Covered:

- M3=1 streaming ordinary valid payload with an unsupported send: the
  read-only summary survives and WS close == HTTP == durable;
- only the unsupported claim: a non-empty honest `Unverified` notice;
- mixed verified canvas receipt + unsupported send: the send is removed and
  exactly one verified section survives on all three sinks;
- benign read-only reply byte-unchanged;
- M3 OFF legacy control (unsupported send survives; one stream call, no
  fallback generation);
- non-streaming M3=1 same contract, one generation, full message list;
- structured payload delivered unchanged;
- protocol-rejected stream does not deliver its raw text;
- guard fault fails closed with the honest delivery notice;
- **guard fault with explicit empty / whitespace / `None` / non-empty
  withheld controls** (the empty and whitespace cases are the root counter);
- **public stream fault control**: a frozen claim split so the close sees
  `withheld == ""` while the raw buffer still carries it, then an
  unavailable receipt read — WS close, HTTP and durable all carry the
  truthful unverified notice, never the raw claim;
- non-canvas turn untouched;
- empty/`None`/no-op semantics preserved.

Commands run (backend dir, cached venv, `TESTING=1`,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`):

```
python -m pytest -q tests/test_m3_canonical_delivery_contract.py
  -> 22 passed

python -m pytest -q \
  tests/test_m3_canonical_delivery_contract.py \
  tests/test_finalization_m3.py tests/test_finalization_m1.py \
  tests/test_finalization_m2.py tests/test_chat_finalization_seam.py \
  tests/test_f6_orchestrator_delivery.py \
  "tests/test_pending_file_task_resume.py::TestCanvasTruthGate"
  -> 110 passed, 2 xfailed
```

The two xfails are the pre-existing strict-XFAIL safety checks in
`TestCanvasTruthGate` against the frozen default helper — deliberately
**not promoted**: `_canvas_claim_correction` is unchanged, and the larger
unified-finalizer gap remains open.

A broader three-file run (`test_l2_guard_order.py`,
`test_r90_stream_empty_and_turn_deadline.py`,
`test_workbook_structured_delivery.py`) shows 1 failure
(`test_empty_stream_records_provider_failure`) in combined order. A paired
baseline with this change stashed fails identically — it is a pre-existing
cross-file order failure, not a regression from this work.

Paired baselines for the contract file (test file kept, only the source
under test stashed):

- original repair baseline (before `fec3411fa`, 12 tests): **8 failed,
  4 passed** — the leaking claim cases fail, only the intended controls
  (M3 OFF, benign, non-canvas, structured) pass;
- follow-up baseline (the empty-withheld fix reverted, 22 tests): **3
  failed, 19 passed** — exactly `withheld=""`, `withheld="   "` and the
  public empty-span stream fault control fail. With the fix: **22
  passed**.

The tests therefore reproduce the defects, not just the fixes.

## Limits (recorded, not hidden)

- M3 remains a **limited-vocabulary** pre-delivery boundary, not a
  whole-app semantic proof. Prose that the frozen legacy matcher and the
  M3 workflow matcher do not know is still not validated here.
- Only canvas-bound turns have an operation record to validate against;
  non-canvas turns are untouched by design.
- The protocol-rejection path and its legacy empty close content are
  intentionally unchanged.
- In these synthetic turns `success=False / outcome=unconfirmed` is the
  existing durable-outcome resolver behavior (the benign twin has it too);
  it is not a claim-specific error and says nothing about normal model
  quality.
- If validation itself faults, a benign sentence that happens to match a
  frozen claim shape is replaced by the honest notice (fail-closed
  trade-off; normal operation is unaffected).
- The incremental M3 gate can still release a frozen legacy claim that is
  split across already-released chunks (it only inspects the current
  unreleased window). That pre-existing mid-stream limitation is unchanged
  by this repair; the final close/HTTP/durable boundary now refuses to
  reintroduce such a claim when the receipt read is unavailable.

## Addendum 2026-11-17 — empty-withheld follow-up (root counter)

The root counter showed that `_m3_canonical_delivery_text(..., withheld="")`
returned the raw claim unchanged when `_canvas_claim_correction` raised,
because the fault predicate was:

```
withheld_unreleased OR (withheld is None AND claim_shape)
```

so an explicit empty string disabled the frozen-claim-shape check. Empty
`withheld` means **no currently unreleased span**, not that the whole raw
buffer was validated (the incremental gate sees only its window). The
predicate is now:

```
withheld_unreleased OR claim_shape(text)
```

The withheld span is additive evidence; it never gates the shape check.
Benign direct text (no claim shape), M3 OFF, normal non-canvas, structured,
protocol and rejection semantics are unchanged. Permanent regressions:
`None`, `""`, `"   "` and non-empty withheld controls plus a public stream
fault control that proves the close received `withheld == ""` via a spy and
that WS close / HTTP / durable carry only the truthful notice.

## CI selection (2026-11-17)

The whole contract file now runs unconditionally in the existing hosted
`backend-core-extra` lane (the isolated-DB core lane), not a parallel
workflow:

- step: **Run M3 canonical chat delivery contract controls**
  (`.github/workflows/ci.yml`, appended after the document-lineage step);
- env: `TESTING=1`, runner-temp absolute scratch `DATABASE_URL`,
  `ATOM_DATA_DIR`, `LANCEDB_URI`, `HF_HUB_OFFLINE=1`,
  `TRANSFORMERS_OFFLINE=1`, `PYTHON_DOTENV_DISABLED=1`;
- selector: `tests/test_m3_canonical_delivery_contract.py` (whole file,
  no `-k`, no skip, no marker filter);
- ledgers updated to match the existing CI partition mechanism:
  `backend/tests/fixtures/ci_backend_additions.json` (step definition) and
  `backend/tests/fixtures/ci_backend_core_extra.json` (`step_names`).

Validation (cached venv, unique mktemp scratch DB/data/Lance, offline env):

```
pytest -q tests/test_ci_backend_lane_contract.py
  -> 628 passed

pytest -q tests/test_m3_canonical_delivery_contract.py \
  --timeout=300 --timeout-method=thread     (CI env above)
  -> 22 passed
```

Every existing selector, order and gate in the workflow is preserved; the
only workflow change is the additive step above. This proof covers the M3
canonical final-text boundary only — it is **not** a whole-app readiness
claim. Historical negatives, the default-OFF flag, and the two pre-existing
strict-XFAIL checks remain as recorded.


