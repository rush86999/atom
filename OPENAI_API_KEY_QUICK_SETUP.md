# OpenAI API Key Configuration

## Current Status
Search functionality requires a valid OpenAI API key. Current error: "Incorrect API key provided: mock_api_key"

## Setup Steps

1. **Get OpenAI API Key**
   - Visit: https://platform.openai.com/account/api-keys
   - Create new secret key
   - Copy the key (won't be shown again)

2. **Configure Environment**
   Add to your .env file:
   ```
   OPENAI_API_KEY=sk-your-actual-key-here
   ```

3. **Restart Backend**
   The backend will automatically pick up the new API key.

4. **Test Search**
   ```bash
   curl -X POST http://localhost:5058/semantic_search_meetings \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "limit": 5}'
   ```

## Expected Response
```json
{
  "results": [...],
  "success": true
}
```

## Troubleshooting
- 401 Error: Invalid API key - verify key is correct
- 429 Error: Rate limit exceeded - check usage limits
- Check OpenAI status: https://status.openai.com
