# Artifact style rubric — 2026-10-30

This is the declared rubric for subjective formatting/style claims. A saved
artifact is not certified as "styled correctly" merely because its schema
validates or its text extracts. Each criterion below is checked against the
saved bytes and, for layout-sensitive criteria, a representative rendered
view.

## Document (DOCX)

| Criterion | Pass condition | Evidence |
|---|---|---|
| Heading order | Taught `heading_order` appears in the saved document in that order; missing required sections are reported | `test_word_renderer_applies_heading_table_and_font_spec` |
| Typography | Taught font name/size/line spacing applied to the normal style | same test |
| Table schema | Taught `table_columns` order appears in the saved table header | same test |
| Prohibited content | A prohibited term blocks creation and reports `prohibited_internal_information` | `test_word_renderer_refuses_prohibited_internal_information` |
| Sources | Source section is present when the taught order requires it | saved-artifact assertion |
| Correction/reopen | A corrected instruction changes the saved artifact; reopening reads the same bytes/hash | package smoke/restart evidence |

## Presentation (PPTX)

| Criterion | Pass condition | Evidence |
|---|---|---|
| Slide order | Taught `slide_order` is reflected in saved slide titles | `test_presentation_renderer_reorders_slides_and_applies_font` |
| Typography | Taught font size/name applied to slide text | same test |
| Tables | Taught column order preserved where a table is rendered | renderer test |
| Notes/order after reopen | Saved deck reopens with the same slide order and notes | saved-artifact check |
| Prohibited content | Prohibited terms block creation | renderer finding path |

## Spreadsheet (XLSX)

| Criterion | Pass condition | Evidence |
|---|---|---|
| Header/columns | Taught `table_columns` order in row 1 | `test_spreadsheet_renderer_applies_columns_header_and_freeze` |
| Header style | Bold/freeze header applied | same test |
| Types | Numeric measures remain numeric; formula text remains text | canvas export readback tests |
| Full frame | Totals cover the full eligible frame, not the display page | `test_total_uses_full_dataset_not_display_page` |

## Email draft

| Criterion | Pass condition | Evidence |
|---|---|---|
| Envelope | To/Cc/subject and thread/reply fields match the prepared draft | `test_email_canvas_attachments.py`, thread-reply tests |
| Greeting/signature | Taught greeting/signature applied deterministically | `apply_email_teaching` tests |
| Subject prefix | Taught prefix applied once | `apply_email_teaching` |
| Attachment association | Attachment ids resolve; approved sha256 matches the actual bytes before transport | attachment-hash tests |
| Draft-only | Saved draft is editable and `send_performed=false` | draft smoke |
| Prohibited content | Prohibited terms block the draft | renderer finding path |

## Rubric limits

- This rubric certifies the declared structural/style criteria above. It does
  not certify aesthetic quality, brand judgment or every possible renderer
  field.
- Layout-sensitive checks are representative, not pixel-perfect visual
  regression across every viewer.
- Embedded image/chart interpretation is excluded.
- A schema-valid artifact that fails a rubric criterion is reported as a
  finding, not silently accepted.
