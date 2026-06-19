# Canvas System

Visual presentations and AI accessibility for agent interactions with 2026 Enhancement Plan integration.

## 📚 Quick Navigation

**Start Here**: [Canvas Reference](reference.md) - Complete canvas reference guide

### Core Canvas Features
- **[Canvas Reference](reference.md)** - Complete canvas operations and types
- **[AI Accessibility](ai-accessibility.md)** - AI-readable canvas state
- **[LLM Summaries](llm-summaries.md)** - Enhanced memory integration

### Integration
- **[Agent Learning](agent-learning.md)** - Canvas-based learning
- **[Feedback & Memory](feedback-memory.md)** - Feedback integration with episodes
- **[Recording](recording.md)** - Canvas recording and replay

## 🎨 Canvas Types

1. **Markdown** - Rich text content
2. **Charts** - Line, bar, pie charts
3. **Forms** - Interactive forms with governance
4. **Sheets** - Tabular data
5. **Files** - File listings
6. **Status** - Progress indicators
7. **HTML** - Custom content

## ✨ Key Features

### AI Accessibility
- **Hidden Accessibility Trees**: Canvas state exposed as JSON
- **Canvas State API**: `window.atom.canvas.getState()`
- **Progressive Detail**: Summary → Standard → Full

### LLM Summaries
- **Semantic Summaries**: 50-100 word LLM-generated summaries
- **Enhanced Retrieval**: Better episode search and agent learning
- **Canvas-Aware Prompts**: Specialized prompts per canvas type

### Episode Integration
- **Automatic Tracking**: Canvases linked to episodes
- **Feedback Capture**: User feedback improves retrieval
- **Memory Enhancement**: Canvas context in episode retrieval

## 🚀 2026 Enhancement Plan Integration

Canvas is integrated with all 5 phases of the Atom Enhancement Plan:

### Phase 1: POMDP Memory Framework ✅
- **Canvas State as Observations**: Canvas interactions form part of the observation space in POMDP memory
- **Action Space Integration**: Canvas actions (present, submit, close) are tracked as agent actions
- **Reward Function**: User feedback on canvases feeds into memory quality assessment
- **Memory Consolidation**: Canvas summaries included in offline consolidation during "sleep" cycles

**Example**:
```python
# Canvas interactions enhance POMDP memory
from core.memory.pomdp_memory_framework import POMDPMemoryFramework

pomdp = POMDPMemoryFramework()
pomdp.define_observation_space(
    states=["canvas_presented", "user_closed", "user_submitted"],
    actions=["present_chart", "present_form", "present_sheet"]
)

# Canvas feedback updates memory quality
reward = pomdp.calculate_reward(
    canvas_type="charts",
    user_engagement_seconds=45,
    feedback_type="thumbs_up"
)
```

### Phase 2: Enhanced GraphRAG ✅
- **Canvas Content Extraction**: LLM extracts entities and relationships from canvas text
- **Multi-Hop Query Enhancement**: GraphRAG uses canvas context for multi-hop expansion
- **Dynamic Graph Updates**: Canvas presentations trigger incremental graph updates
- **Community Detection**: Canvas-based entity clustering via Leiden algorithm

**Example**:
```python
# Canvas content feeds GraphRAG
from core.graphrag.multi_hop_expansion import MultiHopExpander

expander = MultiHopExpander()
# Extract entities from canvas presentation
entities = expander.extract_entities_from_canvas(
    canvas_id="canvas_123",
    text_content="Sales data for Q1 shows upward trend in APAC region"
)
# Multi-hop expansion from canvas entities
results = expander.expand_query(
    query="Show all APAC sales presentations",
    max_hops=3,
    expansion_mode="cue_driven"
)
```

### Phase 3: Learning-Based LLM Routing ✅
- **Canvas-Aware Routing**: Canvas type and complexity inform LLM tier selection
- **Preference Collection**: User feedback on canvas summaries trains RouteLLM model
- **Cache Optimization**: Canvas state hashing enables predictive cache warming
- **Cost Reduction**: 15% additional savings on canvas-related LLM calls

**Example**:
```python
# Canvas complexity influences LLM routing
from core.llm.routing.routellm_trainer import RouteLLMTrainer

trainer = RouteLLMTrainer()
# Collect preference data from canvas interactions
preference = {
    "canvas_type": "charts",
    "complexity": "high",
    "user_satisfaction": 5.0,
    "model_used": "claude-3-5-sonnet"
}
trainer.record_preference(preference)
```

### Phase 4: Zero-Trust Federation Identity ✅
- **Canvas Presentation Signatures**: Canvas states signed with agent DID
- **Verifiable Credentials**: Canvas presentations include VC proofs of authorship
- **Cross-Instance Canvas Sharing**: Federation with DID-based identity verification
- **Credential Rotation**: Automatic 90-day credential rotation for canvas presentations

**Example**:
```python
# Canvas presentations with DID signatures
from core.identity.did_manager import DIDManager
from core.identity.verifiable_credentials import VCManager

did_manager = DIDManager()
vc_manager = VCManager()

# Sign canvas presentation with agent DID
canvas_presentation = {
    "canvas_id": "canvas_123",
    "agent_did": "did:atom:agent_abc",
    "signature": did_manager.sign_canvas_state(canvas_state),
    "verifiable_credential": vc_manager.create_canvas_presentation_vc(
        subject_did="did:atom:agent_abc",
        canvas_type="charts",
        timestamp=datetime.utcnow()
    )
}
```

### Phase 5: Enhanced Orchestration Patterns ✅
- **Conductor Agent Integration**: Canvas state machine coordinates multi-agent workflows
- **Workflow State Machine**: Validated canvas transitions with automatic rollback
- **Event Bus Integration**: Canvas events trigger pub/sub workflows
- **Template Composition**: 8 workflow composition primitives for canvas presentations

**Example**:
```python
# Canvas workflow with Conductor Agent
from core.orchestration.conductor_agent import ConductorAgent

conductor = ConductorAgent()

# Execute canvas workflow with state machine
workflow = conductor.execute_workflow(
    strategy="SEQUENTIAL",  # SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE
    steps=[
        {"agent": "analyst", "action": "present_chart", "canvas_type": "charts"},
        {"agent": "reviewer", "action": "approve", "condition": "user_feedback > 0.7"},
        {"agent": "archiver", "action": "store_episode", "canvas_ids": ["canvas_123"]}
    ],
    state_machine={
        "initial": "presenting",
        "states": ["presenting", "reviewing", "approved", "rejected"],
        "transitions": {
            "presenting": ["reviewing"],
            "reviewing": ["approved", "rejected"],
            "approved": ["completed"],
            "rejected": ["rollback"]
        }
    }
)
```

## 🔧 Quick Start

```typescript
// Canvas State API
window.atom.canvas.getState('canvas-id')
window.atom.canvas.getAllStates()
window.atom.canvas.subscribe((state) => console.log(state))
```

## 📖 Related Documentation

### 2026 Enhancements
- **[Enhancement Plan](../ATOM_ENHANCEMENT_PLAN.md)** - Complete 5-phase enhancement overview
- **[Validation Metrics](../../backend/docs/VALIDATION_METRICS.md)** - Performance validation
- **[POMDP Memory](../intelligence/episodic-memory.md#phase-1-enhancements)** - Memory framework
- **[GraphRAG Enhancement](../intelligence/graphrag.md#phase-2-enhancements)** - Multi-hop expansion
- **[LLM Routing](../architecture/COGNITIVE_TIER_SYSTEM.md#phase-3-enhancements)** - Learning-based routing
- **[Federation Identity](../guides/FEDERATION_INSTANCE_IDENTITY.md)** - Zero-trust DID/VC
- **[Enhanced Orchestration](../agents/governance.md#enhanced-governance-2026)** - Conductor agent

### Core Documentation
- **[Episodic Memory](../intelligence/episodic-memory.md)** - Canvas in episodes
- **[Agent System](../agents/README.md)** - Agent canvas governance
- **[Intelligence Systems](../intelligence/README.md)** - AI capabilities

---

*Last Updated: June 18, 2026*
