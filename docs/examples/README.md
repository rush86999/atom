# Code Examples

Example code demonstrating Atom's capabilities and integration patterns.

## 📚 Quick Navigation

### Autonomous Agent Examples
- **[autonomous-celery-integration.tsx](autonomous-celery-integration.tsx)** - Celery task integration
- **[autonomous-usage-complete.ts](autonomous-usage-complete.ts)** - Complete autonomous usage
- **[autonomous-workflow-demo.ts](autonomous-workflow-demo.ts)** - Workflow demonstration
- **[enhanced-autonomy-usage.js](enhanced-autonomy-usage.js)** - Enhanced autonomy
- **[llama-cpp-integration.ts](llama-cpp-integration.ts)** - LLaMA.cpp integration

## 🎯 Example Categories

### Agent Execution
Examples showing how to:
- Create and configure agents
- Execute structured workflows
- Handle autonomous operations
- Integrate with task queues

### Integration Patterns
Examples demonstrating:
- API integration with external services
- Event-driven workflows
- Async task processing
- Real-time streaming

### Language Bindings
Examples in multiple languages:
- **TypeScript**: Type-safe integrations
- **JavaScript**: Node.js integrations
- **Python**: Backend integrations

## 🚀 Quick Start

### TypeScript Example
```typescript
import { AtomAgent } from '@atom/sdk';

const agent = new AtomAgent({
  type: 'sales',
  maturity: 'AUTONOMOUS'
});

const result = await agent.execute({
  task: 'analyze_sales_data',
  parameters: { timeframe: 'last_30_days' }
});
```

### Python Example
```python
from atom_sdk import AtomAgent

agent = AtomAgent(
    type='marketing',
    maturity='SUPERVISED'
)

result = agent.execute(
    task='create_campaign',
    parameters={'platform': 'slack'}
)
```

## 📖 Related Documentation

- **[API Documentation](../API/README.md)** - Complete API reference
- **[Development](../development/README.md)** - Development setup
- **[Components](../components/README.md)** - Component documentation

## 💡 Contributing Examples

To add new examples:

1. **Choose the right language**: TypeScript, JavaScript, or Python
2. **Follow naming convention**: `descriptive-name.ext`
3. **Add comments**: Explain key concepts
4. **Test thoroughly**: Ensure examples work
5. **Update this README**: Add description

Example file structure:
```typescript
/**
 * Example: Brief description
 *
 * This example demonstrates:
 * - Feature 1
 * - Feature 2
 *
 * Prerequisites:
 * - Atom API key
 * - Required integrations
 */

import { Atom } from '@atom/sdk';

// Your code here
```

---

*Last Updated: April 12, 2026*
