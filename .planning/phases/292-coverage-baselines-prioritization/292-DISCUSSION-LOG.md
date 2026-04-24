# Phase 292: Coverage Baselines & Prioritization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 292-coverage-baselines-prioritization
**Areas discussed:** Baseline measurement validation, High-impact threshold & scoring, Frontend coverage approach, Deliverable format & validation

---

## Baseline measurement validation

| Option | Description | Selected |
|--------|-------------|----------|
| Re-run from scratch | Execute `pytest --cov` fresh, generate new coverage.json. The fresh number IS the baseline. | ✓ |
| Validate existing output | Verify latest coverage snapshot is structurally valid and matches fresh run | |
| Compare against historical trend | Run fresh measurement, compare against coverage_266_final.json (17.13%) | |

**User's choice:** Re-run from scratch
**Notes:** The 18.25% v10.0 figure is a reference point, not authoritative. Fresh run is the baseline.

### Follow-up: Structural validation

| Option | Description | Selected |
|--------|-------------|----------|
| Both — structural validation + number | Verify all coverage.json fields present AND confirm percentage | ✓ |
| Just the number | Run measurement, record percentage, trust pytest-cov tooling | |
| You decide | Claude decides what's sufficient | |

**User's choice:** Both structural validation + number
**Notes:** Reject incomplete or malformed coverage.json output.

---

## High-impact threshold & scoring

| Option | Description | Selected |
|--------|-------------|----------|
| Strict <10% as stated | Files with >200 lines AND <10% coverage. ROADMAP literal. | |
| Broader approach with scoring | <30% coverage, ranked by priority_score formula. More files, prioritized. | |
| Layered approach | Tier 1: <10%, Tier 2: 10-30%, Tier 3: 30-50%. All >200 lines. | ✓ |

**User's choice:** Layered approach
**Notes:** Provides flexibility for downstream phases — Phase 293 picks Tier 1, later phases pull from lower tiers.

### Follow-up: Scoring methodology and LOC cutoff

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing scoring infra | Run existing prioritize_high_impact_files.py with updated data | |
| Fresh scoring, >200 LOC | Build new scoring referencing business_impact_scores.json | |
| You decide both | Claude picks | ✓ |

**User's choice:** You decide (Claude's discretion)
**Notes:** Claude chose to reuse existing prioritize_high_impact_files.py and business_impact_scorer.py with >200 LOC cutoff.

---

## Frontend coverage approach

| Option | Description | Selected |
|--------|-------------|----------|
| Require 291 completion first | Block until 100% pass rate, then measure | ✓ |
| Measure what's there | Run `--coverage` regardless of pass rate | |
| Both — measure now + after | Pre-fix and post-fix baselines for comparison | |

**User's choice:** Require 291 completion first
**Notes:** Clean dependency chain. No frontend measurement until all 1,504 tests pass.

### Follow-up: Frontend component prioritization

| Option | Description | Selected |
|--------|-------------|----------|
| Business criticality first | Rank by feature importance — Canvas, Chat, Dashboard, Integrations | ✓ |
| Lines of code first | Same formula as backend — largest files first | |
| You decide | Claude picks | |

**User's choice:** Business criticality first
**Notes:** Frontend components vary in complexity vs importance — business value matters more than file size.

---

## Deliverable format & validation

| Option | Description | Selected |
|--------|-------------|----------|
| JSON + Markdown reports | JSON for downstream scripts, Markdown for human review | ✓ |
| Markdown only | Clean Markdown tables, simple but requires parsing | |
| You decide | Claude picks | |

**User's choice:** JSON + Markdown reports
**Notes:** Both formats needed — executor scripts in Phases 293-295 consume JSON, humans review Markdown.

### Follow-up: Acceptance criteria

| Option | Description | Selected |
|--------|-------------|----------|
| ROADMAP criteria are sufficient | All 5 success criteria from ROADMAP | |
| Add cross-check verification | ROADMAP criteria + cross-check + parseability | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide (Claude's discretion)
**Notes:** Claude chose ROADMAP criteria + cross-check (frontend/backend lists complementary) + JSON parseability validation + measurement methodology documentation + clean exit codes.

---

## Claude's Discretion

| Area | Discretion |
|------|-----------|
| Scoring methodology | Reuse existing prioritize_high_impact_files.py and business_impact_scorer.py |
| LOC cutoff | Keep >200 lines (ROADMAP requirement) |
| Output file paths | Use existing coverage_reports/metrics/ directory |
| Measurement script approach | Wrap existing scripts for Phase 292 rather than build from scratch |
| Acceptance criteria details | ROADMAP criteria + structural + parseability + cross-check + clean exit |
| Frontend measurement config | Use Jest standard --coverage with COVERAGE_PHASE=phase_1 |
| Partial 291 completion handling | Document the gap, do not measure frontend |

## Deferred Ideas

None — discussion stayed within phase scope.
