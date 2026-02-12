
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ATOM_MODEL_DOWNLOADER")

def download_models():
    """
    Pre-download AI models to local cache to avoid runtime delays.
    """
    logger.info("Starting model download...")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Downloading/Loading model: {model_name}")
        
        # This triggers the download and caches it in ~/.cache/torch/sentence_transformers
        model = SentenceTransformer(model_name)
        
        # Test encoding to ensure it works
        embedding = model.encode("Test sentence for warm-up")
        logger.info(f"Model loaded successfully. Embedding dimension: {len(embedding)}")
        logger.info("✅ Model cached successfully.")
        
    except ImportError:
        logger.error("❌ sentence_transformers not installed. Skipping.")
    except Exception as e:
        logger.error(f"❌ Failed to download model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_models()
