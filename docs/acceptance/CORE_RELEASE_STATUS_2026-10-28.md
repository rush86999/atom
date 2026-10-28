# Core release status — 2026-10-28

## Recommended launch configuration

DeepSeek direct **`deepseek-flash`** for the assessment/review payload,
provider policy selected to `deepseek` only, structured review on, streaming
off, 180 s turn and request deadlines, 300,000 ms client timeout. Auxiliary
planning/verification calls remain on the same DeepSeek provider and may use
another served model; the certified review payload is Flash and a review
fallback to Pro/local/another provider is refused.

`deepseek-v4-pro` remains a verified alternative from the earlier core loop.
Model selection is not reopened by the expanded scope.

## State

| State | Meaning | Current |
|---|---|---|
| CSV workflow verified | The demonstrated CSV assessment/calculation/correction/restart loop passed | **Yes — 28/28 checks** |
| Expanded core verified | Email, documents, PowerPoint, Excel-like canvas and the cross-material employee job each have UI/public-boundary evidence | **Yes — all required slices passed** |
| Package ready | A frozen durable package exists for the verified scope | **Yes — expanded package r3 prepared** |
| Deployed | Installed on a live environment | **No — deployment decision pending** |

**Support statement:** The frozen CSV package retains its CSV-only claim. The
expanded package supports the demonstrated Excel-like canvas, email, DOCX,
PPTX and one bounded cross-material employee job. Neither package is deployed.

## Evidence

- Expanded core: `docs/acceptance/evidence/whole_app_20261028/expanded_core_20261028/` — office slices 40/40 UI + 17/17 artifact checks; two user-created capability canvases 33/33; employee job 16/16 before restart, 17/17 after restart, 19/19 artifact checks. Re-run after three read-only reviews and remediation; tested code `c04591909`.
- Flash screening: `docs/acceptance/evidence/whole_app_20261028/deepseek_flash_judgment_comparison_20261028/` — 7/7 substantive and certified, avg 2.3 s, est. $0.0057.
- Flash core loop: `docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_flash_20261028_fixed2/` — 28/28 checks, calculation 22200.00, correction, fresh post-restart judgment, zero unauthorized writes.
- Pro core loop (verified alternative): `docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_20261028_final2/`.
- All earlier failed attempts remain preserved.

## Scope of the claim

The expanded package certifies the demonstrated Excel-like workbook, email,
DOCX, PPTX and one cross-material employee job, each with its own
UI/public-boundary evidence. It does not certify every common-data workflow or
whole-app behavior. Capability adapters currently support the table base
component; email sending, embedded image/chart interpretation and deployment
remain outside the claim.

One passing acceptance campaign is a bounded pilot claim, not universal
reliability.

## Deployment

No deployment has been performed. A controlled core pilot using the verified
Flash configuration is the recommended launch position once the expanded
scope has passed or the owner explicitly narrows the claim back to CSV.
Deployment approval is required separately.
