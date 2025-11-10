# BYOK (Bring Your Own Keys) User Guide

## Overview

The ATOM system now supports **Bring Your Own Keys (BYOK)** - a powerful feature that allows each user to configure their own API keys for multiple AI providers. This enables:

- **Cost Optimization**: Use cheaper providers for different tasks
- **Enhanced Capabilities**: Access specialized models from different providers
- **Personal Control**: Each user manages their own API keys
- **Multi-Provider Fallback**: Automatic failover between providers

## Supported AI Providers

| Provider | Key Format | Capabilities | Cost Savings |
|----------|------------|--------------|-------------|
| **OpenAI** | `sk-...` | Chat, Embeddings, Moderation | Baseline |
| **DeepSeek AI** | `sk-...` | Chat, Embeddings | 40-60% vs OpenAI |
| **Anthropic Claude** | `sk-ant-...` | Advanced Reasoning | Premium |
| **Google Gemini** | `AIza...` | Multimodal, Embeddings | 93% vs OpenAI |
| **Azure OpenAI** | Azure Key + Endpoint | Enterprise Security | Higher cost |
| **GLM-4.6 (Zhipu AI)** | `glm-...` | Chinese Language, Multilingual | 85-90% vs OpenAI |
| **Kimi K2 (Moonshot AI)** | `sk-...` | Long Context, Document Analysis | 70-80% vs OpenAI |

## Getting Started

### 1. Access AI Provider Settings

**Web Interface (Next.js):**
- Navigate to `/settings` in your browser
- Click on "AI Providers" tab

**Desktop App:**
- Open the Settings panel
- Find "AI Provider Settings" section

### 2. Configure Your First API Key

1. **Choose a Provider**: Select from the available AI providers
2. **Get API Key**: Click "Get API Key" to visit the provider's website
3. **Save Key**: Enter your API key and click "Save Key"
4. **Test Connection**: Verify the key works with "Test Connection"

### 3. Using Multiple Providers

The system automatically:
- **Routes intelligently** based on task requirements
- **Optimizes costs** by selecting the most cost-effective provider
- **Provides fallback** if one provider fails

## API Key Management

### Adding API Keys

Each provider card shows:
- **Status**: Configured/Not Configured, Working/Failed
- **Models**: Available models for the provider
- **Capabilities**: What the provider can do (chat, embeddings, etc.)
- **Key Format**: Expected format for the API key

### Testing API Keys

Use the "Test Connection" button to verify:
- API key validity
- Provider connectivity
- Service availability

### Updating API Keys

To update an existing key:
1. Click "Update Key"
2. Enter the new API key
3. Click "Save Key"

### Removing API Keys

Click "Remove" to delete an API key. This:
- Removes the key from secure storage
- Disables the provider for your account
- Preserves your other configured providers

## Cost Optimization Features

### Automatic Provider Selection

The system intelligently selects providers based on:

1. **Task Type**:
   - Code generation → DeepSeek (96-98% savings)
   - Complex reasoning → Anthropic Claude
   - General chat → Cost-optimized provider
   - Embeddings → Google Gemini (93% savings)
   - Chinese language tasks → GLM-4.6 (85-90% savings)
   - Long context/document analysis → Kimi K2 (70-80% savings)

2. **Cost Priority**: Always selects the most cost-effective available provider

3. **Performance**: Falls back to higher-cost providers if needed

### Cost Tracking

View real-time cost savings in the provider status dashboard:
- Total configured providers
- Working providers
- Available providers

## Security & Privacy

### Key Storage

Your API keys are:
- **Encrypted** using industry-standard encryption
- **Stored securely** in the backend database
- **Never exposed** in frontend responses
- **User-specific** - each user has their own isolated keys

### Data Protection

- API keys are masked in all UI displays (showing only first/last characters)
- Keys are transmitted over secure connections only
- Regular security audits ensure protection

## Troubleshooting

### Common Issues

**API Key Not Working**
- Verify the key format matches the provider's requirements
- Check if the key has proper permissions
- Ensure the key hasn't expired or been revoked

**Provider Unavailable**
- Test the API key directly on the provider's platform
- Check provider status pages for outages
- Verify your account has sufficient credits/quota

**Connection Errors**
- Ensure backend services are running
- Check network connectivity
- Verify firewall settings

### Getting Help

1. **Check Provider Status**: Use the test functionality in settings
2. **Review Documentation**: See provider-specific requirements
3. **Contact Support**: For persistent issues, contact the ATOM support team

## Best Practices

### 1. Start with Cost-Effective Providers

Recommended setup order:
1. **Google Gemini** - Best for embeddings and general tasks
2. **DeepSeek AI** - Excellent for code generation
3. **OpenAI** - Reliable baseline provider
4. **Anthropic Claude** - Advanced reasoning tasks

### 2. Monitor Usage

- Regularly check provider status
- Monitor API usage through provider dashboards
- Set up usage alerts if available

### 3. Key Rotation

- Periodically update API keys
- Use provider-specific key rotation features
- Maintain at least 2 working providers for redundancy

### 4. Budget Management

- Set monthly spending limits with providers
- Use provider dashboards to track costs
- Enable spending alerts

## Advanced Features

### Provider Priority

The system automatically prioritizes providers based on:
- Cost efficiency
- Task compatibility
- Performance history
- Current availability

### Custom Routing (Coming Soon)

Future updates will include:
- Custom provider selection rules
- Task-specific provider assignments
- Performance-based routing

## API Integration

For developers wanting to integrate with the BYOK system:

### Backend Endpoints

All endpoints are available at `/api/user/api-keys/{user_id}`:

- `GET /providers` - List available providers
- `GET /keys` - Get user's API keys (masked)
- `POST /keys/{provider}` - Save API key
- `DELETE /keys/{provider}` - Delete API key
- `POST /keys/{provider}/test` - Test API key
- `GET /services` - Get configured services
- `GET /status` - Get comprehensive status

### Frontend Components

React components are available for easy integration:

```typescript
import AIProviderSettings from '../components/AIProviders/AIProviderSettings';

// Basic usage
<AIProviderSettings 
  userId="current-user"
  baseApiUrl="/api"
  className="custom-styles"
/>
```

## Migration from Global Keys

If you're migrating from global environment variables:

1. **Backup existing keys** from your `.env` file
2. **Configure user-specific keys** through the settings interface
3. **Test all providers** to ensure functionality
4. **Remove global keys** once user keys are confirmed working

## Support & Resources

- **Documentation**: [ATOM Documentation](https://docs.atom.example)
- **Provider Guides**: Links to each provider's API documentation
- **Community**: [ATOM Community Forum](https://community.atom.example)
- **Support**: support@atom.example

---

*Last updated: October 2024*
*ATOM BYOK System v1.0*