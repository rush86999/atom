# Core release status — 2026-10-28 — demonstrated loop PASS

Candidate: `whole-app/successor-f5f` app code `ec5ca78b8`, with transport and
launch repairs through `0640b95e2`. This is the demonstrated core-release
slice, not whole-app certification.

## Winning configuration

DeepSeek direct `deepseek-v4-pro`, provider policy selected to `deepseek` only,
no Ollama/other fallback, structured review on, streaming off, 180 s backend
turn/request budget and 300,000 ms client timeout. The global local-only
default and stored credentials are unchanged; the exception applied only to
the isolated child.

## Gates

| Gate | Result |
|---|---|
| Fixed screening (7 cases, full context + boundaries) | 7/7 substantive, 7/7 certified |
| Real scoped product route | actual `deepseek-v4-pro`, certified, correct decisions |
| Narrow previously intermittent grants request | pass, certified, actual v4-pro |
| Unchanged core UI loop | 25/25 checks pass |
| Calculation | 22200.00, 3 Open rows, cell citations, source hash |
| Correction + different unfamiliar assessment | pass |
| Restart persistence + fresh assessment | pass |
| Zero unauthorized writes | pass |

## Evidence

- `docs/acceptance/evidence/whole_app_20261028/deepseek_judgment_comparison_20261028/`
- `docs/acceptance/evidence/whole_app_20261028/deepseek_product_route_20261028/`
- `docs/acceptance/evidence/whole_app_20261028/core_release_narrow_grants_20261028_attempt8/`
- `docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_20261028_final2/`
- Four failed UI attempts remain preserved in the sibling attempt directories.

## Residual

A single passing UI loop after four preserved failures is a demonstrated
workflow, not a general reliability guarantee. Deferred integrations,
scheduling, marketplace, broader BYOK certification and whole-app claims remain
out of scope. No deployment is authorized; this stops at the deployment
boundary.
