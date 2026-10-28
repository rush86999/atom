# Atom expanded core pilot package — 2026-10-28

Recommended configuration: DeepSeek direct `deepseek-flash` for the certified
assessment/review payload, deepseek-only provider policy, structured review
on, streaming off, 180 s turn/request deadlines, 300,000 ms client timeout.
`deepseek-v4-pro` remains a verified alternative. No deployment.

## Support statement

This package supports the demonstrated:

- Excel-like workbook canvas (upload, sheets/headers/values/blanks/types,
  display filtering, supported formula recalculation, authorized cell edit,
  unrelated-cell/sheet preservation, XLSX save/reopen/download);
- email import with attachment and editable reply draft, durable source
  references, with **send separately authorized and not performed**;
- DOCX read (including tables), real DOCX generation with headings/tables/
  sources, correction, reopen/download;
- PPTX read (slide text, tables, speaker notes where present), real PPTX
  generation with slide order/tables/sources, correction, reopen/download;
- user-created table canvases using the versioned capability manifest,
  deterministic selection/calculation/edit/export and certified assessment;
- one bounded cross-material employee job with correction, unfamiliar
  variation and restart persistence.

It does **not** claim whole-app certification, universal reliability, email
sending, embedded image/chart interpretation, or adapters beyond the table
base component.

## Release identity

- Release tag: `expanded-core-2026-10-28-r2`
- Tested application code commit: recorded in `SOURCE_BUILD_IDENTITY.json`
- Supersedes `expanded-core-2026-10-28`, which was withdrawn after a read-only
  review found release blockers.
- Frontend build ID: recorded in `SOURCE_BUILD_IDENTITY.json`
- Evidence: `docs/acceptance/evidence/whole_app_20261028/expanded_core_20261028/`

## Contents

- `config.env.template` — complete winning configuration, no secrets
- `SUPPORTED_WORKFLOWS.md`
- `KNOWN_LIMITATIONS.md`
- `CAPABILITY_MANIFEST.md`
- `ADAPTER_SUPPORT.md`
- `STARTUP.md`, `BACKUP.md`, `SMOKE.md`, `ROLLBACK.md`
- `SOURCE_BUILD_IDENTITY.json`
- `SECURITY_REDACTIONS.md`
- `CHECKSUMS.sha256`
