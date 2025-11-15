# PDF Processing Module for ATOM

A comprehensive PDF processing system with OCR capabilities, image comprehension, and memory storage integration for the ATOM platform.

## Overview

This module provides advanced PDF processing capabilities for ATOM, including:

- **Text Extraction**: Extract text from searchable PDFs using PyPDF2
- **OCR Processing**: Optical Character Recognition for scanned PDFs and images
- **Image Comprehension**: AI-powered understanding of visual content using OpenAI Vision
- **Memory Integration**: Store processed content in LanceDB for semantic search
- **Fallback Strategies**: Graceful degradation when external services are unavailable

## Features

### Core Processing
- **Multi-format Support**: Process PDFs from files, URLs, or byte streams
- **Smart PDF Detection**: Automatically detect searchable vs scanned PDFs
- **OCR with Fallback**: Cascade through multiple OCR engines (Tesseract, EasyOCR, OpenAI)
- **Image Extraction**: Extract and process embedded images
- **Batch Processing**: Support for processing multiple PDFs efficiently

### Memory Storage
- **Vector Embeddings**: Generate embeddings for semantic search
- **Metadata Management**: Store comprehensive document metadata
- **Semantic Search**: Find documents based on content similarity
- **Document Statistics**: Track usage and storage metrics
- **Tag-based Organization**: Categorize documents with custom tags

### Integration Features
- **RESTful API**: Complete API for integration with other services
- **Health Monitoring**: Service status and capability reporting
- **Error Handling**: Robust error handling with detailed feedback
- **Configuration**: Flexible configuration for different environments

## Installation

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

**macOS:**
```bash
brew install tesseract poppler
```

**Windows:**
- Download Tesseract from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)
- Download Poppler from [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases/)

### Python Dependencies

Add the following to your `requirements.txt`:

```txt
# PDF Processing
PyPDF2>=3.0.0,<4.0.0
pdf2image>=1.16.3,<2.0.0
pillow>=10.0.0,<11.0.0

# OCR Libraries
pytesseract>=0.3.10,<1.0.0
easyocr>=1.7.0,<2.0.0

# AI Vision (Optional)
openai>=1.0.0,<2.0.0

# Image Processing
numpy>=1.24.0,<2.0.0
opencv-python>=4.8.0,<5.0.0
```

## Configuration

### Environment Variables

```bash
# OpenAI API Key (for advanced image comprehension)
OPENAI_API_KEY=your_openai_api_key_here

# Tesseract Path (if not in PATH)
TESSERACT_PATH=/usr/bin/tesseract

# OCR Languages (comma-separated)
OCR_LANGUAGES=en,es,fr,de

# LanceDB Configuration
LANCEDB_URI=./data/lancedb
```

### Service Initialization

```python
from atom.backend.integrations.pdf_processing import PDFOCRService, PDFMemoryIntegration

# Initialize OCR Service
pdf_service = PDFOCRService(
    openai_api_key=os.getenv('OPENAI_API_KEY'),
    tesseract_path=os.getenv('TESSERACT_PATH'),
    easyocr_languages=['en', 'es']  # Default: ['en']
)

# Initialize Memory Integration
memory_service = PDFMemoryIntegration(lancedb_handler=your_lancedb_handler)
```

## API Endpoints

### PDF Processing Endpoints

#### `POST /pdf/process`
Process a PDF file with optional OCR and image comprehension.

**Parameters:**
- `file`: PDF file upload (required)
- `use_ocr`: Use OCR for scanned PDFs (default: true)
- `extract_images`: Extract and process images (default: true)
- `use_advanced_comprehension`: Use AI for image understanding (default: false)
- `fallback_strategy`: "cascade" or "parallel" (default: "cascade")

**Response:**
```json
{
  "processing_summary": {
    "used_ocr": true,
    "ocr_methods_tried": ["tesseract", "easyocr"],
    "best_method": "tesseract",
    "total_pages": 10,
    "total_characters": 2500
  },
  "extracted_content": {
    "text": "Extracted text content...",
    "page_breakdown": [...],
    "images": {...}
  },
  "service_status": {...}
}
```

#### `POST /pdf/process-url`
Process a PDF from a URL.

#### `POST /pdf/extract-text-only`
Fast text extraction without OCR.

#### `POST /pdf/analyze-pdf-type`
Analyze PDF type without full processing.

### Memory Integration Endpoints

#### `POST /pdf-memory/store`
Store processed PDF in memory system.

#### `GET /pdf-memory/search`
Search PDF documents using semantic search.

#### `GET /pdf-memory/documents/{doc_id}`
Retrieve a specific document.

#### `DELETE /pdf-memory/documents/{doc_id}`
Delete a document from memory.

#### `GET /pdf-memory/users/{user_id}/stats`
Get document statistics for a user.

## Usage Examples

### Basic PDF Processing

```python
from atom.backend.integrations.pdf_processing import PDFOCRService

# Initialize service
service = PDFOCRService()

# Process a PDF file
with open('document.pdf', 'rb') as f:
    result = await service.process_pdf(
        pdf_data=f.read(),
        use_ocr=True,
        extract_images=True
    )

print(f"Extracted {result['processing_summary']['total_characters']} characters")
print(f"Used method: {result['processing_summary']['best_method']}")
```

### Memory Integration

```python
from atom.backend.integrations.pdf_processing import PDFMemoryIntegration

# Initialize memory service
memory_service = PDFMemoryIntegration(lancedb_handler=lancedb_handler)

# Store processed PDF
storage_result = await memory_service.store_processed_pdf(
    user_id="user_123",
    processing_result=processing_result,
    source_uri="file:///documents/report.pdf",
    tags=["report", "quarterly", "finance"]
)

# Search documents
search_results = await memory_service.search_pdfs(
    user_id="user_123",
    query="quarterly financial report",
    limit=10,
    similarity_threshold=0.7
)
```

### Complete Workflow

```python
async def process_and_store_pdf(user_id: str, file_path: str):
    # Process PDF
    with open(file_path, 'rb') as f:
        processing_result = await pdf_service.process_pdf(f.read())
    
    # Store in memory
    storage_result = await memory_service.store_processed_pdf(
        user_id=user_id,
        processing_result=processing_result,
        source_uri=f"file://{file_path}"
    )
    
    return storage_result
```

## Fallback Strategies

The system implements intelligent fallback mechanisms:

1. **Cascade Strategy**: Try methods in order of preference
   - OpenAI Vision (if available and requested)
   - EasyOCR
   - Tesseract
   - Basic PyPDF2 extraction

2. **Parallel Strategy**: Try all methods and pick the best result

3. **Service Availability**: Automatically detect available OCR engines

## Error Handling

The module provides comprehensive error handling:

- **File Validation**: Validate PDF files before processing
- **Service Availability**: Check OCR engine availability
- **API Rate Limits**: Handle external API limitations
- **Memory Constraints**: Manage large document processing
- **Network Issues**: Handle connectivity problems gracefully

## Performance Considerations

- **Large Documents**: Process documents in chunks for memory efficiency
- **Batch Processing**: Use batch endpoints for multiple documents
- **Caching**: Implement caching for frequently accessed documents
- **Background Processing**: Use async processing for better performance

## Testing

Run the test suite:

```bash
cd atom/backend/integrations/pdf_processing
python -m pytest tests/ -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This module is part of the ATOM platform and follows the same licensing terms.

## Support

For issues and questions:
- Create an issue in the ATOM repository
- Check the documentation
- Contact the development team