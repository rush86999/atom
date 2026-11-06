# Agent 3 independent review — #689 credential-safe log redaction

Reviewer: Agent 3 (independent verification), 2026-11-06, per
`VERIFIER_AGENT3_WORKFLOW_JOIN_AND_NEXT_READY_20261106.md`. Submitted #688
was CLOSED unmerged (head `74a2804598…`); the changed remote head resolved:
the content was re-submitted and owner-merged as **#689** (`66e09c5ee`,
"Security: redact JWTs from WebSocket and request logs"), now on main. This
review covers the merged content on main, reconciled against the frozen #688
head. Recommendation to the lead; owner review/merge authority separate.

## 1. User contract reviewed

A real user's session credential arriving in a request target
(`?token=<jwt>` on WebSocket handshakes, query params, Bearer headers) must
never appear in retained logs — while path, status, operation and ordinary
non-sensitive query parameters stay observable, and access logging is not
disabled wholesale.

## 2. Source identity and the #688→#689 delta

- All 4 code files (`core/log_redaction.py`, `core/logging_config.py`,
  `tests/test_covpush_w79_logging.py`, `tests/test_log_redaction_jwt.py`)
  hash-identical across #688 head, #689 merge and main — **except**
  `tests/test_log_redaction_jwt.py`, which changed between #688 and #689.
- That delta is the GitGuardian remediation: #688 committed a
  **credential-shaped JWT literal** (synthetic content, but a scanner cannot
  know that); #689 generates the synthetic token at runtime
  (`secrets.token_urlsafe`), so **zero credential-shaped literals are
  committed** anywhere in the new tree or its evidence bundle (scanned: 0
  matches in all 13 bundle files). Runtime generation also strengthens the
  tests: redaction must catch any JWT shape, not a fixed magic value.
- Clean evidence bundle `security_ws_log_redaction_clean/`: executed source
  `b4bcd2a97…` (branch `…-clean-20261106`, base `ace04c8b9`); all 6 declared
  source files hash-match at that executed source **and** at main
  (`ci.yml` included); **all 12 artifacts hash-verified at main**. Bundle
  complete and checkout-verifiable.

## 3. GitGuardian finding — provenance status (no suspect strings quoted)

The flagged commit `c83cebeb3` belongs to the closed #688 branch and **is
still reachable at `origin/codex/oracle01-jwt-log-redaction-20261106`** —
so ref-scans will keep failing until Agent 2's remediation removes that
surface (branch deletion is the safe, history-preserving move; rewrite and
credential rotation are explicitly out of my scope and yours to direct).
Current main contains **no** credential-shaped literal (verified by
structural scan), and the flagged content is remediated in the merged
artifact. The finding is a delivery/provenance issue on a stale ref, not a
defect in #689's code.

## 4. Code trace

- `core/log_redaction.py`: query-pair redaction with sensitive-key set
  (token/jwt/api_key/secret/password/authorization/…), keys percent-decoded
  and dash/underscore-normalized before matching; repeated params handled;
  Authorization/Bearer headers and structured `key: value` assignments
  redacted; `redact_log_text` never raises (falls back to original text).
- `LogRedactionFilter` mutates `record.msg`/clears `args` **before handlers
  format**, never drops a record, and swallows formatting failures.
- `logging_config.py`: `setup_logging()` calls `install_log_redaction()` —
  filter attached at **logger and handler level** to root, `uvicorn`,
  `uvicorn.error`, `uvicorn.access`, both WS impl loggers and `websockets`,
  idempotently. Crucially the previous uvicorn→WARNING suppression was
  **removed**: access lines stay observable and redacted instead of
  suppressed (the work order's "do not merely disable access logs").
  Logger-level filters survive later handler replacement by
  `uvicorn.run` — proven empirically below.

## 5. Independent execution (Python 3.11.16, Node n/a, fresh `TESTING=1` scratch)

- **Decisive packet, once**: `tests/test_covpush_w79_logging.py` +
  `tests/test_log_redaction_jwt.py` — **48 passed / 0 failed** in 17.55s
  (log: `focused-loggate-311.log`). The manifest's "145 passed" focused
  claim is the author's broader selection (committed log hash-verified);
  the committed focused log backs it, and my packet covers both changed
  test files completely.
- **Server-level reproduction, independently rerun** (owned runner adapted
  from the committed `probe_runner.py`; real uvicorn, real WebSocket
  handshakes, runtime-generated synthetic token, only booleans/digests
  printed):
  - BASE `3925cf359` (pre-repair): `raw_synthetic_present=True`,
    0 `<redacted>` markers, 3 raw occurrences across the accepted and
    rejected (403) handshake lines — defect reproduced, matching the
    manifest's `server_base_raw_synthetic: 3`.
  - FIXED `66e09c5ee`: `raw_synthetic_present=False`, 3 `<redacted>`
    markers, both lines preserved with **path and status intact**
    (`/ws?token=<redacted>&api_key=<redacted>&x=1 [accepted]`;
    `/ws/reject?token=<redacted>&x=1 403`) — matching
    `server_fixed_raw_synthetic: 0` and
    `websocket_path_and_status_preserved: true`.
- **Agent 3 probes (genuinely missing)**: (1) a record whose `getMessage()`
  raises is never dropped and never raises through the logging call path;
  (2) the encoding boundary pinned truthfully — single-encoded sensitive
  keys (`%74oken=`) are redacted; a double-encoded key is not, and cannot
  carry a real credential (a server decoding once sees the same
  non-credential key); (3) semicolon-separated sensitive pairs are redacted
  like `&` pairs.
- **Combined decisive gate, once**: packet + probes — **51 passed /
  0 failed** in 17.52s (log: `combined-loggate-311.log`).

## 6. Exclusions (recorded, not certified)

- Local uvicorn scratch reproduction only — production log-pipeline
  aggregation, rotation and retention are not qualified; no live
  credential/revocation/rotation action (explicitly out of scope).
- Log producers outside the covered logger set (e.g., bare `print()` or
  module-local handlers attached after installation to loggers outside the
  tuple) are not covered by this filter; the app's centralized config keeps
  handlers at root, which the handler-level filter covers.
- The opaque `synthetic_token_sha256` in the manifest is the digest of the
  author's runtime token; my rerun generated its own token and verified by
  direct content absence, not by the author's digest.

## 7. Recommendation to the lead

**Accept #689's merged credential-safe log redaction at its tested scope**:
the defect reproduced at the real server boundary on the pre-repair base,
the repair removes the raw credential from that exact output while keeping
path/status/operation observable, the decisive packet reproduces, and the
GitGuardian remediation is correct in the merged artifact. Remaining items
for other lanes: Agent 2's provenance remediation of the still-reachable
flagged commit on the closed #688 branch (branch deletion, no history
rewrite needed on main — main is clean), and the CI worker's check status.

---

## 10. Correction (2026-11-06, lead review of my probes) — stderr
diagnostic was unobserved

**Truthful failure reported.** My §5 malformed-record probe checked only
the normal StringIO handler output; the standard logging fallback
diagnostic goes to **stderr** and was unobserved. The lead's reproduced
path: `LogRedactionFilter.filter` catches the `getMessage()` failure and
returns True with original `msg`/`args` unchanged; `Handler.format` then
fails on the same record and `logging.Handler.handleError` writes the
**original args to stderr** under the ordinary development setting
`logging.raiseExceptions=True` — a session-bearing request target in args
escapes the centralized redaction via that fallback diagnostic.

Corrected probe (committed on this branch,
`tests/test_agent3_pr689_redaction_probes.py`): captures **both** outputs
(`contextlib.redirect_stderr` for the fallback diagnostic, plus the normal
handler stream) with `raiseExceptions=True`, and asserts the credential
reaches neither. **Independent reproduction on Python 3.11.16 against
unpatched main `66e09c5ee`: 1 failed / 2 passed — the malformed-record
node fails with "credential escaped through the handleError stderr
diagnostic"**, matching the lead's Py3.14 run. This corrected test is the
executable twin for Agent 2's bounded repair (sanitize/freeze a safe
fallback record and clear secret-bearing args before downstream handlers
emit diagnostics — not `raiseExceptions=False`, not swallowing every
record, not disabling access logs).

Scope corrections to my earlier report:
- §5's "the token never reached the formatted output" was true only of the
  normal handler output and **must not be read as a complete security
  guarantee** — the malformed-formatter path leaked to stderr.
- The §5 positive handshake/rejected-handshake server evidence and the
  accepted redaction behavior are unaffected by this finding and remain
  valid (the lead confirmed: prior accepted valid/rejected handshake
  redaction is not relabeled failed).
- The §5 double-encoded-key probe stands as a **declared matching
  boundary** — not proof that a value can never contain a credential.
- This corrected finding does not reopen or rewrite superseded #688 and
  requires no credential rotation; implementation ownership is Agent 2's,
  independent verification re-runs the corrected twin on the repair.
