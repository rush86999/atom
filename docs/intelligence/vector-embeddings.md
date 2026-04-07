# Vector Embeddings Guide - Atom Personal Edition

> **Everything you need to know about vector embeddings in Atom**

---

## Table of Contents

1. [What are Vector Embeddings?](#what-are-vector-embeddings)
2. [Atom's Embedding Setup](#atoms-embedding-setup)
3. [Configuration Options](#configuration-options)
4. [Performance Comparison](#performance-comparison)
5. [Usage in Atom](#usage-in-atom)
6. [Testing Embeddings](#testing-embeddings)
7. [Troubleshooting](#troubleshooting)

---

## What are Vector Embeddings?

Vector embeddings are numerical representations of text that capture semantic meaning. They enable:

- **Semantic Search**: Find similar content even without exact keyword matches
- **Episodic Memory**: Agents remember and learn from past experiences
- **Knowledge Retrieval**: Find relevant information across large datasets
- **Recommendations**: Suggest similar workflows, agents, or actions

**Example:**
```
Text: "How do I reset my password?"
Embedding: [0.123, -0.456, 0.789, ...] (384 or 1536 numbers)

Text: "Password reset instructions"
Embedding: [0.125, -0.458, 0.791, ...] (very similar!)

Similarity: 95% match (even though different words)
```

---

## Atom's Embedding Setup

### Default Configuration (Personal Edition)

Atom uses **FastEmbed** by default - perfect for personal use!

**Why FastEmbed?**
- ✅ **Local**: No API calls, no costs, works offline
- ✅ **Fast**: 10-20ms per document (vs 100-300ms for cloud)
- ✅ **Lightweight**: ONNX-based, minimal memory usage
- ✅ **Good Quality**: BAAI/bge-small-en-v1.5 model (384 dimensions)
- ✅ **Privacy**: All embeddings generated on your machine

### Architecture

```
┌─────────────────┐
│  Text Input     │
│  "Hello world"  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  EmbeddingService               │
│  Provider: fastembed (default)  │
│  Model: BAAI/bge-small-en-v1.5  │
│  Output: 384-dimensional vector │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  LanceDB (Vector Database)      │
│  Storage: ./data/lancedb/       │
│  Index: Automatic IVF/PQ        │
│  Search: Cosine similarity      │
└─────────────────────────────────┘
```

---

## Configuration Options

### Provider Comparison

| Provider | Speed | Quality | Cost | Privacy | Use Case |
|----------|-------|---------|------|---------|----------|
| **FastEmbed** | ⚡⚡⚡ Very Fast (10-20ms) | ⭐⭐⭐ Good | ✅ Free | ✅ 100% Local | **Personal Edition (default)** |
| **OpenAI** | ⚡ Moderate (100-300ms) | ⭐⭐⭐⭐⭐ Excellent | 💰 Paid API | ❌ Cloud | Production, highest quality |
| **Cohere** | ⚡ Moderate (150-400ms) | ⭐⭐⭐⭐ Very Good | 💰 Paid API | ❌ Cloud | Multilingual support |

### FastEmbed Models (Recommended for Personal)

**Default: BAAI/bge-small-en-v1.5**
- Dimensions: 384
- Speed: ~10ms per document
- Quality: Good for most use cases
- Memory: ~100MB

**Alternative: BAAI/bge-base-en-v1.5**
- Dimensions: 768
- Speed: ~15ms per document
- Quality: Better for complex queries
- Memory: ~200MB

**Configuration:**
```bash
# .env file
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5  # Default
# OR
FASTEMBED_MODEL=BAAI/bge-base-en-v1.5   # Better quality
```

### OpenAI Models (Optional, Requires API Key)

**text-embedding-3-small** (Recommended)
- Dimensions: 1536
- Speed: ~100ms per document
- Quality: Excellent
- Cost: ~$0.02 per 1M tokens

**text-embedding-3-large**
- Dimensions: 3072
- Speed: ~200ms per document
- Quality: Best available
- Cost: ~$0.13 per 1M tokens

**Configuration:**
```bash
# .env file
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Cohere Models (Optional, Multilingual)

**embed-english-v3.0**
- Dimensions: 1024
- Quality: Very Good
- Cost: ~$0.10 per 1M tokens

**embed-multilingual-v3.0**
- Dimensions: 1024
- Quality: Very Good
- Supports: 100+ languages
- Cost: ~$0.10 per 1M tokens

**Configuration:**
```bash
# .env file
EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=your-cohere-key-here
```

---

## Performance Comparison

### Benchmark Results (Local Machine)

**Test**: Embed 1,000 documents

| Provider | Time | Throughput | Cost |
|----------|------|------------|------|
| **FastEmbed (bge-small)** | 12 seconds | 83 docs/sec | $0.00 |
| **FastEmbed (bge-base)** | 18 seconds | 55 docs/sec | $0.00 |
| **OpenAI (text-embedding-3-small)** | 95 seconds | 10 docs/sec | ~$0.05 |
| **Cohere (embed-english-v3.0)** | 140 seconds | 7 docs/sec | ~$0.10 |

### Memory Usage

| Provider | Model Memory | Vector Size (per doc) |
|----------|--------------|----------------------|
| **FastEmbed (bge-small)** | ~100MB | 1.5 KB (384 dims) |
| **FastEmbed (bge-base)** | ~200MB | 3.0 KB (768 dims) |
| **OpenAI (small)** | ~0MB (cloud) | 6.0 KB (1536 dims) |
| **OpenAI (large)** | ~0MB (cloud) | 12.0 KB (3072 dims) |

---

## Usage in Atom

### Episodic Memory

Agents use embeddings to remember and retrieve past experiences:

```python
# When agent completes a task
episode = {
    "content": "Fixed authentication bug in login flow",
    "timestamp": "2024-02-16T10:30:00Z",
    "outcome": "success"
}

# Automatically embedded and stored
embedding_service.generate_embedding(episode["content"])
# → Stored in LanceDB for semantic retrieval
```

**Retrieval:**
```python
# Agent searches past experiences
query = "How did I fix the login issue?"
similar_episodes = lancedb_handler.search(query, limit=5)
# Returns semantically similar episodes, even with different words
```

### Semantic Search

Search across all agent interactions, documents, and workflows:

```python
# User searches
query = "automate email responses"

# Finds:
# - "Set up email auto-reply rules"
# - "Configure Gmail auto-responders"
# - "Email automation workflows"
# (even though query used "automate" and results use "auto-reply/auto-responders")
```

### Knowledge Graph

Embeddings power the knowledge graph's semantic understanding:

```python
# Relationships discovered through semantic similarity
"invoice" ≈ "bill" ≈ "statement" (similarity > 0.9)
"meeting" ≈ "call" ≈ "discussion" (similarity > 0.85)
```

---

## Testing Embeddings

### Quick Test

```bash
# Start Python
cd backend
source venv/bin/activate
python

# Test embedding service
>>> from core.embedding_service import EmbeddingService
>>> service = EmbeddingService()
>>> embedding = await service.generate_embedding("Hello, world!")
>>> len(embedding)
384  # FastEmbed default dimension
>>> embedding[:5]
[0.123, -0.456, 0.789, -0.234, 0.567]
```

### Test Semantic Search

```python
# Test semantic similarity
>>> text1 = "How do I reset my password?"
>>> text2 = "Password reset instructions"
>>> text3 = "The weather is nice today"

>>> emb1 = await service.generate_embedding(text1)
>>> emb2 = await service.generate_embedding(text2)
>>> emb3 = await service.generate_embedding(text3)

# Calculate cosine similarity
>>> import numpy as np
>>> def similarity(a, b):
...     return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

>>> similarity(emb1, emb2)  # Password texts
0.92  # Very similar!

>>> similarity(emb1, emb3)  # Different topics
0.15  # Not similar
```

### Verify LanceDB Storage

```bash
# Check LanceDB data directory
ls -lh data/lancedb/

# Should see vector indices
# - memory/
# - documents/
# - communications/
```

---

## Troubleshooting

### Issue: Slow Embedding Generation

**Symptom**: Embeddings take >100ms per document

**Solution:**
```bash
# Check which provider you're using
grep EMBEDDING_PROVIDER .env

# If using OpenAI/Cohere, switch to FastEmbed
echo "EMBEDDING_PROVIDER=fastembed" >> .env
echo "FASTEMBED_MODEL=BAAI/bge-small-en-v1.5" >> .env

# Restart Atom
```

### Issue: Poor Search Results

**Symptom**: Semantic search not finding relevant content

**Solutions:**

1. **Check embedding model**:
```bash
# Try better model
echo "FASTEMBED_MODEL=BAAI/bge-base-en-v1.5" >> .env
```

2. **Verify embeddings are being generated**:
```python
# Check LanceDB has embeddings
import lancedb
db = lancedb.connect("./data/lancedb")
tables = db.table_names()
print(tables)  # Should show: ['memory', 'documents', ...]
```

3. **Re-index if needed**:
```bash
# Clear and rebuild indices
rm -rf data/lancedb/
# Restart Atom (will auto-rebuild)
```

### Issue: Out of Memory

**Symptom**: High memory usage when generating embeddings

**Solution:**
```bash
# Use smaller model
echo "FASTEMBED_MODEL=BAAI/bge-small-en-v1.5" >> .env

# Reduce batch size
echo "EMBEDDING_BATCH_SIZE=32" >> .env  # Default: 64
```

### Issue: FastEmbed Not Working

**Symptom**: `ModuleNotFoundError: fastembed`

**Solution:**
```bash
cd backend
source venv/bin/activate
pip install fastembed>=0.2.0

# Or update all dependencies
pip install -r requirements.txt --upgrade
```

### Issue: LanceDB Connection Error

**Symptom**: `ConnectionError: lancedb`

**Solution:**
```bash
# Check data directory exists
mkdir -p data/lancedb

# Verify permissions
chmod 755 data/lancedb

# Check environment variable
grep LANCEDB_PATH .env
# Should be: LANCEDB_PATH=./data/lancedb
```

---

## Best Practices

### For Personal Edition

1. **Use FastEmbed** - Default, optimized for personal use
2. **Keep BAAI/bge-small-en-v1.5** - Good balance of speed/quality
3. **Local storage only** - No need for S3 in personal edition
4. **Regular cleanup** - Old embeddings can be deleted

### When to Switch Providers

**Switch to OpenAI if:**
- You need highest quality embeddings
- You're doing complex semantic tasks
- Cost is not a concern
- You have reliable internet

**Switch to Cohere if:**
- You need multilingual support
- You're working with non-English content
- You need specialized domain embeddings

**Stick with FastEmbed if:**
- Personal use or development
- Privacy is important
- Offline capability needed
- Cost-sensitive

---

## Configuration Examples

### Minimal Personal Setup (Recommended)

```bash
# .env file
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
LANCEDB_PATH=./data/lancedb
```

### High-Quality Personal Setup

```bash
# .env file
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-base-en-v1.5  # Better quality
LANCEDB_PATH=./data/lancedb
EMBEDDING_BATCH_SIZE=32  # Reduce memory
```

### Production Setup (Cloud)

```bash
# .env file
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
LANCEDB_S3_BUCKET=atom-embeddings
AWS_REGION=us-east-1
```

---

## Summary

**Atom Personal Edition uses FastEmbed by default** - perfect for local use!

✅ **What you get:**
- Local embedding generation (no API calls)
- Fast performance (10-20ms per document)
- Good quality (BAAI/bge-small-en-v1.5)
- Privacy-focused (all data stays local)
- Zero cost (free and open source)

✅ **Vector storage:**
- LanceDB database in `./data/lancedb/`
- Automatic indexing
- Semantic search enabled
- Episodic memory powered by embeddings

✅ **No configuration needed:**
- Works out of the box
- Automatic embedding generation
- Semantic search enabled by default

🎉 **Everything just works!**

---

## Next Steps

1. **Verify embeddings are working** (see Testing section above)
2. **Try semantic search** in the Atom dashboard
3. **Check episodic memory** - agents remember past interactions
4. **Adjust model** if needed (switch to bge-base for better quality)

[Documentation Index](./README.md) | [Personal Edition Guide](./PERSONAL_EDITION.md)
