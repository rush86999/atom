# Known limitations

- This is one bounded acceptance campaign, not universal reliability or
  whole-app certification.
- Workbook formula support is the demonstrated subset evaluated by the
  available `formulas` engine. A formula with no computed cache is named in
  `formula_gaps`; it is never silently displayed as blank or used in a
  certified total. LibreOffice is not required for the demonstrated subset.
- Embedded images and charts in DOCX/PPTX are not interpreted. Extracted text
  must not be assumed to cover them.
- Email sending was not performed. Send remains a separately authorized
  action; imported source attachments cannot be sent back automatically.
- The capability adapter supports `base_component: "table"` only. A structured
  canvas with an unknown adapter receives no write or text-replace authority.
- Capability copy/fork keeps the data shape but strips private teaching,
  decision policy, approval requirements and source binding; the copy must be
  re-taught/re-bound.
- The demonstrated review route is DeepSeek `deepseek-flash` with structured
  transport. Auxiliary planning may use another DeepSeek-served model; the
  certified review payload is pinned fail-closed. A review fallback to
  Pro/local/another provider is refused.
- No deployment, credential rotation or live-data operation was performed.
