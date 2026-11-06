# Credential-safe logging — malformed-record stderr repair results

Executed source: `bd4d8f253f3ab38c64d8945b2fddb0cfcd3a67f2`  
Base main: `213e75c436044634df2a0c2e7a88faf6d03c5797`

Every pytest command used a fresh explicit scratch SQLite database and
`-p no:randomly`. The formatter/server probes use only the logging modules and
a runtime-generated synthetic secret.

## Supplied verifier probe

External probe:
`/private/tmp/test_verifier_log_redaction_stderr.py` (copied as
`verifier_probe.py`). Baseline was run from an exact `git archive` of
`213e75c43`:

```sh
git archive 213e75c43 backend | tar -x -C /private/tmp/log-stderr-base-full
cd /private/tmp
PYTHONPATH=/private/tmp/log-stderr-base-full/backend \
  $PY314 -m pytest -p no:randomly \
  /private/tmp/test_verifier_log_redaction_stderr.py -q --tb=short
PYTHONPATH=/private/tmp/atom-log-stderr/backend \
  $PY314 -m pytest -p no:randomly \
  /private/tmp/test_verifier_log_redaction_stderr.py -q --tb=short
```

| Tree | Python | Result | Log |
|---|---|---|---|
| Base `213e75c43` | 3.14 | **1 failed, 1 passed** | `supplied-base-314.log` |
| Fixed `bd4d8f253` | 3.14 | **2 passed** | `supplied-fixed-314.log` |
| Base `213e75c43` | 3.11 | **1 failed, 1 passed** | `supplied-base-311.log` |
| Fixed `bd4d8f253` | 3.11 | **2 passed** | `supplied-fixed-311.log` |

Baseline failure:
`test_secret_does_not_escape_either_logging_output[True]` — the synthetic
secret escaped through a logging output.

## Formatter fallback diagnostic

```sh
PYTHONPATH=<tree>/backend $PY314 -B formatter_fallback_probe.py
```

| Tree | Python | normal stream leak | stderr leak | stderr bytes | safe fallback | redacted twins |
|---|---|---|---|---|---|---|
| Base `213e75c43` | 3.14 | false | **true** | 1258 | false | 2 |
| Fixed `bd4d8f253` | 3.14 | false | **false** | **0** | true | 2 |
| Base `213e75c43` | 3.11 | false | **true** | 1304 | false | 2 |
| Fixed `bd4d8f253` | 3.11 | false | **false** | **0** | true | 2 |

Logs: `formatter-probe-base-314.txt`, `formatter-probe-fixed-314.txt`,
`formatter-probe-base-311.txt`, `formatter-probe-fixed-311.txt`. Both the
malformed format string and its argument carried the synthetic secret; the
probe prints no credential value.

## Focused logging gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_log_redaction_jwt.py \
  tests/test_agent3_pr689_redaction_probes.py \
  tests/test_covpush_w79_logging.py \
  tests/test_covpush_w86_structured_logger.py \
  tests/test_logging_security_bugs.py \
  tests/test_logging_security_fixes.py \
  tests/test_covpush_w64f_secrets_redactor.py \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **151 passed** | `focused-314.log` |
| Python 3.11 | **151 passed** | `focused-311.log` |

New controls in `tests/test_log_redaction_jwt.py`:

1. malformed record is frozen before handler diagnostics; stderr is empty and
   a following well-formed record still redacts normally;
2. direct record freeze clears `args`, `exc_info` and `exc_text` and retains
   logger/path/stage/type context;
3. centralized `install_log_redaction()` covers a malformed `uvicorn.error`
   record.

## Normal uvicorn handshake twin

The #689 scratch app was run on exact base and fixed trees with a
runtime-generated synthetic token:

| Tree | Raw synthetic | Redacted markers | WebSocket lines | Accepted / 403 |
|---|---|---|---|---|
| Base `213e75c43` (includes #689) | **0** | 3 | 2 | preserved |
| Fixed `bd4d8f253` | **0** | 3 | 2 | preserved |

Logs: `server-base-sanitized.log`, `server-base-result.txt`,
`server-fixed.log`, `server-fixed-result.txt`. The base log is sanitized.

## Broader logging/audit selection, 3.14

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_log_redaction_jwt.py \
  tests/test_agent3_pr689_redaction_probes.py \
  tests/test_covpush_w79_logging.py \
  tests/test_covpush_w86_structured_logger.py \
  tests/test_logging_security_bugs.py \
  tests/test_logging_security_fixes.py \
  tests/test_covpush_w64f_secrets_redactor.py \
  tests/core/test_logging_config_coverage.py \
  tests/test_covpush_w73a_middleware.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  -q --tb=line
```

Result: **346 passed, 1 failed** (`affected-314.log`).

Shared pre-existing failure:
`tests/core/test_logging_config_coverage.py::TestLibraryLoggerConfiguration::test_configure_library_loggers`
— `assert 0 >= 30` where `uvicorn` is INFO. The same test fails identically on
the exact base tree; the merged design intentionally preserves the
operator-selected uvicorn level instead of suppressing it.

## Notes

- Runtime-generated synthetic credentials only; no live token, revocation,
  rotation, provider or production exposure claim.
- No `logging.raiseExceptions` suppression, no access-log disable, no
  record-swallowing.
- No merge or deployment; independent verification and code-owner review
  remain required.
