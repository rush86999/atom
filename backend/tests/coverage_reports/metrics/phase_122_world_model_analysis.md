# Phase 122: Agent World Model Coverage Gap Analysis

**Target File**: `backend/core/agent_world_model.py`
**Baseline Coverage**: 24.40% (Plan 01)
**Target Coverage**: 60%+
**Lines to Add**: ~118 lines

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total Lines | 332 |
| Covered Lines | 81 |
| Missing Lines | 251 |
| Coverage % | 24.40% |
| Target % | 60% |
| Gap | 35.60% |

## Zero-Coverage Methods

The following WorldModelService methods have 0% coverage from Plan 01 tests:

- [ ] `record_formula_usage()` — Record formula application as experience (lines 120-180)
- [ ] `update_experience_feedback()` — Update experience with human feedback (lines 182-239)
- [ ] `boost_experience_confidence()` — Boost confidence on successful reuse (lines 241-294)
- [ ] `get_experience_statistics()` — Get learning health statistics (lines 296-350)
- [ ] `update_fact_verification()` — Update fact verification status (lines 385-414)
- [ ] `list_all_facts()` — List all facts with optional filters (lines 459-493)
- [ ] `get_fact_by_id()` — Get single fact by ID (lines 504-529)
- [ ] `delete_fact()` — Soft delete fact (lines 541-543)
- [ ] `bulk_record_facts()` — Bulk record multiple facts (lines 553-557)
- [ ] `archive_session_to_cold_storage()` — Archive chat session to LanceDB (lines 565-604)
- [ ] `recall_experiences()` — Multi-source memory aggregation (lines 622-827)
- [ ] `_extract_canvas_insights()` — Extract patterns from canvas context (lines 856-929)

## Partial Coverage Methods

The following methods have partial coverage:

- [x] `__init__()` — 100% covered (4/4 lines) ✅
- [x] `_ensure_tables()` — 88% covered (7/8 lines) - Missing: error handling
- [x] `record_experience()` — 100% covered (3/3 lines) ✅
- [x] `record_business_fact()` — 100% covered (3/3 lines) ✅
- [x] `get_relevant_business_facts()` — 70% covered (7/10 lines) - Missing: error handling, empty results

## HIGH Priority Gaps (Core Multi-Source Memory)

1. **recall_experiences() — Main Orchestration** (lines 622-827, 84 missing lines)
   - Features: Multi-source aggregation (experiences, knowledge, formulas, conversations, episodes)
   - Tests needed:
     - Experience retrieval with role filtering
     - Knowledge graph context retrieval
     - Formula search and hot fallback
     - Conversation retrieval
     - Episode retrieval with canvas/feedback enrichment
     - Canvas insights extraction
   - Estimated impact: +60 lines (covering main orchestration paths)
   - Complexity: HIGH (230-line method with multiple data sources)

2. **archive_session_to_cold_storage()** (lines 565-604, 16 missing lines)
   - Features: Postgres to LanceDB archival
   - Tests needed:
     - Successful session archival
     - Empty session handling
     - Database error handling
   - Estimated impact: +16 lines

3. **get_experience_statistics()** (lines 296-350, 26 missing lines)
   - Features: Learning health metrics
   - Tests needed:
     - Overall statistics (no filters)
     - Agent-specific statistics
     - Role-specific statistics
   - Estimated impact: +26 lines

4. **list_all_facts()** (lines 459-493, 14 missing lines)
   - Features: List all facts with optional filters
   - Tests needed:
     - List all facts
     - Filter by verification status
     - Filter by domain
     - Pagination support
   - Estimated impact: +14 lines

5. **get_fact_by_id()** (lines 504-529, 10 missing lines)
   - Features: Get single fact by ID
   - Tests needed:
     - Successful retrieval
     - Not found error
   - Estimated impact: +10 lines

## MEDIUM Priority Gaps (Experience Lifecycle)

1. **update_experience_feedback()** (lines 182-239, 20 missing lines)
   - Features: Human feedback integration
   - Tests needed:
     - Successful feedback update
     - Experience not found
     - Confidence recalculation (60% old + 40% new)
   - Estimated impact: +20 lines

2. **boost_experience_confidence()** (lines 241-294, 19 missing lines)
   - Features: Confidence boost on successful reuse
   - Tests needed:
     - Successful confidence boost
     - Cap at 1.0 (max confidence)
     - Boost count tracking
     - Experience not found
   - Estimated impact: +19 lines

3. **update_fact_verification()** (lines 385-414, 15 missing lines)
   - Features: Fact verification status update
   - Tests needed:
     - Successful status update
     - Fact not found
     - Status text replacement
   - Estimated impact: +15 lines

4. **delete_fact()** (lines 541-543, 1 missing line)
   - Features: Soft delete fact
   - Tests needed:
     - Successful soft delete
     - Verify deleted facts filtered
   - Estimated impact: +1 line

5. **bulk_record_facts()** (lines 553-557, 5 missing lines)
   - Features: Bulk record multiple facts
   - Tests needed:
     - Successful bulk record
     - Empty list handling
     - Partial failure handling
   - Estimated impact: +5 lines

## LOW Priority Gaps (Specialized Features)

1. **record_formula_usage()** (lines 120-180, 4 missing lines)
   - Features: Formula application tracking
   - Tests needed:
     - Successful formula usage record
     - Metadata construction (formula_id, formula_name, inputs, result)
   - Estimated impact: +4 lines

2. **_extract_canvas_insights()** (lines 856-929, 33 missing lines)
   - Features: Canvas pattern extraction
   - Tests needed:
     - Canvas type counting
     - User action tracking
     - High-engagement canvas detection
     - Interaction pattern analysis
   - Estimated impact: +33 lines
   - Complexity: HIGH (73-line helper method)

3. **get_relevant_business_facts() — Error Paths** (lines 440-442, 3 missing lines)
   - Features: Vector search error handling
   - Tests needed:
     - Empty search results
     - Vector search error handling
   - Estimated impact: +3 lines

4. **_ensure_tables() — Error Handling** (line 68, 1 missing line)
   - Features: Database error handling
   - Tests needed:
     - Database connection error
   - Estimated impact: +1 line

## Test Estimates

| Priority | Tests Needed | Line Impact | Cumulative % |
|----------|--------------|-------------|--------------|
| HIGH | 15 tests | +126 lines | ~62% |
| MEDIUM | 14 tests | +60 lines | ~80% |
| LOW | 6 tests | +41 lines | ~93% |

**Total Estimated Tests**: 35 tests (3 existing from Plan 01 + 35 new = 38 total)
**Projected Coverage**: ~62% with HIGH priority only (exceeds 60% target)

## Recommended Test Order for Plan 03

### HIGH Priority (Core Multi-Source Memory) - Target: 62%

1. recall_experiences basic orchestration (HIGH) - +10 lines
2. recall_experiences role filtering (HIGH) - +10 lines
3. recall_experiences knowledge retrieval (HIGH) - +10 lines
4. recall_experiences formula search (HIGH) - +10 lines
5. recall_experiences conversation retrieval (HIGH) - +10 lines
6. recall_experiences episode retrieval (HIGH) - +10 lines
7. archive_session_to_cold_storage success (HIGH) - +8 lines
8. archive_session_to_cold_storage empty session (HIGH) - +4 lines
9. archive_session_to_cold_storage error handling (HIGH) - +4 lines
10. get_experience_statistics overall (HIGH) - +8 lines
11. get_experience_statistics agent-specific (HIGH) - +9 lines
12. get_experience_statistics role-specific (HIGH) - +9 lines
13. list_all_facts all facts (HIGH) - +4 lines
14. list_all_facts with filters (HIGH) - +5 lines
15. get_fact_by_id success (HIGH) - +5 lines

### MEDIUM Priority (Experience Lifecycle) - Target: 80%

16. update_experience_feedback success (MEDIUM) - +7 lines
17. update_experience_feedback not found (MEDIUM) - +7 lines
18. update_experience_feedback confidence recalc (MEDIUM) - +6 lines
19. boost_experience_confidence success (MEDIUM) - +5 lines
20. boost_experience_confidence cap at 1.0 (MEDIUM) - +5 lines
21. boost_experience_confidence not found (MEDIUM) - +5 lines
22. boost_experience_confidence boost count (MEDIUM) - +4 lines
23. update_fact_verification success (MEDIUM) - +5 lines
24. update_fact_verification not found (MEDIUM) - +5 lines
25. update_fact_verification status replacement (MEDIUM) - +5 lines
26. delete_fact success (MEDIUM) - +1 line
27. bulk_record_facts success (MEDIUM) - +3 lines
28. bulk_record_facts empty list (MEDIUM) - +2 lines
29. bulk_record_facts partial failure (MEDIUM) - +2 lines

### LOW Priority (Specialized Features) - Optional for 60% target

30. record_formula_usage success (LOW) - +4 lines
31. _extract_canvas_insights canvas types (LOW) - +8 lines
32. _extract_canvas_insights user actions (LOW) - +8 lines
33. _extract_canvas_insights high-engagement (LOW) - +9 lines
34. _extract_canvas_insights interaction patterns (LOW) - +8 lines
35. get_relevant_business_facts empty results (LOW) - +2 lines
36. get_relevant_business_facts error handling (LOW) - +1 line
37. _ensure_tables error handling (LOW) - +1 line

**Quick Win Path**: Tests 1-15 (HIGH priority only) = +126 lines = 62.35% coverage (exceeds 60% target)
**Recommended Path**: Tests 1-29 (HIGH + MEDIUM) = +186 lines = 80.42% coverage (exceeds 60% by 20%)

**Remaining tests** (30-37) for near-full coverage can be added in future phases.

## Missing Line Details

### Function-Level Coverage Breakdown

**100% Covered ✅**:
- `__init__()`: 100% (4/4 lines)
- `record_experience()`: 100% (3/3 lines)
- `record_business_fact()`: 100% (3/3 lines)

**Partial Coverage**:
- `_ensure_tables()`: 88% (7/8 lines) - Missing: error handling (line 68)
- `get_relevant_business_facts()`: 70% (7/10 lines) - Missing: error handling (lines 440-442)

**0% Coverage (Priority Order)**:
- `delete_fact()`: 0% (0/1 lines) - Quick win
- `record_formula_usage()`: 0% (0/4 lines) - Low priority
- `bulk_record_facts()`: 0% (0/5 lines) - Medium priority
- `get_fact_by_id()`: 0% (0/10 lines) - High priority
- `update_fact_verification()`: 0% (0/15 lines) - Medium priority
- `list_all_facts()`: 0% (0/14 lines) - High priority
- `update_experience_feedback()`: 0% (0/20 lines) - Medium priority
- `boost_experience_confidence()`: 0% (0/19 lines) - Medium priority
- `get_experience_statistics()`: 0% (0/26 lines) - High priority
- `archive_session_to_cold_storage()`: 0% (0/16 lines) - High priority
- `recall_experiences()`: 0% (0/84 lines) - High priority (complex)
- `_extract_canvas_insights()`: 0% (0/33 lines) - Low priority (helper)

### Specific Missing Lines by Method

**_ensure_tables() (line 68)**:
- 68: Database error handling

**record_formula_usage() (lines 149, 156, 171, 173)**:
- 149: Metadata construction
- 156: Formula usage record creation
- 171: DB session add
- 173: Commit and return

**update_experience_feedback() (20 lines: 197-239)**:
- 197, 200: Experience lookup
- 206-208: Not found error
- 211-218: Feedback update logic
- 213, 215-216: Confidence recalculation (60% old + 40% new)
- 221-223: Apply feedback delta
- 231, 232: DB update
- 234, 235: Commit and return

**boost_experience_confidence() (19 lines: 250-294)**:
- 250, 252: Experience lookup
- 258-260: Not found error
- 263-264: Confidence boost calculation
- 267: Cap at 1.0
- 269-271: Update confidence and boost count
- 274: DB update
- 282: Commit
- 287: Update hot storage
- 289-290: Return boosted experience

**get_experience_statistics() (26 lines: 304-350)**:
- 304, 305: Query construction
- 311-315: Agent filter application
- 317, 318: Role filter application
- 321-324: Base statistics calculation
- 326-331: Confidence aggregation
- 333-335: Feedback aggregation
- 337, 348: Result construction

**update_fact_verification() (15 lines: 387-414)**:
- 387, 388: Fact lookup
- 394-396: Not found error
- 397-398: Verification status update
- 400: Status text replacement
- 402: DB update
- 409-414: Commit and return

**get_relevant_business_facts() (3 missing lines: 440-442)**:
- 440: Empty results handling
- 441: Vector search error handling
- 442: Return empty list on error

**list_all_facts() (14 lines: 461-493)**:
- 461, 463: Query construction
- 469-471: Verification status filter
- 474-477: Domain filter
- 479: Ordering
- 490-493: Execution and return

**get_fact_by_id() (10 lines: 505-529)**:
- 505, 506: Fact lookup
- 512-515: Not found error
- 526-529: Return fact

**delete_fact() (1 line: 541)**:
- 541: Soft delete execution

**bulk_record_facts() (5 lines: 553-557)**:
- 553-556: Loop and record each fact
- 557: Return count

**archive_session_to_cold_storage() (16 lines: 565-604)**:
- 565-567: Session retrieval
- 572-574: Empty session check
- 577-578: Message serialization
- 586: LanceDB archival
- 594: Error handling
- 598-604: Commit and return

**recall_experiences() (84 lines: 622-827)**:
- 622-629: Query setup and filters
- 631-634: Experience retrieval
- 637-638: Role filtering
- 640: Confidence boost
- 645-646: Knowledge graph retrieval
- 649, 650: Knowledge context
- 652: Formula search
- 668-669: Formula hot storage fallback
- 673: Conversation retrieval
- 681-686: Message serialization
- 690-693: Episode retrieval
- 696: Canvas/feedback enrichment
- 702: Canvas insights extraction
- 715-722: Context synthesis
- 727, 729-730: Result construction
- 739-750: Answer generation (with LLM)
- 754: Return result
- 762-765: Error handling
- 768-774: Fallback to experiences only
- 776-778: Return experiences
- 783-792: Synchronous answer fallback
- 795-798: Final error fallback
- 801-802: Return empty context

**_extract_canvas_insights() (33 lines: 856-929)**:
- 856: Canvas type counting
- 868-871: User action tracking
- 873-875: High-engagement detection
- 877-878: Interaction patterns
- 881-894: Pattern aggregation
- 895-929: Insights construction

## Execution Notes

- Current coverage: 24.40% (81/332 lines)
- Target: 60% = 199.2 lines → need +118 lines
- Quick win (HIGH priority only): +126 lines = 62.35% (exceeds 60% target)
- Recommended (HIGH + MEDIUM): +186 lines = 80.42% (exceeds target by 20%)
- Full coverage: +227 lines = 93% (all 37 tests)

**Strategy**:
1. Focus on HIGH priority methods (recall_experiences, archive_session, statistics, CRUD operations) - 15 tests
2. Add MEDIUM priority experience lifecycle methods (feedback, confidence, verification) - 14 tests
3. Defer LOW priority specialized features (formula tracking, canvas insights) for future phases

**Note**: recall_experiences() is a complex 230-line method with multiple data sources. Split into 6 focused tests covering each data source (experiences, knowledge, formulas, conversations, episodes, canvas insights).
