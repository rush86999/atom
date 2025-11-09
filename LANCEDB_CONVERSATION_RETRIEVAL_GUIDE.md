# LanceDB Conversation Retrieval Guide

This guide explains how to retrieve conversations from LanceDB in the Atom Chat Interface system.

## Overview

The Atom Chat Interface Phase 3 includes a memory system that stores conversations in LanceDB, a vector database optimized for semantic search. This enables:

- **Persistent conversation storage** across sessions
- **Semantic search** for relevant conversation context
- **Memory-aware AI responses** that reference previous discussions
- **Multi-user support** with conversation isolation

## Available Endpoints

### 1. Get Conversation History
**Endpoint:** `GET /api/v1/memory/history/{user_id}`

**Parameters:**
- `user_id` (path): User identifier
- `session_id` (query, optional): Filter by session
- `limit` (query, optional): Number of conversations (default: 50)

**Response:**
```json
{
  "status": "success",
  "conversations": [
    {
      "id": "uuid",
      "user_id": "user123",
      "session_id": "session456",
      "role": "user",
      "content": "Hello, how are you?",
      "message_type": "text",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {}
    }
  ],
  "count": 10,
  "total_count": 50,
  "has_more": true
}
```

### 2. Search Conversations
**Endpoint:** `POST /api/v1/memory/search`

**Request Body:**
```json
{
  "query": "technical support issue",
  "user_id": "user123",
  "session_id": "session456",
  "limit": 10,
  "similarity_threshold": 0.7
}
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {
      "id": "uuid",
      "user_id": "user123",
      "session_id": "session456",
      "role": "user",
      "content": "I'm having trouble with the API",
      "similarity_score": 0.85,
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {}
    }
  ],
  "count": 5,
  "query_embedding_length": 384
}
```

### 3. Get Conversation Details
**Endpoint:** `GET /api/v1/conversations/{conversation_id}`

### 4. Get Analytics Overview
**Endpoint:** `GET /api/v1/analytics/overview`

## Usage Examples

### Using the Python Script

1. **Test LanceDB Connection:**
```bash
python retrieve_lancedb_conversations.py --user-id test-user --action test
```

2. **Retrieve Conversations:**
```bash
python retrieve_lancedb_conversations.py --user-id user123 --action retrieve --limit 20
```

3. **Search Conversations:**
```bash
python retrieve_lancedb_conversations.py --user-id user123 --action search --query "technical issue" --limit 10
```

4. **Export Conversations:**
```bash
python retrieve_lancedb_conversations.py --user-id user123 --action export --output my_conversations.json
```

5. **Get Statistics:**
```bash
python retrieve_lancedb_conversations.py --user-id user123 --action stats
```

### Using the API Client

1. **Test API Connection:**
```bash
python lancedb_api_client.py --base-url http://localhost:5059 --user-id test-user --action test
```

2. **Retrieve via API:**
```bash
python lancedb_api_client.py --user-id user123 --action retrieve --limit 20
```

3. **Search via API:**
```bash
python lancedb_api_client.py --user-id user123 --action search --query "technical issue" --limit 10
```

### Programmatic Usage

```python
from lancedb_api_client import LanceDBAPIClient
import asyncio

async def main():
    async with LanceDBAPIClient("http://localhost:5059") as client:
        # Get conversation history
        history = await client.get_conversation_history("user123", limit=20)
        
        # Search conversations
        search_results = await client.search_conversations(
            "technical support", "user123", limit=10
        )
        
        # Export to JSON
        if history["status"] == "success":
            with open("conversations.json", "w") as f:
                import json
                json.dump(history, f, indent=2)

asyncio.run(main())
```

## Data Schema

### Conversation Record Structure

Each conversation record in LanceDB contains:

```python
{
    "id": "uuid",                    # Unique identifier
    "user_id": "user123",            # User identifier
    "session_id": "session456",      # Session identifier
    "role": "user",                  # Message role (user/assistant/system)
    "content": "Hello world",        # Message content
    "message_type": "text",          # Message type
    "timestamp": "2024-01-15T10:30:00Z",  # Timestamp
    "metadata": {},                  # Additional metadata
    "embedding": [0.1, 0.2, ...]     # Vector embedding (384 dimensions)
}
```

### Storage Location

- **Database Path:** `data/lancedb/`
- **Table Name:** `conversations`
- **Embedding Dimension:** 384

## Integration with Chat Interface

The memory system is integrated with the chat interface in several ways:

### 1. Automatic Storage
All chat messages are automatically stored in LanceDB when the memory system is enabled.

### 2. Context Retrieval
Before generating responses, the system searches for relevant conversation context to provide memory-aware responses.

### 3. Semantic Search
Conversations are indexed with embeddings for efficient semantic search.

## Configuration

### Memory System Settings

The memory system can be configured through environment variables:

```bash
# Enable/disable memory system
MEMORY_ENABLED=true

# LanceDB database path
LANCEDB_PATH=data/lancedb

# Embedding service URL (if using external service)
EMBEDDING_SERVICE_URL=http://localhost:5061

# Similarity threshold for search
SIMILARITY_THRESHOLD=0.7
```

### Performance Considerations

- **Storage:** Each conversation message is stored with a 384-dimensional embedding
- **Search:** Semantic search typically completes in < 50ms
- **Memory:** In-memory caching for frequently accessed conversations
- **Backup:** Regular database backups recommended

## Troubleshooting

### Common Issues

1. **"LanceDB not available"**
   - Check if LanceDB is installed: `pip install lancedb`
   - Verify database path exists and is writable

2. **"Memory system not available"**
   - Check if memory system is enabled in configuration
   - Verify LanceDB connection

3. **No search results**
   - Check similarity threshold (try lowering to 0.5)
   - Verify user_id matches stored conversations

4. **Slow performance**
   - Check database size and consider archiving old conversations
   - Verify system resources (CPU, memory)

### Debug Commands

```bash
# Check LanceDB health
python -c "import lancedb; print('LanceDB available')"

# Test memory system directly
python -c "
from backend.python_api_service.lancedb_handler import get_lancedb_connection
import asyncio
async def test():
    conn = await get_lancedb_connection('data/lancedb')
    print('Connection successful')
asyncio.run(test())
"
```

## Best Practices

### 1. User Management
- Use consistent user_id formats
- Implement session management for multi-session users
- Consider data retention policies

### 2. Search Optimization
- Use appropriate similarity thresholds (0.7-0.8 for strict, 0.5-0.6 for broad)
- Limit search results to prevent performance issues
- Cache frequent search queries

### 3. Data Management
- Regularly backup conversation data
- Implement data archiving for old conversations
- Monitor database size and performance

### 4. Security
- Validate user permissions before retrieving conversations
- Sanitize search queries to prevent injection
- Encrypt sensitive conversation data

## Next Steps

For advanced usage, consider:

1. **Custom Embeddings:** Implement domain-specific embedding models
2. **Cross-User Search:** Enable knowledge sharing across users (with permissions)
3. **Conversation Analytics:** Add advanced analytics and insights
4. **Real-time Updates:** Implement WebSocket-based real-time conversation streaming

## Support

For technical support or questions about LanceDB integration:

- Check the main Atom documentation
- Review the chat interface source code
- Contact the development team for advanced use cases