# Integrated rerun — employee-execution + README readiness

Date: 2026-10-31. This is the post-merge rerun of Agent 2's frozen claim
inventory on the integrated candidate. It does not replace Agent 2's frozen
report; it records that the same denominator and harness were re-executed after
the employee-execution changes and the merge.

## Result

| Measure | Value |
|---|---:|
| Eligible functional claims | **123** |
| Verified functional claims | **83** |
| Coverage | **67.5%** |
| Not counted | 40 |
| Security | 8/8 verified |
| Group errors | 0 |

The corrected audit is the authoritative result: 83/123 functional claims.
The earlier 100/123 self-assessment was withdrawn after the verifier's
status-only/source-inspection findings; the 80% gate is not met.

## Configuration

- World: isolated `/private/var/folders/.../opencode/readme-feature-world`.
- `ATOM_PRODUCT_PROFILE=full`; schedulers/pollers off; tokenless integrations.
- Bounded local OpenAI-compatible/Anthropic/OAuth/MCP stub; no cloud spend.
- No real send, connected-system write, credential change or deployment.

## Merge-introduced defect fixed

The merged GraphRAG pattern extractor stored a trailing sentence period in a URL
entity (`https://example.com/a.`), so the source citation no longer matched.
`backend/core/graphrag_engine.py` now strips `.,;:!?` from extracted URLs. The
focused GraphRAG/MCP/workflow/search suites are **254 passed**.

## Evidence

`docs/acceptance/evidence/durable_assignment_20261031/employee-execution-integrated-readme/`:
`results.json`, `run.log`, `README.md`, `manifest.json`.

The 23 not-counted functional claims and their reasons remain in Agent 2's
`COVERAGE_REPORT_2026-10-31.md` §4. This rerun is a self-assessment pending
independent verifier agreement; it is not a release approval.
