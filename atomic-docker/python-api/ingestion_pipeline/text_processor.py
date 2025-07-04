import os
import logging
import asyncio # Required for asyncio.to_thread
from typing import List, Optional, Tuple
from openai import OpenAI, APIError, RateLimitError, AuthenticationError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Basic configuration if run standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-ada-002" # OpenAI's recommended model for most use cases

# Initialize OpenAI client
_openai_client_instance: Optional[OpenAI] = None

def get_openai_client() -> Optional[OpenAI]:
    global _openai_client_instance
    if _openai_client_instance is None:
        if OPENAI_API_KEY:
            _openai_client_instance = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized by text_processor module.")
        else:
            logger.warning("OPENAI_API_KEY not set. OpenAI client cannot be initialized by text_processor.")
    return _openai_client_instance

def chunk_text(text: str, max_chunk_size_words: int = 400, overlap_words: int = 50) -> List[str]:
    """
    Splits text into chunks based on approximate word count, with overlap.

    NOTE: This is a simplified word-based chunker. For production, using a
    tokenizer like 'tiktoken' to count actual tokens and split based on model
    limits (e.g., 8191 tokens for text-embedding-ada-002) and desired chunk
    token size is strongly recommended for accuracy and to avoid exceeding API limits.
    This implementation approximates tokens with words.
    """
    if not text:
        return []

    words = text.split() # Splits by any whitespace and handles multiple spaces.
    if not words:
        return []

    chunks: List[str] = []
    current_pos = 0

    while current_pos < len(words):
        end_pos = min(current_pos + max_chunk_size_words, len(words))
        chunk_words = words[current_pos:end_pos]
        chunks.append(" ".join(chunk_words))

        if end_pos == len(words): # Reached the end
            break

        # Move current_pos for the next chunk, considering overlap
        # Ensure we don't create an infinite loop with overlap if max_chunk_size_words is too small
        advance_by = max(1, max_chunk_size_words - overlap_words)
        current_pos += advance_by

    if not chunks and text.strip(): # If text was not empty but somehow resulted in no chunks
        chunks.append(text.strip())

    logger.info(f"Chunked text into {len(chunks)} chunks. Original words: {len(words)}. Max words/chunk: {max_chunk_size_words}, Overlap: {overlap_words}")
    return chunks


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError))
)
async def generate_embedding(text_chunk: str, openai_client: Optional[OpenAI] = None) -> Optional[List[float]]:
    """
    Generates embedding for a given text chunk using OpenAI API.
    """
    client = openai_client or get_openai_client()
    if not client:
        logger.error("OpenAI client not available for generating embedding.")
        return None

    # Normalize whitespace and ensure it's not just whitespace
    processed_chunk = text_chunk.strip()
    if not processed_chunk:
        logger.warning("Attempted to generate embedding for empty or whitespace-only text chunk.")
        return None # Return None for empty strings to avoid API call

    try:
        attempt_num = getattr(generate_embedding, 'retry', {}).get('statistics', {}).get('attempt_number', 1)
        logger.debug(f"Generating embedding for chunk (attempt {attempt_num}, len {len(processed_chunk)} chars, first 50): '{processed_chunk[:50]}...'")

        response = await asyncio.to_thread(
            client.embeddings.create,
            input=[processed_chunk], # API expects a list of strings
            model=EMBEDDING_MODEL
        )
        embedding = response.data[0].embedding
        logger.debug(f"Successfully generated embedding for chunk. Vector dim: {len(embedding)}")
        return embedding
    except AuthenticationError as e:
        logger.error(f"OpenAI AuthenticationError during embedding generation: {e}. Will not retry.", exc_info=True)
        raise
    except APIError as e:
        logger.warning(f"OpenAI APIError during embedding generation (will retry if applicable): {e}", exc_info=True)
        raise
    except Exception as e: # Includes openai.BadRequestError if input is too long after stripping
        logger.error(f"Unexpected error during embedding generation for chunk: {e}", exc_info=True)
        # Check for specific error types if input length is an issue, e.g. openai.BadRequestError
        # if "reduce the length of the messages" in str(e).lower():
        #    logger.error(f"Chunk likely too long for OpenAI API: {processed_chunk[:100]}...")
        raise

async def process_text_for_embeddings(
    full_text: str,
    max_tokens_per_chunk_approx: int = 400, # Using word count as proxy
    chunk_overlap_approx: int = 50,       # Using word count as proxy
    openai_client_override: Optional[OpenAI] = None
) -> List[Tuple[str, Optional[List[float]]]]:
    """
    Chunks text and generates embeddings for each chunk.
    Returns a list of tuples: (text_chunk, embedding_vector_or_None).
    """
    client = openai_client_override or get_openai_client()
    if not client:
        logger.error("OpenAI client not available for processing text for embeddings.")
        return []

    text_chunks = chunk_text(full_text,
                             max_chunk_size_words=max_tokens_per_chunk_approx,
                             overlap_words=chunk_overlap_approx)

    if not text_chunks:
        logger.info("No text chunks to process after chunking.")
        return []

    results = []
    for i, chunk in enumerate(text_chunks):
        logger.info(f"Processing chunk {i+1}/{len(text_chunks)} for embedding.")
        embedding_vector: Optional[List[float]] = None
        try:
            embedding_vector = await generate_embedding(chunk, openai_client=client)
        except Exception:
            logger.error(f"Failed to generate embedding for chunk {i+1} after all attempts. Chunk content (start): {chunk[:100]}...")
            # Error is logged by generate_embedding, here we ensure it's None.
        results.append((chunk, embedding_vector))

    return results

if __name__ == '__main__':
    # Example Usage (requires OPENAI_API_KEY to be set)
    async def main_test_processor():
        if not OPENAI_API_KEY:
            print("Please set OPENAI_API_KEY for testing text_processor.")
            return

        sample_text_short = "This is a short test sentence."
        sample_text_long = (
            "This is the first paragraph of a long document. It discusses various interesting topics. "
            "The quick brown fox jumps over the lazy dog. This sentence is here to add more content. "
            "We need to ensure that our chunking strategy works effectively for different lengths of text. "
            "Another paragraph starts here. It continues the discussion from the previous paragraph but focuses on specifics. "
            "Embeddings are crucial for semantic search. This text will be split and embedded. "
            "Yet another sentence to make the text even longer and test the chunking logic properly. "
            "The art of chunking is to find the right balance between context preservation and individual chunk size. "
            "Too small, and you lose context. Too large, and you might exceed model limits or dilute the embedding's focus. "
        ) * 3 # Repeat to make it longer

        print(f"Processing short sample text (length: {len(sample_text_short)} chars)...")
        chunk_embedding_pairs_short = await process_text_for_embeddings(
            sample_text_short,
            max_tokens_per_chunk_approx=50, # small chunks for testing
            chunk_overlap_approx=5
        )
        print(f"\nProcessed {len(chunk_embedding_pairs_short)} chunks for short text:")
        for i, (chunk, embedding) in enumerate(chunk_embedding_pairs_short):
            status = "Success" if embedding else "Failed"
            dim = len(embedding) if embedding else "N/A"
            print(f"  Chunk {i+1} (len: {len(chunk.split())} words) - Embedding: {status} (Dim: {dim}) | Text: '{chunk[:70]}...'")
            if embedding: print(f"    Embedding vector preview: {embedding[:3]}...")

        print(f"\nProcessing long sample text (length: {len(sample_text_long)} chars)...")
        chunk_embedding_pairs_long = await process_text_for_embeddings(
            sample_text_long,
            max_tokens_per_chunk_approx=100,
            chunk_overlap_approx=20
        )
        print(f"\nProcessed {len(chunk_embedding_pairs_long)} chunks for long text:")
        for i, (chunk, embedding) in enumerate(chunk_embedding_pairs_long):
            status = "Success" if embedding else "Failed"
            dim = len(embedding) if embedding else "N/A"
            print(f"  Chunk {i+1} (len: {len(chunk.split())} words) - Embedding: {status} (Dim: {dim}) | Text: '{chunk[:70]}...'")
            if embedding: print(f"    Embedding vector preview: {embedding[:3]}...")

    # To run this test:
    # 1. Make sure OPENAI_API_KEY is in your environment.
    # 2. Uncomment the line below.
    # asyncio.run(main_test_processor())
    pass
