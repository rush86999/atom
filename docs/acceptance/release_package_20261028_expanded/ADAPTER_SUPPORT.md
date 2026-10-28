# Adapter support matrix

| Adapter / capability | Selection | Sum/count | Assessment | Edit + readback | Export | Notes |
|---|---|---|---|---|---|---|
| User-created table canvas | Yes | Yes | Yes (task policy/decisions) | Yes (declared fields) | XLSX | Versioned manifest; unknown adapters get no authority |
| XLSX workbook canvas | Display filter | Formula cells | Via table/capability canvas | Cell/formula edit | XLSX | Formula subset; `formula_gaps` names unsupported caches |
| Email canvas | n/a | n/a | Via table/capability canvas | Draft edit | EML attachment download | Import/draft only; send unauthorized |
| DOCX canvas | n/a | n/a | Via grounded content | Paragraph edit | DOCX | Tables preserved/read |
| PPTX canvas | n/a | n/a | Via grounded content | Title/body edit | PPTX | Tables/notes read; slide order preserved |
