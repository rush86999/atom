"""
Policy Search Service - Hybrid vector + text search for governance policies.

This service provides semantic search capabilities for governance documents using:
- PostgreSQL pgvector for similarity search (cosine distance)
- Exact filters: category (domain), tags, status, and verification status
- Query embedding generation via EmbeddingService (local fastembed by default)
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.models import GovernanceDocument

logger = logging.getLogger(__name__)


class PGPolicySearchService:
    """
    PostgreSQL-based hybrid search service for governance policies.
    Adapted for Upstream single-tenant architecture.
    """

    def __init__(self, db: Session):
        """
        Initialize policy search service.
        """
        self.db = db
        # Embeddings go through EmbeddingService, which honors EMBEDDING_PROVIDER
        # (local fastembed by default) and only routes to cloud LLM providers when
        # explicitly configured — the previous direct-LLMService wiring required
        # an OpenAI client and failed on installs without one.
        from core.embedding_service import EmbeddingService
        self.embedding_service = EmbeddingService()

    async def search(
        self,
        tenant_id: str = "default",
        query: str = "",
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        verification_status: Optional[str] = "verified",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: vector similarity + exact filters.

        Args:
            tenant_id: Tenant for isolation (default: "default")
            query: Natural language query
            domain: Filter by category ('hr', 'finance', 'legal')
            tags: Filter by tags (not yet implemented in Upstream schema but placeholder here)
            verification_status: 'verified', 'unverified', 'outdated', or None
            limit: Max results to return

        Returns:
            List of dicts with document + similarity score
        """
        # Step 1: Generate query embedding
        query_embedding = await self._generate_query_embedding(query)

        # SQLite stores aware datetimes without a tz offset (naive on read),
        # so aware bindings never compare correctly on the Personal Edition.
        # Use naive-UTC instants for all SQL comparisons — identical semantics
        # on PostgreSQL (session TZ = UTC), correct string ordering on SQLite.
        now_utc = datetime.now(timezone.utc)
        now_naive = now_utc.replace(tzinfo=None)

        # Step 2: Build SQLAlchemy query with filters
        stmt = select(GovernanceDocument).where(
            GovernanceDocument.status == "approved",
            GovernanceDocument.is_deleted == False,
            # Exclude expired documents
            or_(
                GovernanceDocument.expiration_date.is_(None),
                GovernanceDocument.expiration_date >= now_naive
            )
        )

        # Optional: Domain/Category filter
        if domain:
            stmt = stmt.where(GovernanceDocument.category == domain)

        # Optional: Verification status filter
        if verification_status == "verified":
            # Last verified within 24 hours
            threshold = now_naive - timedelta(hours=24)
            stmt = stmt.where(GovernanceDocument.last_verified >= threshold)
        elif verification_status == "unverified":
            stmt = stmt.where(GovernanceDocument.last_verified.is_(None))
        elif verification_status == "outdated":
            threshold = now_naive - timedelta(hours=24)
            stmt = stmt.where(GovernanceDocument.last_verified < threshold)

        # Step 3: Fetch candidate documents — limit the query itself to avoid
        # loading the entire table into memory (M6 fix). Fetch limit*3 to give
        # the similarity ranking enough headroom, then truncate after sort.
        stmt = stmt.limit(limit * 3)
        results = self.db.execute(stmt).scalars().all()

        # Step 4: Calculate similarity and sort
        documents_with_similarity = []
        for doc in results:
            doc_embedding = doc.embedding
            if isinstance(doc_embedding, str):
                try:
                    doc_embedding = json.loads(doc_embedding)
                except Exception:
                    continue

            # pgvector Vector columns hand back pgvector.Vector/numpy objects,
            # whose truthiness is ambiguous (`if obj` raises) — normalize to a
            # plain list before the emptiness check.
            if doc_embedding is not None and not isinstance(doc_embedding, (list, tuple)):
                try:
                    doc_embedding = doc_embedding.to_list()
                except AttributeError:
                    try:
                        doc_embedding = list(doc_embedding)
                    except TypeError:
                        continue

            if doc_embedding:
                similarity = self._cosine_similarity(doc_embedding, query_embedding)
                documents_with_similarity.append((doc, similarity))

        # Sort by similarity (descending)
        documents_with_similarity.sort(key=lambda x: x[1], reverse=True)

        # Step 5: Format results
        formatted_results = []
        for doc, similarity in documents_with_similarity[:limit]:
            formatted_results.append({
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "category": doc.category,
                "similarity": similarity,
                "verification_status": self._get_verification_status(doc),
                "last_verified": doc.last_verified.isoformat() if doc.last_verified else None
            })

        return formatted_results

    async def _generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate query embedding.
        """
        try:
            return await self.embedding_service.generate_embedding(query)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # No vector → every cosine scores 0.0 (guard in _cosine_similarity),
            # so filtered documents still surface, just unranked.
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        """
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            return float(dot / (norm_v1 * norm_v2))
        except Exception as e:
            logger.error(f"Cosine similarity calculation failed: {e}")
            return 0.0

    def _get_verification_status(self, doc: GovernanceDocument) -> str:
        """
        Compute verification status from last_verified timestamp.
        """
        last_verified = doc.last_verified
        if not last_verified:
            return "unverified"

        # SQLite returns naive datetimes; normalize both sides to naive UTC
        # so the comparison never raises TypeError.
        if last_verified.tzinfo is not None:
            last_verified = last_verified.astimezone(timezone.utc).replace(tzinfo=None)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        hours_since = (now_naive - last_verified).total_seconds() / 3600
        return "outdated" if hours_since > 24 else "verified"
