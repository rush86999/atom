# Phase 21 Research: LLM-Generated Canvas Presentation Summaries

**Phase**: 21-llm-canvas-summaries
**Date**: February 18, 2026
**Status**: Research Complete

---

## Executive Summary

Phase 20 implemented canvas context for episodic memory using metadata extraction (deterministic, fast). Phase 21 enhances this with **LLM-generated presentation summaries** that provide richer semantic understanding of what was presented on canvases.

**Current State (Phase 20)**:
- `presentation_summary` field populated via metadata extraction
- Example: "Agent presented approval form with revenue chart"
- Deterministic, fast (~5ms), but limited semantic depth

**Proposed Enhancement (Phase 21)**:
- LLM-generated summaries that understand context, intent, and meaning
- Example: "Agent presented $1.2M workflow approval requiring board consent with Q4 revenue trend chart showing 15% growth, highlighting risks and requesting user decision"
- Richer semantic understanding for better episode retrieval and agent learning

**Why This Matters**:
1. **Better Episode Retrieval**: "Find episodes where I approved risky workflows" → LLM summaries capture semantic meaning
2. **Agent Learning**: Agents can understand not just what happened, but why it mattered
3. **Semantic Search**: Natural language queries work better with rich summaries
4. **Decision Context**: Capture the reasoning behind decisions, not just the outcome

---

## Problem Statement

### Current Limitations of Metadata Extraction

**Phase 20 Implementation** (metadata extraction):
```python
presentation_summary = f"Agent presented {canvas_type} with {visual_elements}"

# Example outputs:
- "Agent presented orchestration with line_chart"
- "Agent presented form with approval_button"
- "Agent presented chart with data_table"
```

**Limitations**:
1. **No Context**: Doesn't capture business context (workflow amounts, risks, deadlines)
2. **No Intent**: Doesn't explain why something was presented (approval request, data exploration, error recovery)
3. **No Semantics**: "line_chart" doesn't say what the data shows (revenue growth, user churn, performance metrics)
4. **No Decision Context**: Doesn't capture the reasoning behind user decisions

**Impact on Episode Retrieval**:
- Query: "Find episodes where I approved high-risk workflows"
- Current: "Agent presented orchestration with line_chart" → no match (missing "high-risk", "workflow details")
- Desired: "Agent presented $1.2M workflow approval requiring board consent with risk analysis showing 3 critical blockers" → semantic match

### Why LLM Generation?

**LLMs excel at**:
1. **Context Understanding**: Parse business logic, identify risks, extract key metrics
2. **Intent Inference**: Understand why something was presented (approval, exploration, debugging)
3. **Semantic Summarization**: Distill complex information into natural language
4. **Decision Capture**: Explain the reasoning behind decisions, not just the outcome

**Example Comparison**:

| Canvas Type | Metadata Extraction | LLM-Generated Summary |
|-------------|---------------------|----------------------|
| **Orchestration** | "Agent presented orchestration with approval_form" | "Agent presented $1.2M workflow approval for Q4 marketing campaign requiring board consent due to budget exceeding $1M threshold, with stakeholder approval matrix showing 3 pending responses" |
| **Chart** | "Agent presented line_chart" | "Agent presented Q4 revenue trend chart showing 15% growth ($12.3M vs $10.7M) with notable spike in November due to holiday sales, highlighting deviation from forecast" |
| **Terminal** | "Agent presented terminal" | "Agent presented build output showing 12 tests passing, 2 failing with integration errors in payment service, deployment blocked until critical bugs resolved" |
| **Form** | "Agent presented form" | "Agent presented data access request form for customer support role requiring PII access justification, manager approval, and compliance training verification" |

---

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Canvas Presentation                       │
│                   (Agent displays canvas)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  Canvas State Capture (Phase 20)     │
        │  - Hidden accessibility trees        │
        │  - State API (window.atom.canvas)    │
        └──────────────────────┬───────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────┐
        │   LLM Summary Generation (Phase 21)  │
        │  1. Collect canvas state             │
        │  2. Build LLM prompt with context    │
        │  3. Generate semantic summary        │
        │  4. Store in EpisodeSegment          │
        └──────────────────────┬───────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────┐
        │    EpisodeSegment.canvas_context     │
        │  {                                   │
        │    canvas_type: "orchestration",     │
        │    presentation_summary: "LLM-generated rich summary...", │
        │    visual_elements: [...],           │
        │    critical_data_points: {...}       │
        │  }                                   │
        └──────────────────────────────────────┘
```

### Implementation Strategy

#### Step 1: LLM Summary Generation Service

**File**: `backend/core/llm/canvas_summary_service.py`

**Responsibilities**:
1. Collect canvas state from Phase 20 accessibility trees or state API
2. Build LLM prompts with canvas context, agent task, user interaction
3. Generate semantic summaries using BYOK handler (multi-provider)
4. Cache summaries to avoid redundant generation
5. Fallback to metadata extraction if LLM fails

**Methods**:
```python
class CanvasSummaryService:
    async def generate_summary(
        canvas_type: str,
        canvas_state: dict,
        agent_task: str,
        user_interaction: Optional[str]
    ) -> str:
        """Generate LLM-powered semantic summary of canvas presentation"""

    async def _build_prompt(
        canvas_type: str,
        canvas_state: dict,
        agent_task: str
    ) -> str:
        """Build LLM prompt with canvas context"""

    async def _fallback_to_metadata(
        canvas_type: str,
        canvas_state: dict
    ) -> str:
        """Fallback to metadata extraction if LLM fails"""
```

#### Step 2: Prompt Engineering

**Prompt Template**:
```
You are analyzing a canvas presentation from an AI agent interaction. Generate a concise semantic summary (50-100 words) that captures:

1. **What was presented**: Canvas type, key elements, data shown
2. **Why it mattered**: Business context, decision required, risks highlighted
3. **Critical data**: Key metrics, amounts, deadlines, stakeholders
4. **User decision**: What the user did (if applicable)

**Canvas Type**: {canvas_type}
**Agent Task**: {agent_task}
**Canvas State**: {canvas_state_json}
**User Interaction**: {user_interaction}

**Summary**:
```

**Canvas-Specific Prompts**:

**Orchestration Canvas**:
```
Focus on: Workflow details, approval amounts, stakeholders, risks, decision context
Key fields to extract: workflow_id, approval_amount, approvers, blockers, deadline
```

**Chart Canvas**:
```
Focus on: Data trends, anomalies, key metrics, time periods, deviations from forecast
Key fields to extract: chart_type, data_points, axes_labels, notable_spikes, trends
```

**Terminal Canvas**:
```
Focus on: Command output, errors, test results, deployment status, failures
Key fields to extract: command, exit_code, error_lines, test_counts, blocking_issues
```

**Form Canvas**:
```
Focus on: Form purpose, required fields, validation rules, approval workflow
Key fields to extract: form_title, required_fields, validation_errors, submit_action
```

#### Step 3: Integration with Episode Segmentation

**File**: `backend/core/episode_segmentation_service.py` (modify)

**Change**: Update `_extract_canvas_context()` to use LLM generation:

```python
async def _extract_canvas_context(
    self,
    canvas_audit: CanvasAudit,
    agent_task: str
) -> dict:
    """Extract canvas context with LLM-generated summary"""

    # Get canvas state from Phase 20 accessibility tree
    canvas_state = await self._get_canvas_state(canvas_audit.canvas_id)

    # Generate LLM summary (Phase 21)
    presentation_summary = await self.canvas_summary_service.generate_summary(
        canvas_type=canvas_audit.canvas_type,
        canvas_state=canvas_state,
        agent_task=agent_task,
        user_interaction=canvas_audit.action
    )

    return {
        "canvas_type": canvas_audit.canvas_type,
        "presentation_summary": presentation_summary,  # LLM-generated
        "visual_elements": self._extract_visual_elements(canvas_state),
        "user_interaction": self._extract_user_interaction(canvas_audit),
        "critical_data_points": self._extract_critical_data(canvas_state)
    }
```

#### Step 4: Performance Considerations

**LLM Generation Latency**: 500-2000ms (depending on provider and model)

**Mitigation Strategies**:
1. **Async Generation**: Don't block episode creation on summary generation
2. **Background Queue**: Generate summaries in background, update episodes later
3. **Caching**: Cache summaries by canvas state hash (avoid redundant generation)
4. **Fallback to Metadata**: Use metadata extraction if LLM takes >5s
5. **Progressive Enhancement**: Start with metadata, update to LLM summary when ready

**Implementation Options**:

**Option A: Sync Generation** (simplest)
- Generate summary during episode creation
- Pros: Consistent, always available
- Cons: Blocks episode creation (+500-2000ms)

**Option B: Async Generation** (recommended)
- Create episode with metadata summary immediately
- Generate LLM summary in background
- Update episode when ready
- Pros: Fast episode creation, richer summaries
- Cons: Eventually consistent (summary may update 1-2s later)

**Option C: Hybrid** (best UX)
- Generate summary during episode creation with 2s timeout
- If timeout, use metadata and queue background generation
- Update episode when background generation completes
- Pros: Best of both worlds
- Cons: More complex

**Recommendation**: Start with Option A (Sync Generation) for Phase 21, optimize to Option C in Phase 22+ if needed.

#### Step 5: Cost Management

**LLM API Costs** (per 1K tokens):
- GPT-4: $0.03 (input) + $0.06 (output) = $0.09 per summary
- Claude Sonnet: $0.003 + $0.015 = $0.018 per summary
- DeepSeek: $0.0001 + $0.0002 = $0.0003 per summary

**Estimated Costs** (10K episodes/day):
- GPT-4: $900/day (~$27K/month)
- Claude Sonnet: $180/day (~$5.4K/month)
- DeepSeek: $3/day (~$90/month)

**Recommendation**: Use DeepSeek or Claude Sonnet for cost efficiency. Implement per-episode cost tracking.

#### Step 6: Testing Strategy

**Unit Tests**:
1. Test prompt building for each canvas type
2. Test summary parsing and validation
3. Test fallback to metadata extraction
4. Test caching behavior

**Integration Tests**:
1. Test end-to-end summary generation for each canvas type
2. Test episode creation with LLM summaries
3. Test episode retrieval with LLM-enriched summaries
4. Test cost tracking and rate limiting

**Quality Tests**:
1. Compare LLM summaries to metadata extraction
2. Validate semantic richness (key information captured)
3. Test hallucination detection (LLM making up facts)
4. Test consistency (same canvas state → same summary)

**Evaluation Criteria**:
- **Semantic Richness**: Summary contains business context, intent, decision reasoning
- **Accuracy**: No hallucinations, only information present in canvas state
- **Consistency**: Same canvas state generates consistent summary across runs
- **Conciseness**: 50-100 words per summary (not too verbose)

---

## Success Criteria

### Functional Requirements

1. ✅ LLM-generated summaries captured for all 7 canvas types
2. ✅ Summaries are semantically richer than metadata extraction
3. ✅ Episode retrieval returns LLM-enriched summaries
4. ✅ Fallback to metadata extraction if LLM fails
5. ✅ Cost tracking implemented (<$0.01 per episode target)
6. ✅ Summary generation <5s per episode (or background queue)
7. ✅ No LLM hallucinations (only facts from canvas state)

### Non-Functional Requirements

1. ✅ Episode creation latency <3s (if sync) or <500ms (if async)
2. ✅ LLM cost <5% of episode storage cost
3. ✅ Cache hit rate >50% (avoid redundant generation)
4. ✅ Test coverage >60% for summary generation service

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Semantic Richness Score | >80% (vs 40% for metadata) | Human evaluation of 100 random episodes |
| Hallucination Rate | 0% | Automated fact-checking against canvas state |
| Consistency (same state) | >90% | Generate summary 5x, compare semantic similarity |
| Information Recall | >90% | Key facts present in summary (workflow_id, amounts, etc.) |

---

## Implementation Plans

### Plan 01: LLM Summary Generation Service
**Files**:
- `backend/core/llm/canvas_summary_service.py` (new, ~300 lines)
- `backend/core/llm/__init__.py` (update exports)

**Tasks**:
1. Create CanvasSummaryService with generate_summary() method
2. Build canvas-specific prompts for all 7 canvas types
3. Implement LLM generation via BYOK handler
4. Add fallback to metadata extraction
5. Implement caching by canvas state hash
6. Add cost tracking and rate limiting

**Success Criteria**:
- generate_summary() works for all 7 canvas types
- Prompts capture key context (task, state, interaction)
- Fallback to metadata if LLM fails
- Cache reduces redundant calls

### Plan 02: Episode Segmentation Integration
**Files**:
- `backend/core/episode_segmentation_service.py` (modify)
- `backend/core/episode_segmentation_service_test.py` (update tests)

**Tasks**:
1. Update _extract_canvas_context() to use CanvasSummaryService
2. Make summary generation async with 2s timeout
3. Implement fallback to metadata if timeout
4. Add background queue for async updates (optional)
5. Update episode creation tests
6. Verify episode creation latency <3s

**Success Criteria**:
- Episodes created with LLM summaries
- Fallback to metadata if LLM fails/times out
- Episode creation latency <3s
- All existing tests still pass

### Plan 03: Quality Testing & Validation
**Files**:
- `backend/tests/test_canvas_summary_service.py` (new, ~500 lines)
- `backend/tests/integration/test_llm_episode_integration.py` (new, ~400 lines)

**Tasks**:
1. Unit tests for prompt building (7 canvas types)
2. Unit tests for summary generation and validation
3. Integration tests for episode creation with LLM summaries
4. Quality tests: semantic richness, accuracy, consistency
5. Hallucination detection tests
6. Cost tracking and rate limiting tests

**Success Criteria**:
- All 7 canvas types have passing tests
- Semantic richness >80% (vs 40% metadata)
- Hallucination rate = 0%
- Test coverage >60%

### Plan 04: Coverage & Documentation
**Files**:
- `backend/tests/coverage_reports/metrics/coverage.json` (update)
- `docs/LLM_CANVAS_SUMMARIES.md` (new, ~400 lines)
- `.planning/phases/21-llm-canvas-summaries/21-PHASE-SUMMARY.md` (new)

**Tasks**:
1. Generate coverage report for LLM summary service
2. Verify >60% coverage target achieved
3. Create comprehensive developer documentation
4. Document prompt engineering patterns
5. Document cost optimization strategies
6. Create Phase 21 summary with results

**Success Criteria**:
- Coverage >60% for canvas_summary_service.py
- Complete developer documentation
- Phase summary with metrics and recommendations

---

## Open Questions

1. **Sync vs Async Generation**: Should we block episode creation on summary generation?
   - **Recommendation**: Start with sync (2s timeout), optimize to async later if needed

2. **Which LLM Provider**: GPT-4 (best quality), Claude Sonnet (balanced), DeepSeek (cheapest)?
   - **Recommendation**: Claude Sonnet (quality/cost balance)

3. **Caching Strategy**: Cache by exact canvas state hash or semantic similarity?
   - **Recommendation**: Exact hash first, semantic similarity later (Phase 22+)

4. **Background Queue**: Use Celery, asyncio, or simple thread pool?
   - **Recommendation**: Asyncio with background tasks (no external dependencies)

5. **Quality Evaluation**: Human evaluation or automated metrics?
   - **Recommendation**: Automated metrics first (consistency, recall), human spot-checks

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **LLM Hallucinations** | High | Medium | Strict prompt engineering, fact-checking, fallback to metadata |
| **High API Costs** | Medium | Medium | Use cheaper providers (DeepSeek), caching, rate limiting |
| **Slow Generation** | Medium | Low | Timeout with fallback, async generation, background queue |
| **Inconsistent Summaries** | Low | Medium | Stable prompts, temperature=0, deterministic mode |
| **Episode Creation Latency** | Medium | Low | 2s timeout, async updates, progressive enhancement |

---

## Related Work

### Phase 20: Canvas AI Context & Episodic Memory
- Implemented canvas_context field in EpisodeSegment
- Created metadata extraction (deterministic, fast)
- Established canvas state capture (accessibility trees, state API)

**Phase 21 Builds On**: Replace metadata extraction with LLM generation for richer semantic understanding

### Phase 14: Community Skills Integration
- SkillAdapter parses SKILL.md files
- Skills can present canvases

**Phase 21 Benefits**: Skill episodes will have richer semantic summaries

### BYOK Handler (Multi-Provider LLM)
- Supports OpenAI, Anthropic, DeepSeek, Gemini
- Token-by-token streaming, cost tracking
- Provider failover

**Phase 21 Uses**: Leverage BYOK handler for summary generation

---

## Next Steps

1. ✅ Research complete
2. ⏭️ Create Plan 01: LLM Summary Generation Service
3. ⏭️ Create Plan 02: Episode Segmentation Integration
4. ⏭️ Create Plan 03: Quality Testing & Validation
5. ⏭️ Create Plan 04: Coverage & Documentation

---

**Research Duration**: 30 minutes
**Researcher**: Claude (gsd-phase-researcher)
**Status**: ✅ COMPLETE - Ready for plan creation
