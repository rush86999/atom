---
phase: 16-hybrid-retrieval-enhancement
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - core/hybrid_retrieval_service.py
  - core/lancedb_handler.py
  - core/embedding_service.py
autonomous: true

must_haves:
  truths:
    - Reranking takes coarse results (top-100) and returns refined top-50
    - Reranking completes in <150ms for 100 candidates
    - Fallback to FastEmbed results if reranking fails
    - Cross-encoder scores are normalized to [0, 1] range
  artifacts:
    - path: "core/hybrid_retrieval_service.py"
      provides: "Hybrid retrieval orchestration service"
      exports: ["HybridRetrievalService", "rerank_cross_encoder", "retrieve_hybrid"]
    - path: "core/embedding_service.py"
      provides: "Sentence Transformers cross-encoder for reranking"
      exports: ["rerank_with_cross_encoder", "EmbeddingService"]
  key_links:
    - from: "core/hybrid_retrieval_service.py"
      to: "core/lancedb_handler.py"
      via: "search_coarse method for initial candidate retrieval"
      pattern: "search_coarse|coarse_search"
    - from: "core/hybrid_retrieval_service.py"
      to: "core/embedding_service.py"
      via: "rerank_with_cross_encoder for final ranking"
      pattern: "rerank|cross_encoder"
---

<objective>
Implement Sentence Transformers cross-encoder reranking pipeline to refine FastEmbed coarse search results.

Purpose: Cross-encoder reranking provides higher quality relevance scoring than bi-encoder embeddings alone. This two-stage approach (FastEmbed coarse + ST fine) balances speed (<20ms + <150ms) with quality (Recall@10 >90%, NDCG@10 >0.85 per research).

Output: HybridRetrievalService with cross-encoder reranking, fallback handling, and configurable top-k parameters.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@core/lancedb_handler.py (lines 189-196: Sentence Transformers embedder initialization)
@core/embedding_service.py (FastEmbed integration from Plan 01)
@core/episode_retrieval_service.py (existing retrieval patterns to follow)
@tests/property_tests/episodes/test_episode_retrieval_invariants.py (property test patterns)
</context>

<tasks>

<task type="auto">
  <name>Create HybridRetrievalService with cross-encoder reranking</name>
  <files>core/hybrid_retrieval_service.py</files>
  <action>
    Create a new HybridRetrievalService class that orchestrates two-stage retrieval:

    1. Class structure:
       ```python
    class HybridRetrievalService:
        def __init__(self, db: Session):
            self.db = db
            self.lancedb = get_lancedb_handler()
            self.cross_encoder = None  # Lazy-loaded ST model
            self._load_cross_encoder()

        def _load_cross_encoder(self):
            # Lazy load sentence-transformers cross-encoder
            # Model: ms-marco-MiniLM-L-6-v2 or similar lightweight cross-encoder
            # Fallback: Use bi-encoder if cross-encoder unavailable

        async def retrieve_hybrid(
            self,
            query: str,
            agent_id: str,
            top_k: int = 50,
            coarse_k: int = 100,
            enable_rerank: bool = True
        ) -> Dict[str, Any]:
            # Two-stage retrieval
            # Stage 1: FastEmbed coarse search (top_k=coarse_k)
            # Stage 2: Cross-encoder rerank (top_k=top_k)
            # Fallback: Return coarse results if rerank fails
       ```

    2. Stage 1 - Coarse search:
       - Uses LanceDB search_coarse (384-dim FastEmbed)
       - Returns top-coarse_k candidates (default: 100)
       - Performance: <20ms
       - Include governance check before retrieval

    3. Stage 2 - Reranking:
       - Takes coarse results as input
       - Uses cross-encoder: query-document scoring
       - Re-scores and re-ranks by cross-encoder score
       - Returns top-k refined results (default: 50)
       - Performance: <150ms for 100 candidates
       - Normalizes scores to [0, 1] range

    4. Fallback handling:
       - If cross-encoder fails: return coarse results with warning
       - If coarse search fails: raise error (no fallback)
       - Log all fallbacks with error details

    5. Return format:
       ```python
       {
           "episodes": List[Episode],  # Final top-k results
           "count": int,
           "query": str,
           "coarse_count": int,  # Number of candidates
           "reranked": bool,  # Whether reranking succeeded
           "query_time_ms": float,
           "stage_times": {"coarse_ms": float, "rerank_ms": float}
       }
       ```
  </action>
  <verify>
    pytest tests/unit/test_hybrid_retrieval.py -v -k "HybridRetrievalService"
  </verify>
  <done>
    - HybridRetrievalService class exists in core/hybrid_retrieval_service.py
    - retrieve_hybrid method implements two-stage retrieval
    - Cross-encoder lazy loading with fallback
    - Performance metrics (stage_times) are tracked
  </done>
</task>

<task type="auto">
  <name>Add cross-encoder reranking to EmbeddingService</name>
  <files>core/embedding_service.py</files>
  <action>
    Add cross-encoder reranking capability to EmbeddingService:

    1. Add new method `rerank_with_cross_encoder`:
       ```python
    async def rerank_with_cross_encoder(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using cross-encoder scoring.

        Args:
            query: User query
            candidates: List of candidate episodes with 'text' field
            top_k: Number of results to return

        Returns:
            Reranked and sliced candidates with '_rerank_score' field
        """
       ```

    2. Implementation:
       - Use sentence-transformers CrossEncoder class
       - Model: 'ms-marco-MiniLM-L-6-v2' (lightweight, fast)
       - Score pairs: [(query, doc1), (query, doc2), ...]
       - Sort by cross-encoder score descending
       - Return top-k results

    3. Add fallback to bi-encoder:
       - If CrossEncoder unavailable: use existing embedder for similarity
       - Log warning when fallback is triggered

    4. Add score normalization:
       - Cross-encoder scores may be unbounded
       - Normalize to [0, 1] using min-max or sigmoid
       - Store normalized score in '_rerank_score' field

    5. Performance optimization:
       - Batch prediction: model.predict(list_of_pairs)
       - Limit candidates to 100 (configurable)
       - Timeout: 150ms max for reranking
  </action>
  <verify>
    pytest tests/unit/test_embedding_service.py -v -k "rerank"
  </verify>
  <done>
    - rerank_with_cross_encoder method exists in EmbeddingService
    - Uses CrossEncoder for query-document scoring
    - Normalizes scores to [0, 1] range
    - Has fallback to bi-encoder similarity
  </done>
</task>

<task type="auto">
  <name>Add API endpoints for hybrid retrieval</name>
  <files>core/atom_agent_endpoints.py</files>
  <action>
    Add REST API endpoints to expose hybrid retrieval functionality:

    1. Add POST endpoint `/api/episodes/retrieve/hybrid`:
       ```python
    @router.post("/api/episodes/retrieve/hybrid")
    async def retrieve_episodes_hybrid(
        request: EpisodeRetrievalRequest,
        agent_id: str,
        db: Session = Depends(get_db)
    ):
        """
        Hybrid retrieval with coarse search + reranking.

        Request body:
        {
            "query": str,
            "top_k": int = 50,  # Final results
            "coarse_k": int = 100,  # Coarse candidates
            "enable_rerank": bool = True
        }

        Response:
        {
            "episodes": List[Episode],
            "count": int,
            "coarse_count": int,
            "reranked": bool,
            "query_time_ms": float
        }
       """
    ```

    2. Request model (pydantic):
       ```python
    class EpisodeRetrievalRequest(BaseModel):
        query: str
        top_k: int = Field(default=50, ge=1, le=100)
        coarse_k: int = Field(default=100, ge=1, le=500)
        enable_rerank: bool = True
        time_range: Optional[str] = "30d"
   ```

    3. Governance integration:
       - Check agent maturity before retrieval
       - STUDENT: temporal only (no hybrid)
       - INTERN+: can use hybrid retrieval
       - Log all retrieval attempts to EpisodeAccessLog

    4. Performance monitoring:
       - Track query_time_ms
       - Track stage_times (coarse, rerank)
       - Log warnings if reranking exceeds 150ms
  </action>
  <verify>
    # Manual test with curl
    curl -X POST http://localhost:8000/api/episodes/retrieve/hybrid?agent_id=test-agent \
      -H "Content-Type: application/json" \
      -d '{"query": "test", "top_k": 10}'
  </verify>
  <done>
    - POST /api/episodes/retrieve/hybrid endpoint exists
    - Request validation with Pydantic model
    - Governance checks (INTERN+ only for hybrid)
    - Performance metrics tracked
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Test hybrid retrieval end-to-end:
   ```python
   from core.hybrid_retrieval_service import HybridRetrievalService
   from core.models import SessionLocal

   db = SessionLocal()
   service = HybridRetrievalService(db)
   result = await service.retrieve_hybrid(
       query="test episode about workflows",
       agent_id="test-agent",
       top_k=10,
       coarse_k=50
   )
   assert result["count"] == 10
   assert result["coarse_count"] == 50
   assert result["reranked"] == True
   assert result["query_time_ms"] < 200  # <20ms + <150ms + overhead
   ```

2. Verify fallback behavior:
   - Disable cross-encoder (set to None) and test fallback
   - Should return coarse results with reranked=False

3. Test governance integration:
   - STUDENT agent: should be blocked or fall back to temporal
   - INTERN+ agent: should access hybrid retrieval

4. Performance validation:
   - Run 100 queries and measure average latency
   - Coarse stage: <20ms P95
   - Rerank stage: <150ms P95
   - Total: <200ms P95
</verification>

<success_criteria>
1. HybridRetrievalService implements two-stage retrieval (coarse + rerank)
2. Cross-encoder reranking refines top-100 to top-50 in <150ms
3. Fallback to coarse results works when reranking fails
4. API endpoint exposes hybrid retrieval with governance checks
5. Performance metrics are tracked and logged
6. All existing retrieval tests continue to pass
</success_criteria>

<output>
After completion, create `.planning/phases/16-hybrid-retrieval-enhancement/16-hybrid-retrieval-enhancement-02-SUMMARY.md`
</output>
