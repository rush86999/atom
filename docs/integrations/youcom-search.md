# You.com Search Integration

ATOM now supports **You.com** as a primary web search provider alongside Tavily. You.com provides AI-powered search with real-time web results, citations, and advanced research capabilities.

## Features

- **Real-time web search** with current information
- **Cited results** with source attribution  
- **AI-powered summaries** and answers
- **BYOK (Bring Your Own Key)** support for tenant-specific API keys
- **Automatic fallback** to Tavily if You.com is unavailable
- **Provider transparency** - responses include provider information

## Configuration

### Environment Variables

Set your You.com API key using one of these methods:

```bash
# Platform-wide configuration
YDC_API_KEY=your_youcom_api_key_here

# Alternative: Tavily fallback
TAVILY_API_KEY=your_tavily_key_here
```

### BYOK Configuration

You can also configure API keys per tenant through the BYOK system:

1. Go to **Settings > AI Intelligence (BYOK)**
2. Add a new provider key:
   - Provider: `youcom` 
   - API Key: Your You.com API key
   - Name: Any descriptive name

## Usage

The integration works automatically through ATOM's existing web search functionality:

```python
# Agents automatically use You.com for web search
search_result = await mcp_service.web_search("latest AI research papers")

# Response includes provider information
print(search_result["provider"])  # "you.com" or "tavily"
```

### Priority Order

ATOM tries search providers in this order:

1. **Tenant-specific You.com key** (BYOK)
2. **Platform You.com key** (YDC_API_KEY env var)
3. **Tenant-specific Tavily key** (BYOK fallback)
4. **Platform Tavily key** (TAVILY_API_KEY env var)

## API Response Format

You.com responses are normalized to match ATOM's expected format:

```json
{
  "query": "search query",
  "results": [
    {
      "url": "https://example.com/article",
      "title": "Article Title", 
      "content": "Article description/snippet",
      "score": 0.85
    }
  ],
  "answer": "AI-generated summary answer",
  "provider": "you.com"
}
```

## Benefits Over Tavily

- **More comprehensive results** - You.com often returns richer, more detailed information
- **Better AI summaries** - Advanced answer generation with citations
- **Real-time information** - Access to very recent web content
- **Citation quality** - Higher quality source attribution

## Troubleshooting

### No Search Results

If search returns empty results:

1. **Check API key**: Verify `YDC_API_KEY` is set correctly
2. **Check BYOK**: Ensure tenant has valid You.com key configured
3. **Check logs**: Look for "You.com search failed" messages
4. **Fallback**: System should automatically fall back to Tavily

### API Key Issues

Common API key problems:

- **Invalid key**: Check You.com dashboard for correct API key
- **Quota exceeded**: Verify your You.com account has available credits
- **Network issues**: Check connectivity to api.you.com

### Configuration Check

Verify your configuration:

```bash
# Check if YDC_API_KEY is set
echo $YDC_API_KEY

# Check ATOM logs for provider selection
tail -f backend/logs/app.log | grep "web_search"
```

## Getting You.com API Key

1. Visit [You.com Developer Portal](https://api.you.com)
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Generate a new API key
5. Add to your ATOM configuration

## Implementation Details

The You.com integration:

- Uses the official You.com Search API (`https://api.you.com/search`)
- Implements bearer token authentication
- Includes safety defaults (moderate safesearch, US country code)
- Provides automatic response transformation to ATOM format
- Supports graceful fallback on API failures

For technical details, see `backend/integrations/mcp_service.py` and the BYOK provider configuration in `backend/api/byok_routes.py`.