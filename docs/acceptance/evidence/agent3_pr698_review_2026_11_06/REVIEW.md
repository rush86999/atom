# Agent 3 independent review — PR698 malformed-record stderr fallback repair

Reviewer: Agent 3 (independent verification), 2026-11-06. PR #698
("Security: freeze malformed log records before stderr fallback disclosure",
head `7f5c546cf…`, OPEN, two commits: fix `bd4d8f253` + evidence-freeze
`7f5c546cf`) — Agent 2's bounded successor to the #689 stderr-disclosure
finding this reviewer reproduced at the lead's direction. Recommendation to
the lead; owner review/merge authority separate.

## 1. Contract reviewed

A record whose `msg`/`args` cannot be formatted must not let its credential
reach **either** logging output: the normal handler stream, or
`logging.Handler.handleError`'s stderr fallback diagnostic (which prints
`record.msg`/`record.args` — and `exc_info` — under the ordinary
development setting `logging.raiseExceptions=True`). The repair must keep
useful logger/path/stage/type context, must not set `raiseExceptions=False`,
must not swallow every record, must not disable access logs, and must
preserve normal redaction and the accepted/rejected WebSocket twins.

## 2. Identity

All 5 manifest-declared source files (`log_redaction.py`,
`test_log_redaction_jwt.py`, `logging_config.py`, `main_api_app.py`,
`ci.yml`) hash-match at the executed fix commit `bd4d8f253` **and** the PR
head `7f5c546cf`; `logging_config.py`/`main_api_app.py` unchanged from main
as claimed; the three DIFF-at-main files are exactly the PR's changes
(unmerged). **All 21 evidence artifacts hash-verified** at the PR head.
Bundle `security_log_stderr_fallback_bd4d8f2/` is complete and
checkout-verifiable.

## 3. The repair (trace)

- `_safe_fallback_message`: context-only line — logger name, level,
  pathname, funcName, line, `msg_type`, args shape (type+len), error
  **type** — deliberately excludes `msg`/`args` contents and exception
  text.
- `_freeze_safe_message`: replaces `record.msg`, clears `record.args`,
  `record.exc_info`, `record.exc_text` (handleError renders those too),
  and marks the record `_atom_log_redaction_fallback`.
- `LogRedactionFilter.filter`: frozen records pass through untouched
  (idempotent across the logger+handler dual attachment); `getMessage()`
  failure → freeze + emit; **new hardening branch** — a failure inside
  `redact_log_text` itself also freezes instead of leaving the original
  message in the record (closing the same stderr vector for a
  redaction-internal error). Normal path unchanged.
- No `raiseExceptions` toggle, no global swallow, no access-log change
  (diff touches only `log_redaction.py` + the JWT test file).

## 4. Independent execution (Python 3.11.16, fresh `TESTING=1` scratch)

**Decisive combined gate, once** — 37 w79 logging controls + 10 JWT
controls (7 original + 3 new freeze controls) + **Agent 3's corrected
twin** (3 probes) + **the lead's supplied stderr probe** (2 cases):
**56 passed / 0 failed** in 21.5s (log: `combined-stderr-gate-311.log`).

Decisive facts, independently established:

- **Agent 3's corrected twin** — which failed against unpatched main
  `66e09c5ee` with "credential escaped through the handleError stderr
  diagnostic" — **passes on the #698 head**. The leak is closed.
- The lead's supplied probe runs 2/2 (normal positive + malformed
  negative) on this runtime.
- Agent 3's other probes (encoding boundary, semicolon pairs) still pass —
  normal redaction unchanged.
- **Server-level accepted/rejected twins preserved**: my owned real-uvicorn
  runner rerun against the PR head — raw synthetic token absent, 3
  `<redacted>` markers, both handshake lines intact with path+status
  (`/ws?token=<redacted>&api_key=<redacted>&x=1 [accepted]`;
  `/ws/reject?token=<redacted>&x=1 403`).

## 5. Exclusions (recorded, not certified)

- Author's 151-control focused selection (both Pythons) and affected run
  remain author/CI evidence (committed logs hash-verified); my decisive
  run covers both changed files plus my twin and the supplied probe.
- The frozen fallback line intentionally omits the message content:
  diagnosing a malformed call uses logger/path/stage/shape — retrieving
  the original text requires reproducing the call, which is correct for a
  credential-safety boundary.
- Local scratch only; no production log-pipeline qualification, no live
  credential action.

## 6. Recommendation to the lead

**Accept #698 at its tested scope**: the reproduced stderr-disclosure path
is closed with the exact safe-fallback mechanism the repair order required,
all constraints honored (context preserved; no `raiseExceptions=False`, no
record swallowing, no access-log disabling), normal redaction and the
accepted/rejected twins preserved, and my corrected executable twin plus
the supplied probe both pass on this runtime. Non-blocking observation for
the record: the `redact_log_text`-failure freeze branch is new hardening
beyond the reported defect — reviewed and correct.
