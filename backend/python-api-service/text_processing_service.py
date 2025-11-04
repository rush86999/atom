"""
Text Processing Service for ATOM Agent Memory System

This service provides text processing, chunking, and embedding generation
for document ingestion into LanceDB vector store.
"""

import os
import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

# Try to import text processing libraries
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning("tiktoken not available - using fallback chunking")

# Try to import embedding libraries
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy not available - using dummy embeddings")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available - using dummy embeddings")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available - using fallback embeddings")

logger = logging.getLogger(__name__)


class TextProcessingConfig:
    """Configuration for text processing service"""
    
    def __init__(self):
        self.chunk_size = 500  # characters
        self.chunk_overlap = 50  # characters
        self.min_chunk_size = 100  # characters
        self.max_chunk_size = 1000  # characters
        self.embedding_model = "all-MiniLM-L6-v2"  # sentence-transformers model
        self.embedding_dimension = 384
        self.use_openai_embeddings = False
        self.openai_model = "text-embedding-ada-002"


class TextProcessingService:
    """
    Service for text processing, chunking, and embedding generation
    """
    
    def __init__(self, config: TextProcessingConfig = None):
        self.config = config or TextProcessingConfig()
        self.embedding_model = None
        self.tokenizer = None
        
        # Initialize components
        self._initialize_embedding_model()
        self._initialize_tokenizer()
        
        logger.info("Initialized TextProcessingService")
    
    def _initialize_embedding_model(self):
        """Initialize embedding model"""
        try:
            # Try sentence-transformers first
            if SENTENCE_TRANSFORMERS_AVAILABLE and not self.config.use_openai_embeddings:
                self.embedding_model = SentenceTransformer(self.config.embedding_model)
                logger.info(f"Initialized sentence-transformers model: {self.config.embedding_model}")
                return
            
            # Try OpenAI embeddings
            if OPENAI_AVAILABLE and self.config.use_openai_embeddings:
                # Check API key
                if os.getenv('OPENAI_API_KEY'):
                    logger.info(f"Initialized OpenAI embeddings model: {self.config.openai_model}")
                    return
                else:
                    logger.warning("OpenAI API key not found")
            
            # Use dummy embeddings
            self.embedding_model = "dummy"
            logger.warning("Using dummy embeddings")
            
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            self.embedding_model = "dummy"
    
    def _initialize_tokenizer(self):
        """Initialize tokenizer for text analysis"""
        try:
            if TIKTOKEN_AVAILABLE:
                # Use cl100k_base (compatible with many models)
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
                logger.info("Initialized tiktoken tokenizer")
            else:
                # Use simple word-based tokenizer
                self.tokenizer = "simple"
                logger.info("Using simple word tokenizer")
                
        except Exception as e:
            logger.error(f"Error initializing tokenizer: {e}")
            self.tokenizer = "simple"
    
    def process_text_for_embeddings(
        self, 
        text: str, 
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[str]:
        """
        Process text for embedding generation by chunking appropriately
        
        Args:
            text: Input text to process
            chunk_size: Override chunk size
            chunk_overlap: Override chunk overlap
        
        Returns:
            List of text chunks ready for embedding
        """
        try:
            # Use config or override values
            chunk_size = chunk_size or self.config.chunk_size
            chunk_overlap = chunk_overlap or self.config.chunk_overlap
            
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            
            if not cleaned_text:
                return []
            
            # Choose chunking method
            if self.tokenizer == "simple":
                chunks = self._chunk_by_character_count(
                    cleaned_text, chunk_size, chunk_overlap
                )
            elif TIKTOKEN_AVAILABLE:
                chunks = self._chunk_by_token_count(
                    cleaned_text, chunk_size, chunk_overlap
                )
            else:
                chunks = self._chunk_by_character_count(
                    cleaned_text, chunk_size, chunk_overlap
                )
            
            # Filter chunks by size
            filtered_chunks = [
                chunk for chunk in chunks
                if len(chunk.strip()) >= self.config.min_chunk_size
            ]
            
            logger.debug(f"Generated {len(filtered_chunks)} chunks from {len(cleaned_text)} characters")
            return filtered_chunks
            
        except Exception as e:
            logger.error(f"Error processing text for embeddings: {e}")
            return [text] if text else []
    
    async def generate_embeddings(
        self, 
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors
        """
        try:
            if not texts:
                return []
            
            logger.debug(f"Generating embeddings for {len(texts)} texts")
            
            # Choose embedding method
            if self.embedding_model == "dummy":
                return self._generate_dummy_embeddings(texts)
            elif isinstance(self.embedding_model, SentenceTransformer):
                return self._generate_sentence_transformer_embeddings(texts)
            elif self.config.use_openai_embeddings and OPENAI_AVAILABLE:
                return await self._generate_openai_embeddings(texts)
            else:
                return self._generate_dummy_embeddings(texts)
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Return dummy embeddings as fallback
            return self._generate_dummy_embeddings(texts)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for processing"""
        try:
            if not text:
                return ""
            
            # Remove excessive whitespace
            cleaned = re.sub(r'\s+', ' ', text)
            
            # Remove special characters but keep basic punctuation
            cleaned = re.sub(r'[^\w\s.,!?;:()-"\']', '', cleaned)
            
            # Strip leading/trailing whitespace
            cleaned = cleaned.strip()
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning text: {e}")
            return text or ""
    
    def _chunk_by_character_count(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int
    ) -> List[str]:
        """Chunk text by character count with overlap"""
        try:
            chunks = []
            start = 0
            
            while start < len(text):
                # Calculate chunk end
                end = start + chunk_size
                
                # Get chunk
                chunk = text[start:end]
                
                # Try to end at sentence boundary if possible
                if end < len(text):
                    sentence_end = chunk.rfind('.')
                    if sentence_end > chunk_size // 2:  # Reasonable sentence end
                        chunk = chunk[:sentence_end + 1]
                        end = start + sentence_end + 1
                
                if chunk.strip():
                    chunks.append(chunk.strip())
                
                # Move start position with overlap
                start = max(start + 1, end - chunk_overlap)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error in character-based chunking: {e}")
            return [text]
    
    def _chunk_by_token_count(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int
    ) -> List[str]:
        """Chunk text by token count using tiktoken"""
        try:
            # Tokenize text
            tokens = self.tokenizer.encode(text)
            
            chunks = []
            start = 0
            
            while start < len(tokens):
                # Calculate chunk end
                end = start + chunk_size
                
                # Get token chunk
                chunk_tokens = tokens[start:end]
                
                # Try to end at sentence boundary
                if end < len(tokens):
                    # Look backward for sentence end
                    for i in range(len(chunk_tokens) - 1, -1, -1):
                        if len(chunk_tokens) - i > chunk_overlap:
                            break
                        if chunk_tokens[i] in [13, 46]:  # Period in cl100k_base
                            end = start + i + 1
                            chunk_tokens = tokens[start:end]
                            break
                
                # Decode to text
                chunk = self.tokenizer.decode(chunk_tokens)
                if chunk.strip():
                    chunks.append(chunk.strip())
                
                # Move start with overlap
                start = max(start + 1, end - chunk_overlap)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error in token-based chunking: {e}")
            # Fallback to character-based chunking
            return self._chunk_by_character_count(text, chunk_size, chunk_overlap)
    
    def _generate_dummy_embeddings(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate dummy embeddings for fallback"""
        try:
            embeddings = []
            
            for text in texts:
                # Generate consistent pseudo-random embedding based on text hash
                text_hash = hash(text) % 10000
                embedding = []
                
                for i in range(self.config.embedding_dimension):
                    # Simple pseudo-random based on hash and position
                    value = (text_hash * (i + 1) * 31) % 1000 / 1000.0
                    # Normalize to [-1, 1] range
                    embedding.append((value - 0.5) * 2)
                
                embeddings.append(embedding)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating dummy embeddings: {e}")
            # Return zero vectors
            return [[0.0] * self.config.embedding_dimension for _ in texts]
    
    def _generate_sentence_transformer_embeddings(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings using sentence-transformers"""
        try:
            # Generate embeddings
            embeddings = self.embedding_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                normalize_embeddings=True
            )
            
            # Convert to Python lists
            return [embedding.tolist() for embedding in embeddings]
            
        except Exception as e:
            logger.error(f"Error generating sentence-transformer embeddings: {e}")
            return self._generate_dummy_embeddings(texts)
    
    async def _generate_openai_embeddings(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            # Check API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OpenAI API key not found")
            
            # Import OpenAI
            import openai
            openai.api_key = api_key
            
            # Generate embeddings in batches
            all_embeddings = []
            batch_size = 100  # OpenAI limit
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                response = await openai.Embedding.acreate(
                    model=self.config.openai_model,
                    input=batch_texts
                )
                
                # Extract embeddings
                batch_embeddings = [
                    data.embedding for data in response.data
                ]
                all_embeddings.extend(batch_embeddings)
                
                # Add small delay to avoid rate limiting
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Error generating OpenAI embeddings: {e}")
            return self._generate_dummy_embeddings(texts)
    
    def get_text_statistics(self, text: str) -> Dict[str, Any]:
        """Get statistics about text content"""
        try:
            if not text:
                return {"char_count": 0, "word_count": 0, "token_count": 0}
            
            # Basic statistics
            char_count = len(text)
            word_count = len(text.split())
            
            # Token count if tokenizer available
            token_count = 0
            if self.tokenizer and TIKTOKEN_AVAILABLE:
                token_count = len(self.tokenizer.encode(text))
            elif self.tokenizer:
                token_count = len(text.split())  # Simple approximation
            
            # Sentence count
            sentence_count = len(re.split(r'[.!?]+', text)) if text else 0
            
            return {
                "char_count": char_count,
                "word_count": word_count,
                "token_count": token_count,
                "sentence_count": sentence_count,
                "estimated_chunks": max(
                    1, (token_count // self.config.chunk_size) + 1
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting text statistics: {e}")
            return {
                "char_count": len(text) if text else 0,
                "word_count": 0,
                "token_count": 0,
                "sentence_count": 0
            }


# Global service instance
_text_processing_service: Optional[TextProcessingService] = None


def get_text_processing_service() -> TextProcessingService:
    """Get global text processing service instance"""
    global _text_processing_service
    
    if _text_processing_service is None:
        _text_processing_service = TextProcessingService()
    
    return _text_processing_service


def process_text_for_embeddings(
    text: str, 
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[str]:
    """
    Process text for embedding generation (convenience function)
    
    Args:
        text: Input text to process
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    service = get_text_processing_service()
    return service.process_text_for_embeddings(text, chunk_size, chunk_overlap)


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for texts (convenience function)
    
    Args:
        texts: List of texts to embed
    
    Returns:
        List of embedding vectors
    """
    service = get_text_processing_service()
    return await service.generate_embeddings(texts)


def get_text_statistics(text: str) -> Dict[str, Any]:
    """
    Get text statistics (convenience function)
    
    Args:
        text: Input text
    
    Returns:
        Dictionary with text statistics
    """
    service = get_text_processing_service()
    return service.get_text_statistics(text)


# Initialize service on module import
get_text_processing_service()