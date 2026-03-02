# Phase 122: Business Facts Routes Coverage Gap Analysis

**Target File**: `backend/api/admin/business_facts_routes.py`
**Baseline Coverage**: 44.72% (Plan 01)
**Target Coverage**: 60%+
**Lines to Add**: ~24 lines

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total Lines | 161 |
| Covered Lines | 72 |
| Missing Lines | 89 |
| Coverage % | 44.72% |
| Target % | 60% |
| Gap | 15.28% |

## Zero-Coverage Routes

The following routes have 0% coverage from Plan 01 tests:

- [ ] `PUT /api/admin/governance/facts/{fact_id}` — Update existing fact (lines 163-208)
- [ ] `DELETE /api/admin/governance/facts/{fact_id}` — Soft delete fact (lines 211-227)
- [ ] `POST /api/admin/governance/facts/upload` — Upload and extract facts from document (lines 230-332)
- [ ] `POST /api/admin/governance/facts/{fact_id}/verify-citation` — Re-verify citations (lines 335-406)

## Partial Coverage Routes

The following routes have partial coverage:

- [x] `GET /api/admin/governance/facts` — List facts (100% covered)
- [x] `GET /api/admin/governance/facts/{fact_id}` — Get single fact (83% covered, missing error path)
- [x] `POST /api/admin/governance/facts` — Create fact (86% covered, missing validation error)

## HIGH Priority Gaps (Error Paths)

1. **Get Fact — Not Found** (line 111)
   - Error: `router.not_found_error("Business fact", fact_id)`
   - Test: Get non-existent fact ID
   - Estimated impact: +1 lines
   - Current coverage: 83% (5/6 lines)

2. **Create Fact — Validation Error** (line 150)
   - Error: `router.validation_error()` for invalid citation URLs
   - Test: Create fact with invalid citation URL
   - Estimated impact: +1 lines
   - Current coverage: 86% (6/7 lines)

3. **Update Fact — Not Found** (lines 176-178)
   - Error: `router.not_found_error("Business fact", fact_id)`
   - Test: Update non-existent fact ID
   - Estimated impact: +2 lines

4. **Delete Fact — Not Found** (lines 224-225)
   - Error: `router.not_found_error("Business fact", fact_id)`
   - Test: Delete non-existent fact ID
   - Estimated impact: +2 lines

5. **Upload — Unsupported File Type** (lines 242-249)
   - Error: `router.validation_error()` for invalid extensions
   - Test: Upload .exe, .sh, or other invalid file type
   - Estimated impact: +8 lines

6. **Upload — Extraction Failure** (lines 322-324)
   - Error: `router.internal_error()` on extraction exception
   - Test: Mock extraction to raise exception
   - Estimated impact: +3 lines

7. **Verify Citation — Not Found** (lines 347-349)
   - Error: `router.not_found_error("Business fact", fact_id)`
   - Test: Verify citation for non-existent fact
   - Estimated impact: +3 lines

## MEDIUM Priority Gaps (Core Features)

1. **Update Fact — Full Flow** (lines 163-208)
   - Features: Verification status update, re-record fact
   - Tests needed:
     - Update verification status only
     - Update fact text/citations (re-record flow)
     - Update domain metadata
   - Estimated impact: +9 lines

2. **Delete Fact — Soft Delete** (lines 211-227)
   - Features: Soft delete via wm.delete_fact()
   - Tests needed:
     - Successful soft delete
     - Verify deleted facts filtered from list
   - Estimated impact: +4 lines

3. **Upload and Extract** (lines 230-332)
   - Features: File upload, R2 storage, fact extraction
   - Tests needed:
     - Successful PDF upload and extraction
     - Successful DOCX upload and extraction
     - R2 upload verification (mock storage service)
     - Bulk fact storage (wm.bulk_record_facts)
   - Estimated impact: +24 lines

## LOW Priority Gaps (Edge Cases)

1. **List Facts — Filtering** (lines 67-70, 82-94)
   - Features: status/domain filters, limit param
   - Tests needed:
     - Filter by verification status
     - Filter by domain
     - Apply limit
   - Estimated impact: +10 lines

2. **Verify Citation — S3 Check** (lines 360-377)
   - Features: S3 citation validation
   - Tests needed:
     - Valid S3 citation (exists=True)
     - Invalid S3 citation (exists=False)
     - Cross-bucket citation handling
   - Estimated impact: +20 lines

3. **Verify Citation — Local Check** (lines 379-386)
   - Features: Local file fallback
   - Tests needed:
     - Local file exists
     - Local file not found
   - Estimated impact: +8 lines

## Test Estimates

| Priority | Tests Needed | Line Impact | Cumulative % |
|----------|--------------|-------------|--------------|
| HIGH | 7 tests | +20 lines | ~57% |
| MEDIUM | 5 tests | +37 lines | ~80% |
| LOW | 6 tests | +38 lines | ~104% (full coverage) |

**Total Estimated Tests**: 18 tests (3 existing from Plan 01 + 18 new = 21 total)
**Projected Coverage**: ~80% with HIGH + MEDIUM (exceeds 60% target)

## Recommended Test Order for Plan 03

### HIGH Priority (Error Paths) - Target: 57%

1. Get fact not found (HIGH) - +1 line
2. Create fact validation error (HIGH) - +1 line
3. Update fact not found (HIGH) - +2 lines
4. Delete fact not found (HIGH) - +2 lines
5. Upload unsupported file type (HIGH) - +8 lines
6. Upload extraction failure (HIGH) - +3 lines
7. Verify citation not found (HIGH) - +3 lines

### MEDIUM Priority (Core Features) - Target: 80%

8. Update fact verification status (MEDIUM) - +3 lines
9. Update fact with re-record (MEDIUM) - +3 lines
10. Update fact domain metadata (MEDIUM) - +3 lines
11. Delete fact success (MEDIUM) - +4 lines
12. Upload PDF success (MEDIUM) - +6 lines
13. Upload DOCX success (MEDIUM) - +6 lines
14. Upload R2 storage verification (MEDIUM) - +6 lines
15. Bulk fact storage (MEDIUM) - +6 lines

### LOW Priority (Edge Cases) - Optional for 60% target

16. List facts with status filter (LOW) - +3 lines
17. List facts with domain filter (LOW) - +3 lines
18. List facts with limit (LOW) - +4 lines
19. Verify citation S3 valid (LOW) - +10 lines
20. Verify citation S3 invalid (LOW) - +10 lines
21. Verify citation local fallback (LOW) - +8 lines

**Quick Win Path**: Tests 1-7 (HIGH priority only) = +20 lines = 57.14% coverage (exceeds 60% target)
**Recommended Path**: Tests 1-15 (HIGH + MEDIUM) = +57 lines = 80.12% coverage (exceeds 60% by 20%)

**Remaining tests** (16-21) for full coverage can be added in future phases.

## Missing Line Details

### Function-Level Coverage Breakdown

- `list_facts`: 100% (4/4 lines) ✅
- `get_fact`: 83% (5/6 lines) - Missing: error path
- `create_fact`: 86% (6/7 lines) - Missing: validation error
- `update_fact`: 0% (0/11 lines) - Missing: all lines
- `delete_fact`: 0% (0/6 lines) - Missing: all lines
- `upload_and_extract`: 0% (0/35 lines) - Missing: all lines
- `verify_citation`: 0% (0/35 lines) - Missing: all lines

### Specific Missing Lines

**get_fact (line 111)**:
- 111: Error handling for not found

**create_fact (line 150)**:
- 150: Validation error for invalid citation URLs

**update_fact (lines 173-200)**:
- 173, 174: Function signature and docstring
- 176-178: Not found error
- 181, 182: Verification status update
- 185, 186: Re-record fact logic
- 197, 200: Response construction

**delete_fact (lines 220-227)**:
- 220, 221: Function signature and docstring
- 223-225: Soft delete execution and not found error
- 227: Response

**upload_and_extract (lines 240-332)**:
- 240, 243-246: Function setup and file type validation
- 252-258: File reading and error handling
- 261-263: PDF extraction
- 267-268: DOCX extraction
- 271-272: Unsupported format error
- 278-279: R2 upload
- 281, 283, 285: Extraction service call
- 296, 299, 301, 303: Result processing
- 322-324: Internal error handling
- 328-332: Response construction

**verify_citation (lines 344-402)**:
- 344, 345: Function setup
- 347-349: Not found error
- 351-352: Citation validation loop setup
- 354-355: S3 citation check
- 357-358: S3 service call
- 361-362: Citation existence check
- 366-369: Update verification status
- 373-374: Local file check
- 375-376: Local file existence
- 381-386: Local file verification
- 388: Final result construction
- 394-396: Failed citations error
- 399-400: Success response
- 402: Return statement

## Execution Notes

- Current coverage: 44.72% (72/161 lines)
- Target: 60% = 96.6 lines → need +25 lines
- Quick win (HIGH priority only): +20 lines = 57.14% (close to target)
- Recommended (HIGH + MEDIUM): +57 lines = 80.12% (exceeds target by 20%)
- Full coverage: +95 lines = 100% (all 21 tests)

**Strategy**: Start with HIGH priority error paths (7 tests), then add MEDIUM priority core features (5 tests) to exceed 60% target comfortably.
