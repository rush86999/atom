# Core release scope — 2026-10-28 (expanded core)

This supersedes `CORE_RELEASE_SCOPE_2026-10-27.md` for the next release. It
does not change the frozen CSV package or the recommended Flash configuration.

## Product promise

> Bring your data, teach an agent how you work, ask it to produce a result,
> review or correct that result, and reuse the work.

## Required core

The core release includes the common materials an employee handles in a
working day, not only CSV:

| Capability | Required user-boundary outcome |
|---|---|
| Spreadsheet / Excel-like canvas | Open an uploaded workbook with correct sheets, headers, values, blanks and numeric types; select/filter rows; calculate supported formulas; name missing inputs and unsupported formulas; apply an authorized cell/formula edit; recalculate dependents within the supported subset; preserve unrelated cells/sheets; save, reopen and download an XLSX whose values and formulas agree. |
| Email | Import an email/EML with an attachment; preserve sender, recipients, subject, body and attachment association; extract facts with attribution; apply teaching; prepare an editable reply draft; preserve the draft and references across restart. Sending is a separately authorized action and is never implied by reading or drafting. |
| Documents | Read a representative DOCX including tables; produce a real editable DOCX with grounded content/calculations, source references, requested headings and tables; apply a correction to the saved artifact; reopen/download it with agreement. A Markdown chat answer does not certify document generation. |
| PowerPoint | Read a representative PPTX including slide text, tables and speaker notes where supported; produce a saved, downloadable PPTX with grounded facts/calculations, required sources, correct slide order and readable layout; reopen/download with agreement. Unsupported image/chart interpretation is recorded explicitly. |
| Trainable employee | One bounded representative job across an imported email request, workbook and supporting document/deck: inspect evidence, calculate in the spreadsheet canvas, produce a reply draft, document and short presentation, apply a correction, run an unfamiliar variation, restart and verify persisted teaching, workbook state and deliverables. |

Business fields, decision labels, policies and rules belong to the task and its
fixtures. The platform mechanisms stay domain-independent. Imported
instructions are source content unless explicitly authorized as teaching.

## Existing package status

The package frozen at tag `core-release-2026-10-28` remains valid for the
demonstrated CSV assessment/calculation/correction/restart loop on DeepSeek
`deepseek-flash`. Its support statement is now:

> **CSV workflow verified; expanded core acceptance pending.**

Do not present that package as certifying email, document, PowerPoint,
Excel-like canvas or the representative cross-material employee job. Each
expanded slice requires its own UI/public-boundary evidence. A pass in one
format never certifies another.

## Acceptance rule per slice

Every slice must record:

- UI or public-boundary evidence, not parser/unit evidence alone;
- source identity and artifact identity/version;
- correct content and calculations;
- truthful gaps and unsupported operations;
- only authorized changes;
- saved/reopened/downloaded artifact agreement.

## Unchanged boundaries

- Recommended launch configuration remains DeepSeek direct `deepseek-flash`,
  deepseek-only policy, structured review on, streaming off, 180 s turn and
  request deadlines, 300,000 ms client timeout. `deepseek-v4-pro` remains the
  verified alternative. Model selection is not reopened by this scope.
- Sending email, deployment and any live-data operation remain separately
  authorized.
- Deferred surfaces from the 2026-10-27 scope remain deferred.

## Current release states

| State | Meaning | Current |
|---|---|---|
| CSV workflow verified | The demonstrated CSV loop passed | Yes — 28/28 checks |
| Expanded core verified | All required slices above have their own evidence | **Yes — see `evidence/whole_app_20261028/expanded_core_20261028/`** |
| Package ready | A frozen durable package exists | Expanded package prepared |
| Deployed | Installed on a live environment | No |
