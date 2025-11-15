# BYOK Integration for PDF Processing

## Overview

The BYOK (Bring Your Own Key) system provides comprehensive AI provider management and cost optimization for PDF processing in the ATOM platform. This integration allows users to manage their own API keys, track usage, and optimize costs across multiple AI providers.

## Features

### 🔑 Key Management
- **Secure Storage**: Encrypted API key storage with fallback to environment variables
- **Multi-Environment Support**: Separate keys for development, staging, and production
- **Usage Tracking**: Monitor API usage and costs per provider
- **Key Rotation**: Easy key updates and management

### 💰 Cost Optimization
- **Provider Selection**: Automatic selection of optimal providers based on task type and budget
- **Cost Tracking**: Real-time cost monitoring and usage analytics
- **Budget Constraints**: Set spending limits for different tasks
- **Alternative Scenarios**: Compare different provider options

### 📊 Usage Analytics
- **Request Tracking**: Monitor successful and failed requests
- **Token Usage**: Track token consumption across providers
- **Cost Accumulation**: Real-time cost calculations
- **Rate Limit Monitoring**: Track API rate limits and usage patterns

## Integration Architecture

### BYOK Manager
The central component that manages:
- Provider configurations
- API key storage and encryption
- Usage tracking and analytics
- Cost optimization algorithms

### PDF Processing Integration
- **PDF OCR Service**: Uses BYOK for OpenAI Vision API key management
- **PDF Memory Integration**: Tracks usage for embedding generation and semantic search
- **Route Optimization**: BYOK-aware route selection for optimal performance

## API Endpoints

### BYOK Management Endpoints

#### `GET /api/ai/providers`
Get all available AI providers with status and capabilities.

**Response:**
```json
{
  "providers": [
    {
      "provider": {
        "id": "openai",
        "name": "OpenAI",
        "description": "GPT models for general AI tasks and PDF processing",
        "api_key_env_var": "OPENAI_API_KEY",
        "cost_per_token": 0.002,
        "supported_tasks": ["chat", "code", "analysis", "pdf_ocr", "image_comprehension"],
        "max_requests_per_minute": 60,
        "is_active": true
      },
      "usage": {
        "total_requests": 150,
        "successful_requests": 145,
        "failed_requests": 5,
        "total_tokens_used": 45000,
        "cost_accumulated": 90.0
      },
      "has_api_keys": true,
      "status": "active"
    }
  ],
  "total_providers": 6,
  "active_providers": 3
}
```

#### `POST /api/ai/providers/{provider_id}/keys`
Store an API key for a provider.

**Parameters:**
- `api_key`: The API key to store
- `key_name`: Key identifier (default: "default")
- `environment`: Environment (development/staging/production)

#### `GET /api/ai/providers/{provider_id}/keys/{key_name}`
Get API key status (without revealing the key).

#### `DELETE /api/ai/providers/{provider_id}/keys/{key_name}`
Delete an API key.

### PDF-Specific BYOK Endpoints

#### `GET /api/ai/pdf/providers`
Get AI providers specifically optimized for PDF processing.

**Response:**
```json
{
  "pdf_providers": [
    {
      "provider_id": "openai",
      "name": "OpenAI",
      "supported_tasks": ["pdf_ocr", "image_comprehension"],
      "cost_per_token": 0.002
    }
  ],
  "total_pdf_providers": 4,
  "supported_tasks": ["pdf_ocr", "image_comprehension", "document_processing", "multimodal"]
}
```

#### `POST /api/ai/pdf/optimize`
Optimize provider selection for PDF processing.

**Request:**
```json
{
  "pdf_type": "scanned",
  "needs_ocr": true,
  "needs_image_comprehension": true,
  "estimated_pages": 10,
  "budget_constraint": 0.05
}
```

**Response:**
```json
{
  "pdf_analysis": {
    "pdf_type": "scanned",
    "needs_ocr": true,
    "needs_image_comprehension": true,
    "estimated_pages": 10,
    "estimated_tokens": 5000
  },
  "recommended_provider": {
    "provider_id": "openai",
    "name": "OpenAI",
    "task_type": "image_comprehension",
    "estimated_cost": 10.0,
    "cost_per_token": 0.002
  },
  "alternative_scenarios": {
    "high_quality": {
      "provider": "anthropic",
      "name": "Anthropic Claude",
      "estimated_cost": 40.0,
      "recommended_for": "Complex PDFs with images and diagrams"
    },
    "cost_effective": {
      "provider": "google_gemini",
      "name": "Google Gemini",
      "estimated_cost": 2.5,
      "recommended_for": "Simple OCR tasks on scanned documents"
    }
  }
}
```

### Cost Optimization Endpoints

#### `POST /api/ai/optimize-cost`
Optimize AI cost usage for general tasks.

**Request:**
```json
{
  "task_type": "pdf_ocr",
  "budget_constraint": 0.01,
  "estimated_tokens": 1000
}
```

#### `POST /api/ai/usage/track`
Track AI usage for cost monitoring.

#### `GET /api/ai/usage/stats`
Get usage statistics for AI providers.

## PDF Processing Integration

### PDF OCR Service BYOK Integration

The PDF OCR service automatically integrates with BYOK for:

1. **API Key Management**: Retrieves OpenAI API keys from BYOK system
2. **Provider Optimization**: Uses BYOK to select optimal providers for OCR tasks
3. **Usage Tracking**: Tracks token usage for cost monitoring
4. **Fallback Strategy**: Graceful degradation when BYOK is unavailable

**Configuration:**
```python
from integrations.pdf_processing import PDFOCRService

# With BYOK integration (recommended)
service = PDFOCRService(use_byok=True)

# Without BYOK integration (fallback)
service = PDFOCRService(use_byok=False, openai_api_key="your-key")
```

### PDF Processing Endpoints with BYOK

#### Enhanced PDF Processing
All PDF processing endpoints now support BYOK optimization:

- `POST /api/v1/pdf/process` - Process PDF with BYOK optimization
- `POST /api/v1/pdf/process-url` - Process PDF from URL with BYOK
- `GET /api/v1/pdf/status` - Get service status with BYOK integration info

**Example PDF Processing with BYOK:**
```bash
curl -X POST "http://localhost:5058/api/v1/pdf/process" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "use_ocr=true" \
  -F "use_advanced_comprehension=true" \
  -F "optimize_with_byok=true" \
  -F "fallback_strategy=cascade"
```

**Response includes BYOK optimization info:**
```json
{
  "processing_summary": {
    "used_ocr": true,
    "best_method": "openai_vision",
    "total_pages": 10,
    "total_characters": 2500
  },
  "byok_optimization": {
    "optimized": true,
    "task_type": "image_comprehension",
    "optimal_provider": "openai",
    "provider_name": "OpenAI",
    "cost_per_token": 0.002
  }
}
```

## Configuration

### Environment Variables

```bash
# BYOK Encryption Key (required for production)
BYOK_ENCRYPTION_KEY=your-secure-encryption-key-here

# Provider API Keys (fallback if not stored in BYOK)
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key
AZURE_OPENAI_API_KEY=your-azure-key
DEEPSEEK_API_KEY=your-deepseek-key
HUGGINGFACE_API_KEY=your-huggingface-key
```

### BYOK Configuration Files

BYOK stores configuration in two JSON files:

- `./data/byok_config.json` - Provider configurations and usage stats
- `./data/byok_keys.json` - Encrypted API keys

**Example byok_config.json:**
```json
{
  "providers": {
    "openai": {
      "id": "openai",
      "name": "OpenAI",
      "description": "GPT models for general AI tasks and PDF processing",
      "api_key_env_var": "OPENAI_API_KEY",
      "cost_per_token": 0.002,
      "supported_tasks": ["chat", "code", "analysis", "pdf_ocr", "image_comprehension"],
      "max_requests_per_minute": 60,
      "is_active": true
    }
  },
  "usage_stats": {
    "openai": {
      "provider_id": "openai",
      "total_requests": 150,
      "successful_requests": 145,
      "failed_requests": 5,
      "total_tokens_used": 45000,
      "cost_accumulated": 90.0,
      "last_used": "2024-01-15T10:30:00"
    }
  }
}
```

## Usage Examples

### 1. Setting Up API Keys

```python
from core.byok_endpoints import get_byok_manager

byok_manager = get_byok_manager()

# Store OpenAI API key
key_id = byok_manager.store_api_key(
    provider_id="openai",
    api_key="your-openai-api-key",
    key_name="production",
    environment="production"
)

print(f"API key stored with ID: {key_id}")
```

### 2. PDF Processing with BYOK Optimization

```python
from integrations.pdf_processing import PDFOCRService

# Initialize service with BYOK integration
service = PDFOCRService(use_byok=True)

# Process PDF with automatic provider optimization
with open('document.pdf', 'rb') as f:
    result = await service.process_pdf(
        pdf_data=f.read(),
        use_ocr=True,
        use_advanced_comprehension=True,
        fallback_strategy="cascade"
    )

print(f"Used provider: {result['byok_optimization']['optimal_provider']}")
print(f"Estimated cost: ${result['byok_optimization']['estimated_cost']}")
```

### 3. Cost Optimization for PDF Processing

```python
from core.byok_endpoints import get_byok_manager

byok_manager = get_byok_manager()

# Optimize for PDF processing
optimization = await byok_manager.optimize_pdf_processing({
    "pdf_type": "scanned",
    "needs_ocr": True,
    "needs_image_comprehension": False,
    "estimated_pages": 20,
    "budget_constraint": 0.02
})

print(f"Recommended provider: {optimization['recommended_provider']['name']}")
print(f"Estimated cost: ${optimization['recommended_provider']['estimated_cost']}")
```

## Security Considerations

### Encryption
- API keys are encrypted using a configurable encryption key
- Default encryption uses XOR for development (not production-safe)
- For production, implement proper encryption (AES, Fernet, etc.)

### Access Control
- BYOK endpoints should be protected with authentication
- Consider implementing role-based access control for key management
- Audit logging for all key operations

### Key Rotation
- Regular key rotation is recommended
- BYOK supports multiple key versions per provider
- Seamless key updates without service interruption

## Monitoring and Analytics

### Health Checks
```bash
curl "http://localhost:5058/api/ai/health"
```

### Usage Statistics
```bash
curl "http://localhost:5058/api/ai/usage/stats"
```

### Provider Status
```bash
curl "http://localhost:5058/api/ai/providers/openai"
```

## Troubleshooting

### Common Issues

1. **BYOK Not Available**
   - Check if BYOK_ENCRYPTION_KEY is set
   - Verify BYOK configuration files are writable

2. **Provider Inactive**
   - Ensure API keys are stored in BYOK or environment variables
   - Check provider configuration in byok_config.json

3. **Cost Optimization Fails**
   - Verify supported tasks for each provider
   - Check budget constraints are realistic

4. **PDF Processing Without BYOK**
   - Service falls back to environment variables
   - Basic functionality remains available

### Debug Mode

Enable debug logging for BYOK operations:
```python
import logging
logging.getLogger('byok').setLevel(logging.DEBUG)
```

## Migration Guide

### From Environment Variables to BYOK

1. **Export existing keys:**
   ```bash
   export OPENAI_API_KEY=your-key
   export ANTHROPIC_API_KEY=your-key
   ```

2. **Store keys in BYOK:**
   ```python
   from core.byok_endpoints import get_byok_manager
   byok_manager = get_byok_manager()
   
   byok_manager.store_api_key("openai", os.getenv("OPENAI_API_KEY"))
   byok_manager.store_api_key("anthropic", os.getenv("ANTHROPIC_API_KEY"))
   ```

3. **Update services to use BYOK:**
   ```python
   # Old way
   service = PDFOCRService(openai_api_key=os.getenv("OPENAI_API_KEY"))
   
   # New way
   service = PDFOCRService(use_byok=True)
   ```

## Best Practices

### 1. Key Management
- Use different keys for different environments
- Implement regular key rotation
- Monitor key usage and revoke unused keys

### 2. Cost Optimization
- Set realistic budget constraints
- Monitor usage patterns and adjust accordingly
- Use cost-effective providers for simple tasks

### 3. Error Handling
- Implement graceful fallbacks when BYOK is unavailable
- Monitor BYOK system health
- Log BYOK operations for debugging

### 4. Security
- Never log API keys
- Use secure encryption in production
- Implement proper access controls

## Support

For issues with BYOK integration:

1. Check the BYOK health endpoint: `/api/ai/health`
2. Review application logs for BYOK-related errors
3. Verify API keys are properly stored and accessible
4. Check provider configurations in byok_config.json

## Future Enhancements

- Multi-tenant key management
- Advanced cost prediction algorithms
- Real-time budget alerts
- Provider performance analytics
- Automated key rotation
- Integration with more AI providers