"""Query Helpers for LLM Model Registry

This module provides optimized query functions for filtering LLM models
by their capabilities using PostgreSQL's JSONB operators and GIN indexes.

Supported operators:
- @> (contains): Single capability or multi-capability AND queries
- && (overlap): Any capability OR queries
- ->> (path): Metadata JSONB path queries

The queries optimize for hybrid capability columns (supports_vision, etc.)
when available, falling back to JSONB queries for rare capabilities.
"""
from typing import List, Optional, Any, Dict
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from .models import LLMModel


# Common capability constants
VISION = 'vision'
TOOLS = 'tools'
FUNCTION_CALLING = 'function_calling'
AUDIO = 'audio'
JSON_MODE = 'json_mode'


def query_by_capability(
    db: Session,
    tenant_id: str,
    capability: str
) -> List[LLMModel]:
    """
    Query models by a single capability (AND logic).

    Uses hybrid boolean columns for common capabilities (vision, tools, etc.)
    for optimal performance, falls back to JSONB @> operator for rare capabilities.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        capability: Capability name to filter by (e.g., 'vision', 'tools')

    Returns:
        List of models that have the specified capability

    Example:
        vision_models = query_by_capability(db, 'tenant-123', 'vision')
        # Returns all models with vision capability
    """
    query = select(LLMModel).where(LLMModel.tenant_id == tenant_id)

    # Use hybrid column for common capabilities
    if capability in LLMModel.HYBRID_CAPABILITIES:
        column_name = f'supports_{capability}'
        query = query.where(text(f'{column_name} = TRUE'))
    else:
        # Use JSONB @> operator for rare capabilities
        query = query.where(text('capabilities @> :cap')).params(cap=f'["{capability}"]')

    result = db.execute(query).scalars().all()
    return list(result)


def query_by_all_capabilities(
    db: Session,
    tenant_id: str,
    capabilities: List[str]
) -> List[LLMModel]:
    """
    Query models that have ALL specified capabilities (AND logic).

    Uses hybrid boolean columns for common capabilities, falls back to
    JSONB @> operator for rare capabilities. Mixed queries use hybrid for
    common and JSONB for rare.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        capabilities: List of capabilities that must ALL be present

    Returns:
        List of models that have all specified capabilities

    Example:
        models = query_by_all_capabilities(db, 'tenant-123', ['vision', 'tools'])
        # Returns models that have BOTH vision AND tools
    """
    query = select(LLMModel).where(LLMModel.tenant_id == tenant_id)

    # Separate hybrid and rare capabilities
    hybrid_caps = [c for c in capabilities if c in LLMModel.HYBRID_CAPABILITIES]
    rare_caps = [c for c in capabilities if c not in LLMModel.HYBRID_CAPABILITIES]

    # Add hybrid column filters
    for cap in hybrid_caps:
        column_name = f'supports_{cap}'
        query = query.where(text(f'{column_name} = TRUE'))

    # Add JSONB filter for rare capabilities (if any)
    if rare_caps:
        # Build JSONB array for @> operator
        rare_array = str([f'"{cap}"' for cap in rare_caps]).replace("'", "")
        query = query.where(text(f'capabilities @> {rare_array}::jsonb'))

    result = db.execute(query).scalars().all()
    return list(result)


def query_by_any_capability(
    db: Session,
    tenant_id: str,
    capabilities: List[str]
) -> List[LLMModel]:
    """
    Query models that have ANY of the specified capabilities (OR logic).

    Uses JSONB && (overlap) operator for efficient OR queries across
    both hybrid and rare capabilities.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        capabilities: List of capabilities, at least one must be present

    Returns:
        List of models that have at least one of the specified capabilities

    Example:
        models = query_by_any_capability(db, 'tenant-123', ['vision', 'audio'])
        # Returns models that have vision OR audio (or both)
    """
    query = select(LLMModel).where(LLMModel.tenant_id == tenant_id)

    # Build JSONB array for && operator
    caps_array = str([f'"{cap}"' for cap in capabilities]).replace("'", "")
    query = query.where(text(f'capabilities && {caps_array}::jsonb'))

    result = db.execute(query).scalars().all()
    return list(result)


def query_by_metadata(
    db: Session,
    tenant_id: str,
    metadata_path: str,
    metadata_value: Any
) -> List[LLMModel]:
    """
    Query models by metadata JSONB path.

    Uses ->> operator to extract JSONB values by path for flexible
    provider-specific metadata queries.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        metadata_path: JSONB path (e.g., 'provider', 'max_tokens', 'context_length')
        metadata_value: Value to match

    Returns:
        List of models with matching metadata value

    Example:
        models = query_by_metadata(db, 'tenant-123', 'provider', 'openai')
        # Returns all OpenAI models
    """
    query = select(LLMModel).where(
        and_(
            LLMModel.tenant_id == tenant_id,
            text(f'metadata->>:path = :value')
        )
    ).params(path=metadata_path, value=str(metadata_value))

    result = db.execute(query).scalars().all()
    return list(result)


def get_capable_models(
    db: Session,
    tenant_id: str,
    required_capabilities: Optional[List[str]] = None,
    any_capability: Optional[str] = None,
    any_capabilities: Optional[List[str]] = None
) -> List[LLMModel]:
    """
    Combined query helper for flexible capability filtering.

    This is the main query function that combines multiple filters:
    - required_capabilities: Models must have ALL these capabilities (AND)
    - any_capability / any_capabilities: Models must have at least ONE (OR)

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        required_capabilities: List of capabilities that must ALL be present
        any_capability: Single capability (models must have this one)
        any_capabilities: List of capabilities, at least one must be present

    Returns:
        List of models matching the specified criteria

    Example:
        # Models with vision AND tools, plus EITHER audio OR function_calling
        models = get_capable_models(
            db, 'tenant-123',
            required_capabilities=['vision', 'tools'],
            any_capabilities=['audio', 'function_calling']
        )
    """
    query = select(LLMModel).where(LLMModel.tenant_id == tenant_id)

    # Handle required capabilities (AND logic)
    if required_capabilities:
        hybrid_caps = [c for c in required_capabilities if c in LLMModel.HYBRID_CAPABILITIES]
        rare_caps = [c for c in required_capabilities if c not in LLMModel.HYBRID_CAPABILITIES]

        for cap in hybrid_caps:
            column_name = f'supports_{cap}'
            query = query.where(text(f'{column_name} = TRUE'))

        if rare_caps:
            rare_array = str([f'"{cap}"' for cap in rare_caps]).replace("'", "")
            query = query.where(text(f'capabilities @> {rare_array}::jsonb'))

    # Handle any capability (OR logic)
    if any_capability:
        any_capabilities = [any_capability]

    if any_capabilities:
        caps_array = str([f'"{cap}"' for cap in any_capabilities]).replace("'", "")
        query = query.where(text(f'capabilities && {caps_array}::jsonb'))

    result = db.execute(query).scalars().all()
    return list(result)


def explain_query(
    db: Session,
    tenant_id: str,
    capability: str
) -> str:
    """
    Return EXPLAIN ANALYZE output for a capability query.

    Useful for debugging and verifying that GIN indexes are being used.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        capability: Capability name to filter by

    Returns:
        EXPLAIN ANALYZE output as a string

    Example:
        plan = explain_query(db, 'tenant-123', 'vision')
        print(plan)
        # Should show: "Index Scan using idx_llm_models_capabilities_gin"
    """
    sql = text("""
        EXPLAIN ANALYZE
        SELECT * FROM llm_models
        WHERE tenant_id = :tenant_id
        AND capabilities @> :capability
    """).params(tenant_id=tenant_id, capability=f'["{capability}"]')

    result = db.execute(sql)
    rows = result.fetchall()
    return '\n'.join(str(row[0]) for row in rows)


def get_index_usage_stats(
    db: Session,
    tenant_id: str,
    capability: str
) -> Dict[str, Any]:
    """
    Get query execution statistics for capability filtering.

    Returns details about index usage, execution time, and row counts.

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant identifier for multi-tenancy
        capability: Capability name to filter by

    Returns:
        Dictionary with execution statistics

    Example:
        stats = get_index_usage_stats(db, 'tenant-123', 'vision')
        print(f"Execution time: {stats['execution_time']}ms")
        print(f"Rows returned: {stats['row_count']}")
    """
    explain_output = explain_query(db, tenant_id, capability)

    # Parse EXPLAIN ANALYZE output
    stats = {
        'explain_output': explain_output,
        'uses_gin_index': 'Bitmap Index Scan' in explain_output or 'Index Scan using idx_llm_models_capabilities_gin' in explain_output,
        'execution_time': None,
        'planning_time': None,
        'row_count': None,
    }

    # Extract timing information
    for line in explain_output.split('\n'):
        if 'execution time' in line.lower():
            try:
                time_str = line.split('execution time: ')[1].split(' ms')[0]
                stats['execution_time'] = float(time_str)
            except (IndexError, ValueError):
                pass
        if 'planning time' in line.lower():
            try:
                time_str = line.split('planning time: ')[1].split(' ms')[0]
                stats['planning_time'] = float(time_str)
            except (IndexError, ValueError):
                pass
        if 'rows=' in line:
            try:
                rows_str = line.split('rows=')[1].split(' ')[0]
                stats['row_count'] = int(rows_str)
            except (IndexError, ValueError):
                pass

    return stats


# ============================================================================
# Quality-Based Routing Queries
# ============================================================================

# Auto-inclusion threshold for BPC routing
QUALITY_AUTO_INCLUSION_THRESHOLD = 80.0


def get_models_by_quality_range(
    db: Session,
    tenant_id: str,
    min_quality: float = 0.0,
    max_quality: float = 100.0,
    limit: Optional[int] = None
) -> List[LLMModel]:
    """Get models within a quality score range.

    Args:
        db: Database session
        tenant_id: Tenant identifier
        min_quality: Minimum quality score
        max_quality: Maximum quality score
        limit: Maximum number of models to return

    Returns:
        List of LLMModel instances sorted by quality_score DESC
    """
    query = (
        db.query(LLMModel)
        .filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.quality_score.isnot(None),
                LLMModel.quality_score >= min_quality,
                LLMModel.quality_score <= max_quality,
                LLMModel.is_deprecated == False
            )
        )
        .order_by(LLMModel.quality_score.desc())
    )

    if limit:
        query = query.limit(limit)

    return query.all()


def get_frontier_models(
    db: Session,
    tenant_id: str,
    min_quality: float = QUALITY_AUTO_INCLUSION_THRESHOLD,
    capabilities: Optional[List[str]] = None,
    exclude_experimental: bool = True
) -> List[LLMModel]:
    """Get frontier models suitable for BPC routing.

    Frontier models are high-quality models that can be automatically
    included in routing decisions.

    Args:
        db: Database session
        tenant_id: Tenant identifier
        min_quality: Minimum quality score (default 80)
        capabilities: Optional list of required capabilities
        exclude_experimental: Exclude preview/experimental models

    Returns:
        List of frontier models sorted by quality_score DESC
    """
    query = (
        db.query(LLMModel)
        .filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.quality_score >= min_quality,
                LLMModel.is_deprecated == False
            )
        )
    )

    # Exclude experimental/preview models if requested
    if exclude_experimental:
        # Exclude models with experimental/preview in name
        query = query.filter(
            ~LLMModel.model_name.ilike('%experimental%'),
            ~LLMModel.model_name.ilike('%preview%'),
            ~LLMModel.model_name.ilike('%alpha%'),
            ~LLMModel.model_name.ilike('%beta%')
        )

    # Filter by capabilities if specified
    if capabilities:
        # Use hybrid columns for common capabilities
        for cap in LLMModel.HYBRID_CAPABILITIES:
            if cap in capabilities:
                col = getattr(LLMModel, f'supports_{cap}')
                query = query.filter(col == True)

        # For non-hybrid capabilities, use JSONB
        non_hybrid_caps = [c for c in capabilities if c not in LLMModel.HYBRID_CAPABILITIES]
        if non_hybrid_caps:
            for cap in non_hybrid_caps:
                query = query.filter(LLMModel.capabilities.contains([cap]))

    return query.order_by(LLMModel.quality_score.desc()).all()


def get_auto_include_models(
    db: Session,
    tenant_id: str,
    provider: Optional[str] = None
) -> List[LLMModel]:
    """Get models that should be auto-included in BPC routing.

    Models are auto-included if:
    - quality_score >= 80 (or configured threshold)
    - Not deprecated
    - Not marked experimental/preview

    Args:
        db: Database session
        tenant_id: Tenant identifier
        provider: Optional provider filter

    Returns:
        List of auto-include models
    """
    query = (
        db.query(LLMModel)
        .filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.quality_score >= QUALITY_AUTO_INCLUSION_THRESHOLD,
                LLMModel.is_deprecated == False
            )
        )
        # Exclude experimental
        .filter(
            ~LLMModel.model_name.ilike('%experimental%'),
            ~LLMModel.model_name.ilike('%preview%')
        )
    )

    if provider:
        query = query.filter(LLMModel.provider == provider)

    return query.order_by(LLMModel.quality_score.desc()).all()


def score_model_for_routing(
    model: LLMModel,
    health_priority: Optional[int] = None
) -> float:
    """Calculate composite routing score for a model.

    Combines quality_score, health priority, and other factors
    to produce a ranking score for BPC routing.

    Higher scores = better for routing.

    Args:
        model: LLMModel instance
        health_priority: Optional health priority (0=best, 3=worst)

    Returns:
        Composite score for routing (higher is better)
    """
    # Start with quality score
    score = model.quality_score or 75.0  # Default to mid-range if no score

    # Apply health penalty (health_priority 0 = no penalty, 3 = -15 penalty)
    if health_priority is not None:
        health_penalty = health_priority * 5.0
        score -= health_penalty

    # Small bonus for frontier models (recently discovered)
    # This helps new models get tried
    if hasattr(model, 'discovered_at') and model.discovered_at:
        from datetime import datetime, timedelta
        if model.discovered_at > datetime.utcnow() - timedelta(days=30):
            score += 2.0  # +2 for newly discovered models

    return max(0, min(100, score))  # Clamp to 0-100
