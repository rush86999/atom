# OpenAI API Key Setup Guide for ATOM Platform Search Functionality

## Overview
The ATOM platform's search functionality requires a valid OpenAI API key to generate embeddings for semantic search. Currently, the system is using a mock API key which causes search operations to fail.

## Current Status
- **Search Status**: ❌ Not working (401 error - invalid API key)
- **Current Key**: `mock_api_key`
- **Required**: Valid OpenAI API key

## Step 1: Obtain OpenAI API Key

### Option A: New OpenAI Account
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up for an account or log in
3. Navigate to [API Keys](https://platform.openai.com/account/api-keys)
4. Click "Create new secret key"
5. Copy the generated key (you won't be able to see it again)

### Option B: Existing Account
1. Log into your [OpenAI account](https://platform.openai.com/)
2. Go to [API Keys](https://platform.openai.com/account/api-keys)
3. Create a new key or use an existing one
4. Ensure you have sufficient credits/usage limits

## Step 2: Configure API Key

### Method A: Environment Variable (Recommended)
Add the following to your `.env` file:

```bash
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### Method B: Direct Configuration
Update the search configuration in the backend:

```python
# In your search configuration
openai_api_key = os.getenv("OPENAI_API_KEY", "your-actual-key-here")
```

## Step 3: Verify Configuration

### Test Search Functionality
```bash
# Test semantic search
curl -X POST http://localhost:5058/semantic_search_meetings \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "limit": 5}'
```

### Expected Response
```json
{
  "results": [...],
  "success": true,
  "query": "test query"
}
```

## Step 4: Security Best Practices

### ✅ Do:
- Store API keys in environment variables
- Use different keys for development and production
- Regularly rotate API keys
- Monitor usage through OpenAI dashboard

### ❌ Don't:
- Commit API keys to version control
- Share keys in public repositories
- Use the same key across multiple applications without monitoring

## Step 5: Troubleshooting

### Common Issues

#### 401 Unauthorized
- **Cause**: Invalid or expired API key
- **Solution**: Generate a new key and update configuration

#### 429 Rate Limit
- **Cause**: Too many requests
- **Solution**: Implement rate limiting or upgrade plan

#### Insufficient Credits
- **Cause**: No credits in OpenAI account
- **Solution**: Add billing information to OpenAI account

### Verification Commands

```bash
# Check if API key is loaded
curl -s http://localhost:5058/api/search/health

# Test embedding generation
curl -X POST http://localhost:5058/api/search/test-embedding \
  -H "Content-Type: application/json" \
  -d '{"text": "test document"}'
```

## Step 6: Production Deployment

### Environment Variables for Production
```bash
# Production .env
OPENAI_API_KEY=sk-prod-your-key-here
OPENAI_ORGANIZATION=org-your-org-id  # Optional
OPENAI_PROJECT=proj-your-project-id  # Optional
```

### Monitoring
- Set up alerts for API usage limits
- Monitor embedding generation costs
- Track search performance metrics

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [OpenAI Pricing](https://openai.com/pricing)
- [API Usage Dashboard](https://platform.openai.com/usage)

## Support
If you encounter issues with OpenAI API configuration:
1. Check OpenAI status: [status.openai.com](https://status.openai.com)
2. Verify account billing status
3. Contact OpenAI support if needed

---

**Next Step**: After configuring the OpenAI API key, test the search functionality and proceed with OAuth service integrations.