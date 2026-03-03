# Business Impact Scoring Methodology

**Generated:** 2026-02-27T16:12:17.154128Z
**Phase:** 100-02
**Purpose:** Assign business impact scores to source files for coverage prioritization

---

## Overview

Not all uncovered lines are equally important. A governance bug is 10x more critical than a UI utility bug. Business impact scoring weights coverage gaps by business criticality so we prioritize testing where it matters most.

This enables the COVR-02 requirement: **"rank files by (lines * impact / current_coverage)"**.

---

## Impact Tiers

### Critical (Score: 10)

**Definition:** Core business logic that keeps Atom running safely and effectively.

**Patterns:**
- `agent_context_resolver`
- `agent_governance`
- `agent_graduation`
- `browser`
- `byok_handler`
- `canvas_state`
- `canvas_tool`
- `cognitive_tier`
- `constitutional`
- `constitutional_validator`
- `episode_lifecycle`
- `episode_retrieval`
- `episode_segmentation`
- `governance_cache`
- `llm`
- `meta_agent_training`
- `proposal_service`
- `student_training`
- `supervision_service`
- `trigger_interceptor`

**Examples:**
- `agent_governance_service.py` - Agent permission checks
- `byok_handler.py` - LLM provider routing
- `episode_segmentation_service.py` - Memory creation
- `canvas_tool.py` - Canvas presentations

**Impact:** Bugs here can cause security breaches, data loss, or system failure.

---

### High (Score: 7)

**Definition:** Important operational features with significant business impact.

**Patterns:**
- `auth`
- `browser_tool`
- `business_fact`
- `device_capabilities`
- `device_tool`
- `hazard_sandbox`
- `package_dependency`
- `package_governance`
- `package_installer`
- `permission`
- `policy_fact`
- `security`
- `skill_adapter`
- `skill_registry`
- `skill_security`
- `world_model`

**Examples:**
- `browser_tool.py` - Web automation
- `device_tool.py` - Device capabilities
- `package_governance_service.py` - Package security

**Impact:** Bugs here can cause feature failures or degraded user experience.

---

### Medium (Score: 5)

**Definition:** Supporting services and infrastructure.

**Patterns:**
- `agent_guidance`
- `analytics`
- `canvas_guidance`
- `dashboard`
- `deeplink`
- `embedding`
- `extractor`
- `feedback`
- `formula`
- `health`
- `integration`
- `lancedb`
- `monitoring`
- `vector`
- `workflow`

**Examples:**
- Workflow orchestration
- Analytics and monitoring
- Integration adapters

**Impact:** Bugs here can cause minor disruptions or dashboard errors.

---

### Low (Score: 3)

**Definition:** Utilities, helpers, and non-core features.

**Patterns:**
- `config`
- `constant`
- `deprecated`
- `example`
- `fixture`
- `helper`
- `mock`
- `test`
- `util`

**Examples:**
- Utility functions
- Test fixtures
- Configuration loaders

**Impact:** Bugs here have minimal impact on core operations.

---

## Scoring Distribution

### Summary Statistics

| Metric | Count |
|--------|-------|
| Total Files | 503 |
| Total Lines | 69,417 |
| Uncovered Lines | 50,865 |

### Files by Tier

| Tier | Score | File Count | Uncovered Lines |
|------|-------|------------|-----------------|
| Critical | 10 | 30 | 4,868 |
| High | 7 | 25 | 2,874 |
| Medium | 5 | 435 | 42,376 |
| Low | 3 | 13 | 747 |

---

## Top Gaps by Tier

### Critical Tier (Score: 10)

| File | Coverage | Uncovered Lines |
|------|----------|-----------------|
| core/llm/byok_handler.py | 8.72% | 582 |
| core/episode_segmentation_service.py | 8.25% | 510 |
| tools/canvas_tool.py | 3.8% | 385 |
| core/proposal_service.py | 7.64% | 309 |
| core/episode_retrieval_service.py | 9.03% | 271 |

### High Tier (Score: 7)

| File | Coverage | Uncovered Lines |
|------|----------|-----------------|
| core/skill_registry_service.py | 7.19% | 331 |
| core/agent_world_model.py | 14.02% | 245 |
| tools/device_tool.py | 9.73% | 244 |
| core/enterprise_auth_service.py | 19.54% | 204 |
| core/skill_adapter.py | 17.01% | 179 |

---

## Usage

### Prioritization Formula

Rank files for testing using:

```
priority_score = (uncovered_lines * impact_score) / current_coverage
```

**Example:**
- File A: 100 uncovered lines, Critical (score=10), 0% coverage
  - Priority: (100 * 10) / 1 = 1000
- File B: 100 uncovered lines, High (score=7), 50% coverage
  - Priority: (100 * 7) / 0.5 = 1400
- File C: 100 uncovered lines, Low (score=3), 20% coverage
  - Priority: (100 * 3) / 0.2 = 1500

**Result:** File C (Low tier, poor coverage) ranks higher than File A (Critical tier, no tests) because it has lower existing coverage.

### Quick Wins Strategy

1. **Critical tier files with 0% coverage** - Highest priority
2. **High tier files with <20% coverage** - Quick wins
3. **Large files (500+ lines) with low coverage** - Maximum coverage gain

---

## Data Sources

- **Coverage Baseline:** `tests/coverage_reports/metrics/coverage_baseline.json`
- **Impact Scores:** `tests/coverage_reports/metrics/business_impact_scores.json`
- **Critical Paths:** `tests/coverage_reports/critical_path_mapper.py`

---

*Generated by Phase 100-02 Business Impact Scoring*
*Timestamp: {datetime.utcnow().isoformat() + 'Z'}*
