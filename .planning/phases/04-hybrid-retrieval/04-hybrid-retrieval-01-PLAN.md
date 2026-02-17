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
autonomous: true

must_haves:
  truths:
    - FastEmbed generates 384-dim embeddings in <20ms for coarse search
    - Embeddings are cached in LanceDB on creation to avoid regeneration
    - Top-k coarse search returns exactly k results (default: 100)
    - Dimension mismatch between FastEmbed (384) and Sentence Transformers (1024) is handled
  artifacts:
    - path: "core/embedding_service.py"
      provides: "FastEmbed embedding generation with caching"
      exports: ["generate_embedding", "generate_embeddings_batch", "EmbeddingService"]
    - path: "core/lancedb_handler.py"
      provides: "Vector storage with dual embedding support"
      exports: ["LanceDBHandler", "create_memory_schema"]
    - path: "core/models.py"
      provides: "Database schema for dual embedding columns"
      contains: "vector_fastembed"
  key_links:
    - from: "core/embedding_service.py"
      to: "core/lancedb_handler.py"
      via: "FastEmbed embeddings stored in LanceDB vector_fastembed column"
      pattern: "fastembed.*vector|vector.*fastembed"
---

<objective>
Extend FastEmbed integration for coarse-grained vector search to enable fast initial retrieval before reranking.

Purpose: FastEmbed provides 10-20ms embedding generation with 384-dim vectors, ideal for quickly narrowing down large episode collections before expensive reranking. This two-stage approach (coarse + fine) is the industry standard for production vector search.

Output: Extended EmbeddingService with FastEmbed coarse search, LanceDB dual vector storage, and caching for embeddings.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@core/embedding_service.py (lines 217-275: existing FastEmbed implementation)
@core/lancedb_handler.py (lines 52-56, 189-196: Sentence Transformers integration)
@core/episode_retrieval_service.py (existing retrieval patterns)
@tests/property_tests/episodes/test_episode_retrieval_invariants.py (property test patterns)
</context>

<tasks>

<task type="auto">
  <name>Extend EmbeddingService for coarse-grained search</name>
  <files>core/embedding_service.py</files>
  <action>
    Extend the existing EmbeddingService class to support a two-tier architecture:

    1. Add `coarse_search` method that:
       - Uses FastEmbed (BAAI/bge-small-en-v1.5) for initial retrieval
       - Returns top-k results (configurable, default: 100)
       - Completes in <20ms per the research requirements
       - Takes query: str, top_k: int = 100 parameters

    2. Add `_generate_fastembed_embedding` (already exists at lines 217-251) - extend with:
       - Caching: Store generated embeddings in-memory dict keyed by text hash
       - Cache size limit: 1000 most recent embeddings (LRU eviction)
       - Cache hit logging for performance monitoring

    3. Add `get_coarse_embeddings_batch` method:
       - Batch version of coarse embedding generation
       - Returns List[List[float]] with 384-dim vectors
       - Leverages FastEmbed's efficient batch processing

    Implementation details:
    - FastEmbed model: BAAI/bge-small-en-v1.5 (384 dimensions)
    - DO NOT change the default embedding provider - FastEmbed is already default
    - Cache key: hashlib.sha256(text.encode()).hexdigest()[:16]
    - Logging: Add "cache_hit" and "cache_miss" counters to performance tracking

    Reference existing implementation pattern at lines 217-275.
  </action>
  <verify>
    pytest tests/unit/test_embedding_service.py -v -k "coarse"
  </verify>
  <done>
    - EmbeddingService has coarse_search method returning top-k FastEmbed results
    - Cache is implemented with LRU eviction and hit/miss logging
    - Batch method `get_coarse_embeddings_batch` exists and works
    - All embeddings are 384-dimensional (verified via len(embedding) == 384)
  </done>
</task>

<task type="auto">
  <name>Add dual vector column support to LanceDBHandler</name>
  <files>core/lancedb_handler.py</files>
  <action>
    Extend LanceDBHandler to store both FastEmbed (384-dim) and Sentence Transformers (1024-dim) embeddings:

    1. Update `create_table` method (lines 235-284) to add `vector_fastembed` column:
       - Add pa.field("vector_fastembed", pa.list_(pa.float32(), 384)) to schema
       - Keep existing `vector` column for ST embeddings (1024-dim)
       - Both columns should be nullable for backward compatibility

    2. Add `embed_dual` method:
       - Generates both FastEmbed (384-dim) and ST (1024-dim) embeddings
       - Returns dict with "fastembed" and "st" keys
       - Uses existing `_init_local_embedder` for ST, FastEmbed for coarse

    3. Update `add_document` method (lines 398-518) to:
       - Store FastEmbed embedding in `vector_fastembed` column
       - Keep ST embedding in existing `vector` column
       - Fallback: if ST fails, use FastEmbed for both columns (with warning)

    4. Add `search_coarse` method:
       - Searches using `vector_fastembed` column (384-dim)
       - Returns top-k results (default: 100)
       - ~10-20ms performance target

    Important: Maintain backward compatibility with existing episodes table.
    New columns are nullable - existing records work without migration.
  </action>
  <verify>
    pytest tests/unit/test_lancedb_handler.py -v -k "dual|coarse|fastembed"
  </verify>
  <done>
    - LanceDB schema includes vector_fastembed column (384-dim)
    - embed_dual method generates both embedding types
    - add_document stores both embeddings
    - search_coarse method uses FastEmbed column for fast retrieval
  </done>
</task>

<task type="auto">
  <name>Create migration for dual vector columns</name>
  <files>alembic/versions</files>
  <action>
    Create an Alembic migration to add the FastEmbed vector column to existing tables:

    1. Generate migration: `alembic revision -m "add_fastembed_vector_column"`

    2. Add upgrade/downgrade methods:
       ```python
       def upgrade():
           # Add vector_fastembed column to episodes table in LanceDB
           # Note: LanceDB is external, this is metadata-only migration
           # Actual schema change happens in LanceDBHandler.create_table

       def downgrade():
           # Remove vector_fastembed column (metadata-only)
       ```

    3. Since LanceDB is external, create a database record tracking the schema change:
       - Add to core/models.py: EmbeddingSchemaVersion table
       - Fields: id, table_name, vector_type, dimensions, created_at
       - Seed with fastembed (384) and sentence-transformers (1024) records

    4. Add utility function `ensure_fastembed_schema`:
       - Checks if vector_fastembed column exists
       - Recreates table if needed (LanceDB supports schema evolution)
  </action>
  <verify>
    alembic current
    python -c "from core.models import EmbeddingSchemaVersion; print('OK')"
  </verify>
  <done>
    - Migration file exists for fastembed vector column
    - EmbeddingSchemaVersion model exists with seed data
    - ensure_fastembed_schema utility function exists
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Start Python and test FastEmbed generation:
   ```python
   from core.embedding_service import EmbeddingService
   service = EmbeddingService(provider="fastembed")
   emb = await service.generate_embedding("test query")
   assert len(emb) == 384
   ```

2. Verify dual vector storage:
   ```python
   from core.lancedb_handler import get_lancedb_handler
   handler = get_lancedb_handler()
   # Should have both vector (1024) and vector_fastembed (384) columns
   ```

3. Run performance test:
   ```bash
   python -c "
   import time
   from core.embedding_service import EmbeddingService
   async def test():
       s = EmbeddingService()
       start = time.time()
       for _ in range(10):
           await s.generate_embedding('test')
       print(f'10 embeddings in {time.time()-start:.2f}s')
   import asyncio
   asyncio.run(test())
   "
   # Should complete in <200ms (20ms per embedding)
   ```

4. Verify cache works:
   - Check logs for "cache_hit" after repeated same-text queries
   - Cache should show hit rate >80% for repeated queries
</verification>

<success_criteria>
1. FastEmbed generates 384-dim embeddings in <20ms average
2. EmbeddingService has coarse_search method returning configurable top-k
3. LanceDB tables have both vector (1024-dim ST) and vector_fastembed (384-dim) columns
4. Cache implementation shows hit/miss logging and LRU eviction
5. Migration and schema tracking are in place
6. All existing tests continue to pass (backward compatibility)
</success_criteria>

<output>
After completion, create `.planning/phases/04-hybrid-retrieval/04-hybrid-retrieval-01-SUMMARY.md`
</output>
