# WebSocket/request log credential redaction

Status: **submitted for independent verification.** PR
[#688](https://github.com/rush86999/atom/pull/688). No merge or deployment was
performed.

## Confirmed defect

Uvicorn logs the full WebSocket request target at INFO. A session JWT supplied
as `?token=<jwt>` therefore reached routine logs. The centralized logging
setup was also being skipped because `main_api_app` passed `format_type=` to a
`setup_logging` signature that did not accept it, falling into the `TypeError`
fallback before any filter could be installed.

A bounded server scratch with synthetic credentials reproduced **three raw
synthetic JWT occurrences across two WebSocket log lines** on the base (one
`[accepted]`, one `403` rejection).

## Repair

- Added `redact_log_text` / `LogRedactionFilter` to `core/log_redaction.py` for
  `token`, `access_token`, `refresh_token`, `id_token`, `jwt`, `api_key`,
  secret/password, `Authorization`/`Bearer`, and encoded or repeated query
  parameters.
- `setup_logging` installs the filter on root, `uvicorn.error`,
  `uvicorn.access` and websocket loggers/handlers.
- `setup_logging` now accepts the existing `format_type` keyword, so the
  centralized path actually runs.
- Uvicorn request-target lines remain observable at the operator-selected
  level. Paths, `[accepted]`, `403` and non-sensitive parameters are preserved;
  the access log is not disabled.
- Unit tests cover ordinary queries, repeated/encoded sensitive keys and
  values, `Bearer`/Authorization, structured JSON text, preformatted record
  args and the uvicorn logger.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-jwt-log-redaction-20261106` |
| Base main | `3925cf3592e955bebb8282ec7168e3fdce20ec42` |
| Executed source | `725a819618c424e2b8c56dabe5619233fa7e66b3` |
| Runtime | local uvicorn scratch with synthetic credentials; no live token/provider |

## Server-level scratch result

| Tree | Raw synthetic JWT | WebSocket lines | Path/status |
|---|---|---|---|
| Base | **3 occurrences / 2 lines** | accepted + 403 | present |
| Fixed | **0** | accepted + 403 | `/ws`, `[accepted]`, `403` preserved |

The committed baseline log is sanitized (`<synthetic-jwt>`); the raw baseline
log was not uploaded. The synthetic credential digest is retained in
`verification.json`.

Fixed output examples:

```
WebSocket /ws?token=<redacted>&api_key=<redacted>&x=1 [accepted]
WebSocket /ws/reject?token=<redacted>&x=1 403
```

## Verification

| Gate | Result |
|---|---|
| Focused logging/security selection, 3.14 | **145 passed** |
| Focused logging/security selection, 3.11 | **145 passed** |
| Server scratch, fixed | **0 raw synthetic JWT**, 2 redacted lines |
| Server scratch, base | **3 raw occurrences / 2 lines** |

Selection: `test_log_redaction_jwt.py`, `test_covpush_w79_logging.py`,
`test_covpush_w86_structured_logger.py`, `test_logging_security_bugs.py`,
`test_logging_security_fixes.py`, `test_covpush_w64f_secrets_redactor.py`.

## Boundaries

- No authentication transport, credential engine, token revocation/rotation or
  live credential operation.
- No model/provider/PostgreSQL qualification.
- No merge or deployment; code-owner review remains required.
