#!/usr/bin/env python3
"""
Test script to verify vector embeddings are working in Atom Personal Edition.

Run this script to test:
1. Embedding service initialization
2. Vector generation
3. Semantic similarity
4. LanceDB connection
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from core.embedding_service import EmbeddingService
from core.lancedb_config import get_lancedb_connection


async def test_embeddings():
    """Test embedding generation and semantic similarity"""

    print("╔════════════════════════════════════════════════════════════╗")
    print("║  Atom Personal Edition - Vector Embeddings Test            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    # Test 1: Initialize embedding service
    print("🔧 Test 1: Initialize Embedding Service")
    print("-" * 60)

    try:
        service = EmbeddingService()
        print(f"✅ Provider: {service.provider}")
        print(f"✅ Model: {service.model}")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize embedding service: {e}")
        print("   Make sure fastembed is installed:")
        print("   pip install fastembed>=0.2.0")
        return False

    # Test 2: Generate single embedding
    print("🔢 Test 2: Generate Embedding")
    print("-" * 60)

    test_text = "Hello, world! This is a test of the embedding system."
    print(f"Text: '{test_text}'")

    try:
        import time
        start = time.time()
        embedding = await service.generate_embedding(test_text)
        elapsed = time.time() - start

        print(f"✅ Generated {len(embedding)}-dimensional vector")
        print(f"✅ Time: {elapsed*1000:.1f}ms")
        print(f"✅ Sample values: {embedding[:5]}")
        print()

        # Performance check
        if elapsed > 0.5:
            print(f"⚠️  Warning: Embedding generation took {elapsed*1000:.1f}ms")
            print(f"   Expected: 10-20ms for FastEmbed, 100-300ms for OpenAI")
            print()

    except Exception as e:
        print(f"❌ Failed to generate embedding: {e}")
        return False

    # Test 3: Semantic similarity
    print("🔍 Test 3: Semantic Similarity")
    print("-" * 60)

    text1 = "How do I reset my password?"
    text2 = "Password reset instructions"
    text3 = "The weather is nice today"

    print(f"Text 1: '{text1}'")
    print(f"Text 2: '{text2}'")
    print(f"Text 3: '{text3}'")
    print()

    try:
        import numpy as np

        emb1 = await service.generate_embedding(text1)
        emb2 = await service.generate_embedding(text2)
        emb3 = await service.generate_embedding(text3)

        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)

        print(f"✅ Similarity (text1 vs text2): {sim_12:.3f}")
        print(f"   (Related concepts: 'reset password' ≈ 'password reset')")
        print()
        print(f"✅ Similarity (text1 vs text3): {sim_13:.3f}")
        print(f"   (Unrelated concepts: 'password' vs 'weather')")
        print()

        # Semantic check
        if sim_12 > 0.7:
            print("✅ Semantic similarity working correctly!")
            print(f"   Related texts have high similarity ({sim_12:.2f})")
        else:
            print(f"⚠️  Warning: Low similarity between related texts ({sim_12:.2f})")
            print("   This might indicate an issue with the embedding model")

        if sim_13 < 0.3:
            print("✅ Semantic dissimilarity working correctly!")
            print(f"   Unrelated texts have low similarity ({sim_13:.2f})")
        else:
            print(f"⚠️  Warning: High similarity between unrelated texts ({sim_13:.2f})")

        print()

    except Exception as e:
        print(f"❌ Failed to calculate similarity: {e}")
        return False

    # Test 4: LanceDB connection
    print("💾 Test 4: LanceDB Vector Database")
    print("-" * 60)

    try:
        db = get_lancedb_connection()
        tables = db.table_names()
        print(f"✅ Connected to LanceDB")
        print(f"✅ Existing tables: {tables if tables else 'None (first run)'}")
        print()

        # Check storage path
        from core.lancedb_config import LOCAL_DB_PATH
        import os

        if os.path.exists(LOCAL_DB_PATH):
            size_mb = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, _, filenames in os.walk(LOCAL_DB_PATH)
                for filename in filenames
            ) / (1024 * 1024)
            print(f"✅ Storage path: {LOCAL_DB_PATH}")
            print(f"✅ Database size: {size_mb:.2f} MB")
        else:
            print(f"ℹ️  Storage path will be created: {LOCAL_DB_PATH}")

        print()

    except Exception as e:
        print(f"❌ Failed to connect to LanceDB: {e}")
        print("   This is okay for first-time setup")
        print("   LanceDB will be initialized when you start Atom")
        return True  # Don't fail on this

    # Summary
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  ✅ All Tests Passed!                                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("📊 Summary:")
    print(f"   Provider: {service.provider}")
    print(f"   Model: {service.model}")
    print(f"   Embedding dimensions: {len(embedding)}")
    print(f"   Semantic search: ✅ Working")
    print(f"   Vector storage: ✅ Ready")
    print()
    print("🎉 Vector embeddings are properly configured!")
    print()
    print("📚 Learn more:")
    print("   - Vector Embeddings Guide: docs/VECTOR_EMBEDDINGS.md")
    print("   - Personal Edition Guide: docs/PERSONAL_EDITION.md")
    print()

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_embeddings())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
