# Auto-Dev Module - Self-Evolving Agent Capabilities

**Last Updated:** April 10, 2026
**Reading Time:** 10 minutes
**Difficulty:** Intermediate

---

## Overview

**Auto-Dev** is Atom's self-evolving agent system that enables agents to learn from experience and improve their capabilities over time. Instead of manually writing and maintaining every skill, Auto-Dev allows agents to:

- 🧠 **Learn from failures** - Generate new skills from failed episodes
- 🔄 **Optimize existing skills** - Improve performance through mutation
- 🎯 **Adapt to your environment** - Tailor solutions to your specific use cases
- 🛡️ **Safe experimentation** - All testing happens in isolated sandboxes

### Two Learning Loops

Auto-Dev provides two complementary learning systems:

| System | Purpose | Trigger | Maturity Required |
|--------|---------|---------|-------------------|
| **Memento-Skills** | Generate new skills from failures | Agent fails task repeatedly | INTERN+ |
| **AlphaEvolver** | Optimize existing skills | Manual or automatic trigger | SUPERVISED+ |

---

## How It Works

### The Learning Pipeline

```
Agent Task Execution
        ↓
   Success or Failure?
        ↓
    ┌───┴───┐
    ↓       ↓
Success  Failure
    ↓       ↓
Record  ReflectionEngine
Episode     ↓
    ↓    Detect Patterns
    ↓       ↓
AlphaEvolver  MementoEngine
(Optional)   (Generate New Skill)
    ↓            ↓
Sandbox     Sandbox
Testing     Testing
    ↓            ↓
Fitness     User
Comparison  Approval
    ↓            ↓
Deploy?    Install?
```

### Key Components

1. **EventBus** - Tracks all agent events (task executions, skill usage, failures)
2. **ReflectionEngine** - Monitors failures and detects patterns
3. **MementoEngine** - Generates new skill proposals from failed episodes
4. **AlphaEvolverEngine** - Creates optimized variants of existing skills
5. **FitnessService** - Evaluates skill performance in sandbox
6. **ContainerSandbox** - Isolated Docker environment for safe testing

---

## Getting Started

### Prerequisites

Before enabling Auto-Dev, ensure:

- ✅ Agent maturity is INTERN or higher
- ✅ Workspace has Auto-Dev enabled
- ✅ Docker is available (for sandbox)
- ✅ Sufficient disk space for sandbox images

### Enable Auto-Dev

**Via API:**
```bash
curl -X PATCH http://localhost:8000/api/v1/workspaces/{workspace_id} \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": {
      "auto_dev": {
        "enabled": true,
        "memento_enabled": true,
        "alpha_evolver_enabled": true
      }
    }
  }'
```

**Via Database:**
```sql
UPDATE workspaces
SET configuration = jsonb_set(
  configuration,
  '{auto_dev,enabled}',
  'true'
)
WHERE id = 'your_workspace_id';
```

### Check Capability Gates

```bash
# Check if your agent can use Auto-Dev
curl http://localhost:8000/api/v1/agents/{agent_id}/auto-dev/capabilities
```

**Response:**
```json
{
  "success": true,
  "data": {
    "agent_id": "agent_123",
    "maturity_level": "SUPERVISED",
    "capabilities": {
      "memento_skills": true,
      "alpha_evolver": true,
      "background_evolution": false
    },
    "activation_requirements": {
      "memento_skills": "INTERN maturity required ✅",
      "alpha_evolver": "SUPERVISED maturity required ✅",
      "background_evolution": "AUTONOMOUS maturity required ❌"
    }
  }
}
```

---

## Memento-Skills: Learning from Failures

### What Are Memento-Skills?

When an agent fails a task repeatedly, Memento-Skills analyzes the failure and generates a new skill proposal that addresses the root cause.

### When It Triggers

Memento-Skills activates when:
1. Agent fails the same task 3+ times
2. Failure pattern is detected by ReflectionEngine
3. Agent has INTERN maturity or higher
4. Auto-Dev is enabled in workspace

### The Memento Process

1. **Failure Detection**
   ```bash
   # ReflectionEngine detects pattern
   GET /api/v1/auto-dev/reflection/check?agent_id=agent_123
   ```

2. **Skill Generation**
   ```json
   {
     "episode_id": "ep_456",
     "failure_count": 3,
     "proposed_skill": {
       "name": "fix_api_timeout_issue",
       "code": "async def execute_with_retry(...)",
       "description": "Retries API calls with exponential backoff"
     }
   }
   ```

3. **User Review**
   ```bash
   # Get pending proposals
   GET /api/v1/auto-dev/proposals?agent_id=agent_123&status=pending
   ```

4. **Approval & Installation**
   ```bash
   # Approve and install
   curl -X POST http://localhost:8000/api/v1/auto-dev/proposals/{proposal_id}/approve
   ```

### Example: API Timeout Skill

**Problem:** Agent fails when calling external API due to timeouts

**Memento-Skills generates:**
```python
async def api_call_with_retry(
    url: str,
    max_retries: int = 3,
    backoff_factor: float = 0.5
) -> dict:
    """
    Retry API calls with exponential backoff.
    Generated from episode ep_789 (3 failures).
    """
    import asyncio
    import httpx

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_factor * (2 ** attempt)
            await asyncio.sleep(wait_time)

    return {}
```

**Result:** Agent now handles API timeouts gracefully!

---

## AlphaEvolver: Optimizing Existing Skills

### What Is AlphaEvolver?

AlphaEvolver improves existing skills through iterative mutation and testing. It creates variants, tests them in a sandbox, and keeps the best performing version.

### When to Use It

- ⚡ **Skill is too slow** - Optimize for performance
- 💰 **Token usage is high** - Reduce LLM costs
- 🎯 **Accuracy issues** - Improve success rate
- 🔧 **Edge cases** - Handle rare scenarios

### The Evolution Process

1. **Trigger Evolution**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auto-dev/evolve \
     -H "Content-Type: application/json" \
     -d '{
       "skill_name": "data_analysis",
       "optimization_goal": "latency",
       "generations": 5
     }'
   ```

2. **Variant Generation**
   - AlphaEvolver creates 3-5 variants
   - Each variant has mutations (code changes)
   - Mutations are guided by AI AdvisorService

3. **Sandbox Testing**
   - Each variant runs in isolated Docker container
   - FitnessService measures performance
   - Compared against baseline skill

4. **Fitness Comparison**
   ```json
   {
     "baseline": {
       "latency_ms": 1250,
       "success_rate": 0.85,
       "token_usage": 1500
     },
     "variant_1": {
       "latency_ms": 980,  // 21.6% faster
       "success_rate": 0.87,
       "token_usage": 1450
     },
     "winner": "variant_1"
   }
   ```

5. **Deploy or Queue**
   - SUPERVISED: Results queued for your review
   - AUTONOMOUS: Best variant auto-deploys

### Example: Optimizing Data Analysis

**Original Skill:**
```python
async def analyze_sales_data(data: list) -> dict:
    """Analyze sales data - slow but accurate."""
    results = []
    for item in data:
        # Complex processing
        analysis = await llm.analyze(item)
        results.append(analysis)
    return {"results": results}
```

**AlphaEvolver creates Variant:**
```python
async def analyze_sales_data_optimized(data: list) -> dict:
    """Analyze sales data - batch processing for speed."""
    # Batch items for LLM efficiency
    batch_size = 10
    results = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        analysis = await llm.analyze_batch(batch)
        results.extend(analysis)
    return {"results": results}
```

**Result:**
- ⚡ 45% faster (1.2s → 0.66s)
- 💰 30% fewer tokens (1500 → 1050)
- 🎯 Same accuracy (0.85 success rate)

---

## Capability Gates

Auto-Dev features are gated by agent maturity to ensure safety:

### INTERN Maturity

✅ **Memento-Skills** (User approval required)
- View failure patterns
- Review skill proposals
- Approve or reject proposals
- Install approved skills

### SUPERVISED Maturity

✅ **Everything in INTERN** +
✅ **AlphaEvolver** (Results queued for review)
- Trigger evolution manually
- View variant comparisons
- Deploy best variants
- Monitor evolution progress

### AUTONOMOUS Maturity

✅ **Everything in SUPERVISED** +
✅ **Background Evolution** (Fully automatic)
- Automatic skill optimization
- Self-healing capabilities
- Continuous improvement
- Zero-touch operation

---

## Sandbox Security

All Auto-Dev code execution happens in isolated Docker containers:

### Security Constraints

```python
ContainerSandbox(
    network_disabled=True,        # No network access
    read_only_filesystem=True,    # Immutable filesystem
    memory_limit="512m",          # Memory cap
    cpu_quota=50000,              # CPU limit
    timeout_seconds=60,           # Execution timeout
    drop_all_capabilities=True,   # Minimal privileges
    seccomp_profile='strict'      # System call filtering
)
```

### What's Allowed

- ✅ Python standard library
- ✅ Local data processing
- ✅ Algorithm optimization
- ✅ String manipulation
- ✅ Mathematical operations

### What's Blocked

- ❌ Network requests (http, urllib, etc.)
- ❌ File system writes
- ❌ Subprocess execution
- ❌ Database connections
- ❌ System calls

---

## Monitoring Auto-Dev

### View Active Evolutions

```bash
curl http://localhost:8000/api/v1/auto-dev/evolutions/active
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "evolution_id": "evo_abc123",
      "skill_name": "data_analysis",
      "generation": 3,
      "status": "running",
      "started_at": "2026-04-10T14:30:00Z",
      "estimated_completion": "2026-04-10T14:35:00Z"
    }
  ]
}
```

### View Skill Proposals

```bash
curl http://localhost:8000/api/v1/auto-dev/proposals?status=pending
```

### View Evolution History

```bash
curl http://localhost:8000/api/v1/auto-dev/evolutions/history?skill_name=data_analysis
```

---

## Best Practices

### 1. Start with Memento-Skills

- Let agents fail and learn
- Review proposals carefully
- Test in development first
- Gradually approve as trust builds

### 2. Use AlphaEvolver for Optimization

- Focus on high-usage skills
- Set clear optimization goals
- Review variants before deploying
- Monitor performance after deployment

### 3. Monitor Sandboxes

- Review sandbox logs regularly
- Check for resource usage
- Validate security constraints
- Update base images periodically

### 4. Gradual Maturity Progression

- **INTERN**: Start with Memento-Skills
- **SUPERVISED**: Add AlphaEvolver
- **AUTONOMOUS**: Enable background evolution

### 5. Set Clear Goals

- Define success metrics upfront
- Establish performance baselines
- Document improvement targets
- Track progress over time

---

## Troubleshooting

### Issue: "Auto-Dev capability not available"

**Solution:**
```bash
# Check agent maturity
curl http://localhost:8000/api/v1/agents/{agent_id}/maturity

# Check workspace configuration
curl http://localhost:8000/api/v1/workspaces/{workspace_id}

# Enable Auto-Dev if needed
curl -X PATCH http://localhost:8000/api/v1/workspaces/{workspace_id} \
  -d '{"configuration": {"auto_dev": {"enabled": true}}}'
```

### Issue: "Sandbox execution failed"

**Solution:**
1. Check Docker is running: `docker ps`
2. Verify sufficient disk space: `df -h`
3. Check sandbox logs: `/var/log/atom/sandbox.log`
4. Review security constraints

### Issue: "No skill proposals generated"

**Solution:**
- Ensure agent has experienced failures
- Check ReflectionEngine is running
- Verify pattern detection thresholds
- Review episode data quality

### Issue: "Evolution not improving performance"

**Solution:**
- Adjust optimization goal (latency vs accuracy)
- Increase number of generations
- Review fitness function weights
- Check if skill is already optimal

---

## Advanced Configuration

### Environment Variables

```bash
# Auto-Dev Settings
AUTO_DEV_ENABLED=true
AUTO_DEV_MEMENTO_ENABLED=true
AUTO_DEV_ALPHA_EVOLVER_ENABLED=true
AUTO_DEV_BACKGROUND_EVOLUTION=false  # Requires AUTONOMOUS

# Sandbox Configuration
SANDBOX_TIMEOUT_SECONDS=60
SANDBOX_MEMORY_LIMIT="512m"
SANDBOX_CPU_QUOTA=50000
SANDBOX_NETWORK_DISABLED=true

# Evolution Parameters
EVOLUTION_GENERATIONS=5
EVOLUTION_POPULATION_SIZE=3
EVOLUTION_MUTATION_RATE=0.3

# Reflection Thresholds
REFLECTION_FAILURE_THRESHOLD=3
REFLECTION_PATTERN_WINDOW=24  # hours
```

### Fitness Weights

Configure how FitnessService evaluates variants:

```python
FITNESS_WEIGHTS = {
    "latency": 0.4,      # Speed matters
    "success_rate": 0.4, # Accuracy matters
    "token_usage": 0.2   # Cost matters
}
```

---

## API Reference

### Capability Check

```bash
GET /api/v1/agents/{agent_id}/auto-dev/capabilities
```

### Trigger Evolution

```bash
POST /api/v1/auto-dev/evolve
{
  "skill_name": "skill_name",
  "optimization_goal": "latency" | "accuracy" | "cost",
  "generations": 5
}
```

### List Proposals

```bash
GET /api/v1/auto-dev/proposals?status=pending&agent_id={agent_id}
```

### Approve Proposal

```bash
POST /api/v1/auto-dev/proposals/{proposal_id}/approve
```

### Reject Proposal

```bash
POST /api/v1/auto-dev/proposals/{proposal_id}/reject
```

### Evolution Status

```bash
GET /api/v1/auto-dev/evolutions/{evolution_id}
```

---

## Next Steps

### Learn More
- **[Agent Graduation Guide](../agents/graduation.md)** - Promote agents to unlock Auto-Dev
- **[Episodic Memory](../intelligence/episodic-memory.md)** - Understanding episodes and learning
- **[Python Packages Security](../security/python-packages.md)** - Container security and sandbox architecture

### Explore
- **[Evolution Strategies](#best-practices)** - Advanced evolution techniques (see Best Practices above)
- **[Performance Tuning](../operations/performance.md)** - Optimization best practices
- **[Package Governance](../security/package-governance.md)** - Security constraints and sandbox configuration

### Get Help
- **Documentation:** [docs.atomagentos.com](https://docs.atomagentos.com)
- **Issues:** [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Community:** [Atom Discord](https://discord.gg/atom)

---

## Quick Reference

### Maturity Requirements

| Capability | INTERN | SUPERVISED | AUTONOMOUS |
|------------|--------|------------|------------|
| View failures | ✅ | ✅ | ✅ |
| Memento-Skills | ⚠️ | ✅ | ✅ |
| AlphaEvolver | ❌ | ⚠️ | ✅ |
| Background evolution | ❌ | ❌ | ✅ |

### Key Differences

| Feature | Memento-Skills | AlphaEvolver |
|---------|---------------|--------------|
| **Purpose** | Create new skills | Improve existing skills |
| **Trigger** | Failures | Manual/auto |
| **Approval** | Required | SUPERVISED: yes, AUTONOMOUS: no |
| **Output** | New skill | Optimized variant |

---

**Ready to evolve your agents?** Enable Auto-Dev in your workspace and start learning from experience today!

*Last Updated: April 10, 2026*
