# Context-aware teaching and artifact transfer — 2026-10-29

Status: **local/product-boundary acceptance passed for the demonstrated
contexts.** This is additive to the connected-readiness work. R3, the connected
evidence and the pending live refresh authorization are preserved.

## What was extended

The existing lesson journal (`AgentRegistry.configuration.learning.log`) now
carries optional, validated fields on the same stable teaching-point ID:

- `applies_to`: email/document/presentation/spreadsheet;
- `context`: open-ended task facts (category, audience, location, source
  version, qualification, effective dates, ...), not platform-owned business
  dimensions;
- `conditions`: optional recipient/task exception conditions;
- `format_spec`: typed output requirements;
- `replaces`: explicit replacement relationship by lesson ID;
- `field_mappings`: confirmed concept→sheet/column/unit/version mappings;
- `revision`: incremented by the existing PATCH correction path.

No second training store, classifier, review engine or vector database was
added.

## Applicability contract

`core/artifact_teaching.py` returns typed states:

- `applicable` — every required context fact is established and matches;
- `not_applicable` — a context value differs, an explicit exception applies,
  the workspace boundary differs, or the effective period excludes it;
- `needs_context` — a required qualification/fact is missing; return a targeted
  clarification;
- `conflict` — equally authoritative applicable instructions disagree;
- processing errors remain separate refusals.

Similarity/retrieval only nominates candidates. The resolver checks declared
conditions, workspace, effective dates, explicit replacements, exceptions and
specificity. Higher-specificity scoped guidance may override a broader rule
only through the declared context; at equal specificity, differing values are
reported as a conflict rather than chosen by recency.

Long governing instructions are no longer cut at 320 characters; the block is
still bounded to five lessons (8,000 characters) so a trailing “unless….”
condition survives.

## Product-boundary acceptance

Script: `/private/.../run_teaching_acceptance.py`
Evidence: `docs/acceptance/evidence/teaching_context_20261029/`

| Check | Result |
|---|---|
| Equivalent context (pricing/internal/Warehouse B/v1, qualification standard) | Document applied Arial 11, headings Summary→Findings→Sources, table Item/Value |
| Wrong location (Warehouse A) | `teaching.status=not_applicable`, empty spec; no transfer |
| Missing qualification | HTTP 409 `teaching_context_unresolved`; “I need confirmation … qualification.” |
| Explicit exception (qualification expedited) | Font size 14 applied; source lesson context names the qualification |
| Email protocol | Subject `[Review] Price review`, greeting/signature, `draft_only=true`, no send |
| Email prohibited term | HTTP 400 `prohibited_internal_information`; no artifact |
| Presentation | Slides reordered Overview→Findings→Sources |
| Spreadsheet | Header Item/Value, Arial, frozen header |
| Correction of one preference | Document revision 1→2, font 11→12; headings/table unchanged |
| Unrelated employee | Agent B lessons unchanged; B’s decision rule intact |
| Second context | Agent B service report uses Times New Roman 12 |
| Source text pretending to be teaching | B lesson count unchanged (2→2) |
| Restart | Revision 2, font 12, headings and table survive; email/deck/sheet reopen |

Saved artifacts copied into `evidence/teaching_context_20261029/artifacts/`:
DOCX, corrected DOCX, PPTX, XLSX.

## Local controls

`backend/tests/test_artifact_teaching_context.py` and
`backend/tests/test_artifact_renderers_teaching.py` cover:

- renamed/reordered fields with equivalent context;
- wrong location not applicable;
- missing qualification → needs_context;
- equal-specificity conflict surfaced;
- general rule plus scoped exception;
- workspace mismatch → no teaching;
- stale source version → not applicable;
- explicit replacement;
- effective-period exclusion;
- exact field mapping, ambiguous same column on two sheets, stale version,
  unit change;
- document/email/presentation/spreadsheet renderer checks;
- long trailing exception retained;
- revision increment with unrelated agent preserved.

## Boundaries / unsupported

- Subjective tone/visual balance is not claimed as deterministic; only the
  declared objective rubric/checks are certified.
- Confirmed field mappings are validated by a pure resolver and tested; the
  full multi-sheet mapping UI/clarification loop is not yet wired into every
  canvas surface.
- A model proposal for conditions/field mappings is not authority; the API
  stores only explicitly submitted/confirmed fields.
- No deployment, send, source writeback, credential change or model reopening.

## Release position

R3 remains `expanded-core-2026-10-28-r3 → 68b949409`. The connected successor
still waits on the one combined live-refresh/disposable-source authorization;
this teaching slice does not change that exit condition.
