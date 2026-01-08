import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_embeddings():
    print("Testing OpenAI Embeddings via OpenAIService...")
    try:
        from integrations.openai_service import openai_service
        
        # Test text
        text = "ATOM is an advanced task orchestration platform."
        
        # Check if API Key is set
        if not openai_service.api_key:
            print("WARNING: OPENAI_API_KEY not set. Using mock behavior.")
            # This will fail in real call but service handles it
            
        result = await openai_service.generate_embeddings(text)
        print("✓ Successfully called generate_embeddings")
        
        if "data" in result and len(result["data"]) > 0:
            embedding = result["data"][0]["embedding"]
            print(f"✓ Received embedding of size: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
        else:
            print("✗ Unexpected response format")
            print(result)
            
    except Exception as e:
        print(f"Error during embedding test: {e}")

if __name__ == "__main__":
    asyncio.run(test_embeddings())
