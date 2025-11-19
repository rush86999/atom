# AI Validator Credentials Guide

The Independent AI Validator requires API credentials for multiple AI providers to perform unbiased validation. Here's what you need:

## Required Credentials File

**Path:** `/Users/rushiparikh/projects/atom/atom/backend/independent_ai_validator/data/credentials.json`

**Format:** JSON file with API keys

## Credentials Needed

Based on the validator configuration, you need API keys for the following providers:

### 1. **DeepSeek API** (Primary - Weight: 1.0)
- **Purpose:** Cost-effective AI analysis (currently the only active provider)
- **Key Format:** `sk-[alphanumeric]`
- **How to Get:**
  1. Visit https://platform.deepseek.com
  2. Sign up for an account
  3. Navigate to API Keys section
  4. Create a new API key
- **Cost:** Very cost-effective (~$0.14 per million tokens for DeepSeek-V3)

### 2. **GLM-4 API** (Optional - Weight: 0.0, currently disabled)
- **Purpose:** Alternative cost-effective AI analysis
- **Key Format:** `[alphanumeric._-]+`
- **How to Get:**
  1. Visit https://open.bigmodel.cn
  2. Register and verify account
  3. Generate API key
- **Cost:** Cost-effective option

### 3. **Anthropic Claude** (Optional - Weight: 0.0, currently disabled)
- **Purpose:** High-quality AI analysis
- **Key Format:** `sk-ant-[alphanumeric]`
- **How to Get:**
  1. Visit https://console.anthropic.com
  2. Sign up for an account
  3. Navigate to API Keys
  4. Create a new key
- **Cost:** More expensive but high quality

### 4. **Google AI (Gemini)** (Optional - Weight: 0.0, currently disabled)
- **Purpose:** Additional validation perspective
- **Key Format:** Standard Google API key
- **How to Get:**
  1. Visit https://makersuite.google.com/app/apikey
  2. Create or select a project
  3. Generate API key
- **Cost:** Competitive pricing

## Credentials File Template

Create the file at: `/Users/rushiparikh/projects/atom/atom/backend/independent_ai_validator/data/credentials.json`

```json
{
  "deepseek": {
    "api_key": "sk-your-deepseek-key-here",
    "enabled": true
  },
  "glm": {
    "api_key": "your-glm-key-here",
    "enabled": false
  },
  "anthropic": {
    "api_key": "sk-ant-your-anthropic-key-here",
    "enabled": false
  },
  "google": {
    "api_key": "your-google-api-key-here",
    "enabled": false
  }
}
```

## Minimum Requirement

**For basic validation, you only need:**
- ✅ **DeepSeek API Key** (this is the only provider currently active with weight 1.0)

The validator is configured to use **only DeepSeek** for AI processing, so you can start with just that one key.

## Alternative: Use Environment Variables

The credential manager also supports loading from a markdown file. If you prefer, you can create:

**Path:** `/Users/rushiparikh/projects/atom/atom/backend/notes/credentials.md`

```markdown
# API Credentials

DEEPSEEK_API_KEY=sk-your-deepseek-key-here
GLM_API_KEY=your-glm-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
```

## Steps to Complete Testing

1. **Get DeepSeek API Key** (minimum requirement)
   - Go to https://platform.deepseek.com
   - Sign up and create an API key
   - Copy the key

2. **Create credentials file**
   ```bash
   mkdir -p /Users/rushiparikh/projects/atom/atom/backend/independent_ai_validator/data
   ```

3. **Add credentials** (choose one method):
   
   **Method A - JSON (Recommended):**
   ```bash
   cat > /Users/rushiparikh/projects/atom/atom/backend/independent_ai_validator/data/credentials.json << 'EOF'
   {
     "deepseek": {
       "api_key": "sk-your-actual-key-here",
       "enabled": true
     }
   }
   EOF
   ```

   **Method B - Markdown:**
   ```bash
   mkdir -p /Users/rushiparikh/projects/atom/atom/backend/notes
   echo "DEEPSEEK_API_KEY=sk-your-actual-key-here" > /Users/rushiparikh/projects/atom/atom/backend/notes/credentials.md
   ```

4. **Run the validator**
   ```bash
   cd /Users/rushiparikh/projects/atom/atom/backend
   python3 comprehensive_app_readiness_validator.py
   ```

## Cost Estimate

Using only DeepSeek for the comprehensive validation:
- **6 claims** to validate
- Estimated **~10,000 tokens** per claim
- Total: **~60,000 tokens**
- Cost: **~$0.01** (less than 1 cent)

DeepSeek is extremely cost-effective for this use case!

## Security Note

⚠️ **Important:** Never commit the credentials file to git. The `.gitignore` should already exclude these paths:
- `**/credentials.json`
- `**/credentials.md`
- `**/notes/credentials.md`

Make sure to verify this before creating the credentials file.
