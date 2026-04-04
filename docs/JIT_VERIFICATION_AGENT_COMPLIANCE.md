# JIT Verification for Agent Compliance - Implementation Guide

## Overview: How Agents Use JIT Verification for Compliance

The JIT Verification Cache ensures AI agents make decisions based on **verified, current business policies** by proactively checking that policy citations (documents in R2/S3 storage) exist before agents use them for compliance decisions.

## The Complete Flow

### 1. Agent Decision Flow with JIT Verification

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Request                               │
│           "Process this $750 invoice for payment"               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            WorldModel.recall_experiences()                      │
│  Retrieves: experiences, knowledge, formulas, conversations    │
│  AND business_facts (with citations) ← KEY FOR COMPLIANCE      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              JIT Verification Cache (L1/L2)                     │
│  ✓ Check: Is citation already verified?                         │
│  ✓ HIT: Return cached result (<1ms)                             │
│  ✓ MISS: Verify in R2/S3 (~200ms), cache result                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            Compliance Decision Point                             │
│  For each business fact:                                         │
│  1. Check citation verification status                          │
│  2. If citation exists → Fact is VALID                          │
│  3. If citation missing → Fact is STALE                         │
│  4. Apply business rules accordingly                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Action                                │
│  ✓ Valid fact: "Invoices > $500 need VP approval"              │
│  ✓ Invoice is $750 → Request VP approval                       │
│  OR                                                             │
│  ✗ Stale fact: Flag for human review                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Code Flow: From Agent to Compliance

#### Step 1: Agent Receives Task

```python
# core/generic_agent.py
async def execute(self, task_input: str):
    """
    Agent receives: "Process this $750 invoice for payment"
    """

    # Step 1: Recall relevant memory (includes business facts)
    memory_context = await self.world_model.recall_experiences(
        agent=self._get_registry_model(),
        current_task_description=task_input  # "Process this $750 invoice..."
    )

    # memory_context now contains:
    # {
    #     "experiences": [...],
    #     "knowledge": [...],
    #     "formulas": [...],
    #     "business_facts": [  # ← KEY: Compliance facts
    #         {
    #             "fact": "Invoices > $500 need VP approval",
    #             "citations": ["s3://your-bucket/policies/approval.pdf"],
    #             "verification_status": "verified",
    #             "last_verified": "2026-03-23T10:00:00"
    #         }
    #     ],
    #     "episodes": [...]
    # }

    return await self._think_and_act(task_input, memory_context)
```

#### Step 2: Business Facts Retrieved (WITH JIT Cache)

```python
# core/agent_world_model.py - recall_experiences()

# Line 768: Business facts are retrieved
business_facts = await self.get_relevant_business_facts(
    current_task_description,  # "Process this $750 invoice..."
    limit=limit
)

# WITHOUT JIT Cache (Old Way - SLOW):
# - Direct LanceDB search: ~45ms
# - Each fact's citations NOT verified
# - Agent doesn't know if policy document exists!

# WITH JIT Cache (New Way - FAST):
# - Cached search: ~10ms (if queried before)
# - Citations PRE-VERIFIED via JIT cache
# - Agent knows policy document exists!

async def get_relevant_business_facts(self, query: str, limit: int = 5):
    """
    Search business facts with JIT cache integration
    """
    # OLD: Direct search (slow, no citation verification)
    # results = self.db.search(table_name=self.facts_table_name, query=query, limit=limit)

    # NEW: Use JIT cache (fast, with citation verification)
    from core.jit_verification_cache import get_jit_verification_cache
    cache = get_jit_verification_cache()

    # Check cache first (L1: <1ms, L2: ~5ms)
    cached_facts = await cache.get_business_facts(query, limit)

    if cached_facts:
        return [BusinessFact(**fact) for fact in cached_facts]

    # Cache miss: Do actual search and cache result
    results = self.db.search(table_name=self.facts_table_name, query=query, limit=limit)
    # ... cache results for next time ...

    return facts
```

#### Step 3: Compliance Decision with Citation Verification

```python
# core/generic_agent.py - _think_and_act()

async def _think_and_act(self, task: str, memory_context: dict):
    """
    Agent makes compliance decision using verified business facts
    """
    business_facts = memory_context.get("business_facts", [])

    # Check compliance against verified facts
    compliance_result = await self._check_compliance(task, business_facts)

    if not compliance_result["compliant"]:
        # Action requires additional approval/verification
        return await self._handle_non_compliant(task, compliance_result)

    # Proceed with action
    return await self._execute_action(task)

async def _check_compliance(self, task: str, facts: List[BusinessFact]) -> dict:
    """
    Check compliance using JIT-verified business facts
    """
    from core.jit_verification_cache import get_jit_verification_cache
    cache = get_jit_verification_cache()

    invoice_amount = self._extract_invoice_amount(task)  # $750

    for fact in facts:
        # Verify citations are still valid (FAST with cache)
        for citation in fact.citations:
            verification = await cache.verify_citation(citation)

            if not verification.exists:
                # Citation is stale - policy document missing!
                logger.warning(f"Stale citation detected: {citation}")
                return {
                    "compliant": False,
                    "reason": f"Policy citation outdated: {citation}",
                    "fact": fact.fact,
                    "action_required": "human_review"
                }

        # Citation verified - apply business rule
        if "Invoices > $500 need VP approval" in fact.fact:
            if invoice_amount > 500:
                return {
                    "compliant": False,
                    "reason": "Invoice exceeds $500 threshold",
                    "fact": fact.fact,
                    "action_required": "vp_approval"
                }

    return {"compliant": True}
```

#### Step 4: Action Execution (If Compliant)

```python
# If invoice amount was $400 instead of $750

async def _execute_action(self, task: str):
    """
    Execute action (compliance checks passed)
    """
    invoice_amount = self._extract_invoice_amount(task)

    if invoice_amount < 500:
        # Within approval limit
        return {
            "status": "approved",
            "reason": "Invoice within automatic approval limit",
            "approved_by": "agent",
            "compliance_checks": "passed"
        }
```

### 3. Background Worker: Proactive Verification

While agents are making decisions, the **background worker** proactively verifies citations to keep the cache warm:

```python
# core/jit_verification_worker.py

async def _run_verification_cycle(self):
    """
    Runs every hour (configurable)
    """
    # 1. Fetch all business facts
    facts = await self.world_model.list_all_facts(limit=10000)

    # 2. Prioritize citations
    #    - Frequently accessed (high access count)
    #    - Not verified recently (>24 hours)
    #    - Unverified or outdated status
    jobs = self._prioritize_citations(facts)

    # 3. Verify batch (50 citations per run)
    for job in jobs[:self.batch_size]:
        # Verify citation (uses cache automatically)
        result = await self.cache.verify_citation(job.citation)

        # 4. Update fact status if citation is stale
        if not result.exists:
            await self.world_model.update_fact_verification(
                job.fact_id,
                "outdated"
            )
            logger.warning(f"Citation outdated: {job.citation}")

    # Result: Cache is warm, agents get fast lookups
```

## Example Scenarios

### Scenario 1: Invoice Approval (Compliant)

**Request:** "Process $750 invoice for payment"

**Flow:**

1. **Agent recalls business facts** (with JIT cache check)
   ```python
   fact = {
       "fact": "Invoices > $500 need VP approval",
       "citations": ["s3://your-bucket/policies/approval.pdf"],
       "verification_status": "verified"
   }
   ```

2. **JIT Cache Verification** (<1ms - cache hit!)
   ```python
   result = await cache.verify_citation("s3://your-bucket/policies/approval.pdf")
   # Returns: {exists: True, checked_at: "2026-03-23T10:00:00"}
   ```

3. **Compliance Decision**
   ```python
   if result.exists:  # Citation is valid
       if invoice_amount > 500:
           return "Request VP approval"
   ```

4. **Agent Action**
   ```python
   return {
       "status": "vp_approval_required",
       "reason": "Invoice exceeds $500 (per approval policy)",
       "policy_verified": True,
       "citation": "s3://your-bucket/policies/approval.pdf"
   }
   ```

### Scenario 2: Invoice Approval (Stale Citation Detected)

**Request:** "Process $750 invoice for payment"

**Flow:**

1. **Agent recalls business facts**
   ```python
   fact = {
       "fact": "Invoices > $500 need VP approval",
       "citations": ["s3://your-bucket/policies/approval.pdf"],
       "verification_status": "verified"  # Might be stale!
   }
   ```

2. **JIT Cache Verification** (<1ms - cache hit, but citation missing!)
   ```python
   result = await cache.verify_citation("s3://your-bucket/policies/approval.pdf")
   # Returns: {exists: False, checked_at: "2026-03-23T10:00:00"}
   ```

3. **Compliance Decision - STALE DETECTED**
   ```python
   if not result.exists:
       # Policy document is missing - don't apply rule!
       logger.warning(f"Stale citation: {citation}")
       return {
           "status": "human_review_required",
           "reason": "Policy citation outdated - cannot verify approval rule",
           "fact": "Invoices > $500 need VP approval",
           "stale_citation": "s3://your-bucket/policies/approval.pdf"
       }
   ```

4. **Agent Action**
   ```python
   return {
       "status": "escalated",
       "escalation_reason": "Business rule cannot be verified - policy document missing",
       "action": "Route to finance team for manual review"
   }
   ```

### Scenario 3: Cache Miss - First-Time Verification

**Request:** "Check if this contract needs legal review"

**Flow:**

1. **Agent recalls business facts**
   ```python
   fact = {
       "fact": "Contracts > $100,000 need legal review",
       "citations": ["s3://your-bucket/policies/contracts.pdf"],
       "verification_status": "unverified"
   }
   ```

2. **JIT Cache Verification** (cache miss - verify now)
   ```python
   result = await cache.verify_citation("s3://your-bucket/policies/contracts.pdf")

   # L1 cache miss - check L2
   # L2 cache miss - verify in R2/S3 (~200ms)
   # R2/S3 check: Document exists!
   # Cache result in L1 and L2
   # Returns: {exists: True, checked_at: "2026-03-23T10:05:00"}

   # Next call will be <1ms (cache hit)
   ```

3. **Compliance Decision**
   ```python
   if result.exists:
       contract_value = self._extract_contract_value(task)
       if contract_value > 100000:
           return "Request legal review"
   ```

## Integration Points

### 1. Agent Execution Service

```python
# core/agent_execution_service.py

async def execute_agent_task(agent_id: str, task: str):
    """
    Execute agent with JIT-verified compliance checks
    """
    agent = get_agent(agent_id)

    # Recall memory (includes JIT-verified business facts)
    memory_context = await agent.world_model.recall_experiences(
        agent=agent,
        current_task_description=task
    )

    # Check compliance using verified facts
    compliance_check = await check_agent_compliance(
        agent_id=agent_id,
        task=task,
        business_facts=memory_context.get("business_facts", [])
    )

    if not compliance_check["compliant"]:
        return handle_non_compliant(agent, task, compliance_check)

    # Execute action
    return await agent.execute(task, memory_context)
```

### 2. Agent Governance Integration

```python
# core/agent_governance_service.py

async def check_action_compliance(
    agent_id: str,
    action_type: str,
    business_facts: List[BusinessFact]
) -> dict:
    """
    Verify citations before allowing action
    """
    from core.jit_verification_cache import get_jit_verification_cache
    cache = get_jit_verification_cache()

    for fact in business_facts:
        # Verify all citations
        for citation in fact.citations:
            result = await cache.verify_citation(citation)

            if not result.exists:
                # Citation is stale - block action
                await log_compliance_violation(
                    agent_id=agent_id,
                    action_type=action_type,
                    reason=f"Stale citation: {citation}",
                    fact=fact.fact
                )

                return {
                    "allowed": False,
                    "reason": "Business rule cannot be verified - policy document missing",
                    "stale_citation": citation
                }

    return {"allowed": True}
```

### 3. Canvas Presentation Integration

```python
# tools/canvas_tool.py

async def present_compliance_canvas(agent_id: str, task: str):
    """
    Present canvas with verified business rules
    """
    from core.jit_verification_cache import get_jit_verification_cache
    cache = get_jit_verification_cache()

    # Get business facts
    facts = await cache.get_business_facts(task, limit=5)

    # Verify citations
    verified_facts = []
    for fact in facts:
        citations_status = []
        all_valid = True

        for citation in fact["citations"]:
            result = await cache.verify_citation(citation)
            citations_status.append({
                "citation": citation,
                "exists": result.exists,
                "verified_at": result.checked_at
            })

            if not result.exists:
                all_valid = False

        verified_facts.append({
            "fact": fact["fact"],
            "citations": citations_status,
            "all_citations_valid": all_valid,
            "can_apply_rule": all_valid
        })

    # Present canvas with verification status
    return {
        "canvas_type": "compliance_rules",
        "facts": verified_facts,
        "verification_timestamp": datetime.now()
    }
```

## Performance Benefits

### Before JIT Verification

```python
# OLD: No cache, slow verification
def check_compliance_old(task: str) -> dict:
    facts = search_business_facts(task)  # 50ms

    for fact in facts:
        for citation in fact.citations:
            # Check R2/S3 EVERY TIME - 200ms per citation
            exists = storage.check_exists(citation)  # 200ms

            if not exists:
                return {"compliant": False}

    # With 3 citations: 50ms + (3 * 200ms) = 650ms
    # Agent decision takes >1 second!
```

### After JIT Verification

```python
# NEW: Multi-level cache, fast verification
async def check_compliance_new(task: str) -> dict:
    cache = get_jit_verification_cache()

    facts = await cache.get_business_facts(task)  # 10ms (cached)

    for fact in facts:
        for citation in fact.citations:
            # Check cache FIRST - <1ms
            result = await cache.verify_citation(citation)  # <1ms (cached)

            if not result.exists:
                return {"compliant": False}

    # With 3 citations: 10ms + (3 * 1ms) = 13ms
    # Agent decision takes <100ms - 10x faster!
```

## Monitoring & Observability

### Agent Compliance Metrics

```python
# Track compliance checks
metrics = {
    "compliance_checks_total": 1000,
    "compliance_checks_passed": 950,
    "compliance_checks_failed_stale_citation": 30,
    "compliance_checks_failed_business_rule": 20,

    "citation_verification_cache_hit_rate": 0.85,
    "citation_verification_avg_latency_ms": 5,

    "business_facts_retrieved": 500,
    "business_facts_with_valid_citations": 470,
    "business_facts_with_stale_citations": 30
}
```

### Alerting

```python
# Alert on stale citations
if stale_citations_count > 10:
    alert_team(
        severity="warning",
        message=f"{stale_citations_count} business facts have stale citations",
        action="Update policy documents or remove stale facts"
    )

# Alert on low cache hit rate
if cache_hit_rate < 0.7:
    alert_team(
        severity="info",
        message=f"Low cache hit rate: {cache_hit_rate:.1%}",
        action="Consider warming cache or increasing cache size"
    )
```

## Summary

The JIT Verification Cache ensures agent compliance by:

1. ✅ **Verifying citations exist** before agents use business rules
2. ✅ **Detecting stale policies** (missing documents) immediately
3. ✅ **Providing fast lookups** (<1ms) through multi-level caching
4. ✅ **Proactively verifying** citations via background worker
5. ✅ **Escalating appropriately** when citations are outdated

**Result:** Agents make compliance decisions based on **verified, current business policies** with minimal latency.
