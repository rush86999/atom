# OAuth Authentication - Quick Setup Guide

This guide will help you set up OAuth 2.0 authentication for LLM providers in 5 minutes.

## Prerequisites

- Python 3.11+
- PostgreSQL or SQLite database
- Administrator access to OAuth provider consoles

## Step 1: Install Dependencies (1 minute)

```bash
cd backend
pip install cryptography httpx
```

## Step 2: Generate Encryption Key (1 minute)

Run the encryption key generator:

```bash
python scripts/generate_oauth_encryption_key.py
```

This will generate a Fernet encryption key. **Save it securely!**

Add the key to your `.env` file:

```bash
OAUTH_ENCRYPTION_KEY=your-generated-key-here
```

## Step 3: Run Database Migration (1 minute)

```bash
cd backend
alembic upgrade head
```

Or specifically:

```bash
alembic upgrade 20260426_llm_oauth
```

This creates the `llm_oauth_credentials` table.

## Step 4: Configure OAuth Provider (5-10 minutes)

Choose which providers you want to support and set them up:

### Google AI Studio (Gemini)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new OAuth 2.0 Client ID (Web application)
3. Add redirect URI: `http://localhost:8000/api/v1/llm/oauth/callback`
4. Enable APIs: Cloud AI Platform, Generative Language API
5. Add to `.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### OpenAI

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Navigate to Settings → API keys → Create OAuth app
3. Configure redirect URI
4. Add to `.env`:

```bash
OPENAI_OAUTH_CLIENT_ID=your-openai-client-id
OPENAI_OAUTH_CLIENT_SECRET=your-openai-client-secret
```

### Anthropic (Enterprise Only)

⚠️ **Note**: Anthropic OAuth requires enterprise approval.

1. Contact Anthropic for OAuth access
2. Follow enterprise setup guide
3. Add to `.env`:

```bash
ANTHROPIC_OAUTH_CLIENT_ID=your-anthropic-client-id
ANTHROPIC_OAUTH_CLIENT_SECRET=your-anthropic-client-secret
```

### Hugging Face

1. Go to [Hugging Face Settings](https://huggingface.co/settings/connections)
2. Create new OAuth application
3. Add to `.env`:

```bash
HUGGINGFACE_OAUTH_CLIENT_ID=your-hf-client-id
HUGGINGFACE_OAUTH_CLIENT_SECRET=your-hf-client-secret
```

## Step 5: Configure Redirect URI (1 minute)

Add to your `.env` file:

```bash
# Development
LLM_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/llm/oauth/callback

# Production (change when deploying)
# LLM_OAUTH_REDIRECT_URI=https://your-domain.com/api/v1/llm/oauth/callback
```

## Step 6: Verify Setup (1 minute)

Start your application:

```bash
cd backend
python -m uvicorn main:app --reload
```

Test the OAuth endpoints:

```bash
# List supported providers
curl http://localhost:8000/api/v1/llm/oauth/providers

# Check provider status
curl http://localhost:8000/api/v1/llm/oauth/providers/google/status
```

## Step 7: Connect OAuth (Frontend Integration)

You'll need to build a frontend flow to connect OAuth:

1. **Initiate OAuth** - Call the authorize endpoint
2. **User Authorization** - Redirect user to provider
3. **Callback Handler** - Receive authorization code
4. **Token Exchange** - Backend exchanges code for tokens

Example API flow:

```javascript
// 1. Initiate OAuth
const response = await fetch('/api/v1/llm/oauth/authorize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    provider_id: 'google',
    redirect_uri: 'http://localhost:3000/oauth/callback'
  })
});

const { authorization_url, state } = await response.json();

// 2. Redirect user to authorization_url
window.location.href = authorization_url;

// 3. Handle callback (in your frontend route)
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// 4. Send code to backend
await fetch('/api/v1/llm/oauth/callback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: code,
    state: state,
    redirect_uri: 'http://localhost:3000/oauth/callback'
  })
});
```

## Testing Your Setup

### Test with curl

```bash
# 1. Get authorization URL
curl -X POST http://localhost:8000/api/v1/llm/oauth/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "google",
    "redirect_uri": "http://localhost:8000/api/v1/llm/oauth/callback"
  }'

# 2. Visit the authorization_url in your browser
# 3. After authorization, check credentials
curl http://localhost:8000/api/v1/llm/oauth/credentials
```

### Test with Python

```python
import requests

# Check provider status
response = requests.get("http://localhost:8000/api/v1/llm/oauth/providers/openai/status")
print(response.json())

# List credentials
response = requests.get("http://localhost:8000/api/v1/llm/oauth/credentials")
print(response.json())
```

## Troubleshooting

### "redirect_uri_mismatch" Error

**Cause**: Redirect URI doesn't match what's configured in provider console

**Fix**:
1. Check `LLM_OAUTH_REDIRECT_URI` in `.env`
2. Verify it matches exactly in provider's OAuth app settings
3. Include protocol (http/https) and port

### "invalid_client" Error

**Cause**: Client ID or secret is incorrect

**Fix**:
1. Verify client ID and secret in `.env`
2. Check for extra spaces or quotes
3. Regenerate secrets in provider console if needed

### Encryption Errors

**Cause**: `OAUTH_ENCRYPTION_KEY` is missing or invalid

**Fix**:
1. Run `python scripts/generate_oauth_encryption_key.py`
2. Add generated key to `.env`
3. Restart application

### Migration Fails

**Cause**: Database connection issue or migration conflict

**Fix**:
```bash
# Check current version
alembic current

# Force upgrade (use with caution)
alembic upgrade head --sql

# Or downgrade and retry
alembic downgrade base
alembic upgrade head
```

## Security Checklist

Before going to production, ensure:

- [ ] `OAUTH_ENCRYPTION_KEY` is set and backed up securely
- [ ] All client secrets are in `.env` (not in code)
- [ ] `.env` is added to `.gitignore`
- [ ] Redirect URIs are whitelisted in provider consoles
- [ ] Different OAuth apps for dev/staging/production
- [ ] HTTPS is enabled for production
- [ ] OAuth credentials are tested and working

## Next Steps

1. **Build Frontend UI** - Create OAuth connection flow in your frontend
2. **Add Token Management** - Build interface for managing OAuth credentials
3. **Implement Monitoring** - Track OAuth usage and success rates
4. **Testing** - Test with real OAuth providers in staging
5. **Documentation** - Create user guides for OAuth setup

## Need Help?

- **Implementation Guide**: See `docs/OAUTH_AUTHENTICATION_IMPLEMENTATION.md`
- **API Documentation**: Visit `/docs` when app is running
- **Test Examples**: See `backend/tests/test_llm_oauth_*.py`
- **Issues**: Check troubleshooting section or open an issue

---

**Setup Time**: ~10-15 minutes
**Difficulty**: Intermediate
**Result**: Secure OAuth 2.0 authentication for LLM providers ✅
