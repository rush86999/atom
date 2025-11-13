import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_document_service():
    """Test the enhanced document service"""
    try:
        logger.info("🧪 Testing Document Service")

        # Import the enhanced service
        try:
            from backend.python_api_service.document_service_enhanced import EnhancedDocumentService
            logger.info("✅ Document service imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import
