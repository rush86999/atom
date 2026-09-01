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

---

## 🎨 Canvas Types

1. **Markdown** - Rich text content
2. **Charts** - Line, bar, pie charts
3. **Forms** - Interactive forms with governance
4. **Sheets** - Tabular data
5. **Files** - File listings
6. **Status** - Progress indicators
7. **HTML** - Custom content

---

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

### Full CRUD Support (NEW — Aug 2026)
- **Create**: `present_chart`, `present_markdown`, `present_form`, `present_sheet`, etc.
- **Read**: `read_canvas` — fetch current state by ID (any canvas type)
- **Update**: `update_canvas_content` — modify content, title (generalizes docs-only pattern to all types)
- **Delete**: `delete_canvas` — close specific canvas by ID (audit-preserved, IDOR-guarded)
- **List**: `list_canvases` — enumerate user's canvases with type filter, include deleted
- **Session Isolation**: `session_id` parameter on all operations for parallel workflows
- **Tool Registry**: All CRUD ops registered with metadata (complexity, maturity, cacheable)

### Integration Support (NEW — Aug 2026)
- **Action Registry Integration**: All canvas tools auto-exposed via `core/action_registry.py` → agent MCP loop + frontend RPC (`api/rpc_routes.py`)
- **Governance Enforced**: Maturity-gated (STUDENT+/INTERN+) via `AgentGovernanceService` at dispatch
- **Sandbox Gate**: Every tool call flows through `integrations/mcp_service.call_tool` → `core/sandbox_gate.evaluate_tool_call` (P9 default-on)
- **Audit Trail**: Every CRUD op writes `CanvasAudit` row (append-only, recoverable)
- **WebSocket Broadcast**: Real-time `canvas:update` events for update/delete/list
- **IDOR Protection**: Owner verification (`Canvas.created_by`) on read/update/delete

### WS Frame Contract & Audit-Trail Reads (NEW — Aug 31, 2026)
- **Frame contract**: every `canvas:update` frame declares its semantics via `action`. Content actions: `update` / `present` (payload carries canvas content). Event actions — `email_send`, `mini_app_state` — carry STATUS payloads and must NEVER be applied as canvas content (a failed-send status once replaced the drafted email in the open canvas). Enforced in `frontend-nextjs/lib/canvasFrame.ts` (`isCanvasContentFrame`), consumed by `pages/canvas/[id].tsx` + `components/chat/canvas-host.tsx`. **Adding a new event-style broadcast → add its action to `CANVAS_EVENT_ACTIONS` in canvasFrame.ts.**
- **Reads are audit-authoritative**: `tools/canvas_crud_tool.read_canvas` scans back to the latest CONTENT-bearing `CanvasAudit` row (event rows like `email_send_attempt` carry no body), falling back to the legacy `canvases.content` column only when no recent audit row has a body. The `canvases` row itself is NOT the live content — don't "fix" reads to prefer it.

---

## 🔧 Quick Start

```typescript
// Canvas State API
window.atom.canvas.getState('canvas-id')
window.atom.canvas.getAllStates()
window.atom.canvas.subscribe((state) => console.log(state))
```

```python
# Full CRUD via agent tools (registered in action registry)
from tools.registry import get_tool_registry

registry = get_tool_registry()

# Create
await present_chart(user_id="user-1", chart_type="line_chart", data=[...], session_id="session-a")

# Read
await read_canvas(user_id="user-1", canvas_id="canvas-abc123")

# Update
await update_canvas_content(user_id="user-1", canvas_id="canvas-abc123", content={"data": [...]}, canvas_type="charts")

# Delete
await delete_canvas(user_id="user-1", canvas_id="canvas-abc123")

# List
await list_canvases(user_id="user-1", canvas_type="charts")
```

---

## 🚀 2026 Enhancement Plan Integration

Canvas is integrated with all 5 phases of the Atom Enhancement Plan:

### Phase 1: POMDP Memory Framework ✅
- **Canvas State as Observations**: Canvas interactions form part of the observation space in POMDP memory
- **Action Space Integration**: Canvas actions (present, submit, close, **read, update, delete**) are tracked as agent actions
- **Reward Function**: User feedback on canvases feeds into memory quality assessment
- **Memory Consolidation**: Canvas summaries included in offline consolidation during "sleep" cycles

### Phase 2: Enhanced GraphRAG ✅
- **Canvas Content Extraction**: LLM extracts entities and relationships from canvas text
- **Multi-Hop Query Enhancement**: GraphRAG uses canvas context for multi-hop expansion
- **Dynamic Graph Updates**: Canvas presentations trigger incremental graph updates
- **Community Detection**: Canvas-based entity clustering via Leiden algorithm

### Phase 3: Learning-Based LLM Routing ✅
- **Canvas-Aware Routing**: Canvas type and complexity inform LLM tier selection
- **Preference Collection**: User feedback on canvas summaries trains RouteLLM model
- **Cache Optimization**: Canvas state hashing enables predictive cache warming
- **Cost Reduction**: 15% additional savings on canvas-related LLM calls

### Phase 4: Zero-Trust Federation Identity ✅
- **Canvas Presentation Signatures**: Canvas states signed with agent DID
- **Verifiable Credentials**: Canvas presentations include VC proofs of authorship
- **Cross-Instance Canvas Sharing**: Federation with DID-based identity verification
- **Credential Rotation**: Automatic 90-day credential rotation for canvas presentations

### Phase 5: Enhanced Orchestration Patterns ✅
- **Conductor Agent Integration**: Canvas state machine coordinates multi-agent workflows
- **Workflow State Machine**: Validated canvas transitions with automatic rollback
- **Event Bus Integration**: Canvas events trigger pub/sub workflows
- **Template Composition**: 8 workflow composition primitives for canvas presentations

---

## 📖 Related Documentation

### 2026 Enhancements
- **Enhancement Plan** - Complete 5-phase enhancement overview
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
- **[Execution Sandbox](../guides/EXECUTION_SANDBOX.md)** - Blast-radius defense for canvas tools
- **[Agent Maturity & Governance](../guides/AGENT_MATURITY_GOVERNANCE.md)** - Tier-based access

---

*Last Updated: August 2026*