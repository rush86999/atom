# Atom core pilot package — 2026-10-28

> **Support status: CSV-only package.**
> This package certifies only the demonstrated CSV assessment/calculation/
> correction/restart loop. The expanded core (email, documents, PowerPoint,
> Excel-like canvas and one cross-material employee job) is verified in the
> successor package tagged `expanded-core-2026-10-28`; this CSV package remains
> unchanged and is not relabeled.

Recommended configuration: DeepSeek direct `deepseek-flash`, deepseek-only
provider policy, structured review on, streaming off, 180 s turn/request
deadlines, 300,000 ms client timeout.

Release identity: tag `core-release-2026-10-28`, targeting the single release
commit that contains the tested application and launch repairs. Tested app
code: `35860a7f0`.

Contents:

- `config.env.template` — complete winning configuration, no secrets
- `SUPPORTED_WORKFLOWS.md`
- `KNOWN_LIMITATIONS.md`
- `STARTUP.md`
- `BACKUP.md`
- `SMOKE.md`
- `ROLLBACK.md`
- `SOURCE_BUILD_IDENTITY.json`
- `CHECKSUMS.sha256`

This package stops at the deployment decision. It does not deploy anything.
