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
import logging

logger = logging.getLogger(__name__)

# Check for NumPy availability
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not available, hybrid retrieval will be limited")


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
        # Import EmbeddingService here to avoid circular imports
        from core.embedding_service import EmbeddingService
        self.embedding_service = EmbeddingService(provider="fastembed")
        self._reranker_model = None  # Lazy load cross-encoder

    async def _get_reranker_model(self):
        """Lazy load Sentence Transformer cross-encoder."""
        if self._reranker_model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker_model = CrossEncoder(
                    "BAAI/bge-large-en-v1.5",
                    device="cpu"  # TODO: GPU support
                )
                logger.info("Cross-encoder model loaded: BAAI/bge-large-en-v1.5")
            except ImportError:
                logger.warning("sentence_transformers not available, reranking disabled")
                self._reranker_model = False
            except Exception as e:
                logger.error(f"Failed to load cross-encoder: {e}")
                self._reranker_model = False
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
                # Check if reranker is available
                reranker = await self._get_reranker_model()
                if reranker is False:
                    logger.warning("[HYBRID] Reranking not available, using coarse results only")
                    return [(ep_id, score, "coarse_only") for ep_id, score in coarse_results[:rerank_top_k]]

                logger.info(f"[HYBRID] Stage 2: Reranking top-{min(rerank_top_k, len(coarse_results))}")
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
        from core.models import Episode

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
        if NUMPY_AVAILABLE:
            rerank_scores = (rerank_scores - rerank_scores.min()) / (rerank_scores.max() - rerank_scores.min() + 1e-8)
        else:
            # Python fallback for normalization
            min_score = min(rerank_scores)
            max_score = max(rerank_scores)
            score_range = max_score - min_score + 1e-8
            rerank_scores = [(s - min_score) / score_range for s in rerank_scores]

        # Combine coarse and reranked scores (weighted average)
        # Weight: 30% coarse + 70% reranked (reranking is higher quality)
        combined_scores = []
        for i, (ep_id, coarse_score) in enumerate(candidates):
            if ep_id in episode_map and i < len(rerank_scores):
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
