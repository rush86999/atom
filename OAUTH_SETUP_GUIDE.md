# OAuth Setup Guide

This guide explains how to set up OAuth credentials for the integrations that were implemented in the recent update.

---

## Notion OAuth Setup

### Step 1: Create a Notion Integration

1. Go to [Notion My Integrations](https://www.notion.so/my-integrations)
2. Click "+ New integration"
3. Fill in the details:
   - **Name**: Atom (or your preferred name)
   - **Associated workspace**: Select your workspace
   - **Type**: Internal
   - **Caption**: Atom integration for workflow automation
4. Click "Submit"

### Step 2: Get Your Credentials

After creating the integration, you'll see:
- **Client ID**: Copy this (e.g., `abcd1234-5678-90ef-ghij-klmnopqrstuv`)
- **Client Secret**: Click "Show secret" and copy it

### Step 3: Configure Environment Variables

Update your `.env` file:

```bash
NOTION_CLIENT_ID=your_actual_client_id_here
NOTION_CLIENT_SECRET=your_actual_client_secret_here
NOTION_REDIRECT_URI=http://localhost:8000/api/notion/callback
```

**Note**: The redirect URI must match exactly what you configure in Notion.

### Step 4: Test the OAuth Flow

1. Start the Atom backend server
2. Navigate to: `http://localhost:8000/api/notion/auth/url`
3. Copy the returned URL and open it in a browser
4. Authorize the integration
5. You should be redirected to your callback URL with a success message

---

## Stripe OAuth Setup

### Step 1: Create a Stripe Connect Application

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Navigate to **Developers** → **Appointments** or **Connect**
3. Click "Create app" or "Create platform"
4. Fill in the details:
   - **App name**: Atom
   - **Platform**: Your platform (Web, Mobile, etc.)

### Step 2: Configure OAuth Settings

1. In your Stripe app settings, go to **Connect** or **OAuth**
2. Add redirect URIs:
   - Development: `http://localhost:8000/api/stripe/callback`
   - Production: `https://your-domain.com/api/stripe/callback`
3. Select permissions: Typically "Read and write" for full access
4. Copy your credentials

### Step 3: Get Your Credentials

You'll need:
- **Client ID**: Found in your Stripe app settings
- **Client Secret**: Found in your Stripe app settings (click "Reveal secret key")

### Step 4: Configure Environment Variables

Update your `.env` file:

```bash
STRIPE_CLIENT_ID=your_actual_stripe_client_id
STRIPE_CLIENT_SECRET=your_actual_stripe_client_secret
STRIPE_REDIRECT_URI=http://localhost:8000/api/stripe/callback
```

### Step 5: Test the OAuth Flow

1. Start the Atom backend server
2. Navigate to: `http://localhost:8000/stripe/auth/url`
3. Copy the returned URL and open it in a browser
4. Authorize your Stripe account
5. You should be redirected with a success message

---

## Asana Setup (Personal Access Token)

Asana supports both OAuth and Personal Access Tokens (PAT). For testing, PAT is simpler.

### Step 1: Generate a Personal Access Token

1. Go to [Asana Developer Console](https://app.asana.com/-/developer_console)
2. Click "Create New Personal Access Token"
3. Fill in the details:
   - **Token name**: Atom Integration
   - **Description**: Atom workflow automation
4. Click "Create"
5. **Important**: Copy the token immediately (you won't see it again!)

### Step 2: Configure Environment Variables

Update your `.env` file:

```bash
ASANA_ACCESS_TOKEN=your_actual_asana_token_here
```

### Step 3: Test the Integration

1. Start the Atom backend server
2. Test the health check: `curl http://localhost:8000/api/asana/health`
3. You should see a successful response

---

## Production Deployment

For production, you'll need to:

### 1. Update Redirect URIs

Change all redirect URIs from localhost to your production domain:

```bash
# Notion
NOTION_REDIRECT_URI=https://your-domain.com/api/notion/callback

# Stripe
STRIPE_REDIRECT_URI=https://your-domain.com/api/stripe/callback
```

### 2. Configure OAuth Apps in Production

- **Notion**: Add your production redirect URI to the integration settings
- **Stripe**: Add your production redirect URI to the Connect app settings

### 3. Use Secure Secrets Management

Don't commit `.env` to version control. Use a secrets manager like:
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Google Secret Manager

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NOTION_CLIENT_ID` | Yes | - | Notion OAuth Client ID |
| `NOTION_CLIENT_SECRET` | Yes | - | Notion OAuth Client Secret |
| `NOTION_REDIRECT_URI` | Yes | http://localhost:8000/api/notion/callback | OAuth callback URL |
| `NOTION_OAUTH_ENABLED` | No | true | Enable/disable Notion OAuth |
| `EMERGENCY_OAUTH_BYPASS` | No | false | Emergency bypass for OAuth checks |
| `STRIPE_CLIENT_ID` | Yes | - | Stripe Connect Client ID |
| `STRIPE_CLIENT_SECRET` | Yes | - | Stripe Connect Client Secret |
| `STRIPE_REDIRECT_URI` | Yes | http://localhost:8000/api/stripe/callback | OAuth callback URL |
| `ASANA_ACCESS_TOKEN` | Yes | - | Asana Personal Access Token |
| `WORKFLOW_MOCK_ENABLED` | No | false | Use mock workflow data |
| `COMMISSION_AUTO_CALCULATE` | No | true | Enable auto commission calculation |

---

## Troubleshooting

### Notion OAuth Fails

- **Error**: "redirect_uri_mismatch"
  - **Solution**: Ensure the redirect URI in `.env` matches exactly what's configured in Notion

- **Error**: "invalid_client"
  - **Solution**: Verify your Client ID and Secret are correct

### Stripe OAuth Fails

- **Error**: "invalid_client"
  - **Solution**: Check that you're using the correct Client ID (not the publishable key)

- **Error**: "redirect_uri_mismatch"
  - **Solution**: Add your redirect URI to the Stripe Connect app settings

### Asana Token Not Working

- **Error**: 401 Unauthorized
  - **Solution**: Regenerate the token and ensure it's correctly copied (no extra spaces)

---

## Security Best Practices

1. **Never commit `.env` to version control**
2. **Use different credentials for development and production**
3. **Rotate credentials periodically**
4. **Monitor OAuth token usage**
5. **Implement token revocation on user logout**
6. **Use HTTPS in production for all OAuth callbacks**

---

## Support

If you encounter issues:

1. Check the server logs: `tail -f logs/atom.log`
2. Verify environment variables are loaded: `python -c "import os; print(os.getenv('NOTION_CLIENT_ID'))"`
3. Test OAuth endpoints manually using curl or Postman
4. Review the implementation in `backend/integrations/` directory

---

**Last Updated**: February 3, 2026
