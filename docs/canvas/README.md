# Canvas System

Visual presentations and AI accessibility for agent interactions.

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

## 🔧 Quick Start

```typescript
// Canvas State API
window.atom.canvas.getState('canvas-id')
window.atom.canvas.getAllStates()
window.atom.canvas.subscribe((state) => console.log(state))
```

## 📖 Related Documentation

- **[Episodic Memory](../intelligence/episodic-memory.md)** - Canvas in episodes
- **[Agent System](../agents/README.md)** - Agent canvas governance
- **[Intelligence Systems](../intelligence/README.md)** - AI capabilities

---

*Last Updated: April 12, 2026*
