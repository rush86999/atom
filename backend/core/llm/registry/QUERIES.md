# LLM Model Registry Query Patterns

This document demonstrates how to use the query helpers for capability-based filtering with GIN indexes.

## Index Overview

The `llm_models` table has the following indexes for efficient capability filtering:

### GIN Indexes (JSONB)
- `idx_llm_models_capabilities_gin` - GIN index on `capabilities` JSONB array
- `idx_llm_models_metadata_gin` - GIN index on `metadata` JSONB object

### Partial Indexes (Hybrid Columns)
- `idx_llm_models_vision_partial` - Partial index on `supports_vision` WHERE TRUE
- `idx_llm_models_tools_partial` - Partial index on `supports_tools` WHERE TRUE
- `idx_llm_models_function_calling_partial` - Partial index on `supports_function_calling` WHERE TRUE
- `idx_llm_models_audio_partial` - Partial index on `supports_audio` WHERE TRUE

### Standard Indexes
- `idx_llm_models_tenant` - B-tree index on `tenant_id`
- `idx_llm_models_provider` - B-tree index on `provider`
- `idx_llm_models_tenant_provider_model` - Composite unique index on `(tenant_id, provider, model_name)`

## Query Patterns

### 1. Single Capability Lookup

Find models with a specific capability:

```python
from core.llm.registry.queries import query_by_capability, VISION

# Hybrid capability (uses boolean column)
vision_models = query_by_capability(db, 'tenant-123', VISION)
# SQL: SELECT * WHERE supports_vision = TRUE AND tenant_id = 'tenant-123'

# Rare capability (uses JSONB @> operator)
json_models = query_by_capability(db, 'tenant-123', 'json_mode')
# SQL: SELECT * WHERE capabilities @> '["json_mode"]' AND tenant_id = 'tenant-123'
```

**Index Usage:**
- Hybrid capabilities: Partial index scan (idx_llm_models_vision_partial)
- Rare capabilities: GIN index scan (idx_llm_models_capabilities_gin)

### 2. Multi-Capability AND Query

Find models with ALL specified capabilities:

```python
from core.llm.registry.queries import query_by_all_capabilities, VISION, TOOLS

# Models must have BOTH vision AND tools
models = query_by_all_capabilities(db, 'tenant-123', [VISION, TOOLS])
# SQL: SELECT * WHERE supports_vision = TRUE AND supports_tools = TRUE AND tenant_id = 'tenant-123'

# Mix of hybrid and rare
models = query_by_all_capabilities(db, 'tenant-123', [VISION, 'json_mode'])
# SQL: SELECT * WHERE supports_vision = TRUE AND capabilities @> '["json_mode"]' AND tenant_id = 'tenant-123'
```

**Index Usage:**
- Hybrid columns: Partial index scans (multiple)
- Rare capabilities: GIN index scan (idx_llm_models_capabilities_gin)

### 3. Any Capability OR Query

Find models with ANY of the specified capabilities:

```python
from core.llm.registry.queries import query_by_any_capability

# Models with vision OR tools
models = query_by_any_capability(db, 'tenant-123', [VISION, TOOLS])
# SQL: SELECT * WHERE capabilities && '["vision", "tools"]' AND tenant_id = 'tenant-123'
```

**Index Usage:**
- GIN index scan with overlap operator (idx_llm_models_capabilities_gin)

### 4. Combined Query

Flexible filtering with both AND and OR logic:

```python
from core.llm.registry.queries import get_capable_models

# Models must have tools AND (vision OR audio)
models = get_capable_models(
    db,
    'tenant-123',
    required_capabilities=[TOOLS],
    any_capabilities=[VISION, AUDIO]
)
```

**Index Usage:**
- Hybrid column: Partial index scan (idx_llm_models_tools_partial)
- OR logic: GIN index scan with overlap operator

### 5. Metadata Path Query

Find models by provider-specific metadata:

```python
from core.llm.registry.queries import query_by_metadata

# Find all OpenAI models
openai_models = query_by_metadata(db, 'tenant-123', 'provider', 'openai')
# SQL: SELECT * WHERE metadata->>'provider' = 'openai' AND tenant_id = 'tenant-123'
```

**Index Usage:**
- GIN index scan (idx_llm_models_metadata_gin)

## Verifying Index Usage

Use EXPLAIN ANALYZE to verify index usage:

```python
from core.llm.registry.queries import explain_query, get_index_usage_stats

# Get execution plan
plan = explain_query(db, 'tenant-123', VISION)
print(plan)

# Get statistics
stats = get_index_usage_stats(db, 'tenant-123', VISION)
print(f"Uses GIN index: {stats['uses_gin_index']}")
print(f"Execution time: {stats['execution_time']}ms")
print(f"Rows returned: {stats['row_count']}")
```

## SQL Operator Reference

### JSONB Operators (GIN Index)

| Operator | Description | Example | Index Used |
|----------|-------------|---------|------------|
| `@>` | Contains (left contains right) | `capabilities @> '["vision"]'` | idx_llm_models_capabilities_gin |
| `&&` | Overlap (has any elements in common) | `capabilities && '["vision", "tools"]'` | idx_llm_models_capabilities_gin |
| `?` | Key exists | `metadata ? 'provider'` | idx_llm_models_metadata_gin |
| `?|` | Any keys exist | `metadata ?| array['provider', 'model']` | idx_llm_models_metadata_gin |
| `?&` | All keys exist | `metadata ?& array['provider', 'model']` | idx_llm_models_metadata_gin |
| `->>` | Get value as text | `metadata->>'provider' = 'openai'` | idx_llm_models_metadata_gin |

### Hybrid Column Operators (Partial Index)

| Operator | Description | Example | Index Used |
|----------|-------------|---------|------------|
| `= TRUE` | Boolean equality | `supports_vision = TRUE` | idx_llm_models_vision_partial |

## Performance Characteristics

### Small Dataset (< 100 models)
- PostgreSQL may use sequential scan regardless of indexes
- GIN indexes not yet efficient

### Medium Dataset (100-10,000 models)
- GIN indexes become efficient for JSONB queries
- Partial indexes very efficient for boolean filters

### Large Dataset (> 10,000 models)
- GIN indexes essential for JSONB performance
- Partial indexes provide optimal boolean filtering
- Composite indexes (tenant + provider + model) efficient for lookups

## Common Query Patterns

### Find all vision-capable models
```python
models = query_by_capability(db, tenant_id, VISION)
```

### Find models with vision AND tools
```python
models = query_by_all_capabilities(db, tenant_id, [VISION, TOOLS])
```

### Find models with vision OR tools
```python
models = query_by_any_capability(db, tenant_id, [VISION, TOOLS])
```

### Find models from specific provider
```python
models = query_by_metadata(db, tenant_id, 'provider', 'openai')
```

### Find models with max context window
```python
models = db.query(LLMModel).filter(
    LLMModel.tenant_id == tenant_id,
    LLMModel.context_window >= 128000
).all()
```

### Find models by price range
```python
models = db.query(LLMModel).filter(
    LLMModel.tenant_id == tenant_id,
    LLMModel.input_price_per_token <= 0.0001
).all()
```

## Syncing Hybrid Columns

When modifying capabilities, always sync hybrid columns:

```python
model = db.query(LLMModel).first()
model.capabilities.append('vision')
model.sync_capabilities()  # Updates supports_vision = TRUE
db.commit()
```

This ensures the boolean columns stay in sync with the JSONB array for optimal query performance.
