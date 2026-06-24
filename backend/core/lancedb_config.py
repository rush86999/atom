"""
S3-backed LanceDB Configuration
Configure LanceDB to use AWS S3 (or Cloudflare R2) for vector storage.

Personal Edition uses the **embedded** file-based path (`./data/lancedb` by
default) — no server container required. The S3/R2 paths below are gated behind
``LANCEDB_CLOUD_ENABLED`` (default ``false``) so Personal Edition stops
evaluating dead cloud codepaths. SaaS flips the flag to ``true``.
"""

import os
from typing import Optional
import lancedb

# Cloud gate — Personal Edition is embedded-only by default.
# When false, all S3/R2 storage options are ignored even if env vars are set.
LANCEDB_CLOUD_ENABLED = (
    os.getenv("LANCEDB_CLOUD_ENABLED", "false").lower() == "true"
)

# S3 Configuration (only honored when LANCEDB_CLOUD_ENABLED=true)
S3_BUCKET = os.getenv('LANCEDB_S3_BUCKET', '') if LANCEDB_CLOUD_ENABLED else ''
S3_PREFIX = os.getenv('LANCEDB_S3_PREFIX', 'lancedb')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Local fallback for development / Personal Edition
LOCAL_DB_PATH = os.getenv('LANCEDB_LOCAL_PATH', './data/lancedb')


def get_lancedb_connection(tenant_id: Optional[str] = None) -> lancedb.DBConnection:
    """
    Get LanceDB connection with S3 or local storage.

    For multi-tenant isolation, each tenant gets a separate prefix:
    s3://bucket/lancedb/tenant_123/

    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation

    Returns:
        LanceDB connection
    """
    if S3_BUCKET:
        # S3 storage (production / SaaS edition)
        if tenant_id:
            uri = f"s3://{S3_BUCKET}/{S3_PREFIX}/{tenant_id}/"
        else:
            uri = f"s3://{S3_BUCKET}/{S3_PREFIX}/"

        # LanceDB will use default AWS credentials from environment
        # or EC2 instance role
        return lancedb.connect(uri)
    else:
        # Local storage (development / Personal Edition — embedded, no server)
        if tenant_id:
            path = f"{LOCAL_DB_PATH}/{tenant_id}"
        else:
            path = LOCAL_DB_PATH

        os.makedirs(path, exist_ok=True)
        return lancedb.connect(path)


class LanceDBConfig:
    """LanceDB configuration for the application"""

    # Table names
    MEMORY_TABLE = "memory"
    DOCUMENTS_TABLE = "documents"
    COMMUNICATIONS_TABLE = "communications"
    FORMULAS_TABLE = "formulas"

    # Embedding dimensions (OpenAI ada-002)
    EMBEDDING_DIM = 1536

    # Search defaults
    DEFAULT_LIMIT = 10
    DEFAULT_METRIC = "cosine"

    @classmethod
    def get_storage_uri(cls, tenant_id: str) -> str:
        """Get storage URI for a tenant"""
        if S3_BUCKET:
            return f"s3://{S3_BUCKET}/{S3_PREFIX}/{tenant_id}/"
        return f"{LOCAL_DB_PATH}/{tenant_id}"

    @classmethod
    def is_s3_enabled(cls) -> bool:
        """Check if S3 storage is enabled (legacy alias)."""
        return bool(S3_BUCKET)

    @classmethod
    def is_cloud_enabled(cls) -> bool:
        """
        Check if cloud (S3/R2) storage paths are enabled.

        Returns ``True`` only when ``LANCEDB_CLOUD_ENABLED=true`` AND an S3
        bucket is configured. Personal Edition defaults to embedded (False).
        """
        return LANCEDB_CLOUD_ENABLED and bool(S3_BUCKET)


# Singleton connection cache
_connections: dict[str, lancedb.DBConnection] = {}


def get_db(tenant_id: str) -> lancedb.DBConnection:
    """Get cached LanceDB connection for tenant"""
    if tenant_id not in _connections:
        _connections[tenant_id] = get_lancedb_connection(tenant_id)
    return _connections[tenant_id]


def close_all_connections():
    """Close all cached connections (for cleanup)"""
    global _connections
    _connections = {}
