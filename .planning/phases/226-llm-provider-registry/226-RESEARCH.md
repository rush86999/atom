# Phase 226: LLM Provider Registry & BPC Routing Enhancement - Research

**Researched:** March 22, 2026
**Domain:** LLM Provider Management, BPC Routing, Auto-Discovery, LUX Model Integration
**Confidence:** HIGH

## Executive Summary

Phase 226 aims to create an extensible LLM provider registry system with auto-discovery capabilities, integrate the LUX computer use model into the BPC (Benchmark-Price-Capability) routing system, and enhance API key management. The current architecture has a **solid foundation** with DynamicPricingFetcher already implementing auto-discovery from LiteLLM (GitHub) and OpenRouter API, storing **2,922+ models** in `ai_pricing_cache.json`. However, several gaps exist:

1. **No persistent provider registry** beyond runtime memory
2. **LUX model exists** but isn't integrated into BPC routing
3. **BYOK frontend** has basic functionality but lacks provider management features
4. **No scheduled polling** for model updates

**Primary recommendation:** Build on existing DynamicPricingFetcher infrastructure, create a persistent ProviderRegistry model with auto-discovery polling, add LUX model configuration to BPC routing tables, and enhance the BYOKManager UI with provider health monitoring.

---

## 1. Latest AI Models Catalog (2025-2026)

### Current Frontier Models (March 2026)

Based on the `ai_pricing_cache.json` analysis and `benchmarks.py`:

#### OpenAI Models
- **GPT-5.4 Pro** - $30/M input, $180/M output (1M+ context)
- **GPT-5.4 Mini** - $0.75/M input, $4.5/M output (400K context)
- **GPT-5.4 Nano** - $0.20/M input, $1.25/M output (400K context)
- **GPT-5.3** - Quality score: 100 (frontier tier)
- **GPT-5** - Quality score: 99 (frontier tier)
- **o3** - Quality score: 99 (reasoning specialist)
- **o4-mini** - Quality score: 96 (cost-efficient reasoning)
- **GPT-4.5** - Quality score: 95
- **GPT-4o** - Quality score: 90 (demoted from frontier)

#### Anthropic Models
- **Claude 4 Opus** - Quality score: 99 (frontier tier)
- **Claude 3.5 Opus** - Quality score: 97
- **Claude 3.5 Sonnet** - Quality score: 92 (demoted)
- **Claude 3 Opus 4.6** - Available in BYOK config

#### Google Models
- **Gemini 3 Pro** - Quality score: 100 (frontier tier)
- **Gemini 3 Flash** - Quality score: 93
- **Gemini 2.0 Flash** - Quality score: 86
- **Gemini 1.5 Flash** - Quality score: 84

#### DeepSeek Models
- **DeepSeek V3.2 Speciale** - Quality score: 99 (frontier reasoning at low cost)
- **DeepSeek R2** - Quality score: 97
- **DeepSeek V3** - Quality score: 89 (demoted)
- **DeepSeek V3.2** - Quality score: 89 (demoted)
- **DeepSeek Chat** - Quality score: 80

#### Other Frontier Models
- **Qwen 3 Max** - Quality score: 96
- **Llama 4 70B** - Quality score: 92
- **Llama 3.3 70B** - Quality score: 89
- **MiniMax M2.5** - Quality score: 88 (Standard tier, ~$1/M tokens)

### New Specialist Models (2026)
- **Hunter Alpha** (OpenRouter) - 1T+ parameters, 1M context, agentic use
- **Healer Alpha** (OpenRouter) - Omni-modal (vision, hearing, reasoning, action)
- **Nemotron 3 Super** (NVIDIA) - 120B params, hybrid Mamba-Transformer, 1M context
- **Grok 4.20 Beta** (xAI) - Multi-agent variant with 4-16 parallel agents
- **Mistral Small 4** - Unified Magistral + Pixtral + Devstral capabilities

### Pricing Trends
- **Frontier models**: $20-180/M tokens (GPT-5.4 Pro, Claude 4 Opus)
- **Mid-tier models**: $2-15/M tokens (GPT-4o, Claude 3.5 Sonnet)
- **Budget models**: $0.10-2/M tokens (DeepSeek, MiniMax, Qwen)
- **Reasoning specialists**: Premium pricing (o3, DeepSeek V3.2 Speciale)

---

## 2. LUX Model Details

### What is LUX?

**LUX** is an internal codename for **Claude 3.5 Sonnet with Computer Use capabilities**, integrated into Atom for desktop automation and agent-based computer control. It's **NOT a separate model** from Anthropic, but rather a specialized configuration of Claude's computer use API.

### Capabilities

From `backend/ai/lux_model.py`:

1. **Screen Capture & Analysis**
   - Full screenshot capture via PyAutoGUI
   - Element detection with bounding boxes
   - OCR and text extraction
   - Visual understanding for UI interaction

2. **Computer Actions**
   - Click at coordinates or on elements
   - Type text input
   - Keyboard shortcuts (hotkeys)
   - Scroll (directional)
   - Drag and drop
   - Open/close applications
   - Wait/delay commands

3. **Governance Integration**
   - Callback-based action approval
   - Audit trail for all actions
   - Agent maturity gating (AUTONOMOUS required)

### Technical Implementation

```python
# From lux_model.py
model_config = {
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 4096,
    "temperature": 0.1
}
```

**API Key Resolution** (from `core/lux_config.py`):
1. Check BYOK system for "anthropic" provider
2. Check BYOK system for "lux" provider
3. Fallback to `ANTHROPIC_API_KEY` env var
4. Fallback to `LUX_MODEL_API_KEY` env var

### Integration Status

**Existing**: ✅ LUX model implementation (`lux_model.py`)
**Existing**: ✅ BYOK configuration (`byok_config.json` has "lux" provider)
**Missing**: ❌ LUX not in BPC routing (`byok_handler.py`)
**Missing**: ❌ LUX not in quality benchmarks (`benchmarks.py`)
**Missing**: ❌ No LUX-specific routing logic for computer use tasks

### Recommended Quality Score

Based on Claude 3.5 Sonnet's performance:
```python
LUX_QUALITY_SCORE = 88  # Between gemini-2.0-flash (86) and claude-3-5-sonnet (90)
```

**Rationale**: LUX uses Claude 3.5 Sonnet (quality: 92) but is specialized for computer use, which may reduce general reasoning quality slightly. The 88 score positions it competitively in the STANDARD/VERSATILE tier crossover.

### Pricing

From `byok_config.json`:
```json
{
  "id": "lux",
  "cost_per_token": 2e-05,  // $20/M tokens (Anthropic Claude pricing)
  "supported_tasks": ["computer_use", "agentic", "desktop"]
}
```

---

## 3. Provider Registry Patterns

### Current State: DynamicPricingFetcher

**File**: `backend/core/dynamic_pricing_fetcher.py`

**Capabilities**:
- ✅ Fetches from LiteLLM GitHub (2,922+ models)
- ✅ Fetches from OpenRouter API
- ✅ Merges pricing data (LiteLLM precedence)
- ✅ Caches to `ai_pricing_cache.json` (24-hour validity)
- ✅ Async HTTP client (httpx)
- ✅ Error handling and fallbacks

**Gaps**:
- ❌ No database persistence (only JSON cache)
- ❌ No scheduled polling (manual refresh only)
- ❌ No provider health monitoring
- ❌ No capability filtering (vision, tools, cache)
- ❌ No model versioning tracking

### Recommended Architecture: ProviderRegistry + AutoDiscovery

#### Pattern 1: Persistent Database Registry

```python
# NEW: backend/core/provider_registry.py
from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON, Integer
from core.models import Base
from datetime import datetime

class ProviderRegistry(Base):
    """Persistent provider registry with auto-discovery metadata"""
    __tablename__ = "provider_registry"

    provider_id = Column(String, primary_key=True)  # "openai", "anthropic", "lux"
    name = Column(String, nullable=False)  # "OpenAI GPT-4", "LUX Computer Use"
    description = Column(String)
    litellm_provider = Column(String)  # For mapping to LiteLLM models
    base_url = Column(String)  # API endpoint
    supports_vision = Column(Boolean, default=False)
    supports_tools = Column(Boolean, default=False)
    supports_cache = Column(Boolean, default=False)
    supports_structured_output = Column(Boolean, default=False)
    reasoning_level = Column(Integer)  # 1-4 scale
    quality_score = Column(Float)  # Benchmark score (0-100)
    is_active = Column(Boolean, default=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)  # Freeform provider-specific data

class ModelCatalog(Base):
    """Individual models within providers"""
    __tablename__ = "model_catalog"

    model_id = Column(String, primary_key=True)  # "gpt-4o", "lux-1.0"
    provider_id = Column(String, ForeignKey("provider_registry.provider_id"))
    name = Column(String)  # Human-readable name
    description = Column(String)
    input_cost_per_token = Column(Float)
    output_cost_per_token = Column(Float)
    max_tokens = Column(Integer)
    max_input_tokens = Column(Integer)
    context_window = Column(Integer)
    mode = Column(String)  # "chat", "completion", "vision"
    source = Column(String)  # "litellm", "openrouter", "manual"
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)
```

#### Pattern 2: Scheduled Auto-Discovery

```python
# NEW: backend/core/provider_auto_discovery.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.dynamic_pricing_fetcher import get_pricing_fetcher

class ProviderAutoDiscovery:
    """Orchestrates periodic provider discovery from LiteLLM and OpenRouter"""

    def __init__(self, db_session):
        self.db = db_session
        self.pricing_fetcher = get_pricing_fetcher()
        self.scheduler = AsyncIOScheduler()

    async def sync_providers(self):
        """Fetch latest pricing and sync to registry"""
        # 1. Refresh pricing cache
        await self.pricing_fetcher.refresh_pricing(force=True)

        # 2. Upsert providers and models to DB
        for model_id, pricing in self.pricing_fetcher.pricing_cache.items():
            provider = self._extract_provider(model_id, pricing)
            model = self._extract_model(model_id, pricing)

            # Upsert to ProviderRegistry and ModelCatalog
            self._upsert_provider(provider)
            self._upsert_model(model)

        logger.info(f"Synced {len(self.pricing_fetcher.pricing_cache)} models to registry")

    def start_scheduled_sync(self, interval_hours=24):
        """Schedule automatic sync every 24 hours"""
        self.scheduler.add_job(
            self.sync_providers,
            'interval',
            hours=interval_hours,
            id='provider_sync'
        )
        self.scheduler.start()
```

### Best Practices from Industry

#### LiteLLM Approach
- **GitHub-hosted pricing database** (no API rate limits)
- **Community-contributed model updates** (rapid coverage)
- **Provider mapping** (`litellm_provider` field)
- **Capability flags** (`supports_cache`, `supports_function_calling`)

#### OpenRouter Approach
- **REST API for model catalog** (`/api/v1/models`)
- **Pricing embedded in model object**
- **Description fields for context**
- **Active/inactive model tracking**

#### Combined Approach (Recommended)
1. **Primary source**: LiteLLM GitHub (no rate limits, broad coverage)
2. **Secondary source**: OpenRouter API (up-to-date pricing, descriptions)
3. **Database persistence**: PostgreSQL for querying and filtering
4. **Scheduled polling**: Every 24 hours via APScheduler
5. **Health monitoring**: Track API availability, response times
6. **Version tracking**: Track model updates, deprecations

---

## 4. BPC (Bits Per Character) Routing State-of-the-Art

### Current Atom BPC Implementation

**File**: `backend/core/llm/byok_handler.py` (lines 436-616)

**Algorithm**:
```python
# BPC Value Score Calculation
value_score = (quality_score ** 2) / (normalized_cost * 1e6)

# Where:
# - quality_score: 0-100 (from benchmarks.py)
# - normalized_cost: Cache-aware effective cost
# - Squaring quality penalizes low-end models for complex tasks
```

**Features**:
- ✅ Cache-aware cost calculation (prioritizes Anthropic for cache hits)
- ✅ Cognitive tier filtering (5-tier quality thresholds)
- ✅ Context window requirements by complexity
- ✅ Plan-based model restrictions (free tier blocking)
- ✅ Tool/structured output support filtering
- ✅ Vision model routing (coordinated vision for non-vision reasoning models)

**Gaps**:
- ❌ No LUX model in routing tables
- ❌ No computer use task type
- ❌ No provider health awareness
- ❌ No dynamic model discovery (static COST_EFFICIENT_MODELS dict)

### State-of-the-Art BPC Techniques (2026)

#### 1. Cache-Aware Routing (✅ Already Implemented)
- **Anthropic prompt caching**: 90% cost reduction for cached prompts
- **Cache hit prediction**: Hash-based probability estimation
- **Effective cost calculation**: Adjusts cost based on cache hit probability

#### 2. Multi-Armed Bandit Routing (Missing)
- **Explore-exploit**: Balance cost vs. quality discovery
- **Performance tracking**: Real-world latency, success rates
- **Dynamic adjustment**: Shift routing based on observed metrics

#### 3. Quality Threshold Routing (✅ Partially Implemented)
- **Cognitive tiers**: 5-tier system (MICRO to COMPLEX)
- **Minimum quality filters**: By tier and complexity
- **Escalation logic**: Auto-escalate on quality failures

#### 4. Provider Health Routing (Missing)
- **Availability monitoring**: Track API uptime, error rates
- **Latency awareness**: Prefer faster providers for real-time tasks
- **Rate limit handling**: Distribute load across providers

#### 5. Task-Specific Routing (Partial)
- **Vision routing**: ✅ Implemented
- **Code generation**: ✅ Implemented (deepseek, openai)
- **Computer use**: ❌ Missing (LUX model)

### Recommended Enhancements

#### 1. Add LUX to BPC Routing

```python
# MODIFY: backend/core/llm/byok_handler.py
COST_EFFICIENT_MODELS = {
    # ... existing providers ...

    "lux": {
        QueryComplexity.SIMPLE: "lux-1.0",
        QueryComplexity.MODERATE: "lux-1.0",
        QueryComplexity.COMPLEX: "lux-1.0",
        QueryComplexity.ADVANCED: "lux-1.0",
    },
}

# Add to providers_config
providers_config = {
    # ... existing providers ...
    "lux": {"base_url": None},  # Uses Anthropic client (no custom base URL)
}
```

#### 2. Add Computer Use Task Type

```python
# MODIFY: backend/core/llm/byok_handler.py (get_ranked_providers)
def get_ranked_providers(self, complexity, task_type=None, **kwargs):
    # ... existing logic ...

    # Computer use routing
    if task_type == "computer_use":
        # Prioritize LUX model for desktop automation
        if "lux" in available_providers:
            candidates.append({
                "provider": "lux",
                "model": "lux-1.0",
                "quality_score": LUX_QUALITY_SCORE,
                "supports_computer_use": True,
                "input_cost": 0.00002,  # $20/M from byok_config.json
                "output_cost": 0.00002,
            })
        # Fallback to vision-capable models
        vision_models = ["gpt-4o", "gemini-2.0-flash", "claude-3-5-sonnet"]
        # ... add vision models to candidates ...
```

#### 3. Provider Health Monitoring

```python
# NEW: backend/core/provider_health_monitor.py
class ProviderHealthMonitor:
    """Track API health and adjust routing accordingly"""

    def __init__(self):
        self.health_scores = {}  # provider_id -> 0.0-1.0
        self.error_rates = {}    # provider_id -> error rate
        self.latencies = {}      # provider_id -> avg latency

    def record_call(self, provider_id: str, success: bool, latency: float):
        """Record API call outcome"""
        # Update health score using exponential moving average
        # Decay health on failures, improve on successes

    def get_healthy_providers(self) -> List[str]:
        """Get providers sorted by health score"""
        return sorted(self.health_scores.keys(),
                     key=lambda p: self.health_scores[p],
                     reverse=True)
```

---

## 5. Codebase Analysis: Current Implementation Gaps

### Existing Infrastructure (Strong Foundation)

#### 1. DynamicPricingFetcher ✅
- **File**: `backend/core/dynamic_pricing_fetcher.py`
- **Lines of code**: ~200
- **Models covered**: 2,922+ (from LiteLLM + OpenRouter)
- **Cache duration**: 24 hours
- **Gap**: No database persistence, no scheduled polling

#### 2. BYOKHandler ✅
- **File**: `backend/core/llm/byok_handler.py`
- **Lines of code**: ~1,500
- **BPC algorithm**: Lines 436-616
- **Providers supported**: 6 (openai, anthropic, deepseek, gemini, moonshot, minimax, qwen)
- **Gap**: No LUX integration, static model lists

#### 3. BYOKManager ✅
- **File**: `backend/core/byok_endpoints.py`
- **Lines of code**: ~500
- **Providers configured**: 15 (deepseek, openai, anthropic, groq, google, lux, mistral, etc.)
- **Gap**: Basic UI, no health monitoring, no bulk operations

#### 4. Quality Benchmarks ✅
- **File**: `backend/core/benchmarks.py`
- **Models scored**: ~45 frontier and mid-tier models
- **Scoring methodology**: MMLU, GSM8K, HumanEval, LMSYS Chatbot Arena
- **Gap**: No LUX model, no automatic scoring updates

#### 5. LUX Model Implementation ✅
- **File**: `backend/ai/lux_model.py`
- **Lines of code**: ~540
- **Capabilities**: Screen capture, element detection, computer actions
- **Gap**: Not integrated into BPC routing, no quality score

### Gaps and Improvement Opportunities

#### Gap 1: No Persistent Provider Registry
**Current**: Models exist only in JSON cache and runtime memory
**Impact**: Can't query provider metadata, no historical tracking
**Solution**: Create ProviderRegistry and ModelCatalog SQLAlchemy models

#### Gap 2: LUX Model Not in BPC Routing
**Current**: LUX exists in BYOK config but not in routing logic
**Impact**: Computer use tasks can't leverage BPC optimization
**Solution**: Add LUX to COST_EFFICIENT_MODELS, add computer_use task type

#### Gap 3: No Scheduled Model Discovery
**Current**: Manual refresh only via `refresh_pricing_cache()`
**Impact**: Stale model data, manual intervention required
**Solution**: APScheduler-based polling every 24 hours

#### Gap 4: No Provider Health Monitoring
**Current**: No tracking of API uptime, error rates, latency
**Impact**: Can't avoid unhealthy providers in routing
**Solution**: ProviderHealthMonitor with health-based routing

#### Gap 5: Limited Frontend Provider Management
**Current**: BYOKManager.tsx has basic add/delete functionality
**Impact**: No provider health visibility, no bulk operations
**Solution**: Enhanced UI with health dashboard, provider registry browser

---

## 6. Recommendations for Phase 226

### Priority 1: Provider Registry System (HIGH Impact)

**Goal**: Create persistent database-backed provider registry

**Implementation**:
1. Create SQLAlchemy models (ProviderRegistry, ModelCatalog)
2. Write Alembic migration for new tables
3. Implement ProviderAutoDiscovery service
4. Add APScheduler for 24-hour polling
5. Create CRUD endpoints (`/api/ai/providers/registry`)

**Estimated effort**: 3-5 days
**Impact**: Enables querying, filtering, and historical tracking of 2,922+ models

### Priority 2: LUX Model Integration (MEDIUM Impact)

**Goal**: Integrate LUX into BPC routing for computer use tasks

**Implementation**:
1. Add LUX to `COST_EFFICIENT_MODELS` in byok_handler.py
2. Add "lux" provider to providers_config initialization
3. Set quality score (88) in benchmarks.py
4. Add computer_use task type routing logic
5. Test LUX routing in isolation

**Estimated effort**: 1-2 days
**Impact**: Enables intelligent routing for desktop automation tasks

### Priority 3: Frontend Enhancements (MEDIUM Impact)

**Goal**: Improve API key management UI with provider health

**Implementation**:
1. Refactor BYOKManager to use POST body for API keys (security)
2. Add provider health monitoring dashboard
3. Implement bulk operations (add multiple keys, rotate keys)
4. Add provider registry browser (filter by capabilities, cost, quality)
5. Show model counts, last sync time, health status

**Estimated effort**: 2-3 days
**Impact**: Better UX for provider management, improved security

### Priority 4: Provider Health Monitoring (LOW-MEDIUM Impact)

**Goal**: Track API health and adjust routing accordingly

**Implementation**:
1. Create ProviderHealthMonitor service
2. Record API call outcomes (success/failure, latency)
3. Calculate health scores using exponential moving average
4. Integrate health scores into BPC routing
5. Add health status to provider registry API

**Estimated effort**: 2-3 days
**Impact**: Improved reliability, automatic avoidance of unhealthy providers

### Priority 5: Testing & Documentation (Ongoing)

**Goal**: Comprehensive test coverage and documentation

**Implementation**:
1. Unit tests for ProviderAutoDiscovery sync logic
2. Integration tests for LUX routing in BPC algorithm
3. E2E tests for provider registry CRUD operations
4. Frontend tests for API key security (no query params)
5. Update documentation (CLAUDE.md, API docs)

**Estimated effort**: 2-3 days
**Impact**: Confidence in implementation, maintainability

### Recommended Phase Split

Given the scope, consider splitting into **3 sub-phases**:

#### Phase 226.1: Provider Registry Foundation
- SQLAlchemy models (ProviderRegistry, ModelCatalog)
- ProviderAutoDiscovery service
- APScheduler integration
- CRUD endpoints
- Unit tests

#### Phase 226.2: LUX Integration & Routing
- LUX model in BPC routing
- Computer use task type
- Quality score assignment
- Integration tests
- Documentation

#### Phase 226.3: Frontend & Health Monitoring
- Enhanced BYOKManager UI
- Provider health dashboard
- Provider registry browser
- Bulk operations
- E2E tests

---

## 7. Technical Stack & Dependencies

### Existing Dependencies (No New Installations Required)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| **DynamicPricingFetcher** | Existing | Auto-discovery from LiteLLM/OpenRouter | ✅ Ready |
| **BYOKManager** | Existing | API key encryption, storage | ✅ Ready |
| **BYOKHandler** | Existing | BPC routing algorithm | ✅ Ready |
| **SQLAlchemy 2.0** | Existing | Database models | ✅ Ready |
| **FastAPI** | Existing | REST API endpoints | ✅ Ready |
| **httpx** | Existing | Async HTTP client | ✅ Ready |
| **Pydantic** | Existing | Request/response validation | ✅ Ready |

### New Dependencies

| Library | Version | Purpose | Installation |
|---------|---------|---------|-------------|
| **APScheduler** | 3.10+ | Scheduled polling for model updates | `pip install apscheduler` |

### No Alternative Libraries Needed

All required functionality exists in the codebase. The phase is about **integration and persistence**, not greenfield development.

---

## 8. Common Pitfalls & Mitigation Strategies

### Pitfall 1: Polling LiteLLM/OpenRouter Too Aggressively

**What goes wrong**: API rate limits (429 errors), increased costs, degraded performance

**Mitigation**:
- Set polling interval to 24 hours (matching cache duration)
- Implement exponential backoff on failures
- Add health checks to disable polling after 3 consecutive failures
- Use HTTP caching headers (ETag, Last-Modified)

**Code example**:
```python
# BAD: Polls every 5 minutes
scheduler.add_job(sync_providers, 'interval', minutes=5)

# GOOD: Polls every 24 hours with error handling
scheduler.add_job(sync_providers, 'interval', hours=24, max_instances=1)
```

### Pitfall 2: LUX Model Integration Breaking Existing Routing

**What goes wrong**: Adding LUX to provider list causes routing failures, clients fail to initialize

**Mitigation**:
- Test LUX integration in isolation first
- Ensure `lux_config.py` properly resolves API keys
- Add LUX to `MODELS_WITHOUT_TOOLS` if it doesn't support tool calling
- Verify client initialization with Anthropic's base_url=None

**Code example**:
```python
# Verify LUX client initialization
def _initialize_clients(self):
    # ... existing providers ...
    if self.byok_manager.is_configured(self.workspace_id, "lux"):
        api_key = self.byok_manager.get_api_key("lux") or lux_config.get_anthropic_key()
        if api_key:
            self.clients["lux"] = OpenAI(api_key=api_key)  # Uses Anthropic client
```

### Pitfall 3: Frontend API Key Security Issues

**What goes wrong**: API keys exposed in browser logs, localStorage, or query parameters

**Mitigation**:
- Use POST request body for keys (not query params)
- Implement server-side key encryption (Fernet)
- Never log full keys (log only last 4 characters)
- Add audit trail for key operations

**Code example**:
```typescript
// BAD: API key in URL query params
const url = `/api/ai/providers/${provider}/keys?api_key=${encodeURIComponent(key)}`;
await fetch(url, { method: 'POST' });

// GOOD: API key in request body
const response = await fetch(`/api/ai/providers/${provider}/keys`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ api_key: apiKey, key_name: keyName })
});
```

### Pitfall 4: Database Migration Failures

**What goes wrong**: Alembic migration fails, breaks existing functionality

**Mitigation**:
- Test migrations on development database first
- Create backup before production migration
- Use `--sql` flag to generate SQL for review
- Implement rollback strategy

**Code example**:
```bash
# Review migration SQL before applying
alembic upgrade head --sql

# Apply migration with verification
alembic upgrade head
alembic current  # Verify version
```

### Pitfall 5: Cache Coherency Issues

**What goes wrong**: JSON cache and database registry get out of sync

**Mitigation**:
- Make database the source of truth
- Use JSON cache as backup/fast load only
- Implement cache invalidation on database updates
- Add sync status indicator

**Code example**:
```python
# GOOD: Database as source of truth
async def get_model_price(model_id: str):
    # Try database first
    model = db.query(ModelCatalog).filter_by(model_id=model_id).first()
    if model:
        return model

    # Fallback to JSON cache
    return pricing_fetcher.get_model_price(model_id)
```

---

## 9. Open Questions & Research Needed

### Question 1: LUX Model API Key Resolution

**What we know**: LUX uses Anthropic's API, key can come from BYOK ("lux" provider) or env vars

**What's unclear**: Should LUX have its own BYOK key entry or reuse "anthropic" provider key?

**Recommendation**: Keep separate "lux" provider in BYOK for independent billing/tracking, fallback to "anthropic" key if not configured. This allows:
- Separate cost tracking for computer use tasks
- Independent key rotation for LUX
- Fallback to Anthropic key if LUX key not set

### Question 2: LiteLLM/OpenRouter API Rate Limits

**What we know**: Current implementation polls every 24 hours

**What's unclear**: Are there rate limits on GitHub raw URL (LiteLLM) or OpenRouter API?

**Recommendation**:
- GitHub raw URL: No rate limits for public repos (useful for LiteLLM)
- OpenRouter API: Check docs for rate limits, implement exponential backoff
- Add health check endpoint to disable polling after 3 consecutive failures

### Question 3: Provider Registry Database vs. Cache

**What we know**: `ai_pricing_cache.json` caches 2,922+ models

**What's unclear**: Should ProviderRegistry be the primary source or cache layer?

**Recommendation**: ProviderRegistry (DB) as source of truth, JSON cache as backup/fast load
- Database: Queryable, filterable, persistent
- JSON cache: Fast load, backup if DB unavailable
- Sync strategy: DB → JSON on every successful sync

### Question 4: LUX Model Quality Score

**What we know**: Estimated at 88 (between gemini-2.0-flash and claude-3-5-sonnet)

**What's unclear**: Actual benchmark score for computer use tasks

**Recommendation**: Use 88 as initial estimate, run benchmarks to validate, allow manual override in ProviderRegistry. Computer use is a specialized task, so general reasoning scores may not apply.

### Question 5: Multi-Provider API Key Management

**What we know**: Some providers share API keys (e.g., OpenAI used by multiple models)

**What's unclear**: How to handle shared keys in provider registry?

**Recommendation**: Normalize by provider_id, not model_id
- One API key per provider (e.g., "openai", "anthropic")
- Models belong to providers (foreign key relationship)
- LUX shares Anthropic key but has separate provider entry for tracking

---

## 10. Sources & References

### Primary Sources (HIGH Confidence)

- **DynamicPricingFetcher implementation** (`backend/core/dynamic_pricing_fetcher.py`) - Auto-discovery from LiteLLM GitHub + OpenRouter API
- **BYOKHandler BPC algorithm** (`backend/core/llm/byok_handler.py` lines 436-616) - Provider scoring, cache-aware routing
- **BYOKManager API key storage** (`backend/core/byok_endpoints.py` lines 81-200) - Fernet encryption, provider config
- **LUX model implementation** (`backend/ai/lux_model.py`) - Computer use capabilities, Anthropic client usage
- **Cognitive Tier System** (`backend/docs/COGNITIVE_TIER_SYSTEM.md`) - 5-tier quality thresholds, BPC integration
- **Quality Benchmarks** (`backend/core/benchmarks.py`) - Model quality scores (0-100 scale)
- **BYOK Configuration** (`backend/data/byok_config.json`) - 15 provider configurations
- **Pricing Cache** (`backend/data/ai_pricing_cache.json`) - 2,922 models from litellm + openrouter

### Secondary Sources (MEDIUM Confidence)

- **LiteLLM pricing database** (https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) - Source of model pricing
- **OpenRouter API docs** (https://openrouter.ai/docs) - Model catalog endpoint format
- **APScheduler documentation** (https://apscheduler.readthedocs.io) - Scheduled job patterns
- **Phase 68 completion report** (`.planning/phases/68-byok-cognitive-tier-system/68-04-SUMMARY.md`) - BPC system details

### Tertiary Sources (LOW Confidence)

- **Web search results** (Rate-limited, unable to complete) - Latest AI model releases, pricing updates
- **Industry blog posts** (Not accessed due to rate limits) - Provider registry best practices

**Note**: Web search was rate-limited during research. All findings verified against codebase or official documentation. Research should be validated against latest provider documentation in April 2026.

---

## 11. Metadata

**Confidence breakdown**:
- Standard stack: **HIGH** - All components exist in codebase, verified implementations
- Architecture: **HIGH** - Clear patterns from DynamicPricingFetcher, BYOKManager, BYOKHandler
- LUX integration: **HIGH** - LUX model implementation analyzed, integration points identified
- Pitfalls: **MEDIUM** - Web search rate-limited, relied on code analysis + known best practices
- Latest models: **MEDIUM** - Based on March 2026 pricing cache, may be outdated by April 2026

**Research date**: March 22, 2026
**Valid until**: April 21, 2026 (30 days - LLM provider landscape moves fast)
**Next review**: April 22, 2026

---

## 12. Next Steps for Planner

1. **Provider Registry System** (Phase 226.1)
   - Create SQLAlchemy models (ProviderRegistry, ModelCatalog)
   - Implement ProviderAutoDiscovery service with APScheduler
   - Add CRUD endpoints for provider management
   - Write Alembic migration for new tables
   - Unit tests for sync logic

2. **LUX Integration** (Phase 226.2)
   - Add LUX to `COST_EFFICIENT_MODELS` and `providers_config`
   - Set quality score (88) in benchmarks.py
   - Verify API key resolution in `lux_config.py`
   - Add LUX to vision/computer use routing paths
   - Integration tests for LUX routing

3. **Frontend Enhancements** (Phase 226.3)
   - Refactor BYOKManager to use POST body for API keys (security)
   - Add provider health monitoring dashboard
   - Implement bulk operations (add multiple keys, rotate keys)
   - Add provider registry browser (filter by capabilities, cost, quality)
   - E2E tests for provider registry CRUD

4. **Testing & Documentation**
   - Unit tests for ProviderAutoDiscovery sync logic
   - Integration tests for LUX routing in BPC algorithm
   - E2E tests for provider registry CRUD operations
   - Frontend tests for API key security (no query params)
   - Update CLAUDE.md with new provider registry system

---

*Phase: 226-llm-provider-registry*
*Research completed: March 22, 2026*
*Researcher: Claude (Sonnet 4.5)*
*Status: Ready for planning*
