# Arbor Framework: Hypothesis Tree Refinement (HTR)

**Phase**: 2026-06-19 Implementation
**Status**: ✅ Complete
**Integration**: Atom Platform backend/core

---

## Overview

Arbor is an **optimization framework for LLM code generation** using tree-based refinement. It implements **Hypothesis Tree Refinement (HTR)** with cumulative learning across sessions, enabling intelligent exploration of solution spaces with built-in validation and pruning.

## Key Concepts

### Hypothesis Tree
- **Root Node**: Initial problem state
- **Branching**: Multiple solution hypotheses explored in parallel
- **Pruning**: Failed paths eliminated early (lint errors, test failures, performance regression)
- **Winning Path**: First successful solution found

### Search Strategies
| Algorithm | Best For | Characteristics |
|-----------|---------|-----------------|
| **Best-First Search** | Quick solutions | Prioritizes high-promise nodes |
| **MCTS (Monte Carlo Tree Search)** | Complex spaces | Balances exploration/exploitation |
| **Beam Search** | Resource-constrained | Maintains top-k candidates |

### Cumulative Learning
- **Negative Constraints**: Patterns that consistently fail are avoided
- **Session Tags**: Learning insights tagged for cross-session reuse
- **Path Tracking**: Successful patterns reinforced across sessions

## Architecture

### Core Data Structures

```
┌─────────────────────────────────────────────────────────────────┐
│                    HypothesisTree                                │
├─────────────────────────────────────────────────────────────────┤
│  • root_id: Root node ID                                       │
│  • nodes: Dict[str, HypothesisNode]                            │
│  • winning_path: List[str] (successful path)                    │
│  • max_nodes: int (budget limit)                                │
│  • max_tokens: int (budget limit)                               │
│  • max_cost_usd: float (budget limit)                           │
│  • negative_constraints: List[str] (learned failures)            │
│  • learning_insights: List[str] (cross-session learning)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │HypothesisNode│ │HypothesisNode│ │HypothesisNode│
        │ (SUCCESS)    │ │ (PRUNED)     │ │ (PENDING)     │
        └──────────────┘ └──────────────┘ └──────────────┘
```

### Node Lifecycle

```
PENDING → EXPANDING → SUCCESS (winning path found)
                    → FAILED (validation failed)
                    → PRUNED (budget/exploration limit)
```

### Pruning Reasons

| Reason | Description | Example |
|--------|-------------|---------|
| `LINT_FAILED` | Code linting errors | Syntax errors, style violations |
| `TEST_FAILED` | Unit test failures | Regression bugs |
| `LATENCY_REGRESSION` | Performance degradation | Slower than baseline |
| `RESOURCE_EXCEEDED` | Memory/CPU exceeded | OOM risk detected |
| `NEGATIVE_CONSTRAINT` | Known failure pattern | Matches constraint |
| `BUDGET_EXCEEDED` | Cost/token limit | Max nodes reached |
| `DUPLICATE_HYPOTHESIS` | Already explored | Same code diff |
| `LOW_PROMISE` | Poor estimated quality | Low promise score |

## Extended HTR: Multi-Domain Optimization

### Task Types

```python
class TaskType(Enum):
    CODING = "coding"        # Code generation and refactoring
    WORKFLOW = "workflow"    # Workflow orchestration
    ROUTING = "routing"      # LLM/model routing optimization
```

### Domain-Specific Nodes

#### 1. CodeHypothesisNode
```python
@dataclass
class CodeHypothesisNode(OptimizationNode):
    # Code-specific metrics
    code_diff: str = ""  # Unified diff format
    language: str = ""  # python, typescript, rust
    cyclomatic_complexity: int = 0
    code_coverage: float = 0.0
    security_vulnerabilities: int = 0

    def calculate_promise_score(self) -> float:
        # Weigh test coverage, security, complexity
        ...
```

**Use Case**: Auto-refactoring, code generation, optimization

**Integration with Auto-Dev**: CodeHypothesisNode integrates with Auto-Dev's Memento-Skills and AlphaEvolver:

```python
# Arbor validates AlphaEvolver variants
from auto_dev.alpha_evolver import AlphaEvolverEngine

evolver = AlphaEvolverEngine()
variants = evolver.create_variants(base_skill="data_analysis")

# Arbor tests each variant as a hypothesis
for variant_code in variants:
    node = CodeHypothesisNode(
        code_diff=variant_code,
        language="python",
        cyclomatic_complexity=calculate_complexity(variant_code),
        code_coverage=run_tests(variant_code)
    )
    # Arbor prunes failing variants (lint errors, test failures)
    # Winning path = best performing variant
```

**See Also**: [Auto-Dev User Guide](docs/guides/AUTO_DEV_USER_GUIDE.md) - Skill evolution with Arbor integration

#### 2. WorkflowHypothesisNode
```python
@dataclass
class WorkflowHypothesisNode(OptimizationNode):
    # Workflow-specific configuration
    steps_configuration: Dict[str, Any]
    parallel_steps: List[str]
    sequential_steps: List[str]

    # Performance metrics
    estimated_latency_ms: float = 0.0
    parallelizable_ratio: float = 0.0
    cost_optimization_potential: float = 0.0
```

**Use Case**: Conductor Agent workflows, multi-agent orchestration

#### 3. RoutingHypothesisNode
```python
@dataclass
class RoutingHypothesisNode(OptimizationNode):
    # Routing-specific configuration
    model_sequence: List[str]
    caching_enabled: bool = False
    streaming_enabled: bool = False

    # Quality vs cost metrics
    accuracy_score: float = 0.0
    cost_per_1k_tokens: float = 0.0
    p95_latency_ms: float = 0.0
```

**Use Case**: Cognitive tier system optimization, LLM routing

## Pricing Tiers

| Tier | Max Nodes | Max Tokens | Max Cost | Use Case |
|------|-----------|------------|----------|----------|
| **Free** | 3 | 5,000 | $0.25 | Trial/experimentation |
| **Solo** | 8 | 10,000 | $0.50 | Individual developers |
| **Enterprise** | 20 | 50,000 | $2.00 | Production teams |

## Usage Examples

### Basic Tree Search

```python
from core.hypothesis_tree import HypothesisTree, HypothesisNode, TreeSearchParams

# Create tree with tier budget
tree = HypothesisTree(
    task_description="Fix user authentication bug",
    tier="solo"  # 8 nodes, 10k tokens, $0.50
)

# Configure search parameters
params = TreeSearchParams(
    algorithm="best_first",
    max_depth=5,
    validate_lint=True,
    validate_tests=True,
    prune_on_lint_error=True,
    prune_on_test_failure=True
)

# Search for solution
winning_path = tree.search(params)
print(f"Solution found in {len(winning_path)} iterations")
```

### Cumulative Learning

```python
# Tree learns from previous sessions
tree.add_negative_constraint("avoid async/await in Python")
tree.learning_insights = [
    "prefer context managers for resource cleanup",
    "type hints improve validation success rate"
]

# Future searches avoid these patterns
if tree.violates_constraint(hypothesis="async def authenticate"):
    # Skip this hypothesis
    pass
```

### Multi-Domain Optimization

```python
from core.hypothesis_tree import OptimizationTree, TaskType

# Create workflow optimization tree
workflow_tree = OptimizationTree(
    task_type=TaskType.WORKFLOW,
    task_description="Optimize Conductor Agent workflow"
)

# Create workflow-specific node
node = workflow_tree.create_node(
    node_type=TaskType.WORKFLOW,
    parallel_steps=["agent_1", "agent_2", "agent_3"],
    estimated_latency_ms=500,
    cost_optimization_potential=0.4
)

# Calculate domain-specific promise score
promise = node.calculate_promise_score()
```

## MCTS Node Selection

```python
# UCB1 formula for exploration/exploitation balance
node.get_ucb1_score(exploration_constant=1.41)

# UCB1 = average_reward + c * sqrt(ln(parent_visits) / visits)
#
# • Exploitation: High average reward → revisit
# • Exploration: Low visit count → explore
```

## Budget Enforcement

```python
# Automatic budget checking
if not tree.add_node(node):
    # Budget exceeded
    reason = (
        f"Max nodes ({tree.max_nodes}) reached" or
        f"Max tokens ({tree.max_tokens}) exceeded" or
        f"Max cost (${tree.max_cost_usd}) exceeded"
    )
```

## Integration with Phase 1-5 Features

### Phase 1: POMDP Memory Framework

- **Hypothesis as Actions**: Each hypothesis is an action in the POMDP action space
- **Observations**: Validation results (lint, tests, performance) form observations
- **Rewards**: Successful paths feed into memory quality assessment

**See Also**: [Episodic Memory](docs/intelligence/episodic-memory.md) - Complete POMDP integration guide
- **Hypothesis as Actions**: Each hypothesis is an action in the POMDP action space
- **Observations**: Validation results (lint, tests, performance) form observations
- **Rewards**: Successful paths feed into memory quality assessment

### Phase 2: GraphRAG Enhancement
- **Constraint Discovery**: GraphRAG discovers patterns in failed hypotheses
- **Multi-Hop Analysis**: Trace relationships between failed code patterns

### Phase 3: Learning-Based LLM Routing
- **Model Selection**: RouteLLM selects optimal LLM for hypothesis generation
- **Cost Optimization**: Tree search respects LLM routing cost tiers

**See Also**: [Cognitive Tier System](docs/architecture/COGNITIVE_TIER_SYSTEM.md) - Routing optimization with RoutingHypothesisNode

### Phase 5: Enhanced Orchestration
- **Conductor Agent**: Uses workflow hypothesis nodes for optimization
- **WorkflowHypothesisNode**: Domain-specific node for workflow refinement

**See Also**: [Atom Enhancement Plan](ATOM_ENHANCEMENT_PLAN.md) - Phase 5 orchestration patterns with Arbor integration

## API Endpoints

### Create Tree
```bash
POST /api/hypothesis-tree/create
{
    "task_description": "Optimize database query performance",
    "tier": "solo",
    "algorithm": "best_first"
}
```

### Add Hypothesis
```bash
POST /api/hypothesis-tree/{tree_id}/add-node
{
    "hypothesis": "CREATE INDEX ON users(email)",
    "description": "Add email index to users table"
}
```

### Get Statistics
```bash
GET /api/hypothesis-tree/{tree_id}/statistics
{
    "total_nodes": 8,
    "successful_nodes": 1,
    "pruned_nodes": 5,
    "total_tokens_used": 8500,
    "total_cost_usd": 0.42,
    "winning_path": ["node_1", "node_3", "node_7"]
}
```

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Tree expansion latency | <100ms | ~80ms |
| Node creation overhead | <50ms | ~30ms |
| Pruning decision time | <10ms | ~5ms |
| Budget check overhead | <5ms | ~2ms |

## Testing

```bash
# Run Arbor framework tests
cd backend
PYTHONPATH=. pytest tests/test_hypothesis_tree.py -v

# Expected: All tests passing
# - test_node_creation
# - test_tree_addition
# - test_pruning
# - test_budget_enforcement
# - test_ucb1_calculation
# - test_negative_constraints
# - test_domain_nodes
```

## Documentation References

- **Implementation**: `backend/core/hypothesis_tree.py`
- **Agent Governance**: [docs/agents/governance.md](docs/agents/governance.md) - Enhanced Orchestration with Arbor optimization learning
- **Cognitive Tier System**: [docs/architecture/COGNITIVE_TIER_SYSTEM.md](docs/architecture/COGNITIVE_TIER_SYSTEM.md) - Routing optimization with RoutingHypothesisNode
- **Auto-Dev Guide**: [docs/guides/AUTO_DEV_USER_GUIDE.md](docs/guides/AUTO_DEV_USER_GUIDE.md) - Code generation and skill evolution with Arbor
- **Episodic Memory**: [docs/intelligence/episodic-memory.md](docs/intelligence/episodic-memory.md) - POMDP action space integration
- **Canvas Learning**: [docs/canvas/agent-learning.md](docs/canvas/agent-learning.md) - Optimization node learning from feedback
- **Enhancement Plan**: [ATOM_ENHANCEMENT_PLAN.md](ATOM_ENHANCEMENT_PLAN.md) - Phase 5 orchestration with Arbor

---

**Last Updated**: June 18, 2026
**Status**: Production Ready ✅
