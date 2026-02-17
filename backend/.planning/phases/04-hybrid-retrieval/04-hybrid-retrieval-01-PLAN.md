---
phase: 04-hybrid-retrieval
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - core/embedding_service.py
  - core/lancedb_handler.py
  - core/models.py
  - alembic/versions/xxx_add_fastembed_vector_column.py
autonomous: true

must_haves:
  truths:
    - "FastEmbed generates 384-dimensional embeddings in <20ms per episode"
    - "Dual vector storage: vector_fastembed (384-dim) + vector (1024-dim ST) in LanceDB"
    - "FastEmbed embeddings cached in LanceDB on episode creation"
    - "Coarse search retrieves top-100 candidates in <20ms"
    - "Dimensionality consistency enforced (384-dim for FastEmbed, 1024-dim for ST)"
    - "LRU cache with 1000-episode limit for FastEmbed embeddings"
  artifacts:
    - path: "core/embedding_service.py"
      provides: "FastEmbed coarse search and caching methods"
      min_lines: 100 (extensions)
    - path: "core/lancedb_handler.py"
      provides: "Dual vector storage support in LanceDB"
      min_lines: 50 (extensions)
    - path: "core/models.py"
      provides: "vector_fastembed column in Episode model"
      min_lines: 20 (extensions)
    - path: "alembic/versions/xxx_add_fastembed_vector_column.py"
      provides: "Database migration for dual vector storage"
      min_lines: 50
  key_links:
    - from: "core/embedding_service.py"
      to: "core/lancedb_handler.py"
      via: "cache_fastembed_embedding() stores in LanceDB"
      pattern: "def cache_fastembed_embedding|def get_fastembed_embedding"
    - from: "core/embedding_service.py"
      to: "core/models.py"
      via: "Episode.vector_fastembed column access"
      pattern: "vector_fastembed"
    - from: "tests/unit/test_hybrid_retrieval.py"
      to: "core/embedding_service.py"
      via: "tests FastEmbed coarse search performance"
      pattern: "test_fastembed_coarse_search|test_fastembed_<20ms"
---

## Objective

Extend existing FastEmbed integration for coarse-grained candidate retrieval with dual vector storage (384-dim FastEmbed + 1024-dim Sentence Transformers) and LRU caching.

**Purpose:** FastEmbed provides sub-20ms coarse search using lightweight 384-dimensional embeddings, enabling rapid candidate filtering before expensive reranking. Dual vector storage allows both FastEmbed and ST embeddings to coexist without dimensionality conflicts.

**Output:** Enhanced EmbeddingService with FastEmbed coarse search, LanceDB dual vector support, Episode model with vector_fastembed column, and database migration.

## Execution Context

@core/embedding_service.py (lines 217-275: existing FastEmbed integration)
@core/lancedb_handler.py (lines 52-56, 189-196: existing ST integration)
@core/models.py (Episode model definition)
@.planning/phases/04-hybrid-retrieval/04-RESEARCH.md

## Context

@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md

# Research Findings (04-RESEARCH.md)
- FastEmbed already installed (fastembed>=0.2.0)
- Existing integration in core/embedding_service.py lines 217-275
- 4 critical pitfalls: dimensionality mismatch, reranking too many, missing fallback, not caching
- Performance target: <20ms for top-100 candidates
- LRU cache with 1000-episode limit recommended

# Phase 3 Complete
- Episode segmentation and retrieval tested (189+ tests)
- Performance target <100ms already met for semantic search
- Canvas-aware and feedback-linked episodes implemented

## Tasks

### Task 1: Add FastEmbed Coarse Search to EmbeddingService

**Files:** `core/embedding_service.py`

**Action:**
Extend EmbeddingService with FastEmbed coarse search methods:

```python
# Add to EmbeddingService class
class EmbeddingService:
    def __init__(self, provider: str = "fastembed"):
        # ... existing init ...
        self._fastembed_cache = LRUCache(maxsize=1000)  # LRU cache
        self._fastembed_model = None  # Lazy load

    async def _get_fastembed_model(self):
        """Lazy load FastEmbed model (Rust ONNX runtime)."""
        if self._fastembed_model is None:
            from fastembed.embedding import TextEmbedding
            self._fastembed_model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                cache_dir="/tmp/fastembed_cache"
            )
        return self._fastembed_model

    async def create_fastembed_embedding(self, text: str) -> np.ndarray:
        """
        Create 384-dimensional FastEmbed embedding.

        Performance: <20ms per embedding
        Dimensions: 384 (BAAI/bge-small-en-v1.5)
        """
        model = await self._get_fastembed_model()
        embeddings = list(model.embed([text]))  # Generator
        return np.array(embeddings[0])  # Shape: (384,)

    async def cache_fastembed_embedding(
        self,
        episode_id: str,
        embedding: np.ndarray,
        db: Session
    ):
        """
        Cache FastEmbed embedding in LanceDB.

        Stores in vector_fastembed column (384-dim).
        Also caches in memory LRU for <10ms retrieval.
        """
        # Store in LanceDB
        lancedb = get_lancedb_handler()
        await lancedb.add_embedding(
            episode_id=episode_id,
            vector=embedding.tolist(),
            vector_column="vector_fastembed"  # NEW column
        )

        # Store in LRU cache
        self._fastembed_cache.put(episode_id, embedding)

    async def get_fastembed_embedding(
        self,
        episode_id: str,
        db: Session
    ) -> Optional[np.ndarray]:
        """Get FastEmbed embedding from cache (LRU → LanceDB)."""
        # Check LRU cache first
        cached = self._fastembed_cache.get(episode_id)
        if cached is not None:
            return cached

        # Fallback to LanceDB
        lancedb = get_lancedb_handler()
        embedding = await lancedb.get_embedding(
            episode_id=episode_id,
            vector_column="vector_fastembed"
        )
        if embedding is not None:
            self._fastembed_cache.put(episode_id, np.array(embedding))
        return embedding

    async def coarse_search_fastembed(
        self,
        agent_id: str,
        query: str,
        top_k: int = 100,
        db: Session
    ) -> List[Tuple[str, float]]:
        """
        FastEmbed coarse search (retrieve top-k candidates).

        Performance: <20ms for top-100 candidates
        Returns: List of (episode_id, similarity_score)
        """
        # Create query embedding
        query_embedding = await self.create_fastembed_embedding(query)

        # Search LanceDB
        lancedb = get_lancedb_handler()
        results = await lancedb.similarity_search(
            vector=query_embedding.tolist(),
            vector_column="vector_fastembed",  # Use 384-dim column
            top_k=top_k,
            agent_id=agent_id
        )

        return [(r["episode_id"], r["score"]) for r in results]
```

**Tests:**
- Verify FastEmbed model loads successfully
- Verify embeddings are 384-dimensional
- Verify coarse search completes in <20ms for top-100

**Acceptance:**
- [ ] FastEmbed embeddings are 384-dimensional
- [ ] create_fastembed_embedding executes in <20ms
- [ ] coarse_search_fastembed returns top-100 in <20ms
- [ ] LRU cache hits logged

---

### Task 2: Extend LanceDBHandler for Dual Vector Storage

**Files:** `core/lancedb_handler.py`

**Action:**
Add dual vector column support (vector_fastembed for 384-dim, vector for 1024-dim):

```python
# Extend LanceDBHandler class
class LanceDBHandler:
    def __init__(self, db_path: str):
        # ... existing init ...
        self.vector_columns = {
            "vector": 1024,  # Sentence Transformers (existing)
            "vector_fastembed": 384  # FastEmbed (NEW)
        }

    async def create_table(self, table_name: str, agent_id: str):
        """Create table with dual vector columns."""
        schema = pydantic.Schema([
            ("episode_id", pydantic.string()),
            ("vector", pydantic.vector(1024)),  # ST embeddings
            ("vector_fastembed", pydantic.vector(384)),  # FastEmbed embeddings
            ("created_at", pydantic.string()),
        ])

        self.db.create_table(
            f"{table_name}_{agent_id}",
            schema=schema
        )

    async def add_embedding(
        self,
        episode_id: str,
        vector: List[float],
        vector_column: str = "vector",  # NEW: parameter
        metadata: dict = None
    ):
        """
        Add embedding to specified vector column.

        Args:
            vector_column: "vector" (1024-dim ST) or "vector_fastembed" (384-dim)
        """
        table = self.db.open_table(self.table_name)

        # Validate dimension
        expected_dim = self.vector_columns[vector_column]
        if len(vector) != expected_dim:
            raise ValueError(
                f"Dimension mismatch: expected {expected_dim}, "
                f"got {len(vector)} for column '{vector_column}'"
            )

        # Add to table
        table.add([
            {
                "episode_id": episode_id,
                vector_column: vector,
                "created_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        ])

    async def similarity_search(
        self,
        vector: List[float],
        vector_column: str = "vector",  # NEW: parameter
        top_k: int = 10,
        agent_id: str = None
    ) -> List[dict]:
        """
        Search specified vector column.

        Args:
            vector_column: "vector" (ST) or "vector_fastembed" (FastEmbed)
        """
        table = self.db.open_table(self.table_name)

        # Validate dimension
        expected_dim = self.vector_columns[vector_column]
        if len(vector) != expected_dim:
            raise ValueError(
                f"Dimension mismatch: expected {expected_dim}, "
                f"got {len(vector)} for column '{vector_column}'"
            )

        # Search
        results = table.search(vector).limit(top_k).to_pydantic()

        return [
            {
                "episode_id": r["episode_id"],
                "score": r["score"],
                "vector_column": vector_column  # Tag results
            }
            for r in results
        ]
```

**Tests:**
- Verify dual vector columns created correctly
- Verify dimension validation enforces 384 vs 1024
- Verify searches use correct vector column

**Acceptance:**
- [ ] vector_fastembed column (384-dim) created
- [ ] vector column (1024-dim) preserved
- [ ] Dimension validation raises ValueError on mismatch
- [ ] similarity_search supports vector_column parameter

---

### Task 3: Add vector_fastembed Column to Episode Model

**Files:** `core/models.py`, `alembic/versions/xxx_add_fastembed_vector_column.py`

**Action:**
Add vector_fastembed column to Episode model for tracking dual embeddings:

```python
# In core/models.py
class Episode(Base):
    __tablename__ = "episodes"

    # ... existing columns ...

    # NEW: FastEmbed vector reference (384-dim)
    # Note: Actual vectors stored in LanceDB, this tracks cache status
    fastembed_cached = Column(Boolean, default=False)
    fastembed_cached_at = Column(DateTime, nullable=True)

    # Existing ST vector reference (1024-dim)
    embedding_cached = Column(Boolean, default=False)
    embedding_cached_at = Column(DateTime, nullable=True)
```

**Create migration:**
```bash
alembic revision -m "add fastembed vector cache tracking"
```

```python
# In alembic/versions/xxx_add_fastembed_vector_column.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('episodes',
        sa.Column('fastembed_cached', sa.Boolean(), nullable=True, server_default='false')
    )
    op.add_column('episodes',
        sa.Column('fastembed_cached_at', sa.DateTime(), nullable=True)
    )

def downgrade():
    op.drop_column('episodes', 'fastembed_cached_at')
    op.drop_column('episodes', 'fastembed_cached')
```

**Tests:**
- Verify migration runs successfully
- Verify Episode model has fastembed_cached columns
- Verify existing episodes have fastembed_cached=False

**Acceptance:**
- [ ] Migration created and applied
- [ ] Episode model has fastembed_cached, fastembed_cached_at
- [ ] Existing episodes have fastembed_cached=False (uncached)

---

## Deviations

**Rule 1 (Auto-fix bugs):** If existing FastEmbed integration has bugs, fix them immediately.

**Rule 2 (Test failures):** If tests fail due to missing dependencies, add to requirements.txt.

**Rule 3 (Performance):** If coarse search exceeds 20ms, optimize or increase LRU cache size.

## Success Criteria

- [ ] FastEmbed embeddings generated in <20ms
- [ ] Dual vector storage operational (384-dim + 1024-dim)
- [ ] Coarse search returns top-100 in <20ms
- [ ] LRU cache with 1000-episode limit
- [ ] Dimension validation prevents mismatches
- [ ] Migration applied successfully

## Dependencies

None (Wave 1 - independent plan)

## Estimated Duration

2-3 hours (implementation + testing + migration)
