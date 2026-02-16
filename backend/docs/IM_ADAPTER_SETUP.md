# IM Adapter Setup Guide

Complete guide for integrating Telegram and WhatsApp with Atom Agent OS.

## Overview

Atom supports incoming webhooks from Telegram and WhatsApp, allowing users to interact with agents via IM platforms. All IM interactions are secured with:
- Webhook signature verification (prevents spoofing)
- Rate limiting (10 req/min per user)
- Governance checks (STUDENT agents blocked)
- Comprehensive audit trail

## Prerequisites

- Atom backend running (port 8000)
- Public HTTPS URL for webhook endpoints (use ngrok for development)
- Telegram Bot account (free)
- WhatsApp Business account (Meta Business Suite)

---

## Telegram Setup

### Step 1: Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow prompts to name your bot (e.g., "AtomAgentBot")
4. BotFather will provide a **Bot Token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token - you'll need it for environment configuration

### Step 2: Configure Webhook

Set your webhook URL to point to Atom:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-atom-domain.com/api/telegram/webhook",
    "secret_token": "YOUR_SECRET_TOKEN"
  }'
```

Replace:
- `<YOUR_BOT_TOKEN>`: Token from BotFather
- `https://your-atom-domain.com`: Your public Atom URL
- `YOUR_SECRET_TOKEN`: Random string for webhook verification (generate with: `openssl rand -hex 32`)

### Step 3: Configure Environment Variables

Add to your `.env` file:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_SECRET_TOKEN=your_random_secret_token_here
```

### Step 4: Verify Setup

Test your bot:

```bash
# Check webhook status
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Send test message to your bot in Telegram
# Check logs: tail -f logs/atom.log | grep telegram
```

Expected response: `{"ok":true,"result":{"url":"https://...","has_custom_certificate":false,...}}`

---

## WhatsApp Setup

### Step 1: Create WhatsApp Business App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app (select "Business" type)
3. Add "WhatsApp" product
4. Complete WhatsApp setup (phone number verification)

### Step 2: Get Credentials

From your WhatsApp app settings:
- **Phone Number ID**: Found in WhatsApp > API Setup
- **Access Token**: Generate temporary token (for production, use permanent token)
- **App Secret**: Found in app Settings > Basic
- **Verify Token**: Set your own random string

### Step 3: Configure Webhook

1. In Meta Dashboard, go to WhatsApp > Configuration
2. Click "Edit" next to Webhook
3. Enter: `https://your-atom-domain.com/api/whatsapp/webhook`
4. Enter your **Verify Token** (random string)
5. Click "Verify and Save"

### Step 4: Subscribe to Webhook Events

Subscribe to these events:
- `messages`
- `message_status` (optional, for delivery receipts)

### Step 5: Configure Environment Variables

Add to your `.env` file:

```bash
# WhatsApp Configuration
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_APP_SECRET=your_app_secret_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
```

### Step 6: Verify Setup

Test your webhook:

```bash
# Send test message via WhatsApp to your configured number
# Check logs: tail -f logs/atom.log | grep whatsapp
```

---

## Development with Ngrok

For local development, use [ngrok](https://ngrok.com/) to expose your local server:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Start ngrok tunnel
ngrok http 8000

# Use the HTTPS URL in webhook configuration
# Example: https://abc123.ngrok.io/api/telegram/webhook
```

---

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram Bot API token | `123456789:ABCdef...` |
| `TELEGRAM_SECRET_TOKEN` | Yes | Webhook verification secret | `random_hex_string` |
| `WHATSAPP_ACCESS_TOKEN` | Yes (for WhatsApp) | WhatsApp Cloud API token | `EAAabcdef123...` |
| `WHATSAPP_APP_SECRET` | Yes (for WhatsApp) | App secret for signature verification | `abc123def456` |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (for WhatsApp) | Phone number ID from Meta | `123456789012345` |

---

## Testing Your Integration

### Telegram Test Commands

Send these messages to your bot:

```
/start - Initialize bot
/agents - List available agents
/run <agent> <task> - Execute agent task
/status - Check bot status
/help - Show available commands
```

### WhatsApp Test Commands

```
/run <agent> <task> - Execute agent task
/agents - List available agents
/status - Check bot status
```

---

## Troubleshooting

### Telegram: Webhook Not Receiving Messages

**Symptom**: Messages sent to bot not appearing in logs

**Solutions**:
1. Verify webhook is set: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
2. Check `TELEGRAM_BOT_TOKEN` is correct
3. Check `TELEGRAM_SECRET_TOKEN` matches what you set
4. Check firewall allows incoming HTTPS traffic

### WhatsApp: Verification Fails

**Symptom**: Webhook verification returns 403

**Solutions**:
1. Verify `WHATSAPP_APP_SECRET` matches Meta dashboard
2. Check verify token matches in both places
3. Ensure webhook URL is publicly accessible (not localhost)
4. Check ngrok is running if using for development

### Rate Limiting Issues

**Symptom**: Legitimate users getting 429 errors

**Solutions**:
1. Current limit: 10 req/min per user_id
2. Increase by modifying `IMGovernanceService` (not recommended for production)
3. Add user to whitelist: `IM_RATE_LIMIT_WHITELIST=user@example.com`

### Governance Blocking

**Symptom**: Commands return 403 Forbidden

**Solutions**:
1. Check agent maturity level (STUDENT agents blocked from IM)
2. Check if user is blocked: `im_blocked:telegram:user_id` in GovernanceCache
3. Verify IMGovernanceService is initialized

---

## Security Checklist

Before deploying to production:

- [ ] All webhook verification secrets are strong (>32 characters)
- [ ] HTTPS is enforced (HTTP rejected)
- [ ] Rate limiting is enabled (10 req/min)
- [ ] Audit trail logging is enabled
- [ ] Governance checks are active
- [ ] Webhook URLs are not guessable
- [ ] Secrets are stored securely (not in code)
- [ ] ngrok is NOT used in production

---

## Next Steps

After setup:
1. Test basic commands (see Testing section)
2. Review security best practices (see `IM_SECURITY_BEST_PRACTICES.md`)
3. Configure agent permissions for IM access
4. Set up monitoring for webhook failures
5. Configure alerting for rate limit violations

---

## Support

For issues or questions:
- Check logs: `tail -f logs/atom.log | grep -E "telegram|whatsapp"`
- Review audit trail: `SELECT * FROM im_audit_logs ORDER BY timestamp DESC LIMIT 100;`
- Check health endpoints: `/api/telegram/health`, `/api/whatsapp/health`
