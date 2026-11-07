# Credential-safe logging — malformed-record stderr fallback

Status: **submitted for independent verification.** Successor to merged
[#689](https://github.com/rush86999/atom/pull/689) for the formatter-failure
path that #689 did not cover. No merge or deployment was performed.

## Confirmed defect

`LogRedactionFilter.filter` caught a `record.getMessage()` failure and returned
`True` with the original `msg`/`args` unchanged. `StreamHandler.format` then
failed on the same record, and `logging.Handler.handleError` wrote the original
`Message` and `Arguments` to stderr whenever `logging.raiseExceptions` was true
(the ordinary development/debug setting). A session-bearing request target in
`args` therefore escaped the centralized redaction through logging's own
fallback diagnostic.

This does not relabel the prior accepted WebSocket handshake redaction as
failed: normal records remain redacted. The gap is specifically the
malformed-record formatter fallback.

## Repair

- On `record.getMessage()` failure, `LogRedactionFilter` freezes the record to a
  context-only line containing the logger, level, source path, call stage,
  line, message type, argument shape/length and exception **type**.
- The original format string, arguments, `exc_info` and `exc_text` are cleared
  before any downstream handler or `handleError` diagnostic can render them.
- The frozen record is marked, so additional handlers reuse the same safe line.
- A failure inside redaction itself also freezes a generic safe line instead of
  passing the original record through.
- The repair does **not** set `logging.raiseExceptions = False`, swallow valid
  records, disable access logs, weaken authentication transport, or add a new
  logging engine.
- Normal `redact_log_text` behavior and the uvicorn accepted/rejected
  path/status twins are preserved.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-log-stderr-redaction-20261106` |
| Base main | `213e75c436044634df2a0c2e7a88faf6d03c5797` |
| Executed source | `bd4d8f253f3ab38c64d8945b2fddb0cfcd3a67f2` |
| Runtime | local logging/uvicorn scratch; runtime-generated synthetic secret; no live token/provider |

## Verification

| Gate | Base `213e75c43` | Fixed `bd4d8f253` |
|---|---|---|
| Supplied probe, 3.14 | **1 failed, 1 passed** | **2 passed** |
| Supplied probe, 3.11 | **1 failed, 1 passed** | **2 passed** |
| Focused logging selection, 3.14 | — | **151 passed** |
| Focused logging selection, 3.11 | — | **151 passed** |
| Formatter probe, 3.14 | stderr leaked: **true** | stderr leaked: **false** |
| Formatter probe, 3.11 | stderr leaked: **true** | stderr leaked: **false** |

The formatter probe reports the escaped boolean only, never the synthetic
value. On the fixed tree the fallback diagnostic is **0 bytes**, while the
normal stream keeps both `WebSocket /ws?token=<redacted> [accepted]` and
`WebSocket /ws/reject?token=<redacted> 403`.

The uvicorn handshake twin (base and fixed, already containing #689's normal
redaction) has **0 raw synthetic values**, **3 `<redacted>` markers**, 2
WebSocket lines, and both accepted/`403` statuses preserved. This confirms the
repair does not regress normal operation.

The broader logging/audit selection is **346 passed, 1 failed** on both 3.14
and 3.11. The one failure,
`tests/core/test_logging_config_coverage.py::TestLibraryLoggerConfiguration::test_configure_library_loggers`,
is pre-existing: it asserts uvicorn `WARNING` while the merged design
deliberately keeps the operator-selected uvicorn level (`assert 0 >= 30`,
logger INFO). The same test fails alone on exact base 3.14, and the full 3.11
base selection is **343 passed, 1 failed** with the same identity. It is not
claimed as repaired.

## Evidence controls

- `verifier_probe.py` is the supplied independent probe; synthetic secret is
  generated at runtime.
- `formatter_fallback_probe.py` prints only booleans/constants.
- `supplied-base-*.log` and `formatter-probe-base-*.txt` are baseline failure
  records; no raw credential is present.
- `server-base-sanitized.log` replaces the synthetic value with
  `<synthetic-jwt>`; the raw baseline log was not uploaded.
- All fixed logs are from the exact executed source.

## Boundaries

- Runtime-generated synthetic credentials only; no live token, revocation,
  rotation or production exposure claim.
- Local logging/uvicorn scratch, not production log-pipeline qualification.
- Malformed records are covered when a `LogRedactionFilter` is installed on the
  logger/handler path (the centralized installation). Handlers configured
  outside that path remain outside this boundary.
- No merge or deployment; independent verification and code-owner review
  remain required.
