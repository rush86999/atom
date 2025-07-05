import os
import logging
import asyncio # Required for asyncio.to_thread
from typing import List, Optional, Tuple
from openai import OpenAI, APIError, RateLimitError, AuthenticationError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import tiktoken # Import tiktoken

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Basic configuration if run standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-ada-002" # OpenAI's recommended model for most use cases
DEFAULT_TOKENIZER_MODEL = "cl100k_base" # Default tokenizer for text-embedding-ada-002

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

def chunk_text(
    text: str,
    max_chunk_tokens: int = 500, # Max tokens per chunk (e.g., for text-embedding-ada-002, max is 8191)
    overlap_tokens: int = 50,    # Number of tokens to overlap between chunks
    tokenizer_model_name: str = DEFAULT_TOKENIZER_MODEL
) -> List[str]:
    """
    Splits text into chunks based on token count using tiktoken, with overlap.
    """
    if not text:
        return []

    try:
        tokenizer = tiktoken.get_encoding(tokenizer_model_name)
    except Exception as e:
        logger.error(f"Failed to get tokenizer for '{tokenizer_model_name}': {e}. Falling back to default 'cl100k_base'.")
        try:
            tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e_fallback:
            logger.error(f"Failed to get fallback tokenizer 'cl100k_base': {e_fallback}. Cannot chunk text.")
            # As a last resort, could fall back to word-based, but for now, we'll indicate failure.
            # Or, raise the error to make it clear chunking isn't possible.
            raise ValueError(f"Could not initialize tiktoken tokenizer: {e_fallback}")


    tokens = tokenizer.encode(text)
    if not tokens:
        return []

    chunks_text: List[str] = []
    current_pos = 0

    while current_pos < len(tokens):
        end_pos = min(current_pos + max_chunk_tokens, len(tokens))
        chunk_tokens = tokens[current_pos:end_pos]

        # Decode the tokens back to text for this chunk
        # Note: decode can sometimes produce slightly different text than the original slice
        # if the split occurs mid-multi-token character sequence. This is generally acceptable.
        chunks_text.append(tokenizer.decode(chunk_tokens))

        if end_pos == len(tokens): # Reached the end
            break

        # Move current_pos for the next chunk, considering overlap
        # Ensure we don't create an infinite loop with overlap if max_chunk_tokens is too small
        advance_by = max(1, max_chunk_tokens - overlap_tokens)
        current_pos += advance_by
        # Safety break if advance_by is too small or overlap is >= max_chunk_tokens
        if advance_by <= 0 :
            logger.warning(f"Chunking advance_by is <=0 ({advance_by}), breaking to avoid infinite loop. Check overlap_tokens ({overlap_tokens}) vs max_chunk_tokens ({max_chunk_tokens}).")
            break


    if not chunks_text and text.strip(): # If text was not empty but somehow resulted in no chunks
        chunks_text.append(text.strip()) # Fallback to the whole text if chunking produced nothing

    logger.info(f"Chunked text into {len(chunks_text)} chunks. Original tokens: {len(tokens)}. Max tokens/chunk: {max_chunk_tokens}, Overlap tokens: {overlap_tokens}")
    return chunks_text


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
    max_chunk_tokens: int = 500, # Renamed from max_tokens_per_chunk_approx
    chunk_overlap_tokens: int = 50, # Renamed from chunk_overlap_approx
    tokenizer_model_name: str = DEFAULT_TOKENIZER_MODEL, # Added tokenizer model name
    openai_client_override: Optional[OpenAI] = None
) -> List[Tuple[str, Optional[List[float]]]]:
    """
    Chunks text using tiktoken and generates embeddings for each chunk.
    Returns a list of tuples: (text_chunk, embedding_vector_or_None).
    """
    client = openai_client_override or get_openai_client()
    if not client:
        logger.error("OpenAI client not available for processing text for embeddings.")
        return []

    try:
        text_chunks = chunk_text(
            full_text,
            max_chunk_tokens=max_chunk_tokens,
            overlap_tokens=chunk_overlap_tokens,
            tokenizer_model_name=tokenizer_model_name
        )
    except ValueError as e: # Catch tokenizer initialization errors
        logger.error(f"Cannot process text for embeddings due to tokenizer error: {e}")
        return []


    if not text_chunks:
        logger.info("No text chunks to process after token-based chunking.")
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

        sample_text_short = "This is a short test sentence. Tiktoken helps manage token limits."
        sample_text_long = (
            "This is the first paragraph of a long document. It discusses various interesting topics. "
            "The quick brown fox jumps over the lazy dog. This sentence is here to add more content. "
            "We need to ensure that our chunking strategy works effectively for different lengths of text. "
            "Another paragraph starts here. It continues the discussion from the previous paragraph but focuses on specifics. "
            "Embeddings are crucial for semantic search. This text will be split and embedded. "
            "Yet another sentence to make the text even longer and test the chunking logic properly. "
            "The art of chunking is to find the right balance between context preservation and individual chunk size. "
            "Too small, and you lose context. Too large, and you might exceed model limits or dilute the embedding's focus. "
            "Using tiktoken for accurate token counting is essential for robust OpenAI API interactions, especially with models like text-embedding-ada-002. "
        ) * 3 # Repeat to make it longer

        tokenizer_for_test = tiktoken.get_encoding(DEFAULT_TOKENIZER_MODEL)

        print(f"Processing short sample text (length: {len(sample_text_short)} chars, tokens: {len(tokenizer_for_test.encode(sample_text_short))})...")
        chunk_embedding_pairs_short = await process_text_for_embeddings(
            sample_text_short,
            max_chunk_tokens=10, # small token chunks for testing
            chunk_overlap_tokens=2,
            tokenizer_model_name=DEFAULT_TOKENIZER_MODEL
        )
        print(f"\nProcessed {len(chunk_embedding_pairs_short)} chunks for short text:")
        for i, (chunk, embedding) in enumerate(chunk_embedding_pairs_short):
            status = "Success" if embedding else "Failed"
            dim = len(embedding) if embedding else "N/A"
            chunk_tokens = len(tokenizer_for_test.encode(chunk))
            print(f"  Chunk {i+1} (tokens: {chunk_tokens}) - Embedding: {status} (Dim: {dim}) | Text: '{chunk[:70]}...'")
            if embedding: print(f"    Embedding vector preview: {embedding[:3]}...")

        print(f"\nProcessing long sample text (length: {len(sample_text_long)} chars, tokens: {len(tokenizer_for_test.encode(sample_text_long))})...")
        chunk_embedding_pairs_long = await process_text_for_embeddings(
            sample_text_long,
            max_chunk_tokens=100, # Max tokens per chunk
            chunk_overlap_tokens=20,  # Overlap in tokens
            tokenizer_model_name=DEFAULT_TOKENIZER_MODEL
        )
        print(f"\nProcessed {len(chunk_embedding_pairs_long)} chunks for long text:")
        for i, (chunk, embedding) in enumerate(chunk_embedding_pairs_long):
            status = "Success" if embedding else "Failed"
            dim = len(embedding) if embedding else "N/A"
            chunk_tokens = len(tokenizer_for_test.encode(chunk))
            print(f"  Chunk {i+1} (tokens: {chunk_tokens}) - Embedding: {status} (Dim: {dim}) | Text: '{chunk[:70]}...'")
            if embedding: print(f"    Embedding vector preview: {embedding[:3]}...")

    # To run this test:
    # 1. Make sure OPENAI_API_KEY is in your environment.
    # 2. Ensure tiktoken is installed (`pip install tiktoken`)
    # 2. Uncomment the line below.
    # asyncio.run(main_test_processor())
    pass
