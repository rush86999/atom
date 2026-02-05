"""
Embedding Generation Service

Provides AI embedding generation for semantic search and vector storage.
Supports multiple embedding providers:
- FastEmbed (default, local, fast) - BAAI/bge-small-en-v1.5, BAAI/bge-base-en-v1.5
- OpenAI (cloud, high quality) - text-embedding-3-small, text-embedding-3-large
- Cohere (cloud, multilingual) - embed-english-v3.0, embed-multilingual-v3.0

Usage:
    service = EmbeddingService()
    embedding = await service.generate_embedding("Hello world")
    # Returns: [0.123, -0.456, ...] (vector of floats)

Performance:
    FastEmbed: ~10-20ms per document (local)
    OpenAI: ~100-300ms per document (cloud)
    Cohere: ~150-400ms per document (cloud)
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Supported embedding providers"""
    FASTEMBED = "fastembed"  # Default: Fast, local, ONNX-based
    OPENAI = "openai"        # Cloud: High quality
    COHERE = "cohere"        # Cloud: Multilingual support


class EmbeddingService:
    """
    Service for generating AI embeddings.

    Features:
    - FastEmbed as default (10-20ms per doc, local, lightweight)
    - OpenAI/Cohere cloud options for higher quality
    - Batch embedding generation
    - Text preprocessing
    - Error handling and retries
    - Automatic model caching (FastEmbed)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider (default: "fastembed")
                - "fastembed" - Fast, local ONNX-based embeddings (recommended)
                - "openai" - Cloud-based OpenAI embeddings
                - "cohere" - Cloud-based Cohere embeddings
            model: Model name (default: provider's recommended model)
            config: Additional configuration (API keys, etc.)
        """
        self.provider = provider or os.getenv(
            "EMBEDDING_PROVIDER",
            EmbeddingProvider.FASTEMBED  # Changed default to FastEmbed
        )
        self.config = config or {}
        self._client = None

        # Set default models
        self.model = model or self._get_default_model()

        # Validate provider
        if self.provider not in [
            EmbeddingProvider.FASTEMBED,
            EmbeddingProvider.OPENAI,
            EmbeddingProvider.COHERE
        ]:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

        logger.info(
            f"Initialized EmbeddingService: provider={self.provider}, model={self.model}"
        )

    def _get_default_model(self) -> str:
        """Get default model for provider"""
        defaults = {
            EmbeddingProvider.FASTEMBED: os.getenv(
                "FASTEMBED_MODEL",
                "BAAI/bge-small-en-v1.5"  # Fast, good quality, 384 dimensions
            ),
            EmbeddingProvider.OPENAI: os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small"  # 1536 dimensions
            ),
            EmbeddingProvider.COHERE: "embed-english-v3.0"  # 1024 dimensions
        }
        return defaults.get(self.provider, "BAAI/bge-small-en-v1.5")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text)

            # Generate embedding based on provider
            if self.provider == EmbeddingProvider.FASTEMBED:
                embedding = await self._generate_fastembed_embedding(processed_text)
            elif self.provider == EmbeddingProvider.OPENAI:
                embedding = await self._generate_openai_embedding(processed_text)
            elif self.provider == EmbeddingProvider.COHERE:
                embedding = await self._generate_cohere_embedding(processed_text)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            logger.debug(f"Generated embedding: dimension={len(embedding)}, text_length={len(text)}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        More efficient than calling generate_embedding multiple times.
        FastEmbed handles batching automatically with excellent performance.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            # Preprocess all texts
            processed_texts = [self._preprocess_text(t) for t in texts]

            # Generate embeddings based on provider
            if self.provider == EmbeddingProvider.FASTEMBED:
                embeddings = await self._generate_fastembed_embeddings_batch(processed_texts)
            elif self.provider == EmbeddingProvider.OPENAI:
                embeddings = await self._generate_openai_embeddings_batch(processed_texts)
            elif self.provider == EmbeddingProvider.COHERE:
                embeddings = await self._generate_cohere_embeddings_batch(processed_texts)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            logger.info(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text before embedding.

        - Truncate to max length
        - Remove extra whitespace
        - Normalize unicode

        Args:
            text: Raw text

        Returns:
            Preprocessed text
        """
        import re
        import unicodedata

        if not text:
            return ""

        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Truncate to max length (depends on model)
        # FastEmbed models typically handle up to 512 tokens
        # Rough estimate: 1 token ~ 4 characters
        max_chars = {
            EmbeddingProvider.FASTEMBED: 8192,   # ~2048 tokens (safe margin)
            EmbeddingProvider.OPENAI: 32000,    # ~8k tokens
            EmbeddingProvider.COHERE: 20000
        }

        limit = max_chars.get(self.provider, 8192)
        if len(text) > limit:
            text = text[:limit]
            logger.debug(f"Truncated text to {limit} characters")

        return text

    # ========================================================================
    # FastEmbed Implementation (Default, Recommended)
    # ========================================================================

    async def _generate_fastembed_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using FastEmbed (ONNX-based, local).

        FastEmbed advantages:
        - Written in Rust for performance
        - Uses ONNX Runtime (no PyTorch/TensorFlow needed)
        - ~10-20ms per embedding
        - ~100MB memory (vs 500MB+ for sentence-transformers)
        - Auto-caches models after first download
        """
        try:
            from fastembed import TextEmbedding

            # Initialize model (cached after first use)
            if self._client is None:
                logger.info(f"Loading FastEmbed model: {self.model}")
                self._client = TextEmbedding(model_name=self.model)

            # Generate embedding
            embeddings = list(self._client.embed([text]))

            if not embeddings or len(embeddings) == 0:
                raise Exception("FastEmbed returned empty result")

            return embeddings[0].tolist()

        except ImportError:
            raise Exception(
                "FastEmbed package not installed. "
                "Run: pip install 'fastembed>=0.2.0'"
            )
        except Exception as e:
            logger.error(f"FastEmbed embedding generation failed: {e}")
            raise

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

    # ========================================================================
    # OpenAI Implementation (Cloud, High Quality)
    # ========================================================================

    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
            )

            response = await client.embeddings.create(
                model=self.model,
                input=text
            )

            return response.data[0].embedding

        except ImportError:
            raise Exception("OpenAI package not installed. Run: pip install openai")
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            raise

    async def _generate_openai_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API (batch)"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
            )

            # OpenAI supports up to 2048 texts per request
            batch_size = 2048
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = await client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                all_embeddings.extend([item.embedding for item in response.data])

            return all_embeddings

        except Exception as e:
            logger.error(f"OpenAI batch embedding generation failed: {e}")
            raise

    # ========================================================================
    # Cohere Implementation (Cloud, Multilingual)
    # ========================================================================

    async def _generate_cohere_embedding(self, text: str) -> List[float]:
        """Generate embedding using Cohere API"""
        try:
            import cohere

            client = cohere.Client(
                api_key=self.config.get("api_key") or os.getenv("COHERE_API_KEY")
            )

            response = client.embed(
                model=self.model,
                texts=[text]
            )

            return response.embeddings[0]

        except ImportError:
            raise Exception("Cohere package not installed. Run: pip install cohere")
        except Exception as e:
            logger.error(f"Cohere embedding generation failed: {e}")
            raise

    async def _generate_cohere_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Cohere API (batch)"""
        try:
            import cohere

            client = cohere.Client(
                api_key=self.config.get("api_key") or os.getenv("COHERE_API_KEY")
            )

            # Cohere supports up to 96 texts per request
            batch_size = 96
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = client.embed(
                    model=self.model,
                    texts=batch
                )
                all_embeddings.extend(response.embeddings)

            return all_embeddings

        except Exception as e:
            logger.error(f"Cohere batch embedding generation failed: {e}")
            raise


class LanceDBHandler:
    """
    Handler for storing and retrieving embeddings in LanceDB.

    LanceDB is a vector database optimized for AI/ML workloads.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize LanceDB handler.

        Args:
            db_path: Path to LanceDB database (default: ./data/lancedb)
        """
        import lancedb

        self.db_path = db_path or os.getenv("LANCEDB_PATH", "./data/lancedb")
        self.db = lancedb.connect(self.db_path)

        logger.info(f"Initialized LanceDB handler at {self.db_path}")

    async def upsert(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        vector_column: str = "vector"
    ):
        """
        Upsert documents to LanceDB table.

        Args:
            table_name: Name of the table
            data: List of documents with 'vector' field
            vector_column: Name of the vector column
        """
        try:
            import pandas as pd
            import pyarrow as pa

            # Check if table exists
            table_names = self.db.table_names()
            if table_name not in table_names:
                # Create new table
                df = pd.DataFrame(data)
                schema = self._get_schema(df, vector_column)
                self.db.create_table(table_name, data=df, schema=schema)
                logger.info(f"Created new LanceDB table: {table_name}")
            else:
                # Add to existing table
                table = self.db.open_table(table_name)
                table.add(data)
                logger.info(f"Added {len(data)} rows to table {table_name}")

        except Exception as e:
            logger.error(f"Failed to upsert to LanceDB: {e}")
            raise

    async def search(
        self,
        table_name: str,
        query_vector: List[float],
        limit: int = 10,
        metric: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in LanceDB.

        Args:
            table_name: Name of the table
            query_vector: Query embedding vector
            limit: Number of results to return
            metric: Distance metric (cosine, l2, dot)

        Returns:
            List of search results with scores
        """
        try:
            table = self.db.open_table(table_name)
            results = table.search(query_vector).limit(limit).metric(metric).to_pandas()

            return results.to_dict("records")

        except Exception as e:
            logger.error(f"Failed to search LanceDB: {e}")
            raise

    def _get_schema(self, df, vector_column: str):
        """Get PyArrow schema for LanceDB table"""
        import pyarrow as pa

        # Define schema
        fields = []

        for col in df.columns:
            if col == vector_column:
                # Vector column (fixed size list of floats)
                fields.append(pa.field(col, pa.list_(pa.float32())))
            elif df[col].dtype == "object":
                # String columns
                fields.append(pa.field(col, pa.string()))
            elif df[col].dtype == "int64":
                fields.append(pa.field(col, pa.int64()))
            elif df[col].dtype == "float64":
                fields.append(pa.field(col, pa.float64()))
            else:
                # Default to string
                fields.append(pa.field(col, pa.string()))

        return pa.schema(fields)


# ============================================================================
# Convenience Functions
# ============================================================================

async def generate_embedding(text: str, provider: Optional[str] = None) -> List[float]:
    """
    Convenience function to generate a single embedding.

    Args:
        text: Text to embed
        provider: Optional provider override (default: fastembed)

    Returns:
        Embedding vector
    """
    service = EmbeddingService(provider=provider)
    return await service.generate_embedding(text)


async def generate_embeddings_batch(texts: List[str], provider: Optional[str] = None) -> List[List[float]]:
    """
    Convenience function to generate batch embeddings.

    Args:
        texts: List of texts to embed
        provider: Optional provider override (default: fastembed)

    Returns:
        List of embedding vectors
    """
    service = EmbeddingService(provider=provider)
    return await service.generate_embeddings_batch(texts)
