# Expanded core acceptance — 2026-10-28

Status: **PASS** for the demonstrated workflows below on world
`expanded_core_final_20261028` (run `run-ca4d4d520140`). This is a bounded
acceptance campaign, not whole-app certification. Two frozen candidates were
reviewed read-only; their release-blocking findings were fixed and this
evidence was regenerated on the final repaired candidate (tested code
`65fe6e575`).

## Evidence sets

| Slice | Result | Evidence |
|---|---|---|
| Office slices (workbook, email, DOCX, PPTX) | 40/40 UI checks total; 17/17 artifact checks | `ui_slices.json`, `artifact_checks.json`, `run_stdout.text`, `downloads/` |
| Email with attachment + reply draft | Included in the 37 UI checks; envelope, attachment association, draft persistence and no-send verified | `ui_slices.json`, `downloads/` (email audit is in the world DB) |
| DOCX read / generate / correct / download | Included in the 37 UI checks; generated document has real headings, a real table and source references | `ui_slices.json`, `artifact_checks.json`, `downloads/` |
| PPTX read / generate / correct / download | Included in the 37 UI checks; slide order, table, speaker notes and sources verified | `ui_slices.json`, `artifact_checks.json`, `downloads/` |
| User-created table canvas A | 33/33 UI checks for the two canvases | `capability_ui.json`, `capability_run_stdout.text` |
| User-created table canvas B (different fields/decisions) | Same implementation; different vocabulary and policy | `capability_ui.json` |
| Representative employee job | 16/16 pre-restart; 17/17 post-restart; 19/19 artifact checks | `employee_job.json`, `employee_job_after_restart.json`, `artifact_checks_after_restart.json`, `downloads/` |

Assessment calls in the capability runs and the post-restart job reported
actual `deepseek-flash` / `deepseek`; the pre-restart job evidence stores the
certified decisions and policy revision. The verified launch configuration was
unchanged: DeepSeek-only policy, structured review on, streaming off, 180 s
turn/request deadlines, 300,000 ms client timeout.

## Source / artifact identity

- Backend world: `expanded_core_final_20261028`, run `run-0236669fffc7`
- World storage guard: passed before every rebuild
- Office files carry `source_identity` with `file_sha256` / size
- Email imports carry the EML SHA-256 and RFC Message-ID/References
- Capability receipts carry `source_version`, `manifest_revision`,
  `policy_revision`, `execution_id` and row/cell evidence
- Exported XLSX artifacts carry a Provenance sheet
- DOCX/PPTX downloads were reopened and inspected after restart

## Claim boundaries

- The workbook canvas supports the demonstrated formula subset (arithmetic,
  SUM, dependent recalculation via the `formulas` engine). Unsupported
  formulas, an unavailable engine or a failed recalc are named in
  `formula_gaps` / `recalc_status`; they are not presented as successful
  recalculation or certified totals. The acceptance workbook is small; wide/
  tall range handling and an unsupported-formula UI case are covered by unit
  tests and code, not by the 37-check UI campaign.
- Embedded images/charts in office documents and decks are not interpreted.
  This is recorded as a gap rather than assumed covered by extracted text.
- The PPTX acceptance campaign exercises body edits; a title-only edit that
  preserves body text is covered by a unit test, not the 37-check UI run.
- Email import and drafting are verified. **Sending was not performed.**
  Imported attachments are marked non-sendable as source evidence.
- The capability adapter currently supports the `table` base component.
  Unknown adapters receive no text-replace or write authority.
- One passing bounded job is not universal reliability.
- No deployment was performed.
