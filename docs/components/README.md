# Components Documentation

Reusable components and their documentation.

## 📚 Quick Navigation

### Core Components
- **[Agents](agents.md)** - Agent system components
- **[Voice AI](voice-ai.md)** - Voice interaction components

## 🧩 Component Types

### Agent Components
- **Specialty Agents**: Sales, Marketing, Engineering, Support
- **Orchestrators**: Queen Agent, Fleet Admiral
- **Governance**: Maturity levels, permissions, training
- **Learning**: Episodic memory, self-evolution, graduation

### Voice AI Components
- **Speech Recognition**: Voice-to-text processing
- **Natural Language Understanding**: Intent classification
- **Voice Synthesis**: Text-to-speech responses
- **Conversation Management**: Context tracking

## 🎯 Usage

### Using Agent Components
```python
from core.queen_agent import QueenAgent
from core.fleet_admiral import FleetAdmiral

# Structured workflow (Queen Agent)
queen = QueenAgent()
queen.execute_blueprint(blueprint)

# Unstructured task (Fleet Admiral)
fleet = FleetAdmiral()
fleet.execute_task(task_description)
```

### Using Voice AI Components
```typescript
import { VoiceAI } from '@atom/voice-ai';

const voiceAI = new VoiceAI();
await voiceAI.startListening();
```

## 📖 Related Documentation

- **[Agent System](../agents/README.md)** - Complete agent documentation
- **[Intelligence System](../intelligence/README.md)** - AI capabilities
- **[Canvas System](../canvas/README.md)** - Visual components

---

*Last Updated: April 12, 2026*
