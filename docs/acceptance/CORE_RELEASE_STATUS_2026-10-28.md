# Core release status — 2026-10-28

## Recommended launch configuration

DeepSeek direct **`deepseek-flash`**, provider policy selected to `deepseek`
only, no Pro or local fallback, structured review on, streaming off, 180 s
turn and request deadlines, 300,000 ms client timeout.

`deepseek-v4-pro` remains a verified alternative from the earlier core loop.

## State

| State | Meaning | Current |
|---|---|---|
| Core workflow verified | The demonstrated CSV assessment/calculation/correction/restart loop passed | **Yes — 28/28 checks** |
| Package ready | Durable package, checksums, template, startup/backup/smoke/rollback docs exist | **Yes** |
| Deployed | Installed on a live environment | **No — deployment decision pending** |

## Evidence

- Flash screening: `docs/acceptance/evidence/whole_app_20261028/deepseek_flash_judgment_comparison_20261028/` — 7/7 substantive and certified, avg 2.3 s, est. $0.0057.
- Flash core loop: `docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_flash_20261028/` — 28/28 checks, calculation 22200.00, correction, fresh post-restart judgment, zero unauthorized writes.
- Pro core loop (verified alternative): `docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_20261028_final2/`.
- All earlier failed attempts remain preserved.

## Scope of the claim

This is the demonstrated core CSV assessment/calculation workflow. It does not
certify every common-data workflow: email, PowerPoint, document generation and
other surfaces remain bound to their own evidence. Broader BYOK, streaming and
whole-app certification are separate.

One passing loop is a bounded pilot claim, not universal reliability.

## Deployment

No deployment has been performed. A controlled core pilot using the verified
Flash configuration is the recommended launch position. Deployment approval is
required separately.
