# ATOM Memory Integration Guide

## Overview

This guide explains how ATOM's chat interface is connected with the memory system, implementing short-term and long-term memory capabilities similar to a human brain. The memory system uses LanceDB for vector storage and provides context-aware responses based on conversation history.

## Architecture

### Memory System Components

```
ATOM Memory System
├── Short-Term Memory (Working Memory)
│   ├── Session-based storage
│   ├── Recent conversation context
│   ├── Automatic decay and cleanup
│   └── In-memory storage for performance
├── Long-Term Memory (Persistent Storage)
│   ├── LanceDB vector database
│   ├── Semantic search capabilities
│   ├── Importance-based retention
│   └── Cross-session persistence
├── User Pattern Recognition
│   ├── Behavior pattern detection
│   ├── Workflow usage patterns
│   ├── Communication preferences
│   └── Confidence-based pattern scoring
└── Context Retrieval Engine
    ├── Semantic similarity search
    ├── Relevance scoring
    ├── Context summarization
    └── Memory access optimization
```

### Memory Types

1. **Short-Term Memory**
   - Stores recent conversations (last 50 messages per session)
   - Session-based with automatic timeout (60 minutes)
   - Fast access for immediate context
   - Automatic cleanup on session end

2. **Long-Term Memory**
   - Persistent storage in LanceDB
   - Vector embeddings for semantic search
   - Importance-based retention (threshold: 0.7)
   - Cross-session availability

3. **User Patterns**
   - Workflow usage patterns
   - Active hours detection
   - Communication preferences
   - Automated behavior learning

## Integration Points

### Frontend Integration

#### React Hook: `useChatMemory`

```typescript
import { useChatMemory } from '../hooks/useChatMemory';

const {
  // State
  memories,
  memoryContext,
  memoryStats,
  isLoading,
  error,
  
  // Actions
  storeMemory,
  getMemoryContext,
  clearSessionMemory,
  refreshMemoryStats,
  
  // Utilities
  hasRelevantContext,
  contextRelevanceScore
} = useChatMemory({
  userId: 'user123',
  sessionId: 'session456',
  enableMemory: true,
  autoStoreMessages: true,
  contextWindow: 10
});
```

#### Enhanced Chat Interface

```typescript
import { EnhancedChatInterface } from '../components/chat/EnhancedChatInterface';

<EnhancedChatInterface
  userId="user123"
  sessionId="session456"
  enableMemory={true}
  showMemoryControls={true}
  onWorkflowTrigger={handleWorkflow}
  onVoiceCommand={handleVoice}
/>
```

### Backend Integration

#### Python Service: `ChatMemoryService`

```python
from chat_memory_service import ChatMemoryService, ConversationMemory

# Initialize service
memory_service = ChatMemoryService()

# Store conversation
memory = ConversationMemory(
    user_id="user123",
    session_id="session456",
    role="user",
    content="Schedule a meeting for tomorrow",
    metadata={
        "workflow_id": "wf_123",
        "intent": "schedule_meeting",
        "importance": 0.8
    }
)

result = await memory_service.store_conversation(memory)
```

#### API Endpoints

- `POST /api/chat/memory/store` - Store conversation memory
- `POST /api/chat/memory/context` - Get memory context
- `GET /api/chat/memory/history` - Get conversation history
- `DELETE /api/chat/memory/session/{session_id}` - Clear session memory
- `GET /api/chat/memory/stats` - Get memory statistics
- `GET /api/chat/memory/health` - Health check

## Implementation Details

### Memory Storage Flow

1. **Message Reception**
   - User sends message through chat interface
   - Message is automatically stored in short-term memory
   - Importance score is calculated (0-1 scale)

2. **Context Retrieval**
   - Semantic search in long-term memory using LanceDB
   - Pattern matching for user behavior
   - Relevance scoring and ranking

3. **Response Generation**
   - Context-aware response generation
   - Memory-enhanced suggestions
   - Pattern-based personalization

4. **Memory Consolidation**
   - Important conversations moved to long-term storage
   - User pattern updates
   - Access count tracking

### Importance Scoring

Memory importance is calculated based on:

- **Workflow Relevance** (+0.3): Messages related to workflows
- **Question/Command** (+0.2): User questions and commands
- **Action Responses** (+0.2): Assistant responses with actions
- **Content Length** (+0.1): Longer, more detailed content

### Pattern Detection

The system automatically detects:

- **Workflow Patterns**: Frequently used workflows
- **Time Patterns**: Active hours and usage patterns
- **Communication Styles**: Preferred interaction methods
- **Task Preferences**: Common task types and platforms

## Configuration

### Memory System Settings

```python
# Default configuration
short_term_memory_size = 50
long_term_threshold = 0.7
similarity_threshold = 0.6
session_timeout_minutes = 60
pattern_detection_window = 7 * 24 * 60 * 60  # 1 week
```

### LanceDB Integration

The system uses the existing LanceDB infrastructure:

- **Table**: `conversations`
- **Embedding Dimension**: 1536 (configurable)
- **Search**: Vector similarity with user filtering
- **Storage**: Persistent with automatic indexing

## Usage Examples

### Basic Memory Integration

```typescript
// Store a user message
await storeMemory({
  userId: 'user123',
  sessionId: 'session456',
  role: 'user',
  content: 'Can you help me schedule a team meeting?',
  metadata: {
    messageType: 'text',
    intent: 'schedule_meeting',
    importance: 0.8
  }
});

// Get memory context for response
const context = await getMemoryContext('Can you help me schedule a team meeting?');

// Enhanced response using memory context
if (context.relevanceScore > 0.5) {
  response = `I recall we discussed meetings before. ${response}`;
}
```

### Advanced Memory Features

```typescript
// Check memory statistics
const stats = memoryStats;
console.log(`Short-term memories: ${stats.shortTermMemoryCount}`);
console.log(`User patterns: ${stats.userPatternCount}`);

// Clear session memory (e.g., on logout)
await clearSessionMemory();

// Manual memory management
await storeMemory({
  userId: 'user123',
  sessionId: 'session456',
  role: 'assistant',
  content: 'I created the workflow as requested',
  metadata: {
    workflowId: 'wf_789',
    importance: 0.9
  }
});
```

## Error Handling

### Common Issues

1. **LanceDB Unavailable**
   - System falls back to short-term memory only
   - User patterns still work
   - Graceful degradation

2. **Memory Storage Failures**
   - Individual memory storage failures don't break the system
   - Errors are logged but don't interrupt chat flow
   - Automatic retry mechanisms

3. **Session Timeouts**
   - Automatic cleanup of expired sessions
   - Memory statistics reflect active sessions only
   - No impact on long-term memory

### Monitoring

- Memory health checks via `/api/chat/memory/health`
- Statistics tracking via `/api/chat/memory/stats`
- Error logging with detailed context
- Performance metrics for memory operations

## Best Practices

### Memory Optimization

1. **Importance Scoring**
   - Set appropriate importance thresholds
   - Balance between memory usage and relevance
   - Monitor pattern detection accuracy

2. **Session Management**
   - Use meaningful session IDs
   - Implement proper session cleanup
   - Consider user privacy requirements

3. **Performance**
   - Limit context window size appropriately
   - Use batch operations for multiple memories
   - Monitor LanceDB performance

### Privacy and Security

- User data isolation in memory storage
- Session-based memory separation
- Configurable data retention policies
- Compliance with privacy regulations

## Troubleshooting

### Common Problems

1. **Memory Context Not Available**
   - Check LanceDB connectivity
   - Verify user ID and session ID
   - Check importance threshold settings

2. **Pattern Detection Not Working**
   - Ensure sufficient conversation history
   - Verify pattern detection window
   - Check confidence thresholds

3. **Performance Issues**
   - Monitor memory statistics
   - Check LanceDB indexing
   - Review context window size

### Debugging Tools

- Memory health endpoint
- Detailed logging
- Statistics monitoring
- Context relevance scoring

## Future Enhancements

### Planned Features

1. **Advanced Pattern Recognition**
   - Machine learning-based pattern detection
   - Cross-user pattern analysis
   - Predictive memory retrieval

2. **Memory Compression**
   - Automatic summarization of similar memories
   - Hierarchical memory organization
   - Efficient storage strategies

3. **Multi-modal Memory**
   - Integration with document memory
   - Voice conversation memory
   - Cross-platform memory unification

### Integration Opportunities

- Integration with workflow automation memory
- Connection with document processing pipeline
- Enhanced user modeling capabilities
- Advanced personalization features

## Support

For technical support or questions about memory integration:

- Check system logs for memory-related errors
- Verify LanceDB connectivity and configuration
- Review memory statistics for usage patterns
- Contact the development team for complex issues

---

*Last Updated: 2025*
*Maintained by ATOM Development Team*