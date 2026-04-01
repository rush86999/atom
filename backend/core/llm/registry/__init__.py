"""LLM Model Registry Module

This module provides the database model for storing and managing
LLM model metadata from multiple providers with tenant isolation.

Key features:
- Multi-provider model registration (OpenAI, Anthropic, OpenRouter, etc.)
- Hybrid metadata storage (structured columns + JSONB)
- Tenant isolation via Row Level Security (RLS)
- Pricing and capability tracking
- Scheduled sync job for automatic model discovery

Usage:
    from core.llm.registry import LLMModel, ModelSyncJob, run_sync_job

    # Query models for a tenant
    models = session.query(LLMModel).filter(
        LLMModel.tenant_id == 'tenant-123'
    ).all()

    # Create a new model entry
    model = LLMModel(
        tenant_id='tenant-123',
        provider='openai',
        model_name='gpt-4',
        context_window=8192,
        input_price_per_token=0.00003,
        output_price_per_token=0.00006,
        capabilities=['vision', 'tools', 'function_calling'],
        provider_metadata={'max_tokens': 8192, 'supports_streaming': True}
    )
    session.add(model)
    session.commit()

    # Run scheduled sync job (e.g., in cron)
    result = await run_sync_job('tenant-123')
    print(f"Synced {result['models_fetched']} models")
"""
from core.llm.registry.models import LLMModel
from core.llm.registry.sync_job import ModelSyncJob, run_sync_job

__all__ = ['LLMModel', 'ModelSyncJob', 'run_sync_job']
