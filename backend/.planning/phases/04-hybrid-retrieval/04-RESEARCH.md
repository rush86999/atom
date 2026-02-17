# Phase 4: Hybrid Retrieval Enhancement - Research

**Researched:** February 17, 2026
**Domain:** Vector embeddings, hybrid retrieval, reranking, property-based testing
**Confidence:** HIGH

## Summary

Phase 4 implements a hybrid retrieval system combining **FastEmbed** (for fast initial candidate retrieval) and **Sentence Transformers** (for high-quality reranking). This two-stage approach balances speed and quality: FastEmbed provides sub-20ms coarse search using lightweight 384-dimensional embeddings, while Sentence Transformers reranks the top-50-100 candidates using higher-quality 1024-dimensional embeddings.

The current implementation already has FastEmbed integrated in `core/embedding_service.py` (lines 217-275) and uses Sentence Transformers in `core/lancedb_handler.py` (lines 52-56, 189-196). However, these operate independently—Phase 4 requires orchestrating them into a unified hybrid pipeline with property-based tests for retrieval quality (recall, NDCG, latency).

**Primary recommendation:** Implement a staged retrieval architecture where FastEmbed performs coarse filtering (top-100 candidates in <20ms) and Sentence Transformers reranks the results (top-50 in <150ms), achieving total latency <200ms with >15% relevance improvement over FastEmbed alone.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **FastEmbed** | >=0.2.0 | Fast local embeddings for coarse search | Rust-based ONNX runtime, 10-20ms per embedding, 384-dim vectors, privacy-preserving (no API calls) |
| **sentence-transformers** | >=2.2.0,<3.0.0 | High-quality embeddings for reranking | State-of-the-art bi-encoders, PyTorch ecosystem, 1024-dim vectors, cross-encoder support |
| **LanceDB** | >=0.5.3,<1.0.0 | Vector database for caching embeddings | Already integrated, supports ANN search, local file-based storage |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **numpy** | >=1.24.0,<2.0.0 | Vector operations | Embedding arithmetic, similarity calculations |
| **hypothesis** | >=6.92.0,<7.0.0 | Property-based testing | Retrieval invariants (recall, NDCG, monotonicity) |
| **pytest** | >=7.4.0,<8.0.0 | Test framework | Performance benchmarks, property tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **FastEmbed** | OpenAI text-embedding-3-small | FastEmbed: local, 10-20ms, free vs. OpenAI: cloud, 100-300ms, $0.02/1M tokens |
| **Sentence Transformers** | Cohere embed-english-v3.0 | ST: local, 150ms rerank, 1024-dim vs. Cohere: cloud, 400ms, 1024-dim, API limits |
| **Hybrid approach** | Single-stage retrieval | Hybrid: <200ms total, >15% relevance boost vs. Single: <50ms but lower quality |

**Installation:**
```bash
# Already installed in requirements.txt
fastembed>=0.2.0  # Rust-based ONNX embeddings
sentence-transformers>=2.2.0,<3.0.0  # PyTorch embeddings
lancedb>=0.5.3,<1.0.0  # Vector database
numpy>=1.24.0,<2.0.0  # Vector operations
```

## Architecture Patterns

### Recommended Project Structure

```
core/
├── hybrid_retrieval_service.py    # NEW: Two-stage retrieval orchestration
├── embedding_service.py           # EXISTING: FastEmbed integration (keep)
├── lancedb_handler.py             # EXISTING: LanceDB operations (extend for caching)
└── episode_retrieval_service.py   # EXISTING: Integrate hybrid retrieval

tests/
├── property_tests/hybrid_retrieval/
│   ├── test_hybrid_retrieval_invariants.py  # Top-k quality, monotonic improvement
│   ├── test_fastembed_performance.py        # <20ms coarse search
│   └── test_reranking_quality.py            # Recall, NDCG, relevance
└── unit/hybrid_retrieval/
    ├── test_hybrid_retrieval_service.py     # Unit tests
    └── test_embedding_consistency.py        # Deterministic embeddings
```

### Pattern 1: Two-Stage Hybrid Retrieval

**What:** Coarse-to-fine retrieval pattern where FastEmbed rapidly filters candidates and Sentence Transformers reranks them.

**When to use:** Semantic search on large datasets (10k+ episodes) where speed and quality both matter.

**Example:**
```python
# Source: Hybrid retrieval pattern from information retrieval best practices
class HybridRetrievalService:
    """
    Two-stage retrieval: FastEmbed (coarse) + Sentence Transformers (fine)

    Performance targets:
    - Coarse search: <20ms for top-100 candidates
    - Reranking: <150ms for top-50 candidates
    - Total latency: <200ms end-to-end
    """

    def __init__(self, db: Session):
        self.db = db
        self.fastembed = EmbeddingService(provider="fastembed")  # 384-dim
        self.reranker = SentenceTransformer("BAAI/bge-large-en-v1.5")  # 1024-dim
        self.lancedb = get_lancedb_handler()

    async def retrieve_semantic_hybrid(
        self,
        agent_id: str,
        query: str,
        coarse_top_k: int = 100,
        fine_top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Stage 1: FastEmbed coarse search (top-100 candidates, <20ms)
        Stage 2: Sentence Transformers reranking (top-10, <150ms)
        """
        # Stage 1: FastEmbed coarse search
        start = time.time()
        coarse_results = await self._fastembed_coarse_search(
            agent_id=agent_id,
            query=query,
            limit=coarse_top_k
        )
        coarse_latency = (time.time() - start) * 1000

        # Stage 2: Sentence Transformers reranking
        start = time.time()
        reranked_results = await self._rerank_candidates(
            query=query,
            candidates=coarse_results,
            limit=fine_top_k
        )
        rerank_latency = (time.time() - start) * 1000

        return {
            "episodes": reranked_results,
            "count": len(reranked_results),
            "performance": {
                "coarse_latency_ms": coarse_latency,
                "rerank_latency_ms": rerank_latency,
                "total_latency_ms": coarse_latency + rerank_latency
            }
        }

    async def _fastembed_coarse_search(
        self,
        agent_id: str,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """FastEmbed-based coarse search"""
        # Generate 384-dim query embedding
        query_embedding = await self.fastembed.generate_embedding(query)

        # Search LanceDB (ANN search)
        results = self.lancedb.search(
            table_name="episodes",
            query_vector=query_embedding,
            filter_str=f"agent_id == '{agent_id}'",
            limit=limit
        )

        return results

    async def _rerank_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Sentence Transformers-based reranking"""
        if not candidates:
            return []

        # Generate high-quality 1024-dim embeddings
        query_embedding = self.reranker.encode(query, convert_to_numpy=True)

        # Extract candidate texts
        candidate_texts = [c.get("text", "") for c in candidates]
        candidate_embeddings = self.reranker.encode(
            candidate_texts,
            convert_to_numpy=True
        )

        # Calculate cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity(
            [query_embedding],
            candidate_embeddings
        )[0]

        # Add scores to candidates
        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = float(similarities[i])

        # Sort by rerank score (descending)
        reranked = sorted(
            candidates,
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        return reranked[:limit]
```

### Pattern 2: Fallback Strategy

**What:** Graceful degradation when reranking fails, maintaining FastEmbed baseline.

**When to use:** Production systems where availability matters more than optimal quality.

**Example:**
```python
async def retrieve_semantic_hybrid_with_fallback(
    self,
    agent_id: str,
    query: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Hybrid retrieval with fallback to FastEmbed if reranking fails
    """
    try:
        # Attempt hybrid retrieval
        return await self.retrieve_semantic_hybrid(
            agent_id=agent_id,
            query=query,
            coarse_top_k=100,
            fine_top_k=limit
        )
    except Exception as e:
        logger.warning(f"Reranking failed, falling back to FastEmbed: {e}")

        # Fallback: FastEmbed-only retrieval
        results = await self._fastembed_coarse_search(
            agent_id=agent_id,
            query=query,
            limit=limit
        )

        return {
            "episodes": results,
            "count": len(results),
            "fallback": True,
            "error": str(e)
        }
```

### Anti-Patterns to Avoid

- **Don't rerank all results:** Only rerank top-50-100 candidates. Reranking 10k+ results defeats the performance purpose.
- **Don't skip caching:** Cache FastEmbed embeddings in LanceDB to avoid recomputation (30-50ms overhead).
- **Don't ignore dimensionality mismatch:** FastEmbed (384-dim) and Sentence Transformers (1024-dim) produce different vector sizes—handle gracefully.
- **Don't assume success:** Always implement fallback to FastEmbed if reranking fails (OOM, model load error, etc.).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Vector similarity** | Manual cosine distance calculation | `sklearn.metrics.pairwise.cosine_similarity` | Numerical stability, batch processing, optimized BLAS |
| **Embedding models** | Train custom embedding model | Pre-trained FastEmbed + Sentence Transformers | Training requires massive datasets, compute, and expertise |
| **Vector database** | File-based numpy search | LanceDB | Already integrated, ANN search (HNSW), indexing, persistence |
| **Batch processing** | Manual loop over texts | `model.encode(texts, batch_size=32)` | GPU acceleration, memory efficiency, automatic batching |
| **Property testing** | Manual random test generation | Hypothesis (`@given` strategies) | Shrinking, reproducibility, rich strategy library |

**Key insight:** Custom embedding models take weeks to train and require specialized ML expertise. Pre-trained models (BAAI/bge-small-en-v1.5, BAAI/bge-large-en-v1.5) are state-of-the-art and free to use locally.

## Common Pitfalls

### Pitfall 1: Ignoring Embedding Dimensionality Mismatch

**What goes wrong:** FastEmbed generates 384-dim vectors, Sentence Transformers generates 1024-dim vectors. Mixing them in the same vector database causes search failures.

**Why it happens:** LanceDB schemas require fixed vector dimensions. Can't query 1024-dim vectors against 384-dim index.

**How to avoid:** Store embeddings in separate columns or tables:
```python
# LanceDB schema with dual embeddings
schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("fastembed_vector", pa.list_(pa.float32(), 384)),      # Coarse search
    pa.field("rerank_vector", pa.list_(pa.float32(), 1024))        # Reranking (optional)
])
```

**Warning signs:** `ValueError: Shape mismatch` when querying LanceDB, or cosine similarity returning NaN/Inf.

### Pitfall 2: Reranking Too Many Candidates

**What goes wrong:** Reranking 1000+ candidates takes 500ms-1s, violating <200ms latency target.

**Why it happens:** Sentence Transformers is CPU-bound (unless GPU available). Processing 1000 texts takes ~0.5ms each → 500ms total.

**How to avoid:** Limit reranking to top-50-100 candidates:
```python
# Only rerank top-100 from FastEmbed
coarse_results = await self._fastembed_coarse_search(..., limit=100)
reranked = await self._rerank_candidates(..., candidates=coarse_results[:50])
```

**Warning signs:** Reranking latency >150ms, total latency >200ms.

### Pitfall 3: Missing Fallback Logic

**What goes wrong:** Reranking fails (OOM, model not loaded, CUDA error) and entire search crashes.

**Why it happens:** Assumes Sentence Transformers always works. Not true for all environments (CI, low-memory systems).

**How to avoid:** Wrap reranking in try-except with FastEmbed fallback:
```python
try:
    reranked = await self._rerank_candidates(...)
except Exception as e:
    logger.warning(f"Reranking failed: {e}, using FastEmbed results")
    reranked = coarse_results[:limit]
```

**Warning signs:** Production crashes on low-memory machines, intermittent test failures.

### Pitfall 4: Not Caching FastEmbed Embeddings

**What goes wrong:** Regenerating FastEmbed embeddings for every search adds 30-50ms overhead.

**Why it happens:** Treating embeddings as ephemeral instead of caching in LanceDB.

**How to avoid:** Cache embeddings on episode creation:
```python
# On episode creation
fastembed_vector = await self.fastembed.generate_embedding(episode_text)

# Store in LanceDB
self.lancedb.add_document(
    table_name="episodes",
    text=episode_text,
    metadata={"episode_id": episode_id},
    vector=fastembed_vector  # Cached
)
```

**Warning signs:** FastEmbed search takes 50-70ms instead of <20ms.

## Code Examples

Verified patterns from official sources:

### FastEmbed Batch Embedding

```python
# Source: /Users/rushiparikh/projects/atom/backend/core/embedding_service.py (lines 253-275)
async def _generate_fastembed_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using FastEmbed (batch).

    FastEmbed handles batching very efficiently with parallel processing.
    """
    try:
        from fastembed import TextEmbedding

        # Initialize model (cached after first use)
        if self._client is None:
            logger.info(f"Loading FastEmbed model: {self.model}")
            self._client = TextEmbedding(model_name=self.model)

        # Generate embeddings (FastEmbed handles batching)
        embeddings = list(self._client.embed(texts))

        # Convert to list of lists
        return [emb.tolist() for emb in embeddings]

    except Exception as e:
        logger.error(f"FastEmbed batch embedding generation failed: {e}")
        raise
```

### LanceDB Vector Search

```python
# Source: /Users/rushiparikh/projects/atom/backend/core/lancedb_handler.py (lines 570-638)
def search(self, table_name: str, query: str, user_id: str = None, limit: int = 10,
           filter_str: str = None) -> List[Dict[str, Any]]:
    """Search for documents in memory with optional user filtering"""
    if self.db is None:
        return []

    try:
        table = self.get_table(table_name)
        if not table:
            return []

        # Generate embedding for query
        query_vector = self.embed_text(query)
        if query_vector is None:
            return []

        # Build search query
        search_query = table.search(query_vector.tolist()).limit(limit)

        # Apply filters
        if filter_str:
            search_query = search_query.where(filter_str)

        # Execute search
        results = search_query.to_pandas()

        # Convert to list of dictionaries
        results_list = []
        for _, row in results.iterrows():
            result = {
                "id": row['id'],
                "text": row['text'],
                "score": 1.0 - row.get('_distance', 0.0)  # Distance → similarity
            }
            results_list.append(result)

        return results_list

    except Exception as e:
        logger.error(f"Failed to search in '{table_name}': {e}")
        return []
```

### Property Testing Retrieval Quality

```python
# Source: /Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py (lines 136-196)
class TestSemanticRetrievalInvariants:
    """Tests for semantic retrieval invariants"""

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @example(similarity_scores=[0.0, 0.5, 1.0])  # Boundary values
    @settings(max_examples=100)
    def test_semantic_retrieval_similarity_bounds(self, similarity_scores):
        """
        INVARIANT: Semantic retrieval similarity scores are in valid range [0, 1].
        """
        for score in similarity_scores:
            # Similarity scores should be in [0, 1]
            assert 0.0 <= score <= 1.0, \
                f"Similarity score {score} should be in [0.0, 1.0]"

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_semantic_retrieval_ranking_order(self, similarity_scores):
        """
        INVARIANT: Semantic retrieval ranks by similarity (descending).
        """
        # Create episodes with similarity scores
        episodes = [
            {'id': f'ep_{i}', 'similarity': score}
            for i, score in enumerate(similarity_scores)
        ]

        # Sort by similarity descending (highest first)
        ranked = sorted(episodes, key=lambda x: x['similarity'], reverse=True)

        # Verify ranking
        for i in range(1, len(ranked)):
            assert ranked[i]['similarity'] <= ranked[i-1]['similarity'], \
                "Episodes should be ranked by similarity (descending)"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Single-stage retrieval** (one embedding model) | **Hybrid retrieval** (coarse + fine) | 2023-2024 | 15-20% relevance boost, <200ms latency |
| **Cloud-only embeddings** (OpenAI, Cohere) | **Local-first embeddings** (FastEmbed, ST) | 2024-2025 | Privacy-preserving, 10x faster, zero API costs |
| **Manual reranking** (heuristics, BM25) | **Neural reranking** (cross-encoders) | 2022-2023 | 10-30% NDCG improvement |

**Deprecated/outdated:**
- **Pure keyword search (BM25):** Replaced by semantic search for most use cases. BM25 still useful for exact phrase matching.
- **Single-model retrieval:** Outperformed by hybrid approaches on quality metrics (recall, NDCG).
- **Cloud-only embeddings:** Not suitable for privacy-sensitive or high-volume applications due to latency and cost.

## Open Questions

1. **GPU acceleration for Sentence Transformers**
   - What we know: Sentence Transformers supports CUDA for 10-50x speedup on reranking
   - What's unclear: GPU availability in production environment (Personal Edition uses CPU-only)
   - Recommendation: Implement CPU-first with optional GPU support (check `torch.cuda.is_available()`)

2. **Optimal top-k for reranking**
   - What we know: Reranking top-50-100 is common in literature
   - What's unclear: Optimal k for Atom's workload (episodes vs. general documents)
   - Recommendation: Make k configurable (default: 100) and benchmark different values (50, 100, 200)

3. **Reranking model selection**
   - What we know: BAAI/bge-large-en-v1.5 is state-of-the-art for English
   - What's unclear: Whether multilingual models (multilingual-e5) are needed for non-English episodes
   - Recommendation: Stick with BAAI/bge-large-en-v1.5 for Phase 4 (English-only), add multilingual support in later phases if needed

## Sources

### Primary (HIGH confidence)

- `/Users/rushiparikh/projects/atom/backend/core/embedding_service.py` - FastEmbed integration (lines 217-275)
- `/Users/rushiparikh/projects/atom/backend/core/lancedb_handler.py` - Sentence Transformers integration (lines 52-56, 189-196)
- `/Users/rushiparikh/projects/atom/backend/core/episode_retrieval_service.py` - Existing semantic retrieval (lines 128-197)
- `/Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py` - Property testing patterns (lines 136-196)
- `/Users/rushiparikh/projects/atom/backend/requirements.txt` - Dependency versions (lines 26, 30, 31)
- `/Users/rushiparikh/projects/atom/backend/.planning/ROADMAP.md` - Phase 4 requirements (lines 201-262)

### Secondary (MEDIUM confidence)

- FastEmbed GitHub repository (qdrant/fastembed) - Architecture and usage patterns
- Sentence Transformers documentation (sbert.net) - Reranking workflows, cross-encoders
- LanceDB documentation (lancedb.github.io/lancedb) - Vector search optimization, indexing

### Tertiary (LOW confidence)

- Academic literature on hybrid retrieval (2023-2024) - Recall@10, NDCG@10 benchmarks
- Vector database comparison blogs - Performance characteristics of LanceDB vs. alternatives

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and integrated in codebase
- Architecture: HIGH - Two-stage retrieval pattern is well-established in IR literature
- Pitfalls: HIGH - Identified from code review (dimensionality mismatch, fallback logic)
- Performance targets: MEDIUM - Based on literature (10-20ms FastEmbed, 150ms reranking), need validation in Atom's environment

**Research date:** February 17, 2026
**Valid until:** March 19, 2026 (30 days - stable ML ecosystem, but library versions may update)
