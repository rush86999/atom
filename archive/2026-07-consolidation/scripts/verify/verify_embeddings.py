import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_embeddings():
    print("Testing OpenAI Embeddings via LLMService/EmbeddingService...")
    try:
        from core.llm_service import LLMService
        from core.embedding_service import EmbeddingService
        
        # Initialize services
        # Explicitly use openai since fastembed might not be in this env
        embedding_service = EmbeddingService(provider="openai")
        
        # Test text
        text = "ATOM is an advanced task orchestration platform."
        
        print(f"Generating embedding for: '{text}'")
        
        # In LLMService, we usually need a tenant_id for many operations, 
        # but EmbeddingService.generate_embedding handles the fallback.
        result = await embedding_service.generate_embedding(text)
        
        if result and len(result) > 0:
            print(f"✓ Successfully generated embedding of size: {len(result)}")
            print(f"  First 5 values: {result[:5]}")
        else:
            print("✗ Failed to generate embedding or empty result")
            
    except Exception as e:
        print(f"Error during embedding test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_embeddings())
