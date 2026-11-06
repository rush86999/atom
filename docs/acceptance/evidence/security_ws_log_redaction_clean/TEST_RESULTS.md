# WebSocket log redaction — test results

Executed source: `b4bcd2a97b71c96f155e771e297102f9642276b2`  
Base main: `3925cf3592e955bebb8282ec7168e3fdce20ec42`

## Focused logging/security gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_log_redaction_jwt.py \
  tests/test_covpush_w79_logging.py \
  tests/test_covpush_w86_structured_logger.py \
  tests/test_logging_security_bugs.py \
  tests/test_logging_security_fixes.py \
  tests/test_covpush_w64f_secrets_redactor.py \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **145 passed** | `focused-314.log` |
| Python 3.11 | **145 passed** | `focused-311.log` |

## Server-level scratch

A minimal FastAPI app calls the real `setup_logging(level="INFO",
format_type="json")` and serves an accepted `/ws` plus a rejected `/ws/reject`.
A synthetic JWT (non-functional; digest retained in `verification.json`) is
placed in `?token=` and `?api_key=` on both handshakes. Uvicorn runs at
`--log-level info`; stdout/stderr is captured.

| Tree | Result | Artifact |
|---|---|---|
| Base `3925cf359` | **3 raw synthetic occurrences / 2 WebSocket lines** | `server-base-sanitized.log` |
| Fixed `725a81961` | **0 raw occurrences; 2 redacted WebSocket lines** | `server-fixed.log` |

Fixed lines preserve observability:

```
WebSocket /ws?token=<redacted>&api_key=<redacted>&x=1 [accepted]
WebSocket /ws/reject?token=<redacted>&x=1 403
```

The baseline log is sanitized before commit; no raw synthetic value is in the
evidence. The probe source and runner are included for reproduction.

## Unit coverage

- ordinary query/path preservation;
- repeated and percent-encoded sensitive query keys;
- encoded/repeated sensitive values;
- `Authorization: Bearer`, standalone `Bearer`, structured JSON assignment;
- uvicorn logger with preformatted `%s` args;
- `setup_logging` accepts the application's `format_type` keyword.

## Notes

- No live token, credential rotation/revocation, provider or production action.
- No authentication transport or session semantics changed.
