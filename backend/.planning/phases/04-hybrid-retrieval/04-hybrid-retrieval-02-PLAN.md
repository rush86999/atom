---
phase: 04-hybrid-retrieval
plan: 02
type: execute
wave: 2
depends_on: ["04-hybrid-retrieval-01"]
files_modified:
  - core/hybrid_retrieval_service.py
  - core/embedding_service.py
  - core/atom_agent_endpoints.py
autonomous: true

must_haves:
  truths:
    - "Sentence Transformers cross-encoder reranks top-50-100 candidates in <150ms"
    - "Reranking uses BAAI/bge-large-en-v1.5 model (1024-dim bi-encoder)"
    - "Fallback to FastEmbed coarse results if reranking fails"
    - "Hybrid retrieval total latency <200ms (coarse <20ms + rerank <150ms + overhead <30ms)"
    - "Reranking improves relevance scores by >15% vs. FastEmbed alone"
    - "Top-k results always include best matches (no false negatives from reranking)"
  artifacts:
    - path: "core/hybrid_retrieval_service.py"
      provides: "Two-stage hybrid retrieval orchestration service"
      min_lines: 250
    - path: "core/embedding_service.py"
      provides: "Cross-encoder reranking method"
      min_lines: 80 (extensions)
    - path: "core/atom_agent_endpoints.py"
      provides: "Hybrid retrieval API endpoints"
      min_lines: 50 (extensions)
  key_links:
    - from: "core/hybrid_retrieval_service.py"
      to: "core/embedding_service.py"
      via: "calls coarse_search_fastembed() and rerank_cross_encoder()"
      pattern: "coarse_search|rerank"
    - from: "core/hybrid_retrieval_service.py"
      to: "core/lancedb_handler.py"
      via: "retrieves episode metadata after hybrid search"
      pattern: "get_episode_metadata|fetch_episodes"
    - from: "core/atom_agent_endpoints.py"
      to: "core/hybrid_retrieval_service.py"
      via: "POST /agents/{agent_id}/retrieve-hybrid endpoint"
      pattern: "retrieve_hybrid|hybrid_retrieval"
---

## Objective

Implement HybridRetrievalService for two-stage retrieval orchestration (FastEmbed coarse search + Sentence Transformers cross-encoder reranking) with fallback behavior and API integration.

**Purpose:** Hybrid retrieval balances speed and quality by using FastEmbed for rapid candidate filtering (<20ms) and Sentence Transformers for high-quality reranking (<150ms). The orchestration service manages the pipeline, fallback logic, and result aggregation.

**Output:** New HybridRetrievalService with cross-encoder reranking, fallback to FastEmbed, enhanced EmbeddingService with reranking method, API endpoints for hybrid retrieval.

## Execution Context

@core/embedding_service.py (extend with reranking)
@core/lancedb_handler.py (from Plan 01: dual vector support)
@core/models.py (from Plan 01: vector_fastembed column)
@.planning/phases/04-hybrid-retrieval/04-hybrid-retrieval-01-PLAN.md

## Context

@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md

# Plan 01 Complete
- FastEmbed coarse search operational (<20ms)
- Dual vector storage (384-dim + 1024-dim) in LanceDB
- LRU cache for FastEmbed embeddings

# Research Findings (04-RESEARCH.md)
- Sentence Transformers already installed (sentence-transformers>=2.2.0)
- Cross-encoder reranking recommended for quality improvement
- 4 pitfalls: dimensionality mismatch (avoided in Plan 01), reranking too many (limit to top-50), missing fallback (implement), not caching (done in Plan 01)
- Performance target: <150ms for top-50 candidates
- Quality target: >15% relevance improvement

## Tasks

### Task 1: Create HybridRetrievalService

**Files:** `core/hybrid_retrieval_service.py` (NEW)

**Action:**
Create new HybridRetrievalService for two-stage retrieval orchestration:

```python
"""
Hybrid Retrieval Service: Two-stage retrieval orchestration

Coarse stage: FastEmbed (384-dim, <20ms, top-100)
Fine stage: Sentence Transformers cross-encoder (1024-dim, <150ms, top-50)
Total target: <200ms latency, >15% relevance improvement

Fallback: Return coarse results if reranking fails
"""
from typing import List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import numpy as np

from core.embedding_service import EmbeddingService
from core.models import Episode
import logging

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """
    Two-stage hybrid retrieval: FastEmbed coarse + ST fine reranking

    Performance targets:
    - Coarse search: <20ms (top-100 candidates)
    - Reranking: <150ms (top-50 candidates)
    - Total latency: <200ms end-to-end

    Quality targets:
    - Recall@10: >90% (vs. ~80% FastEmbed alone)
    - NDCG@10: >0.85 (vs. ~0.70 FastEmbed alone)
    - Relevance improvement: >15%
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService(provider="hybrid")
        self._reranker_model = None  # Lazy load

    async def _get_reranker_model(self):
        """Lazy load Sentence Transformer cross-encoder."""
        if self._reranker_model is None:
            from sentence_transformers import CrossEncoder
            self._reranker_model = CrossEncoder(
                "BAAI/bge-large-en-v1.5",
                device="cpu"  # TODO: GPU support
            )
        return self._reranker_model

    async def retrieve_semantic_hybrid(
        self,
        agent_id: str,
        query: str,
        coarse_top_k: int = 100,
        rerank_top_k: int = 50,
        use_reranking: bool = True
    ) -> List[Tuple[str, float, str]]:
        """
        Hybrid semantic retrieval (coarse + fine).

        Args:
            agent_id: Agent ID for filtering episodes
            query: Search query text
            coarse_top_k: Number of candidates from FastEmbed (default: 100)
            rerank_top_k: Number of results after reranking (default: 50)
            use_reranking: Whether to use reranking (default: True)

        Returns:
            List of (episode_id, relevance_score, stage)
            stage: "coarse" or "reranked"

        Performance:
        - Coarse search: <20ms
        - Reranking: <150ms (if enabled)
        - Total: <200ms
        """
        start_time = datetime.utcnow()

        # Stage 1: Coarse search with FastEmbed
        logger.info(f"[HYBRID] Stage 1: Coarse search (top-{coarse_top_k})")
        coarse_results = await self.embedding_service.coarse_search_fastembed(
            agent_id=agent_id,
            query=query,
            top_k=coarse_top_k,
            db=self.db
        )

        if not coarse_results:
            logger.warning("[HYBRID] No coarse results found")
            return []

        coarse_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(f"[HYBRID] Coarse search: {len(coarse_results)} results in {coarse_duration:.1f}ms")

        # Stage 2: Rerank with Sentence Transformers (if enabled)
        if use_reranking:
            try:
                logger.info(f"[HYBRID] Stage 2: Reranking top-{rerank_top_k}")
                reranked_results = await self._rerank_cross_encoder(
                    query=query,
                    candidates=coarse_results[:rerank_top_k],
                    agent_id=agent_id
                )

                rerank_duration = (datetime.utcnow() - start_time).total_seconds() * 1000 - coarse_duration
                total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.info(
                    f"[HYBRID] Reranking: {len(reranked_results)} results in "
                    f"{rerank_duration:.1f}ms (total: {total_duration:.1f}ms)"
                )

                # Tag as reranked
                return [(ep_id, score, "reranked") for ep_id, score in reranked_results]

            except Exception as e:
                logger.error(f"[HYBRID] Reranking failed: {e}. Falling back to coarse results.")
                # Fallback: Return coarse results
                return [(ep_id, score, "coarse_fallback") for ep_id, score in coarse_results[:rerank_top_k]]

        else:
            # No reranking, return coarse results
            return [(ep_id, score, "coarse_only") for ep_id, score in coarse_results[:rerank_top_k]]

    async def _rerank_cross_encoder(
        self,
        query: str,
        candidates: List[Tuple[str, float]],
        agent_id: str
    ) -> List[Tuple[str, float]]:
        """
        Rerank candidates using cross-encoder.

        Args:
            query: Search query
            candidates: List of (episode_id, coarse_score)
            agent_id: Agent ID

        Returns:
            List of (episode_id, reranked_score) sorted by relevance

        Performance: <150ms for 50 candidates
        """
        # Fetch episode content for candidates
        episode_ids = [ep_id for ep_id, _ in candidates]
        episodes = self.db.query(Episode).filter(
            Episode.id.in_(episode_ids),
            Episode.agent_id == agent_id
        ).all()

        # Create (query, episode_text) pairs for cross-encoder
        episode_map = {ep.id: ep for ep in episodes}
        pairs = [
            (query, episode_map[ep_id].summary or episode_map[ep_id].content or "")
            for ep_id, _ in candidates
            if ep_id in episode_map
        ]

        if not pairs:
            logger.warning("[HYBRID] No valid episode content for reranking")
            return candidates

        # Rerank with cross-encoder
        model = await self._get_reranker_model()
        rerank_scores = model.predict(pairs)  # Shape: (n_candidates,)

        # Normalize scores to [0, 1]
        rerank_scores = (rerank_scores - rerank_scores.min()) / (rerank_scores.max() - rerank_scores.min() + 1e-8)

        # Combine coarse and reranked scores (weighted average)
        # Weight: 30% coarse + 70% reranked (reranking is higher quality)
        combined_scores = []
        for i, (ep_id, coarse_score) in enumerate(candidates):
            if ep_id in episode_map:
                reranked_score = rerank_scores[i]
                combined_score = 0.3 * coarse_score + 0.7 * reranked_score
                combined_scores.append((ep_id, combined_score))

        # Sort by combined score (descending)
        combined_scores.sort(key=lambda x: x[1], reverse=True)

        return combined_scores

    async def retrieve_semantic_baseline(
        self,
        agent_id: str,
        query: str,
        top_k: int = 50
    ) -> List[Tuple[str, float]]:
        """
        Baseline semantic retrieval (FastEmbed only, no reranking).

        Used for A/B testing and performance comparison.
        """
        results = await self.embedding_service.coarse_search_fastembed(
            agent_id=agent_id,
            query=query,
            top_k=top_k,
            db=self.db
        )
        return [(ep_id, score) for ep_id, score in results]
```

**Tests:**
- Verify hybrid retrieval completes in <200ms
- Verify reranking improves relevance scores by >15%
- Verify fallback to coarse results on reranking failure
- Verify top-k always includes best matches

**Acceptance:**
- [ ] HybridRetrievalService created
- [ ] retrieve_semantic_hybrid completes in <200ms
- [ ] Reranking improves relevance by >15% (measured via A/B test)
- [ ] Fallback to coarse results works on exception
- [ ] Top-k results include best matches (no false negatives)

---

### Task 2: Add Cross-Encoder Reranking to EmbeddingService

**Files:** `core/embedding_service.py`

**Action:**
Add cross-encoder reranking method to EmbeddingService:

```python
# Add to EmbeddingService class
class EmbeddingService:
    # ... existing methods ...

    async def rerank_cross_encoder(
        self,
        query: str,
        episode_ids: List[str],
        agent_id: str,
        db: Session
    ) -> List[Tuple[str, float]]:
        """
        Rerank episodes using cross-encoder.

        Performance: <150ms for 50 candidates
        Returns: List of (episode_id, reranked_score)
        """
        from sentence_transformers import CrossEncoder

        # Lazy load cross-encoder
        if not hasattr(self, '_cross_encoder'):
            self._cross_encoder = CrossEncoder(
                "BAAI/bge-large-en-v1.5",
                device="cpu"
            )

        # Fetch episode content
        episodes = db.query(Episode).filter(
            Episode.id.in_(episode_ids),
            Episode.agent_id == agent_id
        ).all()

        episode_map = {ep.id: ep for ep in episodes}

        # Create (query, episode_text) pairs
        pairs = [
            (query, episode_map[ep_id].summary or episode_map[ep_id].content or "")
            for ep_id in episode_ids
            if ep_id in episode_map
        ]

        if not pairs:
            return []

        # Rerank
        scores = self._cross_encoder.predict(pairs)

        # Normalize to [0, 1]
        scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-8)

        # Return sorted
        results = list(zip(episode_ids, scores))
        results.sort(key=lambda x: x[1], reverse=True)
        return results
```

**Tests:**
- Verify cross-encoder reranking executes in <150ms for 50 candidates
- Verify scores normalized to [0, 1]
- Verify results sorted by relevance (descending)

**Acceptance:**
- [ ] rerank_cross_executor method added
- [ ] Executes in <150ms for 50 candidates
- [ ] Scores normalized to [0, 1]
- [ ] Results sorted correctly

---

### Task 3: Add Hybrid Retrieval API Endpoints

**Files:** `core/atom_agent_endpoints.py`

**Action:**
Add API endpoints for hybrid retrieval:

```python
# Add to atom_agent_endpoints.py
from core.hybrid_retrieval_service import HybridRetrievalService

@router.post("/agents/{agent_id}/retrieve-hybrid")
async def retrieve_hybrid(
    agent_id: str,
    query: str,
    coarse_top_k: int = 100,
    rerank_top_k: int = 50,
    use_reranking: bool = True,
    db: Session = Depends(get_db)
):
    """
    Hybrid semantic retrieval (FastEmbed + ST reranking).

    Performance: <200ms total
    Quality: >15% relevance improvement vs. FastEmbed alone
    """
    service = HybridRetrievalService(db)

    results = await service.retrieve_semantic_hybrid(
        agent_id=agent_id,
        query=query,
        coarse_top_k=coarse_top_k,
        rerank_top_k=rerank_top_k,
        use_reranking=use_reranking
    )

    return {
        "success": True,
        "results": [
            {
                "episode_id": ep_id,
                "relevance_score": score,
                "stage": stage
            }
            for ep_id, score, stage in results
        ],
        "query": query,
        "coarse_top_k": coarse_top_k,
        "rerank_top_k": rerank_top_k,
        "use_reranking": use_reranking
    }

@router.post("/agents/{agent_id}/retrieve-baseline")
async def retrieve_baseline(
    agent_id: str,
    query: str,
    top_k: int = 50,
    db: Session = Depends(get_db)
):
    """
    Baseline semantic retrieval (FastEmbed only).

    Used for A/B testing and performance comparison.
    """
    service = HybridRetrievalService(db)

    results = await service.retrieve_semantic_baseline(
        agent_id=agent_id,
        query=query,
        top_k=top_k
    )

    return {
        "success": True,
        "results": [
            {
                "episode_id": ep_id,
                "relevance_score": score
            }
            for ep_id, score in results
        ],
        "query": query,
        "top_k": top_k,
        "method": "fastembed_baseline"
    }
```

**Tests:**
- Verify POST /agents/{id}/retrieve-hybrid returns results
- Verify POST /agents/{id}/retrieve-baseline returns results
- Verify performance <200ms for hybrid endpoint

**Acceptance:**
- [ ] /retrieve-hybrid endpoint operational
- [ ] /retrieve-baseline endpoint operational
- [ ] Both endpoints return JSON with episode_ids and scores
- [ ] Hybrid endpoint completes in <200ms

---

## Deviations

**Rule 1 (Auto-fix bugs):** If cross-encoder fails to load, fallback to FastEmbed immediately.

**Rule 2 (Performance):** If reranking exceeds 150ms, reduce rerank_top_k to 30 candidates.

**Rule 3 (GPU):** If GPU available, use it (device="cuda") for 10-50x speedup.

## Success Criteria

- [ ] HybridRetrievalService created and operational
- [ ] Hybrid retrieval completes in <200ms total
- [ ] Reranking improves relevance by >15% (A/B test)
- [ ] Fallback to coarse results works on exception
- [ ] API endpoints return results in <200ms
- [ ] Top-k results include best matches

## Dependencies

- Plan 04-01 (FastEmbed Integration) must be complete

## Estimated Duration

3-4 hours (service creation + cross-encoder + API + testing)
