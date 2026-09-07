from __future__ import annotations

"""
LanceDB Handler for ATOM Platform
Provides comprehensive vector database operations with LanceDB
"""

import asyncio
import json
import logging
import os
import threading

try:
    import pyarrow as pa
except ImportError:
    pa = None

logger = logging.getLogger(__name__)
# Lazy load Numpy to prevent Windows hang
try:
    import importlib.util

    if importlib.util.find_spec("numpy") is not None:
        NUMPY_AVAILABLE = True
    else:
        NUMPY_AVAILABLE = False
except (ImportError, BaseException) as e:
    NUMPY_AVAILABLE = False
    logger.warning(f"Numpy check failed: {e}")

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Union

from core.doc_freshness_service import FRESHNESS_FILTER_ENABLED

if TYPE_CHECKING:  # pragma: no cover - typing only
    from core.chat_context_manager import ChatContextManager

# Lazy load Pandas to prevent Windows hang
try:
    import importlib.util

    if importlib.util.find_spec("pandas") is not None:
        PANDAS_AVAILABLE = True
    else:
        PANDAS_AVAILABLE = False
except (ImportError, BaseException) as e:
    PANDAS_AVAILABLE = False
    logger.warning(f"Pandas check failed: {e}")

# Lazy load LanceDB (Crucial for Windows hang prevention)
try:
    import importlib.util

    if importlib.util.find_spec("lancedb") is not None:
        LANCEDB_AVAILABLE = True
        # Don't import here, let methods import it locally or use TYPE_CHECKING
    else:
        LANCEDB_AVAILABLE = False
except (ImportError, BaseException) as e:
    LANCEDB_AVAILABLE = False
    logger.warning(f"LanceDB check failed: {e}")

# Define placeholders for type hints

Table = Any
LanceDBConnection = Any

def _resolve_local_db_path(path: str) -> str:
    """Anchor a relative LanceDB path to the backend/ directory.

    Agent memory must not depend on the launch CWD — a root-vs-backend
    launch previously pointed at two different memory stores. Relative
    paths (./data/atom_memory) are written against backend/, the documented
    launch dir; absolute and object-store URIs pass through untouched.
    """
    if not path or os.path.isabs(path) or path.startswith(("s3://", "db://", "gs://")):
        return path
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    )


# Embedded fallback path — used when an S3 URI is supplied but
# LANCEDB_CLOUD_ENABLED=false (Personal Edition). Keeps the two storage modes
# isolated without touching the rest of the handler.
LOCAL_DB_PATH_FALLBACK = _resolve_local_db_path(os.getenv("LANCEDB_URI", "./data/atom_memory"))

# Import sentence transformers for embeddings (Lazy load to prevent Windows hang)
try:
    import importlib.util

    # Check if installed without importing
    if importlib.util.find_spec("sentence_transformers") is not None:
        SENTENCE_TRANSFORMERS_AVAILABLE = True
    else:
        SENTENCE_TRANSFORMERS_AVAILABLE = False
except (ImportError, BaseException) as e:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(f"Sentence transformers check failed: {e}")


# Import OpenAI for embeddings
# Import OpenAI for embeddings (Lazy load)
try:
    import importlib.util

    if importlib.util.find_spec("openai") is not None:
        OPENAI_AVAILABLE = True
    else:
        OPENAI_AVAILABLE = False
except (ImportError, Exception) as e:
    OPENAI_AVAILABLE = False
    logger.warning(f"OpenAI check failed: {e}")


# BYOK Integration
try:
    from core.byok_endpoints import get_byok_manager
except ImportError:
    get_byok_manager = None

# LLMService Integration
try:
    from core.llm_service import LLMService

except ImportError:
    LLMService = None


class MockEmbedder:
    """Deterministic mock embedder for testing when ML libs are missing"""

    def __init__(self, dim):
        self.dim = dim

    def encode(self, text, convert_to_numpy=False):
        # Generate pseudo-random vector based on text hash for consistency
        import hashlib

        hash_val = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        try:
            import numpy as np

            np.random.seed(hash_val % (2**32))
            vec = np.random.rand(self.dim).astype(np.float32)
            # Normalize vector to unit length
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec if convert_to_numpy else vec.tolist()
        except ImportError:
            # Fallback for no numpy
            import math
            import random

            random.seed(hash_val)
            vec = [random.random() for _ in range(self.dim)]
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            return vec


class LanceDBHandler:
    """LanceDB vector database handler with dual vector storage support"""

    def __init__(
        self,
        db_path: str = None,
        workspace_id: Union[str, None] = None,
        tenant_id: Union[str, None] = None,
        db: Any = None,  # SQLAlchemy session for BYOK key lookup
        embedding_provider: str = "fastembed",
        embedding_model: str = "text-embedding-3-small",
    ):
        # Determine DB path (S3 or local)
        self.db_path = _resolve_local_db_path(db_path or os.getenv("LANCEDB_URI", "./data/atom_memory"))

        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"

        # Embedding configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", embedding_provider)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", embedding_model)

        # Dual vector storage configuration: 'vector' (OpenAI default, 1536-dim)
        # and 'vector_fastembed' (FastEmbed, 384-dim — BAAI/bge-small-en-v1.5).
        # EmbeddingService writes/reads the fastembed column for coarse search;
        # dropping it here makes every add_embedding/similarity_search call with
        # vector_column="vector_fastembed" raise ValueError (dual-vector dead).
        self.vector_columns = {
            "vector": 1536,  # OpenAI (default) - text-embedding-3-small
            "vector_fastembed": 384,  # FastEmbed - BAAI/bge-small-en-v1.5
        }

        self.db = None
        self.embedder = None

        # Embeddings go through the dedicated EmbeddingService, which honors
        # EMBEDDING_PROVIDER (Personal Edition default: fastembed, local,
        # 384-dim) and only falls back to LLMService/OpenAI for cloud
        # providers. The previous direct-LLMService wiring ignored the
        # provider setting entirely — every embed attempted OpenAI and failed
        # on installs without an OpenAI key, breaking document ingestion,
        # hybrid search, and Knowledge VFS.
        try:
            from core.embedding_service import EmbeddingService

            # Same resolution as self.embedding_provider above so the vector
            # column dim and the embedder always agree.
            self.embedding_service = EmbeddingService(
                provider=self.embedding_provider
            )
        except Exception as emb_err:
            logger.warning(f"EmbeddingService unavailable: {emb_err}")
            self.embedding_service = None

        logger.info(
            f"LanceDBHandler initialized. ID: {id(self)}. LANCEDB_AVAILABLE: {LANCEDB_AVAILABLE}"
        )
        self.embedder = None

    def _ensure_db(self):
        """Ensure DB is initialized before use"""
        if self.db is None and LANCEDB_AVAILABLE:
            logger.info("Lazy loading LanceDB connection...")
            self._initialize_db()

    def _ensure_embedder(self):
        """Ensure embedder is initialized before use"""
        if self.embedder is None:
            logger.info("Lazy loading embedder on first use...")
            self._initialize_embedder()

    def _initialize_db(self):
        """Initialize LanceDB connection"""
        try:
            # Handle local path creation
            if not self.db_path.startswith("s3://"):
                self.db_path = os.path.abspath(self.db_path)
                # Dangling-symlink probe (2026-09-05): the memory store may
                # live on the portable drive via symlink — if the drive is
                # unplugged, os.makedirs below fails with a cryptic ENOENT.
                # Fail with recovery instructions instead; db stays None so
                # the next call retries automatically once the drive is back.
                _probe = self.db_path
                while _probe != os.path.dirname(_probe):
                    if os.path.islink(_probe) and not os.path.exists(_probe):
                        logger.error(
                            "LanceDB store %s is a DANGLING SYMLINK — external "
                            "drive not mounted. Memory features are disabled "
                            "until the drive is reconnected (then retry "
                            "automatically). Run scripts/drive_status.sh to "
                            "diagnose; data is NOT lost (it lives on the "
                            "drive).", _probe,
                        )
                        raise FileNotFoundError(
                            f"External memory store not mounted: {_probe}"
                        )
                    _probe = os.path.dirname(_probe)
                os.makedirs(self.db_path, exist_ok=True)

            # Connect to database with storage options (required for R2/S3 endpoints)
            # Gated by LANCEDB_CLOUD_ENABLED — Personal Edition (embedded file-based)
            # never evaluates the S3/R2 codepath. SaaS edition flips the flag to true.
            from core.lancedb_config import LANCEDB_CLOUD_ENABLED
            storage_options = {}
            if self.db_path.startswith("s3://") and LANCEDB_CLOUD_ENABLED:
                endpoint = (
                    os.getenv("S3_ENDPOINT")  # R2 endpoint - check FIRST
                    or os.getenv("R2_ENDPOINT")
                    or os.getenv("AWS_ENDPOINT_URL")
                    or os.getenv("AWS_S3_ENDPOINT")
                )

                # Auto-construct Cloudflare R2 endpoint if account ID is present
                if not endpoint:
                    r2_account_id = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID")
                    if r2_account_id:
                        endpoint = f"https://{r2_account_id}.r2.cloudflarestorage.com"

                # MUST have endpoint for R2 - otherwise defaults to AWS S3
                if not endpoint:
                    logger.error(
                        "S3_URI detected but no R2 endpoint configured! Will default to AWS S3 and fail."
                    )
                else:
                    storage_options["endpoint"] = endpoint
                    logger.info(f"Using R2 endpoint: {endpoint}")

                # Use R2 credentials ONLY - no fallback to AWS keys for R2 buckets
                # R2 keys are different from AWS keys and won't work with AWS S3
                access_key = os.getenv("R2_ACCESS_KEY_ID")
                secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

                if not access_key or not secret_key:
                    logger.error(
                        "R2 credentials (R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY) not found!"
                    )
                else:
                    storage_options["aws_access_key_id"] = access_key
                    storage_options["aws_secret_access_key"] = secret_key
                    logger.info(f"Using R2 credentials (key ends with: ...{access_key[-4:]})")

                # R2 doesn't use AWS regions - set to 'auto' or omit
                storage_options["region"] = "auto"

            # Lazy import LanceDB to avoid module-level hang
            import lancedb

            # If db_path looks like S3 but cloud is disabled, downgrade to local
            # embedded storage so Personal Edition never attempts a cloud connect.
            if self.db_path.startswith("s3://") and not LANCEDB_CLOUD_ENABLED:
                logger.warning(
                    "LANCEDB_CLOUD_ENABLED=false — downgrading S3 URI to embedded "
                    "local path %s", LOCAL_DB_PATH_FALLBACK
                )
                self.db_path = os.path.abspath(LOCAL_DB_PATH_FALLBACK)
                os.makedirs(self.db_path, exist_ok=True)

            # For S3-compatible storage (R2), empty dict causes issues
            opts = storage_options if storage_options else None
            logger.info(
                f"Connecting to LanceDB at {self.db_path} with storage_options={list(opts.keys()) if opts else None}"
            )

            self.db = lancedb.connect(self.db_path, storage_options=opts)
            logger.info(f"LanceDB connected successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB at {self.db_path}: {e}")
            self.db = None

    def _initialize_embedder(self):
        """Deprecated. Logic moved to LLMService."""
        pass

    def _init_local_embedder(self):
        """Deprecated. Logic moved to LLMService."""
        pass

    def test_connection(self) -> dict[str, Any]:
        """Test LanceDB connection"""
        if not LANCEDB_AVAILABLE:
            return {"status": "error", "message": "LanceDB not available", "connected": False}

        self._ensure_db()
        try:
            if self.db is None:
                return {"status": "error", "message": "LanceDB not initialized", "connected": False}

            # List tables to test connection
            tables = self.db.table_names()
            return {
                "status": "success",
                "message": "LanceDB connection successful",
                "connected": True,
                "tables": tables,
                "db_path": self.db_path,
                "embedding_provider": self.embedding_provider,
            }

        except Exception as e:
            logger.error(f"LanceDB connection test failed: {e}")
            return {"status": "error", "message": "LanceDB connection test failed", "connected": False}

    def create_table(
        self,
        table_name: str,
        schema: Union[dict[str, Any], None] = None,
        vector_size: Union[int, None] = None,
        dual_vector: bool = False,
        overwrite: bool = False,
    ) -> Union[Table, None]:
        """
        Create a new table.

        Args:
            table_name: Name of the table
            schema: Optional custom schema
            vector_size: Vector size for 'vector' column (default: 1536)
            dual_vector: Accepted for API compatibility with add_embedding

        Returns:
            LanceDB Table object or None if failed
        """
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None

        try:
            if schema is None:
                # Vector column must match the ACTIVE embedding provider's
                # true output dim. When the caller doesn't pin a size, infer
                # it from the provider (fastembed→384, else 1536); an explicit
                # vector_size (e.g. the re-embed migration passing the sample
                # embedding's length) is always honored.
                if vector_size is None:
                    if self.embedding_provider == "fastembed":
                        vector_size = 384
                    else:
                        vector_size = 1536

                # Knowledge-graph tables need the edge columns IN ADDITION to
                # the standard document columns (query_knowledge_graph reads
                # text/source; add_knowledge_edge writes from_id/to_id/type).
                # The old `elif table_name == "knowledge_graph"` branch was
                # unreachable dead code (schema is None always entered the
                # first branch), so KG tables were created with the document
                # schema and every edge insert failed on schema mismatch.
                is_knowledge_graph = table_name == "knowledge_graph"

                fields = [
                    pa.field("id", pa.string()),
                    pa.field("user_id", pa.string()),
                    pa.field("workspace_id", pa.string()),
                    pa.field("text", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("created_at", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), vector_size)),
                ]

                if is_knowledge_graph:
                    fields.extend(
                        [
                            pa.field("from_id", pa.string()),
                            pa.field("to_id", pa.string()),
                            pa.field("type", pa.string()),
                        ]
                    )

                # Freshness columns are top-level and filterable (the search
                # freshness filter reads them natively). New documents tables
                # get them from day one; existing tables are migrated in
                # add_document when an extra column is missing.
                if table_name == "documents":
                    fields.extend(
                        [
                            pa.field("freshness_status", pa.string()),
                            pa.field("source_modified_at", pa.string()),
                            pa.field("source_url", pa.string()),
                        ]
                    )

                if dual_vector:
                    fields.append(
                        pa.field("vector_fastembed", pa.list_(pa.float32(), 384))
                    )

                schema = pa.schema(fields)

            # Create table — CREATE-IF-MISSING, never overwrite. The old
            # mode="overwrite" silently DROPPED an existing table (and every
            # row in it) whenever this method ran against a table that
            # already existed, e.g. on handler re-init after an embedding
            # provider switch. Overwrite is now an explicit opt-in.
            try:
                existing = self.db.open_table(table_name)
            except Exception:
                existing = None

            if existing is not None and not overwrite:
                logger.info(
                    f"Table '{table_name}' already exists — opening it "
                    f"(pass overwrite=True to explicitly reset it)"
                )
                try:
                    self._check_embedding_identity(table_name, existing)
                except Exception:
                    pass
                return existing

            if existing is not None and overwrite:
                self.db.drop_table(table_name)
                logger.warning(f"Table '{table_name}' explicitly reset (overwrite=True)")

            table = self.db.create_table(table_name, schema=schema)
            logger.info(f"Table '{table_name}' created successfully")
            try:
                self._register_identity_from_schema(table_name, table.schema)
            except Exception:
                pass
            return table

        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {e}")
            return None

    def get_table(self, table_name: str) -> Union[Table, None]:
        """Get existing table"""
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None

        try:
            tnames = self.db.table_names()
            if table_name in tnames:
                table = self.db.open_table(table_name)
                # Registry check is a cheap dict compare; it schedules a
                # background re-embed when the active embedding model no
                # longer matches the one that produced the table's vectors.
                try:
                    self._check_embedding_identity(table_name, table)
                except Exception:
                    pass
                return table
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get table '{table_name}': {e}")
            return None

    # ------------------------------------------------------------------
    # Embedding-model identity & background re-embedding migration
    # ------------------------------------------------------------------

    # Migration jobs in flight across ALL handler instances (handlers are
    # created per-request in places; one shared set prevents duplicate work).
    _reembed_inflight: "set[str]" = set()
    _reembed_lock = threading.Lock()

    def _active_embedding_identity(self) -> Dict[str, Any]:
        """The embedder currently in effect (provider/model resolved like
        the vector-column sizing logic in create_table)."""
        provider = self.embedding_provider
        if self.embedding_service is not None:
            svc_provider = getattr(self.embedding_service, "provider", None)
            provider = str(getattr(svc_provider, "value", svc_provider) or provider)
            model = getattr(self.embedding_service, "model", None) or self.embedding_model
        else:
            model = self.embedding_model
        return {"provider": str(provider), "model": str(model)}

    def _register_identity_from_schema(self, table_name: str, schema: Any) -> None:
        """Adopt a table's current schema into the registry (first sighting)."""
        from core import embedding_registry

        if embedding_registry.get(table_name) is not None:
            return
        dim = embedding_registry.dim_from_schema(schema)
        if dim is None:
            return
        active = self._active_embedding_identity()
        embedding_registry.set_identity(
            table_name, active["provider"], active["model"], dim
        )

    def _check_embedding_identity(self, table_name: str, table: "Table") -> None:
        """Compare the table's recorded embedding identity against the
        active embedder; schedule a background re-embed on any mismatch."""
        from core import embedding_registry

        identity = embedding_registry.get(table_name)
        active = self._active_embedding_identity()

        if identity is None:
            self._register_identity_from_schema(table_name, table.schema)
            return

        schema_dim = embedding_registry.dim_from_schema(table.schema)
        state = embedding_registry.classify(
            identity, active["provider"], active["model"], schema_dim
        )
        if state == "match":
            return
        if state == "unregistered":
            self._register_identity_from_schema(table_name, table.schema)
            return

        logger.warning(
            f"Embedding model mismatch for '{table_name}': vectors were built "
            f"with {identity.get('provider')}/{identity.get('model')} "
            f"({identity.get('dim')}-dim) but the active embedder is "
            f"{active['provider']}/{active['model']} ({schema_dim}-dim) — "
            f"re-embedding in the background ({state})"
        )
        self._schedule_reembed(table_name)

    def _schedule_reembed(self, table_name: str) -> None:
        """Kick off a background re-embedding migration, at most one per table."""
        with self._reembed_lock:
            if table_name in LanceDBHandler._reembed_inflight:
                return
            LanceDBHandler._reembed_inflight.add(table_name)
        thread = threading.Thread(
            target=self._reembed_table_worker,
            args=(table_name,),
            daemon=True,
            name=f"reembed-{table_name}",
        )
        thread.start()

    def _reembed_table_worker(self, table_name: str) -> None:
        """Re-embed every row of ``table_name`` with the active embedder.

        Runs on a daemon thread so a model switch never blocks or fails
        requests: the old table keeps serving (stale) vectors until the
        migrated one replaces it. Failures leave the original table intact.
        """
        try:
            self._ensure_db()
            if self.db is None:
                return
            table = self.get_table_nocheck(table_name)
            if table is None:
                return

            # Learn the active embedder's true output dimension from a sample;
            # a dead embedder aborts the migration (original table untouched).
            sample = self.embed_text("embedding model migration probe")
            if not sample:
                logger.error(
                    f"Re-embed of '{table_name}' aborted: active embedder "
                    f"returned no vector"
                )
                return
            target_dim = len(sample)

            rows = table.to_arrow().to_pylist()
            had_dual = any(f.name == "vector_fastembed" for f in table.schema)
            logger.info(
                f"Re-embedding '{table_name}': {len(rows)} rows -> {target_dim}-dim"
            )
            self.db.drop_table(table_name)
            fresh = self.create_table(table_name, vector_size=target_dim, dual_vector=had_dual)
            if fresh is None:
                logger.error(f"Re-embed of '{table_name}' failed: recreate returned None")
                return

            batch: list[dict[str, Any]] = []
            done = 0
            for row in rows:
                text = row.get("text") or row.get("content") or ""
                vec = self.embed_text(text)
                if vec is None or len(vec) != target_dim:
                    vec = [0.0] * target_dim
                row["vector"] = list(vec)
                # Any other vector columns (e.g. vector_fastembed) were built
                # by their own embedder — the values carried over from the old
                # rows are still valid and are preserved untouched.
                batch.append(row)
                if len(batch) >= 100:
                    fresh.add(batch)
                    done += len(batch)
                    batch = []
            if batch:
                fresh.add(batch)
                done += len(batch)

            active = self._active_embedding_identity()
            from core import embedding_registry

            embedding_registry.set_identity(
                table_name, active["provider"], active["model"], target_dim
            )
            logger.info(
                f"Re-embed of '{table_name}' complete: {done} rows at "
                f"{target_dim}-dim ({active['provider']}/{active['model']})"
            )
        except Exception as e:
            logger.error(f"Re-embed of '{table_name}' failed: {e}")
        finally:
            with self._reembed_lock:
                LanceDBHandler._reembed_inflight.discard(table_name)

    def get_table_nocheck(self, table_name: str) -> Union[Table, None]:
        """get_table without the identity check (used by the re-embed worker
        to avoid self-scheduling loops)."""
        self._ensure_db()
        if self.db is None:
            return None
        try:
            if table_name in self.db.table_names():
                return self.db.open_table(table_name)
        except Exception as e:
            logger.error(f"Failed to get table '{table_name}': {e}")
        return None

    @staticmethod
    def _has_column(table: "Table", column_name: str) -> bool:
        """True if a LanceDB table has ``column_name`` in its schema.

        Used by the freshness filter so it only applies to tables that
        actually carry the ``freshness_status`` column (older tables created
        before the feature lack it). Defensive: any error → False.
        """
        try:
            schema = table.schema
            names = {f.name for f in schema}
            return column_name in names
        except Exception:
            return False

    def drop_table(self, table_name: str) -> bool:
        """Drop a table"""
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return False

        try:
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
                logger.info(f"Table '{table_name}' dropped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to drop table '{table_name}': {e}")
            return False

    def _table_vector_size(self, table) -> Union[int, None]:
        """Fixed size of the table's 'vector' column, or None when the schema
        carries no fixed-size vector (or the table can't be introspected)."""
        try:
            for f in table.schema:
                if f.name == "vector" and hasattr(f.type, "list_size"):
                    return f.type.list_size
        except Exception:
            pass
        return None

    def embed_text(self, text: str) -> Union[Any, None]:
        """
        Embed text using unified LLMService.
        Sync version for legacy compatibility.

        Thread-safe: Can be called from any context (sync, async, thread executor).
        """
        if not self.embedding_service:
            logger.error("EmbeddingService not initialized")
            return None

        import asyncio

        # get_running_loop() only succeeds in the loop's OWN thread, so a
        # result means "called from the event-loop thread" — no separate
        # thread-id comparison exists or is needed. (The old
        # `loop._thread_id` probe crashed with AttributeError on uvloop,
        # which uvicorn runs, turning the async-context guard into an
        # embed failure on every production request.) On the loop thread
        # this shim must not block the loop: async callers go through
        # async_embed_text, or run this method via asyncio.to_thread.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            try:
                return asyncio.run(self.async_embed_text(text))
            except Exception as e:
                logger.error(f"Failed to embed text (sync): {e}")
                return None
        logger.warning(
            "embed_text (sync) called from the event-loop thread; returning "
            "None. Use async_embed_text or wrap in asyncio.to_thread."
        )
        return None

    async def async_embed_text(self, text: str) -> Union[Any, None]:
        """
        Embed text using unified LLMService.
        Recommended async version.
        """
        if not self.embedding_service:
            logger.error("EmbeddingService not initialized")
            return None

        try:
            embedding = await self.embedding_service.generate_embedding(text)
            if NUMPY_AVAILABLE:
                import numpy as np

                return np.array(embedding)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def add_knowledge_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        description: str = "",
        metadata: dict[str, Any] = None,
        user_id: str = "default_user",
    ) -> bool:
        """Add a relationship edge to the knowledge graph"""
        if self.db is None:
            return False

        try:
            table_name = "knowledge_graph"
            table = self.get_table(table_name)
            if table is None:
                table = self.create_table(table_name)
                if table is None:
                    return False

            # Generate embedding of the relationship description
            embedding = self.embed_text(description)
            vector_size = self._table_vector_size(table)
            if vector_size is None:
                vector_size = self.vector_columns.get("vector_fastembed", 384) \
                    if "fastembed" in str(self.embedding_provider).lower() else 1536
            if embedding is None:
                # Embedding failed (dead embedder / event-loop sync call).
                # The zero-vector fallback MUST match the table's fixed-size
                # vector column — a hardcoded 1536 against a 384-dim table
                # failed the FixedSizeList cast and silently dropped the edge.
                logger.warning(
                    f"add_knowledge_edge: embed failed, writing {vector_size}-dim "
                    "zero vector (edge unsearchable until re-embedded)"
                )
                embedding = [0.0] * vector_size
            elif hasattr(embedding, "__len__") and len(embedding) != vector_size:
                # A SUCCESSFUL embed with the wrong dimension fails the same
                # cast at table.add() (LanceError Arrow: "ListType can only
                # be casted to FixedSizeListType…" — live 2026-09-03, edges
                # dropped on every write while the embedder/table dims
                # disagreed). Align to the table; the edge stays writable.
                logger.warning(
                    f"add_knowledge_edge: embed dim {len(embedding)} != table "
                    f"dim {vector_size} — resizing (edge unsearchable until "
                    "re-embedded at the table's dim)"
                )
                embedding = (list(embedding) + [0.0] * vector_size)[:vector_size]

            # Create unique edge ID
            edge_id = f"{from_id}_{rel_type}_{to_id}"

            if metadata is None:
                metadata = {}

            # Create record (includes the standard columns so the record is
            # schema-complete for the knowledge_graph table)
            record = {
                "id": edge_id,
                "user_id": user_id,
                "workspace_id": self.workspace_id,
                "text": description,
                "source": "knowledge_graph",
                "from_id": from_id,
                "to_id": to_id,
                "type": rel_type,
                "metadata": json.dumps(metadata),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "vector": embedding.tolist() if hasattr(embedding, "tolist") else embedding,
            }

            # Add to table
            table.add([record])
            logger.info(f"Knowledge edge added: {edge_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add knowledge edge: {e}")
            return False

    def add_document(
        self,
        table_name: str,
        text: str,
        source: str = "",
        metadata: dict[str, Any] = None,
        user_id: str = "default_user",
        workspace_id: Union[str, None] = None,
        doc_id: Union[str, None] = None,
        skip_ai_triggers: bool = False,
        extra_columns: Union[dict[str, Any], None] = None,
    ) -> bool:
        """
        Add a single document to memory

        Args:
            table_name: Name of the table to add document to
            text: Document text content
            source: Source of the document
            metadata: Optional metadata dictionary (serialized to JSON — NOT
                natively filterable; use ``extra_columns`` for fields you need
                to prefilter on, like ``outcome`` or ``agent_id``).
            user_id: User ID who owns the document
            workspace_id: Workspace ID
            doc_id: Optional document ID (will generate if not provided)
            skip_ai_triggers: If True, skip AI trigger coordinator and workflow triggers
                             (Use for system-generated updates to prevent loops)
            extra_columns: Optional dict of top-level columns merged into the
                record. These ARE natively filterable via ``filter_str`` (e.g.
                ``outcome``, ``agent_id``) — the discriminator fields that
                LanceDB prefilters on before vector search. Required for the
                outcome-prefilter pattern (cosine cannot separate pass/fail).
        """
        if self.db is None:
            self._ensure_db()
        if self.db is None:
            return False

        try:
            table = self.get_table(table_name)
            # If table is None, we will create it later with data to infer schema

            # SECURITY: Redact secrets before storage
            # This ensures API keys, passwords, and PII are NEVER stored in Atom Memory
            try:
                from core.secrets_redactor import get_secrets_redactor

                redactor = get_secrets_redactor()
                redaction_result = redactor.redact(text)

                if redaction_result.has_secrets:
                    logger.warning(
                        f"Redacted {len(redaction_result.redactions)} secrets/PII before storage"
                    )
                    text = redaction_result.redacted_text

                    # Add redaction metadata for audit
                    if metadata is None:
                        metadata = {}
                    metadata["_redacted_types"] = [r["type"] for r in redaction_result.redactions]
                    metadata["_redaction_count"] = len(redaction_result.redactions)
            except ImportError:
                logger.warning("Secrets redactor not available, storing text as-is")
            except Exception as redact_err:
                logger.error(f"Secrets redaction failed: {redact_err}, proceeding with caution")

            # Guard: don't embed empty/whitespace text. After redaction (or for
            # empty input), text may be "" — embedding it wastes an API call and
            # produces a junk near-zero vector that pollutes vector search (BUG-043).
            if not text or not text.strip():
                logger.warning("Skipping embedding for empty/redacted-to-empty text")
                return False

            # Generate embedding
            embedding = self.embed_text(text)
            if embedding is None:
                return False

            # Use provided doc_id or generate new one
            if doc_id is None:
                doc_id = str(datetime.now(timezone.utc).timestamp())

            # Record with user_id and workspace_id
            # Record with user_id and workspace_id

            # Serialize metadata to ensure schema flexibility (String instead of inferred Struct)
            import json

            serialized_metadata = json.dumps(metadata if metadata else {})

            record = {
                "id": doc_id,
                "user_id": user_id,
                "workspace_id": workspace_id or self.workspace_id,
                "text": text,
                "source": source,
                "metadata": serialized_metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "vector": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
            }
            # Top-level filterable columns (outcome, agent_id, …). These must
            # be real columns — NOT inside the serialized metadata JSON — so
            # LanceDB can prefilter on them natively before vector search.
            if extra_columns:
                for k, v in extra_columns.items():
                    record[k] = v

            # Add to table
            try:
                table = self.get_table(table_name)
                if table is None:
                    # Create with the explicit schema (vector column sized to
                    # the active embedding provider). Inferring from a plain
                    # record fails: LanceDB cannot derive a FixedSizeList
                    # vector column from a Python list of floats.
                    table = self.create_table(table_name)
                if table is not None:
                    # Tables created before a top-level column existed (e.g.
                    # freshness_* on pre-feature documents tables) reject the
                    # write with "Field ... not found in target schema" —
                    # migrate them instead of losing the row.
                    if extra_columns:
                        missing = [
                            k
                            for k in extra_columns
                            if not self._has_column(table, k)
                        ]
                        if missing:
                            try:
                                table.add_columns({k: "''" for k in missing})
                                logger.info(
                                    f"Added missing column(s) {missing} to '{table_name}'"
                                )
                            except Exception as col_err:
                                logger.warning(
                                    f"Could not migrate columns {missing} on "
                                    f"'{table_name}': {col_err}"
                                )
                    table.add([record])
                else:
                    return False
                logger.info(f"Document added to '{table_name}': {doc_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to add document to LanceDB: {e}")
                return False

        except Exception as e:
            logger.error(f"Failed to add document to '{table_name}': {e}")
            return False

    def _add_document_with_embedding(
        self,
        table_name: str,
        text: str,
        embedding: "list[float]",
        source: str = "",
        metadata: dict = None,
        user_id: str = "default_user",
        workspace_id: str = None,
    ) -> bool:
        """Add a document with a pre-computed embedding. Thread-safe.

        Separates embedding generation (async, needs DB session) from
        LanceDB write (sync, can run in thread executor).
        """
        if self.db is None:
            self._ensure_db()
        if self.db is None:
            return False

        try:
            import json
            from datetime import datetime, timezone

            doc_id = str(datetime.now(timezone.utc).timestamp())
            serialized_metadata = json.dumps(metadata if metadata else {})

            record = {
                "id": doc_id,
                "user_id": user_id,
                "workspace_id": workspace_id or self.workspace_id,
                "text": text,
                "source": source,
                "metadata": serialized_metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "vector": list(embedding),
            }

            table = self.get_table(table_name)
            if table is None:
                # Explicit schema (provider-sized vector column) — inferred
                # creation cannot derive a FixedSizeList from Python lists.
                table = self.create_table(table_name)
            if table is not None:
                table.add([record])
            else:
                return False
            logger.info(f"Document added to '{table_name}': {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add document to '{table_name}': {e}")
            return False

    def add_documents_batch(self, table_name: str, documents: list[dict[str, Any]]) -> int:
        """Add multiple documents in batch"""
        if self.db is None:
            self._ensure_db()
        if self.db is None:
            return 0

        try:
            # Prepare batch records first to allow schema inference
            records = []
            for doc in documents:
                text = doc.get("text", "")
                source = doc.get("source", "")
                metadata = doc.get("metadata", {})
                doc_id = doc.get("id", str(datetime.now(timezone.utc).timestamp()))
                user_id = doc.get("user_id", "default_user")

                # Generate embedding
                embedding = self.embed_text(text)
                if embedding is None:
                    continue

                # Prepare record — same field contract as add_document
                # (metadata serialized; extra_columns merged TOP-LEVEL so
                # appends against the freshness_* schema don't fail).
                record = {
                    "id": doc_id,
                    "user_id": user_id,
                    "workspace_id": self.workspace_id,
                    "text": text,
                    "source": source,
                    "metadata": metadata if isinstance(metadata, str) else json.dumps(metadata),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "vector": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
                }
                extra = doc.get("extra_columns")
                if isinstance(extra, dict):
                    record.update(extra)
                records.append(record)

            if not records:
                return 0

            # Get or Create Table
            table = self.get_table(table_name)
            if table is None:
                # Create with the explicit provider-sized schema first; fall
                # back to data-inference only for custom/extra columns the
                # standard schema doesn't cover.
                table = self.create_table(table_name)
                try:
                    if table is not None:
                        table.add(records)
                        logger.info(f"Created table '{table_name}' and added {len(records)} documents")
                        return len(records)
                    table = self.db.create_table(table_name, data=records)
                    logger.info(f"Created table '{table_name}' with inferred schema")
                    return len(records)
                except Exception as create_err:
                    logger.error(f"Failed to create table '{table_name}': {create_err}")
                    return 0

            # Add to existing
            table.add(records)
            logger.info(f"Added {len(records)} documents to '{table_name}'")
            return len(records)

        except Exception as e:
            logger.error(f"Failed to add batch documents to '{table_name}': {e}")
            return 0

    def search(
        self,
        table_name: str,
        query: str,
        user_id: str = None,
        limit: int = 10,
        filter_str: str = None,
        include_stale: bool = False,
    ) -> list[dict[str, Any]]:
        """Search for documents in memory with optional user filtering.

        Freshness filter: when ``table_name == 'documents'`` and the freshness
        feature is enabled (``ATOM_FRESHNESS_FILTER_ENABLED``, default true),
        rows with a non-fresh ``freshness_status`` (stale/outdated/removed/
        superseded) are excluded from results by default. Pass
        ``include_stale=True`` to surface them (admin/observability). See
        core/doc_freshness_service.py.
        """
        self._ensure_db()
        if self.db is None:
            return []

        try:
            table = self.get_table(table_name)
            if table is None:
                return []

            # Generate embedding for query
            query_vector = self.embed_text(query)
            if query_vector is None:
                return []

            # Build search query (embed_text may return a list or numpy array)
            qv = query_vector.tolist() if hasattr(query_vector, "tolist") else list(query_vector)
            search_query = table.search(qv).limit(limit)

            # Apply workspace_id and user_id filter.
            # SECURITY: escape single quotes to prevent filter injection.
            filters = []

            # 1. Enforce Workspace Isolation
            if self.workspace_id:
                # LanceDB/DataFusion SQL string literals escape single quotes
                # by doubling them (''), NOT backslash-escaping (\''). The
                # latter either breaks the filter (parse error → empty results)
                # or can terminate the literal early. Matches _escape_like.
                safe_ws = str(self.workspace_id).replace("'", "''")
                filters.append(f"workspace_id == '{safe_ws}'")

            # 2. Apply User Filter
            if user_id:
                safe_user = str(user_id).replace("'", "''")
                filters.append(f"user_id == '{safe_user}'")

            # 3. Apply Custom Filter
            if filter_str:
                filters.append(f"({filter_str})")

            # 4. Freshness filter — only on the documents table, and only if
            # the table actually has the column (older LanceDB tables created
            # before this feature lack ``freshness_status``). We check the
            # schema defensively so this never breaks pre-existing tables.
            if (
                FRESHNESS_FILTER_ENABLED
                and table_name == "documents"
                and not include_stale
                and self._has_column(table, "freshness_status")
            ):
                filters.append("freshness_status == 'fresh'")

            # Combine all
            final_filter = " AND ".join(filters)

            if final_filter:
                search_query = search_query.where(final_filter)

            # Execute search
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for search results")
                return []
            results = (
                search_query.to_pandas()
            )  # Changed from `search_results = results.to_pandas()`

            # Convert to list of dictionaries
            results_list = []
            for _, row in results.iterrows():
                try:
                    # Metadata is now a Struct (dict), no need to json.loads if it's already a dict
                    metadata = row["metadata"]
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {}

                    result = {
                        "id": row["id"],
                        "text": row["text"],
                        "source": row["source"],
                        "metadata": metadata,
                        "created_at": row["created_at"],
                        "score": max(0.0, 1.0 - row.get("_distance", 2.0)),  # Clamp to [0,1]
                    }
                    results_list.append(result)
                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue

            return results_list

        except Exception as e:
            logger.error(f"Failed to search in '{table_name}': {e}")
            return []

    def list_document_heads(self, table_name: str, limit: int = 200) -> list[dict[str, Any]]:
        """List lightweight heads ({id, metadata, created_at}) without vectors.

        Used by the Knowledge VFS to surface vector-only rows (no PG mirror)
        in ``ls`` output. Metadata is parsed like :meth:`get_document_by_id`.
        """
        self._ensure_db()
        if self.db is None:
            return []

        try:
            table = self.get_table(table_name)
            if table is None:
                return []
            df = table.to_arrow().select(["id", "metadata", "created_at"]).to_pandas()
            if df.empty:
                return []

            heads: list[dict[str, Any]] = []
            for _, row in df.head(limit).iterrows():
                metadata = row.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}
                elif metadata is None:
                    metadata = {}
                heads.append({
                    "id": row["id"],
                    "metadata": metadata,
                    "created_at": row.get("created_at", ""),
                })
            return heads
        except Exception as e:
            logger.error(f"Failed to list heads in '{table_name}': {e}")
            return []

    def get_document_by_id(self, table_name: str, doc_id: str) -> Union[dict[str, Any], None]:
        """Retrieve a single document by ID"""
        self._ensure_db()
        if self.db is None:
            return None

        try:
            table = self.get_table(table_name)
            if table is None:
                return None

            # Arrow filter, NOT table.search(): this is a point lookup —
            # routing it through the kNN query builder can bind the embedding
            # machinery (seconds per call, or a hang when no client is
            # configured) and never needs the vector column anyway.
            # SECURITY: pc.equal is a parameterized comparison — values are
            # matched as-is, so the old SQL-style quote-doubling must NOT be
            # applied here (it would make a quoted doc_id unmatchable).
            import pyarrow.compute as _pc

            arrow = table.to_arrow().select(["id", "text", "source", "metadata", "created_at"])
            rows = arrow.filter(_pc.equal(arrow.column("id"), str(doc_id))).to_pylist()

            if not rows:
                return None

            row = rows[0]
            metadata = row.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:                     metadata = {}
            elif metadata is None:
                metadata = {}

            return {
                "id": row["id"],
                "text": row["text"],
                "source": row.get("source", ""),
                "metadata": metadata,
                "created_at": row.get("created_at", ""),
                "vector": [],
            }
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    def get_document_ids_by_prefix(self, table_name: str, prefix: str) -> list[str]:
        """All row ids whose id starts with ``prefix``.

        Chunk families ({doc_id}::c0, ::c1, …) need family-wide deletes on
        re-ingest; id equality alone can't find them. Small tables — full
        scan is fine (documents ≈ thousands of rows).
        """
        self._ensure_db()
        if self.db is None:
            return []
        try:
            table = self.get_table(table_name)
            if table is None:
                return []
            ids = table.to_arrow().column("id").to_pylist()
            return [str(i) for i in ids if str(i).startswith(prefix)]
        except Exception as e:
            logger.error(f"Failed to list ids by prefix in '{table_name}': {e}")
            return []

    def delete_documents_by_id(self, table_name: str, doc_id: str) -> bool:
        """Delete ALL rows whose id equals ``doc_id`` from a table.

        LanceDB ``table.add`` is append-only, so re-ingesting the same doc_id
        (fact versioning, re-uploads) leaves multiple rows — this removes
        every version. Returns True if the delete call succeeded (including
        zero matches); False on error. Call from a worker thread when the
        table's embedding path may be touched.
        """
        self._ensure_db()
        if self.db is None:
            return False

        try:
            table = self.get_table(table_name)
            if table is None:
                return False
            safe_doc_id = str(doc_id).replace("'", "''")
            table.delete(f"id = '{safe_doc_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from '{table_name}': {e}")
            return False

    def delete_documents_by_prefix(self, table_name: str, id_prefix: str) -> bool:
        """Delete all rows whose id starts with ``id_prefix`` — ONE predicate
        delete, one transaction.

        The per-id loop this replaces (chunk families: {doc}::c0..c3400) cost
        a separate table rewrite per id — ~3.4k transactions, observed at
        25-90+ minutes under concurrent-writer contention before a re-ingest
        could even start adding rows (live 2026-09-04, Consolidated Price
        List 2019.xlsx ev4 refresh). """
        self._ensure_db()
        if self.db is None:
            return False

        try:
            table = self.get_table(table_name)
            if table is None:
                return False
            safe_prefix = str(id_prefix).replace("\\", "\\\\").replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            table.delete(f"id LIKE '{safe_prefix}%'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete documents by prefix {id_prefix} from '{table_name}': {e}")
            return False

    def list_documents(
        self, table_name: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List documents (recent first)"""
        self._ensure_db()
        if self.db is None:
            return []

        try:
            table = self.get_table(table_name)
            if table is None:
                return []

            # Retrieve all (or limit) and sort by created_at desc if possible
            # LanceDB might not support efficient global sorting without an index,
            # so we fetch and sort in memory for small batches
            df = table.search().limit(limit + offset).to_pandas()

            if df.empty:
                return []

            # Sort by created_at if available
            if "created_at" in df.columns:
                df = df.sort_values("created_at", ascending=False)

            # Apply offset/limit
            df = df.iloc[offset : offset + limit]

            docs = []
            for _, row in df.iterrows():
                metadata = row.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:                         metadata = {}
                elif metadata is None:
                    metadata = {}

                docs.append(
                    {
                        "id": row["id"],
                        "title": metadata.get("title") or row.get("source") or "Untitled",
                        "text_preview": (row["text"] or "")[:200],
                        "metadata": metadata,
                        "created_at": row.get("created_at", ""),
                    }
                )

            return docs

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def query_knowledge_graph(
        self,
        query: str,
        user_id: str = None,
        limit: int = 20,
        exclude_source_doc_ids: Union[set[str], None] = None,
    ) -> list[dict[str, Any]]:
        """Search the knowledge graph using semantic similarity on relationship descriptions.

        ``exclude_source_doc_ids`` hides edges whose origin document has gone
        stale/superseded/removed — the freshness cascade for this LanceDB edge
        store. Callers pass the set of IngestedDocument ids that are currently
        non-fresh; edges whose ``metadata.doc_id`` is in that set are filtered
        out after the vector search. See core/doc_freshness_service.py.

        NOTE: GraphRAG proper lives in PostgreSQL (graph_nodes/graph_edges),
        which carries provenance in ``properties->>'doc_id'`` and is cascaded
        separately via the freshness service's Postgres path.
        """
        results = self.search("knowledge_graph", query, limit=limit)
        if not exclude_source_doc_ids:
            return results
        excluded = {str(x) for x in exclude_source_doc_ids}
        out = []
        for r in results:
            meta = r.get("metadata") or {}
            src = meta.get("doc_id") if isinstance(meta, dict) else None
            if src and str(src) in excluded:
                continue
            out.append(r)
        return out

    def seed_mock_data(self, documents: list[dict[str, Any]]) -> int:
        """Seed mock data for validation"""
        return self.add_documents_batch("documents", documents)

    # ========================================================================
    # Dual Vector Storage Methods (NEW - Phase 4)
    # ========================================================================

    async def add_embedding(
        self,
        table_name: str,
        episode_id: str,
        vector: list[float],
        vector_column: str = "vector",
        metadata: Union[dict[str, Any], None] = None,
    ) -> bool:
        """
        Add embedding to specified vector column.

        Args:
            table_name: Name of the table
            episode_id: Episode/document ID
            vector: Embedding vector
            vector_column: "vector" (1024-dim ST) or "vector_fastembed" (384-dim FastEmbed)
            metadata: Optional metadata dictionary

        Returns:
            True if successful

        Raises:
            ValueError: If dimension mismatch
        """
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return False

        try:
            # Validate dimension
            expected_dim = self.vector_columns.get(vector_column)
            if expected_dim is None:
                raise ValueError(
                    f"Unknown vector column: '{vector_column}'. "
                    f"Valid options: {list(self.vector_columns.keys())}"
                )

            if len(vector) != expected_dim:
                raise ValueError(
                    f"Dimension mismatch for column '{vector_column}': "
                    f"expected {expected_dim}, got {len(vector)}"
                )

            # Get or create table
            table = self.get_table(table_name)
            if table is None:
                # Create table with dual vector support
                table = self.create_table(table_name, dual_vector=True)
                if table is None:
                    logger.error(f"Failed to create table '{table_name}'")
                    return False

            # Create record
            record = {
                "id": episode_id,
                "user_id": metadata.get("user_id", "default") if metadata else "default",
                "workspace_id": self.workspace_id,
                "text": metadata.get("text", "") if metadata else "",
                "source": metadata.get("source", "episode") if metadata else "episode",
                "metadata": json.dumps(metadata) if metadata else "{}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                vector_column: vector,  # Add to specified vector column
            }

            # Add to table
            table.add([record])
            logger.debug(
                f"Added embedding to '{table_name}' (column: {vector_column}, "
                f"dim: {len(vector)}, episode: {episode_id})"
            )
            return True

        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Failed to add embedding: {e}")
            return False

    async def similarity_search(
        self,
        table_name: str,
        vector: list[float],
        vector_column: str = "vector",
        top_k: int = 10,
        agent_id: Union[str, None] = None,
    ) -> list[dict[str, Any]]:
        """
        Search specified vector column for similar vectors.

        Args:
            table_name: Name of the table
            vector: Query vector
            vector_column: "vector" (ST) or "vector_fastembed" (FastEmbed)
            top_k: Number of results to return
            agent_id: Optional agent filter

        Returns:
            List of results with episode_id and score

        Raises:
            ValueError: If dimension mismatch
        """
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return []

        try:
            # Validate dimension
            expected_dim = self.vector_columns.get(vector_column)
            if expected_dim is None:
                raise ValueError(
                    f"Unknown vector column: '{vector_column}'. "
                    f"Valid options: {list(self.vector_columns.keys())}"
                )

            if len(vector) != expected_dim:
                raise ValueError(
                    f"Dimension mismatch for column '{vector_column}': "
                    f"expected {expected_dim}, got {len(vector)}"
                )

            # Get table
            table = self.get_table(table_name)
            if table is None:
                logger.warning(f"Table '{table_name}' not found")
                return []

            # Search
            results = table.search(vector).limit(top_k).to_pandas()

            # Convert to list of dictionaries
            results_list = []
            for _, row in results.iterrows():
                try:
                    result = {
                        "episode_id": row.get("id", row.get("episode_id", "")),
                        "score": 1.0 - row.get("_distance", 0.0),  # Convert distance to similarity
                        "vector_column": vector_column,  # Tag results with source column
                        "_distance": row.get("_distance", 0.0),
                    }
                    results_list.append(result)
                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue

            logger.debug(
                f"Similarity search on '{table_name}' (column: {vector_column}, "
                f"results: {len(results_list)})"
            )
            return results_list

        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise
        except Exception as e:
            logger.error(f"Failed to search '{table_name}': {e}")
            return []

    async def get_embedding(
        self, table_name: str, episode_id: str, vector_column: str = "vector"
    ) -> Union[list[float], None]:
        """
        Get embedding for a specific episode from specified column.

        Args:
            table_name: Name of the table
            episode_id: Episode ID
            vector_column: "vector" or "vector_fastembed"

        Returns:
            Embedding vector or None if not found
        """
        self._ensure_db()
        if self.db is None:
            logger.error("LanceDB not initialized")
            return None

        try:
            table = self.get_table(table_name)
            if table is None:
                return None

            # Query by ID (escape single quotes to prevent filter injection,
            # matching get_document_by_id)
            safe_episode_id = str(episode_id).replace("'", "''")
            results = (
                table.search()
                .where(f"id == '{safe_episode_id}'")
                .limit(1)
                .to_pandas()
            )

            if results.empty:
                return None

            # Extract vector from specified column
            vector = results.iloc[0].get(vector_column)
            if vector is not None:
                return vector.tolist() if hasattr(vector, "tolist") else vector

            return None

        except Exception as e:
            logger.error(f"Failed to get embedding for {episode_id}: {e}")
            return None


# Chat History Extension for LanceDBHandler
class ChatHistoryManager:
    """Manages chat history using LanceDB for semantic search"""

    def __init__(self, lancedb_handler: LanceDBHandler):
        self.db = lancedb_handler
        self.table_name = "chat_messages"
        self._ensure_table()

    def _ensure_table(self):
        """Ensure chat_messages table exists"""
        if self.db.db is None:
            logger.warning("LanceDB not initialized, chat history disabled")
            return

        try:
            # Create table if it doesn't exist
            if self.table_name not in self.db.db.table_names():
                self.db.create_table(self.table_name)
                logger.info("Created chat_messages table")
        except Exception as e:
            logger.error(f"Failed to ensure chat_messages table: {e}")

    def save_message(
        self,
        session_id: str,
        user_id: str,
        role: str,  # "user" or "assistant"
        content: str,
        metadata: dict[str, Any] = None,
    ) -> bool:
        """
        Save a chat message with automatic embedding.

        metadata can include:
        - intent: str
        - entities: dict (workflow_ids, task_ids, etc.)
        - workflow_id: str
        - task_id: str
        - schedule_id: str
        """
        if self.db.db is None:
            logger.error("save_message: DB is None")
            return False

        try:
            logger.info(f"save_message: Saving {role} message for session {session_id}")
            # Prepare metadata
            msg_metadata = metadata or {}
            msg_metadata.update({"session_id": session_id, "user_id": user_id, "role": role})

            # Create unique message ID
            message_id = f"{session_id}_{datetime.now(timezone.utc).timestamp()}"

            # Save using existing add_document method
            success = self.db.add_document(
                table_name=self.table_name,
                text=content,
                source=f"chat_{role}",
                metadata=msg_metadata,
                doc_id=message_id,
            )

            if success:
                logger.debug(f"Saved chat message: {message_id}")
            return success

        except Exception as e:
            logger.error(f"Failed to save chat message: {e}")
            return False

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape a value for safe interpolation into a LanceDB LIKE filter.

        Prevents filter-syntax injection / broken filters when the value (e.g. a
        session_id) contains a quote or %/_ wildcard char. ``%`` and ``_`` are
        escaped so they match literally inside a LIKE clause (otherwise a
        session_id like ``abc_1`` would match ``abcX1`` and leak cross-session
        results through the substring pre-filter).
        """
        # Backslash FIRST so we don't double-escape the escapes we add below.
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("'", "''")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

    def get_session_history(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Retrieve recent messages from a session (chronological order).

        Returns list of messages with:
        - id, text, source, role, created_at, metadata
        """
        if self.db is None or self.db.db is None:
            return []

        try:
            table = self.db.get_table(self.table_name)
            if table is None:
                return []

            # LanceDB has no built-in chronological ordering, so we fetch and
            # sort in memory. The previous `.limit(limit * 2)` fetched an
            # arbitrary (insertion-order) slice and could MISS the newest
            # messages for long sessions — returning a stale window. Fetch a
            # generous bounded window so the in-memory sort + slice actually
            # sees the recent messages.
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for session history")
                return []
            safe_sid = self._escape_like(session_id)
            # Fetch a wide window (capped) so we capture the newest messages.
            fetch_window = max(limit * 10, 200)
            results = (
                table.search().where(f"metadata LIKE '%{safe_sid}%'").limit(fetch_window).to_pandas()
            )

            # Parse and filter
            messages = []
            for _, row in results.iterrows():
                try:
                    metadata = row["metadata"]
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {}

                    # Exact session_id match (the LIKE filter is a substring
                    # pre-filter; this guards against session_id prefixes
                    # colliding, e.g. 'abc' matching 'abcdef').
                    if metadata.get("session_id") == session_id:
                        messages.append(
                            {
                                "id": row["id"],
                                "text": row["text"],
                                "role": metadata.get("role", "unknown"),
                                "created_at": row["created_at"],
                                "metadata": metadata,
                            }
                        )
                except Exception as e:
                    logger.warning(f"Error parsing message: {e}")
                    continue

            # Sort by created_at (oldest→newest), then take the newest `limit`.
            messages.sort(key=lambda x: x["created_at"])

            return messages[-limit:]  # most recent

        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    def search_relevant_context(
        self, query: str, session_id: str = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Find semantically similar messages using vector search.

        If session_id provided, search within that session only.
        Otherwise, search across all sessions.
        """
        if self.db is None or self.db.db is None:
            return []

        try:
            # Use existing search method
            filter_expr = None
            if session_id:
                # Escape to avoid filter injection / broken filters on session
                # IDs containing quotes. The LIKE is a substring pre-filter; the
                # exact-match post-filter below prevents cross-session leakage
                # (e.g. 'abc' matching 'abcdef') that would inject another
                # session's context into the prompt.
                safe_sid = self._escape_like(session_id)
                filter_expr = f"metadata LIKE '%{safe_sid}%'"

            results = self.db.search(
                table_name=self.table_name, query=query, limit=limit, filter_str=filter_expr
            )

            # Exact session_id post-filter: the LIKE pre-filter is substring, so
            # without this, prefix-colliding sessions leak into recall.
            if session_id and results:
                results = [
                    r for r in results
                    if isinstance(r, dict)
                    and isinstance(r.get("metadata"), dict)
                    and r["metadata"].get("session_id") == session_id
                ]

            return results

        except Exception as e:
            logger.error(f"Failed to search relevant context: {e}")
            return []

    def get_entity_mentions(
        self,
        entity_type: str,  # "workflow_id", "task_id", "schedule_id"
        entity_id: str,
        session_id: str = None,
    ) -> list[dict[str, Any]]:
        """
        Find all messages mentioning a specific entity.
        """
        if self.db is None or self.db.db is None:
            return []

        try:
            table = self.db.get_table(self.table_name)
            if not table:
                return []

            # Search for entity_id in metadata (escape to avoid filter injection).
            filter_expr = f"metadata LIKE '%{self._escape_like(entity_id)}%'"
            if not PANDAS_AVAILABLE:
                logger.error("Pandas not available for entity mentions")
                return []
            results = table.search().where(filter_expr).limit(50).to_pandas()

            # Parse and filter
            messages = []
            for _, row in results.iterrows():
                try:
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}

                    # Check if this message mentions the entity
                    if metadata.get(entity_type) == entity_id:
                        # Filter by session if provided
                        if session_id is None or metadata.get("session_id") == session_id:
                            messages.append(
                                {
                                    "id": row["id"],
                                    "text": row["text"],
                                    "role": metadata.get("role"),
                                    "created_at": row["created_at"],
                                    "metadata": metadata,
                                }
                            )
                except Exception as e:
                    logger.warning(f"Error parsing message: {e}")
                    continue

            # Sort by created_at
            messages.sort(key=lambda x: x["created_at"])
            return messages

        except Exception as e:
            logger.error(f"Failed to get entity mentions: {e}")
            return []


# Handle multiple handlers (one per workspace) for physical isolation
_workspace_handlers: dict[str, "LanceDBHandler"] = {}


def get_lancedb_handler(
    workspace_id: Union[str, None] = None,
    tenant_id: Union[str, None] = None,
    db: Any = None,  # SQLAlchemy session for BYOK key lookup
) -> "LanceDBHandler":
    """
    Get or create a LanceDBHandler instance for a specific workspace.

    Args:
        workspace_id: Workspace ID for physical data isolation
        tenant_id: Tenant ID for BYOK key lookup (required for embeddings)
        db: Optional SQLAlchemy session (NOTE: when provided, handler is NOT cached
            to prevent connection leaks - sessions must be short-lived)

    Provides physical data isolation by using separate directories.

    Connection Leak Prevention (Issue #7488074293):
    Handlers with a db session are NOT cached because SQLAlchemy sessions should
    be short-lived. Storing them in the global cache causes connection leaks.
    """
    ws_id = workspace_id or "default_shared"

    # 🔴 CRITICAL: Don't cache handlers when db session is passed
    # SQLAlchemy sessions must be short-lived. Caching them causes connection leaks.
    if db is not None:
        base_uri = os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
        ws_path = os.path.join(base_uri, ws_id)
        return LanceDBHandler(
            db_path=ws_path, workspace_id=ws_id, tenant_id=tenant_id, db=db
        )

    # Cache only when no db session provided (safe to cache long-term)
    if ws_id not in _workspace_handlers:
        # Determine isolated path
        base_uri = os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
        ws_path = os.path.join(base_uri, ws_id)

        logger.info(f"Creating isolated LanceDBHandler for workspace: {ws_id} at {ws_path}")
        _workspace_handlers[ws_id] = LanceDBHandler(
            db_path=ws_path, workspace_id=ws_id, tenant_id=tenant_id, db=db
        )

    return _workspace_handlers[ws_id]


# Legacy instance for backward compatibility (points to default)
lancedb_handler = get_lancedb_handler()

# Global chat history manager (uses default handler for now, should ideally be workspace-aware)
chat_history_manager = ChatHistoryManager(lancedb_handler)


def get_chat_history_manager(workspace_id: Union[str, None] = None) -> ChatHistoryManager:
    """Get workspace-aware chat history manager instance"""
    handler = get_lancedb_handler(workspace_id)
    return ChatHistoryManager(handler)


# Global chat context manager helper
def get_chat_context_manager(workspace_id: Union[str, None] = None) -> "ChatContextManager":
    """Get workspace-aware chat context manager instance"""
    from core.chat_context_manager import ChatContextManager

    handler = get_lancedb_handler(workspace_id)
    return ChatContextManager(handler)


# Utility functions
def embed_documents_batch(
    texts: list[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> Union[Any, None]:
    """Embed a batch of texts"""
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None

    try:
        from sentence_transformers import SentenceTransformer

        embedder = SentenceTransformer(model_name)
        if NUMPY_AVAILABLE:
            embeddings = embedder.encode(texts, convert_to_numpy=True)
        else:
            embeddings = embedder.encode(texts, convert_to_numpy=False)
        return embeddings
    except Exception as e:
        logger.error(f"Failed to embed batch texts: {e}")
        return None


def create_memory_schema(vector_size: int = 384) -> dict[str, Any]:
    """Create standard memory schema for ATOM"""
    try:
        from lancedb.pydantic import Vector

        vector_type: Any = Vector(vector_size)
    except ImportError:
        # LanceDB unavailable (e.g. minimal install): fall back to a plain
        # float-list annotation so callers still get a usable schema dict.
        vector_type = List[float]

    return {
        "id": str,
        "text": str,
        "source": str,
        "metadata": str,  # JSON string
        "created_at": str,
        "vector": vector_type,
    }
