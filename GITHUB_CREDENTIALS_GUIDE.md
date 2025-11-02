# GitHub Credential Setup Guide

## 🔑 GitHub Integration Credentials

GitHub integration requires both OAuth credentials and a Personal Access Token for full functionality.

## 📋 Required Credentials

### 1. GitHub OAuth App Credentials
- `GITHUB_CLIENT_ID` - Your GitHub OAuth App Client ID
- `GITHUB_CLIENT_SECRET` - Your GitHub OAuth App Client Secret

### 2. GitHub Personal Access Token
- `GITHUB_TOKEN` - Personal Access Token for API access

## 🚀 Step-by-Step Setup

### Step 1: Create GitHub OAuth App

1. **Go to GitHub Developer Settings:**
   - Visit: https://github.com/settings/developers
   - Or navigate: Your Profile → Settings → Developer settings → OAuth Apps

2. **Register New OAuth Application:**
   - Click "New OAuth App"
   - Fill in the details:
     - **Application name**: `ATOM Integration`
     - **Homepage URL**: `http://localhost:3000` (or your production URL)
     - **Authorization callback URL**: `http://localhost:5058/api/auth/github/callback`

3. **Get Client ID and Secret:**
   - Copy the **Client ID** and **Client Secret**
   - These will be your `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`

### Step 2: Create Personal Access Token

1. **Go to Personal Access Tokens:**
   - Visit: https://github.com/settings/tokens
   - Or navigate: Your Profile → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate New Token:**
   - Click "Generate new token" → "Generate new token (classic)"
   - Give it a descriptive name: `ATOM Integration Token`
   - Set expiration (recommended: 1 year for development)
   - Select required scopes:
     - ✅ **repo** (Full control of private repositories)
     - ✅ **read:org** (Read org and team membership)
     - ✅ **read:user** (Read user profile data)
     - ✅ **user:email** (Read user email addresses)
     - ✅ **read:project** (Read project boards)

3. **Generate and Copy Token:**
   - Click "Generate token"
   - **IMPORTANT**: Copy the token immediately (you won't see it again!)
   - This will be your `GITHUB_TOKEN`

### Step 3: Add Credentials to .env File

Add these lines to your `.env` file:

```bash
# GitHub Integration
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_TOKEN=ghp_your_personal_access_token_here
```

**Example:**
```bash
GITHUB_CLIENT_ID=Ov23li2ZCb3JvRNjVGni
GITHUB_CLIENT_SECRET=aac3bcee94c9466169687ed788f288cb8c73aa4d
GITHUB_TOKEN=ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456789
```

## 🔍 Verification Steps

### Test GitHub Credentials

Run the verification script to test your credentials:

```bash
python test_github_credentials.py
```

### Manual Verification

You can also test manually with curl:

```bash
# Test Personal Access Token
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/user

# Test OAuth App (if you have client credentials)
curl -X POST \
     -H "Accept: application/json" \
     -d '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET","code":"AUTHORIZATION_CODE"}' \
     https://github.com/login/oauth/access_token
```

## 🛠️ Troubleshooting

### Common Issues

1. **Invalid Credentials Error:**
   - Verify all credentials are copied correctly
   - Check for extra spaces or characters
   - Ensure tokens haven't expired

2. **Insufficient Scopes:**
   - Regenerate Personal Access Token with required scopes
   - Ensure OAuth App has correct callback URL

3. **Rate Limiting:**
   - GitHub has API rate limits
   - Personal Access Tokens have higher limits than anonymous requests

4. **Network Issues:**
   - Check internet connectivity
   - Verify GitHub API endpoint is accessible

### Security Best Practices

- 🔒 Store credentials in `.env` file (never commit to version control)
- 🔄 Rotate tokens regularly (especially in production)
- 📋 Use least privilege principle for token scopes
- 🚫 Never share tokens in public repositories
- 🔐 Consider using GitHub's fine-grained personal access tokens for better security

## 📊 Expected Results

When credentials are properly configured:

- ✅ GitHub OAuth flow should work in ATOM settings
- ✅ Repository listing and access should function
- ✅ Issue creation and management should work
- ✅ Pull request operations should be available
- ✅ User profile and organization data should be accessible

## 🎯 Next Steps After Setup

1. **Test OAuth Flow:**
   - Start the OAuth server: `python start_complete_oauth_server.py`
   - Navigate to ATOM settings → Integrations → GitHub
   - Click "Connect" and complete OAuth flow

2. **Verify API Access:**
   - Check if repositories are listed
   - Test issue creation
   - Verify webhook setup (if configured)

3. **Production Deployment:**
   - Update callback URLs for production domain
   - Set up environment-specific credentials
   - Configure webhooks for real-time updates

## 📞 Support

If you encounter issues:

1. Check GitHub's API status: https://www.githubstatus.com/
2. Review GitHub API documentation: https://docs.github.com/en/rest
3. Check ATOM integration logs for detailed error messages
4. Verify all credential values are correctly formatted

---

**Note**: This guide assumes you're using GitHub.com. For GitHub Enterprise Server, replace API endpoints with your enterprise URL.