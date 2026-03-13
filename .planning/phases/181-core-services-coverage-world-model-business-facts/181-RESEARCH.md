# Phase 181 Research: Core Services Coverage (World Model & Business Facts)

**Phase:** 181 - Core Services Coverage (World Model & Business Facts)
**Date:** March 12, 2026
**Goal:** Achieve 75%+ line coverage on World Model and Business Facts system

---

## Executive Summary

This research document analyzes the World Model & Business Facts system to design a comprehensive test coverage strategy for Phase 181. The target files are:

1. **core/agent_world_model.py** (929 lines) - Multi-source memory aggregation, episodic learning, business facts
2. **api/admin/business_facts_routes.py** (407 lines) - REST API for business facts CRUD with JIT citation verification
3. **core/policy_fact_extractor.py** (88 lines) - Document fact extraction (currently stub)
4. **core/graphrag_engine.py** (642 lines) - PostgreSQL-backed knowledge graph with recursive CTE traversal

**Current State:** Partial test coverage exists from Phase 178 (admin skill routes tests). Two test files already exist:
- `backend/tests/test_world_model.py` (1,511 lines) - Comprehensive unit tests
- `backend/tests/test_world_model_integration.py` (730 lines) - Integration tests
- `backend/tests/test_business_facts_routes.py` (414 lines) - Basic API tests

**Key Challenge:** Significant untested code paths in LanceDB integration, GraphRAG traversal, JIT citation verification, and complex multi-source recall orchestration.

---

## Architecture Overview

### 1. Agent World Model Service (`agent_world_model.py`)

**Purpose:** Central memory aggregation system for AI agents

**Core Components:**

#### Data Models
```python
class AgentExperience(BaseModel):
    - Agent learning from task execution
    - Confidence scoring (0.0-1.0)
    - Feedback integration (thumbs_up_down, rating, feedback_score)
    - TRACE metrics (step_efficiency, metadata_trace)

class BusinessFact(BaseModel):
    - Verified knowledge with citations
    - JIT citation verification (R2/S3 checks)
    - Three verification states: unverified, verified, outdated
```

#### Service Architecture
```
WorldModelService
├── _ensure_tables()          # LanceDB table initialization
├── record_experience()        # Agent learning storage
├── record_business_fact()     # Knowledge base storage
├── update_experience_feedback() # Feedback blending (60% old + 40% new)
├── boost_experience_confidence() # Reuse-based learning
├── get_experience_statistics() # Aggregation metrics
├── get_relevant_business_facts() # Vector search
├── list_all_facts()           # Filtering (status, domain)
├── get_fact_by_id()           # ID lookup
├── update_fact_verification() # Status updates
├── delete_fact()              # Soft delete
├── bulk_record_facts()        # Batch operations
├── record_formula_usage()     # Formula application tracking
├── archive_session_to_cold_storage() # PostgreSQL → LanceDB migration
├── recall_experiences()       # Multi-source memory orchestration (7 sources)
└── _extract_canvas_insights() # Episode enrichment analysis
```

#### Multi-Source Recall System (`recall_experiences`)
The most complex method orchestrates 7 memory sources:

1. **Experiences Table** (LanceDB vector search) - Role-scoped, confidence-filtered
2. **Knowledge Documents** (LanceDB) - General knowledge base
3. **Knowledge Graph** (GraphRAG) - Entity relationships
4. **Formulas** (Formula memory + PostgreSQL hot fallback) - Business logic
5. **Conversations** (PostgreSQL) - Recent chat history
6. **Business Facts** (LanceDB) - Trusted knowledge with citations
7. **Episodes** (PostgreSQL + enrichment) - Canvas/feedback context

**Role-Based Access Control:**
- Creator-scoped: Agent's own experiences
- Role-scoped: Experiences from same agent category (Finance, Sales, Engineering)
- Filters out: Low-confidence failures (<0.8 confidence AND "failed" outcome)

---

### 2. Business Facts Routes (`business_facts_routes.py`)

**Purpose:** Admin REST API for business facts management with JIT citation verification

**Endpoints (7 total):**

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| GET | `/api/admin/governance/facts` | List all facts with filters | Tested (Phase 178) |
| POST | `/api/admin/governance/facts` | Create new fact | Tested (Phase 178) |
| GET | `/api/admin/governance/facts/{id}` | Get specific fact | Tested (Phase 178) |
| PUT | `/api/admin/governance/facts/{id}` | Update fact | Partially tested |
| DELETE | `/api/admin/governance/facts/{id}` | Soft delete | Tested (Phase 178) |
| POST | `/api/admin/governance/facts/upload` | Upload & extract | Partially tested |
| POST | `/api/admin/governance/facts/{id}/verify-citation` | JIT verification | **NOT TESTED** |

**Key Features:**
- **RBAC:** Requires `UserRole.ADMIN` (enforced via `require_role`)
- **File Upload:** Supports PDF, DOCX, TXT, PNG, TIFF, JPEG, JPG
- **R2/S3 Integration:** Uploads to persistent storage with citation URIs
- **Fact Extraction:** Calls `PolicyFactExtractor.extract_facts_from_document()`
- **Citation Verification:** Real-time R2/S3 existence checks

**Current Test Gaps:**
1. Upload endpoint file validation (tested)
2. Upload endpoint extraction failure (tested)
3. Upload endpoint success path (NOT tested)
4. Citation verification S3 checks (NOT tested)
5. Citation verification local fallback (NOT tested)
6. Update fact with all fields (partial)
7. Cross-bucket citation verification (NOT tested)

---

### 3. Policy Fact Extractor (`policy_fact_extractor.py`)

**Purpose:** Extract business facts from policy documents

**Current Status:** **STUB IMPLEMENTATION** (88 lines)

```python
class PolicyFactExtractor:
    async def extract_facts_from_document(
        self, document_path: str, user_id: str
    ) -> ExtractionResult:
        # TODO: Implement actual document parsing
        # Returns empty result
        return ExtractionResult(facts=[], extraction_time=0.0)
```

**Document Types Supported:** PDF, DOCX, DOC, TXT, PNG, TIFF, JPEG, JPG

**Test Strategy:** Focus on API integration (routes call this), not internal logic (not implemented yet)

---

### 4. GraphRAG Engine (`graphrag_engine.py`)

**Purpose:** PostgreSQL-backed knowledge graph with stateless traversal

**Architecture:**
- **Storage:** PostgreSQL tables (GraphNode, GraphEdge, GraphCommunity, CommunityMembership)
- **Traversal:** Recursive CTEs (depth-limited BFS)
- **Search Modes:** Local (entity neighborhood), Global (community summaries)
- **Extraction:** LLM-based (GPT-4o-mini) OR pattern-based fallback

**Core Methods:**

```python
class GraphRAGEngine:
    # LLM Extraction
    _llm_extract_entities_and_relationships()
    _pattern_extract_entities_and_relationships() # Fallback
    ingest_document() # Orchestrator

    # Write Operations
    add_entity() # Upsert to GraphNode
    add_relationship() # Insert to GraphEdge
    ingest_structured_data() # Batch ingestion

    # Read Operations
    local_search() # Recursive CTE traversal
    global_search() # Community summaries
    query() # Unified entry point (auto mode detection)
    get_context_for_ai() # AI prompt formatting
    enqueue_reindex_job() # Background re-indexing
```

**Pattern Extraction Fallback:**
When LLM unavailable, extracts 8 entity types via regex:
1. Email addresses
2. URLs
3. Phone numbers (US format)
4. Dates (ISO, US, textual)
5. Currency amounts
6. File paths
7. IP addresses
8. UUIDs

**Relationship Patterns:**
- "X is Y" → affiliated_with
- "X reports to Y" → reports_to
- "X located in Y" → located_in

**Current Test Coverage:** **ZERO TESTS EXIST**

---

## LanceDB Integration Analysis

### LanceDB Handler (`lancedb_handler.py` - 1,390 lines)

**Purpose:** Vector database for semantic search and episodic memory

**Key Features:**
- **Dual Vector Storage:** 1024-dim (Sentence Transformers) + 384-dim (FastEmbed)
- **Lazy Loading:** Prevents Windows import hangs
- **Workspace Isolation:** Physical separation via directory structure
- **Embedding Providers:** OpenAI (BYOK), Sentence Transformers, Mock fallback

**Schema:**
```python
# Standard Document Table
Table {
    id: string
    user_id: string
    workspace_id: string
    text: string
    source: string
    metadata: string (JSON)
    created_at: string
    vector: list[float32] (1024 or 1536)
    vector_fastembed: list[float32] (384) # Optional
}

# Knowledge Graph Table
Table {
    from_id: string
    to_id: string
    type: string
    vector: list[float32]
    vector_fastembed: list[float32] # Optional
}
```

**Test Challenges:**
1. **Lazy Loading:** Tests must trigger `_ensure_db()` and `_ensure_embedder()`
2. **Mock Embedder:** Deterministic hash-based vectors for consistency
3. **PyArrow Schema:** Complex nested structures
4. **Pandas Dependency:** `search()` returns `to_pandas()` results
5. **S3/R2 Storage:** Remote storage mocking for `check_exists()`

---

## Current Test Coverage Analysis

### Existing Test Files

#### 1. `backend/tests/test_world_model.py` (1,511 lines)

**Coverage:** ~60% estimated (based on test count vs. complexity)

**Test Classes:**
- `TestRecordExperience` (2 tests) - Basic success path
- `TestRecordBusinessFact` (1 test) - Basic success path
- `TestGetRelevantBusinessFacts` (1 test) - Vector search
- `TestListAllFacts` (1 test) - Empty list handling
- `TestGetFactById` (1 test) - Success path
- `TestUpdateFactVerification` (1 test) - Status update
- `TestRecallExperiences` (7 tests) - Multi-source orchestration
- `TestUpdateExperienceFeedback` (3 tests) - Confidence blending
- `TestBoostExperienceConfidence` (3 tests) - Confidence capping
- `TestGetExperienceStatistics` (4 tests) - Aggregation metrics
- `TestArchiveSessionToColdStorage` (2 tests) - Error paths
- `TestWorldModelEdgeCases` (3 tests) - Formula usage, bulk facts

**Gaps Identified:**
1. **Error handling:** LanceDB connection failures, embedding failures
2. **Edge cases:** Empty metadata, malformed datetime strings, None handling
3. **Canvas insights:** `_extract_canvas_insights()` not tested (lines 837-929)
4. **Formula fallback:** PostgreSQL hot fallback in recall_experiences (line 718-740)
5. **Episode enrichment:** Canvas/feedback context fetch failures (line 801-812)

#### 2. `backend/tests/test_world_model_integration.py` (730 lines)

**Coverage:** ~40% estimated (focuses on success paths)

**Test Classes:**
- `TestExperienceRecording` (2 tests) - Basic record operations
- `TestFormulaUsageRecording` (1 test) - Formula tracking
- `TestExperienceFeedbackUpdate` (2 tests) - Feedback updates
- `TestConfidenceBoosting` (2 tests) - Confidence operations
- `TestExperienceStatistics` (2 tests) - Stats aggregation
- `TestBusinessFactRecording` (2 tests) - Fact storage
- `TestBusinessFactRetrieval` (2 tests) - Search operations
- `TestBusinessFactListing` (2 tests) - Filtering
- `TestBusinessFactRetrievalById` (2 tests) - ID lookup
- `TestBusinessFactDeletion` (1 test) - Soft delete
- `TestBusinessFactBulkOperations` (1 test) - Batch operations
- `TestFactVerificationUpdate` (2 tests) - Status updates

**Gaps Identified:**
1. **No error path testing** (all tests mock success)
2. **No LanceDB integration** (fully mocked handler)
3. **No GraphRAG integration** (patched out)
4. **No Formula memory integration** (patched out)
5. **No Episode retrieval integration** (patched out)

#### 3. `backend/tests/test_business_facts_routes.py` (414 lines)

**Coverage:** ~50% estimated (7 route endpoints)

**Test Classes:**
- `TestListFacts` (1 test) - Empty list
- `TestCreateFact` (1 test) - Success path
- `TestGetFact` (1 test) - Success path
- `TestUpdateFact` (2 tests) - Not found, verification status only
- `TestDeleteFact` (2 tests) - Not found, success
- `TestUploadAndExtract` (2 tests) - Unsupported file type, extraction failure
- `TestVerifyCitation` (1 test) - Not found only

**Gaps Identified:**
1. **Upload success path** NOT tested
2. **Citation verification S3 checks** NOT tested
3. **Citation verification local fallback** NOT tested
4. **Update fact with all fields** NOT tested
5. **Filter by domain/status** NOT tested in list endpoint
6. **File type validation** incomplete (only .exe tested)

---

## Test Design Strategy

### 1. World Model Service Tests (Unit)

**File:** `backend/tests/test_world_model.py` (expand to 2,000+ lines)

#### New Test Classes

##### `TestRecordExperienceErrors`
```python
- test_record_experience_lancedb_connection_failure
- test_record_experience_embedding_failure
- test_record_experience_with_none_metadata
- test_record_experience_with_empty_task_type
- test_record_experience_with_special_characters_in_text
```

##### `TestRecordBusinessFactErrors`
```python
- test_record_business_fact_with_empty_citations
- test_record_business_fact_with_empty_fact_text
- test_record_business_fact_with_malformed_metadata
- test_record_business_fact_lancedb_add_failure
```

##### `TestUpdateExperienceFeedbackErrors`
```python
- test_update_feedback_experience_not_found
- test_update_feedback_lancedb_search_failure
- test_update_feedback_with_extreme_scores(-1.0, 1.0)
- test_update_feedback_confidence_formula_validation
```

##### `TestBoostExperienceConfidenceErrors`
```python
- test_boost_confidence_experience_not_found
- test_boost_confidence_with_zero_boost_amount
- test_boost_confidence_with_negative_boost_amount
- test_boost_confidence_at_max_already(1.0)
```

##### `TestGetExperienceStatisticsErrors`
```python
- test_get_statistics_lancedb_search_failure
- test_get_statistics_with_empty_results
- test_get_statistics_with_malformed_metadata
- test_get_statistics_case_insensitive_role_filtering
```

##### `TestCanvasInsightsExtraction`
```python
- test_extract_insights_with_empty_canvas_context
- test_extract_insights_with_high_engagement_canvases
- test_extract_insheets_interaction_patterns
- test_extract_insights_with_missing_canvas_types
- test_extract_insights_with_no_feedback_data
```

##### `TestRecallExperiencesErrorHandling`
```python
- test_recall_with_lancedb_connection_failure
- test_recall_with_graphrag_unavailable
- test_recall_with_formula_manager_unavailable
- test_recall_with_database_session_failure
- test_recall_with_episode_service_failure
- test_recall_partial_failure_returns_empty_sources
```

##### `TestRecallExperiencesFormulaHotFallback`
```python
- test_recall_formula_fallback_activates_on_empty_search
- test_recall_formula_fallback_queries_postgres
- test_recall_formula_fallback_avoids_duplicates
- test_recall_formula_fallback_filters_by_domain
- test_recall_formula_fallback_database_error
```

##### `TestRecallExperiencesEpisodeEnrichment`
```python
- test_recall_episodes_canvas_context_fetch_success
- test_recall_episodes_feedback_context_fetch_success
- test_recall_episodes_canvas_fetch_failure_continues
- test_recall_episodes_feedback_fetch_failure_continues
- test_recall_episodes_with_empty_canvas_ids
- test_recall_episodes_with_empty_feedback_ids
```

##### `TestBulkRecordFactsErrors`
```python
- test_bulk_record_with_empty_list
- test_bulk_record_all_failures_returns_zero
- test_bulk_record_with_malformed_facts
- test_bulk_record_preserves_partial_success_order
```

##### `TestArchiveSessionErrors`
```python
- test_archive_session_database_connection_failure
- test_archive_session_with_malformed_messages
- test_archive_session_lancedb_add_failure
- test_archive_session_with_zero_messages
```

##### `TestRecordFormulaUsageErrors`
```python
- test_record_formula_usage_with_empty_inputs
- test_record_formula_usage_with_none_result
- test_record_formula_usage_lancedb_failure
- test_record_formula_usage_metadata_serialization
```

---

### 2. Business Facts Routes Tests (Integration)

**File:** `backend/tests/api/test_business_facts_routes.py` (expand to 1,500+ lines)

#### New Test Classes

##### `TestListFactsFilters`
```python
- test_list_facts_filter_by_status_verified
- test_list_facts_filter_by_status_unverified
- test_list_facts_filter_by_domain_finance
- test_list_facts_filter_by_domain_hr
- test_list_facts_combined_filters
- test_list_facts_excludes_deleted_status
- test_list_facts_custom_limit
```

##### `TestCreateFactValidation`
```python
- test_create_fact_with_empty_fact_text
- test_create_fact_with_empty_citations
- test_create_fact_with_long_fact_text(10000 chars)
- test_create_fact_with_special_characters
- test_create_fact_with_array_citations
- test_create_fact_lancedb_failure_returns_500
```

##### `TestUpdateFactAllFields`
```python
- test_update_fact_fact_field_only
- test_update_fact_citations_field_only
- test_update_fact_reason_field_only
- test_update_fact_domain_field_only
- test_update_fact_all_fields_together
- test_update_fact_preserves_created_at
- test_update_fact_with_empty_citations_array
```

##### `TestUploadAndExtractSuccess`
```python
- test_upload_pdf_file_success
- test_upload_docx_file_success
- test_upload_txt_file_success
- test_upload_png_file_success
- test_upload_with_custom_domain
- test_upload_storage_service_called
- test_upload_fact_extractor_called
- test_upload_bulk_record_facts_called
- test_upload_returns_extraction_response
- test_upload_temp_file_cleanup
```

##### `TestUploadAndExtractFileTypes`
```python
- test_upload_jpeg_file_success
- test_upload_tiff_file_success
- test_upload_jpg_file_success
- test_upload_doc_file_success
- test_upload_all_supported_extensions
```

##### `TestVerifyCitationS3`
```python
- test_verify_citation_s3_exists_true
- test_verify_citation_s3_exists_false
- test_verify_citation_s3_bucket_mismatch
- test_verify_citation_s3_check_exists_called
- test_verify_citation_updates_status_to_verified
- test_verify_citation_updates_status_to_outdated
- test_verify_citation_multiple_citations_mixed
```

##### `TestVerifyCitationLocalFallback`
```python
- test_verify_citation_local_fallback_exists
- test_verify_citation_local_fallback_not_exists
- test_verify_citation_local_fallback_multiple_paths
- test_verify_citation_non_s3_uri_uses_local
```

##### `TestVerifyCitationCrossBucket`
```python
- test_verify_citation_cross_bucket_parsing
- test_verify_citation_cross_bucket_exists
- test_verify_citation_cross_bucket_not_found
- test_verify_citation_malformed_s3_uri
```

##### `TestVerifyCitationErrors`
```python
- test_verify_citation_fact_not_found
- test_verify_citation_s3_check_exception
- test_verify_citation_local_check_exception
- test_verify_citation_verification_update_failure
```

---

### 3. Policy Fact Extractor Tests (Unit)

**File:** `backend/tests/test_policy_fact_extractor.py` (NEW, ~500 lines)

**Note:** Since implementation is a stub, tests focus on:
1. Method signature validation
2. Empty result handling
3. Future-proof interface

#### Test Classes

##### `TestPolicyFactExtractorInit`
```python
- test_init_default_workspace
- test_init_custom_workspace
- test_extractor_registry_returns_same_instance
```

##### `TestExtractFactsFromDocument`
```python
- test_extract_facts_returns_empty_list
- test_extract_facts_returns_zero_extraction_time
- test_extract_facts_with_nonexistent_file
- test_extract_facts_with_pdf_file
- test_extract_facts_with_txt_file
- test_extract_facts_logs_warning
```

##### `TestGetPolicyFactExtractor`
```python
- test_get_extractor_creates_new_instance
- test_get_extractor_returns_cached_instance
- test_get_extractor_different_workspaces
```

---

### 4. GraphRAG Engine Tests (Unit + Integration)

**File:** `backend/tests/test_graphrag_engine.py` (NEW, ~1,500+ lines)

#### Test Classes

##### `TestGraphRAGInit`
```python
- test_init_default_configuration
- test_llm_available_with_api_key
- test_llm_unavailable_without_api_key
```

##### `TestLLMExtraction`
```python
- test_llm_extract_entities_success
- test_llm_extract_relationships_success
- test_llm_extract_with_truncated_text(6000 char limit)
- test_llm_extract_with_json_response
- test_llm_extract_api_failure_returns_empty
- test_llm_extract_with_special_characters
```

##### `TestPatternExtraction`
```python
- test_pattern_extract_email_addresses
- test_pattern_extract_urls
- test_pattern_extract_phone_numbers
- test_pattern_extract_dates_iso_format
- test_pattern_extract_dates_us_format
- test_pattern_extract_dates_textual
- test_pattern_extract_currency_dollars
- test_pattern_extract_currency_euros
- test_pattern_extract_file_paths
- test_pattern_extract_ip_addresses
- test_pattern_extract_uuids
- test_pattern_extract_relationships_is
- test_pattern_extract_relationships_reports_to
- test_pattern_extract_relationships_located_in
- test_pattern_extract_deduplicates_entities
- test_pattern_extract_returns_empty_on_no_matches
```

##### `TestIngestDocument`
```python
- test_ingest_document_calls_llm_when_available
- test_ingest_document_falls_back_to_pattern_when_llm_unavailable
- test_ingest_document_with_no_extraction_returns_early
- test_ingest_document_calls_ingest_structured_data
```

##### `TestAddEntity`
```python
- test_add_entity_new_creates_node
- test_add_entity_existing_updates_description
- test_add_entity_existing_updates_properties
- test_add_entity_database_error_rollback
- test_add_entity_returns_entity_id
```

##### `TestAddRelationship`
```python
- test_add_relationship_success
- test_add_relationship_foreign_key_violation
- test_add_relationship_database_error_rollback
- test_add_relationship_returns_relationship_id
```

##### `TestIngestStructuredData`
```python
- test_ingest_structured_multiple_entities
- test_ingest_structured_multiple_relationships
- test_ingest_structured_maps_entity_names_to_ids
- test_ingest_structured_skips_relationships_with_unknown_entities
- test_ingest_structured_database_error_rollback
- test_ingest_structured_empty_inputs
```

##### `TestLocalSearch`
```python
- test_local_search_finds_matching_entities
- test_local_search_recursive_traversal_depth_1
- test_local_search_recursive_traversal_depth_2
- test_local_search_returns_entity_context
- test_local_search_returns_relationship_context
- test_local_search_no_matches_returns_empty
- test_local_search_bfs_traversal_correctness
- test_local_search_limits_edges_to_50
```

##### `TestGlobalSearch`
```python
- test_global_search_returns_community_summaries
- test_global_search_reranks_by_keywords
- test_global_search_reranks_by_summary_text
- test_global_search_fallback_to_generic_summaries
- test_global_search_no_communities_returns_empty
- test_global_search_limits_to_10_communities
```

##### `TestQuery`
```python
- test_query_auto_mode_detects_local_for_specific_terms
- test_query_auto_mode_detects_global_for_holistic_terms
- test_query_explicit_local_mode
- test_query_explicit_global_mode
```

##### `TestGetContextForAI`
```python
- test_get_context_formats_global_mode
- test_get_context_formats_local_mode_entities
- test_get_context_formats_local_mode_relationships
- test_get_context_limits_entities_to_10
- test_get_context_limits_relationships_to_15
```

##### `TestEnqueueReindexJob`
```python
- test_enqueue_reindex_with_redis_url
- test_enqueue_reindex_pushes_to_list_head
- test_enqueue_reindex_without_redis_url_returns_false
- test_enqueue_reindex_redis_connection_error
```

---

## LanceDB Integration Tests

**File:** `backend/tests/test_lancedb_integration.py` (NEW, ~800 lines)

**Challenge:** LanceDB has heavy dependencies (NumPy, Pandas, LanceDB itself)

**Strategy:**
1. **Mock LanceDB Handler** for unit tests (existing approach)
2. **Integration Tests** with in-memory LanceDB (if feasible)
3. **Focus on API correctness** rather than vector search quality

#### Test Classes

##### `TestLanceDBHandlerInit`
```python
- test_init_creates_directory_if_not_exists
- test_init_with_s3_uri
- test_init_with_custom_workspace_id
- test_lazy_loading_db_not_initialized_on_construction
- test_lazy_loading_embedder_not_initialized_on_construction
```

##### `TestEnsureDB`
```python
- test_ensure_db_initializes_on_first_call
- test_ensure_db_idempotent
- test_ensure_db_with_s3_storage_options
```

##### `TestEnsureEmbedder`
```python
- test_ensure_embedder_initializes_openai_when_configured
- test_ensure_embedder_falls_back_to_local_when_no_api_key
- test_ensure_embedder_loads_sentence_transformers
- test_ensure_embedder_timeout_falls_back_to_mock
- test_ensure_embedder_idempotent
```

##### `TestCreateTable`
```python
- test_create_table_infers_schema_from_data
- test_create_table_with_dual_vector_disabled
- test_create_table_with_dual_vector_enabled
- test_create_table_custom_schema
- test_create_table_knowledge_graph_schema
- test_create_table_vector_size_openai
- test_create_table_vector_size_local
```

##### `TestAddDocument`
```python
- test_add_document_with_secrets_redaction
- test_add_document_without_secrets
- test_add_document_redaction_metadata_added
- test_add_document_redaction_failure_continues
- test_add_document_generates_embedding
- test_add_document_serializes_metadata
- test_add_document_with_workspace_id
- test_add_document_lancedb_failure
```

##### `TestSearch`
```python
- test_search_generates_query_embedding
- test_search_applies_workspace_filter
- test_search_applies_user_filter
- test_search_applies_custom_filter
- test_search_combines_filters_with_and
- test_search_returns_pandas_results
- test_search_parses_metadata_json
- test_search_handles_malformed_metadata
- test_search_lancedb_not_initialized_returns_empty
```

##### `TestAddKnowledgeEdge`
```python
- test_add_knowledge_edge_with_embedding
- test_add_knowledge_edge_fallback_zero_vector
- test_add_knowledge_edge_creates_table_if_missing
- test_add_knowledge_edge_generates_unique_id
```

##### `TestDualVectorStorage`
```python
- test_add_embedding_vector_column_1024_dim
- test_add_embedding_vector_fastembed_column_384_dim
- test_add_embedding_dimension_mismatch_raises_error
- test_add_embedding_unknown_column_raises_error
- test_similarity_search_vector_column
- test_similarity_search_vector_fastembed_column
- test_similarity_search_dimension_validation
- test_get_embedding_from_vector_column
- test_get_embedding_from_vector_fastembed_column
```

##### `TestChatHistoryManager`
```python
- test_save_message_with_metadata
- test_save_message_generates_unique_id
- test_get_session_history_chronological_order
- test_get_session_history_limit
- test_get_session_history_filters_by_session_id
- test_search_relevant_context_semantic
- test_search_relevant_context_with_session_filter
- test_get_entity_mentions_by_entity_type
- test_get_entity_mentions_by_session_id
```

---

## Storage Service Tests (R2/S3)

**File:** `backend/tests/test_storage_service.py` (NEW, ~400 lines)

#### Test Classes

##### `TestStorageServiceInit`
```python
- test_init_loads_s3_client
- test_init_with_r2_credentials
- test_init_with_aws_credentials
- test_init_with_custom_endpoint
- test_init_singleton_pattern
```

##### `TestUploadFile`
```python
- test_upload_file_success
- test_upload_file_with_content_type
- test_upload_file_returns_s3_uri
- test_upload_file_bucket_from_env
- test_upload_file_failure_raises_exception
```

##### `TestCheckExists`
```python
- test_check_exists_true
- test_check_exists_false
- test_check_exists_error_returns_false
- test_check_exists_bucket_from_env
```

##### `TestGetStorageService`
```python
- test_get_storage_service_singleton
- test_get_storage_service_returns_same_instance
```

---

## Test Coverage Targets

### File-by-File Targets

| File | Lines | Target Coverage | Target Tests |
|------|-------|----------------|--------------|
| `agent_world_model.py` | 929 | 75% | ~120 tests |
| `business_facts_routes.py` | 407 | 80% | ~50 tests |
| `policy_fact_extractor.py` | 88 | 60% | ~10 tests |
| `graphrag_engine.py` | 642 | 70% | ~80 tests |
| `lancedb_handler.py` | 1,390 | 50% | ~60 tests |
| `storage.py` | 69 | 80% | ~15 tests |
| **TOTAL** | **3,525** | **70%** | **~335 tests** |

### Priority Breakdown

**Priority 1 (Must-Have):**
- World Model Service core methods: 50 tests
- Business Facts Routes: 30 tests
- GraphRAG Engine: 40 tests

**Priority 2 (Should-Have):**
- World Model error paths: 30 tests
- Business Facts citation verification: 15 tests
- LanceDB integration: 30 tests

**Priority 3 (Nice-to-Have):**
- Policy Fact Extractor stub: 10 tests
- Storage Service: 15 tests
- GraphRAG pattern extraction: 20 tests
- LanceDB dual vector: 20 tests
- Chat History Manager: 15 tests

---

## Testing Patterns and Best Practices

### 1. Mock Database Sessions

**Pattern:** Use `unittest.mock.Mock` and `AsyncMock` for SQLAlchemy sessions

```python
@pytest.fixture
def mock_db_session():
    mock_db = Mock()
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()

    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.order_by.return_value = mock_order
    mock_order.all.return_value = []

    return mock_db

# Usage
with patch('core.agent_world_model.get_db_session') as mock_get_db:
    mock_get_db.return_value.__enter__.return_value = mock_db_session
    result = await world_model_service.archive_session_to_cold_storage("conv-1")
```

### 2. AsyncMock for Async Methods

**Pattern:** Use `AsyncMock` for coroutines

```python
@pytest.mark.asyncio
async def test_async_method():
    mock_service = AsyncMock()
    mock_service.get_fact_by_id.return_value = mock_fact
    result = await mock_service.get_fact_by_id("fact-1")
```

### 3. LanceDB Handler Mocking

**Pattern:** Mock at import location, not at usage

```python
# Mock at the import level
with patch('core.agent_world_model.get_lancedb_handler') as mock_get_handler:
    mock_handler = AsyncMock()
    mock_handler.add_document = Mock(return_value=True)
    mock_handler.search = Mock(return_value=[])
    mock_get_handler.return_value = mock_handler

    service = WorldModelService(workspace_id="test")
    service.db = mock_handler  # Override lazy-loaded instance
```

### 4. Dependency Overrides for FastAPI

**Pattern:** Override authentication and database dependencies

```python
# Import-level RBAC mock (required for import-time errors)
sys.modules['core.security.rbac'] = MagicMock()
sys.modules['core.security.rbac'].require_role = lambda role: lambda: None

# Test-level dependency override
@pytest.fixture
def client_with_admin_auth(client, admin_user):
    def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.clear()
```

### 5. File Upload Mocking

**Pattern:** Use `io.BytesIO` for file uploads

```python
import io

def test_upload_pdf(client):
    pdf_content = b"%PDF-1.4 fake pdf content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"domain": "finance"}

    response = client.post("/api/admin/governance/facts/upload", files=files, data=data)
    assert response.status_code == 200
```

### 6. S3/R2 Mocking

**Pattern:** Mock boto3 S3 client

```python
@patch('core.storage.boto3.client')
def test_check_exists(mock_boto3_client):
    mock_s3 = Mock()
    mock_s3.head_object.return_value = {}
    mock_boto3_client.return_value = mock_s3

    storage = StorageService()
    assert storage.check_exists("test-key") is True
```

### 7. LanceDB Lazy Loading

**Pattern:** Trigger lazy initialization before testing

```python
def test_lancedb_search():
    handler = LanceDBHandler()

    # Trigger lazy loading
    handler._ensure_db()
    handler._ensure_embedder()

    # Mock the db and embedder
    handler.db = Mock()
    handler.embedder = Mock()
    handler.embedder.encode.return_value = np.zeros(384)

    # Test search
    results = handler.search("test_table", "test query")
```

### 8. Exception Testing

**Pattern:** Test error paths with `pytest.raises`

```python
def test_update_fact_not_found():
    service = WorldModelService()
    fact = BusinessFact(
        id="test-fact",
        fact="Test",
        citations=[],
        reason="Test",
        source_agent_id="agent:1",
        created_at=datetime.now(),
        last_verified=datetime.now(),
        verification_status="verified"
    )

    # Mock get_fact_by_id to return None
    with patch.object(service, 'get_fact_by_id', return_value=None):
        result = await service.update_fact_verification("nonexistent", "verified")
        assert result is False
```

---

## Integration vs. Unit Testing Strategy

### Unit Tests (70% of tests)

**Scope:** Individual methods in isolation
**Target Files:**
- `test_world_model.py` (expand)
- `test_graphrag_engine.py` (new)
- `test_policy_fact_extractor.py` (new)

**Approach:**
- Mock all external dependencies (LanceDB, PostgreSQL, LLM, S3)
- Test business logic, edge cases, error handling
- Fast execution (<5 seconds per file)

### Integration Tests (30% of tests)

**Scope:** Multiple components working together
**Target Files:**
- `test_world_model_integration.py` (expand)
- `test_business_facts_routes.py` (expand)
- `test_lancedb_integration.py` (new)

**Approach:**
- Use real database sessions (SQLite in-memory)
- Mock external services (S3, LLM APIs)
- Test API contracts, data flow
- Slower execution (<30 seconds per file)

---

## Existing Test Patterns from Phase 178

**File:** `backend/tests/api/test_admin_business_facts_routes.py` (1,267 lines)

**Key Patterns to Reuse:**

1. **Import-time RBAC mocking:**
```python
sys.modules['core.security.rbac'] = MagicMock()
sys.modules['core.security.rbac'].require_role = lambda role: lambda: None
```

2. **Async route testing:**
```python
async def test_update_fact_verification_status_only(self, mock_wm_class, client_with_admin_auth):
    mock_wm = AsyncMock()
    mock_wm.get_fact_by_id.return_value = existing_fact
    mock_wm.update_fact_verification.return_value = True
    mock_wm_class.return_value = mock_wm

    response = client_with_admin_auth.put("/api/admin/governance/facts/fact-123", ...)
    assert response.status_code == 200
```

3. **File upload testing:**
```python
def test_upload_unsupported_file_type(self, client_with_admin_auth):
    files = {"file": ("test.exe", b"fake exe content", "application/x-msdownload")}
    response = client_with_admin_auth.post("/api/admin/governance/facts/upload", files=files, data=...)
    assert response.status_code == 400
```

---

## Dependencies and Mocking Strategy

### External Services to Mock

1. **LanceDB** (`lancedb` package)
   - Mock `lancedb.connect()`
   - Mock `table.add()`, `table.search()`
   - Mock sentence transformer embedder

2. **PostgreSQL** (`sqlalchemy`)
   - Use `SessionLocal()` with in-memory SQLite
   - Mock `get_db_session()` context manager

3. **OpenAI/LLM APIs** (`openai` package)
   - Mock `OpenAI()` client
   - Mock `chat.completions.create()`
   - Mock `embeddings.create()`

4. **S3/R2** (`boto3` package)
   - Mock `boto3.client('s3')`
   - Mock `upload_fileobj()`, `head_object()`

5. **Redis** (for GraphRAG reindex queue)
   - Mock `redis.from_url()`
   - Mock `r.lpush()`

### Internal Dependencies to Patch

1. **`core.agent_world_model.get_lancedb_handler`**
   - Patch at import location in test files

2. **`core.agent_world_model.get_db_session`**
   - Patch to return mock session

3. **`core.graphrag_engine.get_byok_manager`**
   - Patch to return mock BYOK manager

4. **`core.storage.get_storage_service`**
   - Patch to return mock S3 service

---

## Test Execution Strategy

### Test File Organization

```
backend/tests/
├── test_world_model.py (2,000 lines) - Unit tests for WorldModelService
├── test_world_model_integration.py (1,000 lines) - Integration tests
├── test_business_facts_routes.py (1,500 lines) - API route tests
├── test_graphrag_engine.py (1,500 lines) - GraphRAG unit tests
├── test_policy_fact_extractor.py (500 lines) - Extractor unit tests
├── test_lancedb_integration.py (800 lines) - LanceDB integration tests
└── test_storage_service.py (400 lines) - S3/R2 service tests
```

### Pytest Configuration

**File:** `backend/pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    -p no:warnings
markers =
    asyncio: Async test
    integration: Integration test
    unit: Unit test
    slow: Slow test (>1s)
```

### Test Execution Commands

```bash
# Run all Phase 181 tests
pytest backend/tests/test_world_model.py -v
pytest backend/tests/test_world_model_integration.py -v
pytest backend/tests/test_business_facts_routes.py -v
pytest backend/tests/test_graphrag_engine.py -v

# Run with coverage
pytest backend/tests/test_world_model.py --cov=core.agent_world_model --cov-report=html
pytest backend/tests/test_business_facts_routes.py --cov=api.admin.business_facts_routes --cov-report=html

# Run specific test classes
pytest backend/tests/test_world_model.py::TestRecordExperienceErrors -v
pytest backend/tests/test_business_facts_routes.py::TestVerifyCitationS3 -v

# Run integration tests only
pytest -m integration -v

# Run fast unit tests only
pytest -m "not slow" -v
```

---

## Success Metrics

### Coverage Targets

| Metric | Target | Current (Estimated) | Gap |
|--------|--------|---------------------|-----|
| `agent_world_model.py` line coverage | 75% | 45% | +30% |
| `business_facts_routes.py` line coverage | 80% | 50% | +30% |
| `policy_fact_extractor.py` line coverage | 60% | 0% | +60% |
| `graphrag_engine.py` line coverage | 70% | 0% | +70% |
| `lancedb_handler.py` line coverage | 50% | 5% | +45% |
| `storage.py` line coverage | 80% | 0% | +80% |

### Test Count Targets

| Category | Target | Existing | Gap |
|----------|--------|----------|-----|
| World Model Unit | 120 | 34 | +86 |
| World Model Integration | 30 | 24 | +6 |
| Business Facts Routes | 50 | 11 | +39 |
| GraphRAG Engine | 80 | 0 | +80 |
| Policy Fact Extractor | 10 | 0 | +10 |
| LanceDB Integration | 60 | 0 | +60 |
| Storage Service | 15 | 0 | +15 |
| **TOTAL** | **365** | **69** | **+296** |

### Quality Gates

1. **All tests must pass:** 0 failures allowed
2. **Coverage threshold:** 75%+ for all target files
3. **Test execution time:** <5 minutes for full suite
4. **No test pollution:** Each test isolated with proper cleanup

---

## Risk Mitigation

### Risk 1: LanceDB Import Hangs

**Issue:** LanceDB/NumPy imports hang on Windows

**Mitigation:**
- Use lazy loading in production code (already implemented)
- Mock LanceDB handler in all tests
- Never import `lancedb` at module level in tests

### Risk 2: SQLite JSONB Incompatibility

**Issue:** SQLite doesn't support JSONB (PostgreSQL feature)

**Mitigation:**
- Use JSON string serialization in tests
- Mock database sessions for complex queries
- Document JSONB-only features in test comments

### Risk 3: Async/Await Complexity

**Issue:** Many methods are async, requiring `@pytest.mark.asyncio`

**Mitigation:**
- Use `pytest-asyncio` plugin consistently
- Mock async methods with `AsyncMock`, not `Mock`
- Ensure all async tests have `async def` and `await`

### Risk 4: External API Dependencies

**Issue:** Tests might call real OpenAI/Anthropic APIs

**Mitigation:**
- Mock `openai.OpenAI` client at import level
- Use `with patch()` context managers for all API calls
- Never run tests with real API keys in environment

### Risk 5: GraphRAG Recursive CTEs

**Issue:** Recursive SQL queries may not work in SQLite

**Mitigation:**
- Use PostgreSQL for GraphRAG tests (if available)
- Or mock the `session.execute()` results
- Focus on business logic, not SQL syntax

---

## Phase 181 Execution Plan

### Plan 01: World Model Core Methods (50 tests)
**File:** `backend/tests/test_world_model.py`
**Focus:** Error paths, edge cases, canvas insights

### Plan 02: World Model Recall Experiences (30 tests)
**File:** `backend/tests/test_world_model_integration.py`
**Focus:** Formula fallback, episode enrichment, error handling

### Plan 03: Business Facts Routes (40 tests)
**File:** `backend/tests/test_business_facts_routes.py`
**Focus:** Upload success, citation verification, filtering

### Plan 04: GraphRAG Engine (50 tests)
**File:** `backend/tests/test_graphrag_engine.py` (NEW)
**Focus:** LLM extraction, pattern extraction, local/global search

### Plan 05: LanceDB Integration (40 tests)
**File:** `backend/tests/test_lancedb_integration.py` (NEW)
**Focus:** Dual vector storage, chat history, S3 integration

### Plan 06: Storage Service & Extractor (25 tests)
**Files:**
- `backend/tests/test_storage_service.py` (NEW)
- `backend/tests/test_policy_fact_extractor.py` (NEW)

**Focus:** S3 upload, file validation, extractor stub

---

## Conclusion

Phase 181 requires **~296 new tests** to achieve 75%+ coverage across 6 target files (3,525 lines of code). The testing strategy combines:

1. **Unit tests** (70%) for business logic isolation
2. **Integration tests** (30%) for API contract validation
3. **Mock-heavy approach** for external services (LanceDB, S3, LLM)
4. **Error path focus** for untested exception handling

**Key challenges:**
- LanceDB lazy loading requires careful mocking
- GraphRAG recursive CTEs may need PostgreSQL
- Async/await testing requires `pytest-asyncio`
- File upload testing needs `io.BytesIO` patterns

**Success criteria:**
- 75%+ line coverage for all target files
- All 365+ tests passing
- <5 minutes total execution time
- Zero external API calls (all mocked)

---

## References

1. **Phase 178:** Admin Skill Routes Coverage (existing tests to reference)
2. **Phase 180:** APAR, Artifact, Deep links, Integration catalog (test patterns)
3. **CLAUDE.md:** Project context and architecture overview
4. **backend/docs/CODE_QUALITY_STANDARDS.md:** Testing patterns and best practices
5. **docs/JIT_FACT_PROVISION_SYSTEM.md:** JIT citation verification flow
6. **docs/CITATION_SYSTEM_GUIDE.md:** Citation format and validation

---

*End of Research Document*
